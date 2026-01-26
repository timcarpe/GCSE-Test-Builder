#!/usr/bin/env python3
"""Launcher for the GCSE Test Builder GUI v2 (PySide6)."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists() and SRC.as_posix() not in sys.path:
    sys.path.insert(0, SRC.as_posix())

from gcse_toolkit.gui_v2.app import run


def main() -> int:
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
