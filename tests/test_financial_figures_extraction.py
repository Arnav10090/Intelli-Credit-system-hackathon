"""
tests/test_financial_figures_extraction.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for financial figure extraction with currency patterns.

Tests the CURRENCY_PATTERN regex and _extract_financial_figures helper function
to ensure they correctly identify and extract financial figures with context.

Requirements tested: 3.1, 3.2, 3.3, 3.4, 3.5
──────────────────────────────────────────────────────────────────────────────
"""

import pytest
from backend.ingestor.pdf_parser import _extract_financial_figures, CURRENCY_PATTERN
import re


class TestCurrencyPattern:
    """Test the CURRENCY_PATTERN regex matches expected formats."""
    
    def test_rupee_symbol_with_amount(self):
        """Test matching ₹ symbol with numeric value."""
        text = "The total amount is ₹ 1,234.56 for this year."
        match = re.search(CURRENCY_PATTERN, text, re.IGNORECASE)
        assert match is not None
        assert "₹" in match.group(0)
        assert "1,234.56" in match.group(0)
    
    def test_rs_with_period(self):
        """Test matching Rs. with numeric value."""
        text = "Payment of Rs. 50,000 was made."
        match = re.search(CURRENCY_PATTERN, text, re.IGNORECASE)
        assert match is not None
        assert "Rs." in match.group(0)
        assert "50,000" in match.group(0)
    
    def test_rs_without_period(self):
        """Test matching Rs without period."""
        text = "The cost is Rs 25000 only."
        match = re.search(CURRENCY_PATTERN, text, re.IGNORECASE)
        assert match is not None
        assert "Rs" in match.group(0)
        assert "25000" in match.group(0)
    
    def test_inr_prefix(self):
        """Test matching INR prefix."""
        text = "Total revenue: INR 5,00,000.00"
        match = re.search(CURRENCY_PATTERN, text, re.IGNORECASE)
        assert match is not None
        assert "INR" in match.group(0)
    
    def test_crore_suffix(self):
        """Test matching amounts with Crore suffix."""
        text = "Revenue of ₹ 100 Crore was reported."
        match = re.search(CURRENCY_PATTERN, text, re.IGNORECASE)
        assert match is not None
        assert "Crore" in match.group(0)
    
    def test_cr_suffix(self):
        """Test matching amounts with Cr suffix."""
        text = "Total assets: Rs. 50 Cr"
        match = re.search(CURRENCY_PATTERN, text, re.IGNORECASE)
        assert match is not None
        assert "Cr" in match.group(0)
    
    def test_lakh_suffix(self):
        """Test matching amounts with Lakh suffix."""
        text = "Profit: INR 5.5 Lakh"
        match = re.search(CURRENCY_PATTERN, text, re.IGNORECASE)
        assert match is not None
        assert "Lakh" in match.group(0)
    
    def test_lac_suffix(self):
        """Test matching amounts with Lac suffix."""
        text = "Amount: ₹ 10 Lac"
        match = re.search(CURRENCY_PATTERN, text, re.IGNORECASE)
        assert match is not None
        assert "Lac" in match.group(0)


class TestExtractFinancialFigures:
    """Test the _extract_financial_figures helper function."""
    
    def test_extract_single_figure(self):
        """Test extracting a single financial figure."""
        text = "The company reported revenue of ₹ 1,234.56 for the quarter."
        result = _extract_financial_figures(text)
        
        assert result['count'] == 1
        assert len(result['figures']) == 1
        assert '₹' in result['figures'][0]['value']
        assert '1,234.56' in result['figures'][0]['value']
        assert 'revenue' in result['figures'][0]['context'].lower()
    
    def test_extract_multiple_figures(self):
        """Test extracting multiple financial figures."""
        text = """
        Revenue: ₹ 100 Crore
        Profit: Rs. 50 Lakh
        Assets: INR 200 Crore
        """
        result = _extract_financial_figures(text)
        
        assert result['count'] == 3
        assert len(result['figures']) == 3
    
    def test_context_extraction(self):
        """Test that context includes 20 chars before and after."""
        text = "ABCDEFGHIJKLMNOPQRST₹ 1,000UVWXYZ0123456789AB"
        result = _extract_financial_figures(text)
        
        assert result['count'] == 1
        context = result['figures'][0]['context']
        # Should include 20 chars before and after the match
        assert 'ABCDEFGHIJKLMNOPQRST' in context
        assert 'UVWXYZ0123456789AB' in context
    
    def test_no_figures_found(self):
        """Test when no financial figures are present."""
        text = "This is a document with no currency values."
        result = _extract_financial_figures(text)
        
        assert result['count'] == 0
        assert len(result['figures']) == 0
    
    def test_case_insensitive_matching(self):
        """Test that pattern matching is case-insensitive."""
        text = "Amount: rs. 1000 and also RS. 2000 and Rs. 3000"
        result = _extract_financial_figures(text)
        
        # Should match all three variations
        assert result['count'] == 3
    
    def test_various_formats(self):
        """Test various Indian currency formats."""
        text = """
        Format 1: ₹ 1,234.56
        Format 2: Rs. 10 Crore
        Format 3: INR 5.5 Lakh
        Format 4: Rs 25000
        Format 5: ₹ 100 Cr
        Format 6: Rs. 50 Lac
        """
        result = _extract_financial_figures(text)
        
        assert result['count'] == 6
        assert len(result['figures']) == 6
    
    def test_figures_list_structure(self):
        """Test that each figure has correct structure."""
        text = "Payment of ₹ 1,000 was made."
        result = _extract_financial_figures(text)
        
        assert 'figures' in result
        assert 'count' in result
        assert isinstance(result['figures'], list)
        assert isinstance(result['count'], int)
        
        if result['figures']:
            figure = result['figures'][0]
            assert 'value' in figure
            assert 'context' in figure
            assert isinstance(figure['value'], str)
            assert isinstance(figure['context'], str)
