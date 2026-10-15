"""The MCP door onto onboarding: same service, no adapter, no campaign.

Drives the real Tool objects the server registers. The chain is a device-free
stub; nothing else is replaced.

The property under test is that this door and the browser door are the same
service with the same answers, and that the per-call record cannot be handed
anything a caller supplied.
"""

import asyncio

import pytest
import test_launchpad_onboarding_door as http_onboarding
from mcp.server.mcpserver.exceptions import ToolError
from test_chain_onboarding import _Reader as ChainReader
from test_launchpad_onboarding_door import call as browser_call

from carbon.chain.models import (
    CARBON_NETUID,
    CARBON_NETWORK,
    ChainContext,
    FailureCode,
    MetagraphSnapshot,
    Participant,
)
from carbon.development_session import chain_onboarding as service
from carbon.miner_mcp.mcp_onboarding import PREFIX, make_onboarding_tools
from scripts.dev.miner_launchpad.onboarding import BrowserOnboarding

HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
COLDKEY = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
MNEMONIC = "bottom drive obey lake curtain smoke basket hold race lonely fit walk"

# Reuse the existing real HTTP fixture without creating a second server harness.
browser_server = http_onboarding.server


class _Reader:
    def __init__(self, participants=()):
        self.participants = participants

    async def capture(self, context):
        return MetagraphSnapshot(
            context=context,
            finalized_block=100,
            block_hash="0x" + "cd" * 32,
            timestamp_ms=1,
            participants=tuple(self.participants),
        )


def _context():
    return ChainContext(
        network=CARBON_NETWORK,
        endpoint="wss://entrypoint-finney.opentensor.ai:443",
        provider="test",
        genesis_hash="0x" + "ab" * 32,
        netuid=CARBON_NETUID,
    )


def _door(participants=(), records=None):
    tools = make_onboarding_tools(
        reader=_Reader(participants),
        context=_context(),
        sink=None if records is None else records.append,
    )
    return {tool.name: tool for tool in tools}


def _call(tools, name, **arguments):
    return asyncio.run(tools[PREFIX + name].fn(**arguments))


def test_the_four_tools_are_registered():
    tools = _door()
    assert set(tools) == {
        PREFIX + name for name in ("requirements", "status", "prepare", "confirm")
    }


def test_no_tool_signs_or_accepts_key_material():
    """The rule, asserted on the declared surface a client actually sees."""
    for tool in _door().values():
        assert "sign" not in tool.name
        properties = tool.parameters.get("properties", {})
        assert set(properties) <= {"address"}, tool.name


def test_requirements_needs_no_chain_no_campaign_no_registration():
    tools = _door()
    result = _call(tools, "requirements")
    assert result.payload["mechanism"] == "BURNED_REGISTRATION"
    assert result.payload["cost"]["value"] == "NOT_READ"
    assert result.official_eligible is False


def test_status_and_prepare_answer_the_same_as_the_browser_door():
    """One service, two doors: neither may diverge from the other."""
    browser = BrowserOnboarding(reader=_Reader(), context=_context())
    tools = _door()

    assert _call(tools, "status", address=HOTKEY).payload == browser.status(HOTKEY)
    assert _call(tools, "prepare", address=HOTKEY).payload == browser.prepare(HOTKEY)


def test_a_registered_hotkey_unlocks_through_this_door_too():
    tools = _door(
        (Participant(uid=0, hotkey=HOTKEY, coldkey=COLDKEY, registered_at=42),)
    )
    payload = _call(tools, "confirm", address=HOTKEY).payload
    assert payload["confirmed"] is True and payload["uid"] == 0
    assert payload["research_environment"] == "UNLOCKED"


def test_every_call_records_only_validated_values():
    records = []
    tools = _door(records=records)
    _call(tools, "requirements")
    _call(tools, "status", address=HOTKEY)

    assert [r["operation"] for r in records] == ["requirements", "status"]
    for record in records:
        assert record["arguments"] == "NOT_RECORDED"
        assert record["address"] in (None, HOTKEY)


def test_a_refused_call_records_a_reason_and_no_input():
    """The vector the response-echo test never covered.

    A per-call record is exactly where a pasted phrase would be persisted, so
    the refusal path is asserted to emit a record carrying none of it.
    """
    records = []
    tools = _door(records=records)
    # Right length, wrong alphabet: 0 is not base58, so this reaches the
    # service and is refused there rather than being stopped at the wire.
    refused = "0" * 47
    with pytest.raises(Exception) as caught:
        _call(tools, "status", address=refused)

    assert records and records[-1]["outcome"] == "REFUSED"
    assert records[-1]["address"] is None
    assert records[-1]["arguments"] == "NOT_RECORDED"
    assert refused not in str(caught.value)


def test_the_record_cannot_be_handed_an_unvalidated_value():
    """Structural, and it holds at this door too."""
    with pytest.raises(service.OnboardingFailure):
        service.call_record("status", address=HOTKEY, outcome="REGISTERED")
    with pytest.raises(service.OnboardingFailure):
        service.call_record("status", address=MNEMONIC, outcome="REFUSED")


def test_a_phrase_cannot_even_reach_the_service_through_this_door():
    """Bounded at the wire: an ss58 address is 46-50 characters."""
    tools = _door()
    schema = tools[PREFIX + "status"].parameters["properties"]["address"]
    assert schema["minLength"] == 46 and schema["maxLength"] == 50
    assert len(MNEMONIC) > 50


@pytest.mark.parametrize("operation", ("requirements", "status", "prepare", "confirm"))
def test_every_onboarding_action_reaches_both_real_adapters(browser_server, operation):
    participants = (
        (Participant(uid=0, hotkey=HOTKEY, coldkey=COLDKEY, registered_at=42),)
        if operation == "confirm"
        else ()
    )
    browser_server.onboarding.reader = _Reader(participants)
    tools = _door(participants)
    arguments = {} if operation == "requirements" else {"address": HOTKEY}
    status, payload = browser_call(
        browser_server,
        "/api/v1/onboarding/" + operation,
        None if operation == "requirements" else arguments,
    )
    result = _call(tools, operation, **arguments)
    assert status == 200
    assert result.operation == operation
    assert result.payload == payload
    assert result.official_eligible is False
    assert browser_server.controller.recent() == []


@pytest.mark.parametrize("operation", ("status", "prepare", "confirm"))
@pytest.mark.parametrize(
    ("scenario", "reason"),
    [
        ("malformed", "INVALID_ADDRESS"),
        ("chain_unavailable", "CHAIN_UNAVAILABLE"),
        ("wrong_network", "WRONG_NETWORK"),
    ],
)
def test_every_onboarding_read_refuses_with_the_same_action(
    browser_server, operation, scenario, reason
):
    from dataclasses import replace

    reader = ChainReader(
        failure=FailureCode.UNAVAILABLE if scenario == "chain_unavailable" else None
    )
    context = (
        replace(_context(), netuid=1) if scenario == "wrong_network" else _context()
    )
    browser_server.onboarding.reader = reader
    browser_server.onboarding.context = context
    tools = {
        tool.name: tool
        for tool in make_onboarding_tools(reader=reader, context=context)
    }
    address = "0" * 47 if scenario == "malformed" else HOTKEY
    status, browser = browser_call(
        browser_server, "/api/v1/onboarding/" + operation, {"address": address}
    )
    with pytest.raises(ToolError) as raised:
        _call(tools, operation, address=address)
    code, separator, action = str(raised.value).partition("; next_action=")
    assert status == 409
    assert separator and browser["reason"] == code == reason
    assert browser["next_action"] == action and action
    assert browser["ok"] is False
    assert browser_server.controller.recent() == []
    assert reader.calls == (2 if scenario == "chain_unavailable" else 0)


def test_preparing_an_already_registered_hotkey_has_the_same_refusal(browser_server):
    participants = (Participant(uid=0, hotkey=HOTKEY, coldkey=COLDKEY, registered_at=42),)
    browser_server.onboarding.reader = _Reader(participants)
    status, browser = browser_call(
        browser_server, "/api/v1/onboarding/prepare", {"address": HOTKEY}
    )
    with pytest.raises(ToolError) as raised:
        _call(_door(participants), "prepare", address=HOTKEY)
    code, separator, action = str(raised.value).partition("; next_action=")
    assert status == 409
    assert separator and browser["reason"] == code == "ALREADY_REGISTERED"
    assert browser["next_action"] == action and action
    assert browser_server.controller.recent() == []


def test_unregistered_confirmation_is_the_same_successful_observation(browser_server):
    browser_server.onboarding.reader = _Reader()
    status, browser = browser_call(
        browser_server, "/api/v1/onboarding/confirm", {"address": HOTKEY}
    )
    result = _call(_door(), "confirm", address=HOTKEY)
    assert status == 200
    assert result.payload == browser
    assert browser["registered"] is False and browser["confirmed"] is False
    assert browser["next_action"] == (
        "No registration is visible for this hotkey yet. If you have "
        "just executed it, the chain may not have finalised the block; "
        "retry shortly. Nothing here retries or submits for you."
    )
    assert result.official_eligible is False
    assert browser_server.controller.recent() == []
