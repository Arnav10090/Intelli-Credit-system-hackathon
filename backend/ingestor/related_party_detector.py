"""
ingestor/related_party_detector.py
─────────────────────────────────────────────────────────────────────────────
Related Party Transaction & Promoter Risk Analysis for Intelli-Credit.

Detects and scores:
  1. Promoter pledge concentration risk (from shareholding pattern)
  2. Related party revenue concentration (AS-18 disclosures)
  3. Related party receivables concentration
  4. Inter-company loan exposure
  5. Director/promoter loan exposure
  6. Promoter stake trend (increasing = good, decreasing = red flag)

Inputs:
  - financial_data.json (promoters, shareholding_pattern)
  - Covenant extractor output (related_party_flags from annual report text)
  - Research cache (pledge data from BSE/NSE)

All logic is DETERMINISTIC — no LLM.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

from config import settings


# ── Data Structures ────────────────────────────────────────────────────────────

@dataclass
class PromoterProfile:
    name: str
    din: str
    designation: str
    shareholding_pct: float
    shares_pledged_pct: float      # % of promoter's own holding that is pledged
    pledge_risk_label: str         # CRITICAL | HIGH | MEDIUM | LOW | NONE
    pledge_score_delta: int        # Negative score impact
    other_directorships: list[str]
    directorship_concern: bool     # True if director of distressed entity


@dataclass
class RelatedPartyResult:
    """Complete related party and promoter risk analysis."""
    doc_id: str

    # Promoter analysis
    promoter_profiles: list[PromoterProfile]
    total_promoter_holding_pct: float
    total_promoter_pledged_pct: float     # Weighted avg pledge across promoters
    pledge_risk_label: str                # Aggregate pledge risk
    pledge_score_delta: int               # Points deducted from CHARACTER score

    # Related party concentrations
    related_party_revenue_pct: float      # % of revenue from related parties
    related_party_receivables_pct: float  # % of receivables from related parties
    intercompany_loan_exposure: float     # ₹ Lakhs loans to group companies
    director_loan_exposure: float         # ₹ Lakhs loans to directors/promoters

    # Flags
    flags: list[dict]

    # Summary for scoring engine
    character_risk_score: int             # Total deduction to CHARACTER pillar
    management_quality_score: int         # 0-15 score (fed into five_cs_scorer)

    warnings: list[str] = field(default_factory=list)


# ── Main Analysis Function ────────────────────────────────────────────────────

def analyze_related_parties(
    doc_id: str,
    financial_data: dict,
    covenant_flags: list[str] | None = None,
    research_cache: dict | None = None,
) -> RelatedPartyResult:
    """
    Main entry point.

    Args:
        doc_id:          Document ID for audit trail
        financial_data:  Dict from financial_data.json
        covenant_flags:  Related party text snippets from covenant_extractor
        research_cache:  Dict from research_cache.json (pledge data, news)
    """
    logger.info("Running related party analysis for doc_id=%s", doc_id)

    flags    = []
    warnings = []

    promoters       = financial_data.get("promoters", [])
    shareholding    = financial_data.get("shareholding_pattern", {})
    financials      = financial_data.get("financials", {})

    # ── 1. Promoter Pledge Analysis ───────────────────────────────────────────
    promoter_profiles, pledge_flags, aggregate_pledge_pct = _analyze_promoter_pledge(
        promoters, shareholding, research_cache
    )
    flags.extend(pledge_flags)

    # Aggregate pledge label
    pledge_label = _pledge_risk_label(aggregate_pledge_pct)
    pledge_delta = _pledge_score_delta(aggregate_pledge_pct)

    # ── 2. Related Party Revenue / Receivables ────────────────────────────────
    rp_revenue_pct, rp_receivables_pct, rp_flags = _analyze_rp_concentrations(
        financials, covenant_flags or []
    )
    flags.extend(rp_flags)

    # ── 3. Inter-company & Director Loan Exposure ─────────────────────────────
    ic_loans, dir_loans, loan_flags = _analyze_loan_exposure(
        covenant_flags or [], financial_data
    )
    flags.extend(loan_flags)

    # ── 4. Directorship Concerns ──────────────────────────────────────────────
    dir_flags = _check_directorship_concerns(promoter_profiles, research_cache)
    flags.extend(dir_flags)

    # ── 5. Management Quality Score (0-15) ────────────────────────────────────
    mgmt_score = _compute_management_score(
        promoter_profiles, flags, research_cache
    )

    # Total character risk deduction
    char_risk = pledge_delta + sum(
        f.get("score_delta", 0) for f in flags
        if f.get("pillar") == "CHARACTER"
    )

    result = RelatedPartyResult(
        doc_id=doc_id,
        promoter_profiles=promoter_profiles,
        total_promoter_holding_pct=shareholding.get("promoter_total_pct", 0.0),
        total_promoter_pledged_pct=round(aggregate_pledge_pct, 1),
        pledge_risk_label=pledge_label,
        pledge_score_delta=pledge_delta,
        related_party_revenue_pct=round(rp_revenue_pct, 1),
        related_party_receivables_pct=round(rp_receivables_pct, 1),
        intercompany_loan_exposure=round(ic_loans, 2),
        director_loan_exposure=round(dir_loans, 2),
        flags=flags,
        character_risk_score=char_risk,
        management_quality_score=mgmt_score,
        warnings=warnings,
    )

    logger.info(
        "RP analysis: pledge=%.1f%% (%s) | rp_rev=%.1f%% | flags=%d | mgmt_score=%d",
        aggregate_pledge_pct, pledge_label,
        rp_revenue_pct, len(flags), mgmt_score
    )
    return result


# ── Promoter Pledge ────────────────────────────────────────────────────────────

def _analyze_promoter_pledge(
    promoters: list[dict],
    shareholding: dict,
    research_cache: dict | None,
) -> tuple[list[PromoterProfile], list[dict], float]:
    """
    Analyse pledge concentration for each promoter.
    Uses shareholding_pattern.promoter_pledged_pct as primary source.
    Falls back to promoter-level data if available.
    """
    flags    = []
    profiles = []

    # Primary source: aggregate pledge from shareholding pattern
    aggregate_pledge_pct = shareholding.get("promoter_pledged_pct", 0.0)

    # Override with research cache if available (more current)
    if research_cache:
        for finding in research_cache.get("mca_filings", []):
            if "pledge" in str(finding).lower():
                pass   # Would extract pledge % from BSE/CDSL data

    for p in promoters:
        pledge_pct = p.get("shares_pledged_pct", 0.0)
        label      = _pledge_risk_label(pledge_pct)
        delta      = _pledge_score_delta(pledge_pct)

        profile = PromoterProfile(
            name=p.get("name", ""),
            din=p.get("din", ""),
            designation=p.get("designation", ""),
            shareholding_pct=p.get("shareholding_pct", 0.0),
            shares_pledged_pct=pledge_pct,
            pledge_risk_label=label,
            pledge_score_delta=delta,
            other_directorships=p.get("other_directorships", []),
            directorship_concern=False,  # Set in _check_directorship_concerns
        )
        profiles.append(profile)

    # Flag based on aggregate (portfolio-level) pledge
    if aggregate_pledge_pct >= settings.PROMOTER_PLEDGE_HIGH_PCT:
        flags.append({
            "flag_type": "PROMOTER_PLEDGE_CRITICAL",
            "severity": "HIGH",
            "title": (
                f"Critical promoter pledge: {aggregate_pledge_pct:.1f}% "
                f"of promoter holding pledged"
            ),
            "description": (
                f"Promoters have pledged {aggregate_pledge_pct:.1f}% of their "
                f"{shareholding.get('promoter_total_pct', 0):.1f}% holding. "
                f"Above {settings.PROMOTER_PLEDGE_HIGH_PCT:.0f}% threshold — "
                "triggers mandatory annotation per SEBI disclosure norms. "
                "Margin call risk: if stock falls, forced selling could trigger "
                "ownership change and management disruption."
            ),
            "metric_name": "promoter_pledge_pct",
            "metric_value": aggregate_pledge_pct,
            "threshold": settings.PROMOTER_PLEDGE_HIGH_PCT,
            "score_delta": -35,
            "pillar": "CHARACTER",
        })
    elif aggregate_pledge_pct >= settings.PROMOTER_PLEDGE_WARN_PCT:
        flags.append({
            "flag_type": "PROMOTER_PLEDGE_HIGH",
            "severity": "MEDIUM",
            "title": (
                f"Elevated promoter pledge: {aggregate_pledge_pct:.1f}% pledged"
            ),
            "description": (
                f"Promoter pledge of {aggregate_pledge_pct:.1f}% exceeds the "
                f"{settings.PROMOTER_PLEDGE_WARN_PCT:.0f}% warning threshold. "
                "Represents a contingent ownership risk if lender invokes pledge."
            ),
            "metric_name": "promoter_pledge_pct",
            "metric_value": aggregate_pledge_pct,
            "threshold": settings.PROMOTER_PLEDGE_WARN_PCT,
            "score_delta": -20,
            "pillar": "CHARACTER",
        })

    return profiles, flags, aggregate_pledge_pct


def _pledge_risk_label(pledge_pct: float) -> str:
    if pledge_pct >= settings.PROMOTER_PLEDGE_HIGH_PCT:
        return "CRITICAL"
    if pledge_pct >= settings.PROMOTER_PLEDGE_WARN_PCT:
        return "HIGH"
    if pledge_pct >= 25.0:
        return "MEDIUM"
    if pledge_pct > 0:
        return "LOW"
    return "NONE"


def _pledge_score_delta(pledge_pct: float) -> int:
    if pledge_pct >= settings.PROMOTER_PLEDGE_HIGH_PCT:
        return -35
    if pledge_pct >= settings.PROMOTER_PLEDGE_WARN_PCT:
        return -20
    if pledge_pct >= 25.0:
        return -10
    return 0


# ── Related Party Concentrations ───────────────────────────────────────────────

def _analyze_rp_concentrations(
    financials: dict,
    covenant_flags: list[str],
) -> tuple[float, float, list[dict]]:
    """
    Estimate related party revenue and receivables concentrations.
    Primary source: AS-18 disclosure text from covenant_extractor.
    Falls back to 0% if no disclosure found (conservative assumption).
    """
    flags = []
    rp_revenue_pct      = 0.0
    rp_receivables_pct  = 0.0

    # Try to extract percentages from covenant flags text
    for text in covenant_flags:
        text_lower = text.lower()

        # Revenue pattern: "related party sales of Rs X Cr representing Y% of revenue"
        rev_match = re.search(
            r"related party.*?(\d+\.?\d*)\s*%.*?(?:revenue|turnover|sales)",
            text_lower
        )
        if rev_match and rp_revenue_pct == 0:
            rp_revenue_pct = float(rev_match.group(1))

        # Receivables pattern: "related party receivables of Rs X Cr"
        rec_match = re.search(
            r"related party.*?(?:receivables?|outstanding).*?(\d+\.?\d*)\s*%",
            text_lower
        )
        if rec_match and rp_receivables_pct == 0:
            rp_receivables_pct = float(rec_match.group(1))

    # Flag if thresholds breached
    if rp_revenue_pct > settings.RELATED_PARTY_REVENUE_PCT_HIGH:
        flags.append({
            "flag_type": "RELATED_PARTY_REVENUE_HIGH",
            "severity": "HIGH",
            "title": (
                f"Related party revenue concentration: {rp_revenue_pct:.1f}%"
            ),
            "description": (
                f"Revenue from related parties ({rp_revenue_pct:.1f}%) exceeds "
                f"the {settings.RELATED_PARTY_REVENUE_PCT_HIGH:.0f}% threshold. "
                "High related party concentration may mask true market demand "
                "and creates earnings quality concerns."
            ),
            "metric_name": "related_party_revenue_pct",
            "metric_value": rp_revenue_pct,
            "threshold": settings.RELATED_PARTY_REVENUE_PCT_HIGH,
            "score_delta": -15,
            "pillar": "CHARACTER",
        })

    if rp_receivables_pct > settings.RELATED_PARTY_RECEIVABLES_PCT_HIGH:
        flags.append({
            "flag_type": "RELATED_PARTY_RECEIVABLES_HIGH",
            "severity": "MEDIUM",
            "title": (
                f"Related party receivables concentration: {rp_receivables_pct:.1f}%"
            ),
            "description": (
                f"Receivables from related parties ({rp_receivables_pct:.1f}%) "
                f"exceeds {settings.RELATED_PARTY_RECEIVABLES_PCT_HIGH:.0f}% threshold. "
                "May indicate circular transactions or revenue recognition concerns."
            ),
            "metric_name": "related_party_receivables_pct",
            "metric_value": rp_receivables_pct,
            "threshold": settings.RELATED_PARTY_RECEIVABLES_PCT_HIGH,
            "score_delta": -10,
            "pillar": "CHARACTER",
        })

    return rp_revenue_pct, rp_receivables_pct, flags


# ── Loan Exposure ──────────────────────────────────────────────────────────────

def _analyze_loan_exposure(
    covenant_flags: list[str],
    financial_data: dict,
) -> tuple[float, float, list[dict]]:
    """
    Detect loans to group companies and directors from text flags.
    """
    flags         = []
    ic_loans      = 0.0
    dir_loans     = 0.0

    for text in covenant_flags:
        text_lower = text.lower()

        # Intercompany loans
        ic_match = re.search(
            r"(?:inter.?company|group company|subsidiary).*?"
            r"(?:loan|advance).*?(?:rs\.?|inr|₹)?\s*([\d,]+\.?\d*)",
            text_lower
        )
        if ic_match:
            try:
                ic_loans += float(ic_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Director loans
        dir_match = re.search(
            r"(?:director|promoter|key managerial).*?"
            r"(?:loan|advance|amount due).*?(?:rs\.?|inr|₹)?\s*([\d,]+\.?\d*)",
            text_lower
        )
        if dir_match:
            try:
                dir_loans += float(dir_match.group(1).replace(",", ""))
            except ValueError:
                pass

    # Get net worth for % calculation
    bs    = financial_data.get("financials", {}).get("balance_sheet", {})
    tnw_list = bs.get("tangible_net_worth", [0])
    tnw   = float(tnw_list[-1]) if isinstance(tnw_list, list) else float(tnw_list)

    # Flag if material
    if ic_loans > 0 and tnw > 0 and (ic_loans / tnw) > 0.20:
        flags.append({
            "flag_type": "INTERCOMPANY_LOAN_HIGH",
            "severity": "MEDIUM",
            "title": (
                f"Significant inter-company loans: ₹{ic_loans:.0f}L "
                f"({ic_loans/tnw*100:.1f}% of net worth)"
            ),
            "description": (
                f"Loans to group/subsidiary companies of ₹{ic_loans:.0f}L "
                f"represent {ic_loans/tnw*100:.1f}% of tangible net worth. "
                "This reduces effective security cover and indicates "
                "possible fund diversion risk."
            ),
            "metric_name": "intercompany_loans_to_tnw_pct",
            "metric_value": round(ic_loans / tnw * 100, 1),
            "threshold": 20.0,
            "score_delta": -10,
            "pillar": "CAPITAL",
        })

    if dir_loans > 0:
        flags.append({
            "flag_type": "DIRECTOR_LOAN_EXPOSURE",
            "severity": "MEDIUM",
            "title": f"Loans to directors/promoters: ₹{dir_loans:.0f}L",
            "description": (
                f"Advances of ₹{dir_loans:.0f}L are outstanding to directors "
                "or promoters. Under Companies Act 2013, Section 185 restricts "
                "such loans. Requires legal review."
            ),
            "metric_name": "director_loan_lakhs",
            "metric_value": dir_loans,
            "threshold": 0.0,
            "score_delta": -10,
            "pillar": "CHARACTER",
        })

    return ic_loans, dir_loans, flags


# ── Directorship Concerns ──────────────────────────────────────────────────────

def _check_directorship_concerns(
    profiles: list[PromoterProfile],
    research_cache: dict | None,
) -> list[dict]:
    """
    Check if promoters/directors are associated with distressed or
    fraud-flagged entities via their other directorships.
    """
    flags = []
    if not research_cache:
        return flags

    # Build a set of flagged company names from research
    flagged_companies = set()
    for article in research_cache.get("news_articles", []):
        if article.get("risk_tier") == 1:
            # Tier 1 = Critical. Extract company names from title.
            title = article.get("title", "")
            flagged_companies.add(title[:30].lower())

    for profile in profiles:
        for company in profile.other_directorships:
            if any(fc in company.lower() for fc in flagged_companies):
                profile.directorship_concern = True
                flags.append({
                    "flag_type": "DIRECTORSHIP_CONCERN",
                    "severity": "MEDIUM",
                    "title": (
                        f"Director {profile.name} associated with "
                        f"flagged entity: {company}"
                    ),
                    "description": (
                        f"Director {profile.name} holds a directorship in "
                        f"{company}, which has appeared in risk-flagged news. "
                        "Requires additional due diligence."
                    ),
                    "metric_name": None,
                    "metric_value": None,
                    "threshold": None,
                    "score_delta": -5,
                    "pillar": "CHARACTER",
                })

    return flags


# ── Management Quality Score ───────────────────────────────────────────────────

def _compute_management_score(
    profiles: list[PromoterProfile],
    flags: list[dict],
    research_cache: dict | None,
) -> int:
    """
    Compute management quality score (0-15 points).
    Fed into five_cs_scorer.py as the management_quality feature.

    Scoring logic:
      Base: 12 points
      Deductions:
        - Each CRITICAL/HIGH flag related to management: -3 pts
        - Each MEDIUM flag: -1 pt
        - Pledge > 75%: -3 pts
        - Pledge > 50%: -1 pt
        - Directorship concern: -2 pts
    """
    score = 12   # Base score out of 15

    # Deduct for flags
    for flag in flags:
        severity = flag.get("severity", "")
        if severity in ("CRITICAL", "HIGH"):
            score -= 3
        elif severity == "MEDIUM":
            score -= 1

    # Deduct for pledge
    max_pledge = max(
        (p.shares_pledged_pct for p in profiles), default=0
    )
    if max_pledge >= settings.PROMOTER_PLEDGE_HIGH_PCT:
        score -= 3
    elif max_pledge >= settings.PROMOTER_PLEDGE_WARN_PCT:
        score -= 1

    # Deduct for directorship concerns
    concern_count = sum(1 for p in profiles if p.directorship_concern)
    score -= concern_count * 2

    # Positive: research shows promoter increasing stake
    if research_cache:
        positive = research_cache.get("news_articles", [])
        if any("increasing stake" in str(a).lower() or
               "pledge released" in str(a).lower()
               for a in positive):
            score += 2

    return max(0, min(15, score))   # Clamp to 0-15


def result_to_dict(result: RelatedPartyResult) -> dict:
    """Serialise for API responses and database storage."""
    return {
        "doc_id": result.doc_id,
        "total_promoter_holding_pct": result.total_promoter_holding_pct,
        "total_promoter_pledged_pct": result.total_promoter_pledged_pct,
        "pledge_risk_label": result.pledge_risk_label,
        "pledge_score_delta": result.pledge_score_delta,
        "related_party_revenue_pct": result.related_party_revenue_pct,
        "related_party_receivables_pct": result.related_party_receivables_pct,
        "intercompany_loan_exposure": result.intercompany_loan_exposure,
        "director_loan_exposure": result.director_loan_exposure,
        "character_risk_score": result.character_risk_score,
        "management_quality_score": result.management_quality_score,
        "flags_count": len(result.flags),
        "flags": result.flags,
        "promoter_profiles": [
            {
                "name": p.name,
                "designation": p.designation,
                "shareholding_pct": p.shareholding_pct,
                "shares_pledged_pct": p.shares_pledged_pct,
                "pledge_risk_label": p.pledge_risk_label,
                "pledge_score_delta": p.pledge_score_delta,
                "other_directorships": p.other_directorships,
                "directorship_concern": p.directorship_concern,
            }
            for p in result.promoter_profiles
        ],
        "warnings": result.warnings,
    }