"""Motor's Level 0 attack adapter (OWNER-GRAPHITE-ATTACKER-01; the Graphite
test wave's motor row).

The claims tested:
- the adapter is registered by `(electric-motor-magnetics, 0)`, names the live
  contract read only, and carries the session surface a Graphite session
  needs;
- every Track A check is covered by a family or a declared NOT_RUN seam; every
  run check names an attack example and a valid control; every family has a
  trained and a held-out control, versioned, and the held-out controls are
  canonically distinct from the trained ones and refused by the engine;
- every attack is held by the real boundary, every specimen fires, every
  control passes; the oracle tries each attempt against both the real
  boundary and the vulnerable specimen;
- the Test Lead's motor vectors each map to a check, run where a boundary is
  registered, and name the owner value they still need as a NOT_RUN seam;
- the oracle emits only the CONDITIONS vocabulary, as battery's does;
- Carbon rebuilds with its own typed build record and refuses with a typed
  code; public motor practice scoring is registered, while phase-4's
  verification-pod rebuild remains a separate seam;
- no sealed identity is named, and only public TRAIN and PRACTICE material
  (and the calibration document their loader checks) is read;
- each pinned value is a copy of its motor source;
- the adapter scores through motor's frozen rule (`MotorPracticeRule`, as
  Graphite does): an omitted or null prediction is a schema-gate failure,
  never FAILED_INFRA and never excluded, so a partial set is never eligible
  (GRAPHITE-COVERAGE-PARITY-02);
- mutations: disabling each boundary turns its guard red. Each mutation
  patches the module the check actually reads, never a re-export.
"""

from __future__ import annotations

import dataclasses
import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from carbon.agent_campaign.attack import adapter as core
from carbon.agent_campaign.attack import adapters, engine, knowledge
from carbon.agent_campaign.attack.adapters import motor as m
from carbon.challenge_readiness.admission import CHECKS, CONDITIONS

A = m.ADAPTER
SPECS = {s.name: s for s in A.family_specs()}
REPOSITORY = Path(__file__).resolve().parents[2]


def _held_and_fired(name):
    """Every attack HELD by the oracle (the specimen fired on it); every
    specimen fires."""
    spec = A.family_spec(name)
    attacks = spec.attacks()
    assert attacks
    readings = {n: A.assess(spec, (n, value)) for n, value in attacks}
    not_held = {
        n: (r.reading, r.oracle.verdict)
        for n, r in readings.items()
        if (r.reading, r.oracle.verdict) != (m.HELD, m.HELD)
    }
    assert not not_held, not_held
    assert all(r.condition is None for r in readings.values())
    silent = [n for n, value in attacks if not spec.breached(spec.specimen(value))]
    assert not silent, silent


def _controls_pass(name, split="trained"):
    controls = [x for x in A.controls(split) if x.family == name]
    assert controls
    for control in controls:
        assert control.check(), control.name
        assert A.control_passes(control), control.name


# -- identity, registry and session surface ------------------------------------------------------
def test_the_registry_loads_motor_level_0_and_refuses_anything_else():
    assert adapters.load(m.CHALLENGE_ID, 0) is A
    assert (m.CHALLENGE_ID, 0) in adapters.registered()
    with pytest.raises(adapters.AdapterNotRegistered):
        adapters.load(m.CHALLENGE_ID, 1)
    assert core.get(m.CHALLENGE_ID, 0) is A
    assert core.validate(A) is A
    assert isinstance(A, core.Adapter) and isinstance(A, core.SessionSurface)
    coverage = core.coverage(A)
    assert coverage["fresh_attack_confirmation"]["not_run"] == ["fresh_cases_rerun"]


def test_the_adapter_names_the_live_contract_read_only():
    from carbon.reconstruction.capability_registry import (
        MOTOR_CHALLENGE,
        contract_digest,
    )

    assert (A.challenge_id, A.level) == (MOTOR_CHALLENGE, 0)
    assert A.contract_digest == contract_digest(MOTOR_CHALLENGE)
    surface = A.surface()
    assert surface["profile"] == "level-0"
    assert surface["contract_digest"] == A.contract_digest
    assert surface["submission_form"].startswith("declarative strategy only")
    assert surface["adapter_version"] == m.ADAPTER_VERSION


def test_the_session_surface_is_carbons_own_admission():
    from carbon.motor.challenge import CHALLENGE
    from carbon.motor.research import SCAFFOLD

    inventory = A.permission_inventory()
    assert (inventory["profile"], inventory["challenge"]) == ("level-0", m.CHALLENGE_ID)
    assert A.public_identity() == {"id": CHALLENGE.challenge_id, "version": "1.0"}
    assert A.code_run_seconds() == m.CODE_RUN_SECONDS
    assert A.admission_refusals(SCAFFOLD) == []
    outside = A.admission_refusals(A.recipe_outside_contract())
    assert outside[0] == "contract_refused" and "backbone.not_in_contract" in outside
    assert A.admission_refusals(m._strategy(loss_expressions=True)) == [
        "contract_refused",
        "parameter.not_rebuildable",
    ]


# -- coverage of the eight checks -----------------------------------------------------------------
def test_every_track_a_check_is_covered_by_a_family_or_a_not_run_seam():
    checks = A.checks()
    assert set(checks) == CHECKS[m.TRACK]
    assert all(checks.values())
    assert checks["fresh_attack_confirmation"] == ("fresh_cases_rerun:NOT_RUN",)
    assert {f.check for f in A.families()} == CHECKS[m.TRACK] - {
        "fresh_attack_confirmation"
    }


def test_every_check_names_an_attack_and_a_control():
    """Each run check has a family whose attack example is one of its attacks
    and whose control example is a trained control of that family; the check
    with no family (fresh attack confirmation) is a NOT_RUN seam that names
    the owner decision it waits for."""
    trained = {x.name: x for x in A.controls("trained")}
    named = {}
    for definition in A.families():
        spec = SPECS[definition.name]
        assert definition.attack_example in {n for n, _ in spec.attacks()}
        assert trained[definition.control_example].family == definition.name
        named.setdefault(definition.check, []).append(definition.name)
    for check in CHECKS[m.TRACK]:
        if check == "fresh_attack_confirmation":
            (seam,) = [s for s in A.level_families() if s.check == check]
            assert seam.state == core.NOT_RUN and "reserved: owner" in seam.reason
        else:
            assert named.get(check), check


def test_each_family_def_carries_its_engine_family_and_examples():
    for definition in A.families():
        spec = SPECS[definition.name]
        family = definition.family
        assert (family.name, family.check) == (definition.name, definition.check)
        assert family.boundary is spec.boundary and family.specimen is spec.specimen
        assert family.breached is spec.breached and family.attacks is spec.attacks
        assert definition.boundary == spec.protocol_family == family.description
    assert [f.name for f in A.engine_families()] == [f.name for f in A.families()]


# -- controls -------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(SPECS))
def test_each_family_has_both_control_splits(name):
    for split in m.SPLITS:
        assert [x for x in A.controls(split) if x.family == name], split


def test_controls_are_split_disjoint_and_versioned():
    trained, held = A.controls("trained"), A.controls("held_out")
    assert {x.name for x in trained}.isdisjoint({x.name for x in held})
    assert {x.version for x in trained + held} == {m.CONTROLS_VERSION}
    assert {x.split for x in trained} == {"trained"}
    assert {x.split for x in held} == {"held_out"}
    assert A.controls_digest("trained") != A.controls_digest("held_out")
    with pytest.raises(ValueError):
        A.controls("tuning")


def test_held_out_controls_are_genuinely_distinct_and_still_pass():
    """No held-out control is a reordered or round-tripped copy of a trained
    one: canonically every held-out value differs from every trained value
    of its family, and every registered identity differs."""
    for name in SPECS:
        trained = [x for x in A.control_specs("trained") if x.family == name]
        held = [x for x in A.control_specs("held_out") if x.family == name]
        seen = {m._canonical(x.value()) for x in trained}
        for control in held:
            assert m._canonical(control.value()) not in seen, control.name
    identities = {x.identity for x in A.controls("trained")}
    assert identities.isdisjoint({x.identity for x in A.controls("held_out")})


@pytest.mark.parametrize("name", sorted(SPECS))
def test_the_engine_refuses_held_out_controls_even_relabelled(name):
    core.register_held_out_identities(A)
    family = A.family_spec(name)
    definition = next(f for f in A.families() if f.name == family.name)
    held = [x for x in A.controls("held_out") if x.family == name]
    context = core.run_context(A)
    with pytest.raises(engine.HeldOutControlRefused):
        engine.run_family(definition.family, budget=0, context=context, controls=held)
    relabelled = [dataclasses.replace(x, split="trained") for x in held]
    with pytest.raises(engine.HeldOutControlRefused):
        engine.run_family(
            definition.family, budget=0, context=context, controls=relabelled
        )


@pytest.mark.parametrize("split", m.SPLITS)
def test_every_control_passes(split):
    for name in SPECS:
        _controls_pass(name, split)


def test_the_held_out_controls_measure_no_wrongful_rejection():
    rates = core.wrongful_rejection(core.held_out_outcomes(A), A.families())
    assert {name: row["rate"] for name, row in rates.items()} == dict.fromkeys(
        SPECS, 0.0
    )


def test_the_engine_control_reads_the_trained_split_only(monkeypatch):
    asked = []
    real = A.control_specs

    def control_specs(split):
        asked.append(split)
        if split != "trained":
            raise AssertionError("the engine read a held-out control")
        return real(split)

    monkeypatch.setattr(A, "control_specs", control_specs)
    for name in ("resource_accounting", "mandatory_failure"):
        assert A.trained_control(name)()
    assert set(asked) == {"trained"}


def test_the_engine_runs_every_family_with_trained_controls():
    trained = A.controls("trained")
    runs = []
    for definition in A.families():
        run = engine.run_family(
            definition.family,
            budget=100,
            controls=[x for x in trained if x.family == definition.name],
        )
        assert engine.family_state(run) == "IN_PROGRESS", definition.name
        runs.append(run)
    assert engine.findings(runs) == []


# -- attacks, specimens and the oracle --------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(SPECS))
def test_every_attack_is_held_and_every_specimen_fires(name):
    _held_and_fired(name)


@pytest.mark.parametrize("name", sorted(SPECS))
def test_the_oracle_tries_both_the_real_boundary_and_the_specimen(name):
    """For each family's attack example the oracle calls the real boundary
    and the vulnerable specimen on the same input, and reports both."""
    spec = A.family_spec(name)
    calls = {"boundary": [], "specimen": []}

    def counting(role, call):
        def run(value):
            calls[role].append(m._digest(value))
            return call(value)

        return run

    watched = dataclasses.replace(
        spec,
        boundary=counting("boundary", spec.boundary),
        specimen=counting("specimen", spec.specimen),
    )
    attack = dict(spec.attacks())[spec.attack_example]
    result = A.assess(watched, (spec.attack_example, attack)).oracle
    assert calls["boundary"] == calls["specimen"] == [m._digest(attack)]
    assert (result.verdict, result.specimen) == (m.HELD, m.FIRED)
    assert result.specimen_digest is not None
    # Through the adapter's own oracle the same attempt reads the same.
    again = A.oracle(name, core.AttackInput(spec.attack_example, attack))
    assert (again.verdict, again.specimen) == (m.HELD, m.FIRED)


def test_the_oracle_speaks_only_the_conditions_vocabulary():
    assert set(m.CONDITION_OF.values()) <= CONDITIONS
    spec = A.family_spec("resource_accounting")
    attack = dict(spec.attacks())["seconds_one_hour"]
    with pytest.MonkeyPatch.context() as patch:
        _code_run_seconds_lifted(patch)
        reading = A.assess(spec, ("seconds_one_hour", attack))
    assert reading.reading == m.BREACH
    assert reading.oracle.condition == "FAILING_TRIGGER"


def test_an_observed_path_that_accepts_what_carbon_refuses_is_a_breach():
    outside = A.recipe_outside_contract()
    attempt = {
        "name": "session-1",
        "arguments": {"strategy_json": json.dumps(outside)},
        "path_accepted": True,
    }
    reading = A.assess("recipe_surface", attempt)
    assert reading.reading == m.BREACH and reading.observed
    assert reading.oracle.condition == "FAILING_TRIGGER"
    refused = A.assess("recipe_surface", {**attempt, "path_accepted": False})
    assert (refused.reading, refused.oracle.verdict) == (m.HELD, m.HELD)


def test_a_path_that_refuses_what_carbon_admits_and_runs_is_a_wrongful_refusal():
    attempt = {
        "name": "session-2",
        "arguments": {"strategy_json": json.dumps(m._scaffold())},
        "path_accepted": False,
    }
    reading = A.assess("recipe_surface", attempt)
    assert reading.reading == m.WRONGFUL_REFUSAL
    assert reading.oracle.condition == "FAILING_TRIGGER"
    unknown = A.assess("recipe_surface", {**attempt, "path_accepted": None})
    assert (unknown.reading, unknown.oracle.verdict) == (m.UNDETERMINED, m.INCONCLUSIVE)


def test_only_the_attacker_lane_is_judged_by_the_code_run_rule():
    over = {"kind": "code_run", "arguments": {"seconds": 3600}}
    attacker = {"name": "a", "value": over, "lane": m.ATTACKER_LANE}
    breach = A.assess("resource_accounting", {**attacker, "path_accepted": True})
    assert breach.reading == m.BREACH
    miner = A.assess(
        "resource_accounting", {**attacker, "lane": "miner", "path_accepted": True}
    )
    assert (miner.reading, miner.oracle.verdict) == (m.NOT_APPLICABLE, m.NOT_RUN)


def test_an_attempt_without_input_or_independent_gate_is_not_run():
    reading = A.assess("practice_disclosure", {"name": "x", "arguments": {}})
    assert (reading.reading, reading.oracle.verdict) == (m.NOT_APPLICABLE, m.NOT_RUN)
    observed = A.assess(
        "ripple_phase",
        {"name": "y", "value": {"predictions": {}}, "path_accepted": True},
    )
    assert observed.oracle.verdict == m.NOT_RUN


def test_a_hold_the_detector_cannot_vouch_for_is_inconclusive():
    spec = A.family_spec("ripple_phase")
    blind = dataclasses.replace(spec, specimen=spec.boundary)
    name, attack = spec.attacks()[0]
    reading = A.assess(blind, (name, attack))
    assert reading.reading == m.HELD
    assert (reading.oracle.verdict, reading.oracle.specimen) == (
        m.INCONCLUSIVE,
        m.SILENT,
    )


def test_a_boundary_that_does_not_answer_is_never_a_pass():
    spec = A.family_spec("population_screen")

    def infra(_value):
        raise engine.InfrastructureFailure("screen host down")

    def crash(_value):
        raise KeyError("screen defect")

    name, attack = spec.attacks()[0]
    for broken, verdict in ((infra, "FAILED_INFRA"), (crash, "CRASHED")):
        reading = A.assess(dataclasses.replace(spec, boundary=broken), (name, attack))
        assert reading.oracle.verdict == verdict and reading.condition is None


def test_protected_material_is_withheld_and_only_an_exposure_when_it_got_through():
    named = m._strategy(weights="hidden_case_answers")
    declared = A.assess("recipe_surface", ("named", named))
    assert (declared.reading, declared.oracle.verdict) == (
        m.PROTECTED_WITHHELD,
        m.NOT_RUN,
    )
    attempt = {
        "name": "z",
        "arguments": {"strategy_json": json.dumps(named)},
        "path_accepted": False,
    }
    refused = A.assess("recipe_surface", attempt)
    assert refused.reading == m.PROTECTED_WITHHELD and refused.condition is None
    accepted = A.assess("recipe_surface", {**attempt, "path_accepted": True})
    assert accepted.reading == m.EXPOSURE
    assert accepted.oracle.condition == "OTHER_SIGNAL"
    leaked = A.assess(
        "practice_disclosure",
        {"name": "r", "arguments": {}, "result": {"note": "hidden_case 4"}},
    )
    assert leaked.reading == m.EXPOSURE


def test_a_crash_in_carbons_own_gate_is_never_a_hold(monkeypatch):
    from carbon.reconstruction import challenge_contracts

    def broken(strategy, **kwargs):
        raise KeyError("gate defect")

    monkeypatch.setattr(challenge_contracts, "compile_submission", broken)
    spec = A.family_spec("permission_ablation")
    for name, item in spec.attacks():
        reading = A.assess(spec, (name, item))
        assert reading.oracle.verdict == "CRASHED", name


# -- the Test Lead's motor vectors -----------------------------------------------------------------
VECTORS = A.vectors()


def test_every_motor_vector_from_the_test_lead_is_mapped():
    assert set(VECTORS) == {
        "flat_curve_right_mean",
        "phase_shifted_ripple",
        "flipped_period_or_orientation",
        "saturation_blind_linear_iron",
        "ripple_scaled_to_game_normalised_error",
    }
    seams = {s.name: s for s in A.level_families()}
    for name, vector in VECTORS.items():
        assert vector["check"] in CHECKS[m.TRACK]
        for family in vector["families"]:
            assert family in SPECS, (name, family)
        primary = SPECS[vector["families"][0]]
        assert primary.check == vector["check"]
        assert set(vector["also"]) <= set(vector["families"][1:]), name
        if vector["seam"] is None:
            # Covered whole by registered gates and the registered score.
            continue
        seam = seams[vector["seam"]]
        assert seam.state == core.NOT_RUN and seam.level == 0
        assert "reserved: owner" in seam.reason, name


@pytest.mark.parametrize("name", sorted(VECTORS))
def test_each_motor_vector_has_an_attack_and_a_control_with_expected_verdicts(name):
    """Each vector's attack example (and each further attack it maps to in
    another family) is HELD at the real boundary and FIRES the vulnerable
    specimen; its valid control (trained and held-out) PASSES the real
    boundary."""
    vector = VECTORS[name]
    expected = vector["expected"]
    spec = SPECS[vector["families"][0]]
    trained = {x.name for x in A.controls("trained") if x.family == spec.name}
    assert vector["control"] in trained
    mapped = {spec.name: vector["attack"], **vector["also"]}
    for family, attack_name in mapped.items():
        family_spec = SPECS[family]
        attack = dict(family_spec.attacks())[attack_name]
        reading = A.assess(family_spec, (attack_name, attack)).oracle
        assert reading.verdict == expected["real_boundary"] == m.HELD, attack_name
        assert reading.specimen == expected["vulnerable_specimen"] == m.FIRED
        for split in m.SPLITS:
            controls = [x for x in A.controls(split) if x.family == family]
            assert controls
            for control in controls:
                outcome = engine.PASSED if control.check() else engine.REFUSED
                assert outcome == expected["control"] == engine.PASSED, control.name


def test_the_vector_attacks_carry_what_their_names_say():
    """The attacks are what the vectors describe, read from the public
    references: a flat curve keeps each case's mean, a shifted or reversed
    curve keeps its values, a rescaled ripple keeps its shape and mean, the
    linear-iron curve promises more torque on the important group only, and
    a flipped curve's sign is reversed."""
    from statistics import fmean

    exact = m._oracle_predictions()
    important = m._important_ids()
    assert important and important != set(exact)
    flat = m._flat()
    shifted = m._rolled(m.ANGLE_STEPS // 4)
    reversed_ = m._reversed()
    halved = m._ripple_scaled(0.5)
    linear = m._linear_in_current()
    flipped = m._negated()
    for case, p in exact.items():
        curve = p["torque_nm"]
        assert set(flat[case]["torque_nm"]) == {fmean(curve)}
        assert sorted(shifted[case]["torque_nm"]) == sorted(curve)
        assert shifted[case]["torque_nm"] != curve
        assert reversed_[case]["torque_nm"] == curve[::-1]
        assert m._same(fmean(halved[case]["torque_nm"]), fmean(curve))
        assert flipped[case]["torque_nm"] == [-t for t in curve]
        promised = fmean(linear[case]["torque_nm"]) - fmean(curve)
        if case in important:
            assert promised >= 0
        else:
            assert promised == 0
    view = m.score_view({"predictions": linear, "where": "important"})
    assert view["important_mean_bias_nm"] > 0 and view["score"] > 0


def test_the_population_attacks_are_outside_the_box_or_unbuildable():
    from carbon.motor import domain

    for name, value in A.family_spec("population_screen").attacks():
        case = value["case"]
        try:
            domain.check_inputs(case)
        except ValueError:
            continue
        assert domain.validity(case), name


def test_vectors_that_need_an_owner_value_invent_none():
    """The vector seams name what is missing; the adapter pins no tolerance,
    weight or limit of its own (only copies of registered values)."""
    for vector in VECTORS.values():
        if vector["seam"] is None:
            continue
        seam = next(s for s in m.SEAMS if s.name == vector["seam"])
        assert seam.reserved_decision and seam.reserved_decision.startswith("owner")
    numbers = {
        name: value
        for name, value in vars(m).items()
        if name.isupper() and type(value) in (int, float)
    }
    assert numbers == {
        "LEVEL": 0,
        "CODE_RUN_SECONDS": 600,
        "ANGLE_STEPS": 60,
        "J_IMPORTANT": 10.0,
    }


def test_a_partial_prediction_set_is_a_gate_failure_never_a_pass():
    """GRAPHITE-COVERAGE-PARITY-02: every case a set leaves out, or gives
    null, is a schema-gate failure, never FAILED_INFRA and never excluded, so
    a partial set is never eligible (before it, an omitted case was
    FAILED_INFRA and excluded)."""
    value = {"kind": "scoring", "predictions": {}, "partial": True}
    result = m.resource_boundary(value)
    assert not result["eligible"]
    assert result["n_failed_infra"] == 0
    assert result["n_gate_failed"] == result["n_cases"] == 30
    half = m._half_predictions()
    nulls = {case: None for case in m._oracle_predictions()}
    for predictions in (half, {**nulls, **half}):
        read = m.resource_boundary(
            {"kind": "scoring", "predictions": predictions, "partial": True}
        )
        assert not read["eligible"] and read["n_failed_infra"] == 0
        assert read["n_gate_failed"] == read["n_cases"] - read["n_scored"] == 15
        assert not m.resource_breached(read)
    assert m.resource_breached(m.resource_specimen(value))


def test_the_adapter_scores_through_motors_frozen_rule():
    """`_score` is Graphite's frozen rule for motor (`MotorPracticeRule`),
    whose identity names the coverage rule; a complete exact set is eligible
    with nothing missing."""
    from carbon.challenge_validator import scoring
    from carbon.challenge_validator.motor_scoring import MotorPracticeRule

    rule = m._frozen_rule()
    assert isinstance(rule, MotorPracticeRule)
    assert rule.identity["coverage"] == scoring.COVERAGE_RULE
    _rows, summary = m._score(m._oracle_predictions())
    assert summary["eligible"] and summary["n_missing"] == 0
    assert summary["n_scored"] == summary["n_cases"] == 30


def test_a_code_run_is_refused_before_dispatch_above_the_wall_allowance():
    assert A.code_run_refusal({"seconds": m.CODE_RUN_SECONDS}) is None
    assert A.code_run_refusal({"seconds": m.CODE_RUN_SECONDS + 1}) == (
        "code_run_needs_seconds_up_to_600"
    )
    assert A.code_run_refusal("seconds=1") == "code_run_arguments_unreadable"


# -- rebuild ------------------------------------------------------------------------------------
def test_carbon_rebuilds_with_its_own_build_record_and_refuses_with_a_typed_code():
    from carbon.challenge_validator.scoring import REBUILT_FIELDS

    rebuilt = A.rebuild(m._scaffold())
    assert type(rebuilt) is core.Rebuilt
    assert set(REBUILT_FIELDS) <= set(rebuilt.detail["record"])
    assert rebuilt.detail["record"]["contract_digest"] == A.contract_digest
    assert A.rebuild(m._scaffold()).rebuilt_digest == rebuilt.rebuilt_digest
    other = A.rebuild(m._strategy(length="length_8"))
    assert other.rebuilt_digest != rebuilt.rebuilt_digest
    refusals = {
        "outside": (A.recipe_outside_contract(), "refused_by_contract"),
        "withheld": (m._strategy(loss_expressions=True), "outside_level"),
        "text": (json.dumps(m._scaffold()), "not_declarative"),
        "nonfinite": (m._strategy(ridge=float("nan")), "not_declarative"),
        "other": ({**m._scaffold(), "challenge_id": "x-y"}, "unknown_construction"),
        "cooling": (
            {**m._scaffold(), "challenge_id": "chip-cold-plate"},
            "unknown_construction",
        ),
        "seed": ({"strategy": m._scaffold(), "seed": -1}, "unknown_construction"),
        "protected": (m._strategy(weights="hidden_case"), "protected_material"),
    }
    for label, (construction, code) in refusals.items():
        out = A.rebuild(construction)
        assert type(out) is core.Unrebuildable, label
        assert out.code == code and out.code in core.UNREBUILDABLE_CODES, label


def test_a_stale_contract_record_is_carbons_side_never_the_constructions(monkeypatch):
    from carbon.reconstruction import expansion_record

    monkeypatch.setattr(expansion_record, "records", lambda challenge: [])
    m.clear_caches()
    out = A.rebuild(m._scaffold())
    assert out.code == "rebuild_failed_infra"
    assert A.carbon_code(out) == "construction_contract_unrecorded"


def test_motor_public_scoring_is_registered_but_attack_rebuild_launches_no_pod():
    from carbon.challenge_validator import scoring

    assert scoring.scoring_for(m.CHALLENGE_ID).challenge_id == m.CHALLENGE_ID
    assert m.pod_scoring_code() is None
    detail = A.rebuild(m._scaffold()).detail
    assert detail["served"] is True
    assert detail["pod_scoring"] is None
    assert not any(s.name == "pod_scoring_not_registered" for s in A.level_families())


def _refused(argv, tmp_path):
    from carbon.agent_campaign.graphite import phase4

    out = io.StringIO()
    with redirect_stdout(out), pytest.raises(SystemExit) as stopped:
        phase4.main(argv)
    assert stopped.value.code == 2
    lines = [json.loads(x) for x in out.getvalue().splitlines() if x.startswith("{")]
    return lines[-1], tmp_path


def test_higher_level_families_are_not_run_seams_with_nothing_to_execute():
    seams = A.level_families()
    assert {s.level for s in seams} == {0, 1, 2, 3, 4, 5}
    for seam in seams:
        assert seam.state == core.NOT_RUN
        result = A.oracle(seam.name, core.AttackInput("x", {"anything": 1}))
        assert result.verdict == core.NOT_RUN and result.specimen is None
    for seam in m.SEAMS:
        if seam.level >= 3:
            assert "participant code" in seam.reason
            assert seam.reserved_decision.startswith("security owner")


def test_a_research_tool_call_maps_to_the_family_it_probes():
    from carbon.development_session.research_tools import PREFIX

    assert A.family_for(PREFIX + "dry_validate") == "recipe_surface"
    assert A.family_for(PREFIX + "get_research_result") == "practice_disclosure"
    run = {"action": "run_python"}
    assert A.family_for(PREFIX + "start_research_task", run) == "resource_accounting"
    design = {"action": "check_design"}
    assert A.family_for(PREFIX + "start_research_task", design) == (
        "permission_ablation"
    )
    assert A.family_for(PREFIX + "unknown_tool") is None


# -- pinned values --------------------------------------------------------------------------------
def test_each_pinned_value_is_a_copy_of_its_motor_source():
    from carbon.challenge_validator import scoring
    from carbon.motor import domain, exam, practice, research

    assert m.CODE_RUN_SECONDS == research.PRACTICE_SECONDS
    assert m.ANGLE_STEPS == domain.ANGLE_STEPS
    assert m.J_IMPORTANT == exam.J_IMPORTANT
    assert m.TAMPER_FIELDS == scoring.REBUILT_FIELDS
    assert m.STAGED_NAMES == set(practice.STAGED_MODULES) | {
        "train-v1.jsonl",
        "practice-inputs.json",
        "recipe.json",
    }
    probe = m._probe(m._oracle_predictions())
    assert set(probe) == m.PRACTICE_FEEDBACK_FIELDS
    assert set(probe["summary"]) == m.PRACTICE_SUMMARY_FIELDS
    assert {k: probe[k] for k in m.PRACTICE_FLAGS} == m.PRACTICE_FLAGS
    assert set(exam.COMPONENTS) == {"mean", "ripple"}
    assert m.UNBUILDABLE_CORNER.keys() == set(domain.INPUTS)
    assert A.permission_inventory()["not_permitted"] == list(m._capability_index()[3])


# -- sealed identities and material ---------------------------------------------------------------
def _emitted():
    """Every string-bearing value the adapter emits: family names, boundary
    texts, attack names and inputs, control names and inputs, seams, the
    vector map, the surface and a rebuild record."""
    out = []
    for spec in A.family_specs():
        out += [spec.name, spec.protocol_family, spec.reads, spec.attack_example]
        out += [[n, v] for n, v in spec.attacks()]
    for split in m.SPLITS:
        out += [[x.name, x.value()] for x in A.control_specs(split)]
    out += [[s.name, s.reason] for s in A.level_families()]
    out += [A.vectors(), A.surface(), A.rebuild(m._scaffold()).detail]
    return out


def test_no_sealed_identity_is_named_by_the_adapter():
    """Nothing the adapter emits, and nothing in its source, names a
    registered sealed identity (`knowledge.SEALED_IDENTITIES`): motor's
    private-pool commitment never appears."""
    entry = next(
        e
        for e in knowledge.SEALED_IDENTITIES
        if e["id"] == "motor-private-pool-commitment"
    )
    hex_value = entry["value"].removeprefix("sha256:")
    texts = list(knowledge._strings(_emitted()))
    texts.append(Path(m.__file__).read_text(encoding="utf-8"))
    for text in texts:
        assert knowledge.sealed_identity(text) is None, text[:120]
        assert hex_value not in text.lower(), text[:120]
    assert not knowledge.sealed(_emitted())
    # The check is live: the registered commitment is recognised.
    assert knowledge.sealed_identity(entry["value"]) == entry["id"]


def test_nothing_the_adapter_names_is_protected_material():
    named = []
    for spec in A.family_specs():
        named += [spec.name, spec.protocol_family, spec.reads]
        named += [n for n, _ in spec.attacks()]
    named += [x.name for x in A.controls("trained") + A.controls("held_out")]
    named += [s.name + " " + s.reason for s in A.level_families()]
    named += list(VECTORS)
    leaked = [text for text in named if m._protected(text)]
    assert not leaked, leaked


#: Repository material the adapter must never open: the private pool's
#: commitment, the decision study and its references, counted or pilot
#: GetDP runs, customer material and anything confirmation or sealed.
DENIED_READS = re.compile(
    r"pools\.json|decision|customer|reference_campaign|motor-pilot|motor-rungs"
    r"|counted|confirmation|private|seal|freeze|MOTOR_SYNTHETIC",
    re.IGNORECASE,
)
#: The only evidence files it may open: motor's public TRAIN and PRACTICE
#: records and the public calibration document their loader checks.
PUBLIC_MATERIAL = {
    "docs/development/evidence/motor-pools-v1/train.jsonl",
    "docs/development/evidence/motor-pools-v1/practice.jsonl",
    "docs/development/evidence/motor-pools-v1/baselines.json",
}
_OPENED = []
_RECORDING = []


def _audit(event, args):
    if _RECORDING and event == "open" and args and isinstance(args[0], str | bytes):
        _OPENED.append(args[0] if isinstance(args[0], str) else args[0].decode())


def test_the_adapter_reads_public_train_and_practice_only(tmp_path):
    """Every file the adapter opens while it runs every attack, specimen and
    control, its rebuild, its held-out measurement and its session surface is
    recorded (an audit hook): no data file but the public TRAIN and PRACTICE
    records (and the calibration document) is opened, nothing is study,
    counted, private-pool or sealed material, and the TRAIN and PRACTICE
    records are among the files read."""
    if not getattr(sys, "_motor_attack_audit", False):
        sys.addaudithook(_audit)
        sys._motor_attack_audit = True
    m.clear_caches()
    _OPENED.clear()
    _RECORDING.append(True)
    try:
        for spec in A.family_specs():
            for name, value in spec.attacks():
                A.assess(spec, (name, value))
        for split in m.SPLITS:
            for control in A.controls(split):
                control.check()
        core.held_out_outcomes(A)
        A.rebuild(m._scaffold())
        A.permission_inventory()
        A.admission_refusals(A.recipe_outside_contract())
    finally:
        _RECORDING.clear()
    root = str(REPOSITORY)
    inside = sorted(
        {p[len(root) + 1 :] for p in _OPENED if p.startswith(root + "/")}
        | {p for p in _OPENED if not p.startswith("/")}
    )
    denied = [p for p in inside if DENIED_READS.search(p)]
    assert not denied, denied
    evidence = {p for p in inside if p.startswith("docs/")}
    assert evidence <= PUBLIC_MATERIAL, sorted(evidence - PUBLIC_MATERIAL)
    assert any(p.endswith("motor-pools-v1/train.jsonl") for p in inside)
    assert any(p.endswith("motor-pools-v1/practice.jsonl") for p in inside)


# -- mutations: each disabled boundary turns its guard red -----------------------------------------
_UNKNOWN = {"weights", "iron_bh_curve", "skew_deg"}


def _gate_admits_withheld_permissions(patch):
    from types import SimpleNamespace

    from carbon.reconstruction import challenge_contracts

    original = challenge_contracts.compile_submission

    def lax(strategy, **kwargs):
        try:
            return original(strategy, **kwargs)
        except challenge_contracts.SubmissionRefused:
            recipe = SimpleNamespace(recipe_digest="sha256:" + "0" * 64)
            return SimpleNamespace(construction=recipe)

    patch.setattr(challenge_contracts, "compile_submission", lax)


def _gate_accepts_unknown_field(patch):
    from carbon.reconstruction import challenge_contracts

    original = challenge_contracts.compile_submission

    def lax(strategy, **kwargs):
        if isinstance(strategy, dict) and isinstance(strategy.get("parameters"), dict):
            kept = {
                k: v for k, v in strategy["parameters"].items() if k not in _UNKNOWN
            }
            strategy = {**strategy, "parameters": kept}
        return original(strategy, **kwargs)

    patch.setattr(challenge_contracts, "compile_submission", lax)


def _recipe_token_unchecked(patch):
    from carbon.motor import compile as motor_compile

    patch.setattr(motor_compile.MotorRecipe, "__post_init__", lambda self: None)


def _aggregate(change):
    from carbon.motor import exam

    original = exam.aggregate

    def mutated(rows):
        out = original(rows)
        return {**out, **change(out)}

    return mutated


def _averaging_scorer(patch):
    from carbon.motor import exam

    patch.setattr(
        exam, "aggregate", _aggregate(lambda o: {"eligible": o["n_scored"] > 0})
    )


def _motoring_gate_disabled(patch):
    from carbon.motor import exam

    original = exam.gates

    def lax(prediction, twin=None):
        out = original(prediction, twin)
        if "motoring_mean_nonnegative" in out:
            out["motoring_mean_nonnegative"] = exam.PASS
        return out

    patch.setattr(exam, "gates", lax)


def _guard_sign_flip():
    spec = A.family_spec("mandatory_failure")
    attacks = dict(spec.attacks())
    for name in (
        "torque_sign_flipped_on_every_case",
        "torque_sign_flipped_on_the_most_loaded_case",
    ):
        reading = A.assess(spec, (name, attacks[name]))
        assert (reading.reading, reading.oracle.verdict) == (m.HELD, m.HELD), name


def _missing_prediction_typed_failed_infra(patch):
    """Motor's frozen rule excludes a missing case again, the typing before
    GRAPHITE-COVERAGE-PARITY-02: motor's scoring reads `cover` from its own
    module."""
    from carbon.challenge_validator import motor_scoring

    def excluding(predictions, case_ids):
        source = predictions if isinstance(predictions, dict) else {}
        return {case: source.get(case) for case in case_ids}, []

    patch.setattr(motor_scoring, "cover", excluding)


def _saturation_bias_dropped(patch):
    from carbon.motor import exam

    patch.setattr(
        exam, "aggregate", _aggregate(lambda o: {"important_mean_bias_nm": None})
    )


def _components(change):
    from carbon.motor import exam

    original = exam.case_components

    def mutated(prediction, reference, scales):
        return change(original(prediction, reference, scales), prediction, reference)

    return mutated


def _ripple_left_out(patch):
    from carbon.motor import exam

    patch.setattr(
        exam,
        "case_components",
        _components(lambda out, _p, _r: {**out, "ripple": 0.0}),
    )


def _ripple_compared_sorted(patch):
    """The ripple graded by its sorted values: phase-blind."""
    import math
    from statistics import fmean

    from carbon.motor import exam

    def phase_blind(out, prediction, reference):
        p = [float(t) for t in prediction["torque_nm"]]
        r = list(reference["outputs"]["torque_nm"])
        p_rest = sorted(t - fmean(p) for t in p)
        r_rest = sorted(t - fmean(r) for t in r)
        rms = math.sqrt(fmean((a - b) ** 2 for a, b in zip(p_rest, r_rest)))
        scale = exam.scales_from_train(m._material().train)["s_ripple"]
        return {**out, "ripple": 0.0 if rms < 1e-9 else rms / scale}

    patch.setattr(exam, "case_components", _components(phase_blind))


def _ripple_normalised_by_own_amplitude(patch):
    """The ripple graded after each is normalised by its own amplitude."""
    import math
    from statistics import fmean

    from carbon.motor import exam

    def gameable(out, prediction, reference):
        p = [float(t) for t in prediction["torque_nm"]]
        r = list(reference["outputs"]["torque_nm"])
        p_rest = [t - fmean(p) for t in p]
        r_rest = [t - fmean(r) for t in r]
        p_rms = math.sqrt(fmean(t * t for t in p_rest)) or 1.0
        r_rms = math.sqrt(fmean(t * t for t in r_rest)) or 1.0
        diff = [a / p_rms - b / r_rms for a, b in zip(p_rest, r_rest)]
        rms = math.sqrt(fmean(d * d for d in diff))
        return {**out, "ripple": 0.0 if rms < 1e-9 else rms}

    patch.setattr(exam, "case_components", _components(gameable))


def _screen_disabled(patch):
    from carbon.motor import population

    # The screen reads `validity` through its own module binding.
    patch.setattr(population, "validity", lambda case: [])


def _box_disabled(patch):
    from carbon.motor import population

    patch.setattr(population, "admitted", lambda case: True)


def _code_run_seconds_lifted(patch):
    patch.setattr(m, "CODE_RUN_SECONDS", 10**6)


def _motor_wall_allowance_lifted(patch):
    from carbon.motor import research

    patch.setattr(research, "PRACTICE_SECONDS", 3600)


def _important_floor_moved(patch):
    from carbon.motor import exam

    patch.setattr(exam, "J_IMPORTANT", 12.0)


def _feedback_field_added(patch):
    from carbon.motor import practice

    original = practice.feedback

    def wider(*args, **kwargs):
        return {**original(*args, **kwargs), "screening": {"pool_version": 3}}

    patch.setattr(practice, "feedback", wider)


def _leaky_stager(patch):
    from carbon.motor import practice

    original = practice.staged_files

    def leaky(root, practice_set, recipe):
        files = original(root, practice_set, recipe)
        return {**files, "practice.jsonl": practice_set.public_bytes()}

    patch.setattr(practice, "staged_files", leaky)


def _recipe_digest_drops_settings(patch):
    from carbon.motor import compile as motor_compile

    patch.setattr(
        motor_compile.MotorRecipe,
        "recipe_digest",
        property(lambda self: m._digest({"family": self.family})),
    )


def _rebuilt_field_dropped(patch):
    from carbon.challenge_validator import scoring

    patch.setattr(
        scoring,
        "REBUILT_FIELDS",
        tuple(f for f in scoring.REBUILT_FIELDS if f != "program"),
    )


def _material_digest_unchecked(patch):
    from carbon.motor import challenge

    def trusting(path, expected, name):
        return Path(path).read_bytes().replace(b"\r\n", b"\n")

    patch.setattr(challenge, "canonical_text", trusting)


def _protected_marker_removed(patch):
    # The check reads the leaf module's markers; `tools` only re-exports them,
    # so patching `tools` would disable nothing.
    from carbon.agent_campaign.graphite import protected_material

    patch.setattr(
        protected_material,
        "PROTECTED_MARKERS",
        tuple(x for x in protected_material.PROTECTED_MARKERS if "hidden" not in x),
    )


def _non_conditions_finding(patch):
    patch.setitem(m.CONDITION_OF, m.BREACH, "EXPLOIT_CONFIRMED")


def _engine_reads_held_out(patch):
    def leaky(self, name):
        spec = self.family_spec(name)
        return lambda: all(
            spec.control_check(x.value())
            for split in m.SPLITS
            for x in self.control_specs(split)
            if x.family == name
        )

    patch.setattr(m.MotorLevel0Adapter, "trained_control", leaky)


def _gate_swallows_crashes(patch):
    original = m.gate

    def lax(strategy):
        try:
            return original(strategy)
        except Exception as crashed:  # noqa: BLE001 - the mutation under test
            return {"status": "REFUSED", "codes": [(type(crashed).__name__, "")]}

    patch.setattr(m, "gate", lax)


def _guard_gate_crash():
    with pytest.MonkeyPatch.context() as patch:
        test_a_crash_in_carbons_own_gate_is_never_a_hold(patch)


def _guard_trained_split_only():
    with pytest.MonkeyPatch.context() as patch:
        test_the_engine_control_reads_the_trained_split_only(patch)


MUTATIONS = {
    "gate_admits_withheld_permissions": (
        _gate_admits_withheld_permissions,
        lambda: _held_and_fired("permission_ablation"),
    ),
    "gate_accepts_an_unknown_field": (
        _gate_accepts_unknown_field,
        lambda: _held_and_fired("recipe_surface"),
    ),
    "recipe_token_unchecked": (
        _recipe_token_unchecked,
        lambda: _held_and_fired("recipe_forgery"),
    ),
    "feedback_field_added": (
        _feedback_field_added,
        lambda: _held_and_fired("practice_disclosure"),
    ),
    "averaging_scorer": (
        _averaging_scorer,
        lambda: _held_and_fired("mandatory_failure"),
    ),
    "motoring_gate_disabled": (_motoring_gate_disabled, _guard_sign_flip),
    "ripple_left_out_of_the_score": (
        _ripple_left_out,
        lambda: _held_and_fired("ripple_omission"),
    ),
    "ripple_compared_phase_blind": (
        _ripple_compared_sorted,
        lambda: _held_and_fired("ripple_phase"),
    ),
    "ripple_normalised_by_its_own_amplitude": (
        _ripple_normalised_by_own_amplitude,
        lambda: _held_and_fired("ripple_scaling"),
    ),
    "saturation_bias_dropped": (
        _saturation_bias_dropped,
        lambda: _held_and_fired("saturation_optimism"),
    ),
    "population_geometry_screen_disabled": (
        _screen_disabled,
        lambda: _held_and_fired("population_screen"),
    ),
    "population_box_disabled": (
        _box_disabled,
        lambda: _held_and_fired("population_screen"),
    ),
    "code_run_seconds_lifted": (
        _code_run_seconds_lifted,
        lambda: _held_and_fired("resource_accounting"),
    ),
    # GRAPHITE-COVERAGE-PARITY-02 retired `failed_infra_counted_as_a_pass`: a
    # partial set no longer has FAILED_INFRA cases to count. Its successor
    # restores the old typing itself.
    "missing_prediction_typed_failed_infra": (
        _missing_prediction_typed_failed_infra,
        test_a_partial_prediction_set_is_a_gate_failure_never_a_pass,
    ),
    "missing_prediction_excluded_from_resource_accounting": (
        _missing_prediction_typed_failed_infra,
        lambda: _held_and_fired("resource_accounting"),
    ),
    "motor_wall_allowance_lifted": (
        _motor_wall_allowance_lifted,
        test_each_pinned_value_is_a_copy_of_its_motor_source,
    ),
    "important_floor_moved": (
        _important_floor_moved,
        test_each_pinned_value_is_a_copy_of_its_motor_source,
    ),
    "leaky_stager": (_leaky_stager, lambda: _held_and_fired("staged_bytes")),
    "recipe_digest_drops_settings": (
        _recipe_digest_drops_settings,
        lambda: _held_and_fired("rebuild_identity"),
    ),
    "rebuilt_field_dropped": (
        _rebuilt_field_dropped,
        lambda: _held_and_fired("rebuild_report"),
    ),
    "material_digest_unchecked": (
        _material_digest_unchecked,
        lambda: _held_and_fired("package_integrity"),
    ),
    "protected_marker_removed": (
        _protected_marker_removed,
        test_protected_material_is_withheld_and_only_an_exposure_when_it_got_through,
    ),
    "non_conditions_finding": (
        _non_conditions_finding,
        test_the_oracle_speaks_only_the_conditions_vocabulary,
    ),
    "gate_crash_read_as_a_refusal": (_gate_swallows_crashes, _guard_gate_crash),
    "engine_reads_held_out_controls": (
        _engine_reads_held_out,
        _guard_trained_split_only,
    ),
}


def test_every_family_has_a_mutation():
    """Each run family's guard is the target of at least one mutation."""
    families = set()
    for _mutate, guard in MUTATIONS.values():
        code = getattr(guard, "__code__", None)
        if code is not None:
            families.update(x for x in code.co_consts if x in SPECS)
    assert families == set(SPECS), set(SPECS) - families


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_each_disabled_boundary_turns_its_guard_red(name, monkeypatch):
    mutate, guard = MUTATIONS[name]
    m.clear_caches()
    try:
        mutate(monkeypatch)
        with pytest.raises((AssertionError, ValueError)):
            guard()
    finally:
        monkeypatch.undo()
        m.clear_caches()


def test_every_guard_passes_without_its_mutation():
    """The other half of the mutation check: unmutated, each guard holds."""
    for _mutate, guard in MUTATIONS.values():
        guard()
