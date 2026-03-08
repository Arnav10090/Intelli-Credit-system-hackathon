"""
tests/test_insights_security.py
─────────────────────────────────────────────────────────────────────────────
Security tests for Primary Insight Integration feature.
Tests authentication, authorization, and SQL injection prevention.
─────────────────────────────────────────────────────────────────────────────
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from database import Case, CaseInsight


# ── Authentication Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_post_insights_requires_authentication(client: AsyncClient, demo_case_id: str):
    """Test that POST /insights returns 401 without API key."""
    response = await client.post(
        f"/api/v1/cases/{demo_case_id}/insights",
        json={
            "notes": "Test observation",
            "created_by": "analyst@test.com"
        }
    )
    
    assert response.status_code == 401
    assert "authentication required" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_insights_requires_authentication(client: AsyncClient, demo_case_id: str):
    """Test that GET /insights returns 401 without API key."""
    response = await client.get(f"/api/v1/cases/{demo_case_id}/insights")
    
    assert response.status_code == 401
    assert "authentication required" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_post_insights_with_valid_api_key(client: AsyncClient, demo_case_id: str):
    """Test that POST /insights succeeds with valid API key."""
    response = await client.post(
        f"/api/v1/cases/{demo_case_id}/insights",
        json={
            "notes": "Factory operating at 40% capacity",
            "created_by": "analyst@test.com"
        },
        headers={"X-API-Key": "analyst@test.com:demo-token"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == demo_case_id
    assert data["notes"] == "Factory operating at 40% capacity"


@pytest.mark.asyncio
async def test_get_insights_with_valid_api_key(client: AsyncClient, demo_case_id: str):
    """Test that GET /insights succeeds with valid API key."""
    # First save some insights
    await client.post(
        f"/api/v1/cases/{demo_case_id}/insights",
        json={
            "notes": "Test observation",
            "created_by": "analyst@test.com"
        },
        headers={"X-API-Key": "analyst@test.com:demo-token"}
    )
    
    # Then retrieve them
    response = await client.get(
        f"/api/v1/cases/{demo_case_id}/insights",
        headers={"X-API-Key": "analyst@test.com:demo-token"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["notes"] == "Test observation"


# ── Authorization Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_post_insights_invalid_case_returns_404(client: AsyncClient):
    """Test that POST /insights returns 404 for non-existent case."""
    fake_case_id = "00000000-0000-0000-0000-000000000000"
    
    response = await client.post(
        f"/api/v1/cases/{fake_case_id}/insights",
        json={
            "notes": "Test observation",
            "created_by": "analyst@test.com"
        },
        headers={"X-API-Key": "analyst@test.com:demo-token"}
    )
    
    assert response.status_code == 404
    assert "case not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_insights_invalid_case_returns_404(client: AsyncClient):
    """Test that GET /insights returns 404 for non-existent case."""
    fake_case_id = "00000000-0000-0000-0000-000000000000"
    
    response = await client.get(
        f"/api/v1/cases/{fake_case_id}/insights",
        headers={"X-API-Key": "analyst@test.com:demo-token"}
    )
    
    assert response.status_code == 404
    assert "case not found" in response.json()["detail"].lower()


# ── SQL Injection Prevention Tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sql_injection_in_notes_field(
    client: AsyncClient, demo_case_id: str, db_session
):
    """
    Test that SQL injection payloads in notes field are safely stored.
    SQLAlchemy ORM uses parameterized queries, preventing SQL injection.
    """
    # Common SQL injection payloads
    sql_payloads = [
        "'; DROP TABLE cases; --",
        "' OR '1'='1",
        "'; DELETE FROM case_insights WHERE '1'='1'; --",
        "1' UNION SELECT * FROM cases--",
        "admin'--",
        "' OR 1=1--",
    ]
    
    for payload in sql_payloads:
        response = await client.post(
            f"/api/v1/cases/{demo_case_id}/insights",
            json={
                "notes": payload,
                "created_by": "analyst@test.com"
            },
            headers={"X-API-Key": "analyst@test.com:demo-token"}
        )
        
        # Should succeed (payload stored as text, not executed)
        assert response.status_code == 200
        data = response.json()
        assert data["notes"] == payload
        
        # Verify database integrity - case should still exist
        result = await db_session.execute(
            select(Case).where(Case.id == demo_case_id)
        )
        case = result.scalar_one_or_none()
        assert case is not None, f"Case deleted by SQL injection: {payload}"
        
        # Verify insight was stored correctly
        result = await db_session.execute(
            select(CaseInsight).where(CaseInsight.case_id == demo_case_id)
        )
        insight = result.scalar_one_or_none()
        assert insight is not None
        assert insight.notes == payload


@pytest.mark.asyncio
async def test_sql_injection_in_case_id_parameter(client: AsyncClient):
    """
    Test that SQL injection payloads in case_id URL parameter are rejected.
    FastAPI path validation + SQLAlchemy ORM prevent SQL injection.
    """
    sql_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE cases; --",
        "1' UNION SELECT * FROM cases--",
    ]
    
    for payload in sql_payloads:
        response = await client.post(
            f"/api/v1/cases/{payload}/insights",
            json={
                "notes": "Test observation",
                "created_by": "analyst@test.com"
            },
            headers={"X-API-Key": "analyst@test.com:demo-token"}
        )
        
        # Should return 404 (case not found) or 422 (validation error)
        # Never 200 (successful injection)
        assert response.status_code in [404, 422]


@pytest.mark.asyncio
async def test_sql_injection_in_created_by_field(
    client: AsyncClient, demo_case_id: str, db_session
):
    """
    Test that SQL injection payloads in created_by field are safely stored.
    """
    payload = "'; DROP TABLE audit_logs; --"
    
    response = await client.post(
        f"/api/v1/cases/{demo_case_id}/insights",
        json={
            "notes": "Test observation",
            "created_by": payload
        },
        headers={"X-API-Key": "analyst@test.com:demo-token"}
    )
    
    # Should succeed (payload stored as text)
    assert response.status_code == 200
    data = response.json()
    assert data["created_by"] == payload
    
    # Verify insight was stored correctly
    result = await db_session.execute(
        select(CaseInsight).where(CaseInsight.case_id == demo_case_id)
    )
    insight = result.scalar_one_or_none()
    assert insight is not None
    assert insight.created_by == payload


# ── XSS Prevention Tests (bonus) ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_xss_payload_stored_safely(client: AsyncClient, demo_case_id: str):
    """
    Test that XSS payloads are stored safely in the database.
    Frontend is responsible for escaping when displaying.
    """
    xss_payloads = [
        "<script>alert('xss')</script>",
        "<img src=x onerror=alert('xss')>",
        "javascript:alert('xss')",
        "<iframe src='javascript:alert(\"xss\")'></iframe>",
    ]
    
    for payload in xss_payloads:
        response = await client.post(
            f"/api/v1/cases/{demo_case_id}/insights",
            json={
                "notes": payload,
                "created_by": "analyst@test.com"
            },
            headers={"X-API-Key": "analyst@test.com:demo-token"}
        )
        
        # Should succeed (payload stored as text)
        assert response.status_code == 200
        data = response.json()
        # Payload should be returned as-is (no server-side escaping)
        # Frontend must handle escaping when displaying
        assert data["notes"] == payload


# ── Input Validation Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notes_length_validation(client: AsyncClient, demo_case_id: str):
    """Test that notes exceeding 5000 characters are rejected."""
    long_notes = "x" * 5001
    
    response = await client.post(
        f"/api/v1/cases/{demo_case_id}/insights",
        json={
            "notes": long_notes,
            "created_by": "analyst@test.com"
        },
        headers={"X-API-Key": "analyst@test.com:demo-token"}
    )
    
    # Pydantic validation returns 422, custom validation returns 400
    assert response.status_code in [400, 422]
    detail = response.json()["detail"]
    if isinstance(detail, str):
        assert "5000" in detail or "characters" in detail.lower()
    else:
        # Pydantic returns list of errors
        assert any("5000" in str(err) or "max_length" in str(err) for err in detail)


@pytest.mark.asyncio
async def test_empty_notes_accepted(client: AsyncClient, demo_case_id: str):
    """Test that empty notes are accepted (clears existing insights)."""
    response = await client.post(
        f"/api/v1/cases/{demo_case_id}/insights",
        json={
            "notes": "",
            "created_by": "analyst@test.com"
        },
        headers={"X-API-Key": "analyst@test.com:demo-token"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["notes"] == ""
    assert data["adjustments"] == []
    assert data["total_delta"] == 0
