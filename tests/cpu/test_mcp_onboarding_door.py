"""The MCP door onto onboarding: same service, no adapter, no campaign.

Drives the real Tool objects the server registers. The chain is a device-free
stub; nothing else is replaced.

The property under test is that this door and the browser door are the same
service with the same answers, and that the per-call record cannot be handed
anything a caller supplied.
"""

import asyncio

import pytest

from carbon.chain.models import (
    CARBON_NETUID,
    CARBON_NETWORK,
    ChainContext,
    MetagraphSnapshot,
    Participant,
)
from carbon.development_session import chain_onboarding as service
from carbon.miner_mcp.mcp_onboarding import PREFIX, make_onboarding_tools
from scripts.dev.miner_launchpad.onboarding import BrowserOnboarding

HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
COLDKEY = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
MNEMONIC = "bottom drive obey lake curtain smoke basket hold race lonely fit walk"


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
