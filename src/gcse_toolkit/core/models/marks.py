"""
Module: marks

Purpose:
    Provides the Marks dataclass - the validated, single source of truth
    for mark values in V2. Replaces scattered `marks: Optional[int]` fields
    from V1 with a unified class that tracks both value and source.

Key Functions:
    - Marks.explicit(value): Create marks from explicit detection
    - Marks.aggregate(parts): Calculate marks from child parts
    - Marks.inferred(value): Create marks from inference
    - Marks.zero(): Create zero marks

Dependencies:
    - dataclasses (std)
    - typing (std)
    - .parts.Part (TYPE_CHECKING only)

Used By:
    - core.models.parts.Part
    - core.models.questions.Question
    - core.models.selection.SelectionPlan
    - extractor_v2 (future)
    - builder_v2 (future)

Design Deviation from V1:
    V1 had `marks: Optional[int]` scattered across PartNode, QuestionRecord,
    and metadata. V2 uses this single Marks class with validation.
    See: docs/architecture/bugs.md (B1, B2)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Sequence

if TYPE_CHECKING:
    from .parts import Part


MarkSource = Literal["explicit", "aggregate", "inferred"]


@dataclass(frozen=True, slots=True)
class Marks:
    """
    Validated mark information - single source of truth.
    
    This is the ONLY way marks should be represented in V2.
    Never store total_marks separately - always calculate from parts.
    
    Attributes:
        value: Non-negative integer mark value
        source: How this mark was determined
            - "explicit": Directly from mark box in PDF
            - "aggregate": Sum of child parts
            - "inferred": Estimated from context (rare)
    
    Invariants:
        - value >= 0
        - source is one of the valid literals
    
    Example:
        >>> m = Marks.explicit(5)
        >>> m.value
        5
        >>> m.source
        'explicit'
    """
    
    value: int
    source: MarkSource
    
    def __post_init__(self) -> None:
        """Validate marks on construction."""
        if self.value < 0:
            raise ValueError(f"Marks cannot be negative: {self.value}")
        if self.source not in ("explicit", "aggregate", "inferred"):
            raise ValueError(f"Invalid mark source: {self.source}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Factory Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    @classmethod
    def explicit(cls, value: int) -> Marks:
        """
        Create marks from explicit mark box detection.
        
        Use when marks are read directly from "[N]" notation in PDF.
        
        Args:
            value: The mark value detected
            
        Returns:
            Marks with source="explicit"
        """
        return cls(value=value, source="explicit")
    
    @classmethod
    def aggregate(cls, parts: Sequence[Part]) -> Marks:
        """
        Calculate aggregate marks from child parts.
        
        Use for parent nodes where marks = sum of children.
        
        Args:
            parts: Child parts to sum marks from
            
        Returns:
            Marks with source="aggregate" and value = sum of child marks
        """
        total = sum(p.marks.value for p in parts)
        return cls(value=total, source="aggregate")
    
    @classmethod
    def inferred(cls, value: int) -> Marks:
        """
        Create marks from inference (not directly detected).
        
        Use only when marks must be estimated from context.
        This should be rare in V2.
        
        Args:
            value: The inferred mark value
            
        Returns:
            Marks with source="inferred"
        """
        return cls(value=value, source="inferred")
    
    @classmethod
    def zero(cls) -> Marks:
        """
        Zero marks (for parts with no marks).
        
        Returns:
            Marks with value=0 and source="inferred"
        """
        return cls(value=0, source="inferred")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Operators
    # ─────────────────────────────────────────────────────────────────────────
    
    def __add__(self, other: Marks) -> Marks:
        """
        Add two mark values.
        
        Result is always marked as "aggregate" since it's a calculation.
        
        Args:
            other: Another Marks instance to add
            
        Returns:
            New Marks with combined value
        """
        if not isinstance(other, Marks):
            return NotImplemented
        return Marks(
            value=self.value + other.value,
            source="aggregate"
        )
    
    def __repr__(self) -> str:
        """Concise representation for debugging."""
        return f"Marks({self.value}, {self.source!r})"
