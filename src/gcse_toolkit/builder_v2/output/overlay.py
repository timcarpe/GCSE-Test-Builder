"""
Module: builder_v2.output.overlay

Purpose:
    Apply question number overlays to slice images.
    Draws a white box over the original number and renders
    the new number in its place.

Key Functions:
    - apply_overlay(): Add number overlay to image
    - calculate_overlay_position(): Calculate centered text position

Dependencies:
    - PIL: Image drawing

Used By:
    - builder_v2.layout.composer: When composing assets
    - builder_v2.output.renderer: During PDF rendering
"""

from __future__ import annotations

import logging
from typing import Tuple, Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_FONT_SIZE = 48
DEFAULT_BOX_COLOR = "white"
DEFAULT_TEXT_COLOR = "black"


def apply_overlay(
    image: Image.Image,
    new_number: str,
    bbox: Tuple[int, int, int, int],
    *,
    font_size: int = DEFAULT_FONT_SIZE,
    background_color: str = DEFAULT_BOX_COLOR,
    text_color: str = DEFAULT_TEXT_COLOR,
) -> Image.Image:
    """
    Apply question number overlay to image.
    
    Creates a copy of the image, draws a white rectangle over
    the original number position, and renders the new number.
    
    Args:
        image: Source image (will be copied, not modified)
        new_number: New question number to display
        bbox: Bounding box (x1, y1, x2, y2) to overlay
        font_size: Font size for number text
        background_color: Background color for number box
        text_color: Text color for number
        
    Returns:
        New image with overlay applied
        
    Example:
        >>> overlaid = apply_overlay(img, "5", (10, 10, 60, 60))
        >>> overlaid.size == img.size
        True
    """
    # Copy to avoid mutating original (immutability principle)
    result = image.copy()
    draw = ImageDraw.Draw(result)
    
    x1, y1, x2, y2 = bbox
    
    # Draw background rectangle (cover original number)
    draw.rectangle(bbox, fill=background_color)
    
    # Load font
    font = _load_font(font_size)
    
    # Calculate text position (centered in bbox)
    text_x, text_y = calculate_center_position(bbox, new_number, font, draw)
    
    # Draw new number
    draw.text(
        (text_x, text_y),
        new_number,
        fill=text_color,
        font=font,
    )
    
    logger.debug(f"Applied overlay '{new_number}' at bbox {bbox}")
    
    return result


def calculate_center_position(
    bbox: Tuple[int, int, int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    draw: ImageDraw.ImageDraw,
) -> Tuple[int, int]:
    """
    Calculate position to center text in bounding box.
    
    Args:
        bbox: Bounding box (x1, y1, x2, y2)
        text: Text to center
        font: Font to use for sizing
        draw: ImageDraw object for text metrics
        
    Returns:
        (x, y) position for top-left of text
    """
    x1, y1, x2, y2 = bbox
    box_width = x2 - x1
    box_height = y2 - y1
    
    # Get text bounding box
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # Calculate centered position
    text_x = x1 + (box_width - text_width) // 2
    text_y = y1 + (box_height - text_height) // 2
    
    return text_x, text_y


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """
    Load a bold font for text rendering.
    
    Prefers bold variants for question number overlays.
    Falls back to default font if not available.
    
    Args:
        size: Font size
        
    Returns:
        Font object
    """
    # Try bold fonts first for prominence
    font_options = [
        "arialbd.ttf",      # Arial Bold (Windows)
        "Arial Bold.ttf",   # Arial Bold (Mac)
        "DejaVuSans-Bold.ttf",  # DejaVu Sans Bold
        "arial.ttf",        # Arial regular fallback
        "Arial.ttf",
        "DejaVuSans.ttf",
    ]
    
    for font_name in font_options:
        try:
            return ImageFont.truetype(font_name, size)
        except (IOError, OSError):
            continue
    
    logger.warning("Could not load TrueType font, using default")
    return ImageFont.load_default()
