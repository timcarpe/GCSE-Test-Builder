"""Top-level package for the GCSE Test Builder.

Provides subpackages:
- gcse_toolkit.extractor – wrappers/aliases for the v2 extractor
- gcse_toolkit.builder – wrappers/aliases for the standalone builder
- gcse_toolkit.plugins – manifests and sub-topic mappings
- gcse_toolkit.gui – GUI app
"""

def _get_version() -> str:
    """Get version from pyproject.toml (dev) or importlib.metadata (installed)."""
    import sys
    from pathlib import Path
    
    # In dev mode, read directly from pyproject.toml
    if not getattr(sys, 'frozen', False):
        pyproject = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    else:
        # In frozen mode, read from bundle root
        pyproject = Path(getattr(sys, "_MEIPASS", ".")) / "pyproject.toml"
    
    if pyproject.exists():
        try:
            content = pyproject.read_text()
            for line in content.splitlines():
                if line.strip().startswith("version"):
                    # Parse: version = "0.2.7"
                    return line.split("=")[1].strip().strip('"').strip("'")
        except Exception:
            pass
    
    # Fallback to importlib.metadata for installed package
    try:
        from importlib.metadata import version as pkg_version
        return pkg_version("gcse_toolkit")
    except Exception:
        return "0.0.0"

__version__ = _get_version()
__copyright__ = "Copyright 2026 Timothy Carpenter Licensed under the Polyform Noncommercial License 1.0.0"
__all__: list[str] = ["__version__"]

