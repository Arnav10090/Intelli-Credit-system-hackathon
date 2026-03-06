"""
tests/test_gst_reconciler.py — uses the exact data shape _run_reconciliation expects:
  - gstr_2a_quarterly_summary: list of quarters with eligible_itc_* fields and supplier_filing_rate_pct
  - gstr_3b_monthly: list of monthly records with itc_claimed_* fields
  - bank_vs_gst_reconciliation: dict with variance_details list
  - circular_trading_analysis: optional dict
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from ingestor.gst_reconciler import run_reconciliation_from_dict


def make_gst_data(
    eligible_itc_per_quarter=250_000.0,   # lakhs
    claimed_itc_per_quarter=240_000.0,    # claimed each quarter via 3B months
    supplier_filing_rate=95.0,
    bank_ratio=0.97,                       # bank_credits / gst_turnover per month
    num_quarters=4,
    circular_cycles=0,
) -> dict:
    """Build dict in the exact shape _run_reconciliation reads."""
    quarters = [f"Q{i+1}FY24" for i in range(num_quarters)]
    months_per_q = ["Apr", "Jul", "Oct", "Jan"][:num_quarters]

    # gstr_2a_quarterly_summary — what the reconciler actually reads
    quarterly_2a = [
        {
            "quarter": q,
            "eligible_itc_igst_lakhs": eligible_itc_per_quarter,
            "eligible_itc_cgst_lakhs": 0.0,
            "eligible_itc_sgst_lakhs": 0.0,
            "supplier_filing_rate_pct": supplier_filing_rate,
        }
        for q in quarters
    ]

    # gstr_3b_monthly — one month per quarter for simplicity
    monthly_3b = [
        {
            "month": f"{m} 2023",
            "itc_claimed_igst": claimed_itc_per_quarter,
            "itc_claimed_cgst": 0.0,
            "itc_claimed_sgst": 0.0,
        }
        for m in months_per_q
    ]

    # bank_vs_gst — variance_details list
    monthly_turnover = 5_000_000.0
    bank_vs_gst = {
        "variance_details": [
            {
                "month": f"Month{i+1}",
                "gst_turnover": monthly_turnover,
                "bank_credits": monthly_turnover * bank_ratio,
                "ratio": bank_ratio,
            }
            for i in range(num_quarters * 3)  # ~12 months
        ]
    }

    data = {
        "gstin": "27AAACA1234B1ZV",
        "period": "FY2024",
        "gstr_2a_quarterly_summary": quarterly_2a,
        "gstr_3b_monthly": monthly_3b,
        "bank_vs_gst_reconciliation": bank_vs_gst,
    }

    if circular_cycles > 0:
        data["circular_trading_analysis"] = {"cycles_detected": circular_cycles}

    return data


def call(data):
    return run_reconciliation_from_dict("DOC001", data)


def get_flags(result):
    return getattr(result, "flags", [])


def flag_types(result):
    return [getattr(f, "flag_type", f.get("flag_type", "")) for f in get_flags(result)]


# ─────────────────────────────────────────────────────────────────────────────
class TestCleanGstData:

    def test_clean_data_returns_result(self):
        assert call(make_gst_data()) is not None

    def test_compliance_score_in_0_to_1_range(self):
        result = call(make_gst_data())
        score = getattr(result, "compliance_score",
                getattr(result, "gst_compliance_score", 1.0))
        assert 0.0 <= score <= 1.0

    def test_clean_data_no_flags(self):
        result = call(make_gst_data(
            eligible_itc_per_quarter=250_000.0,
            claimed_itc_per_quarter=240_000.0,   # well under 110%
            supplier_filing_rate=96.0,
            bank_ratio=0.97,
        ))
        assert len(get_flags(result)) == 0


# ─────────────────────────────────────────────────────────────────────────────
class TestItcMismatch:

    def test_large_itc_overclaim_raises_flag(self):
        # Claimed = 130% of eligible → violates 110% rule
        result = call(make_gst_data(
            eligible_itc_per_quarter=100_000.0,
            claimed_itc_per_quarter=130_000.0,
        ))
        assert len(get_flags(result)) >= 1

    def test_110_percent_rule_exact_violation(self):
        # Claimed = 111% of eligible
        result = call(make_gst_data(
            eligible_itc_per_quarter=100_000.0,
            claimed_itc_per_quarter=111_000.0,
        ))
        assert len(get_flags(result)) >= 1

    def test_itc_within_110_percent_no_flag(self):
        # Claimed = 105% → within rule
        result = call(make_gst_data(
            eligible_itc_per_quarter=100_000.0,
            claimed_itc_per_quarter=105_000.0,
        ))
        itc_flags = [f for f in flag_types(result) if "itc" in f.lower()]
        assert len(itc_flags) == 0


# ─────────────────────────────────────────────────────────────────────────────
class TestSupplierCompliance:

    def test_low_supplier_compliance_raises_flag(self):
        # 55% compliance — well below any threshold
        result = call(make_gst_data(supplier_filing_rate=55.0))
        assert len(get_flags(result)) >= 1

    def test_high_supplier_compliance_no_flag(self):
        result = call(make_gst_data(supplier_filing_rate=97.0))
        supplier_flags = [f for f in flag_types(result) if "supplier" in f.lower()]
        assert len(supplier_flags) == 0


# ─────────────────────────────────────────────────────────────────────────────
class TestRevenueInflation:

    def test_bank_credits_far_below_gst_raises_flag(self):
        # ratio=0.70 → bank credits only 70% of GST turnover, below 85% threshold
        # Need ≥2 months to trigger the flag
        result = call(make_gst_data(bank_ratio=0.70))
        assert len(get_flags(result)) >= 1

    def test_bank_credits_matching_gst_no_flag(self):
        result = call(make_gst_data(bank_ratio=0.97))
        rev_flags = [f for f in flag_types(result)
                     if any(k in f.lower() for k in ("revenue", "bank", "inflation"))]
        assert len(rev_flags) == 0


# ─────────────────────────────────────────────────────────────────────────────
class TestCircularTrading:

    def test_circular_trading_flag_when_cycles_detected(self):
        result = call(make_gst_data(circular_cycles=2))
        assert any("circular" in f.lower() or "CIRCULAR" in f
                   for f in flag_types(result))

    def test_no_circular_flag_when_zero_cycles(self):
        result = call(make_gst_data(circular_cycles=0))
        assert not any("CIRCULAR" in f for f in flag_types(result))


# ─────────────────────────────────────────────────────────────────────────────
class TestEdgeCases:

    def test_empty_data_does_not_raise(self):
        assert call({}) is not None

    def test_zero_eligible_itc_handled(self):
        data = make_gst_data(eligible_itc_per_quarter=0.0, claimed_itc_per_quarter=0.0)
        assert call(data) is not None

    def test_result_is_serialisable(self):
        import json
        result = call(make_gst_data())
        if isinstance(result, dict):
            json.dumps(result, default=str)
        elif hasattr(result, "__dict__"):
            json.dumps(result.__dict__, default=str)