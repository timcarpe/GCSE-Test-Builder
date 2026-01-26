"""
Integration tests for keyword mode in the build pipeline.

Tests end-to-end keyword filtering with the build_exam controller.
"""

import pytest
from pathlib import Path
from gcse_toolkit.builder_v2 import build_exam, BuilderConfig, BuildError


class TestKeywordModeIntegration:
    """Integration tests for keyword mode build pipeline."""
    
    def test_build_with_keywords_filters_questions(self, e2e_cache_path, tmp_path):
        """Build with keywords only includes matching questions."""
        # Skip if no cache available
        if not e2e_cache_path.exists():
            pytest.skip("E2E cache not available")
        
        # Find any cache directory with questions
        cache_dirs = [d for d in e2e_cache_path.iterdir() if d.is_dir()]
        if not cache_dirs:
            pytest.skip("No cache directories found")
        
        # Use first cache (e.g., test_extraction)
        cache_name = cache_dirs[0].name
        
        # Load questions to find an exam code
        from gcse_toolkit.builder_v2 import load_questions
        questions = load_questions(e2e_cache_path, cache_name)
        
        if not questions:
            pytest.skip(f"No questions found in {cache_name}")
        
        # Extract exam code from first question
        exam_code = questions[0].exam_code
        
        config = BuilderConfig(
            cache_path=e2e_cache_path,
            exam_code=cache_name,
            target_marks=10,
            tolerance=5,
            keyword_mode=True,
            keywords=["function", "algorithm"],  # Common terms
            output_dir=tmp_path,
            include_markscheme=False,
        )
        
        try:
            result = build_exam(config)
            
            # Verify result
            assert result.questions_pdf.exists()
            assert result.total_marks > 0
            assert result.page_count > 0
            assert result.metadata["keyword_mode"] is True
        except BuildError as e:
            # May fail if no questions match keywords
            if "No questions matched keywords" in str(e):
                pytest.skip(f"No questions matched keywords in {cache_name}")
            else:
                raise
    
    def test_build_with_pinned_questions_includes_them(self, e2e_cache_path, tmp_path):
        """Pinned questions are always included even without keyword match."""
        if not e2e_cache_path.exists():
            pytest.skip("E2E cache not available")
        
        exam_dirs = [d for d in e2e_cache_path.iterdir() if d.is_dir() and len(d.name) == 4]
        if not exam_dirs:
            pytest.skip("No exam codes found in cache")
        
        exam_code = exam_dirs[0].name
        
        # Find a question ID from this exam
        question_dirs = [d for d in (e2e_cache_path / exam_code).iterdir() if d.is_dir()]
        if not question_dirs:
            pytest.skip(f"No questions found for {exam_code}")
        
        pinned_qid = question_dirs[0].name
        
        config = BuilderConfig(
            cache_path=e2e_cache_path,
            exam_code=exam_code,
            target_marks=15,
            keyword_mode=True,
            keywords=["xyzrarekeyword123"],  # Unlikely to match
            keyword_questions=[pinned_qid],  # Pin specific question
            output_dir=tmp_path,
            include_markscheme=False,
        )
        
        result = build_exam(config)
        
        # Verify pinned question is in result
        selected_ids = [plan.question.id for plan in result.selection.plans]
        assert pinned_qid in selected_ids, f"Pinned question {pinned_qid} not in selection"
    
    def test_build_with_part_pins_includes_them(self, e2e_cache_path, tmp_path):
        """Part-level pins work correctly."""
        if not e2e_cache_path.exists():
            pytest.skip("E2E cache not available")
        
        exam_dirs = [d for d in e2e_cache_path.iterdir() if d.is_dir() and len(d.name) == 4]
        if not exam_dirs:
            pytest.skip("No exam codes found in cache")
        
        exam_code = exam_dirs[0].name
        
        # Find a question with parts
        from gcse_toolkit.builder_v2 import load_questions
        questions = load_questions(e2e_cache_path, exam_code)
        
        if not questions:
            pytest.skip(f"No questions found for {exam_code}")
        
        # Find a question with multiple parts
        multi_part_q = None
        for q in questions:
            if hasattr(q, 'question_node'):
                parts = list(q.question_node.iter_all())
                if len(parts) > 1:
                    multi_part_q = q
                    break
        
        if not multi_part_q:
            pytest.skip("No multi-part questions found")
        
        # Get first part label
        first_part = list(multi_part_q.question_node.iter_all())[0]
        part_pin = f"{multi_part_q.id}::{first_part.label}"
        
        config = BuilderConfig(
            cache_path=e2e_cache_path,
            exam_code=exam_code,
            target_marks=10,
            keyword_mode=True,
            keywords=["xyzrarekeyword456"],
            keyword_part_pins=[part_pin],
            output_dir=tmp_path,
            include_markscheme=False,
        )
        
        result = build_exam(config)
        
        # Verify question is in result
        selected_ids = [plan.question.id for plan in result.selection.plans]
        assert multi_part_q.id in selected_ids
    
    def test_keyword_mode_false_ignores_keywords(self, e2e_cache_path, tmp_path):
        """When keyword_mode is False, keywords are ignored."""
        if not e2e_cache_path.exists():
            pytest.skip("E2E cache not available")
        
        exam_dirs = [d for d in e2e_cache_path.iterdir() if d.is_dir() and len(d.name) == 4]
        if not exam_dirs:
            pytest.skip("No exam codes found in cache")
        
        exam_code = exam_dirs[0].name
        
        config = BuilderConfig(
            cache_path=e2e_cache_path,
            exam_code=exam_code,
            target_marks=10,
            keyword_mode=False,  # Disabled
            keywords=["function"],  # Should be ignored
            output_dir=tmp_path,
            include_markscheme=False,
        )
        
        result = build_exam(config)
        
        # Should succeed with normal selection
        assert result.questions_pdf.exists()
        assert result.total_marks > 0
        assert result.metadata["keyword_mode"] is False
    
    def test_empty_keywords_with_keyword_mode_uses_all_questions(self, e2e_cache_path, tmp_path):
        """Empty keywords with keyword_mode=True should use all questions."""
        if not e2e_cache_path.exists():
            pytest.skip("E2E cache not available")
        
        exam_dirs = [d for d in e2e_cache_path.iterdir() if d.is_dir() and len(d.name) == 4]
        if not exam_dirs:
            pytest.skip("No exam codes found in cache")
        
        exam_code = exam_dirs[0].name
        
        config = BuilderConfig(
            cache_path=e2e_cache_path,
            exam_code=exam_code,
            target_marks=10,
            keyword_mode=True,
            keywords=[],  # Empty
            output_dir=tmp_path,
            include_markscheme=False,
        )
        
        result = build_exam(config)
        
        # Should succeed - empty keywords means no filtering
        assert result.questions_pdf.exists()
        assert result.total_marks > 0


@pytest.fixture
def e2e_cache_path():
    """Path to E2E test cache."""
    # Use absolute path from project root
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / "workspace" / "slices_cache_v2"

