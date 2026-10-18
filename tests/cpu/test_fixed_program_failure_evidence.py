"""Private fixed-program observations are bounded, owner-bound, and fail soft."""

import json
import time
from types import SimpleNamespace

import pytest

from carbon.development_session import research_carrier as carrier
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure
from test_fixed_practice_failure_diagnostics import harness  # reuse closed runner fixture


LAUNCH = "sha256:" + "1" * 64
IMAGE = "sha256:" + "2" * 64
NAME = "carbon-d4-fixture"
COUNTERS = b"low 0\nhigh 0\nmax 3\noom 2\noom_kill 1\n4096\n2048\n"


class ProbeCLI:
    def __init__(self, *, state=None, counters=COUNTERS, error=None):
        self.state = state or {
            "launch_digest": LAUNCH,
            "image_id": IMAGE,
            "running": True,
            "oom_killed": False,
            "exit_code": 0,
        }
        self.counters = counters
        self.error = error
        self.calls = []

    def json(self, arguments, *, timeout):
        self.calls.append(("inspect", arguments, timeout))
        if self.error == "inspect":
            raise WorkerFailure(WorkerCode.UNAVAILABLE)
        return self.state

    def run(self, arguments, *, timeout):
        self.calls.append(("cgroup", arguments, timeout))
        if self.error == "cgroup":
            raise WorkerFailure(WorkerCode.RUNTIME)
        return SimpleNamespace(stdout=self.counters)


def observe(cli, *, deadline=None):
    return carrier._fixed_program_container_observation(
        cli,
        container_name=NAME,
        launch_digest=LAUNCH,
        image_id=IMAGE,
        deadline=time.monotonic() + 1 if deadline is None else deadline,
    )


def test_valid_counter_observation_is_data_not_cause():
    cli = ProbeCLI()
    result = observe(cli)
    assert result == {
        "status": "OBSERVED",
        "state": {"running": True, "oom_killed": False, "exit_code": 0},
        "memory": {
            "current_bytes": 2048,
            "peak_bytes": 4096,
            "events": {"oom": 2, "oom_kill": 1},
        },
    }
    assert [kind for kind, _, _ in cli.calls] == ["inspect", "cgroup"]
    assert all(0 < timeout <= 0.5 for _, _, timeout in cli.calls)
    assert b"cause" not in json.dumps(result).encode()


@pytest.mark.parametrize(
    "change",
    [
        {"launch_digest": "sha256:" + "3" * 64},
        {"image_id": "sha256:" + "3" * 64},
        {"running": 1},
        {"oom_killed": 1},
        {"exit_code": True},
        {"exit_code": 256},
        {"extra": "untrusted"},
    ],
)
def test_unowned_or_malformed_inspect_never_reaches_cgroup(change):
    cli = ProbeCLI()
    cli.state = {**cli.state, **change}
    assert observe(cli) == {"status": "UNKNOWN", "state": None, "memory": None}
    assert [kind for kind, _, _ in cli.calls] == ["inspect"]


@pytest.mark.parametrize(
    "counters",
    [
        b"oom 1\noom_kill -1\n4096\n2048\n",
        b"oom 1\noom_kill True\n4096\n2048\n",
        b"oom 1\noom_kill 1\n4096\nsecret\n",
        b"oom 1\noom_kill 1\noom_kill 2\n4096\n2048\n",
        b"oom 1\noom_kill 1\n4096\n2048\n" + b"x" * 4096,
    ],
)
def test_bad_counters_preserve_only_verified_state(counters):
    result = observe(ProbeCLI(counters=counters))
    assert result == {
        "status": "OBSERVED",
        "state": {"running": True, "oom_killed": False, "exit_code": 0},
        "memory": None,
    }


def test_stopped_container_skips_cgroup_and_zero_budget_skips_all_calls():
    cli = ProbeCLI(state={
        "launch_digest": LAUNCH,
        "image_id": IMAGE,
        "running": False,
        "oom_killed": True,
        "exit_code": 137,
    })
    assert observe(cli) == {
        "status": "OBSERVED",
        "state": {"running": False, "oom_killed": True, "exit_code": 137},
        "memory": None,
    }
    assert len(cli.calls) == 1
    no_budget = ProbeCLI()
    assert observe(no_budget, deadline=time.monotonic() - 1)["status"] == "UNKNOWN"
    assert no_budget.calls == []


@pytest.mark.parametrize("error,expected_calls", [("inspect", 1), ("cgroup", 2)])
def test_probe_errors_fail_soft(error, expected_calls):
    cli = ProbeCLI(error=error)
    result = observe(cli)
    assert len(cli.calls) == expected_calls
    assert result["status"] == ("UNKNOWN" if error == "inspect" else "OBSERVED")
    assert result["memory"] is None


def test_private_write_is_allowlisted_bounded_and_best_effort(tmp_path, monkeypatch):
    value = {"status": "UNKNOWN", "secret": "never-publish"}
    assert carrier._retain_fixed_program_evidence(tmp_path, "public-result.json", value) is None
    assert not list(tmp_path.iterdir())
    filename = "private-program-failure-evidence.json"
    digest = carrier._retain_fixed_program_evidence(tmp_path, filename, value)
    assert isinstance(digest, str) and digest.startswith("sha256:")
    assert json.loads((tmp_path / filename).read_bytes()) == value
    assert carrier._retain_fixed_program_evidence(
        tmp_path, "private-program-baseline.json", {"large": "x" * 4096}
    ) is None
    assert not (tmp_path / "private-program-baseline.json").exists()
    monkeypatch.setattr(carrier, "write_once", lambda *args: (_ for _ in ()).throw(OSError("disk")))
    assert carrier._retain_fixed_program_evidence(tmp_path, filename, value) is None


def test_failed_prep_preserves_original_worker_failure_when_private_write_fails(
    harness, monkeypatch
):
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=137\n")
    harness.fail_stage, harness.error = "PROGRAM", original
    original_write = carrier.write_once

    def private_write_fails(path, payload):
        if path.name.startswith("private-program-"):
            raise OSError("unavailable private evidence storage")
        return original_write(path, payload)

    monkeypatch.setattr(carrier, "write_once", private_write_fails)
    with pytest.raises(WorkerFailure) as caught:
        harness.run(provenance=carrier.LIBRARY_PREP_PROVENANCE)
    assert caught.value is original
    assert "CLEANUP" in harness.events
    assert not list(harness.ledger.root.glob("operation-*/private-program-*.json"))
