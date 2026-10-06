"""The PyTorch GPU (CUDA 13) worker image and its environment (TORCH-GPU-01).

The owner confirmed PyTorch GPU rebuilds (2026-10-06, relayed). torch
2.13.0+cu130 needs cuDNN 9.20.0.48; the JAX CUDA 13 lock pins 9.12.0.46, so the
two do not resolve together, and the PyTorch GPU worker is a separate image on
the C-03 worker with its own environment. JAX's lock is untouched. Nothing
here builds an image or reaches a network. What is held:
- the committed lock is the exact-hashed cu130 resolution, its command line
  naming repository paths, and it is not the JAX accelerator lock;
- the GPU environment's pins are the lock's, and its identity moves with any
  pin, while the CPU environment and every Level-0 pin stay byte-identical;
- the image recipe layers on C-03 (never the accelerator image) and keeps
  every guard: the lock digest, the C-03 environment unchanged, the pins, the
  GPU determinism label and the cuBLAS workspace. Dropping any guard is
  caught;
- the build script passes each identity the recipe checks.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from carbon.reconstruction import torch_profile

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_level1 import LEVEL0_PINS

LOCK = REPOSITORY / torch_profile.GPU_REQUIREMENTS_PATH
RECIPE = REPOSITORY / ".devcontainer" / "torch" / "Dockerfile.gpu"
SCRIPT = REPOSITORY / "scripts" / "dev" / "torch_gpu_worker_image.sh"
ACCELERATOR_LOCK = REPOSITORY / ".devcontainer" / "accelerators" / "cuda13-py311.txt"
HEADER = (
    "#    uv pip compile .devcontainer/torch/torch-cu130-py311.in "
    "--python-version 3.11.16 --python-platform x86_64-manylinux_2_31 "
    "--generate-hashes --only-binary=:all: "
    "--extra-index-url https://download.pytorch.org/whl/cu130 "
    "--output-file .devcontainer/torch/torch-cu130-py311.txt"
)
#: Each guard the recipe must keep, by the line that implements it.
GUARDS = {
    "lock_digest": 'test "sha256:$(sha256sum /opt/carbon/torch-gpu-requirements.txt',
    "hashes_only": "--require-hashes --only-binary=:all: --no-deps",
    "c03_unchanged": "the cu130 lock changed the C-03 environment",
    "pins": "is not the pinned {expected}",
    "determinism_label": "the GPU determinism label is not the installed source's profile",
    "cublas_workspace": "the image's CUBLAS_WORKSPACE_CONFIG is not the GPU profile's",
    "cublas_env": "ENV CUBLAS_WORKSPACE_CONFIG=:4096:8",
    "label": 'org.opencontainers.image.carbon.torch.gpu-determinism="${TORCH_GPU_DETERMINISM_DIGEST}"',
    "numeric_user": "USER 65532:65532",
}


def requirements(path):
    pins = {}
    for line in path.read_text().splitlines():
        matched = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)", line)
        if matched:
            pins[matched.group(1).lower()] = matched.group(2)
    return pins


def pin_mismatches(pins, locked):
    """The GPU pins whose exact build is not the lock's."""
    return [
        name
        for name, _version, source in pins
        if locked.get(name) != source.split("==", 1)[1]
    ]


def missing_guards(text):
    return sorted(name for name, line in GUARDS.items() if line not in text)


def test_the_lock_is_the_hashed_cu130_resolution_with_repository_paths():
    text = LOCK.read_text()
    lines = text.splitlines()
    assert lines[1] == HEADER
    assert "\r" not in text
    blocks = re.split(r"\n(?=[a-z0-9])", text.split("\n", 2)[2])
    for block in blocks:
        if re.match(r"[a-z0-9]", block):
            assert "--hash=sha256:" in block, block.splitlines()[0]
    locked = requirements(LOCK)
    assert locked["torch"] == "2.13.0+cu130"
    assert locked["nvidia-cudnn-cu13"] == "9.20.0.48"
    # Why it is separate: the JAX accelerator lock pins another cuDNN.
    assert requirements(ACCELERATOR_LOCK)["nvidia-cudnn-cu13"] == "9.12.0.46"
    assert (REPOSITORY / ".devcontainer/torch/torch-cu130-py311.in").is_file()


def test_the_gpu_pins_are_the_locks_and_any_changed_pin_moves_the_identity():
    locked = requirements(LOCK)
    assert pin_mismatches(torch_profile.GPU_PINS, locked) == []
    pinned = torch_profile.GPU_ENVIRONMENT_DIGEST
    assert torch_profile.gpu_environment_digest() == pinned
    for index, (name, version, source) in enumerate(torch_profile.GPU_PINS):
        changed = list(torch_profile.GPU_PINS)
        changed[index] = (name, version, source + ".post1")
        # The mutation is caught against the lock and moves the identity.
        assert pin_mismatches(changed, locked) == [name]
        assert torch_profile.gpu_environment_digest(tuple(changed)) != pinned
        dropped = tuple(p for p in torch_profile.GPU_PINS if p[0] != name)
        assert torch_profile.gpu_environment_digest(dropped) != pinned
    assert pinned != torch_profile.ENVIRONMENT_DIGEST


def test_the_cpu_environment_and_level0_pins_stay_byte_identical():
    from carbon.battery import contracts

    assert torch_profile.ENVIRONMENT_DIGEST == (
        "sha256:569b153aa814fa81136b070deb2df6c436dd9f5d8011d1cfb0fed8cfbb7b9991"
    )
    assert torch_profile.REQUIREMENTS_PATH == ".devcontainer/torch/torch-cpu-py311.txt"
    assert contracts.implementation_digest() == LEVEL0_PINS["implementation"]
    # The battery contract's dependency pins are the CPU ones only.
    assert all("cu130" not in pin for _, _, pin in contracts.backend_dependency_specs())


def test_the_recipe_layers_on_c03_never_the_accelerator_image():
    text = RECIPE.read_text()
    froms = [line for line in text.splitlines() if line.startswith("FROM ")]
    assert froms[-1] == "FROM ${WORKER_IMAGE_REF}"
    assert not any("accelerator" in line for line in froms)
    assert "COPY .devcontainer/torch/torch-cu130-py311.txt" in text
    assert "cuda13-py311.txt" not in text
    script = SCRIPT.read_text()
    assert 'bash "${script_dir}/c03_worker_image.sh"' in script
    assert "accelerator_worker_image.sh" not in script


def test_the_recipe_keeps_every_guard():
    assert missing_guards(RECIPE.read_text()) == []


@pytest.mark.parametrize("guard", sorted(GUARDS))
def test_dropping_any_guard_is_caught(guard):
    mutated = RECIPE.read_text().replace(GUARDS[guard], "")
    assert missing_guards(mutated) == [guard]


def test_the_build_script_passes_every_identity_the_recipe_checks():
    script = SCRIPT.read_text()
    recipe = RECIPE.read_text()
    for arg in (
        "WORKER_IMAGE_REF",
        "WORKER_IMAGE",
        "TORCH_GPU_RECIPE_DIGEST",
        "TORCH_GPU_LOCK_DIGEST",
        "TORCH_GPU_DETERMINISM_DIGEST",
    ):
        assert f"ARG {arg}" in recipe
        assert f'--build-arg "{arg}=' in script
    assert "GPU_DETERMINISM_DIGEST" in script
    assert ".devcontainer/torch/torch-cu130-py311.txt" in script
    assert SCRIPT.stat().st_mode & 0o111
