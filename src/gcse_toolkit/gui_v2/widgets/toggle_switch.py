"""
Custom Toggle Switch Widget (iOS Style)
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRect, QPropertyAnimation, QEasingCurve, Property, QRectF
from PySide6.QtGui import QPainter, QColor, QBrush, QPen

from gcse_toolkit.gui_v2.styles.theme import Colors, get_colors

class ToggleSwitch(QWidget):
    """
    Custom toggle switch widget.
    """
    
    toggled = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._checked = False
        self._thumb_position = 0.0  # 0.0 (left) to 1.0 (right)
        
        self.setFixedSize(44, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Colors - get from current theme
        self.update_theme()
        
        # Animation
        self._thumb_pos = 0.0  # 0.0 = Left (Off), 1.0 = Right (On)
        self._animation = QPropertyAnimation(self, b"thumb_pos", self)
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        # Connect state change to animation
        self.toggled.connect(self._start_animation)
        
        # Initial state
        self._thumb_pos = 1.0 if self._checked else 0.0

    @Property(float)
    def thumb_pos(self):
        return self._thumb_pos

    @thumb_pos.setter
    def thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()
        
    def isChecked(self):
        return self._checked
        
    def setChecked(self, checked: bool):
        if self._checked != checked:
            self._checked = checked
            self.toggled.emit(checked)
            self._start_animation(checked)
            self.update()

    def _start_animation(self, state):
        self._animation.stop()
        end_val = 1.0 if self._checked else 0.0
        self._animation.setStartValue(self._thumb_pos)
        self._animation.setEndValue(end_val)
        self._animation.start()

    def mouseReleaseEvent(self, event):
        if not self.isEnabled():
            return
            
        if event.button() == Qt.MouseButton.LeftButton:
            # Verify click is within widget bounds (prevents drag-off clicks)
            if self.rect().contains(event.pos()):
                self.setChecked(not self._checked)
            
    # Replaced hitButton with mouseReleaseEvent for QWidget based toggle

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Geometry
        w, h = self.width(), self.height()
        track_h = h
        track_w = w
        thumb_size = h - 4
        
        # Draw Track
        track_rect = QRectF(0, 0, track_w, track_h)
        track_radius = track_h / 2
        
        # Interpolate color
        if not self.isEnabled():
            color = self._track_color_disabled
        elif self.isChecked():
            color = self._track_color_on
        else:
            # If animating, we could interpolate, but simple switch is usually fine
            # Or use thumb_pos to interpolate
            color = self._track_color_off
            
        # For smoother color transition during animation (optional)
        # r = self._track_color_off.red() + (self._track_color_on.red() - self._track_color_off.red()) * self._thumb_pos
        # g = self._track_color_off.green() + (self._track_color_on.green() - self._track_color_off.green()) * self._thumb_pos
        # b = self._track_color_off.blue() + (self._track_color_on.blue() - self._track_color_off.blue()) * self._thumb_pos
        # color = QColor(int(r), int(g), int(b))
        
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(track_rect, track_radius, track_radius)
        
        # Draw Thumb
        # Calculate x position based on thumb_pos (0.0 to 1.0)
        padding = 2
        min_x = padding
        max_x = w - thumb_size - padding
        thumb_x = min_x + (max_x - min_x) * self._thumb_pos
        thumb_y = padding
        
        thumb_rect = QRectF(thumb_x, thumb_y, thumb_size, thumb_size)
        painter.setBrush(QBrush(self._thumb_color))
        # Add subtle shadow or border to thumb
        painter.setPen(QPen(QColor(0, 0, 0, 20), 1)) 
        painter.drawEllipse(thumb_rect)
    def update_theme(self):
        """Update colors when theme changes."""
        C = get_colors()
        self._track_color_off = QColor(C.BORDER)
        self._track_color_on = QColor(C.TOGGLE_BG)
        self._thumb_color = QColor(C.SURFACE)
        self._text_color = QColor(C.TEXT_PRIMARY)
        self._track_color_disabled = QColor(C.DISABLED_BG)
        self.update()
