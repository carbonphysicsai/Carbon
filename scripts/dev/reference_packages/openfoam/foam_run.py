"""Run one OpenFOAM case directory in the pinned image and measure it.

    python3 foam_run.py CASE_DIR 'COMMAND' [--cpus 1] [--memory 3g] [--timeout S]

Same isolation as the triage runner (no network, read-only root, tmpfs /tmp,
the caller's uid, 16 pids) so local measurements describe the shape the bulk
runner will launch. Records wall seconds and, from the container's own cgroup,
CPU microseconds (cpu.stat usage_usec) and memory.peak. Writes
CASE_DIR/run.json and returns it. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import time
from pathlib import Path

LOCK = json.loads((Path(__file__).with_name("image.lock.json")).read_text())
IMAGE = LOCK["run_reference"]
HOST_PROFILE = "local-dev-4vcpu-15g-contended"


def cpu_model():
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor()


def run(case, command, cpus=1, memory="3g", timeout=7200, pids=16):
    case = Path(case).resolve()
    # The image entrypoint (/openfoam/run) starts in $HOME, so enter /case
    # explicitly. cgroup v2 (cpu.stat, memory.peak) or v1 (cpuacct, memory).
    script = (
        f"cd /case && {{ {command}; }}; rc=$?; cd /case; G=/sys/fs/cgroup; "
        "if [ -f $G/cpu.stat ]; then grep usage_usec $G/cpu.stat | cut -d' ' -f2; "
        "else echo $(( $(cat $G/cpuacct/cpuacct.usage) / 1000 )); fi > .cpu_usec; "
        "{ cat $G/memory.peak || cat $G/memory/memory.max_usage_in_bytes; } "
        "> .memory_peak 2>/dev/null; exit $rc"
    )
    name = f"carbon-f17-{case.name}-{os.getpid()}"[:100]
    cmd = [
        "docker", "run", "--rm", "--name", name, "--network", "none", "--read-only",
        "--tmpfs", "/tmp", "--cpus", str(cpus), "--memory", memory, "--memory-swap", memory,
        "--pids-limit", str(pids), "--user", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{case}:/case", "-w", "/case", IMAGE, "bash", "-c", script,
    ]  # fmt: skip
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        code = proc.returncode
        outcome = "COMPLETED" if code == 0 else "FAILED"
        tail = (proc.stdout + proc.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)
        code, outcome, tail = None, "CENSORED_TIMEOUT", ""
    wall = time.monotonic() - t0

    def read(name):
        path = case / name
        if not path.exists():
            return None
        text = path.read_text().strip()
        path.unlink()
        return int(text) if text.isdigit() else None

    usec, peak = read(".cpu_usec"), read(".memory_peak")
    row = {
        "case": case.name,
        "command": command,
        "image": IMAGE,
        "exit": code,
        "outcome": outcome,
        "wall_s": round(wall, 2),
        "cgroup_cpu_s": None if usec is None else round(usec / 1e6, 2),
        "cgroup_memory_peak_mib": None if peak is None else round(peak / 2**20, 1),
        "cpus_limit": cpus,
        "memory_limit": memory,
        "nproc": os.cpu_count(),
        "cpu_model": cpu_model(),
        "host_profile": HOST_PROFILE,
        "started_unix": round(time.time() - wall, 1),
    }
    if outcome != "COMPLETED":
        row["output_tail"] = tail
    (case / "run.json").write_text(json.dumps(row, indent=1) + "\n")
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    parser.add_argument("command")
    parser.add_argument("--cpus", type=float, default=1)
    parser.add_argument("--memory", default="3g")
    parser.add_argument("--timeout", type=float, default=7200)
    args = parser.parse_args(argv)
    row = run(args.case, args.command, args.cpus, args.memory, args.timeout)
    print(json.dumps(row))
    return 0 if row["outcome"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
