"""
Module: builder_v2

Purpose:
    V2 building pipeline for generating exam papers from extracted questions.
    Loads questions from the V2 cache format (composite images + regions.json),
    selects questions to meet mark targets, and renders to PDF/images.

Key Functions:
    - load_questions(): Load questions from cache
    - select_questions(): Select questions to meet mark target
    - build_exam(): Main entry point for exam generation (Phase 6)

Key Classes:
    - BuilderConfig: Configuration for building
    - SelectionConfig: Configuration for selection algorithm
    - ImageProvider: Abstract image access

Dependencies:
    - PIL: Image manipulation
    - gcse_toolkit.core.models: V2 data models (Question, Part, Marks)
    - gcse_toolkit.core.schemas.validator: Schema validation

Used By:
    - gcse_toolkit.gui.tabs.build_tab: GUI build interface
"""

from .config import BuilderConfig
from .loading.loader import load_questions, load_single_question, LoaderError
from .selection import SelectionConfig, select_questions
from .controller import build_exam, BuildResult, BuildError

__all__ = [
    # Config
    "BuilderConfig",
    "SelectionConfig",
    # Loading
    "load_questions",
    "load_single_question",
    "LoaderError",
    # Selection
    "select_questions",
    # Controller
    "build_exam",
    "BuildResult",
    "BuildError",
]

