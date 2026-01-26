"""
Module: builder_v2.controller

Purpose:
    Orchestrate the complete exam building pipeline.
    Load → Filter → Select → Compose → Paginate → Render

Key Functions:
    - build_exam(): Main entry point for building an exam

Key Classes:
    - BuildResult: Complete build result
    - BuildError: Exception for build failures

Dependencies:
    - builder_v2.loading: Question loading
    - builder_v2.selection: Question selection
    - builder_v2.layout: Composition and pagination
    - builder_v2.output: PDF rendering

Used By:
    - gcse_toolkit.gui.tabs.build_tab: GUI integration
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from gcse_toolkit.core.models import Question
from gcse_toolkit.core.models.selection import SelectionResult

from .config import BuilderConfig
from .keyword import KeywordIndex
from .loading import load_questions, LoaderError
from .selection import select_questions, SelectionConfig
from .layout import compose_exam, paginate, LayoutConfig
from .output.renderer import render_to_pdf
from .output.markscheme import render_markscheme

logger = logging.getLogger(__name__)


class BuildError(Exception):
    """Error during build pipeline."""
    pass


@dataclass(frozen=True)
class BuildResult:
    """
    Complete build result (immutable).
    
    Attributes:
        questions_pdf: Path to generated questions PDF
        markscheme_pdf: Path to markscheme PDF (if generated)
        selection: Selection result with plans
        total_marks: Total marks in output
        page_count: Number of pages generated
        metadata: Build metadata dictionary
        warnings: Any warnings during build
        
    Example:
        >>> result = build_exam(config)
        >>> print(f"Generated {result.page_count} pages with {result.total_marks} marks")
        >>> print(f"Build timestamp: {result.metadata['generated_at']}")
    """
    questions_pdf: Path
    markscheme_pdf: Optional[Path]
    selection: SelectionResult
    total_marks: int
    page_count: int
    metadata: dict
    warnings: tuple[str, ...]
    questions_zip: Optional[Path] = None


def build_exam(config: BuilderConfig) -> BuildResult:
    """
    Build an exam from start to finish.
    
    Pipeline:
    1. Load questions from V2 cache
    2. Filter by topics/years/papers
    3. Select questions to meet mark target
    4. Compose slice assets
    5. Paginate onto pages
    6. Render to PDF
    7. (Optional) Render markscheme
    
    Args:
        config: Build configuration
        
    Returns:
        BuildResult with paths and metadata
        
    Raises:
        BuildError: If any step fails
        
    Example:
        >>> config = BuilderConfig(
        ...     cache_path=Path("workspace/slices_cache_v2"),
        ...     exam_code="0478",
        ...     target_marks=50,
        ...     output_dir=Path("output"),
        ... )
        >>> result = build_exam(config)
        >>> print(f"Generated {result.page_count} pages")
    """
    warnings: List[str] = []
    start_time = time.perf_counter()
    
    logger.info(f"Starting build for {config.exam_code} targeting {config.target_marks} marks")
    
    # 1. Load questions
    try:
        questions = load_questions(config.cache_path, config.exam_code)
    except LoaderError as e:
        raise BuildError(f"Failed to load questions: {e}") from e
    
    if not questions:
        raise BuildError(f"No questions found for exam code {config.exam_code}")
    
    logger.info(f"Loaded {len(questions)} questions")
    
    # 2. Apply keyword filtering (if keyword mode)
    keyword_matched_labels = {}
    all_questions = questions  # Keep all for backfilling
    if config.keyword_mode and config.keywords:
        keyword_questions, keyword_matched_labels = _filter_by_keywords(questions, config)
        if not keyword_questions:
            raise BuildError(
                f"No questions matched keywords: {config.keywords}. "
                "Check that question text is extracted."
            )
        logger.info(f"Keyword filter: {len(keyword_questions)} questions match, {len(all_questions)} available for backfill")
        # Keep all questions for potential backfilling - selector will prioritize keyword matches
    
    # 3. Apply topic/year/paper filters
    questions = _apply_filters(questions, config)
    
    if not questions:
        raise BuildError("No questions match the specified filters")
    
    logger.info(f"After filtering: {len(questions)} questions")
    
    # 4. Select questions
    selection_config = SelectionConfig(
        target_marks=config.target_marks,
        tolerance=config.tolerance,
        topics=config.topics,
        seed=config.seed,
        part_mode=config.part_mode,
        force_topic_coverage=config.force_topic_coverage,
        # Keyword mode fields (Phase 6.6)
        keyword_mode=config.keyword_mode,
        keyword_matched_labels=keyword_matched_labels,
        pinned_question_ids=set(config.keyword_questions) if config.keyword_questions else set(),
        pinned_part_labels=set(config.keyword_part_pins) if config.keyword_part_pins else set(),
        allow_keyword_backfill=config.allow_keyword_backfill,
    )
    
    selection = select_questions(questions, selection_config)
    
    logger.info(
        f"Selected {selection.question_count} questions, "
        f"achieved {selection.total_marks}/{config.target_marks} marks"
    )
    
    # 5. Compose assets from selected questions
    logger.info("Composing exam assets...")
    
    # Calculate bottom margin: default or increased for footer
    # Footer is at ~15-22pt. 120px @ 300dpi is ~29pt, providing safe clearance.
    # Always reserve this space to ensure consistent layout.
    margin_bottom = max(120, config.margin_px)
    
    layout_config = LayoutConfig(
        page_width=config.page_width_px,
        page_height=config.page_height_px,
        margin_top=config.margin_px,
        margin_bottom=margin_bottom,
        margin_left=config.margin_px,
        margin_right=config.margin_px,
    )
    
    assets = compose_exam(selection, layout_config, show_question_headers=config.show_question_ids)
    logger.info(f"Composed {len(assets)} slice assets")
    
    # 6. Paginate assets onto pages
    logger.info("Paginating exam...")
    layout = paginate(assets, layout_config)
    warnings.extend(layout.warnings)
    logger.info(f"Paginated onto {layout.page_count} pages")
    
    # 7. Determine output directory
    # CRITICAL: Even if GUI provides output_dir, we MUST create timestamped subfolder
    # to prevent overwrites and match V1 behavior
    if config.output_dir:
        # GUI provided a base directory (e.g., workspace/output/0478)
        # Create timestamped subfolder inside it
        output_dir = _generate_timestamped_subfolder(Path(config.output_dir), config)
    else:
        # No output_dir specified, use default with timestamp
        output_dir = _generate_output_dir(config)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    
    # 8. Render questions PDF
    questions_pdf = output_dir / "questions.pdf"
    render_to_pdf(
        layout,
        questions_pdf,
        dpi=layout_config.dpi,
        margin_top_px=layout_config.margin_top,
        margin_bottom_px=layout_config.margin_bottom,
        margin_left_px=layout_config.margin_left,
        page_width_px=layout_config.page_width,
        page_height_px=layout_config.page_height,
        show_footer=config.show_footer,
    )
    logger.info(f"Rendered questions PDF: {questions_pdf}")
    
    # 9. Render markscheme (optional)
    markscheme_pdf = None
    if config.include_markscheme:
        markscheme_pdf = output_dir / "markscheme.pdf"
        render_markscheme(selection, markscheme_pdf,  config.cache_path)
        logger.info(f"Rendered markscheme PDF: {markscheme_pdf}")
    
    # 10. Export ZIP (optional)
    questions_zip = None
    if config.export_zip:
        from .output.zip_writer import write_questions_zip
        questions_zip = output_dir / "questions.zip"
        write_questions_zip(selection, questions_zip)
        logger.info(f"Exported questions ZIP: {questions_zip}")
    
    # Record completion time
    elapsed = time.perf_counter() - start_time
    logger.info(f"Exam generation completed in {elapsed:.2f}s")
    
    # 10. Write metadata
    metadata = _build_metadata(config, selection, layout)
    _write_metadata(output_dir, metadata)
    logger.info(f"Wrote build metadata to {output_dir / 'build_metadata.json'}")
    
    # Return build result
    return BuildResult(
        questions_pdf=questions_pdf,
        markscheme_pdf=markscheme_pdf,
        selection=selection,
        total_marks=selection.total_marks,
        page_count=layout.page_count,
        metadata=metadata,
        warnings=tuple(warnings),
        questions_zip=questions_zip,
    )


def _generate_timestamped_subfolder(base_dir: Path, config: BuilderConfig) -> Path:
    """
    Create timestamped subfolder inside provided base directory.
    
    Args:
        base_dir: Base directory from GUI (e.g., workspace/output/0478)
        config: Build configuration
        
    Returns:
        Path with timestamped subfolder (e.g., base/20250116-103045__m50__s42__topics)
    """
    from datetime import datetime
    import re
    
    # Build folder name components
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    marks_segment = f"m{config.target_marks}"
    seed_segment = f"s{config.seed}"
    
    # Topic slug (or "keywords" or "all")
    # Check keyword_mode attribute (exists in BuilderConfig)
    if config.keyword_mode and config.keywords:
        topic_segment = "keywords"
    elif config.topics:
        # Slugify topics: remove numbering, lowercase, replace spaces with underscores
        topic_slugs = []
        for topic in sorted(config.topics)[:3]:  # Limit to 3 topics for filename
            # Remove leading numbers (e.g., "01. Data" → "data")
            clean = re.sub(r'^\d+\.\s*', '', topic)
            slug = clean.lower().replace(' ', '_').replace('-', '_')
            topic_slugs.append(slug)
        topic_segment = "+".join(topic_slugs)
    else:
        topic_segment = "all"
    
    # Combine: {timestamp}__{marks}__{seed}__{topics}
    folder_name = f"{timestamp}__{marks_segment}__{seed_segment}__{topic_segment}"
    
    # Handle collisions (unlikely but possible)
    output_path = base_dir / folder_name
    if output_path.exists():
        counter = 1
        while (base_dir / f"{folder_name}({counter})").exists():
            counter += 1
        output_path = base_dir / f"{folder_name}({counter})"
    
    return output_path


def _apply_filters(
    questions: List[Question],
    config: BuilderConfig,
) -> List[Question]:
    """
    Apply topic/year/paper filters to questions.
    
    Args:
        questions: List of questions to filter
        config: Build configuration with filter criteria
        
    Returns:
        Filtered list of questions
    """
    result = questions
    
    if config.topics:
        result = [q for q in result if q.topic in config.topics]
        logger.debug(f"Filtered by topics: {len(result)} remaining")
    
    if config.years:
        # Convert string years to int for comparison (GUI returns strings like "2024")
        year_ints = {int(y) for y in config.years}
        result = [q for q in result if q.year in year_ints]
        logger.debug(f"Filtered by years: {len(result)} remaining")
    
    if config.papers:
        result = [q for q in result if q.paper in config.papers]
        logger.debug(f"Filtered by papers: {len(result)} remaining")
    
    return result


def _generate_output_dir(config: BuilderConfig) -> Path:
    """
    Generate default output directory path with timestamp and metadata.
    
    Matches V1 pattern: workspace/output/{exam}/{timestamp__marks__seed__topics}/
    
    Args:
        config: Build configuration
        
    Returns:
        Path for output directory with unique timestamped subfolder
        
    Example:
        >>> _generate_output_dir(config)
        Path('workspace/output/0478/20250116-103045__m50__s42__hardware+software')
    """
    from datetime import datetime
    import re
    
    # Base directory: workspace/output/{exam_code}/
    base = Path("workspace") / "output" / config.exam_code
    base.mkdir(parents=True, exist_ok=True)
    
    # Build folder name components
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    marks_segment = f"m{config.target_marks}"
    seed_segment = f"s{config.seed}"
    
    # Topic segment (from V1 implementation)
    if config.topics:
        def topic_slug(topic: str) -> str:
            """Convert topic to URL-safe slug."""
            topic = re.sub(r"^\d+[\.\)]\s*", "", topic or "").strip()
            topic = re.sub(r"[^A-Za-z0-9]+", "-", topic).strip("-")
            return topic.lower() or "misc"
        
        topics_sorted = sorted(config.topics)
        topic_segment = "+".join(topic_slug(t) for t in topics_sorted)
    elif config.keyword_mode:
        topic_segment = "keywords"
    else:
        topic_segment = "all"
    
    # Combine: {timestamp}__{marks}__{seed}__{topics}
    folder_name = f"{timestamp}__{marks_segment}__{seed_segment}__{topic_segment}"
    folder_name = re.sub(r"[^A-Za-z0-9_\-+:]", "-", folder_name).strip("-")
    
    # Handle collisions (unlikely with timestamp, but V1 does this)
    candidate = base / folder_name
    suffix = 1
    while candidate.exists():
        candidate = base / f"{folder_name} ({suffix})"
        suffix += 1
    
    return candidate


def _filter_by_keywords(
    questions: List[Question],
    config: BuilderConfig,
) -> Tuple[List[Question], Dict[str, Set[str]]]:
    """
    Filter questions by keyword search.
    
    Searches question text for keywords and returns matching questions
    along with the labels of matching parts.
    
    Supports both question-level pins (entire question) and part-level
    pins using format "question_id::part_label".
    
    Args:
        questions: All loaded questions
        config: Build configuration with keywords
        
    Returns:
        Tuple of:
        - Filtered questions (only those matching keywords or pinned)
        - Dict mapping question_id -> set of matching part labels
        
    Example:
        >>> questions, labels = _filter_by_keywords(questions, config)
        >>> labels["q1"]
        {'1(a)', '1(b)(i)'}  # Parts that matched keywords
    """
    index = KeywordIndex()
    index.prime(questions)
    
    result = index.search(config.keywords)
    
    logger.debug(f"Keyword search matched {result.total_questions} questions")
    
    # Parse part-level pins (format: "question_id::part_label")
    part_pins: Dict[str, Set[str]] = {}  # question_id -> set of pinned part labels
    for pin in config.keyword_part_pins:
        if "::" in pin:
            qid, label = pin.split("::", 1)
            if qid not in part_pins:
                part_pins[qid] = set()
            part_pins[qid].add(label)
        else:
            logger.warning(f"Invalid part pin format (expected 'qid::label'): {pin}")
    
    # Build set of matching question IDs (union of keyword matches + pinned questions + questions with pinned parts)
    matching_ids = set(result.question_ids)
    pinned_question_ids = set(config.keyword_questions)
    part_pinned_question_ids = set(part_pins.keys())
    allowed_ids = matching_ids | pinned_question_ids | part_pinned_question_ids
    
    if pinned_question_ids:
        logger.debug(f"Including {len(pinned_question_ids)} pinned questions")
    if part_pins:
        logger.debug(f"Including {sum(len(labels) for labels in part_pins.values())} pinned parts from {len(part_pins)} questions")
    
    # Filter questions
    filtered = [q for q in questions if q.id in allowed_ids]
    
    # Build matched labels dict
    matched_labels: Dict[str, Set[str]] = {}
    
    # Start with keyword matches
    for qid, labels in result.aggregate_labels.items():
        matched_labels[qid] = set(labels)
    
    # Add all parts for pinned questions (question-level pins)
    for qid in pinned_question_ids:
        if qid not in matched_labels:
            q = next((q for q in questions if q.id == qid), None)
            if q:
                # Include all leaf parts
                matched_labels[qid] = {
                    part.label for part in q.question_node.iter_all()
                    if part.is_leaf
                }
        else:
            # Question already has keyword matches, ensure all parts included
            q = next((q for q in questions if q.id == qid), None)
            if q:
                matched_labels[qid].update(
                    part.label for part in q.question_node.iter_all()
                    if part.is_leaf
                )
    
    # Add pinned parts (part-level pins)
    for qid, pinned_part_labels in part_pins.items():
        if qid not in matched_labels:
            matched_labels[qid] = set()
        matched_labels[qid].update(pinned_part_labels)
    
    return filtered, matched_labels


def _build_metadata(
    config: BuilderConfig,
    selection: SelectionResult,
    layout,
) -> dict:
    """
    Build metadata dictionary for generated exam.
    
    Contains:
    - Build configuration
    - Selection statistics
    - Layout information
    - Timestamp
    
    Args:
        config: Build configuration used
        selection: Selection result
        layout: Layout result
        
    Returns:
        Metadata dictionary ready for JSON serialization
        
    Example:
        >>> metadata = _build_metadata(config, selection, layout)
        >>> metadata['exam_code']
        '0478'
    """
    from datetime import datetime
    
    # Calculate stats
    marks_per_topic: Dict[str, int] = {}
    parts_per_topic: Dict[str, int] = {}
    selection_details = []
    
    for plan in selection.plans:
        # Default topic
        default_topic = plan.question.topic
        
        # Aggregate stats by inspecting included leaves
        for leaf in plan.included_leaves:
            # Use leaf topic if available, else fallback to question topic
            topic = leaf.topic or default_topic
            
            marks_per_topic[topic] = marks_per_topic.get(topic, 0) + leaf.marks.value
            parts_per_topic[topic] = parts_per_topic.get(topic, 0) + 1
        
        # Detailed selection info
        details = {
            "question_id": plan.question.id,
            "topic": default_topic,  # Primary topic
            "total_marks": plan.question.total_marks,
            "selected_marks": plan.marks,
            "status": "full" if plan.is_full_question else "partial",
            "included_parts": [],
        }
        for leaf in plan.included_leaves:
            details["included_parts"].append({
                "label": leaf.label,
                "marks": leaf.marks.value,
                "topic": leaf.topic or default_topic
            })
        selection_details.append(details)

    # Build manifest
    manifest = {
        "questions_pdf": [],
    }
    
    # PDF manifest from layout
    if layout:
        for page in layout.pages:
            for placement in page.placements:
                asset = placement.asset
                manifest["questions_pdf"].append({
                    "page": page.index + 1,  # 1-indexed for humans
                    "question_id": asset.question_id,
                    "part_label": asset.part_label,
                    "type": "text" if asset.is_text_header else "image",
                    "marks": asset.marks,
                })

    # ZIP manifest (predictive)
    if config.export_zip:
        zip_files = []
        # Add README
        zip_files.append("README.txt")
        
        for i, plan in enumerate(selection.plans, start=1):
            q_dir = str(i)
            # Root if available
            root_label = plan.question.question_node.label
            # We don't know for sure if root is available without checking provider/files,
            # but usually root label matches. For manifest prediction, we can list what we INTEND to write.
            # actually zip_writer.py logic is: if valid in provider.
            # For now, let's list the parts we explicitly selected + root if applicable.
            
            # Note: zip_writer logic includes root if it exists in provider.
            # We'll assume root is present if selected or if it's the container of selected parts.
            # But strictly, the zip writer writes:
            # 1. Root slice (if available)
            # 2. Selected parts (leaves)
            
            # Let's align with zip_writer logic as best as possible without re-opening images.
            # It's better to be slightly over-inclusive or just list the selected parts.
            # List selected parts:
            for label in sorted(list(plan.included_parts)):
                # Sanitize logic from zip_writer is just strip()
                filename = label.strip() + ".png"
                zip_files.append(f"{q_dir}/{filename}")
                
        manifest["zip_export"] = zip_files

    return {
        "generated_at": datetime.now().isoformat(),
        "exam_code": config.exam_code,
        "target_marks": config.target_marks,
        "actual_marks": selection.total_marks,
        "tolerance": config.tolerance,
        "seed": config.seed,
        "question_count": selection.question_count,
        "page_count": layout.page_count,
        "topics": list(config.topics) if config.topics else None,
        "years": list(config.years) if config.years else None,
        "papers": list(config.papers) if config.papers else None,
        "include_markscheme": config.include_markscheme,
        "keyword_mode": config.keyword_mode,
        "builder_version": "v2",
        "stats": {
            "marks_per_topic": marks_per_topic,
            "parts_per_topic": parts_per_topic,
        },
        "selection_details": selection_details,
        "manifest": manifest,
    }


def _write_metadata(output_dir: Path, metadata: dict) -> None:
    """
    Write metadata JSON file to output directory.
    
    Args:
        output_dir: Output directory path
        metadata: Metadata dictionary
        
    Raises:
        BuildError: If writing fails
        
    Example:
        >>> _write_metadata(Path("output"), metadata)
        # Creates output/build_metadata.json
    """
    import json
    
    metadata_path = output_dir / "build_metadata.json"
    
    try:
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.debug(f"Wrote metadata to {metadata_path}")
    except Exception as e:
        raise BuildError(f"Failed to write metadata: {e}") from e

