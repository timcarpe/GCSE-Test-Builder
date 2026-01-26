"""
Module: extractor_v2.classification

Purpose:
    Topic classification for extracted questions using regex patterns
    and optional ML model. Ported from extractor/v2/classification.py.

Key Functions:
    - classify_topic(): Main entry point for topic classification
    - best_topic(): Regex-based weighted pattern matching
    - apply_topic_consensus(): Infer topic from part majority voting

Dependencies:
    - gcse_toolkit.common.topics: Pattern loading
    - gcse_toolkit.plugins: Exam stats and model loading
"""

from __future__ import annotations

import logging
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from gcse_toolkit.core.models.parts import Part

logger = logging.getLogger(__name__)

# Fallback topic when classification fails
UNKNOWN_TOPIC = "00. Unknown"


def _is_unknown(topic: Optional[str]) -> bool:
    """Check if a topic is Unknown or unclassified."""
    if not topic:
        return True
    return topic.lower() in ("unknown", "00. unknown", "")


def propagate_topics(
    part_topics: Dict[str, str],
    part_tree: Part,
) -> Dict[str, str]:
    """
    Propagate topics through part hierarchy to fill Unknown gaps.
    
    Rules:
    1. Context roots inherit from first classified child (propagate up)
    2. Unknown siblings adopt topic if before and after share same topic
    3. Final fallback: most prominent topic from all parts
    
    Args:
        part_topics: Dict mapping part label to classified topic
        part_tree: The Part tree structure
        
    Returns:
        Updated part_topics with Unknown gaps filled where possible
        
    Example:
        >>> # (i) is "Arrays", but 6 and (a) are Unknown
        >>> propagate_topics({"6": "Unknown", "(a)": "Unknown", "(i)": "Arrays"}, tree)
        {"6": "Arrays", "(a)": "Arrays", "(i)": "Arrays"}
    """
    result = dict(part_topics)  # Copy to avoid mutation
    
    # Pass 1: Propagate from children to Unknown parents
    def propagate_up(part: Part) -> Optional[str]:
        """Return first classified topic from this branch, propagating to Unknown parents."""
        label = part.label
        current = result.get(label)
        
        if part.children:
            # Get topics from children first
            child_topics = []
            for child in part.children:
                child_topic = propagate_up(child)
                if child_topic:
                    child_topics.append(child_topic)
            
            # If this part is Unknown but has classified children, adopt first child's topic
            if _is_unknown(current) and child_topics:
                result[label] = child_topics[0]
                return child_topics[0]
        
        return current if not _is_unknown(current) else None
    
    propagate_up(part_tree)
    
    # Pass 2: Fill Unknown siblings from adjacent classified siblings
    def propagate_siblings(part: Part) -> None:
        """Fill Unknown siblings when neighbors share the same topic."""
        if not part.children or len(part.children) < 2:
            return
        
        children = list(part.children)
        
        for i, child in enumerate(children):
            label = child.label
            current = result.get(label)
            
            if _is_unknown(current):
                # Check if before and after siblings share the same topic
                before = result.get(children[i-1].label) if i > 0 else None
                after = result.get(children[i+1].label) if i < len(children) - 1 else None
                
                if before and after and before == after and not _is_unknown(before):
                    result[label] = before
        
        # Recurse into children
        for child in part.children:
            propagate_siblings(child)
    
    propagate_siblings(part_tree)
    
    return result


def get_consensus_topic(part_topics: Dict[str, str]) -> str:
    """
    Get the most prominent topic from all classified parts.
    
    Falls back to this when propagation doesn't fill the root topic.
    
    Args:
        part_topics: Dict mapping part label to topic
        
    Returns:
        Most frequent non-Unknown topic, or UNKNOWN_TOPIC if none
    """
    topic_counts: Dict[str, int] = {}
    
    for topic in part_topics.values():
        if not _is_unknown(topic):
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    
    if not topic_counts:
        return UNKNOWN_TOPIC
    
    # Return topic with highest count
    return max(topic_counts.items(), key=lambda x: x[1])[0]


def apply_topic_consensus(
    part_topics: Dict[str, str],
    part_tree: Part,
    root_label: str,
) -> str:
    """
    Apply full consensus logic to determine root topic.
    
    Pipeline:
    1. Propagate topics up from classified children to Unknown parents
    2. Fill Unknown siblings from matching neighbors
    3. If root still Unknown, use most prominent topic
    
    Args:
        part_topics: Dict mapping part label to classified topic
        part_tree: The Part tree structure
        root_label: Label of the root part (e.g., "6")
        
    Returns:
        Final topic for the root, with propagation and consensus applied
        
    Example:
        >>> # Only (i) is classified, parents are Unknown
        >>> apply_topic_consensus({"6": "Unknown", "(a)": "Unknown", "(i)": "Arrays"}, tree, "6")
        'Arrays'
    """
    # Propagate topics through tree
    propagated = propagate_topics(part_topics, part_tree)
    
    # Check if root now has a topic
    root_topic = propagated.get(root_label)
    
    if not _is_unknown(root_topic):
        return root_topic
    
    # Fallback: most prominent topic from all parts
    return get_consensus_topic(propagated)


def classify_all_parts(
    part_tree: Part,
    part_texts: Dict[str, str],
    exam_code: str,
    paper: int = 1,
) -> Dict[str, str]:
    """
    Classify topic for each part in the tree.
    
    Args:
        part_tree: The Part tree structure
        part_texts: Dict mapping part label to text content
        exam_code: Exam code for pattern lookup
        paper: Paper number for paper-specific patterns
        
    Returns:
        Dict mapping part label to classified topic
    """
    result: Dict[str, str] = {}
    
    def classify_part(part: Part) -> None:
        label = part.label
        text = part_texts.get(label, "")
        
        if text.strip():
            topic = classify_topic(text, exam_code, paper)
        else:
            topic = UNKNOWN_TOPIC
        
        result[label] = topic
        
        for child in part.children:
            classify_part(child)
    
    classify_part(part_tree)
    return result


def classify_topic(
    text: str,
    exam_code: str,
    paper: int = 1,
    require_confidence: bool = True,
) -> str:
    """
    Classify question text into a curriculum topic.
    
    Strategy:
    1. Try ML model if available (higher accuracy)
    2. Fallback to regex pattern matching
    3. Return Unknown if no confident match
    
    Args:
        text: Question text to classify
        exam_code: Exam code (e.g., "0478")
        paper: Paper number for paper-specific patterns
        require_confidence: If True, return Unknown on low confidence
        
    Returns:
        Topic label string (e.g., "01. Data representation")
        
    Example:
        >>> classify_topic("Convert 13 to binary", "0478")
        '01. Data representation'
    """
    if not text or not text.strip():
        return UNKNOWN_TOPIC
    
    # Load patterns for this exam
    patterns = _get_topic_patterns(exam_code, paper)
    if not patterns:
        logger.debug(f"No patterns for {exam_code}, returning Unknown")
        return UNKNOWN_TOPIC
    
    # Load evaluation stats for weighted scoring
    stats = _get_exam_stats(exam_code)
    
    # Try ML model first (if available)
    model = _get_topic_model(exam_code)
    model_probs = None
    if model:
        try:
            # Phase 11: Production parity. Use model.predict which favors optimal_threshold.
            # If require_confidence is False, we pass min_conf=0.0 to get argmax result.
            topic = model.predict(text, min_conf=None if require_confidence else 0.0)
            if topic:
                logger.debug(f"ML model classified as {topic}")
                return topic
            
            # If not returned, get probabilities for regex tiebreaking/insight
            model_probs = model.get_probabilities(text)
        except Exception as e:
            logger.debug(f"ML model failed: {e}")
    
    # Fallback to regex classification
    topic = best_topic(
        text, 
        patterns, 
        stats=stats, 
        require_confidence=require_confidence,
        model_probs=model_probs,
    )
    
    if topic:
        logger.debug(f"Regex classified as {topic}")
        return topic
    
    return UNKNOWN_TOPIC


def best_topic(
    sample_text: str,
    patterns: Dict[str, Iterable],
    stats: Optional[Dict[str, Any]] = None,
    require_confidence: bool = True,
    model_probs: Optional[Dict[str, float]] = None,
) -> Optional[str]:
    """
    Infer the most likely curriculum topic using weighted pattern matching.
    
    Args:
        sample_text: The text to classify
        patterns: Dictionary of {topic: [patterns]} where each pattern is either:
                  - A string: "\\bterm\\b" (default weight 1.0)
                  - A dict: {"pattern": "\\bterm\\b", "weight": 1.5}
        stats: Optional evaluation report with pattern precision/tp (legacy)
        require_confidence: If True, returns None if top match is weak
        model_probs: Optional ML model probabilities for tiebreaking
        
    Returns:
        Topic name or None if no confident match
    """
    if not patterns or not sample_text:
        return None

    # Normalize and compile patterns, extracting inline weights
    compiled, inline_weights = _compile_patterns_with_weights(patterns)
    
    # Build pattern weights from stats (legacy support)
    stats_weights = _build_pattern_weights(stats) if stats else {}
    
    scores: Dict[str, float] = {}

    for topic, regexes in compiled.items():
        topic_inline_weights = inline_weights.get(topic, [])
        stats_topic_weights = stats_weights.get(topic) or stats_weights.get(topic.lower()) or {}
        
        topic_score = 0.0
        match_count = 0

        for i, pattern in enumerate(regexes):
            # Priority: inline weight > stats weight > default 1.0
            if i < len(topic_inline_weights) and topic_inline_weights[i] is not None:
                weight = topic_inline_weights[i]
            elif stats_topic_weights:
                # Legacy: look up by pattern string (need original string)
                weight = 0.5  # Default for stats mode
            else:
                weight = 1.0

            if pattern.search(sample_text):
                topic_score += weight
                match_count += 1
        
        if match_count > 0:
            scores[topic] = topic_score

    if not scores:
        return None
        
    # Sort by score descending
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_topic, top_score = sorted_scores[0]
    
    if require_confidence:
        # Minimum score threshold
        if top_score < 0.7:
            return None
            
        # Margin check (separation from 2nd best)
        if len(sorted_scores) > 1:
            second_topic, second_score = sorted_scores[1]
            margin = top_score - second_score
            if margin < 0.3:
                # Use model probabilities to break tie
                if model_probs:
                    p1 = model_probs.get(top_topic, 0.0)
                    p2 = model_probs.get(second_topic, 0.0)
                    if abs(p1 - p2) > 0.05:
                        return top_topic if p1 > p2 else second_topic
                return None
                
    return top_topic


def _compile_patterns_with_weights(
    patterns: Dict[str, Iterable]
) -> tuple:
    """
    Compile regex patterns and extract inline weights.
    
    Args:
        patterns: Dict of {topic: [patterns]} where patterns can be strings or dicts
        
    Returns:
        (compiled_patterns, weights) where:
        - compiled_patterns: {topic: [re.Pattern, ...]}
        - weights: {topic: [weight or None, ...]}
    """
    compiled: Dict[str, List[re.Pattern]] = {}
    weights: Dict[str, List[Optional[float]]] = {}
    
    for topic, pattern_list in patterns.items():
        compiled[topic] = []
        weights[topic] = []
        
        for p in pattern_list:
            if isinstance(p, dict):
                # Weighted pattern format
                pat_str = p.get("pattern", "")
                weight = p.get("weight", 1.0)
            else:
                # String format
                pat_str = p
                weight = None  # Use default
            
            try:
                compiled[topic].append(re.compile(pat_str, re.IGNORECASE))
                weights[topic].append(weight)
            except re.error:
                logger.debug(f"Invalid regex pattern: {pat_str}")
                continue
    
    return compiled, weights


def _compile_patterns(patterns: Dict[str, Iterable[str]]) -> Dict[str, List[re.Pattern]]:
    """Compile regex patterns for all topics (legacy, no weights)."""
    compiled, _ = _compile_patterns_with_weights(patterns)
    return compiled


def _build_pattern_weights(stats: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """Build pattern weights from evaluation stats."""
    pattern_weights: Dict[str, Dict[str, float]] = {}
    
    if "topics" not in stats:
        return pattern_weights
    
    for topic, info in stats["topics"].items():
        w_map = {}
        for p_entry in info.get("patterns", []):
            pat_str = p_entry.get("pattern")
            prec = p_entry.get("precision", 0.0)
            tp = p_entry.get("tp", 0)
            tier = p_entry.get("tier", "C")
            
            # Weight formula: (precision * log(1 + tp)) * TierMultiplier
            base = prec * math.log(1 + tp)
            tier_mult = {"A": 1.2, "B": 1.0}.get(tier, 0.6)
            weight = base * tier_mult
            
            if pat_str:
                w_map[pat_str] = weight
        pattern_weights[topic] = w_map
    
    return pattern_weights


@lru_cache(maxsize=16)
def _get_topic_patterns(exam_code: str, paper: int = 1) -> Dict[str, List[str]]:
    """Get topic patterns for an exam code."""
    from gcse_toolkit.common.topics import topic_patterns_from_subtopics
    return topic_patterns_from_subtopics(exam_code) or {}


@lru_cache(maxsize=16)
def _get_exam_stats(exam_code: str) -> Dict[str, Any]:
    """Get evaluation stats for an exam code."""
    from gcse_toolkit.plugins import load_exam_stats
    return load_exam_stats(exam_code) or {}


@lru_cache(maxsize=16)
def _get_topic_model(exam_code: str):
    """Load topic model for an exam code if available."""
    from gcse_toolkit.plugins import get_exam_plugin
    
    try:
        plugin = get_exam_plugin(exam_code)
        
        # Priority 1: Use model path from manifest (validated.model)
        # Note: ValidatedManifest dataclass has a 'model' field
        from gcse_toolkit.plugins.validation import validate_manifest
        manifest_path = plugin.subtopics_path.parent / "manifest.json"
        
        model_rel_path = "models/topic_model.joblib" # Default
        if manifest_path.exists():
            validated = validate_manifest(manifest_path)
            if validated.model:
                model_rel_path = validated.model
        
        model_path = plugin.subtopics_path.parent / model_rel_path
        
        if model_path.exists():
            from gcse_toolkit.extractor_v2.utils.topic_model import TopicModel
            return TopicModel(model_path)
    except Exception as e:
        logger.debug(f"Could not load topic model for {exam_code}: {e}")
    
    return None
