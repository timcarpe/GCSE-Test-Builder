"""
Module: extractor_v2.utils.visualizer

Purpose:
    Debug visualization for extraction pipeline. Draws bounding boxes
    around detected elements (numerals, letters, romans, marks) to help
    diagnose detection issues.

Key Functions:
    - visualize_detections(): Create debug composite with all overlays
    - save_debug_composite(): Save visualization to disk

Dependencies:
    - PIL: Image drawing
    - extractor_v2.detection: Detection dataclasses

Used By:
    - extractor_v2.slicing.writer: Optional debug output
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from ..detection.numerals import QuestionNumeral
from ..detection.parts import PartLabel
from ..detection.marks import MarkBox

logger = logging.getLogger(__name__)

# Visualization constants
COLORS = {
    "numeral": (255, 0, 0, 180),      # Red - Question numbers
    "letter": (0, 0, 255, 180),       # Blue - (a), (b), (c)
    "roman": (0, 255, 0, 180),        # Green - (i), (ii), (iii)
    "mark": (255, 165, 0, 180),       # Orange - [N] marks
}

LABEL_BG_COLOR = (0, 0, 0, 200)      # Black background for labels
LABEL_TEXT_COLOR = (255, 255, 255)    # White text
BOX_LINE_WIDTH = 3
FONT_SIZE = 16


def visualize_detections(
    composite: Image.Image,
    numeral: Optional[QuestionNumeral],
    letters: List[PartLabel],
    romans: List[PartLabel],
    marks: List[MarkBox],
    numeral_bbox: Optional[Tuple[int, int, int, int]] = None,
) -> Image.Image:
    """
    Create debug visualization with bounding boxes around all detections.
    
    Draws colored boxes around detected elements:
    - Red: Question numeral
    - Blue: Letter parts (a), (b), (c)
    - Green: Roman numeral parts (i), (ii), (iii)
    - Orange: Mark boxes [N]
    
    Each box is labeled with the detected text and Y-position.
    
    Args:
        composite: Source composite image
        numeral: Detected question numeral (optional)
        letters: List of detected letter parts
        romans: List of detected roman parts
        marks: List of detected mark boxes
        numeral_bbox: Optional bbox in composite coords for root numeral
        
    Returns:
        New image with debug overlays (original unchanged)
        
    Example:
        >>> debug_img = visualize_detections(composite, numeral, letters, romans, marks)
        >>> debug_img.save("debug_composite.png")
    """
    # Create copy with alpha channel for transparency
    debug_img = composite.convert("RGBA")
    
    # Create overlay layer for semi-transparent boxes
    overlay = Image.new("RGBA", debug_img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Try to load font for labels
    try:
        font = ImageFont.truetype("Arial.ttf", FONT_SIZE)
    except (IOError, OSError):
        font = ImageFont.load_default()
    
    # Draw numeral bbox if provided
    if numeral_bbox and numeral:
        _draw_detection_box(
            draw,
            numeral_bbox,
            f"Q{numeral.number}",
            COLORS["numeral"],
            font,
        )
    
    # Draw letter boxes
    for letter in letters:
        _draw_detection_box(
            draw,
            letter.bbox,
            f"({letter.label}) Y={letter.y_position}",
            COLORS["letter"],
            font,
        )
    
    # Draw roman boxes
    for roman in romans:
        _draw_detection_box(
            draw,
            roman.bbox,
            f"({roman.label}) Y={roman.y_position}",
            COLORS["roman"],
            font,
        )
    
    # Draw mark boxes
    for mark in marks:
        _draw_detection_box(
            draw,
            mark.bbox,
            f"[{mark.value}] Y={mark.y_position}",
            COLORS["mark"],
            font,
        )
    
    # Composite overlay onto debug image
    debug_img = Image.alpha_composite(debug_img, overlay)
    
    # Convert back to RGB for saving
    return debug_img.convert("RGB")


def _draw_detection_box(
    draw: ImageDraw.ImageDraw,
    bbox: Tuple[int, int, int, int],
    label_text: str,
    color: Tuple[int, int, int, int],
    font: ImageFont.FreeTypeFont,
) -> None:
    """
    Draw a single detection box with label.
    
    Args:
        draw: ImageDraw object
        bbox: (left, top, right, bottom) in pixels
        label_text: Text to display above box
        color: RGBA color tuple for box
        font: Font for label text
    """
    x0, y0, x1, y1 = bbox
    
    # Draw semi-transparent rectangle
    draw.rectangle(bbox, outline=color, width=BOX_LINE_WIDTH)
    
    # Draw label background
    # Get text size
    text_bbox = draw.textbbox((0, 0), label_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # Position label above box (or below if at top edge)
    label_x = x0
    label_y = y0 - text_height - 4
    if label_y < 0:
        label_y = y1 + 2  # Place below box if at top
    
    # Draw label background
    label_bg_bbox = (
        label_x,
        label_y,
        label_x + text_width + 4,
        label_y + text_height + 4,
    )
    draw.rectangle(label_bg_bbox, fill=LABEL_BG_COLOR)
    
    # Draw label text
    draw.text(
        (label_x + 2, label_y + 2),
        label_text,
        fill=LABEL_TEXT_COLOR,
        font=font,
    )


def save_debug_composite(
    composite: Image.Image,
    output_dir: Path,
    question_id: str,
    numeral: Optional[QuestionNumeral],
    letters: List[PartLabel],
    romans: List[PartLabel],
    marks: List[MarkBox],
    numeral_bbox: Optional[Tuple[int, int, int, int]] = None,
) -> Path:
    """
    Create and save debug visualization composite.
    
    Args:
        composite: Source composite image
        output_dir: Directory to save debug image
        question_id: Question identifier for filename
        numeral: Detected question numeral
        letters: Detected letter parts
        romans: Detected roman parts
        marks: Detected mark boxes
        numeral_bbox: Optional bbox for root numeral
        
    Returns:
        Path to saved debug image
        
    Example:
        >>> path = save_debug_composite(
        ...     composite, output_dir, "q1", numeral, letters, romans, marks
        ... )
        >>> print(f"Debug image saved: {path}")
    """
    debug_img = visualize_detections(
        composite=composite,
        numeral=numeral,
        letters=letters,
        romans=romans,
        marks=marks,
        numeral_bbox=numeral_bbox,
    )
    
    # Save with debug suffix
    output_dir.mkdir(parents=True, exist_ok=True)
    debug_path = output_dir / f"{question_id}_debug_composite.png"
    debug_img.save(debug_path, "PNG")
    
    logger.info(
        f"Saved debug composite for {question_id}: "
        f"{len(letters)} letters, {len(romans)} romans, {len(marks)} marks"
    )
    
    return debug_path
