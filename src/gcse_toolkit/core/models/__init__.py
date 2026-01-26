"""
Core Models Package (V2)

Immutable, validated data models that serve as the single source of truth.

**DESIGN RATIONALE:**

All models in this package are frozen dataclasses. This ensures:
1. No accidental mutation during pipeline processing
2. Safe to pass between threads/processes
3. Can be used as dict keys or in sets
4. Easier to reason about data flow

**KEY DIFFERENCES FROM V1 TYPES:**

| V1 Type | V2 Type | Key Changes |
|---------|---------|-------------|
| `marks: Optional[int]` | `Marks` | Always has value, tracks source |
| `SpanNode` | `Part` + `SliceBounds` | Separated concerns |
| `QuestionRecord` | `Question` | Calculated marks, immutable |
| `PlanOption` | `SelectionPlan` | Clearer invariants |
"""

from .marks import Marks
from .bounds import SliceBounds
from .parts import Part
from .questions import Question

__all__ = [
    "Marks",
    "SliceBounds",
    "Part", 
    "Question",
]
