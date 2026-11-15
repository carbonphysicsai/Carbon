"""The kit speed check (owner pick 3, Sun 15 Nov 2026): this machine against the grading worker on one fixed public
workload (`carbon.development_session.speed_workload`).

`python -m scripts.dev.miner_launchpad.speed_check --state-dir <the install's state dir>` runs the workload in this
install's worker image (the grade's own timed inference program) and prints this machine's time per call beside
Carbon's registered time for the same workload on the grading worker (`speed_reference.json`), the ratio, and what the
ratio means against the published inference wall.

The registered row is read only when its workload digest equals this run's: a different graph, parameters, inputs,
allowlist or timed program is a different workload, and the kit says the time is not registered rather than show a
ratio for something else. Until Carbon has measured and registered the worker's time, the kit prints this machine's
figure alone. It is guidance about speed, never a grade.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

REFERENCE_PATH = Path(__file__).with_name("speed_reference.json")
REFERENCE_SCHEMA = "carbon.kit.speed-reference.v1"
_ROW_KEYS = {
    "worker_class",
    "image_id",
    "per_call_median_seconds",
    "startup_seconds",
    "runs",
    "measured_utc",
    "evidence_sha256",
}
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
CAVEAT = (
    "One fixed graph's time: a graph with different operations can scale differently between two machines, and the "
    "grading host is shared, so treat this as a guide, not a grade."
)


def _positive(value) -> bool:
    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def reference(workload_digest: str, path=None):
    """The registered grading-worker row for `workload_digest`, or None (no file, no row, or a malformed row: never
    a guess)."""
    try:
        document = json.loads(
            Path(REFERENCE_PATH if path is None else path).read_bytes()
        )
    except (OSError, ValueError):
        return None
    if type(document) is not dict or document.get("schema") != REFERENCE_SCHEMA:
        return None
    rows = document.get("rows")
    row = rows.get(workload_digest) if type(rows) is dict else None
    if (
        type(row) is not dict
        or set(row) != _ROW_KEYS
        or type(row["worker_class"]) is not str
        or not row["worker_class"]
        or type(row["image_id"]) is not str
        or not _positive(row["per_call_median_seconds"])
        or not (
            type(row["startup_seconds"]) in (int, float)
            and math.isfinite(row["startup_seconds"])
            and row["startup_seconds"] >= 0
        )
        or type(row["runs"]) is not int
        or row["runs"] < 1
        or type(row["measured_utc"]) is not str
        or type(row["evidence_sha256"]) is not str
        or _DIGEST.fullmatch(row["evidence_sha256"]) is None
    ):
        return None
    return row


def _seconds(value: float) -> str:
    if value >= 10:
        return f"{value:.0f} s"
    if value >= 0.1:
        return f"{value:.2f} s"
    return f"{value * 1000:.1f} ms"


def report(here: dict, row, wall_seconds: int) -> list:
    """The lines the kit prints for this machine's result `here` and the registered row (None: not registered)."""
    lines = [
        "Carbon speed check: one fixed public graph, the grade's own inference program, 4 CPUs",
        (
            f"  this machine:    {_seconds(here['per_call_median_seconds'])} per call (median of "
            f"{here['per_call_rows']}), start-up about {_seconds(here['startup_seconds'])}"
        ),
    ]
    if row is None:
        lines.append(
            "  grading worker:  not registered yet for this workload (no ratio is shown until Carbon has measured it)"
        )
        lines.append("  " + CAVEAT)
        return lines
    ratio = row["per_call_median_seconds"] / here["per_call_median_seconds"]
    lines.append(
        f"  grading worker:  {_seconds(row['per_call_median_seconds'])} per call, start-up about "
        f"{_seconds(row['startup_seconds'])} ({row['worker_class']}; measured {row['measured_utc']})"
    )
    if ratio >= 1:
        lines.append(
            f"  ratio:           the grading worker is {ratio:.2f}x slower than this machine on this workload"
        )
    else:
        lines.append(
            f"  ratio:           the grading worker is {1 / ratio:.2f}x faster than this machine on this workload"
        )
    lines.append(
        f"  the {wall_seconds} s limit: a graded inference pass that takes about {_seconds(wall_seconds / ratio)} "
        f"on this machine would take about {wall_seconds} s on the grading worker"
    )
    if row["image_id"] != here["image_id"]:
        lines.append(
            "  note:            your worker image differs from the one the grading worker's time was measured in"
        )
    lines.append("  " + CAVEAT)
    return lines


def _profile(state_dir: Path) -> dict:
    path = state_dir / "environment" / "runner-profile.json"
    try:
        cfg = json.loads(path.read_bytes())
    except (OSError, ValueError):
        raise SystemExit(
            "Carbon speed check: no runner profile at "
            + str(path)
            + "; finish the installer first"
        ) from None
    if type(cfg) is not dict or type(cfg.get("paths")) is not dict:
        raise SystemExit("Carbon speed check: the runner profile is unreadable")
    return cfg


def run_here(state_dir: Path) -> dict:
    """Run the workload once in this install's worker image, in a fresh ledger of its own under the state dir (removed
    afterwards: each check is one bounded run, so no budget or clock accumulates across checks).
    """
    import shutil
    import time

    from carbon.development_session import speed_workload
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    cfg = _profile(state_dir)
    image = load_image_identity(Path(cfg["paths"]["image_manifest"]))
    stamp = int(time.time() * 1000)
    root = (state_dir / "speed-check" / f"run-{stamp}").resolve()
    try:
        ledger = speed_workload.open_ledger(root)
        return speed_workload.measure(
            ledger,
            owner=speed_workload.OWNER,
            identity=f"speed-{stamp}",
            inference_image=image,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    args = parser.parse_args(argv)
    from carbon.development_session import speed_workload

    here = run_here(args.state_dir)
    row = reference(here["workload_digest"])
    if args.json:
        print(json.dumps({"here": here, "grading_worker": row}, sort_keys=True))
        return 0
    print("\n".join(report(here, row, speed_workload.inference_wall_seconds())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
