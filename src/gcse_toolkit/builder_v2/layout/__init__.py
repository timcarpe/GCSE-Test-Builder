"""
Module: builder_v2.layout

Purpose:
    Page layout and composition for exam building.
    Converts selected questions into positioned page layouts.

Key Functions:
    - compose_exam(): Main entry point for layout
    - paginate(): Arrange assets onto pages

Key Classes:
    - LayoutConfig: Configuration for page layout
    - SliceAsset: Renderable image slice
    - PagePlan: Single page layout plan

Dependencies:
    - PIL: Image manipulation
    - gcse_toolkit.core.models: Question, SelectionResult
    - builder_v2.images: ImageProvider, cropper

Used By:
    - builder_v2.controller: Main build controller
    - Phase 7 GUI integration
"""

from .config import LayoutConfig
from .models import SliceAsset, SlicePlacement, PagePlan, LayoutResult
from .composer import compose_question, compose_exam
from .paginator import paginate

__all__ = [
    # Config
    "LayoutConfig",
    # Models
    "SliceAsset",
    "SlicePlacement",
    "PagePlan",
    "LayoutResult",
    # Functions
    "compose_question",
    "compose_exam",
    "paginate",
]
