"""Local completion removes task-owned records without claiming device release.

Synthetic state roots only. The real host grant and quarantine storage are never
touched, no accelerator is initialized and no device is attached.
"""

import json

import pytest
from test_c03_worker_contract import _sha

from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker.model import (
    LOCAL_DEVELOPMENT_AUTHORITY,
    STRICT_HOST_GRANT_AUTHORITY,
    WorkerCode,
    WorkerFailure,
)

LAUNCH = _sha("1")
OTHER_LAUNCH = _sha("2")
CONTAINER = "carbon-local-diagnostic-fixture"


@pytest.fixture
def host(tmp_path, monkeypatch):
    root = tmp_path / "host"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "HOST_ROOT", root)
    return root


def _allocate(
    host, container=CONTAINER, launch=LAUNCH, authority=LOCAL_DEVELOPMENT_AUTHORITY
):
    runtime.mark_device_allocation(
        container_name=container, launch_digest=launch, authority=authority
    )
    assert (host / "active-allocation.json").is_file()


def test_local_completion_removes_the_task_owned_record(host):
    _allocate(host)
    outcome = runtime.finish_local_device_allocation(
        container_name=CONTAINER, launch_digest=LAUNCH
    )
    assert outcome == runtime.LOCAL_RELEASE_UNVERIFIED
    assert not (host / "active-allocation.json").exists()


def test_local_completion_never_claims_whole_device_release(host):
    _allocate(host)
    outcome = runtime.finish_local_device_allocation(
        container_name=CONTAINER, launch_digest=LAUNCH
    )
    assert "UNESTABLISHED" in outcome
    assert "RELEASED" not in outcome
    assert "EXCLUSIVE" not in outcome


def test_local_completion_never_creates_quarantine(host, monkeypatch):
    """It must not reach verify_device_release, which can quarantine the slot."""

    def refuse(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("local completion called the strict release check")

    monkeypatch.setattr(runtime, "verify_device_release", refuse)
    _allocate(host)
    runtime.finish_local_device_allocation(
        container_name=CONTAINER, launch_digest=LAUNCH
    )
    assert not (host / "device-quarantined").exists()


def test_local_completion_does_not_clear_an_existing_quarantine(host):
    """A strict quarantine is another owner's record and stays untouched."""
    marker = host / "device-quarantined"
    marker.write_bytes(b"UNRECONCILED_DEVICE_RELEASE\n")
    _allocate(host)
    runtime.finish_local_device_allocation(
        container_name=CONTAINER, launch_digest=LAUNCH
    )
    assert marker.read_bytes() == b"UNRECONCILED_DEVICE_RELEASE\n"


def test_local_completion_requires_ownership(host):
    _allocate(host)
    with pytest.raises(WorkerFailure) as error:
        runtime.finish_local_device_allocation(
            container_name=CONTAINER, launch_digest=OTHER_LAUNCH
        )
    assert error.value.code is WorkerCode.CLEANUP
    with pytest.raises(WorkerFailure):
        runtime.finish_local_device_allocation(
            container_name="someone-elses-container", launch_digest=LAUNCH
        )
    # The other owner's record survives a refused completion.
    assert (host / "active-allocation.json").is_file()


def test_local_completion_without_any_allocation_is_refused(host):
    with pytest.raises(WorkerFailure):
        runtime.finish_local_device_allocation(
            container_name=CONTAINER, launch_digest=LAUNCH
        )


def test_a_second_local_completion_is_refused(host):
    """A replayed completion cannot delete a later launch's allocation."""
    _allocate(host)
    runtime.finish_local_device_allocation(
        container_name=CONTAINER, launch_digest=LAUNCH
    )
    with pytest.raises(WorkerFailure):
        runtime.finish_local_device_allocation(
            container_name=CONTAINER, launch_digest=LAUNCH
        )


def test_strict_completion_still_performs_the_release_check(host, monkeypatch):
    """The strict path is unchanged and still demands verified release."""
    called = []
    monkeypatch.setattr(
        runtime, "verify_device_release", lambda **kwargs: called.append(True)
    )
    _allocate(host, authority=STRICT_HOST_GRANT_AUTHORITY)
    runtime.finish_device_allocation(container_name=CONTAINER, launch_digest=LAUNCH)
    assert called == [True]


def test_local_and_strict_share_one_allocation_record(host):
    """A distinct completion path must not create a second device slot."""
    _allocate(host)
    document = json.loads((host / "active-allocation.json").read_bytes())
    assert document["container_name"] == CONTAINER
    assert document["launch_digest"] == LAUNCH
    assert document["authority"] == LOCAL_DEVELOPMENT_AUTHORITY
    # The same shared record is what a second launch would collide with.
    with pytest.raises(WorkerFailure):
        runtime.mark_device_allocation(
            container_name="second-container",
            launch_digest=OTHER_LAUNCH,
            authority=LOCAL_DEVELOPMENT_AUTHORITY,
        )


def test_neither_authority_may_complete_the_other_s_allocation(host, monkeypatch):
    """A development run must not skip the release a strict allocation is owed."""
    released = []
    monkeypatch.setattr(
        runtime, "verify_device_release", lambda **kwargs: released.append(True)
    )
    _allocate(host, authority=STRICT_HOST_GRANT_AUTHORITY)
    with pytest.raises(WorkerFailure) as error:
        runtime.finish_local_device_allocation(
            container_name=CONTAINER, launch_digest=LAUNCH
        )
    assert error.value.code is WorkerCode.CLEANUP
    assert released == [], "the strict allocation is still unreleased"
    assert (host / "active-allocation.json").is_file()

    (host / "active-allocation.json").unlink()
    _allocate(host, authority=LOCAL_DEVELOPMENT_AUTHORITY)
    with pytest.raises(WorkerFailure) as error:
        runtime.finish_device_allocation(container_name=CONTAINER, launch_digest=LAUNCH)
    assert error.value.code is WorkerCode.CLEANUP
    assert (host / "active-allocation.json").is_file()


@pytest.mark.parametrize("authority", ["", "OTHER", None, 1])
def test_an_unknown_allocation_authority_is_refused(host, authority):
    with pytest.raises(WorkerFailure):
        runtime.mark_device_allocation(
            container_name=CONTAINER, launch_digest=LAUNCH, authority=authority
        )
    assert not (host / "active-allocation.json").exists()
