"""
Serialization Utilities (V2)

Provides to/from JSON utilities for V2 data models.

**DESIGN DEVIATION FROM V1:**

V1 Problem:
- `_question_from_payload()` and `_part_from_payload()` in loader.py
- Mixed parsing logic with mark calculation
- `total_marks` stored, often wrong
- Multiple fallback paths for missing data

V2 Solution:
- Clean separation: `serialize_*` and `deserialize_*` functions
- All models have `to_dict()` and `from_dict()` methods
- Validation via schemas before deserialization
- Never store calculated values (total_marks)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models.marks import Marks
from ..models.bounds import SliceBounds
from ..models.parts import Part, PartKind
from ..models.questions import Question
from ..schemas.validator import validate_question, validate_regions, ValidationError


# ─────────────────────────────────────────────────────────────────────────────
# Question Serialization
# ─────────────────────────────────────────────────────────────────────────────

def serialize_question(question: Question) -> dict[str, Any]:
    """
    Serialize a Question to a dictionary.
    
    The output can be written to JSON and will pass schema validation.
    
    Args:
        question: Question instance to serialize
        
    Returns:
        Dictionary suitable for JSON serialization
        
    Note:
        total_marks is NOT included - it's always calculated on load.
    """
    return question.to_dict()


def deserialize_question(
    data: dict[str, Any],
    *,
    validate: bool = True,
    base_path: Path | None = None,
) -> Question:
    """
    Deserialize a Question from a dictionary.
    
    Args:
        data: Dictionary from JSON
        validate: Whether to validate against schema first
        base_path: If provided, composite_path and regions_path are relative to this
        
    Returns:
        Question instance
        
    Raises:
        ValidationError: If validate=True and data is invalid
        ValueError: If data cannot be parsed
    """
    if validate:
        validate_question(data, strict=False)  # Basic validation
    
    # Parse question_node
    question_node = _deserialize_part(data["question_node"])
    
    # Resolve paths
    composite_path = Path(data.get("composite_path", ""))
    regions_path = Path(data.get("regions_path", ""))
    mark_scheme_path = Path(data["mark_scheme_path"]) if data.get("mark_scheme_path") else None
    
    if base_path:
        composite_path = base_path / composite_path
        regions_path = base_path / regions_path
        if mark_scheme_path:
            mark_scheme_path = base_path / mark_scheme_path
    
    return Question(
        id=data["id"],
        exam_code=data["exam_code"],
        year=data["year"],
        paper=data["paper"],
        variant=data.get("variant", 1),
        topic=data["topic"],
        question_node=question_node,
        composite_path=composite_path,
        regions_path=regions_path,
        mark_scheme_path=mark_scheme_path,
        sub_topics=tuple(data.get("sub_topics", [])),
        content_right=data.get("content_right"),
        numeral_bbox=tuple(data["numeral_bbox"]) if data.get("numeral_bbox") else None,
        root_text=data.get("root_text", ""),
        child_text=data.get("child_text", {}),
        mark_bboxes=tuple(tuple(box) for box in data.get("mark_bboxes", [])),
        horizontal_offset=data.get("horizontal_offset", 0),
    )


def _deserialize_part(data: dict[str, Any]) -> Part:
    """Deserialize a Part from a dictionary."""
    # Parse children recursively
    children = tuple(
        _deserialize_part(child) for child in data.get("children", [])
    )
    
    # Parse bounds
    bounds = SliceBounds.from_dict(data["bounds"])
    context_bounds = (
        SliceBounds.from_dict(data["context_bounds"])
        if "context_bounds" in data else None
    )
    label_bbox = (
        SliceBounds.from_dict(data["label_bbox"])
        if "label_bbox" in data else None
    )
    
    # Parse marks
    marks = Marks(
        value=data["marks"],
        source=data.get("mark_source", "explicit"),
    )
    
    return Part(
        label=data["label"],
        kind=PartKind(data["kind"]),
        marks=marks,
        bounds=bounds,
        context_bounds=context_bounds,
        label_bbox=label_bbox,
        children=children,
        topic=data.get("topic"),
        sub_topics=tuple(data.get("sub_topics", [])),
        is_valid=data.get("is_valid", True),
        validation_issues=tuple(data.get("validation_issues", [])),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Regions Serialization
# ─────────────────────────────────────────────────────────────────────────────

def serialize_regions(
    question_id: str,
    regions: dict[str, SliceBounds],
    composite_size: tuple[int, int],
    context_bounds: dict[str, SliceBounds] | None = None,
) -> dict[str, Any]:
    """
    Serialize region bounds to a dictionary.
    
    Args:
        question_id: Question this regions data belongs to
        regions: Map of part labels to content bounds
        composite_size: (width, height) of composite image
        context_bounds: Optional map of part labels to context bounds
        
    Returns:
        Dictionary suitable for JSON serialization
    """
    from ..schemas.validator import REGIONS_SCHEMA_VERSION
    
    regions_data = {}
    for label, bounds in regions.items():
        region = {"bounds": bounds.to_dict()}
        if context_bounds and label in context_bounds:
            region["context_bounds"] = context_bounds[label].to_dict()
        regions_data[label] = region
    
    return {
        "schema_version": REGIONS_SCHEMA_VERSION,
        "question_id": question_id,
        "composite_size": {
            "width": composite_size[0],
            "height": composite_size[1],
        },
        "regions": regions_data,
    }


def deserialize_regions(
    data: dict[str, Any],
    *,
    validate: bool = True,
) -> tuple[dict[str, SliceBounds], tuple[int, int]]:
    """
    Deserialize region bounds from a dictionary.
    
    Args:
        data: Dictionary from JSON
        validate: Whether to validate against schema first
        
    Returns:
        Tuple of (regions dict, composite_size tuple)
        
    Raises:
        ValidationError: If validate=True and data is invalid
    """
    if validate:
        validate_regions(data, strict=False)
    
    regions = {}
    for label, region in data.get("regions", {}).items():
        regions[label] = SliceBounds.from_dict(region["bounds"])
    
    size = data.get("composite_size", {})
    composite_size = (size.get("width", 0), size.get("height", 0))
    
    return regions, composite_size


# ─────────────────────────────────────────────────────────────────────────────
# JSONL Utilities
# ─────────────────────────────────────────────────────────────────────────────

def load_questions_jsonl(
    path: Path,
    *,
    validate: bool = True,
    base_path: Path | None = None,
) -> list[Question]:
    """
    Load questions from a JSONL file.
    
    Args:
        path: Path to questions.jsonl file
        validate: Whether to validate each question
        base_path: Base path for resolving relative paths (defaults to parent of jsonl)
        
    Returns:
        List of Question instances
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValidationError: If any question is invalid
    """
    if not path.exists():
        raise FileNotFoundError(f"Questions file not found: {path}")
    
    if base_path is None:
        base_path = path.parent
    
    questions = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                question = deserialize_question(data, validate=validate, base_path=base_path)
                questions.append(question)
            except (json.JSONDecodeError, ValidationError, ValueError) as e:
                raise ValidationError(
                    f"Error parsing line {line_no}: {e}",
                    path=str(path),
                    errors=[str(e)]
                )
    
    return questions


def save_questions_jsonl(questions: list[Question], path: Path) -> None:
    """
    Save questions to a JSONL file.
    
    Args:
        questions: List of Question instances to save
        path: Output path for questions.jsonl
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        for question in questions:
            data = serialize_question(question)
            f.write(json.dumps(data, ensure_ascii=False))
            f.write("\n")


def load_regions_json(path: Path, *, validate: bool = True) -> dict[str, SliceBounds]:
    """
    Load regions from a JSON file.
    
    Args:
        path: Path to regions.json file
        validate: Whether to validate
        
    Returns:
        Dictionary mapping part labels to SliceBounds
    """
    if not path.exists():
        raise FileNotFoundError(f"Regions file not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    regions, _ = deserialize_regions(data, validate=validate)
    return regions


def save_regions_json(
    path: Path,
    question_id: str,
    regions: dict[str, SliceBounds],
    composite_size: tuple[int, int],
    context_bounds: dict[str, SliceBounds] | None = None,
) -> None:
    """
    Save regions to a JSON file.
    
    Args:
        path: Output path for regions.json
        question_id: Question ID
        regions: Map of part labels to bounds
        composite_size: (width, height) of composite image
        context_bounds: Optional context bounds
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = serialize_regions(question_id, regions, composite_size, context_bounds)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
