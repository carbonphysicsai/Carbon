"""Battery's Level 4 rebuild from staged documents (Phase 3; development only).

Claims tested:

1. A rebuild staged with a submission's workspace (`staging.workspace`)
   trains the graph through battery's own loop to the native recipe's
   parameters, bit for bit: the classic path (scaffold MLP) and the general
   path (panel DeepONet). This is E1, through the worker's in-process build.
2. The trained state is self-contained: `state_bytes`, then
   `model_from_bytes`, predicts exactly as the trained model, with nothing
   staged; on the general path that equals the native recipe's predictions.
3. It fails closed as Carbon's environment, never the candidate's, when:
   - no workspace was staged (`BLOCKED`);
   - the workspace is not the record's submission (`level4_staging_corrupt`);
   - the submission carries a loss graph, whose training is not built yet;
   - the family is the nearest-neighbour recipe, which has no network.
4. A state whose manifest is not its recorded submission is refused.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.battery import level4 as battery
from carbon.battery import level4_model, level4_worker, recipes
from carbon.battery.compile import compile_recipe
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import intake, staging, submission

SEED = 7
STEPS = 16


def _staged(strategy):
    allowlist = allowlist_module.load()
    manifest, files = battery.lower_recipe(
        strategy, allowlist, max_bytes=intake.BOUNDS["document_bytes"]
    )
    raw = submission.canonical(manifest)
    found = {"schema": level4_worker.SCHEMA, "submission": submission.digest(manifest)}
    return found, staging.workspace(raw, files)


@pytest.fixture(scope="module", params=["scaffold_mlp", "panel_deeponet"])
def rebuilt(request):
    strategy = battery._steps(battery.level0_strategies()[request.param], STEPS)
    _, recipe = compile_recipe(strategy)
    found, workspace = _staged(strategy)
    m = battery.material()
    model = level4_worker.build_in_process(recipe, found, workspace)
    stats = model.fit(m.train, battery.structure(m), SEED)
    native = recipes.build(recipe.family, recipe.settings)
    native_stats = native.fit(m.train, battery.structure(m), SEED)
    return request.param, model, stats, native, native_stats, m


def test_the_staged_graph_trains_to_the_native_parameters(rebuilt):
    label, model, stats, _native, native_stats, _m = rebuilt
    assert isinstance(model, level4_model.GraphModel)
    assert stats["params_sha256"] == native_stats["params_sha256"], label
    assert model.classic == (label == "scaffold_mlp")


def test_the_state_is_self_contained(rebuilt):
    _label, model, _stats, native, _native_stats, m = rebuilt
    out = model.predict(m.train.x)
    restored = recipes.model_from_bytes(recipes.state_bytes(model))
    assert isinstance(restored, level4_model.GraphModel)
    again = restored.predict(m.train.x)
    assert sorted(again) == sorted(out)
    for key in out:
        assert np.array_equal(np.asarray(out[key]), np.asarray(again[key])), key
    if not model.classic:
        reference = native.predict(m.train.x)
        for key in out:
            assert np.array_equal(np.asarray(out[key]), np.asarray(reference[key]))


def test_every_missing_or_wrong_input_is_carbons(rebuilt):
    strategy = battery._steps(battery.level0_strategies()["scaffold_mlp"], STEPS)
    _, recipe = compile_recipe(strategy)
    found, workspace = _staged(strategy)
    with pytest.raises(ImportError, match=level4_worker.BLOCKED):
        level4_worker.build_in_process(recipe, found)
    wrong = dict(found, submission="sha256:" + "0" * 64)
    with pytest.raises(ImportError, match="level4_staging_corrupt"):
        level4_worker.build_in_process(recipe, wrong, workspace)
    knn = compile_recipe(battery.level0_strategies()["panel_knn"])[1]
    with pytest.raises(ImportError, match="level4_family_not_served"):
        level4_worker.build_in_process(knn, found, workspace)


def test_a_loss_graph_is_not_trained_yet():
    import jax.numpy as jnp

    from carbon.level4.tooling import through_bprime

    strategy = battery._steps(battery.level0_strategies()["scaffold_mlp"], STEPS)
    _, recipe = compile_recipe(strategy)
    allowlist = allowlist_module.load()
    manifest, files = battery.lower_recipe(
        strategy, allowlist, max_bytes=intake.BOUNDS["document_bytes"]
    )
    by_slot = {slot: files[name] for slot, name in manifest["documents"].items()}
    _, loss, _ = through_bprime(
        lambda p, t: jnp.sum((p - t) ** 2, axis=1),
        (jnp.ones((1, 2)), jnp.ones((1, 2))),
        role="loss",
        allowlist=allowlist,
        input_names=["loss/pred/0", "loss/target/0"],
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    import json

    with_loss, loss_files = submission.build(
        challenge=manifest["challenge"],
        interface=manifest["interface"],
        allowlist=allowlist,
        forward=json.loads(by_slot["forward"]),
        init=json.loads(by_slot["init"]),
        loss=loss,
    )
    found = {"schema": level4_worker.SCHEMA, "submission": submission.digest(with_loss)}
    model = level4_worker.build_in_process(
        recipe, found, staging.workspace(submission.canonical(with_loss), loss_files)
    )
    m = battery.material()
    with pytest.raises(ImportError, match=level4_model.LOSS_NOT_BUILT):
        model.fit(m.train, battery.structure(m), SEED)


def test_a_state_whose_manifest_is_not_its_submission_is_refused(rebuilt):
    _label, model, *_ = rebuilt
    header, arrays = recipes.export_state(model)
    header = dict(header, submission="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="not its manifest"):
        recipes.import_state(header, arrays)


def test_the_stageable_module_names_batterys_challenge():
    assert level4_model.CHALLENGE == battery.challenge_id()
    assert battery.classic_fit is level4_model.classic_fit
