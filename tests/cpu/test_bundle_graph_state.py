"""Frozen bundle inference contains only a bounded graph and numeric arrays."""

import io
from pathlib import Path

import numpy as np
import pytest

from carbon.development_session import bundle_graph_state
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.level4 import allowlist, interpret
from carbon.level4.tooling import lower_jax


def _sha(char):
    return "sha256:" + char * 64


def _recipe():
    return ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": {
                "id": "public-field-fixture",
                "version": "development-v1",
                "train_digest": _sha("a"),
                "interface_digest": _sha("b"),
                "construction_limits_digest": _sha("c"),
            },
            "source": {
                "kind": "bundle",
                "bundle_ref": {
                    "schema": "carbon.library-bundle-ref.v1",
                    "bundle_digest": _sha("d"),
                    "language": "python",
                    "runtime_profile_id": "jax-cuda13-py311",
                    "environment_digest": _sha("e"),
                },
            },
            "procedure": {
                "entrypoint": {"module": "candidate.build", "name": "build"},
                "configuration": {},
                "train_use": {},
                "initial_state": None,
            },
            "output": {
                "format": "carbon.numeric-graph.v1",
                "interface_digest": _sha("b"),
            },
        }
    )


def test_bundle_state_reopens_numeric_parameters_in_inert_graph():
    import jax.numpy as jnp

    recipe, permitted = _recipe(), allowlist.load()
    traced = lower_jax.trace(
        lambda p, x: p * x,
        jnp.asarray([2.0, 3.0], dtype=jnp.float32),
        jnp.asarray([4.0, 5.0], dtype=jnp.float32),
    )
    doc = lower_jax.lower(
        traced,
        role="forward",
        allowlist=permitted,
        input_names=["params/0", "inputs/x"],
    )
    state = bundle_graph_state.freeze(
        recipe, doc, [np.asarray([2.0, 3.0], dtype=np.float32)], permitted
    )
    loaded, parameters = bundle_graph_state.load(state, recipe, permitted)
    assert loaded == doc
    assert len(parameters) == 1
    result = interpret.rebuild(loaded, permitted)(
        jnp.asarray(parameters[0]), jnp.asarray([4.0, 5.0], dtype=jnp.float32)
    )
    np.testing.assert_array_equal(np.asarray(result[0]), [8.0, 15.0])
    assert b"pickle" not in state


def test_bundle_state_rejects_recipe_and_parameter_tampering():
    import jax.numpy as jnp

    recipe, permitted = _recipe(), allowlist.load()
    traced = lower_jax.trace(
        lambda p, x: p * x,
        jnp.ones((2,), dtype=jnp.float32),
        jnp.ones((2,), dtype=jnp.float32),
    )
    doc = lower_jax.lower(
        traced,
        role="forward",
        allowlist=permitted,
        input_names=["params/0", "inputs/x"],
    )
    with pytest.raises(RecipeRefused, match="parameter_invalid"):
        bundle_graph_state.freeze(
            recipe,
            doc,
            [np.asarray([float("nan"), 1.0], dtype=np.float32)],
            permitted,
        )
    state = bundle_graph_state.freeze(
        recipe, doc, [np.ones((2,), dtype=np.float32)], permitted
    )
    changed = recipe.to_dict()
    changed["source"]["bundle_ref"]["bundle_digest"] = _sha("f")
    with pytest.raises(RecipeRefused, match="header_invalid"):
        bundle_graph_state.load(state, ConstructionRecipe.from_dict(changed), permitted)
    with np.load(io.BytesIO(state), allow_pickle=False) as original:
        arrays = {name: original[name] for name in original.files}
    arrays["parameter0000"] = np.ones((3,), dtype=np.float32)
    out = io.BytesIO()
    np.savez(out, **arrays)
    with pytest.raises(RecipeRefused, match="parameter_invalid"):
        bundle_graph_state.load(out.getvalue(), recipe, permitted)


def test_graph_source_state_binds_submission_without_changing_bundle_v1():
    import jax.numpy as jnp

    permitted = allowlist.load()
    traced = lower_jax.trace(
        lambda p, x: p * x,
        jnp.asarray([2.0, 3.0], dtype=jnp.float32),
        jnp.asarray([4.0, 5.0], dtype=jnp.float32),
    )
    doc = lower_jax.lower(
        traced,
        role="forward",
        allowlist=permitted,
        input_names=["params/0", "inputs/x"],
    )
    graph_recipe_document = _recipe().to_dict()
    graph_recipe_document["source"] = {
        "kind": "graph",
        "submission_digest": _sha("e"),
    }
    graph_recipe_document["procedure"]["entrypoint"] = None
    recipe = ConstructionRecipe.from_dict(graph_recipe_document)
    state = bundle_graph_state.freeze(
        recipe, doc, [np.asarray([2.0, 3.0], dtype=np.float32)], permitted
    )
    with np.load(io.BytesIO(state), allow_pickle=False) as archived:
        import json

        header = json.loads(archived["__header__"].tobytes())
    assert header["schema"] == bundle_graph_state.GRAPH_SCHEMA
    assert header["submission_digest"] == _sha("e")
    assert "bundle_digest" not in header
    loaded, parameters = bundle_graph_state.load(state, recipe, permitted)
    assert loaded == doc
    np.testing.assert_array_equal(parameters[0], [2.0, 3.0])
    changed = graph_recipe_document.copy()
    changed["source"] = {"kind": "graph", "submission_digest": _sha("f")}
    with pytest.raises(RecipeRefused, match="header_invalid"):
        bundle_graph_state.load(state, ConstructionRecipe.from_dict(changed), permitted)
    with pytest.raises(RecipeRefused, match="header_invalid"):
        bundle_graph_state.load(state, _recipe(), permitted)


def test_prospective_fno_spectral_graph_freezes_real_weights_and_reopens():
    import jax.numpy as jnp

    def spectral(wr, wi, x):
        ft = jnp.fft.rfft2(x, s=(15, 15), axes=(0, 1), norm="ortho")
        upper = ft[:2, :2, :] * (wr + 1j * wi)
        out = jnp.zeros((15, 8, 1), dtype=jnp.complex64)
        out = out.at[:2, :2, :].set(upper)
        return jnp.fft.irfft2(out, s=(15, 15), axes=(0, 1), norm="ortho")[:8, :8, :]

    permitted = allowlist.load(Path(allowlist.PATH).with_name("allowlist_v2.json"))
    weights = [jnp.full((2, 2, 1), value, dtype=jnp.float32) for value in (0.4, -0.2)]
    x = jnp.arange(64, dtype=jnp.float32).reshape(8, 8, 1) / 64
    doc = lower_jax.lower(
        lower_jax.trace(spectral, *weights, x),
        role="forward",
        allowlist=permitted,
        input_names=["params/0", "params/1", "inputs/x"],
    )
    recipe = _recipe()
    state = bundle_graph_state.freeze(
        recipe, doc, [np.asarray(w) for w in weights], permitted
    )
    loaded, parameters = bundle_graph_state.load(state, recipe, permitted)
    actual = interpret.rebuild(loaded, permitted)(
        *(jnp.asarray(p) for p in parameters), x
    )[0]
    np.testing.assert_array_equal(np.asarray(actual), np.asarray(spectral(*weights, x)))
