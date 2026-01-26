"""
Path utilities for handling dev vs production (frozen) file locations.

Dev mode: Uses local workspace/ directory
Frozen mode: Uses system-standard paths (Documents, AppData)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Try to import Qt paths, but don't fail if not available (e.g., in CLI context)
try:
    from PySide6.QtCore import QStandardPaths
    _HAS_QT = True
except ImportError:
    _HAS_QT = False


def is_frozen() -> bool:
    """Check if running as a frozen (PyInstaller) application."""
    return getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')


def get_app_data_dir() -> Path:
    """
    Get the application data directory for internal state files.
    
    Frozen: ~/Library/Application Support/GCSE Test Builder (macOS) 
            or %APPDATA%/GCSE Test Builder (Windows)
    Dev: workspace/
    """
    if is_frozen():
        if _HAS_QT:
            app_data = Path(QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppLocalDataLocation
            ))
            # Ensure directory exists
            app_data.mkdir(parents=True, exist_ok=True)
            return app_data
        else:
            # Fallback for frozen CLI execution or failed Qt import
            import platform
            import os
            if platform.system() == "Windows":
                # Use AppData/Local to match Qt's AppLocalDataLocation
                # os.environ["LOCALAPPDATA"] or fallback to APPDATA
                base = os.environ.get("LOCALAPPDATA", os.environ.get("APPDATA"))
                return Path(base) / "GCSE Test Builder" if base else Path.home() / ".gcse_toolkit"
            elif platform.system() == "Darwin":
                return Path.home() / "Library/Application Support/GCSE Test Builder"
            else:
                return Path.home() / ".local/share/GCSE Test Builder"
    else:
        # Dev mode: use local workspace
        return Path.cwd() / "workspace"


def get_user_document_dir(subdir: str = "") -> Path:
    """
    Get the user documents directory for user-facing content.
    
    Args:
        subdir: Optional subdirectory name ("Source PDFs", "Generated Exams", etc.)
    
    Frozen: ~/Documents/GCSE Test Builder/{subdir}
    Dev: workspace/{mapped_subdir}
    """
    # Mapping from user-friendly names to dev workspace names
    subdir_map = {
        "Source PDFs": "input_pdfs",
        "Generated Exams": "output_papers",
        "": "",
    }
    
    if is_frozen():
        if _HAS_QT:
            docs = Path(QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DocumentsLocation
            ))
            base = docs / "GCSE Test Builder"
        else:
             import platform
             base = Path.home() / "Documents" / "GCSE Test Builder"
             
        if subdir:
            return base / subdir
        return base
    else:
        # Dev mode: use local workspace with mapped names
        mapped = subdir_map.get(subdir, subdir)
        if mapped:
            return Path.cwd() / "workspace" / mapped
        return Path.cwd() / "workspace"


def get_settings_path() -> Path:
    """Get the path for storing GUI settings."""
    return get_app_data_dir() / "gui_settings.json"


def get_cache_dir() -> Path:
    """Get the cache directory for keyword caches etc."""
    return get_app_data_dir() / "cache"


def get_slices_cache_dir() -> Path:
    """Get the slices cache directory (extracted question data)."""
    return get_app_data_dir() / "slices_cache"


def ensure_directories() -> None:
    """
    Ensure required directories exist and generate README files.
    
    Called on app startup in frozen mode.
    """
    if not is_frozen():
        return  # Dev mode handles this differently
    
    # Create user-facing directories
    source_pdfs = get_user_document_dir("Source PDFs")
    generated_exams = get_user_document_dir("Generated Exams")
    
    source_pdfs.mkdir(parents=True, exist_ok=True)
    generated_exams.mkdir(parents=True, exist_ok=True)
    
    # Create README in main GCSE Test Builder folder
    base_dir = get_user_document_dir()
    readme_main = base_dir / "README.txt"
    if not readme_main.exists():
        readme_main.write_text(
            "GCSE Test Builder Folder Structure\n"
            "=============================\n\n"
            "Source PDFs/     - Place your exam papers here (question papers and mark schemes)\n"
            "Generated Exams/ - Your generated exam papers will appear here\n\n"
            "For more information, see the application documentation.\n"
        )
    
    # Create README in Source PDFs with naming convention
    readme_source = source_pdfs / "README.txt"
    if not readme_source.exists():
        readme_source.write_text(
            "PDF Naming Convention\n"
            "=====================\n\n"
            "Question papers and mark schemes should follow this naming pattern:\n\n"
            "  ####_series_qp_##.pdf  (Question Paper)\n"
            "  ####_series_ms_##.pdf  (Mark Scheme)\n\n"
            "Where:\n"
            "  #### = 4-digit exam code (e.g., 0610 for Biology)\n"
            "  series = exam series (e.g., s23 for Summer 2023, w22 for Winter 2022)\n"
            "  ## = paper number (e.g., 12, 22, 42)\n\n"
            "Examples:\n"
            "  0610_s23_qp_12.pdf\n"
            "  0610_s23_ms_12.pdf\n"
            "  0455_w22_qp_22.pdf\n"
            "  0455_w22_ms_22.pdf\n\n"
            "The question paper and mark scheme MUST share the same prefix,\n"
            "differing only in the _qp_ vs _ms_ component.\n"
        )
    
    get_cache_dir().mkdir(parents=True, exist_ok=True)
    get_slices_cache_dir().mkdir(parents=True, exist_ok=True)


def get_user_plugins_dir() -> Path:
    """
    Get the directory where user plugins are stored.
    
    Matches logic in gcse_toolkit.plugins.__init__._get_user_plugins_dir
    """
    if is_frozen():
        if sys.platform == "darwin":
            # macOS: Documents/GCSE Test Builder/plugins
            return Path.home() / "Documents" / "GCSE Test Builder" / "plugins"
        else:
            # Windows: %APPDATA%/GCSE Test Builder/plugins
            import os
            return Path(os.environ.get("APPDATA", "")) / "GCSE Test Builder" / "plugins"
    else:
        # Dev mode: src/gcse_toolkit/plugins
        # This file is in src/gcse_toolkit/gui_v2/utils/paths.py
        # ../../../plugins
        return Path(__file__).resolve().parent.parent.parent / "plugins"
