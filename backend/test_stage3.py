#!/usr/bin/env python3
"""
Quick test script for Stage 3 features
"""

from ingestor.document_classifier import classify_document
from ingestor.schema_mapper import schema_mapper

print("=" * 60)
print("STAGE 3 FEATURES TEST")
print("=" * 60)

# Test 1: Document Classification
print("\n1. Testing Document Classifier...")
print("-" * 60)

test_texts = {
    "annual_report": """
        ANNUAL REPORT 2024
        XYZ Corporation Limited
        
        BALANCE SHEET
        As at March 31, 2024
        
        PROFIT AND LOSS STATEMENT
        For the year ended March 31, 2024
        
        DIRECTOR'S REPORT
        Dear Shareholders,
        
        AUDITOR'S REPORT
        Independent Auditor's Report
    """,
    "shareholding": """
        SHAREHOLDING PATTERN
        As on March 31, 2024
        
        Promoter Holding: 67.5%
        Public Shareholding: 32.5%
        
        Pledged Shares: 0%
        
        Category of Shareholders:
        - Promoters
        - Public
        - Institutional
    """,
    "borrowing": """
        BORROWING PROFILE
        
        Debt Schedule as on March 31, 2024
        
        Term Loan from HDFC Bank
        Sanctioned Amount: Rs. 50 Crore
        Outstanding Amount: Rs. 35 Crore
        Interest Rate: 9.5% p.a.
        
        Working Capital Limit from ICICI Bank
        Credit Facility: Rs. 20 Crore
    """,
}

for doc_type, text in test_texts.items():
    result = classify_document(text, f"test_{doc_type}.pdf")
    print(f"\nTest: {doc_type}")
    print(f"  Classified as: {result.doc_type}")
    print(f"  Confidence: {result.confidence:.2f}")
    print(f"  Matched patterns: {len(result.matched_patterns)}")
    print(f"  Requires review: {result.requires_human_review}")
    if result.matched_patterns:
        print(f"  Patterns: {result.matched_patterns[:3]}")
    
    # Check if classification is correct
    if result.doc_type == doc_type:
        print("  ✓ PASS - Correct classification")
    else:
        print(f"  ✗ FAIL - Expected {doc_type}, got {result.doc_type}")

# Test 2: Schema Mapper
print("\n\n2. Testing Schema Mapper...")
print("-" * 60)

# Test schema retrieval
for schema_type in ["alm", "shareholding", "borrowing", "annual_report", "portfolio"]:
    schema = schema_mapper.get_schema(schema_type)
    if schema:
        print(f"\n{schema_type.upper()} Schema:")
        print(f"  Version: {schema.version}")
        print(f"  Fields: {len(schema.fields)}")
        print(f"  Validation rules: {len(schema.validation_rules)}")
        print("  ✓ Schema loaded")
    else:
        print(f"  ✗ Schema not found for {schema_type}")

# Test 3: Data Mapping
print("\n\n3. Testing Data Mapping...")
print("-" * 60)

test_data = {
    "revenue": "Rs. 218 Crore",
    "ebitda": "Rs. 47.9 Crore",
    "pat": "Rs. 28.4 Crore",
    "total_assets": "Rs. 450 Crore",
    "total_liabilities": "Rs. 233.2 Crore",
    "net_worth": "Rs. 216.8 Crore",
}

print("\nInput data:")
for key, value in test_data.items():
    print(f"  {key}: {value}")

mapped_data = schema_mapper.map_data("annual_report", test_data)

print("\nMapped data:")
for key, value in mapped_data.items():
    if not key.startswith("_"):
        print(f"  {key}: {value}")

# Test 4: Validation
print("\n\n4. Testing Validation...")
print("-" * 60)

is_valid, errors = schema_mapper.validate_data("annual_report", mapped_data)

if is_valid:
    print("✓ Validation PASSED")
else:
    print("✗ Validation FAILED")
    for error in errors:
        print(f"  - {error}")

# Test 5: Currency Transformation
print("\n\n5. Testing Currency Transformation...")
print("-" * 60)

test_currencies = [
    "Rs. 100 Crore",
    "₹ 50 Lakh",
    "Rs. 1,234.56",
    "₹ 10.5 Cr",
]

for currency in test_currencies:
    transformed = schema_mapper._transform_value(currency, "currency")
    print(f"  {currency:20s} → {transformed:,.2f}")

print("\n" + "=" * 60)
print("ALL TESTS COMPLETED")
print("=" * 60)
