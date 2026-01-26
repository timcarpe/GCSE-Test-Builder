"""
Module: extractor_v2.diagnostics

Captures label detection issues during extraction and generates
diagnostic reports for analysis.

Structure:
- Each issue has prev_label_info, next_label_info as inline strings
- pdf_content_between_labels: Text passed directly when recording issue
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple, Callable

logger = logging.getLogger(__name__)

# Type alias for text extraction callback: (y_start, y_end) -> str
TextExtractor = Callable[[int, int], str]


@dataclass
class DetectionIssue:
    """
    A single detection issue with diagnostic context.
    
    Fields:
    - prev_label_info: "label @ y=123 (bbox: [x1,y1,x2,y2])"
    - next_label_info: "label @ y=456 (bbox: [x1,y1,x2,y2])"
    - pdf_content_between_labels: Text from PDF between the labels
    - validation_outcome: Map of part ID → status ("VALID"/"INVALID: reason")
    """
    issue_type: str
    pdf_name: str
    exam_code: str
    question_number: int
    message: str
    y_span: Tuple[int, int] = (0, 0)
    
    # Diagnostic context
    prev_label_info: str = ""
    next_label_info: str = ""
    pdf_content_between_labels: str = ""
    
    # Part validation outcomes: e.g., {"2(a)": "VALID", "2(b)": "INVALID: Label not detected"}
    validation_outcome: Dict[str, str] = None  # type: ignore
    
    def __post_init__(self):
        if self.validation_outcome is None:
            self.validation_outcome = {}
    
    def to_dict(self) -> Dict[str, Any]:
        d = {
            "issue_type": self.issue_type,
            "pdf_name": self.pdf_name,
            "exam_code": self.exam_code,
            "question_number": self.question_number,
            "message": self.message,
            "y_span": list(self.y_span),
        }
        
        if self.prev_label_info:
            d["prev_label"] = self.prev_label_info
        if self.next_label_info:
            d["next_label"] = self.next_label_info
        if self.pdf_content_between_labels:
            d["pdf_content_between_labels"] = self.pdf_content_between_labels[:2000]
        if self.validation_outcome:
            d["validation_outcome"] = self.validation_outcome
        
        return d


def _format_label_info(label: str, kind: str, y: int, bbox: Optional[Tuple[int, int, int, int]]) -> str:
    """Format label info as simple string."""
    bbox_str = f" bbox:{list(bbox)}" if bbox else ""
    return f"({label}) {kind} @ y={y}{bbox_str}"


class DiagnosticsCollector:
    """
    Thread-safe collector for detection issues.
    
    Issues are added with all data including extracted text.
    No callbacks - text extraction is handled by the caller.
    """
    
    def __init__(self):
        self._issues: List[DetectionIssue] = []
        self._lock = threading.Lock()
        self._pdfs: Set[str] = set()
    
    def add_letter_gap(
        self,
        pdf_name: str,
        exam_code: str,
        question_number: int,
        current_label: str,
        next_label: str,
        missed: List[str],
        y_span: Tuple[int, int],
        prev_y: int = 0,
        prev_bbox: Optional[Tuple[int, int, int, int]] = None,
        next_y: int = 0,
        next_bbox: Optional[Tuple[int, int, int, int]] = None,
        pdf_content: str = "",  # Text passed directly by caller
    ) -> None:
        """Record a gap in letter sequence."""
        message = (
            f"Q{question_number}: Letter gap ({current_label}) → ({next_label}), "
            f"missed: {', '.join(f'({m})' for m in missed)}. Y: {y_span[0]}-{y_span[1]}"
        )
        
        issue = DetectionIssue(
            issue_type="letter_gap",
            pdf_name=pdf_name,
            exam_code=exam_code,
            question_number=question_number,
            message=message,
            y_span=y_span,
            prev_label_info=_format_label_info(current_label, "letter", prev_y, prev_bbox),
            next_label_info=_format_label_info(next_label, "letter", next_y, next_bbox),
            pdf_content_between_labels=pdf_content,
        )
        
        with self._lock:
            self._issues.append(issue)
            self._pdfs.add(pdf_name)
    
    def add_roman_gap(
        self,
        pdf_name: str,
        exam_code: str,
        question_number: int,
        parent_label: str,
        current_roman: str,
        next_roman: str,
        missed: List[str],
        y_span: Tuple[int, int],
        prev_y: int = 0,
        prev_bbox: Optional[Tuple[int, int, int, int]] = None,
        next_y: int = 0,
        next_bbox: Optional[Tuple[int, int, int, int]] = None,
        pdf_content: str = "",
    ) -> None:
        """Record a gap in roman numeral sequence."""
        message = (
            f"Q{question_number}: Roman gap in {parent_label}: ({current_roman}) → ({next_roman}), "
            f"missed: {', '.join(f'({m})' for m in missed)}. Y: {y_span[0]}-{y_span[1]}"
        )
        
        issue = DetectionIssue(
            issue_type="roman_gap",
            pdf_name=pdf_name,
            exam_code=exam_code,
            question_number=question_number,
            message=message,
            y_span=y_span,
            prev_label_info=_format_label_info(current_roman, "roman", prev_y, prev_bbox),
            next_label_info=_format_label_info(next_roman, "roman", next_y, next_bbox),
            pdf_content_between_labels=pdf_content,
        )
        
        with self._lock:
            self._issues.append(issue)
            self._pdfs.add(pdf_name)
    
    def add_roman_reset(
        self,
        pdf_name: str,
        exam_code: str,
        question_number: int,
        parent_label: str,
        prev_roman: str,
        reset_roman: str,
        y_span: Tuple[int, int],
        prev_y: int = 0,
        prev_bbox: Optional[Tuple[int, int, int, int]] = None,
        next_y: int = 0,
        next_bbox: Optional[Tuple[int, int, int, int]] = None,
        pdf_content: str = "",
    ) -> None:
        """Record an unexpected roman numeral reset."""
        message = (
            f"Q{question_number}: Roman reset in {parent_label}: ({prev_roman}) → ({reset_roman}). "
            f"Missed parent label? Y: {y_span[0]}-{y_span[1]}"
        )
        
        issue = DetectionIssue(
            issue_type="roman_reset",
            pdf_name=pdf_name,
            exam_code=exam_code,
            question_number=question_number,
            message=message,
            y_span=y_span,
            prev_label_info=_format_label_info(prev_roman, "roman", prev_y, prev_bbox),
            next_label_info=_format_label_info(reset_roman, "roman", next_y, next_bbox),
            pdf_content_between_labels=pdf_content,
        )
        
        with self._lock:
            self._issues.append(issue)
            self._pdfs.add(pdf_name)
    
    def add_orphaned_romans(
        self,
        pdf_name: str,
        exam_code: str,
        question_number: int,
        letters_detected: List[str],
        romans_detected: List[str],
        y_span: Tuple[int, int] = (0, 0),
        prev_label_info: str = "",
        next_label_info: str = "",
    ) -> None:
        """Record when more romans than letters (suggests missed parent labels).
        
        Args:
            y_span: Visual span from question start to first orphaned roman
            prev_label_info: Last valid detection before orphans
            next_label_info: First orphaned roman position
        """
        message = (
            f"Q{question_number}: {len(romans_detected)} romans but only "
            f"{len(letters_detected)} letters. Letters: {letters_detected}, Romans: {romans_detected}"
        )
        
        issue = DetectionIssue(
            issue_type="orphaned_romans",
            pdf_name=pdf_name,
            exam_code=exam_code,
            question_number=question_number,
            message=message,
            y_span=y_span,
            prev_label_info=prev_label_info,
            next_label_info=next_label_info,
        )
        
        with self._lock:
            self._issues.append(issue)
            self._pdfs.add(pdf_name)
    
    def add_layout_issue(
        self,
        pdf_name: str,
        exam_code: str,
        question_number: Optional[int],
        page_index: int,
        message: str,
        details: Dict[str, Any],
        y_span: Tuple[int, int] = (0, 0),
        prev_label_info: str = "",
        next_label_info: str = "",
    ) -> None:
        """Record a layout consistency issue (e.g. mark box alignment).
        
        Args:
            y_span: Visual span around the problematic element
            prev_label_info: Previous valid detection
            next_label_info: Next valid detection
        """
        full_message = f"Q{question_number or '?'} Layout Issue (Page {page_index}): {message}"
        
        issue = DetectionIssue(
            issue_type="layout_issue",
            pdf_name=pdf_name,
            exam_code=exam_code,
            question_number=question_number or 0,
            message=full_message,
            y_span=y_span,
            prev_label_info=prev_label_info,
            next_label_info=next_label_info,
        )
        
        with self._lock:
            self._issues.append(issue)
            self._pdfs.add(pdf_name)

    def add_invalid_question(
        self,
        pdf_name: str,
        exam_code: str,
        question_number: int,
        validation_failures: List[str],
        y_span: Tuple[int, int] = (0, 0),
        prev_label_info: str = "",
        next_label_info: str = "",
    ) -> None:
        """Record a question marked as invalid."""
        message = f"Q{question_number} INVALID: {', '.join(validation_failures)}"
        
        issue = DetectionIssue(
            issue_type="invalid_question",
            pdf_name=pdf_name,
            exam_code=exam_code,
            question_number=question_number,
            message=message,
            y_span=y_span,
            prev_label_info=prev_label_info,
            next_label_info=next_label_info,
        )
        
        with self._lock:
            self._issues.append(issue)
            self._pdfs.add(pdf_name)
    

    
    def generate_report(self) -> "DetectionDiagnosticsReport":
        with self._lock:
            return DetectionDiagnosticsReport.from_issues(list(self._issues), set(self._pdfs))
    
    @property
    def issue_count(self) -> int:
        with self._lock:
            return len(self._issues)


@dataclass
class DetectionDiagnosticsReport:
    """Complete diagnostics report."""
    generated_at: str
    source_pdfs: List[str]
    total_issues: int
    summary_by_type: Dict[str, int]
    issues: List[DetectionIssue]
    
    @classmethod
    def from_issues(cls, issues: List[DetectionIssue], pdfs: Set[str]) -> "DetectionDiagnosticsReport":
        summary_by_type: Dict[str, int] = {}
        for issue in issues:
            summary_by_type[issue.issue_type] = summary_by_type.get(issue.issue_type, 0) + 1
        
        return cls(
            generated_at=datetime.now(timezone.utc).isoformat(),
            source_pdfs=sorted(pdfs),
            total_issues=len(issues),
            summary_by_type=summary_by_type,
            issues=issues,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "source_pdfs": self.source_pdfs,
            "total_issues": self.total_issues,
            "summary_by_type": self.summary_by_type,
            "issues": [issue.to_dict() for issue in self.issues],
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())
        logger.info(f"Detection diagnostics saved: {path}")
