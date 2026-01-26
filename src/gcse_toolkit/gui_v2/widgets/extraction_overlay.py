"""
Extraction Overlay Widget.

Provides a modern, minimalistic loading overlay that displays during
the extraction process with an animated spinner and cycling status text.
"""
import random
from threading import Lock
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsOpacityEffect
)
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, Property, QEasingCurve, QSequentialAnimationGroup, QParallelAnimationGroup
)
from PySide6.QtGui import QPainter, QColor, QPen

from gcse_toolkit.gui_v2.styles.theme import get_colors


# Status keywords to randomly cycle through
STATUS_KEYWORDS = [
    "Extracting",
    "Categorizing", 
    "Processing",
    "Analyzing",
    "Parsing",
    "Indexing",
    "Scanning",
    "Detecting",
    "Compiling",
    "Rendering",
    "Building",
    "Assembling",
    "Constructing",
    "Forming",
    "Arranging",
    "Organizing",
    "Structuring",
]


class ExtractionTextBuffer:
    """
    Thread-safe buffer for extracted question texts.
    
    Used to pass question text from extraction thread to UI overlay.
    """
    
    def __init__(self):
        self._texts: List[str] = []
        self._lock = Lock()
    
    def add(self, text: str):
        """
        Add a question text (called from extraction thread).
        
        Args:
            text: Raw question text (will be processed/truncated)
        """
        with self._lock:
            snippet = _prepare_snippet(text)
            if snippet:
                self._texts.append(snippet)
                # Keep only the 50 most recent texts
                if len(self._texts) > 50:
                    self._texts.pop(0)
    
    def sample(self) -> Optional[str]:
        """
        Get a random text if available (called from UI thread).
        
        Returns:
            Random question text snippet, or None if buffer is empty
        """
        with self._lock:
            if self._texts:
                return random.choice(self._texts)
            return None
    
    def has_texts(self) -> bool:
        """Check if any texts are available."""
        with self._lock:
            return len(self._texts) > 0
    
    def clear(self):
        """Clear all texts."""
        with self._lock:
            self._texts.clear()


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


class ExtractionOverlay(QWidget):
    """
    Full-window extraction loading overlay.
    
    Features:
    - Semi-transparent dark backdrop
    - Modern animated spinner
    - Cycling status text with character-by-character fade animation
    - Waits for text buffer to have data before showing text line
    """
    
    def __init__(self, parent: QWidget, text_buffer: ExtractionTextBuffer):
        """
        Initialize the overlay.
        
        Args:
            parent: Parent widget (typically MainWindow)
            text_buffer: Shared buffer that extraction thread populates
        """
        super().__init__(parent)
        
        self._text_buffer = text_buffer
        
        # Cover entire parent
        self.setGeometry(parent.rect())
        
        # Make overlay translucent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Animation state
        self._char_labels: List[CharacterLabel] = []
        self._current_anim_group: Optional[QSequentialAnimationGroup] = None
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._start_fade_out)
        
        # Timer to check for available text
        self._check_buffer_timer = QTimer(self)
        self._check_buffer_timer.timeout.connect(self._check_buffer_and_start)
        
        # Track if we've started showing text
        self._text_showing = False
        
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
        self._text_layout.setSpacing(0)  # Characters tight together
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
        
        # Start checking for buffer data
        self._check_buffer_timer.start(100)  # Check every 100ms for faster response
    
    def hideEvent(self, event):
        """Stop animations when hidden."""
        super().hideEvent(event)
        self._spinner.stop()
        self._hold_timer.stop()
        self._check_buffer_timer.stop()
        if self._current_anim_group:
            self._current_anim_group.stop()
        self._clear_char_labels()
    
    def _check_buffer_and_start(self):
        """Check if buffer has data and start text cycling."""
        if self._text_buffer.has_texts() and not self._text_showing:
            self._text_showing = True
            self._check_buffer_timer.stop()
            self._start_text_cycle()
    
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
    
    def _start_text_cycle(self):
        """Start the text cycling with character fade effect."""
        # Build the status text
        keyword = random.choice(STATUS_KEYWORDS)
        question_text = self._text_buffer.sample()
        
        if not question_text:
            # Buffer empty (shouldn't happen if we checked, but be safe)
            # Re-enable checking
            self._text_showing = False
            self._check_buffer_timer.start(100)
            return
        
        full_text = f"{keyword} questions about {question_text}..."
        
        # Create character labels
        self._create_char_labels(full_text)
        
        # Start fade-in animation
        self._start_fade_in()
    
    def _start_fade_in(self):
        """Animate characters fading in from left to right."""
        if not self._char_labels:
            return
        
        # Create sequential animation group for staggered character fade
        self._current_anim_group = QSequentialAnimationGroup(self)
        
        # Wave effect: longer fade per character, tight stagger so multiple chars fade at once
        char_fade_duration = 200  # ms - fade duration per character
        stagger_delay = 10  # ms between each character starting - creates wave
        
        # Create parallel group for overlapping animations
        parallel_group = QParallelAnimationGroup(self)
        
        for i, label in enumerate(self._char_labels):
            anim = QPropertyAnimation(label.opacity_effect, b"opacity")
            anim.setDuration(char_fade_duration)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            
            # Set delay for staggered effect (wave)
            delay = i * stagger_delay
            
            # Create a wrapper sequential group with a pause
            wrapper = QSequentialAnimationGroup()
            
            # Add pause for delay
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
        """Hold the text visible."""
        self._hold_timer.start(2000)  # 2 seconds
    
    def _start_fade_out(self):
        """Animate characters fading out from left to right."""
        if not self._char_labels:
            self._on_fade_out_complete()
            return
        
        # Create sequential animation group for staggered character fade
        self._current_anim_group = QSequentialAnimationGroup(self)
        
        # Wave effect: match fade-in timing
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
        self._current_anim_group.finished.connect(self._on_fade_out_complete)
        self._current_anim_group.start()
    
    def _on_fade_out_complete(self):
        """Handle fade out completion - cycle to next text."""
        # Small pause before next text
        QTimer.singleShot(400, self._start_text_cycle)
    
    def paintEvent(self, event):
        """Draw the semi-transparent dark backdrop."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fill with semi-transparent dark overlay
        overlay_color = QColor(0, 0, 0, 180)  # ~70% opacity
        painter.fillRect(self.rect(), overlay_color)
    
    def resizeEvent(self, event):
        """Handle parent resize."""
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())


def _prepare_snippet(text: str, max_length: int = 50) -> str:
    """
    Prepare a question text snippet for display.
    
    - Drops the first word (per user feedback)
    - Truncates to max_length
    - Cleans up whitespace
    """
    if not text:
        return ""
    
    # Clean and split
    text = text.strip()
    words = text.split()
    
    if len(words) <= 1:
        return ""  # Not enough content after dropping first word
    
    # Drop first word
    text = " ".join(words[1:])
    
    # Truncate if needed
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0]  # Break at word boundary
    
    # Clean up any trailing punctuation that looks incomplete
    text = text.rstrip(".,;:-")
    
    return text.lower()
