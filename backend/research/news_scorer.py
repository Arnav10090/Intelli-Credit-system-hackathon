"""
research/news_scorer.py
─────────────────────────────────────────────────────────────────────────────
Keyword-based risk scoring engine for news articles, MCA filings,
eCourt judgements, and BSE disclosures.

Strategy:
  1. Load the 150+ phrase lexicon from data/litigation_lexicon.json
  2. For each text: scan for tier_1/tier_2/tier_3/positive_signals phrases
  3. Apply negation detection (avoid "no winding up petition" scoring negatively)
  4. Compute aggregate risk_score_delta and risk_tier
  5. Return structured ScoredArticle ready for database storage

NO LLM used here. Pure deterministic keyword matching.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from config import LEXICON_PATH


# ── Data Structures ────────────────────────────────────────────────────────────

@dataclass
class ScoredArticle:
    """A news article / filing scored for credit risk."""
    title:            str
    url:              str
    source_name:      str
    published_date:   Optional[str]       # ISO date string
    raw_text:         str
    result_type:      str                 # news_article | mca_filing | ecourts_case | bse_disclosure

    # Scoring output
    risk_tier:        Optional[int]       # 1=Critical, 2=High, 3=Monitor, None=Neutral/Positive
    risk_score_delta: int                 # Negative = risk, Positive = good signal
    matched_keywords: list[str]
    is_cached:        bool = False


# ── Tier score maps ────────────────────────────────────────────────────────────
TIER_DELTA = {
    "tier_1":          -30,
    "tier_2":          -15,
    "tier_3":           -5,
    "positive_signals": +5,
}

TIER_NUMBER = {
    "tier_1": 1,
    "tier_2": 2,
    "tier_3": 3,
    "positive_signals": None,
}

# Negation window: words before the phrase that negate it
NEGATION_WORDS = [
    "no ", "not ", "never ", "without ", "absence of ",
    "nil ", "dismissed ", "withdrawn ", "settled ",
    "vacated ", "quashed ", "no outstanding ",
]


# ── Main Scoring Function ─────────────────────────────────────────────────────

def score_text(
    title: str,
    body: str,
    url: str = "",
    source_name: str = "",
    published_date: str | None = None,
    result_type: str = "news_article",
    is_cached: bool = False,
) -> ScoredArticle:
    """
    Score a single piece of text (headline + body) for credit risk.
    Returns a ScoredArticle ready for database persistence.
    """
    combined_text = f"{title} {body}"
    lexicon       = _load_lexicon()

    matched_keywords : list[str] = []
    total_delta      : int       = 0
    worst_tier       : Optional[int] = None

    for tier_key in ("tier_1", "tier_2", "tier_3", "positive_signals"):
        tier_data   = lexicon.get(tier_key, {})
        tier_delta  = tier_data.get("score_delta", TIER_DELTA.get(tier_key, 0))
        tier_number = TIER_NUMBER.get(tier_key)

        for phrase in tier_data.get("phrases", []):
            phrase_lower = phrase.lower()
            pattern      = re.compile(re.escape(phrase_lower), re.IGNORECASE)
            matches      = list(pattern.finditer(combined_text.lower()))

            if not matches:
                continue

            # Negation check: look at 40 chars before first match
            first_match  = matches[0]
            pre_context  = combined_text[
                max(0, first_match.start() - 40) : first_match.start()
            ].lower()

            if any(neg in pre_context for neg in NEGATION_WORDS):
                continue

            matched_keywords.append(phrase)
            total_delta += tier_delta

            # Track worst tier (1 is worst)
            if tier_number is not None:
                if worst_tier is None or tier_number < worst_tier:
                    worst_tier = tier_number

    # Determine final risk_tier
    # If only positive signals matched → tier = None
    # If mixed → tier = worst negative tier found
    final_tier = worst_tier   # None if only positive or no matches

    return ScoredArticle(
        title=title,
        url=url,
        source_name=source_name,
        published_date=published_date,
        raw_text=body[:2000],    # Truncate for storage
        result_type=result_type,
        risk_tier=final_tier,
        risk_score_delta=total_delta,
        matched_keywords=list(set(matched_keywords)),   # Deduplicate
        is_cached=is_cached,
    )


def score_mca_filing(
    form_type: str,
    description: str,
    filing_date: str | None,
    url: str = "",
    risk_flag: bool = False,
    notes: str = "",
    is_cached: bool = False,
) -> ScoredArticle:
    """
    Score an MCA (Registrar of Companies) filing.
    AOC-4 with Emphasis of Matter, CHG-1 on proposed security = risk flags.
    """
    title = f"MCA Filing: {form_type} — {description[:60]}"
    body  = f"{description} {notes}"

    if form_type == "AOC-4" and risk_flag:
        # Auditor Emphasis of Matter / qualification in annual accounts
        body += " auditor emphasis of matter going concern audit observation"

    if form_type in ("CHG-1", "CHG-9") and risk_flag:
        # Charge creation on proposed security
        body += " charge creation encumbrance lien pledge existing charge"

    scored = score_text(
        title=title, body=body,
        url=url, source_name="MCA21",
        published_date=filing_date,
        result_type="mca_filing",
        is_cached=is_cached,
    )

    # AOC-4 risk flag always gets at least tier_3
    if risk_flag and scored.risk_tier is None:
        scored.risk_tier        = 3
        scored.risk_score_delta = -5
        scored.matched_keywords.append("audit_observation_manual")

    return scored


def score_ecourt_case(
    case_type:    str,
    case_number:  str,
    court:        str,
    status:       str,
    amount_cr:    float,
    risk_tier:    int,
    url:          str = "",
    is_cached:    bool = False,
) -> ScoredArticle:
    """
    Score an eCourts finding.
    IBC Section 9 / Section 7 = Critical (Tier 1).
    """
    title = f"{court}: {case_type} [{case_number}]"
    body  = (
        f"{case_type} {case_number} {court} {status} "
        f"amount {amount_cr} crore "
    )

    # Add tier-appropriate keywords for the scorer to pick up
    if risk_tier == 1:
        body += "NCLT proceedings IBC petition winding up operational creditor "
    elif risk_tier == 2:
        body += "civil suit arbitration recovery of dues "
    else:
        body += "minor litigation pending "

    scored = score_text(
        title=title, body=body,
        url=url, source_name="eCourts India",
        result_type="ecourts_case",
        is_cached=is_cached,
    )

    # Force tier from explicit risk_tier (eCourts data is pre-classified)
    scored.risk_tier        = risk_tier
    scored.risk_score_delta = TIER_DELTA.get(f"tier_{risk_tier}", -5)

    return scored


def aggregate_scores(articles: list[ScoredArticle]) -> dict:
    """
    Aggregate all scored articles into a summary for the scoring engine.
    Returns the same structure as research_cache.json aggregate_risk_score.
    """
    total_news_delta    = sum(
        a.risk_score_delta for a in articles if a.result_type == "news_article"
    )
    total_ecourt_delta  = sum(
        a.risk_score_delta for a in articles if a.result_type == "ecourts_case"
    )
    mca_risk_count      = sum(
        1 for a in articles
        if a.result_type == "mca_filing" and a.risk_tier is not None
    )
    total_delta         = sum(a.risk_score_delta for a in articles)

    if total_delta <= -60:
        label = "CRITICAL"
    elif total_delta <= -30:
        label = "HIGH"
    elif total_delta <= -10:
        label = "MEDIUM"
    elif total_delta < 0:
        label = "LOW"
    else:
        label = "CLEAN"

    return {
        "total_news_risk_delta":    total_news_delta,
        "total_ecourts_risk_delta": total_ecourt_delta,
        "total_mca_risk_notes":     mca_risk_count,
        "total_risk_delta":         total_delta,
        "overall_research_risk_label": label,
        "article_count":            len(articles),
        "tier1_count":              sum(1 for a in articles if a.risk_tier == 1),
        "tier2_count":              sum(1 for a in articles if a.risk_tier == 2),
        "tier3_count":              sum(1 for a in articles if a.risk_tier == 3),
    }


# ── Lexicon loader ─────────────────────────────────────────────────────────────

_lexicon_cache: dict | None = None

def _load_lexicon() -> dict:
    """Load and cache the litigation lexicon."""
    global _lexicon_cache
    if _lexicon_cache is not None:
        return _lexicon_cache
    try:
        with open(LEXICON_PATH) as f:
            _lexicon_cache = json.load(f)
    except Exception as e:
        logger.error("Failed to load lexicon: %s", e)
        _lexicon_cache = {}
    return _lexicon_cache


def scored_to_dict(article: ScoredArticle) -> dict:
    """Serialise ScoredArticle for API responses."""
    return {
        "title":             article.title,
        "url":               article.url,
        "source_name":       article.source_name,
        "published_date":    article.published_date,
        "result_type":       article.result_type,
        "risk_tier":         article.risk_tier,
        "risk_score_delta":  article.risk_score_delta,
        "matched_keywords":  article.matched_keywords,
        "is_cached":         article.is_cached,
    }