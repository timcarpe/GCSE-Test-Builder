"""
Tests for extractor_v2.slicing.writer

Test Coverage:
- write_question(): Writing regions.json, metadata.json, composite.png
- Edge cases: Missing directories, invalid paths

NOTE: Production usage creates question_id subdirectory before calling write_question.
See pipeline.py line 304: question_dir = output_dir / question_id
"""

import pytest
from pathlib import Path
import json
import shutil
from gcse_toolkit.extractor_v2.slicing.writer import write_question
from gcse_toolkit.core.models import Part, SliceBounds, Marks
from gcse_toolkit.core.models.parts import PartKind
from PIL import Image


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create temporary output directory."""
    output_dir = tmp_path / "test_output"
    output_dir.mkdir()
    yield output_dir
    # Cleanup handled by tmp_path


@pytest.fixture
def sample_part_tree():
    """Create sample Part tree for testing."""
    return Part(
        label="1",
        kind=PartKind.QUESTION,
        marks=Marks.explicit(5),
        bounds=SliceBounds(left=0, top=0, right=1654, bottom=500),
        children=(
            Part(
                label="1(a)",
                kind=PartKind.LETTER,
                marks=Marks.explicit(5),
                bounds=SliceBounds(left=0, top=100, right=1654, bottom=300),
                children=()
            ),
        )
    )


@pytest.fixture
def sample_composite_image():
    """Create sample composite image."""
    return Image.new('RGB', (1654, 2339), color='white')


def test_write_question_creates_directories(temp_output_dir, sample_part_tree, sample_composite_image):
    """Creates output directories if they don't exist."""
    # Arrange
    question_id = "0478_m24_qp_12_q1"
    # Production pattern: create question_dir before calling write_question
    question_dir = temp_output_dir / "nonexistent" / question_id
    
    # Act
    bounds = {
        "1": sample_part_tree.bounds,
        "1(a)": sample_part_tree.children[0].bounds
    }
    result = write_question(
        question_id=question_id,
        composite=sample_composite_image,
        part_tree=sample_part_tree,
        bounds=bounds,
        output_dir=question_dir,  # Pass question-specific dir
        exam_code="0478"
    )
    
    # Assert
    assert result.exists()
    assert result.is_dir()
    assert (result / "composite.png").exists()


def test_write_question_saves_regions_json(temp_output_dir, sample_part_tree, sample_composite_image):
    """Saves regions.json with all part bounds."""
    # Arrange
    question_id = "0478_m24_qp_12_q1"
    question_dir = temp_output_dir / question_id
    
    # Act
    bounds = {
        "1": sample_part_tree.bounds,
        "1(a)": sample_part_tree.children[0].bounds
    }
    write_question(
        question_id=question_id,
        composite=sample_composite_image,
        part_tree=sample_part_tree,
        bounds=bounds,
        output_dir=question_dir,
        exam_code="0478"
    )
    
    # Assert
    regions_file = question_dir / "regions.json"
    assert regions_file.exists()
    
    with open(regions_file) as f:
        data = json.load(f)
    
    assert "regions" in data
    assert "1" in data["regions"]
    assert "1(a)" in data["regions"]


def test_write_question_includes_schema_version(temp_output_dir, sample_part_tree, sample_composite_image):
    """Saves regions.json with correct schema version."""
    # Arrange
    question_id = "0478_m24_qp_12_q1"
    question_dir = temp_output_dir / question_id
    
    # Act
    bounds = {
        "1": sample_part_tree.bounds,
        "1(a)": sample_part_tree.children[0].bounds
    }
    write_question(
        question_id=question_id,
        composite=sample_composite_image,
        part_tree=sample_part_tree,
        bounds=bounds,
        output_dir=question_dir,
        exam_code="0478"
    )
    
    # Assert
    regions_file = question_dir / "regions.json"
    with open(regions_file) as f:
        data = json.load(f)
    
    # Should have schema version 3 (added validation fields)
    assert data.get("schema_version") == 3
    assert "question_id" in data
    assert data["question_id"] == question_id


def test_write_question_saves_composite_png(temp_output_dir, sample_part_tree, sample_composite_image):
    """Saves composite.png image."""
    # Arrange
    question_id = "0478_m24_qp_12_q1"
    question_dir = temp_output_dir / question_id
    
    # Act
    bounds = {
        "1": sample_part_tree.bounds,
        "1(a)": sample_part_tree.children[0].bounds
    }
    write_question(
        question_id=question_id,
        composite=sample_composite_image,
        part_tree=sample_part_tree,
        bounds=bounds,
        output_dir=question_dir,
        exam_code="0478"
    )
    
    # Assert
    composite_file = question_dir / "composite.png"
    assert composite_file.exists()
    
    # Verify it's a valid image
    img = Image.open(composite_file)
    assert img.size == (1654, 2339)


def test_write_question_overwrites_existing(temp_output_dir, sample_part_tree, sample_composite_image):
    """Overwrites existing output if present."""
    # Arrange
    question_id = "0478_m24_qp_12_q1"
    question_dir = temp_output_dir / question_id
    question_dir.mkdir()
    
    # Create dummy existing file
    (question_dir / "regions.json").write_text('{"old": "data"}')
    
    # Act
    bounds = {
        "1": sample_part_tree.bounds,
        "1(a)": sample_part_tree.children[0].bounds
    }
    write_question(
        question_id=question_id,
        composite=sample_composite_image,
        part_tree=sample_part_tree,
        bounds=bounds,
        output_dir=question_dir,
        exam_code="0478"
    )
    
    # Assert
    regions_file = question_dir / "regions.json"
    with open(regions_file) as f:
        data = json.load(f)
    
    assert "old" not in data  # Old data replaced
    assert "regions" in data  # New data present
