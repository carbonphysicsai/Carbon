"""Approval and admission behaviour of the controller's local entry method.

SCOPE, stated precisely because it is narrower than end to end. These call
`_execute_local_diagnostic` directly, not the public `execute`. The controller is
built with `__new__` rather than its real initializer, `claimed` and `replica` are
SimpleNamespace stand-ins, `options` is empty, and `_execute_bound`, image
verification and existing-container rejection are replaced. They therefore cover
approval verification, attempt reservation, quarantine and selector typing. They
do NOT cover public entry, real staging, the full worker reader, numerical
dispatch, results or cleanup; `test_local_staged_request_reader.py` covers the
real staging and reader boundary.

Synthetic host roots throughout: the real grant and quarantine storage are never
touched, no container is created and no accelerator is initialized.
"""

import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import accelerator_host
import c02_fixtures
import pytest
from test_accelerator_worker import _gpu_fixture
from test_c03_worker_contract import _image, _sha

from carbon.development_session.profile import canonical
from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
from carbon.reconstruction.model import PublicTrainingArchive
from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker import development_admission as dev
from carbon.reconstruction.worker.model import (
    LOCAL_DEVELOPMENT_AUTHORITY,
    WorkerCode,
    WorkerFailure,
)

# Captured at import, before any fixture patches it: `_gpu_fixture` *appends*
# accelerator pins to whatever is installed, so a second call inside a test
# must start from the pristine list or the plan gets duplicate pins.
PRISTINE_DEPENDENCY_SPECS = c02_fixtures.DEPENDENCY_SPECS

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


DEVICE_UUID = accelerator_host.HOSTS[accelerator_host.DEFAULT_SHAPE]["device_uuid"]


@pytest.fixture
def host(tmp_path, monkeypatch):
    root = tmp_path / "host"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "HOST_ROOT", root)
    monkeypatch.setattr(dev, "HOST_ROOT", root)
    # Which device this host has is installed evidence, not a source constant.
    accelerator_host.install(root)
    return root


@pytest.fixture
def approved(host, tmp_path, monkeypatch):
    """An installed development approval bound to real work, and no strict grant."""
    image = replace(_image(), lock_digest=GPU_PROFILE.environment_lock_digest)
    work_root = tmp_path / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    _, _, _, plan, archive, _, _ = _gpu_fixture(work_root, monkeypatch)
    work = {"plan": plan, "training_archive": archive}
    controller_root = (tmp_path / "controller").resolve()
    controller_root.mkdir(parents=True, exist_ok=True)
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
        "controller_root": str(controller_root),
        "principal": "fixture-principal",
        "roles": [AcceleratorRole.MINER_RESEARCH.value],
        "device_uuid": DEVICE_UUID,
        "execution_profile_digest": GPU_PROFILE.digest,
        "environment_lock_digest": GPU_PROFILE.environment_lock_digest,
        "image_id": image.image_id,
        "plan_digest": derived,
        "input_digest": archive.content_digest,
        "operation": "registered_trainer_fit",
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
        host=host,
        image=image,
        controller_root=controller_root,
        document=document,
        work=work,
        derived=derived,
    )


def _request(approved=None, **overrides):
    """The selector an operator tool would build, echoing the derived identity."""
    values = {
        "plan_digest": approved.derived if approved else PLAN_DIGEST,
        "input_digest": (
            approved.work["training_archive"].content_digest
            if approved
            else INPUT_DIGEST
        ),
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


def _run(controller, approved, monkeypatch, request=None, role=None, work=None):
    claimed, replica = _claimed_and_replica()
    return controller._execute_local_diagnostic(
        options=work if work is not None else getattr(approved, "work", {}),
        local_diagnostic=(
            request
            if request is not None
            else _request(approved if getattr(approved, "work", None) else None)
        ),
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
    # The plan digest the worker sees is the one derived from the real work,
    # not a value the caller supplied.
    assert profile.accelerator_plan_digest == approved.derived
    # The authority record digest, distinct from the plan it authorizes.
    assert profile.accelerator_grant_digest != approved.derived
    assert not (approved.host / "grant.json").exists()


def test_the_attempt_is_reserved_before_the_handoff(approved, monkeypatch):
    """Conservative accounting: the attempt is durable before any attachment.

    Checked at the handoff itself, not afterwards. By the time the exception has
    propagated the controller has reconciled the attempt, so a later assertion
    would be reading the terminal state and could not tell whether the
    reservation had preceded the launch at all.
    """
    controller = _controller(approved, monkeypatch)
    journal = dev.DevelopmentAttemptJournal(approved.host)
    assert journal.consumed() == 0

    observed = {}

    def at_handoff(**kwargs):
        observed["consumed"] = journal.consumed()
        observed["blocking"] = journal.blocking_attempt()
        raise _Handoff(kwargs)

    from carbon.reconstruction.worker.controller import (
        IsolatedReconstructionController,
    )

    monkeypatch.setattr(
        IsolatedReconstructionController, "_execute_bound", staticmethod(at_handoff)
    )
    with pytest.raises(_Handoff):
        _run(controller, approved, monkeypatch)

    # Durable before the launch could have attached anything.
    assert observed["consumed"] == 1
    assert observed["blocking"] is not None
    # And still spent afterwards: reconciling an attempt never refunds it.
    assert journal.consumed() == 1


def test_a_replayed_nonce_cannot_launch_again(approved, monkeypatch):
    """A settled nonce is spent. Replaying it wins no second launch."""
    controller = _controller(approved, monkeypatch)
    journal = dev.DevelopmentAttemptJournal(approved.host)
    with pytest.raises(_Handoff):
        _run(controller, approved, monkeypatch)
    # The controller reconciles its own attempt; nothing here settles it by hand.
    assert journal.blocking_attempt() is None
    assert journal.attempt(nonce=NONCE)["state"] == dev.ATTEMPT_RECONCILED

    with pytest.raises(WorkerFailure) as error:
        _run(controller, approved, monkeypatch)
    assert error.value.code is WorkerCode.CONFLICT
    assert journal.consumed() == 1, "a refused replay consumes nothing extra"


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
def test_a_mismatched_selector_rejects(approved, monkeypatch, request_override):
    """A correctly formatted digest is not authority; it must match the work."""
    controller = _controller(approved, monkeypatch)
    with pytest.raises(WorkerFailure) as error:
        _run(
            controller,
            approved,
            monkeypatch,
            request=_request(approved, **request_override),
        )
    assert error.value.code is WorkerCode.POLICY
    assert dev.DevelopmentAttemptJournal(approved.host).consumed() == 0


def _other_plan(root):
    """A genuinely different recipe: the catalog's other admissible backbone.

    `deeponet` is an allowed row of the same closed compatibility table as the
    fixture's `fno`, so this is a real accepted compile, not a mutated object.
    The outer fixture's accelerator dependency pins stay installed, so the
    resolved plan differs only in the work it describes.
    """
    return c02_fixtures.compile_c02_plan(
        root, backbone="deeponet", environment_digest=GPU_PROFILE.digest
    )


def _other_archive(root, *, payload, provenance):
    source = root / f"train-{provenance}-{len(payload)}.npz"
    source.write_bytes(payload)
    return PublicTrainingArchive.from_file(source, provenance=provenance)


@pytest.mark.parametrize("substitute", ["recipe", "input_bytes", "provenance"])
def test_substituted_real_work_rejects_with_approval_and_selector_unchanged(
    approved, monkeypatch, tmp_path, substitute
):
    """The §4 case: hold authority and selector fixed, change the real work.

    Every substitution here is a real compiled plan or a real archive built from
    real bytes, not a stand-in, so the rejection is the controller's own
    derivation disagreeing with the approved identity.
    """
    other_root = tmp_path / "other-work"
    other_root.mkdir(parents=True, exist_ok=True)
    approved_archive = approved.work["training_archive"]
    work = dict(approved.work)

    if substitute == "recipe":
        work["plan"] = _other_plan(other_root)
        assert (
            work["plan"].to_ref().content_digest
            != approved.work["plan"].to_ref().content_digest
        ), "the substitution must be genuinely different work"
    elif substitute == "input_bytes":
        work["training_archive"] = _other_archive(
            other_root,
            payload=b"different public synthetic TRAIN bytes",
            provenance=approved_archive.provenance,
        )
        assert (
            work["training_archive"].content_digest != approved_archive.content_digest
        )
    else:
        # The sharpest case: byte-identical input, different provenance. The
        # selector's input digest still matches, so only the derived plan
        # identity can catch it.
        work["training_archive"] = _other_archive(
            other_root,
            payload=b"public synthetic TRAIN bytes",
            provenance="other_public_fixture",
        )
        assert (
            work["training_archive"].content_digest == approved_archive.content_digest
        )
        assert work["training_archive"].provenance != approved_archive.provenance

    controller = _controller(approved, monkeypatch)
    with pytest.raises(WorkerFailure) as error:
        _run(controller, approved, monkeypatch, work=work)
    assert error.value.code is WorkerCode.POLICY
    assert dev.DevelopmentAttemptJournal(approved.host).consumed() == 0


@pytest.mark.parametrize(
    "swap",
    [
        # image_id and config_digest are constrained to match, so a different
        # built image moves both.
        {"image_id": _sha("9"), "config_digest": _sha("9")},
        {"source_tree_digest": _sha("9")},
        {"lock_digest": _sha("9")},
        {"wheel_digest": _sha("9")},
        {"base_image_digest": _sha("9")},
        {"build_recipe_digest": _sha("9")},
        {"entrypoint_digest": _sha("9")},
    ],
)
def test_a_substituted_image_rejects_before_any_reservation(
    approved, monkeypatch, swap
):
    """The image is bound into the identity, so a swapped build cannot run."""
    swapped = replace(approved.image, **swap)
    assert swapped != approved.image, "the swap must change the image"
    controller = _controller(approved, monkeypatch)
    object.__setattr__(controller, "image", swapped)
    with pytest.raises(WorkerFailure) as error:
        _run(controller, approved, monkeypatch)
    assert error.value.code is WorkerCode.POLICY
    assert dev.DevelopmentAttemptJournal(approved.host).consumed() == 0


def test_altered_limits_break_the_derived_identity(approved, monkeypatch):
    """Relaxing a limit in the record changes what the record authorizes."""
    limits = {**_limits(), "training_steps": 64}
    document = {**approved.document, "limits": limits}
    path = approved.host / dev.DEVELOPMENT_RECORD
    path.write_bytes(canonical(document))
    path.chmod(0o600)
    controller = _controller(approved, monkeypatch)
    with pytest.raises(WorkerFailure) as error:
        _run(controller, approved, monkeypatch)
    assert error.value.code is WorkerCode.POLICY
    assert dev.DevelopmentAttemptJournal(approved.host).consumed() == 0


def test_an_unregistered_operation_is_refused_at_load(approved, monkeypatch):
    """The operation is part of the authority, not a caller-selected string."""
    document = {**approved.document, "operation": "arbitrary_python"}
    path = approved.host / dev.DEVELOPMENT_RECORD
    path.write_bytes(canonical(document))
    path.chmod(0o600)
    controller = _controller(approved, monkeypatch)
    with pytest.raises(WorkerFailure) as error:
        _run(controller, approved, monkeypatch)
    assert error.value.code is WorkerCode.POLICY
    assert dev.DevelopmentAttemptJournal(approved.host).consumed() == 0


def test_missing_work_rejects_before_any_reservation(approved, monkeypatch):
    controller = _controller(approved, monkeypatch)
    with pytest.raises(WorkerFailure) as error:
        _run(controller, approved, monkeypatch, work={})
    assert error.value.code is WorkerCode.INVALID
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
