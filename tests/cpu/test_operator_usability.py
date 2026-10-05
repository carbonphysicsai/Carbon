"""OPERATOR-USABILITY-01: what an operator or agent waits on is said, not guessed.

D1 - the owner report carries the campaign controller's own state and when
it settled. D2 - stopping and pausing are one shared operation at both doors.
D3 - a reconcile that cannot settle a pod yet says when it can. D4 - phase 4's
typed refusals end as phase 3's do, never as a traceback.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from test_launchpad_supervisor import (
    campaign_root,
    dispatches,
    journey,  # noqa: F401 - the fixture, read by name (getfixturevalue)
    launch,
)

from carbon.agent_campaign.controller import ControllerError
from carbon.agent_campaign.grant import GrantError
from carbon.agent_campaign.graphite import experiment as ex
from carbon.agent_campaign.graphite import phase3, phase4
from carbon.agent_campaign.graphite.pods import RunPodPods
from carbon.development_session.research_control import (
    CampaignControl,
    read_settlement,
)
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_report import render_status
from scripts.dev.miner_launchpad import supervisor as supervision
from scripts.dev.miner_launchpad.runner import RunnerAdapter


def _campaign(tmp_path, now):
    from test_cw1_research_ledger import ledger as make_ledger

    return make_ledger(tmp_path, clock=lambda: now[0])


# -- D1: the report says the campaign settled, and when ---------------------------
def test_a_settled_dispatch_writes_its_state_and_time_into_the_report(tmp_path):
    now = [1000]
    meter = _campaign(tmp_path, now)
    control = CampaignControl(meter)
    assert read_settlement(meter) == {
        "state": "QUEUED",
        "desired": "RUN",
        "generation": 0,
        "settled": False,
        "settled_unix": None,
    }
    generation = control.acquire()
    now[0] = 1100
    assert control.settled(generation, ready=True, cleanup_verified=True) == "READY"
    written = json.loads((tmp_path / "agent-report.json").read_bytes())
    assert written["control"] == {
        "state": "READY",
        "desired": "RUN",
        "generation": generation,
        "settled": True,
        "settled_unix": 1100,
    }
    # Waiting for its miner is settled, not a finished campaign.
    assert written["completed_unix"] is None
    page = (tmp_path / "research-report.html").read_text()
    assert "READY; nothing is running; settled at Unix UTC 1100" in page
    # A new dispatch runs again: no settlement time until it settles.
    control.acquire()
    assert read_settlement(meter)["settled"] is False
    assert read_settlement(meter)["settled_unix"] is None


def test_a_stop_settles_to_stopped_with_its_time(tmp_path):
    now = [2000]
    meter = _campaign(tmp_path, now)
    control = CampaignControl(meter)
    generation = control.acquire()
    control.request("stop")
    now[0] = 2050
    assert control.settled(generation, cleanup_verified=True) == "STOPPED"
    assert render_status(meter, owner="alice")["control"]["settled_unix"] == 2050
    # Stop again: answered as it is, nothing changes.
    control.request("stop")
    assert read_settlement(meter)["state"] == "STOPPED"
    assert read_settlement(meter)["settled_unix"] == 2050


def test_a_ledger_from_before_settlement_times_reads_none(tmp_path):
    meter = CampaignLedger(tmp_path, clock=lambda: 1000)
    assert read_settlement(meter) is None
    with meter.db() as db:
        db.execute(
            "CREATE TABLE launchpad_control (id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL, desired TEXT NOT NULL, observed TEXT NOT NULL)"
        )
        db.execute("INSERT INTO launchpad_control VALUES(1,3,'RUN','READY')")
    assert read_settlement(meter) == {
        "state": "READY",
        "desired": "RUN",
        "generation": 3,
        "settled": True,
        "settled_unix": None,
    }
    # Reading never adds the table.
    with meter.db() as db:
        assert not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='launchpad_settlement'"
        ).fetchone()


def test_a_settlement_with_no_frozen_campaign_writes_no_report(tmp_path):
    meter = CampaignLedger(tmp_path, clock=lambda: 1000)
    control = CampaignControl(meter)
    assert control.settled(control.acquire(), cleanup_verified=True) == "INTERRUPTED"
    assert not (tmp_path / "agent-report.json").exists()
    assert read_settlement(meter)["settled_unix"] == 1000


# -- D2: stop and pause are the shared halt operation ------------------------------
def test_stop_and_pause_are_named_by_the_shared_halt_operation():
    from carbon.miner_mcp.mcp_operations import operation_tool_names
    from scripts.dev.miner_launchpad.operations import CHOICES, OPERATIONS

    assert {"carbon_halt", "carbon_resume"} <= set(operation_tool_names())
    summary = OPERATIONS["halt"].summary
    for words in ("action=stop", "action=pause", "idempotent", "Nothing is deleted"):
        assert words in summary
    assert set(CHOICES["action"]) == {"stop", "pause", "reconcile"}
    # Withdrawing never needs registration, and only the owner's campaign.
    assert OPERATIONS["halt"].gates == ("request", "profile", "campaign")


# -- D3: a reconcile that cannot settle yet says when it can -----------------------
def test_recover_settles_reads_the_intents_age_and_the_grace():
    intent = SimpleNamespace(created_at=1_000_000.0)
    pods = SimpleNamespace(
        CAMPAIGN="graphite",
        store=SimpleNamespace(
            intent=lambda campaign, intent_id: intent if intent_id == "i-1" else None
        ),
        service=SimpleNamespace(not_found_grace_s=600.0),
        clock=lambda: 1_000_250.0,
    )
    assert RunPodPods.recover_settles(pods, "i-1") == {
        "intent_age_s": 250.0,
        "not_found_grace_s": 600.0,
        "settles_at_unix": 1_000_600.0,
    }
    assert RunPodPods.recover_settles(pods, "i-2") is None


def test_an_unknown_recover_row_carries_the_settle_hint():
    hint = {"intent_age_s": 1.0, "not_found_grace_s": 600.0, "settles_at_unix": 7.0}
    with_hint = SimpleNamespace(pods=SimpleNamespace(recover_settles=lambda i: hint))
    assert ex.Experiment._settles(with_hint, "i-1") == hint
    assert ex.Experiment._settles(SimpleNamespace(pods=object()), "i-1") == {}

    def broken(intent_id):
        raise RuntimeError("store unavailable")

    failing = SimpleNamespace(pods=SimpleNamespace(recover_settles=broken))
    assert ex.Experiment._settles(failing, "i-1") == {}


def test_reconcile_pending_names_the_age_and_the_minute_to_rerun():
    # 2026-10-05T14:00:30Z plus 600 s is 14:10:30; the re-run minute is 14:11.
    created = 1791208830.0
    report = {
        "graphite-a": [
            {"intent_id": "i-done", "terminated": True},
            {
                "intent_id": "i-uncertain",
                "terminated": None,
                "intent_age_s": 95.4,
                "not_found_grace_s": 600.0,
                "settles_at_unix": created + 600,
            },
        ],
        "graphite-b": [
            {"intent_id": "i-unverified", "terminated": False},
            {"intent_id": "i-nohint", "terminated": None},
        ],
    }
    value = phase3.reconcile_pending(report)
    assert value["status"] == "REFUSED"
    assert value["reason_code"] == "reconcile_pods_not_settled"
    assert value["rerun_at_utc"] == "2026-10-05T14:11Z"
    uncertain, unverified, nohint = value["unsettled"]
    assert uncertain == {
        "intent_id": "i-uncertain",
        "intent_age_s": 95,
        "not_found_grace_s": 600.0,
        "rerun_at_utc": "2026-10-05T14:11Z",
        "next_step": "settles after 600 s; re-run at or after 14:11 UTC",
    }
    assert unverified["next_step"] == "termination not verified; re-run reconcile now"
    assert "re-run reconcile" in nohint["next_step"]
    assert phase3.reconcile_pending({"graphite-a": []})["unsettled"] == []


# -- D4: phase 4's typed errors end as typed refusals -------------------------------
def _refused(capsys, monkeypatch, tmp_path, error):
    def raises(args):
        raise error

    monkeypatch.setattr(phase4, "command_status", raises)
    with pytest.raises(SystemExit) as stopped:
        phase4.main(["status", "--root", str(tmp_path)])
    assert stopped.value.code == 2
    line = capsys.readouterr().out.strip().splitlines()[-1]
    return json.loads(line)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ControllerError("controller_already_active", "a private detail"), None),
        (ex.BudgetRefused("run_cap_reached_tokens_plus_pods"), None),
        (GrantError("permitted_runs is a positive integer"), "grant_refused"),
    ],
)
def test_phase4_typed_errors_are_refusals_not_tracebacks(
    capsys, monkeypatch, tmp_path, error, code
):
    refusal = _refused(capsys, monkeypatch, tmp_path, error)
    assert refusal == {
        "status": "REFUSED",
        "reason_code": code or error.code,
    }


def test_phase4_knowledge_errors_keep_the_stores_prefix(capsys, monkeypatch, tmp_path):
    from carbon.agent_campaign.attack.knowledge import KnowledgeError

    refusal = _refused(
        capsys, monkeypatch, tmp_path, KnowledgeError("entry_unknown", "detail")
    )
    assert refusal == {
        "status": "REFUSED",
        "reason_code": "attack_knowledge_entry_unknown",
    }


# -- D5: a launch outlives the MCP client that received it --------------------------
# Session 1 (2026-10-03, main 6cffd988b) ran the launch on a daemon thread of
# the MCP process (`launch_admitted` -> `_start`), which died with it after
# creating the campaign's lock and ledger and before the freeze. Since
# LP-PROD-C a client only records and queues; these pin that against a client
# that dies without closing.
def _detached_runs_until_idle(launchpad):
    detached = launchpad.peer(supervision.DETACHED)
    detached.supervisor.poll, detached.supervisor.idle_exit = 0.02, 0.1
    assert detached.supervisor.run_until_idle() is True
    for thread in list(detached.threads.values()):
        thread.join(timeout=30)
        assert not thread.is_alive()
    return detached


def test_a_client_that_dies_right_after_launch_returns_loses_nothing(request):
    launchpad = request.getfixturevalue("journey")
    client = launchpad.peer(supervision.CLIENT)
    launched = launch(client)
    identity = launched["id"]
    root = campaign_root(client, identity)
    # Nothing of the launch runs in the client: no thread, no campaign lock
    # or ledger (session 1's directory held both), a queued item and a
    # detached supervisor started for it.
    assert client.threads == {}
    assert not (root / "campaign.sqlite3").exists()
    assert not (root / "owner.lock").exists()
    assert launched["state"] == "QUEUED"
    assert launched["in_flight"]["state"] == "QUEUED"
    assert launchpad.spawned == [1]
    # The client dies here: never closed, nothing more from it.
    detached = _detached_runs_until_idle(launchpad)
    view = detached.get(identity)
    assert view["state"] == "READY"
    assert view["last_refusal"] is None
    assert (root / "campaign-manifest.json").exists()
    assert [d["state"] for d in dispatches(detached)] == ["DONE"]


class _Died(BaseException):
    """The client process killed mid-call (SIGTERM): no cleanup runs."""


def test_a_client_killed_between_recording_and_queueing_is_recovered(
    request, monkeypatch
):
    launchpad = request.getfixturevalue("journey")
    client = launchpad.peer(supervision.CLIENT)

    def killed(*args, **kwargs):
        raise _Died

    monkeypatch.setattr(client, "_dispatch_run", killed)
    with pytest.raises(_Died):
        launch(client)
    with client.db() as db:
        (identity,) = db.execute("SELECT id FROM launchpad_campaigns").fetchone()
        assert tuple(
            db.execute("SELECT COUNT(*) FROM launchpad_dispatch").fetchone()
        ) == (0,)
    assert launchpad.spawned == []
    # The next client to start wakes a supervisor for the stranded launch,
    # which re-queues it from its record and carries it out.
    later = RunnerAdapter(
        launchpad.host.database, principal="alice", role=supervision.CLIENT
    )
    later.configured = launchpad.host.configured
    try:
        later.wake_if_stranded()
    finally:
        later.close()
    assert launchpad.spawned == [1]
    detached = _detached_runs_until_idle(launchpad)
    view = detached.get(identity)
    assert view["state"] == "READY"
    root = campaign_root(detached, identity)
    assert (root / "campaign-manifest.json").exists()


def test_phase4_other_errors_keep_their_traceback(monkeypatch, tmp_path):
    def raises(args):
        raise RuntimeError("a bug")

    monkeypatch.setattr(phase4, "command_status", raises)
    with pytest.raises(RuntimeError, match="a bug"):
        phase4.main(["status", "--root", str(tmp_path)])
