"""The PyTorch GPU (CUDA 13) worker image and its environment (TORCH-GPU-01).

The owner confirmed PyTorch GPU rebuilds (2026-10-06, relayed). torch
2.13.0+cu130 needs cuDNN 9.20.0.48; the JAX CUDA 13 lock pins 9.12.0.46, so the
two do not resolve together, and the PyTorch GPU worker is a separate image on
the C-03 worker with its own environment. JAX's lock is untouched. Nothing
here builds an image or reaches a network. What is held:
- the committed lock is the exact-hashed cu130 resolution, its command line
  naming repository paths, and it is not the JAX accelerator lock;
- it is constrained to the CPU PyTorch export: every package the two share
  is at the identical version, torch alone differing by its build;
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
    "--index-strategy unsafe-best-match "
    "--constraint .devcontainer/torch/torch-cu130-py311.constraints.txt "
    "--output-file .devcontainer/torch/torch-cu130-py311.txt"
)
CPU_EXPORT = REPOSITORY / torch_profile.REQUIREMENTS_PATH
CONSTRAINTS = REPOSITORY / ".devcontainer/torch/torch-cu130-py311.constraints.txt"
#: Each guard the recipe must keep, by the line that implements it.
GUARDS = {
    "lock_digest": 'test "sha256:$(sha256sum /opt/carbon/torch-gpu-requirements.txt',
    "hashes_only": "--require-hashes --only-binary=:all: --no-deps",
    "c03_unchanged": "the cu130 lock changed the C-03 environment",
    "pins": "is not the pinned {expected}",
    "profile_check": "the accelerator profile label is not the installed source's profile",
    "lock_check": "the environment lock is not the profile's",
    "profile_label": 'org.opencontainers.image.carbon.accelerator.profile="${TORCH_GPU_PROFILE_DIGEST}"',
    "environment_label": 'org.opencontainers.image.carbon.accelerator.environment="${TORCH_GPU_LOCK_DIGEST}"',
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
    assert contracts.implementation_digest("1.0") == LEVEL0_PINS["implementation"]
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
    # Its parent is the C-03 worker, built or (in a release) the pushed one.
    assert 'bash "${script_dir}/worker_parent_manifest.sh"' in script
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
        "TORCH_GPU_PROFILE_DIGEST",
    ):
        assert f"ARG {arg}" in recipe
        assert f'--build-arg "{arg}=' in script
    assert "GPU_PROFILE_DIGEST" in script
    assert ".devcontainer/torch/torch-cu130-py311.txt" in script
    assert SCRIPT.stat().st_mode & 0o111


def test_the_image_never_sets_what_the_overlay_sets_as_jaxs_does_not():
    """The platform, the device kind and the CUDA library controls reach a GPU
    worker through the controller's overlay at run time, for JAX's
    accelerator image and this one alike, never from the image."""
    jax = (REPOSITORY / ".devcontainer/accelerators/Dockerfile").read_text()
    for key in (
        "JAX_PLATFORMS",
        "CARBON_ACCELERATOR_DEVICE_KIND",
        "CUBLAS_WORKSPACE_CONFIG",
        "NVIDIA_TF32_OVERRIDE",
        "CARBON_TORCH_DEVICE",
    ):
        assert "ENV " + key not in jax
        assert "ENV " + key not in RECIPE.read_text(), key
    assert torch_profile.GPU_LOCK_DIGEST == torch_profile.gpu_requirements_digest(
        REPOSITORY
    )


def shared_version_drift(cpu, cuda):
    """Packages both PyTorch environments install at different versions,
    torch's build tag aside."""
    return sorted(
        name
        for name in cpu.keys() & cuda.keys()
        if name != "torch" and cpu[name] != cuda[name]
    )


def test_every_package_shared_with_the_cpu_export_is_the_identical_version():
    cpu, cuda = requirements(CPU_EXPORT), requirements(LOCK)
    assert shared_version_drift(cpu, cuda) == []
    assert cpu["torch"] == "2.13.0+cpu" and cuda["torch"] == "2.13.0+cu130"
    # The general libraries the PyTorch index also serves are PyPI's current
    # ones, exactly as the CPU export has them.
    for name in ("requests", "urllib3", "certifi", "packaging", "tensorly"):
        assert cuda[name] == cpu[name], name
    # A drifted version is caught.
    drifted = dict(cuda, requests="2.28.1")
    assert shared_version_drift(cpu, drifted) == ["requests"]


def test_the_constraints_are_the_cpu_export_without_torch():
    constraints = requirements(CONSTRAINTS)
    cpu = requirements(CPU_EXPORT)
    assert constraints == {k: v for k, v in cpu.items() if k != "torch"}
