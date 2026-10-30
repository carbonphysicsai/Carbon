"""The OFFICIAL pool path on the launch versions, with a crafted non-physical answer in the model's table.

`pool_exam.measure_pool` gates every pool row first: a Challenge answer its `derive` refuses also fails a registered
physics gate, so the grade is gated with D = 0 and neither the optimiser (`grade_set`) nor `agen_accuracy` is reached.
Real bindings (`pool_adapters.official_binding`: the Challenge's derive and gates); the pool, the bank rows and the
sealed `measure` are SYNTHETIC FIXTURES built from the version's reference rows (nothing here is production, no
custody material). Test Engineer, 2026-10-30; tests only.
"""

from __future__ import annotations

import math

import pytest

from carbon.scoring import pool_adapters as pa
from carbon.scoring import pool_exam as exam
from carbon.scoring import pool_gates, pool_grader, practice_dual, practice_grid
from carbon.scoring import pool_proof_suite as suite
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
]
POOL = 40


def _reference_rows(kind, version):
    chosen = practice_grid.adapter(kind, version)
    _bank, _public, _names, rows = practice_dual._rows(chosen)
    return [r for r in rows if r.get("reference_present") and r.get("reference")]


def _vary(kind, version, base, i):
    """Native row i of the fixture pool: a common scale (keeps every ordering law). Motor's ripple fraction is
    scale-free, so its curve also gets a per-slot offset; F08's frequency slots stay put (they have a band).
    """
    scale = 1.0 + 0.01 * i
    if kind == "f08":
        from carbon.scoring import f08_dual_pack

        names = list(f08_dual_pack._targets(version))
        return [
            v * scale if "mm_per_n" in name else v
            for name, v in zip(names, base, strict=True)
        ]
    return [
        v * scale + (0.01 * i * (1 + (j % 3)) if kind == "motor" and j % 2 else 0.0)
        for j, v in enumerate(base)
    ]


def _fixture(kind, version):
    binding = pa.official_binding(kind, version)
    chosen = pa.adapter(kind, version)
    template = _reference_rows(kind, version)[0]
    base = [float(v) for v in template["reference"]]
    to_model = binding.to_model_space or (lambda row: list(row))
    fixed = {n: template["inputs"][n] for n in chosen.condition_names}
    raws = [_vary(kind, version, base, i) for i in range(POOL)]
    designs = [
        [
            float(template["inputs"][n]) * (1.0 + 0.002 * (i + 1))
            for n in chosen.design_names
        ]
        for i in range(POOL)
    ]
    rows = [
        {**fixed, **dict(zip(chosen.design_names, d, strict=True))} for d in designs
    ]
    # the fixture's own truths come from the model-space rows, as the grader's derive reads them
    truths = [
        chosen.derive(r, to_model(raw)) for r, raw in zip(rows, raws, strict=True)
    ]
    assert all(t is not None for t in truths), "the fixture's own truths must derive"
    objective = chosen.objective
    values = sorted(t[objective] for t in truths)
    limits = (
        pool_grader.Limit(
            objective,
            "<=" if chosen.sense == "min" else ">=",
            values[len(values) // 2],
        ),
    )
    box = tuple(
        (min(d[k] for d in designs), max(d[k] for d in designs) + 1e-9)
        for k in range(len(chosen.design_names))
    )
    spec = pool_grader.build_target(
        target_id="fixture",
        conditions={"target_id": "fixture", "fixed": fixed},
        outputs=chosen.outputs,
        objective=objective,
        sense=chosen.sense,
        limits=limits,
        u={name: 1e-9 for name in chosen.outputs},
        box=box,
        designs=designs,
        truths=truths,
        agen=range(POOL - 8, POOL),
        start=tuple(0.5 for _ in box),
        seed=7,
    )
    return binding, chosen, template, spec, [to_model(r) for r in raws], to_model


def _grade(kind, version, corrupt=None, where=None):
    binding, chosen, template, spec, raws, to_model = _fixture(kind, version)
    pool_rows = pool_gates.pool_rows(binding, [spec])
    sealed = [
        {
            "case_id": f"sealed:{i}",
            "inputs": dict(r["inputs"]),
            "reference": [float(v) for v in r["reference"]],
            "cohort": "sealed",
        }
        for i, r in enumerate(_reference_rows(kind, version)[:6])
    ]
    pool = [dict(r, cohort=exam.POOL_COHORT) for r in pool_rows]
    outputs = [to_model(r["reference"]) for r in sealed] + [
        raws[spec.origin[int(r["case_id"].split(":")[1])]] for r in pool_rows
    ]
    if corrupt is not None:
        index = spec.agen[0] if where == "agen_slice" else spec.queryable[0]
        outputs[len(sealed) + index] = corrupt(template, to_model)

    def base_measure(*, bank_rows, outputs, repeats, **_kw):
        return {
            "A": 0.9,
            "A_legs": {"A_acc": 0.9},
            "gates": {"finite": True, "paired_repeat": True},
            "design_fidelity": {"C": 0.9},
        }

    policies = suite.Policies(
        optimizer=pool_grader.OptimizerPolicy(budget=20, sigma0=0.3, population=None),
        honesty=pool_grader.HonestyPolicy(scale=5.0, reduction="max"),
        agen_scales={name: 1.0 for name in chosen.outputs},
        a_rule={"kind": "min"},
        c_rule={"kind": "min"},
    )
    return exam.measure_pool(
        binding=binding,
        sets=((spec,),),
        policies=policies,
        bank_rows=sealed + pool,
        outputs=outputs,
        repeats=[outputs, outputs],
        base_measure=base_measure,
        base_arguments={},
        speed_call_seconds=toy.FAST,
        ceiling_seconds=toy.CEILING,
    )


def _crafted(kind):
    """Non-physical raw rows in the model's space for this Challenge, each a different refusal."""

    def cooling_cold(template, to_model):
        native = [float(v) for v in template["reference"]]
        # a face colder than the inlet: the row decodes, then fails the decision step
        native[1] = template["inputs"]["inlet_c"] - 1.0
        return to_model(native)

    def torque(template, _to_model):
        return [-abs(float(v)) - 1.0 for v in template["reference"]]

    def nan_row(template, _to_model):
        return [math.nan] * len(template["reference"])

    def short_row(template, _to_model):
        return [float(v) for v in template["reference"]][:-1]

    return {
        "motor": [("negative_mean_torque", torque), ("nan", nan_row)],
        "cooling": [
            ("face_below_inlet", cooling_cold),
            ("nan", nan_row),
            ("wrong_width", short_row),
        ],
        "f02": [
            ("nan", lambda t, m: [math.nan]),
            ("wrong_width", lambda t, m: [1.0, 2.0]),
        ],
        "f08": [("nan", nan_row), ("wrong_width", short_row)],
    }[kind]


@pytest.mark.parametrize("kind,version", VERSIONS)
@pytest.mark.parametrize("where", ["queryable", "agen_slice"])
def test_a_refused_answer_is_gated_with_no_exception_and_never_reaches_the_a_gen_path(
    kind, version, where, monkeypatch
):
    clean = _grade(kind, version)
    assert (
        clean["gates"][exam.PHYSICS_GATE] is True and clean["D"] > 0.0
    ), "the fixture must grade when the table is clean, or the gate below proves nothing"

    def never(*_args, **_kwargs):
        raise AssertionError("a gated grade must not reach the optimiser or A_gen")

    monkeypatch.setattr(pool_grader, "agen_accuracy", never)
    monkeypatch.setattr(pool_grader, "grade_set", never)
    for label, craft in _crafted(kind):
        measured = _grade(kind, version, corrupt=craft, where=where)
        assert measured["gates"][exam.PHYSICS_GATE] is False, (kind, label)
        assert measured["D"] == 0.0, (kind, label)
        assert measured["pool"]["physics_failed"], (kind, label)
