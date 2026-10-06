"""The pinned PyTorch determinism profiles, CPU and GPU (IMAGE-RELEASE-01).

The Test Lead (2026-10-06): a PyTorch GPU repeat test means nothing without a
pinned determinism configuration to match the XLA one, and the cuDNN pins go
in a GPU-only profile with its own identity, never in a way that moves a CPU
or Level-0 pin. These tests hold:
- the CPU torch environment (`ENVIRONMENT_DIGEST`, `DEPENDENCY_SPECS`) and
  every Level-0 pin are byte-identical to what they were;
- the CPU and GPU profiles are exactly the pinned settings, each with its own
  digest and label, and the GPU profile's cuBLAS workspace is the NVIDIA
  worker overlay's own value;
- dropping, changing or adding any setting changes the profile identity;
- the PyTorch CPU image builds the CPU profile into its identity;
- the GPU-only module applies every GPU setting on CUDA, refuses without CUDA
  or the pinned workspace, and restores the previous state (a fake torch, so
  no device is needed);
- the CPU rebuild path is the CPU profile.

The reproducibility tolerance stays HUMAN_INPUT (OWNER-PYTORCH-BACKEND-01):
nothing here sets one.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.reconstruction import torch_gpu, torch_profile
from carbon.reconstruction.accelerators import GPU_DETERMINISM_ENVIRONMENT

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_level1 import LEVEL0_PINS

#: The CPU torch environment as it is on main before this ticket.
CPU_ENVIRONMENT_DIGEST = (
    "sha256:569b153aa814fa81136b070deb2df6c436dd9f5d8011d1cfb0fed8cfbb7b9991"
)
#: The pinned identities. A changed setting fails here until updated on purpose.
CPU_PROFILE_DIGEST = torch_profile.determinism_digest(
    torch_profile.CPU_DETERMINISM, torch_profile.CPU_DETERMINISM_SCHEMA
)
GPU_SETTINGS = {
    "use_deterministic_algorithms": True,
    "intra_op_threads": 2,
    "seed_source": "reconstruction_seed_explicit_generator",
    "cudnn_deterministic": True,
    "cudnn_benchmark": False,
    "cublas_workspace_config": ":4096:8",
}

needs_torch = pytest.mark.skipif(
    os.environ.get("CARBON_REQUIRE_TORCH") != "1"
    and importlib.util.find_spec("torch") is None,
    reason="the science-torch group is not installed",
)


def test_the_cpu_environment_and_level0_pins_are_unchanged():
    from carbon.battery import contracts

    assert torch_profile.ENVIRONMENT_DIGEST == CPU_ENVIRONMENT_DIGEST
    assert [name for name, _, _ in torch_profile.DEPENDENCY_SPECS] == [
        "torch",
        "torchvision",
        "neuraloperator",
        "nvidia-physicsnemo",
        "numpy",
    ]
    assert contracts.implementation_digest("1.0") == LEVEL0_PINS["implementation"]
    # No GPU module is a battery implementation module.
    assert "torch_gpu.py" not in contracts.IMPLEMENTATION_MODULES


def test_the_profiles_are_exactly_the_pinned_settings_with_their_own_identities():
    cpu = dict(torch_profile.CPU_DETERMINISM)
    gpu = dict(torch_profile.GPU_DETERMINISM)
    assert gpu == GPU_SETTINGS
    assert cpu == {k: GPU_SETTINGS[k] for k in cpu}
    assert set(gpu) - set(cpu) == {
        "cudnn_deterministic",
        "cudnn_benchmark",
        "cublas_workspace_config",
    }
    assert gpu["cublas_workspace_config"] == (
        GPU_DETERMINISM_ENVIRONMENT["CUBLAS_WORKSPACE_CONFIG"]
    )
    assert torch_profile.CPU_DETERMINISM_DIGEST == CPU_PROFILE_DIGEST
    assert torch_profile.GPU_DETERMINISM_DIGEST != CPU_PROFILE_DIGEST
    assert torch_profile.CPU_DETERMINISM_LABEL != torch_profile.GPU_DETERMINISM_LABEL
    # The same settings under the other schema are another identity.
    assert torch_profile.determinism_digest(
        torch_profile.CPU_DETERMINISM, torch_profile.GPU_DETERMINISM_SCHEMA
    ) != (CPU_PROFILE_DIGEST)


def _mutations(settings):
    settings = list(settings)
    for index, (name, value) in enumerate(settings):
        dropped = settings[:index] + settings[index + 1 :]
        if type(value) is bool:
            changed = not value
        elif type(value) is int:
            changed = value + 1
        else:
            changed = value + "x"
        mutated = settings[:index] + [(name, changed)] + settings[index + 1 :]
        yield name, tuple(dropped), tuple(mutated)
    yield "added", (), (*settings, ("extra", True))


@pytest.mark.parametrize("profile", ["CPU", "GPU"])
def test_dropping_changing_or_adding_a_setting_changes_the_identity(profile):
    settings = getattr(torch_profile, profile + "_DETERMINISM")
    schema = getattr(torch_profile, profile + "_DETERMINISM_SCHEMA")
    pinned = getattr(torch_profile, profile + "_DETERMINISM_DIGEST")
    assert torch_profile.determinism_digest(settings, schema) == pinned
    for name, dropped, mutated in _mutations(settings):
        if dropped:
            assert torch_profile.determinism_digest(dropped, schema) != pinned, name
        assert torch_profile.determinism_digest(mutated, schema) != pinned, name


def test_dropping_any_gpu_pin_changes_the_gpu_identity_not_the_cpu_one():
    gpu_only = ("cudnn_deterministic", "cudnn_benchmark", "cublas_workspace_config")
    for name in gpu_only:
        dropped = tuple(s for s in torch_profile.GPU_DETERMINISM if s[0] != name)
        assert (
            torch_profile.determinism_digest(
                dropped, torch_profile.GPU_DETERMINISM_SCHEMA
            )
            != torch_profile.GPU_DETERMINISM_DIGEST
        ), name
    assert torch_profile.CPU_DETERMINISM_DIGEST == CPU_PROFILE_DIGEST


def test_the_pytorch_cpu_image_builds_the_cpu_profile_into_its_identity():
    recipe = (REPOSITORY / ".devcontainer" / "torch" / "Dockerfile").read_text()
    script = (REPOSITORY / "scripts" / "dev" / "torch_worker_image.sh").read_text()
    assert "ARG TORCH_DETERMINISM_DIGEST" in recipe
    label = 'org.opencontainers.image.carbon.torch.determinism="${TORCH_DETERMINISM_DIGEST}"'
    assert label in recipe
    assert torch_profile.CPU_DETERMINISM_LABEL in "org.opencontainers.image." + (
        label.split("org.opencontainers.image.", 1)[1]
    )
    # The build refuses a label that is not the installed source's digest.
    assert 'os.environ["TORCH_DETERMINISM_DIGEST"] != CPU_DETERMINISM_DIGEST' in recipe
    assert "CPU_DETERMINISM_DIGEST" in script
    assert '--build-arg "TORCH_DETERMINISM_DIGEST=${determinism_digest}"' in script
    release = (REPOSITORY / "scripts" / "dev" / "worker_image_release.py").read_text()
    assert f'"{torch_profile.CPU_DETERMINISM_LABEL}"' in release


class FakeTorch:
    """Just the surface `torch_gpu` touches."""

    def __init__(self, cuda=True):
        self.deterministic, self.threads = False, 8
        self.backends = SimpleNamespace(
            cudnn=SimpleNamespace(deterministic=False, benchmark=True)
        )
        self.cuda = SimpleNamespace(is_available=lambda: cuda)

    def are_deterministic_algorithms_enabled(self):
        return self.deterministic

    def use_deterministic_algorithms(self, value):
        self.deterministic = value

    def get_num_threads(self):
        return self.threads

    def set_num_threads(self, value):
        self.threads = value


def test_the_gpu_module_applies_every_gpu_setting_and_restores_them(monkeypatch):
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch = FakeTorch()
    before = torch_gpu.state(torch)
    with torch_gpu.deterministic_cuda(torch) as active:
        assert active == GPU_SETTINGS
        assert torch_gpu.state(torch) == GPU_SETTINGS
    assert torch_gpu.state(torch) == before
    assert torch_gpu.worker_environment() == {"CUBLAS_WORKSPACE_CONFIG": ":4096:8"}


def test_the_gpu_module_refuses_without_cuda_or_the_pinned_workspace(monkeypatch):
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch = FakeTorch(cuda=False)
    with (
        pytest.raises(RuntimeError, match="CUDA device"),
        torch_gpu.deterministic_cuda(torch),
    ):
        pass
    monkeypatch.setenv("CUBLAS_WORKSPACE_CONFIG", ":16:8")
    torch = FakeTorch()
    with (
        pytest.raises(RuntimeError, match="CUBLAS_WORKSPACE_CONFIG"),
        torch_gpu.deterministic_cuda(torch),
    ):
        pass
    # Refused before anything changed.
    assert torch.backends.cudnn.benchmark is True and torch.threads == 8


def test_the_cpu_rebuild_path_is_the_cpu_profile():
    """Read from the source, without importing torch: the CPU rebuild path
    of the current battery implementation applies the CPU profile."""
    source = (REPOSITORY / "carbon" / "battery" / "torch_training.py").read_text()
    tree = ast.parse(source)
    threads = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and [t.id for t in node.targets if isinstance(t, ast.Name)] == ["THREADS"]
    ]
    cpu = dict(torch_profile.CPU_DETERMINISM)
    assert threads == [cpu["intra_op_threads"]]
    assert "torch.use_deterministic_algorithms(True)" in source
    assert cpu["use_deterministic_algorithms"] is True
    assert "torch.Generator().manual_seed(seed)" in source
    assert "torch.manual_seed(" not in source


@needs_torch
def test_deterministic_puts_the_cpu_profile_in_force_and_restores_it():
    import torch

    from carbon.battery import torch_training

    cpu = dict(torch_profile.CPU_DETERMINISM)
    before = (torch.are_deterministic_algorithms_enabled(), torch.get_num_threads())
    with torch_training.deterministic():
        assert (
            torch.are_deterministic_algorithms_enabled()
            is cpu["use_deterministic_algorithms"]
        )
        assert torch.get_num_threads() == cpu["intra_op_threads"]
    assert (
        torch.are_deterministic_algorithms_enabled(),
        torch.get_num_threads(),
    ) == before
