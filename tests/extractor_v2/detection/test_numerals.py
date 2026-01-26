"""
Tests for extractor_v2.detection.numerals

Test Coverage:
- detect_question_numerals(): Question number detection (1, 2, 3...)
- Edge cases: Empty documents, malformed PDFs

Note: Full testing requires fixture PDFs with known question numbers.
These tests provide basic structure validation.
"""
import pytest
import fitz
from gcse_toolkit.extractor_v2.detection.numerals import detect_question_numerals, QuestionNumeral


def test_detect_question_numerals_returns_list():
    """Returns list of QuestionNumeral."""
    # This test requires actual PDF fixture
    # For now, just test the interface exists
    pytest.skip("Requires PDF fixtures with known question numbers")


def test_detect_question_numerals_empty_document_raises():
    """Raises ValueError for empty document."""
    # Create empty PDF
    doc = fitz.open()
    
    # Act & Assert
    with pytest.raises(ValueError, match="no pages"):
        detect_question_numerals(doc)


def test_detect_question_numerals_closed_document_raises():
    """Raises ValueError for closed document."""
    # Create and close document
    doc = fitz.open()
    doc.close()
    
    # Act & Assert
    with pytest.raises(ValueError, match="closed"):
        detect_question_numerals(doc)


def test_question_numeral_dataclass():
    """QuestionNumeral is a frozen dataclass."""
    # Arrange
    numeral = QuestionNumeral(
        number=1,
        page=0,
        y_position=150.5,
        bbox=(50, 150, 70, 170),
        text="1",
        is_pseudocode=False
    )
    
    # Assert
    assert numeral.number == 1
    assert numeral.page == 0
    assert numeral.y_position == 150.5
    assert numeral.bbox == (50, 150, 70, 170)
    
    # Should be frozen
    with pytest.raises(Exception):
        numeral.number = 2


# Note: Complete testing requires PDF fixtures
# Additional tests should be added with sample PDFs containing known questions
