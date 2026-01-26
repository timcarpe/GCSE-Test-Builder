"""
Unit tests for gcse_toolkit.gui_v2.utils.helpers module.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestScanExamSources:
    """Tests for scan_exam_sources function."""
    
    def test_valid_filenames_categorized_correctly(self, tmp_path):
        """Valid exam PDFs should be categorized as supported or unsupported."""
        from gcse_toolkit.gui_v2.utils.helpers import scan_exam_sources
        
        # Create test PDFs with valid naming patterns
        (tmp_path / "0450_s24_qp_12.pdf").touch()
        (tmp_path / "0450_s24_ms_12.pdf").touch()
        (tmp_path / "9999_w23_qp_11.pdf").touch()  # Valid pattern but unsupported code
        
        supported_codes = {"0450"}
        
        with patch("gcse_toolkit.extractor_v2.utils.exam_code") as mock_detect:
            # Mock exam code detection from PDF
            def detect_code(pdf):
                return pdf.stem.split("_")[0]
            mock_detect.side_effect = detect_code
            
            supported, unsupported, invalid = scan_exam_sources(tmp_path, supported_codes)
        
        # Verify categorization
        assert "0450" in supported
        assert len(supported["0450"]) == 1  # QP included, MS explicitly skipped now
        assert "9999" in unsupported
        assert len(unsupported["9999"]) == 1
        assert len(invalid) == 0
    
    def test_malformed_filenames_added_to_invalid_list(self, tmp_path):
        """Files with unexpected naming patterns should be in invalid list."""
        from gcse_toolkit.gui_v2.utils.helpers import scan_exam_sources
        
        # Create test PDFs with INVALID naming patterns
        (tmp_path / "random_document.pdf").touch()
        (tmp_path / "notes.pdf").touch()
        (tmp_path / "0450.pdf").touch()  # Missing series/type/variant
        (tmp_path / "exam_paper_2024.pdf").touch()
        (tmp_path / "0450_qp_12.pdf").touch()  # Missing series (needs 3-char series)
        
        supported_codes = {"0450", "0478"}
        
        supported, unsupported, invalid = scan_exam_sources(tmp_path, supported_codes)
        
        # All these malformed files should be in invalid list
        assert len(invalid) == 5
        assert len(supported) == 0
        assert len(unsupported) == 0
        
        # Verify the invalid filenames
        invalid_names = {p.name for p in invalid}
        assert "random_document.pdf" in invalid_names
        assert "notes.pdf" in invalid_names
        assert "0450.pdf" in invalid_names
        assert "exam_paper_2024.pdf" in invalid_names
        assert "0450_qp_12.pdf" in invalid_names
    
    def test_mixed_valid_and_invalid_files(self, tmp_path):
        """Mix of valid and invalid files should be correctly separated."""
        from gcse_toolkit.gui_v2.utils.helpers import scan_exam_sources
        
        # Valid files
        (tmp_path / "0450_s24_qp_12.pdf").touch()
        (tmp_path / "0478_w23_ms_11.pdf").touch()
        
        # Invalid files
        (tmp_path / "readme.pdf").touch()
        (tmp_path / "old_exam.pdf").touch()
        
        supported_codes = {"0450", "0478"}
        
        with patch("gcse_toolkit.extractor_v2.utils.exam_code") as mock_detect:
            def detect_code(pdf):
                return pdf.stem.split("_")[0]
            mock_detect.side_effect = detect_code
            
            supported, unsupported, invalid = scan_exam_sources(tmp_path, supported_codes)
        
        # Valid files categorized
        assert "0450" in supported
        assert "0478" not in supported  # 0478 was MS, so it should be skipped
        
        # Invalid files captured
        assert len(invalid) == 2
        invalid_names = {p.name for p in invalid}
        assert "readme.pdf" in invalid_names
        assert "old_exam.pdf" in invalid_names
    
    def test_empty_directory_returns_empty_results(self, tmp_path):
        """Empty directory should return empty results without errors."""
        from gcse_toolkit.gui_v2.utils.helpers import scan_exam_sources
        
        supported_codes = {"0450"}
        supported, unsupported, invalid = scan_exam_sources(tmp_path, supported_codes)
        
        assert len(supported) == 0
        assert len(unsupported) == 0
        assert len(invalid) == 0
    
    def test_nonexistent_directory_returns_empty_results(self):
        """Non-existent directory should return empty results without errors."""
        from gcse_toolkit.gui_v2.utils.helpers import scan_exam_sources
        
        fake_path = Path("/nonexistent/path/to/exams")
        supported_codes = {"0450"}
        
        supported, unsupported, invalid = scan_exam_sources(fake_path, supported_codes)
        
        assert len(supported) == 0
        assert len(unsupported) == 0
        assert len(invalid) == 0
    
    def test_case_insensitive_pattern_matching(self, tmp_path):
        """Pattern matching should be case-insensitive for qp/QP and ms/MS."""
        from gcse_toolkit.gui_v2.utils.helpers import scan_exam_sources
        
        # Mixed case filenames (all valid patterns)
        (tmp_path / "0450_s24_QP_12.pdf").touch()
        (tmp_path / "0450_s24_MS_12.pdf").touch()
        (tmp_path / "0450_w23_Qp_11.pdf").touch()  # Mixed case
        
        supported_codes = {"0450"}
        
        with patch("gcse_toolkit.extractor_v2.utils.exam_code") as mock_detect:
            mock_detect.return_value = "0450"
            supported, unsupported, invalid = scan_exam_sources(tmp_path, supported_codes)
        
        # All should be valid (case insensitive matching)
        assert len(invalid) == 0
        assert "0450" in supported
        assert len(supported["0450"]) == 2  # QP and Qp included, MS skipped
    
    def test_subdirectory_scanning(self, tmp_path):
        """Should recursively scan subdirectories."""
        from gcse_toolkit.gui_v2.utils.helpers import scan_exam_sources
        
        # Create subdirectory structure
        subdir = tmp_path / "2024" / "summer"
        subdir.mkdir(parents=True)
        
        (subdir / "0450_s24_qp_12.pdf").touch()
        (tmp_path / "0450_w23_qp_11.pdf").touch()
        
        supported_codes = {"0450"}
        
        with patch("gcse_toolkit.extractor_v2.utils.exam_code") as mock_detect:
            mock_detect.return_value = "0450"
            supported, unsupported, invalid = scan_exam_sources(tmp_path, supported_codes)
        
        # Should find both PDFs
        assert "0450" in supported
        assert len(supported["0450"]) == 2


class TestDiscoverYears:
    """Tests for discover_years_for_exam function."""
    
    def test_years_extracted_from_metadata(self, tmp_path):
        """Should find unique years in questions.jsonl."""
        from gcse_toolkit.gui_v2.utils.helpers import discover_years_for_exam
        import json
        
        # Setup metadata structure
        exam_dir = tmp_path / "0450"
        meta_dir = exam_dir / "_metadata"
        meta_dir.mkdir(parents=True)
        
        # Create dummy questions.jsonl with year fields
        questions = [
            {"id": "q1", "year": "2023", "mark": 5},
            {"id": "q2", "year": "2024", "mark": 4},
            {"id": "q3", "year": "2023", "mark": 3},  # Duplicate year
            {"id": "q4", "mark": 2},  # Missing year
            {"id": "q5", "year": None},  # Null year
        ]
        
        with open(meta_dir / "questions.jsonl", "w", encoding="utf-8") as f:
            for q in questions:
                f.write(json.dumps(q) + "\n")
                
        years = discover_years_for_exam("0450", tmp_path)
        
        assert years == ["2023", "2024"]
        
    def test_missing_metadata_returns_empty(self, tmp_path):
        """Should return empty list if metadata file missing."""
        from gcse_toolkit.gui_v2.utils.helpers import discover_years_for_exam
        
        years = discover_years_for_exam("0450", tmp_path)
        assert years == []

    def test_malformed_json_lines_skipped(self, tmp_path):
        """Should skip lines that aren't valid JSON."""
        from gcse_toolkit.gui_v2.utils.helpers import discover_years_for_exam
        import json

        exam_dir = tmp_path / "0450"
        meta_dir = exam_dir / "_metadata"
        meta_dir.mkdir(parents=True)
        
        with open(meta_dir / "questions.jsonl", "w", encoding="utf-8") as f:
            f.write('{"year": "2023"}\n')
            f.write('NOT JSON\n')
            f.write('{"year": "2024"}\n')
            
        years = discover_years_for_exam("0450", tmp_path)
        assert years == ["2023", "2024"]


class TestCheckMetadataVersions:
    """Tests for check_metadata_versions function."""
    
    def test_identifies_outdated_versions(self, tmp_path):
        """Should return dictionary of exams with old schema versions."""
        from gcse_toolkit.gui_v2.utils.helpers import check_metadata_versions
        from gcse_toolkit.core.schemas.validator import QUESTION_SCHEMA_VERSION
        import json
        
        # Setup structure with mix of versions
        
        # Outdated (Version 5)
        d1 = tmp_path / "0001" / "_metadata"
        d1.mkdir(parents=True)
        with open(d1 / "questions.jsonl", "w") as f:
            f.write(json.dumps({"_schema_version": 5}) + "\n")
            
        # Current Version
        d2 = tmp_path / "0002" / "_metadata"
        d2.mkdir(parents=True)
        with open(d2 / "questions.jsonl", "w") as f:
            f.write(json.dumps({"schema_version": QUESTION_SCHEMA_VERSION}) + "\n")
            
        # Very Old (Version 1)
        d3 = tmp_path / "0003" / "_metadata"
        d3.mkdir(parents=True)
        with open(d3 / "questions.jsonl", "w") as f:
            f.write(json.dumps({"_schema_version": 1}) + "\n")
            
        # No version key (defaults to 1)
        d4 = tmp_path / "0004" / "_metadata"
        d4.mkdir(parents=True)
        with open(d4 / "questions.jsonl", "w") as f:
            f.write(json.dumps({"id": "q1"}) + "\n")

        # Future Version (Should be ignored as per policy "newer is accepted")
        d5 = tmp_path / "0005" / "_metadata"
        d5.mkdir(parents=True)
        with open(d5 / "questions.jsonl", "w") as f:
            f.write(json.dumps({"schema_version": QUESTION_SCHEMA_VERSION + 1}) + "\n")
            
        outdated = check_metadata_versions(tmp_path)
        
        assert "0001" in outdated
        assert outdated["0001"] == 5
        
        assert "0002" not in outdated
        
        assert "0003" in outdated
        assert outdated["0003"] == 1
        
        assert "0004" in outdated
        assert outdated["0004"] == 1
        
        assert "0005" not in outdated

    def test_handles_empty_or_corrupt_files(self, tmp_path):
        """Should handle empty or corrupt metadata files gracefully."""
        from gcse_toolkit.gui_v2.utils.helpers import check_metadata_versions
        
        # Empty file
        d1 = tmp_path / "0001" / "_metadata"
        d1.mkdir(parents=True)
        (d1 / "questions.jsonl").touch()
        
        # Corrupt file
        d2 = tmp_path / "0002" / "_metadata"
        d2.mkdir(parents=True)
        with open(d2 / "questions.jsonl", "w") as f:
            f.write("NOT JSON")
            
        outdated = check_metadata_versions(tmp_path)
        
        # Empty file check reads line -> empty string -> not updated
        assert "0001" not in outdated 
        
        # Corrupt file -> JSONDecodeError -> outdated[code] = 0
        assert "0002" in outdated
        assert outdated["0002"] == 0
