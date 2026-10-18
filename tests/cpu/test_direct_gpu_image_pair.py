"""Static dispatch selection; no accelerator or model is launched."""

import pytest

from carbon.development_session.gpu_practice import direct_bundle_accelerator
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
    assert direct_bundle_accelerator(cpu, cpu) is None


@pytest.mark.parametrize(
    "lock_digest",
    [GPU_PROFILE.environment_lock_digest, GPU_LOCK_DIGEST],
)
def test_direct_same_backend_gpu_pair_selects_explicit_controls(lock_digest):
    parent = _image(lock_digest, "3")
    inference = _image(lock_digest, "4")
    assert direct_bundle_accelerator(parent, inference) == MINER_GPU


@pytest.mark.parametrize(
    "build_lock,infer_lock",
    [
        (GPU_PROFILE.environment_lock_digest, "sha256:" + "1" * 64),
        ("sha256:" + "1" * 64, GPU_LOCK_DIGEST),
        (GPU_PROFILE.environment_lock_digest, GPU_LOCK_DIGEST),
    ],
)
def test_direct_mixed_backend_pair_refuses_before_dispatch(build_lock, infer_lock):
    with pytest.raises(ValueError, match="accelerator backends differ"):
        direct_bundle_accelerator(_image(build_lock, "5"), _image(infer_lock, "6"))


def test_direct_pair_requires_exact_image_identities():
    with pytest.raises(ValueError, match="exact direct worker image pair"):
        direct_bundle_accelerator(object(), object())
