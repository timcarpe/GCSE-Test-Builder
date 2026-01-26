"""
Unit tests for GUI v2 critical components.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from gcse_toolkit.gui_v2.models.settings import SettingsStore, ExamSettings
from gcse_toolkit.gui_v2.utils.helpers import discover_exam_codes, open_folder_in_browser


class TestSettingsStore(unittest.TestCase):
    """Test settings persistence."""
    
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.settings_path = Path(self.temp_dir.name) / "test_settings.json"
        self.store = SettingsStore(self.settings_path)
    
    def tearDown(self):
        self.temp_dir.cleanup()
    
    def test_metadata_root_persistence(self):
        """Test metadata root is saved and loaded correctly."""
        test_path = "/test/path/to/metadata"
        self.store.set_metadata_root(test_path)
        
        # Create new store instance to test persistence
        new_store = SettingsStore(self.settings_path)
        self.assertEqual(new_store.get_metadata_root(), test_path)
    
    def test_exam_settings_persistence(self):
        """Test exam settings are saved and loaded correctly."""
        settings = ExamSettings(
            topics=["Topic 1", "Topic 2"],
            target_marks=50,
            tolerance=3,
            seed=12345,
            output_dir="/output/path",
            sub_topics={"Topic 1": ["Sub 1", "Sub 2"]},
            filter_mode="Topics",
            keywords=[],
            keyword_pins=[],
            part_mode=1,  # PRUNE mode
            force_topic_representation=True
        )
        
        self.store.set_exam_settings("9702", settings)
        
        # Load and verify
        loaded = self.store.get_exam_settings("9702")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.topics, ["Topic 1", "Topic 2"])
        self.assertEqual(loaded.target_marks, 50)
        self.assertEqual(loaded.tolerance, 3)
        self.assertEqual(loaded.seed, 12345)
        self.assertEqual(loaded.part_mode, 1)
    
    def test_splitter_state_persistence(self):
        """Test splitter state is saved correctly (Bug #4 fix)."""
        # Must be valid hex for SettingsStore validation
        test_state = "abc123def456" 
        self.store.set_splitter_state(test_state)
        
        # Create new store to test persistence
        new_store = SettingsStore(self.settings_path)
        self.assertEqual(new_store.get_splitter_state(), test_state)


class TestHelpers(unittest.TestCase):
    """Test helper functions."""
    
    def test_discover_exam_codes_empty(self):
        """Test discover_exam_codes with non-existent directory."""
        codes = discover_exam_codes(Path("/nonexistent/path"))
        self.assertEqual(codes, [])
    
    def test_discover_exam_codes_with_structure(self):
        """Test discover_exam_codes with proper structure."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            
            # Create exam structure
            exam_dir = root / "9702"
            metadata_dir = exam_dir / "_metadata"
            metadata_dir.mkdir(parents=True)
            (metadata_dir / "questions.jsonl").touch()
            
            codes = discover_exam_codes(root)
            self.assertIn("9702", codes)
    
    def test_open_folder_nonexistent(self):
        """Test open_folder_in_browser with non-existent path."""
        success, error = open_folder_in_browser(Path("/nonexistent/folder"))
        self.assertFalse(success)
        self.assertIn("does not exist", error)
    
    def test_open_folder_not_directory(self):
        """Test open_folder_in_browser with file instead of directory."""
        with TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.txt"
            file_path.touch()
            
            success, error = open_folder_in_browser(file_path)
            self.assertFalse(success)
            self.assertIn("not a directory", error)


if __name__ == "__main__":
    unittest.main()
