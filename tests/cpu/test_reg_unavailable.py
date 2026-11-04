"""REG-UNAVAILABLE (TL 4 Nov 03:14-03:44; Validator 03:15, 05:17): 67 tasks on four doors were never graded because the
registration snapshot went stale mid-grade (the public chain endpoint refused WebSocket upgrades, HTTP 429, retry after
60 s, from one shared IP), and the give-back of each failed task itself raised, so no FAILED_INFRA row was written.

Claims:
- the receiver's chain reader keeps ONE connection open across reads; a policy refusal starts a cool-down of the
  endpoint's Retry-After during which reads fail at once (typed PROVIDER_RATE_LIMITED) without touching the endpoint;
  a dropped connection is reopened; reads from any thread / event loop share it; the 60 s freshness is unchanged;
- `AutoGrader._give_back` reads the pack digest without opening the owner's provider, so a stale snapshot (planted:
  the provider open raises the registration code) still gives the task back as RELEASED / FAILED_INFRA, uncharged;
(The one-shot re-queue of the never-graded tasks and the undelivered-slot release are head A2.)
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import types
from types import SimpleNamespace

import pytest

from carbon.battery import intake as battery_intake
from carbon.chain import sdk
from carbon.chain.adapter import translate
from carbon.chain.models import ChainContext, ChainFailure, FailureCode

GENESIS = "0x" + "a" * 64
A, B, C, D = ("rtsk_" + c * 64 for c in "abcd")


def _context():
    return ChainContext("localnet", "ws://127.0.0.1:9944", "development-a", GENESIS, 1)


def _graph():
    return {
        "netuid": 1,
        "num_uids": 1,
        "hotkeys": ["hot-a"],
        "coldkeys": ["cold-a"],
        "block_at_registration": [2],
    }


class RpcConnectionError(Exception):
    pass


class RpcPolicyError(RpcConnectionError):
    def __init__(self, message, *, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class ChainError(Exception):
    pass


class Endpoint:
    """The fake endpoint: counts WebSocket upgrades (connects) and reads; scripted failures."""

    def __init__(self):
        self.upgrades = 0
        self.reads = 0
        self.closes = 0
        self.connect_fails = []  # exceptions raised by the next connects
        self.read_fails = []  # exceptions raised by the next reads


def _fake_sdk(endpoint):
    class Substrate:
        def __init__(self, url, **kw):
            assert kw == {
                "fallback_endpoints": [],
                "archive_endpoints": [],
                "retry_forever": False,
            }

        async def connect(self):
            if endpoint.connect_fails:
                raise endpoint.connect_fails.pop(0)
            endpoint.upgrades += 1

    class Client:
        def __init__(self, url, *, substrate):
            self.substrate = substrate

        async def close(self):
            endpoint.closes += 1

    return types.SimpleNamespace(
        RpcSubstrate=Substrate,
        Client=Client,
        RpcConnectionError=RpcConnectionError,
        RpcPolicyError=RpcPolicyError,
        ChainError=ChainError,
    )


@pytest.fixture
def endpoint(monkeypatch):
    found = Endpoint()

    async def observe(bt, substrate, client, context):
        if found.read_fails:
            raise found.read_fails.pop(0)
        found.reads += 1
        return translate(context, 10 + found.reads, "0x" + "b" * 64, 100000, _graph())

    monkeypatch.setattr(sdk, "_observe", observe)
    monkeypatch.setattr(
        sdk.PersistentBittensorReader, "_sdk", staticmethod(lambda: _fake_sdk(found))
    )
    return found


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_reads_share_one_open_connection(endpoint):
    reader = sdk.PersistentBittensorReader()
    blocks = [asyncio.run(reader.capture(_context())).finalized_block for _ in range(5)]
    assert blocks == [11, 12, 13, 14, 15]
    assert endpoint.upgrades == 1 and endpoint.closes == 0


def test_reads_from_other_threads_and_loops_share_it(endpoint):
    reader = sdk.PersistentBittensorReader()
    done = []

    def worker():
        done.append(asyncio.run(reader.capture(_context())).finalized_block)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert sorted(done) == [11, 12, 13, 14] and endpoint.upgrades == 1


def test_a_policy_refusal_cools_down_for_retry_after_without_touching_the_endpoint(
    endpoint,
):
    clock = Clock()
    reader = sdk.PersistentBittensorReader(clock=clock)
    endpoint.connect_fails.append(RpcPolicyError("PRIVATE 429", retry_after="60"))
    with pytest.raises(ChainFailure) as refused:
        asyncio.run(reader.capture(_context()))
    assert refused.value.code is FailureCode.RATE_LIMITED
    assert "PRIVATE" not in str(refused.value)
    clock.now += 59
    with pytest.raises(ChainFailure) as cooling:
        asyncio.run(reader.capture(_context()))
    assert cooling.value.code is FailureCode.RATE_LIMITED
    assert (
        endpoint.upgrades == 0 and endpoint.reads == 0
    )  # no upgrade attempted inside the cool-down
    clock.now += 2
    assert asyncio.run(reader.capture(_context())).finalized_block == 11
    assert endpoint.upgrades == 1


def test_a_refused_request_on_an_open_connection_keeps_it(endpoint):
    clock = Clock()
    reader = sdk.PersistentBittensorReader(clock=clock)
    asyncio.run(reader.capture(_context()))
    endpoint.read_fails.append(RpcPolicyError("PRIVATE", retry_after=None))
    with pytest.raises(ChainFailure):
        asyncio.run(reader.capture(_context()))
    clock.now += reader._base_delay + 0.1  # no Retry-After: the backoff's first step
    asyncio.run(reader.capture(_context()))
    assert endpoint.upgrades == 1 and endpoint.closes == 0


def test_a_dropped_connection_is_reopened_on_the_next_read(endpoint):
    reader = sdk.PersistentBittensorReader()
    asyncio.run(reader.capture(_context()))
    endpoint.read_fails.append(RpcConnectionError("PRIVATE"))
    with pytest.raises(ChainFailure) as dropped:
        asyncio.run(reader.capture(_context()))
    assert dropped.value.code is FailureCode.UNAVAILABLE
    asyncio.run(reader.capture(_context()))
    assert endpoint.upgrades == 2 and endpoint.closes == 1


def test_a_hung_read_times_out_drops_the_connection_and_the_next_read_reconnects(
    endpoint, monkeypatch
):
    # Validator 4 Nov 07:18: a half-open socket must not block every later read.
    real = sdk._observe
    hung = []

    async def hung_once(bt, substrate, client, context):
        if not hung:
            hung.append(True)
            await asyncio.Event().wait()  # a read that never answers
        return await real(bt, substrate, client, context)

    monkeypatch.setattr(sdk, "_observe", hung_once)
    reader = sdk.PersistentBittensorReader()
    reader._read_timeout = 0.3
    with pytest.raises(ChainFailure) as hung:
        asyncio.run(reader.capture(_context()))
    assert hung.value.code is FailureCode.UNAVAILABLE
    assert reader._open is None  # the stuck connection is forgotten at once
    assert asyncio.run(reader.capture(_context())).finalized_block == 11
    assert endpoint.upgrades == 2  # the next read opened a fresh connection


def test_a_hung_connect_times_out_too(endpoint, monkeypatch):
    reader = sdk.PersistentBittensorReader()
    reader._read_timeout = 0.3
    real = _fake_sdk(endpoint)

    class Hanging(real.RpcSubstrate):
        async def connect(self):
            await asyncio.Event().wait()

    hanging = types.SimpleNamespace(**{**vars(real), "RpcSubstrate": Hanging})
    monkeypatch.setattr(
        sdk.PersistentBittensorReader, "_sdk", staticmethod(lambda: hanging)
    )
    with pytest.raises(ChainFailure) as hung:
        asyncio.run(reader.capture(_context()))
    assert hung.value.code is FailureCode.UNAVAILABLE and reader._open is None


def test_the_read_timeout_is_20_seconds():
    assert sdk.PersistentBittensorReader._read_timeout == 20.0


def test_the_freshness_window_is_unchanged():
    assert battery_intake.SNAPSHOT_MAX_AGE_S == 60.0


def test_the_receiver_reads_the_chain_through_the_persistent_reader():
    import inspect

    from carbon.challenge_validator import direct_receiver

    source = inspect.getsource(direct_receiver)
    assert "PersistentBittensorReader() if reader is None else reader" in source
    assert "BittensorReader() if reader is None" not in source.replace(
        "PersistentBittensorReader() if reader is None", ""
    )


# ---------------------------------------------------------------- the give-back never needs the registration


def _ledger(tmp_path):
    from carbon.challenge_validator.exam_cap import ExamCap
    from carbon.challenge_validator.ledger import AttemptLedger

    root = tmp_path / "receiver"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    ledger = AttemptLedger(root / "attempts.sqlite3")
    ExamCap(ledger)  # the exam tables
    return root, ledger


def _rows(ledger, task):
    with ledger._db() as db:
        return db.execute(
            "SELECT state, status FROM exam_graded WHERE submission_id=?", (task,)
        ).fetchall()


def test_a_stale_snapshot_still_gives_the_task_back_as_failed_infra(tmp_path):
    from carbon.challenge_validator import auto_grade
    from carbon.challenge_validator.interface import Unavailable

    root, ledger = _ledger(tmp_path)

    def stale(owner):
        raise Unavailable("direct_provider_registration_unavailable")

    class Ledger:
        """The real exam ledger, listing one submitted task."""

        def __getattr__(self, name):
            return getattr(ledger, name)

        def submitted_outcomes(self, contract):
            return (A,)

    adapter = SimpleNamespace(
        contract_digest="sha256:" + "0" * 64,
        ledger=Ledger(),
        owner=lambda submission_id: "hot",
        _provider=stale,
        discovery=SimpleNamespace(evaluation_pack_digest="sha256:k"),
        challenge_id="f02",
        challenge_version="2.5",
    )
    intake = SimpleNamespace(
        adapter=adapter,
        retain_result=lambda *a, **k: stale("hot"),
    )
    grader = auto_grade.AutoGrader(intake, root)
    assert grader.run_once() == (A, "FAILED")
    marker = json.loads((root / "auto-grade" / "markers" / (A + ".json")).read_text())
    assert (
        marker["state"] == "FAILED" and marker["code"] == "Unavailable"
    )  # no ':unrecorded'
    assert _rows(ledger, A) == [
        ("RELEASED", "FAILED_INFRA")
    ]  # uncharged, on the record
