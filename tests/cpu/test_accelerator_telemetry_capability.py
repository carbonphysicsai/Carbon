"""Unestablished GPU telemetry must not certify exclusivity or device release.

These are synthetic fixture observations only; no accelerator is initialized and
no host process list is captured. An empty compute-process query and a genuinely
idle device are indistinguishable, so emptiness is evidence only when a
registered observation contract covers the observing source.

No real source is registered. The established-path tests therefore register a
synthetic contract explicitly, to exercise the mechanism. They do not assert
that any actual host, driver model or platform is established.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
import test_accelerator_worker

from carbon.reconstruction.accelerators import GPU_PROFILE
from carbon.reconstruction.worker import accelerator_runtime as runtime
from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

host_grant = test_accelerator_worker.host_grant

SYNTHETIC_CONTRACT = "synthetic-test-only-observation-contract"

IDENTITY_ROW = (
    f"{GPU_PROFILE.device_uuid}, {GPU_PROFILE.device_kind}, "
    f"{GPU_PROFILE.host_driver}, 6144, Disabled"
)


@pytest.fixture
def registered_contract(monkeypatch):
    """Register one synthetic contract; never a real platform or driver model."""
    monkeypatch.setattr(
        runtime,
        "ESTABLISHED_OBSERVATION_CONTRACTS",
        frozenset({SYNTHETIC_CONTRACT}),
    )
    return SYNTHETIC_CONTRACT


def _cli(driver_model, *, processes=b""):
    """Bounded container CLI returning one fixed observation set."""

    def run(command, **kwargs):
        if "--query-gpu=driver_model.current" in command:
            return SimpleNamespace(stdout=driver_model)
        if "--query-compute-apps=pid,gpu_uuid" in command:
            return SimpleNamespace(stdout=processes)
        return SimpleNamespace(stdout=IDENTITY_ROW.encode())

    return SimpleNamespace(run=run)


# --- capability classification -----------------------------------------------


def test_no_observation_contract_is_registered_by_default():
    """The registry ships empty; nothing is established without its own evidence."""
    assert runtime.ESTABLISHED_OBSERVATION_CONTRACTS == frozenset()


@pytest.mark.parametrize("reading", ["WDDM", "wddm", " WDDM "])
def test_documented_incomplete_platforms_are_unsupported(reading):
    assert runtime.enumeration_capability(reading) == runtime.ENUMERATION_UNSUPPORTED


@pytest.mark.parametrize("reading", ["WDDM", "wddm"])
def test_a_contract_cannot_rescue_a_documented_incomplete_platform(
    reading, registered_contract
):
    assert (
        runtime.enumeration_capability(
            reading, observation_contract=registered_contract
        )
        == runtime.ENUMERATION_UNSUPPORTED
    )


@pytest.mark.parametrize(
    "reading", ["N/A", "n/a", "TCC", "", "   ", "UNKNOWN", "[Not Supported]"]
)
def test_driver_model_alone_never_establishes_capability(reading):
    """A driver-model string describes applicability, not Carbon's visibility."""
    assert runtime.enumeration_capability(reading) == runtime.ENUMERATION_UNESTABLISHED


@pytest.mark.parametrize("reading", [None, b"N/A", 0, ["N/A"], object()])
def test_non_text_capability_readings_are_unestablished(reading):
    assert runtime.enumeration_capability(reading) == runtime.ENUMERATION_UNESTABLISHED


@pytest.mark.parametrize("claimed", ["other-contract", "", None, 0, ["x"]])
def test_an_unregistered_claim_does_not_establish_capability(
    claimed, registered_contract
):
    # A grant field or caller argument identifies a claim; it cannot certify it.
    assert (
        runtime.enumeration_capability("N/A", observation_contract=claimed)
        == runtime.ENUMERATION_UNESTABLISHED
    )


def test_registered_contract_establishes_capability(registered_contract):
    assert (
        runtime.enumeration_capability("N/A", observation_contract=registered_contract)
        == runtime.ENUMERATION_ESTABLISHED
    )


# --- strict admission --------------------------------------------------------


def test_wddm_empty_process_query_cannot_admit():
    """The observed live case: WSL returns nothing while a process is attached."""
    with pytest.raises(WorkerFailure) as error:
        runtime.inspect_gpu_device(cli=_cli(b"WDDM"), container_name="fixture")
    assert error.value.code is WorkerCode.POLICY


@pytest.mark.parametrize(
    "reading", [b"N/A", b"TCC", b"WDDM", b"", b"   ", b"[Not Supported]", b"\xff\xfe"]
)
def test_admission_refuses_without_a_registered_contract(reading):
    """Including readings a previous revision wrongly treated as established."""
    with pytest.raises(WorkerFailure):
        runtime.inspect_gpu_device(cli=_cli(reading), container_name="fixture")


def test_established_source_still_admits_and_reports_no_foreign_processes(
    registered_contract,
):
    observation = runtime.inspect_gpu_device(
        cli=_cli(b"N/A"),
        container_name="fixture",
        observation_contract=registered_contract,
    )
    assert observation["uuid"] == GPU_PROFILE.device_uuid
    assert observation["other_compute_processes"] == []
    assert observation["evidence"] == "OBSERVED_NOT_SECURITY_QUALIFIED"
    assert observation["device_memory_cap"] == "EXCLUSIVE_ALLOCATION_NOT_HOST_CGROUP"


def test_established_source_still_rejects_a_reported_foreign_process(
    registered_contract,
):
    with pytest.raises(WorkerFailure):
        runtime.inspect_gpu_device(
            cli=_cli(b"N/A", processes=b"123, GPU-foreign"),
            container_name="fixture",
            observation_contract=registered_contract,
        )


def test_capability_query_failure_is_not_swallowed_into_a_pass():
    def run(command, **kwargs):
        if "--query-gpu=driver_model.current" in command:
            raise OSError("query unavailable")
        return SimpleNamespace(stdout=IDENTITY_ROW.encode())

    with pytest.raises(OSError):
        runtime.inspect_gpu_device(
            cli=SimpleNamespace(run=run), container_name="fixture"
        )


def test_wrong_device_identity_still_refuses_before_capability(registered_contract):
    stale = IDENTITY_ROW.replace(GPU_PROFILE.device_uuid, "GPU-other").encode()

    def run(command, **kwargs):
        if "--query-gpu=driver_model.current" in command:
            return SimpleNamespace(stdout=b"N/A")
        return SimpleNamespace(stdout=stale)

    with pytest.raises(WorkerFailure):
        runtime.inspect_gpu_device(
            cli=SimpleNamespace(run=run),
            container_name="fixture",
            observation_contract=registered_contract,
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


def test_release_from_unsupported_source_quarantines(host_grant, monkeypatch):
    """Zero reported memory and a disabled display cannot rescue a blind source."""
    _release_capture(monkeypatch, b"WDDM")
    with pytest.raises(WorkerFailure) as error:
        runtime.verify_device_release()
    assert error.value.code is WorkerCode.CLEANUP
    assert (runtime.HOST_ROOT / "device-quarantined").is_file()


def test_release_without_a_registered_contract_quarantines(host_grant, monkeypatch):
    _release_capture(monkeypatch, b"N/A")
    with pytest.raises(WorkerFailure):
        runtime.verify_device_release()
    assert (runtime.HOST_ROOT / "device-quarantined").is_file()


def test_release_capability_query_failure_quarantines(host_grant, monkeypatch):
    _release_capture(monkeypatch, None)
    with pytest.raises(WorkerFailure):
        runtime.verify_device_release()
    assert (runtime.HOST_ROOT / "device-quarantined").is_file()


def test_release_from_established_idle_source_succeeds(
    host_grant, monkeypatch, registered_contract
):
    _release_capture(monkeypatch, b"N/A")
    runtime.verify_device_release(observation_contract=registered_contract)
    assert not (runtime.HOST_ROOT / "device-quarantined").exists()


def test_release_from_established_source_still_rejects_live_process(
    host_grant, monkeypatch, registered_contract
):
    _release_capture(monkeypatch, b"N/A", processes=b"123, GPU-busy")
    with pytest.raises(WorkerFailure):
        runtime.verify_device_release(observation_contract=registered_contract)
    assert (runtime.HOST_ROOT / "device-quarantined").is_file()


def test_repeated_uncertain_release_keeps_one_quarantine_marker(
    host_grant, monkeypatch
):
    """A replayed cleanup cannot clear or duplicate an unreconciled slot."""
    _release_capture(monkeypatch, b"WDDM")
    for _ in range(3):
        with pytest.raises(WorkerFailure):
            runtime.verify_device_release()
    marker = runtime.HOST_ROOT / "device-quarantined"
    assert marker.read_bytes() == b"UNRECONCILED_DEVICE_RELEASE\n"
