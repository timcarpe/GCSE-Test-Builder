"""
Unit Tests for Selection Models (V2)

Tests for SelectionPlan and SelectionResult dataclasses.
"""

import pytest
from pathlib import Path

from gcse_toolkit.core.models.marks import Marks
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.core.models.parts import Part, PartKind
from gcse_toolkit.core.models.questions import Question
from gcse_toolkit.core.models.selection import SelectionPlan, SelectionResult


class TestSelectionPlan:
    """Tests for SelectionPlan dataclass."""
    
    @pytest.fixture
    def sample_question(self) -> Question:
        """Create a sample question for testing."""
        roman1 = Part("1(a)(i)", PartKind.ROMAN, Marks.explicit(2), SliceBounds(100, 150))
        roman2 = Part("1(a)(ii)", PartKind.ROMAN, Marks.explicit(3), SliceBounds(150, 200))
        letter = Part("1(a)", PartKind.LETTER, Marks.aggregate([roman1, roman2]), 
                      SliceBounds(50, 250), children=(roman1, roman2))
        question_node = Part("1", PartKind.QUESTION, Marks.aggregate([letter]),
                            SliceBounds(0, 300), children=(letter,))
        
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
    
    def test_marks_when_all_leaves_included_then_returns_total(self, sample_question):
        """marks should sum all included leaf marks."""
        plan = SelectionPlan.full_question(sample_question)
        # Expected: 2 + 3 = 5
        assert plan.marks == 5
    
    def test_marks_when_partial_leaves_then_returns_partial_sum(self, sample_question):
        """marks should sum only included leaf marks."""
        plan = SelectionPlan(
            question=sample_question,
            included_parts=frozenset(["1(a)(i)"]),  # Only first roman
        )
        assert plan.marks == 2
    
    def test_init_when_invalid_label_then_raises_error(self, sample_question):
        """Invalid part labels should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid part labels"):
            SelectionPlan(
                question=sample_question,
                included_parts=frozenset(["nonexistent"]),
            )
    
    def test_is_partial_when_some_excluded_then_returns_true(self, sample_question):
        """is_partial should be True when some leaves are excluded."""
        plan = SelectionPlan(
            question=sample_question,
            included_parts=frozenset(["1(a)(i)"]),
        )
        assert plan.is_partial is True
        assert plan.is_full_question is False


class TestSelectionResult:
    """Tests for SelectionResult dataclass."""
    
    @pytest.fixture
    def sample_plans(self) -> tuple[SelectionPlan, SelectionPlan]:
        """Create sample plans for testing."""
        # Question 1
        roman1 = Part("1(a)(i)", PartKind.ROMAN, Marks.explicit(2), SliceBounds(100, 150))
        q1_node = Part("1", PartKind.QUESTION, Marks.aggregate([roman1]),
                       SliceBounds(0, 200), children=(roman1,))
        q1 = Question(
            id="q1", exam_code="0478", year=2021, paper=1, variant=1,
            topic="Topic A", question_node=q1_node,
            composite_path=Path("/q1"), regions_path=Path("/q1"),
        )
        
        # Question 2
        roman2 = Part("2(a)(i)", PartKind.ROMAN, Marks.explicit(3), SliceBounds(100, 150))
        q2_node = Part("2", PartKind.QUESTION, Marks.aggregate([roman2]),
                       SliceBounds(0, 200), children=(roman2,))
        q2 = Question(
            id="q2", exam_code="0478", year=2021, paper=1, variant=1,
            topic="Topic B", question_node=q2_node,
            composite_path=Path("/q2"), regions_path=Path("/q2"),
        )
        
        plan1 = SelectionPlan.full_question(q1)
        plan2 = SelectionPlan.full_question(q2)
        return plan1, plan2
    
    def test_total_marks_when_multiple_plans_then_sums_correctly(self, sample_plans):
        """total_marks should sum marks from all plans."""
        result = SelectionResult(
            plans=sample_plans,
            target_marks=10,
            tolerance=5,
        )
        # Expected: 2 + 3 = 5
        assert result.total_marks == 5
    
    def test_within_tolerance_when_close_to_target_then_returns_true(self, sample_plans):
        """within_tolerance should be True when close enough."""
        result = SelectionResult(
            plans=sample_plans,
            target_marks=10,
            tolerance=5,
        )
        # 5 marks, target 10, tolerance 5 -> |5-10| = 5 <= 5
        assert result.within_tolerance is True
    
    def test_covered_topics_when_multiple_topics_then_returns_all(self, sample_plans):
        """covered_topics should include all unique topics."""
        result = SelectionResult(
            plans=sample_plans,
            target_marks=10,
            tolerance=5,
        )
        assert "Topic A" in result.covered_topics
        assert "Topic B" in result.covered_topics
