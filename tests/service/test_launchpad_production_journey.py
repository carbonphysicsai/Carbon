"""The Launchpad production journey, end to end (OWNER-LAUNCHPAD-PROD-01).

A test (or a lettered few) per stage of a miner's journey through the merged
production work (LP-PROD-A to G), each through the doors a miner uses:

1. a launch from a short-lived MCP stdio client that exits at once is carried
   out by a supervisor in another process, not left QUEUED;
2. attaching announces the research tools - `notifications/tools/list_changed`
   to a handshake-era client (2), an event on a current client's
   `subscriptions/listen` stream (2b) - and lists them;
3. a research call with an argument mistake is answered with a correction
   naming the field, before dispatch, and the corrected call succeeds;
4. Carbon's agent runs a three-call parallel turn in order, journalled; a
   malformed selection and an unpractised one are answered recoverably; a
   practised one is selected and, not evaluated, kept with its campaign
   READY through the Tools tab and restarts; a resume replays with no model
   call and no dispatch;
5. a reply cut off at the output cap and a transient 503 do not end the
   epoch; a call whose outcome is unknown is settled conservatively, and the
   epoch goes on (5b: by the Control Center's own reconcile action);
6. a submit is refused at once with its next step when no validator is
   configured (6a), and otherwise shows a closed refusal or the validator's
   outcome, through a loopback intake to a throwaway validator (6b), never a
   false "Submitted"; an intake's refusal reaches the miner with its own
   next step (6c);
7. closing the Control Center pauses, never stops; restarting it flags no
   idle campaign; resume survives a profile change that does not matter.
8. Graphite, the agent miners run (OWNER-GRAPHITE-MINER-01): a RESEARCH
   campaign hunts (a paper already in the pack is never read again: one
   Reader call, by its ledger identity), reads, and writes a plan citing the
   miner's own card, practising nothing, and the view shows that plan (8a);
   the miner pins, bans and edits the plan through both doors - an edit at
   each - and a banned card is neither served nor citable (8b); a BUILD
   campaign constructs from the edited plan, practises, selects the
   practised recipe and submits through the intake, frozen by plan and
   curation digests, and a resume calls nothing (8c); a FULL campaign's
   research stops typed at its share (`research_share_reached`) after the
   calls the share admits, and the build goes on, its unevaluated candidate
   kept READY as in 4 (8d); with no per-epoch cap
   a campaign runs past 48 calls until the miner's own ceiling stops it,
   and a long run compacts once - a metered call, its summary labelled -
   and replays exactly (8e).

Stages 4 and 5 run Carbon's autonomous agent as campaigns launched before
Graphite replaced it still run it: from their record (`recorded_launch`).
Stage 8 needs Graphite's miner edition (S1 to S3); it is skipped until that
is present. Run over S1 to S3's heads of 2026-10-03, 8d passes as it is;
8a, 8b, 8c and 8e also need the S2/S3 seams the S4 report names (the hunt's
id, the Reader's prompt, `record_outcome`'s Challenge, and the miner's
ceiling as a typed stop).

No paid call is made. Real here: the MCP SDK client and the stdio servers
(`standard_cli`), the campaign host (`RunnerAdapter`, the operations table and
its gates, supervision, control settling, the ledger and the projection), the
Control Center's HTTP door, the research SDK and battery's research service,
Carbon's agent loop and provider layer, battery's practice program (in a
subprocess) and the battery intake, worker and validator daemon on loopback.

DEVELOPMENT FIXTURES ONLY, by name, none reachable from a product door:
- the model provider is a scripted transport (`Script`); nothing reaches a
  provider, and nothing here is agent evidence;
- chain registration and signing are the existing fixtures (a stub chain,
  `test_standard_mcp_cli.FixtureSigner`, the intake tests' development keys);
- preparing a campaign is a fixture: `journey_fixture` for the lifecycle
  stages (1, 7) and `battery_prepare` for battery (4, 5, 6), which composes
  battery's real research service with the test practice runner
  (`battery_subprocess_runner`, not isolated) instead of Docker images;
- the validator is a throwaway `operate init` deployment with the `direct`
  backend, its pool opened from published development cases.
Every state directory is under pytest's tmp_path; every listener is loopback.
This is engineering evidence of the path, not scientific, security or
economic evidence; tests are not a security audit.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import itertools
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve()
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests" / "cpu")]

#: journey_fixture.FIXTURE_CHALLENGE, spelled out: the subprocess entry points
#: below import this module before `scripts` is importable.
FIXTURE_CHALLENGE = {"id": "fixture-reference-burgers", "version": "0"}
#: The battery Challenge's registry id.
BATTERY = "battery-fastcharge-ageing-development-v1"
RESEARCH = "carbon_research_v2__"
PRINCIPAL = "alice"


def recipe(neighbours):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "knn",
        "parameters": {"neighbours": neighbours},
    }


KNN = recipe(6)
UNPRACTISED = recipe(3)


# --- processes ---------------------------------------------------------------
#
# Each process a miner runs is a real process here: an MCP stdio server (a
# client of the campaigns' supervisor), the detached supervisor it starts, and
# the Control Center. Each records its pid under <root>/pids, so a test can
# show which process carried the work, and the fixture ends what outlives it.


def record_pid(root, kind):
    (Path(root) / "pids" / f"{kind}-{os.getpid()}").write_text(str(os.getpid()))


def pids(root, kind):
    return sorted(
        int(p.name.rsplit("-", 1)[1]) for p in (root / "pids").glob(kind + "-*")
    )


def alive(pid):
    """Whether `pid` is running (a zombie is not)."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    return stat.rsplit(")", 1)[1].split()[0] != "Z"


def wait_for(predicate, what, timeout=60.0):
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        assert time.monotonic() < deadline, "timed out waiting for " + what
        time.sleep(0.1)


def spawn(root, role, variant=None):
    """Start this module as `role` over `root`, in its own session, as
    `supervisor.spawn_detached` starts a detached supervisor: its standard
    streams are never a client's stdio (they go to a log under the root)."""
    home = Path(root) / "home"
    home.mkdir(mode=0o700, exist_ok=True)
    # The child keeps its own copy of the log's descriptor.
    with open(Path(root) / "logs" / f"{role}-{time.time_ns()}.log", "ab") as log:
        return subprocess.Popen(
            [
                sys.executable,
                str(HERE),
                role,
                str(root),
                *([variant] if variant else []),
            ],
            cwd=REPOSITORY,
            # The test's own HOME: nothing reads or writes the real ~/.carbon.
            env={**os.environ, "HOME": str(home)},
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            close_fds=True,
        )


def shared_root(tmp_path):
    """The miner's machine: one runner database, campaigns and setup state,
    shared by every process in a test."""
    root = tmp_path / "miner"
    root.mkdir(mode=0o700)
    for name in ("campaigns", "pids", "logs", "fixture-hosts", "setup-state"):
        (root / name).mkdir(mode=0o700)
    (root / "runner-profile.json").write_text("{}")
    return root


@pytest.fixture
def processes(tmp_path):
    """Ends every process a test started that is still running, and fails
    the test if one had to be ended (a supervisor must retire by itself)."""
    started = []
    yield started
    for proc in started:
        if proc.poll() is None:
            proc.kill()
            proc.wait(10)
    leftover = []
    for folder in tmp_path.glob("*/pids"):
        for path in folder.iterdir():
            pid = int(path.read_text())
            if alive(pid):
                leftover.append(path.name)
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGKILL)
    assert not leftover, leftover


def stdio(root, role="serve", variant=None):
    """The MCP stdio server a miner's own client starts: this module as
    `role` over `root`. HOME is the test's own, so nothing reads or writes
    the real ~/.carbon."""
    from mcp.client.stdio import StdioServerParameters

    environment = {"HOME": str(root / "home")}
    for name in ("JAX_PLATFORMS", "XLA_PYTHON_CLIENT_PREALLOCATE"):
        if name in os.environ:
            environment[name] = os.environ[name]
    return StdioServerParameters(
        command=sys.executable,
        args=[str(HERE), role, str(root), *([variant] if variant else [])],
        cwd=REPOSITORY,
        env=environment,
    )


def client(root, role="serve", variant=None, **options):
    from mcp import Client

    (root / "home").mkdir(mode=0o700, exist_ok=True)
    return Client(stdio(root, role, variant), read_timeout_seconds=120, **options)


def refusal_of(result):
    """An MCP operation refusal: JSON {error, field, next_step} after the
    SDK's "Error executing tool <name>: " prefix (LP-PROD-B)."""
    assert result.is_error, result.structured_content
    return json.loads(result.content[0].text.split(": ", 1)[1])


async def observe(session, campaign, until, what, timeout=90.0):
    deadline = time.monotonic() + timeout
    while True:
        result = await session.call_tool("carbon_observe", {"campaign": campaign})
        assert not result.is_error, result.content
        view = result.structured_content["payload"]
        if until(view):
            return view
        assert time.monotonic() < deadline, (what, view)
        await asyncio.sleep(0.2)


def method_of(message):
    for item in (message, getattr(message, "root", None)):
        method = getattr(item, "method", None)
        if type(method) is str:
            return method
    return type(message).__name__


# --- the lifecycle host, shared across processes ------------------------------


class Registered:
    """The stub chain the open tier reads: the fixture hotkey holds UID 0."""

    async def capture(self, context):
        from carbon.chain.models import MetagraphSnapshot, Participant
        from scripts.dev.miner_launchpad.journey_fixture import HOTKEY

        return MetagraphSnapshot(
            context=context,
            finalized_block=100,
            block_hash="0x" + "cd" * 32,
            timestamp_ms=1,
            participants=(
                Participant(
                    uid=0, hotkey=HOTKEY, coldkey="5" + "C" * 47, registered_at=1
                ),
            ),
        )


#: Runner-profile changes a test makes. `unrelated` changes nothing a campaign
#: was frozen with (LP-PROD-C D10: the profile's name and a validator intake);
#: `revision` changes the accepted revision, which a frozen campaign binds.
VARIANTS = {
    None: lambda cfg: cfg,
    "unrelated": lambda cfg: {
        **cfg,
        "profile_id": "journey-profile-renamed",
        "intakes": {FIXTURE_CHALLENGE["id"]: "https://validator.example/intake"},
    },
    "revision": lambda cfg: {
        **cfg,
        "accepted_revision": "b" * 40,
        "runtime": {**cfg["runtime"], "implementation": {"revision": "b" * 40}},
    },
}


def install_journey(root, patch, variant=None):
    """`journey_fixture`'s fixtures in this process - preparation, training
    and the final exam - and its runner profile over the shared `root`.

    `journey_host` builds a host on a root of its own; its fixtures are kept
    and its host is closed, so several processes (and peers) share one
    database exactly as a miner's Control Center and MCP clients do."""
    from scripts.dev.miner_launchpad.journey_fixture import journey_host
    from scripts.dev.miner_launchpad.runner import PATH_FIELDS

    own = root / "fixture-hosts" / f"{os.getpid()}-{secrets.token_hex(4)}"
    own.mkdir(mode=0o700)
    inline = journey_host(own, patch=patch)
    try:
        cfg = {
            **inline.configured(),
            "campaigns_root": str(root / "campaigns"),
            "paths": {
                name: str(root / (name + ".json"))
                for name in PATH_FIELDS | {"operator_config"}
            },
        }
        fixtures = SimpleNamespace(
            cfg=VARIANTS[variant](cfg),
            registration=inline.registration,
            preflight=inline.preflight,
        )
    finally:
        inline.close()
    return fixtures


def peer(fixtures, root, role):
    """One process's campaign host over the shared root, as `role`."""
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    host = RunnerAdapter(
        root / "runner.sqlite3",
        principal=PRINCIPAL,
        registration=fixtures.registration,
        role=role,
    )
    host.configured = lambda: fixtures.cfg
    host.preflight = fixtures.preflight
    return host


def agent_fixtures(root, patch):
    """Two DEVELOPMENT FIXTURES for the lifecycle stages, read from files so
    a test steers them across processes:
    - preparation waits while <root>/hold-preparation exists;
    - Carbon's agent (`run_agent`) records which process runs it, then works
      between real campaign checkpoints - a pause parks it there - until
      <root>/release-agent exists, and completes the campaign."""
    from carbon.development_session import research_campaign
    from carbon.development_session.research_control import CampaignControl

    prepare = research_campaign.prepare

    async def gated(args, *, ledger=None):
        while (root / "hold-preparation").exists():
            await asyncio.sleep(0.05)
        return await prepare(args, ledger=ledger)

    def record_run():
        with open(root / "agent-runs.jsonl", "a") as runs:
            runs.write(json.dumps({"pid": os.getpid()}) + "\n")

    async def run_agent(prepared, *, transport=None, **_):
        record_run()
        control = CampaignControl(prepared.ledger)
        while not (root / "release-agent").exists():
            control.checkpoint(prepared.ledger.generation)
            await asyncio.sleep(0.05)
        research_campaign._complete(prepared)

    patch(research_campaign, "prepare", gated)
    patch(research_campaign, "run_agent", run_agent)
    # Carbon's agent for a new launch is Graphite (OWNER-GRAPHITE-MINER-01):
    # where its miner edition's driver is present, the campaign dispatches to
    # it (S3), and the same fixture stands in for it.
    with contextlib.suppress(ImportError):
        from carbon.agent_campaign.graphite.miner import driver

        patch(driver, "run", run_agent)


def agent_runs(root):
    path = root / "agent-runs.jsonl"
    if not path.exists():
        return []
    return [json.loads(line)["pid"] for line in path.read_text().splitlines()]


def lock_held(root):
    from scripts.dev.miner_launchpad import supervisor as supervision

    return supervision.supervisor_alive(
        supervision.lock_directory(root / "runner.sqlite3", PRINCIPAL)
    )


def ledger_status(root, campaign):
    from carbon.development_session.research_control import CampaignControl
    from carbon.development_session.research_ledger import CampaignLedger

    status = CampaignControl(CampaignLedger(root / "campaigns" / campaign)).status()
    return status["desired"], status["state"]


def dispatches(root, campaign):
    import sqlite3

    with contextlib.closing(sqlite3.connect(root / "runner.sqlite3")) as db:
        return [
            (row[0], row[1], row[2], row[3])
            for row in db.execute(
                "SELECT operation,state,outcome,supervisor FROM launchpad_dispatch WHERE campaign=? ORDER BY seq",
                (campaign,),
            )
        ]


def launch_body(key, agent="none"):
    return {
        "challenge": FIXTURE_CHALLENGE["id"],
        "challenge_version": FIXTURE_CHALLENGE["version"],
        "agent": agent,
        "idempotency_key": key,
    }


def recorded_launch(host, body):
    """A launch recorded under `autonomous` before Graphite replaced it for
    new launches (OWNER-GRAPHITE-MINER-01), which now refuses a new one
    (`autonomous_agent_replaced`). Its row is the one `launch_admitted` wrote
    then; it is carried out from that record (`_recorded_launch`), as a
    queued launch is, and its agent runs `run_agent` unchanged - the
    LP-PROD-A loop stages 4 and 5 exercise."""
    from carbon.development_session.profile import canonical

    cfg = host.configured()
    run_id, request_digest, config_pin = host._launch_identity(cfg, body)
    root = Path(cfg["campaigns_root"]) / run_id
    with host.db() as db:
        db.execute(
            "INSERT INTO launchpad_campaigns (id,request_key,request_digest,profile,principal,config_digest,campaign,state,created,root,admission,budget,research_guidance,launch_request) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                body["idempotency_key"],
                request_digest,
                cfg["profile_id"],
                cfg["principal"],
                config_pin,
                "cmp-" + run_id,
                "QUEUED",
                time.time(),
                str(root),
                canonical(host.registration(cfg).record()),
                canonical(body.get("budget") or {}),
                None,
                canonical({k: v for k, v in body.items() if k != "idempotency_key"}),
            ),
        )
    host._dispatch_run(run_id, cfg, root)
    return run_id


def graphite_ready(host, patch):
    """DEVELOPMENT FIXTURE for the lifecycle stages: a host a Graphite launch
    can be admitted on and carried out by - S2's library and shared pack and
    S3's plan rule as in-memory fakes (`test_launchpad_graphite`), graphite
    admitted as an agent. Each process installs its own; the library holds
    no pins, bans or plans, so every process reads the same curation."""
    from test_launchpad_graphite import PACK, FakeLibrary, card

    from carbon.development_session import product_campaign

    if "graphite" not in product_campaign.AGENTS:
        patch(product_campaign, "AGENTS", (*product_campaign.AGENTS, "graphite"))
    library = FakeLibrary([card("arxiv-2101.00001v1")])
    host.library_root = Path(host.database).parent / "setup-state" / "graphite-library"
    host.open_library = lambda path: library
    host.shared_pack = lambda: PACK
    host.validate_plan = lambda plan, library_, curation: (True, None)
    return host


# --- 1. a launch outlives the client that made it -----------------------------


def test_1_a_launch_from_a_client_that_exits_at_once_is_carried_out(
    tmp_path, processes
):
    """The live failure of 2026-10-03: a stdio client's launch ran on that
    client's own thread and was left QUEUED when it exited. Now the client
    queues it and starts a detached supervisor, which carries it out after
    the client and its server process are gone (preparation is held until
    then, so the order is shown, not assumed)."""
    root = shared_root(tmp_path)
    (root / "hold-preparation").touch()

    async def launch_and_exit():
        async with client(root) as session:
            result = await session.call_tool(
                "carbon_launch", launch_body("e2e-launch-key-0000001")
            )
            assert not result.is_error, result.content
            return result.structured_content["payload"]

    launched = asyncio.run(launch_and_exit())
    campaign = launched["id"]
    assert launched["state"] == "QUEUED"
    assert launched["in_flight"]["operation"] == "run"
    assert launched["last_refusal"] is None
    # The client and its server process are gone ...
    (server,) = pids(root, "server")
    wait_for(lambda: not alive(server), "the stdio server to exit")
    # ... and the supervisor it started is alive, in its own session, and
    # holds the launch while preparation is held.
    (detached,) = wait_for(lambda: pids(root, "supervisor"), "a detached supervisor")
    assert alive(detached) and os.getsid(detached) != os.getsid(0)
    wait_for(lambda: lock_held(root), "the supervisor lock")
    assert not (root / "campaigns" / campaign / "campaign-manifest.json").exists()
    (root / "hold-preparation").unlink()

    async def watch():
        async with client(root) as session:
            return await observe(
                session,
                campaign,
                lambda v: v["state"] == "READY",
                "the launch carried out",
            )

    view = asyncio.run(watch())
    assert view["in_flight"] is None and view["last_refusal"] is None
    assert view["recovery"] == []
    manifest = json.loads(
        (root / "campaigns" / campaign / "campaign-manifest.json").read_bytes()
    )
    assert (manifest["agent"], manifest["challenge"]) == ("none", FIXTURE_CHALLENGE)
    ((operation, state, outcome, supervisor),) = dispatches(root, campaign)
    assert (operation, state, outcome) == ("run", "DONE", "finished")
    assert supervisor.startswith("sup-")
    # Once idle, the detached supervisor retires by itself.
    wait_for(lambda: not alive(detached), "the detached supervisor to retire", 60)
    assert not lock_held(root)


# --- 2. and 3. attach, and a research mistake corrected by name ---------------


def attachable_battery(tmp_path, monkeypatch):
    """A registration-admitted battery campaign as a launch leaves it, under
    a runner profile (the existing stdio attach fixture)."""
    from test_standard_mcp_cli import prepare_battery

    root = tmp_path / "miner"
    root.mkdir(mode=0o700)
    _path, ledger, owner, _ = prepare_battery(root, monkeypatch)
    for name in ("pids", "logs", "setup-state", "home"):
        (root / name).mkdir(mode=0o700)
    return root, ledger, owner


def test_2_attaching_announces_and_lists_the_research_tools(
    tmp_path, monkeypatch, processes
):
    """A handshake-era client (the initialize handshake) is sent
    `notifications/tools/list_changed` when it attaches and again when it
    detaches, and its next tools/list holds the research tools exactly while
    it is attached (LP-PROD-B). Detaching leaves the miner's own campaign
    READY for them (LP-PROD-C)."""
    from test_standard_mcp_cli import CAMPAIGN

    from carbon.development_session.research_control import CampaignControl

    root, ledger, _owner = attachable_battery(tmp_path, monkeypatch)
    methods = []

    async def handler(message):
        methods.append(method_of(message))

    async def exercise():
        async with client(
            root, "attach", mode="legacy", message_handler=handler
        ) as session:
            before = {tool.name for tool in (await session.list_tools()).tools}
            assert {"carbon_attach_campaign", "carbon_launch"} <= before
            assert not any(name.startswith(RESEARCH) for name in before)
            result = await session.call_tool(
                "carbon_attach_campaign", {"campaign": CAMPAIGN}
            )
            assert not result.is_error, result.content
            payload = result.structured_content["payload"]
            assert payload["attached"] == CAMPAIGN
            assert payload["list_changed_announced"] is True
            assert RESEARCH + "start_research_task" in payload["tools_added"]
            for _ in range(100):
                if "notifications/tools/list_changed" in methods:
                    break
                await asyncio.sleep(0.05)
            after = {tool.name for tool in (await session.list_tools()).tools}
            assert set(payload["tools_added"]) <= after
            for name in ("start_research_task", "get_research_result", "dry_validate"):
                assert RESEARCH + name in after
            detached = await session.call_tool("carbon_detach_campaign", {})
            assert not detached.is_error, detached.content
            assert detached.structured_content["payload"]["detached"] == CAMPAIGN
            gone = {tool.name for tool in (await session.list_tools()).tools}
            assert not any(name.startswith(RESEARCH) for name in gone)

    asyncio.run(exercise())
    assert "notifications/tools/list_changed" in methods
    assert methods.count("notifications/tools/list_changed") >= 2  # attach, detach
    assert CampaignControl(ledger).status()["state"] == "READY"


def test_2b_a_current_client_hears_the_change_on_its_listen_stream(
    tmp_path, monkeypatch, processes
):
    """A client on the current protocol (2026-07-28, the SDK's default
    negotiation) learns of the new tools on its `subscriptions/listen`
    stream, where that era carries change notifications (LP-PROD-B)."""
    import anyio
    from mcp.client.subscriptions import ToolsListChanged
    from mcp_types.version import MODERN_PROTOCOL_VERSIONS
    from test_standard_mcp_cli import CAMPAIGN

    root, _ledger, _owner = attachable_battery(tmp_path, monkeypatch)

    async def exercise():
        async with client(root, "attach") as session:
            assert session.protocol_version in MODERN_PROTOCOL_VERSIONS
            async with session.listen(tools_list_changed=True) as stream:
                result = await session.call_tool(
                    "carbon_attach_campaign", {"campaign": CAMPAIGN}
                )
                assert not result.is_error, result.content
                with anyio.fail_after(30):
                    event = await stream.__anext__()
                assert isinstance(event, ToolsListChanged)
                names = {tool.name for tool in (await session.list_tools()).tools}
                assert RESEARCH + "start_research_task" in names
                detached = await session.call_tool("carbon_detach_campaign", {})
                assert not detached.is_error, detached.content

    asyncio.run(exercise())


def test_3_a_research_mistake_is_corrected_by_name_and_the_retry_succeeds(
    tmp_path, monkeypatch, processes
):
    """The most common agent mistake - a workspace action missing a field -
    is answered before dispatch, naming the field in object terms, retryable,
    charging nothing; the corrected call succeeds (LP-PROD-B door, LP-PROD-D
    named refusals)."""
    from test_standard_mcp_cli import CAMPAIGN

    root, ledger, owner = attachable_battery(tmp_path, monkeypatch)
    request = {
        "kind": "workspace",
        "action": "public_material",
        "hypothesis": "Read the Challenge's public objective",
        "expected_effect": "Know what the recipe is scored on",
    }

    async def exercise():
        async with client(root, "attach") as session:
            attached = await session.call_tool(
                "carbon_attach_campaign", {"campaign": CAMPAIGN}
            )
            assert not attached.is_error, attached.content
            mistake = await session.call_tool(
                RESEARCH + "start_research_task",
                {**request, "operation_id": "e2e-mistake-000000001", "arguments": {}},
            )
            assert not mistake.is_error, mistake.content
            refused = mistake.structured_content
            assert refused["requires_reconciliation"] is False
            payload = refused["payload"]
            assert payload["status"] == "REJECTED_BEFORE_DISPATCH"
            assert payload["correction_code"] == "workspace_field_missing"
            assert payload["field"] == "arguments.name"
            assert "arguments.name" in payload["correction"]
            assert payload["authority_granted"] is False
            fixed = await session.call_tool(
                RESEARCH + "start_research_task",
                {
                    **request,
                    "operation_id": "e2e-corrected-0000001",
                    "arguments": {"name": "objective"},
                },
            )
            assert not fixed.is_error, fixed.content
            body = fixed.structured_content["payload"]
            assert body["terminal_task"]["state"] == "SUCCEEDED"
            document = body["public_result"]["result"]["document"]
            assert document["challenge"]["id"] == BATTERY

    asyncio.run(exercise())
    # The mistake started nothing and spent no research-trial slot.
    assert ledger.status(owner=owner)["used"]["research_trials"] == 0


# --- 4., 5. and 6.: battery through the Launchpad -----------------------------

#: The fixture runtime a battery campaign is frozen with (the stdio fixtures'
#: image ids; nothing runs in an image here).
BATTERY_REVISION = "f" * 40
BATTERY_IMAGES = ["fixture-cpu", "fixture-analysis"]


def battery_prepare(patch, *, miner_key=None):
    """DEVELOPMENT FIXTURE: prepare a battery product campaign the way
    `battery.campaign.prepare_battery` does - its real manifest
    (`manifest_document`, with the provider plan a launch freezes), its real
    research service and gateway (`compose`), the research SDK - with the
    stdio tests' chain connection and signer, and the test practice runner
    (`battery_subprocess_runner`, not isolated) in place of the worker image,
    the doctor and the miner's signer. `miner_key` is the intake tests'
    development key, for a submission through an intake."""
    import battery_subprocess_runner as practice_runner
    from test_c08_authenticated_miner_mcp import NOW
    from test_standard_mcp_cli import FixtureSigner, fixture_connection

    import carbon.chain.auth
    from carbon.battery import campaign as battery
    from carbon.battery.challenge import CHALLENGE
    from carbon.challenge_registry.campaigns import campaign_for
    from carbon.development_session import research_campaign, research_tools
    from carbon.development_session.data import write_once
    from carbon.development_session.profile import canonical
    from carbon.development_session.research_agent_policy import AUTONOMOUS
    from carbon.development_session.research_tools import ResearchMinerTools
    from carbon.miner_mcp import standard_cli

    patch(carbon.chain.auth, "BittensorMessageSigner", FixtureSigner)
    patch(research_tools, "BittensorMessageSigner", FixtureSigner)
    challenge = campaign_for(
        {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version}
    )
    # One clock for every preparation: 50 ms per transmission, inside the
    # fixture snapshot's freshness window, never faster than the rate limit.
    ticks = itertools.count(NOW, 50_000_000)

    async def prepare(args, *, ledger=None):
        connection = fixture_connection(args.root)
        connection.service.gateway.clock_ns = lambda: next(ticks)
        if miner_key is not None:
            connection.miner_key = miner_key
        owner = await standard_cli._requester(connection)
        path = args.root / "campaign-manifest.json"
        if path.exists():
            manifest = json.loads(path.read_bytes())
        else:
            # The selection a new plan of Carbon's agent freezes, as
            # prepare_battery builds it: the model's own maximum output is
            # its default output cap (OWNER-LAUNCHPAD-PROD-02).
            selection = (
                None
                if args.product.agent == "none"
                else research_campaign.supplied_selection(
                    args,
                    output_default=research_campaign.new_plan_output_default(args),
                )
            )

            # A Graphite launch's choice is frozen as the real preparation
            # freezes it (S3's `prepare_battery`): its launch fields and the
            # miner's library read once (`driver.freeze_launch`), the block
            # that gives passed to the plan builder.
            frozen = {}
            parameters = inspect.signature(battery.manifest_document).parameters
            if "graphite" in parameters and args.product.agent == "graphite":
                from carbon.agent_campaign.graphite.miner.driver import (
                    freeze_launch,
                )

                frozen["graphite"] = freeze_launch(
                    args,
                    args.root,
                    challenge={
                        "id": CHALLENGE.challenge_id,
                        "version": CHALLENGE.version,
                    },
                )
            manifest = battery.manifest_document(
                args.product,
                owner=owner,
                implementation={"revision": BATTERY_REVISION},
                images=BATTERY_IMAGES,
                selection=selection,
                **frozen,
            )
            write_once(path, canonical(manifest))
        ledger.freeze(manifest)
        plan = manifest["provider"]
        # The model selection the frozen plan records, as prepare_battery
        # reads it, for Carbon's agent to call.
        selection = (
            None if plan.get("agent") == "none" else battery.plan_selection(args, plan)
        )
        composition, wrapper = battery.compose(
            ledger=ledger,
            owner=owner,
            image=SimpleNamespace(image_id=BATTERY_IMAGES[0]),
            analysis=SimpleNamespace(image_id=BATTERY_IMAGES[1]),
            connection=connection,
            runner=practice_runner.run,
            backend=practice_runner.BACKEND,
        )
        return research_campaign.PreparedCampaign(
            args=args,
            ledger=ledger,
            owner=owner,
            manifest=manifest,
            seeds=None,
            role_root=None,
            data=None,
            image=None,
            key=None,
            config=None,
            composition=composition,
            sdk=ResearchMinerTools(
                connection=connection,
                wrapper=wrapper,
                composition=composition,
                ledger=ledger,
                owner=owner,
            ),
            task=None,
            grant=None,
            agent_policy=AUTONOMOUS,
            campaign=challenge,
            challenge=CHALLENGE,
            selection=selection,
        )

    patch(research_campaign, "prepare", prepare)
    return ticks


class Script:
    """The model provider, scripted: each item in order is a reply (a dict),
    or an exception the transport raises. Every request is kept as sent."""

    def __init__(self, *items):
        self.items, self.requests = list(items), []

    def __call__(self, request):
        from carbon.development_session.profile import canonical

        self.requests.append(json.loads(canonical(request)))
        if not self.items:
            raise AssertionError("the scripted provider has no more replies")
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def reply(*output, status="completed", reason=None, output_tokens=100):
    from carbon.development_session.agent import MODEL

    body = {
        "model": MODEL,
        "status": status,
        "output": list(output),
        "usage": {
            "input_tokens": 1000,
            "output_tokens": output_tokens,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }
    if reason is not None:
        body["incomplete_details"] = {"reason": reason}
    return body


def call(call_id, name, arguments, **extra):
    return {
        "type": "function_call",
        "name": name,
        "call_id": call_id,
        "arguments": json.dumps(arguments),
        **extra,
    }


def task(kind, *, strategy=None, action=None, arguments=None, why="a test step"):
    from carbon.development_session.research_tools import PREFIX

    return PREFIX + "start_research_task", {
        "kind": kind,
        "strategy_json": None if strategy is None else json.dumps(strategy),
        "action": action,
        "arguments_json": None if arguments is None else json.dumps(arguments),
        "hypothesis": why,
        "expected_effect": "an observation that decides the next step",
    }


def outputs(request):
    return {
        item["call_id"]: json.loads(item["output"])
        for item in request["input"]
        if item.get("type") == "function_call_output"
    }


class BatteryLaunchpad:
    """A miner's Control Center host with battery campaigns: the real
    campaign host in this process (INLINE, as the browser smoke runs it) over
    `battery_prepare`, Carbon's agent with a scripted provider, and the
    Control Center's HTTP door on loopback when a test asks for it."""

    def __init__(self, tmp_path, monkeypatch, *, miner_key=None):
        from carbon.development_session import research_agent, research_campaign
        from scripts.dev.miner_launchpad.runner import PATH_FIELDS, RunnerAdapter

        self.root = shared_root(tmp_path)
        self.patch = monkeypatch.setattr
        self.install = install_journey(self.root, monkeypatch.setattr)
        self.ticks = battery_prepare(monkeypatch.setattr, miner_key=miner_key)
        monkeypatch.setattr(RunnerAdapter, "spawn", staticmethod(lambda _: None))
        # Retries wait no wall time here; the waits asked for are recorded.
        self.waits = []
        monkeypatch.setattr(
            research_agent,
            "retry_wait",
            lambda retries, after, jitter: self.waits.append(retries) or 0.0,
        )
        self.transport = None
        real = research_campaign.run_agent

        async def run_agent(prepared, *, transport=None):
            assert self.transport is not None, "no scripted provider"
            return await real(prepared, transport=self.transport)

        monkeypatch.setattr(research_campaign, "run_agent", run_agent)
        self.cfg = {
            "profile_id": "battery-journey-profile",
            "principal": PRINCIPAL,
            "enabled": True,
            "campaigns_root": str(self.root / "campaigns"),
            "accepted_revision": BATTERY_REVISION,
            "runtime": {
                "implementation": {"revision": BATTERY_REVISION},
                "images": list(BATTERY_IMAGES),
            },
            "paths": {
                name: str(self.root / (name + ".json"))
                for name in PATH_FIELDS | {"operator_config"}
            },
        }
        self.host = self.new_host()
        self.servers = []

    def new_host(self):
        """This Control Center's campaign host over the shared database:
        INLINE, as the browser smoke's host, so it recovers as it starts."""
        from scripts.dev.miner_launchpad.runner import RunnerAdapter

        host = RunnerAdapter(
            self.root / "runner.sqlite3",
            principal=PRINCIPAL,
            registration=self.install.registration,
        )
        host.configured = lambda: self.cfg
        host.preflight = self.install.preflight
        return host

    def restart(self):
        """The Control Center closed and started again: this host closed and
        a new one over the same records, which recovers what it finds."""
        library = self.host.library_root
        self.host.close()
        self.host = self.new_host()
        self.host.library_root = library

    def tools(self, campaign):
        """The Control Center's Tools tab on `campaign`, opened and closed:
        the host's own tool sessions over the real attachment
        (`standard_cli.attached`, as `runner_opener` makes it), under this
        host's runner profile written where the Control Center reads it, with
        the stdio attach fixtures' runtime (`fixture_runtime`: the host,
        images and key) on the preparations' own clock. Returns the
        campaign's ledger state while open."""
        from test_standard_mcp_cli import fixture_runtime, private_write

        from carbon.miner_mcp import standard_cli
        from scripts.dev.miner_launchpad.runner import PROFILE_SCHEMA

        def runtime(profile):
            connection, *rest = fixture_runtime(profile)
            connection.service.gateway.clock_ns = lambda: next(self.ticks)
            return (connection, *rest)

        path = self.root / "runner-profile.json"
        private_write(path, {**self.cfg, "schema": PROFILE_SCHEMA})
        self.patch(standard_cli, "_runtime", runtime)
        self.host.configuration = path
        try:
            opened = self.host.tool_sessions.open(campaign)
            assert opened["open"] is True, opened
            held = ledger_status(self.root, campaign)
        finally:
            self.host.tool_sessions.close(campaign)
            self.host.configuration = None
        return held

    def perform(self, operation, request):
        from scripts.dev.miner_launchpad.operations import perform

        return perform(self.host, operation, request)

    def join(self):
        for thread in list(self.host.threads.values()):
            thread.join(timeout=600)
            assert not thread.is_alive()

    def launch(self, key, agent="none", budget=None):
        from carbon.battery.challenge import CHALLENGE

        if agent != "none" and budget is None:
            budget = {
                "ceilings": {
                    "provider_attempts": 24,
                    "provider_nanodollars": 24 * new_plan_reservation(),
                    "research_trials": 4,
                }
            }
        body = {
            "challenge": CHALLENGE.challenge_id,
            "challenge_version": CHALLENGE.version,
            "agent": agent,
            "idempotency_key": key,
            **({} if budget is None else {"budget": budget}),
        }
        if agent == "autonomous":
            campaign = recorded_launch(self.host, body)
        else:
            campaign = self.perform("launch", body)["id"]
        self.join()
        return campaign

    def campaign_root(self, campaign):
        return self.root / "campaigns" / campaign

    def view(self, campaign):
        return self.host.get(campaign)

    def owner(self, campaign):
        manifest = self.campaign_root(campaign) / "campaign-manifest.json"
        return json.loads(manifest.read_bytes())["owner"]

    def ledger(self, campaign):
        from carbon.development_session.research_ledger import CampaignLedger

        return CampaignLedger(self.campaign_root(campaign))

    def http(self):
        """The Control Center's HTTP door over this host, on loopback."""
        from scripts.dev.miner_launchpad import controller

        token = "e2e-" + secrets.token_hex(20)
        server = controller.Server(
            controller.Controller(self.root / "launchpad.sqlite3"),
            token,
            port=0,
            research_runner=self.host,
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.servers.append(server)
        return server, token

    def close(self):
        for server in self.servers:
            server.shutdown()
            server.server_close()
        self.host.close()


def post(server, token, path, body):
    import http.client

    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=30)
    try:
        connection.request(
            "POST",
            path,
            json.dumps(body),
            {"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


@pytest.fixture
def battery(tmp_path, monkeypatch):
    launchpad = BatteryLaunchpad(tmp_path, monkeypatch)
    yield launchpad
    launchpad.close()


def waits_ready_with_its_candidate(launchpad, campaign):
    """An agent's candidate the validator did not evaluate is kept, and its
    campaign waits for its miner: READY, its `evaluation_unavailable` refusal
    and next step kept, no interruption recorded - after its run, after the
    Tools tab opens and closes on it, and after the Control Center restarts,
    including a restart that finds it held by a Tools tab whose process died
    (LP-PROD-FIX-01). Smoke run 382c4276 showed each of these INTERRUPTED,
    the last with `campaign_interrupted` over the refusal."""
    from carbon.development_session.research_control import CampaignControl
    from scripts.dev.miner_launchpad import supervisor as supervision

    root = launchpad.campaign_root(campaign)

    def kept(view):
        refused = view["last_refusal"]
        assert view["state"] == "READY", (view["state"], refused)
        assert (refused["code"], refused["operation"]) == (
            "evaluation_unavailable",
            "submit",
        )
        assert (
            refused["next_action"] == supervision.NEXT_ACTIONS["evaluation_unavailable"]
        )
        assert view["journey"]["frozen_awaiting_submission"] is True
        assert ledger_status(launchpad.root, campaign) == ("RUN", "READY")
        assert not (root / "interruptions.jsonl").exists()

    kept(launchpad.view(campaign))
    # The Tools tab holds the campaign while open, and settles it as it
    # closes.
    assert launchpad.tools(campaign) == ("RUN", "RECONCILING")
    kept(launchpad.view(campaign))
    launchpad.restart()
    kept(launchpad.view(campaign))
    # A Tools tab whose process died left it held (RECONCILING): the
    # restarted Control Center's recovery settles it.
    CampaignControl(launchpad.ledger(campaign)).acquire()
    launchpad.restart()
    kept(launchpad.view(campaign))


def test_4_carbons_agent_runs_a_parallel_turn_selects_a_practised_recipe_and_replays(
    battery,
):
    """Carbon's own agent on battery, launched through the Launchpad with the
    miner's finite budget: the v2 rule frozen with the plan runs a three-call
    turn in the model's order, each call journalled under its own identity
    (one a real practice through battery's research service); a selection
    missing a field and one of a recipe never practised are answered as
    REJECTED_BEFORE_DISPATCH and the epoch goes on; the practised recipe is
    selected (LP-PROD-A). With no validator configured the selection is not
    evaluated and the campaign says so by name, waiting READY with its
    candidate through the Tools tab and restarts (LP-PROD-FIX-01). A resume
    replays the epoch from its journal: no model call, no dispatch, nothing
    spent."""
    from carbon.development_session.research_agent_policy import PARALLEL_CALLS_V2
    from carbon.development_session.research_loop import (
        SELECT,
        SELECTION_INVALID,
        SELECTION_NOT_PRACTICED,
    )
    from carbon.development_session.research_tools import PREFIX
    from scripts.dev.miner_launchpad import supervisor as supervision

    select = {"strategy_json": json.dumps(KNN), "used_feedback": False}
    battery.transport = script = Script(
        reply(
            call("a", PREFIX + "get_challenge_info", {}),
            call(
                "b",
                *task(
                    "workspace",
                    action="public_material",
                    arguments={"name": "objective"},
                    why="Read the objective first",
                ),
            ),
            call("c", *task("practice", strategy=KNN, why="Neighbours interpolate")),
        ),
        reply(call("d", SELECT, select)),  # no reason: malformed
        reply(
            call(
                "e",
                SELECT,
                {**select, "strategy_json": json.dumps(UNPRACTISED), "reason": "r"},
            )
        ),
        reply(call("f", SELECT, {**select, "reason": "practised; the only result"})),
    )
    campaign = battery.launch("e2e-agent-key-00000001", agent="autonomous")
    root = battery.campaign_root(campaign)
    folder = root / "epoch-1"
    assert len(script.requests) == 4 and not script.items
    plan = json.loads((folder / "plan.json").read_bytes())
    assert plan["parallel_calls"] == PARALLEL_CALLS_V2
    # The parallel turn: all three ran, in the model's order, each journalled
    # before and after it ran under its own identity.
    identities = ["epoch-1-tool-000", "epoch-1-tool-000-01", "epoch-1-tool-000-02"]
    turn = json.loads((folder / "epoch-1-provider-000-calls.json").read_bytes())
    assert [c["tool"] for c in turn["calls"]] == identities
    for identity, call_id in zip(identities, "abc", strict=True):
        intent = json.loads((folder / (identity + "-intent.json")).read_bytes())
        assert intent["call_id"] == call_id
        assert (folder / (identity + "-result.json")).exists()
    answered = outputs(script.requests[1])
    assert list(answered) == ["a", "b", "c"]
    assert answered["b"]["terminal_task"]["state"] == "SUCCEEDED"
    assert answered["c"]["terminal_task"]["state"] == "SUCCEEDED"
    # The malformed selection was answered, naming its field; the epoch went on.
    malformed = outputs(script.requests[2])["d"]
    assert (malformed["status"], malformed["code"]) == (
        "REJECTED_BEFORE_DISPATCH",
        SELECTION_INVALID,
    )
    assert malformed["field"] == "reason"
    # The unpractised selection was refused with what was practised.
    unpractised = outputs(script.requests[3])["e"]
    assert unpractised["code"] == SELECTION_NOT_PRACTICED
    assert unpractised["practiced_recipes"] == [KNN]
    # The practised one was selected.
    selected = json.loads((folder / "selected-recipe.json").read_bytes())
    assert selected["strategy"] == KNN
    # No validator is configured: the selection is not evaluated, and the
    # miner is told so by name with the next step - never "Submitted".
    view = battery.view(campaign)
    assert view["journey"]["submitted_epochs"] == []
    refused = view["last_refusal"]
    assert (refused["code"], refused["operation"]) == (
        "evaluation_unavailable",
        "submit",
    )
    assert refused["next_action"] == supervision.NEXT_ACTIONS["evaluation_unavailable"]
    assert (
        submit_stage(battery, campaign)["refusal"]["code"] == "evaluation_unavailable"
    )
    waits_ready_with_its_candidate(battery, campaign)
    ledger, owner = battery.ledger(campaign), battery.owner(campaign)

    def spent():
        used = ledger.status(owner=owner)["used"]
        return {
            k: used[k]
            for k in ("provider_attempts", "provider_nanodollars", "research_trials")
        }

    before = spent()
    assert before["provider_attempts"] == 4 and before["research_trials"] == 1
    results = sorted(folder.glob("epoch-1-tool-*-result.json"))
    # Resume: the epoch replays from its journal - no model call, no dispatch.
    battery.transport = never = Script()
    resumed = battery.host.control(campaign, "resume")
    assert resumed["last_refusal"] is None
    battery.join()
    assert never.requests == []
    assert spent() == before
    assert sorted(folder.glob("epoch-1-tool-*-result.json")) == results
    assert battery.view(campaign)["last_refusal"]["code"] == "evaluation_unavailable"


def provider_trouble(battery):
    """Carbon's agent through provider trouble, to the call whose outcome is
    unknown: a reply cut off at the output cap (its finished call runs, the
    cut one is answered `call_truncated`), a 503 retried inside the turn, and
    then a timeout, which interrupts the run for reconciliation."""
    from carbon.development_session.model_provider import ProviderHTTPError
    from carbon.development_session.research_loop import CALL_TRUNCATED
    from carbon.development_session.research_tools import PREFIX

    battery.transport = script = Script(
        reply(
            call("a", PREFIX + "get_challenge_info", {}, status="completed"),
            call("b", *task("practice", strategy=KNN, why="cut off mid-call")),
            status="incomplete",
            reason="max_output_tokens",
            output_tokens=2048,
        ),
        ProviderHTTPError(503, code=None, retry_after=None, usage_reported=False),
        reply(call("c", PREFIX + "get_interaction_manifest", {})),
        TimeoutError("timed out"),
    )
    campaign = battery.launch("e2e-trouble-key-000001", agent="autonomous")
    folder = battery.campaign_root(campaign) / "epoch-1"
    assert len(script.requests) == 4 and not script.items
    # The cut reply: the finished call ran; the cut one did not, and said so.
    answered = outputs(script.requests[1])
    assert answered["a"]["reply"]["status"] == "OK"
    assert answered["b"]["code"] == CALL_TRUNCATED
    assert (folder / "epoch-1-provider-000-truncated.json").exists()
    # The 503 (no usage: rejected before generation) was retried inside the
    # turn, the same request sent again.
    assert battery.waits == [0]
    turn = json.loads((folder / "epoch-1-provider-001-turn.json").read_bytes())
    assert turn["attempts"] == 2 and len(turn["rejections"]) == 1
    assert script.requests[2] == script.requests[1]  # the same request, again
    ledger, owner = battery.ledger(campaign), battery.owner(campaign)
    assert ledger.status(owner=owner)["used"]["research_trials"] == 0
    # The timeout: its outcome is unknown, so nothing is resent on its own.
    view = battery.view(campaign)
    assert view["state"] == "RECONCILIATION_REQUIRED", view["state"]
    assert {"action": "reconcile", "operation": "halt"} in view["recovery"]
    from carbon.development_session.research_agent import uncertain_calls

    (uncertain,) = uncertain_calls(ledger, owner=owner)
    assert uncertain["refusal"] is None
    return campaign, script, uncertain


def new_plan_reservation():
    """What each model call of a new plan on the pinned model reserves: the
    cost of its whole input and its own maximum output, the default output
    cap of a new plan (OWNER-LAUNCHPAD-PROD-02)."""
    from carbon.development_session.model_provider import (
        GPT5_MINI,
        OUTPUT_DEFAULT_V2,
        select,
    )

    return select(
        provider_id="openai-responses",
        model_id=GPT5_MINI,
        credential={"kind": "file", "reference": "unset"},
        output_default=OUTPUT_DEFAULT_V2,
    ).reservation_nano


def finish_after_settlement(battery, campaign, script, uncertain):
    """Resume after the unknown call was settled: the same turn goes out
    again under a fresh identity, and the agent stops; the campaign ends."""
    from carbon.development_session.research_agent import RESERVATION_NANO
    from carbon.development_session.research_agent_policy import STOP

    unknown = script.requests[-1]
    battery.transport = rest = Script(
        reply(
            call(
                "s",
                STOP,
                {
                    "reason": "no_feasible_action",
                    "evidence": "a scripted control-flow test; no result",
                    "used_feedback": False,
                },
            )
        )
    )
    battery.host.control(campaign, "resume")
    battery.join()
    assert rest.requests == [unknown]
    view = battery.view(campaign)
    assert view["state"] == "COMPLETED", view["state"]
    ledger, owner = battery.ledger(campaign), battery.owner(campaign)
    used = ledger.status(owner=owner)["used"]
    # Cut reply, 503 and its retry, the unknown call, its resend.
    assert used["provider_attempts"] == 5
    # Settled at its full reservation: the model's own maximum output, not
    # the historical 2,048-token cap (OWNER-LAUNCHPAD-PROD-02).
    assert (
        used["provider_nanodollars"]
        >= uncertain["booked_on_settlement"]["provider_nanodollars"]
        == new_plan_reservation()
        > RESERVATION_NANO
    )


def test_5_provider_trouble_continues_and_an_unknown_outcome_settles_conservatively(
    battery,
):
    """LP-PROD-A end to end through the Launchpad: the call whose outcome is
    unknown is settled at its full reservation by the settlement entry point,
    run as the reconcile action runs it (the campaign's owner lock and a
    fresh control generation, observed RECONCILING); the Control Center's
    reconcile then finds nothing outstanding, and resume carries the epoch
    on. 5b drives the same settlement through the reconcile action itself."""
    from carbon.development_session.research_agent import (
        settle_uncertain_calls,
        uncertain_calls,
    )
    from carbon.development_session.research_control import CampaignControl
    from scripts.dev.miner_launchpad.controller import owner_lock

    campaign, script, uncertain = provider_trouble(battery)
    ledger, owner = battery.ledger(campaign), battery.owner(campaign)
    with owner_lock(battery.campaign_root(campaign)):
        ledger.generation = CampaignControl(ledger).acquire()
        settled = settle_uncertain_calls(ledger, owner=owner)
    assert settled["refused"] == []
    (settlement,) = settled["settled"]
    assert settlement["identity"] == uncertain["identity"]
    assert settlement["booked"] == uncertain["booked_on_settlement"]
    assert settlement["caveat"] is None  # answered by the selected model
    assert settlement["retry_dispatched"] is False
    assert uncertain_calls(ledger, owner=owner) == []
    reconciled = battery.host.control(campaign, "reconcile")
    assert reconciled["state"] != "RECONCILIATION_REQUIRED", reconciled["state"]
    finish_after_settlement(battery, campaign, script, uncertain)


def test_5b_the_reconcile_action_settles_an_unknown_model_call(battery):
    """The miner's Reconcile (Control Center or `carbon_halt action=reconcile`)
    is the only entry point a miner has: it must settle the unknown call
    (LP-PROD-A handoff to LP-PROD-C), not leave the campaign awaiting
    reconciliation forever."""
    from carbon.development_session.research_agent import uncertain_calls

    campaign, script, uncertain = provider_trouble(battery)
    reconciled = battery.host.control(campaign, "reconcile")
    ledger, owner = battery.ledger(campaign), battery.owner(campaign)
    assert uncertain_calls(ledger, owner=owner) == []
    assert reconciled["state"] != "RECONCILIATION_REQUIRED", reconciled["state"]
    finish_after_settlement(battery, campaign, script, uncertain)


def practised_and_frozen(battery):
    """A miner's own battery campaign (no agent): practised, then frozen."""
    campaign = battery.launch("e2e-miner-key-00000001")
    assert battery.view(campaign)["state"] == "READY"
    battery.perform(
        "practice",
        {
            "campaign": campaign,
            "strategy": KNN,
            "hypothesis": "Neighbours interpolate the smooth map",
            "idempotency_key": "e2e-practice-key-00001",
        },
    )
    battery.join()
    view = battery.view(campaign)
    assert view["completed_experiments"] == 1, view.get("last_refusal")
    battery.perform(
        "freeze_candidate",
        {"campaign": campaign, "strategy": KNN, "reason": "practised"},
    )
    battery.join()
    view = battery.view(campaign)
    assert view["journey"]["frozen_awaiting_submission"] is True, view["last_refusal"]
    return campaign


def test_6a_a_submit_with_no_validator_is_refused_at_once_at_both_doors(battery):
    """No validator deployment or intake for the Challenge: the submit is
    refused at once with its next step at the browser's door and at the MCP
    door, nothing is recorded, and the frozen candidate is kept - never
    "Submitted" (LP-PROD-C D11, B's door)."""
    from mcp import Client

    from carbon.development_session.chain_onboarding import carbon_testnet_context
    from carbon.miner_mcp.mcp_operations import make_operation_tools
    from carbon.miner_mcp.open_tier import create_open_tier_server
    from scripts.dev.miner_launchpad import supervisor as supervision

    campaign = practised_and_frozen(battery)
    submit = {"campaign": campaign, "idempotency_key": "e2e-submit-key-000001"}
    server, token = battery.http()
    status, body = post(server, token, "/api/v1/operations/submit", submit)
    assert (status, body["error"]) == (409, "evaluation_unavailable")
    assert body["next_step"] == supervision.NEXT_ACTIONS["evaluation_unavailable"]
    view = battery.view(campaign)
    assert view["in_flight"] is None and view["last_refusal"] is None
    assert view["journey"]["submitted_epochs"] == []
    assert view["journey"]["frozen_awaiting_submission"] is True
    door = create_open_tier_server(
        reader=Registered(), context=carbon_testnet_context()
    )
    for tool in make_operation_tools(battery.host):
        door._tool_manager._tools[tool.name] = tool

    async def through_mcp():
        async with Client(door, mode="legacy") as session:
            return await session.call_tool("carbon_submit", submit)

    refused = refusal_of(asyncio.run(through_mcp()))
    assert refused["error"] == "evaluation_unavailable"
    # One next step for one code, whichever door the miner uses.
    assert refused["next_step"] == supervision.NEXT_ACTIONS["evaluation_unavailable"]


@pytest.fixture
def intake_battery(tmp_path, monkeypatch):
    """The battery host whose campaigns sign intake submissions with the
    intake tests' development key (`test_battery_intake.MINER`)."""
    from test_battery_intake import MINER, signed

    from carbon.battery import deployment
    from carbon.battery import intake as ib
    from carbon.battery import remote_submission as rs

    class Roomy(ib.PeerLimits):
        # Every request here comes from one loopback peer.
        def __init__(self):
            super().__init__(burst=500, rate=100.0)

    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    monkeypatch.setattr(ib, "PeerLimits", Roomy)
    # The miner's signer, as a fixture: the test key signs in test code.
    monkeypatch.setattr(rs, "_signed", lambda signer, facts, body: signed(signer, body))
    monkeypatch.setattr(rs, "POLL_S", 0.3)
    launchpad = BatteryLaunchpad(tmp_path, monkeypatch, miner_key=MINER)
    yield launchpad
    launchpad.close()


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_6b_a_submit_shows_a_closed_refusal_then_the_validators_outcome(
    intake_battery, tmp_path, refs
):
    """Through the Control Center's HTTP door: an intake that cannot be
    reached is a closed refusal on the campaign with its next step, and the
    candidate is kept; through a loopback intake to a throwaway validator the
    submission is scored and the outcome is what the campaign shows. A
    submit is never shown as submitted before a verdict."""
    from test_battery_intake_service_e2e import made_here, open_pool, serving

    from carbon.battery import intake as ib
    from scripts.dev.miner_launchpad import supervisor as supervision

    battery = intake_battery
    campaign = practised_and_frozen(battery)
    server, token = battery.http()
    battery.cfg = {
        **battery.cfg,
        "intakes": {BATTERY: f"http://127.0.0.1:{free_port()}"},
    }
    status, body = post(
        server,
        token,
        "/api/v1/operations/submit",
        {"campaign": campaign, "idempotency_key": "e2e-submit-key-000001"},
    )
    assert status == 200, body
    battery.join()
    view = battery.view(campaign)
    refused = view["last_refusal"]
    assert (refused["code"], refused["operation"]) == ("intake_unreachable", "submit")
    assert refused["next_action"] == supervision.NEXT_ACTIONS["intake_unreachable"]
    assert view["journey"]["submitted_epochs"] == []
    assert view["journey"]["frozen_awaiting_submission"] is True
    assert view["final_results"] == []
    stage = submit_stage(battery, campaign)
    assert stage["detail"].startswith("Not submitted")
    assert stage["refusal"]["code"] == "intake_unreachable"
    made = made_here(tmp_path / "validator-service")
    open_pool(made, refs)
    with serving(made) as live:
        battery.cfg = {**battery.cfg, "intakes": {BATTERY: live.url}}
        status, body = post(
            server,
            token,
            "/api/v1/operations/submit",
            {"campaign": campaign, "idempotency_key": "e2e-submit-key-000002"},
        )
        assert status == 200, body
        battery.join()
        inbox = ib.Inbox(live.config["inbox"]).counts()
    view = battery.view(campaign)
    assert view["last_refusal"] is None, view["last_refusal"]
    assert view["journey"]["submitted_epochs"] == [1]
    (shown,) = view["final_results"]
    assert shown["status"] == "VALIDATOR_OUTCOME"
    assert shown["result"]["state"] == "SCORED"
    assert shown["result"]["qualification"] is False
    assert shown["result"]["reward"] is False
    assert inbox == {"RECEIVED": 0, "ADMITTED": 1, "REFUSED": 0}
    stage = submit_stage(battery, campaign)
    assert stage["detail"].startswith("1 DEVELOPMENT outcome")
    assert "refusal" not in stage


def submit_stage(battery, campaign):
    """The DEVELOPMENT submit stage of the campaign view the miner reads."""
    document = battery.perform("campaign_view", {"campaign": campaign})
    return {stage["id"]: stage for stage in document["stages"]}["submit"]


@contextlib.contextmanager
def not_an_intake():
    """A loopback HTTP server that answers, but is not a battery intake."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"schema": "not-a-battery-intake"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(10)


def test_6c_an_intake_refusal_reaches_the_miner_with_its_own_next_step(
    intake_battery,
):
    """An address that answers but is not a battery intake: nothing is sent
    for evaluation, the candidate is kept, and the miner is told what to do
    about this refusal - not the catalog's generic fallback (LP-PROD-G's
    closed intake codes, as the campaign reports them, LP-PROD-C)."""
    from carbon.battery import campaign as battery_campaign
    from scripts.dev.miner_launchpad import supervisor as supervision

    battery = intake_battery
    campaign = practised_and_frozen(battery)
    with not_an_intake() as url:
        battery.cfg = {**battery.cfg, "intakes": {BATTERY: url}}
        battery.perform(
            "submit", {"campaign": campaign, "idempotency_key": "e2e-submit-key-000001"}
        )
        battery.join()
    view = battery.view(campaign)
    refused = view["last_refusal"]
    assert (refused["code"], refused["operation"]) == ("intake_mismatch", "submit")
    assert battery_campaign.intake_outcome(refused["code"]) == "REFUSED"
    assert view["journey"]["submitted_epochs"] == []
    assert view["journey"]["frozen_awaiting_submission"] is True
    assert refused["next_action"] != supervision.FALLBACK_ACTION


class CommitmentStandIn:
    """NON-PRODUCTION stand-in for the validator's chain commitment reader
    (`chain.commitments.ChainCommitmentReader`): it reads what this test
    commits, at a fixed block, and lists that hotkey as the digest's only
    holder. No chain is read. The real commitment is the miner's own,
    signed at their signer (LAUNCHPAD-ACCEPT-02); here the test drives the
    stand-in so the commitment matches."""

    BLOCK = 40

    def __init__(self):
        self.committed = {}

    def read(self, hotkey):
        digest = self.committed.get(hotkey)
        return None if digest is None else {"digest": digest, "block": self.BLOCK}

    def holders(self, digest):
        return [(h, self.BLOCK) for h, d in self.committed.items() if d == digest]


def through_both_doors(battery, server, token, campaign):
    """`observe` and `campaign_view` as the browser's door and an MCP client
    each read them."""
    from mcp import Client

    from carbon.development_session.chain_onboarding import carbon_testnet_context
    from carbon.miner_mcp.mcp_operations import make_operation_tools
    from carbon.miner_mcp.open_tier import create_open_tier_server

    browser = {}
    for operation in ("observe", "campaign_view"):
        status, body = post(
            server, token, "/api/v1/operations/" + operation, {"campaign": campaign}
        )
        assert status == 200, body
        browser[operation] = body
    door = create_open_tier_server(
        reader=Registered(), context=carbon_testnet_context()
    )
    for tool in make_operation_tools(battery.host):
        door._tool_manager._tools[tool.name] = tool

    async def read():
        found = {}
        async with Client(door, mode="legacy") as session:
            for operation in ("observe", "campaign_view"):
                result = await session.call_tool(
                    "carbon_" + operation, {"campaign": campaign}
                )
                assert not result.is_error, result
                found[operation] = result.structured_content["payload"]
        return found

    return browser, asyncio.run(read())


def test_6d_a_loopback_intake_requiring_a_commitment_reaches_a_sealed_verdict(
    intake_battery, tmp_path, refs, monkeypatch
):
    """LAUNCHPAD-ACCEPT-04, engineering evidence only (the acceptance is the
    plan's A5): a validator served on loopback, as the tunnel presents
    valV2, with `require_commitment: true` and a commitment-reader stand-in,
    under the sealed rule (v2). Its public facts are read as Review reads
    them; a wrong pinned receiver sends nothing; submit before the
    commitment is refused, REFUSED, at both doors; once committed, the
    submission is scored and both doors read back the same submission id
    and sealed public outcome, never a hidden score, case or seed."""
    from test_battery_intake import MINER, VALIDATOR
    from test_battery_intake_service_e2e import open_pool, serving
    from test_battery_validator_service import throwaway

    from carbon.battery import deployment
    from carbon.battery import intake as ib
    from carbon.battery.compile import compile_recipe
    from carbon.battery.daemon import commitment_digest
    from carbon.challenge_registry.campaigns import campaign_for_id
    from scripts.dev.miner_launchpad import supervisor as supervision

    battery = intake_battery
    campaign = practised_and_frozen(battery)
    chain = CommitmentStandIn()
    monkeypatch.setattr(deployment, "_commitment_reader", lambda config: chain)
    made = throwaway(
        tmp_path / "validator-service",
        port=free_port(),
        deployment_changes={"require_commitment": True, "rule": "v2"},
        intake_changes={"receiver": VALIDATOR.ss58_address},
    )
    open_pool(made, refs)
    server, token = battery.http()
    root = battery.campaign_root(campaign)
    frozen = json.loads((root / "epoch-1" / "selected-recipe.json").read_bytes())
    manifest = json.loads((root / "campaign-manifest.json").read_bytes())
    contract = frozen.get("contract_digest") or manifest["contract_digest"]
    _, recipe = compile_recipe(frozen["strategy"])
    expected = commitment_digest(BATTERY, contract, recipe.strategy_hash)

    def submit(key):
        status, body = post(
            server,
            token,
            "/api/v1/operations/submit",
            {"campaign": campaign, "idempotency_key": key},
        )
        assert status == 200, body
        battery.join()
        return battery.view(campaign)

    # A chain that advances a block on each read, as a live one does
    # (`AdvancingChain`): this journey outlasts the intake's 12 s refresh.
    with serving(made, chain=AdvancingChain()) as live:
        # Review's preflight of a loopback intake: the public facts name
        # Carbon's testnet, subnet 567, this Challenge and the receiver.
        facts = campaign_for_id(BATTERY).intake_check(live.url)
        assert (facts["network"], facts["netuid"]) == ("testnet", 567)
        assert facts["challenge"]["id"] == BATTERY
        assert facts["receiver"] == VALIDATOR.ss58_address
        # A receiver pinned for another validator: nothing signed or sent.
        battery.cfg = {
            **battery.cfg,
            "intakes": {BATTERY: live.url},
            "receivers": {BATTERY: MINER.ss58_address},
        }
        view = submit("e2e-submit-key-000001")
        refused = view["last_refusal"]
        assert (refused["code"], refused["intake_outcome"]) == (
            "intake_receiver_mismatch",
            "REFUSED",
        )
        assert ib.Inbox(live.config["inbox"]).counts() == {
            "RECEIVED": 0,
            "ADMITTED": 0,
            "REFUSED": 0,
        }
        # The pinned receiver, before the commitment: refused at admission.
        battery.cfg = {**battery.cfg, "receivers": {BATTERY: VALIDATOR.ss58_address}}
        view = submit("e2e-submit-key-000002")
        refused = view["last_refusal"]
        assert (refused["code"], refused["operation"]) == (
            "commitment_required",
            "submit",
        )
        assert refused["intake_outcome"] == "REFUSED"
        assert refused["next_action"] == supervision.NEXT_ACTIONS["commitment_required"]
        assert view["journey"]["frozen_awaiting_submission"] is True
        browser, mcp = through_both_doors(battery, server, token, campaign)
        for door in (browser, mcp):
            assert door["observe"]["last_refusal"] == refused
            stage = {s["id"]: s for s in door["campaign_view"]["stages"]}["submit"]
            assert stage["refusal"]["intake_outcome"] == "REFUSED"
        # Committed (the stand-in reads it): the same candidate, a verdict.
        chain.committed[MINER.ss58_address] = expected
        view = submit("e2e-submit-key-000003")
        inbox = ib.Inbox(live.config["inbox"]).counts()
    assert view["last_refusal"] is None, view["last_refusal"]
    assert view["journey"]["submitted_epochs"] == [1]
    assert inbox["ADMITTED"] == 1
    browser, mcp = through_both_doors(battery, server, token, campaign)
    for door in (browser, mcp):
        (shown,) = door["observe"]["final_results"]
        result = shown["result"]
        assert result["state"] == "SCORED"
        assert result["sealed"] is True and result["screening"] is None
        assert result["submission_id"]
        assert result["contract_digest"] == contract
        assert result["recipe_digest"].startswith("sha256:")
        assert (result["qualification"], result["reward"]) == (False, False)
        (outcome,) = door["campaign_view"]["outcomes"]
        assert outcome["result"]["submission_id"] == result["submission_id"]
        assert outcome["result"]["sealed"] is True
        assert "screening" not in outcome["result"]
        text = json.dumps(
            [door["observe"]["final_results"], door["campaign_view"]["outcomes"]]
        )
        for hidden in ("important_score", '"score"', "seed", "pool_version"):
            assert hidden not in text, hidden
    assert browser["observe"]["final_results"] == mcp["observe"]["final_results"]
    assert browser["campaign_view"]["outcomes"] == mcp["campaign_view"]["outcomes"]


# --- 7. closing pauses; restarting flags nothing; resume survives ------------


def start_control_center(root, processes, variant=None):
    proc = spawn(root, "control-center", variant)
    processes.append(proc)
    wait_for(
        lambda: pids(root, "control-center") and lock_held(root), "a Control Center"
    )
    return proc


def close_control_center(root, proc):
    proc.send_signal(signal.SIGTERM)
    assert proc.wait(60) == 0
    assert (root / f"control-center-closed-{proc.pid}").exists()


def test_7_closing_pauses_restarting_flags_nothing_and_resume_survives(
    tmp_path, processes
):
    """Three processes, as on a miner's machine: the Control Center (the
    supervisor), the miner's MCP client and, later, a restarted Control
    Center. Closing the client changes nothing; closing the Control Center
    pauses Carbon's running agent (reversible) and leaves an idle campaign
    READY; a restart flags neither; a profile change the campaign was not
    frozen with does not orphan it, while one it was frozen with is named."""
    root = shared_root(tmp_path)
    first = start_control_center(root, processes)

    async def launch_both():
        async with client(root) as session:
            idle = await session.call_tool(
                "carbon_launch", launch_body("e2e-idle-key-000000001")
            )
            # Carbon's agent for a new launch: Graphite (OWNER-GRAPHITE-
            # MINER-01), on the lifecycle fixtures (`agent_fixtures`).
            busy = await session.call_tool(
                "carbon_launch",
                {
                    **launch_body("e2e-agent-key-00000001", agent="graphite"),
                    "graphite_mode": "BUILD",
                },
            )
            for result in (idle, busy):
                assert not result.is_error, result.content
            idle = idle.structured_content["payload"]["id"]
            busy = busy.structured_content["payload"]["id"]
            await observe(session, idle, lambda v: v["state"] == "READY", "READY")
            await asyncio.to_thread(
                wait_for, lambda: first.pid in agent_runs(root), "Carbon's agent"
            )
            return idle, busy

    idle, busy = asyncio.run(launch_both())
    # The client closed: nothing it launched was paused or stopped.
    assert ledger_status(root, busy)[0] == "RUN"
    close_control_center(root, first)
    assert ledger_status(root, busy) == ("PAUSE", "PAUSED")
    assert ledger_status(root, idle)[1] == "READY"

    def looked_at(*campaigns, variant=None):
        async def look():
            async with client(root, variant=variant) as session:
                views = []
                for campaign in campaigns:
                    result = await session.call_tool(
                        "carbon_observe", {"campaign": campaign}
                    )
                    assert not result.is_error, result.content
                    views.append(result.structured_content["payload"])
                return views

        return asyncio.run(look())

    paused, ready = looked_at(busy, idle)
    assert paused["state"] == "PAUSED"  # never STOPPED
    refusal = paused["last_refusal"]
    assert (refusal["code"], refusal["kind"]) == (
        "paused_when_supervisor_closed",
        "paused",
    )
    assert paused["recovery"] == [
        {"action": "resume", "operation": "resume"},
        {"action": "stop", "operation": "halt"},
    ]
    assert ready["state"] == "READY" and ready["last_refusal"] is None
    # A restart recovers what the closed process left, and flags nothing idle.
    second = start_control_center(root, processes)
    time.sleep(1.0)  # several supervisor passes
    paused, ready = looked_at(busy, idle)
    assert ready["state"] == "READY" and ready["last_refusal"] is None
    assert paused["state"] == "PAUSED"
    assert paused["last_refusal"]["code"] == "paused_when_supervisor_closed"
    close_control_center(root, second)
    # So does a campaign host restarted in-process (INLINE, which recovers
    # as it starts: the browser smoke's host).
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    inline = RunnerAdapter(root / "runner.sqlite3", principal=PRINCIPAL)
    try:
        assert inline.get(idle)["state"] == "READY"
        assert inline.get(idle)["last_refusal"] is None
        assert inline.get(busy)["state"] == "PAUSED"
    finally:
        inline.close()
    # A change the campaign was frozen with is named, and changes nothing ...

    async def resume(variant):
        async with client(root, variant=variant) as session:
            return await session.call_tool("carbon_resume", {"campaign": busy})

    refused = refusal_of(asyncio.run(resume("revision")))
    assert refused["error"] == "profile_changed_since_launch"
    assert ledger_status(root, busy) == ("PAUSE", "PAUSED")
    # ... and one it was not frozen with resumes it, carried out by the
    # restarted Control Center under the changed profile.
    third = start_control_center(root, processes, "unrelated")
    resumed = asyncio.run(resume("unrelated"))
    assert not resumed.is_error, resumed.content
    wait_for(lambda: third.pid in agent_runs(root), "the agent to carry on")
    (root / "release-agent").touch()
    wait_for(
        lambda: ledger_status(root, busy)[1] == "COMPLETED",
        "the resumed campaign to complete",
        90,
    )
    (done,) = looked_at(busy, variant="unrelated")
    assert done["state"] == "COMPLETED" and done["last_refusal"] is None
    assert agent_runs(root) == [first.pid, third.pid]
    close_control_center(root, third)


# --- 8. Graphite, the agent miners run ----------------------------------------
#
# Real: everything stages 4 to 6 use, and Graphite's miner edition - its
# driver, roles, toolbox, library, hunt and plan rule (S1 to S3) - over the
# Launchpad's launch fields and library operations (S4). DEVELOPMENT
# FIXTURES, by name: the miner's model (`GraphiteModel`, answering each role
# from its script), arXiv (`FakeArxiv`, a fixed Atom feed on no network) and
# the clock, injected through `driver.run`'s own parameters.

#: Graphite's Planner finish tool (S3's manifest).
PLAN_TOOL = "graphite_record_plan"
#: A paper the shared pack does not hold: what a hunt reads.
NEW_PAPER = {
    "arxiv_id": "2609.99901v1",
    "title": "Neighbourhood surrogates for fast-charge ageing",
    "abstract": (
        "We fit k-nearest-neighbour surrogates to fast-charge protocols and "
        "report lower interpolation error on held-out cells."
    ),
}


def atom(papers):
    """An arXiv Atom page holding `papers` (arxiv_id, title, abstract)."""
    entries = "".join(
        "<entry>"
        f"<id>http://arxiv.org/abs/{p['arxiv_id']}</id>"
        f"<title>{p['title']}</title><summary>{p['abstract']}</summary>"
        "<author><name>A. Author</name></author>"
        '<category term="cs.LG"/><arxiv:primary_category term="cs.LG"/>'
        "<published>2026-09-01T00:00:00Z</published>"
        "<updated>2026-09-01T00:00:00Z</updated>"
        "</entry>"
        for p in papers
    )
    return (
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:arxiv="http://arxiv.org/schemas/atom" '
        'xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">'
        f"<opensearch:totalResults>{len(papers)}</opensearch:totalResults>"
        f"{entries}</feed>"
    ).encode()


class FakeArxiv:
    """DEVELOPMENT FIXTURE: arXiv's API on no network - every query answers
    the same page; each request is kept."""

    def __init__(self, papers):
        self.body, self.requests = atom(papers), []

    def __call__(self, request, timeout=None):
        self.requests.append(getattr(request, "full_url", request))
        body = self.body

        class Response:
            status = 200

            def read(self):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        return Response()


def message(value):
    """A closed call's reply: one JSON document as output text."""
    body = reply()
    body["output"] = [
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": json.dumps(value)}],
        }
    ]
    return body


#: The Reader's extraction of `NEW_PAPER` (method_cards.EXTRACTED_FIELDS).
EXTRACTION = {
    "relevant": True,
    "method_name": "kNN surrogate",
    "family": "reduced-order model",
    "construction_claims": ["neighbours interpolate protocol space"],
    "required_inputs": ["cycling data"],
    "reported_evidence": ["lower interpolation error"],
    "data_regime": "small data",
    "cost": "not stated",
    "code_available": False,
    "applicability": "battery fast-charge surrogate",
}


#: The model's own summary when the engine asks it to compact its context
#: (S1's `COMPACTION_FIELDS`, every field text).
COMPACTION_SUMMARY = {
    "findings": "lit_card found no card under the id tried; nothing practised yet",
    "open_hypotheses": "neighbours interpolate the protocol-to-ageing map",
    "best_recipes": json.dumps(KNN),
    "constraints": "select only a practised recipe",
    "next_steps": "practise the kNN recipe",
}


def compaction_asked(request):
    """Whether the engine's last note asks for a compaction (S1's
    `COMPACTION_V1`): its compaction request ends with that user note."""
    items = request.get("input") or []
    last = items[-1] if items else {}
    content = last.get("content") if type(last) is dict else None
    return (
        type(last) is dict
        and last.get("role") == "user"
        and type(content) is str
        and content.startswith(("Carbon context compaction", "Carbon: no valid"))
    )


class GraphiteModel:
    """DEVELOPMENT FIXTURE: the miner's model, scripted by role. Each request
    is kept as sent. A closed call (no tools) is the Reader's, answered with
    the extraction; a compaction request (the engine's note asking for one)
    is answered with `COMPACTION_SUMMARY`; a Planner turn (its finish tool is
    offered) or a Constructor turn (SELECT is offered) by that role's script,
    in order. A script item is a reply, a callable of the request, or an
    exception the transport raises."""

    def __init__(self, *, planner=(), constructor=()):
        self.scripts = {"planner": list(planner), "constructor": list(constructor)}
        self.requests = {
            "closed": [],
            "compaction": [],
            "planner": [],
            "constructor": [],
        }
        #: What a scripted reply raised: the provider layer settles it as an
        #: unknown outcome, so a test shows it here rather than guessing.
        self.errors = []

    def __call__(self, request):
        from carbon.development_session.profile import canonical
        from carbon.development_session.research_agent_policy import COMPACT
        from carbon.development_session.research_loop import SELECT

        kept = json.loads(canonical(request))
        names = {t.get("name") for t in request.get("tools") or [] if type(t) is dict}
        if not names:
            self.requests["closed"].append(kept)
            return message(EXTRACTION)
        if COMPACT in names and compaction_asked(request):
            self.requests["compaction"].append(kept)
            return reply(call("compact", COMPACT, COMPACTION_SUMMARY))
        role = "planner" if PLAN_TOOL in names else "constructor"
        assert role == "planner" or SELECT in names, sorted(names)
        self.requests[role].append(kept)
        script = self.scripts[role]
        assert script, "the scripted " + role + " has no more replies"
        item = script.pop(0)
        if isinstance(item, BaseException):
            raise item
        if not callable(item):
            return item
        try:
            return item(kept)
        except Exception as failure:
            self.errors.append(role + ": " + repr(failure))
            raise

    @property
    def reader_calls(self):
        """The Reader's calls: the closed calls (no tools). A test also counts
        them by the ledger identity S3 meters them under (`graphite-reader-*`)."""
        return list(self.requests["closed"])


def nothing_called(model):
    """Whether the scripted model was asked nothing at all."""
    return not any(model.requests.values())


def cards_answered(request):
    """Every card a tool answer in `request` carried, by id."""
    found = {}
    for answer in outputs(request).values():
        stack = [answer]
        while stack:
            value = stack.pop()
            if type(value) is dict:
                if type(value.get("card_id")) is str and "origin" in value:
                    found[value["card_id"]] = value
                stack.extend(value.values())
            elif type(value) is list:
                stack.extend(value)
    return found


def miner_card(request):
    """The miner's own hunted card among the answers in `request`."""
    (card,) = [
        c for c in cards_answered(request).values() if c["origin"] == "miner_hunt"
    ]
    assert card["check_status"] == "UNCHECKED"
    return card


def plan_citing(card, *, recipe=None):
    """The Planner's `graphite_record_plan` arguments (S3's finish tool)."""
    return {
        "hypotheses": [
            {
                "hypothesis": "Neighbours interpolate the protocol-to-ageing map",
                "expected_effect": "lower practice error than the control",
                "stopping_rule": "stop after two practices without improvement",
                "recipe_json": None if recipe is None else json.dumps(recipe),
                "cites": [{"card_id": card["card_id"], "origin": card["origin"]}],
            }
        ],
        "pins_considered": [],
    }


#: A capability request the Planner files for a family the contract lacks
#: (`research_workspace.CAPABILITY_FIELDS`).
GP_REQUEST = {
    "purpose": "Practise a Gaussian-process surrogate family on battery",
    "operation": "add a Gaussian-process model family to the research tools",
    "hypothesis": "a GP interpolates sparse protocols with calibrated error",
    "public_evidence": "the public discovery document lists no GP family",
    "reason": "missing_adapter",
    "expected_benefit": "a comparison point for the neighbour surrogate",
    "estimated_cost": "one adapter, CPU only",
    "minimal_safe_design": "the existing practice runner with one new family",
    "verification": "practice on the public cases",
}


class GraphiteLaunchpad(BatteryLaunchpad):
    """A miner's Control Center host running Graphite's miner edition on
    battery: `BatteryLaunchpad` with the miner's library in their setup root,
    and `driver.run` given the scripted model, arXiv and clock through its
    own parameters (nothing else of the driver is replaced)."""

    def __init__(self, tmp_path, monkeypatch, *, miner_key=None):
        driver = pytest.importorskip("carbon.agent_campaign.graphite.miner.driver")
        from carbon.development_session import product_campaign

        assert "graphite" in product_campaign.AGENTS
        super().__init__(tmp_path, monkeypatch, miner_key=miner_key)
        (self.root / "setup").mkdir(mode=0o700)
        self.host.library_root = self.root / "setup" / "graphite-library"
        self.model, self.arxiv = GraphiteModel(), FakeArxiv([])
        self.now = itertools.count(1_790_000_000)
        real = driver.run

        async def run(prepared, *, transport=None, arxiv_opener=None, clock=None):
            return await real(
                prepared,
                transport=self.model,
                arxiv_opener=self.arxiv,
                clock=lambda: float(next(self.now)),
            )

        monkeypatch.setattr(driver, "run", run)

    def launch_graphite(self, key, *, attempts=24, epochs=None, **fields):
        """A Graphite launch through the shared operation, on the miner's
        own ceilings: `attempts` provider attempts (and the money for that
        many calls' reservations, `graphite_call_reservation`), four practice
        trials and, when given, `epochs` committed final epochs."""
        from carbon.battery.challenge import CHALLENGE

        ceilings = {
            "provider_attempts": attempts,
            "provider_nanodollars": attempts * graphite_call_reservation(),
            "research_trials": 4,
            **({} if epochs is None else {"epochs": epochs}),
        }
        body = {
            "challenge": CHALLENGE.challenge_id,
            "challenge_version": CHALLENGE.version,
            "agent": "graphite",
            "idempotency_key": key,
            "budget": {"ceilings": ceilings},
            **fields,
        }
        campaign = self.perform("launch", body)["id"]
        self.join()
        return campaign

    def graphite_view(self, campaign):
        return self.perform("campaign_view", {"campaign": campaign})["graphite"]


def graphite_call_reservation():
    """What each model call of a new Graphite plan on the pinned model
    reserves before it is sent. Where new plans default the agent's output
    cap to the model's own maximum (`model_provider.OUTPUT_DEFAULT_V2`,
    OWNER-LAUNCHPAD-PROD-02), that is the cost of its whole input and that
    full output; before that rule, the historical 2,048-token reservation.
    A research share is a share of money too, so a launch whose share holds
    less than one reservation makes no research call at all."""
    from carbon.development_session import model_provider
    from carbon.development_session.research_agent import RESERVATION_NANO

    rule = getattr(model_provider, "OUTPUT_DEFAULT_V2", None)
    if rule is None:
        return RESERVATION_NANO
    return model_provider.select(
        provider_id="openai-responses",
        model_id=model_provider.GPT5_MINI,
        credential={"kind": "file", "reference": "unset"},
        output_default=rule,
    ).reservation_nano


def shared_pack():
    """The card pack Carbon ships (S2's `pack.load_shared_pack`). Read by
    module path rather than by an import statement, so the import order this
    file is checked against is the same with or without S2's package."""
    return pytest.importorskip(
        "carbon.agent_campaign.graphite.miner.pack"
    ).load_shared_pack()


@pytest.fixture
def graphite(tmp_path, monkeypatch):
    launchpad = GraphiteLaunchpad(tmp_path, monkeypatch)
    yield launchpad
    launchpad.close()


def pack_paper():
    """A paper the shared pack already holds, as arXiv would list it again
    (a later version): the hunt must not pay to read it twice."""
    card_id = shared_pack().cards[0]["card_id"]
    arxiv_id = card_id.removeprefix("arxiv-").rsplit("v", 1)[0]
    return {
        "arxiv_id": arxiv_id + "v9",
        "title": "A paper the pack already holds",
        "abstract": "Already read once; its card ships with Carbon.",
    }


def researched(graphite):
    """8a: a RESEARCH campaign - hunt, read, plan - and what it left."""
    graphite.arxiv = FakeArxiv([pack_paper(), NEW_PAPER])
    graphite.model = GraphiteModel(
        planner=[
            # One parallel turn: the literature, a design check and a
            # capability request, answered in the model's order.
            reply(
                call("a", "lit_search", {"query": "neighbour surrogate fast charge"}),
                call(
                    "b",
                    *task(
                        "workspace",
                        action="check_design",
                        arguments={"strategy": KNN},
                        why="Is the cited recipe rebuildable?",
                    ),
                ),
                call(
                    "c",
                    *task(
                        "workspace",
                        action="capability_request",
                        arguments={"request": GP_REQUEST},
                        why="A family the contract lacks",
                    ),
                ),
            ),
            lambda request: reply(
                call("d", PLAN_TOOL, plan_citing(miner_card(request), recipe=KNN))
            ),
        ]
    )
    campaign = graphite.launch_graphite(
        "e2e-graphite-research-01",
        graphite_mode="RESEARCH",
        hunt={"queries": ["neighbour surrogate"], "max_records": 2},
    )
    return campaign


def test_8a_a_research_campaign_hunts_reads_once_and_plans(graphite):
    campaign = researched(graphite)
    model = graphite.model
    # The hunt asked arXiv (on no network).
    assert graphite.arxiv.requests, graphite.view(campaign)["last_refusal"]
    # The paper the pack holds was never read again: one Reader call, metered
    # under S3's Reader identity, for the new paper only.
    ledger, owner = graphite.ledger(campaign), graphite.owner(campaign)
    operations = ledger.status(owner=owner)["operations"]
    read = [op["id"] for op in operations if op["id"].startswith("graphite-reader-")]
    assert len(read) == 1 and len(model.reader_calls) == 1, model.errors
    assert NEW_PAPER["title"] in json.dumps(model.reader_calls[0])
    # The parallel turn ran in the model's order: the literature, a design
    # check and a capability request, each answered.
    answered = outputs(model.requests["planner"][1])
    assert list(answered) == ["a", "b", "c"]
    assert answered["c"]["terminal_task"]["state"] == "SUCCEEDED", answered["c"]
    # The plan cites the miner's own card, and is in their library.
    plans = graphite.perform("plan_list", {})["plans"]
    assert [p["created_by"] for p in plans] == ["planner"], (
        model.errors,
        outputs(model.requests["planner"][-1]).get("d"),
    )
    plan = graphite.perform("plan_get", {"plan": plans[0]["digest"]})["plan"]
    (cited,) = plan["hypotheses"][0]["cites"]
    assert cited["origin"] == "miner_hunt"
    card = graphite.perform("library_card", {"card_id": cited["card_id"]})["card"]
    assert (card["origin"], card["check_status"]) == ("miner_hunt", "UNCHECKED")
    # Research only: nothing practised, selected or submitted; complete.
    assert ledger.status(owner=owner)["used"]["research_trials"] == 0
    root = graphite.campaign_root(campaign)
    assert not list(root.glob("epoch-*/selected-recipe.json"))
    view = graphite.view(campaign)
    assert view["state"] == "COMPLETED", view["last_refusal"]
    assert view["journey"]["submitted_epochs"] == []
    # The view shows the plan this campaign's Planner wrote, its stages and
    # what its research spent: the Reader's call and the Planner's two.
    shown = graphite.graphite_view(campaign)
    assert shown["mode"] == "RESEARCH" and shown["stage"] == "complete"
    assert shown["plan_digest"] == plans[0]["digest"]
    assert [(s["stage"], s["state"]) for s in shown["stages"]] == [
        ("hunt", "DONE"),
        ("plan", "DONE"),
    ]
    assert (shown["hunt"]["deduped"], shown["hunt"]["extracted"]) == (1, 1)
    assert shown["hunt"]["reader_calls"] == 1
    assert shown["research_spent"]["provider_attempts"] == 3


def edited(graphite):
    """8b: the miner curates through both doors; returns the edited plan."""
    from mcp.server.mcpserver.exceptions import ToolError

    from carbon.miner_mcp.mcp_operations import make_operation_tools

    researched(graphite)
    plan_digest = graphite.perform("plan_list", {})["plans"][0]["digest"]
    plan = graphite.perform("plan_get", {"plan": plan_digest})["plan"]
    pinned, banned = (c["card_id"] for c in shared_pack().cards[1:3])
    server, token = graphite.http()
    # The browser's door pins; the MCP door bans; both are one table.
    status, body = post(server, token, "/api/v1/library/pin", {"card_id": pinned})
    assert status == 200 and pinned in body["curation"]["pins"]
    tools = {t.name: t for t in make_operation_tools(graphite.host)}
    result = asyncio.run(tools["carbon_library_ban"].fn(card_id=banned))
    assert banned in result.payload["curation"]["bans"]
    # A banned card is never served, at either door.
    status, body = post(server, token, "/api/v1/library/card", {"card_id": banned})
    assert (status, body["error"]) == (409, "card_banned")
    with pytest.raises(ToolError, match="card_banned"):
        asyncio.run(tools["carbon_library_card"].fn(card_id=banned))
    found = graphite.perform(
        "library_search", {"query": "surrogate", "challenge": BATTERY, "card_limit": 50}
    )
    assert banned not in {c["card_id"] for c in found["cards"]}
    # The miner's edit, in the stored plan's own shape (as plan_get gave it):
    # the pin considered, and a second ranked hypothesis citing it.
    document = {
        **plan,
        "parent": plan_digest,
        "pins_considered": [
            {"card_id": pinned, "consideration": "worth one comparison practice"}
        ],
        "hypotheses": [
            *plan["hypotheses"],
            {
                "rank": len(plan["hypotheses"]) + 1,
                "hypothesis": "A pinned method is worth one practice",
                "expected_effect": "a comparison point",
                "stopping_rule": "one practice",
                "cites": [{"card_id": pinned, "origin": "shared"}],
            },
        ],
    }
    status, body = post(
        server, token, "/api/v1/plans/edit", {"plan_document": document}
    )
    assert status == 200, body
    assert (body["parent"], body["created_by"]) == (plan_digest, "miner")
    # A second edit through the MCP door, of the first: one more version.
    first = body["digest"]
    second = {
        **document,
        "parent": first,
        "hypotheses": [
            *document["hypotheses"][:-1],
            {**document["hypotheses"][-1], "stopping_rule": "two practices"},
        ],
    }
    result = asyncio.run(tools["carbon_plan_edit"].fn(plan_document=json.dumps(second)))
    assert (result.payload["parent"], result.payload["created_by"]) == (
        first,
        "miner",
    )
    # A plan citing a banned card is refused at the MCP door as at the other.
    banned_cite = {
        **second,
        "hypotheses": [
            {
                **second["hypotheses"][0],
                "cites": [{"card_id": banned, "origin": "shared"}],
            },
            *second["hypotheses"][1:],
        ],
    }
    with pytest.raises(ToolError, match="plan_invalid"):
        asyncio.run(tools["carbon_plan_edit"].fn(plan_document=banned_cite))
    return result.payload["digest"], plan, (plan_digest, first)


def test_8b_the_miner_pins_bans_and_edits_through_both_doors(graphite):
    digest, original, (planned, first) = edited(graphite)
    plans = {p["digest"]: p for p in graphite.perform("plan_list", {})["plans"]}
    # Each edit is a new version; the Planner's plan and the first edit are
    # kept beside the last, newest first.
    assert list(plans) == [digest, first, planned]
    assert [plans[d]["parent"] for d in (digest, first, planned)] == [
        first,
        planned,
        None,
    ]
    assert [plans[d]["created_by"] for d in (digest, first, planned)] == [
        "miner",
        "miner",
        "planner",
    ]
    saved = graphite.perform("plan_get", {"plan": digest})["plan"]
    assert saved["created_by"] == "miner"
    # The edit carries the Planner's hypothesis, the miner's own and the pin
    # it considered.
    assert saved["hypotheses"][0] == original["hypotheses"][0]
    assert len(saved["hypotheses"]) == len(original["hypotheses"]) + 1
    assert saved["hypotheses"][-1]["stopping_rule"] == "two practices"
    assert [p["card_id"] for p in saved["pins_considered"]] == [
        graphite.perform("library_list", {})["curation"]["pins"][0]
    ]


@pytest.fixture
def intake_graphite(tmp_path, monkeypatch):
    """`intake_battery`'s fixtures for a Graphite host (stage 6b's)."""
    from test_battery_intake import MINER, signed

    from carbon.battery import deployment
    from carbon.battery import intake as ib
    from carbon.battery import remote_submission as rs

    class Roomy(ib.PeerLimits):
        def __init__(self):
            super().__init__(burst=500, rate=100.0)

    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    monkeypatch.setattr(ib, "PeerLimits", Roomy)
    monkeypatch.setattr(rs, "_signed", lambda signer, facts, body: signed(signer, body))
    monkeypatch.setattr(rs, "POLL_S", 0.3)
    launchpad = GraphiteLaunchpad(tmp_path, monkeypatch, miner_key=MINER)
    yield launchpad
    launchpad.close()


class AdvancingChain:
    """DEVELOPMENT FIXTURE: the intake refresher's chain reader for a stage
    that outlives a refresh period (`intake.REFRESH_S`). Each read is a fresh
    snapshot of the next finalized block, as a live chain gives. The intake's
    journal refuses two different snapshots of one block
    (`TRANSPORT_CONTEXT`), so one block stamped afresh on every read would
    refuse a submission's poll signed after a refresh, which is a fixture
    race, not the miner's mistake."""

    def __init__(self):
        self.reads = 0

    async def capture(self, context):
        from test_battery_intake import snapshot

        self.reads += 1
        return snapshot(100 + self.reads)


def test_8c_a_build_constructs_from_the_edited_plan_and_submits(
    intake_graphite, tmp_path, refs
):
    from test_battery_intake_service_e2e import made_here, open_pool, serving

    from carbon.development_session.research_loop import SELECT

    graphite = intake_graphite
    digest, original, _versions = edited(graphite)
    cited = original["hypotheses"][0]["cites"][0]["card_id"]
    curation = graphite.perform("library_list", {})["curation"]["digest"]
    select = {"strategy_json": json.dumps(KNN), "used_feedback": False}
    graphite.model = GraphiteModel(
        constructor=[
            # The plan's own card, then its recipe practised.
            reply(
                call("a", "lit_card", {"card_id": cited}),
                call("b", *task("practice", strategy=KNN, why="The plan's recipe")),
            ),
            reply(call("c", SELECT, {**select, "reason": "practised, as planned"})),
        ]
    )
    graphite.arxiv = FakeArxiv([])
    made = made_here(tmp_path / "validator-service")
    open_pool(made, refs)
    # The build runs before it submits, past a refresh of the intake's
    # snapshot: the chain advances a block on each read, as a live one does.
    chain = AdvancingChain()
    with serving(made, chain=chain) as live:
        graphite.cfg = {**graphite.cfg, "intakes": {BATTERY: live.url}}
        # One committed final epoch: the build selects once and completes.
        campaign = graphite.launch_graphite(
            "e2e-graphite-build-0001", epochs=1, graphite_mode="BUILD", plan=digest
        )
    model = graphite.model
    assert not model.requests["planner"] and not model.reader_calls
    assert len(model.requests["constructor"]) == 2 and model.errors == []
    assert graphite.arxiv.requests == []  # a BUILD hunts nothing
    answered = outputs(model.requests["constructor"][1])
    assert answered["b"]["terminal_task"]["state"] == "SUCCEEDED"
    # The card the plan cites is the miner's own, served as such.
    assert cards_answered(model.requests["constructor"][1])[cited]["origin"] == (
        "miner_hunt"
    )
    root = graphite.campaign_root(campaign)
    selected = json.loads((root / "epoch-1" / "selected-recipe.json").read_bytes())
    assert selected["strategy"] == KNN
    view = graphite.view(campaign)
    assert view["state"] == "COMPLETED", view["last_refusal"]
    assert view["journey"]["submitted_epochs"] == [1], view["last_refusal"]
    assert view["final_results"][0]["status"] == "VALIDATOR_OUTCOME"
    # The plan and the curation the miner launched with are frozen by digest.
    manifest = json.loads((root / "campaign-manifest.json").read_bytes())
    block = manifest["provider"]["graphite"]
    assert (block["mode"], block["plan_digest"]) == ("BUILD", digest)
    assert block["curation_digest"] == curation
    assert block["escalation"] == []
    shown = graphite.graphite_view(campaign)
    assert (shown["plan_digest"], shown["stage"]) == (digest, "complete")
    assert [(s["stage"], s["state"]) for s in shown["stages"]] == [("build", "DONE")]
    # A resume replays: no model call, no arXiv request.
    graphite.model, graphite.arxiv = GraphiteModel(), FakeArxiv([])
    graphite.host.control(campaign, "resume")
    graphite.join()
    assert nothing_called(graphite.model)
    assert graphite.arxiv.requests == []


def test_8d_a_full_campaigns_research_stops_at_its_share(graphite):
    from carbon.development_session.research_loop import SELECT
    from carbon.development_session.research_tools import PREFIX

    graphite.arxiv = FakeArxiv([])
    # More research turns than the share admits: it stops typed, and the
    # build goes on with the plan it has (none written: the Planner was cut).
    graphite.model = GraphiteModel(
        planner=[
            reply(call(f"p{i}", PREFIX + "get_challenge_info", {})) for i in range(8)
        ],
        constructor=[
            reply(call("b", *task("practice", strategy=KNN, why="A first practice"))),
            reply(
                call(
                    "c",
                    SELECT,
                    {
                        "strategy_json": json.dumps(KNN),
                        "used_feedback": False,
                        "reason": "practised",
                    },
                )
            ),
        ],
    )
    # One committed final epoch: no second build epoch is scripted.
    campaign = graphite.launch_graphite(
        "e2e-graphite-full-00001", attempts=24, epochs=1, research_share=0.1
    )
    model = graphite.model
    shown = graphite.graphite_view(campaign)
    assert shown["mode"] == "FULL" and shown["research_share"] == 0.1
    # 10% of 24 attempts is 2: the Planner made two calls, both research,
    # and its third was refused before it was reserved or sent.
    assert shown["research_cap"]["provider_attempts"] == 2
    assert shown["research_spent"]["provider_attempts"] == 2
    assert len(model.requests["planner"]) == 2 and model.errors == []
    # The research stage stopped typed, by its closed code.
    stages = {s["stage"]: s for s in shown["stages"]}
    assert (stages["plan"]["state"], stages["plan"]["code"]) == (
        "STOPPED",
        "research_share_reached",
    )
    # The build went on, with no plan (the Planner was cut): it practised and
    # selected; this host names no validator, so the candidate is kept for a
    # later submit (`evaluation_unavailable`), never reported as submitted.
    assert len(model.requests["constructor"]) == 2
    root = graphite.campaign_root(campaign)
    assert (root / "epoch-1" / "selected-recipe.json").exists()
    view = graphite.view(campaign)
    assert view["last_refusal"]["code"] == "evaluation_unavailable"
    assert view["journey"]["submitted_epochs"] == []
    waits_ready_with_its_candidate(graphite, campaign)


#: An unknown card id: `lit_card` answers it with a short refusal, so a long
#: scripted run grows its context slowly and on purpose.
NO_CARD = "arxiv-0000.00000v1"


def shared_plan(graphite):
    """A plan the miner wrote through the plan door, citing a card of the
    shared pack: a BUILD needs no hunt for it."""
    from carbon.battery.challenge import CHALLENGE

    card = shared_pack().cards[0]
    document = {
        "schema": "carbon.graphite.miner-plan.v1",
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "hypotheses": [
            {
                "rank": 1,
                "hypothesis": "Neighbours interpolate the protocol-to-ageing map",
                "expected_effect": "lower practice error than the control",
                "stopping_rule": "stop when the ceiling binds",
                "recipe": KNN,
                "cites": [{"card_id": card["card_id"], "origin": "shared"}],
            }
        ],
        "pins_considered": [],
        "parent": None,
        "created_by": "miner",
    }
    return graphite.perform("plan_edit", {"plan_document": document})["digest"]


def summaries(request):
    """The compaction summaries a request carries, by their label."""
    found = []
    for item in request["input"]:
        content = item.get("content") if item.get("role") == "user" else None
        if type(content) is not str or "carbon_context_compaction" not in content:
            continue
        found.append(json.loads(content)["carbon_context_compaction"])
    return found


def test_8e_limits_are_money_and_time_and_a_long_run_compacts_once(graphite):
    digest = shared_plan(graphite)
    # More turns than the campaign's 80 provider attempts admit, none of them
    # a selection: what ends the run is the miner's own ceiling.
    cheap = [reply(call(f"r{i}", "lit_card", {"card_id": NO_CARD})) for i in range(100)]
    # One reply reports a context near the selection's admission ceiling:
    # before the next turn the engine asks for the recorded compaction.
    cheap[20]["usage"]["input_tokens"] = 53000
    graphite.model = GraphiteModel(constructor=cheap)
    graphite.arxiv = FakeArxiv([])
    campaign = graphite.launch_graphite(
        "e2e-graphite-limits-001",
        attempts=80,
        epochs=1,
        graphite_mode="BUILD",
        plan=digest,
    )
    model = graphite.model
    assert model.errors == []
    # No per-epoch cap was set: past the historical 48 calls, until the
    # campaign's own ceiling - 80 attempts, the compaction call among them.
    ledger, owner = graphite.ledger(campaign), graphite.owner(campaign)
    status = ledger.status(owner=owner)
    assert status["used"]["provider_attempts"] == 80
    assert len(model.requests["constructor"]) == 79
    outcome = json.loads(
        (graphite.campaign_root(campaign) / "epoch-1" / "outcome.json").read_bytes()
    )
    assert outcome["status"] == "STOPPED", outcome
    assert "provider_attempts" in json.dumps(outcome), outcome
    # Compacted once, as a metered and journalled call of its own...
    # (before turn 21, counted from 0: the one after the large reply)...
    compacted = [op["id"] for op in status["operations"] if "-compact-" in op["id"]]
    assert compacted == ["epoch-1-compact-021"]
    assert len(model.requests["compaction"]) == 1
    # ...after which every request carries the model's own summary, labelled
    # as its summary, in place of the turns that left the context.
    before, after = model.requests["constructor"][20], model.requests["constructor"][21]
    assert summaries(before) == []
    (summary,) = summaries(after)
    assert summary["label"] == "SUMMARY"
    assert summary["summary"]["findings"] == COMPACTION_SUMMARY["findings"]
    assert all(len(summaries(r)) == 1 for r in model.requests["constructor"][21:])
    assert graphite.view(campaign)["state"] == "COMPLETED"
    # Replay is exact: a resume calls nothing.
    graphite.model = GraphiteModel()
    graphite.host.control(campaign, "resume")
    graphite.join()
    assert nothing_called(graphite.model)


# --- entry points of the processes above --------------------------------------


def _quietly_handle_stop(stop):
    def handler(*_):
        stop.set()

    for name in ("SIGTERM", "SIGINT", "SIGHUP"):
        with contextlib.suppress(ValueError, OSError):
            signal.signal(getattr(signal, name), handler)


def _serve(root, variant):
    """A miner's own MCP client's server: `standard_cli` with the runner
    profile and no campaign (every operation, including launch), a CLIENT of
    the campaigns' supervisor, starting this module as the detached
    supervisor when work waits with none running."""
    from carbon.development_session.chain_onboarding import carbon_testnet_context
    from carbon.miner_mcp import open_tier, standard_cli
    from scripts.dev.miner_launchpad import runner
    from scripts.dev.miner_launchpad import supervisor as supervision

    record_pid(root, "server")
    fixtures = install_journey(root, setattr, variant)
    agent_fixtures(root, setattr)
    runner.RunnerAdapter.spawn = staticmethod(
        lambda configuration: spawn(root, "supervise", variant)
    )

    def for_profile(cls, *_, **__):
        host = graphite_ready(peer(fixtures, root, supervision.CLIENT), setattr)
        with contextlib.suppress(Exception):
            host.wake_if_stranded()
        return host

    runner.RunnerAdapter.for_profile = classmethod(for_profile)
    real = open_tier.create_open_tier_server
    open_tier.create_open_tier_server = lambda **kw: real(
        reader=Registered(), context=carbon_testnet_context(), **kw
    )
    return standard_cli.main(
        [
            "--configuration",
            str(root / "runner-profile.json"),
            "--state-dir",
            str(root / "setup-state"),
        ]
    )


def _supervise(root, variant):
    """The detached supervisor a client starts (`supervisor.main`), over the
    lifecycle fixtures, retiring after one idle second."""
    from scripts.dev.miner_launchpad import supervisor as supervision

    record_pid(root, "supervisor")
    fixtures = install_journey(root, setattr, variant)
    agent_fixtures(root, setattr)
    host = graphite_ready(peer(fixtures, root, supervision.DETACHED), setattr)
    host.supervisor.idle_exit, host.supervisor.poll = 1.0, 0.1
    stopping = host.supervisor.stopping
    _quietly_handle_stop(stopping)
    try:
        host.supervisor.run_until_idle()
    finally:
        host.close()
    return 0


def _control_center(root, variant):
    """The Control Center's campaign host: the supervisor while it runs; on
    SIGTERM it closes as the Control Center does."""
    from scripts.dev.miner_launchpad import supervisor as supervision

    record_pid(root, "control-center")
    fixtures = install_journey(root, setattr, variant)
    agent_fixtures(root, setattr)
    host = graphite_ready(peer(fixtures, root, supervision.SUPERVISOR), setattr)
    host.supervisor.poll = 0.1
    host.supervisor.start()
    stop = threading.Event()
    _quietly_handle_stop(stop)
    while not stop.wait(0.2):
        pass
    host.close()
    (root / f"control-center-closed-{os.getpid()}").touch()
    return 0


def _serve_attach(root):
    """`standard_cli` with the battery campaign's runner profile: the
    operation tools and attach, with the stdio attach fixtures (stub chain,
    fixture signer, fixture runtime)."""
    from test_standard_mcp_cli import FixtureSigner, fixture_runtime

    import carbon.chain.auth
    from carbon.development_session import research_tools
    from carbon.development_session.chain_onboarding import carbon_testnet_context
    from carbon.miner_mcp import open_tier, standard_cli

    record_pid(root, "server")
    carbon.chain.auth.BittensorMessageSigner = FixtureSigner
    research_tools.BittensorMessageSigner = FixtureSigner
    standard_cli._runtime = fixture_runtime
    real = open_tier.create_open_tier_server
    open_tier.create_open_tier_server = lambda **kw: real(
        reader=Registered(), context=carbon_testnet_context(), **kw
    )
    return standard_cli.main(
        [
            "--configuration",
            str(root / "profile.json"),
            "--state-dir",
            str(root / "setup-state"),
        ]
    )


ROLES = {
    "serve": _serve,
    "supervise": _supervise,
    "control-center": _control_center,
}


def main(argv):
    role, root = argv[0], Path(argv[1])
    if role == "attach":
        return _serve_attach(root)
    return ROLES[role](root, argv[2] if len(argv) > 2 else None)


if __name__ != "__main__":
    # The published development reference cases, as a pytest fixture (6b).
    from test_battery_validator_daemon import refs  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
