"""Grade storage once (owner rule #13): a decoded output stream kept as its framing, an op's inputs stored once per
ledger, and old grade folders moved to a store by digest with a local stub."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import time

import pytest

from carbon.challenge_validator import grade_archive
from carbon.development_session import research_carrier as carrier
from carbon.reconstruction.worker.protocol import (
    OUTPUT_FRAMES,
    compact_output_stream,
    decode_output_stream,
    reassembled_output_stream,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX links, modes and uids"
)


def _line(value):
    return json.dumps(value, sort_keys=True).encode() + b"\n"


def _stream(tmp_path, members):
    body = _line({"schema": "carbon.c03.output-stream.v1"})
    total = 0
    for path, data in members:
        body += _line({"path": path, "size": len(data)}) + data
        total += len(data)
    body += _line({"bytes": total, "end": True, "members": len(members)})
    operation = tmp_path / "operation-1"
    operation.mkdir()
    source = operation / "export.stream"
    source.write_bytes(body)
    return source, body


MEMBERS = [
    ("predictions.json", b"[[1.0, 2.0]]\n" * 5000),
    ("receipt.json", b'{"ok": true}'),
    ("nested/state.npz", bytes(range(256)) * 300),
]


def test_a_decoded_stream_is_kept_as_its_framing_and_rebuilds_byte_for_byte(tmp_path):
    source, body = _stream(tmp_path, MEMBERS)
    snapshot = source.parent / "snapshot"
    decode_output_stream(source, snapshot)
    assert (
        compact_output_stream(source, snapshot, expected="sha256:" + "1" * 64) is False
    )
    assert source.exists()
    expected = "sha256:" + hashlib.sha256(body).hexdigest()
    assert compact_output_stream(source, snapshot, expected=expected) is True
    assert not source.exists()
    frames = source.parent / OUTPUT_FRAMES
    assert frames.stat().st_size < 400
    rebuilt = b"".join(reassembled_output_stream(frames, snapshot))
    assert rebuilt == body
    assert hashlib.sha256(rebuilt).digest() == hashlib.sha256(body).digest()
    # once only: a second call changes nothing
    assert compact_output_stream(source, snapshot) is False


def test_a_stream_whose_body_differs_from_its_snapshot_is_kept_as_it_is(tmp_path):
    source, body = _stream(tmp_path, MEMBERS)
    snapshot = source.parent / "snapshot"
    decode_output_stream(source, snapshot)
    changed = snapshot / "receipt.json"
    changed.write_bytes(b'{"ok": fals}')
    assert compact_output_stream(source, snapshot) is False
    assert source.read_bytes() == body
    assert not (source.parent / OUTPUT_FRAMES).exists()
    assert [p.name for p in source.parent.iterdir() if p.name.startswith(".")] == []


def test_a_stream_that_does_not_parse_or_a_missing_snapshot_file_is_kept(tmp_path):
    source, body = _stream(tmp_path, MEMBERS)
    snapshot = source.parent / "snapshot"
    decode_output_stream(source, snapshot)
    (snapshot / "nested" / "state.npz").unlink()
    assert compact_output_stream(source, snapshot) is False
    assert source.read_bytes() == body
    source.write_bytes(b"not a stream\n")
    assert compact_output_stream(source, snapshot) is False
    assert source.read_bytes() == b"not a stream\n"


def _stage(ledger, operation, files):
    stage = ledger / operation / "input"
    stage.mkdir(parents=True)
    for name, (body, mode) in files.items():
        carrier._stage_once(stage / name, body, mode)
    return stage


def test_an_ops_inputs_are_stored_once_per_ledger_with_their_own_mode(tmp_path):
    files = {
        "program.py": (b"print(1)\n", 0o555),
        "state.npz": (b"\x00" * 70000, 0o444),
        "train.npz": (b"\x01" * 1000, 0o444),
    }
    first = _stage(tmp_path, "operation-a", files)
    second = _stage(tmp_path, "operation-b", files)
    for name, (body, mode) in files.items():
        a, b = os.stat(first / name), os.stat(second / name)
        assert (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)
        assert stat.S_IMODE(a.st_mode) == mode
        assert (second / name).read_bytes() == body
        assert a.st_nlink == 3  # the object and two ops
    objects = sorted(p.name for p in (tmp_path / carrier.INPUT_OBJECTS).iterdir())
    assert len(objects) == 3
    assert stat.S_IMODE(os.stat(tmp_path / carrier.INPUT_OBJECTS).st_mode) == 0o700
    # the same bytes with another mode: another object
    third = _stage(tmp_path, "operation-c", {"program.py": (b"print(1)\n", 0o444)})
    assert stat.S_IMODE(os.stat(third / "program.py").st_mode) == 0o444
    assert os.stat(third / "program.py").st_ino != os.stat(first / "program.py").st_ino


def test_an_object_that_changed_is_never_linked(tmp_path):
    body = b"x" * 5000
    first = _stage(tmp_path, "operation-a", {"inputs.npz": (body, 0o444)})
    stored = (
        tmp_path / carrier.INPUT_OBJECTS / (hashlib.sha256(body).hexdigest() + "-444")
    )
    os.chmod(stored, 0o644)
    second = _stage(tmp_path, "operation-b", {"inputs.npz": (body, 0o444)})
    assert os.stat(second / "inputs.npz").st_ino != os.stat(first / "inputs.npz").st_ino
    assert (second / "inputs.npz").read_bytes() == body
    assert stat.S_IMODE(os.stat(second / "inputs.npz").st_mode) == 0o444


def test_a_trusted_stage_binary_is_never_a_shared_object():
    assert "uv-bin" in carrier._NOT_STORED_ONCE


def _grade(tmp_path, age_days):
    state = tmp_path / "state"
    root = state / "auto-grade" / "artifacts" / ("rtsk_" + "a" * 64)
    root.mkdir(parents=True, mode=0o700)
    big = os.urandom(grade_archive.MIN_BYTES + 5)
    (root / "worker-evidence.json").write_bytes(big)
    os.chmod(root / "worker-evidence.json", 0o600)
    (root / "task-receipt.json").write_bytes(b"{}")
    old = time.time() - age_days * 86400
    for path in (root / "worker-evidence.json", root / "task-receipt.json", root):
        os.utime(path, (old, old))
    store = tmp_path / "store"
    store.mkdir()
    return state, root, big, store


def test_an_old_grade_moves_to_the_store_by_digest_and_restores_whole(tmp_path):
    state, root, big, store_root = _grade(tmp_path, 10)
    assert grade_archive.candidates(state, older_than_days=7) == [root]
    assert grade_archive.candidates(state, older_than_days=11) == []
    store = grade_archive.DirectoryStore(store_root)
    result = grade_archive.archive_tree(root, store)
    assert result == {"moved": 1, "bytes": len(big), "freed": len(big)}
    assert not (root / "worker-evidence.json").exists()
    assert (root / "task-receipt.json").read_bytes() == b"{}"  # small records stay
    stub = json.loads((root / grade_archive.STUB).read_bytes())
    sha = hashlib.sha256(big).hexdigest()
    assert stub["files"] == {
        "worker-evidence.json": {"sha256": sha, "size": len(big), "mode": 0o600}
    }
    assert (store_root / sha[:2] / sha).read_bytes() == big
    assert grade_archive.candidates(state, older_than_days=7) == []
    assert grade_archive.restore_if_archived(root) is True
    assert (root / "worker-evidence.json").read_bytes() == big
    assert stat.S_IMODE(os.stat(root / "worker-evidence.json").st_mode) == 0o600
    assert not (root / grade_archive.STUB).exists()
    assert grade_archive.restore_if_archived(root) is False


def test_a_store_copy_that_differs_is_never_restored(tmp_path):
    _state, root, big, store_root = _grade(tmp_path, 10)
    store = grade_archive.DirectoryStore(store_root)
    grade_archive.archive_tree(root, store)
    sha = hashlib.sha256(big).hexdigest()
    copy = store_root / sha[:2] / sha
    os.chmod(copy, 0o600)
    copy.write_bytes(b"other")
    with pytest.raises(grade_archive.ArchiveRefused):
        grade_archive.restore_tree(root)
    assert not (root / "worker-evidence.json").exists()
    assert (root / grade_archive.STUB).exists()


def test_a_linked_file_frees_nothing_until_its_last_name_goes(tmp_path):
    _state, root, _big, store_root = _grade(tmp_path, 10)
    os.link(root / "worker-evidence.json", tmp_path / "elsewhere")
    result = grade_archive.archive_tree(root, grade_archive.DirectoryStore(store_root))
    assert result["moved"] == 1 and result["freed"] == 0


def test_the_archive_has_no_default_age_or_store(tmp_path):
    with pytest.raises(grade_archive.ArchiveRefused):
        grade_archive.candidates(tmp_path, older_than_days=0)
    with pytest.raises(SystemExit):
        grade_archive.main(["--state", str(tmp_path)])
    with pytest.raises(grade_archive.ArchiveRefused):
        grade_archive.DirectoryStore(tmp_path / "absent")


def _ledger_row(ledger, state, result):
    import sqlite3

    db = sqlite3.connect(ledger / "campaign.sqlite3")
    db.execute(
        "CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, state TEXT NOT NULL, result BLOB)"
    )
    db.execute(
        "INSERT INTO operations VALUES(?,?,?)",
        (str(len(db.execute("SELECT id FROM operations").fetchall())), state, result),
    )
    db.commit()
    db.close()


def _counts(**changes):
    return {
        "streams": 0,
        "not_succeeded": 0,
        "compacted": 0,
        "kept": 0,
        "bytes": 0,
        **changes,
    }


def test_the_backfill_compacts_only_settled_succeeded_streams_with_their_digest(
    tmp_path,
):
    state = tmp_path / "state"
    ledger = state / "owners" / "o1" / "ledger"
    ledger.mkdir(parents=True)
    source, body = _stream(ledger, MEMBERS)
    decode_output_stream(source, source.parent / "snapshot")
    recorded = "sha256:" + hashlib.sha256(body).hexdigest()
    old = time.time() - 7200
    os.utime(source, (old, old))
    # no ledger row (running, left running, adopted, unknown): never touched
    assert grade_archive.compact_streams(state, apply=True) == _counts(not_succeeded=1)
    _ledger_row(ledger, "RESERVED", json.dumps({"operation": "operation-1"}))
    assert grade_archive.compact_streams(state, apply=True) == _counts(not_succeeded=1)
    _ledger_row(
        ledger,
        "SUCCEEDED",
        json.dumps({"operation": "operation-1", "output_digest": recorded}),
    )
    listing = tmp_path / "streams.tsv"
    dry = grade_archive.compact_streams(state, listing=listing)
    assert dry == _counts(streams=1, bytes=len(body))
    assert listing.read_text() == f"{source}\t{len(body)}\t{recorded}\n"
    assert source.exists()
    done = grade_archive.compact_streams(state, apply=True)
    assert done == _counts(streams=1, compacted=1, bytes=len(body))
    assert not source.exists()
    assert (source.parent / OUTPUT_FRAMES).exists()


def test_the_backfill_keeps_a_stream_that_is_not_its_recorded_digest(tmp_path):
    state = tmp_path / "state"
    ledger = state / "owners" / "o1" / "ledger"
    ledger.mkdir(parents=True)
    source, body = _stream(ledger, MEMBERS)
    decode_output_stream(source, source.parent / "snapshot")
    old = time.time() - 7200
    os.utime(source, (old, old))
    _ledger_row(
        ledger,
        "SUCCEEDED",
        json.dumps({"operation": "operation-1", "output_digest": "sha256:" + "0" * 64}),
    )
    done = grade_archive.compact_streams(state, apply=True)
    assert done == _counts(streams=1, kept=1)
    assert source.read_bytes() == body
    assert not (source.parent / OUTPUT_FRAMES).exists()


def test_a_fresh_stream_is_never_backfilled(tmp_path):
    state = tmp_path / "state"
    ledger = state / "owners" / "o1" / "ledger"
    ledger.mkdir(parents=True)
    source, body = _stream(ledger, MEMBERS)
    decode_output_stream(source, source.parent / "snapshot")
    _ledger_row(
        ledger,
        "SUCCEEDED",
        json.dumps(
            {
                "operation": "operation-1",
                "output_digest": "sha256:" + hashlib.sha256(body).hexdigest(),
            }
        ),
    )
    assert grade_archive.compact_streams(state, apply=True) == _counts()
    assert source.exists()


def test_a_grades_breakdown_and_gate_records_stay_on_the_host_at_any_size(tmp_path):
    _state, root, _big, store_root = _grade(tmp_path, 10)
    evaluation = root.parent / (root.name + ".evaluation")
    evaluation.mkdir(mode=0o700)
    kept = {
        root.name + ".grade-breakdown.json": os.urandom(grade_archive.MIN_BYTES + 1),
        "exam-total-se.json": os.urandom(grade_archive.MIN_BYTES + 1),
        "gate-failures.json": os.urandom(grade_archive.MIN_BYTES + 1),
    }
    for name, raw in kept.items():
        (evaluation / name).write_bytes(raw)
    moved = os.urandom(grade_archive.MIN_BYTES + 1)
    (evaluation / "subset-repeat-x.json").write_bytes(moved)
    result = grade_archive.archive_tree(
        evaluation, grade_archive.DirectoryStore(store_root)
    )
    assert result["moved"] == 1
    for name, raw in kept.items():
        assert (evaluation / name).read_bytes() == raw
    assert not (evaluation / "subset-repeat-x.json").exists()
