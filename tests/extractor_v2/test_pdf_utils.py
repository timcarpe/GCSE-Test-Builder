"""
Tests for extractor_v2.utils.pdf module.

Verified: 2025-12-12
Source: extractor/v2/question_extractor.py (lines 294-301, 303-308, 417-438)
"""

import pytest
import numpy as np
from PIL import Image
from unittest.mock import Mock
import io


class TestRenderPageRegion:
    """Tests for render_page_region() function."""

    def test_render_page_region_when_valid_clip_then_returns_image(self):
        """Should render clipped region as grayscale image."""
        # Arrange
        from gcse_toolkit.extractor_v2.utils.pdf import render_page_region
        import fitz
        
        # Create a minimal test image (white background)
        test_img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        img_bytes = io.BytesIO()
        test_img.save(img_bytes, format="PNG")
        
        mock_page = Mock()
        mock_pixmap = Mock()
        mock_pixmap.width = 100
        mock_pixmap.height = 100
        mock_pixmap.samples = bytes([255] * 100 * 100) # White grayscale
        mock_page.get_pixmap.return_value = mock_pixmap
        
        clip = fitz.Rect(0, 0, 100, 100)
        
        # Act
        image, offset = render_page_region(mock_page, clip, dpi=72)
        
        # Assert
        assert isinstance(image, Image.Image)
        assert image.mode == "L"  # Grayscale
        assert offset == (0, 0)  # No trim for all-white image

    def test_render_page_region_when_zero_width_then_raises_error(self):
        """Should raise ValueError for zero-width clip."""
        # Arrange
        from gcse_toolkit.extractor_v2.utils.pdf import render_page_region
        import fitz
        
        mock_page = Mock()
        clip = fitz.Rect(50, 0, 50, 100)  # Zero width
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid clip"):
            render_page_region(mock_page, clip)

    def test_render_page_region_when_no_trim_then_preserves_size(self):
        """Should preserve full size when trim_whitespace=False."""
        # Arrange
        from gcse_toolkit.extractor_v2.utils.pdf import render_page_region
        import fitz
        
        test_img = Image.new("RGB", (200, 150), color=(255, 255, 255))
        img_bytes = io.BytesIO()
        test_img.save(img_bytes, format="PNG")
        
        mock_page = Mock()
        mock_pixmap = Mock()
        mock_pixmap.width = 200
        mock_pixmap.height = 150
        mock_pixmap.samples = bytes([255] * 200 * 150)
        mock_page.get_pixmap.return_value = mock_pixmap
        
        clip = fitz.Rect(0, 0, 200, 150)
        
        # Act
        image, offset = render_page_region(mock_page, clip, trim_whitespace=False)
        
        # Assert
        assert image.size == (200, 150)
        assert offset == (0, 0)


class TestExtractText:
    """Tests for extract_text() function."""

    def test_extract_text_when_valid_page_then_returns_text(self):
        """Should extract text from page."""
        # Arrange
        from gcse_toolkit.extractor_v2.utils.pdf import extract_text
        
        mock_page = Mock()
        mock_page.get_text.return_value = "1 (a) Sample question text"
        
        # Act
        result = extract_text(mock_page)
        
        # Assert
        assert result == "1 (a) Sample question text"
        mock_page.get_text.assert_called_once_with("text")

    def test_extract_text_when_with_clip_then_respects_clip(self):
        """Should pass clip to get_text."""
        # Arrange
        from gcse_toolkit.extractor_v2.utils.pdf import extract_text
        import fitz
        
        mock_page = Mock()
        mock_page.get_text.return_value = "Clipped text"
        clip = fitz.Rect(0, 100, 300, 200)
        
        # Act
        result = extract_text(mock_page, clip=clip)
        
        # Assert
        assert result == "Clipped text"
        mock_page.get_text.assert_called_once_with("text", clip=clip)

    def test_extract_text_when_error_then_returns_empty(self):
        """Should return empty string on error."""
        # Arrange
        from gcse_toolkit.extractor_v2.utils.pdf import extract_text
        
        mock_page = Mock()
        mock_page.get_text.side_effect = RuntimeError("PDF error")
        
        # Act
        result = extract_text(mock_page)
        
        # Assert
        assert result == ""


class TestGetPageDimensions:
    """Tests for get_page_dimensions() function."""

    def test_get_page_dimensions_when_72dpi_then_matches_points(self):
        """At 72 DPI, dimensions should match PDF points."""
        # Arrange
        from gcse_toolkit.extractor_v2.utils.pdf import get_page_dimensions
        import fitz
        
        mock_page = Mock()
        mock_page.rect = fitz.Rect(0, 0, 595, 842)  # A4 in points
        
        # Act
        width, height = get_page_dimensions(mock_page, dpi=72)
        
        # Assert
        assert width == 595
        assert height == 842

    def test_get_page_dimensions_when_200dpi_then_scales_correctly(self):
        """At 200 DPI, dimensions should scale by 200/72."""
        # Arrange
        from gcse_toolkit.extractor_v2.utils.pdf import get_page_dimensions
        import fitz
        
        mock_page = Mock()
        mock_page.rect = fitz.Rect(0, 0, 595, 842)
        
        # Act
        width, height = get_page_dimensions(mock_page, dpi=200)
        
        # Assert
        expected_width = int(595 * 200 / 72)
        expected_height = int(842 * 200 / 72)
        assert width == expected_width
        assert height == expected_height


class TestTrimWhitespace:
    """Tests for _trim_whitespace() private function."""

    def test_trim_whitespace_when_content_centered_then_crops_margins(self):
        """Should crop white margins around content."""
        # Arrange
        from gcse_toolkit.extractor_v2.utils.pdf import _trim_whitespace
        
        # Create image with black content in center
        img = Image.new("L", (100, 100), color=255)
        arr = np.array(img)
        arr[40:60, 40:60] = 0  # Black square in center
        img = Image.fromarray(arr)
        
        # Act
        cropped, offset = _trim_whitespace(img, padding=5)
        
        # Assert
        # Height should be cropped (width may not be due to min_crop_width_ratio)
        assert cropped.height < 100  # Should be cropped vertically
        assert offset[1] > 0  # Top offset should be non-zero

    def test_trim_whitespace_when_all_white_then_returns_original(self):
        """Should return original when no content detected."""
        # Arrange
        from gcse_toolkit.extractor_v2.utils.pdf import _trim_whitespace
        
        img = Image.new("L", (100, 100), color=255)
        
        # Act
        result, offset = _trim_whitespace(img)
        
        # Assert
        assert result.size == img.size
        assert offset == (0, 0)

    def test_trim_whitespace_when_rgb_then_returns_original(self):
        """Should return original for non-grayscale images."""
        # Arrange
        from gcse_toolkit.extractor_v2.utils.pdf import _trim_whitespace
        
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        
        # Act
        result, offset = _trim_whitespace(img)
        
        # Assert  
        assert result.size == img.size
        assert offset == (0, 0)
