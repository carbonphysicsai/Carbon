"""Backend observation diagnostics, with no GPU/TPU hardware claim."""

from __future__ import annotations

import importlib
import runpy
import sys
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from carbon.reconstruction.worker import backend_probe as p


def observation(backend=p.Backend.CPU, count=1, platform=None, **changes):
    platform = (
        platform
        or {p.Backend.CPU: "cpu", p.Backend.NVIDIA: "gpu", p.Backend.TPU: "tpu"}[
            backend
        ]
    )
    values = {
        "requested_backend": backend,
        "jax_version": "0.9.0.1",
        "jaxlib_version": "0.9.0.1",
        "process_index": 0,
        "x64_enabled": False,
        "devices": tuple(
            p.DeviceObservation(i, 0, platform, "Test device") for i in range(count)
        ),
    }
    values.update(changes)
    return p.BackendObservation(**values)


class Observer:
    def __init__(self, result):
        self.result, self.calls = result, []

    def observe(self, backend):
        self.calls.append(backend)
        return self.result


@pytest.mark.parametrize("backend", list(p.Backend))
def test_each_backend_accepts_only_its_explicit_observation(backend):
    result = observation(backend)
    observer = Observer(result)
    assert p.probe_backend(p.BackendRequest(backend), observer=observer) is result
    assert observer.calls == [backend]


@pytest.mark.parametrize("backend", [p.Backend.NVIDIA, p.Backend.TPU])
def test_accelerator_request_rejects_cpu_result(backend):
    with pytest.raises(p.BackendProbeError) as failure:
        p.probe_backend(
            p.BackendRequest(backend),
            observer=Observer(observation(backend, platform="cpu")),
        )
    assert failure.value.code is p.ProbeCode.PLATFORM_MISMATCH


def test_wrong_backend_identity_fails():
    with pytest.raises(p.BackendProbeError) as failure:
        p.validate_observation(
            p.BackendRequest(p.Backend.TPU), observation(p.Backend.CPU)
        )
    assert failure.value.code is p.ProbeCode.PLATFORM_MISMATCH


@pytest.mark.parametrize("count", [0, -1, True, 1.0, "1", 1025, None])
def test_request_device_count_is_exact_bounded_integer(count):
    with pytest.raises(p.BackendProbeError) as failure:
        p.BackendRequest(p.Backend.CPU, count)
    assert failure.value.code is p.ProbeCode.INVALID_REQUEST


@pytest.mark.parametrize("backend", ["cpu", "gpu", "cuda", "tpu", None])
def test_request_requires_closed_backend_type(backend):
    with pytest.raises(p.BackendProbeError):
        p.BackendRequest(backend)


@pytest.mark.parametrize(
    "versions", [("1", None), (None, "1"), ("", "1"), ("secret\n", "1"), (True, "1")]
)
def test_runtime_pins_must_be_complete_and_bounded(versions):
    with pytest.raises(p.BackendProbeError) as failure:
        p.BackendRequest(
            p.Backend.CPU, jax_version=versions[0], jaxlib_version=versions[1]
        )
    assert failure.value.code is p.ProbeCode.INVALID_REQUEST


def test_version_mismatch_fails():
    request = p.BackendRequest(
        p.Backend.CPU, jax_version="0.10.2", jaxlib_version="0.10.2"
    )
    with pytest.raises(p.BackendProbeError) as failure:
        p.validate_observation(request, observation())
    assert failure.value.code is p.ProbeCode.RUNTIME_MISMATCH


def test_matching_version_pin_passes():
    request = p.BackendRequest(
        p.Backend.CPU, jax_version="0.9.0.1", jaxlib_version="0.9.0.1"
    )
    assert p.validate_observation(request, observation()).jax_version == "0.9.0.1"


@pytest.mark.parametrize("count", [2, 4])
def test_visibility_must_match_exact_count(count):
    with pytest.raises(p.BackendProbeError) as failure:
        p.validate_observation(
            p.BackendRequest(p.Backend.CPU), observation(count=count)
        )
    assert failure.value.code is p.ProbeCode.DEVICE_COUNT_MISMATCH


def test_duplicate_devices_rejected():
    d = p.DeviceObservation(0, 0, "cpu", "Test")
    with pytest.raises(p.BackendProbeError):
        observation(devices=(d, d))


def test_remote_device_rejected_from_local_observation():
    with pytest.raises(p.BackendProbeError):
        observation(devices=(p.DeviceObservation(0, 1, "cpu", "Test"),))


@pytest.mark.parametrize(
    "field,value",
    [
        ("device_id", -1),
        ("device_id", True),
        ("process_index", "0"),
        ("platform", "cpu\n"),
        ("device_kind", "x" * 161),
        ("device_kind", ""),
    ],
)
def test_invalid_device_metadata(field, value):
    values = {
        "device_id": 0,
        "process_index": 0,
        "platform": "cpu",
        "device_kind": "Test",
    }
    values[field] = value
    with pytest.raises(p.BackendProbeError):
        p.DeviceObservation(**values)


@pytest.mark.parametrize(
    "changes",
    [
        {"devices": []},
        {"devices": ()},
        {"x64_enabled": 0},
        {"jax_version": ""},
        {"process_index": True},
    ],
)
def test_invalid_observation(changes):
    with pytest.raises(p.BackendProbeError):
        observation(**changes)


def test_x64_flag_does_not_claim_fp64_backend_support():
    value = observation(p.Backend.TPU, x64_enabled=True).to_dict()
    assert value["jax_x64_enabled"] is True
    assert "supports_fp64" not in value
    assert value["evidence_kind"] == "LOCAL_RUNTIME_OBSERVATION_ONLY"
    assert "eligible" not in value and "qualified" not in value


def test_serialized_projection_is_detached():
    value = observation()
    exported = value.to_dict()
    exported["devices"][0]["platform"] = "tpu"
    assert value.devices[0].platform == "cpu"


def test_observation_is_frozen():
    value = observation()
    with pytest.raises(FrozenInstanceError):
        value.jax_version = "changed"


def test_observer_exception_redacted_and_no_retry():
    calls = []

    class Broken:
        def observe(self, backend):
            calls.append(backend)
            raise RuntimeError("secret provider path")

    with pytest.raises(p.BackendProbeError) as failure:
        p.probe_backend(p.BackendRequest(p.Backend.NVIDIA), observer=Broken())
    assert failure.value.code is p.ProbeCode.UNAVAILABLE
    assert "secret" not in str(failure.value)
    assert calls == [p.Backend.NVIDIA]


def test_invalid_request_does_not_touch_backend():
    observer = Observer(observation())
    with pytest.raises(p.BackendProbeError):
        p.probe_backend({"backend": "cpu"}, observer=observer)
    assert observer.calls == []


def test_observer_cannot_return_untyped_data():
    with pytest.raises(p.BackendProbeError):
        p.probe_backend(p.BackendRequest(p.Backend.CPU), observer=Observer({}))


def install_fake_jax(monkeypatch, *, fail=False):
    queries = []

    def local_devices(*, backend):
        queries.append(backend)
        if fail:
            raise RuntimeError("private CUDA failure")
        platform = {"cpu": "cpu", "cuda": "gpu", "tpu": "tpu"}[backend]
        return [
            SimpleNamespace(
                id=0, process_index=0, platform=platform, device_kind="Fake"
            )
        ]

    module = SimpleNamespace(
        __version__="0.9.0.1",
        local_devices=local_devices,
        process_index=lambda **kwargs: 0,
        config=SimpleNamespace(jax_enable_x64=False),
    )
    monkeypatch.setitem(sys.modules, "jax", module)
    monkeypatch.setitem(sys.modules, "jaxlib", SimpleNamespace(__version__="0.9.0.1"))
    return queries


@pytest.mark.parametrize("backend", list(p.Backend))
def test_real_adapter_queries_explicit_backend(monkeypatch, backend):
    queries = install_fake_jax(monkeypatch)
    result = p.probe_backend(p.BackendRequest(backend))
    assert queries == [backend.value]
    assert result.requested_backend is backend


def test_failed_cuda_query_never_attempts_cpu(monkeypatch):
    queries = install_fake_jax(monkeypatch, fail=True)
    with pytest.raises(p.BackendProbeError):
        p.probe_backend(p.BackendRequest(p.Backend.NVIDIA))
    assert queries == ["cuda"]


def test_module_import_does_not_initialize_jax(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("unexpected optional runtime import")

    monkeypatch.setattr(importlib, "import_module", deny)
    runpy.run_path(p.__file__, run_name="carbon_backend_import_diagnostic")


def test_cli_outputs_bounded_failure(monkeypatch, capsys):
    install_fake_jax(monkeypatch, fail=True)
    assert p.main(["--backend", "cuda"]) == 2
    text = capsys.readouterr().out
    assert "backend_probe.backend_unavailable" in text
    assert "private" not in text


def test_cli_outputs_observation(monkeypatch, capsys):
    install_fake_jax(monkeypatch)
    assert p.main(["--backend", "cpu"]) == 0
    assert "LOCAL_RUNTIME_OBSERVATION_ONLY" in capsys.readouterr().out


def test_staged_worker_probes_pinned_cpu_before_reconstruction(monkeypatch, tmp_path):
    from carbon.reconstruction.profile import DEPENDENCY_SPECS
    from carbon.reconstruction.worker import protocol

    calls = []
    monkeypatch.setattr(
        protocol,
        "load_worker_request",
        lambda path: (calls.append("decode") or (None, None, None, None, None)),
    )

    def probe(request):
        calls.append("probe")
        pins = {name: version for name, version, _ in DEPENDENCY_SPECS}
        assert request == p.BackendRequest(
            p.Backend.CPU, 1, pins["jax"], pins["jaxlib"]
        )

    def reconstruct(**kwargs):
        calls.append("reconstruct")
        raise protocol.ReconstructionFailure("test.stop.after.probe")

    monkeypatch.setattr(p, "probe_backend", probe)
    monkeypatch.setattr(protocol, "reconstruct", reconstruct)
    assert protocol.run_staged_worker(tmp_path / "input", tmp_path / "scratch") == 20
    assert calls == ["decode", "probe", "reconstruct"]
    assert not (tmp_path / "scratch" / "ready").exists()


@pytest.mark.parametrize("code", list(p.ProbeCode))
def test_staged_worker_backend_failure_never_trains_or_publishes(
    monkeypatch, tmp_path, code
):
    from carbon.reconstruction.worker import protocol

    monkeypatch.setattr(
        protocol, "load_worker_request", lambda path: (None, None, None, None, None)
    )

    def fail_probe(request):
        raise p.BackendProbeError(code)

    def forbidden(**kwargs):
        pytest.fail("reconstruction after rejected backend")

    monkeypatch.setattr(p, "probe_backend", fail_probe)
    monkeypatch.setattr(protocol, "reconstruct", forbidden)
    assert protocol.run_staged_worker(tmp_path / "input", tmp_path / "scratch") == 20
    assert not (tmp_path / "scratch").exists()


def test_invalid_staged_input_does_not_initialize_backend(monkeypatch, tmp_path):
    from carbon.reconstruction.worker import protocol

    def forbidden(request):
        pytest.fail("backend initialization before validated input")

    monkeypatch.setattr(p, "probe_backend", forbidden)
    assert protocol.run_staged_worker(tmp_path / "missing", tmp_path / "scratch") == 20
    assert not (tmp_path / "scratch").exists()
