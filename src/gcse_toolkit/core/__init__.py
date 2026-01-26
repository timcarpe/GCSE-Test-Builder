"""
GCSE Test Builder Core Package (V2)

This package contains the shared data models and utilities for the V2 refactor.
These models are designed to be the single source of truth for all V2 modules.

**DESIGN DEVIATIONS FROM V1:**

1. **Immutable Data Models**
   - V1: Mutable dataclasses, values changed throughout pipeline
   - V2: Frozen dataclasses, new instances created for any changes

2. **Calculated Marks (Never Stored)**
   - V1: `total_marks` stored in metadata, often wrong
   - V2: `total_marks` always calculated from leaf parts

3. **Unified Storage Format**
   - V1: Both legacy slices AND atlas composite images
   - V2: Composite images ONLY, slices cropped on demand

4. **Consistent Naming**
   - V1: Confusing "root" terminology (meant different things)
   - V2: Clear "question_node", "context_bounds", etc.

See `docs/architecture/verification.md` for the full naming convention table.
"""

from .models import Marks, SliceBounds, Part, Question
from .models.selection import SelectionPlan, SelectionResult

__all__ = [
    "Marks",
    "SliceBounds", 
    "Part",
    "Question",
    "SelectionPlan",
    "SelectionResult",
]
