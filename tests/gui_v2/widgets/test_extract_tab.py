"""Unit tests for ExtractTab UI elements."""

import pytest
from PySide6.QtWidgets import QApplication
from gcse_toolkit.gui_v2.widgets.extract_tab import ExtractTab
from gcse_toolkit.gui_v2.widgets.build_tab import BuildTab
from gcse_toolkit.gui_v2.widgets.console_widget import ConsoleWidget
from gcse_toolkit.gui_v2.models.settings import SettingsStore
import queue


@pytest.fixture
def extract_tab(qtbot, tmp_path):
    """Create an ExtractTab instance for testing."""
    console = ConsoleWidget()
    settings = SettingsStore(tmp_path / "test_settings.json")
    log_queue = queue.Queue()
    
    tab = ExtractTab(console, settings, log_queue)
    qtbot.addWidget(tab)
    tab.show()
    return tab


@pytest.fixture
def build_tab(qtbot, tmp_path):
    """Create a BuildTab instance for testing."""
    console = ConsoleWidget()
    settings = SettingsStore(tmp_path / "test_settings.json")
    log_queue = queue.Queue()
    
    tab = BuildTab(console, settings, log_queue)
    qtbot.addWidget(tab)
    tab.show()
    return tab


class TestExtractTabButtons:
    """Tests for Extract tab button labels and tooltips."""

    def test_browse_button_text_is_change_folder(self, extract_tab):
        """Browse buttons should be labeled 'Change folder'."""
        assert extract_tab.pdf_browse_btn.text() == "Change folder"

    def test_browse_button_tooltip(self, extract_tab):
        """Browse buttons should have clear tooltip."""
        assert "different folder" in extract_tab.pdf_browse_btn.toolTip().lower()

    def test_open_button_text_unchanged(self, extract_tab):
        """Open buttons should remain labeled 'Open'."""
        assert extract_tab.pdf_open_btn.text() == "Open"

    def test_browse_and_open_have_different_tooltips(self, extract_tab):
        """Browse and Open buttons should have distinct tooltips."""
        browse_tip = extract_tab.pdf_browse_btn.toolTip().lower()
        open_tip = extract_tab.pdf_open_btn.toolTip().lower()
        
        assert browse_tip != open_tip
        assert "choose" in browse_tip or "select" in browse_tip or "different" in browse_tip
        assert "explorer" in open_tip or "open" in open_tip


class TestBuildTabButtons:
    """Tests for Build tab button labels and tooltips."""

    def test_browse_button_text_is_change_folder(self, build_tab):
        """Browse button should be labeled 'Change folder'."""
        assert build_tab.browse_out_btn.text() == "Change folder"

    def test_browse_button_tooltip(self, build_tab):
        """Browse button should have clear tooltip."""
        assert "different folder" in build_tab.browse_out_btn.toolTip().lower()

    def test_open_button_text_unchanged(self, build_tab):
        """Open button should remain labeled 'Open'."""
        assert build_tab.open_out_btn.text() == "Open"

    def test_browse_and_open_have_different_tooltips(self, build_tab):
        """Browse and Open buttons should have distinct tooltips."""
        browse_tip = build_tab.browse_out_btn.toolTip().lower()
        open_tip = build_tab.open_out_btn.toolTip().lower()
        
        assert browse_tip != open_tip
        assert "choose" in browse_tip or "select" in browse_tip or "different" in browse_tip
        assert "explorer" in open_tip or "open" in open_tip

