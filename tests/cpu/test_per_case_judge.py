"""The judge grades one case at a time: no case's output depends on another case.

Claims tested:

1. `Prepared.predict(isolated=True)` puts each case alone in row 0 of the declared
   batch with a fixed constant (zeros) in the other rows, so a graph that mixes
   across the batch axis cannot read its neighbours.
2. For a graph with no batch coupling, isolated and batched outputs agree.
3. The positive control: a deliberately batch-mean graph changes with its
   neighbours when batched, and does not when isolated. A check that cannot fail
   proves nothing.
4. `grade.inference_cost` keeps reporting the model's per-case cost (flops per
   declared batch call divided by the batch), not the padded compute of the
   isolated judge.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

import jax.numpy as jnp
import numpy as np

from carbon.level4 import grade
from carbon.level4.train import Prepared

BATCH = 4


def _prepared(apply):
    return Prepared(init=None, apply=apply, batch=BATCH, parameters=())


def _independent(params, x):
    return [x * 2.0 + params[0]]


def _batch_mean(params, x):
    return [x - jnp.mean(x, axis=0, keepdims=True) + params[0]]


def _cases(seed, n):
    return jnp.asarray(np.random.default_rng(seed).normal(size=(n, 3)), jnp.float32)


@pytest.mark.parametrize("n", [1, 3, 4, 7, 10])
def test_isolated_equals_batched_for_a_graph_without_batch_coupling(n):
    prepared, params, x = _prepared(_independent), [jnp.float32(0.5)], _cases(1, n)
    batched = prepared.predict(params, x)[0]
    isolated = prepared.predict(params, x, isolated=True)[0]
    assert isolated.shape == batched.shape == (n, 3)
    assert np.allclose(np.asarray(isolated), np.asarray(batched), atol=1e-6)


def test_a_batch_mean_graph_reads_its_neighbours_batched_but_not_isolated():
    prepared, params = _prepared(_batch_mean), [jnp.float32(0.0)]
    x = _cases(2, 6)
    other = x.at[1:].set(_cases(3, 5))  # case 0 unchanged, every neighbour replaced
    # Positive control: batched, case 0's output changes with its neighbours.
    a = np.asarray(prepared.predict(params, x)[0])[0]
    b = np.asarray(prepared.predict(params, other)[0])[0]
    assert not np.allclose(a, b, atol=1e-3)
    # Isolated, case 0's output is identical whatever its neighbours are.
    a = np.asarray(prepared.predict(params, x, isolated=True)[0])[0]
    b = np.asarray(prepared.predict(params, other, isolated=True)[0])[0]
    assert np.array_equal(a, b)


def test_isolated_filler_is_zeros_and_never_another_case():
    seen = []

    def spy(params, x):
        seen.append(np.asarray(x))
        return [x]

    x = _cases(4, 3)
    _prepared(spy).predict([], x, isolated=True)
    assert len(seen) == 3 and all(rows.shape[0] == BATCH for rows in seen)
    for i, rows in enumerate(seen):
        assert np.array_equal(rows[0], np.asarray(x[i]))
        assert not rows[1:].any()


def test_inference_cost_stays_the_per_case_cost_not_the_padded_compute():
    prepared = _prepared(_independent)
    params = [jnp.zeros((), jnp.float32)]
    inputs = [jnp.zeros((BATCH, 3), jnp.float32)]
    cost = grade.inference_cost(prepared, params, inputs)
    assert cost["batch"] == BATCH
    assert cost["flops_per_case"] == pytest.approx(cost["flops_per_call"] / BATCH)
    # The isolated judge pays one declared-batch call per case; the reported
    # per-case cost must not become that call.
    assert cost["flops_per_case"] < cost["flops_per_call"]
