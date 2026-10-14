"""PLT-30 shared-route controls: synthetic image/device, no GPU/host execution."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from test_battery_gpu_practice import (
    battery_campaign,
    device,
    gpu_image,
    practice,
    record_bytes,
)
from test_battery_gpu_practice import (
    live as _live,
)
from test_battery_validator_daemon import submission

from carbon.development_session import battery_gpu as gpu
from carbon.development_session import gpu_practice, research_carrier
from carbon.development_session.profile import digest
from carbon.reconstruction import torch_profile
from carbon.reconstruction.accelerators import GPU_PROFILE

live = _live


def test_torch_code_cell_reaches_the_same_pinned_host_check(tmp_path, monkeypatch):
    image, record = torch_image(), device()
    finished = []
    ledger = SimpleNamespace(
        root=tmp_path,
        reserve=lambda *args, **kwargs: {"dispatch": True},
        finish=lambda *args, **kwargs: finished.append(kwargs),
    )
    monkeypatch.setattr(research_carrier, "_gpu_device", lambda: record)
    monkeypatch.setattr(research_carrier, "DockerCLI", lambda: object())
    monkeypatch.setattr(
        research_carrier, "doctor", lambda **kwargs: SimpleNamespace(eligible=True)
    )
    checked = []

    def check(cli, selected, selected_device, pins):
        assert selected is image and selected_device is record
        assert pins == (
            torch_profile.GPU_PROFILE_ID,
            torch_profile.GPU_PROFILE_DIGEST,
            torch_profile.GPU_LOCK_DIGEST,
        )
        checked.append(pins)
        raise RuntimeError("stop-before-container-command")

    monkeypatch.setattr(research_carrier, "_check_gpu_host", check)
    with pytest.raises(RuntimeError, match="stop-before-container-command"):
        research_carrier._run_locked(
            ledger,
            owner="fixture",
            identity="torch-cell",
            source="print(1)",
            files={},
            image=image,
            seconds=60,
            provenance="MINER_SELF_REPORTED",
            extra_resources={},
            miner_authored=True,
            accelerator=research_carrier.MINER_GPU,
        )
    assert len(checked) == 1
    assert len(finished) == 1
    assert finished[0]["result"]["worker_created"] is False


def torch_image():
    return gpu_image(lock=torch_profile.GPU_LOCK_DIGEST)


def test_exact_worker_selects_one_backend_and_keeps_legacy_jax_scope():
    jax, torch = gpu_image(), torch_image()
    assert gpu_practice.is_gpu_image(jax) is True
    assert (
        gpu_practice.is_gpu_image(torch) is False
    )  # Legacy/Burgers callers stay JAX-only.
    assert gpu_practice.gpu_image_backend(torch) == "pytorch"
    assert gpu.image_backends(jax) == ("jax",)
    assert gpu.image_backends(torch) == ("pytorch",)
    assert gpu.gpu_scope(jax)["schema"] == gpu.SCOPE_SCHEMA
    assert gpu.gpu_scope(jax)["program"] == digest(gpu.GPU_PROGRAM.encode())
    scope = gpu.gpu_scope(torch)
    assert scope["schema"] == gpu.TORCH_SCOPE_SCHEMA
    assert scope["profile_digest"] == torch_profile.GPU_PROFILE_DIGEST
    assert scope["program"] == digest(gpu.TORCH_GPU_PROGRAM.encode())
    assert scope["backends"] == ["pytorch"]
    assert scope["score"] is None and scope["official_eligible"] is False
    assert gpu.declared_scope({"gpu_research": [scope]}) == [scope]


@pytest.mark.parametrize(
    "image",
    [
        None,
        SimpleNamespace(lock_digest=torch_profile.GPU_LOCK_DIGEST),
        gpu_image(lock="sha256:" + "0" * 64),
        gpu_image(
            lock=torch_profile.requirements_digest(Path(__file__).resolve().parents[2])
        ),
    ],
)
def test_cpu_unknown_and_unvalidated_images_never_become_gpu_workers(image):
    assert gpu_practice.gpu_image_backend(image) is None
    with pytest.raises(ValueError, match="GPU worker"):
        gpu.image_backends(image)


def test_torch_practice_selects_existing_program_on_the_same_miner_carrier(tmp_path):
    image = torch_image()
    seen = []
    callback = practice(tmp_path, gpu_image_=image, seen=[])
    callback._seed = lambda identity: 0  # Synthetic per-trial randomness only.

    def capture(ledger, **kwargs):
        seen.append(kwargs)
        raise RuntimeError("captured-before-dispatch")

    callback.runner = capture
    strategy = submission(
        "hk", "mlp", backend="pytorch", width=8, depth=1, steps=32
    ).strategy
    assert callback.backend_refusal(strategy) is None
    with pytest.raises(RuntimeError, match="captured-before-dispatch"):
        callback("fixture", strategy)
    assert len(seen) == 1
    assert seen[0]["image"] is image
    assert seen[0]["accelerator"] == research_carrier.MINER_GPU
    assert seen[0]["source"] == gpu.TORCH_GPU_PROGRAM


def test_torch_worker_refuses_jax_recipe_before_carrier_call(tmp_path):
    seen = []
    callback = practice(tmp_path, gpu_image_=torch_image(), seen=seen)
    strategy = submission("hk", "mlp", width=8, depth=1, steps=32).strategy
    assert callback.backend_refusal(strategy) == ("pytorch",)
    with pytest.raises(ValueError, match="GPU practice serves PyTorch recipes only"):
        callback("fixture", strategy)
    assert seen == []


def test_miner_and_validator_use_the_same_exact_torch_image_pins():
    expected = (
        torch_profile.GPU_PROFILE_ID,
        torch_profile.GPU_PROFILE_DIGEST,
        torch_profile.GPU_LOCK_DIGEST,
    )
    assert (
        research_carrier._gpu_pins(torch_image(), research_carrier.MINER_GPU)
        == expected
    )
    assert (
        research_carrier._gpu_pins(torch_image(), research_carrier.VALIDATOR_GPU)
        == expected
    )
    assert research_carrier._gpu_pins(gpu_image(), research_carrier.MINER_GPU) == (
        GPU_PROFILE.profile_id,
        GPU_PROFILE.digest,
        GPU_PROFILE.environment_lock_digest,
    )
    observed = {"framework": "pytorch", "default_backend": "cpu"}
    record = gpu.backend_record(device(), observed, backend="pytorch")
    assert record["profile"] == torch_profile.GPU_PROFILE_ID
    assert (
        record["observed"] == observed
    )  # Never turn a mock CPU observation into GPU evidence.
    assert record["purpose"] == "speed_only"


def test_remote_torch_route_is_not_silently_enabled():
    with pytest.raises(ValueError, match="GPU worker"):
        gpu.remote_worker(torch_image())


def test_local_setup_verifies_the_selected_torch_profile_and_lock(live, monkeypatch):
    from carbon.reconstruction.worker import accelerator_runtime

    image = torch_image()
    live.manifest.write_bytes(record_bytes(image))
    seen = []
    monkeypatch.setattr(
        accelerator_runtime,
        "verify_image_and_toolkit",
        lambda **kwargs: seen.append(kwargs),
    )
    found = live.checks.gpu(live.manifest, campaign=battery_campaign())
    assert found["scope"] == gpu.gpu_scope(image)
    assert len(seen) == 1
    assert seen[0]["image"] == image
    assert seen[0]["profile_digest"] == torch_profile.GPU_PROFILE_DIGEST
    assert seen[0]["lock_digest"] == torch_profile.GPU_LOCK_DIGEST


def test_unsupported_challenge_refuses_torch_before_host_preparation(live, monkeypatch):
    from carbon.reconstruction import onboarding

    live.manifest.write_bytes(record_bytes(torch_image()))

    def no_host(**kwargs):
        pytest.fail("unsupported scope must refuse before host preparation")

    monkeypatch.setattr(onboarding, "observe_local_device", no_host)

    def no_scope(image):
        raise ValueError("unsupported GPU worker")

    from scripts.dev.miner_launchpad.environment_setup import SetupRefused

    with pytest.raises(SetupRefused, match="gpu_image_unverified"):
        live.checks.gpu(live.manifest, campaign=SimpleNamespace(gpu_scope=no_scope))
