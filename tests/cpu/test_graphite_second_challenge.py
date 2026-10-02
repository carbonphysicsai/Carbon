"""A second Challenge runs through Graphite's stage profile and Attacker with
no battery code (CHALLENGE-PROTOCOL-04, generalization).

A synthetic Challenge supplies only what `challenge.py` asks of every
Challenge: a Graphite record, an adapter, its pipeline record's construction
block and a suite map. Battery's adapter and #504's battery gate fail the test
if anything calls them.

All scripted: no live inference, no key, no network, no spend.
"""

from __future__ import annotations

import json
import types

import pytest
from graphite_fixtures import (
    FIXTURE_COMMIT,
    LEDGER_NOW,
    RecordingMinerTools,
    ScriptedModel,
    controller,
    grant,
)

from carbon.agent_campaign.graphite import attack, experiment, phase4
from carbon.agent_campaign.graphite import challenge as challenges
from carbon.agent_campaign.graphite import stage as stages
from carbon.agent_campaign.graphite.adapters import battery as battery_adapter
from carbon.agent_campaign.graphite.model import text, tool
from carbon.agent_campaign.provider import ProviderUnavailable
from carbon.challenge_pipeline import suite
from carbon.development_session.research_tools import PREFIX

TOKEN = "synthetic-second-challenge-v1"
DRY = PREFIX + "dry_validate"
START = PREFIX + "start_research_task"
INSIDE = {"challenge_id": TOKEN, "model": "registered"}
OUTSIDE = {"challenge_id": TOKEN, "model": "unregistered"}
SECONDS = 60
TURNS = 6
RECORD = {
    "schema": challenges.SCHEMA,
    "challenge": TOKEN,
    "family": "f99",
    "label": "the synthetic challenge",
    "adapter": challenges.ADAPTERS + "synthetic",
    "suite_report": "synthetic/SUITE_V1_COVERAGE.json",
    "attack_goals": {"A4": "Is the synthetic worker's wall clock enforced?"},
    "attacker_campaign": {
        "campaign": "graphite-synthetic-attacker",
        "workspace": "graphite-synthetic-attacker-workspace",
        "credential_ref": "graphite-synthetic-engy",
        "grant": {"id": "SYNTHETIC-GRANT", "file": "synthetic/grant.json"},
        "ceiling_usd": "1.00",
        "session_turns": TURNS,
        "authority": "synthetic test fixture; no owner value",
    },
}


def _adapter(level):
    def admission_refusals(strategy):
        return [] if strategy.get("model") == "registered" else ["model_unregistered"]

    return types.SimpleNamespace(
        permission_inventory=lambda: {
            "schema": "carbon.agent-campaign.permission-inventory.v1",
            "challenge": TOKEN,
            "profile": f"level-{level}",
            "permitted": [{"id": "model.registered"}],
            "not_permitted": ["model.unregistered"],
        },
        public_identity=lambda: {"id": TOKEN, "version": "1"},
        admission_refusals=admission_refusals,
        code_run_seconds=lambda: SECONDS,
        recipe_outside_contract=lambda: dict(OUTSIDE),
    )


def _forbid_battery(monkeypatch):
    def battery_called(*_args, **_kwargs):
        raise AssertionError("battery code was called for another Challenge")

    for name in challenges.ADAPTER_FUNCTIONS:
        monkeypatch.setattr(battery_adapter, name, battery_called)
    monkeypatch.setattr(experiment, "admit", battery_called)


def _suite_map(directory):
    shared = suite.load_suite()
    document = {
        "schema": "carbon.challenge-pipeline.suite-map.v1",
        "suite_version": shared["suite_version"],
        "challenge": TOKEN,
        "family": RECORD["family"],
        "environment_groups": [],
        "track_a": {
            vid: {"checks": [], "sandbox": [], "gaps": ["synthetic"]}
            for vid in suite.VECTORS
        },
        "track_b": {b["id"]: {"note": "synthetic"} for b in shared["track_b"]},
        "exam": {"note": "synthetic"},
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (TOKEN + ".json")).write_text(json.dumps(document))
    return directory


def _suite_report(level, maps):
    """The suite runner's report shape for this Challenge, with no check run."""
    vectors = []
    for vector in suite.load_suite()["track_a"]:
        ladder = vector["ladder"]
        code = ladder["participant_code_from_level"]
        vectors.append(
            {
                "id": vector["id"],
                "name": vector["name"],
                "status": "NOT_RUN",
                "checks": [],
                "participant_code": None
                if code is None
                else {
                    "what": ladder["participant_code"],
                    "from_level": code,
                    "status": "IN_SCOPE" if level >= code else "NOT_RUN",
                },
                "gaps": vector["gaps"] + ["synthetic"],
                "open_parameters": vector["open_parameters"],
            }
        )
    return {
        "schema": "carbon.challenge-pipeline.suite-run.v1",
        "suite_digest": suite.digest(),
        "challenge": TOKEN,
        "map_digest": suite.map_digest(TOKEN, maps),
        "construction_level": level,
        "commit": None,
        "vectors": vectors,
    }


@pytest.fixture
def synthetic(monkeypatch, tmp_path):
    """Register the synthetic Challenge at a level; return a builder."""
    _forbid_battery(monkeypatch)
    maps = _suite_map(tmp_path / "suite_maps")
    monkeypatch.setattr(attack, "SUITE_MAPS", maps)

    def at(level, pipeline_level=None):
        construction = {
            "challenge": TOKEN,
            "level": level if pipeline_level is None else pipeline_level,
            "levels": [],
        }
        challenge = challenges.from_record(RECORD, _adapter(level), construction)
        monkeypatch.setitem(challenges.REGISTERED, TOKEN, challenge)
        return challenge, _suite_report(level, maps)

    return at


def _session(root, challenge, script, miner):
    graphite = phase4.AttackerProvider(
        root=root / "graphite",
        grant=grant(),
        model=ScriptedModel(script),
        stage_profile=stages.stage_profile("test_iterate", challenge),
        miner_tools=miner,
        clock=lambda: LEDGER_NOW,
    )
    control = controller(root, graphite)
    try:
        entry = phase4.run_session(
            root,
            control,
            graphite,
            phase4.session_brief(challenge, checkout_commit=FIXTURE_COMMIT),
            1,
        )
        findings = [e for e in control.ledger() if e["kind"] == "finding"]
    finally:
        control.close()
    return graphite, entry, findings


def _valid():
    return {
        "protocol": "carbon_research_v2",
        "operation": "dry_validate",
        "reply": {"status": "OK", "result": {"valid": True}},
        "terminal_task": None,
        "public_result": None,
        "requires_reconciliation": False,
    }


def test_a_second_challenge_gets_its_own_stage_profile_and_level(synthetic):
    challenge, _ = synthetic(0)
    profile = stages.stage_profile("test_iterate", TOKEN)
    assert profile["challenge"] == TOKEN and profile["construction_level"] == 0
    assert stages.check(profile)["stages"]["test_iterate"]
    # The same Challenge, given as an object rather than its token.
    assert stages.stage_profile("test_iterate", challenge) == profile
    assert challenge.construction_level() == 0


def test_its_level_must_agree_with_its_pipeline_record(synthetic):
    synthetic(1, pipeline_level=0)
    with pytest.raises(
        ValueError, match="construction_level_disagrees_with_pipeline_record"
    ):
        stages.stage_profile("test_iterate", TOKEN)


def test_a_session_after_its_level_changed_is_refused(synthetic, tmp_path):
    synthetic(0)
    profile = stages.stage_profile("test_iterate", TOKEN)
    synthetic(1)
    with pytest.raises(ProviderUnavailable, match="construction_level_mismatch"):
        phase4.AttackerProvider(
            root=tmp_path / "g",
            grant=grant(),
            model=ScriptedModel([]),
            stage_profile=profile,
        )


def test_an_attacker_session_and_coverage_run_on_it_without_battery_code(
    synthetic, tmp_path
):
    challenge, report = synthetic(0)
    script = [
        tool(DRY, {"strategy_json": json.dumps(OUTSIDE)}),
        tool(DRY, {"strategy_json": json.dumps(INSIDE)}),
        tool(
            START,
            {
                "kind": "workspace",
                "strategy_json": None,
                "action": "run_python",
                "arguments_json": json.dumps(
                    {"source": "print(1)", "files": [], "seconds": SECONDS + 1}
                ),
                "hypothesis": "h",
                "expected_effect": "e",
            },
        ),
        text("done"),
    ]
    miner = RecordingMinerTools({DRY: _valid()})
    graphite, entry, findings = _session(tmp_path, challenge, script, miner)
    assert entry["provider_state"] == "succeeded"
    assert (entry["challenge"], entry["construction_level"]) == (TOKEN, 0)
    assert entry["fail_opens"] == ["epoch-1-tool-000"] and len(findings) == 1
    assert [c[0] for c in miner.calls] == [DRY, DRY]  # the code run was refused
    refused = json.loads(
        (
            graphite._dir(entry["run_id"])
            / "ledger"
            / "epoch-1"
            / "epoch-1-tool-002-result.json"
        ).read_bytes()
    )
    assert refused["reason_code"] == f"code_run_needs_seconds_up_to_{SECONDS}"
    opened = graphite._opened(entry["run_id"])
    assert opened["caps"]["provider_attempts"] == TURNS
    assert opened["task"]["campaign_id"] == "graphite-synthetic-attacker"
    brief = phase4.session_brief(challenge, checkout_commit=FIXTURE_COMMIT)
    observation = brief.initial_observation
    assert observation["challenge"] == {"id": TOKEN, "version": "1"}
    assert observation["objective"].startswith("Probe the synthetic challenge's")
    goals = {v["id"]: v["goal"] for v in observation["vectors"]}
    assert goals["A4"] == RECORD["attack_goals"]["A4"]
    assert goals["A1"] == attack.ATTACK_GOALS["A1"]

    coverage = phase4.write_coverage(tmp_path, report, challenge)
    assert coverage["challenge"] == TOKEN and coverage["construction_level"] == 0
    by_id = {v["id"]: v for v in coverage["vectors"]}
    assert by_id["A1"]["fail_opens"] == ["epoch-1-tool-000"]
    assert by_id["A1"]["held_by_path"] == 1
    assert {
        vid for vid, v in by_id.items() if (v["participant_code"] or {}).get("status")
    } == {"A1", "A2", "A4"}
    assert all(
        v["participant_code"]["status"] == "NOT_RUN"
        for v in by_id.values()
        if v["participant_code"]
    )


def test_at_level_4_participant_code_is_in_scope_and_level_5_is_not_run(
    synthetic, tmp_path
):
    challenge, report = synthetic(4)
    rows = [{"identity": "a", "vector": "A2", "verdict": "HELD", "refused_by": "path"}]
    coverage = attack.coverage(rows, report, challenge=challenge, construction_level=4)
    assert coverage["levels_not_run"] == [5]
    parts = [
        v["participant_code"] for v in coverage["vectors"] if v["participant_code"]
    ]
    assert parts and all(p["status"] == "IN_SCOPE" for p in parts)
    with pytest.raises(ValueError, match="suite_report_at_another_construction_level"):
        attack.coverage(rows, report, challenge=challenge, construction_level=0)


def test_coverage_refuses_another_challenges_report_or_mixed_levels(
    synthetic, tmp_path
):
    challenge, report = synthetic(0)
    other = dict(report, challenge="battery-fastcharge-ageing-development-v1")
    with pytest.raises(ValueError, match="suite_report_for_another_challenge"):
        attack.coverage([], other, challenge=challenge, construction_level=0)
    attacks = tmp_path / "store" / "attacks"
    attacks.mkdir(parents=True)
    for run_id, level in (("r1", 0), ("r2", 1)):
        (attacks / (run_id + ".json")).write_text(
            json.dumps(
                {
                    "schema": attack.ROWS_SCHEMA,
                    "run_id": run_id,
                    "challenge": TOKEN,
                    "construction_level": level,
                    "rows": [],
                }
            )
        )
    with pytest.raises(phase4.RunnerRefused):
        phase4.write_coverage(tmp_path / "store", report, challenge)


def test_a_malformed_record_or_adapter_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(challenges, "RECORDS", tmp_path)
    (tmp_path / (TOKEN + ".json")).write_text(json.dumps(dict(RECORD, adapter="os")))
    with pytest.raises(
        challenges.ChallengeError, match="adapter_outside_the_adapters_package"
    ):
        challenges.get(TOKEN)
    for bad, code in (
        (dict(RECORD, schema="other"), "challenge_record_schema"),
        (dict(RECORD, challenge="Not A Token"), "challenge_is_a_contract_token"),
        (
            dict(RECORD, attack_goals={"A9": "no such vector"}),
            "attack_goals_reword_suite_vectors",
        ),
        (
            dict(
                RECORD,
                attacker_campaign=dict(RECORD["attacker_campaign"], session_turns=0),
            ),
            "attacker_session_turns_is_a_positive_integer",
        ),
    ):
        with pytest.raises(challenges.ChallengeError, match=code):
            challenges.from_record(bad, _adapter(0), {"challenge": bad["challenge"]})
    with pytest.raises(challenges.ChallengeError, match="adapter_lacks_a_function"):
        challenges.from_record(
            RECORD, types.SimpleNamespace(), {"challenge": TOKEN, "level": 0}
        )
    with pytest.raises(
        challenges.ChallengeError, match="pipeline_record_names_another_contract"
    ):
        challenges.from_record(
            RECORD, _adapter(0), {"challenge": "another", "level": 0}
        )
    with pytest.raises(challenges.ChallengeError, match="challenge_not_recorded"):
        challenges.get("no-such-challenge-v1")
