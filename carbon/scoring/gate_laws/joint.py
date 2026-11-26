"""The joint chip-thermal exam's multi-row law set (exam-joint, JOINT_GATE_LAWS.md sha256 dc91155d; review-b 9924621c).

Its challenge id and version are not registered yet (exam-joint handoff: joint-chip-thermal proposed, not confirmed),
so `CHALLENGE` and `VERSION` are None and the module is named for the exam, not a version.

Written, each the exam seat's law as posted:
- A5 permutation (G2): the spots listed in reverse order give the same temperatures.
- A7 mirror (G2, die form): every spot mirrored in x gives the same temperatures. review-b J5: only temperatures are
  compared (a hotspot argmax can flip sides on ties); the mirror pairs are a fact, so the coupled form (mirror in y)
  is another fact set, not another gate.
- B1 power (G1): every spot power times the posted scale never lowers a temperature by more than tol U.
- B2 cooling (G1): h times the posted scale, and the coolant lowered by the posted step, never raise a temperature by
  more than tol U.
NOT written: A1, A3, A4 read one answer (G4 bounds: the per-answer gates of `pool_gates`, door-code's wrap); A2 needs
the NOT_REACHED encoding of the time outputs; A6 needs how an unused spot slot is encoded; B3 and C3 need the coupled
outputs, not registered; C1 and C2 are report only.

No value is set here: the input order, the spot columns, the mirror pairs, h, coolant, every scale and step, the
output order, the temperature outputs and every U are `JointFacts` fields, None until a row sets them; a gate reading
an unset one refuses. Tolerances by gate id from model-eval (owner veto); a missing one refuses. Rule sentences are
DRAFTS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

import numpy as np

from . import GateRefused, law, need

CHALLENGE = None
VERSION = None


@dataclass(frozen=True)
class JointFacts:
    """The values the laws read; each None until an exam-seat or model-eval row sets it."""

    input_names: Optional[tuple] = None
    spot_blocks: Optional[
        tuple
    ] = None  # one tuple of input names per spot, the same field order in every spot
    spot_power: Optional[tuple] = None  # the input names of every spot power
    mirror_pairs: Optional[
        tuple
    ] = None  # ((a, b), ...): mirrored, new a = -old b and new b = -old a; (c, c) = centre
    h_name: Optional[str] = None
    coolant_name: Optional[str] = None
    power_scale: Optional[float] = None  # B1, above 1
    h_scale: Optional[float] = None  # B2, above 1
    coolant_drop: Optional[float] = None  # B2, K, above 0
    output_names: Optional[tuple] = None
    temperature_outputs: Optional[tuple] = None
    u: Optional[Mapping] = None  # {output name: U}


def _index(names, wanted, field, gid):
    if any(w not in names for w in wanted):
        raise GateRefused(field, gid)
    return [names.index(w) for w in wanted]


def _inputs(facts, gid):
    return tuple(need(facts.input_names, "input_names", gid))


def _temps(facts, gid):
    names = tuple(need(facts.output_names, "output_names", gid))
    chosen = tuple(need(facts.temperature_outputs, "temperature_outputs", gid))
    if not chosen:
        raise GateRefused("temperature_outputs", gid)
    idx = _index(names, chosen, "temperature_outputs", gid)
    u_of = need(facts.u, "u", gid)
    u = np.array([need(u_of.get(c), "u:" + c, gid) for c in chosen], dtype=float)
    if not np.all(np.isfinite(u) & (u > 0)):
        raise GateRefused("u", gid)
    return np.array(idx), u


def _above(value, low, field, gid):
    if type(value) not in (int, float) or not np.isfinite(value) or value <= low:
        raise GateRefused(field, gid)
    return float(value)


def _equal_temps(facts, gid):
    def residual(inputs, outputs):
        idx, u = _temps(facts, gid)
        rows = outputs[:, :, idx]
        return np.max(np.abs(rows[:, 1:, :] - rows[:, :1, :]) / u, axis=(1, 2))

    return residual


def _one_way(facts, gid, sign):
    """Worst move of a temperature the wrong way in U: ``sign`` +1 = must not fall, -1 = must not rise."""

    def residual(inputs, outputs):
        idx, u = _temps(facts, gid)
        rows = outputs[:, :, idx]
        wrong = -sign * (rows[:, 1:, :] - rows[:, :1, :])
        return np.max(np.maximum(0.0, wrong) / u, axis=(1, 2))

    return residual


def _permutation(facts, tol):
    gid = "a5_spot_permutation"

    def partners(rng, base, box):
        names = _inputs(facts, gid)
        blocks = [
            _index(names, block, "spot_blocks", gid)
            for block in need(facts.spot_blocks, "spot_blocks", gid)
        ]
        if len(blocks) < 2 or len({len(b) for b in blocks}) != 1:
            raise GateRefused("spot_blocks", gid)
        moved = base.copy()
        for to, frm in zip(blocks, reversed(blocks)):
            moved[:, to] = base[:, frm]
        return np.stack([base, moved], axis=1)

    text = "Listing the same heat spots in another order gives the same temperatures."
    return law(gid, "G2", "fresh", partners, _equal_temps(facts, gid), tol, text, 2)


def _mirror(facts, tol):
    gid = "a7_mirror"

    def partners(rng, base, box):
        names = _inputs(facts, gid)
        pairs = tuple(need(facts.mirror_pairs, "mirror_pairs", gid))
        if not pairs:
            raise GateRefused("mirror_pairs", gid)
        moved = base.copy()
        for a, b in pairs:
            ia, ib = _index(names, (a, b), "mirror_pairs", gid)
            moved[:, ia], moved[:, ib] = -base[:, ib], -base[:, ia]
        return np.stack([base, moved], axis=1)

    text = "Mirroring every heat spot across the die centre line gives the same temperatures."
    return law(gid, "G2", "fresh", partners, _equal_temps(facts, gid), tol, text, 2)


def _power(facts, tol):
    gid = "b1_power_monotone"

    def partners(rng, base, box):
        names = _inputs(facts, gid)
        cols = _index(
            names, need(facts.spot_power, "spot_power", gid), "spot_power", gid
        )
        scale = _above(
            need(facts.power_scale, "power_scale", gid), 1.0, "power_scale", gid
        )
        more = base.copy()
        more[:, cols] = base[:, cols] * scale
        return np.stack([base, more], axis=1)

    text = "More heat from the spots never makes a temperature fall."
    return law(gid, "G1", "fresh", partners, _one_way(facts, gid, +1), tol, text, 2)


def _cooling(facts, tol):
    gid = "b2_cooling_monotone"

    def partners(rng, base, box):
        names = _inputs(facts, gid)
        (ih,) = _index(names, (need(facts.h_name, "h_name", gid),), "h_name", gid)
        (ic,) = _index(
            names, (need(facts.coolant_name, "coolant_name", gid),), "coolant_name", gid
        )
        scale = _above(need(facts.h_scale, "h_scale", gid), 1.0, "h_scale", gid)
        drop = _above(
            need(facts.coolant_drop, "coolant_drop", gid), 0.0, "coolant_drop", gid
        )
        stronger, colder = base.copy(), base.copy()
        stronger[:, ih] = base[:, ih] * scale
        colder[:, ic] = base[:, ic] - drop
        return np.stack([base, stronger, colder], axis=1)

    text = "Stronger cooling or colder coolant never makes a temperature rise."
    return law(gid, "G1", "fresh", partners, _one_way(facts, gid, -1), tol, text, 3)


BUILDERS = (_permutation, _mirror, _power, _cooling)
GATE_IDS = (
    "a5_spot_permutation",
    "a7_mirror",
    "b1_power_monotone",
    "b2_cooling_monotone",
)


def gates(facts: JointFacts, tols: Mapping):
    """``(built gates, {gate id: refusal code})``; a missing tol is None and refuses to grade."""
    built, unbuilt = [], {}
    for gid, build in zip(GATE_IDS, BUILDERS):
        try:
            built.append(build(facts, tols.get(gid)))
        except GateRefused as err:
            unbuilt[gid] = err.code
    return tuple(built), unbuilt
