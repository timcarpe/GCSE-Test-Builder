"""
Console widget for displaying logs.
"""
from typing import Optional, Set
from datetime import datetime
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QPlainTextEdit, QWidget, QHBoxLayout, 
    QToolButton, QMenu, QApplication, QFileDialog, QSizePolicy
)
from PySide6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat
from PySide6.QtCore import Qt, Slot

from gcse_toolkit.gui_v2.styles.theme import Colors, Fonts, get_colors
from gcse_toolkit.gui_v2.utils.icons import MaterialIcons


# =============================================================================
# CONSOLE LOG LEVEL CONFIGURATION
# =============================================================================
# Set of log levels to suppress from GUI console display.
# Valid values: "info", "warning", "error", "success", "warn", "stderr", "ok"
# Example: {"info", "warning"} suppresses both INFO and WARNING logs
CONSOLE_SUPPRESSED_LEVELS: Set[str] = {"info"}
# =============================================================================


class ConsoleWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Console Log", parent)
        
        # Log level suppression - uses module-level CONSOLE_SUPPRESSED_LEVELS
        # Can be overridden per instance: console.suppressed_levels = {"warning"}
        self.suppressed_levels: Set[str] = CONSOLE_SUPPRESSED_LEVELS.copy()
        
        # Set minimum height to ensure title bar is always visible when collapsed
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.layout = QVBoxLayout(self)
        # Reduced margins since we'll add padding via stylesheet
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        
        # Set font
        font = QFont(Fonts.MONO_FONT.split(',')[0]) # Use first available
        if "pt" in Fonts.CONSOLE:
             font.setPointSize(int(Fonts.CONSOLE.replace("pt", "")))
        self.text_edit.setFont(font)
        
        # Add explicit padding via stylesheet to prevent text cutoff
        # Add explicit padding via stylesheet to prevent text cutoff
        C = get_colors()
        
        # Apply initial style to GroupBox (self)
        self.setStyleSheet(f"""
            QGroupBox {{
                background-color: {C.SURFACE};
                border-top: 1px solid {C.BORDER};
                border-bottom: 1px solid {C.BORDER};
                border-left: none;
                border-right: none;
                border-radius: 0px;
                margin-top: 24px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                background-color: {C.BACKGROUND};
                color: {C.TEXT_PRIMARY};
            }}
        """)
        
        self.text_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                border: none;
                background-color: {C.SURFACE};
                padding: 0px;
                border-radius: 0px;
            }}
        """)
        
        self.layout.addWidget(self.text_edit)
        
        # Define formats
        self.format_info = QTextCharFormat()
        self.format_info.setForeground(QColor(C.TEXT_PRIMARY))
        
        self.format_error = QTextCharFormat()
        self.format_error.setForeground(QColor(C.ERROR))
        
        self.format_warning = QTextCharFormat()
        self.format_warning.setForeground(QColor(C.WARNING))
        
        self.format_success = QTextCharFormat()
        self.format_success.setForeground(QColor(C.SUCCESS))

    @Slot(str, str)
    def append_log(self, level: str, message: str):
        """Appends a log message with color coding based on level."""
        # Check if level is suppressed
        if level.lower() in self.suppressed_levels:
            return
        
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        fmt = self.format_info
        if level.lower() in ("error", "stderr"):
            fmt = self.format_error
        elif level.lower() in ("warning", "warn"):
            fmt = self.format_warning
        elif level.lower() in ("success", "ok"):
            fmt = self.format_success
            
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        cursor.insertText(f"[{timestamp}] [{level.upper()}] {message}\n", fmt)
        
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()
        
        # Limit line count (1000 lines)
        doc = self.text_edit.document()
        if doc.lineCount() > 1000:
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, doc.lineCount() - 1000)
            cursor.removeSelectedText()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        
        copy_action = menu.addAction(MaterialIcons.content_copy(), "Copy")
        copy_all_action = menu.addAction(MaterialIcons.content_copy(), "Copy All")
        menu.addSeparator()
        save_action = menu.addAction(MaterialIcons.content_save(), "Save to File...")
        menu.addSeparator()
        clear_action = menu.addAction(MaterialIcons.delete(), "Clear")
        
        action = menu.exec(event.globalPos())
        
        if action == copy_action:
            cursor = self.text_edit.textCursor()
            if cursor.hasSelection():
                QApplication.clipboard().setText(cursor.selectedText())
        elif action == copy_all_action:
            QApplication.clipboard().setText(self.text_edit.toPlainText())
        elif action == save_action:
            self._save_to_file()
        elif action == clear_action:
            self.clear()

    def _save_to_file(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Log", "console_log.txt", "Text Files (*.txt);;All Files (*)"
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.text_edit.toPlainText())
            except Exception as e:
                self.append_log("ERROR", f"Failed to save log: {e}")

    def clear(self):
        self.text_edit.clear()

    def update_theme(self):
        """Update styles when theme changes."""
        C = get_colors()
        
        # Update text edit background and padding
        # Update GroupBox style
        self.setStyleSheet(f"""
            QGroupBox {{
                background-color: {C.SURFACE};
                border-top: 1px solid {C.BORDER};
                border-bottom: 1px solid {C.BORDER};
                border-left: none;
                border-right: none;
                border-radius: 0px;
                margin-top: 24px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                background-color: {C.BACKGROUND};
                color: {C.TEXT_PRIMARY};
            }}
        """)
        
        # Update text edit background and padding
        self.text_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                border: none;
                background-color: {C.SURFACE};
                padding: 0px;
                border-radius: 0px;
            }}
        """)
        
        # Update formats for new text
        self.format_info.setForeground(QColor(C.TEXT_PRIMARY))
        self.format_error.setForeground(QColor(C.ERROR))
        self.format_warning.setForeground(QColor(C.WARNING))
        self.format_success.setForeground(QColor(C.SUCCESS))
