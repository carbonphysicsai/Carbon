"""Run frozen triage decks on the triage host under the grant's caps.

    python3 triage_run.py --decks DIR --family f02 --ledger LEDGER.jsonl [--dry-run]

OWNER-REFERENCE-ROUTE-TRIAGE-GRANT-01 (#801) and #787: one case at a time;
at most 8 CPUs, 24 GiB total cgroup memory and 16 live processes per case;
no network; 7,200 s per case; no retries; per-family node-hour,
allocated-CPU-hour and launch ceilings, sequential and non-transferable.
Every case's files are checked against the frozen manifest before it runs.
Each attempt appends one ledger row: times, wall, process-tree CPU (bash
`times` of the case's children), cgroup memory peak, exit and outcome. A case
cut short by a cap is CENSORED with its consumed cost, never retried.
Standard library only, so it runs on a fresh host.

f08 (Test Lead 2026-10-08) runs on the operator host's free CPU instead: one
CPU per ccx process (serial SPOOLES/ARPACK), 12 GiB per case, up to
`--parallel` cases at once. Its node-hour ceiling is the family's elapsed
wall clock from its first ledger row; allocated CPU-hours are wall x CPUs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CEILINGS = {  # #787 grant proposal, per family
    "f02": {"node_hours": 2, "cpu_hours": 16, "launches": 32},
    "f13": {"node_hours": 4, "cpu_hours": 32, "launches": 20},
    "f08": {"node_hours": 2, "cpu_hours": 16, "launches": 58},
}
CPUS, MEMORY, PIDS, CASE_TIMEOUT_S = 8, "24g", 16, 7200
LIMITS = {"f08": {"cpus": 1, "memory": "12g"}}  # local free CPU; others use CPUS/MEMORY
#: f08 on a shared host: a case starts only when MemAvailable covers its
#: estimated peak (measured 1.08 GB at 52 k nodes, scaled as nodes^1.4) plus
#: a 2 GiB reserve for the host's other work. Waiting is free; no case is skipped.
MEMORY_GATE = {"f08": {"gb_at": (52000, 1.08), "exponent": 1.4, "reserve_gb": 2.0}}
HOST_PROFILE = None
#: Run order within a family: the primary measurements first, so a family
#: ceiling can only censor refinements, never a primary.
PRIORITY = (
    "primary",
    "primary_sweeps",
    "controls",
    "steady_baselines",
    "separate_frequency_smoke",
    "mesh_and_time",
    "fine_sweeps",
    "witness_studies",
    "cold_repeat",
)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _used(ledger, family):
    used = {"wall_s": 0.0, "cpu_s": 0.0, "launches": 0, "first_start": None}
    if Path(ledger).exists():
        for line in Path(ledger).read_text().splitlines():
            row = json.loads(line)
            if row["family"] == family:
                used["wall_s"] += row["wall_s"]
                used["cpu_s"] += row["allocated_cpu_s"]
                used["launches"] += 1
                first = used["first_start"]
                used["first_start"] = (
                    row["started_unix"]
                    if first is None
                    else min(first, row["started_unix"])
                )
    return used


def _mem_available_gb():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024**2
    return float("inf")


def _wait_for_memory(entry, family):
    gate = MEMORY_GATE.get(family)
    nodes = (entry.get("mesh") or {}).get("nodes")
    if not gate or not nodes:
        return
    (n0, gb0), k = gate["gb_at"], gate["exponent"]
    need = gb0 * (nodes / n0) ** k + gate["reserve_gb"]
    while _mem_available_gb() < need:
        time.sleep(60)


def _remaining_s(cap, used, cpus, family):
    if family in LIMITS:  # elapsed family wall clock and allocated CPU
        elapsed = time.time() - used["first_start"] if used["first_start"] else 0.0
        return min(
            cap["node_hours"] * 3600 - elapsed,
            (cap["cpu_hours"] * 3600 - used["cpu_s"]) / cpus,
        )
    return (
        min(cap["node_hours"] * 3600, cap["cpu_hours"] * 3600 / CPUS) - used["wall_s"]
    )


def run(decks, family, ledger, image, run_ref=None, dry_run=False, parallel=1):
    decks = Path(decks)
    manifest = json.loads((decks / "manifest.json").read_text())
    if manifest["image"] != image:
        raise SystemExit("image differs from the frozen manifest")
    # A containerd image store names an image by its OCI manifest digest; the
    # pinned id is the config digest that manifest references. Both are kept.
    run_ref = run_ref or image
    done = set()
    if Path(ledger).exists():
        done = {json.loads(x)["case"] for x in Path(ledger).read_text().splitlines()}
    cap = CEILINGS[family]
    order = {r: i for i, r in enumerate(PRIORITY)}
    entries = [e for e in manifest["cases"] if e["family"] == family]
    entries.sort(
        key=lambda e: (order.get(e["reservation"], len(order)), "mesh2" in e["case"])
    )
    cpus = LIMITS.get(family, {}).get("cpus", CPUS)
    memory = LIMITS.get(family, {}).get("memory", MEMORY)
    lock = threading.Lock()
    todo = [e for e in entries if e["case"] not in done]

    def one(entry):
        with lock:
            used = _used(ledger, family)
            remaining_s = _remaining_s(cap, used, cpus, family)
            if used["launches"] >= cap["launches"] or remaining_s <= 0:
                print(
                    f"family ceiling reached; {entry['case']} not launched", flush=True
                )
                return
        if not dry_run:
            _wait_for_memory(entry, family)
        _launch(
            entry,
            decks,
            family,
            ledger,
            run_ref,
            image,
            dry_run,
            cpus,
            memory,
            remaining_s,
            lock,
        )

    if parallel > 1 and not dry_run:
        with ThreadPoolExecutor(parallel) as pool:
            list(pool.map(one, todo))
    else:
        for entry in todo:
            one(entry)


def _launch(
    entry,
    decks,
    family,
    ledger,
    run_ref,
    image,
    dry_run,
    cpus,
    memory,
    remaining_s,
    lock,
):
    if True:  # one case
        case_dir = decks / family / entry["case"]
        bad = [f for f, h in entry["files"].items() if _sha(case_dir / f) != h]
        if bad:
            raise SystemExit(
                f"{entry['case']}: files differ from the manifest: {bad[:3]}"
            )
        timeout = min(CASE_TIMEOUT_S, remaining_s)
        script = (
            f"{entry['command']}; rc=$?; times > times.txt; "
            "cat /sys/fs/cgroup/memory.peak > memory.peak 2>/dev/null; exit $rc"
        )
        name = f"carbon-triage-{family}-{entry['case']}"[:100]
        cmd = [
            "docker", "run", "--rm", "--name", name, "--network", "none", "--read-only",
            "--tmpfs", "/tmp", "--cpus", str(cpus), "--memory", memory, "--memory-swap", memory,
            "--pids-limit", str(PIDS), "--user", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{case_dir.resolve()}:/case", "-w", "/case", run_ref, "bash", "-c", script,
        ]  # fmt: skip
        if dry_run:
            print(" ".join(cmd))
            return
        started, t0 = time.time(), time.monotonic()
        try:
            done_proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, check=False
            )
            code, outcome = (
                done_proc.returncode,
                ("COMPLETED" if done_proc.returncode == 0 else "FAILED"),
            )
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", name], capture_output=True, check=False)
            code = None
            outcome = (
                "CENSORED_CASE_TIMEOUT"
                if timeout >= CASE_TIMEOUT_S
                else "CENSORED_FAMILY_CAP"
            )
        wall = time.monotonic() - t0
        cpu = None
        times_file = case_dir / "times.txt"
        if times_file.exists():
            lines = times_file.read_text().split("\n")
            if len(lines) > 1:
                cpu = lines[1].strip()  # children's user and system time
        peak = (
            (case_dir / "memory.peak").read_text().strip()
            if (case_dir / "memory.peak").exists()
            else None
        )
        row = {
            "family": family, "case": entry["case"], "reservation": entry["reservation"],
            "started_unix": started, "wall_s": round(wall, 2), "allocated_cpu_s": round(wall * cpus, 1), "cpus": cpus,
            "children_cpu": cpu, "cgroup_memory_peak_bytes": peak, "exit": code, "outcome": outcome,
            "nproc": os.cpu_count(), "host_profile": HOST_PROFILE, "image_config": image, "image_run_ref": run_ref,
        }  # fmt: skip
        with lock, open(ledger, "a") as handle:
            handle.write(json.dumps(row) + "\n")
        print(json.dumps(row), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="triage_run")
    parser.add_argument("--decks", type=Path, required=True)
    parser.add_argument("--family", choices=sorted(CEILINGS), required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument(
        "--image",
        default="sha256:8bcd864dd60be0a80be9769c1a95c67db76eca9e718212f63dd0460cf3a08fc6",
    )
    parser.add_argument(
        "--run-ref", help="the reference docker run resolves (manifest digest)"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--parallel", type=int, default=1, help="concurrent cases (local f08 only)"
    )
    parser.add_argument("--host-profile", help="recorded in every ledger row")
    args = parser.parse_args(argv)
    if args.parallel > 1 and args.family not in LIMITS:
        raise SystemExit("--parallel is only for the local f08 family")
    global HOST_PROFILE
    HOST_PROFILE = args.host_profile
    run(
        args.decks,
        args.family,
        args.ledger,
        args.image,
        args.run_ref,
        args.dry_run,
        args.parallel,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
