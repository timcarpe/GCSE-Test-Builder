"""
Builder Overlay Widget.

Provides a modern loading overlay for the exam generation process
with an animated spinner and pulsing static text.
"""
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsOpacityEffect
)
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, Property, QEasingCurve, QSequentialAnimationGroup, QParallelAnimationGroup
)
from PySide6.QtGui import QPainter, QColor, QPen

from gcse_toolkit.gui_v2.styles.theme import get_colors


class SpinnerWidget(QWidget):
    """Animated circular spinner with modern arc design."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(64, 64)
        self._angle = 0
        
        # Create rotation animation
        self._animation = QPropertyAnimation(self, b"angle")
        self._animation.setDuration(1000)
        self._animation.setStartValue(0)
        self._animation.setEndValue(360)
        self._animation.setLoopCount(-1)  # Infinite loop
        self._animation.setEasingCurve(QEasingCurve.Type.Linear)
    
    def start(self):
        """Start the spinner animation."""
        self._animation.start()
    
    def stop(self):
        """Stop the spinner animation."""
        self._animation.stop()
    
    @Property(int)
    def angle(self):
        return self._angle
    
    @angle.setter
    def angle(self, value: int):
        self._angle = value
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        C = get_colors()
        
        # Draw background track (subtle ring)
        track_pen = QPen(QColor(255, 255, 255, 40), 4)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        rect = self.rect().adjusted(6, 6, -6, -6)
        painter.drawEllipse(rect)
        
        # Draw arc (spinner)
        arc_pen = QPen(QColor(C.PRIMARY_BLUE), 4)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        
        # Draw a 90-degree arc that rotates
        painter.drawArc(rect, self._angle * 16, 90 * 16)


class CharacterLabel(QLabel):
    """A single character label with opacity animation support."""
    
    def __init__(self, char: str, parent: Optional[QWidget] = None):
        super().__init__(char, parent)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)
        self.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: 500;
            }
        """)
    
    @property
    def opacity_effect(self) -> QGraphicsOpacityEffect:
        return self._opacity_effect


class BuilderOverlay(QWidget):
    """
    Simple overlay for build operations with static text.
    
    Features:
    - Shows static text immediately
    - Pulses: fade in → 2s visible → fade out → 1s hidden → repeat
    """
    
    def __init__(self, parent: QWidget, text: str = "Building exam paper..."):
        """
        Initialize the overlay.
        
        Args:
            parent: Parent widget (typically MainWindow)
            text: Static text to display
        """
        super().__init__(parent)
        
        self._text = text
        
        # Cover entire parent
        self.setGeometry(parent.rect())
        
        # Make overlay translucent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Animation state
        self._char_labels: List[CharacterLabel] = []
        self._current_anim_group: Optional[QSequentialAnimationGroup] = None
        
        # Timers for pulsing
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._start_fade_out)
        
        self._hidden_timer = QTimer(self)
        self._hidden_timer.setSingleShot(True)
        self._hidden_timer.timeout.connect(self._start_fade_in)
        
        # Create central content container
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the overlay UI elements."""
        # Main layout centers content
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create centered content container
        self._content = QWidget()
        self._content.setMinimumWidth(500)
        self._content.setMaximumWidth(600)
        self._content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(24)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Spinner (centered)
        self._spinner = SpinnerWidget()
        content_layout.addWidget(self._spinner, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        # Text container - holds individual character labels
        self._text_container = QWidget()
        self._text_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._text_layout = QHBoxLayout(self._text_container)
        self._text_layout.setContentsMargins(0, 0, 0, 0)
        self._text_layout.setSpacing(0)
        self._text_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self._text_container, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        # Add content to main layout (centered)
        layout.addStretch()
        layout.addWidget(self._content, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
    
    def showEvent(self, event):
        """Start animations when shown."""
        super().showEvent(event)
        self._spinner.start()
        
        # Create character labels and start fade-in immediately
        self._create_char_labels(self._text)
        self._start_fade_in()
    
    def hideEvent(self, event):
        """Stop animations when hidden."""
        super().hideEvent(event)
        self._spinner.stop()
        self._hold_timer.stop()
        self._hidden_timer.stop()
        if self._current_anim_group:
            self._current_anim_group.stop()
        self._clear_char_labels()
    
    def _clear_char_labels(self):
        """Remove all character labels."""
        for label in self._char_labels:
            label.deleteLater()
        self._char_labels.clear()
    
    def _create_char_labels(self, text: str):
        """Create character labels for the given text."""
        self._clear_char_labels()
        
        for char in text:
            label = CharacterLabel(char)
            self._text_layout.addWidget(label)
            self._char_labels.append(label)
    
    def _start_fade_in(self):
        """Animate characters fading in from left to right."""
        if not self._char_labels:
            self._create_char_labels(self._text)
        
        self._current_anim_group = QSequentialAnimationGroup(self)
        
        # Animation timing
        char_fade_duration = 200
        stagger_delay = 10
        
        parallel_group = QParallelAnimationGroup(self)
        
        for i, label in enumerate(self._char_labels):
            anim = QPropertyAnimation(label.opacity_effect, b"opacity")
            anim.setDuration(char_fade_duration)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            
            delay = i * stagger_delay
            
            wrapper = QSequentialAnimationGroup()
            if delay > 0:
                pause_anim = QPropertyAnimation(label.opacity_effect, b"opacity")
                pause_anim.setDuration(delay)
                pause_anim.setStartValue(0.0)
                pause_anim.setEndValue(0.0)
                wrapper.addAnimation(pause_anim)
            
            wrapper.addAnimation(anim)
            parallel_group.addAnimation(wrapper)
        
        self._current_anim_group.addAnimation(parallel_group)
        self._current_anim_group.finished.connect(self._start_hold)
        self._current_anim_group.start()
    
    def _start_hold(self):
        """Hold text visible for 2 seconds."""
        self._hold_timer.start(2000)
    
    def _start_fade_out(self):
        """Animate characters fading out from left to right."""
        if not self._char_labels:
            return
        
        self._current_anim_group = QSequentialAnimationGroup(self)
        
        char_fade_duration = 200
        stagger_delay = 10
        
        parallel_group = QParallelAnimationGroup(self)
        
        for i, label in enumerate(self._char_labels):
            anim = QPropertyAnimation(label.opacity_effect, b"opacity")
            anim.setDuration(char_fade_duration)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.Type.InQuad)
            
            delay = i * stagger_delay
            
            wrapper = QSequentialAnimationGroup()
            if delay > 0:
                pause_anim = QPropertyAnimation(label.opacity_effect, b"opacity")
                pause_anim.setDuration(delay)
                pause_anim.setStartValue(1.0)
                pause_anim.setEndValue(1.0)
                wrapper.addAnimation(pause_anim)
            
            wrapper.addAnimation(anim)
            parallel_group.addAnimation(wrapper)
        
        self._current_anim_group.addAnimation(parallel_group)
        self._current_anim_group.finished.connect(self._start_hidden_pause)
        self._current_anim_group.start()
    
    def _start_hidden_pause(self):
        """Pause with text hidden for 1 second, then restart."""
        self._hidden_timer.start(1000)
    
    def paintEvent(self, event):
        """Draw the semi-transparent dark backdrop."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        overlay_color = QColor(0, 0, 0, 180)
        painter.fillRect(self.rect(), overlay_color)
    
    def resizeEvent(self, event):
        """Handle parent resize."""
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())
