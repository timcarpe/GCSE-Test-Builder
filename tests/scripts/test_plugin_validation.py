"""Unit tests for plugin validation and signing."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from gcse_toolkit.plugins.validation import (
    validate_manifest,
    sign_model,
    verify_model,
    update_manifest_model,
    ManifestValidationError,
    ValidatedManifest,
)


class TestValidateManifest:
    """Tests for validate_manifest function."""

    def test_valid_manifest(self, tmp_path: Path) -> None:
        """Valid manifest returns ValidatedManifest."""
        manifest = {"code": "0478", "name": "Computer Science 0478"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        
        assert isinstance(result, ValidatedManifest)
        assert result.code == "0478"
        assert result.name == "Computer Science 0478"
        assert result.subtopics_path == "topic_subtopics.json"
        assert result.default is False
        assert result.model is None

    def test_valid_manifest_with_all_fields(self, tmp_path: Path) -> None:
        """Manifest with all optional fields."""
        manifest = {
            "code": "ABC123",
            "name": "Test Exam",
            "subtopics_path": "custom.json",
            "default": True,
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        
        assert result.subtopics_path == "custom.json"
        assert result.default is True

    def test_rejects_missing_code(self, tmp_path: Path) -> None:
        """Missing code field raises error."""
        manifest = {"name": "Test"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        with pytest.raises(ManifestValidationError, match="Invalid code"):
            validate_manifest(tmp_path / "manifest.json")

    def test_rejects_non_alphanumeric_code(self, tmp_path: Path) -> None:
        """Non-alphanumeric code raises error."""
        manifest = {"code": "../evil", "name": "Bad"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        with pytest.raises(ManifestValidationError, match="alphanumeric"):
            validate_manifest(tmp_path / "manifest.json")

    def test_rejects_long_code(self, tmp_path: Path) -> None:
        """Code exceeding 10 chars raises error."""
        manifest = {"code": "A" * 20, "name": "Too Long Code"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        with pytest.raises(ManifestValidationError, match="1-10"):
            validate_manifest(tmp_path / "manifest.json")

    def test_rejects_missing_name(self, tmp_path: Path) -> None:
        """Missing name field raises error."""
        manifest = {"code": "0478"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        with pytest.raises(ManifestValidationError, match="name"):
            validate_manifest(tmp_path / "manifest.json")

    def test_rejects_long_name(self, tmp_path: Path) -> None:
        """Name exceeding 100 chars raises error."""
        manifest = {"code": "0478", "name": "X" * 150}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        with pytest.raises(ManifestValidationError, match="100"):
            validate_manifest(tmp_path / "manifest.json")

    def test_rejects_invalid_json(self, tmp_path: Path) -> None:
        """Invalid JSON raises error."""
        (tmp_path / "manifest.json").write_text("{invalid json")
        
        with pytest.raises(ManifestValidationError, match="Cannot read"):
            validate_manifest(tmp_path / "manifest.json")


class TestModelSigning:
    """Tests for sign_model and verify_model functions."""

    def test_sign_creates_checksum_file(self, tmp_path: Path) -> None:
        """sign_model creates .sha256 file."""
        model_path = tmp_path / "model.pkl"
        model_path.write_bytes(b"model content")
        
        sig_path = sign_model(model_path)
        
        assert sig_path.exists()
        assert sig_path.name == "model.pkl.sha256"
        assert len(sig_path.read_text()) == 64  # SHA256 hex length

    def test_verify_valid_signature(self, tmp_path: Path) -> None:
        """verify_model returns True for valid signature."""
        model_path = tmp_path / "model.pkl"
        model_path.write_bytes(b"model content")
        sign_model(model_path)
        
        assert verify_model(model_path) is True

    def test_verify_tampered_file(self, tmp_path: Path) -> None:
        """verify_model returns False for tampered file."""
        model_path = tmp_path / "model.pkl"
        model_path.write_bytes(b"original content")
        sign_model(model_path)
        
        # Tamper with the model
        model_path.write_bytes(b"tampered content")
        
        assert verify_model(model_path) is False

    def test_verify_no_signature(self, tmp_path: Path) -> None:
        """verify_model returns True when no signature exists."""
        model_path = tmp_path / "model.pkl"
        model_path.write_bytes(b"model content")
        
        # No signature file exists
        assert verify_model(model_path) is True


class TestUpdateManifestModel:
    """Tests for update_manifest_model function."""

    def test_updates_existing_manifest(self, tmp_path: Path) -> None:
        """update_manifest_model adds model field to existing manifest."""
        manifest = {"code": "0478", "name": "Test"}
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        
        update_manifest_model(manifest_path, "models/test.joblib")
        
        updated = json.loads(manifest_path.read_text())
        assert updated["model"] == "models/test.joblib"
        assert updated["code"] == "0478"  # Preserved existing fields

    def test_validates_after_update(self, tmp_path: Path) -> None:
        """Manifest with model field passes validation."""
        manifest = {"code": "0478", "name": "Test", "model": "models/test.joblib"}
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        
        result = validate_manifest(manifest_path)
        assert result.model == "models/test.joblib"
