"""
demo_reset.py
─────────────────────────────────────────────────────────────────────────────
Logic to reset demo cases to their initial "draft" state on server startup.
Ensures the dashboard always starts with a clean pipeline for Acme and Surya.
─────────────────────────────────────────────────────────────────────────────
"""

import logging
from sqlalchemy import select, delete
from database import (
    AsyncSessionLocal, Case, Document, ReconFlag, 
    ScoringResult, ResearchResult, CaseInsight, AuditLog
)
from config import settings

logger = logging.getLogger(__name__)

DEMO_CASES = [
    {
        "name": settings.DEMO_COMPANY_NAME, # "Acme Textiles Ltd"
        "cin": settings.DEMO_COMPANY_CIN,
        "pan": settings.DEMO_COMPANY_PAN,
        "amount": 20.0,
        "tenor": 7,
        "purpose": "Modernisation of weaving machinery"
    },
    {
        "name": "Surya Pharmaceuticals Ltd",
        "cin": "U24230TG2008PLC058421",
        "pan": "AADCS9876C",
        "amount": 30.0,
        "tenor": 6,
        "purpose": "Greenfield API manufacturing unit expansion"
    }
]

async def reset_demo_cases():
    """
    Deletes all existing demo cases and recreates them in Step 1 (draft) state.
    Called from main.py lifespan hook.
    """
    async with AsyncSessionLocal() as session:
        try:
            for demo in DEMO_CASES:
                # 1. Find all demo cases with this name (to handle duplicates)
                result = await session.execute(
                    select(Case).where(Case.company_name == demo["name"])
                )
                cases = result.scalars().all()
                
                if cases:
                    logger.info(f"Cleaning up {len(cases)} instances of demo case: {demo['name']}")
                    for case in cases:
                        case_id = case.id
                        # Manually delete all related records
                        await session.execute(delete(Document).where(Document.case_id == case_id))
                        await session.execute(delete(ReconFlag).where(ReconFlag.case_id == case_id))
                        await session.execute(delete(ScoringResult).where(ScoringResult.case_id == case_id))
                        await session.execute(delete(ResearchResult).where(ResearchResult.case_id == case_id))
                        await session.execute(delete(CaseInsight).where(CaseInsight.case_id == case_id))
                        await session.execute(delete(AuditLog).where(AuditLog.case_id == case_id))
                        # Delete the case itself
                        await session.delete(case)
                
                # 2. Create a fresh single instance
                logger.info(f"Recreating fresh demo case: {demo['name']}")
                new_case = Case(
                    company_name=demo["name"],
                    company_cin=demo["cin"],
                    company_pan=demo["pan"],
                    requested_amount_cr=demo["amount"],
                    requested_tenor_yr=demo["tenor"],
                    purpose=demo["purpose"],
                    status="draft",
                    created_by="system_reset"
                )
                session.add(new_case)
            
            await session.commit()
            logger.info("Demo cases reset complete.")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Failed to reset demo cases: {e}")
            raise
