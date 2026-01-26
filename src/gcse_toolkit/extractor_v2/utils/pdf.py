"""
Module: extractor_v2.utils.pdf

Purpose:
    PDF rendering and text extraction utilities. Provides functions for
    rendering PDF pages to images and extracting text content.

Key Functions:
    - render_page_region(): Render a clipped region of a PDF page
    - extract_text(): Extract text from a PDF page region
    - get_page_dimensions(): Get page dimensions in pixels

Dependencies:
    - fitz (PyMuPDF): PDF rendering
    - PIL.Image: Image handling
    - numpy: Image array operations

Used By:
    - extractor_v2.pipeline: Renders pages for question extraction
    - extractor_v2.detection: Extracts text for detection

Verified From:
    - question_extractor.py:_render_clip (lines 294-301)
    - question_extractor.py:_extract_segment_text (lines 303-308)
    - question_extractor.py:_trim_whitespace (lines 417-438)
"""

from __future__ import annotations

import io
import logging
from typing import Tuple

import fitz
import numpy as np
from PIL import Image

from gcse_toolkit.common.thresholds import IMAGE_THRESHOLDS, LAYOUT_THRESHOLDS

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_DPI = 200
DEFAULT_TRIM_PADDING = 12
TRIM_PERCENTILE = 98  # Percentile for whitespace detection threshold


def render_page_region(
    page: fitz.Page,
    clip: fitz.Rect,
    dpi: int = DEFAULT_DPI,
    *,
    trim_whitespace: bool = True,
    padding: int = DEFAULT_TRIM_PADDING,
) -> Tuple[Image.Image, Tuple[int, int]]:
    """
    Render a clipped region of a PDF page to an image.
    
    Renders the specified clip region at the given DPI and optionally
    trims whitespace margins from the resulting image.
    
    Args:
        page: PyMuPDF page object.
        clip: Rectangle defining the region to render (in PDF points).
        dpi: Resolution for rendering. Defaults to 200.
        trim_whitespace: Whether to trim whitespace margins. Defaults to True.
        padding: Pixels of padding to keep around content. Defaults to 12.
        
    Returns:
        Tuple of (image, trim_offset) where trim_offset is (left, top)
        pixel offset from original clip, useful for coordinate translation.
        
    Raises:
        ValueError: If clip is invalid (zero width/height).
        
    Example:
        >>> page = doc[0]
        >>> clip = fitz.Rect(0, 100, 595, 400)
        >>> image, offset = render_page_region(page, clip, dpi=150)
        >>> image.size
        (800, 400)
    """
    if clip.width <= 0 or clip.height <= 0:
        raise ValueError(f"Invalid clip region: {clip}")
    
    matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    
    # OPTIMIZATION #1: Render directly to grayscale colorspace
    # This eliminates the RGB→L conversion step (15-20% speedup in composite_creation)
    pix = page.get_pixmap(matrix=matrix, clip=clip, alpha=False, colorspace=fitz.csGRAY)
    
    # Direct grayscale - no .convert("L") needed
    image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    
    if trim_whitespace:
        image, offsets = _trim_whitespace(image, padding=padding)
        return image, (offsets[0], offsets[1])
    
    return image, (0, 0)


def extract_text(
    page: fitz.Page,
    clip: fitz.Rect | None = None,
) -> str:
    """
    Extract text content from a PDF page region.
    
    Extracts plain text from the specified region, preserving
    line breaks but not detailed layout information.
    
    Args:
        page: PyMuPDF page object.
        clip: Optional rectangle to limit extraction. If None, extracts
            from entire page.
            
    Returns:
        Extracted text as a string, empty string on error.
        
    Example:
        >>> text = extract_text(page, clip=fitz.Rect(0, 0, 300, 200))
        >>> print(text[:50])
        "1 (a) Describe how binary is used..."
    """
    try:
        if clip is not None:
            return page.get_text("text", clip=clip) or ""
        return page.get_text("text") or ""
    except (RuntimeError, ValueError) as e:
        logger.warning(f"Failed to extract text from page: {e}")
        return ""


def get_page_dimensions(
    page: fitz.Page,
    dpi: int = DEFAULT_DPI,
) -> Tuple[int, int]:
    """
    Get page dimensions in pixels at the specified DPI.
    
    Args:
        page: PyMuPDF page object.
        dpi: Resolution for calculation. Defaults to 200.
        
    Returns:
        (width, height) tuple in pixels.
        
    Example:
        >>> get_page_dimensions(page, dpi=72)
        (595, 842)
    """
    scale = dpi / 72.0
    width = int(page.rect.width * scale)
    height = int(page.rect.height * scale)
    return width, height


def _trim_whitespace(
    image: Image.Image,
    *,
    padding: int = DEFAULT_TRIM_PADDING,
) -> Tuple[Image.Image, Tuple[int, int]]:
    """
    Trim whitespace margins from an image.
    
    Detects content by finding non-white pixels and crops to 
    the content bounds with specified padding.
    
    Args:
        image: Grayscale PIL Image.
        padding: Pixels of padding to preserve around content.
        
    Returns:
        Tuple of (cropped_image, (left_offset, top_offset)).
        Offsets are useful for translating coordinates from
        original to cropped image space.
    """
    arr = np.array(image)
    if arr.ndim != 2:
        return image, (0, 0)
    
    # Calculate threshold for "white" detection
    thr = max(
        IMAGE_THRESHOLDS.min_white_threshold,
        int(np.percentile(arr, TRIM_PERCENTILE))
    )
    mask = arr < thr
    
    if not mask.any():
        return image, (0, 0)
    
    # Find content bounds
    ys, xs = np.where(mask)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    
    # Dynamic padding based on image size
    dyn = max(padding, image.width // IMAGE_THRESHOLDS.dynamic_trim_divisor)
    
    left = max(0, x0 - dyn)
    right = min(image.width, x1 + dyn)
    top = max(0, y0 - dyn)
    bottom = min(image.height, y1 + dyn)
    
    # Ensure minimum width
    if right - left < image.width * LAYOUT_THRESHOLDS.min_crop_width_ratio:
        left = 0
        right = image.width
    
    cropped = image.crop((left, top, right, bottom))
    return cropped, (left, top)
