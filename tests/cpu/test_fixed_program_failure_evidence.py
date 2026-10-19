"""Private fixed-program observations are bounded, owner-bound, and fail soft."""

import json
import os
import time
from types import SimpleNamespace

import pytest
from test_fixed_practice_failure_diagnostics import harness as _runner_harness

from carbon.development_session import research_carrier as carrier
from carbon.reconstruction.worker import watchdog
from carbon.reconstruction.worker.docker_runtime import _canonical
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure, tagged_sha256

harness = _runner_harness  # pytest discovers the existing fixture by this name


LAUNCH = "sha256:" + "1" * 64
IMAGE = "sha256:" + "2" * 64
NAME = "carbon-d4-" + LAUNCH[7:31]
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
    cli = ProbeCLI(
        state={
            "launch_digest": LAUNCH,
            "image_id": IMAGE,
            "running": False,
            "oom_killed": True,
            "exit_code": 137,
        }
    )
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
    assert (
        carrier._retain_fixed_program_evidence(tmp_path, "public-result.json", value)
        is None
    )
    assert not list(tmp_path.iterdir())
    filename = "private-program-failure-evidence.json"
    digest = carrier._retain_fixed_program_evidence(tmp_path, filename, value)
    assert isinstance(digest, str) and digest.startswith("sha256:")
    assert json.loads((tmp_path / filename).read_bytes()) == value
    assert (
        carrier._retain_fixed_program_evidence(
            tmp_path, "private-program-baseline.json", {"large": "x" * 4096}
        )
        is None
    )
    assert not (tmp_path / "private-program-baseline.json").exists()
    monkeypatch.setattr(
        carrier, "write_once", lambda *args: (_ for _ in ()).throw(OSError("disk"))
    )
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


def _watchdog_intent(tmp_path, *, deadline=123.0, changes=None):
    request = {"provenance": carrier.LIBRARY_PREP_PROVENANCE}
    identity = {
        "owner": "fixture-owner",
        "identity": "fixture-child",
        "request": request,
    }
    launch = tagged_sha256(_canonical(identity))
    name = "carbon-d4-" + launch[7:31]
    operation = tmp_path / ("operation-" + launch[7:])
    operation.mkdir()
    intent = {
        **identity,
        "launch": launch,
        "container": name,
        "deadline_unix": deadline,
    }
    intent.update(changes or {})
    path = operation / "intent.json"
    path.write_bytes(_canonical(intent))
    return path, name, launch


@pytest.mark.parametrize(
    "provenance", [carrier.LIBRARY_PREP_PROVENANCE, "BATTERY_PUBLIC_PRACTICE"]
)
@pytest.mark.parametrize(
    "diagnostic,expected_exit",
    [
        (b"exit=7\nstderr:\nPRIVATE_SECRET", 7),
        (b"exit=137\nstderr:\nPRIVATE_SECRET", 137),
        (b"exit=256\nstderr:\nPRIVATE_SECRET", None),
        (b"exit=-9\nstderr:\nPRIVATE_SECRET", None),
        (b"PRIVATE_SECRET exit=1\n", None),
    ],
)
def test_export_failure_captures_only_closed_private_exit_and_owned_observation(
    harness, monkeypatch, provenance, diagnostic, expected_exit
):
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=diagnostic)
    harness.fail_stage, harness.error = "EXPORT", original
    observed = []

    def observation(cli, **arguments):
        observed.append(arguments)
        harness.events.append("PRIVATE_OBSERVATION")
        assert 0 < arguments["deadline"] - time.monotonic() <= 1
        return {"status": "UNKNOWN", "state": None, "memory": None}

    monkeypatch.setattr(carrier, "_fixed_program_container_observation", observation)
    with pytest.raises(WorkerFailure) as caught:
        harness.run(provenance=provenance)
    assert caught.value is original
    assert harness.events.count("EXPORT") == harness.events.count("CLEANUP") == 1
    assert harness.events.index("EXPORT") < harness.events.index(
        "PRIVATE_OBSERVATION", harness.events.index("EXPORT")
    )
    assert harness.events[-1] == "ABSENCE_QUERY"
    paths = list(
        harness.ledger.root.glob("operation-*/private-export-failure-evidence.json")
    )
    assert len(paths) == 1
    raw = paths[0].read_bytes()
    value = json.loads(raw)
    assert len(raw) <= 4096 and b"PRIVATE_SECRET" not in raw
    assert set(value) == {
        "schema",
        "launch_digest",
        "observed_unix",
        "export_timeout_seconds",
        "export_deadline_reached",
        "observed_exec_exit",
        "observation",
        "interpretation",
    }
    assert value["schema"] == "carbon.autoresearch.export-failure-evidence.v1"
    assert value["observed_exec_exit"] == expected_exit
    assert value["observation"] == {"status": "UNKNOWN", "state": None, "memory": None}
    assert observed[-1]["launch_digest"] == value["launch_digest"]
    assert observed[-1]["container_name"] == "carbon-d4-" + value["launch_digest"][7:31]
    assert observed[-1]["image_id"] == IMAGE
    fixed = json.loads((paths[0].parent / "failure-EXPORT.json").read_bytes())
    assert (
        fixed["stage"] == "EXPORT" and fixed["worker_code"] == WorkerCode.RUNTIME.value
    )
    assert not (paths[0].parent / "result.json").exists()


@pytest.mark.parametrize("failure", ["observation", "write"])
def test_export_observation_or_write_failure_keeps_original_exception_and_cleanup(
    harness, monkeypatch, failure
):
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=7\n")
    harness.fail_stage, harness.error = "EXPORT", original
    if failure == "observation":
        monkeypatch.setattr(
            carrier,
            "_fixed_program_container_observation",
            lambda *args, **kwargs: (_ for _ in ()).throw(OSError("fixture")),
        )
    else:
        prior_write = carrier.write_once

        def write(path, raw):
            if path.name == "private-export-failure-evidence.json":
                raise OSError("fixture")
            return prior_write(path, raw)

        monkeypatch.setattr(carrier, "write_once", write)
    with pytest.raises(WorkerFailure) as caught:
        harness.run()
    assert caught.value is original
    assert harness.events.count("CLEANUP") == harness.events.count("ABSENCE_QUERY") == 1
    assert not list(
        harness.ledger.root.glob("operation-*/private-export-failure-evidence.json")
    )


def test_untrusted_export_failure_never_runs_private_observation(harness, monkeypatch):
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=7\n")
    harness.fail_stage, harness.error = "EXPORT", original
    observation = lambda *args, **kwargs: pytest.fail("untrusted private probe")
    monkeypatch.setattr(carrier, "_fixed_program_container_observation", observation)
    with pytest.raises(WorkerFailure) as caught:
        harness.run(provenance="UNTRUSTED_FIXTURE")
    assert caught.value is original
    assert harness.events.count("CLEANUP") == 1
    assert not list(
        harness.ledger.root.glob("operation-*/private-export-failure-evidence.json")
    )


def test_watchdog_records_only_owned_deadline_request(tmp_path):
    path, name, launch = _watchdog_intent(tmp_path)
    watchdog._retain_deadline_request(path, name, launch, 123.0)
    record = json.loads(
        (path.parent / "private-watchdog-observation.json").read_bytes()
    )
    assert record["schema"] == "carbon.autoresearch.watchdog-observation.v1"
    assert record["launch_digest"] == launch
    assert record["deadline_unix"] == 123.0
    assert record["action"] == "DEADLINE_CLEANUP_REQUESTED"
    assert set(record) == {
        "schema",
        "launch_digest",
        "observed_unix",
        "deadline_unix",
        "action",
        "interpretation",
    }
    raw = (path.parent / "private-watchdog-observation.json").read_bytes()
    assert b"fixture-owner" not in raw and b"fixture-child" not in raw
    if os.name != "nt":
        mode = (path.parent / "private-watchdog-observation.json").stat().st_mode
        assert mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "changes,deadline_shift",
    [
        ({"launch": "sha256:" + "f" * 64}, 0),
        ({"container": "carbon-d4-other"}, 0),
        ({"deadline_unix": 124.0}, 0),
        ({"request": {"provenance": "MINER_SELF_REPORTED"}}, 0),
        ({"identity": "changed-child"}, 0),
        ({}, 1),
    ],
)
def test_watchdog_rejects_mismatched_intent_without_record(
    tmp_path, changes, deadline_shift
):
    path, name, launch = _watchdog_intent(tmp_path, changes=changes)
    watchdog._retain_deadline_request(path, name, launch, 123.0 + deadline_shift)
    assert not (path.parent / "private-watchdog-observation.json").exists()


def test_watchdog_legacy_and_optional_intent_cleanup_survive_observation_failure(
    tmp_path, monkeypatch
):
    path, name, launch = _watchdog_intent(tmp_path)
    removed = []
    monkeypatch.setattr(watchdog, "DockerCLI", lambda: object())
    monkeypatch.setattr(watchdog.time, "time", lambda: 124.0)
    monkeypatch.setattr(
        watchdog,
        "remove_exact_container",
        lambda **kwargs: removed.append(
            (kwargs["container_name"], kwargs["launch_digest"])
        ),
    )
    assert watchdog.main([name, launch, "123.0"]) == 0
    assert not (path.parent / "private-watchdog-observation.json").exists()
    assert watchdog.main([name, launch, "123.0", str(path)]) == 0
    assert (path.parent / "private-watchdog-observation.json").exists()
    monkeypatch.setattr(
        watchdog,
        "_retain_deadline_request",
        lambda *args: (_ for _ in ()).throw(OSError("private storage unavailable")),
    )
    assert watchdog.main([name, launch, "123.0", str(path)]) == 0
    assert removed == [(name, launch)] * 3
