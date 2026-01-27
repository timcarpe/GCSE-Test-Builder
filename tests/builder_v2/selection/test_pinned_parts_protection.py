"""
Tests for pinned parts protection during selection and pruning.

Verifies that:
1. Pinned parts are always included in the selection
2. Pinned parts are never pruned, even when over budget
"""
from pathlib import Path
from gcse_toolkit.core.models.marks import Marks
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.core.models.parts import Part, PartKind
from gcse_toolkit.core.models.questions import Question
from gcse_toolkit.builder_v2.selection import (
    SelectionConfig,
    select_questions,
)


def make_question_with_parts(qid: str, part_marks: list[int]) -> Question:
    """
    Helper to create test questions with multiple parts.
    
    Args:
        qid: Question ID (e.g., "q1")
        part_marks: List of marks for each part (e.g., [3, 5, 2] creates 3 parts)
    """
    leaves = []
    for i, marks in enumerate(part_marks):
        letter = chr(ord('a') + i)  # a, b, c, ...
        # Use non-overlapping bounds: each part is 100 units tall, starting at i*100
        top = i * 100
        bottom = (i + 1) * 100
        leaves.append(
            Part(
                f"{qid}({letter})",
                PartKind.LETTER,
                Marks.explicit(marks),
                SliceBounds(top, bottom)
            )
        )
    
    # Question bounds cover all parts
    question_node = Part(
        qid,
        PartKind.QUESTION,
        Marks.aggregate(leaves),
        SliceBounds(0, len(part_marks) * 100),
        children=tuple(leaves)
    )
    
    return Question(
        id=qid,
        exam_code="0478",
        year=2021,
        paper=1,
        variant=1,
        topic="Test Topic",
        question_node=question_node,
        composite_path=Path("/test"),
        regions_path=Path("/test"),
    )


class TestPinnedPartsAreIncluded:
    """Tests that pinned parts are always included in the selection."""
    
    def test_pinned_part_included_even_when_budget_tight(self):
        """
        When a specific part is pinned, it must be in the final selection,
        even if the budget is very tight.
        """
        # Question with 3 parts: (a)=3, (b)=5, (c)=2 marks
        q = make_question_with_parts("q1", [3, 5, 2])
        
        # Pin part (b) which has 5 marks
        pinned_part = "q1::q1(b)"
        
        config = SelectionConfig(
            target_marks=5,  # Exactly the marks of the pinned part
            tolerance=0,
            keyword_mode=True,
            pinned_part_labels={pinned_part},
            keyword_matched_labels={"q1": {"q1(b)"}},  # Match only pinned part
        )
        
        result = select_questions([q], config)
        
        # The pinned part must be in the result
        assert result.question_count == 1
        plan = result.plans[0]
        assert "q1(b)" in plan.included_parts, f"Pinned part q1(b) not in selection: {plan.included_parts}"
    
    def test_all_pinned_parts_included_when_multiple_pins(self):
        """
        When multiple parts are pinned, all must be included.
        """
        # Question with 3 parts: (a)=3, (b)=5, (c)=2 marks
        q = make_question_with_parts("q1", [3, 5, 2])
        
        # Pin parts (a) and (c)
        pinned_parts = {"q1::q1(a)", "q1::q1(c)"}
        
        config = SelectionConfig(
            target_marks=10,
            tolerance=2,
            keyword_mode=True,
            pinned_part_labels=pinned_parts,
            keyword_matched_labels={"q1": {"q1(a)", "q1(c)"}},
        )
        
        result = select_questions([q], config)
        
        assert result.question_count == 1
        plan = result.plans[0]
        assert "q1(a)" in plan.included_parts, "Pinned part q1(a) missing"
        assert "q1(c)" in plan.included_parts, "Pinned part q1(c) missing"
    
    def test_full_question_pin_includes_all_parts(self):
        """
        When a full question is pinned (not part-level), all parts must be included.
        """
        q = make_question_with_parts("q1", [3, 5, 2])  # Total = 10 marks
        
        config = SelectionConfig(
            target_marks=10,
            tolerance=0,
            keyword_mode=True,
            pinned_question_ids={"q1"},
            keyword_matched_labels={"q1": {"q1(a)", "q1(b)", "q1(c)"}},
        )
        
        result = select_questions([q], config)
        
        assert result.question_count == 1
        plan = result.plans[0]
        assert "q1(a)" in plan.included_parts
        assert "q1(b)" in plan.included_parts
        assert "q1(c)" in plan.included_parts


class TestPinnedPartsNotPruned:
    """Tests that pinned parts are never removed during pruning."""
    
    def test_pinned_part_not_pruned_when_over_budget(self):
        """
        Even when the selection exceeds the budget, pinned parts must not be pruned.
        """
        # Question with 3 parts: (a)=3, (b)=5, (c)=2 marks, total=10
        q = make_question_with_parts("q1", [3, 5, 2])
        
        # Pin the LARGEST part (b) with 5 marks
        pinned_part = "q1::q1(b)"
        
        # Target is only 3 marks, but we need to include the 5-mark pinned part
        config = SelectionConfig(
            target_marks=3,
            tolerance=1,
            keyword_mode=True,
            pinned_part_labels={pinned_part},
            keyword_matched_labels={"q1": {"q1(a)", "q1(b)", "q1(c)"}},
        )
        
        result = select_questions([q], config)
        
        # The pinned part MUST be in the result, even though it exceeds budget
        plan = result.plans[0]
        assert "q1(b)" in plan.included_parts, (
            f"Pinned part q1(b) was pruned! Remaining parts: {plan.included_parts}"
        )
    
    def test_non_pinned_parts_can_be_pruned(self):
        """
        Non-pinned parts can still be pruned to get closer to target.
        """
        # Question with 3 parts: (a)=3, (b)=5, (c)=2 marks, total=10
        q = make_question_with_parts("q1", [3, 5, 2])
        
        # Pin only part (b)
        pinned_part = "q1::q1(b)"
        
        # Target is 5 marks (exactly the pinned part), tolerance 0
        # This should result in only part (b) being selected
        config = SelectionConfig(
            target_marks=5,
            tolerance=0,
            keyword_mode=True,
            pinned_part_labels={pinned_part},
            keyword_matched_labels={"q1": {"q1(b)"}},  # Only match pinned
        )
        
        result = select_questions([q], config)
        
        plan = result.plans[0]
        # Pinned part must be there
        assert "q1(b)" in plan.included_parts
        # Total marks should be 5 (just the pinned part)
        assert result.total_marks == 5
    
    def test_multiple_pinned_parts_all_protected(self):
        """
        When multiple parts are pinned, none of them should be pruned.
        """
        # Question with 4 parts: (a)=2, (b)=3, (c)=4, (d)=5 marks, total=14
        q = make_question_with_parts("q1", [2, 3, 4, 5])
        
        # Pin parts (a) and (d) - 2+5=7 marks
        pinned_parts = {"q1::q1(a)", "q1::q1(d)"}
        
        # Target is 7 marks with tight tolerance
        config = SelectionConfig(
            target_marks=7,
            tolerance=1,
            keyword_mode=True,
            pinned_part_labels=pinned_parts,
            keyword_matched_labels={"q1": {"q1(a)", "q1(d)"}},
        )
        
        result = select_questions([q], config)
        
        plan = result.plans[0]
        assert "q1(a)" in plan.included_parts, "Pinned part q1(a) was pruned"
        assert "q1(d)" in plan.included_parts, "Pinned part q1(d) was pruned"
        # Total should be at least 7 (the sum of pinned parts)
        assert result.total_marks >= 7


class TestPinnedQuestionProtection:
    """Tests for full question-level pins."""
    
    def test_full_question_pin_protects_all_parts_from_pruning(self):
        """
        When a full question is pinned, none of its parts should be prunable.
        """
        # Question with 3 parts totaling 10 marks
        q = make_question_with_parts("q1", [3, 5, 2])
        
        # Pin the full question
        config = SelectionConfig(
            target_marks=5,  # Less than the full question
            tolerance=2,
            keyword_mode=True,
            pinned_question_ids={"q1"},
            keyword_matched_labels={"q1": {"q1(a)", "q1(b)", "q1(c)"}},
        )
        
        result = select_questions([q], config)
        
        # All parts must be present (full question pinned)
        plan = result.plans[0]
        assert "q1(a)" in plan.included_parts
        assert "q1(b)" in plan.included_parts
        assert "q1(c)" in plan.included_parts
        assert result.total_marks == 10  # Full question marks
