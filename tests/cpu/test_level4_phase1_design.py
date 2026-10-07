"""Level 4 Phase 1 design (development only): named functions and Carbon init.

Claims tested:

1. Allowlist v1 is versioned beside v0, whose bytes still carry the digest
   the Phase 0 record names.
2. Every admitted named function is a pinned-JAX kernel: its trace holds
   exactly one `custom_jvp_call`, with no constants.
3. A registered kernel lowers to one `named_function` node, and gradients
   through the rebuilt graph equal native gradients bit for bit (Carbon's own
   rule, never a lowered primal).
4. A miner's custom rule never reaches Carbon: an unregistered rule is
   refused, and a forged rule on a registered primal body is replaced by
   Carbon's own rule.
5. Tampered named-function nodes are refused (unknown, refused, wrong arity,
   malformed name).
6. Battery's relu and softplus recipes now train bit-identically through B'.
7. Carbon-built init for a PyTorch graph: shapes and dtypes from the graph,
   values from Carbon's key and menu; the document does not depend on the
   module's own initialization; malformed declarations are refused.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")
REPOSITORY = Path(__file__).resolve().parents[2]
SPIKE = REPOSITORY / "scripts" / "dev" / "level4_spike"
sys.path.insert(0, str(SPIKE.parent))

from level4_spike import allowlist as allowlist_module
from level4_spike import graph, initializers, interpret, lower_jax, named

MAX_BYTES = 1 << 26  # the tests' parser bound; not a G3 limit


@pytest.fixture(scope="module")
def allowlist():
    return allowlist_module.load()


def test_v1_beside_v0_and_v0_digest_unchanged(allowlist):
    assert allowlist.version == "level4-allowlist-v1"
    assert allowlist.ops["custom_jvp_call"]["default"] == "refuse"
    assert allowlist.ops["named_function"]["params"] == {"name": "name"}
    record = json.loads(
        (allowlist_module.DIRECTORY / "phase0_results.json").read_text()
    )
    v0 = allowlist_module.load(allowlist_module.PATH_V0)
    assert v0.digest == record["allowlist"]["digest"]
    assert not v0.named


def _uses(names):
    return {
        name: entry for name, entry in names.items() if entry["default"] != "refuse"
    }


def test_admitted_names_are_pinned_kernels(allowlist):
    import jax

    admitted = _uses(allowlist.named)
    assert admitted and set(admitted) <= set(named.kernels())
    x = jax.ShapeDtypeStruct((3, 4), "float32")
    for name, entry in admitted.items():
        closed = jax.make_jaxpr(named.kernels()[name])(*[x] * entry["arity"])
        calls = []

        def walk(j, _calls=calls):
            for eqn in getattr(j, "jaxpr", j).eqns:
                if eqn.primitive.name == "custom_jvp_call":
                    _calls.append(eqn.params["num_consts"])
                for value in eqn.params.values():
                    for sub in value if isinstance(value, tuple | list) else [value]:
                        if hasattr(sub, "eqns") or hasattr(sub, "jaxpr"):
                            walk(sub)

        walk(closed)
        assert calls == [0], name


def _rebuild(fn, args, allowlist, role="forward"):
    names = [f"inputs/{i}" for i in range(len(args))]
    return interpret.through_bprime(
        fn,
        tuple(args),
        role=role,
        allowlist=allowlist,
        input_names=names,
        max_bytes=MAX_BYTES,
    )


@pytest.mark.parametrize("name", sorted(_uses(allowlist_module.load().named)))
def test_registered_kernel_gradients_are_carbons(allowlist, name):
    import jax
    import jax.numpy as jnp
    import numpy as np

    kernel = named.kernels()[name]
    arity = allowlist.named[name]["arity"]
    w = jnp.linspace(0.15, 0.85, 12, dtype=jnp.float32).reshape(3, 4)

    def f(v):
        args = [v] if arity == 1 else [v, 1.5 + v]
        out = kernel(*args)
        out = out[0] if isinstance(out, tuple) else out
        return jnp.sum(out * jnp.cos(v))

    rebuilt, doc, _ = _rebuild(f, [w], allowlist, role="loss")
    used = {
        n["params"]["name"]
        for g in doc["graphs"].values()
        for n in g["nodes"]
        if n["op"] == "named_function"
    }
    assert used == {name}
    native = np.asarray(jax.jit(jax.grad(f))(w))
    through = np.asarray(jax.jit(jax.grad(lambda v: rebuilt(v)[0]))(w))
    assert np.array_equal(native, through, equal_nan=True)


def test_unregistered_custom_rule_refused(allowlist):
    import jax
    import jax.numpy as jnp

    @jax.custom_jvp
    def own(v):
        return v * 2.0

    own.defjvp(lambda p, t: (own(*p), t[0] * 3.0))
    with pytest.raises(graph.GraphRefused) as refused:
        closed = lower_jax.trace(lambda v: own(v) + 1.0, jnp.ones((2, 2)))
        lower_jax.lower(
            closed, role="forward", allowlist=allowlist, input_names=["inputs/x"]
        )
    assert refused.value.code == "op_refused"


def test_forged_rule_on_registered_body_gets_carbons_rule(allowlist):
    import jax
    import jax.numpy as jnp
    import numpy as np

    def relu(v):
        return jnp.maximum(v, 0.0)

    @jax.custom_jvp
    def forged(v):
        return jax.jit(relu)(v)  # relu's primal body, structure for structure

    forged.defjvp(lambda p, t: (forged(*p), t[0] * 100.0))  # a rule that lies
    x = jnp.linspace(-1.0, 1.0, 8, dtype=jnp.float32).reshape(2, 4)
    native_relu = jax.nn.relu(x)
    rebuilt, doc, _ = _rebuild(lambda v: forged(v), [x], allowlist)
    ops = [n for g in doc["graphs"].values() for n in g["nodes"]]
    assert [n["params"] for n in ops if n["op"] == "named_function"] == [
        {"name": "relu"}
    ]
    assert np.array_equal(np.asarray(rebuilt(x)[0]), np.asarray(native_relu))
    carbon = jax.grad(lambda v: jnp.sum(rebuilt(v)[0]))(x)
    assert np.array_equal(
        np.asarray(carbon), np.asarray(jax.grad(lambda v: jnp.sum(jax.nn.relu(v)))(x))
    )


def _relu_document(allowlist):
    import jax
    import jax.numpy as jnp

    _, doc, _ = _rebuild(lambda v: jax.nn.relu(v) * 2.0, [jnp.ones((2, 3))], allowlist)
    return doc


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda n: n["params"].update(name="pure_callback"),
            "named_function_not_allowlisted",
        ),
        (lambda n: n["params"].update(name="frexp"), "named_function_refused"),
        (lambda n: n["in"].append(n["in"][0]), "named_function_arity"),
        (lambda n: n["params"].update(name="Relu!"), "parameter_kind_mismatch"),
    ],
)
def test_tampered_named_nodes_refused(allowlist, mutate, code):
    doc = copy.deepcopy(_relu_document(allowlist))
    node = next(
        n
        for g in doc["graphs"].values()
        for n in g["nodes"]
        if n["op"] == "named_function"
    )
    mutate(node)
    with pytest.raises(graph.GraphRefused) as refused:
        interpret.rebuild(graph.parse(graph.dumps(doc), max_bytes=MAX_BYTES), allowlist)
    assert refused.value.code == code


@pytest.mark.parametrize("activation", ["relu", "softplus"])
def test_battery_custom_rule_activations_train_identically(allowlist, activation):
    from level4_spike.adapters import battery

    base = battery.level0_strategies()["scaffold_mlp"]["parameters"]
    s = battery.strategy("mlp", {**base, "activation": activation})
    result = battery.equivalence_general(allowlist, s, steps=16, max_bytes=MAX_BYTES)
    assert result["bprime_matches_native"] and result["predictions_identical"], result


def _torch_document(allowlist, seed):
    import numpy as np
    import torch
    from level4_spike import lower_torch
    from level4_spike.adapters import battery

    from carbon.battery.recipes import features

    m = battery.material()
    strategy = battery.level0_strategies()["default_fno"]
    params, net, _ = battery.torch_network(strategy, m.train, seed=seed)
    f = torch.tensor(features(m.train.x[:4], False).astype(np.float32))
    _, core = lower_torch.export(net, params, f)
    doc, _ = lower_torch.lower(core, allowlist=allowlist)
    return graph.parse(graph.dumps(doc), max_bytes=1 << 30)


def test_carbon_init_for_a_pytorch_graph(allowlist):
    pytest.importorskip("torch")
    pytest.importorskip("neuralop")
    import jax
    import numpy as np
    from level4_spike.adapters import battery

    doc = _torch_document(allowlist, 7)
    assert graph.digest(doc) == graph.digest(_torch_document(allowlist, 8))
    spec = battery.torch_init_spec(doc)
    init = initializers.build(
        initializers.parse(graph.dumps(spec), max_bytes=MAX_BYTES), doc
    )
    first, second = init(jax.random.PRNGKey(3)), init(jax.random.PRNGKey(3))
    inputs = [
        i for i in doc["graphs"]["main"]["inputs"] if i["name"].startswith("params/")
    ]
    for value, again, declared in zip(first, second, inputs):
        assert (
            list(value.shape) == declared["shape"]
            and str(value.dtype) == declared["dtype"]
        )
        assert np.array_equal(np.asarray(value), np.asarray(again))

    def refused(mutate):
        bad = copy.deepcopy(spec)
        mutate(bad)
        with pytest.raises(graph.GraphRefused) as caught:
            initializers.build(bad, doc)
        return caught.value.code

    assert (
        refused(lambda s: s.update(graph="sha256:" + "0" * 64))
        == "init_spec_graph_mismatch"
    )
    assert refused(lambda s: s["parameters"].pop()) == "init_spec_parameters_mismatch"
    assert (
        refused(lambda s: s["parameters"][0].update(initializer="pretrained"))
        == "initializer_not_in_menu"
    )
    assert (
        refused(lambda s: s["parameters"][0].update(fan_in_axes=[9]))
        == "init_spec_axes"
    )
