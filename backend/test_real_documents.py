#!/usr/bin/env python3
"""
Test script for real NBFC annual reports
Tests the system with actual documents from hackathon reference materials
"""

import sys
from pathlib import Path

print("=" * 70)
print("REAL NBFC DOCUMENT TESTING")
print("=" * 70)
print("\nReference Materials:")
print("1. MoneyBoxx Finance - https://moneyboxxfinance.com/annual-reports")
print("2. Kinara Capital - FY24 Annual Report")
print("3. Vivriti Capital - https://www.vivriticapital.com/annual-reports.html")
print("4. Tata Capital - FY 2024-25 Annual Report")
print("=" * 70)

# Check if test documents directory exists
test_docs_dir = Path("test_documents")
if not test_docs_dir.exists():
    print("\n⚠️  Test documents directory not found!")
    print("\nTo test with real documents:")
    print("1. Create directory: mkdir test_documents")
    print("2. Download PDFs from reference URLs")
    print("3. Place them in test_documents/")
    print("\nExample downloads:")
    print('  curl -o test_documents/kinara_fy24.pdf "https://finance.kinaracapital.com/wp-content/uploads/2024/10/fy24-annual-report-kinara-capital.pdf"')
    print('  curl -o test_documents/tata_capital.pdf "https://www.tatacapital.com/content/dam/tata-capital/pdf/investors-and-financial-reports/annual-reports/24-25/tata-capital-limited.pdf"')
    print("\n" + "=" * 70)
    print("SYSTEM READY - Waiting for test documents")
    print("=" * 70)
    sys.exit(0)

# Find PDF files
pdf_files = list(test_docs_dir.glob("*.pdf"))

if not pdf_files:
    print("\n⚠️  No PDF files found in test_documents/")
    print("\nPlease download reference PDFs and place them in test_documents/")
    print("=" * 70)
    sys.exit(0)

print(f"\n✓ Found {len(pdf_files)} PDF file(s) to test")
print("-" * 70)

# Import modules
try:
    from ingestor.pdf_parser import extract_from_pdf
    from ingestor.document_classifier import classify_document
    print("✓ Modules imported successfully")
except Exception as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Test each PDF
results = []

for pdf_file in pdf_files:
    print(f"\n{'=' * 70}")
    print(f"Testing: {pdf_file.name}")
    print("=" * 70)
    
    try:
        # Read PDF
        print("1. Reading PDF...")
        with open(pdf_file, "rb") as f:
            pdf_bytes = f.read()
        
        file_size_mb = len(pdf_bytes) / (1024 * 1024)
        print(f"   File size: {file_size_mb:.2f} MB")
        
        # Extract text
        print("2. Extracting text...")
        import time
        start_time = time.time()
        
        extraction_result = extract_from_pdf(pdf_bytes, pdf_file.name)
        
        extraction_time = time.time() - start_time
        print(f"   Extraction time: {extraction_time:.2f} seconds")
        print(f"   Pages: {extraction_result['page_count']}")
        print(f"   Method: {extraction_result['extraction_method']}")
        print(f"   Confidence: {extraction_result['confidence_score']:.2f}")
        
        # Classify document
        print("3. Classifying document...")
        classification = classify_document(
            extraction_result['raw_text_preview'],
            pdf_file.name
        )
        
        print(f"   Classified as: {classification.doc_type}")
        print(f"   Confidence: {classification.confidence:.2f}")
        print(f"   Requires review: {classification.requires_human_review}")
        
        # Show matched patterns
        if classification.matched_patterns:
            print(f"   Matched patterns ({len(classification.matched_patterns)}):")
            for pattern in classification.matched_patterns[:5]:
                print(f"     • {pattern}")
            if len(classification.matched_patterns) > 5:
                print(f"     ... and {len(classification.matched_patterns) - 5} more")
        
        # Show company name
        if extraction_result.get('company_name'):
            print(f"   Company detected: {extraction_result['company_name']}")
        
        # Show financial figures
        fig_count = len(extraction_result.get('financial_figures', []))
        print(f"   Financial figures: {fig_count}")
        if fig_count > 0:
            print("   Sample figures:")
            for fig in extraction_result['financial_figures'][:3]:
                print(f"     • {fig['value']}")
        
        # Show key sections
        section_count = len(extraction_result.get('key_sections', []))
        print(f"   Key sections: {section_count}")
        if section_count > 0:
            print("   Sections detected:")
            for section in extraction_result['key_sections'][:5]:
                print(f"     • {section}")
        
        # Show risk phrases
        risk_count = len(extraction_result.get('risk_phrases', []))
        print(f"   Risk phrases: {risk_count}")
        if risk_count > 0:
            print("   Risk phrases found:")
            for phrase in extraction_result['risk_phrases'][:3]:
                print(f"     • {phrase['phrase']} (Page {phrase['page']})")
        
        # Store results
        results.append({
            'file': pdf_file.name,
            'size_mb': file_size_mb,
            'pages': extraction_result['page_count'],
            'extraction_time': extraction_time,
            'extraction_method': extraction_result['extraction_method'],
            'confidence': extraction_result['confidence_score'],
            'classified_as': classification.doc_type,
            'classification_confidence': classification.confidence,
            'company_name': extraction_result.get('company_name'),
            'figures': fig_count,
            'sections': section_count,
            'risks': risk_count,
            'status': 'SUCCESS'
        })
        
        print("\n✓ Test PASSED")
        
    except Exception as e:
        print(f"\n✗ Test FAILED: {e}")
        results.append({
            'file': pdf_file.name,
            'status': 'FAILED',
            'error': str(e)
        })

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)

success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
total_count = len(results)

print(f"\nTests run: {total_count}")
print(f"Passed: {success_count}")
print(f"Failed: {total_count - success_count}")

if success_count > 0:
    print("\n" + "-" * 70)
    print("Successful Tests:")
    print("-" * 70)
    
    for result in results:
        if result['status'] == 'SUCCESS':
            print(f"\n{result['file']}")
            print(f"  Size: {result['size_mb']:.2f} MB")
            print(f"  Pages: {result['pages']}")
            print(f"  Time: {result['extraction_time']:.2f}s")
            print(f"  Method: {result['extraction_method']}")
            print(f"  Classified: {result['classified_as']} ({result['classification_confidence']:.0%})")
            if result['company_name']:
                print(f"  Company: {result['company_name']}")
            print(f"  Figures: {result['figures']}, Sections: {result['sections']}, Risks: {result['risks']}")

if total_count - success_count > 0:
    print("\n" + "-" * 70)
    print("Failed Tests:")
    print("-" * 70)
    
    for result in results:
        if result['status'] == 'FAILED':
            print(f"\n{result['file']}")
            print(f"  Error: {result['error']}")

# Performance metrics
if success_count > 0:
    avg_time = sum(r['extraction_time'] for r in results if r['status'] == 'SUCCESS') / success_count
    avg_pages = sum(r['pages'] for r in results if r['status'] == 'SUCCESS') / success_count
    
    print("\n" + "-" * 70)
    print("Performance Metrics:")
    print("-" * 70)
    print(f"  Average extraction time: {avg_time:.2f} seconds")
    print(f"  Average pages: {avg_pages:.0f}")
    print(f"  Average speed: {avg_pages/avg_time:.1f} pages/second")

print("\n" + "=" * 70)
if success_count == total_count:
    print("ALL TESTS PASSED ✓")
    print("System ready for real NBFC documents!")
else:
    print(f"SOME TESTS FAILED ({total_count - success_count}/{total_count})")
    print("Review errors above")
print("=" * 70)
