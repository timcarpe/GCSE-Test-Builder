"""
Multi-select dropdown widget with checkboxes for paper number filtering.
"""
from typing import List, Optional
from PySide6.QtWidgets import QComboBox, QListView
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem


class MultiSelectPaperFilter(QComboBox):
    """Multi-select dropdown with checkboxes for paper number filtering."""
    
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
        self._all_papers: List[int] = []
        self._updating = False
        
        # Connect signals
        self.model.itemChanged.connect(self._on_item_changed)
        
    def populate_papers(self, papers: List[int]) -> None:
        """Populate the dropdown with available paper numbers."""
        self._updating = True
        self._all_papers = sorted(papers)  # Ascending order (1, 2, 3)
        
        self.model.clear()
        
        # Add "All Papers" option
        all_item = QStandardItem("All Papers")
        all_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        all_item.setData(Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        all_item.setData("__all__", Qt.ItemDataRole.UserRole)  # Special marker
        self.model.appendRow(all_item)
        
        # Add individual papers
        for paper in self._all_papers:
            item = QStandardItem(f"Paper {paper}")
            item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setData(Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
            item.setData(paper, Qt.ItemDataRole.UserRole)
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
            # "All Papers" was toggled - update all items
            for i in range(1, self.model.rowCount()):
                paper_item = self.model.item(i)
                paper_item.setCheckState(Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
        else:
            # A paper was toggled - check if all are selected
            all_selected = True
            for i in range(1, self.model.rowCount()):
                paper_item = self.model.item(i)
                if paper_item.checkState() != Qt.CheckState.Checked:
                    all_selected = False
                    break
            
            # Update "All Papers" checkbox
            all_item = self.model.item(0)
            all_item.setCheckState(Qt.CheckState.Checked if all_selected else Qt.CheckState.Unchecked)
        
        self._updating = False
        self._update_display_text()
        self.selectionChanged.emit()
        
    def _update_display_text(self) -> None:
        """Update the display text based on selection."""
        selected_papers = self.get_selected_papers()
        
        if not selected_papers or len(selected_papers) == len(self._all_papers):
            # All selected or none selected (treat as all)
            self.setCurrentText("All Papers")
        elif len(selected_papers) == 1:
            # Single paper selected
            self.setCurrentText(f"Paper {selected_papers[0]}")
        else:
            # Subset selected
            self.setCurrentText("Papers filtered")
        
        # Ensure cursor is at start so text truncates from right
        if self.lineEdit():
            self.lineEdit().setCursorPosition(0)
    
    def get_selected_papers(self) -> List[int]:
        """Get list of selected paper numbers. Empty list means all papers."""
        selected = []
        
        # Check if "All Papers" is selected
        all_item = self.model.item(0)
        if all_item and all_item.checkState() == Qt.CheckState.Checked:
            return []  # Empty list means "all papers"
        
        # Otherwise, collect checked papers
        for i in range(1, self.model.rowCount()):
            item = self.model.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                paper = item.data(Qt.ItemDataRole.UserRole)
                if paper and paper != "__all__":
                    selected.append(paper)
        
        return selected
    
    def set_selected_papers(self, papers: Optional[List[int]]) -> None:
        """Set the selected papers. None or empty list means all papers."""
        self._updating = True
        
        if not papers or not self._all_papers:
            # Select all
            for i in range(self.model.rowCount()):
                item = self.model.item(i)
                item.setCheckState(Qt.CheckState.Checked)
        else:
            # Uncheck "All Papers"
            all_item = self.model.item(0)
            all_item.setCheckState(Qt.CheckState.Unchecked)
            
            # Set individual papers
            papers_set = set(papers)
            for i in range(1, self.model.rowCount()):
                item = self.model.item(i)
                paper = item.data(Qt.ItemDataRole.UserRole)
                if paper in papers_set:
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
        
        self._updating = False
        self._update_display_text()
    
    def is_filtering_active(self) -> bool:
        """Check if a paper filter is active (not all papers selected)."""
        selected = self.get_selected_papers()
        return len(selected) > 0 and len(selected) < len(self._all_papers)
