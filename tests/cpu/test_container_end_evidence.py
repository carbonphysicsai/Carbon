"""A fixed worker that ends by itself leaves its State and last output, privately."""

import json
import os
import time
from types import SimpleNamespace

import pytest
from test_fixed_practice_failure_diagnostics import harness as _runner_harness

from carbon.development_session import research_carrier as carrier
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

harness = _runner_harness  # pytest discovers the existing fixture by this name

LAUNCH = "sha256:" + "1" * 64
NAME = "carbon-d4-" + LAUNCH[7:31]
STATE = {
    "Status": "exited",
    "Running": False,
    "ExitCode": 1,
    "OOMKilled": False,
    "Error": "",
    "StartedAt": "2026-10-20T13:32:19.123456789Z",
    "FinishedAt": "2026-10-20T13:32:20.654321Z",
}
TRACEBACK = b"Traceback (most recent call last):\n  File x\nOSError: [Errno 5] boom\n"


class EndCLI:
    def __init__(self, *, state=None, stdout=b"", stderr=TRACEBACK, error=None):
        self.state = STATE if state is None else state
        self.stdout, self.stderr, self.error = stdout, stderr, error
        self.calls = []

    def json(self, arguments, *, timeout):
        self.calls.append(("inspect", arguments, timeout))
        if self.error == "inspect":
            raise WorkerFailure(WorkerCode.UNAVAILABLE)
        return self.state

    def run(self, arguments, *, timeout):
        self.calls.append(("logs", arguments, timeout))
        if self.error == "logs":
            raise WorkerFailure(WorkerCode.RUNTIME)
        return SimpleNamespace(stdout=self.stdout, stderr=self.stderr)


def end(cli, *, name=NAME, launch=LAUNCH, deadline=None):
    return carrier._fixed_program_container_end(
        cli,
        container_name=name,
        launch_digest=launch,
        deadline=time.monotonic() + 2 if deadline is None else deadline,
    )


def test_a_container_that_ended_gives_state_and_the_last_output():
    cli = EndCLI()
    result = end(cli)
    assert result["schema"] == "carbon.autoresearch.container-end-evidence.v1"
    assert result["launch_digest"] == LAUNCH
    assert result["state"] == {
        "status": "exited",
        "exit_code": 1,
        "oom_killed": False,
        "daemon_error": "",
        "started_at": STATE["StartedAt"],
        "finished_at": STATE["FinishedAt"],
    }
    assert result["log_tail"] == TRACEBACK.decode()
    assert "cause" not in json.dumps(result["state"])
    assert [kind for kind, _, _ in cli.calls] == ["inspect", "logs"]
    assert cli.calls[1][1] == ["logs", "--tail", "40", NAME]
    assert all(0 < timeout <= 1 for _, _, timeout in cli.calls)


def test_a_running_container_gives_nothing_and_never_reads_its_log():
    cli = EndCLI(state={**STATE, "Running": True, "Status": "running"})
    assert end(cli) is None
    assert [kind for kind, _, _ in cli.calls] == ["inspect"]


@pytest.mark.parametrize(
    "name,launch",
    [
        ("carbon-d4-" + "f" * 24, LAUNCH),
        (NAME, "sha256:" + "1" * 63),
        (NAME, "sha256:" + "G" * 64),
    ],
)
def test_only_the_launches_own_container_is_read(name, launch):
    cli = EndCLI()
    assert end(cli, name=name, launch=launch) is None
    assert cli.calls == []


def test_no_budget_reads_nothing():
    cli = EndCLI()
    assert end(cli, deadline=time.monotonic() - 1) is None
    assert cli.calls == []


def test_unreadable_state_gives_nothing_and_unreadable_log_keeps_state():
    assert end(EndCLI(error="inspect")) is None
    partial = end(EndCLI(error="logs"))
    assert partial["state"]["exit_code"] == 1 and partial["log_tail"] is None


def test_malformed_fields_become_unknown_and_text_stays_closed():
    hostile = {
        **STATE,
        "Status": "../etc/passwd",
        "ExitCode": 256,
        "OOMKilled": 1,
        "StartedAt": "yesterday",
        "FinishedAt": None,
        "Error": "bad\x00\x1b[31m " + "x" * 400,
    }
    state = end(EndCLI(state=hostile, stderr=b"\xff\x00\x1b[2Jtail\n"))
    assert state["state"]["status"] is None
    assert state["state"]["exit_code"] is None
    assert state["state"]["oom_killed"] is None
    assert (
        state["state"]["started_at"] is None and state["state"]["finished_at"] is None
    )
    error = state["state"]["daemon_error"]
    assert len(error) <= 200 and all(32 <= ord(c) < 127 for c in error)
    assert all(32 <= ord(c) < 127 or c == "\n" for c in state["log_tail"])
    assert state["log_tail"].endswith("tail\n")


def test_the_log_tail_is_capped_and_the_record_fits_the_private_limit(tmp_path):
    result = end(EndCLI(stderr=b"line with \n newlines\n" * 500))
    assert len(result["log_tail"]) <= carrier._CONTAINER_END_LOG_BYTES
    digest = carrier._retain_fixed_program_evidence(
        tmp_path, "private-container-end-evidence.json", result
    )
    assert digest is not None
    assert len((tmp_path / "private-container-end-evidence.json").read_bytes()) <= 4096


@pytest.mark.parametrize(
    "stage,provenance",
    [
        ("EXPORT", carrier.LIBRARY_PREP_PROVENANCE),
        ("EXPORT", "BATTERY_PUBLIC_PRACTICE"),
        ("PROGRAM", carrier.LIBRARY_PREP_PROVENANCE),
    ],
)
def test_a_failed_fixed_stage_keeps_the_end_evidence_and_the_original_failure(
    harness, monkeypatch, stage, provenance
):
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=1\n")
    harness.fail_stage, harness.error = stage, original
    seen = []

    def fake_end(cli, **arguments):
        seen.append(arguments)
        return {"schema": "carbon.autoresearch.container-end-evidence.v1", "x": 1}

    monkeypatch.setattr(carrier, "_fixed_program_container_end", fake_end)
    with pytest.raises(WorkerFailure) as caught:
        harness.run(provenance=provenance)
    assert caught.value is original
    assert harness.events.count("CLEANUP") == 1
    paths = list(
        harness.ledger.root.glob("operation-*/private-container-end-evidence.json")
    )
    assert len(paths) == 1 and len(seen) == 1
    assert seen[0]["container_name"] == "carbon-d4-" + seen[0]["launch_digest"][7:31]
    assert 0 < seen[0]["deadline"] - time.monotonic() <= 2
    assert not (paths[0].parent / "result.json").exists()
    assert not (paths[0].parent / "snapshot").exists()
    if os.name != "nt":
        assert paths[0].stat().st_mode & 0o777 == 0o600


def test_a_failing_end_read_or_write_keeps_the_original_failure_and_cleanup(
    harness, monkeypatch
):
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=1\n")
    harness.fail_stage, harness.error = "EXPORT", original
    monkeypatch.setattr(
        carrier,
        "_fixed_program_container_end",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("fixture")),
    )
    with pytest.raises(WorkerFailure) as caught:
        harness.run()
    assert caught.value is original
    assert harness.events.count("CLEANUP") == harness.events.count("ABSENCE_QUERY") == 1
    assert not list(
        harness.ledger.root.glob("operation-*/private-container-end-evidence.json")
    )


def test_untrusted_failure_never_reads_the_container_end(harness, monkeypatch):
    original = WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=1\n")
    harness.fail_stage, harness.error = "EXPORT", original
    monkeypatch.setattr(
        carrier,
        "_fixed_program_container_end",
        lambda *args, **kwargs: pytest.fail("untrusted private probe"),
    )
    with pytest.raises(WorkerFailure) as caught:
        harness.run(provenance="UNTRUSTED_FIXTURE")
    assert caught.value is original
    assert not list(
        harness.ledger.root.glob("operation-*/private-container-end-evidence.json")
    )
