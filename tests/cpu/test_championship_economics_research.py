"""Collect the public research controls in the canonical CPU suite."""

import importlib.util
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[2]
    / "Business/research/championship-economics-sim/test_simulate.py"
)
SPEC = importlib.util.spec_from_file_location("economics_research_tests", SOURCE)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
EconomicsTests = MODULE.EconomicsTests
