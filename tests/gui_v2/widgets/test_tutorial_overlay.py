"""Tests for tutorial overlay components."""
import pytest
from pathlib import Path
import tempfile


class TestTutorialSettings:
    """Test tutorial_seen persistence in SettingsStore."""

    def test_tutorial_seen_default_false(self, tmp_path):
        """New settings file should have tutorial_seen as False."""
        from gcse_toolkit.gui_v2.models.settings import SettingsStore
        
        settings_path = tmp_path / "settings.json"
        store = SettingsStore(settings_path)
        
        assert store.has_seen_tutorial() is False

    def test_set_tutorial_seen(self, tmp_path):
        """Setting tutorial_seen should persist the value."""
        from gcse_toolkit.gui_v2.models.settings import SettingsStore
        
        settings_path = tmp_path / "settings.json"
        store = SettingsStore(settings_path)
        
        store.set_tutorial_seen(True)
        assert store.has_seen_tutorial() is True
        
        # Verify persistence by reloading
        store2 = SettingsStore(settings_path)
        assert store2.has_seen_tutorial() is True

    def test_set_tutorial_seen_false(self, tmp_path):
        """Setting tutorial_seen to False should work."""
        from gcse_toolkit.gui_v2.models.settings import SettingsStore
        
        settings_path = tmp_path / "settings.json"
        store = SettingsStore(settings_path)
        
        store.set_tutorial_seen(True)
        store.set_tutorial_seen(False)
        assert store.has_seen_tutorial() is False


class TestTutorialStep:
    """Test TutorialStep dataclass."""

    def test_tutorial_step_defaults(self):
        """TutorialStep should have correct defaults."""
        from gcse_toolkit.gui_v2.widgets.tutorial_overlay import TutorialStep
        
        step = TutorialStep(
            target_widget=None,
            title="Test Title",
            message="Test message"
        )
        
        assert step.title == "Test Title"
        assert step.message == "Test message"
        assert step.callout_position == "bottom"
        assert step.before_show is None

    def test_tutorial_step_with_callback(self):
        """TutorialStep should accept before_show callback."""
        from gcse_toolkit.gui_v2.widgets.tutorial_overlay import TutorialStep
        
        called = []
        def callback():
            called.append(True)
        
        step = TutorialStep(
            target_widget=None,
            title="Test",
            message="Test",
            before_show=callback
        )
        
        step.before_show()
        assert called == [True]
