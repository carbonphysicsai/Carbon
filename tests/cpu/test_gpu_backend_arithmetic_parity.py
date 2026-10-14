"""Same-input arithmetic parity; CPU evidence, or explicit host-owned CUDA mode.

Each framework matches the same exact dyadic float32 answer. No scientific or
training tolerance is selected. CUDA runs select one framework per pinned image.
"""

from __future__ import annotations

import importlib
import os

import numpy as np
import pytest

REQUIRED = os.environ.get("CARBON_REQUIRE_CUDA") == "1"
SELECTED = os.environ.get("CARBON_PARITY_FRAMEWORK")
FRAMEWORKS = (SELECTED,) if SELECTED else ("jax", "pytorch")
X = np.arange(-8, 8, dtype=np.float32).reshape(4, 4) / 16
W = np.arange(-6, 6, dtype=np.float32).reshape(4, 3) / 32
B = np.array([1, -2, 3], dtype=np.float32) / 64
EXPECTED = X @ W + B


def result(framework):
    package = "torch" if framework == "pytorch" else "jax"
    module = (
        importlib.import_module(package) if REQUIRED else pytest.importorskip(package)
    )
    if framework == "pytorch":
        import contextlib

        from carbon.reconstruction import torch_gpu

        guard = (
            torch_gpu.deterministic_cuda(module)
            if REQUIRED
            else contextlib.nullcontext()
        )
        with guard:
            device = "cuda" if REQUIRED else "cpu"
            x, w, b = (
                module.tensor(value, dtype=module.float32, device=device)
                for value in (X, W, B)
            )
            observed = x @ w + b
            assert observed.device.type == device
            return observed.detach().cpu().numpy()
    assert framework == "jax", "unknown selected parity framework"
    import jax.numpy as jnp

    if REQUIRED:
        assert module.default_backend() == "gpu", "CUDA required but JAX is not on GPU"
    observed = jnp.asarray(X) @ jnp.asarray(W) + jnp.asarray(B)
    assert observed.dtype == jnp.float32
    return np.asarray(observed)


@pytest.mark.parametrize("framework", FRAMEWORKS)
def test_same_input_and_parameters_match_the_exact_shared_float32_answer(framework):
    observed = result(framework)
    # Every product and four-term sum is dyadic and exactly representable in
    # float32 here. Zero tolerance is a fixture arithmetic property, not a
    # production or learned-model equivalence threshold.
    np.testing.assert_array_equal(observed, EXPECTED)
    corrupt = observed.copy()
    corrupt[0, 0] += np.float32(1 / 128)
    with pytest.raises(AssertionError):
        np.testing.assert_array_equal(corrupt, EXPECTED)
