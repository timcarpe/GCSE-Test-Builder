"""
Tests for builder_v2.images.cropper

Test Coverage:
- crop_slice(): Image cropping from composite
- add_mark_clearance: +10px padding for parts with marks
- Bounds validation
"""
import pytest
from PIL import Image
from gcse_toolkit.builder_v2.images.cropper import crop_slice, MARK_BOX_CLEARANCE_PX
from gcse_toolkit.core.models.bounds import SliceBounds


@pytest.fixture
def sample_composite():
    """Create sample composite image."""
    return Image.new('RGB', (1654, 2339), color='white')


def test_crop_slice_basic(sample_composite):
    """Crops slice from composite using bounds."""
    # Arrange
    bounds = SliceBounds(left=0, top=100, right=800, bottom=300)
    
    # Act
    result = crop_slice(sample_composite, bounds)
    
    # Assert
    assert result.size == (800, 200)  # width=800, height=200


def test_crop_slice_full_width(sample_composite):
    """Crops full width slice."""
    # Arrange
    bounds = SliceBounds(left=0, top=100, right=1654, bottom=300)
    
    # Act
    result = crop_slice(sample_composite, bounds)
    
    # Assert
    assert result.width == 1654
    assert result.height == 200


def test_crop_slice_with_mark_clearance(sample_composite):
    """Adds 10px padding when add_mark_clearance=True."""
    # Arrange
    bounds = SliceBounds(left=0, top=100, right=800, bottom=300)
    
    # Act
    result = crop_slice(sample_composite, bounds, add_mark_clearance=True)
    
    # Assert
    # Height should be original height + MARK_BOX_CLEARANCE_PX
    assert result.height == 200 + MARK_BOX_CLEARANCE_PX
    assert result.width == 800


def test_crop_slice_without_mark_clearance(sample_composite):
    """No padding when add_mark_clearance=False."""
    # Arrange
    bounds = SliceBounds(left=0, top=100, right=800, bottom=300)
    
    # Act
    result = crop_slice(sample_composite, bounds, add_mark_clearance=False)
    
    # Assert
    assert result.height == 200  # Exactly bounds height
    assert result.width == 800


def test_crop_slice_validates_bounds(sample_composite):
    """Handles bounds at image edges correctly."""
    # Arrange - Bounds at bottom edge
    bounds = SliceBounds(left=0, top=2200, right=1654, bottom=2339)
    
    # Act
    result = crop_slice(sample_composite, bounds)
    
    # Assert
    assert result.height == 139  # 2339 - 2200


def test_crop_slice_mark_clearance_at_bottom_edge(sample_composite):
    """Handles mark clearance at image bottom edge."""
    # Arrange - Bounds near bottom
    bounds = SliceBounds(left=0, top=2300, right=1654, bottom=2339)
    
    # Act
    result = crop_slice(sample_composite, bounds, add_mark_clearance=True)
    
    # Assert
    # Should handle gracefully even if clearance exceeds image
    assert result is not None
    assert result.width == 1654


def test_crop_slice_preserves_mode(sample_composite):
    """Preserves image mode (RGB)."""
    # Arrange
    bounds = SliceBounds(left=0, top=100, right=800, bottom=300)
    
    # Act
    result = crop_slice(sample_composite, bounds)
    
    # Assert
    assert result.mode == 'RGB'


def test_crop_slice_small_region(sample_composite):
    """Handles very small crop regions."""
    # Arrange
    bounds = SliceBounds(left=100, top=100, right=110, bottom=105)
    
    # Act
    result = crop_slice(sample_composite, bounds)
    
    # Assert
    assert result.size == (10, 5)


def test_mark_box_clearance_constant():
    """MARK_BOX_CLEARANCE_PX constant is 10."""
    assert MARK_BOX_CLEARANCE_PX == 10
