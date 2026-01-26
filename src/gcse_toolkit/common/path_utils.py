"""Path and filename utilities.

Provides shared functions for extracting prefixes and standardizing
file path operations across the toolkit.
"""

from __future__ import annotations

import re
from pathlib import Path


def extract_paper_prefix(filename: str | Path) -> str:
    """Extract the standard prefix from an exam paper filename.
    
    Extracts the portion before the paper type marker (_qp_ or _ms_).
    Used for organizing outputs and matching question papers with mark schemes.
    
    Args:
        filename: Filename or Path object to extract prefix from.
        
    Returns:
        Extracted prefix string, or original filename if no marker found.
        
    Examples:
        >>> extract_paper_prefix("0478_s22_qp_12.pdf")
        '0478_s22'
        >>> extract_paper_prefix("9618_w21_ms_21.pdf")
        '9618_w21'
        >>> extract_paper_prefix(Path("/data/0470_m20_qp_11.pdf"))
        '0470_m20'
    """
    if isinstance(filename, Path):
        filename = filename.name
    
    # Match pattern before _qp_ or _ms_
    match = re.match(r"^(.+?)_(?:qp|ms)_", filename)
    if match:
        return match.group(1)
    
    # Fallback: return filename without extension
    return Path(filename).stem


def part_tokens(label: str) -> list[str]:
    """Parse a question label into hierarchical tokens.
    
    Extracts the question number and sub-part identifiers from a question label.
    Used for building file paths and organizing question assets.
    
    Args:
        label: Question label like "q3", "q5(a)", or "q1(a)(ii)".
        
    Returns:
        List of tokens representing the hierarchy, e.g. ["3", "a", "ii"].
        
    Examples:
        >>> part_tokens("q3")
        ['3']
        >>> part_tokens("q5(a)")
        ['5', 'a']
        >>> part_tokens("q1(a)(ii)")
        ['1', 'a', 'ii']
    """
    tokens: list[str] = []
    m = re.match(r"q(\d+)", label, re.IGNORECASE)
    remainder = label
    if m:
        tokens.append(m.group(1))
        remainder = remainder[m.end():]
    for piece in re.findall(r"\(([A-Za-z0-9]+)\)", remainder):
        tokens.append(piece.lower())
    if not tokens:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_")
        if cleaned:
            tokens.append(cleaned.lower())
    return tokens
