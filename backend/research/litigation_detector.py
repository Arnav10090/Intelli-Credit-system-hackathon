"""
research/litigation_detector.py
─────────────────────────────────────────────────────────────────────────────
Litigation Risk Detector for Intelli-Credit.

Consolidates all litigation signals from:
  1. eCourts research findings
  2. News articles mentioning legal proceedings
  3. MCA AOC-4 / qualification disclosures
  4. PDF extraction (legal_notice doc type from pdf_parser)

Outputs:
  - LitigationSummary: structured view of all proceedings
  - Aggregate risk tier (Critical / High / Medium / Low / Clean)
  - Primary trigger (worst single finding for CAM narrative)
  - Counter-factual (what resolution would change the outcome)
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Case type classification ───────────────────────────────────────────────────

# IBC / NCLT = always Tier 1 (winding up risk)
TIER_1_CASE_PATTERNS = [
    r"\bIBC\b", r"\bNCLT\b", r"section\s*9\b", r"section\s*7\b",
    r"insolvency\s+and\s+bankruptcy", r"winding\s+up\s+petition",
    r"corporate\s+insolvency\s+resolution", r"\bCIRP\b",
    r"\bDRT\b", r"debt\s+recovery\s+tribunal",
    r"SARFAESI", r"section\s*138\s+NI\s+Act",
    r"wilful\s+defaulter", r"NPA\s+classification",
]

# Recovery suits, arbitration = Tier 2
TIER_2_CASE_PATTERNS = [
    r"civil\s+suit", r"money\s+suit", r"recovery\s+of\s+dues",
    r"arbitration", r"counter\s+claim", r"commercial\s+court",
    r"summary\s+suit", r"injunction",
    r"consumer\s+complaint", r"labour\s+dispute",
]

# Minor notices = Tier 3
TIER_3_CASE_PATTERNS = [
    r"show\s+cause\s+notice", r"demand\s+notice",
    r"income\s+tax\s+demand", r"GST\s+demand",
    r"labour\s+court", r"industrial\s+dispute",
    r"consumer\s+forum",
]

# Resolved / dismissed = reduce risk
RESOLVED_PATTERNS = [
    r"dismissed", r"withdrawn", r"settled", r"vacated",
    r"quashed", r"disposed", r"closed", r"no\s+dues\s+certificate",
]


# ── Data Structures ────────────────────────────────────────────────────────────

@dataclass
class LitigationCase:
    """A single litigation case or legal proceeding."""
    source:          str       # "ecourts" | "news" | "mca" | "pdf"
    case_type:       str       # Human-readable type
    case_number:     str
    court:           str
    status:          str       # "Pending" | "Resolved" | "Unknown"
    amount_cr:       float     # Disputed amount in crores
    risk_tier:       int       # 1/2/3
    risk_score_delta:int
    is_resolved:     bool
    description:     str


@dataclass
class LitigationSummary:
    """Consolidated litigation risk summary for a case."""
    cases:               list[LitigationCase]
    total_risk_delta:    int
    worst_tier:          int     # 1=Critical, 2=High, 3=Low, 0=Clean
    aggregate_label:     str     # CRITICAL | HIGH | MEDIUM | LOW | CLEAN
    total_amount_cr:     float   # Total disputed amount (₹ Crore)
    pending_count:       int
    resolved_count:      int
    primary_trigger:     str     # Worst single case description
    resolution_path:     str     # What would clear this risk
    knockout:            bool    # True if any Tier-1 unresolved case
    warnings:            list[str] = field(default_factory=list)


# ── Main Detection Function ───────────────────────────────────────────────────

def detect_litigation(research_cache: dict) -> LitigationSummary:
    """
    Main entry point. Analyses the full research cache and returns a
    consolidated LitigationSummary.

    Called from:
      - feature_engineer.py (to compute litigation_risk feature)
      - cam/llm_narrator.py (for CAM narrative generation)
      - research_routes.py (for the /litigation endpoint)
    """
    cases    = []
    warnings = []

    # ── eCourts findings ───────────────────────────────────────────────────────
    for ec in research_cache.get("ecourts_findings", []):
        case = _parse_ecourt_finding(ec)
        if case:
            cases.append(case)

    # ── News articles with legal signals ──────────────────────────────────────
    for article in research_cache.get("news_articles", []):
        if article.get("risk_tier") in (1, 2):
            case = _parse_news_litigation(article)
            if case:
                cases.append(case)

    # ── MCA filings (AOC-4 risk flags) ────────────────────────────────────────
    for filing in research_cache.get("mca_filings", []):
        if filing.get("risk_flag"):
            case = _parse_mca_filing(filing)
            if case:
                cases.append(case)

    # ── Aggregate ─────────────────────────────────────────────────────────────
    pending  = [c for c in cases if not c.is_resolved]
    resolved = [c for c in cases if c.is_resolved]

    total_delta  = sum(c.risk_score_delta for c in pending)
    total_amount = sum(c.amount_cr for c in pending)
    worst_tier   = min((c.risk_tier for c in pending), default=0)

    if worst_tier == 1:
        label   = "CRITICAL"
        knockout = True
    elif worst_tier == 2 or total_delta <= -30:
        label   = "HIGH"
        knockout = False
    elif worst_tier == 3 or total_delta <= -10:
        label   = "MEDIUM"
        knockout = False
    elif total_delta < 0:
        label   = "LOW"
        knockout = False
    else:
        label   = "CLEAN"
        knockout = False

    # Primary trigger: worst pending case
    primary = ""
    resolution = "No significant litigation identified — no action required."

    if pending:
        worst_case = min(pending, key=lambda c: c.risk_tier)
        primary    = worst_case.description
        resolution = _generate_resolution_path(worst_case)

    return LitigationSummary(
        cases=cases,
        total_risk_delta=total_delta,
        worst_tier=worst_tier,
        aggregate_label=label,
        total_amount_cr=round(total_amount, 2),
        pending_count=len(pending),
        resolved_count=len(resolved),
        primary_trigger=primary,
        resolution_path=resolution,
        knockout=knockout,
        warnings=warnings,
    )


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_ecourt_finding(ec: dict) -> Optional[LitigationCase]:
    """Parse an eCourts finding from research_cache.json."""
    case_type = ec.get("case_type", "")
    status    = ec.get("status", "Unknown")
    is_res    = any(
        re.search(p, status, re.IGNORECASE)
        for p in RESOLVED_PATTERNS
    )
    risk_tier  = ec.get("risk_tier", 3)
    score_delta= ec.get("risk_score_delta", -5)
    amount     = float(ec.get("amount_cr", 0) or 0)

    return LitigationCase(
        source="ecourts",
        case_type=case_type,
        case_number=ec.get("case_number", ""),
        court=ec.get("court", ""),
        status=status,
        amount_cr=amount,
        risk_tier=risk_tier,
        risk_score_delta=score_delta if not is_res else 0,
        is_resolved=is_res,
        description=(
            f"{case_type} at {ec.get('court','Unknown Court')} — "
            f"₹{amount:.1f} Cr — Status: {status}"
        ),
    )


def _parse_news_litigation(article: dict) -> Optional[LitigationCase]:
    """Extract a litigation case from a risk-flagged news article."""
    title     = article.get("title", "")
    risk_tier = article.get("risk_tier", 3)
    delta     = article.get("risk_score_delta", -5)

    # Only create a case if the article mentions a specific proceeding
    legal_keywords = [
        "petition", "suit", "proceeding", "notice", "NCLT", "DRT",
        "IBC", "arbitration", "court", "tribunal", "defaulter"
    ]
    if not any(kw.lower() in title.lower() for kw in legal_keywords):
        return None

    # Estimate amount from title
    amount_match = re.search(r"₹?([\d\.]+)\s*(Cr|crore|lakh|lac)", title, re.IGNORECASE)
    amount_cr    = 0.0
    if amount_match:
        val  = float(amount_match.group(1))
        unit = amount_match.group(2).lower()
        amount_cr = val if "cr" in unit else val / 100

    return LitigationCase(
        source="news",
        case_type=f"News: {title[:60]}",
        case_number="",
        court="",
        status="Pending",
        amount_cr=amount_cr,
        risk_tier=risk_tier,
        risk_score_delta=delta,
        is_resolved=False,
        description=title[:120],
    )


def _parse_mca_filing(filing: dict) -> Optional[LitigationCase]:
    """Parse a risk-flagged MCA filing."""
    form     = filing.get("form", "")
    notes    = filing.get("notes", "")
    date_str = filing.get("filed_date", "")

    if form == "AOC-4":
        return LitigationCase(
            source="mca",
            case_type=f"AOC-4 Annual Accounts — Auditor Qualification",
            case_number=f"MCA/{form}/{date_str}",
            court="Registrar of Companies",
            status="On Record",
            amount_cr=0.0,
            risk_tier=3,
            risk_score_delta=-5,
            is_resolved=False,
            description=f"AOC-4 filed with Emphasis of Matter/qualification: {notes[:100]}",
        )

    if form in ("CHG-1", "CHG-9"):
        charge_holder = filing.get("charge_holder", "Unknown Lender")
        charge_amount = float(filing.get("charge_amount_lakhs", 0) or 0) / 100
        return LitigationCase(
            source="mca",
            case_type=f"Existing Charge on Security ({form})",
            case_number=f"MCA/{form}/{date_str}",
            court="Registrar of Companies",
            status="Subsisting",
            amount_cr=charge_amount,
            risk_tier=2,
            risk_score_delta=-10,
            is_resolved=False,
            description=(
                f"Existing charge held by {charge_holder} "
                f"(₹{charge_amount:.1f} Cr). "
                "May encumber proposed security."
            ),
        )

    return None


# ── Resolution Path Generator ─────────────────────────────────────────────────

def _generate_resolution_path(worst_case: LitigationCase) -> str:
    """Generate a plain-English path to resolve the risk."""
    if worst_case.risk_tier == 1:
        amount = worst_case.amount_cr
        return (
            f"The NCLT/IBC petition (₹{amount:.1f} Cr) is the primary obstacle. "
            "Approval can be considered only after: (a) Petition dismissed / withdrawn, "
            "OR (b) Full payment to petitioner with NOC, "
            "OR (c) Settlement agreement with NCLT order. "
            "Current recommendation: REJECT until litigation is resolved."
        )
    if worst_case.risk_tier == 2:
        return (
            f"Pending civil/arbitration proceedings (₹{worst_case.amount_cr:.1f} Cr). "
            "Provide documentary evidence of settlement or escrow of disputed amount. "
            "Partial approval may be considered with reduced exposure."
        )
    return (
        "Minor legal proceedings present. Borrower to provide status update. "
        "No block to approval — include as a monitoring condition."
    )


def summary_to_dict(summary: LitigationSummary) -> dict:
    """Serialise LitigationSummary for API responses."""
    return {
        "aggregate_label":   summary.aggregate_label,
        "worst_tier":        summary.worst_tier,
        "total_risk_delta":  summary.total_risk_delta,
        "total_amount_cr":   summary.total_amount_cr,
        "pending_count":     summary.pending_count,
        "resolved_count":    summary.resolved_count,
        "knockout":          summary.knockout,
        "primary_trigger":   summary.primary_trigger,
        "resolution_path":   summary.resolution_path,
        "cases": [
            {
                "source":         c.source,
                "case_type":      c.case_type,
                "case_number":    c.case_number,
                "court":          c.court,
                "status":         c.status,
                "amount_cr":      c.amount_cr,
                "risk_tier":      c.risk_tier,
                "risk_score_delta": c.risk_score_delta,
                "is_resolved":    c.is_resolved,
                "description":    c.description,
            }
            for c in summary.cases
        ],
        "warnings": summary.warnings,
    }