"""
Tests for extractor_v2.detection.parts

Test Coverage:
- detect_part_labels(): Detection of (a), (b), (c) and (i), (ii), (iii) labels
- Edge cases: Nested parts, overlapping regions, malformed labels

Note: Full testing requires fixture PDFs. These tests provide basic structure validation.
"""
import pytest
import fitz
from gcse_toolkit.extractor_v2.detection.parts import detect_part_labels, PartLabel


def test_detect_part_labels_returns_tuple():
    """Returns tuple of (letters, romans)."""
    # Requires PDF fixture
    pytest.skip("Requires PDF fixtures with known parts")


def test_part_label_dataclass():
    """PartLabel is a frozen dataclass."""
    # Arrange
    label = PartLabel(
        label="a",
        kind="letter",
        y_position=120,
        bbox=(50, 120, 70, 140)
    )
    
    # Assert
    assert label.label == "a"
    assert label.kind == "letter"
    assert label.y_position == 120
    assert label.bbox == (50, 120, 70, 140)
    
    # Should be frozen
    with pytest.raises(Exception):
        label.label = "b"


def test_part_label_kinds():
    """PartLabel supports 'letter' and 'roman' kinds."""
    letter = PartLabel(label="a", kind="letter", y_position=100, bbox=(0, 100, 50, 120))
    roman = PartLabel(label="i", kind="roman", y_position=150, bbox=(0, 150, 50, 170))
    
    assert letter.kind == "letter"
    assert roman.kind == "roman"


# Note: Complete testing requires PDF fixtures
# Additional tests should be added with sample PDFs containing known part labels
