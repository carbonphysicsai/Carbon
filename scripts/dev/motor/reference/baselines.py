"""Calibrate the motor exam on TRAIN and score both baselines.

    python scripts/dev/motor/reference/baselines.py
        --train TRAIN_DIR --practice PRACTICE_DIR --private PRIVATE_DIR
        --out REPORT.json

Each DIR is a reference batch (`run_batch.py`) holding `records.jsonl`.

- **Exam.** Its gates are checked on every OK reference of every pool; its
  scales come from TRAIN only (`exam.scales_from_train`).
- **Closed-form baseline:** the textbook surface-PM model
  (`carbon.motor.analytic`): a flat curve at the linear-iron torque.
- **Learned baseline:** Gaussian-kernel ridge regression on the eight scaled
  inputs (`carbon.learned_baseline`), the 60-angle torque curve as its
  target, trained on TRAIN, its two hyperparameters chosen on PRACTICE. Its
  one clamp lifts a curve whose mean is negative to a zero mean, as the
  motoring quadrant requires. Nothing else of the physics.
- Every prediction is scored with a twin, so the paired-repeat gate runs.
  The report holds aggregates only: no private input or output leaves the
  private batch.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import fmean

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon import learned_baseline
from carbon.motor import analytic, domain, exam


def read(batch):
    return [
        json.loads(line)
        for line in (Path(batch) / "records.jsonl").read_text().splitlines()
        if line.strip()
    ]


def _x(rows):
    return learned_baseline.scale(rows, domain.INPUTS, domain.INPUT_BOUNDS)


def learned_predictor(model):
    def predict(inputs):
        curve = [float(v) for v in model.predict(_x([inputs]))[0]]
        mean = fmean(curve)
        if mean < 0:
            curve = [t - mean for t in curve]
        return {"torque_nm": curve}

    return predict


def closed_form(inputs):
    return {"torque_nm": analytic.predict(inputs)["torque_nm"]}


def score(predict, pool, scales):
    rows = []
    for ref in pool:
        if ref.get("status") != "OK":
            rows.append(exam.score_case(None, ref, scales))
            continue
        rows.append(
            exam.score_case(
                predict(ref["inputs"]), ref, scales, twin=predict(ref["inputs"])
            )
        )
    return exam.aggregate(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--practice", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    pools = {
        name: read(getattr(args, name)) for name in ("train", "practice", "private")
    }
    calibration = {name: exam.calibrate(pool) for name, pool in pools.items()}
    # The private pool's margins are extremes of hidden outputs: only its
    # count and that every gate held leave it.
    calibration["private"] = {
        "n_references": calibration["private"]["n_references"],
        "gates_hold": True,
    }
    scales = exam.scales_from_train(pools["train"])
    train = [r for r in pools["train"] if r["status"] == "OK"]

    def practice_score(model):
        result = score(learned_predictor(model), pools["practice"], scales)
        return result["score"] if result["eligible"] else None

    model, chosen = learned_baseline.select(
        _x([r["inputs"] for r in train]),
        np.array([r["outputs"]["torque_nm"] for r in train]),
        practice_score,
    )
    learned = learned_predictor(model)
    report = {
        "calibration": calibration,
        "scales": scales,
        "learned": {
            "model": "Gaussian-kernel ridge regression (carbon.learned_baseline)",
            "targets": "the 60-angle torque curve",
            "n_train": len(train),
            **chosen,
        },
        "scores": {
            name: {
                "closed_form": score(closed_form, pools[name], scales),
                "learned": score(learned, pools[name], scales),
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
