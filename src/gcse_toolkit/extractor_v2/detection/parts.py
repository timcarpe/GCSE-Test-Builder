"""
Module: extractor_v2.detection.parts

Purpose:
    Part label detection - identifies (a), (b) letters and (i), (ii) roman
    numerals within question regions. Wraps verified detection
    functions with new immutable dataclasses.

Key Functions:
    - detect_part_labels(): Find letters and romans in a page region

Key Classes:
    - PartLabel: Immutable dataclass for detected part label

Dependencies:
    - fitz (PyMuPDF): PDF page access
    - gcse_toolkit.extractor_v2.utils.detectors: Core detection functions

Used By:
    - extractor_v2.pipeline: Detects parts within questions

Verified From:
    - detectors.py:detect_section_labels (lines 72-127)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Tuple

import fitz


@dataclass(frozen=True)
class PartLabel:
    """
    Detected part label with position.
    
    Represents a section marker like (a), (b) for letters or
    (i), (ii) for roman numerals detected within a question region.
    
    Attributes:
        label: The label text without parentheses, e.g. "a", "ii".
        kind: "letter" for (a)-(z), "roman" for (i)-(x).
        y_position: Y-coordinate in composite image pixels.
        bbox: (left, top, right, bottom) in pixels.
        
    Example:
        >>> label = PartLabel(label="a", kind="letter", y_position=120, bbox=(50, 120, 70, 140))
        >>> label.kind
        'letter'
    """
    label: str
    kind: Literal["letter", "roman"]
    y_position: int
    bbox: Tuple[int, int, int, int]


def detect_part_labels(
    page: fitz.Page,
    clip: fitz.Rect,
    dpi: int,
    y_offset: int = 0,
    trim_offset: Tuple[int, int] = (0, 0),
) -> Tuple[List[PartLabel], List[PartLabel]]:
    """
    Detect (a), (b) letters and (i), (ii) roman numerals in a page region.
    
    Scans the clipped region for parenthesized labels and classifies
    them as letters or roman numerals based on content.
    
    Args:
        page: PyMuPDF page object.
        clip: Rectangle defining the search region (in PDF points).
        dpi: Resolution for coordinate conversion.
        y_offset: Vertical offset to add for multi-page composites.
        trim_offset: (x, y) trim offset applied to rendered image.
        
    Returns:
        Tuple of (letters, romans) - two lists of PartLabel.
        
    Example:
        >>> letters, romans = detect_part_labels(page, clip, dpi=200)
        >>> print(f"Found {len(letters)} letters, {len(romans)} romans")
        Found 2 letters, 4 romans
    """
    # Import V2 detection function
    from gcse_toolkit.extractor_v2.utils.detectors import detect_section_labels
    
    # Get detections from utility module
    raw_letters, raw_romans = detect_section_labels(
        page, clip, dpi, y_offset, trim_offset
    )
    
    return _convert_detections(raw_letters, raw_romans)


def detect_part_labels_from_data(
    text_data: dict,
    clip,
    dpi: int,
    y_offset: int = 0,
    trim_offset: Tuple[int, int] = (0, 0),
) -> Tuple[List[PartLabel], List[PartLabel]]:
    """
    Detect part labels from pre-extracted text data.
    
    OPTIMIZATION #3: This variant accepts pre-extracted text data,
    allowing the pipeline to extract once and pass to multiple detectors.
    
    Args:
        text_data: Pre-extracted text data from extract_text_data().
        clip: Rectangle defining the search region (for coordinate conversion).
        dpi: Resolution for coordinate conversion.
        y_offset: Vertical offset to add for multi-page composites.
        trim_offset: (x, y) trim offset applied to rendered image.
        
    Returns:
        Tuple of (letters, romans) - two lists of PartLabel.
    """
    from gcse_toolkit.extractor_v2.utils.detectors import detect_section_labels_from_data
    
    raw_letters, raw_romans = detect_section_labels_from_data(
        text_data, clip, dpi, y_offset, trim_offset
    )
    
    return _convert_detections(raw_letters, raw_romans)


def _convert_detections(raw_letters, raw_romans) -> Tuple[List[PartLabel], List[PartLabel]]:
    """Convert raw Detection objects to PartLabel dataclasses."""
    letters = [
        PartLabel(
            label=d.label,
            kind="letter",
            y_position=d.bbox[1],  # y0 from bbox
            bbox=tuple(d.bbox),
        )
        for d in raw_letters
    ]
    
    romans = [
        PartLabel(
            label=d.label,
            kind="roman",
            y_position=d.bbox[1],  # y0 from bbox
            bbox=tuple(d.bbox),
        )
        for d in raw_romans
    ]
    
    return letters, romans
