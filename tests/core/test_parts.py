"""
Unit Tests for Part Model (V2)

Tests for the Part dataclass validating question tree structure.
"""

import pytest

from gcse_toolkit.core.models.marks import Marks
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.core.models.parts import Part, PartKind


class TestPart:
    """Tests for Part dataclass."""
    
    # ─────────────────────────────────────────────────────────────────────────
    # Constructor Tests
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_init_when_valid_leaf_then_creates_part(self):
        """Valid leaf part should be created successfully."""
        p = Part(
            label="1(a)(i)",
            kind=PartKind.ROMAN,
            marks=Marks.explicit(2),
            bounds=SliceBounds(100, 200),
        )
        assert p.label == "1(a)(i)"
        assert p.kind == PartKind.ROMAN
        assert p.marks.value == 2
        assert p.is_leaf is True
    
    def test_init_when_has_children_then_creates_tree(self):
        """Part with children should create valid tree."""
        child = Part("1(a)", PartKind.LETTER, Marks.explicit(3), SliceBounds(100, 200))
        parent = Part(
            label="1",
            kind=PartKind.QUESTION,
            marks=Marks.aggregate([child]),
            bounds=SliceBounds(0, 300),
            children=(child,),
        )
        assert parent.is_leaf is False
        assert len(parent.children) == 1
    
    def test_init_when_children_unsorted_then_raises_error(self):
        """Children not sorted by position should raise ValueError."""
        child1 = Part("a", PartKind.LETTER, Marks.explicit(2), SliceBounds(100, 200))
        child2 = Part("b", PartKind.LETTER, Marks.explicit(3), SliceBounds(50, 100))
        
        with pytest.raises(ValueError, match="sorted by position"):
            Part(
                label="1",
                kind=PartKind.QUESTION,
                marks=Marks.explicit(5),
                bounds=SliceBounds(0, 300),
                children=(child1, child2),
            )
    
    def test_init_when_children_overlap_then_raises_error(self):
        """Overlapping children should raise ValueError."""
        child1 = Part("a", PartKind.LETTER, Marks.explicit(2), SliceBounds(50, 150))
        child2 = Part("b", PartKind.LETTER, Marks.explicit(3), SliceBounds(100, 200))
        
        with pytest.raises(ValueError, match="cannot overlap"):
            Part(
                label="1",
                kind=PartKind.QUESTION,
                marks=Marks.explicit(5),
                bounds=SliceBounds(0, 300),
                children=(child1, child2),
            )
    
    def test_init_when_roman_has_context_bounds_then_raises_error(self):
        """Roman numeral parts should not have context_bounds."""
        with pytest.raises(ValueError, match="should not have context_bounds"):
            Part(
                label="1(a)(i)",
                kind=PartKind.ROMAN,
                marks=Marks.explicit(2),
                bounds=SliceBounds(100, 200),
                context_bounds=SliceBounds(80, 100),
            )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Property Tests
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_total_marks_when_leaf_then_returns_own_marks(self):
        """total_marks for leaf should be own marks."""
        p = Part("1(a)(i)", PartKind.ROMAN, Marks.explicit(3), SliceBounds(100, 200))
        assert p.total_marks == 3
    
    def test_total_marks_when_parent_then_returns_sum_of_children(self):
        """total_marks for parent should sum children."""
        child1 = Part("1(a)(i)", PartKind.ROMAN, Marks.explicit(2), SliceBounds(100, 150))
        child2 = Part("1(a)(ii)", PartKind.ROMAN, Marks.explicit(3), SliceBounds(150, 200))
        parent = Part("1(a)", PartKind.LETTER, Marks.aggregate([child1, child2]), 
                      SliceBounds(50, 250), children=(child1, child2))
        assert parent.total_marks == 5
    
    def test_depth_when_question_then_returns_zero(self):
        """Question parts should have depth 0."""
        p = Part("1", PartKind.QUESTION, Marks.explicit(5), SliceBounds(0, 300))
        assert p.depth == 0
    
    def test_depth_when_letter_then_returns_one(self):
        """Letter parts should have depth 1."""
        p = Part("1(a)", PartKind.LETTER, Marks.explicit(3), SliceBounds(100, 200))
        assert p.depth == 1
    
    def test_depth_when_roman_then_returns_two(self):
        """Roman parts should have depth 2."""
        p = Part("1(a)(i)", PartKind.ROMAN, Marks.explicit(2), SliceBounds(100, 150))
        assert p.depth == 2
    
    # ─────────────────────────────────────────────────────────────────────────
    # Iteration Tests
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_iter_leaves_when_tree_then_returns_only_leaves(self):
        """iter_leaves() should return only parts without children."""
        roman1 = Part("1(a)(i)", PartKind.ROMAN, Marks.explicit(2), SliceBounds(100, 150))
        roman2 = Part("1(a)(ii)", PartKind.ROMAN, Marks.explicit(3), SliceBounds(150, 200))
        letter = Part("1(a)", PartKind.LETTER, Marks.aggregate([roman1, roman2]), 
                      SliceBounds(50, 250), children=(roman1, roman2))
        question = Part("1", PartKind.QUESTION, Marks.aggregate([letter]),
                        SliceBounds(0, 300), children=(letter,))
        
        leaves = list(question.iter_leaves())
        assert len(leaves) == 2
        assert roman1 in leaves
        assert roman2 in leaves
        assert letter not in leaves
        assert question not in leaves
    
    def test_iter_all_when_tree_then_returns_all_parts(self):
        """iter_all() should return all parts in tree order."""
        roman = Part("1(a)(i)", PartKind.ROMAN, Marks.explicit(2), SliceBounds(100, 150))
        letter = Part("1(a)", PartKind.LETTER, Marks.aggregate([roman]), 
                      SliceBounds(50, 200), children=(roman,))
        question = Part("1", PartKind.QUESTION, Marks.aggregate([letter]),
                        SliceBounds(0, 250), children=(letter,))
        
        all_parts = list(question.iter_all())
        assert len(all_parts) == 3
        assert all_parts[0] == question
        assert all_parts[1] == letter
        assert all_parts[2] == roman
    
    # ─────────────────────────────────────────────────────────────────────────
    # Query Method Tests
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_find_when_label_exists_then_returns_part(self):
        """find() should return matching part."""
        roman = Part("1(a)(i)", PartKind.ROMAN, Marks.explicit(2), SliceBounds(100, 150))
        letter = Part("1(a)", PartKind.LETTER, Marks.aggregate([roman]), 
                      SliceBounds(50, 200), children=(roman,))
        question = Part("1", PartKind.QUESTION, Marks.aggregate([letter]),
                        SliceBounds(0, 250), children=(letter,))
        
        found = question.find("1(a)(i)")
        assert found == roman
    
    def test_find_when_label_not_exists_then_returns_none(self):
        """find() should return None for non-existent label."""
        p = Part("1", PartKind.QUESTION, Marks.explicit(5), SliceBounds(0, 300))
        assert p.find("1(a)(ii)") is None
    
    # ─────────────────────────────────────────────────────────────────────────
    # Serialization Tests
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_roundtrip_when_serialized_then_equals_original(self):
        """to_dict/from_dict roundtrip should preserve data."""
        original = Part(
            label="1(a)(i)",
            kind=PartKind.ROMAN,
            marks=Marks.explicit(2),
            bounds=SliceBounds(100, 200),
            topic="Test Topic",
            sub_topics=("sub1", "sub2"),
        )
        restored = Part.from_dict(original.to_dict())
        assert restored.label == original.label
        assert restored.kind == original.kind
        assert restored.marks.value == original.marks.value
        assert restored.bounds == original.bounds
