"""DATA (sre 21 Nov 2026: inference snapshot predictions.json was 90.6% of the door's owner-ledger growth): a retained file
may be held COMPRESSED (``<name>.gz`` + its RAW note); every reader gets the RAW bytes through `read_raw`, checked against
the note, and accepts the raw file written before; a retained copy of a compressed source is the same compressed pair
(hard links, one inode), never a raw copy.
"""

from __future__ import annotations

import gzip
import json
import os

import pytest

from carbon.development_session import data

RAW = json.dumps([[0.1234567891234 * i, -2.5e-7 * i] for i in range(4000)]).encode()
posix = pytest.mark.skipif(
    not hasattr(os, "getuid"), reason="hard links need POSIX owners"
)


def _held(tmp_path, name="predictions.json", body=RAW):
    path = tmp_path / name
    path.write_bytes(body)
    return path


def test_a_compressed_file_reads_back_its_raw_bytes_and_the_raw_name_goes(tmp_path):
    path = _held(tmp_path)
    assert data.raw_exists(path) and data.raw_size(path) == len(RAW)
    assert data.compress_raw(path) is True
    assert not path.exists()
    assert (tmp_path / "predictions.json.gz").is_file()
    note = json.loads((tmp_path / "predictions.json.gz.raw.json").read_bytes())
    assert note["schema"] == data.RAW_NOTE_SCHEMA and note["size"] == len(RAW)
    assert data.read_raw(path) == RAW
    assert data.raw_exists(path) and data.raw_size(path) == len(RAW)
    assert (tmp_path / "predictions.json.gz").stat().st_size < len(RAW) / 2
    assert data.compress_raw(path) is False  # already held compressed


def test_the_archive_is_deterministic_for_the_same_bytes(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a, b = _held(tmp_path / "a"), _held(tmp_path / "b")
    data.compress_raw(a)
    data.compress_raw(b)
    assert (tmp_path / "a" / "predictions.json.gz").read_bytes() == (
        tmp_path / "b" / "predictions.json.gz"
    ).read_bytes()


def test_an_uncompressed_file_still_reads_as_before(tmp_path):
    path = _held(tmp_path)
    assert data.read_raw(path) == RAW
    with pytest.raises(FileNotFoundError):
        data.read_raw(tmp_path / "absent.json")
    with pytest.raises(FileNotFoundError):
        data.raw_size(tmp_path / "absent.json")
    assert data.raw_exists(tmp_path / "absent.json") is False


@pytest.mark.parametrize("tamper", ["archive", "note_sha", "note_size", "note_shape"])
def test_a_tampered_pair_refuses(tmp_path, tamper):
    path = _held(tmp_path)
    data.compress_raw(path)
    archive = tmp_path / "predictions.json.gz"
    note = tmp_path / "predictions.json.gz.raw.json"
    value = json.loads(note.read_bytes())
    if tamper == "archive":
        archive.chmod(0o600)
        archive.write_bytes(gzip.compress(RAW + b" ", mtime=0))
    else:
        note.chmod(0o600)
        if tamper == "note_sha":
            value["sha256"] = "0" * 64
        elif tamper == "note_size":
            value["size"] += 1
        else:
            value["extra"] = 1
        note.write_bytes(json.dumps(value).encode())
    with pytest.raises(ValueError, match="retained snapshot file differs"):
        data.read_raw(path)


def test_the_raw_bound_refuses_before_reading(tmp_path):
    path = _held(tmp_path)
    with pytest.raises(ValueError, match="oversized"):
        data.read_raw(path, max_bytes=10)
    data.compress_raw(path)
    with pytest.raises(ValueError, match="oversized"):
        data.read_raw(path, max_bytes=10)


@posix
def test_a_retained_copy_of_a_compressed_source_is_the_same_pair(tmp_path):
    (tmp_path / "op").mkdir()
    (tmp_path / "task").mkdir()
    source = _held(tmp_path / "op")
    data.compress_raw(source)
    target = tmp_path / "task" / "predictions.json"
    assert data.link_once(source, target, RAW) is True
    assert not target.exists()  # never a raw copy
    for suffix in (".gz", ".gz.raw.json"):
        a = os.stat(tmp_path / "op" / ("predictions.json" + suffix))
        b = os.stat(tmp_path / "task" / ("predictions.json" + suffix))
        assert (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)
    assert data.read_raw(target) == RAW
    # the same bytes again: nothing to do; other bytes: the immutable conflict as before
    assert data.link_once(source, target, RAW) is False
    with pytest.raises(ValueError, match="immutable"):
        data.link_once(source, target, RAW + b"x")


@posix
def test_a_compressed_source_with_other_bytes_is_never_linked(tmp_path):
    (tmp_path / "op").mkdir()
    (tmp_path / "task").mkdir()
    source = _held(tmp_path / "op", body=RAW + b" ")
    data.compress_raw(source)
    target = tmp_path / "task" / "predictions.json"
    assert data.link_once(source, target, RAW) is False
    assert (
        data.read_raw(target) == RAW
    )  # written, then stored compressed like its source
    assert not os.path.samefile(
        tmp_path / "op" / "predictions.json.gz",
        tmp_path / "task" / "predictions.json.gz",
    )


# --- the readers on the door path read a compressed snapshot exactly as a raw one ------------------------------------


def _decoded(tmp_path):
    from test_grade_storage_once import MEMBERS, _stream

    from carbon.reconstruction.worker.protocol import decode_output_stream

    source, body = _stream(tmp_path, MEMBERS)
    snapshot = source.parent / "snapshot"
    decode_output_stream(source, snapshot)
    return source, body, snapshot


@posix
def test_the_stream_rebuilds_byte_for_byte_from_a_compressed_snapshot(tmp_path):
    from carbon.development_session.research_carrier import (
        OUTPUT_FRAMES,
        compact_output_stream,
        reassembled_output_stream,
    )
    from carbon.reconstruction.worker.model import WorkerFailure

    source, body, snapshot = _decoded(tmp_path)
    assert compact_output_stream(source, snapshot) is True
    assert data.compress_raw(snapshot / "predictions.json") is True
    frames = source.parent / OUTPUT_FRAMES
    assert b"".join(reassembled_output_stream(frames, snapshot)) == body
    archive = snapshot / "predictions.json.gz"
    archive.chmod(0o600)
    archive.write_bytes(gzip.compress(b"[[9.0]]\n", mtime=0))
    with pytest.raises(WorkerFailure):
        b"".join(reassembled_output_stream(frames, snapshot))


@posix
def test_retention_reads_a_compressed_snapshot_and_a_retained_pair(tmp_path):
    import hashlib

    from carbon.challenge_validator import lean_recipe_retention as retention

    _source, _body, snapshot = _decoded(tmp_path)
    raw = (snapshot / "predictions.json").read_bytes()
    data.compress_raw(snapshot / "predictions.json")
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    assert (
        retention._snapshot(
            snapshot / "predictions.json",
            limit=16 * 1024**2,
            digest=digest,
            label="graded",
        )
        == raw
    )
    with pytest.raises(retention.RetentionUnavailable, match="graded_changed"):
        retention._snapshot(
            snapshot / "predictions.json",
            limit=16 * 1024**2,
            digest="0" * 64,
            label="graded",
        )
    task = tmp_path / "task"
    task.mkdir()
    assert data.link_once(snapshot / "predictions.json", task / "predictions.json", raw)
    assert (
        retention._private_measurement_bytes(task / "predictions.json", 16 * 1024**2)
        == raw
    )
    with pytest.raises(retention.RetentionUnavailable):
        retention._private_measurement_bytes(task / "predictions.json", 10)


@posix
def test_a_success_read_takes_the_raw_bytes_of_a_compressed_graded_snapshot(tmp_path):
    from types import SimpleNamespace

    from carbon.development_session.research_tasks import DirectDevelopmentTasksV3

    operation = "operation-" + "a" * 64
    snapshot = tmp_path / operation / "snapshot"
    snapshot.mkdir(parents=True)
    (snapshot / "predictions.json").write_bytes(RAW)
    data.compress_raw(snapshot / "predictions.json")
    provider = SimpleNamespace(ledger=SimpleNamespace(root=tmp_path))
    assert (
        DirectDevelopmentTasksV3._graded_snapshot_predictions(
            provider, {"inference_operation": operation}
        )
        == RAW
    )


@posix
def test_custody_counts_a_compressed_pair_as_its_one_declared_name(tmp_path):
    import hashlib
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "public_unbound_custody",
        root / "scripts/dev/score_lab/public_unbound_custody.py",
    )
    custody = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(custody)
    folder = tmp_path / "task"
    folder.mkdir()
    (folder / "predictions.json").write_bytes(RAW)
    (folder / "receipt.json").write_bytes(b'{"ok": true}')
    data.compress_raw(folder / "predictions.json")
    files = {
        "predictions.json": "sha256:" + hashlib.sha256(RAW).hexdigest(),
        "receipt.json": "sha256:" + hashlib.sha256(b'{"ok": true}').hexdigest(),
    }
    observed, raw = custody._graph_rehash_inventory(
        folder, files, frozenset({"predictions.json"}), lineage_name=None
    )
    assert raw["predictions.json"] == RAW
    assert observed["predictions.json"]["bytes"] == len(RAW)
    (folder / "stray.json").write_bytes(b"{}")
    with pytest.raises(custody.CustodyRefused, match="undeclared_or_missing"):
        custody._graph_rehash_inventory(
            folder, files, frozenset({"predictions.json"}), lineage_name=None
        )


@posix
def test_a_pre_apply_raw_folder_and_a_post_apply_compressed_one_read_the_same_bytes_and_digests(
    tmp_path,
):
    """V2 21 Nov 2026 (FINAL condition 2): the regrade's retained-folder read, the crown / graded snapshot read and the
    custody inventory give IDENTICAL raw bytes and digests over a snapshot written before the apply (raw) and after it
    (compressed)."""
    import hashlib
    import importlib.util
    from pathlib import Path

    from carbon.challenge_validator import lean_recipe_retention as retention

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "public_unbound_custody",
        root / "scripts/dev/score_lab/public_unbound_custody.py",
    )
    custody = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(custody)
    digest = "sha256:" + hashlib.sha256(RAW).hexdigest()
    results = []
    for name, compress in (("pre", False), ("post", True)):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "predictions.json").write_bytes(RAW)
        (folder / "receipt.json").write_bytes(b'{"ok": true}')
        if compress:
            data.compress_raw(folder / "predictions.json")
            assert not (folder / "predictions.json").exists()
        regrade = retention._private_measurement_bytes(
            folder / "predictions.json", 16 * 1024**2
        )
        graded = retention._snapshot(
            folder / "predictions.json",
            limit=16 * 1024**2,
            digest=digest,
            label="graded",
        )
        files = {
            "predictions.json": digest,
            "receipt.json": "sha256:" + hashlib.sha256(b'{"ok": true}').hexdigest(),
        }
        observed, raw = custody._graph_rehash_inventory(
            folder, files, frozenset({"predictions.json"}), lineage_name=None
        )
        results.append((regrade, graded, observed, raw["predictions.json"]))
    assert results[0] == results[1]
    assert results[0][0] == RAW
