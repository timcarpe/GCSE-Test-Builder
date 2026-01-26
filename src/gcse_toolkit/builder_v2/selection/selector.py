"""
Module: builder_v2.selection.selector

Purpose:
    Main question selection algorithm. Selects questions and parts
    to meet a target mark total while respecting constraints.

Key Functions:
    - select_questions(): Main entry point for selection

Key Classes:
    - Selector: Orchestrates the selection algorithm

Algorithm:
    1. Filter questions by requested topics
    2. Generate all valid options per question
    3. Greedy selection prioritizing topic coverage
    4. Prune parts if needed to hit exact marks
    5. Return SelectionResult

Dependencies:
    - gcse_toolkit.core.models: Question, SelectionPlan, SelectionResult
    - builder_v2.selection.options: Option generation
    - builder_v2.selection.config: SelectionConfig

Used By:
    - builder_v2.controller: Main build controller
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import List, Optional, Set

from gcse_toolkit.core.models import Question
from gcse_toolkit.core.models.selection import SelectionPlan, SelectionResult

from .config import SelectionConfig
from .options import generate_options, QuestionOptions
from .part_mode import PartMode

logger = logging.getLogger(__name__)


def _filter_topic_from_tail(question: Question, topic_set: set) -> set:
    """
    Remove mismatched topic children from tail only.
    
    Iterates from end backwards, removing mismatched parts until hitting a match.
    Example: [a:A, b:B, c:A, d:B, e:B, f:B] with topics={A} -> {a, b, c}
    """
    leaves = list(question.leaf_parts)
    
    # Find last index where topic matches (scanning from end)
    last_match_idx = len(leaves) - 1
    while last_match_idx >= 0:
        leaf = leaves[last_match_idx]
        effective_topic = leaf.topic or question.topic
        if effective_topic in topic_set:
            break
        last_match_idx -= 1
    
    if last_match_idx < 0:
        return None  # No matches at all
    
    # Keep all parts up to and including last_match_idx
    return {leaves[i].label for i in range(last_match_idx + 1)}


class SelectionError(Exception):
    """Error during question selection."""
    pass


def select_questions(
    questions: List[Question],
    config: SelectionConfig,
) -> SelectionResult:
    """
    Select questions to meet mark target.
    
    Main entry point for the selection algorithm.
    
    Algorithm:
    1. Filter by topic requirements
    2. Generate all valid options per question
    3. Greedy selection prioritizing topic coverage
    4. Prune parts if needed to hit exact marks
    
    Args:
        questions: Available questions to select from
        config: Selection configuration
        
    Returns:
        SelectionResult with selected plans
        
    Raises:
        SelectionError: If unable to find valid selection
        
    Invariants:
        - result.total_marks within config.tolerance of config.target_marks
        - No duplicate questions in selection
        
    Example:
        >>> result = select_questions(questions, SelectionConfig(target_marks=50))
        >>> result.within_tolerance
        True
    """
    selector = Selector(questions, config)
    return selector.run()


@dataclass
class Selector:
    """
    Question selection orchestrator.
    
    Manages the selection process including topic coverage,
    option generation, and greedy selection.
    
    Attributes:
        questions: Available questions
        config: Selection configuration
    """
    
    questions: List[Question]
    config: SelectionConfig
    
    # Internal state
    _rng: random.Random = field(init=False)
    _filtered_questions: List[Question] = field(init=False)
    _question_options: List[QuestionOptions] = field(init=False)
    _selected: List[SelectionPlan] = field(init=False, default_factory=list)
    _used_question_ids: Set[str] = field(init=False, default_factory=set)
    _covered_topics: Set[str] = field(init=False, default_factory=set)
    _current_marks: int = field(init=False, default=0)
    _size_preference: float = field(init=False, default=0.0)  # -1 to +1: favor small vs large
    
    # Selection breakdown tracking (for warnings)
    _pinned_marks: int = field(init=False, default=0)
    _keyword_marks: int = field(init=False, default=0)
    _keyword_parts_count: int = field(init=False, default=0)
    
    def __post_init__(self) -> None:
        """Initialize internal state."""
        self._rng = random.Random(self.config.seed)
        self._selected = []
        self._used_question_ids = set()
        self._covered_topics = set()
        self._current_marks = 0
        # Per-run size preference: -1 (favor small) to +1 (favor large)
        # This creates variety in whether we get few large or many small questions
        self._size_preference = self._rng.uniform(-1.0, 1.0)
    
    def run(self) -> SelectionResult:
        """
        Execute the selection algorithm.
        
        Returns:
            SelectionResult with selected plans
        """
        initial_seed = self.config.seed
        max_attempts = 5
        
        for attempt in range(max_attempts):
            result = self._run_selection_pass(attempt, initial_seed)
            
            # If not forcing topic coverage, or if successful, return
            if not self.config.force_topic_coverage or not self.config.topics:
                return result
                
            # Verify all requested topics are covered by AT LEAST one mark
            requested = self.config.topic_set
            covered = result.covered_topics
            missing = requested - covered
            
            if not missing:
                return result
                
            # Missing topics - retry with different seed
            logger.debug(f"Selection attempt {attempt + 1} failed to cover topics: {missing}. Retrying...")
            
        # If we reach here, we failed after all attempts
        logger.warning(
            f"Could not force topic representation for all requested topics after {max_attempts} attempts. "
            f"Missing: {missing}. Using best effort selection."
        )
        return result

    def _run_selection_pass(self, attempt: int, initial_seed: int) -> SelectionResult:
        """Single pass of the selection algorithm."""
        # Reset state for retry
        self._rng = random.Random(initial_seed + attempt)
        self._selected = []
        self._used_question_ids = set()
        self._covered_topics = set()
        self._current_marks = 0
        self._size_preference = self._rng.uniform(-1.0, 1.0)
        self._pinned_marks = 0
        self._keyword_marks = 0
        self._keyword_parts_count = 0

        # Step 1: Filter questions by topic (Bypass for pinned/matched in Keyword Mode)
        self._filter_by_topics()
        
        if not self._filtered_questions:
            logger.warning("No questions match topic filter")
            return self._build_result()
        
        # Step 2: Generate options for each question
        self._generate_all_options()
        
        # Step 3: Ensure keyword-matched/pinned questions included FIRST
        if self.config.keyword_mode or self.config.pinned_question_ids or self.config.pinned_part_labels:
            self._ensure_pinned_questions()
        
        # Step 4: Ensure topic coverage (only if budget remains)
        if self.config.force_topic_coverage and self.config.topics and self._current_marks < self.config.target_marks:
            self._ensure_topic_coverage()
        
        # Step 5: Greedy fill to target
        do_greedy = self.config.allow_greedy_fill
        if do_greedy is None:
            do_greedy = not self.config.keyword_mode
            
        if do_greedy and self._current_marks < self.config.target_marks:
            self._greedy_fill()
        
        # Step 6: Prune if over target
        from .part_mode import PartMode
        if self.config.part_mode != PartMode.ALL and self._current_marks > self.config.target_marks:
            self._prune_to_target()
        
        # Step 7: Log warnings
        self._check_warnings()
        
        return self._build_result()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Topic Filtering
    # ─────────────────────────────────────────────────────────────────────────
    
    def _filter_by_topics(self) -> None:
        """Filter questions to only those matching requested topics."""
        if not self.config.topics:
            # No topic filter - use all questions
            self._filtered_questions = list(self.questions)
        else:
            topic_set = self.config.topic_set
            # Include if question.topic matches OR any part.topic matches
            # OR if question is pinned or keyword-matched (bypass topic filter)
            filtered = []
            
            # Pre-calculate pinned/matched IDs for fast lookup
            special_ids = self.config.pinned_question_ids | set(self.config.keyword_matched_labels.keys())
            for pin in self.config.pinned_part_labels:
                if "::" in pin:
                    special_ids.add(pin.split("::")[0])

            for q in self.questions:
                if q.id in special_ids:
                    filtered.append(q)
                    continue
                if q.topic in topic_set:
                    filtered.append(q)
                    continue
                # Check parts
                for part in q.all_parts:
                    if part.topic and part.topic in topic_set:
                        filtered.append(q)
                        break
            self._filtered_questions = filtered
        
        logger.debug(
            f"Filtered to {len(self._filtered_questions)}/{len(self.questions)} "
            f"questions by topic"
        )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Option Generation
    # ─────────────────────────────────────────────────────────────────────────
    
    def _generate_all_options(self) -> None:
        """Generate options for all filtered questions."""
        from .part_mode import PartMode
        self._question_options = []
        for q in self._filtered_questions:
            # In keyword mode, restrict options to matched labels
            if self.config.keyword_mode:
                matched_labels = self.config.keyword_matched_labels.get(q.id, set())
                # Add any pinned part labels for this question
                pinned_for_q = {
                    label.split("::")[-1]  # Extract label from "qid::label"
                    for label in self.config.pinned_part_labels
                    if label.startswith(f"{q.id}::")
                }
                # Check if FULL question is pinned
                is_full_pinned = q.id in self.config.pinned_question_ids
                
                # Combine matched and pinned labels
                allowed_labels = matched_labels | pinned_for_q
                
                # If neither pinned nor matched, this question generates NO options in keyword mode
                # Unless we are explicitly allowing greedy fill from the general pool
                do_greedy = self.config.allow_greedy_fill
                if do_greedy is None:
                    do_greedy = not self.config.keyword_mode
                
                if not allowed_labels and not is_full_pinned and not do_greedy:
                    continue

                # Expand allowed labels to include children if a parent was pinned/matched
                # This handles non-leaf pinning (e.g. pinning "1(a)" includes "1(a)(i)")
                expanded_labels = set(allowed_labels)
                for label in allowed_labels:
                    node = q.get_part(label)
                    if node:
                        # iter_all yields the node itself then all descendants
                        for p in node.iter_all():
                            expanded_labels.add(p.label)
                
                opts = generate_options(
                    q,
                    part_mode=PartMode.SKIP,  # Keyword Mode always uses SKIP logic
                    allowed_labels=expanded_labels if expanded_labels else None,
                )
            else:
                # Topic filtering respects part_mode
                allowed_labels = None
                if self.config.topics:
                    topic_set = self.config.topic_set
                    
                    if self.config.part_mode == PartMode.ALL:
                        # ALL: No child filtering - question already passed topic filter
                        allowed_labels = None
                    elif self.config.part_mode == PartMode.PRUNE:
                        # PRUNE: Remove mismatched from tail only (contiguous)
                        allowed_labels = _filter_topic_from_tail(q, topic_set)
                    else:  # SKIP
                        # SKIP: Remove all mismatched from anywhere
                        allowed_labels = {
                            leaf.label for leaf in q.leaf_parts
                            if (leaf.topic or q.topic) in topic_set
                        }
                
                opts = generate_options(
                    q,
                    part_mode=self.config.part_mode,
                    allowed_labels=allowed_labels,
                )
            self._question_options.append(opts)
        
        logger.debug(
            f"Generated options for {len(self._question_options)} questions"
        )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Topic Coverage
    # ─────────────────────────────────────────────────────────────────────────
    
    def _ensure_topic_coverage(self) -> None:
        """
        Select at least one question per requested topic.
        
        Prioritizes topics that only have a few questions available.
        Refactored to check part-level topics.
        """
        required_topics = self.config.topic_set
        
        # Determine available candidates for each topic
        # candidates_by_topic[topic] = List[QuestionOptions] containing that topic
        candidates_by_topic: dict[str, List[QuestionOptions]] = {}
        
        for opts in self._question_options:
            q = opts.question
            topics_in_q = set()
            if q.topic in required_topics:
                topics_in_q.add(q.topic)
            for part in q.all_parts:
                if part.topic and part.topic in required_topics:
                    topics_in_q.add(part.topic)
            
            for t in topics_in_q:
                candidates_by_topic.setdefault(t, []).append(opts)
        
        # Sort topics by availability (fewest first), then shuffle within tiers
        # to add randomness while preserving priority for rare topics
        sorted_topics = sorted(candidates_by_topic.keys(), key=lambda t: len(candidates_by_topic[t]))
        
        # Shuffle topics with same availability count for variability
        self._rng.shuffle(sorted_topics)
        
        for topic in sorted_topics:
            if topic in self._covered_topics:
                continue
            
            candidates = candidates_by_topic.get(topic, [])
            if not candidates:
                logger.warning(f"No questions available for topic: {topic}")
                continue
            
            # Pick best question for this topic
            best = self._pick_best_for_topic(candidates, topic)
            if best:
                self._add_selection(best)
    
    def _pick_best_for_topic(
        self, candidates: List[QuestionOptions], target_topic: str
    ) -> Optional[SelectionPlan]:
        """Pick the best option from topic candidates."""
        remaining_marks = self.config.target_marks - self._current_marks
        
        # Filter out already-used questions
        available = [
            c for c in candidates 
            if c.question.id not in self._used_question_ids
        ]
        
        if not available:
            return None
            
        # Shuffle available candidates to avoid bias
        self._rng.shuffle(available)
        
        # Find best option that fits remaining budget AND covers the topic
        best_option: Optional[SelectionPlan] = None
        best_score = -1
        
        for opts in available:
            # We need an option that actually includes the target topic!
            # Search through possible options for this question
            potential_options = list(opts.options_in_range(1, max(1, remaining_marks)))
            if not potential_options:
                # Even if it exceeds budget, we might need a small option if forced
                potential_options = [opts.options[-1]] if opts.options else []

            # Pick the best among options that cover the topic
            # Budget-aware scoring: favor options close to (remaining_marks / remaining_topics)
            remaining_topics = len(self.config.topic_set - self._covered_topics)
            target_per_topic = remaining_marks / max(1, remaining_topics)
            
            # Filter potential options to only those that actually include target_topic
            topic_covering_options = []
            for option in potential_options:
                # Check if ANY included leaf has the topic
                for leaf in option.included_leaves:
                    effective_topic = leaf.topic or opts.question.topic
                    if effective_topic == target_topic:
                        topic_covering_options.append(option)
                        break
            
            if not topic_covering_options:
                continue
                
            # Score each topic-covering option
            for option in topic_covering_options:
                # 1. Proximity to budget-aware target (0-10 scale)
                # Lower difference = higher score
                diff = abs(option.marks - target_per_topic)
                proximity_score = max(0, 10 - diff)
                
                # 2. Preference for full questions
                full_bonus = 5.0 if option.is_full_question else 0
                
                # 3. Deterministic Jitter (using self._rng)
                jitter = self._rng.random() * 5.0
                
                score = proximity_score + full_bonus + jitter
                
                if score > best_score:
                    best_score = score
                    best_option = option
        
        return best_option
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 3.5: Pinned Questions (Keyword Mode)
    # ─────────────────────────────────────────────────────────────────────────
    
    def _ensure_pinned_questions(self) -> None:
        """
        Select pinned parts and questions, then fill with keyword matches.
        
        Merged approach:
        1. Identify all questions with ANY intent (Pin Part, Pin Q, or Keyword Match).
        2. Combine labels for that question.
        3. Force Phase 1 & 2 (Pins), then fill Phase 3 (Keywords) while budget allows.
        """
        # Step 1: Collect all "Intended" questions to avoid pin/keyword blocking
        intended_qids = (
            set(self.config.pinned_question_ids) |
            {p.split("::")[0] for p in self.config.pinned_part_labels if "::" in p} |
            set(self.config.keyword_matched_labels.keys())
        )
        
        # Step 2: Handle Explicit Pins (Phase 1 & 2)
        # Pins are processed first and always FORCED (even if they exceed budget)
        for qid in intended_qids:
            if qid in self._used_question_ids:
                continue
            
            is_q_pinned = qid in self.config.pinned_question_ids
            pinned_labels = {
                pin.split("::")[-1] for pin in self.config.pinned_part_labels 
                if pin.startswith(f"{qid}::")
            }
            
            if not is_q_pinned and not pinned_labels:
                # Just a keyword match - skip to Phase 3 loop
                continue
                
            # Pins are forced
            self._select_specific_question(qid, force=True)

        # Step 3: Handle Keyword Matches (Phase 3)
        # Fill remaining budget from match pool
        matched_ids = list(self.config.keyword_matched_labels.keys())
        self._rng.shuffle(matched_ids)
        
        for qid in matched_ids:
            if qid in self._used_question_ids:
                continue
            
            # Keyword backfill control
            if not self.config.allow_keyword_backfill:
                continue
            
            # Keyword matches only added if they fit budget
            self._select_specific_question(qid, force=False, is_keyword=True)

    def _select_specific_question(self, qid: str, force: bool, is_keyword: bool = False) -> None:
        """
        Select a specific question by ID using its generated options.
        
        Args:
            qid: Question ID to select
            force: If True, select smallest option even if it exceeds budget.
                   If False, skip if no option fits budget.
            is_keyword: If True, track as keyword match rather than pin.
        """
        # Find question in options
        opts = None
        for q_opts in self._question_options:
            if q_opts.question.id == qid:
                opts = q_opts
                break
        
        if not opts or not opts.options:
            if force:
                logger.warning(f"Pinned question {qid} not found or has no options")
            return
        
        # Select best option for remaining budget
        remaining = self.config.target_marks - self._current_marks
        option = opts.best_option_for_marks(remaining)
        
        if option is None and force:
            # Force: Take smallest option even if it goes over
            option = opts.options[-1]
            logger.debug(f"Force-selecting pinned question {qid} (exceeds budget)")
        
        if option:
            self._add_selection(option, is_keyword=is_keyword)
            if force:
                logger.debug(f"Selected pinned question: {qid}")
            else:
                logger.debug(f"Selected keyword-matched question: {qid}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Greedy Fill
    # ─────────────────────────────────────────────────────────────────────────
    
    def _greedy_fill(self) -> None:
        """
        Fill to target using first-fit from shuffled options.
        
        Simplified algorithm:
        1. Shuffle question options for seed-based variety
        2. For each question, find best option that fits remaining budget
        3. Stop when target reached or no more fitting options
        
        Never exceeds target + tolerance.
        """
        max_allowed = self.config.target_marks + self.config.tolerance
        
        # Shuffle once for seed-based variety
        candidates = list(self._question_options)
        self._rng.shuffle(candidates)
        
        for opts in candidates:
            # Stop if we've reached or exceeded target
            if self._current_marks >= self.config.target_marks:
                break
            
            # Skip already-used questions
            if opts.question.id in self._used_question_ids:
                continue
            
            # Check question count limit
            if (
                self.config.max_questions is not None
                and len(self._selected) >= self.config.max_questions
            ):
                break
            
            # Find fitting options (within tolerance limit)
            remaining = max_allowed - self._current_marks
            fitting = list(opts.options_in_range(1, remaining))
            
            if not fitting:
                continue
            
            # SIZE PREFERENCE: Bias selection based on per-run preference
            # _size_preference: -1.0 to +1.0 (favor small to favor large)
            if len(fitting) == 1:
                option = fitting[0]
            elif self._size_preference > 0.3:
                # Favor large: pick from largest options (fitting is sorted desc by marks)
                pool = fitting[:min(3, len(fitting))]
                option = self._rng.choice(pool)
            elif self._size_preference < -0.3:
                # Favor small: pick from smallest options
                pool = fitting[-min(3, len(fitting)):]
                option = self._rng.choice(pool)
            else:
                # Neutral: pick randomly from all fitting options
                option = self._rng.choice(fitting)
            
            # Add this option
            self._add_selection(option)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Pruning
    # ─────────────────────────────────────────────────────────────────────────
    
    def _prune_to_target(self) -> None:
        """
        Prune parts from selected questions to hit exact target.
        
        Removes lowest-value parts one at a time until within tolerance.
        """
        from .pruning import prune_selection
        
        if self.config.is_within_tolerance(self._current_marks):
            return
        
        self._selected = prune_selection(
            plans=self._selected,
            target_marks=self.config.target_marks,
            tolerance=self.config.tolerance,
            part_mode=self.config.part_mode,
        )
        
        # Recalculate marks
        self._current_marks = sum(p.marks for p in self._selected)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Warnings
    # ─────────────────────────────────────────────────────────────────────────
    
    def _check_warnings(self) -> None:
        """
        Check for conditions that warrant user warnings.
        
        Logs warnings if:
        1. Mark target exceeded significantly (usually due to PartMode.ALL/PRUNE)
        2. Topics included that were not requested (mismatches due to coarse filtering)
        """
        from .part_mode import PartMode
        
        mode_name = self.config.part_mode.name
        
        # 1. Mark Target Check
        # Check if we exceeded target + tolerance
        max_allowed = self.config.target_marks + self.config.tolerance
        if self._current_marks > max_allowed:
            excess = self._current_marks - self.config.target_marks
            logger.warning(
                f"Exceeded mark target by {excess} marks (Total: {self._current_marks}, Target: {self.config.target_marks}). "
                f"You are using '{mode_name}' mode. "
                "'SKIP' mode may allow more precise mark targeting."
            )
        
        # 2. Topic Mismatch Check
        # Only relevant if specific topics were requested
        if self.config.topics:
            requested = self.config.topic_set
            mismatched_topics = set()
            
            for plan in self._selected:
                # Check each included leaf part
                for leaf in plan.included_leaves:
                    # Effective topic: leaf topic -> question topic
                    effective_topic = leaf.topic or plan.question.topic
                    if effective_topic and effective_topic not in requested:
                        mismatched_topics.add(effective_topic)
            
            if mismatched_topics:
                topics_str = ", ".join(sorted(mismatched_topics)[:3])
                if len(mismatched_topics) > 3:
                    topics_str += "..."
                
                if self.config.part_mode == PartMode.SKIP:
                    logger.warning(
                        f"PARITY FAILURE (SKIP): Included parts with mismatched topics: '{topics_str}'. "
                        "This indicates a logic error or metadata inconsistency."
                    )
                elif self.config.part_mode == PartMode.PRUNE:
                    logger.warning(
                        f"PARITY WARNING (PRUNE): Included parts with mismatched topics: '{topics_str}'. "
                        "Try 'SKIP' mode for strict topic matching."
                    )
                else:
                    logger.warning(
                        f"Included parts with mismatched topics (e.g., '{topics_str}'). "
                        f"You are using '{mode_name}' mode. "
                        "Try 'SKIP' mode for more accurate topic matching."
                    )
        
        # 3. Keyword Breakdown (Requested by user)
        if self.config.keyword_mode:
            logger.warning(
                f"pinned questions have {self._pinned_marks} marks and {self._keyword_parts_count} "
                f"question parts were added from keyword searches to meet mark target of {self.config.target_marks}."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    
    def _add_selection(self, plan: SelectionPlan, is_keyword: bool = False) -> None:
        """Add a plan to the selection and track covered topics."""
        self._selected.append(plan)
        self._used_question_ids.add(plan.question.id)
        
        # Track statistics
        if is_keyword:
            self._keyword_marks += plan.marks
            # Number of leaf parts added
            self._keyword_parts_count += len(plan.included_leaves)
        else:
            self._pinned_marks += plan.marks
        
        # Add all covered topics from INCLUDED parts
        # A topic is covered if an included leaf has it, OR if a leaf inherits it
        for leaf in plan.included_leaves:
            effective_topic = leaf.topic or plan.question.topic
            if effective_topic:
                self._covered_topics.add(effective_topic)
        
        self._current_marks += plan.marks
        
        logger.debug(
            f"Selected {plan.question.id}: {plan.marks} marks "
            f"(total: {self._current_marks})"
        )
    
    def _build_result(self) -> SelectionResult:
        """Build final SelectionResult."""
        return SelectionResult(
            plans=tuple(self._selected),
            target_marks=self.config.target_marks,
            tolerance=self.config.tolerance,
        )
