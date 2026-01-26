"""
Module: builder_v2.layout.models

Purpose:
    Data models for page layout.
    Immutable dataclasses representing slices, placements, and pages.

Key Classes:
    - SliceAsset: Renderable image for a part
    - SlicePlacement: Asset positioned on a page
    - PagePlan: Complete page layout
    - LayoutResult: Final layout output

Dependencies:
    - PIL: Image type
    - dataclasses (std)

Used By:
    - builder_v2.layout.composer: Creates SliceAssets
    - builder_v2.layout.paginator: Creates PagePlans
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from PIL import Image


@dataclass(frozen=True)
class SliceAsset:
    """
    Slice asset for rendering (immutable).
    
    Represents either:
    - An image slice from a question part
    - A text header (when is_text_header=True)
    
    Attributes:
        question_id: Question identifier
        part_label: Part label or "__header__" for text headers
        image: PIL Image object (None for text headers)
        width: Width in pixels
        height: Height in pixels
        marks: Marks value
        sequential_number: Sequential question number for rendering
        numeral_bbox: Question number bounding box for repositioning
        is_text_header: If True, render as text box instead of image
        header_text: Text to display (only for text headers)
    """
    question_id: str
    part_label: str
    image: Optional[Image.Image]
    width: int
    height: int
    marks: int
    sequential_number: Optional[int] = None
    numeral_bbox: Optional[Tuple[int, int, int, int]] = None
    is_text_header: bool = False
    header_text: Optional[str] = None
    horizontal_offset: int = 0  # Phase 6.10: Offset from reference for render-time alignment
    label_alignment_offset: Optional[int] = None  # Offset for aligning label with question number box
    root_width: Optional[int] = None  # Width of question root slice for centering calculation
    numeral_offset_x: Optional[int] = None  # Relative X offset of question number box within root slice


@dataclass(frozen=True)
class SlicePlacement:
    """
    An asset positioned on a page.
    
    Attributes:
        asset: The SliceAsset to place
        top: Y offset from page top (in pixels)
        
    Example:
        >>> placement = SlicePlacement(asset, top=100)
        >>> placement.bottom
        300  # top + asset.height
    """
    
    asset: SliceAsset
    top: int
    
    @property
    def bottom(self) -> int:
        """Bottom Y coordinate (top + height)."""
        return self.top + self.asset.height


@dataclass(frozen=True)
class PagePlan:
    """
    Complete layout plan for a single page.
    
    Attributes:
        index: Page number (0-indexed)
        placements: Tuple of SlicePlacements on this page
        height_used: Total vertical space used
        
    Example:
        >>> page = PagePlan(index=0, placements=(p1, p2), height_used=500)
        >>> len(page.placements)
        2
    """
    
    index: int
    placements: tuple[SlicePlacement, ...]
    height_used: int
    
    @property
    def placement_count(self) -> int:
        """Number of assets on this page."""
        return len(self.placements)
    
    @property
    def is_empty(self) -> bool:
        """Check if page has no placements."""
        return len(self.placements) == 0


@dataclass(frozen=True)
class LayoutResult:
    """
    Final layout output with diagnostics.
    
    Attributes:
        pages: Tuple of PagePlans
        warnings: List of warning messages
        question_page_map: Mapping of question_id to page indices
        
    Example:
        >>> result = LayoutResult(pages=(page1, page2), warnings=[])
        >>> result.page_count
        2
    """
    
    pages: tuple[PagePlan, ...]
    warnings: list[str] = field(default_factory=list)
    question_page_map: dict[str, list[int]] = field(default_factory=dict)
    
    @property
    def page_count(self) -> int:
        """Number of pages in layout."""
        return len(self.pages)
    
    @property
    def total_placements(self) -> int:
        """Total number of asset placements across all pages."""
        return sum(p.placement_count for p in self.pages)
