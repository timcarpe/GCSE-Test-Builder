"""
Module: extractor_v2.detection.marks

Purpose:
    Mark box detection - identifies [N] style mark allocations in
    question regions. Wraps verified detection function with
    new immutable dataclass.

Key Functions:
    - detect_mark_boxes(): Find all [N] marks in a page region

Key Classes:
    - MarkBox: Immutable dataclass for detected mark allocation

Dependencies:
    - fitz (PyMuPDF): PDF page access
    - gcse_toolkit.extractor_v2.utils.detectors: Core detection functions

Used By:
    - extractor_v2.pipeline: Detects marks for questions
    - extractor_v2.structuring.tree_builder: Assigns marks to parts

Verified From:
    - detectors.py:detect_mark_boxes (lines 130-171) - REUSE AS-IS
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import fitz


@dataclass(frozen=True)
class MarkBox:
    """
    Detected [N] mark box with position.
    
    Represents a mark allocation like [5] or [10] detected
    in a question region.
    
    Attributes:
        value: Mark value (1-99).
        y_position: Y-coordinate in composite image pixels.
        bbox: (left, top, right, bottom) in pixels.
        
    Example:
        >>> mark = MarkBox(value=5, y_position=200, bbox=(450, 200, 480, 220))
        >>> mark.y_center
        210
    """
    value: int
    y_position: int
    bbox: Tuple[int, int, int, int]
    
    @property
    def y_center(self) -> int:
        """Vertical center of the mark box."""
        return (self.bbox[1] + self.bbox[3]) // 2


def detect_mark_boxes(
    page: fitz.Page,
    clip: fitz.Rect,
    dpi: int,
    y_offset: int = 0,
    trim_offset: Tuple[int, int] = (0, 0),
) -> List[MarkBox]:
    """
    Detect [N] mark allocations in a page region.
    
    Scans for square-bracketed numbers indicating mark allocations.
    These are typically found on the right side of question content.
    
    Args:
        page: PyMuPDF page object.
        clip: Rectangle defining the search region (in PDF points).
        dpi: Resolution for coordinate conversion.
        y_offset: Vertical offset to add for multi-page composites.
        trim_offset: (x, y) trim offset applied to rendered image.
        
    Returns:
        List of MarkBox sorted by y_position.
        
    Example:
        >>> marks = detect_mark_boxes(page, clip, dpi=200)
        >>> total = sum(m.value for m in marks)
        >>> print(f"Total marks: {total}")
        Total marks: 15
    """
    # Import verified detection function (REUSE AS-IS)
    from gcse_toolkit.extractor_v2.utils.detectors import detect_mark_boxes
    
    # Get detections from V2 module
    raw_marks = detect_mark_boxes(page, clip, dpi, y_offset, trim_offset)
    
    return _convert_mark_detections(raw_marks)


def detect_mark_boxes_from_data(
    text_data: dict,
    clip,
    dpi: int,
    y_offset: int = 0,
    trim_offset: Tuple[int, int] = (0, 0),
) -> List[MarkBox]:
    """
    Detect mark boxes from pre-extracted text data.
    
    OPTIMIZATION #3: This variant accepts pre-extracted text data,
    allowing the pipeline to extract once and pass to multiple detectors.
    
    Args:
        text_data: Pre-extracted text data from extract_text_data().
        clip: Rectangle defining the search region (for coordinate conversion).
        dpi: Resolution for coordinate conversion.
        y_offset: Vertical offset to add for multi-page composites.
        trim_offset: (x, y) trim offset applied to rendered image.
        
    Returns:
        List of MarkBox sorted by y_position.
    """
    from gcse_toolkit.extractor_v2.utils.detectors import detect_mark_boxes_from_data
    
    raw_marks = detect_mark_boxes_from_data(text_data, clip, dpi, y_offset, trim_offset)
    
    return _convert_mark_detections(raw_marks)


def _convert_mark_detections(raw_marks) -> List[MarkBox]:
    """Convert raw Detection objects to MarkBox dataclasses."""
    return [
        MarkBox(
            value=d.value,
            y_position=d.bbox[1],  # y0 from bbox
            bbox=tuple(d.bbox),
        )
        for d in raw_marks
    ]
