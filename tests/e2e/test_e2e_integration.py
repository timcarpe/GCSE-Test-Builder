"""
End-to-End Integration Tests for V2 Pipeline.

These tests verify the complete workflow:
PDF → Extractor V2 → Cache → Builder V2 Loader → Question objects

Verified: 2025-12-12
"""

import json
import pytest
from pathlib import Path

# Use fixtures from extractor tests
FIXTURES_DIR = Path(__file__).parent / "extractor_v2" / "fixtures"


@pytest.fixture
def output_dir(tmp_path):
    """Create temporary output directory."""
    return tmp_path / "v2_cache"


class TestEndToEndPipeline:
    """End-to-end tests for extract → load workflow."""

    def test_e2e_when_extract_then_load_then_marks_match(self, output_dir):
        """Extracted questions should load with correct marks."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Act - Extract
        extract_result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code="0478",
        )
        
        # Act - Load
        questions = load_questions(output_dir, "0478")
        
        # Assert - Same count
        assert len(questions) == extract_result.question_count
        
        # Assert - Each question has marks
        for q in questions:
            assert q.total_marks > 0
            # Verify marks calculated from leaves
            leaf_sum = sum(p.marks.value for p in q.leaf_parts)
            assert q.total_marks == leaf_sum

    def test_e2e_when_extract_then_load_then_tree_structure_preserved(
        self, output_dir
    ):
        """Part tree structure should be preserved through extract/load."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2.loading import load_single_question
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Act - Extract
        extract_result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code="0478",
        )
        
        # Act - Load first question
        question_dir = output_dir / extract_result.question_ids[0]
        question = load_single_question(question_dir)
        
        # Assert - Tree structure
        assert question.question_node is not None
        assert question.question_node.label == "1"
        assert len(question.question_node.children) > 0
        
        # Assert - All parts have bounds
        for part in question.all_parts:
            assert part.bounds is not None
            assert part.bounds.top < part.bounds.bottom

    def test_e2e_when_extract_then_image_provider_returns_slices(
        self, output_dir
    ):
        """Image provider should return cropped slices for each part."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2.loading import load_single_question
        from gcse_toolkit.builder_v2.images import CompositeImageProvider
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Act - Extract
        extract_result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code="0478",
        )
        
        # Act - Load
        question_dir = output_dir / extract_result.question_ids[0]
        question = load_single_question(question_dir)
        
        # Get bounds from question
        bounds = {p.label: p.bounds for p in question.all_parts}
        
        # Act - Get slices
        with CompositeImageProvider(question.composite_path, bounds) as provider:
            for part in question.all_parts:
                slice_img = provider.get_slice(part.label)
                
                # Assert - Slice has correct dimensions
                expected_height = part.bounds.height
                assert slice_img.height == expected_height
                assert slice_img.width > 0

    def test_e2e_when_multiple_exams_then_all_load_correctly(self, output_dir):
        """Should handle multiple exam codes in same cache."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        
        # Extract from multiple exam codes
        results = {}
        for exam_code in ["0478", "0580"]:
            pdf_name = f"{exam_code}_m24_qp_12.pdf" if exam_code == "0478" else f"{exam_code}_s25_qp_11.pdf"
            pdf_path = FIXTURES_DIR / pdf_name
            if not pdf_path.exists():
                continue
            
            result = extract_question_paper(
                pdf_path=pdf_path,
                output_dir=output_dir,
                exam_code=exam_code,
            )
            results[exam_code] = result
        
        if len(results) < 2:
            pytest.skip("Need at least 2 exam PDFs")
        
        # Act - Load each separately
        for exam_code, extract_result in results.items():
            questions = load_questions(output_dir, exam_code)
            
            # Assert
            assert len(questions) == extract_result.question_count
            assert all(q.exam_code == exam_code for q in questions)

    def test_e2e_when_extract_then_regions_have_marks_only_on_leaves(
        self, output_dir
    ):
        """regions.json should only have marks on leaf parts."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Act - Extract
        extract_result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code="0478",
        )
        
        # Check regions.json
        regions_path = output_dir / extract_result.question_ids[0] / "regions.json"
        with open(regions_path) as f:
            data = json.load(f)
        
        # Assert - Parent parts should NOT have marks
        for label, region in data["regions"].items():
            has_marks = region.get("marks") is not None
            is_leaf = "(" not in label or label.count("(") == 2  # romans are leaves
            
            # If it has children, it shouldn't have marks
            # Simple heuristic: check if any other label starts with this one
            has_children = any(
                other.startswith(label + "(") 
                for other in data["regions"].keys() 
                if other != label
            )
            
            if has_children:
                assert not has_marks, f"Parent {label} should not have marks"
    
    def test_e2e_keyword_filtering_matches_questions(self, output_dir):
        """Keyword search should find questions with matching text."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2.keyword import KeywordIndex
        from gcse_toolkit.builder_v2 import load_questions
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Act - Extract
        extract_result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code="0478",
        )
        
        # Load questions
        questions = load_questions(output_dir, "0478")
        
        # Build keyword index
        index = KeywordIndex()
        index.prime(questions)
        
        # Search for common programming terms
        result = index.search(["program", "algorithm"])
        
        # Assert - Should find at least one match
        assert not result.is_empty, "Expected to find questions with 'program' or 'algorithm'"
        assert len(result.question_ids) > 0
        
        # Assert - Matched questions have labels
        for qid in result.question_ids:
            labels = result.aggregate_labels[qid]
            assert len(labels) > 0, f"Question {qid} should have matched part labels"
    
    def test_e2e_keyword_with_question_pin_includes_pinned(self, output_dir):
        """Pinned questions should be included even without keyword match."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Act - Extract
        extract_result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code="0478",
        )
        
        # Pin first question
        pinned_qid = extract_result.question_ids[0]
        
        # Build with keyword mode using rare keyword but pinned question
        config = BuilderConfig(
            cache_path=output_dir,
            exam_code="0478",
            target_marks=10,
            keyword_mode=True,
            keywords=["xyzrarekeyword999"],  # Won't match
            keyword_questions=[pinned_qid],  # Pin question
            output_dir=output_dir / "keyword_build",
            include_markscheme=False,
        )
        
        result = build_exam(config)
        
        # Assert - Pinned question is in result
        selected_ids = [plan.question.id for plan in result.selection.plans]
        assert pinned_qid in selected_ids, f"Pinned question {pinned_qid} should be selected"
        assert result.total_marks > 0
    
    def test_e2e_keyword_with_part_pin_includes_part(self, output_dir):
        """Part-level pins should include specific parts."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions, build_exam, BuilderConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Act - Extract
        extract_result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code="0478",
        )
        
        # Load questions to find one with multiple parts
        questions = load_questions(output_dir, "0478")
        multi_part_q = None
        for q in questions:
            if len(list(q.question_node.iter_all())) > 2:
                multi_part_q = q
                break
        
        if not multi_part_q:
            pytest.skip("No multi-part questions found")
        
        # Get first leaf part
        first_leaf = next(p for p in multi_part_q.question_node.iter_all() if p.is_leaf)
        part_pin = f"{multi_part_q.id}::{first_leaf.label}"
        
        # Build with part pin
        config = BuilderConfig(
            cache_path=output_dir,
            exam_code="0478",
            target_marks=5,
            keyword_mode=True,
            keywords=["xyzrare111"],
            keyword_part_pins=[part_pin],
            output_dir=output_dir / "part_pin_build",
            include_markscheme=False,
        )
        
        result = build_exam(config)
        
        # Assert - Question with pinned part is included
        selected_ids = [plan.question.id for plan in result.selection.plans]
        assert multi_part_q.id in selected_ids, f"Question {multi_part_q.id} with pinned part should be selected"
    
    def test_e2e_keyword_mode_end_to_end_build(self, output_dir):
        """Full keyword mode workflow: extract → search → build."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Act - Extract
        extract_result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code="0478",
        )
        
        # Act - Build with keyword mode
        config = BuilderConfig(
            cache_path=output_dir,
            exam_code="0478",
            target_marks=15,
            tolerance=10,
            keyword_mode=True,
            keywords=["data", "structure"],  # Common CS terms
            output_dir=output_dir / "keyword_output",
            include_markscheme=False,
        )
        
        try:
            result = build_exam(config)
            
            # Assert - PDF generated
            assert result.questions_pdf.exists()
            assert result.questions_pdf.stat().st_size > 0
            
            # Assert - Metadata has keyword mode flag
            assert result.metadata["keyword_mode"] is True
            
            # Assert - Questions selected
            assert result.selection.question_count > 0
            assert result.total_marks > 0
            
        except Exception as e:
            if "No questions matched keywords" in str(e):
                pytest.skip("No questions matched keywords in test PDF")
            else:
                raise
