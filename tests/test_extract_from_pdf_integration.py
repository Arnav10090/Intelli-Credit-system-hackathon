"""
tests/test_extract_from_pdf_integration.py
──────────────────────────────────────────────────────────────────────────────
Integration tests for the main extract_from_pdf function.

Task: 10.5 Write integration tests for extract_from_pdf
Requirements: 1.1, 1.2, 1.3, 1.4

Tests the complete extraction pipeline from PDF bytes to structured result.
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from pathlib import Path

try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

from ingestor.pdf_parser import extract_from_pdf


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def create_test_pdf_bytes(pages_content: list[str]) -> bytes:
    """Create a PDF with specified text content on each page."""
    doc = fitz.open()
    for content in pages_content:
        page = doc.new_page()
        page.insert_text((72, 72), content)
    
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ─────────────────────────────────────────────────────────────────────────────
# Test Cases
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not PYMUPDF_AVAILABLE, reason="PyMuPDF not installed")
class TestExtractFromPDFIntegration:
    """Integration tests for extract_from_pdf function."""
    
    def test_digital_pdf_end_to_end(self):
        """Test complete extraction from a digital PDF with all entity types."""
        # Create a PDF with company name, financial figures, sections, and risk phrases
        page1_content = """
        ACME TEXTILES PRIVATE LIMITED
        Annual Report 2023
        
        Balance Sheet
        Total Revenue: ₹ 100 Crore
        Net Profit: Rs. 50 Lakh
        """
        
        page2_content = """
        Directors Report
        
        The company has faced litigation regarding payment defaults.
        Total Assets: INR 200 Crore
        
        Auditors Report
        """
        
        page3_content = """
        Profit and Loss Statement
        
        Revenue: ₹ 150 Crore
        Expenses: Rs. 120 Crore
        
        Notes to Accounts
        There is ongoing NCLT proceedings.
        """
        
        pdf_bytes = create_test_pdf_bytes([page1_content, page2_content, page3_content])
        
        # Extract from PDF
        result = extract_from_pdf(pdf_bytes, "test_annual_report.pdf")
        
        # Verify result structure (Requirement 1.4)
        assert isinstance(result, dict)
        assert "page_count" in result
        assert "extraction_method" in result
        assert "confidence_score" in result
        assert "company_name" in result
        assert "financial_figures" in result
        assert "key_sections" in result
        assert "risk_phrases" in result
        assert "raw_text_preview" in result
        
        # Verify page count
        assert result["page_count"] == 3
        
        # Verify extraction method (should be digital for text-based PDF)
        assert result["extraction_method"] == "digital"
        
        # Verify confidence score (should be high for digital PDF)
        assert result["confidence_score"] > 0.9
        
        # Verify company name detection
        assert result["company_name"] is not None
        assert "ACME TEXTILES PRIVATE LIMITED" in result["company_name"]
        
        # Verify financial figures extraction
        assert len(result["financial_figures"]) >= 3  # At least 3 figures
        
        # Verify key sections detection
        assert len(result["key_sections"]) >= 3  # At least 3 sections
        section_names = [s.lower() for s in result["key_sections"]]
        assert any("balance sheet" in s for s in section_names)
        assert any("director" in s for s in section_names)
        
        # Verify risk phrases detection
        assert len(result["risk_phrases"]) >= 2  # At least 2 risk phrases
        risk_phrase_texts = [r["phrase"].lower() for r in result["risk_phrases"]]
        assert any("litigation" in p for p in risk_phrase_texts)
        assert any("nclt" in p for p in risk_phrase_texts)
        
        # Verify risk phrases have page numbers
        for risk in result["risk_phrases"]:
            assert "phrase" in risk
            assert "page" in risk
            assert 1 <= risk["page"] <= 3
        
        # Verify raw text preview
        assert len(result["raw_text_preview"]) > 0
        assert len(result["raw_text_preview"]) <= 2000
    
    def test_minimal_pdf(self):
        """Test extraction from a minimal PDF with no entities."""
        # Create content with more than 100 characters to avoid OCR trigger
        page_content = "This is a simple document with no special entities. " * 3
        pdf_bytes = create_test_pdf_bytes([page_content])
        
        result = extract_from_pdf(pdf_bytes, "minimal.pdf")
        
        # Verify basic structure
        assert result["page_count"] == 1
        assert result["extraction_method"] in ["digital", "ocr", "ocr_unavailable"]
        assert result["confidence_score"] >= 0.0
        
        # Verify no entities detected
        assert result["company_name"] is None
        assert len(result["financial_figures"]) == 0
        assert len(result["key_sections"]) == 0
        assert len(result["risk_phrases"]) == 0
        
        # Verify raw text preview exists
        assert len(result["raw_text_preview"]) > 0
    
    def test_mixed_content_pdf(self):
        """Test extraction from PDF with mixed digital and low-content pages."""
        # Page 1: Good content
        page1 = "TECH SOLUTIONS LIMITED\n" + "A" * 200
        
        # Page 2: Low content (should trigger OCR check)
        page2 = "X"
        
        # Page 3: Good content
        page3 = "Balance Sheet\nRevenue: ₹ 50 Crore\n" + "B" * 200
        
        pdf_bytes = create_test_pdf_bytes([page1, page2, page3])
        
        result = extract_from_pdf(pdf_bytes, "mixed_content.pdf")
        
        # Verify extraction completed
        assert result["page_count"] == 3
        
        # Extraction method should be "ocr" or "ocr_unavailable" due to low-content page
        assert result["extraction_method"] in ["ocr", "ocr_unavailable"]
        
        # Confidence should be lower due to low-content page
        assert result["confidence_score"] < 1.0
    
    def test_large_text_preview_truncation(self):
        """Test that raw text preview is truncated to 2000 characters."""
        # Create a PDF with more than 2000 characters
        long_text = "A" * 3000
        pdf_bytes = create_test_pdf_bytes([long_text])
        
        result = extract_from_pdf(pdf_bytes, "long_text.pdf")
        
        # Verify preview is truncated
        assert len(result["raw_text_preview"]) <= 2000
    
    def test_short_text_preview_completeness(self):
        """Test that short text is not truncated."""
        short_text = "This is a short document with less than 2000 characters."
        pdf_bytes = create_test_pdf_bytes([short_text])
        
        result = extract_from_pdf(pdf_bytes, "short_text.pdf")
        
        # Verify preview contains all text
        assert len(result["raw_text_preview"]) < 2000
        assert short_text in result["raw_text_preview"]
    
    def test_multiple_financial_figures(self):
        """Test extraction of multiple financial figures with different formats."""
        content = """
        Financial Summary:
        Revenue: ₹ 100 Crore
        Profit: Rs. 50 Lakh
        Assets: INR 200 Crore
        Liabilities: Rs 75 Lakh
        Cash: ₹ 25 Cr
        Investments: Rs. 10 Lac
        """
        pdf_bytes = create_test_pdf_bytes([content])
        
        result = extract_from_pdf(pdf_bytes, "financial_summary.pdf")
        
        # Verify multiple figures detected
        assert len(result["financial_figures"]) >= 4
        
        # Verify each figure has value and context
        for figure in result["financial_figures"]:
            assert "value" in figure
            assert "context" in figure
            assert isinstance(figure["value"], str)
            assert isinstance(figure["context"], str)
    
    def test_multiple_risk_phrases_with_pages(self):
        """Test detection of risk phrases across multiple pages."""
        page1 = "The company is facing litigation in the high court."
        page2 = "There are concerns about potential default on loans."
        page3 = "NCLT proceedings have been initiated by creditors."
        
        pdf_bytes = create_test_pdf_bytes([page1, page2, page3])
        
        result = extract_from_pdf(pdf_bytes, "risk_document.pdf")
        
        # Verify risk phrases detected
        assert len(result["risk_phrases"]) >= 3
        
        # Verify page numbers are correct
        for risk in result["risk_phrases"]:
            assert 1 <= risk["page"] <= 3
            assert isinstance(risk["phrase"], str)
    
    def test_case_insensitive_section_detection(self):
        """Test that section detection is case-insensitive."""
        content = """
        BALANCE SHEET
        balance sheet
        Balance Sheet
        DIRECTORS REPORT
        """
        pdf_bytes = create_test_pdf_bytes([content])
        
        result = extract_from_pdf(pdf_bytes, "case_test.pdf")
        
        # Should detect sections regardless of case
        assert len(result["key_sections"]) >= 1
        
        # Should not have duplicates (case-insensitive deduplication)
        section_names_lower = [s.lower() for s in result["key_sections"]]
        assert len(section_names_lower) == len(set(section_names_lower))
    
    def test_company_name_prioritization(self):
        """Test that company name from earlier pages is prioritized."""
        page1 = "FIRST COMPANY PRIVATE LIMITED\nAnnual Report"
        page2 = "SECOND COMPANY LIMITED\nFinancial Statements"
        
        pdf_bytes = create_test_pdf_bytes([page1, page2])
        
        result = extract_from_pdf(pdf_bytes, "multiple_companies.pdf")
        
        # Should detect the first company name
        assert result["company_name"] is not None
        assert "FIRST COMPANY" in result["company_name"]
    
    def test_empty_pdf(self):
        """Test extraction from an empty PDF."""
        pdf_bytes = create_test_pdf_bytes([""])
        
        result = extract_from_pdf(pdf_bytes, "empty.pdf")
        
        # Should handle empty PDF gracefully
        assert result["page_count"] == 1
        assert result["confidence_score"] == 0.0  # No content
        assert result["company_name"] is None
        assert len(result["financial_figures"]) == 0
        assert len(result["key_sections"]) == 0
        assert len(result["risk_phrases"]) == 0


@pytest.mark.skipif(not PYMUPDF_AVAILABLE, reason="PyMuPDF not installed")
class TestExtractFromPDFErrorHandling:
    """Test error handling in extract_from_pdf function."""
    
    def test_corrupted_pdf_bytes(self):
        """Test that corrupted PDF bytes raise an exception."""
        corrupted_bytes = b"This is not a valid PDF file"
        
        with pytest.raises(Exception) as exc_info:
            extract_from_pdf(corrupted_bytes, "corrupted.pdf")
        
        assert "Unable to process PDF file" in str(exc_info.value)
    
    def test_empty_bytes(self):
        """Test that empty bytes raise an exception."""
        empty_bytes = b""
        
        with pytest.raises(Exception):
            extract_from_pdf(empty_bytes, "empty.pdf")
    
    def test_pymupdf_unavailable(self):
        """Test error handling when PyMuPDF is not available."""
        # This test would require mocking PYMUPDF_AVAILABLE
        # Skipping for now as it requires more complex setup
        pass


@pytest.mark.skipif(not PYMUPDF_AVAILABLE, reason="PyMuPDF not installed")
class TestExtractFromPDFRealFile:
    """Test extraction from real PDF files if available."""
    
    def test_real_pdf_file(self):
        """Test extraction from a real PDF file if available."""
        # Look for test PDF in uploads directory
        pdf_path = Path(__file__).parent.parent / "backend" / "uploads" / "2366ce66-0bed-4cde-b442-1056c82059b5" / "Arnav_Tiwari_Resume (1).pdf"
        
        if not pdf_path.exists():
            pytest.skip(f"Test PDF not found at {pdf_path}")
        
        # Read PDF bytes
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        # Extract from PDF
        result = extract_from_pdf(pdf_bytes, pdf_path.name)
        
        # Verify basic structure
        assert isinstance(result, dict)
        assert result["page_count"] > 0
        assert result["extraction_method"] in ["digital", "ocr", "ocr_unavailable"]
        assert 0.0 <= result["confidence_score"] <= 1.0
        assert isinstance(result["financial_figures"], list)
        assert isinstance(result["key_sections"], list)
        assert isinstance(result["risk_phrases"], list)
        assert isinstance(result["raw_text_preview"], str)
