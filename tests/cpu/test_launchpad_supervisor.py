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
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.development_session import research_campaign
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
    return perform(
        host,
        "launch",
        {
            "challenge": FIXTURE_CHALLENGE["id"],
            "challenge_version": FIXTURE_CHALLENGE["version"],
            "agent": agent,
            "idempotency_key": key,
        },
    )


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
    assert view["recovery"] == [RESUME, STOP]
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
        assert view["recovery"] == [RESUME, STOP]
    # The holder went away without settling it: resume cancels the pause.
    host.control(identity, "resume")
    join(host)
    assert host.get(identity)["state"] == "READY"


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
    detached = journey.peer(supervision.DETACHED)
    detached.supervisor.poll, detached.supervisor.idle_exit = 0.05, 0.2
    control_center = journey.peer(supervision.SUPERVISOR)
    directory = supervision.lock_directory(journey.host.database, "alice")
    assert detached.supervisor.tick()
    assert not control_center.supervisor.tick()  # one holder at a time
    assert supervision.supervisor_alive(directory)
    # While it does not hold the lock, the Control Center queues its work.
    identity = launch(control_center)["id"]
    assert control_center.threads == {}
    assert detached.supervisor.run_until_idle() is True
    join(detached)
    assert not detached.supervisor.held
    assert not supervision.supervisor_alive(directory)
    assert control_center.get(identity)["state"] == "READY"
    assert control_center.supervisor.tick()  # the next supervisor takes over


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
