"""
Tests for multi-topic selection logic.

Verifies that:
1. Questions with multiple topics are correctly handled.
2. Parts matching requested topics are included.
3. Parts NOT matching requested topics are excluded.
4. Metadata correctly attributes marks to specific topics.
"""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

from gcse_toolkit.core.models import Question, Part, Marks
from gcse_toolkit.core.models.selection import SelectionResult
from gcse_toolkit.builder_v2.selection.selector import select_questions
from gcse_toolkit.builder_v2.selection.config import SelectionConfig
from gcse_toolkit.builder_v2.controller import _build_metadata
from gcse_toolkit.builder_v2.layout import LayoutResult


def create_mock_part(label, marks, topic=None):
    """Helper to create a mock leaf part."""
    p = MagicMock(spec=Part)
    p.label = label
    p.marks = Marks.explicit(marks)
    p.total_marks = marks
    p.topic = topic
    p.is_leaf = True
    p.children = ()
    return p

def create_mock_question(qid, default_topic, parts):
    """Helper to create a mock question with parts."""
    q = MagicMock(spec=Question)
    q.id = qid
    q.topic = default_topic
    q.leaf_parts = parts
    q.all_parts = parts # Simplified
    q.total_marks = sum(p.marks.value for p in parts)
    
    # Needs a root node for metadata generation (zip export)
    # Just use the first part as the "root" for these simple tests
    if parts:
        q.question_node = parts[0]
    else:
        q.question_node = MagicMock(spec=Part)
        q.question_node.label = "1"
    
    # Link parts to question
    for p in parts:
        p.question = q
        
    return q

class TestMultiTopicSelection:
    
    def test_selects_multi_topic_question(self):
        """
        Scenario:
        Q1: Default Topic A
            - 1(a): Topic A (5 marks)
            - 1(b): Topic B (5 marks)
        
        Target: 10 marks
        Topics: {Topic A, Topic B}
        
        Expected:
        - Q1 selected fully.
        - Covered topics include both A and B.
        """
        # Arrange
        p_a = create_mock_part("1(a)", 5, topic="Topic A")
        p_b = create_mock_part("1(b)", 5, topic="Topic B")
        q1 = create_mock_question("q1", "Topic A", [p_a, p_b])
        
        config = SelectionConfig(
            target_marks=10,
            topics={"Topic A", "Topic B"}
        )
        
        # Act
        result = select_questions([q1], config)
        
        # Assert
        assert result.question_count == 1
        assert "Topic A" in result.covered_topics
        assert "Topic B" in result.covered_topics
        
    def test_excludes_irrelevant_parts(self):
        """
        Scenario:
        Q1: Default Topic A
            - 1(a): Topic A (5 marks)
            - 1(b): Topic B (5 marks)
            
        Target: 5 marks
        Topics: {Topic A}
        
        Expected:
        - Q1 selected PARTIALLY (only 1(a)).
        - 1(b) should be excluded because Topic B is not requested.
        """
        # Arrange
        p_a = create_mock_part("1(a)", 5, topic="Topic A")
        p_b = create_mock_part("1(b)", 5, topic="Topic B")
        q1 = create_mock_question("q1", "Topic A", [p_a, p_b])
        
        config = SelectionConfig(
            target_marks=5,
            topics={"Topic A"}
        )
        
        # Act
        result = select_questions([q1], config)
        
        # Assert
        assert len(result.plans) == 1
        plan = result.plans[0]
        
        assert "1(a)" in plan.included_parts
        assert "1(b)" not in plan.included_parts
        assert plan.marks == 5

    def test_metadata_attributes_marks_correctly(self):
        """
        Scenario:
        Q1: Default Topic A
            - 1(a): Topic A (5 marks)
            - 1(b): Topic B (5 marks)
            
        Selection: Full Q1 selected.
        
        Expected Metadata:
        - marks_per_topic: {Topic A: 5, Topic B: 5}
        """
        # Arrange
        p_a = create_mock_part("1(a)", 5, topic="Topic A")
        p_b = create_mock_part("1(b)", 5, topic="Topic B")
        q1 = create_mock_question("q1", "Topic A", [p_a, p_b])
        
        # Mock SelectionPlan
        mock_plan = MagicMock()
        mock_plan.question = q1
        mock_plan.marks = 10
        mock_plan.included_leaves = [p_a, p_b]
        mock_plan.included_parts = {"1(a)", "1(b)"}
        mock_plan.is_full_question = True
        
        selection = SelectionResult(
            plans=(mock_plan,),
            target_marks=10,
            tolerance=0
        )
        
        # Mock Build Config
        config = MagicMock()
        config.exam_code = "0478"
        config.target_marks = 10
        config.tolerance = 0
        config.seed = 123
        config.topics = {"Topic A", "Topic B"}
        config.years = None
        config.papers = None
        config.include_markscheme = False
        config.keyword_mode = False
        config.export_zip = False
        
        # Mock Layout
        layout = MagicMock(spec=LayoutResult)
        layout.pages = []
        layout.page_count = 1
        
        # Act
        metadata = _build_metadata(config, selection, layout)
        
        # Assert
        stats = metadata["stats"]
        assert stats["marks_per_topic"]["Topic A"] == 5
        assert stats["marks_per_topic"]["Topic B"] == 5
        assert stats["parts_per_topic"]["Topic A"] == 1
        assert stats["parts_per_topic"]["Topic B"] == 1

    def test_metadata_works_in_keyword_mode(self):
        """
        Scenario: Keyword Mode (no topic filters explicitly set for exclusion, 
        but we want to ensure metadata still clumps by topic correctly).
        
        Q1: Topic X
           - 1(a) [selected via keyword]
        
        Expected:
        - Metadata reports Topic X: marks.
        """
        # Arrange
        p_a = create_mock_part("1(a)", 3, topic=None) # Inherits Q topic
        q1 = create_mock_question("q1", "Topic X", [p_a])
        
        # Mock SelectionPlan
        mock_plan = MagicMock()
        mock_plan.question = q1
        mock_plan.marks = 3
        mock_plan.included_leaves = [p_a]
        mock_plan.included_parts = {"1(a)"}
        mock_plan.is_full_question = False
        
        selection = SelectionResult(
            plans=(mock_plan,),
            target_marks=3,
            tolerance=0
        )
        
        # Mock Build Config for Keyword Mode
        config = MagicMock()
        config.exam_code = "0478"
        config.target_marks = 3
        config.tolerance = 0
        config.seed = 123
        config.topics = None # Might be None in keyword mode
        config.keyword_mode = True
        config.include_markscheme = False
        config.years = None
        config.papers = None
        
        # Mock Layout
        layout = MagicMock(spec=LayoutResult)
        layout.pages = []
        layout.page_count = 1
        
        # Act
        metadata = _build_metadata(config, selection, layout)
        
        # Assert
        stats = metadata["stats"]
        assert stats["marks_per_topic"]["Topic X"] == 3
        assert stats["parts_per_topic"]["Topic X"] == 1
        
        details = metadata["selection_details"][0]
        assert details["topic"] == "Topic X"
