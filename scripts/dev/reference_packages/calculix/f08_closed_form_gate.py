"""The closed-form gate of Ribbed Bracket 2.0 (STRESS): can a cheap structured fit solve the fillet-stress exam?

Before any pool is graded, the exam must not be solvable by a cheap structured fit. Two adversaries are fitted on TRAIN
(scalar rows only: inputs -> peak von Mises at the fillet) and predict a probe pool:

1. **Structured (beam theory + a notch-factor fit).** The nominal bending stress at the rib root from the section's two
   second moments (plate plus two ribs), for the load's two components (the angle), times a stress-concentration factor
   fitted log-linearly in the fillet's proportions (fillet radius over plate thickness, over rib thickness) and the rib
   slenderness. A stress under a given force does not depend on the alloy, so the alloy enters only through the yield
   limit, a table lookup: the adversary gets it for free, which the report states.
2. **The client's way.** The ten best-spread TRAIN rows a client might afford to run (greedy max-min) and a ridge fit of
   ln(peak) on a handful of log features.

    python3 f08_closed_form_gate.py fit --train TRAIN.json --out MODEL.json [--ridge 1e-6]
    python3 f08_closed_form_gate.py predict --model MODEL.json --rows ROWS.json --out PREDICTIONS.json

The STOP rule (`stop_rule`) compares each adversary's TOTAL on the probe pool, graded by the proof grid like any other
model, with the oracle's within the crown margin, which is the owner-signed criterion and a REQUIRED argument. Every
number a model holds is a fit parameter, not a physical value; the fitted parameters and digests are saved with it
(capture 3). The probe pool is never graded as an exam.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

INPUTS = (
    "length_mm",
    "width_mm",
    "thickness_mm",
    "rib_height_mm",
    "rib_thickness_mm",
    "relief_length_mm",
    "fillet_radius_mm",
    "load_angle_deg",
    "load_position_in_gap",
)
PAD_X = 5.0  # the 1.7 pad's length along x (the load arm is L - PAD_X / 2)
TRAIN_SCHEMA = "carbon.f08.train-scalars.v1"
MODEL_SCHEMA = "carbon.f08.closed-form-gate-model.v1"
CLIENT_ROWS = 10


class GateRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _sha(obj):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def section(row):
    """Plate W x t plus two ribs (tr x hr) at y = +-W/4: neutral-axis height and the two second moments (mm^4)."""
    W, t, hr, tr = (
        row["width_mm"],
        row["thickness_mm"],
        row["rib_height_mm"],
        row["rib_thickness_mm"],
    )
    a_plate, a_rib = W * t, tr * hr
    z_plate, z_rib = t / 2, t + hr / 2
    area = a_plate + 2 * a_rib
    zbar = (a_plate * z_plate + 2 * a_rib * z_rib) / area
    iy = (
        W * t**3 / 12
        + a_plate * (z_plate - zbar) ** 2
        + 2 * (tr * hr**3 / 12 + a_rib * (z_rib - zbar) ** 2)
    )
    iz = t * W**3 / 12 + 2 * (hr * tr**3 / 12 + a_rib * (W / 4) ** 2)
    return {"zbar": zbar, "iy": iy, "iz": iz}


def nominal_stress(row):
    """Beam-theory bending stress at the rib root for a 1 N load at angle theta (0 = +z, 90 = +y), MPa."""
    s = section(row)
    arm = row["length_mm"] - PAD_X / 2
    theta = math.radians(row["load_angle_deg"])
    fz, fy = math.cos(theta), math.sin(theta)
    top = row["thickness_mm"] + row["rib_height_mm"]
    sigma_z = abs(fz) * arm * max(top - s["zbar"], s["zbar"]) / s["iy"]
    sigma_y = (
        abs(fy) * arm * (row["width_mm"] / 4 + row["rib_thickness_mm"] / 2) / s["iz"]
    )
    return sigma_z + sigma_y


def structured_features(row):
    """[1, ln sigma_nom, ln(rf/t), ln(rf/tr), ln(hr/tr)]: the notch factor in the fillet's proportions."""
    rf, t, tr, hr = (
        row["fillet_radius_mm"],
        row["thickness_mm"],
        row["rib_thickness_mm"],
        row["rib_height_mm"],
    )
    return [
        1.0,
        math.log(nominal_stress(row)),
        math.log(rf / t),
        math.log(rf / tr),
        math.log(hr / tr),
    ]


def client_features(row):
    return [
        1.0,
        math.log(row["fillet_radius_mm"]),
        math.log(row["thickness_mm"]),
        math.log(row["rib_height_mm"]),
        math.log(row["width_mm"]),
        math.log(row["length_mm"]),
        math.cos(math.radians(row["load_angle_deg"])),
    ]


def _check_rows(rows):
    if not rows:
        raise GateRefused("no_rows")
    for row in rows:
        if any(not math.isfinite(float(row.get(k, math.nan))) for k in INPUTS):
            raise GateRefused("row_input_not_finite")


def _ridge(features, target, ridge):
    x = np.array(features, dtype=float)
    y = np.array(target, dtype=float)
    gram = x.T @ x + ridge * np.eye(x.shape[1])
    return np.linalg.solve(gram, x.T @ y).tolist()


def _spread_rows(rows, count):
    """Greedy max-min selection in normalised input space (deterministic: starts at the row nearest the centroid)."""
    matrix = np.array([[float(r[k]) for k in INPUTS] for r in rows])
    span = matrix.max(axis=0) - matrix.min(axis=0)
    span[span == 0] = 1.0
    unit = (matrix - matrix.min(axis=0)) / span
    chosen = [int(np.argmin(((unit - unit.mean(axis=0)) ** 2).sum(axis=1)))]
    while len(chosen) < min(count, len(rows)):
        distance = np.min([((unit - unit[i]) ** 2).sum(axis=1) for i in chosen], axis=0)
        chosen.append(int(np.argmax(distance)))
    return chosen


def fit(train, *, ridge=1e-6):
    """Fit both adversaries on a TRAIN document {"schema", "rows": [{inputs..., "peak_von_mises_mpa"}]}."""
    if train.get("schema") != TRAIN_SCHEMA:
        raise GateRefused("train_schema")
    rows = train["rows"]
    _check_rows(rows)
    if any(not row["peak_von_mises_mpa"] > 0 for row in rows):
        raise GateRefused("peak_not_positive")
    target = [math.log(row["peak_von_mises_mpa"]) for row in rows]
    structured = _ridge([structured_features(r) for r in rows], target, ridge)
    picked = _spread_rows(rows, CLIENT_ROWS)
    client = _ridge(
        [client_features(rows[i]) for i in picked],
        [target[i] for i in picked],
        max(ridge, 1e-3),
    )
    return {
        "schema": MODEL_SCHEMA,
        "train_sha256": _sha(train),
        "ridge": ridge,
        "structured": {"coefficients": structured},
        "client": {"coefficients": client, "rows": picked},
    }


def digest(model):
    return _sha(model)


# ------------------------------------------------ the PRIMARY output: worst-band DYNAMIC fillet stress (Validator ruling)

DYNAMIC_INPUTS = (*INPUTS, "damping_ratio", "E_mpa", "rho_t_per_mm3")
DYNAMIC_MODEL_SCHEMA = "carbon.f08.closed-form-gate-dynamic-model.v1"
BAND_HZ = (
    80.0,
    600.0,
)  # the registered band (f08_proof.BAND_HZ); read here so the gate has no solver import
FIRST_MODE_COEFFICIENT = 1.8751**2 / (2.0 * math.pi)  # cantilever first-mode constant


def first_mode_hz(row):
    """Euler-Bernoulli cantilever first bending frequency of the section (mm, t, N, s: sqrt(E I / (rho A L^4)) is rad/s),
    for the weaker bending axis: an adversary's estimate, not a physical claim."""
    s = section(row)
    area = (
        row["width_mm"] * row["thickness_mm"]
        + 2 * row["rib_thickness_mm"] * row["rib_height_mm"]
    )
    inertia = min(s["iy"], s["iz"])
    return FIRST_MODE_COEFFICIENT * math.sqrt(
        row["E_mpa"] * inertia / (row["rho_t_per_mm3"] * area * row["length_mm"] ** 4)
    )


def band_amplification(f1_hz, zeta, band=BAND_HZ):
    """Peak over the band of a single oscillator's dynamic amplification |1 / (1 - r^2 + 2 i zeta r)|, r = f / f1."""
    lo, hi = band
    if lo <= f1_hz <= hi:
        return 1.0 / (2.0 * zeta * math.sqrt(1.0 - zeta**2))  # the resonance peak
    edge = lo if f1_hz < lo else hi
    r = edge / f1_hz
    return 1.0 / math.hypot(1.0 - r * r, 2.0 * zeta * r)


def dynamic_features(row):
    """The modal-superposition adversary: the static notch features plus ln(band amplification) and ln(1 / f1^2)."""
    f1 = first_mode_hz(row)
    return [
        *structured_features(row),
        math.log(band_amplification(f1, row["damping_ratio"])),
        -2.0 * math.log(f1),
    ]


def fit_dynamic(train, *, ridge=1e-6):
    """Fit the structured modal-superposition adversary on rows carrying `dynamic_von_mises_mpa_per_n`."""
    if train.get("schema") != TRAIN_SCHEMA:
        raise GateRefused("train_schema")
    rows = train["rows"]
    if not rows:
        raise GateRefused("no_rows")
    for row in rows:
        if any(not math.isfinite(float(row.get(k, math.nan))) for k in DYNAMIC_INPUTS):
            raise GateRefused("row_input_not_finite")
        if not row.get("dynamic_von_mises_mpa_per_n", 0) > 0:
            raise GateRefused("peak_not_positive")
    target = [math.log(r["dynamic_von_mises_mpa_per_n"]) for r in rows]
    return {
        "schema": DYNAMIC_MODEL_SCHEMA,
        "train_sha256": _sha(train),
        "ridge": ridge,
        "band_hz": list(BAND_HZ),
        "structured": {
            "coefficients": _ridge([dynamic_features(r) for r in rows], target, ridge)
        },
    }


def predict_dynamic(model, rows):
    if model.get("schema") != DYNAMIC_MODEL_SCHEMA:
        raise GateRefused("model_schema")
    coef = np.array(model["structured"]["coefficients"])
    return [math.exp(float(np.dot(coef, dynamic_features(r)))) for r in rows]


def predict(model, rows):
    if model.get("schema") != MODEL_SCHEMA:
        raise GateRefused("model_schema")
    _check_rows(rows)
    s_coef = np.array(model["structured"]["coefficients"])
    c_coef = np.array(model["client"]["coefficients"])
    return {
        "structured": [
            math.exp(float(np.dot(s_coef, structured_features(r)))) for r in rows
        ],
        "client": [math.exp(float(np.dot(c_coef, client_features(r)))) for r in rows],
    }


def stop_rule(adversary_total, oracle_total, margin):
    """STOP when an adversary's graded total is within the crown margin of the oracle's. The margin is an owner value."""
    if margin in (None, "HUMAN_INPUT") or not margin > 0:
        raise GateRefused("margin_not_registered")
    gap = oracle_total - adversary_total
    return {"gap": gap, "margin": margin, "stop": gap <= margin}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fit")
    p.add_argument("--train", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--ridge", type=float, default=1e-6)
    q = sub.add_parser("predict")
    q.add_argument("--model", required=True)
    q.add_argument("--rows", required=True)
    q.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "fit":
        model = fit(json.loads(Path(args.train).read_text()), ridge=args.ridge)
        model["model_sha256"] = digest(model)
        Path(args.out).write_text(json.dumps(model, indent=1, sort_keys=True) + "\n")
    else:
        model = json.loads(Path(args.model).read_text())
        model.pop("model_sha256", None)
        rows = json.loads(Path(args.rows).read_text())["rows"]
        Path(args.out).write_text(
            json.dumps(predict(model, rows), indent=1, sort_keys=True) + "\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
