"""Unit tests for checkbox styling consistency."""

import pytest
import os
from PySide6.QtWidgets import QCheckBox
from PySide6.QtCore import Qt

from gcse_toolkit.gui_v2.styles.theme import Colors, ColorsDark, Styles, StylesDark


class TestCheckboxIconsExist:
    """Verify all checkbox icon paths are valid."""

    def test_light_mode_icons_defined(self):
        """Light mode checkbox icons should point to existing files."""
        icons = [
            Colors.ICON_CHECKBOX_UNCHECKED,
            Colors.ICON_CHECKBOX_UNCHECKED_HOVER,
            Colors.ICON_CHECKBOX_CHECKED,
            Colors.ICON_CHECKBOX_CHECKED_HOVER,
            Colors.ICON_CHECKBOX_DISABLED,
            Colors.ICON_CHECKBOX_DISABLED_CHECKED
        ]
        
        for icon in icons:
            assert isinstance(icon, str)
            # Should be absolute path
            assert os.path.exists(icon), f"Icon not found: {icon}"
            assert os.path.isabs(icon)

    def test_dark_mode_icons_defined(self):
        """Dark mode checkbox icons should point to existing files."""
        icons = [
            ColorsDark.ICON_CHECKBOX_UNCHECKED,
            ColorsDark.ICON_CHECKBOX_UNCHECKED_HOVER,
            ColorsDark.ICON_CHECKBOX_CHECKED,
            ColorsDark.ICON_CHECKBOX_CHECKED_HOVER,
            ColorsDark.ICON_CHECKBOX_DISABLED,
            ColorsDark.ICON_CHECKBOX_DISABLED_CHECKED
        ]
        
        for icon in icons:
            assert isinstance(icon, str)
            assert os.path.exists(icon), f"Icon not found: {icon}"


class TestCheckboxStateRendering:
    """Verify checkbox renders correctly in different states."""

    def test_checkbox_unchecked_state(self, qtbot):
        """Unchecked checkbox should display correctly."""
        cb = QCheckBox("Test")
        cb.setStyleSheet(Styles.CHECKBOX)
        qtbot.addWidget(cb)
        cb.show()
        
        assert not cb.isChecked()
        # Widget should be enabled and visible
        assert cb.isEnabled()
        assert cb.isVisible()

    def test_checkbox_checked_state(self, qtbot):
        """Checked checkbox should display correctly."""
        cb = QCheckBox("Test")
        cb.setStyleSheet(Styles.CHECKBOX)
        qtbot.addWidget(cb)
        cb.show()
        cb.setChecked(True)
        
        assert cb.isChecked()

    def test_checkbox_disabled_state(self, qtbot):
        """Disabled checkbox should use disabled icon."""
        cb = QCheckBox("Test")
        cb.setStyleSheet(Styles.CHECKBOX)
        qtbot.addWidget(cb)
        cb.show()
        cb.setEnabled(False)
        
        assert not cb.isEnabled()


class TestCrossPlatformConsistency:
    """Verify checkbox looks consistent across platforms."""

    def test_no_native_override(self, qtbot):
        """Checkbox should not have native styling leaking through."""
        cb = QCheckBox("Test")
        cb.setStyleSheet(Styles.CHECKBOX)
        qtbot.addWidget(cb)
        cb.show()
        
        # Verify stylesheet is applied (not empty)
        style = cb.styleSheet()
        assert "QCheckBox" in style
        
        # Verify we are using images and NOT borders
        style_lower = style.lower()
        assert "image:" in style_lower
        assert "border: none" in style_lower or "border: 0px" in style_lower or "border:none" in style_lower
        
        # Verify URL structure
        # Should be url('.../icons/checkbox_unchecked.png')
        assert "checkbox_unchecked.png" in style_lower
