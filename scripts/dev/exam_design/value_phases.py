"""Pod phases for EV4 and the Problem-C optimizer (dispatched by `runner.py`).

    python -m scripts.dev.exam_design.runner value_refs  --out DIR --config PLAN
    python -m scripts.dev.exam_design.runner value_panel --out DIR --config PLAN

* ``value_refs`` solves one shard of reference jobs with Carbon's own
  `TruthService` and `reference_solver` (the pinned PyBaMM of the battery
  overlay; `require_truth_runtime` refuses any other version). Jobs are the
  EV4 contract's decision cases (``"contract"``) or a committed jobs file
  (``"jobs_file"``, the optimizer's verification jobs). Every job ends as a
  typed record in ``records.jsonl`` (OK, REFERENCE_SOLVER_FAILED,
  REFERENCE_TIMEOUT or FAILED_INFRA); its case id and inputs are the job's, so
  `Experiment.import_references` and `optimizer.import_references` accept the
  file as it is (they never import FAILED_INFRA). Admission stops at
  ``stop_admitting_epoch``: a later job is typed FAILED_INFRA "not_admitted"
  and left for a later pod (``skip_case_keys`` resumes).
* ``value_panel`` reconstructs one shard of the contract's panel members with
  `DirectBackend` (JAX on the pod's GPU when JAX_PLATFORMS=cuda,cpu) and writes,
  per member: ``predictions/<member>.json.gz``, the exact bundle
  `Experiment.panel` writes (`experiment.member_bundle`), and
  ``grid/<member>.json.gz``, the member's predicted decision quantities on the
  optimizer's 1023 designs x 32 conditions. A member whose two files exist is
  skipped. A candidate's own reconstruction or prediction failure is typed in
  ``failures.jsonl`` and never retried as infrastructure.

Sharding is by position: shard i of n takes items i, i + n, i + 2n, ... of the
deterministic job (or member) order. Public synthetic DEVELOPMENT work only.
"""

from __future__ import annotations

import gzip
import json
import os
import threading
import time
from pathlib import Path


def shard(items, index, count):
    if not (type(index) is int and type(count) is int and 0 <= index < count):
        raise ValueError("shard index must be in [0, count)")
    return list(items)[index::count]


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=1, sort_keys=True))


def reference_jobs(cfg, repository="."):
    """The plan's jobs, in their deterministic order, before sharding."""
    if ("contract" in cfg) == ("jobs_file" in cfg):
        raise ValueError("a plan names exactly one of contract or jobs_file")
    if "contract" in cfg:
        from carbon.battery.value import contract as ev

        document, _ = ev.load(Path(repository) / cfg["contract"])
        return [
            {k: job[k] for k in ("case_id", "c1", "c2", "t_amb_c", "soc0")}
            for job in ev.decision_cases(document)
        ]
    jobs = json.loads((Path(repository) / cfg["jobs_file"]).read_text())["jobs"]
    return [
        {k: job[k] for k in ("case_id", "c1", "c2", "t_amb_c", "soc0")} for job in jobs
    ]


def admitted(solver, stop_at):
    """The solver, closed at `stop_at`: a job that starts after the admission
    window ends is typed FAILED_INFRA ("not_admitted"), never solved and never
    a reference. A resume pod solves it (`--skip-from` skips only OK cases).
    The truth service itself is unchanged."""

    def solve(job):
        if stop_at is not None and time.time() >= stop_at:
            return {"status": "FAILED_INFRA", "reason": "not_admitted"}
        return solver(job)

    return solve


def run_value_refs(cfg, out, *, solver=None, host=None):
    from carbon.battery.truth import (
        TRUTH_IMAGE,
        TruthService,
        lock_digest,
        reference_solver,
    )
    from scripts.dev.exam_design.runner import host_info, workers_for_host

    info = host() if host else host_info()
    _write_json(os.path.join(out, "host.json"), info)
    runtime = {"truth_image": TRUTH_IMAGE, "overlay_lock_digest": lock_digest(".")}
    if solver is None:
        from carbon.battery.truth_env import require_truth_runtime

        # Imports PyBaMM here, once, so every forked solve inherits it.
        runtime["pybamm"] = require_truth_runtime(".")
    _write_json(os.path.join(out, "runtime.json"), runtime)
    jobs = shard(reference_jobs(cfg), cfg.get("shard", 0), cfg.get("shards", 1))
    skip = set(cfg.get("skip_case_keys", []))
    jobs = [j for j in jobs if j["case_id"] not in skip]
    workers = workers_for_host(info, cfg.get("max_workers"))
    stop_at = float(cfg.get("stop_admitting_epoch", 0)) or None
    started = time.time()
    records = os.path.join(out, "records.jsonl")
    service = TruthService(
        records,
        solver=admitted(solver or reference_solver, stop_at),
        workers=workers,
        timeout_s=float(cfg.get("timeout_s", 1200)),
    )
    stop = threading.Event()

    def progress():
        while True:
            counts = {}
            if os.path.exists(records):
                for line in Path(records).read_text().splitlines():
                    if line.strip():
                        status = json.loads(line)["status"]
                        counts[status] = counts.get(status, 0) + 1
            _write_json(
                os.path.join(out, "progress.json"),
                {
                    "phase": "value_refs",
                    "workers": workers,
                    "total": len(jobs),
                    "done": counts,
                    "elapsed_s": round(time.time() - started, 1),
                },
            )
            if stop.wait(10):
                return

    reporter = threading.Thread(target=progress, daemon=True)
    reporter.start()
    try:
        summary = service.run(jobs)
    finally:
        stop.set()
        reporter.join()
    _write_json(
        os.path.join(out, "DONE.json"),
        {
            "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "summary": summary,
            "elapsed_s": time.time() - started,
        },
    )
    return 0


def _gzip_json(value):
    return gzip.compress(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode(), mtime=0
    )


def run_value_panel(cfg, out, *, backend=None):
    from carbon.battery.value import contract as ev
    from carbon.battery.value import optimizer as op
    from carbon.battery.value import panel as pn
    from carbon.battery.value.experiment import (
        bundle_bytes,
        member_bundle,
        panel_inputs,
    )
    from carbon.battery.worker import WorkerFailure
    from scripts.dev.exam_design.runner import host_info

    _write_json(os.path.join(out, "host.json"), host_info())
    if backend is None:
        import jax

        from carbon.battery.worker import DirectBackend

        _write_json(
            os.path.join(out, "backend.json"),
            {
                "jax_backend": jax.default_backend(),
                "devices": [str(d) for d in jax.devices()],
                "JAX_PLATFORMS": os.environ.get("JAX_PLATFORMS"),
                "XLA_FLAGS": os.environ.get("XLA_FLAGS"),
            },
        )
        backend = DirectBackend(".")
    contract, contract_digest = ev.load(Path(cfg["contract"]))
    members = shard(
        pn.members(contract["panel"]), cfg.get("shard", 0), cfg.get("shards", 1)
    )
    inputs = panel_inputs(contract, ".")
    predictions = Path(out) / "predictions"
    grid = Path(out) / "grid"
    predictions.mkdir(parents=True, exist_ok=True)
    grid.mkdir(parents=True, exist_ok=True)
    stop_at = float(cfg.get("stop_admitting_epoch", 0)) or None
    started = time.time()
    done = {"written": 0, "skipped": 0, "candidate_failures": 0, "not_admitted": 0}
    for index, (member, _label, strategy, seed) in enumerate(members):
        bundle_path = predictions / f"{member}.json.gz"
        grid_path = grid / f"{member}.json.gz"
        if bundle_path.exists() and grid_path.exists():
            done["skipped"] += 1
            continue
        if stop_at and time.time() >= stop_at:
            done["not_admitted"] = len(members) - index
            break
        try:
            bundle, state = member_bundle(backend, member, strategy, seed, inputs)
            if not bundle_path.exists():
                bundle_path.write_bytes(bundle_bytes(bundle))
            t0 = time.monotonic()
            quantities = op.grid_predictions(
                contract,
                lambda x, m=member, s=state: backend.infer(f"ev4-grid-{m}", s, x),
            )
            seconds = time.monotonic() - t0
        except WorkerFailure as failure:
            done["candidate_failures"] += 1
            with open(os.path.join(out, "failures.jsonl"), "a") as log:
                log.write(
                    json.dumps(
                        {"member": member, "failure": str(failure), "candidate": True}
                    )
                    + "\n"
                )
            continue
        document = op.grid_document(
            contract,
            member,
            bundle["recipe_digest"],
            seed,
            quantities,
            extra={
                "reconstruction": dict(backend.identity),
                "seconds": {"grid_prediction": seconds, **bundle["seconds"]},
            },
        )
        if document["contract_digest"] != contract_digest:
            raise RuntimeError("contract digest changed during the phase")
        grid_path.write_bytes(_gzip_json(document))
        done["written"] += 1
        _write_json(
            os.path.join(out, "progress.json"),
            {
                "phase": "value_panel",
                "total": len(members),
                "index": index + 1,
                "done": done,
                "elapsed_s": round(time.time() - started, 1),
            },
        )
    _write_json(
        os.path.join(out, "DONE.json"),
        {"done": done, "members": len(members), "elapsed_s": time.time() - started},
    )
    return 0
