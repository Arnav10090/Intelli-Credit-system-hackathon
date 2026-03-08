# Bugfix Requirements Document

## Introduction

This document specifies the requirements for fixing three critical bugs in the Intelli-Credit system:

1. **False litigation finding in Surya Pharmaceuticals CAM** - The system displays a false "fail to pay loan" finding despite the clean research cache
2. **Em-dash encoding corruption in CAM Word documents** - Generated .docx files show "â€"" instead of proper dashes
3. **Groq API not being called despite correct .env configuration** - The system falls back to template narrative despite valid API credentials

These bugs affect the accuracy and professionalism of generated Credit Appraisal Memoranda and prevent the LLM-powered narrative generation from functioning.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the Surya Pharmaceuticals demo is loaded THEN the CAM Section 6 displays "Firm owners fail to pay loan, banks paste possession notice" with Risk Δ: -30 despite the demo_company2/research_cache.json containing only clean litigation records

1.2 WHEN the system loads research data for demo_company2 THEN it reads from a stale runtime cache file (backend/research/cache/4734b78e7a5b.json) instead of the authoritative demo_company2/research_cache.json

1.3 WHEN the CAM document builder writes text containing em-dashes (U+2014) or en-dashes (U+2013) to the Word document THEN the generated .docx displays corrupted characters "â€"" instead of proper dashes

1.4 WHEN text with em-dashes is passed to python-docx TextRun() or Paragraph() THEN the UTF-8 encoding is misinterpreted resulting in multi-byte corruption patterns

1.5 WHEN the FastAPI application starts with valid LLM_API_KEY in .env THEN the OpenAI client is initialized as None because config.py loads environment variables after the llm_narrator.py module imports and initializes the client at module level

1.6 WHEN generate_cam_narrative() is called with a valid Groq API configuration THEN the system uses template fallback because _grok_client was initialized to None at import time before dotenv was loaded

1.7 WHEN the CAM is generated with LLM_API_KEY correctly set THEN the audit trail shows "Narrative source: Deterministic template" instead of "Narrative source: llama-3.3-70b-versatile"

### Expected Behavior (Correct)

2.1 WHEN the Surya Pharmaceuticals demo is loaded THEN the CAM Section 6 SHALL display only the clean litigation findings from demo_company2/research_cache.json with aggregate_label "LOW" or "CLEAN" and no false possession notice finding

2.2 WHEN the load-demo endpoint is called for demo_company2 THEN the system SHALL invalidate any stale runtime cache files and reload fresh data from demo_company2/research_cache.json

2.3 WHEN the CAM document builder writes text containing em-dashes or en-dashes to the Word document THEN the generated .docx SHALL display proper hyphen-minus characters "-" without any encoding corruption

2.4 WHEN text is passed to python-docx TextRun() or Paragraph() THEN all Unicode dash characters SHALL be sanitized to ASCII hyphen-minus before writing to prevent encoding issues

2.5 WHEN the FastAPI application starts with valid LLM_API_KEY in .env THEN the OpenAI client SHALL be lazily initialized on first use after config.py has loaded the environment variables

2.6 WHEN generate_cam_narrative() is called with a valid Groq API configuration THEN the system SHALL successfully call the Groq API and generate LLM-powered narrative sections

2.7 WHEN the CAM is generated with LLM_API_KEY correctly set THEN the audit trail SHALL show "Narrative source: llama-3.3-70b-versatile" and the Executive Summary SHALL contain flowing prose instead of template text

2.8 WHEN the application starts THEN the startup log SHALL confirm the LLM configuration with a log message showing the model, base URL, and first 8 characters of the API key

2.9 WHEN the Groq API call fails THEN the error SHALL be logged with the exception type and message before falling back to template generation

### Unchanged Behavior (Regression Prevention)

3.1 WHEN demo_company (Acme Textiles) is loaded THEN the system SHALL CONTINUE TO load research data correctly from demo_company/research_cache.json

3.2 WHEN the CAM document builder writes text without special Unicode characters THEN the generated .docx SHALL CONTINUE TO display text correctly without any changes

3.3 WHEN the LLM_API_KEY is not set or empty THEN the system SHALL CONTINUE TO fall back gracefully to deterministic template generation

3.4 WHEN the CAM is generated with template fallback THEN all financial tables, scorecard data, and loan calculations SHALL CONTINUE TO be populated correctly from deterministic modules

3.5 WHEN research data is loaded from live API sources THEN the runtime cache mechanism SHALL CONTINUE TO function for performance optimization

3.6 WHEN the Word document is generated THEN all sections (cover page, financial summary, scorecard, etc.) SHALL CONTINUE TO be formatted correctly with proper tables and styling

3.7 WHEN text sanitization is applied THEN the semantic meaning of the text SHALL CONTINUE TO be preserved with only visual dash characters being normalized

3.8 WHEN the OpenAI client is lazily initialized THEN the LLM_MODEL and LLM_BASE_URL configuration SHALL CONTINUE TO be respected from environment variables
