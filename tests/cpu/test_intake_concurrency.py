"""The intake serves concurrent clients; past capacity it answers, it never drops.

valV3, 2026-10-27: five simultaneous clients through one ssh forward got
`RemoteDisconnected`: the per-address connection cap (4) closed the fifth socket
without a byte, and every client behind a local forward shares 127.0.0.1.
GPU_REBUILD_RULINGS section 12: a bounded concurrent server; past capacity a typed
`503 intake_busy` with `Retry-After`; reads in parallel; state-changing calls single-writer.
"""

from __future__ import annotations

import http.client
import json
import threading
import time
from types import SimpleNamespace

import pytest

from carbon.battery import intake as battery_intake
from carbon.battery.intake import Answer, ConnectionSlots, PeerLimits, _handler
from carbon.challenge_validator.direct_intake import DirectRecipeIntake


class FakeIntake:
    """The few things the HTTP handler asks of an intake; the route is scripted."""

    proxy_header = None
    local_hop = True

    def __init__(self, route, limits=None):
        self.route = route
        self.limits = limits or PeerLimits(burst=10_000, rate=10_000.0)
        self.client_connections = ConnectionSlots()


def serve(intake, *, slots=None, local_hop=True):
    server = battery_intake._Server(
        ("127.0.0.1", 0), _handler(intake), local_hop=local_hop
    )
    if slots is not None:
        server.slots = slots
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop(server, thread):
    server.shutdown()
    server.server_close()
    thread.join(5)


def call(port, method="GET", body=b"", timeout=20):
    """(status, headers, parsed body) or the exception a dropped connection raises."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request(
            method,
            "/carbon/v1/construction/intake" if method == "GET" else "/carbon/v1/mcp",
            body=body or None,
            headers={"Content-Length": str(len(body))} if method == "POST" else {},
        )
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), json.loads(response.read())
    finally:
        connection.close()


def fire(port, plan):
    """Run every (method, body) of `plan` at once; return one outcome per call."""
    outcomes = [None] * len(plan)
    barrier = threading.Barrier(len(plan))

    def one(index, method, body):
        barrier.wait()
        try:
            outcomes[index] = call(port, method, body)
        except Exception as failure:  # noqa: BLE001 - a drop is what is being counted
            outcomes[index] = failure

    threads = [
        threading.Thread(target=one, args=(i, m, b)) for i, (m, b) in enumerate(plan)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    return outcomes


def test_thirty_two_probes_and_sixteen_submits_all_get_a_typed_answer():
    seen = {"writes": 0}
    guard = threading.Lock()

    def route(method, path, headers, body):
        time.sleep(0.02)
        if method == "POST":
            with guard:
                seen["writes"] += 1
            return Answer(202, {"state": "RECEIVED"})
        return Answer(200, {"schema": "probe"})

    server, thread = serve(FakeIntake(route))
    try:
        port = server.server_address[1]
        plan = [("GET", b"")] * 32 + [("POST", b"x" * 200)] * 16
        outcomes = fire(port, plan)
    finally:
        stop(server, thread)
    dropped = [o for o in outcomes if isinstance(o, Exception)]
    assert dropped == []  # 0 disconnects
    reads, writes = outcomes[:32], outcomes[32:]
    assert [r[0] for r in reads] == [
        200
    ] * 32  # reads run in parallel and are never refused
    # Past the in-flight bound a submit gets a typed 503 with Retry-After, never silence.
    assert {w[0] for w in writes} <= {202, 503}
    for status, headers, body in writes:
        if status == 503:
            assert body == {"refused": "capacity"} and headers["Retry-After"] == "1"
    assert seen["writes"] == sum(1 for w in writes if w[0] == 202) >= 1


def test_the_overflow_is_a_typed_503_with_retry_after_never_a_drop():
    release = threading.Event()
    entered = threading.Semaphore(0)

    def route(method, path, headers, body):
        entered.release()
        release.wait(20)
        return Answer(200, {"schema": "probe"})

    server, thread = serve(
        FakeIntake(route), slots=ConnectionSlots(total=4, per_peer=4)
    )
    holders = []
    try:
        port = server.server_address[1]
        for _ in range(4):  # fill every slot with a request that is being served
            holder = threading.Thread(target=lambda: call(port), daemon=True)
            holder.start()
            holders.append(holder)
        for _ in range(4):
            assert entered.acquire(timeout=10)
        outcomes = fire(port, [("GET", b"")] * 12 + [("POST", b"y" * 300)] * 4)
    finally:
        release.set()
        for holder in holders:
            holder.join(10)
        stop(server, thread)
    assert [o for o in outcomes if isinstance(o, Exception)] == []
    for status, headers, body in outcomes:
        assert status == 503
        assert body == {"refused": "intake_busy"}
        assert headers["Retry-After"] == "1"


def test_clients_behind_one_local_forward_are_not_capped_per_address():
    """Every client of an ssh forward or a local proxy arrives from 127.0.0.1."""
    release = threading.Event()

    def route(method, path, headers, body):
        release.wait(10)
        return Answer(200, {"ok": True})

    slots = ConnectionSlots(total=64, per_peer=2)
    server, thread = serve(FakeIntake(route), slots=slots)
    results = []
    try:
        port = server.server_address[1]
        threads = [
            threading.Thread(target=lambda: results.append(call(port)), daemon=True)
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        deadline = time.monotonic() + 10
        while slots.open() < 10 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert slots.open() == 10  # all ten were accepted: no per-address refusal
        release.set()
        for t in threads:
            t.join(10)
    finally:
        release.set()
        stop(server, thread)
    assert [status for status, *_ in results] == [200] * 10


def test_rate_and_capacity_refusals_carry_retry_after_and_arrive_as_responses():
    def route(method, path, headers, body):
        return Answer(202, {"state": "RECEIVED"})

    limits = PeerLimits(burst=1, rate=0.0001)
    server, thread = serve(FakeIntake(route, limits))
    try:
        port = server.server_address[1]
        first = call(port, "POST", b"z" * 4000)
        second = call(port, "POST", b"z" * 4000)  # over the peer's bucket: 429
    finally:
        stop(server, thread)
    assert first[0] == 202
    status, headers, body = second
    assert (status, body) == (429, {"refused": "rate"})
    assert headers["Retry-After"] == "1"


def test_state_changing_calls_run_one_writer_at_a_time():
    """Admission and source staging share one writer; the cap and idempotency stay exact."""
    state = {"inside": 0, "max": 0}
    guard = threading.Lock()
    admitted = {}

    def evaluate(submitted):
        with guard:
            state["inside"] += 1
            state["max"] = max(state["max"], state["inside"])
        time.sleep(0.01)
        # an idempotent admission: the first of a (hotkey, recipe) wins, a duplicate is the same task
        first = admitted.setdefault(submitted, len(admitted) + 1)
        with guard:
            state["inside"] -= 1
        return {"kind": "OUTCOME", "task": first}

    intake = object.__new__(DirectRecipeIntake)
    intake._write = threading.Lock()
    intake.door = SimpleNamespace(evaluate=evaluate)
    keys = [("hotkey-a", "recipe-1")] * 8 + [("hotkey-b", "recipe-1")] * 8
    results = []
    threads = [
        threading.Thread(target=lambda k=k: results.append(intake._admit(k)))
        for k in keys
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    assert state["max"] == 1
    assert len(results) == 16
    assert len({r["task"] for r in results}) == 2  # duplicates admitted once each


def test_the_busy_reply_is_valid_http():
    head, _, body = battery_intake.BUSY_REPLY.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    assert lines[0] == b"HTTP/1.1 503 Service Unavailable"
    assert b"Retry-After: 1" in lines
    declared = next(l for l in lines if l.startswith(b"Content-Length: "))
    assert int(declared.split(b": ")[1]) == len(body)
    assert json.loads(body) == {"refused": "intake_busy"}


@pytest.mark.parametrize("peer", ["127.0.0.1", "::1"])
def test_loopback_peers_count_as_a_shared_hop(peer):
    assert battery_intake.is_loopback(peer)


def test_another_door_keeps_its_per_address_cap_and_its_close_at_once():
    """Only the local-hop door (the direct construction intake) shares the loopback address;
    every other door still refuses the over-cap peer by closing it, with no body."""
    import socket

    def route(method, path, headers, body):
        return Answer(200, {"ok": True})

    slots = ConnectionSlots(total=64, per_peer=1)
    server, thread = serve(FakeIntake(route), slots=slots, local_hop=False)
    held = None
    try:
        port = server.server_address[1]
        held = socket.create_connection(("127.0.0.1", port))
        deadline = time.monotonic() + 10
        while slots.open() < 1 and time.monotonic() < deadline:
            time.sleep(0.02)
        extra = socket.create_connection(("127.0.0.1", port))
        extra.settimeout(10)
        try:
            assert extra.recv(1) == b""
        except ConnectionResetError:
            pass
        extra.close()
    finally:
        if held is not None:
            held.close()
        stop(server, thread)


def test_the_direct_construction_door_is_the_local_hop_door():
    assert DirectRecipeIntake.local_hop is True
    assert not getattr(battery_intake.BatteryIntake, "local_hop", False)
