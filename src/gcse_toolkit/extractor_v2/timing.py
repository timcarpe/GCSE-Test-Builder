"""
Module: extractor_v2.timing

Purpose:
    Timing instrumentation for the extraction pipeline to identify
    performance bottlenecks and optimization opportunities.

Key Classes:
    - TimingLog: Collects timing metrics for paper and question phases
    
Key Functions:
    - timed_phase: Context manager for timing code blocks

Dependencies:
    - time (std)
    - contextlib (std)
    - dataclasses (std)

Used By:
    - extractor_v2.pipeline: Main extraction orchestrator
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TimingLog:
    """
    Timing metrics for extraction pipeline.
    
    Collects both paper-level (global) and question-level (per-question)
    timing metrics for performance analysis.
    
    Attributes:
        paper_timings: Dict of phase_name -> duration_seconds
        question_timings: Dict of question_id -> {phase_name -> duration_seconds}
    
    Example:
        >>> log = TimingLog()
        >>> log.log_paper("numeral_detection", 0.234)
        >>> log.log_question("0478_s25_qp_11_q1", "tree_building", 0.012)
        >>> print(log.summary())
    """
    paper_timings: Dict[str, float] = field(default_factory=dict)
    question_timings: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    def log_paper(self, phase: str, duration: float) -> None:
        """Log a paper-level timing metric."""
        self.paper_timings[phase] = duration
    
    def log_question(self, question_id: str, phase: str, duration: float) -> None:
        """Log a question-level timing metric."""
        if question_id not in self.question_timings:
            self.question_timings[question_id] = {}
        self.question_timings[question_id][phase] = duration
    
    def get_question_total(self, question_id: str) -> float:
        """Get total time for a question."""
        if question_id not in self.question_timings:
            return 0.0
        return sum(self.question_timings[question_id].values())
    
    def get_phase_averages(self) -> Dict[str, float]:
        """Calculate average time per phase across all questions."""
        if not self.question_timings:
            return {}
        
        phase_totals: Dict[str, float] = {}
        phase_counts: Dict[str, int] = {}
        
        for qid, phases in self.question_timings.items():
            for phase, duration in phases.items():
                phase_totals[phase] = phase_totals.get(phase, 0.0) + duration
                phase_counts[phase] = phase_counts.get(phase, 0) + 1
        
        return {
            phase: phase_totals[phase] / phase_counts[phase]
            for phase in phase_totals
        }
    
    def get_slowest_questions(self, n: int = 3) -> List[tuple]:
        """Get the N slowest questions with their total time and slowest phase."""
        if not self.question_timings:
            return []
        
        results = []
        for qid, phases in self.question_timings.items():
            total = sum(phases.values())
            slowest_phase = max(phases.items(), key=lambda x: x[1])
            results.append((qid, total, slowest_phase[0], slowest_phase[1]))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:n]
    
    def summary(self) -> str:
        """Generate human-readable timing summary."""
        lines = ["", "=== Extraction Timing Summary ==="]
        
        # Paper-level timings
        if self.paper_timings:
            lines.append("Paper-level:")
            for phase, duration in sorted(self.paper_timings.items()):
                lines.append(f"  {phase:25s} {duration:.3f}s")
        
        # Question-level averages
        averages = self.get_phase_averages()
        if averages:
            lines.append("")
            lines.append("Question-level averages:")
            for phase, avg in sorted(averages.items(), key=lambda x: -x[1]):
                lines.append(f"  {phase:25s} {avg:.3f}s")
        
        # Slowest questions
        slowest = self.get_slowest_questions(3)
        if slowest:
            lines.append("")
            lines.append("Slowest questions:")
            for qid, total, slow_phase, slow_duration in slowest:
                lines.append(f"  {qid}: {total:.3f}s ({slow_phase}: {slow_duration:.3f}s)")
        
        lines.append("")
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export timing data as dictionary."""
        return {
            "paper_timings": self.paper_timings,
            "question_timings": self.question_timings,
            "phase_averages": self.get_phase_averages(),
            "slowest_questions": [
                {"id": qid, "total": total, "slowest_phase": phase, "phase_duration": dur}
                for qid, total, phase, dur in self.get_slowest_questions(5)
            ],
        }
    
    def save(self, path: Path, merge: bool = True) -> None:
        """
        Save timing data to JSON file.
        
        PARALLEL SAFE: When merge=True (default), uses file locking to
        merge with existing timing data from other PDF extractions.
        
        Args:
            path: Path to JSON file.
            merge: If True, merge with existing data. If False, overwrite.
        """
        if merge:
            self._save_merged(path)
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, indent=2)
            logger.debug(f"Saved timing data to {path}")
    
    def _save_merged(self, path: Path) -> None:
        """
        Save timing data, merging with existing data using file locking.
        
        This allows multiple parallel PDF extractions to safely contribute
        their timing data to the same file.
        """
        from .file_locking import locked_read_modify_write_json
        
        def merge_timing_data(existing: Dict[str, Any]) -> Dict[str, Any]:
            # Merge paper_timings (update with new values)
            if "paper_timings" not in existing:
                existing["paper_timings"] = {}
            existing["paper_timings"].update(self.paper_timings)
            
            # Merge question_timings (add new questions)
            if "question_timings" not in existing:
                existing["question_timings"] = {}
            existing["question_timings"].update(self.question_timings)
            
            # Recalculate phase_averages from merged data
            phase_totals: Dict[str, float] = {}
            phase_counts: Dict[str, int] = {}
            for q_phases in existing["question_timings"].values():
                for phase, duration in q_phases.items():
                    phase_totals[phase] = phase_totals.get(phase, 0.0) + duration
                    phase_counts[phase] = phase_counts.get(phase, 0) + 1
            existing["phase_averages"] = {
                phase: phase_totals[phase] / phase_counts[phase]
                for phase in phase_totals
            }
            
            # Recalculate slowest_questions from merged data
            results = []
            for qid, phases in existing["question_timings"].items():
                total = sum(phases.values())
                if phases:
                    slowest = max(phases.items(), key=lambda x: x[1])
                    results.append((qid, total, slowest[0], slowest[1]))
            results.sort(key=lambda x: x[1], reverse=True)
            existing["slowest_questions"] = [
                {"id": qid, "total": total, "slowest_phase": phase, "phase_duration": dur}
                for qid, total, phase, dur in results[:5]
            ]
            
            return existing
        
        locked_read_modify_write_json(
            path,
            merge_timing_data,
            default=lambda: {"paper_timings": {}, "question_timings": {}},
        )
        logger.debug(f"Merged timing data to {path}")



@contextmanager
def timed_phase(
    log: TimingLog,
    phase: str,
    question_id: Optional[str] = None,
) -> Generator[None, None, None]:
    """
    Context manager for timing a code phase.
    
    Args:
        log: TimingLog instance to record metrics
        phase: Name of the phase being timed
        question_id: If provided, records as question-level metric;
                    otherwise records as paper-level metric
    
    Example:
        >>> log = TimingLog()
        >>> with timed_phase(log, "numeral_detection"):
        ...     numerals = detect_question_numerals(doc)
        >>> with timed_phase(log, "tree_building", question_id="q1"):
        ...     tree = build_part_tree(...)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        if question_id:
            log.log_question(question_id, phase, elapsed)
        else:
            log.log_paper(phase, elapsed)
