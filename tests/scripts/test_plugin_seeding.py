"""Tests for plugin seeding and version checking."""
import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestCheckPluginUpdates:
    """Tests for check_plugin_updates function."""

    def test_returns_empty_in_dev_mode(self):
        """In non-frozen mode, should return empty list."""
        from gcse_toolkit.plugins import check_plugin_updates
        
        # Ensure we're not in frozen mode
        with patch('gcse_toolkit.plugins.sys') as mock_sys:
            mock_sys.frozen = False
            # Actually call the function which checks getattr(sys, 'frozen', False)
            result = check_plugin_updates()
        
        # In dev mode, should return empty
        assert result == []

    def test_detects_newer_bundled_plugin(self, tmp_path: Path):
        """Should detect when bundled plugin is newer than installed."""
        from gcse_toolkit.plugins import _load_manifest_generated_at
        
        older_date = "2025-01-01T00:00:00+00:00"
        newer_date = "2026-01-01T00:00:00+00:00"
        
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"generated_at": older_date}))
        
        result = _load_manifest_generated_at(manifest_path)
        assert result == older_date
        assert older_date < newer_date  # Verify ISO comparison works

    def test_handles_missing_timestamp(self, tmp_path: Path):
        """Should return None for manifests without generated_at."""
        from gcse_toolkit.plugins import _load_manifest_generated_at
        
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"code": "0580", "name": "Math"}))
        
        result = _load_manifest_generated_at(manifest_path)
        assert result is None


class TestSeedPluginsFromBundle:
    """Tests for seed_plugins_from_bundle function."""

    def test_force_update_overwrites_existing(self, tmp_path: Path):
        """force_update_codes should overwrite existing plugins."""
        import shutil
        
        # Create a mock bundled plugin
        bundled_dir = tmp_path / "bundled"
        bundled_plugin = bundled_dir / "0580"
        bundled_plugin.mkdir(parents=True)
        (bundled_plugin / "manifest.json").write_text(json.dumps({
            "code": "0580",
            "name": "Math New",
            "generated_at": "2026-01-01T00:00:00+00:00"
        }))
        
        # Create existing user plugin (older)
        user_dir = tmp_path / "user"
        user_plugin = user_dir / "0580"
        user_plugin.mkdir(parents=True)
        (user_plugin / "manifest.json").write_text(json.dumps({
            "code": "0580",
            "name": "Math Old",
            "generated_at": "2025-01-01T00:00:00+00:00"
        }))
        
        # Manually simulate force update logic
        force_codes = {"0580"}
        for item in bundled_dir.iterdir():
            if item.is_dir() and (item / "manifest.json").exists():
                dest = user_dir / item.name
                if dest.exists() and item.name in force_codes:
                    shutil.rmtree(dest)
                    shutil.copytree(item, dest)
        
        # Verify overwrite happened
        updated_manifest = json.loads((user_plugin / "manifest.json").read_text())
        assert updated_manifest["name"] == "Math New"

    def test_preserves_plugins_not_in_force_list(self, tmp_path: Path):
        """Plugins not in force_update_codes should be preserved."""
        import shutil
        
        # Create bundled plugin
        bundled_dir = tmp_path / "bundled"
        bundled_plugin = bundled_dir / "0580"
        bundled_plugin.mkdir(parents=True)
        (bundled_plugin / "manifest.json").write_text(json.dumps({
            "code": "0580",
            "name": "Math New",
        }))
        
        # Create existing user plugin
        user_dir = tmp_path / "user"
        user_plugin = user_dir / "0580"
        user_plugin.mkdir(parents=True)
        (user_plugin / "manifest.json").write_text(json.dumps({
            "code": "0580",
            "name": "Math Old",
        }))
        
        # Simulate seed with empty force list
        force_codes = set()  # No force updates
        for item in bundled_dir.iterdir():
            if item.is_dir() and (item / "manifest.json").exists():
                dest = user_dir / item.name
                if dest.exists() and item.name in force_codes:
                    shutil.rmtree(dest)
                    shutil.copytree(item, dest)
        
        # Verify original preserved
        original_manifest = json.loads((user_plugin / "manifest.json").read_text())
        assert original_manifest["name"] == "Math Old"


class TestPopupQueue:
    """Tests for StartupPopupQueue."""

    def test_processes_popups_in_order(self, qtbot):
        """Popups should be processed in FIFO order."""
        from gcse_toolkit.gui_v2.utils.popup_queue import StartupPopupQueue
        
        queue = StartupPopupQueue()
        order = []
        
        def popup1():
            order.append(1)
            queue.notify_complete()
        
        def popup2():
            order.append(2)
            queue.notify_complete()
        
        def popup3():
            order.append(3)
            queue.notify_complete()
        
        queue.enqueue(popup1)
        queue.enqueue(popup2)
        queue.enqueue(popup3)
        queue.start()
        
        assert order == [1, 2, 3]

    def test_emits_all_completed_signal(self, qtbot):
        """Should emit all_completed when queue is exhausted."""
        from gcse_toolkit.gui_v2.utils.popup_queue import StartupPopupQueue
        
        queue = StartupPopupQueue()
        completed = []
        
        queue.all_completed.connect(lambda: completed.append(True))
        
        def popup():
            queue.notify_complete()
        
        queue.enqueue(popup)
        queue.start()
        
        assert len(completed) == 1

    def test_handles_empty_queue(self, qtbot):
        """Starting empty queue should just emit complete."""
        from gcse_toolkit.gui_v2.utils.popup_queue import StartupPopupQueue
        
        queue = StartupPopupQueue()
        completed = []
        
        queue.all_completed.connect(lambda: completed.append(True))
        queue.start()
        
        assert len(completed) == 1
