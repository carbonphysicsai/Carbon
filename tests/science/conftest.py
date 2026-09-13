"""Shared path setup for compiler fixtures used by the explicit science lane."""

from __future__ import annotations

import sys
from pathlib import Path

CPU_TESTS = Path(__file__).resolve().parents[1] / "cpu"
sys.path.insert(0, str(CPU_TESTS))
