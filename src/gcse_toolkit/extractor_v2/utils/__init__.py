"""
Module: extractor_v2.utils

Purpose:
    Utility subpackage with shared helpers for PDF rendering
    and image manipulation.

Key Modules:
    - pdf: PDF page rendering and text extraction
    - image: Image trimming and manipulation
    - detection: Exam code extraction from filenames

Dependencies:
    - fitz (PyMuPDF): PDF operations
    - PIL: Image operations

Used By:
    - extractor_v2.pipeline: Uses utils for rendering
    - extractor_v2.detection: Uses utils for text extraction
    - gui_v2.utils.helpers: Uses exam_code for PDF scanning
"""

from .detection import exam_code

__all__ = ["exam_code"]
