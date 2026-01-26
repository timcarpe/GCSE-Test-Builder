"""Bounding box conversion utilities for PDF coordinate systems.

Provides shared functions for converting PDF bounding boxes to pixel coordinates,
accounting for scaling, clipping, trimming, and offsets.
"""

from __future__ import annotations

from typing import List, Tuple

import fitz  # type: ignore


def bbox_to_pixels(
    bbox: Tuple[float, float, float, float],
    clip: fitz.Rect,
    scale: float,
    trim_offset: Tuple[int, int],
    offset_y: int = 0,
) -> List[int]:
    """Convert PDF bounding box coordinates to pixel coordinates.
    
    Takes a PDF bounding box (in PDF coordinate system) and converts it to
    pixel coordinates, accounting for clipping region, DPI scaling, whitespace
    trimming offsets, and vertical offsets for stitched multi-page images.
    
    Args:
        bbox: PDF bounding box as (x0, y0, x1, y1) in PDF coordinates.
        clip: Clipping rectangle that defines the extracted region.
        scale: Scale factor from PDF to pixel coordinates (typically DPI/72.0).
        trim_offset: Whitespace trim offset as (offset_x, offset_y) in pixels.
        offset_y: Additional vertical offset for multi-page stitching (default: 0).
        
    Returns:
        List of pixel coordinates [px0, py0, px1, py1] ensuring px1 > px0 and py1 > py0.
        
    Example:
        >>> bbox = (100.0, 200.0, 150.0, 220.0)
        >>> clip = fitz.Rect(0, 0, 595, 842)
        >>> scale = 180.0 / 72.0  # 180 DPI
        >>> trim_offset = (5, 10)
        >>> bbox_to_pixels(bbox, clip, scale, trim_offset)
        [245, 490, 370, 540]
    """
    x0, y0, x1, y1 = bbox
    trim_x, trim_y = trim_offset
    
    # Convert PDF coordinates to pixel coordinates relative to clip
    px0 = int(round((x0 - clip.x0) * scale)) - trim_x
    py0 = int(round((y0 - clip.y0) * scale)) - trim_y + offset_y
    px1 = int(round((x1 - clip.x0) * scale)) - trim_x
    py1 = int(round((y1 - clip.y0) * scale)) - trim_y + offset_y
    
    # Ensure valid bounding box (x1 > x0, y1 > y0)
    if px1 <= px0:
        px1 = px0 + 1
    if py1 <= py0:
        py1 = py0 + 1
        
    return [px0, py0, px1, py1]
