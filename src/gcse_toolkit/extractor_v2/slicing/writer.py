"""
Module: extractor_v2.slicing.writer

Purpose:
    Writes extraction results to disk in the V2 CompositeOnly format.
    Output consists of composite.png, regions.json, and metadata.json per question.

Key Functions:
    - write_question(): Write complete question to disk
    - write_regions_json(): Write regions.json file
    - write_metadata_json(): Write metadata.json file

Dependencies:
    - PIL.Image: Image saving
    - gcse_toolkit.core.schemas.validator: Schema validation

Used By:
    - extractor_v2.pipeline: Final output step
"""

from __future__ import annotations

import json
import tempfile
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from gcse_toolkit.core.models import Part, SliceBounds
from gcse_toolkit.core.models.parts import PartKind
from gcse_toolkit.core.schemas.validator import validate_regions, QUESTION_SCHEMA_VERSION

logger = logging.getLogger(__name__)


def write_question(
    question_id: str,
    composite: Image.Image,
    part_tree: Part,
    bounds: Dict[str, SliceBounds],
    output_dir: Path,
    *,
    exam_code: str = "",
    year: int = 0,
    paper: int = 0,
    variant: int = 1,
    content_right: Optional[int] = None,
    numeral_bbox: Optional[Tuple[int, int, int, int]] = None,
    root_text: str = "",
    child_text: Optional[Dict[str, str]] = None,
    mark_bboxes: Optional[List[Tuple[int, int, int, int]]] = None,
    markscheme_path: Optional[str] = None,
    horizontal_offset: int = 0,  # Phase 6.10: For render-time alignment
    validate: bool = True,
) -> Path:
    """
    Write question to disk in CompositeOnly format.
    
    Creates:
        {output_dir}/
        ├── composite.png    # Full question image
        ├── regions.json     # Part bounds and metadata
        └── metadata.json    # Question-level metadata
    
    All writes are atomic (write to temp then rename) to prevent
    partial files on failure.
    
    Args:
        question_id: Unique question identifier.
        composite: Composite image to save.
        part_tree: Root Part with complete tree structure.
        bounds: Dict mapping part labels to SliceBounds.
        output_dir: Directory to write files to.
        exam_code: Exam code like "0478".
        year: Exam year like 2024.
        paper: Paper number.
        variant: Variant number.
        content_right: Rightmost x-coordinate of content for centering.
        numeral_bbox: Question number bounding box.
        root_text: Root question text for keyword search.
        child_text: Part-specific text for keyword search.
        mark_bboxes: List of mark box bounding boxes.
        markscheme_path: Relative path to markscheme image (if extracted).
        validate: Whether to validate regions.json against schema.
        
    Returns:
        Path to created question directory.
        
    Raises:
        ValidationError: If validate=True and regions data is invalid.
        
    Example:
        >>> write_question("s21_qp_12_q1", composite, tree, bounds, output_path)
        PosixPath('.../s21_qp_12_q1')
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build part kind and marks mappings for regions.json
    part_kinds = _build_part_kind_map(part_tree)
    part_marks = _build_part_marks_map(part_tree)
    part_label_bboxes = _build_part_label_bbox_map(part_tree)
    part_validity = _build_part_validity_map(part_tree)  # 1:1 parity with diagnostics
    
    # Build regions data with kind, marks, bbox, and validity fields included
    regions_data = _build_regions_dict(
        question_id, bounds, composite.size, part_kinds, part_marks, part_label_bboxes,
        part_validity=part_validity,
        numeral_bbox=numeral_bbox,
        mark_bboxes=mark_bboxes,
        horizontal_offset=horizontal_offset,
    )
    
    # Validate against schema
    if validate:
        validate_regions(regions_data)
    
    # Write composite image atomically
    composite_path = output_dir / "composite.png"
    _atomic_write_image(composite, composite_path)
    
    # Write regions.json atomically
    regions_path = output_dir / "regions.json"
    _atomic_write_json(regions_data, regions_path)
    
    # Write metadata.json atomically (self-contained directory)
    metadata_path = output_dir / "metadata.json"
    write_metadata_json(
        question_id=question_id,
        part_tree=part_tree,
        output_path=metadata_path,
        exam_code=exam_code,
        year=year,
        paper=paper,
        variant=variant,
        content_right=content_right,
        numeral_bbox=numeral_bbox,
        root_text=root_text,
        child_text=child_text,
        mark_bboxes=mark_bboxes,
        markscheme_path=markscheme_path,
        horizontal_offset=horizontal_offset,
    )
    
    logger.debug(f"Wrote question {question_id} to {output_dir}")
    return output_dir


def write_question_async(
    question_id: str,
    composite: Image.Image,
    part_tree: Part,
    bounds: Dict[str, SliceBounds],
    output_dir: Path,
    write_queue: "WriteQueue",  # type: ignore
    *,
    exam_code: str = "",
    year: int = 0,
    paper: int = 0,
    variant: int = 1,
    content_right: Optional[int] = None,
    numeral_bbox: Optional[Tuple[int, int, int, int]] = None,
    root_text: str = "",
    child_text: Optional[Dict[str, str]] = None,
    mark_bboxes: Optional[List[Tuple[int, int, int, int]]] = None,
    markscheme_path: Optional[str] = None,
    horizontal_offset: int = 0,
    validate: bool = True,
) -> Path:
    """
    Write question to disk with async image writing.
    
    OPTIMIZATION C: Uses WriteQueue to queue image writes in background
    threads, allowing processing to continue to the next question while
    files are written to disk.
    
    Same as write_question() but image writing is non-blocking.
    JSON writes remain synchronous (small files, fast).
    
    Args:
        question_id: Unique question identifier.
        composite: Composite image to save.
        part_tree: Root Part with complete tree structure.
        bounds: Dict mapping part labels to SliceBounds.
        output_dir: Directory to write files to.
        write_queue: WriteQueue instance for async writes.
        ... (other args same as write_question)
        
    Returns:
        Path to created question directory.
        
    Example:
        >>> with WriteQueue() as queue:
        ...     for q in questions:
        ...         write_question_async(..., write_queue=queue)
        ...     # queue.wait_all() called on exit
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build part kind and marks mappings for regions.json
    part_kinds = _build_part_kind_map(part_tree)
    part_marks = _build_part_marks_map(part_tree)
    part_label_bboxes = _build_part_label_bbox_map(part_tree)
    part_validity = _build_part_validity_map(part_tree)  # 1:1 parity with diagnostics
    
    # Build regions data with validity
    regions_data = _build_regions_dict(
        question_id, bounds, composite.size, part_kinds, part_marks, part_label_bboxes,
        part_validity=part_validity,
        numeral_bbox=numeral_bbox,
        mark_bboxes=mark_bboxes,
        horizontal_offset=horizontal_offset,
    )
    
    # Validate against schema
    if validate:
        validate_regions(regions_data)
    
    # Queue async image write (non-blocking)
    composite_path = output_dir / "composite.png"
    write_queue.queue_image_write(composite, composite_path)
    
    # Write regions.json synchronously (small file, fast)
    regions_path = output_dir / "regions.json"
    _atomic_write_json(regions_data, regions_path)
    
    # Write metadata.json synchronously
    metadata_path = output_dir / "metadata.json"
    write_metadata_json(
        question_id=question_id,
        part_tree=part_tree,
        output_path=metadata_path,
        exam_code=exam_code,
        year=year,
        paper=paper,
        variant=variant,
        content_right=content_right,
        numeral_bbox=numeral_bbox,
        root_text=root_text,
        child_text=child_text,
        mark_bboxes=mark_bboxes,
        markscheme_path=markscheme_path,
        horizontal_offset=horizontal_offset,
    )
    
    logger.debug(f"Queued write for {question_id} to {output_dir}")
    return output_dir


def write_regions_json(
    question_id: str,
    bounds: Dict[str, SliceBounds],
    composite_size: tuple,
    output_path: Path,
    *,
    part_kinds: Optional[Dict[str, str]] = None,
    validate: bool = True,
) -> None:
    """
    Write regions.json file.
    
    Args:
        question_id: Question identifier.
        bounds: Dict mapping part labels to SliceBounds.
        composite_size: (width, height) of composite image.
        output_path: Path to write regions.json.
        part_kinds: Optional dict mapping labels to kind ("question", "letter", "roman").
        validate: Whether to validate against schema.
    """
    regions_data = _build_regions_dict(question_id, bounds, composite_size, part_kinds)
    
    if validate:
        validate_regions(regions_data)
    
    _atomic_write_json(regions_data, output_path)


def write_metadata_json(
    question_id: str,
    part_tree: Part,
    output_path: Path,
    *,
    exam_code: str = "",
    year: int = 0,
    paper: int = 0,
    variant: int = 1,
    content_right: Optional[int] = None,
    numeral_bbox: Optional[Tuple[int, int, int, int]] = None,
    root_text: str = "",
    child_text: Optional[Dict[str, str]] = None,
    mark_bboxes: Optional[List[Tuple[int, int, int, int]]] = None,
    markscheme_path: Optional[str] = None,
    horizontal_offset: int = 0,
) -> None:
    """
    Write metadata.json with question-level info.
    
    Args:
        question_id: Question identifier.
        part_tree: Root Part with tree structure.
        output_path: Path to write metadata.json.
        exam_code: Exam code.
        year: Exam year.
        paper: Paper number.
        variant: Variant number.
        content_right: Rightmost x-coordinate of content.
        numeral_bbox: Question number bbox.
        root_text: Root text.
        child_text: Child text.
        mark_bboxes: Mark box bboxes.
        markscheme_path: Relative path to ms image.
        horizontal_offset: Alignment offset.
    """
    metadata = _build_metadata_dict(
        question_id=question_id,
        part_tree=part_tree,
        exam_code=exam_code,
        year=year,
        paper=paper,
        variant=variant,
        content_right=content_right,
        numeral_bbox=numeral_bbox,
        root_text=root_text,
        child_text=child_text,
        mark_bboxes=mark_bboxes,
        markscheme_path=markscheme_path,
        horizontal_offset=horizontal_offset,
    )
    _atomic_write_json(metadata, output_path)


def _build_part_kind_map(part: Part) -> Dict[str, str]:
    """Build mapping of part labels to their kinds."""
    result = {part.label: part.kind.value}
    for child in part.children:
        result.update(_build_part_kind_map(child))
    return result


def _build_part_marks_map(part: Part) -> Dict[str, int]:
    """
    Build mapping of LEAF part labels to their marks.
    
    Only includes leaf parts (those with no children).
    Parent marks are always calculated from children, never stored.
    This ensures single source of truth for marks.
    """
    result = {}
    if not part.children:
        # Leaf part - store its marks
        result[part.label] = part.marks.value
    else:
        # Non-leaf - recurse to children only
        for child in part.children:
            result.update(_build_part_marks_map(child))
    return result


def _build_part_label_bbox_map(part: Part) -> Dict[str, Dict[str, int]]:
    """Build mapping of part labels to their label bboxes."""
    result = {}
    if part.label_bbox:
        result[part.label] = part.label_bbox.to_dict()
    for child in part.children:
        result.update(_build_part_label_bbox_map(child))
    return result


def _build_part_validity_map(part: Part) -> Dict[str, Dict[str, Any]]:
    """Build mapping of part labels to their validation status.
    
    Only includes parts where is_valid=False (to keep regions.json lean).
    
    Returns:
        Dict mapping label -> {"is_valid": False, "validation_issues": [...]}
    """
    result = {}
    if not part.is_valid:
        result[part.label] = {
            "is_valid": False,
            "validation_issues": list(part.validation_issues) if part.validation_issues else [],
        }
    for child in part.children:
        result.update(_build_part_validity_map(child))
    return result


def _build_regions_dict(
    question_id: str,
    bounds: Dict[str, SliceBounds],
    composite_size: tuple,
    part_kinds: Optional[Dict[str, str]] = None,
    part_marks: Optional[Dict[str, int]] = None,
    part_label_bboxes: Optional[Dict[str, Dict[str, int]]] = None,
    part_validity: Optional[Dict[str, Dict[str, Any]]] = None,
    numeral_bbox: Optional[Tuple[int, int, int, int]] = None,
    mark_bboxes: Optional[List[Tuple[int, int, int, int]]] = None,
    horizontal_offset: int = 0,
) -> Dict[str, Any]:
    """Build regions.json data structure."""
    regions = {}
    for label, slice_bounds in bounds.items():
        region = {
            "bounds": {
                "top": slice_bounds.top,
                "bottom": slice_bounds.bottom,
                "left": slice_bounds.left if slice_bounds.left else 0,
                "right": slice_bounds.right if slice_bounds.right else composite_size[0],
            }
        }
        # Add child_is_inline flag for inline parts (e.g., "(a)" in "8 (a)")
        # Builder uses this to skip rendering separate slices for inline children
        if slice_bounds.child_is_inline:
            region["child_is_inline"] = True
        # Add kind if available
        if part_kinds and label in part_kinds:
            region["kind"] = part_kinds[label]
        # Add marks if available
        if part_marks and label in part_marks:
            region["marks"] = part_marks[label]
        # Add label_bbox if available
        if part_label_bboxes and label in part_label_bboxes:
            region["label_bbox"] = part_label_bboxes[label]
        # Add validity data if part is invalid (1:1 parity with diagnostics)
        if part_validity and label in part_validity:
            region["is_valid"] = part_validity[label]["is_valid"]
            region["validation_issues"] = part_validity[label]["validation_issues"]
        regions[label] = region
    
    result = {
        "schema_version": 3,  # Bumped for validation fields
        "question_id": question_id,
        "composite_size": {
            "width": composite_size[0],
            "height": composite_size[1],
        },
        "horizontal_offset": horizontal_offset,
        "regions": regions,
    }
    
    # Add bbox fields (moved from questions.jsonl)
    if numeral_bbox is not None:
        result["numeral_bbox"] = list(numeral_bbox)
    if mark_bboxes is not None:
        result["mark_bboxes"] = [list(bbox) for bbox in mark_bboxes]
    
    return result


def _build_metadata_dict(
    question_id: str,
    part_tree: Part,
    exam_code: str,
    year: int,
    paper: int,
    variant: int,
    content_right: Optional[int] = None,
    numeral_bbox: Optional[Tuple[int, int, int, int]] = None,
    root_text: str = "",
    child_text: Optional[Dict[str, str]] = None,
    mark_bboxes: Optional[List[Tuple[int, int, int, int]]] = None,
    markscheme_path: Optional[str] = None,
    horizontal_offset: int = 0,  # Phase 6.10: For render-time alignment
) -> Dict[str, Any]:
    """Build metadata.json data structure."""
    metadata = {
        "schema_version": QUESTION_SCHEMA_VERSION,
        "question_id": question_id,
        "exam_code": exam_code,
        "year": year,
        "paper": paper,
        "variant": variant,
        "question_number": int(part_tree.label) if part_tree.label.isdigit() else 0,
        "total_marks": part_tree.total_marks,
        "part_count": part_tree.leaf_count,
        "topic": part_tree.topic or "00. Unknown",
    }
    # Add content_right boundary (rightmost mark box x-coordinate) for margin cropping
    if content_right is not None:
        metadata["content_right"] = content_right
    # Add numeral_bbox for question number overlay positioning
    if numeral_bbox is not None:
        metadata["numeral_bbox"] = list(numeral_bbox)
    # Add text fields for keyword search
    metadata["root_text"] = root_text
    metadata["child_text"] = child_text or {}
    # Add mark box bounding boxes for UI highlighting
    metadata["mark_bboxes"] = [list(bbox) for bbox in (mark_bboxes or [])]
    # Add markscheme path if extracted
    if markscheme_path is not None:
        metadata["markscheme_path"] = markscheme_path
    # Phase 6.10: Add horizontal offset for render-time alignment
    metadata["horizontal_offset"] = horizontal_offset
    return metadata


def _atomic_write_image(image: Image.Image, path: Path) -> None:
    """Write image atomically using temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=".png",
        dir=path.parent,
        delete=False,
    ) as f:
        # OPTIMIZATION: Use compress_level=1 instead of optimize=True
        # compress_level 1 is much faster with minimal size increase
        image.save(f, format="PNG", compress_level=1)
        temp_path = Path(f.name)
    
    # Use replace() instead of rename() for Windows compatibility
    temp_path.replace(path)


def _atomic_write_json(data: Dict[str, Any], path: Path) -> None:
    """Write JSON atomically using temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        dir=path.parent,
        delete=False,
        encoding="utf-8",
    ) as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path = Path(f.name)
    
    # Use replace() instead of rename() for Windows compatibility
    # replace() will overwrite existing files on all platforms
    temp_path.replace(path)
