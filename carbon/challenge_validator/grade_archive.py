"""Move old grade files off the host by digest, keeping a local stub (owner rule #13: storage).

A grade's retained folders (``auto-grade/artifacts/<task>/`` and ``<task>.evaluation/``) and, when asked, its
owner's settled ``operation-*`` folders hold files that are read again only by a later regrade or an operator. Once a
folder is older than an operator's chosen number of days, each of its files of at least `MIN_BYTES` is copied into a
content-addressed store (``<store>/<sha256[:2]>/<sha256>``, checked by re-reading), and a stub ``ARCHIVED.json`` in
the folder keeps every moved file's name, SHA-256, size and mode, and the store's path. Only then is the local name
removed. Small records (receipts, intents, framings) stay on the host. Nothing is changed in place: `restore_tree`
puts each file back with the same name, bytes (SHA-256 checked) and mode, then removes the stub, and a regrade
restores its origin before reading it (`lean_recipe_retention._regrade_origin`).

No default store and no default age: both are operator values (the store an off-host mount, e.g. a storage box
mounted on the host; the age an owner/sre choice). Run by an operator; dry run unless ``--apply``:

    python -I -m carbon.challenge_validator.grade_archive --state STATE --store DIR --older-than-days N [--operations]
    python -I -m carbon.challenge_validator.grade_archive --restore FOLDER

``--compact-streams`` (dry run unless ``--apply``; ``--list FILE`` writes the candidates as TSV for a receipt) does
once, for the SUCCEEDED operations already on the host, what every new
operation now does itself (`research_carrier.compact_output_stream`): a decoded ``export.stream`` older than an hour is kept as
its framing only, after its framing and snapshot are shown to rebuild it byte for byte.

    python -I -m carbon.challenge_validator.grade_archive --state STATE --compact-streams [--apply]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import time
from pathlib import Path

SCHEMA = "carbon.grade-archive.stub.v1"
STUB = "ARCHIVED.json"
#: files smaller than this stay on the host (receipts, intents, framings, markers)
MIN_BYTES = 64 * 1024
_HEX = re.compile(r"[0-9a-f]{64}")
#: a grade's own aggregate records stay on the host at any size: its breakdown (`grade_breakdown.SUFFIX`), its gate
#: failures, its total SE and accuracy record (data harvest plan action 1: the breakdown survives every trim)
KEPT_LOCAL_SUFFIXES = (
    ".grade-breakdown.json",
    ".grade-breakdown.recomputed.json",
)
KEPT_LOCAL_PARTS = ("gate-failures", "gate_failures")


def kept_local(name):
    """True for a file the archive never moves (`KEPT_LOCAL_SUFFIXES`, `KEPT_LOCAL_PARTS`, and the exam's two custody
    sidecars by the names their writer owns, `exam_rotation`; never opened here: only kept where they are).
    """
    from carbon.challenge_validator.exam_rotation import (
        ACCURACY_SIDECAR,
        CASE_ERRORS_SIDECAR,
        SE_SIDECAR,
    )

    return (
        name.endswith(KEPT_LOCAL_SUFFIXES)
        or name in (SE_SIDECAR, ACCURACY_SIDECAR, CASE_ERRORS_SIDECAR)
        or any(part in name for part in KEPT_LOCAL_PARTS)
    )


class ArchiveRefused(RuntimeError):
    """A folder that cannot be archived or restored as asked; nothing was removed."""


def _sha256(path):
    whole = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            whole.update(block)
    return whole.hexdigest()


def _place(path, chunks, mode):
    """Write ``chunks`` beside ``path`` and link it into place (never replacing a file); synced, ``mode``."""
    descriptor, staged = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            for block in chunks:
                stream.write(block)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(staged, mode)
        os.link(staged, path)
    finally:
        os.unlink(staged)


def _blocks(path):
    with open(path, "rb") as stream:
        yield from iter(lambda: stream.read(1 << 20), b"")


class DirectoryStore:
    """A content-addressed folder (an off-host mount): one file per SHA-256, written once, checked on every read."""

    def __init__(self, root):
        root = Path(root)
        if root.is_symlink() or not root.is_dir():
            raise ArchiveRefused("store_unavailable")
        self.root = root.resolve()

    def path(self, sha256):
        if type(sha256) is not str or not _HEX.fullmatch(sha256):
            raise ArchiveRefused("store_digest_invalid")
        return self.root / sha256[:2] / sha256

    def put(self, source, sha256):
        """Hold ``source``'s bytes under ``sha256``; an existing copy must already hold them."""
        target = self.path(sha256)
        if not target.exists():
            target.parent.mkdir(mode=0o700, exist_ok=True)
            try:
                _place(target, _blocks(source), 0o400)
            except FileExistsError:
                pass
        if _sha256(target) != sha256:
            raise ArchiveRefused("store_copy_differs")

    def get(self, sha256, destination, mode):
        """Put the bytes held under ``sha256`` at ``destination`` (a new name) with ``mode``, checked first."""
        source = self.path(sha256)
        if source.is_symlink() or not source.is_file() or _sha256(source) != sha256:
            raise ArchiveRefused("store_copy_unavailable")
        _place(destination, _blocks(source), mode)
        if _sha256(destination) != sha256:
            os.unlink(destination)
            raise ArchiveRefused("store_copy_differs")


def _payload_files(folder, min_bytes):
    """``{relative posix path: Path}`` of the folder's regular files of at least ``min_bytes`` (never a link)."""
    found = {}
    for directory, names, files in os.walk(folder, followlinks=False):
        names[:] = sorted(
            n for n in names if not os.path.islink(os.path.join(directory, n))
        )
        for name in sorted(files):
            path = Path(directory) / name
            info = os.lstat(path)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_size < min_bytes
                or kept_local(name)
            ):
                continue
            relative = path.relative_to(folder).as_posix()
            if relative != STUB:
                found[relative] = path
    return found


def archive_tree(folder, store, *, min_bytes=MIN_BYTES):
    """Move ``folder``'s files of at least ``min_bytes`` into ``store``, leaving the stub. Returns ``{"moved", "bytes",
    "freed"}`` (``freed``: bytes whose last name was removed; a file still linked elsewhere frees nothing yet).
    """
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise ArchiveRefused("folder_unavailable")
    stub = folder / STUB
    if os.path.lexists(stub):
        return {"moved": 0, "bytes": 0, "freed": 0}
    files = _payload_files(folder, min_bytes)
    if not files:
        return {"moved": 0, "bytes": 0, "freed": 0}
    record = {}
    for relative, path in files.items():
        sha256 = _sha256(path)
        store.put(path, sha256)
        info = os.lstat(path)
        record[relative] = {
            "sha256": sha256,
            "size": info.st_size,
            "mode": stat.S_IMODE(info.st_mode),
        }
    document = {"schema": SCHEMA, "store": str(store.root), "files": record}
    _place(
        stub,
        [json.dumps(document, sort_keys=True, separators=(",", ":")).encode()],
        0o600,
    )
    moved = total = freed = 0
    for relative, path in files.items():
        info = os.lstat(path)
        if (
            info.st_size != record[relative]["size"]
            or _sha256(path) != record[relative]["sha256"]
        ):
            raise ArchiveRefused("folder_changed_while_archiving")
        os.unlink(path)
        moved += 1
        total += info.st_size
        if info.st_nlink == 1:
            freed += info.st_size
    return {"moved": moved, "bytes": total, "freed": freed}


def _stub(folder):
    path = Path(folder) / STUB
    if path.is_symlink() or not path.is_file():
        return None
    document = json.loads(path.read_bytes())
    if (
        type(document) is not dict
        or document.get("schema") != SCHEMA
        or type(document.get("files")) is not dict
        or type(document.get("store")) is not str
    ):
        raise ArchiveRefused("stub_invalid")
    return document


def restore_tree(folder):
    """Put every archived file back (same name, bytes and mode), then remove the stub. Returns the files restored."""
    folder = Path(folder)
    document = _stub(folder)
    if document is None:
        return 0
    store = DirectoryStore(document["store"])
    restored = 0
    for relative, item in sorted(document["files"].items()):
        parts = Path(relative).parts
        if not parts or ".." in parts or Path(relative).is_absolute():
            raise ArchiveRefused("stub_invalid")
        target = folder.joinpath(*parts)
        if os.path.lexists(target):
            if target.is_symlink() or _sha256(target) != item["sha256"]:
                raise ArchiveRefused("restored_file_differs")
            continue
        mode = item["mode"]
        if type(mode) is not int or mode & ~0o777:
            raise ArchiveRefused("stub_invalid")
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        store.get(item["sha256"], target, mode)
        restored += 1
    os.unlink(folder / STUB)
    return restored


def restore_if_archived(folder):
    """True when ``folder`` was archived and is now whole again; False when it never was."""
    if _stub(folder) is None:
        return False
    restore_tree(folder)
    return True


def _newest(folder):
    newest = os.lstat(folder).st_mtime
    for directory, _names, files in os.walk(folder, followlinks=False):
        for name in files:
            newest = max(newest, os.lstat(os.path.join(directory, name)).st_mtime)
    return newest


def candidates(state, *, older_than_days, operations=False, now=None):
    """The folders older than ``older_than_days`` (newest file), not yet archived: each retained grade folder and, with
    ``operations``, each owner ledger's ``operation-*`` folder."""
    if type(older_than_days) not in (int, float) or older_than_days < 1:
        raise ArchiveRefused("age_unset")
    cutoff = (time.time() if now is None else now) - older_than_days * 86400
    state = Path(state)
    roots = [state / "auto-grade" / "artifacts"]
    found = []
    for root in roots:
        if root.is_dir():
            found += [
                p
                for p in sorted(root.iterdir())
                if re.fullmatch(r"rtsk_[0-9a-f]+(\.evaluation)?", p.name)
            ]
    if operations:
        found += sorted(state.glob("owners/*/ledger/operation-*"))
    return [
        p
        for p in found
        if not p.is_symlink()
        and p.is_dir()
        and not os.path.lexists(p / STUB)
        and _newest(p) < cutoff
    ]


def _succeeded_outputs(ledger):
    """``{operation folder name: recorded output_digest}`` of ``ledger``'s SUCCEEDED operations, read from its
    ``campaign.sqlite3`` opened read-only. An op still RESERVED (running, left running, adopted) or settled any other
    way names none; an unreadable ledger names none."""
    import sqlite3

    path = Path(ledger) / "campaign.sqlite3"
    if path.is_symlink() or not path.is_file():
        return {}
    try:
        db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10)
        try:
            rows = db.execute(
                "SELECT result FROM operations WHERE state='SUCCEEDED' AND result IS NOT NULL"
            ).fetchall()
        finally:
            db.close()
    except sqlite3.Error:
        return {}
    found = {}
    for (raw,) in rows:
        try:
            result = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if (
            type(result) is dict
            and type(result.get("operation")) is str
            and type(result.get("output_digest")) is str
        ):
            found[result["operation"]] = result["output_digest"]
    return found


def compact_streams(
    state, *, apply=False, settled_seconds=3600, now=None, listing=None
):
    """`research_carrier.compact_output_stream` for every decoded stream under ``state`` of an operation its ledger records
    SUCCEEDED, older than ``settled_seconds``, removed only when its own SHA-256 is that op's recorded output digest and
    framing + snapshot rebuild it byte for byte (V2 11:13:29Z). ``listing``: a TSV path written with every candidate
    (path, bytes, recorded digest). Returns the counts and bytes."""
    from carbon.development_session.research_carrier import compact_output_stream

    cutoff = (time.time() if now is None else now) - settled_seconds
    totals = {"streams": 0, "not_succeeded": 0, "compacted": 0, "kept": 0, "bytes": 0}
    rows = []
    outputs = {}
    for stream in sorted(Path(state).glob("owners/*/ledger/operation-*/export.stream")):
        info = os.lstat(stream)
        snapshot = stream.parent / "snapshot"
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_mtime >= cutoff
            or not snapshot.is_dir()
        ):
            continue
        ledger = stream.parent.parent
        if ledger not in outputs:
            outputs[ledger] = _succeeded_outputs(ledger)
        expected = outputs[ledger].get(stream.parent.name)
        if expected is None:
            totals["not_succeeded"] += 1
            continue
        totals["streams"] += 1
        rows.append(f"{stream}\t{info.st_size}\t{expected}\n")
        if not apply:
            totals["bytes"] += info.st_size
        elif compact_output_stream(stream, snapshot, expected=expected):
            totals["compacted"] += 1
            totals["bytes"] += info.st_size if info.st_nlink == 1 else 0
        else:
            totals["kept"] += 1
    if listing is not None:
        _place(Path(listing), [("".join(rows)).encode()], 0o600)
    return totals


def prune_objects(state, *, apply=False, older_than_seconds=86400, now=None):
    """The door-wide stored objects (`data.store_once`: ``<state>/objects``) no name links any more (link count 1,
    older than ``older_than_seconds``): removed with ``apply``, else only counted. A name staged meanwhile is not lost: a
    store that finds its object gone stores it again. Returns the count and bytes."""
    from carbon.development_session.data import DOOR_OBJECTS

    cutoff = (time.time() if now is None else now) - older_than_seconds
    totals = {"orphans": 0, "removed": 0, "bytes": 0}
    folder = Path(state) / DOOR_OBJECTS
    if folder.is_symlink() or not folder.is_dir():
        return totals
    for path in sorted(folder.iterdir()):
        info = os.lstat(path)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_mtime >= cutoff
            or not re.fullmatch(r"[0-9a-f]{64}-[0-7]{3,4}", path.name)
        ):
            continue
        totals["orphans"] += 1
        totals["bytes"] += info.st_size
        if apply:
            os.unlink(path)
            totals["removed"] += 1
    return totals


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state")
    parser.add_argument("--store")
    parser.add_argument("--older-than-days", type=float)
    parser.add_argument("--operations", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore")
    parser.add_argument("--compact-streams", action="store_true")
    parser.add_argument("--list")
    parser.add_argument("--prune-objects", action="store_true")
    args = parser.parse_args(argv)
    if args.prune_objects:
        if not args.state:
            parser.error("--state is required")
        print(
            json.dumps(
                {"apply": args.apply, **prune_objects(args.state, apply=args.apply)}
            )
        )
        return 0
    if args.compact_streams:
        if not args.state:
            parser.error("--state is required")
        print(
            json.dumps(
                {
                    "apply": args.apply,
                    **compact_streams(args.state, apply=args.apply, listing=args.list),
                }
            )
        )
        return 0
    if args.restore:
        print(
            json.dumps({"restored": restore_tree(args.restore), "folder": args.restore})
        )
        return 0
    if not (args.state and args.store and args.older_than_days):
        parser.error(
            "--state, --store and --older-than-days are all required (no defaults)"
        )
    store = DirectoryStore(args.store)
    folders = candidates(
        args.state, older_than_days=args.older_than_days, operations=args.operations
    )
    totals = {"folders": len(folders), "moved": 0, "bytes": 0, "freed": 0}
    for folder in folders:
        if not args.apply:
            files = _payload_files(folder, MIN_BYTES)
            totals["moved"] += len(files)
            totals["bytes"] += sum(os.lstat(p).st_size for p in files.values())
            continue
        result = archive_tree(folder, store)
        for key in ("moved", "bytes", "freed"):
            totals[key] += result[key]
    print(json.dumps({"apply": args.apply, **totals}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
