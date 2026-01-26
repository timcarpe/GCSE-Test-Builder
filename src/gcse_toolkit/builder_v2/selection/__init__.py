"""
Module: builder_v2.selection

Purpose:
    Question selection algorithm for building exams. Selects questions
    and parts to meet a target mark total while respecting topic coverage
    and other constraints.

Key Functions:
    - select_questions(): Main entry point for selection
    - generate_options(): Generate valid selection options per question

Key Classes:
    - SelectionConfig: Configuration for selection algorithm
    - Selector: Main selection orchestrator

Dependencies:
    - gcse_toolkit.core.models: Question, Part, SelectionPlan, SelectionResult
    - builder_v2.loading: Question loading

Used By:
    - builder_v2.controller: Main build controller
    - gcse_toolkit.gui: GUI integration
"""

from .config import SelectionConfig
from .selector import select_questions, Selector
from .options import generate_options, QuestionOptions
from .pruning import prune_to_target
from .part_mode import PartMode

__all__ = [
    "SelectionConfig",
    "select_questions",
    "Selector",
    "generate_options",
    "QuestionOptions",
    "prune_to_target",
    "PartMode",
]
