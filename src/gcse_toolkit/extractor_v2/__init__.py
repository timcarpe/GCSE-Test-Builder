"""
Module: extractor_v2

Purpose:
    V2 extraction pipeline for processing exam PDFs into questions with
    composite images and region metadata. Uses immutable data models from
    core.models and outputs CompositeOnly format.

Key Functions:
    - extract_question_paper(): Main entry point for extraction
    
Key Classes:
    - ExtractionConfig: Configuration for extraction settings
    - ExtractionResult: Container for extraction output

Dependencies:
    - fitz (PyMuPDF): PDF rendering and text extraction
    - PIL: Image manipulation
    - gcse_toolkit.core.models: V2 data models (Part, Marks, SliceBounds)

Used By:
    - gcse_toolkit.gui_v2.tabs.extract_tab: GUI extraction interface
"""

from .config import ExtractionConfig, SliceConfig
from .pipeline import extract_question_paper, ExtractionResult

__all__ = [
    "extract_question_paper",
    "ExtractionConfig",
    "ExtractionResult",
    "SliceConfig",
]
