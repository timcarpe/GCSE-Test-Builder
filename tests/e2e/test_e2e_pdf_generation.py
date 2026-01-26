"""
End-to-End Pipeline Tests for Phase 6.5: Complete PDF Generation.

Tests the full workflow:
PDF → Extractor V2 → Cache → Builder V2 → PDF Output

Verified: 2025-12-13
"""

import pytest
from pathlib import Path

# Fixtures directory
FIXTURES_DIR = Path(__file__).parent / "extractor_v2" / "fixtures"


@pytest.fixture
def output_dir(tmp_path):
    """Create temporary output directory."""
    return tmp_path / "v2_output"


@pytest.fixture
def cache_dir(tmp_path):
    """Create temporary cache directory."""
    return tmp_path / "v2_cache"


class TestFullPipelinePDFGeneration:
    """End-to-end tests: Extract → Load → Select → Layout → Render PDF."""
    
    def test_e2e_full_pipeline_produces_pdf(self, cache_dir, output_dir):
        """Complete pipeline from PDF input to PDF output."""
        # Arrange
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Act - Step 1: Extract questions to cache
        extract_result = extract_question_paper(
            pdf_path=pdf_path,
            output_dir=cache_dir,
            exam_code="0478",
        )
        
        assert extract_result.question_count > 0, "No questions extracted"
        
        # Act - Step 2: Build exam from cache to PDF
        config = BuilderConfig(
            cache_path=cache_dir,
            exam_code="0478",
            target_marks=15,
            tolerance=5,
            output_dir=output_dir,
            include_markscheme=True,
        )
        
        build_result = build_exam(config)
        
        # Assert - PDF files created
        assert build_result.questions_pdf.exists(), "Questions PDF not created"
        assert build_result.questions_pdf.stat().st_size > 0, "Questions PDF is empty"
        
        # Assert - Markscheme created
        assert build_result.markscheme_pdf is not None
        assert build_result.markscheme_pdf.exists(), "Markscheme PDF not created"
        
        # Assert - Marks within tolerance
        assert build_result.total_marks > 0
        assert build_result.total_marks <= config.target_marks + config.tolerance
        
        # Assert - Page count reasonable
        assert build_result.page_count >= 1
        
    def test_e2e_zip_export(self, cache_dir, output_dir):
        """Verify ZIP export works in full pipeline."""
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig
        import zipfile
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
            
        # Extract
        extract_question_paper(pdf_path=pdf_path, output_dir=cache_dir, exam_code="0478")
        
        # Build with ZIP export
        config = BuilderConfig(
            cache_path=cache_dir,
            exam_code="0478",
            target_marks=10,
            output_dir=output_dir,
            export_zip=True,
        )
        
        result = build_exam(config)
        
        # Assert ZIP exists and is valid
        assert result.questions_zip is not None
        assert result.questions_zip.exists()
        assert zipfile.is_zipfile(result.questions_zip)
        
        with zipfile.ZipFile(result.questions_zip, "r") as zf:
            names = zf.namelist()
            assert "README.txt" in names
            # Check for at least one question folder (1/)
            assert any(n.startswith("1/") for n in names)
            # Check for PNG files
            assert any(n.endswith(".png") for n in names)
            # Verify no spaces in PNG names (except those from part labels which we now return compact)
            png_names = [n for n in names if n.endswith(".png")]
            for png in png_names:
                # Should not have " (" which was the old format
                assert " (" not in png, f"Space found in filename: {png}"
        """Marks are consistent throughout the pipeline."""
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig, load_questions
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Extract
        extract_question_paper(
            pdf_path=pdf_path,
            output_dir=cache_dir,
            exam_code="0478",
        )
        
        # Load and verify marks
        questions = load_questions(cache_dir, "0478")
        for q in questions:
            # Total marks = sum of leaf marks
            leaf_sum = sum(p.marks.value for p in q.leaf_parts)
            assert q.total_marks == leaf_sum, f"Mark mismatch in {q.id}"
        
        # Build and verify
        config = BuilderConfig(
            cache_path=cache_dir,
            exam_code="0478",
            target_marks=20,
            tolerance=5,
            output_dir=output_dir,
        )
        
        result = build_exam(config)
        
        # Selection marks = sum of plan marks
        plan_total = sum(p.marks for p in result.selection.plans)
        assert result.total_marks == plan_total, "Selection marks mismatch"
        
    def test_e2e_deterministic_output(self, cache_dir, output_dir):
        """Same seed produces same results."""
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Extract once
        extract_question_paper(
            pdf_path=pdf_path,
            output_dir=cache_dir,
            exam_code="0478",
        )
        
        # Build twice with same seed
        base_config = {
            "cache_path": cache_dir,
            "exam_code": "0478",
            "target_marks": 15,
            "seed": 12345,
        }
        
        result1 = build_exam(BuilderConfig(**base_config, output_dir=output_dir / "run1"))
        result2 = build_exam(BuilderConfig(**base_config, output_dir=output_dir / "run2"))
        
        # Same questions selected
        ids1 = [p.question.id for p in result1.selection.plans]
        ids2 = [p.question.id for p in result2.selection.plans]
        assert ids1 == ids2, "Selection not deterministic"
        
        # Same marks
        assert result1.total_marks == result2.total_marks


class TestMultiSeedPDFGeneration:
    """Generate multiple PDFs with different seeds, topics, and mark targets."""
    
    @pytest.mark.parametrize("test_config", [
        # Test 1: Low marks, default random seed, no topic filter
        {
            "name": "low_marks_no_filter",
            "target_marks": 10,
            "tolerance": 3,
            "seed": 11111,
            "topics": [],  # No topic filter - pick any questions
        },
        # Test 2: Medium marks, different seed, with topic filter
        {
            "name": "medium_marks_topic_filter",
            "target_marks": 20,
            "tolerance": 5,
            "seed": 22222,
            "topics": ["00. Unknown"],  # Filter to Unknown topic
        },
        # Test 3: Higher marks, another seed, pruning allowed
        {
            "name": "high_marks_pruning",
            "target_marks": 30,
            "tolerance": 8,
            "seed": 33333,
            "topics": [],
        },
    ])
    def test_e2e_multi_seed_pdf_generation(self, cache_dir, output_dir, test_config):
        """
        Generate PDFs with different seeds, mark targets, and topic configurations.
        
        Tests varied question selections to ensure the pipeline handles different
        combinations of questions correctly.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Extract to cache
        extract_question_paper(
            pdf_path=pdf_path,
            output_dir=cache_dir,
            exam_code="0478",
        )
        
        # Build with test config
        run_output = output_dir / test_config["name"]
        config = BuilderConfig(
            cache_path=cache_dir,
            exam_code="0478",
            target_marks=test_config["target_marks"],
            tolerance=test_config["tolerance"],
            seed=test_config["seed"],
            topics=test_config["topics"],
            output_dir=run_output,
            include_markscheme=True,
        )
        
        result = build_exam(config)
        
        # Assert - PDF files created
        assert result.questions_pdf.exists(), f"Questions PDF not created for {test_config['name']}"
        assert result.questions_pdf.stat().st_size > 0, f"Questions PDF is empty for {test_config['name']}"
        
        # Assert - Markscheme created
        assert result.markscheme_pdf is not None
        assert result.markscheme_pdf.exists(), f"Markscheme not created for {test_config['name']}"
        
        # Assert - Marks within tolerance
        target = test_config["target_marks"]
        tolerance = test_config["tolerance"]
        assert result.total_marks > 0, f"No marks for {test_config['name']}"
        assert result.total_marks <= target + tolerance, (
            f"Marks {result.total_marks} exceed target+tolerance {target + tolerance} "
            f"for {test_config['name']}"
        )
        
        # Assert - Page count reasonable
        assert result.page_count >= 1, f"No pages for {test_config['name']}"
        
        # Assert - Selection has questions
        assert result.selection.question_count > 0, f"No questions selected for {test_config['name']}"
        
        # Log info for debugging
        print(f"\n{test_config['name']}:")
        print(f"  - Questions: {result.selection.question_count}")
        print(f"  - Marks: {result.total_marks}/{target} (tolerance: {tolerance})")
        print(f"  - Pages: {result.page_count}")
        print(f"  - Seed: {test_config['seed']}")

