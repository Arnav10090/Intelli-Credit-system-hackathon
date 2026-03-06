"""
api/research_routes.py
─────────────────────────────────────────────────────────────────────────────
FastAPI routes for the Research Agent.
Step 5: Full pipeline — crawl → score → persist → litigation summary.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings, DEMO_DIR
from database import get_session, Case, ResearchResult
from audit.audit_logger import log_event
from research.web_crawler import run_research_agent, result_to_dict as crawler_to_dict
from research.litigation_detector import detect_litigation, summary_to_dict

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ResearchTriggerResponse(BaseModel):
    case_id:   str
    status:    str
    message:   str


class ResearchSummaryResponse(BaseModel):
    case_id:             str
    total_articles:      int
    total_risk_delta:    int
    overall_label:       str
    tier1_count:         int
    tier2_count:         int
    tier3_count:         int
    knockout:            bool
    primary_trigger:     str
    used_cache:          bool
    message:             str


# ── Trigger Research ──────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/research",
             response_model=ResearchTriggerResponse,
             summary="Trigger Research Agent — async background crawl")
async def trigger_research(
    case_id:          str,
    background_tasks: BackgroundTasks,
    session:          AsyncSession = Depends(get_session),
):
    """
    Triggers the async Research Agent pipeline:
      1. Google News RSS — company name search
      2. MCA21 portal    — company master + filings
      3. BSE India       — corporate announcements
      4. eCourts India   — case search (best effort)
      5. Demo fallback   — research_cache.json if live crawl fails

    Returns immediately. Poll GET /research for results.
    Each article is scored by news_scorer.py and persisted to research_results.
    """
    # Verify case
    result = await session.execute(select(Case).where(Case.id == case_id))
    case   = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, f"Case {case_id} not found.")

    background_tasks.add_task(
        _run_research_background,
        case_id=case_id,
        company_name=case.company_name,
        cin=case.company_cin or "",
        pan=case.company_pan or "",
    )

    await log_event(
        session, "RESEARCH_TRIGGERED",
        f"Research agent queued for {case.company_name}",
        case_id=case_id,
    )

    return ResearchTriggerResponse(
        case_id=case_id,
        status="queued",
        message=(
            f"Research agent triggered for {case.company_name}. "
            "Live crawl running in background. "
            "Poll GET /cases/{case_id}/research for results."
        ),
    )


# ── Get Research Results ──────────────────────────────────────────────────────

@router.get("/cases/{case_id}/research",
            summary="Get all research results for a case")
async def get_research(
    case_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Return all research findings ordered by risk severity (worst first)."""
    result = await session.execute(
        select(ResearchResult)
        .where(ResearchResult.case_id == case_id)
        .order_by(ResearchResult.risk_tier.asc().nullslast(),
                  ResearchResult.risk_score_delta.asc())
    )
    items = result.scalars().all()
    return [
        {
            "id":               r.id,
            "result_type":      r.result_type,
            "title":            r.title,
            "url":              r.url,
            "source_name":      r.source_name,
            "published_date":   r.published_date.isoformat() if r.published_date else None,
            "risk_tier":        r.risk_tier,
            "risk_score_delta": r.risk_score_delta,
            "matched_keywords": r.matched_keywords,
            "is_cached":        r.is_cached,
            "retrieved_at":     r.retrieved_at.isoformat(),
        }
        for r in items
    ]


# ── Research Summary ──────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/research/summary",
            response_model=ResearchSummaryResponse,
            summary="Get aggregated research risk summary")
async def get_research_summary(
    case_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Returns aggregate risk metrics + litigation summary.
    Used by the frontend dashboard and scoring engine.
    """
    result = await session.execute(
        select(ResearchResult).where(ResearchResult.case_id == case_id)
    )
    items = result.scalars().all()

    if not items:
        raise HTTPException(
            404,
            "No research results found. Run POST /research first."
        )

    # Build research_cache-style dict from DB records
    research_cache = _db_records_to_cache(items)

    # Run litigation detector
    lit_summary   = detect_litigation(research_cache)
    lit_dict      = summary_to_dict(lit_summary)

    # Aggregate stats
    total_delta   = sum(r.risk_score_delta or 0 for r in items)
    tier1_count   = sum(1 for r in items if r.risk_tier == 1)
    tier2_count   = sum(1 for r in items if r.risk_tier == 2)
    tier3_count   = sum(1 for r in items if r.risk_tier == 3)
    used_cache    = any(r.is_cached for r in items)

    if total_delta <= -60:  label = "CRITICAL"
    elif total_delta <= -30: label = "HIGH"
    elif total_delta <= -10: label = "MEDIUM"
    elif total_delta < 0:   label = "LOW"
    else:                   label = "CLEAN"

    return ResearchSummaryResponse(
        case_id=case_id,
        total_articles=len(items),
        total_risk_delta=total_delta,
        overall_label=label,
        tier1_count=tier1_count,
        tier2_count=tier2_count,
        tier3_count=tier3_count,
        knockout=lit_summary.knockout,
        primary_trigger=lit_summary.primary_trigger,
        used_cache=used_cache,
        message=(
            f"Research summary: {len(items)} findings | "
            f"Total risk delta: {total_delta} pts | "
            f"Label: {label} | "
            f"{'⚠ KNOCKOUT FLAG' if lit_summary.knockout else 'No knockout'}"
        ),
    )


# ── Litigation Detail ─────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/research/litigation",
            summary="Get detailed litigation analysis")
async def get_litigation_detail(
    case_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Detailed litigation analysis with resolution path."""
    result = await session.execute(
        select(ResearchResult).where(ResearchResult.case_id == case_id)
    )
    items = result.scalars().all()

    if not items:
        # Try loading from demo cache directly
        demo_rc_path = DEMO_DIR / "research_cache.json"
        if demo_rc_path.exists():
            with open(demo_rc_path) as f:
                research_cache = json.load(f)
        else:
            raise HTTPException(404, "No research data found.")
    else:
        research_cache = _db_records_to_cache(items)

    lit_summary = detect_litigation(research_cache)
    return summary_to_dict(lit_summary)


# ── Load Research from Demo Cache ─────────────────────────────────────────────

@router.post("/cases/{case_id}/research/load-cache",
             summary="Load research from pre-cached demo data (instant)")
async def load_research_from_cache(
    case_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Loads the pre-built Acme Textiles research cache directly into the database.
    Bypasses live crawling — instant result.
    Use this for demo when network is unavailable.
    """
    result = await session.execute(select(Case).where(Case.id == case_id))
    case   = result.scalar_one_or_none()
    if not case:
        raise HTTPException(404, f"Case {case_id} not found.")

    demo_rc_path = DEMO_DIR / "research_cache.json"
    if not demo_rc_path.exists():
        raise HTTPException(500, "Demo research cache file not found.")

    # Run crawler in demo-cache mode (no live crawl)
    agent_result = await run_research_agent(
        company_name=case.company_name,
        cin=case.company_cin or "",
        use_cache=False,
        demo_fallback_path=demo_rc_path,
    )

    # Persist all articles to research_results table
    saved_count = 0
    for article in agent_result.articles:
        pub_date = None
        if article.published_date:
            try:
                from datetime import date
                pub_date = datetime.fromisoformat(article.published_date)
            except ValueError:
                pass

        rec = ResearchResult(
            case_id=case_id,
            result_type=article.result_type,
            title=article.title[:500] if article.title else "",
            url=article.url[:1000] if article.url else "",
            source_name=article.source_name,
            published_date=pub_date,
            raw_text=article.raw_text[:2000] if article.raw_text else "",
            risk_tier=article.risk_tier,
            risk_score_delta=article.risk_score_delta,
            matched_keywords=article.matched_keywords,
            is_cached=True,
        )
        session.add(rec)
        saved_count += 1

    await log_event(
        session, "RESEARCH_CACHE_LOADED",
        f"Demo research cache loaded: {saved_count} findings | "
        f"delta={agent_result.aggregate.get('total_risk_delta', 0)}",
        case_id=case_id,
        actor="research_agent",
        output_data=agent_result.aggregate,
    )

    return {
        "case_id":        case_id,
        "articles_saved": saved_count,
        "aggregate":      agent_result.aggregate,
        "used_cache":     True,
        "message": (
            f"{saved_count} research findings loaded from demo cache. "
            f"Total risk delta: {agent_result.aggregate.get('total_risk_delta', 0)} pts. "
            f"Label: {agent_result.aggregate.get('overall_research_risk_label', 'N/A')}."
        ),
    }


# ── Background Task ───────────────────────────────────────────────────────────

async def _run_research_background(
    case_id:      str,
    company_name: str,
    cin:          str,
    pan:          str,
) -> None:
    """
    Background task: run full research agent and persist results.
    Falls back to demo cache if live crawl fails.
    """
    from database import AsyncSessionLocal

    demo_rc_path = DEMO_DIR / "research_cache.json"

    try:
        agent_result = await run_research_agent(
            company_name=company_name,
            cin=cin,
            pan=pan,
            use_cache=True,
            demo_fallback_path=demo_rc_path if demo_rc_path.exists() else None,
        )

        async with AsyncSessionLocal() as session:
            for article in agent_result.articles:
                pub_date = None
                if article.published_date:
                    try:
                        pub_date = datetime.fromisoformat(article.published_date)
                    except ValueError:
                        pass

                rec = ResearchResult(
                    case_id=case_id,
                    result_type=article.result_type,
                    title=article.title[:500] if article.title else "",
                    url=article.url[:1000] if article.url else "",
                    source_name=article.source_name,
                    published_date=pub_date,
                    raw_text=article.raw_text[:2000] if article.raw_text else "",
                    risk_tier=article.risk_tier,
                    risk_score_delta=article.risk_score_delta,
                    matched_keywords=article.matched_keywords,
                    is_cached=agent_result.used_cache,
                )
                session.add(rec)

            await log_event(
                session, "RESEARCH_COMPLETE",
                f"Research complete: {len(agent_result.articles)} findings | "
                f"delta={agent_result.aggregate.get('total_risk_delta', 0)} | "
                f"cache={agent_result.used_cache}",
                case_id=case_id,
                actor="research_agent",
                output_data=agent_result.aggregate,
            )
            logger.info(
                "Research persisted: case=%s articles=%d",
                case_id, len(agent_result.articles)
            )

    except Exception as e:
        logger.error("Research background task failed: case=%s error=%s", case_id, e)


# ── Helper ────────────────────────────────────────────────────────────────────

def _db_records_to_cache(items) -> dict:
    """Convert DB ResearchResult records to the research_cache dict format."""
    news_articles     = []
    ecourts_findings  = []
    mca_filings       = []

    for r in items:
        entry = {
            "title":            r.title,
            "url":              r.url,
            "source":           r.source_name,
            "risk_tier":        r.risk_tier,
            "risk_score_delta": r.risk_score_delta,
            "date":             r.published_date.isoformat()[:10] if r.published_date else None,
        }
        if r.result_type == "news_article":
            news_articles.append(entry)
        elif r.result_type == "ecourts_case":
            ecourts_findings.append({
                **entry,
                "case_type":  r.title,
                "case_number":"",
                "court":      r.source_name,
                "status":     "Pending",
                "amount_cr":  0.0,
            })
        elif r.result_type == "mca_filing":
            mca_filings.append({
                **entry,
                "form":       r.title[:10],
                "risk_flag":  r.risk_tier is not None,
                "notes":      r.raw_text[:100] if r.raw_text else "",
            })

    return {
        "news_articles":    news_articles,
        "ecourts_findings": ecourts_findings,
        "mca_filings":      mca_filings,
    }