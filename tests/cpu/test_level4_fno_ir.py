"""The authentic FNO2D spectral core through the existing JAX graph boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

jax = pytest.importorskip("jax")
import jax.numpy as jnp
import numpy as np

from carbon.level4 import allowlist, graph, params, tooling

FNO_ALLOWLIST = Path(allowlist.PATH).with_name("allowlist_v2.json")
SHARDING_ALLOWLIST = Path(allowlist.PATH).with_name("allowlist_v3.json")


def _spectral(wr_upper, wi_upper, wr_lower, wi_lower, x):
    # Foundax SpectralConv2d's exact 8x8 linear-convolution FFT sizes/modes.
    ft = jnp.fft.rfft2(x, s=(15, 15), axes=(0, 1), norm="ortho")
    upper = ft[:2, :2, :] * (wr_upper + 1j * wi_upper)
    lower = ft[-2:, :2, :] * (wr_lower + 1j * wi_lower)
    out = jnp.zeros((15, 8, 1), dtype=jnp.complex64)
    out = out.at[:2, :2, :].set(upper)
    out = out.at[-2:, :2, :].set(lower)
    return jnp.fft.irfft2(out, s=(15, 15), axes=(0, 1), norm="ortho")[:8, :8, :]


def test_fno_spectral_output_and_weight_gradient_round_trip():
    weights = [
        jnp.full((2, 2, 1), value, dtype=jnp.float32) for value in (0.4, -0.2, 0.1, 0.3)
    ]
    x = jnp.arange(64, dtype=jnp.float32).reshape(8, 8, 1) / 64
    inputs = (*weights, x)
    rebuilt, doc, raw = tooling.through_bprime(
        _spectral,
        inputs,
        role="forward",
        allowlist=allowlist.load(FNO_ALLOWLIST),
        input_names=[
            "weights/upper_real",
            "weights/upper_imag",
            "weights/lower_real",
            "weights/lower_imag",
            "inputs/x",
        ],
        max_bytes=1 << 20,
    )
    assert graph.parse(raw, max_bytes=1 << 20) == doc
    assert any(
        node["op"] == "fft" for g in doc["graphs"].values() for node in g["nodes"]
    )
    assert doc["allowlist"] == "level4-allowlist-v2"

    def replay(*values):
        return rebuilt(*values)[0]

    np.testing.assert_array_equal(
        np.asarray(replay(*inputs)), np.asarray(_spectral(*inputs))
    )
    native_grad = jax.grad(lambda *w: jnp.sum(_spectral(*w, x)), argnums=(0, 1, 2, 3))(
        *weights
    )
    replay_grad = jax.grad(lambda *w: jnp.sum(replay(*w, x)), argnums=(0, 1, 2, 3))(
        *weights
    )
    for actual, expected in zip(replay_grad, native_grad):
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(expected))


def test_traced_numpy_integer_padding_becomes_strict_json_integer():
    spec = {"padding_config": "padding_config"}
    traced = {"padding_config": ((np.int64(0), np.int64(7), np.int64(0)),)}
    encoded = params.encode(spec, traced, lambda _: None)
    assert encoded == {"padding_config": [[0, 7, 0]]}
    assert params.decode(spec, encoded) == {"padding_config": ((0, 7, 0),)}
    for bad in (((True, 7, 0),), ((0.0, 7, 0),), ((0, 7),)):
        with pytest.raises(graph.GraphRefused) as refused:
            params.encode(spec, {"padding_config": bad}, lambda _: None)
        assert refused.value.code == "parameter_kind_mismatch"
    with pytest.raises(graph.GraphRefused) as refused:
        params.decode(spec, {"padding_config": [[True, 7, 0]]})
    assert refused.value.code == "parameter_kind_mismatch"


def test_prospective_material_keeps_existing_v1_contract():
    old = allowlist.load()
    new = allowlist.load(FNO_ALLOWLIST)
    assert old.version == "level4-allowlist-v1"
    assert new.version == "level4-allowlist-v2"
    assert "scatter" not in old.ops and "reduce_prod" not in old.ops
    assert set(new.ops) - set(old.ops) == {"scatter", "reduce_prod"}
    for op in ("scatter", "reduce_prod"):
        assert new.ops[op]["roles"] == ["forward"]


def test_scatter_replacement_metadata_and_malformed_values():
    from jax.lax import GatherScatterMode, ScatterDimensionNumbers

    spec = allowlist.load(FNO_ALLOWLIST).ops["scatter"]["params"]
    traced = {
        "dimension_numbers": ScatterDimensionNumbers((0, 1, 2), (), (0, 1)),
        "indices_are_sorted": True,
        "unique_indices": True,
        "mode": GatherScatterMode.FILL_OR_DROP,
        "update_consts": (),
        "update_jaxpr": None,
    }
    encoded = params.encode(spec, traced, lambda _: None)
    assert (
        params.decode(spec, encoded)["dimension_numbers"] == traced["dimension_numbers"]
    )
    for field, value in (("update_jaxpr", object()), ("update_consts", (1,))):
        with pytest.raises(graph.GraphRefused) as refused:
            params.encode(spec, {**traced, field: value}, lambda _: None)
        assert refused.value.code == "parameter_not_default"
    for field, value in (("indices_are_sorted", 1), ("mode", "untrusted")):
        with pytest.raises(graph.GraphRefused) as refused:
            params.decode(spec, {**encoded, field: value})
        assert refused.value.code == "parameter_kind_mismatch"
    bad_dims = dict(encoded["dimension_numbers"], update_window_dims=[0, 0, 2])
    with pytest.raises(graph.GraphRefused) as refused:
        params.decode(spec, {**encoded, "dimension_numbers": bad_dims})
    assert refused.value.code == "parameter_kind_mismatch"


def test_effectful_trace_refuses_before_lowering_any_primitive():
    from carbon.level4.tooling import lower_jax

    def effectful(x):
        jax.debug.callback(lambda _: None, x)
        return x

    closed = jax.make_jaxpr(effectful)(jax.ShapeDtypeStruct((1,), jnp.float32))
    with pytest.raises(graph.GraphRefused) as refused:
        lower_jax.lower(
            closed,
            role="forward",
            allowlist=allowlist.load(FNO_ALLOWLIST),
            input_names=["inputs/x"],
        )
    assert refused.value.code == "op_refused"


def test_nondefault_sharding_refusal_names_op_and_type_without_value():
    from carbon.level4.tooling import lower_jax

    shape = jax.ShapeDtypeStruct((8, 8, 1), jnp.float32)
    closed = jax.make_jaxpr(lambda x: jnp.broadcast_to(x, (2, 8, 8, 1)))(shape)
    eqn = next(e for e in closed.jaxpr.eqns if e.primitive.name == "broadcast_in_dim")
    bad_value = object()
    eqn.params["sharding"] = bad_value
    with pytest.raises(graph.GraphRefused) as refused:
        lower_jax.lower(
            closed,
            role="forward",
            allowlist=allowlist.load(FNO_ALLOWLIST),
            input_names=["inputs/x"],
        )
    assert refused.value.code == "parameter_not_default"
    assert "op broadcast_in_dim parameter sharding type builtins.object" in str(
        refused.value
    )
    assert repr(bad_value) not in str(refused.value)


def _named_sharding(spec=(), *, repeated_device=False):
    from jax.sharding import Mesh, NamedSharding, PartitionSpec

    device = jax.devices("cpu")[0]
    devices = [device, device] if repeated_device else [device]
    mesh = Mesh(np.asarray(devices), ("d",))
    return NamedSharding(mesh, PartitionSpec(*spec))


def test_sharding_material_changes_only_broadcast_placement():
    old = allowlist.load(FNO_ALLOWLIST)
    new = allowlist.load(SHARDING_ALLOWLIST)
    assert new.version == "level4-allowlist-v3"
    assert set(old.ops) == set(new.ops)
    for op in old.ops:
        old_op = old.ops[op]
        new_op = new.ops[op]
        if op == "broadcast_in_dim":
            assert old_op["params"]["sharding"] == "none"
            assert new_op["params"]["sharding"] == "owned_single_device_sharding"
            assert {
                **old_op,
                "params": {
                    **old_op["params"],
                    "sharding": "owned_single_device_sharding",
                },
            } == new_op
        else:
            assert old_op == new_op


def test_owned_single_device_sharding_replays_as_runtime_owned_default():
    sharding = _named_sharding()
    spec = {"sharding": "owned_single_device_sharding"}
    assert params.encode(spec, {"sharding": sharding}, lambda _: None) == {
        "sharding": None
    }
    assert params.decode(spec, {"sharding": None}) == {"sharding": None}
    with pytest.raises(graph.GraphRefused) as refused:
        params.decode(spec, {"sharding": {"mesh": "d"}})
    assert refused.value.code == "parameter_not_default"

    shape = jax.ShapeDtypeStruct((8, 8, 1), jnp.float32)
    closed = jax.make_jaxpr(
        lambda x: jax.lax.broadcast_in_dim(
            x, (2, 8, 8, 1), (1, 2, 3), out_sharding=sharding
        )
    )(shape)
    traced = next(
        eqn.params["sharding"]
        for eqn in closed.jaxpr.eqns
        if eqn.primitive.name == "broadcast_in_dim"
    )
    assert type(traced.mesh).__name__ == "AbstractMesh"
    assert traced.mesh.size == 1
    assert params.encode(spec, {"sharding": traced}, lambda _: None) == {
        "sharding": None
    }
    from carbon.level4.tooling import lower_jax

    doc = lower_jax.lower(
        closed,
        role="forward",
        allowlist=allowlist.load(SHARDING_ALLOWLIST),
        input_names=["inputs/x"],
    )
    node = next(
        n for n in doc["graphs"]["main"]["nodes"] if n["op"] == "broadcast_in_dim"
    )
    assert node["params"]["sharding"] is None
    assert doc["allowlist"] == "level4-allowlist-v3"

    def broadcast(x):
        return jax.lax.broadcast_in_dim(
            x, (2, 8, 8, 1), (1, 2, 3), out_sharding=sharding
        )

    x = jnp.arange(64, dtype=jnp.float32).reshape(8, 8, 1)
    rebuilt, _, _ = tooling.through_bprime(
        broadcast,
        (x,),
        role="forward",
        allowlist=allowlist.load(SHARDING_ALLOWLIST),
        input_names=["inputs/x"],
        max_bytes=1 << 20,
    )
    np.testing.assert_array_equal(np.asarray(rebuilt(x)[0]), np.asarray(broadcast(x)))
    np.testing.assert_array_equal(
        np.asarray(jax.grad(lambda value: jnp.sum(rebuilt(value)[0]))(x)),
        np.asarray(jax.grad(lambda value: jnp.sum(broadcast(value)))(x)),
    )


@pytest.mark.parametrize(
    "sharding",
    [
        pytest.param(lambda: _named_sharding(("d",)), id="named-partition-axis"),
        pytest.param(
            lambda: _named_sharding(repeated_device=True), id="duplicate-device-mesh"
        ),
        pytest.param(lambda: object(), id="unknown-sharding-type"),
    ],
)
def test_unsafe_or_unknown_sharding_stays_refused(sharding):
    spec = {"sharding": "owned_single_device_sharding"}
    with pytest.raises(graph.GraphRefused) as refused:
        params.encode(spec, {"sharding": sharding()}, lambda _: None)
    assert refused.value.code == "parameter_not_default"


def test_abstract_single_slot_named_partition_stays_refused():
    from jax.sharding import NamedSharding, PartitionSpec

    # JAX reports this as replicated on one slot, despite the named axis.
    sharding = _named_sharding()
    shape = jax.ShapeDtypeStruct((8, 8, 1), jnp.float32)
    closed = jax.make_jaxpr(
        lambda x: jax.lax.broadcast_in_dim(
            x, (2, 8, 8, 1), (1, 2, 3), out_sharding=sharding
        )
    )(shape)
    traced = next(
        eqn.params["sharding"]
        for eqn in closed.jaxpr.eqns
        if eqn.primitive.name == "broadcast_in_dim"
    )
    assert type(traced.mesh).__name__ == "AbstractMesh"
    partitioned = NamedSharding(traced.mesh, PartitionSpec("d"))
    assert partitioned.is_fully_replicated
    with pytest.raises(graph.GraphRefused) as refused:
        params.encode(
            {"sharding": "owned_single_device_sharding"},
            {"sharding": partitioned},
            lambda _: None,
        )
    assert refused.value.code == "parameter_not_default"


def test_historical_v2_still_refuses_named_sharding():
    from carbon.level4.tooling import lower_jax

    sharding = _named_sharding()
    shape = jax.ShapeDtypeStruct((8, 8, 1), jnp.float32)
    closed = jax.make_jaxpr(
        lambda x: jax.lax.broadcast_in_dim(
            x, (2, 8, 8, 1), (1, 2, 3), out_sharding=sharding
        )
    )(shape)
    with pytest.raises(graph.GraphRefused) as refused:
        lower_jax.lower(
            closed,
            role="forward",
            allowlist=allowlist.load(FNO_ALLOWLIST),
            input_names=["inputs/x"],
        )
    assert refused.value.code == "parameter_not_default"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("compiler_options_kvs", (("xla_cpu_enable_fast_math", "true"),)),
        ("inline", True),
        ("keep_unused", True),
        ("donated_invars", (True,)),
        ("in_shardings", ("untrusted-placement",)),
        ("ctx_mesh", "untrusted-mesh"),
    ],
)
def test_nondefault_jit_metadata_refuses(name, value):
    with pytest.raises(graph.GraphRefused) as refused:
        params.encode({name: "call_metadata"}, {name: value}, lambda _: None)
    assert refused.value.code == "parameter_not_default"
