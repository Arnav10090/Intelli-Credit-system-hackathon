# Implementation Plan

## Bug 1: False Litigation Finding

- [x] 1. Write bug condition exploration test for false litigation finding
  - **Property 1: Bug Condition** - Research Cache Loaded from Correct Demo Directory
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Test the specific scenario where Acme is loaded first, then Surya is loaded, and CAM is generated for Surya
  - Test implementation: Load Acme demo → Load Surya demo → Generate CAM for Surya case → Assert Section 6 displays clean litigation findings (aggregate_label "LOW") with no "fail to pay loan" finding
  - The test assertions should match Expected Behavior Property 1: research data loaded from demo_company2/research_cache.json
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (Section 6 shows Acme's "fail to pay loan" finding instead of Surya's clean findings)
  - Document counterexamples found to understand root cause (e.g., which research_cache.json was loaded, what file_path was used in query)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.1, 2.2_

- [ ] 2. Write preservation property tests for research cache loading (BEFORE implementing fix)
  - **Property 2: Preservation** - Acme Demo Research Data Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code: Load Acme demo (scenario="acme" or default) → Generate CAM → Check that research data is loaded from demo_company/research_cache.json
  - Write property-based test: For all cases where scenario is "acme" or default, research cache should be loaded from demo_company directory
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1_

- [ ] 3. Fix for false litigation finding bug

  - [x] 3.1 Implement the research cache loading fix across the full data flow chain
    - **CRITICAL**: Fix both the load-demo endpoint AND the CAM generation endpoint
    - **File 1: backend/api/ingest_routes.py (load_demo_data function)**
      - Verify the existing cleanup logic (lines 169-174) properly deletes old research_cache_demo.json documents
      - Ensure the new research cache document is stored with the correct file_path pointing to the demo directory
    - **File 2: backend/api/cam_routes.py (_load_research_cache function)**
      - Query the Case table to retrieve company_name for the given case_id
      - Map company_name to correct demo directory: "Surya Pharmaceuticals Ltd" → demo_company2, "Acme Textiles Ltd" → demo_company
      - Construct expected file_path using demo directory and filter by exact path instead of filename alone
      - Handle unknown scenarios by returning empty dict
    - _Bug_Condition: isBugCondition1(input) where input.scenario == "surya" AND load_demo_endpoint_called AND generate_cam_endpoint_called_
    - _Expected_Behavior: Research data loaded from demo_company2/research_cache.json for Surya scenario (Property 1 from design)_
    - _Preservation: Acme demo continues to load from demo_company/research_cache.json (Property 4 from design)_
    - _Requirements: 2.1, 2.2, 3.1_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Research Cache Loaded from Correct Demo Directory
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (Section 6 shows Surya's clean findings, no false litigation)
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Acme Demo Research Data Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (Acme demo still loads correctly from demo_company)
    - Confirm all tests still pass after fix (no regressions)

## Bug 2: Em-dash Encoding Corruption

- [ ] 4. Write bug condition exploration test for em-dash encoding corruption
  - **Property 1: Bug Condition** - Unicode Dashes Sanitized Before Word Document Generation
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Test specific text containing em-dashes (U+2014) and en-dashes (U+2013) in CAM generation
  - Test implementation: Generate CAM with text containing "APPROVE — Grade A+" → Extract text from generated .docx → Assert no "â€"" corruption appears
  - The test assertions should match Expected Behavior Property 2: Unicode dashes replaced with ASCII hyphen-minus before writing to Word document
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (generated .docx contains "â€"" corruption)
  - Document counterexamples found (e.g., which specific text locations show corruption, what the corrupted bytes are)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.3, 2.4_

- [ ] 5. Write preservation property tests for text display (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Unicode Text Display Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code: Generate CAM with text containing NO Unicode dash characters → Extract text from .docx → Record the output
  - Write property-based test: For all text that does NOT contain em-dash or en-dash, the generated .docx should display text identically to unfixed code
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (confirms baseline text display behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.2, 3.7_

- [ ] 6. Fix for em-dash encoding corruption bug

  - [ ] 6.1 Implement the Unicode dash sanitization fix in backend/cam/doc_builder.py
    - **IMPORTANT**: doc_builder.py is a PYTHON file containing a Node.js script as a string constant (_NODE_SCRIPT)
    - **DO NOT write Python sanitization** - the fix must be JavaScript code INSIDE the _NODE_SCRIPT string
    - Add JavaScript sanitizeDashes(text) helper function inside _NODE_SCRIPT that replaces U+2014, U+2013, U+2012, U+2015 with ASCII hyphen-minus "-"
    - Apply sanitization in cell() helper before passing to TextRun
    - Apply sanitization in para() helper before passing to TextRun
    - Apply sanitization in h1() and h2() helpers before passing to TextRun
    - Replace default em-dash '\u2014' with hyphen '-' in cell() function
    - _Bug_Condition: isBugCondition2(input) where input.text contains '\u2014' OR '\u2013' AND text_passed_to_nodejs_docx_builder_
    - _Expected_Behavior: All Unicode dash characters replaced with ASCII hyphen-minus before Word document generation (Property 2 from design)_
    - _Preservation: Text without Unicode dashes displays identically to unfixed code (Property 5 from design)_
    - _Requirements: 2.3, 2.4, 3.2, 3.7_

  - [ ] 6.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Unicode Dashes Sanitized Before Word Document Generation
    - **IMPORTANT**: Re-run the SAME test from task 4 - do NOT write a new test
    - The test from task 4 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 4
    - **EXPECTED OUTCOME**: Test PASSES (generated .docx displays proper dashes, no "â€"" corruption)
    - _Requirements: 2.3, 2.4_

  - [ ] 6.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Unicode Text Display Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 5 - do NOT write new tests
    - Run preservation property tests from step 5
    - **EXPECTED OUTCOME**: Tests PASS (text without Unicode dashes still displays correctly)
    - Confirm all tests still pass after fix (no regressions)

## Bug 3: Groq API Initialization

- [ ] 7. Write bug condition exploration test for Groq API initialization
  - **Property 1: Bug Condition** - LLM Client Lazily Initialized After Environment Variables Loaded
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Test the specific scenario where LLM_API_KEY is set in .env and app is started
  - Test implementation: Set valid LLM_API_KEY in .env → Start FastAPI app → Generate CAM → Assert audit trail shows "Narrative source: llama-3.3-70b-versatile" (not "Deterministic template")
  - The test assertions should match Expected Behavior Property 3: OpenAI client initialized after environment variables loaded
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (audit trail shows "Deterministic template" because _grok_client is None)
  - Document counterexamples found (e.g., check _grok_client value at startup, check when LLM_API_KEY is evaluated)
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 2.5, 2.6, 2.7, 2.8, 2.9_

- [ ] 8. Write preservation property tests for LLM fallback behavior (BEFORE implementing fix)
  - **Property 2: Preservation** - Template Fallback When LLM_API_KEY Not Set
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code: Start app with empty or missing LLM_API_KEY → Generate CAM → Check that template fallback is used
  - Write property-based test: For all cases where LLM_API_KEY is not set or empty, system should fall back to deterministic template generation
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (confirms baseline fallback behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.3, 3.4, 3.8_

- [ ] 9. Fix for Groq API initialization bug

  - [ ] 9.1 Implement the lazy initialization fix in backend/cam/llm_narrator.py
    - Remove module-level _grok_client initialization (lines 42-47)
    - Create _get_client() function that initializes client on first use with global _grok_client variable
    - Import OpenAI and config values inside _get_client() to ensure environment variables are loaded
    - Add startup logging to confirm LLM configuration (model, base_url, api_key prefix)
    - Add error logging with exception type and message before template fallback
    - Update generate_cam_narrative to call _get_client() instead of checking _grok_client directly
    - Update _call_grok_api to use _get_client().chat.completions.create
    - _Bug_Condition: isBugCondition3(input) where LLM_API_KEY is valid AND fastapi_application_started AND _grok_client == None_
    - _Expected_Behavior: OpenAI client lazily initialized after environment variables loaded (Property 3 from design)_
    - _Preservation: Template fallback when LLM_API_KEY not set (Property 6 from design)_
    - _Requirements: 2.5, 2.6, 2.7, 2.8, 2.9, 3.3, 3.4, 3.8_

  - [ ] 9.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - LLM Client Lazily Initialized After Environment Variables Loaded
    - **IMPORTANT**: Re-run the SAME test from task 7 - do NOT write a new test
    - The test from task 7 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 7
    - **EXPECTED OUTCOME**: Test PASSES (audit trail shows "llama-3.3-70b-versatile", LLM is called)
    - _Requirements: 2.5, 2.6, 2.7, 2.8, 2.9_

  - [ ] 9.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Template Fallback When LLM_API_KEY Not Set
    - **IMPORTANT**: Re-run the SAME tests from task 8 - do NOT write new tests
    - Run preservation property tests from step 8
    - **EXPECTED OUTCOME**: Tests PASS (template fallback still works when LLM_API_KEY not set)
    - Confirm all tests still pass after fix (no regressions)

## Final Validation

- [ ] 10. Checkpoint - Ensure all tests pass
  - Run all bug condition exploration tests (tasks 1, 4, 7) - all should PASS
  - Run all preservation property tests (tasks 2, 5, 8) - all should PASS
  - Run full integration test: Load Acme → Load Surya → Generate CAM for both → Verify correct research data and no encoding corruption
  - Verify LLM client initialization with valid API key
  - Ensure all tests pass, ask the user if questions arise
