"""Miner setup, agent first (OWNER-MINER-SETUP-AGENT-FIRST-01).

The owner, 2026-10-02: "yes make this more agent first and easy for an agent
to automate". These tests hold:
- door parity: the browser's routes and the MCP tools come from one table,
  with the same arguments (the browser alone may paste a key), the same
  refusals and the same records, each door seeing the other's progress;
- the order, with Inference skipped for the miner's own agent;
- a model key reaches the MCP door only as an owner-only file;
- the miner's own steps (signer, registration) answer human_action_required;
- an agent loop driven only by status reaches launch, against a stub
  registered miner;
- no key material in any result or record.
No chain, provider, signer or container is reached: the checks are fixtures.
"""

from __future__ import annotations

import asyncio
import http.client
import json
import os
import threading
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from test_miner_launchpad_environment_setup import HOTKEY, Checks, Onboarding

from carbon.miner_mcp.mcp_setup import STATUS, WORKFLOW_PROMPT, SetupDoor
from carbon.miner_mcp.open_tier import attach_operations, create_open_tier_server
from scripts.dev.miner_launchpad import controller, installed
from scripts.dev.miner_launchpad.environment_setup import (
    NO_MODEL_KEY,
    OWN_AGENT,
    EnvironmentSetup,
    SetupRefused,
)
from scripts.dev.miner_launchpad.setup_operations import (
    HTTP,
    MCP,
    ORDER,
    SETUP_OPERATIONS,
    perform,
    schema,
)

TOKEN = "s" * 40
KEY = "sk-agent-first-fixture-never-echoed"
OTHER = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"


class Chain(Onboarding):
    """A stub chain whose registration the test can make happen."""

    def __init__(self, registered=False):
        super().__init__(registered)

    def confirm(self, address):
        ok = self.registered and address == HOTKEY
        return {"registered": ok, "confirmed": ok}


class Signer(Checks):
    """Fixture checks with a signer the miner may not have started yet."""

    def __init__(self, running=True):
        super().__init__()
        self.running = running

    def agent(self, hotkey, socket_path=None):
        if not self.running:
            raise SetupRefused("signer", "signer_not_running")
        return super().agent(hotkey, socket_path)


def made(tmp_path):
    """The installer's record of this machine's images, and the state dir."""
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    images = tmp_path / "images"
    images.mkdir()
    for name in ("worker.json", "analysis.json"):
        (images / name).write_text("{}")
    installed.write(
        state,
        image_manifest=images / "worker.json",
        analysis_image_manifest=images / "analysis.json",
    )
    return state


def model_key_file(tmp_path, mode=0o600, name="model.key"):
    path = tmp_path / name
    path.write_text(KEY + "\n")
    path.chmod(mode)
    return path


class Host:
    """The operations' host, as far as building their tools needs."""

    def recent(self):
        return []


def door(state, checks, chain):
    server = create_open_tier_server()
    setup = EnvironmentSetup(state, onboarding=chain, checks=checks)

    def attach(path):
        from carbon.miner_mcp.mcp_operations import Attachment

        return attach_operations(server, Host(), Attachment(server, path))

    setup_door = SetupDoor(server, setup, attach_operations=attach)
    setup_door.install()
    return server, setup, setup_door


def names(server):
    return {tool.name for tool in asyncio.run(server.list_tools())}


def call(server, name, arguments):
    result = asyncio.run(server.call_tool(name, arguments))
    assert not result.is_error
    return result.structured_content


def refusal(server, name, arguments):
    """The closed refusal a client branches on: JSON, never an argument."""
    with pytest.raises(ToolError) as raised:
        asyncio.run(server.call_tool(name, arguments))
    message = str(raised.value)
    return json.loads(message[message.index("{") :])


def rejected(server, name, arguments):
    """Arguments the tool's schema does not take never reach the step."""
    try:
        result = asyncio.run(server.call_tool(name, arguments))
    except ToolError:
        return True
    return result.is_error


# --- one table, two doors -------------------------------------------------------------


def test_the_tools_and_routes_are_the_one_table(tmp_path):
    from scripts.dev.miner_launchpad.setup_operations import OPEN, REGISTERED

    server, _, _ = door(made(tmp_path), Checks(), Chain(registered=True))
    open_tools = {
        "carbon_setup_" + n for n, op in SETUP_OPERATIONS.items() if op.tier == OPEN
    }
    later = {
        "carbon_setup_" + n
        for n, op in SETUP_OPERATIONS.items()
        if op.tier == REGISTERED
    }
    live = names(server)
    # Before registration the later steps are absent, not refusing.
    assert {STATUS} | open_tools <= live and not later & live
    added = call(server, "carbon_setup_begin", {"address": HOTKEY})["tools_added"]
    assert set(added) == later and later <= names(server)
    # Each tool's arguments are its table schema for the MCP door; the browser
    # door's differ only by the key it may paste.
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    for name, op in SETUP_OPERATIONS.items():
        mcp, http_ = schema(name, MCP), schema(name, HTTP)
        listed = tools["carbon_setup_" + name].input_schema
        assert set(listed["properties"]) == set(mcp["properties"]), name
        assert set(listed.get("required", [])) == set(mcp["required"]), name
        assert set(http_["properties"]) - set(mcp["properties"]) == set(op.browser_only)
    assert {n for n, op in SETUP_OPERATIONS.items() if op.browser_only} == {"inference"}
    assert "key" not in tools["carbon_setup_inference"].input_schema["properties"]


@pytest.fixture
def page(tmp_path):
    """The Control Center over the same state dir an MCP door uses."""
    state = made(tmp_path)
    checks = Checks()
    served = controller.Server(
        controller.Controller(tmp_path / "runs.sqlite3"),
        TOKEN,
        port=0,
        onboarding=Chain(registered=True),
        state_dir=state,
        setup_checks=checks,
    )
    served.setup.attach = lambda path: True
    thread = threading.Thread(target=served.serve_forever, daemon=True)
    thread.start()
    yield served, state, checks
    served.shutdown()
    served.server_close()
    thread.join(timeout=3)


def http_call(served, method, path, body=None):
    connection = http.client.HTTPConnection("127.0.0.1", served.server_port, timeout=10)
    headers = {"Authorization": "Bearer " + TOKEN}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    connection.request(method, path, body=data, headers=headers)
    response = connection.getresponse()
    result = (response.status, json.loads(response.read()))
    connection.close()
    return result


def test_both_doors_refuse_alike_and_see_each_others_progress(page):
    served, state, checks = page
    server, _, _ = door(state, checks, Chain(registered=True))
    # Every table operation is a route; nothing else is.
    for name in SETUP_OPERATIONS:
        status, _ = http_call(served, "POST", "/api/v1/setup/" + name, {})
        assert status != 404, name
    assert http_call(served, "POST", "/api/v1/setup/elsewhere", {})[0] == 404
    # The same refusal, closed, with its field and next step, on either door.
    phrase = {"address": "bottom drive obey lake curtain smoke"}
    status, body = http_call(served, "POST", "/api/v1/setup/begin", phrase)
    assert status == 409
    assert refusal(server, "carbon_setup_begin", phrase) == body
    assert body["error"] == "hotkey_address_required" and body["next_step"]
    # The agent registers over MCP; the page's status shows it.
    call(server, "carbon_setup_begin", {"address": HOTKEY})
    status, page_view = http_call(served, "GET", "/api/v1/setup/status")
    assert status == 200 and "register" in page_view["done"]
    # The page chooses the agent; the agent's status shows it.
    status, _ = http_call(served, "POST", "/api/v1/setup/agent", {"choice": OWN_AGENT})
    assert status == 200
    agent_view = call(server, STATUS, {})["payload"]
    assert "agent" in agent_view["done"]
    # The two views agree on every step, door aside.
    status, page_view = http_call(served, "GET", "/api/v1/setup/status")
    assert [(r["id"], r["state"]) for r in page_view["steps"]] == [
        (r["id"], r["state"]) for r in agent_view["steps"]
    ]


# --- the order, and Inference skipped for your own agent ------------------------------


def test_the_order_and_the_inference_skip(tmp_path):
    state = made(tmp_path)
    setup = EnvironmentSetup(state, onboarding=Chain(registered=True), checks=Checks())
    from scripts.dev.miner_launchpad.setup_operations import status

    view = status(setup, door=MCP)
    assert (
        [row["id"] for row in view["steps"]]
        == list(ORDER)
        == [
            "signer",
            "register",
            "agent",
            "inference",
            "compute",
            "review",
        ]
    )
    setup.begin({"address": HOTKEY})
    setup.signer({"address": HOTKEY})
    # Who researches comes next, before Inference.
    assert status(setup, door=MCP)["next"]["step"] == "agent"
    setup.agent({"choice": OWN_AGENT})
    view = status(setup, door=MCP)
    inference = next(row for row in view["steps"] if row["id"] == "inference")
    assert inference == {
        "id": "inference",
        "title": "Inference",
        "state": "skipped",
        "why": "your agent uses its own model",
    }
    assert view["next"]["step"] == "compute"
    images = view["next"]["options"]
    setup.compute(
        {
            "choice": "this-machine-cpu",
            "image_manifest": images["image_manifest"],
            "analysis_image_manifest": images["analysis_image_manifest"],
        }
    )
    assert setup.state()["steps"]["review"]["ready"] is True
    setup.review({"confirm": True})
    profile = json.loads(setup.profile_path.read_bytes())
    # No model was chosen in setup: Carbon's agent stays unavailable.
    assert "model_selection" not in profile and "provider_credentials" not in profile
    assert profile["paths"]["api_key_file"].endswith(NO_MODEL_KEY)
    assert not Path(profile["paths"]["api_key_file"]).exists()
    assert status(setup, door=MCP)["next"]["step"] == "launch"

    # Carbon's agent calls setup's model: Inference is needed, and Review
    # waits for it.
    second = tmp_path / "second"
    second.mkdir()
    state2 = made(second)
    other = EnvironmentSetup(state2, onboarding=Chain(registered=True), checks=Checks())
    other.begin({"address": HOTKEY})
    other.agent({"choice": "carbon-graphite"})
    view = status(other, door=MCP)
    assert view["next"]["step"] == "inference"
    assert view["next"]["before"]["tool"] == "carbon_setup_quote"
    review = next(row for row in view["steps"] if row["id"] == "review")
    assert review["state"] == "waiting" and review["after"] == "inference"
    assert other.state()["steps"]["review"]["ready"] is False


# --- the model key: a file on the MCP door, never a value ------------------------------


def test_a_key_reaches_the_mcp_door_only_as_an_owner_only_file(tmp_path):
    state = made(tmp_path)
    checks = Checks()
    server, setup, _ = door(state, checks, Chain(registered=True))
    call(server, "carbon_setup_begin", {"address": HOTKEY})
    quote = call(
        server,
        "carbon_setup_quote",
        {"provider_id": "engy-chat", "model_id": "deepseek-v4-flash-0731"},
    )["payload"]
    base = {
        "provider_id": "engy-chat",
        "model_id": "deepseek-v4-flash-0731",
        "consent": {"max_cost_nano": quote["max_cost_nano"]},
    }
    # A key value is not an argument of this door at all ...
    assert rejected(server, "carbon_setup_inference", {**base, "key": KEY})
    # ... and the shared operation refuses it by name for this door.
    with pytest.raises(SetupRefused) as refused:
        perform(setup, "inference", {**base, "key": KEY}, door=MCP)
    assert refused.value.code == "key_must_be_a_file_on_this_door"
    # Only an owner-only regular file, owned by this user, is accepted.
    target = model_key_file(tmp_path)
    link = tmp_path / "link.key"
    link.symlink_to(target)
    folder = tmp_path / "folder.key"
    folder.mkdir(mode=0o700)
    for path, code in (
        (tmp_path / "absent.key", "model_key_file_not_found"),
        (link, "model_key_file_not_owner_only"),
        (
            model_key_file(tmp_path, 0o640, "shared.key"),
            "model_key_file_not_owner_only",
        ),
        (model_key_file(tmp_path, 0o604, "world.key"), "model_key_file_not_owner_only"),
        (folder, "model_key_file_not_owner_only"),
    ):
        body = refusal(
            server, "carbon_setup_inference", {**base, "model_key_file": str(path)}
        )
        assert (body["error"], body["field"]) == (code, "model_key_file"), path
        assert body["next_step"]
    body = refusal(
        server, "carbon_setup_inference", {**base, "model_key_file": "model.key"}
    )
    assert body["error"] == "absolute_path_required"
    assert [c for c in checks.calls if c[0] == "inference"] == []
    # The miner's file: checked with that path, referenced, never copied.
    result = call(
        server, "carbon_setup_inference", {**base, "model_key_file": str(target)}
    )
    assert checks.calls[-1] == ("inference", "engy-chat", target)
    assert result["payload"]["steps"]["inference"]["checked"] is True
    assert not (setup.root / "keys" / "engy-chat.key").exists()
    # The browser keeps its paste-once field; a key and a file at once is
    # refused.
    with pytest.raises(SetupRefused) as refused:
        perform(
            setup,
            "inference",
            {**base, "key": KEY, "model_key_file": str(target)},
            door=HTTP,
        )
    assert refused.value.code == "key_or_model_key_file_not_both"
    assert (
        target.stat().st_mode & 0o777 == 0o600 and os.getuid() == target.stat().st_uid
    )


# --- the miner's own steps ------------------------------------------------------------


def test_the_signer_and_the_registration_are_the_miners_to_do(tmp_path):
    state = made(tmp_path)
    signer, chain = Signer(running=False), Chain(registered=False)
    setup = EnvironmentSetup(state, onboarding=chain, checks=signer)
    for door_name in (HTTP, MCP):
        started = perform(setup, "signer", {"address": HOTKEY}, door=door_name)
        assert started["result"] == "human_action_required"
        assert (started["step"], started["action"]) == ("signer", "start_signer")
        assert "carbon-miner-signer" in started["command"]
        assert started["then"]["tool"] == "carbon_setup_signer"
        registered = perform(setup, "begin", {"address": HOTKEY}, door=door_name)
        assert (registered["result"], registered["action"]) == (
            "human_action_required",
            "sign_registration",
        )
        assert "carbon_onboarding_prepare" in registered["instruction"]
    # Nothing was marked done; status names both, each with its human step.
    from scripts.dev.miner_launchpad.setup_operations import status

    view = status(setup, door=MCP)
    assert view["done"] == []
    assert view["next"]["step"] == "signer"
    assert view["next"]["human_action_required"]["action"] == "start_signer"
    # The miner acts; the same calls now succeed.
    signer.running, chain.registered = True, True
    assert perform(setup, "signer", {"address": HOTKEY}, door=MCP)["steps"]["signer"][
        "checked"
    ]
    assert (
        perform(setup, "begin", {"address": HOTKEY}, door=MCP)["registered_hotkey"]
        == HOTKEY
    )
    assert status(setup, door=MCP)["done"] == ["signer", "register"]


# --- an agent's loop, driven only by status -------------------------------------------


def arguments_for(entry, *, address, key_path=None):
    """What an agent sends for a status entry: ids from its options, values
    the miner gave it (their public address, their key file's path)."""
    step = entry["step"]
    if step in ("signer", "register"):
        chosen = {"address": address}
    elif step == "agent":
        assert OWN_AGENT in [c["id"] for c in entry["options"]["choice"]]
        chosen = {"choice": OWN_AGENT}
    elif step == "compute" and "consent" in entry:
        chosen = {"consent": entry["consent"]}
    elif step == "compute":
        options = entry["options"]
        chosen = {
            "choice": options["choice"][0],
            "image_manifest": options["image_manifest"],
            "analysis_image_manifest": options["analysis_image_manifest"],
        }
    elif step == "review":
        chosen = {"confirm": True}
    else:
        raise AssertionError(f"no rule for {step}")
    allowed = entry["call"]["arguments"]["properties"]
    assert set(chosen) <= set(allowed), (step, chosen)
    return chosen


def test_an_agent_loop_driven_only_by_status_reaches_launch(tmp_path):
    state = made(tmp_path)
    signer, chain = Signer(running=False), Chain(registered=False)
    server, setup, _ = door(state, signer, chain)
    seen, results = [], []
    for _ in range(20):
        view = call(server, STATUS, {})["payload"]
        entry = view["next"]
        if entry["step"] == "launch":
            break
        seen.append(entry["step"])
        tool = entry["call"]["tool"]
        assert tool in names(server), tool
        result = call(server, tool, arguments_for(entry, address=HOTKEY))
        results.append(result)
        if result["payload"].get("result") == "human_action_required":
            # The agent tells the miner; the miner does it.
            if result["payload"]["step"] == "signer":
                signer.running = True
            else:
                chain.registered = True
    else:
        raise AssertionError(f"no launch after {seen}")
    assert seen == [
        "signer",
        "signer",
        "register",
        "register",
        "agent",
        "compute",
        "review",
    ]
    assert (
        entry
        == {
            "step": "launch",
            "done": False,
            "call": entry["call"],
        }
        and entry["call"]["tool"] == "carbon_launch"
    )
    # Review attached the registered tier in this session.
    assert results[-1]["tools_added"] and "carbon_launch" in names(server)
    assert {"carbon_attach_campaign", "carbon_observe"} <= names(server)
    # The workflow prompt states the loop.
    prompt = asyncio.run(server.get_prompt(WORKFLOW_PROMPT, {}))
    assert "carbon_setup_status" in str(prompt)
    # No key material anywhere an agent or a file can see it.
    blob = json.dumps(results) + json.dumps(view)
    for path in setup.root.rglob("*"):
        if path.is_file():
            blob += path.read_text(errors="ignore")
    for forbidden in ("mnemonic", "seed phrase", 'password"', "private_key", KEY):
        assert forbidden not in blob, forbidden


def test_no_key_material_in_results_or_records(tmp_path):
    state = made(tmp_path)
    server, setup, _ = door(state, Checks(), Chain(registered=True))
    target = model_key_file(tmp_path)
    outputs = [
        call(server, "carbon_setup_begin", {"address": HOTKEY}),
        call(server, "carbon_setup_agent", {"choice": "carbon-graphite"}),
    ]
    quote = call(
        server,
        "carbon_setup_quote",
        {"provider_id": "engy-chat", "model_id": "deepseek-v4-flash-0731"},
    )
    outputs += [
        quote,
        call(
            server,
            "carbon_setup_inference",
            {
                "provider_id": "engy-chat",
                "model_id": "deepseek-v4-flash-0731",
                "consent": {"max_cost_nano": quote["payload"]["max_cost_nano"]},
                "model_key_file": str(target),
            },
        ),
        call(server, STATUS, {}),
    ]
    text = json.dumps(outputs)
    for path in setup.root.rglob("*"):
        if path.is_file():
            text += path.read_text(errors="ignore")
    assert KEY not in text
    # The key file is referenced by its path, which is not secret.
    assert str(target) in (setup.root / "setup.json").read_text()
