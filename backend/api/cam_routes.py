"""
api/cam_routes.py
─────────────────────────────────────────────────────────────────────────────
FastAPI routes for CAM generation and download.
Step 6: Full pipeline — narrative → docx → download.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings, OUTPUT_DIR, DEMO_DIR
from database import get_session, Case, Document, ScoringResult, ResearchResult, CaseInsight
from audit.audit_logger import log_event
from cam.llm_narrator import generate_cam_narrative
from cam.doc_builder import build_cam_docx
from research.litigation_detector import detect_litigation, summary_to_dict

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class CAMGenerateResponse(BaseModel):
    case_id:      str
    status:       str
    filename:     str
    download_url: str
    pages_est:    int
    model_used:   str
    message:      str

class CAMStatusResponse(BaseModel):
    case_id:    str
    exists:     bool
    filename:   str | None
    size_kb:    float | None
    generated_at: str | None


# ── Generate CAM ──────────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/cam",
             response_model=CAMGenerateResponse,
             summary="Generate Credit Appraisal Memo (DOCX)")
async def generate_cam(
    case_id:    str,
    analyst_id: str = "System",
    session:    AsyncSession = Depends(get_session),
):
    """
    Generates the full CAM Word document in one call.
    Pipeline:
      1. Load all data from DB (financial, scorecard, research, GST)
      2. Run litigation_detector for summary
      3. Call llm_narrator for 5 narrative sections (Claude API or template)
      4. Call doc_builder to produce the .docx via Node.js
      5. Store file path, log event, return download URL

    Prerequisites: /load-demo + /analyze + /score must be run first.
    """
    # ── Verify case ────────────────────────────────────────────────────────────
    case_res = await session.execute(select(Case).where(Case.id == case_id))
    case = case_res.scalar_one_or_none()
    if not case:
        raise HTTPException(404, f"Case {case_id} not found.")

    # ── Load scorecard ─────────────────────────────────────────────────────────
    sc_res = await session.execute(
        select(ScoringResult)
        .where(ScoringResult.case_id == case_id)
        .order_by(ScoringResult.scored_at.desc())
    )
    sc_rec = sc_res.scalar_one_or_none()
    if not sc_rec:
        raise HTTPException(
            400,
            "No scoring result found. Run /score before generating the CAM."
        )

    # ── Load financial data ────────────────────────────────────────────────────
    financial_data = await _load_doc_json(session, case_id, "balance_sheet")
    if not financial_data:
        raise HTTPException(400, "No financial data found. Run /load-demo first.")

    wc_analysis = financial_data.get("working_capital_analysis", {})
    rp_analysis = financial_data.get("related_party_analysis", {})

    # ── Load GST data ──────────────────────────────────────────────────────────
    gst_data = await _load_doc_json(session, case_id, "gstr_3b") or {}

    # ── Load research findings ─────────────────────────────────────────────────
    research_items = await _load_research_items(session, case_id)

    # ── Load research cache for litigation detector ────────────────────────────
    research_cache = await _load_research_cache(session, case_id)
    lit_summary = summary_to_dict(detect_litigation(research_cache))

    # ── Load insights (field observations) ─────────────────────────────────────
    insights_rec = await session.execute(
        select(CaseInsight).where(CaseInsight.case_id == case_id)
    )
    insights = insights_rec.scalar_one_or_none()
    insights_dict = None
    if insights:
        insights_dict = {
            "notes": insights.notes,
            "adjustments": insights.adjustments_json,
            "total_delta": insights.total_delta,
            "created_at": insights.created_at.isoformat() if insights.created_at else "",
            "created_by": insights.created_by,
        }

    # ── Build scorecard + loan sizing dicts from stored result ─────────────────
    fv = sc_rec.feature_values or {}
    scorecard_dict = {
        "risk_grade":         sc_rec.risk_grade,
        "risk_label":         _grade_label(sc_rec.risk_grade),
        "normalised_score":   sc_rec.normalized_score,
        "total_raw_score":    sc_rec.total_raw_score,
        "decision":           sc_rec.decision,
        "primary_rejection_trigger": sc_rec.primary_rejection_trigger or "",
        "counter_factual":    sc_rec.counter_factual or "",
        "knockout_flags":     fv.get("knockout_flags", []),
        "pillar_scores":      fv.get("pillar_scores", {}),
        "contributions":      sc_rec.score_contributions or {},
        "recommended_rate_pct": sc_rec.recommended_rate_pct or 0,
    }
    loan_sizing_dict = fv.get("loan_sizing", {})

    # ── Load override log if any ──────────────────────────────────────────────
    override_log = []
    if sc_rec.is_overridden:
        override_log.append({
            "overridden_at": sc_rec.overridden_at.isoformat() if sc_rec.overridden_at else "",
            "override_by":   sc_rec.override_by or "",
            "decision":      sc_rec.decision,
            "override_reason": sc_rec.override_reason or "",
        })

    # ── Step 6a: Generate narrative (LLM or template) ─────────────────────────
    narrative = await generate_cam_narrative(
        financial_data=financial_data,
        scorecard=scorecard_dict,
        loan_sizing=loan_sizing_dict,
        wc_analysis=wc_analysis,
        rp_analysis=rp_analysis,
        research_cache=research_cache,
        lit_summary=lit_summary,
        insights=insights_dict,
    )

    await log_event(
        session, "CAM_NARRATIVE_GENERATED",
        f"CAM narrative generated using {narrative.model_used}",
        case_id=case_id, actor=analyst_id,
        output_data={"model": narrative.model_used, "warnings": narrative.warnings},
    )

    # ── Step 6b: Build DOCX ────────────────────────────────────────────────────
    doc_path = build_cam_docx(
        case_id=case_id,
        financial_data=financial_data,
        scorecard=scorecard_dict,
        loan_sizing=loan_sizing_dict,
        wc_analysis=wc_analysis,
        rp_analysis=rp_analysis,
        gst_recon=gst_data,
        research_items=research_items,
        lit_summary=lit_summary,
        narrative=narrative,
        analyst_id=analyst_id,
        override_log=override_log,
        insights=insights_dict,
    )

    suffix    = doc_path.suffix          # .docx or .txt
    filename  = doc_path.name
    size_kb   = doc_path.stat().st_size / 1024 if doc_path.exists() else 0
    pages_est = max(1, int(size_kb / 12))  # ~12KB per page rough estimate

    await log_event(
        session, "CAM_GENERATED",
        f"CAM document generated: {filename} ({size_kb:.0f} KB, ~{pages_est} pages)",
        case_id=case_id, actor=analyst_id,
        output_data={"filename": filename, "size_kb": round(size_kb, 1)},
    )

    # Update case status
    case.status = "cam_generated"
    session.add(case)

    logger.info(
        "CAM generated: case=%s file=%s size=%.0fKB model=%s",
        case_id, filename, size_kb, narrative.model_used
    )

    return CAMGenerateResponse(
        case_id=case_id,
        status="generated",
        filename=filename,
        download_url=f"/api/v1/cases/{case_id}/cam/download",
        pages_est=pages_est,
        model_used=narrative.model_used,
        message=(
            f"CAM generated for {case.company_name}: {filename} "
            f"({size_kb:.0f} KB, ~{pages_est} pages). "
            f"Narrative: {narrative.model_used}. "
            f"Download at /api/v1/cases/{case_id}/cam/download"
        ),
    )


# ── Download CAM ──────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/cam/download",
            summary="Download the generated CAM DOCX")
async def download_cam(
    case_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Returns the generated CAM file as a download.
    Tries .docx first, falls back to .txt.
    Returns 404 if CAM has not been generated yet.
    """
    for ext, media in [
        (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        (".txt",  "text/plain"),
    ]:
        cam_path = Path(OUTPUT_DIR) / f"{case_id}_CAM{ext}"
        if cam_path.exists():
            short_id = case_id[:8].upper()
            return FileResponse(
                path=str(cam_path),
                media_type=media,
                filename=f"CreditAppraisalMemo_{short_id}{ext}",
            )

    raise HTTPException(
        404,
        "CAM document not found. Run POST /cases/{case_id}/cam to generate it first."
    )


# ── CAM Status ────────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/cam/status",
            response_model=CAMStatusResponse,
            summary="Check if a CAM has been generated")
async def cam_status(
    case_id: str,
    session: AsyncSession = Depends(get_session),
):
    for ext in (".docx", ".txt"):
        cam_path = Path(OUTPUT_DIR) / f"{case_id}_CAM{ext}"
        if cam_path.exists():
            stat = cam_path.stat()
            return CAMStatusResponse(
                case_id=case_id,
                exists=True,
                filename=cam_path.name,
                size_kb=round(stat.st_size / 1024, 1),
                generated_at=datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            )

    return CAMStatusResponse(
        case_id=case_id, exists=False,
        filename=None, size_kb=None, generated_at=None,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_doc_json(
    session: AsyncSession, case_id: str, doc_type: str
) -> dict | None:
    result = await session.execute(
        select(Document).where(
            Document.case_id == case_id,
            Document.doc_type == doc_type,
            Document.status == "extracted",
        ).order_by(Document.processed_at.desc())
    )
    doc = result.scalars().first()
    return doc.extracted_json if doc else None


async def _load_research_items(
    session: AsyncSession, case_id: str
) -> list[dict]:
    result = await session.execute(
        select(ResearchResult)
        .where(ResearchResult.case_id == case_id)
        .order_by(ResearchResult.risk_score_delta.asc())
    )
    items = result.scalars().all()
    return [
        {
            "title":            r.title,
            "url":              r.url,
            "source_name":      r.source_name,
            "result_type":      r.result_type,
            "risk_tier":        r.risk_tier,
            "risk_score_delta": r.risk_score_delta,
            "matched_keywords": r.matched_keywords or [],
            "is_cached":        r.is_cached,
        }
        for r in items
    ]


async def _load_research_cache(
    session: AsyncSession, case_id: str
) -> dict:
    result = await session.execute(
        select(Document).where(
            Document.case_id == case_id,
            Document.filename == "research_cache_demo.json",
        ).order_by(Document.processed_at.desc())
    )
    doc = result.scalars().first()
    if doc and doc.file_path:
        try:
            with open(doc.file_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _grade_label(grade: str) -> str:
    return {
        "A+": "Excellent", "A": "Strong",
        "B+": "Acceptable", "B": "Marginal",
        "C": "Watch", "D": "Decline",
    }.get(grade or "", "Unknown")