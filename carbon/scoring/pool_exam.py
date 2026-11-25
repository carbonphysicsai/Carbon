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

import contextlib
import contextvars
import copy
import hashlib
import json
import math
import random
import statistics
from dataclasses import replace

from carbon.scoring import (
    case_errors,
    pool_gates,
    pool_grader,
    pool_physics_score,
    pool_plugin,
    pool_serving,
    probe_design,
)
from carbon.scoring import pool_proof_suite as suite

#: The bank-row cohort of a pool row (queryable or A_gen); every other row is the sealed grader's.
POOL_COHORT = probe_design.POOL_COHORT
#: The mandatory gates this module adds to the sealed grader's native ones.
PHYSICS_GATE = "physics_pool"
#: The inner name (private, in "pool".physics_failed) of an A_gen slice answer the validity gates refuse.
AGEN_VALIDITY_GATE = "agen_prediction_validity"
#: The in-range accuracy gate of a version with physics scoring (`pool_physics_score`); absent for every other version.
ACCURACY_GATE = pool_physics_score.ACCURACY_GATE
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


#: The capture staged for the grade being produced in THIS context (`staged_capture`): set by the receiver around its producer
#: call, never through a producer file (as `pool_menu.staged_rowcheck`: producer bytes never move).
_STAGED_CAPTURE = contextvars.ContextVar("carbon_pool_capture", default=None)


@contextlib.contextmanager
def staged_capture():
    """Yield a dict the FIRST pool measure called inside this block fills as its ``capture`` argument would be filled
    (``accuracy``, ``menu``, a gated grade's ``se_basis``), so the receiver keeps the official grade's own custody accuracy
    record and SE basis without measuring the model a second time (door-code item 5, 19 Nov 2026). Write-only: the grade
    is the same with or without it.

    One difference: a scored grade's SE basis is NOT derived inside the measure. The block holds ``se_basis_of``, a
    function of the grade's own values that returns it, called by the receiver AFTER the producer call: so the extra work
    never runs under a lock the produce holds (`pair_read_bound`'s process-wide lock), and its failure can never change
    or refuse the grade. Cleared on exit. A ``capture`` passed explicitly (the operator's SE tools) is filled as before
    and the stage is ignored.
    """
    found = {}
    token = _STAGED_CAPTURE.set(found)
    try:
        yield found
    finally:
        _STAGED_CAPTURE.reset(token)


def split_rows(bank_rows, *, pool_only=False):
    """(sealed rows, pool rows, their positions) of a bank whose pool rows carry cohort `POOL_COHORT`. Every version needs
    both; a REGISTERED pool-only version (P1) needs pool rows and holds no sealed row.
    """
    sealed = [i for i, r in enumerate(bank_rows) if r.get("cohort") != POOL_COHORT]
    pool = [i for i, r in enumerate(bank_rows) if r.get("cohort") == POOL_COHORT]
    if pool_only:
        _require(not sealed, "pool_only_bank_holds_sealed_rows")
        _require(pool, "exam_bank_needs_pool_rows")
    else:
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
    speed_outputs_match=True,
    capture=None,
    coverage_plan=None,
    coverage_plan_sums=None,
    variant_starts=None,
    scoring_cells=None,
    in_range_cases=None,
    menu_tasks=None,
    menu_key=None,
    menu_rowcheck=None,
    menu_rowcheck_key=None,
    confirmation_sets=None,
):
    """The adapter-shaped `measure` of a pool-graded version for one model.

    ``capture`` (a dict, operator-only, default None) receives the per-target decomposition of the final total
    (`se_basis`) for the exam-total standard error; it is never part of the returned dict.

    ``bank_rows`` / ``outputs`` / ``repeats`` are the receiver's: every exam row, the model's raw answers to each,
    and the two inferences of the paired repeat. ``sets`` are the version's `pool_grader` target sets (custody
    material); ``policies`` a `pool_proof_suite.Policies` (the owner's constants); ``base_measure`` the Challenge's
    sealed v2 `measure` with ``base_arguments`` (definition, limits, objective, train_raw, names).

    ``coverage_plan`` / ``coverage_plan_sums`` are a NEW version's sealed class-map document and its plan package's
    SHA256SUMS text (`attach_coverage_plan`); None for every registered version, whose policies stay as given.

    ``variant_starts`` is a NEW version's sealed per-target variant starts (`attach_variant_starts`), required exactly
    when its registered optimizer policy carries a ``variant_rule``; None for every registered version.

    ``scoring_cells`` is a NEW version's sealed scoring-cell document (`attach_physics`), required exactly when its
    policies carry a physics rule (`pool_physics_score`); None for every registered version, whose result is unchanged.
    ``in_range_cases`` is its sealed in-range case set, required exactly when the rule registers one.
    ``menu_tasks`` / ``menu_key`` are a NEW version's sealed menu tasks (`pool_menu.load_tasks`) and the validator host's
    menu draw key, required exactly when its policies carry a ``menu`` rule: D is then the menu D (`pool_menu.score`)
    and the custody record lands under ``["pool"]["menu"]`` (and ``capture["menu"]``). None for every other version.
    ``menu_rowcheck`` (``{"positions", "outputs"}``: a FRESH model instance's raw answers to a keyed subset of the bank in
    a keyed order, `pool_menu.rowcheck_plan`) and ``menu_rowcheck_key`` are required with it (Carbon Validator-B 7 Nov
    (1)); answers that differ from the graded ones beyond the registered tolerance give D = 0, MODEL_ROW_DEPENDENT.
    With a physics rule A is the family value (`pool_physics_score.family_value`, per set), and the grade adds the
    mandatory gate `ACCURACY_GATE` (in-range accuracy, pass/fail) and the custody
    accuracy record under ``["pool"]["accuracy"]`` (and ``capture["accuracy"]``); `public` never carries the record.

    With no ``capture`` given, a receiver's `staged_capture` block (still empty: only the first measure) is filled instead,
    its scored SE basis deferred to ``se_basis_of`` (see `staged_capture`).

    ``confirmation_sets`` (owner CROWN-CONFIRMATION-SET, 25 Nov 2026) are a NEW version's sealed confirmation sets
    (`pool_version.confirmation_sets`), required exactly when its policies register a ``confirmation``; None for every
    other version, whose grade is unchanged. Their designs are bank pool rows like any other (answered in the same single
    inference, nothing marks them), but they enter NO part of the grade: not A, D, the total, a gate, the record or the
    returned dict. Their number (the version's physics family value on those rows, mean over the confirmation sets) is
    kept in ``capture["confirmation"]`` only, for the crown (`crown_official.confirm`); a gate-failed grade keeps none.
    """
    staged = capture is None and _STAGED_CAPTURE.get() == {}
    if staged:
        capture = _STAGED_CAPTURE.get()
    confirming = getattr(policies, "confirmation", None)
    _require(
        (confirming is None) == (confirmation_sets is None),
        "confirmation_sets_do_not_match_the_registration",
    )
    registered_physics = policies.physics
    policies = attach_coverage_plan(policies, coverage_plan, coverage_plan_sums, sets)
    if confirmation_sets is not None:
        # the confirmation sets' structure is the EXAM's, checked once like the open sets' (a fault is Carbon's)
        _check_confirmation_sets(
            policies,
            registered_physics,
            sets,
            confirmation_sets,
            scoring_cells,
            in_range_cases,
        )
    policies = attach_physics(
        policies, scoring_cells, sets, a_multiplier, in_range_cases
    )
    sets = attach_variant_starts(sets, policies.optimizer.variant_rule, variant_starts)
    menu = getattr(policies, "menu", None)
    _require(
        (menu is None and menu_tasks is None and menu_key is None)
        or (menu is not None and menu_tasks and menu_key is not None),
        "menu_material_does_not_match_the_registration",
    )
    _require(
        menu is not None or (menu_rowcheck is None and menu_rowcheck_key is None),
        "menu_material_does_not_match_the_registration",
    )
    if menu is not None:
        # Carbon's gap (the receiver did not run the re-check), never a candidate failure
        _require(
            type(menu_rowcheck) is dict
            and set(menu_rowcheck) == {"positions", "outputs"}
            and menu_rowcheck_key is not None,
            "menu_rowcheck_unavailable",
        )
    _require(
        len(bank_rows) == len(outputs)
        and all(len(r) == len(bank_rows) for r in repeats),
        "one_answer_per_exam_row",
    )
    # The delivered query holds the pool rows quantised to the bank's dtype (`pool_version.rows_from_material`);
    # the grader asks the model's table about the same rounded rows, never about the unrounded designs.
    quantize = _quantizer(input_dtype)
    # P1 (model-eval 22 Nov 2026 04:41:52Z): a REGISTERED pool-only version has no sealed grid and no base measure; its
    # gates are the pool's own (physics, speed, in-range accuracy) and the C cap is each set's physics A (below)
    pool_only = getattr(policies, "pool_only", False) is True
    sealed, pool = split_rows(bank_rows, pool_only=pool_only)
    if pool_only:
        _require(
            policies.physics is not None and menu is not None,
            "pool_only_needs_a_physics_rule_and_a_menu",
        )
        base = {}
    else:
        sealed_rows = [bank_rows[i] for i in sealed]
        base = base_measure(
            bank_rows=sealed_rows,
            outputs=[outputs[i] for i in sealed],
            repeats=[[r[i] for i in sealed] for r in repeats],
            **base_arguments,
        )
    base_gates = dict(base.get("gates") or {})
    _require(pool_only or base_gates, "sealed_measure_returned_no_gates")
    _require(
        PHYSICS_GATE not in base_gates
        and SPEED_GATE not in base_gates
        and (policies.physics is None or ACCURACY_GATE not in base_gates),
        "native_gate_names_collide_with_the_pool_gates",
    )
    all_specs = [spec for group in sets for spec in group]
    _require(all_specs, "exam_has_no_targets")
    # R1: a version's targets are all accuracy-only or none; all accuracy-only needs the sealed menu (its D) and the
    # physics rule (its A). Every other version has none and is unchanged.
    accuracy_only = {bool(getattr(spec, "accuracy_only", False)) for spec in all_specs}
    _require(
        len(accuracy_only) == 1, "accuracy_only_targets_mixed_with_optimizer_targets"
    )
    accuracy_only = accuracy_only == {True}
    _require(
        not accuracy_only or (menu is not None and policies.physics is not None),
        "accuracy_only_targets_need_a_menu_and_a_physics_rule",
    )
    # The REGISTRATION decides the kind, never the pack material (Validator-2B M-1): both must agree, both ways.
    registered_kind = getattr(policies.physics, "target_kind", None)
    _require(
        not accuracy_only or registered_kind == "accuracy_only",
        "accuracy_only_targets_not_registered",
    )
    _require(
        accuracy_only or registered_kind is None,
        "registered_target_kind_not_in_the_material",
    )
    if accuracy_only:
        # Each scored case is graded ONCE, in its own target's role (CV-B A4, CV-Motor (3)): a target id twice, or the
        # same case (its fixed conditions + design) in two targets or two sets, is the exam's structural fault.
        _require(
            len({spec.target_id for spec in all_specs}) == len(all_specs),
            "accuracy_only_target_id_twice",
        )
        cases = [
            (json.dumps(spec.conditions.get("fixed"), sort_keys=True), design)
            for spec in all_specs
            for design in spec.designs
        ]
        _require(len(set(cases)) == len(cases), "accuracy_case_in_two_targets")
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
    confirmation_specs = [spec for group in confirmation_sets or () for spec in group]
    if confirmation_specs:
        # the confirmation rows are bank pool rows the model answered with every other row (`rows_from_material`)
        answered = answered | {
            tuple(quantize(r["inputs"])[n] for n in binding.input_names)
            for r in pool_gates.pool_rows(submitted, confirmation_specs)
        }
    held = {tuple(bank_rows[i]["inputs"][n] for n in binding.input_names) for i in pool}
    if menu is not None:
        from carbon.scoring import pool_menu

        menu_held = {
            tuple(quantize(row)[n] for n in binding.input_names)
            for row in pool_menu.bank_rows(menu_tasks, binding.design_names)
        }
        # Validator-2B a3: the menu designs, quantised as the bank holds them, are bank pool rows.
        _require(menu_held <= held, "menu_rows_differ_from_the_bank")
        answered = answered | menu_held
    if policies.physics is not None and policies.physics.in_range is not None:
        # The sealed in-range case set's rows are pool rows too (`pool_version.rows_from_material`: the model answers
        # only the bank's rows). A case row that is no pool row is left out of `answered` here and refused below as
        # `in_range_case_not_an_exam_row` when it is no bank row at all (a cell or probe row is a bank row).
        answered = answered | {
            row
            for row in (
                tuple(quantize(inputs)[n] for n in binding.input_names)
                for _name, inputs, _t, _u in policies.physics.in_range.cases
                if set(inputs) == set(binding.input_names)
            )
            if row in held
        }
    _require(answered == held, "exam_pool_rows_differ_from_the_targets_pools")
    case_predict = None
    if policies.physics is not None and policies.physics.in_range is not None:
        # The in-range case set's rows must be rows the model answered: read from its one table, never re-asked.
        exam_inputs = {
            tuple(quantize(r["inputs"])[n] for n in binding.input_names)
            for r in bank_rows
        }
        for _name, inputs, _t, _u in policies.physics.in_range.cases:
            _require(
                set(inputs) == set(binding.input_names)
                and tuple(quantize(inputs)[n] for n in binding.input_names)
                in exam_inputs,
                "in_range_case_not_an_exam_row",
            )

        def case_predict(rows):
            answers = serve(rows)
            return [submitted.derive(row, out) for row, out in zip(rows, answers)]

    raw_pool = serve([r["inputs"] for r in pool_row_dicts])
    physics_failed = pool_gates.failed_gates(submitted, pool_row_dicts, raw_pool)
    # An A_gen slice answer the Challenge's own validity gates refuse is the candidate's gate failure on a pool
    # answer (OWNER-GATES-ON-POOL-3A-01: the A_gen slice alike), never an untyped refusal inside agen_accuracy.
    if not pool_grader.agen_predictions_valid(
        all_specs,
        pool_plugin.pool_predictor(submitted, serve),
        pool_physics_score.answer_check(policies.physics),
    ):
        physics_failed = sorted({*physics_failed, AGEN_VALIDITY_GATE})
    speed = single_call_speed_gate(speed_call_seconds, ceiling_seconds=ceiling_seconds)
    if speed_outputs_match is not True:
        # The timed calls answered differently from the graded run on the same rows: a graph that does other
        # work when timed. That is the candidate's, so the speed gate fails (never a pass on odd timings).
        speed = {
            **speed,
            "passed": False,
            "code": pool_gates.SPEED_CODE,
            "outputs_differ": True,
        }
    gates = {
        **base_gates,
        PHYSICS_GATE: not physics_failed,
        SPEED_GATE: speed["passed"],
    }
    accuracy = None
    if policies.physics is not None:
        # The in-range accuracy gate and the full record (custody), every grade. An answer the validity gate already
        # refused leaves nothing sound to measure: the record says so and the gate fails (fail closed).
        if AGEN_VALIDITY_GATE in physics_failed:
            accuracy = {
                "schema": pool_physics_score.RECORD_SCHEMA,
                "skipped": AGEN_VALIDITY_GATE,
            }
        else:
            predictor, case_rows, sink = (
                pool_plugin.pool_predictor(submitted, serve),
                case_predict,
                None,
            )
            if capture is not None:
                # LL2 (owner LL-A): the same measure, its rows served through a recorder, so each answered case's errors
                # are kept with the bank row it was answered from. Custody only; the record and the gate are unchanged.
                sink = case_errors.Sink()
                served = case_errors.ServedKeys(
                    serve,
                    lambda row: tuple(quantize(row)[n] for n in binding.input_names),
                )
                predictor = pool_plugin.pool_predictor(submitted, served)
                if case_predict is not None:

                    def case_rows(rows):
                        answers = served(rows)
                        return [
                            submitted.derive(row, out)
                            for row, out in zip(rows, answers)
                        ]

            accuracy = pool_physics_score.accuracy_record(
                all_specs,
                predictor,
                policies.optimizer.coverage_plan,
                policies.physics,
                case_rows,
                sink,
            )
            if sink is not None:
                if confirmation_specs:
                    # S2 (bank 8319, model-eval 8325): the confirmation cases join the same per-case file as source 2, read
                    # through their own recorder and merged only whole, so a failure never misaligns the open cases
                    _confirmation_cases(
                        confirmation_specs,
                        submitted,
                        serve,
                        lambda row: tuple(
                            quantize(row)[n] for n in binding.input_names
                        ),
                        policies,
                        sink,
                        served,
                        capture,
                    )
                try:
                    bank_keys = [
                        tuple(quantize(r["inputs"])[n] for n in binding.input_names)
                        for r in bank_rows
                    ]
                    capture["case_errors"] = case_errors.assemble(
                        sink, served.keys, bank_keys
                    )
                except Exception as failure:  # noqa: BLE001
                    # custody evidence, never the grade
                    capture["case_errors_unavailable"] = getattr(
                        failure, "code", type(failure).__name__
                    )
        # The sealed grader's measured laws (Validator 5 Nov, condition before FINAL): with A the family value, a law
        # measured but not yet given a gate margin is neither scored nor gated, so every grade records it here (custody)
        # until the owner registers its margin. Copied as the Challenge's physics half reported it; never scored.
        accuracy = {
            **accuracy,
            "laws": {
                "physics_half": copy.deepcopy(base.get("physics_half")),
                "a_legs": dict(base.get("A_legs") or {}),
            },
        }
        gates[ACCURACY_GATE] = bool((accuracy.get("gate") or {}).get("passed"))
        if capture is not None:
            capture["accuracy"] = accuracy
    gated = (not pool_only and base.get("A") is None) or not all(gates.values())
    if confirmation_sets is not None and capture is not None:
        # the crown's private number on the confirmation rows (a gate-failed grade has no score, so none to confirm)
        capture["confirmation"] = (
            {
                "status": "UNAVAILABLE",
                "reason": "gated",
                "sets_sha256": confirming["sets_sha256"],
            }
            if gated
            else confirmation_value(
                confirmation_sets, submitted, serve, policies, confirming
            )
        )
    if gated:
        # A failed mandatory gate gives no score; the dual pack reads only the gate verdicts.
        if capture is not None:
            capture["se_basis"] = {"gated": True}
        _offer_kept(speed, speed_call_seconds, accuracy)
        return {
            **base,
            "A": base.get("A"),
            "D": 0.0,
            "gates": gates,
            "decision_outcome": base.get("decision_outcome", OUTCOME_POOL),
            "pool": {
                "physics_failed": physics_failed,
                "speed": speed,
                **({} if accuracy is None else {"accuracy": accuracy}),
            },
        }
    legs = {
        "A": base.get("A") if pool_only else base["A"],
        "C": (base.get("design_fidelity") or {}).get("C"),
        "gates_ok": True,
        "A_legs": dict(base.get("A_legs") or {}),
    }
    # a pool-only version has no sealed C: its cap is each set's physics A (`cap`, below)
    _require(
        pool_only or (type(legs["C"]) in (int, float) and math.isfinite(legs["C"])),
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
        variant_rule=policies.optimizer.variant_rule,
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
        None  # a pool-only version has no sealed A (its A is the physics family value)
        if pool_only
        else (
            statistics.fmean(tighten(v, a_multiplier) for v in a_legs.values())
            if a_legs
            else tighten(legs["A"], a_multiplier)
        )
    )
    descriptor = {"kind": "good"}
    if accuracy_only:
        # R1: no optimisation problem, so no pick D (the menu below gives D) and no set total from a pick: A per set is
        # the physics family value, exactly as `score_specs` computes it for a physics version.
        good = suite.pool_predictor(plugin, descriptor, all_specs)
        per_set = [
            (None, None, suite._physics_a_gen(specs, good, policies), legs)
            for specs in plugin.sets
        ]
    else:
        per_set = [
            suite.score_specs(plugin, specs, descriptor, policies, all_specs)
            for specs in plugin.sets
        ]
    a_values, d_values, reasons, a_gen = [], [], set(), []

    def cap(position):
        """The owner's C rule for set ``position``: the sealed C, or (pool-only) that set's own physics A."""
        return a_values[position] if pool_only else legs["C"]

    for _total, grade, gen, _legs in per_set:
        a_gen.append(gen)
        # A version with physics scoring: A is the family value (the in-range A leg is its gate, never points).
        a_values.append(
            gen
            if policies.physics is not None
            else pool_grader.combine_a(a_bank, gen, policies.a_rule)
        )
        if grade is None:
            continue  # accuracy-only: the menu D replaces every set's D below
        # D as the total sees it: capped by C, so the dual pack's own 0.5 A + 0.5 D is each set's TOP.
        d_values.append(min(grade.d, cap(len(a_values) - 1)))
        reasons.update(grade.public()["reasons"])
    menu_graded = None
    if menu is not None:
        from carbon.scoring import pool_menu

        def predict_rows(rows):
            answers = serve(rows)
            _require(
                type(answers) is list and len(answers) == len(rows),
                "serve_must_return_one_row_per_input",
            )
            return [submitted.derive(row, out) for row, out in zip(rows, answers)]

        # The menu D replaces each set's pick D (Validator-2B (b): the epoch menu is drawn after the predictions); the
        # C rule still caps it, so the dual pack's 0.5 A + 0.5 D is each set's TOP as before.
        positions = pool_menu.rowcheck_plan(
            len(bank_rows), menu.rowcheck[2], menu_rowcheck_key, epoch=menu.epoch
        )
        _require(
            list(menu_rowcheck["positions"]) == positions,
            "menu_rowcheck_positions_not_the_keyed_plan",
        )
        menu_graded = pool_menu.score(
            menu_tasks,
            menu,
            predict_rows,
            key=menu_key,
            design_names=binding.design_names,
            row_dependent=pool_menu.rowcheck_differs(
                outputs, menu_rowcheck["outputs"], positions, menu
            ),
        )
        d_values = [min(menu_graded["D"], cap(i)) for i in range(len(per_set))]
        if capture is not None:
            capture["menu"] = menu_graded["record"]
    a_only = policies.physics is not None and policies.physics.total_rule == "a_only"
    if a_only:
        # The owner's "physics score alone" for this version: D := A per set, so the dual pack's 0.5 A + 0.5 D is A.
        d_values = list(a_values)

    def se_basis():
        """The per-target decomposition of the final total (`se_basis`), from this grade's own values."""
        if policies.physics is not None:
            # A version with physics scoring: each target carries its d and its sums per scored cell (`target_cells`), so a
            # resample recomposes cell -> family -> A exactly as the grade did (`total_of_targets`).
            predict = suite.pool_predictor(plugin, descriptor, all_specs)
            basis = {
                "gated": False,
                "physics": True,
                "a_only": a_only,
                # in memory only (never serialized): the rule a resample recomposes headroom skill with
                "physics_rule": policies.physics,
                "c": legs["C"],
                # pool-only: the cap of each set is its own (recomposed) physics A
                **({"c_is_a": True} if pool_only else {}),
                # a menu version: the resample holds the menu D fixed (it conditions on the epoch's draw); absent otherwise
                **({} if menu_graded is None else {"menu_d": menu_graded["D"]}),
                "a_sets": list(a_values),
                "sets": [
                    [
                        {
                            # an accuracy-only target has no pick d (the basis holds the menu D fixed)
                            "d": None if target is None else target.d,
                            "cells": pool_physics_score.target_cells(
                                spec,
                                predict,
                                policies.agen_scales,
                                policies.optimizer.coverage_plan,
                                policies.physics,
                            ),
                        }
                        for spec, target in zip(
                            specs,
                            [None] * len(specs) if grade is None else grade.targets,
                            strict=True,
                        )
                    ]
                    for specs, (_t, grade, _g, _l) in zip(
                        plugin.sets, per_set, strict=True
                    )
                ],
                "total": 0.5 * statistics.fmean(a_values)
                + 0.5 * statistics.fmean(d_values),
            }
            _basis_regions(basis, policies.optimizer, plugin.sets)
        else:
            predict = suite.pool_predictor(plugin, descriptor, all_specs)
            basis = {
                "gated": False,
                "a_bank": a_bank,
                "c": legs["C"],
                **({} if menu_graded is None else {"menu_d": menu_graded["D"]}),
                "a_rule": dict(policies.a_rule),
                "sets": [
                    [
                        {
                            "d": target.d,
                            "agen": pool_grader.agen_accuracy(
                                [spec], predict, policies.agen_scales
                            ),
                        }
                        for spec, target in zip(specs, grade.targets, strict=True)
                    ]
                    for specs, (_t, grade, _g, _l) in zip(
                        plugin.sets, per_set, strict=True
                    )
                ],
                "total": 0.5 * statistics.fmean(a_values)
                + 0.5 * statistics.fmean(d_values),
            }
            _basis_regions(basis, policies.optimizer, plugin.sets)
        return basis

    if staged:
        # derived by the receiver AFTER the producer call: outside every lock the produce holds, its failure never the grade's
        capture["se_basis_of"] = se_basis
    elif capture is not None:
        capture["se_basis"] = se_basis()
    _offer_kept(speed, speed_call_seconds, accuracy, a_values, d_values, plugin.sets)
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
            # a menu version's set totals are recomposed with the menu D (the pick's totals no longer apply)
            "set_totals": (
                [t for t, _g, _a, _l in per_set]
                if menu_graded is None
                else [0.5 * a + 0.5 * d for a, d in zip(a_values, d_values)]
            ),
            **({} if menu_graded is None else {"menu": menu_graded["record"]}),
            **({} if accuracy is None else {"accuracy": accuracy}),
            **({"total_rule": "a_only"} if a_only else {}),
        },
    }


def _check_confirmation_sets(
    policies, registered_physics, sets, groups, scoring_cells, in_range_cases
):
    """A NEW version's confirmation sets are a sound exam part, or `ExamRefused` (Carbon's, before any grade): the
    version has a physics rule and a coverage plan; every confirmation set holds every registered class, exactly as an
    open set must (so its family value is defined the same way); the scoring cells check out on them as on the open sets;
    and no confirmation target is an open target (its number would then not be on rows the open grade never shows)."""
    _require(registered_physics is not None, "confirmation_sets_need_a_physics_rule")
    plan = policies.optimizer.coverage_plan
    _require(plan is not None, "confirmation_sets_need_a_registered_coverage_plan")
    _require(
        type(groups) is tuple and groups and all(groups), "confirmation_sets_empty"
    )
    open_ids = {spec.target_id for group in sets for spec in group}
    for group in groups:
        try:
            classes = {pool_grader.region_class(spec, plan) for spec in group}
        except pool_grader.PoolRefused:
            raise ExamRefused("confirmation_target_not_in_the_coverage_plan") from None
        _require(
            classes == set(plan.classes), "confirmation_set_missing_a_registered_class"
        )
        _require(
            not any(spec.target_id in open_ids for spec in group),
            "confirmation_target_is_an_open_target",
        )
    try:
        pool_physics_score.attach_cells(
            registered_physics, scoring_cells, plan, groups, in_range_cases
        )
    except pool_grader.PoolRefused as refused:
        raise ExamRefused(f"confirmation_structure_refused:{refused}") from None


def confirmation_value(groups, submitted, serve, policies, rule):
    """The private confirmation record of one scored grade: ``{"status", "value", "sets", "sets_sha256"}``.

    MEASURED: ``value`` is the version's physics family value per confirmation set (`pool_proof_suite._physics_a_gen`,
    the same call that gives the open sets' A), mean over the sets: the version's ranked number on rows no public
    surface shows. INVALID: a confirmation answer the Challenge's validity check refuses (the candidate's: the crown is
    not confirmed). UNAVAILABLE with ``reason``: anything else that stops the number (Carbon's: the crown waits). Never
    raises and never touches the grade."""
    base = {"sets": len(groups), "sets_sha256": rule["sets_sha256"]}
    try:
        predictor = pool_plugin.pool_predictor(submitted, serve)
        specs = [spec for group in groups for spec in group]
        if not pool_grader.agen_predictions_valid(
            specs, predictor, pool_physics_score.answer_check(policies.physics)
        ):
            return {**base, "status": "INVALID", "value": None}
        values = [suite._physics_a_gen(group, predictor, policies) for group in groups]
        value = statistics.fmean(values)
        if not (type(value) is float and math.isfinite(value)):
            return {
                **base,
                "status": "UNAVAILABLE",
                "value": None,
                "reason": "not_finite",
            }
        return {**base, "status": "MEASURED", "value": value}
    except Exception as failure:  # noqa: BLE001 - the crown waits, never the grade
        return {
            **base,
            "status": "UNAVAILABLE",
            "value": None,
            "reason": getattr(failure, "code", None) or type(failure).__name__,
        }


def _confirmation_cases(
    specs, submitted, serve, key_of, policies, sink, served, capture
):
    """The confirmation cases' per-case errors (`case_errors` source 2) into ``sink``, their served keys into ``served``:
    collected in their own recorder first and merged only when whole, so the open cases stay aligned whatever happens.
    A failure is noted in ``capture["confirmation_case_errors_unavailable"]``; never the grade."""
    try:
        own = case_errors.Sink()
        keys = case_errors.ServedKeys(serve, key_of)
        plan = policies.optimizer.coverage_plan
        pool_physics_score._ratios(
            [(spec, plan.class_of(spec.target_id)) for spec in specs],
            pool_plugin.pool_predictor(submitted, keys),
            pool_physics_score.class_ranges(specs, plan),
            policies.physics,
            case_errors.Relabelled(own, case_errors.SOURCE_CONFIRMATION),
        )
        if len(keys.keys) != len(own.cases):
            raise ExamRefused("case_errors_served_rows_misaligned")
    except Exception as failure:  # noqa: BLE001 - custody evidence, never the grade
        capture["confirmation_case_errors_unavailable"] = getattr(
            failure, "code", type(failure).__name__
        )
        return
    sink.cases.extend(own.cases)
    served.keys.extend(keys.keys)


def _offer_kept(speed, call_seconds, accuracy, a_values=None, d_values=None, sets=None):
    """Offer what this grade already computed to a staged keep (`grade_breakdown.staged`, set by the receiver around
    its producer call; nothing staged: a no-op, nothing built): each set's A, D and target count, the accuracy record's
    per class and output aggregates (never a per-case value), and the scored single-call seconds with the speed verdict.
    Never changes, stops or refuses the grade (owner via Lead, 19 Nov 2026: king statistics from the official grade).
    """
    from carbon.scoring import grade_breakdown

    if sets is not None:
        grade_breakdown.offer(
            "sets",
            lambda: {
                f"set{i}": {"A": float(a), "D": float(d), "rows": len(specs)}
                for i, (a, d, specs) in enumerate(
                    zip(a_values, d_values, sets, strict=True)
                )
            },
        )
    if accuracy is not None and "rows" in accuracy:
        grade_breakdown.offer(
            "outputs",
            lambda: [
                {
                    "class": row["class"],
                    "output": row["output"],
                    "range": row["range"],
                    "n": int(row["n"]),
                    "median": (None if row["median"] is None else float(row["median"])),
                    "p90": None if row["p90"] is None else float(row["p90"]),
                }
                for row in accuracy["rows"]
            ],
        )
    grade_breakdown.offer(
        "speed",
        lambda: {
            "call_seconds": [float(c) for c in call_seconds],
            "median_seconds": float(speed["median_seconds"]),
            "ceiling_seconds": float(speed["ceiling_seconds_per_design"]),
            "passed": bool(speed["passed"]),
        },
    )
    grade_breakdown.offer("measure", None)


#: A weekly-check SE is reported only from at least this many targets per set (Validator ruling, 2026-10-29).
SE_MIN_TARGETS = 4


def _basis_regions(basis, optimizer, sets):
    """A balanced version's SE basis also carries its aggregation, the class order and each target's class, so the
    recomposed total aggregates exactly as the grade did. A version with neither aggregate (every registered version)
    keeps its basis as it was."""
    if optimizer.d_aggregate is None and optimizer.a_gen_aggregate is None:
        return
    plan = optimizer.coverage_plan
    basis["d_aggregate"] = optimizer.d_aggregate
    basis["a_gen_aggregate"] = optimizer.a_gen_aggregate
    basis["classes"] = list(pool_grader.class_order(plan))
    for targets, specs in zip(basis["sets"], sets, strict=True):
        for target, spec in zip(targets, specs, strict=True):
            target["region"] = pool_grader.region_class(spec, plan)
    if optimizer.a_gen_aggregate == "ood_class_mean":
        # The out-of-range A_gen classes per set, the small ones pooled, as `agen_accuracy` grouped them on the full set.
        # The bootstrap keeps this grouping fixed (it conditions on the graded pooling): a resample keeps each class's
        # TARGET count, not its reserved-case count, so re-pooling a resample could group it differently.
        basis["agen_orders"] = []
        for targets, specs in zip(basis["sets"], sets, strict=True):
            buckets, order = pool_grader.agen_buckets(
                specs, plan, optimizer.a_gen_min_class_cases
            )
            for target, bucket in zip(targets, buckets, strict=True):
                target["agen_region"] = bucket
            basis["agen_orders"].append(list(order))


def _region_mean(targets, key, order):
    rows = [t for t in targets if t[key] is not None]
    if not rows:
        return None
    regions = pool_grader.region_means(
        [t["region"] for t in rows], [t[key] for t in rows], order
    )
    return statistics.fmean(value for _name, value in regions)


def total_of_targets(basis, sets):
    """The final pool total recomputed from per-target values: the exam's own composition
    (`measure_pool`): per set, D = min(mean d, C) and A = combine_a(A_bank, mean A_gen, rule); the
    total is 0.5 * mean(A) + 0.5 * mean(D) over the sets. A balanced version's basis (`_basis_regions`) takes each
    balanced mean over its classes in the basis's order instead, as `grade_set` / `agen_accuracy` did.
    """
    order = basis.get("classes")
    a_values, d_values = [], []
    for position, targets in enumerate(sets):
        if basis.get("physics") is True:
            # A IS the family value: recomposed from the drawn targets' cell sums. A draw holding no case of any scored
            # cell (possible only in a resample) keeps the set's graded A: the bootstrap conditions on it.
            a = pool_physics_score.compose(
                [t["cells"] for t in targets], basis.get("physics_rule")
            )
            a_values.append(basis["a_sets"][position] if a is None else a)
        elif basis.get("a_gen_aggregate") is None:
            gens = [t["agen"] for t in targets if t["agen"] is not None]
            a_gen = statistics.fmean(gens) if gens else None
        elif basis["a_gen_aggregate"] == "ood_class_mean":
            rows = [t for t in targets if t["agen"] is not None]
            regions = pool_grader.region_means(
                [t["agen_region"] for t in rows],
                [t["agen"] for t in rows],
                basis["agen_orders"][position],
            )
            # A resample that draws only slice-less targets has no A_gen, as on the balanced path: A is then A_bank.
            a_gen = statistics.fmean(v for _n, v in regions) if regions else None
        else:
            a_gen = _region_mean(targets, "agen", order)
        if basis.get("physics") is not True:
            a_values.append(
                pool_grader.combine_a(basis["a_bank"], a_gen, basis["a_rule"])
            )
        if basis.get("menu_d") is not None:
            # a menu version: the resample holds the epoch's menu D fixed (an accuracy-only target has no pick d)
            d = basis["menu_d"]
        elif basis.get("d_aggregate") is None:
            d = statistics.fmean(t["d"] for t in targets)
        else:
            d = _region_mean(targets, "d", order)
        d_values.append(
            min(d, a_values[-1] if basis.get("c_is_a") is True else basis["c"])
        )
    if basis.get("a_only") is True:
        return statistics.fmean(
            a_values
        )  # a physics version scored by A alone (its D is reported as A)
    return 0.5 * statistics.fmean(a_values) + 0.5 * statistics.fmean(d_values)


def target_bootstrap_se(basis, exam_key, *, resamples=200):
    """(SE, n_targets) of the exam total: a cluster bootstrap over TARGETS (Validator ruling, 2026-10-29).

    Targets are resampled with replacement within each set (the set structure kept, a target's d and A_gen
    travelling with it), the final total is recomputed exactly as the exam computes it, and the SE is the standard
    deviation of the resampled totals times sqrt(n / (n - 1)), n = the smallest set's targets. The seed is the
    first 8 bytes of the exam key. Raises `ExamRefused` with "gated" (a gate failed, so there is no total) or
    "too_few_targets" (fewer than SE_MIN_TARGETS in a set)."""
    import numpy as np

    _require(type(basis) is dict and basis.get("gated") is False, "gated")
    sets = basis["sets"]
    sizes = [len(targets) for targets in sets]
    _require(sizes and min(sizes) >= SE_MIN_TARGETS, "too_few_targets")
    _require(
        type(exam_key) is str and exam_key.startswith("sha256:"),
        "bootstrap_exam_key_invalid",
    )
    try:
        seed = int.from_bytes(bytes.fromhex(exam_key[7:])[:8], "big")
    except ValueError:
        raise ExamRefused("bootstrap_exam_key_invalid") from None
    generator = np.random.Generator(np.random.PCG64(seed))
    totals = []
    stratified = basis.get("classes") is not None
    for _ in range(resamples):
        drawn = []
        for targets in sets:
            if stratified:
                drawn.append(_stratified_draw(generator, targets, basis["classes"]))
                continue
            order = generator.choice(len(targets), size=len(targets), replace=True)
            drawn.append([targets[int(i)] for i in order])
        totals.append(total_of_targets(basis, drawn))
    n = min(sizes)
    spread = float(np.std(np.asarray(totals), ddof=1)) * math.sqrt(n / (n - 1))
    return spread, sizes


def _stratified_draw(generator, targets, classes):
    """A balanced version's resample of one set: with replacement WITHIN each class, in the class order, so every class
    the grade averaged over stays in the resample with its own size (the set and class structure kept).
    """
    drawn = []
    for name in classes:
        members = [t for t in targets if t["region"] == name]
        if not members:
            continue
        order = generator.choice(len(members), size=len(members), replace=True)
        drawn += [members[int(i)] for i in order]
    return drawn


def geometric_v1_names_valid(classes):
    """Whether every class name of a coverage plan is a geometric-v1 name. The vocabulary is read from the receipted
    geometric-v1 rule code (`carbon.scoring.geometric_v1`, B1 option (a)); no name is typed here.
    """
    from carbon.scoring import geometric_v1

    return geometric_v1.names_valid(classes)


def attach_coverage_plan(policies, document, sums, sets):
    """``policies`` with the version's registered coverage plan attached, or `ExamRefused`.

    A version that registers no coverage plan keeps its policies unchanged and its sealed material carries none. A
    version that registers one (`coverage_plan_sha256` and `coverage_plan_sums_sha256`) grades only with a sealed
    class-map ``document`` of exactly that sha256, listed in a ``sums`` text (the plan package's SHA256SUMS) of exactly
    that sha256, whose class names are geometric-v1 names (or, for a version that registers an admission class
    vocabulary, exactly that vocabulary: X-1), and that classes every target of every set, each set holding every
    registered class (a missing target or class is refused, never defaulted or skipped).
    """
    optimizer = policies.optimizer
    registered = optimizer.coverage_plan_sha256
    if registered is None:
        _require(document is None and sums is None, "coverage_plan_not_registered")
        return policies
    _require(document is not None, "coverage_plan_missing_from_the_sealed_pack")
    _require(sums is not None, "coverage_plan_sums_missing_from_the_sealed_pack")
    try:
        plan = pool_grader.coverage_plan(document)
        listed = pool_grader.sums_list(sums, plan.sha256)
    except pool_grader.PoolRefused:
        raise ExamRefused("coverage_plan_malformed") from None
    _require(plan.sha256 == registered, "coverage_plan_sha256_mismatch")
    _require(
        hashlib.sha256(sums.encode()).hexdigest()
        == optimizer.coverage_plan_sums_sha256,
        "coverage_plan_sums_sha256_mismatch",
    )
    _require(listed, "coverage_plan_not_listed_in_its_sums")
    vocabulary = optimizer.coverage_class_vocabulary
    if vocabulary is None:
        _require(
            geometric_v1_names_valid(plan.classes) is True,
            "coverage_plan_class_not_geometric_v1",
        )
    else:
        # X-1 (Carbon Validator-C b98e6e19): the version's registered admission labels, read from its registration
        _require(
            set(plan.classes) == set(vocabulary),
            "coverage_plan_classes_are_not_the_registered_vocabulary",
        )
    for group in sets:
        try:
            classes = {pool_grader.region_class(spec, plan) for spec in group}
        except pool_grader.PoolRefused:
            raise ExamRefused("target_not_in_the_coverage_plan") from None
        _require(classes == set(plan.classes), "set_missing_a_registered_class")
        if optimizer.a_gen_aggregate == "ood_class_mean":
            # The out-of-range A_gen structure is the EXAM's, not a candidate's: check it here, once, typed, before any
            # submission is graded (a reference failure is never collapsed into a candidate's result).
            try:
                pool_grader.agen_buckets(group, plan, optimizer.a_gen_min_class_cases)
            except pool_grader.PoolRefused as refused:
                raise ExamRefused(f"a_gen_structure_refused:{refused}") from None
    return replace(policies, optimizer=replace(optimizer, coverage_plan=plan))


def attach_physics(policies, document, sets, a_multiplier=None, in_range_document=None):
    """``policies`` with a NEW version's sealed scoring cells attached to its physics rule, or `ExamRefused`. A version
    without a physics rule keeps its policies unchanged and its sealed material carries no scoring cells. The structure
    is the EXAM's: checked here, once, typed, before any submission is graded."""
    rule = policies.physics
    if rule is None:
        _require(document is None, "scoring_cells_not_registered")
        _require(in_range_document is None, "in_range_cases_not_registered")
        return policies
    _require(
        policies.optimizer.a_gen_aggregate is None,
        "physics_rule_replaces_the_a_gen_aggregate",
    )
    try:
        attached = pool_physics_score.attach_cells(
            rule,
            document,
            policies.optimizer.coverage_plan,
            sets,
            in_range_document,
        )
    except pool_grader.PoolRefused as refused:
        raise ExamRefused(f"physics_structure_refused:{refused}") from None
    # The registered A multiplier rides with the rule: a cell scale that applies it reads it from there.
    return replace(policies, physics=replace(attached, a_multiplier=a_multiplier))


def attach_variant_starts(sets, rule, starts):
    """``sets`` with each target's neighbour-task variants attached (`pool_grader.attach_variants`) from the sealed
    material's ``variant_starts`` when the version registers a ``variant_rule``; unchanged, and the material must carry
    none, when it does not. Custody: the starts name targets."""
    if rule is None:
        _require(starts is None, "variant_starts_without_a_variant_rule")
        return sets
    _require(type(starts) is dict, "variant_starts_missing_from_the_sealed_pack")
    ids = {spec.target_id for group in sets for spec in group}
    _require(set(starts) == ids, "variant_starts_must_name_every_target_exactly")
    return tuple(
        tuple(
            pool_grader.attach_variants(spec, rule, starts[spec.target_id])
            for spec in group
        )
        for group in sets
    )


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
    "ACCURACY_GATE",
    "OUTCOME_POOL",
    "PHYSICS_GATE",
    "POOL_COHORT",
    "SPEED_GATE",
    "SPEED_SAMPLE",
    "ExamRefused",
    "attach_coverage_plan",
    "attach_physics",
    "geometric_v1_names_valid",
    "measure_pool",
    "public",
    "single_call_speed_gate",
    "speed_sample",
    "split_rows",
    "table_server",
]
