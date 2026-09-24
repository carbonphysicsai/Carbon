"""Phase runner for the exam-design campaign (runs on the pod or locally).

    python -m scripts.dev.exam_design.runner <phase> --out DIR  [config in PHASE_CONFIG or --config FILE]

Phases:

* ``battery_refs`` - solve a list of battery reference jobs in parallel worker
  processes, one process per case, each under a hard wall limit. Every job ends
  as a typed record in ``records.jsonl``: ``OK``, ``REFERENCE_SOLVER_FAILED``,
  ``REFERENCE_TIMEOUT`` or ``FAILED_INFRA``. Admission stops at the config's
  ``stop_admitting_epoch`` so the pod can export before its deadline.
* ``host`` - record host identity only.

Progress is rewritten to ``progress.json`` so the status page can report it.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import platform
import resource
import sys
import time


def host_info() -> dict:
    info = {"python": sys.version.split()[0], "platform": platform.platform(), "cpu_count": os.cpu_count(),
            "affinity": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None}
    try:
        q = open("/sys/fs/cgroup/cpu.max").read().split()
        info["cgroup_cpu_max"] = q
        if q[0] != "max":
            info["cpu_quota"] = int(q[0]) / int(q[1])
    except Exception:
        pass
    try:
        info["cpu_model"] = next(l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name"))
    except Exception:
        pass
    try:
        info["mem_total_kb"] = int(next(l.split()[1] for l in open("/proc/meminfo") if l.startswith("MemTotal")))
        info["cgroup_memory_max"] = open("/sys/fs/cgroup/memory.max").read().strip()
    except Exception:
        pass
    try:
        import ctypes

        lib = ctypes.CDLL("libnvidia-ml.so.1")
        lib.nvmlInit_v2()
        buf = ctypes.create_string_buffer(96)
        lib.nvmlSystemGetDriverVersion(buf, 96)
        info["nvidia_driver"] = buf.value.decode()
        h = ctypes.c_void_p()
        lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(h))
        lib.nvmlDeviceGetName(h, buf, 96)
        info["gpu"] = buf.value.decode()
        lib.nvmlDeviceGetUUID(h, buf, 96)
        info["gpu_uuid"] = buf.value.decode()
    except Exception as e:
        info["nvml"] = repr(e)[:120]
    from importlib import metadata

    for mod in ("pybamm", "casadi", "numpy", "scipy", "jax", "jaxlib"):
        try:
            info[mod] = metadata.version(mod)  # metadata only: importing JAX here would make fork unsafe
        except Exception:
            pass
    return info


def workers_for_host(info: dict, cap: int | None) -> int:
    n = int(info.get("cpu_quota") or info.get("affinity") or info.get("cpu_count") or 1)
    return max(1, min(n, cap or n))


def _child(job: dict, q) -> None:
    t0 = time.perf_counter()
    from scripts.dev.exam_design import battery_reference as br

    t_import = time.perf_counter() - t0
    case = br.BatteryCase(**job["case"])
    rec = br.solve_case(case, job["n_cycles"], job["checkpoints"], refined=job.get("refined", False))
    rec["role"] = job.get("role")
    rec["batch"] = job.get("batch")
    rec["timing_s"] = dict(rec.get("timing_s") or {}, import_s=t_import)
    rec["peak_rss_kb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    q.put(rec)


def run_battery_refs(cfg: dict, out: str) -> int:
    info = host_info()
    json.dump(info, open(os.path.join(out, "host.json"), "w"), indent=1)
    jobs = cfg["jobs"]
    workers = workers_for_host(info, cfg.get("max_workers"))
    timeout = float(cfg.get("timeout_s", 1200))
    stop_at = float(cfg.get("stop_admitting_epoch", 0)) or None
    ctx = mp.get_context("fork")
    recf = open(os.path.join(out, "records.jsonl"), "a")
    running: dict = {}
    pending = list(jobs)
    done = {"OK": 0, "REFERENCE_SOLVER_FAILED": 0, "REFERENCE_TIMEOUT": 0, "FAILED_INFRA": 0, "NOT_ADMITTED": 0}
    t_start = time.time()

    def progress():
        json.dump({"phase": "battery_refs", "workers": workers, "total": len(jobs), "pending": len(pending),
                   "running": len(running), "done": done, "elapsed_s": round(time.time() - t_start, 1)},
                  open(os.path.join(out, "progress.json"), "w"))

    def write(rec):
        recf.write(json.dumps(rec) + "\n")
        recf.flush()
        done[rec["status"]] = done.get(rec["status"], 0) + 1

    while pending or running:
        while pending and len(running) < workers:
            if stop_at and time.time() >= stop_at:
                for j in pending:
                    write({"case_id": j["case"]["case_id"], "role": j.get("role"), "refined": j.get("refined", False),
                           "status": "NOT_ADMITTED", "reason": "admission window closed before the pod deadline"})
                pending = []
                break
            job = pending.pop(0)
            q = ctx.Queue()
            p = ctx.Process(target=_child, args=(job, q))
            p.start()
            running[p.pid] = (p, q, job, time.time())
        for pid, (p, q, job, t0) in list(running.items()):
            rec = None
            try:
                rec = q.get_nowait()
            except Exception:
                pass
            base = {"case_id": job["case"]["case_id"], "inputs": {k: v for k, v in job["case"].items() if k != "case_id"},
                    "role": job.get("role"), "batch": job.get("batch"), "refined": job.get("refined", False),
                    "n_cycles": job["n_cycles"]}
            if rec is not None:
                p.join(5)
                rec["wall_total_s"] = time.time() - t0
                write(rec)
                del running[pid]
            elif time.time() - t0 > timeout:
                p.kill()
                p.join(5)
                write(base | {"status": "REFERENCE_TIMEOUT", "wall_total_s": time.time() - t0})
                del running[pid]
            elif not p.is_alive():
                try:
                    rec = q.get(timeout=2)
                    rec["wall_total_s"] = time.time() - t0
                    write(rec)
                except Exception:
                    write(base | {"status": "FAILED_INFRA", "exitcode": p.exitcode, "wall_total_s": time.time() - t0})
                del running[pid]
        progress()
        time.sleep(0.5)
    progress()
    recf.close()
    json.dump({"finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "done": done,
               "elapsed_s": time.time() - t_start}, open(os.path.join(out, "DONE.json"), "w"))
    return 0


def _photonic_child(job: dict, q) -> None:
    import resource as _r

    from scripts.dev.exam_design import photonic_reference as pr

    rec = pr.solve_case(job["case"], refined=job.get("refined", False), wavelengths=job.get("wavelengths"))
    rec["role"] = job.get("role")
    rec["peak_rss_kb"] = _r.getrusage(_r.RUSAGE_SELF).ru_maxrss
    q.put(rec)


def run_photonic_refs(cfg: dict, out: str) -> int:
    """Sequential (one GPU); each case in a fresh spawned process under a wall limit."""
    json.dump(host_info(), open(os.path.join(out, "host.json"), "w"), indent=1)
    ctx = mp.get_context("spawn")
    stop_at = float(cfg.get("stop_admitting_epoch", 0)) or None
    recf = open(os.path.join(out, "records.jsonl"), "a")
    done: dict = {}
    t_start = time.time()
    jobs = cfg["jobs"]
    for i, job in enumerate(jobs):
        json.dump({"phase": "photonic_refs", "total": len(jobs), "index": i, "done": done,
                   "elapsed_s": round(time.time() - t_start, 1)}, open(os.path.join(out, "progress.json"), "w"))
        base = {"case_id": job["case"]["case_id"], "inputs": job["case"], "refined": job.get("refined", False),
                "role": job.get("role")}
        if stop_at and time.time() >= stop_at:
            rec = base | {"status": "NOT_ADMITTED", "reason": "admission window closed before the pod deadline"}
        else:
            timeout = float(job.get("timeout_s", cfg.get("timeout_s", 900)))
            q = ctx.Queue()
            p = ctx.Process(target=_photonic_child, args=(job, q))
            t0 = time.time()
            p.start()
            rec = None
            while time.time() - t0 < timeout:
                try:
                    rec = q.get(timeout=2)
                    break
                except Exception:
                    if not p.is_alive():
                        break
            if rec is None:
                alive = p.is_alive()
                p.kill()
                rec = base | ({"status": "REFERENCE_TIMEOUT"} if alive else {"status": "FAILED_INFRA", "exitcode": p.exitcode})
            p.join(10)
            rec["wall_total_s"] = time.time() - t0
        recf.write(json.dumps(rec) + "\n")
        recf.flush()
        done[rec["status"]] = done.get(rec["status"], 0) + 1
    recf.close()
    json.dump({"phase": "photonic_refs", "total": len(jobs), "index": len(jobs), "done": done,
               "elapsed_s": round(time.time() - t_start, 1)}, open(os.path.join(out, "progress.json"), "w"))
    json.dump({"done": done, "elapsed_s": time.time() - t_start}, open(os.path.join(out, "DONE.json"), "w"))
    return 0


def run_multi(cfg: dict, out: str) -> int:
    """Run child phases concurrently (e.g. CPU battery references beside GPU photonics)."""
    import subprocess

    procs = []
    root = os.environ.get("OVERLAY_ROOT", "/tmp/overlay")
    for child in cfg["children"]:
        sub = os.path.join(out, child["phase"])
        os.makedirs(sub, exist_ok=True)
        ccfg = dict(child["config"])
        if cfg.get("stop_admitting_epoch"):
            ccfg["stop_admitting_epoch"] = cfg["stop_admitting_epoch"]
        cpath = os.path.join(sub, "child_config.json")
        json.dump(ccfg, open(cpath, "w"))
        env = dict(os.environ)
        code_root = os.getcwd()
        env["PYTHONPATH"] = ":".join([code_root, os.path.join(root, child["overlay"])])
        log = open(os.path.join(sub, "phase.log"), "wb")
        procs.append((child["phase"], subprocess.Popen([sys.executable, "-m", "scripts.dev.exam_design.runner",
                                                         child["phase"], "--out", sub, "--config", cpath],
                                                        env=env, stdout=log, stderr=subprocess.STDOUT)))
    while any(p.poll() is None for _, p in procs):
        prog = {}
        for name, _ in procs:
            try:
                prog[name] = json.load(open(os.path.join(out, name, "progress.json")))
            except Exception:
                prog[name] = None
        json.dump({"phase": "multi", "children": prog}, open(os.path.join(out, "progress.json"), "w"))
        time.sleep(5)
    rc = {name: p.returncode for name, p in procs}
    json.dump({"phase": "multi", "exit": rc}, open(os.path.join(out, "DONE.json"), "w"))
    return 0 if all(v == 0 for v in rc.values()) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    cfg = json.load(open(a.config)) if a.config else json.loads(os.environ.get("PHASE_CONFIG", "{}"))
    if "plan" in cfg:  # committed, hash-pinned plan file; runtime keys (deadlines) override
        cfg = json.load(open(cfg["plan"])) | {k: v for k, v in cfg.items() if k != "plan"}
    json.dump(cfg, open(os.path.join(a.out, "config.json"), "w"))
    if a.phase == "battery_refs":
        return run_battery_refs(cfg, a.out)
    if a.phase == "photonic_refs":
        return run_photonic_refs(cfg, a.out)
    if a.phase == "multi":
        return run_multi(cfg, a.out)
    if a.phase == "host":
        json.dump(host_info(), open(os.path.join(a.out, "host.json"), "w"), indent=1)
        return 0
    if a.phase == "train":
        from scripts.dev.exam_design import train_phase

        return train_phase.run(cfg, a.out)
    raise SystemExit(f"unknown phase {a.phase}")


if __name__ == "__main__":
    sys.exit(main())
