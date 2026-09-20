"""Local development approval and durable attempt accounting.

Synthetic state roots only. No real host grant or quarantine storage is used, no
accelerator is initialized and no device is touched.
"""

import json
import os
from pathlib import Path

import pytest
from test_c03_worker_contract import _image, _sha

from carbon.development_session.profile import canonical
from carbon.reconstruction.accelerators import GPU_PROFILE, AcceleratorRole
from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker import development_admission as dev
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

NONCE = "a" * 32
OTHER_NONCE = "b" * 32
PLAN = _sha("1")
INPUT = _sha("2")


def _limits(**overrides):
    values = {
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
    values.update(overrides)
    return values


@pytest.fixture
def host(tmp_path, monkeypatch):
    """A synthetic HOST_ROOT. The real one is never touched."""
    root = tmp_path / "host"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "HOST_ROOT", root)
    monkeypatch.setattr(dev, "HOST_ROOT", root)
    return root


def _document(root, image, **overrides):
    document = {
        "schema": dev.DEVELOPMENT_SCHEMA,
        "status": "APPROVED",
        "authority": "OWNER-C-CORE-18-LOCAL-DIAGNOSTIC",
        "approval_id": "synthetic-fixture-approval",
        "approving_owner": "fixture-owner",
        "approval_provenance": "synthetic test fixture",
        "host_root": str(root),
        "controller_root": str((root.parent / "controller").resolve()),
        "principal": "fixture-principal",
        "roles": [AcceleratorRole.MINER_RESEARCH.value],
        "device_uuid": GPU_PROFILE.device_uuid,
        "execution_profile_digest": GPU_PROFILE.digest,
        "environment_lock_digest": GPU_PROFILE.environment_lock_digest,
        "image_id": image.image_id,
        "plan_digest": PLAN,
        "input_digest": INPUT,
        "operation": "registered_trainer_fit",
        "expires_unix": 100000.0,
        "attempt_budget": 4,
        "limits": _limits(),
        "allocation": dev.DEVELOPMENT_ALLOCATION,
        "host_use": dev.DEVELOPMENT_HOST_USE,
        "cleanup": dev.DEVELOPMENT_CLEANUP,
    }
    document.update(overrides)
    return document


def _install(root, document):
    path = root / dev.DEVELOPMENT_RECORD
    path.write_bytes(canonical(document))
    path.chmod(0o600)
    return path


@pytest.fixture
def approval(host):
    from dataclasses import replace

    image = replace(_image(), lock_digest=GPU_PROFILE.environment_lock_digest)
    document = _document(host, image)
    _install(host, document)
    controller = Path(document["controller_root"])
    controller.mkdir(parents=True, exist_ok=True)
    return host, image, document, controller


def _verify(loaded, image, controller, **overrides):
    options = {
        "principal": "fixture-principal",
        "state_root": controller,
        "image": image,
        "role": AcceleratorRole.MINER_RESEARCH,
        "plan_digest": PLAN,
        "input_digest": INPUT,
        "now": 1000.0,
    }
    options.update(overrides)
    return loaded.verify(**options)


# --- the record is not a strict grant -----------------------------------------


def test_valid_approval_verifies(approval):
    _, image, _, controller = approval
    _verify(dev.DevelopmentHostApproval.load(), image, controller)


def test_a_strict_grant_is_not_a_development_approval(host):
    """Installing the strict document under the development name must fail."""
    _install(host, {"schema": runtime.GRANT_SCHEMA, "status": "APPROVED"})
    with pytest.raises(WorkerFailure) as error:
        dev.DevelopmentHostApproval.load()
    assert error.value.code is WorkerCode.POLICY


def test_development_approval_is_rejected_by_the_strict_verifier(approval):
    """Symmetry: the strict path must refuse this document on its own terms."""
    host, image, document, controller = approval
    strict_path = host / "grant.json"
    strict_path.write_bytes(canonical(document))
    strict_path.chmod(0o600)
    strict = runtime.AcceleratorHostAdmission.load()
    with pytest.raises(WorkerFailure):
        strict.verify(
            principal="fixture-principal",
            state_root=controller,
            image=image,
            role=AcceleratorRole.MINER_RESEARCH,
            now=1000.0,
        )


def test_the_approval_never_writes_or_reads_grant_json(approval):
    host, _, _, _ = approval
    assert (host / dev.DEVELOPMENT_RECORD).is_file()
    assert not (host / "grant.json").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("allocation", "EXCLUSIVE_SINGLE_DEVICE"),
        ("host_use", "DEDICATED_NO_DISPLAY_OR_OTHER_COMPUTE"),
        ("cleanup", "EXACT_GRANT_OWNED_CONTAINERS_AND_DEVICE_RELEASE"),
    ],
)
def test_strict_host_assertions_are_refused(approval, field, value):
    """A development approval may not borrow the strict host claims."""
    host, image, document, controller = approval
    _install(host, {**document, field: value})
    with pytest.raises(WorkerFailure):
        _verify(dev.DevelopmentHostApproval.load(), image, controller)


def test_require_development_approval_refuses_other_objects(approval):
    document = approval[2]
    loaded = dev.DevelopmentHostApproval.load()
    assert dev.require_development_approval(loaded) is loaded
    for bad in (None, {}, document, "approval"):
        with pytest.raises(WorkerFailure):
            dev.require_development_approval(bad)


# --- binding ------------------------------------------------------------------


@pytest.mark.parametrize(
    "override",
    [
        {"plan_digest": _sha("3")},
        {"input_digest": _sha("3")},
        {"image_id": _sha("4")},
        {"device_uuid": "GPU-other"},
        {"execution_profile_digest": _sha("5")},
        {"environment_lock_digest": _sha("6")},
        {"principal": "someone-else"},
        {"status": "PENDING"},
        {"roles": [AcceleratorRole.VALIDATOR_RECONSTRUCTION.value]},
        {"approving_owner": ""},
        {"approval_provenance": ""},
    ],
)
def test_mismatched_binding_is_refused(approval, override):
    host, image, document, controller = approval
    _install(host, {**document, **override})
    with pytest.raises(WorkerFailure):
        _verify(dev.DevelopmentHostApproval.load(), image, controller)


def test_caller_supplied_plan_digest_must_match_the_record(approval):
    """A digest the caller asserts is not authority by itself."""
    _, image, _, controller = approval
    with pytest.raises(WorkerFailure):
        _verify(
            dev.DevelopmentHostApproval.load(),
            image,
            controller,
            plan_digest=_sha("7"),
        )


def test_extra_or_missing_fields_are_refused(approval):
    host, image, document, controller = approval
    _install(host, {**document, "extra": 1})
    with pytest.raises(WorkerFailure):
        _verify(dev.DevelopmentHostApproval.load(), image, controller)
    reduced = dict(document)
    del reduced["limits"]
    _install(host, reduced)
    with pytest.raises(WorkerFailure):
        _verify(dev.DevelopmentHostApproval.load(), image, controller)


def test_revoked_or_edited_record_is_refused(approval):
    root, image, document, controller = approval
    loaded = dev.DevelopmentHostApproval.load()
    _install(root, {**document, "approval_id": "rotated"})
    with pytest.raises(WorkerFailure):
        _verify(loaded, image, controller)


def test_quarantine_blocks_local_work_and_is_not_cleared(approval):
    host, image, _, controller = approval
    marker = host / "device-quarantined"
    marker.write_bytes(b"UNRECONCILED_DEVICE_RELEASE\n")
    with pytest.raises(WorkerFailure) as error:
        _verify(dev.DevelopmentHostApproval.load(), image, controller)
    assert error.value.code is WorkerCode.QUARANTINED
    assert marker.is_file(), "local admission must never clear strict quarantine"


# --- expiry -------------------------------------------------------------------


def test_expired_approval_is_refused(approval):
    _, image, _, controller = approval
    with pytest.raises(WorkerFailure) as error:
        _verify(dev.DevelopmentHostApproval.load(), image, controller, now=100000.0)
    assert error.value.code is WorkerCode.DEADLINE


def test_insufficient_remaining_validity_is_refused(approval):
    """Remaining validity must cover the whole attempt, not just start it."""
    _, image, _, controller = approval
    with pytest.raises(WorkerFailure) as error:
        _verify(dev.DevelopmentHostApproval.load(), image, controller, now=99000.0)
    assert error.value.code is WorkerCode.DEADLINE


@pytest.mark.parametrize(
    "limits",
    [
        _limits(productive_seconds=1700, cleanup_seconds=200),
        _limits(attempt_seconds=7200),
        _limits(worker_network="ENABLED"),
        _limits(output_bytes=0),
    ],
)
def test_incoherent_limits_are_refused(approval, limits):
    host, image, document, controller = approval
    _install(host, {**document, "limits": limits})
    with pytest.raises(WorkerFailure):
        _verify(dev.DevelopmentHostApproval.load(), image, controller)


# --- durable attempt accounting -----------------------------------------------


def test_reserve_consumes_budget_durably(host):
    journal = dev.DevelopmentAttemptJournal(host)
    assert journal.consumed() == 0
    journal.reserve(nonce=NONCE, plan_digest=PLAN, budget=4, now=1.0)
    assert journal.consumed() == 1
    # A brand new journal object sees the same durable state.
    assert dev.DevelopmentAttemptJournal(host).consumed() == 1


def test_replayed_nonce_cannot_consume_a_second_attempt(host):
    journal = dev.DevelopmentAttemptJournal(host)
    journal.reserve(nonce=NONCE, plan_digest=PLAN, budget=4, now=1.0)
    journal.settle(nonce=NONCE, state=dev.ATTEMPT_COMPLETED)
    with pytest.raises(WorkerFailure) as error:
        journal.reserve(nonce=NONCE, plan_digest=PLAN, budget=4, now=2.0)
    assert error.value.code is WorkerCode.CONFLICT
    assert journal.consumed() == 1


def test_budget_is_enforced_including_failed_attempts(host):
    journal = dev.DevelopmentAttemptJournal(host)
    for index in range(4):
        nonce = f"{index:032x}"
        journal.reserve(nonce=nonce, plan_digest=PLAN, budget=4, now=float(index))
        journal.settle(nonce=nonce, state=dev.ATTEMPT_COMPLETED)
    assert journal.consumed() == 4
    with pytest.raises(WorkerFailure):
        journal.reserve(nonce=OTHER_NONCE, plan_digest=PLAN, budget=4, now=9.0)


def test_a_new_directory_does_not_reset_the_budget(host):
    """A different output path must not create a second allowance."""
    journal = dev.DevelopmentAttemptJournal(host)
    journal.reserve(nonce=NONCE, plan_digest=PLAN, budget=4, now=1.0)
    journal.settle(nonce=NONCE, state=dev.ATTEMPT_COMPLETED)
    assert dev.DevelopmentAttemptJournal(host).consumed() == 1


def test_unsettled_attempt_blocks_the_next_launch(host):
    """A crash between reserve and settle leaves the slot unreconciled."""
    journal = dev.DevelopmentAttemptJournal(host)
    journal.reserve(nonce=NONCE, plan_digest=PLAN, budget=4, now=1.0)
    assert journal.blocking_attempt() is not None
    with pytest.raises(WorkerFailure) as error:
        journal.reserve(nonce=OTHER_NONCE, plan_digest=PLAN, budget=4, now=2.0)
    assert error.value.code is WorkerCode.CONFLICT


def test_ambiguous_attempt_keeps_blocking(host):
    journal = dev.DevelopmentAttemptJournal(host)
    journal.reserve(nonce=NONCE, plan_digest=PLAN, budget=4, now=1.0)
    journal.settle(nonce=NONCE, state=dev.ATTEMPT_AMBIGUOUS)
    assert journal.blocking_attempt() is not None
    with pytest.raises(WorkerFailure):
        journal.reserve(nonce=OTHER_NONCE, plan_digest=PLAN, budget=4, now=2.0)


def test_completed_attempt_does_not_block(host):
    journal = dev.DevelopmentAttemptJournal(host)
    journal.reserve(nonce=NONCE, plan_digest=PLAN, budget=4, now=1.0)
    journal.settle(nonce=NONCE, state=dev.ATTEMPT_COMPLETED)
    assert journal.blocking_attempt() is None
    journal.reserve(nonce=OTHER_NONCE, plan_digest=PLAN, budget=4, now=2.0)


def test_settle_cannot_invent_a_refund_or_rewrite_a_terminal_state(host):
    journal = dev.DevelopmentAttemptJournal(host)
    journal.reserve(nonce=NONCE, plan_digest=PLAN, budget=4, now=1.0)
    journal.settle(nonce=NONCE, state=dev.ATTEMPT_AMBIGUOUS)
    with pytest.raises(WorkerFailure):
        journal.settle(nonce=NONCE, state=dev.ATTEMPT_COMPLETED)
    assert journal.consumed() == 1


@pytest.mark.parametrize("state", ["RESERVED", "", "DELETED", None, 1])
def test_invalid_settle_states_are_refused(host, state):
    journal = dev.DevelopmentAttemptJournal(host)
    journal.reserve(nonce=NONCE, plan_digest=PLAN, budget=4, now=1.0)
    with pytest.raises(WorkerFailure):
        journal.settle(nonce=NONCE, state=state)


@pytest.mark.parametrize("nonce", ["", "short", "A" * 32, "g" * 32, 0, None])
def test_malformed_nonce_is_refused(host, nonce):
    journal = dev.DevelopmentAttemptJournal(host)
    with pytest.raises(WorkerFailure):
        journal.reserve(nonce=nonce, plan_digest=PLAN, budget=4, now=1.0)


def test_marker_is_private_and_canonical(host):
    journal = dev.DevelopmentAttemptJournal(host)
    path = journal.reserve(nonce=NONCE, plan_digest=PLAN, budget=4, now=1.0)
    assert path.stat().st_mode & 0o077 == 0
    assert json.loads(path.read_bytes())["state"] == dev.ATTEMPT_RESERVED
    assert canonical(json.loads(path.read_bytes())) == path.read_bytes()
    assert os.stat(journal.root).st_mode & 0o077 == 0
