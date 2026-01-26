"""Startup popup queue manager.

Ensures dialogs are shown sequentially without overlap.
Each popup must call notify_complete() when dismissed to trigger the next.
"""
from __future__ import annotations

from typing import Callable, List, Optional
from PySide6.QtCore import QObject, Signal


class StartupPopupQueue(QObject):
    """Queue manager for startup dialogs to prevent overlap.
    
    Usage:
        queue = StartupPopupQueue()
        queue.enqueue(lambda: self._show_metadata_warning())
        queue.enqueue(lambda: self._show_plugin_updates())
        queue.enqueue(lambda: self._show_tutorial())
        queue.start()
        
        # In each popup handler, call queue.notify_complete() when user dismisses dialog
    """
    
    # Emitted when all queued popups have been processed
    all_completed = Signal()
    
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._queue: List[Callable[[], None]] = []
        self._active = False
        self._current_index = 0
    
    def enqueue(self, popup_fn: Callable[[], None]) -> None:
        """Add a popup function to the queue.
        
        Args:
            popup_fn: A callable that shows the popup. The callable should
                     call notify_complete() when the popup is dismissed.
                     If the popup doesn't need to be shown (e.g., condition not met),
                     the callable should still call notify_complete() to proceed.
        """
        self._queue.append(popup_fn)
    
    def start(self) -> None:
        """Start processing the popup queue.
        
        Safe to call even if already active (will be ignored).
        """
        if self._active:
            return
        self._active = True
        self._current_index = 0
        self._process_next()
    
    def notify_complete(self) -> None:
        """Called by popup when user dismisses it.
        
        Triggers the next popup in the queue, or emits all_completed
        if the queue is exhausted.
        """
        self._current_index += 1
        self._process_next()
    
    def _process_next(self) -> None:
        """Process the next popup in the queue."""
        if self._current_index >= len(self._queue):
            self._active = False
            self.all_completed.emit()
            return
        
        popup_fn = self._queue[self._current_index]
        try:
            popup_fn()
        except Exception:
            # If popup fails, continue to next
            self.notify_complete()
    
    def is_active(self) -> bool:
        """Check if queue is currently processing popups."""
        return self._active
    
    def clear(self) -> None:
        """Clear the queue and stop processing."""
        self._queue.clear()
        self._active = False
        self._current_index = 0
