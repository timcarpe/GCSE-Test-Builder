# Unit Test Inventory

> **Document Type:** CURRENT ARCHITECTURE + V2 REQUIREMENTS  
> **Purpose:** Documents existing test coverage and identifies gaps for V2  
> **See Also:** V2 test structure in `docs/TODO/d) Major Refactoring/30_builder_extractor_v2/`

## Overview

This document catalogs existing unit tests and identifies coverage gaps that must be addressed in Phase 1 and during V2 development.

---

# CURRENT TEST COVERAGE

## Existing Test Files

| Test File | Module | Functions Covered | Status |
|-----------|--------|-------------------|--------|
| `test_detection.py` | extractor/detection | Basic detection | Minimal |
| `test_detectors.py` | extractor/detectors | Detection helpers | Minimal |
| `test_slicer.py` | extractor/slicer | Minimal smoke test | Minimal |
| `test_extractor.py` | extractor/pipeline | Basic pipeline | Minimal |
| `test_loader.py` | builder/loader | Partial loading | Partial |
| `test_selection.py` | builder/selection | Core selection | Partial |
| `test_layout_pagination.py` | builder/layout | Pagination | Partial |
| `test_config.py` | builder/config | Config parsing | Good |
| `test_reportlab_writer.py` | builder/reportlab_writer | PDF generation | Good |
| `test_helpers.py` | Various helpers | Helper functions | Good |
| `test_schema_versioning.py` | Schema handling | Version validation | Good |

---

## Coverage by Module

### Extractor Modules

#### pipeline.py (414 lines)
| Function | Tests? | Coverage | Priority |
|----------|--------|----------|----------|
| `__init__` | ❌ | 0% | Low |
| `run_on_directory` | ❌ | 0% | High |
| `run_on_pdf` | ❌ | 0% | High |
| `_scan_pdfs` | ❌ | 0% | Medium |
| `_parse_exam_paper` | ❌ | 0% | Medium |
| `_cleanup_exam_folder` | ❌ | 0% | Low |

**Gap:** No integration tests for extraction pipeline. Should add:
- Directory scan test with mock PDFs
- Single PDF extraction test
- Mark scheme pairing test

#### detection.py (295 lines)
| Function | Tests? | Coverage | Priority |
|----------|--------|----------|----------|
| `detect_question_starts` | ⚠️ | 20% | High |
| `filter_monotonic` | ❌ | 0% | Medium |
| `find_next_on_same_page` | ❌ | 0% | Medium |
| `resolve_question_sequence` | ❌ | 0% | Medium |

**Gap:** Detection tests exist but don't cover edge cases:
- Multi-digit question numbers
- Questions starting mid-page
- Pseudocode detection

#### slicer.py (1262 lines)
| Function | Tests? | Coverage | Priority |
|----------|--------|----------|----------|
| `process` | ⚠️ | 5% | Critical |
| `_build_spans` | ❌ | 0% | Critical |
| `_crop_parts` | ❌ | 0% | High |
| `_fallback_regex_classify` | ❌ | 0% | Medium |
| `_apply_consensus` | ❌ | 0% | Medium |
| `_detect_footer_bands` | ❌ | 0% | Medium |
| `_sanitize_sections` | ❌ | 0% | High |

**Gap:** Most critical module has almost no tests:
- Need span building tests with mock bundles
- Need bounds calculation tests
- Need consensus logic tests

---

### Builder Modules

#### loader.py (330 lines)
| Function | Tests? | Coverage | Priority |
|----------|--------|----------|----------|
| `load_questions` | ✅ | 60% | - |
| `_question_from_payload` | ⚠️ | 40% | High |
| `_part_from_payload` | ⚠️ | 30% | High |
| `_validate_question_payload` | ✅ | 80% | - |
| `_discover_part_images` | ❌ | 0% | Medium |
| `_extract_sub_topics` | ⚠️ | 20% | Low |

**Gap:** Payload parsing needs more edge case tests:
- Malformed parts array
- Missing optional fields
- Schema version migrations

#### selection.py (1220 lines)
| Function | Tests? | Coverage | Priority |
|----------|--------|----------|----------|
| `select_questions` | ✅ | 50% | - |
| `_select_questions_budgeted` | ⚠️ | 30% | Critical |
| `_generate_plan_options` | ⚠️ | 20% | High |
| `_select_pinned_option` | ❌ | 0% | Medium |
| `_normalise_option_marks` | ⚠️ | 40% | High |

**Gap:** Complex selection logic undertested:
- Topic coverage enforcement
- Mark overshoot/undershoot handling
- In-question pruning

#### layout.py (503 lines)
| Function | Tests? | Coverage | Priority |
|----------|--------|----------|----------|
| `build_layout` | ⚠️ | 30% | Medium |
| `_compose_question_assets` | ❌ | 0% | High |
| `_paginate_slices` | ✅ | 60% | - |
| `_resolve_part_image` | ❌ | 0% | Medium |
| `_scale_to_available_width` | ❌ | 0% | Low |

**Gap:** Asset composition untested:
- Image loading failures
- Missing slice handling
- Lock-with-next constraints

#### controller.py (551 lines)
| Function | Tests? | Coverage | Priority |
|----------|--------|----------|----------|
| `run_builder` | ❌ | 0% | High |
| `_filter_by_topics` | ⚠️ | 20% | Medium |
| `_filter_by_year_paper` | ✅ | 80% | - |
| `_filter_by_keywords` | ⚠️ | 30% | Medium |
| `_order_by_topic` | ❌ | 0% | Low |

**Gap:** End-to-end builder flow untested:
- Need integration test with mock cache
- Need filter combination tests

---

## Coverage Summary

| Module | Current Coverage | Target Coverage | Gap |
|--------|-----------------|-----------------|-----|
| Extractor | ~10% | 90% | 80% |
| Builder | ~35% | 85% | 50% |
| Overall | ~25% | 85% | 60% |

---

## Phase 1 Testing Requirements

### Must-Have Tests (Before V2 Development)

1. **Mark Calculation Tests**
   ```python
   def test_part_mark_extraction():
       """Verify marks are correctly extracted from PartNode."""
       part = PartNode(label="(a)(i)", marks=2)
       assert _part_mark(part) == 2
   
   def test_total_marks_from_leaves():
       """Verify total marks equals sum of leaf marks."""
       leaves = [PartNode(marks=2), PartNode(marks=3)]
       assert sum(_part_mark(l) for l in leaves) == 5
   ```

2. **Span Building Tests**
   ```python
   def test_build_spans_simple_question():
       """Test span building for question with (a), (b) parts."""
       bundle = create_mock_bundle(letters=["a", "b"], romans=[])
       spans = slicer._build_spans(bundle)
       assert len(spans) == 3  # root, (a), (b)
       assert spans[("1",)].kind == "question"
       assert spans[("1", "a")].kind == "letter"
   ```

3. **Bounds Calculation Tests**
   ```python
   def test_letter_bounds_non_overlapping():
       """Verify letter slices don't overlap."""
       spans = build_test_spans()
       for i, letter in enumerate(letters[:-1]):
           next_letter = letters[i + 1]
           assert letter.bottom <= next_letter.top
   ```

4. **Selection Invariant Tests**
   ```python
   def test_selection_marks_match_leaves():
       """Verify selection marks equal sum of kept leaf marks."""
       result = select_questions(questions, config)
       for item in result.items:
           leaf_sum = sum(_part_mark(l) for l in item.option.kept_leaves)
           assert item.marks == leaf_sum
   ```

### Characterization Tests

For functions marked ⚠️ MODIFY, write characterization tests first:

```python
def test_question_from_payload_current_behavior():
    """
    Characterization test capturing current parsing behavior.
    
    Verified: 2025-12-12
    Source: loader.py:86-173
    """
    payload = {
        "filename": "s21_qp_12_q1.png",
        "relative_path": "01. Topic/s21_qp_12_q1/1/file.png",
        "main_topic": "01. Topic",
        "parts": [{"label": "1", "marks": 5}],
        "_schema_version": 6,
    }
    config = BuilderConfig(...)
    result = _question_from_payload(payload, Path(), Path(), config)
    
    # Capture current behavior
    assert result.question_id == "s21_qp_12_q1"
    assert result.main_topic == "01. Topic"
```

---

## Test Fixtures Needed

### Mock Data Structures

```python
# tests/fixtures/mock_data.py

def create_mock_bundle(
    qnum: int = 1,
    letters: List[str] = None,
    romans: Dict[str, List[str]] = None,
    marks: Dict[str, int] = None,
) -> QuestionBundle:
    """Create a mock QuestionBundle for testing."""
    ...

def create_mock_question_record(
    question_id: str = "test_q1",
    topic: str = "01. Test Topic",
    marks: int = 10,
    parts: List[Dict] = None,
) -> QuestionRecord:
    """Create a mock QuestionRecord for testing."""
    ...
```

### Sample Files

```
tests/fixtures/
├── sample_pages/
│   ├── simple_question.png      # Single question, 2 parts
│   ├── nested_question.png      # Question with roman numerals
│   ├── multi_page_question.png  # Question spanning pages
│   └── footer_examples.png      # Various footer styles
├── sample_metadata/
│   ├── valid_v6.jsonl           # Valid schema v6 metadata
│   ├── missing_fields.jsonl     # Missing required fields
│   └── old_schema.jsonl         # Schema v5 (should fail)
└── sample_pdfs/
    ├── 0478_s21_qp_12.pdf       # Real exam paper (redacted)
    └── mock_exam.pdf            # Generated mock for tests
```

---

## V2 Test Structure

```
tests/
├── v2/
│   ├── core/
│   │   ├── test_marks.py
│   │   ├── test_bounds.py
│   │   └── test_parts.py
│   ├── extractor_v2/
│   │   ├── test_detection/
│   │   │   ├── test_numerals.py
│   │   │   ├── test_parts.py
│   │   │   └── test_marks.py
│   │   ├── test_slicing/
│   │   │   ├── test_compositor.py
│   │   │   ├── test_bounds.py
│   │   │   └── test_writer.py
│   │   └── test_pipeline.py
│   └── builder_v2/
│       ├── test_loading/
│       │   ├── test_loader.py
│       │   ├── test_parser.py
│       │   └── test_validator.py
│       ├── test_selection/
│       │   ├── test_selector.py
│       │   ├── test_options.py
│       │   └── test_pruning.py
│       └── test_layout/
│           ├── test_composer.py
│           └── test_paginator.py
├── integration/
│   └── test_v2_pipeline.py
└── fixtures/
    ├── sample_pages/
    └── sample_questions/
```

---

## Coverage Requirements for V2

| Module | Minimum Coverage |
|--------|-----------------|
| `core/models` | 95% |
| `extractor_v2/detection` | 90% |
| `extractor_v2/slicing` | 90% |
| `builder_v2/selection` | 95% |
| `builder_v2/layout` | 85% |
| Other modules | 85% |

---

## Next Steps

1. **Run existing tests** to establish baseline
2. **Identify failing tests** (if any)
3. **Write characterization tests** for functions marked MODIFY
4. **Create mock fixtures** for testing
5. **Add invariant assertions** to selection module
