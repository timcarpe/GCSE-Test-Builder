"""
Module: common.topics

Purpose:
    Helpers for working with GCSE topic/sub-topic mappings. Provides
    functions to normalize, resolve, and classify topics and sub-topics
    using the exam plugin's subtopics configuration.

Key Functions:
    - resolve_topic_label(): Normalize and resolve a topic label to canonical form
    - canonical_sub_topic_label(): Get canonical sub-topic name
    - topic_sub_topics(): Get all sub-topics for each topic
    - classify_sub_topics(): Classify text into sub-topics by pattern matching
    - topic_patterns_from_subtopics(): Get regex patterns for topic matching

Dependencies:
    - gcse_toolkit.plugins: Plugin registry for subtopics path resolution

Used By:
    - gcse_toolkit.gui_v2.widgets.build_tab: Topic selection and canonicalization
    - gcse_toolkit.gui_v2.widgets.topic_selector: Topic display
    - gcse_toolkit.builder_v2: Topic filtering during selection
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Set, Tuple

from gcse_toolkit.plugins import MissingResourcesError, resolve_subtopics_path


__all__ = [
    "normalise_topic_label",
    "normalise_sub_topic",
    "resolve_topic_label",
    "canonical_sub_topic_label",
    "topic_sub_topics",
    "classify_sub_topics",
    "topic_patterns_from_subtopics",
    "sub_topic_parents",
    "iter_all_sub_topics",
    "FALLBACK_SUB_TOPIC",
]


_TOPIC_PREFIX_RE = re.compile(r"^\s*(\d+)[\.)\]]\s*(.*)$")
_TOPIC_SLUG_RE = re.compile(r"^\s*\d+[\.)\]]\s*")
FALLBACK_SUB_TOPIC = "Subtopic not found"


def normalise_topic_label(value: Optional[str]) -> str:
    """
    Normalize a topic label to standard format "NN. Topic Name".
    
    Args:
        value: Raw topic label (e.g., "1. Data", "01) Data", "1 Data").
        
    Returns:
        Normalized topic label with zero-padded number and period
        (e.g., "01. Data"). Returns "00. Unknown" if value is empty.
        
    Example:
        >>> normalise_topic_label("1. Data representation")
        '01. Data representation'
        >>> normalise_topic_label(None)
        '00. Unknown'
    """
    if not value:
        return "00. Unknown"
    match = _TOPIC_PREFIX_RE.match(value)
    if not match:
        return value.strip()
    number = int(match.group(1))
    remainder = match.group(2).strip()
    if remainder:
        return f"{number:02d}. {remainder}"
    return f"{number:02d}."


def normalise_sub_topic(value: Optional[str]) -> str:
    """
    Normalize a sub-topic name for comparison.
    
    Args:
        value: Raw sub-topic name.
        
    Returns:
        Lowercase, stripped sub-topic name. Empty string if None.
    """
    if not value:
        return ""
    return value.strip().lower()


@lru_cache(maxsize=None)
def _raw_mapping(exam_code: Optional[str]) -> Dict[str, Dict[str, object]]:
    """Load raw subtopics mapping from plugin configuration."""
    try:
        path = resolve_subtopics_path(exam_code)
    except MissingResourcesError:
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload


@lru_cache(maxsize=None)
def _compiled_mapping(exam_code: Optional[str]) -> Dict[str, List[Tuple[str, List[re.Pattern]]]]:
    """Compile regex patterns from subtopics configuration."""
    compiled: Dict[str, List[Tuple[str, List[re.Pattern]]]] = {}
    for topic, payload in _raw_mapping(exam_code).items():
        norm_topic = normalise_topic_label(topic)
        entries: List[Tuple[str, List[re.Pattern]]] = []
        for item in payload.get("sub_topics", []):  # type: ignore[assignment]
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            patterns: List[re.Pattern] = []
            for pattern in item.get("patterns", []):  # type: ignore[assignment]
                try:
                    patterns.append(re.compile(str(pattern), re.IGNORECASE))
                except re.error:
                    continue
            entries.append((name, patterns))
        compiled[norm_topic] = entries
    return compiled


@lru_cache(maxsize=None)
def topic_patterns_from_subtopics(exam_code: Optional[str]) -> Dict[str, List]:
    """
    Aggregate topic-level regex patterns from both top-level and sub-topic patterns.
    
    Args:
        exam_code: Exam code to load patterns for.
        
    Returns:
        Dict mapping normalized topic labels to lists of pattern objects.
        Pattern objects can be strings (legacy) or dicts with 'pattern' and 'weight' keys.
    """
    aggregated: Dict[str, List] = {}
    
    # 1. Extract from Direct Top-Level Patterns (v3 style with weights)
    raw = _raw_mapping(exam_code)
    for topic, payload in raw.items():
        norm_topic = normalise_topic_label(topic)
        # Ensure payload is a dict
        if isinstance(payload, dict):
            top_pats = payload.get("patterns", [])
            if top_pats:
                # Pass patterns through as-is (dicts or strings)
                # classification._compile_patterns_with_weights handles both
                aggregated.setdefault(norm_topic, []).extend(top_pats)

    # 2. Extract from Sub-topics (legacy / v2 style)
    for topic, entries in _compiled_mapping(exam_code).items():
        for _name, compiled_list in entries:
            if compiled_list:
                aggregated.setdefault(topic, []).extend(p.pattern for p in compiled_list)
                
    # Dedupe patterns - need to handle both strings and dicts
    final_output = {}
    for topic, pats in aggregated.items():
        if pats:
            seen = set()
            unique_pats = []
            for p in pats:
                # For deduplication, extract the pattern string
                pat_key = p.get("pattern") if isinstance(p, dict) else p
                if pat_key not in seen:
                    seen.add(pat_key)
                    unique_pats.append(p)
            final_output[topic] = unique_pats
            
    return final_output


def _topic_slug(value: str) -> str:
    """Extract slug (lowercase name without number prefix) from topic label."""
    cleaned = _TOPIC_SLUG_RE.sub("", value).strip().lower()
    return re.sub(r"\s+", " ", cleaned)


@lru_cache(maxsize=None)
def _topic_slug_index(exam_code: Optional[str]) -> Dict[str, str]:
    """Build index mapping topic slugs to canonical topic labels."""
    mapping: Dict[str, str] = {}
    for topic in _compiled_mapping(exam_code).keys():
        slug = _topic_slug(topic)
        mapping.setdefault(slug, topic)
    return mapping


def resolve_topic_label(value: Optional[str], exam_code: Optional[str] = None) -> str:
    """
    Resolve a topic label to its canonical form.
    
    First normalizes the label, then looks up the canonical version
    in the exam's subtopics configuration.
    
    Args:
        value: Topic label to resolve.
        exam_code: Exam code for context.
        
    Returns:
        Canonical topic label if found, otherwise normalized input.
        
    Example:
        >>> resolve_topic_label("1 Data representation", "0478")
        '01. Data representation'
    """
    if not value:
        return normalise_topic_label(value)
    candidate = normalise_topic_label(value)
    if candidate in _compiled_mapping(exam_code):
        return candidate
    slug = _topic_slug(candidate)
    return _topic_slug_index(exam_code).get(slug, candidate)


@lru_cache(maxsize=None)
def _sub_topic_index(exam_code: Optional[str]) -> Dict[str, Set[str]]:
    """Build index mapping sub-topic names to parent topic labels."""
    index: Dict[str, Set[str]] = {}
    for topic, entries in _compiled_mapping(exam_code).items():
        for name, _patterns in entries:
            index.setdefault(normalise_sub_topic(name), set()).add(topic)
        index.setdefault(normalise_sub_topic(FALLBACK_SUB_TOPIC), set()).add(topic)
    return index


def classify_sub_topics(
    main_topic: str,
    *texts: str,
    exam_code: Optional[str] = None,
) -> List[str]:
    """
    Classify text content into sub-topics by pattern matching.
    
    Args:
        main_topic: Parent topic label.
        *texts: Text content to classify.
        exam_code: Exam code for pattern lookup.
        
    Returns:
        List of matching sub-topic names. Returns [FALLBACK_SUB_TOPIC]
        if no patterns match.
    """
    norm_topic = resolve_topic_label(main_topic, exam_code)
    entries = _compiled_mapping(exam_code).get(norm_topic, [])
    combined_text = " ".join(t for t in texts if t).strip()
    matches: List[str] = []
    if combined_text and entries:
        for name, patterns in entries:
            if any(pattern.search(combined_text) for pattern in patterns):
                if name not in matches:
                    matches.append(name)
    if not matches:
        matches.append(FALLBACK_SUB_TOPIC)
    return matches


def canonical_sub_topic_label(
    main_topic: Optional[str],
    label: Optional[str],
    exam_code: Optional[str] = None,
) -> Optional[str]:
    """
    Get the canonical form of a sub-topic label.
    
    Args:
        main_topic: Parent topic label for context.
        label: Sub-topic label to canonicalize.
        exam_code: Exam code for lookup.
        
    Returns:
        Canonical sub-topic name if found in schema, otherwise
        FALLBACK_SUB_TOPIC. Returns None if label is empty.
    """
    if not label:
        return None
    cleaned = str(label).strip()
    if not cleaned:
        return None
    topic = resolve_topic_label(main_topic, exam_code) if main_topic else None
    if topic:
        canonical_entries = _compiled_mapping(exam_code).get(topic, [])
        for name, _patterns in canonical_entries:
            if cleaned.lower() == name.lower():
                return name
    if cleaned.lower() == FALLBACK_SUB_TOPIC.lower():
        return FALLBACK_SUB_TOPIC
    
    # STRICT VALIDATION: If the name isn't in the schema, treat it as unknown.
    return FALLBACK_SUB_TOPIC


def topic_sub_topics(exam_code: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Get all sub-topics for each topic.
    
    Args:
        exam_code: Exam code to load sub-topics for.
        
    Returns:
        Dict mapping topic labels to lists of sub-topic names.
        Each list includes FALLBACK_SUB_TOPIC if not already present.
        
    Example:
        >>> subs = topic_sub_topics("0478")
        >>> subs["01. Data representation"]
        ['Binary systems', 'Hexadecimal', ..., 'Subtopic not found']
    """
    mapping: Dict[str, List[str]] = {}
    for topic, entries in _compiled_mapping(exam_code).items():
        names = [name for name, _patterns in entries]
        if not any(name.lower() == FALLBACK_SUB_TOPIC.lower() for name in names):
            names.append(FALLBACK_SUB_TOPIC)
        mapping[topic] = names
    return mapping


def sub_topic_parents(sub_topic: str, exam_code: Optional[str] = None) -> Set[str]:
    """
    Get all topics that contain a given sub-topic.
    
    Args:
        sub_topic: Sub-topic name to look up.
        exam_code: Exam code for context.
        
    Returns:
        Set of topic labels that contain this sub-topic.
    """
    lookup = normalise_sub_topic(sub_topic)
    parents = _sub_topic_index(exam_code).get(lookup)
    if not parents:
        return set()
    return parents.copy()


def iter_all_sub_topics(exam_code: Optional[str] = None) -> Iterable[Tuple[str, str]]:
    """
    Iterate over all (topic, sub_topic) pairs.
    
    Args:
        exam_code: Exam code to load sub-topics for.
        
    Yields:
        Tuples of (topic_label, sub_topic_name).
    """
    for topic, names in topic_sub_topics(exam_code).items():
        for name in names:
            yield topic, name
