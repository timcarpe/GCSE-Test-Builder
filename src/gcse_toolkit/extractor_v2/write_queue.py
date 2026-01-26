"""
Module: extractor_v2.write_queue

Purpose:
    Async file writing queue for non-blocking I/O during extraction.
    Allows processing to continue while files are written in background.

Key Classes:
    - WriteQueue: Thread pool-based async write queue

Dependencies:
    - concurrent.futures: Thread pool execution
    - PIL.Image: Image saving

Used By:
    - extractor_v2.pipeline: Queue writes during extraction

OPTIMIZATION C: Async File Writing
"""

from __future__ import annotations

import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
from typing import List, Optional

from PIL import Image

logger = logging.getLogger(__name__)


class WriteQueue:
    """
    Thread pool-based async write queue for file I/O.
    
    Queues file writes to execute in background threads,
    allowing the main extraction logic to continue processing
    the next question while files are being saved.
    
    Usage:
        queue = WriteQueue(max_workers=4)
        try:
            for question in questions:
                # ... processing ...
                queue.queue_image_write(composite, path)
            queue.wait_all()  # Wait for all writes at end
        finally:
            queue.shutdown()
    
    Attributes:
        max_workers: Maximum concurrent write threads.
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize write queue.
        
        Args:
            max_workers: Maximum concurrent write threads.
                        Default 4 is good for typical SSDs.
        """
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: List[Future] = []
        self._enabled = True
    
    def queue_image_write(
        self,
        image: Image.Image,
        path: Path,
        compress_level: int = 1,
    ) -> Optional[Future]:
        """
        Queue an image write operation.
        
        Args:
            image: PIL Image to save.
            path: Target path for the image.
            compress_level: PNG compression (1=fast, 9=small).
            
        Returns:
            Future object if queued, None if queue disabled.
        """
        if not self._enabled:
            # Synchronous fallback
            _write_image_sync(image, path, compress_level)
            return None
        
        future = self._executor.submit(
            _write_image_sync, image, path, compress_level
        )
        self._futures.append(future)
        return future
    
    def wait_all(self, timeout: Optional[float] = None) -> int:
        """
        Wait for all queued writes to complete.
        
        Args:
            timeout: Max seconds to wait (None = indefinite).
            
        Returns:
            Number of completed writes.
        """
        completed = 0
        for future in self._futures:
            try:
                future.result(timeout=timeout)
                completed += 1
            except Exception as e:
                logger.error(f"Write failed: {e}")
        self._futures.clear()
        return completed
    
    def shutdown(self) -> None:
        """Shutdown the thread pool."""
        self.wait_all()
        self._executor.shutdown(wait=True)
    
    def disable(self) -> None:
        """Disable async writes (use synchronous mode)."""
        self._enabled = False
    
    def __enter__(self) -> "WriteQueue":
        return self
    
    def __exit__(self, *args) -> None:
        self.shutdown()


def _write_image_sync(
    image: Image.Image,
    path: Path,
    compress_level: int = 1,
) -> None:
    """Synchronous atomic image write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=".png",
        dir=path.parent,
        delete=False,
    ) as f:
        image.save(f, format="PNG", compress_level=compress_level)
        temp_path = Path(f.name)
    
    temp_path.replace(path)
