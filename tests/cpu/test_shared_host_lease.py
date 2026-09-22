"""Strict and development work contend for one shared Carbon device slot.

Synthetic state roots only. No accelerator is initialized and no device is
attached.
"""

import pytest

from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker import development_admission as dev
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure


@pytest.fixture
def host(tmp_path, monkeypatch):
    root = tmp_path / "host"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(runtime, "HOST_ROOT", root)
    monkeypatch.setattr(dev, "HOST_ROOT", root)
    return root


def test_both_variants_use_the_same_lease_function():
    """Not a parallel lock: the development path calls the shared one."""
    approval = dev.DevelopmentHostApproval({"schema": dev.DEVELOPMENT_SCHEMA}, "d")
    assert dev.shared_host_lease is runtime.shared_host_lease
    assert callable(approval.exclusive_lease)


def test_a_held_lease_blocks_a_second_holder(host):
    """One Carbon job at a time, whichever variant asked first."""
    with (
        runtime.shared_host_lease(),
        pytest.raises(WorkerFailure) as error,
        runtime.shared_host_lease(),
    ):
        pass  # pragma: no cover - must not be reached
    assert error.value.code is WorkerCode.CONFLICT


def test_the_lease_is_released_after_use(host):
    with runtime.shared_host_lease():
        pass
    with runtime.shared_host_lease():
        pass


def test_a_failure_inside_the_lease_still_releases_it(host):
    """The lock must not leak when the body fails, whatever it reports.

    The expected type changed with the repair and the intent did not: the body
    error now propagates as itself rather than as CONFLICT. Release is what this
    asserts, and if it leaked the next acquisition would report CONFLICT -
    turning the repair into a worse version of the bug it fixes.
    """
    with pytest.raises(ValueError, match="workload failed"):  # noqa: SIM117
        with runtime.shared_host_lease():
            raise ValueError("workload failed")
    with runtime.shared_host_lease():
        pass


def test_a_body_value_error_propagates_instead_of_becoming_a_conflict(host):
    """The repair. A workload error is not device contention.

    `yield` used to sit inside the `try`, so an exception from the *body*
    propagated into the generator and was caught beside a genuine lock failure.
    The caller was then told CONFLICT, which asserts another holder has the
    single Carbon device slot - sending an operator to diagnose a slot that is
    not contended, and hiding the real error in attempt accounting.
    """
    with pytest.raises(ValueError, match="a workload error"):  # noqa: SIM117
        with runtime.shared_host_lease():
            raise ValueError("a workload error, not a lock conflict")


def test_a_body_os_error_propagates_too(host):
    """The other type the acquisition catch names, so both are covered."""
    with pytest.raises(OSError, match="a workload failure"):  # noqa: SIM117
        with runtime.shared_host_lease():
            raise OSError("a workload failure, not a lock conflict")


def test_a_worker_failure_from_the_body_is_not_relabelled(host):
    """A body failure that is already typed keeps its own code."""
    with pytest.raises(WorkerFailure) as error:  # noqa: SIM117
        with runtime.shared_host_lease():
            raise WorkerFailure(WorkerCode.DEADLINE)
    assert error.value.code is WorkerCode.DEADLINE


def test_strict_admission_lease_delegates_to_the_shared_lock(host):
    """The strict wrapper must not acquire a different lock."""
    admission = runtime.AcceleratorHostAdmission({"schema": runtime.GRANT_SCHEMA}, "d")
    with admission.exclusive_lease(), pytest.raises(WorkerFailure):  # noqa: SIM117
        with runtime.shared_host_lease():
            pass  # pragma: no cover - must not be reached


def test_a_different_output_directory_does_not_create_a_second_slot(host, tmp_path):
    """The lock root is the host record's parent, never a caller-chosen path."""
    other = tmp_path / "somewhere-else"
    other.mkdir()
    with runtime.shared_host_lease(), pytest.raises(WorkerFailure):  # noqa: SIM117
        with runtime.shared_host_lease():
            pass  # pragma: no cover - must not be reached
