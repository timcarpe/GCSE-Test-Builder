"""
Module: builder_v2.output

Purpose:
    PDF rendering and output generation for V2 builder.
    Converts LayoutResult to PDF files using ReportLab.

Key Functions:
    - render_to_pdf(): Render layout to PDF
    - render_markscheme(): Generate markscheme PDF

Dependencies:
    - reportlab: PDF generation
    - PIL: Image handling
    - builder_v2.layout.models: LayoutResult

Used By:
    - builder_v2.controller: Pipeline orchestration
"""

from .renderer import render_to_pdf
from .markscheme import render_markscheme

__all__ = [
    "render_to_pdf",
    "render_markscheme",
]
