"""
Module: extractor_v2.detection

Purpose:
    Detection subpackage for identifying question elements in PDFs.
    Contains modules for detecting question numerals, part labels,
    and mark allocations.

Key Modules:
    - numerals: Question number detection (1, 2, 3...)
    - parts: Part label detection ((a), (i), etc.)
    - marks: Mark box detection ([N] patterns)

Dependencies:
    - fitz (PyMuPDF): Text extraction from PDFs

Used By:
    - extractor_v2.pipeline: Orchestrates detection modules
"""
