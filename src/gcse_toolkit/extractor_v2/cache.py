"""
Module: extractor_v2.cache

Purpose:
    Page render caching for extraction pipeline optimization.
    Caches full-page renders to avoid re-rendering the same page
    for multiple questions.

Key Classes:
    - PageRenderCache: LRU cache for rendered page images

Dependencies:
    - PIL.Image: Image handling
    - fitz (PyMuPDF): PDF rendering

Used By:
    - extractor_v2.pipeline: Caches page renders during extraction

OPTIMIZATION #4: Page Pixmap Caching
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple, Optional

from PIL import Image
import fitz

logger = logging.getLogger(__name__)


class PageRenderCache:
    """
    LRU cache for rendered page images.
    
    Caches full-page renders to avoid re-rendering the same page
    for multiple questions. Most effective for papers with many
    short questions on a single page (e.g., Mathematics).
    
    Attributes:
        max_pages: Maximum number of pages to cache.
        
    Example:
        >>> cache = PageRenderCache(max_pages=16)
        >>> img = cache.get_or_render(doc, 0, 200)
        >>> img2 = cache.get_or_render(doc, 0, 200)  # Cache hit
    """
    
    def __init__(self, max_pages: int = 16):
        """
        Initialize cache with maximum page limit.
        
        Args:
            max_pages: Maximum pages to cache (~3MB each at 200 DPI).
                      Default 16 = ~50MB max memory.
        """
        self._cache: Dict[Tuple[int, int], Image.Image] = {}
        self._max_pages = max_pages
        self._access_order: list = []  # For LRU eviction
        self._doc_id: Optional[str] = None
    
    def set_document(self, doc_path: str) -> None:
        """
        Set the current document. Clears cache if document changes.
        
        Args:
            doc_path: Path to the current PDF document.
        """
        if self._doc_id != doc_path:
            self.clear()
            self._doc_id = doc_path
    
    def get_or_render(
        self,
        doc: fitz.Document,
        page_idx: int,
        dpi: int,
    ) -> Image.Image:
        """
        Get cached page render or create new one.
        
        Args:
            doc: Open PyMuPDF document.
            page_idx: 0-indexed page number.
            dpi: Resolution for rendering.
            
        Returns:
            Full-page grayscale image.
        """
        key = (page_idx, dpi)
        
        if key in self._cache:
            # Move to end (most recently used)
            self._access_order.remove(key)
            self._access_order.append(key)
            logger.debug(f"Cache HIT: page {page_idx} at {dpi} DPI")
            return self._cache[key]
        
        # Render full page
        page = doc[page_idx]
        matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        
        # OPTIMIZATION #1: Direct grayscale rendering
        pix = page.get_pixmap(
            matrix=matrix,
            alpha=False,
            colorspace=fitz.csGRAY
        )
        image = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        
        # Cache with LRU eviction
        if len(self._cache) >= self._max_pages:
            oldest = self._access_order.pop(0)
            del self._cache[oldest]
            logger.debug(f"Cache EVICT: page {oldest[0]} at {oldest[1]} DPI")
        
        self._cache[key] = image
        self._access_order.append(key)
        logger.debug(f"Cache MISS: rendered page {page_idx} at {dpi} DPI")
        
        return image
    
    def crop_region(
        self,
        page_idx: int,
        dpi: int,
        clip: fitz.Rect,
        page_rect: fitz.Rect,
    ) -> Tuple[Image.Image, Tuple[int, int]]:
        """
        Crop a region from a cached full-page render.
        
        Args:
            page_idx: Page index (must be cached).
            dpi: DPI of the cached render.
            clip: Region to crop (in PDF points).
            page_rect: Full page rectangle (in PDF points).
            
        Returns:
            Tuple of (cropped_image, trim_offset).
            
        Raises:
            KeyError: If page is not cached.
        """
        key = (page_idx, dpi)
        if key not in self._cache:
            raise KeyError(f"Page {page_idx} at {dpi} DPI not in cache")
        
        full_page = self._cache[key]
        scale = dpi / 72.0
        
        # Convert clip to pixel coordinates
        left = int((clip.x0 - page_rect.x0) * scale)
        top = int((clip.y0 - page_rect.y0) * scale)
        right = int((clip.x1 - page_rect.x0) * scale)
        bottom = int((clip.y1 - page_rect.y0) * scale)
        
        # Clamp to image bounds
        left = max(0, left)
        top = max(0, top)
        right = min(full_page.width, right)
        bottom = min(full_page.height, bottom)
        
        cropped = full_page.crop((left, top, right, bottom))
        
        # Return 0,0 trim offset since we're not trimming whitespace here
        # (that's done separately if needed)
        return cropped, (0, 0)
    
    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._access_order.clear()
        logger.debug("Cache cleared")
    
    @property
    def size(self) -> int:
        """Number of pages currently cached."""
        return len(self._cache)
    
    @property
    def hit_rate(self) -> str:
        """Return cache statistics as string."""
        return f"Cache: {self.size}/{self._max_pages} pages"
