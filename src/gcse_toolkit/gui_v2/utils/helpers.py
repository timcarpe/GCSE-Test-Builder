"""
Helper functions for GUI v2.
Helper utilities for GUI v2.
"""
import json
import platform
import re
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Iterable, Set
from PySide6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)
from gcse_toolkit.common import canonical_sub_topic_label, resolve_topic_label, topic_sub_topics


def discover_exam_codes(root: Path) -> list[str]:
    """Discover exam codes in cache by looking for questions.jsonl metadata file.
    
    Single source of truth: {root}/{exam_code}/_metadata/questions.jsonl
    """
    codes: list[str] = []
    if not root.exists():
        return codes
    
    # Check subdirectories for exam codes with centralized metadata
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        
        # Only format: _metadata/questions.jsonl
        if (entry / "_metadata" / "questions.jsonl").exists():
            codes.append(entry.name)
    
    return codes


def check_metadata_versions(root: Path) -> dict[str, int]:
    """
    Check schema versions of all discovered exams.
    
    Args:
        root: The metadata root directory containing extracted exams.
        
    Returns:
        Dict mapping exam_code to schema_version for outdated exams only.
        Empty dict if all exams are up-to-date or no exams found.
    """
    # V2 uses QUESTION_SCHEMA_VERSION (currently 7)
    from gcse_toolkit.core.schemas.validator import QUESTION_SCHEMA_VERSION
    
    outdated: dict[str, int] = {}
    codes = discover_exam_codes(root)
    
    for code in codes:
        # Check V2 centralized metadata format
        jsonl_path = _questions_json_path(root, code)
        
        if jsonl_path and jsonl_path.exists():
            try:
                # Read first line to check schema version
                with open(jsonl_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    if first_line:
                        try:
                            data = json.loads(first_line)
                            # V2 uses "schema_version", V1 used "_schema_version"
                            version = data.get("schema_version", data.get("_schema_version", 1))
                            if version < QUESTION_SCHEMA_VERSION:
                                outdated[code] = version
                        except json.JSONDecodeError:
                            # Treat corrupt files as outdated (version 0)
                            outdated[code] = 0
            except OSError:
                pass
            continue
            
        # Check V2 per-question metadata format (fallback if no centralized metadata)
        exam_dir = root / code
        if exam_dir.exists():
            # Check the first valid metadata.json we find
            for question_dir in exam_dir.iterdir():
                if not question_dir.is_dir() or question_dir.name.startswith("."):
                    continue
                meta_file = question_dir / "metadata.json"
                if meta_file.exists():
                    try:
                        with meta_file.open("r", encoding="utf-8") as f:
                            data = json.load(f)
                            version = data.get("schema_version", 1)
                            if version < QUESTION_SCHEMA_VERSION:
                                outdated[code] = version
                        break # Only need to check one file
                    except (OSError, json.JSONDecodeError):
                        continue
    
    return outdated


def discover_years_for_exam(exam_code: str, metadata_root: Path) -> List[str]:
    """
    Discover unique years from metadata for a given exam code.
    
    Args:
        exam_code: The exam code to scan
        metadata_root: The metadata root directory
        
    Returns:
        Sorted list of unique year strings found in the metadata.
    """
    years: Set[str] = set()
    
    # Check V1 format
    jsonl_path = _questions_json_path(metadata_root, exam_code)
    
    if jsonl_path and jsonl_path.exists():
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        year = data.get("year")
                        # Accept both int and str, convert to string for storage
                        if year is not None:
                            years.add(str(year))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
    else:
        # Check V2 format
        exam_dir = metadata_root / exam_code
        if exam_dir.exists():
            for question_dir in exam_dir.iterdir():
                if not question_dir.is_dir() or question_dir.name.startswith("."):
                    continue
                meta_file = question_dir / "metadata.json"
                if meta_file.exists():
                    try:
                        with meta_file.open("r", encoding="utf-8") as f:
                            data = json.load(f)
                            year = str(data.get("year", ""))
                            if year:
                                years.add(year)
                    except (OSError, json.JSONDecodeError):
                        continue
    
    return sorted(years)


def discover_papers_for_exam(exam_code: str, metadata_root: Path) -> List[int]:
    """
    Discover unique paper numbers from metadata for a given exam code.
    
    Args:
        exam_code: The exam code to scan
        metadata_root: The metadata root directory
        
    Returns:
        Sorted list of unique paper numbers found in the metadata (e.g., [1, 2]).
    """
    papers: Set[int] = set()
    
    # Check V1 format
    jsonl_path = _questions_json_path(metadata_root, exam_code)
    
    if jsonl_path and jsonl_path.exists():
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        # V2 uses "paper" (int), V1 uses "paper_no" (int)
                        paper_no = data.get("paper") or data.get("paper_no")
                        if paper_no and isinstance(paper_no, int):
                            papers.add(paper_no)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
    else:
        # Check V2 format
        exam_dir = metadata_root / exam_code
        if exam_dir.exists():
            for question_dir in exam_dir.iterdir():
                if not question_dir.is_dir() or question_dir.name.startswith("."):
                    continue
                meta_file = question_dir / "metadata.json"
                if meta_file.exists():
                    try:
                        with meta_file.open("r", encoding="utf-8") as f:
                            data = json.load(f)
                            paper = data.get("paper")
                            if paper and isinstance(paper, int):
                                papers.add(paper)
                            elif paper and isinstance(paper, str) and paper.isdigit():
                                papers.add(int(paper))
                    except (OSError, json.JSONDecodeError):
                        continue
    
    return sorted(papers)


def scan_exam_sources(
    exams_root: Path,
    supported_codes: set[str]
) -> Tuple[dict[str, list[Path]], dict[str, list[Path]], list[Path]]:
    """
    Scan PDF folder and categorize exam files.
    
    Args:
        exams_root: Root directory containing exam PDFs
        supported_codes: Set of supported exam codes from exam definitions
    
    Returns:
        Tuple of (supported_map, unsupported_map, invalid_files) where:
        - supported_map: {exam_code: [pdf_paths]} for supported exams
        - unsupported_map: {exam_code: [pdf_paths]} for unsupported exams
        - invalid_files: [pdf_paths] for files with invalid naming patterns
    """
    from gcse_toolkit.extractor_v2.utils import exam_code as detect_exam_code
    
    supported: dict[str, list[Path]] = {}
    unsupported: dict[str, list[Path]] = {}
    invalid: list[Path] = []
    
    # Pattern to match valid QUESTION PAPER filenames only (NOT markschemes)
    # Example: 4037_abc_qp_12.pdf (qp = question paper)
    # Explicitly excludes: 4037_abc_ms_12.pdf (ms = mark scheme)
    pattern = re.compile(r"_(\w{3})_(q[pP])_(\d{2})")
    
    if not exams_root.exists():
        return supported, unsupported, invalid
    
    try:
        pdfs = sorted(exams_root.rglob("*.pdf"))
    except OSError:
        return supported, unsupported, invalid
    
    for pdf in pdfs:
        stem = pdf.stem.lower()
        
        # Skip markscheme files explicitly (extractor finds them automatically)
        if "_ms_" in stem or "_MS_" in pdf.stem:
            logger.debug(f"Skipping markscheme file: {pdf.name}")
            continue
        
        # Check if filename matches expected pattern
        if not pattern.search(stem):
            invalid.append(pdf)
            continue
        
        # Detect exam code from PDF
        code = detect_exam_code(pdf)
        
        if code in supported_codes:
            supported.setdefault(code, []).append(pdf)
        else:
            key = code or "unknown"
            unsupported.setdefault(key, []).append(pdf)
    
    return supported, unsupported, invalid


def open_folder_in_browser(folder_path: Path) -> Tuple[bool, Optional[str]]:
    """
    Open a folder in the system's file browser.
    
    Args:
        folder_path: Path to the folder to open
        
    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    import platform
    import subprocess
    
    if not folder_path.exists():
        return False, f"Folder does not exist: {folder_path}"
    
    if not folder_path.is_dir():
        return False, f"Path is not a directory: {folder_path}"
        
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess.Popen(["open", str(folder_path)])
        elif system == "Windows":
            subprocess.Popen(["explorer", str(folder_path)])
        else:  # Linux
            subprocess.Popen(["xdg-open", str(folder_path)])
        return True, None
    except FileNotFoundError:
        return False, f"File browser command not found for {system}"
    except PermissionError:
        return False, f"Permission denied when opening folder: {folder_path}"
    except Exception as e:
        return False, f"Failed to open folder: {e}"


def _questions_json_path(metadata_root: Path, exam_code: str) -> Optional[Path]:
    candidates = [metadata_root / exam_code / "_metadata" / "questions.jsonl"]
    if metadata_root.name == exam_code:
        candidates.append(metadata_root / "_metadata" / "questions.jsonl")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_topics(metadata_root: Path, exam_code: str, year_filter: Optional[List[str]] = None, paper_filter: Optional[List[int]] = None) -> Tuple[List[str], Dict[str, int], Dict[str, Dict[str, int]]]:
    """
    Load topic and sub-topic counts from metadata.
    
    Supports both formats:
    - V1: {exam_code}/_metadata/questions.jsonl
    - V2: {exam_code}/{question_id}/metadata.json (per-question)
    
    Args:
        metadata_root: Path to metadata root
        exam_code: Exam code to load topics for
        year_filter: Optional list of year strings to filter questions by (e.g., ["2023", "2024"]). 
                    None or empty list means all years.
        paper_filter: Optional list of paper numbers to filter questions by (e.g., [1, 2]).
                    None or empty list means all papers.
    
    Returns:
        Tuple of (ordered_topics, topic_counts, sub_topic_counts)
    """
    topic_counts: Dict[str, int] = {}
    sub_topic_counts: Dict[str, Dict[str, int]] = {}
    
    # Pre-fill with canonical topics
    canonical_map = topic_sub_topics(exam_code)
    for topic, subs in canonical_map.items():
        topic_counts[topic] = 0
        sub_topic_counts[topic] = {sub: 0 for sub in subs}

    def canonical(label: Optional[str]) -> Optional[str]:
        if not label:
            return None
        cleaned = str(label).strip()
        if not cleaned:
            return None
        return resolve_topic_label(cleaned, exam_code)

    def bump_topic(label: Optional[str], count: int = 1) -> Optional[str]:
        """Increment topic count by count (number of parts/sub-questions)."""
        canonical_label = canonical(label)
        if not canonical_label:
            return None
        topic_counts[canonical_label] = topic_counts.get(canonical_label, 0) + count
        return canonical_label

    def bump_sub_topic(topic_label: Optional[str], sub_topic: Optional[str]) -> None:
        canonical_topic = canonical(topic_label)
        canonical_sub = canonical_sub_topic_label(canonical_topic, sub_topic, exam_code)
        if not canonical_topic or not canonical_sub:
            return
        
        if canonical_topic not in sub_topic_counts:
            sub_topic_counts[canonical_topic] = {}
            
        sub_topic_counts[canonical_topic][canonical_sub] = sub_topic_counts[canonical_topic].get(canonical_sub, 0) + 1

    # Load from centralized JSONL (single source of truth)
    meta_path = _questions_json_path(metadata_root, exam_code)
    if meta_path and meta_path.exists():
        _load_topics_from_jsonl(meta_path, year_filter, paper_filter, bump_topic, bump_sub_topic)
    else:
        logger.warning(f"No questions.jsonl found for {exam_code}")
            
    # Sort topics
    ordered_topics = sorted(topic_counts.keys(), key=lambda t: t.lower())
    
    return ordered_topics, topic_counts, sub_topic_counts


def _load_topics_from_jsonl(meta_path: Path, year_filter, paper_filter, bump_topic, bump_sub_topic):
    """Load topics from centralized questions.jsonl file."""
    def collect_parts(parts, inherited_topic):
        for part in parts or []:
            part_topic = part.get("topic") or inherited_topic
            canonical_topic = bump_topic(part_topic) or inherited_topic
            for sub_topic in part.get("sub_topics") or []:
                bump_sub_topic(canonical_topic or inherited_topic, sub_topic)
            collect_parts(part.get("children") or [], canonical_topic or inherited_topic)

    try:
        with meta_path.open("r", encoding="utf-8") as handle:
            for line_num, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping malformed JSON at line {line_num} in {meta_path}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Unexpected error parsing line {line_num} in {meta_path}: {e}")
                    continue
                
                # Apply year filter if specified
                if year_filter:
                    question_year = payload.get("year")
                    if question_year is not None:
                        question_year = str(question_year)  # Normalize to string
                    if question_year not in year_filter:
                        continue
                
                # Apply paper filter if specified
                if paper_filter:
                    question_paper = payload.get("paper")
                    if question_paper not in paper_filter:
                        continue
                
                # Skip invalid questions (is_valid=false means extraction issues)
                if not payload.get("is_valid", True):
                    continue
                
                try:
                    main_topic = payload.get("topic")
                    
                    # Count leaf parts only (not context roots)
                    part_count = payload.get("leaf_part_count") or payload.get("part_count", 1)
                    
                    canonical_main = bump_topic(main_topic, count=part_count)
                    for sub_topic in payload.get("sub_topics") or []:
                        bump_sub_topic(canonical_main, sub_topic)
                    collect_parts(payload.get("parts") or [], canonical_main)
                except Exception as e:
                    logger.warning(f"Error processing question data at line {line_num}: {e}")
                    continue

    except OSError as e:
        logger.warning(f"Could not read metadata file {meta_path}: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error reading {meta_path}: {e}")
