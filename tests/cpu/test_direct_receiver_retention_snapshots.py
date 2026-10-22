"""A retain or regrade run keeps a fresh finalized snapshot for its whole life
(Validator ruling VALIDATOR_RULING_RECV3_FLOWCHECK_20261022, Follow-up 2).

Serve mode gets fresh snapshots from the intake. A retain or regrade has none,
so a run longer than the window's 60 s freshness found no snapshot at the
provider's registration re-check and refused with
``direct_provider_registration_unavailable``. The refresher reads a finalized
snapshot every 20 s into the same ReceiverSnapshotWindow; the window is not
lengthened. No chain, network or spend: a scripted reader and a fake clock."""

from __future__ import annotations

import io
import os
import threading
import time
from contextlib import redirect_stderr
from dataclasses import replace
from pathlib import Path

import pytest
from test_c08_authenticated_miner_mcp import CONTEXT, _snapshot

from carbon.battery import intake
from carbon.chain.models import CARBON_NETUID, CARBON_NETWORK, ChainContext
from carbon.challenge_validator import direct_receiver as receiver

OWNER = "5" + "1" * 47
RECEIVER = "5" + "3" * 47
POSIX = pytest.mark.skipif(os.name == "nt", reason="POSIX owner-only receiver root")

CONTEXT_FOR_NETWORK = ChainContext(
    CARBON_NETWORK,
    CONTEXT.endpoint,
    CONTEXT.provider,
    CONTEXT.genesis_hash,
    CARBON_NETUID,
)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def _fresh(clock, blocks):
    return replace(
        _snapshot(sender=OWNER, receiver=RECEIVER, context=CONTEXT_FOR_NETWORK),
        finalized_block=blocks,
        block_hash="0x" + f"{blocks:064x}"[-64:],
        timestamp_ms=int(clock() * 1000),
    )


class Reader:
    """A scripted chain reader: each capture is a newer finalized snapshot at
    the clock's current time, or a failure."""

    def __init__(self, clock, start_block, fail=False):
        self.clock, self.block, self.fail, self.calls = clock, start_block, fail, 0

    async def capture(self, context):
        self.calls += 1
        if self.fail:
            raise OSError("test-only chain read failure")
        self.block += 1
        return _fresh(self.clock, self.block)


def _window(tmp_path, clock):
    root = receiver._private_directory(tmp_path / "receiver")
    window = receiver.ReceiverSnapshotWindow(
        root, CONTEXT_FOR_NETWORK, RECEIVER, clock=clock
    )
    window.add(_fresh(clock, 100))
    return window


def _wait(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_the_period_is_20_seconds_and_the_window_is_not_lengthened():
    assert receiver.RETENTION_REFRESH_S == 20.0
    assert intake.SNAPSHOT_MAX_AGE_S == 60.0


@POSIX
def test_a_run_past_60_seconds_keeps_its_snapshot_with_the_refresher(tmp_path):
    clock = Clock(time.time())
    window = _window(tmp_path, clock)
    assert window.latest() is not None
    reader = Reader(clock, 100)
    with receiver.retention_snapshots(window, CONTEXT_FOR_NETWORK, reader, period=0.01):
        # 90 fake seconds pass while the run works; the refresher keeps reading.
        for _ in range(9):
            clock.now += 10
            assert _wait(lambda: window.latest() is not None)
            seen = reader.calls
            assert _wait(lambda: reader.calls > seen)
        assert window.latest() is not None
        assert window.latest().finalized_block > 100
    assert reader.calls >= 9


@POSIX
def test_without_the_refresher_the_startup_snapshot_ages_out(tmp_path):
    clock = Clock(time.time())
    window = _window(tmp_path, clock)
    clock.now += 61
    assert window.latest() is None  # the registration re-check would refuse


@POSIX
def test_the_refresher_stops_with_the_run(tmp_path):
    clock = Clock(time.time())
    window = _window(tmp_path, clock)
    reader = Reader(clock, 100)
    with receiver.retention_snapshots(window, CONTEXT_FOR_NETWORK, reader, period=0.01):
        assert _wait(lambda: reader.calls >= 2)
    after = reader.calls
    time.sleep(0.2)
    assert reader.calls == after
    assert not [
        t for t in threading.enumerate() if t.name == "retention-snapshot-refresher"
    ]


@POSIX
def test_a_run_that_raises_still_stops_the_refresher(tmp_path):
    clock = Clock(time.time())
    window = _window(tmp_path, clock)
    reader = Reader(clock, 100)
    with pytest.raises(RuntimeError, match="the run failed"):
        with receiver.retention_snapshots(
            window, CONTEXT_FOR_NETWORK, reader, period=0.01
        ):
            raise RuntimeError("the run failed")
    after = reader.calls
    time.sleep(0.1)
    assert reader.calls == after


@POSIX
def test_a_failed_read_is_infrastructure_not_a_candidate_failure(tmp_path):
    clock = Clock(time.time())
    window = _window(tmp_path, clock)
    reader = Reader(clock, 100, fail=True)
    err = io.StringIO()
    with redirect_stderr(err):
        with receiver.retention_snapshots(
            window, CONTEXT_FOR_NETWORK, reader, period=0.01
        ):
            assert _wait(lambda: reader.calls >= 3)
            # The run itself is not interrupted by the read failure.
            clock.now += 61
            assert window.latest() is None
    log = err.getvalue()
    # One structured line by exception type only: no message, path or hotkey.
    assert log.count("snapshot_refresh_failed") == 1
    assert "OSError" in log and "test-only" not in log


@POSIX
def test_a_lagged_read_never_restores_an_earlier_registration(tmp_path):
    clock = Clock(time.time())
    window = _window(tmp_path, clock)
    reader = Reader(clock, 100)
    with receiver.retention_snapshots(window, CONTEXT_FOR_NETWORK, reader, period=0.01):
        assert _wait(
            lambda: window.latest() is not None
            and window.latest().finalized_block > 102
        )
        high = window.latest().finalized_block
        # A lagging read (an older finalized block) is ignored by the durable
        # high-water the refresher writes through.
        window.add(_fresh(clock, 101))
        assert window.latest().finalized_block >= high
