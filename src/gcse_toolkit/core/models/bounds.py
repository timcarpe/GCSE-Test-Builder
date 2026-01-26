"""
Module: bounds

Purpose:
    Provides the SliceBounds dataclass - defines pixel regions within
    composite images for cropping question parts. Replaces scattered
    top/bottom/mark_bottom fields from V1's SpanNode.

Key Functions:
    - SliceBounds.crop_from(image): Crop this region from a PIL image
    - SliceBounds.contains(y): Check if y-coordinate is in region
    - SliceBounds.overlaps(other): Check for overlap with another region
    - SliceBounds.to_dict(): Serialize for JSON
    - SliceBounds.from_dict(data): Deserialize from JSON

Dependencies:
    - dataclasses (std)
    - typing (std)
    - PIL.Image (TYPE_CHECKING only)

Used By:
    - core.models.parts.Part
    - core.models.questions.Question
    - core.utils.serialization
    - extractor_v2 (future)
    - builder_v2 (future)

Design Deviation from V1:
    V1 stored bounds in SpanNode with mark_bottom complexity.
    V2 uses clean SliceBounds with validation.
    See: docs/architecture/bugs.md (B4, B5)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from PIL import Image


@dataclass(frozen=True, slots=True)
class SliceBounds:
    """
    Image region specification in pixels.
    
    Defines where a part exists within a composite image.
    Coordinates are relative to the composite image origin (0, 0).
    
    The region is defined as [top, bottom) x [left, right):
    - top is inclusive (first row included)
    - bottom is exclusive (first row NOT included)
    - left is inclusive
    - right is exclusive (or None for full width)
    
    Attributes:
        top: Y-coordinate of top edge (inclusive, pixels from image top)
        bottom: Y-coordinate of bottom edge (exclusive)
        left: X-coordinate of left edge (default: 0)
        right: X-coordinate of right edge (None = full width)
        child_is_inline: Whether this part is a child inline with its parent (default: False)
    
    Invariants:
        - top >= 0
        - bottom > top
        - left >= 0  
        - right is None or right > left
    
    Example:
        >>> bounds = SliceBounds(top=100, bottom=300)
        >>> bounds.height
        200
        >>> bounds.contains(150)
        True
        >>> bounds.contains(300)  # bottom is exclusive
        False
    """
    
    top: int
    bottom: int
    left: int = 0
    right: Optional[int] = None  # None means full width
    child_is_inline: bool = False
    
    def __post_init__(self) -> None:
        """Validate bounds on construction."""
        if self.top < 0:
            raise ValueError(f"top must be >= 0: {self.top}")
        if self.bottom <= self.top:
            raise ValueError(f"bottom must be > top: {self.bottom} <= {self.top}")
        if self.left < 0:
            raise ValueError(f"left must be >= 0: {self.left}")
        if self.right is not None and self.right <= self.left:
            raise ValueError(f"right must be > left: {self.right} <= {self.left}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────────────────
    
    @property
    def height(self) -> int:
        """Height of the region in pixels."""
        return self.bottom - self.top
    
    @property
    def width(self) -> Optional[int]:
        """
        Width of the region in pixels, or None if full width.
        
        Returns None when right is None (meaning full image width).
        """
        if self.right is None:
            return None
        return self.right - self.left
    
    # ─────────────────────────────────────────────────────────────────────────
    # Query Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def contains(self, y: int) -> bool:
        """
        Check if a y-coordinate is within this region.
        
        Args:
            y: Y-coordinate to check
            
        Returns:
            True if top <= y < bottom
        """
        return self.top <= y < self.bottom
    
    def overlaps(self, other: SliceBounds) -> bool:
        """
        Check if this region overlaps with another.
        
        Two regions overlap if they share at least one pixel row.
        Adjacent regions (one.bottom == other.top) do NOT overlap.
        
        Args:
            other: Another SliceBounds to check against
            
        Returns:
            True if regions overlap
        """
        return not (self.bottom <= other.top or other.bottom <= self.top)
    
    def is_above(self, other: SliceBounds) -> bool:
        """
        Check if this region is entirely above another.
        
        Args:
            other: Another SliceBounds to compare
            
        Returns:
            True if self.bottom <= other.top
        """
        return self.bottom <= other.top
    
    # ─────────────────────────────────────────────────────────────────────────
    # Image Operations
    # ─────────────────────────────────────────────────────────────────────────
    
    def crop_from(self, image: Image.Image) -> Image.Image:
        """
        Crop this region from an image.
        
        Args:
            image: PIL Image to crop from
            
        Returns:
            New PIL Image containing just this region
        """
        right = self.right if self.right is not None else image.width
        return image.crop((self.left, self.top, right, self.bottom))
    
    def as_tuple(self) -> tuple[int, int, int, int]:
        """
        Get as (left, top, right, bottom) tuple for PIL.
        
        Note: right will be the actual value, use with image.width for None.
        
        Returns:
            Tuple suitable for PIL crop (after handling None right)
        """
        return (self.left, self.top, self.right or 0, self.bottom)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Serialization
    # ─────────────────────────────────────────────────────────────────────────
    
    def to_dict(self) -> dict:
        """
        Serialize to dictionary for JSON storage.
        
        Returns:
            Dict with top, bottom, and optionally left, right
        """
        d = {"top": self.top, "bottom": self.bottom}
        if self.left != 0:
            d["left"] = self.left
        if self.right is not None:
            d["right"] = self.right
        if self.child_is_inline:
            d["child_is_inline"] = True
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> SliceBounds:
        """
        Deserialize from dictionary.
        
        Args:
            data: Dict with top, bottom, optionally left, right
            
        Returns:
            SliceBounds instance
        """
        return cls(
            top=data["top"],
            bottom=data["bottom"],
            left=data.get("left", 0),
            right=data.get("right"),
            child_is_inline=data.get("child_is_inline", False),
        )
    
    def __repr__(self) -> str:
        """Concise representation for debugging."""
        if self.left == 0 and self.right is None:
            return f"SliceBounds({self.top}, {self.bottom})"
        return f"SliceBounds({self.top}, {self.bottom}, {self.left}, {self.right})"
