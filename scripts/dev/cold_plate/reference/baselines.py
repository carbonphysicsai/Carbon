"""Calibrate the cold plate exam on TRAIN and score both baselines.

    python scripts/dev/cold_plate/reference/baselines.py
        --train TRAIN_DIR --practice PRACTICE_DIR --private PRIVATE_DIR
        --out REPORT.json

Each DIR is a reference batch (`run_batch.py`) holding `records.jsonl`.

- **Exam.** Its gates are checked on every OK reference of every pool
  (`exam.calibrate` refuses a gate a sound reference fails); its scales come
  from TRAIN only (`exam.scales_from_train`).
- **Closed-form baseline:** `carbon.cold_plate.analytic`.
- **Learned baseline:** Gaussian-kernel ridge regression on the nine scaled
  inputs (`carbon.learned_baseline`), trained on TRAIN, its two
  hyperparameters chosen on PRACTICE. It learns the outputs as the positive
  quantities they are, log(peak - inlet), log(profile - inlet) and
  log(pressure drop), so its predictions keep the signs every reference has;
  its one clamp lifts the peak to the hottest profile segment if it falls
  below it. Nothing else of the physics.
- Every prediction is scored with a twin (a second evaluation), so the
  paired-repeat gate runs. The report holds aggregates only: no private
  input or output leaves the private batch.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon import learned_baseline
from carbon.cold_plate import analytic, domain, exam


def read(batch):
    return [
        json.loads(line)
        for line in (Path(batch) / "records.jsonl").read_text().splitlines()
        if line.strip()
    ]


def _x(rows):
    return learned_baseline.scale(rows, domain.INPUTS, domain.INPUT_BOUNDS)


def _y(records):
    rows = []
    for r in records:
        inlet, out = r["inputs"]["inlet_c"], r["outputs"]
        rows.append(
            [math.log(out["peak_c"] - inlet)]
            + [math.log(t - inlet) for t in out["profile_c"]]
            + [math.log(out["pressure_drop_pa"])]
        )
    return np.array(rows)


def learned_predictor(model):
    def predict(inputs):
        values = model.predict(_x([inputs]))[0]
        inlet = inputs["inlet_c"]
        profile = [inlet + math.exp(v) for v in values[1:-1]]
        peak = max(inlet + math.exp(values[0]), max(profile))
        return {
            "peak_c": peak,
            "profile_c": profile,
            "pressure_drop_pa": math.exp(values[-1]),
        }

    return predict


def closed_form(inputs):
    out = analytic.predict(inputs)
    return {k: out[k] for k in ("peak_c", "profile_c", "pressure_drop_pa")}


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
        _x([r["inputs"] for r in train]), _y(train), practice_score
    )
    learned = learned_predictor(model)
    report = {
        "calibration": calibration,
        "scales": scales,
        "learned": {
            "model": "Gaussian-kernel ridge regression (carbon.learned_baseline)",
            "targets": "log(peak - inlet), log(profile - inlet), log(pressure drop)",
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
