"""Motor 1.9's multi-row law set (exam-motor 8266, file MOTOR_19_GATE_LAWS.md sha256 f8c52d9ee881521c).

Each gate is the exam seat's formula as posted. No value is set here: every U, the small current J0, the winding
table, the motoring window, the fixed remanence, the remanence scales, the knee and the smoothness steps are fields
of `MotorFacts`, None until a row sets them, and a gate that reads an unset one refuses (`GateRefused` ``unset:...``).
Every tolerance is model-eval's (owner veto): `gates` takes them by gate id and a missing one is None, which refuses
to grade. The rule sentences are DRAFTS for miner-ux and the owner, not published words.

The answer row is the registered 1.9 layout (`carbon.motor.row19`): torque over 60 rotor steps of one slot-pitch
period, the three phase flux linkages over the same steps, then ``magnet_min_b_t``.

Written: M1 (torque wrap and linkage wrap), M2 (open-circuit zero mean torque), M3 (low-current linearity), M5
(remanence scaling; refuses while the version has no ``br`` input), M6 (magnet field bound), M8 (motoring sign), M9
(smoothness on the scored rows, the shared G3 builder). M10 (determinism) is the runner's.
NOT written, each a FINDING to exam-motor (registry-a row): M4 asks psi + 180 degrees but the version's current-angle
box is 0 to 60 degrees, so its partner is never in the box; M7's K_ub multiplies turns by J x slot area, which already
counts every turn (J x coil area = the slot's ampere-turns), and the coil area is not an input; the linkage shift of
M2 needs the winding table across two slot pitches, which one 60-step window does not hold.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Mapping, Optional

import numpy as np

from carbon.motor import row19
from carbon.motor.domain import ANGLE_STEPS

from . import GateRefused, column, copies, law, need, setting, smoothness

CHALLENGE = "electric-motor-magnetics"
VERSION = "1.9"

_TORQUE = slice(0, ANGLE_STEPS)
_LINK = {
    p: slice((i + 1) * ANGLE_STEPS, (i + 2) * ANGLE_STEPS) for i, p in enumerate("ABC")
}
_MAGNET = row19.WIDTH - 1
_J = "current_density_a_mm2"
_PSI = "current_angle_deg"
_BR = "br"


@dataclass(frozen=True)
class MotorFacts:
    """The values the laws read; each None until an exam-seat or model-eval row sets it."""

    input_names: Optional[tuple] = None  # the version's input order
    u_torque: Optional[float] = None  # U of torque, N m
    u_linkage: Optional[float] = None  # U of a phase linkage, Wb
    u_magnet: Optional[float] = None  # U of magnet_min_b_t, T
    j0: Optional[float] = None  # the small current density of M3, A/mm2
    winding: Optional[
        Mapping
    ] = None  # {phase: (phase it continues into, sign)} for one slot pitch (M1)
    motoring_window: Optional[
        tuple
    ] = None  # (low, high) current angle, degrees, read from solver rows (M8)
    br_fixed: Optional[
        float
    ] = None  # the deck's remanence when it is not an input, T (M6)
    remanence_scales: Optional[tuple] = None  # s of M5
    knee_t: Optional[
        float
    ] = None  # M5 applies only while magnet_min_b_t stays above it, T
    smooth_steps: Optional[tuple] = None  # steps of M9 ("ulp" or a box-width fraction)


def _width(outputs, gate_id):
    if outputs.shape[2] != row19.WIDTH:
        raise GateRefused("width", gate_id)
    return outputs


def _mean_torque(outputs):
    return outputs[..., _TORQUE].mean(axis=-1)


def _second_diff(curve):
    return curve[..., 2:] - 2.0 * curve[..., 1:-1] + curve[..., :-2]


def _torque_wrap(facts, tol):
    gid = "m1_torque_wrap"

    def residual(inputs, outputs):
        t = _width(outputs, gid)[:, 0, _TORQUE]
        typical = np.median(_second_diff(t), axis=-1)
        end = t[:, 0] - 2.0 * t[:, -1] + t[:, -2]
        start = t[:, 1] - 2.0 * t[:, 0] + t[:, -1]
        worst = np.maximum(np.abs(end - typical), np.abs(start - typical))
        return worst / need(facts.u_torque, "u_torque", gid)

    text = (
        "The torque curve continues smoothly across the end of its one-period window."
    )
    return law(gid, "G1", "fresh", copies(), residual, tol, text, arity=1)


def _linkage_wrap(facts, tol):
    gid = "m1_linkage_wrap"

    def residual(inputs, outputs):
        rows = _width(outputs, gid)[:, 0, :]
        table = need(facts.winding, "winding", gid)
        if set(table) != set("ABC"):
            raise GateRefused("winding", gid)
        u = need(facts.u_linkage, "u_linkage", gid)
        worst = np.zeros(rows.shape[0])
        for phase, (into, sign) in table.items():
            lam = rows[:, _LINK[phase]]
            after = float(sign) * rows[:, _LINK[into]][:, 0]
            wrap = after - 2.0 * lam[:, -1] + lam[:, -2]
            typical = np.median(_second_diff(lam), axis=-1)
            worst = np.maximum(worst, np.abs(wrap - typical) / u)
        return worst

    text = "Each phase flux linkage continues across the end of its window into the phase the winding symmetry names."
    return law(gid, "G1", "fresh", copies(), residual, tol, text, arity=1)


def _open_circuit(facts, tol):
    gid = "m2_open_circuit_torque"
    j = partial(column, facts.input_names, _J, gid)

    def residual(inputs, outputs):
        tm = _mean_torque(_width(outputs, gid)[:, 1, :])
        return np.abs(tm) / need(facts.u_torque, "u_torque", gid)

    text = "With no current, the mean torque over the period is zero."
    partners = copies(setting(j, lambda: 0.0))
    return law(gid, "G1", "fresh", partners, residual, tol, text, arity=2)


def _low_current(facts, tol):
    gid = "m3_low_current_linear"
    j = partial(column, facts.input_names, _J, gid)
    j0 = partial(need, facts.j0, "j0", gid)

    def _steps(outputs):
        tm = _mean_torque(_width(outputs, gid))
        return tm[:, 2] - tm[:, 1], tm[:, 3] - tm[:, 1]

    def residual(inputs, outputs):
        one, two = _steps(outputs)
        return np.abs(two - 2.0 * one) / need(facts.u_torque, "u_torque", gid)

    def applicable(
        inputs, outputs
    ):  # a tiny denominator is skipped and counted (8266 M3)
        one, _ = _steps(outputs)
        return np.abs(one) >= 0.1 * need(facts.u_torque, "u_torque", gid)

    text = "At small current, the mean torque above its no-current value doubles when the current doubles."
    partners = copies(
        setting(j, lambda: 0.0),
        setting(j, j0),
        setting(j, lambda: 2.0 * j0()),
    )
    return law(
        gid,
        "G1",
        "fresh",
        partners,
        residual,
        tol,
        text,
        arity=4,
        applicable=applicable,
    )


def _remanence(facts, tol):
    gid = "m5_remanence_scaling"
    j = partial(column, facts.input_names, _J, gid)
    br = partial(column, facts.input_names, _BR, gid)

    values = tuple(need(facts.remanence_scales, "remanence_scales", gid))
    if not values or any(
        type(v) is not float or not (np.isfinite(v) and v > 0 and v != 1.0)
        for v in values
    ):
        raise GateRefused("remanence_scales", gid)

    def scaled(k):
        def edit(rows):
            rows[:, j()] = 0.0
            rows[:, br()] = rows[:, br()] * values[k]
            return rows

        return edit

    partners = copies(setting(j, lambda: 0.0), *(scaled(k) for k in range(len(values))))

    def residual(inputs, outputs):
        rows = _width(outputs, gid)
        u = need(facts.u_linkage, "u_linkage", gid)
        worst = np.zeros(rows.shape[0])
        for k, s in enumerate(values):
            for part in _LINK.values():
                diff = rows[:, 2 + k, part] / s - rows[:, 1, part]
                worst = np.maximum(worst, np.max(np.abs(diff), axis=-1) / u)
        return worst

    def applicable(inputs, outputs):
        knee = need(facts.knee_t, "knee_t", gid)
        return np.all(_width(outputs, gid)[:, 1:, _MAGNET] > knee, axis=-1)

    text = "With no current and below saturation, every flux linkage scales with the magnet remanence."
    arity = 2 + len(values)
    return law(
        gid,
        "G1",
        "fresh",
        partners,
        residual,
        tol,
        text,
        arity=arity,
        applicable=applicable,
    )


def _magnet_bound(facts, tol):
    gid = "m6_magnet_bound"
    j = partial(column, facts.input_names, _J, gid)

    def residual(inputs, outputs):
        names = tuple(need(facts.input_names, "input_names", gid))
        if _BR in names:
            br = inputs[:, 1, names.index(_BR)]
        else:
            br = need(facts.br_fixed, "br_fixed", gid)
        over = _width(outputs, gid)[:, 1, _MAGNET] - br
        return np.maximum(0.0, over) / need(facts.u_magnet, "u_magnet", gid)

    text = "With no current, the minimum flux density in the magnet does not exceed its remanence."
    partners = copies(setting(j, lambda: 0.0))
    return law(gid, "G1", "fresh", partners, residual, tol, text, arity=2)


def _motoring_sign(facts, tol):
    gid = "m8_motoring_sign"

    def residual(inputs, outputs):
        tm = _mean_torque(_width(outputs, gid)[:, 0, :])
        return np.maximum(0.0, -tm) / need(facts.u_torque, "u_torque", gid)

    def applicable(inputs, outputs):
        low, high = need(facts.motoring_window, "motoring_window", gid)
        psi = inputs[:, 0, column(facts.input_names, _PSI, gid)]
        return (psi >= low) & (psi <= high)

    text = "In the motoring range of current angle, the mean torque is not negative."
    return law(
        gid,
        "G1",
        "fresh",
        copies(),
        residual,
        tol,
        text,
        arity=1,
        applicable=applicable,
    )


def _smooth(facts, tol):
    gid = "m9_smooth"
    text = "An answer does not jump when its inputs move by a tiny step."
    steps = need(facts.smooth_steps, "smooth_steps", gid)
    u = np.concatenate(
        [
            np.full(ANGLE_STEPS, need(facts.u_torque, "u_torque", gid)),
            np.full(3 * ANGLE_STEPS, need(facts.u_linkage, "u_linkage", gid)),
            [need(facts.u_magnet, "u_magnet", gid)],
        ]
    )
    return smoothness(gid, steps, u, tol, text)


#: Builders in gate order; M5 and M9 need their posted values to be built at all (`gates` lists them as unbuilt
#: with the code otherwise).
BUILDERS = (
    _torque_wrap,
    _linkage_wrap,
    _open_circuit,
    _low_current,
    _remanence,
    _magnet_bound,
    _motoring_sign,
    _smooth,
)
GATE_IDS = (
    "m1_torque_wrap",
    "m1_linkage_wrap",
    "m2_open_circuit_torque",
    "m3_low_current_linear",
    "m5_remanence_scaling",
    "m6_magnet_bound",
    "m8_motoring_sign",
    "m9_smooth",
)


def gates(facts: MotorFacts, tols: Mapping):
    """``(built gates, {gate id: refusal code})``: every law of the set, each with its tol from ``tols`` (missing =
    None = refuses to grade). A gate that cannot even be built from the facts is listed with its code, never dropped
    silently."""
    built, unbuilt = [], {}
    for gid, build in zip(GATE_IDS, BUILDERS):
        try:
            built.append(build(facts, tols.get(gid)))
        except GateRefused as err:
            unbuilt[gid] = err.code
    return tuple(built), unbuilt
