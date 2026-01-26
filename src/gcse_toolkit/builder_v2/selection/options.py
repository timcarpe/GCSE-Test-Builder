"""
Module: builder_v2.selection.options

Purpose:
    Generate valid selection options for each question.
    An option represents a valid way to select parts from a question.

Key Functions:
    - generate_options(): Generate all valid options for a question
    - generate_all_options(): Generate options for multiple questions

Key Classes:
    - QuestionOptions: Container for a question's selection options

Dependencies:
    - gcse_toolkit.core.models: Question, Part, SelectionPlan

Used By:
    - builder_v2.selection.selector: Main selector
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cached_property
from itertools import combinations
from typing import Iterator, List

from gcse_toolkit.core.models import Question, Part
from gcse_toolkit.core.models.selection import SelectionPlan

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuestionOptions:
    """
    Container for a question's valid selection options.
    
    Stores all valid ways to select parts from a question,
    sorted by marks descending.
    
    Attributes:
        question: The source question
        options: Tuple of SelectionPlan options, sorted by marks desc
    
    Example:
        >>> opts = generate_options(question)
        >>> opts.max_marks
        8
        >>> opts.option_count
        15
    """
    
    question: Question
    options: tuple[SelectionPlan, ...]
    
    @cached_property
    def max_marks(self) -> int:
        """Maximum marks available (full question)."""
        return self.options[0].marks if self.options else 0
    
    @cached_property
    def min_marks(self) -> int:
        """Minimum marks (smallest option)."""
        return self.options[-1].marks if self.options else 0
    
    @property
    def option_count(self) -> int:
        """Number of valid options."""
        return len(self.options)
    
    def options_in_range(self, min_marks: int, max_marks: int) -> Iterator[SelectionPlan]:
        """
        Yield options within a mark range.
        
        Args:
            min_marks: Minimum marks (inclusive)
            max_marks: Maximum marks (inclusive)
            
        Yields:
            SelectionPlan objects within range
        """
        for option in self.options:
            if min_marks <= option.marks <= max_marks:
                yield option
    
    def best_option_for_marks(self, target: int) -> SelectionPlan | None:
        """
        Get option closest to target marks without exceeding.
        
        Args:
            target: Target mark value
            
        Returns:
            Best matching SelectionPlan or None
        """
        for option in self.options:  # Already sorted desc
            if option.marks <= target:
                return option
        return None


from .part_mode import PartMode


def generate_options(
    question: Question,
    *,
    part_mode: PartMode = PartMode.SKIP,
    min_parts: int = 1,
    allowed_labels: set[str] | None = None,
) -> QuestionOptions:
    """
    Generate valid selection options for a question based on part mode.
    
    Options are sorted by marks descending, then by part count descending.
    
    Args:
        question: Question to generate options for
        part_mode: How parts can be excluded:
            - ALL: Only full question (no partial selections)
            - PRUNE: Remove from end only (contiguous suffix subsets)
            - SKIP: Remove from anywhere (all combinations)
        min_parts: Minimum number of parts in an option
        allowed_labels: If provided, only use parts with these labels (keyword mode)
        
    Returns:
        QuestionOptions container with all valid options
        
    Example:
        >>> opts = generate_options(question, part_mode=PartMode.PRUNE)
        >>> len(opts.options)
        3  # Full, minus last, minus last two, etc.
    """
    all_leaves = question.leaf_parts
    
    # Filter leaves by allowed labels if keyword mode
    if allowed_labels is not None:
        leaves = [p for p in all_leaves if p.label in allowed_labels]
        if not leaves:
            logger.debug(f"Question {question.id}: no parts match allowed labels")
            return QuestionOptions(question=question, options=())
    else:
        leaves = list(all_leaves)
    
    # Filter out invalid parts (1:1 parity - retain valid parts only)
    valid_leaves = [p for p in leaves if p.is_valid]
    if len(valid_leaves) < len(leaves):
        invalid_count = len(leaves) - len(valid_leaves)
        logger.debug(f"Question {question.id}: excluded {invalid_count} invalid parts")
    leaves = valid_leaves

    options: List[SelectionPlan] = []
    
    if not leaves:
        logger.warning(f"Question {question.id} has no leaf parts")
        return QuestionOptions(question=question, options=())
    
    # Always include full question (all matched leaves)
    full = SelectionPlan(question=question, included_parts=frozenset(p.label for p in leaves))
    options.append(full)
    
    if part_mode == PartMode.ALL:
        # Only full question allowed - no partial selections
        pass
    
    elif part_mode == PartMode.PRUNE and len(leaves) > 1:
        # Contiguous suffix subsets only - remove from end
        # For leaves [a, b, c], generate: {a,b}, {a}
        for size in range(len(leaves) - 1, min_parts - 1, -1):
            labels = frozenset(p.label for p in leaves[:size])
            plan = SelectionPlan(question=question, included_parts=labels)
            options.append(plan)
    
    elif part_mode == PartMode.SKIP and len(leaves) > 1:
        # All combinations - remove from anywhere
        for size in range(len(leaves) - 1, min_parts - 1, -1):
            for leaf_combo in combinations(leaves, size):
                labels = frozenset(p.label for p in leaf_combo)
                plan = SelectionPlan(question=question, included_parts=labels)
                options.append(plan)
    
    # Sort by marks desc, then by part count desc (prefer more parts)
    options.sort(key=lambda p: (-p.marks, -len(p.included_parts)))
    
    return QuestionOptions(question=question, options=tuple(options))


def generate_all_options(
    questions: List[Question],
    *,
    part_mode: PartMode = PartMode.SKIP,
    min_parts: int = 1,
) -> List[QuestionOptions]:
    """
    Generate options for all questions.
    
    Args:
        questions: List of questions to process
        part_mode: How parts can be excluded (ALL, PRUNE, SKIP)
        min_parts: Minimum number of parts per option
        
    Returns:
        List of QuestionOptions, one per question
        
    Example:
        >>> all_opts = generate_all_options(questions)
        >>> total_options = sum(o.option_count for o in all_opts)
    """
    return [
        generate_options(q, part_mode=part_mode, min_parts=min_parts)
        for q in questions
    ]


def _get_context_labels(question: Question, matched_labels: set[str]) -> set[str]:
    """
    Get labels of parent parts needed for context.
    
    When only certain leaf parts match keywords, we still need to
    include their parent parts to maintain proper question structure.
    
    Args:
        question: Question to analyze
        matched_labels: Set of labels that matched (leaf parts)
        
    Returns:
        Set of parent part labels to include for context
        
    Example:
        >>> # If 1(a)(i) matches, we need 1(a) and 1 as context
        >>> matched = {'1(a)(i)'}
        >>> context = _get_context_labels(question, matched)
        >>> context
        {'1', '1(a)'}
    """
    context = set()
    
    if not question.question_node:
        return context
    
    # Find all parts with matched labels
    matched_parts = []
    for part in question.all_parts:
        if part.label in matched_labels:
            matched_parts.append(part)
    
    # Walk up tree from each matched part to root
    for part in matched_parts:
        current = part.parent
        while current is not None:
            if current.label and current.label not in matched_labels:
                context.add(current.label)
            current = current.parent
    
    return context
