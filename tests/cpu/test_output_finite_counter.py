"""scripts/dev/output_finite_counter.py: its counting and x64 rule (numpy only; the graph run needs the inference
image and is receipted per run)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "dev" / "output_finite_counter.py"
)
_SPEC = importlib.util.spec_from_file_location("output_finite_counter", _PATH)
tool = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tool)


def test_a_row_counts_once_whatever_its_non_finite_values():
    block = np.zeros((4, 3, 2))
    block[1, 0, 0] = np.nan
    block[1, 2, 1] = np.inf
    block[3, 1, 1] = -np.inf
    assert tool._bad(block) == 2


def test_the_x64_rule_follows_the_inference_program():
    doc = {"graphs": {"main": {"inputs": [{"dtype": "float32"}]}}}
    small = np.zeros(2, dtype=np.float32)
    assert tool._x64(doc, small, [small]) is False
    assert tool._x64(doc, small, [np.zeros(2)]) is True  # a float64 parameter
    assert tool._x64(doc, small, [small], "float64") is True  # the interface's output
    assert tool._x64({"x": [{"dtype": "int64"}]}, small, []) is True
