"""Split the default CPU suite across parallel CI runners, one test file at a time.

`ci.sh` loads this plugin only for its sharded CPU lane:

    CARBON_TEST_SHARD=<index>/<count> ./scripts/dev/test.sh -p scripts.dev.ci_shard

Every runner collects the whole suite, so a file that fails to collect still
fails every shard. Each runner then keeps only the files assigned to it. The
assignment is a pure function of the collected files and the committed weights,
so all runners compute the same partition, and every file runs on exactly one
shard. Whole files move together: module and class fixtures, and any ordering
inside a file, behave as they do in one serial run.

Balance comes from measured seconds per file (`ci_shard_weights.json`). A file
without a measurement weighs its test count times the measured mean seconds per
test. At the end each shard prints its basis (files, tests, the partition
digest every shard must share) and the seconds each of its files took, so the
weights can be refreshed from any run.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path

import pytest

ENVIRONMENT = "CARBON_TEST_SHARD"
WEIGHTS_PATH = Path(__file__).with_name("ci_shard_weights.json")
_SPEC = re.compile(r"([0-9]+)/([1-9][0-9]*)")


def parse_shard(value: str) -> tuple[int, int]:
    """`<index>/<count>` with 0 <= index < count; anything else is refused."""
    match = _SPEC.fullmatch(value.strip()) if isinstance(value, str) else None
    if match is None:
        raise ValueError(f"{ENVIRONMENT} must be <index>/<count>, not {value!r}")
    index, count = int(match.group(1)), int(match.group(2))
    if index >= count:
        raise ValueError(f"{ENVIRONMENT} index {index} is not below count {count}")
    return index, count


def file_weights(
    counts: Mapping[str, int], measured: Mapping[str, float]
) -> dict[str, float]:
    """Measured seconds where known; otherwise test count times the measured
    mean seconds per test (1.0 when nothing collected here was measured)."""
    known = [path for path in counts if path in measured]
    tests = sum(counts[path] for path in known)
    mean = sum(measured[path] for path in known) / tests if tests else 1.0
    return {
        path: float(measured[path]) if path in measured else counts[path] * mean
        for path in counts
    }


def partition(weights: Mapping[str, float], count: int) -> list[list[str]]:
    """Heaviest file first onto the lightest shard. Ties break on the path and
    the shard index, so the result depends only on the inputs."""
    if count < 1:
        raise ValueError("count must be at least 1")
    loads = [0.0] * count
    shards: list[list[str]] = [[] for _ in range(count)]
    for path in sorted(weights, key=lambda item: (-weights[item], item)):
        target = min(range(count), key=lambda shard: (loads[shard], shard))
        shards[target].append(path)
        loads[target] += weights[path]
    return shards


def partition_digest(shards: list[list[str]]) -> str:
    text = json.dumps([sorted(shard) for shard in shards], separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def load_measured(path: Path = WEIGHTS_PATH) -> dict[str, float]:
    if not path.is_file():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    seconds = document.get("seconds") if isinstance(document, dict) else None
    if not isinstance(seconds, dict) or not all(
        isinstance(key, str)
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value >= 0
        for key, value in seconds.items()
    ):
        raise ValueError(f"{path} must hold {{'seconds': {{path: seconds >= 0}}}}")
    return {key: float(value) for key, value in seconds.items()}


def _file_of(item: pytest.Item) -> str:
    return item.nodeid.split("::", 1)[0]


_state: dict[str, object] = {}


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[pytest.Item]
) -> None:
    value = os.environ.get(ENVIRONMENT)
    if value is None:
        raise pytest.UsageError(
            f"scripts.dev.ci_shard is loaded but {ENVIRONMENT} is unset"
        )
    try:
        index, count = parse_shard(value)
    except ValueError as error:
        raise pytest.UsageError(str(error)) from None
    counts = Counter(_file_of(item) for item in items)
    shards = partition(file_weights(counts, load_measured()), count)
    mine = set(shards[index])
    kept = [item for item in items if _file_of(item) in mine]
    if not kept:
        raise pytest.UsageError(
            f"shard {index}/{count} received no tests from {len(counts)} files"
        )
    deselected = [item for item in items if _file_of(item) not in mine]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = kept
    _state.update(
        index=index,
        count=count,
        files=len(mine),
        all_files=len(counts),
        tests=len(kept),
        all_tests=sum(counts.values()),
        digest=partition_digest(shards),
        seconds=defaultdict(float),
    )


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    seconds = _state.get("seconds")
    if isinstance(seconds, defaultdict):
        seconds[report.nodeid.split("::", 1)[0]] += report.duration


def pytest_terminal_summary(terminalreporter) -> None:
    if "index" not in _state:
        return
    write = terminalreporter.write_line
    write(
        f"{ENVIRONMENT} {_state['index']}/{_state['count']}: "
        f"{_state['files']} of {_state['all_files']} files, "
        f"{_state['tests']} of {_state['all_tests']} tests, "
        f"partition {_state['digest']}"
    )
    seconds = _state["seconds"]
    timings = {path: round(seconds[path], 2) for path in sorted(seconds)}
    write("CARBON_SHARD_SECONDS " + json.dumps(timings, separators=(",", ":")))
