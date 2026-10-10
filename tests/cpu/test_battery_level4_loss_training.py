"""G6: battery trains a submitted per-case loss graph (development only).

Claims tested:

1. The general-path copy (`level4_model.objective_train`) is
   `training.train` with only the loss replaced: with battery's own case
   loss as its objective it reproduces the native recipe's parameters, bit
   for bit.
2. A submitted loss graph trains under a record whose variant declares
   `loss_override: graph`, on the classic path (scaffold MLP) and the general
   path (panel DeepONet). The trained parameters equal those from training on
   the JAX function the graph was lowered from, mapped and averaged the same
   way (`loss.per_case_mean`), bit for bit.
3. The trained state is self-contained, loss graph included: it predicts
   exactly as the trained model.
4. Refusals are the candidate's:
   - a loss graph under a record with no `loss_override` (`loss_not_permitted`);
   - a loss graph beside one of battery's own loss terms (`LOSS_TERMS`).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os

import numpy as np
import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.battery import level4 as battery
from carbon.battery import level4_model, level4_worker, recipes
from carbon.battery.compile import compile_recipe
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, intake, staging, submission
from carbon.level4 import loss as loss_slot

SEED = 7
STEPS = 16


def _recipe(label):
    strategy = battery._steps(battery.level0_strategies()[label], STEPS)
    return strategy, compile_recipe(strategy)[1]


def _native(recipe, m):
    native = recipes.build(recipe.family, recipe.settings)
    stats = native.fit(m.train, battery.structure(m), SEED)
    return native, stats


def _case_loss(native):
    """Battery's own per-case loss (no case weights) as a JAX function of
    one case: `pred`, `target` and `x`, each with a leading dimension."""
    import jax.numpy as jnp

    n_out = level4_model.dims(native)[1]
    gw = jnp.asarray(native._group_weights(n_out), jnp.float32)

    def case(p, t, x):
        del x
        return jnp.sum((p - t) ** 2 * gw[None, :], axis=1)

    return case


def _with_loss(strategy, native, case, loss_override="graph"):
    import jax.numpy as jnp

    from carbon.level4.tooling import through_bprime

    allowlist = allowlist_module.load()
    manifest, files = battery.lower_recipe(
        strategy, allowlist, max_bytes=intake.BOUNDS["document_bytes"]
    )
    by_slot = {slot: files[name] for slot, name in manifest["documents"].items()}
    n_in, n_out = level4_model.dims(native)
    _, loss, _ = through_bprime(
        case,
        (jnp.ones((1, n_out)), jnp.ones((1, n_out)), jnp.ones((1, n_in))),
        role="loss",
        allowlist=allowlist,
        input_names=["loss/pred/0", "loss/target/0", "loss/x/features"],
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    built, built_files = submission.build(
        challenge=manifest["challenge"],
        interface=manifest["interface"],
        allowlist=allowlist,
        forward=json.loads(by_slot["forward"]),
        init=json.loads(by_slot["init"]),
        loss=loss,
    )
    found = {"schema": level4_worker.SCHEMA, "submission": submission.digest(built)}
    if loss_override is not None:
        found["loss_override"] = loss_override
    return found, staging.workspace(submission.canonical(built), built_files)


def _reference(model, case):
    """The same model, trained on `case` itself (jitted with the rest of
    training) in place of the rebuilt loss graph."""

    class Reference(level4_model.GraphModel):
        def _prepare(self, batch):
            prepared = super()._prepare(batch)
            return dataclasses.replace(
                prepared, loss=loss_slot.per_case_mean(lambda *a: [case(*a)])
            )

    return Reference(
        model.family,
        model.settings,
        model.files,
        model.raw_manifest,
        model.submission,
        loss_override=model.loss_override,
    )


def test_the_general_copy_is_training_train_with_only_the_loss_replaced():
    import jax
    import jax.numpy as jnp

    _, recipe = _recipe("panel_deeponet")
    assert all(recipe.settings[k] == v for k, v in level4_model.NEUTRAL.items())
    m = battery.material()
    native, stats = _native(recipe, m)
    assert not native.classic and native.settings["precision"] == "float32"
    d = recipes.train_subset(m.train, native.fraction, SEED)
    z = native._encode(native.layout.targets(d)).astype(np.float32)
    f = recipes.features(d.x, native.rich).astype(np.float32)
    gw = jnp.asarray(native._group_weights(z.shape[1]))
    init, apply = native._network(jax, np.float32, f.shape[1], z.shape[1])

    def objective(pred, target, x):
        del x
        return jnp.mean(jnp.sum((pred[0] - target[0]) ** 2 * gw[None, :], axis=1))

    params = level4_model.objective_train(
        init=init,
        apply=apply,
        f=f,
        z=z,
        settings=native.settings,
        seed=SEED,
        objective=objective,
    )
    leaves = [np.asarray(a) for a in jax.tree_util.tree_leaves(params)]
    digest = hashlib.sha256(b"".join(a.tobytes() for a in leaves)).hexdigest()
    assert digest == stats["params_sha256"]


@pytest.fixture(scope="module", params=["scaffold_mlp", "panel_deeponet"])
def trained(request):
    strategy, recipe = _recipe(request.param)
    m = battery.material()
    native, _ = _native(recipe, m)
    case = _case_loss(native)
    found, workspace = _with_loss(strategy, native, case)
    model = level4_worker.build_in_process(recipe, found, workspace)
    stats = model.fit(m.train, battery.structure(m), SEED)
    reference = _reference(model, case)
    reference_stats = reference.fit(m.train, battery.structure(m), SEED)
    return request.param, model, stats, reference_stats, m


def test_a_loss_graph_trains_as_the_function_it_was_lowered_from(trained):
    label, model, stats, reference_stats, _m = trained
    assert model.prepared.loss is not None
    assert model.classic == (label == "scaffold_mlp")
    assert stats["params_sha256"] == reference_stats["params_sha256"], label
    assert np.isfinite(stats["final_loss"])


def test_a_loss_graph_state_is_self_contained(trained):
    _label, model, _stats, _reference_stats, m = trained
    restored = level4_model.model_from_bytes(level4_model.state_bytes(model))
    assert restored.loss_override == "graph"
    assert restored.prepared.loss is not None
    out, again = model.predict(m.train.x), restored.predict(m.train.x)
    for key in out:
        assert np.array_equal(np.asarray(out[key]), np.asarray(again[key])), key


def test_a_loss_graph_without_the_variants_declaration_is_refused():
    strategy, recipe = _recipe("scaffold_mlp")
    m = battery.material()
    native, _ = _native(recipe, m)
    found, workspace = _with_loss(strategy, native, _case_loss(native), None)
    model = level4_worker.build_in_process(recipe, found, workspace)
    with pytest.raises(graph.GraphRefused) as refused:
        model.fit(m.train, battery.structure(m), SEED)
    assert refused.value.code == "loss_not_permitted"


def test_a_loss_graph_beside_batterys_own_loss_terms_is_refused():
    strategy, recipe = _recipe("scaffold_mlp")
    m = battery.material()
    native, _ = _native(recipe, m)
    found, workspace = _with_loss(strategy, native, _case_loss(native))
    weighted = {
        "family": recipe.family,
        "settings": {**recipe.settings, "important_region_weight": 2.0},
    }
    model = level4_worker.build_in_process(weighted, found, workspace)
    with pytest.raises(graph.GraphRefused) as refused:
        model.fit(m.train, battery.structure(m), SEED)
    assert refused.value.code == level4_model.LOSS_TERMS
    assert model.prepared is None
