"""
Module: selection

Purpose:
    Provides SelectionPlan and SelectionResult dataclasses for the
    question selection algorithm. These track which parts of which
    questions will be included in the generated exam.

Key Functions:
    - SelectionPlan.full_question(q): Include all parts
    - SelectionPlan.leaves_only(q): Include only leaf parts
    - SelectionPlan.marks: Calculated from included leaves
    - SelectionResult.total_marks: Sum across all plans
    - SelectionResult.within_tolerance: Check against target

Dependencies:
    - dataclasses (std)
    - functools (std)
    - .questions.Question
    - .parts.Part

Used By:
    - builder_v2 (future)

Design Deviation from V1:
    V1 PlanOption was mutable with marks calculated inconsistently.
    V2 uses frozen dataclasses with cached_property for marks.
    See: docs/architecture/bugs.md (B1, B2)
    See: docs/architecture/decision_log.md (DECISION-004)
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import FrozenSet, Set

from .questions import Question
from .parts import Part


@dataclass(frozen=True)
class SelectionPlan:
    """
    Plan for which parts of a question to include in output.
    
    Defines a selection of parts from a question to render.
    Used by the selection algorithm to track what will be included.
    
    Attributes:
        question: The question being selected from
        included_parts: Set of part labels to include
    
    Invariants:
        - included_parts contains only valid labels from question
        - marks is calculated from included leaf parts only
    
    Example:
        >>> plan = SelectionPlan(question, frozenset(["1(a)(i)", "1(a)(ii)"]))
        >>> plan.marks  # Sum of marks for included leaves
        5
        >>> plan.included_leaves
        [Part("1(a)(i)"), Part("1(a)(ii)")]
    """

    question: Question
    included_parts: FrozenSet[str]  # Set of part labels to include

    def __post_init__(self) -> None:
        """Validate selection on construction."""
        # Validate all included parts exist in question
        valid_labels = {p.label for p in self.question.all_parts}
        invalid = self.included_parts - valid_labels
        if invalid:
            raise ValueError(
                f"Invalid part labels for question {self.question.id}: {invalid}"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Calculated Properties (NEVER stored)
    # ─────────────────────────────────────────────────────────────────────────

    @cached_property
    def marks(self) -> int:
        """
        Calculate marks from included leaf parts only.
        
        **IMPORTANT:** Only counts LEAF parts, not parent aggregates.
        This ensures no double-counting.
        
        Returns:
            Sum of marks for all included leaves
        """
        total = 0
        for part in self.question.leaf_parts:
            if part.label in self.included_parts:
                total += part.marks.value
        return total

    @cached_property
    def included_leaves(self) -> tuple[Part, ...]:
        """
        Get tuple of included leaf parts.
        
        Returns:
            Immutable tuple of Parts that are leaves AND included
        """
        return tuple(
            p for p in self.question.leaf_parts 
            if p.label in self.included_parts
        )

    @cached_property
    def excluded_leaves(self) -> tuple[Part, ...]:
        """
        Get tuple of excluded leaf parts.
        
        Returns:
            Immutable tuple of Parts that are leaves but NOT included
        """
        return tuple(
            p for p in self.question.leaf_parts 
            if p.label not in self.included_parts
        )

    @property
    def is_full_question(self) -> bool:
        """
        Check if all leaves are included.
        
        Returns:
            True if no leaves are excluded
        """
        return len(self.excluded_leaves) == 0

    @property
    def is_partial(self) -> bool:
        """
        Check if some but not all leaves are included.
        
        Returns:
            True if at least one leaf is excluded
        """
        return len(self.excluded_leaves) > 0

    # ─────────────────────────────────────────────────────────────────────────
    # Factory Methods
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def full_question(cls, question: Question) -> SelectionPlan:
        """
        Create a plan that includes all parts.
        
        Args:
            question: Question to select from
            
        Returns:
            SelectionPlan with all parts included
        """
        all_labels = frozenset(p.label for p in question.all_parts)
        return cls(question=question, included_parts=all_labels)

    @classmethod
    def leaves_only(cls, question: Question) -> SelectionPlan:
        """
        Create a plan that includes only leaf parts.
        
        Args:
            question: Question to select from
            
        Returns:
            SelectionPlan with only leaf parts included
        """
        leaf_labels = frozenset(p.label for p in question.leaf_parts)
        return cls(question=question, included_parts=leaf_labels)

    def __repr__(self) -> str:
        """Concise representation for debugging."""
        return (
            f"SelectionPlan({self.question.id}, "
            f"marks={self.marks}, "
            f"parts={len(self.included_leaves)}/{len(self.question.leaf_parts)})"
        )


@dataclass(frozen=True)
class SelectionResult:
    """
    Result of the selection algorithm.
    
    Contains all selected questions/plans and selection metadata.
    
    Attributes:
        plans: Tuple of SelectionPlan objects
        target_marks: Requested target mark total
        tolerance: Allowed deviation from target
    
    Invariants:
        - total_marks == sum of plan.marks for all plans
        - No duplicate questions in plans
    
    Example:
        >>> result = SelectionResult(plans=(plan1, plan2), target_marks=50, tolerance=5)
        >>> result.total_marks
        47
        >>> result.within_tolerance
        True
    """

    plans: tuple[SelectionPlan, ...]
    target_marks: int
    tolerance: int

    def __post_init__(self) -> None:
        """Validate selection result on construction."""
        # Check for duplicate questions
        question_ids = [p.question.id for p in self.plans]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Duplicate questions in selection result")

    # ─────────────────────────────────────────────────────────────────────────
    # Calculated Properties (NEVER stored)
    # ─────────────────────────────────────────────────────────────────────────

    @cached_property
    def total_marks(self) -> int:
        """
        Calculate total marks from plans.
        
        **IMPORTANT:** Always calculated, never stored.
        
        Returns:
            Sum of marks across all plans
        """
        return sum(plan.marks for plan in self.plans)

    @cached_property
    def covered_topics(self) -> Set[str]:
        """
        Get set of topics covered by selection.
        
        Includes both question-level topics and granular part-level topics.
        
        Returns:
            Set of unique topic strings
        """
        topics = set()
        for plan in self.plans:
            # Add specific topics from included leaves (with fallback to question topic)
            for leaf in plan.included_leaves:
                effective_topic = leaf.topic or plan.question.topic
                if effective_topic:
                    topics.add(effective_topic)
        return topics

    @property
    def question_count(self) -> int:
        """Number of questions in selection."""
        return len(self.plans)

    @property
    def within_tolerance(self) -> bool:
        """
        Check if total marks are within tolerance of target.
        
        Returns:
            True if |total_marks - target_marks| <= tolerance
        """
        return abs(self.total_marks - self.target_marks) <= self.tolerance

    @property
    def deviation(self) -> int:
        """
        Absolute deviation from target marks.
        
        Returns:
            Absolute difference between total and target
        """
        return abs(self.total_marks - self.target_marks)

    @property
    def mark_difference(self) -> int:
        """
        How far total is from target (signed).
        
        Returns:
            Positive if over target, negative if under
        """
        return self.total_marks - self.target_marks

    # ─────────────────────────────────────────────────────────────────────────
    # Query Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_plan(self, question_id: str) -> SelectionPlan | None:
        """
        Find a plan by question ID.
        
        Args:
            question_id: Question ID to search for
            
        Returns:
            Matching SelectionPlan or None
        """
        for plan in self.plans:
            if plan.question.id == question_id:
                return plan
        return None

    def __repr__(self) -> str:
        """Concise representation for debugging."""
        return (
            f"SelectionResult(questions={self.question_count}, "
            f"marks={self.total_marks}/{self.target_marks}±{self.tolerance}, "
            f"topics={len(self.covered_topics)})"
        )
