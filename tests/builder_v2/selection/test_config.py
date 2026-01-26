"""
Unit tests for SelectionConfig.

Verified: 2025-12-12
"""

import pytest

from gcse_toolkit.builder_v2.selection import SelectionConfig


class TestSelectionConfig:
    """Tests for SelectionConfig dataclass."""

    def test_init_when_valid_params_then_creates_config(self):
        """Valid parameters should create config successfully."""
        # Act
        config = SelectionConfig(target_marks=50, tolerance=5)
        
        # Assert
        assert config.target_marks == 50
        assert config.tolerance == 5

    def test_init_when_zero_marks_then_raises_error(self):
        """Zero target_marks should raise ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="target_marks must be positive"):
            SelectionConfig(target_marks=0)

    def test_init_when_negative_marks_then_raises_error(self):
        """Negative target_marks should raise ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="target_marks must be positive"):
            SelectionConfig(target_marks=-10)

    def test_init_when_negative_tolerance_then_raises_error(self):
        """Negative tolerance should raise ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="tolerance must be non-negative"):
            SelectionConfig(target_marks=50, tolerance=-1)

    def test_init_when_max_less_than_min_then_raises_error(self):
        """max_questions < min_questions should raise ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="max_questions"):
            SelectionConfig(target_marks=50, min_questions=5, max_questions=3)

    def test_mark_range_when_valid_then_returns_correct_tuple(self):
        """mark_range should return (target - tolerance, target + tolerance)."""
        # Arrange
        config = SelectionConfig(target_marks=50, tolerance=3)
        
        # Act
        result = config.mark_range
        
        # Assert
        assert result == (47, 53)

    def test_topic_set_when_topics_provided_then_returns_set(self):
        """topic_set should return topics as a set."""
        # Arrange
        config = SelectionConfig(
            target_marks=50,
            topics=["Topic A", "Topic B", "Topic A"],  # Duplicate
        )
        
        # Act
        result = config.topic_set
        
        # Assert
        assert result == {"Topic A", "Topic B"}

    def test_is_within_tolerance_when_in_range_then_returns_true(self):
        """is_within_tolerance should return True for marks in range."""
        # Arrange
        config = SelectionConfig(target_marks=50, tolerance=5)
        
        # Act & Assert
        assert config.is_within_tolerance(45) is True
        assert config.is_within_tolerance(50) is True
        assert config.is_within_tolerance(55) is True

    def test_is_within_tolerance_when_out_of_range_then_returns_false(self):
        """is_within_tolerance should return False for marks outside range."""
        # Arrange
        config = SelectionConfig(target_marks=50, tolerance=5)
        
        # Act & Assert
        assert config.is_within_tolerance(44) is False
        assert config.is_within_tolerance(56) is False
