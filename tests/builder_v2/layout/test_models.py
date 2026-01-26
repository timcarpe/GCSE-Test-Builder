"""
Unit tests for layout config and models.

Verified: 2025-12-12
"""

import pytest
from PIL import Image

from gcse_toolkit.builder_v2.layout import (
    LayoutConfig,
    SliceAsset,
    SlicePlacement,
    PagePlan,
    LayoutResult,
)


class TestLayoutConfig:
    """Tests for LayoutConfig dataclass."""

    def test_init_when_defaults_then_creates_valid_config(self):
        """Default parameters should create valid config."""
        # Act
        config = LayoutConfig()
        
        # Assert
        assert config.page_width > 0
        assert config.page_height > 0
        assert config.available_width > 0
        assert config.available_height > 0

    def test_available_width_when_valid_margins_then_correct(self):
        """available_width should be page_width - margins."""
        # Arrange
        config = LayoutConfig(page_width=1000, margin_left=100, margin_right=50)
        
        # Act & Assert
        assert config.available_width == 850  # 1000 - 100 - 50

    def test_available_height_when_valid_margins_then_correct(self):
        """available_height should be page_height - margins."""
        # Arrange
        config = LayoutConfig(page_height=2000, margin_top=80, margin_bottom=120)
        
        # Act & Assert
        assert config.available_height == 1800  #2000 - 80 - 120

    def test_init_when_margins_exceed_width_then_raises_error(self):
        """Invalid margins should raise ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Margins exceed page width"):
            LayoutConfig(page_width=100, margin_left=60, margin_right=60)


class TestSliceAsset:
    """Tests for SliceAsset dataclass."""

    def test_dimensions_when_image_loaded_then_correct(self):
        """Width and height should match image dimensions."""
        # Arrange
        img = Image.new('RGB', (200, 150))
        asset = SliceAsset("q1", "1(a)", img, width=200, height=150, marks=1)
        
        # Act & Assert
        assert asset.width == 200
        assert asset.height == 150


class TestSlicePlacement:
    """Tests for SlicePlacement dataclass."""

    def test_bottom_when_placed_then_correct(self):
        """bottom should be top + asset.height."""
        # Arrange
        img = Image.new('RGB', (100, 50))
        asset = SliceAsset("q1", "1(a)", img, width=100, height=50, marks=1)
        placement = SlicePlacement(asset, top=100)
        
        # Act & Assert
        assert placement.bottom == 150  # 100 + 50


class TestPagePlan:
    """Tests for PagePlan dataclass."""

    def test_placement_count_when_multiple_placements_then_correct(self):
        """placement_count should return number of placements."""
        # Arrange
        img = Image.new('RGB', (100, 50))
        p1 = SlicePlacement(SliceAsset("q1", "1(a)", img, 100, 50, 1), 0)
        p2 = SlicePlacement(SliceAsset("q1", "1(b)", img, 100, 50, 1), 50)
        page = PagePlan(0, (p1, p2), 100)
        
        # Act & Assert
        assert page.placement_count == 2

    def test_is_empty_when_no_placements_then_true(self):
        """is_empty should be True for empty page."""
        # Arrange
        page = PagePlan(0, (), 0)
        
        # Act & Assert
        assert page.is_empty is True


class TestLayoutResult:
    """Tests for LayoutResult dataclass."""

    def test_page_count_when_multiple_pages_then_correct(self):
        """page_count should return number of pages."""
        # Arrange
        p1 = PagePlan(0, (), 0)
        p2 = PagePlan(1, (), 0)
        result = LayoutResult(pages=(p1, p2))
        
        # Act & Assert
        assert result.page_count == 2
