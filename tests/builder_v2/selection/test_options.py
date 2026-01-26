"""
Unit tests for option generation.

Verified: 2025-12-12
"""

import pytest
from pathlib import Path

from gcse_toolkit.core.models.marks import Marks
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.core.models.parts import Part, PartKind
from gcse_toolkit.core.models.questions import Question
from gcse_toolkit.builder_v2.selection.options import (
    generate_options,
    generate_all_options,
    QuestionOptions,
)
from gcse_toolkit.builder_v2.selection.part_mode import PartMode


@pytest.fixture
def simple_question() -> Question:
    """Create a simple question with 2 leaf parts."""
    roman1 = Part("1(a)(i)", PartKind.ROMAN, Marks.explicit(2), SliceBounds(100, 150))
    roman2 = Part("1(a)(ii)", PartKind.ROMAN, Marks.explicit(3), SliceBounds(150, 200))
    letter = Part(
        "1(a)", PartKind.LETTER, Marks.aggregate([roman1, roman2]),
        SliceBounds(50, 250), children=(roman1, roman2)
    )
    question_node = Part(
        "1", PartKind.QUESTION, Marks.aggregate([letter]),
        SliceBounds(0, 300), children=(letter,)
    )
    
    return Question(
        id="test_q1",
        exam_code="0478",
        year=2021,
        paper=1,
        variant=1,
        topic="Test Topic",
        question_node=question_node,
        composite_path=Path("/test"),
        regions_path=Path("/test"),
    )


@pytest.fixture
def multi_part_question() -> Question:
    """Create a question with 4 leaf parts."""
    leaves = [
        Part(f"1({chr(97+i)})", PartKind.LETTER, Marks.explicit(i+1), SliceBounds(i*50, (i+1)*50))
        for i in range(4)
    ]
    question_node = Part(
        "1", PartKind.QUESTION, Marks.aggregate(leaves),
        SliceBounds(0, 200), children=tuple(leaves)
    )
    
    return Question(
        id="multi_q1",
        exam_code="0478",
        year=2021,
        paper=1,
        variant=1,
        topic="Multi Topic",
        question_node=question_node,
        composite_path=Path("/test"),
        regions_path=Path("/test"),
    )


class TestGenerateOptions:
    """Tests for generate_options function."""

    def test_generate_options_when_simple_question_then_returns_all_combinations(
        self, simple_question
    ):
        """Should generate full + partial options."""
        # Act
        result = generate_options(simple_question)
        
        # Assert - 2 leaves = full + 2 singles = 3 options
        assert result.option_count == 3
        assert result.max_marks == 5  # Full question
        assert result.min_marks == 2  # Smallest single part

    def test_generate_options_when_multi_part_then_generates_many_options(
        self, multi_part_question
    ):
        """Should generate 2^n - 1 options for n leaves."""
        # Act
        result = generate_options(multi_part_question)
        
        # Assert - 4 leaves = 2^4 - 1 = 15 subsets
        assert result.option_count == 15

    def test_generate_options_when_no_partial_then_only_full(
        self, simple_question
    ):
        """part_mode=PartMode.ALL should only return full question."""
        # Act
        result = generate_options(simple_question, part_mode=PartMode.ALL)
        
        # Assert
        assert result.option_count == 1
        assert result.options[0].is_full_question

    def test_generate_options_when_sorted_then_descending_by_marks(
        self, multi_part_question
    ):
        """Options should be sorted by marks descending."""
        # Act
        result = generate_options(multi_part_question)
        
        # Assert
        marks = [opt.marks for opt in result.options]
        assert marks == sorted(marks, reverse=True)


class TestQuestionOptions:
    """Tests for QuestionOptions container."""

    def test_options_in_range_when_valid_range_then_returns_matching(
        self, multi_part_question
    ):
        """Should yield only options within mark range."""
        # Arrange
        opts = generate_options(multi_part_question)
        
        # Act
        in_range = list(opts.options_in_range(3, 6))
        
        # Assert
        for opt in in_range:
            assert 3 <= opt.marks <= 6

    def test_best_option_for_marks_when_exact_match_then_returns_it(
        self, multi_part_question
    ):
        """Should return option that fits exactly."""
        # Arrange
        opts = generate_options(multi_part_question)
        
        # Act
        best = opts.best_option_for_marks(10)  # Total is 1+2+3+4=10
        
        # Assert
        assert best is not None
        assert best.marks == 10

    def test_best_option_for_marks_when_under_target_then_returns_best_fit(
        self, multi_part_question
    ):
        """Should return largest option <= target."""
        # Arrange
        opts = generate_options(multi_part_question)
        
        # Act
        best = opts.best_option_for_marks(7)
        
        # Assert
        assert best is not None
        assert best.marks <= 7


class TestGenerateAllOptions:
    """Tests for generate_all_options function."""

    def test_generate_all_options_when_multiple_questions_then_returns_for_each(
        self, simple_question, multi_part_question
    ):
        """Should return options for each question."""
        # Arrange
        questions = [simple_question, multi_part_question]
        
        # Act
        result = generate_all_options(questions)
        
        # Assert
        assert len(result) == 2
        assert result[0].question.id == "test_q1"
        assert result[1].question.id == "multi_q1"
