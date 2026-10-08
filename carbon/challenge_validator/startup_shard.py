"""Sharded solves for a startup host (PRODUCER-STARTUP-HOST-01 slice 1).
Producer-only: no validator surface imports it.

A bank fill or any other large solve is split into shards. A dedicated
startup host solves its shard with the same pinned truth image, code and
overlay, and the producer merges the records back. Every solve in Carbon
shares one shape, a work directory's `jobs.json` and its `records.jsonl`, so
this is Challenge-neutral. Each Challenge supplies only how a job's inputs
and terminal statuses read (`ADAPTERS`).

    python -m carbon.challenge_validator.startup_shard split --work W --shards N --out D \\
        --challenge C --custody RECORD.md --host-key SHA256:...
    python -m carbon.challenge_validator.startup_shard merge --work W --shard D/shard-K --challenge C
    python -m carbon.challenge_validator.startup_shard status --work W

- **The custody gate.** A shard carries hidden cases to another host, which
  is a custody extension and the owner's security call. `split` refuses
  (`startup_custody_unrecorded`) unless the named decision file under
  `.agent/decisions/` records OWNER-STARTUP-HOST-CUSTODY-01 and the host's
  SSH host-key fingerprint.
- **Split.** Every job with no terminal record goes into exactly one shard,
  balanced by count and in a deterministic order. Each shard's manifest pins
  the work fingerprint, the code commit, the truth image, the overlay, the
  host key, and a digest of its jobs. It is journaled (`shard_written`) in
  `W/startup-journal.jsonl`. A re-split of the same work writes the same
  shards.
- **Merge.** A shard's records are accepted only if its manifest is one
  `split` journaled for this work, with today's pins, and every record is a
  terminal outcome for one of the shard's own jobs, for exactly its inputs.
  - Infrastructure failures are skipped, left for a re-split.
  - A case that already holds an identical record is skipped. A different
    terminal record for an already-solved case refuses the whole shard
    (`startup_record_mismatch`), and nothing is appended.
  - Accepted records are appended to `W/records.jsonl` and journaled
    (`shard_merged`). Then the normal seal or ingest runs, unchanged.

The journal and `status` hold public counts and digests only.
DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from .batch_source import ProducerRefused

REPOSITORY = Path(__file__).resolve().parents[2]
MANIFEST_SCHEMA = "carbon.challenge-validator.startup-shard.v1"
JOURNAL = "startup-journal.jsonl"
CUSTODY_RECORD = "OWNER-STARTUP-HOST-CUSTODY-01"
HOST_KEY = re.compile(r"SHA256:[A-Za-z0-9+/]{43}=?")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


# --- what each Challenge supplies ---------------------------------------------------


class Battery:
    """Battery's truth jobs: the case id and the inputs, flattened. A refine
    job also carries `refined: true`."""

    terminal = ("OK", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT")

    @staticmethod
    def inputs(job):
        from carbon.battery.challenge import INPUTS

        return {k: job[k] for k in INPUTS}

    @staticmethod
    def pins(repository, overlay):
        from carbon.battery.truth import TRUTH_IMAGE
        from carbon.battery.truth_env import load_lock

        _lock, lock_sha = load_lock(repository)
        return {"image": TRUTH_IMAGE["base_image"], "overlay": "sha256:" + lock_sha}


class Motor:
    """Motor's GetDP jobs: `{case_id, inputs}`."""

    @property
    def terminal(self):
        from .motor_hidden import TERMINAL

        return TERMINAL

    @staticmethod
    def inputs(job):
        return job["inputs"]

    @staticmethod
    def pins(repository, overlay):
        from .motor_hidden import SOLVER_IMAGE

        return {"image": SOLVER_IMAGE, "overlay": None}


def adapters():
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        MOTOR_CHALLENGE,
    )

    return {BATTERY_CHALLENGE: Battery(), MOTOR_CHALLENGE: Motor()}


def adapter_for(challenge_id):
    found = adapters().get(challenge_id)
    if found is None:
        raise ProducerRefused("startup_challenge_not_served")
    return found


def code_commit(repository):
    done = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.strip() or None


# --- the custody gate ---------------------------------------------------------------


def require_custody(record_file, host_keys, *, repository=REPOSITORY):
    """The owner's custody record for this startup names every host's key
    (one or more hosts; a single key is accepted as a string). Returns its
    sha256."""
    if type(host_keys) is str:
        host_keys = [host_keys]
    if (
        type(host_keys) not in (list, tuple)
        or not host_keys
        or len(set(host_keys)) != len(host_keys)
        or any(type(k) is not str or not HOST_KEY.fullmatch(k) for k in host_keys)
    ):
        raise ProducerRefused("startup_host_key_malformed")
    if type(record_file) is not str or not record_file:
        raise ProducerRefused("startup_custody_unrecorded")
    if record_file.startswith("/"):
        return _startup_hosts_file(record_file, host_keys, repository)
    if "/" in record_file or not record_file.endswith(".md"):
        raise ProducerRefused("startup_custody_unrecorded")
    path = Path(repository) / ".agent" / "decisions" / record_file
    try:
        body = path.read_bytes()
    except OSError:
        raise ProducerRefused("startup_custody_unrecorded") from None
    if CUSTODY_RECORD.encode() not in body or any(
        k.encode() not in body for k in host_keys
    ):
        raise ProducerRefused("startup_custody_unrecorded")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _standing_record(repository):
    """The repository's standing custody record (the procedure's approval),
    or None."""
    for path in sorted((Path(repository) / ".agent" / "decisions").glob("*.md")):
        body = path.read_bytes()
        if b"## " in body and CUSTODY_RECORD.encode() in body.split(b"\n", 1)[0]:
            return body
    return None


def _startup_hosts_file(path, host_keys, repository):
    """A per-startup hosts file the owner writes on the producer host, under
    the repository's standing record (hourly startup hosts, created per
    startup). It must name the record and every host key, and be a regular
    file only root can write. Returns the sha256 over the standing record
    and the file."""
    import os
    import stat

    standing = _standing_record(repository)
    if standing is None:
        raise ProducerRefused("startup_custody_unrecorded")
    try:
        info = os.lstat(path)
        body = Path(path).read_bytes()
    except OSError:
        raise ProducerRefused("startup_custody_unrecorded") from None
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ProducerRefused("startup_custody_file_not_owner_written")
    if CUSTODY_RECORD.encode() not in body or any(
        k.encode() not in body for k in host_keys
    ):
        raise ProducerRefused("startup_custody_unrecorded")
    return "sha256:" + hashlib.sha256(standing + b"\0" + body).hexdigest()


# --- the work directory ----------------------------------------------------------


def _owner_only_dir(path):
    path = Path(path)
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def _read_json(path):
    return json.loads(Path(path).read_text())


def _records(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(_canonical(value) + "\n")


def _journal(work):
    return _records(Path(work) / JOURNAL)


def _append_journal(work, event, **fields):
    entry = {"event": event, "sequence": len(_journal(work)), **fields}
    path = Path(work) / JOURNAL
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as handle:
        handle.write(_canonical(entry) + "\n")
    return entry


def _key(item):
    """A solve's identity: its case id, and whether it is the refined solve
    of that case (battery's truth service keys records the same way)."""
    return (item.get("case_id"), bool(item.get("refined")))


def _terminal_by_case(work, terminal):
    found = {}
    for record in _records(Path(work) / "records.jsonl"):
        if record.get("status") in terminal and _key(record) not in found:
            found[_key(record)] = record
    return found


# --- split, merge, status -----------------------------------------------------------


def split(
    work,
    shards,
    out,
    challenge_id,
    *,
    custody,
    host_key,
    overlay=None,
    repository=REPOSITORY,
    commit=None,
):
    """Write `shards` shard directories under `out` covering every job of
    `work` with no terminal record. Returns public summaries."""
    if type(shards) is not int or shards < 1:
        raise ProducerRefused("startup_shards_malformed")
    adapter = adapter_for(challenge_id)
    hosts = [host_key] if type(host_key) is str else list(host_key)
    custody_sha = require_custody(custody, hosts, repository=repository)
    work = Path(work)
    jobs_file = _read_json(work / "jobs.json")
    solved = _terminal_by_case(work, adapter.terminal)
    left = sorted(
        (j for j in jobs_file["jobs"] if _key(j) not in solved),
        key=lambda j: (j["case_id"], bool(j.get("refined"))),
    )
    if not left:
        return []
    pins = {
        "work_fingerprint": jobs_file.get("fingerprint"),
        "code": commit if commit is not None else code_commit(repository),
        **adapter.pins(repository, overlay),
        "custody_sha256": custody_sha,
        "challenge_id": challenge_id,
    }
    out = _owner_only_dir(out)
    summaries = []
    for k in range(shards):
        mine = left[k::shards]
        if not mine:
            continue
        manifest = {
            "schema": MANIFEST_SCHEMA,
            **pins,
            # Shards go to the startup's hosts round-robin; each manifest
            # pins the one host it is for.
            "host_key": hosts[k % len(hosts)],
            "shard": k,
            "shards": shards,
            "jobs": len(mine),
            "jobs_digest": _digest(mine),
        }
        digest = _digest(manifest)
        directory = _owner_only_dir(out / f"shard-{k}")
        _write_private(directory / "manifest.json", manifest)
        _write_private(
            directory / "jobs.json",
            {
                "fingerprint": jobs_file.get("fingerprint"),
                "shard": digest,
                "jobs": mine,
            },
        )
        if not any(
            e["event"] == "shard_written" and e["manifest_digest"] == digest
            for e in _journal(work)
        ):
            _append_journal(
                work, "shard_written", manifest_digest=digest, shard=k, jobs=len(mine)
            )
        summaries.append(
            {
                "shard": k,
                "jobs": len(mine),
                "host_key": manifest["host_key"],
                "manifest_digest": digest,
            }
        )
    return summaries


def merge(
    work, shard_dir, challenge_id, *, overlay=None, repository=REPOSITORY, commit=None
):
    """Accept one solved shard's records into `work`, all or nothing.
    Returns public counts."""
    adapter = adapter_for(challenge_id)
    work, shard_dir = Path(work), Path(shard_dir)
    manifest = _read_json(shard_dir / "manifest.json")
    digest = _digest(manifest)
    if not any(
        e["event"] == "shard_written" and e["manifest_digest"] == digest
        for e in _journal(work)
    ):
        raise ProducerRefused("startup_shard_not_from_this_work")
    pins = {
        "code": commit if commit is not None else code_commit(repository),
        **adapter.pins(repository, overlay),
        "challenge_id": challenge_id,
    }
    if any(manifest.get(k) != v for k, v in pins.items()):
        raise ProducerRefused("startup_shard_pins_changed")
    shard_jobs = _read_json(shard_dir / "jobs.json")
    if (
        shard_jobs.get("shard") != digest
        or _digest(shard_jobs["jobs"]) != manifest["jobs_digest"]
    ):
        raise ProducerRefused("startup_shard_jobs_changed")
    jobs = {_key(j): j for j in shard_jobs["jobs"]}
    held = _terminal_by_case(work, adapter.terminal)
    accepted, skipped, infra = [], 0, 0
    seen = set()
    for record in _records(shard_dir / "records.jsonl"):
        key = _key(record) if type(record) is dict else None
        job = jobs.get(key)
        if job is None:
            raise ProducerRefused("startup_record_outside_shard")
        if record.get("inputs") != adapter.inputs(job):
            raise ProducerRefused("startup_record_inputs_changed")
        if record.get("status") not in adapter.terminal:
            infra += 1
            continue
        if key in seen:
            continue
        seen.add(key)
        if key in held:
            if _canonical(held[key]) != _canonical(record):
                raise ProducerRefused("startup_record_mismatch")
            skipped += 1
            continue
        accepted.append(record)
    if accepted:
        path = work / "records.jsonl"
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a") as handle:
            for record in accepted:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
    walls = sorted(
        float(r["wall_s"]) for r in accepted if type(r.get("wall_s")) in (int, float)
    )
    entry = _append_journal(
        work,
        "shard_merged",
        manifest_digest=digest,
        accepted=len(accepted),
        skipped=skipped,
        infra=infra,
        records_digest=_digest(accepted),
        wall_s_p50=walls[len(walls) // 2] if walls else None,
        wall_s_p95=(
            walls[min(len(walls) - 1, int(0.95 * len(walls)))] if walls else None
        ),
    )
    return {k: entry[k] for k in entry if k != "event"}


#: The custody transfers the startup runbook journals, in order.
TRANSFER_EVENTS = ("pushed", "pulled", "wiped", "deleted")


def note(work, event, *, host_key, manifest_digest=None, nbytes=None):
    """Journal one custody transfer (the startup runbook, slice 2): a shard
    or the overlay pushed to a startup host, its records pulled back, the
    host's copies wiped, the server deleted. Public values only."""
    if event not in TRANSFER_EVENTS:
        raise ProducerRefused("startup_event_unknown")
    if type(host_key) is not str or not HOST_KEY.fullmatch(host_key):
        raise ProducerRefused("startup_host_key_malformed")
    if manifest_digest is not None and not any(
        e["event"] == "shard_written" and e["manifest_digest"] == manifest_digest
        for e in _journal(work)
    ):
        raise ProducerRefused("startup_shard_not_from_this_work")
    if nbytes is not None and (type(nbytes) is not int or nbytes < 0):
        raise ProducerRefused("startup_bytes_malformed")
    fields = {"host_key": host_key}
    if manifest_digest is not None:
        fields["manifest_digest"] = manifest_digest
    if nbytes is not None:
        fields["bytes"] = nbytes
    return _append_journal(work, event, **fields)


def status(work):
    """Public counts per shard."""
    written, merged = {}, {}
    for entry in _journal(work):
        if entry["event"] == "shard_written":
            written[entry["manifest_digest"]] = entry
        elif entry["event"] == "shard_merged":
            merged.setdefault(entry["manifest_digest"], []).append(entry)
    return {
        "shards": [
            {
                "shard": w["shard"],
                "jobs": w["jobs"],
                "merged": sum(m["accepted"] for m in merged.get(d, [])),
                "infra": sum(m["infra"] for m in merged.get(d, [])),
                "wall_s_p50": next(
                    (m["wall_s_p50"] for m in reversed(merged.get(d, []))), None
                ),
            }
            for d, w in written.items()
        ]
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.startup_shard")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("split")
    for name in ("--work", "--out", "--challenge", "--custody"):
        s.add_argument(name, required=True)
    # One per startup host (CCX63s, created per startup): repeatable.
    s.add_argument("--host-key", required=True, action="append")
    s.add_argument("--shards", type=int, required=True)
    s.add_argument("--overlay")
    m = sub.add_parser("merge")
    for name in ("--work", "--shard", "--challenge"):
        m.add_argument(name, required=True)
    m.add_argument("--overlay")
    sub.add_parser("status").add_argument("--work", required=True)
    n = sub.add_parser("note")
    n.add_argument("--work", required=True)
    n.add_argument("--event", required=True, choices=TRANSFER_EVENTS)
    n.add_argument("--host-key", required=True)
    n.add_argument("--manifest-digest")
    n.add_argument("--bytes", type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "split":
            result = split(
                args.work,
                args.shards,
                args.out,
                args.challenge,
                custody=args.custody,
                host_key=args.host_key,
                overlay=args.overlay,
            )
        elif args.command == "note":
            result = note(
                args.work,
                args.event,
                host_key=args.host_key,
                manifest_digest=args.manifest_digest,
                nbytes=args.bytes,
            )
        elif args.command == "merge":
            result = merge(args.work, args.shard, args.challenge, overlay=args.overlay)
        else:
            result = status(args.work)
    except ProducerRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["merge", "note", "require_custody", "split", "status"]
