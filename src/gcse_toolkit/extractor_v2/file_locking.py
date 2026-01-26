"""
Module: extractor_v2.file_locking

Purpose:
    Cross-platform file locking utilities for safe concurrent extraction.
    Uses portalocker for Mac, Windows, and Linux compatibility.

Key Functions:
    - locked_append_jsonl: Append to JSONL with exclusive lock
    - locked_read_modify_write_json: Read-modify-write JSON with lock
    - locked_file: Context manager for locked file access

Dependencies:
    - portalocker: Cross-platform file locking

Used By:
    - pipeline.py: Centralized metadata writing
    - timing.py: Timing data merging
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Generator

import portalocker

logger = logging.getLogger(__name__)


@contextmanager
def locked_file(
    path: Path,
    mode: str = 'r',
    lock_type: int = portalocker.LOCK_EX,
) -> Generator:
    """
    Context manager for cross-platform locked file access.
    
    Args:
        path: Path to file.
        mode: File open mode ('r', 'w', 'a', etc.).
        lock_type: Lock type (LOCK_EX for exclusive, LOCK_SH for shared).
        
    Yields:
        Open file handle with lock held.
        
    Example:
        >>> with locked_file(path, 'a') as f:
        ...     f.write('data')
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Ensure file exists for read modes
    if 'r' in mode and not path.exists():
        path.touch()
    
    with open(path, mode, encoding='utf-8') as f:
        portalocker.lock(f, lock_type)
        try:
            yield f
        finally:
            portalocker.unlock(f)


def locked_append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    """
    Append a record to JSONL file with exclusive lock.
    
    Thread/process-safe for concurrent writes from parallel extractions.
    
    Args:
        path: Path to JSONL file.
        record: Dictionary to append as JSON line.
        
    Example:
        >>> locked_append_jsonl(metadata_path, {"id": "q1", "marks": 5})
    """
    with locked_file(path, 'a', portalocker.LOCK_EX) as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    logger.debug(f"Appended record to {path.name}")


def locked_read_modify_write_json(
    path: Path,
    modifier: Callable[[Dict[str, Any]], Dict[str, Any]],
    default: Callable[[], Dict[str, Any]] = dict,
) -> Dict[str, Any]:
    """
    Read JSON, apply modifier, write back - all with exclusive lock.
    
    Used for merging timing data from parallel extractions.
    
    Args:
        path: Path to JSON file.
        modifier: Function that takes existing data, returns modified data.
        default: Factory for default data if file doesn't exist.
        
    Returns:
        The modified data that was written.
        
    Example:
        >>> def merge_timings(existing):
        ...     existing['question_timings'].update(new_timings)
        ...     return existing
        >>> locked_read_modify_write_json(timing_path, merge_timings)
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use r+ mode for read-modify-write, create if needed
    if not path.exists():
        path.write_text(json.dumps(default(), indent=2))
    
    with open(path, 'r+', encoding='utf-8') as f:
        portalocker.lock(f, portalocker.LOCK_EX)
        try:
            # Read existing
            f.seek(0)
            content = f.read()
            if content.strip():
                existing = json.loads(content)
            else:
                existing = default()
            
            # Modify
            modified = modifier(existing)
            
            # Write back
            f.seek(0)
            f.truncate()
            json.dump(modified, f, indent=2, ensure_ascii=False)
            
            return modified
        finally:
            portalocker.unlock(f)
