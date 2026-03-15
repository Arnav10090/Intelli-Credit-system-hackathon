"""
ingestor/schema_mapper.py
─────────────────────────────────────────────────────────────────────────────
Dynamic schema mapping for extracted document data.

Allows users to:
1. Define custom output schemas for each document type
2. Map extracted fields to schema fields
3. Validate extracted data against schema
4. Transform data to match schema requirements

This addresses Stage 3 requirement: "Dynamic Schema: Enable users to define
or configure the output schema to ingest/structure data extracted from raw files."
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class FieldMapping:
    """Maps an extracted field to a schema field."""
    source_field: str  # Field name in extracted data
    target_field: str  # Field name in output schema
    transform: Optional[str] = None  # Optional transformation: "currency", "percentage", "date"
    required: bool = True
    default_value: Any = None


@dataclass
class SchemaDefinition:
    """User-defined schema for a document type."""
    doc_type: str
    version: str
    fields: list[FieldMapping]
    validation_rules: dict[str, Any]


class SchemaMapper:
    """
    Maps extracted data to user-defined schemas.
    
    Supports:
    - Field renaming
    - Type transformations
    - Validation
    - Default values
    """
    
    def __init__(self):
        self.schemas: dict[str, SchemaDefinition] = {}
        self._load_default_schemas()
    
    def _load_default_schemas(self):
        """Load default schemas for the 5 document types."""
        # ALM Schema
        self.schemas["alm"] = SchemaDefinition(
            doc_type="alm",
            version="1.0",
            fields=[
                FieldMapping("maturity_buckets", "maturity_buckets", required=True),
                FieldMapping("assets_by_bucket", "assets", transform="currency", required=True),
                FieldMapping("liabilities_by_bucket", "liabilities", transform="currency", required=True),
                FieldMapping("gap_analysis", "gap", transform="currency", required=True),
            ],
            validation_rules={
                "maturity_buckets": {"type": "list", "min_length": 1},
                "assets": {"type": "dict", "min_keys": 1},
                "liabilities": {"type": "dict", "min_keys": 1},
            },
        )
        
        # Shareholding Schema
        self.schemas["shareholding"] = SchemaDefinition(
            doc_type="shareholding",
            version="1.0",
            fields=[
                FieldMapping("promoter_holding_pct", "promoter_holding", transform="percentage", required=True),
                FieldMapping("public_holding_pct", "public_holding", transform="percentage", required=True),
                FieldMapping("pledged_shares_pct", "pledged_shares", transform="percentage", required=True),
                FieldMapping("promoter_names", "promoters", required=True),
            ],
            validation_rules={
                "promoter_holding": {"type": "float", "min": 0, "max": 100},
                "public_holding": {"type": "float", "min": 0, "max": 100},
                "pledged_shares": {"type": "float", "min": 0, "max": 100},
            },
        )
        
        # Borrowing Profile Schema
        self.schemas["borrowing"] = SchemaDefinition(
            doc_type="borrowing",
            version="1.0",
            fields=[
                FieldMapping("lender_name", "lender", required=True),
                FieldMapping("loan_type", "type", required=True),
                FieldMapping("sanctioned_amount", "sanctioned", transform="currency", required=True),
                FieldMapping("outstanding_amount", "outstanding", transform="currency", required=True),
                FieldMapping("interest_rate", "rate", transform="percentage", required=True),
                FieldMapping("maturity_date", "maturity", transform="date", required=True),
            ],
            validation_rules={
                "sanctioned": {"type": "float", "min": 0},
                "outstanding": {"type": "float", "min": 0},
                "rate": {"type": "float", "min": 0, "max": 50},
            },
        )
        
        # Annual Report Schema
        self.schemas["annual_report"] = SchemaDefinition(
            doc_type="annual_report",
            version="1.0",
            fields=[
                FieldMapping("revenue", "revenue", transform="currency", required=True),
                FieldMapping("ebitda", "ebitda", transform="currency", required=True),
                FieldMapping("pat", "profit_after_tax", transform="currency", required=True),
                FieldMapping("total_assets", "assets", transform="currency", required=True),
                FieldMapping("total_liabilities", "liabilities", transform="currency", required=True),
                FieldMapping("net_worth", "net_worth", transform="currency", required=True),
            ],
            validation_rules={
                "revenue": {"type": "float"},
                "ebitda": {"type": "float"},
                "assets": {"type": "float", "min": 0},
                "liabilities": {"type": "float", "min": 0},
            },
        )
        
        # Portfolio Schema
        self.schemas["portfolio"] = SchemaDefinition(
            doc_type="portfolio",
            version="1.0",
            fields=[
                FieldMapping("gross_npa_pct", "gross_npa", transform="percentage", required=True),
                FieldMapping("net_npa_pct", "net_npa", transform="percentage", required=True),
                FieldMapping("provision_coverage_ratio", "pcr", transform="percentage", required=True),
                FieldMapping("total_loan_book", "loan_book", transform="currency", required=True),
            ],
            validation_rules={
                "gross_npa": {"type": "float", "min": 0, "max": 100},
                "net_npa": {"type": "float", "min": 0, "max": 100},
                "pcr": {"type": "float", "min": 0, "max": 100},
                "loan_book": {"type": "float", "min": 0},
            },
        )
    
    def map_data(self, doc_type: str, extracted_data: dict) -> dict:
        """
        Map extracted data to schema-compliant output.
        
        Args:
            doc_type: Document type (alm, shareholding, etc.)
            extracted_data: Raw extracted data
            
        Returns:
            Schema-compliant data dict
        """
        if doc_type not in self.schemas:
            logger.warning(f"No schema defined for doc_type: {doc_type}")
            return extracted_data
        
        schema = self.schemas[doc_type]
        mapped_data = {}
        errors = []
        
        for field_mapping in schema.fields:
            source = field_mapping.source_field
            target = field_mapping.target_field
            
            # Get value from extracted data
            value = extracted_data.get(source)
            
            # Handle missing required fields
            if value is None:
                if field_mapping.required and field_mapping.default_value is None:
                    errors.append(f"Missing required field: {source}")
                    continue
                value = field_mapping.default_value
            
            # Apply transformation
            if field_mapping.transform and value is not None:
                value = self._transform_value(value, field_mapping.transform)
            
            mapped_data[target] = value
        
        if errors:
            logger.warning(f"Schema mapping errors for {doc_type}: {errors}")
            mapped_data["_mapping_errors"] = errors
        
        return mapped_data
    
    def _transform_value(self, value: Any, transform: str) -> Any:
        """Apply transformation to a value."""
        try:
            if transform == "currency":
                # Convert currency strings to float (handles ₹, Rs., Cr, Lakh)
                if isinstance(value, str):
                    # Remove currency symbols and commas
                    clean = value.replace("₹", "").replace("Rs.", "").replace("Rs", "")
                    clean = clean.replace(",", "").strip()
                    
                    # Handle Crore/Lakh multipliers
                    multiplier = 1.0
                    if "crore" in clean.lower() or "cr" in clean.lower():
                        multiplier = 10000000  # 1 Crore = 10 million
                        clean = clean.lower().replace("crore", "").replace("cr", "").strip()
                    elif "lakh" in clean.lower() or "lac" in clean.lower():
                        multiplier = 100000  # 1 Lakh = 100 thousand
                        clean = clean.lower().replace("lakh", "").replace("lac", "").strip()
                    
                    return float(clean) * multiplier
                return float(value)
            
            elif transform == "percentage":
                # Convert percentage strings to float
                if isinstance(value, str):
                    clean = value.replace("%", "").strip()
                    return float(clean)
                return float(value)
            
            elif transform == "date":
                # Basic date parsing (can be enhanced)
                from datetime import datetime
                if isinstance(value, str):
                    # Try common date formats
                    for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]:
                        try:
                            return datetime.strptime(value, fmt).isoformat()
                        except ValueError:
                            continue
                return value
            
            return value
        
        except Exception as e:
            logger.error(f"Transform error ({transform}): {e}")
            return value
    
    def validate_data(self, doc_type: str, data: dict) -> tuple[bool, list[str]]:
        """
        Validate data against schema rules.
        
        Returns:
            (is_valid, list_of_errors)
        """
        if doc_type not in self.schemas:
            return True, []
        
        schema = self.schemas[doc_type]
        errors = []
        
        for field_name, rules in schema.validation_rules.items():
            if field_name not in data:
                continue
            
            value = data[field_name]
            
            # Type validation
            if "type" in rules:
                expected_type = rules["type"]
                if expected_type == "float" and not isinstance(value, (int, float)):
                    errors.append(f"{field_name}: Expected float, got {type(value).__name__}")
                elif expected_type == "list" and not isinstance(value, list):
                    errors.append(f"{field_name}: Expected list, got {type(value).__name__}")
                elif expected_type == "dict" and not isinstance(value, dict):
                    errors.append(f"{field_name}: Expected dict, got {type(value).__name__}")
            
            # Range validation
            if isinstance(value, (int, float)):
                if "min" in rules and value < rules["min"]:
                    errors.append(f"{field_name}: Value {value} below minimum {rules['min']}")
                if "max" in rules and value > rules["max"]:
                    errors.append(f"{field_name}: Value {value} above maximum {rules['max']}")
            
            # Length validation
            if isinstance(value, (list, dict)):
                if "min_length" in rules and len(value) < rules["min_length"]:
                    errors.append(f"{field_name}: Length {len(value)} below minimum {rules['min_length']}")
                if "min_keys" in rules and len(value) < rules["min_keys"]:
                    errors.append(f"{field_name}: Keys {len(value)} below minimum {rules['min_keys']}")
        
        return len(errors) == 0, errors
    
    def register_custom_schema(self, schema: SchemaDefinition):
        """Allow users to register custom schemas."""
        self.schemas[schema.doc_type] = schema
        logger.info(f"Registered custom schema for {schema.doc_type} v{schema.version}")
    
    def get_schema(self, doc_type: str) -> Optional[SchemaDefinition]:
        """Get schema definition for a document type."""
        return self.schemas.get(doc_type)
    
    def list_schemas(self) -> list[str]:
        """List all available schema types."""
        return list(self.schemas.keys())


# Global schema mapper instance
schema_mapper = SchemaMapper()
