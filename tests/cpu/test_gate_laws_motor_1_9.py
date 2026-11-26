"""Motor 1.9 law set (carbon/scoring/gate_laws/motor_1_9.py) on synthetic toys.

The toy motor below obeys every written law by construction; each broken toy breaks exactly one, so each check is
shown to fail. Every fact and tolerance here is a toy number for the toys, never a registered value.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from carbon.motor import domain, row19
from carbon.scoring import gate_laws as gl
from carbon.scoring.gate_laws import motor_1_9 as m

NAMES = domain.INPUTS
NAMES_BR = NAMES + ("br",)
BOX = gl.Box(
    lower=tuple(domain.INPUT_BOUNDS[n][0] for n in NAMES),
    upper=tuple(domain.INPUT_BOUNDS[n][1] for n in NAMES),
)
BOX_BR = gl.Box(lower=BOX.lower + (1.0,), upper=BOX.upper + (1.5,))
WINDING = {"A": ("B", -1.0), "B": ("C", -1.0), "C": ("A", -1.0)}
FACTS = m.MotorFacts(
    input_names=NAMES,
    u_torque=0.1,
    u_linkage=1e-3,
    u_magnet=0.01,
    j0=1.0,
    winding=WINDING,
    motoring_window=(0.0, 60.0),
    br_fixed=1.2,
    remanence_scales=(0.9, 1.1),
    knee_t=0.1,
    smooth_steps=("ulp", 1e-6),
    m3_skip_cap=1.0,
    gap_radius_mm=lambda case: 25.6 + case["airgap_mm"] / 2,
    m7_bound_checked="toy",
)
TOLS = {gid: 0.5 for gid in m.GATE_IDS}
THETA = np.radians(
    np.arange(domain.ANGLE_STEPS, dtype=float)
)  # 60 electrical degrees over one slot pitch
PHASE = {"A": 0.0, "B": np.radians(120.0), "C": np.radians(240.0)}


def toy(
    rows,
    names=NAMES,
    *,
    drift=0.0,
    link_sign=1.0,
    quad=0.0,
    magnet_over=0.0,
    flip=1.0,
    br_power=1.0,
):
    """A smooth toy motor: mean torque k J cos(psi), a slot-periodic ripple, linkages of a balanced winding with a
    magnet part proportional to br, and a magnet field below br. Each keyword breaks one law.
    """
    rows = np.asarray(rows, dtype=float)
    flat = rows.reshape(-1, rows.shape[-1])
    col = {n: flat[:, i] for i, n in enumerate(names)}
    j, psi = col["current_density_a_mm2"], np.radians(col["current_angle_deg"])
    br = col["br"] if "br" in col else np.full(len(flat), 1.2)
    mean = flip * (0.1 * j * np.cos(psi) + quad * j**2)  # below the M7 bound
    ripple = (
        0.02 * (1 + j / 15)[:, None] * np.sin(2 * np.pi * np.arange(60) / 60)[None, :]
    )
    torque = mean[:, None] + ripple + drift * np.arange(60)[None, :]
    links = []
    for p in "ABC":
        lam = 0.01 * br[:, None] ** br_power * np.cos(THETA[None, :] - PHASE[p])
        lam = lam + 0.001 * j[:, None] * np.cos(
            THETA[None, :] - PHASE[p] - psi[:, None]
        )
        links.append(lam)
    links[0] = links[0] * link_sign
    magnet = 0.8 * br - 0.01 * j + magnet_over
    out = np.concatenate([torque, *links, magnet[:, None]], axis=1)
    assert out.shape[1] == row19.WIDTH
    return out.reshape(rows.shape[:-1] + (row19.WIDTH,))


def _draw(n=24, box=BOX, seed=11):
    rng = np.random.default_rng(seed)
    return box.lo + rng.random((n, len(box.lower))) * box.width


def _run(gate, model, box=BOX, base=None):
    base = _draw(box=box) if base is None else base
    rows = gl.rows(gate, np.random.default_rng(3), base, box)
    return gl.verdicts(gate, rows, model(rows))


def _gate(gid, facts=FACTS):
    built, unbuilt = m.gates(facts, TOLS)
    assert gid not in unbuilt, unbuilt
    return {g.gate_id: g for g in built}[gid]


def test_every_written_law_is_built_from_full_facts():
    built, unbuilt = m.gates(FACTS, TOLS)
    assert [g.gate_id for g in built] == list(m.GATE_IDS)
    assert unbuilt == {}


@pytest.mark.parametrize("gid", [g for g in m.GATE_IDS if g != "m5_remanence_scaling"])
def test_the_toy_motor_passes(gid):
    got = _run(_gate(gid), toy)
    assert np.all(got != gl.FAIL)
    assert np.any(got == gl.PASS)


def test_the_toy_motor_passes_remanence_scaling_with_a_br_input():
    facts = dataclasses.replace(FACTS, input_names=NAMES_BR)
    gate = _gate("m5_remanence_scaling", facts)
    base = _draw(box=BOX_BR)
    base[:, -1] = 1.2  # 0.9 and 1.1 times it stay in the toy box
    got = _run(gate, lambda r: toy(r, NAMES_BR), box=BOX_BR, base=base)
    assert np.all(got == gl.PASS)


BROKEN = [
    ("m1_torque_wrap", dict(drift=0.01)),
    ("m1_linkage_wrap", dict(link_sign=-1.0)),
    ("m3_low_current_linear", dict(quad=0.2)),
    ("m6_magnet_bound", dict(magnet_over=1.0)),
    ("m7_torque_bound", dict(quad=5.0)),
    ("m8_motoring_sign", dict(flip=-1.0)),
]


@pytest.mark.parametrize("gid,broken", BROKEN)
def test_each_check_can_fail(gid, broken):
    got = _run(_gate(gid), lambda r: toy(r, **broken))
    assert np.any(got == gl.FAIL)


def test_open_circuit_fails_a_model_with_torque_at_no_current():
    got = _run(
        _gate("m2_open_circuit_torque"),
        lambda r: toy(r) + np.r_[np.full(60, 1.0), np.zeros(181)],
    )
    assert np.all(got == gl.FAIL)


def test_remanence_scaling_fails_a_model_that_ignores_br():
    facts = dataclasses.replace(FACTS, input_names=NAMES_BR)
    gate = _gate("m5_remanence_scaling", facts)
    base = _draw(box=BOX_BR)
    base[:, -1] = 1.2
    got = _run(gate, lambda r: toy(r, NAMES_BR, br_power=0.0), box=BOX_BR, base=base)
    assert np.all(got == gl.FAIL)


def _nearest_table(train):
    """A nearest-neighbour table of training rows: real toy curves, but piecewise constant between them."""
    answers = toy(train)
    scale = BOX.width

    def model(rows):
        flat = rows.reshape(-1, rows.shape[-1])
        dist = (((flat[:, None, :] - train[None, :, :]) / scale) ** 2).sum(-1)
        return answers[np.argmin(dist, axis=1)].reshape(
            rows.shape[:-1] + (row19.WIDTH,)
        )

    return model


def test_a_nearest_neighbour_table_fails_open_circuit():
    train = _draw(n=40, seed=5)
    j = NAMES.index("current_density_a_mm2")
    train[:, j] = np.maximum(train[:, j], 3.0)  # no current-free row in its table
    assert np.all(
        _run(_gate("m2_open_circuit_torque"), _nearest_table(train)) == gl.FAIL
    )


def test_a_table_of_the_scored_rows_fails_smoothness():
    scored = _draw(n=8, seed=5)
    exact = {r.tobytes(): a for r, a in zip(scored, toy(scored))}

    def keyed(rows):
        flat = rows.reshape(-1, rows.shape[-1])
        out = np.array([exact.get(x.tobytes(), toy(x[None])[0] + 1.0) for x in flat])
        return out.reshape(rows.shape[:-1] + (row19.WIDTH,))

    assert np.all(_run(_gate("m9_smooth"), keyed, base=scored) == gl.FAIL)


def test_low_current_skips_a_tiny_denominator_as_not_applicable():
    got = _run(_gate("m3_low_current_linear"), lambda r: toy(r, flip=0.0))
    assert np.all(got == gl.NOT_APPLICABLE)


@pytest.mark.parametrize(
    "field,gid,code",
    [
        ("u_torque", "m1_torque_wrap", "unset:u_torque"),
        ("winding", "m1_linkage_wrap", "unset:winding"),
        ("j0", "m3_low_current_linear", "unset:j0"),
        ("u_magnet", "m6_magnet_bound", "unset:u_magnet"),
        ("motoring_window", "m8_motoring_sign", "unset:motoring_window"),
        ("m3_skip_cap", "m3_low_current_linear", "unset:m3_skip_cap"),
        ("gap_radius_mm", "m7_torque_bound", "unset:gap_radius_mm"),
    ],
)
def test_an_unset_fact_refuses_never_guesses(field, gid, code):
    facts = dataclasses.replace(FACTS, **{field: None})
    gate = _gate(gid, facts)
    with pytest.raises(gl.GateRefused) as err:
        _run(gate, toy)
    assert err.value.code == code


def test_remanence_scaling_refuses_while_the_version_has_no_br_input():
    with pytest.raises(gl.GateRefused) as err:
        _run(_gate("m5_remanence_scaling"), toy)
    assert err.value.code == "no_input:br"


def test_unbuilt_gates_are_listed_with_their_code():
    facts = dataclasses.replace(
        FACTS, remanence_scales=None, smooth_steps=None, m7_bound_checked=None
    )
    built, unbuilt = m.gates(facts, TOLS)
    assert unbuilt == {
        "m5_remanence_scaling": "unset:remanence_scales",
        "m7_torque_bound": "unset:m7_bound_checked",
        "m9_smooth": "unset:smooth_steps",
    }
    assert len(built) == len(m.GATE_IDS) - 3


def test_a_missing_tol_refuses_to_grade():
    built, _ = m.gates(FACTS, {})
    gate = built[0]
    rows = gl.rows(gate, np.random.default_rng(1), _draw(), BOX)
    with pytest.raises(gl.GateRefused) as err:
        gl.verdicts(gate, rows, toy(rows))
    assert err.value.code == "tol_unset"


def test_a_row_of_another_width_refuses():
    gate = _gate("m1_torque_wrap")
    rows = gl.rows(gate, np.random.default_rng(1), _draw(), BOX)
    with pytest.raises(gl.GateRefused) as err:
        gl.verdicts(gate, rows, toy(rows)[..., :240])
    assert err.value.code == "width"


def test_dropped_laws_are_not_in_the_set():
    assert not any(g.startswith(("m4", "m10")) for g in m.GATE_IDS)


def test_open_circuit_and_low_current_anchor_on_scored_designs():
    assert _gate("m2_open_circuit_torque").base == "scored"
    assert _gate("m3_low_current_linear").base == "scored"


def test_low_current_fails_every_skipped_base_above_the_cap():
    facts = dataclasses.replace(FACTS, m3_skip_cap=0.2)
    got = _run(_gate("m3_low_current_linear", facts), lambda r: toy(r, flip=0.0))
    assert np.all(got == gl.FAIL)


def test_low_current_cap_of_the_wrong_type_refuses():
    facts = dataclasses.replace(FACTS, m3_skip_cap=1)
    with pytest.raises(gl.GateRefused) as err:
        _run(_gate("m3_low_current_linear", facts), toy)
    assert err.value.code == "m3_skip_cap"


def test_remanence_base_box_keeps_every_scaled_br_inside():
    facts = dataclasses.replace(FACTS, input_names=NAMES_BR)
    narrowed = m.remanence_base_box(facts, BOX_BR)
    assert narrowed.lower[-1] == pytest.approx(1.0 / 0.9)
    assert narrowed.upper[-1] == pytest.approx(1.5 / 1.1)
    assert narrowed.lower[:-1] == BOX_BR.lower[:-1]
    base = _draw(box=narrowed)
    got = _run(
        _gate("m5_remanence_scaling", facts),
        lambda r: toy(r, NAMES_BR),
        box=BOX_BR,
        base=base,
    )
    assert np.all(got == gl.PASS)


def test_remanence_base_box_refuses_when_nothing_is_left():
    facts = dataclasses.replace(
        FACTS, input_names=NAMES_BR, remanence_scales=(0.5, 2.0)
    )
    with pytest.raises(gl.GateRefused) as err:
        m.remanence_base_box(facts, BOX_BR)
    assert err.value.code == "remanence_base_box"


def test_torque_bound_holds_at_no_current_only_for_zero_torque():
    got = _run(
        _gate("m7_torque_bound"),
        lambda r: toy(r) + np.r_[np.full(60, 50.0), np.zeros(181)],
    )
    assert np.all(got == gl.FAIL)
