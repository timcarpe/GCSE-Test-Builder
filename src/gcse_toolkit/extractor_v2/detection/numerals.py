"""
Module: extractor_v2.detection.numerals

Purpose:
    Question numeral detection - identifies question starts (1, 2, 3...)
    in PDF pages. Wraps verified detection functions with new
    immutable dataclasses.

Key Functions:
    - detect_question_numerals(): Find all question starts in document

Key Classes:
    - QuestionNumeral: Immutable dataclass for detected question start

Dependencies:
    - fitz (PyMuPDF): PDF document access
    - gcse_toolkit.extractor.v2.utils.detection: Core detection functions

Used By:
    - extractor_v2.pipeline: Detects questions for extraction

Verified From:
    - detection.py:detect_question_starts (lines 184-213)
    - detection.py:filter_monotonic (lines 281-294)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Optional

import fitz


@dataclass(frozen=True)
class QuestionNumeral:
    """
    Detected question number with position.
    
    Represents a question start marker detected in a PDF. Question
    starts can be numerals (1, 2), letters (a, b), or romans (i, ii).
    
    Attributes:
        number: Question number (1, 2, 3...) or ordinal for letters/romans.
        page: 0-indexed page number where detected.
        y_position: Y-coordinate in PDF points from page top.
        bbox: (left, top, right, bottom) in PDF points.
        text: Original detected text.
        is_pseudocode: True if detected in pseudocode context.
        
    Example:
        >>> numeral = QuestionNumeral(number=1, page=0, y_position=150.5, bbox=(50, 150, 70, 170))
        >>> numeral.number
        1
    """
    number: int
    page: int
    y_position: float
    bbox: Tuple[float, float, float, float]
    text: str = ""
    is_pseudocode: bool = False


def detect_question_numerals(
    doc: fitz.Document,
    *,
    header_ratio: float = 0.08,
    footer_ratio: float = 0.08,
) -> List[QuestionNumeral]:
    """
    Detect question numbers across all pages in a PDF.
    
    Scans each page for question start markers in the left margin.
    Returns a monotonic sequence (1, 2, 3...) filtering out duplicates
    and preferring non-pseudocode detections.
    
    Args:
        doc: Open PyMuPDF document.
        header_ratio: Fraction of page height to skip as header. Defaults to 0.08.
        footer_ratio: Fraction of page height to skip as footer. Defaults to 0.08.
        
    Returns:
        List of QuestionNumeral sorted by (page, y_position).
        
    Raises:
        ValueError: If doc is closed or empty.
        
    Example:
        >>> with fitz.open("exam.pdf") as doc:
        ...     numerals = detect_question_numerals(doc)
        ...     print(f"Found {len(numerals)} questions")
        Found 8 questions
    """
    if doc.is_closed:
        raise ValueError("Document is closed")
    if doc.page_count == 0:
        raise ValueError("Document has no pages")
    
    # Import and use verified functions from utils
    from gcse_toolkit.extractor_v2.utils.detection import (
        detect_question_starts,
        filter_monotonic,
    )
    from gcse_toolkit.extractor_v2.config import ExtractionConfig
    
    # Create config
    config = ExtractionConfig(
        header_ratio=header_ratio,
        footer_ratio=footer_ratio,
    )
    
    # Get filtered starts
    raw_starts = filter_monotonic(detect_question_starts(doc, config))
    
    # Convert to V2 dataclasses
    return [
        QuestionNumeral(
            number=s.qnum,
            page=s.page,
            y_position=s.y,
            bbox=s.bbox if s.bbox else (0, s.y, 50, s.y + 20),
            text=getattr(s, 'text', ''),
            is_pseudocode=getattr(s, 'looks_like_pseudocode', False),
        )
        for s in raw_starts
    ]
