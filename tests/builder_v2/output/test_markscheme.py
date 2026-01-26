"""
Unit tests for markscheme output generation.

Includes regression tests for correct file pattern recognition (Phase 6.8 fix).
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from gcse_toolkit.builder_v2.output.markscheme import render_markscheme
from gcse_toolkit.core.models.selection import SelectionResult, SelectionPlan
from gcse_toolkit.core.models import Question


@pytest.fixture
def mock_selection(tmp_path):
    """Create a mock selection result."""
    q = MagicMock(spec=Question)
    q.id = "q1"
    q.composite_path = tmp_path / "cache" / "q1" / "composite.png"
    q.mark_scheme_path = "q1_ms.png"
    
    plan = MagicMock(spec=SelectionPlan)
    plan.question = q
    
    result = MagicMock(spec=SelectionResult)
    result.plans = [plan]
    return result


@patch("reportlab.pdfgen.canvas.Canvas")
@patch("reportlab.lib.utils.ImageReader")
@patch("PIL.Image.open")
def test_render_markscheme_when_files_match_pattern_then_includes_them(
    mock_image_open,
    mock_image_reader_cls,
    mock_canvas_cls,
    mock_selection,
    tmp_path
):
    """
    Regression Test: specific verification that *_ms.png files are found.
    Previous bug: looked for markscheme_page_*.png
    """
    # Arrange
    cache_path = tmp_path / "cache"
    output_path = tmp_path / "output.pdf"
    
    # Create question directory
    q_dir = cache_path / "q1"
    q_dir.mkdir(parents=True)
    
    # Create valid markscheme file (New Pattern)
    ms_file = q_dir / "q1_ms.png"
    ms_file.touch()
    
    # Create INVALID file (Old Pattern) to ensure it's NOT picking up garbage
    invalid_file = q_dir / "markscheme_page_0.png"
    invalid_file.touch()
    
    # Mock image (return dummy size)
    mock_img = MagicMock()
    mock_img.size = (100, 100)
    mock_image_open.return_value = mock_img
    
    # Mock canvas instance
    mock_canvas = mock_canvas_cls.return_value
    
    # Act
    render_markscheme(mock_selection, output_path, cache_path)
    
    # Assert
    # Verify Image.open was called with the correct file
    mock_image_open.assert_called_with(ms_file)
    
    # Verify drawImage was called (meaning it processed the file)
    assert mock_canvas.drawImage.call_count == 1
    
    # Ensure it didn't try to open the invalid file
    # We can check verify all calls to image_open
    open_args = [c.args[0] for c in mock_image_open.call_args_list]
    assert ms_file in open_args
    assert invalid_file not in open_args


@patch("reportlab.pdfgen.canvas.Canvas")
def test_render_markscheme_when_no_files_found_then_logs_warning(
    mock_canvas_cls,
    mock_selection,
    tmp_path,
    caplog
):
    """Verify behavior when no markscheme files exist."""
    import logging
    caplog.set_level(logging.DEBUG)
    
    cache_path = tmp_path / "cache"
    output_path = tmp_path / "output.pdf"
    cache_path.mkdir() # No q1 dir
    
    render_markscheme(mock_selection, output_path, cache_path)
    
    assert "Markscheme image missing for q1" in caplog.text
