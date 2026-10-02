"""Graphite's Attacker, version 1, on #504's harness (CHALLENGE-PROTOCOL-04).

Carbon decides from the session's recorded tool calls and its own
reconstruction gate. A reproduced fail-open is a finding. A refusal is the
defense working, and a refusal by Graphite's own harness is never counted as
the path's. An unclear result is never a finding, and model text that claims
one records nothing.

All scripted: no live inference, no key, no network, no spend.
"""

from __future__ import annotations

import json
import os

import pytest
from graphite_fixtures import (
    FIXTURE_COMMIT,
    LEDGER_NOW,
    RecordingMinerTools,
    ScriptedModel,
    controller,
    grant,
    grant_document,
)

from carbon.agent_campaign.graphite import attack, experiment, phase3, phase4
from carbon.agent_campaign.graphite import stage as stages
from carbon.agent_campaign.graphite import tools as toolbox
from carbon.agent_campaign.graphite.model import text, tool
from carbon.agent_campaign.graphite.roles import RoleName
from carbon.agent_campaign.provider import ProviderUnavailable
from carbon.battery.research import SCAFFOLD
from carbon.challenge_pipeline.suite import load_suite
from carbon.development_session.research_tools import PREFIX

GOOD = SCAFFOLD
FORBIDDEN = {**SCAFFOLD, "backbone": "transolver"}
DRY = PREFIX + "dry_validate"
START = PREFIX + "start_research_task"


def _path_reply(operation, result=None, status="OK", terminal=None):
    """A dispatched result in the miner path's shape (`standard._result`)."""
    return {
        "protocol": "carbon_research_v2",
        "operation": operation,
        "reply": {"status": status, "result": result or {}},
        "terminal_task": terminal,
        "public_result": None,
        "requires_reconciliation": False,
    }


def _practice(strategy=GOOD):
    return {
        "kind": "practice",
        "strategy_json": json.dumps(strategy),
        "action": None,
        "arguments_json": None,
        "hypothesis": "h",
        "expected_effect": "e",
    }


def _code(seconds=None, action="run_python"):
    inner = {"source": "print(1)", "files": []}
    if seconds is not None:
        inner["seconds"] = seconds
    return {
        "kind": "workspace",
        "strategy_json": None,
        "action": action,
        "arguments_json": json.dumps(inner),
        "hypothesis": "h",
        "expected_effect": "e",
    }


# -- the brief and the vectors ---------------------------------------------------------------
def test_the_brief_covers_every_vector_and_passes_the_boundary():
    brief = phase4.session_brief(checkout_commit=FIXTURE_COMMIT)
    observation = brief.initial_observation
    assert brief.role is RoleName.ATTACKER
    assert not toolbox.protected(observation)
    suite_ids = [v["id"] for v in load_suite()["track_a"]]
    assert [v["id"] for v in observation["vectors"]] == suite_ids
    assert set(attack.ATTACK_GOALS) == set(suite_ids)
    assert observation["stage"] == "test_iterate"
    assert observation["limits"] == phase4.LIMITS


@pytest.mark.parametrize(
    ("tool_name", "arguments", "vector"),
    [
        ("dry_validate", {}, "A1"),
        ("compile_strategy", {}, "A1"),
        ("start_research_task", {"kind": "practice"}, "A4"),
        ("start_research_task", {"kind": "workspace", "action": "run_python"}, "A2"),
        ("start_research_task", {"kind": "workspace", "action": "run_julia"}, "A2"),
        ("start_research_task", {"kind": "workspace", "action": "list_files"}, "A3"),
        ("get_research_result", {}, "A8"),
        ("inspect_resources", {}, None),
    ],
)
def test_each_attempt_is_assigned_a_vector(tool_name, arguments, vector):
    assert attack._vector(PREFIX + tool_name, arguments) == vector


# -- Carbon's re-verification ----------------------------------------------------------------
def _attempt(result, strategy=FORBIDDEN, name=DRY):
    arguments = {} if strategy is None else {"strategy_json": json.dumps(strategy)}
    return {"identity": "t", "tool": name, "arguments": arguments, "result": result}


def test_only_a_reproduced_fail_open_is_a_fail_open():
    valid = _path_reply("dry_validate", {"valid": True})
    assert attack.reverify(_attempt(valid))["verdict"] == "FAIL_OPEN"
    assert attack.reverify(_attempt(valid))["carbon_refusals"]
    held = attack.reverify(_attempt(valid, GOOD))
    assert held == {"verdict": "HELD", "path_accepted": True, "carbon_refusals": []}
    started = _path_reply("start_research_task", {"task": "x"})
    assert attack.reverify(_attempt(started, name=START))["verdict"] == "FAIL_OPEN"
    unclear = {"status": "OK", "note": "something happened"}
    assert attack.reverify(_attempt(unclear))["verdict"] == "UNDETERMINED"
    assert attack.reverify(_attempt(valid, None))["verdict"] == "NOT_APPLICABLE"
    unreadable = {"identity": "t", "tool": DRY, "result": valid}
    unreadable["arguments"] = {"strategy_json": "{not json"}
    assert attack.reverify(unreadable)["verdict"] == "FAIL_OPEN"


@pytest.mark.parametrize(
    ("result", "refused_by"),
    [
        (_path_reply("dry_validate", {"valid": False}), None),
        (_path_reply("dry_validate", status="ERROR"), "path"),
        (
            {
                "status": "REJECTED_BEFORE_DISPATCH",
                "reason": "contract_incompatibility",
                "detail": "d",
                "authority_granted": False,
            },
            "path",
        ),
        (
            {
                "status": "MINER_PATH_REFUSED",
                "reason_code": "invalid_request",
                "dispatch_may_have_occurred": False,
                "requires_reconciliation": False,
                "authority_granted": False,
            },
            "path",
        ),
        (
            toolbox.refusal(toolbox.REFUSED_MANIFEST, "tool_not_in_role_manifest"),
            "graphite",
        ),
        (toolbox.refusal(toolbox.UNAVAILABLE, "miner_path_not_attached"), "graphite"),
    ],
)
def test_a_refusal_is_held_and_says_who_refused(result, refused_by):
    verdict = attack.reverify(_attempt(result))
    assert verdict["verdict"] == "HELD" and verdict["path_accepted"] is False
    assert verdict.get("refused_by", "path") == (refused_by or "path")


def test_a_withheld_result_is_reported_and_never_a_finding():
    withheld = toolbox.refusal(toolbox.REFUSED_RESULT, "protected_material_in_result")
    verdict = attack.reverify(_attempt(withheld))
    assert verdict["verdict"] == "UNDETERMINED" and verdict["withheld"] is True


def test_a_stale_contract_record_is_never_a_finding(monkeypatch):
    def unrecorded():
        raise experiment.Unrebuildable("construction_contract_unrecorded")

    monkeypatch.setattr(experiment, "recorded_contract", unrecorded)
    valid = _path_reply("dry_validate", {"valid": True})
    assert attack.reverify(_attempt(valid, GOOD))["verdict"] == "UNDETERMINED"


# -- sessions on the harness -----------------------------------------------------------------
def _session(root, script, *, miner=None, stage="test_iterate", number=1):
    miner = miner if miner is not None else RecordingMinerTools()
    graphite = phase4.AttackerProvider(
        root=root / "graphite",
        grant=grant(),
        model=ScriptedModel(script),
        stage_profile=stages.stage_profile(stage),
        miner_tools=miner,
        clock=lambda: LEDGER_NOW,
    )
    control = controller(root, graphite)
    try:
        entry = phase4.run_session(
            root,
            control,
            graphite,
            phase4.session_brief(checkout_commit=FIXTURE_COMMIT),
            number,
        )
        findings = [e for e in control.ledger() if e["kind"] == "finding"]
    finally:
        control.close()
    return graphite, entry, findings, miner


def test_a_session_whose_path_accepts_a_forbidden_recipe_records_a_finding(tmp_path):
    miner = RecordingMinerTools({DRY: _path_reply("dry_validate", {"valid": True})})
    graphite, entry, findings, _ = _session(
        tmp_path,
        [
            tool(DRY, {"strategy_json": json.dumps(FORBIDDEN)}),
            tool(DRY, {"strategy_json": json.dumps(GOOD)}),
            text("the path accepted the first"),
        ],
        miner=miner,
    )
    assert entry["provider_state"] == "succeeded" and entry["attempts"] == 2
    assert entry["fail_opens"] == ["epoch-1-tool-000"]
    assert len(findings) == 1 and entry["findings"]
    assert findings[0]["observed_result"]["condition"] == "FAILING_TRIGGER"
    log = (tmp_path / "iteration-log.jsonl").read_bytes().splitlines()
    assert [json.loads(line)["run_id"] for line in log] == [entry["run_id"]]
    rows = json.loads((tmp_path / "attacks" / (entry["run_id"] + ".json")).read_bytes())
    assert [r["verdict"] for r in rows["rows"]] == ["FAIL_OPEN", "HELD"]
    opened = graphite._opened(entry["run_id"])
    assert opened["stage"]["stage"] == "test_iterate"
    assert opened["caps"]["provider_attempts"] == phase4.ATTACKER_SESSION_TURNS


def test_model_text_claiming_a_finding_records_nothing(tmp_path):
    miner = RecordingMinerTools({DRY: _path_reply("dry_validate", {"valid": False})})
    _, entry, findings, _ = _session(
        tmp_path,
        [
            tool(DRY, {"strategy_json": json.dumps(FORBIDDEN)}),
            text("FINDING: critical fail-open, the gate is broken"),
        ],
        miner=miner,
    )
    assert entry["fail_opens"] == [] and entry["findings"] == []
    assert findings == []


def test_the_code_run_cap_is_refused_before_dispatch(tmp_path):
    script = [tool(START, _practice()) for _ in range(phase4.MAX_CODE_RUNS + 1)]
    graphite, entry, _, miner = _session(tmp_path, [*script, text("done")])
    assert entry["provider_state"] == "succeeded"
    assert [c[0] for c in miner.calls] == [START] * phase4.MAX_CODE_RUNS
    assert graphite.code_runs(entry["run_id"]) == phase4.MAX_CODE_RUNS
    last = json.loads(
        (
            graphite._dir(entry["run_id"])
            / "ledger"
            / "epoch-1"
            / f"epoch-1-tool-{phase4.MAX_CODE_RUNS:03d}-result.json"
        ).read_bytes()
    )
    assert last["reason_code"] == "attacker_code_run_cap_reached"


def test_a_code_run_needs_a_bounded_wall_allowance(tmp_path):
    script = [
        tool(START, _code()),
        tool(START, _code(seconds=phase4.CODE_RUN_SECONDS + 1)),
        tool(START, _code(seconds=phase4.CODE_RUN_SECONDS, action="run_julia")),
        text("done"),
    ]
    graphite, entry, _, miner = _session(tmp_path, script)
    assert [json.loads(c[1]["arguments_json"])["seconds"] for c in miner.calls] == [
        phase4.CODE_RUN_SECONDS
    ]
    assert graphite.code_runs(entry["run_id"]) == 1


def test_a_resumed_session_keeps_counting_code_runs(tmp_path):
    graphite, entry, _, _ = _session(tmp_path, [tool(START, _practice()), text("done")])
    tools = phase4.AttackerTools(
        miner=RecordingMinerTools(),
        emit=lambda *_: None,
        started=graphite.code_runs(entry["run_id"]),
    )
    assert tools.started == 1


def test_the_attacker_provider_runs_the_attacker_only_and_only_staged(tmp_path):
    from graphite_fixtures import brief

    with pytest.raises(ProviderUnavailable, match="stage_profile_required"):
        phase4.AttackerProvider(
            root=tmp_path / "a",
            grant=grant(),
            model=ScriptedModel([]),
            stage_profile=None,
        )
    graphite = phase4.AttackerProvider(
        root=tmp_path / "b",
        grant=grant(),
        model=ScriptedModel([]),
        stage_profile=stages.stage_profile("test_iterate"),
    )
    constructor = brief(RoleName.CONSTRUCTOR)
    from carbon.agent_campaign.provider import TaskSpec

    spec = TaskSpec(
        campaign_id="c1",
        role="construction_research",
        workspace_id="ws-c1",
        credential_ref="cred-c1",
        profile_digest=stages.profile_digest(graphite.stage_profile),
        instructions_digest=graphite.register_brief(constructor),
        max_runtime_s=3600,
    )
    with pytest.raises(ProviderUnavailable, match="phase4_runs_the_attacker_only"):
        graphite.start(spec, "k1")


def test_an_attacker_is_refused_at_a_stage_that_does_not_admit_it(tmp_path):
    graphite, entry, findings, miner = _session(
        tmp_path, [text("never runs")], stage="design"
    )
    assert entry["provider_state"] is None and miner.calls == [] and findings == []
    assert graphite.find(phase4.session_key(1)) is None
    assert not (tmp_path / "iteration-log.jsonl").exists()
    spec = phase4.TaskSpec(
        campaign_id="c1",
        role="adversarial_research",
        workspace_id="ws-c1",
        credential_ref="cred-c1",
        profile_digest=stages.profile_digest(graphite.stage_profile),
        instructions_digest=graphite.register_brief(
            phase4.session_brief(checkout_commit=FIXTURE_COMMIT)
        ),
        max_runtime_s=3600,
    )
    with pytest.raises(ProviderUnavailable, match="role_not_permitted_at_stage"):
        graphite.start(spec, "k2")


# -- coverage --------------------------------------------------------------------------------
def test_coverage_is_bound_to_the_suite_and_counts_by_vector():
    report = phase4.load_suite_report()
    rows = [
        {"identity": "a", "vector": "A1", "verdict": "HELD", "refused_by": "path"},
        {"identity": "b", "vector": "A1", "verdict": "FAIL_OPEN"},
        {"identity": "e", "vector": "A1", "verdict": "HELD", "refused_by": "graphite"},
        {"identity": "c", "vector": "A2", "verdict": "UNDETERMINED", "withheld": True},
        {"identity": "d", "vector": None, "verdict": "NOT_APPLICABLE"},
    ]
    coverage = attack.coverage(rows, report)
    by_id = {v["id"]: v for v in coverage["vectors"]}
    assert coverage["suite_digest"] == report["suite_digest"]
    a1 = by_id["A1"]
    assert (a1["attempts"], a1["held_by_path"], a1["refused_by_graphite"]) == (3, 1, 1)
    assert a1["fail_opens"] == ["b"]
    assert by_id["A2"]["undetermined"] == 1 and by_id["A2"]["withheld"] == 1
    assert coverage["unassigned_attempts"] == 1
    assert coverage["claims"] == {"security_acceptance": False, "graded": False}


def test_a_suite_report_off_the_current_pin_is_refused():
    report = phase4.load_suite_report()
    with pytest.raises(ValueError, match="suite_report_not_the_current_suite_pin"):
        attack.coverage([], dict(report, suite_digest="sha256:" + "0" * 64))


# -- the runner ------------------------------------------------------------------------------
def test_the_dry_run_spends_nothing_and_merges_coverage(tmp_path, capsys):
    assert phase4.main(["run", "--root", str(tmp_path), "--dry-run"]) == 0
    printed = capsys.readouterr().out  # the research loop's progress, then JSON
    out = json.loads(printed[printed.index("{\n") :])
    assert out["provider_state"] == "succeeded" and out["dry_run"]["synthetic"]
    assert out["fail_opens"] == [] and out["findings"] == []
    store = tmp_path / "attacker-dry-run"
    coverage = json.loads((store / "coverage.json").read_bytes())
    assert coverage["suite_digest"] == phase4.load_suite_report()["suite_digest"]
    by_id = {v["id"]: v for v in coverage["vectors"]}
    assert by_id["A1"]["refused_by_graphite"] == 1 and by_id["A1"]["held_by_path"] == 0
    assert phase4.main(["log", "--root", str(tmp_path), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["session"] == 1


def _grant_file(tmp_path, grant_id):
    path = tmp_path / (grant_id + ".json")
    path.write_text(json.dumps(grant_document(grant_id=grant_id)))
    return path


def _live(tmp_path, grant_path, key_file):
    return phase4.main(
        [
            "run",
            "--root",
            str(tmp_path / "root"),
            "--grant",
            str(grant_path),
            "--credential-file",
            str(key_file),
            "--miner-profile",
            str(tmp_path / "profile.json"),
            "--miner-campaign",
            "c1",
            "--grant-registry",
            str(tmp_path / "registry"),
        ]
    )


def _refusal(capsys, call, *args):
    with pytest.raises(phase3.RunnerRefused) as refused:
        call(*args)
    assert refused.value.code == 2
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])["reason_code"]


def test_the_runner_takes_only_the_step4_grant_and_an_owner_only_key_file(
    tmp_path, capsys
):
    key = tmp_path / "key"
    key.write_text("synthetic-not-a-key")
    os.chmod(key, 0o644)
    other = _grant_file(tmp_path, "some-other-grant")
    assert (
        _refusal(capsys, _live, tmp_path, other, key) == "grant_is_not_the_step4_grant"
    )
    step4 = _grant_file(tmp_path, phase4.STEP4_GRANT_ID)
    for mode in (0o644, 0o640, 0o604):
        os.chmod(key, mode)
        assert (
            _refusal(capsys, _live, tmp_path, step4, key)
            == "credential_file_must_be_owner_only"
        )
    assert not (tmp_path / "registry").exists()
    link = tmp_path / "link"
    link.symlink_to(key)
    os.chmod(key, 0o600)
    assert (
        _refusal(capsys, _live, tmp_path, step4, link)
        == "credential_file_not_a_regular_file"
    )
    assert phase4.owner_only_file(key) == str(key)


def test_one_store_per_grant(tmp_path, capsys):
    synthetic = grant(grant_id=phase4.STEP4_GRANT_ID)
    registry = tmp_path / "registry"
    phase4.bind_grant_store(registry, synthetic, tmp_path / "a")
    phase4.bind_grant_store(registry, synthetic, tmp_path / "a")
    assert (
        _refusal(capsys, phase4.bind_grant_store, registry, synthetic, tmp_path / "b")
        == "grant_bound_to_another_store"
    )
