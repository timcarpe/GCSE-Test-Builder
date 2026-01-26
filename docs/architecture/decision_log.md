# Decision Log

Key architectural decisions made during V2 refactoring.

## Page Dimensions Fix (2024-12-14)

**Decision**: Corrected page dimensions to 1654×2339px (A4 at 200 DPI)

**Context**: 
- BuilderConfig had incorrect dimensions: 1240×1754px
- Caused excessive page breaks and wasted whitespace
- Pages were only 70% of correct height

**Impact**:
- test3_high_marks: 6 pages → 5 pages
- test2_medium_marks: 4 pages → 3 pages
- Better page utilization across all outputs

**Files Modified**:
- `builder_v2/config.py` - Updated default dimensions

---

## Bounds vs. Padding Separation (2024-12-14)

**Decision**: Separate detection bounds from layout padding

**Context**:
- Previously, `+10px` padding was added during bounds calculation
- This mixed detection logic with presentation logic
- Detection should store REAL bounds only

**Implementation**:
- Detection layer: Store exact bbox.bottom from mark boxes
- Layout layer: Add `MARK_BOX_CLEARANCE_PX = 10` when cropping
- `crop_slice(..., add_mark_clearance=True)` for parts with marks

**Benefits**:
- Clean separation of concerns
- Easier to verify bounds accuracy
- Padding can be adjusted without re-extraction

**Files Modified**:
- `extractor_v2/slicing/bounds_calculator.py` - Removed padding
- `builder_v2/images/cropper.py` - Added conditional padding
- `builder_v2/images/provider.py` - Pass padding flag
- `builder_v2/layout/composer.py` - Apply padding for marked parts

---

## Lock-Free Pagination (2024-12-14)

**Decision**: Remove `lock_with_next` mechanism, use simple space calculations

**Context**:
- Previous pagination used complex `lock_with_next` attribute
- Created rigid blocks that couldn't be split
- Hard to understand and debug

**New Approach**:
- Check if asset fits on current page
- Only special case: context stays with first child
- Everything else places based on available space

**Benefits**:
- Simpler logic (269 lines → 189 lines)
- More predictable behavior
- Easier to debug spacing issues

**Files Modified**:
- `builder_v2/layout/models.py` - Removed `lock_with_next` attribute
- `builder_v2/layout/paginator.py` - Complete rewrite
- `builder_v2/layout/composer.py` - Removed lock assignment

---

## Mark Calculation Always from Leaves (2024-12)

**Decision**: `total_marks` is ALWAYS `@cached_property`, never stored

**Context**:
- V1 had `total_marks` stored in multiple places
- Inconsistencies between stored and calculated values
- No single source of truth

**Implementation**:
```python
@cached_property
def total_marks(self) -> int:
    return sum(leaf.marks.value for leaf in self.iter_leaves())
```

**Benefits**:
- Single source of truth for marks
- Always accurate
- Validates against stored aggregates

**Files Modified**:
- `core/models/part.py` - Added cached_property
- `core/models/question.py` - Delegates to part tree

---

## Overlap Detection for Context Slices (2024-12-14)

**Decision**: Skip leaf rendering when overlapping with parent context

**Context**:
- Q8 root and Q8(a) often have identical bounds
- Would render same content twice
- Need to detect and skip

**Implementation**:
```python
if context_parts:
    parent = context_parts[-1]
    if parent.bounds and leaf.bounds.top == parent.bounds.top:
        skip_leaf = True  # Context already covers this
```

**Files Modified**:
- `builder_v2/layout/composer.py` - Added overlap detection

---

## Magic Number Elimination (2024-12-14)

**Decision**: All magic numbers must be named constants

**Context**:
- Code had literals like `10`, `98`, `1` scattered throughout
- Hard to understand purpose
- Difficult to maintain

**Constants Added**:
```python
MARK_BOX_CLEARANCE_PX = 10    # Padding below marks
TRIM_PERCENTILE = 98          # Whitespace detection
MIN_TEXT_HEIGHT = 1           # Minimum text span
MIN_REGION_HEIGHT = 1         # Minimum region
MIN_PART_HEIGHT = 1           # Minimum part height
MIN_ROOT_HEIGHT = 20          # Root when first letter at y=0
```

**Files Modified**:
- `extractor_v2/slicing/bounds_calculator.py`
- `extractor_v2/utils/text.py`
- `extractor_v2/utils/pdf.py`
- `extractor_v2/structuring/tree_builder.py`
- `builder_v2/images/cropper.py`

---

## Immutable Data Models (2024-12)

**Decision**: All core models use `@dataclass(frozen=True)`

**Benefits**:
- Thread-safe
- Predictable behavior
- Easier to test
- Forces proper use of `dataclasses.replace()`

**Models**:
- `Part`
- `Marks`
- `SliceBounds`
- `Question`
- `SelectionPlan`
- `LayoutConfig`
- All layout models

---

## Type Hints Everywhere (2024-12)

**Decision**: 100% type hint coverage for V2

**Benefits**:
- Better IDE support
- Catch bugs before runtime
- Self-documenting code
- Enables mypy checking

**Standard**:
```python
def function_name(
    arg1: Type1,
    arg2: Type2,
    *,
    optional: Type3 = default
) -> ReturnType:
    """Docstring."""
```

---

## See Also

- [Architecture Overview](overview.md) - System design
- [Pipeline Documentation](pipelines.md) - Implementation details
