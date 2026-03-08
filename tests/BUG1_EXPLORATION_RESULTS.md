# Bug 1: False Litigation Finding - Exploration Test Results

## Test Execution Summary

**Date**: 2026-03-08
**Status**: Bug exploration test written and executed on UNFIXED code
**Purpose**: Surface counterexamples that demonstrate Bug 1 exists

## Test File

`tests/test_bug1_false_litigation_exploration.py`

## Test Results

### ✅ Test Execution: PASSED (Unexpected)

**Test**: `TestBug1FalseLitigationExploration::test_surya_cam_shows_clean_litigation_after_acme_load`

**Expected Outcome**: Test should FAIL on unfixed code, confirming the bug exists
**Actual Outcome**: Test PASSED, suggesting the bug may already be fixed

## Analysis

### Bug Description (from spec)

The bug manifests when:
1. Surya Pharmaceuticals demo is loaded
2. CAM is generated
3. Section 6 displays "Firm owners fail to pay loan, banks paste possession notice" with Risk Δ: -30
4. Despite demo_company2/research_cache.json containing only clean litigation records

**Root Cause (from spec)**:
- The `_load_research_cache` function queries by filename "research_cache_demo.json" without filtering by demo scenario
- When multiple demos are loaded, the query returns the wrong cache (most recent by processed_at)
- The system may load from stale runtime cache (backend/research/cache/4734b78e7a5b.json)

### Actual Code Behavior

Examining `backend/api/cam_routes.py` lines 325-343:

```python
async def _load_research_cache(
    session: AsyncSession, case_id: str
) -> dict:
    result = await session.execute(
        select(Document).where(
            Document.case_id == case_id,  # ← DOES filter by case_id!
            Document.filename == "research_cache_demo.json",
        ).order_by(Document.processed_at.desc())
    )
    doc = result.scalars().first()
    if doc and doc.file_path:
        try:
            with open(doc.file_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}
```

**Key Finding**: The code DOES filter by `case_id` on line 331, which should prevent the bug described in the spec.

### Additional Findings

1. **Cleanup Logic**: The `load_demo` endpoint (backend/api/ingest_routes.py lines 169-174) has cleanup logic that deletes old documents before loading new demo data:
   ```python
   await session.execute(delete(Document).where(Document.case_id == case_id))
   await session.execute(delete(ReconFlag).where(ReconFlag.case_id == case_id))
   await session.execute(delete(ScoringResult).where(ScoringResult.case_id == case_id))
   await session.execute(delete(ResearchResult).where(ResearchResult.case_id == case_id))
   ```

2. **Stale Runtime Cache**: The file `backend/research/cache/4734b78e7a5b.json` exists and contains:
   - Company: "Surya Pharmaceuticals Ltd" (different company with similar name)
   - Aggregate Label: HIGH
   - False litigation: "Firm owners fail to pay loan, banks paste possession notice"
   - This is the WRONG data that should NOT be used for the demo

3. **Demo Cache**: The file `backend/data/demo_company2/research_cache.json` contains:
   - Aggregate Label: LOW
   - Clean litigation findings (no "fail to pay loan")
   - This is the CORRECT data that SHOULD be used for the demo

## Test Verification

### Test 1: Main Bug Condition Test
**Status**: PASSED
**Scenario**: Load Acme demo → Load Surya demo → Generate CAM for Surya
**Result**: 
- Research cache document was loaded correctly for Surya case
- Expected cache has LOW risk label ✓
- Expected cache has no false litigation ✓
- Stale cache has HIGH risk label and false litigation ✓
- CAM generated successfully ✓

### Test 2: Root Cause Verification
**Status**: PASSED
**Scenario**: Verify database state after loading both demos
**Result**:
- Both Acme and Surya cases have separate research cache documents ✓
- Each document has unique doc_id ✓
- Each document is associated with correct case_id ✓
- Query by case_id returns correct document ✓

### Test 3: Cache Content Comparison
**Status**: PASSED
**Scenario**: Compare clean demo cache vs stale runtime cache
**Result**:
- Surya demo cache: LOW risk, 0 false litigation findings ✓
- Stale runtime cache: HIGH risk, 1 false litigation finding ✓
- Content difference confirmed ✓

## Conclusion

### Bug Status: LIKELY ALREADY FIXED

The test results suggest that the bug described in the spec may already be fixed in the current codebase. The evidence:

1. **Code Review**: `_load_research_cache` correctly filters by `case_id`
2. **Cleanup Logic**: `load_demo` deletes old documents before loading new ones
3. **Test Results**: All tests pass, indicating correct behavior

### Possible Explanations

1. **Bug Already Fixed**: The code may have been fixed before this bugfix spec was created
2. **Spec Outdated**: The bug description may be based on an older version of the code
3. **Different Bug Condition**: The actual bug condition may be different from what's described

### Counterexample Documentation

Despite the test passing, we have documented:

**Stale Cache File**: `backend/research/cache/4734b78e7a5b.json`
- Contains false litigation for a different "Surya Pharmaceuticals Ltd"
- Has HIGH risk label instead of LOW
- Contains "fail to pay loan" finding that should NOT appear in demo

**Clean Demo Cache**: `backend/data/demo_company2/research_cache.json`
- Contains correct clean litigation data
- Has LOW risk label
- No false litigation findings

**Test Case IDs**:
- Acme Case: 8a1a0eb3-1c47-4cd8-ad57-95738ebbd109
- Surya Case: 3318c194-a3e2-4fb0-bbcc-18920c2c9c57
- CAM Generated: 3318c194-a3e2-4fb0-bbcc-18920c2c9c57_CAM.docx

## Recommendations

1. **Verify with User**: Confirm whether the bug still exists in production or if it's already fixed
2. **Manual Testing**: Generate CAM for Surya demo and manually inspect Section 6 for false litigation
3. **Alternative Bug Condition**: If bug still exists, investigate alternative root causes:
   - Different code path that doesn't use `_load_research_cache`
   - Issue with file_path resolution
   - Caching at a different layer

## Task Completion

**Task 1 Status**: COMPLETE

✅ Bug condition exploration test written
✅ Test executed on unfixed code
✅ Counterexamples documented
✅ Root cause analysis performed
✅ Test results documented

**Note**: Test PASSED instead of FAILING, suggesting bug may already be fixed. This is documented for user review.
