"""
Tests for PartMode functionality in selection options.

Verified: 2024-12-18
"""

import pytest
from pathlib import Path

from gcse_toolkit.core.models.marks import Marks
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.core.models.parts import Part, PartKind
from gcse_toolkit.core.models.questions import Question
from gcse_toolkit.builder_v2.selection.part_mode import PartMode
from gcse_toolkit.builder_v2.selection.options import generate_options


def make_question_with_parts(
    qid: str,
    topic: str,
    marks: list[int],
) -> Question:
    """Helper to create test questions with sequential parts (a), (b), (c), etc."""
    leaves = [
        Part(
            f"{qid[1:]}({chr(97+i)})",  # e.g., "1(a)", "1(b)", "1(c)"
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
def question_abc() -> Question:
    """A question with 3 parts: (a)=2, (b)=3, (c)=5 marks."""
    return make_question_with_parts("q1", "Topic", [2, 3, 5])


class TestPartModeAll:
    """Tests for PartMode.ALL - only full question."""

    def test_generates_only_full_question(self, question_abc):
        """ALL mode should only generate the full question option."""
        opts = generate_options(question_abc, part_mode=PartMode.ALL)
        
        assert len(opts.options) == 1
        assert opts.options[0].is_full_question
        assert opts.options[0].marks == 10  # 2 + 3 + 5

    def test_single_part_question_works(self):
        """ALL mode should work for single-part questions."""
        q = make_question_with_parts("q1", "Topic", [5])
        opts = generate_options(q, part_mode=PartMode.ALL)
        
        assert len(opts.options) == 1
        assert opts.options[0].marks == 5


class TestPartModePrune:
    """Tests for PartMode.PRUNE - remove from end only."""

    def test_generates_contiguous_suffixes(self, question_abc):
        """PRUNE mode should generate contiguous suffix subsets."""
        opts = generate_options(question_abc, part_mode=PartMode.PRUNE)
        
        # Expected: full (a,b,c), (a,b), (a)
        assert len(opts.options) == 3
        
        # Get sets of labels for each option
        option_labels = [frozenset(p.label for p in opt.included_leaves) for opt in opts.options]
        
        assert frozenset(["1(a)", "1(b)", "1(c)"]) in option_labels  # Full
        assert frozenset(["1(a)", "1(b)"]) in option_labels         # Pruned (c)
        assert frozenset(["1(a)"]) in option_labels                  # Pruned (b) and (c)

    def test_no_non_contiguous_options(self, question_abc):
        """PRUNE mode should NOT allow non-contiguous subsets."""
        opts = generate_options(question_abc, part_mode=PartMode.PRUNE)
        
        option_labels = [frozenset(p.label for p in opt.included_leaves) for opt in opts.options]
        
        # These are skipping (non-contiguous) and should NOT be present
        assert frozenset(["1(a)", "1(c)"]) not in option_labels
        assert frozenset(["1(b)", "1(c)"]) not in option_labels
        assert frozenset(["1(b)"]) not in option_labels
        assert frozenset(["1(c)"]) not in option_labels

    def test_single_part_question_same_as_all(self):
        """PRUNE mode should produce same result as ALL for single-part questions."""
        q = make_question_with_parts("q1", "Topic", [5])
        
        opts_prune = generate_options(q, part_mode=PartMode.PRUNE)
        opts_all = generate_options(q, part_mode=PartMode.ALL)
        
        assert len(opts_prune.options) == len(opts_all.options) == 1


class TestPartModeSkip:
    """Tests for PartMode.SKIP - remove from anywhere."""

    def test_generates_all_combinations(self, question_abc):
        """SKIP mode should generate all possible subsets."""
        opts = generate_options(question_abc, part_mode=PartMode.SKIP)
        
        # For 3 parts: 1 full + 3 pairs + 3 singles = 7 options
        assert len(opts.options) == 7

    def test_includes_non_contiguous_options(self, question_abc):
        """SKIP mode should include non-contiguous subsets."""
        opts = generate_options(question_abc, part_mode=PartMode.SKIP)
        
        option_labels = [frozenset(p.label for p in opt.included_leaves) for opt in opts.options]
        
        # Non-contiguous options should be present
        assert frozenset(["1(a)", "1(c)"]) in option_labels  # Skipped (b)
        assert frozenset(["1(b)"]) in option_labels          # Just (b)
        assert frozenset(["1(c)"]) in option_labels          # Just (c)

    def test_options_sorted_by_marks_descending(self, question_abc):
        """Options should be sorted by marks (descending)."""
        opts = generate_options(question_abc, part_mode=PartMode.SKIP)
        
        marks = [opt.marks for opt in opts.options]
        assert marks == sorted(marks, reverse=True)


class TestPartModeDefault:
    """Tests for default behavior."""

    def test_default_is_skip(self, question_abc):
        """Default part_mode should be SKIP."""
        opts_default = generate_options(question_abc)
        opts_skip = generate_options(question_abc, part_mode=PartMode.SKIP)
        
        assert len(opts_default.options) == len(opts_skip.options)
