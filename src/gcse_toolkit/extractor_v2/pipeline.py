"""
Module: extractor_v2.pipeline

Purpose:
    Main pipeline orchestrator for PDF question extraction. Coordinates
    detection, structuring, and output to produce CompositeOnly format
    extraction results.

Key Functions:
    - extract_question_paper(): Main entry point for extraction

Key Classes:
    - ExtractionResult: Container for extraction output

Dependencies:
    - fitz (PyMuPDF): PDF access
    - gcse_toolkit.extractor_v2.detection: Detection modules
    - gcse_toolkit.extractor_v2.structuring: Tree building
    - gcse_toolkit.extractor_v2.slicing: Composite and output

Used By:
    - gcse_toolkit.gui.tabs.extract_tab: GUI extraction
    - gcse_toolkit.cli: Command-line extraction
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz

from .config import ExtractionConfig
from gcse_toolkit.core.models.parts import Part
from .detection.numerals import detect_question_numerals, QuestionNumeral
from .detection.parts import detect_part_labels, detect_part_labels_from_data
from .detection.marks import detect_mark_boxes, detect_mark_boxes_from_data
from .utils.detectors import extract_text_data  # OPTIMIZATION #3
from .structuring.tree_builder import build_part_tree
from .slicing.compositor import (
    create_composite, 
    render_question_composite,
    QuestionBounds,
    PageSegment,
)
from .slicing.bounds_calculator import calculate_all_bounds, bounds_from_detections
from .slicing.writer import write_question, write_question_async
from .write_queue import WriteQueue  # OPTIMIZATION C: Async file writing
from .utils.text import extract_text_spans, text_for_bounded_region
from .classification import classify_topic
from .timing import TimingLog, timed_phase
from .diagnostics import DiagnosticsCollector


logger = logging.getLogger(__name__)


def _collect_validation_outcome(part_tree) -> Dict[str, str]:
    """Collect validation status for all parts in a tree.
    
    Args:
        part_tree: Root Part object
        
    Returns:
        Dict mapping part labels to validation status strings
    """
    outcome = {}
    
    def _collect(part):
        if part.is_valid:
            outcome[part.label] = "VALID"
        else:
            reason = part.validation_issues[0] if part.validation_issues else "Unknown"
            outcome[part.label] = f"INVALID: {reason}"
        for child in part.children:
            _collect(child)
    
    _collect(part_tree)
    return outcome


@dataclass
class ExtractionResult:
    """
    Result of extracting a PDF.
    
    Contains the list of questions extracted, any warnings
    encountered, and the output directory.
    
    Attributes:
        question_count: Number of questions extracted.
        question_ids: List of extracted question IDs.
        warnings: List of warning messages.
        output_dir: Directory where results were written.
    """
    question_count: int
    question_ids: List[str]
    warnings: List[str]
    output_dir: Path


def extract_question_paper(
    pdf_path: Path,
    output_dir: Path,
    exam_code: str,
    *,
    config: Optional[ExtractionConfig] = None,
    markscheme_search_dirs: Optional[List[Path]] = None,
    diagnostics_collector: Optional[DiagnosticsCollector] = None,
) -> ExtractionResult:
    """
    Extract questions from a question paper PDF.
    
    Pipeline:
    1. Detect question numerals across all pages
    2. Find matching markscheme PDF (if extract_markschemes enabled)
    3. For each question:
       a. Render page segments to composite image
       b. Detect part labels and marks
       c. Build Part tree
       d. Calculate slice bounds
       e. Extract markscheme pages (if MS PDF found)
       f. Write to disk
    
    Args:
        pdf_path: Path to PDF file.
        output_dir: Directory for output (created if needed).
        exam_code: Exam code like "0478".
        config: Optional extraction configuration.
        markscheme_search_dirs: Optional directories to search for MS PDF.
        
    Returns:
        ExtractionResult with question IDs and warnings.
        
    Raises:
        FileNotFoundError: If pdf_path doesn't exist.
        ValueError: If PDF has no pages or can't be opened.
        
    Example:
        >>> result = extract_question_paper(
        ...     Path("0478_s24_qp_12.pdf"),
        ...     Path("output"),
        ...     "0478"
        ... )
        >>> print(f"Extracted {result.question_count} questions")
        Extracted 8 questions
    """
    config = config or ExtractionConfig()
    warnings: List[str] = []
    question_ids: List[str] = []
    metadata_records: List[Dict[str, Any]] = []
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find matching markscheme PDF (if enabled)
    ms_pdf_path = None
    ms_page_mapping = {}
    if config.extract_markschemes:
        from .markscheme import find_markscheme_pdf, map_ms_pages_to_questions
        ms_pdf_path = find_markscheme_pdf(pdf_path, markscheme_search_dirs)
        if ms_pdf_path:
            logger.info(f"Found markscheme PDF: {ms_pdf_path.name}")
        else:
            logger.debug(f"No markscheme PDF found for {pdf_path.name}")
    
    # Initialize timing log and diagnostics collector
    timing_log = TimingLog()
    # Use passed-in collector or create one if diagnostics enabled
    owns_collector = diagnostics_collector is None and config.run_diagnostics
    if owns_collector:
        diagnostics_collector = DiagnosticsCollector()
    
    with fitz.open(pdf_path) as doc:
        # Step 1: Detect question numerals
        with timed_phase(timing_log, "numeral_detection"):
            numerals = detect_question_numerals(
                doc,
                header_ratio=config.header_ratio,
                footer_ratio=config.footer_ratio,
            )
        logger.info(f"Detected {len(numerals)} questions in {pdf_path.name}")
        
        if not numerals:
            warnings.append("No questions detected in PDF")
            return ExtractionResult(
                question_count=0,
                question_ids=[],
                warnings=warnings,
                output_dir=output_dir,
            )
        
        # Step 2: Map MS pages to questions (if MS PDF found)
        if ms_pdf_path:
            with timed_phase(timing_log, "ms_page_mapping"):
                from .markscheme import map_ms_pages_to_questions
                question_numbers = {num.number for num in numerals}
                ms_page_mapping = map_ms_pages_to_questions(ms_pdf_path, question_numbers)
            logger.info(f"Mapped MS pages: {len(ms_page_mapping)} questions have markschemes")
        
        # Step 3: Extract each question with async file writing
        # OPTIMIZATION C: WriteQueue allows processing to continue while files write
        with WriteQueue(max_workers=4) as write_queue:
            for i, numeral in enumerate(numerals):
                next_numeral = numerals[i + 1] if i + 1 < len(numerals) else None
                
                try:
                    question_id, metadata_record = _extract_single_question(
                        doc=doc,
                        numeral=numeral,
                        next_numeral=next_numeral,
                        exam_code=exam_code,
                        pdf_name=pdf_path.stem,
                        output_dir=output_dir,
                        config=config,
                        ms_pdf_path=ms_pdf_path,
                        ms_page_mapping=ms_page_mapping,
                        timing_log=timing_log,
                        write_queue=write_queue,  # OPTIMIZATION C: Pass queue for async writes
                        diagnostics_collector=diagnostics_collector,
                    )
                    question_ids.append(question_id)
                    metadata_records.append(metadata_record)
                    logger.debug(f"Extracted question {numeral.number}")
                except Exception as e:
                    msg = (
                        f"Failed to extract question {numeral.number}: {e} "
                        f"[PDF: {pdf_path.name}, Exam: {exam_code}, Page: {numeral.page}]"
                    )
                    logger.warning(
                        msg,
                        extra={
                            "exam_code": exam_code,
                            "pdf_name": pdf_path.name,
                            "question_number": numeral.number,
                            "page_number": numeral.page,
                            "error": str(e),
                        }
                    )
                    warnings.append(msg)
                    
                    # Capture failed extraction in diagnostics (1:1 parity)
                    if diagnostics_collector:
                        diagnostics_collector.add_invalid_question(
                            pdf_name=pdf_path.stem,
                            exam_code=exam_code,
                            question_number=numeral.number,
                            reason=str(e),
                        )
    
    # Write centralized metadata
    _write_centralized_metadata(output_dir, exam_code, metadata_records)
    
    # Write diagnostics report if we own the collector and have issues
    if owns_collector and diagnostics_collector and diagnostics_collector.issue_count > 0:
        diagnostics_report = diagnostics_collector.generate_report()
        diagnostics_path = output_dir / exam_code / "_metadata" / "detection_diagnostics.json"
        diagnostics_report.save(diagnostics_path)
        logger.info(f"Detection diagnostics: {diagnostics_collector.issue_count} issues found")
    
    # Save timing log to file
    timing_path = output_dir / exam_code / "_metadata" / "timing.json"
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    timing_log.save(timing_path)
    
    # Log timing summary
    logger.info(timing_log.summary())
    
    # One-line summary per PDF (summary format)
    logger.info(
        f"Completed extraction for {exam_code} ({pdf_path.stem}): {len(question_ids)} questions",
        extra={"pdf_name": pdf_path.name, "exam_code": exam_code, "question_count": len(question_ids)}
    )
    
    return ExtractionResult(
        question_count=len(question_ids),
        question_ids=question_ids,
        warnings=warnings,
        output_dir=output_dir,
    )


def _extract_single_question(
    doc: fitz.Document,
    numeral: QuestionNumeral,
    next_numeral: Optional[QuestionNumeral],
    exam_code: str,
    pdf_name: str,
    output_dir: Path,
    config: ExtractionConfig,
    ms_pdf_path: Optional[Path] = None,
    ms_page_mapping: Optional[dict] = None,
    timing_log: Optional[TimingLog] = None,
    write_queue: Optional[WriteQueue] = None,  # OPTIMIZATION C: Async file writing
    diagnostics_collector: Optional[DiagnosticsCollector] = None,
) -> str:
    """
    Extract a single question from the document.
    
    Args:
        ms_pdf_path: Optional path to markscheme PDF
        ms_page_mapping: Dict mapping question_number -> list of MS page indices
        timing_log: Optional TimingLog for performance tracking
    
    Returns:
        Tuple of (question_id, metadata_record) where metadata_record contains
        all question metadata for centralized questions.jsonl file.
    """
    dpi = config.dpi
    question_id = f"{pdf_name}_q{numeral.number}"  # Pre-compute for timing
    
    # Determine question bounds
    # End position: next question's Y or last mark box or page end
    start_page = numeral.page
    start_y = numeral.y_position
    
    if next_numeral:
        end_page = next_numeral.page
        end_y = next_numeral.y_position
    else:
        end_page = doc.page_count - 1
        end_y = doc[end_page].rect.height
    
    bounds = QuestionBounds(
        start_page=start_page,
        start_y=start_y,
        end_page=end_page,
        end_y=end_y,
    )
    
    # Render composite (timed)
    if timing_log:
        with timed_phase(timing_log, "composite_creation", question_id):
            composite, segments = render_question_composite(doc, bounds, dpi=dpi)
    else:
        composite, segments = render_question_composite(doc, bounds, dpi=dpi)
    
    # Collect detections from all segments (timed)
    all_letters = []
    all_romans = []
    all_marks = []
    
    if timing_log:
        with timed_phase(timing_log, "part_detection", question_id):
            for segment in segments:
                page = doc[segment.page_index]
                
                # OPTIMIZATION #3: Extract text ONCE per segment, pass to both detectors
                text_data = extract_text_data(page, segment.clip)
                
                letters, romans = detect_part_labels_from_data(
                    text_data,
                    segment.clip,
                    dpi,
                    segment.y_offset,
                    segment.trim_offset,
                )
                all_letters.extend(letters)
                all_romans.extend(romans)
                
                marks = detect_mark_boxes_from_data(
                    text_data,
                    segment.clip,
                    dpi,
                    segment.y_offset,
                    segment.trim_offset,
                )
                all_marks.extend(marks)
    else:
        for segment in segments:
            page = doc[segment.page_index]
            
            # OPTIMIZATION #3: Extract text ONCE per segment, pass to both detectors
            text_data = extract_text_data(page, segment.clip)
            
            letters, romans = detect_part_labels_from_data(
                text_data,
                segment.clip,
                dpi,
                segment.y_offset,
                segment.trim_offset,
            )
            all_letters.extend(letters)
            all_romans.extend(romans)
            
            marks = detect_mark_boxes_from_data(
                text_data,
                segment.clip,
                dpi,
                segment.y_offset,
                segment.trim_offset,
            )
            all_marks.extend(marks)
    
    # Enhanced logging for detection results
    logger.debug(
        f"Q{numeral.number} detections: "
        f"letters=[{', '.join(l.label for l in all_letters)}], "
        f"romans=[{', '.join(r.label for r in all_romans)}], "
        f"marks={len(all_marks)}",
        extra={
            "exam_code": exam_code,
            "pdf_name": pdf_name,
            "question_number": numeral.number,
            "letter_count": len(all_letters),
            "roman_count": len(all_romans),
            "mark_count": len(all_marks),
        }
    )
    
    # Validation: warn if romans detected without parent letters
    if all_romans and len(all_letters) <= len([r for r in all_romans if '(' in r.label]):
        # Rough heuristic: if we have as many or more romans than letters, might be missing letters
        logger.warning(
            f"Q{numeral.number}: Detected {len(all_romans)} romans but only {len(all_letters)} letters - "
            f"detection may have missed parent labels (e.g., missing '(b)' when '(i)' and '(ii)' exist)",
            extra={
                "exam_code": exam_code,
                "pdf_name": pdf_name,
                "question_number": numeral.number,
                "letters_detected": [l.label for l in all_letters],
                "romans_detected": [r.label for r in all_romans],
            }
        )
        # NOTE: Diagnostic recording moved to after part_tree is built to include validation_outcome
    
    # Flag for orphaned romans to record later with validation_outcome
    has_orphaned_romans = all_romans and len(all_letters) <= len([r for r in all_romans if '(' in r.label])
    orphaned_romans_context = None
    if has_orphaned_romans:
        first_roman = all_romans[0] if all_romans else None
        last_valid = all_letters[-1] if all_letters else None
        orphaned_romans_context = {
            "y_start": 0,
            "y_end": first_roman.y_position if first_roman else composite.height,
            "prev_info": f"({last_valid.label}) @ y={last_valid.y_position}" if last_valid else "",
            "next_info": f"({first_roman.label}) @ y={first_roman.y_position}" if first_roman else "",
        }

    
    # Create text extractor for diagnostics
    # This extracts PDF text for Y-spans in composite pixel coordinates
    def extract_pdf_text(y_start: int, y_end: int) -> str:
        """Extract PDF text from a Y-span in composite pixel coordinates."""
        print(f"[DIAG-PRINT] extract_pdf_text called: y_start={y_start}, y_end={y_end}, segments={len(segments)}")
        text_parts = []
        scale = dpi / 72.0  # Pixels per PDF point
        matched_segments = 0
        
        logger.info(f"[DIAG] extract_pdf_text called: y_start={y_start}, y_end={y_end}, segments={len(segments)}")
        logger.debug(f"Number of segments: {len(segments)}")
        
        for idx, segment in enumerate(segments):
            # Segment's Y range in composite pixel coordinates
            seg_top = segment.y_offset
            seg_height_px = segment.clip.height * scale
            seg_bottom = seg_top + seg_height_px
            
            logger.debug(f"  Segment {idx}: offset_y={seg_top}, height_px={seg_height_px:.1f}, seg_bottom={seg_bottom:.1f}, page={segment.page_index}")
            
            # Check if segment overlaps with requested Y range
            if seg_bottom < y_start or seg_top > y_end:
                logger.debug(f"    -> No overlap with y_range [{y_start}, {y_end}]")
                continue  # No overlap
            
            matched_segments += 1
            
            # Clamp Y range to segment bounds
            local_y_start = max(y_start, seg_top)
            local_y_end = min(y_end, seg_bottom)
            
            # Convert composite Y to PDF Y
            # Formula: composite_y = segment.y_offset + (pdf_y - segment.clip.y0) * scale
            # So: pdf_y = (composite_y - segment.y_offset) / scale + segment.clip.y0
            pdf_y_start = (local_y_start - segment.y_offset) / scale + segment.clip.y0
            pdf_y_end = (local_y_end - segment.y_offset) / scale + segment.clip.y0
            
            logger.debug(f"    -> Overlaps! local_y=[{local_y_start}, {local_y_end}], pdf_y=[{pdf_y_start:.1f}, {pdf_y_end:.1f}]")
            
            # Extract text from PDF region (full width)
            page = doc[segment.page_index]
            clip = fitz.Rect(segment.clip.x0, pdf_y_start, segment.clip.x1, pdf_y_end)
            logger.debug(f"    -> Clip: {clip}")
            text = page.get_text("text", clip=clip) or ""
            if text.strip():
                text_parts.append(text.strip())
                logger.debug(f"    -> Got text ({len(text.strip())} chars)")
            else:
                logger.debug(f"    -> No text found in clip")
        
        if matched_segments == 0:
            logger.debug(f"  No segments matched y_range [{y_start}, {y_end}]")
        
        result = " ".join(text_parts)
        logger.debug(f"extract_pdf_text result: {len(result)} chars")
        return result
    
    # Build Part tree (timed) - pass text_extractor directly for diagnostics
    if timing_log:
        with timed_phase(timing_log, "tree_building", question_id):
            part_tree = build_part_tree(
                question_num=numeral.number,
                letters=all_letters,
                romans=all_romans,
                marks=all_marks,
                composite_height=composite.height,
                composite_width=composite.width,
                exam_code=exam_code,
                pdf_name=pdf_name,
                diagnostics_collector=diagnostics_collector,
                text_extractor=extract_pdf_text if diagnostics_collector else None,
            )
    else:
        part_tree = build_part_tree(
            question_num=numeral.number,
            letters=all_letters,
            romans=all_romans,
            marks=all_marks,
            composite_height=composite.height,
            composite_width=composite.width,
            exam_code=exam_code,
            pdf_name=pdf_name,
            diagnostics_collector=diagnostics_collector,
            text_extractor=extract_pdf_text if diagnostics_collector else None,
        )
    
    # Record orphaned_romans diagnostic NOW with validation_outcome from part_tree
    if diagnostics_collector and orphaned_romans_context:
        validation_outcome = _collect_validation_outcome(part_tree)
        diagnostics_collector.add_orphaned_romans(
            pdf_name=pdf_name,
            exam_code=exam_code,
            question_number=numeral.number,
            letters_detected=[l.label for l in all_letters],
            romans_detected=[r.label for r in all_romans],
            y_span=(orphaned_romans_context["y_start"], orphaned_romans_context["y_end"]),
            prev_label_info=orphaned_romans_context["prev_info"],
            next_label_info=orphaned_romans_context["next_info"],
        )
        # Update the last issue with validation_outcome
        if diagnostics_collector._issues:
            diagnostics_collector._issues[-1].validation_outcome = validation_outcome
    
    # Phase 6.9: Calculate numeral_bbox in composite pixels FIRST
    # This bbox is used for both bounds calculation and metadata storage
    numeral_bbox = None
    if numeral.bbox:
        scale = dpi / 72.0  # PDF points to pixels
        first_segment = segments[0] if segments else None
        if first_segment:
            # Adjust for clip offset and convert to pixels
            x0, y0, x1, y1 = numeral.bbox
            # Convert PDF coordinates to composite image coordinates
            px0 = int((x0 - first_segment.clip.x0) * scale) - first_segment.trim_offset[0]
            py0 = int((y0 - first_segment.clip.y0) * scale) - first_segment.trim_offset[1]
            px1 = int((x1 - first_segment.clip.x0) * scale) - first_segment.trim_offset[0]
            py1 = int((y1 - first_segment.clip.y0) * scale) - first_segment.trim_offset[1]
            
            # Sanity check: numeral bbox should be compact (typically <100px wide)
            bbox_width = px1 - px0
            MAX_NUMERAL_WIDTH_PX = 100
            if bbox_width > MAX_NUMERAL_WIDTH_PX:
                logger.warning(
                    f"Q{numeral.number} has oversized numeral bbox (width={bbox_width}px > {MAX_NUMERAL_WIDTH_PX}px). "
                    f"Detection may have captured entire line instead of just question number."
                )
                if diagnostics_collector:
                    diagnostics_collector.add_layout_issue(
                        pdf_name=pdf_name,
                        exam_code=exam_code,
                        question_number=numeral.number,
                        page_index=numeral.page,
                        message=f"Oversized numeral bbox: width={bbox_width}px",
                        details={"bbox_width": bbox_width, "expected_max": MAX_NUMERAL_WIDTH_PX},
                        y_span=(py0, py1),
                    )
            
            numeral_bbox = (px0, py0, px1, py1)
    
    # Calculate bounds for regions.json (timed)
    if timing_log:
        with timed_phase(timing_log, "bounds_calculation", question_id):
            part_bounds_list = bounds_from_detections(
                question_num=numeral.number,
                letters=all_letters,
                romans=all_romans,
                composite_height=composite.height,
                marks=all_marks,
                numeral_bbox=numeral_bbox,
            )
            
            all_labels = all_letters + all_romans
            
            slice_bounds, horizontal_offset = calculate_all_bounds(
                parts=part_bounds_list,
                composite_height=composite.height,
                composite_width=composite.width,
                marks=all_marks,
                config=config.slice_config,
                labels=all_labels,
                numeral_bbox=numeral_bbox,
                exam_code=exam_code,
                pdf_name=pdf_name,
                question_number=numeral.number,
                diagnostics_collector=diagnostics_collector,
            )
    else:
        part_bounds_list = bounds_from_detections(
            question_num=numeral.number,
            letters=all_letters,
            romans=all_romans,
            composite_height=composite.height,
            marks=all_marks,
            numeral_bbox=numeral_bbox,
        )
        
        all_labels = all_letters + all_romans
        
        slice_bounds, horizontal_offset = calculate_all_bounds(
            parts=part_bounds_list,
            composite_height=composite.height,
            composite_width=composite.width,
            marks=all_marks,
            config=config.slice_config,
            labels=all_labels,
            numeral_bbox=numeral_bbox,
            exam_code=exam_code,
            pdf_name=pdf_name,
            question_number=numeral.number,
            diagnostics_collector=diagnostics_collector,
        )
    
    # STRICT VALIDATION: Collect validation issues from PartBounds
    # These are populated by bounds_from_detections when composite_height fallback is used
    # 1:1 ALIGNMENT: Log warning AND record diagnostic for each part-level issue
    bounds_validation_issues = []
    for part_bound in part_bounds_list:
        if part_bound.validation_issues:
            for issue in part_bound.validation_issues:
                issue_desc = f"{part_bound.label}: {issue}"
                bounds_validation_issues.append(issue_desc)
                
                # Log warning for each part (1:1 alignment)
                logger.warning(
                    f"Q{numeral.number} Part {part_bound.label} INVALID: {issue}"
                )
                
                # Record diagnostic for each part (1:1 alignment)
                if diagnostics_collector:
                    diagnostics_collector.add_layout_issue(
                        pdf_name=pdf_name,
                        exam_code=exam_code,
                        question_number=numeral.number,
                        page_index=0,  # Unknown at this point
                        message=f"Part {part_bound.label} uses composite fallback",
                        details={"issue": issue, "detected_bottom": part_bound.detected_bottom},
                        y_span=(part_bound.detected_top, part_bound.detected_bottom),
                    )
    
    # Extract metadata from PDF name
    year = _extract_year(pdf_name)
    paper = _extract_paper(pdf_name)
    variant = _extract_variant(pdf_name)
    
    # Calculate content_right from rightmost mark box x-coordinate
    # This defines the true right edge of question content for margin cropping
    content_right = None
    if all_marks:
        content_right = max(mark.bbox[2] for mark in all_marks)  # max right edge
    
    # Calculate mark bboxes in composite pixels for metadata
    mark_bboxes = None
    if all_marks:
        mark_bboxes = [mark.bbox for mark in all_marks]  # Store all mark box positions
    
    # numeral_bbox already calculated above in composite coordinates
    
    # Extract text from question for keyword search
    # Note: bounds are now correctly capped in bounds_calculator, no content_right needed
    root_text, child_text = _extract_question_text(doc, segments, slice_bounds, dpi)
    
    # Classify topic using per-part consensus (GAP-017)
    # 1. Build part_texts dict for all parts
    part_texts = {str(numeral.number): root_text}
    for label, text in (child_text or {}).items():
        part_texts[label] = text
    
    # 2. Classify each part individually
    from .classification import classify_all_parts, apply_topic_consensus
    part_topics = classify_all_parts(part_tree, part_texts, exam_code, paper)
    
    # 3. Apply propagation and consensus to get final topic
    from .classification import propagate_topics
    propagated_part_topics = propagate_topics(part_topics, part_tree)
    topic = apply_topic_consensus(part_topics, part_tree, str(numeral.number))
    
    # Update tree with propagated topics
    part_tree = _update_tree_topics(part_tree, propagated_part_topics)
    # Ensure root topic is specifically set to the consensus result
    part_tree = replace(part_tree, topic=topic)

    # Structure: output_dir/exam_code/topic/question_id/
    topic_dir = output_dir / exam_code / topic
    question_dir = topic_dir / question_id
    
    # Extract markscheme pages if MS PDF available and question has mapping
    markscheme_path = None
    if ms_pdf_path and ms_page_mapping:
        from .markscheme import extract_markscheme_for_question
        
        # Get MS page indices for this question from mapping
        ms_page_indices = ms_page_mapping.get(numeral.number, [])
        
        if ms_page_indices:
            ms_image_path = extract_markscheme_for_question(
                ms_pdf_path=ms_pdf_path,
                question_number=numeral.number,
                ms_page_indices=ms_page_indices,
                output_dir=question_dir,
                dpi=config.dpi,
            )
            
            if ms_image_path:
                # Store relative path from question dir (just filename)
                markscheme_path = ms_image_path.name
                logger.debug(f"Extracted MS for Q{numeral.number}: {len(ms_page_indices)} page(s)")
        else:
            logger.debug(f"No MS pages found for Q{numeral.number}")
    
    # Generate debug visualization if enabled
    if config.debug_overlay:
        from .utils.visualizer import save_debug_composite
        
        # Save debug composite with all detection overlays
        debug_path = save_debug_composite(
            composite=composite,
            output_dir=question_dir,
            question_id=question_id,
            numeral=numeral,
            letters=all_letters,
            romans=all_romans,
            marks=all_marks,
            numeral_bbox=numeral_bbox,
        )
        logger.info(f"Saved debug visualization: {debug_path.name}")
    
    # Write output (composite.png, regions.json) - timed
    # OPTIMIZATION C: Use async writing when write_queue is available
    # question_dir already includes topic hierarchy from above
    if timing_log:
        with timed_phase(timing_log, "file_writing", question_id):
            if write_queue:
                # Async write - queues image write in background
                write_question_async(
                    question_id=question_id,
                    composite=composite,
                    part_tree=part_tree,
                    bounds=slice_bounds,
                    output_dir=question_dir,
                    write_queue=write_queue,
                    exam_code=exam_code,
                    year=year,
                    paper=paper,
                    variant=variant,
                    content_right=content_right,
                    numeral_bbox=numeral_bbox,
                    root_text=root_text,
                    child_text=child_text,
                    mark_bboxes=mark_bboxes,
                    markscheme_path=str(markscheme_path) if markscheme_path else None,
                    horizontal_offset=horizontal_offset,
                )
            else:
                # Sync fallback
                write_question(
                    question_id=question_id,
                    composite=composite,
                    part_tree=part_tree,
                    bounds=slice_bounds,
                    output_dir=question_dir,
                    exam_code=exam_code,
                    year=year,
                    paper=paper,
                    variant=variant,
                    content_right=content_right,
                    numeral_bbox=numeral_bbox,
                    root_text=root_text,
                    child_text=child_text,
                    mark_bboxes=mark_bboxes,
                    markscheme_path=str(markscheme_path) if markscheme_path else None,
                    horizontal_offset=horizontal_offset,
                )
    else:
        if write_queue:
            write_question_async(
                question_id=question_id,
                composite=composite,
                part_tree=part_tree,
                bounds=slice_bounds,
                output_dir=question_dir,
                write_queue=write_queue,
                exam_code=exam_code,
                year=year,
                paper=paper,
                variant=variant,
                content_right=content_right,
                numeral_bbox=numeral_bbox,
                root_text=root_text,
                child_text=child_text,
                mark_bboxes=mark_bboxes,
                markscheme_path=str(markscheme_path) if markscheme_path else None,
                horizontal_offset=horizontal_offset,
            )
        else:
            write_question(
                question_id=question_id,
                composite=composite,
                part_tree=part_tree,
                bounds=slice_bounds,
                output_dir=question_dir,
                exam_code=exam_code,
                year=year,
                paper=paper,
                variant=variant,
                content_right=content_right,
                numeral_bbox=numeral_bbox,
                root_text=root_text,
                child_text=child_text,
                mark_bboxes=mark_bboxes,
                markscheme_path=str(markscheme_path) if markscheme_path else None,
                horizontal_offset=horizontal_offset,
            )
    
    # Build metadata record for centralized questions.jsonl
    from gcse_toolkit.core.schemas.validator import QUESTION_SCHEMA_VERSION
    
    # Extract unique sub-topics from part tree (for GUI sub-topic filtering)
    sub_topics = set()  
    def collect_sub_topics(part):
        """Recursively collect all sub-topics from part tree."""
        # Fix: Collect topic from the part itself if valid
        if part.topic and part.topic != "00. Unknown":
            sub_topics.add(part.topic)
            
        if hasattr(part, 'sub_topics') and part.sub_topics:
            sub_topics.update(part.sub_topics)
        if hasattr(part, 'children'):
            for child in part.children:
                collect_sub_topics(child)
    collect_sub_topics(part_tree)
    
    # CRITICAL: Determine if question is valid for selection
    # A question is invalid if it has critical extraction errors that would
    # cause rendering failures or incorrect content selection
    is_valid = True
    validation_failures = []
    
    # Check 1: Must have valid bounds for all parts
    if not slice_bounds:
        is_valid = False
        validation_failures.append("No slice bounds calculated")
    
    # Check 2: Must have detected at least one part (letter or standalone question)
    if not all_letters and not all_romans and part_tree.leaf_count == 1:
        # Single-part question with no sub-parts is OK
        pass
    elif part_tree.leaf_count == 0:
        is_valid = False
        validation_failures.append("No leaf parts detected")
    
    # NOTE: Check 3 (suspicious structure heuristic) REMOVED
    # We trust other validation methods: composite_height fallback, gap detection

    
    # Check 4: Must have valid numeral bbox for root overlay
    if numeral_bbox is None:
        # Not critical - overlay just won't be applied
        logger.debug(f"Q{numeral.number}: No numeral bbox - overlay will be skipped")
    
    # Check 5: Part-level validation issues (already logged warnings + diagnostics above)
    # NOTE: Part-level issues do NOT invalidate the entire question
    # Valid parts are preserved - only the specific invalid parts are excluded
    # Part.is_valid is set in tree_builder and used for filtering downstream

    
    # Log validation result
    if not is_valid:
        logger.warning(
            f"Q{numeral.number} marked as INVALID: {', '.join(validation_failures)}",
            extra={
                "exam_code": exam_code,
                "pdf_name": pdf_name,
                "question_number": numeral.number,
                "validation_failures": validation_failures,
            }
        )
        # Record in diagnostics
        if diagnostics_collector:
            diagnostics_collector.add_invalid_question(
                pdf_name=pdf_name,
                exam_code=exam_code,
                question_number=numeral.number,
                validation_failures=validation_failures,
                y_span=(0, composite.height),
            )
    
    metadata_record = {
        "schema_version": QUESTION_SCHEMA_VERSION,
        "question_id": question_id,
        "exam_code": exam_code,
        "year": year,
        "paper": paper,
        "variant": variant,
        "question_number": numeral.number,
        "total_marks": part_tree.total_marks,
        "part_count": part_tree.leaf_count,
        "topic": topic,
        "sub_topics": sorted(list(sub_topics)),  # CRITICAL: GUI expects this field for sub-topic filtering
        "child_topics": {label: t for label, t in propagated_part_topics.items() if label != str(numeral.number)},
        # CRITICAL: relative_path must be relative to output_dir (cache root)
        # output_dir is the cache root, question_dir is output_dir/exam_code/topic/question_id
        # So relative path should be: exam_code/topic/question_id
        "relative_path": str(question_dir.relative_to(output_dir)),
        # NOTE: content_right, numeral_bbox, mark_bboxes, horizontal_offset moved to regions.json
        "root_text": root_text,
        "child_text": child_text or {},
        "markscheme_path": markscheme_path,
        "is_valid": is_valid,  # Question validation flag
    }
    
    return question_id, metadata_record

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def _extract_question_text(
    doc: fitz.Document,
    segments: list,
    slice_bounds: dict,
    dpi: int,
) -> tuple:
    """
    Extract text content for a question and its parts.
    
    Uses per-part bounds from slice_bounds to filter text.
    Bounds are already correctly capped in bounds_calculator.
    
    Args:
        doc: PDF document
        segments: List of PageSegment objects
        slice_bounds: Dict mapping part label to SliceBounds
        dpi: Resolution for coordinate conversion
        
    Returns:
        Tuple of (root_text, child_text_dict)
    """
    from typing import Dict
    
    # Collect text spans from all segments (now includes x-coordinates)
    all_spans = []
    y_offset = 0
    
    for segment in segments:
        page = doc[segment.page_index]
        # Pass trim_offset to get accurate x-coordinates in composite space
        spans = extract_text_spans(
            page, segment.clip, dpi, y_offset,
            trim_offset=segment.trim_offset,
        )
        all_spans.extend(spans)
        y_offset += segment.image.height
    
    # Build root_text and child_text from part bounds
    root_text = ""
    child_text: Dict[str, str] = {}
    
    from .utils.text import sanitize_metadata_text  # GAP-018: Sanitization
    
    for label, bounds in slice_bounds.items():
        # bounds.right is already correctly capped in bounds_calculator
        text = text_for_bounded_region(
            all_spans,
            bounds.top, bounds.bottom,
            bounds.left, bounds.right,
        )
        
        # Sanitize text to remove answer lines (dots)
        text = sanitize_metadata_text(text)
        if not text:
            continue
            
        # First part (shortest label) is the root
        if '(' not in label:
            root_text = text
        else:
            child_text[label] = text
    
    return root_text, child_text


def _extract_year(pdf_name: str) -> int:
    """Extract year from PDF name like 0478_s24_qp_12."""
    match = re.search(r"[smw](\d{2})", pdf_name, re.IGNORECASE)
    if match:
        year = int(match.group(1))
        return 2000 + year if year < 50 else 1900 + year
    return 2024


def _extract_paper(pdf_name: str) -> int:
    """Extract paper number from PDF name."""
    match = re.search(r"qp_(\d)", pdf_name)
    return int(match.group(1)) if match else 1


def _extract_variant(pdf_name: str) -> int:
    """Extract variant from PDF name."""
    match = re.search(r"qp_\d(\d)", pdf_name)
    return int(match.group(1)) if match else 1


def _write_centralized_metadata(
    output_dir: Path,
    exam_code: str,
    metadata_records: List[Dict[str, Any]],
) -> None:
    """
    Write centralized questions.jsonl metadata file.
    
    Creates a JSONL file containing metadata for all extracted questions
    in a single location. This enables fast question discovery without
    recursive filesystem searches.
    
    File location: {output_dir}/{exam_code}/_metadata/questions.jsonl
    Format: One JSON object per line (JSONL)
    
    PARALLEL SAFE: Uses file locking for concurrent writes from
    parallel PDF extractions.
    
    Args:
        output_dir: Root extraction output directory.
        exam_code: Exam code (e.g., "0478").
        metadata_records: List of metadata dictionaries for all questions.
    """
    if not metadata_records:
        logger.debug(f"No metadata to write for {exam_code}")
        return
    
    from .file_locking import locked_append_jsonl
    
    metadata_path = output_dir / exam_code / "_metadata" / "questions.jsonl"
    
    # PARALLEL SAFE: Use locked append for each record
    # This allows concurrent PDF extractions to safely append to the same file
    try:
        for record in metadata_records:
            locked_append_jsonl(metadata_path, record)
        logger.debug(f"Appended {len(metadata_records)} metadata records to {metadata_path}")
    except OSError as e:
        logger.error(f"Failed to write centralized metadata: {e}")
        raise


    
    
def _update_tree_topics(part: Part, part_topics: Dict[str, str]) -> Part:
    """
    Recursively update part tree with classified topics.
    
    Since Part is frozen, this reconstructs the tree with updated topic fields.
    
    Args:
        part: Root part to update
        part_topics: Dict mapping part label to topic string
        
    Returns:
        New Part instance with updated topics
    """
    
    # Update children first to rebuild from bottom up
    updated_children = []
    for child in part.children:
        updated_children.append(_update_tree_topics(child, part_topics))
        
    # Get topic for this part
    topic = part_topics.get(part.label)
    
    # Create new part with updated topic and children
    return replace(
        part,
        topic=topic,
        children=tuple(updated_children)
    )
