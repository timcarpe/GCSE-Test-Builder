"""
Attention getter utilities for GUI widgets.

Provides pulsing border animations to draw user attention to specific UI elements.
"""
from typing import Optional, Dict, Any
from PySide6.QtWidgets import QPushButton, QWidget
from PySide6.QtCore import QTimer

from gcse_toolkit.gui_v2.styles.theme import get_colors, get_styles


# Track active animations per widget (key = widget id)
_active_animations: Dict[int, Dict[str, Any]] = {}


def pulse_button(
    button: QPushButton,
    color: tuple = (241, 196, 15),     # Bright yellow/gold #F1C40F
    pulse_ms: int = 1000,              # Time for one pulse cycle
    duration_ms: int = None,           # Total duration (None = until clicked/hovered)
    stop_on_click: bool = True,        # Stop when button is clicked
    stop_on_hover: bool = False,       # Stop when button is hovered
) -> None:
    """
    Apply a pulsing colored border animation to a button.
    
    Uses smooth easing for a natural, polished feel.
    The button's original style is preserved - only the border color is modified.
    Animation continues until clicked, hovered, or duration expires.
    
    Args:
        button: The QPushButton to animate.
        color: RGB tuple for the pulse color (default: gold/yellow).
        pulse_ms: Duration of one complete pulse cycle in milliseconds (default 1000).
        duration_ms: Total animation duration in ms. None = indefinite (default).
        stop_on_click: If True, stop animation when button is clicked (default True).
        stop_on_hover: If True, stop animation when button is hovered (default False).
    """
    import math
    
    widget_id = id(button)
    
    # Stop any existing animation on this button
    stop_pulse(button)
    
    # Animation state - save original style to restore later
    frame_ms = 33  # ~30 FPS for smooth animation
    border_width = 3  # Fixed border width to prevent layout shift
    
    state = {
        'tick': 0,
        'original_style': button.styleSheet(),
        'ticks_per_cycle': pulse_ms // frame_ms,
    }
    
    def ease_in_out(t: float) -> float:
        """Smooth ease-in-out curve (sine-based)."""
        return (1 - math.cos(t * math.pi)) / 2
    
    def update_pulse():
        """Update the pulsing border color."""
        state['tick'] += 1
        
        # Calculate position in current cycle (0 to 1)
        cycle_pos = (state['tick'] % state['ticks_per_cycle']) / state['ticks_per_cycle']
        
        # Use sine wave for smooth oscillation (0 -> 1 -> 0)
        intensity = ease_in_out(cycle_pos * 2) if cycle_pos < 0.5 else ease_in_out((1 - cycle_pos) * 2)
        
        # Color intensity: full color at peak, faded to gray at low
        base_gray = 128  # Neutral gray when faded
        r = int(base_gray + (color[0] - base_gray) * intensity)
        g = int(base_gray + (color[1] - base_gray) * intensity)
        b = int(base_gray + (color[2] - base_gray) * intensity)
        
        # Apply only the border color change on top of the original style
        original = state['original_style']
        button.setStyleSheet(f"{original} QPushButton {{ border: {border_width}px solid rgb({r}, {g}, {b}) !important; }}")
    
    def on_click():
        """Stop animation when button is clicked."""
        stop_pulse(button)
    
    def on_hover(event):
        """Stop animation when button is hovered."""
        stop_pulse(button)
        # Call original event handler if any
        return False
    
    # Create and start timer
    timer = QTimer()
    timer.timeout.connect(update_pulse)
    timer.start(frame_ms)
    
    # Store animation state  
    _active_animations[widget_id] = {
        'timer': timer,
        'state': state,
        'button': button,
        'click_connection': None,
    }
    
    # Connect to clicked signal to stop on click
    if stop_on_click:
        connection = button.clicked.connect(on_click)
        _active_animations[widget_id]['click_connection'] = connection
    
    # Install event filter for hover detection
    if stop_on_hover:
        button.enterEvent = lambda e: stop_pulse(button)
    
    # Auto-stop after duration if specified
    if duration_ms is not None:
        QTimer.singleShot(duration_ms, lambda: stop_pulse(button))


def stop_pulse(button: QPushButton) -> None:
    """
    Stop any active pulsing animation on a button and restore its original style.
    
    Args:
        button: The QPushButton to stop animating.
    """
    widget_id = id(button)
    
    if widget_id in _active_animations:
        anim = _active_animations[widget_id]
        anim['timer'].stop()
        
        # Restore original style or use default from theme
        original_style = anim['state'].get('original_style')
        if original_style:
            button.setStyleSheet(original_style)
        else:
            S = get_styles()
            button.setStyleSheet(S.BUTTON_PRIMARY)
        
        del _active_animations[widget_id]


def is_pulsing(button: QPushButton) -> bool:
    """
    Check if a button currently has an active pulse animation.
    
    Args:
        button: The QPushButton to check.
        
    Returns:
        True if the button is currently pulsing, False otherwise.
    """
    return id(button) in _active_animations


def pulse_button_danger(button: QPushButton, duration_ms: int = None) -> None:
    """
    Apply a danger (red) pulsing animation to a button.
    
    Args:
        button: The QPushButton to animate.
        duration_ms: Total duration in ms (None = until clicked).
    """
    pulse_button(
        button,
        duration_ms=duration_ms,
        color=(239, 83, 80),  # Red #EF5350
    )


def pulse_button_success(button: QPushButton, duration_ms: int = None) -> None:
    """
    Apply a success (green) pulsing animation to a button.
    
    Args:
        button: The QPushButton to animate.
        duration_ms: Total duration in ms (None = until clicked).
    """
    pulse_button(
        button,
        duration_ms=duration_ms,
        color=(76, 175, 80),  # Green #4CAF50
    )


def pulse_button_info(button: QPushButton, duration_ms: int = None) -> None:
    """
    Apply an info (blue) pulsing animation to a button.
    
    Args:
        button: The QPushButton to animate.
        duration_ms: Total duration in ms (None = until clicked).
    """
    pulse_button(
        button,
        duration_ms=duration_ms,
        color=(66, 165, 245),  # Blue #42A5F5
    )
