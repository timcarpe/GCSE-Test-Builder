"""
Module: builder_v2.keyword.models

Purpose:
    Data models for keyword search results.
    Immutable dataclasses representing indexed entries and search results.

Key Classes:
    - KeywordEntry: Indexed text for a question
    - KeywordSearchResult: Aggregated search results

Dependencies:
    - dataclasses (std)
    - gcse_toolkit.core.models.questions: Question model

Used By:
    - builder_v2.keyword.index: KeywordIndex
    - builder_v2.controller: Keyword filtering
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Set


@dataclass(frozen=True)
class KeywordEntry:
    """
    Indexed text entry for a single question.
    
    Contains searchable text blobs extracted from question content.
    
    Attributes:
        question_id: Question identifier (e.g., "0478_m24_qp_12_q1")
        root_text: Combined text from question root/header
        part_texts: Dict mapping part label to searchable text
        
    Example:
        >>> entry = KeywordEntry(
        ...     question_id="q1",
        ...     root_text="Explain binary search",
        ...     part_texts={"1(a)": "Define binary", "1(b)": "Write code"}
        ... )
    """
    question_id: str
    root_text: str = ""
    part_texts: Dict[str, str] = field(default_factory=dict)
    
    def matches_substring(self, term: str) -> Set[str]:
        """
        Find parts matching term as substring (case-insensitive).
        
        Args:
            term: Normalized search term (lowercase, no spaces)
            
        Returns:
            Set of matching part labels
        """
        matched = set()
        
        # Check part texts
        for label, text in self.part_texts.items():
            if term in _normalize(text):
                matched.add(label)
        
        # If root matches, include all parts
        if term in _normalize(self.root_text):
            if self.part_texts:
                matched.update(self.part_texts.keys())
        
        return matched
    
    def matches_exact(self, pattern) -> Set[str]:
        """
        Find parts matching regex pattern (word boundary match).
        
        Args:
            pattern: Compiled regex pattern with word boundaries
            
        Returns:
            Set of matching part labels
        """
        matched = set()
        
        # Check part texts
        for label, text in self.part_texts.items():
            if pattern.search(text):
                matched.add(label)
        
        # If root matches, include all parts
        if pattern.search(self.root_text):
            if self.part_texts:
                matched.update(self.part_texts.keys())
        
        return matched


@dataclass
class KeywordSearchResult:
    """
    Result of keyword search across all questions.
    
    Aggregates matches from multiple keywords across multiple questions.
    
    Attributes:
        keyword_hits: Maps keyword -> set of matching question IDs
        keyword_label_hits: Maps keyword -> (question_id -> matching part labels)
        aggregate_labels: Maps question_id -> all matching part labels (combined)
        
    Example:
        >>> result.keyword_hits["binary"]
        {'q1', 'q3'}
        >>> result.keyword_label_hits["binary"]["q1"]
        {'1(a)', '1(b)(i)'}
        >>> result.aggregate_labels["q1"]
        {'1(a)', '1(b)(i)', '1(c)'}  # combined from all keywords
    """
    keyword_hits: Dict[str, Set[str]] = field(default_factory=dict)
    keyword_label_hits: Dict[str, Dict[str, Set[str]]] = field(default_factory=dict)
    aggregate_labels: Dict[str, Set[str]] = field(default_factory=dict)
    
    @property
    def question_ids(self) -> FrozenSet[str]:
        """Get all matching question IDs (union across all keywords)."""
        return frozenset(self.aggregate_labels.keys())
    
    @property
    def is_empty(self) -> bool:
        """Check if no matches were found."""
        return len(self.aggregate_labels) == 0
    
    @property
    def total_questions(self) -> int:
        """Get count of matching questions."""
        return len(self.aggregate_labels)
    
    def labels_for_question(self, question_id: str) -> Set[str]:
        """Get all matching labels for a question."""
        return self.aggregate_labels.get(question_id, set())


def _normalize(text: str) -> str:
    """Normalize text for loose matching: lowercase, remove spaces."""
    return text.lower().replace(" ", "")
