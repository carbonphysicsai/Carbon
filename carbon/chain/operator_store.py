"""Private C0 journal operations; no SDK, acceptance or settlement authority."""

import hashlib
import json
import os
import sqlite3
import stat
import time
from contextlib import closing, contextmanager
from dataclasses import asdict
from pathlib import Path

from carbon.transport.models import canonical

from .dispatch import STATES, TERMINAL
from .models import ChainContext

MAX_DATABASE_BYTES = 1024**3  # DEVELOPMENT, not a production capacity promise.


class OperatorFailure(RuntimeError):
    pass


def regular(path, *, maximum=MAX_DATABASE_BYTES):
    path = Path(path).absolute()
    if path.resolve() != path or not path.is_file():
        raise OperatorFailure("REGULAR_CANONICAL_FILE_REQUIRED")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
        raise OperatorFailure("FILE_TYPE_OR_SIZE_REJECTED")
    return path


def new_path(path):
    path = Path(path).absolute()
    if path.resolve() != path or not path.parent.is_dir() or path.exists():
        raise OperatorFailure("NEW_CANONICAL_DESTINATION_REQUIRED")
    return path


def read_json(path, *, maximum=65536):
    path = regular(path, maximum=maximum)

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise OperatorFailure("DUPLICATE_JSON_FIELD")
            result[key] = value
        return result

    def invalid(_):
        raise OperatorFailure("NONFINITE_JSON")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=invalid,
    )


def sync_directory(path):
    if os.name == "posix":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def exclusive_json(path, value):
    path = new_path(path)
    data = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


@contextmanager
def journal_view(path):
    path = regular(path)
    with closing(
        sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)
    ) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("BEGIN")
        yield db


def identity(db):
    row = db.execute("SELECT context FROM transport_meta WHERE id=1").fetchone()
    if row is None:
        raise OperatorFailure("MISSING_JOURNAL_CONTEXT")
    context = ChainContext(**json.loads(row[0]))
    if context.network != "localnet" or context.netuid == 0:
        raise OperatorFailure("LOCALNET_JOURNAL_REQUIRED")
    if canonical(asdict(context)).decode() != row[0]:
        raise OperatorFailure("NONCANONICAL_JOURNAL_CONTEXT")
    return context


def schema_digest(db):
    rows = db.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
    ).fetchall()
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def sha256(path):
    with regular(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@contextmanager
def publisher_lease(journal):
    """OS releases the same inode lock on crash; never unlink or trust a PID file."""
    journal = regular(journal)
    path = journal.with_name(journal.name + ".publisher.lock")
    if path.resolve() != path:
        raise OperatorFailure("LOCK_PATH_REJECTED")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    acquired = False
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OperatorFailure("LOCK_FILE_REJECTED")
        if os.name == "nt":
            import msvcrt

            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError:
                raise OperatorFailure("PUBLISHER_ALREADY_OWNED") from None
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise OperatorFailure("PUBLISHER_ALREADY_OWNED") from None
        acquired = True
        yield
    finally:
        if acquired:
            if os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def health(path, *, now_ms=None):
    """Local observation only: timestamps diagnose age, never accrue reward credit."""
    now_ms = time.time_ns() // 1000000 if now_ms is None else now_ms
    if type(now_ms) is not int or now_ms < 0:
        raise OperatorFailure("INVALID_HEALTH_CLOCK")
    with journal_view(path) as db:
        context = identity(db)
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        pending, latest, total = [], None, 0
        if "publication_v1" in tables:
            for row in db.execute(
                "SELECT identity,document,digest,state,tracking,tracking_digest FROM publication_v1"
            ):
                total += 1
                if (
                    total > 10000
                    or row[3] not in STATES
                    or any(
                        hashlib.sha256(row[value].encode()).hexdigest() != row[pin]
                        for value, pin in ((1, 2), (4, 5))
                    )
                ):
                    raise OperatorFailure("CONFLICTING_PUBLICATION_JOURNAL")
                if row[3] not in TERMINAL:
                    pending.append(row[0])
                doc, tracking = json.loads(row[1]), json.loads(row[4])
                timestamp = doc["snapshot"]["timestamp_ms"]
                if latest is None or timestamp > latest[0]:
                    latest = (timestamp, row[3], tracking)
        if len(pending) > 1:
            raise OperatorFailure("CONFLICTING_PENDING_DISPATCHES")
        clock = db.execute(
            "SELECT block,chain_time FROM transport_meta WHERE id=1"
        ).fetchone()
        if "reward_clock_v1" in tables:
            clock = (
                db.execute(
                    "SELECT block,time_ms FROM reward_clock_v1 WHERE id=1"
                ).fetchone()
                or clock
            )
        age = None if not clock[1] else now_ms - clock[1]
        return {
            "schema": "carbon.localnet.operator.health.v1",
            "maturity": "SYNTHETIC_ONLY",
            "network": context.network,
            "finalized_block_last_observed": clock[0],
            "chain_observation_age_ms": age,
            "observation_health": (
                "UNKNOWN"
                if age is None
                else (
                    "CLOCK_DISAGREEMENT"
                    if age < 0
                    else "STALE" if age > 30000 else "RECENT"
                )
            ),
            "pending_dispatch": pending[0] if pending else None,
            "dispatch_count": total,
            "capacity": (
                "EXHAUSTED"
                if total >= 10000
                else "NEAR_CAPACITY" if total >= 9000 else "AVAILABLE"
            ),
            "last_dispatch_state": None if latest is None else latest[1],
            "last_stored_row_block": (
                None if latest is None else latest[2].get("row_block")
            ),
            "settlement": "OBSERVE_CHAIN_SEPARATELY",
            "stored_weights_may_remain_effective": True,
            "treasury": None,
        }


def backup(journal, destination):
    """Copy every table/WAL-consistent snapshot; no publication pause or deletion."""
    destination = new_path(destination)
    destination.mkdir(mode=0o700)
    snapshot = destination / "journal.sqlite"
    # SQLite backup owns its consistent source view; do not copy a live db file.
    with journal_view(journal) as source:
        context = identity(source)
        if (
            source.execute("PRAGMA page_count").fetchone()[0]
            * source.execute("PRAGMA page_size").fetchone()[0]
            > MAX_DATABASE_BYTES
        ):
            raise OperatorFailure("LOGICAL_DATABASE_TOO_LARGE")
        deadline = time.monotonic() + 60

        def progress(_status, _remaining, _total):
            if time.monotonic() > deadline:
                raise OperatorFailure("BACKUP_DEADLINE_EXCEEDED")

        fd = os.open(snapshot, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        with closing(sqlite3.connect(snapshot)) as target:
            source.backup(target, pages=256, progress=progress)
            if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise OperatorFailure("BACKUP_INTEGRITY_FAILED")
            schema = schema_digest(target)
    with snapshot.open("r+b") as stream:
        os.fsync(stream.fileno())
    manifest = {
        "schema": "carbon.localnet.journal.backup.v1",
        "context": asdict(context),
        "sha256": sha256(snapshot),
        "schema_sha256": schema,
        "size": snapshot.stat().st_size,
        "maturity": "SYNTHETIC_ONLY",
        "contains_all_tables": True,
    }
    exclusive_json(destination / "manifest.json", manifest)
    return manifest


def restore(directory, destination, expected_context):
    """Restore into a new path only; original journal and unresolved rights survive."""
    destination = new_path(destination)
    directory = Path(directory)
    manifest = read_json(directory / "manifest.json")
    source = regular(directory / "journal.sqlite")
    if set(manifest) != {
        "schema",
        "context",
        "sha256",
        "schema_sha256",
        "size",
        "maturity",
        "contains_all_tables",
    } or (
        manifest["schema"] != "carbon.localnet.journal.backup.v1"
        or manifest["context"] != asdict(expected_context)
        or manifest["maturity"] != "SYNTHETIC_ONLY"
        or manifest["contains_all_tables"] is not True
        or manifest["size"] != source.stat().st_size
        or manifest["sha256"] != sha256(source)
    ):
        raise OperatorFailure("BACKUP_IDENTITY_OR_DIGEST_MISMATCH")
    with journal_view(source) as db:
        if (
            identity(db) != expected_context
            or schema_digest(db) != manifest["schema_sha256"]
            or db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]
        ):
            raise OperatorFailure("BACKUP_SCHEMA_OR_INTEGRITY_MISMATCH")
    temp = destination.with_name(destination.name + ".restore-pending")
    fd = os.open(new_path(temp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if sha256(temp) != manifest["sha256"]:
            raise OperatorFailure("BACKUP_CHANGED_DURING_RESTORE")
        # Atomic publish; existing destination is never replaced.
        os.link(temp, destination)
    finally:
        temp.unlink(missing_ok=True)
    sync_directory(destination.parent)
    return manifest
