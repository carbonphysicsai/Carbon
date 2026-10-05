"""Measure cooling's practice equivalence margin (OWNER-GRAPHITE-TEST-WAVE-06 §1).

    python -m scripts.dev.cold_plate.equivalence_margin --out RESULT.json

For testing only. Cooling's promotion rule borrows battery's unit-free
comparison settings and needs a relative equivalence margin measured from the
seed-to-seed spread on cooling's public PRACTICE set.

**Battery's documented method** (OD-2). Source: `scripts/dev/exam_design/campaign.py`
and `docs/development/evidence/exam-design-2026-09-24/analysis.json`. The
margin is 2 x the largest seed-to-seed relative SD (sample SD, ddof = 1) of the
large-sample score among the reconstructed recipes. Battery's recipes were
stochastic MLPs, three seeds each.

**Why cooling needs an adaptation.** Cooling's reference construction is the
registered KRR (length 8.0, ridge 1e-6). It is a deterministic closed-form fit
(`carbon/cold_plate/recipes.py`), and no seed affects it. Applied literally,
battery's rule gives a margin of exactly 0; that value is recorded. A zero
margin would count every difference as real.

**The Test Lead's delegated decision under WAVE-06 §1 (2026-10-05).**
- **Primary seed definition: a bootstrap of public TRAIN.** Resample with
  replacement at the full size n (`random.Random(seed).choices`), refit the
  KRR, and score it on the full PRACTICE set with the registered TRAIN scales
  held fixed. Thirty seeds. The margin is 2 x the relative SD (ddof 1).
- **Sensitivity.** Reproducible subsamples without replacement at fractions
  0.8, 0.9 and 0.95. Heavily overlapping subsamples understate the variance,
  which is why they are not the primary.
- **Stochastic recipes.** If cooling's Level 0 contract registers a stochastic
  family, the literal OD-2 analogue is computed as well: 2 recipes x 3
  training seeds, largest relative SD x 2. The registered margin is the max of
  the two values. When only deterministic families are registered, the
  bootstrap value is used, and the result says so.
- **Precheck.** A full-TRAIN fit must reproduce the registered practice score
  exactly.

Public data only (TRAIN and PRACTICE), CPU only, deterministic given the
seeds. No private pool or reference is read, and nothing is promoted here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from carbon.cold_plate import contracts, exam, recipes

POOLS = ROOT / "docs" / "development" / "evidence" / "cold-plate-pools-v1"
SETTINGS = {"length": 8.0, "ridge": 1e-6}
FRACTIONS = (0.8, 0.9, 0.95)
SEEDS = 30
#: Families whose fit is deterministic given its data and settings.
DETERMINISTIC_FAMILIES = {"kernel_ridge"}
SCHEMA = "carbon.cold-plate.practice-equivalence-margin.v1"


def _records(name):
    path = POOLS / name
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def practice_result(train, practice, scales):
    model = recipes.build("kernel_ridge", SETTINGS, train)
    rows = [
        exam.score_case(model.predict(record["inputs"]), record, scales)
        for record in practice
    ]
    return exam.aggregate(rows)


def _spread(values):
    mean = statistics.fmean(values)
    sd = statistics.stdev(values)
    return {"mean": mean, "sd": sd, "rel_sd": sd / mean, "margin_rel": 2 * sd / mean}


def _seeded(train, practice, scales, seeds, draw):
    scores, important = [], []
    for seed in range(seeds):
        result = practice_result(draw(random.Random(seed)), practice, scales)
        scores.append(result["score"])
        important.append(result["important_score"])
    return {
        "seeds": seeds,
        "practice_scores": scores,
        "score": _spread(scores),
        "important_score": _spread(important),
    }


def measure(seeds=SEEDS, fractions=FRACTIONS):
    train = [r for r in _records("train.jsonl") if r.get("status") == "OK"]
    practice = _records("practice.jsonl")
    baselines = json.loads((POOLS / "baselines.json").read_text(encoding="utf-8"))
    scales = baselines["scales"]
    if exam.scales_from_train(train) != scales:
        raise SystemExit("registered TRAIN scales do not reproduce")
    full = practice_result(train, practice, scales)
    registered = baselines["scores"]["practice"]["learned"]["score"]
    if abs(full["score"] - registered) > 1e-12:
        raise SystemExit(
            "full-TRAIN KRR does not reproduce the registered practice score"
        )
    repeat = practice_result(train, practice, scales)
    n = len(train)
    bootstrap = _seeded(
        train, practice, scales, seeds, lambda rng: rng.choices(train, k=n)
    )
    subsamples = {}
    for fraction in fractions:
        size = round(fraction * n)
        subsamples[str(fraction)] = {
            "train_size": size,
            **_seeded(
                train, practice, scales, seeds, lambda rng, s=size: rng.sample(train, s)
            ),
        }
    families = [
        name
        for name, _ in contracts.rebuildable_families(contracts.COLD_PLATE_CHALLENGE)
    ]
    stochastic = sorted(set(families) - DETERMINISTIC_FAMILIES)
    if stochastic:
        raise SystemExit(
            f"stochastic families registered ({stochastic}): compute the OD-2 analogue first"
        )
    chosen = bootstrap["score"]["margin_rel"]
    return {
        "schema": SCHEMA,
        "authority": (
            "OWNER-GRAPHITE-TEST-WAVE-06 section 1 (testing only); method per the "
            "Test Lead's delegated decision, 2026-10-05"
        ),
        "reference_construction": {"family": "kernel_ridge", **SETTINGS},
        "inputs": {
            "train_sha256": _sha256(POOLS / "train.jsonl"),
            "practice_sha256": _sha256(POOLS / "practice.jsonl"),
            "baselines_sha256": _sha256(POOLS / "baselines.json"),
            "train_ok": n,
            "practice_cases": len(practice),
        },
        "full_train_practice": {
            "score": full["score"],
            "important_score": full["important_score"],
            "n_scored": full["n_scored"],
            "n_important": full["n_important"],
            "reproduces_registered_score": True,
        },
        "battery_method": {
            "source": (
                "scripts/dev/exam_design/campaign.py; "
                "docs/development/evidence/exam-design-2026-09-24/analysis.json"
            ),
            "rule": (
                "2 x the largest seed-to-seed relative SD of the large-sample "
                "score among the reconstructed recipes"
            ),
            "battery_value": 0.056993107446249414,
        },
        "literal_battery_rule_on_cooling": {
            "basis": "the registered KRR has no seed; a refit is identical",
            "refit_identical": repeat == full,
            "margin_rel": 0.0 if repeat == full else None,
        },
        "bootstrap": {"train_size": n, "with_replacement": True, **bootstrap},
        "subsample_sensitivity": subsamples,
        "stochastic_recipes": {
            "registered_families": families,
            "stochastic_families": stochastic,
            "od2_analogue_margin_rel": None,
            "status": "NONE_REGISTERED: only deterministic kernel_ridge is rebuildable",
        },
        "equivalence_margin_rel": chosen,
        "chosen_from": "bootstrap (max of bootstrap and stochastic-recipe values; no stochastic family)",
        "claims": "DEVELOPMENT testing value only; not a production threshold",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seeds", type=int, default=SEEDS)
    args = parser.parse_args(argv)
    result = measure(seeds=args.seeds)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "equivalence_margin_rel": result["equivalence_margin_rel"],
                "bootstrap_rel_sd": result["bootstrap"]["score"]["rel_sd"],
                "subsample_margins": {
                    f: v["score"]["margin_rel"]
                    for f, v in result["subsample_sensitivity"].items()
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
