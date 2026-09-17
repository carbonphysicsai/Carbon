"""Research transport preserves nominal v2 dispatch and requester isolation."""

import asyncio
import base64

import pytest
from test_b07g_research_service import _service_fixture
from test_c08_authenticated_miner_mcp import (
    CONTEXT,
    NOW,
    _Adapter,
    _headers,
    _snapshot,
    _Verifier,
)

from carbon import research
from carbon.miner_mcp.research import AuthenticatedResearchService
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import message
from carbon.transport.store import ReceiptJournal


def compose(tmp_path):
    fixture, service = _service_fixture(tmp_path / "research")
    state = _snapshot()
    gateway = AuthenticatedGateway(
        CONTEXT,
        fixture.info.challenge_key,
        "validator",
        _Adapter(state),
        _Verifier(),
        ReceiptJournal(tmp_path / "transport.sqlite3", CONTEXT),
        clock_ns=lambda: NOW,
    )
    call = research.ServiceCall(
        research.RESEARCH_NAMESPACE,
        "get_challenge_info",
        research.GetChallengeInfoRequest(fixture.info.challenge_key),
    )

    def body(index=1, namespace=research.RESEARCH_NAMESPACE, request=call):
        return message(
            CONTEXT,
            state.snapshot_id,
            fixture.info.challenge_key,
            session="research",
            request="call-" + str(index),
            tool=namespace,
            fields={
                "call_base64": base64.b64encode(
                    research.canonical_bytes(request)
                ).decode("ascii")
            },
        )

    wire = body()
    received = asyncio.run(gateway.receive(wire, _headers(wire, NOW)))
    owner = received.requester.value
    return gateway, service, owner, body


def test_twelve_operations_stay_owned_by_b07_with_authenticated_requester(tmp_path):
    gateway, service, owner, body = compose(tmp_path)
    wrapper = AuthenticatedResearchService(gateway, {owner: service})
    wire = body(2)
    result = research.load_canonical(
        asyncio.run(wrapper.call(wire, _headers(wire, NOW + 1))), research.ServiceReply
    )
    assert result.status is research.ReplyStatus.OK
    assert type(result.result) is research.ChallengeInfo
    assert len(research.SUPPORTED_OPERATIONS) == 12


def test_unknown_requester_and_v1_namespace_never_dispatch(tmp_path):
    gateway, service, owner, body = compose(tmp_path)
    wire = body(2)
    with pytest.raises(ValueError, match="requester"):
        asyncio.run(
            AuthenticatedResearchService(gateway, {}).call(
                wire, _headers(wire, NOW + 1)
            )
        )
    wire = body(3, namespace="carbon_protocol_v1")
    with pytest.raises(ValueError, match="namespace"):
        asyncio.run(
            AuthenticatedResearchService(gateway, {owner: service}).call(
                wire, _headers(wire, NOW + 2)
            )
        )
    with pytest.raises(ValueError, match="shared"):
        AuthenticatedResearchService(gateway, {owner: service, "other": service})


def test_supervised_discovery_preserves_canonical_reply_and_owner_check(tmp_path):
    from types import SimpleNamespace

    gateway, service, owner, body = compose(tmp_path)
    wrapper = AuthenticatedResearchService(gateway, {owner: service})
    composition = SimpleNamespace(
        service=service,
        executor=SimpleNamespace(owner=owner),
        tasks=service._context.research_task_provider,
    )
    wire = body(4)
    result = asyncio.run(
        wrapper.supervised_call(wire, _headers(wire, NOW + 3), {owner: composition})
    )
    reply = research.load_canonical(
        base64.b64decode(result["protocol_reply_base64"]), research.ServiceReply
    )
    assert reply.status is research.ReplyStatus.OK
    assert result["terminal_observation_base64"] is None
    assert result["public_result"] is None
    assert not result["requires_reconciliation"]
    assert not result["official_eligible"]
    wire = body(5)
    composition.executor.owner = "other-miner"
    with pytest.raises(ValueError, match="authenticated"):
        asyncio.run(
            wrapper.supervised_call(wire, _headers(wire, NOW + 4), {owner: composition})
        )
