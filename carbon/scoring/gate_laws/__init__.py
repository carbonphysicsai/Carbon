"""Multi-row law gates: the relation a grade checks across SEVERAL answers of one model (Lead 8421, door-code 8269).

The gate suite (model-eval 8260) names seven families. Today every grade-path gate reads ONE answer row (G4 bounds, in
`pool_gates`). This package holds the families that relate several answers: G1 law, G2 invariance, G3 smoothness and
G6 off-box sanity. Each is a `RelationGate`: given base input rows it builds k input rows per base (`partners`), and
given the model's k answers per base it says PASS, FAIL or NOT_APPLICABLE (`check`).

Split with door-code (GATE_RUNNER_SPLIT_8421): this package is pure functions on arrays. It never calls a model, reads
no truth, no file and no custody material, and names no Challenge. The runner (`carbon/scoring/gate_runner.py`,
door-code) draws the bases per grade on custody, puts the rows into the ONE graded inference in keyed order, splits the
answers back and turns FAIL into GATE_FAILED (unranked, never a penalty). One module per exam law set
(``<exam>_<version>.py``) builds its gates from the formulas its exam seat posts; it may name its inputs.

Fail closed, by construction:
- ``tol`` None means no value has been set (model-eval sets it, owner veto): `verdicts` refuses to grade
  (`GateRefused`, code ``tol_unset``). No default tolerance exists here.
- A non-finite answer in any of a base's k rows is FAIL, never NOT_APPLICABLE.
- Row 0 of every base's partner rows is the base itself, byte-equal; a ``fresh`` or ``scored`` gate keeps every row
  inside the box. A partner or check of the wrong shape refuses the gate, it never grades a candidate.
- G3 (smoothness) ties the SCORED rows (door-code 8269 section 2: a model that keeps a table of the scored designs and
  answers honestly elsewhere passes every law on fresh designs alone).

numpy only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

PASS = 1
FAIL = 0
NOT_APPLICABLE = -1

#: The multi-row families of the gate suite (model-eval 8260). G4, G5 and G7 live elsewhere (one row, truths, repeat).
FAMILIES = ("G1", "G2", "G3", "G6")
#: Where a gate's base rows come from: a fresh in-box draw, the scored designs themselves, or an off-box draw.
BASES = ("fresh", "scored", "offbox")
#: Families whose bases must be the scored rows (door-code 8269 section 2).
SCORED_ONLY = frozenset({"G3"})

_GATE_ID = re.compile(r"[a-z][a-z0-9_]{0,63}")


class GateRefused(ValueError):
    """The gate cannot grade (no tolerance, or a partner or check of the wrong shape): a Carbon failure, not the
    candidate's."""

    def __init__(self, code, gate_id=None):
        self.code = code
        self.gate_id = gate_id
        super().__init__(code if gate_id is None else f"{gate_id}: {code}")


@dataclass(frozen=True)
class Box:
    """The public input box, in the version's input order: ``lower[i] < upper[i]``, every bound finite."""

    lower: tuple
    upper: tuple

    def __post_init__(self):
        lo, hi = np.asarray(self.lower, dtype=float), np.asarray(
            self.upper, dtype=float
        )
        if lo.ndim != 1 or lo.shape != hi.shape or lo.size == 0:
            raise GateRefused("box_shape")
        if not (
            np.all(np.isfinite(lo)) and np.all(np.isfinite(hi)) and np.all(lo < hi)
        ):
            raise GateRefused("box_bounds")
        object.__setattr__(self, "lower", tuple(float(v) for v in lo))
        object.__setattr__(self, "upper", tuple(float(v) for v in hi))

    @property
    def lo(self):
        return np.asarray(self.lower, dtype=float)

    @property
    def hi(self):
        return np.asarray(self.upper, dtype=float)

    @property
    def width(self):
        return self.hi - self.lo

    def contains(self, rows):
        """Per row of ``rows`` (..., d): every input inside the closed box."""
        rows = np.asarray(rows, dtype=float)
        return np.all((rows >= self.lo) & (rows <= self.hi), axis=-1)


@dataclass(frozen=True)
class RelationGate:
    """One multi-row law, exam-agnostic in shape (GATE_RUNNER_SPLIT_8421)."""

    gate_id: str  # stable, lower snake case, published
    family: str  # one of FAMILIES
    arity: int  # rows per relation (k), row 0 = the base
    base: str  # one of BASES
    partners: Callable  # (rng, base_inputs (n, d), box) -> (n, k, d)
    check: Callable  # (inputs (n, k, d), outputs (n, k, m), tol) -> int (n,) of PASS / FAIL / NOT_APPLICABLE
    margin: Callable  # (inputs, outputs, tol) -> float (n,) in tol units (1.0 = at the bar), custody record only
    tol: Optional[float]  # None = refuse to grade
    rule_text: str  # the one published sentence: no design, no value, no margin

    def __post_init__(self):
        if type(self.gate_id) is not str or not _GATE_ID.fullmatch(self.gate_id):
            raise GateRefused("gate_id", None)
        gid = self.gate_id
        if self.family not in FAMILIES:
            raise GateRefused("family", gid)
        if type(self.arity) is not int or self.arity < 1:
            raise GateRefused("arity", gid)
        if self.base not in BASES:
            raise GateRefused("base", gid)
        if self.family in SCORED_ONLY and self.base != "scored":
            raise GateRefused("base_must_be_scored", gid)
        if not (
            callable(self.partners) and callable(self.check) and callable(self.margin)
        ):
            raise GateRefused("callables", gid)
        if self.tol is not None:
            if (
                type(self.tol) not in (int, float)
                or not np.isfinite(self.tol)
                or self.tol <= 0
            ):
                raise GateRefused("tol", gid)
        text = self.rule_text
        if (
            type(text) is not str
            or not text.strip()
            or "\n" in text
            or "\r" in text
            or not text.isascii()
        ):
            raise GateRefused("rule_text", gid)


def rows(gate, rng, base_inputs, box):
    """The gate's input rows for ``base_inputs`` (n, d): (n, k, d), checked before any model sees them."""
    base = np.asarray(base_inputs, dtype=float)
    if base.ndim != 2 or base.shape[1] != len(box.lower):
        raise GateRefused("base_shape", gate.gate_id)
    if gate.base != "offbox" and not np.all(box.contains(base)):
        raise GateRefused("base_off_box", gate.gate_id)
    out = np.asarray(gate.partners(rng, base.copy(), box), dtype=float)
    if out.shape != (base.shape[0], gate.arity, base.shape[1]):
        raise GateRefused("partners_shape", gate.gate_id)
    if not np.all(np.isfinite(out)):
        raise GateRefused("partners_nonfinite", gate.gate_id)
    if not np.array_equal(out[:, 0, :], base):
        raise GateRefused("partners_row0", gate.gate_id)
    if gate.base != "offbox" and not np.all(box.contains(out)):
        raise GateRefused("partners_off_box", gate.gate_id)
    return out


def _answers(gate, inputs, outputs):
    inputs = np.asarray(inputs, dtype=float)
    outputs = np.asarray(outputs, dtype=float)
    if inputs.ndim != 3 or inputs.shape[1] != gate.arity:
        raise GateRefused("inputs_shape", gate.gate_id)
    if (
        outputs.ndim != 3
        or outputs.shape[:2] != inputs.shape[:2]
        or outputs.shape[2] == 0
    ):
        raise GateRefused("outputs_shape", gate.gate_id)
    return inputs, outputs


def verdicts(gate, inputs, outputs):
    """PASS / FAIL / NOT_APPLICABLE per base (int8 (n,)); a non-finite answer in a base's rows is FAIL."""
    if gate.tol is None:
        raise GateRefused("tol_unset", gate.gate_id)
    inputs, outputs = _answers(gate, inputs, outputs)
    finite = np.all(np.isfinite(outputs), axis=(1, 2))
    safe = np.where(np.isfinite(outputs), outputs, 0.0)
    got = np.asarray(gate.check(inputs, safe, float(gate.tol)))
    if got.shape != (inputs.shape[0],) or not np.all(
        np.isin(got, (PASS, FAIL, NOT_APPLICABLE))
    ):
        raise GateRefused("check_shape", gate.gate_id)
    return np.where(finite, got, FAIL).astype(np.int8)


def margins(gate, inputs, outputs):
    """Per base, the worst distance to the bar in tol units (custody record only); a non-finite answer is inf."""
    if gate.tol is None:
        raise GateRefused("tol_unset", gate.gate_id)
    inputs, outputs = _answers(gate, inputs, outputs)
    finite = np.all(np.isfinite(outputs), axis=(1, 2))
    safe = np.where(np.isfinite(outputs), outputs, 0.0)
    got = np.asarray(gate.margin(inputs, safe, float(gate.tol)), dtype=float)
    if got.shape != (inputs.shape[0],):
        raise GateRefused("margin_shape", gate.gate_id)
    return np.where(finite & ~np.isnan(got), got, np.inf)


def smoothness(gate_id, steps, u, tol, rule_text):
    """A G3 gate on the scored rows: each base x is answered again at x moved by each step along one random sign
    direction (a step of ``"ulp"`` is one float64 spacing on every input; a number in (0, 0.5] is that fraction of each
    input's box width, so one of the two ways along an input always stays in the box); PASS when every output moves
    at most ``tol`` in its U (``u``, per output) for every step.

    Shape only: the steps, U and tol come from the exam seat and model-eval by row, never from here.
    """
    steps = tuple(steps)
    if not steps or any(
        not (s == "ulp" or (type(s) is float and np.isfinite(s) and 0 < s <= 0.5))
        for s in steps
    ):
        raise GateRefused("steps", gate_id)
    u = np.asarray(u, dtype=float)
    if u.ndim != 1 or u.size == 0 or not np.all(np.isfinite(u)) or not np.all(u > 0):
        raise GateRefused("u", gate_id)

    def partners(rng, base, box):
        n, d = base.shape
        sign = np.where(rng.random((n, d)) < 0.5, -1.0, 1.0)
        out = [base]
        for step in steps:
            for flip in (
                1.0,
                -1.0,
            ):  # the move that leaves the box is taken the other way
                if step == "ulp":
                    target = np.where(sign * flip > 0, np.inf, -np.inf)
                    moved = np.nextafter(base, target)
                else:
                    moved = base + sign * flip * step * box.width
                inside = (moved >= box.lo) & (moved <= box.hi)
                if flip > 0:
                    first = np.where(inside, moved, np.nan)
                else:
                    first = np.where(np.isnan(first), moved, first)
            out.append(first)
        return np.stack(out, axis=1)

    def _ratio(inputs, outputs):
        if outputs.shape[2] != u.size:
            raise GateRefused("u_width", gate_id)
        return np.max(np.abs(outputs[:, 1:, :] - outputs[:, :1, :]) / u, axis=(1, 2))

    def check(inputs, outputs, tol_value):
        return np.where(_ratio(inputs, outputs) <= tol_value, PASS, FAIL)

    def margin(inputs, outputs, tol_value):
        return _ratio(inputs, outputs) / tol_value

    return RelationGate(
        gate_id=gate_id,
        family="G3",
        arity=1 + len(steps),
        base="scored",
        partners=partners,
        check=check,
        margin=margin,
        tol=tol,
        rule_text=rule_text,
    )


def need(value, name, gate_id):
    """``value``, or `GateRefused` ``unset:<name>`` when no row has set it (None): a fact is never guessed."""
    if value is None:
        raise GateRefused("unset:" + name, gate_id)
    return value


def column(input_names, name, gate_id):
    """The index of input ``name`` in the version's input order, or `GateRefused` ``no_input:<name>``."""
    names = tuple(need(input_names, "input_names", gate_id))
    if name not in names:
        raise GateRefused("no_input:" + name, gate_id)
    return names.index(name)


def copies(*edits):
    """Partners: the base, then one edited copy per edit (each ``edit(base copy) -> rows``), in order."""

    def partners(rng, base, box):
        return np.stack([base] + [edit(base.copy()) for edit in edits], axis=1)

    return partners


def setting(index_of, value_of):
    """An edit that sets one input: ``index_of()`` and ``value_of()`` are read when the rows are built, so an unset
    fact refuses there."""

    def edit(rows):
        rows[:, index_of()] = value_of()
        return rows

    return edit


def law(
    gate_id, family, base, partners, residual, tol, rule_text, arity, applicable=None
):
    """A gate from a residual in tol units: PASS when ``residual(inputs, outputs) <= tol`` per base, NOT_APPLICABLE
    where ``applicable(inputs, outputs)`` is False (default: everywhere applicable). The margin is residual / tol, and
    0 where not applicable."""

    def _applies(inputs, outputs):
        if applicable is None:
            return np.ones(inputs.shape[0], dtype=bool)
        return np.asarray(applicable(inputs, outputs), dtype=bool)

    def check(inputs, outputs, tol_value):
        res = np.asarray(residual(inputs, outputs), dtype=float)
        verdict = np.where(res <= tol_value, PASS, FAIL)
        return np.where(_applies(inputs, outputs), verdict, NOT_APPLICABLE)

    def margin(inputs, outputs, tol_value):
        res = np.asarray(residual(inputs, outputs), dtype=float)
        return np.where(_applies(inputs, outputs), res / tol_value, 0.0)

    return RelationGate(
        gate_id=gate_id,
        family=family,
        arity=arity,
        base=base,
        partners=partners,
        check=check,
        margin=margin,
        tol=tol,
        rule_text=rule_text,
    )
