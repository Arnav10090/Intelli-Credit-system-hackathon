"""
tests/test_pdf_parser_pymupdf.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for PyMuPDF text extraction helper function.

Task: 2.1 Create _extract_text_with_pymupdf helper function
Requirements: 1.2

Covers:
  - Text extraction from all pages using PyMuPDF
  - Return tuple of (page_texts: list[str], char_counts: list[int])
  - Exception handling for PyMuPDF errors

Run:
  cd backend && pytest ../tests/test_pdf_parser_pymupdf.py -v
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

from ingestor.pdf_parser import _extract_text_with_pymupdf


# ─────────────────────────────────────────────────────────────────────────────
# Test Cases
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not PYMUPDF_AVAILABLE, reason="PyMuPDF not installed")
def test_extract_text_with_pymupdf_basic():
    """Test basic text extraction from a real PDF file."""
    # Use the existing PDF file in the project
    pdf_path = Path(__file__).parent.parent / "backend" / "uploads" / "2366ce66-0bed-4cde-b442-1056c82059b5" / "Arnav_Tiwari_Resume (1).pdf"
    
    if not pdf_path.exists():
        pytest.skip(f"Test PDF not found at {pdf_path}")
    
    # Open PDF with PyMuPDF
    doc = fitz.open(str(pdf_path))
    
    try:
        # Call the function
        page_texts, char_counts = _extract_text_with_pymupdf(doc)
        
        # Verify return types
        assert isinstance(page_texts, list), "page_texts should be a list"
        assert isinstance(char_counts, list), "char_counts should be a list"
        
        # Verify lengths match
        assert len(page_texts) == len(char_counts), "page_texts and char_counts should have same length"
        assert len(page_texts) == len(doc), "Should extract text from all pages"
        
        # Verify each element is correct type
        for i, (text, count) in enumerate(zip(page_texts, char_counts)):
            assert isinstance(text, str), f"page_texts[{i}] should be a string"
            assert isinstance(count, int), f"char_counts[{i}] should be an integer"
            assert count == len(text), f"char_counts[{i}] should equal length of page_texts[{i}]"
        
        # Verify at least some text was extracted (resume should have content)
        total_chars = sum(char_counts)
        assert total_chars > 0, "Should extract some text from the PDF"
        
    finally:
        doc.close()


@pytest.mark.skipif(not PYMUPDF_AVAILABLE, reason="PyMuPDF not installed")
def test_extract_text_with_pymupdf_empty_pdf():
    """Test extraction from a PDF with minimal/no text content."""
    # Create a minimal PDF with one blank page
    doc = fitz.open()
    doc.new_page()
    
    try:
        page_texts, char_counts = _extract_text_with_pymupdf(doc)
        
        # Should still return lists
        assert isinstance(page_texts, list)
        assert isinstance(char_counts, list)
        assert len(page_texts) == 1
        assert len(char_counts) == 1
        
        # Empty page should have empty or minimal text
        assert isinstance(page_texts[0], str)
        assert char_counts[0] == len(page_texts[0])
        
    finally:
        doc.close()


@pytest.mark.skipif(not PYMUPDF_AVAILABLE, reason="PyMuPDF not installed")
def test_extract_text_with_pymupdf_multiple_pages():
    """Test extraction from a multi-page PDF."""
    # Create a PDF with multiple pages containing text
    doc = fitz.open()
    
    try:
        # Add 3 pages with different text content
        for i in range(3):
            page = doc.new_page()
            text = f"This is page {i+1} with some test content."
            page.insert_text((72, 72), text)
        
        page_texts, char_counts = _extract_text_with_pymupdf(doc)
        
        # Verify correct number of pages
        assert len(page_texts) == 3
        assert len(char_counts) == 3
        
        # Verify each page has content
        for i in range(3):
            assert len(page_texts[i]) > 0, f"Page {i+1} should have text"
            assert char_counts[i] > 0, f"Page {i+1} should have character count > 0"
            assert char_counts[i] == len(page_texts[i])
            # Verify the text contains expected content
            assert f"page {i+1}" in page_texts[i].lower()
        
    finally:
        doc.close()


@pytest.mark.skipif(not PYMUPDF_AVAILABLE, reason="PyMuPDF not installed")
def test_extract_text_with_pymupdf_exception_handling():
    """Test that exceptions are properly raised when PyMuPDF encounters errors."""
    # Create a valid document first
    doc = fitz.open()
    doc.new_page()
    
    # Close the document to make it invalid
    doc.close()
    
    # Attempting to extract from a closed document should raise an exception
    with pytest.raises(Exception):
        _extract_text_with_pymupdf(doc)
