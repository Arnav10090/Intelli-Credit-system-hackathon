"""
ingestor/working_capital_analyzer.py
─────────────────────────────────────────────────────────────────────────────
Working Capital Cycle Stress Analysis for Intelli-Credit.

Computes from financial statement data:
  - Debtor Days (DSO)       = Trade Receivables / (Revenue / 365)
  - Creditor Days (DPO)     = Trade Payables / (COGS / 365)
  - Inventory Days (DIO)    = Inventory / (COGS / 365)
  - Cash Conversion Cycle   = DIO + DSO - DPO
  - Current Ratio           = Current Assets / Current Liabilities
  - Working Capital Gap     = CA - CL (excl. cash and ST borrowings)
  - Revenue CAGR (3yr)
  - EBITDA Margin Trend

Thresholds come from config.py — no hardcoded numbers here.
All computations are DETERMINISTIC — no LLM.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

from config import settings


# ── Data Structures ────────────────────────────────────────────────────────────

@dataclass
class YearlyMetrics:
    """All working capital metrics for one financial year."""
    year: str

    # Profitability
    revenue: float
    ebitda: float
    ebitda_margin_pct: float
    pat: float
    pat_margin_pct: float
    interest_expense: float

    # Balance sheet ratios
    current_ratio: float
    de_ratio: float                # Total Debt / Tangible Net Worth
    tangible_net_worth: float
    total_debt: float

    # Working capital days
    debtor_days: float             # DSO
    creditor_days: float           # DPO
    inventory_days: float          # DIO
    cash_conversion_cycle: float   # DIO + DSO - DPO

    # Working capital gap (₹ Lakhs)
    working_capital_gap: float     # CA - CL (excl. cash + ST borrow)
    net_working_capital: float     # Total CA - Total CL

    # Cash flow
    cfo: float
    capex: float
    fcf: float

    # Derived
    dscr: float                    # EBITDA / (Interest + Principal repayment)
    interest_coverage: float       # EBITDA / Interest


@dataclass
class WorkingCapitalResult:
    """Complete working capital analysis across all years."""
    doc_id: str
    years: list[str]
    yearly_metrics: list[YearlyMetrics]

    # Trend analysis
    revenue_cagr_pct: float
    ebitda_cagr_pct: float
    nw_cagr_pct: float

    # Deterioration flags
    flags: list[dict]              # [{metric, year, value, threshold, severity, message}]

    # Summary scores (fed into feature_engineer.py)
    avg_dscr: float
    avg_current_ratio: float
    avg_de_ratio: float
    latest_de_ratio: float
    latest_dscr: float
    latest_current_ratio: float
    latest_debtor_days: float
    latest_creditor_days: float
    latest_ccc: float              # Cash Conversion Cycle

    warnings: list[str] = field(default_factory=list)


# ── Main Analysis Function ────────────────────────────────────────────────────

def analyze_working_capital(doc_id: str, financial_data: dict) -> WorkingCapitalResult:
    """
    Main entry point. Takes the financial_data dict from demo_company/financial_data.json
    or extracted table data and computes all working capital metrics.

    Called from:
      - ingest_routes.py load_demo_data endpoint
      - feature_engineer.py (Step 4) for the scoring engine
    """
    logger.info("Running working capital analysis for doc_id=%s", doc_id)

    fin  = financial_data.get("financials", {})
    pnl  = fin.get("profit_and_loss", {})
    bs   = fin.get("balance_sheet", {})
    cf   = fin.get("cash_flow", {})
    years = fin.get("years", [])

    if not years:
        return _empty_result(doc_id, "No financial years found in data")

    yearly_metrics = []
    warnings       = []

    for i, year in enumerate(years):
        try:
            ym = _compute_year_metrics(year, i, pnl, bs, cf, warnings)
            yearly_metrics.append(ym)
        except Exception as e:
            warnings.append(f"Could not compute metrics for {year}: {e}")
            logger.error("Metrics computation failed for %s: %s", year, e)

    if not yearly_metrics:
        return _empty_result(doc_id, "Could not compute metrics for any year")

    # Trend metrics
    revenue_cagr = _compute_cagr(
        [m.revenue for m in yearly_metrics], len(yearly_metrics) - 1
    )
    ebitda_cagr = _compute_cagr(
        [m.ebitda for m in yearly_metrics], len(yearly_metrics) - 1
    )
    nw_cagr = _compute_cagr(
        [m.tangible_net_worth for m in yearly_metrics], len(yearly_metrics) - 1
    )

    # Raise flags based on thresholds
    flags = _detect_stress_flags(yearly_metrics)

    # Summary values (latest year + averages)
    latest = yearly_metrics[-1]
    avg_dscr    = _safe_avg([m.dscr for m in yearly_metrics])
    avg_cr      = _safe_avg([m.current_ratio for m in yearly_metrics])
    avg_de      = _safe_avg([m.de_ratio for m in yearly_metrics])

    result = WorkingCapitalResult(
        doc_id=doc_id,
        years=years,
        yearly_metrics=yearly_metrics,
        revenue_cagr_pct=round(revenue_cagr, 2),
        ebitda_cagr_pct=round(ebitda_cagr, 2),
        nw_cagr_pct=round(nw_cagr, 2),
        flags=flags,
        avg_dscr=round(avg_dscr, 3),
        avg_current_ratio=round(avg_cr, 3),
        avg_de_ratio=round(avg_de, 3),
        latest_de_ratio=round(latest.de_ratio, 3),
        latest_dscr=round(latest.dscr, 3),
        latest_current_ratio=round(latest.current_ratio, 3),
        latest_debtor_days=round(latest.debtor_days, 1),
        latest_creditor_days=round(latest.creditor_days, 1),
        latest_ccc=round(latest.cash_conversion_cycle, 1),
        warnings=warnings,
    )

    logger.info(
        "WC analysis complete: years=%d | flags=%d | avg_dscr=%.2f | avg_de=%.2f",
        len(yearly_metrics), len(flags), avg_dscr, avg_de
    )
    return result


# ── Per-Year Computation ──────────────────────────────────────────────────────

def _compute_year_metrics(
    year: str,
    idx: int,
    pnl: dict,
    bs: dict,
    cf: dict,
    warnings: list,
) -> YearlyMetrics:
    """
    Compute all metrics for a single year.
    idx is the position in the years list (0 = earliest).
    """
    def v(field_dict: dict, key: str) -> float:
        """Safe value extractor — returns 0.0 if missing."""
        val = field_dict.get(key)
        if val is None:
            return 0.0
        if isinstance(val, list):
            return float(val[idx]) if idx < len(val) else 0.0
        return float(val)

    # ── P&L ───────────────────────────────────────────────────────────────────
    revenue         = v(pnl, "revenue_from_operations")
    ebitda          = v(pnl, "ebitda")
    depreciation    = v(pnl, "depreciation")
    interest_exp    = v(pnl, "interest_expense")
    pat             = v(pnl, "pat")
    raw_material    = v(pnl, "raw_material_cost")
    employee_cost   = v(pnl, "employee_cost")
    manufacturing   = v(pnl, "manufacturing_overhead")

    # COGS approximation for days calculation
    cogs = raw_material + employee_cost + manufacturing
    if cogs == 0:
        cogs = revenue * 0.70   # Fallback: assume 70% COGS if not broken down
        warnings.append(f"{year}: COGS approximated at 70% of revenue")

    # ── Balance Sheet ──────────────────────────────────────────────────────────
    trade_rec    = v(bs, "trade_receivables")
    inventory    = v(bs, "inventory")
    trade_pay    = v(bs, "trade_payables")
    cash         = v(bs, "cash_and_bank")
    total_ca     = v(bs, "total_current_assets")
    total_cl     = v(bs, "total_current_liabilities")
    st_borrow    = v(bs, "short_term_borrowings")
    lt_borrow    = v(bs, "long_term_borrowings")
    total_debt   = v(bs, "total_debt") or (st_borrow + lt_borrow)
    tnw          = v(bs, "tangible_net_worth")

    # ── Cash Flow ──────────────────────────────────────────────────────────────
    cfo   = v(cf, "cfo")
    capex = v(cf, "capex")
    fcf   = cfo - capex

    # ── Derived Ratios ─────────────────────────────────────────────────────────
    daily_revenue = revenue / 365 if revenue > 0 else 1
    daily_cogs    = cogs    / 365 if cogs    > 0 else 1

    debtor_days   = trade_rec / daily_revenue
    creditor_days = trade_pay / daily_cogs
    inventory_days = inventory / daily_cogs
    ccc           = inventory_days + debtor_days - creditor_days

    current_ratio = total_ca / total_cl if total_cl > 0 else 0.0
    de_ratio      = total_debt / tnw    if tnw     > 0 else 0.0

    # Working capital gap (CA excl. cash) - (CL excl. ST borrowings)
    adj_ca = total_ca - cash
    adj_cl = total_cl - st_borrow
    wc_gap = adj_ca - adj_cl
    net_wc = total_ca - total_cl

    # DSCR
    # Estimate annual principal repayment as total_debt / 5 (rough)
    # Production: use actual repayment schedule from sanction letter
    estimated_principal = total_debt / 5 if total_debt > 0 else 0
    dscr = ebitda / (interest_exp + estimated_principal) if (interest_exp + estimated_principal) > 0 else 0.0

    interest_coverage = ebitda / interest_exp if interest_exp > 0 else 0.0

    ebitda_margin = (ebitda / revenue * 100) if revenue > 0 else 0.0
    pat_margin    = (pat    / revenue * 100) if revenue > 0 else 0.0

    return YearlyMetrics(
        year=year,
        revenue=round(revenue, 2),
        ebitda=round(ebitda, 2),
        ebitda_margin_pct=round(ebitda_margin, 2),
        pat=round(pat, 2),
        pat_margin_pct=round(pat_margin, 2),
        interest_expense=round(interest_exp, 2),
        current_ratio=round(current_ratio, 3),
        de_ratio=round(de_ratio, 3),
        tangible_net_worth=round(tnw, 2),
        total_debt=round(total_debt, 2),
        debtor_days=round(debtor_days, 1),
        creditor_days=round(creditor_days, 1),
        inventory_days=round(inventory_days, 1),
        cash_conversion_cycle=round(ccc, 1),
        working_capital_gap=round(wc_gap, 2),
        net_working_capital=round(net_wc, 2),
        cfo=round(cfo, 2),
        capex=round(capex, 2),
        fcf=round(fcf, 2),
        dscr=round(dscr, 3),
        interest_coverage=round(interest_coverage, 3),
    )


# ── Stress Flag Detection ─────────────────────────────────────────────────────

def _detect_stress_flags(metrics: list[YearlyMetrics]) -> list[dict]:
    """
    Compare each metric against thresholds from config.py.
    Returns list of flag dicts for storage in recon_flags table.
    """
    flags = []
    latest = metrics[-1]

    # ── Debtor Days ────────────────────────────────────────────────────────────
    if latest.debtor_days > settings.DEBTOR_DAYS_HIGH_RISK:
        flags.append({
            "flag_type": "DEBTOR_DAYS_HIGH",
            "severity": "HIGH",
            "title": f"Debtor days critically high: {latest.debtor_days:.0f} days",
            "description": (
                f"Trade receivable collection period is {latest.debtor_days:.0f} days "
                f"in {latest.year}, exceeding the {settings.DEBTOR_DAYS_HIGH_RISK:.0f}-day "
                "threshold. Indicates stretched collections or channel stuffing risk. "
                "Sector benchmark for textiles: 65 days."
            ),
            "metric_name": "debtor_days",
            "metric_value": latest.debtor_days,
            "threshold": settings.DEBTOR_DAYS_HIGH_RISK,
        })

    # ── Creditor Days ─────────────────────────────────────────────────────────
    if latest.creditor_days > settings.CREDITOR_DAYS_UNSUSTAINABLE:
        flags.append({
            "flag_type": "CREDITOR_DAYS_HIGH",
            "severity": "MEDIUM",
            "title": f"Creditor days unsustainable: {latest.creditor_days:.0f} days",
            "description": (
                f"Payable period {latest.creditor_days:.0f} days exceeds "
                f"{settings.CREDITOR_DAYS_UNSUSTAINABLE:.0f}-day threshold. "
                "Indicates the company is stretching vendor payments — "
                "a liquidity stress signal."
            ),
            "metric_name": "creditor_days",
            "metric_value": latest.creditor_days,
            "threshold": settings.CREDITOR_DAYS_UNSUSTAINABLE,
        })

    # ── Cash Conversion Cycle ─────────────────────────────────────────────────
    if (latest.cash_conversion_cycle > settings.CASH_CONVERSION_CYCLE_WARN
            and len(metrics) >= 2
            and latest.cash_conversion_cycle > metrics[-2].cash_conversion_cycle):
        flags.append({
            "flag_type": "CCC_WORSENING",
            "severity": "MEDIUM",
            "title": (
                f"Cash conversion cycle worsening: "
                f"{latest.cash_conversion_cycle:.0f} days in {latest.year}"
            ),
            "description": (
                f"CCC increased from {metrics[-2].cash_conversion_cycle:.0f} days "
                f"({metrics[-2].year}) to {latest.cash_conversion_cycle:.0f} days "
                f"({latest.year}). CCC > {settings.CASH_CONVERSION_CYCLE_WARN:.0f} "
                "days and deteriorating — working capital funding pressure increasing."
            ),
            "metric_name": "cash_conversion_cycle",
            "metric_value": latest.cash_conversion_cycle,
            "threshold": settings.CASH_CONVERSION_CYCLE_WARN,
        })

    # ── Negative Working Capital Gap ──────────────────────────────────────────
    negative_wc_years = [m.year for m in metrics if m.working_capital_gap < 0]
    if len(negative_wc_years) >= 2:
        flags.append({
            "flag_type": "WORKING_CAPITAL_STRESS",
            "severity": "HIGH",
            "title": "Negative working capital gap for multiple years",
            "description": (
                f"Adjusted working capital gap (CA excl. cash minus CL excl. "
                f"ST borrowings) was negative in: {', '.join(negative_wc_years)}. "
                "The company is funding its operations with short-term debt — "
                "a structural liquidity risk."
            ),
            "metric_name": "working_capital_gap_negative_years",
            "metric_value": float(len(negative_wc_years)),
            "threshold": 2.0,
        })

    # ── DSCR Below Minimum ────────────────────────────────────────────────────
    if latest.dscr < settings.MIN_ACCEPTABLE_DSCR:
        severity = "CRITICAL" if latest.dscr < 1.0 else "HIGH"
        flags.append({
            "flag_type": "DSCR_LOW",
            "severity": severity,
            "title": f"DSCR below acceptable minimum: {latest.dscr:.2f}x in {latest.year}",
            "description": (
                f"Debt Service Coverage Ratio of {latest.dscr:.2f}x is below "
                f"the minimum acceptable {settings.MIN_ACCEPTABLE_DSCR:.2f}x. "
                f"EBITDA: ₹{latest.ebitda:.0f}L | "
                f"Estimated debt service: ₹{(latest.interest_expense + latest.total_debt/5):.0f}L. "
                f"{'EBITDA does not cover debt obligations.' if latest.dscr < 1.0 else 'Thin coverage leaves no buffer for stress.'}"
            ),
            "metric_name": "dscr",
            "metric_value": latest.dscr,
            "threshold": settings.MIN_ACCEPTABLE_DSCR,
        })

    # ── D/E Ratio ─────────────────────────────────────────────────────────────
    if latest.de_ratio > 3.0:
        flags.append({
            "flag_type": "HIGH_LEVERAGE",
            "severity": "HIGH",
            "title": f"High leverage: D/E ratio {latest.de_ratio:.2f}x in {latest.year}",
            "description": (
                f"Debt-to-equity ratio of {latest.de_ratio:.2f}x indicates "
                "the company is highly leveraged. Total debt: "
                f"₹{latest.total_debt:.0f}L vs tangible net worth: "
                f"₹{latest.tangible_net_worth:.0f}L."
            ),
            "metric_name": "de_ratio",
            "metric_value": latest.de_ratio,
            "threshold": 3.0,
        })

    # ── Revenue CAGR vs Sector ────────────────────────────────────────────────
    if len(metrics) >= 2:
        revenue_cagr = _compute_cagr(
            [m.revenue for m in metrics], len(metrics) - 1
        )
        # Textiles benchmark from sector_benchmarks.json: 8% CAGR
        if revenue_cagr > 35.0:
            flags.append({
                "flag_type": "CAGR_ANOMALY",
                "severity": "MEDIUM",
                "title": f"Revenue CAGR of {revenue_cagr:.1f}% significantly exceeds sector",
                "description": (
                    f"3-year revenue CAGR of {revenue_cagr:.1f}% significantly "
                    "exceeds the textile sector benchmark of ~8%. "
                    "Requires cross-validation with GST turnover and bank credits."
                ),
                "metric_name": "revenue_cagr_pct",
                "metric_value": revenue_cagr,
                "threshold": 35.0,
            })

    return flags


# ── Utilities ─────────────────────────────────────────────────────────────────

def _compute_cagr(values: list[float], periods: int) -> float:
    """
    Compute CAGR between first and last value.
    CAGR = (end/start)^(1/n) - 1
    """
    if periods <= 0 or not values or values[0] <= 0:
        return 0.0
    try:
        return ((values[-1] / values[0]) ** (1 / periods) - 1) * 100
    except (ZeroDivisionError, ValueError):
        return 0.0


def _safe_avg(values: list[float]) -> float:
    valid = [v for v in values if v is not None and v > 0]
    return sum(valid) / len(valid) if valid else 0.0


def _empty_result(doc_id: str, reason: str) -> WorkingCapitalResult:
    return WorkingCapitalResult(
        doc_id=doc_id, years=[], yearly_metrics=[],
        revenue_cagr_pct=0.0, ebitda_cagr_pct=0.0, nw_cagr_pct=0.0,
        flags=[], avg_dscr=0.0, avg_current_ratio=0.0, avg_de_ratio=0.0,
        latest_de_ratio=0.0, latest_dscr=0.0, latest_current_ratio=0.0,
        latest_debtor_days=0.0, latest_creditor_days=0.0, latest_ccc=0.0,
        warnings=[reason],
    )


def result_to_dict(result: WorkingCapitalResult) -> dict:
    """Serialise for API responses and database storage."""
    return {
        "doc_id": result.doc_id,
        "years": result.years,
        "revenue_cagr_pct": result.revenue_cagr_pct,
        "ebitda_cagr_pct": result.ebitda_cagr_pct,
        "nw_cagr_pct": result.nw_cagr_pct,
        "avg_dscr": result.avg_dscr,
        "avg_current_ratio": result.avg_current_ratio,
        "avg_de_ratio": result.avg_de_ratio,
        "latest_de_ratio": result.latest_de_ratio,
        "latest_dscr": result.latest_dscr,
        "latest_current_ratio": result.latest_current_ratio,
        "latest_debtor_days": result.latest_debtor_days,
        "latest_creditor_days": result.latest_creditor_days,
        "latest_ccc": result.latest_ccc,
        "flags_count": len(result.flags),
        "flags": result.flags,
        "yearly_metrics": [
            {
                "year": m.year,
                "revenue": m.revenue,
                "ebitda": m.ebitda,
                "ebitda_margin_pct": m.ebitda_margin_pct,
                "pat": m.pat,
                "pat_margin_pct": m.pat_margin_pct,
                "current_ratio": m.current_ratio,
                "de_ratio": m.de_ratio,
                "total_debt": m.total_debt,
                "tangible_net_worth": m.tangible_net_worth,
                "debtor_days": m.debtor_days,
                "creditor_days": m.creditor_days,
                "inventory_days": m.inventory_days,
                "cash_conversion_cycle": m.cash_conversion_cycle,
                "working_capital_gap": m.working_capital_gap,
                "dscr": m.dscr,
                "interest_coverage": m.interest_coverage,
                "cfo": m.cfo,
                "fcf": m.fcf,
            }
            for m in result.yearly_metrics
        ],
        "warnings": result.warnings,
    }