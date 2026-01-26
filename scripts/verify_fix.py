
import sys
import shutil
import json
from pathlib import Path

# Add src to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from gcse_toolkit.extractor_v2.pipeline import extract_question_paper, ExtractionConfig

def main():
    # Setup
    pdf_path = project_root / "workspace/input_pdfs/9618/9618_w22_qp_41.pdf"
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        # Try finding it
        found = list(project_root.rglob("9618_w22_qp_41.pdf"))
        if found:
            pdf_path = found[0]
            print(f"Found PDF at {pdf_path}")
        else:
            return 1

    output_dir = project_root / "workspace/verify_fix_output"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run Extraction
    print(f"Running extraction on {pdf_path.name}...")
    config = ExtractionConfig(run_diagnostics=True)  
    try:
        extract_question_paper(
            pdf_path=pdf_path,
            output_dir=output_dir,
            exam_code="9618",
            config=config
        )
    except Exception as e:
        print(f"Extraction failed: {e}")
        return 1
        
    # Check Diagnostics
    diag_path = output_dir / "9618" / "_metadata" / "detection_diagnostics.json"
    if not diag_path.exists():
        print("Diagnostics file not generated!")
        return 1
        
    with open(diag_path, "r") as f:
        data = json.load(f)
        issues = data.get("issues", [])
        
    # Filter for this PDF (should be only this pdf)
    pdf_issues = [i for i in issues if i.get("pdf_name") == "9618_w22_qp_41"]
    
    # Count Roman Resets
    resets = [i for i in pdf_issues if i.get("issue_type") == "roman_reset"]
    
    print(f"\nTotal Issues Found: {len(pdf_issues)}")
    print(f"Roman Resets: {len(resets)}")
    
    for r in resets:
        print(f"  FAIL: {r.get('message')}")
        
    if len(resets) == 0:
        print("\nSUCCESS: No Roman Resets found. Fix verified!")
        return 0
    else:
        print("\nFAILURE: Roman Resets still present.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
