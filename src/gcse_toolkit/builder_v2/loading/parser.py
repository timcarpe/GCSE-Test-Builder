"""
Module: builder_v2.loading.parser

Purpose:
    Parse and validate JSON metadata files from the V2 cache format.
    Provides typed dataclasses for parsed data.

Key Functions:
    - parse_metadata(): Parse metadata.json file
    - parse_regions(): Parse regions.json file

Key Classes:
    - ParsedMetadata: Parsed metadata.json contents
    - ParsedRegion: Single region from regions.json
    - ParseError: Exception for parse failures

Dependencies:
    - json (std)
    - pathlib (std)
    - gcse_toolkit.core.schemas.validator: Schema validation

Used By:
    - builder_v2.loading.loader: Question loading
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gcse_toolkit.core.schemas.validator import validate_regions

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """Error parsing metadata file."""
    pass


@dataclass(frozen=True)
class ParsedMetadata:
    """
    Parsed and validated metadata.json contents.
    
    Attributes:
    Parsed metadata from metadata.json.
    
    Contains all fields needed to construct a Question object.
    Intermediate step between raw JSON and Question.
    """
    question_id: str
    exam_code: str
    year: int
    paper: int
    variant: int
    question_number: int
    total_marks: int
    part_count: int
    topic: str
    content_right: Optional[int] = None
    numeral_bbox: Optional[Tuple[int, int, int, int]] = None
    root_text: str = ""
    child_text: Dict[str, str] = field(default_factory=dict)
    child_topics: Dict[str, str] = field(default_factory=dict)  # Schema v9: part label -> topic
    markscheme_path: Optional[str] = None
    horizontal_offset: int = 0  # Phase 6.10: For render-time alignment


@dataclass(frozen=True)
class ParsedRegion:
    """
    Parsed region from regions.json.
    
    Attributes:
        label: Part label like "1(a)(i)"
        kind: Part type ("question", "letter", "roman")
        top: Top coordinate in pixels
        bottom: Bottom coordinate in pixels
        left: Left coordinate in pixels
        right: Right coordinate in pixels
        marks: Mark value for this part (optional)
    """
    label: str
    kind: str
    top: int
    bottom: int
    left: int
    right: int
    marks: Optional[int] = None


@dataclass(frozen=True)
class ParsedRegions:
    """
    Parsed regions.json contents.
    
    Attributes:
        question_id: Question identifier
        schema_version: Schema version number
        composite_width: Composite image width
        composite_height: Composite image height
        regions: List of parsed regions
        numeral_bbox: Question numeral bbox (moved from metadata)
        mark_bboxes: List of mark box bboxes (moved from metadata)
        horizontal_offset: Horizontal offset for alignment (moved from metadata)
    """
    question_id: str
    schema_version: int
    composite_width: int
    composite_height: int
    regions: List[ParsedRegion]
    numeral_bbox: Optional[Tuple[int, int, int, int]] = None
    mark_bboxes: Optional[List[Tuple[int, int, int, int]]] = None
    horizontal_offset: int = 0


def parse_metadata(path: Path) -> ParsedMetadata:
    """
    Parse metadata.json file.
    
    Validates:
    - File exists and is valid JSON
    - Required fields present
    - Field types correct
    
    Args:
        path: Path to metadata.json
        
    Returns:
        ParsedMetadata object
        
    Raises:
        ParseError: If file missing, invalid JSON, or missing fields
        
    Example:
        >>> meta = parse_metadata(Path("q1/metadata.json"))
        >>> meta.exam_code
        '0478'
    """
    if not path.exists():
        raise ParseError(f"Metadata file not found: {path}")
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON in {path}: {e}")
    
    return parse_metadata_from_dict(data, source=str(path))


def parse_metadata_from_dict(data: Dict[str, Any], *, source: str = "JSONL") -> ParsedMetadata:
    """
    Parse metadata from a dict (e.g., from JSONL record).
    
    This is the single source of truth for metadata parsing.
    Used by both parse_metadata() (file) and JSONL loading.
    
    Args:
        data: Dict with metadata fields
        source: Source identifier for error messages
        
    Returns:
        ParsedMetadata object
        
    Raises:
        ParseError: If missing required fields or invalid types
    """
    # Validate required fields
    required = [
        "question_id", "exam_code", "year", "paper", "variant",
        "question_number", "total_marks", "part_count", "topic"
    ]
    missing = [field for field in required if field not in data]
    if missing:
        raise ParseError(f"Missing required fields in {source}: {missing}")
    
    try:
        return ParsedMetadata(
            question_id=str(data["question_id"]),
            exam_code=str(data["exam_code"]),
            year=int(data["year"]),
            paper=int(data["paper"]),
            variant=int(data["variant"]),
            question_number=int(data["question_number"]),
            total_marks=int(data["total_marks"]),
            part_count=int(data["part_count"]),
            topic=str(data["topic"]),
            content_right=int(data["content_right"]) if data.get("content_right") else None,
            numeral_bbox=tuple(data["numeral_bbox"]) if data.get("numeral_bbox") else None,
            root_text=str(data.get("root_text", "")),
            child_text=dict(data.get("child_text", {})),
            child_topics=dict(data.get("child_topics", {})),
            markscheme_path=data.get("markscheme_path"),
            horizontal_offset=int(data.get("horizontal_offset", 0)),
        )
    except (ValueError, TypeError) as e:
        raise ParseError(f"Invalid field type in {source}: {e}")


def parse_regions(path: Path, *, validate: bool = True) -> ParsedRegions:
    """
    Parse regions.json file.
    
    Validates:
    - File exists and is valid JSON
    - Schema version supported
    - Node structure valid (via schema validation)
    
    Args:
        path: Path to regions.json
        validate: Whether to validate against schema (default True)
        
    Returns:
        ParsedRegions object
        
    Raises:
        ParseError: If file missing, invalid JSON, or schema invalid
        
    Example:
        >>> regions = parse_regions(Path("q1/regions.json"))
        >>> len(regions.regions)
        5
    """
    if not path.exists():
        raise ParseError(f"Regions file not found: {path}")
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON in {path}: {e}")
    
    # Validate against schema
    if validate:
        try:
            validate_regions(data)
        except Exception as e:
            raise ParseError(f"Schema validation failed for {path}: {e}")
    
    # Extract fields
    schema_version = data.get("schema_version", 1)
    question_id = data.get("question_id", "")
    composite_size = data.get("composite_size", {})
    composite_width = composite_size.get("width", 0)
    composite_height = composite_size.get("height", 0)
    
    # Parse regions
    regions_data = data.get("regions", {})
    regions = []
    
    for label, region_data in regions_data.items():
        bounds = region_data.get("bounds", {})
        kind = region_data.get("kind", _infer_kind(label))
        marks = region_data.get("marks")  # Optional, may be None
        
        regions.append(ParsedRegion(
            label=label,
            kind=kind,
            top=int(bounds.get("top", 0)),
            bottom=int(bounds.get("bottom", 0)),
            left=int(bounds.get("left", 0)),
            right=int(bounds.get("right", composite_width)),
            marks=int(marks) if marks is not None else None,
        ))
    
    # Sort by top position
    regions.sort(key=lambda r: r.top)
    
    # Parse bbox fields (added in schema v2)
    numeral_bbox = None
    if data.get("numeral_bbox"):
        numeral_bbox = tuple(data["numeral_bbox"])
    
    mark_bboxes = None
    if data.get("mark_bboxes"):
        mark_bboxes = [tuple(bbox) for bbox in data["mark_bboxes"]]
    
    horizontal_offset = int(data.get("horizontal_offset", 0))
    
    return ParsedRegions(
        question_id=question_id,
        schema_version=schema_version,
        composite_width=composite_width,
        composite_height=composite_height,
        regions=regions,
        numeral_bbox=numeral_bbox,
        mark_bboxes=mark_bboxes,
        horizontal_offset=horizontal_offset,
    )


def _infer_kind(label: str) -> str:
    """Infer part kind from label format."""
    # Count parentheses depth
    paren_count = label.count("(")
    if paren_count == 0:
        return "question"
    elif paren_count == 1:
        return "letter"
    else:
        return "roman"
