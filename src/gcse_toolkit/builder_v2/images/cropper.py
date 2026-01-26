"""
Module: builder_v2.images.cropper

Purpose:
    Utilities for cropping slices from composite images.
    Provides efficient cropping with bounds validation.

Key Functions:
    - crop_slice(): Crop single region from composite
    - crop_multiple(): Crop multiple regions efficiently

Dependencies:
    - PIL: Image manipulation
    - gcse_toolkit.core.models.bounds: SliceBounds

Used By:
    - builder_v2.images.provider: CompositeImageProvider
    - builder_v2.layout: Page composition
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from PIL import Image

from gcse_toolkit.core.models import SliceBounds

# Constants
# Padding added below mark boxes in layout (not stored in detection bounds)
MARK_BOX_CLEARANCE_PX = 10



def crop_slice(
    composite: Image.Image,
    bounds: SliceBounds,
    *,
    add_mark_clearance: bool = False,
) -> Image.Image:
    """
    Crop a slice from a composite image.
    
    Args:
        composite: Source composite image
        bounds: Region to crop (top, bottom, left, right)
        add_mark_clearance: If True, add MARK_BOX_CLEARANCE_PX pixels below the slice
        
    Returns:
        Cropped image (new copy, not a view)
        
    Raises:
        ValueError: If bounds outside image dimensions
        
    Example:
        >>> slice_img = crop_slice(composite, SliceBounds(100, 200))
        >>> slice_img.height
        100
    """
    # Validate bounds
    if bounds.top < 0:
        raise ValueError(f"Bounds top {bounds.top} is negative")
    
    # Determine bottom edge - add clearance if requested
    bottom = bounds.bottom
    if add_mark_clearance:
        bottom = min(bottom + MARK_BOX_CLEARANCE_PX, composite.height)
    
    if bottom > composite.height:
        raise ValueError(
            f"Bounds bottom {bottom} exceeds image height {composite.height}"
        )
    if bounds.left < 0:
        raise ValueError(f"Bounds left {bounds.left} is negative")
    
    # Determine right edge
    right = bounds.right if bounds.right else composite.width
    if right > composite.width:
        raise ValueError(
            f"Bounds right {right} exceeds image width {composite.width}"
        )
    
    # Perform crop
    box = (bounds.left, bounds.top, right, bottom)
    return composite.crop(box)


def crop_multiple(
    composite: Image.Image,
    labels_and_bounds: List[Tuple[str, SliceBounds]],
) -> Dict[str, Image.Image]:
    """
    Crop multiple slices efficiently.
    
    Opens composite once and crops all regions.
    More efficient than calling crop_slice multiple times
    for large numbers of slices.
    
    Args:
        composite: Source composite image
        labels_and_bounds: List of (label, bounds) tuples
        
    Returns:
        Dict mapping label to cropped image
        
    Raises:
        ValueError: If any bounds outside image
        
    Example:
        >>> slices = crop_multiple(composite, [("1(a)", bounds_a), ("1(b)", bounds_b)])
        >>> slices["1(a)"].height
        100
    """
    result = {}
    for label, bounds in labels_and_bounds:
        result[label] = crop_slice(composite, bounds)
    return result


def crop_part_tree(
    composite: Image.Image,
    root_bounds: Dict[str, SliceBounds],
    labels: List[str],
) -> Dict[str, Image.Image]:
    """
    Crop slices for specific parts from a bounds dictionary.
    
    Filters bounds to only requested labels and crops.
    
    Args:
        composite: Source composite image
        root_bounds: Full dict of label -> SliceBounds
        labels: Labels to crop
        
    Returns:
        Dict mapping label to cropped image
        
    Raises:
        KeyError: If label not found in bounds
        
    Example:
        >>> slices = crop_part_tree(composite, all_bounds, ["1(a)", "1(b)"])
    """
    labels_and_bounds = []
    for label in labels:
        if label not in root_bounds:
            raise KeyError(f"Label not found in bounds: {label}")
        labels_and_bounds.append((label, root_bounds[label]))
    
    return crop_multiple(composite, labels_and_bounds)
