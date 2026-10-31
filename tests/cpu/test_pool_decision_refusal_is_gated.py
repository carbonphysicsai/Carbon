"""A model answer that a Challenge's `derive` refuses can never reach the pool grader's scoring on the official path.

`pool_grader.grade_target` scores a None prediction as `prediction_invalid` (D = 0), but `pool_grader.agen_accuracy`
raises `PoolRefused("agen_prediction_invalid")` on one. The official route is safe only because every answer `derive`
refuses ALSO fails a registered physics gate, and `pool_exam.measure_pool` returns on a failed gate before any scoring.
These tests pin both halves (Test Engineer, 2026-10-30; no carbon/ change):

1. for every launch Challenge, over crafted and extreme FINITE or malformed rows: `derive` is None  =>  the gate
   names a failure, and neither `derive` nor the gate raises;
2. through `pool_exam.measure_pool` on the toy Challenge: a refused answer that the gate ALSO fails is a gated D = 0
   grade with no exception; a refused queried design that the gate would pass is `prediction_invalid`.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from carbon.scoring import pool_adapters as pa
from carbon.scoring import pool_exam as exam
from carbon.scoring import practice_dual, practice_grid
from tests.cpu import test_pool_exam as toy

VERSIONS = [
    ("motor", "1.4"),
    ("motor", "1.5"),
    ("cooling", "1.4"),
    ("cooling", "1.6"),
    ("f02", "2.4"),
    ("f02", "2.5"),
    ("f08", "1.5"),
    ("f08", "1.7"),
]  # 2.5 and 1.7 are the launch versions; practice_grid has an adapter for each


def _rows(kind, version):
    chosen = practice_grid.adapter(kind, version)
    _bank, _public, _names, rows = practice_dual._rows(chosen)
    return [r for r in rows if r.get("reference_present") and r.get("reference")]


def _crafted(kind, version, reference):
    """Finite and malformed raw rows built around one real reference row, including the extremes."""
    width = len(reference)
    base = [float(v) for v in reference]
    rng = np.random.default_rng(20261030)
    rows = [
        base,
        base[:-1],
        base + [0.0],
        [math.nan] * width,
        [math.inf] * width,
        [-math.inf] + base[1:],
        [0.0] * width,
        [-1.0] * width,
        [1e300] * width,
        [-1e300] * width,
        [1e-300] * width,
        [-abs(v) - 1.0 for v in base],
        [0.0] + base[1:],
        base[:-1] + [-1.0],
        base[:-1] + [0.0],
    ]
    for scale in (1e-6, 1e-2, 1.0, 1e2, 1e6, 1e150):
        rows.append(list(rng.normal(0.0, scale, width)))
        rows.append([v * scale for v in base])
    for index in range(width):
        cold = list(base)
        cold[index] = -1e6
        rows.append(cold)
        hot = list(base)
        hot[index] = 1e300
        rows.append(hot)
    return rows


@pytest.mark.parametrize("kind,version", VERSIONS)
def test_every_answer_derive_refuses_also_fails_a_registered_gate_and_nothing_raises(
    kind, version
):
    chosen = pa.adapter(kind, version, mass_of=lambda design: 0.3)
    gates = pa.physics_gates(kind, version)
    reference = _rows(kind, version)[0]
    refused = 0
    for raw in _crafted(kind, version, reference["reference"]):
        # a model answer in the model's space (Cooling 1.4 answers encoded): the crafted rows are model-space
        derived = chosen.derive(reference["inputs"], raw)
        failed = gates.failed(reference["inputs"], raw)
        if derived is None:
            refused += 1
            assert failed, f"{kind}: derive refused a row no gate names"
    assert refused > 0


def _toy_grade(index_of, sentinel_passes_gate):
    the_sets = toy.sets()
    spec = the_sets[0][0]
    bad = tuple(float(v) for v in spec.designs[index_of(spec)])

    def serve(rows):
        out = toy.good_serve(rows)
        return [
            [12345.0 if sentinel_passes_gate else -1.0, 0.0]
            if (r["x"], r["y"]) == bad
            else o
            for r, o in zip(rows, out, strict=True)
        ]

    def derive(row, raw):
        return None if raw[0] in (12345.0, -1.0) else {"f": raw[0], "g": raw[1]}

    binding = dataclasses.replace(toy.toy_binding(serve), derive=derive)
    rows = toy.exam_rows(the_sets)
    outputs = toy.answers(rows, serve)
    return exam.measure_pool(
        binding=binding,
        sets=the_sets,
        policies=toy.POLICIES,
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=toy.fake_measure,
        base_arguments=toy.ARGUMENTS,
        speed_call_seconds=toy.FAST,
        ceiling_seconds=toy.CEILING,
    )


@pytest.mark.parametrize("where", ["agen_slice", "queryable"])
def test_a_refused_answer_the_gate_also_fails_is_a_gated_zero_not_an_exception(where):
    pick = (
        (lambda spec: next(iter(spec.agen)))
        if where == "agen_slice"
        else (lambda spec: min(spec.queryable))
    )
    measured = _toy_grade(pick, sentinel_passes_gate=False)
    assert measured["D"] == 0.0
    assert measured["gates"][exam.PHYSICS_GATE] is False
    assert measured["pool"]["physics_failed"]


def test_a_refused_queried_design_the_gate_would_pass_is_prediction_invalid():
    measured = _toy_grade(lambda s: min(s.queryable), sentinel_passes_gate=True)
    assert "prediction_invalid" in measured["pool"]["reasons"]


def test_a_refused_a_gen_design_the_gate_would_pass_raises_so_the_invariant_above_is_load_bearing():
    """Documents the one raising edge: only reachable if a Challenge's derive refuses what its gates pass."""
    with pytest.raises(Exception, match="agen_prediction_invalid"):
        _toy_grade(lambda s: next(iter(s.agen)), sentinel_passes_gate=True)
