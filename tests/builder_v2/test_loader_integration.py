"""
Integration tests for builder_v2 loading module.

These tests verify the complete loading pipeline using real extracted data.

Verified: 2025-12-12
"""

import pytest
from pathlib import Path

# Use fixtures from extractor tests
FIXTURES_DIR = Path(__file__).parents[1] / "extractor_v2" / "fixtures"


@pytest.fixture
def output_dir(tmp_path):
    """Create temporary output directory for extraction."""
    return tmp_path / "extraction_output"


@pytest.fixture
def extracted_questions(output_dir):
    """Extract questions for use in loader tests."""
    from gcse_toolkit.extractor_v2 import extract_question_paper
    
    pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Sample PDF not found: {pdf_path}")
    
    result = extract_question_paper(
        pdf_path=pdf_path,
        output_dir=output_dir,
        exam_code="0478",
    )
    return output_dir, result


class TestLoadSingleQuestion:
    """Tests for load_single_question()."""

    def test_load_single_question_when_valid_then_returns_question(
        self, extracted_questions
    ):
        """Should return Question object from valid directory."""
        # Arrange
        from gcse_toolkit.builder_v2.loading import load_single_question, discover_questions
        cache_dir, result = extracted_questions
        # Use discover_questions to find actual hierarchical path
        dirs = discover_questions(cache_dir, "0478")
        question_dir = dirs[0]
        
        # Act
        question = load_single_question(question_dir)
        
        # Assert
        assert question is not None
        assert question.id == result.question_ids[0]
        assert question.exam_code == "0478"

    def test_load_single_question_when_valid_then_has_total_marks(
        self, extracted_questions
    ):
        """Should calculate total marks from leaf parts."""
        # Arrange
        from gcse_toolkit.builder_v2.loading import load_single_question, discover_questions
        cache_dir, result = extracted_questions
        dirs = discover_questions(cache_dir, "0478")
        question_dir = dirs[0]
        
        # Act
        question = load_single_question(question_dir)
        
        # Assert
        assert question.total_marks > 0
        # Verify marks match leaf sum
        leaf_sum = sum(p.marks.value for p in question.leaf_parts)
        assert question.total_marks == leaf_sum

    def test_load_single_question_when_valid_then_parent_marks_aggregated(
        self, extracted_questions
    ):
        """Parent parts should have aggregate marks, leaves explicit."""
        # Arrange
        from gcse_toolkit.builder_v2.loading import load_single_question, discover_questions
        cache_dir, result = extracted_questions
        dirs = discover_questions(cache_dir, "0478")
        question_dir = dirs[0]
        
        # Act
        question = load_single_question(question_dir)
        
        # Assert
        for part in question.all_parts:
            if part.children:
                # Parent - should be aggregate
                assert part.marks.source == "aggregate"
            else:
                # Leaf - should be explicit
                assert part.marks.source == "explicit"

    def test_load_single_question_when_missing_file_then_raises(
        self, tmp_path
    ):
        """Should raise LoaderError for missing required files."""
        # Arrange
        from gcse_toolkit.builder_v2.loading import load_single_question, LoaderError
        
        # Act & Assert
        with pytest.raises(LoaderError):
            load_single_question(tmp_path / "nonexistent")


class TestLoadQuestions:
    """Tests for load_questions()."""

    def test_load_questions_when_valid_cache_then_returns_all(
        self, extracted_questions
    ):
        """Should load all questions from cache."""
        # Arrange
        from gcse_toolkit.builder_v2 import load_questions
        cache_dir, result = extracted_questions
        
        # Act
        questions = load_questions(cache_dir, "0478")
        
        # Assert
        assert len(questions) == result.question_count

    def test_load_questions_when_empty_cache_then_returns_empty(
        self, tmp_path
    ):
        """Should return empty list for empty cache."""
        # Arrange
        from gcse_toolkit.builder_v2 import load_questions
        tmp_path.mkdir(exist_ok=True)
        
        # Act
        questions = load_questions(tmp_path, "0478")
        
        # Assert
        assert questions == []

    def test_load_questions_when_nonexistent_cache_then_raises(
        self
    ):
        """Should raise LoaderError for nonexistent cache."""
        # Arrange
        from gcse_toolkit.builder_v2 import load_questions, LoaderError
        
        # Act & Assert
        with pytest.raises(LoaderError):
            load_questions(Path("/nonexistent"), "0478")


class TestImageProvider:
    """Tests for CompositeImageProvider."""

    def test_provider_when_valid_then_returns_slice(
        self, extracted_questions
    ):
        """Should crop and return slice for valid label."""
        # Arrange
        from gcse_toolkit.builder_v2.loading import load_single_question, discover_questions
        from gcse_toolkit.builder_v2.images import CompositeImageProvider
        
        cache_dir, result = extracted_questions
        dirs = discover_questions(cache_dir, "0478")
        question_dir = dirs[0]
        question = load_single_question(question_dir)
        
        # Get bounds from question
        bounds = {p.label: p.bounds for p in question.all_parts}
        
        # Act
        with CompositeImageProvider(question.composite_path, bounds) as provider:
            slice_img = provider.get_slice(question.question_node.label)
        
        # Assert
        assert slice_img is not None
        assert slice_img.height > 0
        assert slice_img.width > 0

    def test_provider_when_invalid_label_then_raises(
        self, extracted_questions
    ):
        """Should raise ImageNotFoundError for unknown label."""
        # Arrange
        from gcse_toolkit.builder_v2.loading import load_single_question, discover_questions
        from gcse_toolkit.builder_v2.images import CompositeImageProvider, ImageNotFoundError
        
        cache_dir, result = extracted_questions
        dirs = discover_questions(cache_dir, "0478")
        question_dir = dirs[0]
        question = load_single_question(question_dir)
        bounds = {p.label: p.bounds for p in question.all_parts}
        
        # Act & Assert
        with CompositeImageProvider(question.composite_path, bounds) as provider:
            with pytest.raises(ImageNotFoundError):
                provider.get_slice("INVALID_LABEL")
