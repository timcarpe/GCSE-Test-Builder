"""
Unit tests for selector and pruning.

Verified: 2025-12-12
"""

import pytest
from pathlib import Path

from gcse_toolkit.core.models.marks import Marks
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.core.models.parts import Part, PartKind
from gcse_toolkit.core.models.questions import Question
from gcse_toolkit.core.models.selection import SelectionPlan
from gcse_toolkit.builder_v2.selection import (
    SelectionConfig,
    select_questions,
    prune_to_target,
)
from gcse_toolkit.builder_v2.selection.pruning import prune_selection


def make_question(
    qid: str,
    topic: str,
    marks: list[int],
) -> Question:
    """Helper to create test questions."""
    leaves = [
        Part(
            f"{qid[1:]}({chr(97+i)})",
            PartKind.LETTER,
            Marks.explicit(m),
            SliceBounds(i*50, (i+1)*50)
        )
        for i, m in enumerate(marks)
    ]
    question_node = Part(
        qid[1:],  # Remove 'q' prefix
        PartKind.QUESTION,
        Marks.aggregate(leaves),
        SliceBounds(0, len(marks)*50),
        children=tuple(leaves)
    )
    
    return Question(
        id=qid,
        exam_code="0478",
        year=2021,
        paper=1,
        variant=1,
        topic=topic,
        question_node=question_node,
        composite_path=Path("/test"),
        regions_path=Path("/test"),
    )


@pytest.fixture
def sample_questions() -> list[Question]:
    """Create sample questions for selection testing."""
    return [
        make_question("q1", "Topic A", [2, 3, 5]),     # 10 marks
        make_question("q2", "Topic A", [4, 6]),        # 10 marks
        make_question("q3", "Topic B", [3, 3, 4]),     # 10 marks
        make_question("q4", "Topic C", [2, 2, 2, 2]),  # 8 marks
        make_question("q5", "Topic D", [5, 5]),        # 10 marks
    ]


class TestSelectQuestions:
    """Tests for select_questions function."""

    def test_select_questions_when_target_reachable_then_within_tolerance(
        self, sample_questions
    ):
        """Should select questions within tolerance of target."""
        # Arrange
        config = SelectionConfig(target_marks=20, tolerance=2)
        
        # Act
        result = select_questions(sample_questions, config)
        
        # Assert
        assert result.within_tolerance
        assert 18 <= result.total_marks <= 22

    def test_select_questions_when_topic_filter_then_only_matching_topics(
        self, sample_questions
    ):
        """Should only select from requested topics."""
        # Arrange
        config = SelectionConfig(
            target_marks=15,
            topics=["Topic A"],
        )
        
        # Act
        result = select_questions(sample_questions, config)
        
        # Assert
        for plan in result.plans:
            assert plan.question.topic == "Topic A"

    def test_select_questions_when_force_coverage_then_covers_all_topics(
        self, sample_questions
    ):
        """Should ensure all requested topics are covered."""
        # Arrange
        config = SelectionConfig(
            target_marks=30,
            topics=["Topic A", "Topic B", "Topic C"],
            force_topic_coverage=True,
        )
        
        # Act
        result = select_questions(sample_questions, config)
        
        # Assert
        covered = result.covered_topics
        assert "Topic A" in covered
        assert "Topic B" in covered
        assert "Topic C" in covered

    def test_select_questions_when_no_matching_topics_then_empty_result(
        self, sample_questions
    ):
        """Should return empty result if no topics match."""
        # Arrange
        config = SelectionConfig(
            target_marks=20,
            topics=["Nonexistent Topic"],
        )
        
        # Act
        result = select_questions(sample_questions, config)
        
        # Assert
        assert result.question_count == 0

    def test_select_questions_when_max_questions_then_respects_limit(
        self, sample_questions
    ):
        """Should not exceed max_questions limit."""
        # Arrange
        config = SelectionConfig(
            target_marks=50,
            max_questions=2,
        )
        
        # Act
        result = select_questions(sample_questions, config)
        
        # Assert
        assert result.question_count <= 2


class TestPruneToTarget:
    """Tests for prune_to_target function."""

    def test_prune_to_target_when_already_under_then_no_change(self):
        """Should not modify if already at or below target."""
        # Arrange
        q = make_question("q1", "Topic", [2, 3])
        plan = SelectionPlan.full_question(q)  # 5 marks
        
        # Act
        result = prune_to_target(plan, target_marks=10)
        
        # Assert
        assert result.marks == 5
        assert result.is_full_question

    def test_prune_to_target_when_over_then_removes_parts(self):
        """Should remove parts to hit target."""
        # Arrange
        q = make_question("q1", "Topic", [2, 3, 5])
        plan = SelectionPlan.full_question(q)  # 10 marks
        
        # Act
        result = prune_to_target(plan, target_marks=5)
        
        # Assert
        assert result.marks <= 5
        assert result.is_partial

    def test_prune_to_target_when_min_parts_then_respects_limit(self):
        """Should keep at least min_parts parts."""
        # Arrange
        q = make_question("q1", "Topic", [5, 5, 5])
        plan = SelectionPlan.full_question(q)  # 15 marks
        
        # Act
        result = prune_to_target(plan, target_marks=3, min_parts=2)
        
        # Assert
        assert len(result.included_leaves) >= 2


class TestPruneSelection:
    """Tests for prune_selection function."""

    def test_prune_selection_when_within_tolerance_then_no_change(self):
        """Should not modify if already within tolerance."""
        # Arrange
        q = make_question("q1", "Topic", [2, 3])
        plan = SelectionPlan.full_question(q)  # 5 marks
        
        # Act
        result = prune_selection([plan], target_marks=5, tolerance=0)
        
        # Assert
        assert len(result) == 1
        assert result[0].marks == 5

    def test_prune_selection_when_over_then_prunes_across_plans(self):
        """Should prune parts across multiple plans."""
        # Arrange
        q1 = make_question("q1", "Topic", [2, 3])
        q2 = make_question("q2", "Topic", [4, 6])
        plans = [
            SelectionPlan.full_question(q1),  # 5 marks
            SelectionPlan.full_question(q2),  # 10 marks
        ]  # Total: 15 marks
        
        # Act
        result = prune_selection(plans, target_marks=10, tolerance=2)
        
        # Assert
        total = sum(p.marks for p in result)
        assert total <= 12  # Within tolerance
