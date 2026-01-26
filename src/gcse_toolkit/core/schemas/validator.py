"""
Schema Validation Utilities (V2)

Validates JSON data against V2 schemas.

**DESIGN DEVIATION FROM V1:**

V1 Problem:
- `_validate_question_payload()` in loader.py did basic checks
- Schema version checked but structure not fully validated
- Easy to create invalid data

V2 Solution:
- JSON Schema definitions for all data formats
- `validate_question()` and `validate_regions()` functions
- Fail fast on any schema violation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


# Schema version constants
QUESTION_SCHEMA_VERSION = 9  # V2 schema version (V1 was 6, V2.0 was 7, V2.1 adds is_valid, V2.2 adds sub_topic fix)
REGIONS_SCHEMA_VERSION = 3  # v3 adds is_valid, validation_issues for 1:1 diagnostic parity


# Load schemas lazily
_SCHEMAS: dict[str, dict] = {}


def _get_jsonschema():
    """Import jsonschema lazily."""
    try:
        import jsonschema
        return jsonschema
    except ImportError:
        return None


def _load_schema(name: str) -> dict:
    """Load a schema from the schemas directory."""
    if name not in _SCHEMAS:
        schema_path = Path(__file__).parent / f"{name}.schema.json"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {schema_path}")
        with open(schema_path, "r", encoding="utf-8") as f:
            _SCHEMAS[name] = json.load(f)
    return _SCHEMAS[name]


class ValidationError(Exception):
    """Raised when data fails schema validation."""
    
    def __init__(self, message: str, path: str = "", errors: list[str] | None = None):
        super().__init__(message)
        self.path = path
        self.errors = errors or []


def validate_question(data: dict[str, Any], *, strict: bool = False) -> None:
    """
    Validate question data against the V2 schema.
    
    Supports two formats:
    1. Discovery Format (flat metadata used in questions.jsonl)
    2. Model Format (hierarchical data used for Question object)
    
    Args:
        data: Question dictionary to validate
        strict: If True, use jsonschema; if False, do basic checks only
        
    Raises:
        ValidationError: If data is invalid
    """
    is_model = "question_node" in data
    
    # Basic required field checks
    if is_model:
        # Model format
        required = ["id", "exam_code", "year", "paper", "topic"]
    else:
        # Discovery format
        required = [
            "schema_version", "question_id", "exam_code", "year", "paper", 
            "topic", "relative_path", "is_valid"
        ]
        
    missing = [f for f in required if f not in data]
    if missing:
        raise ValidationError(
            f"Missing required fields: {missing}",
            path="",
            errors=[f"Missing field: {f}" for f in missing]
        )
    
    # Validate schema version (only for Discovery format)
    if not is_model:
        version = data.get("schema_version")
        if version != QUESTION_SCHEMA_VERSION:
            raise ValidationError(
                f"Unsupported question schema version: {version} (expected {QUESTION_SCHEMA_VERSION})",
                path="schema_version"
            )

    # Validate exam_code format
    exam_code = data.get("exam_code", "")
    if not (isinstance(exam_code, str) and len(exam_code) == 4 and exam_code.isdigit()):
        raise ValidationError(
            f"Invalid exam_code: {exam_code!r} (must be 4 digits)",
            path="exam_code"
        )
    
    # Validate year range
    year = data.get("year", 0)
    if not (2000 <= year <= 2100):
        raise ValidationError(
            f"Invalid year: {year} (must be 2000-2100)",
            path="year"
        )
    
    # Validate question_node if present (recursively)
    if is_model:
        _validate_part(data["question_node"], "question_node")
    
    # Full schema validation if jsonschema available and strict mode
    if strict:
        jsonschema = _get_jsonschema()
        if jsonschema:
            schema_name = "question_model" if is_model else "question"
            schema = _load_schema(schema_name)
            try:
                jsonschema.validate(data, schema)
            except jsonschema.ValidationError as e:
                raise ValidationError(
                    f"Schema validation failed: {e.message}",
                    path=".".join(str(p) for p in e.absolute_path),
                    errors=[e.message]
                )


def _validate_part(data: dict[str, Any], path: str) -> None:
    """Validate a part node recursively."""
    required = ["label", "kind", "marks", "bounds"]
    missing = [f for f in required if f not in data]
    if missing:
        raise ValidationError(
            f"Part missing required fields: {missing}",
            path=path,
            errors=[f"Missing field: {f}" for f in missing]
        )
    
    # Validate kind
    kind = data.get("kind")
    if kind not in ("question", "letter", "roman"):
        raise ValidationError(
            f"Invalid part kind: {kind!r}",
            path=f"{path}.kind"
        )
    
    # Validate marks
    marks = data.get("marks")
    if not isinstance(marks, int) or marks < 0:
        raise ValidationError(
            f"Invalid marks: {marks} (must be non-negative integer)",
            path=f"{path}.marks"
        )
    
    # Validate bounds
    bounds = data.get("bounds")
    if not isinstance(bounds, dict):
        raise ValidationError(
            "bounds must be a dict",
            path=f"{path}.bounds"
        )
    _validate_bounds(bounds, f"{path}.bounds")
    
    # Validate context_bounds if present
    if "context_bounds" in data:
        if kind == "roman":
            raise ValidationError(
                "Roman parts should not have context_bounds",
                path=f"{path}.context_bounds"
            )
        _validate_bounds(data["context_bounds"], f"{path}.context_bounds")
    
    # Validate children recursively
    children = data.get("children", [])
    if not isinstance(children, list):
        raise ValidationError(
            "children must be a list",
            path=f"{path}.children"
        )
    for i, child in enumerate(children):
        _validate_part(child, f"{path}.children[{i}]")


def _validate_bounds(data: dict[str, Any], path: str) -> None:
    """Validate bounds data."""
    if "top" not in data or "bottom" not in data:
        raise ValidationError(
            "bounds must have top and bottom",
            path=path
        )
    
    top = data["top"]
    bottom = data["bottom"]
    
    if not isinstance(top, int) or top < 0:
        raise ValidationError(
            f"Invalid top: {top} (must be non-negative integer)",
            path=f"{path}.top"
        )
    
    if not isinstance(bottom, int) or bottom <= top:
        raise ValidationError(
            f"Invalid bottom: {bottom} (must be > top={top})",
            path=f"{path}.bottom"
        )


def validate_regions(data: dict[str, Any], *, strict: bool = False) -> None:
    """
    Validate regions data against the V2 schema.
    
    Args:
        data: Regions dictionary to validate
        strict: If True, use jsonschema; if False, do basic checks only
        
    Raises:
        ValidationError: If data is invalid
    """
    required = ["schema_version", "question_id", "composite_size", "regions"]
    missing = [f for f in required if f not in data]
    if missing:
        raise ValidationError(
            f"Missing required fields: {missing}",
            errors=[f"Missing field: {f}" for f in missing]
        )
    
    # Validate schema version (only accept latest version)
    version = data.get("schema_version")
    if version != REGIONS_SCHEMA_VERSION:
        raise ValidationError(
            f"Unsupported regions schema version: {version} (expected {REGIONS_SCHEMA_VERSION})",
            path="schema_version"
        )
    
    # Validate composite_size
    size = data.get("composite_size", {})
    if not isinstance(size, dict) or "width" not in size or "height" not in size:
        raise ValidationError(
            "composite_size must have width and height",
            path="composite_size"
        )
    
    # Validate regions
    regions = data.get("regions", {})
    if not isinstance(regions, dict):
        raise ValidationError(
            "regions must be a dict",
            path="regions"
        )
    
    for label, region in regions.items():
        if not isinstance(region, dict) or "bounds" not in region:
            raise ValidationError(
                f"Region {label!r} must have bounds",
                path=f"regions.{label}"
            )
        _validate_bounds(region["bounds"], f"regions.{label}.bounds")
    
    # Full schema validation if available
    if strict:
        jsonschema = _get_jsonschema()
        if jsonschema:
            schema = _load_schema("regions")
            try:
                jsonschema.validate(data, schema)
            except jsonschema.ValidationError as e:
                raise ValidationError(
                    f"Schema validation failed: {e.message}",
                    path=".".join(str(p) for p in e.absolute_path),
                    errors=[e.message]
                )
