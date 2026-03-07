"""
tests/test_demo_scenarios.py
──────────────────────────────────────────────────────────────────────────────
Validates both demo scenarios end-to-end at the data and scoring level.

  Scenario 1 — Acme Textiles Ltd (acme):  Grade C / REJECT  (~42/100)
  Scenario 2 — Surya Pharmaceuticals Ltd (surya): Grade A+/ APPROVE (~88/100)

These tests run without a live server — they load the JSON files directly,
compute features, and run the scorecard. They also validate the API route
parameter works correctly via the TestClient.
──────────────────────────────────────────────────────────────────────────────
"""

import sys, os, json
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest

BACKEND_DIR = Path(__file__).parent.parent / "backend"
DEMO_DIR    = BACKEND_DIR / "data" / "demo_company"
DEMO_DIR2   = BACKEND_DIR / "data" / "demo_company2"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — load JSON and build FeatureSet manually without running the server
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def features_from_financial(fin: dict):
    """
    Build a FeatureSet from a financial_data.json dict.
    Mirrors what feature_engineer.py does for the demo case.
    """
    from scoring.feature_engineer import FeatureSet

    fi = fin["financials"]
    pl = fi["profit_and_loss"]
    bs = fi["balance_sheet"]
    dr = fin["derived_ratios"]
    prom = fin["promoters"]
    sh   = fin["shareholding_pattern"]

    revenues = pl["revenue_from_operations"]
    ebitdas  = pl["ebitda"]
    debts    = bs["total_debt"]
    nws      = bs["tangible_net_worth"]

    # Use last year values
    dscr_vals = dr["dscr"]
    avg_dscr  = sum(dscr_vals) / len(dscr_vals)
    avg_de    = sum(dr["de_ratio"]) / len(dr["de_ratio"])

    # EBITDA margin trend: slope of margin series (normalised to 0-1)
    margins = pl["ebitda_margin_pct"]
    ebitda_trend = (margins[-1] - margins[0]) / max(margins[0], 1)
    ebitda_trend = max(0.0, min(1.0, 0.5 + ebitda_trend * 2))

    # Revenue CAGR vs sector benchmark (assume sector ~8% for textiles, ~10% for pharma)
    from ingestor.working_capital_analyzer import compute_cagr
    rev_cagr = compute_cagr(revenues)
    sector_cagr = 0.10  # default benchmark
    cagr_ratio = min(1.0, max(0.0, (rev_cagr / sector_cagr) * 0.5 + 0.3))

    pledged = sh.get("promoter_pledged_pct", 0.0)
    pledge_score = max(0.0, 1.0 - pledged / 100.0)

    promoter_eq = sh.get("promoter_total_pct", 50.0)

    return FeatureSet(
        litigation_risk=0.55,           # overridden per scenario in tests
        promoter_track_record=pledge_score,
        gst_compliance=0.90,            # overridden per scenario in tests
        management_quality=0.65,
        dscr=avg_dscr,
        ebitda_margin_trend=ebitda_trend,
        revenue_cagr_vs_sector=cagr_ratio,
        plant_utilization=0.70,
        de_ratio=avg_de,
        net_worth_trend=0.60,
        promoter_equity_pct=promoter_eq,
        security_cover=1.5,             # overridden per scenario in tests
        collateral_encumbrance=0.80,
        sector_outlook=0.55,
        customer_concentration=0.60,
        regulatory_environment=0.60,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Data file sanity checks
# ─────────────────────────────────────────────────────────────────────────────

class TestDemoDataFiles:

    def test_acme_financial_data_exists(self):
        assert (DEMO_DIR / "financial_data.json").exists()

    def test_acme_gst_data_exists(self):
        assert (DEMO_DIR / "gst_data.json").exists()

    def test_acme_research_cache_exists(self):
        assert (DEMO_DIR / "research_cache.json").exists()

    def test_surya_financial_data_exists(self):
        assert (DEMO_DIR2 / "financial_data.json").exists()

    def test_surya_gst_data_exists(self):
        assert (DEMO_DIR2 / "gst_data.json").exists()

    def test_surya_research_cache_exists(self):
        assert (DEMO_DIR2 / "research_cache.json").exists()

    def test_surya_financial_is_valid_json(self):
        data = load_json(DEMO_DIR2 / "financial_data.json")
        assert "company" in data
        assert "financials" in data
        assert "loan_request" in data

    def test_surya_gst_is_valid_json(self):
        data = load_json(DEMO_DIR2 / "gst_data.json")
        assert "gstr_3b_monthly" in data
        assert "gstr_2a_quarterly_summary" in data
        assert len(data["gstr_3b_monthly"]) == 12

    def test_surya_research_risk_label_is_low(self):
        data = load_json(DEMO_DIR2 / "research_cache.json")
        label = data["aggregate_risk_score"]["overall_research_risk_label"]
        assert label == "LOW"

    def test_acme_research_risk_label_is_high(self):
        data = load_json(DEMO_DIR / "research_cache.json")
        label = data["aggregate_risk_score"]["overall_research_risk_label"]
        assert label == "HIGH"


# ─────────────────────────────────────────────────────────────────────────────
# Financial profile contrasts
# ─────────────────────────────────────────────────────────────────────────────

class TestFinancialContrasts:

    def test_surya_revenue_higher_than_acme(self):
        acme  = load_json(DEMO_DIR  / "financial_data.json")
        surya = load_json(DEMO_DIR2 / "financial_data.json")
        acme_rev  = acme["financials"]["profit_and_loss"]["revenue_from_operations"][-1]
        surya_rev = surya["financials"]["profit_and_loss"]["revenue_from_operations"][-1]
        assert surya_rev > acme_rev * 1.5

    def test_surya_ebitda_margin_above_20pct(self):
        surya = load_json(DEMO_DIR2 / "financial_data.json")
        margins = surya["financials"]["profit_and_loss"]["ebitda_margin_pct"]
        assert all(m >= 20.0 for m in margins)

    def test_acme_ebitda_margin_below_15pct(self):
        acme = load_json(DEMO_DIR / "financial_data.json")
        margins = acme["financials"]["profit_and_loss"]["ebitda_margin_pct"]
        assert all(m < 15.0 for m in margins)

    def test_surya_dscr_above_2(self):
        surya = load_json(DEMO_DIR2 / "financial_data.json")
        assert all(d >= 2.0 for d in surya["derived_ratios"]["dscr"])

    def test_acme_dscr_below_1_5(self):
        acme = load_json(DEMO_DIR / "financial_data.json")
        assert all(d < 1.5 for d in acme["derived_ratios"]["dscr"])

    def test_surya_de_ratio_below_1(self):
        surya = load_json(DEMO_DIR2 / "financial_data.json")
        assert all(d < 1.0 for d in surya["derived_ratios"]["de_ratio"])

    def test_acme_de_ratio_above_2(self):
        acme = load_json(DEMO_DIR / "financial_data.json")
        assert all(d >= 2.0 for d in acme["derived_ratios"]["de_ratio"])

    def test_surya_promoter_pledge_is_zero(self):
        surya = load_json(DEMO_DIR2 / "financial_data.json")
        assert surya["shareholding_pattern"]["promoter_pledged_pct"] == 0.0

    def test_acme_promoter_pledge_above_50pct(self):
        acme = load_json(DEMO_DIR / "financial_data.json")
        assert acme["shareholding_pattern"]["promoter_pledged_pct"] >= 50.0

    def test_surya_collateral_exceeds_loan_request(self):
        surya = load_json(DEMO_DIR2 / "financial_data.json")
        collateral_cr = surya["loan_request"]["total_eligible_collateral_cr"]
        requested_cr  = surya["loan_request"]["total_requested_cr"]
        assert collateral_cr > requested_cr * 1.5

    def test_surya_has_three_security_types(self):
        surya = load_json(DEMO_DIR2 / "financial_data.json")
        assert len(surya["loan_request"]["security_proposed"]) == 3

    def test_surya_cash_balance_growing(self):
        surya = load_json(DEMO_DIR2 / "financial_data.json")
        cash = surya["financials"]["balance_sheet"]["cash_and_bank"]
        assert cash[-1] > cash[0]

    def test_acme_cash_balance_declining(self):
        acme = load_json(DEMO_DIR / "financial_data.json")
        cash = acme["financials"]["balance_sheet"]["cash_and_bank"]
        assert cash[-1] < cash[0]


# ─────────────────────────────────────────────────────────────────────────────
# GST profile contrasts
# ─────────────────────────────────────────────────────────────────────────────

class TestGstContrasts:

    def test_surya_gst_no_reconciliation_issues(self):
        data = load_json(DEMO_DIR2 / "gst_data.json")
        assert data["bank_vs_gst_reconciliation"]["months_with_variance_above_threshold"] == 0

    def test_acme_gst_has_variance_months(self):
        data = load_json(DEMO_DIR / "gst_data.json")
        assert data["bank_vs_gst_reconciliation"]["months_with_variance_above_threshold"] >= 1

    def test_surya_supplier_filing_rate_above_96pct(self):
        data = load_json(DEMO_DIR2 / "gst_data.json")
        rates = [q["supplier_filing_rate_pct"] for q in data["gstr_2a_quarterly_summary"]]
        assert all(r >= 96.0 for r in rates)

    def test_acme_has_quarter_below_85pct_supplier_rate(self):
        data = load_json(DEMO_DIR / "gst_data.json")
        rates = [q["supplier_filing_rate_pct"] for q in data["gstr_2a_quarterly_summary"]]
        assert any(r < 85.0 for r in rates)

    def test_surya_no_circular_trading(self):
        data = load_json(DEMO_DIR2 / "gst_data.json")
        assert data["circular_trading_analysis"]["cycles_detected"] == 0

    def test_surya_has_12_monthly_gst_records(self):
        data = load_json(DEMO_DIR2 / "gst_data.json")
        assert len(data["gstr_3b_monthly"]) == 12

    def test_surya_bank_vs_gst_ratio_above_98pct(self):
        data = load_json(DEMO_DIR2 / "gst_data.json")
        ratios = [m["ratio"] for m in data["bank_vs_gst_reconciliation"]["variance_details"]]
        assert all(r >= 0.985 for r in ratios)


# ─────────────────────────────────────────────────────────────────────────────
# Scorecard outcome — Surya should APPROVE, Acme should REJECT
# ─────────────────────────────────────────────────────────────────────────────

class TestScorecardOutcomes:

    def _surya_features(self):
        from scoring.feature_engineer import FeatureSet
        surya = load_json(DEMO_DIR2 / "financial_data.json")
        dr = surya["derived_ratios"]
        sh = surya["shareholding_pattern"]
        avg_dscr = sum(dr["dscr"]) / len(dr["dscr"])
        avg_de   = sum(dr["de_ratio"]) / len(dr["de_ratio"])
        return FeatureSet(
            litigation_risk=0.95,        # Clean — no NCLT, minor consumer dispute
            promoter_track_record=0.88,  # 0% pledge, 28yr experience
            gst_compliance=0.96,         # 97%+ supplier filing, zero ITC issues
            management_quality=0.85,     # PhD promoter, ICRA A-
            dscr=avg_dscr,
            ebitda_margin_trend=0.78,    # Stable 22% margin
            revenue_cagr_vs_sector=0.82, # 15.2% CAGR vs ~10% sector
            plant_utilization=0.78,
            de_ratio=avg_de,
            net_worth_trend=0.85,        # Net worth growing rapidly
            promoter_equity_pct=68.0,
            security_cover=1.96,         # 58.9 Cr collateral / 30 Cr loan
            collateral_encumbrance=0.92, # Fresh charge only
            sector_outlook=0.78,         # China+1 tailwind
            customer_concentration=0.72, # Diversified export + domestic
            regulatory_environment=0.80, # USFDA approved
        )

    def _acme_features(self):
        from scoring.feature_engineer import FeatureSet
        acme = load_json(DEMO_DIR / "financial_data.json")
        dr = acme["derived_ratios"]
        avg_dscr = sum(dr["dscr"]) / len(dr["dscr"])
        avg_de   = sum(dr["de_ratio"]) / len(dr["de_ratio"])
        return FeatureSet(
            # NCLT IBC Section 9 petition → critical litigation → knockout (< 0.25)
            litigation_risk=0.18,
            promoter_track_record=0.32,  # 68% pledge
            gst_compliance=0.62,         # ITC overclaim + supplier non-compliance
            management_quality=0.55,
            dscr=avg_dscr,               # ~1.24x — stressed
            ebitda_margin_trend=0.48,
            revenue_cagr_vs_sector=0.45,
            plant_utilization=0.62,
            de_ratio=avg_de,             # ~2.3x
            net_worth_trend=0.50,
            promoter_equity_pct=67.0,
            security_cover=1.11,         # 22.2 Cr collateral / 20 Cr loan
            collateral_encumbrance=0.60,
            sector_outlook=0.40,         # Textile sector headwinds
            customer_concentration=0.45,
            regulatory_environment=0.50,
        )

    def test_surya_scores_above_75(self):
        from scoring.five_cs_scorer import compute_score
        result = compute_score(self._surya_features())
        assert result.normalised_score >= 75, (
            f"Expected Surya to score ≥75, got {result.normalised_score}"
        )

    def test_surya_decision_is_approve(self):
        from scoring.five_cs_scorer import compute_score
        result = compute_score(self._surya_features())
        assert result.decision == "APPROVE", (
            f"Expected APPROVE, got {result.decision} "
            f"(score={result.normalised_score}, grade={result.risk_grade})"
        )

    def test_surya_grade_is_a_or_better(self):
        from scoring.five_cs_scorer import compute_score
        result = compute_score(self._surya_features())
        assert result.risk_grade in ("A+", "A"), (
            f"Expected A or A+, got {result.risk_grade}"
        )

    def test_acme_scores_below_approve_threshold(self):
        """Acme scores below 55 (approve threshold) — knockout REJECT regardless."""
        from scoring.five_cs_scorer import compute_score
        result = compute_score(self._acme_features())
        assert result.normalised_score < 55, (
            f"Expected Acme to score <55, got {result.normalised_score}"
        )

    def test_acme_decision_is_reject_or_partial(self):
        from scoring.five_cs_scorer import compute_score
        result = compute_score(self._acme_features())
        assert result.decision in ("REJECT", "PARTIAL"), (
            f"Expected REJECT/PARTIAL, got {result.decision}"
        )

    def test_surya_no_knockout_flags(self):
        from scoring.five_cs_scorer import compute_score
        result = compute_score(self._surya_features())
        assert len(result.knockout_flags) == 0

    def test_acme_has_knockout_flags(self):
        from scoring.five_cs_scorer import compute_score
        result = compute_score(self._acme_features())
        assert len(result.knockout_flags) >= 1

    def test_surya_scores_higher_than_acme(self):
        from scoring.five_cs_scorer import compute_score
        surya_score = compute_score(self._surya_features()).normalised_score
        acme_score  = compute_score(self._acme_features()).normalised_score
        assert surya_score > acme_score + 20, (
            f"Expected Surya ({surya_score}) >> Acme ({acme_score}) by 20+ pts"
        )

    def test_surya_character_pillar_dominates(self):
        """Clean litigation + 0% pledge + strong compliance → top character score."""
        from scoring.five_cs_scorer import compute_score
        result = compute_score(self._surya_features())
        char_pct = result.character_score / result.character_max
        assert char_pct >= 0.75

    def test_surya_capacity_pillar_strong(self):
        """DSCR 2.6x + 22% EBITDA margin → strong capacity score."""
        from scoring.five_cs_scorer import compute_score
        result = compute_score(self._surya_features())
        cap_pct = result.capacity_score / result.capacity_max
        assert cap_pct >= 0.70

    def test_surya_capital_pillar_strong(self):
        """D/E 0.4x → top capital score."""
        from scoring.five_cs_scorer import compute_score
        result = compute_score(self._surya_features())
        capital_pct = result.capital_score / result.capital_max
        assert capital_pct >= 0.70


# ─────────────────────────────────────────────────────────────────────────────
# API route — scenario param (requires running server via TestClient)
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadDemoScenarioParam:

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    @pytest.fixture
    def case_id(self, client):
        resp = client.post("/api/v1/cases", json={"company_name": "Test Co"})
        return resp.json().get("case_id") or resp.json().get("id")

    def test_default_scenario_loads_acme(self, client, case_id):
        resp = client.post(f"/api/v1/cases/{case_id}/load-demo")
        assert resp.status_code == 200

    def test_acme_scenario_explicit(self, client, case_id):
        resp = client.post(f"/api/v1/cases/{case_id}/load-demo?scenario=acme")
        assert resp.status_code == 200
        assert resp.json()["documents_loaded"] >= 2

    def test_surya_scenario_loads(self, client):
        resp = client.post("/api/v1/cases", json={"company_name": "Surya Pharmaceuticals Ltd"})
        cid = resp.json().get("case_id") or resp.json().get("id")
        resp = client.post(f"/api/v1/cases/{cid}/load-demo?scenario=surya")
        assert resp.status_code == 200
        assert resp.json()["documents_loaded"] >= 2

    def test_surya_scenario_zero_flags(self, client):
        """Surya has clean GST — expect 0 reconciliation flags."""
        resp = client.post("/api/v1/cases", json={"company_name": "Surya Pharmaceuticals Ltd"})
        cid = resp.json().get("case_id") or resp.json().get("id")
        client.post(f"/api/v1/cases/{cid}/load-demo?scenario=surya")
        flags_resp = client.get(f"/api/v1/cases/{cid}/flags")
        assert flags_resp.status_code == 200
        assert len(flags_resp.json()) == 0

    def test_acme_scenario_has_flags(self, client, case_id):
        """Acme has ITC mismatch + supplier non-compliance → expect flags."""
        client.post(f"/api/v1/cases/{case_id}/load-demo?scenario=acme")
        flags_resp = client.get(f"/api/v1/cases/{case_id}/flags")
        assert flags_resp.status_code == 200
        assert len(flags_resp.json()) >= 1

    def test_unknown_scenario_falls_back_to_acme(self, client, case_id):
        """Unknown scenario name should not crash — falls back to acme dir."""
        resp = client.post(f"/api/v1/cases/{case_id}/load-demo?scenario=unknown_xyz")
        assert resp.status_code == 200