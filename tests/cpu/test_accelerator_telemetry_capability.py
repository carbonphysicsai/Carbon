"""Unestablished GPU telemetry must not certify exclusivity or device release.

These are synthetic fixture observations only; no accelerator is initialized and
no host process list is captured. An empty compute-process query and a genuinely
idle device are indistinguishable, so emptiness is evidence only when the
observing source is established as able to enumerate compute processes.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from test_accelerator_worker import host_grant  # noqa: F401  (fixture import)

from carbon.reconstruction.accelerators import GPU_PROFILE
from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

IDENTITY_ROW = (
    f"{GPU_PROFILE.device_uuid}, {GPU_PROFILE.device_kind}, "
    f"{GPU_PROFILE.host_driver}, 6144, Disabled"
)


def _cli(driver_model, *, processes=b""):
    """Bounded container CLI returning one fixed observation set."""

    def run(command, **kwargs):
        if "--query-gpu=driver_model.current" in command:
            return SimpleNamespace(stdout=driver_model)
        if "--query-compute-apps=pid,gpu_uuid" in command:
            return SimpleNamespace(stdout=processes)
        return SimpleNamespace(stdout=IDENTITY_ROW.encode())

    return SimpleNamespace(run=run)


# --- capability helper -------------------------------------------------------


@pytest.mark.parametrize("reading", ["N/A", "n/a", "TCC", " TCC "])
def test_established_readings_permit_enumeration(reading):
    assert runtime.process_enumeration_established(reading) is True


@pytest.mark.parametrize(
    "reading",
    ["WDDM", "wddm", " WDDM ", "", "   ", "UNKNOWN", "[Not Supported]", "N/A, WDDM"],
)
def test_unestablished_readings_refuse_enumeration(reading):
    assert runtime.process_enumeration_established(reading) is False


@pytest.mark.parametrize("reading", [None, b"N/A", 0, ["N/A"], object()])
def test_non_text_capability_readings_refuse(reading):
    # A caller cannot certify capability by supplying a convenient object.
    assert runtime.process_enumeration_established(reading) is False


# --- strict admission --------------------------------------------------------


def test_wddm_empty_process_query_cannot_admit():
    """The observed live case: WSL returns nothing while a process is attached."""
    with pytest.raises(WorkerFailure) as error:
        runtime.inspect_gpu_device(cli=_cli(b"WDDM"), container_name="fixture")
    assert error.value.code is WorkerCode.POLICY


def test_established_source_still_admits_and_reports_no_foreign_processes():
    observation = runtime.inspect_gpu_device(cli=_cli(b"N/A"), container_name="fixture")
    assert observation["uuid"] == GPU_PROFILE.device_uuid
    assert observation["other_compute_processes"] == []
    assert observation["evidence"] == "OBSERVED_NOT_SECURITY_QUALIFIED"
    assert observation["device_memory_cap"] == "EXCLUSIVE_ALLOCATION_NOT_HOST_CGROUP"


def test_established_source_still_rejects_a_reported_foreign_process():
    with pytest.raises(WorkerFailure):
        runtime.inspect_gpu_device(
            cli=_cli(b"N/A", processes=b"123, GPU-foreign"), container_name="fixture"
        )


@pytest.mark.parametrize(
    "reading", [b"WDDM", b"", b"   ", b"[Not Supported]", b"\xff\xfe", b"N/A\nWDDM"]
)
def test_unestablished_or_malformed_capability_refuses_admission(reading):
    with pytest.raises(WorkerFailure):
        runtime.inspect_gpu_device(cli=_cli(reading), container_name="fixture")


def test_capability_query_failure_refuses_admission():
    def run(command, **kwargs):
        if "--query-gpu=driver_model.current" in command:
            raise OSError("query unavailable")
        return SimpleNamespace(stdout=IDENTITY_ROW.encode())

    with pytest.raises(OSError):
        runtime.inspect_gpu_device(
            cli=SimpleNamespace(run=run), container_name="fixture"
        )


def test_wrong_device_identity_still_refuses_before_capability():
    stale = IDENTITY_ROW.replace(GPU_PROFILE.device_uuid, "GPU-other").encode()

    def run(command, **kwargs):
        if "--query-gpu=driver_model.current" in command:
            return SimpleNamespace(stdout=b"N/A")
        return SimpleNamespace(stdout=stale)

    with pytest.raises(WorkerFailure):
        runtime.inspect_gpu_device(
            cli=SimpleNamespace(run=run), container_name="fixture"
        )


# --- device release ----------------------------------------------------------


def _release_capture(monkeypatch, driver_model, *, processes=b"", memory=None):
    from carbon.reconstruction.worker import docker_runtime

    if memory is None:
        memory = f"{GPU_PROFILE.device_uuid}, 0, Disabled".encode()
    monkeypatch.setattr(Path, "is_file", lambda self: True)

    def capture(command, **kwargs):
        if "--query-gpu=driver_model.current" in command:
            return SimpleNamespace(
                returncode=0 if driver_model is not None else 1,
                stdout=driver_model or b"",
            )
        if "--query-compute-apps=pid,gpu_uuid" in command:
            return SimpleNamespace(returncode=0, stdout=processes)
        return SimpleNamespace(returncode=0, stdout=memory)

    monkeypatch.setattr(docker_runtime, "_bounded_capture", capture)


def test_release_from_unestablished_source_quarantines(host_grant, monkeypatch):  # noqa: F811
    """Zero reported memory and a disabled display cannot rescue a blind source."""
    _release_capture(monkeypatch, b"WDDM")
    with pytest.raises(WorkerFailure) as error:
        runtime.verify_device_release()
    assert error.value.code is WorkerCode.CLEANUP
    assert (runtime.HOST_ROOT / "device-quarantined").is_file()


def test_release_capability_query_failure_quarantines(host_grant, monkeypatch):  # noqa: F811
    _release_capture(monkeypatch, None)
    with pytest.raises(WorkerFailure):
        runtime.verify_device_release()
    assert (runtime.HOST_ROOT / "device-quarantined").is_file()


def test_release_from_established_idle_source_succeeds(host_grant, monkeypatch):  # noqa: F811
    _release_capture(monkeypatch, b"N/A")
    runtime.verify_device_release()
    assert not (runtime.HOST_ROOT / "device-quarantined").exists()


def test_release_from_established_source_still_rejects_live_process(
    host_grant,  # noqa: F811
    monkeypatch,
):
    _release_capture(monkeypatch, b"N/A", processes=b"123, GPU-busy")
    with pytest.raises(WorkerFailure):
        runtime.verify_device_release()
    assert (runtime.HOST_ROOT / "device-quarantined").is_file()


def test_repeated_uncertain_release_keeps_one_quarantine_marker(
    host_grant,  # noqa: F811
    monkeypatch,
):
    """A replayed cleanup cannot clear or duplicate an unreconciled slot."""
    _release_capture(monkeypatch, b"WDDM")
    for _ in range(3):
        with pytest.raises(WorkerFailure):
            runtime.verify_device_release()
    marker = runtime.HOST_ROOT / "device-quarantined"
    assert marker.read_bytes() == b"UNRECONCILED_DEVICE_RELEASE\n"
