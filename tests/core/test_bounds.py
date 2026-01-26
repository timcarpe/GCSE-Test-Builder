"""
Unit Tests for SliceBounds Model (V2)

Tests for the SliceBounds dataclass validating image regions.
"""

import pytest

from gcse_toolkit.core.models.bounds import SliceBounds


class TestSliceBounds:
    """Tests for SliceBounds dataclass."""
    
    # ─────────────────────────────────────────────────────────────────────────
    # Constructor Tests
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_init_when_valid_bounds_then_creates_bounds(self):
        """Valid bounds should be created successfully."""
        b = SliceBounds(top=0, bottom=100)
        assert b.top == 0
        assert b.bottom == 100
        assert b.left == 0
        assert b.right is None
    
    def test_init_when_negative_top_then_raises_error(self):
        """Negative top should raise ValueError."""
        with pytest.raises(ValueError, match="top must be >= 0"):
            SliceBounds(top=-1, bottom=100)
    
    def test_init_when_bottom_not_greater_than_top_then_raises_error(self):
        """bottom <= top should raise ValueError."""
        with pytest.raises(ValueError, match="bottom must be > top"):
            SliceBounds(top=100, bottom=50)
    
    def test_init_when_bottom_equals_top_then_raises_error(self):
        """bottom == top should raise ValueError."""
        with pytest.raises(ValueError, match="bottom must be > top"):
            SliceBounds(top=100, bottom=100)
    
    def test_init_when_negative_left_then_raises_error(self):
        """Negative left should raise ValueError."""
        with pytest.raises(ValueError, match="left must be >= 0"):
            SliceBounds(top=0, bottom=100, left=-1)
    
    def test_init_when_right_not_greater_than_left_then_raises_error(self):
        """right <= left should raise ValueError."""
        with pytest.raises(ValueError, match="right must be > left"):
            SliceBounds(top=0, bottom=100, left=50, right=50)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Property Tests
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_height_when_valid_bounds_then_returns_difference(self):
        """height should be bottom - top."""
        b = SliceBounds(top=50, bottom=150)
        assert b.height == 100
    
    def test_width_when_right_is_none_then_returns_none(self):
        """width should be None when right is None."""
        b = SliceBounds(top=0, bottom=100)
        assert b.width is None
    
    def test_width_when_right_is_set_then_returns_difference(self):
        """width should be right - left when right is set."""
        b = SliceBounds(top=0, bottom=100, left=10, right=110)
        assert b.width == 100
    
    # ─────────────────────────────────────────────────────────────────────────
    # Query Method Tests
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_contains_when_y_in_range_then_returns_true(self):
        """contains() should return True for y in [top, bottom)."""
        b = SliceBounds(top=50, bottom=150)
        assert b.contains(50) is True
        assert b.contains(100) is True
        assert b.contains(149) is True
    
    def test_contains_when_y_at_bottom_then_returns_false(self):
        """contains() should return False for y == bottom (exclusive)."""
        b = SliceBounds(top=50, bottom=150)
        assert b.contains(150) is False
    
    def test_contains_when_y_outside_range_then_returns_false(self):
        """contains() should return False for y outside range."""
        b = SliceBounds(top=50, bottom=150)
        assert b.contains(49) is False
        assert b.contains(200) is False
    
    def test_overlaps_when_regions_overlap_then_returns_true(self):
        """overlaps() should return True for overlapping regions."""
        b1 = SliceBounds(top=0, bottom=100)
        b2 = SliceBounds(top=50, bottom=150)
        assert b1.overlaps(b2) is True
        assert b2.overlaps(b1) is True
    
    def test_overlaps_when_regions_adjacent_then_returns_false(self):
        """overlaps() should return False for adjacent regions."""
        b1 = SliceBounds(top=0, bottom=100)
        b2 = SliceBounds(top=100, bottom=200)
        assert b1.overlaps(b2) is False
    
    def test_overlaps_when_regions_separate_then_returns_false(self):
        """overlaps() should return False for separate regions."""
        b1 = SliceBounds(top=0, bottom=100)
        b2 = SliceBounds(top=150, bottom=250)
        assert b1.overlaps(b2) is False
    
    def test_is_above_when_fully_above_then_returns_true(self):
        """is_above() should return True when self is above other."""
        b1 = SliceBounds(top=0, bottom=100)
        b2 = SliceBounds(top=100, bottom=200)
        assert b1.is_above(b2) is True
    
    # ─────────────────────────────────────────────────────────────────────────
    # Serialization Tests
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_to_dict_when_minimal_then_returns_top_bottom(self):
        """to_dict() should only include top and bottom when defaults."""
        b = SliceBounds(top=50, bottom=150)
        d = b.to_dict()
        assert d == {"top": 50, "bottom": 150}
    
    def test_to_dict_when_full_then_returns_all_fields(self):
        """to_dict() should include all fields when set."""
        b = SliceBounds(top=50, bottom=150, left=10, right=200)
        d = b.to_dict()
        assert d == {"top": 50, "bottom": 150, "left": 10, "right": 200}
    
    def test_from_dict_when_valid_data_then_creates_bounds(self):
        """from_dict() should recreate bounds from dict."""
        d = {"top": 50, "bottom": 150, "left": 10, "right": 200}
        b = SliceBounds.from_dict(d)
        assert b.top == 50
        assert b.bottom == 150
        assert b.left == 10
        assert b.right == 200
    
    def test_roundtrip_when_serialized_then_equals_original(self):
        """to_dict/from_dict roundtrip should preserve data."""
        original = SliceBounds(top=50, bottom=150, left=10, right=200)
        restored = SliceBounds.from_dict(original.to_dict())
        assert original == restored
