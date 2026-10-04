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
from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS

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

    def replayed(self, profile, request, operation):
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

        # The browser's refusal carries the catalog's next step (LP-PROD-C
        # D8, review repair); the MCP door's refusal names the same code.
        assert (code, body) == (
            403,
            {
                "error": "registration_required",
                "next_step": NEXT_ACTIONS["registration_required"],
            },
        )
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
    # The catalog's step, as the MCP door gives it for the same code (W1).
    assert (code, body) == (
        400,
        {
            "error": "closed_request_required",
            "next_step": NEXT_ACTIONS["closed_request_required"],
        },
    )
    code, body = through_browser(browser, SpyHost(), "official_submit", {})
    assert (code, body) == (404, {"error": "unknown_operation"})
    assert PREFIX + "official_submit" not in {
        t.name for t in make_operation_tools(SpyHost())
    }


class RefusingHost(SpyHost):
    """A host whose operation bodies refuse with one closed code."""

    def __init__(self, code):
        super().__init__()
        self.code = code

    def __getattr__(self, name):
        if not name.endswith("_admitted"):
            raise AttributeError(name)

        def body(admitted, request):
            raise launchpad.Rejected(self.code, 409)

        return body


@pytest.mark.parametrize(
    "code",
    [
        # C's catalog codes the MCP door used to answer with a generic step.
        "evaluation_unavailable",
        "candidate_awaits_submission",
        "practice_result_required",
        # B's codes the browser's door used to answer with no step at all.
        "challenge_required",
        "invalid_budget",
        # LP-PROD-G's intake codes, wherever a door meets one.
        "intake_mismatch",
        "AUTH_STALE",
    ],
)
def test_a_refusal_reads_the_same_next_step_at_both_doors(browser, code):
    """W1: one catalog of next steps (`supervisor.NEXT_ACTIONS`) for both
    doors. The MCP door adds only the field to correct."""
    from mcp.server.mcpserver.exceptions import ToolError

    from scripts.dev.miner_launchpad.operations import REFUSAL_FIELDS

    op = OPERATIONS["submit"]
    status, body = through_browser(browser, RefusingHost(code), op.name, sample(op))
    assert (status, body) == (409, {"error": code, "next_step": NEXT_ACTIONS[code]})
    with pytest.raises(ToolError) as refused:
        through_mcp(RefusingHost(code), op.name, sample(op))
    answered = json.loads(str(refused.value))
    assert answered["error"] == code
    assert answered["next_step"] == NEXT_ACTIONS[code]
    assert answered.get("field") == REFUSAL_FIELDS.get(code)


class SteppedHost(SpyHost):
    """A host whose operation bodies refuse with a code and its own next step
    (`runner.stepped`), as the reconcile action's settlement refusal and the
    stale-profile refusal do."""

    def __init__(self, code, step):
        super().__init__()
        self.code, self.step = code, step

    def __getattr__(self, name):
        if not name.endswith("_admitted"):
            raise AttributeError(name)

        def body(admitted, request):
            from scripts.dev.miner_launchpad.runner import stepped

            raise stepped(self.code, self.step)

        return body


def _stepped_cases():
    from carbon.development_session.research_agent import SETTLEMENT_REFUSALS
    from scripts.dev.miner_launchpad.runner import CARBON_UPDATED

    return [
        *SETTLEMENT_REFUSALS.items(),
        # What `install_refusal` computes: the step that clears it, and why.
        (
            CARBON_UPDATED,
            (
                "check Compute again in setup, then review to write your "
                "profile again: the worker image was rebuilt since this "
                "profile was written"
            ),
        ),
    ]


@pytest.mark.parametrize(
    ("code", "step"), _stepped_cases(), ids=[code for code, _ in _stepped_cases()]
)
def test_a_refusal_with_its_own_step_reads_the_same_at_both_doors(browser, code, step):
    """Review repair: the browser's door sent a refusal's own step
    (`controller.error_body` reads `next_step`); the MCP door read only the
    catalog, so a settlement refusal over `carbon_halt action=reconcile` read
    the fallback and a stale profile read "re-run the installer". Both doors
    now send the refusal's own step."""
    from mcp.server.mcpserver.exceptions import ToolError

    from scripts.dev.miner_launchpad.operations import REFUSAL_FIELDS

    body = {"campaign": SAMPLE["string"], "action": "reconcile"}
    status, answered = through_browser(browser, SteppedHost(code, step), "halt", body)
    assert (status, answered) == (409, {"error": code, "next_step": step})
    with pytest.raises(ToolError) as refused:
        through_mcp(SteppedHost(code, step), "halt", body)
    assert json.loads(str(refused.value)) == {
        "error": code,
        "next_step": step,
        **({"field": REFUSAL_FIELDS[code]} if code in REFUSAL_FIELDS else {}),
    }
    # The step is the refusal's, not the catalog's for its code.
    assert step != NEXT_ACTIONS[code]


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
