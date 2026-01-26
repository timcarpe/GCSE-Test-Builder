# Testing Documentation

Complete testing guide with code-to-test mappings and coverage information.

## Test Organization

Tests are organized to mirror the code structure:

```
tests/
├── core/
│   ├── models/
│   │   ├── test_marks.py        → core/models/marks.py
│   │   ├── test_parts.py        → core/models/parts.py
│   │   └── test_bounds.py        → core/models/bounds.py
├── extractor_v2/
│   ├── detection/
│   │   ├── test_numerals.py              → extractor_v2/detection/numerals.py
│   │   ├── test_parts.py                 → extractor_v2/detection/parts.py
│   │   └── test_marks.py                 → extractor_v2/detection/marks.py
│   ├── structuring/
│   │   └── test_tree_builder.py          → extractor_v2/structuring/tree_builder.py
│   ├── slicing/
│   │   └── test_bounds_calculator.py     → extractor_v2/slicing/bounds_calculator.py
│   ├── utils/
│   │   ├── test_pdf.py                   → extractor_v2/utils/pdf.py
│   │   └── test_text.py                  → extractor_v2/utils/text.py
└── builder_v2/
    ├── loading/
    │   └── test_loader.py                → builder_v2/loading/loader.py
    ├── selection/
    │   └── test_selector.py              → builder_v2/selection/selector.py
    ├── layout/
    │   ├── test_composer.py              → builder_v2/layout/composer.py
    │   ├── test_paginator.py             → builder_v2/layout/paginator.py
    │   ├── test_config.py                → builder_v2/layout/config.py
    │   └── test_models.py                → builder_v2/layout/models.py
    ├── output/
    │   └── test_renderer.py              → builder_v2/output/renderer.py
    ├── keyword/
    │   └── test_keyword_index.py         → builder_v2/keyword/index.py
    └── test_controller.py                → builder_v2/controller.py
```

## Code-to-Test Mapping

### Core Models

| Module | Tests | Coverage |
|--------|-------|----------|
| [`core/models/marks.py`](../../src/gcse_toolkit/core/models/marks.py) | [`test_marks.py`](../../tests/core/models/test_marks.py) | ✅ High |
| [`core/models/parts.py`](../../src/gcse_toolkit/core/models/parts.py) | [`test_parts.py`](../../tests/core/models/test_parts.py) | ✅ High |
| [`core/models/bounds.py`](../../src/gcse_toolkit/core/models/bounds.py) | [`test_bounds.py`](../../tests/core/models/test_bounds.py) | ✅ High |
| [`core/models/questions.py`](../../src/gcse_toolkit/core/models/questions.py) | [`test_questions.py`](../../tests/core/models/test_questions.py) | ✅ High |

### Extract V2 - Detection

| Module | Tests | Coverage |
|--------|-------|----------|
| [`detection/numerals.py`](../../src/gcse_toolkit/extractor_v2/detection/numerals.py) | [`test_numerals.py`](../../tests/extractor_v2/detection/test_numerals.py) | ✅ High |
| [`detection/parts.py`](../../src/gcse_toolkit/extractor_v2/detection/parts.py) | [`test_parts.py`](../../tests/extractor_v2/detection/test_parts.py) | ✅ High |
| [`detection/marks.py`](../../src/gcse_toolkit/extractor_v2/detection/marks.py) | [`test_marks.py`](../../tests/extractor_v2/detection/test_marks.py) | ⚠️ Medium |

### Extractor V2 - Structuring & Slicing

| Module | Tests | Coverage |
|--------|-------|----------|
| [`structuring/tree_builder.py`](../../src/gcse_toolkit/extractor_v2/structuring/tree_builder.py) | [`test_tree_builder.py`](../../tests/extractor_v2/structuring/test_tree_builder.py) | ✅ High |
| [`slicing/bounds_calculator.py`](../../src/gcse_toolkit/extractor_v2/slicing/bounds_calculator.py) | [`test_bounds_calculator.py`](../../tests/extractor_v2/slicing/test_bounds_calculator.py) | ✅ High |

### Extractor V2 - Utils

| Module | Tests | Coverage |
|--------|-------|----------|
| [`utils/pdf.py`](../../src/gcse_toolkit/extractor_v2/utils/pdf.py) | [`test_pdf.py`](../../tests/extractor_v2/utils/test_pdf.py) | ✅ High |
| [`utils/text.py`](../../src/gcse_toolkit/extractor_v2/utils/text.py) | [`test_text.py`](../../tests/extractor_v2/utils/test_text.py) | ✅ Good |

### Builder V2 - Loading & Selection

| Module | Tests | Coverage |
|--------|-------|----------|
| [`loading/loader.py`](../../src/gcse_toolkit/builder_v2/loading/loader.py) | [`test_loader.py`](../../tests/builder_v2/loading/test_loader.py) | ✅ High |
| [`selection/selector.py`](../../src/gcse_toolkit/builder_v2/selection/selector.py) | [`test_selector.py`](../../tests/builder_v2/selection/test_selector.py) | ✅ High |

### Builder V2 - Layout

| Module | Tests | Coverage |
|--------|-------|----------|
| [`layout/composer.py`](../../src/gcse_toolkit/builder_v2/layout/composer.py) | [`test_composer.py`](../../tests/builder_v2/layout/test_composer.py) | ✅ Good |
| [`layout/paginator.py`](../../src/gcse_toolkit/builder_v2/layout/paginator.py) | [`test_paginator.py`](../../tests/builder_v2/layout/test_paginator.py) | ✅ Good |
| [`layout/config.py`](../../src/gcse_toolkit/builder_v2/layout/config.py) | [`test_config.py`](../../tests/builder_v2/layout/test_config.py) | ✅ High |
| [`layout/models.py`](../../src/gcse_toolkit/builder_v2/layout/models.py) | [`test_models.py`](../../tests/builder_v2/layout/test_models.py) | ✅ High |

### Builder V2 - Output & Keyword

| Module | Tests | Coverage |
|--------|-------|----------|
| [`output/renderer.py`](../../src/gcse_toolkit/builder_v2/output/renderer.py) | [`test_renderer.py`](../../tests/builder_v2/output/test_renderer.py) | ⚠️ Medium |
| [`keyword/index.py`](../../src/gcse_toolkit/builder_v2/keyword/index.py) | [`test_keyword_index.py`](../../tests/builder_v2/keyword/test_keyword_index.py) | ✅ Good |
| [`controller.py`](../../src/gcse_toolkit/builder_v2/controller.py) | [`test_controller.py`](../../tests/builder_v2/test_controller.py) | ✅ Good |

## Integration Tests

| Test File | Coverage |
|-----------|----------|
| [`tests/integration/test_extraction_pipeline.py`](../../tests/integration/test_extraction_pipeline.py) | Full extraction flow |
| [`tests/integration/test_build_pipeline.py`](../../tests/integration/test_build_pipeline.py) | Full building flow |

## Running Tests

### Run All Tests
```bash
python -m pytest tests -v
```

### Run Specific Module Tests
```bash
# Test builder tests only
python -m pytest tests/builder_v2 -v

# Core model tests
python -m pytest tests/core -v
```

## Fixture Organization

Shared test fixtures are in [`tests/fixtures/`](../../tests/fixtures/):

- `sample_pages/` - PDF page images for detection tests
- `sample_questions/` - Complete question data for integration tests
- `conftest.py` - Pytest fixtures and configuration

## Coverage Goals

| Component | Target | Current |
|-----------|--------|---------|
| Core Models | 100% | ✅ 95%+ |
| Extractor V2 | 90%+ | ✅ 88% |
| Builder V2 | 90%+ | ✅ 85% |
| Integration | Key flows | ✅ Covered |
