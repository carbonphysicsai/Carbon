"""Refresh and check the CI shard weights from measured CI runs.

`scripts/dev/ci_shard.py` balances the six canonical shards by measured seconds per
test file (`scripts/dev/ci_shard_weights.json`). A file with no measurement weighs its
test count times the measured mean seconds per test, so a weights file that lags the
suite (hundreds of new files) balances badly. Every shard prints one line,

    CARBON_SHARD_SECONDS {"tests/cpu/test_x.py": 12.3, ...}

at the end of its log. This tool turns such logs into the committed weights file. It
invents no duration: a file's weight is the mean of what the supplied runs measured.

Regeneration (a run is the six `Canonical environment (n)` job logs of one CI run;
use the runs you want to average, ideally a few recent full ones):

    for job in $(gh run view RUN --json jobs \\
        --jq '.jobs[]|select(.name|test("Canonical environment [(]"))|.databaseId'); do
      gh api repos/OWNER/REPO/actions/jobs/$job/logs --allow-escape-sequences \\
        | sed 's/\\x1b\\[[0-9;]*m//g' > logs/RUN-$job.log
    done
    python scripts/dev/ci_shard_weights.py build logs/*.log \\
        --source "CI runs RUN1, RUN2, RUN3: per-file seconds" \\
        --out scripts/dev/ci_shard_weights.json

    python scripts/dev/ci_shard_weights.py simulate        # the balance it gives
    python scripts/dev/ci_shard_weights.py simulate --assigned OLD_WEIGHTS.json

`simulate --assigned OLD` applies the partition OLD would choose (with its fallback for
files it never measured) to the new measurements: the balance that weights file really
gave. The lane seconds (`lane_seconds`) are carried over unchanged unless `--lanes`
names a file to take them from.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from scripts.dev import ci_shard
except ImportError:  # run as a script from scripts/dev
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.dev import ci_shard

_SECONDS = re.compile(r"CARBON_SHARD_SECONDS (\{.*\})")
_DIGEST = re.compile(r"partition ([0-9a-f]{16})")
_FILE = re.compile(r"[A-Za-z0-9_./-]+\.py")


def parse_log(text: str) -> tuple[str, dict[str, float]]:
    """`(partition digest, {file: seconds})` from one shard's log text."""
    seconds = _SECONDS.search(text)
    digest = _DIGEST.search(text)
    if seconds is None or digest is None:
        raise ValueError("no CARBON_SHARD_SECONDS and partition line in this log")
    try:
        measured = json.loads(seconds.group(1))
    except ValueError as error:
        raise ValueError("CARBON_SHARD_SECONDS is not JSON") from error
    if not isinstance(measured, dict) or not all(
        isinstance(key, str)
        and _FILE.fullmatch(key)
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value >= 0
        for key, value in measured.items()
    ):
        raise ValueError("CARBON_SHARD_SECONDS must map test files to seconds >= 0")
    return digest.group(1), {key: float(value) for key, value in measured.items()}


def merge_runs(logs: list[str]) -> dict[str, float]:
    """Per file, the mean seconds over the runs (a run = the logs sharing one
    partition digest) that measured it. Within a run each file is on one shard."""
    runs: dict[str, dict[str, float]] = {}
    for text in logs:
        digest, measured = parse_log(text)
        run = runs.setdefault(digest, {})
        for path, value in measured.items():
            if path in run:
                raise ValueError(f"{path} appears on two shards of one run ({digest})")
            run[path] = value
    totals: dict[str, list[float]] = {}
    for run in runs.values():
        for path, value in run.items():
            totals.setdefault(path, []).append(value)
    return {path: round(sum(v) / len(v), 2) for path, v in sorted(totals.items())}


def build_document(
    seconds: dict[str, float], source: str, previous: Path | None
) -> dict:
    """The weights document, carrying the previous lane data over unchanged."""
    document: dict = {"source": source}
    if previous is not None and previous.is_file():
        old = json.loads(previous.read_text(encoding="utf-8"))
        for key in ("lane_source", "lane_seconds"):
            if key in old:
                document[key] = old[key]
    document["seconds"] = seconds
    return document


def shard_loads(
    shards: list[list[str]], truth: dict[str, float], lanes: dict[int, float]
) -> list[float]:
    """Actual seconds per shard: the truth for each file, plus the shard's lanes."""
    loads = [0.0] * len(shards)
    for lane, seconds in lanes.items():
        loads[lane % len(shards)] += seconds
    for index, shard in enumerate(shards):
        loads[index] += sum(truth[path] for path in shard)
    return loads


def simulate(weights: Path, assigned: Path | None, count: int) -> dict[str, object]:
    """The balance `assigned` weights (default: `weights` itself) give when the
    measurements in `weights` are the truth. Files `assigned` never measured use its
    own fallback."""
    truth = ci_shard.load_measured(weights)
    lanes = ci_shard.load_lanes(weights)
    basis = ci_shard.load_measured(assigned or weights)
    counts = {path: 1 for path in truth}  # one "test" each: the fallback's unit
    plan = ci_shard.partition(
        ci_shard.file_weights(counts, basis),
        count,
        ci_shard.load_lanes(assigned or weights),
    )
    loads = shard_loads(plan, truth, lanes)
    ideal = (sum(truth.values()) + sum(lanes.values())) / count
    return {
        "files": len(truth),
        "measured_by_assigned": len([p for p in truth if p in basis]),
        "shard_minutes": [round(load / 60, 1) for load in loads],
        "critical_path_minutes": round(max(loads) / 60, 1),
        "ideal_minutes": round(ideal / 60, 1),
        "spread": round(max(loads) / min(loads), 2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="weights from shard logs")
    build.add_argument("logs", nargs="+", type=Path)
    build.add_argument("--source", required=True)
    build.add_argument("--out", type=Path, default=ci_shard.WEIGHTS_PATH)
    build.add_argument("--lanes", type=Path, help="take lane data from this file")
    check = sub.add_parser("simulate", help="the balance a weights file gives")
    check.add_argument("--weights", type=Path, default=ci_shard.WEIGHTS_PATH)
    check.add_argument("--assigned", type=Path)
    check.add_argument("--count", type=int, default=6)
    args = parser.parse_args(argv)
    if args.command == "build":
        seconds = merge_runs([path.read_text(encoding="utf-8") for path in args.logs])
        document = build_document(seconds, args.source, args.lanes or args.out)
        args.out.write_text(
            json.dumps(document, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(
            f"{len(seconds)} files, {sum(seconds.values()) / 60:.1f} measured minutes"
        )
        return 0
    print(json.dumps(simulate(args.weights, args.assigned, args.count), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
