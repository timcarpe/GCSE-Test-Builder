"""
Folder browser widget for the Extract tab.
"""
from pathlib import Path
from typing import Optional, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, 
    QPushButton, QHeaderView, QMessageBox, QSizePolicy, QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QIcon, QFont, QPainter, QColor, QPalette

from gcse_toolkit.gui_v2.styles.theme import Colors, Styles, Fonts, get_colors, get_styles
from gcse_toolkit.gui_v2.utils.tooltips import apply_tooltip
from gcse_toolkit.gui_v2.utils.icons import MaterialIcons

class FolderBrowser(QWidget):
    folder_selected = Signal(Path)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        self.title_label = QLabel("Extract Question Slice Browser")
        font = self.title_label.font()
        font.setWeight(QFont.Weight.Medium)
        font.setPointSize(14) # Slightly larger
        self.title_label.setFont(font)
        self.layout.addWidget(self.title_label)
        
        # Tree Widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(20) # Match TopicSelector
        self.tree.setFocusPolicy(Qt.StrongFocus) # Ensure it can grab focus
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        
        self.layout.addWidget(self.tree)
        apply_tooltip(self.tree, "Browse extracted slices. Select a folder to open it.")
        
        # Open Folder Button
        self.open_btn = QPushButton("Open Folder")
        self.open_btn.setIcon(MaterialIcons.folder())
        self.open_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.open_btn.clicked.connect(self._on_open_clicked)
        self.layout.addWidget(self.open_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        apply_tooltip(self.open_btn, "Open the currently selected folder in the tree.")

        # Apply initial theme
        self.update_theme()
        
        self.root_path: Optional[Path] = None
        self.nodes = {} # Path -> QTreeWidgetItem

    def set_root_path(self, path: Path):
        self.root_path = path
        self.refresh()

    def refresh(self):
        self.tree.clear()
        self.nodes.clear()
        
        if not self.root_path or not self.root_path.exists():
            return
            
        root_item = QTreeWidgetItem(self.tree)
        # We don't set text on item, we use widget
        # Create label for root
        # Revert to standard item text to ensure hover effects work
        root_item.setText(0, self.root_path.name)
        self.tree.setItemWidget(root_item, 0, None) # Clear any existing widget
        
        self._add_children(self.root_path, root_item)

    def _add_children(self, parent_path: Path, parent_item: QTreeWidgetItem, depth=0):
        if depth > 3: # Limit depth
            return
            
        try:
            # Sort: Directories first, then files
            items = sorted(
                [p for p in parent_path.iterdir() if not p.name.startswith(".")],
                key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except OSError:
            return

        for item_path in items:
            item_node = QTreeWidgetItem(parent_item)
            item_node.setText(0, item_path.name)
            item_node.setData(0, Qt.UserRole, str(item_path))
            self.nodes[item_path] = item_node
            
            if item_path.is_dir():
                self._add_children(item_path, item_node, depth + 1)

    def _on_selection_changed(self):
        self.tree.setFocus() # Force focus to ensure active selection color
        items = self.tree.selectedItems()
        if items:
            path_str = items[0].data(0, Qt.UserRole)
            if path_str:
                self.folder_selected.emit(Path(path_str))

    def _on_open_clicked(self):
        """Open selected folder using shared utility."""
        from gcse_toolkit.gui_v2.utils.helpers import open_folder_in_browser
        
        target: Optional[Path] = None
        items = self.tree.selectedItems()
        if items:
            path_str = items[0].data(0, Qt.UserRole)
            if path_str:
                target = Path(path_str)
        elif self.root_path:
            target = self.root_path

        if not target:
            QMessageBox.information(self, "No folder selected", "Select a folder to open.")
            return

        success, error = open_folder_in_browser(target)
        if not success and error:
            QMessageBox.warning(self, "Error", error)

    def update_theme(self):
        """Update styles when theme changes."""
        C = get_colors()
        S = get_styles()
        self.title_label.setStyleSheet(f"color: {C.TEXT_PRIMARY};")
        
        # Use shared style
        # TODO: Fix hover color. Currently uses Colors.BACKGROUND which appears black in dark mode.
        # User reported "black on hover, blue on selection".
        # Consider using Colors.HOVER in the TREE_WIDGET style definition or overriding here.
        self.tree.setStyleSheet(S.TREE_WIDGET)
        
        self.open_btn.setStyleSheet(S.BUTTON_SECONDARY)
        self.open_btn.setIcon(MaterialIcons.folder()) # Refresh icon color if needed
