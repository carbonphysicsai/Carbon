"""NET-2 wire, durable replay, installed SDK and existing MCP contracts."""

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from carbon.chain import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.auth import (
    AuthCode,
    AuthenticatedHotkey,
    AuthFailure,
    BittensorHotkeyVerifier,
    BittensorMessageSigner,
)
from carbon.registry import ChallengeKey
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import (
    ReceiptRef,
    TransportFailure,
    canonical,
    digest,
    message,
    parse_message,
)
from carbon.transport.store import ReceiptJournal

NOW = 100_000_000_000
CONTEXT = ChainContext("localnet", "ws://127.0.0.1:9944", "dev", "0x" + "1" * 64, 1)
CHALLENGE = ChallengeKey("synthetic", "1.0")


def snapshot(sender="miner", receiver="validator"):
    return MetagraphSnapshot(
        CONTEXT,
        10,
        "0x" + "2" * 64,
        NOW // 1_000_000,
        (
            Participant(0, receiver, "owner", 1),
            Participant(1, sender, "cold", 2),
        ),
    )


class Adapter:
    def __init__(self, state):
        self.state = state

    async def observe(self, *, minimum_finalized_block):
        return self.state


class FakeVerifier:
    """Deterministic test double, never selected by a wire request or local server."""

    def verify(self, headers, body, *, method, path, receiver, now_ns, nonce_store):
        if headers["body"] != digest(body):
            raise AuthFailure(AuthCode.SIGNATURE)
        nonce = int(headers["nonce"])
        if not -2_000_000_000 <= now_ns - nonce <= 10_000_000_000:
            raise AuthFailure(AuthCode.STALE)
        if not nonce_store.check_and_store(headers["hotkey"], nonce):
            raise AuthFailure(AuthCode.REPLAY)
        return AuthenticatedHotkey(headers["hotkey"], nonce)


def wire(state=None, **changes):
    state = snapshot() if state is None else state
    args = {
        "session": "session-1",
        "request": "request-1",
        "tool": "dry_validate",
        "fields": {"strategy": {}},
    }
    args.update(changes)
    return message(CONTEXT, state.snapshot_id, CHALLENGE, **args)


def headers(body, nonce=NOW, hotkey="miner"):
    return {"body": digest(body), "nonce": str(nonce), "hotkey": hotkey}


def gateway(tmp_path, *, capacity=100000, state=None, now=NOW):
    state = snapshot() if state is None else state
    journal = ReceiptJournal(tmp_path / "receipts.sqlite", CONTEXT, capacity=capacity)
    return AuthenticatedGateway(
        CONTEXT,
        CHALLENGE,
        state.participants[0].hotkey,
        Adapter(state),
        FakeVerifier(),
        journal,
        clock_ns=lambda: now,
    )


def receive(gate, body=None, nonce=NOW, **kwargs):
    body = wire(gate.adapter.state) if body is None else body
    return asyncio.run(gate.receive(body, headers(body, nonce), **kwargs))


def test_canonical_wire_is_order_independent_but_not_encoding_ambiguous():
    body = wire(fields={"strategy": {"x": 0.1, "y": [1, False, None]}})
    parsed = parse_message(body)
    assert canonical(dict(reversed(list(parsed.items())))) == body
    assert parse_message(body)["fields"]["strategy"]["x"] == 0.1
    with pytest.raises(TransportFailure):
        parse_message(json.dumps(parsed).encode())


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"[]",
        b"{}",
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e999}',
        b'"\\ud800"',
        b"\xff",
        b"[" * 10000,
        b" " * 65537,
    ],
    ids=[str(n) for n in range(11)],
)
def test_malformed_wire_is_bounded(body):
    with pytest.raises(TransportFailure):
        parse_message(body)


@pytest.mark.parametrize("value", [2**65, float("nan"), {1: "x"}, set(), object()])
def test_noncanonical_local_values_are_rejected(value):
    with pytest.raises(TransportFailure):
        canonical(value)


def test_nested_cyclic_and_node_limits():
    cycle = []
    cycle.append(cycle)
    for value in (cycle, [0] * 4097):
        with pytest.raises(TransportFailure):
            canonical(value)


@pytest.mark.parametrize(
    "key,value",
    [
        ("network", "finney"),
        ("genesis", "0x" + "3" * 64),
        ("netuid", 2),
        ("challenge_id", "other"),
        ("challenge_version", "2.0"),
        ("snapshot", "stale"),
    ],
)
def test_cross_context_replay_never_reaches_dispatch(tmp_path, key, value):
    body = json.loads(wire())
    body[key] = value
    with pytest.raises(TransportFailure, match="CONTEXT"):
        receive(gateway(tmp_path), canonical(body))


def test_tool_fields_cannot_override_signed_challenge():
    with pytest.raises(TransportFailure, match="CONTEXT"):
        wire(fields={"challenge_id": "other"})


@pytest.mark.parametrize("change", [{"method": "GET"}, {"path": "/other"}])
def test_method_and_route_domain(tmp_path, change):
    with pytest.raises(TransportFailure, match="CONTEXT"):
        receive(gateway(tmp_path), **change)


def test_receipts_survive_restart_and_forged_references_fail(tmp_path):
    gate = gateway(tmp_path)
    first = receive(gate)
    assert first.receipt.ref.sequence == 1
    assert gate.journal.resolve(first.receipt.ref) == first.receipt
    restarted = gateway(tmp_path)
    assert restarted.journal.resolve(first.receipt.ref) == first.receipt
    with pytest.raises(AuthFailure, match="REPLAY"):
        receive(restarted)
    with pytest.raises(TransportFailure, match="REPLAY"):
        receive(restarted, nonce=NOW + 1)
    with pytest.raises(TransportFailure, match="CONFLICT"):
        receive(restarted, wire(tool="estimate"), nonce=NOW + 2)
    with pytest.raises(TransportFailure, match="CONFLICT"):
        restarted.journal.resolve(ReceiptRef(1, "0" * 64))
    second = receive(restarted, wire(request="request-2"), nonce=NOW + 3)
    assert second.receipt.ref.sequence == 2


def test_nonce_and_order_commit_atomically_under_concurrency(tmp_path):
    gate = gateway(tmp_path)

    def attempt(nonce):
        try:
            return receive(gate, nonce=nonce).receipt.ref.sequence
        except TransportFailure:
            return "duplicate"

    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(attempt, [NOW, NOW + 1]))
    assert sorted(map(str, result)) == ["1", "duplicate"]


def test_invalid_signature_does_not_poison_nonce_or_receipt(tmp_path):
    gate = gateway(tmp_path)
    signed = headers(wire())
    signed["body"] = "wrong"
    with pytest.raises(AuthFailure):
        asyncio.run(gate.receive(wire(), signed))
    assert receive(gate).receipt.ref.sequence == 1


def test_unregistered_and_recycled_identity_cannot_inherit(tmp_path):
    gate = gateway(tmp_path)
    previous = receive(gate)
    old_body = wire()
    gate.adapter.state = replace(
        snapshot(),
        finalized_block=11,
        participants=(
            snapshot().participants[0],
            Participant(1, "miner", "cold", 11),
        ),
    )
    with pytest.raises(TransportFailure, match="CONTEXT"):
        receive(gate, old_body, nonce=NOW + 1)
    fresh = receive(gate, wire(gate.adapter.state, request="new"), nonce=NOW + 2)
    assert fresh.requester != previous.requester
    gate.adapter.state = replace(
        gate.adapter.state,
        finalized_block=12,
        participants=(snapshot().participants[0], Participant(1, "other", "cold", 12)),
    )
    with pytest.raises(TransportFailure, match="IDENTITY"):
        receive(gate, wire(gate.adapter.state), nonce=NOW + 3)


def test_context_clock_and_snapshot_watermarks_survive_restart(tmp_path):
    first = receive(gateway(tmp_path))
    with pytest.raises(TransportFailure, match="STALE"):
        receive(gateway(tmp_path, now=NOW - 1), wire(request="new"), nonce=NOW + 1)
    changed = replace(snapshot(), block_hash="0x" + "4" * 64)
    with pytest.raises(TransportFailure, match="CONTEXT"):
        receive(gateway(tmp_path, state=changed), wire(changed), nonce=NOW + 1)
    with pytest.raises(TransportFailure, match="CONTEXT"):
        ReceiptJournal(tmp_path / "receipts.sqlite", replace(CONTEXT, netuid=2))
    assert gateway(tmp_path).journal.resolve(first.receipt.ref) == first.receipt


def test_stale_nonce_and_snapshot(tmp_path):
    with pytest.raises(AuthFailure, match="STALE"):
        receive(gateway(tmp_path), nonce=NOW - 11_000_000_000)
    with pytest.raises(TransportFailure, match="STALE"):
        receive(gateway(tmp_path, now=NOW + 61_000_000_000))


def test_header_duplicates_and_size_are_bounded(tmp_path):
    gate = gateway(tmp_path)
    for bad in ({"a": "x" * 4097}, {"a": "1", "A": "2"}, {"a": "\r\nsecret"}):
        with pytest.raises(TransportFailure, match="MALFORMED"):
            asyncio.run(gate.receive(wire(), bad))


def test_import_never_opens_database_network_or_sdk():
    code = """
import sqlite3, socket, sys
def forbidden(*args, **kwargs):
    raise AssertionError('import attempted external state')
sqlite3.connect = forbidden
socket.create_connection = forbidden
import carbon.chain.auth
import carbon.transport.gateway
assert 'bittensor' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_capacity_and_burst_limits_preserve_previous_receipts(tmp_path):
    gate = gateway(tmp_path, capacity=1)
    receive(gate)
    with pytest.raises(TransportFailure, match="CAPACITY"):
        receive(gate, wire(request="new"), nonce=NOW + 1)
    gate.journal.capacity = 100000
    for n in range(1, 32):
        receive(gate, wire(request=f"r{n}"), nonce=NOW + n)
    with pytest.raises(TransportFailure, match="RATE"):
        receive(gate, wire(request="r32"), nonce=NOW + 32)


def sdk():
    if importlib.util.find_spec("bittensor") is None:
        if os.environ.get("CARBON_REQUIRE_CHAIN_SDK") == "1":
            pytest.fail("Installed SDK auth contract is required")
        pytest.skip("Installed SDK contract runs in canonical Linux")
    import bittensor as bt
    from bittensor.keyfiles import Keypair

    return bt, Keypair


@pytest.mark.parametrize(
    "mutation", ["none", "body", "method", "path", "receiver", "nonce", "signature"]
)
def test_installed_sdk_signatures_and_domains(tmp_path, mutation):
    bt, keypair = sdk()
    sender = keypair.create_from_uri("//Alice")
    receiver = keypair.create_from_uri("//Bob")
    state = snapshot(sender.ss58_address, receiver.ss58_address)
    body = wire(state)
    signed = BittensorMessageSigner(sender).sign(
        body, receiver=receiver.ss58_address, nonce_ns=NOW
    )
    args = {
        "method": "POST",
        "path": "/carbon/v1/mcp",
        "receiver": receiver.ss58_address,
        "now_ns": NOW,
        "nonce_store": bt.http_auth.InMemoryNonceStore(),
    }
    if mutation == "body":
        body += b" "
    elif mutation in ("method", "path"):
        args[mutation] = "altered"
    elif mutation == "receiver":
        args["receiver"] = sender.ss58_address
    elif mutation == "nonce":
        signed["X-Bittensor-Nonce"] = str(NOW - 11_000_000_000)
    elif mutation == "signature":
        signed["X-Bittensor-Signature"] = "0x" + "00" * 64
    if mutation != "none":
        with pytest.raises(AuthFailure) as error:
            BittensorHotkeyVerifier().verify(signed, body, **args)
        assert error.value.__context__ is None and error.value.__cause__ is None
    else:
        gate = AuthenticatedGateway(
            CONTEXT,
            CHALLENGE,
            receiver.ss58_address,
            Adapter(state),
            BittensorHotkeyVerifier(),
            ReceiptJournal(tmp_path / "auth.sqlite", CONTEXT),
            clock_ns=lambda: NOW,
        )
        result = asyncio.run(gate.receive(body, signed))
        assert result.receipt.hotkey == sender.ss58_address
        with pytest.raises(AuthFailure, match="REPLAY"):
            asyncio.run(gate.receive(body, signed))


@pytest.mark.skipif(
    os.name == "nt",
    reason="Existing A3 registry requires descriptor-relative Linux filesystem access",
)
def test_authenticated_request_dispatches_through_existing_mcp(tmp_path):
    from test_mcp_skeleton import _service, _strategy

    from carbon.mcp import DryValidateResponse

    service, *_ = _service(tmp_path / "mcp")
    gate = gateway(tmp_path)
    body = wire(fields={"strategy": _strategy()})
    ref, result = asyncio.run(gate.dispatch(body, headers(body), service))
    assert type(result) is DryValidateResponse
    assert gate.journal.resolve(ref).body_digest == digest(body)
