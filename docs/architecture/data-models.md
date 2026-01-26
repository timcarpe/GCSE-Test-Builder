# Data Models

Core data structures used throughout GCSE Test Builder V2.

## Overview

All V2 data models are:
- **Immutable** - Implemented as frozen dataclasses (often with `slots=True`)
- **Type-Safe** - Full type hints
- **Validated** - Validation in `__post_init__`
- **Well-Documented** - Complete docstrings

## Core Models

### Part

**Module**: [`core/models/parts.py`](../../src/gcse_toolkit/core/models/parts.py)  
**Tests**: [`tests/v2/core/models/test_parts.py`](../../tests/v2/core/models/test_parts.py)

Represents a question part in the hierarchy (the question node, a letter, or a roman numeral).

```python
@dataclass(frozen=True, slots=True)
class Part:
    """Immutable question part in hierarchy."""
    
    label: str                          # e.g., "1(a)(i)"
    kind: PartKind                      # QUESTION, LETTER, or ROMAN
    marks: Marks                        # Mark information (always present)
    bounds: SliceBounds                 # Pixel coordinates for content
    context_bounds: Optional[SliceBounds] = None   # Bounds for context/header
    label_bbox: Optional[SliceBounds] = None       # Bounding box of the label itself
    children: tuple[Part, ...] = ()     # Child parts (immutable tuple)
    topic: Optional[str] = None         # Optional topic override
    sub_topics: tuple[str, ...] = ()    # Optional sub-topics
    is_valid: bool = True               # Validation flag
    validation_issues: tuple[str, ...] = () # Reasons for invalidity
    
    @property
    def total_marks(self) -> int:
        """ALWAYS calculated from leaves, never stored."""
        if self.is_leaf:
            return self.marks.value
        return sum(child.total_marks for child in self.children)
    
    @property
    def is_leaf(self) -> bool:
        """True if this part has no children."""
        return len(self.children) == 0
    
    def iter_leaves(self) -> Iterator[Part]:
        """Iterate all leaf descendants."""
        if self.is_leaf:
            yield self
        else:
            for child in self.children:
                yield from child.iter_leaves()
```

### Marks

**Module**: [`core/models/marks.py`](../../src/gcse_toolkit/core/models/marks.py)  
**Tests**: [`tests/v2/core/models/test_marks.py`](../../tests/v2/core/models/test_marks.py)

Validated mark information with source tracking.

```python
@dataclass(frozen=True, slots=True)
class Marks:
    """Validated mark value with source."""
    
    value: int                    # Mark value (must be >= 0)
    source: MarkSource            # "explicit", "aggregate", or "inferred"
    
    def __post_init__(self):
        """Validate mark value."""
        if self.value < 0:
            raise ValueError(f"Marks cannot be negative: {self.value}")
```

### SliceBounds

**Module**: [`core/models/bounds.py`](../../src/gcse_toolkit/core/models/bounds.py)  
**Tests**: [`tests/v2/core/models/test_bounds.py`](../../tests/v2/core/models/test_bounds.py)

Bounding box for image cropping.

```python
@dataclass(frozen=True, slots=True)
class SliceBounds:
    """Bounding box in pixels (top, bottom, left, right)."""
    
    top: int     # Y-coordinate of top edge (inclusive)
    bottom: int  # Y-coordinate of bottom edge (exclusive)
    left: int = 0    # X-coordinate of left edge
    right: Optional[int] = None   # X-coordinate of right edge (None = full width)
    child_is_inline: bool = False # Whether part is inline with parent
```

### Question

**Module**: [`core/models/questions.py`](../../src/gcse_toolkit/core/models/questions.py)  
**Tests**: [`tests/v2/core/models/test_questions.py`](../../tests/v2/core/models/test_questions.py)

Complete question with metadata and hierarchy.

```python
@dataclass(frozen=True)
class Question:
    """Complete question with metadata."""
    
    id: str                       # e.g., "0478_m24_qp_12_q1"
    exam_code: str                # e.g., "0478"
    year: int                     # e.g., 2024
    paper: int                    # e.g., 1
    variant: int                  # e.g., 2
    topic: str                    # e.g., "01. Data Representation"
    question_node: Part           # Root part of question tree
    composite_path: Path          # Path to composite.png
    regions_path: Path            # Path to regions.json
    mark_scheme_path: Optional[Path] = None
    sub_topics: tuple[str, ...] = ()
```

## Layout Models

### SliceAsset

**Module**: [`builder_v2/layout/models.py`](../../src/gcse_toolkit/builder_v2/layout/models.py)

Renderable image asset for a part.

```python
@dataclass(frozen=True)
class SliceAsset:
    """Image asset ready for pagination."""
    
    question_id: str              # Source question
    part_label: str               # e.g., "1(a)(i)"
    image: Image.Image            # PIL Image
    original_height: int          # Height before any scaling
```

## Selection Models

### SelectionPlan

**Module**: [`core/models/selection.py`](../../src/gcse_toolkit/core/models/selection.py)

Plan for which parts of a question to include.

```python
@dataclass(frozen=True)
class SelectionPlan:
    """Question selection with included parts."""
    
    question: Question
    included_parts: FrozenSet[str] # Labels of parts to include
    
    @cached_property
    def marks(self) -> int:
        """Sum marks of included leaves ONLY."""
        # Implementation avoids double-counting parent marks
```

### SelectionResult

**Module**: [`core/models/selection.py`](../../src/gcse_toolkit/core/models/selection.py)

Complete selection result with statistics.

```python
@dataclass(frozen=True)
class SelectionResult:
    """Question selection result."""
    
    plans: tuple[SelectionPlan, ...] # Selected questions
    target_marks: int
    tolerance: int
```

## See Also

- [Pipeline Documentation](pipelines.md) - How models flow through pipelines
- [Decision Log](decision_log.md) - Why models are structured this way
