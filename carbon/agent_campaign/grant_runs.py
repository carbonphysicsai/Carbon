"""One run count per grant, across every controller root on the host.

A controller counts the runs in its own root. A grant of N runs is therefore N per
root: stage A's Constructor grant (5 runs) ran a sixth from a new root. For a LIVE
controller (`CampaignController(..., shared_runs=True)`) this module keeps one ledger
per grant id, outside the repository, and a launch is refused when the grant's
`permitted_runs` entries are already claimed, whichever root claimed them.

* Host-level and outside the repository: `CARBON_GRANT_RUNS_DIR`, else
  `~/.local/state/carbon/grant-runs`. A directory inside the repository is refused.
  Never committed.
* Counts and ids only: an entry is a digest of (store id, launch key), the store id,
  whether it was seeded, and no balance, account or key.
* Locked: an exclusive `flock` on the grant's file covers read, check and append, so two
  concurrent claims cannot both take the last slot.
* Fail closed: an unusable directory, an unreadable or corrupt ledger, or a grant id that
  cannot name a file refuses the launch (`grant_runs_unavailable`). There is no fallback
  to the per-root count alone.
* Migration: the first claim from a root seeds the ledger with that root's existing runs
  (so they are never under-counted from then on). Runs in OTHER roots that predate the
  ledger are not known until each root claims or is seeded:
  `python -m carbon.agent_campaign.grant_runs seed --grant-id ID --root DIR ...` counts
  the listed roots. The operator lists every root that used the grant.

Dry runs, prelive and tests build controllers without `shared_runs`, so they never
consume a real grant's runs.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
ENV = "CARBON_GRANT_RUNS_DIR"
DEFAULT = Path("~/.local/state/carbon/grant-runs")
LIMIT = "run_limit_reached"
UNAVAILABLE = "grant_runs_unavailable"
_SAFE = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_STORE_ID = re.compile(r"[0-9a-f]{32}")


class SharedRunsError(Exception):
    """A launch the shared ledger refuses; `code` is `run_limit_reached` or
    `grant_runs_unavailable`."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def ledger_dir(repository=REPOSITORY):
    """The host-level directory, created owner-only, or `SharedRunsError`."""
    configured = os.environ.get(ENV)
    base = Path(configured) if configured else DEFAULT.expanduser()
    if not base.is_absolute():
        raise SharedRunsError(UNAVAILABLE, "ledger directory is not absolute")
    base = Path(os.path.abspath(base))
    root = Path(repository).resolve()
    if base == root or root in base.parents:
        raise SharedRunsError(UNAVAILABLE, "ledger directory is inside the repository")
    try:
        base.mkdir(parents=True, exist_ok=True, mode=0o700)
        if base.is_symlink() or not base.is_dir():
            raise SharedRunsError(UNAVAILABLE, "ledger directory is not a directory")
        if not os.access(base, os.R_OK | os.W_OK | os.X_OK):
            raise SharedRunsError(UNAVAILABLE, "ledger directory is not accessible")
    except OSError as error:
        raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    return base


def _file(grant_id, repository):
    if type(grant_id) is not str or not _SAFE.fullmatch(grant_id):
        raise SharedRunsError(UNAVAILABLE, "grant id cannot name a ledger")
    tag = hashlib.sha256(grant_id.encode()).hexdigest()[:12]
    safe = grant_id.replace(":", "_")
    return ledger_dir(repository) / f"{safe}.{tag}.jsonl"


def entry_id(store_id, key):
    return hashlib.sha256(f"{store_id}\0{key}".encode()).hexdigest()


def _read(stream):
    stream.seek(0)
    entries = {}
    for number, line in enumerate(stream.read().decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            identifier = entry["entry"]
        except (ValueError, KeyError, TypeError):
            raise SharedRunsError(
                UNAVAILABLE, f"ledger line {number} is corrupt"
            ) from None
        if type(identifier) is not str or not re.fullmatch(r"[0-9a-f]{64}", identifier):
            raise SharedRunsError(UNAVAILABLE, f"ledger line {number} is corrupt")
        entries[identifier] = entry
    return entries


def _line(store_id, key, seeded):
    return (
        json.dumps(
            {"entry": entry_id(store_id, key), "store": store_id, "seeded": seeded},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def claim(grant, store_id, key, seed_keys=(), repository=REPOSITORY):
    """Claim one run of `grant` for launch `key` in the store `store_id`. Idempotent for
    a key already claimed. `seed_keys` are this store's existing launch keys, added first
    so they are counted. Raises `SharedRunsError`; returns the count after the claim."""
    if type(store_id) is not str or not _STORE_ID.fullmatch(store_id):
        raise SharedRunsError(UNAVAILABLE, "store id is invalid")
    path = _file(grant.grant_id, repository)
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as error:
        raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    with os.fdopen(descriptor, "r+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX)
            entries = _read(stream)
            stream.seek(0, os.SEEK_END)
            # This store's existing runs are facts: record them before deciding.
            for seed in seed_keys:
                identifier = entry_id(store_id, seed)
                if identifier not in entries:
                    entries[identifier] = {}
                    stream.write(_line(store_id, seed, True))
            stream.flush()
            os.fsync(stream.fileno())
            identifier = entry_id(store_id, key)
            if identifier not in entries:
                if len(entries) >= grant.permitted_runs:
                    raise SharedRunsError(
                        LIMIT, f"{len(entries)} of {grant.permitted_runs} runs claimed"
                    )
                entries[identifier] = {}
                stream.write(_line(store_id, key, False))
                stream.flush()
                os.fsync(stream.fileno())
        except SharedRunsError:
            raise
        except OSError as error:
            raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    return len(entries)


def count(grant_id, repository=REPOSITORY):
    """Runs claimed against `grant_id` on this host (fails closed if unreadable)."""
    path = _file(grant_id, repository)
    if not path.exists():
        return 0
    try:
        with open(path, "rb") as stream:
            fcntl.flock(stream, fcntl.LOCK_SH)
            return len(_read(stream))
    except OSError as error:
        raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None


def seed_root(grant, root, repository=REPOSITORY):
    """Count every run an existing controller root already holds, read-only from its
    store. Returns the ledger count after seeding."""
    from .controller import STORE_ID_FILE

    root = Path(root)
    try:
        store_id = (root / STORE_ID_FILE).read_text().strip()
    except OSError:
        raise SharedRunsError(UNAVAILABLE, "no store id in the root") from None
    database = root / "campaign.sqlite3"
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            keys = [
                r[0] for r in connection.execute("SELECT key FROM runs ORDER BY key")
            ]
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    if not keys:
        return count(grant.grant_id, repository)
    return claim_seeds(grant, store_id, keys, repository)


def claim_seeds(grant, store_id, keys, repository=REPOSITORY):
    """Seed `keys` (no new launch), refusing if they would exceed the grant."""
    path = _file(grant.grant_id, repository)
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as error:
        raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    with os.fdopen(descriptor, "r+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX)
            entries = _read(stream)
            stream.seek(0, os.SEEK_END)
            for key in keys:
                identifier = entry_id(store_id, key)
                if identifier not in entries:
                    entries[identifier] = {}
                    stream.write(_line(store_id, key, True))
            stream.flush()
            os.fsync(stream.fileno())
        except OSError as error:
            raise SharedRunsError(UNAVAILABLE, type(error).__name__) from None
    return len(entries)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.agent_campaign.grant_runs")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status", help="runs claimed against a grant id")
    status.add_argument("--grant-id", required=True)
    seed = sub.add_parser("seed", help="count the runs existing controller roots hold")
    seed.add_argument(
        "--grant", required=True, type=Path, help="the grant document (JSON file)"
    )
    seed.add_argument("--root", action="append", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            print(
                json.dumps({"grant_id": args.grant_id, "claimed": count(args.grant_id)})
            )
            return 0
        from .grant import SpendingGrant

        grant = SpendingGrant.from_document(json.loads(args.grant.read_text()))
        for root in args.root:
            total = seed_root(grant, root)
            print(
                json.dumps(
                    {"grant_id": grant.grant_id, "root": root.name, "claimed": total}
                )
            )
        return 0
    except SharedRunsError as error:
        print(error.code, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
