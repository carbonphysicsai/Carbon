"""The pre-release state snapshot (MAINNET_UPDATE_ARCHITECTURE s1.4; Validator H0 must-fix (a)).

A file appended or edited in place after the snapshot must leave the snapshot's copy unchanged; only proven
write-once files are hard-linked; sqlite goes through the backup API (WAL included)."""

from __future__ import annotations

import json
import os
import sqlite3

import pytest

from scripts.dev.release import state_snapshot
from scripts.dev.release.state_snapshot import SnapshotRefused, take


@pytest.fixture
def state(tmp_path):
    root = tmp_path / "state"
    for directory in ("owners/abc/ledger", "auto-grade/markers", "bindings", "logs"):
        (root / directory).mkdir(parents=True, mode=0o700)
    (root / "manifest-migrations.jsonl").write_text('{"n": 1}\n')
    (root / "owners/abc/workspace.json").write_text('{"doc": 1}')
    (root / "auto-grade/markers/rtsk_1.json").write_text('{"state": "GRADED"}')
    (root / "bindings/x.json").write_text("{}")
    (root / "door-binding.json").write_text("{}")
    (root / "logs/nested.json").write_text("{}")
    db = sqlite3.connect(root / "owners/abc/ledger/campaign.sqlite3")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE t (v INTEGER)")
    db.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(50)])
    db.commit()
    db.close()
    return root


def _manifest(out):
    return {
        r["path"]: r for r in json.loads((out / "snapshot.json").read_text())["records"]
    }


def test_an_append_in_place_after_the_snapshot_leaves_the_snapshot_unchanged(
    state, tmp_path
):
    out = tmp_path / "snap"
    take(state, out)
    with open(state / "manifest-migrations.jsonl", "a") as f:
        f.write('{"n": 2}\n')
    with open(state / "owners/abc/workspace.json", "r+") as f:
        f.write('{"doc": 9}')
    assert (out / "manifest-migrations.jsonl").read_text() == '{"n": 1}\n'
    assert (out / "owners/abc/workspace.json").read_text() == '{"doc": 1}'


def test_only_proven_write_once_files_are_hard_linked(state, tmp_path):
    out = tmp_path / "snap"
    result = take(state, out)
    records = _manifest(out)
    linked = {p for p, r in records.items() if r.get("method") == "hardlink"}
    assert linked == {"bindings/x.json", "door-binding.json"}
    assert records["auto-grade/markers/rtsk_1.json"]["method"] == "copy"
    for path in linked:
        assert os.stat(out / path).st_ino == os.stat(state / path).st_ino
    for path in (
        "manifest-migrations.jsonl",
        "owners/abc/workspace.json",
        "logs/nested.json",
    ):
        assert records[path]["method"] == "copy"
        assert os.stat(out / path).st_ino != os.stat(state / path).st_ino
    assert result["by_method"]["sqlite_backup"] == 1


def test_a_live_wal_database_is_backed_up_with_its_uncheckpointed_rows(state, tmp_path):
    writer = sqlite3.connect(state / "owners/abc/ledger/campaign.sqlite3")
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("INSERT INTO t VALUES (999)")
    writer.commit()  # the row is in the -wal file only
    try:
        out = tmp_path / "snap"
        result = take(state, out)
        copy = sqlite3.connect(out / "owners/abc/ledger/campaign.sqlite3")
        assert copy.execute("SELECT COUNT(*), MAX(v) FROM t").fetchone() == (51, 999)
        copy.close()
        assert result["sqlite_side_skipped"] >= 1
        assert not (out / "owners/abc/ledger/campaign.sqlite3-wal").exists()
    finally:
        writer.close()


def test_no_content_file_of_the_state_is_written(state, tmp_path):
    # sqlite's own lock side files (-shm/-wal) may appear when a WAL database is read; nothing else may change.
    def listing():
        return sorted(
            (p.relative_to(state).as_posix(), p.read_bytes() if p.is_file() else None)
            for p in state.rglob("*")
            if not p.name.endswith(state_snapshot.SQLITE_SIDE)
        )

    before = listing()
    take(state, tmp_path / "snap")
    assert listing() == before


@pytest.mark.parametrize("case", ["exists", "inside", "relative", "link"])
def test_refusals_write_nothing(state, tmp_path, case):
    out = tmp_path / "snap"
    if case == "exists":
        out.mkdir()
    elif case == "inside":
        out = state / "snap"
    elif case == "relative":
        out = state_snapshot.Path("snap")
    else:
        os.symlink(tmp_path, state / "a-link")
    with pytest.raises(SnapshotRefused):
        take(state, out)
    if case in ("inside", "link"):
        assert not out.exists()


def test_staging_files_are_skipped_and_a_vanishing_file_refuses(
    state, tmp_path, monkeypatch
):
    (state / "bindings/.x.json.abc123").write_text("half")
    result = take(state, tmp_path / "snap")
    assert result["staging_skipped"] == 1
    assert not (tmp_path / "snap/bindings/.x.json.abc123").exists()

    real_copy = state_snapshot.shutil.copy2

    def vanish(source, target, **kwargs):
        if str(source).endswith("manifest-migrations.jsonl"):
            os.unlink(source)
        return real_copy(source, target, **kwargs)

    monkeypatch.setattr(state_snapshot.shutil, "copy2", vanish)
    with pytest.raises(SnapshotRefused, match="file_vanished_during_snapshot"):
        take(state, tmp_path / "snap2")
    assert not (tmp_path / "snap2" / "snapshot.json").exists()


def test_a_read_only_directory_is_snapshotted_with_its_mode(state, tmp_path):
    os.chmod(state / "logs", 0o500)
    try:
        take(state, tmp_path / "snap")
        assert (tmp_path / "snap/logs/nested.json").read_text() == "{}"
        assert os.stat(tmp_path / "snap/logs").st_mode & 0o777 == 0o500
    finally:
        os.chmod(state / "logs", 0o700)
        os.chmod(tmp_path / "snap/logs", 0o700)
