"""
Module: common.exams

Purpose:
    Thin compatibility layer for exam definitions, wrapping the plugin
    registry to provide a simpler ExamDefinition dataclass for GUI usage.

Key Functions:
    - get_exam_definition(): Get exam metadata by code
    - supported_exam_codes(): List all available exam codes

Dependencies:
    - gcse_toolkit.plugins: Exam plugin registry

Used By:
    - gcse_toolkit.gui_v2.widgets.build_tab: Exam name display
    - gcse_toolkit.gui_v2.widgets.extract_tab: Exam validation
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from gcse_toolkit.plugins import (
    UnsupportedCodeError,
    get_exam_plugin,
    list_exam_plugins,
)

# Re-export UnsupportedCodeError for convenience
__all__ = [
    "ExamDefinition",
    "get_exam_definition",
    "supported_exam_codes",
    "UnsupportedCodeError",
]


@dataclass(frozen=True)
class ExamDefinition:
    """
    Simplified exam metadata for GUI display.
    
    Attributes:
        code: Exam code (e.g., "0478", "4037").
        name: Human-readable exam name.
        subtopics_path: Path to subtopics configuration file.
        options: Additional exam-specific options.
    """
    code: str
    name: str
    subtopics_path: Path
    options: Dict[str, Any]


def supported_exam_codes() -> Iterable[str]:
    """
    Return all supported exam codes.
    
    Returns:
        Iterable of exam code strings (e.g., ["0450", "0478", "4037"]).
        
    Example:
        >>> list(supported_exam_codes())
        ['0450', '0478', '4037', ...]
    """
    return [plugin.code for plugin in list_exam_plugins()]


def get_exam_definition(code: Optional[str]) -> ExamDefinition:
    """
    Get exam definition by code.
    
    Args:
        code: Exam code (e.g., "0478", "4037"). If None, uses default.
        
    Returns:
        ExamDefinition with code, name, subtopics_path, and options.
        
    Raises:
        UnsupportedCodeError: If code is not registered in the plugin system.
        
    Example:
        >>> defn = get_exam_definition("0478")
        >>> defn.name
        'Computer Science'
    """
    plugin = get_exam_plugin(code)
    return ExamDefinition(
        code=plugin.code,
        name=plugin.name,
        subtopics_path=plugin.subtopics_path,
        options=dict(plugin.options),
    )
