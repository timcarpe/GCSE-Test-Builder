
import base64
from pathlib import Path

# Config
WORKSPACE_DIR = Path("/Users/timothy.carpenter/Documents/GCSE-Tool-Kit/workspace")
ARTIFACTS_DIR = Path("/Users/timothy.carpenter/.gemini/antigravity/brain/5b87401d-111c-45c0-ba45-a4b96ef59327")
EVIDENCE_DIR = WORKSPACE_DIR / "evidence"

OUTPUT_HTML = ARTIFACTS_DIR / "detection_analysis_report.html"

def get_b64_image(filename):
    path = EVIDENCE_DIR / filename
    if not path.exists():
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def main():
    # Load images
    img1 = get_b64_image("9618_w22_qp_41_q1_roman_reset_0.png")
    img2 = get_b64_image("9618_w23_qp_11_q8_roman_reset_0.png")
    img3 = get_b64_image("0478_m24_qp_12_q6_roman_reset_2.png")
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Detection Diagnostics Analysis</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; max_width: 800px; margin: 0 auto; padding: 20px; color: #333; }}
            h1 {{ border-bottom: 2px solid #eaeaea; padding-bottom: 10px; }}
            h2 {{ margin-top: 30px; color: #0056b3; }}
            .finding {{ background: #f9f9f9; padding: 20px; border-radius: 8px; margin-bottom: 30px; border: 1px solid #ddd; }}
            .evidence-img {{ width: 100%; border: 1px solid #ccc; margin-top: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .caption {{ font-size: 0.9em; color: #666; font-style: italic; margin-top: 6px; }}
            .impact-high {{ color: #d73a49; font-weight: bold; }}
            .impact-med {{ color: #b08800; font-weight: bold; }}
            code {{ background: #eee; padding: 2px 5px; border-radius: 4px; font-family: monospace; }}
        </style>
    </head>
    <body>
        <h1>Detection Diagnostics Analysis Report</h1>
        
        <p><strong>Date:</strong> 2025-12-19<br>
        <strong>Status:</strong> Analysis Complete</p>
        
        <h2>1. Executive Summary</h2>
        <p>An analysis of 194 detection diagnostics issues confirmed that <strong>90% of failures in 9618 papers are caused by instructional text ("Copy and paste...")</strong> containing label-like strings. The detection algorithm currently lacks horizontal filtering, treating these right-aligned instructions as new question parts.</p>
        
        <h2>2. Detailed Findings & Verification</h2>

        <div class="finding">
            <h3>Finding 1: Evidence Document Instructions (The "Paper 4" Issue)</h3>
            <p><span class="impact-high">Impact: HIGH</span> (~50+ issues)</p>
            <p><strong>Description:</strong> Paper 4 questions consistently include instructions like <em>"Copy and paste the program code into part 1(d)(i) in the evidence document"</em>. The detector incorrectly identifies the <code>(i)</code> in this sentence as a new label.</p>
            <img src="data:image/png;base64,{img1}" class="evidence-img">
            <div class="caption">Verification: Blue box shows the valid previous label. Red box shows the FALSE positive detected in the far-right instruction text. Yellow highlight shows the "gap" region scanned.</div>
        </div>

        <div class="finding">
            <h3>Finding 2: Assembly Code & Data Tables</h3>
            <p><span class="impact-med">Impact: MEDIUM</span></p>
            <p><strong>Description:</strong> Assembly language tables containing indices like <code>(ix)</code> or lists `(i)` are detected as labels.</p>
            <img src="data:image/png;base64,{img2}" class="evidence-img">
            <div class="caption">Verification: The table content (ix) is misidentified, causing a reset sequence.</div>
        </div>

        <div class="finding">
            <h3>Finding 3: Page Break Context Loss</h3>
            <p><span class="impact-med">Impact: LOW</span> (Structural)</p>
            <p><strong>Description:</strong> When a list spans a page, the parent context is sometimes lost, treating the continuation as a new sequence start.</p>
            <img src="data:image/png;base64,{img3}" class="evidence-img">
            <div class="caption">Verification: Valid sequence interrupted by page footer.</div>
        </div>

        <h2>3. Root Cause Analysis</h2>
        <ul>
            <li><strong>No Horizontal Filtering:</strong> The detector accepts matches at x > 600px (instructions/margins).</li>
            <li><strong>Context-Blind Regex:</strong> <code>(i)</code> matches inside sentences if not filtered by "Start of Line" logic.</li>
        </ul>

        <h2>4. Recommendations</h2>
        <p>Implement strict filtering in <code>detectors.py</code>:</p>
        <ol>
            <li><strong>Horizontal Threshold:</strong> Reject labels with x > 0.4 * page_width.</li>
            <li><strong>Line Start Validation:</strong> Reject labels that are not the first alphanumeric content on a line.</li>
        </ol>
    </body>
    </html>
    """
    
    with open(OUTPUT_HTML, "w") as f:
        f.write(html_content)
    
    print(f"Report generated at {OUTPUT_HTML}")

if __name__ == "__main__":
    main()
