"""
Module: builder_v2.selection.part_mode

Purpose:
    Enum defining how sub-question parts can be selected/excluded
    during the question selection process.

Key Classes:
    - PartMode: Three-state enum for part selection behavior

Used By:
    - builder_v2.selection.config: SelectionConfig
    - builder_v2.selection.options: generate_options
    - builder_v2.selection.selector: Selector
"""

from enum import Enum, auto


class PartMode(Enum):
    """
    Controls how sub-question parts can be selected/excluded.
    
    This is a hierarchical setting where each mode is more permissive
    than the previous: ALL ⊂ PRUNE ⊂ SKIP
    
    Attributes:
        ALL: No partial selection allowed. Only full questions (all matching
             parts) can be selected. Useful when you want complete questions.
        PRUNE: Remove parts from the end only (contiguous suffix subsets).
               E.g., for parts (a)(b)(c), valid options are: {a,b,c}, {a,b}, {a}.
               Maintains question structure integrity.
        SKIP: Remove parts from anywhere (all combinations).
              E.g., for parts (a)(b)(c), valid options include: {a,c}, {b}, etc.
              Maximum flexibility but may disrupt question flow.
    
    Example:
        >>> from gcse_toolkit.builder_v2.selection.part_mode import PartMode
        >>> mode = PartMode.PRUNE
        >>> mode == PartMode.ALL
        False
    """
    
    ALL = auto()    # No partial selection - include all matching parts
    PRUNE = auto()  # Remove from end only (contiguous suffix subsets)
    SKIP = auto()   # Remove from anywhere (all combinations)
