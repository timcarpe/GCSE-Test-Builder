"""
Multi-select dropdown widget with checkboxes for year filtering.
"""
from typing import List, Optional, Set
from PySide6.QtWidgets import QComboBox, QListView
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem


class MultiSelectYearFilter(QComboBox):
    """Multi-select dropdown with checkboxes for year filtering."""
    
    selectionChanged = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set up the model
        self.model = QStandardItemModel(self)
        self.setModel(self.model)
        
        # Auto-size to fit content
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        
        # Use a list view with checkboxes
        self.list_view = QListView(self)
        self.setView(self.list_view)
        
        # Configure to behave like a dropdown (not a popup window)
        self.view().window().setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.view().setResizeMode(QListView.ResizeMode.Adjust)
        
        # Allow custom text display (read-only line edit)
        self.setEditable(True)
        if self.lineEdit():
            self.lineEdit().setReadOnly(True)
            self.lineEdit().setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            # Make line edit ignore mouse events so clicking triggers standard combo popup logic
            self.lineEdit().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # Don't allow closing by clicking, only by selecting
        self.list_view.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        
        # Track internal state
        self._all_years: List[str] = []
        self._updating = False
        
        # Connect signals
        self.model.itemChanged.connect(self._on_item_changed)
        
    def populate_years(self, years: List[str]) -> None:
        """Populate the dropdown with available years."""
        self._updating = True
        self._all_years = sorted(years, reverse=True)  # Most recent first
        
        self.model.clear()
        
        # Add "All Years" option
        all_item = QStandardItem("All Years")
        all_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        all_item.setData(Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        all_item.setData("__all__", Qt.ItemDataRole.UserRole)  # Special marker
        self.model.appendRow(all_item)
        
        # Add individual years
        for year in self._all_years:
            item = QStandardItem(year)
            item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setData(Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
            item.setData(year, Qt.ItemDataRole.UserRole)
            self.model.appendRow(item)
        
        self._updating = False
        self._update_display_text()
        
    def _on_item_changed(self, item: QStandardItem) -> None:
        """Handle checkbox state changes."""
        if self._updating:
            return
            
        self._updating = True
        
        # Get the item data
        item_data = item.data(Qt.ItemDataRole.UserRole)
        is_checked = item.checkState() == Qt.CheckState.Checked
        
        if item_data == "__all__":
            # "All Years" was toggled - update all items
            for i in range(1, self.model.rowCount()):
                year_item = self.model.item(i)
                year_item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
        else:
            # A year was toggled - check if all are selected
            all_selected = True
            for i in range(1, self.model.rowCount()):
                year_item = self.model.item(i)
                if year_item.checkState() != Qt.CheckState.Checked:
                    all_selected = False
                    break
            
            # Update "All Years" checkbox
            all_item = self.model.item(0)
            all_item.setCheckState(Qt.CheckState.Checked if all_selected else Qt.CheckState.Unchecked)
        
        self._updating = False
        self._update_display_text()
        self.selectionChanged.emit()
        
    def _update_display_text(self) -> None:
        """Update the display text based on selection."""
        selected_years = self.get_selected_years()
        
        if not selected_years or len(selected_years) == len(self._all_years):
            # All selected or none selected (treat as all)
            self.setCurrentText("All Years")
        else:
            # Subset selected
            self.setCurrentText("Years filtered")
        
        # Ensure cursor is at start so text truncates from right ("Years filt..." not "...rs filtered")
        if self.lineEdit():
            self.lineEdit().setCursorPosition(0)
    
    def get_selected_years(self) -> List[str]:
        """Get list of selected years. Empty list means all years."""
        selected = []
        
        # Check if "All Years" is selected
        all_item = self.model.item(0)
        if all_item and all_item.checkState() == Qt.CheckState.Checked:
            return []  # Empty list means "all years"
        
        # Otherwise, collect checked years
        for i in range(1, self.model.rowCount()):
            item = self.model.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                year = item.data(Qt.ItemDataRole.UserRole)
                if year and year != "__all__":
                    selected.append(year)
        
        return selected
    
    def set_selected_years(self, years: Optional[List[str]]) -> None:
        """Set the selected years. None or empty list means all years."""
        self._updating = True
        
        if not years or not self._all_years:
            # Select all
            for i in range(self.model.rowCount()):
                item = self.model.item(i)
                item.setCheckState(Qt.CheckState.Checked)
        else:
            # Uncheck "All Years"
            all_item = self.model.item(0)
            all_item.setCheckState(Qt.CheckState.Unchecked)
            
            # Set individual years
            years_set = set(years)
            for i in range(1, self.model.rowCount()):
                item = self.model.item(i)
                year = item.data(Qt.ItemDataRole.UserRole)
                if year in years_set:
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
        
        self._updating = False
        self._update_display_text()
    
    def is_filtering_active(self) -> bool:
        """Check if a year filter is active (not all years selected)."""
        selected = self.get_selected_years()
        return len(selected) > 0 and len(selected) < len(self._all_years)
