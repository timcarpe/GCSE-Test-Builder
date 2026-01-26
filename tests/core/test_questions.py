"""
Unit Tests for Question Model (V2)

Tests for the Question dataclass validating complete question representation.
"""

import pytest
from pathlib import Path

from gcse_toolkit.core.models.marks import Marks
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.core.models.parts import Part, PartKind
from gcse_toolkit.core.models.questions import Question


class TestQuestion:
    """Tests for Question dataclass."""
    
    @pytest.fixture
    def sample_question_node(self) -> Part:
        """Create a sample question tree for testing."""
        roman1 = Part("1(a)(i)", PartKind.ROMAN, Marks.explicit(2), SliceBounds(100, 150))
        roman2 = Part("1(a)(ii)", PartKind.ROMAN, Marks.explicit(3), SliceBounds(150, 200))
        letter_a = Part("1(a)", PartKind.LETTER, Marks.aggregate([roman1, roman2]), 
                        SliceBounds(50, 250), children=(roman1, roman2))
        letter_b = Part("1(b)", PartKind.LETTER, Marks.explicit(4), SliceBounds(250, 350))
        question = Part("1", PartKind.QUESTION, Marks.aggregate([letter_a, letter_b]),
                        SliceBounds(0, 400), children=(letter_a, letter_b))
        return question
    
    def test_init_when_valid_data_then_creates_question(self, sample_question_node):
        """Valid question data should be created successfully."""
        q = Question(
            id="s21_qp_12_q1",
            exam_code="0478",
            year=2021,
            paper=1,
            variant=2,
            topic="01. Data Representation",
            question_node=sample_question_node,
            composite_path=Path("/cache/0478/composite.png"),
            regions_path=Path("/cache/0478/regions.json"),
        )
        assert q.id == "s21_qp_12_q1"
        assert q.exam_code == "0478"
    
    def test_init_when_invalid_exam_code_then_raises_error(self, sample_question_node):
        """Invalid exam code should raise ValueError."""
        with pytest.raises(ValueError, match="exam_code must be 4 characters"):
            Question(
                id="test",
                exam_code="04",  # Too short
                year=2021,
                paper=1,
                variant=1,
                topic="Test",
                question_node=sample_question_node,
                composite_path=Path("/test"),
                regions_path=Path("/test"),
            )
    
    def test_init_when_exam_code_not_digits_then_raises_error(self, sample_question_node):
        """Non-digit exam code should raise ValueError."""
        with pytest.raises(ValueError, match="exam_code must be digits"):
            Question(
                id="test",
                exam_code="ABCD",
                year=2021,
                paper=1,
                variant=1,
                topic="Test",
                question_node=sample_question_node,
                composite_path=Path("/test"),
                regions_path=Path("/test"),
            )
    
    def test_total_marks_when_accessed_then_calculated_from_tree(self, sample_question_node):
        """total_marks should be calculated from leaves, not stored."""
        q = Question(
            id="test",
            exam_code="0478",
            year=2021,
            paper=1,
            variant=1,
            topic="Test",
            question_node=sample_question_node,
            composite_path=Path("/test"),
            regions_path=Path("/test"),
        )
        # Expected: 2 + 3 + 4 = 9
        assert q.total_marks == 9
    
    def test_leaf_parts_when_accessed_then_returns_only_leaves(self, sample_question_node):
        """leaf_parts should return only leaf parts."""
        q = Question(
            id="test",
            exam_code="0478",
            year=2021,
            paper=1,
            variant=1,
            topic="Test",
            question_node=sample_question_node,
            composite_path=Path("/test"),
            regions_path=Path("/test"),
        )
        # Expected leaves: 1(a)(i), 1(a)(ii), 1(b)
        assert len(q.leaf_parts) == 3
