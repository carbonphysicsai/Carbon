"""Level 4 G4 init checks and G6 training (development only).

Claims tested:

1. Init data flow: an init graph takes only Carbon's key; it may return
   key-derived values and uniform fills, but never a key, a table built from
   `iota`, or a table assembled from pieces.
2. A submission's init outputs must match the forward graph's parameters,
   and the forward graph must be lowered at the pinned batch.
3. `Prepared.predict` pads cases into blocks of the declared batch; every
   case's result equals the declared graph's.
4. E1: battery's Level 0 MLP (classic path) and DeepONet (general path),
   lowered into submissions and run through G3, G4 and G6, reproduce the
   declarative path's parameters and predictions bit for bit on CPU.
5. A minibatch recipe trains with Carbon's own key schedule: deterministic,
   and by design not the declarative path's key.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, submission, tooling, train, validate

MAX_BYTES = 1 << 26  # the tests' parser bound; not a G3 limit


@pytest.fixture(scope="module")
def allowlist():
    return allowlist_module.load()


def _init_doc(allowlist, fn):
    import jax

    _, doc, _ = tooling.through_bprime(
        fn,
        (jax.random.PRNGKey(0),),
        role="init",
        allowlist=allowlist,
        input_names=["carbon/key"],
        max_bytes=MAX_BYTES,
    )
    return doc


def test_init_data_flow(allowlist):
    import jax
    import jax.numpy as jnp

    def honest(key):
        return [jax.random.normal(key, (3, 2)) * 0.5, jnp.zeros(2), jnp.ones(2) * 0.1]

    validate.check_init(_init_doc(allowlist, honest), allowlist)

    cases = {
        "returns its key": (
            lambda key: [key, jax.random.normal(key, (2,))],
            "init_returns_key",
        ),
        "iota table": (
            lambda key: [jax.random.normal(key, (2,)), jnp.sin(jnp.arange(6.0) * 3.7)],
            "init_output_not_keyed",
        ),
        "table from pieces": (
            lambda key: [
                jax.random.normal(key, (2,)),
                jnp.concatenate([jnp.zeros(3), jnp.ones(3)]),
            ],
            "init_output_not_keyed",
        ),
    }
    for label, (fn, code) in cases.items():
        with pytest.raises(graph.GraphRefused) as refused:
            validate.check_init(_init_doc(allowlist, fn), allowlist)
        assert refused.value.code == code, label


def _submission(allowlist, *, n=4, init_shape=(3, 2)):
    import jax
    import jax.numpy as jnp

    def forward(w, b, x):
        return jnp.tanh(x @ w + b)

    _, fwd, _ = tooling.through_bprime(
        forward,
        (jnp.ones((3, 2)), jnp.zeros(2), jnp.ones((n, 3))),
        role="forward",
        allowlist=allowlist,
        input_names=["params/0", "params/1", "inputs/x"],
        max_bytes=MAX_BYTES,
    )
    ini = _init_doc(
        allowlist, lambda key: [jax.random.normal(key, init_shape), jnp.zeros(2)]
    )
    interface = validate.Interface(
        inputs=(("inputs/x", "float32", (3,)),), outputs=(("float32", (2,)),)
    )
    manifest, files = submission.build(
        challenge="example",
        interface=interface.digest(),
        allowlist=allowlist,
        forward=fwd,
        init=ini,
    )
    _, parsed = submission.verify(
        submission.canonical(manifest),
        files,
        allowlist=allowlist,
        challenge="example",
        interface=interface.digest(),
        max_bytes=MAX_BYTES,
    )
    return parsed, interface


def test_submission_pairs_init_with_forward(allowlist):
    parsed, interface = _submission(allowlist)
    verdict = validate.validate_submission(
        parsed, allowlist, interface=interface, batch=4
    )
    assert verdict["status"] == "admitted" and verdict["batch"] == 4
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate_submission(parsed, allowlist, interface=interface, batch=8)
    assert refused.value.code == "interface_batch"
    bad, interface = _submission(allowlist, init_shape=(2, 3))
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate_submission(bad, allowlist, interface=interface, batch=4)
    assert refused.value.code == "init_outputs_mismatch"


def test_predict_pads_to_the_declared_batch(allowlist):
    import jax
    import jax.numpy as jnp
    import numpy as np

    parsed, interface = _submission(allowlist)
    verdict = validate.validate_submission(
        parsed, allowlist, interface=interface, batch=4
    )
    prepared = train.prepare(parsed, allowlist, verdict=verdict)
    init_key, train_key = train.keys(3)
    assert not np.array_equal(np.asarray(init_key), np.asarray(train_key))
    params = prepared.init(init_key)
    x = jax.random.normal(jax.random.PRNGKey(1), (10, 3))
    out = np.asarray(prepared.predict(params, x)[0])
    assert out.shape == (10, 2)
    for start in (0, 4):
        block = np.asarray(prepared.apply(params, x[start : start + 4])[0])
        assert np.array_equal(out[start : start + 4], block)
    tail = jnp.pad(x[8:], [(0, 2), (0, 0)])
    assert np.array_equal(out[8:], np.asarray(prepared.apply(params, tail)[0])[:2])


@pytest.mark.parametrize("label", ["scaffold_mlp", "panel_deeponet"])
def test_e1_level0_through_the_gates(allowlist, label):
    from carbon.battery import level4 as battery

    result = battery.graph_equivalence(
        allowlist, battery.level0_strategies()[label], steps=16, max_bytes=MAX_BYTES
    )
    assert result["identical"], result
    assert result["status"] == "admitted"  # under the owner's caps


def test_minibatch_recipe_uses_carbons_key(allowlist):
    from carbon.battery import level4 as battery

    base = battery.level0_strategies()["panel_deeponet"]["parameters"]
    strategy = battery.strategy("deeponet", {**base, "batch_size": 64})
    first = battery.graph_equivalence(
        allowlist, strategy, steps=16, max_bytes=MAX_BYTES
    )
    again = battery.graph_equivalence(
        allowlist, strategy, steps=16, max_bytes=MAX_BYTES
    )
    assert first["batch"] == 64
    assert first["graph_params_sha256"] == again["graph_params_sha256"]
    assert not first["identical"]  # Carbon's training key, not the recipe's
