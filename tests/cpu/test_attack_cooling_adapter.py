"""Cooling's Level 0 attack adapter (OWNER-GRAPHITE-ATTACKER-01; the Graphite
test wave's cooling row).

The claims tested:
- the adapter is registered by `(chip-cold-plate, 0)`, names the live contract
  read only, and carries the session surface a Graphite session needs;
- every Track A check is covered by a family or a declared NOT_RUN seam; every
  run check names an attack example and a valid control; every family has a
  trained and a held-out control, versioned, and the held-out controls are
  canonically distinct from the trained ones and refused by the engine;
- every attack is held by the real boundary, every specimen fires, every
  control passes; the oracle tries each attempt against both the real
  boundary and the vulnerable specimen;
- the Test Lead's cooling vectors each map to a check, run where a boundary is
  registered, and name the owner value they still need as a NOT_RUN seam;
- the oracle emits only the CONDITIONS vocabulary, as battery's does;
- Carbon rebuilds with `experiment.admit` and refuses with a typed code;
- no sealed identity is named, and no sealed or study material is read;
- each pinned value is a copy of its cooling source;
- the phase-4 dry run runs end to end at cooling with nothing spent;
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
from carbon.agent_campaign.attack.adapters import cooling as c
from carbon.challenge_readiness.admission import CHECKS, CONDITIONS

A = c.ADAPTER
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
        if (r.reading, r.oracle.verdict) != (c.HELD, c.HELD)
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
def test_the_registry_loads_cooling_level_0_and_refuses_anything_else():
    assert adapters.load(c.CHALLENGE_ID, 0) is A
    assert (c.CHALLENGE_ID, 0) in adapters.registered()
    with pytest.raises(adapters.AdapterNotRegistered):
        adapters.load(c.CHALLENGE_ID, 1)
    assert core.get(c.CHALLENGE_ID, 0) is A
    assert core.validate(A) is A
    assert isinstance(A, core.Adapter) and isinstance(A, core.SessionSurface)
    coverage = core.coverage(A)
    assert coverage["fresh_attack_confirmation"]["not_run"] == ["fresh_cases_rerun"]


def test_the_adapter_names_the_live_contract_read_only():
    from carbon.reconstruction.capability_registry import (
        COLD_PLATE_CHALLENGE,
        contract_digest,
    )

    assert (A.challenge_id, A.level) == (COLD_PLATE_CHALLENGE, 0)
    assert A.contract_digest == contract_digest(COLD_PLATE_CHALLENGE)
    surface = A.surface()
    assert surface["profile"] == "level-0"
    assert surface["contract_digest"] == A.contract_digest
    assert surface["submission_form"].startswith("declarative strategy only")
    assert surface["adapter_version"] == c.ADAPTER_VERSION


def test_the_session_surface_is_carbons_own_admission():
    from carbon.cold_plate.challenge import CHALLENGE
    from carbon.cold_plate.research import SCAFFOLD

    inventory = A.permission_inventory()
    assert (inventory["profile"], inventory["challenge"]) == ("level-0", c.CHALLENGE_ID)
    assert A.public_identity() == {"id": CHALLENGE.challenge_id, "version": "1.0"}
    assert A.code_run_seconds() == c.CODE_RUN_SECONDS
    assert A.admission_refusals(SCAFFOLD) == []
    outside = A.admission_refusals(A.recipe_outside_contract())
    assert outside[0] == "contract_refused" and "backbone.not_in_contract" in outside
    assert A.admission_refusals(c._strategy(loss_expressions=True)) == [
        "contract_refused",
        "parameter.not_rebuildable",
    ]


# -- coverage of the eight checks -----------------------------------------------------------------
def test_every_track_a_check_is_covered_by_a_family_or_a_not_run_seam():
    checks = A.checks()
    assert set(checks) == CHECKS[c.TRACK]
    assert all(checks.values())
    assert checks["fresh_attack_confirmation"] == ("fresh_cases_rerun:NOT_RUN",)
    assert {f.check for f in A.families()} == CHECKS[c.TRACK] - {
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
    for check in CHECKS[c.TRACK]:
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
    for split in c.SPLITS:
        assert [x for x in A.controls(split) if x.family == name], split


def test_controls_are_split_disjoint_and_versioned():
    trained, held = A.controls("trained"), A.controls("held_out")
    assert {x.name for x in trained}.isdisjoint({x.name for x in held})
    assert {x.version for x in trained + held} == {c.CONTROLS_VERSION}
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
        seen = {c._canonical(x.value()) for x in trained}
        for control in held:
            assert c._canonical(control.value()) not in seen, control.name
    identities = {x.identity for x in A.controls("trained")}
    assert identities.isdisjoint({x.identity for x in A.controls("held_out")})


@pytest.mark.parametrize("name", sorted(SPECS))
def test_the_engine_refuses_held_out_controls_even_relabelled(name):
    core.register_held_out_identities(A)
    family = A.family_spec(name)
    definition = next(f for f in A.families() if f.name == family.name)
    held = [x for x in A.controls("held_out") if x.family == name]
    with pytest.raises(engine.HeldOutControlRefused):
        engine.run_family(definition.family, budget=0, controls=held)
    relabelled = [dataclasses.replace(x, split="trained") for x in held]
    with pytest.raises(engine.HeldOutControlRefused):
        engine.run_family(definition.family, budget=0, controls=relabelled)


@pytest.mark.parametrize("split", c.SPLITS)
def test_every_control_passes(split):
    for name in SPECS:
        _controls_pass(name, split)


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
            calls[role].append(c._digest(value))
            return call(value)

        return run

    watched = dataclasses.replace(
        spec,
        boundary=counting("boundary", spec.boundary),
        specimen=counting("specimen", spec.specimen),
    )
    attack = dict(spec.attacks())[spec.attack_example]
    result = A.assess(watched, (spec.attack_example, attack)).oracle
    assert calls["boundary"] == calls["specimen"] == [c._digest(attack)]
    assert (result.verdict, result.specimen) == (c.HELD, c.FIRED)
    assert result.specimen_digest is not None
    # Through the adapter's own oracle the same attempt reads the same.
    again = A.oracle(name, core.AttackInput(spec.attack_example, attack))
    assert (again.verdict, again.specimen) == (c.HELD, c.FIRED)


def test_the_oracle_speaks_only_the_conditions_vocabulary():
    assert set(c.CONDITION_OF.values()) <= CONDITIONS
    spec = A.family_spec("resource_accounting")
    attack = dict(spec.attacks())["seconds_one_hour"]
    with pytest.MonkeyPatch.context() as m:
        _code_run_seconds_lifted(m)
        reading = A.assess(spec, ("seconds_one_hour", attack))
    assert reading.reading == c.BREACH
    assert reading.oracle.condition == "FAILING_TRIGGER"


def test_an_observed_path_that_accepts_what_carbon_refuses_is_a_breach():
    outside = A.recipe_outside_contract()
    attempt = {
        "name": "session-1",
        "arguments": {"strategy_json": json.dumps(outside)},
        "path_accepted": True,
    }
    reading = A.assess("recipe_surface", attempt)
    assert reading.reading == c.BREACH and reading.observed
    assert reading.oracle.condition == "FAILING_TRIGGER"
    refused = A.assess("recipe_surface", {**attempt, "path_accepted": False})
    assert (refused.reading, refused.oracle.verdict) == (c.HELD, c.HELD)


def test_a_path_that_refuses_what_carbon_admits_and_runs_is_a_wrongful_refusal():
    attempt = {
        "name": "session-2",
        "arguments": {"strategy_json": json.dumps(c._scaffold())},
        "path_accepted": False,
    }
    reading = A.assess("recipe_surface", attempt)
    assert reading.reading == c.WRONGFUL_REFUSAL
    assert reading.oracle.condition == "FAILING_TRIGGER"
    unknown = A.assess("recipe_surface", {**attempt, "path_accepted": None})
    assert (unknown.reading, unknown.oracle.verdict) == (c.UNDETERMINED, c.INCONCLUSIVE)


def test_only_the_attacker_lane_is_judged_by_the_code_run_rule():
    over = {"kind": "code_run", "arguments": {"seconds": 3600}}
    attacker = {"name": "a", "value": over, "lane": c.ATTACKER_LANE}
    breach = A.assess("resource_accounting", {**attacker, "path_accepted": True})
    assert breach.reading == c.BREACH
    miner = A.assess(
        "resource_accounting", {**attacker, "lane": "miner", "path_accepted": True}
    )
    assert (miner.reading, miner.oracle.verdict) == (c.NOT_APPLICABLE, c.NOT_RUN)


def test_an_attempt_without_input_or_independent_gate_is_not_run():
    reading = A.assess("practice_disclosure", {"name": "x", "arguments": {}})
    assert (reading.reading, reading.oracle.verdict) == (c.NOT_APPLICABLE, c.NOT_RUN)
    observed = A.assess(
        "mandatory_failure",
        {"name": "y", "value": {"predictions": {}}, "path_accepted": True},
    )
    assert observed.oracle.verdict == c.NOT_RUN


def test_a_hold_the_detector_cannot_vouch_for_is_inconclusive():
    spec = A.family_spec("cooling_optimism")
    blind = dataclasses.replace(spec, specimen=spec.boundary)
    name, attack = spec.attacks()[0]
    reading = A.assess(blind, (name, attack))
    assert reading.reading == c.HELD
    assert (reading.oracle.verdict, reading.oracle.specimen) == (
        c.INCONCLUSIVE,
        c.SILENT,
    )


def test_a_boundary_that_does_not_answer_is_never_a_pass():
    spec = A.family_spec("regime_screen")

    def infra(_value):
        raise engine.InfrastructureFailure("screen host down")

    def crash(_value):
        raise KeyError("screen defect")

    name, attack = spec.attacks()[0]
    for broken, verdict in ((infra, "FAILED_INFRA"), (crash, "CRASHED")):
        reading = A.assess(dataclasses.replace(spec, boundary=broken), (name, attack))
        assert reading.oracle.verdict == verdict and reading.condition is None


def test_protected_material_is_withheld_and_only_an_exposure_when_it_got_through():
    named = c._strategy(weights="hidden_case_answers")
    declared = A.assess("recipe_surface", ("named", named))
    assert (declared.reading, declared.oracle.verdict) == (
        c.PROTECTED_WITHHELD,
        c.NOT_RUN,
    )
    attempt = {
        "name": "z",
        "arguments": {"strategy_json": json.dumps(named)},
        "path_accepted": False,
    }
    refused = A.assess("recipe_surface", attempt)
    assert refused.reading == c.PROTECTED_WITHHELD and refused.condition is None
    accepted = A.assess("recipe_surface", {**attempt, "path_accepted": True})
    assert accepted.reading == c.EXPOSURE
    assert accepted.oracle.condition == "OTHER_SIGNAL"
    leaked = A.assess(
        "practice_disclosure",
        {"name": "r", "arguments": {}, "result": {"note": "hidden_case 4"}},
    )
    assert leaked.reading == c.EXPOSURE


def test_a_crash_in_carbons_own_gate_is_never_a_hold(monkeypatch):
    from carbon.reconstruction import challenge_contracts

    def broken(strategy, **kwargs):
        raise KeyError("gate defect")

    monkeypatch.setattr(challenge_contracts, "compile_submission", broken)
    spec = A.family_spec("permission_ablation")
    for name, item in spec.attacks():
        reading = A.assess(spec, (name, item))
        assert reading.oracle.verdict == "CRASHED", name


# -- the Test Lead's cooling vectors --------------------------------------------------------------
VECTORS = A.vectors()


def test_every_cooling_vector_from_the_test_lead_is_mapped():
    assert set(VECTORS) == {
        "false_cooling_optimism",
        "hidden_flow_imbalance",
        "under_predicted_pressure_drop",
        "group_sacrifice",
        "out_of_regime_reynolds",
    }
    seams = {s.name: s for s in A.level_families()}
    for name, vector in VECTORS.items():
        assert vector["check"] in CHECKS[c.TRACK]
        for family in vector["families"]:
            assert family in SPECS, (name, family)
        primary = SPECS[vector["families"][0]]
        assert primary.check == vector["check"]
        seam = seams[vector["seam"]]
        assert seam.state == core.NOT_RUN and seam.level == 0
        assert "reserved: owner" in seam.reason, name


@pytest.mark.parametrize("name", sorted(VECTORS))
def test_each_cooling_vector_has_an_attack_and_a_control_with_expected_verdicts(name):
    """Each vector's attack example is HELD at the real boundary and FIRES the
    vulnerable specimen; its valid control (trained and held-out) PASSES the
    real boundary."""
    vector = VECTORS[name]
    spec = SPECS[vector["families"][0]]
    trained = {x.name for x in A.controls("trained") if x.family == spec.name}
    assert vector["control"] in trained
    attack = dict(spec.attacks())[vector["attack"]]
    reading = A.assess(spec, (vector["attack"], attack)).oracle
    expected = vector["expected"]
    assert reading.verdict == expected["real_boundary"] == c.HELD
    assert reading.specimen == expected["vulnerable_specimen"] == c.FIRED
    for split in c.SPLITS:
        controls = [x for x in A.controls(split) if x.family == spec.name]
        assert controls
        for control in controls:
            outcome = engine.PASSED if control.check() else engine.REFUSED
            assert outcome == expected["control"] == engine.PASSED, control.name


def test_vectors_that_need_an_owner_value_invent_none():
    """The vector seams name what is missing; the adapter pins no tolerance,
    weight or limit of its own (only copies of registered values)."""
    for vector in VECTORS.values():
        seam = next(s for s in c.SEAMS if s.name == vector["seam"])
        assert seam.reserved_decision and seam.reserved_decision.startswith("owner")
    numbers = {
        name: value
        for name, value in vars(c).items()
        if name.isupper() and type(value) in (int, float)
    }
    assert numbers == {
        "LEVEL": 0,
        "CODE_RUN_SECONDS": 600,
        "RE_LAMINAR_MAX": 2000.0,
        "T_IMPORTANT_C": 85.0,
    }


def test_a_partial_prediction_set_is_failed_infra_never_a_pass():
    half = c._half_predictions()
    result = c.resource_boundary({"kind": "scoring", "predictions": half})
    assert result["n_failed_infra"] == result["n_cases"] - len(half) == 50
    assert result["n_gate_failed"] == 0
    nothing = c.resource_boundary(
        {"kind": "scoring", "predictions": {}, "partial": True}
    )
    assert not nothing["eligible"] and not c.resource_breached(nothing)


def test_a_code_run_is_refused_before_dispatch_above_the_wall_allowance():
    assert A.code_run_refusal({"seconds": c.CODE_RUN_SECONDS}) is None
    assert A.code_run_refusal({"seconds": c.CODE_RUN_SECONDS + 1}) == (
        "code_run_needs_seconds_up_to_600"
    )
    assert A.code_run_refusal("seconds=1") == "code_run_arguments_unreadable"


# -- rebuild ------------------------------------------------------------------------------------
def test_carbon_rebuilds_with_admit_and_refuses_with_a_typed_code():
    from carbon.challenge_validator.scoring import REBUILT_FIELDS

    rebuilt = A.rebuild(c._scaffold())
    assert type(rebuilt) is core.Rebuilt
    assert set(REBUILT_FIELDS) <= set(rebuilt.detail["record"])
    assert A.rebuild(c._scaffold()).rebuilt_digest == rebuilt.rebuilt_digest
    refusals = {
        "outside": (A.recipe_outside_contract(), "refused_by_contract"),
        "withheld": (c._strategy(loss_expressions=True), "outside_level"),
        "text": (json.dumps(c._scaffold()), "not_declarative"),
        "nonfinite": (c._strategy(ridge=float("nan")), "not_declarative"),
        "other": ({**c._scaffold(), "challenge_id": "x-y"}, "unknown_construction"),
        "seed": ({"strategy": c._scaffold(), "seed": -1}, "unknown_construction"),
        "protected": (c._strategy(weights="hidden_case"), "protected_material"),
    }
    for label, (construction, code) in refusals.items():
        out = A.rebuild(construction)
        assert type(out) is core.Unrebuildable, label
        assert out.code == code and out.code in core.UNREBUILDABLE_CODES, label


def test_a_stale_contract_record_is_carbons_side_never_the_constructions(monkeypatch):
    from carbon.agent_campaign.graphite import experiment

    def unrecorded(scoring=None):
        raise experiment.Unrebuildable("construction_contract_unrecorded")

    monkeypatch.setattr(experiment, "recorded_contract", unrecorded)
    out = A.rebuild(c._scaffold())
    assert out.code == "rebuild_failed_infra"
    assert A.carbon_code(out) == "construction_contract_unrecorded"


def test_higher_level_families_are_not_run_seams_with_nothing_to_execute():
    seams = A.level_families()
    assert {s.level for s in seams} == {0, 1, 2, 3, 4, 5}
    for seam in seams:
        assert seam.state == core.NOT_RUN
        result = A.oracle(seam.name, core.AttackInput("x", {"anything": 1}))
        assert result.verdict == core.NOT_RUN and result.specimen is None
    for seam in c.SEAMS:
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
def test_each_pinned_value_is_a_copy_of_its_cooling_source():
    from carbon.challenge_validator import scoring
    from carbon.cold_plate import domain, exam, population, practice, research

    assert c.CODE_RUN_SECONDS == research.PRACTICE_SECONDS
    assert c.RE_LAMINAR_MAX == domain.RE_LAMINAR_MAX == population.SCREEN["re_max"]
    assert c.T_IMPORTANT_C == exam.T_IMPORTANT_C
    assert c.TAMPER_FIELDS == scoring.REBUILT_FIELDS
    assert c.STAGED_NAMES == set(practice.STAGED_MODULES) | {
        "train-v1.jsonl",
        "practice-inputs.json",
        "recipe.json",
    }
    probe = c._probe(c._oracle_predictions())
    assert set(probe) == c.PRACTICE_FEEDBACK_FIELDS
    assert set(probe["summary"]) == c.PRACTICE_SUMMARY_FIELDS
    assert {k: probe[k] for k in c.PRACTICE_FLAGS} == c.PRACTICE_FLAGS
    assert (
        A.recipe_outside_contract()
        == scoring.scoring_for(c.CHALLENGE_ID).fixture_refused_strategy()
    )
    assert A.permission_inventory()["not_permitted"] == list(c._capability_index()[3])


# -- sealed identities and material ---------------------------------------------------------------
def _emitted():
    """Every string-bearing value the adapter emits: family names, boundary
    texts, attack names and inputs, control names and inputs, seams and the
    vector map."""
    out = []
    for spec in A.family_specs():
        out += [spec.name, spec.protocol_family, spec.reads, spec.attack_example]
        out += [[n, v] for n, v in spec.attacks()]
    for split in c.SPLITS:
        out += [[x.name, x.value()] for x in A.control_specs(split)]
    out += [[s.name, s.reason] for s in A.level_families()]
    out += [A.vectors(), A.surface()]
    return out


def _sealed_phrases():
    entry = next(
        e
        for e in knowledge.SEALED_IDENTITIES
        if e["id"] == "cooling-final-condition-ids"
    )
    return entry, [knowledge.normalise(p)[0] for p in entry["value"]]


def test_no_sealed_identity_is_named_by_the_adapter():
    """Nothing the adapter emits, and nothing in its source, names a
    registered sealed identity (`knowledge.SEALED_IDENTITIES`), in the
    registered scoped form or bare: cooling's final condition ids never
    appear, with or without the study that scopes them."""
    entry, phrases = _sealed_phrases()
    texts = list(knowledge._strings(_emitted()))
    texts.append(Path(c.__file__).read_text(encoding="utf-8"))
    for text in texts:
        assert knowledge.sealed_identity(text) is None, text[:120]
        spaced = " " + knowledge.normalise(text)[0] + " "
        assert not [p for p in phrases if " " + p + " " in spaced], text[:120]
    # The emitted values themselves pass the store's whole sealed rule.
    assert not knowledge.sealed(_emitted())
    # The check is live: the registered scoped form is recognised.
    scope = entry.get("scope", ("chip-cold-plate",))[0]
    assert knowledge.sealed_identity(scope + "/" + entry["value"][0]) == entry["id"]


def test_nothing_the_adapter_names_is_protected_material():
    named = []
    for spec in A.family_specs():
        named += [spec.name, spec.protocol_family, spec.reads]
        named += [n for n, _ in spec.attacks()]
    named += [x.name for x in A.controls("trained") + A.controls("held_out")]
    named += [s.name + " " + s.reason for s in A.level_families()]
    leaked = [text for text in named if c._protected(text)]
    assert not leaked, leaked


#: Repository paths the adapter must never open: the decision study and its
#: fixtures (which hold the study's own cases), counted CFD, customer material
#: and anything confirmation, private or sealed.
DENIED_READS = re.compile(
    r"decision[-_]fixture|decision_study|customer_decision|ai-cooling-counted"
    r"|AI_ACCELERATOR_COOLING|confirmation|private|seal|freeze",
    re.IGNORECASE,
)
_OPENED = []
_RECORDING = []


def _audit(event, args):
    if _RECORDING and event == "open" and args and isinstance(args[0], str | bytes):
        _OPENED.append(args[0] if isinstance(args[0], str) else args[0].decode())


def test_the_adapter_reads_public_material_only(tmp_path):
    """Every file the adapter opens while it runs every attack, specimen and
    control, its rebuild, its held-out measurement and its session surface is
    recorded (an audit hook); none is study, counted, confirmation or private
    material, and the public TRAIN and PRACTICE records are among them."""
    if not getattr(sys, "_cooling_attack_audit", False):
        sys.addaudithook(_audit)
        sys._cooling_attack_audit = True
    c.clear_caches()
    _OPENED.clear()
    _RECORDING.append(True)
    try:
        for spec in A.family_specs():
            for name, value in spec.attacks():
                A.assess(spec, (name, value))
        for split in c.SPLITS:
            for control in A.controls(split):
                control.check()
        core.held_out_outcomes(A)
        A.rebuild(c._scaffold())
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
    assert any(p.endswith("cold-plate-pools-v1/train.jsonl") for p in inside)
    assert any(p.endswith("cold-plate-pools-v1/practice.jsonl") for p in inside)


# -- the phase-4 dry run at cooling ----------------------------------------------------------------
def test_the_cooling_dry_run_produces_coverage_and_b2_with_no_spend(tmp_path):
    from carbon.agent_campaign.graphite import phase4

    out = io.StringIO()
    with redirect_stdout(out):
        code = phase4.main(
            [
                "run",
                "--root",
                str(tmp_path / "root"),
                "--challenge",
                c.CHALLENGE_ID,
                "--dry-run",
            ]
        )
    assert code == 0
    body = out.getvalue()
    printed = json.loads(body[body.index('{\n "coverage"') :])
    coverage = printed["coverage"]
    assert coverage["challenge"] == c.CHALLENGE_ID
    assert coverage["construction_level"] == 0
    assert coverage["contract_digest"] == A.contract_digest
    assert coverage["findings"] == []
    assert coverage["checks"]["undeclared"] == []
    assert set(coverage["checks"]["checks"]) == CHECKS[c.TRACK]
    assert coverage["claims"] == {"security_acceptance": False, "graded": False}
    assert printed["dry_run"]["synthetic"] is True
    assert printed["session"]["code_runs"] == 0
    rates = coverage["wrongful_rejection_held_out"]
    assert {name: row["rate"] for name, row in rates.items()} == dict.fromkeys(
        SPECS, 0.0
    )


# -- mutations: each disabled boundary turns its guard red -----------------------------------------
_UNKNOWN = {"weights", "channel_flow_split"}


def _gate_admits_withheld_permissions(m):
    from types import SimpleNamespace

    from carbon.reconstruction import challenge_contracts

    original = challenge_contracts.compile_submission

    def lax(strategy, **kwargs):
        try:
            return original(strategy, **kwargs)
        except challenge_contracts.SubmissionRefused:
            recipe = SimpleNamespace(recipe_digest="sha256:" + "0" * 64)
            return SimpleNamespace(construction=recipe)

    m.setattr(challenge_contracts, "compile_submission", lax)


def _gate_accepts_unknown_field(m):
    from carbon.reconstruction import challenge_contracts

    original = challenge_contracts.compile_submission

    def lax(strategy, **kwargs):
        if isinstance(strategy, dict) and isinstance(strategy.get("parameters"), dict):
            kept = {
                k: v for k, v in strategy["parameters"].items() if k not in _UNKNOWN
            }
            strategy = {**strategy, "parameters": kept}
        return original(strategy, **kwargs)

    m.setattr(challenge_contracts, "compile_submission", lax)


def _recipe_token_unchecked(m):
    from carbon.cold_plate import compile as cold_compile

    m.setattr(cold_compile.ColdPlateRecipe, "__post_init__", lambda self: None)


def _aggregate(change):
    from carbon.cold_plate import exam

    original = exam.aggregate

    def mutated(rows):
        out = original(rows)
        return {**out, **change(out)}

    return mutated


def _averaging_scorer(m):
    from carbon.cold_plate import exam

    m.setattr(exam, "aggregate", _aggregate(lambda o: {"eligible": o["n_scored"] > 0}))


def _failed_infra_counts_as_pass(m):
    from carbon.cold_plate import exam

    m.setattr(
        exam, "aggregate", _aggregate(lambda o: {"eligible": o["n_gate_failed"] == 0})
    )


def _optimism_bias_dropped(m):
    from carbon.cold_plate import exam

    m.setattr(exam, "aggregate", _aggregate(lambda o: {"important_peak_bias_k": None}))


def _hot_group_pooled(m):
    from carbon.cold_plate import exam

    m.setattr(exam, "aggregate", _aggregate(lambda o: {"important_score": o["score"]}))


def _components(change):
    from carbon.cold_plate import exam

    original = exam.case_components

    def mutated(prediction, reference, scales):
        return change(original(prediction, reference, scales), prediction, reference)

    return mutated


def _profile_scored_by_mean(m):
    from statistics import fmean

    from carbon.cold_plate import exam

    def by_mean(out, prediction, reference):
        got = fmean(float(v) for v in prediction["profile_c"])
        want = fmean(reference["outputs"]["profile_c"])
        same = abs(got - want) <= 1e-9 * max(1.0, abs(want))
        return {**out, "profile": 0.0 if same else out["profile"]}

    m.setattr(exam, "case_components", _components(by_mean))


def _pressure_left_out(m):
    from carbon.cold_plate import exam

    m.setattr(
        exam,
        "case_components",
        _components(lambda out, _p, _r: {**out, "pressure": 0.0}),
    )


def _screen_disabled(m):
    from carbon.cold_plate import population

    m.setattr(population, "SCREEN", {"max_wall_c": 1e9, "re_max": 1e9})


def _code_run_seconds_lifted(m):
    m.setattr(c, "CODE_RUN_SECONDS", 10**6)


def _cooling_wall_allowance_lifted(m):
    from carbon.cold_plate import research

    m.setattr(research, "PRACTICE_SECONDS", 3600)


def _feedback_field_added(m):
    from carbon.cold_plate import practice

    original = practice.feedback

    def wider(*args, **kwargs):
        return {**original(*args, **kwargs), "screening": {"pool_version": 3}}

    m.setattr(practice, "feedback", wider)


def _leaky_stager(m):
    from carbon.cold_plate import practice

    original = practice.staged_files

    def leaky(root, practice_set, recipe):
        files = original(root, practice_set, recipe)
        return {**files, "practice.jsonl": practice_set.public_bytes()}

    m.setattr(practice, "staged_files", leaky)


def _recipe_digest_drops_settings(m):
    from carbon.cold_plate import compile as cold_compile

    m.setattr(
        cold_compile.ColdPlateRecipe,
        "recipe_digest",
        property(lambda self: c._digest({"family": self.family})),
    )


def _rebuilt_field_dropped(m):
    from carbon.challenge_validator import scoring

    m.setattr(
        scoring,
        "REBUILT_FIELDS",
        tuple(f for f in scoring.REBUILT_FIELDS if f != "program"),
    )


def _material_digest_unchecked(m):
    from carbon.cold_plate import challenge

    def trusting(path, expected, name):
        return Path(path).read_bytes().replace(b"\r\n", b"\n")

    m.setattr(challenge, "canonical_text", trusting)


def _protected_marker_removed(m):
    # The check reads the leaf module's markers; `tools` only re-exports them,
    # so patching `tools` would disable nothing.
    from carbon.agent_campaign.graphite import protected_material

    m.setattr(
        protected_material,
        "PROTECTED_MARKERS",
        tuple(x for x in protected_material.PROTECTED_MARKERS if "hidden" not in x),
    )


def _non_conditions_finding(m):
    m.setitem(c.CONDITION_OF, c.BREACH, "EXPLOIT_CONFIRMED")


def _engine_reads_held_out(m):
    def leaky(self, name):
        spec = self.family_spec(name)
        return lambda: all(
            spec.control_check(x.value())
            for split in c.SPLITS
            for x in self.control_specs(split)
            if x.family == name
        )

    m.setattr(c.CoolingLevel0Adapter, "trained_control", leaky)


def _gate_swallows_crashes(m):
    original = c.gate

    def lax(strategy):
        try:
            return original(strategy)
        except Exception as crashed:  # noqa: BLE001 - the mutation under test
            return {"status": "REFUSED", "codes": [(type(crashed).__name__, "")]}

    m.setattr(c, "gate", lax)


def _guard_gate_crash():
    with pytest.MonkeyPatch.context() as m:
        test_a_crash_in_carbons_own_gate_is_never_a_hold(m)


def _guard_trained_split_only():
    with pytest.MonkeyPatch.context() as m:
        test_the_engine_control_reads_the_trained_split_only(m)


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
    "optimism_bias_dropped": (
        _optimism_bias_dropped,
        lambda: _held_and_fired("cooling_optimism"),
    ),
    "profile_scored_by_mean": (
        _profile_scored_by_mean,
        lambda: _held_and_fired("flow_imbalance_masking"),
    ),
    "pressure_left_out_of_the_score": (
        _pressure_left_out,
        lambda: _held_and_fired("pressure_underprediction"),
    ),
    "hot_group_pooled": (
        _hot_group_pooled,
        lambda: _held_and_fired("group_sacrifice"),
    ),
    "population_screen_disabled": (
        _screen_disabled,
        lambda: _held_and_fired("regime_screen"),
    ),
    "code_run_seconds_lifted": (
        _code_run_seconds_lifted,
        lambda: _held_and_fired("resource_accounting"),
    ),
    "failed_infra_counted_as_a_pass": (
        _failed_infra_counts_as_pass,
        lambda: _held_and_fired("resource_accounting"),
    ),
    "cooling_wall_allowance_lifted": (
        _cooling_wall_allowance_lifted,
        test_each_pinned_value_is_a_copy_of_its_cooling_source,
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
    c.clear_caches()
    try:
        mutate(monkeypatch)
        with pytest.raises((AssertionError, ValueError)):
            guard()
    finally:
        monkeypatch.undo()
        c.clear_caches()


def test_every_guard_passes_without_its_mutation():
    """The other half of the mutation check: unmutated, each guard holds."""
    for _mutate, guard in MUTATIONS.values():
        guard()
