"""
Module: builder_v2.layout.composer

Purpose:
    Compose SliceAssets from selected questions.
    Loads and crops images for selected parts.

Key Functions:
    - compose_question(): Create assets for a single question
    - compose_exam(): Create assets for entire selection

Dependencies:
    - PIL: Image manipulation
    - gcse_toolkit.core.models: SelectionPlan
    - builder_v2.images: ImageProvider

Used By:
    - builder_v2.layout.paginator: Page layout
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

from gcse_toolkit.core.models.selection import SelectionPlan, SelectionResult
from gcse_toolkit.builder_v2.images import CompositeImageProvider

from .config import LayoutConfig
from .models import SliceAsset

logger = logging.getLogger(__name__)


def _apply_question_number_overlay(
    img: Image.Image,
    seq_number: int,
    numeral_bbox: Optional[Tuple[int, int, int, int]],
    slice_left_offset: int = 0,
) -> Image.Image:
    """
    Apply sequential question number overlay to image.
    
    Wrapper around overlay.apply_overlay() for question number renumbering.
    
    Args:
        img: Source image to modify (will be copied)
        seq_number: Sequential number to draw (1, 2, 3...)
        numeral_bbox: (left, top, right, bottom) in pixels, or None
        slice_left_offset: Left boundary of slice (for bbox adjustment)
        
    Returns:
        Image with number overlay (or original if no bbox)
    """
    if numeral_bbox is None:
        return img
    
    # Use the overlay module's apply_overlay function (no duplicate logic)
    from gcse_toolkit.builder_v2.output.overlay import apply_overlay
    
    # Calculate font size based on bbox height
    y0, y1 = numeral_bbox[1], numeral_bbox[3]
    font_size = max(12, y1 - y0 + 4)  # Slightly larger than bbox height for prominence
    
    # Phase 6.9: Adjust bbox for cropped slice coordinates
    # The bbox is in composite coordinates, but the image is cropped starting at slice_left_offset
    adjusted_bbox = (
        numeral_bbox[0] - slice_left_offset,  # left
        numeral_bbox[1],  # top (vertical position unchanged)
        numeral_bbox[2] - slice_left_offset,  # right
        numeral_bbox[3],  # bottom
    )
    
    return apply_overlay(
        image=img,
        new_number=str(seq_number),
        bbox=adjusted_bbox,
        font_size=font_size,
    )


def compose_question(
    plan: SelectionPlan,
    config: LayoutConfig,
    seq_number: Optional[int] = None,
) -> List[SliceAsset]:
    """
    Create renderable assets for a selected question.
    
    Given a SelectionPlan, loads the composite image and crops
    slices for all included parts. Each leaf gets its required
    context slices (question root, letter header) prepended.
    
    Context + leaf pairs are locked together and will never be
    split across pages.
    
    Args:
        plan: Selection plan with included parts
        config: Layout configuration
        
    Returns:
        List of SliceAssets ordered as: [ctx_q, ctx_letter?, leaf]* 
        Context slices are locked with their following leaf.
        
    Example:
        >>> assets = compose_question(plan, config)
        # [6_ctx, 6(a)] [6(b)_ctx, 6(b)(i)] [6(b)(ii)] ...
    """
    assets: List[SliceAsset] = []
    
    # Build bounds dict from question parts (all parts including context)
    all_parts = {part.label: part for part in plan.question.all_parts}
    bounds = {label: part.bounds for label, part in all_parts.items() if part.bounds is not None}
    
    # Also add context_bounds to the bounds dict under special keys
    for label, part in all_parts.items():
        if part.context_bounds is not None:
            bounds[f"{label}_context"] = part.context_bounds
    
    # NOTE: Right margin capping is now done at extraction time in bounds_calculator
    # Bounds in regions.json are already correctly capped, no runtime adjustment needed
    
    # Load composite image
    provider = CompositeImageProvider(plan.question.composite_path, bounds)
    
    # Get included leaves in document order
    included_leaves = plan.included_leaves
    
    if not included_leaves:
        return assets
    
    question_node = plan.question.question_node
    emitted_contexts = set()  # Track which context slices we've already added
    
    for idx, leaf in enumerate(included_leaves):
        is_last_leaf = (idx == len(included_leaves) - 1)
        
        # Get context parts for this leaf (ordered root-to-leaf)
        context_parts = question_node.get_context_for(leaf.label)
        
        # Add any context that hasn't been emitted yet
        for ctx_part in context_parts:
            ctx_label = f"{ctx_part.label}_context"
            
            if ctx_label in emitted_contexts:
                continue  # Already added this context
            
            if ctx_part.context_bounds is None:
                continue  # No context bounds for this part
            
            # Check if this context shares the same top position as any already-emitted context
            # If yes, skip it to avoid duplicate rendering (e.g., "8" and "(a)" on same line)
            skip_duplicate_context = False
            for prev_ctx_part in context_parts:
                prev_ctx_label = f"{prev_ctx_part.label}_context"
                if prev_ctx_label in emitted_contexts and prev_ctx_part.context_bounds:
                    if ctx_part.context_bounds.top == prev_ctx_part.context_bounds.top:
                        skip_duplicate_context = True
                        logger.debug(
                            f"Skipping context {ctx_part.label} - same top position ({ctx_part.context_bounds.top}) "
                            f"as already-rendered context {prev_ctx_part.label}"
                        )
                        break
            
            if skip_duplicate_context:
                continue
            
            try:
                ctx_img = provider.get_slice(ctx_label)
                
                # Apply question number overlay for root context
                # Check if this is the question root context (label matches question number)
                is_root_context = ctx_part.label == str(plan.question.question_node.label)
                if is_root_context and seq_number is not None:
                    # Phase 6.9: Pass slice left offset for bbox adjustment
                    slice_left = ctx_part.bounds.left if ctx_part.bounds else 0
                    ctx_img = _apply_question_number_overlay(
                        ctx_img,
                        seq_number,
                        plan.question.numeral_bbox,
                        slice_left_offset=slice_left,
                    )
                
                # Scale if needed
                if config.scale_to_fit and ctx_img.width > config.available_width:
                    scale_factor = config.available_width / ctx_img.width
                    new_width = config.available_width
                    new_height = int(ctx_img.height * scale_factor)
                    ctx_img = ctx_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Context asset - pagination handles staying with child
                asset = SliceAsset(
                    question_id=plan.question.id,
                    part_label=ctx_label,
                    image=ctx_img,
                    width=ctx_img.width,
                    height=ctx_img.height,
                    marks=0,
                    horizontal_offset=plan.question.horizontal_offset,  # Phase 6.10
                )
                assets.append(asset)
                emitted_contexts.add(ctx_label)
                
            except Exception as e:
                logger.warning(f"Could not get context for {ctx_part.label}: {e}")
        
        # Check if this leaf's bounds overlap with its parent's context
        # If leaf starts at same position as parent context, skip leaf (context already covers it)
        skip_leaf = False
        if context_parts:
            # Check if leaf bounds match the immediate parent's CONTEXT bounds
            parent = context_parts[-1]  # Last context is immediate parent
            if parent.context_bounds and leaf.bounds.top == parent.context_bounds.top:
                # Leaf starts at same position as parent context - context already covers this
                skip_leaf = True
                logger.debug(f"Skipping leaf {leaf.label} - overlaps with parent {parent.label} context (top={leaf.bounds.top})")
        
        if skip_leaf:
            continue
        
        # Now add the leaf itself
        try:
            # Add clearance for leaf parts with explicit marks
            has_marks = leaf.marks and leaf.marks.source == "explicit" and leaf.marks.value > 0
            leaf_img = provider.get_slice(leaf.label, add_mark_clearance=has_marks)
        except Exception as e:
            logger.warning(f"Could not get slice for {leaf.label}: {e}")
            continue
        
        # Apply question number repositioning for leaf parts
        # For single-part questions where leaf IS the root, apply overlay here
        is_leaf_root = leaf.label == str(plan.question.question_node.label)
        if is_leaf_root and seq_number is not None and plan.question.numeral_bbox:
            slice_left = leaf.bounds.left if leaf.bounds else 0
            leaf_img = _apply_question_number_overlay(
                leaf_img,
                seq_number,
                plan.question.numeral_bbox,
                slice_left_offset=slice_left,
            )
        
        # Scale if needed
        if config.scale_to_fit and leaf_img.width > config.available_width:
            scale_factor = config.available_width / leaf_img.width
            new_width = config.available_width
            new_height = int(leaf_img.height * scale_factor)
            leaf_img = leaf_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Leaf asset - pagination will calculate space dynamically
        asset = SliceAsset(
            question_id=plan.question.id,
            part_label=leaf.label,
            image=leaf_img,
            width=leaf_img.width,
            height=leaf_img.height,
            marks=leaf.marks.value,
            sequential_number=seq_number,
            numeral_bbox=None,  # Overlay already applied to image if needed
            horizontal_offset=plan.question.horizontal_offset,  # Phase 6.10
        )
        assets.append(asset)
    
    logger.debug(
        f"Composed {len(assets)} assets for {plan.question.id} "
        f"({len(emitted_contexts)} context + {len(included_leaves)} leaves)"
    )
    
    return assets


def compose_exam(
    result: SelectionResult,
    config: LayoutConfig,
    show_question_headers: bool = True,
) -> List[SliceAsset]:
    """
    Create assets for an entire exam selection.
    
    Composes assets for all selected questions in order.
    Optionally inserts text header assets before each question.
    
    Args:
        result: Selection result with all plans
        config: Layout configuration
        show_question_headers: If True, insert question ID text headers
        
    Returns:
        List of all SliceAssets for the exam
        
    Example:
        >>> assets = compose_exam(selection_result, config)
        >>> len(assets)
        17  # Total slices + headers across all questions
    """
    all_assets: List[SliceAsset] = []
    current_question_id = None
    
    # Header configuration
    HEADER_HEIGHT_PX = 60  # Height for text header box
    
    for seq_number, plan in enumerate(result.plans, start=1):
        question_id = plan.question.id
        
        # Insert text label before first part of each new question
        if question_id != current_question_id and show_question_headers:
            # Phase 2.1: Find root width and number box offset for precise alignment
            root_node_label = str(plan.question.question_node.label)
            root_part = next((p for p in plan.question.all_parts if p.label == root_node_label), None)
            
            root_width = None
            numeral_offset_x = 0
            if root_part and root_part.bounds:
                root_width = root_part.bounds.width
                if plan.question.numeral_bbox:
                    numeral_offset_x = plan.question.numeral_bbox[0] - root_part.bounds.left

            header_asset = SliceAsset(
                question_id=question_id,
                part_label="__header__",
                image=None,
                width=config.page_width,
                height=HEADER_HEIGHT_PX,
                marks=0,
                is_text_header=True,
                header_text=question_id,
                label_alignment_offset=plan.question.horizontal_offset,
                root_width=root_width,
                numeral_offset_x=numeral_offset_x,
            )
            all_assets.append(header_asset)
            current_question_id = question_id
        
        # Compose regular assets for this question
        question_assets = compose_question(plan, config, seq_number=seq_number)
        all_assets.extend(question_assets)
    
    logger.info(
        f"Composed {len(all_assets)} total assets from "
        f"{len(result.plans)} questions"
    )
    
    return all_assets
