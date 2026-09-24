"""Neither door holds an operation or a gate the other lacks - by construction.

Every test here iterates the operations table itself. An operation added to
the table is exercised through both doors without anyone editing this file,
and there is nowhere to add one to a single door: the browser route and the
MCP tools are both generated from the table. So what these tests pin is that
the generation holds - the same gates, in the same order, reaching the same
body with the same request, through a real HTTP server and real MCP tools.
"""

import asyncio
import json
import threading

import pytest
from test_miner_launchpad import auth, request

from carbon.development_session.chain_onboarding import OnboardingFailure
from carbon.miner_mcp.mcp_operations import PREFIX, make_operation_tools
from scripts.dev.miner_launchpad import controller as launchpad
from scripts.dev.miner_launchpad.operations import (
    FIELDS,
    OPERATIONS,
    Admitted,
    Operation,
    describe,
)

SAMPLE = {"string": "value-0123456789abcdef", "boolean": False, "object": {"k": 1}}


class SpyHost:
    """A campaign host that records every gate and body it is asked for."""

    principal = "miner"

    def __init__(self, registered=True):
        self.calls = []
        self.registered = registered

    def configured(self):
        self.calls.append("profile")
        return {"profile_id": "value-0123456789abcdef", "principal": "miner"}

    def owner(self):
        self.calls.append("owner")
        return {"principal": "miner"}

    def replayed(self, profile, request):
        self.calls.append("replay")

    def registration(self, profile):
        self.calls.append("registration")
        if not self.registered:
            raise OnboardingFailure("NOT_REGISTERED", next_action="register")
        return "registered-miner"

    def owned_campaign(self, identity):
        self.calls.append("campaign")
        return {"id": identity, "root": "/nowhere", "kind": "product"}

    def __getattr__(self, name):
        if not name.endswith("_admitted"):
            raise AttributeError(name)

        def body(admitted, request):
            assert type(admitted) is Admitted
            self.calls.append("body:" + name)
            return {"body": name, "request": request}

        return body


def sample(op):
    return {field: SAMPLE[FIELDS[field][0]] for field in sorted(op.required)}


@pytest.fixture
def browser(tmp_path):
    def serve(host):
        server = launchpad.Server(
            launchpad.Controller(tmp_path / "launchpad.sqlite3"),
            "x" * 40,
            port=0,
            research_runner=host,
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server

    servers = []
    yield serve
    for server in servers:
        server.shutdown()
        server.server_close()


def through_browser(browser, host, name, body):
    code, _, content = request(
        browser(host), "/api/v1/operations/" + name, "POST", body, auth()
    )
    return code, json.loads(content)


def through_mcp(host, name, body):
    tool = {t.name: t for t in make_operation_tools(host)}[PREFIX + name]
    return asyncio.run(tool.fn(**body))


@pytest.mark.parametrize("name", list(OPERATIONS))
def test_both_doors_run_the_same_gates_to_the_same_body(browser, name):
    op = OPERATIONS[name]
    via_browser, via_mcp = SpyHost(), SpyHost()
    code, body = through_browser(browser, via_browser, name, sample(op))
    result = through_mcp(via_mcp, name, sample(op))
    assert code == 200, body
    assert via_browser.calls == via_mcp.calls
    assert body == result.payload
    # The gates the table declares are the gates that ran, in its order.
    expected = [g for g in op.gates if g not in ("request",)]
    ran = [c for c in via_browser.calls if not c.startswith("body:")]
    assert [("profile" if c == "owner" else c) for c in ran] == expected
    assert via_browser.calls[-1] == "body:" + name + "_admitted"


@pytest.mark.parametrize("name", list(OPERATIONS))
def test_an_unregistered_miner_is_refused_new_work_on_both_doors(browser, name):
    op = OPERATIONS[name]
    via_browser, via_mcp = SpyHost(registered=False), SpyHost(registered=False)
    code, body = through_browser(browser, via_browser, name, sample(op))
    if op.admits_work:
        from mcp.server.mcpserver.exceptions import ToolError

        assert (code, body) == (403, {"error": "registration_required"})
        with pytest.raises(ToolError, match="registration_required"):
            through_mcp(via_mcp, name, sample(op))
        for calls in (via_browser.calls, via_mcp.calls):
            assert not [c for c in calls if c.startswith("body:")]
    else:
        # Specimen: reading and withdrawing never needed registration.
        assert code == 200
        assert through_mcp(via_mcp, name, sample(op)).payload == body


def test_the_doors_list_exactly_the_table(browser):
    tools = {t.name for t in make_operation_tools(SpyHost())}
    assert tools == {PREFIX + name for name in OPERATIONS}
    code, _, content = request(browser(SpyHost()), "/api/v1/operations", headers=auth())
    assert code == 200 and json.loads(content) == {"operations": describe()}


def test_a_request_outside_the_table_is_refused_on_both_doors(browser):
    op = OPERATIONS["freeze_candidate"]
    extra = {**sample(op), "official": True}
    code, body = through_browser(browser, SpyHost(), op.name, extra)
    assert (code, body) == (400, {"error": "closed_request_required"})
    code, body = through_browser(browser, SpyHost(), "official_submit", {})
    assert (code, body) == (404, {"error": "unknown_operation"})
    assert PREFIX + "official_submit" not in {
        t.name for t in make_operation_tools(SpyHost())
    }


def test_an_operation_that_admits_work_cannot_skip_registration():
    kwargs = {
        "summary": "x",
        "required": frozenset({"campaign"}),
        "optional": frozenset(),
    }
    with pytest.raises(ValueError, match="registration"):
        Operation("sneaky", gates=("request", "profile", "campaign"), **kwargs)
    with pytest.raises(ValueError, match="order"):
        Operation(
            "sneaky",
            gates=("request", "profile", "campaign", "registration"),
            **kwargs,
        )
    with pytest.raises(ValueError, match="FIELDS"):
        Operation(
            "sneaky",
            gates=("request", "profile", "registration"),
            **{**kwargs, "required": frozenset({"undeclared"})},
        )
    # Specimen: the same operation with registration ahead of its body builds.
    assert Operation(
        "fine", gates=("request", "profile", "registration", "campaign"), **kwargs
    )


def test_a_body_cannot_be_reached_without_perform():
    with pytest.raises(TypeError):
        Admitted(object(), SpyHost(), {}, "miner", None)
