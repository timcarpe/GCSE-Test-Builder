"""
Module: builder_v2.output.zip_writer

Purpose:
    Export selected questions as individual cropped images in a ZIP archive.
    Organizes images by question folder with full leaf ID filenames.

Key Functions:
    - write_questions_zip(): Main entry point

Dependencies:
    - zipfile (std)
    - PIL/Pillow
    - builder_v2.images.provider: CompositeImageProvider
    - core.models.selection: SelectionResult

Used By:
    - builder_v2.controller: Build pipeline (optional output)
    - GUI: User-initiated export
"""

from __future__ import annotations

import logging
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image

from gcse_toolkit.core.models.selection import SelectionResult
from gcse_toolkit.builder_v2.images.provider import (
    CompositeImageProvider,
    create_provider_for_question,
)

logger = logging.getLogger(__name__)


def write_questions_zip(
    result: SelectionResult,
    output_path: Path,
    *,
    include_readme: bool = True,
) -> Path:
    """
    Export selected questions as cropped images in a ZIP archive.
    
    Creates a ZIP file with structure:
        questions.zip
        ├── README.txt           # Summary (optional)
        ├── 1/                   # First selected question
        │   ├── 1.png            # Root question slice
        │   ├── 1 (a).png        # Part (a)
        │   └── 1 (a) (i).png    # Part (a)(i)
        ├── 2/                   # Second selected question
        │   └── 2.png            # Root (if single-part question)
        └── ...
    
    Args:
        result: SelectionResult with selected plans
        output_path: Path for .zip file (will append .zip if missing)
        include_readme: Whether to include README.txt
        
    Returns:
        Path to created ZIP file
        
    Raises:
        IOError: If output path is not writable
    """
    if not output_path.suffix == ".zip":
        output_path = output_path.with_suffix(".zip")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Creating ZIP export at {output_path}")
    
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write README
        if include_readme:
            readme = _generate_readme(result)
            zf.writestr("README.txt", readme)
        
        # Process each plan
        for i, plan in enumerate(result.plans, start=1):
            question_dir = str(i)
            _export_plan_slices(zf, plan, question_dir)
    
    return output_path


def _export_plan_slices(
    zf: zipfile.ZipFile,
    plan: "SelectionPlan",
    question_dir: str,
) -> None:
    """Export all included slices for a selection plan."""
    question = plan.question
    
    # Use ImageProvider to get cropped slices
    # We use a context manager to ensure the composite is closed
    with create_provider_for_question(
        question.composite_path.parent, 
        {p.label: p.bounds for p in question.all_parts}
    ) as provider:
        # Always include root if it exists
        if question.question_node.label in provider.available_labels:
            _write_slice(zf, provider, question.question_node.label, question_dir)
        
        # Include all selected parts (leaves)
        # We also need to include branch parts if we want "Option B" from spec
        # User request said "full leaf id... placed in the same folder"
        # I'll include all labels in plan.included_labels
        for label in plan.included_parts:
            # Skip root if already written
            if label == question.question_node.label:
                continue
            _write_slice(zf, provider, label, question_dir)


def _write_slice(
    zf: zipfile.ZipFile,
    provider: CompositeImageProvider,
    label: str,
    question_dir: str,
) -> None:
    """Crop and write a single slice to the ZIP."""
    try:
        image = provider.get_slice(label)
        
        # Convert to PNG bytes
        img_bytes = BytesIO()
        image.save(img_bytes, format="PNG")
        
        # Format filename
        filename = _sanitize_filename(label) + ".png"
        arcname = f"{question_dir}/{filename}"
        
        zf.writestr(arcname, img_bytes.getvalue())
    except Exception as e:
        logger.warning(f"Failed to export slice '{label}': {e}")


def _sanitize_filename(label: str) -> str:
    """
    Convert Part label to filesystem-safe filename.
    
    Converts:
        "1"       -> "1"
        "1(a)"    -> "1(a)"
        "1(a)(ii)" -> "1(a)(ii)"
    """
    # Simply return label for now as user requested no spaces
    return label.strip()


def _generate_readme(result: SelectionResult) -> str:
    """Generate README.txt content."""
    lines = [
        "GCSE Test Builder - Exported Question Slices",
        "=" * 50,
        "",
        f"Total Marks: {result.total_marks}",
        f"Target: {result.target_marks} (±{result.tolerance})",
        f"Questions: {len(result.plans)}",
        "",
        "=" * 50,
        "Question List:",
        ""
    ]
    
    for i, plan in enumerate(result.plans, start=1):
        q = plan.question
        lines.append(f"{i}. {q.id} ({plan.marks} marks)")
        lines.append(f"   Topic: {q.topic}")
        # Show which parts were exported
        parts = sorted(list(plan.included_parts))
        lines.append(f"   Parts: {', '.join(parts)}")
        lines.append("")
    
    lines.extend([
        "=" * 50,
        "Usage:",
        "- Import images into Word, PowerPoint, or LaTeX.",
        "- Each folder contains slices for one question.",
        "- Images are named by their full label (e.g., '1(a)(i).png').",
        ""
    ])
    
    return "\n".join(lines)
