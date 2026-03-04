"""
scoring/feature_engineer.py
─────────────────────────────────────────────────────────────────────────────
Feature Engineering for the Five Cs Scoring Engine.

Takes all raw outputs from Steps 2-3 and computes the 16 clean numeric
features that feed directly into five_cs_scorer.py.

16 Features across Five Cs:
  CHARACTER (4 features):
    1.  litigation_risk         — From research cache (eCourts, news risk delta)
    2.  promoter_track_record   — From pledge % + directorship concerns
    3.  gst_compliance          — From GST reconciliation flags (ITC overclaim etc.)
    4.  management_quality      — From related_party_detector score

  CAPACITY (4 features):
    5.  dscr                    — From working_capital_analyzer
    6.  ebitda_margin_trend     — YoY EBITDA margin improvement/deterioration
    7.  revenue_cagr_vs_sector  — Revenue CAGR vs sector benchmark
    8.  plant_utilization       — From financial data or default estimate

  CAPITAL (3 features):
    9.  de_ratio                — Total debt / Tangible net worth (latest year)
    10. net_worth_trend         — Net worth CAGR (growing = good)
    11. promoter_equity_pct     — Promoter holding % (skin in the game)

  COLLATERAL (2 features):
    12. security_cover          — FMV of collateral / loan requested
    13. collateral_encumbrance  — Existing charges on proposed security

  CONDITIONS (3 features):
    14. sector_outlook          — Sector cyclicality + RBI watch status
    15. customer_concentration  — Top customer concentration risk
    16. regulatory_environment  — Regulatory headwinds in sector

All values are normalised to 0.0–1.0 range where 1.0 = best possible.
five_cs_scorer.py converts these to points using the scoring formulas.

DETERMINISTIC — no LLM used here.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from config import settings, BENCHMARKS_PATH


# ── FeatureSet Dataclass ───────────────────────────────────────────────────────

@dataclass
class FeatureSet:
    """
    The 16 normalised feature values fed into the scoring engine.
    Each value is on a 0.0–1.0 scale where 1.0 = maximum score.

    Also carries raw values for display in the audit trail and waterfall chart.
    """
    # ── CHARACTER ─────────────────────────────────────────────────────────────
    litigation_risk: float          # 0=critical litigation, 1=clean
    promoter_track_record: float    # 0=heavy pledge+concerns, 1=clean promoter
    gst_compliance: float           # 0=multiple violations, 1=fully compliant
    management_quality: float       # 0-1 scaled from 0-15 raw score

    # ── CAPACITY ──────────────────────────────────────────────────────────────
    dscr: float                     # Raw DSCR value (scorer applies formula)
    ebitda_margin_trend: float      # 0=declining sharply, 1=improving strongly
    revenue_cagr_vs_sector: float   # 0=far below sector, 1=far above sector
    plant_utilization: float        # 0=<30%, 1=90%+

    # ── CAPITAL ───────────────────────────────────────────────────────────────
    de_ratio: float                 # Raw D/E value (scorer applies formula)
    net_worth_trend: float          # 0=eroding, 1=growing strongly
    promoter_equity_pct: float      # Raw promoter holding % (0-100)

    # ── COLLATERAL ────────────────────────────────────────────────────────────
    security_cover: float           # FMV of collateral / loan amount
    collateral_encumbrance: float   # 0=fully encumbered, 1=clean title

    # ── CONDITIONS ────────────────────────────────────────────────────────────
    sector_outlook: float           # 0=RBI watch/high cyclicality, 1=stable
    customer_concentration: float   # 0=single customer, 1=diversified
    regulatory_environment: float   # 0=heavy headwinds, 1=tailwinds

    # ── Raw values for waterfall chart / audit trail ───────────────────────────
    raw: dict = field(default_factory=dict)

    # ── Validation flags ──────────────────────────────────────────────────────
    missing_fields: list[str] = field(default_factory=list)
    assumptions_made: list[str] = field(default_factory=list)


# ── Main Feature Engineering Function ────────────────────────────────────────

def engineer_features(
    financial_data: dict,
    wc_analysis: dict,
    rp_analysis: dict,
    gst_recon: dict,
    research_cache: dict,
    loan_request: dict | None = None,
) -> FeatureSet:
    """
    Main entry point. Takes all Step 2-3 outputs and produces a clean FeatureSet.

    Args:
        financial_data:  From financial_data.json or extracted documents
        wc_analysis:     From working_capital_analyzer.result_to_dict()
        rp_analysis:     From related_party_detector.result_to_dict()
        gst_recon:       From gst_reconciler.result_to_dict()
        research_cache:  From research_cache.json
        loan_request:    Loan amount/collateral details (from financial_data)
    """
    logger.info("Engineering features from Step 2-3 outputs")

    missing     = []
    assumptions = []
    raw         = {}

    # Load sector benchmarks
    benchmarks = _load_benchmarks()
    sector     = financial_data.get("company", {}).get("sector", "generic")
    benchmark  = benchmarks.get(sector, benchmarks.get("generic", {}))

    fin   = financial_data.get("financials", {})
    pnl   = fin.get("profit_and_loss", {})
    bs    = fin.get("balance_sheet", {})
    years = fin.get("years", [])

    # ── Helper: get latest year value ─────────────────────────────────────────
    def latest(d: dict, key: str, fallback: float = 0.0) -> float:
        val = d.get(key, fallback)
        if isinstance(val, list):
            return float(val[-1]) if val else fallback
        return float(val) if val is not None else fallback

    # ═══════════════════════════════════════════════════════════════════════════
    # CHARACTER FEATURES
    # ═══════════════════════════════════════════════════════════════════════════

    # ── 1. Litigation Risk (0=critical, 1=clean) ──────────────────────────────
    # Source: research_cache eCourts + news risk delta
    litigation_risk, litigation_raw = _compute_litigation_risk(research_cache)
    raw["litigation_risk_raw"] = litigation_raw

    # ── 2. Promoter Track Record (0=high risk, 1=excellent) ───────────────────
    pledge_pct   = rp_analysis.get("total_promoter_pledged_pct", 0.0)
    dir_concern  = any(
        p.get("directorship_concern", False)
        for p in rp_analysis.get("promoter_profiles", [])
    )
    promoter_tr  = _compute_promoter_track_record(pledge_pct, dir_concern, research_cache)
    raw["promoter_pledge_pct"]       = pledge_pct
    raw["directorship_concern"]      = dir_concern

    # ── 3. GST Compliance (0=multiple violations, 1=fully compliant) ──────────
    gst_compliance, gst_raw = _compute_gst_compliance(gst_recon)
    raw["gst_flags_count"]  = gst_raw["flags_count"]
    raw["gst_itc_overclaim"] = gst_raw["has_itc_overclaim"]

    # ── 4. Management Quality (0-1 scaled from 0-15) ──────────────────────────
    mgmt_raw   = rp_analysis.get("management_quality_score", 10)
    mgmt_score = mgmt_raw / 15.0
    raw["management_quality_raw_score"] = mgmt_raw

    # ═══════════════════════════════════════════════════════════════════════════
    # CAPACITY FEATURES
    # ═══════════════════════════════════════════════════════════════════════════

    # ── 5. DSCR (raw value — scorer applies piecewise formula) ────────────────
    dscr_val = wc_analysis.get("latest_dscr", 0.0)
    if dscr_val == 0.0:
        # Compute from raw financials as fallback
        ebitda    = latest(pnl, "ebitda")
        int_exp   = latest(pnl, "interest_expense")
        total_dbt = latest(bs, "total_debt")
        principal = total_dbt / 5 if total_dbt > 0 else 0
        dscr_val  = ebitda / (int_exp + principal) if (int_exp + principal) > 0 else 0.0
        assumptions.append("DSCR computed from raw financials (principal estimated as debt/5)")
    raw["dscr_value"] = dscr_val

    # ── 6. EBITDA Margin Trend (0=declining, 1=improving) ────────────────────
    ebitda_margins = pnl.get("ebitda_margin_pct", [])
    ebitda_trend, ebitda_trend_raw = _compute_margin_trend(
        ebitda_margins, benchmark.get("typical_ebitda_margin_pct", 14.0)
    )
    raw["ebitda_margins"] = ebitda_margins
    raw["ebitda_trend_direction"] = ebitda_trend_raw

    # ── 7. Revenue CAGR vs Sector (0=far below, 1=at/above sector) ───────────
    rev_cagr    = wc_analysis.get("revenue_cagr_pct", 0.0)
    sector_cagr = benchmark.get("typical_revenue_cagr_3yr_pct", 8.0)
    cagr_ratio  = rev_cagr / sector_cagr if sector_cagr > 0 else 0.5
    rev_cagr_score = min(1.0, max(0.0, cagr_ratio * 0.5))  # Scaled: at sector = 0.5
    raw["revenue_cagr_pct"]   = rev_cagr
    raw["sector_cagr_pct"]    = sector_cagr
    raw["cagr_ratio"]         = round(cagr_ratio, 3)

    # ── 8. Plant Utilization (0=<30%, 1=90%+) ────────────────────────────────
    plant_util, plant_raw = _estimate_plant_utilization(pnl, financial_data, assumptions)
    raw["plant_utilization_pct"] = plant_raw

    # ═══════════════════════════════════════════════════════════════════════════
    # CAPITAL FEATURES
    # ═══════════════════════════════════════════════════════════════════════════

    # ── 9. D/E Ratio (raw value — scorer applies stepped formula) ─────────────
    de_val = wc_analysis.get("latest_de_ratio", 0.0)
    if de_val == 0.0:
        total_dbt = latest(bs, "total_debt")
        tnw       = latest(bs, "tangible_net_worth")
        de_val    = total_dbt / tnw if tnw > 0 else 99.0
        assumptions.append("D/E computed directly from balance sheet")
    raw["de_ratio_value"] = de_val

    # ── 10. Net Worth Trend (0=eroding, 1=growing strongly) ──────────────────
    nw_cagr     = wc_analysis.get("nw_cagr_pct", 0.0)
    nw_trend    = _compute_nw_trend(nw_cagr)
    raw["nw_cagr_pct"] = nw_cagr

    # ── 11. Promoter Equity % (raw %) ─────────────────────────────────────────
    promo_pct = financial_data.get(
        "shareholding_pattern", {}
    ).get("promoter_total_pct", 0.0)
    if promo_pct == 0.0:
        promo_pct = sum(
            p.get("shareholding_pct", 0)
            for p in financial_data.get("promoters", [])
        )
        if promo_pct > 0:
            assumptions.append("Promoter equity summed from individual promoter holdings")
    raw["promoter_equity_pct"] = promo_pct

    # ═══════════════════════════════════════════════════════════════════════════
    # COLLATERAL FEATURES
    # ═══════════════════════════════════════════════════════════════════════════

    # ── 12. Security Cover (FMV of collateral / loan requested) ──────────────
    lr = loan_request or financial_data.get("loan_request", {})
    sec_cover, sec_raw = _compute_security_cover(lr)
    raw["security_cover_value"]    = sec_raw["security_cover"]
    raw["collateral_fmv_cr"]       = sec_raw["collateral_fmv_cr"]
    raw["loan_requested_cr"]       = sec_raw["loan_requested_cr"]

    # ── 13. Collateral Encumbrance (0=fully charged, 1=free) ─────────────────
    encumbrance, enc_raw = _compute_encumbrance(research_cache, lr)
    raw["encumbrance_flag"]        = enc_raw

    # ═══════════════════════════════════════════════════════════════════════════
    # CONDITIONS FEATURES
    # ═══════════════════════════════════════════════════════════════════════════

    # ── 14. Sector Outlook (0=RBI watch/high cyclicality, 1=stable/positive) ──
    sect_out = _compute_sector_outlook(benchmark, research_cache)
    raw["sector_rbi_watch"]        = benchmark.get("rbi_sector_watch", False)
    raw["sector_cyclicality"]      = benchmark.get("cyclicality", "medium")

    # ── 15. Customer Concentration (0=single, 1=diversified) ─────────────────
    cust_conc, cust_raw = _compute_customer_concentration(
        financial_data, rp_analysis
    )
    raw["customer_concentration_score"] = cust_raw

    # ── 16. Regulatory Environment (0=heavy headwinds, 1=tailwinds) ──────────
    reg_env = _compute_regulatory_environment(benchmark, research_cache)
    raw["regulatory_environment_score"] = reg_env

    # ── Validation ────────────────────────────────────────────────────────────
    critical_fields = {
        "dscr": dscr_val, "de_ratio": de_val,
        "security_cover": sec_cover, "promoter_equity_pct": promo_pct
    }
    for fname, fval in critical_fields.items():
        if fval == 0.0:
            missing.append(fname)

    fs = FeatureSet(
        # CHARACTER
        litigation_risk        = round(litigation_risk,  4),
        promoter_track_record  = round(promoter_tr,      4),
        gst_compliance         = round(gst_compliance,   4),
        management_quality     = round(mgmt_score,       4),
        # CAPACITY
        dscr                   = round(dscr_val,         4),
        ebitda_margin_trend    = round(ebitda_trend,     4),
        revenue_cagr_vs_sector = round(rev_cagr_score,  4),
        plant_utilization      = round(plant_util,       4),
        # CAPITAL
        de_ratio               = round(de_val,           4),
        net_worth_trend        = round(nw_trend,         4),
        promoter_equity_pct    = round(promo_pct,        4),
        # COLLATERAL
        security_cover         = round(sec_cover,        4),
        collateral_encumbrance = round(encumbrance,      4),
        # CONDITIONS
        sector_outlook         = round(sect_out,         4),
        customer_concentration = round(cust_conc,        4),
        regulatory_environment = round(reg_env,          4),
        # Meta
        raw                    = raw,
        missing_fields         = missing,
        assumptions_made       = assumptions,
    )

    logger.info(
        "Features engineered: dscr=%.3f de=%.2f sec_cover=%.2f "
        "lit_risk=%.2f pledge=%.1f%% mgmt=%d/15",
        dscr_val, de_val, sec_cover,
        litigation_risk, pledge_pct, mgmt_raw
    )
    return fs


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE COMPUTATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_litigation_risk(research_cache: dict) -> tuple[float, dict]:
    """
    Score 0 (critical litigation) → 1 (completely clean).

    Sources (highest severity wins):
      - eCourts IBC/NCLT petition (tier 1) → max deduction
      - DRT/SARFAESI (tier 1) → severe deduction
      - Civil suits (tier 2-3) → moderate deduction
      - Positive news → small boost
    """
    total_delta = 0

    for finding in research_cache.get("ecourts_findings", []):
        total_delta += finding.get("risk_score_delta", 0)

    for article in research_cache.get("news_articles", []):
        total_delta += article.get("risk_score_delta", 0)

    # Normalise: 0 delta = score 1.0; -100 delta = score 0.0
    # Clamp total_delta between -100 and +20
    clamped = max(-100, min(20, total_delta))
    score = (clamped + 100) / 120   # Maps [-100,+20] → [0,1]

    raw = {
        "total_risk_delta": total_delta,
        "ecourts_count": len(research_cache.get("ecourts_findings", [])),
        "flagged_articles": sum(
            1 for a in research_cache.get("news_articles", [])
            if a.get("risk_tier") in (1, 2)
        ),
    }
    return round(score, 4), raw


def _compute_promoter_track_record(
    pledge_pct: float,
    directorship_concern: bool,
    research_cache: dict,
) -> float:
    """
    Score 0 (very high risk) → 1 (excellent promoter profile).

    Deductions:
      - Pledge ≥ 75%: -0.40
      - Pledge ≥ 50%: -0.20
      - Pledge ≥ 25%: -0.10
      - Directorship concern: -0.15
      - Promoter selling shares (news): -0.10
    Additions:
      - Pledge released (news): +0.10
      - Long tenure (>10 years): +0.05
    """
    score = 1.0

    if pledge_pct >= settings.PROMOTER_PLEDGE_HIGH_PCT:
        score -= 0.40
    elif pledge_pct >= settings.PROMOTER_PLEDGE_WARN_PCT:
        score -= 0.20
    elif pledge_pct >= 25.0:
        score -= 0.10

    if directorship_concern:
        score -= 0.15

    # Scan news for promoter-specific signals
    for article in research_cache.get("news_articles", []):
        title_lower = article.get("title", "").lower()
        if "promoter" in title_lower and "selling" in title_lower:
            score -= 0.10
        if "pledge released" in title_lower or "stake increased" in title_lower:
            score += 0.10

    return round(max(0.0, min(1.0, score)), 4)


def _compute_gst_compliance(gst_recon: dict) -> tuple[float, dict]:
    """
    Score 0 (serious violations) → 1 (fully compliant).

    Deductions per flag severity:
      - ITC_OVERCLAIM (violates CGST 110% rule): -0.35
      - SUPPLIER_NONCOMPLIANCE HIGH: -0.20
      - SUPPLIER_NONCOMPLIANCE MEDIUM: -0.10
      - REVENUE_INFLATION: -0.15
      - CIRCULAR_TRADING: -0.50 (CRITICAL)
    """
    score = 1.0
    has_itc_overclaim = False
    flags_count = 0

    deductions = {
        "ITC_OVERCLAIM":          {"CRITICAL": 0.35, "HIGH": 0.35, "MEDIUM": 0.20},
        "SUPPLIER_NONCOMPLIANCE": {"HIGH": 0.20, "MEDIUM": 0.10, "LOW": 0.05},
        "REVENUE_INFLATION":      {"CRITICAL": 0.25, "HIGH": 0.20, "MEDIUM": 0.15},
        "CIRCULAR_TRADING":       {"CRITICAL": 0.50, "HIGH": 0.40},
    }

    for flag in gst_recon.get("flags", []):
        flag_type = flag.get("flag_type", "")
        severity  = flag.get("severity", "MEDIUM")
        flags_count += 1

        if flag_type == "ITC_OVERCLAIM":
            has_itc_overclaim = True

        deduction = deductions.get(flag_type, {}).get(severity, 0.10)
        score -= deduction

    raw = {
        "flags_count":     flags_count,
        "has_itc_overclaim": has_itc_overclaim,
        "raw_score":       score,
    }
    return round(max(0.0, min(1.0, score)), 4), raw


def _compute_margin_trend(
    ebitda_margins: list,
    sector_typical: float,
) -> tuple[float, str]:
    """
    Score 0 (declining + below sector) → 1 (improving + above sector).

    Components:
      - Direction trend: improving YoY = +0.4, flat = +0.2, declining = 0
      - Level vs sector: above typical = +0.4, at sector = +0.2, below = 0
      - Consistency (no single-year collapse): +0.2
    """
    if not ebitda_margins or len(ebitda_margins) < 2:
        return 0.5, "insufficient_data"

    margins = [float(m) for m in ebitda_margins]
    latest  = margins[-1]
    first   = margins[0]
    mid     = margins[len(margins) // 2]

    # Direction
    if latest > mid > first:
        direction_score = 0.4
        direction       = "improving"
    elif latest >= mid:
        direction_score = 0.2
        direction       = "stable"
    else:
        direction_score = 0.0
        direction       = "declining"

    # Level vs sector
    if latest > sector_typical * 1.10:
        level_score = 0.4
    elif latest >= sector_typical * 0.90:
        level_score = 0.2
    else:
        level_score = 0.0

    # Consistency: no single year collapse > 3 percentage points
    max_drop = max(
        (margins[i] - margins[i+1] for i in range(len(margins)-1)), default=0
    )
    consistency = 0.2 if max_drop < 3.0 else 0.0

    return round(direction_score + level_score + consistency, 4), direction


def _estimate_plant_utilization(
    pnl: dict,
    financial_data: dict,
    assumptions: list,
) -> tuple[float, float]:
    """
    Estimate plant utilization as capacity utilization proxy.
    Primary: use explicit utilization from financial data if available.
    Fallback: estimate from revenue trend vs asset base.

    Returns (0-1 score, raw %)
    """
    # Check if explicit utilization is in data
    util_pct = financial_data.get("plant_utilization_pct")
    if util_pct:
        raw_pct = float(util_pct)
        score   = min(1.0, raw_pct / 90.0)   # 90%+ = 1.0
        return round(score, 4), raw_pct

    # Fallback: use revenue CAGR as proxy
    # Positive CAGR → capacity being utilised
    rev_list = pnl.get("revenue_from_operations", [])
    if len(rev_list) >= 2:
        rev_cagr = ((float(rev_list[-1]) / float(rev_list[0])) ** 
                    (1 / (len(rev_list)-1)) - 1) * 100
        # Map CAGR to utilization proxy
        # > 10% CAGR → assume ~80% utilization
        # 5-10%      → assume ~70%
        # 0-5%       → assume ~60%
        # Negative   → assume ~45%
        if rev_cagr > 10:
            util_pct = 80.0
        elif rev_cagr > 5:
            util_pct = 70.0
        elif rev_cagr > 0:
            util_pct = 60.0
        else:
            util_pct = 45.0
        assumptions.append(
            f"Plant utilization estimated from revenue CAGR ({rev_cagr:.1f}%) "
            f"as {util_pct:.0f}%"
        )
    else:
        util_pct = 60.0
        assumptions.append("Plant utilization defaulted to 60% (insufficient data)")

    score = min(1.0, util_pct / 90.0)
    return round(score, 4), util_pct


def _compute_nw_trend(nw_cagr_pct: float) -> float:
    """
    Score net worth trend 0 (eroding) → 1 (growing strongly).

    CAGR > 12%  → 1.0
    CAGR 8-12%  → 0.8
    CAGR 4-8%   → 0.6
    CAGR 0-4%   → 0.4
    CAGR < 0%   → 0.0
    """
    if nw_cagr_pct >= 12.0:
        return 1.0
    if nw_cagr_pct >= 8.0:
        return 0.8
    if nw_cagr_pct >= 4.0:
        return 0.6
    if nw_cagr_pct >= 0.0:
        return 0.4
    return 0.0


def _compute_security_cover(loan_request: dict) -> tuple[float, dict]:
    """
    Compute security cover = FMV of eligible collateral / total loan requested.

    Uses LTV-adjusted values from the loan_request section.
    """
    security = loan_request.get("security_proposed", [])
    total_eligible_cr = loan_request.get("total_eligible_collateral_cr", 0.0)
    total_requested_cr = loan_request.get("total_requested_cr", 0.0)

    if total_eligible_cr == 0.0 and security:
        # Compute from individual security items
        for s in security:
            fmv_lakhs = s.get("fmv_lakhs", 0) or 0
            ltv       = s.get("ltv", 0.5) or 0.5
            total_eligible_cr += (fmv_lakhs * ltv) / 100  # Convert lakhs to crores

    # Fallback: look for eligible_collateral_lakhs
    if total_eligible_cr == 0.0:
        eligible_lakhs = loan_request.get("total_eligible_collateral_lakhs", 0)
        total_eligible_cr = float(eligible_lakhs) / 100

    cover = total_eligible_cr / total_requested_cr if total_requested_cr > 0 else 0.0

    raw = {
        "security_cover":     round(cover, 3),
        "collateral_fmv_cr":  round(total_eligible_cr, 2),
        "loan_requested_cr":  round(total_requested_cr, 2),
    }
    return round(cover, 4), raw


def _compute_encumbrance(research_cache: dict, loan_request: dict) -> tuple[float, str]:
    """
    Score collateral encumbrance 0 (fully charged) → 1 (free and clear).

    Checks:
      - MCA CHG-1 filings for existing charges on proposed assets
      - Security type: second charge = 0.3, first charge = 0.7, free = 1.0
    """
    score = 1.0
    flag  = "clean"

    # Check MCA filings for existing charges
    mca_filings = research_cache.get("mca_filings", [])
    existing_charges = [
        m for m in mca_filings
        if m.get("form") in ("CHG-1", "CHG-9") and m.get("status") == "Subsisting"
    ]

    if existing_charges:
        flagged = [m for m in existing_charges if m.get("risk_flag", False)]
        if flagged:
            # Risk-flagged charge (e.g., existing second charge on proposed security)
            score = 0.40
            flag  = f"existing_charge_{flagged[0].get('charge_holder','unknown')}"
        else:
            # Charges exist but not on proposed security
            score = 0.70
            flag  = "existing_charge_other_assets"

    return round(score, 4), flag


def _compute_sector_outlook(benchmark: dict, research_cache: dict) -> float:
    """
    Score sector outlook 0 (RBI watch + high cyclicality) → 1 (stable + positive).
    """
    score = 0.5   # Base

    # RBI sector watch → deduction
    if benchmark.get("rbi_sector_watch", False):
        score -= 0.20

    # Cyclicality
    cyclicality = benchmark.get("cyclicality", "medium")
    if cyclicality == "low":
        score += 0.20
    elif cyclicality == "high":
        score -= 0.15

    # Negative sector news from research
    sector_neg = sum(
        1 for a in research_cache.get("news_articles", [])
        if a.get("risk_tier") == 3
        and "sector" in a.get("title", "").lower()
    )
    score -= sector_neg * 0.05

    return round(max(0.0, min(1.0, score)), 4)


def _compute_customer_concentration(
    financial_data: dict,
    rp_analysis: dict,
) -> tuple[float, str]:
    """
    Estimate customer concentration risk 0 (single customer) → 1 (diversified).

    Uses related party revenue % as a proxy for concentration
    (high RP revenue = concentrated customer base).
    """
    rp_rev_pct = rp_analysis.get("related_party_revenue_pct", 0.0)

    if rp_rev_pct >= 50:
        return 0.1, "very_high_concentration"
    if rp_rev_pct >= 30:
        return 0.3, "high_concentration"
    if rp_rev_pct >= 15:
        return 0.6, "moderate_concentration"

    # No explicit data — use sector default (textiles = relatively diversified)
    return 0.7, "assumed_moderate_diversification"


def _compute_regulatory_environment(
    benchmark: dict, research_cache: dict
) -> float:
    """
    Score regulatory environment 0 (heavy headwinds) → 1 (tailwinds).
    """
    score = 0.6   # Base

    if benchmark.get("rbi_sector_watch", False):
        score -= 0.20

    # Positive regulatory news
    positive_articles = [
        a for a in research_cache.get("news_articles", [])
        if a.get("risk_score_delta", 0) > 0
    ]
    score += min(0.20, len(positive_articles) * 0.05)

    # Negative regulatory news
    critical_articles = [
        a for a in research_cache.get("news_articles", [])
        if a.get("risk_tier") == 1
    ]
    score -= min(0.30, len(critical_articles) * 0.15)

    return round(max(0.0, min(1.0, score)), 4)


# ── Utilities ─────────────────────────────────────────────────────────────────

def _load_benchmarks() -> dict:
    """Load sector benchmarks from JSON file."""
    try:
        with open(BENCHMARKS_PATH) as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load sector benchmarks: %s", e)
        return {}


def feature_set_to_dict(fs: FeatureSet) -> dict:
    """Serialise FeatureSet for API responses, scoring, and audit trail."""
    return {
        "features": {
            # CHARACTER
            "litigation_risk":        fs.litigation_risk,
            "promoter_track_record":  fs.promoter_track_record,
            "gst_compliance":         fs.gst_compliance,
            "management_quality":     fs.management_quality,
            # CAPACITY
            "dscr":                   fs.dscr,
            "ebitda_margin_trend":    fs.ebitda_margin_trend,
            "revenue_cagr_vs_sector": fs.revenue_cagr_vs_sector,
            "plant_utilization":      fs.plant_utilization,
            # CAPITAL
            "de_ratio":               fs.de_ratio,
            "net_worth_trend":        fs.net_worth_trend,
            "promoter_equity_pct":    fs.promoter_equity_pct,
            # COLLATERAL
            "security_cover":         fs.security_cover,
            "collateral_encumbrance": fs.collateral_encumbrance,
            # CONDITIONS
            "sector_outlook":         fs.sector_outlook,
            "customer_concentration": fs.customer_concentration,
            "regulatory_environment": fs.regulatory_environment,
        },
        "raw_values":       fs.raw,
        "missing_fields":   fs.missing_fields,
        "assumptions_made": fs.assumptions_made,
    }