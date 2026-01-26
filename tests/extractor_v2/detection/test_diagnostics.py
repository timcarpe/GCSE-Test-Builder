"""
Tests for extractor_v2.diagnostics

Test Coverage:
- DetectionIssue: Dataclass operations and serialization
- DiagnosticsCollector: Thread-safe issue collection
- DetectionDiagnosticsReport: Report generation and JSON output
"""
import json
import pytest
from pathlib import Path

from gcse_toolkit.extractor_v2.diagnostics import (
    DetectionIssue,
    DiagnosticsCollector,
    DetectionDiagnosticsReport,
)


class TestDetectionIssue:
    """Tests for DetectionIssue dataclass."""
    
    def test_to_dict(self):
        """to_dict returns correct structure."""
        issue = DetectionIssue(
            issue_type="letter_gap",
            pdf_name="0450_s25_qp_11.pdf",
            exam_code="0450",
            question_number=2,
            message="Q2: Gap detected",
            y_span=(150, 320),
            prev_label_info="(a) letter @ y=150 bbox:[45,148,58,168]",
            next_label_info="(c) letter @ y=320 bbox:[45,318,58,338]",
        )
        
        d = issue.to_dict()
        
        assert d["issue_type"] == "letter_gap"
        assert d["pdf_name"] == "0450_s25_qp_11.pdf"
        assert d["exam_code"] == "0450"
        assert d["question_number"] == 2
        assert d["y_span"] == [150, 320]
        assert "(a)" in d["prev_label"]
        assert "(c)" in d["next_label"]


class TestDiagnosticsCollector:
    """Tests for DiagnosticsCollector class."""
    
    def test_add_letter_gap(self):
        """add_letter_gap creates correct issue."""
        collector = DiagnosticsCollector()
        
        collector.add_letter_gap(
            pdf_name="0450_s25_qp_11.pdf",
            exam_code="0450",
            question_number=2,
            current_label="a",
            next_label="c",
            missed=["b"],
            y_span=(150, 320),
            prev_y=150,
            prev_bbox=(45, 148, 58, 168),
            next_y=320,
            next_bbox=(45, 318, 58, 338),
        )
        
        assert collector.issue_count == 1
        report = collector.generate_report()
        assert report.total_issues == 1
        assert report.issues[0].issue_type == "letter_gap"
        assert "(a)" in report.issues[0].prev_label_info
        assert "(c)" in report.issues[0].next_label_info
    
    def test_add_roman_gap(self):
        """add_roman_gap creates correct issue."""
        collector = DiagnosticsCollector()
        
        collector.add_roman_gap(
            pdf_name="0580_s25_qp_11.pdf",
            exam_code="0580",
            question_number=3,
            parent_label="3(a)",
            current_roman="i",
            next_roman="iii",
            missed=["ii"],
            y_span=(200, 400),
        )
        
        assert collector.issue_count == 1
        report = collector.generate_report()
        assert report.issues[0].issue_type == "roman_gap"
    
    def test_add_roman_reset(self):
        """add_roman_reset creates correct issue."""
        collector = DiagnosticsCollector()
        
        collector.add_roman_reset(
            pdf_name="0580_s25_qp_11.pdf",
            exam_code="0580",
            question_number=4,
            parent_label="4(a)",
            prev_roman="ii",
            reset_roman="i",
            y_span=(300, 450),
        )
        
        assert collector.issue_count == 1
        report = collector.generate_report()
        assert report.issues[0].issue_type == "roman_reset"
    
    def test_validation_outcome(self):
        """validation_outcome is serialized correctly."""
        collector = DiagnosticsCollector()
        
        collector.add_letter_gap(
            pdf_name="0450_s25_qp_11.pdf",
            exam_code="0450",
            question_number=2,
            current_label="a",
            next_label="c",
            missed=["b"],
            y_span=(150, 320),
        )
        
        # Manually set validation outcome
        report = collector.generate_report()
        report.issues[0].validation_outcome = {
            "2(a)": "VALID",
            "2(b)": "INVALID: Label not detected",
            "2(c)": "VALID",
        }
        
        d = report.issues[0].to_dict()
        assert "validation_outcome" in d
        assert d["validation_outcome"]["2(b)"] == "INVALID: Label not detected"
    
    def test_add_invalid_question(self):
        """add_invalid_question creates correct issue."""
        collector = DiagnosticsCollector()
        
        collector.add_invalid_question(
            pdf_name="0450_s25_qp_11.pdf",
            exam_code="0450",
            question_number=6,
            validation_failures=["No slice bounds calculated"],
        )
        
        assert collector.issue_count == 1
        report = collector.generate_report()
        assert report.issues[0].issue_type == "invalid_question"
    
    def test_summary_by_type(self):
        """generate_report includes summary by issue type."""
        collector = DiagnosticsCollector()
        
        collector.add_letter_gap(
            pdf_name="test.pdf", exam_code="0000", question_number=1,
            current_label="a", next_label="c", missed=["b"], y_span=(0, 100),
        )
        collector.add_letter_gap(
            pdf_name="test.pdf", exam_code="0000", question_number=2,
            current_label="b", next_label="d", missed=["c"], y_span=(100, 200),
        )
        collector.add_roman_reset(
            pdf_name="test.pdf", exam_code="0000", question_number=3,
            parent_label="3(a)", prev_roman="ii", reset_roman="i", y_span=(200, 300),
        )
        
        report = collector.generate_report()
        
        assert report.summary_by_type["letter_gap"] == 2
        assert report.summary_by_type["roman_reset"] == 1


class TestDetectionDiagnosticsReport:
    """Tests for DetectionDiagnosticsReport class."""
    
    def test_to_json(self):
        """to_json produces valid JSON."""
        collector = DiagnosticsCollector()
        collector.add_letter_gap(
            pdf_name="test.pdf", exam_code="0000", question_number=1,
            current_label="a", next_label="c", missed=["b"], y_span=(0, 100),
        )
        
        report = collector.generate_report()
        json_str = report.to_json()
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        
        assert "generated_at" in parsed
        assert parsed["total_issues"] == 1
        assert len(parsed["issues"]) == 1
    
    def test_save(self, tmp_path: Path):
        """save writes JSON file to disk."""
        collector = DiagnosticsCollector()
        collector.add_letter_gap(
            pdf_name="test.pdf", exam_code="0000", question_number=1,
            current_label="a", next_label="c", missed=["b"], y_span=(0, 100),
        )
        
        report = collector.generate_report()
        report_path = tmp_path / "diagnostics" / "detection_diagnostics.json"
        report.save(report_path)
        
        assert report_path.exists()
        
        with open(report_path) as f:
            loaded = json.load(f)
        
        assert loaded["total_issues"] == 1
