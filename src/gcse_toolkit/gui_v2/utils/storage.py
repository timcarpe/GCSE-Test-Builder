"""Storage management utilities for GCSE Test Builder."""
from pathlib import Path
from typing import Dict, Any


def calculate_directory_size(path: Path) -> int:
    """Calculate total size of directory in bytes.
    
    Args:
        path: Directory path to calculate size for.
        
    Returns:
        Total size in bytes, or 0 if path doesn't exist or on error.
    """
    total = 0
    try:
        for entry in path.rglob('*'):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except (OSError, PermissionError):
                    # Skip files we can't read
                    continue
    except (PermissionError, OSError):
        pass
    return total


def format_size(bytes_size: int) -> str:
    """Format bytes to human-readable string (e.g., '1.2 GB').
    
    Args:
        bytes_size: Size in bytes.
        
    Returns:
        Formatted string with appropriate unit.
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"


def get_storage_info() -> Dict[str, Any]:
    """Get storage usage for various GCSE Test Builder directories.
    
    Returns:
        Dict with bytes and paths for slices_cache, input_pdfs, and keyword_cache.
    """
    from gcse_toolkit.gui_v2.utils.paths import (
        get_slices_cache_dir, 
        get_user_document_dir,
        get_cache_dir
    )
    
    slices_cache = get_slices_cache_dir()
    input_pdfs = get_user_document_dir("Source PDFs")
    keyword_cache = get_cache_dir()
    
    return {
        "slices_cache_bytes": calculate_directory_size(slices_cache) if slices_cache.exists() else 0,
        "slices_cache_path": slices_cache,
        "input_pdfs_bytes": calculate_directory_size(input_pdfs) if input_pdfs.exists() else 0,
        "input_pdfs_path": input_pdfs,
        "keyword_cache_bytes": calculate_directory_size(keyword_cache) if keyword_cache.exists() else 0,
        "keyword_cache_path": keyword_cache,
    }
