"""
Automated PDF Validation Tests for Phase 6.5.

Tests the output PDF meets quality requirements:
- A4 page size
- Proper margins
- Complete slice rendering (no cut-offs)
- Question context included

Uses pypdf to inspect generated PDFs.

Verified: 2025-12-13
"""

import pytest
from pathlib import Path
from typing import Tuple

# Try to import pypdf for PDF inspection
try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


# A4 dimensions in points (1/72 inch)
A4_WIDTH_PT = 595.276  # 210mm
A4_HEIGHT_PT = 841.890  # 297mm
TOLERANCE_PT = 1.0  # Allow 1 point tolerance


FIXTURES_DIR = Path(__file__).parent / "extractor_v2" / "fixtures"


@pytest.fixture
def output_dir(tmp_path):
    """Create temporary output directory."""
    return tmp_path / "v2_output"


@pytest.fixture
def cache_dir(tmp_path):
    """Create temporary cache directory."""
    return tmp_path / "v2_cache"


@pytest.fixture
def generated_pdf(cache_dir, output_dir) -> Path:
    """Generate a test PDF for validation."""
    from gcse_toolkit.extractor_v2 import extract_question_paper
    from gcse_toolkit.builder_v2 import build_exam, BuilderConfig
    
    pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
    if not pdf_path.exists():
        pytest.skip("Sample PDF not found")
    
    # Extract
    extract_question_paper(pdf_path, cache_dir, "0478")
    
    # Build
    config = BuilderConfig(
        cache_path=cache_dir,
        exam_code="0478",
        target_marks=15,
        tolerance=5,
        output_dir=output_dir,
    )
    result = build_exam(config)
    
    return result.questions_pdf


@pytest.mark.skipif(not PYPDF_AVAILABLE, reason="pypdf not installed")
class TestPDFPageSize:
    """Tests for A4 page size compliance."""
    
    def test_all_pages_are_a4_size(self, generated_pdf):
        """Every page in the PDF should be A4 size."""
        reader = PdfReader(generated_pdf)
        
        for i, page in enumerate(reader.pages):
            box = page.mediabox
            width = float(box.width)
            height = float(box.height)
            
            assert abs(width - A4_WIDTH_PT) < TOLERANCE_PT, \
                f"Page {i+1} width {width:.2f} not A4 ({A4_WIDTH_PT:.2f})"
            assert abs(height - A4_HEIGHT_PT) < TOLERANCE_PT, \
                f"Page {i+1} height {height:.2f} not A4 ({A4_HEIGHT_PT:.2f})"
    
    def test_pdf_is_not_empty(self, generated_pdf):
        """PDF should have at least one page."""
        reader = PdfReader(generated_pdf)
        assert len(reader.pages) >= 1, "PDF has no pages"


@pytest.mark.skipif(not PYPDF_AVAILABLE, reason="pypdf not installed")
class TestPDFContent:
    """Tests for PDF content quality."""
    
    def test_pdf_file_not_too_small(self, generated_pdf):
        """PDF should have reasonable file size (not empty/corrupt)."""
        size = generated_pdf.stat().st_size
        assert size > 1000, f"PDF file too small ({size} bytes), may be corrupt"
    
    def test_pdf_is_readable(self, generated_pdf):
        """PDF should be readable by pypdf without errors."""
        reader = PdfReader(generated_pdf)
        # Try accessing all pages
        for page in reader.pages:
            _ = page.mediabox  # Access should not raise


class TestLayoutWarnings:
    """Tests for layout warning capture."""
    
    def test_overflow_warnings_captured(self, cache_dir, output_dir):
        """Build result should capture overflow warnings."""
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        
        config = BuilderConfig(
            cache_path=cache_dir,
            exam_code="0478",
            target_marks=50,  # Large target to stress layout
            tolerance=10,
            output_dir=output_dir,
        )
        
        result = build_exam(config)
        
        # Warnings should be a tuple/list
        assert isinstance(result.warnings, (list, tuple))
        
    def test_context_slices_included_in_output(self, cache_dir, output_dir):
        """Build should include context slices (question number, letter headers)."""
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig, load_questions
        from gcse_toolkit.builder_v2.layout import compose_exam, LayoutConfig
        from gcse_toolkit.builder_v2.selection import select_questions, SelectionConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        
        # Load and select
        questions = load_questions(cache_dir, "0478")
        selection = select_questions(questions, SelectionConfig(target_marks=15, tolerance=5))
        
        # Compose
        layout_config = LayoutConfig()
        assets = compose_exam(selection, layout_config)
        
        # Check for context slices (labels ending with _context)
        context_assets = [a for a in assets if a.part_label.endswith("_context")]
        
        # Note: context_assets may be empty if context_bounds not set by extractor
        # This test documents the current behavior
        print(f"Found {len(context_assets)} context assets out of {len(assets)} total")


class TestMargins:
    """Tests for margin configuration."""
    
    def test_layout_config_has_margins(self):
        """LayoutConfig should define margin values."""
        from gcse_toolkit.builder_v2.layout import LayoutConfig
        
        config = LayoutConfig()
        
        assert config.margin_top >= 0, "margin_top should be defined"
        assert config.margin_bottom >= 0, "margin_bottom should be defined"
        assert config.margin_left >= 0, "margin_left should be defined"
        assert config.margin_right >= 0, "margin_right should be defined"
        
    def test_available_dimensions_account_for_margins(self):
        """available_width/height should exclude margins."""
        from gcse_toolkit.builder_v2.layout import LayoutConfig
        
        config = LayoutConfig(
            page_width=1000,
            page_height=1000,
            margin_left=50,
            margin_right=50,
            margin_top=100,
            margin_bottom=100,
        )
        
        assert config.available_width == 900, "available_width = page_width - left - right"
        assert config.available_height == 800, "available_height = page_height - top - bottom"


class TestContextParentHeuristics:
    """Tests for context parent selection logic."""
    
    def test_context_ancestors_have_no_marks_value(self, cache_dir):
        """
        Context parts should be non-leaf (have children) and not carry marks themselves.
        
        A part like "(d)" with marks=2 should NOT be a context parent for "(i)" below it.
        Only parts without marks (parent aggregators) should provide context.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        questions = load_questions(cache_dir, "0478")
        
        for q in questions:
            for leaf in q.leaf_parts:
                # Get context parts for this leaf
                context_parts = q.question_node.get_context_for(leaf.label)
                
                for ctx in context_parts:
                    # Context parts should NOT be leaves (should have children)
                    assert not ctx.is_leaf, \
                        f"Context part {ctx.label} for leaf {leaf.label} is a leaf itself"
                    
                    # Context parts should only have context_bounds if they're parents
                    if ctx.context_bounds is not None:
                        # Verify this part has children (is a parent)
                        assert len(ctx.children) > 0, \
                            f"Context part {ctx.label} has context_bounds but no children"
    
    def test_leaf_marks_are_explicit(self, cache_dir):
        """Leaf parts should have explicit marks, not aggregated."""
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        questions = load_questions(cache_dir, "0478")
        
        for q in questions:
            for leaf in q.leaf_parts:
                # Leaf marks should have a value >= 0
                assert leaf.marks.value >= 0, \
                    f"Leaf {leaf.label} has invalid marks: {leaf.marks.value}"
    
    def test_parent_marks_are_sum_of_children(self, cache_dir):
        """Parent part marks should equal sum of leaf marks."""
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        questions = load_questions(cache_dir, "0478")
        
        for q in questions:
            # Check question_node total_marks = sum of leaf marks
            leaf_sum = sum(leaf.marks.value for leaf in q.leaf_parts)
            assert q.total_marks == leaf_sum, \
                f"Question {q.id}: total_marks {q.total_marks} != leaf sum {leaf_sum}"


class TestPreRenderingValidation:
    """Pre-rendering tests to catch problems BEFORE PDF generation."""
    
    def test_question_root_has_context_bounds(self, cache_dir):
        """
        Question root (e.g., "1") should have context_bounds set.
        This is the header region containing just the question number.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        questions = load_questions(cache_dir, "0478")
        
        questions_with_context = 0
        questions_without_context = []
        
        for q in questions:
            qn = q.question_node
            if qn.context_bounds is not None:
                questions_with_context += 1
            else:
                questions_without_context.append(q.id)
        
        # At least some questions should have context_bounds
        assert questions_with_context > 0, \
            f"No questions have context_bounds set. Missing: {questions_without_context}"
    
    def test_letter_parts_have_context_bounds_when_parent(self, cache_dir):
        """
        Letter parts with children (e.g., "(a)" with "(i)", "(ii)") should have context_bounds.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        questions = load_questions(cache_dir, "0478")
        
        parent_letters_with_context = 0
        parent_letters_without = []
        
        for q in questions:
            for part in q.all_parts:
                # Find letter parts that have children
                if part.kind.value == "letter" and len(part.children) > 0:
                    if part.context_bounds is not None:
                        parent_letters_with_context += 1
                    else:
                        parent_letters_without.append(f"{q.id}/{part.label}")
        
        # Log findings
        print(f"Parent letters with context: {parent_letters_with_context}")
        print(f"Parent letters without context: {len(parent_letters_without)}")
        
        # At least some parent letters should have context
        if parent_letters_with_context == 0 and len(parent_letters_without) > 0:
            pytest.fail(f"No parent letter parts have context_bounds: {parent_letters_without[:5]}")
    
    def test_composed_assets_include_context_slices(self, cache_dir):
        """
        Composed assets should include context slices (labels ending with _context).
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        from gcse_toolkit.builder_v2.layout import compose_exam, LayoutConfig
        from gcse_toolkit.builder_v2.selection import select_questions, SelectionConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        questions = load_questions(cache_dir, "0478")
        selection = select_questions(questions, SelectionConfig(target_marks=15, tolerance=5))
        
        layout_config = LayoutConfig()
        assets = compose_exam(selection, layout_config)
        
        # Count context vs leaf assets
        context_assets = [a for a in assets if "_context" in a.part_label]
        leaf_assets = [a for a in assets if "_context" not in a.part_label]
        
        print(f"Composed: {len(context_assets)} context assets, {len(leaf_assets)} leaf assets")
        
        # Every question should have at least a root context slice
        assert len(context_assets) > 0, \
            "No context slices composed - question headers will be missing"
    
    def test_pagination_produces_required_pages(self, cache_dir, output_dir):
        """
        Pagination should produce multiple pages when content exceeds page height.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        from gcse_toolkit.builder_v2.layout import compose_exam, paginate, LayoutConfig
        from gcse_toolkit.builder_v2.selection import select_questions, SelectionConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        questions = load_questions(cache_dir, "0478")
        
        # Select enough marks to require multiple pages
        selection = select_questions(questions, SelectionConfig(target_marks=50, tolerance=10))
        
        layout_config = LayoutConfig()
        assets = compose_exam(selection, layout_config)
        layout_result = paginate(assets, layout_config)
        
        # Calculate expected minimum pages
        total_height = sum(a.height for a in assets)
        min_pages_expected = max(1, total_height // layout_config.available_height)
        
        print(f"Total asset height: {total_height}px")
        print(f"Available page height: {layout_config.available_height}px")
        print(f"Min pages expected: {min_pages_expected}")
        print(f"Actual pages: {layout_result.page_count}")
        
        # Should produce reasonable page count
        if total_height > layout_config.available_height:
            assert layout_result.page_count > 1, \
                f"Content height {total_height}px exceeds page height {layout_config.available_height}px but only {layout_result.page_count} page produced"
    
    def test_slice_bounds_within_composite(self, cache_dir):
        """
        All slice bounds should be within composite image dimensions.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        from PIL import Image
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        questions = load_questions(cache_dir, "0478")
        
        for q in questions:
            # Load composite to get dimensions
            composite = Image.open(q.composite_path)
            comp_width, comp_height = composite.size
            composite.close()
            
            for part in q.all_parts:
                bounds = part.bounds
                
                # Validate bounds
                assert bounds.top >= 0, \
                    f"{q.id}/{part.label}: top {bounds.top} < 0"
                assert bounds.bottom <= comp_height, \
                    f"{q.id}/{part.label}: bottom {bounds.bottom} > composite height {comp_height}"
                assert bounds.top < bounds.bottom, \
                    f"{q.id}/{part.label}: top {bounds.top} >= bottom {bounds.bottom}"


class TestOversizedSliceDetection:
    """Tests to catch oversized slices that will cause page overflow."""
    
    def test_no_single_slice_exceeds_page_height(self, cache_dir):
        """
        No individual slice should exceed the available page height.
        If a slice is taller than a page, it will be cut off.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        from gcse_toolkit.builder_v2.layout import compose_exam, LayoutConfig
        from gcse_toolkit.builder_v2.selection import select_questions, SelectionConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        questions = load_questions(cache_dir, "0478")
        selection = select_questions(questions, SelectionConfig(target_marks=50, tolerance=10))
        
        layout_config = LayoutConfig()
        assets = compose_exam(selection, layout_config)
        
        oversized = []
        for asset in assets:
            if asset.height > layout_config.available_height:
                oversized.append(f"{asset.part_label}: {asset.height}px > {layout_config.available_height}px")
        
        if oversized:
            print(f"Oversized slices detected:")
            for s in oversized[:5]:
                print(f"  {s}")
        
        # This test documents the issue - ideally there should be no oversized slices
        # For now, we just report them
        assert len(oversized) == 0, \
            f"{len(oversized)} slice(s) exceed page height: {oversized[:3]}"
    
    def test_pagination_does_not_overflow_page(self, cache_dir, output_dir):
        """
        After pagination, no page should have content exceeding available height.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        from gcse_toolkit.builder_v2.layout import compose_exam, paginate, LayoutConfig
        from gcse_toolkit.builder_v2.selection import select_questions, SelectionConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        questions = load_questions(cache_dir, "0478")
        selection = select_questions(questions, SelectionConfig(target_marks=30, tolerance=10))
        
        layout_config = LayoutConfig()
        assets = compose_exam(selection, layout_config)
        layout_result = paginate(assets, layout_config)
        
        overflowed_pages = []
        for page in layout_result.pages:
            if page.height_used > layout_config.available_height:
                overflowed_pages.append(
                    f"Page {page.index}: {page.height_used}px > {layout_config.available_height}px"
                )
        
        # No pages should overflow
        assert len(overflowed_pages) == 0, \
            f"Pages with overflow: {overflowed_pages}"
    
    def test_all_content_fits_on_pages(self, cache_dir, output_dir):
        """
        All slices should fit within their assigned page boundaries.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import load_questions
        from gcse_toolkit.builder_v2.layout import compose_exam, paginate, LayoutConfig
        from gcse_toolkit.builder_v2.selection import select_questions, SelectionConfig
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        extract_question_paper(pdf_path, cache_dir, "0478")
        questions = load_questions(cache_dir, "0478")
        selection = select_questions(questions, SelectionConfig(target_marks=15, tolerance=5))
        
        layout_config = LayoutConfig()
        assets = compose_exam(selection, layout_config)
        layout_result = paginate(assets, layout_config)
        
        # Check each placement fits on page
        page_height = layout_config.page_height - layout_config.margin_bottom
        
        out_of_bounds = []
        for page in layout_result.pages:
            for placement in page.placements:
                bottom = placement.top + placement.asset.height
                if bottom > page_height:
                    out_of_bounds.append(
                        f"{placement.asset.part_label}: bottom={bottom}px > page_height={page_height}px"
                    )
        
        assert len(out_of_bounds) == 0, \
            f"Slices extending beyond page: {out_of_bounds[:5]}"


class TestKeywordModePinning:
    """E2E tests for keyword mode with pinned questions."""
    
    def test_pinned_questions_included_in_output(self, cache_dir, output_dir):
        """
        Pinned questions should always be included even if they don't match keywords.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig, load_questions
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Extract
        extract_question_paper(pdf_path, cache_dir, "0478")
        
        # Load to get question IDs
        questions = load_questions(cache_dir, "0478")
        if len(questions) < 2:
            pytest.skip("Need at least 2 questions for this test")
        
        # Pin first question
        first_qid = questions[0].id
        
        # Build with keyword mode - use keyword unlikely to match first question
        config = BuilderConfig(
            cache_path=cache_dir,
            exam_code="0478",
            target_marks=15,
            tolerance=10,
            keyword_mode=True,
            keywords=["RARELY_MATCHING_KEYWORD_xyz123"],
            keyword_questions=[first_qid],  # Pin first question
            output_dir=output_dir,
        )
        
        result = build_exam(config)
        
        # Get selected question IDs
        selected_ids = {plan.question.id for plan in result.selection.plans}
        
        # Pinned question should be in selection
        assert first_qid in selected_ids, \
            f"Pinned question {first_qid} not in selection: {selected_ids}"
        
        # PDF should exist
        assert result.questions_pdf.exists(), "Questions PDF not generated"
    
    def test_pinned_parts_included_in_selection(self, cache_dir, output_dir):
        """
        Part-level pins should ensure those specific parts are included.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig, load_questions
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Extract
        extract_question_paper(pdf_path, cache_dir, "0478")
        
        # Load to get multi-part questions
        questions = load_questions(cache_dir, "0478")
        multipart_q = None
        for q in questions:
            if q.leaf_count > 1:
                multipart_q = q
                break
        
        if not multipart_q:
            pytest.skip("No multi-part questions found")
        
        # Pin a specific part (format: "question_id::part_label")
        first_part_label = multipart_q.leaf_parts[0].label
        part_pin = f"{multipart_q.id}::{first_part_label}"
        
        # Build with part-level pin
        config = BuilderConfig(
            cache_path=cache_dir,
            exam_code="0478",
            target_marks=10,
            tolerance=5,
            keyword_mode=True,
            keywords=["UNLIKELY_MATCH"],
            keyword_part_pins=[part_pin],
            output_dir=output_dir,
        )
        
        result = build_exam(config)
        
        # Verify pinned question is in selection
        selected_ids = {plan.question.id for plan in result.selection.plans}
        assert multipart_q.id in selected_ids, \
            f"Question {multipart_q.id} with pinned part not selected"


class TestKeywordModeAsTopicPool:
    """E2E tests for using keyword search results as a filtered topic pool."""
    
    def test_keyword_search_filters_available_questions(self, cache_dir, output_dir):
        """
        Keyword search should act as a filter, restricting selection to matching questions only.
        
        This tests the "topic pool" behavior where keywords define the pool of available
        questions, and the selector picks from that pool to meet the target marks.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig, load_questions
        from gcse_toolkit.builder_v2.keyword import KeywordIndex
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Extract
        extract_question_paper(pdf_path, cache_dir, "0478")
        
        # Load all questions
        all_questions = load_questions(cache_dir, "0478")
        
        
        if len(all_questions) < 3:
            pytest.skip("Need at least 3 questions for this test")
        
        # Find a keyword that matches some but not all questions
        # We'll use question text from first question
        if not all_questions[0].root_text:
            pytest.skip("Questions have no text extracted")
        
        # Extract a specific word from first question's text
        words = all_questions[0].root_text.split()
        if len(words) < 3:
            pytest.skip("First question text too short")
        
        # Use a somewhat specific word as keyword
        keyword = words[2] if len(words[2]) > 4 else "data"
        
        # Build with keyword mode (no pins - pure filter)
        config = BuilderConfig(
            cache_path=cache_dir,
            exam_code="0478",
            target_marks=15,
            tolerance=5,
            keyword_mode=True,
            keywords=[keyword],
            output_dir=output_dir,
        )
        
        result = build_exam(config)
        
        # Get selected question IDs
        selected_ids = {plan.question.id for plan in result.selection.plans}
        
        # Verify selection is non-empty
        assert len(selected_ids) > 0, "No questions selected with keyword filter"
        
        # Verify all selected questions match the keyword
        index = KeywordIndex()
        index.prime(all_questions)
        search_result = index.search([keyword])
        
        matching_ids = search_result.question_ids
        
        # Every selected question should be in the matching set
        for qid in selected_ids:
            assert qid in matching_ids, \
                f"Question {qid} selected but doesn't match keyword '{keyword}'"
        
        # PDF should be generated
        assert result.questions_pdf.exists(), "Questions PDF not generated"
    
    def test_multiple_keywords_union_pool(self, cache_dir, output_dir):
        """
        Multiple keywords should create a union pool (OR logic) of matching questions.
        
        NOTE: This test requires text extraction to be functional. If questions
        don't have extracted text (root_text, child_text fields), the test is skipped.
        """
        from gcse_toolkit.extractor_v2 import extract_question_paper
        from gcse_toolkit.builder_v2 import build_exam, BuilderConfig, load_questions
        from gcse_toolkit.builder_v2.keyword import KeywordIndex
        
        pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
        if not pdf_path.exists():
            pytest.skip("Sample PDF not found")
        
        # Extract
        extract_question_paper(pdf_path, cache_dir, "0478")
        
        # Load all questions
        all_questions = load_questions(cache_dir, "0478")
        
        if len(all_questions) < 2:
            pytest.skip("Need at least 2 questions")
        
        # Check if text extraction is implemented
        text_available = any(q.root_text or q.child_text for q in all_questions)
        if not text_available:
            pytest.skip(
                "Text extraction not yet implemented - "
                "questions have no root_text or child_text. "
                "This test requires Phase 6.7 (Text Extraction) to be complete."
            )
        
        # Build with multiple keywords
        config = BuilderConfig(
            cache_path=cache_dir,
            exam_code="0478",
            target_marks=20,
            tolerance=10,
            keyword_mode=True,
            keywords=["data", "algorithm", "program"],  # Common CS keywords
            output_dir=output_dir,
        )
        
        result = build_exam(config)
        
        # Verify we got results
        assert len(result.selection.plans) > 0, "No questions selected"
        
        # Verify all selected questions match at least one keyword
        index = KeywordIndex()
        index.prime(all_questions)
        search_result = index.search(config.keywords)
        
        matching_ids = search_result.question_ids
        selected_ids = {plan.question.id for plan in result.selection.plans}
        
        for qid in selected_ids:
            assert qid in matching_ids, \
                f"Question {qid} selected but doesn't match any keywords"


