"""The on-box store of OFFICIAL GPU receipts (OWNER-GPU-OPEN-WITH-READY-01).

Official receipts live in the validator's state, not in the repository: a receipt per batch in the repository would move
the image ids on every batch and break the calibrate-once binding. The store is owner-only (directory 0700, files 0600),
write-once and append-only, and written only by the standing receipt job (`receipt_job`):

- ``records/<sha256>.json``: one record per file, named by the digest of its canonical bytes, created exclusively;
- ``receipts.log``: one line per record, each naming its sequence number, the record's digest and the digest of the
  previous line, so a removed, reordered or altered record breaks the chain;
- a replacement is a NEW record naming the one it replaces (``supersedes``); a record is never edited or deleted.

A record binds the bundle digest, the pinned GPU image id, the host class, the determinism-flags digest, the result
(bit-identical, or a difference within the Challenge's registered rebuild noise) and the run digests. A malformed,
foreign-owned, loosely-permissioned or mismatched record is refused (`ReceiptRefused`), never served. The module
imports only the standard library: a catalog module must not reach the execution side.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path

SCHEMA = "carbon.backbone-catalog.official-gpu-receipt.v1"
LOG_SCHEMA = "carbon.backbone-catalog.official-gpu-receipt-log.v1"
LOG = "receipts.log"
RECORDS = "records"
BIT_IDENTICAL = "bit_identical"
WITHIN_NOISE = "within_noise"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_KEYS = {
    "schema",
    "catalog_id",
    "runtime_profile_id",
    "bundle_digest",
    "image_id",
    "host_class",
    "determinism_flags_digest",
    "result",
    "run_digests",
    "supersedes",
}


class ReceiptRefused(ValueError):
    """A store, record or log line that is not what the rules above require."""


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _is_digest(value) -> bool:
    return type(value) is str and _DIGEST.fullmatch(value) is not None


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def check_record(record, registered_noise=None) -> None:
    """Refuse a record that is not exactly the schema, or whose result does not hold.

    ``registered_noise(challenge_id)`` is the Challenge's registered rebuild noise (a number, or None when none is
    registered): a within-noise result is refused unless its stated noise IS the registered one and the measured
    difference is within it. A bit-identical result needs identical run digests."""
    if type(record) is not dict or set(record) != _KEYS:
        raise ReceiptRefused("record_shape")
    if record["schema"] != SCHEMA:
        raise ReceiptRefused("record_schema")
    for key in ("catalog_id", "runtime_profile_id", "host_class"):
        if type(record[key]) is not str or not record[key]:
            raise ReceiptRefused(f"record_{key}")
    for key in ("bundle_digest", "image_id", "determinism_flags_digest"):
        if not _is_digest(record[key]):
            raise ReceiptRefused(f"record_{key}")
    runs = record["run_digests"]
    if type(runs) is not list or len(runs) < 2 or not all(map(_is_digest, runs)):
        raise ReceiptRefused("record_run_digests")
    if record["supersedes"] is not None and not _is_digest(record["supersedes"]):
        raise ReceiptRefused("record_supersedes")
    result = record["result"]
    if type(result) is not dict:
        raise ReceiptRefused("record_result")
    if result.get("kind") == BIT_IDENTICAL:
        if set(result) != {"kind"} or len(set(runs)) != 1:
            raise ReceiptRefused("record_not_bit_identical")
    elif result.get("kind") == WITHIN_NOISE:
        if set(result) != {"kind", "challenge_id", "noise_value", "max_abs_diff"}:
            raise ReceiptRefused("record_result")
        noise, diff = result["noise_value"], result["max_abs_diff"]
        if (
            type(result["challenge_id"]) is not str
            or not result["challenge_id"]
            or not _number(noise)
            or not _number(diff)
            or not noise > 0
            or diff < 0
        ):
            raise ReceiptRefused("record_result")
        if diff > noise:
            raise ReceiptRefused("record_beyond_noise")
        registered = (
            None
            if registered_noise is None
            else registered_noise(result["challenge_id"])
        )
        if registered is None or registered != noise:
            raise ReceiptRefused("record_noise_not_registered")
    else:
        raise ReceiptRefused("record_result")


def _owned_private(path: Path, *, directory: bool) -> os.stat_result:
    try:
        info = os.lstat(path)
    except OSError:
        raise ReceiptRefused("store_unreadable") from None
    wanted = stat.S_ISDIR if directory else stat.S_ISREG
    owner = getattr(os, "geteuid", lambda: info.st_uid)()
    if not wanted(info.st_mode) or info.st_uid != owner or info.st_mode & 0o077:
        raise ReceiptRefused("store_not_owner_only")
    return info


class ReceiptStore:
    """Read and (for the standing job only) append to the store at ``root``."""

    def __init__(self, root, *, registered_noise=None):
        self.root = Path(root)
        self.registered_noise = registered_noise

    # --- reading -------------------------------------------------------------------------------------------------

    def records(self) -> list:
        """Every logged record, in log order, after verifying the whole store; refuses on any defect.

        An absent store has no records."""
        if not os.path.lexists(self.root):
            return []
        _owned_private(self.root, directory=True)
        log = self.root / LOG
        if not os.path.lexists(log):
            return []
        _owned_private(log, directory=False)
        _owned_private(self.root / RECORDS, directory=True)
        found, previous = [], None
        for sequence, line in enumerate(log.read_bytes().splitlines()):
            try:
                entry = json.loads(line)
            except ValueError:
                raise ReceiptRefused("log_line") from None
            if (
                type(entry) is not dict
                or set(entry) != {"schema", "sequence", "record", "previous"}
                or entry["schema"] != LOG_SCHEMA
                or entry["sequence"] != sequence
                or entry["previous"] != previous
                or not _is_digest(entry["record"])
            ):
                raise ReceiptRefused("log_chain")
            found.append(self._record(entry["record"]))
            previous = digest(line)
        self._links(found)
        return found

    def _record(self, record_digest):
        path = self.root / RECORDS / (record_digest.removeprefix("sha256:") + ".json")
        _owned_private(path, directory=False)
        raw = path.read_bytes()
        if digest(raw) != record_digest:
            raise ReceiptRefused("record_digest")
        try:
            record = json.loads(raw)
        except ValueError:
            raise ReceiptRefused("record_shape") from None
        check_record(record, self.registered_noise)
        if canonical(record) != raw:
            raise ReceiptRefused("record_not_canonical")
        return record

    @staticmethod
    def _links(found):
        """A replacement names the record it replaces, and nothing is replaced twice."""
        by_digest, replaced = {}, set()
        for record in found:
            own = digest(canonical(record))
            old = record["supersedes"]
            if old is not None:
                before = by_digest.get(old)
                if (
                    before is None
                    or old in replaced
                    or (before["bundle_digest"], before["runtime_profile_id"])
                    != (record["bundle_digest"], record["runtime_profile_id"])
                ):
                    raise ReceiptRefused("record_supersedes")
                replaced.add(old)
            by_digest[own] = record
        heads = {}
        for own, record in by_digest.items():
            if own in replaced:
                continue
            key = (record["bundle_digest"], record["runtime_profile_id"])
            if key in heads:
                raise ReceiptRefused("record_fork")
            heads[key] = record

    def current(self, bundle_digest, runtime):
        """The record in force for this bundle and runtime, or None when it has none."""
        found = self.records()
        replaced = {r["supersedes"] for r in found if r["supersedes"]}
        newest = None
        for record in found:
            if digest(canonical(record)) in replaced:
                continue
            if (record["bundle_digest"], record["runtime_profile_id"]) == (
                bundle_digest,
                runtime,
            ):
                newest = record
        return newest

    # --- writing (the standing receipt job only) --------------------------------------------------------------

    def append(self, record) -> str:
        """Append ``record``; returns its digest. A replacement names the record in force; a new bundle must have none.

        The store is created owner-only on first use. Exclusive: one writer at a time.
        """
        import fcntl

        check_record(record, self.registered_noise)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        (self.root / RECORDS).mkdir(mode=0o700, exist_ok=True)
        _owned_private(self.root, directory=True)
        _owned_private(self.root / RECORDS, directory=True)
        log = self.root / LOG
        fd = os.open(log, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            _owned_private(log, directory=False)
            existing = self.records()  # verifies the chain before extending it
            key = (record["bundle_digest"], record["runtime_profile_id"])
            inforce = self.current(*key)
            if inforce is None and record["supersedes"] is not None:
                raise ReceiptRefused("record_supersedes")
            if inforce is not None and record["supersedes"] != digest(
                canonical(inforce)
            ):
                raise ReceiptRefused("record_replacement_must_name_the_old")
            raw = canonical(record)
            own = digest(raw)
            path = self.root / RECORDS / (own.removeprefix("sha256:") + ".json")
            try:
                out = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                if (
                    path.read_bytes() != raw
                ):  # an orphan from an earlier crash is fine only if identical
                    raise ReceiptRefused("record_exists") from None
            else:
                with os.fdopen(out, "wb") as handle:
                    handle.write(raw)
            lines = log.read_bytes().splitlines()
            line = canonical(
                {
                    "schema": LOG_SCHEMA,
                    "sequence": len(existing),
                    "record": own,
                    "previous": digest(lines[-1]) if lines else None,
                }
            )
            os.write(fd, line + b"\n")
            os.fsync(fd)
            return own
        finally:
            os.close(fd)

    def log_digest(self):
        """The digest of the whole append-only log (what an operator pins or compares), or None when empty."""
        self.records()
        log = self.root / LOG
        return digest(log.read_bytes()) if os.path.lexists(log) else None
