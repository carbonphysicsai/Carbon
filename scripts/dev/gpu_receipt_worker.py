"""The standing GPU receipt worker (OWNER-GPU-OPEN-WITH-READY-01): the only writer of the on-box official receipt store.

For every served catalog entry with a GPU twin and no record in force in the store, it runs the entry's two official GPU
rebuilds (two SEPARATE `scripts/dev/gpu_repeat.py` containers in the pinned GPU worker image, as the validator box's own
runs do: `--gpus device=UUID --network none --read-only`, checkout read-only) and compares them with gpu_repeat's own
`compare`. A bit-identical pair appends a record to `carbon.backbone_catalog.receipt_store` (bundle digest, image id, host
class, determinism-flags digest, result, the two run digests); nothing is written to the repository.
A pair that differs is UNSTABLE (`non_reproducible`: a tolerance is the registered rebuild noise's, once the recalibration
registers it); other failures are FAILED with a typed reason. Each outcome is one line of `failures.jsonl` (owner-only) and
an entry gets at most `--max-attempts` attempts. A failed entry has no record, so it is never offered. The CNO1d twins
(SMOKE_ONLY) are SKIPPED: the official route refuses them.

- Low priority, yields: `os.nice(19)`. No lane starts, and running containers are frozen (`docker pause`), while the
  operator's `operator-pause.json` in `--operator-state-dir` pauses anything (an unreadable flag pauses everything) or
  official grading is running (chosen explicitly: `--grading-state-dir` for `official-grading.lock`, `--yield-file`,
  `--busy-command` or `--no-yield`). One GPU: it never competes with a grade.
- Lanes: min(free VRAM, CPUs, memory, cap) from the measured per-lane limits you pass (nothing defaulted).
- Resumes: the queue is a SQLite file in `--state-dir`; a restart (or reboot, via the `units` service) re-queues RUNNING jobs.
- Progress: "GPU receipts: <challenge> N of M ..." per Challenge, on every finish and on `status`.
- Start proof: every `run` prints and writes HEAD/TREE, images, queue, limits and lane plan.

    gpu_receipt_worker.py run --state-dir D --checkout C --gpu-uuid U --torch-gpu-manifest M [--jax-gpu-manifest M]
        --host-class ID --wheels W --store-dir S --max-attempts N --entry-timeout-s S --lane-vram-bytes B
        --lane-cpus N --lane-memory-bytes B --max-lanes N
        (--grading-state-dir V | --yield-file F | --busy-command CMD | --no-yield) [--operator-state-dir V] [--dry-run] [--only ID ...]
    gpu_receipt_worker.py status --state-dir D
    gpu_receipt_worker.py units  (same flags as run) --out-dir DIR      # a systemd --user service, not installed

Public data only; reads no sealed material. Records say where and on what they ran, never a score.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import hashlib
import io
import json
import os
import shlex
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

TWINS = {"torch-cu130-py311": "torch", "jax-cuda13-py311": "jax"}
STATUSES = ("QUEUED", "RUNNING", "PASS", "UNSTABLE", "FAILED", "SKIPPED")
DONE = ("PASS", "UNSTABLE", "FAILED", "SKIPPED")
SCHEMA_PROOF = "carbon.gpu-receipt-worker.start-proof.v1"

_DDL = """
CREATE TABLE IF NOT EXISTS jobs(
    key TEXT PRIMARY KEY,
    catalog_id TEXT NOT NULL,
    runtime TEXT NOT NULL,
    bundle_digest TEXT NOT NULL DEFAULT '',
    challenges TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('QUEUED','RUNNING','PASS','UNSTABLE','FAILED','SKIPPED')),
    attempts INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    updated REAL NOT NULL
);
"""


# --- what is served and what needs a receipt -------------------------------------------------------------------------


def served_jobs(*, entries=None, versions=None):
    """[{key, catalog_id, runtime, challenges}] for every served entry with a GPU twin.

    Served = offered on an IMPLEMENTED Challenge version (`registry.entries()`), through the catalog's own listing (the
    cross-version rule included). `entries` / `versions` are test seams."""
    from carbon.backbone_catalog import listing
    from carbon.challenge_registry import registry

    if versions is None:
        versions = [
            (e.challenge_id, e.version)
            for e in registry.entries()
            if e.status == registry.IMPLEMENTED
        ]
    seen = {}
    for challenge_id, version in versions:
        offered = (
            listing.entries(challenge_id, version)
            if entries is None
            else [
                e
                for e in entries
                if any(c["id"] == challenge_id for c in e["challenges"])
            ]
        )
        for item in offered:
            for runtime in sorted(item.get("bundle_refs") or {}):
                if runtime not in TWINS:
                    continue
                key = f"{item['catalog_id']}|{runtime}"
                job = seen.setdefault(
                    key,
                    {
                        "key": key,
                        "catalog_id": item["catalog_id"],
                        "runtime": runtime,
                        "bundle_digest": item["bundle_refs"][runtime]["bundle_digest"],
                        "challenges": set(),
                    },
                )
                job["challenges"].add(challenge_id)
    return [
        {**job, "challenges": sorted(job["challenges"])}
        for job in sorted(seen.values(), key=lambda j: j["key"])
    ]


def record_is_done(store, job, image_id, host_class):
    """Whether the store already holds this entry's official record on this image and host class (a refused store is
    an error, never a yes)."""
    from carbon.backbone_catalog import gpu_receipt

    record = store.current(job["bundle_digest"], job["runtime"])
    return (
        record is not None
        and record["catalog_id"] == job["catalog_id"]
        and record["image_id"] == image_id
        and record["host_class"] == host_class
        and record["determinism_flags_digest"]
        == gpu_receipt.required_determinism_digest(job["runtime"])
    )


# --- the queue -----------------------------------------------------------------------------------------------------


class Queue:
    """The standing queue, in one SQLite file (restart-safe)."""

    def __init__(self, path, *, clock=time.time):
        self.path, self.clock = path, clock
        self.db = sqlite3.connect(str(path) if path != ":memory:" else ":memory:")
        self.db.executescript(_DDL)

    def sync(self, jobs, *, skipped=None, adopted=None):
        """Add jobs not yet known; `skipped` {key: reason} and `adopted` {key: reason} are final at once."""
        skipped, adopted = skipped or {}, adopted or {}
        for job in jobs:
            known = self.db.execute(
                "SELECT status FROM jobs WHERE key=?", (job["key"],)
            ).fetchone()
            if known is not None:
                continue
            status, reason = "QUEUED", ""
            if job["key"] in skipped:
                status, reason = "SKIPPED", skipped[job["key"]]
            elif job["key"] in adopted:
                status, reason = "PASS", adopted[job["key"]]
            self.db.execute(
                "INSERT INTO jobs(key, catalog_id, runtime, bundle_digest, challenges, status, reason, updated) VALUES(?,?,?,?,?,?,?,?)",
                (
                    job["key"],
                    job["catalog_id"],
                    job["runtime"],
                    job["bundle_digest"],
                    json.dumps(job["challenges"]),
                    status,
                    reason,
                    self.clock(),
                ),
            )
        self.db.commit()

    def recover(self):
        """After a restart: a job left RUNNING is queued again (its attempt stays counted)."""
        cursor = self.db.execute(
            "UPDATE jobs SET status='QUEUED', reason='restarted', updated=? WHERE status='RUNNING'",
            (self.clock(),),
        )
        self.db.commit()
        return cursor.rowcount

    def exhaust(self, max_attempts):
        """A queued job that has used every attempt is FAILED, never retried again."""
        self.db.execute(
            "UPDATE jobs SET status='FAILED', reason='max_attempts_exhausted', updated=? "
            "WHERE status='QUEUED' AND attempts>=?",
            (self.clock(), max_attempts),
        )
        self.db.commit()

    def claim(self, only=None):
        row = self.db.execute(
            "SELECT key, catalog_id, runtime, bundle_digest, challenges, attempts FROM jobs WHERE status='QUEUED' ORDER BY attempts, key"
        ).fetchall()
        for key, catalog_id, runtime, bundle_digest, challenges, attempts in row:
            if only and catalog_id not in only:
                continue
            self.db.execute(
                "UPDATE jobs SET status='RUNNING', attempts=attempts+1, updated=? WHERE key=?",
                (self.clock(), key),
            )
            self.db.commit()
            return {
                "key": key,
                "catalog_id": catalog_id,
                "runtime": runtime,
                "bundle_digest": bundle_digest,
                "challenges": json.loads(challenges),
                "attempt": attempts + 1,
            }
        return None

    def finish(self, key, status, reason="", detail=""):
        assert status in STATUSES
        self.db.execute(
            "UPDATE jobs SET status=?, reason=?, detail=?, updated=? WHERE key=?",
            (status, reason, detail[:500], self.clock(), key),
        )
        self.db.commit()

    def requeue(self, key, reason):
        """An attempt that failed with attempts left goes back to the queue with its reason."""
        self.db.execute(
            "UPDATE jobs SET status='QUEUED', reason=?, updated=? WHERE key=?",
            (reason, self.clock(), key),
        )
        self.db.commit()

    def counts(self):
        out = {s: 0 for s in STATUSES}
        for status, count in self.db.execute(
            "SELECT status, COUNT(*) FROM jobs GROUP BY status"
        ):
            out[status] = count
        return out

    def per_challenge(self):
        """{challenge: {"total", "PASS", ...}}; a job counts under every Challenge it serves. SKIPPED jobs are
        not part of the total (they are CPU-rebuilt, not waiting for a receipt)."""
        out = {}
        for challenges, status in self.db.execute(
            "SELECT challenges, status FROM jobs"
        ):
            if status == "SKIPPED":
                continue
            for challenge in json.loads(challenges):
                row = out.setdefault(
                    challenge, {"total": 0, **{s: 0 for s in STATUSES}}
                )
                row["total"] += 1
                row[status] += 1
        return out

    def failures(self):
        return [
            {"key": k, "status": s, "reason": r, "detail": d}
            for k, s, r, d in self.db.execute(
                "SELECT key, status, reason, detail FROM jobs WHERE status IN ('FAILED','UNSTABLE') ORDER BY key"
            )
        ]


def progress_line(queue):
    """The owner's daily line: N of M per Challenge, and what is not passing."""
    parts = []
    for challenge, row in sorted(queue.per_challenge().items()):
        parts.append(f"{challenge} {row['PASS']} of {row['total']}")
    counts = queue.counts()
    return (
        "GPU receipts: "
        + ("; ".join(parts) or "nothing queued")
        + f" (running {counts['RUNNING']}, queued {counts['QUEUED']}, UNSTABLE {counts['UNSTABLE']}, FAILED {counts['FAILED']})"
    )


# --- lanes, yielding ----------------------------------------------------------------------------------------------


def plan_lanes(
    *, free_vram, lane_vram, cpus, lane_cpus, memory_available, lane_memory, max_lanes
):
    """How many rebuild lanes may run at once: the smallest of what VRAM, CPUs, memory and the cap allow (never negative;
    zero when a limit is not met even once)."""
    for name, value in (
        ("lane_vram", lane_vram),
        ("lane_cpus", lane_cpus),
        ("lane_memory", lane_memory),
    ):
        if type(value) is not int or value < 1:
            raise ValueError(
                f"{name} is a positive integer you supply (the measured per-lane figure)"
            )
    return max(
        0,
        min(
            max_lanes,
            free_vram // lane_vram,
            cpus // lane_cpus,
            memory_available // lane_memory,
        ),
    )


def make_busy(
    *,
    grading_state_dir=None,
    yield_file=None,
    busy_command=None,
    no_yield=False,
    operator_state_dir=None,
    run=subprocess.run,
    grading_busy=None,
):
    """`busy()`: whether the worker must not use the GPU now: the operator pause flag (`operator-pause.json` in the
    validator state: any pause, or a flag that cannot be read, holds everything), or official grading running.

    Grading is detected one way, chosen explicitly (never by omission): the validator state's `official-grading.lock`
    (`receipt_job.grading_busy`), a yield file, a busy command (exit 0 = busy), or `no_yield` (tests, scratch boxes).
    """
    chosen = [
        x for x in (grading_state_dir, yield_file, busy_command, no_yield or None) if x
    ]
    if len(chosen) != 1:
        raise ValueError(
            "choose exactly one of --grading-state-dir, --yield-file, --busy-command and --no-yield"
        )
    if grading_state_dir:
        if grading_busy is None:
            from carbon.backbone_catalog.receipt_job import grading_busy

        def grading():
            return grading_busy(grading_state_dir)

    elif yield_file:

        def grading():
            return Path(yield_file).exists()

    elif busy_command:

        def grading():
            return (
                run(
                    busy_command, shell=True, capture_output=True, check=False
                ).returncode
                == 0
            )

    else:

        def grading():
            return False

    def busy():
        if operator_state_dir is not None:
            from carbon.challenge_validator import operator_pause

            if any(operator_pause.read(operator_state_dir).values()):
                return True
        return grading()

    return busy


# --- one entry's two official GPU rebuilds -------------------------------------------------------------------------


@dataclass
class Context:
    checkout: Path
    state_dir: Path
    gpu_uuid: str
    images: dict  # runtime -> image id (sha256:...)
    wheels: Path
    store: object
    host_class: str
    tested_on: str
    entry_timeout_s: int
    steps: int = 20
    run: object = field(default=subprocess.run, repr=False)


def docker_argv(ctx, runtime, catalog_id, run_name, out_dir, scratch):
    """The container run of ONE rebuild, as the validator box's own gpu_repeat runs do it (checkout and wheels read-only,
    no network, a read-only root with scratch volumes). Creates no image and no tag."""
    framework = TWINS[runtime]
    image = ctx.images[runtime]
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        run_name,
        "--gpus",
        f"device={ctx.gpu_uuid}",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,size=8g",
        "-v",
        f"{ctx.checkout}:/work:ro",
        "-v",
        f"{out_dir}:/out:rw",
        "-v",
        f"{scratch}:/scratch:rw",
        "-v",
        f"{ctx.wheels}:/wheels:ro",
        "-e",
        "PYTHONPATH=/work",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        "JAX_PLATFORMS=cuda",
        "--workdir",
        "/work",
        "--entrypoint",
        "/opt/carbon-worker/bin/python",
        image,
        "scripts/dev/gpu_repeat.py",
        "/work",
        f"/out/{run_name}.json",
        catalog_id,
        "--framework",
        framework,
        "--wheels",
        "/wheels",
        "--steps",
        str(ctx.steps),
    ]


def run_name_of(job, n):
    digest = hashlib.sha256(job["key"].encode()).hexdigest()[:10]
    return f"carbon-gpurcpt-{digest}-r{n}"


def compare_runs(first, second):
    """gpu_repeat's own compare on two run files -> verdict for the entry ('PASS', 'DIFFER' or 'NOT_OK: ...')."""
    from scripts.dev import gpu_repeat

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        gpu_repeat.compare(str(first), str(second))
    verdict = json.loads(captured.getvalue())
    if "error" in verdict:
        return "NOT_OK: " + verdict["error"]
    (only,) = verdict.values()
    return only


def run_digest(first):
    """The digest of what must repeat bit for bit in one run (gpu_repeat's own `stable`), canonical JSON."""
    from carbon.backbone_catalog import receipt_store
    from scripts.dev import gpu_repeat

    return receipt_store.digest(receipt_store.canonical(gpu_repeat.stable(first)))


def official_pair(ctx, job):
    """Run the entry's two rebuilds in two separate containers and compare. Returns
    {"verdict": "PASS"|"UNSTABLE"|"FAILED", "reason", "detail", "peak_gpu_bytes"}."""
    root = ctx.state_dir / "runs" / hashlib.sha256(job["key"].encode()).hexdigest()[:16]
    out_dir, scratch = root / "out", root / "scratch"
    for directory in (out_dir, scratch / "tmp", scratch / "cache"):
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o777)
    for stale in out_dir.glob("*.json"):
        stale.unlink()
    peak = 0
    digests = []
    for n in (1, 2):
        name = run_name_of(job, n)
        try:
            done = ctx.run(
                docker_argv(
                    ctx, job["runtime"], job["catalog_id"], name, out_dir, scratch
                ),
                capture_output=True,
                text=True,
                timeout=ctx.entry_timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            ctx.run(["docker", "rm", "-f", name], capture_output=True, check=False)
            return {
                "verdict": "FAILED",
                "reason": "timeout",
                "detail": f"run {n} over {ctx.entry_timeout_s} s",
                "peak_gpu_bytes": peak,
            }
        if done.returncode != 0 or not (out_dir / f"{name}.json").is_file():
            return {
                "verdict": "FAILED",
                "reason": "worker_exit",
                "detail": f"run {n} rc={done.returncode}: {(done.stderr or '')[-300:]}",
                "peak_gpu_bytes": peak,
            }
        document = json.loads((out_dir / f"{name}.json").read_bytes())
        entry = (document.get("entries") or {}).get(job["catalog_id"]) or {}
        peak = max(peak, int((entry.get("first") or {}).get("peak_gpu_bytes", 0)))
        digests.append(run_digest(entry.get("first") or {}))
    verdict = compare_runs(
        out_dir / (run_name_of(job, 1) + ".json"),
        out_dir / (run_name_of(job, 2) + ".json"),
    )
    return {**_classify(verdict, peak), "run_digests": digests}


def _classify(verdict, peak):
    if verdict == "PASS":
        return {
            "verdict": "PASS",
            "reason": "bit_identical",
            "detail": "",
            "peak_gpu_bytes": peak,
        }
    if verdict == "DIFFER":
        return {
            "verdict": "UNSTABLE",
            "reason": "non_reproducible",
            "detail": "the two rebuilds did not match bit for bit; a tolerance is the registered tolerance's, not this worker's",
            "peak_gpu_bytes": peak,
        }
    return {
        "verdict": "FAILED",
        "reason": "not_ok",
        "detail": verdict[:300],
        "peak_gpu_bytes": peak,
    }


def make_record(ctx, job, result):
    """The official record of a bit-identical pair (`receipt_store`'s own schema): the entry's bundle digest, the pinned
    GPU image, the registered host class, the determinism-flags digest and the two run digests.
    """
    from carbon.backbone_catalog import gpu_receipt, receipt_store

    return {
        "schema": receipt_store.SCHEMA,
        "catalog_id": job["catalog_id"],
        "runtime_profile_id": job["runtime"],
        "bundle_digest": job["bundle_digest"],
        "image_id": ctx.images[job["runtime"]],
        "host_class": ctx.host_class,
        "determinism_flags_digest": gpu_receipt.required_determinism_digest(
            job["runtime"]
        ),
        "result": {"kind": receipt_store.BIT_IDENTICAL},
        "run_digests": list(result["run_digests"]),
        "supersedes": None,
    }


def write_record(ctx, job, result):
    """Append the record to the on-box store (the worker is its only writer). Returns the record digest."""
    return ctx.store.append(make_record(ctx, job, result))


FAILURE_LOG = "failures.jsonl"


def log_failure(ctx, job, status, reason, detail):
    """One typed line per FAILED / UNSTABLE entry, append-only, owner-only, no addresses. A failed entry is never
    offered: it has no store record."""
    ctx.state_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "catalog_id": job["catalog_id"],
            "runtime": job["runtime"],
            "bundle_digest": job["bundle_digest"],
            "status": status,
            "reason": reason,
            "detail": (detail or "")[:300],
            "attempt": job.get("attempt"),
        },
        sort_keys=True,
    )
    fd = os.open(
        ctx.state_dir / FAILURE_LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
    )
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        stream.write(line + "\n")


# --- the loop ---------------------------------------------------------------------------------------------------


def run_loop(
    queue,
    ctx,
    *,
    max_attempts,
    only=None,
    lanes_now,
    busy,
    executor=official_pair,
    receipt_writer=write_record,
    pauser=None,
    nice=19,
    sleep=time.sleep,
    poll_s=5.0,
    out=print,
):
    """Run the queue to the end: claim jobs while lanes are free and official grading is not busy, finish them, print
    progress. Never retries a job beyond `max_attempts`. Returns the final counts."""
    if hasattr(os, "nice"):
        os.nice(nice)  # the standing job never competes with grading for the CPU
    queue.recover()
    queue.exhaust(max_attempts)
    running = {}
    paused = False
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=64)
    try:
        while True:
            queue.exhaust(max_attempts)
            held = busy()
            if pauser is not None and held != paused:
                pauser([running[f] for f in running], held)  # freeze/thaw containers
                paused = held
            if not held:
                allowed = lanes_now() - len(running)
                for _ in range(max(0, allowed)):
                    job = queue.claim(only)
                    if job is None:
                        break
                    out(f"start {job['key']} attempt {job['attempt']}")
                    running[pool.submit(executor, ctx, job)] = job
            if not running:
                if held and queue.counts()["QUEUED"]:
                    sleep(poll_s)
                    continue
                break
            finished, _ = concurrent.futures.wait(
                running, timeout=poll_s, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in finished:
                job = running.pop(future)
                try:
                    result = future.result()
                # a crashed attempt is a result, never a stop
                except Exception as error:  # noqa: BLE001
                    result = {
                        "verdict": "FAILED",
                        "reason": "worker_crash",
                        "detail": f"{type(error).__name__}: {error}"[:300],
                    }
                _settle(queue, job, result, ctx, receipt_writer, max_attempts, out)
                out(progress_line(queue))
    finally:
        pool.shutdown(wait=True)
    return queue.counts()


def docker_pauser(run=subprocess.run):
    """Freeze (`docker pause`) or thaw the containers of the running entries; either container of a pair may be live."""

    def pause(jobs, paused):
        for job in jobs:
            for n in (1, 2):
                run(
                    ["docker", "pause" if paused else "unpause", run_name_of(job, n)],
                    capture_output=True,
                    check=False,
                )

    return pause


def _settle(queue, job, result, ctx, receipt_writer, max_attempts, out):
    verdict = result["verdict"]
    if verdict == "PASS":
        try:
            path = receipt_writer(ctx, job, result)
        except Exception as error:  # noqa: BLE001
            queue.finish(
                job["key"],
                "FAILED",
                "receipt_not_written",
                f"{type(error).__name__}: {error}",
            )
            log_failure(
                ctx, job, "FAILED", "receipt_not_written", f"{type(error).__name__}"
            )
            out(f"FAILED {job['key']}: receipt_not_written")
            return
        queue.finish(job["key"], "PASS", "bit_identical", str(path))
        out(f"PASS {job['key']} -> {str(path)[:19]}")
    elif verdict == "UNSTABLE":
        queue.finish(job["key"], "UNSTABLE", result["reason"], result.get("detail", ""))
        log_failure(ctx, job, "UNSTABLE", result["reason"], result.get("detail", ""))
        out(f"UNSTABLE {job['key']}: {result['reason']}")
    elif job["attempt"] >= max_attempts:
        queue.finish(job["key"], "FAILED", result["reason"], result.get("detail", ""))
        log_failure(ctx, job, "FAILED", result["reason"], result.get("detail", ""))
        out(f"FAILED {job['key']}: {result['reason']}")
    else:
        queue.requeue(job["key"], result["reason"])
        out(
            f"retry {job['key']} (attempt {job['attempt']} of {max_attempts}): {result['reason']}"
        )


# --- host facts ----------------------------------------------------------------------------------------------------


def gpu_facts(uuid, *, run=subprocess.run):
    """(free VRAM bytes, 'name / driver') from nvidia-smi for the device."""
    done = run(
        [
            "nvidia-smi",
            f"--id={uuid}",
            "--query-gpu=memory.free,name,driver_version",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0 or not done.stdout.strip():
        raise RuntimeError(
            "nvidia-smi could not read the GPU: " + (done.stderr or "").strip()[:200]
        )
    free, name, driver = (
        part.strip() for part in done.stdout.strip().splitlines()[0].split(",")
    )
    return int(float(free)) * 1024 * 1024, f"{name} / {driver}"


def host_memory_available():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("MemAvailable is not readable")


def git_identity(checkout, *, run=subprocess.run):
    def one(*args):
        return run(
            ["git", "-C", str(checkout), *args],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()

    return {"head": one("rev-parse", "HEAD"), "tree": one("rev-parse", "HEAD^{tree}")}


# --- the command line -----------------------------------------------------------------------------------------------


def _parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("run", "status", "units"))
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--checkout", type=Path)
    parser.add_argument("--gpu-uuid")
    parser.add_argument("--torch-gpu-manifest", type=Path)
    parser.add_argument("--jax-gpu-manifest", type=Path)
    parser.add_argument("--host-class")
    parser.add_argument("--wheels", type=Path)
    parser.add_argument("--store-dir", type=Path)
    parser.add_argument("--grading-state-dir", type=Path)
    parser.add_argument("--operator-state-dir", type=Path)
    parser.add_argument("--max-attempts", type=int)
    parser.add_argument("--entry-timeout-s", type=int)
    parser.add_argument("--lane-vram-bytes", type=int)
    parser.add_argument("--lane-cpus", type=int)
    parser.add_argument("--lane-memory-bytes", type=int)
    parser.add_argument("--max-lanes", type=int)
    parser.add_argument("--yield-file")
    parser.add_argument("--busy-command")
    parser.add_argument("--no-yield", action="store_true")
    parser.add_argument("--poll-s", type=float, default=5.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--out-dir", type=Path)
    return parser


REQUIRED_RUN = (
    "checkout",
    "gpu_uuid",
    "host_class",
    "wheels",
    "store_dir",
    "operator_state_dir",
    "max_attempts",
    "entry_timeout_s",
    "lane_vram_bytes",
    "lane_cpus",
    "lane_memory_bytes",
    "max_lanes",
)


def image_ids(args):
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    images = {}
    for runtime, path in (
        ("torch-cu130-py311", args.torch_gpu_manifest),
        ("jax-cuda13-py311", args.jax_gpu_manifest),
    ):
        if path is not None:
            images[runtime] = load_image_identity(Path(path)).image_id
    return images


def build_queue(args, queue, *, jobs=None):
    """Fill the queue: served GPU entries, minus the smoke-only ones (CPU lane), minus those whose receipt is already
    on disk for this host class, minus those whose runtime has no recorded GPU image."""
    from carbon.backbone_catalog import gpu_receipt
    from carbon.backbone_catalog.receipt_store import ReceiptStore

    jobs = served_jobs() if jobs is None else jobs
    images = image_ids(args)
    skipped, adopted = {}, {}
    for job in jobs:
        if job["catalog_id"] in gpu_receipt.SMOKE_ONLY:
            skipped[job["key"]] = "smoke_only_cpu_rebuild_lane"
        elif job["runtime"] not in images:
            skipped[job["key"]] = "no_gpu_image_recorded_for_runtime"
        else:
            if record_is_done(
                ReceiptStore(args.store_dir),
                job,
                images[job["runtime"]],
                args.host_class,
            ):
                adopted[job["key"]] = "record_already_in_store"
    queue.sync(jobs, skipped=skipped, adopted=adopted)
    return images


def main(argv=None):
    args = _parser().parse_args(argv)
    args.state_dir.mkdir(parents=True, exist_ok=True)
    if args.command == "status":
        queue = Queue(args.state_dir / "queue.sqlite3")
        print(progress_line(queue))
        for row in queue.failures():
            print(json.dumps(row, sort_keys=True))
        return 0
    missing = [name for name in REQUIRED_RUN if getattr(args, name) in (None, "")]
    if missing:
        print(
            "missing: " + ", ".join("--" + m.replace("_", "-") for m in missing),
            file=sys.stderr,
        )
        return 2
    try:
        busy = make_busy(
            grading_state_dir=args.grading_state_dir,
            yield_file=args.yield_file,
            busy_command=args.busy_command,
            no_yield=args.no_yield,
            operator_state_dir=args.operator_state_dir,
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    from carbon.backbone_catalog import gpu_receipt

    if args.host_class not in gpu_receipt.REGISTERED_HOST_CLASSES:
        print(
            f"host class {args.host_class!r} is not registered (gpu_receipt.REGISTERED_HOST_CLASSES)",
            file=sys.stderr,
        )
        return 2
    if args.command == "units":
        return _units(args)
    from carbon.backbone_catalog.receipt_store import ReceiptStore

    queue = Queue(":memory:" if args.dry_run else args.state_dir / "queue.sqlite3")
    images = build_queue(args, queue)
    _, tested_on = gpu_facts(args.gpu_uuid)
    ctx = Context(
        checkout=args.checkout.resolve(),
        state_dir=args.state_dir,
        gpu_uuid=args.gpu_uuid,
        images=images,
        wheels=args.wheels,
        store=ReceiptStore(args.store_dir),
        host_class=args.host_class,
        tested_on=tested_on,
        entry_timeout_s=args.entry_timeout_s,
    )
    lane_vram = args.lane_vram_bytes

    def lanes_now():
        nonlocal lane_vram
        free, _ = gpu_facts(args.gpu_uuid)
        return plan_lanes(
            free_vram=free,
            lane_vram=lane_vram,
            cpus=os.cpu_count() or 1,
            lane_cpus=args.lane_cpus,
            memory_available=host_memory_available(),
            lane_memory=args.lane_memory_bytes,
            max_lanes=args.max_lanes,
        )

    proof = {
        "schema": SCHEMA_PROOF,
        "checkout": git_identity(ctx.checkout),
        "images": images,
        "host_class": args.host_class,
        "tested_on": tested_on,
        "queue": queue.counts(),
        "progress": progress_line(queue),
        "lanes_at_start": lanes_now(),
        "dry_run": bool(args.dry_run),
        "limits": {
            "max_attempts": args.max_attempts,
            "entry_timeout_s": args.entry_timeout_s,
            "lane_vram_bytes": args.lane_vram_bytes,
            "lane_cpus": args.lane_cpus,
            "lane_memory_bytes": args.lane_memory_bytes,
            "max_lanes": args.max_lanes,
        },
    }
    print(json.dumps(proof, indent=1, sort_keys=True))
    if args.dry_run:
        first = queue.claim(args.only)
        if first is not None:
            scratch = args.state_dir / "runs" / "<key>" / "scratch"
            out_dir = args.state_dir / "runs" / "<key>" / "out"
            for n in (1, 2):
                print(
                    shlex.join(
                        docker_argv(
                            ctx,
                            first["runtime"],
                            first["catalog_id"],
                            run_name_of(first, n),
                            out_dir,
                            scratch,
                        )
                    )
                )
        return 0
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    (args.state_dir / f"start-proof-{stamp}.json").write_text(
        json.dumps(proof, indent=1, sort_keys=True)
    )
    counts = run_loop(
        queue,
        ctx,
        max_attempts=args.max_attempts,
        only=set(args.only) if args.only else None,
        lanes_now=lanes_now,
        busy=busy,
        pauser=docker_pauser(),
        poll_s=args.poll_s,
    )
    print(json.dumps(counts, sort_keys=True))
    return 0 if not counts["FAILED"] and not counts["UNSTABLE"] else 1


def _units(args):
    """A systemd --user service for the standing job (not installed): it restarts on failure and starts at login/boot (with
    linger), and the queue resumes from its state file."""
    if args.out_dir is None:
        print("units needs --out-dir", file=sys.stderr)
        return 2
    flags = []
    for name in (
        "state_dir",
        "checkout",
        "gpu_uuid",
        "torch_gpu_manifest",
        "jax_gpu_manifest",
        "host_class",
        "wheels",
        "store_dir",
        "max_attempts",
        "entry_timeout_s",
        "lane_vram_bytes",
        "lane_cpus",
        "lane_memory_bytes",
        "max_lanes",
        "grading_state_dir",
        "operator_state_dir",
        "yield_file",
        "busy_command",
    ):
        value = getattr(args, name)
        if value not in (None, ""):
            flags += ["--" + name.replace("_", "-"), str(value)]
    if args.no_yield:
        flags.append("--no-yield")
    command = shlex.join(
        [sys.executable, "-B", str(Path(__file__).resolve()), "run", *flags]
    )
    text = (
        "[Unit]\nDescription=Carbon GPU receipt worker (standing job; yields to official grading)\n\n"
        f"[Service]\nType=simple\nWorkingDirectory={args.checkout}\nEnvironment=PYTHONDONTWRITEBYTECODE=1\n"
        f"ExecStart={command}\nRestart=on-failure\nRestartSec=30\n\n[Install]\nWantedBy=default.target\n"
    )
    args.out_dir.mkdir(mode=0o700)
    (args.out_dir / "carbon-gpu-receipt-worker.service").write_text(
        text, encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {"written": ["carbon-gpu-receipt-worker.service"], "installed": False}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
