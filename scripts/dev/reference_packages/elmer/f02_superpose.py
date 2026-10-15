"""f02 linear-superposition predictor (planning and diagnostics only).

    python3 f02_superpose.py STEPS_DIR BASELINES_DIR OUT.json [--solved DIR ...]

The f02 stack is linear: constant properties, perfect contact, Robin
cooling. In a context, the die-top temperature for any schedule is the
context's 20 W transient baseline plus the burst excess convolved with the
step response of its cooling pair and split (Duhamel). This predicts the
peak of every menu-v2 action from 4 step solves and 8 baseline solves. The
die-top value is the spatial maximum of each field, so the prediction (sum
of maxima) bounds the true maximum from above.

It is a PLANNING tool: it chooses where to look, sizes the bank and checks
NONE_FEASIBLE contexts. It is never reference truth; every decision value
comes from the solved deck. `--solved` compares predictions with solved
menu primaries and reports the error.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f02_deck as deck
import f02_menu as menu

DT = 0.01
GRID = np.arange(0.0, deck.HORIZON_S + DT / 2, DT)


def curve(case_dir):
    cols, rows = deck.read_scalars(case_dir)
    i_top = next(i for i, c in enumerate(cols) if c.startswith("boundary max"))
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    t = [0.0] + [r[0] for r in rows]
    v = [meta["case"]["initial_c"]] + [r[i_top] - 273.15 for r in rows]
    return np.interp(GRID, t, v)


def load(steps_dir, baselines_dir):
    steps, bases = {}, {}
    for d in sorted(Path(steps_dir).glob("step-*")):
        meta = json.loads((d / "deck.json").read_text())
        c = meta["case"]
        key = (c["h_w_m2_k"], c["left_source_fraction"])
        steps[key] = (curve(d) - c["coolant_c"]) / c["peak_w"]
    for d in sorted(Path(baselines_dir).glob("c*-baseline")):
        if (d / "scalars.dat").exists():
            bases[d.name[: -len("-baseline")]] = curve(d)
    return steps, bases


def excess(case):
    knots = deck.schedule(case)
    t = [k[0] for k in knots]
    p = [k[1] - deck.BASE_W for k in knots]
    return np.interp(GRID, t, p)


def predict(case, steps, bases):
    """Predicted die-top maximum curve on GRID."""
    ctx = f"c{case['coolant_c']:g}-i{case['initial_c']:g}-s{case['left_source_fraction']:g}"
    s = steps[(case["h_w_m2_k"], case["left_source_fraction"])]
    dp = np.diff(excess(case), prepend=0.0)
    # Linear convolution by FFT (equal to np.convolve to rounding; O(n log n)).
    n = 2 * len(GRID)
    theta = np.fft.irfft(np.fft.rfft(dp, n) * np.fft.rfft(s, n), n)[: len(GRID)]
    return bases[ctx] + theta


def peak(case, steps, bases):
    c = predict(case, steps, bases)
    i = int(np.argmax(c))
    return float(c[i]), float(GRID[i])


def menu_table(steps, bases):
    out = {}
    for ctx, base in menu.contexts():
        for p, d in itertools.product(menu.PEAKS_W, menu.ON_TIMES_S):
            pk, at = peak({**base, "peak_w": p, "on_time_s": d}, steps, bases)
            out[menu.case_name(ctx, p, d)] = {"predicted_peak_c": pk, "at_s": at}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f02_superpose")
    parser.add_argument("steps", type=Path)
    parser.add_argument("baselines", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--solved", type=Path, nargs="*", default=[])
    args = parser.parse_args(argv)
    steps, bases = load(args.steps, args.baselines)
    table = menu_table(steps, bases)
    errors = []
    for root in args.solved:
        for d in sorted(root.glob("*-primary")):
            if d.name in table and (d / "scalars.dat").exists():
                solved = deck.observe(d)["peak_top_c"]
                table[d.name]["solved_peak_c"] = solved
                errors.append(table[d.name]["predicted_peak_c"] - solved)
    doc = {
        "schema": "carbon.f02-superposition.prediction.v1",
        "role": "PLANNING_ONLY_NOT_REFERENCE_TRUTH",
        "step_regimes": sorted(f"h{h:g}-s{s:g}" for h, s in steps),
        "baselines": sorted(bases),
        "compared": len(errors),
        "error_c": None
        if not errors
        else {
            "min": min(errors),
            "max": max(errors),
            "mean_abs": sum(abs(e) for e in errors) / len(errors),
        },
        "menu": table,
    }
    args.out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in doc.items() if k != "menu"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
