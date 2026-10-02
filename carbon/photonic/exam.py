# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""The photonic coupler DEVELOPMENT exam: case typing, gates, score, aggregate.

In the shape of `carbon.cold_plate.exam`, kept apart the same way:

- **A case is typed first.** `REFERENCE_INVALID` is withdrawn for every
  model; `FAILED_INFRA` is not scored, is retryable, and is never a
  scientific failure. Otherwise the gates decide `GATE_FAILED` or
  `SCORABLE`.
- **Gates are laws of the reference contract a prediction must not break.**
  Each holds for every sound reference by construction, and `calibrate`
  checks that it does before any model is judged. One failed gate makes the
  submission ineligible; no score compensates it.
- **The score is soft and phase-aware:** the RMS error of the complex
  S-parameters S31 and S41 that the outputs imply (`reference.
  s_parameters`), over the five wavelengths, lower is better. It is
  unit-free and blind to a whole turn of common phase, which no measurement
  could see, but it charges any other phase error: a model that ignores
  phase cannot score well. It is bound to this Challenge version and not
  comparable across Challenges.
- **Feasibility is not a gate.** Whether a coupler meets a tap ratio and a
  flatness is a decision about designs (`feasibility`), reported beside the
  score.

Every number here is a provisional DEVELOPMENT value under
OWNER-CHALLENGE-DESIGN-01, with its basis beside it. None is scientifically
qualified.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise
from statistics import fmean

from .domain import WAVELENGTHS_UM
from .reference import s_parameters

SCORABLE, GATE_FAILED, REFERENCE_INVALID, FAILED_INFRA = (
    "SCORABLE",
    "GATE_FAILED",
    "REFERENCE_INVALID",
    "FAILED_INFRA",
)
PASS, FAIL, NOT_APPLICABLE = "PASS", "FAIL", "NOT_APPLICABLE"
F32_EPS = 2.0**-23
ULP_FACTOR = 32  # float32 round-off allowance, as battery's and the cold plate's
OUTPUTS = ("cross_power", "common_phase_rad")
N_WL = len(WAVELENGTHS_UM)
#: The important region: cases whose reference cross power at 1.55 um is at
#: least this. Provisional DEVELOPMENT value: the strongest couplers of the
#: family (its cross power runs from below 1 % to about 20 %), where the
#: cross port carries a signal a circuit is designed around.
CROSS_IMPORTANT = 0.10
CENTRE = WAVELENGTHS_UM.index(1.55)


@dataclass(frozen=True)
class Gate:
    gate_id: str
    formula: str
    basis: str


GATES = (
    Gate(
        "schema_finite",
        "cross_power and common_phase_rad present, five values each, finite",
        "the prediction contract",
    ),
    Gate(
        "cross_power_bounded",
        "0 <= cross_power <= 1 within 32 float32 ulp, at every wavelength",
        "a power fraction of a passive, lossless coupler (the reference "
        "contract has no loss and no gain)",
    ),
    Gate(
        "phase_falls_with_wavelength",
        "common_phase_rad strictly decreasing from 1.50 to 1.60 um",
        "the common phase is k0 times the path's mean index; its growth with "
        "frequency is the group delay, positive for a guided mode",
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


def _values(prediction, name):
    value = prediction[name]
    if (
        type(value) not in (list, tuple)
        or len(value) != N_WL
        or not all(_number(v) for v in value)
    ):
        return None
    return [float(v) for v in value]


def _finite_shape(prediction):
    try:
        return all(_values(prediction, name) is not None for name in OUTPUTS)
    except (KeyError, TypeError):
        return False


def gates(prediction, twin=None):
    """Every gate's verdict for one prediction."""
    g = {"schema_finite": PASS if _finite_shape(prediction) else FAIL}
    if g["schema_finite"] == FAIL:
        return g
    cross = _values(prediction, "cross_power")
    phase = _values(prediction, "common_phase_rad")
    g["cross_power_bounded"] = (
        PASS if all(-_ulp(1.0) <= c <= 1.0 + _ulp(1.0) for c in cross) else FAIL
    )
    g["phase_falls_with_wavelength"] = (
        PASS if all(b < a for a, b in pairwise(phase)) else FAIL
    )
    if twin is None:
        g["paired_repeat"] = NOT_APPLICABLE
    else:
        same = _finite_shape(twin)
        if same:
            for name in OUTPUTS:
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
    g = gates(prediction, twin)
    return {"state": GATE_FAILED if FAIL in g.values() else SCORABLE, "gates": g}


def calibrate(references):
    """Check every gate on every OK reference; refuse rather than widen.
    Returns each gate's smallest margin as evidence."""
    margins = {"cross_power_bounded": math.inf, "phase_falls_with_wavelength": math.inf}
    count = 0
    for ref in references:
        if ref.get("status") != "OK":
            continue
        count += 1
        out = ref["outputs"]
        failed = [k for k, v in gates(out).items() if v == FAIL]
        if failed:
            raise ValueError(f"reference {ref.get('case_id')} fails gates {failed}")
        cross, phase = out["cross_power"], out["common_phase_rad"]
        margins["cross_power_bounded"] = min(
            margins["cross_power_bounded"], min(cross), 1 - max(cross)
        )
        margins["phase_falls_with_wavelength"] = min(
            margins["phase_falls_with_wavelength"],
            min(a - b for a, b in pairwise(phase)),
        )
    if count == 0:
        raise ValueError("no OK reference: nothing to calibrate on")
    return {"n_references": count, "smallest_margin": margins}


def _wrap(angle):
    return (angle + math.pi) % (2 * math.pi) - math.pi


def case_error(prediction, reference):
    """RMS complex S-parameter error over the wavelengths, with the two
    diagnostics it combines (reported, not scored separately)."""
    out = reference["outputs"]
    predicted = s_parameters(prediction)
    true = s_parameters(out)
    # |dS31|^2 + |dS41|^2 per wavelength: a common phase error d alone costs
    # (2 sin(d/2))^2, so the RMS reads as radians for small phase errors.
    squared = [
        abs(p31 - t31) ** 2 + abs(p41 - t41) ** 2
        for (p31, p41), (t31, t41) in zip(predicted, true)
    ]
    cross = [
        float(p) - r for p, r in zip(prediction["cross_power"], out["cross_power"])
    ]
    phase = [
        _wrap(float(p) - r)
        for p, r in zip(prediction["common_phase_rad"], out["common_phase_rad"])
    ]
    return {
        "s_rms": math.sqrt(fmean(squared)),
        "cross_rms": math.sqrt(fmean(c * c for c in cross)),
        "phase_rms_rad": math.sqrt(fmean(p * p for p in phase)),
        "cross_signed_centre": cross[CENTRE],
    }


def important(reference):
    return reference["outputs"]["cross_power"][CENTRE] >= CROSS_IMPORTANT


def score_case(prediction, reference, twin=None, infra_failed=False):
    """A typed, gated and (when scorable) scored row for one case."""
    row = evaluate_case(prediction, reference, twin, infra_failed)
    row["case_id"] = reference.get("case_id")
    if row["state"] == SCORABLE:
        errors = case_error(prediction, reference)
        row.update(errors=errors, error=errors["s_rms"], important=important(reference))
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

    def mean(rows_, key):
        return fmean(r["errors"][key] for r in rows_) if rows_ else None

    return {
        "n_cases": len(rows),
        "n_scored": len(scored),
        "n_gate_failed": states.count(GATE_FAILED),
        "n_reference_invalid": states.count(REFERENCE_INVALID),
        "n_failed_infra": states.count(FAILED_INFRA),
        "eligible": states.count(GATE_FAILED) == 0 and bool(scored),
        "score": mean(scored, "s_rms"),
        "cross_rms": mean(scored, "cross_rms"),
        "phase_rms_rad": mean(scored, "phase_rms_rad"),
        "important_score": mean(strong, "s_rms"),
        "n_important": len(strong),
        # Reported, not scored: a negative mean under-predicts the cross
        # port where it carries most.
        "important_cross_bias": mean(strong, "cross_signed_centre"),
        "gate_failures": fails,
    }


def feasibility(outputs, *, target, tolerance, flatness):
    """Whether a coupler is a tap of `target` +- `tolerance` at 1.55 um whose
    cross power varies by at most `flatness` over the band, from outputs
    (predicted or reference). A decision property, never a gate."""
    cross = list(outputs["cross_power"])
    spread = max(cross) - min(cross)
    return {
        "cross_centre": cross[CENTRE],
        "spread": spread,
        "feasible": abs(cross[CENTRE] - target) <= tolerance and spread <= flatness,
    }
