"""
Unit Tests for Schema Validation (V2)

Tests for the validator module.
"""

import pytest

from gcse_toolkit.core.schemas.validator import (
    validate_question,
    validate_regions,
    ValidationError,
    QUESTION_SCHEMA_VERSION,
    REGIONS_SCHEMA_VERSION,
)


class TestValidateQuestion:
    """Tests for validate_question function."""
    
    @pytest.fixture
    def valid_question_data(self) -> dict:
        """Create valid question data for testing."""
        return {
            "id": "s21_qp_12_q1",
            "exam_code": "0478",
            "year": 2021,
            "paper": 1,
            "variant": 1,
            "topic": "01. Data Representation",
            "question_node": {
                "label": "1",
                "kind": "question",
                "marks": 5,
                "mark_source": "aggregate",
                "bounds": {"top": 0, "bottom": 300},
                "children": [
                    {
                        "label": "1(a)",
                        "kind": "letter",
                        "marks": 5,
                        "mark_source": "aggregate",
                        "bounds": {"top": 50, "bottom": 250},
                        "children": [
                            {
                                "label": "1(a)(i)",
                                "kind": "roman",
                                "marks": 2,
                                "mark_source": "explicit",
                                "bounds": {"top": 100, "bottom": 150},
                            },
                            {
                                "label": "1(a)(ii)",
                                "kind": "roman",
                                "marks": 3,
                                "mark_source": "explicit",
                                "bounds": {"top": 150, "bottom": 200},
                            },
                        ],
                    }
                ],
            },
        }
    
    def test_validate_when_valid_data_then_no_error(self, valid_question_data):
        """Valid question data should pass validation."""
        # Should not raise
        validate_question(valid_question_data, strict=False)
    
    def test_validate_when_missing_id_then_raises_error(self, valid_question_data):
        """Missing required field should raise ValidationError."""
        del valid_question_data["id"]
        
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_question(valid_question_data, strict=False)
    
    def test_validate_when_invalid_exam_code_then_raises_error(self, valid_question_data):
        """Invalid exam_code should raise ValidationError."""
        valid_question_data["exam_code"] = "04"  # Too short
        
        with pytest.raises(ValidationError, match="Invalid exam_code"):
            validate_question(valid_question_data, strict=False)
    
    def test_validate_when_exam_code_not_digits_then_raises_error(self, valid_question_data):
        """Non-digit exam_code should raise ValidationError."""
        valid_question_data["exam_code"] = "ABCD"
        
        with pytest.raises(ValidationError, match="Invalid exam_code"):
            validate_question(valid_question_data, strict=False)
    
    def test_validate_when_year_out_of_range_then_raises_error(self, valid_question_data):
        """Year outside valid range should raise ValidationError."""
        valid_question_data["year"] = 1999
        
        with pytest.raises(ValidationError, match="Invalid year"):
            validate_question(valid_question_data, strict=False)
    
    def test_validate_when_invalid_part_kind_then_raises_error(self, valid_question_data):
        """Invalid part kind should raise ValidationError."""
        valid_question_data["question_node"]["kind"] = "invalid"
        
        with pytest.raises(ValidationError, match="Invalid part kind"):
            validate_question(valid_question_data, strict=False)
    
    def test_validate_when_negative_marks_then_raises_error(self, valid_question_data):
        """Negative marks should raise ValidationError."""
        valid_question_data["question_node"]["marks"] = -1
        
        with pytest.raises(ValidationError, match="Invalid marks"):
            validate_question(valid_question_data, strict=False)
    
    def test_validate_when_invalid_bounds_then_raises_error(self, valid_question_data):
        """Invalid bounds should raise ValidationError."""
        valid_question_data["question_node"]["bounds"]["bottom"] = 0  # <= top
        
        with pytest.raises(ValidationError, match="Invalid bottom"):
            validate_question(valid_question_data, strict=False)


class TestValidateRegions:
    """Tests for validate_regions function."""
    
    @pytest.fixture
    def valid_regions_data(self) -> dict:
        """Create valid regions data for testing."""
        return {
            "schema_version": REGIONS_SCHEMA_VERSION,
            "question_id": "s21_qp_12_q1",
            "composite_size": {"width": 800, "height": 1200},
            "regions": {
                "1": {"bounds": {"top": 0, "bottom": 300}},
                "1(a)": {"bounds": {"top": 50, "bottom": 250}},
                "1(a)(i)": {"bounds": {"top": 100, "bottom": 150}},
            },
        }
    
    def test_validate_when_valid_data_then_no_error(self, valid_regions_data):
        """Valid regions data should pass validation."""
        validate_regions(valid_regions_data, strict=False)
    
    def test_validate_when_missing_schema_version_then_raises_error(self, valid_regions_data):
        """Missing schema_version should raise ValidationError."""
        del valid_regions_data["schema_version"]
        
        with pytest.raises(ValidationError, match="Missing required fields"):
            validate_regions(valid_regions_data, strict=False)
    
    def test_validate_when_wrong_schema_version_then_raises_error(self, valid_regions_data):
        """Wrong schema version should raise ValidationError."""
        valid_regions_data["schema_version"] = 999
        
        with pytest.raises(ValidationError, match="Unsupported regions schema version"):
            validate_regions(valid_regions_data, strict=False)
    
    def test_validate_when_invalid_bounds_then_raises_error(self, valid_regions_data):
        """Invalid bounds in regions should raise ValidationError."""
        valid_regions_data["regions"]["1"]["bounds"]["top"] = -1
        
        with pytest.raises(ValidationError, match="Invalid top"):
            validate_regions(valid_regions_data, strict=False)
