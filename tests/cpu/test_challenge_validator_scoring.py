"""The challenge-neutral scoring port for construction on Carbon's pods (VALIDATOR-01 slice 2).

Graphite's battery-only scoring moved behind `ChallengeScoring`. These tests
pin that battery is unchanged through the port: the same contract record, the
same build, the same data paths, the same worker deadline, the same frozen
rule and the same brief. They also pin that shared code holds no Challenge
default once a second scoring is registered. No pod, key, network or spend.
"""

import json
from pathlib import Path

import pytest

from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import miner_path, phase3, pod_phase, pods
from carbon.battery.challenge import CHALLENGE
from carbon.battery.research import SCAFFOLD
from carbon.challenge_validator import scoring as cs
from carbon.challenge_validator.battery_scoring import BatteryScoring
from carbon.reconstruction import capability_registry as registry

REPOSITORY = Path(__file__).resolve().parents[2]
EVIDENCE = "docs/development/evidence/exam-design-2026-09-24"
#: Graphite's battery data paths before the move (`pods.DATA_PATHS` at f49ac6d9f).
SHIPPED_BEFORE = (
    EVIDENCE + "/datasets/train-v1.jsonl.gz",
    EVIDENCE + "/ocv_table.json",
    EVIDENCE + "/refs-a-part2/out/records.jsonl",
)
#: The Constructor brief's objective before the move (`phase3.session_brief`).
OBJECTIVE_BEFORE = (
    "Propose battery TrainingStrategy recipes that beat the baseline under "
    "Carbon's frozen rule on public PRACTICE. Carbon runs, scores and "
    "rebuilds each proposal; you see development feedback only."
)


@pytest.fixture
def battery():
    return cs.scoring_for(CHALLENGE.challenge_id)


@pytest.fixture
def cooling():
    return cs.scoring_for(registry.COLD_PLATE_CHALLENGE)


class Second(BatteryScoring):
    """A second registered scoring, for the no-default rule."""


def test_two_registered_scorings_remove_every_silent_default(battery, cooling):
    assert cs.registered() == sorted(
        [
            registry.BATTERY_CHALLENGE,
            registry.COLD_PLATE_CHALLENGE,
            registry.MOTOR_CHALLENGE,
        ]
    )
    with pytest.raises(cs.ScoringUnavailable, match="challenge_scoring_must_be_named"):
        cs.scoring_for(None)
    with pytest.raises(cs.ScoringUnavailable, match="challenge_scoring_must_be_named"):
        cs.resolve(None)
    assert cs.resolve(battery) is battery
    assert cs.resolve(cooling) is cooling
    with pytest.raises(TypeError):
        cs.resolve(object())
    for unknown in ("cold-plate-v1", "", 7):
        with pytest.raises(cs.ScoringUnavailable) as refused:
            cs.scoring_for(unknown)
        assert refused.value.code == "challenge_scoring_not_registered"


def test_an_additional_scoring_keeps_every_silent_default_closed(monkeypatch):
    monkeypatch.setitem(cs._FACTORIES, "second-challenge-v1", Second)
    with pytest.raises(cs.ScoringUnavailable, match="challenge_scoring_must_be_named"):
        cs.scoring_for(None)
    with pytest.raises(cs.ScoringUnavailable):
        ex.recorded_contract()
    with pytest.raises(cs.ScoringUnavailable):
        pods.contract_work_seconds()
    with pytest.raises(miner_path.MinerPathRefused, match="must_be_named"):
        miner_path.check_challenge({"challenge": {"id": "x", "version": "1"}})
    # A named scoring still serves.
    assert ex.recorded_contract(cs.scoring_for(CHALLENGE.challenge_id))


def test_battery_is_unchanged_through_the_port(battery):
    assert battery.challenge() == {
        "id": CHALLENGE.challenge_id,
        "version": CHALLENGE.version,
    }
    assert battery.data_paths == SHIPPED_BEFORE == pods.data_paths(battery)
    assert battery.construction_objective == OBJECTIVE_BEFORE
    assert battery.baseline_strategy() is SCAFFOLD
    # The served backends are a versioned record (TORCH-POD-01): v1 is the
    # port's JAX-only set, unchanged; the current version adds PyTorch.
    from carbon.challenge_validator.battery_scoring import SERVED_BACKENDS

    assert SERVED_BACKENDS["battery-scoring-v1"] == ("jax",)
    assert battery.served_backends == SERVED_BACKENDS[battery.scoring_version]
    envelope = dict(registry.contract(registry.BATTERY_CHALLENGE).envelope)
    assert (
        pods.contract_work_seconds(battery)
        == envelope["worker_deadline_seconds"]
        == 600
    )
    assert pods.proposal_minutes(battery) == 30
    recorded = ex.recorded_contract(battery)
    assert recorded == battery.recorded_contract()
    assert recorded["contract_digest"] == registry.contract_digest(
        registry.BATTERY_CHALLENGE
    )


def test_the_build_is_the_same_by_every_route(battery):
    contract = ex.recorded_contract(battery)["contract_digest"]
    direct, _files, _program = battery.built_record(SCAFFOLD, contract, 7, REPOSITORY)
    via_pod, _, _ = pod_phase.built_record(SCAFFOLD, contract, 7, REPOSITORY)
    assert via_pod == direct
    admitted = ex.admit(SCAFFOLD, 7, REPOSITORY, scoring=battery)
    named = ex.admit(SCAFFOLD, 7, REPOSITORY, scoring=battery)
    assert (
        admitted == named == {**direct, "record_sequence": admitted["record_sequence"]}
    )
    assert set(cs.REBUILT_FIELDS) <= set(direct)
    assert ex.rebuild_differences(admitted, direct) == []
    assert ex.rebuild_differences(admitted, {**direct, "seed": 8}) == ["seed"]
    assert ex.rebuild_differences(admitted, None) == ["built_record_missing"]


def test_admission_refusals_keep_their_codes(battery):
    with pytest.raises(ex.Unrebuildable, match="strategy_not_an_object"):
        ex.admit([SCAFFOLD], 0, scoring=battery)
    other = {**SCAFFOLD, "challenge_id": registry.BURGERS_CHALLENGE}
    with pytest.raises(ex.Unrebuildable) as refused:
        ex.admit(other, 0, scoring=battery)
    assert refused.value.code == "not_the_battery_development_challenge"
    with pytest.raises(ex.Unrebuildable) as refused:
        ex.admit({**SCAFFOLD, "backbone": "transolver"}, 0, scoring=battery)
    assert refused.value.code in ("contract_refused", "recipe_rejected")
    torch = {**SCAFFOLD, "parameters": {**SCAFFOLD["parameters"], "backend": "pytorch"}}
    # Scoring v1 served JAX only, and its refusal keeps its code; v2
    # (TORCH-POD-01) builds PyTorch with the PyTorch pod program.
    from carbon.challenge_validator.battery_scoring import SERVED_BACKENDS
    from carbon.development_session.battery_gpu import TORCH_GPU_PROGRAM
    from carbon.development_session.profile import digest

    v1 = BatteryScoring()
    v1.served_backends = SERVED_BACKENDS["battery-scoring-v1"]
    with pytest.raises(ex.NotServed, match="backend_not_served:pytorch"):
        ex.admit(torch, 0, scoring=v1)
    admitted = ex.admit(torch, 0, scoring=battery)
    assert admitted["program"] == digest(TORCH_GPU_PROGRAM.encode())
    # The experiment module's error types are the port's own.
    assert ex.Unrebuildable is cs.Unrebuildable and ex.NotServed is cs.NotServed


def test_the_frozen_rule_is_battery_rule_v2_on_public_practice(battery):
    from carbon.battery import exam
    from carbon.battery.practice import PracticeSet

    rule = ex.frozen_rule(REPOSITORY, battery)
    assert type(rule) is type(battery.frozen_rule(REPOSITORY))
    margin = exam.RULES["v2"]["equivalence_margin_rel"]
    assert rule.identity["rule"] == "v2"
    assert rule.identity["equivalence_margin_rel"] == margin
    practice = PracticeSet.load(REPOSITORY)
    exact = {r["case_id"]: r["outputs"] for r in practice.records}
    rows, summary = rule.score(exact)
    assert len(rows) == len(practice.case_ids) and summary["eligible"] is True
    json.dumps([rows, summary], allow_nan=False)
    same = rule.compare(rows, rows, True)
    assert same["promotable"] is False


def test_protected_data_never_ships_whatever_a_challenge_declares(monkeypatch):
    for bad in (
        "docs/x/ev4-sealed.json",
        "docs/x/graphite-confirmation-v1.jsonl",
        "data/private/cases.json",
        "SECRET.txt",
        "keys/credential.json",
        "canary/cases.json",
    ):

        class Leaky(BatteryScoring):
            data_paths = (*SHIPPED_BEFORE, bad)

        with pytest.raises(ValueError, match="forbidden data path"):
            Leaky().ship_check()
        with pytest.raises(pods.PodFailure, match="forbidden data path") as refused:
            pods.ship_list("0" * 40, REPOSITORY, scoring=Leaky())
        assert refused.value.executed is False
    assert pods.FORBIDDEN_DATA is cs.FORBIDDEN_DATA


def test_the_brief_and_checks_follow_the_sessions_scoring(battery):
    from graphite_phase3_fixtures import grant

    budget = ex.phase3_budget(grant(), battery)
    brief = phase3.session_brief(
        checkout_commit="1" * 40, budget=budget, scoring=battery
    )
    observation = brief.initial_observation
    assert observation["challenge"] == battery.challenge()
    assert observation["objective"] == OBJECTIVE_BEFORE
    assert observation["baseline_strategy"] == SCAFFOLD
    assert observation["construction_contract"] == ex.recorded_contract(battery)
    phase3.check_observation(observation, battery)
    other = {
        **observation,
        "challenge": {"id": "burgers-dynamics-v1", "version": "1.0"},
    }
    with pytest.raises(phase3.ProviderUnavailable, match="phase3_challenge_not_served"):
        phase3.check_observation(other, battery)
    manifest = {"challenge": {**battery.challenge(), "extra": "kept"}}
    assert miner_path.check_challenge(manifest, battery) == manifest["challenge"]
    with pytest.raises(
        miner_path.MinerPathRefused,
        match="miner_campaign_is_not_the_sessions_challenge",
    ):
        miner_path.check_challenge(
            {"challenge": {"id": CHALLENGE.challenge_id}}, battery
        )
