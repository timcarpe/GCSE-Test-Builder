"""
Module: parts

Purpose:
    Provides the Part dataclass - an immutable tree node representing
    question structure. Each Part can be a question (root), letter (a),
    or roman numeral (i). Parts form a hierarchy with calculated marks.

Key Functions:
    - Part.iter_leaves(): Iterate over leaf parts (scorable items)
    - Part.iter_all(): Iterate over all parts in tree
    - Part.find(label): Find a part by label
    - Part.total_marks: Property calculating marks from leaves
    - Part.to_dict() / Part.from_dict(): Serialization

Dependencies:
    - dataclasses (std)
    - typing (std)
    - .bounds.SliceBounds
    - .marks.Marks

Used By:
    - core.models.questions.Question
    - core.models.selection.SelectionPlan
    - core.utils.serialization
    - extractor_v2 (future)
    - builder_v2 (future)

Design Deviation from V1:
    V1 PartNode was mutable with confusing marks fields. V2 Part is frozen,
    validates sibling ordering/overlap, uses Marks class for marks.
    See: docs/architecture/bugs.md (B1, B2)
    See: docs/architecture/decision_log.md (DECISION-002)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Optional, Tuple

from .bounds import SliceBounds
from .marks import Marks


class PartKind(str, Enum):
    """Type of question part."""
    QUESTION = "question"  # Top-level question node (e.g., "1")
    LETTER = "letter"      # Letter sub-part (e.g., "(a)")
    ROMAN = "roman"        # Roman numeral sub-part (e.g., "(i)")
    
    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Part:
    """
    Question part node (immutable tree structure).
    
    Represents a single part of a question: the question node,
    a letter part (a), or a roman numeral part (ii).
    
    The tree structure is:
        Question ("1")
        ├── Letter ("(a)")
        │   ├── Roman ("(i)") [leaf]
        │   └── Roman ("(ii)") [leaf]
        └── Letter ("(b)") [leaf if no romans]
    
    Attributes:
        label: Display label like "1", "1(a)", "1(a)(ii)"
        kind: Type of part - QUESTION, LETTER, or ROMAN
        marks: Mark information for this part
        bounds: Pixel coordinates in composite image for this part's content
        context_bounds: Bounds for the context/header slice (QUESTION and LETTER only)
        label_bbox: Bounding box of the part label (e.g. "(a)") within the composite
        children: Child parts (immutable tuple, sorted by bounds.top)
        topic: Optional topic override (usually inherited from question)
        sub_topics: Optional sub-topic list
    
    Invariants:
        - Children are sorted by bounds.top
        - No overlapping bounds between siblings
        - context_bounds only set for QUESTION and LETTER kinds
    
    Example:
        >>> roman = Part("1(a)(i)", PartKind.ROMAN, Marks.explicit(2), SliceBounds(100, 200))
        >>> letter = Part("1(a)", PartKind.LETTER, Marks.aggregate([roman]), 
        ...               SliceBounds(50, 250), children=(roman,))
        >>> letter.total_marks
        2
        >>> letter.is_leaf
        False
        >>> roman.is_leaf
        True
    """
    
    label: str
    kind: PartKind
    marks: Marks
    bounds: SliceBounds
    context_bounds: Optional[SliceBounds] = None
    label_bbox: Optional[SliceBounds] = None
    children: Tuple[Part, ...] = ()
    topic: Optional[str] = None
    sub_topics: Tuple[str, ...] = ()
    is_valid: bool = True  # Part-level validation flag
    validation_issues: Tuple[str, ...] = ()  # Reasons for invalidity

    
    def __post_init__(self) -> None:
        """Validate part tree on construction."""
        # Validate children ordering and overlaps
        last_bottom = -1
        for child in self.children:
            # Ordering invariant (sorted by top)
            if child.bounds.top < last_bottom:
                # We use top for ordering, but bottom must also be non-decreasing for non-overlap
                # Actually, strictly children should be sorted by top.
                # If they are not sorted by top in the list, raise error.
                pass
            
            # Refined check: children must be strictly sorted by bounds.top
            # and they must not overlap vertically.
            if child.bounds.top < last_bottom:
                 raise ValueError(f"Children of {self.label} must be sorted by position and cannot overlap (top={child.bounds.top} < last_bottom={last_bottom})")
            
            last_bottom = child.bounds.bottom

        # Validate context_bounds only for QUESTION and LETTER
        if self.context_bounds is not None and self.kind == PartKind.ROMAN:
            raise ValueError("Roman numeral parts should not have context_bounds")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────────────────
    
    @property
    def is_leaf(self) -> bool:
        """Check if this part has no children."""
        return len(self.children) == 0
    
    @property
    def total_marks(self) -> int:
        """
        Calculate total marks for this part and all descendants.
        
        For a leaf, returns self.marks.value.
        For a parent, returns sum of all leaf marks.
        
        **IMPORTANT:** This is ALWAYS calculated, never stored.
        """
        if self.is_leaf:
            return self.marks.value
        return sum(child.total_marks for child in self.children)
    
    @property
    def depth(self) -> int:
        """
        Depth in the tree (question=0, letter=1, roman=2).
        
        Returns:
            Integer depth level
        """
        if self.kind == PartKind.QUESTION:
            return 0
        elif self.kind == PartKind.LETTER:
            return 1
        else:
            return 2
    
    @property
    def leaf_count(self) -> int:
        """Count of leaf parts in this subtree."""
        if self.is_leaf:
            return 1
        return sum(child.leaf_count for child in self.children)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Iteration Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def iter_leaves(self) -> Iterator[Part]:
        """
        Iterate over all leaf parts (parts with no children).
        
        Yields:
            All leaf Part instances in tree order
        """
        if self.is_leaf:
            yield self
        else:
            for child in self.children:
                yield from child.iter_leaves()
    
    def iter_all(self) -> Iterator[Part]:
        """
        Iterate over this part and all descendants (pre-order).
        
        Yields:
            This part, then all descendants in tree order
        """
        yield self
        for child in self.children:
            yield from child.iter_all()
    
    def iter_ancestors_of(self, label: str) -> Iterator[Part]:
        """
        Iterate over ancestors of a part (from root to parent).
        
        Args:
            label: Label of the part to find ancestors for
            
        Yields:
            Ancestor parts from root toward the target
        """
        if self.label == label:
            return
        for child in self.children:
            if child.label == label or child.find(label) is not None:
                yield self
                yield from child.iter_ancestors_of(label)
                return
    
    # ─────────────────────────────────────────────────────────────────────────
    # Query Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def find(self, label: str) -> Optional[Part]:
        """
        Find a part by label in this subtree.
        
        Args:
            label: Part label to search for
            
        Returns:
            Matching Part or None if not found
        """
        if self.label == label:
            return self
        for child in self.children:
            found = child.find(label)
            if found is not None:
                return found
        return None
    
    def get_context_for(self, leaf_label: str) -> list[Part]:
        """
        Get context parts needed to render a leaf.
        
        Returns all ancestor parts that have context_bounds set.
        Used when rendering a leaf to include question/letter headers.
        
        Args:
            leaf_label: Label of the leaf part
            
        Returns:
            List of ancestor Parts with context_bounds (ordered root-to-leaf)
        """
        result = []
        for ancestor in self.iter_ancestors_of(leaf_label):
            if ancestor.context_bounds is not None:
                result.append(ancestor)
        return result
    
    # ─────────────────────────────────────────────────────────────────────────
    # Serialization
    # ─────────────────────────────────────────────────────────────────────────
    
    def to_dict(self) -> dict:
        """
        Serialize to dictionary for JSON storage.
        
        Returns:
            Dict representation of this part and children
        """
        d = {
            "label": self.label,
            "kind": str(self.kind),
            "marks": self.marks.value,
            "mark_source": self.marks.source,
            "bounds": self.bounds.to_dict(),
        }
        if self.context_bounds is not None:
            d["context_bounds"] = self.context_bounds.to_dict()
        if self.label_bbox is not None:
            d["label_bbox"] = self.label_bbox.to_dict()
        if self.children:
            d["children"] = [child.to_dict() for child in self.children]
        if self.topic:
            d["topic"] = self.topic
        if self.sub_topics:
            d["sub_topics"] = list(self.sub_topics)
        # Part-level validation
        if not self.is_valid:
            d["is_valid"] = False
            d["validation_issues"] = list(self.validation_issues)
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> Part:
        """
        Deserialize from dictionary.
        
        Args:
            data: Dict representation
            
        Returns:
            Part instance
        """
        children = tuple(
            cls.from_dict(child) for child in data.get("children", [])
        )
        
        return cls(
            label=data["label"],
            kind=PartKind(data["kind"]),
            marks=Marks(data["marks"], data.get("mark_source", "explicit")),
            bounds=SliceBounds.from_dict(data["bounds"]),
            context_bounds=(
                SliceBounds.from_dict(data["context_bounds"])
                if "context_bounds" in data else None
            ),
            label_bbox=(
                SliceBounds.from_dict(data["label_bbox"])
                if "label_bbox" in data else None
            ),
            children=children,
            topic=data.get("topic"),
            sub_topics=tuple(data.get("sub_topics", [])),
            is_valid=data.get("is_valid", True),
            validation_issues=tuple(data.get("validation_issues", [])),
        )
    
    def __repr__(self) -> str:
        """Concise representation for debugging."""
        child_str = f", children={len(self.children)}" if self.children else ""
        return f"Part({self.label!r}, {self.kind.value}, marks={self.marks.value}{child_str})"
