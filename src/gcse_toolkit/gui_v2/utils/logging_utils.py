"""
Logging utilities for redirecting logs to a queue for GUI display.
"""
from __future__ import annotations

import logging
import threading
from logging.handlers import QueueHandler
from queue import Queue, Empty
from typing import Optional, Callable, Any
import multiprocessing


class QueueLogHandler(logging.Handler):
    """
    A logging handler that sends log records to a queue.
    
    Used to capture logs from internal APIs and display them in the GUI console.
    """
    
    def __init__(self, log_queue: Queue, level: int = logging.INFO):
        super().__init__(level)
        self.log_queue = log_queue
        self.setFormatter(logging.Formatter("%(message)s"))
    
    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            level = record.levelname
            # Map DEBUG to INFO for GUI display
            if level == "DEBUG":
                level = "INFO"
            self.log_queue.put((message, level))
        except Exception:
            self.handleError(record)


def attach_queue_handler(log_queue: Queue, logger_name: Optional[str] = None) -> QueueLogHandler:
    """
    Attach a QueueLogHandler to the specified logger (or root logger if None).
    
    Args:
        log_queue: Queue to send log messages to.
        logger_name: Name of logger to attach to. None = root logger.
        
    Returns:
        The attached handler (for later removal).
    """
    logger = logging.getLogger(logger_name)
    handler = QueueLogHandler(log_queue)
    logger.addHandler(handler)
    return handler


def detach_queue_handler(handler: QueueLogHandler, logger_name: Optional[str] = None) -> None:
    """
    Remove a QueueLogHandler from the specified logger.
    
    Args:
        handler: The handler to remove.
        logger_name: Name of logger to detach from. None = root logger.
    """
    logger = logging.getLogger(logger_name)
    logger.removeHandler(handler)


# =============================================================================
# Multiprocessing Logging Support
# =============================================================================

def configure_worker_logging(mp_log_queue: multiprocessing.Queue) -> None:
    """
    Configure logging in a child process to send logs to a multiprocessing queue.
    
    Call this as the initializer for ProcessPoolExecutor to enable log
    capture from worker processes.
    
    Args:
        mp_log_queue: Multiprocessing queue to send log records to.
        
    Example:
        >>> with ProcessPoolExecutor(
        ...     max_workers=4,
        ...     initializer=configure_worker_logging,
        ...     initargs=(mp_log_queue,),
        ... ) as executor:
        ...     # workers will send logs to mp_log_queue
    """
    # Get root logger and remove all existing handlers
    root = logging.getLogger()
    root.handlers = []
    
    # Add QueueHandler that sends to multiprocessing queue
    handler = QueueHandler(mp_log_queue)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)


def start_log_listener(
    mp_log_queue: multiprocessing.Queue,
    gui_queue: Queue,
    stop_event: threading.Event,
) -> threading.Thread:
    """
    Start a listener thread that reads from multiprocessing queue and 
    forwards to the GUI queue.
    
    Args:
        mp_log_queue: Multiprocessing queue that workers write to.
        gui_queue: GUI queue that ConsoleWidget reads from.
        stop_event: Event to signal listener to stop.
        
    Returns:
        The listener thread (already started).
        
    Example:
        >>> stop_event = threading.Event()
        >>> listener = start_log_listener(mp_queue, gui_queue, stop_event)
        >>> # ... do work ...
        >>> stop_event.set()
        >>> listener.join()
    """
    def _listener():
        while not stop_event.is_set():
            try:
                record = mp_log_queue.get(timeout=0.1)
                if record is None:  # Sentinel value
                    break
                # Forward to GUI queue
                level = record.levelname if hasattr(record, 'levelname') else "INFO"
                message = record.getMessage() if hasattr(record, 'getMessage') else str(record)
                if level == "DEBUG":
                    level = "INFO"
                gui_queue.put((message, level))
            except Empty:
                continue
            except Exception:
                pass  # Ignore errors in listener
    
    thread = threading.Thread(target=_listener, daemon=True)
    thread.start()
    return thread

