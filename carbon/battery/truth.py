"""The battery truth service: pinned reference solves with typed failures.

WRAPS the exam-design pod runner's per-case pattern
(`scripts/dev/exam_design/runner.py`): one forked child per case, a wall-clock
deadline, a memory bound and resume from the records file. Every case ends in
exactly one typed status:

- ``OK``: a complete reference; the only status that may enter an exam;
- ``REFERENCE_SOLVER_FAILED``: the solver raised, or did not finish every
  cycle;
- ``REFERENCE_TIMEOUT``: the per-case wall-clock limit expired;
- ``FAILED_INFRA``: the worker died, or hit the memory bound. This is never a
  scientific result, and it is retried on resume.

A reference failure is never a candidate failure: the exam types such a case
``REFERENCE_INVALID`` and withdraws it for every model.

The solves run in the truth image pinned by `TRUTH_IMAGE`: the campaign's
study image plus its hash-locked PyBaMM overlay. Security review of that image
is OD-3. This module never installs anything.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import resource
import time
from pathlib import Path

OK = "OK"
SOLVER_FAILED = "REFERENCE_SOLVER_FAILED"
TIMEOUT = "REFERENCE_TIMEOUT"
FAILED_INFRA = "FAILED_INFRA"
TERMINAL = frozenset({OK, SOLVER_FAILED, TIMEOUT})

LOCK_PATH = "scripts/dev/exam_design/locks/battery-overlay.lock.json"
#: The truth image: base image digest and the overlay lock's exact bytes.
TRUTH_IMAGE = {
    "base_image": (
        "ghcr.io/carbonphysicsai/carbon-determinism-study@sha256:"
        "2d19b261e722fe67f20bee02e115f2277a799c448b90d54d2872361b341bd940"
    ),
    "overlay_lock": LOCK_PATH,
    "root_requirement": "pybamm==26.8.0.0",
}
MAIN_CYCLES, CHECKPOINTS = 30, (1, 10, 20, 30)


def lock_digest(root="."):
    return "sha256:" + hashlib.sha256((Path(root) / LOCK_PATH).read_bytes()).hexdigest()


def reference_solver(job):
    """The pinned PyBaMM solve of one job (runs inside the truth image)."""
    from . import reference

    case = reference.BatteryCase(
        job["case_id"], job["c1"], job["c2"], job["t_amb_c"], job["soc0"]
    )
    return reference.solve_case(
        case, MAIN_CYCLES, list(CHECKPOINTS), refined=job.get("refined", False)
    )


def _address_space():
    """This process's current virtual size in bytes (Linux)."""
    import os

    pages = int(Path("/proc/self/statm").read_text().split()[0])
    return pages * os.sysconf("SC_PAGE_SIZE")


def _child(solver, job, memory_bytes, queue):
    if memory_bytes:
        # The bound is what the solve may add to the forked worker's size.
        limit = _address_space() + memory_bytes
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    try:
        record = solver(job)
    except MemoryError:
        record = {"status": FAILED_INFRA, "reason": "memory_bound"}
    except Exception as exc:  # noqa: BLE001 - a solver failure is typed
        record = {"status": SOLVER_FAILED, "error": type(exc).__name__}
    if record.get("status") == SOLVER_FAILED and str(
        record.get("error", "")
    ).startswith("MemoryError"):
        # The pinned solve catches everything; a memory bound is still infra.
        record = {"status": FAILED_INFRA, "reason": "memory_bound"}
    record["peak_rss_kb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    queue.put(record)


class TruthService:
    """Solve jobs into an append-only records file, resumably."""

    def __init__(
        self,
        records_path,
        *,
        solver=reference_solver,
        timeout_s=1200.0,
        memory_bytes=2 * 1024**3,
        workers=1,
    ):
        self.path = Path(records_path)
        self.solver, self.timeout_s = solver, float(timeout_s)
        self.memory_bytes, self.workers = memory_bytes, max(1, int(workers))

    def records(self):
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def completed(self):
        """Case keys with a terminal record. FAILED_INFRA is retried."""
        return {_key(r) for r in self.records() if r.get("status") in TERMINAL}

    def run(self, jobs):
        """Solve every job without a terminal record. Returns what it did."""
        done = self.completed()
        pending = [j for j in jobs if _key(j) not in done]
        counts = {s: 0 for s in (*sorted(TERMINAL), FAILED_INFRA)}
        ctx = mp.get_context("fork")
        running = {}
        with self.path.open("a") as out:

            def write(record):
                out.write(json.dumps(record, sort_keys=True) + "\n")
                out.flush()
                counts[record["status"]] += 1

            while pending or running:
                while pending and len(running) < self.workers:
                    job = pending.pop(0)
                    queue = ctx.Queue()
                    process = ctx.Process(
                        target=_child, args=(self.solver, job, self.memory_bytes, queue)
                    )
                    process.start()
                    running[process.pid] = (process, queue, job, time.monotonic())
                for pid, (process, queue, job, start) in list(running.items()):
                    base = {
                        "case_id": job["case_id"],
                        "refined": job.get("refined", False),
                        "inputs": {k: job[k] for k in ("c1", "c2", "t_amb_c", "soc0")},
                    }
                    record = None
                    try:
                        record = queue.get_nowait()
                    except Exception:  # noqa: BLE001, S110 - not ready yet
                        pass
                    if record is not None:
                        process.join(5)
                        write({**base, **record, "wall_s": time.monotonic() - start})
                    elif time.monotonic() - start > self.timeout_s:
                        process.kill()
                        process.join(5)
                        write({**base, "status": TIMEOUT})
                    elif not process.is_alive():
                        try:
                            record = queue.get(timeout=1)
                            write({**base, **record})
                        except Exception:  # noqa: BLE001 - the worker died
                            write(
                                {
                                    **base,
                                    "status": FAILED_INFRA,
                                    "reason": "worker_exit",
                                    "exitcode": process.exitcode,
                                }
                            )
                    else:
                        continue
                    del running[pid]
                time.sleep(0.02)
        return {
            "jobs": len(jobs),
            "skipped_completed": len(jobs)
            - len([j for j in jobs if _key(j) not in done]),
            "counts": counts,
        }


def _key(record):
    return record["case_id"] + ("/R" if record.get("refined") else "")
