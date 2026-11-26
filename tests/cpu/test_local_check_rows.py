"""The local scorer's verify check for a family no code names (miner-ux 8683, shared item).

Claims:
1. MOTOR UNCHANGED: Motor keeps its code row (`LOCAL_CHECKS`), its truth check and its U keys.
2. BINDING CHECK: any other Challenge is checked with the gates and derive of its registered pool binding, the ones the
   official grade reads: gate verdicts by name, SCORABLE or GATE_FAILED, and accuracy within the verify set's U per
   derived output it names. A derived value the binding cannot give is never within U.
3. FAIL CLOSED: a Challenge with no pool kind, or an overlay version whose binding is not registered in this process,
   refuses; the static adapter of another version is never used.
4. VERIFY TRUTH: a binding-checked design carries a finite raw output row; the Motor default is as before.

Every value is a SYNTHETIC fixture; no pool, pack or custody material is read.
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from carbon.challenge_kit import local_scorer as ls

NAMES = ("a", "b")


def _binding(failed=lambda inputs, raw: (), derive=None):
    def default_derive(inputs, raw):
        return {"peak": raw[0], "sum": raw[0] + raw[1]}

    return SimpleNamespace(
        input_names=NAMES,
        derive=derive or default_derive,
        physics_gates=SimpleNamespace(gate_names=("finite", "ordered"), failed=failed),
    )


def _design(truth=(1.0, 2.0)):
    return {
        "case_id": "d1",
        "inputs": {"a": 0.5, "b": 0.25},
        "truth": {"raw": list(truth)},
    }


# ---------------------------------------------------------------- 1. Motor


def test_motor_keeps_its_code_row():
    check = ls.local_check(ls.MOTOR, "1.8")
    assert check.per_design is ls._motor_design
    assert check.aggregate is ls._motor_aggregate
    assert check.u is ls._u
    assert check.truth_error is ls._motor_truth_error


# ---------------------------------------------------------------- 2. the binding check


def test_gates_by_name_and_accuracy_within_u():
    check = ls._binding_check(_binding())
    u = check.u({"u": {"peak": 0.1, "sum": 0.01}})
    assert u == {"peak": 0.1, "sum": 0.01}
    row = check.per_design(_design(), [1.05, 2.0], u)
    assert row["state"] == ls.SCORABLE
    assert row["gates"] == {"finite": ls.PASS, "ordered": ls.PASS}
    assert row["accuracy_vs_u"]["peak"]["within_u"] is True
    assert row["accuracy_vs_u"]["sum"]["within_u"] is False
    assert row["accuracy_vs_u"]["within_u"] is False
    summary = check.aggregate([row], u)
    assert summary["n_scorable"] == 1 and summary["gate_failures"] == {}
    assert summary["accuracy_vs_u"] == {"peak": 1, "sum": 0, "n_within_u": 0}


def test_a_failed_gate_is_gate_failed_by_name():
    check = ls._binding_check(_binding(failed=lambda inputs, raw: ("ordered",)))
    row = check.per_design(_design(), [1.0, 2.0], None)
    assert row["state"] == ls.GATE_FAILED
    assert row["gates"] == {"finite": ls.PASS, "ordered": ls.FAIL}
    assert row["accuracy_vs_u"]["status"] == ls.NOT_EVALUATED
    summary = check.aggregate([row], None)
    assert summary["n_gate_failed"] == 1 and summary["gate_failures"] == {"ordered": 1}


def test_a_value_the_binding_cannot_derive_is_never_within_u():
    def derive(inputs, raw):
        raise ValueError("unreadable")

    check = ls._binding_check(_binding(derive=derive))
    row = check.per_design(_design(), [1.0, 2.0], {"peak": 10.0})
    assert row["accuracy_vs_u"]["peak"]["delta"] is None
    assert row["accuracy_vs_u"]["within_u"] is False
    # a U name the binding does not derive
    check = ls._binding_check(_binding())
    row = check.per_design(_design(), [1.0, 2.0], {"mass": 10.0})
    assert row["accuracy_vs_u"]["within_u"] is False


def test_inputs_follow_the_binding_and_a_mismatch_refuses():
    seen = {}

    def failed(inputs, raw):
        seen.update(inputs)
        return ()

    ls._binding_check(_binding(failed=failed)).per_design(_design(), [1.0, 2.0], None)
    assert seen == {"a": 0.5, "b": 0.25}
    design = _design()
    del design["inputs"]["b"]
    with pytest.raises(ls.ScorerRefused):
        ls._binding_check(_binding()).per_design(design, [1.0, 2.0], None)


@pytest.mark.parametrize("u", [None, {}, {"peak": -1.0}, {"peak": "1"}, [1.0]])
def test_an_unregistered_u_is_none(u):
    assert ls._named_u({"u": u}) is None


# ---------------------------------------------------------------- 3. fail closed


def test_a_challenge_with_no_pool_kind_refuses():
    with pytest.raises(ls.ScorerRefused):
        ls.local_check("no-such-challenge", "1.0")


def test_an_overlay_version_without_its_binding_refuses(monkeypatch):
    from carbon.challenge_kit import version_overlay
    from carbon.scoring import pool_version

    monkeypatch.setitem(pool_version.KINDS, "synthetic-family", "synthetic")
    monkeypatch.setattr(version_overlay, "is_overlay", lambda cid, ver: True)
    with pytest.raises(ls.ScorerRefused, match="not registered in this process"):
        ls.local_check("synthetic-family", "9.9")


def test_a_registered_binding_is_the_one_checked(monkeypatch):
    from carbon.challenge_kit import version_overlay
    from carbon.scoring import pool_version

    binding = _binding()
    monkeypatch.setitem(pool_version.KINDS, "synthetic-family", "synthetic")
    monkeypatch.setitem(pool_version._BINDINGS, ("synthetic", "9.9"), lambda: binding)
    monkeypatch.setattr(version_overlay, "is_overlay", lambda cid, ver: True)
    check = ls.local_check("synthetic-family", "9.9")
    assert check.truth_error is ls._raw_truth_error
    row = check.per_design(_design(), [1.0, 2.0], None)
    assert row["gates"] == {"finite": ls.PASS, "ordered": ls.PASS}


# ---------------------------------------------------------------- 4. verify truth


def _verify(designs):
    raw = json.dumps({"designs": designs}).encode()
    return raw, hashlib.sha256(raw).hexdigest()


def test_a_binding_checked_verify_set_needs_a_raw_truth_row():
    raw, sha = _verify([_design()])
    document = ls.load_verify_set(raw, sha, NAMES, truth_error=ls._raw_truth_error)
    assert document["designs"][0]["truth"]["raw"] == [1.0, 2.0]
    bad = _design()
    bad["truth"] = {"raw": [1.0, "x"]}
    raw, sha = _verify([bad])
    with pytest.raises(ls.ScorerRefused, match="raw output row"):
        ls.load_verify_set(raw, sha, NAMES, truth_error=ls._raw_truth_error)


def test_the_default_truth_check_is_motor_as_before():
    raw, sha = _verify([_design()])
    with pytest.raises(ls.ScorerRefused, match="the truth curve is malformed"):
        ls.load_verify_set(raw, sha, NAMES)
