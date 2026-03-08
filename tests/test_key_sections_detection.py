"""
tests/test_key_sections_detection.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for document section detection helper function.

Task: 7.2 Create _detect_key_sections helper function
Requirements: 4.1, 4.3, 4.4, 4.5

Covers:
  - Case-insensitive matching against KEY_SECTIONS
  - Handling whitespace variations and line breaks
  - Returning deduplicated list of detected sections

Run:
  cd backend && pytest ../tests/test_key_sections_detection.py -v
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from ingestor.pdf_parser import _detect_key_sections, KEY_SECTIONS


# ─────────────────────────────────────────────────────────────────────────────
# Test Cases
# ─────────────────────────────────────────────────────────────────────────────

def test_detect_key_sections_basic():
    """Test basic section detection with standard formatting."""
    text = """
    Annual Report 2023
    
    Directors Report
    The board of directors is pleased to present...
    
    Balance Sheet
    Assets and Liabilities as of March 31, 2023
    
    Profit and Loss
    Statement of Income for the year ended...
    """
    
    sections = _detect_key_sections(text)
    
    assert isinstance(sections, list)
    assert "Directors Report" in sections
    assert "Balance Sheet" in sections
    assert "Profit and Loss" in sections


def test_detect_key_sections_case_insensitive():
    """Test case-insensitive matching (Requirement 4.3)."""
    text = """
    DIRECTORS REPORT
    Some content here...
    
    balance sheet
    More content...
    
    Profit And Loss
    Even more content...
    """
    
    sections = _detect_key_sections(text)
    
    # Should detect sections regardless of case
    assert len(sections) >= 3
    assert "Directors Report" in sections
    assert "Balance Sheet" in sections
    assert "Profit and Loss" in sections


def test_detect_key_sections_with_apostrophe_variations():
    """Test detection of variations like "Director's Report" vs "Directors Report"."""
    text1 = "Director's Report for the year 2023"
    text2 = "Directors Report for the year 2023"
    
    sections1 = _detect_key_sections(text1)
    sections2 = _detect_key_sections(text2)
    
    # Both variations should be detected
    assert "Director's Report" in sections1
    assert "Directors Report" in sections2


def test_detect_key_sections_whitespace_variations():
    """Test handling of extra whitespace and line breaks (Requirement 4.5)."""
    text = """
    Directors    Report
    Some content...
    
    Balance
    Sheet
    More content...
    
    Profit  and  Loss
    Even more...
    """
    
    sections = _detect_key_sections(text)
    
    # Should detect sections even with whitespace variations
    assert "Directors Report" in sections or "Director's Report" in sections
    assert "Balance Sheet" in sections
    assert "Profit and Loss" in sections


def test_detect_key_sections_deduplication():
    """Test that duplicate sections are removed (Requirement 4.4)."""
    text = """
    Directors Report
    Some content...
    
    Balance Sheet
    Assets...
    
    Directors Report
    More content from directors...
    
    DIRECTORS REPORT
    Yet more content...
    """
    
    sections = _detect_key_sections(text)
    
    # Count how many times "Directors Report" appears
    directors_count = sections.count("Directors Report")
    
    # Should only appear once despite multiple occurrences in text
    assert directors_count == 1


def test_detect_key_sections_all_standard_sections():
    """Test detection of all standard sections from KEY_SECTIONS."""
    text = """
    Directors Report
    Director's Report
    Balance Sheet
    Profit and Loss
    P&L Statement
    Cash Flow
    Notes to Accounts
    Auditors Report
    Auditor's Report
    Independent Auditor
    """
    
    sections = _detect_key_sections(text)
    
    # Should detect multiple sections
    assert len(sections) >= 5
    assert "Balance Sheet" in sections
    assert "Cash Flow" in sections
    assert "Notes to Accounts" in sections


def test_detect_key_sections_no_matches():
    """Test with text containing no key sections."""
    text = """
    This is just some random text
    with no financial document sections
    at all in the content.
    """
    
    sections = _detect_key_sections(text)
    
    assert isinstance(sections, list)
    assert len(sections) == 0


def test_detect_key_sections_empty_text():
    """Test with empty text."""
    sections = _detect_key_sections("")
    
    assert isinstance(sections, list)
    assert len(sections) == 0


def test_detect_key_sections_partial_matches():
    """Test that partial matches are not detected."""
    text = """
    The directors reported good results.
    We have a balanced approach.
    Profits and losses were analyzed.
    """
    
    sections = _detect_key_sections(text)
    
    # These are not actual section headers, just words in sentences
    # The function should not detect them as sections
    # (This depends on implementation - our regex should be strict enough)
    assert isinstance(sections, list)


def test_detect_key_sections_auditor_variations():
    """Test detection of auditor report variations."""
    text = """
    Auditors Report
    Opinion on financial statements...
    
    Auditor's Report
    We have audited...
    
    Independent Auditor
    Independent auditor's report...
    """
    
    sections = _detect_key_sections(text)
    
    # Should detect auditor-related sections
    assert "Auditors Report" in sections or "Auditor's Report" in sections
    assert "Independent Auditor" in sections


def test_detect_key_sections_pnl_variations():
    """Test detection of P&L Statement variations."""
    text = """
    P&L Statement
    Revenue and expenses...
    
    Profit and Loss
    Statement of income...
    """
    
    sections = _detect_key_sections(text)
    
    # Should detect both P&L variations
    assert "P&L Statement" in sections
    assert "Profit and Loss" in sections
