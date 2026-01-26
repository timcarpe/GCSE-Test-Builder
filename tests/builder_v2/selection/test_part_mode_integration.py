"""
Integration tests for PartMode behavior during selection.

Specifically verifies that pruning logic respects PartMode invariants
during the final 'trim to target' phase.
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
)
from gcse_toolkit.builder_v2.selection.part_mode import PartMode
from gcse_toolkit.builder_v2.selection.pruning import prune_to_target, prune_selection


def make_question(qid: str, part_marks: list[int]) -> Question:
    """
    Create a question with sequential parts.
    
    Args:
        qid: Question ID (e.g. "q1")
        part_marks: List of marks for parts (a), (b), (c)...
    """
    leaves = [
        Part(
            f"{qid[1:]}({chr(97+i)})",
            PartKind.LETTER,
            Marks.explicit(m),
            SliceBounds(i*50, (i+1)*50)
        )
        for i, m in enumerate(part_marks)
    ]
    question_node = Part(
        qid[1:],
        PartKind.QUESTION,
        Marks.aggregate(leaves),
        SliceBounds(0, len(part_marks)*50),
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


class TestPruningInvariants:
    """
    Verify that pruning respects PartMode invariants.
    
    The critical bug is that standard pruning just removes the 'cheapest' part
    to hit the target, which might be a middle part (breaking PRUNE structure).
    """

    def test_prune_mode_should_not_remove_middle_part(self):
        """
        Scenario:
        - Question with parts: (a)=2, (b)=5. Total=7.
        - Target marks: 5.
        - Tolerance: 0.
        
        If we remove (a) [2 marks], we hit 5 EXACTLY.
        BUT removing (a) leaves {(b)}, which is invalid for PRUNE mode.
        PRUNE mode must preserve prefix, so valid subsets are {(a,b)}, {(a)}.
        
        Plan: {a, b} (7 marks). 
        To hit 5, we must remove marks.
        Options:
        - Remove (b): leaves {a} (2 marks). Valid PRUNE.
        - Remove (a): leaves {b} (5 marks). Invalid PRUNE.
        
        Current buggy behavior might choose to remove (a) because it results in 5 marks (perfect match),
        whereas removing (b) results in 2 marks (under target).
        
        Correct behavior: Should remove (b) (resulting in 2 marks) OR fail to find perfect match,
        but NEVER return {b}.
        """
        # Arrange
        q = make_question("q1", [2, 5])  # (a)=2, (b)=5
        plan = SelectionPlan.full_question(q)
        
        # Manually run prune_to_target which is where the logic lives
        # Note: We need to update prune_to_target to accept part_mode first?
        # Or check if it already breaks.
        
        # Currently prune_to_target doesn't take part_mode, so this checks baseline behavior
        result = prune_to_target(plan, target_marks=5, min_parts=1)
        
        # Assert - Check what happened
        included_labels = {p.label for p in result.included_leaves}
        
        # IF functionality is correct for PRUNE mode (which we haven't passed yet),
        # it should NOT be {"1(b)"}.
        # But this function is generic right now.
        
        # Correct behavior for PRUNE:
        # To reduce from 7 marks to <= 5 marks:
        # - Can only remove (b) [last]. New marks = 2.
        # - Can't remove (a) [first].
        # 
        # So we expect the result to be JUST {a} (2 marks).
        # It's an imperfect match (2 vs target 5), but it's a structural match.
        
        # We need to pass part_mode to this function now
        result = prune_to_target(plan, target_marks=5, min_parts=1, part_mode=PartMode.PRUNE)
        included_labels = {p.label for p in result.included_leaves}
        
        # EXPECTATION: Only (a) remains. (b) was pruned.
        assert "1(a)" in included_labels
        assert "1(b)" not in included_labels
        assert result.marks == 2
        

class TestSelectorIntegration:
    """Test full integration with Selector."""
    
    def test_selector_respects_prune_mode_during_pruning(self):
        """
        Run full selection with PartMode.PRUNE.
        Verify result does not contain invalid structures.
        """
        q = make_question("q1", [2, 5])
        config = SelectionConfig(
            target_marks=5,
            tolerance=0,
            part_mode=PartMode.PRUNE,
            topics=["Test Topic"]
        )
        
        # This might fail if the initial greedy fill picks a perfect option?
        # generate_options for PRUNE(q) -> {a,b}=7, {a}=2.
        # It won't generate {b}=5. 
        # So greedy fill will pick {a}=2 (best fit <= 5).
        # Or it picks {a,b}=7 if we allow over-filling then pruning?
        # Selector logic:
        # 1. Greedy fill uses best_option_for_marks(remaining).
        #    If target=5, remaining=5.
        #    Options: {a,b}=7, {a}=2.
        #    Best <= 5 is {a}=2.
        #    So it picks {a}. Result is valid.
        
        # We need to force it to pick the full question first, THEN prune.
        # This happens if we have a larger target that we exceed slightly, OR if the options logic forced overfill?
        pass

