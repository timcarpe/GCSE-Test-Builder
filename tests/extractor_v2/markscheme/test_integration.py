"""Integration test for markscheme extraction in pipeline."""

import pytest
from pathlib import Path
import fitz

from gcse_toolkit.extractor_v2.pipeline import extract_question_paper
from gcse_toolkit.extractor_v2.config import ExtractionConfig


class TestMarkschemeIntegration:
    """Integration tests for markscheme extraction in extraction pipeline."""
    
    def test_extraction_with_markscheme(self, tmp_path):
        """Test full extraction pipeline with markscheme PDF."""
        # Create test QP PDF
        qp_pdf = tmp_path / "0478_s25_qp_11.pdf"
        self._create_test_qp_pdf(qp_pdf)
        
        # Create test MS PDF
        ms_pdf = tmp_path / "0478_s25_ms_11.pdf"
        self._create_test_ms_pdf(ms_pdf)
        
        output_dir = tmp_path / "output"
        
        # Act - extract with markschemes enabled
        config = ExtractionConfig(extract_markschemes=True)
        result = extract_question_paper(
            pdf_path=qp_pdf,
            output_dir=output_dir,
            exam_code="0478",
            config=config,
        )
        
        # Assert
        assert result.question_count >= 1, "Should extract at least one question"
        
        # Check that markscheme was extracted for first question
        question_id = result.question_ids[0]
        # V2 produces hierarchical output: output/exam_code/topic/question_id
        # Use discover_questions to find it
        from gcse_toolkit.builder_v2.loading import discover_questions
        dirs = discover_questions(output_dir, "0478")
        question_dir = dirs[0]
        
        assert question_dir.exists(), f"Question directory {question_dir} should exist"
        assert (question_dir / "composite.png").exists(), "Should have composite image"
        assert (question_dir / "metadata.json").exists(), "Should have metadata"
        
        # Check for markscheme page - V2 uses {question_id}_ms.png
        ms_name = f"{question_dir.name}_ms.png"
        ms_page = question_dir / ms_name
        assert ms_page.exists(), f"Should have markscheme page extracted as {ms_name}"
        
        # Verify metadata contains markscheme_path
        import json
        metadata = json.loads((question_dir / "metadata.json").read_text())
        assert "markscheme_path" in metadata, "Metadata should contain markscheme_path"
        assert metadata["markscheme_path"] == ms_name
    
    def test_extraction_without_markscheme(self, tmp_path):
        """Test extraction when MS PDF not found."""
        # Create only QP PDF (no MS)
        qp_pdf = tmp_path / "0478_s25_qp_11.pdf"
        self._create_test_qp_pdf(qp_pdf)
        
        output_dir = tmp_path / "output"
        
        # Act
        config = ExtractionConfig(extract_markschemes=True)
        result = extract_question_paper(
            pdf_path=qp_pdf,
            output_dir=output_dir,
            exam_code="0478",
            config=config,
        )
        
        # Assert - should still extract questions successfully
        assert result.question_count >= 1
        
        # Check metadata doesn't have markscheme_path
        import json
        from gcse_toolkit.builder_v2.loading import discover_questions
        dirs = discover_questions(output_dir, "0478")
        question_dir = dirs[0]
        metadata = json.loads((question_dir / "metadata.json").read_text())
        assert "markscheme_path" not in metadata, "Should not have markscheme_path when MS not found"
    
    def test_extraction_with_markscheme_disabled(self, tmp_path):
        """Test extraction with markscheme extraction disabled."""
        # Create both PDFs
        qp_pdf = tmp_path / "0478_s25_qp_11.pdf"
        ms_pdf = tmp_path / "0478_s25_ms_11.pdf"
        self._create_test_qp_pdf(qp_pdf)
        self._create_test_ms_pdf(ms_pdf)
        
        output_dir = tmp_path / "output"
        
        # Act - disable markscheme extraction
        config = ExtractionConfig(extract_markschemes=False)
        result = extract_question_paper(
            pdf_path=qp_pdf,
            output_dir=output_dir,
            exam_code="0478",
            config=config,
        )
        
        # Assert - MS should not be extracted even though it exists
        from gcse_toolkit.builder_v2.loading import discover_questions
        dirs = discover_questions(output_dir, "0478")
        question_dir = dirs[0]
        
        ms_name = f"{question_dir.name}_ms.png"
        assert not (question_dir / ms_name).exists(), "Should not extract MS when disabled"
        
        import json
        metadata = json.loads((question_dir / "metadata.json").read_text())
        assert "markscheme_path" not in metadata
    
    @staticmethod
    def _create_test_qp_pdf(path: Path):
        """Create a simple question paper PDF for testing."""
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        
        # Add question number
        page.insert_text((50, 100), "1", fontsize=20)
        
        # Add some question text
        page.insert_text((80, 120), "(a) What is the capital of France?")
        
        # Add mark box
        page.insert_text((500, 120), "[2]")
        
        doc.save(path)
        doc.close()
    
    @staticmethod
    def _create_test_ms_pdf(path: Path):
        """Create a simple markscheme PDF for testing."""
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        
        # Add markscheme content
        page.insert_text((50, 100), "Question 1")
        page.insert_text((50, 150), "1(a) Paris [2]")
        
        doc.save(path)
        doc.close()
