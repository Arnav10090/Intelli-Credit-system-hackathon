"""
api/score_routes.py
─────────────────────────────────────────────────────────────────────────────
FastAPI routes for the Five Cs scoring engine.
Step 4: Full pipeline — feature engineering → scorecard → loan sizing → ML.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import (
    get_session, Case, Document, ScoringResult, AuditLog
)
from audit.audit_logger import log_event
from scoring.feature_engineer import engineer_features, feature_set_to_dict
from scoring.five_cs_scorer import compute_score, scorecard_to_dict
from scoring.loan_calculator import compute_loan_sizing, sizing_to_dict
from scoring.ml_validator import validate_with_ml, ml_result_to_dict

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ScoreResponse(BaseModel):
    case_id:              str
    company_name:         str
    normalised_score:     int
    total_raw_score:      int
    risk_grade:           str
    risk_label:           str
    decision:             str
    recommended_cr:       float
    recommended_rate_pct: float
    primary_rejection_trigger: str
    counter_factual:      str
    ml_agrees:            bool
    ml_default_prob:      float
    message:              str


class OverrideRequest(BaseModel):
    override_decision:  str = Field(..., description="APPROVE | PARTIAL | REJECT")
    override_amount_cr: float | None = None
    justification:      str = Field(..., min_length=50,
                                    description="Minimum 50 characters required")
    analyst_id:         str


class OverrideResponse(BaseModel):
    case_id:   str
    original_decision:  str
    new_decision:       str
    override_by:        str
    message:            str


# ── Score Endpoint ────────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/score", response_model=ScoreResponse,
             summary="Run Five Cs scoring engine — full Step 4 pipeline")
async def score_case(
    case_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Runs the complete Step 4 pipeline in sequence:
      1. Loads all extracted data from database (financial, GST, research, WC, RP)
      2. Runs feature_engineer.py → 16 normalised features
      3. Runs five_cs_scorer.py → 200-pt scorecard + decision
      4. Runs loan_calculator.py → recommended amount + rate
      5. Runs ml_validator.py → XGBoost second opinion
      6. Persists full result to scoring_results table
      7. Logs everything to audit_logs

    Prerequisites: /load-demo + /analyze must be run first.
    """
    # ── Load case ──────────────────────────────────────────────────────────────
    case_result = await session.execute(select(Case).where(Case.id == case_id))
    case = case_result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, f"Case {case_id} not found.")

    # ── Load all data payloads ─────────────────────────────────────────────────
    financial_data = await _load_doc_json(session, case_id, "balance_sheet")
    if not financial_data:
        raise HTTPException(
            400,
            "No financial data found. Run /load-demo then /analyze first."
        )

    # Extract sub-dicts stored by the /analyze endpoint
    wc_analysis = financial_data.get("working_capital_analysis", {})
    rp_analysis = financial_data.get("related_party_analysis", {})

    # GST recon from gst document
    gst_data    = await _load_doc_json(session, case_id, "gstr_3b") or {}

    # Research cache from file (not stored as extracted_json)
    research_cache = await _load_research_cache(session, case_id)

    # ── Step 4a: Feature Engineering ──────────────────────────────────────────
    features = engineer_features(
        financial_data=financial_data,
        wc_analysis=wc_analysis,
        rp_analysis=rp_analysis,
        gst_recon=gst_data,
        research_cache=research_cache,
        loan_request=financial_data.get("loan_request"),
    )
    features_dict = feature_set_to_dict(features)

    await log_event(
        session, "FEATURES_ENGINEERED",
        f"16 features computed: dscr={features.dscr:.3f} "
        f"de={features.de_ratio:.2f} lit={features.litigation_risk:.3f}",
        case_id=case_id,
        output_data=features_dict,
    )

    # ── Step 4b: Five Cs Scorecard ─────────────────────────────────────────────
    scorecard     = compute_score(features)
    scorecard_dict = scorecard_to_dict(scorecard)

    await log_event(
        session, "SCORECARD_COMPUTED",
        f"Score: {scorecard.total_raw_score}/200 "
        f"({scorecard.normalised_score}/100) "
        f"Grade: {scorecard.risk_grade} | Decision: {scorecard.decision}",
        case_id=case_id,
        output_data=scorecard_dict,
    )

    # ── Step 4c: Loan Sizing ───────────────────────────────────────────────────
    sizing     = compute_loan_sizing(scorecard, features, financial_data)
    sizing_dict = sizing_to_dict(sizing)

    await log_event(
        session, "LOAN_SIZED",
        f"Recommended: ₹{sizing.recommended_cr:.2f}Cr "
        f"@ {sizing.recommended_rate_pct:.2f}% "
        f"(binding: {sizing.binding_constraint})",
        case_id=case_id,
        output_data=sizing_dict,
    )

    # ── Step 4d: ML Validation ─────────────────────────────────────────────────
    ml_result     = validate_with_ml(features, scorecard)
    ml_dict       = ml_result_to_dict(ml_result)

    await log_event(
        session, "ML_VALIDATED",
        f"ML: {ml_result.predicted_label} "
        f"({ml_result.default_probability*100:.0f}% default prob) "
        f"agrees={ml_result.agrees_with_scorecard} "
        f"divergence={ml_result.divergence_flag}",
        case_id=case_id,
        output_data=ml_dict,
    )

    # ── Persist to scoring_results ─────────────────────────────────────────────
    await _persist_scoring_result(
        session, case_id,
        features_dict, scorecard_dict, sizing_dict, ml_dict,
        scorecard, sizing, ml_result,
    )

    # ── Update case status ─────────────────────────────────────────────────────
    case.status = "scored"
    session.add(case)

    logger.info(
        "Scoring complete: case=%s score=%d/200 grade=%s decision=%s "
        "recommended=₹%.2fCr @ %.2f%%",
        case_id, scorecard.total_raw_score, scorecard.risk_grade,
        scorecard.decision, sizing.recommended_cr, sizing.recommended_rate_pct
    )

    return ScoreResponse(
        case_id=case_id,
        company_name=case.company_name,
        normalised_score=scorecard.normalised_score,
        total_raw_score=scorecard.total_raw_score,
        risk_grade=scorecard.risk_grade,
        risk_label=scorecard.risk_label,
        decision=scorecard.decision,
        recommended_cr=sizing.recommended_cr,
        recommended_rate_pct=sizing.recommended_rate_pct,
        primary_rejection_trigger=scorecard.primary_rejection_trigger,
        counter_factual=scorecard.counter_factual,
        ml_agrees=ml_result.agrees_with_scorecard,
        ml_default_prob=ml_result.default_probability,
        message=(
            f"Scoring complete for {case.company_name}. "
            f"Score: {scorecard.normalised_score}/100 (Grade {scorecard.risk_grade}). "
            f"Decision: {scorecard.decision}. "
            f"Recommended: ₹{sizing.recommended_cr:.2f}Cr "
            f"@ {sizing.recommended_rate_pct:.2f}% p.a."
        ),
    )


# ── Get Score ─────────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/score",
            summary="Retrieve the latest scoring result for a case")
async def get_score(case_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(ScoringResult)
        .where(ScoringResult.case_id == case_id)
        .order_by(ScoringResult.scored_at.desc())
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "No scoring result found. Run /score first.")

    return {
        "case_id":              case_id,
        "normalised_score":     rec.normalized_score,
        "total_raw_score":      rec.total_raw_score,
        "risk_grade":           rec.risk_grade,
        "decision":             rec.decision,
        "recommended_cr":       rec.recommended_amount_cr,
        "recommended_rate_pct": rec.recommended_rate_pct,
        "is_overridden":        rec.is_overridden,
        "override_by":          rec.override_by,
        "override_reason":      rec.override_reason,
        "scored_at":            rec.scored_at.isoformat(),
        "pillar_scores":        rec.feature_values.get("pillar_scores") if rec.feature_values else {},
        "contributions":        rec.score_contributions,
        "loan_sizing":          rec.feature_values.get("loan_sizing") if rec.feature_values else {},
        "ml_validation":        rec.feature_values.get("ml_validation") if rec.feature_values else {},
        "counter_factual":      rec.counter_factual,
        "primary_rejection_trigger": rec.primary_rejection_trigger,
        "knockout_flags":       rec.feature_values.get("knockout_flags", []) if rec.feature_values else [],
    }


# ── Override Endpoint ─────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/override", response_model=OverrideResponse,
             summary="Analyst override — requires 50-char justification")
async def override_decision(
    case_id: str,
    request: OverrideRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Allows a senior analyst to override the scorecard decision.
    Fully audited — original score and override reason stored immutably.
    """
    # Load latest score
    result = await session.execute(
        select(ScoringResult)
        .where(ScoringResult.case_id == case_id)
        .order_by(ScoringResult.scored_at.desc())
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "No scoring result to override.")

    original_decision = rec.decision
    original_score    = rec.normalised_score

    # Check delta threshold
    decision_values = {"APPROVE": 2, "PARTIAL": 1, "REJECT": 0}
    orig_val = decision_values.get(original_decision, 0)
    new_val  = decision_values.get(request.override_decision, 0)
    delta    = abs(orig_val - new_val)

    if delta > 1 and len(request.justification) < settings.OVERRIDE_MAX_DELTA_WITHOUT_COUNTERSIGN:
        raise HTTPException(
            400,
            f"Override from {original_decision} to {request.override_decision} "
            f"requires justification of at least "
            f"{settings.OVERRIDE_MAX_DELTA_WITHOUT_COUNTERSIGN} characters."
        )

    # Apply override
    rec.is_overridden   = True
    rec.override_by     = request.analyst_id
    rec.override_reason = request.justification
    rec.decision        = request.override_decision
    if request.override_amount_cr:
        rec.recommended_amount_cr = request.override_amount_cr
    rec.overridden_at = datetime.now(timezone.utc)
    session.add(rec)

    # Update case status
    case_res = await session.execute(select(Case).where(Case.id == case_id))
    case = case_res.scalar_one_or_none()
    if case:
        case.status = "overridden"
        session.add(case)

    await log_event(
        session, "DECISION_OVERRIDDEN",
        f"Override by {request.analyst_id}: "
        f"{original_decision} → {request.override_decision} | "
        f"Original score: {original_score}/100 | "
        f"Justification: {request.justification[:100]}",
        case_id=case_id,
        actor=request.analyst_id,
    )

    return OverrideResponse(
        case_id=case_id,
        original_decision=original_decision,
        new_decision=request.override_decision,
        override_by=request.analyst_id,
        message=(
            f"Override applied. Decision changed from {original_decision} "
            f"to {request.override_decision} by {request.analyst_id}. "
            "Full audit trail preserved."
        ),
    )


# ── Audit Trail ───────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/audit",
            summary="Get full audit trail for a case")
async def get_audit_trail(case_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.case_id == case_id)
        .order_by(AuditLog.timestamp.asc())
    )
    logs = result.scalars().all()
    return [
        {
            "id":          l.id,
            "action_type": l.action_type,
            "description": l.description,
            "actor":       l.actor,
            "timestamp":   l.timestamp.isoformat(),
        }
        for l in logs
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_doc_json(
    session: AsyncSession, case_id: str, doc_type: str
) -> dict | None:
    """Load extracted_json from a document of given type."""
    result = await session.execute(
        select(Document).where(
            Document.case_id == case_id,
            Document.doc_type == doc_type,
            Document.status == "extracted",
        ).order_by(Document.processed_at.desc())
    )
    doc = result.scalars().first()
    return doc.extracted_json if doc else None


async def _load_research_cache(session: AsyncSession, case_id: str) -> dict:
    """Load research cache JSON from file."""
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


async def _persist_scoring_result(
    session, case_id,
    features_dict, scorecard_dict, sizing_dict, ml_dict,
    scorecard, sizing, ml_result,
):
    """Persist the full scoring result to the scoring_results table."""
    from database import ScoringResult

    # Check for existing record (update in place)
    existing = await session.execute(
        select(ScoringResult).where(ScoringResult.case_id == case_id)
    )
    rec = existing.scalar_one_or_none()

    if not rec:
        rec = ScoringResult(case_id=case_id)

    rec.feature_values     = {
        **features_dict,
        "pillar_scores":   scorecard_dict["pillar_scores"],
        "knockout_flags":  scorecard_dict["knockout_flags"],
        "loan_sizing":     sizing_dict,
        "ml_validation":   ml_dict,
    }
    rec.score_contributions      = scorecard_dict["contributions"]

    # Five Cs sub-scores (NOT NULL columns — this was the missing piece)
    rec.character_score          = scorecard.character_score
    rec.capacity_score           = scorecard.capacity_score
    rec.capital_score            = scorecard.capital_score
    rec.collateral_score         = scorecard.collateral_score
    rec.conditions_score         = scorecard.conditions_score

    rec.total_raw_score          = scorecard.total_raw_score
    rec.normalized_score         = scorecard.normalised_score  # DB column is American spelling
    rec.risk_grade               = scorecard.risk_grade
    rec.decision                 = scorecard.decision
    rec.recommended_amount_cr    = sizing.recommended_cr
    rec.recommended_rate_pct     = sizing.recommended_rate_pct
    rec.loan_limit_dscr_cr       = sizing.limit_dscr_cr
    rec.loan_limit_collateral_cr = sizing.limit_collateral_cr
    rec.loan_limit_drawing_power_cr = sizing.limit_drawing_power_cr
    rec.primary_rejection_trigger = scorecard.primary_rejection_trigger
    rec.counter_factual          = scorecard.counter_factual
    rec.xgb_prediction           = ml_result.predicted_label   # String column: "high_risk"/"low_risk"
    rec.xgb_probability          = ml_result.default_probability  # Float column
    rec.ml_agrees_with_scorecard = ml_result.agrees_with_scorecard
    rec.scored_at                = datetime.now(timezone.utc)

    session.add(rec)