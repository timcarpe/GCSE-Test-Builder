"""
Module: builder_v2.selection.pruning

Purpose:
    Prune parts from selected questions to hit exact mark targets.
    Removes lowest-value parts one at a time until within tolerance.

Key Functions:
    - prune_to_target(): Prune a single plan to hit target
    - prune_selection(): Prune across multiple plans

Dependencies:
    - gcse_toolkit.core.models: Part, SelectionPlan

Used By:
    - builder_v2.selection.selector: Main selector
"""

from __future__ import annotations

import logging
from typing import List, Optional

from gcse_toolkit.core.models import Part
from gcse_toolkit.core.models.selection import SelectionPlan

logger = logging.getLogger(__name__)


from gcse_toolkit.builder_v2.selection.part_mode import PartMode


def prune_to_target(
    plan: SelectionPlan,
    target_marks: int,
    *,
    min_parts: int = 1,
    part_mode: PartMode = PartMode.SKIP,
) -> SelectionPlan:
    """
    Prune parts from a plan to hit a target mark value.
    
    Removes parts one at a time until marks <= target.
    Respects PartMode constraints:
    - ALL: No pruning allowed (returns as is)
    - PRUNE: Only removes from end (contiguous suffix)
    - SKIP: Removes lowest-value parts (anywhere)
    
    Args:
        plan: Plan to prune
        target_marks: Target marks to hit (will not exceed)
        min_parts: Minimum number of parts to keep
        part_mode: Pruning constraint mode
        
    Returns:
        New SelectionPlan with parts removed (original unchanged)
        
    Example:
        >>> pruned = prune_to_target(plan, 5, part_mode=PartMode.PRUNE)
    """
    if plan.marks <= target_marks:
        return plan
        
    if part_mode == PartMode.ALL:
        # Cannot prune in ALL mode
        return plan

    current_marks = plan.marks
    # Initialize set of included labels
    included = set(p.label for p in plan.included_leaves)
    
    # We will loop until we are under target or hit min_parts
    while current_marks > target_marks:
        if len(included) <= min_parts:
            break
            
        # Determine candidate parts to remove based on mode
        # Re-resolve leaves from included set to get their objects
        # We need them sorted to find "last" or "cheapest"
        # Since we only have leaf objects from the plan, we filter them
        current_leaves = [
            p for p in plan.included_leaves 
            if p.label in included
        ]
        
        if not current_leaves:
            break
            
        victim = None
        
        if part_mode == PartMode.PRUNE:
            # PRUNE: Must remove the LAST part (highest index/bounds)
            # Assuming leaves are essentially ordered by appearance in question
            # We can use bounds or just trust the list order if it's stable?
            # Safe bet: sort by bounds (top/left) or just extraction order
            # Included leaves in plan are usually in document order
            
            # Sort by bounds to find true "last" part
            sorted_leaves = sorted(
                current_leaves, 
                key=lambda p: (p.bounds.top if p.bounds else 0, p.bounds.left if p.bounds else 0)
            )
            victim = sorted_leaves[-1]
            
        else:  # PartMode.SKIP and default
            # SKIP: Remove lowest mark value part
            # Sort by marks ascending (lowest first)
            sorted_leaves = sorted(current_leaves, key=lambda p: p.marks.value)
            victim = sorted_leaves[0]
            
        # Remove the victim
        included.remove(victim.label)
        current_marks -= victim.marks.value
        
        logger.debug(
            f"Pruned {victim.label} ({victim.marks.value} marks) [{part_mode.name}], "
            f"now {current_marks} marks"
        )
    
    return SelectionPlan(
        question=plan.question,
        included_parts=frozenset(included),
    )


def prune_selection(
    plans: List[SelectionPlan],
    target_marks: int,
    tolerance: int,
    part_mode: PartMode = PartMode.SKIP,
    protected_labels: set[str] | None = None,
) -> List[SelectionPlan]:
    """
    Prune parts across multiple plans to hit target.
    
    Strategy:
    1. Find plans with removable parts (respecting mode and protected labels)
    2. Remove lowest-mark parts one at a time
    3. Stop when within tolerance
    
    Args:
        plans: List of plans to prune
        target_marks: Target total marks
        tolerance: Acceptable deviation
        part_mode: Pruning constraint mode
        protected_labels: Set of "qid::label" strings that must not be removed (pinned parts)
        
    Returns:
        New list of plans with parts pruned
    """
    if not plans:
        return []
        
    if part_mode == PartMode.ALL:
        return list(plans)
    
    protected = protected_labels or set()
    
    # Calculate current total
    current_total = sum(p.marks for p in plans)
    
    if current_total <= target_marks + tolerance:
        return list(plans)  # Already within tolerance
    
    # Create mutable copies
    result = list(plans)
    
    # Loop until we hit target or can't prune anymore
    while current_total > target_marks + tolerance:
        # Identify all possible candidates for removal across ALL plans
        # A candidate is: (plan_idx, leaf_to_remove, marks_saved)
        candidates: List[tuple[int, Part, int]] = []
        
        has_prunable_plans = False
        
        for idx, plan in enumerate(result):
            if len(plan.included_leaves) <= 1:
                continue  # Can't remove last part of a question
            
            has_prunable_plans = True
            current_leaves = list(plan.included_leaves)
            
            # Get question ID for protected check
            qid = plan.question.id
            
            # Filter out protected leaves
            prunable_leaves = [
                leaf for leaf in current_leaves
                if f"{qid}::{leaf.label}" not in protected
            ]
            
            # If all leaves are protected, skip this plan
            if not prunable_leaves:
                continue
            
            # Must retain at least one leaf (protected or not)
            # Calculate how many leaves we can remove
            protected_count = len(current_leaves) - len(prunable_leaves)
            if protected_count >= len(current_leaves) - 1:
                # Too many protected, can't prune without removing last leaf
                continue
            
            # Determine valid candidates for this plan based on mode
            if part_mode == PartMode.PRUNE:
                # Can only remove the LAST part (if it's not protected)
                # Sort by bounds
                sorted_leaves = sorted(
                    prunable_leaves,
                    key=lambda p: (p.bounds.top if p.bounds else 0, p.bounds.left if p.bounds else 0)
                )
                victim = sorted_leaves[-1]
                candidates.append((idx, victim, victim.marks.value))
                
            else:  # SKIP
                # Can remove ANY non-protected part
                for leaf in prunable_leaves:
                    candidates.append((idx, leaf, leaf.marks.value))
        
        if not candidates:
            break  # No more moves possible
            
        # Pick best candidate (lowest marks)
        # Sort by marks ascending
        candidates.sort(key=lambda x: x[2])
        best_candidate = candidates[0]
        
        plan_idx, leaf, marks = best_candidate
        
        # Absolute error check: Stop if pruning makes us further from target
        # e.g., if target is 10, and we are at 12, pruning 5 marks makes it 7.
        # Error before: |10 - 12| = 2. Error after: |10 - 7| = 3.
        # Since 3 > 2, we STOP.
        current_error = abs(target_marks - current_total)
        new_error = abs(target_marks - (current_total - marks))
        
        if new_error > current_error:
            logger.debug(
                f"Stopping pruning: removing {leaf.label} ({marks} marks) "
                f"increases error from {current_error} to {new_error}"
            )
            break
        
        # Apply removal
        plan = result[plan_idx]
        new_included = plan.included_parts - {leaf.label}
        result[plan_idx] = SelectionPlan(
            question=plan.question,
            included_parts=new_included,
        )
        current_total -= marks
        
        logger.debug(
            f"Pruned {leaf.label} from {plan.question.id} [{part_mode.name}], "
            f"total now {current_total}"
        )
            
    return result


def find_prunable_parts(plan: SelectionPlan) -> List[Part]:
    """
    Find parts that can be pruned from a plan (DEPRECATED/Unused in new logic?).
    
    This helper assumes SKIP mode (sorts by marks). 
    Keeping for backward compat if needed, but warning: ignores PartMode.
    """
    if len(plan.included_leaves) <= 1:
        return []
    
    return sorted(plan.included_leaves, key=lambda p: p.marks.value)


def calculate_prune_amount(
    plans: List[SelectionPlan],
    target_marks: int,
) -> int:
    """
    Calculate how many marks need to be pruned.
    
    Args:
        plans: Current selection
        target_marks: Target to hit
        
    Returns:
        Positive value = marks to remove, 0 = at or below target
    """
    current = sum(p.marks for p in plans)
    return max(0, current - target_marks)
