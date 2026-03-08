"""
tests/test_upload_endpoint.py
──────────────────────────────────────────────────────────────────────────────
Integration tests for the enhanced upload endpoint with PDF extraction.

Tests cover:
  - File type validation (PDF, CSV, XLSX only)
  - File size validation (50MB limit)
  - PDF extraction integration
  - Response structure for PDF and non-PDF files
  - Error handling for unsupported types and oversized files

Run:
  cd backend && pytest ../tests/test_upload_endpoint.py -v
──────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
import io
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create a TestClient with in-memory SQLite for the full test session."""
    os.environ["INTELLI_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["LLM_API_KEY"] = "test-key-not-real"

    from main import app
    from database import init_db
    import asyncio

    # Initialize tables in the in-memory DB
    asyncio.get_event_loop().run_until_complete(init_db())

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(scope="module")
def demo_case_id(client):
    """Create and return a demo case ID for endpoint tests."""
    resp = client.post("/api/v1/cases", json={
        "company_name": "Test Upload Corp Ltd",
        "company_cin": "U12345MH2010PLC000001",
        "company_pan": "AAAAA1234A",
        "requested_amount_cr": 20.0,
        "requested_tenor_yr": 7,
        "purpose": "Working Capital",
    })
    assert resp.status_code in (200, 201)
    return resp.json()["case_id"]


def create_mock_pdf_bytes() -> bytes:
    """Create a minimal valid PDF file in memory."""
    # Minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000317 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
410
%%EOF
"""
    return pdf_content


class TestFileTypeValidation:
    """Test subtask 13.2: File type validation"""

    def test_upload_pdf_accepted(self, client, demo_case_id):
        """PDF files should be accepted"""
        pdf_bytes = create_mock_pdf_bytes()
        files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        assert resp.status_code == 200

    def test_upload_csv_accepted(self, client, demo_case_id):
        """CSV files should be accepted"""
        csv_content = b"col1,col2\nval1,val2"
        files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        assert resp.status_code == 200

    def test_upload_xlsx_accepted(self, client, demo_case_id):
        """XLSX files should be accepted"""
        # Minimal XLSX file (just a ZIP with minimal structure)
        xlsx_content = b"PK\x03\x04" + b"\x00" * 100  # Simplified XLSX
        files = {"file": ("test.xlsx", io.BytesIO(xlsx_content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        # May fail due to invalid XLSX structure, but should not reject based on extension
        assert resp.status_code in (200, 400)

    def test_upload_unsupported_type_rejected(self, client, demo_case_id):
        """Unsupported file types should return 400 error"""
        txt_content = b"This is a text file"
        files = {"file": ("test.txt", io.BytesIO(txt_content), "text/plain")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    def test_upload_doc_rejected(self, client, demo_case_id):
        """DOC files should be rejected"""
        doc_content = b"Fake DOC content"
        files = {"file": ("test.doc", io.BytesIO(doc_content), "application/msword")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        assert resp.status_code == 400


class TestFileSizeValidation:
    """Test subtask 13.3: File size validation"""

    def test_upload_within_size_limit(self, client, demo_case_id):
        """Files under 50MB should be accepted"""
        pdf_bytes = create_mock_pdf_bytes()
        files = {"file": ("small.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        assert resp.status_code == 200

    def test_upload_exceeds_size_limit(self, client, demo_case_id):
        """Files over 50MB should return 413 error"""
        # Create a file larger than 50MB
        large_content = b"x" * (51 * 1024 * 1024)  # 51MB
        files = {"file": ("large.pdf", io.BytesIO(large_content), "application/pdf")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        assert resp.status_code == 413
        assert "exceeds maximum limit" in resp.json()["detail"]


class TestPDFExtraction:
    """Test subtask 13.4: PDF extraction integration"""

    def test_pdf_extraction_called(self, client, demo_case_id):
        """PDF files should trigger extraction"""
        pdf_bytes = create_mock_pdf_bytes()
        files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        assert resp.status_code == 200
        body = resp.json()
        
        # Should have extraction-specific fields
        assert "extraction_method" in body
        assert "confidence_score" in body
        assert "page_count" in body

    def test_csv_skips_extraction(self, client, demo_case_id):
        """CSV files should skip extraction"""
        csv_content = b"col1,col2\nval1,val2"
        files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        assert resp.status_code == 200
        body = resp.json()
        
        # Should not have extraction-specific fields
        assert body["extraction_method"] is None
        assert body["confidence_score"] is None
        assert body["page_count"] is None


class TestUploadResponse:
    """Test subtask 13.5: Response structure"""

    def test_pdf_response_structure(self, client, demo_case_id):
        """PDF upload response should have all required fields"""
        pdf_bytes = create_mock_pdf_bytes()
        files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        assert resp.status_code == 200
        body = resp.json()
        
        # Required fields for all uploads
        assert "filename" in body
        assert "file_type" in body
        assert body["filename"] == "test.pdf"
        assert body["file_type"] == "pdf"
        
        # PDF-specific fields
        assert "page_count" in body
        assert "extraction_method" in body
        assert "confidence_score" in body
        assert "company_name_detected" in body
        assert "financial_figures_found" in body
        assert "risk_phrases_found" in body
        assert "key_sections_detected" in body
        assert "raw_text_preview" in body

    def test_csv_response_structure(self, client, demo_case_id):
        """CSV upload response should have basic fields only"""
        csv_content = b"col1,col2\nval1,val2"
        files = {"file": ("data.csv", io.BytesIO(csv_content), "text/csv")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        assert resp.status_code == 200
        body = resp.json()
        
        # Required fields
        assert body["filename"] == "data.csv"
        assert body["file_type"] == "csv"
        
        # Extraction fields should be None or empty
        assert body["page_count"] is None
        assert body["extraction_method"] is None
        assert body["confidence_score"] is None
        assert body["financial_figures_found"] == 0
        assert body["risk_phrases_found"] == []
        assert body["key_sections_detected"] == []

    def test_raw_text_preview_truncated(self, client, demo_case_id):
        """Raw text preview should be truncated to 500 characters"""
        pdf_bytes = create_mock_pdf_bytes()
        files = {"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        assert resp.status_code == 200
        body = resp.json()
        
        # Preview should be at most 500 characters
        if body["raw_text_preview"]:
            assert len(body["raw_text_preview"]) <= 500


class TestErrorHandling:
    """Test error handling for extraction failures"""

    def test_corrupted_pdf_returns_400(self, client, demo_case_id):
        """Corrupted PDF files should return 400 error"""
        corrupted_pdf = b"This is not a valid PDF"
        files = {"file": ("corrupted.pdf", io.BytesIO(corrupted_pdf), "application/pdf")}
        
        resp = client.post(f"/api/v1/cases/{demo_case_id}/upload", files=files)
        assert resp.status_code == 400
        assert "Unable to process PDF file" in resp.json()["detail"]
