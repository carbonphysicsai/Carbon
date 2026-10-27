"""The official pool grade of ONE submitted model: the link between the receiver's single inference and
the version's score (Validator V8_RULINGS section 10; spec POOL_GRADER_AND_PROOF_SUITE_SPEC section 2 and
section 9.3 option (b)).

Where it sits on the sealed route (each arrow is a module that exists; this file is the middle one):

    direct_receiver (sealed pack, `evaluation_pack_sealed`) -> lean_recipe_retention (rebuild + ONE inference
    over every exam row, twice for the paired repeat) -> physical_dual_pack.grade (calls the adapter's
    `measure`) -> THIS MODULE's `measure_pool` -> `score(benchmark, pack)` -> bound evidence ->
    bank_promotion.consider_private (KOTH, set level through pack_set_grading) -> winner_eligibility.lean_promotion
    -> testnet_winner_publication (weights).

The exam rows are the sealed A cases and probes (graded by the Challenge's own sealed v2 `measure`, so A, C and
the native gates are unchanged) plus every pool row of every target (queryable and A_gen), marked with the cohort
`POOL_COHORT`. The model sees inputs only. This module turns that one table of answers into

- A: the sealed grader's A, with A_gen entering by the owner's rule (per set, then the mean over sets);
- D: the pool grader's set D (seeded CMA-ES replayed on the table; no solver), capped by C, mean over sets;
- the mandatory gates: the sealed grader's native gates, `physics_pool` (the Challenge's physics gates on EVERY
  pool answer) and `speed` (the single-call median rule below), names only;
- the same `{"A", "D", "gates", "decision_outcome", "A_legs", "design_fidelity"}` an adapter's `measure` returns,
  so the existing dual-pack `score` composes the total (0.5 A + 0.5 D) and nothing else changes.

Speed (Validator section 10): the gate times SINGLE-DESIGN calls, never a batched average. A custody-seeded random
sample of `SPEED_SAMPLE` (20) sealed pool rows is each asked in its own inference call on the grading class; the
gate passes when the MEDIAN per-call seconds is at most the registered ceiling (`challenge_registry.speed_gate`).
`speed_sample` picks the rows; the calls themselves are the receiver's (see ``Open links`` in the report).

Every constant the owner picks (`policies`) is a required argument. Nothing here names a Challenge.
"""

from __future__ import annotations

import hashlib
import math
import random
import statistics
from dataclasses import replace

from carbon.scoring import (
    pool_gates,
    pool_grader,
    pool_plugin,
    pool_serving,
    probe_design,
)
from carbon.scoring import pool_proof_suite as suite

#: The bank-row cohort of a pool row (queryable or A_gen); every other row is the sealed grader's.
POOL_COHORT = probe_design.POOL_COHORT
#: The mandatory gates this module adds to the sealed grader's native ones.
PHYSICS_GATE = "physics_pool"
SPEED_GATE = "speed"
SPEED_SAMPLE = 20
OUTCOME_POOL = "POOL_GRADED"


class ExamRefused(ValueError):
    """The exam material or the answers cannot give a sound grade: the Challenge's wiring or the receiver's
    infrastructure, never a candidate's score."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise ExamRefused(code)


def split_rows(bank_rows):
    """(sealed rows, pool rows, their positions) of a bank whose pool rows carry cohort `POOL_COHORT`."""
    sealed = [i for i, r in enumerate(bank_rows) if r.get("cohort") != POOL_COHORT]
    pool = [i for i, r in enumerate(bank_rows) if r.get("cohort") == POOL_COHORT]
    _require(sealed and pool, "exam_bank_needs_sealed_rows_and_pool_rows")
    return sealed, pool


def speed_sample(pool_row_count, *, seed, count=SPEED_SAMPLE):
    """Indices (sorted) of the sealed pool rows timed in single calls: a custody-seeded draw, per grade. ``seed``
    is custody's bytes for this grade; it is never the miner's and never reused across grades.
    """
    _require(
        type(seed) is bytes and len(seed) >= 16, "speed_seed_must_be_custody_bytes"
    )
    _require(
        type(count) is int and 0 < count <= pool_row_count,
        "speed_sample_larger_than_the_pool",
    )
    rng = random.Random(int.from_bytes(hashlib.sha256(seed).digest(), "big"))
    return sorted(rng.sample(range(pool_row_count), count))


def single_call_speed_gate(call_seconds, *, ceiling_seconds, count=SPEED_SAMPLE):
    """The speed gate on single-design calls: `count` positive finite per-call seconds, MEDIAN against the
    registered ceiling. A batched average is never an input."""
    _require(
        type(call_seconds) in (list, tuple) and len(call_seconds) == count,
        "speed_needs_one_timing_per_sampled_row",
    )
    _require(
        all(
            type(s) in (int, float) and math.isfinite(s) and s > 0 for s in call_seconds
        ),
        "speed_timings_must_be_positive_and_finite",
    )
    _require(
        type(ceiling_seconds) in (int, float)
        and math.isfinite(ceiling_seconds)
        and ceiling_seconds > 0,
        "speed_ceiling_must_be_positive_and_finite",
    )
    median = statistics.median(call_seconds)
    passed = median <= ceiling_seconds
    return {
        "passed": passed,
        "code": None if passed else pool_gates.SPEED_CODE,
        "median_seconds": median,
        "max_seconds": max(call_seconds),
        "calls": len(call_seconds),
        "ceiling_seconds_per_design": ceiling_seconds,
    }


def table_server(rows, raw, input_names):
    """`serve(rows)` over the model's ONE table of answers: exact-input lookup, a missing row refused."""
    _require(len(rows) == len(raw), "one_answer_per_exam_row")
    document = {
        "input_names": list(input_names),
        "state_digest": None,
        "rows": [
            {"inputs": [float(r[name]) for name in input_names], "raw": list(p)}
            for r, p in zip(rows, raw, strict=True)
        ],
    }
    return pool_serving.TableServer(document, input_names)


def measure_pool(
    *,
    binding,
    sets,
    policies,
    bank_rows,
    outputs,
    repeats,
    base_measure,
    base_arguments,
    speed_call_seconds,
    ceiling_seconds,
    input_dtype=None,
    a_multiplier=1.0,
):
    """The adapter-shaped `measure` of a pool-graded version for one model.

    ``bank_rows`` / ``outputs`` / ``repeats`` are the receiver's: every exam row, the model's raw answers to each,
    and the two inferences of the paired repeat. ``sets`` are the version's `pool_grader` target sets (custody
    material); ``policies`` a `pool_proof_suite.Policies` (the owner's constants); ``base_measure`` the Challenge's
    sealed v2 `measure` with ``base_arguments`` (definition, limits, objective, train_raw, names).
    """
    _require(
        len(bank_rows) == len(outputs)
        and all(len(r) == len(bank_rows) for r in repeats),
        "one_answer_per_exam_row",
    )
    # The delivered query holds the pool rows quantised to the bank's dtype (`pool_version.rows_from_material`);
    # the grader asks the model's table about the same rounded rows, never about the unrounded designs.
    quantize = _quantizer(input_dtype)
    sealed, pool = split_rows(bank_rows)
    sealed_rows = [bank_rows[i] for i in sealed]
    base = base_measure(
        bank_rows=sealed_rows,
        outputs=[outputs[i] for i in sealed],
        repeats=[[r[i] for i in sealed] for r in repeats],
        **base_arguments,
    )
    base_gates = dict(base.get("gates") or {})
    _require(base_gates, "sealed_measure_returned_no_gates")
    _require(
        PHYSICS_GATE not in base_gates and SPEED_GATE not in base_gates,
        "native_gate_names_collide_with_the_pool_gates",
    )
    all_specs = [spec for group in sets for spec in group]
    _require(all_specs, "exam_has_no_targets")
    # The owner's C rule is `min` (D = min(D, C)); the dual pack's own total then equals each set's TOP.
    _require(policies.c_rule.get("kind") == "min", "official_c_rule_must_be_min")
    # The model's one table over EVERY exam row; every lookup below is a read of it.
    table = table_server([r["inputs"] for r in bank_rows], outputs, binding.input_names)

    def serve(rows):
        return table([quantize(row) for row in rows])

    submitted = replace(binding, serve_good=serve)
    pool_row_dicts = pool_gates.pool_rows(submitted, all_specs)
    answered = {
        tuple(quantize(r["inputs"])[n] for n in binding.input_names)
        for r in pool_row_dicts
    }
    held = {tuple(bank_rows[i]["inputs"][n] for n in binding.input_names) for i in pool}
    _require(answered == held, "exam_pool_rows_differ_from_the_targets_pools")
    raw_pool = serve([r["inputs"] for r in pool_row_dicts])
    physics_failed = pool_gates.failed_gates(submitted, pool_row_dicts, raw_pool)
    speed = single_call_speed_gate(speed_call_seconds, ceiling_seconds=ceiling_seconds)
    gates = {
        **base_gates,
        PHYSICS_GATE: not physics_failed,
        SPEED_GATE: speed["passed"],
    }
    if base.get("A") is None or not all(gates.values()):
        # A failed mandatory gate gives no score; the dual pack reads only the gate verdicts.
        return {
            **base,
            "A": base.get("A"),
            "D": 0.0,
            "gates": gates,
            "decision_outcome": base.get("decision_outcome", OUTCOME_POOL),
            "pool": {"physics_failed": physics_failed, "speed": speed},
        }
    legs = {
        "A": base["A"],
        "C": (base.get("design_fidelity") or {}).get("C"),
        "gates_ok": True,
        "A_legs": dict(base.get("A_legs") or {}),
    }
    _require(
        type(legs["C"]) in (int, float) and math.isfinite(legs["C"]),
        "sealed_measure_gave_no_finite_C",
    )
    plugin = suite.ProofPlugin(
        sets=tuple(tuple(group) for group in sets),
        fresh_set=None,
        train_box=binding.train_box,
        train_model=_refused("train_model"),
        default_model=_refused("default_model"),
        floor_model=_refused("floor_model"),
        good_model=pool_plugin.pool_predictor(submitted, serve),
        legs=lambda descriptor, specs: legs,
    )
    # The owner's A-leg tightening (the sheet's A multiplier; 1 = the sealed grader's registered scale): each A leg
    # 1 / (1 + x) becomes 1 / (1 + m x) before the legs are averaged, exactly as the proof grid scored the row.
    _require(
        type(a_multiplier) in (int, float)
        and math.isfinite(a_multiplier)
        and a_multiplier > 0,
        "a_multiplier_must_be_positive",
    )
    from carbon.scoring.pool_proof_grid import tighten

    a_legs = legs["A_legs"]
    a_bank = (
        statistics.fmean(tighten(v, a_multiplier) for v in a_legs.values())
        if a_legs
        else tighten(legs["A"], a_multiplier)
    )
    descriptor = {"kind": "good"}
    per_set = [
        suite.score_specs(plugin, specs, descriptor, policies, all_specs)
        for specs in plugin.sets
    ]
    a_values, d_values, reasons, a_gen = [], [], set(), []
    for _total, grade, gen, _legs in per_set:
        a_gen.append(gen)
        a_values.append(pool_grader.combine_a(a_bank, gen, policies.a_rule))
        # D as the total sees it: capped by C, so the dual pack's own 0.5 A + 0.5 D is each set's TOP.
        d_values.append(min(grade.d, legs["C"]))
        reasons.update(grade.public()["reasons"])
    return {
        **base,
        "A": statistics.fmean(a_values),
        "D": statistics.fmean(d_values),
        "gates": gates,
        "decision_outcome": OUTCOME_POOL,
        "pool": {
            "physics_failed": physics_failed,
            "speed": speed,
            "reasons": sorted(reasons),
            "sets": len(per_set),
            "set_totals": [t for t, _g, _a, _l in per_set],
        },
    }


def _quantizer(input_dtype):
    """``row -> row`` rounded to ``input_dtype`` (None: unchanged)."""
    if input_dtype is None:
        return lambda row: row
    import numpy as np

    kind = np.dtype(input_dtype)
    return lambda row: {name: float(kind.type(value)) for name, value in row.items()}


def _refused(name):
    def refuse(conditions, designs):
        raise ExamRefused(f"{name}_is_not_part_of_the_official_grade")

    return refuse


def public(measured):
    """All that may leave custody for a pool-graded measure: the gate verdict NAMES and the closed reason codes.
    Never a pick, a per-target value, a pool point, a timing or a query."""
    failed = sorted(name for name, ok in measured["gates"].items() if not ok)
    return {
        "status": pool_gates.GATE_FAILED if failed else "SCORED",
        "gates": failed,
        "reasons": list((measured.get("pool") or {}).get("reasons", [])),
    }


__all__ = [
    "OUTCOME_POOL",
    "PHYSICS_GATE",
    "POOL_COHORT",
    "SPEED_GATE",
    "SPEED_SAMPLE",
    "ExamRefused",
    "measure_pool",
    "public",
    "single_call_speed_gate",
    "speed_sample",
    "split_rows",
    "table_server",
]
