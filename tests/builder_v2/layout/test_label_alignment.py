
import pytest
from unittest.mock import MagicMock
from gcse_toolkit.builder_v2.layout import (
    LayoutConfig,
    paginate,
    SliceAsset,
)
from gcse_toolkit.builder_v2.layout.models import SlicePlacement

@pytest.fixture
def mock_asset_factory():
    def _create(
        height: int, 
        question_id: str = "q1", 
        part_label: str = "1(a)", 
        is_header: bool = False
    ):
        asset = SliceAsset(
            question_id=question_id,
            part_label=part_label,
            image=None,
            width=100,
            height=height,
            marks=1,
            is_text_header=is_header
        )
        return asset
    return _create

class TestTripletGrouping:
    def test_label_context_child_stay_together(self, mock_asset_factory):
        """Header (Label) + Context + Child should move to new page as a unit."""
        config = LayoutConfig(
            page_height=1000,
            margin_top=40,
            margin_bottom=40,
            context_child_spacing=20,
        )
        # Available height = 920
        
        # Filler to leave only 200px space
        filler = mock_asset_factory(720, part_label="filler")
        
        # Group total height: 60 (label) + 10 (spacing) + 50 (ctx) + 20 (spacing) + 80 (child) = 220
        # 220 > 200. Should move to page 2.
        label = mock_asset_factory(60, question_id="q2", part_label="__header__", is_header=True)
        ctx = mock_asset_factory(50, question_id="q2", part_label="2_context")
        child = mock_asset_factory(80, question_id="q2", part_label="2(a)")
        
        assets = [filler, label, ctx, child]
        result = paginate(assets, config)
        
        assert result.page_count == 2
        # Page 2 should have Label, Context, Child
        page2 = result.pages[1]
        assert len(page2.placements) == 3
        assert page2.placements[0].asset.part_label == "__header__"
        assert page2.placements[1].asset.part_label == "2_context"
        assert page2.placements[2].asset.part_label == "2(a)"
        
        # Check positions on page 2
        assert page2.placements[0].top == 40
        assert page2.placements[1].top == 110 # 40 + 60 + 10
        assert page2.placements[2].top == 180 # 110 + 50 + 20

    def test_oversized_triplet_bleeds_but_starts_on_new_page(self, mock_asset_factory):
        """Triplet larger than page height should move to new page and start at top."""
        config = LayoutConfig(
            page_height=500, # Small page
            margin_top=40,
            margin_bottom=40,
        )
        # Available = 420
        
        # Triplet height: 100 + 10 + 200 + 20 + 200 = 530. (Exceeds 420)
        label = mock_asset_factory(100, part_label="__header__", is_header=True)
        ctx = mock_asset_factory(200, part_label="1_context")
        child = mock_asset_factory(200, part_label="1(a)")
        
        # Place a small filler first
        filler = mock_asset_factory(50, part_label="filler")
        
        result = paginate([filler, label, ctx, child], config)
        
        assert result.page_count == 2
        assert len(result.pages[0].placements) == 1
        assert len(result.pages[1].placements) == 3
        # First element of triplet should be at margin_top
        assert result.pages[1].placements[0].top == 40
