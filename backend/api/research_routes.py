"""
api/research_routes.py — Research Agent trigger and results endpoints.
Full implementation: Step 6 (web_crawler.py + news_scorer.py).
"""

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session

router = APIRouter()


@router.post("/cases/{case_id}/research", summary="Trigger Research Agent")
async def trigger_research(
    case_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Triggers the async Research Agent for a case.
    Crawls MCA, BSE, news sources, e-Courts for the company.
    Returns immediately; use GET /research to poll results.
    Full implementation: Step 6.
    """
    # Step 6 will add: background_tasks.add_task(run_research_agent, case_id)
    return {"message": "Research agent triggered", "case_id": case_id, "status": "queued"}


@router.get("/cases/{case_id}/research", summary="Get research results for a case")
async def get_research(case_id: str, session: AsyncSession = Depends(get_session)):
    """Return all research findings for a case."""
    from sqlalchemy import select
    from database import ResearchResult
    result = await session.execute(
        select(ResearchResult)
        .where(ResearchResult.case_id == case_id)
        .order_by(ResearchResult.risk_score_delta.asc())
    )
    items = result.scalars().all()
    return [
        {
            "id": r.id,
            "result_type": r.result_type,
            "title": r.title,
            "url": r.url,
            "source_name": r.source_name,
            "published_date": r.published_date.isoformat() if r.published_date else None,
            "risk_tier": r.risk_tier,
            "risk_score_delta": r.risk_score_delta,
            "matched_keywords": r.matched_keywords,
            "is_cached": r.is_cached,
        }
        for r in items
    ]