#!/usr/bin/env python3
"""Generate detection issue reports from diagnostic data.

Creates an HTML page focused on detection failures where:
- Labels were skipped/not identified
- BBox locations were unexpected
- Visual snippets show context from prev -> next detected element
- Part validation status is displayed
"""

from pathlib import Path
import json
from io import BytesIO
import base64

try:
    from PIL import Image
except ImportError:
    Image = None

SLICES_ROOT = Path("workspace/slices_cache")
REPORT_DIR = Path("workspace/quality_reports")


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Detection Issues: {exam_code}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: #1e1e1e; 
            color: #d4d4d4; 
            margin: 0; 
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{ color: #fff; border-bottom: 2px solid #444; padding-bottom: 10px; }}
        .summary {{ 
            background: #252526; 
            padding: 15px; 
            border-radius: 8px; 
            margin: 20px 0; 
            display: flex; 
            gap: 20px; 
            flex-wrap: wrap; 
        }}
        .summary-item {{ 
            background: #333; 
            padding: 10px 15px; 
            border-radius: 4px; 
        }}
        .summary-item strong {{ color: #9cdcfe; }}
        
        .issue {{ 
            background: #252526; 
            border-radius: 8px; 
            margin: 20px 0; 
            padding: 20px; 
            border-left: 4px solid #f48771; 
        }}
        .issue.reviewed {{ border-left-color: #4ec9b0; }}
        .issue-header {{ 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .issue-type {{ 
            font-size: 12px; 
            font-weight: bold; 
            color: #f48771; 
            background: rgba(244,135,113,0.15);
            padding: 4px 8px;
            border-radius: 4px;
            text-transform: uppercase;
        }}
        .issue-location {{ 
            font-size: 13px; 
            color: #888; 
        }}
        .issue-message {{ 
            font-size: 16px; 
            color: #fff; 
            margin: 15px 0; 
        }}
        
        .context-section {{
            background: #333;
            border-radius: 6px;
            padding: 15px;
            margin: 15px 0;
        }}
        .context-title {{
            font-size: 11px;
            text-transform: uppercase;
            color: #888;
            margin-bottom: 10px;
        }}
        .label-info {{
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
            font-size: 13px;
            color: #4ec9b0;
            margin: 5px 0;
        }}
        .label-info.prev {{ color: #9cdcfe; }}
        .label-info.next {{ color: #ce9178; }}
        
        .validation {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 8px;
            margin-top: 10px;
        }}
        .validation-item {{
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
        }}
        .validation-item.valid {{
            background: rgba(78, 201, 176, 0.15);
            border-left: 3px solid #4ec9b0;
        }}
        .validation-item.invalid {{
            background: rgba(244, 135, 113, 0.15);
            border-left: 3px solid #f48771;
        }}
        .validation-part {{
            font-weight: bold;
            color: #fff;
        }}
        .validation-status {{
            color: #888;
            font-size: 11px;
        }}
        
        .visual-context {{
            margin-top: 15px;
            max-height: 400px;
            overflow-y: auto;
            overflow-x: hidden;
            border: 1px solid #444;
            border-radius: 4px;
            background: #1a1a1a;
        }}
        .visual-context img {{
            display: block;
            width: 100%;
            max-width: 100%;
            height: auto;
            border: none;
        }}
        .visual-label {{
            font-size: 11px;
            color: #666;
            margin-bottom: 5px;
        }}
        
        .pdf-content {{
            background: #1e1e1e;
            padding: 10px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 11px;
            white-space: pre-wrap;
            max-height: 200px;
            overflow-y: auto;
            color: #888;
            margin-top: 10px;
        }}
        
        .no-issues {{
            text-align: center;
            padding: 60px;
            color: #4ec9b0;
            font-size: 18px;
        }}
        
        /* Feedback UI */
        .feedback-section {{
            background: #2d2d2d;
            border-radius: 6px;
            padding: 15px;
            margin-top: 15px;
            border: 1px dashed #444;
        }}
        .feedback-section .context-title {{
            color: #9cdcfe;
        }}
        .feedback-row {{
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }}
        .feedback-row select {{
            padding: 8px;
            background: #333;
            border: 1px solid #444;
            color: #d4d4d4;
            border-radius: 4px;
            min-width: 200px;
        }}
        .feedback-row textarea {{
            flex: 1;
            min-width: 300px;
            min-height: 60px;
            padding: 8px;
            background: #333;
            border: 1px solid #444;
            color: #d4d4d4;
            border-radius: 4px;
            resize: vertical;
        }}
        .feedback-row textarea:focus, .feedback-row select:focus {{
            outline: none;
            border-color: #9cdcfe;
        }}
        
        /* Export button */
        .export-container {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
        }}
        .export-btn {{
            background: #0e639c;
            color: #fff;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        .export-btn:hover {{ background: #1177bb; }}
        .export-btn.secondary {{ background: #444; }}
        .export-btn.secondary:hover {{ background: #555; }}
        
        .status-badge {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: #333;
            padding: 10px 15px;
            border-radius: 6px;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <h1>Detection Issues: {exam_code}</h1>
    <div class="summary">
        <div class="summary-item"><strong>Total Issues:</strong> {total_issues}</div>
        {summary_by_type}
    </div>
    
    <div class="status-badge">
        Reviewed: <span id="reviewed-count">0</span> / {total_issues}
    </div>
    
    {content}
    
    <div class="export-container">
        <button class="export-btn secondary" onclick="clearAll()">Clear All</button>
        <button class="export-btn" onclick="exportFeedback()">Export Feedback JSON</button>
    </div>
    
    <script>
        const issueData = {issues_json};
        
        function updateReviewCount() {{
            let count = 0;
            document.querySelectorAll('.issue').forEach((el, i) => {{
                const cat = el.querySelector('select').value;
                const notes = el.querySelector('textarea').value;
                if (cat !== '' || notes.trim() !== '') {{
                    count++;
                    el.classList.add('reviewed');
                }} else {{
                    el.classList.remove('reviewed');
                }}
            }});
            document.getElementById('reviewed-count').textContent = count;
        }}
        
        function clearAll() {{
            if (!confirm('Clear all feedback?')) return;
            document.querySelectorAll('.issue select').forEach(s => s.value = '');
            document.querySelectorAll('.issue textarea').forEach(t => t.value = '');
            updateReviewCount();
        }}
        
        async function exportFeedback() {{
            const feedback = [];
            document.querySelectorAll('.issue').forEach((el, i) => {{
                const cat = el.querySelector('select').value;
                const notes = el.querySelector('textarea').value.trim();
                
                // Include all issues with feedback OR all for completeness
                if (cat || notes) {{
                    feedback.push({{
                        issue_index: i,
                        issue_type: issueData[i].issue_type,
                        pdf_name: issueData[i].pdf_name,
                        exam_code: issueData[i].exam_code,
                        question_number: issueData[i].question_number,
                        message: issueData[i].message,
                        y_span: issueData[i].y_span,
                        prev_label: issueData[i].prev_label || null,
                        next_label: issueData[i].next_label || null,
                        feedback_category: cat || 'unreviewed',
                        feedback_notes: notes,
                        agent_action_hint: getActionHint(cat, notes),
                    }});
                }}
            }});
            
            if (feedback.length === 0) {{
                alert('No feedback to export. Please review at least one issue.');
                return;
            }}
            
            const report = {{
                exam_code: '{exam_code}',
                generated_at: new Date().toISOString(),
                total_issues: issueData.length,
                reviewed_count: feedback.length,
                feedback: feedback
            }};
            
            const jsonStr = JSON.stringify(report, null, 2);
            const filename = '{exam_code}_feedback_' + new Date().toISOString().slice(0,10) + '.json';
            
            // Try File System API
            if ('showSaveFilePicker' in window) {{
                try {{
                    const handle = await window.showSaveFilePicker({{
                        suggestedName: filename,
                        types: [{{ accept: {{ 'application/json': ['.json'] }} }}]
                    }});
                    const writable = await handle.createWritable();
                    await writable.write(jsonStr);
                    await writable.close();
                    alert('Saved: ' + filename);
                    return;
                }} catch (err) {{ if (err.name !== 'AbortError') console.error(err); }}
            }}
            
            // Fallback download
            const blob = new Blob([jsonStr], {{type: 'application/json'}});
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            a.click();
        }}
        
        function getActionHint(category, notes) {{
            switch(category) {{
                case 'false_positive':
                    return 'Consider adjusting detection thresholds or adding exception rule';
                case 'missed_label':
                    return 'Investigate label detection algorithm - may need pattern adjustment';
                case 'bbox_position':
                    return 'Review mark box detection margins and alignment logic';
                case 'algorithm_bug':
                    return 'Code review needed in detection pipeline';
                case 'pdf_quality':
                    return 'No action needed - source PDF has quality issues';
                default:
                    return notes ? 'Review user notes for context' : null;
            }}
        }}
        
        // Auto-save to localStorage
        function saveLocal() {{
            const state = [];
            document.querySelectorAll('.issue').forEach((el, i) => {{
                state.push({{
                    cat: el.querySelector('select').value,
                    notes: el.querySelector('textarea').value
                }});
            }});
            localStorage.setItem('feedback_{exam_code}', JSON.stringify(state));
        }}
        
        function loadLocal() {{
            const saved = localStorage.getItem('feedback_{exam_code}');
            if (saved) {{
                const state = JSON.parse(saved);
                document.querySelectorAll('.issue').forEach((el, i) => {{
                    if (state[i]) {{
                        el.querySelector('select').value = state[i].cat || '';
                        el.querySelector('textarea').value = state[i].notes || '';
                    }}
                }});
                updateReviewCount();
            }}
        }}
        
        // Event listeners
        document.querySelectorAll('.issue select, .issue textarea').forEach(el => {{
            el.addEventListener('change', () => {{ updateReviewCount(); saveLocal(); }});
            el.addEventListener('input', () => {{ saveLocal(); }});
        }});
        
        // Load on start
        loadLocal();
    </script>
</body>
</html>
"""


def crop_debug_image(img_path: Path, y_span: tuple, padding: int = 100) -> str:
    """Crop debug image to y_span with padding and return base64 data URI.
    
    Args:
        img_path: Path to the debug composite image
        y_span: Tuple of (y_start, y_end) pixel coordinates
        padding: Pixels to add above and below the span
        
    Returns:
        Base64 data URI for the cropped image, or file:// URI if cropping fails
    """
    if Image is None:
        return f"file://{img_path.absolute()}"
    
    try:
        with Image.open(img_path) as im:
            width, height = im.size
            y_start, y_end = y_span
            
            # Add padding
            crop_top = max(0, int(y_start) - padding)
            crop_bottom = min(height, int(y_end) + padding)
            
            # Ensure valid crop
            if crop_bottom > crop_top:
                cropped = im.crop((0, crop_top, width, crop_bottom))
                
                # Convert to base64
                buffered = BytesIO()
                cropped.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                return f"data:image/png;base64,{img_str}"
    except Exception:
        pass
    
    return f"file://{img_path.absolute()}"


def find_debug_image(slices_root: Path, exam_code: str, pdf_name: str, question_number: int) -> Path | None:
    """Find the debug composite image for a question.
    
    Args:
        slices_root: Root directory of slices cache
        exam_code: Exam code (e.g., "0620")
        pdf_name: PDF filename without extension
        question_number: Question number
        
    Returns:
        Path to debug composite if found, else None
    """
    pdf_stem = Path(pdf_name).stem
    q_id = f"{pdf_stem}_q{question_number}"
    debug_filename = f"{q_id}_debug_composite.png"
    
    exam_dir = slices_root / exam_code
    if not exam_dir.exists():
        return None
    
    found = list(exam_dir.glob(f"**/{debug_filename}"))
    return found[0] if found else None


def generate_issue_html(issue: dict, slices_root: Path, exam_code: str) -> str:
    """Generate HTML for a single detection issue."""
    issue_type = issue.get("issue_type", "unknown")
    pdf_name = issue.get("pdf_name", "")
    q_num = issue.get("question_number", 0)
    message = issue.get("message", "")
    y_span = issue.get("y_span", [0, 0])
    prev_label = issue.get("prev_label", "")
    next_label = issue.get("next_label", "")
    pdf_content = issue.get("pdf_content_between_labels", "")
    validation = issue.get("validation_outcome", {})
    
    # Build label info section
    label_html = ""
    if prev_label or next_label:
        label_html = f"""
        <div class="context-section">
            <div class="context-title">Detection Context</div>
            <div class="label-info prev">▶ Previous: {prev_label}</div>
            <div class="label-info next">▶ Next: {next_label}</div>
        </div>
        """
    
    # Build validation outcome section
    validation_html = ""
    if validation:
        items = []
        for part_id, status in validation.items():
            is_valid = status.upper().startswith("VALID")
            css_class = "valid" if is_valid else "invalid"
            items.append(f"""
            <div class="validation-item {css_class}">
                <div class="validation-part">{part_id}</div>
                <div class="validation-status">{status}</div>
            </div>
            """)
        validation_html = f"""
        <div class="context-section">
            <div class="context-title">Part Validation Status</div>
            <div class="validation">{" ".join(items)}</div>
        </div>
        """
    
    # Build visual context section
    visual_html = ""
    debug_img = find_debug_image(slices_root, exam_code, pdf_name, q_num)
    if debug_img:
        # Check if we have a valid y_span for cropping
        if y_span and y_span != [0, 0] and y_span[0] < y_span[1]:
            img_src = crop_debug_image(debug_img, tuple(y_span))
            y_start, y_end = y_span
            visual_html = f"""
            <div class="visual-context">
                <div class="visual-label">Visual Context (Y={y_start} → {y_end})</div>
                <img src="{img_src}" alt="Detection context">
            </div>
            """
        else:
            # No y_span available - show full debug composite
            visual_html = f"""
            <div class="visual-context">
                <div class="visual-label">Full Question Debug Composite</div>
                <img src="file://{debug_img.absolute()}" alt="Full debug composite">
            </div>
            """
    
    # Build PDF content preview
    content_html = ""
    if pdf_content:
        # Truncate and escape
        text = pdf_content[:500]
        if len(pdf_content) > 500:
            text += "..."
        # Basic HTML escape
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        content_html = f"""
        <div class="context-section">
            <div class="context-title">PDF Text Between Labels</div>
            <div class="pdf-content">{text}</div>
        </div>
        """
    
    return f"""
    <div class="issue">
        <div class="issue-header">
            <span class="issue-type">{issue_type.replace("_", " ")}</span>
            <span class="issue-location">{pdf_name} • Question {q_num}</span>
        </div>
        <div class="issue-message">{message}</div>
        {label_html}
        {validation_html}
        {visual_html}
        {content_html}
        <div class="feedback-section">
            <div class="context-title">Feedback for Agent</div>
            <div class="feedback-row">
                <select>
                    <option value="">-- Select Category --</option>
                    <option value="false_positive">False Positive (not a real issue)</option>
                    <option value="missed_label">Missed Label Detection</option>
                    <option value="bbox_position">BBox Position Issue</option>
                    <option value="algorithm_bug">Algorithm Bug</option>
                    <option value="pdf_quality">PDF Quality Issue</option>
                    <option value="needs_investigation">Needs Investigation</option>
                </select>
                <textarea placeholder="Describe the issue, expected behavior, or suggested fix..."></textarea>
            </div>
        </div>
    </div>
    """


def generate_report(exam_code: str, report_path: Path, slices_root: Path = SLICES_ROOT) -> Path | None:
    """Generate detection issue report for an exam code.
    
    Args:
        exam_code: Exam code to generate report for
        report_path: Output path for HTML report
        slices_root: Root directory of slices cache
        
    Returns:
        Path to generated report, or None if no diagnostics found
    """
    diag_path = slices_root / exam_code / "_metadata" / "detection_diagnostics.json"
    
    if not diag_path.exists():
        return None
    
    try:
        data = json.loads(diag_path.read_text())
    except (json.JSONDecodeError, IOError) as e:
        print(f"Failed to load diagnostics for {exam_code}: {e}")
        return None
    
    issues = data.get("issues", [])
    summary_by_type = data.get("summary_by_type", {})
    
    # Filter out non-actionable issues (system working correctly)
    # "Skipping malformed mark box" = correct behavior, not a problem
    actionable_issues = [
        issue for issue in issues
        if "Skipping malformed mark box" not in issue.get("message", "")
    ]
    
    # Recalculate summary for filtered issues
    filtered_summary = {}
    for issue in actionable_issues:
        itype = issue.get("issue_type", "unknown")
        filtered_summary[itype] = filtered_summary.get(itype, 0) + 1
    
    # Generate content
    if not actionable_issues:
        content = '<div class="no-issues">✓ No detection issues found</div>'
    else:
        content = "\n".join(
            generate_issue_html(issue, slices_root, exam_code)
            for issue in actionable_issues
        )
    
    # Generate summary items (using filtered summary)
    summary_html = "".join(
        f'<div class="summary-item"><strong>{t.replace("_", " ").title()}:</strong> {c}</div>'
        for t, c in filtered_summary.items()
    )
    
    # Prepare issues JSON for JavaScript (strip pdf_content for size)
    issues_for_js = []
    for issue in actionable_issues:
        issue_copy = {k: v for k, v in issue.items() if k != "pdf_content_between_labels"}
        issues_for_js.append(issue_copy)
    
    html = HTML_TEMPLATE.format(
        exam_code=exam_code,
        total_issues=len(actionable_issues),
        summary_by_type=summary_html,
        content=content,
        issues_json=json.dumps(issues_for_js),
    )
    
    report_path.write_text(html)
    return report_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate detection issue reports")
    parser.add_argument("--input", "-i", type=Path, default=SLICES_ROOT, 
                        help="Input slices directory")
    parser.add_argument("--output", "-o", type=Path, default=REPORT_DIR, 
                        help="Output reports directory")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    
    if not args.input.exists():
        print(f"Error: Input directory {args.input} does not exist")
        return

    # Find all exam codes with diagnostics
    exam_codes = []
    for d in args.input.iterdir():
        if d.is_dir() and not d.name.startswith("."):
            diag_file = d / "_metadata" / "detection_diagnostics.json"
            if diag_file.exists():
                exam_codes.append(d.name)
    
    if not exam_codes:
        print("No detection_diagnostics.json files found")
        return
    
    generated_reports = []
    
    for exam_code in sorted(exam_codes):
        print(f"Processing {exam_code}...")
        report_path = args.output / f"{exam_code}_detection_issues.html"
        
        result = generate_report(exam_code, report_path, args.input)
        
        if result:
            print(f"  Report: {report_path}")
            generated_reports.append(report_path)
        else:
            print(f"  Skipped (no issues or error)")
    
    if generated_reports:
        print(f"\nGenerated {len(generated_reports)} reports")
        print(f"Open: file://{generated_reports[0].absolute()}")


if __name__ == "__main__":
    main()
