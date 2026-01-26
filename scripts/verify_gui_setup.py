"""
Verify V2 GUI Components (Headless)

This script instantiates the key V2 widgets in a headless environment
to verify that all imports are correct, data structures are valid,
and signals are wired up without crashing.
"""

import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Setup path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

# Logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("gui_verify")

def verify_gui_components():
    """Instantiate V2 widgets to check for import/init errors."""
    print("--- Starting Headless GUI Verification ---")
    
    # 1. Start App
    app = QApplication(sys.argv)
    print("[OK] QApplication created")
    
    try:
        # 2. Check TopicSelector
        from gcse_toolkit.gui_v2.widgets.topic_selector import TopicSelector
        ts = TopicSelector()
        print("[OK] TopicSelector instantiated")
        
        # 3. Check KeywordPanel
        from gcse_toolkit.gui_v2.widgets.keyword_panel import KeywordPanel
        kp = KeywordPanel()
        print("[OK] KeywordPanel instantiated")
        
        # 4. Check BuildTab (Complex dependency)
        # BuildTab requires SettingsStore access usually.
        # We'll mock the minimal environment if needed, or see if it crashes.
        try:
            from gcse_toolkit.gui_v2.widgets.build_tab import BuildTab
            # Mock settings? BuildTab usually takes parent but manages its own settings via QSettings
            # Let's try instantiating it.
            # Now that dependencies are optional, this should work.
            bt = BuildTab()
            print("[OK] BuildTab instantiated")
            
            # 5. Check ExtractTab
            from gcse_toolkit.gui_v2.widgets.extract_tab import ExtractTab
            et = ExtractTab()
            print("[OK] ExtractTab instantiated")
        except Exception as e:
            print(f"[FAIL] BuildTab init failed: {e}")
            # Identify if it's a "real" bug or just missing context
            raise e
            
        print("--- Verification Complete: All components loaded ---")
        return 0
        
    except ImportError as e:
        print(f"[ERROR] IMPORT ERROR: {e}")
        return 1
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] RUNTIME ERROR: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(verify_gui_components())
