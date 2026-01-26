"""Tests for storage utilities."""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from gcse_toolkit.gui_v2.utils.storage import (
    calculate_directory_size,
    format_size,
    get_storage_info,
)


class TestCalculateDirectorySize:
    """Tests for calculate_directory_size function."""

    def test_empty_directory_returns_zero(self, tmp_path: Path) -> None:
        """Empty directory returns 0."""
        size = calculate_directory_size(tmp_path)
        assert size == 0

    def test_single_file(self, tmp_path: Path) -> None:
        """Correctly calculates size of single file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World!")  # 12 bytes
        
        size = calculate_directory_size(tmp_path)
        assert size == 12

    def test_multiple_files(self, tmp_path: Path) -> None:
        """Correctly sums sizes of multiple files."""
        (tmp_path / "file1.txt").write_text("A" * 100)  # 100 bytes
        (tmp_path / "file2.txt").write_text("B" * 200)  # 200 bytes
        
        size = calculate_directory_size(tmp_path)
        assert size == 300

    def test_nested_directories(self, tmp_path: Path) -> None:
        """Recursively calculates size including subdirectories."""
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file1.txt").write_text("A" * 50)
        (tmp_path / "subdir" / "file2.txt").write_text("B" * 150)
        
        size = calculate_directory_size(tmp_path)
        assert size == 200

    def test_nonexistent_directory_returns_zero(self, tmp_path: Path) -> None:
        """Nonexistent directory returns 0."""
        fake_dir = tmp_path / "does_not_exist"
        size = calculate_directory_size(fake_dir)
        assert size == 0

    def test_ignores_subdirectories_in_count(self, tmp_path: Path) -> None:
        """Only counts file sizes, not directory entries themselves."""
        (tmp_path / "subdir1").mkdir()
        (tmp_path / "subdir2").mkdir()
        (tmp_path / "file.txt").write_text("X" * 10)
        
        size = calculate_directory_size(tmp_path)
        assert size == 10  # Only the file, not directory entries


class TestFormatSize:
    """Tests for format_size function."""

    def test_format_bytes(self) -> None:
        """Formats bytes correctly."""
        assert format_size(0) == "0.0 B"
        assert format_size(512) == "512.0 B"
        assert format_size(1023) == "1023.0 B"

    def test_format_kilobytes(self) -> None:
        """Formats KB correctly."""
        assert format_size(1024) == "1.0 KB"
        assert format_size(1536) == "1.5 KB"
        assert format_size(10240) == "10.0 KB"

    def test_format_megabytes(self) -> None:
        """Formats MB correctly."""
        assert format_size(1024 * 1024) == "1.0 MB"
        assert format_size(int(2.5 * 1024 * 1024)) == "2.5 MB"

    def test_format_gigabytes(self) -> None:
        """Formats GB correctly."""
        assert format_size(1024 * 1024 * 1024) == "1.0 GB"
        assert format_size(int(1.5 * 1024 * 1024 * 1024)) == "1.5 GB"

    def test_format_terabytes(self) -> None:
        """Formats TB correctly."""
        assert format_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"


class TestGetStorageInfo:
    """Tests for get_storage_info function."""

    def test_returns_dict_with_expected_keys(self) -> None:
        """Returns dict with all expected keys."""
        info = get_storage_info()
        
        expected_keys = {
            "slices_cache_bytes",
            "slices_cache_path",
            "input_pdfs_bytes",
            "input_pdfs_path",
            "keyword_cache_bytes",
            "keyword_cache_path",
        }
        
        assert set(info.keys()) == expected_keys

    def test_byte_values_are_integers(self) -> None:
        """All byte values are non-negative integers."""
        info = get_storage_info()
        
        assert isinstance(info["slices_cache_bytes"], int)
        assert isinstance(info["input_pdfs_bytes"], int)
        assert isinstance(info["keyword_cache_bytes"], int)
        
        assert info["slices_cache_bytes"] >= 0
        assert info["input_pdfs_bytes"] >= 0
        assert info["keyword_cache_bytes"] >= 0

    def test_path_values_are_paths(self) -> None:
        """All path values are Path objects."""
        info = get_storage_info()
        
        assert isinstance(info["slices_cache_path"], Path)
        assert isinstance(info["input_pdfs_path"], Path)
        assert isinstance(info["keyword_cache_path"], Path)
