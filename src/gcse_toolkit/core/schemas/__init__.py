"""
Schemas Package (V2)

JSON schema definitions and validation utilities.
"""

from .validator import (
    validate_question,
    validate_regions,
    ValidationError,
    QUESTION_SCHEMA_VERSION,
    REGIONS_SCHEMA_VERSION,
)

__all__ = [
    "validate_question",
    "validate_regions",
    "ValidationError",
    "QUESTION_SCHEMA_VERSION",
    "REGIONS_SCHEMA_VERSION",
]
