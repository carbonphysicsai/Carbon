"""Practice feedback from the dual measurement (C13; VALIDATOR_DESIGN_VALUE_SCORE_GAP_20261022).

One feedback document per model on the Challenge's PUBLIC development bank:
gates first, then accuracy, design value and the total in (0, 1], 1 best. A
stand-in "perfect" model returns the bank's own reference rows."""

from __future__ import annotations

import importlib

import numpy as np
import pytest

from carbon.challenge_kit import battery_pack, physical_pack
from carbon.scoring import practice_dual as pdual

PHYSICAL = ("motor", "cooling", "f08", "f02")


def _adapter(name):
    return importlib.import_module(f"carbon.scoring.{name}_dual_pack")


def _references(adapter, name):
    if name == "battery":
        bank = battery_pack.development_bank(adapter.VERSION)
        rows = np.asarray(bank["references"], dtype=float)
        fill = rows[~np.isnan(rows).any(axis=1)][0]
        return [list(r) if not np.isnan(r).any() else list(fill) for r in rows]
    bank = physical_pack.development_bank(adapter.CHALLENGE, adapter.VERSION)
    return [list(map(float, r)) for r in bank["references"]]


@pytest.mark.parametrize("name", (*PHYSICAL, "battery"))
def test_a_reference_model_is_eligible_and_scored_in_unit_range(name):
    adapter = _adapter(name)
    refs = _references(adapter, name)
    document = pdual.feedback(adapter, lambda cases: refs)
    assert document["schema"] == pdual.SCHEMA and document["available"] is True
    assert document["scope"] == pdual.SCOPE
    assert document["gates"] and all(document["gates"].values())
    assert document["eligible"] is True
    assert type(document["n_cases"]) is int and document["n_cases"] > 0
    a, d, total = (document[k] for k in ("accuracy", "design_value", "total"))
    assert 0 < a <= 1 and 0 < d <= 1
    assert total == pytest.approx(0.5 * a + 0.5 * d) and 0 < total <= 1
    # Only the registered fields; no sealed or hidden material.
    assert set(document) == {
        "schema",
        "scope",
        "challenge",
        "available",
        "n_cases",
        "gates",
        "eligible",
        "total",
        "accuracy",
        "design_value",
        "decision_outcome",
        "note",
    }


def test_a_gate_failure_is_not_eligible_and_shows_no_number():
    adapter = _adapter("motor")
    refs = _references(adapter, "motor")
    broken = [list(r) for r in refs]
    broken[0][0] = float("nan")
    document = pdual.feedback(adapter, lambda cases: broken)
    assert document.get("eligible") is not True
    assert document.get("total") is None
    assert document.get("accuracy") is None and document.get("design_value") is None


def test_a_predict_fault_is_typed_not_raised():
    def broken(cases):
        raise RuntimeError("model blew up")

    document = pdual.feedback(_adapter("motor"), broken)
    assert document["available"] is False
    assert document["reason"] == "practice_predict_failed"
    assert "total" not in document
