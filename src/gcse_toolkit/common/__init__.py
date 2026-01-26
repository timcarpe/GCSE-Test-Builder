"""Common utilities shared across the toolkit."""

from __future__ import annotations

from .exams import (
    ExamDefinition,
    get_exam_definition,
    supported_exam_codes,
    UnsupportedCodeError,
)
from .topics import (
    resolve_topic_label,
    canonical_sub_topic_label,
    topic_sub_topics,
    topic_patterns_from_subtopics,
    classify_sub_topics,
    normalise_topic_label,
    normalise_sub_topic,
    sub_topic_parents,
    iter_all_sub_topics,
    FALLBACK_SUB_TOPIC,
)

__all__ = [
    # exams
    "ExamDefinition",
    "get_exam_definition",
    "supported_exam_codes",
    "UnsupportedCodeError",
    # topics
    "resolve_topic_label",
    "canonical_sub_topic_label",
    "topic_sub_topics",
    "topic_patterns_from_subtopics",
    "classify_sub_topics",
    "normalise_topic_label",
    "normalise_sub_topic",
    "sub_topic_parents",
    "iter_all_sub_topics",
    "FALLBACK_SUB_TOPIC",
    # legacy module references
    "bbox_utils",
    "path_utils",
]

