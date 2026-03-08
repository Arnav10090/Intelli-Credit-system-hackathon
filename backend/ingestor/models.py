"""
ingestor/models.py
─────────────────────────────────────────────────────────────────────────────
Pydantic data models for PDF extraction and upload responses.

These models define the structure and validation rules for extraction results
and API responses in the Intelli-Credit document ingestion pipeline.
─────────────────────────────────────────────────────────────────────────────
"""

from pydantic import BaseModel, Field
from typing import Optional


class FinancialFigure(BaseModel):
    """
    Represents a financial figure extracted from a document.
    
    Requirements: 3.3
    """
    value: str = Field(
        ...,
        description="The extracted financial value (e.g., '₹ 1,234.56', 'Rs. 10 Crore')"
    )
    context: str = Field(
        ...,
        description="Surrounding text context (20 characters before/after the figure)"
    )


class RiskPhrase(BaseModel):
    """
    Represents a risk phrase detected in a document.
    
    Requirements: 5.5
    """
    phrase: str = Field(
        ...,
        description="The detected risk keyword (e.g., 'litigation', 'NCLT', 'default')"
    )
    page: int = Field(
        ...,
        description="Page number where the phrase was found (1-indexed)",
        ge=1
    )


class ExtractionResult(BaseModel):
    """
    Complete extraction result from PDF processing.
    
    Contains all structured data extracted from a PDF including text quality metrics,
    detected entities, and raw text preview.
    
    Requirements: 1.4
    """
    page_count: int = Field(
        ...,
        description="Total number of pages in the PDF",
        ge=0
    )
    extraction_method: str = Field(
        ...,
        description="Method used for text extraction: 'digital', 'ocr', or 'ocr_unavailable'"
    )
    confidence_score: float = Field(
        ...,
        description="Extraction quality score (ratio of pages with >100 characters)",
        ge=0.0,
        le=1.0
    )
    company_name: Optional[str] = Field(
        None,
        description="Detected company name with legal suffixes, or None if not found"
    )
    financial_figures: list[FinancialFigure] = Field(
        default_factory=list,
        description="List of detected financial figures with context"
    )
    key_sections: list[str] = Field(
        default_factory=list,
        description="List of detected document sections (e.g., 'Balance Sheet', 'Auditors Report')"
    )
    risk_phrases: list[RiskPhrase] = Field(
        default_factory=list,
        description="List of detected risk phrases with page numbers"
    )
    raw_text_preview: str = Field(
        ...,
        description="First 2000 characters of extracted text",
        max_length=2000
    )


class UploadResponse(BaseModel):
    """
    API response model for document upload endpoint.
    
    Contains file metadata and extraction results. Extraction fields are optional
    for non-PDF files (CSV, XLSX).
    
    Requirements: 7.3, 7.4
    """
    filename: str = Field(
        ...,
        description="Original filename of the uploaded document"
    )
    file_type: str = Field(
        ...,
        description="File type: 'pdf', 'csv', or 'xlsx'"
    )
    page_count: Optional[int] = Field(
        None,
        description="Number of pages (PDF only)",
        ge=0
    )
    extraction_method: Optional[str] = Field(
        None,
        description="Extraction method used (PDF only): 'digital', 'ocr', or 'ocr_unavailable'"
    )
    confidence_score: Optional[float] = Field(
        None,
        description="Extraction quality score (PDF only)",
        ge=0.0,
        le=1.0
    )
    company_name_detected: Optional[str] = Field(
        None,
        description="Detected company name (PDF only)"
    )
    financial_figures_found: int = Field(
        0,
        description="Count of financial figures detected (PDF only)",
        ge=0
    )
    risk_phrases_found: list[str] = Field(
        default_factory=list,
        description="List of detected risk phrases (PDF only)"
    )
    key_sections_detected: list[str] = Field(
        default_factory=list,
        description="List of detected document sections (PDF only)"
    )
    raw_text_preview: Optional[str] = Field(
        None,
        description="First 500 characters of extracted text (PDF only)",
        max_length=500
    )
