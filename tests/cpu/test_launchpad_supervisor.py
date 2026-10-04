"""One long-lived supervisor owns campaign threads; state stays truthful.

LP-PROD-C, found live on 2026-10-03: a launch from a short-lived MCP stdio
client ran on that client's own daemon thread, so when the client exited the
campaign was left QUEUED with no frozen manifest and could not be attached;
closing any client sent every live campaign an irreversible stop; every
restart flagged idle READY campaigns RECONCILIATION_REQUIRED; and a pause or
stop on an idle campaign was never settled.

Against the real campaign host (`journey_fixture`: RunnerAdapter, the
operations table and its gates, control settling, the ledger and the
projection), with only preparation and training as fixtures. Two hosts over
one database stand in for two processes: a CLIENT (an MCP door) and a
SUPERVISOR (the Control Center) or a DETACHED supervisor. One real detached
process is started at the end. No chain, provider, compute or network.
"""

import asyncio
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.development_session import research_campaign, research_control
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import CampaignLedger
from scripts.dev.miner_launchpad import supervisor as supervision
from scripts.dev.miner_launchpad.campaign_view import (
    controls,
    in_flight,
    last_refusal,
)
from scripts.dev.miner_launchpad.controller import Rejected, owner_lock
from scripts.dev.miner_launchpad.journey_fixture import (
    FIXTURE_CHALLENGE,
    journey_host,
)
from scripts.dev.miner_launchpad.operations import perform
from scripts.dev.miner_launchpad.runner import PATH_FIELDS, RunnerAdapter

REPOSITORY = Path(__file__).resolve().parents[2]
RECIPE = {
    "schema_version": "1.0",
    "challenge_id": "burgers-dynamics-v1",
    "backbone": "fno",
    "parameters": {"steps": 64},
}
RESUME = {"action": "resume", "operation": "resume"}
STOP = {"action": "stop", "operation": "halt"}
RECONCILE = {"action": "reconcile", "operation": "halt"}


@pytest.fixture
def journey(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    host = journey_host(tmp_path, patch=monkeypatch.setattr)
    spawned = []
    monkeypatch.setattr(
        RunnerAdapter, "spawn", staticmethod(lambda configuration: spawned.append(1))
    )
    reads = []

    def registration(cfg):
        reads.append(1)
        return host.registration(cfg)

    peers = []

    def peer(role):
        other = RunnerAdapter(
            host.database, principal="alice", registration=registration, role=role
        )
        other.configured = host.configured
        peers.append(other)
        return other

    yield SimpleNamespace(
        host=host, peer=peer, spawned=spawned, reads=reads, root=tmp_path
    )
    for other in peers:
        other.close()
    host.close()


def launch(host, key="launch-key-0000001", agent="none"):
    request = {
        "challenge": FIXTURE_CHALLENGE["id"],
        "challenge_version": FIXTURE_CHALLENGE["version"],
        "agent": agent,
        "idempotency_key": key,
    }
    if agent == "autonomous":
        return recorded_autonomous(host, request)
    return perform(host, "launch", request)


def recorded_autonomous(host, request):
    """A Carbon-agent campaign as such campaigns exist now: launched under
    `autonomous` before Graphite replaced it for new launches
    (OWNER-GRAPHITE-MINER-01), which refuses a new one. Its row is the one
    `launch_admitted` wrote then, and it is carried out from that record
    (`_recorded_launch`), as a queued launch is; its agent runs `run_agent`
    unchanged."""
    cfg = host.configured()
    run_id, request_digest, config_pin = host._launch_identity(cfg, request)
    root = Path(cfg["campaigns_root"]) / run_id
    with host.db() as db:
        db.execute(
            "INSERT INTO launchpad_campaigns (id,request_key,request_digest,profile,principal,config_digest,campaign,state,created,root,admission,budget,research_guidance,launch_request) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                request["idempotency_key"],
                request_digest,
                cfg["profile_id"],
                cfg["principal"],
                config_pin,
                "cmp-" + run_id,
                "QUEUED",
                time.time(),
                str(root),
                canonical(host.registration(cfg).record()),
                canonical({}),
                None,
                canonical({k: v for k, v in request.items() if k != "idempotency_key"}),
            ),
        )
    host._dispatch_run(run_id, cfg, root)
    return host.get(run_id)


def practice(identity, key):
    return {
        "campaign": identity,
        "strategy": RECIPE,
        "hypothesis": "width helps",
        "idempotency_key": key,
    }


def join(*hosts):
    for host in hosts:
        for thread in list(host.threads.values()):
            thread.join(timeout=30)
            assert not thread.is_alive()


def campaign_root(host, identity):
    return Path(host._bound(identity)[2])


def dispatches(host):
    with host.db() as db:
        return [
            dict(r) for r in db.execute("SELECT * FROM launchpad_dispatch ORDER BY seq")
        ]


# --- 1. one long-lived supervisor owns campaign threads ----------------------


def test_a_client_queues_a_launch_and_the_supervisor_carries_it_out(journey):
    """The live failure: the client that received the launch exits. The
    launch is queued, not run on the client's thread, so its exit loses
    nothing; the supervisor prepares it with the launch's own choices."""
    client = journey.peer(supervision.CLIENT)
    launched = launch(client)
    identity = launched["id"]
    assert client.threads == {}
    assert launched["state"] == "QUEUED"
    assert launched["in_flight"]["operation"] == "run"
    assert launched["in_flight"]["state"] == "QUEUED"
    assert launched["in_flight"]["supervisor_running"] is False
    # No supervisor was alive, so the client started one; it runs nothing.
    assert journey.spawned == [1]
    client.close()  # the stdio client exits

    supervisor = journey.peer(supervision.SUPERVISOR)
    assert supervisor.supervisor.tick()
    join(supervisor)
    view = supervisor.get(identity)
    assert view["state"] == "READY"
    assert view["in_flight"] is None and view["last_refusal"] is None
    assert view["recovery"] == []
    manifest = json.loads(
        (campaign_root(supervisor, identity) / "campaign-manifest.json").read_bytes()
    )
    assert manifest["agent"] == "none"
    assert manifest["challenge"] == FIXTURE_CHALLENGE
    # The admission was read again where the launch was carried out: the
    # client's RegisteredMiner lived in its own process (launch read + run).
    assert len(journey.reads) == 2
    assert [d["state"] for d in dispatches(supervisor)] == ["DONE"]


def test_a_clients_practice_is_carried_out_by_the_supervisor(journey):
    supervisor = journey.peer(supervision.SUPERVISOR)
    supervisor.supervisor.tick()
    identity = launch(supervisor)["id"]
    join(supervisor)
    client = journey.peer(supervision.CLIENT)
    first = perform(client, "practice", practice(identity, "practice-key-00001"))
    assert first["in_flight"]["operation"] == "practice"
    assert client.threads == {}
    # Queued work is the campaign's: another action waits its turn...
    with pytest.raises(Rejected, match="campaign_busy"):
        perform(client, "practice", practice(identity, "practice-key-00002"))
    # ...and a retry of the same one replays rather than queueing twice.
    again = perform(client, "practice", practice(identity, "practice-key-00001"))
    assert again["id"] == identity
    assert len([d for d in dispatches(client) if d["operation"] == "practice"]) == 1
    # The supervisor was alive (it holds the lock): nothing was spawned.
    assert journey.spawned == []
    supervisor.supervisor.tick()
    join(supervisor)
    view = client.get(identity)
    assert view["state"] == "READY" and view["in_flight"] is None
    assert view["completed_experiments"] == 1


# --- 2. closing pauses or detaches, never stops --------------------------------


def test_closing_the_supervisor_pauses_its_campaign_and_resume_continues_it(
    journey, monkeypatch
):
    supervisor = journey.peer(supervision.SUPERVISOR)
    supervisor.supervisor.tick()
    identity = launch(supervisor)["id"]
    join(supervisor)
    entered, gate = threading.Event(), threading.Event()

    async def slow_practice(prepared, **kwargs):
        entered.set()
        await asyncio.to_thread(gate.wait, 20)
        return {"status": "SUCCEEDED"}

    monkeypatch.setattr(research_campaign, "practice_recipe", slow_practice)
    perform(supervisor, "practice", practice(identity, "practice-key-00001"))
    assert entered.wait(20)
    client = journey.peer(supervision.CLIENT)
    # Work the Control Center runs is visible, as running, to every door.
    flight = client.get(identity)["in_flight"]
    assert (flight["operation"], flight["state"]) == ("practice", "RUNNING")
    assert flight["supervisor_running"] is True
    assert client.tools_busy_hint(identity) == "carbon_agent_or_operation"
    client.close()  # a client closing changes nothing
    assert CampaignControl(CampaignLedger(campaign_root(client, identity))).status()[
        "desired"
    ] == ("RUN")

    threading.Timer(0.3, gate.set).start()
    supervisor.close()  # the Control Center closes mid-practice
    view = journey.host.get(identity)
    # Paused, never stopped (before 2026-10-03: STOPPED, irreversibly).
    assert view["state"] == "PAUSED"
    assert view["last_refusal"]["code"] == "paused_when_supervisor_closed"
    assert view["last_refusal"]["kind"] == "paused"
    assert view["recovery"] == [RESUME, STOP]
    resumed = journey.host.control(identity, "resume")
    assert resumed["last_refusal"] is None
    join(journey.host)
    assert journey.host.get(identity)["state"] == "READY"


# --- 3. startup recovery -------------------------------------------------------


def test_a_restart_leaves_an_idle_ready_campaign_ready(journey):
    """Before 2026-10-03 every start settled it with cleanup assumed failed:
    RECONCILIATION_REQUIRED for a campaign nothing was doing."""
    identity = launch(journey.host)["id"]
    join(journey.host)
    restarted = RunnerAdapter(journey.host.database, principal="alice")
    assert restarted.get(identity)["state"] == "READY"
    supervisor = journey.peer(supervision.SUPERVISOR)
    assert supervisor.supervisor.tick()
    view = supervisor.get(identity)
    assert view["state"] == "READY" and view["last_refusal"] is None


def test_a_dead_supervisors_work_is_settled_truthfully_and_never_replayed(journey):
    identity = launch(journey.host)["id"]
    join(journey.host)
    root = campaign_root(journey.host, identity)
    # A supervisor died mid-practice with nothing reserved: its generation is
    # still in flight and its queue item still says RUNNING.
    CampaignControl(CampaignLedger(root)).acquire()
    with journey.host.db() as db:
        supervision.enqueue(
            db,
            principal="alice",
            campaign=identity,
            operation="practice",
            params={},
            config_digest="sha256:dead",
            state=supervision.RUNNING,
            supervisor="sup-dead-process",
        )
    supervisor = journey.peer(supervision.SUPERVISOR)
    assert supervisor.supervisor.tick()
    join(supervisor)
    view = supervisor.get(identity)
    # Nothing outstanding and nobody selects but the miner: READY again,
    # told why the practice did not finish.
    assert view["state"] == "READY"
    assert view["last_refusal"]["code"] == "operation_interrupted"
    assert view["last_refusal"]["operation"] == "practice"
    assert view["in_flight"] is None and view["completed_experiments"] == 0
    (orphan,) = [d for d in dispatches(supervisor) if d["operation"] == "practice"]
    assert (orphan["state"], orphan["outcome"]) == ("DONE", "interrupted")


def test_recovery_leaves_a_campaign_to_the_work_queued_for_it(journey):
    """A resume queued by a client leaves the ledger RESUME_REQUESTED. A
    supervisor taking the lock does not settle that as interrupted first: the
    queued run settles it, and no stale refusal outlives it."""
    host = journey.host
    identity = launch(host)["id"]
    join(host)
    host.control(identity, "pause")
    client = journey.peer(supervision.CLIENT)
    client.control(identity, "resume")
    assert CampaignControl(CampaignLedger(campaign_root(host, identity))).status()[
        "state"
    ] == ("RESUME_REQUESTED")
    supervisor = journey.peer(supervision.SUPERVISOR)
    supervisor.supervisor.tick()
    join(supervisor)
    view = supervisor.get(identity)
    assert view["state"] == "READY" and view["last_refusal"] is None


def test_an_operation_never_starts_over_unresolved_work(journey):
    """As a run already refused to: a practice after a crash that left an
    operation RESERVED is refused and goes to reconciliation, unsent."""
    host = journey.host
    identity = launch(host)["id"]
    join(host)
    ledger = CampaignLedger(campaign_root(host, identity))
    ledger.generation = CampaignControl(ledger).acquire()
    ledger.reserve(
        "crashed-operation",
        owner="miner-requester",
        phase="research",
        request={"fixture": 1},
        resources={"research_trials": 1},
    )
    perform(host, "practice", practice(identity, "practice-key-00001"))
    join(host)
    view = host.get(identity)
    assert view["last_refusal"]["code"] == "unresolved_operation"
    assert view["state"] == "RECONCILIATION_REQUIRED"
    assert view["completed_experiments"] == 0
    assert view["recovery"] == [RECONCILE, STOP]


def test_a_restart_settles_a_dead_run_with_the_real_cleanup_check(journey):
    """In flight with nothing outstanding is INTERRUPTED, not reconciliation;
    the existing test keeps reserved work going to reconciliation."""
    client = journey.peer(supervision.CLIENT)
    identity = launch(client)["id"]
    root = campaign_root(client, identity)
    with client.db() as db:
        db.execute("UPDATE launchpad_dispatch SET state='DONE'")
        # Already refused, so recovery leaves it for the miner to resume.
        db.execute(
            "UPDATE launchpad_campaigns SET last_refusal=?",
            (canonical(supervision.refusal("registration_unreadable")),),
        )
    ledger = CampaignLedger(root)
    CampaignControl(ledger).acquire()  # a run that died while preparing
    supervisor = journey.peer(supervision.SUPERVISOR)
    supervisor.supervisor.tick()
    view = supervisor.get(identity)
    assert view["state"] == "INTERRUPTED"
    # Resume is the way forward; Reconcile is offered too (review repair).
    assert view["recovery"] == [RESUME, RECONCILE, STOP]
    assert not (root / "campaign-manifest.json").exists()
    # Reconcile checks again what is held and settles the campaign as it
    # stands: nothing was outstanding, so it stays INTERRUPTED, and nothing
    # is dispatched or prepared.
    before = dispatches(supervisor)
    assert supervisor.control(identity, "reconcile")["state"] == "INTERRUPTED"
    assert dispatches(supervisor) == before
    assert not (root / "campaign-manifest.json").exists()


def test_an_admitted_launch_nothing_carried_out_is_redispatched_with_its_choices(
    journey,
):
    client = journey.peer(supervision.CLIENT)
    identity = launch(client)["id"]
    # What happened live: the process holding the launch died, so nothing
    # carries it out.
    with client.db() as db:
        db.execute("UPDATE launchpad_dispatch SET state='DONE', outcome='lost'")
    stranded = client.get(identity)
    assert stranded["state"] == "QUEUED" and stranded["in_flight"] is None
    assert stranded["recovery"] == [RESUME, STOP]
    supervisor = journey.peer(supervision.SUPERVISOR)
    supervisor.supervisor.tick()
    join(supervisor)
    view = supervisor.get(identity)
    assert view["state"] == "READY"
    manifest = json.loads(
        (campaign_root(supervisor, identity) / "campaign-manifest.json").read_bytes()
    )
    assert (manifest["agent"], manifest["challenge"]) == ("none", FIXTURE_CHALLENGE)


def test_an_orphaned_launch_never_prepared_is_carried_out_again_once(journey):
    """Review finding: the supervisor that claimed the launch died while
    preparing it. Recovery re-queued it from a row read before it recorded the
    interruption, so the campaign ran to READY still reading
    `campaign_interrupted` ("Resume it"). It is carried out again - nothing
    could have been dispatched before its manifest - and the interruption is
    history once it is."""
    client = journey.peer(supervision.CLIENT)
    identity = launch(client)["id"]
    root = campaign_root(client, identity)
    with client.db() as db:
        db.execute(
            "UPDATE launchpad_dispatch SET state='RUNNING', supervisor='sup-dead', claimed=1"
        )
    CampaignControl(CampaignLedger(root)).acquire()  # died while preparing
    supervisor = journey.peer(supervision.SUPERVISOR)
    assert supervisor.supervisor.tick()
    queued = supervisor.get(identity)
    assert queued["last_refusal"] is None  # being carried out, not interrupted
    join(supervisor)
    supervisor.supervisor.tick()
    join(supervisor)
    view = supervisor.get(identity)
    assert view["state"] == "READY" and view["last_refusal"] is None
    assert (root / "campaign-manifest.json").exists()
    assert [(d["operation"], d["outcome"]) for d in dispatches(supervisor)] == [
        ("run", "interrupted"),
        ("run", "finished"),
    ]


def test_a_launch_interrupted_again_waits_for_its_miner(journey):
    """Carried out again once, it died again: preparation itself may be what
    ends the process, so recovery does not try a third time on its own. It
    keeps its interruption, and Resume carries it out."""
    client = journey.peer(supervision.CLIENT)
    identity = launch(client)["id"]
    root = campaign_root(client, identity)
    with client.db() as db:
        db.execute(
            "UPDATE launchpad_dispatch SET state='DONE', outcome='interrupted', supervisor='sup-dead-1'"
        )
        supervision.enqueue(
            db,
            principal="alice",
            campaign=identity,
            operation="run",
            params={},
            config_digest="sha256:again",
            state=supervision.RUNNING,
            supervisor="sup-dead-2",
        )
    CampaignControl(CampaignLedger(root)).acquire()
    supervisor = journey.peer(supervision.SUPERVISOR)
    assert supervisor.supervisor.tick()
    join(supervisor)
    view = supervisor.get(identity)
    assert view["state"] == "INTERRUPTED"
    assert view["last_refusal"]["code"] == "campaign_interrupted"
    assert view["recovery"] == [RESUME, RECONCILE, STOP]
    assert [d["outcome"] for d in dispatches(supervisor)] == [
        "interrupted",
        "interrupted",
    ]
    assert not (root / "campaign-manifest.json").exists()
    supervisor.control(identity, "resume")
    join(supervisor)
    assert supervisor.get(identity)["state"] == "READY"


def test_a_run_settled_paused_keeps_why_it_was_paused(journey):
    """A run left mid-flight with a pause asked - its Control Center closed,
    or a handover - settles PAUSED and keeps that reason, rather than being
    retold it was interrupted."""
    host = journey.host
    identity = launch(host)["id"]
    join(host)
    control = CampaignControl(CampaignLedger(campaign_root(host, identity)))
    control.acquire()
    control.request("pause")
    host._refused(identity, "paused_when_supervisor_closed", None, kind="paused")
    with host.db() as db:
        supervision.enqueue(
            db,
            principal="alice",
            campaign=identity,
            operation="run",
            params={},
            config_digest="sha256:closed",
            state=supervision.RUNNING,
            supervisor="sup-closed",
        )
    supervisor = journey.peer(supervision.SUPERVISOR)
    assert supervisor.supervisor.tick()
    view = supervisor.get(identity)
    assert view["state"] == "PAUSED"
    assert view["last_refusal"]["code"] == "paused_when_supervisor_closed"


def test_an_operation_left_waiting_at_a_pause_is_reported(journey):
    """A practice that reached the campaign's pause before it dispatched
    anything, in a process that then exited: it never ran. The campaign
    stays PAUSED and says the practice did not finish, so it is sent again
    rather than silently lost."""
    host = journey.host
    identity = launch(host)["id"]
    join(host)
    assert host.control(identity, "pause")["state"] == "PAUSED"
    with host.db() as db:
        supervision.enqueue(
            db,
            principal="alice",
            campaign=identity,
            operation="practice",
            params={},
            config_digest="sha256:parked",
            state=supervision.RUNNING,
            supervisor="sup-exited",
        )
    supervisor = journey.peer(supervision.SUPERVISOR)
    assert supervisor.supervisor.tick()
    view = supervisor.get(identity)
    assert view["state"] == "PAUSED"
    refused = view["last_refusal"]
    assert (refused["code"], refused["operation"]) == (
        "operation_interrupted",
        "practice",
    )


def test_a_launch_without_its_recorded_choices_never_falls_to_another_path(journey):
    """Before 2026-10-03 resuming an unprepared launch ran with no product,
    which is the retired grant path. Now it is refused by name."""
    client = journey.peer(supervision.CLIENT)
    identity = launch(client)["id"]
    with client.db() as db:
        db.execute("UPDATE launchpad_dispatch SET state='DONE'")
        db.execute("UPDATE launchpad_campaigns SET launch_request=NULL")
    supervisor = journey.peer(supervision.SUPERVISOR)
    supervisor.supervisor.tick()
    assert [d["operation"] for d in dispatches(supervisor)] == ["run"]  # no re-run
    client.control(identity, "resume")
    supervisor.supervisor.tick()
    join(supervisor)
    view = supervisor.get(identity)
    assert view["last_refusal"]["code"] == "launch_choices_unrecorded"
    assert view["last_refusal"]["next_action"].startswith("This launch was recorded")
    assert view["state"] == "INTERRUPTED"
    assert not (campaign_root(supervisor, identity) / "campaign-manifest.json").exists()


def test_a_supervisor_refuses_work_admitted_under_another_profile(journey):
    client = journey.peer(supervision.CLIENT)
    identity = launch(client)["id"]
    supervisor = journey.peer(supervision.SUPERVISOR)
    changed = {**journey.host.configured(), "profile_id": "another-profile"}
    supervisor.configured = lambda: changed
    supervisor.supervisor.tick()
    join(supervisor)
    view = client.get(identity)
    assert view["last_refusal"]["code"] == "profile_differs_from_request"
    assert view["state"] == "QUEUED" and view["in_flight"] is None
    assert dispatches(client)[-1]["outcome"] == "refused"


# --- 4. pause or stop on an idle campaign settles at once ----------------------


def test_pause_and_stop_on_an_idle_campaign_settle_at_once(journey):
    host = journey.host
    identity = launch(host)["id"]
    join(host)
    assert host.control(identity, "pause")["state"] == "PAUSED"
    # A paused campaign takes no new work; resume first.
    with pytest.raises(Rejected, match="campaign_paused"):
        perform(host, "practice", practice(identity, "practice-key-00001"))
    host.control(identity, "resume")
    join(host)
    assert host.get(identity)["state"] == "READY"
    assert host.control(identity, "stop")["state"] == "STOPPED"
    with pytest.raises(Rejected, match="campaign_stopped"):
        perform(host, "practice", practice(identity, "practice-key-00002"))


def test_a_held_campaign_keeps_the_request_and_resume_stays_available(journey):
    host = journey.host
    identity = launch(host)["id"]
    join(host)
    root = campaign_root(host, identity)
    with owner_lock(root):  # an attached agent holds it
        view = host.control(identity, "pause")
        assert view["state"] == "PAUSE_REQUESTED"
        resume = {c["action"]: c for c in controls(view, fixture=False)}["resume"]
        assert resume["available"] is True  # disabled before 2026-10-03
        assert view["recovery"] == [RESUME, RECONCILE, STOP]
    # The holder went away without settling it: resume cancels the pause.
    host.control(identity, "resume")
    join(host)
    assert host.get(identity)["state"] == "READY"


def test_reconcile_settles_a_pause_its_holder_left_unsettled(journey):
    """Review repair: Reconcile is offered for PAUSE_REQUESTED. While the
    holder lives it is refused `campaign_busy` and changes nothing; once the
    holder has gone without settling the pause (its process died, and no
    supervisor has recovered it yet), Reconcile settles it PAUSED - the pause
    the miner asked for, not a resume - and nothing is dispatched."""
    host = journey.host
    identity = launch(host)["id"]
    join(host)
    root = campaign_root(host, identity)
    with owner_lock(root):  # an attached agent holds it
        assert host.control(identity, "pause")["state"] == "PAUSE_REQUESTED"
        with pytest.raises(Rejected, match="campaign_busy"):
            host.control(identity, "reconcile")
        assert host.get(identity)["state"] == "PAUSE_REQUESTED"
    view = host.get(identity)
    assert view["state"] == "PAUSE_REQUESTED"
    assert RECONCILE in view["recovery"]
    before = dispatches(host)
    settled = host.control(identity, "reconcile")
    assert settled["state"] == "PAUSED"
    assert settled["recovery"] == [RESUME, STOP]
    assert dispatches(host) == before


def test_reconcile_on_a_held_campaign_is_refused_by_name(journey):
    host = journey.host
    identity = launch(host)["id"]
    join(host)
    with (
        owner_lock(campaign_root(host, identity)),
        pytest.raises(Rejected, match="campaign_busy"),
    ):
        host.control(identity, "reconcile")
    # Nothing outstanding and the miner selects: reconciled, it waits for
    # them (READY), rather than reading as interrupted.
    assert host.control(identity, "reconcile")["state"] == "READY"


# --- last_refusal: what no caller saw, with its next action --------------------


def test_a_refusal_on_a_thread_is_kept_with_its_next_action(journey, monkeypatch):
    """The miner's signer stopped after the practice was admitted: nothing
    was signed, so it is a refusal, kept for the miner with its next step.
    (Until LP-PROD-C part 2 this test held the campaign's lock; a held lock is
    now refused before the thread starts - see the busy test below.)"""
    from carbon.chain.external_signer import SignerCode, SignerFailure

    host = journey.host
    identity = launch(host)["id"]
    join(host)

    async def signer_stopped(prepared, **kwargs):
        raise SignerFailure(SignerCode.NOT_RUNNING)

    with monkeypatch.context() as patch:
        patch.setattr(research_campaign, "practice_recipe", signer_stopped)
        perform(host, "practice", practice(identity, "practice-key-00001"))
        join(host)
    view = host.get(identity)
    refused = view["last_refusal"]
    assert refused["code"] == "signer_not_running"
    assert refused["operation"] == "practice" and refused["kind"] == "refused"
    assert refused["next_action"] == supervision.NEXT_ACTIONS["signer_not_running"]
    assert view["state"] == "READY"  # a refusal changes nothing
    document = perform(host, "campaign_view", {"campaign": identity})
    assert document["last_refusal"]["code"] == "signer_not_running"
    assert document["recovery"] == [] and document["in_flight"] is None
    # A new attempt is admitted: the earlier refusal is history.
    perform(host, "practice", practice(identity, "practice-key-00002"))
    join(host)
    view = host.get(identity)
    assert view["last_refusal"] is None and view["completed_experiments"] == 1


def test_a_code_from_another_slice_reaches_the_miner_with_a_generic_step(
    journey, monkeypatch
):
    host = journey.host
    identity = launch(host)["id"]
    join(host)

    async def refused(prepared, **kwargs):
        raise research_campaign.OperationRefused("intake_refused_new_code")

    monkeypatch.setattr(research_campaign, "practice_recipe", refused)
    perform(host, "practice", practice(identity, "practice-key-00001"))
    join(host)
    entry = host.get(identity)["last_refusal"]
    assert entry["code"] == "intake_refused_new_code"
    assert entry["next_action"] == supervision.FALLBACK_ACTION
    # A code that is not a closed identifier is never echoed.
    assert supervision.refusal("Provider said: SECRET")["code"] == "operation_refused"


def test_an_agents_unevaluated_candidate_is_reported_with_its_code(
    journey, monkeypatch
):
    host = journey.host
    identity = launch(host)["id"]
    join(host)

    async def execute(args, *, ledger):
        return "evaluation_queued"

    monkeypatch.setattr(research_campaign, "execute", execute)
    host._run(identity, host.configured(), campaign_root(host, identity), None)
    entry = host.get(identity)["last_refusal"]
    assert (entry["code"], entry["operation"]) == ("evaluation_queued", "submit")
    assert entry["next_action"] == supervision.NEXT_ACTIONS["evaluation_queued"]


def retained_by_its_agent(journey, monkeypatch, key="launch-key-0000001", fail=None):
    """A Carbon-agent campaign whose agent selected a candidate the validator
    did not evaluate. DEVELOPMENT FIXTURE: `run_agent` freezes the candidate
    where the agent's SELECT writes it (`epoch-1/selected-recipe.json`) and
    returns what `submit_or_retain` returns then - the refusal's closed code,
    `evaluation_unavailable` - or, with `fail`, raises it after the freeze."""

    from carbon.development_session.research_loop import candidate_record

    async def run_agent(prepared, **_):
        folder = prepared.ledger.root / "epoch-1"
        folder.mkdir(mode=0o700, exist_ok=True)
        (folder / "selected-recipe.json").write_bytes(
            canonical(candidate_record(RECIPE, "practised", False))
        )
        if fail is not None:
            raise fail
        return "evaluation_unavailable"

    monkeypatch.setattr(research_campaign, "run_agent", run_agent)
    identity = launch(journey.host, key=key, agent="autonomous")["id"]
    join(journey.host)
    return identity


def test_a_retained_candidate_waits_ready_through_tools_and_restarts(
    journey, monkeypatch
):
    """LP-PROD-FIX-01, smoke run 382c4276: a submit refused
    `evaluation_unavailable` keeps the agent's candidate, and its campaign
    waits for its miner. Until 2026-10-04 it settled INTERRUPTED with no
    interruption recorded; the Tools tab then left it RECONCILING, and a
    restart settled it INTERRUPTED again with `campaign_interrupted` over
    the refusal."""
    host = journey.host
    identity = retained_by_its_agent(journey, monkeypatch)
    root = campaign_root(host, identity)

    def kept(view):
        refusal = view["last_refusal"]
        assert view["state"] == "READY", (view["state"], refusal)
        assert (refusal["code"], refusal["operation"]) == (
            "evaluation_unavailable",
            "submit",
        )
        assert refusal["next_action"] == supervision.NEXT_ACTIONS[
            "evaluation_unavailable"
        ]
        assert (root / "epoch-1" / "selected-recipe.json").exists()
        assert not (root / "epoch-1" / "permitted-final-feedback.json").exists()
        assert not (root / "interruptions.jsonl").exists()

    kept(host.get(identity))
    assert host.get(identity)["journey"]["frozen_awaiting_submission"] is True
    assert CampaignControl(CampaignLedger(root)).status()["state"] == "READY"
    # The Tools tab (or an attached agent) holds it, and its process dies
    # before settling: a restart finds it RECONCILING and settles it READY.
    CampaignControl(CampaignLedger(root)).acquire()
    restarted = RunnerAdapter(host.database, principal="alice")
    try:
        kept(restarted.get(identity))
    finally:
        restarted.close()
    # A supervisor taking the lock does the same.
    CampaignControl(CampaignLedger(root)).acquire()
    supervisor = journey.peer(supervision.SUPERVISOR)
    assert supervisor.supervisor.tick()
    join(supervisor)
    kept(supervisor.get(identity))
    # An idle settle (the miner's Reconcile) leaves it READY too.
    kept(host.control(identity, "reconcile"))


def test_a_run_that_raised_after_its_agent_selected_stays_interrupted(
    journey, monkeypatch
):
    """Only a refusal that kept the candidate waits READY: a run that raised
    after the selection keeps its interruption, recorded, as before."""
    identity = retained_by_its_agent(
        journey, monkeypatch, fail=RuntimeError("not a refusal")
    )
    root = campaign_root(journey.host, identity)
    view = journey.host.get(identity)
    assert view["state"] == "INTERRUPTED"
    assert view["last_refusal"]["code"] == "campaign_interrupted"
    assert CampaignControl(CampaignLedger(root)).status()["state"] == "INTERRUPTED"
    assert (root / "interruptions.jsonl").read_text().count("\n") == 1


def test_waits_for_its_miner_reads_the_campaigns_own_files(tmp_path):
    from carbon.development_session.research_campaign import waits_for_its_miner
    from carbon.miner_mcp.standard_cli import _waits_for_its_miner

    root = tmp_path / "campaign"
    root.mkdir()
    assert not waits_for_its_miner(root)  # not prepared: no frozen manifest

    def frozen(agent):
        manifest = {} if agent is None else {"agent": agent}
        (root / "campaign-manifest.json").write_bytes(canonical(manifest))
        return manifest

    def write(epoch, name):
        folder = root / ("epoch-" + str(epoch))
        folder.mkdir(exist_ok=True)
        (folder / name).write_text("{}")

    frozen("none")
    assert waits_for_its_miner(root)
    for agent in ("autonomous", "graphite", None):  # None: the historical default
        frozen(agent)
        assert not waits_for_its_miner(root)
    write(1, "selected-recipe.json")
    assert waits_for_its_miner(root)  # retained, epoch 1 unevaluated
    write(1, "permitted-final-feedback.json")
    assert not waits_for_its_miner(root)  # epoch 1 evaluated, nothing frozen in 2
    write(2, "selected-recipe.json")
    assert waits_for_its_miner(root)
    write(2, "permitted-final-feedback.json")
    assert not waits_for_its_miner(root)  # both final exams used
    (root / "epoch-2" / "permitted-final-feedback.json").unlink()
    (root / "campaign-complete.json").write_text("{}")
    assert not waits_for_its_miner(root)
    (root / "campaign-complete.json").unlink()
    # A detach asks the same, with the profile's manifest.
    profile = SimpleNamespace(
        cleanup_only=False, manifest=frozen("graphite"), root=root
    )
    run = SimpleNamespace(status=lambda: {"desired": "RUN"})
    pause = SimpleNamespace(status=lambda: {"desired": "PAUSE"})
    assert _waits_for_its_miner(profile, run)
    assert not _waits_for_its_miner(profile, pause)
    assert not _waits_for_its_miner(
        SimpleNamespace(cleanup_only=True, manifest=profile.manifest, root=root), run
    )


def test_execute_returns_what_the_agent_returns(monkeypatch, tmp_path):
    closed = []

    async def prepare(args, *, ledger=None):
        return SimpleNamespace(agent=args.agent, close=lambda: closed.append(1))

    async def run_agent(prepared):
        return "intake_unreachable"

    monkeypatch.setattr(research_campaign, "prepare", prepare)
    monkeypatch.setattr(research_campaign, "run_agent", run_agent)
    autonomous = SimpleNamespace(agent="autonomous")
    assert asyncio.run(research_campaign.execute(autonomous)) == "intake_unreachable"
    assert asyncio.run(research_campaign.execute(SimpleNamespace(agent="none"))) is None
    assert closed == [1, 1]


def test_a_credential_refusal_settles_rather_than_leaving_the_run_in_flight(
    tmp_path, monkeypatch
):
    """`_operate` acquired a generation and then refused the key file, leaving
    the campaign RECONCILING with nothing running."""
    monkeypatch.setattr(RunnerAdapter, "_cleanup", staticmethod(lambda _: True))
    host = RunnerAdapter(tmp_path / "runner.sqlite3", registration=lambda _: None)
    root = tmp_path / "campaign"
    root.mkdir(mode=0o700)
    admitted = SimpleNamespace(
        campaign={"id": "cmp-fixture", "root": str(root), "research_guidance": None},
        profile={
            "paths": {"api_key_file": "/keys/other.key"},
            "provider_credentials": {"anthropic-messages": "/keys/other.key"},
            "accepted_revision": "a" * 40,
            "principal": "alice",
        },
    )
    with pytest.raises(Rejected, match="model_provider_credential_not_configured"):
        host._operate(admitted, lambda prepared: None)
    assert CampaignControl(CampaignLedger(root)).status()["state"] == "READY"


# --- the supervisor lock and the detached process ------------------------------


def test_one_supervisor_holds_the_lock_and_a_detached_one_retires_when_idle(journey):
    """(Until the handover this test used a Control Center as the second
    supervisor and let the detached one carry out its launch; a running
    Control Center is now handed the work instead - see the handover tests
    below - so the second supervisor here is another detached one.)"""
    detached = journey.peer(supervision.DETACHED)
    detached.supervisor.poll, detached.supervisor.idle_exit = 0.05, 0.2
    other = journey.peer(supervision.DETACHED)
    directory = supervision.lock_directory(journey.host.database, "alice")
    assert detached.supervisor.tick()
    assert not other.supervisor.tick()  # one holder at a time
    assert supervision.supervisor_alive(directory)
    client = journey.peer(supervision.CLIENT)
    identity = launch(client)["id"]
    assert client.threads == {}
    assert detached.supervisor.run_until_idle() is True
    join(detached)
    assert not detached.supervisor.held
    assert not supervision.supervisor_alive(directory)
    assert client.get(identity)["state"] == "READY"
    assert other.supervisor.tick()  # the next supervisor takes over


# --- the handover: a Control Center started after a detached supervisor -------


def practices_of(host, identity):
    return [
        (d["state"], d["outcome"])
        for d in dispatches(host)
        if d["campaign"] == identity and d["operation"] == "practice"
    ]


def slow_practice_fixture(monkeypatch):
    """A practice that runs until its gate opens; entered once it started."""
    entered, gate = threading.Event(), threading.Event()

    async def slow_practice(prepared, **kwargs):
        entered.set()
        await asyncio.to_thread(gate.wait, 20)
        return {"status": "SUCCEEDED"}

    monkeypatch.setattr(research_campaign, "practice_recipe", slow_practice)
    return entered, gate


def test_a_control_center_takes_over_from_a_detached_supervisor(journey, monkeypatch):
    """The review's case: a Control Center started while a detached
    supervisor held the lock stayed a client for as long as that process
    lived - its own launch ran there, and closing it paused nothing. Now the
    detached supervisor starts nothing more, lets the miner's practice finish
    (it is never cut off), and hands the lock over; the Control Center then
    carries out what it queued."""
    detached = journey.peer(supervision.DETACHED)
    assert detached.supervisor.tick()
    identity = launch(detached)["id"]
    join(detached)
    entered, gate = slow_practice_fixture(monkeypatch)
    perform(detached, "practice", practice(identity, "practice-key-00001"))
    assert entered.wait(20)
    control_center = journey.peer(supervision.SUPERVISOR)
    assert not control_center.supervisor.tick()  # present; the lock is held
    second = launch(control_center, key="launch-key-0000002")["id"]
    assert control_center.threads == {}
    assert not detached.supervisor.tick()  # handing over: claims nothing
    assert detached.supervisor.held and detached.supervisor.handing_over
    assert [d["state"] for d in dispatches(detached) if d["campaign"] == second] == [
        "QUEUED"
    ]
    gate.set()
    join(detached)
    assert not detached.supervisor.tick()  # nothing of its own working: released
    assert detached.supervisor.handed_over and not detached.supervisor.held
    assert control_center.supervisor.tick()
    join(control_center)
    assert control_center.get(second)["state"] == "READY"
    assert control_center.get(identity)["state"] == "READY"
    assert practices_of(control_center, identity) == [("DONE", "finished")]
    assert list(control_center.threads) == [second]  # carried out here


class ProcessGone(Exception):
    """Stands in, in one test process, for the detached process exiting."""


def test_a_detached_supervisor_hands_carbons_agent_over_to_the_control_center(
    journey, monkeypatch
):
    """Carbon's agent pauses at its next checkpoint - between bounded
    operations, never mid-call - and the detached supervisor releases the
    lock once its run is parked there: a parked run holds nothing a process
    must keep, so it is not waited for, and it no longer keeps a detached
    supervisor alive while its campaign stays paused. The Control Center
    resumes it only once that run's process is gone: resuming earlier would
    wake the run in a process about to exit."""
    entered, gone = threading.Event(), threading.Event()
    calls = []

    async def run_agent(prepared):
        control = CampaignControl(prepared.ledger)
        calls.append(1)
        entered.set()
        try:
            while not gone.is_set():
                # The agent's real checkpoint: parks while the campaign is
                # paused.
                control.checkpoint(prepared.ledger.generation)
                await asyncio.sleep(0.02)
        except ProcessGone:
            return

    real_sleep = time.sleep

    def parked_sleep(seconds):
        if gone.is_set():
            raise ProcessGone
        real_sleep(seconds)

    monkeypatch.setattr(research_campaign, "run_agent", run_agent)
    monkeypatch.setattr(research_control, "time", SimpleNamespace(sleep=parked_sleep))
    detached = journey.peer(supervision.DETACHED)
    assert detached.supervisor.tick()
    identity = launch(detached, agent="autonomous")["id"]
    assert entered.wait(20)
    assert detached.busy_threads() == [identity]
    control_center = journey.peer(supervision.SUPERVISOR)
    assert not control_center.supervisor.tick()
    deadline = time.monotonic() + 20
    while not detached.supervisor.handed_over and time.monotonic() < deadline:
        detached.supervisor.tick()
        real_sleep(0.05)
    assert detached.supervisor.handed_over and not detached.supervisor.held
    root = campaign_root(detached, identity)

    def status():
        value = CampaignControl(CampaignLedger(root)).status()
        return value["desired"], value["state"]

    assert status() == ("PAUSE", "PAUSED")
    refused = detached.get(identity)["last_refusal"]
    assert (refused["code"], refused["kind"]) == (supervision.HANDED_OVER, "paused")
    # Parked: alive until its process exits, but nothing to wait for.
    assert detached.live_threads() == [identity] and detached.busy_threads() == []
    assert detached.supervisor.idle()
    # The Control Center holds the lock now, but the parked run's process
    # has not exited: nothing is resumed yet.
    assert control_center.supervisor.tick()
    assert status() == ("PAUSE", "PAUSED") and len(calls) == 1
    assert control_center.get(identity)["last_refusal"]["code"] == (
        supervision.HANDED_OVER
    )
    gone.set()  # the detached process exits
    join(detached)
    assert control_center.supervisor.tick()
    join(control_center)
    assert len(calls) == 2  # Carbon's agent carried on in the Control Center
    assert control_center.get(identity)["last_refusal"] is None
    runs = [d for d in dispatches(control_center) if d["campaign"] == identity]
    assert [(d["supervisor"], d["outcome"]) for d in runs] == [
        (detached.token, "interrupted"),
        (control_center.token, "finished"),
    ]


def pause_as_a_departed_supervisor_left_it(host, identity):
    """What a detached supervisor that paused Carbon's agent and exited
    leaves: the run parked at its checkpoint (settled PAUSED) and its queue
    item still RUNNING under a process that is gone."""
    ledger = CampaignLedger(campaign_root(host, identity))
    control = CampaignControl(ledger)
    generation = control.acquire()
    control.request("pause")
    assert control.settled(generation, cleanup_verified=True) == "PAUSED"
    with host.db() as db:
        supervision.enqueue(
            db,
            principal="alice",
            campaign=identity,
            operation="run",
            params={},
            config_digest="sha256:departed",
            state=supervision.RUNNING,
            supervisor="sup-departed-detached",
        )


def test_a_control_center_resumes_what_was_paused_for_it(journey, monkeypatch):
    """Opening the Control Center never leaves a running campaign paused: what
    was paused to hand it over is resumed once it holds the lock, exactly as
    a Resume would. A campaign its miner paused stays paused."""
    started = []

    async def run_agent(prepared):
        started.append(1)

    monkeypatch.setattr(research_campaign, "run_agent", run_agent)
    host = journey.host
    handed = launch(host, agent="autonomous")["id"]
    paused = launch(host, key="launch-key-0000002", agent="autonomous")["id"]
    join(host)
    assert len(started) == 2
    for identity in (handed, paused):
        pause_as_a_departed_supervisor_left_it(host, identity)
    host._refused(handed, supervision.HANDED_OVER, None, kind="paused")
    control_center = journey.peer(supervision.SUPERVISOR)
    assert control_center.supervisor.tick()
    join(control_center)
    assert len(started) == 3  # the handed-over agent carried on here
    assert control_center.get(handed)["last_refusal"] is None
    carried = [d for d in dispatches(control_center) if d["campaign"] == handed]
    assert [(d["supervisor"], d["outcome"]) for d in carried][-2:] == [
        ("sup-departed-detached", "interrupted"),
        (control_center.token, "finished"),
    ]
    assert control_center.get(paused)["state"] == "PAUSED"


def test_without_a_control_center_a_handover_pause_stays_a_pause(journey):
    """The Control Center went away before it took over: a detached
    supervisor never resumes what was paused for it, and says why as closing
    the Control Center would (D4)."""
    host = journey.host
    identity = launch(host)["id"]
    join(host)
    assert host.control(identity, "pause")["state"] == "PAUSED"
    host._refused(identity, supervision.HANDED_OVER, None, kind="paused")
    detached = journey.peer(supervision.DETACHED)
    assert detached.supervisor.tick()
    join(detached)
    view = detached.get(identity)
    assert view["state"] == "PAUSED"
    assert view["last_refusal"]["code"] == "paused_when_supervisor_closed"
    assert detached.threads == {}


def test_closing_a_control_center_before_it_took_over_leaves_nothing_running(
    journey, monkeypatch
):
    """D4 for work a Control Center admitted while it was not yet the
    supervisor: what no supervisor started is withdrawn (its launch then
    waits, paused, for Resume); the detached supervisor carries on only what
    was its own."""
    detached = journey.peer(supervision.DETACHED)
    assert detached.supervisor.tick()
    ready = launch(detached)["id"]
    join(detached)
    entered, gate = slow_practice_fixture(monkeypatch)
    perform(detached, "practice", practice(ready, "practice-key-00001"))
    assert entered.wait(20)
    control_center = journey.peer(supervision.SUPERVISOR)
    assert not control_center.supervisor.tick()
    queued = launch(control_center, key="launch-key-0000002")["id"]
    assert not detached.supervisor.tick()  # handing over: nothing claimed
    control_center.close()
    view = detached.get(queued)
    assert view["state"] == "QUEUED" and view["in_flight"] is None
    refused = view["last_refusal"]
    assert (refused["code"], refused["operation"], refused["kind"]) == (
        "paused_when_supervisor_closed",
        "run",
        "paused",
    )
    assert view["recovery"] == [RESUME, STOP]
    (item,) = [d for d in dispatches(detached) if d["campaign"] == queued]
    assert (item["state"], item["outcome"]) == ("DONE", "withdrawn")
    gate.set()
    assert detached.supervisor.tick()  # no Control Center: supervising again
    join(detached)
    assert detached.get(ready)["state"] == "READY"
    assert practices_of(detached, ready) == [("DONE", "finished")]
    assert not (campaign_root(detached, queued) / "campaign-manifest.json").exists()
    detached.control(queued, "resume")  # carried out from its record (D3)
    join(detached)
    assert detached.get(queued)["state"] == "READY"


def test_a_withdrawn_operation_says_it_never_ran(journey):
    """A practice the Control Center queued and closed before any supervisor
    started it: withdrawn, nothing ran, and the campaign is not paused for
    it - it is simply sent again."""
    host = journey.host
    identity = launch(host)["id"]
    join(host)
    detached = journey.peer(supervision.DETACHED)
    assert detached.supervisor.tick()
    control_center = journey.peer(supervision.SUPERVISOR)
    assert not control_center.supervisor.tick()
    perform(control_center, "practice", practice(identity, "practice-key-00001"))
    control_center.close()
    view = host.get(identity)
    assert view["state"] == "READY" and view["in_flight"] is None
    refused = view["last_refusal"]
    assert (refused["code"], refused["operation"]) == (
        "withdrawn_when_supervisor_closed",
        "practice",
    )
    assert view["completed_experiments"] == 0


def test_work_queued_while_retiring_is_taken_back(journey):
    detached = journey.peer(supervision.DETACHED)
    assert detached.supervisor.tick()
    client = journey.peer(supervision.CLIENT)
    launch(client)  # queued while the supervisor still holds the lock
    assert journey.spawned == []
    assert detached.supervisor._retire() is False
    assert detached.supervisor.held


def test_a_client_wakes_a_supervisor_only_for_stranded_work(tmp_path, monkeypatch):
    path = minimal_profile(tmp_path)
    spawned = []
    monkeypatch.setattr(
        RunnerAdapter,
        "spawn",
        staticmethod(lambda configuration: spawned.append(configuration)),
    )
    RunnerAdapter.for_profile(path).close()
    assert spawned == []
    database = tmp_path / "campaigns" / "launchpad-campaigns.sqlite3"
    queue_refused_item(database)
    RunnerAdapter.for_profile(path).close()
    assert spawned == [path]
    # A supervisor already alive takes it: nothing is started.
    lock = supervision.SupervisorLock(supervision.lock_directory(database, "alice"))
    assert lock.try_acquire()
    try:
        RunnerAdapter.for_profile(path).close()
    finally:
        lock.release()
    assert spawned == [path]


def test_a_client_observing_waiting_work_starts_a_supervisor_at_most_once(
    journey, monkeypatch
):
    """After the Control Center closes, queued work waits for a supervisor;
    a client that observes it starts one - and polling does not fan out."""
    client = journey.peer(supervision.CLIENT)
    identity = launch(client)["id"]
    assert journey.spawned == [1]
    for _ in range(5):
        assert client.get(identity)["in_flight"]["supervisor_running"] is False
    assert journey.spawned == [1]
    monkeypatch.setattr(supervision, "ACQUIRE_SECONDS", 0.0)
    client.get(identity)
    assert journey.spawned == [1, 1]


def test_admitted_work_is_never_answered_as_failed_when_no_supervisor_starts(
    journey, monkeypatch
):
    """Review nit: a supervisor that could not be started (the host out of
    processes, say) answered a launch already recorded and queued as a
    failure. The work is admitted; the next observe or client start wakes a
    supervisor for it."""

    def cannot_start(configuration):
        raise OSError(11, "Resource temporarily unavailable")

    monkeypatch.setattr(RunnerAdapter, "spawn", staticmethod(cannot_start))
    client = journey.peer(supervision.CLIENT)
    launched = launch(client)
    assert launched["state"] == "QUEUED"
    assert launched["in_flight"]["state"] == "QUEUED"
    supervisor = journey.peer(supervision.SUPERVISOR)
    assert supervisor.supervisor.tick()
    join(supervisor)
    assert supervisor.get(launched["id"])["state"] == "READY"


def test_a_paused_launch_never_prepared_wakes_no_supervisor(journey):
    """Review nit: `_stranded` ignored what recovery checks, so a paused or
    stopped launch that was never prepared started an idle detached
    supervisor on every client start."""
    client = journey.peer(supervision.CLIENT)
    identity = launch(client)["id"]
    with client.db() as db:
        db.execute("UPDATE launchpad_dispatch SET state='DONE', outcome='lost'")
    row = dict(client._bound(identity)[0])
    assert RunnerAdapter._stranded(row)  # specimen: waiting for a supervisor
    control = CampaignControl(CampaignLedger(campaign_root(client, identity)))
    generation = control.acquire()
    control.request("pause")
    assert control.settled(generation, cleanup_verified=True) == "PAUSED"
    assert not RunnerAdapter._stranded(row)
    control.request("stop")
    assert control.settled(control.acquire(), cleanup_verified=True) == "STOPPED"
    assert not RunnerAdapter._stranded(row)


def test_the_detached_supervisor_is_started_in_its_own_session(monkeypatch, tmp_path):
    started = []
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda command, **options: started.append((command, options)),
    )
    supervision.spawn_detached(tmp_path / "profile.json")
    ((command, options),) = started
    assert command[1:] == [
        "-m",
        "scripts.dev.miner_launchpad.supervisor",
        "--configuration",
        str(tmp_path / "profile.json"),
    ]
    assert options["start_new_session"] is True
    assert options["cwd"] == REPOSITORY
    for stream in ("stdin", "stdout", "stderr"):
        # Never the client's stdio: an MCP client's protocol runs over it.
        assert options[stream] == subprocess.DEVNULL


def test_a_real_detached_supervisor_claims_refuses_and_exits_when_idle(tmp_path):
    """A real process: it takes the lock, claims the queued item, refuses it
    by name (admitted under another profile), and exits once idle."""
    path = minimal_profile(tmp_path)
    database = tmp_path / "campaigns" / "launchpad-campaigns.sqlite3"
    RunnerAdapter.for_profile(path, role=supervision.INLINE)
    identity = queue_refused_item(database)
    finished = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.dev.miner_launchpad.supervisor",
            "--configuration",
            str(path),
            "--idle-exit-seconds",
            "0.3",
        ],
        cwd=REPOSITORY,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr[-2000:]
    host = RunnerAdapter(database, principal="alice")
    assert host.get(identity)["last_refusal"]["code"] == "profile_differs_from_request"
    assert [d["outcome"] for d in dispatches(host)] == ["refused"]
    assert not supervision.supervisor_alive(
        supervision.lock_directory(database, "alice")
    )


# --- the published contract ----------------------------------------------------


def test_the_view_publishes_only_the_closed_shapes():
    good = supervision.refusal("campaign_busy", operation="practice")
    assert set(good) == {"code", "next_action", "at", "operation", "kind"}
    assert last_refusal({"last_refusal": good})["code"] == "campaign_busy"
    for bad in (
        {"code": "Not a code!", "at": 1.0},
        {"code": "campaign_busy", "at": True},
        {"code": "campaign_busy"},
        "campaign_busy",
    ):
        assert last_refusal({"last_refusal": bad}) is None
    assert in_flight({"in_flight": {"state": "DONE"}}) is None
    assert supervision.read_refusal(b"not json") is None
    assert supervision.recovery_actions("RECONCILIATION_REQUIRED") == [RECONCILE, STOP]
    assert supervision.recovery_actions("READY") == []
    assert supervision.recovery_actions("QUEUED", {"state": "QUEUED"}) == []
    # Nothing resumes a retired-grant or retired-Challenge campaign, so it is
    # offered only what can succeed (review nit: it was offered resume).
    assert supervision.recovery_actions("PAUSED", resumable=False) == [STOP]
    assert supervision.recovery_actions("INTERRUPTED", resumable=False) == [
        RECONCILE,
        STOP,
    ]
    # Reconcile after resume, before stop, wherever the state may hold
    # something to settle (review repair: the lead's W3 contract).
    for state in ("INTERRUPTED", "PAUSE_REQUESTED"):
        assert supervision.recovery_actions(state) == [RESUME, RECONCILE, STOP]
    assert supervision.recovery_actions("PAUSED") == [RESUME, STOP]
    assert supervision.recovery_actions("RECONCILIATION_REQUIRED", resumable=False) == [
        RECONCILE,
        STOP,
    ]
    queued = {"state": "QUEUED", "in_flight": {"state": "QUEUED"}}
    stranded = {"state": "QUEUED", "in_flight": None}
    available = {
        name: {c["action"]: c["available"] for c in controls(own, fixture=False)}
        for name, own in (("queued", queued), ("stranded", stranded))
    }
    assert available == {
        "queued": {"pause": True, "resume": False, "stop": True, "reconcile": True},
        "stranded": {"pause": True, "resume": True, "stop": True, "reconcile": True},
    }


def test_detaching_leaves_an_agentless_campaign_ready(tmp_path):
    from carbon.miner_mcp.standard_cli import _waits_for_its_miner

    def profile(agent, cleanup=False):
        return SimpleNamespace(
            cleanup_only=cleanup, manifest={"agent": agent}, root=tmp_path
        )

    def control(desired):
        return SimpleNamespace(status=lambda: {"desired": desired})

    assert _waits_for_its_miner(profile("none"), control("RUN"))
    assert not _waits_for_its_miner(profile("autonomous"), control("RUN"))
    assert not _waits_for_its_miner(profile("none"), control("PAUSE"))
    assert not _waits_for_its_miner(profile("none", cleanup=True), control("RUN"))
    (tmp_path / "campaign-complete.json").write_text("{}")
    assert not _waits_for_its_miner(profile("none"), control("RUN"))


# --- helpers for a profile on disk ---------------------------------------------


def minimal_profile(tmp_path):
    """A closed runner profile v2 that names files it never opens here."""
    tmp_path.chmod(0o700)
    campaigns = tmp_path / "campaigns"
    campaigns.mkdir(mode=0o700, exist_ok=True)
    revision = "a" * 40
    cfg = {
        "schema": "carbon.launchpad.runner-profile.v2",
        "profile_id": "supervisor-profile",
        "principal": "alice",
        "enabled": True,
        "accepted_revision": revision,
        "campaigns_root": str(campaigns),
        "runtime": {
            "implementation": {"revision": revision},
            "images": ["sha256:" + "d" * 64],
        },
        "paths": {
            key: str(tmp_path / (key + ".json"))
            for key in PATH_FIELDS | {"operator_config"}
        },
    }
    path = tmp_path / "runner-profile.json"
    path.write_bytes(canonical(cfg))
    path.chmod(0o600)
    return path


def queue_refused_item(database):
    """A campaign row and one run queued for it under another profile."""
    identity = "e" * 32
    host = RunnerAdapter(database, principal="alice")
    with host.db() as db:
        db.execute(
            "INSERT INTO launchpad_campaigns (id,request_key,request_digest,profile,principal,config_digest,campaign,state,created,root,admission,budget) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                identity,
                "queued-request-key-01",
                "sha256:request",
                "supervisor-profile",
                "alice",
                "sha256:another-profile",
                "cmp-" + identity,
                "QUEUED",
                1.0,
                str(Path(database).parent / identity),
                canonical({}),
                canonical({}),
            ),
        )
        supervision.enqueue(
            db,
            principal="alice",
            campaign=identity,
            operation="run",
            params={},
            config_digest="sha256:" + digest(b"another")[7:],
            state=supervision.QUEUED,
        )
    return identity
