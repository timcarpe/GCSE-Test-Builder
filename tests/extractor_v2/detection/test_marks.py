"""
Tests for extractor_v2.detection.marks

Test Coverage:
- detect_mark_boxes(): Detection of [2], [3], etc. mark boxes
- MarkBox: y_center property

Note: Full testing requires PDF fixtures. These tests provide basic structure validation.
"""
import pytest
import fitz
from gcse_toolkit.extractor_v2.detection.marks import detect_mark_boxes, MarkBox


def test_detect_mark_boxes_returns_list():
    """Returns list of MarkBox."""
    # Requires PDF fixture
    pytest.skip("Requires PDF fixtures with known mark boxes")


def test_mark_box_dataclass():
    """MarkBox is a frozen dataclass."""
    # Arrange
    mark = MarkBox(
        value=5,
        y_position=200,
        bbox=(450, 200, 480, 220)
    )
    
    # Assert
    assert mark.value == 5
    assert mark.y_position == 200
    assert mark.bbox == (450, 200, 480, 220)
   
    # Should be frozen
    with pytest.raises(Exception):
        mark.value = 10


def test_mark_box_y_center():
    """y_center property calculates vertical center."""
    # Arrange
    mark = MarkBox(
        value=3,
        y_position=200,
        bbox=(450, 200, 480, 220)  # y_top=200, y_bottom=220
    )
    
    # Act
    center = mark.y_center
    
    # Assert
    assert center == 210  # (200 + 220) // 2


# Note: Complete testing requires PDF fixtures
# Additional tests should be added with sample PDFs containing known mark boxes
