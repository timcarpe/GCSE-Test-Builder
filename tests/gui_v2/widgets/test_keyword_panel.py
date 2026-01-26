"""Unit tests for KeywordPanel Enter key behavior."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit
from unittest.mock import patch, MagicMock

from gcse_toolkit.gui_v2.widgets.keyword_panel import KeywordPanel
from gcse_toolkit.gui_v2.widgets.console_widget import ConsoleWidget


@pytest.fixture
def keyword_panel(qtbot, tmp_path):
    """Create a KeywordPanel instance for testing."""
    console = ConsoleWidget()
    panel = KeywordPanel(console)
    qtbot.addWidget(panel)
    panel.show()
    
    # Set up minimal context to avoid errors in _on_preview_clicked
    panel.current_exam = "test_exam"
    panel.metadata_root = tmp_path
    
    return panel


class TestEnterKeyTriggersSearch:
    """Tests for Enter key search triggering."""

    def test_enter_key_connected(self, keyword_panel):
        """Each keyword entry should have returnPressed connected."""
        for row in keyword_panel.keyword_rows:
            entry = row["entry"]
            # Check that returnPressed signal has at least one receiver
            # PySide6 requires SIGNAL() string format for receivers()
            receivers = entry.receivers("2returnPressed()")
            assert receivers > 0, "returnPressed signal should have a receiver"

    def test_enter_triggers_preview(self, keyword_panel, qtbot):
        """Pressing Enter in keyword field should trigger preview."""
        with patch.object(keyword_panel, '_on_preview_clicked') as mock_preview:
            # Get the first keyword entry
            entry = keyword_panel.keyword_rows[0]["entry"]
            entry.setFocus()
            entry.setText("test keyword")
            
            # Simulate Enter key press
            QTest.keyClick(entry, Qt.Key_Return)
            
            # Verify preview was triggered
            mock_preview.assert_called_once()

    def test_enter_on_empty_field_still_triggers(self, keyword_panel, qtbot):
        """Enter on empty field should still attempt preview (validation in _on_preview_clicked)."""
        with patch.object(keyword_panel, '_on_preview_clicked') as mock_preview:
            entry = keyword_panel.keyword_rows[0]["entry"]
            entry.clear()
            
            QTest.keyClick(entry, Qt.Key_Return)
            
            # Should still trigger (method handles empty validation)
            mock_preview.assert_called_once()

    def test_multiple_rows_all_support_enter(self, keyword_panel, qtbot):
        """All keyword rows should support Enter to search."""
        # Add more rows
        keyword_panel._add_keyword_row("keyword2")
        keyword_panel._add_keyword_row("keyword3")
        
        with patch.object(keyword_panel, '_on_preview_clicked') as mock_preview:
            # Press Enter on each row
            for row in keyword_panel.keyword_rows:
                entry = row["entry"]
                QTest.keyClick(entry, Qt.Key_Return)
            
            # Should be called once per row
            assert mock_preview.call_count == 3
