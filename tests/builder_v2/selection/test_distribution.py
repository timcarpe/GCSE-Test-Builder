"""
Tests for selection determinism and distribution.

Verifies:
1. Determinism: Same inputs + same seed = exact same output
2. Distribution: Different seeds = varied output (given sufficient freedom)

Verified: 2025-12-12
"""

import pytest
from pathlib import Path
from collections import Counter

from gcse_toolkit.core.models.marks import Marks
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.core.models.parts import Part, PartKind
from gcse_toolkit.core.models.questions import Question
from gcse_toolkit.builder_v2.selection import (
    SelectionConfig,
    select_questions,
)


@pytest.fixture
def question_pool() -> list[Question]:
    """
    Create a large pool of similar questions to test distribution.
    
    Creates 20 questions, each worth 10 marks, but with different IDs.
    This gives the selector many valid options to hit a target of e.g. 50 marks.
    """
    questions = []
    for i in range(20):
        # Create a question with 2 parts (5 marks each)
        pid = f"q{i}"
        
        leaves = [
            Part(
                f"{i}(a)", PartKind.LETTER, Marks.explicit(5), 
                SliceBounds(0, 50)
            ),
            Part(
                f"{i}(b)", PartKind.LETTER, Marks.explicit(5), 
                SliceBounds(50, 100)
            )
        ]
        
        node = Part(
            str(i), PartKind.QUESTION, Marks.aggregate(leaves),
            SliceBounds(0, 100), children=tuple(leaves)
        )
        
        q = Question(
            id=f"question_{i}",
            exam_code="0478",
            year=2021,
            paper=1,
            variant=1,
            topic="General",
            question_node=node,
            composite_path=Path("/test"),
            regions_path=Path("/test"),
        )
        questions.append(q)
    return questions


class TestSelectionProperties:
    """Property-based tests for selection."""

    def test_determinism_when_same_seed_then_same_selection(
        self, question_pool
    ):
        """
        Property: f(questions, seed=X) == f(questions, seed=X)
        
        Even with random choices available, the same seed must produce
        identical results for reproducibility.
        """
        # Arrange
        config = SelectionConfig(
            target_marks=50,
            seed=42,
            topics=["General"]
        )
        
        # Act
        result1 = select_questions(question_pool, config)
        result2 = select_questions(question_pool, config)
        
        # Assert
        # Check plan IDs match exactly
        ids1 = [plan.question.id for plan in result1.plans]
        ids2 = [plan.question.id for plan in result2.plans]
        assert ids1 == ids2
        
        # Check parts match exactly (pruning determinism)
        parts1 = set()
        for plan in result1.plans:
            parts1.update(f"{plan.question.id}:{p.label}" for p in plan.included_leaves)
            
        parts2 = set()
        for plan in result2.plans:
            parts2.update(f"{plan.question.id}:{p.label}" for p in plan.included_leaves)
            
        assert parts1 == parts2

    def test_distribution_when_multiple_seeds_then_varied_selection(
        self, question_pool
    ):
        """
        Property: f(questions, seed=X) != f(questions, seed=Y) generally.
        
        With a large pool of identical-value questions, running with
        different seeds should result in different selections.
        """
        # Arrange
        # Target 50 marks from pool of 200 marks (10 marks/question)
        # We need 5 questions. There are C(20, 5) = 15,504 combinations.
        config_base = SelectionConfig(
            target_marks=50,
            topics=["General"],
            # Enable randomness by NOT forcing topic coverage (since all same topic)
            # or by having multiple options per topic.
            # Here we rely on the greedy fill randomness.
        )
        
        selections = []
        seeds = [1, 2, 3, 4, 5]
        
        # Act
        for seed in seeds:
            config = SelectionConfig(
                target_marks=50,
                seed=seed,
                topics=["General"]
            )
            result = select_questions(question_pool, config)
            # Store set of selected IDs
            selections.append(frozenset(p.question.id for p in result.plans))
            
        # Assert
        # Check that we got at least 3 different combinations out of 5 runs
        # (It's theoretically possible to get same result by chance, but unlikely)
        unique_selections = set(selections)
        assert len(unique_selections) >= 3, \
            f"Expected variety, got {len(unique_selections)} unique sets: {selections}"

    def test_leaf_distribution_when_varied_seeds_then_uniform_ish(
        self, question_pool
    ):
        """
        Property: Over many runs, selection frequency should be roughly distributed.
        This verifies we aren't biased towards specific array modifications.
        """
        # Arrange
        # Select 1 question (10 marks) out of 20
        # Expected prob for any question = 1/20 = 5%
        runs = 100
        counts = Counter()
        
        # Act
        for i in range(runs):
            config = SelectionConfig(
                target_marks=10, 
                seed=i,
                topics=["General"]
            )
            result = select_questions(question_pool, config)
            for plan in result.plans:
                counts[plan.question.id] += 1
                
        # Assert
        # Every question should have been picked at least once (with high probability)
        # In 100 picks of 1/20 chance items, P(0 selections) is very low
        selected_count = len(counts)
        assert selected_count > 10, \
            f"Only picked {selected_count}/20 unique questions in {runs} runs"
