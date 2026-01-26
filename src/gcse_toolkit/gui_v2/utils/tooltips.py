"""
Shared tooltip helpers for GUI v2.

Light tooltip styling to match the app palette:
- soft grey background
- white text
- rounded corners
- no shadow, no arrow, no custom window
"""
from __future__ import annotations

from typing import Optional, Union

from PySide6.QtCore import QObject, QEvent, QPoint, QTimer, Qt
from PySide6.QtGui import QAction, QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication, QToolTip, QTreeWidgetItem, QWidget, QLabel
from PySide6.QtGui import QCursor

from gcse_toolkit.gui_v2.styles.theme import Colors

# Light palette aligned with the global stylesheet
BG_COLOR = Colors.BACKGROUND
TEXT_COLOR = Colors.TEXT_PRIMARY


# ---------------------------------------------------------------------------
# Global font + style for QToolTip
# ---------------------------------------------------------------------------

def init_tooltips() -> None:
    """Apply the light tooltip theme."""
    font = QFont()
    font.setPointSize(11)
    font.setWeight(QFont.Weight.Medium)

    QApplication.setFont(font, "QToolTip")
    QToolTip.setFont(font)

    # Older PySide6 builds may not expose QToolTip.setStyleSheet; fall back to palette.
    if hasattr(QToolTip, "setStyleSheet"):
        QToolTip.setStyleSheet(
            """
            QToolTip {
                background-color: """ + BG_COLOR + """;
                color: """ + TEXT_COLOR + """;
                border-radius: 10px;
                padding: 8px 12px;
            }
            """
        )
    else:
        palette = QToolTip.palette()
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_COLOR))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_COLOR))
        QToolTip.setPalette(palette)


# ---------------------------------------------------------------------------
# Delayed hover filter (controls timing)
# ---------------------------------------------------------------------------

class _DelayedTooltipFilter(QObject):
    def __init__(self, widget: QWidget, text: str, delay_ms: int) -> None:
        super().__init__(widget)
        self.widget = widget
        self.text = text
        self.delay_ms = max(0, delay_ms)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._show)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self.widget:
            et = event.type()

            if et == QEvent.Type.Enter:
                self._timer.start(self.delay_ms)

            elif et in (QEvent.Type.Leave, QEvent.Type.MouseButtonPress):
                self._timer.stop()
                QToolTip.hideText()
                FluentTooltip.instance().hide_tooltip()

            elif et == QEvent.Type.ToolTip:
                return True

        return super().eventFilter(obj, event)

    def _show(self) -> None:
        if self.text and self.widget.isVisible():
            FluentTooltip.instance().show_for(self.widget, self.text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_tooltip(
    target: Union[QWidget, QTreeWidgetItem, QAction],
    text: Optional[str],
    delay_ms: int = 1000,
) -> None:
    if not text:
        return

    if isinstance(target, QTreeWidgetItem):
        target.setToolTip(0, text)
        return

    if isinstance(target, QAction):
        target.setToolTip(text)
        return

    if isinstance(target, QWidget):
        target.setToolTip(text)
        target.installEventFilter(_DelayedTooltipFilter(target, text, delay_ms))
        return

    setter = getattr(target, "setToolTip", None)
    if callable(setter):
        setter(text)


# ---------------------------------------------------------------------------
# Wrapper around QToolTip (keeps old API)
# ---------------------------------------------------------------------------

class FluentTooltip(QLabel):
    _instance: "FluentTooltip | None" = None

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.ToolTip)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        # Apply the same styling as the global tooltip
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {BG_COLOR};
                color: {TEXT_COLOR};
                padding: 6px 8px;
                border: 1px solid #454545;
            }}
        """)
        
        # Ensure it looks right
        self.setMargin(2) 
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)

    @classmethod
    def instance(cls) -> "FluentTooltip":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def hide_tooltip(self) -> None:
        self.hide()

    def show_for(
        self,
        anchor: QWidget,
        text: str,
        preferred_side: Qt.Edge = Qt.TopEdge,
    ) -> None:
        if not text or not anchor.isVisible():
            return

        self.setText(text)
        self.adjustSize()

        # Position relative to cursor
        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos)
        if not screen:
            screen = QApplication.primaryScreen()
        
        screen_geo = screen.availableGeometry()
        
        # Default offset
        x = cursor_pos.x() + 16
        y = cursor_pos.y() + 16
        
        # Check right edge
        if x + self.width() > screen_geo.right():
            # Flip to left of cursor if it overflows right
            x = cursor_pos.x() - self.width() - 8
            
        # Check bottom edge
        if y + self.height() > screen_geo.bottom():
            # Flip to above cursor if it overflows bottom
            y = cursor_pos.y() - self.height() - 8
            
        # Final safety check for left/top (ensure not off-screen entirely)
        x = max(screen_geo.left(), x)
        y = max(screen_geo.top(), y)

        self.move(x, y)
        self.show()
