"""The canonical CPU suite split across CI runners (scripts/dev/ci_shard.py).

The property that matters is coverage: every collected test file runs on
exactly one shard, every shard computes the same partition, and a
misconfigured shard fails instead of running nothing.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.dev import ci_shard

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("value, expected", [("0/1", (0, 1)), ("7/8", (7, 8))])
def test_a_shard_is_index_over_count(value, expected):
    assert ci_shard.parse_shard(value) == expected


@pytest.mark.parametrize("value", ["", "8/8", "1/0", "-1/4", "a/4", "3", "1/2/3"])
def test_a_malformed_shard_is_refused(value):
    with pytest.raises(ValueError):
        ci_shard.parse_shard(value)


def test_every_file_lands_on_exactly_one_shard():
    rng = random.Random(7)
    weights = {f"tests/cpu/test_{n}.py": rng.uniform(0.1, 120) for n in range(345)}
    for count in (1, 2, 3, 8, 13):
        shards = ci_shard.partition(weights, count)
        assigned = [path for shard in shards for path in shard]
        assert sorted(assigned) == sorted(weights)
        assert len(assigned) == len(set(assigned))
        # Greedy balance: no shard exceeds the mean by more than one file.
        loads = [sum(weights[path] for path in shard) for shard in shards]
        assert max(loads) <= sum(loads) / count + max(weights.values())


def test_the_partition_depends_only_on_its_inputs():
    weights = {f"t{n}.py": float(n % 5) for n in range(40)}
    reordered = dict(reversed(list(weights.items())))
    first = ci_shard.partition(weights, 8)
    assert ci_shard.partition(reordered, 8) == first
    assert ci_shard.partition_digest(first) == ci_shard.partition_digest(
        ci_shard.partition(reordered, 8)
    )


def test_unmeasured_files_weigh_their_tests_at_the_measured_rate():
    weights = ci_shard.file_weights({"a.py": 10, "b.py": 4}, {"a.py": 20.0})
    assert weights == {"a.py": 20.0, "b.py": 8.0}
    assert ci_shard.file_weights({"c.py": 3}, {}) == {"c.py": 3.0}


@pytest.mark.parametrize(
    "document",
    ['{"seconds": {"a.py": -1}}', '{"seconds": {"a.py": true}}', "[]", '{"x": 1}'],
)
def test_a_malformed_weights_file_is_refused(tmp_path, document):
    path = tmp_path / "weights.json"
    path.write_text(document)
    with pytest.raises(ValueError):
        ci_shard.load_measured(path)


def test_the_committed_weights_file_is_well_formed():
    if ci_shard.WEIGHTS_PATH.is_file():
        assert ci_shard.load_measured()
    else:
        assert ci_shard.load_measured() == {}


def _suite(tmp_path: Path) -> Path:
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "pytest.ini").write_text("[pytest]\n")
    for n in range(6):
        tests = "\n".join(f"def test_{n}_{k}():\n    pass\n" for k in range(n + 1))
        (suite / f"test_file_{n}.py").write_text(tests)
    return suite


def _run(suite: Path, shard: str | None) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value for key, value in os.environ.items() if key != ci_shard.ENVIRONMENT
    }
    if shard is not None:
        environment[ci_shard.ENVIRONMENT] = shard
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "scripts.dev.ci_shard",
            "-p",
            "no:cacheprovider",
            "-c",
            str(suite / "pytest.ini"),
            "--rootdir",
            str(suite),
            "-rA",
            str(suite),
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _passed(output: str) -> set[str]:
    return {
        line.split()[1] for line in output.splitlines() if line.startswith("PASSED ")
    }


def test_shards_run_every_test_exactly_once_and_report_their_basis(tmp_path):
    suite = _suite(tmp_path)
    runs = [_run(suite, f"{index}/3") for index in range(3)]
    for run in runs:
        assert run.returncode == 0, run.stdout + run.stderr
    passed = [_passed(run.stdout) for run in runs]
    everything = set().union(*passed)
    assert len(everything) == sum(n + 1 for n in range(6)) == 21
    assert sum(len(shard) for shard in passed) == 21
    files = [{test.split("::")[0] for test in shard} for shard in passed]
    assert all(
        left.isdisjoint(right) for left in files for right in files if left is not right
    )
    digests = set()
    for run in runs:
        [summary] = [
            line
            for line in run.stdout.splitlines()
            if line.startswith("CARBON_TEST_SHARD ")
        ]
        assert " of 6 files, " in summary and " of 21 tests, " in summary
        digests.add(summary.rsplit(" ", 1)[1])
        [timings] = [
            line
            for line in run.stdout.splitlines()
            if line.startswith("CARBON_SHARD_SECONDS ")
        ]
        assert json.loads(timings.split(" ", 1)[1])
    assert len(digests) == 1  # every shard computed the same partition


def test_a_loaded_plugin_without_a_shard_fails(tmp_path):
    run = _run(_suite(tmp_path), None)
    assert run.returncode != 0
    assert "CARBON_TEST_SHARD is unset" in run.stdout + run.stderr


def test_a_shard_with_no_files_fails(tmp_path):
    run = _run(_suite(tmp_path), "7/8")
    assert run.returncode != 0
    assert "received no tests" in run.stdout + run.stderr


def test_ci_runs_every_lane_on_exactly_one_shard():
    source = (REPOSITORY_ROOT / "scripts/dev/ci.sh").read_text(encoding="utf-8")
    assert 'shard_spec="${CARBON_CI_SHARD:-0/1}"' in source
    assert 'CARBON_TEST_SHARD="${shard_index}/${shard_count}"' in source
    assert "./scripts/dev/test.sh -p scripts.dev.ci_shard" in source
    lanes = {
        "tests/invariants -m invariant -q": "on_shard 0",
        "tests/cpu/test_package_installation.py": "on_shard 0",
        "tests/science -q": "on_shard 1",
        "tests/cpu/test_battery_torch_backend.py": "on_shard 2",
        "tests/service/test_standard_mcp_stdio.py": "on_shard 3",
        "scripts/dev/miner_launchpad/browser_smoke.py": "on_shard 4",
        "tests/cpu/test_code_authority.py -q": "on_shard 0",
    }
    for lane, guard in lanes.items():
        before = source[: source.index(lane)]
        assert before.rindex(guard) > before.rindex("\nfi\n"), lane


@pytest.mark.parametrize("spec", ["8/8", "x", "1/0"])
def test_ci_refuses_a_malformed_shard(spec):
    run = subprocess.run(
        ["bash", str(REPOSITORY_ROOT / "scripts/dev/ci.sh")],
        env={**os.environ, "CARBON_CI_SHARD": spec},
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 2
    assert "Invalid CARBON_CI_SHARD" in run.stderr
