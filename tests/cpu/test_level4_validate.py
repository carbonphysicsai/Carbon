"""Level 4 gate G4 (development only): `carbon.level4.validate`.

Claims tested:

1. A clean forward graph that matches the Challenge's interface is
   `blocked_human_input` while any cap is unset, and `admitted` only when
   every cap is set (fixture values, non-production) and met.
2. A cap below a measurement refuses with `cap_exceeded`; an unnamed cap
   stays HUMAN_INPUT and blocks.
3. The interface check refuses unexpected, missing, mistyped or misshapen
   inputs and outputs, and inconsistent batch sizes.
4. The expected role is enforced.
5. Battery's development interface admits a Level 0 recipe's lowered graph
   up to the caps.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, tooling, validate

MAX_BYTES = 1 << 26  # the tests' parser bound; not a G3 limit
#: Fixture caps, far above anything here: NOT production values.
FIXTURE_CAPS = {name: 10**12 for name in allowlist_module.CAPS}


@pytest.fixture(scope="module")
def allowlist():
    return allowlist_module.load()


def _forward(allowlist, batch=5, n_in=3, n_out=2, name="inputs/x"):
    import jax.numpy as jnp

    w = jnp.ones((n_in, n_out), jnp.float32)
    x = jnp.ones((batch, n_in), jnp.float32)
    _, doc, _ = tooling.through_bprime(
        lambda p, v: jnp.tanh(v @ p),
        (w, x),
        role="forward",
        allowlist=allowlist,
        input_names=["params/0", name],
        max_bytes=MAX_BYTES,
    )
    return doc


INTERFACE = validate.Interface(
    inputs=(("inputs/x", "float32", (3,)),), outputs=(("float32", (2,)),)
)


def test_caps_gate_admission(allowlist):
    doc = _forward(allowlist)
    unset = {name: allowlist_module.HUMAN_INPUT for name in allowlist_module.CAPS}
    blocked = validate.validate(
        doc, allowlist, role="forward", interface=INTERFACE, caps=unset
    )
    assert blocked["status"] == "blocked_human_input" and blocked["batch"] == 5
    assert set(blocked["caps"].values()) == {"blocked_human_input"}
    # Unnamed caps are the owner's (OWNER-L4-VALUES-01).
    owners = validate.validate(doc, allowlist, role="forward", interface=INTERFACE)
    assert owners["status"] == "admitted"
    admitted = validate.validate(doc, allowlist, interface=INTERFACE, caps=FIXTURE_CAPS)
    assert admitted["status"] == "admitted"
    partial = {**FIXTURE_CAPS, "call_depth": allowlist_module.HUMAN_INPUT}
    assert (
        validate.validate(doc, allowlist, caps=partial)["status"]
        == "blocked_human_input"
    )
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(doc, allowlist, caps={**FIXTURE_CAPS, "nodes_executed": 1})
    assert refused.value.code == "cap_exceeded"


@pytest.mark.parametrize(
    ("kwargs", "interface", "code"),
    [
        ({"name": "inputs/y"}, INTERFACE, "interface_input_unexpected"),
        ({"name": "secret/x"}, INTERFACE, "interface_input_unexpected"),
        ({"n_in": 4}, INTERFACE, "interface_shape"),
        ({"n_out": 3}, INTERFACE, "interface_shape"),
        (
            {},
            validate.Interface(
                inputs=(("inputs/x", "float64", (3,)),), outputs=(("float32", (2,)),)
            ),
            "interface_dtype",
        ),
        (
            {},
            validate.Interface(
                inputs=(("inputs/x", "float32", (3,)), ("inputs/z", "float32", (1,))),
                outputs=(("float32", (2,)),),
            ),
            "interface_input_missing",
        ),
        (
            {},
            validate.Interface(
                inputs=(("inputs/x", "float32", (3,)),),
                outputs=(("float32", (2,)), ("float32", (2,))),
            ),
            "interface_output_count",
        ),
    ],
)
def test_interface_refusals(allowlist, kwargs, interface, code):
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(_forward(allowlist, **kwargs), allowlist, interface=interface)
    assert refused.value.code == code


def test_inconsistent_batch_refused(allowlist):
    import jax.numpy as jnp

    _, doc, _ = tooling.through_bprime(
        lambda a, b: (a.sum(1, keepdims=True) + b.sum())[:2],
        (jnp.ones((3, 3)), jnp.ones((4, 3))),
        role="forward",
        allowlist=allowlist,
        input_names=["inputs/a", "inputs/b"],
        max_bytes=MAX_BYTES,
    )
    interface = validate.Interface(
        inputs=(("inputs/a", "float32", (3,)), ("inputs/b", "float32", (3,))),
        outputs=(("float32", (1,)),),
    )
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(doc, allowlist, interface=interface)
    assert refused.value.code == "interface_batch"


def test_role_enforced(allowlist):
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(_forward(allowlist), allowlist, role="init")
    assert refused.value.code == "role_mismatch"


def test_battery_development_interface(allowlist):
    import jax

    from carbon.battery import level4 as battery

    strategy = battery.level0_strategies()["panel_deeponet"]
    net = battery.jax_network(strategy, battery.material().train)
    _, p = net["init"](jax.random.PRNGKey(0))
    leaves = jax.tree_util.tree_leaves(p)
    f = jax.ShapeDtypeStruct((1, net["n_in"]), net["dtype"])
    _, doc, _ = tooling.through_bprime(
        net["apply"],
        (p, f),
        role="forward",
        allowlist=allowlist,
        input_names=[f"params/{i}" for i in range(len(leaves))] + ["inputs/features"],
        max_bytes=MAX_BYTES,
    )
    verdict = validate.validate(
        doc,
        allowlist,
        role="forward",
        interface=battery.interface(strategy),
        caps=FIXTURE_CAPS,
    )
    assert verdict["status"] == "admitted" and verdict["batch"] == 1
