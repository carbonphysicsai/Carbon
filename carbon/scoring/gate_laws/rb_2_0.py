"""RB 2.0's multi-row law set on the load map (exam-rb 8263; review-b fail-ability read 9924621c).

Each design is a geometry plus a load map. Per base (geometry with its map A) the gate asks the same geometry under a
second map B and under C = lam A + (1 - lam) B, lam drawn uniform in the posted range. Written:
- L1 tip superposition (exact): tip(C) = lam tip(A) + (1 - lam) tip(B).
- L2 triangle bounds for the outputs that are a seminorm of a linear field (exact): out(C) at most
  lam out(A) + (1 - lam) out(B), and at least lam out(A) - (1 - lam) out(B) and the same with A and B swapped.
  review-b R2: the lower bounds need a SYMMETRIC seminorm; only outputs exam-rb names as such may be listed.
- L3 load independence (exact): the map-free outputs are equal across A, B and C.
NOT written: L4 (door-code says shares or newtons), L5 (not applicable, 8263), L6 (false as written, review-b R1),
L7 (report only).

No value is set here. The input order, the map columns, the map sampler for B, the lam range, the output order, which
outputs each law reads, and every U are `RbFacts` fields, None until a row sets them; a gate reading an unset one
refuses. Tolerances come by gate id from model-eval (owner veto); a missing one refuses to grade. Rule sentences are
DRAFTS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Optional

import numpy as np

from . import GateRefused, law, need

CHALLENGE = "f08-ribbed-bracket"
VERSION = "2.0"


@dataclass(frozen=True)
class RbFacts:
    """The values the laws read; each None until an exam-seat, door-code or model-eval row sets it."""

    input_names: Optional[tuple] = None  # the version's input order
    map_columns: Optional[tuple] = None  # input names of the load map, in order
    draw_map: Optional[
        Callable
    ] = None  # (rng, n) -> (n, len(map_columns)) maps B, the registered sampler
    lam_range: Optional[tuple] = None  # (low, high), 0 < low <= high < 1
    output_names: Optional[tuple] = None  # the version's output order
    tip_outputs: Optional[tuple] = None  # L1: signed tip components
    seminorm_outputs: Optional[
        tuple
    ] = None  # L2: symmetric seminorms of a linear field
    map_free_outputs: Optional[tuple] = None  # L3
    u: Optional[Mapping] = None  # {output name: U}


def _map_index(facts, gid):
    names = tuple(need(facts.input_names, "input_names", gid))
    cols = tuple(need(facts.map_columns, "map_columns", gid))
    if not cols or any(c not in names for c in cols) or len(set(cols)) != len(cols):
        raise GateRefused("map_columns", gid)
    return np.array([names.index(c) for c in cols])


def _outputs(facts, which, gid):
    """(indices, U vector) of the outputs named by the field ``which``."""
    names = tuple(need(facts.output_names, "output_names", gid))
    chosen = tuple(need(getattr(facts, which), which, gid))
    if not chosen or any(c not in names for c in chosen):
        raise GateRefused(which, gid)
    u_of = need(facts.u, "u", gid)
    u = np.array([need(u_of.get(c), "u:" + c, gid) for c in chosen], dtype=float)
    if not np.all(np.isfinite(u) & (u > 0)):
        raise GateRefused("u", gid)
    return np.array([names.index(c) for c in chosen]), u


def _partners(facts, gid):
    def partners(rng, base, box):
        cols = _map_index(facts, gid)
        low, high = need(facts.lam_range, "lam_range", gid)
        if not (0 < low <= high < 1):
            raise GateRefused("lam_range", gid)
        maps_b = np.asarray(
            need(facts.draw_map, "draw_map", gid)(rng, base.shape[0]), dtype=float
        )
        if maps_b.shape != (base.shape[0], cols.size):
            raise GateRefused("draw_map", gid)
        lam = rng.uniform(low, high, size=(base.shape[0], 1))
        b = base.copy()
        b[:, cols] = maps_b
        c = base.copy()
        c[:, cols] = lam * base[:, cols] + (1.0 - lam) * maps_b
        return np.stack([base, b, c], axis=1)

    return partners


def _lam(facts, inputs, gid):
    """lam of each base, read back from its three maps (C - B = lam (A - B)); NaN where A equals B."""
    cols = _map_index(facts, gid)
    a, b, c = (inputs[:, k, :][:, cols] for k in range(3))
    span = ((a - b) ** 2).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(span > 0, ((c - b) * (a - b)).sum(axis=1) / span, np.nan)


def _distinct(facts, gid):
    def applicable(inputs, outputs):
        return np.isfinite(_lam(facts, inputs, gid))

    return applicable


def _tip(facts, tol):
    gid = "l1_tip_superposition"

    def residual(inputs, outputs):
        idx, u = _outputs(facts, "tip_outputs", gid)
        lam = _lam(facts, inputs, gid)[:, None]
        a, b, c = (outputs[:, k, idx] for k in range(3))
        return np.max(np.abs(c - lam * a - (1.0 - lam) * b) / u, axis=1)

    text = "Under a blend of two load maps, the tip answer is the same blend of the two tip answers."
    return law(
        gid,
        "G1",
        "fresh",
        _partners(facts, gid),
        residual,
        tol,
        text,
        3,
        _distinct(facts, gid),
    )


def _triangle(facts, tol):
    gid = "l2_seminorm_triangle"

    def residual(inputs, outputs):
        idx, u = _outputs(facts, "seminorm_outputs", gid)
        lam = _lam(facts, inputs, gid)[:, None]
        a, b, c = (outputs[:, k, idx] for k in range(3))
        la, lb = lam * a, (1.0 - lam) * b
        over = np.maximum.reduce([c - (la + lb), (la - lb) - c, (lb - la) - c])
        return np.max(np.maximum(0.0, over) / u, axis=1)

    text = "Under a blend of two load maps, each stress answer lies between the bounds the two stress answers set."
    return law(
        gid,
        "G1",
        "fresh",
        _partners(facts, gid),
        residual,
        tol,
        text,
        3,
        _distinct(facts, gid),
    )


def _independent(facts, tol):
    gid = "l3_load_independence"

    def residual(inputs, outputs):
        idx, u = _outputs(facts, "map_free_outputs", gid)
        rows = outputs[:, :, idx]
        return np.max(np.abs(rows[:, 1:, :] - rows[:, :1, :]) / u, axis=(1, 2))

    text = "The answers that do not depend on the load map stay the same when only the map changes."
    return law(gid, "G2", "fresh", _partners(facts, gid), residual, tol, text, 3)


BUILDERS = (_tip, _triangle, _independent)
GATE_IDS = ("l1_tip_superposition", "l2_seminorm_triangle", "l3_load_independence")


def gates(facts: RbFacts, tols: Mapping):
    """``(built gates, {gate id: refusal code})``; a missing tol is None and refuses to grade."""
    built, unbuilt = [], {}
    for gid, build in zip(GATE_IDS, BUILDERS):
        try:
            built.append(build(facts, tols.get(gid)))
        except GateRefused as err:
            unbuilt[gid] = err.code
    return tuple(built), unbuilt
