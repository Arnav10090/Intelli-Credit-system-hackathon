"""
Insight Scorer Module

This module parses qualitative insight notes and generates quantitative score adjustments
using keyword-based rules. It provides the core intelligence for translating field observations
into structured scorecard modifications.
"""

from dataclasses import dataclass, field
from typing import List

from .insight_rules import INSIGHT_RULES


@dataclass
class InsightAdjustment:
    """
    Represents a single score adjustment derived from insight notes.
    
    Attributes:
        pillar: The Five Cs pillar to adjust (Character, Capacity, Capital, Collateral, Conditions)
        delta: Point adjustment (negative or positive integer)
        reason: Human-readable explanation for the adjustment
        keywords_matched: List of keywords/phrases that triggered this adjustment
    """
    pillar: str
    delta: int
    reason: str
    keywords_matched: List[str] = field(default_factory=list)


@dataclass
class InsightScoringResult:
    """
    Structured result from parsing insight notes.
    
    Attributes:
        adjustments: List of all score adjustments generated from the notes
        total_delta: Sum of all adjustment deltas
        parsed_triggers: List of all keywords that were matched across all rules
    """
    adjustments: List[InsightAdjustment] = field(default_factory=list)
    total_delta: int = 0
    parsed_triggers: List[str] = field(default_factory=list)


def _match_keywords(notes: str, keywords: List[str]) -> List[str]:
    """
    Perform case-insensitive substring matching for keywords in notes.
    
    Args:
        notes: The insight notes text to search
        keywords: List of keyword phrases to match
    
    Returns:
        List of keywords that were found in the notes
    """
    notes_lower = notes.lower()
    matched = []
    
    for keyword in keywords:
        if keyword.lower() in notes_lower:
            matched.append(keyword)
    
    return matched


def parse_and_score(notes: str) -> InsightScoringResult:
    """
    Parse insight notes and return structured score adjustments.
    
    This function applies all configured keyword rules to the input notes,
    generating a list of score adjustments for matching keywords. Multiple
    keywords can match, and adjustments are cumulative.
    
    Args:
        notes: Free-text qualitative observations (max 5000 chars)
    
    Returns:
        InsightScoringResult containing adjustments list, total delta, and matched keywords
    
    Example:
        >>> result = parse_and_score("Factory operating at 40% capacity. Management was evasive.")
        >>> result.total_delta
        -18
        >>> len(result.adjustments)
        2
    """
    adjustments = []
    all_triggers = []
    total_delta = 0
    
    # Apply each rule from configuration
    for rule in INSIGHT_RULES:
        matched_keywords = _match_keywords(notes, rule["keywords"])
        
        if matched_keywords:
            # Create adjustment for this rule
            adjustment = InsightAdjustment(
                pillar=rule["pillar"],
                delta=rule["delta"],
                reason=rule["reason"],
                keywords_matched=matched_keywords
            )
            
            adjustments.append(adjustment)
            total_delta += rule["delta"]
            all_triggers.extend(matched_keywords)
    
    return InsightScoringResult(
        adjustments=adjustments,
        total_delta=total_delta,
        parsed_triggers=all_triggers
    )
