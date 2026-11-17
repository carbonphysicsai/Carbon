#!/usr/bin/env python3
"""Take a pre-release snapshot of one door's state directory (MAINNET_UPDATE_ARCHITECTURE s1.4).

    python3 -I -B scripts/dev/release/state_snapshot.py take STATE_DIR OUT_DIR

A safety net for a one-way release step, not part of the normal deploy path (a release never copies state). Take it
while the door is DRAINING and idle (no grade or construction running), so no non-sqlite file is mid-write.

How each file is kept (Validator H0 must-fix (a)):
- every sqlite database (by its header): through sqlite's online backup API, consistent while the receiver runs;
- a HARD LINK only for files this code base writes once and never edits in place (`HARDLINK_CLASSES`, each with the
  writer that proves it). A hard link to a file edited or appended in place would change inside the snapshot too;
- everything else is COPIED (jsonl logs, `manifest-migrations.jsonl`, operator files, anything not proven).
  Unknown means copy.

``OUT_DIR`` must not exist; it is created owner-only. ``OUT_DIR/snapshot.json`` lists every file with its sha256,
mode and method, and the snapshot is verified against the source before the tool says SNAPSHOT_TAKEN. Symlinks,
devices and sockets refuse. No content file in STATE_DIR is written. The one exception is sqlite's own lock side file:
reading a WAL-mode database may create its ``-shm`` (sqlite's shared-memory index), exactly as any reader does.

    python3 -I -B scripts/dev/release/state_snapshot.py take --live STATE_DIR OUT_DIR

A LIVE snapshot (zero drain; Live ops' rehearsal-host finding, 17 Nov 2026) is taken while the door serves, for a
never-live COPY only (a rehearsal), never as a release safety net. Nothing in STATE_DIR is written, as above. Where the
idle snapshot refuses because live moved, the live one keeps a consistent earlier state instead:
- every sqlite database FIRST, each through the online backup API (one consistent point per database), and not
  compared with the live database afterwards (it is expected to have moved on);
- then a FRESH walk for every other file, so a write-once file a database row already names is present;
- a file still changing after `LIVE_RETRIES` copies: a `.jsonl` (append-only) keeps its complete-line prefix, which is
  an earlier state of the same log; any other is kept as last read and listed under ``moving``;
- a file that vanished is listed under ``vanished``, not kept.
The manifest says ``mode: live`` and ``never_live: true`` and lists the work that was in flight (``in_flight``: this
door's ``work-inflight.json`` and, per database, the rows in a RESERVED/RUNNING/CANCEL_REQUESTED state). A copy started
from it must have that work settled offline FIRST: on start, the door's restore reconciles every interrupted worker
by its identity, and the copy's lanes are live's.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import sys
from pathlib import Path

SCHEMA = "carbon.release.state-snapshot.v1"
SQLITE_HEADER = b"SQLite format 3\x00"
#: Relative-path patterns proven write-once (created exclusively, never edited in place), each with its writer.
HARDLINK_CLASSES = (
    # direct_receiver serve() via state_binding.bind / data.write_once: link-into-place, never replaced.
    ("receiver-binding.json", "data.write_once"),
    ("door-binding.json", "data.write_once"),
    ("bindings/*.json", "data.write_once"),
    ("evaluation-pack-selection.json", "data.write_once"),
    # direct_receiver._sealed_pack: write_once(pack_root / <digest>.json, sealed bytes).
    ("evaluation-packs/*.json", "data.write_once"),
    # ReceiverSnapshotWindow._record: a new file each time, put in place by os.replace (never edited in place).
    ("snapshot-high-water.json", "os.replace"),
)
# Not listed on purpose: auto-grade markers are created (O_EXCL) and THEN written, so a link taken mid-write would
# carry a stale digest; they are copied and checked.
#: sqlite's own side files: never copied (the backup API reads the database through sqlite, WAL included).
SQLITE_SIDE = ("-wal", "-shm", "-journal")


class SnapshotRefused(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _is_sqlite(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(len(SQLITE_HEADER)) == SQLITE_HEADER


def method_for(relative: str, path: Path) -> str:
    if _is_sqlite(path):
        return "sqlite_backup"
    directory, _, name = relative.rpartition("/")
    for pattern, _writer in HARDLINK_CLASSES:
        pattern_dir, _, pattern_name = pattern.rpartition("/")
        if directory == pattern_dir and fnmatch.fnmatchcase(name, pattern_name):
            return "hardlink"
    return "copy"


def _sqlite_backup(source: Path, target: Path) -> None:
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _sqlite_digest(path: Path) -> str:
    """The database's logical content (its SQL dump), so a backup is checked on what it holds, not on page bytes."""
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        h = hashlib.sha256()
        for line in db.iterdump():
            h.update(line.encode("utf-8") + b"\n")
        return h.hexdigest()
    finally:
        db.close()


def take(state_dir: Path, out_dir: Path) -> dict:
    state_dir, out_dir = Path(state_dir), Path(out_dir)
    if not state_dir.is_absolute() or state_dir.is_symlink() or not state_dir.is_dir():
        raise SnapshotRefused("state_dir_invalid")
    if not out_dir.is_absolute() or out_dir.exists() or out_dir.is_symlink():
        raise SnapshotRefused("out_dir_must_be_new")
    if state_dir == out_dir or state_dir in out_dir.parents:
        raise SnapshotRefused("out_dir_inside_state")
    # Refuse before writing anything: links, devices, sockets, fifos.
    entries = []
    for root, dirs, files in os.walk(state_dir):
        for name in dirs + files:
            path = Path(root) / name
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode):
                raise SnapshotRefused(f"link_refused:{path.relative_to(state_dir)}")
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise SnapshotRefused(f"special_file:{path.relative_to(state_dir)}")
            entries.append((path, info))
    out_dir.mkdir(mode=0o700)
    try:
        return _take(state_dir, out_dir, entries)
    except FileNotFoundError as gone:
        # A file vanished between the walk and its copy: the door was not idle. OUT_DIR is left for inspection and
        # is never a valid snapshot (it has no snapshot.json).
        raise SnapshotRefused(
            f"file_vanished_during_snapshot:{Path(gone.filename or '').name}"
        ) from None


def _take(state_dir: Path, out_dir: Path, entries) -> dict:
    records = []
    directory_modes = []
    for path, info in sorted(entries, key=lambda e: str(e[0])):
        relative = path.relative_to(state_dir).as_posix()
        target = out_dir / relative
        if stat.S_ISDIR(info.st_mode):
            target.mkdir(mode=0o700, parents=True, exist_ok=True)
            directory_modes.append((target, stat.S_IMODE(info.st_mode)))
            records.append(
                {"path": relative, "kind": "dir", "mode": stat.S_IMODE(info.st_mode)}
            )
            continue
        if path.name.startswith("."):
            # A writer's staging file (write_once / os.replace temp names): never state, and it may vanish any time.
            records.append({"path": relative, "kind": "staging", "kept": False})
            continue
        if relative.endswith(SQLITE_SIDE):
            records.append({"path": relative, "kind": "sqlite_side", "kept": False})
            continue
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        method = method_for(relative, path)
        if method == "sqlite_backup":
            _sqlite_backup(path, target)
            os.chmod(target, stat.S_IMODE(info.st_mode))
            content = _sqlite_digest(target)
            if content != _sqlite_digest(path):
                # The database changed during the backup: the door was not idle.
                raise SnapshotRefused(f"sqlite_moved_during_snapshot:{relative}")
        elif method == "hardlink":
            try:
                os.link(path, target)
            except OSError:
                # Another filesystem (or no link support): a copy is always safe.
                method = "copy"
                shutil.copy2(path, target, follow_symlinks=False)
            content = _sha256(target)
        else:
            shutil.copy2(path, target, follow_symlinks=False)
            content = _sha256(target)
            if content != _sha256(path):
                raise SnapshotRefused(f"file_moved_during_snapshot:{relative}")
        records.append(
            {
                "path": relative,
                "kind": "file",
                "method": method,
                "mode": stat.S_IMODE(info.st_mode),
                "sha256": content,
            }
        )
    # Directory modes last (deepest first), so a read-only source directory never blocks writing its children.
    for target, mode in sorted(directory_modes, key=lambda d: -len(d[0].parts)):
        os.chmod(target, mode)
    files = [r for r in records if r["kind"] == "file"]
    result = {
        "schema": SCHEMA,
        "state": "SNAPSHOT_TAKEN",
        "state_dir": str(state_dir),
        "files": len(files),
        "by_method": {
            m: sum(1 for r in files if r["method"] == m)
            for m in ("sqlite_backup", "hardlink", "copy")
        },
        "sqlite_side_skipped": sum(1 for r in records if r["kind"] == "sqlite_side"),
        "staging_skipped": sum(1 for r in records if r["kind"] == "staging"),
        "records": records,
    }
    manifest = out_dir / "snapshot.json"
    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(result, f, sort_keys=True, indent=1)
        f.write("\n")
    return {k: v for k, v in result.items() if k != "records"}


LIVE_SCHEMA = "carbon.release.state-snapshot.live.v1"
#: Copies of a file that keeps changing before the live snapshot keeps what it read (see the module docstring).
LIVE_RETRIES = 3
#: Row states that mean work in flight, reported per database table (any table with a ``state`` column).
IN_FLIGHT_STATES = ("RESERVED", "RUNNING", "CANCEL_REQUESTED")
INFLIGHT_NAME = "work-inflight.json"


def _walk(state_dir: Path):
    """Every entry under STATE_DIR (dirs and regular files); links and special files refuse."""
    entries = []
    for root, dirs, files in os.walk(state_dir):
        for name in dirs + files:
            path = Path(root) / name
            try:
                info = os.lstat(path)
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode):
                raise SnapshotRefused(f"link_refused:{path.relative_to(state_dir)}")
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise SnapshotRefused(f"special_file:{path.relative_to(state_dir)}")
            entries.append((path, info))
    return sorted(entries, key=lambda e: str(e[0]))


def _in_flight_rows(database: Path) -> dict:
    """{table: {state: count}} for the in-flight states, in a database backup (read-only)."""
    db = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        found = {}
        tables = [
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            columns = {row[1] for row in db.execute(f"PRAGMA table_info({quoted})")}
            if "state" not in columns:
                continue
            marks = ",".join("?" for _ in IN_FLIGHT_STATES)
            counts = dict(
                db.execute(
                    f"SELECT state, COUNT(*) FROM {quoted} WHERE state IN ({marks}) "
                    "GROUP BY state ORDER BY state",
                    IN_FLIGHT_STATES,
                ).fetchall()
            )
            if counts:
                found[table] = counts
        return found
    finally:
        db.close()


def _copy_settled(path: Path, target: Path, relative: str):
    """Copy a file that may be changing: (method, sha256 of what is kept, moving?)."""
    for _ in range(LIVE_RETRIES):
        shutil.copy2(path, target, follow_symlinks=False)
        kept = _sha256(target)
        if kept == _sha256(path):
            return "copy", kept, False
    if relative.endswith(".jsonl"):
        data = target.read_bytes()
        end = data.rfind(b"\n") + 1
        with open(target, "r+b") as f:
            f.truncate(end)
        return "copy_prefix", _sha256(target), False
    return "copy", _sha256(target), True


def take_live(state_dir: Path, out_dir: Path) -> dict:
    """A consistent earlier state of a door that keeps serving (module docstring); for a never-live copy only."""
    state_dir, out_dir = Path(state_dir), Path(out_dir)
    if not state_dir.is_absolute() or state_dir.is_symlink() or not state_dir.is_dir():
        raise SnapshotRefused("state_dir_invalid")
    if not out_dir.is_absolute() or out_dir.exists() or out_dir.is_symlink():
        raise SnapshotRefused("out_dir_must_be_new")
    if state_dir == out_dir or state_dir in out_dir.parents:
        raise SnapshotRefused("out_dir_inside_state")
    first = _walk(state_dir)
    out_dir.mkdir(mode=0o700)
    records, directory_modes = [], {}
    vanished, moving, in_flight_rows = [], [], {}
    taken = set()

    def directory(relative, info):
        target = out_dir / relative
        target.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory_modes[target] = stat.S_IMODE(info.st_mode)
        records.append(
            {"path": relative, "kind": "dir", "mode": stat.S_IMODE(info.st_mode)}
        )

    def skipped(relative, name):
        if name.startswith("."):
            records.append({"path": relative, "kind": "staging", "kept": False})
            return True
        if relative.endswith(SQLITE_SIDE):
            records.append({"path": relative, "kind": "sqlite_side", "kept": False})
            return True
        return False

    # 1. every database, each at one consistent point
    for path, info in first:
        relative = path.relative_to(state_dir).as_posix()
        if stat.S_ISDIR(info.st_mode) or skipped(relative, path.name):
            continue
        try:
            if not _is_sqlite(path):
                continue
            target = out_dir / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _sqlite_backup(path, target)
        except FileNotFoundError:
            vanished.append(relative)
            continue
        os.chmod(target, stat.S_IMODE(info.st_mode))
        rows = _in_flight_rows(target)
        if rows:
            in_flight_rows[relative] = rows
        taken.add(relative)
        records.append(
            {
                "path": relative,
                "kind": "file",
                "method": "sqlite_backup",
                "mode": stat.S_IMODE(info.st_mode),
                "sha256": _sqlite_digest(target),
            }
        )
    records = [
        r for r in records if r["kind"] == "file"
    ]  # side/staging re-listed below
    # 2. a fresh walk for everything else (a write-once file a database row names exists by now)
    for path, info in _walk(state_dir):
        relative = path.relative_to(state_dir).as_posix()
        if stat.S_ISDIR(info.st_mode):
            directory(relative, info)
            continue
        if relative in taken or skipped(relative, path.name):
            continue
        target = out_dir / relative
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            if _is_sqlite(path):
                # a database created after step 1
                _sqlite_backup(path, target)
                rows = _in_flight_rows(target)
                if rows:
                    in_flight_rows[relative] = rows
                method, content, moved = "sqlite_backup", _sqlite_digest(target), False
            elif method_for(relative, path) == "hardlink":
                try:
                    os.link(path, target)
                    method = "hardlink"
                except OSError:
                    method = "copy"
                    shutil.copy2(path, target, follow_symlinks=False)
                content, moved = _sha256(target), False
            else:
                method, content, moved = _copy_settled(path, target, relative)
        except FileNotFoundError:
            vanished.append(relative)
            target.unlink(missing_ok=True)
            continue
        os.chmod(target, stat.S_IMODE(info.st_mode))
        if moved:
            moving.append(relative)
        records.append(
            {
                "path": relative,
                "kind": "file",
                "method": method,
                "mode": stat.S_IMODE(info.st_mode),
                "sha256": content,
            }
        )
    for target, mode in sorted(directory_modes.items(), key=lambda d: -len(d[0].parts)):
        os.chmod(target, mode)
    inflight_record = None
    if (out_dir / INFLIGHT_NAME).is_file():
        try:
            inflight_record = json.loads((out_dir / INFLIGHT_NAME).read_bytes())
        except ValueError:
            inflight_record = "unreadable"
    files = [r for r in records if r["kind"] == "file"]
    result = {
        "schema": LIVE_SCHEMA,
        "state": "SNAPSHOT_TAKEN_LIVE",
        "mode": "live",
        "never_live": True,
        "state_dir": str(state_dir),
        "files": len(files),
        "by_method": {
            m: sum(1 for r in files if r["method"] == m)
            for m in ("sqlite_backup", "hardlink", "copy", "copy_prefix")
        },
        "sqlite_side_skipped": sum(1 for r in records if r["kind"] == "sqlite_side"),
        "staging_skipped": sum(1 for r in records if r["kind"] == "staging"),
        "in_flight": {"work_inflight": inflight_record, "rows": in_flight_rows},
        "moving": sorted(moving),
        "vanished": sorted(vanished),
        "records": sorted(records, key=lambda r: r["path"]),
    }
    manifest = out_dir / "snapshot.json"
    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(result, f, sort_keys=True, indent=1)
        f.write("\n")
    return {k: v for k, v in result.items() if k != "records"}


SETTLE_SCHEMA = "carbon.release.copy-settlement.v1"


def settle_copy(copy_dir: Path) -> dict:
    """Settle, OFFLINE, the work a live snapshot caught in flight, before the copy's door first starts.

    Why: at start the door restores every owner and reconciles each RESERVED worker operation by its exact container
    name (`research_carrier.reconcile_worker`: `remove_exact_container` on the lane the intent names, then
    `remote_lane.discard` of its input). On a copy those are LIVE's containers on live's shared lanes (Ryzen, A100), so
    a copy started unsettled would stop live's grades and builds. Here every RESERVED operation in the copy's owner
    ledgers is finished FAILED_INFRA through the ledger's own `CampaignLedger.finish` (full reservation kept, cleanup
    NOT observed, no retry dispatched), with no container, lane or network call. The door's start then ends each
    interrupted task FAILED_INFRA through its normal restore (no worker call: the operation is no longer RESERVED) and
    its own infrastructure retry requeues it on the copy, exactly as after a crash. ``work-inflight.json`` (live's
    process) is removed from the copy. Only a directory whose ``snapshot.json`` is a LIVE snapshot is touched; running
    it again changes nothing more.
    """
    copy_dir = Path(copy_dir)
    if not copy_dir.is_absolute() or copy_dir.is_symlink() or not copy_dir.is_dir():
        raise SnapshotRefused("copy_dir_invalid")
    try:
        manifest = json.loads((copy_dir / "snapshot.json").read_bytes())
    except (OSError, ValueError):
        raise SnapshotRefused("not_a_live_snapshot") from None
    if (
        type(manifest) is not dict
        or manifest.get("schema") != LIVE_SCHEMA
        or manifest.get("never_live") is not True
    ):
        raise SnapshotRefused("not_a_live_snapshot")
    if Path(manifest.get("state_dir", "")).resolve() == copy_dir.resolve():
        raise SnapshotRefused("copy_is_the_live_state")
    repository = str(Path(__file__).resolve().parents[3])
    if repository not in sys.path:
        sys.path.insert(0, repository)
    from carbon.development_session.research_ledger import CampaignLedger

    settled, deferred = [], []
    for owner_file in sorted(copy_dir.rglob("owner.json")):
        database = owner_file.parent / "ledger" / "campaign.sqlite3"
        if not database.is_file():
            continue
        owner = json.loads(owner_file.read_bytes())
        if type(owner) is not dict or type(owner.get("hotkey")) is not str:
            raise SnapshotRefused(
                f"owner_binding_invalid:{owner_file.relative_to(copy_dir)}"
            )
        ledger = CampaignLedger(owner_file.parent / "ledger")
        with ledger.db() as db:
            reserved = db.execute(
                "SELECT id, owner, reservation FROM operations WHERE state='RESERVED' "
                "AND id NOT IN (SELECT parent FROM operation_sequences) ORDER BY id"
            ).fetchall()
            parents = db.execute(
                "SELECT o.id, o.owner FROM operations o JOIN operation_sequences s ON s.parent=o.id "
                "WHERE o.state='RESERVED' ORDER BY o.id"
            ).fetchall()
            held = db.execute(
                "SELECT id FROM operations WHERE state='HELD' ORDER BY id"
            ).fetchall()
        where = owner_file.parent.relative_to(copy_dir).as_posix()
        for identity, op_owner, reservation in reserved:
            ledger.finish(
                identity,
                owner=op_owner,
                state="FAILED_INFRA",
                actual=json.loads(reservation),
                result={
                    "schema": SETTLE_SCHEMA,
                    "state": "FAILED_INFRA",
                    "cleanup_observed": False,
                    "accounting": "full original reservation retained as conservative consumption",
                    "scientific_outcome": "UNRESOLVED",
                    "retry_dispatched": False,
                    "cause": "in flight on LIVE at a live snapshot; its worker is live's and is never touched by the copy",
                },
            )
            settled.append({"owner_dir": where, "operation": identity})
        for parent, op_owner in parents:
            try:
                ledger.settle_sequence(parent, owner=op_owner)
                settled.append(
                    {"owner_dir": where, "operation": parent, "sequence": True}
                )
            except ValueError as refused:
                deferred.append(
                    {"owner_dir": where, "operation": parent, "why": str(refused)}
                )
        deferred.extend(
            {
                "owner_dir": where,
                "operation": row[0],
                "why": "HELD (never claimed; no worker)",
            }
            for row in held
        )
    inflight = copy_dir / INFLIGHT_NAME
    removed_inflight = inflight.is_file()
    if removed_inflight:
        inflight.unlink()
    return {
        "schema": SETTLE_SCHEMA,
        "state": "COPY_SETTLED",
        "copy_dir": str(copy_dir),
        "settled": settled,
        "deferred": deferred,
        "work_inflight_removed": removed_inflight,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="state_snapshot.py")
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("take")
    t.add_argument(
        "--live",
        action="store_true",
        help="zero drain, for a never-live copy only (module docstring)",
    )
    t.add_argument("state_dir", type=Path)
    t.add_argument("out_dir", type=Path)
    s = sub.add_parser(
        "settle-copy", help="settle a live snapshot's in-flight work, offline"
    )
    s.add_argument("copy_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "settle-copy":
            result = settle_copy(args.copy_dir)
        else:
            result = (take_live if args.live else take)(args.state_dir, args.out_dir)
    except SnapshotRefused as refusal:
        print(json.dumps({"state": "REFUSED", "code": refusal.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
