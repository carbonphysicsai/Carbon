"""At Level 4 the submitted graph is the network; the recipe's width and depth are not.

The Level 4 starter's spec builds a width-32 network while its recipe says width 64, and
two fresh agents (2026-10-13) assumed the two are independent. This pins it: one staged
graph, trained under recipes that differ only in width and depth, gives bit-identical
parameters, and the trained network has the graph's shapes, not the recipe's. A recipe
setting that does reach training (here steps) still changes the result, so the test
can tell "ignored" from "never read".
"""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.battery import level4 as battery
from carbon.battery import level4_worker
from carbon.battery.compile import compile_recipe
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import intake, staging, submission

SEED = 7
STEPS = 16


def _staged(strategy):
    manifest, files = battery.lower_recipe(
        strategy, allowlist_module.load(), max_bytes=intake.BOUNDS["document_bytes"]
    )
    raw = submission.canonical(manifest)
    found = {"schema": level4_worker.SCHEMA, "submission": submission.digest(manifest)}
    return found, staging.workspace(raw, files)


def _with(strategy, **parameters):
    changed = json.loads(json.dumps(strategy))
    changed["parameters"].update(parameters)
    return changed


def _without(strategy, *names):
    changed = json.loads(json.dumps(strategy))
    for name in names:
        del changed["parameters"][name]
    return changed


def _fit(strategy, found, workspace):
    _, recipe = compile_recipe(strategy)
    model = level4_worker.build_in_process(recipe, found, workspace)
    m = battery.material()
    stats = model.fit(m.train, battery.structure(m), SEED)
    return recipe, model, stats


@pytest.fixture(scope="module")
def trained():
    base = battery._steps(battery.level0_strategies()["scaffold_mlp"], STEPS)
    found, workspace = _staged(base)  # the graph is lowered once, from the base recipe
    width = base["parameters"]["width"]
    depth = base["parameters"]["depth"]
    other = _with(base, width=width * 2, depth=depth + 1)
    return {
        "base": _fit(base, found, workspace),
        "other": _fit(other, found, workspace),
        "steps": _fit(_with(base, steps=STEPS * 2), found, workspace),
        "omitted": _fit(_without(base, "width", "depth"), found, workspace),
        "width": width,
        "depth": depth,
    }


def test_the_recipes_width_and_depth_do_not_shape_the_trained_graph(trained):
    (r0, m0, s0), (r1, m1, s1) = trained["base"], trained["other"]
    assert r0.settings["width"] != r1.settings["width"]
    assert r0.settings["depth"] != r1.settings["depth"]
    assert s0["params_sha256"] == s1["params_sha256"]
    shapes0 = [tuple(getattr(p, "shape", ())) for p in _leaves(m0.params)]
    shapes1 = [tuple(getattr(p, "shape", ())) for p in _leaves(m1.params)]
    assert shapes0 == shapes1
    # The network is the graph's: no parameter has the recipe's doubled width.
    assert all(trained["width"] * 2 not in shape for shape in shapes1)


def test_a_setting_training_does_read_still_changes_the_result(trained):
    assert trained["steps"][2]["params_sha256"] != trained["base"][2]["params_sha256"]


def _leaves(tree):
    import jax

    return jax.tree_util.tree_leaves(tree)


def test_a_recipe_without_width_and_depth_trains_the_same_graph(trained):
    """Omitting them is safe on battery-l4-graph-v3: the compiler fills the
    catalog's defaults before battery's MLP reads `settings["width"]`, and the
    graph is still the network."""
    recipe, _model, stats = trained["omitted"]
    assert "width" in recipe.settings and "depth" in recipe.settings
    assert stats["params_sha256"] == trained["base"][2]["params_sha256"]
