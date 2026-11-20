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


def test_the_x64_rule_reads_the_inputs_own_dtype_when_none_is_served():
    doc = {"graphs": {"main": {"inputs": [{"dtype": "float32"}]}}}
    small = np.zeros(2, dtype=np.float32)
    assert (
        tool._x64(doc, np.zeros(2), [small]) is True
    )  # float64 inputs, no served dtype
    assert tool._x64(doc, small, [small], None) is False


def test_the_contract_reads_the_served_shape_tail_and_dtype():
    control = {"expected_output_shape": [2564, 240], "expected_output_dtype": "float32"}
    good = np.zeros((7, 240), dtype=np.float32)
    assert tool._contract(good, 7, control) == {
        "shape_matches": True,
        "dtype_matches": True,
    }
    narrow = np.zeros((7, 239), np.float32)
    assert tool._contract(narrow, 7, control)["shape_matches"] is False
    assert tool._contract(good.astype(np.float64), 7, control)["dtype_matches"] is False
    unserved = {"expected_output_shape": [3, 2]}
    assert tool._contract(np.zeros((5, 2)), 5, unserved)["dtype_matches"] is True
    assert tool._contract(np.zeros((5, 2), bool), 5, unserved)["dtype_matches"] is False


def test_the_decoder_applies_after_the_concatenation_as_live():
    blocks = [np.ones((1, 2), np.float32), np.full((1, 2), 2, np.float32)]
    assert tool._graded(blocks).dtype == np.float32
    mu, sd = np.zeros(2), np.full(2, 3.0)  # a float64 decoder upcasts, exactly as live
    decoded = tool._graded(blocks, (mu, sd))
    assert decoded.dtype == np.float64 and decoded.tolist() == [[3.0, 3.0], [6.0, 6.0]]
    huge = tool._graded(blocks, (np.zeros(2), np.full(2, np.inf)))
    assert tool._bad(huge) == 2


def test_the_control_must_bind_the_state_recipe_and_allowlist():
    import hashlib
    from types import SimpleNamespace

    import pytest

    state = b"state"
    recipe = SimpleNamespace(digest="sha256:r")
    allowed = SimpleNamespace(digest="sha256:a")
    control = {
        "recipe_digest": "sha256:r",
        "state_digest": "sha256:" + hashlib.sha256(state).hexdigest(),
        "allowlist_digest": "sha256:a",
        "expected_output_shape": [4, 2],
    }
    tool._bind(control, state, recipe, allowed)
    for name in ("recipe_digest", "state_digest", "allowlist_digest"):
        with pytest.raises(ValueError, match="does not bind"):
            tool._bind({**control, name: "sha256:x"}, state, recipe, allowed)
    with pytest.raises(ValueError, match="expected_output_shape"):
        tool._bind({**control, "expected_output_shape": []}, state, recipe, allowed)
