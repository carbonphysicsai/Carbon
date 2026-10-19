"""Published Challenge material as named `kit/` graph inputs
(OWNER-L4-CONSTANT-ACCOUNTING-02): admitted only as registered, bound by
Carbon by name, never sliced or padded, and never counted as constants."""

from __future__ import annotations

import io
import os

import numpy as np
import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, initializers, train, validate
from carbon.level4.tooling import lower_jax

BATCH = 4
TABLE = np.linspace(0.5, 1.5, 64).astype(np.float32)
KIT = (("kit/table", "float32", (64,), "sha256:" + "a" * 64),)
NAMES = ["params/0", "inputs/x", "kit/table"]


@pytest.fixture(scope="module")
def allowlist():
    return allowlist_module.load()


def _interface(kit=KIT):
    return validate.Interface(
        inputs=(("inputs/x", "float32", (3,)),), outputs=(("float32", (2,)),), kit=kit
    )


def _forward(w, x, table):
    import jax.numpy as jnp

    # Row-independent: each case reads the published table, not its neighbours.
    return x @ w * jnp.mean(table) + table[:2]


def _doc(allowlist, names=NAMES, table_shape=(64,)):
    import jax.numpy as jnp

    closed = lower_jax.trace(
        _forward,
        jnp.zeros((3, 2), jnp.float32),
        jnp.zeros((BATCH, 3), jnp.float32),
        jnp.zeros(table_shape, jnp.float32),
    )
    return lower_jax.lower(
        closed, role="forward", allowlist=allowlist, input_names=list(names)
    )


def _prepared(allowlist, doc, kit):
    spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(doc),
        "parameters": [
            {
                "input": "params/0",
                "initializer": "he_normal",
                "fan_in_axes": [0],
                "fan_out_axes": [1],
            }
        ],
    }
    parsed = {"forward": doc, "init_spec": spec}
    verdict = validate.validate_submission(parsed, allowlist, interface=_interface())
    return verdict, train.prepare(parsed, allowlist, verdict=verdict, kit=kit)


def test_a_registered_kit_input_is_admitted_and_never_a_constant(allowlist):
    doc = _doc(allowlist)
    verdict = validate.validate(doc, allowlist, interface=_interface())
    assert verdict["status"] == "admitted"
    assert verdict["kit"] == [["kit/table", KIT[0][3]]]
    assert verdict["measurements"]["unique_constant_bytes"] < TABLE.nbytes
    # The interface digest covers only the case boundary, not the kit.
    assert _interface().digest() == _interface(kit=()).digest()


def test_an_unregistered_or_reshaped_kit_input_is_refused(allowlist):
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(_doc(allowlist), allowlist, interface=_interface(kit=()))
    assert refused.value.code == "interface_kit_input_unexpected"
    with pytest.raises(graph.GraphRefused) as refused:
        validate.validate(
            _doc(allowlist, table_shape=(32,)), allowlist, interface=_interface()
        )
    assert refused.value.code == "interface_kit_input_shape"


def test_carbon_binds_the_kit_and_isolated_equals_batched(allowlist):
    import jax
    import jax.numpy as jnp

    doc = _doc(allowlist)
    verdict, prepared = _prepared(allowlist, doc, {"kit/table": TABLE})
    assert verdict["status"] == "admitted"
    w = prepared.init(jax.random.PRNGKey(0))
    x = jax.random.normal(jax.random.PRNGKey(1), (7, 3), jnp.float32)
    expected = np.asarray(_forward(w[0], x, TABLE))
    batched = np.asarray(prepared.predict(w, x)[0])
    isolated = np.asarray(prepared.predict(w, x, isolated=True)[0])
    np.testing.assert_allclose(batched, expected, rtol=1e-6, atol=1e-6)
    np.testing.assert_array_equal(isolated, batched)


def test_an_unbound_kit_input_is_refused(allowlist):
    with pytest.raises(graph.GraphRefused) as refused:
        _prepared(allowlist, _doc(allowlist), None)
    assert refused.value.code == "kit_input_unbound"


def test_battery_kit_digests_are_the_published_arrays_from_either_source():
    from carbon.battery import level4 as battery
    from carbon.battery import level4_model

    material = battery.material()
    host, _ = level4_model.published_kit("float32")
    structure = battery.structure(material)
    rebuilt_source = level4_model.kit_source(
        structure.ocv_soc,
        structure.ocv_v,
        level4_model.train_target_stats(material.train),
    )
    from_rebuild, arrays = level4_model.published_kit("float32", rebuilt_source)
    assert host == from_rebuild
    assert [name for name, *_ in host] == list(level4_model.KIT_INPUTS)
    train = material.train
    y = np.column_stack((train.v, train.t, train.eta, train.q))
    np.testing.assert_array_equal(
        arrays["kit/train_target_std"], y.std(axis=0).astype(np.float32)
    )
    np.testing.assert_array_equal(
        arrays["kit/ocv_v"], np.asarray(material.ocv_v, np.float32)
    )


def test_a_battery_state_carries_the_train_statistics_it_reads():
    from carbon.battery import level4 as battery
    from carbon.battery import level4_model, level4_worker
    from carbon.battery.compile import compile_recipe
    from carbon.level4 import intake, staging, submission

    strategy = battery._steps(battery.level0_strategies()["scaffold_mlp"], 16)
    _, recipe = compile_recipe(strategy)
    manifest, files = battery.lower_recipe(
        strategy, allowlist_module.load(), max_bytes=intake.BOUNDS["document_bytes"]
    )
    found = {"schema": level4_worker.SCHEMA, "submission": submission.digest(manifest)}
    workspace = staging.workspace(submission.canonical(manifest), files)
    material = battery.material()
    model = level4_worker.build_in_process(recipe, found, workspace)
    model.fit(material.train, battery.structure(material), 7)
    # A graph that reads none of the kit leaves its state as it was.
    plain = level4_model.state_bytes(model)
    assert "kit_train_target_mean" not in np.load(io.BytesIO(plain)).files
    model.kit_used = level4_model.KIT_TRAIN_STATS
    restored = level4_model.model_from_bytes(level4_model.state_bytes(model))
    for name in level4_model.KIT_TRAIN_STATS:
        np.testing.assert_array_equal(restored.kit_source[name], model.kit_source[name])
