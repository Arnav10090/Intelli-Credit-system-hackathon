"""
ingestor/document_classifier.py
─────────────────────────────────────────────────────────────────────────────
Intelligent document classification for the 5 critical document types required
by the hackathon challenge:

1. ALM (Asset-Liability Management)
2. Shareholding Pattern
3. Borrowing Profile
4. Annual Reports (P&L, Cashflow, Balance Sheet)
5. Portfolio Cuts/Performance Data

Uses deterministic pattern matching + confidence scoring.
NO LLM - fully explainable classification logic.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of document classification."""
    doc_type: str  # One of: alm, shareholding, borrowing, annual_report, portfolio, unknown
    confidence: float  # 0.0 to 1.0
    matched_patterns: list[str]  # Which patterns triggered the classification
    suggested_schema: dict  # Suggested extraction schema for this doc type
    requires_human_review: bool  # True if confidence < 0.7


# Classification patterns for each document type
# Each pattern has: (regex, weight, description)
CLASSIFICATION_PATTERNS = {
    "alm": [
        (r"asset\s+liability\s+management", 0.4, "ALM title"),
        (r"maturity\s+profile", 0.3, "Maturity profile section"),
        (r"liquidity\s+gap", 0.3, "Liquidity gap analysis"),
        (r"duration\s+gap", 0.2, "Duration gap"),
        (r"repricing\s+gap", 0.2, "Repricing gap"),
        (r"bucket\s+analysis", 0.2, "Bucket analysis"),
        (r"residual\s+maturity", 0.2, "Residual maturity"),
    ],
    "shareholding": [
        (r"shareholding\s+pattern", 0.5, "Shareholding pattern title"),
        (r"promoter\s+holding", 0.3, "Promoter holding"),
        (r"public\s+shareholding", 0.2, "Public shareholding"),
        (r"pledged\s+shares", 0.3, "Pledged shares"),
        (r"category\s+of\s+shareholders", 0.2, "Shareholder categories"),
        (r"non-promoter\s+holding", 0.2, "Non-promoter holding"),
    ],
    "borrowing": [
        (r"borrowing\s+profile", 0.4, "Borrowing profile title"),
        (r"debt\s+schedule", 0.3, "Debt schedule"),
        (r"loan\s+details", 0.2, "Loan details"),
        (r"sanction\s+letter", 0.3, "Sanction letter"),
        (r"credit\s+facility", 0.2, "Credit facility"),
        (r"term\s+loan", 0.2, "Term loan"),
        (r"working\s+capital\s+limit", 0.2, "Working capital limit"),
        (r"outstanding\s+debt", 0.2, "Outstanding debt"),
    ],
    "annual_report": [
        (r"annual\s+report", 0.5, "Annual report title"),
        (r"balance\s+sheet", 0.3, "Balance sheet"),
        (r"profit\s+and\s+loss", 0.3, "P&L statement"),
        (r"cash\s+flow\s+statement", 0.3, "Cash flow statement"),
        (r"director'?s\s+report", 0.3, "Directors report"),
        (r"auditor'?s\s+report", 0.3, "Auditors report"),
        (r"notes\s+to\s+accounts", 0.2, "Notes to accounts"),
        (r"financial\s+statements", 0.2, "Financial statements"),
    ],
    "portfolio": [
        (r"portfolio\s+performance", 0.4, "Portfolio performance title"),
        (r"asset\s+quality", 0.3, "Asset quality"),
        (r"npa\s+ratio", 0.3, "NPA ratio"),
        (r"gross\s+npa", 0.2, "Gross NPA"),
        (r"net\s+npa", 0.2, "Net NPA"),
        (r"provision\s+coverage", 0.2, "Provision coverage"),
        (r"loan\s+book", 0.2, "Loan book"),
        (r"disbursement", 0.2, "Disbursement"),
    ],
}


def classify_document(text: str, filename: str) -> ClassificationResult:
    """
    Classify a document into one of the 5 critical types.
    
    Args:
        text: Extracted text from the document
        filename: Original filename (used as secondary signal)
        
    Returns:
        ClassificationResult with doc_type, confidence, and matched patterns
    """
    logger.info(f"Classifying document: {filename}")
    
    # Normalize text for matching
    text_lower = text.lower()
    filename_lower = filename.lower()
    
    # Score each document type
    scores = {}
    matched_patterns_by_type = {}
    
    for doc_type, patterns in CLASSIFICATION_PATTERNS.items():
        score = 0.0
        matched = []
        
        # Check text patterns
        for pattern, weight, description in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                score += weight
                matched.append(description)
        
        # Filename bonus (0.2 if filename contains doc type keyword)
        if doc_type in filename_lower or _get_filename_keywords(doc_type, filename_lower):
            score += 0.2
            matched.append(f"Filename contains '{doc_type}' keyword")
        
        scores[doc_type] = min(score, 1.0)  # Cap at 1.0
        matched_patterns_by_type[doc_type] = matched
    
    # Find best match
    if not scores or max(scores.values()) == 0:
        return ClassificationResult(
            doc_type="unknown",
            confidence=0.0,
            matched_patterns=[],
            suggested_schema={},
            requires_human_review=True,
        )
    
    best_type = max(scores, key=scores.get)
    confidence = scores[best_type]
    matched = matched_patterns_by_type[best_type]
    
    logger.info(
        f"Classification result: {best_type} (confidence={confidence:.2f}, "
        f"matched={len(matched)} patterns)"
    )
    
    return ClassificationResult(
        doc_type=best_type,
        confidence=confidence,
        matched_patterns=matched,
        suggested_schema=_get_extraction_schema(best_type),
        requires_human_review=(confidence < 0.7),
    )


def _get_filename_keywords(doc_type: str, filename: str) -> bool:
    """Check if filename contains keywords for this doc type."""
    keywords = {
        "alm": ["alm", "asset", "liability", "maturity"],
        "shareholding": ["shareholding", "share", "holding", "promoter"],
        "borrowing": ["borrowing", "debt", "loan", "sanction"],
        "annual_report": ["annual", "report", "financial", "statement"],
        "portfolio": ["portfolio", "performance", "npa", "asset"],
    }
    return any(kw in filename for kw in keywords.get(doc_type, []))


def _get_extraction_schema(doc_type: str) -> dict:
    """
    Return suggested extraction schema for each document type.
    This guides the extraction pipeline on what fields to look for.
    """
    schemas = {
        "alm": {
            "required_fields": [
                "maturity_buckets",
                "assets_by_bucket",
                "liabilities_by_bucket",
                "gap_analysis",
            ],
            "optional_fields": [
                "cumulative_gap",
                "duration_gap",
                "repricing_gap",
            ],
        },
        "shareholding": {
            "required_fields": [
                "promoter_holding_pct",
                "public_holding_pct",
                "pledged_shares_pct",
                "promoter_names",
            ],
            "optional_fields": [
                "institutional_holding",
                "retail_holding",
                "foreign_holding",
            ],
        },
        "borrowing": {
            "required_fields": [
                "lender_name",
                "loan_type",
                "sanctioned_amount",
                "outstanding_amount",
                "interest_rate",
                "maturity_date",
            ],
            "optional_fields": [
                "security_details",
                "covenants",
                "repayment_schedule",
            ],
        },
        "annual_report": {
            "required_fields": [
                "revenue",
                "ebitda",
                "pat",
                "total_assets",
                "total_liabilities",
                "net_worth",
            ],
            "optional_fields": [
                "cash_flow_operations",
                "cash_flow_investing",
                "cash_flow_financing",
            ],
        },
        "portfolio": {
            "required_fields": [
                "gross_npa_pct",
                "net_npa_pct",
                "provision_coverage_ratio",
                "total_loan_book",
            ],
            "optional_fields": [
                "disbursements",
                "collections",
                "write_offs",
            ],
        },
    }
    return schemas.get(doc_type, {})


def classify_batch(documents: list[dict]) -> list[ClassificationResult]:
    """
    Classify multiple documents at once.
    
    Args:
        documents: List of dicts with 'text' and 'filename' keys
        
    Returns:
        List of ClassificationResult objects
    """
    results = []
    for doc in documents:
        result = classify_document(doc.get("text", ""), doc.get("filename", ""))
        results.append(result)
    return results


def get_human_review_summary(results: list[ClassificationResult]) -> dict:
    """
    Generate a summary for human review of classification results.
    
    Returns:
        Dict with counts and list of documents requiring review
    """
    total = len(results)
    needs_review = [r for r in results if r.requires_human_review]
    unknown = [r for r in results if r.doc_type == "unknown"]
    
    return {
        "total_documents": total,
        "needs_review_count": len(needs_review),
        "unknown_count": len(unknown),
        "review_required": len(needs_review) > 0,
        "documents_needing_review": [
            {
                "doc_type": r.doc_type,
                "confidence": r.confidence,
                "matched_patterns": r.matched_patterns,
            }
            for r in needs_review
        ],
    }
