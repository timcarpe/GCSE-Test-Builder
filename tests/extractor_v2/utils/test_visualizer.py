"""
Tests for extractor_v2.utils.visualizer

Test Coverage:
- save_debug_composite(): Directory creation and image saving
"""

import pytest
from pathlib import Path
from PIL import Image

from gcse_toolkit.extractor_v2.utils.visualizer import (
    save_debug_composite,
    visualize_detections,
)


@pytest.fixture
def sample_composite():
    """Create a sample composite image for testing."""
    return Image.new('RGB', (800, 1200), color='white')


def test_save_debug_composite_creates_directory(tmp_path, sample_composite):
    """save_debug_composite creates output directory if it doesn't exist."""
    # Arrange - nested directory that doesn't exist
    output_dir = tmp_path / "nested" / "deep" / "question_dir"
    assert not output_dir.exists()
    
    # Act
    result = save_debug_composite(
        composite=sample_composite,
        output_dir=output_dir,
        question_id="test_q1",
        numeral=None,
        letters=[],
        romans=[],
        marks=[],
    )
    
    # Assert
    assert output_dir.exists()
    assert result.exists()
    assert result.name == "test_q1_debug_composite.png"


def test_save_debug_composite_works_with_existing_directory(tmp_path, sample_composite):
    """save_debug_composite works when directory already exists."""
    # Arrange
    output_dir = tmp_path / "existing_dir"
    output_dir.mkdir()
    
    # Act
    result = save_debug_composite(
        composite=sample_composite,
        output_dir=output_dir,
        question_id="test_q2",
        numeral=None,
        letters=[],
        romans=[],
        marks=[],
    )
    
    # Assert
    assert result.exists()
    assert result.name == "test_q2_debug_composite.png"


def test_visualize_detections_returns_rgb_image(sample_composite):
    """visualize_detections returns an RGB image."""
    # Act
    result = visualize_detections(
        composite=sample_composite,
        numeral=None,
        letters=[],
        romans=[],
        marks=[],
    )
    
    # Assert
    assert result.mode == "RGB"
    assert result.size == sample_composite.size
