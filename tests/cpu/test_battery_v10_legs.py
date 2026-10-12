"""Registry v10's leg `v3s` and gate measure `sign` (SCORE-PROOF-01
amendment 11), on synthetic rows: no predictions, references or tuning data."""

from __future__ import annotations

import pytest

from carbon.battery.value import sign_gate as sg
from carbon.battery.value import verify_quiz as vq


def q(score, *statuses):
    return {"score": score, "attempt_statuses": list(statuses)}


def test_v3s_charges_an_infeasible_pick_kappa_units():
    clean = [q(0.0, "FEASIBLE"), q(0.5, "FEASIBLE")]
    assert vq.harsh_leg(clean) == pytest.approx(1 / (1 + 0.25))
    # An infeasible pick costs kappa even when a later pick returned a design.
    unsafe = [q(0.0, "INFEASIBLE", "FEASIBLE"), q(0.5, "FEASIBLE")]
    assert vq.harsh_leg(unsafe) == pytest.approx(1 / (1 + (vq.KAPPA + 0.5) / 2))
    assert vq.harsh_leg(unsafe) < vq.harsh_leg(clean)
    # Never a partial leg.
    assert vq.harsh_leg([q(None), q(0.0, "FEASIBLE")]) is None
    assert vq.KAPPA == 3.0 and vq.HARSH_LEG == "v3s"


def refs_for(cases):
    return {
        cid: {"inputs": inputs, "outputs": {"T": t, "P": p}}
        for cid, (inputs, t, p) in cases.items()
    }


def measure(contract, outputs):
    return {"peak_temperature_c": outputs["T"], "plating_margin_v": outputs["P"]}


BASE = {"c1": 1.0, "c2": 0.5, "soc0": 0.2, "t_amb_c": 25.0}
CASES = {
    "a": (BASE, 30.0, 0.10),
    "b": ({**BASE, "c1": 2.0}, 35.0, 0.05),  # faster: hotter, plates more
    "c": ({**BASE, "t_amb_c": 35.0}, 40.0, 0.12),  # warmer: hotter, plates less
    "d": ({**BASE, "soc0": 0.4, "c1": 3.0}, 50.0, 0.0),  # no partner: not a pair
}


def test_probe_pairs_differ_in_one_input_only():
    refs = refs_for(CASES)
    assert sg.probe_pairs(refs, list(refs), "c1") == [("a", "b")]
    assert sg.probe_pairs(refs, list(refs), "t_amb_c") == [("a", "c")]
    assert sg.probe_pairs(refs, list(refs), "c2") == []


def test_the_sign_measure_follows_the_reference_not_the_law():
    refs = refs_for(CASES)
    truthful = {cid: {"T": t, "P": p} for cid, (_, t, p) in CASES.items()}
    assert sg.sign_disagreement(None, truthful, list(refs), refs, measure) == 0.0
    # A localized sign error: plating improves with rate in the prediction.
    flipped = {**truthful, "b": {"T": 35.0, "P": 0.20}}
    share = sg.sign_disagreement(None, flipped, list(refs), refs, measure)
    assert share == pytest.approx(1 / 4)  # B5 c1, B6 c1, B7, B8 evaluable
    # Missing a prediction on an evaluable pair: unmeasured, never a pass.
    assert (
        sg.sign_disagreement(None, {"a": truthful["a"]}, list(refs), refs, measure)
        is None
    )
    # No evaluable pair at all: unmeasured.
    lone = refs_for({"d": CASES["d"]})
    assert sg.sign_disagreement(None, truthful, ["d"], lone, measure) is None
