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
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CEILINGS = {  # #787 grant proposal, per family
    "f02": {"node_hours": 2, "cpu_hours": 16, "launches": 32},
    "f13": {"node_hours": 4, "cpu_hours": 32, "launches": 20},
}
CPUS, MEMORY, PIDS, CASE_TIMEOUT_S = 8, "24g", 16, 7200


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _used(ledger, family):
    used = {"wall_s": 0.0, "launches": 0}
    if Path(ledger).exists():
        for line in Path(ledger).read_text().splitlines():
            row = json.loads(line)
            if row["family"] == family:
                used["wall_s"] += row["wall_s"]
                used["launches"] += 1
    return used


def run(decks, family, ledger, image, dry_run=False):
    decks = Path(decks)
    manifest = json.loads((decks / "manifest.json").read_text())
    if manifest["image"] != image:
        raise SystemExit("image differs from the frozen manifest")
    done = set()
    if Path(ledger).exists():
        done = {json.loads(x)["case"] for x in Path(ledger).read_text().splitlines()}
    cap = CEILINGS[family]
    for entry in (e for e in manifest["cases"] if e["family"] == family):
        if entry["case"] in done:
            continue
        used = _used(ledger, family)
        remaining_s = (
            min(cap["node_hours"] * 3600, cap["cpu_hours"] * 3600 / CPUS)
            - used["wall_s"]
        )
        if used["launches"] >= cap["launches"] or remaining_s <= 0:
            print("family ceiling reached; stopping", flush=True)
            return
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
            "--tmpfs", "/tmp", "--cpus", str(CPUS), "--memory", MEMORY, "--memory-swap", MEMORY,
            "--pids-limit", str(PIDS), "--user", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{case_dir.resolve()}:/case", "-w", "/case", image, "bash", "-c", script,
        ]  # fmt: skip
        if dry_run:
            print(" ".join(cmd))
            continue
        started, t0 = time.time(), time.monotonic()
        try:
            done_proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, check=False
            )
            code, outcome = done_proc.returncode, (
                "COMPLETED" if done_proc.returncode == 0 else "FAILED"
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
            "started_unix": started, "wall_s": round(wall, 2), "allocated_cpu_s": round(wall * CPUS, 1),
            "children_cpu": cpu, "cgroup_memory_peak_bytes": peak, "exit": code, "outcome": outcome,
            "host": os.uname().nodename, "nproc": os.cpu_count(),
        }  # fmt: skip
        with open(ledger, "a") as handle:
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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    run(args.decks, args.family, args.ledger, args.image, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
