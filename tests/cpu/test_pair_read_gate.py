"""Owner LO-3: grades that read the repeat pair under the same ceiling read together (`pair_read_gate`), while
`pair_read_bound.py`, a Motor 1.8 producer file, keeps every byte (v2 20 Nov 16:12:44Z)."""

from __future__ import annotations

import contextlib
import importlib
import inspect
import json
import random
import struct
import sys
import threading
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from test_inference_pair_evidence import sha
from test_pair_read_bound import FIXED, ROWS, WIDTH, big_pair

from carbon.challenge_validator import pair_read_gate as gate
from carbon.scoring import inference_pair_evidence as reader
from carbon.scoring import pair_read_bound as bound

SIZED = bound.pair_bytes(ROWS, WIDTH)
BIGGER = bound.pair_bytes(2 * ROWS, WIDTH)


@pytest.fixture(autouse=True)
def installed():
    assert gate.install() is True
    assert gate.install() is True  # idempotent
    assert bound._LOCK is gate._GATE
    assert bound.held is gate.held and bound.raised is gate.raised
    assert reader._MAX_BYTES == FIXED
    yield
    assert reader._MAX_BYTES == FIXED


@pytest.fixture(scope="module")
def motor18_pair():
    rng = random.Random(18)
    return big_pair(ROWS, WIDTH, lambda: rng.uniform(-1.0, 1.0))


def test_the_gate_moves_no_producer_byte_and_no_worker_build_input():
    importlib.import_module("carbon.challenge_kit.version_registry")
    importlib.import_module("carbon.scoring.motor_sealed_dual_pack")
    from carbon.reconstruction.worker import build_inputs
    from carbon.scoring import motor18_dual_pack
    from carbon.scoring import physical_dual_pack as physical

    pins = json.loads(
        (
            ROOT / "scripts" / "validator_host_classes" / "producer_successor.json"
        ).read_text(encoding="utf-8")
    )["rows"]["electric-motor-magnetics 1.8"]
    # the pinned producer identity of Motor 1.8 still binds: pair_read_bound.py is byte for byte main's
    assert motor18_dual_pack.producer_digest() == pins["producer_digest"]
    assert "pair_read_gate.py" not in (
        *motor18_dual_pack.FILES,
        *physical._SHARED_FILES,
    )
    assert "carbon/challenge_validator/pair_read_gate.py" not in build_inputs.paths()
    # the producer file's own code still reaches its lock and its blocks through the module at call time
    assert "with _LOCK:" in inspect.getsource(bound)
    produce = inspect.getsource(bound.size_produce)
    assert "with held():" in produce and "with raised(" in produce


def test_the_door_installs_the_gate_when_retention_is_imported():
    retention = importlib.import_module(
        "carbon.challenge_validator.lean_recipe_retention"
    )
    assert bound._LOCK is gate._GATE
    source = inspect.getsource(retention)
    # at import (module level, before any grade) and again on each sized block outside the produce
    assert chr(10) + "_pair_read_gate.install()" + chr(10) in source
    assert "_pair_read_gate.install()" in inspect.getsource(
        retention._sized_pair_ceiling
    )


def _run_together(blocks, timeout=10):
    """One thread per ``(name, context manager factory)``; each records the ceiling it read under and stays inside its
    block briefly. Returns (most inside at once, values)."""
    inside, values, lock = set(), {}, threading.Lock()
    most = []
    go = threading.Event()

    def run(name, block):
        with block() as value:
            with lock:
                inside.add(name)
                values[name] = reader._MAX_BYTES if value is None else value
                most.append(len(inside))
            go.wait(0.5)
            with lock:
                inside.discard(name)

    threads = [threading.Thread(target=run, args=item) for item in blocks]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout)
    go.set()
    return max(most), values


def test_lo3_grades_at_one_ceiling_read_together_each_under_exactly_its_own_value():
    """Every 1.8 grade's block reads under the same sized ceiling, so they no longer wait for each other; each reads
    under exactly the value the one process-wide lock gave it."""
    together, values = _run_together(
        [(n, lambda: bound.raised(SIZED)) for n in range(4)]
    )
    assert together == 4
    assert set(values.values()) == {SIZED}


def test_lo3_the_sized_produce_of_two_grades_runs_together(monkeypatch):
    from carbon.scoring import physical_dual_pack as physical

    both = threading.Barrier(2, timeout=5)
    seen = []

    def original(adapter, **kwargs):
        both.wait()  # breaks (BrokenBarrierError) unless both grades are inside at once
        seen.append(reader._MAX_BYTES)
        return adapter.VERSION

    class Adapter:
        def __init__(self, challenge, version):
            self.CHALLENGE, self.VERSION = challenge, version

    monkeypatch.setattr(physical, "produce", original)
    monkeypatch.setattr(bound, "_SIZED", set())
    bound.size_produce("electric-motor-magnetics", "1.8")
    bank = {"case_ids": list(range(ROWS)), "references": [[0.0] * WIDTH]}
    results = []

    def grade():
        results.append(
            physical.produce(Adapter("electric-motor-magnetics", "1.8"), bank=bank)
        )

    threads = [threading.Thread(target=grade) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert results == ["1.8", "1.8"] and seen == [SIZED, SIZED]
    # another version's produce reads under the reader's own ceiling, once they have left
    seen.clear()
    both = threading.Barrier(1)
    assert (
        physical.produce(Adapter("electric-motor-magnetics", "1.6"), bank=bank) == "1.6"
    )
    assert seen == [FIXED]


def test_lo3_another_ceiling_never_reads_alongside_and_waits_in_arrival_order():
    small = bound.pair_bytes(300, WIDTH)
    order, release = [], threading.Event()
    first_in = threading.Event()

    def block(name, factory, hold=None):
        def run():
            with factory() as value:
                order.append((name, reader._MAX_BYTES, value))
                if hold is not None:
                    first_in.set()
                    hold.wait(10)

        return threading.Thread(target=run)

    a = block("a", lambda: bound.raised(SIZED), hold=release)
    a.start()
    assert first_in.wait(10)
    b = block("b", lambda: bound.raised(small))
    b.start()
    b.join(0.2)
    # same value as a, but arrived after b: no barging past b
    c = block("c", lambda: bound.raised(SIZED))
    c.start()
    c.join(0.2)
    assert [o[0] for o in order] == ["a"] and b.is_alive() and c.is_alive()
    release.set()
    for t in (a, b, c):
        t.join(10)
    assert [o[0] for o in order] == ["a", "b", "c"]
    assert order[1][1] == max(FIXED, small) and order[2][1] == SIZED


def test_lo3_held_waits_while_a_sized_ceiling_is_up_then_reads_the_reader_s_own():
    up, release = threading.Event(), threading.Event()
    seen = {}

    def raise_and_wait():
        with bound.raised(SIZED):
            up.set()
            release.wait(10)

    def other():
        with bound.held():
            seen["held"] = reader._MAX_BYTES

    worker = threading.Thread(target=raise_and_wait)
    worker.start()
    assert up.wait(10)
    waiting = threading.Thread(target=other)
    waiting.start()
    waiting.join(0.3)
    try:
        assert waiting.is_alive() and "held" not in seen
    finally:
        release.set()
        worker.join(10)
        waiting.join(10)
    assert seen["held"] == FIXED


def test_lo3_nesting_reads_as_the_reentrant_lock_did():
    with bound.raised(SIZED) as outer:
        with bound.raised(SIZED) as same, bound.held():
            assert same == outer == reader._MAX_BYTES == SIZED  # same value: just nests
        # alone: raised further, put back on the way out
        with bound.raised(BIGGER) as inner:
            assert inner == reader._MAX_BYTES == BIGGER
        assert reader._MAX_BYTES == SIZED
        with bound.raised(1) as low:
            assert low == SIZED  # never lowered


def test_lo3_a_nested_raise_waits_until_its_block_is_alone():
    other_in, other_go, seen = threading.Event(), threading.Event(), []

    def other():
        with bound.raised(SIZED):
            other_in.set()
            other_go.wait(10)
            seen.append(("other", reader._MAX_BYTES))

    t = threading.Thread(target=other)
    t.start()
    assert other_in.wait(10)
    done = threading.Event()

    def nested():
        with bound.raised(SIZED), bound.raised(BIGGER):
            seen.append(("nested", reader._MAX_BYTES))
        done.set()

    n = threading.Thread(target=nested)
    n.start()
    assert not done.wait(0.3)  # waits: the other holder still reads under SIZED
    other_go.set()
    t.join(10)
    n.join(10)
    assert seen == [("other", SIZED), ("nested", BIGGER)]


def test_lo3_nobody_joins_a_nested_value_before_it_is_put_back():
    inside, go, seen = threading.Event(), threading.Event(), []

    def nested():
        with bound.raised(SIZED):
            with bound.raised(BIGGER):
                inside.set()
                go.wait(10)
            seen.append(("put back", reader._MAX_BYTES))

    def newcomer():
        with bound.raised(BIGGER):
            seen.append(("newcomer", reader._MAX_BYTES))

    n = threading.Thread(target=nested)
    n.start()
    assert inside.wait(10)
    c = threading.Thread(target=newcomer)
    c.start()
    c.join(0.3)
    assert c.is_alive() and seen == []
    go.set()
    n.join(10)
    c.join(10)
    assert seen == [("put back", SIZED), ("newcomer", BIGGER)]


def test_lo3_two_nested_raises_at_once_refuse_rather_than_deadlock():
    both_in, release, errors = threading.Barrier(2), threading.Event(), []
    first_waiting = threading.Event()

    def holder(first):
        try:
            with bound.raised(SIZED):
                both_in.wait(10)
                if first:
                    first_waiting.set()
                    with bound.raised(BIGGER):
                        pass
                else:
                    assert first_waiting.wait(10)
                    release.wait(0.3)  # the first is now waiting to be alone
                    with bound.raised(BIGGER):
                        pass
        except gate.NestedCeilingConflict as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=holder, args=(f,)) for f in (True, False)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert not any(t.is_alive() for t in threads)
    assert errors == ["pair_read_bound_nested_conflict"]


@contextlib.contextmanager
def _original_raised(limit):
    """`pair_read_bound.raised`'s own body (main's bytes) as a caller that resolved it BEFORE `install` runs it: it
    reaches the module's `_LOCK` at call time, which is now the gate held alone."""
    with bound._LOCK:
        before = reader._MAX_BYTES
        reader._MAX_BYTES = max(before, limit)
        try:
            yield reader._MAX_BYTES
        finally:
            reader._MAX_BYTES = before


def test_an_original_code_block_after_install_holds_the_gate_alone():
    in_held, held_go = threading.Event(), threading.Event()
    in_old, old_go = threading.Event(), threading.Event()
    seen = []

    def shared():
        with bound.held():
            in_held.set()
            held_go.wait(10)
            seen.append(("held", reader._MAX_BYTES))

    def old():
        with _original_raised(SIZED) as value:
            in_old.set()
            old_go.wait(10)
            seen.append(("old", value, reader._MAX_BYTES))

    def newcomer():
        with bound.held():
            seen.append(("newcomer", reader._MAX_BYTES))

    s = threading.Thread(target=shared)
    s.start()
    assert in_held.wait(10)
    o = threading.Thread(target=old)
    o.start()
    # the original block waits for the shared holder to leave
    assert not in_old.wait(0.3)
    held_go.set()
    s.join(10)
    assert in_old.wait(10)
    n = threading.Thread(target=newcomer)
    n.start()
    n.join(0.3)
    # nobody joins the original block, even at the reader's own ceiling
    assert n.is_alive()
    old_go.set()
    o.join(10)
    n.join(10)
    assert seen == [("held", FIXED), ("old", SIZED, SIZED), ("newcomer", FIXED)]


def test_an_original_code_block_nests_the_installed_blocks_as_the_lock_did():
    with _original_raised(SIZED):
        with bound.held():
            assert reader._MAX_BYTES == SIZED
        with bound.raised(BIGGER) as inner:
            assert inner == reader._MAX_BYTES == BIGGER
        assert reader._MAX_BYTES == SIZED  # put back to the original block's own value
        with _original_raised(BIGGER) as again:  # re-entrant, as the RLock
            assert again == reader._MAX_BYTES == BIGGER
        assert reader._MAX_BYTES == SIZED


def test_the_installed_lock_acquires_alone_with_a_timeout_and_refuses_a_stray_release():
    up, release = threading.Event(), threading.Event()

    def raise_and_wait():
        with bound.raised(SIZED):
            up.set()
            release.wait(10)

    worker = threading.Thread(target=raise_and_wait)
    worker.start()
    try:
        assert up.wait(10)
        assert not bound._LOCK.acquire(timeout=0.2)
        assert not bound._LOCK.acquire(blocking=False)
    finally:
        release.set()
        worker.join(10)
    assert bound._LOCK.acquire(timeout=1)
    bound._LOCK.release()
    with pytest.raises(RuntimeError):
        bound._LOCK.release()


def test_lo3_bit_for_bit_concurrent_reads_equal_the_serial_read(motor18_pair):
    """The LO-3 condition at the reader: four Motor 1.8-size pairs read at once under the shared ceiling give exactly
    the outputs (and digests) one serial read under the old lock gives."""
    raw, kwargs = motor18_pair
    with _original_raised(SIZED):
        serial = reader.read_inference_pair(raw, registered_sha256=sha(raw), **kwargs)
    results, errors = [None] * 4, []

    def read(i):
        try:
            with bound.raised(SIZED):
                results[i] = reader.read_inference_pair(
                    raw, registered_sha256=sha(raw), **kwargs
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=read, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert errors == []

    # bit for bit: -0.0 vs 0.0 and NaN payloads included, never float ==
    def bits(evidence):
        return [struct.pack(f"<{len(o)}d", *o) for o in evidence.outputs]

    for got in results:
        assert bits(got) == bits(serial)
        assert got.sha256 == serial.sha256 and got.evidence == serial.evidence
