"""
Module: builder_v2.output.renderer

Purpose:
    Render LayoutResult to PDF using ReportLab.
    Each PagePlan becomes one PDF page with images placed at
    their specified positions.

Key Functions:
    - render_to_pdf(): Main rendering function

Dependencies:
    - reportlab: PDF generation
    - PIL: Image handling
    - builder_v2.layout.models: LayoutResult, PagePlan

Used By:
    - builder_v2.controller: Pipeline orchestration
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from gcse_toolkit.builder_v2.layout.models import LayoutResult, PagePlan, SlicePlacement

logger = logging.getLogger(__name__)

# Constants
A4_WIDTH_PT, A4_HEIGHT_PT = A4
DEFAULT_DPI = 300

# Footer configuration
FOOTER_FONT_SIZE = 7  # Matches exam code label size
FOOTER_GITHUB_URL = "https://github.com/timcarpe/GCSE-Test-Builder"
FOOTER_KOFI_URL = "https://ko-fi.com/timcarpe"  # Placeholder - update with actual URL


def _get_footer_text() -> str:
    """Get footer text with current version number."""
    try:
        from gcse_toolkit import __version__
        version = __version__
    except ImportError:
        version = "unknown"
    return f"Generated with GCSE Test Builder v{version}: {FOOTER_GITHUB_URL} | Copyright 2026 Timothy Carpenter Licensed under the Polyform Noncommercial License 1.0.0"


def render_to_pdf(
    layout: LayoutResult,
    output_path: Path,
    *,
    dpi: int = DEFAULT_DPI,
    margin_top_px: int = 40,
    margin_bottom_px: int = 40,
    margin_left_px: int = 0,
    page_width_px: int = 1654,
    page_height_px: int = 2339,
    show_footer: bool = True,
) -> None:
    """
    Render layout result to PDF file.
    
    Converts each PagePlan in the LayoutResult to a PDF page,
    placing slice images at their specified positions.
    
    Args:
        layout: Layout result from paginator
        output_path: Path to write PDF
        dpi: DPI for coordinate conversion (default 300)
        margin_top_px: Top margin in pixels (default 40)
        margin_bottom_px: Bottom margin in pixels (default 40)
        margin_left_px: Left margin in pixels (unused)
        page_width_px: Page width in pixels (default 1654 for A4 @ 200 DPI)
        page_height_px: Page height in pixels (default 2339 for A4 @ 200 DPI)
        
    Returns:
        None
        
    Raises:
        IOError: If PDF cannot be written
        
    Example:
        >>> render_to_pdf(layout, Path("output/questions.pdf"))
    """
    if layout.page_count == 0:
        logger.warning("Empty layout, creating empty PDF")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Calculate page size in points from pixel dimensions
    page_width_pt = _px_to_pt(page_width_px, dpi)
    page_height_pt = _px_to_pt(page_height_px, dpi)
    custom_page_size = (page_width_pt, page_height_pt)
    
    c = canvas.Canvas(str(output_path), pagesize=custom_page_size)
    
    for page in layout.pages:
        _render_page(c, page, dpi, margin_top_px, margin_left_px, page_width_pt, page_height_pt, show_footer)
        c.showPage()
    
    c.save()
    
    logger.info(f"Rendered {layout.page_count} pages to {output_path}")


def _render_page(
    c: canvas.Canvas,
    page: PagePlan,
    dpi: int,
    margin_top_px: int,
    margin_left_px: int,
    page_width_pt: float,
    page_height_pt: float,
    show_footer: bool = True,
) -> None:
    """
    Render a single page to the canvas.
    
    Phase 6.9: Tracks root bounds per question for child alignment.
    
    Args:
        c: ReportLab canvas
        page: Page plan with placements
        dpi: DPI for coordinate conversion
        margin_top_px: Top margin in pixels
        margin_left_px: Left margin in pixels
        page_width_pt: Page width in points
        page_height_pt: Page height in points
    """
    # Phase 6.9: Track root bounds for each question (for child right-alignment)
    # Phase 6.9: Track root bounds for each question (for child right-alignment)
    root_bounds_cache = {}  # question_id -> (left_pt, right_pt)
    
    # Render placements directly (spacing now handled in paginator)
    for i, placement in enumerate(page.placements):
        # Look ahead to find next non-header placement for alignment
        next_placement = None
        if i + 1 < len(page.placements):
            next_placement = page.placements[i + 1]
        
        _draw_slice(
            c, 
            placement, 
            dpi,
            margin_top_px,
            margin_left_px, 
            page_width_pt, 
            page_height_pt,
            root_bounds_cache,
            next_placement,  # Pass next placement for header alignment
        )
    
    # Draw footer at bottom of page (after all content)
    if show_footer:
        _draw_footer(c, page_width_pt, page_height_pt)


def _draw_footer(
    c: canvas.Canvas,
    page_width_pt: float,
    page_height_pt: float,
) -> None:
    """
    Draw centered footer with version and copyright info.
    
    Positioned in bottom margin area, ~15pt from page bottom.
    Uses 7pt Helvetica to match exam code label styling.
    
    Args:
        c: ReportLab canvas
        page_width_pt: Page width in points
        page_height_pt: Page height in points (unused, position is from bottom)
    """
    footer_text = _get_footer_text()
    
    c.saveState()
    c.setFont("Helvetica", FOOTER_FONT_SIZE)
    c.setFillColorRGB(0.4, 0.4, 0.4)  # Subtle gray color
    
    # Position centered, 15pt from bottom of page
    text_width = c.stringWidth(footer_text, "Helvetica", FOOTER_FONT_SIZE)
    x_pt = (page_width_pt - text_width) / 2
    y_pt = 15  # 15pt from bottom
    
    c.drawString(x_pt, y_pt, footer_text)
    c.restoreState()


def _draw_text_header(
    c: canvas.Canvas,
    text: str,
    x_pt: float,
    y_pt: float,
    width_pt: float,
    height_pt: float,
) -> None:
    """
    Draw question ID header as left-aligned text box.
    
    Args:
        c: ReportLab canvas
        text: Header text to display
        x_pt: X position in points (left edge)
        y_pt: Y position in points (bottom-left)
        width_pt: Box width in points
        height_pt: Box height in points
    """
    FONT_SIZE = 7  # 50% smaller than previous 14pt
    
    c.saveState()
    
    # Draw text (left-aligned, vertically centered)
    text_x = x_pt  # Left-align at box left edge
    center_y = y_pt + (height_pt / 2) - (FONT_SIZE / 2)
    
    text_obj = c.beginText()
    text_obj.setTextOrigin(text_x, center_y)
    text_obj.setFont("Helvetica", FONT_SIZE)  # Regular (non-bold)
    text_obj.setFillColorRGB(0, 0, 0)
    text_obj.textLine(text)
    c.drawText(text_obj)
    
    c.restoreState()


def _draw_slice(
    c: canvas.Canvas,
    placement: SlicePlacement,
    dpi: int,
    margin_top_px: int,
    margin_left_px: int,
    page_width_pt: float,
    page_height_pt: float,
    root_bounds_cache: dict,
    next_placement: Optional[SlicePlacement] = None,
) -> None:
    """
    Draw a single slice with smart horizontal positioning.
    
    Handles both image slices and text headers.
    Phase 6.9: Centers root parts, right-aligns children to root boundary.
    
    Args:
        c: ReportLab canvas
        placement: Slice placement with asset and position
        dpi: DPI for coordinate conversion
        margin_top_px: Top margin in pixels
        margin_left_px: Left margin in pixels (unused)
        page_width_pt: Page width for centering calculation
        page_height_pt: Page height for Y coordinate transformation
        root_bounds_cache: Dict tracking root bounds per question
        next_placement: Next placement (for header alignment)
    """
    asset = placement.asset
    
    # Check if this is a text header
    if asset.is_text_header:
        # Phase 2.1: Align label with question number box
        if asset.label_alignment_offset is not None:
            # Calculate where root context starts (centering logic must match root rendering)
            root_width_px = asset.root_width if asset.root_width is not None else 1400
            root_width_pt = _px_to_pt(root_width_px, dpi)
            
            # Center on page
            x_centered = max(0, (page_width_pt - root_width_pt) / 2)
            
            # Apply cross-question normalization offset
            offset_pt = _px_to_pt(asset.label_alignment_offset, dpi)
            root_left_pt = max(0, x_centered - offset_pt)
            
            # Align label with literal question number box left edge
            numeral_offset_pt = _px_to_pt(asset.numeral_offset_x or 0, dpi)
            content_left_pt = root_left_pt + numeral_offset_pt
        else:
            content_left_pt = 10  # Fallback
        
        width_pt = _px_to_pt(asset.width, dpi)
        height_pt = _px_to_pt(asset.height, dpi)
        
        # Calculate Y position
        y_pt = _transform_y(
            page_height_pt=page_height_pt,
            y_px_top=placement.top,
            height_px=asset.height,
            dpi=dpi,
        )
        
        c.saveState()
        # Use calculated position for alignment with qnum box
        _draw_text_header(c, asset.header_text, content_left_pt, y_pt, width_pt, height_pt)
        c.restoreState()
        return  # Done, don't continue to image drawing
    
    # Regular image slice handling
    # Convert PIL image to ReportLab ImageReader
    img_reader = _pil_to_reader(asset.image)
    
    # Convert pixel dimensions to PDF points
    width_pt = _px_to_pt(asset.width, dpi)
    height_pt = _px_to_pt(asset.height, dpi)
    
    # Phase 6.9 + 6.10: Smart horizontal positioning with offset normalization
    question_id = placement.asset.question_id
    is_context = placement.asset.part_label.endswith("_context")
    horizontal_offset = placement.asset.horizontal_offset
    
    if is_context:
        # Root context parts: center on page, then adjust by offset
        x_pt = max(0, (page_width_pt - width_pt) / 2)
        
        # Phase 6.10: Apply horizontal offset for consistent alignment across questions
        # Offset is subtracted to align with reference (first) question
        if horizontal_offset != 0:
            offset_pt = _px_to_pt(horizontal_offset, dpi)
            x_pt = max(0, x_pt - offset_pt)
        
        # Cache root bounds for child alignment
        if question_id not in root_bounds_cache:
            left_pt = x_pt
            right_pt = x_pt + width_pt
            root_bounds_cache[question_id] = (left_pt, right_pt)
    
    elif question_id in root_bounds_cache:
        # Child parts: right-align to root boundary
        _, root_right_pt = root_bounds_cache[question_id]
        x_pt = root_right_pt - width_pt
        
        # Fallback: center if child exceeds root width
        if x_pt < 0:
            logger.debug(
                f"Part {placement.asset.part_label} exceeds root width, "
                f"centering instead"
            )
            x_pt = max(0, (page_width_pt - width_pt) / 2)
    
    else:
        # No root found (shouldn't happen) - center anyway
        x_pt = max(0, (page_width_pt - width_pt) / 2)
    
    # Convert Y coordinate (top-down to bottom-up)
    y_pt = _transform_y(
        page_height_pt=page_height_pt,
        y_px_top=placement.top,
        height_px=placement.asset.height,
        dpi=dpi,
    )
    
    c.drawImage(
        img_reader,
        x_pt,
        y_pt,
        width=width_pt,
        height=height_pt,
        preserveAspectRatio=True,
    )





def _pil_to_reader(img: Image.Image) -> ImageReader:
    """
    Convert PIL image to ReportLab ImageReader.
    
    Args:
        img: PIL Image object
        
    Returns:
        ImageReader for use with ReportLab
    """
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return ImageReader(buf)


def _px_to_pt(px: int, dpi: int = DEFAULT_DPI) -> float:
    """
    Convert pixels to PDF points.
    
    PDF points are 1/72 inch.
    
    Args:
        px: Pixel value
        dpi: Dots per inch
        
    Returns:
        Value in PDF points
    """
    return px * 72.0 / dpi


def _transform_y(
    page_height_pt: float,
    y_px_top: float,
    height_px: float,
    dpi: int = DEFAULT_DPI,
) -> float:
    """
    Convert top-down pixel Y coordinate to bottom-up PDF Y.
    
    Args:
        page_height_pt: Page height in points
        y_px_top: Y position from top in pixels (absolute)
        height_px: Height of element in pixels
        dpi: Dots per inch
        
    Returns:
        Y position from bottom in points
    """
    y_pt_from_top = _px_to_pt(y_px_top, dpi)
    height_pt = _px_to_pt(height_px, dpi)
    return page_height_pt - y_pt_from_top - height_pt
