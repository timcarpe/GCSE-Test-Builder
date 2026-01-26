"""
Module: extractor_v2.structuring.tree_builder

Purpose:
    Builds immutable Part trees from detection results. Converts flat
    lists of detected labels and marks into a hierarchical Part structure
    with calculated bounds and marks.

Key Functions:
    - build_part_tree(): Build Part tree from detections
    - assign_marks_to_detections(): Match marks to detected parts

Dependencies:
    - gcse_toolkit.core.models: Part, Marks, PartKind, SliceBounds

Used By:
    - extractor_v2.pipeline: Creates Part trees for each question
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field

from gcse_toolkit.core.models import Part, Marks, SliceBounds
from gcse_toolkit.core.models.parts import PartKind
from ..detection.parts import PartLabel
from ..detection.marks import MarkBox
from ..diagnostics import DiagnosticsCollector, TextExtractor

logger = logging.getLogger(__name__)


# Constants
MIN_PART_HEIGHT = 1  # Minimum height for parts with undefined bounds


@dataclass
class PartBuilder:
    """
    Mutable builder for constructing Part objects.
    
    Used internally during tree construction. Converted to immutable
    Part once tree structure is finalized.
    """
    label: str
    kind: PartKind
    y_start: int
    y_end: Optional[int] = None
    label_bbox: Optional[Tuple[int, int, int, int]] = None  # (left, top, right, bottom)
    marks_value: Optional[int] = None
    children: Optional[List["PartBuilder"]] = None
    is_valid: bool = True  # Phase 6.10: Per-part validity
    validation_note: Optional[str] = None  # Phase 6.10: Reason for invalidity
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


def build_part_tree(
    question_num: int,
    letters: List[PartLabel],
    romans: List[PartLabel],
    marks: List[MarkBox],
    composite_height: int,
    composite_width: int,
    exam_code: str = "",
    pdf_name: str = "",
    diagnostics_collector: Optional[DiagnosticsCollector] = None,
    text_extractor: Optional[TextExtractor] = None,
) -> Part:
    """
    Build an immutable Part tree from detection results.
    
    Creates a hierarchical structure where:
    - Root is the question (e.g., "1")
    - Letters are first-level children (e.g., "1(a)")
    - Romans are children of letters (e.g., "1(a)(i)")
    
    Marks are assigned to the nearest leaf part above each mark box.
    
    Args:
        question_num: Question number for label prefix.
        letters: Detected (a), (b) labels sorted by y_position.
        romans: Detected (i), (ii) labels sorted by y_position.
        marks: Detected [N] mark boxes sorted by y_position.
        composite_height: Height of composite image.
        composite_width: Width of composite image.
        
    Returns:
        Root Part with complete tree structure.
        
    Raises:
        ValueError: If tree structure is invalid.
        
    Example:
        >>> tree = build_part_tree(1, letters, romans, marks, 1200, 800)
        >>> tree.label
        '1'
        >>> tree.total_marks
        15
    """
    # Sort inputs by position
    letters = sorted(letters, key=lambda l: l.y_position)
    romans = sorted(romans, key=lambda r: r.y_position)
    marks = sorted(marks, key=lambda m: m.y_position)
    
    # Build mutable tree
    root = PartBuilder(
        label=str(question_num),
        kind=PartKind.QUESTION,
        y_start=0,
        y_end=composite_height,
    )
    
    # Attach letters to root
    for i, letter in enumerate(letters):
        next_letter_y = letters[i + 1].y_position if i + 1 < len(letters) else composite_height
        
        letter_builder = PartBuilder(
            label=f"{question_num}({letter.label})",
            kind=PartKind.LETTER,
            y_start=letter.y_position,
            y_end=next_letter_y,
            # PartLabel bbox is (left, top, right, bottom)
            label_bbox=letter.bbox,
        )
        root.children.append(letter_builder)
    
    # Attach romans to their parent letters
    for roman in romans:
        parent = _find_parent_letter(root.children, roman.y_position)
        if parent:
            roman_builder = PartBuilder(
                label=f"{parent.label}({roman.label})",
                kind=PartKind.ROMAN,
                y_start=roman.y_position,
                # PartLabel bbox is (left, top, right, bottom)
                label_bbox=roman.bbox,
            )
            parent.children.append(roman_builder)
    
    # Calculate roman y_end values
    for letter in root.children:
        _finalize_children_bounds(letter.children, letter.y_end)
    
    # Phase 6.10: Validate sequences and log issues
    _validate_letter_sequence(
        letters,
        question_num,
        exam_code,
        pdf_name,
        diagnostics_collector,
        text_extractor,
    )
    
    # Validate letter builders and flag gaps (1:1 alignment: is_valid + warning + diagnostic)
    _validate_letter_builders(
        root.children,
        question_num,
        exam_code,
        pdf_name,
        diagnostics_collector,
    )
    
    for letter_builder in root.children:
        if letter_builder.children:
            _validate_roman_sequence_for_letter(
                letter_builder.children,
                letter_builder.label,
                question_num,
                exam_code,
                pdf_name,
                diagnostics_collector,
                text_extractor,
            )

    
    # Assign marks to leaf parts
    _assign_marks(root, marks)
    
    # NOTE: Part-level validation is now done in bounds_calculator.py
    # which has access to mark box detection results and composite_height
    
    # Convert to immutable Part
    return _convert_to_part(root, composite_width)


def _find_parent_letter(
    letters: List[PartBuilder],
    y_pos: int,
) -> Optional[PartBuilder]:
    """Find the letter that contains this y-position."""
    for i, letter in enumerate(letters):
        next_start = letters[i + 1].y_start if i + 1 < len(letters) else float('inf')
        if letter.y_start <= y_pos < next_start:
            return letter
    return letters[-1] if letters else None


def _finalize_children_bounds(
    children: List[PartBuilder],
    parent_end: int,
) -> None:
    """Set y_end for each child based on next sibling."""
    for i, child in enumerate(children):
        if i + 1 < len(children):
            child.y_end = children[i + 1].y_start
        else:
            child.y_end = parent_end


def _assign_marks(
    root: PartBuilder,
    marks: List[MarkBox],
) -> None:
    """
    Assign mark values to the nearest leaf part above each mark.
    
    Uses y-position proximity to match marks to parts.
    """
    leaves = list(_iter_leaves(root))
    used_marks = set()
    
    for leaf in leaves:
        # Find marks within this leaf's bounds
        leaf_marks = [
            m for i, m in enumerate(marks)
            if leaf.y_start <= m.y_position < (leaf.y_end or float('inf'))
            and i not in used_marks
        ]
        
        if leaf_marks:
            # Use the last mark in this region (usually the leaf's own mark)
            mark = max(leaf_marks, key=lambda m: m.y_position)
            leaf.marks_value = mark.value
            used_marks.add(marks.index(mark))


def _iter_leaves(node: PartBuilder):
    """Yield all leaf nodes in the tree."""
    if not node.children:
        yield node
    else:
        for child in node.children:
            yield from _iter_leaves(child)



def _find_first_non_inline_descendant_top(children: Tuple[Part, ...]) -> Optional[int]:
    """
    Find the first non-inline descendant's top position for context bounds.
    
    Recursively traverses inline children to find the first descendant
    that is NOT inline with its parent. This is used to calculate the
    context bounds bottom for parent parts with inline children.
    
    For example, with "8 (a) (i)" where (a) is inline with 8:
    - children[0] = (a) with child_is_inline=True
    - We skip (a) and look at (a)'s children
    - (a)'s children[0] = (i) with child_is_inline=False
    - Return (i).bounds.top as the context bottom
    
    Args:
        children: Tuple of Part children to search through
        
    Returns:
        The top position of the first non-inline descendant, or None if
        no children exist or all descendants are inline (edge case).
        
    Example:
        >>> # children = [(a), (b)] where (a) is inline
        >>> top = _find_first_non_inline_descendant_top(children)
        >>> # Returns (i).bounds.top if (a) has child (i) that's non-inline
    """
    if not children:
        return None
    
    first_child = children[0]
    
    # If first child is NOT inline, use its top directly
    if not first_child.bounds.child_is_inline:
        return first_child.bounds.top
    
    # First child IS inline - recursively search its children
    if first_child.children:
        return _find_first_non_inline_descendant_top(first_child.children)
    
    # Edge case: inline child with no children (shouldn't happen in well-formed data)
    # Fall back to this child's top anyway
    return first_child.bounds.top


def _convert_to_part(
    builder: PartBuilder,
    composite_width: int,
) -> Part:
    """Convert PartBuilder to immutable Part with context_bounds."""
    # Convert children first
    children = tuple(_convert_to_part(c, composite_width) for c in builder.children)
    
    # Determine marks
    if builder.marks_value is not None:
        marks = Marks.explicit(builder.marks_value)
    elif children:
        # Aggregate from children - use the already-converted Part objects
        marks = Marks.aggregate(children)
    else:
        # No marks found
        marks = Marks.inferred(0)
    
    # Create bounds - ensure bottom > top
    y_end = builder.y_end if builder.y_end and builder.y_end > builder.y_start else builder.y_start + MIN_PART_HEIGHT
    bounds = SliceBounds(
        top=builder.y_start,
        bottom=y_end,
        left=0,
        right=composite_width,
    )
    
    # Calculate context_bounds for parent parts (QUESTION and LETTER)
    # Context is the header region from part start to first non-inline child start
    context_bounds = None
    if children and builder.kind in (PartKind.QUESTION, PartKind.LETTER):
        # Find the first non-inline descendant for context bottom
        # This handles cases like "8 (a) (i)" where (a) is inline with 8
        # We need to find (i) as the context bottom since (a) shares the same line
        first_non_inline_top = _find_first_non_inline_descendant_top(children)
        
        # Only create context if there's actual header space
        if first_non_inline_top is not None and first_non_inline_top > builder.y_start:
            context_bounds = SliceBounds(
                top=builder.y_start,
                bottom=first_non_inline_top,
                left=0,
                right=composite_width,
            )
            
    # Convert tuple label_bbox to SliceBounds
    label_bbox = None
    if builder.label_bbox:
        l, t, r, b = builder.label_bbox
        label_bbox = SliceBounds(top=t, bottom=b, left=l, right=r)
    
    # Aggregate validation issues from builder
    validation_issues = []
    if builder.validation_note:
        validation_issues.append(builder.validation_note)
    
    # Check if any child is invalid - propagate to parent awareness (but don't invalidate parent)
    # The actual Part.is_valid is set from the builder's state
    
    return Part(
        label=builder.label,
        kind=builder.kind,
        marks=marks,
        bounds=bounds,
        context_bounds=context_bounds,
        label_bbox=label_bbox,
        children=children,
        is_valid=builder.is_valid,
        validation_issues=tuple(validation_issues),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6.10: Sequence Validation
# ─────────────────────────────────────────────────────────────────────────────

# Expected sequences
LETTER_SEQUENCE = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l']
ROMAN_SEQUENCE = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x', 'xi', 'xii']


def _validate_letter_builders(
    letter_builders: List[PartBuilder],
    question_num: int,
    exam_code: str = "",
    pdf_name: str = "",
    collector: Optional[DiagnosticsCollector] = None,
) -> None:
    """
    Validate letter sequence on PartBuilders and flag gaps.
    
    When a gap is detected (e.g., (a)->(c), missed (b)), the part BEFORE
    the gap is marked invalid because its boundary may be incorrect.
    
    1:1 ALIGNMENT: Sets is_valid=False, logs warning, AND records diagnostic.
    
    Args:
        letter_builders: List of PartBuilder for letters (root.children)
        question_num: Question number for logging
        exam_code: Exam code for diagnostics
        pdf_name: PDF name for diagnostics
        collector: DiagnosticsCollector for recording gaps
    """
    if len(letter_builders) < 2:
        return
    
    for i in range(len(letter_builders) - 1):
        curr = letter_builders[i]
        next_builder = letter_builders[i + 1]
        
        # Extract just the letter part from labels like "1(a)"
        try:
            curr_letter = curr.label.split('(')[1].rstrip(')')
            next_letter = next_builder.label.split('(')[1].rstrip(')')
            
            curr_idx = LETTER_SEQUENCE.index(curr_letter.lower())
            next_idx = LETTER_SEQUENCE.index(next_letter.lower())
            
            if next_idx > curr_idx + 1:
                # GAP DETECTED: Mark preceding part as invalid
                # Its y_end boundary may be incorrect (should have ended earlier)
                missed = LETTER_SEQUENCE[curr_idx + 1:next_idx]
                y_span = (curr.y_start, next_builder.y_start)
                
                # 1. Set is_valid = False
                curr.is_valid = False
                curr.validation_note = f"Boundary unreliable - missed letter(s): {', '.join(f'({m})' for m in missed)}"
                
                # 2. Log warning
                logger.warning(
                    f"Q{question_num}: Part {curr.label} marked INVALID due to letter gap "
                    f"({curr_letter})->({next_letter}), missed: {missed}"
                )
                
                # 3. Record diagnostic (1:1 alignment)
                if collector:
                    collector.add_letter_gap(
                        pdf_name=pdf_name,
                        exam_code=exam_code,
                        question_number=question_num,
                        current_label=curr_letter,
                        next_label=next_letter,
                        missed=missed,
                        y_span=y_span,
                        prev_y=curr.y_start,
                        prev_bbox=curr.label_bbox,
                        next_y=next_builder.y_start,
                        next_bbox=next_builder.label_bbox,
                    )
        except (ValueError, IndexError):
            # Label not in expected sequence or parse error, ignore
            pass




def _validate_letter_sequence(
    letters: List[PartLabel],
    question_num: int,
    exam_code: str = "",
    pdf_name: str = "",
    collector: Optional[DiagnosticsCollector] = None,
    text_extractor: Optional[TextExtractor] = None,
) -> List[str]:
    """
    Validate letter sequence and log gaps.
    
    Detects skipped letters like (a) → (c) which indicates missed (b).
    
    Returns:
        List of warning messages for gaps.
    """
    warnings = []
    if len(letters) < 2:
        return warnings
    
    for i in range(len(letters) - 1):
        curr = letters[i]
        next_label = letters[i + 1]
        
        try:
            curr_idx = LETTER_SEQUENCE.index(curr.label.lower())
            next_idx = LETTER_SEQUENCE.index(next_label.label.lower())
            
            if next_idx > curr_idx + 1:
                # Gap detected
                missed = LETTER_SEQUENCE[curr_idx + 1:next_idx]
                y_span_start = curr.y_position
                y_span_end = next_label.y_position
                
                msg = (
                    f"Q{question_num}: Detected letter gap ({curr.label}) → ({next_label.label}), "
                    f"missed: {', '.join(f'({m})' for m in missed)}. "
                    f"Y-span: {y_span_start} to {y_span_end} "
                    f"[{pdf_name}, {exam_code}]"
                )
                logger.warning(msg)
                warnings.append(msg)
                
                # Extract PDF content for diagnostics
                pdf_content = ""
                if text_extractor and y_span_start < y_span_end:
                    try:
                        pdf_content = text_extractor(y_span_start, y_span_end)
                        logger.info(f"[DIAG] Extracted {len(pdf_content)} chars for letter gap Y={y_span_start}-{y_span_end}")
                    except Exception as e:
                        logger.warning(f"[DIAG] Failed to extract text for gap: {e}")
                else:
                    logger.info(f"[DIAG] No text_extractor (has={text_extractor is not None}) or invalid y_span ({y_span_start}, {y_span_end})")
                
                # Record in diagnostics
                if collector:
                    collector.add_letter_gap(
                        pdf_name=pdf_name,
                        exam_code=exam_code,
                        question_number=question_num,
                        current_label=curr.label,
                        next_label=next_label.label,
                        missed=missed,
                        y_span=(y_span_start, y_span_end),
                        prev_y=curr.y_position,
                        prev_bbox=curr.bbox,
                        next_y=next_label.y_position,
                        next_bbox=next_label.bbox,
                        pdf_content=pdf_content,
                    )
        except ValueError:
            # Label not in expected sequence, ignore
            pass
    
    return warnings


def _validate_roman_sequence_for_letter(
    romans: List[PartBuilder],
    parent_label: str,
    question_num: int,
    exam_code: str = "",
    pdf_name: str = "",
    collector: Optional[DiagnosticsCollector] = None,
    text_extractor: Optional[TextExtractor] = None,
) -> List[str]:
    """
    Validate roman sequence under a letter and detect resets/gaps.
    
    Detects:
    - Resets: (i) → (ii) → (i) again = suggests missed parent
    - Gaps: (i) → (iii) = missed (ii)
    
    Returns:
        List of warning messages.
    """
    warnings = []
    if len(romans) < 2:
        return warnings
    
    prev_idx = -1
    for i, roman in enumerate(romans):
        # Extract just the roman numeral from label like "1(a)(ii)"
        roman_part = roman.label.split('(')[-1].rstrip(')')
        
        try:
            curr_idx = ROMAN_SEQUENCE.index(roman_part.lower())
        except ValueError:
            continue  # Unknown roman, skip
        
        if prev_idx >= 0:
            if curr_idx <= prev_idx:
                # Reset detected! This could mean missed parent letter
                # Mark this and remaining romans as potentially invalid
                y_pos = roman.y_start
                prev_roman = romans[i - 1]
                prev_y = prev_roman.y_start
                
                msg = (
                    f"Q{question_num}: Roman reset detected in {parent_label}: "
                    f"({ROMAN_SEQUENCE[prev_idx]}) → ({roman_part}). "
                    f"Missed parent label between Y={prev_y} and Y={y_pos}. "
                    f"[{pdf_name}, {exam_code}]"
                )
                logger.warning(msg)
                warnings.append(msg)
                
                # Mark this roman as invalid
                roman.is_valid = False
                roman.validation_note = f"Orphaned - parent label likely missed before Y={y_pos}"
                
                # Extract PDF content for diagnostics
                pdf_content = ""
                if text_extractor and prev_y < y_pos:
                    try:
                        pdf_content = text_extractor(prev_y, y_pos)
                        logger.info(f"[DIAG] Extracted {len(pdf_content)} chars for roman reset Y={prev_y}-{y_pos}")
                    except Exception as e:
                        logger.warning(f"[DIAG] Failed to extract text for reset: {e}")
                else:
                    logger.info(f"[DIAG] No text_extractor (has={text_extractor is not None}) or invalid y_span ({prev_y}, {y_pos})")
                
                # Record in diagnostics
                if collector:
                    collector.add_roman_reset(
                        pdf_name=pdf_name,
                        exam_code=exam_code,
                        question_number=question_num,
                        parent_label=parent_label,
                        prev_roman=ROMAN_SEQUENCE[prev_idx],
                        reset_roman=roman_part,
                        y_span=(prev_y, y_pos),
                        prev_y=prev_y,
                        prev_bbox=prev_roman.label_bbox,
                        next_y=y_pos,
                        next_bbox=roman.label_bbox,
                        pdf_content=pdf_content,
                    )
                
            elif curr_idx > prev_idx + 1:
                # Gap detected
                missed = ROMAN_SEQUENCE[prev_idx + 1:curr_idx]
                prev_roman = romans[i - 1]
                y_span_start = prev_roman.y_start
                y_span_end = roman.y_start
                
                msg = (
                    f"Q{question_num}: Roman gap in {parent_label}: "
                    f"({ROMAN_SEQUENCE[prev_idx]}) → ({roman_part}), "
                    f"missed: {', '.join(f'({m})' for m in missed)}. "
                    f"Y-span: {y_span_start} to {y_span_end} "
                    f"[{pdf_name}, {exam_code}]"
                )
                logger.warning(msg)
                warnings.append(msg)
                
                # Extract PDF content for diagnostics
                pdf_content = ""
                if text_extractor and y_span_start < y_span_end:
                    try:
                        pdf_content = text_extractor(y_span_start, y_span_end)
                    except Exception as e:
                        logger.debug(f"Failed to extract text for gap: {e}")
                
                # Record in diagnostics
                if collector:
                    collector.add_roman_gap(
                        pdf_name=pdf_name,
                        exam_code=exam_code,
                        question_number=question_num,
                        parent_label=parent_label,
                        current_roman=ROMAN_SEQUENCE[prev_idx],
                        next_roman=roman_part,
                        missed=missed,
                        y_span=(y_span_start, y_span_end),
                        prev_y=y_span_start,
                        prev_bbox=prev_roman.label_bbox,
                        next_y=y_span_end,
                        next_bbox=roman.label_bbox,
                        pdf_content=pdf_content,
                    )
        
        prev_idx = curr_idx
    
    return warnings
