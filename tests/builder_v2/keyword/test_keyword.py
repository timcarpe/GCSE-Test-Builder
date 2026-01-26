"""
Unit tests for KeywordIndex and KeywordSearchResult.

Tests keyword search functionality for V2 builder.
"""

import pytest
from gcse_toolkit.builder_v2.keyword.models import (
    KeywordEntry,
    KeywordSearchResult,
    _normalize,
)
from gcse_toolkit.builder_v2.keyword.index import KeywordIndex


class TestNormalize:
    """Tests for text normalization."""
    
    def test_normalize_lowercase(self):
        """Normalize converts to lowercase."""
        assert _normalize("Binary") == "binary"
    
    def test_normalize_removes_spaces(self):
        """Normalize removes spaces."""
        assert _normalize("binary search") == "binarysearch"
    
    def test_normalize_combined(self):
        """Normalize applies all transformations."""
        assert _normalize("Binary Search Algorithm") == "binarysearchalgorithm"


class TestKeywordEntry:
    """Tests for KeywordEntry model."""
    
    def test_matches_substring_in_part(self):
        """Substring match finds term in part text."""
        entry = KeywordEntry(
            question_id="q1",
            root_text="Question about algorithms",
            part_texts={"1(a)": "Explain binary search", "1(b)": "Write code"},
        )
        
        matched = entry.matches_substring("binary")
        
        assert "1(a)" in matched
        assert "1(b)" not in matched
    
    def test_matches_substring_in_root(self):
        """Substring match in root includes all parts."""
        entry = KeywordEntry(
            question_id="q1",
            root_text="Binary search question",
            part_texts={"1(a)": "Part A", "1(b)": "Part B"},
        )
        
        matched = entry.matches_substring("binary")
        
        assert "1(a)" in matched
        assert "1(b)" in matched
    
    def test_matches_substring_case_insensitive(self):
        """Substring match is case insensitive."""
        entry = KeywordEntry(
            question_id="q1",
            root_text="",
            part_texts={"1(a)": "BINARY search"},
        )
        
        matched = entry.matches_substring("binary")
        
        assert "1(a)" in matched


class TestKeywordSearchResult:
    """Tests for KeywordSearchResult model."""
    
    def test_question_ids_aggregates(self):
        """question_ids returns union of all matches."""
        result = KeywordSearchResult(
            keyword_hits={"kw1": {"q1", "q2"}, "kw2": {"q2", "q3"}},
            aggregate_labels={"q1": {"a"}, "q2": {"b"}, "q3": {"c"}},
        )
        
        assert result.question_ids == frozenset({"q1", "q2", "q3"})
    
    def test_is_empty_when_no_matches(self):
        """is_empty returns True when no matches."""
        result = KeywordSearchResult()
        assert result.is_empty
    
    def test_is_empty_false_when_matches(self):
        """is_empty returns False when matches exist."""
        result = KeywordSearchResult(aggregate_labels={"q1": {"a"}})
        assert not result.is_empty
    
    def test_total_questions(self):
        """total_questions returns correct count."""
        result = KeywordSearchResult(
            aggregate_labels={"q1": {"a"}, "q2": {"b"}}
        )
        assert result.total_questions == 2


class TestKeywordIndex:
    """Tests for KeywordIndex class."""
    
    def test_search_empty_keywords_returns_empty(self):
        """Searching with no keywords returns empty result."""
        index = KeywordIndex()
        result = index.search([])
        assert result.is_empty
    
    def test_search_empty_index_returns_empty(self):
        """Searching empty index returns empty result."""
        index = KeywordIndex()
        result = index.search(["binary"])
        assert result.is_empty
    
    def test_question_count(self):
        """question_count reflects indexed questions."""
        index = KeywordIndex()
        assert index.question_count == 0
