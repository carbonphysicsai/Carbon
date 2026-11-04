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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="state_snapshot.py")
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("take")
    t.add_argument("state_dir", type=Path)
    t.add_argument("out_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        result = take(args.state_dir, args.out_dir)
    except SnapshotRefused as refusal:
        print(json.dumps({"state": "REFUSED", "code": refusal.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
