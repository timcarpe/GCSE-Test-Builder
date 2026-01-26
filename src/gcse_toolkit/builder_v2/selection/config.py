"""
Module: builder_v2.selection.config

Purpose:
    Configuration dataclass for the selection algorithm.
    Immutable configuration with validation on construction.

Key Classes:
    - SelectionConfig: Main configuration for question selection

Dependencies:
    - dataclasses (std)

Used By:
    - builder_v2.selection.selector: Main selector
    - builder_v2.controller: Build controller
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .part_mode import PartMode


@dataclass(frozen=True)
class SelectionConfig:
    """
    Configuration for the selection algorithm (immutable).
    
    Controls how questions are selected to meet mark targets
    while respecting topic coverage constraints.
    
    Attributes:
        target_marks: Target total marks for the exam
        tolerance: Acceptable deviation from target_marks (±)
        topics: List of topics to include (empty = all topics)
        seed: Random seed for reproducible selection
        allow_pruning: Whether to prune parts to hit exact marks
        force_topic_coverage: Ensure all requested topics have questions
        max_questions: Maximum number of questions to select
        min_questions: Minimum number of questions to select
        prefer_full_questions: Prefer whole questions over partial
    
    Invariants:
        - target_marks > 0
        - tolerance >= 0
        - max_questions is None or max_questions >= min_questions
    
    Example:
        >>> config = SelectionConfig(target_marks=50, tolerance=3)
        >>> config.mark_range
        (47, 53)
    """
    
    # Mark targeting
    target_marks: int
    tolerance: int = 2
    
    # Topic filtering
    topics: List[str] = field(default_factory=list)
    
    # Algorithm behavior
    seed: int = 42
    part_mode: PartMode = PartMode.SKIP
    force_topic_coverage: bool = True
    
    # Question count limits
    max_questions: Optional[int] = None
    min_questions: int = 1
    
    # Selection preferences
    prefer_full_questions: bool = True
    
    # Keyword mode (Phase 6.6)
    keyword_mode: bool = False
    keyword_matched_labels: Dict[str, Set[str]] = field(default_factory=dict)
    pinned_question_ids: Set[str] = field(default_factory=set)
    pinned_part_labels: Set[str] = field(default_factory=set)
    
    # Advanced behavioral control
    allow_greedy_fill: Optional[bool] = None  # None = True for Topic, False for Keyword
    allow_keyword_backfill: bool = True       # Control keyword matching backfill
    
    def __post_init__(self) -> None:
        """Validate configuration on construction."""
        if self.target_marks <= 0:
            raise ValueError(f"target_marks must be positive: {self.target_marks}")
        if self.tolerance < 0:
            raise ValueError(f"tolerance must be non-negative: {self.tolerance}")
        if self.min_questions < 0:
            raise ValueError(f"min_questions must be non-negative: {self.min_questions}")
        if self.max_questions is not None and self.max_questions < self.min_questions:
            raise ValueError(
                f"max_questions ({self.max_questions}) must be >= "
                f"min_questions ({self.min_questions})"
            )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Calculated Properties
    # ─────────────────────────────────────────────────────────────────────────
    
    @property
    def mark_range(self) -> tuple[int, int]:
        """
        Get acceptable mark range (min, max).
        
        Returns:
            Tuple of (target - tolerance, target + tolerance)
        """
        return (self.target_marks - self.tolerance, self.target_marks + self.tolerance)
    
    @property
    def topic_set(self) -> Set[str]:
        """
        Get topics as a set for efficient lookup.
        
        Returns:
            Set of topic strings, empty if all topics allowed
        """
        return set(self.topics)
    
    def is_within_tolerance(self, marks: int) -> bool:
        """
        Check if marks value is within acceptable tolerance.
        
        Args:
            marks: Mark value to check
            
        Returns:
            True if marks within [target - tolerance, target + tolerance]
        """
        min_marks, max_marks = self.mark_range
        return min_marks <= marks <= max_marks
