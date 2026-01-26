"""
Module: builder_v2.output.markscheme

Purpose:
    Generate markscheme PDF summarizing selected questions and marks.

Key Functions:
    - render_markscheme(): Create markscheme PDF

Dependencies:
    - reportlab: PDF generation
    - gcse_toolkit.core.models.selection: SelectionResult
"""

from __future__ import annotations

import logging
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

from gcse_toolkit.core.models.selection import SelectionResult

logger = logging.getLogger(__name__)

# Constants
A4_WIDTH, A4_HEIGHT = A4
MARGIN = 50
LINE_HEIGHT = 18


def render_markscheme(
    result: SelectionResult,
    output_path: Path,
    cache_path: Path,
) -> None:
    """
    Compile markscheme PDF from extracted MS pages.
    
    For each selected question, loads its markscheme image(s)
    and adds them to the PDF in order.
    
    Phase 6.8: Uses markscheme_page_*.png format from extraction.
    
    Args:
        result: Selection result with selected questions
        output_path: Path to write markscheme PDF
        cache_path: Path to extraction cache (to find MS images)
        
    Returns:
        None
        
    Example:
        >>> render_markscheme(selection, Path("output/markscheme.pdf"), cache_path)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    c = canvas.Canvas(str(output_path), pagesize=A4)
    a4_width, a4_height = A4
    
    total_pages = 0
    
    for plan in result.plans:
        question = plan.question
        question_dir = question.composite_path.parent
        
        # Check for markscheme image path in metadata
        if not question.mark_scheme_path:
            logger.debug(f"No markscheme path registered for {question.id}")
            continue
            
        ms_page_path = question_dir / question.mark_scheme_path
        if not ms_page_path.exists():
            logger.warning(f"Markscheme image missing for {question.id}: {ms_page_path}")
            continue
            
        # Add each MS page
        # (Assuming single image for now as per V2 schema, but logic remains extensible)
        ms_pages = [ms_page_path]
        
        # Add each MS page
        for ms_page_path in ms_pages:
            try:
                # Load image
                from PIL import Image
                img = Image.open(ms_page_path)
                
                # Calculate scaling to fit A4
                img_width, img_height = img.size
                scale_width = a4_width / img_width
                scale_height = a4_height / img_height
                scale = min(scale_width, scale_height)
                
                final_width = img_width * scale
                final_height = img_height * scale
                
                # Center on page
                x = (a4_width - final_width) / 2
                y = (a4_height - final_height) / 2
                
                # Draw image
                from reportlab.lib.utils import ImageReader
                c.drawImage(
                    ImageReader(img),
                    x, y,
                    width=final_width,
                    height=final_height,
                    preserveAspectRatio=True,
                )
                
                c.showPage()
                total_pages += 1
                
            except Exception as e:
                logger.error(f"Failed to add markscheme page {ms_page_path.name}: {e}")
    
    if total_pages == 0:
        logger.warning("No markscheme pages found for any questions")
        # Create blank page to avoid empty PDF
        c.showPage()
    
    c.save()
    logger.info(f"Compiled markscheme with {total_pages} pages to {output_path}")
