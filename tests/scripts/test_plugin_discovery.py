"""Tests for plugin discovery with dynamic exam code detection.

This module tests plugin discovery, validation, and signature checking
using dynamically discovered exam codes rather than hardcoded values.
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from gcse_toolkit.plugins import (
    supported_exam_codes,
    list_exam_plugins,
    get_exam_plugin,
    default_exam_code,
    ExamPlugin,
    UnsupportedCodeError,
)
from gcse_toolkit.plugins.validation import (
    validate_manifest,
    sign_model,
    verify_model,
    ManifestValidationError,
)


class TestDynamicPluginDiscovery:
    """Tests that dynamically discover and validate installed plugins."""

    def test_at_least_one_plugin_discovered(self):
        """At least one plugin should be discovered in the environment."""
        codes = supported_exam_codes()
        assert len(codes) >= 1, "No plugins discovered"

    def test_all_discovered_codes_are_valid(self):
        """All discovered exam codes should be alphanumeric and reasonable length."""
        for code in supported_exam_codes():
            assert code.isalnum(), f"Code '{code}' is not alphanumeric"
            assert 1 <= len(code) <= 10, f"Code '{code}' has invalid length"

    def test_all_plugins_have_required_fields(self):
        """All discovered plugins have required fields populated."""
        for plugin in list_exam_plugins():
            assert isinstance(plugin, ExamPlugin)
            assert plugin.code, "Plugin missing code"
            assert plugin.name, "Plugin missing name"
            assert plugin.subtopics_path, "Plugin missing subtopics_path"

    def test_default_exam_code_is_valid(self):
        """Default exam code should be one of the discovered codes."""
        default = default_exam_code()
        assert default in supported_exam_codes()

    def test_get_plugin_returns_correct_plugin(self):
        """get_exam_plugin returns the correct plugin for each discovered code."""
        for code in supported_exam_codes():
            plugin = get_exam_plugin(code)
            assert plugin.code == code

    def test_get_plugin_with_none_returns_default(self):
        """get_exam_plugin(None) returns the default plugin."""
        plugin = get_exam_plugin(None)
        assert plugin.code == default_exam_code()

    def test_unsupported_code_raises_error(self):
        """Requesting an unsupported code raises UnsupportedCodeError."""
        with pytest.raises(UnsupportedCodeError):
            get_exam_plugin("INVALID_CODE_THAT_DOES_NOT_EXIST")


class TestPluginTopicResources:
    """Tests that plugin resources are properly structured."""

    @pytest.fixture
    def all_plugins(self):
        """Get all discovered plugins."""
        return list(list_exam_plugins())

    def test_all_plugins_have_subtopics_file(self, all_plugins):
        """All plugins should have their subtopics file present."""
        for plugin in all_plugins:
            subtopics_path = plugin.subtopics_path
            assert subtopics_path.exists(), \
                f"Plugin {plugin.code}: subtopics file not found at {subtopics_path}"

    def test_subtopics_files_are_valid_json(self, all_plugins):
        """All subtopics files should contain valid JSON."""
        for plugin in all_plugins:
            try:
                content = plugin.subtopics_path.read_text(encoding="utf-8")
                data = json.loads(content)
                assert isinstance(data, dict), f"Plugin {plugin.code}: subtopics should be a dict"
            except json.JSONDecodeError as e:
                pytest.fail(f"Plugin {plugin.code}: invalid JSON in subtopics - {e}")

    def test_subtopics_have_topics(self, all_plugins):
        """Subtopics files should contain topics or a valid structure."""
        for plugin in all_plugins:
            content = plugin.subtopics_path.read_text(encoding="utf-8")
            data = json.loads(content)
            # Different plugins may use different structures:
            # Some have "topics" key, others have topic names as keys
            topics = data.get("topics", [])
            if not topics:
                # Fallback: check if it's a dict with topic keys
                assert len(data) >= 1, f"Plugin {plugin.code}: no topic data found"


class TestPluginManifestIntegrity:
    """Tests manifest validation against real plugin manifests."""

    def test_all_installed_manifests_are_valid(self):
        """All installed plugin manifests should pass validation."""
        for plugin in list_exam_plugins():
            # Find the manifest path from subtopics_path (same directory)
            manifest_path = plugin.subtopics_path.parent / "manifest.json"
            if manifest_path.exists():
                result = validate_manifest(manifest_path)
                assert result.code == plugin.code
                assert result.name == plugin.name


class TestModelSignatureValidation:
    """Tests for model signing and verification."""

    def test_sign_and_verify_roundtrip(self, tmp_path: Path):
        """Signed model can be verified."""
        model_path = tmp_path / "model.joblib"
        model_path.write_bytes(b"fake model content for testing")
        
        sig_path = sign_model(model_path)
        assert sig_path.exists()
        assert verify_model(model_path) is True

    def test_tampered_model_fails_verification(self, tmp_path: Path):
        """Tampered model fails signature verification."""
        model_path = tmp_path / "model.joblib"
        model_path.write_bytes(b"original content")
        sign_model(model_path)
        
        # Tamper with model
        model_path.write_bytes(b"TAMPERED content")
        
        assert verify_model(model_path) is False

    def test_missing_signature_passes(self, tmp_path: Path):
        """Model without signature passes (signature is optional)."""
        model_path = tmp_path / "model.joblib"
        model_path.write_bytes(b"model without signature")
        
        # No signature file created
        assert verify_model(model_path) is True

    def test_signature_file_has_correct_format(self, tmp_path: Path):
        """Signature file contains valid SHA256 hex string."""
        model_path = tmp_path / "model.joblib"
        model_path.write_bytes(b"test content")
        
        sig_path = sign_model(model_path)
        sig_content = sig_path.read_text().strip()
        
        # SHA256 is 64 hex characters
        assert len(sig_content) == 64
        assert all(c in "0123456789abcdef" for c in sig_content)


class TestPluginOptionsLoading:
    """Tests for plugin options/overrides loading."""

    def test_all_plugins_load_options_without_error(self):
        """All plugins should load options without raising exceptions."""
        for plugin in list_exam_plugins():
            # options is a dict, may be empty
            assert isinstance(plugin.options, dict)


class TestExamResourcesLoading:
    """Tests for ExamResources functionality."""

    def test_load_resources_for_all_plugins(self):
        """ExamResources can be loaded for all discovered plugins."""
        from gcse_toolkit.plugins import load_exam_resources
        
        for code in supported_exam_codes():
            resources = load_exam_resources(code)
            assert resources is not None
            # ExamResources uses 'code' not 'exam_code'
            assert resources.code == code


class TestFaultyPluginHandling:
    """Tests for handling of faulty or malformed plugins."""

    def test_manifest_missing_code_rejected(self, tmp_path: Path):
        """Manifest without code field is rejected."""
        manifest = {"name": "Test Plugin"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        with pytest.raises(ManifestValidationError):
            validate_manifest(tmp_path / "manifest.json")

    def test_manifest_missing_name_rejected(self, tmp_path: Path):
        """Manifest without name field is rejected."""
        manifest = {"code": "TEST"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        with pytest.raises(ManifestValidationError):
            validate_manifest(tmp_path / "manifest.json")

    def test_manifest_with_path_traversal_code_rejected(self, tmp_path: Path):
        """Manifest with path traversal in code is rejected."""
        manifest = {"code": "../evil", "name": "Evil Plugin"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        with pytest.raises(ManifestValidationError, match="alphanumeric"):
            validate_manifest(tmp_path / "manifest.json")

    def test_manifest_invalid_json_rejected(self, tmp_path: Path):
        """Manifest with invalid JSON is rejected."""
        (tmp_path / "manifest.json").write_text("{not valid json")
        
        with pytest.raises(ManifestValidationError):
            validate_manifest(tmp_path / "manifest.json")

    def test_signature_missing_is_acceptable(self, tmp_path: Path):
        """Model without signature file is allowed (signature optional)."""
        model_path = tmp_path / "model.joblib"
        model_path.write_bytes(b"model content")
        
        # No signature file exists - should return True (allow by default)
        assert verify_model(model_path) is True

    def test_signature_corrupted_is_detected(self, tmp_path: Path):
        """Corrupted signature file fails verification."""
        model_path = tmp_path / "model.joblib"
        model_path.write_bytes(b"model content")
        
        # Create a bad signature (wrong hash)
        sig_path = tmp_path / "model.joblib.sha256"
        sig_path.write_text("0" * 64)  # Wrong hash
        
        assert verify_model(model_path) is False

    def test_empty_manifest_rejected(self, tmp_path: Path):
        """Empty manifest file is rejected."""
        (tmp_path / "manifest.json").write_text("{}")
        
        with pytest.raises(ManifestValidationError):
            validate_manifest(tmp_path / "manifest.json")


class TestBoardFieldValidation:
    """Tests for the optional board field in plugin manifests."""

    def test_valid_board_string_accepted(self, tmp_path: Path):
        """Manifest with valid board string is accepted."""
        manifest = {
            "code": "TEST",
            "name": "Test Plugin",
            "board": "Cambridge"
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        assert result.board == "Cambridge"

    def test_null_board_accepted(self, tmp_path: Path):
        """Manifest with null board is accepted (field is optional)."""
        manifest = {
            "code": "TEST",
            "name": "Test Plugin",
            "board": None
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        # Depending on implementation, might stay None or exclude it
        assert result.board is None

    def test_missing_board_accepted(self, tmp_path: Path):
        """Manifest without board field is accepted."""
        manifest = {
            "code": "TEST",
            "name": "Test Plugin"
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        assert result.board is None

    def test_invalid_board_type_rejected(self, tmp_path: Path):
        """Manifest with non-string board field is rejected."""
        manifest = {
            "code": "TEST",
            "name": "Test Plugin",
            "board": 123  # Not a string
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        with pytest.raises(ManifestValidationError, match="board must be a string"):
            validate_manifest(tmp_path / "manifest.json")

    def test_schema_version_3_accepted(self, tmp_path: Path):
        """Manifest with schema version 3 is accepted."""
        manifest = {
            "code": "TEST",
            "name": "Test Plugin",
            "manifest_schema_version": 3
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        assert result.manifest_schema_version == 3

