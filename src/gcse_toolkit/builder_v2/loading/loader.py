"""
Module: builder_v2.loading.loader

Purpose:
    Load questions from the V2 extraction cache with full validation.
    Reconstructs Question objects from composite.png, regions.json,
    and metadata.json files.

Key Functions:
    - load_questions(): Load all questions for an exam code
    - load_single_question(): Load single question from directory
    - discover_questions(): Find question directories in cache

Key Classes:
    - LoaderError: Exception for loading failures

Dependencies:
    - pathlib (std)
    - gcse_toolkit.core.models: Question, Part
    - builder_v2.loading.parser: JSON parsing
    - builder_v2.loading.reconstructor: Part tree building

Used By:
    - builder_v2.controller: Main build controller
    - builder_v2 integration tests
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gcse_toolkit.core.models import Question, Part

from .parser import parse_metadata, parse_metadata_from_dict, parse_regions, ParsedMetadata, ParseError
from .reconstructor import reconstruct_part_tree, ValidationError


logger = logging.getLogger(__name__)


def _apply_child_topics(part: Part, child_topics: Dict[str, str]) -> Part:
    """
    Recursively apply child_topics to Part tree.
    
    Since Part is frozen, reconstructs tree with topic assignments.
    
    Args:
        part: Root part to update
        child_topics: Mapping of part labels to topics
        
    Returns:
        New Part tree with topics applied
    """
    from dataclasses import replace
    
    # Apply to children first (bottom-up)
    updated_children = tuple(
        _apply_child_topics(child, child_topics)
        for child in part.children
    )
    
    # Get topic for this part from child_topics mapping
    topic = child_topics.get(part.label, part.topic)
    
    return replace(part, topic=topic, children=updated_children)


class LoaderError(Exception):
    """Error loading questions from cache."""
    pass


def load_questions(
    cache_path: Path,
    exam_code: str,
    *,
    topics: Optional[List[str]] = None,
    years: Optional[List[int]] = None,
    papers: Optional[List[int]] = None,
) -> List[Question]:
    """
    Load all questions for an exam code from the cache.
    
    Process:
    1. Read centralized questions.jsonl for metadata
    2. For each question:
       a. Parse metadata from JSONL record
       b. Load and validate regions.json
       c. Reconstruct Part tree
       d. Create Question object
    3. Filter by topics/years/papers if specified
    4. Return sorted by question ID
    
    Args:
        cache_path: Path to slices cache root
        exam_code: Exam code like "0478"
        topics: Optional list of topics to filter by
        years: Optional list of years to filter by
        papers: Optional list of paper numbers to filter by
        
    Returns:
        List of Question objects, sorted by ID
        
    Raises:
        LoaderError: If cache doesn't exist or no questions found
        
    Example:
        >>> questions = load_questions(Path("/cache"), "0478")
        >>> len(questions)
        45
    """
    if not cache_path.exists():
        raise LoaderError(f"Cache path does not exist: {cache_path}")
    
    # Discover questions WITH their metadata from centralized JSONL
    question_entries = discover_questions_with_metadata(cache_path, exam_code)
    
    if not question_entries:
        logger.warning(f"No questions found for {exam_code} in {cache_path}")
        return []
    
    # Load each question, passing pre-parsed metadata
    questions = []
    for question_dir, metadata_dict in question_entries:
        try:
            question = load_single_question(question_dir, metadata_dict=metadata_dict)
            questions.append(question)
        except (ParseError, ValidationError, LoaderError, ValueError) as e:
            logger.warning(f"Failed to load {question_dir.name}: {e}")
            continue
    
    # Apply filters
    if topics:
        topics_set = set(topics)
        questions = [q for q in questions if q.topic in topics_set]
    
    if years:
        years_set = set(years)
        questions = [q for q in questions if q.year in years_set]
    
    if papers:
        papers_set = set(papers)
        questions = [q for q in questions if q.paper in papers_set]
    
    # Sort by ID
    questions.sort(key=lambda q: q.id)
    
    logger.info(f"Loaded {len(questions)} questions for {exam_code}")
    return questions


def load_single_question(
    question_dir: Path,
    *,
    metadata_dict: Optional[Dict[str, Any]] = None,
) -> Question:
    """
    Load a single question from its directory.
    
    Expects directory to contain:
    - composite.png: Question composite image
    - regions.json: Part bounds and metadata
    
    Metadata can be provided from centralized JSONL (preferred) or
    read from per-question metadata.json (legacy fallback).
    
    Args:
        question_dir: Path to question directory
        metadata_dict: Pre-parsed metadata dict from JSONL (optional)
        
    Returns:
        Question object with reconstructed Part tree
        
    Raises:
        LoaderError: If required files missing
        ParseError: If JSON parsing fails
        ValidationError: If tree reconstruction fails
        
    Example:
        >>> q = load_single_question(Path("cache/0478_m24_qp_12_q1"))
        >>> q.total_marks
        8
    """
    # Validate directory structure
    composite_path = question_dir / "composite.png"
    regions_path = question_dir / "regions.json"
    
    if not composite_path.exists():
        raise LoaderError(f"Missing composite.png in {question_dir}")
    if not regions_path.exists():
        raise LoaderError(f"Missing regions.json in {question_dir}")
    
    # Parse metadata from JSONL dict or fallback to file
    if metadata_dict is not None:
        metadata = parse_metadata_from_dict(metadata_dict, source=question_dir.name)
    else:
        # Legacy fallback: read from per-question metadata.json
        metadata_path = question_dir / "metadata.json"
        if not metadata_path.exists():
            raise LoaderError(f"Missing metadata.json in {question_dir} (and no JSONL metadata provided)")
        metadata = parse_metadata(metadata_path)

    # Parse regions
    regions = parse_regions(regions_path)
    
    # Reconstruct Part tree
    part_tree = reconstruct_part_tree(regions)
    
    # Apply child_topics to Part tree (schema v9+)
    if metadata.child_topics:
        part_tree = _apply_child_topics(part_tree, metadata.child_topics)
    
    # NOTE: Validation is done at extraction time and stored in is_valid metadata.
    # No need to re-validate on every load.
    
    # Get bbox from regions (schema v2) or fall back to metadata (schema v1)
    numeral_bbox = regions.numeral_bbox or getattr(metadata, 'numeral_bbox', None)
    horizontal_offset = regions.horizontal_offset or getattr(metadata, 'horizontal_offset', 0)
    # content_right removed - bounds are now correct at extraction time
    
    # Create Question object
    return Question(
        id=metadata.question_id,
        exam_code=metadata.exam_code,
        year=metadata.year,
        paper=metadata.paper,
        variant=metadata.variant,
        topic=metadata.topic,
        question_node=part_tree,
        composite_path=composite_path,
        regions_path=regions_path,
        mark_scheme_path=metadata.markscheme_path,
        content_right=None,  # No longer used - bounds are correct
        numeral_bbox=numeral_bbox,
        root_text=metadata.root_text,
        child_text=metadata.child_text,
        horizontal_offset=horizontal_offset,
    )


def discover_questions(cache_path: Path, exam_code: str) -> List[Path]:
    """
    Find question directories by reading centralized metadata file.
    
    Reads from {cache_path}/{exam_code}/_metadata/questions.jsonl to get
    question directory paths. This is fast (single file read) and relies
    on the extractor having created the metadata file.
    
    Args:
        cache_path: Root cache directory
        exam_code: Exam code to search for (e.g., "0478")
        
    Returns:
        List of paths to question directories, sorted by name
        
    Raises:
        LoaderError: If metadata file doesn't exist or is unreadable
        
    Example:
        >>> dirs = discover_questions(Path("/cache"), "0478")
        >>> len(dirs)
        45
    
    Note:
        Requires V2 extractor to have created questions.jsonl.
        Will not work with old V1 caches that lack centralized metadata.
    """
    metadata_path = cache_path / exam_code / "_metadata" / "questions.jsonl"
    
    if not metadata_path.exists():
        raise LoaderError(
            f"Metadata file not found: {metadata_path}. "
            f"Extract questions using V2 extractor first."
        )
    
    return _discover_from_metadata(cache_path, metadata_path)


def _discover_from_metadata(
    cache_path: Path, 
    metadata_path: Path,
    *,
    include_metadata: bool = False,
) -> List[Tuple[Path, Dict[str, Any]]] | List[Path]:
    """
    Load question paths (and optionally metadata) from centralized questions.jsonl file.
    
    Reads JSONL file where each line contains a metadata record with
    a 'relative_path' field pointing to the question directory.
    
    Args:
        cache_path: Root cache directory
        metadata_path: Path to questions.jsonl file
        include_metadata: If True, return (path, record) tuples; else just paths
        
    Returns:
        List of VALID question entries (paths or tuples), sorted by name
        
    Note:
        Skips records with missing directories or invalid JSON.
        Validates that regions.json exists in each directory.
        Filters out questions marked as invalid (is_valid=False).
    """
    entries: List[Tuple[Path, Dict[str, Any]]] = []
    invalid_count = 0
    
    with metadata_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            
            try:
                record = json.loads(line)
                rel_path = record.get("relative_path")
                
                if not rel_path:
                    logger.warning(f"Record at line {line_num} missing 'relative_path'")
                    continue
                
                # FILTER: Skip invalid questions
                # is_valid field is optional for backward compatibility with schema v7
                is_valid = record.get("is_valid", True)  # Default to True for old extractions
                if not is_valid:
                    invalid_count += 1
                    logger.debug(f"Skipping invalid question: {rel_path}")
                    continue
                
                question_dir = cache_path / rel_path
                
                # Verify directory and regions.json exist
                if question_dir.exists() and (question_dir / "regions.json").exists():
                    entries.append((question_dir, record))
                else:
                    logger.debug(f"Skipping missing directory: {question_dir}")
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON at line {line_num}: {e}")
                continue
    
    entries.sort(key=lambda e: e[0].name)
    logger.debug(
        f"Discovered {len(entries)} valid questions from metadata "
        f"({invalid_count} invalid questions filtered out)"
    )
    
    if include_metadata:
        return entries
    else:
        return [path for path, _ in entries]


def discover_questions_with_metadata(
    cache_path: Path, 
    exam_code: str,
) -> List[Tuple[Path, Dict[str, Any]]]:
    """
    Find question directories WITH their metadata from centralized JSONL.
    
    Returns tuples of (question_dir, metadata_dict) so that metadata
    doesn't need to be re-read from per-question files.
    
    This is the preferred discovery method for loading questions.
    
    Args:
        cache_path: Root cache directory
        exam_code: Exam code to search for (e.g., "0478")
        
    Returns:
        List of (path, metadata_dict) tuples, sorted by name
        
    Raises:
        LoaderError: If metadata file doesn't exist or is unreadable
    """
    metadata_path = cache_path / exam_code / "_metadata" / "questions.jsonl"
    
    if not metadata_path.exists():
        logger.debug(f"Metadata file not found: {metadata_path}")
        return []
    
    return _discover_from_metadata(cache_path, metadata_path, include_metadata=True)
