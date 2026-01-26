"""
Unit tests for paginator layout engine.

Includes regression tests for margin cutoff fix (Phase 6.9).
"""

import pytest
from unittest.mock import MagicMock

from gcse_toolkit.builder_v2.layout import (
    LayoutConfig,
    paginate,
    SliceAsset,
)
from gcse_toolkit.builder_v2.layout.models import LayoutResult, PagePlan


@pytest.fixture
def mock_asset_factory():
    """Factory to create mock assets."""
    def _create(
        height: int, 
        question_id: str = "q1", 
        part_label: str = "1(a)", 
        is_header: bool = False
    ):
        mock_img = MagicMock()
        mock_img.width = 100
        mock_img.height = height
        
        # Override label if header requested
        final_label = "1_header" if is_header else part_label
        
        asset = SliceAsset(
            question_id=question_id,
            part_label=final_label,
            image=mock_img,
            width=mock_img.width,
            height=height,
            marks=1,
            is_text_header=is_header,  # Pass is_header to constructor
        )
        
        return asset
    return _create


class TestPaginatorWithContextSpacing:
    """
    Tests specifically for context+child spacing and margin handling.
    Regression test for: Slices Cut Off by Bottom Margin
    """
    
    def test_when_context_and_child_fit_with_spacing_then_keeps_on_page(self, mock_asset_factory):
        """
        Verify that context and child are kept on same page if they fit
        INCLUDING the context_child_spacing.
        """
        # Arrange
        config = LayoutConfig(
            page_height=1000,
            margin_top=40,
            margin_bottom=40,
            context_child_spacing=20, # The new config field
            inter_part_spacing=20
        )
        # Available height = 920
        
        # Context (400) + Spacing (20) + Child (500) = 920. Fits exactly.
        a1 = mock_asset_factory(400, part_label="1(a)_context")
        a2 = mock_asset_factory(500, part_label="1(a)(i)")
        
        assets = [a1, a2]
        
        # Act
        result = paginate(assets, config)
        
        # Assert
        assert result.page_count == 1
        page = result.pages[0]
        assert len(page.placements) == 2
        # Check positions
        # P1: top=40 (margin)
        # P2: top=40 + 400 + 20(context_spacing) = 460
        # Bottom of P2 = 460 + 500 = 960. (Page bottom is 1000-40=960). Fits.
        assert page.placements[0].top == 40
        assert page.placements[1].top == 460

    def test_when_context_and_child_overflow_due_to_spacing_then_breaks_page(self, mock_asset_factory):
        """
        Verify that if context spacing pushes child over margin, BOTH move to new page.
        This confirms the fix is working (paginator accounts for spacing).
        """
        # Arrange
        config = LayoutConfig(
            page_height=1000,
            margin_top=40,
            margin_bottom=40,
            context_child_spacing=20,
            inter_part_spacing=20
        )
        # Available height = 920
        
        # Fill page partially first
        # Filler: 50px. Top=40. Bottom=90.
        a0 = mock_asset_factory(50, part_label="filler")
        
        # Remaining space: 960 (bottom) - 90 = 870.
        
        # Context (400) + Spacing (20) + Child (460) = 880.
        # 880 > 870. Should NOT fit.
        
        a1 = mock_asset_factory(400, part_label="1(a)_context")
        a2 = mock_asset_factory(460, part_label="1(a)(i)")
        
        assets = [a0, a1, a2]
        
        # Act
        result = paginate(assets, config)
        
        # Assert
        assert result.page_count == 2
        
        # Page 1: Filler only
        assert len(result.pages[0].placements) == 1
        assert result.pages[0].placements[0].asset == a0
        
        # Page 2: Context + Child
        assert len(result.pages[1].placements) == 2
        assert result.pages[1].placements[0].asset == a1
        assert result.pages[1].placements[1].asset == a2
        
        # Verify Page 2 positions
        # P1 (Context): top=40 (margin)
        # P2 (Child): top=40 + 400 + 20 (spacing) = 460
        assert result.pages[1].placements[0].top == 40
        assert result.pages[1].placements[1].top == 460

    def test_when_multi_level_context_overflows_then_breaks_page_atomically(self, mock_asset_factory):
        """
        Verify that a chain of Headers and Contexts stays with the final leaf.
        Scenario: Header(50) -> Context(50) -> Context(50) -> Leaf(100)
        Total Height = 50 + 10 + 50 + 20 + 50 + 20 + 100 = 300 (approx with spacing)
        If page has 200 space left, ALL should move to next page.
        """
        config = LayoutConfig(
            page_height=1000,
            margin_top=40,
            margin_bottom=40,
            context_child_spacing=20,
            inter_part_spacing=20
        )
        # Page height: 960 bottom.
        
        # Filler to leave only 200px space
        # 960 - 200 = 760 used.
        # Top=40. Filler Height = 720. 
        a0 = mock_asset_factory(720, part_label="filler")
        
        # The Atomic Chain
        # 1. Header (Question 2)
        a1 = mock_asset_factory(60, question_id="q2", part_label="2_header", is_header=True)
        # 2. Root Context (2)
        a2 = mock_asset_factory(100, question_id="q2", part_label="2_context")
        # 3. Child Context (a)
        a3 = mock_asset_factory(50, question_id="q2", part_label="2(a)_context")
        # 4. Leaf (i)
        a4 = mock_asset_factory(50, question_id="q2", part_label="2(a)(i)")

        # Total Group Check:
        # Header (60)
        # + 10 (header spacing)
        # + Context (100)
        # + 20 (ctx spacing)
        # + Context (50)
        # + 20 (ctx spacing)
        # + Leaf (50)
        # = 310 total needed.
        # Space available: 200.
        # MUST move to Page 2.
        
        assets = [a0, a1, a2, a3, a4]
        
        result = paginate(assets, config)
        
        assert result.page_count == 2
        
        # Page 1: only filler
        assert len(result.pages[0].placements) == 1
        assert result.pages[0].placements[0].asset == a0
        
        # Page 2: The entire chain
        p2 = result.pages[1]
        assert len(p2.placements) == 4
        assert p2.placements[0].asset == a1  # Header
        assert p2.placements[1].asset == a2  # 2_context
        assert p2.placements[2].asset == a3  # 2(a)_context
        assert p2.placements[3].asset == a4  # 2(a)(i)
        
        # Check positions on Page 2 (top=40)
        # Header at 40
        assert p2.placements[0].top == 40
        # Context 1 at 40 + 60 + 10 = 110
        assert p2.placements[1].top == 110
        # Context 2 at 110 + 100 + 20 = 230
        assert p2.placements[2].top == 230
        # Leaf at 230 + 50 + 20 = 300
        assert p2.placements[3].top == 300

    def test_regular_spacing_default(self, mock_asset_factory):
        """Verify normal inter-part spacing is used for non-context items."""
        config = LayoutConfig(inter_part_spacing=50) # Large spacing
        
        a1 = mock_asset_factory(100, part_label="1(a)")
        a2 = mock_asset_factory(100, part_label="1(b)")
        
        result = paginate([a1, a2], config)
        
        assert result.page_count == 1
        # P1: 40
        # P2: 40 + 100 + 50 = 190
        assert result.pages[0].placements[1].top == 190
