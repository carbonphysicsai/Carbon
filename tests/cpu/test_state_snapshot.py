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


# --- the LIVE (zero-drain) snapshot, for a never-live copy -------------------------------------------------------


def test_a_live_snapshot_of_an_idle_door_keeps_everything_and_is_marked_never_live(
    state, tmp_path
):
    out = tmp_path / "snap"
    result = state_snapshot.take_live(state, out)
    assert result["state"] == "SNAPSHOT_TAKEN_LIVE"
    assert result["mode"] == "live" and result["never_live"] is True
    assert result["in_flight"] == {"work_inflight": None, "rows": {}}
    assert result["moving"] == [] and result["vanished"] == []
    records = _manifest(out)
    assert records["owners/abc/ledger/campaign.sqlite3"]["method"] == "sqlite_backup"
    assert records["door-binding.json"]["method"] == "hardlink"
    assert records["manifest-migrations.jsonl"]["method"] == "copy"
    db = sqlite3.connect(out / "owners/abc/ledger/campaign.sqlite3")
    assert db.execute("SELECT COUNT(*) FROM t").fetchone() == (50,)
    db.close()


def test_a_database_written_during_a_live_snapshot_is_kept_at_one_consistent_point(
    state, tmp_path, monkeypatch
):
    """The idle snapshot refuses `sqlite_moved_during_snapshot`; the live one keeps the backup's own state."""
    path = state / "owners/abc/ledger/campaign.sqlite3"
    real = state_snapshot._sqlite_backup

    def backup_then_live_writes(source, target):
        real(source, target)
        db = sqlite3.connect(path)
        db.execute("INSERT INTO t VALUES (999)")
        db.commit()
        db.close()

    monkeypatch.setattr(state_snapshot, "_sqlite_backup", backup_then_live_writes)
    with pytest.raises(SnapshotRefused, match="sqlite_moved_during_snapshot"):
        take(state, tmp_path / "idle")
    out = tmp_path / "snap"
    state_snapshot.take_live(state, out)
    db = sqlite3.connect(out / "owners/abc/ledger/campaign.sqlite3")
    assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert db.execute("SELECT COUNT(*) FROM t").fetchone()[0] in (50, 51)
    db.close()


def test_a_log_still_growing_keeps_its_complete_line_prefix(
    state, tmp_path, monkeypatch
):
    log = state / "manifest-migrations.jsonl"
    real = state_snapshot.shutil.copy2

    def copy_then_append(source, target, **kwargs):
        out = real(source, target, **kwargs)
        if str(source) == str(log):
            with open(log, "a") as f:
                f.write('{"n": "partial')  # a writer mid-line
        return out

    monkeypatch.setattr(state_snapshot.shutil, "copy2", copy_then_append)
    out = tmp_path / "snap"
    result = state_snapshot.take_live(state, out)
    kept = (out / "manifest-migrations.jsonl").read_bytes()
    assert kept.endswith(b"\n") and log.read_bytes().startswith(kept)
    assert _manifest(out)["manifest-migrations.jsonl"]["method"] == "copy_prefix"
    assert result["moving"] == []


def test_a_file_that_keeps_changing_is_listed_moving_and_a_vanished_one_is_listed_not_kept(
    state, tmp_path, monkeypatch
):
    workspace = state / "owners/abc/workspace.json"
    marker = state / "auto-grade/markers/rtsk_1.json"
    real = state_snapshot.shutil.copy2
    edits = iter(range(100))

    def copy(source, target, **kwargs):
        if str(source) == str(marker):
            raise FileNotFoundError(2, "gone", str(source))
        out = real(source, target, **kwargs)
        if str(source) == str(workspace):
            workspace.write_text(f'{{"doc": {next(edits)}}}')
        return out

    monkeypatch.setattr(state_snapshot.shutil, "copy2", copy)
    out = tmp_path / "snap"
    result = state_snapshot.take_live(state, out)
    assert result["moving"] == ["owners/abc/workspace.json"]
    assert result["vanished"] == ["auto-grade/markers/rtsk_1.json"]
    assert not (out / "auto-grade/markers/rtsk_1.json").exists()
    assert "auto-grade/markers/rtsk_1.json" not in _manifest(out)


def test_work_in_flight_is_listed_for_the_copy_to_settle(state, tmp_path):
    (state / "work-inflight.json").write_text('{"kind": "grade", "pid": 7}')
    db = sqlite3.connect(state / "owners/abc/ledger/ops.sqlite3")
    db.execute("CREATE TABLE operations (identity TEXT, state TEXT)")
    db.executemany(
        "INSERT INTO operations VALUES (?, ?)",
        [("a", "RESERVED"), ("b", "SUCCEEDED"), ("c", "RESERVED"), ("d", "RUNNING")],
    )
    db.commit()
    db.close()
    result = state_snapshot.take_live(state, tmp_path / "snap")
    assert result["in_flight"] == {
        "work_inflight": {"kind": "grade", "pid": 7},
        "rows": {
            "owners/abc/ledger/ops.sqlite3": {
                "operations": {"RESERVED": 2, "RUNNING": 1}
            }
        },
    }


def test_a_live_snapshot_writes_no_content_file_of_the_state(state, tmp_path):
    def listing():
        return {
            p.relative_to(state).as_posix(): p.read_bytes()
            for p in state.rglob("*")
            if p.is_file() and not p.name.endswith(("-shm", "-wal"))
        }

    before = listing()
    state_snapshot.take_live(state, tmp_path / "snap")
    assert listing() == before


def test_the_live_cli_says_live(state, tmp_path, capsys):
    assert (
        state_snapshot.main(["take", "--live", str(state), str(tmp_path / "snap")]) == 0
    )
    assert json.loads(capsys.readouterr().out)["state"] == "SNAPSHOT_TAKEN_LIVE"


def _live_door_with_work_in_flight(root):
    """A door state with one owner whose ledger holds a RESERVED worker op (live's grade in flight) and a settled one."""
    from carbon.development_session.research_ledger import CampaignLedger

    hotkey = "5F" + "a" * 46
    owner_dir = root / "receiver" / ("b" * 64)
    owner_dir.mkdir(parents=True, mode=0o700)
    (owner_dir / "owner.json").write_text(json.dumps({"hotkey": hotkey}))
    ledger = CampaignLedger(owner_dir / "ledger")
    reservation = json.dumps({"numerical_milliseconds": 648000, "provider_attempts": 1})
    with ledger.db() as db:
        db.executemany(
            "INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    "op-live",
                    hotkey,
                    "evaluation",
                    "d1",
                    "RESERVED",
                    reservation,
                    None,
                    None,
                    1.0,
                ),
                (
                    "op-done",
                    hotkey,
                    "evaluation",
                    "d2",
                    "SUCCEEDED",
                    reservation,
                    reservation,
                    "{}",
                    1.0,
                ),
            ],
        )
    (root / "work-inflight.json").write_text('{"kind": "grade", "pid": 7}')
    # live's open grade session (its reaper and container are live's)
    (owner_dir / "ledger/session-live").mkdir(mode=0o700)
    (owner_dir / "ledger/session-live/intent.json").write_text("{}")
    return hotkey, owner_dir


@pytest.mark.skipif(os.name != "posix", reason="the ledger lease uses fcntl.flock")
def test_a_copy_settles_live_in_flight_work_offline_and_never_touches_a_worker(
    state, tmp_path, monkeypatch
):
    """The copy's first start must not reconcile live's worker (its container is live's, on live's lanes)."""
    from carbon.development_session import research_carrier
    from carbon.development_session.research_ledger import CampaignLedger

    hotkey, owner_dir = _live_door_with_work_in_flight(state)
    out = tmp_path / "snap"
    taken = state_snapshot.take_live(state, out)
    rel = owner_dir.relative_to(state).as_posix() + "/ledger/campaign.sqlite3"
    assert taken["in_flight"]["rows"][rel] == {"operations": {"RESERVED": 1}}
    assert taken["in_flight"]["work_inflight"] == {"kind": "grade", "pid": 7}

    with pytest.raises(SnapshotRefused, match="not_a_live_snapshot"):
        state_snapshot.settle_copy(state)  # the live state itself: no live manifest
    result = state_snapshot.settle_copy(out)
    assert result["state"] == "COPY_SETTLED" and result["work_inflight_removed"]
    assert [s["operation"] for s in result["settled"]] == ["op-live"]
    assert not (out / "work-inflight.json").exists()

    copy = CampaignLedger(out / owner_dir.relative_to(state) / "ledger")
    assert copy.operation_state("op-live", owner=hotkey) == "FAILED_INFRA"
    assert copy.operation_state("op-done", owner=hotkey) == "SUCCEEDED"
    with copy.db() as db:
        actual, body = db.execute(
            "SELECT actual, result FROM operations WHERE id='op-live'"
        ).fetchone()
    assert json.loads(actual) == {
        "numerical_milliseconds": 648000,
        "provider_attempts": 1,
    }
    assert json.loads(body)["cleanup_observed"] is False
    # the door's restore path on the copy now never reaches a container or a lane
    monkeypatch.setattr(
        research_carrier,
        "remove_exact_container",
        lambda **_: pytest.fail("the copy touched a worker"),
    )
    research_carrier.reconcile_worker(copy, owner=hotkey, identity="op-live")
    # live is untouched: its op is still RESERVED and its in-flight record still there
    live = CampaignLedger(owner_dir / "ledger")
    assert live.operation_state("op-live", owner=hotkey) == "RESERVED"
    assert (state / "work-inflight.json").exists()
    # once only: by now the copy's own door may hold RESERVED operations of its own
    with pytest.raises(SnapshotRefused, match="already_settled"):
        state_snapshot.settle_copy(out)
    assert json.loads(body)["schema"] == "carbon.autoresearch.worker-reconciliation.v1"
    assert result["sessions_removed"] == [
        owner_dir.relative_to(state).as_posix() + "/ledger/session-live"
    ]
    assert not (out / owner_dir.relative_to(state) / "ledger/session-live").exists()
    assert (owner_dir / "ledger/session-live/intent.json").exists()


def test_settle_refuses_an_idle_snapshot(state, tmp_path):
    out = tmp_path / "snap"
    take(state, out)
    with pytest.raises(SnapshotRefused, match="not_a_live_snapshot"):
        state_snapshot.settle_copy(out)


def test_owner_ledgers_are_backed_up_after_every_other_database(
    state, tmp_path, monkeypatch
):
    """A task store is never newer than the operations it names (review should-fix 3)."""
    tasks = state / "owners/abc/tasks"
    tasks.mkdir(mode=0o700)
    db = sqlite3.connect(tasks / "direct-tasks.sqlite3")
    db.execute("CREATE TABLE v (x)")
    db.commit()
    db.close()
    order = []
    real = state_snapshot._sqlite_backup
    monkeypatch.setattr(
        state_snapshot,
        "_sqlite_backup",
        lambda s, t: (order.append(s.name), real(s, t)),
    )
    state_snapshot.take_live(state, tmp_path / "snap")
    assert order[-1] == "campaign.sqlite3" and "direct-tasks.sqlite3" in order[:-1]


def test_a_copy_at_lives_own_path_name_on_another_host_is_not_refused_as_live(
    state, tmp_path
):
    """The guard compares the directory itself, not the path string (review should-fix 4)."""
    out = tmp_path / "snap"
    state_snapshot.take_live(state, out)
    manifest = json.loads((out / "snapshot.json").read_text())
    manifest["state_dir"] = str(
        tmp_path / "elsewhere" / "state"
    )  # live's path, absent on this host
    (out / "snapshot.json").write_text(json.dumps(manifest))
    assert state_snapshot.settle_copy(out)["state"] == "COPY_SETTLED"
    manifest["state_dir"] = str(out)
    (out / "snapshot.json").write_text(json.dumps(manifest))
    (out / "copy-settled.json").unlink()
    with pytest.raises(SnapshotRefused, match="copy_is_the_live_state"):
        state_snapshot.settle_copy(out)
