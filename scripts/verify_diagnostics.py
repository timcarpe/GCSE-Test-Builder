
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
    # Target PDF known to have layout issues: 0478_s24_qp_21 (Page 0/Q6)
    pdf_path = project_root / "workspace/input_pdfs/0478/0478_s24_qp_21.pdf"
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        # Try finding it
        found = list(project_root.rglob("0478_s24_qp_21.pdf"))
        if found:
            pdf_path = found[0]
            print(f"Found PDF at {pdf_path}")
        else:
            return 1

    output_dir = project_root / "workspace/verify_diagnostics_output"
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
            exam_code="0478",
            config=config
        )
    except Exception as e:
        print(f"Extraction failed: {e}")
        return 1
        
    # Check Diagnostics
    diag_path = output_dir / "0478" / "_metadata" / "detection_diagnostics.json"
    if not diag_path.exists():
        print("Diagnostics file not generated!")
        return 1
        
    with open(diag_path, "r") as f:
        data = json.load(f)
        issues = data.get("issues", [])
        
    # Filter for this PDF
    pdf_issues = [i for i in issues if i.get("pdf_name") == "0478_s24_qp_21"]
    
    # Check for layout_issue
    layout_issues = [i for i in pdf_issues if i.get("issue_type") == "layout_issue"]
    
    print(f"\nTotal Issues Found: {len(pdf_issues)}")
    print(f"Layout Issues: {len(layout_issues)}")
    
    for i in layout_issues:
        print(f"  FOUND: {i.get('message')}")
        print(f"         Y-Span: {i.get('y_span')}")
        print(f"         Prev Label: {i.get('prev_label')}")
        print(f"         Next Label: {i.get('next_label')}")
        
    if len(layout_issues) > 0:
        print("\nSUCCESS: Layout issues correctly logged!")
        return 0
    else:
        print("\nFAILURE: Expected layout issues were not found.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
