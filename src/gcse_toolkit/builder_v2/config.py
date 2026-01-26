"""
Module: builder_v2.config

Purpose:
    Configuration dataclass for the V2 building pipeline. Immutable
    configuration with validation on construction.

Key Classes:
    - BuilderConfig: Main configuration for building exams

Dependencies:
    - dataclasses (std)
    - pathlib (std)

Used By:
    - builder_v2.controller: Main build controller
    - builder_v2.loading.loader: Question loading
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from gcse_toolkit.builder_v2.selection.part_mode import PartMode


@dataclass(frozen=True)
class BuilderConfig:
    """
    Configuration for building exams (immutable).
    
    Changes from v1:
    - Immutable (frozen=True)
    - No legacy/atlas options (single format)
    - Clearer field names
    
    Attributes:
        cache_path: Path to slices cache root
        exam_code: Exam code like "0478"
        target_marks: Target total marks for exam
        topics: Optional list of topics to filter by
        years: Optional list of years to filter by
        papers: Optional list of paper numbers to filter by
        tolerance: Acceptable deviation from target_marks
        seed: Random seed for selection reproducibility
        allow_pruning: Whether to prune parts to fit marks (deprecated, use part_mode)
        part_mode: Part selection mode (ALL/PRUNE/SKIP)
        force_topic_coverage: Ensure all topics represented
        output_dir: Output directory for generated files
        include_markscheme: Whether to include mark scheme
        page_width_px: Page width in pixels
        page_height_px: Page height in pixels
        margin_px: Page margin in pixels
    
    Example:
        >>> config = BuilderConfig(
        ...     cache_path=Path("/cache"),
        ...     exam_code="0478",
        ...     target_marks=50,
        ... )
    """
    
    # Required
    cache_path: Path
    exam_code: str
    target_marks: int
    
    # Optional filtering
    topics: List[str] = field(default_factory=list)
    years: Optional[List[int]] = None
    papers: Optional[List[int]] = None
    
    # Selection behavior
    tolerance: int = 2
    seed: int = 42
    part_mode: PartMode = PartMode.SKIP
    force_topic_coverage: bool = True
    
    # Output
    output_dir: Optional[Path] = None
    include_markscheme: bool = True
    export_zip: bool = False  # If True, also export selected questions as cropped images in questions.zip
    
    # Layout
    page_width_px: int = 1654  # A4 width at 200 DPI
    page_height_px: int = 2339  # A4 height at 200 DPI
    margin_px: int = 50
    
    # Keyword mode
    keyword_mode: bool = False
    keywords: List[str] = field(default_factory=list)
    keyword_questions: List[str] = field(default_factory=list)  # Pinned question IDs
    keyword_part_pins: List[str] = field(default_factory=list)  # Pinned parts (format: "qid::label")
    allow_keyword_backfill: bool = True  # Control keyword matching backfill
    
    # Question ID headers
    show_question_ids: bool = True  # Show question ID as text header before each question
    
    # Footer
    show_footer: bool = True  # Show version/copyright footer on each page
    
    def __post_init__(self) -> None:
        """Validate configuration on construction."""
        if self.target_marks <= 0:
            raise ValueError(f"target_marks must be positive: {self.target_marks}")
        if self.tolerance < 0:
            raise ValueError(f"tolerance must be non-negative: {self.tolerance}")
        if not self.exam_code or len(self.exam_code) != 4:
            raise ValueError(f"exam_code must be 4 characters: {self.exam_code!r}")
        if not self.exam_code.isdigit():
            raise ValueError(f"exam_code must be digits: {self.exam_code!r}")
