"""Source upload appends, never rewrites (live 116, 19 Nov 2026: each <= 8 KiB chunk stored the whole partial again as a
new workspace object and never removed the old one, so later chunks' storage scans grew without end). V2's five
conditions (RECEIPTS 16:04Z): the limits see the same amount at the same point; no door-wide limit is in this path; one
upload is serial, different owners run in parallel; the received count is the file's length, exact after a crash; the
same refusal codes. Fixture campaigns only.
"""

from __future__ import annotations

import threading
import time

import pytest
from test_direct_source_staging import _ledger, _request

from carbon import research
from carbon.development_session import direct_source_staging as dss
from carbon.development_session.research_ledger import (
    MINER_CEILING_REACHED,
    LedgerRefusal,
)
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.level4 import staging, submission


def _body(n):
    """A graph document of ``n`` bytes (any bytes: a document is checked by its digest)."""
    return bytes((i * 7) % 251 for i in range(n))


def _name(body):
    return staging.WORKSPACE_PREFIX + submission.name(body)[7:] + ".json"


def _chunks(body, size=8192):
    return [(i, body[i : i + size]) for i in range(0, len(body), size)]


def _objects(ledger):
    root = ledger.root / "workspace-objects"
    return sorted(p.name for p in root.iterdir()) if root.is_dir() else []


def test_chunks_append_one_file_and_store_no_object_until_complete(tmp_path):
    ledger = _ledger(tmp_path)
    body = _body(100_000)
    parts = _chunks(body)
    for offset, chunk in parts[:-1]:
        result = dss.stage_source(
            ledger, "alice", _request(_name(body), body, offset, chunk)
        )
        assert result.received_bytes == offset + len(chunk) and not result.complete
        assert _objects(ledger) == []  # nothing superseded is left behind
    path = dss._partial_path(
        ledger, "alice", dss._partial_name(_request(_name(body), body, 0, body[:1]))
    )
    assert path.stat().st_size == parts[-1][0]
    offset, chunk = parts[-1]
    assert dss.stage_source(
        ledger, "alice", _request(_name(body), body, offset, chunk)
    ).complete
    assert ResearchWorkspace(ledger, "alice").get(_name(body)) == body
    assert len(_objects(ledger)) == 1 and not path.exists()


def test_the_storage_check_sees_the_same_amount_at_the_same_point(
    tmp_path, monkeypatch
):
    """Before each chunk is accepted the check is asked for the whole partial with the chunk plus 64 KiB, exactly the
    amount the earlier rewrite's `workspace.put` asked for; a refusal there accepts nothing.
    """
    ledger = _ledger(tmp_path)
    body = _body(30_000)
    asked = []
    real = ledger.check_storage_fast
    monkeypatch.setattr(
        ledger,
        "check_storage_fast",
        lambda additional=0: asked.append(additional) or real(additional),
    )
    for offset, chunk in _chunks(body)[:-1]:
        dss.stage_source(ledger, "alice", _request(_name(body), body, offset, chunk))
    assert asked == [
        offset + len(chunk) + 65536 for offset, chunk in _chunks(body)[:-1]
    ]

    def refuse(additional=0):
        raise LedgerRefusal(
            "miner budget: retained_bytes",
            code=MINER_CEILING_REACHED,
            dimension="retained_bytes",
            refused_at="storage_check",
        )

    monkeypatch.setattr(ledger, "check_storage_fast", refuse)
    offset, chunk = _chunks(body)[-1]
    path = dss._partial_path(
        ledger, "alice", dss._partial_name(_request(_name(body), body, 0, body[:1]))
    )
    before = path.stat().st_size
    with pytest.raises(LedgerRefusal):
        dss.stage_source(ledger, "alice", _request(_name(body), body, offset, chunk))
    assert path.stat().st_size == before  # nothing appended


def test_conflicts_replays_and_bounds_answer_as_before(tmp_path):
    ledger = _ledger(tmp_path)
    body = _body(20_000)
    first = _request(_name(body), body, 0, body[:8192])
    dss.stage_source(ledger, "alice", first)
    # a replay of held bytes changes nothing and says how much is held
    assert dss.stage_source(ledger, "alice", first).received_bytes == 8192
    # past the received bytes, or different bytes at a held offset: a conflict
    for bad in (
        _request(_name(body), body, 8193, body[8193:9000]),
        _request(_name(body), body, 0, b"y" * 8192),
    ):
        with pytest.raises(research.ResearchTaskProviderError) as refused:
            dss.stage_source(ledger, "alice", bad)
        assert (
            refused.value.code is research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
        )


def test_a_torn_append_is_completed_by_its_retry(tmp_path):
    """A crash mid-append leaves part of a chunk: its retry at the same offset appends only the rest (the file never
    shrinks) and the count is the file's length, so nothing is double-counted or missing.
    """
    ledger = _ledger(tmp_path)
    body = _body(20_000)
    dss.stage_source(ledger, "alice", _request(_name(body), body, 0, body[:8192]))
    path = dss._partial_path(
        ledger, "alice", dss._partial_name(_request(_name(body), body, 0, body[:1]))
    )
    with path.open("ab") as out:
        out.write(
            body[8192 : 8192 + 1000]
        )  # torn: 1,000 of the next chunk's 8,192 bytes
    result = dss.stage_source(
        ledger, "alice", _request(_name(body), body, 8192, body[8192:16384])
    )
    assert result.received_bytes == 16384 and path.stat().st_size == 16384
    assert path.read_bytes() == body[:16384]
    # the continuation check (the request buckets' read) reads the same length, from the file
    assert dss.continuation_at(
        ledger, "alice", _request(_name(body), body, 16384, body[16384:])
    )


def test_an_upload_the_earlier_layout_began_is_continued(tmp_path):
    ledger = _ledger(tmp_path)
    body = _body(20_000)
    first = _request(_name(body), body, 0, body[:8192])
    ResearchWorkspace(ledger, "alice").put(dss._partial_name(first), body[:8192])
    assert dss.continuation_at(
        ledger, "alice", _request(_name(body), body, 8192, body[8192:16384])
    )
    for offset, chunk in _chunks(body)[1:]:
        result = dss.stage_source(
            ledger, "alice", _request(_name(body), body, offset, chunk)
        )
    assert (
        result.complete and ResearchWorkspace(ledger, "alice").get(_name(body)) == body
    )


def test_one_upload_is_serial_and_two_owners_run_in_parallel(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    body = _body(40_000)
    inside, most, guard = {}, {}, threading.Lock()
    real = dss._append

    def counted(ledger_, workspace, request, *args):
        key = workspace.owner
        with guard:
            inside[key] = inside.get(key, 0) + 1
            most[key] = max(most.get(key, 0), inside[key])
            most["all"] = max(most.get("all", 0), sum(inside.values()))
        time.sleep(0.05)
        try:
            return real(ledger_, workspace, request, *args)
        finally:
            with guard:
                inside[key] -= 1

    monkeypatch.setattr(dss, "_append", counted)
    first = _request(_name(body), body, 0, body[:8192])

    def same(owner):
        dss.stage_source(ledger, owner, first)

    threads = [
        threading.Thread(target=same, args=(o,))
        for o in ("alice", "alice", "alice", "bob", "bob", "bob")
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert most["alice"] == 1 and most["bob"] == 1  # one upload: one stage at a time
    assert most["all"] == 2  # two owners: at once
    for owner in ("alice", "bob"):
        path = dss._partial_path(ledger, owner, dss._partial_name(first))
        assert path.stat().st_size == 8192  # three stages of one chunk: held once


def test_another_owner_never_sees_an_upload_it_does_not_hold(tmp_path):
    ledger = _ledger(tmp_path)
    body = _body(20_000)
    dss.stage_source(ledger, "alice", _request(_name(body), body, 0, body[:8192]))
    second = _request(_name(body), body, 8192, body[8192:16384])
    assert dss.continuation_at(ledger, "alice", second)
    assert not dss.continuation_at(ledger, "bob", second)
    with pytest.raises(research.ResearchTaskProviderError) as refused:
        dss.stage_source(ledger, "bob", second)
    assert refused.value.code is research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT


def test_a_resend_from_an_earlier_offset_appends_only_its_new_bytes(tmp_path):
    """V2 (ca445f32): a chunk whose held bytes equal its first bytes is accepted and only the rest is appended; a
    differing byte still refuses."""
    ledger = _ledger(tmp_path)
    body = _body(20_000)
    dss.stage_source(ledger, "alice", _request(_name(body), body, 0, body[:5000]))
    result = dss.stage_source(
        ledger, "alice", _request(_name(body), body, 1000, body[1000:9192])
    )
    path = dss._partial_path(
        ledger, "alice", dss._partial_name(_request(_name(body), body, 0, body[:1]))
    )
    assert result.received_bytes == 9192 and path.read_bytes() == body[:9192]
    changed = bytearray(body[2000:10000])
    changed[0] ^= 1
    with pytest.raises(research.ResearchTaskProviderError) as refused:
        dss.stage_source(
            ledger, "alice", _request(_name(body), body, 2000, bytes(changed))
        )
    assert refused.value.code is research.ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
    assert path.read_bytes() == body[:9192]


def test_a_refused_overlap_leaves_the_held_bytes_unchanged(tmp_path, monkeypatch):
    ledger = _ledger(tmp_path)
    body = _body(20_000)
    dss.stage_source(ledger, "alice", _request(_name(body), body, 0, body[:5000]))
    path = dss._partial_path(
        ledger, "alice", dss._partial_name(_request(_name(body), body, 0, body[:1]))
    )

    def refuse(additional=0):
        raise LedgerRefusal(
            "miner budget: retained_bytes",
            code=MINER_CEILING_REACHED,
            dimension="retained_bytes",
            refused_at="storage_check",
        )

    monkeypatch.setattr(ledger, "check_storage_fast", refuse)
    with pytest.raises(LedgerRefusal):
        dss.stage_source(
            ledger, "alice", _request(_name(body), body, 1000, body[1000:9192])
        )
    assert path.read_bytes() == body[:5000]  # nothing held was lost, nothing appended
