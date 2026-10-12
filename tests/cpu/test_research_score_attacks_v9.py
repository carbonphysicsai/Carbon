"""Collect RES-02's public research controls; no runtime behavior changes."""

import importlib.util
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[2]
    / "Business/research/score-candidate-attacks-v9/test_analyze.py"
)
SPEC = importlib.util.spec_from_file_location("research_attacks_v9_tests", SOURCE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
ResearchAttacksV9Tests = MODULE.ResearchAttacksV9Tests
