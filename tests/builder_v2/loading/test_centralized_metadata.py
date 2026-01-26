"""
Unit tests for centralized metadata system.

Tests metadata writing (extractor) and reading (loader).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from gcse_toolkit.extractor_v2.pipeline import _write_centralized_metadata
from gcse_toolkit.builder_v2.loading.loader import (
    _discover_from_metadata,
    discover_questions,
    LoaderError,
)


# ─────────────────────────────────────────────────────────────────────────────
# Metadata Writing Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_write_centralized_metadata_creates_file(tmp_path: Path):
    """Verify metadata file is created with correct structure."""
    # Arrange
    exam_code = "0478"
    metadata_records = [
        {
            "schema_version": 7,
            "question_id": "0478_s24_qp_12_q1",
            "exam_code": "0478",
            "year": 2024,
            "paper": 1,
            "variant": 2,
            "question_number": 1,
            "total_marks": 5,
            "part_count": 3,
            "topic": "01. Data representation",
            "relative_path": "0478/01. Data representation/0478_s24_qp_12_q1",
            "content_right": 450,
            "numeral_bbox": [10, 20, 30, 40],
            "root_text": "Convert to binary",
            "child_text": {"(a)": "Show working"},
            "mark_bboxes": [[400, 50, 420, 70]],
            "markscheme_path": "ms_1.png",
        },
        {
            "schema_version": 7,
            "question_id": "0478_s24_qp_12_q2",
            "exam_code": "0478",
            "year": 2024,
            "paper": 1,
            "variant": 2,
            "question_number": 2,
            "total_marks": 8,
            "part_count": 2,
            "topic": "02. Communication",
            "relative_path": "0478/02. Communication/0478_s24_qp_12_q2",
            "content_right": 460,
            "numeral_bbox": None,
            "root_text": "Describe protocols",
            "child_text": {},
            "mark_bboxes": [],
            "markscheme_path": None,
        },
    ]
    
    # Act
    _write_centralized_metadata(tmp_path, exam_code, metadata_records)
    
    # Assert
    metadata_path = tmp_path / "0478" / "_metadata" / "questions.jsonl"
    assert metadata_path.exists(), "Metadata file should be created"
    
    # Verify JSONL format
    with metadata_path.open("r") as f:
        lines = f.readlines()
    
    assert len(lines) == 2, "Should have 2 records"
    
    # Parse and verify each record
    record1 = json.loads(lines[0])
    assert record1["question_id"] == "0478_s24_qp_12_q1"
    assert record1["relative_path"] == "0478/01. Data representation/0478_s24_qp_12_q1"
    
    record2 = json.loads(lines[1])
    assert record2["question_id"] == "0478_s24_qp_12_q2"
    assert record2["markscheme_path"] is None


def test_write_centralized_metadata_empty_list(tmp_path: Path):
    """Empty metadata list should not create file."""
    # Arrange
    exam_code = "0478"
    metadata_records: List[Dict[str, Any]] = []
    
    # Act
    _write_centralized_metadata(tmp_path, exam_code, metadata_records)
    
    # Assert
    metadata_path = tmp_path / "0478" / "_metadata" / "questions.jsonl"
    assert not metadata_path.exists(), "Should not create file for empty list"


def test_write_centralized_metadata_appends_to_existing(tmp_path: Path):
    """Writing metadata should append to existing file (parallel-safe behavior)."""
    # Arrange
    exam_code = "0478"
    metadata_path = tmp_path / "0478" / "_metadata" / "questions.jsonl"
    metadata_path.parent.mkdir(parents=True)
    metadata_path.write_text("old content\n")
    
    new_records = [
        {
            "schema_version": 7,
            "question_id": "new_question",
            "exam_code": "0478",
            "relative_path": "0478/Topic/new_question",
        }
    ]
    
    # Act
    _write_centralized_metadata(tmp_path, exam_code, new_records)
    
    # Assert
    content = metadata_path.read_text()
    assert "old content" in content, "Old content should be preserved (appended)"
    assert "new_question" in content, "New content should be appended"


# ─────────────────────────────────────────────────────────────────────────────
# Metadata Reading Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_discover_from_metadata_finds_questions(tmp_path: Path):
    """Discover questions from metadata file."""
    # Arrange
    exam_code = "0478"
    
    # Create question directories
    q1_dir = tmp_path / "0478" / "01. Data" / "0478_s24_qp_12_q1"
    q2_dir = tmp_path / "0478" / "02. Comms" / "0478_s24_qp_12_q2"
    q1_dir.mkdir(parents=True)
    q2_dir.mkdir(parents=True)
    (q1_dir / "regions.json").write_text("{}")
    (q2_dir / "regions.json").write_text("{}")
    
    # Create metadata file
    metadata_path = tmp_path / "0478" / "_metadata" / "questions.jsonl"
    metadata_path.parent.mkdir(parents=True)
    
    with metadata_path.open("w") as f:
        f.write(json.dumps({
            "question_id": "q1",
            "relative_path": "0478/01. Data/0478_s24_qp_12_q1"
        }) + "\n")
        f.write(json.dumps({
            "question_id": "q2",
            "relative_path": "0478/02. Comms/0478_s24_qp_12_q2"
        }) + "\n")
    
    # Act
    dirs = _discover_from_metadata(tmp_path, metadata_path)
    
    # Assert
    assert len(dirs) == 2
    assert dirs[0].name == "0478_s24_qp_12_q1"
    assert dirs[1].name == "0478_s24_qp_12_q2"


def test_discover_from_metadata_skips_missing_directories(tmp_path: Path):
    """Missing directories should be skipped."""
    # Arrange
    metadata_path = tmp_path / "0478" / "_metadata" / "questions.jsonl"
    metadata_path.parent.mkdir(parents=True)
    
    # Only create first directory
    q1_dir = tmp_path / "0478" / "Topic" / "q1"
    q1_dir.mkdir(parents=True)
    (q1_dir / "regions.json").write_text("{}")
    
    # Metadata references two questions, but only first exists
    with metadata_path.open("w") as f:
        f.write(json.dumps({"question_id": "q1", "relative_path": "0478/Topic/q1"}) + "\n")
        f.write(json.dumps({"question_id": "q2", "relative_path": "0478/Topic/q2"}) + "\n")
    
    # Act
    dirs = _discover_from_metadata(tmp_path, metadata_path)
    
    # Assert
    assert len(dirs) == 1, "Should skip missing directory"
    assert dirs[0].name == "q1"


def test_discover_from_metadata_handles_invalid_json(tmp_path: Path):
    """Invalid JSON lines should be skipped with warning."""
    # Arrange
    metadata_path = tmp_path / "0478" / "_metadata" / "questions.jsonl"
    metadata_path.parent.mkdir(parents=True)
    
    q_dir = tmp_path / "0478" / "Topic" / "q1"
    q_dir.mkdir(parents=True)
    (q_dir / "regions.json").write_text("{}")
    
    # Mix valid and invalid JSON
    with metadata_path.open("w") as f:
        f.write(json.dumps({"question_id": "q1", "relative_path": "0478/Topic/q1"}) + "\n")
        f.write("{ invalid json }\n")  # Bad line
        f.write("\n")  # Empty line
    
    # Act
    dirs = _discover_from_metadata(tmp_path, metadata_path)
    
    # Assert
    assert len(dirs) == 1, "Should skip invalid JSON"
    assert dirs[0].name == "q1"


def test_discover_questions_raises_when_no_metadata(tmp_path: Path):
    """Should raise LoaderError if metadata file missing."""
    # Arrange
    exam_code = "0478"
    
    # Act & Assert
    with pytest.raises(LoaderError, match="Metadata file not found"):
        discover_questions(tmp_path, exam_code)


def test_discover_questions_uses_metadata_when_exists(tmp_path: Path):
    """Should use metadata file when it exists."""
    # Arrange
    exam_code = "0478"
    
    q_dir = tmp_path / "0478" / "Topic" / "q1"
    q_dir.mkdir(parents=True)
    (q_dir / "regions.json").write_text("{}")
    
    metadata_path = tmp_path / "0478" / "_metadata" / "questions.jsonl"
    metadata_path.parent.mkdir(parents=True)
    
    with metadata_path.open("w") as f:
        f.write(json.dumps({"question_id": "q1", "relative_path": "0478/Topic/q1"}) + "\n")
    
    # Act
    dirs = discover_questions(tmp_path, exam_code)
    
    # Assert
    assert len(dirs) == 1
    assert dirs[0].name == "q1"


def test_discover_from_metadata_sorts_by_name(tmp_path: Path):
    """Results should be sorted by directory name."""
    # Arrange
    metadata_path = tmp_path / "0478" / "_metadata" / "questions.jsonl"
    metadata_path.parent.mkdir(parents=True)
    
    # Create in reverse order
    for qid in ["q3", "q1", "q2"]:
        q_dir = tmp_path / "0478" / "Topic" / qid
        q_dir.mkdir(parents=True)
        (q_dir / "regions.json").write_text("{}")
    
    # Write metadata in random order
    with metadata_path.open("w") as f:
        for qid in ["q3", "q1", "q2"]:
            f.write(json.dumps({"question_id": qid, "relative_path": f"0478/Topic/{qid}"}) + "\n")
    
    # Act
    dirs = _discover_from_metadata(tmp_path, metadata_path)
    
    # Assert
    assert [d.name for d in dirs] == ["q1", "q2", "q3"], "Should be sorted"
