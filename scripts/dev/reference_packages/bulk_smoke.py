"""Write a tiny bulk-runner smoke plan (real docker, seconds of CPU).

    python3 bulk_smoke.py --root DIR --busybox REF --busybox-pin PIN \
        --debian REF --debian-pin PIN
    python3 bulk_run.py --plan DIR/plan.json --out DIR/out --dry-run
    python3 bulk_run.py --plan DIR/plan.json --out DIR/out

Two families exercise every runner path within one CPU and 1 GiB in total
(two 0.5-CPU, 0.5-GiB cases at a time, so it needs no shared-host lock): a
COMPLETED case, a CPU burner, a 200 MiB tmpfs write (memory peak), a FAILED
exit, a case past its wall timeout (CENSORED_CASE_TIMEOUT, stats still recorded through
the SIGTERM trap) and a passing acceptance command. ``PIN`` is the identity
the frozen manifest carries (image id, manifest digest or config digest).
No solver, no science: an operator rehearsal of the runner on a new host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CASES = {
    "smoke-busybox": [
        ("hello", "primary", "cat case.sif > out.txt && echo done >> out.txt"),
        ("burn", "primary", "i=0; while [ $i -lt 400000 ]; do i=$((i+1)); done"),
        ("memory", "controls", "dd if=/dev/zero of=/tmp/blob bs=1M count=200"),
        ("fails", "controls", "echo broken > solver.log; exit 3"),
    ],
    "smoke-debian": [
        ("hello", "primary", "cat case.sif > out.txt"),
        ("too-slow", "controls", "sleep 300"),
    ],
}


def write(root, images):
    root = Path(root)
    families = []
    for family, cases in CASES.items():
        ref, pin = images[family]
        mdir = root / family
        entries = []
        for name, reservation, command in cases:
            cdir = mdir / family / name
            cdir.mkdir(parents=True, exist_ok=True)
            body = f"smoke deck {family}/{name}\n".encode()
            (cdir / "case.sif").write_bytes(body)
            entries.append(
                {
                    "family": family,
                    "case": name,
                    "reservation": reservation,
                    "command": command,
                    "files": {"case.sif": hashlib.sha256(body).hexdigest()},
                    "estimate_wall_s": 5,
                }
            )
        manifest = {
            "schema": "carbon.reference-triage.frozen-decks.v1",
            "image": pin,
            "cases": entries,
        }
        (mdir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
        families.append(
            {
                "family": family,
                "manifest_dir": family,
                "image": ref,
                "priority": 10,
                "case_limits": {
                    "cpus": 0.5,
                    "memory_gib": 0.5,
                    "pids": 32,
                    "wall_timeout_s": 8 if family == "smoke-debian" else 120,
                },
                "ceilings": {"launches": 10, "cpu_hours": 1},
                "acceptance": {"command": "true", "timeout_s": 60},
            }
        )
    plan = {
        "schema": "carbon.reference-bulk.run-plan.v1",
        "plan_id": "bulk-smoke",
        "authority": "local runner rehearsal; no spend",
        "host_profile": "local-dev-4vcpu-15g-contended",
        "machine": {
            "cpus": 1,
            "memory_gib": 1,
            "node_hours": 0.5,
            "clock_start": "first_run",
            "margin_minutes": 0,
            "min_case_window_s": 30,
        },
        "families": families,
    }
    (root / "plan.json").write_text(json.dumps(plan, indent=1) + "\n")
    return root / "plan.json"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bulk_smoke")
    parser.add_argument("--root", type=Path, required=True)
    for name in ("busybox", "debian"):
        parser.add_argument(f"--{name}", required=True, help="image id or repo@digest")
        parser.add_argument(f"--{name}-pin", required=True, help="manifest pin")
    args = parser.parse_args(argv)
    path = write(
        args.root,
        {
            "smoke-busybox": (args.busybox, args.busybox_pin),
            "smoke-debian": (args.debian, args.debian_pin),
        },
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
