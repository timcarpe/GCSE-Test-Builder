"""Unit tests for markscheme extraction."""

import pytest
from pathlib import Path
from PIL import Image
import fitz

from gcse_toolkit.extractor_v2.markscheme.extractor import (
    find_markscheme_pdf,
    extract_markscheme_for_question,
)


class TestFindMarkschemePDF:
    """Tests for markscheme PDF discovery."""
    
    def test_finds_ms_in_same_directory(self, tmp_path):
        """Finds MS PDF in same directory as QP."""
        # Arrange
        qp_path = tmp_path / "0478_s25_qp_11.pdf"
        ms_path = tmp_path / "0478_s25_ms_11.pdf"
        qp_path.touch()
        ms_path.touch()
        
        # Act
        result = find_markscheme_pdf(qp_path)
        
        #Assert
        assert result == ms_path
    
    def test_finds_ms_in_search_dirs(self, tmp_path):
        """Finds MS PDF in additional search directory."""
        # Arrange
        qp_dir = tmp_path / "qp"
        ms_dir = tmp_path / "ms"
        qp_dir.mkdir()
        ms_dir.mkdir()
        
        qp_path = qp_dir / "0478_s25_qp_11.pdf"
        ms_path = ms_dir / "0478_s25_ms_11.pdf"
        qp_path.touch()
        ms_path.touch()
        
        # Act
        result = find_markscheme_pdf(qp_path, [ms_dir])
        
        # Assert
        assert result == ms_path
    
    def test_returns_none_when_not_found(self, tmp_path):
        """Returns None when MS PDF missing."""
        qp_path = tmp_path / "0478_s25_qp_11.pdf"
        qp_path.touch()
        
        result = find_markscheme_pdf(qp_path)
        
        assert result is None


class TestExtractMarkschemePages:
    """Tests for markscheme page extraction."""
    
    def test_extracts_single_page(self, tmp_path):
        """Extracts single-page markscheme."""
        # Create a simple test PDF
        ms_pdf = tmp_path / "test_ms.pdf"
        self._create_test_pdf(ms_pdf, num_pages=1)
        
        # Act
        output_dir = tmp_path / "output_q1"
        result = extract_markscheme_for_question(
            ms_pdf_path=ms_pdf,
            question_number=1,
            ms_page_indices=[0],
            output_dir=output_dir,
        )
        
        # Assert
        assert result is not None
        assert result.exists()
        assert result.name == "output_q1_ms.png"
        
        # Verify it's a valid image
        img = Image.open(result)
        assert img.width > 0
        assert img.height > 0
    
    def test_extracts_multi_page(self, tmp_path):
        """Extracts multi-page markscheme."""
        # Create a test PDF with multiple pages
        ms_pdf = tmp_path / "test_ms.pdf"
        self._create_test_pdf(ms_pdf, num_pages=3)
        
        output_dir = tmp_path / "output_q2"
        
        # Act
        result = extract_markscheme_for_question(
            ms_pdf_path=ms_pdf,
            question_number=2,
            ms_page_indices=[1, 2],
            output_dir=output_dir,
        )
        
        # Assert
        assert result is not None
        assert result.name == "output_q2_ms.png"
        assert result.exists()
    
    def test_handles_invalid_page_range(self, tmp_path):
        """Handles invalid page range gracefully."""
        ms_pdf = tmp_path / "test_ms.pdf"
        self._create_test_pdf(ms_pdf, num_pages=2)
        
        # Act - request pages that don't exist
        result = extract_markscheme_for_question(
            ms_pdf_path=ms_pdf,
            question_number=1,
            ms_page_indices=[5, 10],  # Out of range
            output_dir=tmp_path / "output_q3",
        )
        
        # Assert - should return None or handle gracefully
        assert result is None
    
    def test_returns_none_for_missing_pdf(self, tmp_path):
        """Returns None when PDF doesn't exist."""
        result = extract_markscheme_for_question(
            ms_pdf_path=tmp_path / "nonexistent.pdf",
            question_number=1,
            ms_page_indices=[0],
            output_dir=tmp_path / "output_nonexistent",
        )
        
        assert result is None
    
    @staticmethod
    def _create_test_pdf(path: Path, num_pages: int = 1):
        """Helper to create a simple test PDF."""
        doc = fitz.open()
        for i in range(num_pages):
            page = doc.new_page(width=595, height=842)  # A4 size
            # Add some text to make it non-empty
            page.insert_text((100, 100), f"Test Page {i + 1}")
        doc.save(path)
        doc.close()
