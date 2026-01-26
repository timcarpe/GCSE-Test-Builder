"""
Tutorial Overlay Widget for first-launch guidance.

Provides a spotlight overlay that highlights UI elements with 
instructional callouts to guide new users through the app workflow.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Callable

from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QTimer, QSize
from PySide6.QtGui import QPainter, QColor, QPainterPath

from gcse_toolkit.gui_v2.styles.theme import get_colors, get_styles


@dataclass
class TutorialStep:
    """Definition of a single tutorial step."""
    target_widget: QWidget              # Widget to spotlight
    title: str                          # Step title
    message: str                        # Instruction text
    callout_position: str = "bottom"    # "top", "bottom", "left", "right"
    before_show: Optional[Callable] = None  # Optional callback before showing step


class CalloutWidget(QWidget):
    """Tooltip-style callout with step info and navigation."""
    
    next_clicked = Signal()
    skip_clicked = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("tutorialCallout")
        self.setAutoFillBackground(True)  # Required for background to render
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)  # macOS: enable stylesheet background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)  # Prevent background transparency
        self.setMinimumWidth(320)  # Ensure consistent width
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # Title
        self.title_label = QLabel()
        self.title_label.setObjectName("tutorialTitle")
        layout.addWidget(self.title_label)
        
        # Message
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setFixedWidth(280)  # Fixed width to prevent text overflow
        from PySide6.QtWidgets import QSizePolicy
        self.message_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.message_label)
        
        # Step indicator + buttons
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        
        self.step_label = QLabel()
        self.step_label.setObjectName("tutorialStepLabel")
        button_row.addWidget(self.step_label)
        
        button_row.addStretch()
        
        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setObjectName("tutorialSkipBtn")
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.clicked.connect(self.skip_clicked)
        button_row.addWidget(self.skip_btn)
        
        self.next_btn = QPushButton("Next")
        self.next_btn.setObjectName("tutorialNextBtn")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setMinimumWidth(85)  # Prevent text overflow on "Finish"
        self.next_btn.clicked.connect(self.next_clicked)
        button_row.addWidget(self.next_btn)
        
        layout.addLayout(button_row)
        
        # Apply initial theme and shadow
        self.update_theme()
        
        # Add drop shadow for visibility against dark overlay
        from gcse_toolkit.gui_v2.styles.theme import apply_shadow
        apply_shadow(self, blur_radius=30, y_offset=8, color=QColor(0, 0, 0, 100))
    
    def update_theme(self):
        """Update styling based on current theme."""
        C = get_colors()
        
        # Set background explicitly via palette for WA_TranslucentBackground parent
        from PySide6.QtGui import QPalette
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(C.SURFACE))
        self.setPalette(palette)
        
        self.setStyleSheet(f"""
            #tutorialCallout {{
                background: {C.SURFACE};
                border-radius: 12px;
                border: 1px solid {C.BORDER};
            }}
            #tutorialTitle {{
                font-weight: bold;
                font-size: 15px;
                color: {C.TEXT_PRIMARY};
            }}
            #tutorialStepLabel {{
                color: {C.TEXT_SECONDARY};
                font-size: 12px;
            }}
            QLabel {{
                color: {C.TEXT_PRIMARY};
            }}
            #tutorialSkipBtn {{
                background: transparent;
                color: {C.TEXT_SECONDARY};
                border: none;
                padding: 6px 12px;
            }}
            #tutorialSkipBtn:hover {{
                color: {C.TEXT_PRIMARY};
            }}
            #tutorialNextBtn {{
                background: {C.PRIMARY_BLUE};
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 6px;
                font-weight: 500;
            }}
            #tutorialNextBtn:hover {{
                background: {C.PRIMARY_BLUE_HOVER};
            }}
        """)
    
    def set_content(self, title: str, message: str, step_num: int, total_steps: int, is_last: bool):
        """Update callout content for a step."""
        # Clear labels first to prevent text overlap (critical for transparent parent)
        self.title_label.clear()
        self.message_label.clear()
        
        # Set new text
        self.title_label.setText(title)
        self.message_label.setText(message)
        self.step_label.setText(f"Step {step_num} of {total_steps}")
        self.next_btn.setText("Finish" if is_last else "Next")
        
        # Force immediate repaint to clear old text artifacts
        self.title_label.repaint()
        self.message_label.repaint()
        self.step_label.repaint()
        self.repaint()
        
        # Process events to ensure repaint completes
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()


class TutorialOverlay(QWidget):
    """Semi-transparent overlay with spotlight cutout for tutorial steps."""
    
    finished = Signal()  # Emitted when tutorial completes or is skipped
    
    def __init__(self, parent: QWidget, steps: List[TutorialStep]):
        super().__init__(parent)
        self.steps = steps
        self.current_step = 0
        self._callout = None  # Created fresh for each step
        
        # Cover entire parent
        self.setGeometry(parent.rect())
        
        # Make overlay receive mouse events but be transparent visually
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Show first step
        self._update_step()
    
    def paintEvent(self, event):
        """Draw dark overlay with transparent spotlight hole."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Full overlay path
        overlay_path = QPainterPath()
        overlay_path.addRect(self.rect().toRectF())
        
        # Subtract spotlight region (rounded rect around target)
        if self.current_step < len(self.steps):
            target = self.steps[self.current_step].target_widget
            if target and target.isVisible():
                # Map target geometry to overlay coordinates
                global_pos = target.mapToGlobal(QPoint(0, 0))
                local_pos = self.mapFromGlobal(global_pos)
                spotlight_rect = QRect(local_pos, target.size())
                
                # Add padding around widget
                spotlight_rect.adjust(-12, -12, 12, 12)
                
                # Create rounded spotlight hole
                spotlight_path = QPainterPath()
                spotlight_path.addRoundedRect(spotlight_rect.toRectF(), 12, 12)
                overlay_path = overlay_path.subtracted(spotlight_path)
        
        # Draw semi-transparent dark overlay
        overlay_color = QColor(0, 0, 0, 160)
        painter.fillPath(overlay_path, overlay_color)
    
    def _update_step(self):
        """Update callout position and content for current step."""
        if self.current_step >= len(self.steps):
            self._finish()
            return
            
        step = self.steps[self.current_step]
        
        # Call before_show callback if present (e.g., to switch tabs)
        if step.before_show:
            step.before_show()
            # Small delay to allow tab switch animation to complete
            QTimer.singleShot(350, lambda: self._show_step(step))
        else:
            self._show_step(step)
    
    def _show_step(self, step: TutorialStep):
        """Display the current step's callout and spotlight."""
        # Destroy old callout and create fresh one to prevent text artifacts
        if hasattr(self, '_callout') and self._callout:
            self._callout.hide()
            self._callout.close()
            self._callout.deleteLater()
        
        self._callout = CalloutWidget()
        self._callout.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self._callout.next_clicked.connect(self._next_step)
        self._callout.skip_clicked.connect(self._skip)
        
        self._callout.set_content(
            title=step.title,
            message=step.message,
            step_num=self.current_step + 1,
            total_steps=len(self.steps),
            is_last=(self.current_step == len(self.steps) - 1)
        )
        self._position_callout(step)
        self._callout.show()
        self._callout.raise_()
        self.update()  # Trigger repaint
    
    def _position_callout(self, step: TutorialStep):
        """Position callout relative to spotlighted widget."""
        target = step.target_widget
        if not target:
            return
        
        # Get target position in global screen coordinates (callout is now a separate window)
        target_global = target.mapToGlobal(QPoint(0, 0))
        target_rect = QRect(target_global, target.size())
        
        # Get screen geometry for clamping
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        screen_rect = screen.geometry()
        
        callout_size = self._callout.sizeHint()
        margin = 20
        
        if step.callout_position == "bottom":
            x = target_rect.center().x() - callout_size.width() // 2
            y = target_rect.bottom() + margin
        elif step.callout_position == "top":
            x = target_rect.center().x() - callout_size.width() // 2
            y = target_rect.top() - callout_size.height() - margin
        elif step.callout_position == "right":
            x = target_rect.right() + margin
            y = target_rect.center().y() - callout_size.height() // 2
        else:  # left
            x = target_rect.left() - callout_size.width() - margin
            y = target_rect.center().y() - callout_size.height() // 2
        
        # Clamp to screen bounds
        x = max(screen_rect.left() + margin, min(x, screen_rect.right() - callout_size.width() - margin))
        y = max(screen_rect.top() + margin, min(y, screen_rect.bottom() - callout_size.height() - margin))
        
        self._callout.move(int(x), int(y))
    
    def _next_step(self):
        """Advance to the next step."""
        self.current_step += 1
        self._update_step()
    
    def _skip(self):
        """Skip the entire tutorial."""
        self._finish()
    
    def _finish(self):
        """Complete the tutorial."""
        self._callout.hide()
        self._callout.close()
        self.hide()
        self.finished.emit()
    
    def resizeEvent(self, event):
        """Handle parent resize."""
        super().resizeEvent(event)
        # Resize overlay to match parent
        if self.parent():
            self.setGeometry(self.parent().rect())
        # Reposition callout (guard against early resize before init completes)
        if hasattr(self, '_callout') and self.current_step < len(self.steps):
            self._position_callout(self.steps[self.current_step])
    
    def update_theme(self):
        """Update theme for callout widget."""
        self._callout.update_theme()
