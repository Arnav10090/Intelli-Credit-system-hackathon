"""
audit/audit_logger.py
─────────────────────────────────────────────────────────────────────────────
Centralised audit logging utility.
Wraps database.log_action with a simpler interface for use throughout the app.

BUG FIX: Updated score logging to show correct denominator (230 instead of 200)
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ACTUAL_MAX for Five Cs scoring (60+60+45+30+35 = 230)
SCORE_ACTUAL_MAX = 230


async def log_event(
    session,
    action_type: str,
    description: str,
    case_id: str | None = None,
    actor: str = "system",
    input_data: Any = None,
    output_data: Any = None,
    extra_metadata: dict | None = None,
) -> None:
    """
    Convenience wrapper around database.log_action.
    Also emits a Python log entry at INFO level for observability.
    
    BUG FIX: For SCORECARD_COMPUTED events, the description now correctly
    shows the actual max score of 230 instead of the display label 200.
    """
    from database import log_action
    
    # Fix score logging to show correct denominator
    if action_type == "SCORECARD_COMPUTED" and description:
        # Replace /200 with /230 in score descriptions
        description = description.replace("/200", f"/{SCORE_ACTUAL_MAX}")
    
    await log_action(
        session=session,
        action_type=action_type,
        description=description,
        case_id=case_id,
        actor=actor,
        input_data=input_data,
        output_data=output_data,
        extra_metadata=extra_metadata,
    )
    logger.info("[AUDIT] %s | case=%s | %s", action_type, case_id, description)