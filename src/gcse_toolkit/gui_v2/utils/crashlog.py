"""
Crashlog utilities for capturing unhandled exceptions in compiled applications.

In frozen (PyInstaller) builds, stderr is not visible to users. This module
captures exceptions (both Python and C++/Qt level), writes them to crash log
files, and shows a user-friendly dialog.

C++ Crash Handling Strategy:
1. Python exceptions: sys.excepthook (works well)
2. Native crashes (segfaults): faulthandler module writes to crash file
3. Qt errors: Qt message handler intercepts qWarning/qCritical/qFatal
4. Process-level crashes: Detected on restart via unclean_exit marker file
"""
from __future__ import annotations

import atexit
import faulthandler
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

# Global reference to original excepthook
_original_excepthook: Optional[Callable] = None

# Maximum number of crash logs to keep
MAX_CRASH_LOGS = 5

# File handle for faulthandler output (kept open for native crash capture)
_faulthandler_file = None

# App version for crash reports
_app_version = "unknown"


def get_crashlog_dir() -> Path:
    """Get the directory for crash logs."""
    from gcse_toolkit.gui_v2.utils.paths import get_app_data_dir
    crash_dir = get_app_data_dir() / "crash_logs"
    crash_dir.mkdir(parents=True, exist_ok=True)
    return crash_dir


def _get_unclean_exit_marker() -> Path:
    """Get path to the unclean exit marker file."""
    return get_crashlog_dir() / ".running"


def _get_last_crash_file() -> Path:
    """Get path to the last crash file (for faulthandler output)."""
    return get_crashlog_dir() / "last_crash.log"


def _rotate_crash_logs() -> None:
    """
    Maintain a maximum of MAX_CRASH_LOGS files.
    
    Deletes oldest logs when limit is exceeded.
    """
    crash_dir = get_crashlog_dir()
    logs = sorted(crash_dir.glob("crash_*.log"), key=lambda p: p.stat().st_mtime)
    
    # Remove oldest logs if we're at or over the limit
    while len(logs) >= MAX_CRASH_LOGS:
        oldest = logs.pop(0)
        try:
            oldest.unlink()
        except Exception:
            pass  # Best effort deletion


def _install_qt_message_handler() -> None:
    """
    Install a Qt message handler to capture Qt warnings and errors.
    
    Qt's qWarning, qCritical, and qFatal messages are logged to the crash log.
    qFatal messages are particularly important as they usually precede a crash.
    """
    try:
        from PySide6.QtCore import qInstallMessageHandler, QtMsgType
        
        def qt_message_handler(mode, context, message):
            """Handle Qt debug/warning/error messages."""
            level_map = {
                QtMsgType.QtDebugMsg: "DEBUG",
                QtMsgType.QtInfoMsg: "INFO",
                QtMsgType.QtWarningMsg: "WARNING",
                QtMsgType.QtCriticalMsg: "CRITICAL",
                QtMsgType.QtFatalMsg: "FATAL",
            }
            level = level_map.get(mode, "UNKNOWN")
            
            # For critical/fatal, write to crash log immediately
            if mode in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
                try:
                    crash_file = _get_last_crash_file()
                    with open(crash_file, "a", encoding="utf-8") as f:
                        f.write(f"\n[{datetime.now().isoformat()}] Qt {level}:\n")
                        f.write(f"  File: {context.file}:{context.line}\n")
                        f.write(f"  Function: {context.function}\n")
                        f.write(f"  Message: {message}\n")
                except Exception:
                    pass
            
            # Also print to stderr for console visibility
            print(f"Qt {level}: {message}", file=sys.stderr)
        
        qInstallMessageHandler(qt_message_handler)
    except ImportError:
        pass  # Qt not available yet


def _install_faulthandler() -> None:
    """
    Install faulthandler to capture native crashes (segfaults, etc.).
    
    Faulthandler writes Python traceback to a file when a native crash occurs.
    This is our best chance to capture C++ crashes from PyMuPDF, Qt, etc.
    """
    global _faulthandler_file
    
    try:
        crash_file = _get_last_crash_file()
        # Open file in append mode and keep it open
        _faulthandler_file = open(crash_file, "a", encoding="utf-8")
        _faulthandler_file.write(f"\n[{datetime.now().isoformat()}] Session started (v{_app_version})\n")
        _faulthandler_file.flush()
        
        # Enable faulthandler to write to this file
        faulthandler.enable(file=_faulthandler_file, all_threads=True)
        
        # Also output to stderr for console visibility
        faulthandler.enable(file=sys.stderr, all_threads=True)
    except Exception as e:
        print(f"Warning: Could not install faulthandler: {e}", file=sys.stderr)


def _install_threading_excepthook() -> None:
    """
    Install a thread exception handler (Python 3.8+).
    
    Catches unhandled exceptions in worker threads and writes them to the crash log.
    Note: This doesn't show a dialog (threads can't safely interact with Qt GUI),
    but it ensures the exception is logged.
    """
    import threading
    
    def thread_excepthook(args):
        """Handle uncaught exceptions in threads."""
        exc_type, exc_value, exc_tb, thread = args.exc_type, args.exc_value, args.exc_traceback, args.thread
        
        # Format the traceback
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        tb_text = "".join(tb_lines)
        
        # Write to stderr
        thread_name = thread.name if thread else "Unknown"
        print(f"\n*** Unhandled exception in thread '{thread_name}' ***", file=sys.stderr)
        print(tb_text, file=sys.stderr)
        sys.stderr.flush()
        
        # Write to crash log file
        try:
            crash_file = _get_last_crash_file()
            with open(crash_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now().isoformat()}] Thread exception in '{thread_name}':\n")
                f.write(tb_text)
        except Exception:
            pass
    
    # Python 3.8+ has threading.excepthook
    if hasattr(threading, 'excepthook'):
        threading.excepthook = thread_excepthook


def _create_unclean_exit_marker() -> None:
    """Create a marker file indicating the app is running."""
    try:
        marker = _get_unclean_exit_marker()
        marker.write_text(datetime.now().isoformat())
    except Exception:
        pass


def _remove_unclean_exit_marker() -> None:
    """Remove the marker file on clean exit."""
    try:
        marker = _get_unclean_exit_marker()
        if marker.exists():
            marker.unlink()
    except Exception:
        pass


def check_previous_crash() -> Optional[str]:
    """
    Check if the previous session crashed (unclean exit).
    
    Call this after QApplication is created to potentially show crash info.
    
    Returns:
        Crash log content if previous session crashed, None otherwise.
    """
    marker = _get_unclean_exit_marker()
    crash_file = _get_last_crash_file()
    
    if marker.exists():
        # Previous session didn't exit cleanly
        crash_content = None
        if crash_file.exists():
            try:
                crash_content = crash_file.read_text(encoding="utf-8")
            except Exception:
                pass
        
        # Clean up marker and crash file
        try:
            marker.unlink()
        except Exception:
            pass
            
        return crash_content
    
    return None


def show_previous_crash_dialog(crash_content: str) -> None:
    """
    Show a dialog informing user about a previous crash.
    
    Args:
        crash_content: The crash log content from the previous session.
    """
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtCore import Qt
        
        app = QApplication.instance()
        if not app:
            return
        
        # Save the crash content with proper timestamp
        try:
            _rotate_crash_logs()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            crash_file = get_crashlog_dir() / f"crash_{timestamp}.log"
            crash_file.write_text(
                f"GCSE Test Builder Crash Report (recovered from previous session)\n"
                f"{'=' * 50}\n"
                f"Recovered at: {datetime.now().isoformat()}\n\n"
                f"{crash_content}"
            )
        except Exception:
            crash_file = None
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("GCSE Test Builder - Previous Session Crashed")
        msg.setText("The application crashed in a previous session.")
        
        if crash_file and crash_file.exists():
            msg.setInformativeText(
                f"A crash report has been saved to:\n{crash_file}\n\n"
                "This may have been caused by a native error (C++/Qt).\n"
                "Please include this file when reporting issues."
            )
        else:
            msg.setInformativeText(
                "The crash may have been caused by a native error.\n"
                "Unfortunately, no detailed crash log could be saved."
            )
        
        msg.setDetailedText(crash_content or "No crash details available.")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        
    except Exception:
        pass


def install_crash_handler(app_version: str = "unknown") -> None:
    """
    Install comprehensive crash handling for Python and native crashes.
    
    Call this early in application startup, before any GUI code.
    
    This installs:
    1. Python exception handler (sys.excepthook)
    2. Native crash handler (faulthandler for segfaults)
    3. Qt message handler (for qWarning/qCritical/qFatal)
    4. Unclean exit detection (marker file)
    
    Args:
        app_version: Application version string for crash reports.
    """
    global _original_excepthook, _app_version
    _original_excepthook = sys.excepthook
    _app_version = app_version
    
    # Install faulthandler for native crashes FIRST
    _install_faulthandler()
    
    # Create unclean exit marker
    _create_unclean_exit_marker()
    
    # Register clean exit handler
    atexit.register(_remove_unclean_exit_marker)
    atexit.register(_cleanup_faulthandler)
    
    # Install thread exception handler (Python 3.8+)
    # This catches unhandled exceptions in worker threads
    _install_threading_excepthook()
    
    def crash_handler(exc_type, exc_value, exc_tb):
        # Format the traceback FIRST (before any operations that might fail)
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        tb_text = "".join(tb_lines)
        
        # Also print to stderr immediately
        print(tb_text, file=sys.stderr)
        sys.stderr.flush()
        
        # Gather system info early
        import platform
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
        
        # Write crash log BEFORE any Qt operations
        crash_file = None
        try:
            _rotate_crash_logs()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            crash_file = get_crashlog_dir() / f"crash_{timestamp}.log"
            crash_file.write_text("\n".join(system_info))
        except Exception:
            pass  # Can't even write the crash log
        
        # Show user-friendly dialog if possible
        # This MUST block until user acknowledges
        _show_crash_dialog(crash_file, tb_text)
        
        # Remove unclean exit marker since we're handling this crash
        _remove_unclean_exit_marker()
        
        # Explicitly exit after dialog is dismissed
        # This prevents Python from continuing with undefined state
        sys.exit(1)
    
    sys.excepthook = crash_handler


def _cleanup_faulthandler() -> None:
    """Clean up faulthandler file handle on exit."""
    global _faulthandler_file
    if _faulthandler_file:
        try:
            _faulthandler_file.write(f"[{datetime.now().isoformat()}] Clean exit\n")
            _faulthandler_file.close()
        except Exception:
            pass
        _faulthandler_file = None


def install_qt_crash_handling() -> None:
    """
    Install Qt-specific crash handling.
    
    Call this AFTER QApplication is created but BEFORE showing the main window.
    This is a separate function because Qt must be initialized first.
    """
    _install_qt_message_handler()


def _show_crash_dialog(crash_file: Optional[Path], traceback_text: str) -> None:
    """
    Show a crash dialog to the user with the log location.
    
    This function blocks until the user acknowledges the dialog.
    
    Args:
        crash_file: Path to the written crash log file (may be None if write failed).
        traceback_text: Formatted traceback string for detailed view.
    """
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtCore import Qt
        
        # Get existing application instance (don't create one)
        app = QApplication.instance()
        if not app:
            return  # No Qt app running, silently fail
        
        # Build informative text
        if crash_file and crash_file.exists():
            info_text = (
                f"A crash report has been saved to:\n{crash_file}\n\n"
                "Please include this file when reporting the issue."
            )
        else:
            info_text = (
                "Could not save crash report.\n\n"
                "Please copy the details below when reporting the issue."
            )
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("GCSE Test Builder - Unexpected Error")
        msg.setText("The application encountered an unexpected error and needs to close.")
        msg.setInformativeText(info_text)
        msg.setDetailedText(traceback_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        # Ensure the dialog stays on top and is modal
        msg.setWindowModality(Qt.WindowModality.ApplicationModal)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        # Force event processing to ensure dialog is fully rendered
        app.processEvents()
        
        # Show and wait for user to click OK
        msg.exec()
        
        # Process any remaining events before exit
        app.processEvents()
        
    except Exception:
        pass  # Qt not available or dialog failed, fail silently

