"""End-to-end test for markscheme extraction and PDF building."""

import pytest
from pathlib import Path
import fitz

from gcse_toolkit.extractor_v2.pipeline import extract_question_paper
from gcse_toolkit.extractor_v2.config import ExtractionConfig
from gcse_toolkit.builder_v2.controller import build_exam
from gcse_toolkit.builder_v2.config import BuilderConfig
from gcse_toolkit.builder_v2.loading import discover_questions


# Test file paths
INPUT_PDFS = Path("workspace/input_pdfs")
QP_FILE = "0478_s25_qp_11.pdf"
MS_FILE = "0478_s25_ms_11.pdf"


@pytest.mark.skipif(
    not (INPUT_PDFS / QP_FILE).exists() or not (INPUT_PDFS / MS_FILE).exists(),
    reason="Test requires real QP/MS pair in workspace/input_pdfs"
)
class TestMarkschemeE2E:
    """End-to-end test for markscheme extraction and building with real PDFs."""
    
    def test_extract_and_build_with_markscheme(self, tmp_path):
        """
        Full E2E test: Extract QP with MS, then build exam with markscheme PDF.
        
        Tests the complete workflow:
        1. Extract question paper
        2. Extract markscheme pages automatically
        3. Build exam PDF
        4. Build markscheme PDF
        5. Verify all artifacts generated correctly
        """
        # Setup paths
        qp_pdf = INPUT_PDFS / QP_FILE
        cache_dir = tmp_path / "cache"
        output_dir = tmp_path / "output"
        
        # ═══════════════════════════════════════════════════════════
        # STEP 1: Extract Question Paper with Markscheme
        # ═══════════════════════════════════════════════════════════
        extract_config = ExtractionConfig(
            extract_markschemes=True,
            dpi=200,
        )
        
        extraction_result = extract_question_paper(
            pdf_path=qp_pdf,
            output_dir=cache_dir,
            exam_code="0478",
            config=extract_config,
            markscheme_search_dirs=[INPUT_PDFS],  # Tell it where to find MS PDF
        )
        
        # Verify extraction succeeded
        assert extraction_result.question_count > 0, "Should extract questions"
        print(f"\n[OK] Extracted {extraction_result.question_count} questions")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 2: Verify Markscheme Pages Were Extracted
        # ═══════════════════════════════════════════════════════════
        questions_with_ms = 0
        
        # Use discover_questions to find the actual question directories
        # which are now nested: cache/0478/topic/question_id/
        question_dirs = discover_questions(cache_dir, "0478")
        assert len(question_dirs) > 0, "No questions discovered in cache"
        
        for question_dir in question_dirs:
            metadata_path = question_dir / "metadata.json"
            question_id = question_dir.name
            
            # Check if metadata exists
            assert metadata_path.exists(), f"Missing metadata for {question_id}"
            
            # Load metadata
            import json
            metadata = json.loads(metadata_path.read_text())
            
            # Check for markscheme
            if "markscheme_path" in metadata and metadata["markscheme_path"]:
                questions_with_ms += 1
                ms_image_path = question_dir / metadata["markscheme_path"]
                
                # Verify markscheme image exists
                assert ms_image_path.exists(), f"Missing MS image for {question_id}"
                
                # Verify it's a valid image
                from PIL import Image
                img = Image.open(ms_image_path)
                assert img.width > 0 and img.height > 0, "MS image should have dimensions"
                
                print(f"  [OK] Question {question_id} has markscheme: {metadata['markscheme_path']}")
        
        assert questions_with_ms > 0, "Should have extracted markschemes for at least one question"
        print(f"\n[OK] {questions_with_ms}/{extraction_result.question_count} questions have markschemes")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 3: Build Exam with Markscheme
        # ═══════════════════════════════════════════════════════════
        build_config = BuilderConfig(
            cache_path=cache_dir,
            exam_code="0478",
            target_marks=20,  # Build a small exam
            include_markscheme=True,  # Include markscheme PDF
            output_dir=output_dir,
        )
        
        build_result = build_exam(build_config)
        
        # ═══════════════════════════════════════════════════════════
        # STEP 4: Verify Output PDFs
        # ═══════════════════════════════════════════════════════════
        
        # 4a. Verify questions PDF exists and is valid
        questions_pdf = build_result.questions_pdf
        assert questions_pdf.exists(), "Questions PDF should exist"
        
        with fitz.open(questions_pdf) as doc:
            assert doc.page_count > 0, "Questions PDF should have pages"
            print(f"\n[OK] Questions PDF: {questions_pdf.name} ({doc.page_count} pages)")
        
        # 4b. Verify markscheme PDF exists and is valid
        markscheme_pdf = build_result.markscheme_pdf
        assert markscheme_pdf is not None, "Markscheme PDF should be generated"
        assert markscheme_pdf.exists(), "Markscheme PDF should exist"
        
        with fitz.open(markscheme_pdf) as doc:
            assert doc.page_count > 0, "Markscheme PDF should have pages"
            print(f"[OK] Markscheme PDF: {markscheme_pdf.name} ({doc.page_count} pages)")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 5: Verify Markscheme PDF Content
        # ═══════════════════════════════════════════════════════════
        
        # The markscheme PDF should contain actual markscheme images, not just a summary
        # Check that it has reasonable dimensions (not just a tiny summary table)
        with fitz.open(markscheme_pdf) as doc:
            first_page = doc[0]
            page_width = first_page.rect.width
            page_height = first_page.rect.height
            
            # A4 page is ~595x842 points, markscheme should be similar
            assert page_width > 400, "Markscheme page should be reasonable width"
            assert page_height > 400, "Markscheme page should be reasonable height"
            
            print(f"  [OK] Markscheme page dimensions: {int(page_width)}x{int(page_height)} points")
        
        # ═══════════════════════════════════════════════════════════
        # STEP 6: Summary
        # ═══════════════════════════════════════════════════════════
        
        print(f"\n{'='*60}")
        print("E2E TEST SUMMARY")
        print(f"{'='*60}")
        print(f"[OK] Extraction: {extraction_result.question_count} questions")
        print(f"[OK] Markschemes extracted: {questions_with_ms} questions")
        print(f"[OK] Questions PDF: {build_result.questions_pdf.name}")
        print(f"[OK] Markscheme PDF: {build_result.markscheme_pdf.name}")
        print(f"[OK] Total marks: {build_result.total_marks}")
        print(f"{'='*60}\n")
    
    def test_extraction_finds_correct_ms_pdf(self, tmp_path):
        """Verify that MS PDF discovery works correctly."""
        qp_pdf = INPUT_PDFS / QP_FILE
        
        from gcse_toolkit.extractor_v2.markscheme import find_markscheme_pdf
        
        # Should find MS in same directory
        ms_path = find_markscheme_pdf(qp_pdf, [INPUT_PDFS])
        
        assert ms_path is not None, "Should find markscheme PDF"
        assert ms_path.name == MS_FILE, f"Should find correct MS file"
        assert ms_path.exists(), "MS PDF should exist"
        
        print(f"[OK] Found markscheme: {ms_path.name}")
    
    def test_markscheme_pdf_has_actual_content(self, tmp_path):
        """
        Verify the built markscheme PDF contains actual markscheme images,
        not just a summary table.
        """
        # Extract and build
        qp_pdf = INPUT_PDFS / QP_FILE
        cache_dir = tmp_path / "cache"
        output_dir = tmp_path / "output"
        
        # Extract
        extract_question_paper(
            pdf_path=qp_pdf,
            output_dir=cache_dir,
            exam_code="0478",
            config=ExtractionConfig(extract_markschemes=True),
            markscheme_search_dirs=[INPUT_PDFS],
        )
        
        # Build
        build_result = build_exam(BuilderConfig(
            cache_path=cache_dir,
            exam_code="0478",
            target_marks=10,  # Small exam
            include_markscheme=True,
            output_dir=output_dir,
        ))
        
        # Check markscheme PDF content
        ms_pdf = build_result.markscheme_pdf
        assert ms_pdf is not None
        
        with fitz.open(ms_pdf) as doc:
            # Get images from first page
            page = doc[0]
            image_list = page.get_images()
            
            # Should have at least one image (the markscheme page)
            assert len(image_list) > 0, "Markscheme PDF should contain images"
            
            # Get first image info
            xref = image_list[0][0]
            base_image = doc.extract_image(xref)
            
            # Verify image has reasonable dimensions
            img_width = base_image.get("width", 0)
            img_height = base_image.get("height", 0)
            
            assert img_width > 100, "MS image should have reasonable width"
            assert img_height > 100, "MS image should have reasonable height"
            
            print(f"[OK] Markscheme contains {len(image_list)} image(s)")
            print(f"  First image: {img_width}x{img_height} pixels")
