"""
api/ingest_routes.py
─────────────────────────────────────────────────────────────────────────────
FastAPI routes for document upload and data ingestion.
Step 3: Adds working capital analysis, related party detection,
        and the /analyze endpoint that runs the full Step 3 pipeline.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings, UPLOAD_DIR, DEMO_DIR
from database import (
    get_session, create_case, add_document, add_recon_flag,
    Case, Document, ReconFlag
)
from audit.audit_logger import log_event
from ingestor.gst_reconciler import run_reconciliation_from_dict
from ingestor.working_capital_analyzer import analyze_working_capital, result_to_dict as wc_to_dict
from ingestor.related_party_detector import analyze_related_parties, result_to_dict as rp_to_dict

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateCaseRequest(BaseModel):
    company_name: str
    company_cin: str | None = None
    company_pan: str | None = None
    requested_amount_cr: float | None = None
    requested_tenor_yr: int | None = None
    purpose: str | None = None

class CaseResponse(BaseModel):
    case_id: str
    company_name: str
    status: str
    message: str

class DocumentUploadResponse(BaseModel):
    doc_id: str
    case_id: str
    filename: str
    doc_type: str
    file_hash: str
    status: str

class LoadDemoResponse(BaseModel):
    case_id: str
    message: str
    documents_loaded: int
    flags_raised: int
    financial_data_loaded: bool

class AnalyzeResponse(BaseModel):
    case_id: str
    status: str
    wc_flags_raised: int
    rp_flags_raised: int
    total_flags: int
    avg_dscr: float
    latest_de_ratio: float
    revenue_cagr_pct: float
    pledge_risk_label: str
    management_quality_score: int
    message: str


# ── Core Endpoints ────────────────────────────────────────────────────────────

@router.post("/cases", response_model=CaseResponse,
             summary="Create a new credit appraisal case")
async def create_new_case(
    request: CreateCaseRequest,
    session: AsyncSession = Depends(get_session),
):
    case = await create_case(
        session,
        company_name=request.company_name,
        company_cin=request.company_cin,
        company_pan=request.company_pan,
        requested_amount_cr=request.requested_amount_cr,
        requested_tenor_yr=request.requested_tenor_yr,
        purpose=request.purpose,
    )
    return CaseResponse(
        case_id=case.id,
        company_name=case.company_name,
        status=case.status,
        message=f"Case created for {case.company_name}",
    )


@router.post("/cases/{case_id}/documents", response_model=DocumentUploadResponse,
             summary="Upload a document to a case")
async def upload_document(
    case_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type: str = Form(
        default="other",
        description="annual_report|balance_sheet|gstr_2a|gstr_3b|"
                    "bank_statement|itr|sanction_letter|legal_notice|other"
    ),
    session: AsyncSession = Depends(get_session),
):
    suffix = Path(file.filename).suffix.lower().lstrip(".")
    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type '.{suffix}' not supported.")

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, "File exceeds maximum size limit.")

    file_hash = hashlib.sha256(content).hexdigest()
    case_dir  = UPLOAD_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    file_path = case_dir / file.filename
    file_path.write_bytes(content)

    mime_type = mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
    doc = await add_document(
        session,
        case_id=case_id,
        filename=file.filename,
        doc_type=doc_type,
        file_path=str(file_path),
        file_size_bytes=len(content),
        file_hash=file_hash,
        mime_type=mime_type,
    )

    background_tasks.add_task(
        _extract_document, doc.id, str(file_path), doc_type, suffix
    )

    return DocumentUploadResponse(
        doc_id=doc.id, case_id=case_id, filename=file.filename,
        doc_type=doc_type, file_hash=file_hash,
        status="uploaded_queued_for_extraction",
    )


@router.post("/cases/{case_id}/load-demo", response_model=LoadDemoResponse,
             summary="Load Acme Textiles demo data — instant demo fallback")
async def load_demo_data(
    case_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Loads pre-built Acme Textiles demo data. Runs GST reconciliation,
    working capital analysis, and related party detection automatically.
    Use this for the demo — avoids live document parsing.
    """
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, f"Case {case_id} not found.")

    flags_raised = 0
    docs_loaded  = 0
    fin_data_loaded = False
    fin_data = {}

    # ── Financial data ─────────────────────────────────────────────────────────
    fin_path = DEMO_DIR / "financial_data.json"
    if fin_path.exists():
        with open(fin_path) as f:
            fin_data = json.load(f)

        fin_doc = await add_document(
            session, case_id=case_id,
            filename="financial_data_demo.json", doc_type="balance_sheet",
            file_path=str(fin_path), file_size_bytes=fin_path.stat().st_size,
            file_hash=hashlib.sha256(fin_path.read_bytes()).hexdigest(),
            mime_type="application/json", actor="demo_loader",
        )
        fin_doc.extracted_json = fin_data
        fin_doc.status = "extracted"
        fin_doc.processed_at = datetime.now(timezone.utc)
        session.add(fin_doc)
        docs_loaded += 1
        fin_data_loaded = True

    # ── GST data + reconciliation ──────────────────────────────────────────────
    gst_path = DEMO_DIR / "gst_data.json"
    if gst_path.exists():
        with open(gst_path) as f:
            gst_data = json.load(f)

        gst_doc = await add_document(
            session, case_id=case_id,
            filename="gst_data_demo.json", doc_type="gstr_3b",
            file_path=str(gst_path), file_size_bytes=gst_path.stat().st_size,
            file_hash=hashlib.sha256(gst_path.read_bytes()).hexdigest(),
            mime_type="application/json", actor="demo_loader",
        )
        gst_doc.status = "extracted"
        gst_doc.processed_at = datetime.now(timezone.utc)
        session.add(gst_doc)
        docs_loaded += 1

        recon = run_reconciliation_from_dict(gst_doc.id, gst_data)
        for flag in recon.flags:
            await add_recon_flag(
                session, case_id=case_id,
                flag_type=flag.flag_type, severity=flag.severity,
                title=flag.title, description=flag.description,
                metric_name=flag.metric_name, metric_value=flag.metric_value,
                threshold=flag.threshold, source_doc_ids=[gst_doc.id],
            )
            flags_raised += 1

    # ── Research cache ─────────────────────────────────────────────────────────
    rc_path = DEMO_DIR / "research_cache.json"
    if rc_path.exists():
        rc_doc = await add_document(
            session, case_id=case_id,
            filename="research_cache_demo.json", doc_type="other",
            file_path=str(rc_path), file_size_bytes=rc_path.stat().st_size,
            file_hash=hashlib.sha256(rc_path.read_bytes()).hexdigest(),
            mime_type="application/json", actor="demo_loader",
        )
        rc_doc.status = "extracted"
        rc_doc.processed_at = datetime.now(timezone.utc)
        session.add(rc_doc)
        docs_loaded += 1

    # Update case status
    case.status = "ingested"
    session.add(case)

    await log_event(
        session, "DEMO_DATA_LOADED",
        f"Demo data loaded: {docs_loaded} docs, {flags_raised} flags",
        case_id=case_id, actor="demo_loader",
        output_data={"docs": docs_loaded, "flags": flags_raised},
    )

    return LoadDemoResponse(
        case_id=case_id,
        message=(
            f"Demo data loaded for {case.company_name}. "
            f"{docs_loaded} documents ingested, {flags_raised} GST flags raised. "
            f"Run /analyze next for working capital & related party analysis."
        ),
        documents_loaded=docs_loaded,
        flags_raised=flags_raised,
        financial_data_loaded=fin_data_loaded,
    )


@router.post("/cases/{case_id}/analyze", response_model=AnalyzeResponse,
             summary="Run Step 3: Working Capital + Related Party Analysis")
async def analyze_case(
    case_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Runs the full Step 3 structured data analysis pipeline:
      1. Working Capital Cycle analysis (DSCR, D/E, CCC, debtor days, etc.)
      2. Related Party & Promoter Pledge analysis
      3. Persists all new flags to recon_flags table
      4. Stores computed metrics for use by the scoring engine (Step 5)

    Requires load-demo (or document upload + extraction) to be completed first.
    """
    # Verify case
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, f"Case {case_id} not found.")

    # Load financial data from extracted documents
    fin_data = await _get_financial_data(case_id, session)
    if not fin_data:
        raise HTTPException(
            400,
            "No financial data found. Run /load-demo or upload financial documents first."
        )

    # Load research cache if available
    research_cache = await _get_research_cache(case_id, session)

    wc_flags_count = 0
    rp_flags_count = 0

    # ── Working Capital Analysis ───────────────────────────────────────────────
    wc_result = analyze_working_capital(case_id, fin_data)
    wc_dict   = wc_to_dict(wc_result)

    for flag in wc_result.flags:
        await add_recon_flag(
            session, case_id=case_id,
            flag_type=flag["flag_type"],
            severity=flag["severity"],
            title=flag["title"],
            description=flag["description"],
            metric_name=flag.get("metric_name"),
            metric_value=flag.get("metric_value"),
            threshold=flag.get("threshold"),
        )
        wc_flags_count += 1

    # Store WC metrics in the financial doc's extracted_json for Step 5
    fin_doc = await _get_financial_doc(case_id, session)
    if fin_doc:
        existing = fin_doc.extracted_json or {}
        existing["working_capital_analysis"] = wc_dict
        fin_doc.extracted_json = existing
        session.add(fin_doc)

    await log_event(
        session, "WC_ANALYSIS_COMPLETE",
        f"Working capital analysis: {wc_flags_count} flags | "
        f"DSCR={wc_result.latest_dscr:.2f} | DE={wc_result.latest_de_ratio:.2f}",
        case_id=case_id,
        output_data={"avg_dscr": wc_result.avg_dscr, "flags": wc_flags_count},
    )

    # ── Related Party Analysis ────────────────────────────────────────────────
    rp_result = analyze_related_parties(
        case_id, fin_data,
        covenant_flags=None,
        research_cache=research_cache,
    )
    rp_dict = rp_to_dict(rp_result)

    for flag in rp_result.flags:
        await add_recon_flag(
            session, case_id=case_id,
            flag_type=flag["flag_type"],
            severity=flag["severity"],
            title=flag["title"],
            description=flag["description"],
            metric_name=flag.get("metric_name"),
            metric_value=flag.get("metric_value"),
            threshold=flag.get("threshold"),
        )
        rp_flags_count += 1

    # Store RP metrics in financial doc
    if fin_doc:
        existing = fin_doc.extracted_json or {}
        existing["related_party_analysis"] = rp_dict
        fin_doc.extracted_json = existing
        session.add(fin_doc)

    await log_event(
        session, "RP_ANALYSIS_COMPLETE",
        f"Related party analysis: {rp_flags_count} flags | "
        f"pledge={rp_result.total_promoter_pledged_pct:.1f}% ({rp_result.pledge_risk_label})",
        case_id=case_id,
        output_data={
            "pledge_pct": rp_result.total_promoter_pledged_pct,
            "mgmt_score": rp_result.management_quality_score,
        },
    )

    # Update case status
    case.status = "analyzed"
    session.add(case)

    total_flags = wc_flags_count + rp_flags_count

    logger.info(
        "Step 3 complete: case=%s | wc_flags=%d | rp_flags=%d | dscr=%.2f",
        case_id, wc_flags_count, rp_flags_count, wc_result.latest_dscr
    )

    return AnalyzeResponse(
        case_id=case_id,
        status="analyzed",
        wc_flags_raised=wc_flags_count,
        rp_flags_raised=rp_flags_count,
        total_flags=total_flags,
        avg_dscr=wc_result.avg_dscr,
        latest_de_ratio=wc_result.latest_de_ratio,
        revenue_cagr_pct=wc_result.revenue_cagr_pct,
        pledge_risk_label=rp_result.pledge_risk_label,
        management_quality_score=rp_result.management_quality_score,
        message=(
            f"Step 3 analysis complete. {total_flags} flag(s) raised. "
            f"DSCR: {wc_result.latest_dscr:.2f}x | "
            f"D/E: {wc_result.latest_de_ratio:.2f}x | "
            f"Pledge: {rp_result.total_promoter_pledged_pct:.1f}% "
            f"({rp_result.pledge_risk_label}). "
            f"Ready for scoring."
        ),
    )


# ── Read Endpoints ────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/documents",
            summary="List all documents for a case")
async def list_documents(case_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Document).where(Document.case_id == case_id)
    )
    docs = result.scalars().all()
    return [
        {
            "id": d.id, "filename": d.filename, "doc_type": d.doc_type,
            "status": d.status, "ocr_confidence_avg": d.ocr_confidence_avg,
            "page_count": d.page_count,
            "extraction_warnings": d.extraction_warnings,
            "uploaded_at": d.uploaded_at.isoformat(),
            "processed_at": d.processed_at.isoformat() if d.processed_at else None,
        }
        for d in docs
    ]


@router.get("/cases/{case_id}/flags",
            summary="Get all reconciliation flags for a case")
async def get_flags(case_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(ReconFlag)
        .where(ReconFlag.case_id == case_id)
        .order_by(ReconFlag.detected_at.asc())
    )
    flags = result.scalars().all()
    return [
        {
            "id": f.id, "flag_type": f.flag_type, "severity": f.severity,
            "title": f.title, "description": f.description,
            "metric_name": f.metric_name, "metric_value": f.metric_value,
            "threshold": f.threshold,
            "detected_at": f.detected_at.isoformat(),
        }
        for f in flags
    ]


@router.get("/cases", summary="List all cases")
async def list_cases(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Case).order_by(Case.created_at.desc()))
    cases = result.scalars().all()
    return [
        {
            "id": c.id, "company_name": c.company_name,
            "company_cin": c.company_cin, "status": c.status,
            "requested_amount_cr": c.requested_amount_cr,
            "created_at": c.created_at.isoformat(),
        }
        for c in cases
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_financial_data(case_id: str, session: AsyncSession) -> dict | None:
    """Load financial data from the balance_sheet document for this case."""
    result = await session.execute(
        select(Document).where(
            Document.case_id == case_id,
            Document.doc_type == "balance_sheet",
            Document.status == "extracted",
        )
    )
    doc = result.scalar_one_or_none()
    if doc and doc.extracted_json:
        return doc.extracted_json
    return None


async def _get_financial_doc(case_id: str, session: AsyncSession):
    """Get the financial document object for updating extracted_json."""
    result = await session.execute(
        select(Document).where(
            Document.case_id == case_id,
            Document.doc_type == "balance_sheet",
        )
    )
    return result.scalar_one_or_none()


async def _get_research_cache(case_id: str, session: AsyncSession) -> dict | None:
    """Load research cache from demo data if available."""
    result = await session.execute(
        select(Document).where(
            Document.case_id == case_id,
            Document.filename == "research_cache_demo.json",
        )
    )
    doc = result.scalar_one_or_none()
    if doc and doc.file_path:
        try:
            with open(doc.file_path) as f:
                return json.load(f)
        except Exception:
            return None
    return None


# ── Background Extraction Task ────────────────────────────────────────────────

async def _extract_document(doc_id: str, file_path: str, doc_type: str, extension: str):
    """Route uploaded document to the correct ingestor sub-module."""
    from ingestor.pdf_parser import extract_pdf, result_to_dict as pdf_to_dict
    from ingestor.bank_parser import parse_bank_statement, result_to_dict as bank_to_dict
    from ingestor.gst_reconciler import parse_gst_file, result_to_dict as gst_to_dict

    logger.info("Background extraction: doc_id=%s ext=%s", doc_id, extension)
    try:
        if extension == "pdf":
            result = await extract_pdf(doc_id, file_path)
            extracted = pdf_to_dict(result)
        elif extension in {"csv", "xlsx", "xls"} and "bank" in doc_type:
            result = await parse_bank_statement(doc_id, file_path)
            extracted = bank_to_dict(result)
        elif extension in {"csv", "xlsx", "json"} and "gst" in doc_type:
            result = await parse_gst_file(doc_id, file_path, doc_type)
            extracted = gst_to_dict(result)
        else:
            return

        from database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Document).where(Document.id == doc_id))
            doc = res.scalar_one_or_none()
            if doc:
                doc.extracted_json = extracted
                doc.status = "extracted"
                doc.processed_at = datetime.now(timezone.utc)
                if "avg_confidence" in extracted:
                    doc.ocr_confidence_avg = extracted["avg_confidence"]
                if "page_count" in extracted:
                    doc.page_count = extracted["page_count"]
                db.add(doc)
                await db.commit()
    except Exception as e:
        logger.error("Extraction failed for doc_id=%s: %s", doc_id, e)