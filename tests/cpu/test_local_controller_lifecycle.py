"""The local diagnostic run through the controller's real public entry.

SCOPE, stated precisely. These call `IsolatedReconstructionController.execute`
on a controller built by its real initializer, with a real DurableExecutionQueue
holding a real claim, a real DurableWorkerLaunchStore, real staging, the real
worker request reader, the real effective-controls verification and the real
cleanup and terminal-state machine. The work is a real compiled construction
plan and a real training archive.

Two things are replaced, both because they leave this process:

  * the container CLI, by a scripted daemon whose inspect response is built by
    reading back the create command line the controller itself produced, so a
    control the controller failed to request is genuinely absent; and
  * `spawn_watchdog`, which starts a separate deadline-owning process.

What is therefore NOT covered here: the terminal success path. Reaching
ASSOCIATED needs a genuine trained checkpoint that the bounded native validator
accepts, which no fixture can fabricate. These cover reaching RUNNING, and every
way a run can end short of success. Nothing here is a hardware result, a device
attachment or an acceptance.

Synthetic host roots throughout. No device is attached, no real grant or
approval storage is touched, and no container is created.
"""

import time
from dataclasses import replace

import accelerator_host
import pytest
import scripted_docker
from test_accelerator_worker import _gpu_fixture
from test_c03_worker_contract import _image

from carbon.development_session.profile import canonical
from carbon.execution import ClaimedExecution, DurableExecutionQueue
from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker import development_admission as dev
from carbon.reconstruction.worker import docker_runtime
from carbon.reconstruction.worker.controller import IsolatedReconstructionController
from carbon.reconstruction.worker.model import (
    LOCAL_DEVELOPMENT_AUTHORITY,
    WorkerCode,
    WorkerFailure,
    WorkerLaunchState,
)

NONCE = "a" * 32


def _limits():
    return {
        "productive_seconds": 600,
        "cleanup_seconds": 120,
        "attempt_seconds": 1800,
        "batch_seconds": 3600,
        "host_ram_bytes": 8 * 1024**3,
        "output_bytes": 64 * 1024**2,
        "batch_output_bytes": 256 * 1024**2,
        "training_steps": 32,
        "worker_network": "DISABLED",
    }


# The controls a run is actually executed under, which is what the batch is
# charged against. Resolved once, the same way the controller resolves them.
CONTROLS = dev.effective_controls(_limits())


class _Harness:
    def __init__(self, **values):
        self.__dict__.update(values)

    def run(self, **overrides):
        options = {
            "claimed": self.claimed,
            "repeat_plan": self.repeat,
            "replica": self.replica,
            "plan": self.plan,
            "training_archive": self.archive,
            "derived_seed": self.seed,
            "accelerator_role": AcceleratorRole.MINER_RESEARCH,
            "local_diagnostic": self.selector,
        }
        options.update(overrides)
        return self.controller.execute(**options)

    def status(self):
        return self.controller.store.raw_status(self.execution_id)

    def state(self):
        status = self.status()
        return None if status is None else status["state"]


@pytest.fixture
def harness(tmp_path, monkeypatch):
    host = tmp_path / "host"
    host.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "HOST_ROOT", host)
    monkeypatch.setattr(dev, "HOST_ROOT", host)
    accelerator_host.install(host)

    # The watchdog owns a deadline in a separate process; starting one here
    # would outlive the test. Its own behaviour is covered elsewhere.
    spawned = []
    monkeypatch.setattr(
        docker_runtime,
        "spawn_watchdog",
        lambda **kwargs: spawned.append(kwargs),
    )
    monkeypatch.setattr(
        "carbon.reconstruction.worker.controller.spawn_watchdog",
        lambda **kwargs: spawned.append(kwargs),
        raising=False,
    )

    work = tmp_path / "work"
    work.mkdir()
    claimed, repeat, replica, plan, archive, seed, _ = _gpu_fixture(work, monkeypatch)

    queue = DurableExecutionQueue(tmp_path / "queue.sqlite3")
    queue.admit(claimed.binding)
    active = queue.claim(claimed.claim.ref, "c03-worker", claim_id="lifecycle-claim")
    claimed = ClaimedExecution(active.claim, claimed.binding)

    state_root = (tmp_path / "controller").resolve()
    image = replace(_image(), lock_digest=GPU_PROFILE.environment_lock_digest)
    cli = scripted_docker.ScriptedDocker(image=image)
    controller = IsolatedReconstructionController(
        state_root=state_root, execution_queue=queue, image=image, cli=cli
    )

    derived, _ = dev.diagnostic_plan_identity(
        construction_plan_digest=plan.to_ref().content_digest,
        training_archive_digest=archive.content_digest,
        training_archive_provenance=archive.provenance,
        training_archive_role=archive.role,
        image=image,
        profile_digest=GPU_PROFILE.digest,
        role=AcceleratorRole.MINER_RESEARCH,
        operation="registered_trainer_fit",
        limits=_limits(),
    )
    document = {
        "schema": dev.DEVELOPMENT_SCHEMA,
        "status": "APPROVED",
        "authority": "OWNER-C-CORE-18-LOCAL-DIAGNOSTIC",
        "approval_id": "synthetic-fixture-approval",
        "approving_owner": "fixture-owner",
        "approval_provenance": "synthetic test fixture",
        "host_root": str(host),
        "controller_root": str(state_root),
        "principal": claimed.binding.requester_identity.value,
        "roles": [AcceleratorRole.MINER_RESEARCH.value],
        "device_uuid": accelerator_host.HOSTS[accelerator_host.DEFAULT_SHAPE][
            "device_uuid"
        ],
        "execution_profile_digest": GPU_PROFILE.digest,
        "environment_lock_digest": GPU_PROFILE.environment_lock_digest,
        "image_id": image.image_id,
        "plan_digest": derived,
        "input_digest": archive.content_digest,
        "operation": "registered_trainer_fit",
        "expires_unix": time.time() + 7200.0,
        "attempt_budget": 4,
        "limits": _limits(),
        "allocation": dev.DEVELOPMENT_ALLOCATION,
        "host_use": dev.DEVELOPMENT_HOST_USE,
        "cleanup": dev.DEVELOPMENT_CLEANUP,
    }
    path = host / dev.DEVELOPMENT_RECORD
    path.write_bytes(canonical(document))
    path.chmod(0o600)

    reference = claimed.claim.ref
    return _Harness(
        host=host,
        work=work,
        image=image,
        cli=cli,
        queue=queue,
        controller=controller,
        state_root=state_root,
        claimed=claimed,
        repeat=repeat,
        replica=replica,
        plan=plan,
        archive=archive,
        seed=seed,
        derived=derived,
        spawned=spawned,
        # The installed approval, so a test can reinstall a variant of it rather
        # than rebuild the whole fixture to change one approved limit.
        document=document,
        selector=dev.LocalDiagnosticRequest(
            plan_digest=derived,
            input_digest=archive.content_digest,
            nonce=NONCE,
        ),
        execution_id=f"{reference.submission_id.value}:{reference.attempt_number}",
    )


def _stages(root):
    staging = root / "staging"
    return [] if not staging.is_dir() else list(staging.iterdir())


# --- the run reaches RUNNING through the real path -----------------------------


def test_a_local_run_reaches_running_through_the_real_public_entry(harness):
    """Everything up to the numerical result, with nothing stubbed above Docker."""
    with pytest.raises(WorkerFailure) as error:
        harness.run()
    # The export cannot produce a real artifact here, so the run ends there.
    assert error.value.code in (WorkerCode.OUTPUT, WorkerCode.RUNTIME)

    heads = [command[0] for command in harness.cli.commands]
    assert "create" in heads or "run" in heads
    assert "start" in heads
    assert harness.spawned, "the deadline owner starts before any work is dispatched"

    # The container the controller asked for carried the local authority label
    # and the device from the installed host record - not a strict grant label.
    flags = scripted_docker._flags(harness.cli.create_arguments)
    labels = dict(item.split("=", 1) for item in flags["label"] if "=" in item)
    device = accelerator_host.HOSTS[accelerator_host.DEFAULT_SHAPE]["device_uuid"]
    assert labels["carbon.accelerator.device"] == device
    assert docker_runtime.LOCAL_APPROVAL_LABEL in labels
    assert docker_runtime.STRICT_GRANT_LABEL not in labels
    assert f"device={device}" in flags["gpus"]


def test_the_attempt_is_consumed_exactly_once_by_a_real_run(harness):
    journal = dev.DevelopmentAttemptJournal(harness.host)
    assert journal.consumed() == 0
    with pytest.raises(WorkerFailure):
        harness.run()
    assert journal.consumed() == 1


def test_the_staged_request_is_the_local_form_and_is_removed_on_failure(harness):
    with pytest.raises(WorkerFailure):
        harness.run()
    # Staging is real, and the controller removes it on a terminal failure.
    assert _stages(harness.state_root) == []


def test_a_failed_run_is_terminal_and_removes_the_container(harness):
    with pytest.raises(WorkerFailure):
        harness.run()
    assert harness.cli.removed, "the exact container is removed"
    assert harness.state() in (
        WorkerLaunchState.FAILED_INFRA.value,
        WorkerLaunchState.CANCELLED.value,
    )


def test_a_failed_run_does_not_mint_a_successor_attempt(harness):
    """C-01 admits a successor only from RETRYABLE_INFRA; this is not that."""
    from carbon.execution import ExecutionCode, ExecutionFailure

    with pytest.raises(WorkerFailure):
        harness.run()
    successor = replace(
        harness.claimed.binding,
        handle=replace(harness.claimed.binding.handle, attempt_number=2),
    )
    with pytest.raises(ExecutionFailure) as error:
        harness.queue.admit(successor)
    assert error.value.code is ExecutionCode.CONFLICT


# --- cleanup that cannot be confirmed quarantines ------------------------------


def test_a_container_that_cannot_be_removed_quarantines(harness):
    harness.cli.removable = False
    with pytest.raises(WorkerFailure) as error:
        harness.run()
    assert error.value.code is WorkerCode.QUARANTINED
    assert harness.state() == WorkerLaunchState.QUARANTINED.value


# --- cancellation at each checkpoint -------------------------------------------


def test_cancellation_before_attachment_creates_no_container(harness):
    with pytest.raises(WorkerFailure) as error:
        harness.run(cancelled=lambda: True)
    assert error.value.code is WorkerCode.CANCELLED
    assert not harness.cli.created, "nothing is created once a run is cancelled"
    assert dev.DevelopmentAttemptJournal(harness.host).consumed() == 0


def test_cancellation_after_the_container_starts_is_terminal(harness):
    calls = {"count": 0}

    def cancelled():
        calls["count"] += 1
        # Allow admission, reservation and create; cancel once the container
        # is running and the controller is waiting on it.
        return harness.cli.started and calls["count"] > 3

    with pytest.raises(WorkerFailure) as error:
        harness.run(cancelled=cancelled)
    assert error.value.code is WorkerCode.CANCELLED
    assert harness.cli.removed
    assert harness.state() == WorkerLaunchState.CANCELLED.value


def test_a_container_that_stops_early_is_a_runtime_failure(harness):
    harness.cli.ready_after = 10
    harness.cli.running = False
    with pytest.raises(WorkerFailure) as error:
        harness.run()
    assert error.value.code in (WorkerCode.RUNTIME, WorkerCode.QUARANTINED)


# --- admission still gates the real entry --------------------------------------


def test_a_withdrawn_host_record_refuses_before_any_container(harness):
    (harness.host / "host-device.json").unlink()
    with pytest.raises(WorkerFailure):
        harness.run()
    assert not harness.cli.created
    assert dev.DevelopmentAttemptJournal(harness.host).consumed() == 0


def test_a_withdrawn_approval_refuses_before_any_container(harness):
    (harness.host / dev.DEVELOPMENT_RECORD).unlink()
    with pytest.raises(WorkerFailure) as error:
        harness.run()
    assert error.value.code is WorkerCode.UNAVAILABLE
    assert not harness.cli.created


def test_the_strict_route_still_needs_a_grant_and_takes_no_local_fallback(harness):
    """A refused strict admission must not degrade into the local path."""
    assert not (harness.host / "grant.json").exists()
    with pytest.raises(WorkerFailure) as error:
        harness.run(local_diagnostic=None)
    assert error.value.code is WorkerCode.UNAVAILABLE
    assert not harness.cli.created
    assert dev.DevelopmentAttemptJournal(harness.host).consumed() == 0


def test_an_untyped_selector_cannot_reach_the_local_entry(harness):
    for bad in (
        True,
        "LOCAL_DEVELOPMENT_APPROVAL",
        {"plan_digest": harness.derived},
        1,
    ):
        with pytest.raises(WorkerFailure) as error:
            harness.run(local_diagnostic=bad)
        assert error.value.code is WorkerCode.POLICY
        assert not harness.cli.created


def test_a_selector_that_does_not_match_the_real_work_refuses(harness):
    from test_c03_worker_contract import _sha

    selector = dev.LocalDiagnosticRequest(
        plan_digest=_sha("7"),
        input_digest=harness.archive.content_digest,
        nonce=NONCE,
    )
    with pytest.raises(WorkerFailure) as error:
        harness.run(local_diagnostic=selector)
    assert error.value.code is WorkerCode.POLICY
    assert not harness.cli.created
    assert dev.DevelopmentAttemptJournal(harness.host).consumed() == 0


def test_a_missing_accelerator_role_refuses(harness):
    with pytest.raises(WorkerFailure) as error:
        harness.run(accelerator_role=None)
    assert error.value.code is WorkerCode.POLICY
    assert not harness.cli.created


def test_the_worker_profile_reaching_the_container_is_the_local_variant(harness):
    with pytest.raises(WorkerFailure):
        harness.run()
    flags = scripted_docker._flags(harness.cli.create_arguments)
    environment = dict(
        item.split("=", 1) for item in flags.get("env", []) if "=" in item
    )
    device = accelerator_host.HOSTS[accelerator_host.DEFAULT_SHAPE]["device_uuid"]
    assert environment["CUDA_VISIBLE_DEVICES"] == device
    assert environment["NVIDIA_VISIBLE_DEVICES"] == device
    assert environment["JAX_PLATFORMS"] == "cuda"
    # The worker is told which device kind to expect, because it cannot read
    # the operator-owned host record itself.
    assert (
        environment["CARBON_ACCELERATOR_DEVICE_KIND"]
        == accelerator_host.HOSTS[accelerator_host.DEFAULT_SHAPE]["device_kind"]
    )
    assert LOCAL_DEVELOPMENT_AUTHORITY not in environment
