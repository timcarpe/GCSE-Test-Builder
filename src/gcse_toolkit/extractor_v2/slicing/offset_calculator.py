"""
Module: extractor_v2.slicing.offset_calculator

Purpose:
    Provides helper functions for calculating and applying horizontal
    offset normalization. Used to handle page margin shifts in multi-page
    questions where left/right pages have different inner margins.

Key Functions:
    - calculate_part_shift(): Calculate shift for a single part
    - normalize_horizontal_bounds(): Apply shift to left/right bounds

Dependencies:
    None (pure functions)

Used By:
    - extractor_v2.slicing.bounds_calculator: Normalizes bounds per-part

Design Notes:
    Per-part offset detection ensures correct normalization even when
    questions span 3+ pages with alternating left/right margin shifts.
    Each part's label position is compared to a global reference.
"""

from __future__ import annotations

from typing import Tuple


def calculate_part_shift(
    reference_x: int,
    part_label_x: int,
) -> int:
    """
    Calculate horizontal shift for a part relative to reference.
    
    Compares the part's label X position to a global reference point
    (typically the first question's numeral in the PDF batch).
    
    Args:
        reference_x: X position of reference label (first question numeral).
        part_label_x: X position of this part's label.
        
    Returns:
        Shift in pixels. Positive = part is shifted right of reference.
        Negative = part is shifted left of reference. Zero = aligned.
        
    Example:
        >>> reference = 50  # First question's numeral at x=50
        >>> current = 70    # This part's label at x=70
        >>> calculate_part_shift(reference, current)
        20  # Part is shifted 20px right, need to subtract to normalize
        
        >>> calculate_part_shift(50, 30)
        -20  # Part is shifted 20px left, need to add to normalize
    """
    return part_label_x - reference_x


def normalize_horizontal_bounds(
    left: int,
    right: int,
    shift: int,
) -> Tuple[int, int]:
    """
    Apply horizontal shift to normalize bounds to reference position.
    
    Subtracts the shift from both left and right to bring the bounds
    back to the reference coordinate system.
    
    Args:
        left: Original left boundary in pixels.
        right: Original right boundary in pixels.
        shift: Shift value from calculate_part_shift().
        
    Returns:
        Tuple of (normalized_left, normalized_right).
        Values are clamped to minimum of 0.
        
    Example:
        >>> # Part on right page (shifted +20)
        >>> normalize_horizontal_bounds(left=70, right=720, shift=20)
        (50, 700)  # Normalized back to reference position
        
        >>> # Part on left page (shifted -10)
        >>> normalize_horizontal_bounds(left=40, right=690, shift=-10)
        (50, 700)  # Normalized back to reference position
    """
    return (
        max(0, left - shift),
        max(0, right - shift),
    )


def get_reference_x_from_numeral(
    numeral_bbox: Tuple[int, int, int, int],
) -> int:
    """
    Extract reference X coordinate from numeral bounding box.
    
    Args:
        numeral_bbox: (left, top, right, bottom) of question numeral.
        
    Returns:
        Left edge of numeral as reference X.
        
    Example:
        >>> get_reference_x_from_numeral((50, 10, 70, 30))
        50
    """
    return numeral_bbox[0]


def get_part_label_x(
    label_bbox: Tuple[int, int, int, int],
) -> int:
    """
    Extract label X coordinate from part label bounding box.
    
    Args:
        label_bbox: (left, top, right, bottom) of part label.
        
    Returns:
        Left edge of label as part X.
        
    Example:
        >>> get_part_label_x((60, 100, 80, 120))
        60
    """
    return label_bbox[0]
