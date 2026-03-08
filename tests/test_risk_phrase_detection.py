"""
Tests for risk phrase detection functionality.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
"""

import pytest
from backend.ingestor.pdf_parser import _detect_risk_phrases, RISK_KEYWORDS


def test_detect_risk_phrases_basic():
    """Test basic risk phrase detection with single keyword."""
    page_texts = [
        "This is page 1 with no risk phrases.",
        "This document mentions litigation on page 2.",
        "Page 3 is clean."
    ]
    
    result = _detect_risk_phrases(page_texts)
    
    assert len(result) == 1
    assert result[0]['phrase'] == 'litigation'
    assert result[0]['page'] == 2


def test_detect_risk_phrases_case_insensitive():
    """Test case-insensitive matching (Requirement 5.3)."""
    page_texts = [
        "This document mentions LITIGATION in uppercase.",
        "Another page with Litigation in mixed case.",
        "And litigation in lowercase."
    ]
    
    result = _detect_risk_phrases(page_texts)
    
    # Should only return one entry due to deduplication
    assert len(result) == 1
    assert result[0]['phrase'] == 'litigation'
    assert result[0]['page'] == 1


def test_detect_risk_phrases_multiple_keywords():
    """Test detection of multiple different risk keywords."""
    page_texts = [
        "The company is facing litigation.",
        "There is a case in NCLT.",
        "The loan has been declared as NPA.",
        "Clean page with no risks."
    ]
    
    result = _detect_risk_phrases(page_texts)
    
    assert len(result) == 3
    phrases = [r['phrase'] for r in result]
    assert 'litigation' in phrases
    assert 'NCLT' in phrases
    assert 'NPA' in phrases


def test_detect_risk_phrases_deduplication():
    """Test that duplicate phrases are deduplicated (Requirement 5.4)."""
    page_texts = [
        "First mention of default on page 1.",
        "Second mention of default on page 2.",
        "Third mention of DEFAULT on page 3."
    ]
    
    result = _detect_risk_phrases(page_texts)
    
    # Should only return one entry despite multiple occurrences
    assert len(result) == 1
    assert result[0]['phrase'] == 'default'
    assert result[0]['page'] == 1  # First occurrence


def test_detect_risk_phrases_page_numbers():
    """Test that page numbers are correctly tracked (Requirement 5.5)."""
    page_texts = [
        "Clean page 1.",
        "Clean page 2.",
        "Page 3 mentions insolvency.",
        "Clean page 4.",
        "Page 5 mentions bankruptcy."
    ]
    
    result = _detect_risk_phrases(page_texts)
    
    assert len(result) == 2
    
    # Find insolvency entry
    insolvency_entry = next(r for r in result if r['phrase'] == 'insolvency')
    assert insolvency_entry['page'] == 3
    
    # Find bankruptcy entry
    bankruptcy_entry = next(r for r in result if r['phrase'] == 'bankruptcy')
    assert bankruptcy_entry['page'] == 5


def test_detect_risk_phrases_empty_pages():
    """Test handling of empty page texts."""
    page_texts = ["", "", ""]
    
    result = _detect_risk_phrases(page_texts)
    
    assert len(result) == 0


def test_detect_risk_phrases_no_matches():
    """Test when no risk phrases are found."""
    page_texts = [
        "This is a normal financial document.",
        "It contains balance sheet information.",
        "And profit and loss statements."
    ]
    
    result = _detect_risk_phrases(page_texts)
    
    assert len(result) == 0


def test_detect_risk_phrases_multi_word_keywords():
    """Test detection of multi-word risk keywords."""
    page_texts = [
        "The company received a show cause notice.",
        "There was regulatory action taken.",
        "The account is non-performing."
    ]
    
    result = _detect_risk_phrases(page_texts)
    
    assert len(result) == 3
    phrases = [r['phrase'] for r in result]
    assert 'show cause' in phrases
    assert 'regulatory action' in phrases
    assert 'non-performing' in phrases


def test_risk_keywords_constant():
    """Test that RISK_KEYWORDS constant contains all required keywords (Requirement 5.2)."""
    required_keywords = [
        "litigation", "NCLT", "NPA", "non-performing", "default",
        "winding up", "insolvency", "bankruptcy", "dishonour",
        "dishonored", "penalty", "show cause", "regulatory action", "fraud"
    ]
    
    for keyword in required_keywords:
        assert keyword in RISK_KEYWORDS, f"Missing required keyword: {keyword}"
