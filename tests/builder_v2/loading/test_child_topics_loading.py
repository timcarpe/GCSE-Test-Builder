"""
Tests for child_topics loading and part_mode topic filtering.

Verifies:
1. child_topics are correctly parsed from metadata
2. child_topics are applied to Part.topic during loading
3. _generate_all_options respects part_mode for topic filtering
"""

import pytest
from unittest.mock import MagicMock

from gcse_toolkit.core.models import Question, Part, Marks
from gcse_toolkit.builder_v2.loading.parser import parse_metadata_from_dict, ParsedMetadata
from gcse_toolkit.builder_v2.selection.selector import _filter_topic_from_tail
from gcse_toolkit.builder_v2.selection.config import SelectionConfig
from gcse_toolkit.builder_v2.selection.selector import select_questions
from gcse_toolkit.builder_v2.selection.part_mode import PartMode


class TestParseChildTopics:
    """Tests for child_topics parsing."""
    
    def test_parses_child_topics_when_present(self):
        """Should parse child_topics field from metadata dict."""
        data = {
            "question_id": "0478_s24_qp_12_q1",
            "exam_code": "0478",
            "year": 2024,
            "paper": 1,
            "variant": 2,
            "question_number": 1,
            "total_marks": 10,
            "part_count": 2,
            "topic": "01. Data Representation",
            "child_topics": {
                "1(a)": "01. Data Representation",
                "1(b)": "02. Databases"
            }
        }
        
        result = parse_metadata_from_dict(data)
        
        assert result.child_topics == {
            "1(a)": "01. Data Representation",
            "1(b)": "02. Databases"
        }
    
    def test_defaults_to_empty_dict_when_missing(self):
        """Should default child_topics to empty dict for older metadata."""
        data = {
            "question_id": "0478_s24_qp_12_q1",
            "exam_code": "0478",
            "year": 2024,
            "paper": 1,
            "variant": 2,
            "question_number": 1,
            "total_marks": 10,
            "part_count": 2,
            "topic": "01. Data Representation",
        }
        
        result = parse_metadata_from_dict(data)
        
        assert result.child_topics == {}


class TestFilterTopicFromTail:
    """Tests for _filter_topic_from_tail helper."""
    
    def _make_mock_part(self, label: str, topic: str = None):
        """Create a mock leaf part."""
        p = MagicMock(spec=Part)
        p.label = label
        p.topic = topic
        p.is_leaf = True
        p.children = ()
        return p
    
    def _make_mock_question(self, parts: list, default_topic: str):
        """Create a mock question with given leaf parts."""
        q = MagicMock(spec=Question)
        q.topic = default_topic
        q.leaf_parts = parts
        return q
    
    def test_removes_trailing_mismatched_parts(self):
        """Should remove mismatched parts from end."""
        # [a:A, b:B, c:A, d:B, e:B, f:B] with topics={A} -> {a, b, c}
        parts = [
            self._make_mock_part("a", "A"),
            self._make_mock_part("b", "B"),
            self._make_mock_part("c", "A"),
            self._make_mock_part("d", "B"),
            self._make_mock_part("e", "B"),
            self._make_mock_part("f", "B"),
        ]
        q = self._make_mock_question(parts, "A")
        
        result = _filter_topic_from_tail(q, {"A"})
        
        assert result == {"a", "b", "c"}
    
    def test_keeps_all_when_last_matches(self):
        """Should keep all parts if last part matches."""
        parts = [
            self._make_mock_part("a", "A"),
            self._make_mock_part("b", "B"),
            self._make_mock_part("c", "A"),
        ]
        q = self._make_mock_question(parts, "A")
        
        result = _filter_topic_from_tail(q, {"A"})
        
        assert result == {"a", "b", "c"}
    
    def test_returns_none_when_no_matches(self):
        """Should return None when no parts match."""
        parts = [
            self._make_mock_part("a", "B"),
            self._make_mock_part("b", "C"),
        ]
        q = self._make_mock_question(parts, "A")
        
        result = _filter_topic_from_tail(q, {"X"})
        
        assert result is None
    
    def test_uses_question_topic_as_fallback(self):
        """Should use question.topic when part.topic is None."""
        parts = [
            self._make_mock_part("a", None),  # Inherits q.topic = "A"
            self._make_mock_part("b", "B"),
        ]
        q = self._make_mock_question(parts, "A")
        
        result = _filter_topic_from_tail(q, {"A"})
        
        assert result == {"a"}


class TestPartModeTopicFiltering:
    """Tests for part_mode respecting topic filtering."""
    
    def _make_mock_part(self, label: str, marks: int, topic: str = None):
        """Create a mock leaf part."""
        p = MagicMock(spec=Part)
        p.label = label
        p.marks = Marks.explicit(marks)
        p.total_marks = marks
        p.topic = topic
        p.is_leaf = True
        p.is_valid = True
        p.children = ()
        return p
    
    def _make_mock_question(self, qid: str, parts: list, default_topic: str):
        """Create a mock question."""
        q = MagicMock(spec=Question)
        q.id = qid
        q.topic = default_topic
        q.leaf_parts = parts
        q.all_parts = parts
        q.total_marks = sum(p.marks.value for p in parts)
        
        if parts:
            q.question_node = parts[0]
        else:
            q.question_node = MagicMock(spec=Part)
            q.question_node.label = "1"
        
        for p in parts:
            p.question = q
        
        return q
    
    def test_all_mode_includes_all_parts(self):
        """ALL mode should not filter child parts by topic."""
        # Q1: Topic A with mixed child topics
        p_a = self._make_mock_part("1(a)", 5, topic="Topic A")
        p_b = self._make_mock_part("1(b)", 5, topic="Topic B")
        q1 = self._make_mock_question("q1", [p_a, p_b], "Topic A")
        
        config = SelectionConfig(
            target_marks=10,
            topics={"Topic A"},
            part_mode=PartMode.ALL
        )
        
        result = select_questions([q1], config)
        
        # Should include full question (both parts) in ALL mode
        assert result.question_count == 1
        plan = result.plans[0]
        assert "1(a)" in plan.included_parts
        assert "1(b)" in plan.included_parts
    
    def test_skip_mode_excludes_mismatched_parts(self):
        """SKIP mode should exclude parts with mismatched topics."""
        p_a = self._make_mock_part("1(a)", 5, topic="Topic A")
        p_b = self._make_mock_part("1(b)", 5, topic="Topic B")
        q1 = self._make_mock_question("q1", [p_a, p_b], "Topic A")
        
        config = SelectionConfig(
            target_marks=5,
            topics={"Topic A"},
            part_mode=PartMode.SKIP
        )
        
        result = select_questions([q1], config)
        
        # Should only include 1(a) which matches Topic A
        assert result.question_count == 1
        plan = result.plans[0]
        assert "1(a)" in plan.included_parts
        assert "1(b)" not in plan.included_parts
