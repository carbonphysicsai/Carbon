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
   - the family is the nearest-neighbour recipe, which has no network.
4. A state whose manifest is not its recorded submission is refused.

Training on a submitted loss graph (G6) is
`tests/cpu/test_battery_level4_loss_training.py`.
"""

from __future__ import annotations

import os
from pathlib import Path

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
    state = level4_model.state_bytes(model)
    restored = level4_model.model_from_bytes(state)
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


def test_an_unset_owner_cap_blocks_as_carbons(monkeypatch):
    strategy = battery._steps(battery.level0_strategies()["scaffold_mlp"], STEPS)
    _, recipe = compile_recipe(strategy)
    found, workspace = _staged(strategy)
    model = level4_worker.build_in_process(recipe, found, workspace)
    caps = {**allowlist_module.CAPS, "nodes_executed": allowlist_module.HUMAN_INPUT}
    monkeypatch.setattr(allowlist_module, "CAPS", caps)
    m = battery.material()
    with pytest.raises(ImportError, match=level4_model.CAPS_UNSET):
        model.fit(m.train, battery.structure(m), SEED)
    assert model.prepared is None


def test_a_state_whose_manifest_is_not_its_submission_is_refused(rebuilt):
    _label, model, *_ = rebuilt
    header, arrays = model.export_state()
    header = dict(header, submission="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="not its manifest"):
        level4_model.import_state(header, arrays, model.layout, model.s)


def test_battery_implementation_modules_are_untouched_by_level4(rebuilt):
    """A graph model's state is `level4_model`'s: `recipes` never reads or
    writes one, so battery's implementation digest (every recipe digest) is
    unchanged by Level 4."""
    import io
    import json

    from carbon.battery import implementation_versions

    _label, model, *_ = rebuilt
    for name in implementation_versions.MODULES:
        body = Path(recipes.__file__).with_name(name).read_text(encoding="utf-8")
        assert "level4" not in body, name
    state = level4_model.state_bytes(model)
    with pytest.raises(ValueError, match="unknown model state kind"):
        recipes.model_from_bytes(state)
    with np.load(io.BytesIO(state), allow_pickle=False) as data:
        arrays = {k: data[k] for k in data.files if k != "__header__"}
        header = json.loads(bytes(data["__header__"]).decode())
    buffer = io.BytesIO()
    np.savez(
        buffer,
        __header__=np.frombuffer(
            json.dumps({**header, "kind": "mlp"}).encode(), np.uint8
        ),
        **arrays,
    )
    with pytest.raises(ValueError, match="not a Level 4"):
        level4_model.model_from_bytes(buffer.getvalue())


def test_the_stageable_module_names_batterys_challenge():
    assert level4_model.CHALLENGE == battery.challenge_id()
    assert battery.classic_fit is level4_model.classic_fit
