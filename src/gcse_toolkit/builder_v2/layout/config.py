"""
Module: builder_v2.layout.config

Purpose:
    Configuration for page layout engine.
    Defines page dimensions, margins, and rendering settings.

Key Classes:
    - LayoutConfig: Immutable layout configuration

Dependencies:
    - dataclasses (std)

Used By:
    - builder_v2.layout.composer: Asset composition
    - builder_v2.layout.paginator: Page arrangement
"""

from __future__ import annotations

from dataclasses import dataclass


# Standard A4 page dimensions at 200 DPI
DEFAULT_PAGE_WIDTH_PX = 1654
DEFAULT_PAGE_HEIGHT_PX = 2339
DEFAULT_DPI = 200


@dataclass(frozen=True)
class LayoutConfig:
    """
    Configuration for page layout (immutable).
    
    Controls page dimensions, margins, and rendering behavior.
    
    Attributes:
        page_width: Page width in pixels
        page_height: Page height in pixels
        dpi: Dots per inch for rendering
        margin_top: Top margin in pixels
        margin_bottom: Bottom margin in pixels
        margin_left: Left margin in pixels
        margin_right: Right margin in pixels
        inter_question_spacing: Vertical spacing between questions (px)
        inter_part_spacing: Vertical spacing between parts (px)
        scale_to_fit: Whether to scale oversized slices
        
    Example:
        >>> config = LayoutConfig()
        >>> config.available_height
        2239  # page_height - margins
    """
    
    # Page dimensions
    page_width: int = DEFAULT_PAGE_WIDTH_PX
    page_height: int = DEFAULT_PAGE_HEIGHT_PX
    dpi: int = DEFAULT_DPI
    
    # Margins
    margin_top: int = 40
    margin_bottom: int = 40
    margin_left: int = 50
    margin_right: int = 50
    
    # Spacing
    inter_question_spacing: int = 40
    inter_part_spacing: int = 20
    context_child_spacing: int = 20
    
    # Behavior
    scale_to_fit: bool = False  # No scaling - preserve original dimensions
    
    def __post_init__(self) -> None:
        """Validate configuration on construction."""
        if self.page_width <= 0:
            raise ValueError(f"page_width must be positive: {self.page_width}")
        if self.page_height <= 0:
            raise ValueError(f"page_height must be positive: {self.page_height}")
        if self.available_width <= 0:
            raise ValueError("Margins exceed page width")
        if self.available_height <= 0:
            raise ValueError("Margins exceed page height")
    
    @property
    def available_width(self) -> int:
        """Width available for content (excluding margins)."""
        return self.page_width - self.margin_left - self.margin_right
    
    @property
    def available_height(self) -> int:
        """Height available for content (excluding margins)."""
        return self.page_height - self.margin_top - self.margin_bottom
