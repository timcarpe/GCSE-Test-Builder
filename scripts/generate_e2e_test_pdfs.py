"""
Generate test PDFs from E2E tests for manual review.

This script runs the E2E tests and keeps the generated PDFs in a known location.
Cleans and re-extracts cache to ensure text extraction is fresh.
"""

import shutil
from pathlib import Path
from gcse_toolkit.extractor_v2 import extract_question_paper
from gcse_toolkit.builder_v2 import build_exam, BuilderConfig, load_questions

# Paths
FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "v2" / "extractor_v2" / "fixtures"
OUTPUT_DIR = Path(__file__).parent.parent / "workspace" / "e2e_test_pdfs"
CACHE_DIR = Path(__file__).parent.parent / "workspace" / "e2e_test_cache"

def main():
    pdf_path = FIXTURES_DIR / "0478_m24_qp_12.pdf"
    
    if not pdf_path.exists():
        print(f"[ERROR] Sample PDF not found: {pdf_path}")
        return
    
    print(f"[OK] Found sample PDF: {pdf_path}")
    
    # Clean and create directories (FORCE RE-EXTRACTION)
    if CACHE_DIR.exists():
        print(f"[CLEAN] Removing old cache: {CACHE_DIR}")
        shutil.rmtree(CACHE_DIR)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Extract
    print("\n[EXTRACT] Extracting questions...")
    extract_result = extract_question_paper(
        pdf_path=pdf_path,
        output_dir=CACHE_DIR,
        exam_code="0478",
    )
    print(f"[OK] Extracted {extract_result.question_count} questions")
    
    # Load and check text extraction by examining metadata.json files
    print(f"\n[CHECK] Checking text extraction...")
    
    text_extracted_count = 0
    for qdir in CACHE_DIR.glob("*_q*"):
        metadata_file = qdir / "metadata.json"
        if metadata_file.exists():
            import json
            data = json.loads(metadata_file.read_text())
            if data.get("root_text"):
                text_extracted_count += 1
    
    print(f"[OK] {text_extracted_count}/{extract_result.question_count} questions have extracted text")
    
    if text_extracted_count == 0:
        print("[WARNING] No questions have extracted text!")
        print("          Keyword search will fail.")
    
    # Load questions for building
    questions = load_questions(CACHE_DIR, "0478")
    
    # Test configurations
    test_configs = [
        {
            "name": "test1_low_marks",
            "target_marks": 10,
            "tolerance": 3,
            "seed": 11111,
            "topics": [],
        },
        {
            "name": "test2_medium_marks",
            "target_marks": 20,
            "tolerance": 5,
            "seed": 22222,
            "topics": ["00. Unknown"],
        },
        {
            "name": "test3_high_marks",
            "target_marks": 30,
            "tolerance": 8,
            "seed": 33333,
            "topics": [],
        },
        {
            "name": "test4_with_markscheme",
            "target_marks": 15,
            "tolerance": 5,
            "seed": 44444,
            "topics": [],
            "include_markscheme": True,
        },
        {
            "name": "test5_deterministic",
            "target_marks": 15,
            "tolerance": 3,
            "seed": 12345,
            "topics": [],
        },
        {
            "name": "test6_keyword_pool",
            "target_marks": 15,
            "tolerance": 5,
            "seed": 55555,
            "topics": [],
            "keyword_mode": True,
            "keywords": ["binary"],  # Keyword pool filtering - "binary" appears in Q1
        },
        {
            "name": "test7_pinned_question",
            "target_marks": 15,
            "tolerance": 5,
            "seed": 66666,
            "topics": [],
            "keyword_mode": True,
            "keywords": ["UNLIKELY_MATCH"],  # Won't match, relies on pins
            "keyword_questions": [],  # Will be populated with first question ID
        },
    ]
    
    # Populate keyword_questions for test7 with first question ID
    if text_extracted_count > 0:
        for cfg in test_configs:
            if cfg.get("name") == "test7_pinned_question" and "keyword_questions" in cfg:
                cfg["keyword_questions"] = [questions[0].id]  # Pin first question
                print(f"[PIN] Pinning question {questions[0].id} for test7")
    
    print(f"\n[BUILD] Generating {len(test_configs)} test PDFs...")
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n[{i}/{len(test_configs)}] Generating: {config['name']}")
        
        run_output = OUTPUT_DIR / config['name']
        
        builder_config = BuilderConfig(
            cache_path=CACHE_DIR,
            exam_code="0478",
            target_marks=config["target_marks"],
            tolerance=config["tolerance"],
            seed=config["seed"],
            topics=config.get("topics", []),
            output_dir=run_output,
            include_markscheme=config.get("include_markscheme", False),
            keyword_mode=config.get("keyword_mode", False),
            keywords=config.get("keywords", []),
            keyword_questions=config.get("keyword_questions", []),
        )
        
        try:
            result = build_exam(builder_config)
            
            print(f"  [OK] Generated: {result.questions_pdf}")
            print(f"       Questions: {result.selection.question_count}")
            print(f"       Marks: {result.total_marks}/{config['target_marks']}")
            print(f"       Pages: {result.page_count}")
            
            if result.markscheme_pdf:
                print(f"  [OK] Markscheme: {result.markscheme_pdf}")
                
        except Exception as e:
            print(f"  [ERROR] {e}")
    
    print(f"\n[DONE] All PDFs generated in: {OUTPUT_DIR}")
    print(f"\nGenerated files:")
    for pdf in sorted(OUTPUT_DIR.rglob("*.pdf")):
        print(f"  - {pdf.relative_to(OUTPUT_DIR.parent)}")

if __name__ == "__main__":
    main()
