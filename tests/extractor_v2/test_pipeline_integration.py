"""
Integration tests for extractor_v2 pipeline.

These tests verify the complete extraction pipeline using real PDF files.

Test Fixtures (in tests/v2/extractor_v2/fixtures/):
    - 0478_m24_qp_12.pdf: Computer Science paper with 8 questions
    - 0450_s25_qp_11.pdf: Business Studies paper
    - 0580_s25_qp_11.pdf: Mathematics paper

Verified: 2025-12-12
"""

import json
import pytest
import shutil
from pathlib import Path

# Use fixtures directory in tests folder
FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Test PDFs from different exam codes
TEST_PDFS = [
    ("0478", FIXTURES_DIR / "0478_m24_qp_12.pdf"),
    ("0450", FIXTURES_DIR / "0450_s25_qp_11.pdf"),
    ("0580", FIXTURES_DIR / "0580_s25_qp_11.pdf"),
]


@pytest.fixture
def output_dir(tmp_path):
    """Create temporary output directory."""
    return tmp_path / "extraction_output"


@pytest.fixture(params=TEST_PDFS, ids=["0478-CS", "0450-Business", "0580-Maths"])
def sample_pdf(request):
    """Get sample PDF path, skip if not available."""
    exam_code, pdf_path = request.param
    if not pdf_path.exists():
        pytest.skip(f"Sample PDF not found: {pdf_path}")
    return exam_code, pdf_path


class TestExtractQuestionPaper:
    """Integration tests for extract_question_paper()."""

    def test_extract_question_paper_when_valid_pdf_then_extracts_questions(
        self, sample_pdf, output_dir
    ):
        """Should extract questions from a valid PDF."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        exam_code, pdf_path = sample_pdf
        
        # Act
        result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code=exam_code,
        )
        
        # Assert
        assert result.question_count > 0
        assert len(result.question_ids) > 0
        assert result.output_dir == output_dir

    def test_extract_question_paper_when_valid_then_creates_output_files(
        self, sample_pdf, output_dir
    ):
        """Should create composite.png, regions.json, metadata.json for each question."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        exam_code, pdf_path = sample_pdf
        
        # Act
        result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code=exam_code,
        )
        
        # Assert
        from gcse_toolkit.builder_v2.loading import discover_questions
        dirs = discover_questions(output_dir, exam_code)
        assert len(dirs) == len(result.question_ids)
        
        for question_dir in dirs:
            assert question_dir.exists()
            assert (question_dir / "composite.png").exists()
            assert (question_dir / "regions.json").exists()
            assert (question_dir / "metadata.json").exists()

    def test_extract_question_paper_when_valid_then_regions_validate_against_schema(
        self, sample_pdf, output_dir
    ):
        """All regions.json files should validate against schema."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.core.schemas.validator import validate_regions
        exam_code, pdf_path = sample_pdf
        
        # Act
        result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code=exam_code,
        )
        
        # Assert
        from gcse_toolkit.builder_v2.loading import discover_questions
        dirs = discover_questions(output_dir, exam_code)
        
        for question_dir in dirs:
            regions_path = question_dir / "regions.json"
            with open(regions_path) as f:
                data = json.load(f)
            # Should not raise
            validate_regions(data)

    def test_extract_question_paper_when_valid_then_regions_have_kind(
        self, sample_pdf, output_dir
    ):
        """All regions should include kind field (question/letter/roman)."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        exam_code, pdf_path = sample_pdf
        
        # Act
        result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code=exam_code,
        )
        
        # Assert
        from gcse_toolkit.builder_v2.loading import discover_questions
        dirs = discover_questions(output_dir, exam_code)
        question_dir = dirs[0]
        
        regions_path = question_dir / "regions.json"
        with open(regions_path) as f:
            data = json.load(f)
        
        for label, region in data["regions"].items():
            assert "kind" in region, f"Missing 'kind' for region {label}"
            assert region["kind"] in ("question", "letter", "roman")

    def test_extract_question_paper_when_valid_then_metadata_has_required_fields(
        self, sample_pdf, output_dir
    ):
        """Metadata should include required fields."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        exam_code, pdf_path = sample_pdf
        
        # Act
        result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code=exam_code,
        )
        
        # Assert
        from gcse_toolkit.builder_v2.loading import discover_questions
        dirs = discover_questions(output_dir, exam_code)
        question_dir = dirs[0]
        
        metadata_path = question_dir / "metadata.json"
        with open(metadata_path) as f:
            data = json.load(f)
        
        assert "total_marks" in data
        assert "exam_code" in data
        assert data["exam_code"] == exam_code
        assert "year" in data
        assert "paper" in data

    def test_extract_question_paper_when_pdf_not_found_then_raises_error(
        self, output_dir
    ):
        """Should raise FileNotFoundError for missing PDF."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        missing_pdf = Path("/nonexistent/path.pdf")
        
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            extract_question_paper(
                pdf_path=missing_pdf,
                output_dir=output_dir,
                exam_code="0478",
            )


class TestMultiPageQuestion:
    """Tests for questions spanning multiple pages."""

    def test_extract_multipage_when_question_spans_pages_then_stitches_composite(
        self, sample_pdf, output_dir
    ):
        """Should stitch segments into single composite for multi-page questions."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from PIL import Image
        exam_code, pdf_path = sample_pdf
        
        # Act
        result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code=exam_code,
        )
        
        # Assert - composite should have reasonable dimensions
        from gcse_toolkit.builder_v2.loading import discover_questions
        dirs = discover_questions(output_dir, exam_code)
        question_dir = dirs[0]
        
        q1_composite = question_dir / "composite.png"
        with Image.open(q1_composite) as img:
            assert img.height > 100  # Should have content
            assert img.width > 100


class TestBoundsCalculation:
    """Tests for slice bounds calculation."""

    def test_bounds_when_calculated_then_no_overlap_between_siblings(
        self, sample_pdf, output_dir
    ):
        """Sibling part bounds should not overlap."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        exam_code, pdf_path = sample_pdf
        
        # Act
        result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code=exam_code,
        )
        
        # Assert
        from gcse_toolkit.builder_v2.loading import discover_questions
        dirs = discover_questions(output_dir, exam_code)
        question_dir = dirs[0]
        
        regions_path = question_dir / "regions.json"
        with open(regions_path) as f:
            data = json.load(f)
        
        # Check no overlaps between LEAF parts
        # Leaf parts in V2 do not overlap by definition.
        # Parent parts (like '1' or '1(a)') will naturally overlap with their children.
        leaf_bounds = []
        for label, region in data["regions"].items():
            # In V2 regions.json, kind is available
            if region["kind"] in ("letter", "roman"):
                # Check if it has any children in the regions list
                has_children = any(l.startswith(f"{label}(") for l in data["regions"] if l != label)
                if not has_children:
                    leaf_bounds.append((label, region["bounds"]["top"], region["bounds"]["bottom"]))
        
        leaf_bounds.sort(key=lambda x: x[1])
        
        for i in range(len(leaf_bounds) - 1):
            label1, _, bottom1 = leaf_bounds[i]
            label2, top2, _ = leaf_bounds[i + 1]
            assert bottom1 <= top2, f"Overlap between leaf parts {label1} and {label2}"

    def test_bounds_when_calculated_then_within_composite_dimensions(
        self, sample_pdf, output_dir
    ):
        """All bounds should be within composite image dimensions."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        exam_code, pdf_path = sample_pdf
        
        # Act
        result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code=exam_code,
        )
        
        # Assert
        from gcse_toolkit.builder_v2.loading import discover_questions
        dirs = discover_questions(output_dir, exam_code)
        question_dir = dirs[0]
        
        regions_path = question_dir / "regions.json"
        with open(regions_path) as f:
            data = json.load(f)
        
        width = data["composite_size"]["width"]
        height = data["composite_size"]["height"]
        
        for label, region in data["regions"].items():
            bounds = region["bounds"]
            assert 0 <= bounds["top"] < height, f"Invalid top for {label}"
            assert 0 < bounds["bottom"] <= height, f"Invalid bottom for {label}"
            assert 0 <= bounds["left"] < width, f"Invalid left for {label}"
            assert 0 < bounds["right"] <= width, f"Invalid right for {label}"
