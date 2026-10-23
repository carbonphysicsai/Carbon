"""Practice-only setup: practise without registering (LP practice-only).

A miner who chose Setup's "Practise without registering" freezes, submits
and commits nothing: both doors refuse `registration_required`, typed, with
the steps that register, before a replay or the chain is read and before any
body runs. Setup's first step offers the choice on both doors; taking it asks
no chain, signer or wallet, and nothing leaves the machine. Registering later
keeps the steps checked. A registered profile keeps every path it had.

The practice-only runner profile itself (its typed identity and local
authentication) is not here yet: Review refuses `practice_profile_unavailable`
until it is.
"""

from __future__ import annotations

import asyncio
import socket

import pytest
from no_outbound import OutboundBlocked, no_outbound
from test_miner_launchpad_environment_setup import HOTKEY, Checks
from test_miner_operations_doors import (
    SpyHost,
    browser,  # noqa: F401 - the fixture
    sample,
    through_browser,
    through_mcp,
)
from test_miner_setup_agent_first import Chain, call, door, made, names, refusal

from scripts.dev.miner_launchpad import practice_only
from scripts.dev.miner_launchpad.controller import Rejected
from scripts.dev.miner_launchpad.environment_setup import (
    OWN_AGENT,
    EnvironmentSetup,
    SetupRefused,
)
from scripts.dev.miner_launchpad.operations import _TOKEN, OPERATIONS, Admitted
from scripts.dev.miner_launchpad.setup_operations import (
    HTTP,
    MCP,
    SETUP_OPERATIONS,
    perform,
    status,
)
from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS

PRACTICE_IDENTITY = {"kind": "PRACTICE_ONLY", "public_key": "ab" * 32}


class PracticeHost(SpyHost):
    """A campaign host whose profile is a practice-only one."""

    def configured(self):
        self.calls.append("profile")
        return {
            "profile_id": "value-0123456789abcdef",
            "principal": "practice:" + PRACTICE_IDENTITY["public_key"],
            "practice_identity": PRACTICE_IDENTITY,
        }


# --- freeze, submit and commit need a registration --------------------------------


def test_the_registered_only_operations_are_the_table_s_signing_ones():
    assert practice_only.REGISTERED_ONLY == {"freeze_candidate", "submit", "commit"}
    assert practice_only.REGISTERED_ONLY <= set(OPERATIONS)
    assert all(OPERATIONS[name].admits_work for name in practice_only.REGISTERED_ONLY)


@pytest.mark.parametrize("name", sorted(practice_only.REGISTERED_ONLY))
def test_a_practice_only_profile_is_refused_on_both_doors_before_anything(
    browser,  # noqa: F811 - the fixture
    name,
):
    from mcp.server.mcpserver.exceptions import ToolError

    op = OPERATIONS[name]
    via_browser, via_mcp = PracticeHost(), PracticeHost()
    code, body = through_browser(browser, via_browser, name, sample(op))
    assert (code, body) == (
        403,
        {
            "error": "registration_required",
            "next_step": NEXT_ACTIONS["registration_required"],
        },
    )
    with pytest.raises(ToolError, match="registration_required"):
        through_mcp(via_mcp, name, sample(op))
    # Refused at the profile: no replay, no chain read, no body.
    assert via_browser.calls == via_mcp.calls == ["profile"]
    step = NEXT_ACTIONS["registration_required"]
    for words in ("carbon_setup_begin", "signer", "carbon_setup_review"):
        assert words in step


@pytest.mark.parametrize(
    "name", sorted(set(OPERATIONS) - practice_only.REGISTERED_ONLY)
)
def test_every_other_operation_is_not_refused_by_the_practice_gate(
    browser,  # noqa: F811 - the fixture
    name,
):
    op = OPERATIONS[name]
    via_browser = PracticeHost()
    code, body = through_browser(browser, via_browser, name, sample(op))
    assert code == 200, body
    assert via_browser.calls[-1] == "body:" + name + "_admitted"


@pytest.mark.parametrize(
    "profile",
    [
        {"principal": HOTKEY},
        {"principal": HOTKEY, "practice_identity": None},
        {"principal": HOTKEY, "practice_identity": {"kind": "REGISTERED"}},
        {"principal": HOTKEY, "practice_identity": "PRACTICE_ONLY"},
        None,
    ],
)
def test_a_registered_profile_keeps_every_path(profile):
    assert not practice_only.is_practice_only(profile)
    for name in practice_only.REGISTERED_ONLY:
        practice_only.require_registered(profile, name)


@pytest.mark.parametrize("operation", ["freeze_candidate", "submit", "commit"])
def test_the_runner_starts_no_signing_work_for_a_practice_only_profile(operation):
    """Whatever reached it - a door, a resume's retry - the runner's own
    background start refuses before it touches its campaign or lock."""
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    admitted = Admitted(
        _TOKEN,
        None,
        {"practice_identity": PRACTICE_IDENTITY},
        None,
        {"id": "c", "root": "/nowhere"},
    )
    with pytest.raises(Rejected) as refused:
        RunnerAdapter._background(object(), admitted, operation, {}, None, {})
    assert (refused.value.code, refused.value.status) == ("registration_required", 403)


# --- Setup's first step: "Practise without registering" ---------------------------


def test_setup_offers_practice_at_the_first_step_on_both_doors(tmp_path):
    setup = EnvironmentSetup(made(tmp_path), onboarding=Chain(), checks=Checks())
    for door_name in (HTTP, MCP):
        view = status(setup, door=door_name)
        assert view["practice_only"] is False
        choice = view["practice_choice"]
        assert choice["title"] == "Practise without registering"
        assert choice["call"]["tool"] == "carbon_setup_practice"
        assert choice["call"]["http"] == "POST /api/v1/setup/practice"
        assert view["next"]["step"] == "signer"
        assert view["next"]["or"] == choice
    assert SETUP_OPERATIONS["practice"].tier == "open"


def test_practice_only_setup_skips_signer_and_registration(tmp_path, monkeypatch):
    checks, chain = Checks(), Chain()
    confirmed = []
    monkeypatch.setattr(chain, "confirm", lambda address: confirmed.append(address))
    setup = EnvironmentSetup(made(tmp_path), onboarding=chain, checks=checks)
    with no_outbound(monkeypatch) as guard:
        chosen = perform(setup, "practice", {"confirm": True}, door=MCP)
        assert chosen["practice_only"] is True and chosen["registered_hotkey"] is None
        view = status(setup, door=MCP)
        rows = {row["id"]: row for row in view["steps"]}
        for step in ("signer", "register"):
            assert rows[step]["state"] == "skipped" and not rows[step]["blocks_launch"]
        assert rows["register"]["later"]["tool"] == "carbon_setup_begin"
        assert view["practice_only"] is True and view["practice_choice"] is None
        assert view["next"]["step"] == "agent"
        # Who researches: the choice alone - no signer, no network read.
        perform(setup, "agent", {"choice": OWN_AGENT}, door=MCP)
        agent = setup.state()["steps"]["agent"]
        assert agent["check"] == {"practice_only": True}
        # Choosing again changes nothing.
        perform(setup, "practice", {"confirm": True}, door=HTTP)
    assert guard.attempts == []
    assert confirmed == []
    assert [c[0] for c in checks.calls if c[0] in ("agent", "network")] == []


def test_practice_only_agent_refuses_a_signer_socket(tmp_path):
    setup = EnvironmentSetup(made(tmp_path), onboarding=Chain(), checks=Checks())
    perform(setup, "practice", {"confirm": True}, door=MCP)
    with pytest.raises(SetupRefused) as refused:
        perform(
            setup,
            "agent",
            {"choice": OWN_AGENT, "signer_socket": "/run/signer.sock"},
            door=MCP,
        )
    assert refused.value.code == "nothing_to_check_in_practice_only"
    assert refused.value.next_step


def test_review_refuses_a_practice_only_profile_until_it_exists(tmp_path, monkeypatch):
    setup = EnvironmentSetup(made(tmp_path), onboarding=Chain(), checks=Checks())
    perform(setup, "practice", {"confirm": True}, door=MCP)
    with no_outbound(monkeypatch) as guard, pytest.raises(SetupRefused) as refused:
        perform(
            setup,
            "review",
            {"confirm": True, "intakes": {"battery": "https://intake.invalid"}},
            door=MCP,
        )
    assert refused.value.code == "practice_profile_unavailable"
    assert "carbon_setup_begin" in refused.value.next_step
    assert guard.attempts == []
    assert not setup.profile_path.exists()


def test_practice_needs_confirmation_and_is_before_registration(tmp_path):
    setup = EnvironmentSetup(
        made(tmp_path), onboarding=Chain(registered=True), checks=Checks()
    )
    with pytest.raises(SetupRefused) as refused:
        perform(setup, "practice", {"confirm": False}, door=MCP)
    assert refused.value.next_step == "send confirm: true"
    perform(setup, "begin", {"address": HOTKEY}, door=MCP)
    with pytest.raises(SetupRefused) as refused:
        perform(setup, "practice", {"confirm": True}, door=MCP)
    assert refused.value.code == "practice_only_is_before_registration"
    assert status(setup, door=MCP)["practice_choice"] is None


def test_registering_after_practice_keeps_the_steps_and_asks_the_signer(tmp_path):
    checks, chain = Checks(), Chain()
    setup = EnvironmentSetup(made(tmp_path), onboarding=chain, checks=checks)
    perform(setup, "practice", {"confirm": True}, door=MCP)
    perform(setup, "agent", {"choice": OWN_AGENT}, door=MCP)
    computed = perform(setup, "compute", _compute_arguments(setup), door=MCP)
    assert computed["steps"]["compute"]["check"]
    chain.registered = True
    upgraded = perform(setup, "begin", {"address": HOTKEY}, door=MCP)
    assert upgraded["registered_hotkey"] == HOTKEY
    assert upgraded["practice_only"] is False
    view = status(setup, door=MCP)
    done = set(view["done"])
    assert "compute" in done and "register" in done
    # Who researches is chosen again, so the signer is asked for the hotkey.
    assert "agent" not in done
    assert view["practice_choice"] is None


def _compute_arguments(setup):
    view = status(setup, door=MCP)
    assert view["next"]["step"] == "compute"
    options = view["next"]["options"]
    return {
        "choice": options["choice"][0],
        "image_manifest": options["image_manifest"],
        "analysis_image_manifest": options["analysis_image_manifest"],
    }


def test_the_mcp_door_adds_the_setup_steps_after_practice(tmp_path):
    from scripts.dev.miner_launchpad.setup_operations import REGISTERED

    server, _, _ = door(made(tmp_path), Checks(), Chain())
    later = {
        "carbon_setup_" + n
        for n, op in SETUP_OPERATIONS.items()
        if op.tier == REGISTERED
    }
    assert "carbon_setup_practice" in names(server) and not later & names(server)
    added = call(server, "carbon_setup_practice", {"confirm": True})["tools_added"]
    assert set(added) == later
    payload = call(server, "carbon_setup_status", {})["payload"]
    assert payload["practice_only"] is True and payload["next"]["step"] == "agent"
    # The same typed refusal the browser gets.
    assert refusal(server, "carbon_setup_practice", {"confirm": False}) == {
        "error": "practice_needs_confirmation",
        "field": "confirm",
        "next_step": "send confirm: true",
    }


# --- the no-outbound guard itself ----------------------------------------------------


def test_the_guard_records_and_refuses_what_would_leave(monkeypatch):
    with no_outbound(monkeypatch) as guard:
        with pytest.raises(OutboundBlocked):
            socket.create_connection(("192.0.2.1", 443), timeout=1)
        with pytest.raises(OutboundBlocked):
            socket.getaddrinfo("example.com", 443)
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(OutboundBlocked):
                raw.connect(("198.51.100.7", 80))
            # A swallowed refusal is still recorded.
            try:
                raw.connect_ex(("203.0.113.9", 80))
            except OSError:
                pass
        finally:
            raw.close()
        # Loopback stays open.
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        try:
            local = socket.create_connection(listener.getsockname(), timeout=1)
            local.close()
        finally:
            listener.close()
        assert socket.getaddrinfo("localhost", 80)
    assert [kind for kind, _ in guard.attempts] == [
        "connect",
        "lookup",
        "connect",
        "connect",
    ]
    # Restored after the block.
    assert socket.create_connection.__name__ == "create_connection"


def test_the_doors_list_the_practice_step(tmp_path):
    server, _, _ = door(made(tmp_path), Checks(), Chain())
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    listed = tools["carbon_setup_practice"].input_schema
    assert set(listed["properties"]) == {"confirm"}
    assert listed["required"] == ["confirm"]
