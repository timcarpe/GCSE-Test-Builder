"""
Module: extractor_v2.slicing.compositor

Purpose:
    Creates composite images from PDF page segments. A composite is a
    single vertical image containing all content for a question, stitched
    from potentially multiple pages.

Key Functions:
    - create_composite(): Stitch page segments into single image
    - render_question_composite(): Render question from PDF to composite

Key Classes:
    - PageSegment: Rendered section of a PDF page
    - QuestionBounds: Start/end positions across pages

Dependencies:
    - PIL.Image: Image stitching
    - gcse_toolkit.extractor_v2.utils.pdf: Page rendering

Used By:
    - extractor_v2.pipeline: Creates composites for each question
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from PIL import Image
import fitz

from ..utils.pdf import render_page_region, extract_text


@dataclass
class PageSegment:
    """
    A rendered segment from a PDF page.
    
    Represents a portion of a PDF page that has been rendered
    to an image. Multiple segments are stitched into a composite.
    
    Attributes:
        page_index: 0-indexed page number in the PDF.
        image: Rendered grayscale image.
        y_offset: Vertical offset in the composite (set during stitching).
        clip: Original clip rectangle in PDF points.
        trim_offset: (x, y) offset from trimming whitespace.
    """
    page_index: int
    image: Image.Image
    y_offset: int = 0
    clip: Optional[fitz.Rect] = None
    trim_offset: Tuple[int, int] = (0, 0)


@dataclass(frozen=True)
class QuestionBounds:
    """
    Bounds of a question across pages.
    
    Defines where a question starts and ends within the PDF,
    potentially spanning multiple pages.
    
    Attributes:
        start_page: 0-indexed page where question starts.
        start_y: Y-coordinate where question starts (PDF points).
        end_page: 0-indexed page where question ends.
        end_y: Y-coordinate where question ends (PDF points).
    """
    start_page: int
    start_y: float
    end_page: int
    end_y: float


def create_composite(segments: List[PageSegment]) -> Image.Image:
    """
    Stitch page segments into a single composite image.
    
    Vertically concatenates rendered page segments into one tall
    grayscale image. Updates each segment's y_offset to track
    its position in the composite.
    
    Args:
        segments: List of rendered page segments to stitch.
        
    Returns:
        Single grayscale composite image.
        
    Raises:
        ValueError: If segments is empty.
        
    Example:
        >>> segments = [PageSegment(0, img1), PageSegment(1, img2)]
        >>> composite = create_composite(segments)
        >>> composite.height
        1200  # Sum of segment heights
    """
    if not segments:
        raise ValueError("No segments to composite")
    
    # Calculate total dimensions
    total_height = sum(s.image.height for s in segments)
    max_width = max(s.image.width for s in segments)
    
    # Create composite canvas
    composite = Image.new("L", (max_width, total_height), 255)
    
    # Stitch segments
    y_offset = 0
    for segment in segments:
        composite.paste(segment.image, (0, y_offset))
        # Update segment's offset for coordinate translation
        segment.y_offset = y_offset
        y_offset += segment.image.height
    
    return composite


def render_question_composite(
    doc: fitz.Document,
    bounds: QuestionBounds,
    dpi: int = 200,
    *,
    trim_whitespace: bool = True,
) -> Tuple[Image.Image, List[PageSegment]]:
    """
    Render a question from PDF to composite image.
    
    Renders all pages/regions that contain the question content
    and stitches them into a single vertical image.
    
    Args:
        doc: Open PyMuPDF document.
        bounds: Question start/end positions.
        dpi: Resolution for rendering. Defaults to 200.
        trim_whitespace: Whether to trim margins. Defaults to True.
        
    Returns:
        Tuple of (composite_image, segments) where segments contains
        the individual page segments with their positions.
        
    Example:
        >>> bounds = QuestionBounds(start_page=0, start_y=150, end_page=0, end_y=600)
        >>> composite, segments = render_question_composite(doc, bounds)
        >>> composite.size
        (800, 450)
    """
    segments: List[PageSegment] = []
    
    for page_idx in range(bounds.start_page, bounds.end_page + 1):
        page = doc[page_idx]
        page_rect = page.rect
        
        # Determine vertical bounds for this page
        top = bounds.start_y if page_idx == bounds.start_page else 0.0
        bottom = bounds.end_y if page_idx == bounds.end_page else page_rect.height
        
        # Skip if no content
        if bottom <= top:
            continue
        
        # Create clip for this page segment
        clip = fitz.Rect(page_rect.x0, top, page_rect.x1, bottom)
        
        # Render the region
        image, trim_offset = render_page_region(
            page, clip, dpi, 
            trim_whitespace=trim_whitespace
        )
        
        segment = PageSegment(
            page_index=page_idx,
            image=image,
            clip=clip,
            trim_offset=trim_offset,
        )
        segments.append(segment)
    
    if not segments:
        raise ValueError(f"No content found for question bounds: {bounds}")
    
    composite = create_composite(segments)
    return composite, segments
