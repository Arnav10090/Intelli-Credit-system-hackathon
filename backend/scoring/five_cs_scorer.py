"""
scoring/five_cs_scorer.py
─────────────────────────────────────────────────────────────────────────────
Deterministic 200-point Five Cs Scorecard for Intelli-Credit.

Architecture:
  - Takes a FeatureSet from feature_engineer.py
  - Applies piecewise scoring formulas to each of 16 features
  - Returns raw score (0-200), normalised score (0-100), risk grade, decision
  - Every point contribution is recorded for the waterfall chart (explainability)

Five Cs breakdown (200 pts total):
  CHARACTER  — 60 pts  (litigation, promoter, GST, management)
  CAPACITY   — 60 pts  (DSCR, EBITDA trend, revenue CAGR, plant util)
  CAPITAL    — 45 pts  (D/E ratio, NW trend, promoter equity)
  COLLATERAL — 30 pts  (security cover, encumbrance)
  CONDITIONS — 35 pts  (sector outlook, customer conc., regulatory)

Decision logic:
  APPROVE  → score ≥ 55 AND no CRITICAL single-feature knockout
  PARTIAL  → 35 ≤ score < 55 OR CRITICAL knockout with recoverable structure
  REJECT   → score < 35 OR CRITICAL knockout with no recovery path

DETERMINISTIC — no LLM. LLM is used only for CAM narrative in Step 7.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

from config import settings
from scoring.feature_engineer import FeatureSet


# ── Output Dataclass ───────────────────────────────────────────────────────────

@dataclass
class ScorecardResult:
    """Full scorecard output — feeds loan_calculator.py and CAM generator."""

    # Sub-scores per pillar (raw, out of max)
    character_score:  int
    capacity_score:   int
    capital_score:    int
    collateral_score: int
    conditions_score: int

    character_max:  int = 60
    capacity_max:   int = 60
    capital_max:    int = 45
    collateral_max: int = 30
    conditions_max: int = 35

    # Totals
    total_raw_score:    int = 0     # 0-200
    normalised_score:   int = 0     # 0-100 (raw/200 * 100)
    risk_grade:         str = ""    # A+, A, B+, B, C, D
    risk_label:         str = ""    # Excellent, Strong, Acceptable, etc.

    # Decision
    decision:                   str = ""    # APPROVE | PARTIAL | REJECT
    primary_rejection_trigger:  str = ""    # Feature that caused reject/partial
    counter_factual:            str = ""    # "What would change the decision"

    # Point contributions for waterfall chart
    # {feature_name: {"points_awarded": X, "max_points": Y, "pct": Z}}
    contributions: dict = field(default_factory=dict)

    # Knockout flags (features that can force REJECT regardless of total)
    knockout_flags: list[str] = field(default_factory=list)

    # Interest rate basis
    interest_premium_bps: int = 0
    base_rate_pct: float = 0.0
    recommended_rate_pct: float = 0.0


# ── Main Scoring Function ─────────────────────────────────────────────────────

def compute_score(features: FeatureSet) -> ScorecardResult:
    """
    Main entry point. Takes a FeatureSet and returns a complete ScorecardResult.
    Called from score_routes.py.
    """
    logger.info("Running Five Cs scorecard")

    contributions = {}
    knockouts     = []

    # ─────────────────────────────────────────────────────────────────────────
    # CHARACTER (60 pts)
    # ─────────────────────────────────────────────────────────────────────────

    # 1. Litigation Risk (20 pts)
    lit_pts = _score_litigation_risk(features.litigation_risk)
    contributions["litigation_risk"] = _contrib(lit_pts, 20)
    if lit_pts <= 4:   # ≤20% of max → knockout
        knockouts.append("litigation_risk: Critical litigation detected (NCLT/IBC/DRT)")

    # 2. Promoter Track Record (15 pts)
    promo_pts = _score_promoter_track_record(features.promoter_track_record)
    contributions["promoter_track_record"] = _contrib(promo_pts, 15)

    # 3. GST Compliance (10 pts)
    gst_pts = _score_gst_compliance(features.gst_compliance)
    contributions["gst_compliance"] = _contrib(gst_pts, 10)
    if gst_pts == 0:
        knockouts.append("gst_compliance: Critical GST violation (circular trading)")

    # 4. Management Quality (15 pts)
    mgmt_pts = _score_management_quality(features.management_quality)
    contributions["management_quality"] = _contrib(mgmt_pts, 15)

    character_score = lit_pts + promo_pts + gst_pts + mgmt_pts

    # ─────────────────────────────────────────────────────────────────────────
    # CAPACITY (60 pts)
    # ─────────────────────────────────────────────────────────────────────────

    # 5. DSCR (25 pts) — piecewise formula
    dscr_pts = _score_dscr(features.dscr)
    contributions["dscr"] = _contrib(dscr_pts, 25)
    if dscr_pts <= 5:
        knockouts.append(f"dscr: DSCR {features.dscr:.2f}x — insufficient cash flow for debt service")

    # 6. EBITDA Margin Trend (15 pts)
    ebitda_pts = _score_ebitda_margin_trend(features.ebitda_margin_trend)
    contributions["ebitda_margin_trend"] = _contrib(ebitda_pts, 15)

    # 7. Revenue CAGR vs Sector (10 pts)
    cagr_pts = _score_revenue_cagr(features.revenue_cagr_vs_sector)
    contributions["revenue_cagr_vs_sector"] = _contrib(cagr_pts, 10)

    # 8. Plant Utilization (10 pts)
    plant_pts = _score_plant_utilization(features.plant_utilization)
    contributions["plant_utilization"] = _contrib(plant_pts, 10)

    capacity_score = dscr_pts + ebitda_pts + cagr_pts + plant_pts

    # ─────────────────────────────────────────────────────────────────────────
    # CAPITAL (45 pts)
    # ─────────────────────────────────────────────────────────────────────────

    # 9. D/E Ratio (20 pts) — piecewise formula
    de_pts = _score_de_ratio(features.de_ratio)
    contributions["de_ratio"] = _contrib(de_pts, 20)

    # 10. Net Worth Trend (15 pts)
    nw_pts = _score_net_worth_trend(features.net_worth_trend)
    contributions["net_worth_trend"] = _contrib(nw_pts, 15)

    # 11. Promoter Equity % (10 pts)
    equity_pts = _score_promoter_equity(features.promoter_equity_pct)
    contributions["promoter_equity_pct"] = _contrib(equity_pts, 10)

    capital_score = de_pts + nw_pts + equity_pts

    # ─────────────────────────────────────────────────────────────────────────
    # COLLATERAL (30 pts)
    # ─────────────────────────────────────────────────────────────────────────

    # 12. Security Cover (20 pts) — piecewise formula
    sec_pts = _score_security_cover(features.security_cover)
    contributions["security_cover"] = _contrib(sec_pts, 20)
    if sec_pts == 0:
        knockouts.append("security_cover: Insufficient collateral to secure the loan")

    # 13. Collateral Encumbrance (10 pts)
    enc_pts = _score_collateral_encumbrance(features.collateral_encumbrance)
    contributions["collateral_encumbrance"] = _contrib(enc_pts, 10)

    collateral_score = sec_pts + enc_pts

    # ─────────────────────────────────────────────────────────────────────────
    # CONDITIONS (35 pts)
    # ─────────────────────────────────────────────────────────────────────────

    # 14. Sector Outlook (15 pts)
    sector_pts = _score_sector_outlook(features.sector_outlook)
    contributions["sector_outlook"] = _contrib(sector_pts, 15)

    # 15. Customer Concentration (10 pts)
    cust_pts = _score_customer_concentration(features.customer_concentration)
    contributions["customer_concentration"] = _contrib(cust_pts, 10)

    # 16. Regulatory Environment (10 pts)
    reg_pts = _score_regulatory_environment(features.regulatory_environment)
    contributions["regulatory_environment"] = _contrib(reg_pts, 10)

    conditions_score = sector_pts + cust_pts + reg_pts

    # ─────────────────────────────────────────────────────────────────────────
    # TOTALS & GRADE
    # ─────────────────────────────────────────────────────────────────────────

    total_raw = (character_score + capacity_score +
                 capital_score + collateral_score + conditions_score)
    normalised = round((total_raw / settings.SCORE_MAX) * 100)

    grade, label = _get_grade(normalised)

    # ─────────────────────────────────────────────────────────────────────────
    # DECISION LOGIC
    # ─────────────────────────────────────────────────────────────────────────

    decision, trigger, counter = _make_decision(
        normalised, knockouts, features, contributions
    )

    # ─────────────────────────────────────────────────────────────────────────
    # INTEREST RATE
    # ─────────────────────────────────────────────────────────────────────────

    premium_bps, base_rate, recommended_rate = _compute_rate(
        grade, features
    )

    result = ScorecardResult(
        character_score=character_score,
        capacity_score=capacity_score,
        capital_score=capital_score,
        collateral_score=collateral_score,
        conditions_score=conditions_score,
        total_raw_score=total_raw,
        normalised_score=normalised,
        risk_grade=grade,
        risk_label=label,
        decision=decision,
        primary_rejection_trigger=trigger,
        counter_factual=counter,
        contributions=contributions,
        knockout_flags=knockouts,
        interest_premium_bps=premium_bps,
        base_rate_pct=base_rate,
        recommended_rate_pct=recommended_rate,
    )

    logger.info(
        "Scorecard complete: raw=%d/200 normalised=%d/100 grade=%s decision=%s",
        total_raw, normalised, grade, decision
    )
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE SCORING FORMULAS
# Each returns integer points (0 to max for that feature)
# ═══════════════════════════════════════════════════════════════════════════════

def _score_litigation_risk(value: float) -> int:
    """
    Piecewise linear scoring.
    0.0–0.25 (critical/IBC): 0–4 pts
    0.25–0.50 (serious):     4–10 pts
    0.50–0.75 (moderate):    10–15 pts
    0.75–1.0  (clean):       15–20 pts
    """
    if value >= 0.75:
        return 20
    if value >= 0.50:
        return 15 + int((value - 0.50) / 0.25 * 5)
    if value >= 0.25:
        return 10 + int((value - 0.25) / 0.25 * 5)
    return int(value / 0.25 * 4)


def _score_promoter_track_record(value: float) -> int:
    """
    0.0–0.3 (heavy pledge/concerns): 0–5 pts
    0.3–0.6 (elevated pledge):       5–10 pts
    0.6–1.0 (acceptable):            10–15 pts
    """
    if value >= 0.6:
        return 10 + int((value - 0.6) / 0.4 * 5)
    if value >= 0.3:
        return 5 + int((value - 0.3) / 0.3 * 5)
    return int(value / 0.3 * 5)


def _score_gst_compliance(value: float) -> int:
    """
    0.0 (circular trading): 0 pts (knockout)
    0.0–0.5 (serious):      0–5 pts
    0.5–0.8 (moderate):     5–8 pts
    0.8–1.0 (good):         8–10 pts
    """
    if value >= 0.8:
        return 10
    if value >= 0.5:
        return 5 + int((value - 0.5) / 0.3 * 3)
    return int(value / 0.5 * 5)


def _score_management_quality(value: float) -> int:
    """Linear 0–1 → 0–15 pts."""
    return int(value * 15)


def _score_dscr(dscr: float) -> int:
    """
    Piecewise DSCR scoring (25 pts max):
    DSCR < 1.0:       0 pts  (knockout — cannot service debt)
    1.0 ≤ DSCR < 1.1: 3 pts  (barely covers — partial only)
    1.1 ≤ DSCR < 1.3: 8 pts  (below minimum threshold)
    1.3 ≤ DSCR < 1.5: 14 pts (at minimum acceptable)
    1.5 ≤ DSCR < 1.75:18 pts (comfortable)
    1.75≤ DSCR < 2.0: 22 pts (strong)
    DSCR ≥ 2.0:       25 pts (excellent)
    """
    if dscr < 1.00:   return 0
    if dscr < 1.10:   return 3
    if dscr < 1.30:   return 8
    if dscr < 1.50:   return 14
    if dscr < 1.75:   return 18
    if dscr < 2.00:   return 22
    return 25


def _score_ebitda_margin_trend(value: float) -> int:
    """Linear 0–1 → 0–15 pts."""
    return int(value * 15)


def _score_revenue_cagr(value: float) -> int:
    """
    value = cagr_ratio (company CAGR / sector CAGR), clamped 0–1.
    0.0 (far below sector): 0–3 pts
    0.3–0.6 (near sector):  3–7 pts
    0.6–1.0 (at/above):     7–10 pts
    """
    if value >= 0.6:
        return 7 + int((value - 0.6) / 0.4 * 3)
    if value >= 0.3:
        return 3 + int((value - 0.3) / 0.3 * 4)
    return int(value / 0.3 * 3)


def _score_plant_utilization(value: float) -> int:
    """Linear 0–1 → 0–10 pts."""
    return int(value * 10)


def _score_de_ratio(de: float) -> int:
    """
    Piecewise D/E scoring (20 pts max):
    D/E > 5.0:          0 pts  (critically over-leveraged)
    4.0 < D/E ≤ 5.0:    4 pts
    3.0 < D/E ≤ 4.0:    8 pts
    2.0 < D/E ≤ 3.0:   12 pts
    1.0 < D/E ≤ 2.0:   16 pts
    D/E ≤ 1.0:         20 pts  (conservative leverage)
    """
    if de > 5.0:   return 0
    if de > 4.0:   return 4
    if de > 3.0:   return 8
    if de > 2.0:   return 12
    if de > 1.0:   return 16
    return 20


def _score_net_worth_trend(value: float) -> int:
    """Linear 0–1 → 0–15 pts."""
    return int(value * 15)


def _score_promoter_equity(promo_pct: float) -> int:
    """
    Piecewise promoter equity scoring (10 pts max):
    < 26% (minority):      0–3 pts
    26–51% (significant):  3–7 pts
    > 51% (majority):      7–10 pts
    """
    if promo_pct >= 51.0:
        return 7 + int(min(3, (promo_pct - 51.0) / 49.0 * 3))
    if promo_pct >= 26.0:
        return 3 + int((promo_pct - 26.0) / 25.0 * 4)
    return int(promo_pct / 26.0 * 3)


def _score_security_cover(cover: float) -> int:
    """
    Piecewise security cover scoring (20 pts max):
    cover < 0.8x:   0 pts  (under-secured — knockout)
    0.8x–1.0x:      5 pts
    1.0x–1.25x:    10 pts
    1.25x–1.5x:    14 pts
    1.5x–2.0x:     17 pts
    ≥ 2.0x:        20 pts
    """
    if cover < 0.80:   return 0
    if cover < 1.00:   return 5
    if cover < 1.25:   return 10
    if cover < 1.50:   return 14
    if cover < 2.00:   return 17
    return 20


def _score_collateral_encumbrance(value: float) -> int:
    """Linear 0–1 → 0–10 pts."""
    return int(value * 10)


def _score_sector_outlook(value: float) -> int:
    """Linear 0–1 → 0–15 pts."""
    return int(value * 15)


def _score_customer_concentration(value: float) -> int:
    """Linear 0–1 → 0–10 pts."""
    return int(value * 10)


def _score_regulatory_environment(value: float) -> int:
    """Linear 0–1 → 0–10 pts."""
    return int(value * 10)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_grade(normalised: int) -> tuple[str, str]:
    """Return (grade, label) from normalised 0-100 score."""
    for band_key, band in settings.RISK_BANDS.items():
        if band["min"] <= normalised <= band["max"]:
            return band["grade"], band["label"]
    return "D", "Decline"


def _make_decision(
    normalised: int,
    knockouts: list[str],
    features: FeatureSet,
    contributions: dict,
) -> tuple[str, str, str]:
    """
    Determine APPROVE / PARTIAL / REJECT with primary trigger and counter-factual.

    Rules:
      REJECT:  score < 35 OR any knockout flag present
      PARTIAL: 35 ≤ score < 55 (B or below) — can approve reduced amount
      APPROVE: score ≥ 55
    """
    if knockouts:
        # Find the most severe knockout
        trigger = knockouts[0]

        # Check if PARTIAL is possible despite knockout
        # Possible if: (a) DSCR knockout is the only one AND score ≥ 35
        #             (b) Litigation but borrower offers additional security
        dscr_only_knockout = (
            len(knockouts) == 1 and "dscr" in knockouts[0].lower()
        )
        litigation_knockout = any("litigation" in k.lower() for k in knockouts)

        if litigation_knockout:
            counter = (
                "Approval possible only after NCLT petition is resolved or "
                "dismissed. Borrower must provide no-objection from petitioner "
                "or proof of full settlement."
            )
            return "REJECT", trigger, counter

        if dscr_only_knockout and normalised >= 35:
            counter = (
                f"DSCR of {features.dscr:.2f}x is below the 1.30x minimum. "
                f"Partial approval possible at reduced loan amount where "
                f"DSCR ≥ 1.30x. Alternatively, additional cash flow "
                f"security (FD/escrow) may support full sanction."
            )
            return "PARTIAL", trigger, counter

        counter = _generate_counter_factual(knockouts, features, contributions)
        return "REJECT", trigger, counter

    if normalised >= 55:
        counter = "Maintain current financial profile. Quarterly DSCR monitoring recommended."
        return "APPROVE", "", counter

    if normalised >= 35:
        # Find the lowest-scoring feature as the primary trigger
        worst = min(
            contributions.items(),
            key=lambda x: x[1]["pct"]
        )
        trigger = (
            f"{worst[0]} scored {worst[1]['points_awarded']}/{worst[1]['max_points']} "
            f"({worst[1]['pct']:.0f}%)"
        )
        counter = _generate_counter_factual([], features, contributions)
        return "PARTIAL", trigger, counter

    worst = min(contributions.items(), key=lambda x: x[1]["pct"])
    trigger = worst[0]
    counter = _generate_counter_factual([], features, contributions)
    return "REJECT", trigger, counter


def _generate_counter_factual(
    knockouts: list[str],
    features: FeatureSet,
    contributions: dict,
) -> str:
    """
    Generate a plain-English counter-factual explanation.
    What single change would most improve the decision?
    """
    # Find the feature with biggest gap from max
    gaps = {
        name: data["max_points"] - data["points_awarded"]
        for name, data in contributions.items()
    }
    biggest_gap_feature = max(gaps, key=gaps.get)
    gap_pts = gaps[biggest_gap_feature]

    templates = {
        "dscr": (
            f"Improving DSCR from {features.dscr:.2f}x to ≥1.30x (minimum) "
            f"would unlock up to {gap_pts} additional score points. "
            "This can be achieved through revenue growth, cost reduction, "
            "or reducing the loan quantum."
        ),
        "de_ratio": (
            f"Reducing D/E from {features.de_ratio:.2f}x to ≤2.0x through "
            f"equity infusion or debt repayment would add up to {gap_pts} points."
        ),
        "security_cover": (
            f"Providing additional collateral to raise security cover to ≥1.25x "
            f"would add up to {gap_pts} points. Consider FD pledge, "
            "receivables assignment, or additional property."
        ),
        "litigation_risk": (
            f"Resolving the pending litigation / NCLT proceedings would add "
            f"up to {gap_pts} points and may convert the decision to APPROVE."
        ),
        "promoter_track_record": (
            f"Releasing promoter pledges (currently {features.promoter_equity_pct:.1f}% pledged) "
            f"would add up to {gap_pts} points to the CHARACTER pillar."
        ),
    }

    return templates.get(
        biggest_gap_feature,
        f"Improving {biggest_gap_feature.replace('_', ' ')} "
        f"to best-in-class would add up to {gap_pts} score points."
    )


def _compute_rate(grade: str, features: FeatureSet) -> tuple[int, float, float]:
    """
    Compute interest rate for this case.

    Formula:
      Rate = RBI Repo + NBFC Spread + Risk Premium
              + Long Tenor Premium (if tenor > 5yr)
              - Strong Collateral Discount (if cover > 2.0x)

    Risk Premium: midpoint of grade's bps range
    """
    band = None
    for b in settings.RISK_BANDS.values():
        if b["grade"] == grade:
            band = b
            break

    if not band or grade == "D":
        # Reject — no rate
        return 0, 0.0, 0.0

    premium_bps = (
        band["interest_premium_bps_min"] + band["interest_premium_bps_max"]
    ) // 2

    base_rate = settings.RBI_REPO_RATE + settings.NBFC_BASE_SPREAD
    rate      = base_rate + (premium_bps / 100)

    # Long tenor premium (applied at loan calculator level, but noted here)
    # Strong collateral discount
    if features.security_cover >= settings.STRONG_COLLATERAL_THRESHOLD:
        rate -= settings.STRONG_COLLATERAL_DISCOUNT_BPS / 100

    return premium_bps, round(base_rate, 2), round(rate, 2)


def _contrib(points: int, max_points: int) -> dict:
    """Build a contribution dict for the waterfall chart."""
    pct = (points / max_points * 100) if max_points > 0 else 0
    return {
        "points_awarded": points,
        "max_points":     max_points,
        "pct":            round(pct, 1),
    }


def scorecard_to_dict(result: ScorecardResult) -> dict:
    """Serialise ScorecardResult for API responses and database storage."""
    return {
        "pillar_scores": {
            "character":  {"score": result.character_score,  "max": result.character_max},
            "capacity":   {"score": result.capacity_score,   "max": result.capacity_max},
            "capital":    {"score": result.capital_score,    "max": result.capital_max},
            "collateral": {"score": result.collateral_score, "max": result.collateral_max},
            "conditions": {"score": result.conditions_score, "max": result.conditions_max},
        },
        "total_raw_score":    result.total_raw_score,
        "normalised_score":   result.normalised_score,
        "risk_grade":         result.risk_grade,
        "risk_label":         result.risk_label,
        "decision":           result.decision,
        "primary_rejection_trigger": result.primary_rejection_trigger,
        "counter_factual":    result.counter_factual,
        "knockout_flags":     result.knockout_flags,
        "contributions":      result.contributions,
        "interest_premium_bps":  result.interest_premium_bps,
        "base_rate_pct":         result.base_rate_pct,
        "recommended_rate_pct":  result.recommended_rate_pct,
    }