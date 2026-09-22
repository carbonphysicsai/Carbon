"""A registered miner with no campaign connects, discovers, and is refused late.

The path the owner set: miner setup, compute setup, agent option, MCP if agent,
control center. Step four is a miner who has registered and chosen compute
connecting their own agent. They have no grant - there are no grants in the
product - and no campaign yet.

What must work: connecting, discovering what is there, reading the surface
contract. What must not: dispatching work there is nothing to account against.
The refusal has to arrive at dispatch rather than at connect, and it has to be
honest about the two things a miner will act on - which limit stopped them, and
whether anything started.
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_standard_mcp_adapter import make_adapter

from carbon.development_session.research_tools import PreDispatchRefusal
from carbon.miner_mcp.serving import NEXT_ACTION
from carbon.miner_mcp.standard import AdapterCode
from carbon.miner_mcp.standard_server import PREFIX, _create_server

PRACTICE = {
    "kind": "practice",
    "strategy": {"parameters": {"steps": 512}},
    "action": None,
    "arguments": None,
    "hypothesis": "A bounded training update improves practice",
    "expected_effect": "Measure the effect under existing physics gates",
}


def campaign_free_server():
    """A registered principal, no grant, no campaign, no ledger."""
    _sdk, adapter = make_adapter(ledger=None)
    return _create_server(adapter)


def test_a_miner_with_no_campaign_can_connect_and_discover():
    """Refused at dispatch, not at connect - so connecting has to work."""
    server = campaign_free_server()
    tools = asyncio.run(server.list_tools())
    assert len(tools) >= 12
    assert any(tool.name.startswith(PREFIX) for tool in tools)


def test_the_surface_contract_is_readable_without_a_campaign():
    server = campaign_free_server()
    assert asyncio.run(server.read_resource("carbon://research/v1/catalogue"))


def test_dispatch_is_refused_with_a_slug_and_a_next_action():
    from mcp.server.mcpserver.exceptions import ToolError

    server = campaign_free_server()
    with pytest.raises(ToolError) as raised:
        asyncio.run(
            server.call_tool(
                PREFIX + "start_research_task",
                {"operation_id": "external-operation-0001", **PRACTICE},
            )
        )
    message = str(raised.value)
    assert "NO_CAMPAIGN" in message
    assert "next_action=" in message


def test_a_refusal_before_dispatch_never_claims_dispatch_may_have_occurred():
    """The half of the old message that would send a miner looking for nothing.

    The blanket handler reports `dispatch_may_have_occurred=true`, which is the
    right conservative answer when the controller might be holding an ambiguous
    reservation. It is provably wrong here: the refusal fires before any
    reservation is possible, because there is no ledger to reserve against.

    Asserted as the exact string a client parses rather than on the exception
    object, since that string is what a miner's agent branches on.
    """
    from mcp.server.mcpserver.exceptions import ToolError

    server = campaign_free_server()
    with pytest.raises(ToolError) as raised:
        asyncio.run(
            server.call_tool(
                PREFIX + "start_research_task",
                {"operation_id": "external-operation-0001", **PRACTICE},
            )
        )
    assert "dispatch_may_have_occurred=false" in str(raised.value)
    assert "dispatch_may_have_occurred=true" not in str(raised.value)


def test_every_research_operation_refuses_the_same_way_not_just_dispatch():
    """Inspection needs a campaign too, and should say so at the top.

    Every operation reaches the validator through `supervised_call`, which needs
    a composition a campaign supplies. Failing at the entry names the real
    problem; failing deep produced a message about a campaign not accepting
    work, when there was no campaign at all.
    """
    from mcp.server.mcpserver.exceptions import ToolError

    server = campaign_free_server()
    for operation in ("get_challenge_info", "get_prior", "get_interaction_manifest"):
        with pytest.raises(ToolError) as raised:
            asyncio.run(
                server.call_tool(
                    PREFIX + operation, {"operation_id": "external-operation-0002"}
                )
            )
        assert "NO_CAMPAIGN" in str(raised.value), operation


def test_the_refusal_is_a_type_rather_than_a_flag():
    """Why this is a distinct exception and not a boolean.

    Once "refused before dispatch" and "failed mid-flight" are both `Exception`,
    the transport cannot tell them apart and must assume the worse of the two.
    A distinct type is what lets the honest answer through, and it cannot be
    constructed without stating the next action.
    """
    assert issubclass(PreDispatchRefusal, Exception)
    refusal = PreDispatchRefusal("NO_CAMPAIGN", next_action="do the thing")
    assert refusal.reason == "NO_CAMPAIGN"
    assert refusal.next_action == "do the thing"
    with pytest.raises(TypeError):
        PreDispatchRefusal("NO_CAMPAIGN")


def test_the_new_slug_carries_a_next_action_like_every_other():
    assert NEXT_ACTION[AdapterCode.NO_CAMPAIGN.value].strip()
    assert "nothing to reconcile" in NEXT_ACTION[AdapterCode.NO_CAMPAIGN.value]
    for code in AdapterCode:
        assert NEXT_ACTION[code.value].strip(), code
