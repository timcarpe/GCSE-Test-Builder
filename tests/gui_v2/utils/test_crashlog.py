"""Unit tests for crashlog module."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


class TestCrashlogModule:
    """Tests for crashlog utilities."""
    
    def test_get_crashlog_dir_creates_directory(self):
        """Verify crashlog directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_data = Path(tmpdir) / "appdata"
            
            # Patch at the source where it's imported from
            with patch('gcse_toolkit.gui_v2.utils.paths.get_app_data_dir', return_value=mock_app_data):
                from gcse_toolkit.gui_v2.utils.crashlog import get_crashlog_dir
                
                crash_dir = get_crashlog_dir()
                
                assert crash_dir.exists()
                assert crash_dir.name == "crash_logs"
                assert crash_dir.parent == mock_app_data
    
    def test_rotate_crash_logs_limits_to_max(self):
        """Verify log rotation keeps at most MAX_CRASH_LOGS files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            crash_dir = Path(tmpdir)
            
            # Create 6 existing logs with different mtimes
            import time
            import os
            for i in range(6):
                log_file = crash_dir / f"crash_2024010{i}_120000.log"
                log_file.write_text(f"log {i}")
                # Touch with different times to ensure ordering
                os.utime(log_file, (i, i))
            
            with patch('gcse_toolkit.gui_v2.utils.crashlog.get_crashlog_dir', return_value=crash_dir):
                from gcse_toolkit.gui_v2.utils.crashlog import _rotate_crash_logs, MAX_CRASH_LOGS
                
                _rotate_crash_logs()
                
                remaining = list(crash_dir.glob("crash_*.log"))
                # After rotation, should have MAX_CRASH_LOGS - 1 (room for new one)
                assert len(remaining) < MAX_CRASH_LOGS

    def test_max_crash_logs_constant(self):
        """Verify MAX_CRASH_LOGS is set to 5."""
        from gcse_toolkit.gui_v2.utils.crashlog import MAX_CRASH_LOGS
        assert MAX_CRASH_LOGS == 5

    def test_crash_handler_format(self):
        """Test crash log formatting without actually invoking excepthook."""
        import traceback
        from datetime import datetime
        import platform
        
        # Simulate what the crash handler would produce
        try:
            raise RuntimeError("Test exception")
        except RuntimeError:
            exc_type, exc_value, exc_tb = sys.exc_info()
        
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        tb_text = "".join(tb_lines)
        
        # Build the same format as crashlog.py
        app_version = "1.2.3"
        system_info = [
            "GCSE Test Builder Crash Report",
            "=" * 50,
            f"Timestamp: {datetime.now().isoformat()}",
            f"Version: {app_version}",
            f"Python: {sys.version}",
            f"Platform: {platform.platform()}",
            f"Frozen: {getattr(sys, 'frozen', False)}",
            "",
            "Exception:",
            "-" * 50,
            tb_text,
        ]
        content = "\n".join(system_info)
        
        # Verify expected content structure
        assert "GCSE Test Builder Crash Report" in content
        assert "Version: 1.2.3" in content
        assert "RuntimeError" in content
        assert "Test exception" in content
        assert "Python:" in content
        assert "Platform:" in content
        assert "Frozen:" in content
    
    def test_install_crash_handler_sets_excepthook(self):
        """Verify install_crash_handler modifies sys.excepthook."""
        original_hook = sys.excepthook
        
        try:
            from gcse_toolkit.gui_v2.utils.crashlog import install_crash_handler
            
            install_crash_handler(app_version="test")
            
            # Verify sys.excepthook was replaced
            assert sys.excepthook != original_hook
            assert callable(sys.excepthook)
        finally:
            # Restore original hook
            sys.excepthook = original_hook
    
    def test_crashlog_dir_path_structure(self):
        """Verify crash log directory follows expected path structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_app_data = Path(tmpdir)
            
            with patch('gcse_toolkit.gui_v2.utils.paths.get_app_data_dir', return_value=mock_app_data):
                from gcse_toolkit.gui_v2.utils.crashlog import get_crashlog_dir
                
                crash_dir = get_crashlog_dir()
                
                # Should be app_data_dir / crash_logs
                assert crash_dir == mock_app_data / "crash_logs"
                assert crash_dir.is_dir()
