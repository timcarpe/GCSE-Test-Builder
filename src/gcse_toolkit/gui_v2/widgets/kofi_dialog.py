"""
Ko-Fi Support Dialog for footer disable confirmation.

Shows a prompt asking users to consider supporting development before
disabling the footer. Provides options to open Ko-Fi or proceed with disable.
"""

import webbrowser
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


# Ko-Fi URL - update with actual profile
KOFI_URL = "https://ko-fi.com/timcarpe"


class KoFiSupportDialog(QDialog):
    """Dialog asking for support when disabling footer."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Support GCSE Test Builder")
        self.setFixedWidth(420)
        self.setModal(True)
        
        # Track if user chose to disable footer
        self._should_disable = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Title
        title = QLabel("Support Development")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Message
        message = QLabel(
            "If you find GCSE Test Builder useful, please consider supporting "
            "its development! Your contribution helps keep the project "
            "maintained and free for everyone."
        )
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # Open Ko-Fi / Disable button
        kofi_btn = QPushButton("Open Ko-Fi / Disable Footer")
        kofi_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        kofi_btn.setDefault(True)
        kofi_btn.clicked.connect(self._on_kofi_clicked)
        button_layout.addWidget(kofi_btn)
        
        layout.addLayout(button_layout)
    
    def _on_kofi_clicked(self):
        """Open Ko-Fi in browser and accept dialog."""
        try:
            webbrowser.open(KOFI_URL)
        except Exception:
            pass  # Ignore browser open failures
        self._should_disable = True
        self.accept()
    
    def should_disable_footer(self) -> bool:
        """Returns True if footer should be disabled after dialog closes."""
        return self._should_disable
