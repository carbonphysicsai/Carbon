"""The phase-4 Attacker's stop rule (GRAPHITE-ATTACKER-STOP-RULE-01).

A session under the rule ends through its finish tool once every reachable
family has `STOP_RULE_K` counted attempts, or once money can be sure of no
more than `FINISH_NOTICE_CALLS` model calls; a text-only turn gets the
continue reminder, at most twice in a row, then the session stops typed. The
rule is frozen in the session record, so a session opened without it resumes
exactly as recorded. Families no offered tool reaches carry a registered
label, never a silent NOT_RUN.
"""

from __future__ import annotations

import io
import json
import socket
import types
from contextlib import redirect_stdout

import pytest

from carbon.agent_campaign.attack import analysis
from carbon.agent_campaign.attack.adapter import ADAPTERS
from carbon.agent_campaign.graphite import phase4
from carbon.agent_campaign.graphite.provider import ENGINE_TOOLS_V2, SESSION_LIMITS_V2
from carbon.agent_campaign.graphite.roles import ROLES, RoleName
from carbon.development_session.research_agent_policy import FINISH_NOTICE_CALLS
from carbon.development_session.research_loop import (
    ARGUMENTS_INVALID,
    STOPPED_NO_TOOL_USE,
    check_continue_reminder,
)
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE

CID = BATTERY_CHALLENGE
TOOLS = ROLES[RoleName.ATTACKER].tool_schemas()
REACHABLE = [
    "permission_ablation",
    "practice_disclosure",
    "recipe_surface",
    "resource_accounting",
    "staged_bytes",
]
#: The Test Lead's labels for battery Level 0's unreachable families.
LABELS = {
    "mandatory_failure": "not participant-reachable at this level",
    "recipe_forgery": "not participant-reachable at this level",
    "rebuild_identity": "queued: cross-attempt identity oracle (WAVE-04 §1)",
    "rebuild_report": "deferred: POD_REBUILD_SEAM not run",
}
#: One door per reachable family, as the Attacker's tools call it.
DOORS = {
    "permission_ablation": (
        "start_research_task",
        {"kind": "workspace", "action": "check_design"},
    ),
    "practice_disclosure": ("get_challenge_info", {}),
    "recipe_surface": ("dry_validate", {}),
    "resource_accounting": (
        "start_research_task",
        {"kind": "workspace", "action": "run_python"},
    ),
    "staged_bytes": (
        "start_research_task",
        {"kind": "workspace", "action": "read_file"},
    ),
}


def _adapter(challenge=CID):
    adapter = ADAPTERS[(challenge, 0)]
    return adapter() if isinstance(adapter, type) else adapter


def _attempt(n, tool, arguments, result=None):
    return analysis.Attempt(
        identity=f"epoch-1-tool-{n:03d}",
        epoch=1,
        stage=None,
        turn=n,
        position=0,
        tool="carbon_research_v2__" + tool,
        arguments=arguments,
        result=result,
        withheld=None,
        intent_digest="",
        result_digest=None,
    )


def _attempts(per_family):
    found, n = [], 0
    for family, count in per_family.items():
        tool, arguments = DOORS[family]
        for _ in range(count):
            n += 1
            found.append(_attempt(n, tool, arguments, {"status": "SUCCEEDED"}))
    return found


# -- the rule as recorded ----------------------------------------------------------------------
def test_the_rule_record_and_its_reminder_are_the_registered_v1():
    record = phase4.stop_rule_record()
    assert record["schema"] == phase4.STOP_RULE_V1
    assert record["k"] == phase4.STOP_RULE_K == 2
    assert record["finish_tool"] == phase4.FINISH_TOOL["name"]
    assert record["finish_money_floor_calls"] == FINISH_NOTICE_CALLS
    reminder = check_continue_reminder(record["continue_reminder"])
    assert reminder["max_consecutive"] == 2
    assert reminder["stop_code"] == STOPPED_NO_TOOL_USE
    assert record["family_labels"] == {
        k: v for k, v in LABELS.items() if k.startswith("rebuild")
    }


def test_the_provider_takes_only_the_registered_rule():
    with pytest.raises(ValueError):
        phase4.AttackerProvider(
            root=None,
            grant=None,
            model=None,
            pods=None,
            adapter=_adapter(),
            stop_rule="carbon.graphite.attacker-stop-rule.v0",
        )


# -- the coverage table --------------------------------------------------------------------------
@pytest.mark.parametrize("challenge", sorted({key[0] for key in ADAPTERS}))
def test_every_adapter_family_is_reachable_or_labelled(challenge):
    adapter = _adapter(challenge)
    table = phase4.stop_rule_coverage(adapter, TOOLS)
    named = {row["family"] for row in table["families"]}
    labelled = {row["family"]: row["label"] for row in table["unreachable"]}
    families = {analysis.family_name(f) for f in adapter.families()}
    assert named | set(labelled) == families and not named & set(labelled)
    assert all(label for label in labelled.values())
    assert all(row["doors"] for row in table["families"])
    assert table["b2_scope"] == phase4.B2_SCOPE_NOTE


def test_battery_level0_reaches_five_families_and_labels_the_four_others():
    table = phase4.stop_rule_coverage(_adapter(), TOOLS)
    assert [row["family"] for row in table["families"]] == REACHABLE
    assert {row["family"]: row["label"] for row in table["unreachable"]} == LABELS
    doors = {row["family"]: row["doors"] for row in table["families"]}
    assert "start_research_task[workspace/read_file]" in doors["staged_bytes"]


def test_counts_skip_the_loops_own_refusals_of_malformed_calls():
    found = _attempts({"recipe_surface": 1})
    malformed = {"status": "REJECTED_BEFORE_DISPATCH", "code": ARGUMENTS_INVALID}
    found.append(_attempt(99, "dry_validate", {}, malformed))
    # A refusal the research path itself made is an attempt like any other.
    path_refused = {"status": "REJECTED_BEFORE_DISPATCH", "code": "strategy.invalid"}
    found.append(_attempt(98, "dry_validate", {}, path_refused))
    table = phase4.stop_rule_coverage(_adapter(), TOOLS, found)
    row = next(r for r in table["families"] if r["family"] == "recipe_surface")
    assert row["attempts"] == 2 and row["covered"]


# -- the finish verdict ----------------------------------------------------------------------------
def _table(per_family):
    return phase4.stop_rule_coverage(_adapter(), TOOLS, _attempts(per_family))


def test_finish_is_refused_while_a_reachable_family_is_under_k():
    table = _table({**dict.fromkeys(REACHABLE, 2), "staged_bytes": 1})
    ok, refusal = phase4.finish_verdict(table, None)
    assert not ok
    assert refusal["status"] == "REJECTED_BEFORE_DISPATCH"
    assert refusal["code"] == phase4.FINISH_REFUSED
    assert "staged_bytes (1/2)" in refusal["reason"]
    assert refusal["coverage"] == table
    # Plenty of money left changes nothing.
    assert phase4.finish_verdict(table, 50)[0] is False


def test_finish_is_accepted_once_every_reachable_family_has_k():
    ok, refusal = phase4.finish_verdict(_table(dict.fromkeys(REACHABLE, 2)), None)
    assert ok and refusal is None


@pytest.mark.parametrize("sure", [0, 1, FINISH_NOTICE_CALLS])
def test_finish_is_accepted_when_money_can_be_sure_of_two_calls_or_fewer(sure):
    ok, _ = phase4.finish_verdict(_table({}), sure)
    assert ok
    assert phase4.finish_verdict(_table({}), FINISH_NOTICE_CALLS + 1)[0] is False


def test_sure_calls_follow_the_ledgers_money_and_call_ceilings():
    selection = types.SimpleNamespace(reservation_nano=10)
    status = {
        "budget": {"provider_nanodollars": 100, "provider_attempts": 7},
        "used": {"provider_nanodollars": 75, "provider_attempts": 1},
    }
    assert phase4.sure_model_calls(status, selection) == 2
    unbounded = {"budget": {}, "used": {}}
    assert phase4.sure_model_calls(unbounded, selection) is None


# -- the session record, the brief and the dry run ----------------------------------------------
def _dry_run(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network use in a run that must send nothing")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    out = io.StringIO()
    with redirect_stdout(out):
        code = phase4.main(
            ["run", "--root", str(tmp_path / "root"), "--challenge", CID, "--dry-run"]
        )
    assert code == 0
    runs = list((tmp_path / "root").rglob("session-open.json"))
    assert len(runs) == 1
    return runs[0].parent


def test_the_dry_run_freezes_the_rule_and_ends_typed(tmp_path, monkeypatch):
    run = _dry_run(tmp_path, monkeypatch)
    opened = json.loads((run / "session-open.json").read_bytes())
    assert opened["session_limits"]["stop_rule"] == phase4.stop_rule_record()
    offered = phase4.AttackerProvider.offered_tools(opened)
    assert offered[-1 - len(ENGINE_TOOLS_V2)] == phase4.FINISH_TOOL_NAME
    journal = [json.loads(path.read_bytes()) for path in sorted(run.rglob("*.json"))]
    refusals = [
        body
        for body in journal
        if isinstance(body, dict) and body.get("code") == phase4.FINISH_REFUSED
    ]
    assert refusals, "the scripted finish was not refused"
    reminders = sorted(run.rglob("*-continuation.json"))
    assert len(reminders) == 2
    plan = json.loads(next(run.rglob("plan.json")).read_bytes())
    assert plan["continue_reminder"] == phase4.CONTINUE_REMINDER
    assert any(STOPPED_NO_TOOL_USE in path.read_text() for path in run.rglob("*.json"))
    # The finish call is no attack attempt: Carbon's side never judges it.
    assert all(a.tool != phase4.FINISH_TOOL_NAME for a in phase4.attack_attempts(run))


def test_the_brief_carries_the_coverage_table_and_the_labels():
    observation = phase4.brief_observation(_adapter(), stop_rule=True)
    coverage = observation["stop_rule"]["coverage"]
    assert observation["stop_rule"]["finish_tool"] == phase4.FINISH_TOOL_NAME
    assert [row["family"] for row in coverage["families"]] == REACHABLE
    assert all(row["attempts"] == 0 for row in coverage["families"])
    assert {row["family"]: row["label"] for row in coverage["unreachable"]} == LABELS
    assert "stop_rule" not in phase4.brief_observation(_adapter())


def test_a_session_opened_without_the_rule_resumes_without_it():
    opened = {
        "role": {"tool_manifest": ["a", "b"]},
        "session_limits": {
            "schema": SESSION_LIMITS_V2,
            "engine_tools": list(ENGINE_TOOLS_V2),
        },
    }
    assert phase4.AttackerProvider.offered_tools(opened) == [
        "a",
        "b",
        *ENGINE_TOOLS_V2,
    ]
    ruled = {
        **opened,
        "session_limits": {
            **opened["session_limits"],
            "stop_rule": phase4.stop_rule_record(),
        },
    }
    assert phase4.AttackerProvider.offered_tools(ruled) == [
        "a",
        "b",
        phase4.FINISH_TOOL_NAME,
        *ENGINE_TOOLS_V2,
    ]


# -- each guard, disabled, turns its test red --------------------------------------------------
MUTATIONS = {
    "malformed_calls_counted": (
        "_counted",
        lambda attempt: True,
        test_counts_skip_the_loops_own_refusals_of_malformed_calls,
    ),
    "finish_always_accepted": (
        "finish_verdict",
        lambda table, sure: (True, None),
        test_finish_is_refused_while_a_reachable_family_is_under_k,
    ),
    "labels_dropped": (
        "FAMILY_LABELS",
        {},
        test_battery_level0_reaches_five_families_and_labels_the_four_others,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_a_guard_fails_its_test(name, monkeypatch):
    attribute, replacement, check = MUTATIONS[name]
    monkeypatch.setattr(phase4, attribute, replacement)
    with pytest.raises(AssertionError):
        check()
