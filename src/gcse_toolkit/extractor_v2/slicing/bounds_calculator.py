"""
Module: extractor_v2.slicing.bounds_calculator

Purpose:
    Calculates slice bounds for each part within a composite image.
    These bounds are stored in regions.json and used by the builder
    to dynamically crop slices at render time.

Key Functions:
    - calculate_all_bounds(): Calculate bounds for all parts in tree
    - calculate_part_bounds(): Calculate bounds for a single part

Dependencies:
    - gcse_toolkit.core.models: SliceBounds dataclass
    - gcse_toolkit.extractor_v2.config: SliceConfig settings

Used By:
    - extractor_v2.pipeline: Calculates bounds for regions.json
    - builder_v2: Reads bounds to crop slices at render time
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ..diagnostics import DiagnosticsCollector

from gcse_toolkit.core.models import SliceBounds
from ..config import SliceConfig
from ..detection.marks import MarkBox
from ..detection.parts import PartLabel
from .offset_calculator import (
    calculate_part_shift,
    normalize_horizontal_bounds,
    get_reference_x_from_numeral,
)

logger = logging.getLogger(__name__)


# Constants
# Minimum height for root part when first letter is at y=0
# Minimum height for root part when first letter is at y=0

# Phase 6.9: Bounds calculation padding
BOUNDS_PADDING_PX = 5

# Phase 6.9: Clustering thresholds
PAGE_GAP_THRESHOLD_PX = 200  # Y-gap indicating new page
MARK_CLUSTER_TOLERANCE_PX = 10  # Right edge tolerance for same page


@dataclass
class PartBounds:
    """
    Bounds information for a single part.
    
    Contains the detected bounds (from detection) and calculated
    slice bounds (with padding and adjustments).
    
    Attributes:
        label: Part label like "1", "1(a)", "1(a)(i)".
        kind: Part type - "question", "letter", or "roman".
        detected_top: Raw top position from detection.
        detected_bottom: Raw bottom position (next part or composite end).
        label_height: Height of the label bounding box (for minimum slice height).
        slice_bounds: Final calculated bounds with padding.
        context_bounds: Optional context/header bounds.
        validation_issues: List of validation issues (e.g. composite_height fallback).
    """
    label: str
    kind: str
    detected_top: int
    detected_bottom: int
    label_bbox: Optional[Tuple[int, int, int, int]] = None  # (left, top, right, bottom)
    label_height: int = 20  # Default fallback if no label bbox
    child_is_inline: bool = False
    slice_bounds: Optional[SliceBounds] = None
    context_bounds: Optional[SliceBounds] = None
    validation_issues: List[str] = field(default_factory=list)


@dataclass
class PageGroup:
    """
    Group of parts on the same physical page.
    
    Used for Phase 6.9.1 hierarchical bounds inheritance to track
    page-specific horizontal offsets from the root page.
    
    Attributes:
        page_index: Logical page number (0, 1, 2...).
        parts: Parts on this page.
        horizontal_offset: Horizontal offset in pixels from root page.
                          Can be positive (shifted right) or negative (shifted left).
    """
    page_index: int
    parts: List[PartBounds]
    horizontal_offset: int = 0


def calculate_all_bounds(
    parts: List[PartBounds],
    composite_height: int,
    composite_width: int,
    marks: List[MarkBox],
    config: SliceConfig,
    labels: Optional[List[PartLabel]] = None,
    numeral_bbox: Optional[Tuple[int, int, int, int]] = None,
    # Context for enhanced warning logging
    exam_code: Optional[str] = None,
    pdf_name: Optional[str] = None,
    question_number: Optional[int] = None,
    # Reference for offset calculation (not applied to bounds)
    reference_x: Optional[int] = None,
    diagnostics_collector: Optional[DiagnosticsCollector] = None,
) -> Tuple[Dict[str, SliceBounds], int]:
    """
    Calculate slice bounds using exact detected positions.
    
    Bounds are stored as exact true values from detection.
    Offset is calculated and returned separately for render-time use.
    
    Args:
        parts: List of PartBounds with detected positions.
        composite_height: Total height of composite image.
        composite_width: Total width of composite image.
        marks: List of detected mark boxes for right boundary.
        config: Slice configuration settings.
        labels: List of detected part labels (unused).
        numeral_bbox: Question numeral bbox for left edge.
        exam_code: Exam code for logging context.
        pdf_name: PDF filename for logging context.
        question_number: Question number for logging context.
        reference_x: Global reference X for offset calculation.
        
    Returns:
        Tuple of:
        - Dict mapping part label to SliceBounds (true detected positions)
        - horizontal_offset: int (this question's shift from reference)
    """
    result: Dict[str, SliceBounds] = {}
    horizontal_offset = 0
    
    if not parts:
        return result, horizontal_offset
    
    # Calculate horizontal offset for this question (for rendering)
    if numeral_bbox:
        this_numeral_x = numeral_bbox[0]
        if reference_x is not None:
            horizontal_offset = calculate_part_shift(reference_x, this_numeral_x)
            if horizontal_offset != 0:
                logger.debug(
                    f"Question {question_number}: offset={horizontal_offset:+d}px from reference"
                )
    
    # Normalize mark bboxes for right edge calculation
    normalized_marks = _normalize_mark_bboxes(
        marks,
        exam_code=exam_code,
        pdf_name=pdf_name,
        question_number=question_number,
        diagnostics_collector=diagnostics_collector,
        labels=labels,
    ) if marks else {}
    
    # Calculate content_right: the maximum right edge from all marks
    # This defines the true content boundary (excluding margin)
    # Used as fallback for parts without a mark in their range
    content_right = composite_width  # Default to full width if no marks
    if normalized_marks:
        content_right = max(normalized_marks.values()) + BOUNDS_PADDING_PX
    
    # Calculate bounds for each part using TRUE detected positions (no offset adjustment)
    for part in parts:
        # Left edge: from label bbox (true detected position)
        if part.label_bbox:
            left = max(0, part.label_bbox[0] - BOUNDS_PADDING_PX)
        elif numeral_bbox and part.kind == "question":
            left = max(0, numeral_bbox[0] - BOUNDS_PADDING_PX)
        else:
            left = 0
        
        # Right edge: from marks, capped at content_right
        # This ensures ALL parts have correct right bounds (no composite_width fallback)
        right = _calculate_right_from_marks(
            part,
            normalized_marks,
            content_right,  # Use content_right instead of composite_width
            padding=BOUNDS_PADDING_PX,
        )
        
        # Vertical bounds (unchanged)
        top = int(part.detected_top)
        bottom = int(part.detected_bottom)
        
        result[part.label] = SliceBounds(
            top=top,
            bottom=bottom,
            left=left,
            right=right,
            child_is_inline=part.child_is_inline,
        )
    
    return result, horizontal_offset


# ─────────────────────────────────────────────────────────────────────────
# Phase 6.9: Normalization Helpers
# ─────────────────────────────────────────────────────────────────────────

def _normalize_label_bboxes(labels: List[PartLabel]) -> Dict[str, int]:
    """
    Normalize label left edges per-level, per-page.
    
    Groups labels by:
    1. Kind (letter vs roman) - different indentation levels
    2. Page (using Y-position clustering) - different page margins
    
    Returns minimum left edge within each group for consistent alignment.
    
    Args:
        labels: List of detected part labels
        
    Returns:
        Dict mapping label text -> normalized left edge
    """
    if not labels:
        return {}
    
    # Group by kind (level)
    letters = [l for l in labels if l.kind == "letter"]
    romans = [l for l in labels if l.kind == "roman"]
    
    normalized = {}
    
    # Normalize each level separately
    for group in [letters, romans]:
        if not group:
            continue
        
        # Cluster by page using Y positions
        y_positions = [l.y_position for l in group]
        page_clusters = _cluster_by_page(y_positions, PAGE_GAP_THRESHOLD_PX)
        
        # Normalize within each page
        for cluster_indices in page_clusters:
            page_labels = [group[i] for i in cluster_indices]
            # Use minimum left edge (leftmost label on this page/level)
            min_left = min(l.bbox[0] for l in page_labels)
            for label in page_labels:
                normalized[label.label] = min_left
    
    return normalized


def _normalize_mark_bboxes(
    marks: List[MarkBox],
    exam_code: Optional[str] = None,
    pdf_name: Optional[str] = None,
    question_number: Optional[int] = None,
    diagnostics_collector: Optional[DiagnosticsCollector] = None,
    labels: Optional[List[PartLabel]] = None,
) -> Dict[int, int]:
    """
    Normalize mark right edges per-page with sanity check.
    
    Groups marks by page and verifies they generally agree on right edge.
    Returns the right edge for each mark's Y position.
    
    Sanity check: Warns if marks on same page have significantly different
    right edges (suggests detection issue or multi-page question).
    
    Args:
        marks: List of detected mark boxes
        exam_code: Exam code for logging context
        pdf_name: PDF filename for logging context
        question_number: Question number for logging context
        
    Returns:
        Dict mapping mark.y_position -> right edge for that page
    """
    if not marks:
        return {}
    
    # Group marks by page using Y position (gap > 200px = new page)
    y_positions = [m.y_position for m in marks]
    page_clusters = _cluster_by_page(y_positions, PAGE_GAP_THRESHOLD_PX)
    
    normalized = {}
    for page_idx, cluster_indices in enumerate(page_clusters):
        page_marks = [marks[i] for i in cluster_indices]
        
        # Determine the "true" right margin for this page
        # Heuristic: The right-most marks are likely the valid ones.
        # Marks significantly to the left (e.g. >100px) are likely false positives in text.
        all_right_edges = [m.bbox[2] for m in page_marks]
        header_max_right = max(all_right_edges)
        
        # Filter out outliers (User defined threshold: 100px)
        valid_page_marks = []
        skipped_count = 0
        
        for m in page_marks:
            deviation = header_max_right - m.bbox[2]
            if deviation > 100:
                # Mark is too far left (>100px from margin) - Skip it
                skipped_count += 1
                if diagnostics_collector:
                    diagnostics_collector.add_layout_issue(
                        pdf_name=pdf_name or "unknown",
                        exam_code=exam_code or "unknown",
                        question_number=question_number,
                        page_index=page_idx,
                        message=f"Skipping malformed mark box: [mark {m.value}] deviates by {deviation}px from margin",
                        details={
                            "mark_value": m.value,
                            "mark_right": m.bbox[2],
                            "page_max_right": header_max_right,
                            "deviation": deviation
                        },
                        y_span=(m.y_position, m.bbox[3]),
                        prev_label_info=f"Mark [{m.value}]",
                        next_label_info=f"Margin @ {header_max_right}"
                    )
                logger.warning(
                    f"Skipping outlier mark [{m.value}] at y={m.y_position}. "
                    f"Right edge {m.bbox[2]} is {deviation}px from page margin ({header_max_right})."
                )
            else:
                valid_page_marks.append(m)
        
        if not valid_page_marks:
            # Fallback if everything was filtered (unlikely)
            valid_page_marks = page_marks
            header_max_right = max(m.bbox[2] for m in page_marks)

        # Sanity check on REMAINING valid marks
        # (Use original tolerance of 10px for the "clean" set)
        valid_right_edges = [m.bbox[2] for m in valid_page_marks]
        min_right = min(valid_right_edges)
        max_right = max(valid_right_edges) # Should be header_max_right
        
        if max_right - min_right > MARK_CLUSTER_TOLERANCE_PX:
            # Marks still vary (but less than 100px) - Log warning
            # ... (existing logging logic) ...
            # import logging
            # logger = logging.getLogger(__name__)
            
            context_str = f"Q{question_number}" if question_number else "Unknown"
            
            logger.warning(
                f"Mark boxes vary (minor): {min_right}-{max_right}px (diff: {max_right - min_right}px). "
                f"Using max right edge. [{context_str}]",
                extra={
                    "exam_code": exam_code,
                    "diff": max_right - min_right,
                }
            )
            # We don't add a diagnostic for minor variance if we've already cleaned up outliers,
            # or we can keep it if strictness is desired.
            
        for mark in valid_page_marks:
            normalized[mark.y_position] = max_right
    
    return normalized


def _cluster_by_page(y_positions: List[int], gap_threshold: int) -> List[List[int]]:
    """
    Group items into pages by Y position gaps.
    
    Large Y gaps (> gap_threshold) indicate page boundaries.
    
    Args:
        y_positions: List of Y coordinates
        gap_threshold: Minimum gap to consider a new page
        
    Returns:
        List of index lists, one per page
    """
    if not y_positions:
        return []
    
    # Sort by Y position
    sorted_indices = sorted(range(len(y_positions)), key=lambda i: y_positions[i])
    
    # Group into pages
    pages = []
    current_page = [sorted_indices[0]]
    
    for i in range(1, len(sorted_indices)):
        idx = sorted_indices[i]
        prev_idx = sorted_indices[i - 1]
        
        if y_positions[idx] - y_positions[prev_idx] > gap_threshold:
            # New page detected
            pages.append(current_page)
            current_page = [idx]
        else:
            current_page.append(idx)
    
    pages.append(current_page)
    return pages


def _cluster_values(values: List[int], tolerance: int) -> List[List[int]]:
    """
    Cluster values within tolerance.
    
    Values within tolerance of each other are considered the same cluster.
    
    Args:
        values: List of values to cluster
        tolerance: Maximum difference for same cluster
        
    Returns:
        List of index lists, one per cluster
    """
    if not values:
        return []
    
    # Sort by value
    sorted_indices = sorted(range(len(values)), key=lambda i: values[i])
    
    # Group into clusters
    clusters = []
    current_cluster = [sorted_indices[0]]
    
    for i in range(1, len(sorted_indices)):
        idx = sorted_indices[i]
        prev_idx = sorted_indices[i - 1]
        
        if abs(values[idx] - values[prev_idx]) <= tolerance:
            current_cluster.append(idx)
        else:
            clusters.append(current_cluster)
            current_cluster = [idx]
    
    clusters.append(current_cluster)
    return clusters


def _calculate_left_from_labels(
    part: PartBounds,
    labels: List[PartLabel],
    normalized_labels: Dict[str, int],
    padding: int,
) -> int:
    """
    Calculate left boundary from part label position.
    
    Returns normalized left edge minus padding if label found within part's range.
    Falls back to 0 if label not found or not in range.
    
    Args:
        part: Part bounds to calculate left edge for
        labels: List of all detected labels (for range checking)
        normalized_labels: Dict from _normalize_label_bboxes()
        padding: Pixels to subtract from left edge
        
    Returns:
        Left boundary in pixels
    """
    # Root part - use left edge
    if '(' not in part.label:
        return 0
    
    # Get innermost label (last parenthesized part)
    # e.g., "1(a)(i)" -> "i", "1(a)" -> "a"
    base_label = part.label.split('(')[-1].rstrip(')')
    
    # Find the label and check if it's within this part's vertical range
    for label in labels:
        if label.label == base_label:
            # Check if label is within this part's range (with tolerance)
            # Labels are at the top of parts, so check near detected_top
            if abs(label.y_position - part.detected_top) < 50:
                if base_label in normalized_labels:
                    return max(0, normalized_labels[base_label] - padding)
    
    # Label not found in range - fallback to left edge
    return 0


def _calculate_right_from_marks(
    part: PartBounds,
    normalized_marks: Dict[int, int],
    composite_width: int,
    padding: int,
) -> int:
    """
    Calculate right boundary from mark box position.
    
    For leaf parts, uses normalized mark right edge if mark found within part's range.
    For context parts or when no mark found, uses composite width.
    
    Args:
        part: Part bounds to calculate right edge for
        normalized_marks: Dict from _normalize_mark_bboxes()
        composite_width: Full composite width for fallback
        padding: Pixels to add to right edge
        
    Returns:
        Right boundary in pixels
    """
    if not normalized_marks:
        return composite_width
    
    # Find mark within this part's vertical range
    for mark_y, right_edge in normalized_marks.items():
        # Check if mark is within this part (with some tolerance)
        if part.detected_top <= mark_y <= part.detected_bottom + 50:
            return min(composite_width, right_edge + padding)
    
    # No mark found in range - use full width
    return composite_width


# ─────────────────────────────────────────────────────────────────────────
# Phase 6.9.1: Hierarchical Bounds Inheritance Helpers
# ─────────────────────────────────────────────────────────────────────────

def _group_parts_by_page(
    parts: List[PartBounds],
    gap_threshold: int = PAGE_GAP_THRESHOLD_PX,
) -> List[PageGroup]:
    """
    Group parts into pages using vertical position clustering.
    
    Large Y-position gaps (>gap_threshold) indicate page boundaries.
    Each PageGroup represents parts on the same physical page.
    
    Args:
        parts: All parts for a question, sorted by detected_top
        gap_threshold: Y-gap indicating new page boundary (default 200px)
        
    Returns:
        List of PageGroup, one per physical page, ordered by appearance
        
    Example:
        >>> parts = [part_a, part_b, part_c]  # c is 300px below b
        >>> pages = _group_parts_by_page(parts, gap_threshold=200)
        >>> len(pages)
        2  # parts a,b on page 0, part c on page 1
    """
    if not parts:
        return []
    
    # Sort by vertical position
    sorted_parts = sorted(parts, key=lambda p: p.detected_top)
    
    # Group into pages based on Y-gaps
    pages: List[PageGroup] = []
    current_parts = [sorted_parts[0]]
    
    for i in range(1, len(sorted_parts)):
        prev_part = sorted_parts[i - 1]
        curr_part = sorted_parts[i]
        
        # Check for page boundary (large Y-gap)
        if curr_part.detected_top - prev_part.detected_bottom > gap_threshold:
            # Save current page and start new one
            pages.append(PageGroup(
                page_index=len(pages),
                parts=current_parts,
                horizontal_offset=0,  # Will be calculated later
            ))
            current_parts = [curr_part]
        else:
            current_parts.append(curr_part)
    
    # Add final page
    pages.append(PageGroup(
        page_index=len(pages),
        parts=current_parts,
        horizontal_offset=0,
    ))
    
    return pages


def _find_reference_labels(
    page_parts: List[PartBounds],
    labels: List[PartLabel],
    kind: str,
) -> List[PartLabel]:
    """
    Find labels on a page for offset detection.
    
    Filters labels by kind and vertical position to find labels
    belonging to parts on this page. Used to compare label positions
    across pages for shift detection.
    
    Args:
        page_parts: Parts on this page
        labels: All detected labels
        kind: Label kind to filter by ("letter" or "roman")
        
    Returns:
        Labels that fall within this page's vertical range
        
    Example:
        >>> page_parts = [part_a, part_b]  # y=100-200
        >>> all_labels = [label_a, label_b, label_c]  # a,b in range, c not
        >>> refs = _find_reference_labels(page_parts, all_labels, "letter")
        >>> len(refs)
        2  # label_a and label_b
    """
    if not page_parts or not labels:
        return []
    
    # Get vertical range of this page
    page_top = min(p.detected_top for p in page_parts)
    page_bottom = max(p.detected_bottom for p in page_parts)
    
    # Filter labels within this page's range
    page_labels = []
    for label in labels:
        if label.kind == kind and page_top <= label.y_position <= page_bottom:
            page_labels.append(label)
    
    return page_labels


def _calculate_page_offset(
    current_page: PageGroup,
    previous_page: PageGroup,
    labels: List[PartLabel],
) -> int:
    """
    Calculate horizontal offset between two pages.
    
    Compares label X-positions at the same nesting level (preferring
    letters) to detect content shifts between pages. Returns the median
    offset if multiple labels are found (robust to outliers).
    
    Args:
        current_page: Current page group
        previous_page: Previous page group
        labels: All detected labels for position lookup
        
    Returns:
        Horizontal offset in pixels. Positive = shifted right,
        negative = shifted left, 0 = no shift or no labels to compare
        
    Example:
        >>> # Labels on page 0 at x=50, labels on page 1 at x=60
        >>> offset = _calculate_page_offset(page1, page0, all_labels)
        >>> offset
        10  # Shifted 10px to the right
    """
    # Try letters first (outermost level, most reliable)
    prev_letters = _find_reference_labels(previous_page.parts, labels, "letter")
    curr_letters = _find_reference_labels(current_page.parts, labels, "letter")
    
    if prev_letters and curr_letters:
        # Calculate offsets for each label pair
        prev_x = sum(l.bbox[0] for l in prev_letters) / len(prev_letters)
        curr_x = sum(l.bbox[0] for l in curr_letters) / len(curr_letters)
        return int(curr_x - prev_x)
    
    # Fallback to romans if no letters found
    prev_romans = _find_reference_labels(previous_page.parts, labels, "roman")
    curr_romans = _find_reference_labels(current_page.parts, labels, "roman")
    
    if prev_romans and curr_romans:
        prev_x = sum(l.bbox[0] for l in prev_romans) / len(prev_romans)
        curr_x = sum(l.bbox[0] for l in curr_romans) / len(curr_romans)
        return int(curr_x - prev_x)
    
    # No labels to compare - assume no offset
    return 0


def _get_parent_label(label: str) -> Optional[str]:
    """
    Extract parent label from a part label.
    
    Examples:
        "1" → None
        "1(a)" → "1"
        "1(a)(i)" → "1(a)"
        "1(b)(ii)" → "1(b)"
    
    Args:
        label: Part label
        
    Returns:
        Parent label or None if label is root
    """
    if "(" not in label:
        return None
    
    # Remove last parenthesized section
    # "1(a)(i)" → "1(a)"
    # "1(a)" → "1"
    last_open = label.rfind("(")
    if last_open == -1:
        return None
    
    parent = label[:last_open]
    return parent if parent else None




def _find_part_mark(
    part_y: int,
    next_part_y: int,
    marks: List[MarkBox],
) -> Optional[MarkBox]:
    """
    Find mark box belonging to this part.
    
    Args:
        part_y: Part's y position.
        next_part_y: Next part's y position (or composite height).
        marks: List of all mark boxes.
        
    Returns:
        Mark box for this part, or None if no mark found.
    """
    for mark in marks:
        if part_y <= mark.y_position < next_part_y:
            return mark
    return None


def bounds_from_detections(
    question_num: int,
    letters: List,  # List[PartLabel]
    romans: List,   # List[PartLabel]
    composite_height: int,
    marks: List = None,  # List[MarkBox]
    numeral_bbox: Optional[Tuple[int, int, int, int]] = None,
) -> List[PartBounds]:
    """
    Create PartBounds list from detection results.
    
    Simple rule: If a part has a mark box, use mark.bbox[3] + clearance as bottom.
    Otherwise use next sibling position or composite_height.
    
    Args:
        question_num: Question number for label prefix.
        letters: Detected letter labels.
        romans: Detected roman numerals.
        composite_height: Height of composite for end bounds.
        marks: Optional detected mark boxes for accurate bounds.
        numeral_bbox: Optional numeral bounding box (unused).
        
    Returns:
        List of PartBounds ready for bounds calculation.
    """
    if marks is None:
        marks = []
    
    parts: List[PartBounds] = []
    
    # Sort letters by Y-position upfront (input may be unsorted)
    sorted_letters = sorted(letters, key=lambda l: l.y_position)
    
    # Root question part
    root_top = 0
    # Determine basic root bottom
    if sorted_letters:
        root_bottom = sorted_letters[0].y_position
    elif marks:
        # Single-part question with marks: clamp bottom to mark box instead of page end
        max_mark_bottom = max(m.bbox[3] for m in marks)
        root_bottom = min(composite_height, max_mark_bottom + BOUNDS_PADDING_PX)
    else:
        root_bottom = composite_height
    
    # Placeholder for root (will finalize after letters)
    root_part = PartBounds(
        label=str(question_num),
        kind="question",
        detected_top=root_top,
        detected_bottom=root_bottom,
        label_bbox=numeral_bbox,  # Root uses numeral bbox
    )
    parts.append(root_part)
    
    # Letter parts
    
    for i, letter in enumerate(sorted_letters):
        # Find romans belonging to this letter
        letter_romans = []
        next_letter_y = sorted_letters[i + 1].y_position if i + 1 < len(sorted_letters) else composite_height
        
        for roman in romans:
            if letter.y_position <= roman.y_position < next_letter_y:
                letter_romans.append(roman)
        
        # Determine letter bottom
        if letter_romans:
            # Has child romans
            first_roman = letter_romans[0]
            
            # Check if letter is inline with first roman (e.g. "(a) (i)")
            if abs(first_roman.y_position - letter.y_position) < 10:
                # Inline: Letter shares bounds with first roman
                # We need to calculate first roman's bottom to extend letter
                next_roman_limit = letter_romans[1].y_position if len(letter_romans) > 1 else next_letter_y
                
                roman_mark = _find_part_mark(first_roman.y_position, next_roman_limit, marks)
                if roman_mark:
                    # Fix: Clamp extended bottom to avoid overlapping next part
                    letter_bottom = min(roman_mark.bbox[3], next_roman_limit)
                else:
                    letter_bottom = next_roman_limit
            else:
                # Not inline: Letter ends where first roman starts
                letter_bottom = first_roman.y_position
        else:
            # No child romans - check for mark box (use exact bottom)
            letter_mark = _find_part_mark(letter.y_position, next_letter_y, marks)
            if letter_mark:
                # STRICT FIX: Clamp to next letter to prevent overlap
                letter_bottom = min(letter_mark.bbox[3], next_letter_y)
            else:
                # For last letter (fallback = composite_height), clamp to max mark bottom
                if next_letter_y == composite_height and marks:
                    max_mark_bottom = max(m.bbox[3] for m in marks)
                    letter_bottom = min(composite_height, max_mark_bottom + BOUNDS_PADDING_PX)
                else:
                    letter_bottom = next_letter_y
                
        # Check for inline letter: e.g. "(a) (i)"
        letter_is_inline = False
        if letter_romans:
            # If first roman starts at same Y as letter
            if abs(letter_bottom - letter.y_position) < 10:
                letter_is_inline = True
                # If inline, letter shares bounds with first roman
                # But roman's bottom is determined by *its* content/next roman
                # So we need to calculate first roman's bottom
                
                # Look ahead to first roman's end
                first_roman = letter_romans[0]
                next_roman_limit = letter_romans[1].y_position if len(letter_romans) > 1 else next_letter_y
                
                roman_mark = _find_part_mark(first_roman.y_position, next_roman_limit, marks)
                if roman_mark:
                    # FIXED: Clamp here too
                    letter_bottom = min(roman_mark.bbox[3], next_roman_limit)
                else:
                    letter_bottom = next_roman_limit
        
        # Check if letter is inline with ROOT (e.g. "8 (a)")
        # If letter starts at same Y as root, it is inline with root
        if abs(letter.y_position - root_top) < 10:
            letter_is_inline = True
            # Since letter is inline with root, the ROOT must be extended to cover this letter
            # We update the root_part's detected_bottom to match this letter's bottom (at least)
            # This ensures the root slice contains the inline content
            if letter_bottom > root_part.detected_bottom:
                root_part.detected_bottom = letter_bottom
        
        # STRICT VALIDATION: Flag if letter uses composite_height fallback (no mark box, no next sibling)
        letter_validation_issues = []
        if letter_bottom == composite_height:
            letter_validation_issues.append("No mark box detected (uses composite_height)")
        
        parts.append(PartBounds(
            label=f"{question_num}({letter.label})",
            kind="letter",
            detected_top=letter.y_position,
            detected_bottom=letter_bottom,
            label_bbox=letter.bbox,  # Per-part label bbox
            label_height=letter.bbox[3] - letter.bbox[1],
            child_is_inline=letter_is_inline,
            validation_issues=letter_validation_issues,
        ))
        
        # Roman parts under this letter
        for j, roman in enumerate(letter_romans):
            # Determine roman bottom
            next_roman_y = letter_romans[j + 1].y_position if j + 1 < len(letter_romans) else next_letter_y
            
            # Calculate mark for THIS roman part
            this_roman_mark = _find_part_mark(roman.y_position, next_roman_y, marks)
            if this_roman_mark:
                # STRICT FIX: Clamp to next roman to prevent overlap
                roman_bottom = min(this_roman_mark.bbox[3], next_roman_y)
            else:
                # For last roman (fallback cascades to composite_height), clamp to max mark bottom
                if next_roman_y == composite_height and marks:
                    max_mark_bottom = max(m.bbox[3] for m in marks)
                    roman_bottom = min(composite_height, max_mark_bottom + BOUNDS_PADDING_PX)
                else:
                    roman_bottom = next_roman_y
            
            # Check if roman is inline with LETTER (e.g. "(a) (i)")
            roman_is_inline = False
            if abs(roman.y_position - letter.y_position) < 10:
                roman_is_inline = True
            
            # STRICT VALIDATION: Flag if roman uses composite_height fallback
            roman_validation_issues = []
            if roman_bottom == composite_height:
                roman_validation_issues.append("No mark box detected (uses composite_height)")
            
            parts.append(PartBounds(
                label=f"{question_num}({letter.label})({roman.label})",
                kind="roman",
                detected_top=roman.y_position,
                detected_bottom=roman_bottom,
                label_bbox=roman.bbox,  # Per-part label bbox
                label_height=roman.bbox[3] - roman.bbox[1],
                child_is_inline=roman_is_inline,
                validation_issues=roman_validation_issues,
            ))
            
    return parts
