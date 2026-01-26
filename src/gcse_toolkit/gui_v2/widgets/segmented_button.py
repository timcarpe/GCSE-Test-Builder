"""
Custom Segmented Button Widget
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup, QFrame
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QBrush

from gcse_toolkit.gui_v2.styles.theme import Colors, Fonts, get_colors

class SegmentedButton(QFrame):
    """
    A segmented button group acting as a tab switcher.
    Design: Rounded top corners, 1dp outline, 40dp height.
    """
    
    valueChanged = Signal(int)  # Emits index (0 or 1)
    
    def __init__(self, left_text="Option 1", right_text="Option 2", parent=None):
        super().__init__(parent)
        
        self.setFixedHeight(40)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.idClicked.connect(self.valueChanged.emit)
        
        # Left Button
        self.btn_left = QPushButton(left_text)
        self.btn_left.setCheckable(True)
        self.btn_left.setChecked(True)
        self.btn_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self.group.addButton(self.btn_left, 0)
        self.layout.addWidget(self.btn_left)
        
        # Right Button
        self.btn_right = QPushButton(right_text)
        self.btn_right.setCheckable(True)
        self.btn_right.setCursor(Qt.CursorShape.PointingHandCursor)
        self.group.addButton(self.btn_right, 1)
        self.layout.addWidget(self.btn_right)
        
        # Apply Styles
        self._update_styles()
        
    def _update_styles(self):
        # Get current theme colors
        C = get_colors()
        
        # Common base style - use C.SURFACE for inactive state to match text boxes
        base_style = f"""
            QPushButton {{
                height: 40px;
                border: 1px solid {C.BORDER};
                font-family: {Fonts.UI_FONT.split(',')[0]};
                font-size: {Fonts.BODY};
                font-weight: {Fonts.WEIGHT_MEDIUM};
                background-color: {C.SURFACE};
                color: {C.TEXT_PRIMARY};
                border-bottom: 1px solid {C.BORDER};
            }}
            QPushButton:hover {{
                background-color: {C.HOVER};
            }}
            QPushButton:checked {{
                background-color: {C.SELECTION_BG};
                color: {C.SELECTION_TEXT};
                border-bottom: 2px solid {C.PRIMARY_BLUE};
            }}
            QPushButton:disabled {{
                background-color: {C.DISABLED_BG};
                color: {C.TEXT_DISABLED};
                border-color: {C.DISABLED_BG};
            }}
        """
        
        # Left Button Specifics (Top-Left Radius, no right radius for straight middle)
        left_style = base_style + """
            QPushButton {
                border-top-left-radius: 8px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                border-right: none; /* Avoid double border */
            }
        """
        
        # Right Button Specifics (Top-Right Radius, no left radius for straight middle)
        right_style = base_style + f"""
            QPushButton {{
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 0px;
                border-left: 1px solid {C.BORDER};
            }}
        """
        
        self.btn_left.setStyleSheet(left_style)
        self.btn_right.setStyleSheet(right_style)

    def set_index(self, index: int):
        if index == 0:
            self.btn_left.setChecked(True)
        elif index == 1:
            self.btn_right.setChecked(True)
        self.valueChanged.emit(index)

    def update_theme(self):
        """Update styles when theme changes."""
        self._update_styles()
