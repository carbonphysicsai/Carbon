"""R3: self-trust on the pool route (`carbon.scoring.pool_trust`; model-eval 5685).

Synthetic pool grades only: a per-case record shaped like `case_errors.assemble`'s, and a candidate ``sigma.json`` of
raw log-sigma columns. The 4 variants of the owner's selftest (honest / x0.1 / x10 / constant) on heteroscedastic
classes, read through the same transform the trust trainer uses (sigma = floor + exp(log_sigma)). Fixture floors only.
"""

from __future__ import annotations

import json
import math
from statistics import NormalDist

import pytest

from carbon.scoring import pool_trust as pt
from carbon.scoring import self_trust as st

TRUST = pt.PoolTrust(outputs=("f_hz", "s_mpa"), sigma_floor=(0.0, 0.01))
LEVEL = st.OWNER_AMPLIFIER.band_level  # the owner's 90% band
SCALES = {"K1": 0.5, "K2": 1.0, "K3": 2.0}  # the true error scale of each class
N = 120  # cases per class
ADMITTED = [("fam", "K1", "f_hz"), ("fam", "K2", "f_hz"), ("fam", "K3", "f_hz")]


def _content():
    """One answered case per bank row: class K_i, |error| at the exact quantiles of
    N(0, s^2) on f_hz, U 1; s_mpa is measured but never admitted."""
    rows, classes, abs_error, u = [], [], [], []
    names = sorted(SCALES)
    for c, name in enumerate(names):
        for i in range(N):
            e = abs(SCALES[name] * NormalDist().inv_cdf((i + 0.5) / N))
            rows.append(len(rows))
            classes.append(c)
            abs_error.append([e, 3.0])
            u.append([1.0, 1.0])
    return {
        "row_index": rows,
        "class_index": classes,
        "class_names": names,
        "invalid": [False] * len(rows),
        "output_names": ["f_hz", "s_mpa"],
        "abs_error": abs_error,
        "u": u,
    }


def _sigma_json(stated):
    """A candidate's raw trust columns: log(sigma - floor) per row, sigma = stated(s)."""
    content = _content()
    out = []
    for c in content["class_index"]:
        s = stated(SCALES[content["class_names"][c]])
        out.append(
            [math.log(s - TRUST.sigma_floor[0]), math.log(1.0 - TRUST.sigma_floor[1])]
        )
    return json.dumps(out).encode()


def _t(stated):
    content = _content()
    sigma = pt.sigma_rows(_sigma_json(stated), len(content["row_index"]), TRUST)
    return pt.record(content, sigma, ADMITTED, TRUST, LEVEL)


def _best_constant():
    content = _content()
    cases = [
        st.TrustCase(
            predictions={"f_hz": row[0]},
            truths={"f_hz": 0.0},
            u={"f_hz": 1.0},
            status=st.PRESENT,
            answer=None,
        )
        for row in content["abs_error"]
    ]
    w, _ = st.best_constant_half_width(LEVEL, cases, "f_hz")
    return w


def test_selftest_4_variants_through_the_pool_record():
    honest = _t(lambda s: s)
    over = _t(lambda s: 0.1 * s)
    under = _t(lambda s: 10.0 * s)
    z = NormalDist().inv_cdf((1 + LEVEL) / 2)
    w = _best_constant()
    constant = _t(lambda s: w / z)
    for out in (honest, over, under, constant):
        assert out["status"] == st.SCORED and out["n_cells"] == 3
    # one T_cell per admitted class: within one class sigma is constant, so the per-cell
    # reference is that class's own best constant band and honest is ~ it (T_cell ~ 0)
    # while x0.1 / x10 lose to it in every class
    assert all(v is not None for _, _, v in honest["cells"])
    assert over["t"] < -0.5 and under["t"] < -1.0
    assert honest["t"] > max(over["t"], under["t"])
    assert honest["t"] == pytest.approx(0.0, abs=0.05)
    assert constant["t"] <= honest["t"] + 1e-9
    multiplier = {
        name: st.multiplier(out["t"], st.OWNER_AMPLIFIER)
        for name, out in (("x0.1", over), ("x10", under))
    }
    assert multiplier == {"x0.1": pytest.approx(0.9), "x10": pytest.approx(0.9)}


def test_one_cell_over_all_classes_rewards_honest_per_case_sigma():
    """Admit one cell spanning heteroscedastic cases (every case in class K): honest
    per-case sigma beats the one constant band (T > 0), the constant at w* scores 0."""
    content = _content()
    content["class_index"] = [0] * len(content["row_index"])
    content["class_names"] = ["K"]
    admitted = [("fam", "K", "f_hz")]

    def t_of(stated):
        sigma_json = []
        for c in _content()["class_index"]:
            s = stated(SCALES[sorted(SCALES)[c]])
            sigma_json.append([math.log(s), 0.0])
        sigma = pt.sigma_rows(
            json.dumps(sigma_json).encode(), len(content["row_index"]), TRUST
        )
        return pt.record(content, sigma, admitted, TRUST, LEVEL)["t"]

    w = _best_constant()
    z = NormalDist().inv_cdf((1 + LEVEL) / 2)
    honest = t_of(lambda s: s)
    over = t_of(lambda s: 0.1 * s)
    under = t_of(lambda s: 10 * s)
    constant = t_of(lambda s: w / z)
    assert honest > 0.05
    assert over < 0 and under < 0
    assert constant == pytest.approx(0.0, abs=1e-9)


def test_no_sigma_is_absent_t_zero_and_unreadable_is_invalid_t_zero():
    content = _content()
    n = len(content["row_index"])
    absent = pt.record(content, pt.sigma_rows(None, n, TRUST), ADMITTED, TRUST, LEVEL)
    assert absent["status"] == st.ABSENT and absent["t"] == 0.0
    bad = (
        b"not json",
        b"[]",
        json.dumps([[0.0]] * n).encode(),
        json.dumps([[0.0, float("inf")]] * n).encode(),
    )
    for raw in bad:
        sigma = pt.sigma_rows(raw, n, TRUST)
        assert sigma is None
        out = pt.record(content, sigma, ADMITTED, TRUST, LEVEL)
        assert out["status"] == st.INVALID and out["t"] == 0.0


def test_the_transform_is_the_trainers_floor_plus_exp():
    rows = pt.sigma_rows(json.dumps([[0.0, math.log(2.0)]]).encode(), 1, TRUST)
    assert rows[0]["f_hz"] == 1.0
    assert rows[0]["s_mpa"] == pytest.approx(0.01 + 2.0)


def test_only_admitted_cells_and_valid_answers_are_read():
    content = _content()
    content["invalid"][0] = True
    out = _t(lambda s: s)
    assert {(c, o) for c, o, _ in out["cells"]} == {
        ("K1", "f_hz"),
        ("K2", "f_hz"),
        ("K3", "f_hz"),
    }  # s_mpa is measured but no cell admits it
    none = pt.record(
        content,
        pt.sigma_rows(_sigma_json(lambda s: s), len(content["row_index"]), TRUST),
        [("fam", "K9", "f_hz")],
        TRUST,
        LEVEL,
    )
    assert none["t"] == 0.0 and none["reason"] == "pool_trust_no_admitted_trust_cell"


def test_the_record_is_json_safe_and_deterministic():
    a, b = _t(lambda s: s), _t(lambda s: s)
    assert a == b
    json.dumps(a, allow_nan=False)


def test_registration_refusals_and_empty_gate():
    assert pt.POOL_TRUST == {}
    for bad in (
        pt.PoolTrust(outputs=(), sigma_floor=()),
        pt.PoolTrust(outputs=("a", "a"), sigma_floor=(0.0, 0.0)),
        pt.PoolTrust(outputs=("a",), sigma_floor=(-1.0,)),
        pt.PoolTrust(outputs=("a",), sigma_floor=(0.0, 0.0)),
    ):
        with pytest.raises(pt.PoolTrustRefused):
            pt.check(bad)


# -- the grade hook (lean_recipe_retention._write_trust_record) ------------------------------------------------------


def _accuracy():
    return {
        "rows": [
            {"family": "fam", "class": c, "output": o, "scored": c != "K9"}
            for c in ("K1", "K2", "K3", "K9")
            for o in ("f_hz", "s_mpa")
            if o == "f_hz" or c == "K9"
        ]
    }


def test_admitted_cells_come_from_the_accuracy_records_scored_rows():
    assert pt.admitted_cells(_accuracy()) == ADMITTED


class _Adapter:
    challenge_id, challenge_version = "rb-test", "9.9"


class _Snapshot:
    manifest_digest = "sha256:" + "ab" * 32


def _hook(tmp_path, monkeypatch, *, registered, sigma):
    from carbon.challenge_validator import lean_recipe_retention as lrr

    journal = []
    monkeypatch.setattr(lrr, "_journal", lambda event, **f: journal.append((event, f)))
    if registered:
        monkeypatch.setitem(pt.POOL_TRUST, ("rb-test", "9.9"), TRUST)
    captured = {"case_errors": _content(), "accuracy": _accuracy()}
    artifacts = {} if sigma is None else {"sigma.json": sigma}
    lrr._write_trust_record(
        _Adapter(), "task-1", _Snapshot(), tmp_path, artifacts, captured
    )
    return journal


def test_the_hook_reads_and_writes_nothing_for_an_unregistered_version(
    tmp_path, monkeypatch
):
    journal = _hook(tmp_path, monkeypatch, registered=False, sigma=b"x")
    assert journal == [] and list(tmp_path.iterdir()) == []


def test_the_hook_writes_the_custody_record_for_a_trust_version(tmp_path, monkeypatch):
    journal = _hook(
        tmp_path, monkeypatch, registered=True, sigma=_sigma_json(lambda s: s)
    )
    document = json.loads((tmp_path / pt.SIDECAR).read_bytes())
    assert document["schema"] == pt.SCHEMA and document["band_level"] == 0.9
    assert document["amplified"] is False  # no version is switched on
    assert document["record"]["status"] == st.SCORED
    assert document["record"]["n_cells"] == 3
    assert journal == [
        ("grade_trust", {"task": "task-1", "status": "scored", "cells": 3})
    ]


def test_the_hook_records_an_absent_block_as_t_zero(tmp_path, monkeypatch):
    _hook(tmp_path, monkeypatch, registered=True, sigma=None)
    document = json.loads((tmp_path / pt.SIDECAR).read_bytes())
    assert document["record"]["status"] == st.ABSENT
    assert document["record"]["t"] == 0.0


def test_the_hook_never_raises(tmp_path, monkeypatch):
    from carbon.challenge_validator import lean_recipe_retention as lrr

    journal = []
    monkeypatch.setattr(lrr, "_journal", lambda event, **f: journal.append((event, f)))
    monkeypatch.setitem(pt.POOL_TRUST, ("rb-test", "9.9"), TRUST)
    captured = {"case_errors": {"bad": 1}, "accuracy": _accuracy()}
    lrr._write_trust_record(_Adapter(), "task-1", _Snapshot(), tmp_path, {}, captured)
    assert journal and journal[0][0] == "grade_sidecar_unwritten"
