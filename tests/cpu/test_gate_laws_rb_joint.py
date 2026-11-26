"""RB 2.0 and joint law sets (carbon/scoring/gate_laws/rb_2_0.py, joint.py) on synthetic toys.

Each toy obeys its laws by construction; each broken toy breaks one law, so every check is shown to fail. Every
layout, sampler, scale and tolerance here is a toy value for the toys, never a registered one.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from carbon.scoring import gate_laws as gl
from carbon.scoring.gate_laws import joint as jt
from carbon.scoring.gate_laws import rb_2_0 as rb

# --- RB toy: geometry (g0, g1) and a 4-cell load map; tip linear in the map, stress a Euclidean norm of a field
# linear in the map, mode free of the map.

RB_IN = ("g0", "g1", "w0", "w1", "w2", "w3")
RB_OUT = ("tip", "stress", "mode")
RB_BOX = gl.Box(
    lower=(1.0, 1.0, 0.0, 0.0, 0.0, 0.0), upper=(2.0, 2.0, 1.0, 1.0, 1.0, 1.0)
)
RB_FACTS = rb.RbFacts(
    input_names=RB_IN,
    map_columns=("w0", "w1", "w2", "w3"),
    draw_map=lambda rng, n: rng.dirichlet(np.ones(4), size=n),
    lam_range=(0.2, 0.8),
    output_names=RB_OUT,
    tip_outputs=("tip",),
    seminorm_outputs=("stress",),
    map_free_outputs=("mode",),
    u={"tip": 0.1, "stress": 0.1, "mode": 0.1},
)
RB_TOLS = {g: 0.5 for g in rb.GATE_IDS}
_FIELD = np.array(
    [[1.0, -2.0, 0.5], [0.3, 1.0, -1.0], [-1.5, 0.2, 2.0], [0.7, 0.7, 0.7]]
)
_TIP = np.array([1.0, -0.5, 2.0, 0.25])


def rb_toy(rows, *, tip_power=1.0, bump=0.0, mode_map=0.0):
    rows = np.asarray(rows, dtype=float)
    flat = rows.reshape(-1, rows.shape[-1])
    g, w = flat[:, :2], flat[:, 2:]
    scale = g[:, :1] * g[:, 1:]
    tip = scale[:, 0] * (w @ _TIP) ** tip_power
    stress = scale[:, 0] * np.linalg.norm(w @ _FIELD, axis=1) + bump * w[:, 0] * (
        1 - w[:, 0]
    )
    mode = g[:, 0] + g[:, 1] + mode_map * w[:, 0]
    return np.stack([tip, stress, mode], axis=1).reshape(rows.shape[:-1] + (3,))


def _rb_base(n=32, seed=4):
    rng = np.random.default_rng(seed)
    return np.hstack([1.0 + rng.random((n, 2)), rng.dirichlet(np.ones(4), size=n)])


def _rb_run(gid, model, facts=RB_FACTS):
    built, unbuilt = rb.gates(facts, RB_TOLS)
    assert unbuilt == {}
    gate = {g.gate_id: g for g in built}[gid]
    rows = gl.rows(gate, np.random.default_rng(9), _rb_base(), RB_BOX)
    return gl.verdicts(gate, rows, model(rows))


@pytest.mark.parametrize("gid", rb.GATE_IDS)
def test_the_rb_toy_passes(gid):
    assert np.all(_rb_run(gid, rb_toy) == gl.PASS)


@pytest.mark.parametrize(
    "gid,broken",
    [
        ("l1_tip_superposition", dict(tip_power=2.0)),
        ("l2_seminorm_triangle", dict(bump=50.0)),
        ("l3_load_independence", dict(mode_map=5.0)),
    ],
)
def test_each_rb_check_can_fail(gid, broken):
    assert np.any(_rb_run(gid, lambda r: rb_toy(r, **broken)) == gl.FAIL)


def test_a_table_keyed_on_geometry_and_map_fails_superposition_and_independence():
    base = _rb_base()
    exact = {r.tobytes(): a for r, a in zip(base, rb_toy(base))}

    def keyed(rows):
        flat = rows.reshape(-1, rows.shape[-1])
        out = np.array([exact.get(x.tobytes(), rb_toy(x[None])[0] + 1.0) for x in flat])
        return out.reshape(rows.shape[:-1] + (3,))

    for gid in ("l1_tip_superposition", "l3_load_independence"):
        assert np.all(_rb_run(gid, keyed) == gl.FAIL)


def test_rb_unset_facts_refuse():
    for field, code in (
        ("draw_map", "unset:draw_map"),
        ("lam_range", "unset:lam_range"),
    ):
        facts = dataclasses.replace(RB_FACTS, **{field: None})
        with pytest.raises(gl.GateRefused) as err:
            _rb_run("l1_tip_superposition", rb_toy, facts)
        assert err.value.code == code
    facts = dataclasses.replace(RB_FACTS, u={"tip": 0.1})
    with pytest.raises(gl.GateRefused) as err:
        _rb_run("l2_seminorm_triangle", rb_toy, facts)
    assert err.value.code == "unset:u:stress"


def test_rb_a_map_sampler_of_the_wrong_shape_refuses():
    facts = dataclasses.replace(RB_FACTS, draw_map=lambda rng, n: np.ones((n, 3)) / 3)
    with pytest.raises(gl.GateRefused) as err:
        _rb_run("l1_tip_superposition", rb_toy, facts)
    assert err.value.code == "draw_map"


# --- joint toy: two spots (x, y, power), h and coolant; temperatures above coolant, even in x, symmetric in the
# spots, rising with power, falling with h.

JT_IN = ("s0_x", "s0_y", "s0_p", "s1_x", "s1_y", "s1_p", "h", "coolant")
JT_OUT = ("peak", "mean")
JT_BOX = gl.Box(
    lower=(-5.0, -5.0, 1.0, -5.0, -5.0, 1.0, 100.0, 20.0),
    upper=(5.0, 5.0, 20.0, 5.0, 5.0, 20.0, 2000.0, 40.0),
)
JT_FACTS = jt.JointFacts(
    input_names=JT_IN,
    spot_blocks=(("s0_x", "s0_y", "s0_p"), ("s1_x", "s1_y", "s1_p")),
    spot_power=("s0_p", "s1_p"),
    mirror_pairs=(("s0_x", "s0_x"), ("s1_x", "s1_x")),
    h_name="h",
    coolant_name="coolant",
    power_scale=1.25,
    h_scale=1.25,
    coolant_drop=2.0,
    output_names=JT_OUT,
    temperature_outputs=("peak", "mean"),
    u={"peak": 0.5, "mean": 0.5},
)
JT_TOLS = {g: 0.5 for g in jt.GATE_IDS}


def jt_toy(rows, *, skew=0.0, order=0.0, power_sign=1.0, h_sign=-1.0):
    rows = np.asarray(rows, dtype=float)
    flat = rows.reshape(-1, rows.shape[-1])
    c = {n: flat[:, i] for i, n in enumerate(JT_IN)}
    h_term = (c["h"] / 1000.0) ** h_sign
    spots = []
    for k in (0, 1):
        x, y, p = c[f"s{k}_x"], c[f"s{k}_y"], c[f"s{k}_p"]
        weight = 1.0 + order * k
        spots.append(
            weight * (power_sign * p) * (2.0 + 0.05 * (x**2 + y**2) + skew * x)
        )
    peak = c["coolant"] + 10.0 * h_term * np.maximum(spots[0], spots[1])
    mean = c["coolant"] + 4.0 * h_term * (spots[0] + spots[1])
    return np.stack([peak, mean], axis=1).reshape(rows.shape[:-1] + (2,))


def _jt_base(n=32, seed=6):
    rng = np.random.default_rng(seed)
    lo = np.array([-5.0, -5.0, 1.0, -5.0, -5.0, 1.0, 100.0, 25.0])
    hi = np.array([5.0, 5.0, 10.0, 5.0, 5.0, 10.0, 1500.0, 40.0])
    return lo + rng.random((n, 8)) * (hi - lo)


def _jt_run(gid, model, facts=JT_FACTS):
    built, unbuilt = jt.gates(facts, JT_TOLS)
    assert unbuilt == {}
    gate = {g.gate_id: g for g in built}[gid]
    rows = gl.rows(gate, np.random.default_rng(2), _jt_base(), JT_BOX)
    return gl.verdicts(gate, rows, model(rows))


@pytest.mark.parametrize("gid", jt.GATE_IDS)
def test_the_joint_toy_passes(gid):
    assert np.all(_jt_run(gid, jt_toy) == gl.PASS)


@pytest.mark.parametrize(
    "gid,broken",
    [
        ("a5_spot_permutation", dict(order=0.5)),
        ("a7_mirror", dict(skew=0.5)),
        ("b1_power_monotone", dict(power_sign=-1.0)),
        ("b2_cooling_monotone", dict(h_sign=1.0)),
    ],
)
def test_each_joint_check_can_fail(gid, broken):
    assert np.any(_jt_run(gid, lambda r: jt_toy(r, **broken)) == gl.FAIL)


def test_joint_unset_facts_refuse():
    for field, gid in (
        ("mirror_pairs", "a7_mirror"),
        ("power_scale", "b1_power_monotone"),
        ("coolant_drop", "b2_cooling_monotone"),
        ("temperature_outputs", "a5_spot_permutation"),
    ):
        facts = dataclasses.replace(JT_FACTS, **{field: None})
        with pytest.raises(gl.GateRefused) as err:
            _jt_run(gid, jt_toy, facts)
        assert err.value.code == "unset:" + field


def test_joint_a_scale_that_cannot_test_the_law_refuses():
    facts = dataclasses.replace(JT_FACTS, power_scale=1.0)
    with pytest.raises(gl.GateRefused) as err:
        _jt_run("b1_power_monotone", jt_toy, facts)
    assert err.value.code == "power_scale"


def test_joint_names_no_registered_id():
    assert jt.CHALLENGE is None and jt.VERSION is None
