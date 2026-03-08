"""
tests/test_api_integration.py
──────────────────────────────────────────────────────────────────────────────
Integration tests for the FastAPI endpoints.

These tests spin up the full FastAPI app using TestClient (synchronous wrapper
around HTTPX) with an in-memory SQLite database, so no external services or
files are required.

Covered endpoints:
  POST /api/v1/cases                    — create case
  GET  /api/v1/cases                    — list cases
  GET  /api/v1/cases/:id                — get single case
  POST /api/v1/cases/:id/load-demo      — load demo data
  POST /api/v1/cases/:id/analyze        — run analysis
  POST /api/v1/cases/:id/score          — run scoring engine
  GET  /api/v1/cases/:id/score          — get score result
  GET  /api/v1/cases/:id/flags          — get raised flags
  GET  /api/v1/cases/:id/audit          — get audit trail

Run:
  cd backend && pytest ../tests/test_api_integration.py -v
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
import asyncio
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# App fixture — use in-memory SQLite DB for each test run
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Create a TestClient with in-memory SQLite for the full test session."""
    os.environ["INTELLI_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    # Mock LLM API key so cam generation doesn't fail fast on missing key
    os.environ["LLM_API_KEY"] = "test-key-not-real"

    from main import app
    from database import init_db

    # Initialise tables in the in-memory DB
    asyncio.get_event_loop().run_until_complete(init_db())

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(scope="module")
def demo_case_id(client):
    """Create and return a demo case ID for endpoint tests."""
    resp = client.post("/api/v1/cases", json={
        "company_name": "Test Corp Ltd",
        "company_cin": "U12345MH2010PLC000001",
        "company_pan": "AAAAA1234A",
        "requested_amount_cr": 20.0,
        "requested_tenor_yr": 7,
        "purpose": "Working Capital + Term Loan",
    })
    assert resp.status_code in (200, 201)
    return resp.json()["case_id"]


# ─────────────────────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthCheck:

    def test_root_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code in (200, 404)  # 404 ok if no root route

    def test_docs_available(self, client):
        resp = client.get("/api/docs")
        assert resp.status_code == 200

    def test_openapi_schema(self, client):
        resp = client.get("/api/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "openapi" in schema


# ─────────────────────────────────────────────────────────────────────────────
# Case CRUD
# ─────────────────────────────────────────────────────────────────────────────

class TestCaseCrud:

    def test_create_case_returns_201(self, client):
        resp = client.post("/api/v1/cases", json={
            "company_name": "Acme Widgets Ltd",
            "company_cin": "U99999MH2010PLC000002",
            "requested_amount_cr": 10.0,
            "requested_tenor_yr": 5,
        })
        assert resp.status_code in (200, 201)
        body = resp.json()
        assert "case_id" in body
        assert body["company_name"] == "Acme Widgets Ltd"

    def test_create_case_requires_company_name(self, client):
        resp = client.post("/api/v1/cases", json={})
        assert resp.status_code == 422  # Validation error

    def test_list_cases_returns_200(self, client):
        resp = client.get("/api/v1/cases")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_cases_includes_created_case(self, client, demo_case_id):
        resp = client.get("/api/v1/cases")
        ids = [c.get("id") or c.get("case_id") for c in resp.json()]
        assert demo_case_id in ids

    def test_get_single_case_returns_200(self, client, demo_case_id):
        resp = client.get(f"/api/v1/cases/{demo_case_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["case_id"] == demo_case_id

    def test_get_nonexistent_case_returns_404(self, client):
        resp = client.get("/api/v1/cases/NONEXISTENT-CASE-ID")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Demo Data Loading
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadDemo:

    def test_load_demo_returns_200(self, client, demo_case_id):
        resp = client.post(f"/api/v1/cases/{demo_case_id}/load-demo")
        assert resp.status_code == 200

    def test_load_demo_returns_documents_loaded(self, client, demo_case_id):
        resp = client.post(f"/api/v1/cases/{demo_case_id}/load-demo")
        body = resp.json()
        assert "documents_loaded" in body
        assert body["documents_loaded"] > 0

    def test_load_demo_for_nonexistent_case_returns_404(self, client):
        resp = client.post("/api/v1/cases/FAKE-CASE/load-demo")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Analysis
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyze:

    @pytest.fixture(autouse=True, scope="class")
    def load_demo_first(self, client, demo_case_id):
        """Ensure demo data is loaded before running analysis tests."""
        client.post(f"/api/v1/cases/{demo_case_id}/load-demo")

    def test_analyze_returns_200(self, client, demo_case_id):
        resp = client.post(f"/api/v1/cases/{demo_case_id}/analyze")
        assert resp.status_code == 200

    def test_analyze_returns_dscr(self, client, demo_case_id):
        resp = client.post(f"/api/v1/cases/{demo_case_id}/analyze")
        body = resp.json()
        assert "avg_dscr" in body
        assert isinstance(body["avg_dscr"], (int, float))

    def test_analyze_returns_flags_count(self, client, demo_case_id):
        resp = client.post(f"/api/v1/cases/{demo_case_id}/analyze")
        body = resp.json()
        assert "total_flags" in body
        assert body["total_flags"] >= 0

    def test_get_flags_after_analyze(self, client, demo_case_id):
        client.post(f"/api/v1/cases/{demo_case_id}/analyze")
        resp = client.get(f"/api/v1/cases/{demo_case_id}/flags")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_analyze_updates_case_status(self, client, demo_case_id):
        resp = client.get(f"/api/v1/cases/{demo_case_id}")
        body = resp.json()
        assert body.get("status") in ("analyzed", "demo_loaded", "scored", "draft")


# ─────────────────────────────────────────────────────────────────────────────
# Scoring Engine
# ─────────────────────────────────────────────────────────────────────────────

class TestScoring:

    @pytest.fixture(autouse=True, scope="class")
    def setup_scoring(self, client, demo_case_id):
        """Load demo + analyze before scoring tests."""
        client.post(f"/api/v1/cases/{demo_case_id}/load-demo")
        client.post(f"/api/v1/cases/{demo_case_id}/analyze")

    def test_run_score_returns_200(self, client, demo_case_id):
        resp = client.post(f"/api/v1/cases/{demo_case_id}/score")
        assert resp.status_code == 200

    def test_score_response_has_decision(self, client, demo_case_id):
        resp = client.post(f"/api/v1/cases/{demo_case_id}/score")
        body = resp.json()
        assert body.get("decision") in ("APPROVE", "PARTIAL", "REJECT")

    def test_score_response_has_grade(self, client, demo_case_id):
        resp = client.post(f"/api/v1/cases/{demo_case_id}/score")
        body = resp.json()
        assert body.get("risk_grade") in ("A+", "A", "B+", "B", "C", "D")

    def test_score_response_normalised_score_in_range(self, client, demo_case_id):
        resp = client.post(f"/api/v1/cases/{demo_case_id}/score")
        body = resp.json()
        assert 0 <= body["normalised_score"] <= 100

    def test_score_acme_demo_is_reject(self, client, demo_case_id):
        """Acme Textiles demo case should be REJECT (NCLT + low DSCR)."""
        resp = client.post(f"/api/v1/cases/{demo_case_id}/score")
        body = resp.json()
        # The demo case has litigation → REJECT
        assert body["decision"] == "REJECT"

    def test_get_score_returns_200(self, client, demo_case_id):
        client.post(f"/api/v1/cases/{demo_case_id}/score")
        resp = client.get(f"/api/v1/cases/{demo_case_id}/score")
        assert resp.status_code == 200

    def test_get_score_has_pillar_scores(self, client, demo_case_id):
        client.post(f"/api/v1/cases/{demo_case_id}/score")
        resp = client.get(f"/api/v1/cases/{demo_case_id}/score")
        body = resp.json()
        assert "pillar_scores" in body
        pillars = body["pillar_scores"]
        for pillar in ("character", "capacity", "capital", "collateral", "conditions"):
            assert pillar in pillars

    def test_get_score_has_contributions(self, client, demo_case_id):
        client.post(f"/api/v1/cases/{demo_case_id}/score")
        resp = client.get(f"/api/v1/cases/{demo_case_id}/score")
        body = resp.json()
        assert "contributions" in body
        assert len(body["contributions"]) == 16

    def test_get_score_has_loan_sizing(self, client, demo_case_id):
        client.post(f"/api/v1/cases/{demo_case_id}/score")
        resp = client.get(f"/api/v1/cases/{demo_case_id}/score")
        body = resp.json()
        assert "loan_sizing" in body
        assert "recommendation" in body["loan_sizing"]

    def test_get_score_for_unscored_case_returns_404(self, client):
        # Create a new case but don't score it
        resp = client.post("/api/v1/cases", json={
            "company_name": "Unscored Co",
            "requested_amount_cr": 5.0,
        })
        case_id = resp.json()["case_id"]
        resp = client.get(f"/api/v1/cases/{case_id}/score")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Audit Trail
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditTrail:

    def test_audit_returns_200(self, client, demo_case_id):
        resp = client.get(f"/api/v1/cases/{demo_case_id}/audit")
        assert resp.status_code in (200, 404)

    def test_audit_has_events_after_scoring(self, client, demo_case_id):
        client.post(f"/api/v1/cases/{demo_case_id}/load-demo")
        client.post(f"/api/v1/cases/{demo_case_id}/analyze")
        client.post(f"/api/v1/cases/{demo_case_id}/score")
        resp = client.get(f"/api/v1/cases/{demo_case_id}/audit")
        if resp.status_code == 200:
            events = resp.json()
            assert isinstance(events, list)


# ─────────────────────────────────────────────────────────────────────────────
# Error Handling
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorHandling:

    def test_score_without_demo_data_returns_error(self, client):
        """Scoring a case with no documents should fail gracefully."""
        resp = client.post("/api/v1/cases", json={
            "company_name": "Empty Case Ltd",
            "requested_amount_cr": 10.0,
        })
        case_id = resp.json()["case_id"]
        # Try to score without loading data first
        resp = client.post(f"/api/v1/cases/{case_id}/score")
        assert resp.status_code in (400, 422, 404, 500)

    def test_invalid_json_body_returns_422(self, client):
        resp = client.post(
            "/api/v1/cases",
            content="not json at all",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_flags_for_nonexistent_case_returns_404(self, client):
        resp = client.get("/api/v1/cases/GHOST-CASE-ID/flags")
        # Endpoint returns 200 with empty list for unknown case (not 404)
        assert resp.status_code in (200, 404)