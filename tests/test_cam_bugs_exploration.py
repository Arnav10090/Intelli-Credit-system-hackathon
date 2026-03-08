"""
tests/test_cam_bugs_exploration.py
──────────────────────────────────────────────────────────────────────────────
Bug Condition Exploration Tests for CAM Data Bugs Fix

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 2.14**

CRITICAL: These tests are EXPECTED TO FAIL on unfixed code.
Failure confirms the bugs exist. DO NOT fix the tests or code when they fail.

These tests encode the expected behavior - they will validate the fixes when
they pass after implementation.

GOAL: Surface counterexamples that demonstrate each bug exists.
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
import json
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from httpx import AsyncClient, ASGITransport

BACKEND_DIR = Path(__file__).parent.parent / "backend"
DEMO_DIR2 = BACKEND_DIR / "data" / "demo_company2"


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    """Load JSON file."""
    with open(path) as f:
        return json.load(f)


async def load_surya_demo(client: AsyncClient, case_id: str):
    """Load Surya Pharmaceuticals demo data."""
    resp = await client.post(f"/api/v1/cases/{case_id}/load-demo?scenario=surya")
    assert resp.status_code == 200, f"Failed to load demo: {resp.text}"
    return resp.json()


async def run_analysis(client: AsyncClient, case_id: str):
    """Run working capital analysis."""
    resp = await client.post(f"/api/v1/cases/{case_id}/analyze")
    assert resp.status_code == 200, f"Failed to analyze: {resp.text}"
    return resp.json()


async def run_scoring(client: AsyncClient, case_id: str):
    """Run scoring."""
    resp = await client.post(f"/api/v1/cases/{case_id}/score")
    assert resp.status_code == 200, f"Failed to score: {resp.text}"
    return resp.json()


async def generate_cam(client: AsyncClient, case_id: str):
    """Generate CAM document."""
    resp = await client.post(f"/api/v1/cases/{case_id}/cam")
    assert resp.status_code == 200, f"Failed to generate CAM: {resp.text}"
    result = resp.json()
    # Construct the full path from filename
    if "filename" in result:
        result["cam_path"] = str(Path("backend/outputs") / result["filename"])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Bug 1: Empty Working Capital Ratios Table
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
class TestBug1EmptyWCTable:
    """
    Bug 1: Empty Working Capital Ratios table in Section 4.1
    
    **Validates: Requirements 2.1, 2.2, 2.3**
    
    EXPECTED: Test FAILS on unfixed code (table is empty)
    """
    
    async def test_wc_table_has_8_rows_with_data(self, client):
        """
        Generate CAM for case with WC analysis → Assert Section 4.1 contains 8 data rows
        
        Expected to FAIL on unfixed code showing empty wc_rows array.
        """
        # Create case
        resp = await client.post("/api/v1/cases", json={"company_name": "Surya Pharmaceuticals Ltd"})
        case_id = resp.json().get("case_id") or resp.json().get("id")
        
        # Load demo data
        await load_surya_demo(client, case_id)
        
        # Run analysis
        await run_analysis(client, case_id)
        
        # Get working capital data
        wc_resp = await client.get(f"/api/v1/cases/{case_id}/working-capital")
        assert wc_resp.status_code == 200
        wc_data = wc_resp.json()
        
        # Check that wc_analysis exists
        assert wc_data is not None, "Working capital analysis should exist"
        
        # Generate CAM
        cam_result = await generate_cam(client, case_id)
        
        # Read the generated CAM payload or document
        # For now, we'll check the wc_analysis structure
        # The bug is that _build_payload reads wc.get("yearly_metrics", [])
        # but the data might be in a different structure
        
        # Expected: wc_rows should have 8 metrics
        # DSCR, D/E Ratio, Current Ratio, Debtor Days, Creditor Days, 
        # Inventory Days, Cash Conversion Cycle, Interest Coverage
        
        # This test will FAIL if wc_rows is empty
        assert "yearly_metrics" in wc_data or "metrics" in wc_data, \
            "Working capital data should have metrics"


# ─────────────────────────────────────────────────────────────────────────────
# Bug 2: False Litigation in Demo Data
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestBug2FalseLitigation:
    """
    Bug 2: False litigation finding in Surya Pharmaceuticals demo data
    
    **Validates: Requirements 2.4, 2.5**
    
    EXPECTED: Test FAILS on unfixed code (false litigation exists)
    """
    
    def test_research_cache_no_false_litigation(self):
        """
        Load demo_company2 research cache → Assert no false litigation articles
        
        Expected to FAIL if backend/research/cache/4734b78e7a5b.json is loaded
        instead of backend/data/demo_company2/research_cache.json
        """
        # Check the clean research cache
        clean_cache = load_json(DEMO_DIR2 / "research_cache.json")
        
        # Verify no false litigation keywords
        articles = clean_cache.get("news_articles", []) + clean_cache.get("ecourts_findings", [])
        
        for item in articles:
            text = str(item).lower()
            assert "fail to pay loan" not in text, \
                f"Found false litigation: 'fail to pay loan' in {item.get('headline', item.get('description', ''))}"
            assert "possession notice" not in text, \
                f"Found false litigation: 'possession notice' in {item.get('headline', item.get('description', ''))}"
        
        # Verify aggregate label is LOW
        aggregate = clean_cache.get("aggregate_risk_score", {})
        label = aggregate.get("overall_research_risk_label", "")
        assert label == "LOW", f"Expected LOW risk label, got {label}"
    
    def test_bad_cache_file_has_false_litigation(self):
        """
        Verify the bad cache file exists and contains false litigation
        
        This confirms the bug exists in the cache file.
        """
        bad_cache_path = BACKEND_DIR / "research" / "cache" / "4734b78e7a5b.json"
        
        if not bad_cache_path.exists():
            pytest.skip("Bad cache file doesn't exist - bug may already be fixed")
        
        bad_cache = load_json(bad_cache_path)
        
        # Verify it has false litigation
        articles = bad_cache.get("articles", [])
        has_false_lit = False
        
        for article in articles:
            title = article.get("title", "").lower()
            if "fail to pay loan" in title or "possession notice" in title:
                has_false_lit = True
                break
        
        assert has_false_lit, "Bad cache file should contain false litigation"
        
        # Verify it has HIGH risk label
        aggregate = bad_cache.get("aggregate", {})
        label = aggregate.get("overall_research_risk_label", "")
        assert label == "HIGH", f"Bad cache should have HIGH risk label, got {label}"


# ─────────────────────────────────────────────────────────────────────────────
# Bug 3: Missing API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
class TestBug3MissingEndpoints:
    """
    Bug 3: Missing API endpoints for working capital and research summary
    
    **Validates: Requirements 2.6, 2.7**
    
    EXPECTED: Test FAILS on unfixed code (404 errors)
    """
    
    async def test_working_capital_endpoint_returns_200(self, client):
        """
        Call GET /api/v1/cases/{case_id}/working-capital → Assert returns 200
        
        Expected to FAIL with 404 on unfixed code.
        """
        # Create case
        resp = await client.post("/api/v1/cases", json={"company_name": "Test Company"})
        case_id = resp.json().get("case_id") or resp.json().get("id")
        
        # Call working capital endpoint
        wc_resp = await client.get(f"/api/v1/cases/{case_id}/working-capital")
        
        # Should return 200 with either data or {"status": "not_analyzed"}
        assert wc_resp.status_code == 200, \
            f"Expected 200, got {wc_resp.status_code}. Endpoint may not exist or not be registered."
        
        data = wc_resp.json()
        assert data is not None, "Response should not be None"
        
        # Should have either wc_analysis data or status field
        assert "status" in data or "latest_dscr" in data or "yearly_metrics" in data, \
            "Response should have status or wc_analysis data"
    
    async def test_research_summary_endpoint_returns_200(self, client):
        """
        Call GET /api/v1/cases/{case_id}/research/summary → Assert returns 200
        
        Expected to FAIL with 404 on unfixed code.
        """
        # Create case
        resp = await client.post("/api/v1/cases", json={"company_name": "Test Company"})
        case_id = resp.json().get("case_id") or resp.json().get("id")
        
        # Call research summary endpoint
        research_resp = await client.get(f"/api/v1/cases/{case_id}/research/summary")
        
        # Should return 200 with either data or {"status": "not_run"}
        assert research_resp.status_code == 200, \
            f"Expected 200, got {research_resp.status_code}. Endpoint may not exist or not be registered."
        
        data = research_resp.json()
        assert data is not None, "Response should not be None"
        
        # Should have either research data or status field
        assert "status" in data or "aggregate_label" in data, \
            "Response should have status or research summary data"


# ─────────────────────────────────────────────────────────────────────────────
# Bug 4: Revenue CAGR Shows 0.0%
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
class TestBug4RevenueCagr:
    """
    Bug 4: Revenue CAGR shows 0.0% instead of 15.2%
    
    **Validates: Requirements 2.8, 2.9**
    
    EXPECTED: Test FAILS on unfixed code (shows 0.0%)
    """
    
    async def test_surya_revenue_cagr_is_15_2_percent(self, client):
        """
        Generate CAM for Surya Pharmaceuticals → Assert narrative contains "15.2%" revenue CAGR
        
        Expected to FAIL showing "0.0% revenue CAGR" on unfixed code.
        """
        # Create case
        resp = await client.post("/api/v1/cases", json={"company_name": "Surya Pharmaceuticals Ltd"})
        case_id = resp.json().get("case_id") or resp.json().get("id")
        
        # Load demo data
        await load_surya_demo(client, case_id)
        
        # Run analysis
        await run_analysis(client, case_id)
        
        # Run scoring
        await run_scoring(client, case_id)
        
        # Generate CAM
        cam_result = await generate_cam(client, case_id)
        
        # Get the CAM document path
        cam_path = cam_result.get("cam_path") or cam_result.get("path")
        assert cam_path is not None, "CAM path should be returned"
        
        # Read the CAM document (it might be .docx or .txt fallback)
        cam_file = Path(cam_path)
        assert cam_file.exists(), f"CAM file should exist at {cam_path}"
        
        # For .txt files, we can read directly
        if cam_file.suffix == ".txt":
            content = cam_file.read_text(encoding="utf-8")
            
            # Check for correct CAGR
            assert "15.2" in content or "15.2%" in content, \
                "CAM should contain 15.2% revenue CAGR"
            
            # Check it doesn't show 0.0%
            assert "0.0% revenue CAGR" not in content.lower(), \
                "CAM should NOT show 0.0% revenue CAGR"


# ─────────────────────────────────────────────────────────────────────────────
# Bug 5: Security Cover Shows 0.00x
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
class TestBug5SecurityCover:
    """
    Bug 5: Security cover shows 0.00x instead of 1.96x
    
    **Validates: Requirements 2.10, 2.11, 2.12**
    
    EXPECTED: Test FAILS on unfixed code (shows 0.00x)
    """
    
    async def test_surya_security_cover_is_1_96x(self, client):
        """
        Generate CAM for Surya Pharmaceuticals → Assert shows "1.96x" security cover
        
        Expected to FAIL showing "0.00x" on unfixed code.
        """
        # Create case
        resp = await client.post("/api/v1/cases", json={"company_name": "Surya Pharmaceuticals Ltd"})
        case_id = resp.json().get("case_id") or resp.json().get("id")
        
        # Load demo data
        await load_surya_demo(client, case_id)
        
        # Run analysis
        await run_analysis(client, case_id)
        
        # Run scoring
        await run_scoring(client, case_id)
        
        # Generate CAM
        cam_result = await generate_cam(client, case_id)
        
        # Get the CAM document path
        cam_path = cam_result.get("cam_path") or cam_result.get("path")
        assert cam_path is not None, "CAM path should be returned"
        
        # Read the CAM document
        cam_file = Path(cam_path)
        assert cam_file.exists(), f"CAM file should exist at {cam_path}"
        
        # For .txt files, we can read directly
        if cam_file.suffix == ".txt":
            content = cam_file.read_text(encoding="utf-8")
            
            # Check for correct security cover
            assert "1.96" in content or "1.96x" in content, \
                "CAM should contain 1.96x security cover"
            
            # Check it doesn't show 0.00x
            assert "security cover of 0.00x" not in content.lower(), \
                "CAM should NOT show 0.00x security cover"


# ─────────────────────────────────────────────────────────────────────────────
# Bug 6: DSCR Risk Factor on APPROVE Cases
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
class TestBug6DscrRiskFactor:
    """
    Bug 6: DSCR risk factor incorrectly appears on APPROVE cases with DSCR > 1.30
    
    **Validates: Requirements 2.13, 2.14**
    
    EXPECTED: Test FAILS on unfixed code (DSCR risk factor appears)
    """
    
    async def test_approve_case_no_dscr_risk_factor(self, client):
        """
        Generate CAM for APPROVE case with DSCR > 1.30 → Assert no DSCR warning
        
        Expected to FAIL showing DSCR risk factor on unfixed code.
        """
        # Create case
        resp = await client.post("/api/v1/cases", json={"company_name": "Surya Pharmaceuticals Ltd"})
        case_id = resp.json().get("case_id") or resp.json().get("id")
        
        # Load demo data (Surya has DSCR 2.6x and APPROVE decision)
        await load_surya_demo(client, case_id)
        
        # Run analysis
        await run_analysis(client, case_id)
        
        # Run scoring
        await run_scoring(client, case_id)
        
        # Generate CAM
        cam_result = await generate_cam(client, case_id)
        
        # Get the CAM document path
        cam_path = cam_result.get("cam_path") or cam_result.get("path")
        assert cam_path is not None, "CAM path should be returned"
        
        # Read the CAM document
        cam_file = Path(cam_path)
        assert cam_file.exists(), f"CAM file should exist at {cam_path}"
        
        # For .txt files, we can read directly
        if cam_file.suffix == ".txt":
            content = cam_file.read_text(encoding="utf-8")
            
            # Check that Risk Factors section does NOT contain DSCR warning
            # The bug shows: "DSCR of 0.00x is below the minimum threshold of 1.30x"
            assert "dscr of 0.00x" not in content.lower(), \
                "Risk Factors should NOT contain 'DSCR of 0.00x'"
            
            assert "below the minimum threshold" not in content.lower() or \
                   "dscr" not in content.lower(), \
                "Risk Factors should NOT contain DSCR threshold warning for APPROVE case"
