"""
Unit tests for zip_writer.py.
"""

import zipfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
from io import BytesIO

from gcse_toolkit.core.models.marks import Marks
from gcse_toolkit.core.models.bounds import SliceBounds
from gcse_toolkit.core.models.parts import Part, PartKind
from gcse_toolkit.core.models.questions import Question
from gcse_toolkit.core.models.selection import SelectionPlan, SelectionResult
from gcse_toolkit.builder_v2.output.zip_writer import (
    write_questions_zip,
    _sanitize_filename,
    _generate_readme,
)


def make_test_question(qid: str, labels: list[str]) -> Question:
    """Helper to create a test question with specific part labels."""
    # We need to build a valid tree or SelectionPlan will reject it
    # For testing filenames, we can just make them all children of the root
    root_label = labels[0]
    children = []
    for label in labels[1:]:
        children.append(
            Part(
                label,
                PartKind.LETTER,
                Marks.explicit(1),
                SliceBounds(50, 100)
            )
        )
    
    question_node = Part(
        root_label,
        PartKind.QUESTION,
        Marks.aggregate(children) if children else Marks.explicit(1),
        SliceBounds(0, 100),
        children=tuple(children)
    )
    
    return Question(
        id=qid,
        exam_code="0478",
        year=2021,
        paper=1,
        variant=1,
        topic="Test",
        question_node=question_node,
        composite_path=Path("/test/composite.png"),
        regions_path=Path("/test/regions.json"),
    )


class TestZipWriter:
    """Tests for ZIP export functionality."""

    def test_sanitize_filename(self):
        """Should return compact labels as requested."""
        assert _sanitize_filename("1") == "1"
        assert _sanitize_filename("1(a)") == "1(a)"
        assert _sanitize_filename("1(a)(i)") == "1(a)(i)"
        assert _sanitize_filename("3(b)(ii)") == "3(b)(ii)"

    def test_generate_readme(self):
        """Should generate a README with question details."""
        q1 = make_test_question("q1", ["1", "1(a)"])
        plan = SelectionPlan(q1, included_parts=frozenset(["1", "1(a)"]))
        result = SelectionResult((plan,), target_marks=10, tolerance=2)
        
        readme = _generate_readme(result)
        assert "Total Marks: 1" in readme  # Only leaf 1(a) has marks in our helper
        assert "q1" in readme
        assert "Parts: 1, 1(a)" in readme

    @patch("gcse_toolkit.builder_v2.output.zip_writer.create_provider_for_question")
    def test_write_questions_zip(self, mock_create_provider, tmp_path):
        """Should create a ZIP with correct folder and file structure."""
        # Arrange
        q1 = make_test_question("q1", ["1", "1(a)"])
        plan = SelectionPlan(q1, included_parts=frozenset(["1", "1(a)"]))
        result = SelectionResult((plan,), target_marks=10, tolerance=2)
        
        output_zip = tmp_path / "questions.zip"
        
        # Mock provider
        mock_provider = MagicMock()
        mock_provider.available_labels = ["1", "1(a)"]
        # Return a small test image
        test_img = Image.new("RGB", (10, 10), color="red")
        mock_provider.get_slice.return_value = test_img
        
        # Mock __enter__ and __exit__ for context manager
        mock_create_provider.return_value.__enter__.return_value = mock_provider
        
        # Act
        write_questions_zip(result, output_zip)
        
        # Assert
        assert output_zip.exists()
        with zipfile.ZipFile(output_zip, "r") as zf:
            names = zf.namelist()
            assert "README.txt" in names
            assert "1/1.png" in names
            assert "1/1(a).png" in names
            
            # Verify image content (optional, just check it's not empty)
            with zf.open("1/1.png") as f:
                img = Image.open(f)
                assert img.size == (10, 10)

    @patch("gcse_toolkit.builder_v2.output.zip_writer.create_provider_for_question")
    def test_selection_order_determines_folder_name(self, mock_create_provider, tmp_path):
        """Folders should be 1/, 2/ based on order in SelectionResult."""
        # Arrange
        q_a = make_test_question("qa", ["5"])
        q_b = make_test_question("qb", ["3"])
        
        plan_1 = SelectionPlan(q_a, included_parts=frozenset(["5"]))
        plan_2 = SelectionPlan(q_b, included_parts=frozenset(["3"]))
        
        # Order is qa then qb
        result = SelectionResult((plan_1, plan_2), target_marks=2, tolerance=0)
        
        output_zip = tmp_path / "ordered.zip"
        
        mock_provider = MagicMock()
        mock_provider.available_labels = ["5", "3"]
        mock_provider.get_slice.return_value = Image.new("RGB", (1, 1))
        mock_create_provider.return_value.__enter__.return_value = mock_provider
        
        # Act
        write_questions_zip(result, output_zip)
        
        # Assert
        with zipfile.ZipFile(output_zip, "r") as zf:
            names = zf.namelist()
            # qa is first -> folder 1/
            assert "1/5.png" in names
            # qb is second -> folder 2/
            assert "2/3.png" in names
