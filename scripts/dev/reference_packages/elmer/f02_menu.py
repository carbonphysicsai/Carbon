"""f02-v2 denser schedule menu (#846; registry
docs/development/evidence/reference-packages-01/f02-menu-v2/registry.json).

    python3 f02_menu.py plan DIR
    python3 f02_menu.py run DIR --parallel N --image REF [--host-profile TEXT]
    python3 f02_menu.py plan-refine DIR
    python3 f02_menu.py score DIR OUT.json

Test Lead 2026-10-08 relaying #846: measure whether >= 5 PASS and >= 5
near-limit FAIL schedules emerge per context under a denser menu inside the
existing bounds (peak 80-140 W, on-time 5-20 s, base 20 W, 95 C, same
stack, waveform families, splits, cooling pairs and initial states). The
menu is fixed before any solve and never tuned after seeing answers:
peak {80, 100, 120, 140} W x on-time {5, 10, 15, 20} s = 16 actions in each
of the 24 contexts (384 transients). Every case whose peak lies within
1 C (two 0.5 C bands) of 95 C is re-solved at mesh 2 and at dt/2; a case
whose rungs straddle 95 C is UNRESOLVED. Local free CPU, one CPU per
ElmerSolver, costs as CPU-s with the host profile.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f02_deck as deck

PEAKS_W, ON_TIMES_S = (80.0, 100.0, 120.0, 140.0), (5.0, 10.0, 15.0, 20.0)
COOLING = ((30.0, 2500.0), (40.0, 1500.0))
INITIAL_C, SPLITS, FAMILIES = (
    (40.0, 55.0),
    (0.5, 0.8),
    ("rectangular", "ramp", "two-pulse"),
)
LIMIT, BAND, NEAR_K = deck.LIMIT_C, 0.5, 1.0
SOLVE = "ElmerSolver case.sif > solver.log 2>&1"


def contexts():
    for (coolant, h), t0, split, family in itertools.product(
        COOLING, INITIAL_C, SPLITS, FAMILIES
    ):
        yield f"c{coolant:g}-i{t0:g}-s{split:g}-{family}", {
            "coolant_c": coolant, "h_w_m2_k": h, "initial_c": t0, "left_source_fraction": split, "waveform": family}  # fmt: skip


def case_name(ctx, peak, d, tag="primary"):
    return f"{ctx}-p{peak:g}-d{d:g}-{tag}"


def plan(root):
    root = Path(root)
    entries = []
    for ctx, base in contexts():
        for peak, d in itertools.product(PEAKS_W, ON_TIMES_S):
            name = case_name(ctx, peak, d)
            deck.write_case(
                {**base, "peak_w": peak, "on_time_s": d}, root / "cases" / name
            )
            entries.append(
                {
                    "case": name,
                    "context": ctx,
                    "peak_w": peak,
                    "on_time_s": d,
                    "tag": "primary",
                }
            )
    _manifest(root, entries)
    return len(entries)


def _manifest(root, entries):
    path = Path(root) / "manifest.json"
    old = json.loads(path.read_text())["cases"] if path.exists() else []
    known = {e["case"] for e in old}
    for e in entries:
        d = Path(root) / "cases" / e["case"]
        e["files"] = {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(d.rglob("*")) if p.is_file()}  # fmt: skip
    cases = old + [e for e in entries if e["case"] not in known]
    path.write_text(
        json.dumps({"schema": "carbon.f02-menu-v2.decks.v1", "cases": cases}, indent=1)
        + "\n"
    )


def run(root, parallel, image, host_profile=None):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text())
    ledger = root / "ledger.jsonl"
    done = (
        {json.loads(x)["case"] for x in ledger.read_text().splitlines()}
        if ledger.exists()
        else set()
    )
    lock = threading.Lock()

    def one(entry):
        d = root / "cases" / entry["case"]
        bad = [
            f
            for f, h in entry["files"].items()
            if hashlib.sha256((d / f).read_bytes()).hexdigest() != h
        ]
        if bad:
            raise SystemExit(f"{entry['case']}: files differ from the manifest")
        script = f"{SOLVE}; rc=$?; times > times.txt; cat /sys/fs/cgroup/memory.peak > memory.peak 2>/dev/null; exit $rc"
        cmd = ["docker", "run", "--rm", "--name", f"carbon-f02menu-{entry['case']}"[:100], "--network", "none",
               "--read-only", "--cpu-shares", "256", "--tmpfs", "/tmp", "--cpus", "1", "--memory", "4g", "--pids-limit", "16",
               "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{d.resolve()}:/case", "-w", "/case", image,
               "bash", "-c", script]  # fmt: skip
        started, t0 = time.time(), time.monotonic()
        proc = subprocess.run(
            cmd, capture_output=True, text=True, check=False, timeout=7200
        )
        wall = time.monotonic() - t0
        times = (
            (d / "times.txt").read_text().split("\n")
            if (d / "times.txt").exists()
            else []
        )
        row = {"case": entry["case"], "tag": entry["tag"], "started_unix": started, "wall_s": round(wall, 2),
               "children_cpu": times[1].strip() if len(times) > 1 else None,
               "cgroup_memory_peak_bytes": (d / "memory.peak").read_text().strip() if (d / "memory.peak").exists() else None,
               "exit": proc.returncode, "outcome": "COMPLETED" if proc.returncode == 0 else "FAILED",
               "cpus": 1, "nproc": os.cpu_count(), "host_profile": host_profile, "image": image}  # fmt: skip
        with lock, ledger.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(entry["case"], row["outcome"], row["wall_s"], flush=True)

    todo = [e for e in manifest["cases"] if e["case"] not in done]
    with ThreadPoolExecutor(parallel) as pool:
        list(pool.map(one, todo))


def _observed(root):
    out = {}
    for e in json.loads((Path(root) / "manifest.json").read_text())["cases"]:
        d = Path(root) / "cases" / e["case"]
        try:
            out[e["case"]] = {**e, **deck.observe(d)}
        except (OSError, StopIteration, ValueError, IndexError):
            out[e["case"]] = {**e, "peak_top_c": None}
    return out


def plan_refine(root):
    obs, entries = _observed(root), []
    for o in obs.values():
        if (
            o["tag"] != "primary"
            or o["peak_top_c"] is None
            or abs(o["peak_top_c"] - LIMIT) > NEAR_K
        ):
            continue
        base = dict(next(b for c, b in contexts() if c == o["context"]))
        case = {**base, "peak_w": o["peak_w"], "on_time_s": o["on_time_s"]}
        for tag, level, dt in (("mesh2", 2, 1.0), ("dt0.5", 1, 0.5)):
            new = case_name(o["context"], o["peak_w"], o["on_time_s"], tag)
            deck.write_case(case, Path(root) / "cases" / new, level, dt)
            entries.append(
                {
                    "case": new,
                    "context": o["context"],
                    "peak_w": o["peak_w"],
                    "on_time_s": o["on_time_s"],
                    "tag": tag,
                }
            )
    _manifest(root, entries)
    return len(entries)


def score(root, out):
    obs = _observed(root)
    per = {}
    for ctx, _ in contexts():
        rows = []
        for peak, d in itertools.product(PEAKS_W, ON_TIMES_S):
            prim = obs.get(case_name(ctx, peak, d))
            if not prim or prim["peak_top_c"] is None:
                rows.append(
                    {"action": f"p{peak:g}-d{d:g}", "verdict": "NOT_RUN_OR_FAILED"}
                )
                continue
            rungs = [prim["peak_top_c"]] + [
                obs[n]["peak_top_c"] for n in (case_name(ctx, peak, d, t) for t in ("mesh2", "dt0.5"))
                if n in obs and obs[n]["peak_top_c"] is not None
            ]  # fmt: skip
            near = abs(prim["peak_top_c"] - LIMIT) <= NEAR_K
            if near and len(rungs) < 3:
                verdict = "UNRESOLVED_REFINEMENT_PENDING"
            elif all(r <= LIMIT for r in rungs):
                verdict = "PASS"
            elif all(r > LIMIT for r in rungs):
                verdict = "FAIL"
            else:
                verdict = "UNRESOLVED"
            rows.append({"action": f"p{peak:g}-d{d:g}", "verdict": verdict, "peak_top_c": prim["peak_top_c"],
                         "rung_spread_k": max(rungs) - min(rungs), "extra_energy_j": prim["extra_energy_j"]})  # fmt: skip
        passes = [r for r in rows if r["verdict"] == "PASS"]
        fails = [r for r in rows if r["verdict"] == "FAIL"]
        best = (
            max(passes, key=lambda r: (r["extra_energy_j"], -r["peak_top_c"]))
            if passes
            else None
        )
        per[ctx] = {
            "pass": len(passes), "fail": len(fails),
            "fail_within_1k": sum(r["peak_top_c"] - LIMIT <= NEAR_K for r in fails),
            "fail_within_5k": sum(r["peak_top_c"] - LIMIT <= 5.0 for r in fails),
            "unresolved": sum(r["verdict"].startswith("UNRESOLVED") for r in rows),
            "contested_1k": len(passes) >= 5 and sum(r["peak_top_c"] - LIMIT <= NEAR_K for r in fails) >= 5,
            "contested_5k": len(passes) >= 5 and sum(r["peak_top_c"] - LIMIT <= 5.0 for r in fails) >= 5,
            "best": best and best["action"], "best_extra_energy_j": best and best["extra_energy_j"],
            "rows": rows,
        }  # fmt: skip
    ledger = [
        json.loads(x) for x in (Path(root) / "ledger.jsonl").read_text().splitlines()
    ]
    cpu = sorted(
        _cpu_s(r["children_cpu"])
        for r in ledger
        if r["outcome"] == "COMPLETED" and r["children_cpu"]
    )
    doc = {
        "schema": "carbon.f02-menu-v2.score.v1",
        "contexts": per,
        "contested_contexts_1k": sum(v["contested_1k"] for v in per.values()),
        "contested_contexts_5k": sum(v["contested_5k"] for v in per.values()),
        "distinct_bests": sorted({v["best"] for v in per.values() if v["best"]}),
        "unresolved_rate": sum(v["unresolved"] for v in per.values()) / (16 * len(per)),
        "cost": {
            "solves": len(ledger),
            "cpu_s_p50": cpu[len(cpu) // 2] if cpu else None,
            "cpu_s_p95": cpu[int(0.95 * (len(cpu) - 1))] if cpu else None,
            "cpu_s_total": sum(cpu),
            "peak_memory_bytes_max": max(
                (
                    int(r["cgroup_memory_peak_bytes"])
                    for r in ledger
                    if r["cgroup_memory_peak_bytes"]
                ),
                default=None,
            ),
        },
    }
    Path(out).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    return doc


def _cpu_s(text):
    total = 0.0
    for part in text.split():
        m, s = part.rstrip("s").split("m")
        total += 60 * float(m) + float(s)
    return total


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f02_menu")
    parser.add_argument("command", choices=("plan", "run", "plan-refine", "score"))
    parser.add_argument("root", type=Path)
    parser.add_argument("out", type=Path, nargs="?")
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument(
        "--image",
        default="sha256:8bcd864dd60be0a80be9769c1a95c67db76eca9e718212f63dd0460cf3a08fc6",
    )
    parser.add_argument("--host-profile")
    args = parser.parse_args(argv)
    if args.command == "plan":
        print(plan(args.root))
    elif args.command == "plan-refine":
        print(plan_refine(args.root))
    elif args.command == "run":
        run(args.root, args.parallel, args.image, args.host_profile)
    else:
        doc = score(args.root, args.out)
        print(
            json.dumps(
                {
                    k: doc[k]
                    for k in (
                        "contested_contexts_1k",
                        "contested_contexts_5k",
                        "distinct_bests",
                        "unresolved_rate",
                        "cost",
                    )
                },
                indent=1,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
