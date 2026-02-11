"""
Module: builder_v2.layout.paginator

Purpose:
    Arrange slices onto pages using simple space-based placement.
    Only rule: context slices stay with their immediate next child.

Key Functions:
    - paginate(): Main pagination function

Algorithm:
    Ultra-simple:
    1. For each asset, check if it fits on current page
    2. If it's a context and next asset is a leaf, keep them together
    3. Otherwise, place individually
    4. Start new page when out of space

Dependencies:
    - builder_v2.layout.models: SliceAsset, PagePlan
    - builder_v2.layout.config: LayoutConfig

Used By:
    - builder_v2.controller: Main build controller
"""

from __future__ import annotations

import logging
from typing import List

from .config import LayoutConfig
from .models import SliceAsset, SlicePlacement, PagePlan, LayoutResult

logger = logging.getLogger(__name__)


def paginate(
    assets: List[SliceAsset],
    config: LayoutConfig,
) -> LayoutResult:
    """
    Arrange assets onto pages using atomic grouping.
    
    Rules:
    1. Identify "Atomic Groups" of assets that must stay together.
       - A group consists of [Header*, Context*, Leaf].
       - E.g. [Header:2, Context:2, Context:(a), Leaf:(i)]
    2. Place entire group on current page if it fits.
    3. If group doesn't fit, move entire group to next page.
    
    Args:
        assets: List of SliceAssets to place
        config: Layout configuration
        
    Returns:
        LayoutResult with page plans
    """
    if not assets:
        return LayoutResult(pages=(), warnings=[])
    
    pages: List[PagePlan] = []
    warnings: List[str] = []
    question_page_map: dict[str, list[int]] = {}
    
    current_placements: List[SlicePlacement] = []
    current_height = config.margin_top
    page_index = 0
    page_bottom = config.page_height - config.margin_bottom
    
    i = 0
    while i < len(assets):
        # Identify the next atomic group of assets
        group = _get_atomic_group(i, assets)
        
        # Calculate total height needed for this group
        group_height = 0
        group_placements = []
        
        # Temporary height tracking for group calculation
        temp_y = current_height
        is_start_of_page = not current_placements
        
        # Determine spacing before the group starts
        # If it's the very first item on page, no spacing
        # Otherwise, standard inter-part spacing
        initial_spacing = config.inter_part_spacing if not is_start_of_page else 0
        
        # Calculate layout for the group
        # We need to simulate placing them to get accurate height with internal spacing
        simulated_y = temp_y + initial_spacing
        
        for j, asset in enumerate(group):
            # Spacing logic within the group
            # Header -> Content: small gap (header_spacing)
            # Context -> Child: specific gap (context_child_spacing)
            
            spacing = 0
            if j > 0:
                prev = group[j-1]
                if prev.is_text_header:
                    spacing = 10  # Hardcoded header spacing from original logic
                elif prev.part_label.endswith("_context"):
                    spacing = config.context_child_spacing
            
            simulated_y += spacing
            group_placements.append(SlicePlacement(asset=asset, top=simulated_y))
            simulated_y += asset.height
            
        total_group_height = simulated_y - temp_y
        space_left = page_bottom - current_height
        
        if total_group_height > space_left and is_start_of_page:
            logger.warning(
                f"Atomic group overflows page {page_index}: "
                f"{total_group_height}px needed, {space_left}px available"
            )

        if total_group_height > space_left and not is_start_of_page:
            # Group doesn't fit - start new page
            pages.append(PagePlan(
                index=page_index,
                placements=tuple(current_placements),
                height_used=current_height - config.margin_top,
            ))
            page_index += 1
            current_placements = []
            current_height = config.margin_top
            
            # Recalculate group layout for new page (no initial spacing)
            temp_y = config.margin_top
            group_placements = []
            simulated_y = temp_y
            
            for j, asset in enumerate(group):
                spacing = 0
                if j > 0:
                    prev = group[j-1]
                    if prev.is_text_header:
                        spacing = 10
                    elif prev.part_label.endswith("_context"):
                        spacing = config.context_child_spacing
                
                simulated_y += spacing
                group_placements.append(SlicePlacement(asset=asset, top=simulated_y))
                simulated_y += asset.height
                
            total_group_height = simulated_y - temp_y

        # Place the group
        current_placements.extend(group_placements)
        current_height += total_group_height
        
        # Track pages
        for asset in group:
            _track_question(question_page_map, asset.question_id, page_index)
            
        # Advance index
        i += len(group)
    
    # Add final page
    if current_placements:
        pages.append(PagePlan(
            index=page_index,
            placements=tuple(current_placements),
            height_used=current_height - config.margin_top,
        ))
    
    logger.info(f"Paginated {len(assets)} assets onto {len(pages)} pages")
    
    return LayoutResult(
        pages=tuple(pages),
        warnings=warnings,
        question_page_map=question_page_map,
    )


def _get_atomic_group(start_idx: int, assets: List[SliceAsset]) -> List[SliceAsset]:
    """
    Get the next atomic group of assets starting at start_idx.
    
    A group captures a chain of headers/contexts and their final leaf.
    E.g. [Header, Context, Context, Leaf] -> All returned as one group.
    
    Args:
        start_idx: Current index in assets list
        assets: Full list of assets
        
    Returns:
        List of assets that must stay together
    """
    group = [assets[start_idx]]
    current_idx = start_idx
    
    while current_idx + 1 < len(assets):
        current = assets[current_idx]
        next_asset = assets[current_idx + 1]
        
        # Check if we should extend the group to include the next asset
        should_extend = False
        
        if current.question_id != next_asset.question_id:
            # Never chain across question boundaries
            break

        if current.is_text_header:
            # Header always grabs the next item (context or content)
            should_extend = True
        elif current.part_label.endswith("_context"):
            # Context always grabs the next item
            should_extend = True
            
        if should_extend:
            group.append(next_asset)
            current_idx += 1
        else:
            # Chain broken (current is a leaf)
            break
            
    return group


def _track_question(
    question_page_map: dict[str, list[int]],
    question_id: str,
    page_index: int,
) -> None:
    """Track which pages a question appears on."""
    if question_id not in question_page_map:
        question_page_map[question_id] = []
    if page_index not in question_page_map[question_id]:
        question_page_map[question_id].append(page_index)
