"""
auth/auth_middleware.py
─────────────────────────────────────────────────────────────────────────────
Authentication and authorization middleware for Intelli-Credit API.

For MVP/demo purposes, this implements a simple API key-based authentication.
In production, this would be replaced with OAuth2/JWT tokens.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Header, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session, Case

logger = logging.getLogger(__name__)


# ── Authentication ────────────────────────────────────────────────────────────

async def verify_api_key(
    x_api_key: Optional[str] = Header(None, description="API key for authentication")
) -> str:
    """
    Verify API key authentication.
    
    For MVP/demo: Accept any non-empty API key and extract user from it.
    In production: Validate against database or external auth service.
    
    Args:
        x_api_key: API key from X-API-Key header
    
    Returns:
        User identifier (email or username)
    
    Raises:
        HTTPException: 401 if authentication fails
    """
    if not x_api_key:
        logger.warning("Authentication failed: Missing X-API-Key header")
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # For MVP: Extract user from API key format "user@example.com:token"
    # In production: Validate token against database/auth service
    if ":" in x_api_key:
        user_id = x_api_key.split(":")[0]
    else:
        user_id = x_api_key
    
    if not user_id:
        logger.warning("Authentication failed: Invalid API key format")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key format",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    logger.debug(f"Authentication successful: user={user_id}")
    return user_id


# ── Authorization ─────────────────────────────────────────────────────────────

async def verify_case_access(
    case_id: str,
    user_id: str,
    session: AsyncSession,
) -> None:
    """
    Verify that the authenticated user has access to the specified case.
    
    For MVP/demo: All authenticated users have access to all cases.
    In production: Check user permissions, team assignments, etc.
    
    Args:
        case_id: Case identifier
        user_id: Authenticated user identifier
        session: Database session
    
    Raises:
        HTTPException: 403 if user doesn't have access
        HTTPException: 404 if case doesn't exist
    """
    # First verify case exists
    result = await session.execute(
        select(Case).where(Case.id == case_id)
    )
    case = result.scalar_one_or_none()
    
    if not case:
        logger.warning(f"Case not found: case_id={case_id} user={user_id}")
        raise HTTPException(
            status_code=404,
            detail="Case not found"
        )
    
    # For MVP: All authenticated users have access
    # In production: Check permissions here
    # Example production logic:
    # if not await _user_has_case_access(session, user_id, case_id):
    #     logger.warning(f"Access denied: user={user_id} case={case_id}")
    #     raise HTTPException(
    #         status_code=403,
    #         detail="You do not have permission to access this case"
    #     )
    
    logger.debug(f"Authorization successful: user={user_id} case={case_id}")


# ── Combined Dependency ───────────────────────────────────────────────────────

class AuthorizedUser:
    """Dependency that combines authentication and authorization."""
    
    def __init__(self, case_id: str):
        self.case_id = case_id
    
    async def __call__(
        self,
        user_id: str = Depends(verify_api_key),
        session: AsyncSession = Depends(get_session),
    ) -> str:
        """
        Verify authentication and authorization for a case.
        
        Returns:
            User identifier if authorized
        
        Raises:
            HTTPException: 401 if not authenticated, 403 if not authorized
        """
        await verify_case_access(self.case_id, user_id, session)
        return user_id
