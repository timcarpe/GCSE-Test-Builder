"""
Three-State Button Group Widget

A horizontal button group with three mutually exclusive options,
designed for settings selection (e.g., PDF / ZIP / BOTH output formats).
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup, QSizePolicy
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

from gcse_toolkit.gui_v2.styles.theme import get_colors, Fonts


class ThreeStateButtonGroup(QWidget):
    """
    Horizontal button group with three mutually exclusive options.
    
    Displays as a pill-shaped container with three equal-width buttons.
    Active button has solid blue fill; inactive buttons are transparent.
    
    Signals:
        valueChanged(int): Emitted when selection changes (0, 1, or 2)
    """
    
    valueChanged = Signal(int)
    
    def __init__(self, option1: str, option2: str, option3: str, parent=None):
        super().__init__(parent)
        
        self._options = (option1, option2, option3)
        self._selected_index = 0
        
        self.setFixedHeight(32)
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        
        # Layout
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        
        # Button group for mutual exclusivity
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        
        # Create buttons
        self._buttons = []
        for i, option in enumerate(self._options):
            btn = QPushButton(option)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.setMinimumWidth(50)
            self._button_group.addButton(btn, i)
            self._layout.addWidget(btn)
            self._buttons.append(btn)
        
        # Set initial selection
        self._buttons[0].setChecked(True)
        
        # Connect signals
        self._button_group.idClicked.connect(self._on_button_clicked)
        
        # Apply initial styling
        self.update_theme()
    
    def value(self) -> int:
        """Get current selection index (0, 1, or 2)."""
        return self._selected_index
    
    def setValue(self, index: int) -> None:
        """Set current selection by index."""
        if 0 <= index < 3 and index != self._selected_index:
            self._selected_index = index
            self._buttons[index].setChecked(True)
            self._update_button_styles()
    
    def options(self) -> tuple:
        """Return the three option labels."""
        return self._options
    
    def _on_button_clicked(self, button_id: int) -> None:
        if button_id != self._selected_index:
            self._selected_index = button_id
            self._update_button_styles()
            self.valueChanged.emit(button_id)
    
    def _update_button_styles(self) -> None:
        C = get_colors()
        
        for i, btn in enumerate(self._buttons):
            is_active = (i == self._selected_index)
            is_first = (i == 0)
            is_last = (i == 2)
            
            # Border radius - swap to have inner corners rounded
            if is_first:
                # PDF: right corners rounded (inner edge)
                radius = "border-top-right-radius: 16px; border-bottom-right-radius: 16px;"
            elif is_last:
                # BOTH: left corners rounded (inner edge)
                radius = "border-top-left-radius: 16px; border-bottom-left-radius: 16px;"
            else:
                # ZIP: completely square
                radius = "border-radius: 0;"
            
            # Use negative margin to overlap borders for separator effect
            margin = "margin-right: -1px;" if not is_last else ""
            
            if is_active:
                style = f"""
                    QPushButton {{
                        background-color: {C.PRIMARY_BLUE};
                        color: {C.TEXT_ON_PRIMARY};
                        border: 1px solid {C.PRIMARY_BLUE};
                        {radius}
                        {margin}
                        padding: 4px 14px;
                        font-weight: {Fonts.WEIGHT_MEDIUM};
                    }}
                    QPushButton:hover {{
                        background-color: {C.PRIMARY_BLUE_HOVER};
                    }}
                """
            else:
                style = f"""
                    QPushButton {{
                        background-color: {C.SURFACE};
                        color: {C.TEXT_PRIMARY};
                        border: 1px solid {C.BORDER};
                        {radius}
                        {margin}
                        padding: 4px 14px;
                        font-weight: {Fonts.WEIGHT_MEDIUM};
                    }}
                    QPushButton:hover {{
                        background-color: {C.HOVER};
                    }}
                """
            btn.setStyleSheet(style)
    
    def update_theme(self) -> None:
        """Update colors when theme changes."""
        self._update_button_styles()
