"""
Custom Segmented Toggle Widget (Pill Style)
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRect, QPoint, QPropertyAnimation, QEasingCurve, Property, QRectF, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from gcse_toolkit.gui_v2.styles.theme import Colors, ColorsDark, Fonts, get_colors

class SegmentedToggle(QWidget):
    """
    Custom segmented toggle switch with text labels (e.g., Topics / Keywords).
    """
    
    valueChanged = Signal(int)  # Emits 0 or 1
    
    def __init__(self, left_text="Option 1", right_text="Option 2", parent=None):
        super().__init__(parent)
        
        self.left_text = left_text
        self.right_text = right_text
        self._current_index = 0  # 0 = left, 1 = right
        self._padding = 4.0
        
        # UI Settings
        # UI Settings
        import platform
        is_windows = platform.system() == "Windows"
        
        if is_windows:
            self.setFixedHeight(60)
            self.setMinimumWidth(290)
        else:
            self.setFixedHeight(50)
            self.setMinimumWidth(240)
            
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Colors - get from current theme
        self.update_theme()
        
        # Animation
        self._thumb_x = self._padding
        self._animation = QPropertyAnimation(self, b"thumb_x", self)
        self._animation.setDuration(250)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Font
        self._font = QFont()
        # Parse font string from theme or use default
        self._font.setFamily(Fonts.UI_FONT)
        self._font.setBold(True)
        self._font.setPointSize(11 if is_windows else 12)

    @Property(float)
    def thumb_x(self):
        return self._thumb_x

    @thumb_x.setter
    def thumb_x(self, x):
        self._thumb_x = x
        self.update()

    def set_index(self, index: int):
        if index not in (0, 1):
            return
        if self._current_index == index:
            return
            
        self._current_index = index
        self._animate_to_index(index)
        self.valueChanged.emit(index)
        
    def set_index_immediate(self, index: int):
        """Set index without animation - for use during initialization."""
        if index not in (0, 1):
            return
        self._animation.stop()  # Ensure any running animation is stopped
        self._current_index = index
        self._thumb_x = self._padding if index == 0 else (self.width() / 2) + self._padding
        self.update()

    def _animate_to_index(self, index):
        self._animation.stop()
        self._animation.setStartValue(self._thumb_x)
        
        # Calculate target x with symmetric padding on both halves
        target_x = self._padding if index == 0 else (self.width() / 2) + self._padding
        
        self._animation.setEndValue(target_x)
        self._animation.start()


    def mouseReleaseEvent(self, event):
        """Handle toggle click on mouse release for consistency with QPushButton."""
        if not self.isEnabled():
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        # Verify click is within widget bounds (prevents drag-off clicks)
        if not self.rect().contains(event.pos()):
            return
            
        # Determine which side was clicked
        if event.x() < self.width() / 2:
            self.set_index(0)
        else:
            self.set_index(1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Use cached colors (set by __init__ and update_theme)
        # This avoids issues with animation repaints reading stale global state
        
        # Determine colors based on enabled state
        if self.isEnabled():
            bg_color = self._bg_color
            thumb_color = self._thumb_color
            text_active = self._text_color_active
            text_inactive = self._text_color_inactive
        else:
            bg_color = self._bg_color_disabled
            thumb_color = self._thumb_color
            text_active = self._text_color_disabled
            text_inactive = self._text_color_disabled
        
        w, h = self.width(), self.height()
        padding = self._padding
        
        # Draw Background Track
        track_rect = QRectF(0, 0, w, h)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(track_rect, h/2, h/2)
        
        # Draw Thumb
        thumb_w = max(0.0, (w / 2) - 2 * padding)
        thumb_h = max(0.0, h - 2 * padding)
        
        # Target X is managed by animation property
        thumb_rect = QRectF(self._thumb_x, padding, thumb_w, thumb_h)
        
        painter.setBrush(QBrush(thumb_color))
        # Shadow simulation
        painter.setPen(QPen(QColor(0, 0, 0, 15), 1))
        painter.drawRoundedRect(thumb_rect, thumb_h/2, thumb_h/2)
        
        # Draw Text
        painter.setFont(self._font)
        
        # Left Text
        left_rect = QRectF(0, 0, w/2, h)
        if self._current_index == 0:
            painter.setPen(text_active)
        else:
            painter.setPen(text_inactive)
        painter.drawText(left_rect, Qt.AlignmentFlag.AlignCenter, self.left_text)
        
        # Right Text
        right_rect = QRectF(w/2, 0, w/2, h)
        if self._current_index == 1:
            painter.setPen(text_active)
        else:
            painter.setPen(text_inactive)
        painter.drawText(right_rect, Qt.AlignmentFlag.AlignCenter, self.right_text)




    def resizeEvent(self, event):
        """Keep thumb aligned when the widget is resized."""
        self._thumb_x = self._padding if self._current_index == 0 else (self.width() / 2) + self._padding
        super().resizeEvent(event)

    def update_theme(self):
        """Update colors when theme changes."""
        C = get_colors()
        is_dark = C is ColorsDark
        
        # Light mode: Blue Track, White Text (inactive), White Thumb, Blue Text (active)
        # Dark mode: Surface Pill, Normal Text
        if not is_dark:
            self._bg_color = QColor(C.PRIMARY_BLUE)           # Blue Track
            self._thumb_color = QColor(C.SURFACE)             # White Thumb
            self._text_color_active = QColor(C.PRIMARY_BLUE)  # Blue Text on Thumb
            self._text_color_inactive = QColor(C.TEXT_ON_PRIMARY) # White Text on Track
        else:
            self._bg_color = QColor(C.SELECTION_BG)
            self._thumb_color = QColor(C.SURFACE)
            self._text_color_active = QColor(C.PRIMARY_BLUE)
            self._text_color_inactive = QColor(C.TEXT_PRIMARY)
            
        self._border_color = QColor(C.BORDER)
        
        # Disabled colors
        self._bg_color_disabled = QColor(C.DISABLED_BG)
        self._text_color_disabled = QColor(C.TEXT_DISABLED)
        self.update()
