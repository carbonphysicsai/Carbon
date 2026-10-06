"""The pinned PyTorch determinism configuration (IMAGE-RELEASE-01).

The Test Lead (2026-10-06): a PyTorch GPU repeat test means nothing without a
pinned determinism configuration to match the XLA one. These tests hold:
- the configuration is exactly the pinned settings, and its cuBLAS workspace
  is the NVIDIA worker overlay's own value;
- the PyTorch worker image builds it in: the recipe checks the installed
  source's digest and labels the image with it, and the release record must
  carry that label;
- dropping, changing or adding any one setting changes the identity, so the
  pinned digest below fails until it is updated on purpose;
- the CPU rebuild path is the pinned configuration (deterministic algorithms,
  the thread count, an explicit generator) and restores the previous state.
  The cuDNN settings act only on CUDA; PyTorch has no CUDA rebuild path yet.

The reproducibility tolerance stays HUMAN_INPUT (OWNER-PYTORCH-BACKEND-01):
nothing here sets one.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from carbon.reconstruction import torch_profile
from carbon.reconstruction.accelerators import GPU_DETERMINISM_ENVIRONMENT

REPOSITORY = Path(__file__).resolve().parents[2]
#: The pinned identity. A changed setting fails here until updated on purpose.
PINNED_DIGEST = (
    "sha256:98e10cf36db23f1f1e030dd2966653b5a6b34021037196c83d83779e6e89cbb6"
)

needs_torch = pytest.mark.skipif(
    os.environ.get("CARBON_REQUIRE_TORCH") != "1"
    and importlib.util.find_spec("torch") is None,
    reason="the science-torch group is not installed",
)


def test_the_configuration_is_exactly_the_pinned_settings():
    assert dict(torch_profile.DETERMINISM) == {
        "use_deterministic_algorithms": True,
        "cudnn_deterministic": True,
        "cudnn_benchmark": False,
        "cublas_workspace_config": ":4096:8",
        "intra_op_threads": 2,
        "seed_source": "reconstruction_seed_explicit_generator",
    }
    # One cuBLAS workspace for JAX and PyTorch: the NVIDIA overlay's own.
    assert (
        dict(torch_profile.DETERMINISM)["cublas_workspace_config"]
        == GPU_DETERMINISM_ENVIRONMENT["CUBLAS_WORKSPACE_CONFIG"]
    )
    assert torch_profile.DETERMINISM_DIGEST == PINNED_DIGEST
    assert torch_profile.determinism_digest() == PINNED_DIGEST


@pytest.mark.parametrize("index", range(len(torch_profile.DETERMINISM)))
def test_dropping_or_changing_any_setting_changes_the_identity(index):
    settings = list(torch_profile.DETERMINISM)
    dropped = settings[:index] + settings[index + 1 :]
    assert torch_profile.determinism_digest(tuple(dropped)) != PINNED_DIGEST
    name, value = settings[index]
    if type(value) is bool:
        changed = not value
    elif type(value) is int:
        changed = value + 1
    else:
        changed = value + "x"
    mutated = settings[:index] + [(name, changed)] + settings[index + 1 :]
    assert torch_profile.determinism_digest(tuple(mutated)) != PINNED_DIGEST
    added = (*settings, ("extra", True))
    assert torch_profile.determinism_digest(added) != PINNED_DIGEST


def test_the_pytorch_worker_image_builds_the_configuration_into_its_identity():
    recipe = (REPOSITORY / ".devcontainer" / "torch" / "Dockerfile").read_text()
    script = (REPOSITORY / "scripts" / "dev" / "torch_worker_image.sh").read_text()
    assert "ARG TORCH_DETERMINISM_DIGEST" in recipe
    label = 'org.opencontainers.image.carbon.torch.determinism="${TORCH_DETERMINISM_DIGEST}"'
    assert label in recipe
    # The build refuses a label that is not the installed source's digest.
    assert 'os.environ["TORCH_DETERMINISM_DIGEST"] != DETERMINISM_DIGEST' in recipe
    assert "DETERMINISM_DIGEST" in script
    assert '--build-arg "TORCH_DETERMINISM_DIGEST=${determinism_digest}"' in script
    # The release record carries it, and a pull refuses an image without it.
    release = (REPOSITORY / "scripts" / "dev" / "worker_image_release.py").read_text()
    assert '"org.opencontainers.image.carbon.torch.determinism"' in release


def test_the_cpu_rebuild_path_is_the_pinned_configuration():
    """Read from the source, without importing torch: the CPU rebuild path's
    own constants are the pinned ones. The battery implementation module is
    not edited here (that would move the battery contract digest)."""
    import ast

    source = (REPOSITORY / "carbon" / "battery" / "torch_training.py").read_text()
    tree = ast.parse(source)
    threads = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and [t.id for t in node.targets if isinstance(t, ast.Name)] == ["THREADS"]
    ]
    pinned = dict(torch_profile.DETERMINISM)
    assert threads == [pinned["intra_op_threads"]]
    assert "torch.use_deterministic_algorithms(True)" in source
    assert pinned["use_deterministic_algorithms"] is True
    # Randomness only through an explicit generator seeded by Carbon.
    assert "torch.Generator().manual_seed(seed)" in source
    assert "torch.manual_seed(" not in source


@needs_torch
def test_deterministic_puts_the_cpu_settings_in_force_and_restores_them():
    import torch

    from carbon.battery import torch_training

    pinned = dict(torch_profile.DETERMINISM)
    before = (torch.are_deterministic_algorithms_enabled(), torch.get_num_threads())
    with torch_training.deterministic():
        assert (
            torch.are_deterministic_algorithms_enabled()
            is pinned["use_deterministic_algorithms"]
        )
        assert torch.get_num_threads() == pinned["intra_op_threads"]
    assert (
        torch.are_deterministic_algorithms_enabled(),
        torch.get_num_threads(),
    ) == before
