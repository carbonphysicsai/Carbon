"""Battery's Level 0 attack adapter (OWNER-GRAPHITE-ATTACKER-01, slice AT-B).

The claims tested:
- the adapter is registered by `(challenge, level)`, names the live contract
  read only, and carries the session surface a Graphite session needs;
- every Track A check is covered by a family or a declared NOT_RUN seam, and
  every family has an attack example and a trained and a held-out control;
- every attack is held by the real boundary, every specimen fires, and every
  control passes;
- the oracle emits only the CONDITIONS vocabulary: a breach or a wrongful
  refusal is FAILING_TRIGGER, protected material that got through is
  OTHER_SIGNAL, protected material refused or never sent is no finding; a
  hold the detector cannot vouch for is never HELD; a crash in Carbon's own
  gate is never a hold; the Attacker code-run rule judges only the Attacker
  lane;
- Carbon rebuilds with `experiment.admit` and refuses with a typed code;
- higher-level families are NOT_RUN seams with nothing to execute;
- each pinned value is a copy of its battery source;
- mutations: disabling each boundary turns its guard red (the pattern of
  `test_graphite_phase3_mutations.py`).
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from carbon.agent_campaign.attack import adapters
from carbon.agent_campaign.attack.adapters import battery as b
from carbon.battery import track_a
from carbon.challenge_readiness.admission import CHECKS, CONDITIONS

A = b.ADAPTER
SPECS = {s.name: s for s in A.family_specs()}
#: The core's typed refusal codes (`attack.adapter.UNREBUILDABLE_CODES`).
CORE_REFUSALS = getattr(
    b._core,
    "UNREBUILDABLE_CODES",
    {
        "not_declarative",
        "refused_by_contract",
        "outside_level",
        "protected_material",
        "unknown_construction",
        "rebuild_failed_infra",
    },
)


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
        if (r.reading, r.oracle.verdict) != (b.HELD, b.HELD)
    }
    assert not not_held, not_held
    assert all(r.condition is None for r in readings.values())
    silent = [n for n, value in attacks if not spec.breached(spec.specimen(value))]
    assert not silent, silent


def _controls_pass(name, split="trained"):
    controls = [c for c in A.controls(split) if c.family == name]
    assert controls
    for control in controls:
        assert control.check(), control.name
        assert A.control_passes(control), control.name


# -- identity, registry and session surface ------------------------------------------------------
def test_the_registry_loads_battery_level_0_and_refuses_anything_else():
    assert adapters.load(b.CHALLENGE_ID, 0) is A
    assert (b.CHALLENGE_ID, 0) in adapters.registered()
    # Levels 1-3 have their own adapters (GRAPHITE-L1-BUILD-01,
    # battery_level2, battery_level3); Level 5 has none.
    for level in (1, 2, 3):
        assert adapters.load(b.CHALLENGE_ID, level) is not A
    with pytest.raises(adapters.AdapterNotRegistered):
        adapters.load(b.CHALLENGE_ID, 5)
    with pytest.raises(adapters.AdapterNotRegistered):
        adapters.load("burgers-dynamics-v1", 0)


def test_the_core_registry_holds_the_adapter_when_the_core_is_present():
    core = pytest.importorskip("carbon.agent_campaign.attack.adapter")
    assert core.get(b.CHALLENGE_ID, 0) is A
    assert core.validate(A) is A
    assert isinstance(A, core.Adapter) and isinstance(A, core.SessionSurface)
    coverage = core.coverage(A)
    assert coverage["fresh_attack_confirmation"]["not_run"] == ["fresh_cases_rerun"]


def test_the_adapter_names_the_live_contract_read_only():
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        contract_digest,
    )

    assert (A.challenge_id, A.level) == (BATTERY_CHALLENGE, 0)
    assert A.contract_digest == contract_digest(BATTERY_CHALLENGE)
    surface = A.surface()
    assert surface["profile"] == "level-0"
    assert surface["contract_digest"] == A.contract_digest
    assert surface["submission_form"].startswith("declarative strategy only")
    assert surface["adapter_version"] == b.ADAPTER_VERSION


def test_the_session_surface_is_carbons_own_admission():
    from carbon.battery.challenge import CHALLENGE

    assert A.permission_inventory()["profile"] == "level-0"
    assert A.permission_inventory()["challenge"] == b.CHALLENGE_ID
    assert A.public_identity() == {"id": CHALLENGE.challenge_id, "version": "1.0"}
    assert A.code_run_seconds() == b.CODE_RUN_SECONDS
    assert A.admission_refusals(track_a.RECIPE_CONTROL) == []
    # Carbon rebuilds it; only the phase-3 pods do not serve it.
    assert A.admission_refusals(track_a._strategy(backend="pytorch", steps=100)) == []
    outside = A.admission_refusals(A.recipe_outside_contract())
    assert outside[0] == "contract_refused" and "backbone.not_rebuildable" in outside
    assert A.admission_refusals(track_a._strategy(label_method="x")) == [
        "contract_refused",
        "parameter.not_rebuildable",
    ]


def test_every_track_a_check_is_covered_by_a_family_or_a_not_run_seam():
    checks = A.checks()
    assert set(checks) == CHECKS[b.TRACK]
    assert all(checks.values())
    assert checks["fresh_attack_confirmation"] == ("fresh_cases_rerun:NOT_RUN",)
    assert {f.check for f in A.families()} == CHECKS[b.TRACK] - {
        "fresh_attack_confirmation"
    }


def test_each_family_def_carries_its_engine_family_and_examples():
    for definition in A.families():
        spec = SPECS[definition.name]
        family = definition.family
        assert (family.name, family.check) == (definition.name, definition.check)
        assert family.boundary is spec.boundary and family.specimen is spec.specimen
        assert family.breached is spec.breached and family.attacks is spec.attacks
        assert definition.attack_example in {n for n, _ in spec.attacks()}
        trained = {c.name for c in A.controls("trained")}
        assert definition.control_example in trained
        assert definition.boundary == spec.protocol_family == family.description
    assert [f.name for f in A.engine_families()] == [f.name for f in A.families()]


@pytest.mark.parametrize("name", sorted(SPECS))
def test_each_family_has_both_control_splits(name):
    for split in b.SPLITS:
        assert [c for c in A.controls(split) if c.family == name], split


def test_controls_are_split_disjoint_and_versioned():
    trained, held = A.controls("trained"), A.controls("held_out")
    assert {c.name for c in trained}.isdisjoint({c.name for c in held})
    assert {c.version for c in trained + held} == {b.CONTROLS_VERSION}
    assert {c.split for c in trained} == {"trained"}
    assert {c.split for c in held} == {"held_out"}
    assert A.controls_digest("trained") == A.controls_digest("trained")
    assert A.controls_digest("trained") != A.controls_digest("held_out")
    with pytest.raises(ValueError):
        A.controls("tuning")


def test_held_out_and_trained_controls_are_canonically_distinct():
    """No held-out control is a key-reordered or round-tripped copy of a
    trained one: canonically (sorted keys, JSON) every held-out value
    differs from every trained value of its family, and every registered
    identity differs. Each held-out control still passes the real boundary."""
    for name in SPECS:
        trained = [c for c in A.control_specs("trained") if c.family == name]
        held = [c for c in A.control_specs("held_out") if c.family == name]
        seen = {b._canonical(c.value()) for c in trained}
        for control in held:
            assert b._canonical(control.value()) not in seen, control.name
    identities = {c.identity for c in A.controls("trained")}
    assert identities.isdisjoint({c.identity for c in A.controls("held_out")})
    for name in ("practice_disclosure", "mandatory_failure"):
        for control in [c for c in A.control_specs("held_out") if c.family == name]:
            assert A.control_passes(control), control.name


def test_nothing_the_adapter_names_is_protected_material():
    named = []
    for spec in A.family_specs():
        named += [spec.name, spec.protocol_family, spec.reads]
        named += [n for n, _ in spec.attacks()]
    named += [c.name for c in A.controls("trained") + A.controls("held_out")]
    named += [s.name + " " + s.reason for s in A.level_families()]
    leaked = [text for text in named if b._protected(text)]
    assert not leaked, leaked
    # The Track A check id `fresh_attack_confirmation` itself names protected
    # material for Graphite ("confirmation"): it is Carbon's vocabulary, never
    # shown to an agent, so the seam that covers it has its own name.
    assert b._protected("fresh_attack_confirmation")


# -- attacks, specimens, controls ---------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(SPECS))
def test_every_attack_is_held_and_every_specimen_fires(name):
    _held_and_fired(name)


@pytest.mark.parametrize("split", b.SPLITS)
def test_every_control_passes(split):
    for name in SPECS:
        _controls_pass(name, split)


def test_every_withheld_permission_is_an_expected_refusal():
    inventory = A.permission_inventory()
    items = {n: v for n, v in b._ablation_attacks() if not v.get("climb")}
    assert {n.removeprefix("withheld_") for n in items} == set(
        inventory["not_permitted"]
    )
    assert all(item["expected_refusal"] for item in items.values())
    assert {p["id"] for p in inventory["permitted"]} == set(b.level0_permissions())


def test_the_climb_ablates_to_level_0_and_every_removed_permission_is_refused():
    report = b.climb_report()
    assert report["status"] == "COMPLETED" and report["findings"] == []
    assert report["new_permissions"] == [b.DRAFT_PERMISSION]
    for step in ("matched_attacks", "ablation", "interactions"):
        runs = [r for r in report["steps"][step]["runs"] if r["kind"] == "attack"]
        assert runs, step
        for run in runs:
            # The live gate is Level 0's whatever the run's profile label.
            assert run["status"] == "REFUSED", (step, run["item_id"])
            if run["profile"] != "level-1-draft":
                assert run["expected_refusal"], (step, run["item_id"])
    assert any(
        r["profile"].startswith("ablated:") for r in report["steps"]["ablation"]["runs"]
    )
    (rebuild,) = report["steps"]["reconstruction"]["runs"]
    assert rebuild["outcome"]["matches"]
    assert b.uses(b._panel("mlp")) <= b.level0_permissions()
    # The specimen: runners that do not enforce the profile are caught.
    weak = b.climb_report(b._unenforced_runners())
    assert weak["status"] == "STOPPED_ON_FINDING"


def test_a_crash_in_carbons_own_gate_is_never_a_hold(monkeypatch):
    """Only the gate's typed refusals read as REFUSED. A gate that raises
    anything else crashed: the withheld attack and the climb run both read
    CRASHED (core INCONCLUSIVE family state), never HELD."""
    from carbon.reconstruction import challenge_contracts

    def broken(strategy, **kwargs):
        raise KeyError("gate defect")

    monkeypatch.setattr(challenge_contracts, "compile_submission", broken)
    attacks = dict(b._ablation_attacks())
    name = "withheld_" + b.DRAFT_PERMISSION
    for attack in (name, "climb_ablation_of_the_level_1_draft"):
        reading = A.assess("permission_ablation", (attack, attacks[attack]))
        assert reading.reading == "CRASHED", attack
        assert reading.oracle.verdict == "CRASHED" and reading.condition is None
    with pytest.raises(KeyError):
        b.gate(track_a.RECIPE_CONTROL)
    # Malformed input is still a typed refusal, not a crash.
    monkeypatch.undo()
    for malformed in ("not a strategy", None, [], {}):
        assert b.gate(malformed)["status"] == "REFUSED", malformed


def test_each_reused_family_carries_track_as_protocol_text_not_its_name():
    for name in ("recipe_surface", "recipe_forgery", "mandatory_failure"):
        assert SPECS[name].protocol_family != name
    assert SPECS["staged_bytes"].protocol_family != "staged_bytes"
    assert SPECS["rebuild_identity"].protocol_family != "rebuild_identity"


def test_protocol_text_reads_an_engine_family_description(monkeypatch):
    from types import SimpleNamespace

    engine_shaped = SimpleNamespace(name="recipe_surface", description="the text")
    monkeypatch.setattr(track_a, "FAMILIES", (engine_shaped,))
    assert b._protocol("recipe_surface") == "the text"
    bare = SimpleNamespace(name="recipe_surface", description="recipe_surface")
    monkeypatch.setattr(track_a, "FAMILIES", (bare,))
    with pytest.raises(LookupError):
        b._protocol("recipe_surface")
    monkeypatch.setattr(track_a, "FAMILIES", (SimpleNamespace(name="recipe_surface"),))
    with pytest.raises(LookupError):
        b._protocol("recipe_surface")


def test_cached_reads_follow_the_live_contract_record(monkeypatch):
    from carbon.agent_campaign.graphite import experiment

    strategy = b._canonical(track_a.RECIPE_CONTROL)
    first = b._expected_build(strategy, 7)
    real = experiment.recorded_contract

    def newer(scoring=None):
        return {
            **real(scoring),
            "record_sequence": real(scoring)["record_sequence"] + 1,
        }

    before = b._expected_build_cached.cache_info().misses
    monkeypatch.setattr(experiment, "recorded_contract", newer)
    rebuilt = b._expected_build(strategy, 7)
    assert b._expected_build_cached.cache_info().misses == before + 1
    # Carbon's admit record under the newer contract record, never the stale one.
    assert rebuilt["record_sequence"] == first["record_sequence"] + 1
    assert {k: v for k, v in rebuilt.items() if k != "record_sequence"} == {
        k: v for k, v in first.items() if k != "record_sequence"
    }
    # The contract index is keyed by the live contract's digest.
    assert set(b._INDEX_BY_CONTRACT) == {A.contract_digest}
    b.clear_caches()
    assert b._INDEX_BY_CONTRACT == {} and A.contract_digest
    assert set(b._INDEX_BY_CONTRACT) == {A.contract_digest}


def test_a_code_run_is_refused_before_dispatch_above_the_wall_allowance():
    most = A.code_run_seconds()
    assert A.code_run_refusal({"seconds": most}) is None
    assert A.code_run_refusal({"seconds": 1}) is None
    for arguments in (
        {"seconds": most + 1},
        {"seconds": 0},
        {"seconds": True},
        {"seconds": float(most)},
        {},
        "seconds=1",
    ):
        assert A.code_run_refusal(arguments), arguments


def test_a_partial_prediction_set_is_a_gate_failure_never_a_pass():
    """GRAPHITE-COVERAGE-PARITY-01: every case a set leaves out is a schema-
    gate failure, never FAILED_INFRA and never excluded, so a partial set is
    never eligible (before it, an omitted case was FAILED_INFRA and excluded)."""
    value = {"kind": "scoring", "predictions": {}, "partial": True}
    result = b.resource_boundary(value)
    assert not result["eligible"]
    assert result["n_failed_infra"] == 0
    assert result["n_gate_failed"] == result["n_cases"] == 200
    half = b.resource_boundary(
        {"kind": "scoring", "predictions": b._half_predictions(), "partial": True}
    )
    assert not half["eligible"] and half["n_failed_infra"] == 0
    assert half["n_gate_failed"] == half["n_cases"] - half["n_scored"] == 100
    assert not b.resource_breached(half)
    assert b.resource_breached(b.resource_specimen(value))


def test_a_pod_timeout_is_a_seam_never_judged_by_the_scoring_stand_in():
    """The pod path types a timeout CANDIDATE_FAILED; the frozen rule types a
    missing prediction FAILED_INFRA. The adapter claims neither for a pod
    timeout: it is an owner question, declared NOT_RUN."""
    (seam,) = [s for s in A.level_families() if s.name == "pod_timeout_typing"]
    assert (seam.level, seam.state) == (0, b.NOT_RUN)
    assert seam.check == "resource_and_failure_accounting"
    assert "reserved: owner" in seam.reason and "CANDIDATE_FAILED" in seam.reason
    names = {n for n, _ in A.family_spec("resource_accounting").attacks()}
    assert not any("timed_out" in n or "timeout" in n for n in names)
    assert "pod_timeout_typing:NOT_RUN" in A.checks()["resource_and_failure_accounting"]


# -- selective fault and omission (GRAPHITE-COVERAGE-PARITY-01) ---------------------------------
_RESULTS = {}


def _result(family, name):
    """One attack's real-boundary result, computed once per test session."""
    key = (family, name)
    if key not in _RESULTS:
        value = dict(A.family_spec(family).attacks())[name]
        _RESULTS[key] = (value, b.fault_boundary(value))
    return _RESULTS[key]


@pytest.mark.parametrize("name", [n for n, _ in b._selective_attacks()])
def test_a_selective_fault_dodges_no_case_on_either_path(name):
    """A raise on the hit cases fails the whole attempt and charges it: the
    Interface v1 validator (battery's daemon behind `Validator.evaluate`)
    marks it RECONSTRUCTION_FAILED (`DirectBackend.infer` types the predict
    fault as the candidate's) and a resubmission reads the same; Graphite's
    pod path types the program crash CANDIDATE_FAILED, never retried. A
    non-finite output is a gate failure on both: the set is ineligible and
    no case is excluded."""
    value, result = _result("selective_fault", name)
    assert not b.fault_breached(result)
    v1, graphite = result["interface_v1"], result["graphite"]
    assert v1["hit"] and graphite["hit"]
    assert v1["retry_same"] and graphite["pods_launched"] == 2
    assert not graphite["retried"]
    if value["mode"] == "raise":
        assert v1["outcome"] == (
            "OUTCOME:RECONSTRUCTION_FAILED:prediction_failed:ConstructionFault"
        )
        assert graphite["outcome"] == "CANDIDATE_FAILED:program"
    else:
        assert v1["outcome"] == "SCORED" and v1["eligible"] is False
        assert v1["n_scored"] + len(v1["hit"]) == v1["n_cases"]
        assert v1["n_failed_infra"] == 0
        assert graphite["outcome"] == "SCORED" and graphite["eligible"] is False
        assert graphite["n_gate_failed"] == len(graphite["hit"])
        # An ineligible record never headlines a score (item 2).
        assert graphite["score"] is None
        assert graphite["against_baseline"] == "REGRESSION"


@pytest.mark.parametrize("name", [n for n, _ in b._omission_attacks()])
def test_an_omission_is_charged_on_both_paths(name):
    """A case left out, or given null, is the candidate's on both paths:
    battery's validator refuses the incomplete set (`daemon.incomplete`,
    RECONSTRUCTION_FAILED) and Graphite's frozen rule types each missing case
    a schema-gate failure (`scoring.cover`), so the set is ineligible."""
    _value, result = _result("prediction_omission", name)
    assert not b.fault_breached(result)
    v1, graphite = result["interface_v1"], result["graphite"]
    assert v1["outcome"] == "OUTCOME:RECONSTRUCTION_FAILED:prediction_cases_differ"
    assert v1["retry_same"]
    assert graphite["outcome"] == "SCORED" and graphite["eligible"] is False
    assert graphite["n_gate_failed"] == len(graphite["hit"]) > 0
    assert graphite["n_scored"] + len(graphite["hit"]) == graphite["n_cases"]
    assert graphite["score"] is None


def test_the_specimen_drops_the_hit_cases():
    for family in ("selective_fault", "prediction_omission"):
        for name, value in A.family_spec(family).attacks():
            weak = b.dropping_accounting(value)
            assert b.fault_breached(weak), (family, name)
            for path in b.FAULT_PATHS:
                assert weak[path]["n_scored"] == 200 - len(weak[path]["hit"])


def test_the_probe_runs_carbons_own_program_and_validator(monkeypatch):
    """The pod's program is Carbon's practice program (the GPU program is it
    plus a runtime record) from its fitted model onward; the validator path
    is `BatteryAdapter.evaluate` through `DirectBackend.infer`, twice."""
    from carbon.battery import practice
    from carbon.battery.worker import DirectBackend
    from carbon.challenge_validator.battery import BatteryAdapter
    from carbon.development_session.battery_gpu import GPU_PROGRAM

    assert GPU_PROGRAM.startswith(practice.PROGRAM)
    assert "predictions" in b._program_tail(practice.PROGRAM).co_names
    calls = {"evaluate": 0, "infer": 0}
    evaluate, infer = BatteryAdapter.evaluate, DirectBackend.infer

    def counted_evaluate(self, submission):
        calls["evaluate"] += 1
        return evaluate(self, submission)

    def counted_infer(self, *args):
        calls["infer"] += 1
        return infer(self, *args)

    monkeypatch.setattr(BatteryAdapter, "evaluate", counted_evaluate)
    monkeypatch.setattr(DirectBackend, "infer", counted_infer)
    b.fault_boundary({"mode": "none", "select": "none"})
    assert calls["evaluate"] == 2 and calls["infer"] >= 1


def test_repeated_practice_probes_disclose_the_allow_list_and_nothing_sealed():
    from carbon.battery import exam

    oracle = track_a.mandatory_control()
    view = b.disclosure_boundary(
        {"kind": "probe", "probes": [oracle] * 2, "identical": True}
    )
    assert set(view["fields"]) == b.PRACTICE_FEEDBACK_FIELDS
    assert len(set(view["digests"])) == 1
    sealed = b.disclosure_boundary({"kind": "disclosure", "rule": "v2"})
    assert sealed["shown"] == exam.disclosure(exam.RULES["v2"]) == b.SEALED_DISCLOSURE
    assert sealed["sealed"]


# -- pinned copies --------------------------------------------------------------------------------
def test_each_pinned_value_is_a_copy_of_its_battery_source():
    from carbon.agent_campaign.graphite import experiment
    from carbon.battery import exam, level1_draft, practice, research

    assert b.CODE_RUN_SECONDS == research.PRACTICE_SECONDS
    assert b.TAMPER_FIELDS == experiment.REBUILT_FIELDS
    assert b.SEALED_DISCLOSURE == exam.MINER_DISCLOSURE[2]
    assert b.DRAFT_PERMISSION == level1_draft.PERMISSION
    assert set(exam.aggregate([])) == b.PRACTICE_SUMMARY_FIELDS
    feedback = practice.feedback(
        exam.aggregate([]),
        {},
        recipe=b._control_recipe(),
        backend=b.PROBE_BACKEND,
        worker={},
    )
    assert set(feedback) == b.PRACTICE_FEEDBACK_FIELDS
    assert {k: feedback[k] for k in b.PRACTICE_FLAGS} == b.PRACTICE_FLAGS
    assert set(b.REFUSAL_CODES.values()) <= set(CORE_REFUSALS)


# -- the oracle -----------------------------------------------------------------------------------
def test_the_oracle_speaks_only_the_conditions_vocabulary():
    assert set(b.CONDITION_OF.values()) <= CONDITIONS
    assert b.CONDITION_OF == {
        b.BREACH: "FAILING_TRIGGER",
        b.WRONGFUL_REFUSAL: "FAILING_TRIGGER",
        b.EXPOSURE: "OTHER_SIGNAL",
    }
    with pytest.raises(ValueError):
        b.OracleResult("f", "a", b.BREACHED, "sha256:" + "0" * 64, "EXPLOIT")


def _observed(strategy, accepted, name="session-attempt", refusal_kind="construction"):
    # A refused attempt defaults to a construction-level refusal (the compiler
    # or contract refused the construction itself), the only refusal that can
    # be a wrongful rejection; a request-level refusal is passed explicitly.
    return {
        "name": name,
        "arguments": {"strategy_json": json.dumps(strategy)},
        "path_accepted": accepted,
        "refusal_kind": None if accepted else refusal_kind,
    }


def test_an_observed_path_that_accepts_what_carbon_refuses_is_a_breach():
    hostile = dict(track_a.RECIPE_ATTACKS)["pretrained_weights_field"]
    breach = A.assess("recipe_surface", _observed(hostile, True))
    assert (breach.reading, breach.observed) == (b.BREACH, True)
    assert (breach.oracle.verdict, breach.oracle.condition) == (
        b.BREACHED,
        "FAILING_TRIGGER",
    )
    assert A.oracle("recipe_surface", _observed(hostile, True)) == breach.oracle
    held = A.assess("recipe_surface", _observed(hostile, False))
    assert (held.reading, held.oracle.verdict) == (b.HELD, b.HELD)
    unknown = A.assess("recipe_surface", _observed(hostile, None))
    assert (unknown.reading, unknown.oracle.verdict) == (b.UNDETERMINED, b.INCONCLUSIVE)
    legit = A.assess("recipe_surface", _observed(track_a.RECIPE_CONTROL, True))
    assert (legit.reading, legit.condition) == (b.HELD, None)
    withheld = A.assess("permission_ablation", _observed(hostile, True))
    assert withheld.reading == b.BREACH


def _reading(result):
    return (result.reading, result.oracle.verdict, result.oracle.condition)


def test_a_path_that_refuses_what_carbon_admits_and_runs_is_a_wrongful_refusal():
    wrongful = (b.WRONGFUL_REFUSAL, b.BREACHED, "FAILING_TRIGGER")
    control = A.assess("recipe_surface", _observed(track_a.RECIPE_CONTROL, False))
    assert _reading(control) == wrongful
    assert "agrees" not in control.basis
    ablation = A.assess("permission_ablation", _observed(track_a.RECIPE_CONTROL, False))
    assert _reading(ablation) == wrongful
    valid = {
        "name": "p",
        "value": track_a.mandatory_control(),
        "path_accepted": False,
        "refusal_kind": "construction",
    }
    assert _reading(A.assess("mandatory_failure", valid)) == wrongful
    # Only a construction-level refusal is a wrongful rejection. The same valid
    # control refused for a request-level reason (an invalid argument, a
    # missing field) is UNDETERMINED: the family judges nothing, never a
    # finding (OWNER-GRAPHITE triage item 5).
    request_refused = {**valid, "refusal_kind": "request"}
    assert _reading(A.assess("mandatory_failure", request_refused)) == (
        b.UNDETERMINED,
        b.INCONCLUSIVE,
        None,
    )
    # Carbon admits it but the pods do not serve it: the refusal may be the
    # path's own, so it is undetermined, never HELD and never a finding.
    unserved = track_a._strategy(backend="pytorch", steps=100)
    reading = A.assess("recipe_surface", _observed(unserved, False))
    assert _reading(reading) == (b.UNDETERMINED, b.INCONCLUSIVE, None)
    # Agreement in either direction is HELD.
    nan = dict(track_a.mandatory_inputs())["nan_voltage"]
    refused = {"name": "p", "value": nan, "path_accepted": False}
    assert A.assess("mandatory_failure", refused).reading == b.HELD


def _code_run(seconds, lane=b.ATTACKER_LANE, accepted=True):
    arguments = {"kind": "workspace", "action": "run_python"}
    if seconds is not None:
        arguments["arguments_json"] = json.dumps({"seconds": seconds})
    attempt = {"name": "run", "arguments": arguments, "path_accepted": accepted}
    if lane is not None:
        attempt["lane"] = lane
    return attempt


def test_an_observed_attacker_code_run_dispatched_over_the_allowance_is_a_breach():
    assert A.assess("resource_accounting", _code_run(3600)).reading == b.BREACH
    assert A.assess("resource_accounting", _code_run(60)).reading == b.HELD
    assert A.assess("resource_accounting", _code_run(3600, accepted=False)).reading == (
        b.HELD
    )
    # A refused run the rule admits: the path may refuse for reasons the
    # code-run rule does not judge. Undetermined, never HELD, never a finding.
    refused = A.assess("resource_accounting", _code_run(60, accepted=False))
    assert _reading(refused) == (b.UNDETERMINED, b.INCONCLUSIVE, None)


def test_a_miner_lane_code_run_is_not_judged_by_the_attacker_rule():
    """The miner's own research has no Carbon limits (`research_carrier`): a
    run with no allowance, or a long one, on any lane but the Attacker's is
    never a finding."""
    for lane in (None, "miner_research", "carbon_worker"):
        for seconds in (None, 3600, 1):
            reading = A.assess("resource_accounting", _code_run(seconds, lane=lane))
            assert _reading(reading) == (b.NOT_APPLICABLE, b.NOT_RUN, None), (
                lane,
                seconds,
            )


def test_an_attempt_without_input_or_independent_gate_is_not_run():
    missing = A.assess("staged_bytes", {"name": "x", "arguments": {}})
    assert (missing.reading, missing.oracle.verdict) == (b.NOT_APPLICABLE, b.NOT_RUN)
    observed = {"name": "x", "value": {"probes": []}, "path_accepted": True}
    no_gate = A.assess("practice_disclosure", observed)
    assert (no_gate.reading, no_gate.oracle.verdict) == (b.NOT_APPLICABLE, b.NOT_RUN)


def test_an_attempt_object_with_a_name_and_a_value_is_read():
    attempt = b.AttackInput(
        "too_long", {"kind": "code_run", "arguments": {"seconds": 601}}
    )
    assert A.oracle("resource_accounting", attempt).verdict == b.HELD


def test_a_hold_the_detector_cannot_vouch_for_is_inconclusive():
    spec = dataclasses.replace(
        A.family_spec("resource_accounting"),
        specimen=b.resource_boundary,  # the specimen is the real boundary
    )
    attack = dict(spec.attacks())["seconds_one_hour"]
    reading = A.assess(spec, ("seconds_one_hour", attack))
    assert reading.oracle.verdict == b.INCONCLUSIVE and reading.condition is None


def test_a_boundary_that_does_not_answer_is_never_a_pass():
    def lost(_value):
        raise TimeoutError("pod lost")

    spec = dataclasses.replace(A.family_spec("resource_accounting"), boundary=lost)
    attack = dict(spec.attacks())["seconds_one_hour"]
    reading = A.assess(spec, ("seconds_one_hour", attack))
    assert reading.oracle.verdict == "TIMEOUT" and reading.condition is None


def test_protected_material_is_withheld_and_only_an_exposure_when_it_got_through():
    calls = []

    def spy(strategy):
        calls.append(strategy)
        return {"accepted": False}

    spec = dataclasses.replace(
        A.family_spec("recipe_surface"),
        boundary=spy,
        specimen=spy,
        admissible=spy,
        runnable=spy,
    )
    probe = track_a._strategy(hidden_case_ids=["a"])
    withheld = (b.PROTECTED_WITHHELD, b.NOT_RUN, None)
    exposure = (b.EXPOSURE, b.BREACHED, "OTHER_SIGNAL")
    # Declared, refused by the path, or an unknown outcome: no finding.
    assert _reading(A.assess(spec, ("probe", probe))) == withheld
    assert _reading(A.assess(spec, _observed(probe, False))) == withheld
    assert _reading(A.assess(spec, _observed(probe, None))) == withheld
    # The path accepted it, or a result carries it: an exposure.
    assert _reading(A.assess(spec, _observed(probe, True))) == exposure
    leaked = {**_observed(track_a.RECIPE_CONTROL, True), "result": {"hidden_case": 1}}
    assert b._protected(leaked["result"])
    assert _reading(A.assess(spec, leaked)) == exposure
    assert calls == []  # the input never reached a boundary or a specimen


def test_a_wrongly_refused_control_fails_its_check(monkeypatch):
    monkeypatch.setattr(b, "code_run_refusal", lambda arguments: "refused_all")
    (control,) = [
        c
        for c in A.controls("trained")
        if c.name == "resource_accounting_trained_code_run_at_the_allowance"
    ]
    assert control.check() is False


# -- rebuild --------------------------------------------------------------------------------------
def test_carbon_rebuilds_with_admit_and_refuses_with_a_typed_code():
    from carbon.agent_campaign.graphite import experiment

    rebuilt = A.rebuild(track_a.RECIPE_CONTROL)
    assert isinstance(rebuilt, b.Rebuilt) and rebuilt.detail["served"]
    assert rebuilt.detail["record"] == experiment.admit(track_a.RECIPE_CONTROL, 0)
    assert rebuilt.rebuilt_digest == b._digest(rebuilt.detail["record"])
    seeded = A.rebuild({"strategy": track_a.RECIPE_CONTROL, "seed": 7})
    assert seeded.detail["record"]["seed"] == 7
    torch = A.rebuild(track_a._strategy(backend="pytorch", steps=100))
    assert isinstance(torch, b.Rebuilt) and not torch.detail["served"]
    assert torch.detail["reason"] == "backend_not_served:pytorch"
    for name, strategy in track_a.RECIPE_ATTACKS:
        refused = A.rebuild(strategy)
        assert isinstance(refused, b.Unrebuildable), name
        assert refused.code in CORE_REFUSALS, (name, refused.code)
        assert refused.detail.split(":")[0] in b.REFUSAL_CODES, name
    cases = {
        "not_declarative": "not a strategy",
        "refused_by_contract": track_a._strategy(blob="x" * 20000),
        "protected_material": track_a._strategy(hidden_case_ids=["a"]),
        "outside_level": track_a._strategy(label_method="reference_solver"),
        "unknown_construction": {"strategy": track_a.RECIPE_CONTROL, "seed": -1},
    }
    for code, construction in cases.items():
        assert A.rebuild(construction).code == code, code
    assert A.rebuild(track_a._strategy(width=object())).detail == "strategy_not_json"
    assert A.rebuild_differences(rebuilt, dict(rebuilt.detail["record"])) == []


def test_a_stale_contract_record_is_carbons_side_never_the_constructions(monkeypatch):
    from carbon.agent_campaign.graphite import experiment

    def unrecorded(scoring=None):
        raise experiment.Unrebuildable("construction_contract_unrecorded")

    monkeypatch.setattr(experiment, "recorded_contract", unrecorded)
    refused = A.rebuild(track_a.RECIPE_CONTROL)
    assert refused.code == "rebuild_failed_infra"
    assert A.carbon_code(refused) == "construction_contract_unrecorded"
    assert A.admission_refusals(track_a.RECIPE_CONTROL)[0] == (
        "construction_contract_unrecorded"
    )


# -- seams ----------------------------------------------------------------------------------------
def test_higher_level_families_are_not_run_seams_with_nothing_to_execute():
    from carbon.challenge_pipeline.ladder import LEVELS

    seams = A.level_families()
    assert {s.state for s in seams} == {b.NOT_RUN}
    # Every ladder level is a seam here or has its own registered adapter
    # (Level 1: `adapters.battery_level1`, GRAPHITE-L1-BUILD-01).
    own = {
        level
        for challenge, level in adapters.registered()
        if challenge == b.CHALLENGE_ID and level > 0
    }
    assert {s.level for s in seams} | own == set(LEVELS)
    assert not {s.level for s in seams} & own
    assert {s.check for s in seams} <= CHECKS[b.TRACK]
    for seam in seams:
        assert not any(callable(v) for v in dataclasses.asdict(seam).values())
        if seam.level >= 3:
            assert "reserved: security owner" in seam.reason


def test_a_seam_names_the_registered_variant_it_waits_on():
    """A seam at a level whose development variant is registered names that
    variant and why the level is still not run; it never claims the level
    has no proposal (the Level 2 reason did, after battery-l2-spectral-v1)."""
    from carbon.reconstruction import development_variants as dv

    registry = dv.load()
    for seam in A.level_families():
        found = registry.current.get((b.CHALLENGE_ID, seam.level))
        if found is None or seam.level == dv.GRAPH_ONLY_LEVEL:
            # Level 4's seam is replaced by its own adapter, battery_level4.
            continue
        assert dv.variant(b.CHALLENGE_ID, seam.level).version in seam.reason
        assert "no attack adapter" in seam.reason
        assert "no Level" not in seam.reason


def test_a_research_tool_call_maps_to_the_family_it_probes():
    from carbon.development_session.research_tools import PREFIX

    assert A.family_for(PREFIX + "dry_validate") == "recipe_surface"
    assert (
        A.family_for(PREFIX + "start_research_task", {"action": "run_python"})
        == "resource_accounting"
    )
    assert A.family_for(PREFIX + "start_research_task", {"kind": "practice"}) == (
        "recipe_surface"
    )
    assert A.family_for(PREFIX + "get_research_result") == "practice_disclosure"
    assert A.family_for(PREFIX + "unknown_tool") is None


# -- the engine never reads held-out controls ------------------------------------------------------
def test_the_engine_control_reads_the_trained_split_only(monkeypatch):
    real = A.control_specs
    asked = []

    def control_specs(split):
        asked.append(split)
        if split != "trained":
            raise AssertionError("the engine read a held-out control")
        return real(split)

    monkeypatch.setattr(A, "control_specs", control_specs)
    for name in ("resource_accounting", "mandatory_failure"):
        assert A.trained_control(name)()
    assert set(asked) == {"trained"}


def test_the_engine_runs_the_families_with_trained_controls():
    engine = pytest.importorskip("carbon.agent_campaign.attack.engine")
    trained = A.controls("trained")
    for definition in A.families():
        if definition.name not in ("resource_accounting", "recipe_forgery"):
            continue
        run = engine.run_family(
            definition.family,
            budget=100,
            controls=[c for c in trained if c.family == definition.name],
        )
        assert engine.family_state(run) == "IN_PROGRESS"
        assert engine.findings([run]) == []
        with pytest.raises(engine.HeldOutControlRefused):
            engine.run_family(
                definition.family,
                controls=[
                    c for c in A.controls("held_out") if c.family == definition.name
                ],
            )


# -- mutations: each disabled boundary turns its guard red -----------------------------------------
_UNKNOWN = {"weights", "pretrained_weights", "loss_expression"}


def _compiler_accepts_unknown_field(m):
    from carbon.battery import compile as compile_module

    original = compile_module.compile_recipe

    def lax(strategy, **kwargs):
        if isinstance(strategy, dict) and isinstance(strategy.get("parameters"), dict):
            kept = {
                k: v for k, v in strategy["parameters"].items() if k not in _UNKNOWN
            }
            strategy = {**strategy, "parameters": kept}
        return original(strategy, **kwargs)

    m.setattr(compile_module, "compile_recipe", lax)


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


def _aggregate(eligible):
    from carbon.battery import exam

    original = exam.aggregate

    def mutated(rows):
        out = original(rows)
        return {**out, "eligible": eligible(out)}

    return mutated


def _averaging_scorer(m):
    from carbon.battery import exam

    m.setattr(exam, "aggregate", _aggregate(lambda out: out["n_scored"] > 0))


def _missing_prediction_typed_failed_infra(m):
    """Graphite's frozen rule excludes a missing case again: battery's
    scoring reads `cover` from its own module."""
    from carbon.challenge_validator import battery_scoring

    def excluding(predictions, case_ids):
        source = predictions if isinstance(predictions, dict) else {}
        return {case: source.get(case) for case in case_ids}, []

    m.setattr(battery_scoring, "cover", excluding)


def _daemon_accepts_a_null_prediction(m):
    """Battery's validator checks the keys only, as before the ruling: a case
    given null is typed FAILED_INFRA by the exam and excluded. `_infer`
    reads `incomplete` from the daemon module."""
    from carbon.battery import daemon

    m.setattr(
        daemon,
        "incomplete",
        lambda predictions, asked: set(predictions) != set(asked),
    )


def _nonfinite_typed_failed_infra(m):
    """The exam drops a non-finite case: a schema_finite failure typed
    FAILED_INFRA (`exam.evaluate` reads `evaluate_case` from `exam`)."""
    from carbon.battery import exam

    original = exam.evaluate_case

    def lax(pred, reference, *args, **kwargs):
        row = original(pred, reference, *args, **kwargs)
        if row["gates"].get("schema_finite") == exam.FAIL:
            return {"state": exam.FAILED_INFRA, "gates": {}}
        return row

    m.setattr(exam, "evaluate_case", lax)


def _leaky_stager(m):
    original = track_a.real_stager

    def leaky(recipe, inputs, batch):
        staged = original(recipe, inputs, batch)
        staged["infer"] = {**staged["infer"], "batch.json": json.dumps(batch).encode()}
        return staged

    m.setattr(track_a, "real_stager", leaky)


def _rebuilt_field_dropped(m):
    # The rebuild check's field list lives with the neutral scoring port
    # (VALIDATOR-01 slice 2), which `experiment.rebuild_differences` is.
    from carbon.challenge_validator import scoring

    m.setattr(
        scoring,
        "REBUILT_FIELDS",
        tuple(f for f in scoring.REBUILT_FIELDS if f != "program"),
    )


def _protected_marker_removed(m):
    # The check reads the leaf module's markers (#561); `tools` only
    # re-exports them, so patching `tools` would disable nothing.
    from carbon.agent_campaign.graphite import protected_material

    m.setattr(
        protected_material,
        "PROTECTED_MARKERS",
        tuple(x for x in protected_material.PROTECTED_MARKERS if "hidden" not in x),
    )


def _feedback_field_added(m):
    from carbon.battery import practice

    original = practice.feedback

    def wider(*args, **kwargs):
        return {**original(*args, **kwargs), "screening": {"pool_version": 3}}

    m.setattr(practice, "feedback", wider)


def _code_run_seconds_lifted(m):
    m.setattr(b, "CODE_RUN_SECONDS", 10**6)


def _battery_wall_allowance_lifted(m):
    from carbon.battery import research

    m.setattr(research, "PRACTICE_SECONDS", 3600)


def _non_conditions_finding(m):
    m.setitem(b.CONDITION_OF, b.BREACH, "EXPLOIT_CONFIRMED")


def _engine_reads_held_out(m):
    def leaky(self, name):
        spec = self.family_spec(name)
        return lambda: all(
            spec.control_check(c.value())
            for split in b.SPLITS
            for c in self.control_specs(split)
            if c.family == name
        )

    m.setattr(b.BatteryLevel0Adapter, "trained_control", leaky)


def _gate_swallows_crashes(m):
    original = b.gate

    def lax(strategy):
        try:
            return original(strategy)
        except Exception as crashed:  # noqa: BLE001 - the mutation under test
            return {"status": "REFUSED", "codes": [(type(crashed).__name__, "")]}

    m.setattr(b, "gate", lax)


def _guard_gate_crash():
    with pytest.MonkeyPatch.context() as m:
        test_a_crash_in_carbons_own_gate_is_never_a_hold(m)


def _guard_trained_split_only():
    with pytest.MonkeyPatch.context() as m:
        test_the_engine_control_reads_the_trained_split_only(m)


def _guard_breach_condition():
    spec = A.family_spec("resource_accounting")
    attack = dict(spec.attacks())["seconds_one_hour"]
    with pytest.MonkeyPatch.context() as m:
        _code_run_seconds_lifted(m)
        reading = A.assess(spec, ("seconds_one_hour", attack))
    assert reading.reading == b.BREACH
    assert reading.oracle.condition == "FAILING_TRIGGER"


MUTATIONS = {
    "compiler_accepts_an_unknown_field": (
        _compiler_accepts_unknown_field,
        lambda: _held_and_fired("recipe_surface"),
    ),
    "gate_admits_withheld_permissions": (
        _gate_admits_withheld_permissions,
        lambda: _held_and_fired("permission_ablation"),
    ),
    "rebuilt_field_dropped": (
        _rebuilt_field_dropped,
        lambda: _held_and_fired("rebuild_report"),
    ),
    "averaging_scorer": (
        _averaging_scorer,
        lambda: _held_and_fired("mandatory_failure"),
    ),
    "leaky_stager": (_leaky_stager, lambda: _held_and_fired("staged_bytes")),
    "protected_marker_removed": (
        _protected_marker_removed,
        test_protected_material_is_withheld_and_only_an_exposure_when_it_got_through,
    ),
    "code_run_seconds_lifted": (
        _code_run_seconds_lifted,
        lambda: _held_and_fired("resource_accounting"),
    ),
    "battery_wall_allowance_lifted": (
        _battery_wall_allowance_lifted,
        test_each_pinned_value_is_a_copy_of_its_battery_source,
    ),
    "feedback_field_added": (
        _feedback_field_added,
        lambda: _held_and_fired("practice_disclosure"),
    ),
    # GRAPHITE-COVERAGE-PARITY-01 retired `failed_infra_counted_as_a_pass`:
    # a partial set no longer has FAILED_INFRA cases to count. Its successor
    # restores the old typing itself.
    "missing_prediction_typed_failed_infra": (
        _missing_prediction_typed_failed_infra,
        test_a_partial_prediction_set_is_a_gate_failure_never_a_pass,
    ),
    "missing_prediction_excluded_on_graphite": (
        _missing_prediction_typed_failed_infra,
        lambda: _held_and_fired("prediction_omission"),
    ),
    "daemon_accepts_a_null_prediction": (
        _daemon_accepts_a_null_prediction,
        lambda: _held_and_fired("prediction_omission"),
    ),
    "nonfinite_case_typed_failed_infra": (
        _nonfinite_typed_failed_infra,
        lambda: _held_and_fired("selective_fault"),
    ),
    "non_conditions_finding": (_non_conditions_finding, _guard_breach_condition),
    "gate_crash_read_as_a_refusal": (_gate_swallows_crashes, _guard_gate_crash),
    "engine_reads_held_out_controls": (
        _engine_reads_held_out,
        _guard_trained_split_only,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_each_disabled_boundary_turns_its_guard_red(name, monkeypatch):
    mutate, guard = MUTATIONS[name]
    mutate(monkeypatch)
    with pytest.raises((AssertionError, ValueError)):
        guard()


def test_every_guard_passes_without_its_mutation():
    """The other half of the mutation check: unmutated, each guard holds
    (the family guards are the parametrized tests above)."""
    test_protected_material_is_withheld_and_only_an_exposure_when_it_got_through()
    test_each_pinned_value_is_a_copy_of_its_battery_source()
    test_a_partial_prediction_set_is_a_gate_failure_never_a_pass()
    _held_and_fired("selective_fault")
    _held_and_fired("prediction_omission")
    _guard_trained_split_only()
    _guard_breach_condition()
    _guard_gate_crash()


#: Under each accounting that drops hit cases, the attacks that dodge and the
#: path they dodge on.
_DODGES = {
    "missing_prediction_excluded_on_graphite": (
        "prediction_omission",
        {name: ("graphite",) for name, _ in b._omission_attacks()},
    ),
    "daemon_accepts_a_null_prediction": (
        "prediction_omission",
        {
            "null_the_important_region": ("interface_v1",),
            "null_the_worse_half": ("interface_v1",),
        },
    ),
    "nonfinite_case_typed_failed_infra": (
        "selective_fault",
        {
            "nonfinite_only_on_the_hard_cases": ("interface_v1", "graphite"),
            "infinite_capacity_on_the_worst_k_cases": ("interface_v1", "graphite"),
        },
    ),
}


@pytest.mark.parametrize("name", sorted(_DODGES))
def test_an_accounting_that_drops_hit_cases_turns_its_family_red(name, monkeypatch):
    """Which attacks breach, on which path, with the hit cases gone from the
    score; each reads BREACH with a FAILING_TRIGGER condition."""
    mutate, _guard = MUTATIONS[name]
    family, expected = _DODGES[name]
    mutate(monkeypatch)
    found = {}
    for attack, value in A.family_spec(family).attacks():
        result = b.fault_boundary(value)
        paths = tuple(p for p in b.FAULT_PATHS if b._dodged(result[p]))
        if paths:
            found[attack] = paths
            for path in paths:
                row = result[path]
                assert row["n_scored"] == row["n_cases"] - len(row["hit"])
            reading = A.assess(family, (attack, value))
            assert reading.reading == b.BREACH
            assert reading.oracle.condition == "FAILING_TRIGGER"
    assert found == expected
