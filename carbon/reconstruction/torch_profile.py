"""The pinned PyTorch reconstruction environment (OWNER-PYTORCH-BACKEND-01).

The sibling of `carbon.reconstruction.profile` for the PyTorch backend: the
environment identity a PyTorch recipe is rebuilt in, and its direct dependency
pins. The versions are the ones `uv.lock` resolves for the `science-torch`
group, CPU wheels from the PyTorch index. The worker image's lock digest pins
the full transitive closure.

The PyTorch worker image is layered on the C-03 JAX worker image, so it also
carries the JAX stack the battery domain code shares.

Pure data: importing this module never imports torch.
"""

from __future__ import annotations

import hashlib

ENVIRONMENT_ID = "carbon_torch_linux_x86_64_py311"
ENVIRONMENT_VERSION = "1.0"


def _tagged(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


#: The exact direct pins, in `uv.lock`'s resolution for `science-torch`:
#: (name, version, build source). Torch and torchvision are the CPU builds
#: from the PyTorch index; the build tag is part of the pin's digest, since a
#: contract version token carries no local label.
PINS = (
    ("torch", "2.13.0", "pytorch-cpu:torch==2.13.0+cpu"),
    ("torchvision", "0.28.0", "pytorch-cpu:torchvision==0.28.0+cpu"),
    ("neuraloperator", "2.0.0", "pypi:neuraloperator==2.0.0"),
    ("nvidia-physicsnemo", "2.2.0", "pypi:nvidia-physicsnemo==2.2.0"),
    ("numpy", "2.4.6", "pypi:numpy==2.4.6"),
)

ENVIRONMENT_DIGEST = _tagged(
    b"python==3.11.*\0"
    + b"\0".join(source.encode() for _, _, source in PINS)
    + b"\0linux-x86_64-cpu"
)

#: The exact-hashed export of the `science-torch` group from `uv.lock`
#: (`uv export --frozen --no-dev --group science-torch --no-emit-project`),
#: which the PyTorch worker image installs. Its sha256 is the image's
#: `lock_digest`, and a deployment checks that binding.
REQUIREMENTS_PATH = ".devcontainer/torch/torch-cpu-py311.txt"


def requirements_digest(root) -> str:
    """The digest a PyTorch worker image built from `root` records."""
    from pathlib import Path

    return _tagged((Path(root) / REQUIREMENTS_PATH).read_bytes())


DEPENDENCY_SPECS = tuple(
    (name, version, _tagged(source.encode())) for name, version, source in PINS
)


# The determinism profiles for PyTorch reconstruction (IMAGE-RELEASE-01).
#
# Two profiles with separate identities, siblings of the XLA configuration in
# `carbon.reconstruction.accelerators` (`GPU_DETERMINISM_XLA_FLAGS`,
# `GPU_DETERMINISM_ENVIRONMENT`). Neither changes `ENVIRONMENT_DIGEST` or
# `DEPENDENCY_SPECS`, so the CPU torch environment stays byte-identical.
#
# CPU (`CPU_DETERMINISM`): what the CPU rebuild path
# (`carbon.battery.torch_training.deterministic`) already applies.
#
#   use_deterministic_algorithms   refuses an op with no deterministic
#                                  implementation instead of silently using a
#                                  nondeterministic one.
#   intra_op_threads               the fixed CPU thread count; reduction order
#                                  depends on it.
#   seed_source                    all randomness comes from Carbon's
#                                  reconstruction seed through an explicit
#                                  `torch.Generator`, never the global RNG.
#
# GPU (`GPU_DETERMINISM`): the CPU settings, PyTorch's in-process CUDA
# settings (`accelerators.GPU_DETERMINISM_TORCH`, beside JAX's XLA flags) and
# the CUDA library controls both backends share
# (`accelerators.GPU_DETERMINISM_ENVIRONMENT`, delivered by the same
# `accelerators.worker_environment` overlay that delivers JAX's). It is part of
# the PyTorch GPU accelerator profile (`GPU_PROFILE_DIGEST`), so a changed
# setting changes that identity, as a changed JAX lock changes JAX's.
#
# These pin configurations only. Whether a repeat on a CUDA device reproduces
# within a tolerance is the owner's (OWNER-PYTORCH-BACKEND-01, HUMAN_INPUT);
# nothing here sets or implies one. That the CUDA settings take effect on a
# device is unverified until a GPU run establishes it.
CPU_DETERMINISM = (
    ("use_deterministic_algorithms", True),
    ("intra_op_threads", 2),
    ("seed_source", "reconstruction_seed_explicit_generator"),
)


def _gpu_determinism():
    from carbon.reconstruction.accelerators import (
        GPU_DETERMINISM_ENVIRONMENT,
        GPU_DETERMINISM_TORCH,
    )

    torch_settings = tuple(
        s for s in GPU_DETERMINISM_TORCH if s[0] not in dict(CPU_DETERMINISM)
    )
    environment = tuple(
        ("environment:" + key, value)
        for key, value in sorted(GPU_DETERMINISM_ENVIRONMENT.items())
    )
    return (*CPU_DETERMINISM, *torch_settings, *environment)


GPU_DETERMINISM = _gpu_determinism()
CPU_DETERMINISM_SCHEMA = "carbon.torch-determinism.cpu.v1"
#: The PyTorch CPU worker image carries the CPU profile's digest under this
#: label (#684). The GPU worker carries JAX's accelerator labels instead.
CPU_DETERMINISM_LABEL = "org.opencontainers.image.carbon.torch.determinism"


def determinism_digest(settings, schema) -> str:
    """The identity of a determinism profile: any changed, dropped or added
    setting, or another schema, changes it."""
    import json

    document = {"schema": schema, "settings": [list(s) for s in settings]}
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return _tagged(raw.encode("ascii"))


CPU_DETERMINISM_DIGEST = determinism_digest(CPU_DETERMINISM, CPU_DETERMINISM_SCHEMA)


# The PyTorch CUDA 13 worker environment (TORCH-GPU-01).
#
# A separate environment on the C-03 worker image, never JAX's: torch
# 2.13.0+cu130 needs cuDNN 9.20.0.48, and the JAX CUDA 13 accelerator lock pins
# cuDNN 9.12.0.46, so the two do not resolve together. The exact-hashed lock is
# `GPU_REQUIREMENTS_PATH` (`uv pip compile` against PyPI plus the PyTorch cu130
# index); its sha256 is the PyTorch GPU worker image's `lock_digest`. It
# carries the PyTorch backend's battery stack (torch, neuraloperator, numpy) and
# not torchvision or nvidia-physicsnemo, which the battery backend never
# imports. The CPU constants above are untouched by it.
GPU_ENVIRONMENT_ID = "carbon_torch_linux_x86_64_py311_cuda13"
GPU_ENVIRONMENT_VERSION = "1.0"
GPU_PINS = (
    ("torch", "2.13.0", "pytorch-cu130:torch==2.13.0+cu130"),
    ("neuraloperator", "2.0.0", "pypi:neuraloperator==2.0.0"),
    ("numpy", "2.4.6", "pypi:numpy==2.4.6"),
)


def gpu_environment_digest(pins=GPU_PINS) -> str:
    """The GPU environment's identity: any changed, dropped or added pin
    changes it. Composed exactly as the CPU `ENVIRONMENT_DIGEST`, with the
    CUDA platform tag."""
    return _tagged(
        b"python==3.11.*\0"
        + b"\0".join(source.encode() for _, _, source in pins)
        + b"\0linux-x86_64-cuda13"
    )


GPU_ENVIRONMENT_DIGEST = gpu_environment_digest()
GPU_REQUIREMENTS_PATH = ".devcontainer/torch/torch-cu130-py311.txt"


def gpu_requirements_digest(root) -> str:
    """The digest a PyTorch GPU worker image built from `root` records."""
    from pathlib import Path

    return _tagged((Path(root) / GPU_REQUIREMENTS_PATH).read_bytes())


# The PyTorch GPU accelerator profile (TORCH-GPU-01), the counterpart of JAX's
# `accelerators.GPU_PROFILE`: what the work needs, identically on every
# machine, and nothing of one host. The two GPU worker images carry their
# profile the same way, under the same labels (`ACCELERATOR_LABELS`): the
# profile digest, and the exact-hashed environment lock. JAX's profile
# document is JAX's own (`carbon.accelerator-profile.v2`) and is not reused,
# so no JAX identity moves.
#: The cu130 lock's sha256, pinned as JAX's profile pins its lock.
GPU_LOCK_DIGEST = (
    "sha256:8ebbccd38e0d1f9b1992242ddb8ff49b31270b439f7a21d50051da55fa796c7e"
)
GPU_PROFILE_ID = "carbon_torch_cuda13_nvidia_development_v1"
ACCELERATOR_LABELS = (
    "org.opencontainers.image.carbon.accelerator.profile",
    "org.opencontainers.image.carbon.accelerator.environment",
)


def gpu_profile_document(determinism=GPU_DETERMINISM, pins=GPU_PINS) -> dict:
    """The PyTorch GPU profile, in the shape of JAX's portable profile."""
    return {
        "schema": "carbon.accelerator-profile.pytorch.v1",
        "profile_id": GPU_PROFILE_ID,
        "backend": "cuda",
        "local_device_count": 1,
        "global_device_count": 1,
        "process_count": 1,
        "topology": "single-device",
        "environment_file": GPU_REQUIREMENTS_PATH,
        "environment_lock_digest": GPU_LOCK_DIGEST,
        "environment_digest": gpu_environment_digest(pins),
        "python": "3.11.16",
        "language": "python-pytorch",
        "determinism": [list(item) for item in determinism],
        "parameter_dtype": "float32",
        "allocation": "EXCLUSIVE_REQUIRED_NOT_VERIFIED",
        "memory_cap": "DEVICE_ENFORCEMENT_UNVERIFIED",
        "admission_enabled": False,
        "execution_acceptance": "NOT_EXECUTED",
        "scientifically_qualified": False,
        "final_comparison_eligible": False,
    }


def gpu_profile_digest(**changes) -> str:
    import json

    raw = json.dumps(
        gpu_profile_document(**changes), sort_keys=True, separators=(",", ":")
    )
    return _tagged(raw.encode("ascii"))


GPU_PROFILE_DIGEST = gpu_profile_digest()
