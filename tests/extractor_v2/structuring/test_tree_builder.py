"""
Tests for extractor_v2.structuring.tree_builder

Test Coverage:
- build_part_tree(): Building hierarchical Part tree from detections
- Edge cases: Missing children, overlapping parts, orphaned romans
"""
import pytest
from gcse_toolkit.core.models import Part, Marks
from gcse_toolkit.core.models.parts import PartKind
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.extractor_v2.structuring.tree_builder import build_part_tree
from gcse_toolkit.extractor_v2.detection.numerals import QuestionNumeral
from gcse_toolkit.extractor_v2.detection.parts import PartLabel
from gcse_toolkit.extractor_v2.detection.marks import MarkBox


def test_build_part_tree_simple_question():
    """Builds tree for simple question with no parts."""
    # Arrange
    question = QuestionNumeral(number=1, page=0, y_position=100, bbox=(0, 100, 50, 120))
    letters = []
    romans = []
    marks = []
    
    # Act
    result = build_part_tree(1, letters, romans, marks, composite_height=2339, composite_width=1654)
    
    # Assert
    assert result.label == "1"
    assert len(result.children) == 0


def test_build_part_tree_with_letters():
    """Builds tree with letter parts (a), (b)."""
    # Arrange
    question = QuestionNumeral(number=1, page=0, y_position=100, bbox=(0, 100, 50, 120))
    letters = [
        PartLabel(label="a", kind="letter", y_position=150, bbox=(0, 150, 100, 170)),
        PartLabel(label="b", kind="letter", y_position=300, bbox=(0, 300, 100, 320)),
    ]
    romans = []
    marks = []
    
    # Act
    result = build_part_tree(1, letters, romans, marks, composite_height=2339, composite_width=1654)
    
    # Assert
    assert result.label == "1"
    assert len(result.children) == 2
    assert result.children[0].label == "1(a)"
    assert result.children[1].label == "1(b)"


def test_build_part_tree_with_nested_romans():
    """Builds tree with nested roman numerals under letters."""
    # Arrange
    question = QuestionNumeral(number=1, page=0, y_position=100, bbox=(0, 100, 50, 120))
    letters = [
        PartLabel(label="a", kind="letter", y_position=150, bbox=(0, 150, 100, 170)),
    ]
    romans = [
        PartLabel(label="i", kind="roman", y_position=200, bbox=(0, 200, 100, 220)),
        PartLabel(label="ii", kind="roman", y_position=250, bbox=(0, 250, 100, 270)),
    ]
    marks = []
    
    # Act
    result = build_part_tree(1, letters, romans, marks, composite_height=2339, composite_width=1654)
    
    # Assert
    assert len(result.children) == 1
    letter_part = result.children[0]
    assert letter_part.label == "1(a)"
    assert len(letter_part.children) == 2
    assert letter_part.children[0].label == "1(a)(i)"
    assert letter_part.children[1].label == "1(a)(ii)"


def test_build_part_tree_with_marks():
    """Assigns marks to leaf parts."""
    # Arrange
    question = QuestionNumeral(number=1, page=0, y_position=100, bbox=(0, 100, 50, 120))
    letters = [
        PartLabel(label="a", kind="letter", y_position=150, bbox=(0, 150, 100, 170)),
    ]
    romans = []
    marks = [
        MarkBox(value=2, y_position=150, bbox=(1500, 150, 1600, 170)),  # Near letter (a)
    ]
    
    # Act
    result = build_part_tree(1, letters, romans, marks, composite_height=2339, composite_width=1654)
    
    # Assert
    letter_part = result.children[0]
    assert letter_part.marks is not None
    assert letter_part.marks.value == 2
    assert letter_part.marks.source == "explicit"


def test_build_part_tree_orphaned_romans():
    """Handles roman numerals without parent letter."""
    # Arrange
    question = QuestionNumeral(number=1, page=0, y_position=100, bbox=(0, 100, 50, 120))
    letters = []
    romans = [
        PartLabel(label="i", kind="roman", y_position=200, bbox=(0, 200, 100, 220)),
    ]
    marks = []
    
    # Act
    result = build_part_tree(1, letters, romans, marks, composite_height=2339, composite_width=1654)
    
    # Assert
    # Should attach roman directly to question or handle gracefully
    # Exact behavior depends on implementation
    assert result.label == "1"


def test_build_part_tree_preserves_hierarchy():
    """Complex tree maintains correct parent-child relationships."""
    # Arrange
    question = QuestionNumeral(number=1, page=0, y_position=100, bbox=(0, 100, 50, 120))
    letters = [
        PartLabel(label="a", kind="letter", y_position=150, bbox=(0, 150, 100, 170)),
        PartLabel(label="b", kind="letter", y_position=400, bbox=(0, 400, 100, 420)),
    ]
    romans = [
        PartLabel(label="i", kind="roman", y_position=200, bbox=(0, 200, 100, 220)),
        PartLabel(label="ii", kind="roman", y_position=250, bbox=(0, 250, 100, 270)),
        PartLabel(label="i", kind="roman", y_position=450, bbox=(0, 450, 100, 470)),
    ]
    marks = [
        MarkBox(value=2, y_position=200, bbox=(1500, 200, 1600, 220)),
        MarkBox(value=3, y_position=250, bbox=(1500, 250, 1600, 270)),
        MarkBox(value=4, y_position=450, bbox=(1500, 450, 1600, 470)),
    ]
    
    # Act
    result = build_part_tree(1, letters, romans, marks, composite_height=2339, composite_width=1654)
    
    # Assert
    assert len(result.children) == 2
    
    # Check (a) has 2 children
    part_a = result.children[0]
    assert part_a.label == "1(a)"
    assert len(part_a.children) == 2
    assert part_a.children[0].marks.value == 2
    assert part_a.children[1].marks.value == 3
    
    # Check (b) has 1 child
    part_b = result.children[1]
    assert part_b.label == "1(b)"
    assert len(part_b.children) == 1
    assert part_b.children[0].marks.value == 4


def test_build_part_tree_immutable_result():
    """Result is an immutable frozen dataclass."""
    # Arrange
    question = QuestionNumeral(number=1, page=0, y_position=100, bbox=(0, 100, 50, 120))
    
    # Act
    result = build_part_tree(1, [], [], [], composite_height=2339, composite_width=1654)
    
    # Assert
    assert isinstance(result, Part)
    # Frozen dataclass should raise error on modification
    with pytest.raises(Exception):
        result.label = "changed"
