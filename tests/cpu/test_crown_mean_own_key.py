"""A king's crown mean counts only on the exam it was measured on (Validator 5 Nov 06:24, NO CARRY).

The crown means filed at the Ribbed Bracket and Cooling switches are on the kings' PREVIOUS evaluation keys. Before this
fix `crown_average.screening` read the king's latest mean on ANY key, so once a king was regraded on the current key the
averaged rule met challengers against the old-exam mean. Claims: screening reads only the mean (and the unstable flag)
filed on the evaluation key of the king's grade in the pair; an old-key mean leaves him KING_UNMEASURED there (no rebuild
spent, nothing moves, the decision is queued by the caller); a mean filed on the current key is used; the card's
averaged bar follows the same rule. Synthetic grades; no model runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_crown_average_wiring import (
    KEY,
    Repeat,
    _active,
    _body,
    _comparator,
    _flow,
    _pair,
)

from carbon.challenge_validator import bank_promotion as bp
from carbon.challenge_validator import crown_average as ca
from carbon.challenge_validator.interface import digest

OLD = digest("the previous evaluation key")


def _king_on_current_key(total=0.70):
    return {**_body("a", total), "evaluation_key": KEY}


def test_an_old_key_mean_is_no_measure_of_the_current_exam(tmp_path, monkeypatch):
    a, b = _king_on_current_key(), _body("b", 0.95)
    store, flow = _flow(tmp_path, monkeypatch, {"b": _pair(b, a)})
    store.set_incumbent("a", bp.DEVELOPMENT_PROMOTION)
    store.record_crown_average(
        "a", OLD, {"mean": 0.60}
    )  # the 3 Nov measurement, the previous pack
    assert store.crown_mean("a") == pytest.approx(
        0.60
    )  # the key-blind read still sees it ...
    assert store.crown_mean("a", KEY) is None  # ... the current exam has no measurement
    repeat = Repeat("b", [0.95] * 10)
    outcome = flow.consider_private(
        "b", KEY, _comparator(), repeat=repeat, average=_active(tmp_path)
    )
    assert (outcome["outcome"], outcome["reason"]) == (
        bp.UNAVAILABLE,
        ca.KING_UNMEASURED,
    )
    assert repeat.asked == [] and store.incumbent()["model_id"] == "a"


def test_an_old_key_unstable_flag_does_not_stand_for_the_current_exam(
    tmp_path, monkeypatch
):
    a, b = _king_on_current_key(), _body("b", 0.95)
    store, flow = _flow(tmp_path, monkeypatch, {"b": _pair(b, a)})
    store.set_incumbent("a", bp.DEVELOPMENT_PROMOTION)
    store.record_crown_average("a", OLD, {"statuses": ["SCORED", "GATE_FAILED"]})
    assert store.crown_average_unstable("a") and not store.crown_average_unstable(
        "a", KEY
    )
    outcome = flow.consider_private(
        "b",
        KEY,
        _comparator(),
        repeat=Repeat("b", [0.95] * 10),
        average=_active(tmp_path),
    )
    assert outcome["reason"] == ca.KING_UNMEASURED


def test_a_mean_measured_on_the_current_key_is_the_bar(tmp_path, monkeypatch):
    # a's single grade (0.80) is lucky; its mean on THIS exam is 0.70; an old-exam mean of 0.90 must not be the bar
    a, b = _king_on_current_key(0.80), _body("b", 0.71)
    store, flow = _flow(tmp_path, monkeypatch, {"b": _pair(b, a)})
    store.set_incumbent("a", bp.DEVELOPMENT_PROMOTION)
    store.record_crown_average("a", OLD, {"mean": 0.90})
    store.record_crown_average("a", KEY, {"mean": 0.70})
    store.record_crown_average(
        "a", digest("an even older key"), {"mean": 0.95}
    )  # filed last, on another exam
    assert store.crown_mean("a", KEY) == pytest.approx(0.70)
    outcome = flow.consider_private(
        "b",
        KEY,
        _comparator(),
        repeat=Repeat("b", [0.71] * 10),
        average=_active(tmp_path),
    )
    assert outcome["outcome"] == bp.CHALLENGER


def test_a_grade_without_its_key_keeps_the_previous_read(tmp_path, monkeypatch):
    """An evaluation body always carries its key in the store; a body without one (older fixtures) reads as before."""
    a, b = _body("a", 0.80), _body("b", 0.71)
    store, flow = _flow(tmp_path, monkeypatch, {"b": _pair(b, a)})
    store.set_incumbent("a", bp.DEVELOPMENT_PROMOTION)
    store.record_crown_average("a", OLD, {"mean": 0.70})
    outcome = flow.consider_private(
        "b",
        KEY,
        _comparator(),
        repeat=Repeat("b", [0.71] * 10),
        average=_active(tmp_path),
    )
    assert outcome["outcome"] == bp.CHALLENGER
