# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

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
