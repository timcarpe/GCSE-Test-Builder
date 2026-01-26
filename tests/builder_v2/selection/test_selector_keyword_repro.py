"""
Reproduction test for keyword mode over-selection bug.
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

def make_question(qid: str, marks: int) -> Question:
    """Helper to create test questions."""
    # Simple question with 1 part matching the marks
    leaves = [
        Part(
            f"{qid}(a)",
            PartKind.LETTER,
            Marks.explicit(marks),
            SliceBounds(0, 100)
        )
    ]
    question_node = Part(
        qid,
        PartKind.QUESTION,
        Marks.aggregate(leaves),
        SliceBounds(0, 100),
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

def test_keyword_mode_respects_mark_limit():
    """
    Test that keyword mode respects the mark target even if many questions match.
    
    Bug Description:
        - We have 10 questions, each 5 marks.
        - All 10 match the keyword.
        - Target is 5 marks.
        - Currently (Bug), it force-adds all 10 questions -> 50 marks.
        - Expected: Select 1 question -> 5 marks.
    """
    # 1. Setup questions (10 questions, 5 marks each)
    questions = [make_question(f"q{i}", 5) for i in range(10)]
    
    # 2. Setup config with keyword mode matching ALL questions
    # Create dict mapping all question IDs to their part label
    matched_labels = {
        q.id: {f"{q.id}(a)"} 
        for q in questions
    }
    
    config = SelectionConfig(
        target_marks=5,
        tolerance=2,
        keyword_mode=True,
        keyword_matched_labels=matched_labels
    )
    
    # 3. Run selection
    result = select_questions(questions, config)
    
    # 4. Assert
    # If bug exists, count will be 10 and marks 50
    # If fixed, count should be 1 and marks 5
    print(f"Selected {result.question_count} questions, {result.total_marks} marks")
    
    assert result.question_count == 1, f"Expected 1 question, got {result.question_count}"
    assert result.total_marks == 5, f"Expected 5 marks, got {result.total_marks}"
