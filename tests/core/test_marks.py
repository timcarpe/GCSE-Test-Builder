"""
Unit Tests for Marks Model (V2)

Tests for the Marks dataclass validating mark values and sources.
"""

import pytest

from gcse_toolkit.core.models.marks import Marks
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.core.models.parts import Part, PartKind


class TestMarks:
    """Tests for Marks dataclass."""
    
    # ─────────────────────────────────────────────────────────────────────────
    # Constructor Tests
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_init_when_valid_values_then_creates_marks(self):
        """Valid marks should be created successfully."""
        m = Marks(value=5, source="explicit")
        assert m.value == 5
        assert m.source == "explicit"
    
    def test_init_when_zero_value_then_creates_marks(self):
        """Zero marks should be valid."""
        m = Marks(value=0, source="inferred")
        assert m.value == 0
    
    def test_init_when_negative_value_then_raises_error(self):
        """Negative marks should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            Marks(value=-1, source="explicit")
    
    def test_init_when_invalid_source_then_raises_error(self):
        """Invalid source should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid mark source"):
            Marks(value=5, source="wrong")
    
    def test_init_when_frozen_then_immutable(self):
        """Marks should be immutable (frozen)."""
        m = Marks(value=5, source="explicit")
        with pytest.raises(AttributeError):
            m.value = 10  # type: ignore
    
    # ─────────────────────────────────────────────────────────────────────────
    # Factory Method Tests
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_explicit_when_called_then_source_is_explicit(self):
        """explicit() factory should set source to 'explicit'."""
        m = Marks.explicit(3)
        assert m.value == 3
        assert m.source == "explicit"
    
    def test_inferred_when_called_then_source_is_inferred(self):
        """inferred() factory should set source to 'inferred'."""
        m = Marks.inferred(2)
        assert m.value == 2
        assert m.source == "inferred"
    
    def test_zero_when_called_then_returns_zero_marks(self):
        """zero() factory should return 0 with 'inferred' source."""
        m = Marks.zero()
        assert m.value == 0
        assert m.source == "inferred"
    
    def test_aggregate_when_parts_given_then_sums_values(self):
        """aggregate() should sum child part marks."""
        p1 = Part("a", PartKind.LETTER, Marks.explicit(2), SliceBounds(0, 100))
        p2 = Part("b", PartKind.LETTER, Marks.explicit(3), SliceBounds(100, 200))
        
        m = Marks.aggregate([p1, p2])
        
        assert m.value == 5
        assert m.source == "aggregate"
    
    def test_aggregate_when_empty_list_then_returns_zero(self):
        """aggregate() with empty list should return 0."""
        m = Marks.aggregate([])
        assert m.value == 0
        assert m.source == "aggregate"
    
    # ─────────────────────────────────────────────────────────────────────────
    # Operator Tests
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_add_when_two_marks_then_combines_values(self):
        """Adding two Marks should sum values."""
        m1 = Marks.explicit(3)
        m2 = Marks.explicit(4)
        result = m1 + m2
        assert result.value == 7
        assert result.source == "aggregate"
    
    def test_repr_when_called_then_shows_value_and_source(self):
        """__repr__ should show value and source."""
        m = Marks(5, "explicit")
        assert repr(m) == "Marks(5, 'explicit')"
