"""D3: failure and recovery, end to end, on the miner research carrier.

Every failure path here keeps three properties the owner set: the outcome is
typed truthfully (the miner's own program failing is not an infrastructure
failure, and the reverse), the full reservation is kept (absence of evidence is
not evidence of non-use), and cleanup is observed rather than assumed. Each
refusal or absence asserted is paired with a specimen showing the check fires.

Docker is replaced by a recording fake; nothing here starts a container.
"""

import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_miner_research_unlimited import ledger as unbudgeted_ledger

from carbon.development_session import miner_container, research_image
from carbon.development_session import research_carrier as carrier
from carbon.development_session.miner_container import (
    MinerOutputRefused,
    collect_outputs,
)
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_carrier import (
    MinerProgramFailure,
    reconcile_worker,
    request_cancel,
)
from carbon.miner_mcp.research import _requires_reconciliation
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure
from carbon.research import ResearchTaskState

IMAGE = SimpleNamespace(image_id="sha256:" + "b" * 64)
OWNER = "miner"


class FakeDocker:
    """Records every command; the miner's 'program' runs as a host callback."""

    def __init__(self, program=None, *, exec_error=None, state=None, inspect=True):
        self.program = program
        self.exec_error = exec_error
        self.state = state if state is not None else {"Running": True}
        self.inspect = inspect
        self.commands = []

    def run(self, arguments, *, timeout=30, accepted=(0,)):
        self.commands.append(list(arguments))
        return SimpleNamespace(stdout=b"", stderr=b"", returncode=0)

    def json(self, arguments, *, timeout=30):
        self.commands.append(list(arguments))
        if not self.inspect:
            raise WorkerFailure(WorkerCode.RUNTIME)
        return self.state

    def stream_kept(self, arguments, operation, *, timeout):
        # The miner lane keeps both streams, whatever the outcome (RSURF-D21).
        (operation / "stderr.txt").write_bytes(b"")
        return self.stream_to_file(
            arguments, operation / "stdout.txt", maximum=None, timeout=timeout
        )

    def stream_to_file(self, arguments, destination, *, maximum, timeout):
        self.commands.append(list(arguments))
        destination.write_bytes(b"")
        scratch = destination.parent / "scratch"
        (scratch / "output").mkdir(exist_ok=True)
        if self.program is not None:
            self.program(scratch / "output")
        if self.exec_error is not None:
            raise self.exec_error
        return 0

    def created(self):
        return any(c and c[0] == "create" for c in self.commands)


@pytest.fixture
def docker(monkeypatch):
    holder = {"cli": FakeDocker(), "removed": []}
    monkeypatch.setattr(carrier, "DockerCLI", lambda: holder["cli"])
    monkeypatch.setattr(
        carrier,
        "doctor",
        lambda **kwargs: SimpleNamespace(eligible=True, cpuset="0"),
    )
    monkeypatch.setattr(research_image, "verify_image", lambda image, cli: None)
    monkeypatch.setattr(carrier, "spawn_watchdog", lambda **kwargs: None)
    holder["reapers"] = []
    monkeypatch.setattr(
        carrier.liveness_reaper,
        "spawn_liveness_reaper",
        lambda **kwargs: holder["reapers"].append(kwargs),
    )
    monkeypatch.setattr(
        carrier,
        "remove_exact_container",
        lambda **kwargs: holder["removed"].append(kwargs["container_name"]),
    )
    monkeypatch.setattr(miner_container, "create_arguments", lambda run: ["create"])
    monkeypatch.setattr(miner_container, "inspect_isolation", lambda cli, run: {})
    return holder


def run(ledger, identity="run", *, seconds=None, miner_authored=True, **extra):
    return carrier._run(
        ledger,
        owner=OWNER,
        identity=identity,
        source="print('x')",
        files={},
        image=IMAGE,
        seconds=seconds,
        provenance="MINER_SELF_REPORTED",
        extra_resources={"research_trials": 1},
        miner_authored=miner_authored,
        **extra,
    )


def operation(ledger, identity="run"):
    (op,) = [o for o in ledger.status(owner=OWNER)["operations"] if o["id"] == identity]
    return op


# Gap 1: a terminal task over a RESERVED operation still needs reconciling.


def test_a_failed_task_over_a_reserved_operation_requires_reconciliation(tmp_path):
    ledger = unbudgeted_ledger(tmp_path)
    ledger.reserve(
        "task-1",
        owner=OWNER,
        phase="research",
        request={},
        resources={"research_trials": 1},
    )
    composition = SimpleNamespace(executor=SimpleNamespace(owner=OWNER, ledger=ledger))
    task = SimpleNamespace(
        state=ResearchTaskState.FAILED_INFRA, task_id=SimpleNamespace(value="task-1")
    )
    assert _requires_reconciliation(task, composition) is True
    # Specimen: the same task over a settled operation does not.
    ledger.finish(
        "task-1",
        owner=OWNER,
        state="FAILED_INFRA",
        actual={"research_trials": 1},
        result={},
    )
    assert _requires_reconciliation(task, composition) is False
    running = SimpleNamespace(state=ResearchTaskState.RUNNING, task_id=task.task_id)
    assert _requires_reconciliation(running, composition) is True


# Gap 2: an unbounded run reserves no milliseconds and is still a worker.


def _abandoned_unbounded_run(ledger, docker):
    """Reserve and write the intent as the carrier does, then stop dead."""

    def killed(*args, **kwargs):
        raise KeyboardInterrupt  # the supervisor dies mid-run; nothing settles

    docker["cli"].stream_to_file = killed
    with pytest.raises(KeyboardInterrupt):
        run(ledger, "unbounded", seconds=None)
    op = operation(ledger, "unbounded")
    assert op["state"] == "RESERVED"
    assert op["reservation"]["numerical_milliseconds"] == 0
    return op


def test_an_unbounded_run_is_reconciled_by_its_intent(tmp_path, docker):
    ledger = unbudgeted_ledger(tmp_path)
    op = _abandoned_unbounded_run(ledger, docker)
    result = reconcile_worker(ledger, owner=OWNER, identity="unbounded")
    assert result["state"] == "FAILED_INFRA" and result["cleanup_observed"]
    settled = operation(ledger, "unbounded")
    assert settled["state"] == "FAILED_INFRA"
    assert settled["actual"] == op["reservation"]  # the full reservation, no refund
    assert docker["removed"]  # cleanup was performed, then observed by `ps`


def test_the_launchpad_cleanup_reconciles_an_unbounded_run(tmp_path, docker):
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    ledger = unbudgeted_ledger(tmp_path)
    _abandoned_unbounded_run(ledger, docker)
    assert RunnerAdapter._cleanup(ledger) is True
    assert operation(ledger, "unbounded")["state"] == "FAILED_INFRA"


def test_the_launchpad_cleanup_never_calls_a_skipped_operation_clean(tmp_path):
    """An operation reconcile_worker cannot settle leaves cleanup unclean."""
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    ledger = unbudgeted_ledger(tmp_path)
    ledger.reserve(
        "no-intent",
        owner=OWNER,
        phase="research",
        request={},
        resources={"numerical_milliseconds": 0, "research_trials": 1},
    )
    with pytest.raises(ValueError, match="intent unavailable"):
        reconcile_worker(ledger, owner=OWNER, identity="no-intent")
    assert RunnerAdapter._cleanup(ledger) is False
    assert operation(ledger, "no-intent")["state"] == "RESERVED"


# Gap 3: the ledger never says SUCCEEDED while the task then fails.


def test_uncertain_cancellation_is_checked_before_the_ledger_finishes(
    tmp_path, docker, monkeypatch
):
    ledger = unbudgeted_ledger(tmp_path)

    def uncertain(*args, **kwargs):
        raise WorkerFailure(WorkerCode.CLEANUP)

    monkeypatch.setattr(carrier, "_cancel_active_intent", uncertain)
    real_collect = miner_container.collect_outputs

    def cancelled_while_collecting(scratch, snapshot):
        # After the last cancellation check, before the ledger records a result.
        request_cancel(ledger, owner=OWNER, identity="run")
        time.sleep(0.5)  # the watcher polls every 0.1 s and records its error
        return real_collect(scratch, snapshot)

    monkeypatch.setattr(miner_container, "collect_outputs", cancelled_while_collecting)
    with pytest.raises(ValueError, match="cancellation cleanup uncertain"):
        run(ledger)
    assert operation(ledger)["state"] == "RESERVED"


@pytest.mark.parametrize("seconds", [None, 3600])
def test_the_early_intent_records_the_miner_lanes_guard(tmp_path, docker, seconds):
    """The intent is written before staging, and it names what will remove the
    container if its owner cannot: the deadline watchdog, or the liveness
    reaper for an unbounded run, which is then started with that guard."""
    ledger = unbudgeted_ledger(tmp_path)
    run(ledger, seconds=seconds)
    (path,) = ledger.root.glob("operation-*/intent.json")
    intent = json.loads(path.read_bytes())
    if seconds is None:
        guard = carrier.liveness_reaper.controller_guard()
        assert intent["deadline_unix"] is None and intent["reaper"] == guard
        assert [r["guard"] for r in docker["reapers"]] == [guard]
    else:
        assert intent["reaper"] == {"kind": "DEADLINE"}
        assert docker["reapers"] == []


def test_without_a_cancellation_the_same_run_succeeds(tmp_path, docker):
    """Specimen: the path above reaches the ledger's finish when nothing fails."""
    ledger = unbudgeted_ledger(tmp_path)
    result = run(ledger)
    assert operation(ledger)["state"] == "SUCCEEDED"
    assert result["files"] == {}


# Gap 4: a failure before anything is created settles, keeping the reservation.


def test_an_ineligible_host_settles_failed_infra_with_nothing_created(
    tmp_path, docker, monkeypatch
):
    ledger = unbudgeted_ledger(tmp_path)
    monkeypatch.setattr(
        carrier,
        "doctor",
        lambda **kwargs: SimpleNamespace(eligible=False, cpuset=None),
    )
    with pytest.raises(ValueError, match="research host ineligible"):
        run(ledger)
    op = operation(ledger)
    assert op["state"] == "FAILED_INFRA"
    assert op["result"]["worker_created"] is False
    assert op["actual"] == op["reservation"]  # no refund
    assert not docker["cli"].created()
    # The intent was durable before the doctor ran.
    assert list(ledger.root.glob("operation-*/intent.json"))


def test_an_interruption_during_the_doctor_leaves_a_reconcilable_intent(
    tmp_path, docker, monkeypatch
):
    ledger = unbudgeted_ledger(tmp_path)

    def interrupted(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(carrier, "doctor", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run(ledger)
    assert operation(ledger)["state"] == "RESERVED"
    result = reconcile_worker(ledger, owner=OWNER, identity="run")
    assert result["state"] == "FAILED_INFRA" and result["cleanup_observed"]
    op = operation(ledger)
    assert op["actual"] == op["reservation"]


# Gap 6: the miner's own program failing is typed as the miner's.


@pytest.mark.parametrize(
    "error,state,code,observation",
    [
        (
            WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=1\nstderr:\n"),
            {"Running": True, "OOMKilled": False},
            WorkerCode.RUNTIME,
            "NONZERO_EXIT",
        ),
        (
            WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=137\n"),
            {"Running": False, "OOMKilled": True},
            WorkerCode.RUNTIME,
            "OOM_KILLED",
        ),
    ],
)
def test_observed_miner_failures_settle_failed_miner(
    tmp_path, docker, error, state, code, observation
):
    ledger = unbudgeted_ledger(tmp_path)
    docker["cli"] = FakeDocker(exec_error=error, state=state)
    with pytest.raises(MinerProgramFailure) as raised:
        run(ledger)
    assert raised.value.code is code
    op = operation(ledger)
    assert op["state"] == "FAILED_MINER"
    assert op["result"]["observation"] == observation
    assert op["result"]["cleanup_observed"] is True
    assert op["actual"]["research_trials"] == 1
    assert op["actual"]["numerical_milliseconds"] >= 0
    assert docker["removed"]  # removed, then confirmed absent by `ps`
    assert ["ps", "-aq", "--filter", "name=^" + docker["removed"][0] + "$"] in (
        docker["cli"].commands
    )
    # A replay reports the same typed failure, never a success.
    with pytest.raises(MinerProgramFailure):
        run(ledger)


def test_the_miners_own_allowance_elapsing_is_a_deadline(tmp_path, docker):
    ledger = unbudgeted_ledger(tmp_path)

    def slow(output):
        time.sleep(1.1)

    docker["cli"] = FakeDocker(
        slow,
        exec_error=WorkerFailure(
            WorkerCode.RUNTIME, private_diagnostic=b"stream command timed out"
        ),
    )
    with pytest.raises(MinerProgramFailure) as raised:
        run(ledger, seconds=1)
    assert raised.value.code is WorkerCode.DEADLINE
    op = operation(ledger)
    assert op["actual"]["numerical_milliseconds"] >= 1000  # full allowance kept


@pytest.mark.parametrize(
    "diagnostic,inspect",
    [
        (b"exit=1\nstderr:\nError response from daemon: no such exec", True),
        (b"exit=126\nstderr:\nOCI runtime exec failed", True),
        (b"exit=1\nstderr:\n", False),  # the daemon cannot be asked
        (b"stream command timed out", True),  # no allowance was set
    ],
)
def test_ambiguous_failures_stay_infrastructure(tmp_path, docker, diagnostic, inspect):
    """Specimen for the classifier: daemon and CLI failures are never the miner's."""
    ledger = unbudgeted_ledger(tmp_path)
    docker["cli"] = FakeDocker(
        exec_error=WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=diagnostic),
        inspect=inspect,
    )
    with pytest.raises(WorkerFailure):
        run(ledger)
    assert operation(ledger)["state"] == "RESERVED"


def test_carbons_own_program_failing_is_never_the_miners(tmp_path, docker):
    """The same nonzero exit, from a Carbon-authored program, stays infra."""
    ledger = unbudgeted_ledger(tmp_path)
    docker["cli"] = FakeDocker(
        exec_error=WorkerFailure(WorkerCode.RUNTIME, private_diagnostic=b"exit=1\n")
    )
    with pytest.raises(WorkerFailure):
        run(ledger, miner_authored=False)
    assert operation(ledger)["state"] == "RESERVED"


def test_a_link_in_the_miners_output_is_the_miners_output_failure(tmp_path, docker):
    ledger = unbudgeted_ledger(tmp_path)
    docker["cli"] = FakeDocker(lambda out: os.symlink("/etc/passwd", out / "escape"))
    with pytest.raises(MinerProgramFailure) as raised:
        run(ledger)
    assert raised.value.code is WorkerCode.OUTPUT
    assert operation(ledger)["state"] == "FAILED_MINER"


def test_a_validator_refusal_of_miner_bytes_is_an_output_failure(tmp_path, docker):
    ledger = unbudgeted_ledger(tmp_path)

    def nonfinite(snapshot):
        raise ValueError("nonfinite authored Julia output")

    with pytest.raises(MinerProgramFailure) as raised:
        run(ledger, output_validator=nonfinite)
    assert raised.value.code is WorkerCode.OUTPUT
    assert operation(ledger)["result"]["observation"] == ("OUTPUT_REFUSED_BY_VALIDATOR")


def test_the_task_reports_the_miners_failure_rather_than_infrastructure(
    tmp_path, monkeypatch
):
    from carbon.development_session import research_tasks

    failure = {
        "schema": carrier.MINER_FAILURE_SCHEMA,
        "operation": "operation-x",
        "state": "FAILED_MINER",
        "cause": "MINER_PROGRAM",
        "failure_code": WorkerCode.RUNTIME.value,
        "observation": "NONZERO_EXIT",
    }

    def failing(*args, **kwargs):
        raise MinerProgramFailure(failure)

    monkeypatch.setattr(research_tasks, "run_script", failing)
    executor = _bare_executor(tmp_path)
    result = executor._workspace_action(_python_spec(), "task-1")
    assert result["outcome"] == "MINER_PROGRAM_FAILED"
    assert result["worker"]["failure_code"] == WorkerCode.RUNTIME.value
    # Specimen: an infrastructure failure is not converted.
    monkeypatch.setattr(
        research_tasks,
        "run_script",
        lambda *a, **k: (_ for _ in ()).throw(WorkerFailure(WorkerCode.UNAVAILABLE)),
    )
    with pytest.raises(WorkerFailure) as raised:
        executor._workspace_action(_python_spec(), "task-2")
    assert raised.value.code is WorkerCode.UNAVAILABLE


def test_a_miner_failure_result_must_be_typed():
    with pytest.raises(TypeError, match="typed miner program failure"):
        MinerProgramFailure({"schema": "other"})


# Gap 8: tamper leaves a security_incident record.


def _bare_executor(tmp_path):
    from carbon.development_session.research_tasks import PublicResearchExecutor

    executor = object.__new__(PublicResearchExecutor)
    executor.ledger = unbudgeted_ledger(tmp_path / "exec")
    executor.owner = OWNER
    executor.image = IMAGE
    executor.julia_image = None
    executor.workspace = SimpleNamespace(
        snapshot=lambda names: {}, put=lambda name, body: digest(body)
    )
    return executor


def _python_spec():
    return SimpleNamespace(
        action="run_python",
        arguments_json=canonical(
            {
                "source": "print(1)",
                "files": [],
                "hypothesis": "h",
                "expected_effect": "e",
            }
        ).decode(),
    )


def _run_returning(executor, monkeypatch, body, recorded):
    from carbon.development_session import research_tasks

    snapshot = executor.ledger.root / "operation-x" / "snapshot"
    snapshot.mkdir(parents=True)
    (snapshot / "out.txt").write_bytes(body)
    monkeypatch.setattr(
        research_tasks,
        "run_script",
        lambda *a, **k: {"operation": "operation-x", "files": {"out.txt": recorded}},
    )


def incidents(ledger):
    return [
        n
        for n in ledger.status(owner=OWNER)["notes"]
        if n["kind"] == "security_incident"
    ]


def test_a_changed_export_leaves_a_security_incident(tmp_path, monkeypatch):
    executor = _bare_executor(tmp_path)
    _run_returning(executor, monkeypatch, b"changed", digest(b"original"))
    with pytest.raises(ValueError, match="changed after collection"):
        executor._workspace_action(_python_spec(), "task-1")
    (incident,) = incidents(executor.ledger)
    assert incident["body"]["event"] == "RESEARCH_OUTPUT_DIGEST_MISMATCH"
    assert incident["body"]["expected_digest"] == digest(b"original")
    assert incident["body"]["observed_digest"] == digest(b"changed")


def test_an_unchanged_export_leaves_no_incident(tmp_path, monkeypatch):
    """Specimen: the incident is written for the mismatch, not on every export."""
    executor = _bare_executor(tmp_path)
    _run_returning(executor, monkeypatch, b"original", digest(b"original"))
    result = executor._workspace_action(_python_spec(), "task-1")
    assert result["workspace_exports"]
    assert incidents(executor.ledger) == []


def test_a_changed_battery_result_leaves_a_security_incident(tmp_path):
    ledger = unbudgeted_ledger(tmp_path)
    with pytest.raises(ValueError, match="changed after collection"):
        carrier.record_output_tamper(
            ledger,
            owner=OWNER,
            operation="operation-x",
            name="predictions.json",
            expected=digest(b"a"),
            observed=digest(b"b"),
        )
    assert len(incidents(ledger)) == 1


# Missing cheap tests: collection refuses a link and a FIFO.


def _scratch(tmp_path):
    scratch = tmp_path / "scratch"
    (scratch / "output").mkdir(parents=True)
    (scratch / "output" / "ok.txt").write_bytes(b"ok")
    return scratch


def test_collection_refuses_a_link(tmp_path):
    scratch = _scratch(tmp_path)
    os.symlink(scratch / "output" / "ok.txt", scratch / "output" / "link.txt")
    with pytest.raises(MinerOutputRefused, match="regular files only"):
        collect_outputs(scratch, tmp_path / "snapshot")


def test_collection_refuses_a_directory_link(tmp_path):
    scratch = _scratch(tmp_path)
    os.symlink(tmp_path, scratch / "output" / "escape")
    with pytest.raises(MinerOutputRefused, match="may not contain links"):
        collect_outputs(scratch, tmp_path / "snapshot")


def test_collection_refuses_a_fifo(tmp_path):
    scratch = _scratch(tmp_path)
    os.mkfifo(scratch / "output" / "pipe")
    with pytest.raises(MinerOutputRefused, match="regular files only"):
        collect_outputs(scratch, tmp_path / "snapshot")


def test_collection_copies_regular_files(tmp_path):
    """Specimen: the refusals above are about the link and FIFO, not the tree."""
    scratch = _scratch(tmp_path)
    assert collect_outputs(scratch, tmp_path / "snapshot") == {"ok.txt": 2}
    assert json.dumps(sorted(p.name for p in (tmp_path / "snapshot").iterdir()))


# Gap 7: reconciling a worker also ends its task.


def _orphaned_task(tmp_path, monkeypatch):
    """A run_python task whose supervisor died mid-run: RUNNING over RESERVED."""
    from dataclasses import replace

    from test_cw1_research_tasks import compose

    from carbon import research
    from carbon.development_session import research_tasks

    fixture, provider, executor = compose(tmp_path)
    executor.ledger.freeze(
        {
            "schema": "carbon.autoresearch.campaign.v1",
            "campaign_id": "d3",
            "owner": "test-miner",
            "implementation": "x",
            "objective": "x",
            "sampling": "x",
            "control": "x",
            "selection": "x",
            "replica_policy": "x",
            "provider": "x",
        }
    )

    def dies_mid_run(ledger, *, owner, identity, **kwargs):
        request = {"source": "fixture"}
        ledger.reserve(
            identity,
            owner=owner,
            phase="research",
            request=request,
            resources={"numerical_milliseconds": 0, "research_trials": 1},
        )
        launch = digest(
            canonical({"owner": owner, "identity": identity, "request": request})
        )
        directory = ledger.root / ("operation-" + launch[7:])
        directory.mkdir()
        (directory / "intent.json").write_bytes(
            canonical(
                {
                    "owner": owner,
                    "identity": identity,
                    "request": request,
                    "launch": launch,
                    "container": "carbon-d4-" + launch[7:31],
                }
            )
        )
        raise KeyboardInterrupt  # not an Exception: nothing downstream settles

    monkeypatch.setattr(research_tasks, "run_script", dies_mid_run)
    request = replace(
        fixture.request(),
        idempotency_key="workspace-request-d3",
        task_spec=research.DevelopmentWorkspaceTaskSpecV1(
            "carbon.autoresearch.workspace.v1",
            "run_python",
            _python_spec().arguments_json,
        ),
    )
    task = provider.start_research_task(request).task
    with pytest.raises(KeyboardInterrupt):
        provider.run_queued_task(task.task_id)
    assert provider._tasks[task.task_id].state is ResearchTaskState.RUNNING
    return compose, provider, executor, task.task_id


def _clean_docker(monkeypatch):
    monkeypatch.setattr(carrier, "remove_exact_container", lambda **kwargs: None)
    monkeypatch.setattr(carrier, "DockerCLI", lambda: FakeDocker())


def test_reconciling_the_task_settles_the_ledger_and_ends_the_task(
    tmp_path, monkeypatch
):
    from carbon.research.model import InfrastructureFailureClass

    _compose, provider, executor, task_id = _orphaned_task(tmp_path, monkeypatch)
    _clean_docker(monkeypatch)
    result = provider.reconcile_task(task_id)
    assert result["cleanup_observed"] is True
    task = provider._tasks[task_id]
    assert task.state is ResearchTaskState.FAILED_INFRA
    assert (
        task.receipt.infrastructure_failure_class
        is InfrastructureFailureClass.WORKER_LOST
    )
    assert executor.ledger.operation_state(task_id.value, owner="test-miner") == (
        "FAILED_INFRA"
    )


def test_a_restart_ends_a_task_whose_worker_was_reconciled_meanwhile(
    tmp_path, monkeypatch
):
    """The launchpad reconciles with only the ledger; the next load ends the task."""
    compose, provider, executor, task_id = _orphaned_task(tmp_path, monkeypatch)
    provider.close()
    # Specimen: with the operation still RESERVED, a restart leaves it RUNNING.
    _fixture, reopened, _executor = compose(tmp_path)
    assert reopened._tasks[task_id].state is ResearchTaskState.RUNNING
    reopened.close()
    _clean_docker(monkeypatch)
    reconcile_worker(executor.ledger, owner="test-miner", identity=task_id.value)
    _fixture, reopened, _executor = compose(tmp_path)
    assert reopened._tasks[task_id].state is ResearchTaskState.FAILED_INFRA
    reopened.close()
