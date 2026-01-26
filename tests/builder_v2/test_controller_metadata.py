"""
Unit tests for controller metadata helpers.

Tests the metadata generation and writing functionality added in Phase 7.

Verified: 2025-12-15
"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from gcse_toolkit.builder_v2.controller import (
    _build_metadata,
    _write_metadata,
    build_exam,
    BuildError,
    BuilderConfig,
)
from gcse_toolkit.core.models.selection import SelectionResult


class TestBuildMetadata:
    """Tests for _build_metadata() helper."""

    def test_build_metadata_contains_required_fields(self):
        """Metadata should contain all required fields."""
        # Arrange
        from gcse_toolkit.core.models.selection import SelectionPlan
        from gcse_toolkit.builder_v2.layout import LayoutResult, PagePlan
        
        config = BuilderConfig(
            cache_path=Path("/fake/cache"),
            exam_code="0478",
            target_marks=40,
            tolerance=2,
            seed=12345,
        )
        
        # SelectionResult requires plans, target_marks, tolerance
        selection = SelectionResult(plans=tuple(), target_marks=40, tolerance=2)
        
        # LayoutResult requires pages and warnings
        layout = LayoutResult(
            pages=tuple(),
            warnings=tuple(),
        )
        
        # Act
        metadata = _build_metadata(config, selection, layout)
        
        # Assert - Required fields
        assert "generated_at" in metadata
        assert "exam_code" in metadata
        assert "target_marks" in metadata
        assert "actual_marks" in metadata
        assert "tolerance" in metadata
        assert "seed" in metadata
        assert "question_count" in metadata
        assert "page_count" in metadata
        assert "builder_version" in metadata

    def test_build_metadata_includes_config_values(self):
        """Metadata should include values from config."""
        # Arrange
        from gcse_toolkit.builder_v2.layout import LayoutResult
        
        config = BuilderConfig(
            cache_path=Path("/fake/cache"),
            exam_code="0620",
            target_marks=50,
            tolerance=3,
            seed=99999,
            topics={"Algorithms", "Data Structures"},
            years={2023, 2024},
            papers={1, 2},
            include_markscheme=True,
            keyword_mode=True,
        )
        
        selection = SelectionResult(plans=tuple(), target_marks=50, tolerance=3)
        layout = LayoutResult(pages=tuple(), warnings=tuple())
        
        # Act
        metadata = _build_metadata(config, selection, layout)
        
        # Assert
        assert metadata["exam_code"] == "0620"
        assert metadata["target_marks"] == 50
        assert metadata["actual_marks"] == 0  # Empty plans = 0 marks
        assert metadata["tolerance"] == 3
        assert metadata["seed"] == 99999
        assert metadata["page_count"] == 0  # Empty pages
        assert set(metadata["topics"]) == {"Algorithms", "Data Structures"}
        assert set(metadata["years"]) == {2023, 2024}
        assert set(metadata["papers"]) == {1, 2}
        assert metadata["include_markscheme"] is True
        assert metadata["keyword_mode"] is True
        assert metadata["builder_version"] == "v2"

    def test_build_metadata_includes_timestamp(self):
        """Metadata should include ISO format timestamp."""
        # Arrange
        from gcse_toolkit.builder_v2.layout import LayoutResult
        
        config = BuilderConfig(
            cache_path=Path("/fake/cache"),
            exam_code="0478",
            target_marks=40,
        )
        selection = SelectionResult(plans=tuple(), target_marks=40, tolerance=2)
        layout = LayoutResult(pages=tuple(), warnings=tuple())
        
        # Act
        before = datetime.now()
        metadata = _build_metadata(config, selection, layout)
        after = datetime.now()
        
        # Assert
        assert "generated_at" in metadata
        timestamp = datetime.fromisoformat(metadata["generated_at"])
        assert before <= timestamp <= after

    def test_build_metadata_handles_none_optional_fields(self):
        """Metadata should handle None for optional fields."""
        # Arrange
        from gcse_toolkit.builder_v2.layout import LayoutResult
        
        config = BuilderConfig(
            cache_path=Path("/fake/cache"),
            exam_code="0478",
            target_marks=40,
            # topics, years, papers not specified
        )
        selection = SelectionResult(plans=tuple(), target_marks=40, tolerance=2)
        layout = LayoutResult(pages=tuple(), warnings=tuple())
        
        # Act
        metadata = _build_metadata(config, selection, layout)
        
        # Assert
        assert metadata["papers"] is None

    def test_build_metadata_includes_expanded_fields(self):
        """Metadata should include stats, selection_details, and manifest."""
        # Arrange
        from gcse_toolkit.builder_v2.layout import LayoutResult, PagePlan, SlicePlacement, SliceAsset
        from gcse_toolkit.core.models import Question, Part
        from gcse_toolkit.core.models.selection import SelectionResult, SelectionPlan
        from unittest.mock import MagicMock
        
        # 1. Create a dummy selection with 1 question
        q_mock = MagicMock(spec=Question)
        q_mock.id = "s21_qp12_q1"
        q_mock.topic = "Hardware"
        q_mock.total_marks = 10
        # Create a mock for question_node since it's a data field
        q_mock.question_node = MagicMock(spec=Part)
        q_mock.question_node.label = "1"
        
        # Create a plan
        plan_mock = MagicMock(spec=SelectionPlan)
        plan_mock.question = q_mock
        plan_mock.marks = 5
        # Create mocks for leaves with proper values
        leaf_1 = MagicMock(spec=Part)
        leaf_1.label = "1(a)"
        leaf_1.topic = "Hardware"
        leaf_1.marks.value = 2
        
        leaf_2 = MagicMock(spec=Part)
        leaf_2.label = "1(b)"
        leaf_2.topic = None # Should fallback to question topic
        leaf_2.marks.value = 3
        
        plan_mock.included_leaves = [leaf_1, leaf_2]
        plan_mock.included_parts = frozenset(["1(a)", "1(b)"])
        plan_mock.is_full_question = False
        
        selection = SelectionResult(plans=(plan_mock,), target_marks=10, tolerance=0)
        
        # 2. Create a dummy layout
        asset = SliceAsset(
            question_id="s21_qp12_q1",
            part_label="1(a)",
            image=None,
            width=100, height=50,
            marks=2,
            is_text_header=False
        )
        placement = SlicePlacement(asset=asset, top=0)
        page = PagePlan(index=0, placements=(placement,), height_used=50)
        layout = LayoutResult(pages=(page,), warnings=[])
        
        # 3. Config
        config = BuilderConfig(
            cache_path=Path("/fake"),
            exam_code="0478",
            target_marks=10,
            topics={"Hardware"},
            export_zip=True, # Enable zip to test manifest
        )
        
        # Act
        metadata = _build_metadata(config, selection, layout)
        
        # Assert - Stats
        assert "stats" in metadata
        assert metadata["stats"]["marks_per_topic"] == {"Hardware": 5}
        assert metadata["stats"]["parts_per_topic"] == {"Hardware": 2} # 2 leaves
        
        # Assert - Selection Details
        assert "selection_details" in metadata
        details = metadata["selection_details"][0]
        assert details["question_id"] == "s21_qp12_q1"
        assert details["topic"] == "Hardware"
        assert details["selected_marks"] == 5
        assert details["status"] == "partial"
        assert {p["label"] for p in details["included_parts"]} == {"1(a)", "1(b)"}
        assert details["included_parts"][0]["marks"] == 2
        assert details["included_parts"][1]["marks"] == 3
        
        # Assert - Manifest
        assert "manifest" in metadata
        # PDF
        pdf_manifest = metadata["manifest"]["questions_pdf"]
        assert len(pdf_manifest) == 1
        assert pdf_manifest[0]["question_id"] == "s21_qp12_q1"
        assert pdf_manifest[0]["part_label"] == "1(a)"
        assert pdf_manifest[0]["page"] == 1
        
        # ZIP (predictive)
        zip_manifest = metadata["manifest"]["zip_export"]
        assert "README.txt" in zip_manifest
        assert "1/1(a).png" in zip_manifest
        assert "1/1(b).png" in zip_manifest


class TestWriteMetadata:
    """Tests for _write_metadata() helper."""

    def test_write_metadata_creates_json_file(self, tmp_path):
        """Should create build_metadata.json file."""
        # Arrange
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        metadata = {
            "generated_at": "2025-12-15T10:00:00",
            "exam_code": "0478",
            "target_marks": 40,
            "builder_version": "v2",
        }
        
        # Act
        _write_metadata(output_dir, metadata)
        
        # Assert
        metadata_path = output_dir / "build_metadata.json"
        assert metadata_path.exists()
        
        # Verify contents
        with open(metadata_path) as f:
            loaded = json.load(f)
        assert loaded == metadata

    def test_write_metadata_formats_with_indentation(self, tmp_path):
        """Should write formatted JSON with indentation."""
        # Arrange
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        metadata = {"exam_code": "0478", "target_marks": 40}
        
        # Act
        _write_metadata(output_dir, metadata)
        
        # Assert
        metadata_path = output_dir / "build_metadata.json"
        content = metadata_path.read_text()
        
        # Should be formatted (contains newlines and spaces)
        assert "\n" in content
        assert "  " in content  # indent=2

    def test_write_metadata_raises_on_permission_error(self, tmp_path):
        """Should raise BuildError on write failure."""
        # Arrange
        output_dir = tmp_path / "nonexistent"
        # Don't create directory
        
        metadata = {"exam_code": "0478"}
        
        # Act & Assert
        with pytest.raises(BuildError, match="Failed to write metadata"):
            _write_metadata(output_dir, metadata)


class TestBuildExamMetadataIntegration:
    """Integration tests for metadata in build_exam()."""

    def test_build_exam_includes_metadata_in_result(self, tmp_path):
        """BuildResult should include metadata dict."""
        # This test requires a valid cache, skip if not available
        pytest.skip("Requires valid cache - tested in E2E")

    def test_build_exam_writes_metadata_file(self, tmp_path):
        """build_exam() should write build_metadata.json."""
        # This test requires a valid cache, skip if not available
        pytest.skip("Requires valid cache - tested in E2E")
