"""Carbon-side error calibration (OWNER-CONFIDENCE-MIDDLE-PATH-01): custody only, never a score input.

Every number is a SYNTHETIC value on a toy two-variable problem.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import pytest

from carbon.scoring import pool_calibration as cal
from carbon.scoring import pool_grader
from carbon.scoring.pool_grader import (
    HonestyPolicy,
    Limit,
    OptimizerPolicy,
    build_target,
)

U = 0.01
SHELL = {"mode": "designs", "inputs": ((0.1, 0.2, 0.0, 0.8), (0.1, 0.2, 0.0, 0.8))}


def truths_of(points):
    return [
        {
            "f": x + y,
            "g": x * x + y * y,
            "e": x * y,
            "h": 0.1 + 0.2 * (x * x + y * y) / 2.0,
        }
        for x, y in points
    ]


def target(name, seed, extended=False):
    rng = random.Random(seed)
    if extended:
        points = [(rng.uniform(0.6, 1.0), rng.uniform(0.6, 1.0)) for _ in range(100)]
        bound = 1.2
    else:
        points = [(rng.random(), rng.random()) for _ in range(60)]
        points += [
            (0.63 + rng.uniform(-0.12, 0.12), 0.63 + rng.uniform(-0.12, 0.12))
            for _ in range(40)
        ]
        bound = 0.8
    return build_target(
        target_id=name,
        conditions={"case": name},
        outputs=("f", "g", "e", "h"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", bound),),
        # f and g: an absolute U; e: exactly computed (U = 0); h: relative (3 % of the row's own value)
        u={"f": U, "g": U, "e": 0.0, "h": {"relative": 0.03}},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=[list(p) for p in points],
        truths=truths_of(points),
        agen=range(92, 100),
        start=(0.5, 0.5),
        seed=seed,
        shell=SHELL if extended else None,
    )


def model(specs, err_in, err_out):
    table = {}
    for spec in specs:
        for design, truth in zip(spec.designs, spec.truths, strict=True):
            table[(spec.conditions["case"], design)] = (spec, truth)

    def predict(conditions, designs):
        out = []
        for design in designs:
            spec, truth = table[(conditions["case"], tuple(design))]
            k = err_out if spec.extended else err_in
            out.append(
                {
                    "f": truth["f"] + k * U,
                    "g": truth["g"] - k * U,
                    "e": truth["e"],
                    "h": truth["h"] * (1.0 + 0.03 * k),
                }
            )
        return out

    return predict


def test_quantiles_and_the_exact_upper_bound_on_a_miss_rate():
    values = [0.0, 1.0, 2.0, 3.0, 4.0]
    assert cal.quantile(values, 0.5) == 2.0 and cal.quantile(values, 0.0) == 0.0
    assert cal.quantile(values, 0.99) == pytest.approx(3.96)
    # No misses in n rows: about 3 / n (the exact bound is 1 - 0.05 ** (1 / n)).
    assert cal.miss_rate_upper_95(0, 200) == pytest.approx(
        1 - 0.05 ** (1 / 200), rel=1e-9
    )
    assert cal.miss_rate_upper_95(0, 200) == pytest.approx(3 / 200, rel=0.2)
    # One miss in ten: the textbook one-sided 95 % upper bound 0.3942.
    assert cal.miss_rate_upper_95(1, 10) == pytest.approx(0.3942, abs=1e-3)
    assert cal.miss_rate_upper_95(10, 10) == 1.0
    assert cal.miss_rate_upper_95(2, 100) < cal.miss_rate_upper_95(5, 100)
    with pytest.raises(cal.CalibrationRefused):
        cal.miss_rate_upper_95(3, 2)


def test_errors_are_summarised_per_region_and_output_with_a_per_row_u_and_gate_rows_counted_apart():
    registered = target("r", 1)
    extended = target("x", 2, extended=True)
    predict = model([registered, extended], err_in=2.0, err_out=6.0)
    report = cal.calibrate_errors(
        [registered, extended],
        predict,
        exam_version="exam-v-test",
        model_state_digest="sha256:" + "a" * 64,
        band_u=4.0,
        gate_failed={"r": {0, 1, 2}},
    )
    assert report["custody_only"] is True and report["schema"] == cal.SCHEMA
    assert report["exam_version"] == "exam-v-test" and report["band_u"] == 4.0
    assert report["calibration_pool_digests"] == sorted(
        [registered.digest, extended.digest]
    )
    rows_in, rows_out = len(registered.designs), len(extended.designs)
    low, high = report["regions"]["in_range"], report["regions"]["out_of_range"]
    assert low["rows"] == rows_in and low["gate_failed_rows"] == 3
    assert high["rows"] == rows_out and high["gate_failed_rows"] == 0
    # f is off by k U exactly: in range 2 U (within the band 4 U), out of range 6 U (beyond it).
    f_in, f_out = low["outputs"]["f"], high["outputs"]["f"]
    assert f_in["n"] == rows_in - 3 and f_in["quantiles"]["p95"] == pytest.approx(2.0)
    assert f_in["misses_beyond_band"] == 0 and f_in["miss_rate_upper_95"] < 0.05
    assert f_out["max"] == pytest.approx(6.0)
    assert f_out["misses_beyond_band"] == rows_out
    assert f_out["miss_rate_upper_95"] == 1.0
    # h is off by k x 3 % of its own value and its U is 3 % of its own value: the error is k U on every row.
    assert low["outputs"]["h"]["max"] == pytest.approx(2.0)
    assert high["outputs"]["h"]["max"] == pytest.approx(6.0)
    # An exactly computed output (U = 0) has no model error to calibrate and is not reported.
    assert "e" not in low["outputs"] and "e" not in high["outputs"]


def test_a_calibration_needs_its_bindings_and_a_sound_table():
    spec = target("r", 1)
    predict = model([spec], 0.0, 0.0)
    ok = {"exam_version": "v", "model_state_digest": "sha256:x", "band_u": 3.0}
    for bad in (
        {"exam_version": ""},
        {"model_state_digest": ""},
        {"band_u": 0.0},
        {"band_u": float("nan")},
    ):
        with pytest.raises(cal.CalibrationRefused):
            cal.calibrate_errors([spec], predict, **{**ok, **bad})
    with pytest.raises(cal.CalibrationRefused, match="no_pools"):
        cal.calibrate_errors([], predict, **ok)
    with pytest.raises(cal.CalibrationRefused, match="one_answer_per_row"):
        cal.calibrate_errors([spec], lambda c, d: [], **ok)
    with pytest.raises(cal.CalibrationRefused, match="every_predicted_output"):
        cal.calibrate_errors([spec], lambda c, d: [{"f": 1.0}] * len(d), **ok)


def test_no_calibration_field_reaches_a_miner_or_public_surface():
    spec = build_target(
        target_id="p",
        conditions={"case": "p"},
        outputs=("f", "g"),
        objective="f",
        sense="max",
        limits=(Limit("g", "<=", 0.8),),
        u={"f": U, "g": U},
        box=((0.0, 1.0), (0.0, 1.0)),
        designs=[[0.5 + 0.004 * i, 0.5] for i in range(40)],
        truths=[{"f": 1.0 + 0.004 * i, "g": 0.5 + 0.0001 * i} for i in range(40)],
        agen=(),
        start=(0.5, 0.5),
        seed=1,
        public=True,
    )
    table = {tuple(d): t for d, t in zip(spec.designs, spec.truths, strict=True)}

    def predict(conditions, designs):
        return [dict(table[tuple(d)]) for d in designs]

    wide = OptimizerPolicy(budget=30, sigma0=0.3, population=None)
    honesty = HonestyPolicy(scale=5.0, reduction="max")
    exam_public = pool_grader.grade_set([spec], predict, wide, honesty).public()
    practice = pool_grader.practice_report(
        [spec],
        predict,
        wide,
        honesty,
        a=1.0,
        c=1.0,
        a_rule={"kind": "min"},
        agen_scales={"f": 0.1, "g": 0.1},
        c_rule={"kind": "min"},
    )

    def keys(value):
        if isinstance(value, dict):
            for key, inner in value.items():
                yield str(key)
                yield from keys(inner)
        elif isinstance(value, (list, tuple)):
            for inner in value:
                yield from keys(inner)

    seen = set(keys(exam_public)) | set(keys(practice))
    assert not seen & set(cal.CUSTODY_FIELDS)
    assert not any("calibrat" in k or "quantile" in k for k in seen)
    # And no miner-facing code or guide so much as imports it.
    root = Path(cal.__file__).resolve().parents[2]
    for surface in (
        "scripts/dev/miner_launchpad",
        "carbon/miner_mcp",
        "carbon/development_session",
    ):
        for path in (root / surface).rglob("*.py"):
            assert "pool_calibration" not in path.read_text(encoding="utf-8"), path
    assert "pool_calibration" not in (root / "docs/MINING.md").read_text(
        encoding="utf-8"
    )
    assert math.isfinite(cal.quantile([1.0], 0.5))
