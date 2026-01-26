"""
Entry point for the PySide6 GUI v2.

CRITICAL: Worker process detection must happen BEFORE any imports.
When ProcessPoolExecutor spawns workers in a frozen PyInstaller app,
each worker re-runs this module. We use an environment variable set
by the parent to detect workers and exit before loading GUI code.
"""
# WORKER DETECTION - Must be the VERY FIRST thing, before any other imports
import os
import sys

# Check if this is a multiprocessing worker process
# The parent sets GCSE_MP_WORKER=1 before spawning workers
if os.environ.get('GCSE_MP_WORKER') == '1' and getattr(sys, 'frozen', False):
    # This is a worker process in a frozen app - do NOT start GUI
    # Just let multiprocessing machinery handle this process
    import multiprocessing
    multiprocessing.freeze_support()
    # If we reach here, freeze_support didn't exit (unexpected)
    # Exit anyway to prevent GUI from starting
    sys.exit(0)

# From here, only the main GUI process should reach this code
import multiprocessing

# Standard freeze_support for non-frozen mode and main process
if getattr(sys, 'frozen', False):
    multiprocessing.freeze_support()
    # Install crash handler for compiled builds (captures unhandled exceptions)
    from gcse_toolkit import __version__
    from gcse_toolkit.gui_v2.utils.crashlog import install_crash_handler
    install_crash_handler(app_version=__version__)


def _set_macos_app_name(name: str):
    """
    Set the application name in the macOS menu bar.
    This requires pyobjc-framework-Cocoa.
    """
    if sys.platform != "darwin":
        return
        
    try:
        from Foundation import NSBundle
        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        if info:
            info["CFBundleName"] = name
            
        from AppKit import NSApplication
        app = NSApplication.sharedApplication()
    except ImportError:
        pass


def _create_rounded_icon(icon_path_str: str):
    """
    Create a QIcon with rounded corners from an image path.
    """
    from PySide6.QtGui import QIcon, QPixmap, QPainter, QPainterPath
    from PySide6.QtCore import Qt
    
    pixmap = QPixmap(icon_path_str)
    if pixmap.isNull():
        return QIcon()
        
    size = pixmap.size()
    rounded = QPixmap(size)
    rounded.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    path = QPainterPath()
    radius = min(size.width(), size.height()) * 0.22
    path.addRoundedRect(0, 0, size.width(), size.height(), radius, radius)
    
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    
    return QIcon(rounded)


def run():
    """
    Main entry point for the GUI application.
    """
    from pathlib import Path
    from PySide6.QtWidgets import QApplication
    from gcse_toolkit.gui_v2.main_window import MainWindow
    from gcse_toolkit.gui_v2.utils.tooltips import init_tooltips
    
    _set_macos_app_name("GCSE Test Builder")
    app = QApplication(sys.argv)
    app.setApplicationName("GCSE Test Builder")
    app.setApplicationDisplayName("GCSE Test Builder")
    app.setOrganizationName("GCSE Test Builder")
    app.setDesktopFileName("GCSE Test Builder")

    # Install Qt-specific crash handling (must be after QApplication is created)
    from gcse_toolkit.gui_v2.utils.crashlog import (
        install_qt_crash_handling,
        check_previous_crash,
        show_previous_crash_dialog,
    )
    install_qt_crash_handling()
    
    # Check if previous session crashed (C++ crashes won't show dialog at crash time)
    previous_crash = check_previous_crash()
    if previous_crash:
        show_previous_crash_dialog(previous_crash)

    from gcse_toolkit.gui_v2.models.settings import SettingsStore
    from gcse_toolkit.gui_v2.styles.theme import set_dark_mode, GLOBAL_STYLESHEET, GLOBAL_STYLESHEET_DARK
    from gcse_toolkit.gui_v2.utils.paths import get_settings_path, ensure_directories
    
    ensure_directories()
    
    settings_path = get_settings_path()
    settings = SettingsStore(settings_path)
    
    # Check for malformed settings and prompt user to reset if needed
    if not settings.check_load_error():
        sys.exit(1)  # User chose not to reset, exit app
    
    is_dark = settings.get_dark_mode()
    
    set_dark_mode(is_dark)
    if is_dark:
        app.setStyleSheet(GLOBAL_STYLESHEET_DARK)
    else:
        app.setStyleSheet(GLOBAL_STYLESHEET)
    
    init_tooltips()
    
    # Seed plugins to user directory (in frozen mode only)
    # Also done via popup queue for updates, but initial seeding happens here
    from gcse_toolkit.plugins import seed_plugins_from_bundle
    seed_plugins_from_bundle()
    
    if hasattr(sys, '_MEIPASS'):
        icon_path = Path(sys._MEIPASS) / "gcse_toolkit" / "gui_v2" / "styles" / "logo.png"
    else:
        icon_path = Path(__file__).resolve().parent / "styles" / "logo.png"
    if icon_path.exists():
        app.setWindowIcon(_create_rounded_icon(str(icon_path)))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    run()
