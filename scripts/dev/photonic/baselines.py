"""Fit the learned baseline on TRAIN and score both baselines through the exam.

    python scripts/dev/photonic/baselines.py PUBLIC_DIR --private PRIVATE.jsonl
        --out REPORT.json

- **Closed-form:** the effective index method (`carbon.photonic.analytic`).
- **Learned:** ridge regression on tensor Chebyshev features of the two
  inputs, one fit per output value, trained on TRAIN only. Its degree and
  ridge are chosen on PRACTICE from a small declared grid; the private pool
  is touched once, to score. A generic surrogate on purpose: it knows the
  inputs' box and nothing of the physics, so it measures what the TRAIN
  pool alone teaches.

The exam is calibrated on every pool first (its gates must hold for each
reference). Each prediction is scored with a twin, the same model's second
evaluation of the same inputs, so the paired-repeat gate is exercised. The
report holds aggregates only: no private input or output leaves PRIVATE.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.photonic import analytic, domain, exam

DEGREES = (4, 6, 8, 10, 12)
RIDGES = (1e-12, 1e-9, 1e-6)


def read(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def _scaled(inputs):
    x = []
    for name in domain.INPUTS:
        low, high = domain.INPUT_BOUNDS[name]
        x.append(2 * (inputs[name] - low) / (high - low) - 1)
    return x


def features(rows, degree):
    x = np.array([_scaled(r) for r in rows])
    tg = np.polynomial.chebyshev.chebvander(x[:, 0], degree)
    tl = np.polynomial.chebyshev.chebvander(x[:, 1], degree)
    return np.einsum("ni,nj->nij", tg, tl).reshape(len(rows), -1)


def targets(records):
    return np.array(
        [
            r["outputs"]["cross_power"] + r["outputs"]["common_phase_rad"]
            for r in records
        ]
    )


class Learned:
    def __init__(self, train, degree, ridge):
        self.degree = degree
        a = features([r["inputs"] for r in train], degree)
        y = targets(train)
        self.coef = np.linalg.solve(a.T @ a + ridge * np.eye(a.shape[1]), a.T @ y)

    def predict(self, inputs):
        values = (features([inputs], self.degree) @ self.coef)[0]
        n = len(domain.WAVELENGTHS_UM)
        # A power fraction: the model's own clamp, as any rebuilt model may do.
        cross = [min(max(float(v), 0.0), 1.0) for v in values[:n]]
        return {
            "cross_power": cross,
            "common_phase_rad": [float(v) for v in values[n:]],
        }


def score(model, pool):
    rows = []
    for ref in pool:
        prediction = model(ref["inputs"])
        rows.append(exam.score_case(prediction, ref, twin=model(ref["inputs"])))
    return exam.aggregate(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("public", type=Path)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    pools = {
        "train": read(args.public / "train.jsonl"),
        "practice": read(args.public / "practice.jsonl"),
        "private": read(args.private),
    }
    calibration = {name: exam.calibrate(pool) for name, pool in pools.items()}
    # The private pool's margins are extremes of hidden outputs: only its
    # count and that every gate held leave it.
    calibration["private"] = {
        "n_references": calibration["private"]["n_references"],
        "gates_hold": True,
    }
    train = [r for r in pools["train"] if r["status"] == "OK"]
    selection = []
    for degree in DEGREES:
        for ridge in RIDGES:
            model = Learned(train, degree, ridge)
            result = score(model.predict, pools["practice"])
            selection.append(
                {
                    "degree": degree,
                    "ridge": ridge,
                    "practice_score": result["score"],
                    "eligible": result["eligible"],
                }
            )
    best = min(
        (s for s in selection if s["eligible"]), key=lambda s: s["practice_score"]
    )
    learned = Learned(train, best["degree"], best["ridge"])
    report = {
        "calibration": calibration,
        "learned": {
            "model": "ridge regression on tensor Chebyshev features of the scaled inputs",
            "selection": selection,
            "chosen": {"degree": best["degree"], "ridge": best["ridge"]},
            "n_train": len(train),
        },
        "scores": {
            name: {
                "closed_form": score(analytic.predict, pools[name]),
                "learned": score(learned.predict, pools[name]),
            }
            for name in ("practice", "private")
        },
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {k: {m: v[m]["score"] for m in v} for k, v in report["scores"].items()}
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
