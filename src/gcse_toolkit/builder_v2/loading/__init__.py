"""
Module: builder_v2.loading

Purpose:
    Question loading and parsing from the V2 cache format.
    Reconstructs Question objects from extracted files.

Key Functions:
    - load_questions(): Load all questions for an exam code
    - load_single_question(): Load a single question from directory
    - parse_metadata(): Parse metadata.json
    - parse_regions(): Parse regions.json

Dependencies:
    - gcse_toolkit.core.models: V2 data models
    - gcse_toolkit.core.schemas.validator: Schema validation

Used By:
    - builder_v2.controller: Main build controller
"""

from .loader import (
    load_questions,
    load_single_question,
    discover_questions,
    discover_questions_with_metadata,
    LoaderError
)
from .parser import parse_metadata, parse_regions, ParseError
from .reconstructor import reconstruct_part_tree, ValidationError

__all__ = [
    "load_questions",
    "load_single_question",
    "discover_questions",
    "discover_questions_with_metadata",
    "LoaderError",
    "parse_metadata",
    "parse_regions",
    "ParseError",
    "reconstruct_part_tree",
    "ValidationError",
]
