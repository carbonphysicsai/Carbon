"""The cold plate DEVELOPMENT exam: case typing, gates, score and aggregate.

Built in the shape of `carbon.battery.exam`, and kept apart the same way:

- **A case is typed first.**
  - `REFERENCE_INVALID`: withdrawn for every model.
  - `FAILED_INFRA`: not scored, retryable, never a scientific failure.
  - Otherwise the gates decide `GATE_FAILED` or `SCORABLE`.
- **Gates are physical laws a prediction must not break.** Every one holds
  for every sound reference by construction, and `calibrate` checks it does
  on the references before any model is judged. A gate never judges whether
  the design is good: an accurate prediction of a hot, costly plate passes.
- **Mandatory gate failure is never compensated by score.** One failed gate
  makes the submission ineligible.
- **The score is soft:** the mean of three TRAIN-normalized errors, lower is
  better. It is bound to this Challenge version and not comparable across
  Challenges.
- **Feasibility is not a gate.** Whether a plate keeps a die below a
  temperature at a pumping budget is a decision about designs
  (`feasibility`), reported beside the score, never inside it.

Every number here is a provisional DEVELOPMENT value under
OWNER-CHALLENGE-DESIGN-01, with its basis beside it. None is scientifically
qualified.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean, pstdev

from .domain import (
    PROFILE_SEGMENTS,
    TIM_RESISTANCE_M2K_W,
    check_inputs,
    derived,
    heat_flux,
)

SCORABLE, GATE_FAILED, REFERENCE_INVALID, FAILED_INFRA = (
    "SCORABLE",
    "GATE_FAILED",
    "REFERENCE_INVALID",
    "FAILED_INFRA",
)
PASS, FAIL, NOT_APPLICABLE = "PASS", "FAIL", "NOT_APPLICABLE"
F32_EPS = 2.0**-23  # float32 machine epsilon
#: Float32 round-off allowance, as battery's: 32 ulp at the largest value.
ULP_FACTOR = 32
SHAPES = {"peak_c": (), "profile_c": (PROFILE_SEGMENTS,), "pressure_drop_pa": ()}
#: The important region: cases whose reference heated-face peak is at least
#: this. Provisional DEVELOPMENT value: the upper third of the population's
#: closed-form peak range (about 50 to 105 C), where a design is near its
#: limit and an optimistic prediction costs most.
T_IMPORTANT_C = 85.0
COMPONENTS = ("peak", "profile", "pressure")


@dataclass(frozen=True)
class Gate:
    gate_id: str
    formula: str
    basis: str


GATES = (
    Gate(
        "schema_finite",
        "peak_c, profile_c (30 values) and pressure_drop_pa present, of that "
        "shape, and finite",
        "the prediction contract",
    ),
    Gate(
        "face_above_inlet",
        "min(profile_c) > inlet_c",
        "heat flows from the heated face into coolant no colder than the "
        "inlet; the face is at least the base's conduction rise above it",
    ),
    Gate(
        "peak_bounds_profile",
        "peak_c >= max(profile_c) - 32 float32 ulp at the peak",
        "the peak is the face's maximum; each profile value is a mean over a "
        "segment and the span",
    ),
    Gate(
        "pressure_drop_positive",
        "pressure_drop_pa > 0",
        "the coolant flows from inlet to outlet through a viscous duct",
    ),
    Gate(
        "paired_repeat",
        "a hidden duplicate's prediction equals the original's within "
        "32 float32 ulp",
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


def _values(prediction, name):
    """The output's values as a flat list, or None if it is not of its
    declared shape or not finite. A scalar must be a number, never a list."""
    value = prediction[name]
    if SHAPES[name] == ():
        return [float(value)] if _number(value) else None
    if (
        type(value) not in (list, tuple)
        or len(value) != SHAPES[name][0]
        or not all(_number(v) for v in value)
    ):
        return None
    return [float(v) for v in value]


def _finite_shape(prediction):
    try:
        return all(_values(prediction, name) is not None for name in SHAPES)
    except (KeyError, TypeError):
        return False


def gates(prediction, case, twin=None):
    """Every gate's verdict for one prediction of one case."""
    g = {"schema_finite": PASS if _finite_shape(prediction) else FAIL}
    if g["schema_finite"] == FAIL:
        return g  # nothing else can be read from a malformed prediction
    profile = _values(prediction, "profile_c")
    peak = float(prediction["peak_c"])
    g["face_above_inlet"] = PASS if min(profile) > case["inlet_c"] else FAIL
    g["peak_bounds_profile"] = (
        PASS if peak >= max(profile) - _ulp(max(profile)) else FAIL
    )
    g["pressure_drop_positive"] = (
        PASS if float(prediction["pressure_drop_pa"]) > 0 else FAIL
    )
    if twin is None:
        g["paired_repeat"] = NOT_APPLICABLE
    else:
        same = _finite_shape(twin)
        if same:
            for name in SHAPES:
                pairs = zip(_values(prediction, name), _values(twin, name))
                if any(abs(a - b) > _ulp(a) for a, b in pairs):
                    same = False
        g["paired_repeat"] = PASS if same else FAIL
    return g


def evaluate_case(prediction, reference, twin=None, infra_failed=False):
    """Type one case for one model and run every applicable gate."""
    if reference.get("status") != "OK":
        return {"state": REFERENCE_INVALID, "gates": {}}
    if infra_failed or prediction is None:
        return {"state": FAILED_INFRA, "gates": {}}
    g = gates(prediction, reference["inputs"], twin)
    return {"state": GATE_FAILED if FAIL in g.values() else SCORABLE, "gates": g}


def calibrate(references):
    """Check every gate on every OK reference, from reference evidence only.

    A gate a sound reference fails is a broken gate, so this refuses rather
    than widening a tolerance. Returns each gate's smallest margin as
    evidence."""
    margins = {"face_above_inlet": math.inf, "peak_bounds_profile": math.inf}
    count = 0
    for ref in references:
        if ref.get("status") != "OK":
            continue
        count += 1
        out = ref["outputs"]
        verdict = gates(out, ref["inputs"])
        failed = [k for k, v in verdict.items() if v == FAIL]
        if failed:
            raise ValueError(f"reference {ref['case_id']} fails gates {failed}")
        margins["face_above_inlet"] = min(
            margins["face_above_inlet"],
            min(out["profile_c"]) - ref["inputs"]["inlet_c"],
        )
        margins["peak_bounds_profile"] = min(
            margins["peak_bounds_profile"], out["peak_c"] - max(out["profile_c"])
        )
    if count == 0:
        raise ValueError("no OK reference: nothing to calibrate on")
    return {"n_references": count, "smallest_margin": margins}


def scales_from_train(train):
    """TRAIN spread of each scored quantity, from OK references only.

    Temperatures are scaled by the spread of their rise above the inlet: the
    inlet is an input, so its 15 K range would otherwise inflate the scale.
    Pressure is scored in log space, because it spans two decades."""
    ok = [r for r in train if r.get("status") == "OK"]
    if len(ok) < 2:
        raise ValueError("at least two OK TRAIN references are needed")
    peak = [r["outputs"]["peak_c"] - r["inputs"]["inlet_c"] for r in ok]
    profile = [
        t - r["inputs"]["inlet_c"] for r in ok for t in r["outputs"]["profile_c"]
    ]
    log_dp = [math.log(r["outputs"]["pressure_drop_pa"]) for r in ok]
    return {
        "s_peak": pstdev(peak),
        "s_profile": pstdev(profile),
        "s_log_dp": pstdev(log_dp),
        "n_train": len(ok),
    }


def case_components(prediction, reference, scales):
    out = reference["outputs"]
    squared = [
        (float(p) - r) ** 2 for p, r in zip(prediction["profile_c"], out["profile_c"])
    ]
    return {
        "peak": abs(float(prediction["peak_c"]) - out["peak_c"]) / scales["s_peak"],
        "profile": math.sqrt(fmean(squared)) / scales["s_profile"],
        "pressure": abs(
            math.log(float(prediction["pressure_drop_pa"]) / out["pressure_drop_pa"])
        )
        / scales["s_log_dp"],
    }


def case_error(components):
    return fmean(components[c] for c in COMPONENTS)


def important(reference):
    return reference["outputs"]["peak_c"] >= T_IMPORTANT_C


def score_case(prediction, reference, scales, twin=None, infra_failed=False):
    """A typed, gated and (when scorable) scored row for one case."""
    row = evaluate_case(prediction, reference, twin, infra_failed)
    row["case_id"] = reference.get("case_id")
    if row["state"] == SCORABLE:
        components = case_components(prediction, reference, scales)
        row.update(
            components=components,
            error=case_error(components),
            important=important(reference),
            peak_signed_error=float(prediction["peak_c"])
            - reference["outputs"]["peak_c"],
        )
    return row


def aggregate(rows):
    """One submission's result over typed rows. Reference-invalid and infra
    cases are counted and excluded, never charged to the model."""
    states = [r["state"] for r in rows]
    scored = [r for r in rows if r["state"] == SCORABLE]
    hot = [r for r in scored if r.get("important")]
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
        "important_score": fmean(r["error"] for r in hot) if hot else None,
        "n_important": len(hot),
        # Reported, not scored: a negative mean is optimism where it costs
        # most (EV2's boundary-optimist finding on battery).
        "important_peak_bias_k": (
            fmean(r["peak_signed_error"] for r in hot) if hot else None
        ),
        "gate_failures": fails,
    }


def die_peak_c(case, outputs):
    """The hottest die temperature implied by the outputs and the TIM.

    Each segment's face temperature plus its local flux through R'', then
    the face's excess of its peak over the hottest segment mean (spanwise
    and within-segment variation) added on. The TIM term is not small: R''
    times a 3x spot at 1.5 kW is about 25 K, against 5.6 K for a uniform
    1 kW map, so where the flux peaks matters as much as where the face
    does."""
    case = check_inputs(case)
    seg = 30.0 / PROFILE_SEGMENTS
    profile = list(outputs["profile_c"])
    through_tim = max(
        t + heat_flux(case, (i + 0.5) * seg) * TIM_RESISTANCE_M2K_W
        for i, t in enumerate(profile)
    )
    return through_tim + max(0.0, outputs["peak_c"] - max(profile))


def feasibility(case, outputs, *, die_limit_c, hydraulic_limit_w):
    """Whether a design meets a decision's limits, from outputs (predicted or
    reference). A decision property, never a gate on a prediction."""
    case = check_inputs(case)
    hydraulic = outputs["pressure_drop_pa"] * derived(case)["flow_m3_s"]
    die = die_peak_c(case, outputs)
    return {
        "die_peak_c": die,
        "hydraulic_w": hydraulic,
        "feasible": die <= die_limit_c and hydraulic <= hydraulic_limit_w,
    }
