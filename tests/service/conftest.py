"""Shared compiler fixtures for explicitly selected service-backed tests."""

from __future__ import annotations

import sys
from pathlib import Path

CPU_TESTS = Path(__file__).resolve().parents[1] / "cpu"
sys.path.insert(0, str(CPU_TESTS))
