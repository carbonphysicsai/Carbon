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


# The determinism configuration for PyTorch reconstruction (IMAGE-RELEASE-01).
#
# The sibling of the XLA configuration pinned in
# `carbon.reconstruction.accelerators` (`GPU_DETERMINISM_XLA_FLAGS` and
# `GPU_DETERMINISM_ENVIRONMENT`):
#
#   use_deterministic_algorithms   refuses an op with no deterministic
#                                  implementation instead of silently using a
#                                  nondeterministic one.
#   cudnn_deterministic            deterministic cuDNN convolution algorithms.
#   cudnn_benchmark=False          no per-run, timing-dependent algorithm choice
#                                  (the PyTorch analogue of autotune level 0).
#   cublas_workspace_config        the fixed cuBLAS workspace that
#                                  deterministic algorithms require on CUDA. It
#                                  is the NVIDIA worker overlay's own value, so
#                                  JAX and PyTorch share one setting.
#   intra_op_threads               the fixed CPU thread count; reduction order
#                                  depends on it.
#   seed_source                    all randomness comes from Carbon's
#                                  reconstruction seed through an explicit
#                                  `torch.Generator`, never the global RNG.
#
# Where each is applied today: the CPU rebuild path
# (`carbon.battery.torch_training.deterministic`) applies deterministic
# algorithms, the thread count and the explicit generator; the NVIDIA worker
# overlay sets the cuBLAS workspace. The cuDNN settings act only on CUDA, and
# PyTorch has no CUDA rebuild path yet: they are applied when it is added.
# That change edits a battery implementation module, so it moves the battery
# contract digest and is a contract migration of its own, not part of this pin.
#
# This pins a configuration only. Whether a repeat on a CUDA device reproduces
# within a tolerance is the owner's (OWNER-PYTORCH-BACKEND-01, HUMAN_INPUT);
# nothing here sets or implies one. That the CUDA settings take effect on a
# device is unverified until a GPU run establishes it.
DETERMINISM = (
    ("use_deterministic_algorithms", True),
    ("cudnn_deterministic", True),
    ("cudnn_benchmark", False),
    ("cublas_workspace_config", ":4096:8"),
    ("intra_op_threads", 2),
    ("seed_source", "reconstruction_seed_explicit_generator"),
)
DETERMINISM_SCHEMA = "carbon.torch-determinism.v1"


def determinism_digest(settings=DETERMINISM) -> str:
    """The identity of a determinism configuration: any changed, dropped or
    added setting changes it. The PyTorch worker image checks it at build time
    and carries it as its `carbon.torch.determinism` label."""
    import json

    document = {"schema": DETERMINISM_SCHEMA, "settings": [list(s) for s in settings]}
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return _tagged(raw.encode("ascii"))


DETERMINISM_DIGEST = determinism_digest()
