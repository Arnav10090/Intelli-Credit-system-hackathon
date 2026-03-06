"""
tests/test_working_capital.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the working capital analysis engine.

Key implementation details discovered:
  - P&L key: "revenue_from_operations" (not "revenue")
  - Balance sheet keys: "total_current_assets" / "total_current_liabilities"
  - DSCR = EBITDA / (interest_expense + total_debt/5)  [estimates principal]
  - Debtor days = trade_receivables / (revenue_from_operations / 365)
  - Revenue CAGR uses "revenue_from_operations" field

Run:
  cd backend && pytest ../tests/test_working_capital.py -v
──────────────────────────────────────────────────────────────────────────────
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from ingestor.working_capital_analyzer import (
    analyze_working_capital,
    _compute_cagr,
    _safe_avg,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixture helpers — use CORRECT key names matching the analyzer
# ─────────────────────────────────────────────────────────────────────────────

def make_financial_data(
    revenues=(8420.0, 9150.0, 9800.0),
    ebitdas=(1000.0, 1100.0, 1180.0),
    pats=(145.0, 180.0, 210.0),
    interest_expenses=(300.0, 320.0, 340.0),
    inventories=(800.0, 850.0, 900.0),
    trade_receivables=(900.0, 950.0, 980.0),
    trade_payables=(500.0, 520.0, 540.0),
    total_debts=(2400.0, 2500.0, 2600.0),
    tangible_net_worths=(900.0, 1000.0, 1100.0),
    total_current_assets=(2000.0, 2100.0, 2200.0),
    total_current_liabilities=(1200.0, 1250.0, 1300.0),
    years=("FY2022", "FY2023", "FY2024"),
) -> dict:
    """Build financial_data dict using the exact key names the analyzer expects."""
    return {
        "financials": {
            "years": list(years),
            "profit_and_loss": {
                # Correct key name used by _compute_year_metrics
                "revenue_from_operations": list(revenues),
                "ebitda":                  list(ebitdas),
                "pat":                     list(pats),
                "interest_expense":        list(interest_expenses),
            },
            "balance_sheet": {
                "inventory":                  list(inventories),
                "trade_receivables":          list(trade_receivables),
                "trade_payables":             list(trade_payables),
                "total_debt":                 list(total_debts),
                "tangible_net_worth":         list(tangible_net_worths),
                # Correct key names for current ratio
                "total_current_assets":       list(total_current_assets),
                "total_current_liabilities":  list(total_current_liabilities),
            },
            "cash_flow": {},
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# CAGR Helper
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeCagr:

    def test_flat_growth(self):
        assert abs(_compute_cagr([100.0, 100.0, 100.0], 2)) < 0.01

    def test_positive_growth(self):
        # 100 → 121 over 2 years ≈ 10% CAGR
        assert abs(_compute_cagr([100.0, 110.0, 121.0], 2) - 10.0) < 0.5

    def test_negative_growth(self):
        assert _compute_cagr([100.0, 90.0, 81.0], 2) < 0

    def test_single_value_zero_cagr(self):
        assert _compute_cagr([100.0], 0) == 0.0

    def test_empty_list(self):
        assert _compute_cagr([], 2) == 0.0

    def test_zero_start_value(self):
        assert _compute_cagr([0.0, 100.0], 1) == 0.0


class TestSafeAvg:
    def test_normal_average(self):  assert _safe_avg([1.0, 2.0, 3.0]) == 2.0
    def test_empty_returns_zero(self): assert _safe_avg([]) == 0.0
    def test_single_value(self):    assert _safe_avg([5.0]) == 5.0


# ─────────────────────────────────────────────────────────────────────────────
# Core Working Capital Analysis
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeWorkingCapital:

    def test_returns_correct_year_count(self):
        result = analyze_working_capital("DOC001", make_financial_data())
        assert len(result.yearly_metrics) == 3

    def test_years_list_matches(self):
        result = analyze_working_capital("DOC001", make_financial_data())
        assert result.years == ["FY2022", "FY2023", "FY2024"]

    def test_dscr_is_positive(self):
        result = analyze_working_capital("DOC001", make_financial_data())
        assert result.latest_dscr > 0
        assert result.avg_dscr > 0

    def test_dscr_formula_includes_principal_estimate(self):
        """DSCR = EBITDA / (interest + total_debt/5). Not simple EBITDA/interest."""
        # EBITDA=1200, interest=200, debt=2000 → principal_est=400
        # DSCR = 1200 / (200+400) = 2.0
        data = make_financial_data(
            ebitdas=(1200.0, 1200.0, 1200.0),
            interest_expenses=(200.0, 200.0, 200.0),
            total_debts=(2000.0, 2000.0, 2000.0),
        )
        result = analyze_working_capital("DOC001", data)
        expected = 1200 / (200 + 2000 / 5)  # = 2.0
        assert abs(result.latest_dscr - expected) < 0.05

    def test_positive_revenue_cagr(self):
        data = make_financial_data(revenues=(8000.0, 9000.0, 10000.0))
        result = analyze_working_capital("DOC001", data)
        assert result.revenue_cagr_pct > 0

    def test_zero_revenue_cagr_for_flat(self):
        data = make_financial_data(revenues=(9000.0, 9000.0, 9000.0))
        result = analyze_working_capital("DOC001", data)
        assert abs(result.revenue_cagr_pct) < 0.5

    def test_de_ratio_is_debt_over_net_worth(self):
        data = make_financial_data(
            total_debts=(2000.0, 2000.0, 2000.0),
            tangible_net_worths=(1000.0, 1000.0, 1000.0),
        )
        result = analyze_working_capital("DOC001", data)
        assert abs(result.latest_de_ratio - 2.0) < 0.05

    def test_cash_conversion_cycle_positive_for_standard_data(self):
        result = analyze_working_capital("DOC001", make_financial_data())
        # With normal textiles data, CCC should be positive
        assert result.latest_ccc > 0

    def test_ccc_decreases_when_payables_increase(self):
        """Higher payables → lower CCC."""
        data_low  = make_financial_data(trade_payables=(200.0, 200.0, 200.0))
        data_high = make_financial_data(trade_payables=(800.0, 800.0, 800.0))
        result_low  = analyze_working_capital("DOC001", data_low)
        result_high = analyze_working_capital("DOC001", data_high)
        assert result_high.latest_ccc < result_low.latest_ccc

    def test_current_ratio_computed_when_bs_keys_provided(self):
        data = make_financial_data(
            total_current_assets=(2000.0, 2000.0, 2000.0),
            total_current_liabilities=(1000.0, 1000.0, 1000.0),
        )
        result = analyze_working_capital("DOC001", data)
        assert result.latest_current_ratio >= 1.0

    def test_stress_flag_raised_for_high_debtor_days(self):
        """Very high receivables relative to revenue → DEBTOR_DAYS_HIGH flag."""
        data = make_financial_data(
            revenues=(1000.0, 1000.0, 1000.0),
            trade_receivables=(600.0, 600.0, 600.0),  # DSO ≈ 219 days
        )
        result = analyze_working_capital("DOC001", data)
        assert len(result.flags) > 0

    def test_empty_years_returns_empty_result(self):
        data = {"financials": {"years": [], "profit_and_loss": {}, "balance_sheet": {}}}
        result = analyze_working_capital("DOC001", data)
        assert len(result.yearly_metrics) == 0
        assert len(result.warnings) > 0

    def test_missing_financials_key_handled_gracefully(self):
        result = analyze_working_capital("DOC001", {})
        assert result is not None
        assert len(result.warnings) > 0

    def test_doc_id_preserved(self):
        result = analyze_working_capital("MY_DOC_ID", make_financial_data())
        assert result.doc_id == "MY_DOC_ID"

    def test_no_negative_dscr_or_de(self):
        result = analyze_working_capital("DOC001", make_financial_data())
        assert result.latest_dscr >= 0
        assert result.avg_dscr >= 0
        assert result.latest_de_ratio >= 0


# ─────────────────────────────────────────────────────────────────────────────
# Stress flag tests
# ─────────────────────────────────────────────────────────────────────────────

class TestStressFlags:

    def test_no_flags_for_ideal_data(self):
        """Low receivables + low payables + strong EBITDA → zero or minimal flags."""
        data = make_financial_data(
            revenues=(8000.0, 9000.0, 10000.0),
            ebitdas=(1600.0, 1800.0, 2000.0),
            interest_expenses=(200.0, 200.0, 200.0),
            # Tight working capital days — receivables ≈ 15 days, payables ≈ 15 days
            trade_receivables=(330.0, 370.0, 411.0),   # ~15 day DSO
            trade_payables=(233.0, 247.0, 260.0),       # ~15 day DPO  (based on COGS ≈ 70%)
            inventories=(233.0, 247.0, 260.0),           # ~15 day DIO
            total_debts=(1000.0, 900.0, 800.0),
            tangible_net_worths=(2000.0, 2200.0, 2400.0),
            total_current_assets=(3000.0, 3200.0, 3400.0),
            total_current_liabilities=(1000.0, 1000.0, 1000.0),
        )
        result = analyze_working_capital("DOC001", data)
        assert len(result.flags) == 0

    def test_declining_revenue_raises_flag(self):
        data = make_financial_data(revenues=(10000.0, 8000.0, 6000.0))
        result = analyze_working_capital("DOC001", data)
        assert len(result.flags) > 0

    def test_high_de_ratio_raises_flag(self):
        data = make_financial_data(
            total_debts=(5000.0, 5500.0, 6000.0),
            tangible_net_worths=(800.0, 800.0, 800.0),  # D/E ≈ 7.5x
        )
        result = analyze_working_capital("DOC001", data)
        assert len(result.flags) > 0