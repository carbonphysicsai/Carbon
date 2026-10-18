"""Static dispatch selection; no accelerator or model is launched."""

import pytest

from carbon.development_session.gpu_practice import direct_bundle_accelerators
from carbon.development_session.research_carrier import MINER_GPU
from carbon.reconstruction.accelerators import GPU_PROFILE
from carbon.reconstruction.torch_profile import GPU_LOCK_DIGEST
from carbon.reconstruction.worker.model import WorkerImageIdentity


def _image(lock_digest: str, token: str) -> WorkerImageIdentity:
    digest = "sha256:" + token * 64
    return WorkerImageIdentity(
        digest, digest, digest, digest, lock_digest, digest, digest, digest
    )


def test_direct_cpu_pair_keeps_default_dispatch():
    cpu = _image("sha256:" + "1" * 64, "2")
    assert direct_bundle_accelerators(cpu, cpu) == (None, None)


@pytest.mark.parametrize(
    "lock_digest",
    [GPU_PROFILE.environment_lock_digest],
)
def test_direct_jax_gpu_pair_selects_explicit_controls(lock_digest):
    parent = _image(lock_digest, "3")
    inference = _image(lock_digest, "4")
    assert direct_bundle_accelerators(parent, inference) == (MINER_GPU, MINER_GPU)


@pytest.mark.parametrize(
    "build_lock,infer_lock,expected",
    [
        (GPU_LOCK_DIGEST, GPU_PROFILE.environment_lock_digest, (MINER_GPU, MINER_GPU)),
        (GPU_LOCK_DIGEST, "sha256:" + "1" * 64, (MINER_GPU, None)),
        (GPU_PROFILE.environment_lock_digest, "sha256:" + "1" * 64, (MINER_GPU, None)),
        ("sha256:" + "1" * 64, GPU_PROFILE.environment_lock_digest, (None, MINER_GPU)),
    ],
)
def test_direct_phases_select_controls_independently(build_lock, infer_lock, expected):
    assert (
        direct_bundle_accelerators(_image(build_lock, "5"), _image(infer_lock, "6"))
        == expected
    )


def test_direct_fixed_jax_inference_refuses_torch_gpu_image():
    with pytest.raises(ValueError, match="requires JAX worker"):
        direct_bundle_accelerators(
            _image(GPU_PROFILE.environment_lock_digest, "5"),
            _image(GPU_LOCK_DIGEST, "6"),
        )


def test_direct_pair_requires_exact_image_identities():
    with pytest.raises(ValueError, match="exact direct worker image pair"):
        direct_bundle_accelerators(object(), object())
