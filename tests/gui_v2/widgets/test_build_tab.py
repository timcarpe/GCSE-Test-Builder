"""Unit tests for BuildTab filter toggle auto-refresh."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from PySide6.QtWidgets import QWidget

from gcse_toolkit.gui_v2.widgets.build_tab import BuildTab
from gcse_toolkit.gui_v2.widgets.console_widget import ConsoleWidget
from gcse_toolkit.gui_v2.models.settings import SettingsStore
import queue

@pytest.fixture
def build_tab(qtbot, tmp_path):
    """Create a BuildTab instance for testing."""
    console = ConsoleWidget()
    settings = SettingsStore(tmp_path / "test_settings.json")
    log_queue = queue.Queue()
    
    # Patch get_metadata_root on the instance to persist beyond fixture
    settings.get_metadata_root = MagicMock(return_value=str(tmp_path))
    
    tab = BuildTab(console, settings, log_queue)
    qtbot.addWidget(tab)
    
    # Setup mock dependencies that might be called
    tab.topic_selector.load_topics_for_exam = MagicMock()
    tab.keyword_panel._on_preview_clicked = MagicMock()
    
    return tab

class TestFilterModeAutoRefresh:
    """Tests for auto-refresh on filter mode change."""

    def test_topics_mode_refreshes_topic_selector(self, build_tab):
        """Switching to Topics mode should reload topic selector."""
        # Setup
        build_tab.current_exam_code = "test_exam"
        
        # Act - Switch to Topics (index 0)
        # Note: We need to ensure we're not starting at 0, or force the signal
        build_tab.filter_toggle.set_index(1) # Start at Keywords
        
        # Reset mocks after setup side effects
        build_tab.topic_selector.load_topics_for_exam.reset_mock()
        
        build_tab.filter_toggle.set_index(0) # Switch to Topics
        
        # Assert
        build_tab.topic_selector.load_topics_for_exam.assert_called_once()
        args = build_tab.topic_selector.load_topics_for_exam.call_args
        assert args[0][0] == "test_exam"

    def test_keywords_mode_triggers_preview_if_keywords_exist(self, build_tab):
        """Switching to Keywords mode with keywords should trigger preview."""
        # Setup
        build_tab.current_exam_code = "test_exam"
        
        # Mock has keywords
        with patch.object(build_tab.keyword_panel, 'get_current_keywords', return_value=["test_keyword"]):
            
            # Act - Switch to Keywords (index 1)
            build_tab.filter_toggle.set_index(0) # Start at Topics
            
            # Reset mocks
            build_tab.keyword_panel._on_preview_clicked.reset_mock()
            
            build_tab.filter_toggle.set_index(1) # Switch to Keywords
            
            # Assert
            build_tab.keyword_panel._on_preview_clicked.assert_called_once()

    def test_keywords_mode_no_preview_if_no_keywords(self, build_tab):
        """Switching to Keywords mode without keywords should not trigger preview."""
        # Setup
        build_tab.current_exam_code = "test_exam"
        
        # Mock NO keywords
        with patch.object(build_tab.keyword_panel, 'get_current_keywords', return_value=[]):
            
            # Act
            build_tab.filter_toggle.set_index(0)
            build_tab.keyword_panel._on_preview_clicked.reset_mock()
            
            build_tab.filter_toggle.set_index(1)
            
            # Assert
            build_tab.keyword_panel._on_preview_clicked.assert_not_called()

    def test_no_refresh_without_exam_code(self, build_tab):
        """Should not attempt refresh if no exam code is selected."""
        # Setup - explicitly set no exam code
        build_tab.current_exam_code = None
        
        # Act
        build_tab.filter_toggle.set_index(1)
        build_tab.filter_toggle.set_index(0)
        
        # Assert
        build_tab.topic_selector.load_topics_for_exam.assert_not_called()
        build_tab.keyword_panel._on_preview_clicked.assert_not_called()
