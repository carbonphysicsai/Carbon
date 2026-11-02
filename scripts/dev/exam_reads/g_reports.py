"""G1-G9 REPORTS (STRONG_CHECKS_SPEC_20261102, the generalisation axes), from one checks-1-3 run. CUSTODY scratch; aggregates only.

Each axis is either MEASURED from what that run already graded (G1, G2, G3, G7, G8, G9) or a typed ``NOT_RUN`` naming the rows it
needs (G4, G5, G6: they need models trained on held-out regimes, variant cases or TRAIN fractions, which a checks run does not
build). Owner values (the G2 distance threshold, the G3 class floor) are inputs; unset, the count against them is null. No bar,
no pass/fail.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import checks_report as report
import q3_q8_whatif as reads

SCHEMA = "carbon.exam-reads.g-reports.v1"
INPUT_KEYS = frozenset({"g2_threshold", "g3_floor_n", "g8_practice_inputs"})
#: G2 / G8 distance: TRAIN's own per-column min-max scaling, then the max-norm (G2: "max-norm distance from every TRAIN point").
MAXNORM_RULE = "train_minmax_maxnorm"
#: A probe point this close to a TRAIN or practice row (max-norm, scaled) is reported as a duplicate for G8.
DUPLICATE_EPS = 1e-12

_need = reads._need


def load_inputs(path):
    """``{"g2_threshold": float or null, "g3_floor_n": int or null, "g8_practice_inputs": {npy, columns, sha256} or null}``."""
    if path is None:
        return {k: None for k in INPUT_KEYS}
    doc = json.loads(Path(path).read_bytes())
    _need(type(doc) is dict and set(doc) == INPUT_KEYS, "g_inputs_shape")
    t = doc["g2_threshold"]
    _need(
        t is None or (type(t) in (int, float) and not isinstance(t, bool) and t > 0),
        "g2_threshold",
    )
    f = doc["g3_floor_n"]
    _need(f is None or (type(f) is int and f >= 1), "g3_floor_n")
    p = doc["g8_practice_inputs"]
    _need(
        p is None
        or (
            type(p) is dict
            and set(p) == {"npy", "columns", "sha256"}
            and type(p["columns"]) is list
        ),
        "g8_practice_inputs",
    )
    return doc


def _matrix(spec):
    import numpy as np

    raw = Path(spec["npy"]).read_bytes()
    _need(
        hashlib.sha256(raw).hexdigest() == spec["sha256"].removeprefix("sha256:"),
        "g8_practice_inputs_sha256",
    )
    matrix = np.asarray(np.load(io.BytesIO(raw), allow_pickle=False), dtype=float)
    _need(
        matrix.ndim == 2 and matrix.shape[1] == len(spec["columns"]),
        "g8_practice_inputs_shape",
    )
    return matrix


def maxnorm_distances(points, reference, train, columns):
    """Each point's max-norm distance (TRAIN-scaled) to the nearest row of ``reference``, by class: ``{class: [d, ...]}``."""
    import numpy as np

    lo, hi = train.min(axis=0), train.max(axis=0)
    width = np.where(hi > lo, hi - lo, 1.0)
    scaled = (reference - lo) / width
    by = {}
    for cls, inputs in points:
        _need(set(columns) <= set(inputs), "g_point_lacks_a_train_column")
        x = (np.array([float(inputs[c]) for c in columns]) - lo) / width
        by.setdefault(cls, []).append(float(np.abs(scaled - x).max(axis=1).min()))
    return by


def _not_run(needs):
    return {"status": "NOT_RUN", "needs": needs}


def build(checks, sink, g_inputs):
    """The G1-G9 document from a checks-1-3 report (``checks``) and its run's ``sink`` (`checks_report.run_report`)."""
    classes = {row["class"]: row for row in checks["classes"]}
    points, train, columns = sink["points"], sink["train"], sink["columns"]
    to_train = maxnorm_distances(points, train, train, columns)
    threshold = g_inputs["g2_threshold"]
    floor_n = g_inputs["g3_floor_n"]
    ood = [c for c in classes if c != report.IN_TRAIN]
    g8 = {
        "train": {
            cls: {
                "min_maxnorm": min(v),
                "duplicates": sum(d <= DUPLICATE_EPS for d in v),
            }
            for cls, v in sorted(to_train.items())
        },
        "practice": None,
    }
    if g_inputs["g8_practice_inputs"] is not None:
        spec = g_inputs["g8_practice_inputs"]
        _need(spec["columns"] == columns, "g8_practice_columns_differ_from_train")
        practice = maxnorm_distances(points, _matrix(spec), train, columns)
        g8["practice"] = {
            cls: {
                "min_maxnorm": min(v),
                "duplicates": sum(d <= DUPLICATE_EPS for d in v),
            }
            for cls, v in sorted(practice.items())
        }
    gates = {
        c["role"]: {"status": c["status"], "gates": c["gates"]}
        for c in checks["contenders"]
    }
    return {
        "schema": SCHEMA,
        "challenge": checks["challenge"],
        "version": checks["version"],
        "scratch_only": True,
        "checks_report_run_digest": checks["run_digest"],
        "distance_rule": MAXNORM_RULE,
        "G1_extrapolation": {
            cls: checks["checks"]["1_shortcuts_out_of_range"].get(cls) for cls in ood
        },
        "G2_interpolation_holes": {
            "threshold": threshold,
            "by_class": {
                cls: {
                    "n": len(v),
                    "min_maxnorm": min(v),
                    "max_maxnorm": max(v),
                    "at_or_beyond_threshold": (
                        None if threshold is None else sum(d >= threshold for d in v)
                    ),
                }
                for cls, v in sorted(to_train.items())
            },
        },
        "G3_hard_regimes": {
            "floor_n": floor_n,
            "by_class": {
                cls: {
                    "n": row["n"],
                    "below_floor": None if floor_n is None else row["n"] < floor_n,
                }
                for cls, row in classes.items()
            },
        },
        "G4_leave_regime_out": _not_run(
            "default-model rows trained with each registered regime label held out"
        ),
        "G5_nearby_variants": _not_run("a registered variant set and its solved cases"),
        "G6_learning_curve": _not_run(
            "default-model and best-shortcut rows trained on 25 / 50 / 100 % of TRAIN"
        ),
        "G7_seed_robustness": {
            "registered_rebuild_noise": checks["margin_n"],
            "score_step": checks["score_step"],
        },
        "G8_no_leakage": g8,
        "G9_physical_validity": {
            "gate_failed": {
                cls: row["gate_failed"] for cls, row in sorted(classes.items())
            },
            "gate_failed_scope": checks["gate_failed_scope"],
            "contenders": gates,
        },
        "bars": "owner values: measured only, no pass/fail",
    }
