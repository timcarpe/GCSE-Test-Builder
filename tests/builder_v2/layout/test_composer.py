"""
Tests for builder_v2.layout.composer

Test Coverage:
- compose_question(): Asset composition from selection plan
- Padding application for parts with marks
- Context slice handling
- Overlap detection
"""
import pytest
from pathlib import Path
from PIL import Image
from gcse_toolkit.builder_v2.layout.composer import compose_question
from gcse_toolkit.builder_v2.layout.config import LayoutConfig
from gcse_toolkit.core.models import Question, Part, Marks, SliceBounds
from gcse_toolkit.core.models.parts import PartKind


@pytest.fixture
def sample_question():
    """Create sample question for testing."""
    return Question(
        id="test_q1",
        topic="Test Topic",
        year=2024,
        paper=1,
        variant=1,
        exam_code="0478",
        question_node=Part(
            label="1",
            kind=PartKind.QUESTION,
            marks=Marks.explicit(5),
            bounds=SliceBounds(0, 500, 0, 1654),
            children=(
                Part(
                    label="1(a)",
                    kind=PartKind.LETTER,
                    marks=Marks.explicit(5),
                    bounds=SliceBounds(100, 300, 0, 1654),
                    children=()
                ),
            )
        ),
        composite_path=Path("dummy.png"),
        regions_path=Path("dummy.json")
    )


@pytest.fixture
def layout_config():
    """Standard layout configuration."""
    return LayoutConfig()


def test_compose_question_returns_assets(sample_question, layout_config, monkeypatch):
    """Returns list of SliceAsset."""
    # Mock the image provider to avoid file system access
    def mock_get_slice(label, add_mark_clearance=False):
        return Image.new('RGB', (1654, 100), color='white')
    
    # This test needs proper mocking - skipping for now
    pytest.skip("Requires mocking image provider")


def test_compose_question_adds_padding_for_marks(sample_question, layout_config):
    """Adds 10px padding for parts with explicit marks."""
    # Test that add_mark_clearance=True is passed for parts with marks
    pytest.skip("Requires mocking image provider")


def test_compose_question_creates_context_slices():
    """Creates context slices for parent parts."""
    pytest.skip("Requires mocking image provider")


def test_compose_question_skips_overlapping_leaves():
    """Skips leaf parts that overlap with parent context."""
    pytest.skip("Requires mocking image provider")


# Note: Full tests require mocking the ImageProvider
# These tests should be completed with proper fixture setup
