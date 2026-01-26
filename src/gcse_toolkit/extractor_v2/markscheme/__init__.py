"""
Module: extractor_v2.markscheme

Purpose:
    Markscheme extraction from markscheme PDFs. Scans MS PDF to
    identify which pages contain which questions, then extracts them.

Key Functions:
    - map_ms_pages_to_questions(): Scan MS PDF and detect questions
    - extract_markscheme_for_question(): Extract MS pages for one question
    - find_markscheme_pdf(): Locate matching MS PDF file

Dependencies:
    - fitz (pymupdf): PDF rendering and OCR
    - numpy: Image trimming

Used By:
    - extractor_v2.pipeline: MS extraction during processing
"""

from .extractor import (
    extract_markscheme_for_question,
    find_markscheme_pdf,
    map_ms_pages_to_questions,
)

__all__ = [
    "extract_markscheme_for_question",
    "find_markscheme_pdf",
    "map_ms_pages_to_questions",
]
