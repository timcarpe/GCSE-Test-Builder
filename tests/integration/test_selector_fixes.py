
import pytest
from pathlib import Path
from gcse_toolkit.core.models import Question, Part
from gcse_toolkit.core.models.marks import Marks
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.core.models.selection import SelectionPlan
from gcse_toolkit.builder_v2.selection.selector import select_questions
from gcse_toolkit.builder_v2.selection.config import SelectionConfig
from gcse_toolkit.builder_v2.selection.pruning import prune_selection

def create_mock_question(qid, marks_values):
    """Helper to create a question with specific part marks and correct offsets."""
    if isinstance(marks_values, int):
        marks_values = [marks_values]
        
    leaves = []
    for i, m in enumerate(marks_values):
        leaves.append(Part(
            label=f"({chr(97+i)})", kind="letter", marks=Marks.explicit(m),
            bounds=SliceBounds(top=i*100, bottom=(i+1)*100, left=0, right=100),
            children=()
        ))
    
    root = Part(
        label="1", kind="question", marks=Marks.explicit(0),
        bounds=SliceBounds(top=0, bottom=len(marks_values)*100, left=0, right=100),
        children=tuple(leaves)
    )
    return Question(
        id=qid, exam_code="0000", year=2024, paper=1, variant=1,
        topic="Test Topic", question_node=root,
        composite_path=Path("/tmp/fake.png"), regions_path=Path("/tmp/fake.json")
    )

def test_atomic_overshoot_rejection():
    """Verify that the selector prefers a smaller undershoot over a larger overshoot (Atomic Question Case)."""
    # Setup: Q1(4), Q2(12). Target 8.
    q1 = create_mock_question("q1", 4)
    q2 = create_mock_question("q2", 12)
    config = SelectionConfig(target_marks=8, tolerance=0)
    
    result = select_questions([q1, q2], config)
    
    # Should pick Q1 (4 marks) as it's closer to 8 than Q2 (12 marks)
    # 8-4=4 vs 12-8=4. In case of tie, undershoot is usually safer or first seen.
    # Actually, current_error (8) -> new_error (4). So Q1 is added.
    # Then current_error (4) -> new_error (8) for Q2. So Q2 is rejected.
    assert result.total_marks == 4
    assert result.plans[0].question.id == "q1"

def test_pruning_absolute_error():
    """Verify that pruning stops if removing a part makes the absolute error worse."""
    # Setup: Q1 with parts [7, 5]. Target 10.
    q1 = create_mock_question("q1", [7, 5])
    plan = SelectionPlan(q1, frozenset(["(a)", "(b)"])) # 12 marks
    
    pruned = prune_selection([plan], target_marks=10, tolerance=0)
    
    # Should NOT prune because 12 is closer to 10 than 7 is.
    # Error before: |10-12|=2. Error after pruning (b): |10-7|=3.
    assert sum(p.marks for p in pruned) == 12
    assert len(pruned[0].included_leaves) == 2

def test_complex_pruning_improvement():
    """Verify that pruning STILL WORKS when it actually improves accuracy."""
    # Setup: Q1 with parts [10, 1]. Target 10.
    q1 = create_mock_question("q1", [10, 1])
    plan = SelectionPlan(q1, frozenset(["(a)", "(b)"])) # 11 marks
    
    pruned = prune_selection([plan], target_marks=10, tolerance=0)
    
    # Should prune (b) because 10 is closer to 10 than 11 is.
    assert sum(p.marks for p in pruned) == 10
    assert len(pruned[0].included_leaves) == 1
    assert pruned[0].included_leaves[0].label == "(a)"
