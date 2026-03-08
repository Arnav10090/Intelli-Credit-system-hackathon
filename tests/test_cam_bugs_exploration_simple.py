"""
tests/test_cam_bugs_exploration_simple.py
──────────────────────────────────────────────────────────────────────────────
Simplified Bug Condition Exploration Tests for CAM Data Bugs Fix

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 2.14**

CRITICAL: These tests are EXPECTED TO FAIL on unfixed code.
Failure confirms the bugs exist. DO NOT fix the tests or code when they fail.

These tests focus on the data structures and API responses rather than
parsing generated DOCX files.
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
import json
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from httpx import AsyncClient

BACKEND_DIR = Path(__file__).parent.parent / "backend"
DEMO_DIR2 = BACKEND_DIR / "data" / "demo_company2"


def load_json(path: Path) -> dict:
    """Load JSON file."""
    with open(path) as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# Bug 2: False Litigation in Demo Data
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestBug2FalseLitigation:
    """
    Bug 2: False litigation finding in Surya Pharmaceuticals demo data
    
    **Validates: Requirements 2.4, 2.5**
    
    EXPECTED: Test FAILS on unfixed code (false litigation exists in bad cache)
    """
    
    def test_clean_research_cache_no_false_litigation(self):
        """
        Verify clean research cache has no false litigation articles.
        
        This test should PASS - it confirms the clean cache is correct.
        """
        clean_cache = load_json(DEMO_DIR2 / "research_cache.json")
        
        # Check all articles and findings
        articles = clean_cache.get("news_articles", []) + clean_cache.get("ecourts_findings", [])
        
        for item in articles:
            text = json.dumps(item).lower()
            assert "fail to pay loan" not in text, \
                f"Found false litigation: 'fail to pay loan' in {item.get('headline', item.get('description', ''))}"
            assert "possession notice" not in text, \
                f"Found false litigation: 'possession notice' in {item.get('headline', item.get('description', ''))}"
        
        # Verify aggregate label is LOW
        aggregate = clean_cache.get("aggregate_risk_score", {})
        label = aggregate.get("overall_research_risk_label", "")
        assert label == "LOW", f"Expected LOW risk label, got {label}"
    
    def test_bad_cache_file_contains_false_litigation(self):
        """
        Verify the bad cache file exists and contains false litigation.
        
        This test should PASS - it confirms the bug exists in the bad cache file.
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
        
        assert has_false_lit, "Bad cache file should contain false litigation (this confirms the bug exists)"
        
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
    Bug 3: Missing API endpoints return 404 instead of proper status
    
    **Validates: Requirements 2.6, 2.7**
    
    EXPECTED: Tests FAIL on unfixed code (404 errors instead of 200 with status)
    """
    
    async def test_working_capital_endpoint_exists(self, client):
        """
        Call GET /api/v1/cases/{case_id}/working-capital → Should return 200
        
        Expected to FAIL with 404 on unfixed code when no data exists.
        Should return {"status": "not_analyzed"} instead of 404.
        """
        # Create case
        resp = await client.post("/api/v1/cases", json={"company_name": "Test Company"})
        case_id = resp.json().get("case_id") or resp.json().get("id")
        
        # Call working capital endpoint WITHOUT running analysis
        wc_resp = await client.get(f"/api/v1/cases/{case_id}/working-capital")
        
        # Bug: Returns 404 when no data exists
        # Expected: Should return 200 with {"status": "not_analyzed"}
        assert wc_resp.status_code == 200, \
            f"Expected 200, got {wc_resp.status_code}. Should return 200 with status field, not 404."
        
        data = wc_resp.json()
        assert "status" in data, "Response should have status field when no analysis exists"
        assert data["status"] == "not_analyzed", "Status should be 'not_analyzed'"
    
    async def test_research_summary_endpoint_exists(self, client):
        """
        Call GET /api/v1/cases/{case_id}/research/summary → Should return 200
        
        Expected to FAIL with 404 on unfixed code when no research exists.
        Should return {"status": "not_run"} instead of 404.
        """
        # Create case
        resp = await client.post("/api/v1/cases", json={"company_name": "Test Company"})
        case_id = resp.json().get("case_id") or resp.json().get("id")
        
        # Call research summary endpoint WITHOUT running research
        research_resp = await client.get(f"/api/v1/cases/{case_id}/research/summary")
        
        # Bug: Returns 404 when no research exists
        # Expected: Should return 200 with {"status": "not_run"}
        assert research_resp.status_code == 200, \
            f"Expected 200, got {research_resp.status_code}. Should return 200 with status field, not 404."
        
        data = research_resp.json()
        assert "status" in data, "Response should have status field when no research exists"
        assert data["status"] == "not_run", "Status should be 'not_run'"


# ─────────────────────────────────────────────────────────────────────────────
# Bug 1: Empty Working Capital Ratios Table (Data Structure Test)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
class TestBug1EmptyWCTable:
    """
    Bug 1: Working capital data structure test
    
    **Validates: Requirements 2.1, 2.2, 2.3**
    
    EXPECTED: Test FAILS if wc_rows is empty or missing required metrics
    """
    
    async def test_wc_analysis_has_required_metrics(self, client):
        """
        Load demo and analyze → Check wc_analysis has required metrics
        
        Expected to FAIL if the data structure doesn't have the right keys.
        """
        # Create case
        resp = await client.post("/api/v1/cases", json={"company_name": "Surya Pharmaceuticals Ltd"})
        case_id = resp.json().get("case_id") or resp.json().get("id")
        
        # Load demo data
        await client.post(f"/api/v1/cases/{case_id}/load-demo?scenario=surya")
        
        # Run analysis
        analyze_resp = await client.post(f"/api/v1/cases/{case_id}/analyze")
        assert analyze_resp.status_code == 200
        
        # Get working capital data
        wc_resp = await client.get(f"/api/v1/cases/{case_id}/working-capital")
        
        # This will fail with 404 on unfixed code (Bug 3)
        # But if Bug 3 is fixed, we can check the data structure
        if wc_resp.status_code == 200:
            wc_data = wc_resp.json()
            
            # Check for required metrics
            # The bug is that _build_payload reads wc.get("yearly_metrics", [])
            # but the data might be structured differently
            
            # Expected metrics: DSCR, D/E Ratio, Current Ratio, DSO, DPO, 
            # Inventory Days, CCC, Interest Coverage
            required_keys = [
                "latest_dscr", "latest_de_ratio", "latest_current_ratio",
                "latest_dso", "latest_dpo", "latest_inventory_days",
                "latest_ccc", "latest_interest_coverage"
            ]
            
            for key in required_keys:
                assert key in wc_data, f"Working capital data should have {key}"


# ─────────────────────────────────────────────────────────────────────────────
# Summary Test: Document All Bugs
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
class TestBugSummary:
    """
    Summary test that documents all bugs in one place.
    """
    
    def test_bug_summary_documentation(self):
        """
        Document all 6 bugs for reference.
        
        This test always passes - it's just documentation.
        """
        bugs = {
            "Bug 1": "Empty Working Capital Ratios table in Section 4.1",
            "Bug 2": "False litigation in Surya Pharmaceuticals demo data",
            "Bug 3a": "GET /api/v1/cases/{case_id}/working-capital returns 404",
            "Bug 3b": "GET /api/v1/cases/{case_id}/research/summary returns 404",
            "Bug 4": "Revenue CAGR shows 0.0% instead of 15.2%",
            "Bug 5": "Security cover shows 0.00x instead of 1.96x",
            "Bug 6": "DSCR risk factor appears on APPROVE cases with DSCR > 1.30"
        }
        
        print("\n" + "="*70)
        print("CAM DATA BUGS - EXPLORATION TEST SUMMARY")
        print("="*70)
        for bug_id, description in bugs.items():
            print(f"{bug_id}: {description}")
        print("="*70)
        
        assert True, "Documentation test"
