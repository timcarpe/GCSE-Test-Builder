
import json
import fitz
import os
import base64
import io
from pathlib import Path
from datetime import datetime

# Configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
SLICES_DIR = WORKSPACE_DIR / "slices_cache"
OUTPUT_HTML = WORKSPACE_DIR / "master_detection_report.html"

# CSS Styles
CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; max_width: 1200px; margin: 0 auto; padding: 20px; color: #333; background: #f4f6f8; }
h1 { border-bottom: 2px solid #eaeaea; padding-bottom: 10px; color: #2c3e50; }
h2 { margin-top: 40px; color: #34495e; border-bottom: 1px solid #ddd; padding-bottom: 5px; }
h3 { margin-top: 20px; color: #2980b9; }
.card { background: #fff; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e1e4e8; }
.summary-table { width: 100%; border-collapse: collapse; margin-bottom: 30px; background: white; }
.summary-table th, .summary-table td { padding: 12px; border: 1px solid #ddd; text-align: left; }
.summary-table th { background: #f8f9fa; font-weight: 600; }
.issue-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 15px; }
.tag { padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 600; }
.tag-layout { background: #e3f2fd; color: #1976d2; }
.tag-invalid { background: #ffebee; color: #c62828; }
.tag-manual { background: #f3e5f5; color: #7b1fa2; }
.evidence-container { margin: 15px 0; border: 1px solid #ddd; background: #fafafa; padding: 10px; text-align: center; }
.evidence-img { max-width: 100%; max-height: 600px; border: 1px solid #ccc; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
.gemini-field { background: #fef9e7; border: 1px dashed #f1c40f; padding: 15px; margin-top: 15px; border-radius: 6px; }
.gemini-label { font-weight: bold; color: #d35400; display: block; margin-bottom: 5px; font-size: 0.9em; text-transform: uppercase; letter-spacing: 0.5px; }
.gemini-input { width: 100%; min-height: 80px; border: 1px solid #e0e0e0; background: #fff; padding: 10px; font-family: inherit; resize: vertical; box-sizing: border-box; }
.metadata { color: #666; font-size: 0.9em; margin-bottom: 10px; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
.meta-item { background: #f1f3f4; padding: 5px 10px; border-radius: 4px; }
"""

def find_composite_image(exam_code, pdf_name, q_num):
    """Find composite.png for a given question."""
    # Try constructing standard paths
    # slices_cache/{exam_code}/{topic}/{pdf_name}_q{q_num}/composite.png
    # Since topic is unknown, search recursively in exam_dir
    exam_dir = SLICES_DIR / exam_code
    if not exam_dir.exists():
        return None
        
    target_folder = f"{pdf_name}_q{q_num}"
    
    # Fast recursive glob
    for path in exam_dir.rglob("composite.png"):
        if path.parent.name == target_folder:
            return path
    return None

from PIL import Image

def create_evidence_crop(composite_path, y_span, padding=50):
    """
    Open composite image, crop to y_span with padding, return base64 string.
    """
    try:
        with Image.open(composite_path) as img:
            w, h = img.size
            
            y1, y2 = y_span
            
            # Validate coords
            if y1 >= y2:
                return None
                
            # Apply padding
            crop_y1 = max(0, y1 - padding)
            crop_y2 = min(h, y2 + padding)
            
            # Crop: (left, top, right, bottom)
            crop_img = img.crop((0, crop_y1, w, crop_y2))
            
            # Save to buffer
            buffer = io.BytesIO()
            crop_img.save(buffer, format="PNG")
            img_data = buffer.getvalue()
            
            return base64.b64encode(img_data).decode("utf-8")
        
    except Exception as e:
        print(f"Error creating crop for {composite_path}: {e}")
        return None

def analyze_issue(issue):
    """
    Perform deep code-level analysis on the issue.
    Based on tracing bounds_calculator.py logic.
    """
    issue_type = issue.get("issue_type")
    message = issue.get("message", "")
    
    analysis = "Manual inspection required."
    cause = "Unknown - requires code tracing."
    fix = "Investigate source PDF and detection pipeline."
    
    if issue_type == "layout_issue" and "Mark boxes vary" in message:
        analysis = (
            "Mark box right-edge variance detected. Mark boxes on this page have "
            "inconsistent X-coordinates (PDF scan skew or variable typesetting)."
        )
        cause = (
            "PDF visual variance. The bounds calculator uses MAX(right_edges) as fallback. "
            "This is cosmetic and handled by normalization."
        )
        fix = (
            "No code change required. Monitor only if variance >200px "
            "(indicating possible mark detection failure)."
        )
        
    elif issue_type == "invalid_question" and "Suspicious part structure" in message:
        analysis = (
            "Structure heuristic triggered. The question has many romans (i,ii,iii...) "
            "under few letters - common in CS 9618 long-form questions. NOT a detection failure."
        )
        cause = (
            "Heuristic in pipeline._validate_structure_heuristics flags romans >> letters. "
            "Conservative check causing false positives on legitimate deep-nested questions."
        )
        fix = (
            "Option 1: Raise ratio threshold. "
            "Option 2: Whitelist 9618. "
            "Option 3: Convert 'INVALID' to 'WARNING'."
        )
        
    return analysis, cause, fix

def process_issue(issue, exam_code):
    """Process a single issue into HTML components."""
    issue_type = issue.get("issue_type", "unknown")
    pdf_name = issue.get("pdf_name", "?")
    q_num = issue.get("question_number", "?")
    message = issue.get("message", "")
    y_span = issue.get("y_span")
    prev_label = issue.get("prev_label")
    next_label = issue.get("next_label")
    
    css_class = "tag-layout" if "layout" in issue_type else "tag-invalid"
    
    # AI Analysis
    ai_analysis, ai_cause, ai_fix = analyze_issue(issue)
    
    # Generate Evidence
    evidence_html = "<div class='evidence-container'><em>No visual evidence generated (missing span or composite)</em></div>"
    
    if y_span and pdf_name != "?" and q_num != "?":
        comp_path = find_composite_image(exam_code, pdf_name, q_num)
        if comp_path:
            b64_img = create_evidence_crop(comp_path, y_span)
            if b64_img:
                evidence_html = f"""
                <div class='evidence-container'>
                    <img src="data:image/png;base64,{b64_img}" class='evidence-img' />
                    <div style='margin-top:5px; font-size:0.8em; color:#666;'>
                        Span: Y={y_span[0]}-{y_span[1]} | Source: {comp_path.name}
                    </div>
                </div>
                """
            else:
                 evidence_html = "<div class='evidence-container'><em>Failed to generate crop from composite</em></div>"
        else:
             evidence_html = f"<div class='evidence-container'><em>Composite image not found for {pdf_name} Q{q_num}</em></div>"

    html = f"""
    <div class="card">
        <div class="issue-header">
            <h3>{issue_type.replace('_', ' ').title()} - {pdf_name} Q{q_num}</h3>
            <span class="tag {css_class}">{issue_type}</span>
        </div>
        
        <div class="metadata">
            <div class="meta-item"><strong>Message:</strong> {message}</div>
            <div class="meta-item"><strong>Y-Span:</strong> {y_span}</div>
            <div class="meta-item"><strong>Prev Label:</strong> {prev_label or 'N/A'}</div>
            <div class="meta-item"><strong>Next Label:</strong> {next_label or 'N/A'}</div>
        </div>
        
        {evidence_html}
        
        <div class="gemini-field">
            <span class="gemini-label">&lt;Gemini Inference Field&gt;</span>
            <div class="gemini-content">
                <strong>Analysis:</strong> {ai_analysis}<br><br>
                <strong>Likely Cause:</strong> {ai_cause}<br>
                <strong>Proposed Fix:</strong> {ai_fix}
            </div>
        </div>
    </div>
    """
    return html

def generate_summary(all_issues):
    """Generate AI summary based on deep code analysis."""
    total_issues = 0
    layout_issues = 0
    invalid_struct = 0
    exam_codes = set()
    
    for code, issues in all_issues.items():
        exam_codes.add(code)
        total_issues += len(issues)
        for i in issues:
            it = i.get("issue_type")
            msg = i.get("message", "")
            if it == "layout_issue":
                layout_issues += 1
            if it == "invalid_question" and "Suspicious part structure" in msg:
                invalid_struct += 1
                
    summary_text = "<p><strong>Deep Analysis Summary (Code-Level Review)</strong></p>"
    
    summary_text += f"""
    <p>Analyzed {total_issues} diagnostic issues. However, the <strong>actual CLI loading failures</strong> 
    have a DIFFERENT root cause not captured in these diagnostics:</p>
    
    <div style='background:#fff3cd; padding:15px; border-radius:6px; margin:15px 0;'>
        <h4 style='color:#856404; margin-top:0;'>⚠️ Critical Finding: Bounds Overlap Bug</h4>
        <p><code>Sibling bounds cannot overlap: 7(a)(i) (bottom=1262) overlaps with 7(a)(ii) (top=1256)</code></p>
        <ul>
            <li><strong>Location:</strong> <code>bounds_calculator.py:863</code></li>
            <li><strong>Bug:</strong> Mark box's <code>bbox[3]</code> (bottom) extends past next sibling's Y without clamping.</li>
            <li><strong>Fix:</strong> <code>roman_bottom = min(mark.bbox[3], next_roman_y)</code></li>
        </ul>
    </div>
    
    <div style='background:#fff3cd; padding:15px; border-radius:6px; margin:15px 0;'>
        <h4 style='color:#856404; margin-top:0;'>⚠️ Secondary Finding: Letter Sorting Bug</h4>
        <p><code>Children must be sorted: 7(a) (top=903) should be above 7(b) (top=831)</code></p>
        <ul>
            <li><strong>Bug:</strong> Letters processed alphabetically, not by Y-position.</li>
            <li><strong>Fix:</strong> Sort letters by <code>y_position</code> at line 775.</li>
        </ul>
    </div>
    """
    
    if layout_issues > 0:
        summary_text += f"""
        <h4>Informational: Layout Variance ({layout_issues} issues)</h4>
        <p>Mark box alignment variance is handled correctly by normalization. No action needed.</p>
        """
        
    if invalid_struct > 0:
        summary_text += f"""
        <h4>Informational: Structure Heuristic ({invalid_struct} issues)</h4>
        <p>False positives from conservative ratio check. Consider raising threshold for 9618.</p>
        """
        
    return summary_text

def main():
    print("Starting Main Diagnostic Report Generation...")
    
    # 1. Gather all Diagnostics
    diagnostic_files = list(SLICES_DIR.glob(f"*/_metadata/detection_diagnostics.json"))
    
    all_issues = {} # exam_code -> list of issues
    total_issues = 0
    
    for d_path in diagnostic_files:
        exam_code = d_path.parent.parent.name
        try:
            with open(d_path, 'r') as f:
                data = json.load(f)
                issues = data.get("issues", [])
                if issues:
                    all_issues[exam_code] = issues
                    total_issues += len(issues)
        except Exception as e:
            print(f"Failed to read {d_path}: {e}")
            
    # 2. Build HTML
    html_body = []
    
    # Summary Section
    summary_rows = ""
    for code, issues in all_issues.items():
        layout_count = len([i for i in issues if i.get("issue_type") == "layout_issue"])
        invalid_count = len([i for i in issues if i.get("issue_type") == "invalid_question"])
        other_count = len(issues) - layout_count - invalid_count
        
        summary_rows += f"""
        <tr>
            <td>{code}</td>
            <td>{len(issues)}</td>
            <td>{layout_count}</td>
            <td>{invalid_count}</td>
            <td>{other_count}</td>
        </tr>
        """
        
    ai_summary_content = generate_summary(all_issues)
        
    html_body.append(f"""
    <h1>Master Detection Diagnostics Report</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <h2>1. Executive Summary</h2>
    <table class="summary-table">
        <thead>
            <tr>
                <th>Exam Code</th>
                <th>Total Issues</th>
                <th>Layout Issues</th>
                <th>Invalid Questions</th>
                <th>Other</th>
            </tr>
        </thead>
        <tbody>
            {summary_rows}
        </tbody>
    </table>
    
    <div class="gemini-field" style="background: #e8f8f5; border-color: #1abc9c;">
        <span class="gemini-label">&lt;Gemini Summary&gt;</span>
        {ai_summary_content}
    </div>
    """)
    
    # Details Section
    html_body.append("<h2>2. Detailed Issue Analysis</h2>")
    
    for code, issues in sorted(all_issues.items()):
        html_body.append(f"<h2>Exam Code: {code}</h2>")
        
        # Sort issues by type and question
        sorted_issues = sorted(issues, key=lambda x: (x.get("issue_type", ""), x.get("pdf_name", ""), x.get("question_number", 0)))
        
        for issue in sorted_issues:
            card_html = process_issue(issue, code)
            html_body.append(card_html)
            
    # Assemble Full Page
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Master Detection Report</title>
        <meta charset="utf-8">
        <style>{CSS}</style>
    </head>
    <body>
        {''.join(html_body)}
    </body>
    </html>
    """
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(full_html)
        
    print(f"Success! Master report generated at: {OUTPUT_HTML}")
    print(f"Total issues processed: {total_issues}")

if __name__ == "__main__":
    main()
