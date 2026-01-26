"""
Verification script for Phase 6.5: Generate a test PDF.

This script demonstrates the complete V2 pipeline:
1. Load questions from V2 cache
2. Select questions to meet target marks
3. Compose slice assets
4. Paginate onto pages
5. Render to PDF

Run this script to verify the pipeline works end-to-end.
"""

from pathlib import Path
import sys

# Add src to path if needed
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from gcse_toolkit.builder_v2 import build_exam, BuilderConfig, BuildError


def main():
    # Find V2 cache
    cache_path = Path("workspace/slices_cache_v2")
    if not cache_path.exists():
        print(f"V2 cache not found at {cache_path}")
        print("Please extract some papers first using extractor_v2")
        return 1
    
    # List available exam codes
    exam_codes = set()
    for d in cache_path.iterdir():
        if d.is_dir() and "_" in d.name:
            code = d.name.split("_")[0]
            if code.isdigit() and len(code) == 4:
                exam_codes.add(code)
    
    if not exam_codes:
        print(f"No exam codes found in {cache_path}")
        return 1
    
    exam_code = sorted(exam_codes)[0]
    print(f"Using exam code: {exam_code}")
    
    # Configure build
    output_dir = Path("workspace/test_output_v2")
    config = BuilderConfig(
        cache_path=cache_path,
        exam_code=exam_code,
        target_marks=15,
        output_dir=output_dir,
        include_markscheme=True,
    )
    
    # Build exam
    try:
        result = build_exam(config)
        
        print("\n=== BUILD SUCCESS ===")
        print(f"Questions PDF: {result.questions_pdf}")
        print(f"Markscheme PDF: {result.markscheme_pdf}")
        print(f"Total marks: {result.total_marks}")
        print(f"Page count: {result.page_count}")
        print(f"Questions: {result.selection.question_count}")
        
        if result.warnings:
            print(f"\nWarnings:")
            for w in result.warnings:
                print(f"  - {w}")
        
        print(f"\nOpen the PDF to verify: {result.questions_pdf}")
        return 0
        
    except BuildError as e:
        print(f"Build failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
