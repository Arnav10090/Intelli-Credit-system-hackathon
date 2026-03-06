"""
tests/test_loan_calculator.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the loan sizing engine (loan_calculator.py).

Covers:
  - DSCR-based loan limit
  - Collateral-based limit (LTV computation)
  - Drawing power computation
  - Binding constraint selection (min of limits)
  - REJECT case → recommended = ₹0
  - Interest rate build-up (base + risk premium + tenor + collateral discount)
  - LTV mapping (land/plant/receivables)
  - Sizing notes generation

Run:
  cd backend && pytest ../tests/test_loan_calculator.py -v
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from scoring.loan_calculator import compute_loan_sizing, sizing_to_dict
from scoring.five_cs_scorer import ScorecardResult
from scoring.feature_engineer import FeatureSet
from config import settings


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def make_scorecard(
    decision="APPROVE",
    normalised_score=72,
    risk_grade="A",
    interest_premium_bps=75,
    base_rate_pct=9.0,
    recommended_rate_pct=10.75,
    **overrides
) -> ScorecardResult:
    defaults = dict(
        character_score=50, capacity_score=50, capital_score=38,
        collateral_score=25, conditions_score=28,
        total_raw_score=191, normalised_score=normalised_score,
        risk_grade=risk_grade, risk_label="Strong",
        decision=decision,
        primary_rejection_trigger="",
        counter_factual="",
        contributions={},
        knockout_flags=[],
        interest_premium_bps=interest_premium_bps,
        base_rate_pct=base_rate_pct,
        recommended_rate_pct=recommended_rate_pct,
    )
    defaults.update(overrides)
    return ScorecardResult(**defaults)


def make_features(
    dscr=1.8,
    security_cover=1.6,
    promoter_equity_pct=65.0,
    de_ratio=2.0,
    **overrides
) -> FeatureSet:
    defaults = dict(
        litigation_risk=0.9,
        promoter_track_record=0.8,
        gst_compliance=0.9,
        management_quality=0.8,
        dscr=dscr,
        ebitda_margin_trend=0.7,
        revenue_cagr_vs_sector=0.7,
        plant_utilization=0.75,
        de_ratio=de_ratio,
        net_worth_trend=0.7,
        promoter_equity_pct=promoter_equity_pct,
        security_cover=security_cover,
        collateral_encumbrance=0.9,
        sector_outlook=0.7,
        customer_concentration=0.7,
        regulatory_environment=0.7,
    )
    defaults.update(overrides)
    return FeatureSet(**defaults)


def make_financial_data(
    ebitda=1400.0,
    interest_expense=350.0,
    requested_cr=20.0,
    tenor_years=7,
    cc_requested_cr=5.0,
    inventory=900.0,
    trade_receivables=1000.0,
    trade_payables=550.0,
    securities=None,
) -> dict:
    if securities is None:
        securities = [
            {"description": "Factory Land", "asset_type": "land", "fmv_lakhs": 2200.0, "existing_charge_lakhs": 0.0},
            {"description": "Plant & Machinery", "asset_type": "plant_machinery", "fmv_lakhs": 800.0, "existing_charge_lakhs": 0.0},
        ]
    return {
        "loan_request": {
            "total_requested_cr": requested_cr,
            "tenor_years": tenor_years,
            "cc_requested_cr": cc_requested_cr,
            "security_proposed": securities,
        },
        "financials": {
            "profit_and_loss": {
                "ebitda": ebitda,
                "interest_expense": interest_expense,
            },
            "balance_sheet": {
                "inventory": inventory,
                "trade_receivables": trade_receivables,
                "trade_payables": trade_payables,
            },
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# Basic Sanity Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestLoanSizingBasics:

    def test_returns_result_object(self):
        sc = make_scorecard()
        f = make_features()
        fd = make_financial_data()
        result = compute_loan_sizing(sc, f, fd)
        assert result is not None

    def test_reject_case_recommended_zero(self):
        sc = make_scorecard(
            decision="REJECT",
            recommended_rate_pct=0.0,
            interest_premium_bps=0,
            base_rate_pct=0.0,
        )
        f = make_features()
        fd = make_financial_data()
        result = compute_loan_sizing(sc, f, fd)
        assert result.recommended_cr == 0.0
        assert result.binding_constraint == "decision_reject"

    def test_approve_case_positive_recommended(self):
        sc = make_scorecard(decision="APPROVE")
        f = make_features()
        fd = make_financial_data()
        result = compute_loan_sizing(sc, f, fd)
        assert result.recommended_cr > 0

    def test_recommended_does_not_exceed_requested(self):
        sc = make_scorecard(decision="APPROVE")
        f = make_features()
        fd = make_financial_data(requested_cr=20.0)
        result = compute_loan_sizing(sc, f, fd)
        assert result.recommended_cr <= 20.0


# ─────────────────────────────────────────────────────────────────────────────
# Collateral LTV Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCollateralLtv:

    def test_land_ltv_60_percent(self):
        """Land LTV = 60% per config."""
        sc = make_scorecard(decision="APPROVE")
        f = make_features()
        securities = [
            {"description": "Land", "asset_type": "land", "fmv_lakhs": 1000.0, "existing_charge_lakhs": 0.0}
        ]
        fd = make_financial_data(securities=securities, requested_cr=100.0)
        result = compute_loan_sizing(sc, f, fd)
        # LTV = 60% → eligible = 600L = ₹6 Cr
        assert abs(result.limit_collateral_cr - 6.0) < 0.1

    def test_plant_machinery_ltv_50_percent(self):
        """Plant & Machinery LTV = 50%."""
        sc = make_scorecard(decision="APPROVE")
        f = make_features()
        securities = [
            {"description": "Plant", "asset_type": "plant_machinery", "fmv_lakhs": 1000.0, "existing_charge_lakhs": 0.0}
        ]
        fd = make_financial_data(securities=securities, requested_cr=100.0)
        result = compute_loan_sizing(sc, f, fd)
        # LTV = 50% → eligible = 500L = ₹5 Cr
        assert abs(result.limit_collateral_cr - 5.0) < 0.1

    def test_receivables_ltv_75_percent(self):
        """Receivables LTV = 75%."""
        sc = make_scorecard(decision="APPROVE")
        f = make_features()
        securities = [
            {"description": "Receivables", "asset_type": "receivables", "fmv_lakhs": 1000.0, "existing_charge_lakhs": 0.0}
        ]
        fd = make_financial_data(securities=securities, requested_cr=100.0)
        result = compute_loan_sizing(sc, f, fd)
        # LTV = 75% → eligible = 750L = ₹7.5 Cr
        assert abs(result.limit_collateral_cr - 7.5) < 0.1

    def test_existing_charge_reduces_eligible_collateral(self):
        """Existing charge on security reduces eligible amount."""
        sc = make_scorecard(decision="APPROVE")
        f = make_features()
        securities_no_charge = [
            {"description": "Land", "asset_type": "land", "fmv_lakhs": 1000.0, "existing_charge_lakhs": 0.0}
        ]
        securities_with_charge = [
            {"description": "Land", "asset_type": "land", "fmv_lakhs": 1000.0, "existing_charge_lakhs": 400.0}
        ]
        fd_clean  = make_financial_data(securities=securities_no_charge,    requested_cr=100.0)
        fd_charge = make_financial_data(securities=securities_with_charge,  requested_cr=100.0)
        result_clean  = compute_loan_sizing(sc, f, fd_clean)
        result_charge = compute_loan_sizing(sc, f, fd_charge)
        assert result_charge.limit_collateral_cr < result_clean.limit_collateral_cr

    def test_multiple_securities_sum_correctly(self):
        """Multiple security items → limits should aggregate."""
        sc = make_scorecard(decision="APPROVE")
        f = make_features()
        securities = [
            {"description": "Land",  "asset_type": "land",           "fmv_lakhs": 1000.0, "existing_charge_lakhs": 0.0},
            {"description": "Plant", "asset_type": "plant_machinery", "fmv_lakhs": 1000.0, "existing_charge_lakhs": 0.0},
        ]
        fd = make_financial_data(securities=securities, requested_cr=100.0)
        result = compute_loan_sizing(sc, f, fd)
        # Land: 1000×0.6=600L + Plant: 1000×0.5=500L = 1100L = ₹11 Cr
        assert abs(result.limit_collateral_cr - 11.0) < 0.2


# ─────────────────────────────────────────────────────────────────────────────
# Interest Rate Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestInterestRate:

    def test_base_rate_is_repo_plus_nbfc_spread(self):
        sc = make_scorecard(decision="APPROVE")
        f = make_features()
        fd = make_financial_data()
        result = compute_loan_sizing(sc, f, fd)
        expected_base = settings.RBI_REPO_RATE + settings.NBFC_BASE_SPREAD
        assert abs(result.base_rate_pct - expected_base) < 0.01

    def test_long_tenor_premium_applied_above_5_years(self):
        sc = make_scorecard(decision="APPROVE")
        f = make_features(security_cover=0.9)  # No collateral discount
        fd_short = make_financial_data(tenor_years=4)
        fd_long  = make_financial_data(tenor_years=7)
        result_short = compute_loan_sizing(sc, f, fd_short)
        result_long  = compute_loan_sizing(sc, f, fd_long)
        expected_diff = settings.LONG_TENOR_PREMIUM_BPS / 100
        assert abs((result_long.recommended_rate_pct - result_short.recommended_rate_pct) - expected_diff) < 0.01

    def test_no_tenor_premium_for_short_tenor(self):
        sc = make_scorecard(decision="APPROVE")
        f = make_features(security_cover=0.9)  # No collateral discount
        fd = make_financial_data(tenor_years=5)
        result = compute_loan_sizing(sc, f, fd)
        assert result.tenor_premium_pct == 0.0

    def test_strong_collateral_discount_applied(self):
        """Security cover ≥2.0x triggers a discount."""
        sc = make_scorecard(decision="APPROVE")
        f_strong = make_features(security_cover=2.5)   # Above STRONG_COLLATERAL_THRESHOLD
        f_weak   = make_features(security_cover=1.2)   # Below threshold
        fd = make_financial_data(tenor_years=4)         # No tenor premium
        result_strong = compute_loan_sizing(sc, f_strong, fd)
        result_weak   = compute_loan_sizing(sc, f_weak,   fd)
        assert result_strong.recommended_rate_pct < result_weak.recommended_rate_pct
        expected_discount = settings.STRONG_COLLATERAL_DISCOUNT_BPS / 100
        assert abs((result_weak.recommended_rate_pct - result_strong.recommended_rate_pct) - expected_discount) < 0.01

    def test_rate_components_sum_to_final(self):
        sc = make_scorecard(decision="APPROVE")
        f = make_features(security_cover=1.2)  # No collateral discount
        fd = make_financial_data(tenor_years=4)  # No tenor premium
        result = compute_loan_sizing(sc, f, fd)
        expected = result.base_rate_pct + result.risk_premium_pct + result.tenor_premium_pct - result.collateral_discount_pct
        assert abs(result.recommended_rate_pct - expected) < 0.01


# ─────────────────────────────────────────────────────────────────────────────
# Binding Constraint Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBindingConstraint:

    def test_dscr_binds_when_earnings_are_low(self):
        """Low EBITDA → DSCR limit is the binding constraint."""
        sc = make_scorecard(decision="APPROVE")
        f = make_features(security_cover=2.5)  # Plenty of collateral
        fd = make_financial_data(
            ebitda=400.0,          # Very low → tight DSCR limit
            interest_expense=100.0,
            requested_cr=100.0,    # Much larger than earnings can support
            securities=[
                {"description": "Land", "asset_type": "land", "fmv_lakhs": 5000.0, "existing_charge_lakhs": 0.0}
            ]
        )
        result = compute_loan_sizing(sc, f, fd)
        assert result.binding_constraint in ("dscr", "requested")

    def test_collateral_binds_when_insufficient(self):
        """Small collateral → collateral limit is binding."""
        sc = make_scorecard(decision="APPROVE")
        f = make_features(security_cover=1.0)
        fd = make_financial_data(
            ebitda=5000.0,         # Strong earnings
            interest_expense=100.0,
            requested_cr=100.0,
            securities=[
                {"description": "Land", "asset_type": "land", "fmv_lakhs": 500.0, "existing_charge_lakhs": 0.0}
            ]
        )
        result = compute_loan_sizing(sc, f, fd)
        assert result.binding_constraint in ("collateral", "requested")

    def test_requested_binds_when_all_limits_exceed_request(self):
        """If borrower requests less than all limits, requested is binding."""
        sc = make_scorecard(decision="APPROVE")
        f = make_features(security_cover=2.0)
        fd = make_financial_data(
            ebitda=5000.0,
            interest_expense=100.0,
            requested_cr=5.0,   # Small request
            securities=[
                {"description": "Land", "asset_type": "land", "fmv_lakhs": 5000.0, "existing_charge_lakhs": 0.0}
            ]
        )
        result = compute_loan_sizing(sc, f, fd)
        assert result.recommended_cr <= 5.0


# ─────────────────────────────────────────────────────────────────────────────
# Serialisation
# ─────────────────────────────────────────────────────────────────────────────

class TestSizingToDict:

    def test_all_expected_keys_present(self):
        sc = make_scorecard(decision="APPROVE")
        f = make_features()
        fd = make_financial_data()
        result = compute_loan_sizing(sc, f, fd)
        d = sizing_to_dict(result)

        assert "limits" in d
        assert "recommendation" in d
        assert "rate" in d
        assert "repayment" in d
        assert "sizing_notes" in d

    def test_limits_keys(self):
        sc = make_scorecard(decision="APPROVE")
        result = compute_loan_sizing(sc, make_features(), make_financial_data())
        d = sizing_to_dict(result)
        assert all(k in d["limits"] for k in (
            "dscr_based_cr", "collateral_based_cr", "drawing_power_cr", "requested_cr"
        ))

    def test_rate_keys(self):
        sc = make_scorecard(decision="APPROVE")
        result = compute_loan_sizing(sc, make_features(), make_financial_data())
        d = sizing_to_dict(result)
        assert all(k in d["rate"] for k in (
            "base_rate_pct", "risk_premium_pct", "tenor_premium_pct",
            "collateral_discount_pct", "recommended_rate_pct"
        ))

    def test_sizing_notes_is_list(self):
        sc = make_scorecard(decision="APPROVE")
        result = compute_loan_sizing(sc, make_features(), make_financial_data())
        d = sizing_to_dict(result)
        assert isinstance(d["sizing_notes"], list)

    def test_reject_has_zero_recommendation_in_dict(self):
        sc = make_scorecard(
            decision="REJECT", recommended_rate_pct=0.0,
            interest_premium_bps=0, base_rate_pct=0.0
        )
        result = compute_loan_sizing(sc, make_features(), make_financial_data())
        d = sizing_to_dict(result)
        assert d["recommendation"]["recommended_cr"] == 0.0