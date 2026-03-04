"""
audit/audit_logger.py
─────────────────────────────────────────────────────────────────────────────
Centralised audit logging utility.
Wraps database.log_action with a simpler interface for use throughout the app.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


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
    """
    from database import log_action
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