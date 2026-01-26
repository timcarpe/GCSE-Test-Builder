# V2 Design Deviations from V1

> **Document Type:** DESIGN DECISION LOG  
> **Purpose:** Tracks all intentional deviations from V1 architecture  
> **Status:** Living document, updated as V2 develops

---

## Overview

This document provides a comprehensive mapping of V1 -> V2 changes. Each deviation is documented with:
- **What changed** - The specific difference
- **Why** - Root cause or problem being solved
- **Bug References** - Links to bugs.md if applicable
- **Location** - Where the new code lives

---

## Naming Convention Changes

| V1 Term | V2 Term | Reason |
|---------|---------|--------|
| `root` (PartNode tree) | `question_node` | "root" was ambiguous - could mean tree root or image header |
| `root` (image slice) | `context_bounds` | Clear that this is the context/header bounds |
| `_root.png` | `_context.png` | Consistent naming in file system |
| `header` | `question_context` | More descriptive |
| `letter root` | `letter_context` | Consistent with question_context |
| `marks: Optional[int]` | `marks: Marks` | Always present, typed, validated |
| `SpanNode` | `Part` + `SliceBounds` | Separated concerns |

---

## Data Model Changes

### Marks Representation

| Aspect | V1 (`marks: Optional[int]`) | V2 (`Marks` class) |
|--------|------------------------------|---------------------|
| Type | `Optional[int]` scattered across types | Single `Marks` dataclass |
| Validation | None, could be negative | `__post_init__` validates >= 0 |
| Source tracking | `mark_source: str` separate field | `source: Literal[...]` in same class |
| Total calculation | Stored in `total_marks` field | **NEVER stored**, always calculated |
| Factory methods | None | `Marks.explicit()`, `Marks.aggregate()` |

**Bug Fixed:** B1, B2 (mark inconsistencies)

**Location:** `src/gcse_toolkit/core/models/marks.py`

---

### Bounds Representation

| Aspect | V1 (`SpanNode.top/bottom`) | V2 (`SliceBounds` class) |
|--------|----------------------------|--------------------------|
| Type | Individual fields on SpanNode | Dedicated dataclass |
| Validation | None | `__post_init__` validates ranges |
| Overlap detection | Manual comparison | `bounds.overlaps(other)` method |
| Image cropping | Calculated in multiple places | `bounds.crop_from(image)` method |
| Serialization | Mixed with SpanNode | `to_dict()` / `from_dict()` |

**Bug Fixed:** B4, B5 (slice overlap, header cutoff)

**Location:** `src/gcse_toolkit/core/models/bounds.py`

---

### Part Tree Representation

| Aspect | V1 (`PartNode`) | V2 (`Part`) |
|--------|-----------------|-------------|
| Mutability | Mutable list children | Frozen, tuple children |
| Children type | `List[PartNode]` | `Tuple[Part, ...]` |
| Validation | None | Sorted order, no overlaps |
| Context bounds | Not stored | `context_bounds: Optional[SliceBounds]` |
| Total marks | Accessed via aggregate_marks field | `total_marks` property, always calculated |
| Kind type | `str` | `PartKind` enum |

**Location:** `src/gcse_toolkit/core/models/parts.py`

---

### Question Representation

| Aspect | V1 (`QuestionRecord`) | V2 (`Question`) |
|--------|----------------------|-----------------|
| Mutability | Mutable | Frozen |
| Top-level part | `root: PartNode` | `question_node: Part` |
| Total marks | `total_marks: Optional[int]` stored | `@cached_property`, always calculated |
| Image path | `question_image: Path` | `composite_path`, `regions_path` |
| Exam code | Optional, multiple fallbacks | Required, single source |
| Validation | None | `__post_init__` validates format |

**Bug Fixed:** B1 (mark totals), B12 (exam code fallbacks)

**Location:** `src/gcse_toolkit/core/models/questions.py`

---

### Selection Representation

| Aspect | V1 (`PlanOption`) | V2 (`SelectionPlan`) |
|--------|-------------------|----------------------|
| Mutability | Mutable | Frozen |
| Included parts | `kept_leaves`, `removed_leaves` tuples | `included_parts: FrozenSet[str]` |
| Marks | `marks: int` stored | `@cached_property`, always calculated |
| Question reference | `question: QuestionRecord` | `question: Question` |
| Validation | None | Part labels validated on construction |

**Bug Fixed:** B2 (selection marks don't match PDF)

**Location:** `src/gcse_toolkit/core/models/selection.py`

---

## Storage Format Changes

### V1 Format (Legacy + Atlas)

```
slices_cache/{exam_code}/{topic}/{question_id}/
├── {qnum}/
│   ├── {prefix}_{qnum}.png           # Question root slice
│   ├── {letter}/
│   │   ├── {prefix}_{qnum}_{letter}_root.png  # Letter root
│   │   └── {roman}/
│   │       └── {prefix}_{qnum}_{letter}_{roman}.png  # Roman leaf
│   └── ...
└── questions.jsonl
```

### V2 Format (Composite Only)

```
slices_cache_v2/{exam_code}/{topic}/{question_id}/
├── composite.png                    # Single image per question
├── regions.json                     # All slice bounds
└── markscheme/                      # Optional mark scheme
    ├── composite.png
    └── regions.json
```

**Benefits:**
- Fewer files (1 vs potentially 20+)
- Less disk I/O during extraction
- Slices cropped on-demand using ImageProvider
- Bounds pre-calculated, validated at extraction time

**Location:** V2 extractor (Phase 3), V2 builder/ImageProvider (Phase 4)

---

## Invariants Enforced in V2

### Mark Invariant

```python
# V2 enforces: total_marks == sum of leaf marks
assert question.total_marks == sum(
    leaf.marks.value for leaf in question.question_node.iter_leaves()
)
```

### Sibling Non-Overlap Invariant

```python
# V2 enforces: siblings never overlap
for i in range(len(part.children) - 1):
    assert not part.children[i].bounds.overlaps(part.children[i+1].bounds)
```

### Selection Marks Invariant

```python
# V2 enforces: selection marks == sum of included leaf marks
assert result.total_marks == sum(plan.marks for plan in result.plans)
```

---

## Test Coverage Requirements

| Model | V1 Coverage | V2 Coverage Target | Current V2 |
|-------|-------------|-------------------|------------|
| Marks | 0% | 100% | 100% (11 tests) |
| SliceBounds | 0% | 100% | 100% (16 tests) |
| Part | ~10% | 95% | 95% (14 tests) |
| Question | ~20% | 95% | 100% (5 tests) |
| Selection | ~30% | 95% | 100% (7 tests) |

---

## Migration Path

The V2 models are designed to coexist with V1 during migration:

1. **Phase 2 (Current):** V2 models implemented, tested independently
2. **Phase 3:** V2 extractor produces V2 format (parallel directory)
3. **Phase 4:** V2 builder consumes V2 format
4. **Phase 7:** Integration tests verify V1 -> V2 migration
5. **Phase 8:** V1 code deprecated, V2 becomes primary

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-12-12 | Remove `slots=True` from classes with `@cached_property` | Python limitation: cached_property requires `__dict__` |
| 2025-12-12 | Use `Tuple[Part, ...]` not `List[Part]` for children | Enforces immutability, compatible with frozen dataclass |
| 2025-12-12 | `context_bounds` only on QUESTION and LETTER kinds | Roman numerals don't need context headers |
| 2025-12-12 | Validation in `__post_init__` | Fail fast, invalid data never exists |
