"""Battery exam-design score: per-case normalized error from stored predictions.

The score reuses exactly the predictions the gates checked. Each component is
normalized by a public scale published with the TRAIN dataset version (the
TRAIN standard deviation of that output), so no component dominates by units:

* ``voltage``      RMS_t(V_hat - V) / s_V
* ``temperature``  RMS_t(T_hat - T) / s_T   (s_T: spread of the rise T - T_amb, not of T)
* ``plating``      |eta_hat - eta| / s_eta
* ``capacity``     mean of |Q_hat_1 - Q_1| / s_Q1 and RMS_k(fade_hat_k - fade_k) / s_fade, where
                   fade_k = Q_1 - Q_k. Split because cycle-1 capacity varies ~60 mAh with temperature
                   while 30-cycle fade is ~6-8 mAh: one pooled scale would make a fade error of most
                   of the degradation signal nearly free.

**What the weights mean.** ``s_c`` is the spread of output ``c`` across TRAIN,
so a component of 1.0 means the model explains none of that output's variation
over the operating envelope (it does as well as predicting the TRAIN mean) and
0.1 means it leaves a tenth. Dividing by the spread therefore expresses each
error as a fraction of what the envelope makes worth predicting, and weighting
the four components equally is a declared **engineering choice** - equal
concern for terminal voltage, thermal response, plating risk and capacity fade
- not a scientific finding. An owner who values, say, plating risk above
voltage fit would change the weights; that is a scoring-contract change.

**Near-zero spread.** A scale is never allowed below that output's reference
uncertainty (``floor_c``, the median coarse-versus-refined disagreement from
the refinement sample): an output that barely varies across TRAIN cannot
amplify errors the reference itself cannot resolve.

The case error is the unweighted mean of the four; lower is better. It is a
development measure of agreement with the specified model, bound to this
challenge version, and not comparable across challenges.

**Important region.** A case is important when its *reference* plating margin
is at or below ``PLATING_IMPORTANT_V`` (plating conditions reached or within
20 mV) or its reference peak temperature reaches ``T_IMPORTANT_C``. These are
the cases where a prediction matters most for a charging decision. They are
scored exactly like any other case, never gated, and reported separately so a
comparison can refuse an overall gain bought by an important-region regression.
"""

from __future__ import annotations

import numpy as np

COMPONENTS = ("voltage", "temperature", "plating", "capacity")
PLATING_IMPORTANT_V = 0.02
T_IMPORTANT_C = 45.0


def scales_from_train(train_refs: list[dict], floors: dict | None = None) -> dict:
    """TRAIN spread per output, never below the output's reference-uncertainty floor."""
    v = np.array([r["outputs"]["voltage_v"] for r in train_refs])
    # Temperature is scaled by the spread of the *rise above ambient*: ambient is an input, so its 5-40 C
    # range would otherwise inflate the scale and make a 1 C thermal error nearly free.
    t = np.array([np.asarray(r["outputs"]["temperature_c"]) - r["inputs"]["t_amb_c"] for r in train_refs])
    e = np.array([r["outputs"]["plating_margin_v"] for r in train_refs])
    q = np.array([r["outputs"]["capacity_ah"] for r in train_refs])
    fade = q[:, :1] - q[:, 1:]
    raw = {"s_v": float(v.std()), "s_t": float(t.std()), "s_eta": float(e.std()), "s_q1": float(q[:, 0].std()),
           "s_fade": float(fade.std())}
    floors = floors or {}
    out = {k: max(val, float(floors.get(k, 0.0))) for k, val in raw.items()}
    return out | {"raw": raw, "floors": floors, "n_train": len(train_refs)}


def is_important(ref: dict) -> bool:
    return (ref["outputs"]["plating_margin_v"] <= PLATING_IMPORTANT_V
            or ref.get("diagnostics", {}).get("t_max_c", -1e9) >= T_IMPORTANT_C)


def case_components(pred: dict, ref: dict, scales: dict) -> dict:
    o = ref["outputs"]
    rms = lambda a, b: float(np.sqrt(np.mean((np.asarray(a, float) - np.asarray(b, float)) ** 2)))  # noqa: E731
    return {
        "voltage": rms(pred["voltage_v"], o["voltage_v"]) / scales["s_v"],
        "temperature": rms(pred["temperature_c"], o["temperature_c"]) / scales["s_t"],
        "plating": abs(float(pred["plating_margin_v"]) - o["plating_margin_v"]) / scales["s_eta"],
        "capacity": 0.5 * (abs(float(pred["capacity_ah"][0]) - o["capacity_ah"][0]) / scales["s_q1"]
                           + rms(np.asarray(pred["capacity_ah"][0]) - np.asarray(pred["capacity_ah"][1:], float),
                                 o["capacity_ah"][0] - np.asarray(o["capacity_ah"][1:], float)) / scales["s_fade"]),
    }


def case_error(components: dict) -> float:
    return float(np.mean([components[c] for c in COMPONENTS]))


def aggregate(case_rows: list[dict]) -> dict:
    """Summarize typed case rows from ``gates.evaluate_case`` plus errors.

    A single gate failure makes the submission ineligible: mandatory failure is
    not compensated by soft performance. Reference-invalid and infra cases are
    counted and excluded, never charged to the model.
    """
    states = [r["state"] for r in case_rows]
    scored = [r for r in case_rows if r["state"] == "SCORABLE"]
    imp = [r for r in scored if r.get("important")]
    out = {
        "n_cases": len(case_rows),
        "n_scored": len(scored),
        "n_gate_failed": states.count("GATE_FAILED"),
        "n_reference_invalid": states.count("REFERENCE_INVALID"),
        "n_failed_infra": states.count("FAILED_INFRA"),
        "eligible": states.count("GATE_FAILED") == 0 and len(scored) > 0,
        "score": float(np.mean([r["error"] for r in scored])) if scored else None,
        "important_score": float(np.mean([r["error"] for r in imp])) if imp else None,
        "n_important": len(imp),
        "components": {c: float(np.mean([r["components"][c] for r in scored])) for c in COMPONENTS} if scored else None,
    }
    fails: dict[str, int] = {}
    for r in case_rows:
        for g, v in r.get("gates", {}).items():
            if v == "FAIL":
                fails[g] = fails.get(g, 0) + 1
    out["gate_failures"] = fails
    return out
