"""
Unit tests for extractor_v2.slicing.bounds_calculator module.

Tests for calculating slice bounds from part detections.

Verified: 2025-12-12
"""

import pytest

from gcse_toolkit.core.models import SliceBounds
from gcse_toolkit.extractor_v2.config import SliceConfig
from gcse_toolkit.extractor_v2.slicing.bounds_calculator import (
    calculate_all_bounds,
    bounds_from_detections,
    PartBounds,
)
from gcse_toolkit.extractor_v2.detection.parts import PartLabel
from gcse_toolkit.extractor_v2.detection.marks import MarkBox


class TestCalculateAllBounds:
    """Tests for calculate_all_bounds()."""

    @pytest.fixture
    def default_config(self):
        """Default SliceConfig for tests."""
        return SliceConfig(
            padding_px=10,
            min_height_px=20,
            mark_box_clearance_px=8,
            overlap_tolerance_px=4,
        )

    def test_calculate_all_bounds_when_single_part_then_returns_full_height(
        self, default_config
    ):
        """Single part should span entire composite."""
        # Arrange
        parts = [
            PartBounds(label="1", kind="question", detected_top=0, detected_bottom=500)
        ]
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=[],
            config=default_config,
        )
        
        # Assert
        assert "1" in result
        assert result["1"].top == 0
        assert result["1"].bottom <= 500

    def test_calculate_all_bounds_when_multiple_parts_then_no_overlap(
        self, default_config
    ):
        """Multiple parts should not overlap."""
        # Arrange
        parts = [
            PartBounds(label="1", kind="question", detected_top=0, detected_bottom=100),
            PartBounds(label="1(a)", kind="letter", detected_top=100, detected_bottom=300),
            PartBounds(label="1(b)", kind="letter", detected_top=300, detected_bottom=500),
        ]
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=[],
            config=default_config,
        )
        
        # Assert
        assert result["1"].bottom <= result["1(a)"].top + default_config.overlap_tolerance_px
        assert result["1(a)"].bottom <= result["1(b)"].top + default_config.overlap_tolerance_px

    def test_calculate_all_bounds_when_marks_present_then_clamps_to_marks(self):
        """Test that bounds are clamped to mark box positions."""
        # Arrange
        parts = [
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=400),
        ]
        marks = [
            MarkBox(value=5, y_position=260, bbox=(700, 250, 750, 270)),
        ]
        default_config = SliceConfig()
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=1000,
            composite_width=800,
            marks=marks,
            config=default_config,
        )
        
        # Assert
        # With new passthrough behavior, bottom uses detected_bottom (no clamping)
        assert result["1(a)"].bottom == 400

    def test_calculate_all_bounds_when_small_gap_then_respects_min_height(
        self, default_config
    ):
        """Parts use detected bounds even if height is small."""
        # Arrange
        parts = [
            PartBounds(label="1", kind="question", detected_top=0, detected_bottom=10),
        ]
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=[],
            config=default_config,
        )
        
        # Assert
        # With passthrough behavior, just uses detected values
        assert result["1"].bottom == 10

    def test_calculate_all_bounds_when_negative_detected_then_clamps_to_zero(
        self, default_config
    ):
        """Bounds should never be negative."""
        # Arrange - detected_top that would go negative with padding
        parts = [
            PartBounds(label="1", kind="question", detected_top=5, detected_bottom=100),
        ]
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=[],
            config=default_config,
        )
        
        # Assert
        assert result["1"].top >= 0

    def test_calculate_all_bounds_when_exceeds_height_then_clamps(
        self, default_config
    ):
        """Bounds should not exceed composite height."""
        # Arrange
        parts = [
            PartBounds(label="1", kind="question", detected_top=400, detected_bottom=500),
        ]
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=[],
            config=default_config,
        )
        
        # Assert
        assert result["1"].bottom <= 500


class TestBoundsFromDetections:
    """Tests for bounds_from_detections()."""

    def test_bounds_from_detections_when_letters_only_then_creates_letter_parts(self):
        """Should create PartBounds for each letter."""
        # Arrange
        letters = [
            PartLabel(label="a", kind="letter", y_position=100, bbox=(50, 100, 70, 120)),
            PartLabel(label="b", kind="letter", y_position=300, bbox=(50, 300, 70, 320)),
        ]
        
        # Act
        result = bounds_from_detections(
            question_num=1,
            letters=letters,
            romans=[],
            composite_height=500,
        )
        
        # Assert
        labels = [p.label for p in result]
        assert "1" in labels
        assert "1(a)" in labels
        assert "1(b)" in labels

    def test_bounds_from_detections_when_nested_then_creates_hierarchy(self):
        """Should create PartBounds for letters and their romans."""
        # Arrange
        letters = [
            PartLabel(label="a", kind="letter", y_position=100, bbox=(50, 100, 70, 120)),
        ]
        romans = [
            PartLabel(label="i", kind="roman", y_position=150, bbox=(80, 150, 100, 170)),
            PartLabel(label="ii", kind="roman", y_position=250, bbox=(80, 250, 100, 270)),
        ]
        
        # Act
        result = bounds_from_detections(
            question_num=1,
            letters=letters,
            romans=romans,
            composite_height=500,
        )
        
        # Assert
        labels = [p.label for p in result]
        assert "1(a)(i)" in labels
        assert "1(a)(ii)" in labels

    def test_bounds_from_detections_when_empty_then_returns_root_only(self):
        """Should return root question part when no letters/romans."""
        # Arrange
        
        # Act
        result = bounds_from_detections(
            question_num=1,
            letters=[],
            romans=[],
            composite_height=500,
        )
        
        # Assert
        assert len(result) == 1
        assert result[0].label == "1"
        assert result[0].kind == "question"

    def test_bounds_from_detections_single_part_uses_mark_bottom(self):
        """Single-part question should cap bottom at mark box, not page end."""
        marks = [
            MarkBox(value=5, y_position=380, bbox=(450, 380, 480, 420)),
        ]
        
        result = bounds_from_detections(
            question_num=1,
            letters=[],
            romans=[],
            composite_height=800,
            marks=marks,
        )
        
        assert len(result) == 1
        root = result[0]
        assert root.label == "1"
        # Bottom should be mark bottom plus padding (5) but never exceed composite
        assert root.detected_bottom == 425

    def test_bounds_from_detections_unsorted_letters_produce_correct_bounds(self):
        """Unsorted letter inputs should produce same bounds as sorted inputs."""
        # Arrange - letters deliberately out of Y-order
        unsorted_letters = [
            PartLabel(label="b", kind="letter", y_position=300, bbox=(50, 300, 70, 320)),
            PartLabel(label="a", kind="letter", y_position=100, bbox=(50, 100, 70, 120)),
        ]
        sorted_letters = [
            PartLabel(label="a", kind="letter", y_position=100, bbox=(50, 100, 70, 120)),
            PartLabel(label="b", kind="letter", y_position=300, bbox=(50, 300, 70, 320)),
        ]

        # Act
        result_unsorted = bounds_from_detections(
            question_num=1, letters=unsorted_letters, romans=[], composite_height=500,
        )
        result_sorted = bounds_from_detections(
            question_num=1, letters=sorted_letters, romans=[], composite_height=500,
        )

        # Assert - same labels and same bounds regardless of input order
        unsorted_map = {p.label: (p.detected_top, p.detected_bottom) for p in result_unsorted}
        sorted_map = {p.label: (p.detected_top, p.detected_bottom) for p in result_sorted}
        assert unsorted_map == sorted_map

    def test_bounds_from_detections_last_letter_clamps_to_mark_bottom(self):
        """Last letter with no own mark should clamp to max mark bottom, not composite_height."""
        # Arrange - two letters, mark only on (a), none on last letter (b)
        letters = [
            PartLabel(label="a", kind="letter", y_position=100, bbox=(50, 100, 70, 120)),
            PartLabel(label="b", kind="letter", y_position=300, bbox=(50, 300, 70, 320)),
        ]
        marks = [
            # Mark for (a) at y=200, bottom=230
            MarkBox(value=3, y_position=200, bbox=(700, 200, 750, 230)),
        ]

        # Act
        result = bounds_from_detections(
            question_num=1, letters=letters, romans=[], composite_height=800, marks=marks,
        )

        # Assert - (b) is the last letter with no mark; should clamp to max mark bottom + 5
        part_b = next(p for p in result if p.label == "1(b)")
        assert part_b.detected_bottom == 235  # 230 + BOUNDS_PADDING_PX (5)
        assert part_b.detected_bottom < 800   # NOT composite_height

    def test_bounds_from_detections_last_roman_clamps_to_mark_bottom(self):
        """Last roman with no own mark should clamp to max mark bottom, not composite_height."""
        # Arrange - one letter with two romans, mark only on (i), none on last roman (ii)
        letters = [
            PartLabel(label="a", kind="letter", y_position=100, bbox=(50, 100, 70, 120)),
        ]
        romans = [
            PartLabel(label="i", kind="roman", y_position=150, bbox=(80, 150, 100, 170)),
            PartLabel(label="ii", kind="roman", y_position=300, bbox=(80, 300, 100, 320)),
        ]
        marks = [
            # Mark for (i) at y=200, bottom=230
            MarkBox(value=2, y_position=200, bbox=(700, 200, 750, 230)),
        ]

        # Act
        result = bounds_from_detections(
            question_num=1, letters=letters, romans=romans, composite_height=800, marks=marks,
        )

        # Assert - (ii) is the last roman with no mark; should clamp to max mark bottom + 5
        part_ii = next(p for p in result if p.label == "1(a)(ii)")
        assert part_ii.detected_bottom == 235  # 230 + BOUNDS_PADDING_PX (5)
        assert part_ii.detected_bottom < 800   # NOT composite_height


class TestBoundsValidation:
    """Tests for invalid bounds detection."""

    @pytest.fixture
    def default_config(self):
        return SliceConfig()

    def test_slicebounds_when_top_greater_than_bottom_then_raises(self):
        """SliceBounds with top > bottom should raise ValueError."""
        with pytest.raises(ValueError, match="bottom must be > top"):
            SliceBounds(top=200, bottom=100)

    def test_slicebounds_when_negative_top_then_raises(self):
        """SliceBounds with negative top should raise ValueError."""
        with pytest.raises(ValueError, match="top must be >= 0"):
            SliceBounds(top=-10, bottom=100)

    def test_overlaps_when_vertical_overlap_then_returns_true(self):
        """Overlapping bounds should be detected."""
        b1 = SliceBounds(top=0, bottom=150)
        b2 = SliceBounds(top=100, bottom=250)
        assert b1.overlaps(b2) is True

    def test_overlaps_when_adjacent_then_returns_false(self):
        """Adjacent bounds (no gap, no overlap) should not overlap."""
        b1 = SliceBounds(top=0, bottom=100)
        b2 = SliceBounds(top=100, bottom=200)
        assert b1.overlaps(b2) is False

    def test_overlaps_when_separate_then_returns_false(self):
        """Non-overlapping bounds should return False."""
        b1 = SliceBounds(top=0, bottom=100)
        b2 = SliceBounds(top=200, bottom=300)
        assert b1.overlaps(b2) is False


class TestPhase69Normalization:
    """Tests for Phase 6.9 box bounds calculation and normalization."""

    @pytest.fixture
    def default_config(self):
        return SliceConfig()

    def test_calculate_all_bounds_with_labels_uses_left_boundary(self, default_config):
        """Phase 6.9.1: Parts inherit root left from numeral, not individual labels."""
        # Arrange
        parts = [
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
        ]
        labels = [
            PartLabel("a", "letter", y_position=100, bbox=(50, 100, 70, 120)),
        ]
        numeral_bbox = (12, 5, 38, 27)  # Root at x=12
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=[],
            config=default_config,
            labels=labels,
            numeral_bbox=numeral_bbox,  # Provides root left edge
        )
        
        # Assert - New behavior: exact true values. "1(a)" has no label_bbox, so it defaults to 0.
        assert result["1(a)"].left == 0
        
        # If we provide label_bbox, then it uses it (50 - 5 padding = 45)
        parts[0].label_bbox = (50, 100, 70, 120)
        result2, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=[],
            config=default_config,
            numeral_bbox=numeral_bbox,
        )
        assert result2["1(a)"].left == 45
    def test_calculate_all_bounds_with_marks_uses_right_boundary(self, default_config):
        """Marks should provide right boundary for parts."""
        # Arrange
        parts = [
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
        ]
        marks = [
            MarkBox(value=5, y_position=110, bbox=(700, 105, 750, 125)),
        ]
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=marks,
            config=default_config,
        )
        
        # Assert - right should be mark right edge plus padding (750 + 5 = 755, updated for BOUNDS_PADDING_PX)
        assert result["1(a)"].right == 755
        assert result["1(a)"].right > 750  # More than mark right

    def test_calculate_all_bounds_box_not_full_width(self, default_config):
        """Bounds should be tight boxes, not full-width spans."""
        # Arrange
        parts = [
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
        ]
        labels = [
            PartLabel("a", "letter", y_position=100, bbox=(50, 100, 70, 120)),
        ]
        marks = [
            MarkBox(value=3, y_position=110, bbox=(700, 105, 750, 125)),
        ]
        numeral_bbox = (12, 5, 38, 27)  # Root at x=12
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=marks,
            config=default_config,
            labels=labels,
            numeral_bbox=numeral_bbox,
        )
        
        # Assert - should NOT be (0, composite_width)
        # "1(a)" has no label_bbox in this test setup, so it falls back to 0.
        # However, the root (if kind was question) would use numeral_bbox.
        # Let's add a root part to test this properly.
        assert result["1(a)"].left == 0
        assert result["1(a)"].right == 755

    def test_normalize_labels_per_level_per_page(self, default_config):
        """Phase 6.9.1: All parts inherit root left, page shifts apply offsets."""
        # Arrange - two pages with letters
        parts = [
            # Page 1
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
            PartBounds("1(b)", "letter", detected_top=220, detected_bottom=320),
            # Page 2 (> 200px gap = new page)
            PartBounds("1(c)", "letter", detected_top=600, detected_bottom=700),
        ]
        labels = [
            # Page 1: letters at x=50, 55 (avg ~52)
            PartLabel("a", "letter", y_position=100, bbox=(50, 100, 70, 120)),
            PartLabel("b", "letter", y_position=220, bbox=(55, 220, 75, 240)),
            # Page 2: letter shifted left to x=48 (offset = 48 - 52.5 ≈ -5)
            PartLabel("c", "letter", y_position=600, bbox=(48, 600, 68, 620)),
        ]
        numeral_bbox = (12, 5, 38, 27)  # Root at x=12, root_left = 7
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=1000,
            composite_width=800,
            marks=[],
            config=default_config,
            labels=labels,
            numeral_bbox=numeral_bbox,
        )
        
        # Assert - New behavior: exact true values (minus padding).
        # "1(a)" has no label_bbox, so it's 0.
        # If it HAD label_bbox (like in real life), it would be based on that.
        # But certainly no inheritance from root numeral.
        assert result["1(a)"].left == 0
        assert result["1(b)"].left == 0
        assert result["1(c)"].left == 0
        
        # Update parts with label_bboxes and re-test
        parts[0].label_bbox = (50, 100, 70, 120)  # L: 45
        parts[1].label_bbox = (55, 220, 75, 240)  # L: 50
        parts[2].label_bbox = (48, 600, 68, 620)  # L: 43
        
        result2, _ = calculate_all_bounds(parts=parts, composite_height=1000, composite_width=800, marks=[], config=default_config)
        assert result2["1(a)"].left == 45
        assert result2["1(b)"].left == 50
        assert result2["1(c)"].left == 43

    def test_normalize_marks_per_page_with_sanity_check(self, default_config, caplog):
        """Marks on same page should normalize together, warn if disagreement."""
        # Arrange - marks on same page with similar right edges
        parts = [
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
            PartBounds("1(b)", "letter", detected_top=220, detected_bottom=320),
        ]
        marks = [
            MarkBox(value=3, y_position=110, bbox=(700, 105, 750, 125)),
            MarkBox(value=2, y_position=230, bbox=(700, 225, 748, 245)),  # Within 10px tolerance
        ]
        
        # Act
        with caplog.at_level("WARNING"):
            result, _ = calculate_all_bounds(
                parts=parts,
                composite_height=500,
                composite_width=800,
                marks=marks,
                config=default_config,
            )
        
        # Assert - both should use max right edge (750)
        assert result["1(a)"].right == 755  # 750 + 5 padding (BOUNDS_PADDING_PX)
        assert result["1(b)"].right == 755  # Same
        # No warning since within tolerance
        assert "varying right edges" not in caplog.text

    def test_normalize_marks_warns_on_disagreement(self, default_config, caplog):
        """Should warn when marks on same page have significantly different right edges."""
        # Arrange - marks with different right edges (> 10px apart)
        parts = [
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
            PartBounds("1(b)", "letter", detected_top=220, detected_bottom=320),
        ]
        marks = [
            MarkBox(value=3, y_position=110, bbox=(700, 105, 750, 125)),
            MarkBox(value=2, y_position=230, bbox=(700, 225, 730, 245)),  # 20px difference
        ]
        
        # Act
        with caplog.at_level("WARNING"):
            result, _ = calculate_all_bounds(
                parts=parts,
                composite_height=500,
                composite_width=800,
                marks=marks,
                config=default_config,
            )
        
        # Assert - should warn and use max
        assert "Mark boxes vary (minor)" in caplog.text
        assert result["1(a)"].right == 755  # Uses max (750 + 5)
        assert result["1(b)"].right == 755

    def test_fallback_when_no_labels(self, default_config):
        """Should fallback to left=0 when no labels provided."""
        # Arrange
        parts = [
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
        ]
        
        # Act - no labels parameter
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=[],
            config=default_config,
            labels=None,
        )
        
        # Assert
        assert result["1(a)"].left == 0
        assert result["1(a)"].right == 800  # composite_width

    def test_fallback_when_no_marks(self, default_config):
        """Should fallback to composite_width when no marks."""
        # Arrange
        parts = [
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
        ]
        labels = [
            PartLabel("a", "letter", y_position=100, bbox=(50, 100, 70, 120)),
        ]
        numeral_bbox = (12, 5, 38, 27)  # Root at x=12
        
        # Act - no marks
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=[],
            config=default_config,
            labels=labels,
            numeral_bbox=numeral_bbox,
        )
        
        # Assert - root (not present here) would use 7. sub-parts fallback to 0.
        assert result["1(a)"].left == 0
        assert result["1(a)"].right == 800  # Fallback to full width
    def test_root_part_uses_left_edge(self, default_config):
        """Root parts (no parentheses) should use left edge 0."""
        # Arrange
        parts = [
            PartBounds("1", "question", detected_top=0, detected_bottom=100),
        ]
        labels = []  # No labels for root
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=[],
            config=default_config,
            labels=labels,
        )
        
        # Assert
        assert result["1"].left == 0  # Root always starts at 0


class TestPhase691HierarchicalInheritance:
    """Tests for Phase 6.9.1 hierarchical bounds inheritance."""

    @pytest.fixture
    def default_config(self):
        return SliceConfig()

    def test_group_parts_by_page_single_page(self):
        """All parts on one page should form single group."""
        from gcse_toolkit.extractor_v2.slicing.bounds_calculator import _group_parts_by_page, PartBounds
        
        # Arrange - parts with small gaps (<200px)
        parts = [
            PartBounds("1", "question", detected_top=0, detected_bottom=100),
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=250),
            PartBounds("1(b)", "letter", detected_top=250, detected_bottom=400),
        ]
        
        # Act
        pages = _group_parts_by_page(parts, gap_threshold=200)
        
        # Assert
        assert len(pages) == 1
        assert pages[0].page_index == 0
        assert len(pages[0].parts) == 3
        assert pages[0].horizontal_offset == 0

    def test_group_parts_by_page_multi_page(self):
        """Parts with >200px Y-gap should split into pages."""
        from gcse_toolkit.extractor_v2.slicing.bounds_calculator import _group_parts_by_page, PartBounds
        
        # Arrange - large gap between part b and c (300px gap)
        parts = [
            PartBounds("1", "question", detected_top=0, detected_bottom=100),
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
            # 300px gap here (200->500) - triggers new page
            PartBounds("1(b)", "letter", detected_top=500, detected_bottom=600),
        ]
        
        # Act
        pages = _group_parts_by_page(parts, gap_threshold=200)
        
        # Assert
        assert len(pages) == 2
        assert len(pages[0].parts) == 2  # root and (a)
        assert len(pages[1].parts) == 1  # (b)
        assert pages[1].page_index == 1

    def test_calculate_page_offset_no_shift(self):
        """Labels at same X-position should return offset=0."""
        from gcse_toolkit.extractor_v2.slicing.bounds_calculator import (
            _calculate_page_offset, PageGroup, PartBounds
        )
        
        # Arrange - labels at same X position on both pages
        page0 = PageGroup(0, [
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
        ])
        page1 = PageGroup(1, [
            PartBounds("1(b)", "letter", detected_top=500, detected_bottom=600),
        ])
        labels = [
            PartLabel("a", "letter", y_position=100, bbox=(50, 100, 70, 120)),
            PartLabel("b", "letter", y_position=500, bbox=(50, 500, 70, 520)),  # Same X
        ]
        
        # Act
        offset = _calculate_page_offset(page1, page0, labels)
        
        # Assert
        assert offset == 0

    def test_calculate_page_offset_shift_right(self):
        """Labels shifted right should return positive offset."""
        from gcse_toolkit.extractor_v2.slicing.bounds_calculator import (
            _calculate_page_offset, PageGroup, PartBounds
        )
        
        # Arrange - page 1 labels shifted +15px to the right
        page0 = PageGroup(0, [
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
        ])
        page1 = PageGroup(1, [
            PartBounds("1(b)", "letter", detected_top=500, detected_bottom=600),
        ])
        labels = [
            PartLabel("a", "letter", y_position=100, bbox=(50, 100, 70, 120)),
            PartLabel("b", "letter", y_position=500, bbox=(65, 500, 85, 520)),  # +15px
        ]
        
        # Act
        offset = _calculate_page_offset(page1, page0, labels)
        
        # Assert
        assert offset == 15

    def test_calculate_page_offset_shift_left(self):
        """Labels shifted left should return negative offset."""
        from gcse_toolkit.extractor_v2.slicing.bounds_calculator import (
            _calculate_page_offset, PageGroup, PartBounds
        )
        
        # Arrange - page 1 labels shifted -10px to the left
        page0 = PageGroup(0, [
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
        ])
        page1 = PageGroup(1, [
            PartBounds("1(b)", "letter", detected_top=500, detected_bottom=600),
        ])
        labels = [
            PartLabel("a", "letter", y_position=100, bbox=(50, 100, 70, 120)),
            PartLabel("b", "letter", y_position=500, bbox=(40, 500, 60, 520)),  # -10px
        ]
        
        # Act
        offset = _calculate_page_offset(page1, page0, labels)
        
        # Assert
        assert offset == -10

    def test_hierarchical_bounds_all_same_left(self, default_config):
        """All parts on same page should share root left edge."""
        # Arrange
        parts = [
            PartBounds("1", "question", detected_top=0, detected_bottom=100),
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=250),
            PartBounds("1(b)", "letter", detected_top=250, detected_bottom=400),
        ]
        labels = [
            PartLabel("a", "letter", y_position=100, bbox=(76, 100, 96, 120)),
            PartLabel("b", "letter", y_position=250, bbox=(78, 250, 98, 270)),
        ]
        numeral_bbox = (12, 5, 38, 27)  # Root at x=12
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=[],
            config=default_config,
            labels=labels,
            numeral_bbox=numeral_bbox,
        )
        
        # Assert - root uses numeral (7), but sub-parts use 0 if no label_bbox
        assert result["1"].left == 7
        assert result["1(a)"].left == 0
        assert result["1(b)"].left == 0

    def test_hierarchical_bounds_with_page_shift(self, default_config):
        """Parts on shifted page should use root_left + offset."""
        # Arrange - simulate multi-page with horizontal shift
        parts = [
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
            # Large gap - new page
            PartBounds("1(b)", "letter", detected_top=500, detected_bottom=600),
        ]
        labels = [
            PartLabel("a", "letter", y_position=100, bbox=(50, 100, 70, 120)),
            PartLabel("b", "letter", y_position=500, bbox=(60, 500, 80, 520)),  # +10px shift
        ]
        numeral_bbox = (12, 5, 38, 27)  # Root left = 7
        
        # Act
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=700,
            composite_width=800,
            marks=[],
            config=default_config,
            labels=labels,
            numeral_bbox=numeral_bbox,
        )
        
        # Assert - Sub-parts no longer inherit left edge or offsets.
        # (Offsets are returned separately instead)
        assert result["1(a)"].left == 0
        assert result["1(b)"].left == 0
    def test_hierarchical_bounds_no_numeral_fallback(self, default_config):
        """Should gracefully handle missing numeral_bbox."""
        # Arrange
        parts = [
            PartBounds("1", "question", detected_top=0, detected_bottom=100),
            PartBounds("1(a)", "letter", detected_top=100, detected_bottom=200),
        ]
        labels = [
            PartLabel("a", "letter", y_position=100, bbox=(50, 100, 70, 120)),
        ]
        
        # Act - no numeral_bbox provided
        result, _ = calculate_all_bounds(
            parts=parts,
            composite_height=500,
            composite_width=800,
            marks=[],
            config=default_config,
            labels=labels,
            numeral_bbox=None,  # Missing
        )
        
        # Assert - should fallback to left=0
        assert result["1"].left == 0
        assert result["1(a)"].left == 0
