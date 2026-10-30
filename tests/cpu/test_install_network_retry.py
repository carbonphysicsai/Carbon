"""G1 (bug hunt): a network cut during an install step is retried once and, if it persists, explained in plain words.

The installer's `network_step` is run in bash against fake step commands. Nothing is downloaded or built."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "scripts/install_miner.sh").read_text(encoding="utf-8")


def _function() -> str:
    start = SCRIPT.index("NETWORK_FAILURE_PATTERN=")
    end = SCRIPT.index("\n}\n", SCRIPT.index("network_step() {")) + 3
    return SCRIPT[start:end]


def _run(tmp_path, body: str, wait="0"):
    count = tmp_path / "count"
    count.write_text("0")
    script = (
        "set -euo pipefail\n"
        f"export CARBON_INSTALL_NETWORK_RETRY_WAIT={wait}\n"
        + _function()
        + f"\ncount={count.as_posix()}\n"
        # a subshell, like the external scripts the installer runs: its `exit` ends only the step
        + "step_cmd() (\n"
        + '  n=$(( $(cat "${count}") + 1 )); echo "${n}" > "${count}"\n'
        + body
        + "\n)\n"
        + 'network_step "step 4/6, building the worker image" step_cmd\n'
        + 'echo "AFTER rc=$?"\n'
    )
    done = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=False, timeout=60
    )
    return done, int(count.read_text())


BUILDKIT = (
    'echo "ERROR: failed to solve: failed to resolve reference '
    "docker.io/library/ubuntu@sha256:33ce...: failed to do request: Head https://registry-1.docker.io/v2/: "
    'dial tcp 1.2.3.4:443: i/o timeout" >&2; exit 1'
)


def test_a_success_runs_once_and_prints_nothing_extra(tmp_path):
    done, attempts = _run(tmp_path, "echo built; echo progress >&2")
    assert done.returncode == 0 and attempts == 1
    assert "AFTER rc=0" in done.stdout and "built" in done.stdout
    assert "network dropped" not in done.stderr and "progress" in done.stderr


def test_a_network_failure_that_clears_is_retried_once_and_the_install_goes_on(
    tmp_path,
):
    body = f'if [ "$n" = 1 ]; then {BUILDKIT}; fi; echo built'
    done, attempts = _run(tmp_path, body)
    assert done.returncode == 0 and attempts == 2, done.stderr
    assert "AFTER rc=0" in done.stdout
    assert (
        "Your network dropped while downloading (step 4/6, building the worker image)"
        in done.stderr
    )
    assert "Trying this step once more" in done.stderr
    assert "paused" not in done.stderr


def test_a_network_failure_that_persists_stops_with_plain_words_after_one_retry(
    tmp_path,
):
    done, attempts = _run(tmp_path, BUILDKIT)
    assert done.returncode == 2 and attempts == 2
    assert "AFTER" not in done.stdout  # the installer stopped
    assert (
        "Carbon install paused: your network dropped while downloading (step 4/6, building the worker image)."
        in done.stderr
    )
    assert (
        "Nothing is broken; run the same command again and it continues." in done.stderr
    )


@pytest.mark.parametrize(
    "line",
    [
        "Temporary failure in name resolution",
        "curl: (6) Could not resolve host: astral.sh",
        "TLS handshake timeout",
        "read tcp 10.0.0.2:5555->1.2.3.4:443: connection reset by peer",
        "context deadline exceeded",
    ],
)
def test_other_network_wordings_are_recognised(tmp_path, line):
    done, attempts = _run(tmp_path, f'echo "{line}" >&2; exit 1')
    assert (
        done.returncode == 2
        and attempts == 2
        and "run the same command again" in done.stderr
    )


def test_a_failure_that_is_not_the_network_is_left_exactly_as_it_was(tmp_path):
    done, attempts = _run(
        tmp_path, 'echo "ERROR: Dockerfile parse error on line 3" >&2; exit 7'
    )
    assert (
        attempts == 1 and "AFTER" not in done.stdout
    )  # set -e stopped the script on the step's own status
    assert done.returncode == 7
    assert "Dockerfile parse error" in done.stderr and "network" not in done.stderr


def test_every_downloading_install_step_goes_through_it():
    for fragment in (
        'network_step "step 3/6, installing the locked environment" ./scripts/dev/bootstrap.sh',
        'network_step "step 4/6, pulling the released images"',
        'network_step "step 4/6, building the worker image" ./scripts/dev/c03_worker_image.sh',
        'network_step "step 4/6, building the PyTorch worker image"',
        'network_step "step 4/6, building the GPU worker image"',
        'network_step "step 4/6, building the PyTorch GPU worker image"',
        'network_step "step 4/6, building the analysis image"',
    ):
        assert fragment in SCRIPT, fragment


def test_the_wrapper_never_reads_the_background_pid_variable():
    """`$!` is unbound under `set -u` on bash builds that do not set it for a process substitution (Targon, 49 installer
    tests failed on it): the wrapper must not mention it."""
    assert "$!" not in _function() and "${!" not in _function()
