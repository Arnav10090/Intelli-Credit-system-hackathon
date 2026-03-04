"""
ingestor/covenant_extractor.py
─────────────────────────────────────────────────────────────────────────────
Extracts financial covenants, loan terms, and risk phrases from document text.

Used on: annual report notes, sanction letters, rating reports, legal notices.

All extraction is DETERMINISTIC regex — no LLM.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

from config import LEXICON_PATH


# ── Covenant Regex Patterns ────────────────────────────────────────────────────
# Each pattern captures the numeric value after the label.
# Using named groups for clarity.

COVENANT_PATTERNS = {
    "dscr_covenant": [
        r"(?:DSCR|debt service coverage ratio)[^\d]{0,40}(?:minimum|min\.?|not less than|>=|>)\s*([\d]+\.?[\d]*)",
        r"(?:DSCR|debt service coverage)[^\d]{0,30}([\d]+\.[\d]+)",
    ],
    "current_ratio_covenant": [
        r"current ratio[^\d]{0,30}(?:minimum|min\.?|not less than)\s*([\d]+\.?[\d]*)",
        r"current ratio[^\d]{0,20}([\d]+\.[\d]+)",
    ],
    "de_ratio_covenant": [
        r"(?:debt.equity|D/E ratio|leverage ratio)[^\d]{0,30}(?:maximum|max\.?|not more than|<=|<)\s*([\d]+\.?[\d]*)",
        r"(?:debt.equity|D/E ratio)[^\d]{0,20}([\d]+\.?[\d]*)",
    ],
    "net_worth_covenant": [
        r"(?:net worth|tangible net worth)[^\d]{0,40}(?:minimum|min\.?|not less than)\s*"
        r"(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:crore|cr|lakh)?",
    ],
    "interest_coverage_covenant": [
        r"(?:interest coverage|ICR)[^\d]{0,30}(?:minimum|min\.?|not less than)\s*([\d]+\.?[\d]*)",
    ],
    "loan_amount": [
        r"(?:sanctioned amount|sanction limit|loan amount|credit facility)[^\d]{0,30}"
        r"(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:crore|cr\.?|lakh|lac)?",
    ],
    "interest_rate": [
        r"(?:interest rate|rate of interest|ROI|pricing)[^\d]{0,30}([\d]+\.?[\d]*)\s*%\s*(?:p\.a\.?|per annum)?",
        r"([\d]+\.[\d]+)\s*%\s*(?:p\.a\.?|per annum)",
    ],
    "repayment_tenor": [
        r"(?:repayment period|tenor|tenure|repayable in)[^\d]{0,20}([\d]+)\s*(?:years?|months?|quarterly instalments?)",
    ],
    "moratorium": [
        r"moratorium[^\d]{0,20}([\d]+)\s*(?:months?|years?)",
    ],
    "ltv_ratio": [
        r"(?:LTV|loan to value)[^\d]{0,20}([\d]+\.?[\d]*)\s*%",
    ],
}

# Audit qualification patterns
AUDIT_QUALIFICATION_PATTERNS = [
    r"(?:subject to|except for|qualified opinion|adverse opinion)",
    r"(?:material uncertainty|going concern|substantial doubt)",
    r"(?:emphasis of matter|other matter paragraph)",
    r"(?:qualified audit|audit qualification|qualified report)",
    r"(?:auditor.*resigned|resignation of.*auditor)",
    r"(?:statutory auditor.*change|change.*statutory auditor)",
]

# Related party transaction patterns
RELATED_PARTY_PATTERNS = [
    r"(?:loans to directors?|advances to promoters?|loan.*related party)",
    r"(?:related party.*outstanding|outstanding.*related party)",
    r"(?:inter company|intercompany|group company.*loan)",
]


@dataclass
class CovenantResult:
    """Extracted covenants and loan terms from a document."""
    doc_id: str
    covenants: dict           # {covenant_name: value}
    loan_terms: dict          # {term_name: value}
    audit_flags: list[str]    # Audit qualification phrases found
    related_party_flags: list[str]
    raw_matches: list[dict]   # For audit trail: {field, pattern, raw_text, value}
    warnings: list[str] = field(default_factory=list)


def extract_covenants(doc_id: str, text: str) -> CovenantResult:
    """
    Extract all financial covenants and loan terms from document text.
    Input: full text string from pdf_parser.py
    """
    logger.info("Extracting covenants for doc_id=%s", doc_id)

    # Normalise whitespace
    text_clean = re.sub(r"\s+", " ", text)

    covenants   = {}
    loan_terms  = {}
    raw_matches = []

    # Separate targets for covenants vs loan terms
    covenant_fields = {"dscr_covenant", "current_ratio_covenant",
                       "de_ratio_covenant", "net_worth_covenant",
                       "interest_coverage_covenant"}
    loan_term_fields = {"loan_amount", "interest_rate",
                        "repayment_tenor", "moratorium", "ltv_ratio"}

    for field_name, patterns in COVENANT_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                raw_val = match.group(1).replace(",", "")
                try:
                    value = float(raw_val)
                    raw_matches.append({
                        "field": field_name,
                        "pattern": pattern[:60] + "...",
                        "raw_text": match.group(0)[:100],
                        "value": value,
                    })
                    if field_name in covenant_fields:
                        covenants[field_name] = value
                    else:
                        loan_terms[field_name] = value
                    break  # First match wins per field
                except ValueError:
                    continue

    # Audit qualification detection
    audit_flags = []
    for pattern in AUDIT_QUALIFICATION_PATTERNS:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            start = max(0, match.start() - 50)
            end   = min(len(text_clean), match.end() + 100)
            context = text_clean[start:end].strip()
            audit_flags.append(context)

    # Related party detection
    rp_flags = []
    for pattern in RELATED_PARTY_PATTERNS:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            start = max(0, match.start() - 30)
            end   = min(len(text_clean), match.end() + 100)
            context = text_clean[start:end].strip()
            rp_flags.append(context)

    result = CovenantResult(
        doc_id=doc_id,
        covenants=covenants,
        loan_terms=loan_terms,
        audit_flags=audit_flags,
        related_party_flags=rp_flags,
        raw_matches=raw_matches,
    )

    logger.info(
        "Covenant extraction: %d covenants, %d loan terms, %d audit flags",
        len(covenants), len(loan_terms), len(audit_flags)
    )
    return result


def result_to_dict(result: CovenantResult) -> dict:
    return {
        "doc_id": result.doc_id,
        "covenants": result.covenants,
        "loan_terms": result.loan_terms,
        "audit_flags": result.audit_flags,
        "related_party_flags": result.related_party_flags,
        "raw_matches": result.raw_matches,
        "warnings": result.warnings,
    }