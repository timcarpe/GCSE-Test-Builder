# GCSE Test Builder - Dependency Management

## Installing Dependencies

### For Users (Runtime Dependencies)
```bash
pip install -r requirements.txt
```

### For Developers (Runtime + Development Tools)
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Using pip-editable Install (Recommended for Development)
```bash
pip install -e .
pip install -r requirements-dev.txt
```

## Package Organization

### requirements.txt
Contains all runtime dependencies needed to run the toolkit:
- **Core:** Pillow, numpy, PyMuPDF (from pyproject.toml)
- **GUI:** customtkinter
- **Config:** pyyaml  
- **Testing:** pytest, pytest-cov

### requirements-dev.txt
Contains development and testing tools:
- **Type Checking:** mypy
- **Testing:** pytest, pytest-cov

### pyproject.toml
Defines the core package dependencies for pip installation:
- Minimal set: Pillow, numpy, PyMuPDF
- Additional dependencies (customtkinter, pyyaml) should be installed from requirements.txt

## Removed Dependencies

The following packages were removed as they were not used:
- ❌ nltk
- ❌ transformers
- ❌ torch

This saves ~2GB of installation space and reduces installation time.

## Version Pinning

Currently using unpinned versions for flexibility during development.

**For Production:** Consider using `pip-compile` to create locked versions:
```bash
pip install pip-tools
pip-compile requirements.in -o requirements.txt
pip-compile requirements-dev.in -o requirements-dev.txt
```

## Notes

- Python 3.10+ required (specified in pyproject.toml)
- All packages are available on PyPI
- No private or proprietary packages
