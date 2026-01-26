"""
Module: builder_v2.loading.reconstructor

Purpose:
    Reconstruct the Part tree from parsed regions.json data.
    Creates immutable Part objects with proper parent/child relationships.

Key Functions:
    - reconstruct_part_tree(): Build Part tree from parsed regions
    - validate_part_tree(): Validate tree consistency

Key Classes:
    - ValidationError: Exception for invalid tree structure

Dependencies:
    - gcse_toolkit.core.models: Part, Marks, SliceBounds

Used By:
    - builder_v2.loading.loader: Question loading
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from gcse_toolkit.core.models import Part, Marks, SliceBounds
from gcse_toolkit.core.models.parts import PartKind

from .parser import ParsedRegion, ParsedRegions

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Error validating data structure."""
    pass


def reconstruct_part_tree(
    regions: ParsedRegions,
    *,
    marks_data: Optional[Dict[str, int]] = None,
) -> Part:
    """
    Reconstruct Part tree from parsed regions.
    
    Algorithm:
    1. Index regions by label
    2. Extract marks from regions (if available)
    3. Build parent/child relationships from label structure
    4. Create Parts bottom-up (leaves first, then parents)
    5. Assign marks (from regions, data override, or infer)
    
    Args:
        regions: Parsed regions data
        marks_data: Optional dict mapping labels to mark values (overrides)
        
    Returns:
        Root Part with children populated
        
    Raises:
        ValidationError: If tree structure invalid
        
    Example:
        >>> tree = reconstruct_part_tree(regions)
        >>> tree.label
        '1'
        >>> len(tree.children)
        3
    """
    if not regions.regions:
        raise ValidationError("No regions to reconstruct")
    
    # Build marks data from regions if not provided
    if marks_data is None:
        marks_data = {}
        for region in regions.regions:
            if region.marks is not None:
                marks_data[region.label] = region.marks
    
    # Build label -> region mapping
    region_map: Dict[str, ParsedRegion] = {r.label: r for r in regions.regions}
    
    # Find root label (shortest, usually question number)
    root_label = min(region_map.keys(), key=lambda l: (l.count("("), l))
    
    # Build tree recursively
    return _build_part(root_label, region_map, marks_data, regions.composite_width)


def _build_part(
    label: str,
    region_map: Dict[str, ParsedRegion],
    marks_data: Dict[str, int],
    composite_width: int,
) -> Part:
    """Build a Part and its children recursively."""
    region = region_map.get(label)
    if region is None:
        raise ValidationError(f"No region found for label: {label}")
    
    # Find children
    children_labels = _find_children(label, set(region_map.keys()))
    
    # Build children first (bottom-up)
    children = tuple(
        _build_part(child_label, region_map, marks_data, composite_width)
        for child_label in sorted(children_labels, key=_label_sort_key)
    )
    
    # Create bounds
    bounds = SliceBounds(
        top=region.top,
        bottom=region.bottom,
        left=region.left,
        right=region.right,
    )
    
    # Determine kind
    kind = _parse_kind(region.kind)
    
    # Determine marks
    if label in marks_data:
        marks = Marks.explicit(marks_data[label])
    elif children:
        marks = Marks.aggregate(children)
    else:
        marks = Marks.inferred(0)
    
    # Calculate context_bounds for parent parts (QUESTION and LETTER with children)
    # Phase 6.9.1: Use hierarchical left from part.bounds, not region.left
    # Phase 6.9.1.2: Use minimum right bound from ALL descendants (not just immediate children)
    context_bounds = None
    if children and kind in (PartKind.QUESTION, PartKind.LETTER):
        # Use parent's own bounds - the header portion only
        # This prevents context from overlapping into the first child's region
        if region.bottom > region.top:
            # Phase 6.9.1.2: Collect rights from all leaf descendants
            def collect_leaf_rights(part: Part) -> List[int]:
                """Recursively collect right bounds from all leaf descendants."""
                if not part.children:
                    # Leaf part - return its right
                    return [part.bounds.right]
                # Non-leaf - recurse to all children
                rights = []
                for child in part.children:
                    rights.extend(collect_leaf_rights(child))
                return rights
            
            # Get all leaf rights from this parent's tree
            all_leaf_rights = []
            for child in children:
                all_leaf_rights.extend(collect_leaf_rights(child))
            
            context_right = min(all_leaf_rights) if all_leaf_rights else bounds.right
            
            context_bounds = SliceBounds(
                top=region.top,
                bottom=region.bottom,  # Parent's natural end, not first_child.top
                left=bounds.left,      # Phase 6.9.1: Use hierarchical left!
                right=context_right,   # Phase 6.9.1.2: Min of ALL leaves!
            )
    
    return Part(
        label=label,
        kind=kind,
        marks=marks,
        bounds=bounds,
        context_bounds=context_bounds,
        children=children,
    )


def _find_children(parent_label: str, all_labels: set) -> List[str]:
    """
    Find direct children of a parent label.
    
    Parent "1" has direct children "1(a)", "1(b)", etc.
    Parent "1(a)" has direct children "1(a)(i)", "1(a)(ii)", etc.
    """
    children = []
    parent_depth = parent_label.count("(")
    
    for label in all_labels:
        if label == parent_label:
            continue
        
        # Check if this is a direct child
        label_depth = label.count("(")
        if label_depth != parent_depth + 1:
            continue
        
        # Check if label starts with parent
        if not label.startswith(parent_label):
            continue
        
        # Ensure no intermediate parent (e.g., "1(a)(i)" is not child of "1")
        expected_prefix = parent_label if parent_depth == 0 else parent_label
        if label.startswith(expected_prefix):
            children.append(label)
    
    return children


def _label_sort_key(label: str) -> tuple:
    """
    Sort key for part labels.
    
    Sorts letters alphabetically (a-z), romans numerically (i-x).
    
    A label segment is a roman numeral if it:
    - Contains only i, v, x characters (case-insensitive)
    
    A label segment is a letter if it:
    - Is a single character a-z (excluding i, v, x)
    
    Examples:
        "1(a)" < "1(b)" < "1(a)(i)" < "1(a)(ii)" < "1(a)(v)"
    """
    # Extract parts between parentheses
    parts = re.findall(r"\(([^)]+)\)", label)
    
    result = []
    for part in parts:
        # Check if it's a roman numeral (only i, v, x characters)
        part_lower = part.lower()
        roman_chars = {'i', 'v', 'x'}
        is_roman = all(c in roman_chars for c in part_lower)
        
        if part.isalpha() and len(part) == 1 and not is_roman:
            # Letter: a=0, b=1, etc. (excludes i, v, x)
            result.append((0, ord(part.lower()) - ord('a')))
        else:
            # Roman numeral: convert to number
            result.append((1, _roman_to_int(part)))
    
    return tuple(result)


def _roman_to_int(s: str) -> int:
    """Convert roman numeral to integer."""
    roman_map = {'i': 1, 'v': 5, 'x': 10}
    s = s.lower()
    result = 0
    prev = 0
    for c in reversed(s):
        curr = roman_map.get(c, 0)
        if curr < prev:
            result -= curr
        else:
            result += curr
        prev = curr
    return result


def _parse_kind(kind_str: str) -> PartKind:
    """Parse kind string to PartKind enum."""
    kind_map = {
        "question": PartKind.QUESTION,
        "letter": PartKind.LETTER,
        "roman": PartKind.ROMAN,
    }
    return kind_map.get(kind_str.lower(), PartKind.QUESTION)


def validate_part_tree(root: Part) -> List[str]:
    """
    Validate a Part tree for consistency.
    
    Checks:
    - No overlapping bounds between siblings
    - Children within parent bounds
    - Marks are non-negative
    - Labels are unique
    
    Args:
        root: Root Part to validate
        
    Returns:
        List of warning messages (empty if valid)
        
    Example:
        >>> warnings = validate_part_tree(tree)
        >>> len(warnings)
        0
    """
    warnings = []
    seen_labels = set()
    
    def _validate_node(part: Part, parent_bounds: Optional[SliceBounds] = None) -> None:
        # Check unique label
        if part.label in seen_labels:
            warnings.append(f"Duplicate label: {part.label}")
        seen_labels.add(part.label)
        
        # Check marks non-negative
        if part.marks.value < 0:
            warnings.append(f"Negative marks for {part.label}: {part.marks.value}")
        
        # Check within parent bounds
        if parent_bounds:
            if part.bounds.top < parent_bounds.top:
                warnings.append(f"{part.label} top {part.bounds.top} above parent {parent_bounds.top}")
            if part.bounds.bottom > parent_bounds.bottom:
                warnings.append(f"{part.label} bottom {part.bounds.bottom} below parent {parent_bounds.bottom}")
        
        # Check sibling overlap
        for i, child in enumerate(part.children):
            for j, other in enumerate(part.children):
                if i >= j:
                    continue
                if child.bounds.overlaps(other.bounds):
                    warnings.append(f"Overlapping siblings: {child.label} and {other.label}")
        
        # Recurse
        for child in part.children:
            _validate_node(child, part.bounds)
    
    _validate_node(root)
    return warnings
