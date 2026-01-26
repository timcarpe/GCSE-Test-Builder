"""
Tests for seed-based variability in selection.

Verifies:
1. Same seed produces identical results (determinism)
2. Different seeds produce variety
3. All matching parts get used across many runs (distribution)
"""

import pytest
from pathlib import Path
from collections import Counter

from gcse_toolkit.core.models import Question, Part, Marks, SliceBounds
from gcse_toolkit.builder_v2.selection.selector import select_questions
from gcse_toolkit.builder_v2.selection.config import SelectionConfig


def create_test_question(qid: str, part_marks: list[int]) -> Question:
    """Create a test question with specified part marks."""
    leaves = []
    for i, m in enumerate(part_marks):
        leaves.append(Part(
            label=f"{qid}({chr(97+i)})",
            kind="letter",
            marks=Marks.explicit(m),
            bounds=SliceBounds(top=i*100, bottom=(i+1)*100, left=0, right=100),
        ))
    
    root = Part(
        label=qid,
        kind="question",
        marks=Marks.aggregate(leaves),
        bounds=SliceBounds(top=0, bottom=len(leaves)*100, left=0, right=100),
        children=tuple(leaves),
    )
    
    return Question(
        id=qid, exam_code="0000", year=2024, paper=1, variant=1,
        topic="Test", question_node=root,
        composite_path=Path("/tmp/fake.png"),
        regions_path=Path("/tmp/fake.json"),
    )


@pytest.fixture
def varied_questions() -> list[Question]:
    """Questions with varied sizes for testing."""
    return [
        create_test_question("q1", [2, 3]),       # 5 total
        create_test_question("q2", [4, 4]),       # 8 total
        create_test_question("q3", [1, 2, 3]),    # 6 total
        create_test_question("q4", [5]),          # 5 total (atomic)
        create_test_question("q5", [3, 3, 3]),    # 9 total
        create_test_question("q6", [2, 2, 2, 2]), # 8 total
    ]


class TestSeedDeterminism:
    """Tests for deterministic selection with same seed."""
    
    def test_same_seed_produces_identical_results(self, varied_questions):
        """Same seed should always produce the same selection."""
        seed = 12345
        
        config1 = SelectionConfig(target_marks=15, seed=seed)
        config2 = SelectionConfig(target_marks=15, seed=seed)
        
        result1 = select_questions(varied_questions, config1)
        result2 = select_questions(varied_questions, config2)
        
        assert result1.total_marks == result2.total_marks
        assert [p.question.id for p in result1.plans] == [p.question.id for p in result2.plans]
        for p1, p2 in zip(result1.plans, result2.plans):
            assert p1.included_parts == p2.included_parts


class TestSeedVariability:
    """Tests for variety across different seeds."""
    
    def test_different_seeds_produce_different_results(self, varied_questions):
        """Different seeds should produce variety in selection."""
        results = set()
        
        for seed in range(100):
            config = SelectionConfig(target_marks=15, seed=seed)
            result = select_questions(varied_questions, config)
            # Create a hashable representation
            selection_key = tuple(sorted(
                (p.question.id, frozenset(p.included_parts))
                for p in result.plans
            ))
            results.add(selection_key)
        
        # At least 5 unique selections from 100 seeds
        assert len(results) >= 5, f"Only {len(results)} unique selections from 100 seeds"
    
    def test_size_preference_creates_variety(self, varied_questions):
        """Size preference should cause some seeds to favor large/small questions."""
        large_selections = 0
        small_selections = 0
        
        for seed in range(50):
            config = SelectionConfig(target_marks=15, seed=seed)
            result = select_questions(varied_questions, config)
            
            # Count questions by average marks per question
            if result.plans:
                avg_marks = result.total_marks / len(result.plans)
                if avg_marks > 5:  # Fewer questions = larger avg
                    large_selections += 1
                elif avg_marks < 4:  # More questions = smaller avg
                    small_selections += 1
        
        # Should have at least some variety in size patterns
        assert large_selections > 0, "No large-question-favoring seeds found"
        assert small_selections > 0, "No small-question-favoring seeds found"


class TestPartDistribution:
    """Tests for balanced part usage across many selections."""
    
    @pytest.fixture
    def large_question_set(self) -> list[Question]:
        """
        Realistic exam structure with ~500 leaf parts.
        
        Structure varies to match real exam patterns:
        - Some questions: 1(a), 1(b), 1(c) - letter-only leaves
        - Some questions: 1(a)(i), 1(a)(ii), 1(b) - mixed depth
        - Some questions: 1(a)(i), 1(a)(ii), 1(b)(i), 1(b)(ii) - all nested
        """
        questions = []
        roman = ["i", "ii", "iii", "iv"]
        
        for q_idx in range(80):  # 80 questions = ~500 parts
            pattern = q_idx % 4
            leaves = []
            y_offset = 0
            
            if pattern == 0:
                # Pattern A: Flat letters - 1(a), 1(b), 1(c), 1(d)
                for p_idx in range(4):
                    leaves.append(Part(
                        label=f"{q_idx+1}({chr(97+p_idx)})",
                        kind="letter",
                        marks=Marks.explicit((p_idx % 3) + 2),  # 2-4 marks
                        bounds=SliceBounds(top=y_offset, bottom=y_offset+100, left=0, right=100),
                    ))
                    y_offset += 100
                    
            elif pattern == 1:
                # Pattern B: Mixed - 1(a)(i), 1(a)(ii), 1(b), 1(c)
                for sub_idx in range(2):
                    leaves.append(Part(
                        label=f"{q_idx+1}(a)({roman[sub_idx]})",
                        kind="roman",
                        marks=Marks.explicit(sub_idx + 1),  # 1-2 marks
                        bounds=SliceBounds(top=y_offset, bottom=y_offset+100, left=0, right=100),
                    ))
                    y_offset += 100
                for p_idx in range(2):
                    leaves.append(Part(
                        label=f"{q_idx+1}({chr(98+p_idx)})",
                        kind="letter",
                        marks=Marks.explicit(3),  # 3 marks
                        bounds=SliceBounds(top=y_offset, bottom=y_offset+100, left=0, right=100),
                    ))
                    y_offset += 100
                    
            elif pattern == 2:
                # Pattern C: Deep nested - 1(a)(i), 1(a)(ii), 1(b)(i), 1(b)(ii), 1(c)(i), 1(c)(ii)
                for letter_idx in range(3):
                    for sub_idx in range(2):
                        leaves.append(Part(
                            label=f"{q_idx+1}({chr(97+letter_idx)})({roman[sub_idx]})",
                            kind="roman",
                            marks=Marks.explicit(sub_idx + 1),  # 1-2 marks
                            bounds=SliceBounds(top=y_offset, bottom=y_offset+100, left=0, right=100),
                        ))
                        y_offset += 100
                        
            else:
                # Pattern D: Heavy - 1(a)(i), 1(a)(ii), 1(a)(iii), 1(b)(i), 1(b)(ii), 1(c), 1(d)
                for sub_idx in range(3):
                    leaves.append(Part(
                        label=f"{q_idx+1}(a)({roman[sub_idx]})",
                        kind="roman",
                        marks=Marks.explicit(sub_idx + 1),  # 1-3 marks
                        bounds=SliceBounds(top=y_offset, bottom=y_offset+100, left=0, right=100),
                    ))
                    y_offset += 100
                for sub_idx in range(2):
                    leaves.append(Part(
                        label=f"{q_idx+1}(b)({roman[sub_idx]})",
                        kind="roman",
                        marks=Marks.explicit(2),  # 2 marks
                        bounds=SliceBounds(top=y_offset, bottom=y_offset+100, left=0, right=100),
                    ))
                    y_offset += 100
                for p_idx in range(2):
                    leaves.append(Part(
                        label=f"{q_idx+1}({chr(99+p_idx)})",
                        kind="letter",
                        marks=Marks.explicit(4),  # 4 marks
                        bounds=SliceBounds(top=y_offset, bottom=y_offset+100, left=0, right=100),
                    ))
                    y_offset += 100
            
            root = Part(
                label=f"{q_idx+1}",
                kind="question",
                marks=Marks.aggregate(leaves),
                bounds=SliceBounds(top=0, bottom=y_offset, left=0, right=100),
                children=tuple(leaves),
            )
            
            questions.append(Question(
                id=f"q{q_idx+1}", exam_code="0478", year=2024, paper=1, variant=1,
                topic="Test", question_node=root,
                composite_path=Path("/tmp/fake.png"),
                regions_path=Path("/tmp/fake.json"),
            ))
        
        return questions
    
    def test_all_500_parts_used_across_1000_seeds(self, large_question_set):
        """Every part should be selected at least once across 1000 seeds."""
        part_usage = Counter()
        
        for seed in range(1000):
            config = SelectionConfig(target_marks=50, seed=seed)
            result = select_questions(large_question_set, config)
            
            for plan in result.plans:
                for label in plan.included_parts:
                    part_usage[label] += 1
        
        # Get all available parts
        all_parts = {
            p.label 
            for q in large_question_set 
            for p in q.leaf_parts
        }
        
        # 100% coverage expected
        used_parts = set(part_usage.keys())
        coverage = len(used_parts) / len(all_parts)
        
        assert coverage == 1.0, (
            f"Only {coverage:.0%} part coverage. "
            f"Missing: {all_parts - used_parts}"
        )

