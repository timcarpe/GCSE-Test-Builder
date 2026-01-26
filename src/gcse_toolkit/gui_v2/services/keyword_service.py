"""
Keyword search service for GUI.

Manages question loading, caching, and V2 keyword index lifecycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from gcse_toolkit.builder_v2 import load_questions
from gcse_toolkit.builder_v2.keyword import KeywordIndex, KeywordSearchResult
from gcse_toolkit.core.models.questions import Question

logger = logging.getLogger(__name__)


@dataclass
class EnrichedKeywordResult(KeywordSearchResult):
    """
    Keyword search result enriched with Question objects.
    
    Extends V2 KeywordSearchResult with GUI-needed data.
    
    Attributes:
        keyword_hits: Per-keyword question ID sets (from parent)
        keyword_label_hits: Per-keyword part label mappings (from parent)
        aggregate_labels: Combined part labels per question (from parent)
        questions: Question objects for matched questions (NEW)
    """
    questions: Dict[str, Question] = field(default_factory=dict)


class KeywordSearchService:
    """
    Stateful keyword search service for GUI.
    
    Manages:
    - Question loading and caching per exam
    - V2 KeywordIndex lifecycle
    - Result enrichment with Question objects
    
    Example:
        >>> service = KeywordSearchService(cache_path)
        >>> result = service.search("0478", ["binary", "validation"])
        >>> result.questions  # Dict[str, Question]
        {'0478_m24_qp_12_q1': Question(...), ...}
    """
    
    def __init__(self, cache_path: Path):
        """
        Initialize service.
        
        Args:
            cache_path: Path to slices cache root
        """
        self.cache_path = cache_path
        
        # Per-exam caches
        self._questions_cache: Dict[str, List[Question]] = {}
        self._index_cache: Dict[str, KeywordIndex] = {}
    
    def search(
        self,
        exam_code: str,
        keywords: List[str],
    ) -> EnrichedKeywordResult:
        """
        Search for questions matching keywords.
        
        Auto-loads questions if not cached.
        
        Args:
            exam_code: Exam code (e.g., "0478")
            keywords: List of keywords to search
            
        Returns:
            EnrichedKeywordResult with Question objects
            
        Example:
            >>> result = service.search("0478", ["binary"])
            >>> len(result.questions)
            5
            >>> result.keyword_hits["binary"]
            {'0478_m24_qp_12_q1', '0478_m24_qp_12_q3'}
        """
        # Ensure questions loaded and indexed
        self._ensure_exam_loaded(exam_code)
        
        # Get cached index
        index = self._index_cache[exam_code]
        questions_list = self._questions_cache[exam_code]
        
        # Search using V2
        result = index.search(keywords)
        
        # Enrich with Question objects
        questions_map = {q.id: q for q in questions_list}
        matched_questions = {
            qid: questions_map[qid]
            for qid in result.question_ids
            if qid in questions_map
        }
        
        logger.debug(f"Keyword search for {exam_code}: {len(matched_questions)} matches")
        
        return EnrichedKeywordResult(
            keyword_hits=result.keyword_hits,
            keyword_label_hits=result.keyword_label_hits,
            aggregate_labels=result.aggregate_labels,
            questions=matched_questions,
        )
    
    def _ensure_exam_loaded(self, exam_code: str) -> None:
        """
        Load and cache questions for exam if not already loaded.
        
        Args:
            exam_code: Exam code to load
            
        Raises:
            ValueError: If no questions found for exam
        """
        if exam_code in self._questions_cache:
            return  # Already loaded
        
        logger.info(f"Loading questions for {exam_code}...")
        
        # Load using V2 loader
        questions = load_questions(
            cache_path=self.cache_path,
            exam_code=exam_code,
        )
        
        if not questions:
            raise ValueError(f"No questions found for {exam_code}")
        
        # Create and prime index
        index = KeywordIndex()
        index.prime(questions)
        
        # Cache
        self._questions_cache[exam_code] = questions
        self._index_cache[exam_code] = index
        
        logger.info(f"Cached {len(questions)} questions for {exam_code}")
    
    def clear_cache(self, exam_code: Optional[str] = None) -> None:
        """
        Clear cached data.
        
        Args:
            exam_code: Clear specific exam, or all if None
        """
        if exam_code:
            self._questions_cache.pop(exam_code, None)
            self._index_cache.pop(exam_code, None)
            logger.debug(f"Cleared cache for {exam_code}")
        else:
            self._questions_cache.clear()
            self._index_cache.clear()
            logger.debug("Cleared all caches")
