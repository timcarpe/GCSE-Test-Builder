"""
Exam code selection dialog for GUI v2.
Ported from v1 GUI's ExamSelectionDialog.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QCheckBox, QScrollArea, QWidget, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt

from gcse_toolkit.gui_v2.styles.theme import get_colors, get_styles, Fonts
from gcse_toolkit.gui_v2.utils.tooltips import apply_tooltip


class ExamSelectionDialog(QDialog):
    """Modal dialog allowing users to select exam codes to process."""
    
    def __init__(
        self,
        parent,
        code_map: dict[str, list[Path]],
        display_names: dict[str, str]
    ):
        super().__init__(parent)
        self.setWindowTitle("Select Exam Codes")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        # Get current theme colors/styles
        C = get_colors()
        S = get_styles()
        
        self.result: Optional[list[str]] = None
        self._vars: dict[str, bool] = {}
        self._checkboxes: dict[str, QCheckBox] = {}
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Heading
        heading = QLabel("Choose Exam Codes to Extract:")
        heading.setStyleSheet(f"font-size: {Fonts.H2}; font-weight: {Fonts.WEIGHT_BOLD}; color: {C.TEXT_PRIMARY};")
        layout.addWidget(heading)
        
        # Scrollable list of checkboxes
        codes = sorted(code_map.keys())
        if codes:
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QFrame.Shape.NoFrame)
            scroll_area.setStyleSheet(f"""
                QScrollArea {{
                    background-color: {C.BACKGROUND};
                    border: 1px solid {C.BORDER};
                    border-radius: 4px;
                }}
            """)
            
            list_widget = QWidget()
            list_layout = QVBoxLayout(list_widget)
            list_layout.setContentsMargins(8, 8, 8, 8)
            list_layout.setSpacing(8)
            
            # Apply background to list widget to ensure it matches
            list_widget.setStyleSheet(f"background-color: {C.BACKGROUND};")
            
            for code in codes:
                friendly = display_names.get(code, "")
                suffix = f" – {friendly}" if friendly else ""
                count = len(code_map.get(code, []))
                label = f"{code}{suffix} ({count} PDF{'s' if count != 1 else ''})"
                
                checkbox = QCheckBox(label)
                checkbox.setChecked(True)
                checkbox.setStyleSheet(S.CHECKBOX)
                checkbox.stateChanged.connect(lambda state, c=code: self._on_checkbox_changed(c, state))
                
                list_layout.addWidget(checkbox)
                self._vars[code] = True
                self._checkboxes[code] = checkbox
            
            list_layout.addStretch()
            scroll_area.setWidget(list_widget)
            layout.addWidget(scroll_area, stretch=1)
            
            # Selection controls
            controls_row = QHBoxLayout()
            controls_row.setSpacing(8)
            
            select_all_btn = QPushButton("Select All")
            select_all_btn.setStyleSheet(S.BUTTON_SECONDARY)
            select_all_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            select_all_btn.clicked.connect(lambda: self._set_all(True))
            controls_row.addWidget(select_all_btn)
            apply_tooltip(select_all_btn, "Select every exam code shown in the list.")

            clear_btn = QPushButton("Clear")
            clear_btn.setStyleSheet(S.BUTTON_SECONDARY)
            clear_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            clear_btn.clicked.connect(lambda: self._set_all(False))
            controls_row.addWidget(clear_btn)
            apply_tooltip(clear_btn, "Clear every selection so you can choose specific exams.")
            
            controls_row.addStretch()
            layout.addLayout(controls_row)
        else:
            empty = QLabel("No supported exam codes found in the exams directory.")
            empty.setStyleSheet(f"color: {C.TEXT_SECONDARY};")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
        
        # Dialog buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addStretch()
        
        ok_btn = QPushButton("OK")
        ok_btn.setStyleSheet(S.BUTTON_PRIMARY)
        ok_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        ok_btn.clicked.connect(self._on_ok)
        button_row.addWidget(ok_btn)
        apply_tooltip(ok_btn, "Confirm the selected exam codes and continue.")

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(S.BUTTON_SECONDARY)
        cancel_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        cancel_btn.clicked.connect(self._on_cancel)
        button_row.addWidget(cancel_btn)
        apply_tooltip(cancel_btn, "Close without making any changes.")
        
        layout.addLayout(button_row)
        
        # Apply generic dialog styling
        self.setStyleSheet(f"background-color: {C.BACKGROUND}; color: {C.TEXT_PRIMARY};")

    def _on_checkbox_changed(self, code: str, state: int):
        """Handle checkbox state changes."""
        self._vars[code] = state == Qt.CheckState.Checked.value
    
    def _set_all(self, value: bool):
        """Select or deselect all checkboxes."""
        for code, checkbox in self._checkboxes.items():
            checkbox.setChecked(value)
            self._vars[code] = value
    
    def _on_ok(self):
        """Confirm selection and close dialog."""
        selected = [code for code, checked in self._vars.items() if checked]
        self.result = selected
        self.accept()
    
    def _on_cancel(self):
        """Cancel and close dialog."""
        self.result = None
        self.reject()
