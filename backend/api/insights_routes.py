"""
api/insights_routes.py
─────────────────────────────────────────────────────────────────────────────
FastAPI routes for Primary Insight Integration feature.
Enables Credit Officers to capture qualitative field observations and
automatically translate them into quantitative score adjustments.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import hashlib
import logging
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session, Case, CaseInsight
from audit.audit_logger import log_event
from scoring.insight_scorer import parse_and_score
from auth.auth_middleware import verify_api_key, verify_case_access

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class SaveInsightsRequest(BaseModel):
    notes: str = Field(..., max_length=5000, description="Qualitative field observations")
    created_by: str = Field(..., description="User who created the insights")


class InsightAdjustmentResponse(BaseModel):
    pillar: str
    delta: int
    reason: str
    keywords_matched: list[str]


class SaveInsightsResponse(BaseModel):
    case_id: str
    notes: str
    adjustments: list[InsightAdjustmentResponse]
    total_delta: int
    created_at: str
    created_by: str
    message: str


class GetInsightsResponse(BaseModel):
    case_id: str
    notes: str | None
    adjustments: list[InsightAdjustmentResponse]
    total_delta: int
    created_at: str | None = None
    created_by: str | None = None


# ── POST Endpoint ─────────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/insights", response_model=SaveInsightsResponse,
             summary="Save insight notes and compute score adjustments")
async def save_insights(
    case_id: str,
    request: SaveInsightsRequest,
    session: AsyncSession = Depends(get_session),
    x_api_key: str | None = Header(None),
):
    """
    Save or update qualitative insight notes for a case and return computed
    score adjustments based on keyword matching rules.
    
    Prerequisites: Case must exist in database.
    Authentication: Optional X-API-Key header (for demo purposes).
    
    Workflow:
      1. Verify case exists
      2. Validate notes length (max 5000 characters)
      3. Parse notes using insight_scorer.parse_and_score()
      4. Upsert to case_insights table (INSERT OR REPLACE pattern)
      5. Log to audit trail
      6. Return notes, adjustments, total_delta, and metadata
    
    Error Responses:
      - 400: Notes exceed 5000 characters
      - 404: Case not found
      - 500: Database error
    """
    try:
        # ── Verify case exists ─────────────────────────────────────────────────
        result_case = await session.execute(
            select(Case).where(Case.id == case_id)
        )
        case = result_case.scalar_one_or_none()
        
        if not case:
            logger.warning(f"Case not found: case_id={case_id}")
            raise HTTPException(
                status_code=404,
                detail="Case not found"
            )
        
        # ── Validate notes length ──────────────────────────────────────────────
        if len(request.notes) > 5000:
            logger.warning(
                "Notes length validation failed: case=%s length=%d user=%s",
                case_id, len(request.notes), user_id
            )
            raise HTTPException(
                status_code=400,
                detail="Notes cannot exceed 5000 characters"
            )
        
        # Note: Case existence is already verified by verify_case_access
        
        # ── Parse notes and compute adjustments ────────────────────────────────
        scoring_result = parse_and_score(request.notes)
        
        # Convert adjustments to dict format for JSON storage
        adjustments_json = [
            {
                "pillar": adj.pillar,
                "delta": adj.delta,
                "reason": adj.reason,
                "keywords_matched": adj.keywords_matched
            }
            for adj in scoring_result.adjustments
        ]
        
        # ── Upsert to case_insights table ──────────────────────────────────────
        # Check if insight already exists for this case
        existing_result = await session.execute(
            select(CaseInsight).where(CaseInsight.case_id == case_id)
        )
        existing_insight = existing_result.scalar_one_or_none()
        
        if existing_insight:
            # Update existing record
            existing_insight.notes = request.notes
            existing_insight.adjustments_json = adjustments_json
            existing_insight.total_delta = scoring_result.total_delta
            existing_insight.created_by = request.created_by
            existing_insight.updated_at = datetime.now(timezone.utc)
            insight = existing_insight
        else:
            # Create new record
            insight = CaseInsight(
                case_id=case_id,
                notes=request.notes,
                adjustments_json=adjustments_json,
                total_delta=scoring_result.total_delta,
                created_by=request.created_by,
            )
            session.add(insight)
        
        await session.flush()
        
        # ── Audit logging ──────────────────────────────────────────────────────
        notes_hash = hashlib.sha256(request.notes.encode()).hexdigest()
        
        await log_event(
            session=session,
            action_type="INSIGHTS_SAVED",
            description=(
                f"Insight notes saved: {len(request.notes)} chars, "
                f"{len(scoring_result.adjustments)} adjustments"
            ),
            case_id=case_id,
            actor=request.created_by,
            input_data={"notes_hash": notes_hash},
            output_data={
                "total_delta": scoring_result.total_delta,
                "adjustment_count": len(scoring_result.adjustments)
            },
        )
        
        logger.info(
            "Insights saved: case=%s adjustments=%d total_delta=%d actor=%s",
            case_id, len(scoring_result.adjustments),
            scoring_result.total_delta, request.created_by
        )
        
        # ── Build response ─────────────────────────────────────────────────────
        adjustment_responses = [
            InsightAdjustmentResponse(
                pillar=adj.pillar,
                delta=adj.delta,
                reason=adj.reason,
                keywords_matched=adj.keywords_matched
            )
            for adj in scoring_result.adjustments
        ]
        
        return SaveInsightsResponse(
            case_id=case_id,
            notes=request.notes,
            adjustments=adjustment_responses,
            total_delta=scoring_result.total_delta,
            created_at=insight.created_at.isoformat(),
            created_by=request.created_by,
            message=(
                f"Insights saved successfully. "
                f"Net score impact: {scoring_result.total_delta:+d} pts"
            )
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    
    except Exception as e:
        # ── Error logging ──────────────────────────────────────────────────────
        error_trace = traceback.format_exc()
        logger.error(
            "Database error saving insights: case=%s error=%s\n%s",
            case_id, str(e), error_trace
        )
        
        # Log error to audit trail
        try:
            await log_event(
                session=session,
                action_type="INSIGHTS_ERROR",
                description=f"Error saving insights: {str(e)}",
                case_id=case_id,
                actor=request.created_by,
                extra_metadata={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }
            )
        except Exception:
            # If audit logging fails, just log to application log
            pass
        
        raise HTTPException(
            status_code=500,
            detail="Database error. Please contact support."
        )


# ── GET Endpoint ──────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/insights", response_model=GetInsightsResponse,
            summary="Retrieve saved insight notes and adjustments")
async def get_insights(
    case_id: str,
    session: AsyncSession = Depends(get_session),
    x_api_key: str | None = Header(None),
):
    """
    Retrieve saved insight notes and computed adjustments for a case.
    
    Authentication: Optional X-API-Key header (for demo purposes).
    
    Returns:
      - If insights exist: notes, adjustments, total_delta, and metadata
      - If no insights exist: empty result with notes=null, adjustments=[], total_delta=0
    
    Always returns HTTP 200 (never 404 for missing insights).
    
    Error Responses:
      - 404: Case not found
      - 500: Database error
    """
    # ── Verify case exists ─────────────────────────────────────────────────
    result_case = await session.execute(
        select(Case).where(Case.id == case_id)
    )
    case = result_case.scalar_one_or_none()
    
    if not case:
        logger.warning(f"Case not found: case_id={case_id}")
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )
    
    try:
        # ── Query case_insights table ──────────────────────────────────────────
        result = await session.execute(
            select(CaseInsight).where(CaseInsight.case_id == case_id)
        )
        insight = result.scalar_one_or_none()
        
        # ── Return empty result if no insights exist ───────────────────────────
        if not insight:
            logger.debug("No insights found for case: case_id=%s", case_id)
            return GetInsightsResponse(
                case_id=case_id,
                notes=None,
                adjustments=[],
                total_delta=0,
                created_at=None,
                created_by=None,
            )
        
        # ── Build response with saved insights ─────────────────────────────────
        adjustment_responses = [
            InsightAdjustmentResponse(
                pillar=adj["pillar"],
                delta=adj["delta"],
                reason=adj["reason"],
                keywords_matched=adj.get("keywords_matched", [])
            )
            for adj in insight.adjustments_json
        ]
        
        logger.debug(
            "Insights retrieved: case=%s adjustments=%d total_delta=%d",
            case_id, len(adjustment_responses), insight.total_delta
        )
        
        return GetInsightsResponse(
            case_id=case_id,
            notes=insight.notes,
            adjustments=adjustment_responses,
            total_delta=insight.total_delta,
            created_at=insight.created_at.isoformat(),
            created_by=insight.created_by,
        )
    
    except Exception as e:
        # ── Error logging ──────────────────────────────────────────────────────
        error_trace = traceback.format_exc()
        logger.error(
            "Error retrieving insights: case=%s error=%s\n%s",
            case_id, str(e), error_trace
        )
        
        raise HTTPException(
            status_code=500,
            detail="Database error. Please contact support."
        )
