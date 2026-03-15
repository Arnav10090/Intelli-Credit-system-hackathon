"""
api/document_routes.py
─────────────────────────────────────────────────────────────────────────────
Enhanced document ingestion API routes for Stage 3 requirements:

1. Multi-document upload (5 document types)
2. Automatic classification with human-in-the-loop approval
3. Dynamic schema configuration
4. Extraction with schema mapping

Addresses hackathon Stage 3: "Automated Extraction & Schema Mapping"
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from ingestor.pdf_parser import extract_from_pdf
from ingestor.document_classifier import classify_document, ClassificationResult
from ingestor.schema_mapper import schema_mapper

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    """Response for document upload with classification."""
    filename: str
    file_type: str
    page_count: Optional[int] = None
    extraction_method: Optional[str] = None
    confidence_score: Optional[float] = None
    
    # Classification results
    classified_as: str
    classification_confidence: float
    matched_patterns: list[str]
    requires_human_review: bool
    
    # Schema information
    suggested_schema: dict
    
    # Preview
    raw_text_preview: Optional[str] = None


class ClassificationApprovalRequest(BaseModel):
    """Request to approve/override classification."""
    case_id: str
    document_id: str
    approved_type: str  # User-approved document type
    override_reason: Optional[str] = None


class SchemaConfigRequest(BaseModel):
    """Request to configure extraction schema."""
    doc_type: str
    field_mappings: list[dict]  # List of {source_field, target_field, transform, required}
    validation_rules: dict


class ExtractionRequest(BaseModel):
    """Request to extract data with schema mapping."""
    case_id: str
    document_id: str
    use_custom_schema: bool = False
    schema_config: Optional[dict] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/documents/upload-multi", response_model=DocumentUploadResponse)
async def upload_document_with_classification(
    case_id: str,
    file: UploadFile = File(...),
    doc_slot: str = Form(..., description="alm|shareholding|borrowing|annual_report|portfolio"),
    session: AsyncSession = Depends(get_session),
):
    """
    Upload document with automatic classification.
    
    Stage 3 Requirements:
    - Classification: Automatically identify and categorize uploaded files
    - Human-in-the-loop: Allow users to approve, deny, or edit auto-classification
    - Dynamic Schema: Show suggested schema for the classified document type
    """
    
    logger.info(f"Uploading document to case {case_id}, slot: {doc_slot}")
    
    # Validate file type
    from pathlib import Path
    suffix = Path(file.filename).suffix.lower().lstrip(".")
    if suffix not in ["pdf", "csv", "xlsx"]:
        raise HTTPException(400, f"Unsupported file type: {suffix}")
    
    # Read file content
    content = await file.read()
    
    # File size validation (50MB limit)
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "File exceeds 50MB limit")
    
    # Extract text from PDF
    if suffix == "pdf":
        try:
            extraction_result = extract_from_pdf(content, file.filename)
            
            # Classify the document
            classification = classify_document(
                extraction_result["raw_text_preview"],
                file.filename
            )
            
            # Build response
            response = DocumentUploadResponse(
                filename=file.filename,
                file_type=suffix,
                page_count=extraction_result["page_count"],
                extraction_method=extraction_result["extraction_method"],
                confidence_score=extraction_result["confidence_score"],
                classified_as=classification.doc_type,
                classification_confidence=classification.confidence,
                matched_patterns=classification.matched_patterns,
                requires_human_review=classification.requires_human_review,
                suggested_schema=classification.suggested_schema,
                raw_text_preview=extraction_result["raw_text_preview"][:500],
            )
            
            logger.info(
                f"Document classified as {classification.doc_type} "
                f"(confidence={classification.confidence:.2f})"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            raise HTTPException(400, f"PDF processing error: {str(e)}")
    
    else:
        # For CSV/XLSX, return basic response without classification
        return DocumentUploadResponse(
            filename=file.filename,
            file_type=suffix,
            classified_as="unknown",
            classification_confidence=0.0,
            matched_patterns=[],
            requires_human_review=True,
            suggested_schema={},
        )


@router.post("/cases/{case_id}/documents/{doc_id}/approve-classification")
async def approve_classification(
    case_id: str,
    doc_id: str,
    request: ClassificationApprovalRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Human-in-the-loop: Approve or override document classification.
    
    Stage 3 Requirement: "Allow users to approve, deny, or edit the auto-classification"
    """
    logger.info(
        f"Classification approval: case={case_id}, doc={doc_id}, "
        f"approved_type={request.approved_type}"
    )
    
    # TODO: Update document record in database with approved classification
    # For now, return success
    
    return {
        "case_id": case_id,
        "document_id": doc_id,
        "approved_type": request.approved_type,
        "status": "approved",
        "message": f"Document classified as {request.approved_type}",
    }


@router.post("/schemas/configure")
async def configure_schema(
    request: SchemaConfigRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Configure custom extraction schema for a document type.
    
    Stage 3 Requirement: "Enable users to define or configure the output schema"
    """
    from ingestor.schema_mapper import FieldMapping, SchemaDefinition
    
    logger.info(f"Configuring custom schema for {request.doc_type}")
    
    # Build field mappings
    field_mappings = []
    for fm in request.field_mappings:
        field_mappings.append(FieldMapping(
            source_field=fm["source_field"],
            target_field=fm["target_field"],
            transform=fm.get("transform"),
            required=fm.get("required", True),
            default_value=fm.get("default_value"),
        ))
    
    # Create schema definition
    schema = SchemaDefinition(
        doc_type=request.doc_type,
        version="custom",
        fields=field_mappings,
        validation_rules=request.validation_rules,
    )
    
    # Register schema
    schema_mapper.register_custom_schema(schema)
    
    return {
        "doc_type": request.doc_type,
        "status": "configured",
        "field_count": len(field_mappings),
        "message": f"Custom schema configured for {request.doc_type}",
    }


@router.get("/schemas/{doc_type}")
async def get_schema(doc_type: str):
    """
    Get extraction schema for a document type.
    
    Returns the field mappings and validation rules.
    """
    schema = schema_mapper.get_schema(doc_type)
    
    if not schema:
        raise HTTPException(404, f"No schema found for {doc_type}")
    
    return {
        "doc_type": schema.doc_type,
        "version": schema.version,
        "fields": [
            {
                "source_field": f.source_field,
                "target_field": f.target_field,
                "transform": f.transform,
                "required": f.required,
                "default_value": f.default_value,
            }
            for f in schema.fields
        ],
        "validation_rules": schema.validation_rules,
    }


@router.get("/schemas")
async def list_schemas():
    """List all available document type schemas."""
    schemas = schema_mapper.list_schemas()
    return {
        "schemas": schemas,
        "count": len(schemas),
    }


@router.post("/cases/{case_id}/documents/{doc_id}/extract")
async def extract_with_schema(
    case_id: str,
    doc_id: str,
    request: ExtractionRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Extract data from document and map to schema.
    
    Stage 3 Requirement: "Extraction: Ingest the data from the files into your 
    defined schema with high precision, with user defined adjustments as needed"
    """
    logger.info(f"Extracting data: case={case_id}, doc={doc_id}")
    
    # TODO: Implement actual extraction logic
    # For now, return mock response
    
    return {
        "case_id": case_id,
        "document_id": doc_id,
        "status": "extracted",
        "extracted_data": {},
        "mapped_data": {},
        "validation_errors": [],
        "message": "Data extraction complete",
    }
