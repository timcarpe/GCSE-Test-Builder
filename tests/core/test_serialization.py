"""
Unit Tests for Serialization Utilities (V2)

Tests for serialization and deserialization functions.
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from gcse_toolkit.core.models.marks import Marks
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.core.models.parts import Part, PartKind
from gcse_toolkit.core.models.questions import Question
from gcse_toolkit.core.utils.serialization import (
    serialize_question,
    deserialize_question,
    serialize_regions,
    deserialize_regions,
    load_questions_jsonl,
    save_questions_jsonl,
    load_regions_json,
    save_regions_json,
)
from gcse_toolkit.core.schemas.validator import ValidationError


class TestQuestionSerialization:
    """Tests for question serialization/deserialization."""
    
    @pytest.fixture
    def sample_question(self) -> Question:
        """Create a sample question for testing."""
        roman1 = Part("1(a)(i)", PartKind.ROMAN, Marks.explicit(2), SliceBounds(100, 150))
        roman2 = Part("1(a)(ii)", PartKind.ROMAN, Marks.explicit(3), SliceBounds(150, 200))
        letter = Part("1(a)", PartKind.LETTER, Marks.aggregate([roman1, roman2]), 
                      SliceBounds(50, 250), children=(roman1, roman2))
        question_node = Part("1", PartKind.QUESTION, Marks.aggregate([letter]),
                            SliceBounds(0, 300), children=(letter,))
        
        return Question(
            id="s21_qp_12_q1",
            exam_code="0478",
            year=2021,
            paper=1,
            variant=2,
            topic="01. Data Representation",
            question_node=question_node,
            composite_path=Path("composite.png"),
            regions_path=Path("regions.json"),
        )
    
    def test_serialize_when_question_given_then_returns_dict(self, sample_question):
        """serialize_question should return a dictionary."""
        result = serialize_question(sample_question)
        
        assert isinstance(result, dict)
        assert result["id"] == "s21_qp_12_q1"
        assert result["exam_code"] == "0478"
        assert "question_node" in result
    
    def test_serialize_when_question_given_then_no_total_marks(self, sample_question):
        """serialize_question should NOT include total_marks."""
        result = serialize_question(sample_question)
        
        assert "total_marks" not in result
    
    def test_deserialize_when_valid_data_then_returns_question(self, sample_question):
        """deserialize_question should recreate the Question."""
        data = serialize_question(sample_question)
        
        restored = deserialize_question(data, validate=True)
        
        assert restored.id == sample_question.id
        assert restored.exam_code == sample_question.exam_code
        assert restored.total_marks == 5  # Calculated, not stored
    
    def test_roundtrip_when_serialized_then_preserves_data(self, sample_question):
        """Serialize/deserialize roundtrip should preserve question data."""
        data = serialize_question(sample_question)
        restored = deserialize_question(data, validate=True)
        
        assert restored.id == sample_question.id
        assert restored.year == sample_question.year
        assert restored.topic == sample_question.topic
        assert len(restored.leaf_parts) == len(sample_question.leaf_parts)


class TestRegionsSerialization:
    """Tests for regions serialization/deserialization."""
    
    def test_serialize_when_regions_given_then_returns_dict(self):
        """serialize_regions should return a dictionary."""
        regions = {
            "1": SliceBounds(0, 300),
            "1(a)": SliceBounds(50, 250),
        }
        
        result = serialize_regions("q1", regions, (800, 1200))
        
        assert isinstance(result, dict)
        assert result["question_id"] == "q1"
        assert result["composite_size"] == {"width": 800, "height": 1200}
        assert "1" in result["regions"]
    
    def test_deserialize_when_valid_data_then_returns_bounds(self):
        """deserialize_regions should return bounds dict."""
        regions = {
            "1": SliceBounds(0, 300),
            "1(a)": SliceBounds(50, 250),
        }
        data = serialize_regions("q1", regions, (800, 1200))
        
        restored, size = deserialize_regions(data, validate=True)
        
        assert len(restored) == 2
        assert "1" in restored
        assert restored["1"].top == 0
        assert restored["1"].bottom == 300
        assert size == (800, 1200)


class TestJSONLOperations:
    """Tests for JSONL file operations."""
    
    @pytest.fixture
    def sample_questions(self) -> list[Question]:
        """Create sample questions for testing."""
        questions = []
        for i in range(3):
            roman = Part(f"{i+1}(a)(i)", PartKind.ROMAN, Marks.explicit(2), SliceBounds(100, 150))
            question_node = Part(f"{i+1}", PartKind.QUESTION, Marks.aggregate([roman]),
                                SliceBounds(0, 200), children=(roman,))
            q = Question(
                id=f"q{i+1}",
                exam_code="0478",
                year=2021,
                paper=1,
                variant=1,
                topic=f"Topic {i+1}",
                question_node=question_node,
                composite_path=Path(f"q{i+1}/composite.png"),
                regions_path=Path(f"q{i+1}/regions.json"),
            )
            questions.append(q)
        return questions
    
    def test_save_load_roundtrip_when_questions_then_preserves_data(self, sample_questions):
        """save/load roundtrip should preserve questions."""
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "questions.jsonl"
            
            save_questions_jsonl(sample_questions, path)
            loaded = load_questions_jsonl(path, validate=True)
            
            assert len(loaded) == 3
            assert loaded[0].id == "q1"
            assert loaded[1].topic == "Topic 2"
            assert loaded[2].total_marks == 2
    
    def test_load_when_file_not_found_then_raises_error(self):
        """load_questions_jsonl should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_questions_jsonl(Path("/nonexistent/path.jsonl"))


class TestRegionsFileOperations:
    """Tests for regions JSON file operations."""
    
    def test_save_load_roundtrip_when_regions_then_preserves_data(self):
        """save/load roundtrip should preserve regions."""
        regions = {
            "1": SliceBounds(0, 300),
            "1(a)": SliceBounds(50, 250),
            "1(a)(i)": SliceBounds(100, 150),
        }
        
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "regions.json"
            
            save_regions_json(path, "q1", regions, (800, 1200))
            loaded = load_regions_json(path, validate=True)
            
            assert len(loaded) == 3
            assert loaded["1"].top == 0
            assert loaded["1(a)(i)"].bottom == 150
