"""Published gates for the battery exam-design challenge, with typed outcomes.

A gate is published with its formula, tolerance, how the tolerance was derived,
where it applies and which model outputs it needs. Gates run on *every*
screening and final case, reuse the same stored predictions the score uses, and
return one of three per-case outcomes: ``PASS``, ``FAIL`` or ``NOT_APPLICABLE``.

Before any gate runs, the case itself is typed:

* ``REFERENCE_INVALID`` - the reference record is not ``OK`` or fails the
  reference self-check. The case is withdrawn for every model; no model is
  charged with it.
* ``FAILED_INFRA`` - the prediction is missing because the worker failed. Not
  a scientific failure, not scored, retryable.
* otherwise the gates decide ``GATE_FAILED`` or ``SCORABLE``.

Deliberately absent, and why:

* **No non-negative heat gate.** Reversible (entropic) heat can be negative, so
  total heat generation is not sign-definite.
* **No temperature >= ambient gate.** Entropic cooling can pull a lumped cell
  below ambient.
* **No gate on the plating margin or a temperature limit.** Correctly predicting
  that a protocol crosses an unsafe operating limit is a correct prediction; it
  is scored for accuracy and weighted as an important region, never failed.
* **No charge-conservation gate.** The required outputs are voltage,
  temperature, a plating indicator and capacities. Current is not predicted, so
  conservation cannot be established from them and is not inferred.
* **No capacity-monotonicity gate.** The reference itself shows capacity rising
  across early cycles in cold, high-rate cases (self-heating and partial
  stripping of reversibly plated lithium), so monotone fade is not a property
  of the specified model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

F32_EPS = float(np.finfo(np.float32).eps)
ULP_FACTOR = (
    32  # the Burgers development rule's initial-condition resolution, 32 float32 ulp
)

PASS, FAIL, NOT_APPLICABLE = "PASS", "FAIL", "NOT_APPLICABLE"
SCORABLE, GATE_FAILED, REFERENCE_INVALID, FAILED_INFRA = (
    "SCORABLE",
    "GATE_FAILED",
    "REFERENCE_INVALID",
    "FAILED_INFRA",
)


@dataclass(frozen=True)
class Gate:
    gate_id: str
    formula: str
    required_outputs: tuple[str, ...]
    applicability: str
    tolerance_rule: str


GATES = (
    Gate(
        "schema_finite",
        "every required output present, of the declared shape, and finite",
        ("voltage_v", "temperature_c", "plating_margin_v", "capacity_ah"),
        "all cases",
        "exact",
    ),
    Gate(
        "initial_voltage",
        "|V_hat(0) - OCV(soc0)| <= tau_v0",
        ("voltage_v",),
        "all cases (cycle 1 begins with a zero-current rest at soc0)",
        "max(2 x max reference |V(0) - OCV| on calibration references, 32 float32 ulp at 4.2 V). The reference's "
        "V(0) is a zero-current rest voltage 0.003-0.44 mV below OCV (internal side-reaction currents), so this "
        "is a bounded-offset boundary probe, not an exact initial-value constraint",
    ),
    Gate(
        "initial_temperature",
        "|T_hat(0) - T_amb| <= tau_t0",
        ("temperature_c",),
        "all cases (initial temperature = ambient)",
        "max(2 x max reference |T(0) - T_amb|, 32 float32 ulp at 40 C)",
    ),
    Gate(
        "voltage_ceiling",
        "max_t V_hat(t) <= V_max + tau_vmax",
        ("voltage_v",),
        "all cases (the cycler holds V <= 4.2 V; this is protocol control, not a safety limit)",
        "max(2 x max reference overshoot of V_max, 32 float32 ulp at 4.2 V)",
    ),
    Gate(
        "voltage_floor",
        "min_t V_hat(t) >= V_min - tau_vmin",
        ("voltage_v",),
        "all cases (discharge stops at 2.5 V)",
        "max(2 x max reference undershoot of V_min, 32 float32 ulp at 2.5 V)",
    ),
    Gate(
        "capacity_bound",
        "0 < Q_hat_k <= Q_bound for every checkpoint k",
        ("capacity_ah",),
        "all cases",
        "Q_bound = min(negative, positive, lithium-inventory capacity) from the parameter set; no tolerance",
    ),
    Gate(
        "paired_repeat",
        "|y_hat(x) - y_hat(x')| <= 32 float32 ulp x max(1, |y|) when x' duplicates x",
        ("voltage_v", "temperature_c", "plating_margin_v", "capacity_ah"),
        "cases carrying a hidden duplicate in the same batch",
        "32 float32 ulp",
    ),
)


@dataclass
class Tolerances:
    tau_v0: float
    tau_t0: float
    tau_vmax: float
    tau_vmin: float
    q_bound: float
    v_max: float = 4.2
    v_min: float = 2.5
    evidence: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            k: getattr(self, k)
            for k in (
                "tau_v0",
                "tau_t0",
                "tau_vmax",
                "tau_vmin",
                "q_bound",
                "v_max",
                "v_min",
            )
        } | {"evidence": self.evidence}


def calibrate(
    references: list[dict], ocv: dict[str, float], q_bound: float, v_max=4.2, v_min=2.5
) -> Tolerances:
    """Derive tolerances from reference evidence only (never from model predictions).

    ``references`` are OK reference records on the calibration roles (TRAIN,
    PRACTICE and pilot refinements); ``ocv`` maps case_id to the parameter-set
    OCV at that case's initial state.
    """
    d_v0 = max(
        abs(r["outputs"]["voltage_v"][0] - ocv[r["case_id"]]) for r in references
    )
    d_t0 = max(
        abs(r["outputs"]["temperature_c"][0] - r["inputs"]["t_amb_c"])
        for r in references
    )
    over = max(max(r["outputs"]["voltage_v"]) - v_max for r in references)
    under = max(v_min - min(r["outputs"]["voltage_v"]) for r in references)
    ulp = lambda x: ULP_FACTOR * F32_EPS * x
    return Tolerances(
        tau_v0=max(2 * d_v0, ulp(v_max)),
        tau_t0=max(2 * d_t0, ulp(40.0)),
        tau_vmax=max(2 * max(over, 0.0), ulp(v_max)),
        tau_vmin=max(2 * max(under, 0.0), ulp(v_min)),
        q_bound=q_bound,
        v_max=v_max,
        v_min=v_min,
        evidence={
            "max_ref_v0_minus_ocv": d_v0,
            "max_ref_t0_minus_ambient": d_t0,
            "max_ref_overshoot_v": over,
            "max_ref_undershoot_v": under,
            "n_references": len(references),
        },
    )


def _finite_shape(pred: dict, shapes: dict) -> bool:
    try:
        for k, shp in shapes.items():
            a = np.asarray(pred[k], dtype=float)
            if a.shape != shp or not np.all(np.isfinite(a)):
                return False
        return True
    except Exception:  # noqa: BLE001 -- failure is typed
        return False


def evaluate_case(
    pred: dict | None,
    reference: dict,
    case_inputs: dict,
    ocv: float,
    tol: Tolerances,
    shapes: dict,
    twin_pred: dict | None = None,
    infra_failed: bool = False,
) -> dict:
    """Type one case for one model and run every applicable gate."""
    if reference.get("status") != "OK" or not reference.get("reference_valid", True):
        return {"state": REFERENCE_INVALID, "gates": {}}
    if infra_failed or pred is None:
        return {"state": FAILED_INFRA, "gates": {}}
    g: dict[str, str] = {}
    g["schema_finite"] = PASS if _finite_shape(pred, shapes) else FAIL
    if g["schema_finite"] == FAIL:
        # Nothing else can be evaluated on malformed output; the case fails.
        return {"state": GATE_FAILED, "gates": g}
    v = np.asarray(pred["voltage_v"], float)
    t = np.asarray(pred["temperature_c"], float)
    q = np.asarray(pred["capacity_ah"], float)
    g["initial_voltage"] = PASS if abs(v[0] - ocv) <= tol.tau_v0 else FAIL
    g["initial_temperature"] = (
        PASS if abs(t[0] - case_inputs["t_amb_c"]) <= tol.tau_t0 else FAIL
    )
    g["voltage_ceiling"] = PASS if v.max() <= tol.v_max + tol.tau_vmax else FAIL
    g["voltage_floor"] = PASS if v.min() >= tol.v_min - tol.tau_vmin else FAIL
    g["capacity_bound"] = PASS if np.all(q > 0) and np.all(q <= tol.q_bound) else FAIL
    if twin_pred is None:
        g["paired_repeat"] = NOT_APPLICABLE
    else:
        ok = _finite_shape(twin_pred, shapes)
        if ok:
            for k in shapes:
                a, b = np.asarray(pred[k], float), np.asarray(twin_pred[k], float)
                if np.any(
                    np.abs(a - b) > ULP_FACTOR * F32_EPS * np.maximum(1.0, np.abs(a))
                ):
                    ok = False
        g["paired_repeat"] = PASS if ok else FAIL
    state = GATE_FAILED if FAIL in g.values() else SCORABLE
    return {"state": state, "gates": g}
