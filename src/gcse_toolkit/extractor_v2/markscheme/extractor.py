"""
Module: extractor_v2.markscheme.extractor

Purpose:
    Extract markscheme pages for questions from markscheme PDFs.
    Scans MS PDF to detect which pages contain which questions.

Key Functions:
    - extract_markscheme_for_question(): Extract MS pages for one question
    - map_ms_pages_to_questions(): Scan MS PDF and detect all questions

Dependencies:
    - fitz: PDF access and rendering
    - PIL: Image saving
    - numpy: Image trimming

Used By:
    - extractor_v2.pipeline: Called per question

Prior Reference:
    Directly ported from extractor/v2/mark_scheme.py::MarkSchemeSaver
    VERIFIED: 2025-12-14
    Decision: EXACT PORT with V2 API
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

import fitz
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Regex patterns (verified exact match)
QUESTION_HEADER_PATTERN = re.compile(r"(?i)question\s+(\d{1,2})")
QUESTION_LINE_WITH_PARTS = re.compile(r"(?im)^\s*(\d{1,2})(\s*\([a-z]+\))+")
QUESTION_TABLE_HEADER = re.compile(r"(?i)question\s+answer\s+marks\s+(\d{1,2})")


def extract_markscheme_for_question(
    ms_pdf_path: Path,
    question_number: int,
    ms_page_indices: List[int],
    output_dir: Path,
    *,
    dpi: int = 200,
) -> Optional[Path]:
    """
    Extract markscheme pages for a specific question.
    
    Renders the specified MS pages, converts to grayscale,
    trims whitespace, and stitches if multiple pages.
    
    Args:
        ms_pdf_path: Path to markscheme PDF
        question_number: Question number (1, 2, 3, etc.)
        ms_page_indices: List of page indices in MS PDF (0-indexed)
        output_dir: Directory to save image
        dpi: Resolution for rendering
        
    Returns:
        Path to saved MS image, or None if failed
        
    Example:
        # If Q1 is on MS pages 0 and 1:
        >>> extract_markscheme_for_question(
        ...     Path("0478_s25_ms_11.pdf"),
        ...     question_number=1,
        ...     ms_page_indices=[0, 1],
        ...     output_dir=Path("cache/0478_s25_qp_11_q1")
        ... )
        PosixPath('cache/0478_s25_qp_11_q1/0478_s25_qp_11_q1_ms.png')
    """
    if not ms_pdf_path.exists():
        logger.warning(f"Markscheme PDF not found: {ms_pdf_path}")
        return None
    
    if not ms_page_indices:
        logger.debug(f"No MS pages for question {question_number}")
        return None
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        with fitz.open(ms_pdf_path) as doc:
            # Import render utility (uses grayscale colorspace directly)
            from gcse_toolkit.extractor_v2.utils.pdf import render_page_region
            
            images = []
            
            for page_idx in ms_page_indices:
                if page_idx >= doc.page_count:
                    logger.warning(f"Page {page_idx} out of range in {ms_pdf_path.name}")
                    continue
                
                page = doc[page_idx]
                
                # Use shared render function (already optimized for grayscale)
                # Pass full page rect as clip to render entire page
                img, _ = render_page_region(
                    page,
                    page.rect,
                    dpi=dpi,
                    trim_whitespace=True,
                )
                images.append(img)
                
                logger.debug(f"Rendered MS page {page_idx} for Q{question_number}")
            
            if not images:
                return None
            
            # Stitch images vertically if multiple pages
            stitched = _stitch_images(images) if len(images) > 1 else images[0]
            
            # Save with compatible filename
            image_path = output_dir / f"{output_dir.name}_ms.png"
            stitched.save(image_path, "PNG", optimize=True)
            
            logger.debug(f"Saved MS for Q{question_number}: {len(ms_page_indices)} page(s) → {image_path.name}")
            return image_path
            
    except Exception as e:
        logger.error(f"Failed to extract MS for Q{question_number}: {e}")
        return None


def map_ms_pages_to_questions(
    ms_pdf_path: Path,
    question_numbers: Set[int],
) -> Dict[int, List[int]]:
    """
    Scan markscheme PDF and detect which pages contain which questions.
    
    Uses OCR text extraction and regex patterns to identify
    question numbers on each page.
    
    Args:
        ms_pdf_path: Path to markscheme PDF
        question_numbers: Set of question numbers to look for
        
    Returns:
        Dict mapping question_number → list of page indices
        
    Example:
        >>> map_ms_pages_to_questions(
        ...     Path("0478_s25_ms_11.pdf"),
        ...     {1, 2, 3, 4, 5, 6, 7, 8, 9}
        ... )
        {1: [0], 2: [1, 2], 3: [2], 4: [3, 4], ...}
        
    Algorithm:
        1. For each page in MS PDF:
           a. Extract text
           b. Find question numbers using regex patterns
           c. Map page to those questions
        2. If no questions found on a page, use last found questions
        3. Return mapping
    """
    if not ms_pdf_path.exists():
        logger.warning(f"Markscheme PDF not found: {ms_pdf_path}")
        return {}
    
    mapping: Dict[int, List[int]] = {}
    last_tokens: Set[int] = set()
    
    try:
        with fitz.open(ms_pdf_path) as doc:
            for page_idx in range(doc.page_count):
                page = doc[page_idx]
                
                # Extract text and find question numbers
                tokens = _find_question_tokens_on_page(page, question_numbers)
                
                # If no tokens found, use last page's tokens (continuation)
                if not tokens:
                    tokens = last_tokens
                
                if not tokens:
                    continue
                
                # Map each question number to this page
                for qnum in tokens:
                    mapping.setdefault(qnum, []).append(page_idx)
                
                last_tokens = tokens
            
            logger.info(f"Mapped {len(mapping)} questions across {doc.page_count} MS pages")
            return mapping
            
    except Exception as e:
        logger.error(f"Failed to map MS pages: {e}")
        return {}


def _find_question_tokens_on_page(
    page: fitz.Page,
    available_qnums: Set[int],
) -> Set[int]:
    """
    Find question numbers mentioned on a page using OCR.
    
    Uses three regex patterns:
    1. "Question N" headers
    2. "N(a)" style line prefixes  
    3. "Question Answer Marks N" table headers
    """
    tokens: Set[int] = set()
    text = page.get_text("text") or ""
    
    # Pattern 1: "Question N"
    for match in QUESTION_HEADER_PATTERN.finditer(text):
        value = int(match.group(1))
        if value in available_qnums:
            tokens.add(value)
    
    # Pattern 2: "N(a)" at start of line
    for match in QUESTION_LINE_WITH_PARTS.finditer(text):
        value = int(match.group(1))
        if value in available_qnums:
            tokens.add(value)
    
    # Pattern 3: Table header "Question Answer Marks N"
    for match in QUESTION_TABLE_HEADER.finditer(text):
        value = int(match.group(1))
        if value in available_qnums:
            tokens.add(value)
    
    return tokens


def _trim_whitespace(img: Image.Image, padding: int = 10) -> Image.Image:
    """
    Trim whitespace from grayscale image.
    
    Removes margins by finding content boundaries.
    Ported from original mark_scheme.py.
    """
    arr = np.array(img)
    
    # Calculate threshold (98th percentile or minimum 250)
    threshold = max(250, int(np.percentile(arr, 98)))
    
    # Find pixels darker than threshold (content)
    mask = arr < threshold
    
    if not mask.any():
        return img
    
    # Find bounding box of content
    ys, xs = np.where(mask)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    
    # Add padding
    left = max(0, x0 - padding)
    right = min(img.width, x1 + padding)
    top = max(0, y0 - padding)
    bottom = min(img.height, y1 + padding)
    
    if right <= left or bottom <= top:
        return img
    
    return img.crop((left, top, right, bottom))


def _stitch_images(images: List[Image.Image]) -> Image.Image:
    """
    Stitch multiple images vertically.
    
    Creates single tall image from list of images.
    Ported from original mark_scheme.py.
    """
    if len(images) == 1:
        return images[0]
    
    # Calculate total dimensions
    width = max(img.width for img in images)
    height = sum(img.height for img in images)
    
    # Create canvas (white background for grayscale)
    canvas = Image.new("L", (width, height), 255)
    
    # Paste images vertically
    offset = 0
    for img in images:
        canvas.paste(img, (0, offset))
        offset += img.height
    
    return canvas


def find_markscheme_pdf(
    question_pdf_path: Path,
    search_dirs: Optional[List[Path]] = None,
) -> Optional[Path]:
    """
    Find matching markscheme PDF for a question paper.
    
    Looks for PDF with same code but 'ms' instead of 'qp'.
    If not in same directory, searches optional search_dirs.
    
    Args:
        question_pdf_path: Path to question paper PDF
        search_dirs: Optional additional directories to search
        
    Returns:
        Path to markscheme PDF if found, None otherwise
        
    Example:
        >>> find_markscheme_pdf(Path("input/0478_s25_qp_11.pdf"))
        PosixPath('input/0478_s25_ms_11.pdf')
    """
    # Convert qp -> ms in filename
    ms_name = question_pdf_path.stem.replace("_qp_", "_ms_") + ".pdf"
    
    # Check same directory first
    ms_path = question_pdf_path.parent / ms_name
    if ms_path.exists():
        return ms_path
    
    # Check additional directories
    if search_dirs:
        for directory in search_dirs:
            ms_path = directory / ms_name
            if ms_path.exists():
                return ms_path
    
    return None
