"""Plugin update dialog with checkbox selection.

Shows a dialog allowing users to select which plugins to update
when newer bundled versions are available.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt


class PluginUpdateDialog(QDialog):
    """Dialog for selecting plugins to update.
    
    Shows a list of plugins with checkboxes, displaying bundled vs installed dates.
    """
    
    def __init__(
        self,
        updates: List[Dict[str, str]],
        parent: Optional[QWidget] = None,
        on_complete: Optional[Callable[[], None]] = None
    ) -> None:
        """Initialize the plugin update dialog.
        
        Args:
            updates: List of dicts with keys: code, name, bundled_date, installed_date
            parent: Parent widget
            on_complete: Callback to invoke when dialog closes (for queue system)
        """
        super().__init__(parent)
        self._updates = updates
        self._on_complete = on_complete
        self._checkboxes: Dict[str, QCheckBox] = {}
        
        self.setWindowTitle("Plugin Updates Available")
        self.setMinimumWidth(500)
        self.setModal(True)
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Header
        header = QLabel(
            "<b>Updated plugins are available.</b><br>"
            "Select which plugins to update:"
        )
        header.setWordWrap(True)
        layout.addWidget(header)
        
        # Scroll area for plugin list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(300)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        
        for update in self._updates:
            item = self._create_plugin_item(update)
            scroll_layout.addWidget(item)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Select all / deselect all buttons
        select_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        select_row.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self._deselect_all)
        select_row.addWidget(deselect_all_btn)
        
        select_row.addStretch()
        layout.addLayout(select_row)
        
        # Action buttons
        button_row = QHBoxLayout()
        button_row.addStretch()
        
        skip_btn = QPushButton("Skip")
        skip_btn.clicked.connect(self._on_skip)
        button_row.addWidget(skip_btn)
        
        update_btn = QPushButton("Update Selected")
        update_btn.setDefault(True)
        update_btn.clicked.connect(self._on_update)
        button_row.addWidget(update_btn)
        
        layout.addLayout(button_row)
    
    def _create_plugin_item(self, update: Dict[str, str]) -> QWidget:
        """Create a widget for a single plugin update entry."""
        item = QWidget()
        layout = QHBoxLayout(item)
        layout.setContentsMargins(8, 4, 8, 4)
        
        # Checkbox with plugin name
        checkbox = QCheckBox(update["name"])
        checkbox.setChecked(True)  # Checked by default
        self._checkboxes[update["code"]] = checkbox
        layout.addWidget(checkbox, 1)
        
        # Date info
        date_label = QLabel(
            f"<span style='color: gray;'>"
            f"Installed: {self._format_date(update['installed_date'])}"
            f" → Bundled: {self._format_date(update['bundled_date'])}"
            f"</span>"
        )
        date_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(date_label)
        
        return item
    
    def _format_date(self, iso_date: str) -> str:
        """Format ISO date for display, or return as-is if not parseable."""
        if iso_date == "(unknown)":
            return iso_date
        try:
            # Parse ISO format and display just the date
            from datetime import datetime
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            return iso_date[:10] if len(iso_date) >= 10 else iso_date
    
    def _select_all(self) -> None:
        for checkbox in self._checkboxes.values():
            checkbox.setChecked(True)
    
    def _deselect_all(self) -> None:
        for checkbox in self._checkboxes.values():
            checkbox.setChecked(False)
    
    def _on_skip(self) -> None:
        """Handle skip button click."""
        self._selected_codes: List[str] = []
        self.accept()
    
    def _on_update(self) -> None:
        """Handle update button click."""
        self._selected_codes = [
            code for code, checkbox in self._checkboxes.items()
            if checkbox.isChecked()
        ]
        self.accept()
    
    def get_selected_codes(self) -> List[str]:
        """Return the list of plugin codes that were selected for update."""
        return getattr(self, '_selected_codes', [])
    
    def done(self, result: int) -> None:
        """Override done to invoke callback after dialog closes."""
        super().done(result)
        # Only call on_complete here (not also in closeEvent) to avoid double-call
        if self._on_complete:
            self._on_complete()
            self._on_complete = None  # Prevent subsequent calls
