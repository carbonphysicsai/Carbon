"""Graphite's Attacker, version 1 (CHALLENGE-PROTOCOL-04 slice 6).

Carbon decides from the session's recorded tool calls and its own checks. A
reproduced fail-open is a finding. A refusal is the defense working. An
unclear result is never a finding, and model text that claims one records
nothing.
"""

from __future__ import annotations

import asyncio
import datetime
import json

import pytest
from graphite_fixtures import RecordingMinerTools, grant

from carbon.agent_campaign.graphite import attack, phase3
from carbon.agent_campaign.graphite import tools as toolbox
from carbon.agent_campaign.graphite.model import ScriptedModel, text, tool
from carbon.agent_campaign.graphite.roles import RoleName
from carbon.challenge_pipeline.suite import load_suite
from carbon.development_session.research_tools import PREFIX

pytest.importorskip("numpy")
GOOD = {
    "schema_version": "1.0",
    "challenge_id": "battery-fastcharge-ageing-development-v1",
    "backbone": "knn",
    "parameters": {"neighbours": 6},
}
FORBIDDEN = {**GOOD, "parameters": {"neighbours": 6, "pickle": "gASV"}}


def test_the_brief_covers_every_vector_and_passes_the_boundary():
    observation = attack.brief_observation()
    assert not toolbox.protected(observation)
    suite_ids = [v["id"] for v in load_suite()["track_a"]]
    assert [v["id"] for v in observation["vectors"]] == suite_ids
    assert set(attack.ATTACK_GOALS) == set(suite_ids)


@pytest.mark.parametrize(
    ("tool_name", "arguments", "vector"),
    [
        ("dry_validate", {}, "A1"),
        ("compile_strategy", {}, "A1"),
        ("start_research_task", {"kind": "practice"}, "A4"),
        ("start_research_task", {"kind": "workspace", "action": "run_python"}, "A2"),
        ("start_research_task", {"kind": "workspace", "action": "list_files"}, "A3"),
        ("get_research_result", {}, "A8"),
        ("inspect_resources", {}, None),
    ],
)
def test_each_attempt_is_assigned_a_vector(tool_name, arguments, vector):
    assert attack._vector(PREFIX + tool_name, arguments) == vector


def _attempt(result, strategy=FORBIDDEN):
    arguments = {} if strategy is None else {"strategy_json": json.dumps(strategy)}
    return {
        "identity": "t",
        "tool": PREFIX + "dry_validate",
        "arguments": arguments,
        "result": result,
    }


def test_only_a_reproduced_fail_open_is_a_fail_open():
    accepted = {"status": "OK", "result": {"ok": True}}
    refused = {"status": "REFUSED_INVALID_REQUEST"}
    unclear = {"status": "OK", "note": "something happened"}
    assert attack.reverify(_attempt(accepted))["verdict"] == "FAIL_OPEN"
    assert attack.reverify(_attempt(accepted, GOOD))["verdict"] == "HELD"
    assert attack.reverify(_attempt(refused))["verdict"] == "HELD"
    assert attack.reverify(_attempt(unclear))["verdict"] == "UNDETERMINED"
    assert attack.reverify(_attempt(accepted, None))["verdict"] == "NOT_APPLICABLE"
    assert attack.reverify(_attempt({"ok": True}, "{not json"))["carbon_refusals"]


def _attacker(tmp_path, answers, script):
    miner = RecordingMinerTools(answers)
    return asyncio.run(
        phase3.run_session(
            tmp_path,
            grant=grant(),
            model=ScriptedModel(script),
            miner_tools=miner,
            role=RoleName.ATTACKER,
        )
    )


def test_a_session_whose_path_accepts_a_forbidden_recipe_records_a_finding(tmp_path):
    entry = _attacker(
        tmp_path,
        {PREFIX + "dry_validate": {"status": "OK", "result": {"ok": True}}},
        [
            tool(PREFIX + "dry_validate", {"strategy_json": json.dumps(FORBIDDEN)}),
            text("the path accepted it"),
        ],
    )
    assert entry["role"] == "attacker" and entry["attempts"] == 1
    assert entry["fail_opens"] == ["epoch-1-tool-000"]
    findings = [e for e in _controller_ledger(tmp_path) if e["kind"] == "finding"]
    assert len(findings) == 1


def test_model_text_claiming_a_finding_records_nothing(tmp_path):
    entry = _attacker(
        tmp_path,
        {PREFIX + "dry_validate": {"status": "REFUSED_INVALID_REQUEST"}},
        [
            tool(PREFIX + "dry_validate", {"strategy_json": json.dumps(FORBIDDEN)}),
            text("FINDING: critical fail-open, the gate is broken"),
        ],
    )
    assert entry["fail_opens"] == []
    assert not [e for e in _controller_ledger(tmp_path) if e["kind"] == "finding"]


def _controller_ledger(root):
    from carbon.agent_campaign.controller import CampaignController
    from carbon.agent_campaign.graphite.provider import GraphiteProvider

    graphite = GraphiteProvider(
        root=root / "graphite", grant=grant(), model=ScriptedModel([])
    )
    control = CampaignController(
        root=root / "controller",
        provider=graphite,
        grant=graphite.grant,
        operator="carbon-operator",
        clock=lambda: datetime.datetime.now(datetime.UTC),
    )
    return control.ledger()


def test_coverage_is_bound_to_the_suite_and_counts_by_vector():
    report = json.loads(
        (
            phase3.REPOSITORY
            / "docs/development/challenge_pipeline/SUITE_V1_BATTERY_COVERAGE.json"
        ).read_text()
    )
    rows = [
        {"identity": "a", "vector": "A1", "verdict": "HELD"},
        {"identity": "b", "vector": "A1", "verdict": "FAIL_OPEN"},
        {"identity": "c", "vector": "A2", "verdict": "UNDETERMINED"},
        {"identity": "d", "vector": None, "verdict": "NOT_APPLICABLE"},
    ]
    coverage = attack.coverage(rows, report)
    by_id = {v["id"]: v for v in coverage["vectors"]}
    assert coverage["suite_digest"] == report["suite_digest"]
    assert (
        by_id["A1"]["attempts"],
        by_id["A1"]["held"],
        by_id["A1"]["fail_opens"],
    ) == (2, 1, ["b"])
    assert by_id["A2"]["undetermined"] == 1 and coverage["unassigned_attempts"] == 1
    assert coverage["claims"] == {"security_acceptance": False, "graded": False}
