"""
Unit tests for V2 question selection module.
Adapts V1 selection strategy tests to V2 architecture.
"""

import pytest
from unittest.mock import MagicMock, PropertyMock
from typing import List, Set

from gcse_toolkit.core.models import Question, Part
from gcse_toolkit.core.models.selection import SelectionPlan, SelectionResult
from gcse_toolkit.builder_v2.selection.selector import select_questions
from gcse_toolkit.builder_v2.selection.config import SelectionConfig
from gcse_toolkit.builder_v2.selection.options import generate_options, QuestionOptions
from gcse_toolkit.builder_v2.selection.part_mode import PartMode

# --- Mocks & Fixtures ---

@pytest.fixture
def mock_question():
    """Create a mock question with leaf parts."""
    q = MagicMock(spec=Question)
    q.id = "q1"
    q.topic = "Topic A"
    
    # Mock parts
    p1 = MagicMock(spec=Part)
    p1.label = "(a)"
    p1.marks = MagicMock()
    p1.marks.value = 2
    
    p1.is_valid = True
    p1.topic = None
    
    p2 = MagicMock(spec=Part)
    p2.label = "(b)"
    p2.marks = MagicMock()
    p2.marks.value = 3
    p2.is_valid = True
    p2.topic = None
    
    q.leaf_parts = [p1, p2]
    q.all_parts = [p1, p2]
    q.question_node = MagicMock()
    return q

# --- Test QuestionOptions (replaces V1 PlanOption checks) ---

def test_generate_options_full_question(mock_question):
    """Test that full question option is always generated first."""
    opts = generate_options(mock_question, part_mode=PartMode.ALL)
    
    assert opts.question == mock_question
    assert len(opts.options) == 1
    
    full_plan = opts.options[0]
    assert full_plan.is_full_question
    assert full_plan.marks == 5  # 2 + 3

def test_generate_options_partials(mock_question):
    """Test generation of partial options."""
    # SKIP mode should generate subsets
    # Subsets of {a:2, b:3}: {a, b} (5), {b} (3), {a} (2)
    opts = generate_options(mock_question, part_mode=PartMode.SKIP)
    
    assert len(opts.options) == 3
    marks = [o.marks for o in opts.options]
    assert 5 in marks
    assert 3 in marks
    assert 2 in marks

# --- Test SelectionResult (Logic Port) ---

def test_selection_result_deviation():
    """Test deviation calculation logic."""
    # V2 SelectionResult
    result = SelectionResult(
        plans=(),
        target_marks=50,
        tolerance=5
    )
    
    # Total marks 0
    assert result.deviation == 50
    assert not result.within_tolerance
    
    # Mock plan with 50 marks
    p = MagicMock(spec=SelectionPlan)
    p.marks = 50
    p.question = MagicMock()
    p.question.id = "q1"
    result_perfect = SelectionResult(
        plans=(p,),
        target_marks=50,
        tolerance=5
    )
    assert result_perfect.deviation == 0
    assert result_perfect.within_tolerance

def test_selection_result_undershoot_overshoot():
    """Test deviation handles undershoot and overshoot."""
    # Undershoot
    p_under = MagicMock(spec=SelectionPlan)
    p_under.marks = 40
    p_under.question = MagicMock()
    p_under.question.id = "q1"
    result_under = SelectionResult(
        plans=(p_under,),
        target_marks=50,
        tolerance=5
    )
    assert result_under.deviation == 10
    assert not result_under.within_tolerance
    
    # Overshoot
    p_over = MagicMock(spec=SelectionPlan)
    p_over.marks = 60
    p_over.question = MagicMock()
    p_over.question.id = "q1"
    result_over = SelectionResult(
        plans=(p_over,),
        target_marks=50,
        tolerance=5
    )
    assert result_over.deviation == 10
    assert not result_over.within_tolerance

# --- Test Selector Logic (Integration equivalent) ---

def test_select_questions_basic_fill():
    """Test basic greedy fill to reach target."""
    # Create 5 questions worth 10 marks each
    questions = []
    for i in range(5):
        q = MagicMock(spec=Question)
        q.id = f"q{i}"
        q.topic = "General"
        
        p = MagicMock(spec=Part)
        p.label = "a"
        p.marks = MagicMock()
        p.marks.value = 10
        q.leaf_parts = [p]
        q.all_parts = [p]  # REQUIRED for SelectionPlan validation
        questions.append(q)
        
    config = SelectionConfig(
        target_marks=30,
        tolerance=0,
        seed=42
    )
    
    result = select_questions(questions, config)
    
    assert result.total_marks == 30
    assert len(result.plans) == 3
    assert result.within_tolerance

def test_select_questions_topic_filtering():
    """Test that selector respects topic filters."""
    q1 = MagicMock(spec=Question)
    q1.id = "q1"
    q1.topic = "Topic A"
    q1.leaf_parts = [MagicMock(label="a", spec=Part)]
    q1.leaf_parts[0].marks = MagicMock(value=10)
    q1.leaf_parts[0].is_valid = True
    q1.leaf_parts[0].topic = None
    q1.all_parts = q1.leaf_parts
    q1.question_node = MagicMock()
    
    q2 = MagicMock(spec=Question)
    q2.id = "q2"
    q2.topic = "Topic B"
    q2.leaf_parts = [MagicMock(label="a", spec=Part)]
    q2.leaf_parts[0].marks = MagicMock(value=10)
    q2.leaf_parts[0].is_valid = True
    q2.leaf_parts[0].topic = None
    q2.all_parts = q2.leaf_parts
    q2.question_node = MagicMock()
    
    config = SelectionConfig(
        target_marks=10,
        topics={"Topic A"}
    )
    
    result = select_questions([q1, q2], config)
    
    assert len(result.plans) == 1
    assert result.plans[0].question.id == "q1"
    assert result.plans[0].question.topic == "Topic A"

def test_select_questions_empty_input():
    """Test handling of empty question list."""
    config = SelectionConfig(target_marks=50)
    result = select_questions([], config)
    assert result.total_marks == 0
    assert len(result.plans) == 0

