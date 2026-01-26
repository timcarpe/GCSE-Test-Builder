"""Detection utilities for identifying mark boxes and section labels in PDFs.

Provides functions to detect bracketed marks [N], lettered sections (a), (b), (c),
and roman numeral sub-sections (i), (ii), (iii) from extracted PDF text.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import fitz  # type: ignore

logger = logging.getLogger(__name__)

SECTION_PATTERN = re.compile(r"\(\s*([a-z])\s*\)")
ROMAN_PATTERN = re.compile(r"\(\s*((?:i{1,3}|iv|v|vi{0,3}|ix|x))\s*\)", re.IGNORECASE)
MARK_PATTERN = re.compile(r"\[\s*(\d{1,2})\s*\]")
ROMAN_LETTERS = {"i", "v", "x"}


@dataclass
class Detection:
    kind: str  # "letter", "roman", "mark"
    label: str
    bbox: List[int]
    value: int | None = None


def _scale(dpi: int) -> float:
    return dpi / 72.0


def _clip_text(page: fitz.Page, clip: fitz.Rect, mode: str = "dict") -> dict:
    """Extract text from a clipped region of a PDF page.
    
    Args:
        page: PDF page object.
        clip: Rectangular region to extract text from.
        mode: Text extraction mode ("dict", "rawdict", etc.).
        
    Returns:
        Dictionary of extracted text data, or empty dict on failure.
    """
    try:
        return page.get_text(mode, clip=clip)
    except (RuntimeError, ValueError) as e:
        logger.debug(f"Failed to extract text with mode {mode}: {e}")
        return {}


def extract_text_data(page: fitz.Page, clip: fitz.Rect) -> dict:
    """Extract text data once for reuse by multiple detectors.
    
    OPTIMIZATION #3: This function allows extracting text once per segment
    and passing it to both detect_section_labels_from_data and
    detect_mark_boxes_from_data, eliminating duplicate PDF parsing.
    
    Args:
        page: PDF page object.
        clip: Rectangular region to extract text from.
        
    Returns:
        Dictionary of extracted text data in rawdict format.
    """
    return _clip_text(page, clip, mode="rawdict")


def _bbox_from_chars(chars: Iterable[dict]) -> Tuple[float, float, float, float] | None:
    xs = []
    ys = []
    xe = []
    ye = []
    for ch in chars:
        bbox = ch.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        xs.append(bbox[0])
        ys.append(bbox[1])
        xe.append(bbox[2])
        ye.append(bbox[3])
    if not xs:
        return None
    return min(xs), min(ys), max(xe), max(ye)


def detect_section_labels(
    page: fitz.Page,
    clip: fitz.Rect,
    dpi: int,
    offset_y: int,
    trim_offset: Tuple[int, int],
) -> Tuple[List[Detection], List[Detection]]:
    """Detect lettered sections and roman numeral subsections.
    
    Scans for patterns like (a), (b), (c) for letters and (i), (ii), (iii)
    for roman numerals within a clipped page region.
    
    Args:
        page: PDF page to scan.
        clip: Rectangular region to search.
        dpi: Resolution for pixel coordinate conversion.
        offset_y: Vertical offset for stitched images.
        trim_offset: Whitespace trim offset (x, y).
        
    Returns:
        Tuple of (letter_detections, roman_detections) with pixel coordinates.
    """
    data = _clip_text(page, clip, mode="rawdict")
    return detect_section_labels_from_data(data, clip, dpi, offset_y, trim_offset)


def detect_section_labels_from_data(
    data: dict,
    clip: fitz.Rect,
    dpi: int,
    offset_y: int,
    trim_offset: Tuple[int, int],
) -> Tuple[List[Detection], List[Detection]]:
    """Detect lettered sections from pre-extracted text data.
    
    OPTIMIZATION #3: This variant accepts pre-extracted text data,
    allowing the pipeline to extract once and pass to multiple detectors.
    
    Args:
        data: Pre-extracted text data from extract_text_data().
        clip: Rectangular region used for coordinate conversion.
        dpi: Resolution for pixel coordinate conversion.
        offset_y: Vertical offset for stitched images.
        trim_offset: Whitespace trim offset (x, y).
        
    Returns:
        Tuple of (letter_detections, roman_detections) with pixel coordinates.
    """
    letters: List[Detection] = []
    romans: List[Detection] = []
    scale = _scale(dpi)
    x_limit = clip.x0 + (clip.width * 0.35)  # Limit search to left 35%

    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            text_seen_in_line = False
            
            for span in line.get("spans", []):
                chars = span.get("chars") or []
                if not chars:
                    continue
                span_text = "".join(ch.get("c", "") for ch in chars)
                
                # Check for SECTION labels (a), (b)
                for match in SECTION_PATTERN.finditer(span_text):
                    label = match.group(1).lower()
                    if label in ROMAN_LETTERS:
                        continue
                        
                    start = match.start()
                    # Line Start Check: 
                    # 1. No significant text seen previously in this line
                    # 2. No alphanumeric chars before this match in current span
                    #    EXCEPTION: Ignore preceding Section labels (e.g. allow "(a) (i)")
                    #    EXCEPTION: Ignore preceding question numerals (e.g. allow "12 (a)")
                    preceding = span_text[:start]
                    preceding_clean = SECTION_PATTERN.sub('', preceding)
                    # Allow if preceding text is ONLY a question number (1-2 digits + optional space)
                    is_question_numeral_only = bool(re.match(r'^\d{1,2}\s*$', preceding_clean))
                    if text_seen_in_line or (re.search(r'[a-zA-Z0-9]', preceding_clean) and not is_question_numeral_only):
                        continue

                        
                    end = match.end()
                    segment = chars[start:end]
                    bbox = _bbox_from_chars(segment)
                    if not bbox:
                        continue
                        
                    # Horizontal Check
                    if bbox[0] > x_limit:
                        continue
                        
                    det_bbox = _to_pixels(bbox, clip, scale, offset_y, trim_offset)
                    letters.append(Detection(kind="letter", label=label, bbox=det_bbox))

                # Check for ROMAN labels (i), (ii)
                for match in ROMAN_PATTERN.finditer(span_text):
                    label = match.group(1).lower()
                    start = match.start()
                    
                    # Line Start Check
                    preceding = span_text[:start]
                    preceding_clean = SECTION_PATTERN.sub('', preceding)
                    if text_seen_in_line or re.search(r'[a-zA-Z0-9]', preceding_clean):
                        continue

                    end = match.end()
                    segment = chars[start:end]
                    bbox = _bbox_from_chars(segment)
                    if not bbox:
                        continue
                        
                    # Horizontal Check
                    if bbox[0] > x_limit:
                        continue

                    det_bbox = _to_pixels(bbox, clip, scale, offset_y, trim_offset)
                    romans.append(Detection(kind="roman", label=label, bbox=det_bbox))
                
                # Update text seen status for next span
                if re.search(r'[a-zA-Z0-9]', span_text):
                    text_seen_in_line = True
    
    
    # Validate alphabetical sequence for letters
    letters = _validate_alphabetical_sequence(letters)
    
    return letters, romans


def _validate_alphabetical_sequence(detections: List[Detection]) -> List[Detection]:
    """Filter letter detections to only include valid alphabetical sequences.
    
    Validates that letters appear in alphabetical order, allowing gaps but
    rejecting out-of-sequence labels. This prevents false positives from
    content text like "(s)" appearing after "(a)".
    
    Rules (matching V1 implementation):
    - Letters must appear in order: (a), (b), (c), etc.
    - Small gaps allowed: (a), (c) is valid (gap of 1)
    - Starts with any letter (to support multi-page questions)
    - Large gaps rejected: (a), (s) is invalid (gap > 1)
    
    Args:
        detections: List of letter Detection objects
        
    Returns:
        Filtered list with only valid sequential letters
        
    Example:
        >>> # Input: [(a, y=10), (b, y=20), (s, y=30)]
        >>> # Output: [(a, y=10), (b, y=20)]
    """
    if not detections:
        return []
    
    
    # Sort by Y position (top to bottom)
    sorted_dets = sorted(detections, key=lambda d: d.bbox[1])
    
    # Validate sequence (matching V1 logic from slicer.py)
    # UPDATED: Allow starting with any letter to support multi-page questions
    valid = [sorted_dets[0]]
    expected_next_ord = ord(sorted_dets[0].label) + 1
    
    for det in sorted_dets[1:]:
        label_ord = ord(det.label)
        
        # Allow current expected letter OR next one (within 1 step)
        # This prevents (s) being detected after (a) but allows slight out-of-order
        if label_ord > expected_next_ord + 1:
            # Skip letters that are too far ahead in sequence (like 's' when expecting 'b')
            logger.debug(f"Letter '{det.label}' is too far ahead (expected '{chr(expected_next_ord)}' or '{chr(expected_next_ord + 1)}'). Stopping sequence.")
            break
        
        valid.append(det)
        # Update expected to next letter after this one
        expected_next_ord = max(expected_next_ord, label_ord + 1)
    
    return valid


def detect_mark_boxes(
    page: fitz.Page,
    clip: fitz.Rect,
    dpi: int,
    offset_y: int,
    trim_offset: Tuple[int, int],
) -> List[Detection]:
    """Detect mark value boxes in square brackets [N].
    
    Scans for patterns like [5], [10], [2] indicating mark allocations.
    
    Args:
        page: PDF page to scan.
        clip: Rectangular region to search.
        dpi: Resolution for pixel coordinate conversion.
        offset_y: Vertical offset for stitched images.
        trim_offset: Whitespace trim offset (x, y).
        
    Returns:
        List of Detection objects for mark boxes with values and positions.
    """
    data = _clip_text(page, clip, mode="rawdict")
    return detect_mark_boxes_from_data(data, clip, dpi, offset_y, trim_offset)


def detect_mark_boxes_from_data(
    data: dict,
    clip: fitz.Rect,
    dpi: int,
    offset_y: int,
    trim_offset: Tuple[int, int],
) -> List[Detection]:
    """Detect mark boxes from pre-extracted text data.
    
    OPTIMIZATION #3: This variant accepts pre-extracted text data,
    allowing the pipeline to extract once and pass to multiple detectors.
    
    Args:
        data: Pre-extracted text data from extract_text_data().
        clip: Rectangular region used for coordinate conversion.
        dpi: Resolution for pixel coordinate conversion.
        offset_y: Vertical offset for stitched images.
        trim_offset: Whitespace trim offset (x, y).
        
    Returns:
        List of Detection objects for mark boxes with values and positions.
    """
    marks: List[Detection] = []
    scale = _scale(dpi)
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                chars = span.get("chars") or []
                if not chars:
                    continue
                span_text = "".join(ch.get("c", "") for ch in chars)
                for match in MARK_PATTERN.finditer(span_text):
                    value = int(match.group(1))
                    start = match.start()
                    end = match.end()
                    segment = chars[start:end]
                    bbox = _bbox_from_chars(segment)
                    if not bbox:
                        continue
                    det_bbox = _to_pixels(bbox, clip, scale, offset_y, trim_offset)
                    marks.append(Detection(kind="mark", label=str(value), value=value, bbox=det_bbox))
    
    # Filter marks to reject false positives (e.g. "[1]" in question text)
    # Logic: 
    # 1. Identify the "Mark Column" using the first detector in the right 40% of the page
    # 2. Establish a minimum X threshold (Anchor X - 10%)
    # 3. Reject any marks to the left of this threshold
    if marks:
        # Calculate image width in pixels
        img_width = clip.width * scale
        right_side_start = img_width * 0.5  # Look in right half
        
        # Find anchor: First mark that is clearly on the right side
        # (Marks are collected top-to-bottom, so first one is usually Q1)
        anchor = next((m for m in marks if m.bbox[0] > right_side_start), None)
        
        if anchor:
            anchor_x = anchor.bbox[0]
            # Allow 10% leftward shift from anchor as margin
            # (User request: "normalize ... based on initial ... adding 10% to margin")
            min_valid_x = anchor_x * 0.90
            
            filtered_marks = []
            for m in marks:
                if m.bbox[0] >= min_valid_x:
                    filtered_marks.append(m)
                else:
                    logger.debug(f"Rejected false mark '{m.value}' at x={m.bbox[0]} (Threshold: {min_valid_x})")
            return filtered_marks
            
    return marks


def _to_pixels(
    bbox: Tuple[float, float, float, float],
    clip: fitz.Rect,
    scale: float,
    offset_y: int,
    trim_offset: Tuple[int, int],
) -> List[int]:
    x0, y0, x1, y1 = bbox
    trim_x, trim_y = trim_offset
    px0 = int(round((x0 - clip.x0) * scale)) - trim_x
    py0 = int(round((y0 - clip.y0) * scale)) - trim_y + offset_y
    px1 = int(round((x1 - clip.x0) * scale)) - trim_x
    py1 = int(round((y1 - clip.y0) * scale)) - trim_y + offset_y
    if px1 <= px0:
        px1 = px0 + 1
    if py1 <= py0:
        py1 = py0 + 1
    return [px0, py0, px1, py1]
