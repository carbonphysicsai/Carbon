"""The closed-form gate of Burst Thermal 3.0 (design step 7, as strengthened by OWNER-F02-V3-PICKS-01).

Before any pool is graded, the exam must not be solvable by a cheap structured fit. Two adversaries are fitted on TRAIN
(scalar outputs only: inputs -> peak) and predict a probe pool:

1. **Structured superposition (the strong one).** The die-top temperature is modelled as the physics says a nearly linear
   system behaves: the coolant plus a decaying start offset plus, per patch, a MODAL SUM of the Duhamel convolution of the
   total power waveform with M exponential modes. Mode amplitudes and rates are log-linear in (ln h, ln TIM thickness) (the
   "modes interpolated over (h, TIM)"), a per-mode patch coupling mixes the two patches by the split, and a first-order
   k(T) correction adds kappa (peak - coolant)^2. The peak is the maximum over time and the two patches. Everything in the
   waveform (rectangle to triangle, one or two pulses, the gap) enters through the convolution, with no per-shape fit.
2. **The client's way.** The 10 well-spread TRAIN rows a client might afford to run (a greedy max-min selection) and a ridge
   regression on a handful of features.

    python3 f02_closed_form_gate.py fit --train TRAIN.json --out MODEL.json [--modes 3] [--seed 0]
    python3 f02_closed_form_gate.py predict --model MODEL.json --rows ROWS.json --out PREDICTIONS.json
    python3 f02_closed_form_gate.py score --truth TRUTH.json --predictions PREDICTIONS.json --u 0.012 --within-u 5

The STOP rule (`stop_rule`) compares each adversary's TOTAL on the probe pool, graded by the proof grid like any other
model, with the oracle's within the crown margin (margin_N); the margin is the owner-signed criterion and is a required
argument. These adversaries predict the PEAK; the grid turns them into a graded model. The probe pool is NEVER graded as an
exam: it is not reused in any pack. Every value here is a fit parameter, not a physical value, and nothing is a score.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

try:
    from scripts.dev.reference_packages.elmer import f02_deck_v3 as deck
except ImportError:  # run as a payload script beside the deck
    import f02_deck_v3 as deck

INPUTS = (
    "peak_w",
    "on_time_s",
    "left_source_fraction",
    "ramp_fraction",
    "pulses",
    "gap_s",
    "coolant_c",
    "h_w_m2_k",
    "start_offset_c",
    "tim_thickness_mm",
)
TRAIN_SCHEMA = "carbon.f02.train-scalars.v1"
MODEL_SCHEMA = "carbon.f02.closed-form-gate-model.v1"
DT_S = 0.1  # the convolution grid: an adversary, not a reference
H_REF, TIM_REF = 2500.0, 0.2


class GateRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _row(inputs):
    missing = [
        name
        for name in INPUTS
        if name not in inputs or (name != "gap_s" and inputs[name] is None)
    ]
    if missing:
        raise GateRefused("inputs_incomplete:" + ",".join(missing))
    return {name: inputs[name] for name in INPUTS}


def waveform_power(inputs, grid):
    """The total power (W) on ``grid`` for a case's v3 waveform: the deck's own knots, linearly interpolated."""
    case = {
        "peak_w": inputs["peak_w"],
        "on_time_s": inputs["on_time_s"],
        "ramp_fraction": inputs["ramp_fraction"],
        "pulses": int(inputs["pulses"]),
        **({"gap_s": inputs["gap_s"]} if int(inputs["pulses"]) == 2 else {}),
    }
    knots = deck.schedule_v3(case)
    return np.interp(grid, [t for t, _ in knots], [w for _, w in knots])


def _logistic(x):
    return 1.0 / (1.0 + np.exp(-x))


def unpack(theta, modes):
    """``(alpha, beta, mix, kappa)``: alpha and beta are (modes, 3) log-linear coefficients (const, ln h, ln TIM)."""
    theta = np.asarray(theta, dtype=float)
    alpha = theta[: 3 * modes].reshape(modes, 3)
    beta = theta[3 * modes : 6 * modes].reshape(modes, 3)
    mix = _logistic(theta[6 * modes : 7 * modes])
    return alpha, beta, mix, float(theta[7 * modes])


def n_params(modes):
    return 7 * modes + 1


def predict_peaks(theta, modes, rows):
    """The structured-superposition peak (C) of every row, batched over rows and modes."""
    alpha, beta, mix, kappa = unpack(theta, modes)
    grid = np.arange(0.0, deck.HORIZON_S + DT_S / 2, DT_S)
    n = len(rows)
    xs = np.array(
        [
            [
                1.0,
                math.log(r["h_w_m2_k"] / H_REF),
                math.log(r["tim_thickness_mm"] / TIM_REF),
            ]
            for r in rows
        ]
    )
    amp = np.exp(xs @ alpha.T)  # (n, modes)
    lam = np.exp(xs @ beta.T)  # (n, modes)
    power = np.stack([waveform_power(r, grid) for r in rows])  # (n, steps)
    decay = np.exp(-lam * DT_S)  # (n, modes)
    gain_p = (1 - decay) / lam
    gain_b = DT_S / lam - (1 - decay) / lam**2
    share = np.array([r["left_source_fraction"] for r in rows])[:, None]
    drive_left = share + mix[None, :] * (1 - share)  # (n, modes)
    drive_right = (1 - share) + mix[None, :] * share
    y = np.zeros((n, modes))
    left = np.zeros((n, len(grid)))
    right = np.zeros((n, len(grid)))
    for k in range(len(grid) - 1):
        slope = (power[:, k + 1] - power[:, k]) / DT_S
        y = y * decay + power[:, k, None] * gain_p + slope[:, None] * gain_b
        left[:, k + 1] = (amp * drive_left * y).sum(axis=1)
        right[:, k + 1] = (amp * drive_right * y).sum(axis=1)
    coolant = np.array([r["coolant_c"] for r in rows])[:, None]
    offset = np.array([r["start_offset_c"] for r in rows])[:, None]
    start = offset * np.exp(-lam[:, :1] * grid[None, :])
    top = coolant + start + np.maximum(left, right)
    peak = top.max(axis=1)
    return peak + kappa * (peak - coolant[:, 0]) ** 2


def _initial(modes, rng):
    theta = np.zeros(n_params(modes))
    rates = np.geomspace(0.5, 0.02, modes)
    for m in range(modes):
        theta[3 * m] = math.log(
            0.2 * rates[m]
        )  # amplitude: a steady rise of ~0.2 C/W shared across the modes
        theta[3 * modes + 3 * m] = math.log(rates[m])
    theta[6 * modes : 7 * modes] = rng.normal(0.0, 0.5, modes)
    theta[7 * modes] = 0.0
    return theta + rng.normal(0.0, 0.05, theta.shape) * (np.abs(theta) > 0)


def fit_superposition(rows, peaks, *, modes=3, seed=0, starts=3):
    """Fit the structured-superposition model to TRAIN; the model document (best of ``starts`` seeded starts)."""
    from scipy.optimize import least_squares

    rows = [_row(r) for r in rows]
    target = np.asarray(peaks, dtype=float)
    if len(rows) < n_params(modes) // 2 or len(rows) != len(target):
        raise GateRefused("too_few_train_rows")
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(starts):
        start = _initial(modes, rng)

        def residual(theta):
            return predict_peaks(theta, modes, rows) - target

        found = least_squares(residual, start, method="trf", max_nfev=60, x_scale="jac")
        if best is None or found.cost < best.cost:
            best = found
    fit = np.sqrt(2 * best.cost / len(rows))
    return {
        "schema": MODEL_SCHEMA,
        "adversary": "structured_superposition",
        "modes": modes,
        "theta": [float(v) for v in best.x],
        "train_rmse_c": float(fit),
        "train_rows": len(rows),
        "seed": seed,
    }


def predict_superposition(model, rows):
    if model.get("adversary") != "structured_superposition":
        raise GateRefused("model_is_not_superposition")
    return predict_peaks(
        model["theta"], model["modes"], [_row(r) for r in rows]
    ).tolist()


# --- the client's way --------------------------------------------------------------------------------------------


def _features(rows):
    return np.array(
        [
            [
                1.0,
                r["peak_w"],
                r["on_time_s"],
                r["peak_w"] * r["on_time_s"],
                r["coolant_c"],
                r["start_offset_c"],
            ]
            for r in rows
        ]
    )


def client_selection(rows, count=10):
    """The ``count`` rows a client with that many solver runs would take: greedy max-min over the normalised inputs, from the
    row nearest the middle. Deterministic."""
    matrix = np.array([[float(_row(r)[name] or 0.0) for name in INPUTS] for r in rows])
    low, span = matrix.min(axis=0), np.ptp(matrix, axis=0)
    unit = (matrix - low) / np.where(span == 0, 1.0, span)
    chosen = [int(np.argmin(np.linalg.norm(unit - 0.5, axis=1)))]
    while len(chosen) < min(count, len(rows)):
        gap = np.min(
            np.linalg.norm(unit[:, None, :] - unit[chosen][None, :, :], axis=2), axis=1
        )
        gap[chosen] = -1
        chosen.append(int(np.argmax(gap)))
    return chosen


def fit_client(rows, peaks, *, count=10, ridge=1e-3):
    rows = [_row(r) for r in rows]
    chosen = client_selection(rows, count)
    x = _features([rows[i] for i in chosen])
    y = np.asarray(peaks, dtype=float)[chosen]
    scale = np.maximum(np.abs(x).max(axis=0), 1e-9)
    xs = x / scale
    weights = np.linalg.solve(xs.T @ xs + ridge * np.eye(xs.shape[1]), xs.T @ y)
    return {
        "schema": MODEL_SCHEMA,
        "adversary": "client_ten_runs",
        "rows_used": chosen,
        "scale": scale.tolist(),
        "weights": weights.tolist(),
    }


def predict_client(model, rows):
    if model.get("adversary") != "client_ten_runs":
        raise GateRefused("model_is_not_client")
    x = _features([_row(r) for r in rows]) / np.array(model["scale"])
    return (x @ np.array(model["weights"])).tolist()


# --- scoring and the stop rule ----------------------------------------------------------------------------------


def accuracy(truth, predicted, *, u, within_u):
    """RMSE and max error in C, the share of probe rows within ``within_u`` multiples of U (both required: the criterion is
    the owner's), and the same in U."""
    if len(truth) != len(predicted) or len(truth) == 0:
        raise GateRefused("probe_shape")
    if not (u > 0 and within_u > 0):
        raise GateRefused("criterion_required")
    err = np.abs(np.asarray(predicted, dtype=float) - np.asarray(truth, dtype=float))
    return {
        "rows": len(truth),
        "rmse_c": float(np.sqrt((err**2).mean())),
        "max_abs_c": float(err.max()),
        "share_within": float((err <= within_u * u).mean()),
        "rmse_u": float(np.sqrt((err**2).mean()) / u),
        "within_u": within_u,
    }


def stop_rule(adversary_totals, oracle_total, *, margin_n):
    """STOP when any adversary's graded total is within the crown margin of the oracle's on the probe pool.

    ``adversary_totals`` maps an adversary's name to its total on the probe pool (graded by the proof grid); ``margin_n`` is
    the owner-signed margin and has no default."""
    if (
        type(margin_n) not in (int, float)
        or isinstance(margin_n, bool)
        or not margin_n > 0
    ):
        raise GateRefused("margin_required")
    near = sorted(
        name
        for name, total in adversary_totals.items()
        if oracle_total - total <= margin_n
    )
    return {"stop": bool(near), "adversaries_within_margin": near, "margin_n": margin_n}


# --- the command ------------------------------------------------------------------------------------------------


def _train(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("schema") != TRAIN_SCHEMA:
        raise GateRefused("not_a_train_file")
    rows = [r["inputs"] for r in document["rows"]]
    return rows, [r["peak_top_c"] for r in document["rows"]]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f02_closed_form_gate")
    commands = parser.add_subparsers(dest="command", required=True)
    fit = commands.add_parser("fit")
    fit.add_argument("--train", type=Path, required=True)
    fit.add_argument("--out", type=Path, required=True)
    fit.add_argument("--modes", type=int, default=3)
    fit.add_argument("--seed", type=int, default=0)
    predict = commands.add_parser("predict")
    predict.add_argument("--model", type=Path, required=True)
    predict.add_argument("--rows", type=Path, required=True)
    predict.add_argument("--out", type=Path, required=True)
    score = commands.add_parser("score")
    score.add_argument("--truth", type=Path, required=True)
    score.add_argument("--predictions", type=Path, required=True)
    score.add_argument("--u", type=float, required=True)
    score.add_argument("--within-u", type=float, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "fit":
            rows, peaks = _train(args.train)
            models = {
                "structured_superposition": fit_superposition(
                    rows, peaks, modes=args.modes, seed=args.seed
                ),
                "client_ten_runs": fit_client(rows, peaks),
            }
            args.out.write_text(json.dumps(models, indent=1) + "\n", encoding="utf-8")
            print(json.dumps({k: v.get("train_rmse_c") for k, v in models.items()}))
        elif args.command == "predict":
            models = json.loads(args.model.read_text(encoding="utf-8"))
            rows = json.loads(args.rows.read_text(encoding="utf-8"))["rows"]
            out = {
                "structured_superposition": predict_superposition(
                    models["structured_superposition"], rows
                ),
                "client_ten_runs": predict_client(models["client_ten_runs"], rows),
            }
            args.out.write_text(json.dumps(out) + "\n", encoding="utf-8")
        else:
            truth = json.loads(args.truth.read_text(encoding="utf-8"))
            predicted = json.loads(args.predictions.read_text(encoding="utf-8"))
            print(
                json.dumps(
                    {
                        name: accuracy(truth, values, u=args.u, within_u=args.within_u)
                        for name, values in predicted.items()
                    },
                    indent=1,
                )
            )
    except GateRefused as refused:
        print(f"REFUSED: {refused.code}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
