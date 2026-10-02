"""The motor DEVELOPMENT exam: case typing, gates, score and aggregate.

In the shape of `carbon.cold_plate.exam`, kept apart the same way:

- **A case is typed first.** `REFERENCE_INVALID` and
  `REFERENCE_SOLVER_FAILED` are withdrawn for every model; `FAILED_INFRA` is
  not scored, is retryable, and is never a scientific failure. Otherwise the
  gates decide `GATE_FAILED` or `SCORABLE`.
- **Gates are laws a prediction must not break.** Each holds for every sound
  reference, and `calibrate` checks that it does before any model is judged.
  One failed gate makes the submission ineligible; no score compensates it.
- **The score is soft:** the mean of two TRAIN-normalized errors, the
  period-mean torque and the ripple's shape (the curve less its mean), lower
  is better. The two are separate because they are separate engineering
  quantities, and because a model that predicts a flat curve (the textbook
  one) must be charged for the ripple it omits. Bound to this Challenge
  version, not comparable across Challenges.
- **Feasibility is not a gate.** Whether a machine makes a torque with a
  bounded ripple is a decision about designs (`feasibility`), reported beside
  the score.

Every number here is a provisional DEVELOPMENT value under
OWNER-CHALLENGE-DESIGN-01, with its basis beside it. None is scientifically
qualified.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean, pstdev

from .domain import ANGLE_STEPS

SCORABLE, GATE_FAILED, REFERENCE_INVALID, FAILED_INFRA = (
    "SCORABLE",
    "GATE_FAILED",
    "REFERENCE_INVALID",
    "FAILED_INFRA",
)
PASS, FAIL, NOT_APPLICABLE = "PASS", "FAIL", "NOT_APPLICABLE"
F32_EPS = 2.0**-23
ULP_FACTOR = 32  # float32 round-off allowance, as battery's and the cold plate's
#: The motoring gate's allowance: the reference's own periodicity check
#: (`scripts/dev/motor/reference/run_batch.py` REFERENCE_CHECKS), a fraction
#: of the curve's largest |torque| with an absolute floor.
MEAN_ALLOWANCE_REL, MEAN_ALLOWANCE_FLOOR_NM = 1e-3, 1e-3
#: The important region: cases at a peak current density of at least this.
#: Provisional DEVELOPMENT value: the top third of the current range, where
#: saturation acts (rung M2: 10 % of the torque at 10.9 A on the benchmark
#: machine) and an optimistic torque costs most.
J_IMPORTANT = 10.0
COMPONENTS = ("mean", "ripple")


@dataclass(frozen=True)
class Gate:
    gate_id: str
    formula: str
    basis: str


GATES = (
    Gate(
        "schema_finite",
        "torque_nm present, 60 values, finite",
        "the prediction contract",
    ),
    Gate(
        "motoring_mean_nonnegative",
        "mean(torque_nm) >= -(1e-3 max|torque_nm| + 1e-3 N m)",
        "the current is in the motoring quadrant (current angle 0 to 60 deg, "
        "so the q-axis current is at least half the amplitude) and the "
        "magnets are surface-mounted, so the period-mean torque is not "
        "negative; the allowance is the reference's own periodicity check",
    ),
    Gate(
        "paired_repeat",
        "a hidden duplicate's prediction equals the original's within 32 float32 ulp",
        "a rebuilt model is a function of its inputs",
    ),
)


def _ulp(value):
    return ULP_FACTOR * F32_EPS * max(1.0, abs(value))


def _number(value):
    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _curve(prediction):
    try:
        value = prediction["torque_nm"]
    except (KeyError, TypeError):
        return None
    if (
        type(value) not in (list, tuple)
        or len(value) != ANGLE_STEPS
        or not all(_number(v) for v in value)
    ):
        return None
    return [float(v) for v in value]


def gates(prediction, twin=None):
    """Every gate's verdict for one prediction."""
    curve = _curve(prediction)
    g = {"schema_finite": PASS if curve is not None else FAIL}
    if curve is None:
        return g
    allowance = (
        MEAN_ALLOWANCE_REL * max(abs(t) for t in curve) + MEAN_ALLOWANCE_FLOOR_NM
    )
    g["motoring_mean_nonnegative"] = PASS if fmean(curve) >= -allowance else FAIL
    if twin is None:
        g["paired_repeat"] = NOT_APPLICABLE
    else:
        other = _curve(twin)
        same = other is not None and all(
            abs(a - b) <= _ulp(a) for a, b in zip(curve, other)
        )
        g["paired_repeat"] = PASS if same else FAIL
    return g


def evaluate_case(prediction, reference, twin=None, infra_failed=False):
    """Type one case for one model and run every applicable gate."""
    if reference.get("status") != "OK":
        return {"state": REFERENCE_INVALID, "gates": {}}
    if infra_failed or prediction is None:
        return {"state": FAILED_INFRA, "gates": {}}
    g = gates(prediction, twin)
    return {"state": GATE_FAILED if FAIL in g.values() else SCORABLE, "gates": g}


def calibrate(references):
    """Check every gate on every OK reference; refuse rather than widen.
    Returns the motoring gate's smallest margin as evidence."""
    margin, count = math.inf, 0
    for ref in references:
        if ref.get("status") != "OK":
            continue
        count += 1
        failed = [k for k, v in gates(ref["outputs"]).items() if v == FAIL]
        if failed:
            raise ValueError(f"reference {ref.get('case_id')} fails gates {failed}")
        margin = min(margin, fmean(ref["outputs"]["torque_nm"]))
    if count == 0:
        raise ValueError("no OK reference: nothing to calibrate on")
    return {"n_references": count, "smallest_mean_torque_nm": margin}


def _split(curve):
    mean = fmean(curve)
    return mean, [t - mean for t in curve]


def scales_from_train(train):
    """TRAIN spread of the period-mean torque and of the ripple values."""
    ok = [r for r in train if r.get("status") == "OK"]
    if len(ok) < 2:
        raise ValueError("at least two OK TRAIN references are needed")
    means, ripple = [], []
    for r in ok:
        mean, rest = _split(r["outputs"]["torque_nm"])
        means.append(mean)
        ripple.extend(rest)
    return {"s_mean": pstdev(means), "s_ripple": pstdev(ripple), "n_train": len(ok)}


def case_components(prediction, reference, scales):
    p_mean, p_rest = _split([float(t) for t in prediction["torque_nm"]])
    r_mean, r_rest = _split(reference["outputs"]["torque_nm"])
    rms = math.sqrt(fmean((a - b) ** 2 for a, b in zip(p_rest, r_rest)))
    return {
        "mean": abs(p_mean - r_mean) / scales["s_mean"],
        "ripple": rms / scales["s_ripple"],
    }


def important(reference):
    return reference["inputs"]["current_density_a_mm2"] >= J_IMPORTANT


def score_case(prediction, reference, scales, twin=None, infra_failed=False):
    """A typed, gated and (when scorable) scored row for one case."""
    row = evaluate_case(prediction, reference, twin, infra_failed)
    row["case_id"] = reference.get("case_id")
    if row["state"] == SCORABLE:
        components = case_components(prediction, reference, scales)
        row.update(
            components=components,
            error=fmean(components[c] for c in COMPONENTS),
            important=important(reference),
            mean_signed_error_nm=fmean(float(t) for t in prediction["torque_nm"])
            - fmean(reference["outputs"]["torque_nm"]),
        )
    return row


def aggregate(rows):
    """One submission's result over typed rows. Reference-invalid and infra
    cases are counted and excluded, never charged to the model."""
    states = [r["state"] for r in rows]
    scored = [r for r in rows if r["state"] == SCORABLE]
    strong = [r for r in scored if r.get("important")]
    fails = {}
    for r in rows:
        for gate, verdict in r.get("gates", {}).items():
            if verdict == FAIL:
                fails[gate] = fails.get(gate, 0) + 1
    return {
        "n_cases": len(rows),
        "n_scored": len(scored),
        "n_gate_failed": states.count(GATE_FAILED),
        "n_reference_invalid": states.count(REFERENCE_INVALID),
        "n_failed_infra": states.count(FAILED_INFRA),
        "eligible": states.count(GATE_FAILED) == 0 and bool(scored),
        "score": fmean(r["error"] for r in scored) if scored else None,
        "components": (
            {c: fmean(r["components"][c] for r in scored) for c in COMPONENTS}
            if scored
            else None
        ),
        "important_score": fmean(r["error"] for r in strong) if strong else None,
        "n_important": len(strong),
        # Reported, not scored: a positive mean promises torque the machine
        # does not make where saturation acts.
        "important_mean_bias_nm": (
            fmean(r["mean_signed_error_nm"] for r in strong) if strong else None
        ),
        "gate_failures": fails,
    }


def feasibility(outputs, *, min_torque_nm, max_ripple_fraction):
    """Whether a machine makes at least `min_torque_nm` on average with a
    peak-to-peak ripple of at most `max_ripple_fraction` of it, from outputs
    (predicted or reference). A decision property, never a gate."""
    curve = list(outputs["torque_nm"])
    mean = fmean(curve)
    ripple = max(curve) - min(curve)
    return {
        "mean_nm": mean,
        "ripple_pk_pk_nm": ripple,
        "feasible": mean >= min_torque_nm and ripple <= max_ripple_fraction * mean,
    }
