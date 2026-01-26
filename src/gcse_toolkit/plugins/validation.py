"""Plugin validation and model signing.

This module provides runtime validation for plugin manifests
and signature verification for model files.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# Schema Versioning
# =============================================================================
# BACKWARD COMPATIBILITY POLICY:
# - The application maintains backward compatibility with older schema versions
# - Newer code can read older formats without error
# - If loaded manifest_schema_version < expected, a soft warning is logged
# - If loaded manifest_schema_version > expected, no warning (newer data accepted)
# - Version format: integer (easier comparison than semantic versioning strings)
#
# MANIFEST_SCHEMA_VERSION: Version of the plugin manifest format
# Used in: manifest.json files, manifest_schema_version key
# Changelog:
#   v1: Initial schema with code, name, subtopics_path, default
#   v2: Added supported_years field for tracking training data years
#   v3: Added board field
# =============================================================================
MANIFEST_SCHEMA_VERSION = 3


class ManifestValidationError(RuntimeError):
    """Raised when manifest validation fails."""


@dataclass(frozen=True)
class ValidatedManifest:
    """Validated and type-safe manifest data."""
    code: str
    name: str
    subtopics_path: str
    default: bool
    model: Optional[str]  # Relative path to model file, or None if no model
    manifest_schema_version: int  # Manifest schema version (integer)
    generated_at: Optional[str]  # ISO timestamp when generated
    generator_version: Optional[str]  # Version of generator that created this
    supported_years: List[str]  # Years of exams the plugin was trained on
    board: Optional[str]  # Exam board identifier (e.g. "Cambridge")


def validate_manifest(manifest_path: Path) -> ValidatedManifest:
    """Validate manifest.json schema and return typed data.
    
    Args:
        manifest_path: Path to manifest.json file.
        
    Returns:
        ValidatedManifest with validated fields.
        
    Raises:
        ManifestValidationError: If validation fails.
    """
    try:
        text = manifest_path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        raise ManifestValidationError(f"Cannot read manifest {manifest_path}: {e}") from e
    
    if not isinstance(data, dict):
        raise ManifestValidationError(f"Manifest must be a JSON object: {manifest_path}")
    
    # Required fields
    code = str(data.get("code", "")).strip()
    name = str(data.get("name", "")).strip()
    
    # Code validation: alphanumeric, 1-10 chars
    if not re.match(r"^[A-Za-z0-9]{1,10}$", code):
        raise ManifestValidationError(
            f"Invalid code '{code}': must be 1-10 alphanumeric characters"
        )
    
    # Name validation: non-empty, reasonable length
    if not name:
        raise ManifestValidationError("Missing 'name' field in manifest")
    if len(name) > 100:
        raise ManifestValidationError(f"Name exceeds 100 characters: {name[:50]}...")
    
    # Optional fields with defaults
    subtopics_path = data.get("subtopics_path", "topic_subtopics.json")
    if not isinstance(subtopics_path, str):
        raise ManifestValidationError("subtopics_path must be a string")
    
    default = data.get("default", False)
    if not isinstance(default, bool):
        raise ManifestValidationError("default must be a boolean")
    
    # Optional model field
    model = data.get("model")
    if model is not None and not isinstance(model, str):
        raise ManifestValidationError("model must be a string or null")
    
    # Version metadata (optional, for informational purposes)
    # Support both old "schema_version" (string) and new "manifest_schema_version" (int)
    raw_schema = data.get("manifest_schema_version") or data.get("schema_version")
    try:
        manifest_schema_version = int(float(str(raw_schema).replace(".", ""))) if raw_schema else 1
    except (ValueError, TypeError):
        manifest_schema_version = 1
    
    generated_at = data.get("generated_at")
    generator_version = data.get("generator_version")
    
    # Supported years (optional, defaults to empty list)
    supported_years = data.get("supported_years", [])
    if not isinstance(supported_years, list):
        supported_years = []
    supported_years = [str(y) for y in supported_years if isinstance(y, (str, int))]
    
    # Optional board field
    board = data.get("board")
    if board is not None and not isinstance(board, str):
        raise ManifestValidationError("board must be a string or null")

    # Version check: warn if manifest is behind expected (backward compatible)
    if manifest_schema_version < MANIFEST_SCHEMA_VERSION:
        logger.warning(
            f"Plugin '{code}' has manifest_schema_version {manifest_schema_version}, "
            f"expected {MANIFEST_SCHEMA_VERSION}. Consider regenerating the plugin.",
            extra={"code": code, "manifest_version": manifest_schema_version}
        )
    
    return ValidatedManifest(
        code=code,
        name=name,
        subtopics_path=subtopics_path,
        default=default,
        model=model,
        manifest_schema_version=manifest_schema_version,
        generated_at=generated_at,
        generator_version=generator_version,
        supported_years=supported_years,
        board=board,
    )


def sign_model(model_path: Path) -> Path:
    """Generate SHA256 checksum file for a model.
    
    Args:
        model_path: Path to model file to sign.
        
    Returns:
        Path to the generated .sha256 signature file.
    """
    checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
    sig_path = model_path.with_suffix(model_path.suffix + ".sha256")
    sig_path.write_text(checksum, encoding="utf-8")
    return sig_path


def verify_model(model_path: Path) -> bool:
    """Verify model file against its SHA256 signature.
    
    Args:
        model_path: Path to model file to verify.
        
    Returns:
        True if signature is valid or no signature exists.
        False if signature exists but doesn't match.
    """
    sig_path = model_path.with_suffix(model_path.suffix + ".sha256")
    if not sig_path.exists():
        return True  # No signature = skip verification (allow unsigned)
    
    try:
        expected = sig_path.read_text(encoding="utf-8").strip()
        actual = hashlib.sha256(model_path.read_bytes()).hexdigest()
        return expected == actual
    except Exception:
        return False


def update_manifest_model(manifest_path: Path, model_relative_path: str) -> None:
    """Update manifest.json with model path after training.
    
    Args:
        manifest_path: Path to manifest.json file.
        model_relative_path: Relative path to model file from plugin root.
    """
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    
    data["model"] = model_relative_path
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
