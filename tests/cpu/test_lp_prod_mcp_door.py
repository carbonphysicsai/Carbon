"""LP-PROD-B: the MCP door's errors are correct, its tools discoverable and
its schemas natural (OWNER-LAUNCHPAD-PROD-01).

Each test names the behaviour it pins. The research tools are exercised
through the real SDK (`ResearchMinerTools`) wherever the behaviour lives in
it, so a fake of an old shape cannot keep a broken path green: a correction
the SDK really builds, a refusal its admission check really raises.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_cw1_research_ledger import ledger as frozen_ledger
from test_standard_mcp_adapter import make_adapter, practice, reply, workspace

from carbon import research
from carbon.development_session.profile import CHALLENGE, canonical
from carbon.development_session.research_control import DispatchStopped
from carbon.development_session.research_ledger import DEVELOPMENT_ELAPSED_SECONDS
from carbon.development_session.research_tools import (
    PREFIX,
    TASK_CORRECTIONS,
    ResearchMinerTools,
    task_correction,
)
from carbon.miner_mcp import serving
from carbon.miner_mcp.standard import (
    AdapterCode,
    AdapterFailure,
    ResearchToolAdapter,
    ResearchToolRequest,
)

OPERATION_ID = "lp-prod-b-operation-0001"
TASK_ID = "rtsk_" + "c" * 64
CAMPAIGN = "d" * 32


class Connection:
    """The campaign's connection as the SDK meets it: the admission check
    runs, and refuses with `refusal` - the way the attached campaign's
    connection refuses - or the fixture stops before anything is signed."""

    def __init__(self, refusal=None):
        self.refusal = refusal
        self.checked = 0

    async def check_registration(self):
        self.checked += 1
        if self.refusal is not None:
            raise ValueError(self.refusal)
        raise AssertionError("this fixture never signs or dispatches")


def real_sdk(tmp_path, connection=None, **ledger_args):
    """A real SDK over a real frozen ledger; the composition holds only what
    the SDK reads before it signs."""
    meter = frozen_ledger(tmp_path / "ledger", **ledger_args)
    composition = SimpleNamespace(
        challenge=CHALLENGE,
        executor=SimpleNamespace(owner="alice"),
        discovery=SimpleNamespace(info=SimpleNamespace(training_support_ref=None)),
    )
    sdk = ResearchMinerTools(
        connection=connection or Connection(),
        wrapper=object(),
        composition=composition,
        ledger=meter,
        owner="alice",
    )
    return sdk, ResearchToolAdapter(sdk, principal="alice"), meter


def run(adapter, operation, arguments, identity=OPERATION_ID):
    return asyncio.run(
        adapter.call(ResearchToolRequest(operation, identity, arguments))
    )


# -- 1. Registered corrections reach the client -----------------------------


def test_a_real_sdk_correction_reaches_the_client_named_in_object_terms(tmp_path):
    """The blocker: every correction became INVALID_RESULT 'do not retry'."""
    _, adapter, meter = real_sdk(tmp_path)
    result = run(adapter, "start_research_task", workspace("public_material", {}))
    payload = result.payload
    assert payload["status"] == "REJECTED_BEFORE_DISPATCH"
    assert payload["correction_code"] == "workspace_field_missing"
    assert payload["field"] == "arguments.name"
    assert "The field that broke the contract: arguments.name." in payload["correction"]
    assert "_json" not in payload["correction"] + payload["field"]
    assert payload["authority_granted"] is False
    assert not result.requires_reconciliation
    # Journalled as a refusal; nothing was charged.
    assert meter.status(owner="alice")["used"]["research_trials"] == 0


def test_an_unexpected_workspace_field_is_named_through_the_mcp_tool(tmp_path):
    from carbon.miner_mcp.standard_server import _create_server

    _, adapter, _ = real_sdk(tmp_path)
    server = _create_server(adapter)
    result = asyncio.run(
        server.call_tool(
            PREFIX + "start_research_task",
            {**workspace("inventory", {"surprise": 1}), "operation_id": OPERATION_ID},
        )
    )
    assert not result.is_error
    payload = result.structured_content["payload"]
    assert payload["correction_code"] == "workspace_field_unexpected"
    assert payload["field"] == "arguments"


@pytest.mark.parametrize(
    "forged",
    [
        {"field": "arguments_json.name", "correction": "private exception text"},
        {
            "field": "/private/controller/path",
            "correction": task_correction(
                "workspace_field_missing", "/private/controller/path", None
            ),
        },
        {
            "field": "arguments_json.name",
            "correction": task_correction(
                "workspace_field_missing", "arguments_json.name", None
            )
            + " plus solver text",
        },
        {
            "field": "arguments_json.name",
            "correction": TASK_CORRECTIONS["workspace_field_missing"],
        },
        {"field": 7, "correction": TASK_CORRECTIONS["workspace_field_missing"]},
    ],
)
def test_a_correction_the_sdk_could_not_have_built_never_escapes(forged, monkeypatch):
    _, adapter = make_adapter()

    async def reject(*args, **kwargs):
        return {
            "status": "REJECTED_BEFORE_DISPATCH",
            "reason": "contract_incompatibility",
            "detail": "Request rejected before dispatch",
            "authority_granted": False,
            "correction_code": "workspace_field_missing",
            **forged,
        }

    monkeypatch.setattr(ResearchMinerTools, "call", reject)
    with pytest.raises(AdapterFailure, match="INVALID_RESULT") as error:
        run(adapter, "start_research_task", workspace())
    assert "private" not in str(error.value)


def test_a_json_string_correction_is_restated_for_the_object_wire(monkeypatch):
    _, adapter = make_adapter()

    async def reject(*args, **kwargs):
        return {
            "status": "REJECTED_BEFORE_DISPATCH",
            "reason": "contract_incompatibility",
            "detail": "Request rejected before dispatch",
            "authority_granted": False,
            "correction_code": "json_string_required",
            "field": "arguments_json",
            "correction": task_correction(
                "json_string_required", "arguments_json", "null"
            ),
        }

    monkeypatch.setattr(ResearchMinerTools, "call", reject)
    payload = run(adapter, "start_research_task", workspace()).payload
    assert payload["correction"].startswith("This field takes a JSON object")
    assert "quoted string" not in payload["correction"]
    assert payload["field"] == "arguments"


# -- 2. Pre-dispatch stops have their own codes -----------------------------


@pytest.mark.parametrize(
    "message,code",
    [
        (
            "campaign elapsed budget reached",
            AdapterCode.CAMPAIGN_ELAPSED_BUDGET_REACHED,
        ),
        ("campaign admission stopped", AdapterCode.CAMPAIGN_ADMISSION_STOPPED),
        ("operator profile changed or controller closed", AdapterCode.OPERATIONAL_STOP),
    ],
)
def test_the_admission_check_refuses_with_its_own_code_and_nothing_started(
    tmp_path, message, code
):
    connection = Connection(message)
    _, adapter, _ = real_sdk(tmp_path, connection)
    with pytest.raises(AdapterFailure) as raised:
        run(adapter, "get_challenge_info", {})
    assert raised.value.code is code
    assert raised.value.dispatch_may_have_occurred is False
    assert connection.checked == 1


def test_the_task_path_reports_an_admission_stop_the_same_way(tmp_path):
    _, adapter, _ = real_sdk(tmp_path, Connection("campaign admission stopped"))
    with pytest.raises(AdapterFailure) as raised:
        asyncio.run(adapter.observe_task(TASK_ID))
    assert raised.value.code is AdapterCode.CAMPAIGN_ADMISSION_STOPPED
    assert raised.value.dispatch_may_have_occurred is False


def test_the_same_text_raised_elsewhere_keeps_the_conservative_answer(monkeypatch):
    """Only the raising site proves nothing was signed; text alone never does."""
    _, adapter = make_adapter(ledger=object())

    async def deeper(self, *args, **kwargs):
        raise ValueError("campaign elapsed budget reached")

    monkeypatch.setattr(ResearchMinerTools, "_call", deeper)
    with pytest.raises(AdapterFailure) as raised:
        run(adapter, "get_challenge_info", {})
    assert raised.value.code is AdapterCode.OPERATIONAL_STOP
    assert raised.value.dispatch_may_have_occurred is True


def test_an_elapsed_budget_at_the_binding_is_its_own_code(tmp_path, monkeypatch):
    now = [1000]
    _, adapter, _ = real_sdk(tmp_path, clock=lambda: now[0])

    async def started(self, *args, **kwargs):
        return reply("start_research_task")

    monkeypatch.setattr(ResearchMinerTools, "_call", started)
    run(adapter, "start_research_task", practice(), "lp-prod-b-first-trial-01")
    now[0] += DEVELOPMENT_ELAPSED_SECONDS + 1
    with pytest.raises(AdapterFailure) as raised:
        run(adapter, "start_research_task", practice(), "lp-prod-b-later-trial-01")
    assert raised.value.code is AdapterCode.CAMPAIGN_ELAPSED_BUDGET_REACHED
    assert raised.value.dispatch_may_have_occurred is False


def test_a_fenced_dispatch_at_the_binding_is_admission_stopped(tmp_path, monkeypatch):
    _, adapter, meter = real_sdk(tmp_path)

    def reserve(*args, **kwargs):
        raise DispatchStopped("dispatch fenced by campaign control")

    monkeypatch.setattr(meter, "reserve", reserve)
    with pytest.raises(AdapterFailure) as raised:
        run(adapter, "start_research_task", practice())
    assert raised.value.code is AdapterCode.CAMPAIGN_ADMISSION_STOPPED
    assert raised.value.dispatch_may_have_occurred is False


def test_a_reused_operation_id_reads_as_retryable_on_the_wire(tmp_path, monkeypatch):
    from mcp.server.mcpserver.exceptions import ToolError

    from carbon.miner_mcp.standard_server import _create_server

    _, adapter, _ = real_sdk(tmp_path)

    async def started(self, *args, **kwargs):
        return reply("start_research_task")

    monkeypatch.setattr(ResearchMinerTools, "_call", started)
    server = _create_server(adapter)
    first = {**practice(), "operation_id": OPERATION_ID}
    asyncio.run(server.call_tool(PREFIX + "start_research_task", first))
    changed = {**first, "hypothesis": "A different request under the same id"}
    with pytest.raises(ToolError) as raised:
        asyncio.run(server.call_tool(PREFIX + "start_research_task", changed))
    text = str(raised.value)
    assert "OPERATION_ID_REUSED; dispatch_may_have_occurred=false; next_action=" in text
    assert "not retry" not in text.lower()


def test_every_new_code_has_a_next_action_that_does_not_forbid_retrying():
    for code in (
        AdapterCode.CAMPAIGN_ELAPSED_BUDGET_REACHED,
        AdapterCode.CAMPAIGN_ADMISSION_STOPPED,
        AdapterCode.OPERATION_ID_REUSED,
        AdapterCode.TASK_NOT_FOUND,
    ):
        action = serving.NEXT_ACTION[code.value]
        assert "Nothing" in action
        assert "do not retry" not in action.lower()
        assert "never retry" not in action.lower()


# -- 3. Tasks refusals read like the plain tools' ----------------------------


def test_an_unknown_task_is_its_own_code_and_started_nothing(monkeypatch):
    _, adapter = make_adapter(ledger=object())

    async def missing(self, mode, args, identity):
        raise research.ResearchTaskProviderError(
            research.ResearchServiceErrorCode.TASK_NOT_FOUND
        )

    monkeypatch.setattr(ResearchMinerTools, "task_call", missing)
    for observe in (adapter.observe_task, adapter.cancel_task):
        with pytest.raises(AdapterFailure) as raised:
            asyncio.run(observe(TASK_ID))
        assert raised.value.code is AdapterCode.TASK_NOT_FOUND
        assert raised.value.dispatch_may_have_occurred is False


def test_a_task_observation_tells_unavailable_from_retry():
    from carbon.miner_mcp.mcp_extensions import observation_error

    for code in ("TASK_NOT_FOUND", "OWNER_BINDING", "INVALID_RESULT"):
        number, message = observation_error(code)
        # One answer for every unavailable task: no oracle on foreign tasks.
        assert (number, message.split(";")[0]) == (-32602, "TASK_NOT_FOUND")
        assert "retry=false" in message
    for code in (
        "SIGNER_NOT_RUNNING",
        "CAMPAIGN_ADMISSION_STOPPED",
        "OPERATIONAL_STOP",
    ):
        number, message = observation_error(code)
        assert number == -32603
        assert message.startswith(code + "; retry=true; next_action=")


def tasks_extension(adapter, monkeypatch):
    """The real Tasks extension of the real server, negotiation waived."""
    from mcp.server import mcpserver

    from carbon.miner_mcp.mcp_extensions import TASKS_EXTENSION
    from carbon.miner_mcp.standard_server import _create_server

    monkeypatch.setattr(mcpserver, "require_client_extension", lambda ctx, ext: None)
    server = _create_server(adapter)
    (extension,) = [e for e in server._extensions if e.identifier == TASKS_EXTENSION]
    ctx = SimpleNamespace(
        protocol_version="2026-07-28",
        session=SimpleNamespace(
            client_capabilities=SimpleNamespace(extensions={TASKS_EXTENSION: {}})
        ),
    )
    return extension, ctx


def start(extension, ctx, arguments):
    async def plain(_ctx):
        raise AssertionError("the negotiated start never falls through")

    params = SimpleNamespace(name=PREFIX + "start_research_task", arguments=arguments)
    result = asyncio.run(extension.intercept_tool_call(params, ctx, plain))
    return result["content"][0]["text"] if result.get("isError") else result


def test_a_tasks_start_names_the_invalid_field(monkeypatch):
    _, adapter = make_adapter()
    extension, ctx = tasks_extension(adapter, monkeypatch)
    text = start(extension, ctx, {**practice(), "hypothesis": ""})
    assert text.startswith(
        "INVALID_ARGUMENT; dispatch_may_have_occurred=false; field=hypothesis; "
    )
    # A key the caller invented is never echoed back as a field name.
    text = start(extension, ctx, {**practice(), "my_secret_key": 1})
    assert "my_secret_key" not in text and "field=" not in text


def test_a_tasks_start_keeps_the_adapters_own_code(monkeypatch):
    _, adapter = make_adapter()
    extension, ctx = tasks_extension(adapter, monkeypatch)

    async def unsigned(self, request):
        raise AdapterFailure(AdapterCode.SIGNER_NOT_RUNNING)

    monkeypatch.setattr(ResearchToolAdapter, "start_task", unsigned)
    text = start(extension, ctx, practice())
    assert text == serving.refusal(
        "SIGNER_NOT_RUNNING", dispatch_may_have_occurred=False
    )


def test_a_tasks_get_failure_is_retryable_unless_the_task_is_unknown(monkeypatch):
    from mcp.shared.exceptions import MCPError

    _, adapter = make_adapter()
    extension, ctx = tasks_extension(adapter, monkeypatch)
    raised = {"code": AdapterCode.SIGNER_TIMEOUT}

    async def observe(self, task_id):
        raise AdapterFailure(raised["code"])

    monkeypatch.setattr(ResearchToolAdapter, "observe_task", observe)
    params = SimpleNamespace(task_id=TASK_ID)
    with pytest.raises(MCPError) as transient:
        asyncio.run(extension.get(ctx, params))
    assert transient.value.code == -32603
    assert "SIGNER_TIMEOUT; retry=true" in str(transient.value)
    raised["code"] = AdapterCode.TASK_NOT_FOUND
    with pytest.raises(MCPError) as unknown:
        asyncio.run(extension.get(ctx, params))
    assert unknown.value.code == -32602
    assert "TASK_NOT_FOUND; retry=false" in str(unknown.value)


def test_a_tasks_start_without_an_operation_id_gets_one(monkeypatch):
    _, adapter = make_adapter()
    extension, ctx = tasks_extension(adapter, monkeypatch)
    seen = []

    async def started(self, request):
        seen.append(request.operation_id)
        raise AdapterFailure(AdapterCode.NO_CAMPAIGN)

    monkeypatch.setattr(ResearchToolAdapter, "start_task", started)
    start(extension, ctx, practice())
    assert seen and seen[0].startswith("mcp-auto-")


# -- 4. Growing the surface is announced -------------------------------------


def test_the_open_tier_advertises_list_changes():
    from carbon.miner_mcp.open_tier import create_open_tier_server

    capabilities = create_open_tier_server().initialization_options().capabilities
    assert capabilities.tools.list_changed is True
    assert capabilities.prompts.list_changed is True
    assert capabilities.resources.list_changed is True


def test_announce_reaches_both_eras_and_never_fails_the_call():
    from carbon.miner_mcp.open_tier import announce

    sent = []

    class Session:
        async def send_tool_list_changed(self):
            sent.append("session:tools")

        async def send_prompt_list_changed(self):
            raise RuntimeError("closed stream")

    class Context:
        request_context = SimpleNamespace(session=Session())

        async def notify_tools_changed(self):
            sent.append("bus:tools")

        async def notify_prompts_changed(self):
            sent.append("bus:prompts")

    assert asyncio.run(announce(Context(), tools=True, prompts=True)) is True
    assert sent == ["session:tools", "bus:tools", "bus:prompts"]
    assert asyncio.run(announce(None)) is False


def attachable(monkeypatch, *, pause=None):
    """`standard_cli.attached` replaced by a fixture campaign."""
    from carbon.miner_mcp import standard_cli

    @contextlib.asynccontextmanager
    async def attached(configuration, campaign):
        if pause is not None:
            await pause.wait()
        yield make_adapter()[1], None

    monkeypatch.setattr(standard_cli, "attached", attached)


def test_attaching_sends_list_changed_to_a_real_client(monkeypatch):
    from mcp import Client

    from carbon.miner_mcp.mcp_operations import Attachment, make_attachment_tools
    from carbon.miner_mcp.open_tier import create_open_tier_server

    attachable(monkeypatch)
    server = create_open_tier_server()
    attachment = Attachment(server, Path("/nowhere/profile.json"))
    for tool in make_attachment_tools(attachment):
        server._tool_manager._tools[tool.name] = tool
    methods = []

    async def handler(message):
        methods.append(getattr(message, "method", type(message).__name__))

    async def exercise():
        async with Client(server, mode="legacy", message_handler=handler) as client:
            result = await client.call_tool(
                "carbon_attach_campaign", {"campaign": CAMPAIGN}
            )
            assert not result.is_error
            payload = result.structured_content["payload"]
            assert payload["tools_added"] and payload["list_changed_announced"] is True
            assert "carbon_detach_campaign" in payload["next_step"]
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert set(payload["tools_added"]) <= names
            await client.call_tool("carbon_detach_campaign", {})
            for _ in range(20):
                await asyncio.sleep(0)

    asyncio.run(exercise())
    assert "notifications/tools/list_changed" in methods
    assert "notifications/prompts/list_changed" in methods


# -- 5./6. Research tool schemas and descriptions ----------------------------


def research_tools():
    from carbon.miner_mcp.standard_server import _create_server

    server = _create_server(make_adapter()[1])
    return {tool.name: tool for tool in asyncio.run(server.list_tools())}, server


def test_the_start_schema_requires_only_what_every_kind_needs():
    tools, _ = research_tools()
    schema = tools[PREFIX + "start_research_task"].input_schema
    assert set(schema["required"]) == {"kind", "hypothesis", "expected_effect"}
    for name in ("strategy", "action", "arguments"):
        assert schema["properties"][name].get("default", "absent") is None, name
    identity = schema["properties"]["operation_id"]
    assert (identity["minLength"], identity["maxLength"]) == (16, 114)
    assert identity["pattern"] == "^[A-Za-z0-9._:-]{16,114}$"
    assert "idempotent" in identity["description"]


def test_every_research_tool_takes_an_optional_operation_id():
    tools, _ = research_tools()
    for name, tool in tools.items():
        assert "operation_id" not in tool.input_schema.get("required", []), name


def test_the_start_description_lists_each_action_in_object_terms():
    tools, _ = research_tools()
    description = tools[PREFIX + "start_research_task"].description
    assert "public_material {name:" in description
    assert "run_python {source" in description
    assert "_json" not in description
    assert "hypothesis and expected_effect twice" in description


def test_poll_sequence_is_documented():
    tools, _ = research_tools()
    tool = tools[PREFIX + "get_research_result"]
    assert "starts at 0" in tool.description
    assert (
        "0 for the first poll"
        in tool.input_schema["properties"]["poll_sequence"]["description"]
    )


def test_a_call_without_an_operation_id_returns_the_generated_one(monkeypatch):
    _, server = research_tools()
    seen = []

    async def answered(self, name, args, identity, *, transport_request_id=None):
        seen.append(identity)
        return reply("get_challenge_info")

    monkeypatch.setattr(ResearchMinerTools, "call", answered)
    result = asyncio.run(server.call_tool(PREFIX + "get_challenge_info", {}))
    assert result.structured_content["operation_id"] == seen[0]
    assert seen[0].startswith("mcp-auto-")
    # A workspace start needs no strategy, action or arguments it does not use.
    started = asyncio.run(
        server.call_tool(
            PREFIX + "get_challenge_info", {"operation_id": "my-own-retry-key-01"}
        )
    )
    assert started.structured_content["operation_id"] == "my-own-retry-key-01"


# -- 8. Results ---------------------------------------------------------------


def test_an_oversized_result_is_cut_with_a_marker_not_refused(monkeypatch):
    _, adapter = make_adapter()
    big = {
        "text": "x" * (2 * 1024 * 1024),
        "values": list(range(300_000)),
        "task_id": TASK_ID,
    }

    async def answered(*args, **kwargs):
        return {**reply("get_challenge_info"), "public_result": big}

    monkeypatch.setattr(ResearchMinerTools, "call", answered)
    result = run(adapter, "get_challenge_info", {})
    payload = result.payload
    assert len(canonical(payload)) <= 1024 * 1024
    assert payload["public_result"]["task_id"] == TASK_ID
    assert "truncated by Carbon MCP" in payload["public_result"]["text"]
    cut = {entry["path"]: entry for entry in payload["truncation"]["cut"]}
    assert cut["public_result.text"]["kind"] == "string"
    assert payload["truncation"]["marker"] == "truncated by Carbon MCP"


def test_a_result_beyond_the_hard_limit_is_still_refused(monkeypatch):
    _, adapter = make_adapter()

    async def answered(*args, **kwargs):
        return {**reply("get_challenge_info"), "public_result": "x" * (17 * 1024**2)}

    monkeypatch.setattr(ResearchMinerTools, "call", answered)
    with pytest.raises(AdapterFailure, match="INVALID_RESULT"):
        run(adapter, "get_challenge_info", {})


# -- 7./8./9. The operations door ----------------------------------------------


class Host:
    """A campaign host recording what each body received."""

    principal = "miner"

    def __init__(self, refuse_at=None, payload=None):
        self.bodies = []
        self.refuse_at = refuse_at
        self.payload = payload

    def configured(self):
        return {"profile_id": "profile-0123456789", "principal": "miner"}

    def owner(self):
        return {"principal": "miner"}

    def replayed(self, profile, request, operation):
        return None

    def registration(self, profile):
        from scripts.dev.miner_launchpad.controller import Rejected

        if self.refuse_at is not None:
            raise Rejected(self.refuse_at, 409)
        return "registered-miner"

    def owned_campaign(self, identity):
        return {"id": identity, "root": "/nowhere", "kind": "product"}

    def __getattr__(self, name):
        if not name.endswith("_admitted"):
            raise AttributeError(name)

        def body(admitted, request):
            self.bodies.append((name, dict(request)))
            return self.payload if self.payload is not None else {"ok": True}

        return body


def operation_tools(host):
    from carbon.miner_mcp.mcp_operations import make_operation_tools

    return {tool.name: tool for tool in make_operation_tools(host)}


def test_launch_states_its_requirements_and_closed_values():
    tools = operation_tools(Host())
    launch = tools["carbon_launch"].parameters
    assert {"agent", "challenge", "challenge_version"} <= set(launch["required"])
    assert "idempotency_key" not in launch["required"]
    agent = json.dumps(launch["properties"]["agent"])
    for name in ("none", "autonomous", "own-agent", "carbon-autonomous"):
        assert '"' + name + '"' in agent
    halt = json.dumps(tools["carbon_halt"].parameters["properties"]["action"])
    assert all('"' + a + '"' in halt for a in ("stop", "pause", "reconcile"))
    kinds = json.dumps(tools["carbon_note"].parameters["properties"]["note_kind"])
    assert '"reply"' in kinds


def launch_request(**extra):
    return {
        "agent": "own-agent",
        "challenge": "battery",
        "challenge_version": "1.0",
        **extra,
    }


def test_launch_without_a_key_runs_under_a_generated_one_and_returns_it():
    host = Host()
    result = asyncio.run(operation_tools(host)["carbon_launch"].fn(**launch_request()))
    ((_name, request),) = host.bodies
    assert request["idempotency_key"] == result.idempotency_key
    assert (
        result.idempotency_key.startswith("mcp-") and len(result.idempotency_key) == 36
    )
    # Setup's agent name is launch's own value by the time any gate sees it.
    assert request["agent"] == "none"


def test_a_supplied_key_is_used_and_returned_unchanged():
    host = Host()
    key = "my-launch-key-0123456789"
    result = asyncio.run(
        operation_tools(host)["carbon_launch"].fn(**launch_request(idempotency_key=key))
    )
    assert result.idempotency_key == key == host.bodies[0][1]["idempotency_key"]


def test_both_doors_normalise_setups_agent_names():
    from scripts.dev.miner_launchpad.operations import perform

    host = Host()
    perform(
        host,
        "launch",
        launch_request(agent="carbon-autonomous", idempotency_key="k" * 16),
    )
    assert host.bodies[0][1]["agent"] == "autonomous"


@pytest.mark.parametrize(
    "code,field",
    [("signer_not_running", None), ("challenge_required", "challenge")],
)
def test_a_refusal_is_json_with_its_field_and_next_step(code, field):
    from mcp.server.mcpserver.exceptions import ToolError

    tool = operation_tools(Host(refuse_at=code))["carbon_launch"]
    with pytest.raises(ToolError) as raised:
        asyncio.run(tool.fn(**launch_request()))
    body = json.loads(str(raised.value))
    assert body["error"] == code
    assert body.get("field") == field
    assert body["next_step"]


def attached_context(campaign):
    attachment = SimpleNamespace(campaign=campaign)
    return SimpleNamespace(mcp_server=SimpleNamespace(_carbon_attachment=attachment))


@pytest.mark.parametrize(
    "name,request_",
    [
        ("practice", {"strategy": {"k": 1}, "hypothesis": "h"}),
        ("freeze_candidate", {"strategy": {"k": 1}, "reason": "r"}),
        ("submit", {}),
        ("resume", {}),
        ("halt", {"action": "reconcile"}),
    ],
)
def test_while_attached_the_lock_taking_calls_answer_busy_up_front(name, request_):
    from mcp.server.mcpserver.exceptions import ToolError

    host = Host()
    tool = operation_tools(host)["carbon_" + name]
    with pytest.raises(ToolError) as raised:
        asyncio.run(
            tool.fn(ctx=attached_context(CAMPAIGN), campaign=CAMPAIGN, **request_)
        )
    body = json.loads(str(raised.value))
    assert body["error"] == "campaign_busy"
    assert "carbon_detach_campaign" in body["next_step"]
    assert host.bodies == []
    # Another campaign is not held by this session.
    asyncio.run(tool.fn(ctx=attached_context(CAMPAIGN), campaign="e" * 32, **request_))
    assert len(host.bodies) == 1


@pytest.mark.parametrize(
    "name,request_",
    [
        ("observe", {}),
        ("messages", {}),
        ("note", {"note_kind": "plan", "note": "n"}),
        ("run_output", {"task": TASK_ID}),
        ("halt", {"action": "pause"}),
    ],
)
def test_while_attached_reading_and_withdrawing_keep_working(name, request_):
    host = Host()
    tool = operation_tools(host)["carbon_" + name]
    asyncio.run(tool.fn(ctx=attached_context(CAMPAIGN), campaign=CAMPAIGN, **request_))
    assert [body[0] for body in host.bodies] == [name + "_admitted"]


def test_run_output_images_travel_as_image_content():
    from mcp.server import MCPServer

    png = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
    document = {
        "schema": "carbon.control-center.run-output.v1",
        "files": [
            {
                "name": "plot.png",
                "bytes": len(png),
                "media_type": "image/png",
                "image_base64": base64.b64encode(png).decode(),
            },
            {"name": "notes.txt", "bytes": 3, "media_type": None},
        ],
    }
    server = MCPServer(
        "t", tools=list(operation_tools(Host(payload=document)).values())
    )
    result = asyncio.run(
        server.call_tool("carbon_run_output", {"campaign": CAMPAIGN, "task": TASK_ID})
    )
    assert [block.type for block in result.content] == ["text", "image"]
    assert result.content[1].mime_type == "image/png"
    assert base64.b64decode(result.content[1].data) == png
    files = result.structured_content["payload"]["files"]
    assert "image_base64" not in json.dumps(result.structured_content)
    assert files[0]["image_content"] == 1
    assert json.loads(result.content[0].text) == result.structured_content


def test_run_output_no_longer_claims_stderr_is_not_kept():
    from scripts.dev.miner_launchpad.operations import OPERATIONS

    summary = OPERATIONS["run_output"].summary
    assert "keeps no stderr" not in summary
    assert "stdout and stderr" in summary


# -- 9. Attach mode, catalogue, guidance, parallel calls ---------------------


def test_the_attach_path_catalogue_lists_only_offered_extensions():
    from carbon.miner_mcp.mcp_skills import make_skills_extension
    from carbon.miner_mcp.open_tier import attach_campaign, create_open_tier_server

    for extensions, expected in (
        ([], []),
        ([make_skills_extension(guard=None)], ["ResearchSkills"]),
    ):
        server = create_open_tier_server(extensions=extensions)
        attach_campaign(server, make_adapter()[1])
        catalogue = json.loads(
            asyncio.run(server.read_resource(serving.CATALOGUE_URI))[0].content
        )
        assert catalogue["extensions"] == expected


def test_the_standalone_server_still_lists_its_tasks_extension():
    _, server = research_tools()
    catalogue = json.loads(
        asyncio.run(server.read_resource(serving.CATALOGUE_URI))[0].content
    )
    assert "ResearchTasks" in catalogue["extensions"]


def test_the_research_guidance_speaks_of_campaigns_not_grants():
    from carbon.miner_mcp.mcp_skills import DESCRIPTION, SKILL, WORKFLOW

    for text in (DESCRIPTION, SKILL, WORKFLOW):
        assert "grant " not in text and "grant." not in text and "grant/" not in text


def test_parallel_attaches_change_the_session_once(monkeypatch):
    from carbon.miner_mcp.mcp_operations import Attachment, AttachmentBusy
    from carbon.miner_mcp.open_tier import (
        CampaignAlreadyAttached,
        create_open_tier_server,
    )

    async def exercise():
        pause = asyncio.Event()
        attachable(monkeypatch, pause=pause)
        server = create_open_tier_server()
        attachment = Attachment(server, Path("/nowhere/profile.json"))
        first = asyncio.ensure_future(attachment.attach(CAMPAIGN))
        await asyncio.sleep(0)
        with pytest.raises(AttachmentBusy) as busy:
            await attachment.attach("f" * 32)
        assert busy.value.code == "attachment_busy"
        pause.set()
        await first
        with pytest.raises(CampaignAlreadyAttached):
            await attachment.attach("f" * 32)
        assert attachment.campaign == CAMPAIGN
        return attachment

    attachment = asyncio.run(exercise())
    assert attachment.tools


def test_a_detach_under_research_calls_in_flight_is_refused_until_they_return(
    monkeypatch,
):
    from carbon.miner_mcp.mcp_operations import Attachment, AttachmentBusy
    from carbon.miner_mcp.open_tier import create_open_tier_server

    async def exercise():
        attachable(monkeypatch)
        server = create_open_tier_server()
        attachment = Attachment(server, Path("/nowhere/profile.json"))
        await attachment.attach(CAMPAIGN)
        assert await attachment.capacity.acquire()
        with pytest.raises(AttachmentBusy) as busy:
            await attachment.detach(when_idle=True)
        assert busy.value.code == "research_calls_in_flight"
        attachment.capacity.release()
        detached = await attachment.detach(when_idle=True)
        assert detached["detached"] == CAMPAIGN
        # Releasing at the end of a session never waits on the client.
        await attachment.attach(CAMPAIGN)
        assert await attachment.capacity.acquire()
        assert (await attachment.detach())["detached"] == CAMPAIGN

    asyncio.run(exercise())


# -- 4./9. Setup: reconnect, honest status, one attach per review -------------


class Setup:
    def __init__(self, written=True):
        self.profile_path = Path("/home/miner/.carbon/profile.json")
        self.written = written

    def state(self):
        return {
            "registered_hotkey": None,
            "steps": {"review": {"profile_written": self.written}},
        }


def test_a_session_reconnecting_after_review_gets_the_operations():
    from carbon.miner_mcp.mcp_setup import SetupDoor
    from carbon.miner_mcp.open_tier import create_open_tier_server

    attached = []

    def attach(path):
        attached.append(path)
        return ("carbon_launch",)

    door = SetupDoor(create_open_tier_server(), Setup(), attach_operations=attach)
    added = door.install()
    assert "carbon_launch" in added and door.operations
    assert attached == [Setup().profile_path]


def test_an_unusable_profile_at_reconnect_does_not_stop_the_server():
    from carbon.miner_mcp.mcp_setup import SetupDoor
    from carbon.miner_mcp.open_tier import create_open_tier_server

    def broken(path):
        raise ValueError("profile unreadable")

    door = SetupDoor(create_open_tier_server(), Setup(), attach_operations=broken)
    door.install()
    assert not door.operations


def test_parallel_reviews_attach_the_operations_once():
    from carbon.miner_mcp.mcp_setup import SetupDoor
    from carbon.miner_mcp.open_tier import create_open_tier_server

    calls = []

    def attach(path):
        calls.append(path)
        return ("carbon_launch",)

    door = SetupDoor(create_open_tier_server(), Setup(), attach_operations=attach)
    reviewed = {"steps": {"review": {"profile_written": True}}}

    async def both():
        return await asyncio.gather(
            door.after("review", reviewed), door.after("review", reviewed)
        )

    results = asyncio.run(both())
    assert len(calls) == 1
    assert sorted(map(len, results)) == [0, 1]


@pytest.mark.parametrize("available", [True, False])
def test_setup_status_says_where_launch_is(available):
    from scripts.dev.miner_launchpad.setup_operations import MCP, _launch_call

    call = _launch_call(Setup(), MCP, available)
    assert call["tool"] == "carbon_launch"
    assert call["in_this_session"] is available
    assert "carbon_operations" not in json.dumps(call)
    if not available:
        assert call["reconnect"] == (
            "carbon-mcp --configuration /home/miner/.carbon/profile.json"
        )


def test_the_compute_schema_says_challenge_is_for_the_gpu_choice():
    from scripts.dev.miner_launchpad.setup_operations import FIELDS, NEXT_STEPS

    assert "challenge_is_for_the_gpu_choice" in FIELDS["challenge"][1]
    assert "GPU choice" in FIELDS["challenge"][1]
    assert NEXT_STEPS["challenge_is_for_the_gpu_choice"]
