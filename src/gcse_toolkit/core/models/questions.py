"""
Module: questions

Purpose:
    Provides the Question dataclass - the main data structure passed between
    extractor and builder. Represents a complete question with metadata,
    part tree, and image paths. Immutable with calculated marks.

Key Functions:
    - Question.total_marks: Cached property, always calculated from parts
    - Question.leaf_parts: Get all leaf parts
    - Question.get_part(label): Find a part by label
    - Question.to_dict() / Question.from_dict(): Serialization

Dependencies:
    - dataclasses (std)
    - functools (std)
    - pathlib (std)
    - .parts.Part

Used By:
    - core.models.selection.SelectionPlan
    - core.utils.serialization
    - extractor_v2 (future)
    - builder_v2 (future)

Design Deviation from V1:
    V1 QuestionRecord was mutable with stored total_marks (often wrong).
    V2 Question is frozen, calculates total_marks from leaves, uses
    question_node instead of root.
    See: docs/architecture/bugs.md (B1, B6, B12)
    See: docs/architecture/decision_log.md (DECISION-002, DECISION-004)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Dict, Optional

from .parts import Part


@dataclass(frozen=True)
class Question:
    """
    Complete question representation (immutable).
    
    This is the main data structure passed between extractor and builder.
    Contains all information needed to render a question.
    
    Attributes:
        id: Unique identifier like "s21_qp_12_q1"
        exam_code: Exam code like "0478" (always required)
        year: Exam year like 2021
        paper: Paper number like 1 or 2
        variant: Variant number like 1, 2, 3
        topic: Main topic classification
        question_node: Root part node containing full tree (NOT called "root")
        composite_path: Path to composite image (single image per question)
        regions_path: Path to regions.json with all slice bounds
        mark_scheme_path: Optional path to mark scheme image
        sub_topics: Additional topic classifications
    
    Invariants:
        - total_marks is always calculated from question_node
        - composite_path exists (not validated here, checked at load time)
    
    Example:
        >>> q = Question(
        ...     id="s21_qp_12_q1",
        ...     exam_code="0478",
        ...     year=2021,
        ...     paper=1,
        ...     variant=2,
        ...     topic="01. Data Representation",
        ...     question_node=some_part_tree,
        ...     composite_path=Path("/cache/0478/..."),
        ...     regions_path=Path("/cache/0478/.../regions.json"),
        ... )
        >>> q.total_marks  # Always calculated
        9
    """
    
    id: str
    exam_code: str
    year: int
    paper: int
    variant: int
    topic: str
    question_node: Part  # NOT called "root" - see naming conventions
    composite_path: Path
    regions_path: Path
    mark_scheme_path: Optional[Path] = None
    sub_topics: tuple[str, ...] = ()
    content_right: Optional[int] = None  # Rightmost content x-coordinate (from mark boxes)
    numeral_bbox: Optional[tuple[int, int, int, int]] = None  # Question number bbox in pixels
    root_text: str = ""  # Keyword search: question header text
    child_text: Dict[str, str] = field(default_factory=dict)  # Keyword search: part labels -> text
    mark_bboxes: tuple[tuple[int, int, int, int], ...] = ()  # Mark box positions for UI highlighting
    horizontal_offset: int = 0  # Phase 6.10: Offset from reference for render-time alignment
    
    def __post_init__(self) -> None:
        """Validate question on construction."""
        # Validate exam_code format (4 digits)
        if not self.exam_code or len(self.exam_code) != 4:
            raise ValueError(f"exam_code must be 4 characters: {self.exam_code!r}")
        if not self.exam_code.isdigit():
            raise ValueError(f"exam_code must be digits: {self.exam_code!r}")
        
        # Validate year range
        if not (2000 <= self.year <= 2100):
            raise ValueError(f"year must be 2000-2100: {self.year}")
        
        # Validate paper/variant
        if not (1 <= self.paper <= 9):
            raise ValueError(f"paper must be 1-9: {self.paper}")
        if not (1 <= self.variant <= 9):
            raise ValueError(f"variant must be 1-9: {self.variant}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Calculated Properties (NEVER stored)
    # ─────────────────────────────────────────────────────────────────────────
    
    @cached_property
    def total_marks(self) -> int:
        """
        Calculate total marks from parts.
        
        **IMPORTANT:** This is ALWAYS calculated, NEVER stored.
        This ensures marks are always consistent with the part tree.
        
        Returns:
            Sum of all leaf part marks
        """
        return self.question_node.total_marks
    
    @cached_property
    def all_parts(self) -> list[Part]:
        """
        Get flat list of all parts in tree order.
        
        Returns:
            List including question_node and all descendants
        """
        return list(self.question_node.iter_all())
    
    @cached_property
    def leaf_parts(self) -> list[Part]:
        """
        Get list of leaf parts only.
        
        Returns:
            List of parts with no children (the actual sub-questions)
        """
        return list(self.question_node.iter_leaves())
    
    @cached_property
    def leaf_count(self) -> int:
        """
        Count of leaf parts.
        
        Returns:
            Number of selectable sub-parts
        """
        return self.question_node.leaf_count
    
    # ─────────────────────────────────────────────────────────────────────────
    # Query Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_part(self, label: str) -> Optional[Part]:
        """
        Find a part by label.
        
        Args:
            label: Part label like "1(a)(ii)"
            
        Returns:
            Matching Part or None
        """
        return self.question_node.find(label)
    
    def get_bounds(self, label: str) -> Optional[Part]:
        """
        Get bounds for a specific part.
        
        Args:
            label: Part label to find
            
        Returns:
            SliceBounds for the part, or None if not found
        """
        part = self.get_part(label)
        return part.bounds if part else None
    
    def get_context_parts(self, leaf_label: str) -> list[Part]:
        """
        Get context parts needed to render a leaf.
        
        When rendering a leaf like "1(a)(ii)", we may need to include
        the question header ("1") and letter context ("(a)...") first.
        
        Args:
            leaf_label: Label of the leaf to render
            
        Returns:
            List of ancestor Parts with context_bounds
        """
        return self.question_node.get_context_for(leaf_label)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Serialization
    # ─────────────────────────────────────────────────────────────────────────
    
    def to_dict(self) -> dict:
        """
        Serialize to dictionary for JSON storage.
        
        Note: Paths are converted to strings, total_marks NOT stored.
        
        Returns:
            Dict representation
        """
        d = {
            "id": self.id,
            "exam_code": self.exam_code,
            "year": self.year,
            "paper": self.paper,
            "variant": self.variant,
            "topic": self.topic,
            "question_node": self.question_node.to_dict(),
            "composite_path": str(self.composite_path),
            "regions_path": str(self.regions_path),
            "sub_topics": list(self.sub_topics),
            "root_text": self.root_text,
            "child_text": self.child_text,
            "horizontal_offset": self.horizontal_offset,
        }
        if self.mark_scheme_path:
            d["mark_scheme_path"] = str(self.mark_scheme_path)
        if self.content_right is not None:
            d["content_right"] = self.content_right
        if self.numeral_bbox is not None:
            d["numeral_bbox"] = list(self.numeral_bbox)
        if self.mark_bboxes:
            d["mark_bboxes"] = [list(box) for box in self.mark_bboxes]
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> Question:
        """
        Deserialize from dictionary.
        
        Args:
            data: Dict representation
            
        Returns:
            Question instance
        """
        return cls(
            id=data["id"],
            exam_code=data["exam_code"],
            year=data["year"],
            paper=data["paper"],
            variant=data.get("variant", 1),
            topic=data["topic"],
            question_node=Part.from_dict(data["question_node"]),
            composite_path=Path(data["composite_path"]),
            regions_path=Path(data["regions_path"]),
            mark_scheme_path=(
                Path(data["mark_scheme_path"]) 
                if data.get("mark_scheme_path") else None
            ),
            sub_topics=tuple(data.get("sub_topics", [])),
            content_right=data.get("content_right"),
            numeral_bbox=tuple(data["numeral_bbox"]) if data.get("numeral_bbox") else None,
            root_text=data.get("root_text", ""),
            child_text=data.get("child_text", {}),
            mark_bboxes=tuple(tuple(box) for box in data.get("mark_bboxes", [])),
            horizontal_offset=data.get("horizontal_offset", 0),
        )
    
    def __repr__(self) -> str:
        """Concise representation for debugging."""
        return (
            f"Question({self.id!r}, exam={self.exam_code}, "
            f"marks={self.total_marks}, topic={self.topic!r})"
        )
