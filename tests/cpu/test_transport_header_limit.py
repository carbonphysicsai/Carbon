"""The gateway's header limits: 32 headers and 4096 bytes, no duplicates, ASCII, no line breaks.

A signed request plus a client's own headers plus what Cloudflare adds in front of the door exceeded the old count of 16 and
every signed POST was refused TRANSPORT_MALFORMED (branch HEADER_COUNT). The count is now `MAX_HEADER_COUNT`; the BYTE budget
(`MAX_HEADERS`), the duplicate check, ASCII and line breaks are unchanged and remain the real guard.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest
from test_battery_intake import (
    DIGEST,
    MINER,
    STRATEGY,
    backend,  # noqa: F401 - fixture registered for request.getfixturevalue
    build,
    facts,
    refs,  # noqa: F401 - fixture registered for request.getfixturevalue
    signed,
)
from test_net2_transport import gateway, headers, wire

from carbon.battery import intake_client as ic
from carbon.transport import gateway as gateway_module
from carbon.transport.models import (
    MAX_HEADER_COUNT,
    MAX_HEADERS,
    PATH,
    TransportFailure,
)

#: What a client library sends by itself, and what Cloudflare adds in front of a tunnelled door, with realistic values.
CLIENT = {
    "Host": "door.carbon-validator.example",
    "User-Agent": "carbon-miner/1.0",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, br",
    "Content-Type": "application/json",
    "Content-Length": "1234",
    "Connection": "keep-alive",
}
CLOUDFLARE = {
    "CF-Connecting-IP": "203.0.113.45",
    "CF-IPCountry": "US",
    "CF-RAY": "8a1b2c3d4e5f6789-IAD",
    "CF-Visitor": '{"scheme":"https"}',
    "CF-Warp-Tag-Id": "11111111-2222-3333-4444-555555555555",
    "CDN-Loop": "cloudflare; loops=1",
    "X-Forwarded-For": "203.0.113.45",
    "X-Forwarded-Proto": "https",
}


@pytest.fixture
def deployed(tmp_path, request):
    return build(
        tmp_path, request.getfixturevalue("refs"), request.getfixturevalue("backend")
    )


def _bytes(items):
    return sum(len(k) + len(v) for k, v in items.items())


def _branch(tmp_path, items):
    """The gateway's malformed branch for these headers, or None when it gets past every header guard."""
    body = wire()
    gate = gateway(tmp_path)
    try:
        asyncio.run(gate.receive(body, {**headers(body), **items}))
    except TransportFailure as failure:
        return failure._branch.value
    return None


def test_the_limit_is_one_named_constant_the_gateway_uses():
    assert MAX_HEADER_COUNT == 32 and MAX_HEADERS == 4096
    source = inspect.getsource(gateway_module.AuthenticatedGateway.receive)
    assert "MAX_HEADER_COUNT" in source
    assert "> 16" not in source and "> 17" not in source


def test_a_realistic_cloudflare_forwarded_request_passes_the_gateway(tmp_path):
    body = wire()
    sent = {**headers(body), **CLIENT, **CLOUDFLARE}
    assert len(sent) > 16  # over the old limit
    assert len(sent) <= MAX_HEADER_COUNT
    assert _bytes(sent) < MAX_HEADERS
    received = asyncio.run(gateway(tmp_path).receive(body, sent))
    assert received.receipt.hotkey == "miner"


def test_a_realistic_signed_cloudflare_request_is_accepted_by_the_intake(deployed):
    intake, _ = deployed
    body = ic.submission_message(facts(intake), STRATEGY, DIGEST, request="cf-1")
    sent = {**signed(MINER, body), **CLIENT, **CLOUDFLARE}
    assert 16 < len(sent) <= MAX_HEADER_COUNT and _bytes(sent) < MAX_HEADERS
    answer = intake.handle("POST", PATH, sent, body, "198.51.100.7")
    assert answer.status == 202, answer.body
    assert answer.body["state"] == "RECEIVED"


def test_the_count_limit_is_exactly_the_constant(tmp_path):
    at_limit = {
        f"x-{i}": "v" for i in range(MAX_HEADER_COUNT - 3)
    }  # headers() adds three
    assert _branch(tmp_path, at_limit) != "HEADER_COUNT"
    over = {f"x-{i}": "v" for i in range(MAX_HEADER_COUNT - 2)}
    assert _branch(tmp_path, over) == "HEADER_COUNT"
    assert _branch(tmp_path, {f"x-{i}": "" for i in range(33)}) == "HEADER_COUNT"


def test_thirty_three_headers_are_refused_header_count(tmp_path):
    gate = gateway(tmp_path)
    with pytest.raises(TransportFailure) as caught:
        asyncio.run(gate.receive(wire(), {str(i): "" for i in range(33)}))
    assert caught.value._branch.value == "HEADER_COUNT"


def test_the_byte_budget_is_unchanged(tmp_path):
    # 1 + 4095 = 4096 bytes of name and value: allowed; 4097: refused HEADER_BUDGET
    gate = gateway(tmp_path)
    with pytest.raises(TransportFailure) as caught:
        asyncio.run(gate.receive(wire(), {"x": "x" * 4096}))
    assert caught.value._branch.value == "HEADER_BUDGET"
    body = wire()
    exactly = {"x": "x" * (MAX_HEADERS - 1 - _bytes(headers(body)))}
    assert _bytes({**headers(body), **exactly}) == MAX_HEADERS
    assert _branch(tmp_path, exactly) != "HEADER_BUDGET"


@pytest.mark.parametrize(
    "items,branch",
    [
        ({"x": "", "X": ""}, "HEADER_DUPLICATE"),
        ({"X-Forwarded-For": "1", "x-forwarded-for": "2"}, "HEADER_DUPLICATE"),
        ({"x": "é"}, "HEADER_ASCII"),
        ({"x": "a\nb"}, "HEADER_LINE_BREAK"),
    ],
)
def test_the_other_guards_are_unchanged(tmp_path, items, branch):
    assert _branch(tmp_path, items) == branch
