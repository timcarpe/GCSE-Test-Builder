
import logging
from pathlib import Path
from gcse_toolkit.builder_v2.selection.selector import select_questions
from gcse_toolkit.builder_v2.selection.config import SelectionConfig
from gcse_toolkit.core.models.questions import Question
from gcse_toolkit.core.models.parts import Part, PartKind
from gcse_toolkit.core.models.parts import Marks
from gcse_toolkit.core.models.bounds import SliceBounds

# Configure logging to capture output
class LogCaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs = []
    def emit(self, record):
        self.logs.append(self.format(record))

handler = LogCaptureHandler()
logger = logging.getLogger("gcse_toolkit.builder_v2.selection.selector")
logger.addHandler(handler)
logger.setLevel(logging.WARNING)

def make_question(qid, marks, topic="Topic A"):
    bounds = SliceBounds(0, 100)
    leaf_bounds = SliceBounds(10, 90)
    node = Part(
        label=qid, 
        kind=PartKind.QUESTION, 
        marks=Marks.explicit(marks), 
        bounds=bounds,
        children=(Part(label=f"{qid}(a)", kind=PartKind.LETTER, marks=Marks.explicit(marks), bounds=leaf_bounds),)
    )
    return Question(
        id=qid,
        exam_code="0478",
        year=2024,
        paper=1,
        variant=1,
        topic=topic,
        question_node=node,
        composite_path=Path("dummy.png"),
        regions_path=Path("dummy.json")
    )

def test_backfill_behavior():
    # Setup questions
    q1 = make_question("Q1", 10)  # Pinned
    q2 = make_question("Q2", 5)   # Keyword match
    q3 = make_question("Q3", 5)   # Keyword match
    questions = [q1, q2, q3]

    # CASE 1: Backfill ON (default)
    handler.logs = []
    config_on = SelectionConfig(
        target_marks=20,
        keyword_mode=True,
        pinned_question_ids={"Q1"},
        keyword_matched_labels={"Q2": {"Q2(a)"}, "Q3": {"Q3(a)"}},
        allow_keyword_backfill=True,
        seed=42
    )
    result_on = select_questions(questions, config_on)
    print(f"Backfill ON: Selected {len(result_on.plans)} questions, Total marks: {result_on.total_marks}")
    for log in handler.logs:
        print(f"LOG: {log}")
    
    assert result_on.total_marks == 20
    assert any("pinned questions have 10 marks and 2 question parts were added" in log for log in handler.logs)

    # CASE 2: Backfill OFF
    handler.logs = []
    config_off = SelectionConfig(
        target_marks=20,
        keyword_mode=True,
        pinned_question_ids={"Q1"},
        keyword_matched_labels={"Q2": {"Q2(a)"}, "Q3": {"Q3(a)"}},
        allow_keyword_backfill=False,
        seed=42
    )
    result_off = select_questions(questions, config_off)
    print(f"\nBackfill OFF: Selected {len(result_off.plans)} questions, Total marks: {result_off.total_marks}")
    for log in handler.logs:
        print(f"LOG: {log}")
    
    assert result_off.total_marks == 10
    assert any("pinned questions have 10 marks and 0 question parts were added" in log for log in handler.logs)

if __name__ == "__main__":
    try:
        test_backfill_behavior()
        print("\nVerification SUCCESSFUL!")
    except Exception as e:
        print(f"\nVerification FAILED: {e}")
        import traceback
        traceback.print_exc()
