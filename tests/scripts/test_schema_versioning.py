"""Unit tests for schema versioning and supported_years features."""

import json
import logging
import pytest
from pathlib import Path
from unittest.mock import patch

from gcse_toolkit.plugins.validation import (
    validate_manifest,
    ManifestValidationError,
    ValidatedManifest,
    MANIFEST_SCHEMA_VERSION,
)
from gcse_toolkit.core.schemas.validator import QUESTION_SCHEMA_VERSION


class TestManifestSchemaVersion:
    """Tests for manifest schema version handling."""

    def test_manifest_schema_version_constant_is_integer(self) -> None:
        """MANIFEST_SCHEMA_VERSION should be an integer."""
        assert isinstance(MANIFEST_SCHEMA_VERSION, int)
        assert MANIFEST_SCHEMA_VERSION >= 1

    def test_metadata_schema_version_constant_is_integer(self) -> None:
        """QUESTION_SCHEMA_VERSION should be an integer."""
        assert isinstance(QUESTION_SCHEMA_VERSION, int)
        assert QUESTION_SCHEMA_VERSION >= 1

    def test_parses_manifest_schema_version_as_integer(self, tmp_path: Path) -> None:
        """manifest_schema_version is parsed as integer."""
        manifest = {
            "code": "0478",
            "name": "Test",
            "manifest_schema_version": 2,
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        
        assert result.manifest_schema_version == 2
        assert isinstance(result.manifest_schema_version, int)

    def test_parses_legacy_string_schema_version(self, tmp_path: Path) -> None:
        """Legacy schema_version string is converted to integer."""
        manifest = {
            "code": "0478",
            "name": "Test",
            "schema_version": "1.1",  # Old string format
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        
        # "1.1" -> removes "." -> "11" -> int(11)
        assert isinstance(result.manifest_schema_version, int)

    def test_defaults_to_version_1_when_missing(self, tmp_path: Path) -> None:
        """Missing schema version defaults to 1."""
        manifest = {"code": "0478", "name": "Test"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        
        assert result.manifest_schema_version == 1

    def test_logs_warning_for_old_manifest(self, tmp_path: Path, caplog) -> None:
        """Soft warning logged when manifest version is behind expected."""
        manifest = {
            "code": "0478",
            "name": "Test",
            "manifest_schema_version": 1,  # Behind current
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        with caplog.at_level(logging.WARNING):
            validate_manifest(tmp_path / "manifest.json")
        
        # Should have logged a warning about outdated version
        assert any("manifest_schema_version" in record.message for record in caplog.records)

    def test_no_warning_for_current_version(self, tmp_path: Path, caplog) -> None:
        """No warning when manifest version matches expected."""
        manifest = {
            "code": "0478",
            "name": "Test",
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        with caplog.at_level(logging.WARNING):
            validate_manifest(tmp_path / "manifest.json")
        
        # Should not have logged a warning
        version_warnings = [r for r in caplog.records if "manifest_schema_version" in r.message]
        assert len(version_warnings) == 0

    def test_no_warning_for_newer_version(self, tmp_path: Path, caplog) -> None:
        """No warning when manifest version is ahead (backward compatible)."""
        manifest = {
            "code": "0478",
            "name": "Test",
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION + 10,  # Future version
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        with caplog.at_level(logging.WARNING):
            validate_manifest(tmp_path / "manifest.json")
        
        # Should not have logged a warning for newer version
        version_warnings = [r for r in caplog.records if "manifest_schema_version" in r.message]
        assert len(version_warnings) == 0


class TestSupportedYears:
    """Tests for supported_years field in manifests."""

    def test_parses_supported_years_list(self, tmp_path: Path) -> None:
        """supported_years is parsed as list of strings."""
        manifest = {
            "code": "0478",
            "name": "Test",
            "supported_years": ["2022", "2023", "2024"],
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        
        assert result.supported_years == ["2022", "2023", "2024"]

    def test_defaults_to_empty_list(self, tmp_path: Path) -> None:
        """Missing supported_years defaults to empty list."""
        manifest = {"code": "0478", "name": "Test"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        
        assert result.supported_years == []

    def test_converts_integer_years_to_strings(self, tmp_path: Path) -> None:
        """Integer years are converted to strings."""
        manifest = {
            "code": "0478",
            "name": "Test",
            "supported_years": [2022, 2023, 2024],  # Integers
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        
        assert result.supported_years == ["2022", "2023", "2024"]

    def test_handles_invalid_supported_years_gracefully(self, tmp_path: Path) -> None:
        """Invalid supported_years format doesn't crash."""
        manifest = {
            "code": "0478",
            "name": "Test",
            "supported_years": "invalid",  # Not a list
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        
        result = validate_manifest(tmp_path / "manifest.json")
        
        # Should fallback to empty list
        assert result.supported_years == []


class TestYearExtraction:
    """Tests for year extraction from PDF filenames."""

    def test_extract_year_from_may_session(self) -> None:
        """m20 extracts to 2020."""
        from gcse_toolkit.extractor_v2.pipeline import _extract_year
        
        assert _extract_year("m20") == 2020
        assert _extract_year("m19") == 2019
        assert _extract_year("m21") == 2021

    def test_extract_year_from_summer_session(self) -> None:
        """s21 extracts to 2021."""
        from gcse_toolkit.extractor_v2.pipeline import _extract_year
        
        assert _extract_year("s21") == 2021
        assert _extract_year("s22") == 2022

    def test_extract_year_from_winter_session(self) -> None:
        """w19 extracts to 2019."""
        from gcse_toolkit.extractor_v2.pipeline import _extract_year
        
        assert _extract_year("w19") == 2019
        assert _extract_year("w23") == 2023

    def test_extract_year_case_insensitive(self) -> None:
        """Year extraction is case-insensitive."""
        from gcse_toolkit.extractor_v2.pipeline import _extract_year
        
        assert _extract_year("M20") == 2020
        assert _extract_year("S21") == 2021
        assert _extract_year("W19") == 2019

    def test_extract_year_returns_none_for_invalid(self) -> None:
        """Invalid series returns fallback (2024)."""
        from gcse_toolkit.extractor_v2.pipeline import _extract_year
        
        assert _extract_year("invalid") == 2024
        assert _extract_year("") == 2024
        assert _extract_year("x20") == 2024

    def test_extract_year_handles_old_years(self) -> None:
        """Years 51-99 map to 1900s."""
        from gcse_toolkit.extractor_v2.pipeline import _extract_year
        
        assert _extract_year("m99") == 1999
        assert _extract_year("s51") == 1951


class TestPluginYearsIntegration:
    """Integration tests for plugin years feature."""

    def test_bundled_plugins_have_supported_years(self) -> None:
        """All bundled plugins should have supported_years field."""
        from gcse_toolkit.plugins import list_exam_plugins
        
        plugins = list(list_exam_plugins())
        assert len(plugins) >= 1
        
        for plugin in plugins:
            assert hasattr(plugin, 'supported_years')
            assert isinstance(plugin.supported_years, list)

    def test_plugin_supported_years_are_strings(self) -> None:
        """Plugin supported_years should be list of string years."""
        from gcse_toolkit.plugins import list_exam_plugins
        
        plugins = list(list_exam_plugins())
        
        for plugin in plugins:
            for year in plugin.supported_years:
                assert isinstance(year, str)
                # Should be 4-digit year
                assert len(year) == 4
                assert year.isdigit()
