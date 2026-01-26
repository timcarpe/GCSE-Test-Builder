"""
Module: extractor_v2.utils.text

Purpose:
    Text extraction utilities for question content.
    Extracts text from PDF pages for keyword search.

Key Functions:
    - extract_text_spans(): Get text with x/y positions from PDF page
    - text_for_region(): Get text within y-bounds (legacy)
    - text_for_bounded_region(): Get text within x/y bounding box

Dependencies:
    - fitz (pymupdf): PDF text extraction

Used By:
    - extractor_v2.pipeline: Text extraction during processing
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import fitz

logger = logging.getLogger(__name__)

# Constants
MIN_TEXT_HEIGHT = 1  # Minimum height for text spans
MIN_REGION_HEIGHT = 1  # Minimum height for regions

# Type alias for text spans with x/y coordinates
# (y_top, y_bottom, x_left, x_right, text)
TextSpan = Tuple[int, int, int, int, str]


def extract_text_spans(
    page: fitz.Page,
    clip: fitz.Rect,
    dpi: int,
    y_offset: int = 0,
    trim_offset: Tuple[int, int] = (0, 0),
) -> List[TextSpan]:
    """
    Extract text spans with x/y positions from a PDF page region.
    
    Args:
        page: PDF page to extract from
        clip: Rectangular region to extract
        dpi: Resolution for coordinate conversion
        y_offset: Vertical offset for stitched images
        trim_offset: (x, y) offset from whitespace trimming
        
    Returns:
        List of (y_top, y_bottom, x_left, x_right, text) tuples sorted by y_top
        
    Example:
        >>> spans = extract_text_spans(page, clip, dpi=200)
        >>> spans[0]
        (50, 65, 10, 400, "1 (a) Describe...")
    """
    scale = dpi / 72.0
    trim_x, trim_y = trim_offset
    spans: List[TextSpan] = []
    
    try:
        data = page.get_text("dict", clip=clip)
    except (RuntimeError, ValueError) as e:
        logger.debug(f"Failed to extract text: {e}")
        return spans
    
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            text = "".join(
                span.get("text", "") for span in line.get("spans", [])
            ).strip()
            if not text:
                continue
            
            bbox = line.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            
            # Convert to pixel coordinates (relative to composite)
            x0 = int(round((bbox[0] - clip.x0) * scale)) - trim_x
            y0 = int(round((bbox[1] - clip.y0) * scale)) - trim_y + y_offset
            x1 = int(round((bbox[2] - clip.x0) * scale)) - trim_x
            y1 = int(round((bbox[3] - clip.y0) * scale)) - trim_y + y_offset
            
            if y1 <= y0:
                y1 = y0 + MIN_TEXT_HEIGHT
            if x1 <= x0:
                x1 = x0 + 1
            
            spans.append((max(0, y0), max(0, y1), max(0, x0), max(0, x1), text))
    
    return sorted(spans, key=lambda s: s[0])


def text_for_region(
    spans: List[TextSpan],
    top: int,
    bottom: int,
) -> str:
    """
    Extract text content within a y-region (ignores x-bounds).
    
    Legacy function - use text_for_bounded_region for x/y filtering.
    
    Args:
        spans: List of (y_top, y_bottom, x_left, x_right, text) tuples
        top: Top y-coordinate of region
        bottom: Bottom y-coordinate of region
        
    Returns:
        Concatenated text from spans in region
    """
    if bottom <= top:
        bottom = top + MIN_REGION_HEIGHT
    
    parts: List[str] = []
    for span in spans:
        y0, y1 = span[0], span[1]
        text = span[-1]  # text is always last element
        if y1 <= top:
            continue
        if y0 >= bottom:
            break
        parts.append(text)
    
    return " ".join(parts).strip()


def text_for_bounded_region(
    spans: List[TextSpan],
    top: int,
    bottom: int,
    left: int,
    right: int,
) -> str:
    """
    Extract text content within a rectangular bounding box.
    
    Filters text spans by both x AND y coordinates, excluding
    margin text that falls outside the content area.
    
    Args:
        spans: List of (y_top, y_bottom, x_left, x_right, text) tuples
        top: Top y-coordinate of bounding box
        bottom: Bottom y-coordinate of bounding box
        left: Left x-coordinate of bounding box
        right: Right x-coordinate of bounding box
        
    Returns:
        Concatenated text from spans within bounding box
        
    Example:
        >>> spans = [(10, 20, 50, 200, "Question text"), (10, 20, 500, 600, "DO NOT WRITE")]
        >>> text_for_bounded_region(spans, 0, 30, 0, 400)
        "Question text"
    """
    if bottom <= top:
        bottom = top + MIN_REGION_HEIGHT
    if right <= left:
        right = left + 1
    
    parts: List[str] = []
    for y0, y1, x0, x1, text in spans:
        # Skip if outside y-bounds
        if y1 <= top:
            continue
        if y0 >= bottom:
            break  # Spans are sorted by y, so we can exit early
        
        # Skip if outside x-bounds (text entirely to left or right)
        if x1 <= left or x0 >= right:
            continue
        
        parts.append(text)
    
    return " ".join(parts).strip()


def sanitize_metadata_text(text: str) -> str:
    """
    Sanitize text for metadata by removing 'answer lines' (dots).
    
    Removes sequences of 3 or more dots and collapses whitespace.
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text
        
    Example:
        >>> sanitize_metadata_text("Explain: ........")
        "Explain:"
    """
    import re
    # Remove sequences of 3 or more dots
    text = re.sub(r"\.{3,}", " ", text)
    # Collapse multiple whitespaces and trim
    text = re.sub(r"\s+", " ", text).strip()
    return text

