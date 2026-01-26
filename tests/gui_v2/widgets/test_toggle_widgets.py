"""Unit tests for button click responsiveness."""

import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QPushButton
from PySide6.QtTest import QTest

from gcse_toolkit.gui_v2.widgets.segmented_toggle import SegmentedToggle
from gcse_toolkit.gui_v2.widgets.toggle_switch import ToggleSwitch


class TestSegmentedToggleClick:
    """Tests for SegmentedToggle click registration."""

    def test_single_click_registers_left(self, qtbot):
        """Single click on left side should select left option."""
        toggle = SegmentedToggle("Left", "Right")
        qtbot.addWidget(toggle)
        toggle.show()
        toggle.set_index(1)  # Start on right
        
        # Simulate single click on left side
        left_point = QPoint(toggle.width() // 4, toggle.height() // 2)
        QTest.mouseClick(toggle, Qt.MouseButton.LeftButton, pos=left_point)
        
        assert toggle._current_index == 0

    def test_single_click_registers_right(self, qtbot):
        """Single click on right side should select right option."""
        toggle = SegmentedToggle("Left", "Right")
        qtbot.addWidget(toggle)
        toggle.show()
        toggle.set_index(0)  # Start on left
        
        # Simulate single click on right side
        right_point = QPoint(3 * toggle.width() // 4, toggle.height() // 2)
        QTest.mouseClick(toggle, Qt.MouseButton.LeftButton, pos=right_point)
        
        assert toggle._current_index == 1

    def test_click_emits_signal(self, qtbot):
        """Click should emit valueChanged signal."""
        toggle = SegmentedToggle("Left", "Right")
        qtbot.addWidget(toggle)
        toggle.show()
        
        with qtbot.waitSignal(toggle.valueChanged, timeout=1000) as blocker:
            right_point = QPoint(3 * toggle.width() // 4, toggle.height() // 2)
            QTest.mouseClick(toggle, Qt.MouseButton.LeftButton, pos=right_point)
        
        assert blocker.args == [1]

    def test_drag_off_does_not_toggle(self, qtbot):
        """Mouse release outside widget should not toggle."""
        toggle = SegmentedToggle("Left", "Right")
        qtbot.addWidget(toggle)
        toggle.show()
        toggle.set_index(0)  # Start on left
        
        # Press inside, release outside
        center = QPoint(toggle.width() // 2, toggle.height() // 2)
        outside = QPoint(toggle.width() * 2, toggle.height() // 2)
        
        QTest.mousePress(toggle, Qt.MouseButton.LeftButton, pos=center)
        # Move mouse outside and release
        QTest.mouseRelease(toggle, Qt.MouseButton.LeftButton, pos=outside)
        
        # Should remain on left (index 0)
        assert toggle._current_index == 0


class TestToggleSwitchClick:
    """Tests for ToggleSwitch click registration."""

    def test_single_click_toggles_state(self, qtbot):
        """Single click should toggle the switch."""
        switch = ToggleSwitch()
        qtbot.addWidget(switch)
        switch.show()
        switch.setChecked(False)
        
        center = QPoint(switch.width() // 2, switch.height() // 2)
        QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=center)
        
        assert switch.isChecked() is True

    def test_drag_off_does_not_toggle(self, qtbot):
        """Mouse release outside widget should not toggle."""
        switch = ToggleSwitch()
        qtbot.addWidget(switch)
        switch.show()
        switch.setChecked(False)
        
        # Press inside, release outside
        center = QPoint(switch.width() // 2, switch.height() // 2)
        outside = QPoint(switch.width() * 2, switch.height() // 2)
        
        QTest.mousePress(switch, Qt.MouseButton.LeftButton, pos=center)
        # Move mouse outside and release
        QTest.mouseRelease(switch, Qt.MouseButton.LeftButton, pos=outside)
        
        assert switch.isChecked() is False


class TestQPushButtonClick:
    """Tests for standard QPushButton responsiveness."""

    def test_button_click_fires_immediately(self, qtbot):
        """Standard button click should fire without delay."""
        button = QPushButton("Test")
        qtbot.addWidget(button)
        button.show()
        
        clicked = MagicMock()
        button.clicked.connect(clicked)
        
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        
        clicked.assert_called_once()
