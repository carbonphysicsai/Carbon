"""The producer host's solve parallelism reaches the truth image's command
(the owner's request, 2026-10-07): `tuning solve` and `producer solve` take
`--workers` and `--timeout-s`, defaulting to the earlier 7 workers and
1,200 s. No container runs: the command is captured."""

from __future__ import annotations

import subprocess

import pytest

from carbon.battery import truth_env
from carbon.challenge_validator import tuning


@pytest.fixture
def captured(monkeypatch):
    seen = {}
    real = truth_env.solve_command

    def solve_command(target, workdir, **options):
        seen.update(options)
        return real(target, workdir, **options)

    class Done:
        returncode = 0

    monkeypatch.setattr(truth_env, "solve_command", solve_command)
    monkeypatch.setattr(subprocess, "run", lambda command, check: Done())
    return seen


def work(tmp_path):
    path = tmp_path / "quiz"
    path.mkdir(mode=0o700)
    return path


@pytest.mark.parametrize(
    ("flags", "workers", "timeout_s"),
    [([], 7, 1200.0), (["--workers", "12", "--timeout-s", "900"], 12, 900.0)],
)
def test_tuning_solve_passes_workers_and_timeout(
    tmp_path, captured, flags, workers, timeout_s
):
    argv = [
        "solve",
        "--work",
        str(work(tmp_path)),
        "--overlay",
        str(tmp_path / "overlay"),
    ]
    assert tuning.main(argv + flags) == 0
    assert captured["workers"] == workers and captured["timeout_s"] == timeout_s


def test_the_solve_command_carries_the_worker_count(tmp_path):
    command = truth_env.solve_command(
        tmp_path / "overlay", tmp_path, repository=".", workers=12, timeout_s=900.0
    )
    assert command[command.index("--workers") + 1] == "12"


def test_producer_solve_passes_workers_and_timeout(monkeypatch):
    from carbon.challenge_validator import producer as pr

    seen = {}

    class Fake:
        def solve(self, challenge, fingerprint, **options):
            seen.update(options)
            return {"returncode": 0}

    monkeypatch.setattr(
        pr.Producer, "from_config", classmethod(lambda cls, path: Fake())
    )
    argv = ["solve", "--config", "x", "--challenge", "c", "--fingerprint", "f"]
    assert pr.main(argv + ["--workers", "12", "--timeout-s", "900"]) == 0
    assert seen == {"workers": 12, "timeout_s": 900.0}
    seen.clear()
    assert pr.main(argv) == 0
    assert seen == {"workers": 7}  # each source keeps its own timeout
