"""The physics half of the exam, shared by the sealed graders (Validator spec
VALIDATOR_EXAM_PHYSICS_HALF_V1_20261023; owner direction: gates for gross
physical violations, measured fidelity for the degree).

```text
A = mean(A_acc, A_robust, A_law, A_response)      # equal weights, each in 0..1
```

- **A_acc**: the Challenge's own accuracy benefit, unchanged.
- **A_robust**: the same benefit on the worst stratum (near-limit versus interior
  by the reference's own distance to its limits, a median split), so one weak
  region caps it.
- **A_law**: ``1/(1+r)`` where ``r`` is the mean residual of the registered laws
  in the same normalised-output units as A_acc (TRAIN spread), so no new scale is
  chosen.
- **A_response**: local sensitivities from predictions at the private probe
  points x and x(1 +- delta) (``probe_design``), against the registered reference
  exponents fitted on TRAIN. Each error is the exponent error beyond the fit own
  residual band, expressed as the output change over that input full span, in
  TRAIN-spread units (so the same units as A_acc). The sign of the probe-mean
  sensitivity of the registered trends is a gate.

Laws are plugin data: each constrains a predicted row and names the output that
normalises its residual. A law that the reference satisfies with a clear margin
may also gate gross violation; the gate tolerance is ``reference residual
quantile + a registered margin`` (PHYSICS-CONTRACT-01). The margin is a registered
value this module does not choose: a law whose margin is None is measured but does
not gate.

Pure arithmetic; no I/O. DEVELOPMENT only: no qualification, weight, reward or
LIVE authority.
"""

from __future__ import annotations

import math
from statistics import fmean

RULE = "A=mean(A_acc,A_robust,A_law,A_response)"
LEGS = ("A_acc", "A_robust", "A_law", "A_response")
NOT_APPLIED = ()
SCHEMA = "carbon.scoring.physics-half.v1"
ROBUST = "median_split_by_reference_limit_distance"


class PhysicsHalfRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(ok, code):
    if not ok:
        raise PhysicsHalfRefused(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def block(laws, response):
    """The definition block. ``laws``: ``[(name, role, normaliser_output,
    gate_margin)]`` with role ``measured`` or ``gate`` and ``gate_margin`` None
    until the Validator registers it. ``response``: the registered reference
    sensitivities (see ``validate_response``)."""
    return {
        "schema": SCHEMA,
        "rule": RULE,
        "legs": list(LEGS),
        "legs_not_applied": list(NOT_APPLIED),
        "robust": ROBUST,
        "response": response,
        "laws": [
            {"name": n, "role": r, "normaliser": o, "gate_margin": g}
            for n, r, o, g in laws
        ],
    }


def validate_block(value):
    _require(
        type(value) is dict
        and set(value)
        == {
            "schema",
            "rule",
            "legs",
            "legs_not_applied",
            "robust",
            "laws",
            "response",
        }
        and value["schema"] == SCHEMA
        and value["rule"] == RULE
        and value["legs"] == list(LEGS)
        and value["legs_not_applied"] == list(NOT_APPLIED)
        and value["robust"] == ROBUST
        and type(value["laws"]) is list
        and all(
            type(law) is dict
            and set(law) == {"name", "role", "normaliser", "gate_margin"}
            and law["role"] in ("measured", "gate")
            and type(law["name"]) is str
            and type(law["normaliser"]) is str
            and (law["gate_margin"] is None or _number(law["gate_margin"]))
            for law in value["laws"]
        ),
        "physics_block",
    )
    validate_response(value["response"])
    return value


def validate_response(spec):
    """The registered reference sensitivities: per output and input the fitted
    log-log exponent, its allowance band, the input span and the sign gates."""
    inputs = spec.get("inputs") if type(spec) is dict else None
    outputs = spec.get("outputs") if type(spec) is dict else None
    _require(
        type(spec) is dict
        and set(spec)
        == {
            "inputs",
            "outputs",
            "exponent",
            "band",
            "span",
            "delta_range",
            "sign_gates",
        }
        and type(inputs) is list
        and type(outputs) is list
        and type(spec["delta_range"]) is list
        and len(spec["delta_range"]) == 2
        and all(_number(v) for v in spec["delta_range"])
        and 0 < spec["delta_range"][0] <= spec["delta_range"][1] < 0.5
        and type(spec["span"]) is list
        and len(spec["span"]) == len(inputs)
        and all(_number(v) and v > 0 for v in spec["span"])
        and all(
            type(spec[k]) is list
            and len(spec[k]) == len(outputs)
            and all(
                type(row) is list
                and len(row) == len(inputs)
                and all(
                    v is None or (_number(v) and (k == "exponent" or v >= 0))
                    for v in row
                )
                for row in spec[k]
            )
            for k in ("exponent", "band")
        )
        and type(spec["sign_gates"]) is list
        and all(
            type(g) is dict
            and set(g) == {"output", "input", "sign"}
            and g["output"] in outputs
            and g["input"] in inputs
            and g["sign"] in (1, -1)
            for g in spec["sign_gates"]
        ),
        "physics_response",
    )


def acc_benefit(errors):
    """The accuracy benefit of normalised absolute errors ``errors`` (rows x
    targets): the minimum of 1/(1+loss) over each target mean error and the
    worst row mean error (the Challenge A form)."""
    losses = [fmean(row[j] for row in errors) for j in range(len(errors[0]))]
    losses.append(max(fmean(row) for row in errors))
    return min(1.0 / (1.0 + loss) for loss in losses)


def split_by_nearness(nearness):
    """Indices of the nearer half and the interior half (stable on ties); one
    stratum only when there is a single row."""
    order = sorted(range(len(nearness)), key=lambda i: (nearness[i], i))
    half = max(1, len(order) // 2)
    near, interior = order[:half], order[half:]
    return [sorted(near)] + ([sorted(interior)] if interior else [])


def robust_benefit(errors, strata):
    """The worst stratum accuracy benefit."""
    return min(acc_benefit([errors[i] for i in stratum]) for stratum in strata)


def law_benefit(residuals):
    """``(A_law, record)`` from ``{law name: [normalised residual per row]}``."""
    means = {name: fmean(rows) for name, rows in residuals.items()}
    r = fmean(means.values()) if means else 0.0
    return 1.0 / (1.0 + r), {"mean_residual_by_law": means, "mean_residual": r}


def response_benefit(groups, inputs_of, outputs_of, spec, spread):
    """``(A_response, record)``. ``groups``: `probe_design.groups` output over
    probe-row indices; ``inputs_of(i)``/``outputs_of(i)`` give a probe row inputs
    and predicted outputs (lists of floats); ``spread`` is per output. Returns
    ``(None, record)`` when a probe prediction is unusable (a candidate fault)."""
    validate_response(spec)
    n_in, n_out = len(spec["inputs"]), len(spec["outputs"])
    errors, slopes = [], {}
    for group in groups:
        y0, x0 = outputs_of(group["base"]), inputs_of(group["base"])
        used = [y0] + [outputs_of(i) for pair in group["dims"].values() for i in pair]
        if not all(_number(v) for row in used for v in row) or not all(
            v > 0 for v in y0
        ):
            return None, {"probe_invalid": True}
        for d in range(n_in):
            plus, minus = group["dims"][d]
            yp, ym = outputs_of(plus), outputs_of(minus)
            dx = (inputs_of(plus)[d] - inputs_of(minus)[d]) / x0[d]
            for j in range(n_out):
                slope = ((yp[j] - ym[j]) / y0[j]) / dx
                slopes.setdefault((j, d), []).append(slope)
                if spec["exponent"][j][d] is None:
                    continue  # a sign-gate-only pair: no registered size
                gap = max(
                    0.0,
                    abs(slope - spec["exponent"][j][d]) - spec["band"][j][d],
                )
                errors.append(gap * abs(y0[j]) * (spec["span"][d] / x0[d]) / spread[j])
    mean_slope = {key: fmean(values) for key, values in slopes.items()}
    failed = []
    for gate in spec["sign_gates"]:
        j, d = spec["outputs"].index(gate["output"]), spec["inputs"].index(
            gate["input"]
        )
        if mean_slope[(j, d)] * gate["sign"] <= 0:
            failed.append(f"{gate['output']}~{gate['input']}")
    mean_error = fmean(errors) if errors else 0.0
    return 1.0 / (1.0 + mean_error), {
        "mean_response_error": mean_error,
        "sign_gate_failed": sorted(failed),
    }


def combine(a_acc, a_robust, a_law, a_response):
    legs = {
        "A_acc": a_acc,
        "A_robust": a_robust,
        "A_law": a_law,
        "A_response": a_response,
    }
    return fmean(legs.values()), legs
