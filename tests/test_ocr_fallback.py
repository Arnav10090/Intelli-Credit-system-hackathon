"""
Tests for _apply_ocr_fallback function in pdf_parser.py

Feature: pdf-upload-extraction
Tests Requirements: 1.3, 1.6, 12.2, 12.4
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from backend.ingestor.pdf_parser import _apply_ocr_fallback


class TestApplyOCRFallback:
    """Unit tests for _apply_ocr_fallback helper function"""
    
    def test_ocr_fallback_with_pytesseract_available(self):
        """Test OCR fallback when pytesseract is available"""
        # Mock PDF document and page
        mock_doc = Mock()
        mock_page = Mock()
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        
        # Mock pixmap
        mock_pix = Mock()
        mock_pix.tobytes = Mock(return_value=b"fake_png_data")
        mock_page.get_pixmap = Mock(return_value=mock_pix)
        
        with patch('backend.ingestor.pdf_parser.TESSERACT_AVAILABLE', True):
            with patch('backend.ingestor.pdf_parser.CV2_AVAILABLE', False):
                with patch('backend.ingestor.pdf_parser.Image') as mock_image:
                    with patch('backend.ingestor.pdf_parser.pytesseract') as mock_tess:
                        mock_tess.image_to_string = Mock(return_value="Extracted text from OCR")
                        mock_image.open = Mock(return_value=Mock())
                        
                        result = _apply_ocr_fallback(mock_doc, [0, 1])
                        
                        assert len(result) == 2
                        assert result[0] == "Extracted text from OCR"
                        assert result[1] == "Extracted text from OCR"
    
    def test_ocr_fallback_without_pytesseract(self):
        """Test OCR fallback when pytesseract is not available (Requirement 1.6)"""
        mock_doc = Mock()
        
        with patch('backend.ingestor.pdf_parser.TESSERACT_AVAILABLE', False):
            result = _apply_ocr_fallback(mock_doc, [0, 1, 2])
            
            # Should return empty strings for all pages
            assert len(result) == 3
            assert all(text == "" for text in result)
    
    def test_ocr_fallback_limits_to_first_3_pages(self):
        """Test that OCR is limited to first 3 pages (Requirements 12.2, 12.4)"""
        mock_doc = Mock()
        mock_page = Mock()
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        
        mock_pix = Mock()
        mock_pix.tobytes = Mock(return_value=b"fake_png_data")
        mock_page.get_pixmap = Mock(return_value=mock_pix)
        
        with patch('backend.ingestor.pdf_parser.TESSERACT_AVAILABLE', True):
            with patch('backend.ingestor.pdf_parser.CV2_AVAILABLE', False):
                with patch('backend.ingestor.pdf_parser.Image') as mock_image:
                    with patch('backend.ingestor.pdf_parser.pytesseract') as mock_tess:
                        mock_tess.image_to_string = Mock(return_value="OCR text")
                        mock_image.open = Mock(return_value=Mock())
                        
                        # Request OCR for 5 pages
                        result = _apply_ocr_fallback(mock_doc, [0, 1, 2, 3, 4])
                        
                        # Should return 5 results but only first 3 have content
                        assert len(result) == 5
                        assert result[0] == "OCR text"
                        assert result[1] == "OCR text"
                        assert result[2] == "OCR text"
                        assert result[3] == ""
                        assert result[4] == ""
                        
                        # Verify OCR was only called 3 times
                        assert mock_tess.image_to_string.call_count == 3
    
    def test_ocr_fallback_handles_exceptions_gracefully(self):
        """Test that OCR failures return empty strings (Requirement 1.6)"""
        mock_doc = Mock()
        mock_page = Mock()
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        
        # Make get_pixmap raise an exception
        mock_page.get_pixmap = Mock(side_effect=Exception("Pixmap error"))
        
        with patch('backend.ingestor.pdf_parser.TESSERACT_AVAILABLE', True):
            result = _apply_ocr_fallback(mock_doc, [0, 1])
            
            # Should return empty strings for failed pages
            assert len(result) == 2
            assert result[0] == ""
            assert result[1] == ""
    
    def test_ocr_fallback_with_empty_page_list(self):
        """Test OCR fallback with no pages to process"""
        mock_doc = Mock()
        
        with patch('backend.ingestor.pdf_parser.TESSERACT_AVAILABLE', True):
            result = _apply_ocr_fallback(mock_doc, [])
            
            assert len(result) == 0
    
    def test_ocr_fallback_with_single_page(self):
        """Test OCR fallback with a single page"""
        mock_doc = Mock()
        mock_page = Mock()
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        
        mock_pix = Mock()
        mock_pix.tobytes = Mock(return_value=b"fake_png_data")
        mock_page.get_pixmap = Mock(return_value=mock_pix)
        
        with patch('backend.ingestor.pdf_parser.TESSERACT_AVAILABLE', True):
            with patch('backend.ingestor.pdf_parser.CV2_AVAILABLE', False):
                with patch('backend.ingestor.pdf_parser.Image') as mock_image:
                    with patch('backend.ingestor.pdf_parser.pytesseract') as mock_tess:
                        mock_tess.image_to_string = Mock(return_value="Single page OCR")
                        mock_image.open = Mock(return_value=Mock())
                        
                        result = _apply_ocr_fallback(mock_doc, [2])
                        
                        assert len(result) == 1
                        assert result[0] == "Single page OCR"
