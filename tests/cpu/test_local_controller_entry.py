"""The real controller's local entry, exercised without a device.

These drive `IsolatedReconstructionController.execute` itself rather than a
stand-in, stopping at the launch handoff. Synthetic host roots throughout: the
real grant and quarantine storage are never touched, no container is created and
no accelerator is initialized.
"""

import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_c03_worker_contract import _image, _sha

from carbon.development_session.profile import canonical
from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker import development_admission as dev
from carbon.reconstruction.worker.model import (
    LOCAL_DEVELOPMENT_AUTHORITY,
    WorkerCode,
    WorkerFailure,
)

PLAN_DIGEST = _sha("5")
INPUT_DIGEST = _sha("6")
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


@pytest.fixture
def host(tmp_path, monkeypatch):
    root = tmp_path / "host"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "HOST_ROOT", root)
    monkeypatch.setattr(dev, "HOST_ROOT", root)
    return root


@pytest.fixture
def approved(host, tmp_path):
    """An installed development approval, and no strict grant anywhere."""
    image = replace(_image(), lock_digest=GPU_PROFILE.environment_lock_digest)
    controller_root = (tmp_path / "controller").resolve()
    controller_root.mkdir(parents=True, exist_ok=True)
    document = {
        "schema": dev.DEVELOPMENT_SCHEMA,
        "status": "APPROVED",
        "authority": "OWNER-C-CORE-18-LOCAL-DIAGNOSTIC",
        "approval_id": "synthetic-fixture-approval",
        "approving_owner": "fixture-owner",
        "approval_provenance": "synthetic test fixture",
        "host_root": str(host),
        "controller_root": str(controller_root),
        "principal": "fixture-principal",
        "roles": [AcceleratorRole.MINER_RESEARCH.value],
        "device_uuid": GPU_PROFILE.device_uuid,
        "execution_profile_digest": GPU_PROFILE.digest,
        "environment_lock_digest": GPU_PROFILE.environment_lock_digest,
        "image_id": image.image_id,
        "plan_digest": PLAN_DIGEST,
        "input_digest": INPUT_DIGEST,
        # The controller uses real wall-clock time, so the approval must be
        # valid now and for the whole attempt it authorizes.
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
    assert not (host / "grant.json").exists()
    return SimpleNamespace(
        host=host, image=image, controller_root=controller_root, document=document
    )


def _request(**overrides):
    values = {
        "plan_digest": PLAN_DIGEST,
        "input_digest": INPUT_DIGEST,
        "nonce": NONCE,
    }
    values.update(overrides)
    return dev.LocalDiagnosticRequest(**values)


class _Handoff(Exception):
    """Raised at the launch handoff so no container is ever created."""


def _controller(approved, monkeypatch):
    """The real controller, stopped exactly at the supervised launch."""
    from carbon.reconstruction.worker.controller import (
        IsolatedReconstructionController,
    )

    controller = IsolatedReconstructionController.__new__(
        IsolatedReconstructionController
    )
    object.__setattr__(controller, "state_root", approved.controller_root)
    object.__setattr__(controller, "image", approved.image)
    object.__setattr__(controller, "cli", SimpleNamespace())

    def reached(**kwargs):
        raise _Handoff(kwargs)

    monkeypatch.setattr(
        IsolatedReconstructionController, "_execute_bound", staticmethod(reached)
    )
    monkeypatch.setattr(runtime, "verify_image_and_toolkit", lambda **k: None)
    monkeypatch.setattr(runtime, "reject_existing_device_containers", lambda **k: None)
    return controller


def _claimed_and_replica():
    claimed = SimpleNamespace(
        binding=SimpleNamespace(
            requester_identity=SimpleNamespace(value="fixture-principal")
        )
    )
    replica = SimpleNamespace(
        binding=SimpleNamespace(
            replicate_identity=SimpleNamespace(
                policy_ref=SimpleNamespace(content_digest=_sha("2")),
                resource_class_ref=SimpleNamespace(content_digest=_sha("3")),
            )
        )
    )
    return claimed, replica


def _run(controller, approved, monkeypatch, request=None, role=None):
    claimed, replica = _claimed_and_replica()
    return controller._execute_local_diagnostic(
        options={},
        local_diagnostic=request if request is not None else _request(),
        accelerator_role=role or AcceleratorRole.MINER_RESEARCH,
        claimed=claimed,
        replica=replica,
        cancelled=None,
    )


# --- the approved route reaches the launch handoff with no strict grant -------


def test_valid_local_approval_reaches_the_launch_handoff(approved, monkeypatch):
    controller = _controller(approved, monkeypatch)
    with pytest.raises(_Handoff) as reached:
        _run(controller, approved, monkeypatch)
    profile = reached.value.args[0]["worker_profile"]
    assert profile.accelerator_authority == LOCAL_DEVELOPMENT_AUTHORITY
    assert profile.accelerator_plan_digest == PLAN_DIGEST
    # The authority record digest, distinct from the plan it authorizes.
    assert profile.accelerator_grant_digest != PLAN_DIGEST
    assert not (approved.host / "grant.json").exists()


def test_the_attempt_is_reserved_before_the_handoff(approved, monkeypatch):
    """Conservative accounting: the attempt is durable before any attachment."""
    controller = _controller(approved, monkeypatch)
    journal = dev.DevelopmentAttemptJournal(approved.host)
    assert journal.consumed() == 0
    with pytest.raises(_Handoff):
        _run(controller, approved, monkeypatch)
    assert journal.consumed() == 1
    assert journal.blocking_attempt() is not None


def test_a_replayed_nonce_cannot_launch_again(approved, monkeypatch):
    controller = _controller(approved, monkeypatch)
    with pytest.raises(_Handoff):
        _run(controller, approved, monkeypatch)
    dev.DevelopmentAttemptJournal(approved.host).settle(
        nonce=NONCE, state=dev.ATTEMPT_COMPLETED
    )
    with pytest.raises(WorkerFailure) as error:
        _run(controller, approved, monkeypatch)
    assert error.value.code is WorkerCode.CONFLICT


# --- rejection happens before anything could attach ---------------------------


def test_a_missing_approval_rejects(host, tmp_path, monkeypatch):
    image = replace(_image(), lock_digest=GPU_PROFILE.environment_lock_digest)
    controller_root = (tmp_path / "controller").resolve()
    controller_root.mkdir(parents=True, exist_ok=True)
    approved = SimpleNamespace(
        host=host, image=image, controller_root=controller_root, document={}
    )
    controller = _controller(approved, monkeypatch)
    with pytest.raises(WorkerFailure) as error:
        _run(controller, approved, monkeypatch)
    assert error.value.code is WorkerCode.UNAVAILABLE


@pytest.mark.parametrize(
    "request_override",
    [
        {"plan_digest": _sha("7")},
        {"input_digest": _sha("7")},
    ],
)
def test_cross_plan_or_cross_input_binding_rejects(
    approved, monkeypatch, request_override
):
    """A correctly formatted digest is not authority; it must match the record."""
    controller = _controller(approved, monkeypatch)
    with pytest.raises(WorkerFailure) as error:
        _run(controller, approved, monkeypatch, request=_request(**request_override))
    assert error.value.code is WorkerCode.POLICY
    assert dev.DevelopmentAttemptJournal(approved.host).consumed() == 0


def test_an_expired_approval_rejects_before_reserving(approved, monkeypatch):
    document = {**approved.document, "expires_unix": 1.0}
    path = approved.host / dev.DEVELOPMENT_RECORD
    path.write_bytes(canonical(document))
    path.chmod(0o600)
    controller = _controller(approved, monkeypatch)
    with pytest.raises(WorkerFailure) as error:
        _run(controller, approved, monkeypatch)
    assert error.value.code is WorkerCode.DEADLINE
    assert dev.DevelopmentAttemptJournal(approved.host).consumed() == 0


def test_a_wrong_role_rejects(approved, monkeypatch):
    controller = _controller(approved, monkeypatch)
    with pytest.raises(WorkerFailure):
        _run(
            controller,
            approved,
            monkeypatch,
            role=AcceleratorRole.VALIDATOR_RECONSTRUCTION,
        )


def test_an_untyped_selector_rejects(approved, monkeypatch):
    """A public route cannot select this entry with a flag or a string."""
    controller = _controller(approved, monkeypatch)
    claimed, replica = _claimed_and_replica()
    for bad in (True, "LOCAL_DEVELOPMENT_APPROVAL", {"plan_digest": PLAN_DIGEST}, 1):
        with pytest.raises(WorkerFailure) as error:
            controller._execute_local_diagnostic(
                options={},
                local_diagnostic=bad,
                accelerator_role=AcceleratorRole.MINER_RESEARCH,
                claimed=claimed,
                replica=replica,
                cancelled=None,
            )
        assert error.value.code is WorkerCode.POLICY


def test_an_existing_strict_quarantine_blocks_local_work(approved, monkeypatch):
    marker = approved.host / "device-quarantined"
    marker.write_bytes(b"UNRECONCILED_DEVICE_RELEASE\n")
    controller = _controller(approved, monkeypatch)
    with pytest.raises(WorkerFailure) as error:
        _run(controller, approved, monkeypatch)
    assert error.value.code is WorkerCode.QUARANTINED
    assert marker.is_file(), "local admission must never clear strict quarantine"
    assert dev.DevelopmentAttemptJournal(approved.host).consumed() == 0


def test_an_unreconciled_previous_attempt_blocks_a_new_launch(approved, monkeypatch):
    journal = dev.DevelopmentAttemptJournal(approved.host)
    journal.reserve(nonce="b" * 32, plan_digest=PLAN_DIGEST, budget=4, now=1.0)
    controller = _controller(approved, monkeypatch)
    with pytest.raises(WorkerFailure) as error:
        _run(controller, approved, monkeypatch)
    assert error.value.code is WorkerCode.CONFLICT


def test_the_exhausted_budget_blocks_a_new_launch(approved, monkeypatch):
    journal = dev.DevelopmentAttemptJournal(approved.host)
    for index in range(4):
        nonce = f"{index:032x}"
        journal.reserve(nonce=nonce, plan_digest=PLAN_DIGEST, budget=4, now=1.0)
        journal.settle(nonce=nonce, state=dev.ATTEMPT_COMPLETED)
    controller = _controller(approved, monkeypatch)
    with pytest.raises(WorkerFailure):
        _run(controller, approved, monkeypatch)


# --- the strict route is unaffected -------------------------------------------


def test_a_strict_request_still_requires_a_strict_grant(approved, monkeypatch):
    """No fallback: without grant.json the strict branch fails, not degrades."""
    from carbon.reconstruction.worker.accelerator_runtime import (
        AcceleratorHostAdmission,
    )

    assert not (approved.host / "grant.json").exists()
    with pytest.raises(WorkerFailure) as error:
        AcceleratorHostAdmission.load()
    assert error.value.code is WorkerCode.UNAVAILABLE


def test_the_local_selector_requires_two_distinct_identities():
    with pytest.raises(WorkerFailure):
        dev.LocalDiagnosticRequest(
            plan_digest=PLAN_DIGEST, input_digest=PLAN_DIGEST, nonce=NONCE
        )


@pytest.mark.parametrize(
    "override",
    [
        {"plan_digest": "not-a-digest"},
        {"input_digest": ""},
        {"nonce": "short"},
        {"nonce": "A" * 32},
    ],
)
def test_a_malformed_selector_rejects(override):
    with pytest.raises(WorkerFailure):
        _request(**override)


def test_discovery_imports_do_not_initialize_a_backend():
    """Importing the local path must not pull in or start a numerical backend."""
    import subprocess
    import sys

    source = (
        "import sys;"
        "import carbon.reconstruction.worker.development_admission;"
        "import carbon.reconstruction.worker.controller;"
        "import carbon.reconstruction.accelerators;"
        "print('jax' in sys.modules, 'jaxlib' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False False"
