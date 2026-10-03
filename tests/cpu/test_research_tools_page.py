"""The working toolbox: the page uses the agent's own research tools.

OWNER-MINER-RESEARCH-SURFACE-03 ("my other request for the research surface
was access to the tooling in the control center"), RSURF-D15 to D18:
- parity: the page's tools, schemas, results and refusals are the MCP
  server's own, for every tool;
- lock: one holder at a time, refused as campaign_busy with what to do,
  released on close and after idle minutes;
- text only: the page parses no HTML and inlines raster images only;
- bounds: stdout and images are bounded;
- the fixture can run no work.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from carbon.development_session.research_tools import PREFIX
from scripts.dev.miner_launchpad import run_output, tool_door
from scripts.dev.miner_launchpad.controller import Rejected, owner_lock
from scripts.dev.miner_launchpad.research_fixture import CAMPAIGN, FixtureRunner
from scripts.dev.miner_launchpad.tool_fixture import (
    REFUSED,
    TASK,
    FixtureTools,
    fixture_adapter,
    plot_png,
)

ROOT = Path(__file__).resolve().parents[2]
OP = "page-0123456789abcdef01234567"


def fixture():
    runner = FixtureRunner()
    return runner, fixture_adapter(FixtureTools(runner), runner.principal)


def example(runner):
    return runner.toolbox()["examples"][0]


def arguments_for(operation, runner):
    """One valid call of each research tool."""
    strategy = example(runner)
    return {
        "get_challenge_info": {},
        "get_interaction_manifest": {},
        "get_prior": {},
        "get_mock_scaffold": {},
        "dry_validate": {"strategy": strategy},
        "compile_strategy": {"strategy": strategy},
        "inspect_prior_alignment": {"strategy": strategy},
        "inspect_resources": {"strategy": strategy},
        "forecast_resources": {"strategy": strategy, "seconds": 60},
        "start_research_task": {
            "kind": "workspace",
            "strategy": None,
            "action": "inventory",
            "arguments": {},
            "hypothesis": "List my files",
            "expected_effect": "See them",
        },
        "get_research_result": {"task_id": TASK, "poll_sequence": 0},
        "cancel_research_task": {"task_id": TASK},
    }[operation]


# ---- Parity: the same tools, schemas, results and refusals as MCP.


def test_every_tool_is_the_mcp_servers_own_with_its_own_schema():
    from carbon import research
    from carbon.miner_mcp.standard_server import _create_server

    _, adapter = fixture()
    door = tool_door.ToolDoor(adapter)
    listed = asyncio.run(_create_server(adapter).list_tools())
    mcp = {tool.name: tool.input_schema for tool in listed}
    page = {tool["name"]: tool["input_schema"] for tool in door.describe()["tools"]}
    assert page == mcp
    assert set(page) == {PREFIX + op for op in research.SUPPORTED_OPERATIONS}


@pytest.mark.parametrize(
    "operation",
    [
        "get_challenge_info",
        "get_interaction_manifest",
        "get_prior",
        "get_mock_scaffold",
        "dry_validate",
        "compile_strategy",
        "inspect_prior_alignment",
        "inspect_resources",
        "forecast_resources",
        "start_research_task",
        "get_research_result",
        "cancel_research_task",
    ],
)
def test_every_tool_answers_the_page_as_it_answers_mcp(operation):
    from carbon.miner_mcp.standard_server import _create_server

    runner, adapter = fixture()
    door = tool_door.ToolDoor(adapter)
    server = _create_server(adapter)
    args = {"operation_id": OP, **arguments_for(operation, runner)}
    page = asyncio.run(door.call(PREFIX + operation, args))
    mcp = asyncio.run(server.call_tool(PREFIX + operation, args))
    assert page == {"ok": True, "result": mcp.structured_content}


def test_a_refusal_reads_exactly_as_the_agent_reads_it():
    from mcp.server.mcpserver.exceptions import ToolError

    from carbon.miner_mcp.standard_server import _create_server

    runner, adapter = fixture()
    door = tool_door.ToolDoor(adapter)
    server = _create_server(adapter)
    bad = {"operation_id": "short", "strategy": example(runner)}
    page = asyncio.run(door.call(PREFIX + "dry_validate", bad))
    with pytest.raises(ToolError) as raised:
        asyncio.run(server.call_tool(PREFIX + "dry_validate", bad))
    assert page == {"ok": False, "error": str(raised.value)}
    with pytest.raises(Rejected) as unknown:
        asyncio.run(door.call("carbon_not_a_tool", {}))
    assert unknown.value.code == "tool_unknown"


def test_long_tasks_use_the_mcp_tasks_projection():
    from carbon.miner_mcp.mcp_extensions import task_projection

    _, adapter = fixture()
    door = tool_door.ToolDoor(adapter)
    observed = asyncio.run(door.observe(TASK))
    expected = task_projection(asyncio.run(adapter.observe_task(TASK)), detailed=True)
    assert observed == {"ok": True, "task": expected}
    assert observed["task"]["status"] == "completed"


def test_both_doors_have_run_output():
    from carbon.miner_mcp.mcp_operations import make_operation_tools
    from scripts.dev.miner_launchpad.operations import OPERATIONS, perform

    runner = FixtureRunner()
    op = OPERATIONS["run_output"]
    assert op.admits_work is False and op.required == {"campaign", "task"}
    tool = {t.name: t for t in make_operation_tools(runner)}["carbon_run_output"]
    mcp = asyncio.run(tool.fn(campaign=CAMPAIGN, task=TASK)).payload
    assert mcp == perform(runner, "run_output", {"campaign": CAMPAIGN, "task": TASK})


# ---- The lock: one holder at a time.


def locked_opener(root):
    """An opener that holds `root`'s ownership lock, as `attached` does."""
    import contextlib

    @contextlib.asynccontextmanager
    async def opener(campaign):
        try:
            with owner_lock(root):
                yield fixture()[1]
        except RuntimeError as exc:
            if "owns this state directory" in str(exc):
                raise tool_door.Busy() from None
            raise

    return opener


def test_a_held_campaign_is_refused_with_what_to_do(tmp_path):
    sessions = tool_door.ToolSessions(locked_opener(tmp_path))
    # An MCP agent has the campaign attached.
    with owner_lock(tmp_path), pytest.raises(Rejected) as refused:
        sessions.open("c")
    assert refused.value.code == "campaign_busy_another_session"
    assert "carbon_detach_campaign" in tool_door.BUSY["another_session"]
    running = tool_door.ToolSessions(
        locked_opener(tmp_path), busy_hint=lambda c: "carbon_agent_or_operation"
    )
    # Carbon's agent, or an operation.
    with owner_lock(tmp_path), pytest.raises(Rejected) as refused:
        running.open("c")
    assert refused.value.code == "campaign_busy_carbon_agent_or_operation"
    assert sessions.state("c")["open"] is False


def test_the_page_holds_the_campaign_until_it_closes(tmp_path):
    sessions = tool_door.ToolSessions(locked_opener(tmp_path))
    state = sessions.open("c")
    assert state["open"] and "campaign_busy" in state["holds"]
    # While open, an agent's attach or an operation cannot take the lock.
    with pytest.raises(RuntimeError), owner_lock(tmp_path):
        pass
    assert sessions.close("c") == {"open": False, "closed": True}
    with owner_lock(tmp_path):
        pass


def test_an_idle_session_is_released(tmp_path):
    now = [0.0]
    sessions = tool_door.ToolSessions(
        locked_opener(tmp_path), idle=600, clock=lambda: now[0]
    )
    sessions.open("c")
    now[0] = 599
    assert sessions.state("c")["open"] is True
    now[0] = 1200
    assert sessions.state("c")["open"] is False
    with owner_lock(tmp_path):
        pass
    with pytest.raises(Rejected) as closed:
        sessions.call("c", {"tool": PREFIX + "get_prior", "arguments": {}})
    assert closed.value.code == "tools_session_not_open"


def test_opening_a_real_campaign_passes_the_operation_gates_first():
    from carbon.development_session.chain_onboarding import OnboardingFailure

    opened = []

    class Host:
        tool_sessions = tool_door.ToolSessions(lambda campaign: opened.append(campaign))

        def owned_campaign(self, campaign):
            return {"id": campaign, "root": "/nowhere", "kind": "product"}

        def configured(self):
            return {"profile_id": "p"}

        def registration(self, profile):
            raise OnboardingFailure("NOT_REGISTERED", next_action="register")

    with pytest.raises(Rejected) as refused:
        tool_door.route(Host(), "c", "open", {})
    assert refused.value.code == "registration_required"
    assert opened == []
    retired = Host()
    retired.owned_campaign = lambda c: {"id": c, "root": None, "kind": "grant"}
    with pytest.raises(Rejected) as refused:
        tool_door.route(retired, "c", "open", {})
    assert refused.value.code == "retired_grant_campaign"


# ---- Output: text only, bounded.


def test_the_page_parses_no_html_and_inlines_only_raster_images():
    source = (ROOT / "scripts/dev/miner_launchpad/research_tools.js").read_text()
    for pattern in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.write",
        "DOMParser",
        "eval(",
        "new Function",
        "createContextualFragment",
    ):
        assert pattern not in source, pattern
    assert '"image/png", "image/jpeg", "image/gif", "image/webp"' in source
    assert "svg" not in source.lower().split("image_types")[1].split(";")[0]
    # Images are blobs of checked bytes; the page's CSP allows blob: images
    # and no data: URL.
    assert "URL.createObjectURL(new Blob([decode(" in source
    assert '"data:"' not in source


def test_stdout_is_a_bounded_tail_and_text_is_shown_as_it_reads():
    long = b"x" * (run_output.STDOUT_MAX + 10) + b"\xe2\x80\xaeend"
    doc = run_output.document(
        TASK, {"worker": {"operation": "op"}}, stdout=long, exports=[]
    )
    assert len(doc["stdout"].encode()) <= run_output.STDOUT_MAX
    assert doc["stdout"].endswith("�end")  # a bidi override cannot hide
    assert doc["stdout_truncated_to_last_bytes"] == run_output.STDOUT_MAX
    assert doc["carrier"]["stderr"].startswith("not kept")


def test_images_are_recognised_by_their_bytes_and_bounded():
    png = plot_png()
    big = b"\x89PNG\r\n\x1a\n" + b"\0" * run_output.IMAGE_MAX
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>x</script></svg>'
    named = b"not a png at all"
    many = [(f"p{n}.png", png) for n in range(run_output.IMAGES_COUNT + 2)]
    doc = run_output.document(
        TASK,
        {"worker": {"operation": "op"}},
        stdout=None,
        exports=[("big.png", big), ("x.svg", svg), ("fake.png", named), *many],
    )
    by_name = {f["name"]: f for f in doc["files"]}
    assert (
        "image_base64" not in by_name["big.png"] and by_name["big.png"]["not_inlined"]
    )
    assert (
        by_name["x.svg"]["media_type"] is None
        and "image_base64" not in by_name["x.svg"]
    )
    assert by_name["fake.png"]["media_type"] is None
    inlined = [f for f in doc["files"] if "image_base64" in f]
    assert len(inlined) == run_output.IMAGES_COUNT
    assert sum(len(base64.b64decode(f["image_base64"])) for f in inlined) <= (
        run_output.IMAGES_TOTAL
    )
    assert base64.b64decode(inlined[0]["image_base64"]) == png
    total = run_output.document(
        TASK,
        {"worker": {}},
        stdout=None,
        exports=[
            (f"m{n}.png", b"\x89PNG\r\n\x1a\n" + b"\0" * (900 * 1024)) for n in range(5)
        ],
    )
    kept = sum(
        len(base64.b64decode(f["image_base64"]))
        for f in total["files"]
        if "image_base64" in f
    )
    assert kept <= run_output.IMAGES_TOTAL


def test_run_output_reads_the_campaigns_own_records(tmp_path):
    from carbon.development_session.profile import canonical, digest
    from carbon.development_session.research_ledger import CampaignLedger
    from carbon.development_session.research_workspace import ResearchWorkspace

    ledger = CampaignLedger(tmp_path)
    workspace = ResearchWorkspace(ledger, "alice")
    workspace.put("abc-plot.png", plot_png())
    (tmp_path / "operation-1").mkdir()
    (tmp_path / "operation-1" / "stdout.txt").write_bytes(b"hello\n")
    result = {
        "provenance": "MINER_SELF_REPORTED",
        "worker": {"operation": "operation-1"},
        "workspace_exports": ["abc-plot.png"],
    }
    body = canonical(result)
    with ledger.db() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS research_results(owner TEXT NOT NULL,task TEXT NOT NULL,body BLOB NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(owner,task))"
        )
        db.execute(
            "INSERT INTO research_results VALUES(?,?,?,?)",
            ("alice", TASK, body, digest(body)),
        )
    doc = run_output.for_campaign(tmp_path, "alice", TASK)
    assert doc["stdout"] == "hello\n"
    assert doc["files"][0]["media_type"] == "image/png"
    with pytest.raises(Rejected) as other:
        run_output.for_campaign(tmp_path, "bob", TASK)
    assert other.value.code == "run_output_unavailable"
    with pytest.raises(Rejected) as malformed:
        run_output.for_campaign(tmp_path, "alice", "../../etc")
    assert malformed.value.code == "research_task_id_required"


# ---- The fixture runs nothing.


def test_the_fixture_can_run_no_work():
    from carbon.development_session.research_tools import (
        PreDispatchRefusal,
        ResearchMinerTools,
    )

    runner, adapter = fixture()
    door = tool_door.ToolDoor(adapter)
    sdk = adapter._sdk
    # No connection, no composition worker, no ledger: the SDK's own path
    # refuses before anything is dispatched.
    assert sdk.connection is None and sdk.wrapper is None and sdk.ledger is None
    with pytest.raises(PreDispatchRefusal):
        asyncio.run(ResearchMinerTools.call(sdk, PREFIX + "get_prior", {}, OP))
    run = {
        "kind": "workspace",
        "strategy": None,
        "action": "run_python",
        "arguments": {
            "source": "print(1)",
            "files": [],
            "hypothesis": "h",
            "expected_effect": "e",
        },
        "hypothesis": "h",
        "expected_effect": "e",
    }
    practice = {
        **run,
        "kind": "practice",
        "strategy": example(runner),
        "action": None,
        "arguments": None,
    }
    for args in (run, practice):
        blocking = asyncio.run(
            door.call(PREFIX + "start_research_task", {"operation_id": OP, **args})
        )
        assert blocking["result"]["payload"]["reason"] == "fixture_read_only"
        started = asyncio.run(door.start({"operation_id": OP, **args}))
        assert started["task"] is None
        assert "fixture_read_only" in json.dumps(started["result"])
    # Its one task is already finished: a cancel changes nothing.
    cancelled = asyncio.run(door.observe(TASK, cancel=True))
    assert cancelled["ok"] and cancelled["task"]["status"] == "completed"
    assert REFUSED["authority_granted"] is False
    # Its campaign has no root and no profile: nothing to lock or launch.
    assert runner.owned_campaign(CAMPAIGN)["root"] is None
    with pytest.raises(Rejected):
        runner.configured()


def test_the_demo_shows_a_workspace_a_finished_run_and_a_validation():
    runner = FixtureRunner()
    state = tool_door.route(runner, CAMPAIGN, "open", {})
    try:
        assert state["open"] and state["tasks"] == [TASK]
        start = PREFIX + "start_research_task"
        listed = tool_door.route(
            runner,
            CAMPAIGN,
            "call",
            {
                "tool": start,
                "arguments": {
                    "operation_id": OP,
                    "kind": "workspace",
                    "strategy": None,
                    "action": "inventory",
                    "arguments": {},
                    "hypothesis": "List",
                    "expected_effect": "See",
                },
            },
        )
        names = [
            f["name"]
            for f in listed["result"]["payload"]["public_result"]["result"]["files"]
        ]
        assert "analyse_capacity.py" in names and any(n.endswith(".png") for n in names)
        output = runner.run_output_admitted(None, {"task": TASK})
        assert output["stdout"] and output["files"][0]["image_base64"]
        checked = tool_door.route(
            runner,
            CAMPAIGN,
            "call",
            {
                "tool": PREFIX + "dry_validate",
                "arguments": {"operation_id": OP, "strategy": example(runner)},
            },
        )
        assert checked["result"]["payload"]["reply"]["result"]["valid"] is True
    finally:
        tool_door.route(runner, CAMPAIGN, "close", {})


def test_the_tools_route_takes_tool_sized_bodies_only(tmp_path):
    import threading

    from test_miner_launchpad import auth, request

    from scripts.dev.miner_launchpad import controller

    runner = FixtureRunner()
    server = controller.Server(
        controller.Controller(tmp_path / "r.sqlite3"),
        "x" * 40,
        port=0,
        research_runner=runner,
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        base = "/api/v1/tools/" + CAMPAIGN
        code, _, body = request(server, base, headers=auth())
        assert code == 200 and json.loads(body)["open"] is False
        assert request(server, base + "/open", "POST", {}, auth())[0] == 200
        # More than the 4 KiB other routes take, within the tool's own
        # 16 KiB arguments bound.
        content = base64.b64encode(b"# edited\n" * 1000).decode()
        write = {
            "tool": PREFIX + "start_research_task",
            "arguments": {
                "operation_id": OP,
                "kind": "workspace",
                "strategy": None,
                "action": "write_file",
                "arguments": {
                    "name": "notes.md",
                    "content_base64": content,
                    "expected_digest": "sha256:" + "0" * 64,
                },
                "hypothesis": "Edit",
                "expected_effect": "Save",
            },
        }
        code, _, body = request(server, base + "/call", "POST", write, auth())
        assert code == 200, body
        # The digest guard refused the stale write, as write_file does.
        assert "compare-and-swap" in json.loads(body)["result"]["payload"]["detail"]
        # Other routes keep the 4 KiB bound.
        code, _, body = request(
            server,
            "/api/v1/conversation/" + CAMPAIGN,
            "POST",
            {"text": "x" * 5000},
            auth(),
        )
        assert code == 413
        assert request(server, base + "/close", "POST", {}, auth())[0] == 200
    finally:
        server.shutdown()
        server.server_close()
        runner.close()


def test_the_toolbox_carries_the_registered_example_recipes():
    from carbon.challenge_registry import registry
    from scripts.dev.miner_launchpad import toolbox

    battery = {"id": "battery-fastcharge-ageing-development-v1", "version": "1.0"}
    described = registry.describe(battery["id"], battery["version"])
    examples = toolbox.build(battery)["examples"]
    assert examples and examples == [e["strategy"] for e in described["examples"]][:4]


def test_the_runner_opens_through_the_agents_own_attach_path(tmp_path, monkeypatch):
    import contextlib

    from carbon.miner_mcp import standard_cli

    seen = []

    @contextlib.asynccontextmanager
    async def attached(configuration, campaign):
        seen.append((configuration, campaign))
        with owner_lock(tmp_path / campaign):
            yield fixture()[1], None

    monkeypatch.setattr(standard_cli, "attached", attached)

    class Host:
        configuration = tmp_path / "profile.json"

        def owned_campaign(self, campaign):
            return {"id": campaign, "root": str(tmp_path / "abcd"), "kind": "product"}

    sessions = tool_door.ToolSessions(tool_door.runner_opener(Host()))
    sessions.open("c")
    assert seen == [(Host.configuration, "abcd")]
    sessions.close("c")
    with owner_lock(tmp_path / "abcd"), pytest.raises(Rejected) as refused:
        sessions.open("c")
    assert refused.value.code == "campaign_busy_another_session"


def test_the_runner_says_when_its_own_agent_holds_the_campaign(tmp_path):
    from types import SimpleNamespace

    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    runner = RunnerAdapter(tmp_path / "runner.sqlite3", principal="alice")
    assert isinstance(runner.tool_sessions, tool_door.ToolSessions)
    assert runner.tools_busy_hint("c") == "another_session"
    runner.threads["c"] = SimpleNamespace(is_alive=lambda: True)
    assert runner.tools_busy_hint("c") == "carbon_agent_or_operation"
