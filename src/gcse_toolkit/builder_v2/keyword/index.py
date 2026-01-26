"""
Module: builder_v2.keyword.index

Purpose:
    In-memory keyword index for searching question text.
    Supports exact (word-boundary) and fuzzy (substring) matching.

Key Classes:
    - KeywordIndex: Main index class with search method

Dependencies:
    - re: Regex for exact matching
    - concurrent.futures: Parallel search
    - gcse_toolkit.core.models.questions: Question model

Used By:
    - builder_v2.controller: Keyword filtering pipeline
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Dict, List, Optional, Set

from gcse_toolkit.core.models.questions import Question

from .models import KeywordEntry, KeywordSearchResult, _normalize

logger = logging.getLogger(__name__)


class KeywordIndex:
    """
    In-memory keyword index built from Question objects.
    
    Builds a searchable index of question text for fast keyword lookup.
    Thread-safe for concurrent searches.
    
    Example:
        >>> index = KeywordIndex()
        >>> index.prime(questions)
        >>> result = index.search(["binary", "stack"])
        >>> result.question_ids
        frozenset({'0478_m24_qp_12_q3', '0478_m24_qp_12_q5'})
    """
    
    def __init__(self) -> None:
        """Initialize empty keyword index."""
        self._entries: Dict[str, KeywordEntry] = {}
        self._lock = Lock()
    
    def prime(self, questions: List[Question]) -> None:
        """
        Populate index from questions.
        
        Builds text blobs from question and part text for searching.
        Clears any existing entries first.
        
        Args:
            questions: List of Question objects to index
        """
        with self._lock:
            self._entries.clear()
            for question in questions:
                entry = self._build_entry(question)
                self._entries[question.id] = entry
            logger.info(f"Indexed {len(self._entries)} questions for keyword search")
    
    def search(
        self,
        keywords: List[str],
    ) -> KeywordSearchResult:
        """
        Search for questions matching keywords.
        
        Supports two matching modes:
        - Exact: Wrap keyword in quotes ("binary") for word-boundary matching
        - Fuzzy: Plain keyword (binary) for substring matching
        
        Args:
            keywords: List of terms to search for
                   
        Returns:
            KeywordSearchResult with matching question IDs and part labels
            
        Example:
            >>> result = index.search(["binary", '"stack"'])
            >>> # "binary" matches "binary123", '"stack"' only matches whole word
        """
        clean_keywords = [kw.strip() for kw in keywords if kw and kw.strip()]
        if not clean_keywords:
            return KeywordSearchResult()
        
        # Parse keywords into (original, term, is_exact) tuples
        keyword_tuples = []
        for kw in clean_keywords:
            raw = kw.strip()
            if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
                # Exact match: strip quotes
                keyword_tuples.append((kw, raw[1:-1], True))
            else:
                # Fuzzy match: normalize
                keyword_tuples.append((kw, _normalize(raw), False))
        
        # Search each keyword (parallel for multiple keywords)
        keyword_hits: Dict[str, Set[str]] = {}
        keyword_label_hits: Dict[str, Dict[str, Set[str]]] = {}
        aggregate_labels: Dict[str, Set[str]] = {}
        
        with self._lock:
            entries = dict(self._entries)
        
        if len(keyword_tuples) > 1:
            with ThreadPoolExecutor(max_workers=min(4, len(keyword_tuples))) as pool:
                future_map = {
                    pool.submit(self._match_keyword, term, is_exact, entries): kw_orig
                    for kw_orig, term, is_exact in keyword_tuples
                }
                for future in future_map:
                    kw_orig = future_map[future]
                    per_keyword = future.result()
                    self._aggregate_results(
                        kw_orig, per_keyword,
                        keyword_hits, keyword_label_hits, aggregate_labels
                    )
        else:
            # Single keyword - no thread overhead
            kw_orig, term, is_exact = keyword_tuples[0]
            per_keyword = self._match_keyword(term, is_exact, entries)
            self._aggregate_results(
                kw_orig, per_keyword,
                keyword_hits, keyword_label_hits, aggregate_labels
            )
        
        return KeywordSearchResult(
            keyword_hits=keyword_hits,
            keyword_label_hits=keyword_label_hits,
            aggregate_labels=aggregate_labels,
        )
    
    def _aggregate_results(
        self,
        keyword: str,
        per_keyword: Dict[str, Set[str]],
        keyword_hits: Dict[str, Set[str]],
        keyword_label_hits: Dict[str, Dict[str, Set[str]]],
        aggregate_labels: Dict[str, Set[str]],
    ) -> None:
        """Aggregate results from a single keyword search."""
        keyword_label_hits[keyword] = per_keyword
        keyword_hits[keyword] = set(per_keyword.keys())
        for qid, labels in per_keyword.items():
            aggregate_labels.setdefault(qid, set()).update(labels)
    
    def _build_entry(self, question: Question) -> KeywordEntry:
        """
        Build searchable entry for a question.
        
        Extracts text from question root and all parts.
        """
        # Get root text (question header text)
        root_text = getattr(question, 'root_text', '') or ''
        
        # Get part texts
        part_texts: Dict[str, str] = {}
        child_text = getattr(question, 'child_text', {}) or {}
        
        if child_text:
            part_texts = dict(child_text)
        
        # Also try to get text from parts themselves
        if hasattr(question, 'question_node'):
            for part in question.question_node.iter_all():
                label = part.label
                if label and label not in part_texts:
                    # Try to get any text associated with the part
                    part_text = child_text.get(label, '')
                    if part_text:
                        part_texts[label] = part_text
        
        return KeywordEntry(
            question_id=question.id,
            root_text=root_text,
            part_texts=part_texts,
        )
    
    def _match_keyword(
        self,
        term: str,
        is_exact: bool,
        entries: Dict[str, KeywordEntry],
    ) -> Dict[str, Set[str]]:
        """
        Find questions/parts matching a keyword.
        
        Args:
            term: Search term (normalized for fuzzy, original for exact)
            is_exact: Whether to use word-boundary matching
            entries: Dict of entries to search
            
        Returns:
            Dict mapping question_id -> set of matching part labels
        """
        matches: Dict[str, Set[str]] = {}
        
        # Compile regex for exact match
        pattern = None
        if is_exact:
            pattern = re.compile(fr"\b{re.escape(term)}\b", re.IGNORECASE)
        
        for qid, entry in entries.items():
            if is_exact and pattern:
                matched = entry.matches_exact(pattern)
            else:
                matched = entry.matches_substring(term)
            
            if matched:
                matches[qid] = matched
        
        return matches
    
    @property
    def question_count(self) -> int:
        """Get number of indexed questions."""
        return len(self._entries)
