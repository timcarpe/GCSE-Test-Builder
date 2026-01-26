import pytest
from pathlib import Path
from gcse_toolkit.core.models import Question, Part, SliceBounds, Marks
from gcse_toolkit.core.models.parts import PartKind
from gcse_toolkit.builder_v2.selection.selector import select_questions
from gcse_toolkit.builder_v2.selection.config import SelectionConfig
from gcse_toolkit.builder_v2.selection.part_mode import PartMode

def create_mock_part(label, kind, marks, top, bottom, topic=None):
    return Part(
        label=label,
        kind=kind,
        marks=Marks.explicit(marks),
        bounds=SliceBounds(top=top, bottom=bottom, left=0, right=100),
        topic=topic
    )

def create_multi_topic_question(qid):
    # Question with 3 parts: 1(a) [Topic A], 1(b) [Topic B], 1(c) [None - inherits Topic A]
    p1 = create_mock_part(f"{qid}(a)", PartKind.LETTER, 2, 100, 200, topic="Topic A")
    p2 = create_mock_part(f"{qid}(b)", PartKind.LETTER, 3, 200, 300, topic="Topic B")
    p3 = create_mock_part(f"{qid}(c)", PartKind.LETTER, 4, 300, 400, topic=None) # Inherits from Q
    
    root = Part(
        label=qid,
        kind=PartKind.QUESTION,
        marks=Marks.aggregate([p1, p2, p3]),
        bounds=SliceBounds(top=0, bottom=400, left=0, right=100),
        children=(p1, p2, p3)
    )
    
    return Question(
        id=qid,
        exam_code="0478",
        year=2024,
        paper=1,
        variant=1,
        topic="Topic A",
        question_node=root,
        composite_path=Path("mock.png"),
        regions_path=Path("mock.json")
    )

def test_skip_mode_filters_by_part_topic():
    """Verify that PartMode.SKIP correctly filters parts based on requested topics."""
    q = create_multi_topic_question("q1")
    
    # CASE 1: Request "Topic B" only
    config_b = SelectionConfig(
        target_marks=10,
        topics=["Topic B"],
        part_mode=PartMode.SKIP
    )
    
    result_b = select_questions([q], config_b)
    assert result_b.question_count == 1
    plan_b = result_b.plans[0]
    
    # Should ONLY include 1(b)
    assert plan_b.included_parts == {"q1(b)"}
    assert plan_b.marks == 3

    # CASE 2: Request "Topic A" only
    # Note: 1(a) has "Topic A", 1(c) inherits "Topic A" from question
    config_a = SelectionConfig(
        target_marks=10,
        topics=["Topic A"],
        part_mode=PartMode.SKIP
    )
    
    result_a = select_questions([q], config_a)
    assert result_a.question_count == 1
    plan_a = result_a.plans[0]
    
    # Should include 1(a) and 1(c)
    assert plan_a.included_parts == {"q1(a)", "q1(c)"}
    assert plan_a.marks == 2 + 4

def test_prune_mode_does_not_skip_middle_topics():
    """Verify that PartMode.PRUNE keeps middle parts even if topics mismatch (it only cuts tail)."""
    q = create_multi_topic_question("q1")
    
    # Request "Topic A" in PRUNE mode. 
    # Structure: 1(a)[A], 1(b)[B], 1(c)[A]
    # PRUNE mode should keep all unless it needs to cut from the end.
    config = SelectionConfig(
        target_marks=10,
        topics=["Topic A"],
        part_mode=PartMode.PRUNE
    )
    
    result = select_questions([q], config)
    plan = result.plans[0]
    
    # Should include ALL parts because it's PRUNE mode and we didn't overshoot.
    # Topic filtering in PRUNE mode is only used to determine initial validity
    # and potential tail cuts.
    # Note: allowed_labels in PRUNE/SKIP mode contains only leaf labels.
    assert plan.included_parts == {"q1(a)", "q1(b)", "q1(c)"}
    assert plan.marks == 9

def test_all_mode_includes_everything():
    """Verify that PartMode.ALL ignores topic mismatches within parts."""
    q = create_multi_topic_question("q1")
    
    config = SelectionConfig(
        target_marks=10,
        topics=["Topic B"],
        part_mode=PartMode.ALL
    )
    
    result = select_questions([q], config)
    plan = result.plans[0]
    
    # Should include EVERYTHING
    assert plan.is_full_question
    assert plan.marks == 9


def test_prune_mode_removes_from_tail_only():
    """Verify PRUNE mode only removes contiguous suffix when pruning to mark target."""
    # Create question: (a)=10, (b)=2, (c)=3. Total=15.
    p1 = create_mock_part("q1(a)", PartKind.LETTER, 10, 100, 200)
    p2 = create_mock_part("q1(b)", PartKind.LETTER, 2, 200, 300)
    p3 = create_mock_part("q1(c)", PartKind.LETTER, 3, 300, 400)
    
    root = Part(
        label="q1",
        kind=PartKind.QUESTION,
        marks=Marks.aggregate([p1, p2, p3]),
        bounds=SliceBounds(top=0, bottom=400, left=0, right=100),
        children=(p1, p2, p3)
    )
    
    q = Question(
        id="q1",
        exam_code="0478",
        year=2024,
        paper=1,
        variant=1,
        topic="Topic A",
        question_node=root,
        composite_path=Path("mock.png"),
        regions_path=Path("mock.json")
    )
    
    # Target 12 marks with PRUNE mode
    # Should select {a,b} = 12 by removing (c) from tail
    # NOT {a,c} = 13 which would skip middle part (b)
    config = SelectionConfig(
        target_marks=12,
        tolerance=0,
        part_mode=PartMode.PRUNE
    )
    
    result = select_questions([q], config)
    plan = result.plans[0]
    
    # PRUNE semantics: only contiguous suffix removal allowed
    # {a,b,c} -> {a,b} is valid (removed c)
    # {a,b,c} -> {a,c} would be invalid (skipped b)
    assert plan.included_parts == {"q1(a)", "q1(b)"}
    assert plan.marks == 12
