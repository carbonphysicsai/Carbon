"""JAX backbones (jNO, foundax) under the prospective v6 allowlist. In the
pinned JAX 0.10.2, `reduce_max` and `reduce_min` carry only `axes`, while v5's
spec also demands `out_sharding`, so v5 refuses every JAX `max`/`min`; binding
`out_sharding` would also break their JVP rule. v6 specifies `axes` only and
admits `tan` and `erfc`; values and gradients match JAX. Torch's softmax, the
only Torch emitter of `reduce_max`, follows whichever spec the allowlist has.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")
jax = pytest.importorskip("jax")

import jax.numpy as jnp
import numpy as np
from jax.scipy import special

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret
from carbon.level4.tooling import lower_jax

V5 = Path(allowlist_module.__file__).with_name("allowlist_v5.json")
V6 = Path(allowlist_module.__file__).with_name("allowlist_v6.json")


def model(w, x):
    h = jnp.tanh(x @ w)
    return (
        jnp.max(h, axis=1)
        - jnp.min(h, axis=1)
        + jnp.tan(h[:, 0] * 0.5)
        + special.erfc(h[:, 1])
    )


def _lower(allowlist):
    closed = lower_jax.trace(
        model,
        jax.ShapeDtypeStruct((3, 4), "float32"),
        jax.ShapeDtypeStruct((5, 3), "float32"),
    )
    return lower_jax.lower(
        closed, role="forward", allowlist=allowlist, input_names=["params/w", "x"]
    )


def test_v5_refuses_a_jax_max():
    with pytest.raises(graph.GraphRefused) as refused:
        _lower(allowlist_module.load(V5))
    assert refused.value.code == "parameters_not_allowlisted"


def test_v6_max_min_tan_erfc_match_jax_values_and_gradients():
    allowlist = allowlist_module.load(V6)
    doc = _lower(allowlist)
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    rebuilt = interpret.rebuild(parsed, allowlist)
    w = jax.random.normal(jax.random.PRNGKey(0), (3, 4), jnp.float32)
    x = jax.random.normal(jax.random.PRNGKey(1), (5, 3), jnp.float32)
    np.testing.assert_allclose(
        np.asarray(rebuilt(w, x)[0]), np.asarray(model(w, x)), rtol=1e-6, atol=1e-6
    )
    got = jax.grad(lambda v: rebuilt(v, x)[0].sum())(w)
    want = jax.grad(lambda v: model(v, x).sum())(w)
    np.testing.assert_allclose(np.asarray(got), np.asarray(want), rtol=1e-5, atol=1e-6)


@pytest.mark.parametrize("path", [V5, V6])
def test_torch_softmax_rebuilds_with_its_gradient_under_either_spec(path):
    torch = pytest.importorskip("torch")
    from carbon.level4.tooling import lower_torch

    class Softmax(torch.nn.Module):
        def forward(self, x):
            return torch.softmax(x, dim=-1) * torch.arange(4.0)

    allowlist = allowlist_module.load(path)
    x = torch.randn(3, 4, generator=torch.Generator().manual_seed(2))
    program = torch.export.export(Softmax(), (x,)).run_decompositions()
    doc, _ = lower_torch.lower(program, allowlist=allowlist)
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    rebuilt = interpret.rebuild(parsed, allowlist)
    value = jnp.asarray(x.numpy())
    np.testing.assert_allclose(
        np.asarray(rebuilt(value)[0]), Softmax()(x).numpy(), rtol=1e-6, atol=1e-6
    )
    grad = jax.grad(lambda v: rebuilt(v)[0].sum())(value)
    want = x.clone().requires_grad_(True)
    Softmax()(want).sum().backward()
    np.testing.assert_allclose(np.asarray(grad), want.grad.numpy(), atol=1e-6)
