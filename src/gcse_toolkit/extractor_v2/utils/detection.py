"""Question-start detection helpers for the v2 extractor."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import fitz  # type: ignore

if TYPE_CHECKING:
    from ..config import ExtractionConfig

from gcse_toolkit.common.thresholds import TEXT_LAYOUT_THRESHOLDS

__all__ = [
    "QuestionStart",
    "detect_question_starts",
    "filter_monotonic",
    "find_next_on_same_page",
    "exam_code",
]

# Regex to extract exam code from PDF filename (e.g., "0478_s23_qp_12.pdf" -> "0478")
EXAM_CODE_RE = re.compile(r"^(\d{3,5})_")


def exam_code(pdf: Path) -> str:
    """Return the qualification or syllabus code from a PDF filename.
    
    Extracts the exam code from standard Cambridge exam PDF naming:
    - Pattern: {code}_{series}_{qp|ms}_{paper}.pdf
    - Example: 0478_s23_qp_12.pdf -> "0478"
    
    Fallback: If pattern doesn't match, extracts digits from first part before underscore.
    
    Args:
        pdf: Path to PDF file
        
    Returns:
        Exam code string (e.g., "0478", "9618")
        
    Example:
        >>> exam_code(Path("0478_s23_qp_12.pdf"))
        '0478'
        >>> exam_code(Path("invalid_name.pdf"))
        'invalid'
    """
    stem = pdf.stem
    match = EXAM_CODE_RE.match(stem)
    if match:
        return match.group(1)
    head = stem.split("_", 1)[0]
    digits = "".join(ch for ch in head if ch.isdigit())
    return digits or head.lower()


@dataclass(frozen=True)
class QuestionStart:
    qnum: int
    page: int
    y: float
    x: float
    text: str
    looks_like_pseudocode: bool = False
    bbox: Optional[Tuple[float, float, float, float]] = None


QUESTION_NUMBER_RE = re.compile(r"^([1-9]\d?)(?:\s|$|\()")
# TODO: Command-word detection may be deprecated; consider removing when coverage is sufficient.
PSEUDOCODE_KEYWORDS = {
    "DECLARE",
    "INPUT",
    "OUTPUT",
    "FOR",
    "NEXT",
    "WHILE",
    "UNTIL",
    "CASE",
    "ELSE",
    "ENDIF",
    "END IF",
    "ELSEIF",
    "THEN",
}


def _page_clip_rect(page: fitz.Page, cfg: ExtractionConfig) -> fitz.Rect:
    """Calculate clipping rectangle with sidebar margins removed.
    
    Args:
        page: PDF page object.
        cfg: Extractor configuration with sidebar ratio.
        
    Returns:
        Clipped rectangle with horizontal margins trimmed.
    """
    rect = page.rect
    shave = rect.width * cfg.sidebar_ratio
    left = rect.x0 + shave
    right = rect.x1 - shave
    if right - left < rect.width * TEXT_LAYOUT_THRESHOLDS.clip_guard_ratio:
        return rect
    return fitz.Rect(left, rect.y0, right, rect.y1)


def _looks_like_pseudocode_line(text: str, line: Dict) -> bool:
    # TODO: Pseudocode heuristics are brittle; mark for eventual removal/refactor.
    stripped = text.strip()
    body = stripped
    m = re.match(r"^\d+\s+(.*)", stripped)
    if m:
        body = m.group(1)
    if any(re.search(rf"\b{kw}\b", body) for kw in PSEUDOCODE_KEYWORDS):
        return True
    if "←" in body or ":=" in body:
        return True
    upper_body = body.upper()
    if upper_body.startswith(("IF ", "ELSE", "END", "REPEAT", "UNTIL")):
        return True
    if re.match(r"^[A-Z]\w*\s*<-\s*", body):
        return True
    words = body.split()
    if len(words) <= 2 and not any(ch in body for ch in ".?:;") and not re.search(r"\bquestion\b", body, re.IGNORECASE):
        alphabetic = sum(ch.isalpha() for ch in body)
        if alphabetic > 0:
            return True
    spans = line.get("spans", [])
    if len(spans) == 1:
        # Handle both dict mode (has 'text') and rawdict mode (has 'chars')
        span = spans[0]
        if "text" in span:
            span_text = span["text"].strip()
        elif "chars" in span:
            span_text = "".join(ch.get("c", "") for ch in span["chars"]).strip()
        else:
            span_text = ""
        if span_text.isupper():
            return True
    return False



def _extract_numeral_bbox_precise(
    chars: List[Dict], qnum_str: str
) -> Optional[Tuple[float, float, float, float]]:
    """Extract precise bbox covering only the question numeral characters.
    
    Uses character-level coordinates to avoid including adjacent labels
    like "(a)" when "12 (a)" appears on the same line.
    
    Args:
        chars: List of character dicts from rawdict mode with 'c' and 'bbox' keys.
        qnum_str: The question number as string (e.g., "12").
        
    Returns:
        Bbox tuple (x0, y0, x1, y1) for just the numeral characters, or None if not found.
        
    Example:
        >>> # For line "12 (a) Identify..."
        >>> # Returns bbox covering just "12", not "(a)"
    """
    if not chars:
        return None
    
    # Find the starting index of the numeral
    text = "".join(ch.get("c", "") for ch in chars)
    if not text.startswith(qnum_str):
        return None
    
    # Collect bboxes for just the numeral characters
    numeral_len = len(qnum_str)
    numeral_chars = chars[:numeral_len]
    
    if not numeral_chars:
        return None
    
    # Compute combined bbox from numeral characters
    x0 = min(ch["bbox"][0] for ch in numeral_chars if "bbox" in ch)
    y0 = min(ch["bbox"][1] for ch in numeral_chars if "bbox" in ch)
    x1 = max(ch["bbox"][2] for ch in numeral_chars if "bbox" in ch)
    y1 = max(ch["bbox"][3] for ch in numeral_chars if "bbox" in ch)
    
    return (x0, y0, x1, y1)


def _detect_left_margin_qnums_on_page(page: fitz.Page) -> List[Tuple[int, float, float, str, bool, Tuple[float, float, float, float]]]:
    """Detect question numbers in the left margin of a page.
    
    Filters out:
    - Headers (top 8% of page, center-aligned)
    - Footers (bottom 8% of page) - prevents page numbers being detected as questions
    - Non-left-margin content
    
    Uses rawdict mode for character-level bbox extraction to handle inline
    patterns like "12 (a)" where we need only the numeral bbox.
    """
    # Use rawdict mode for character-level bbox extraction
    data = page.get_text("rawdict")
    found: List[Tuple[int, float, float, str, bool, Tuple[float, float, float, float]]] = []
    
    # Define header/footer zones to exclude
    header_zone = page.rect.height * 0.08
    footer_zone = page.rect.height * 0.92  # Bottom 8%
    
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            x0, y0, _, _ = line["bbox"]
            
            # Collect all characters from all spans in the line
            all_chars = []
            for span in line.get("spans", []):
                all_chars.extend(span.get("chars", []))
            
            # Build text from characters
            text = "".join(ch.get("c", "") for ch in all_chars).strip()
            if not text or text.count(".") >= 4:
                continue
            if x0 > page.rect.width * 0.12:
                continue
            m = QUESTION_NUMBER_RE.match(text)
            if not m:
                continue
            # Skip header zone (centered text at top)
            if y0 < header_zone and (page.rect.width * 0.40 <= x0 <= page.rect.width * 0.60):
                continue
            # Skip footer zone - prevents page numbers like "11" being detected as Q11
            if y0 > footer_zone:
                continue
            if x0 > page.rect.width * 0.23:
                continue
            qnum = int(m.group(1))
            looks_like = _looks_like_pseudocode_line(text, line)
            
            # Extract precise bbox for just the numeral characters
            # This prevents oversized bbox when "12 (a) text..." is all on one line
            qnum_str = str(qnum)
            qnum_bbox = _extract_numeral_bbox_precise(all_chars, qnum_str)
            
            # Fallback to line bbox if precise extraction fails
            if qnum_bbox is None:
                qnum_bbox = tuple(line["bbox"])
            
            found.append((qnum, x0, y0, text, looks_like, qnum_bbox))

    plain = page.get_text("text") or ""
    seen_numbers = {item[0] for item in found}
    for match in re.finditer(r"(?i)\bquestion\s*(\d{1,2})\b", plain):
        qnum = int(match.group(1))
        if qnum in seen_numbers:
            continue
        found.append((qnum, page.rect.x0, 0.0, f"Question {qnum}", False, (page.rect.x0, 0.0, page.rect.x1, 0.0)))
    return sorted(found, key=lambda item: item[2])


def find_next_on_same_page(
    page: fitz.Page,
    start_y: float,
    current_qnum: int,
    cfg: ExtractionConfig,
) -> Optional[float]:
    rect = _page_clip_rect(page, cfg)
    data = page.get_text("dict")
    candidates: List[float] = []
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            x0, y0, _, _ = line["bbox"]
            if y0 <= start_y + 5:
                continue
            text = "".join(span["text"] for span in line.get("spans", [])).strip()
            if not text or text.count(".") >= 4:
                continue
            m = QUESTION_NUMBER_RE.match(text)
            if not m:
                continue
            candidate_qnum = int(m.group(1))
            if candidate_qnum <= current_qnum:
                continue
            if x0 > page.rect.width * 0.23:
                continue
            if _looks_like_pseudocode_line(text, line):
                continue
            if x0 > rect.x1:
                continue
            if not any(ch.isalpha() for ch in text) and x0 > page.rect.width * 0.12:
                continue
            if page.rect.width * 0.09 < x0 < page.rect.width * 0.14:
                digits = sum(ch.isdigit() for ch in text)
                if digits > 2 and any(ch.isalpha() for ch in text):
                    continue
            candidates.append(y0)
    return min(candidates) if candidates else None


def detect_question_starts(doc: fitz.Document, cfg: ExtractionConfig) -> List[QuestionStart]:
    """Detect all question start markers in a PDF document.
    
    Scans each page for patterns that look like question numbers (1, 2, 3, etc.)
    in the left margin or "Question N" patterns in the text.
    
    Args:
        doc: PyMuPDF document to scan.
        cfg: Extractor configuration.
        
    Returns:
        List of QuestionStart objects with position and metadata.
    """
    starts: List[QuestionStart] = []
    for page_index in range(len(doc)):
        page = doc[page_index]
        found = _detect_left_margin_qnums_on_page(page)
        for qnum, x, y, text, looks_like, bbox in found:
            starts.append(
                QuestionStart(
                    qnum=qnum,
                    page=page_index,
                    y=y,
                    x=x,
                    text=text,
                    looks_like_pseudocode=looks_like,
                    bbox=bbox,
                )
            )
    return starts


def _find_candidate_with_q(
    ordered: List[QuestionStart],
    start_idx: int,
    target_q: int,
    used_indices: Set[int],
) -> Optional[int]:
    """Find the best candidate for a target question number.
    
    Preference order:
    1. Real left-margin detections (y > 0) over fallback "Question N" (y == 0)
    2. Non-pseudocode detections over pseudocode-like detections
    """
    best_idx: Optional[int] = None
    for idx in range(start_idx, len(ordered)):
        if idx in used_indices:
            continue
        candidate = ordered[idx]
        if candidate.qnum != target_q:
            continue
        if best_idx is None:
            best_idx = idx
            # Keep searching if this is a fallback detection (y==0) or pseudocode
            if candidate.y > 0 and not candidate.looks_like_pseudocode:
                break
            continue
        
        current_best = ordered[best_idx]
        
        # Prefer detections with y > 0 (real position) over y == 0 (fallback)
        if current_best.y == 0 and candidate.y > 0:
            best_idx = idx
            if not candidate.looks_like_pseudocode:
                break
            continue
        
        # Prefer non-pseudocode detections
        if current_best.looks_like_pseudocode and not candidate.looks_like_pseudocode:
            best_idx = idx
            break
    return best_idx



def _find_next_candidate(
    ordered: List[QuestionStart],
    start_idx: int,
    used_indices: Set[int],
) -> Optional[int]:
    for idx in range(start_idx, len(ordered)):
        if idx in used_indices:
            continue
        return idx
    return None


def resolve_question_sequence(starts: Iterable[QuestionStart], max_gap: int = 2) -> List[QuestionStart]:
    ordered = sorted(starts, key=lambda item: (item.page, item.y))
    if not ordered:
        return []
    resolved: List[QuestionStart] = []
    used_indices: Set[int] = set()
    resolved_qnums: Set[int] = set()  # Track already-resolved question numbers
    expected_q = 1
    prev_idx: Optional[int] = None
    prev_qnum = 0

    while True:
        idx = _find_candidate_with_q(ordered, 0 if prev_idx is None else prev_idx + 1, expected_q, used_indices)
        if idx is None:
            idx = _find_next_candidate(ordered, 0 if prev_idx is None else prev_idx + 1, used_indices)
            if idx is None:
                break
            # Skip this candidate if its qnum was already resolved (prevents duplicates)
            if ordered[idx].qnum in resolved_qnums:
                used_indices.add(idx)  # Mark as used to skip it
                continue
            expected_q = ordered[idx].qnum
        resolved.append(ordered[idx])
        used_indices.add(idx)
        resolved_qnums.add(ordered[idx].qnum)  # Track this qnum as resolved
        prev_idx = idx
        prev_qnum = ordered[idx].qnum
        expected_q = prev_qnum + 1
        if expected_q - prev_qnum > max_gap:
            expected_q = prev_qnum + 1

    return resolved



def filter_monotonic(starts: Iterable[QuestionStart]) -> List[QuestionStart]:
    """Filter question starts to ensure monotonic question numbering.
    
    Removes duplicate question numbers and ensures questions appear in
    sequential order (1, 2, 3...). Prefers non-pseudocode detections when
    duplicates exist.
    
    Args:
        starts: Iterable of detected question starts.
        
    Returns:
        Filtered list of question starts in sequential order.
    """
    return resolve_question_sequence(starts)
