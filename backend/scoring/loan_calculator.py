"""
scoring/loan_calculator.py
─────────────────────────────────────────────────────────────────────────────
Loan Sizing Engine for Intelli-Credit.

Computes three independent loan limits and returns the MINIMUM (most
conservative) as the recommended sanction amount:

  1. DSCR-based limit     — How much can earnings service?
     Max loan = (EBITDA - Operating Expenses) / (Annual Rate × 1/DSCR_min)
     Simplified: Loan = (EBITDA × DSCR adjustment) / annuity factor

  2. Collateral-based     — How much can security support?
     Max loan = Sum(FMV × LTV%) for each security item
     LTVs per config: land=60%, plant/machinery=50%, receivables=75%

  3. Drawing Power limit   — For working capital (CC limit only)
     DP = (Inventory × DP_margin) + (Receivables × DP_margin) - Creditors

Tenor: from loan request
Rate:  from five_cs_scorer recommended_rate_pct

Final recommended amount = min(DSCR limit, Collateral limit, Requested amount)
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from config import settings
from scoring.feature_engineer import FeatureSet
from scoring.five_cs_scorer import ScorecardResult


@dataclass
class LoanSizingResult:
    """Complete loan sizing output."""

    # Three independent limits (₹ Crores)
    limit_dscr_cr:          float   # DSCR-based maximum
    limit_collateral_cr:    float   # Collateral/LTV-based maximum
    limit_drawing_power_cr: float   # Drawing power (WC only)

    # Final recommendation
    requested_cr:           float
    recommended_cr:         float   # min(dscr, collateral, requested)
    recommended_tm_cr:      float   # Term loan portion
    recommended_cc_cr:      float   # CC/WC portion

    # Rate components
    base_rate_pct:          float
    risk_premium_pct:       float
    tenor_premium_pct:      float
    collateral_discount_pct:float
    recommended_rate_pct:   float

    # Tenor
    requested_tenor_yr:     int
    recommended_tenor_yr:   int

    # EMI / annual repayment (for display in CAM)
    annual_repayment_cr:    float
    emi_monthly_lakhs:      float

    # Binding constraint
    binding_constraint:     str     # "dscr" | "collateral" | "requested" | "policy"

    # Security cover ratio
    security_cover:         float   # FMV of collateral / loan requested

    # Explanation
    sizing_notes:           list[str]


def compute_loan_sizing(
    scorecard:      ScorecardResult,
    features:       FeatureSet,
    financial_data: dict,
) -> LoanSizingResult:
    """
    Main entry point. Computes loan sizing from scorecard + features.
    Called from score_routes.py after compute_score().
    """
    logger.info("Computing loan sizing")

    notes = []
    lr    = financial_data.get("loan_request", {})

    requested_cr    = float(lr.get("total_requested_cr", 0))
    requested_tenor = int(lr.get("tenor_years", 7))
    fin             = financial_data.get("financials", {})
    pnl             = fin.get("profit_and_loss", {})
    bs              = fin.get("balance_sheet", {})

    def latest(d: dict, key: str, fallback: float = 0.0) -> float:
        v = d.get(key, fallback)
        if isinstance(v, list):
            return float(v[-1]) if v else fallback
        return float(v) if v is not None else fallback

    rate_pct = scorecard.recommended_rate_pct
    if rate_pct == 0.0:
        rate_pct = settings.RBI_REPO_RATE + settings.NBFC_BASE_SPREAD + 3.5
        notes.append("Rate defaulted: REJECT case — using indicative rate for sizing only")

    # ── 1. DSCR-Based Limit ───────────────────────────────────────────────────
    ebitda    = latest(pnl, "ebitda")
    int_exist = latest(pnl, "interest_expense")   # Existing interest

    # Available surplus for new debt service
    # Surplus = EBITDA × (1 - 1/DSCR_min) adjusted for existing obligations
    # Simplified: max_new_ds = (EBITDA / DSCR_min) - existing_interest
    max_new_ds_annual = max(0.0, (ebitda / settings.MIN_ACCEPTABLE_DSCR) - int_exist)

    # Convert annual debt service to loan amount via annuity formula
    # Loan = DS × [(1-(1+r)^-n) / r]  where r = annual rate, n = tenor
    r = rate_pct / 100
    n = requested_tenor

    if r > 0 and n > 0:
        annuity_factor = (1 - (1 + r) ** (-n)) / r
        limit_dscr_cr  = max(0.0, max_new_ds_annual * annuity_factor / 100)
        # Convert lakhs to crores (financial data in lakhs)
    else:
        limit_dscr_cr = 0.0
        notes.append("DSCR limit: could not compute (zero rate or tenor)")

    # ── 2. Collateral-Based Limit ─────────────────────────────────────────────
    security   = lr.get("security_proposed", [])
    limit_coll = 0.0

    ltv_map = {
        "land":              settings.LTV_LAND,
        "land_and_building": settings.LTV_LAND,
        "building":          settings.LTV_LAND,
        "plant_machinery":   settings.LTV_PLANT_MACHINERY,
        "plant":             settings.LTV_PLANT_MACHINERY,
        "machinery":         settings.LTV_PLANT_MACHINERY,
        "receivables":       settings.LTV_RECEIVABLES,
        "book_debts":        settings.LTV_RECEIVABLES,
    }

    for item in security:
        fmv_lakhs  = float(item.get("fmv_lakhs", 0) or 0)
        asset_type = item.get("asset_type", "").lower().replace(" ", "_")
        ltv        = ltv_map.get(asset_type, 0.50)  # Default 50% LTV

        # Deduct existing charges
        existing_charge_lakhs = float(item.get("existing_charge_lakhs", 0) or 0)
        net_fmv = max(0.0, fmv_lakhs - existing_charge_lakhs)

        eligible_cr = (net_fmv * ltv) / 100   # Convert lakhs→crores
        limit_coll += eligible_cr

        notes.append(
            f"Security: {item.get('description','asset')} — "
            f"FMV ₹{fmv_lakhs:.0f}L × LTV {ltv*100:.0f}% "
            f"= ₹{eligible_cr:.2f}Cr eligible"
        )

    # Fallback: use pre-computed eligible collateral from loan_request
    if limit_coll == 0.0:
        eligible_lakhs = float(lr.get("total_eligible_collateral_lakhs", 0) or 0)
        limit_coll     = eligible_lakhs / 100
        if limit_coll > 0:
            notes.append(f"Collateral limit from pre-computed eligible: ₹{limit_coll:.2f}Cr")

    # ── 3. Drawing Power (CC limit only) ─────────────────────────────────────
    inventory    = latest(bs, "inventory")
    receivables  = latest(bs, "trade_receivables")
    payables     = latest(bs, "trade_payables")
    dp_margin    = settings.DRAWING_POWER_MARGIN

    dp_lakhs = max(0.0,
        (inventory * dp_margin) + (receivables * dp_margin) - payables
    )
    limit_dp_cr = dp_lakhs / 100

    # ── 4. Final Recommendation ────────────────────────────────────────────────
    # For REJECT: recommended = 0
    if scorecard.decision == "REJECT":
        recommended_cr = 0.0
        binding        = "decision_reject"
        notes.append("Loan amount: ₹0 — case is REJECT")
    else:
        limits = {
            "dscr":       limit_dscr_cr,
            "collateral": limit_coll,
            "requested":  requested_cr,
            "policy":     settings.POLICY_MAX_SINGLE_BORROWER_CR,
        }
        # Remove zero limits (means data was missing)
        valid_limits = {k: v for k, v in limits.items() if v > 0}
        if valid_limits:
            binding         = min(valid_limits, key=valid_limits.get)
            recommended_cr  = round(min(valid_limits.values()), 2)
        else:
            recommended_cr = 0.0
            binding        = "insufficient_data"

    # Split into TL + CC
    cc_requested  = float(lr.get("cc_requested_cr", 0) or 0)
    tl_requested  = requested_cr - cc_requested
    if requested_cr > 0:
        tl_ratio      = tl_requested / requested_cr
        cc_ratio      = cc_requested / requested_cr
        recommended_tl = round(recommended_cr * tl_ratio, 2)
        recommended_cc = round(recommended_cr * cc_ratio, 2)
    else:
        recommended_tl = recommended_cr
        recommended_cc = 0.0

    # Cap CC at drawing power
    if recommended_cc > limit_dp_cr > 0:
        recommended_cc = round(limit_dp_cr, 2)
        notes.append(f"CC limit capped at drawing power: ₹{recommended_cc:.2f}Cr")

    # ── 5. Rate Computation ────────────────────────────────────────────────────
    base_rate       = settings.RBI_REPO_RATE + settings.NBFC_BASE_SPREAD
    risk_premium    = scorecard.interest_premium_bps / 100
    tenor_premium   = (settings.LONG_TENOR_PREMIUM_BPS / 100
                       if requested_tenor > 5 else 0.0)
    coll_discount   = (settings.STRONG_COLLATERAL_DISCOUNT_BPS / 100
                       if features.security_cover >= settings.STRONG_COLLATERAL_THRESHOLD
                       else 0.0)
    final_rate      = round(base_rate + risk_premium + tenor_premium - coll_discount, 2)

    # ── 6. Repayment Schedule ─────────────────────────────────────────────────
    annual_repayment     = 0.0
    emi_monthly          = 0.0
    recommended_tenor_yr = requested_tenor

    if recommended_tl > 0 and final_rate > 0 and recommended_tenor_yr > 0:
        r_monthly      = (final_rate / 100) / 12
        n_months       = requested_tenor * 12
        recommended_cr_lakhs = recommended_tl * 100   # Convert to lakhs

        emi_lakhs = (
            recommended_cr_lakhs * r_monthly * (1 + r_monthly) ** n_months
        ) / ((1 + r_monthly) ** n_months - 1)

        emi_monthly      = round(emi_lakhs, 2)
        annual_repayment = round((emi_lakhs * 12) / 100, 2)  # Crores
    else:
        notes.append("EMI not computed — zero loan or rate")


    result = LoanSizingResult(
        limit_dscr_cr=          round(limit_dscr_cr, 2),
        limit_collateral_cr=    round(limit_coll, 2),
        limit_drawing_power_cr= round(limit_dp_cr, 2),
        requested_cr=           round(requested_cr, 2),
        recommended_cr=         recommended_cr,
        recommended_tm_cr=      recommended_tl,
        recommended_cc_cr=      recommended_cc,
        base_rate_pct=          round(base_rate, 2),
        risk_premium_pct=       round(risk_premium, 2),
        tenor_premium_pct=      round(tenor_premium, 2),
        collateral_discount_pct=round(coll_discount, 2),
        recommended_rate_pct=   final_rate,
        requested_tenor_yr=     requested_tenor,
        recommended_tenor_yr=   recommended_tenor_yr,
        annual_repayment_cr=    annual_repayment,
        emi_monthly_lakhs=      emi_monthly,
        binding_constraint=     binding,
        security_cover=         round(features.security_cover, 2),
        sizing_notes=           notes,
    )

    logger.info(
        "Loan sizing: dscr_lim=₹%.2fCr coll_lim=₹%.2fCr "
        "recommended=₹%.2fCr binding=%s rate=%.2f%%",
        limit_dscr_cr, limit_coll, recommended_cr, binding, final_rate
    )
    return result


def sizing_to_dict(result: LoanSizingResult) -> dict:
    """Serialise LoanSizingResult for API responses."""
    return {
        "limits": {
            "dscr_based_cr":       result.limit_dscr_cr,
            "collateral_based_cr": result.limit_collateral_cr,
            "drawing_power_cr":    result.limit_drawing_power_cr,
            "requested_cr":        result.requested_cr,
        },
        "recommendation": {
            "recommended_cr":    result.recommended_cr,
            "term_loan_cr":      result.recommended_tm_cr,
            "cc_limit_cr":       result.recommended_cc_cr,
            "binding_constraint":result.binding_constraint,
            "security_cover":    result.security_cover,
        },
        "rate": {
            "base_rate_pct":          result.base_rate_pct,
            "risk_premium_pct":       result.risk_premium_pct,
            "tenor_premium_pct":      result.tenor_premium_pct,
            "collateral_discount_pct":result.collateral_discount_pct,
            "recommended_rate_pct":   result.recommended_rate_pct,
        },
        "repayment": {
            "tenor_years":         result.recommended_tenor_yr,
            "emi_monthly_lakhs":   result.emi_monthly_lakhs,
            "annual_repayment_cr": result.annual_repayment_cr,
        },
        "sizing_notes": result.sizing_notes,
    }