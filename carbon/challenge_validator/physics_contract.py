"""A Challenge's physics contract and its law checker (PHYSICS-CONTRACT-01).

The owner (2026-10-12): "we are trying to get these models to learn the real
physics". A physics contract is plain data in the Challenge's packet: the laws
a model's outputs must obey, each from a closed set of **registered law
types** (no per-Challenge code is executed), the outputs that make them
checkable, the probe region, and how each law's tolerance is calibrated.

Laws are **hard gates** (admissibility before ranking; invariant 7.3), never
score terms (the Test Lead's decision, 2026-10-12): the score stays decision
value. DEVELOPMENT only: nothing here is live, and adoption of any law,
tolerance or margin is the owner's.

**The checker** reads a model only through its predictions:
- `check_cases`: single-point laws on stored predictions (bound,
  initial_equals_input, initial_near_aux, ordered, floor_input);
- `check_probes`: pair laws (monotone, monotone_curve, smoothness) on random
  probe pairs drawn in the contract's region, scored through a `predict`
  callable, so no solver runs for a probe.
Each law gives a **residual** per point: 0 when the law holds, otherwise the
size of the violation. A law's tolerance is the verified reference's own
residual quantile plus a registered margin (`tolerance`); a residual above it
is a violation. A probe outside the declared validity is UNRESOLVED and
excluded.

Standard library only: the challenge-validator package is a miner-reachable,
variant-invariant surface.
"""

from __future__ import annotations

import itertools
import json
import math
import random
from pathlib import Path

SCHEMA = "carbon.physics-contract.v1"
SINGLE = frozenset(
    {"bound", "initial_equals_input", "initial_near_aux", "ordered", "floor_input"}
)
PAIR = frozenset({"monotone", "monotone_curve", "smoothness"})
LAW_TYPES = SINGLE | PAIR
SUMMARIES = frozenset({"max", "min", "first", "last", "value"})
HUMAN_INPUT = "HUMAN_INPUT"


class ContractRefused(ValueError):
    """A malformed contract; the code names the part at fault."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def load(path):
    """The contract at `path`, validated by shape."""
    contract = json.loads(Path(path).read_text())
    return validate(contract)


def validate(contract):
    if type(contract) is not dict or contract.get("schema") != SCHEMA:
        raise ContractRefused("physics_contract_schema")
    region = contract.get("probe_region")
    if type(region) is not dict or not region:
        raise ContractRefused("physics_contract_region")
    for name, bounds in region.items():
        if (
            type(bounds) is not list
            or len(bounds) != 2
            or not all(_number(b) for b in bounds)
            or not bounds[0] < bounds[1]
        ):
            raise ContractRefused("physics_contract_region:" + name)
    laws = contract.get("laws")
    if type(laws) is not list or not laws:
        raise ContractRefused("physics_contract_laws")
    seen = set()
    for law in laws:
        if type(law) is not dict or law.get("type") not in LAW_TYPES:
            raise ContractRefused("physics_contract_law_type")
        if law.get("id") in seen or type(law.get("id")) is not str:
            raise ContractRefused("physics_contract_law_id")
        seen.add(law["id"])
        if law["type"] in ("monotone", "monotone_curve") and (
            law.get("input") not in region
        ):
            raise ContractRefused("physics_contract_law_input:" + law["id"])
        if law.get("summary", "value") not in SUMMARIES:
            raise ContractRefused("physics_contract_law_summary:" + law["id"])
        if law.get("direction", "increasing") not in ("increasing", "decreasing"):
            raise ContractRefused("physics_contract_law_direction:" + law["id"])
    return contract


def _number(x):
    return type(x) in (int, float) and math.isfinite(x)


def _summary(value, how):
    if how == "value":
        return float(value)
    seq = [float(v) for v in value]
    return {
        "max": max(seq),
        "min": min(seq),
        "first": seq[0],
        "last": seq[-1],
    }[how]


# --- single-point laws ------------------------------------------------------------------


def single_residual(law, inputs, outputs, aux=None):
    """The law's residual at one point (0 holds), or None when the needed
    output is absent or non-finite (UNRESOLVED)."""
    try:
        value = outputs[law["output"]]
        kind = law["type"]
        if kind == "bound":
            seq = value if isinstance(value, list) else [value]
            seq = [float(v) for v in seq]
            low, high = law["low"], law["high"]
            return max(0.0, low - min(seq), max(seq) - high)
        if kind == "initial_equals_input":
            return abs(float(value[0]) - float(inputs[law["input"]]))
        if kind == "initial_near_aux":
            target = aux[law["aux"]](float(inputs[law["input"]]))
            return abs(float(value[0]) - float(target))
        if kind == "ordered":
            seq = [float(v) for v in value]
            step = (
                (lambda a, b: b - a)
                if law.get("direction", "decreasing") == "decreasing"
                else (lambda a, b: a - b)
            )
            return max([0.0] + [step(a, b) for a, b in itertools.pairwise(seq)])
        if kind == "floor_input":
            low = float(inputs[law["input"]]) - float(law.get("offset", 0.0))
            return max(0.0, low - min(float(v) for v in value))
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    raise ContractRefused("physics_contract_law_not_single:" + law["id"])


def check_cases(contract, cases, aux=None):
    """`{law_id: [residual per case]}` for the single-point laws over `cases`,
    an iterable of `(inputs, outputs)`; an UNRESOLVED point is omitted."""
    laws = [law for law in contract["laws"] if law["type"] in SINGLE]
    found = {law["id"]: [] for law in laws}
    for inputs, outputs in cases:
        for law in laws:
            r = single_residual(law, inputs, outputs, aux)
            if r is not None and math.isfinite(r):
                found[law["id"]].append(r)
    return found


# --- pair laws on probes ----------------------------------------------------------------


def probe_pairs(contract, law, *, seed, count):
    """`count` probe pairs for a pair law: a uniform point in the region and
    its partner moved by the law's step (along its input, or a random input
    for smoothness), kept inside the region. Deterministic in `seed`."""
    region = contract["probe_region"]
    rng = random.Random(f"{seed}:{law['id']}")
    names = sorted(region)
    pairs = []
    while len(pairs) < count:
        base = {k: rng.uniform(*region[k]) for k in names}
        along = law["input"] if law["type"] != "smoothness" else rng.choice(names)
        low, high = region[along]
        step = float(law["step"]) * (high - low)
        if base[along] + step > high:
            base[along] = rng.uniform(low, high - step)
        partner = {**base, along: base[along] + step}
        pairs.append((along, base, partner, step))
    return pairs


def pair_residual(law, base_out, partner_out, along, step, scale=None):
    """The residual of a pair law: how far the partner (the input moved up
    by `step`) breaks the declared direction, or, for smoothness, the
    largest output change per unit input step (scaled by `scale[output]`)."""
    try:
        if law["type"] == "monotone":
            a = _summary(base_out[law["output"]], law.get("summary", "value"))
            b = _summary(partner_out[law["output"]], law.get("summary", "value"))
            change = b - a
            return max(0.0, -change if law.get("direction") == "increasing" else change)
        if law["type"] == "monotone_curve":
            a = [float(v) for v in base_out[law["output"]]]
            b = [float(v) for v in partner_out[law["output"]]]
            gaps = [(y - x) for x, y in zip(a, b)]
            if law.get("direction") == "increasing":
                return max([0.0] + [-g for g in gaps])
            return max([0.0] + gaps)
        if law["type"] == "smoothness":
            worst = 0.0
            for name in law["outputs"]:
                a, b = base_out[name], partner_out[name]
                a = a if isinstance(a, list) else [a]
                b = b if isinstance(b, list) else [b]
                change = max(abs(float(y) - float(x)) for x, y in zip(a, b))
                unit = (scale or {}).get(name, 1.0) or 1.0
                worst = max(worst, change / unit / step)
            return worst
    except (KeyError, TypeError, ValueError):
        return None
    raise ContractRefused("physics_contract_law_not_pair:" + law["id"])


def check_probes(contract, predict, *, seed, count, scale=None):
    """`{law_id: [residual per probe pair]}` for the pair laws: probe pairs
    drawn per law, predicted through `predict(list_of_input_dicts) ->
    list_of_output_dicts` (one call), no solver."""
    laws = [law for law in contract["laws"] if law["type"] in PAIR]
    drawn = {
        law["id"]: probe_pairs(contract, law, seed=seed, count=count) for law in laws
    }
    points = [p for pairs in drawn.values() for _a, b, q, _s in pairs for p in (b, q)]
    outputs = predict(points) if points else []
    found, i = {}, 0
    for law in laws:
        found[law["id"]] = []
        for along, _b, _q, step in drawn[law["id"]]:
            r = pair_residual(law, outputs[i], outputs[i + 1], along, step, scale)
            i += 2
            if r is not None and math.isfinite(r):
                found[law["id"]].append(r)
    return found


# --- tolerances and verdicts ----------------------------------------------------------


def quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    position = q * (len(values) - 1)
    low, high = math.floor(position), math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def tolerance(reference_residuals, *, q, margin):
    """The law's tolerance: the verified reference's residual quantile `q`
    plus a registered `margin`. Either HUMAN_INPUT (or no reference
    residuals) leaves the tolerance unset (None): the gate is not ready."""
    if q == HUMAN_INPUT or margin == HUMAN_INPUT or q is None or margin is None:
        return None
    base = quantile(reference_residuals, q)
    return None if base is None else base + margin


def violation_rate(residuals, tol):
    """The share of checked points whose residual exceeds `tol`."""
    if tol is None or not residuals:
        return None
    return sum(r > tol for r in residuals) / len(residuals)


__all__ = [
    "HUMAN_INPUT",
    "LAW_TYPES",
    "PAIR",
    "SCHEMA",
    "SINGLE",
    "ContractRefused",
    "check_cases",
    "check_probes",
    "load",
    "pair_residual",
    "probe_pairs",
    "quantile",
    "single_residual",
    "tolerance",
    "validate",
    "violation_rate",
]
