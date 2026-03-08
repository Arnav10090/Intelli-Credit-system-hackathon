# Intelli-Credit Bugfixes Design

## Overview

This design addresses three critical bugs in the Intelli-Credit system that affect CAM accuracy and LLM functionality:

1. **False Litigation Finding Bug**: Surya Pharmaceuticals CAM displays false "fail to pay loan" finding despite clean research cache
2. **Em-dash Encoding Corruption Bug**: Generated .docx files show "â€"" instead of proper dashes
3. **Groq API Initialization Bug**: LLM client initialized as None due to module-level import timing issue

The fix approach is minimal and surgical: (1) ensure research cache is loaded from the correct demo directory based on scenario, (2) sanitize Unicode dash characters to ASCII hyphen-minus before writing to Word documents, and (3) implement lazy initialization for the OpenAI client after environment variables are loaded.

## Glossary

- **Bug_Condition (C)**: The condition that triggers each bug
- **Property (P)**: The desired behavior when the bug condition is met
- **Preservation**: Existing functionality that must remain unchanged by the fixes
- **research_cache.json**: Pre-built research data file containing litigation findings and news articles
- **demo_company**: Acme Textiles demo (Grade C / REJECT scenario)
- **demo_company2**: Surya Pharmaceuticals demo (Grade A+ / APPROVE scenario)
- **_grok_client**: Module-level OpenAI client instance in llm_narrator.py
- **python-docx**: Node.js library used to generate Word documents via subprocess
- **em-dash (U+2014)**: Unicode character "—" that causes encoding corruption
- **en-dash (U+2013)**: Unicode character "–" that causes encoding corruption

## Bug Details

### Bug 1: False Litigation Finding

The bug manifests when the Surya Pharmaceuticals demo is loaded and the CAM is generated. The system displays "Firm owners fail to pay loan, banks paste possession notice" with Risk Δ: -30 in Section 6, despite demo_company2/research_cache.json containing only clean litigation records with aggregate_label "LOW".

**Formal Specification:**
```
FUNCTION isBugCondition1(input)
  INPUT: input of type { scenario: string, case_id: string }
  OUTPUT: boolean
  
  RETURN input.scenario == "surya"
         AND load_demo_endpoint_called(input.case_id, "surya")
         AND generate_cam_endpoint_called(input.case_id)
         AND cam_section_6_displays_false_litigation_finding()
END FUNCTION
```

**Root Cause**: The `_load_research_cache` function in `backend/api/cam_routes.py` queries for documents with filename "research_cache_demo.json" but does NOT filter by the demo scenario. When both Acme and Surya demos have been loaded in the same database, the query returns the FIRST match ordered by `processed_at.desc()`, which may be the stale Acme cache instead of the fresh Surya cache.

### Bug 2: Em-dash Encoding Corruption

The bug manifests when the CAM document builder writes text containing em-dashes (U+2014) or en-dashes (U+2013) to the Word document. The generated .docx displays corrupted characters "â€"" instead of proper dashes.

**Formal Specification:**
```
FUNCTION isBugCondition2(input)
  INPUT: input of type { text: string }
  OUTPUT: boolean
  
  RETURN (input.text CONTAINS '\u2014' OR input.text CONTAINS '\u2013')
         AND text_passed_to_nodejs_docx_builder(input.text)
         AND generated_docx_displays_corrupted_characters()
END FUNCTION
```

**Root Cause**: The Node.js script in `backend/cam/doc_builder.py` passes Unicode dash characters directly to the `docx` library's `TextRun()` constructor. The UTF-8 encoding is misinterpreted during the Word document generation process, resulting in multi-byte corruption patterns where "—" becomes "â€"".

### Bug 3: Groq API Not Being Called

The bug manifests when the FastAPI application starts with a valid LLM_API_KEY in .env, but the OpenAI client is initialized as None because config.py loads environment variables after the llm_narrator.py module imports and initializes the client at module level.

**Formal Specification:**
```
FUNCTION isBugCondition3(input)
  INPUT: input of type { env_vars: dict, case_id: string }
  OUTPUT: boolean
  
  RETURN input.env_vars["LLM_API_KEY"] IS_VALID
         AND fastapi_application_started()
         AND generate_cam_narrative_called(input.case_id)
         AND _grok_client == None
         AND template_fallback_used()
END FUNCTION
```

**Root Cause**: The `_grok_client` variable in `backend/cam/llm_narrator.py` is initialized at module import time (lines 42-47). At this point, `backend/config.py` has not yet loaded the .env file via `pydantic_settings`, so `LLM_API_KEY` is an empty string, causing the client to be set to None. When `generate_cam_narrative()` is later called, it checks `if _grok_client is not None` and falls back to template generation.

### Examples

**Bug 1 Examples:**
- Load Surya demo → Generate CAM → Section 6 shows "fail to pay loan" (INCORRECT)
- Load Acme demo → Load Surya demo → Generate CAM for Surya → Section 6 shows Acme's litigation (INCORRECT)
- Load Surya demo in fresh database → Generate CAM → Section 6 shows clean findings (CORRECT)

**Bug 2 Examples:**
- Scorecard decision text: "APPROVE — Grade A+ (92/100)" → displays as "APPROVE â€" Grade A+ (92/100)"
- Footer text: "CONFIDENTIAL — Credit Appraisal Memo" → displays as "CONFIDENTIAL â€" Credit Appraisal Memo"
- Any narrative text with em-dashes → displays with corruption

**Bug 3 Examples:**
- Set LLM_API_KEY in .env → Start app → Generate CAM → Audit trail shows "Narrative source: Deterministic template" (INCORRECT)
- Set LLM_API_KEY in .env → Start app → Generate CAM → Audit trail shows "Narrative source: llama-3.3-70b-versatile" (CORRECT)
- Empty LLM_API_KEY → Start app → Generate CAM → Template fallback used (CORRECT - expected behavior)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Acme Textiles (demo_company) demo must continue to load research data correctly from demo_company/research_cache.json
- CAM document builder must continue to display text without special Unicode characters correctly
- System must continue to fall back gracefully to deterministic template generation when LLM_API_KEY is not set or empty
- All financial tables, scorecard data, and loan calculations must continue to be populated correctly from deterministic modules
- Runtime cache mechanism must continue to function for performance optimization when research data is loaded from live API sources
- All CAM sections (cover page, financial summary, scorecard, etc.) must continue to be formatted correctly with proper tables and styling
- Text sanitization must preserve the semantic meaning of text with only visual dash characters being normalized
- OpenAI client lazy initialization must respect LLM_MODEL and LLM_BASE_URL configuration from environment variables

**Scope:**
All inputs that do NOT involve the three specific bug conditions should be completely unaffected by these fixes. This includes:
- Other demo scenarios beyond Acme and Surya
- CAM generation for cases without Unicode dash characters
- CAM generation when LLM_API_KEY is intentionally not configured
- All other API endpoints and data processing pipelines

## Hypothesized Root Cause

Based on the bug descriptions and code analysis, the root causes are:

### Bug 1: Research Cache Loading
1. **Insufficient Query Filtering**: The `_load_research_cache` function queries by filename "research_cache_demo.json" but does not distinguish between demo scenarios
2. **Stale Data Contamination**: When multiple demos are loaded sequentially, the database contains multiple documents with the same filename from different demo directories
3. **Order-By Ambiguity**: The `.order_by(Document.processed_at.desc())` clause returns the most recently processed document, which may not correspond to the current case's demo scenario

### Bug 2: Unicode Encoding
1. **Direct Unicode Pass-Through**: The Node.js script passes Unicode dash characters (U+2014, U+2013) directly to the docx library without sanitization
2. **UTF-8 Misinterpretation**: The python-docx library (or the underlying XML generation) misinterprets the UTF-8 encoding of these characters
3. **Multi-Byte Corruption**: The em-dash (3 bytes in UTF-8: 0xE2 0x80 0x94) is decoded incorrectly, producing the visible corruption "â€"" (which is the UTF-8 bytes interpreted as Windows-1252)

### Bug 3: Module Import Timing
1. **Module-Level Initialization**: The `_grok_client` is initialized at module import time (line 42-47 in llm_narrator.py)
2. **Environment Variable Loading Order**: The `backend/config.py` module loads environment variables via `pydantic_settings.BaseSettings`, which reads the .env file when the Settings class is instantiated
3. **Import-Time Evaluation**: When `llm_narrator.py` imports `LLM_API_KEY` from `backend.config`, the value is evaluated immediately, before the FastAPI app startup has triggered the .env loading
4. **Immutable None Assignment**: Once `_grok_client = None`, it remains None for the lifetime of the process

## Correctness Properties

Property 1: Bug Condition - Research Cache Loaded from Correct Demo Directory

_For any_ case where the load-demo endpoint is called with scenario="surya" and the CAM is subsequently generated, the fixed _load_research_cache function SHALL load research data from demo_company2/research_cache.json (not demo_company/research_cache.json), ensuring that Section 6 displays only the clean litigation findings with aggregate_label "LOW" and no false possession notice finding.

**Validates: Requirements 2.1, 2.2**

Property 2: Bug Condition - Unicode Dashes Sanitized Before Word Document Generation

_For any_ text containing em-dashes (U+2014) or en-dashes (U+2013) that is passed to the CAM document builder, the fixed sanitization function SHALL replace all Unicode dash characters with ASCII hyphen-minus ("-") before writing to the Word document, ensuring that the generated .docx displays proper dashes without any encoding corruption.

**Validates: Requirements 2.3, 2.4**

Property 3: Bug Condition - LLM Client Lazily Initialized After Environment Variables Loaded

_For any_ application startup where LLM_API_KEY is set to a valid value in the .env file, the fixed llm_narrator module SHALL lazily initialize the OpenAI client on first use (after config.py has loaded environment variables), ensuring that generate_cam_narrative() successfully calls the Groq API and the audit trail shows "Narrative source: llama-3.3-70b-versatile" instead of "Narrative source: Deterministic template".

**Validates: Requirements 2.5, 2.6, 2.7, 2.8, 2.9**

Property 4: Preservation - Acme Demo Research Data Unchanged

_For any_ case where the load-demo endpoint is called with scenario="acme" (or default), the fixed _load_research_cache function SHALL produce exactly the same result as the original function, preserving the correct loading of research data from demo_company/research_cache.json.

**Validates: Requirements 3.1**

Property 5: Preservation - Non-Unicode Text Display Unchanged

_For any_ text that does NOT contain Unicode dash characters (em-dash, en-dash), the fixed sanitization function SHALL produce exactly the same output as the original function, preserving correct text display in generated .docx files.

**Validates: Requirements 3.2, 3.7**

Property 6: Preservation - Template Fallback When LLM_API_KEY Not Set

_For any_ application startup where LLM_API_KEY is not set or empty, the fixed llm_narrator module SHALL produce exactly the same behavior as the original module, preserving graceful fallback to deterministic template generation.

**Validates: Requirements 3.3, 3.4, 3.8**

## Fix Implementation

### Bug 1: Research Cache Loading Fix

**CRITICAL**: The fix must address the FULL data flow chain, not just the CAM generation endpoint.

**Data Flow Chain**:
1. **load-demo endpoint** (`backend/api/ingest_routes.py`) → Loads research_cache.json and stores it in the Document table
2. **Database storage** → Document record with file_path pointing to the demo directory
3. **CAM generation** (`backend/api/cam_routes.py`) → Reads research cache from Document table via `_load_research_cache`

**Root Cause**: The `_load_research_cache` function in `cam_routes.py` queries by filename "research_cache_demo.json" without filtering by the correct demo directory. When both Acme and Surya demos have been loaded, it returns the wrong cache.

**Files to Fix**:

**File 1**: `backend/api/ingest_routes.py` (load-demo endpoint)
**Function**: `load_demo_data`
**Changes**:
1. **Clean up stale documents**: Before loading new demo data, delete any existing documents with filename "research_cache_demo.json" for this case_id to prevent contamination
2. **Store demo scenario**: Consider adding a metadata field to the Document record to track which demo scenario it belongs to (optional enhancement)

**File 2**: `backend/api/cam_routes.py` (CAM generation)
**Function**: `_load_research_cache`
**Changes**:
1. **Query by case_id**: The current implementation already filters by case_id, but we need to ensure it gets the MOST RECENT document for this case
2. **Add file_path validation**: Verify the file_path contains the correct demo directory based on the case's company_name
3. **Alternative**: Query the Case table to get company_name, map to demo directory, and filter by exact file_path

**Specific Implementation**:
1. **Add Case-to-Demo-Directory Mapping**: Query the Case table to retrieve the company_name for the given case_id
2. **Determine Demo Directory**: Map company_name to the correct demo directory:
   - "Surya Pharmaceuticals Ltd" → demo_company2
   - "Acme Textiles Ltd" → demo_company
   - Other → return empty dict (no demo cache)
3. **Filter by File Path**: Instead of querying by filename alone, construct the expected file_path using the demo directory and filter by that exact path
4. **Ensure load-demo cleans up**: The load-demo endpoint already has cleanup logic (lines 169-174 in ingest_routes.py) that deletes old documents, which should prevent stale cache contamination

### Bug 2: Em-dash Encoding Fix

**File**: `backend/cam/doc_builder.py`

**IMPORTANT**: doc_builder.py is a PYTHON file that contains a Node.js script as a string constant. The sanitization must be added to the JavaScript code INSIDE the Python string.

**Function**: Node.js script constant `_NODE_SCRIPT` (lines 30-805+)

**Specific Changes**:
1. **Add Sanitization Helper Function**: Insert a JavaScript function `sanitizeDashes(text)` inside the `_NODE_SCRIPT` string constant that replaces all Unicode dash characters with ASCII hyphen-minus:
   ```javascript
   function sanitizeDashes(text) {
     if (typeof text !== 'string') return text;
     return text
       .replace(/\u2014/g, '-')  // em-dash
       .replace(/\u2013/g, '-')  // en-dash
       .replace(/\u2012/g, '-')  // figure dash
       .replace(/\u2015/g, '-'); // horizontal bar
   }
   ```

2. **Apply Sanitization in cell() Helper**: Modify the `cell()` function to sanitize text before passing to TextRun:
   ```javascript
   text: sanitizeDashes(String(text == null ? '-' : text)),
   ```

3. **Apply Sanitization in para() Helper**: Modify the `para()` function to sanitize text:
   ```javascript
   text: sanitizeDashes(String(text || '')),
   ```

4. **Apply Sanitization in h1() and h2() Helpers**: Modify heading functions to sanitize text:
   ```javascript
   text: sanitizeDashes(text),
   ```

5. **Replace Default Em-dash with Hyphen**: Change the default null value from `'\u2014'` to `'-'` in the cell() function

### Bug 3: Groq API Initialization Fix

**File**: `backend/cam/llm_narrator.py`

**Function**: Module-level initialization and `generate_cam_narrative`

**Specific Changes**:
1. **Remove Module-Level Client Initialization**: Delete lines 42-47 that initialize `_grok_client` at import time
2. **Add Lazy Initialization Function**: Create a new function `_get_client()` that initializes the client on first use:
   ```python
   _grok_client = None
   
   def _get_client():
       global _grok_client
       if _grok_client is None and LLM_API_KEY:
           try:
               from openai import OpenAI
               from backend.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
               _grok_client = OpenAI(
                   api_key=LLM_API_KEY,
                   base_url=LLM_BASE_URL,
               )
               logger.info(
                   "LLM client initialized: model=%s, base_url=%s, api_key=%s...",
                   LLM_MODEL, LLM_BASE_URL, LLM_API_KEY[:8]
               )
           except Exception as e:
               logger.error("Failed to initialize LLM client: %s", e)
       return _grok_client
   ```

3. **Update generate_cam_narrative**: Replace `if _grok_client is not None:` with `if _get_client() is not None:`

4. **Update _call_grok_api**: Replace `_grok_client.chat.completions.create` with `_get_client().chat.completions.create`

5. **Add Startup Logging**: Add a log message in the lazy initialization function to confirm LLM configuration (Requirement 2.8)

6. **Add Error Logging**: Wrap the Groq API call in a try-except block and log the exception type and message before falling back to template generation (Requirement 2.9)

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate each bug on unfixed code, then verify the fixes work correctly and preserve existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate all three bugs BEFORE implementing the fixes. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate the bug conditions and assert the expected failures. Run these tests on the UNFIXED code to observe failures and understand the root causes.

**Test Cases**:
1. **Bug 1 - False Litigation Test**: Load Acme demo, then load Surya demo, generate CAM for Surya, assert Section 6 shows clean findings (will fail on unfixed code - shows Acme's litigation)
2. **Bug 1 - Stale Cache Test**: Load Surya demo, generate CAM, check that research_cache.json path in logs matches demo_company2 (will fail on unfixed code - may load from demo_company)
3. **Bug 2 - Em-dash Corruption Test**: Generate CAM with em-dashes in text, extract text from .docx, assert no "â€"" corruption (will fail on unfixed code)
4. **Bug 2 - Scorecard Decision Test**: Generate CAM, check scorecard decision line for proper dashes (will fail on unfixed code - shows corruption)
5. **Bug 3 - LLM Client Initialization Test**: Set valid LLM_API_KEY, start app, generate CAM, assert audit trail shows LLM model name (will fail on unfixed code - shows template fallback)
6. **Bug 3 - Startup Log Test**: Set valid LLM_API_KEY, start app, check logs for LLM configuration message (will fail on unfixed code - no log message)

**Expected Counterexamples**:
- Bug 1: CAM Section 6 displays "fail to pay loan" for Surya demo despite clean cache
- Bug 2: Generated .docx contains "â€"" instead of "-" in multiple locations
- Bug 3: Audit trail shows "Narrative source: Deterministic template" despite valid API key
- Possible causes: query filtering issue, UTF-8 encoding issue, module import timing issue

### Fix Checking

**Goal**: Verify that for all inputs where each bug condition holds, the fixed functions produce the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition1(input) DO
  result := _load_research_cache_fixed(input.case_id)
  ASSERT result.file_path CONTAINS "demo_company2/research_cache.json"
  ASSERT cam_section_6_displays_clean_findings()
END FOR

FOR ALL input WHERE isBugCondition2(input) DO
  result := sanitizeDashes(input.text)
  ASSERT result DOES_NOT_CONTAIN '\u2014'
  ASSERT result DOES_NOT_CONTAIN '\u2013'
  ASSERT generated_docx_displays_proper_dashes()
END FOR

FOR ALL input WHERE isBugCondition3(input) DO
  result := generate_cam_narrative_fixed(input)
  ASSERT result.model_used == "llama-3.3-70b-versatile"
  ASSERT audit_trail_shows_llm_source()
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug conditions do NOT hold, the fixed functions produce the same result as the original functions.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition1(input) DO
  ASSERT _load_research_cache_original(input) = _load_research_cache_fixed(input)
END FOR

FOR ALL input WHERE NOT isBugCondition2(input) DO
  ASSERT sanitizeDashes(input.text) = input.text
END FOR

FOR ALL input WHERE NOT isBugCondition3(input) DO
  ASSERT generate_cam_narrative_original(input) = generate_cam_narrative_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for non-bug scenarios, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Acme Demo Preservation**: Load Acme demo, generate CAM, verify research data loaded from demo_company/research_cache.json
2. **Non-Unicode Text Preservation**: Generate CAM with text containing no Unicode dashes, verify output is identical to unfixed code
3. **Template Fallback Preservation**: Start app with empty LLM_API_KEY, generate CAM, verify template fallback is used
4. **Financial Tables Preservation**: Generate CAM, verify all financial tables are populated correctly
5. **Scorecard Preservation**: Generate CAM, verify Five Cs scorecard is calculated correctly
6. **Loan Sizing Preservation**: Generate CAM, verify loan terms and security cover are calculated correctly

### Unit Tests

- Test `_load_research_cache` with Acme scenario (should load from demo_company)
- Test `_load_research_cache` with Surya scenario (should load from demo_company2)
- Test `_load_research_cache` with unknown scenario (should return empty dict)
- Test `sanitizeDashes` with em-dash input (should return hyphen-minus)
- Test `sanitizeDashes` with en-dash input (should return hyphen-minus)
- Test `sanitizeDashes` with no Unicode dashes (should return unchanged)
- Test `_get_client` with valid LLM_API_KEY (should return OpenAI client)
- Test `_get_client` with empty LLM_API_KEY (should return None)
- Test `_get_client` called multiple times (should return same client instance)

### Property-Based Tests

- Generate random case scenarios (Acme, Surya, other) and verify research cache is loaded from correct directory
- Generate random text with and without Unicode dashes and verify sanitization preserves non-Unicode text
- Generate random LLM_API_KEY values (valid, empty, invalid) and verify client initialization behavior
- Test that all non-buggy inputs continue to work across many scenarios

### Integration Tests

- Full E2E test: Load Surya demo → Generate CAM → Verify Section 6 shows clean findings
- Full E2E test: Load Acme demo → Generate CAM → Verify Section 6 shows high-risk findings
- Full E2E test: Set valid LLM_API_KEY → Start app → Generate CAM → Verify LLM narrative is used
- Full E2E test: Generate CAM → Extract .docx text → Verify no encoding corruption
- Cross-scenario test: Load Acme → Load Surya → Generate CAM for both → Verify correct research data for each
