"""Back up and restore a battery validator deployment, root, journal and state together.

The deployment's handoff requires the private root, the seed journal and the
daemon state to be backed up together (`BATTERY_TESTNET_HOST_HANDOFF.md` §0.7
and §3): a lost root cannot be replaced without a new journal, and a state
without its journal cannot prove its batches. A backup therefore copies all
three under the deployment's single-writer lock, so no admission, run, batch
commitment or upgrade lands half inside it. The intake's inbox and transport
journal are copied beside them (each a consistent SQLite snapshot of its
own), so a restored host still holds the submissions miners were told it
received; the daemon's admission is idempotent, so an inbox a moment older or
newer than the state is resolved by the worker's next pass.

A backup is one owner-only directory `battery-validator-<UTC>` holding the
files and a `manifest.json` with each file's SHA-256 and size, the root's
public commitment and the journal's entry count - never the root itself. It
is written under a hidden name and renamed into place only when complete.

The work directory is not copied: a run whose staged output is missing after
a restore is retried as infrastructure, never held against the miner.

A backup carries the deployment's state, not its configuration: the
deployment, intake and service configurations, the TLS material and the
deployment's optional `service_key` are moved separately (owner-only) when a
deployment changes hosts.

A restore never overwrites and is all or nothing. It refuses while any part
of the service runs, however it was started (`running_parts`: the
supervisor's, the intake's and the daemon's locks), and when any destination
- or a SQLite side file beside one - already exists. It verifies every file
against the manifest and makes every destination directory owner-only before
writing a byte, writes each file under a temporary name and links it into
place (a link never replaces a file), and checks the restored deployment
loads with the same root commitment. If any step fails, every file this
restore wrote is removed again, so a rerun starts from the same state.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path

from .service import (
    REPOSITORY,
    ServiceRefused,
    _deployment,
    _intake,
    digest_file,
    load_service,
    owner_only_directory,
    running_parts,
)

BACKUP_SCHEMA = "carbon.battery.validator-backup.v1"
PREFIX = "battery-validator-"


def _members(intake_config, deployment_config):
    """`{file name in the backup: (role, source path, kind)}`."""
    from carbon.battery.intake import attempt_ledger_path

    return {
        "root.bin": ("private_root", Path(deployment_config["private_root"]), "bytes"),
        "journal.jsonl": ("seed_journal", Path(deployment_config["journal"]), "bytes"),
        "state.sqlite3": ("daemon_state", Path(deployment_config["state"]), "sqlite"),
        "inbox.sqlite3": ("intake_inbox", Path(intake_config["inbox"]), "sqlite"),
        "transport.sqlite3": (
            "transport_journal",
            Path(intake_config["transport_journal"]),
            "sqlite",
        ),
        # The operator's attempt ledger (VALIDATOR-01 VAL-D3): Track A's
        # record of every submission attempt, refusals included.
        "attempts.sqlite3": (
            "attempt_ledger",
            attempt_ledger_path(intake_config),
            "sqlite",
        ),
    }


#: The members a deployment cannot be restored without; the intake's three
#: are copied when they exist (an intake that never ran has none).
REQUIRED_MEMBERS = ("root.bin", "journal.jsonl", "state.sqlite3")


def digest_bytes(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _write_new(path, body):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def _sqlite_copy(source, destination):
    """A consistent snapshot of a live SQLite database (WAL included)."""
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    src = sqlite3.connect(source, timeout=30)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    for suffix in ("-wal", "-shm"):
        Path(str(destination) + suffix).unlink(missing_ok=True)


def _stamp(clock):
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(clock()))


def backup(path, *, repository=REPOSITORY, clock=time.time):
    """Snapshot root, journal and state together, with the intake's stores."""
    from carbon.battery import deployment

    service = load_service(path)
    intake_config = _intake(service, repository)
    deployment_config = _deployment(intake_config)
    members = _members(intake_config, deployment_config)
    for name in REQUIRED_MEMBERS:
        if not members[name][1].exists():
            raise ServiceRefused("backup_member_missing", member=members[name][0])
    try:
        target = deployment.validator(
            intake_config["deployment"], repository=repository, readonly=True
        )
    except deployment.EvaluationUnavailable as refused:
        raise ServiceRefused(refused.code) from None
    folder = owner_only_directory(service.backups, create=True)
    name = PREFIX + _stamp(clock)
    serial = 0
    while (folder / name).exists():
        serial += 1
        name = f"{PREFIX}{_stamp(clock)}-{serial}"
    partial = folder / ("." + name + ".partial")
    partial.mkdir(mode=0o700)
    try:
        manifest = _snapshot(target, members, partial, clock)
        os.rename(partial, folder / name)
    except BaseException:
        # A failed backup leaves no hidden copy of the private root behind.
        shutil.rmtree(partial, ignore_errors=True)
        raise
    return {"backup": str(folder / name), **manifest}


def _snapshot(target, members, partial, clock):
    """Copy every member into `partial` under the writer lock, then write
    the manifest; returns it."""
    from carbon.battery import deployment, seeds

    files = {}
    with deployment.writer(target):
        for member, (role, source, kind) in members.items():
            if not source.exists():
                continue
            destination = partial / member
            if kind == "sqlite":
                _sqlite_copy(source, destination)
            else:
                _write_new(destination, source.read_bytes())
            files[member] = {
                "role": role,
                "sha256": digest_file(destination),
                "bytes": destination.stat().st_size,
            }
        identities = target.store.identities()
    root = seeds.PrivateRoot.load(partial / "root.bin")
    journal = seeds.SeedJournal(partial / "journal.jsonl")
    manifest = {
        "schema": BACKUP_SCHEMA,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(clock())),
        "files": files,
        "root_commitment": root.commitment(),
        "journal_entries": len(journal._entries()),
        "identities_sha256": (
            None
            if identities is None
            else digest_bytes(json.dumps(identities, sort_keys=True).encode())
        ),
    }
    _write_new(
        partial / "manifest.json",
        (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode(),
    )
    return manifest


#: Files SQLite keeps beside a database. A restore never lands a database
#: next to one: a stale write-ahead log would be replayed into it.
SQLITE_SIDE = ("-wal", "-shm", "-journal")
RESTORING = ".restoring"


def _occupied(path):
    return path.exists() or path.is_symlink()


def _stage(path, body, written):
    """Write `body` to a new owner-only file, recording it in `written` the
    moment it exists, so a failed restore removes exactly what it made."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    written.append(path)
    with os.fdopen(fd, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def _forget(intake_config):
    """Drop this process's cached read-only build of the deployment."""
    from carbon.battery import deployment

    deployment._VALIDATORS.pop(
        (str(Path(intake_config["deployment"]).resolve()), True), None
    )


def restore(path, source, *, repository=REPOSITORY):
    """Restore one backup into the deployment's configured, absent paths,
    all or nothing (see the module's description)."""
    from carbon.battery import deployment

    service = load_service(path)
    intake_config = _intake(service, repository)
    deployment_config = _deployment(intake_config)
    parts = running_parts(service, intake_config)
    if parts:
        raise ServiceRefused(
            "restore_service_running",
            running=parts,
            next_step=(
                "stop the service first: systemctl --user stop "
                "carbon-battery-intake.service carbon-battery-validator.service, "
                "or SIGTERM the supervisor"
            ),
        )
    source = Path(source)
    try:
        manifest = json.loads((source / "manifest.json").read_bytes())
    except (OSError, ValueError):
        raise ServiceRefused("backup_manifest_unreadable") from None
    if type(manifest) is not dict or manifest.get("schema") != BACKUP_SCHEMA:
        raise ServiceRefused("backup_manifest_unreadable")
    members = _members(intake_config, deployment_config)
    files = manifest.get("files") or {}
    if set(files) - set(members) or not set(REQUIRED_MEMBERS) <= set(files):
        raise ServiceRefused("backup_manifest_unreadable")
    for member, recorded in files.items():
        held = source / member
        if not held.is_file() or digest_file(held) != recorded["sha256"]:
            raise ServiceRefused("backup_corrupt", member=member)
    # Nothing is written unless every destination is free: a restore never
    # replaces a root, journal or state, live or not, and never lands a
    # database beside a stale SQLite side file.
    plan = {}
    for member in files:
        role, destination, kind = members[member]
        beside = (
            [Path(str(destination) + suffix) for suffix in SQLITE_SIDE]
            if kind == "sqlite"
            else []
        )
        if any(_occupied(p) for p in (destination, *beside)):
            raise ServiceRefused("restore_target_exists", member=role)
        staged = destination.with_name("." + destination.name + RESTORING)
        if _occupied(staged):
            raise ServiceRefused(
                "restore_leftover_exists",
                member=role,
                next_step="remove the .restoring file an interrupted restore left",
            )
        plan[member] = (destination, staged, beside)
    # Every destination directory exists and is owner-only before any byte
    # is written, so no member can fail on its directory after another landed.
    for directory in sorted({entry[0].parent for entry in plan.values()}):
        owner_only_directory(directory, create=True)
    written = []
    try:
        for member, (_destination, staged, _beside) in plan.items():
            _stage(staged, (source / member).read_bytes(), written)
        for destination, staged, beside in plan.values():
            os.link(staged, destination)  # a link never replaces a file
            written += [destination, *beside]
        for _destination, staged, _beside in plan.values():
            staged.unlink()
            written.remove(staged)
        _forget(intake_config)
        try:
            target = deployment.validator(
                intake_config["deployment"], repository=repository, readonly=True
            )
        except deployment.EvaluationUnavailable as refused:
            raise ServiceRefused(refused.code) from None
        if target.root.commitment() != manifest["root_commitment"]:
            raise ServiceRefused("restore_root_differs")
    except BaseException:
        # All or nothing: remove every file this restore made (the members,
        # their staged copies, and SQLite files the check opened beside them).
        for made in written:
            made.unlink(missing_ok=True)
        _forget(intake_config)
        raise
    return {
        "restored": sorted(members[m][0] for m in files),
        "root_commitment": manifest["root_commitment"],
        "journal_entries": manifest["journal_entries"],
    }
