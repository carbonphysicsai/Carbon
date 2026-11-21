"""The self-trust ensemble state (carbon/development_session/physical_graph_state_v3.py, SELF_TRUST H3d-2a): graph output
W + k wide, decoder and combination W wide, the trust block named in the header under its own schema, so no older loader
reads these bytes and this loader reads no older state.
"""

from __future__ import annotations

import io
import json

import numpy as np
import pytest

pytest.importorskip("jax")

from carbon.development_session import (
    graph_state_contract,
)
from carbon.development_session import (
    physical_graph_state_v2 as state_v2,
)
from carbon.development_session import (
    physical_graph_state_v3 as state_v3,
)
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.level4 import allowlist
from carbon.level4.tooling import lower_jax

W, K, B = 3, 3, 4


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
            "source": {"kind": "graph", "submission_digest": _sha("e")},
            "procedure": {
                "entrypoint": None,
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


def _trust_doc(permitted):
    """A forward graph `(p0, p1, x) -> concatenate([x * p0, x * p1])`: W + K = 6 output columns."""
    import jax.numpy as jnp

    traced = lower_jax.trace(
        lambda p0, p1, x: jnp.concatenate([x * p0, x * p1], axis=-1),
        jnp.ones((W,), dtype=jnp.float32),
        jnp.ones((K,), dtype=jnp.float32),
        jnp.ones((B, W), dtype=jnp.float32),
    )
    return lower_jax.lower(
        traced,
        role="forward",
        allowlist=permitted,
        input_names=["params/0", "params/1", "inputs/x"],
    )


def _plain_doc(permitted):
    """The same kind of graph without a trust block: output W wide."""
    import jax.numpy as jnp

    traced = lower_jax.trace(
        lambda p0, x: x * p0,
        jnp.ones((W,), dtype=jnp.float32),
        jnp.ones((B, W), dtype=jnp.float32),
    )
    return lower_jax.lower(
        traced,
        role="forward",
        allowlist=permitted,
        input_names=["params/0", "inputs/x"],
    )


def _decoder(width=W):
    return np.zeros(width, dtype=np.float32), np.ones(width, dtype=np.float32)


def _combine(width=W, members=1):
    return np.full((members, width), 1.0 / members, dtype=np.float32)


def _members():
    return [
        [np.full((W,), 2.0, dtype=np.float32), np.full((K,), 3.0, dtype=np.float32)]
    ]


def _freeze(permitted, **override):
    mu, sd = _decoder()
    arguments = {
        "recipe": _recipe(),
        "doc": _trust_doc(permitted),
        "members": _members(),
        "allowlist": permitted,
        "mu": mu,
        "sd": sd,
        "combine": _combine(),
        "trust_width": K,
    }
    arguments.update(override)
    return state_v3.freeze(**arguments)


def _header(raw):
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        return json.loads(archive["__header__"].tobytes())


def _rewritten(raw, **changes):
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    header = json.loads(arrays["__header__"].tobytes())
    for key, value in changes.items():
        header[key] = value
    arrays["__header__"] = np.frombuffer(
        json.dumps(header, sort_keys=True, separators=(",", ":")).encode(),
        dtype=np.uint8,
    )
    out = io.BytesIO()
    np.savez(out, **arrays)
    return out.getvalue()


def test_the_trust_schema_is_registered_and_distinct_from_the_ensemble_schema():
    assert (
        state_v3.TRUST_STATE_SCHEMA
        == graph_state_contract.GRAPH_ENSEMBLE_TRUST_STATE_SCHEMA
    )
    assert (
        state_v3.TRUST_STATE_SCHEMA in graph_state_contract.GRAPH_SOURCE_STATE_SCHEMAS
    )
    assert state_v3.TRUST_STATE_SCHEMA != state_v2.ENSEMBLE_SCHEMA


def test_a_trust_state_round_trips_with_a_w_wide_decoder_and_combination():
    permitted = allowlist.load()
    raw = _freeze(permitted)
    doc, members, mu, sd, combine = state_v3.load(raw, _recipe(), permitted)
    assert doc == _trust_doc(permitted)
    assert len(members) == 1 and len(members[0]) == 2
    np.testing.assert_array_equal(members[0][0], np.full((W,), 2.0))
    np.testing.assert_array_equal(members[0][1], np.full((K,), 3.0))
    assert mu.shape == sd.shape == (W,) and combine.shape == (1, W)
    assert state_v3.validate(raw, _recipe(), permitted) is None


def test_the_header_names_the_trust_block_and_the_physics_decoder_width():
    header = _header(_freeze(allowlist.load()))
    assert header["schema"] == state_v3.TRUST_STATE_SCHEMA
    assert header["trust"] == {"member": 0, "width": K}
    assert header["decoder"]["width"] == W  # the physics columns, not W + k


def test_no_older_loader_reads_a_trust_state_and_this_one_reads_no_older_state():
    permitted = allowlist.load()
    trust_bytes = _freeze(permitted)
    with pytest.raises(RecipeRefused, match="header_invalid"):
        state_v2.load(trust_bytes, _recipe(), permitted)
    mu, sd = _decoder()
    plain = state_v2.freeze(
        _recipe(),
        _plain_doc(permitted),
        [[np.full((W,), 2.0, dtype=np.float32)]],
        permitted,
        mu,
        sd,
        _combine(),
    )
    with pytest.raises(RecipeRefused, match="header_invalid"):
        state_v3.load(plain, _recipe(), permitted)


@pytest.mark.parametrize("trust_width", [0, -1, True, 1.5, W + K, W + K + 1])
def test_a_bad_trust_width_is_refused_at_freeze(trust_width):
    # 0 / negative / bool / float are not widths; W + K and more leave no physics column (the graph is W + K wide)
    with pytest.raises(
        RecipeRefused, match="trust_graph_state_width_invalid|decoder_invalid"
    ):
        _freeze(allowlist.load(), trust_width=trust_width)


def test_a_decoder_or_combination_as_wide_as_the_graph_is_refused():
    permitted = allowlist.load()
    mu, sd = _decoder(W + K)
    with pytest.raises(RecipeRefused, match="decoder_invalid"):
        _freeze(permitted, mu=mu, sd=sd)
    with pytest.raises(RecipeRefused, match="combine_invalid"):
        _freeze(permitted, combine=_combine(W + K))


def test_a_tampered_trust_block_in_the_header_is_refused():
    permitted = allowlist.load()
    raw = _freeze(permitted)
    for bad in (
        {"member": 1, "width": K},  # not the trust member
        {"member": 0, "width": K + 1},  # another width: the decoder no longer matches
        {"member": 0, "width": 0},
        {"member": 0},
        None,
    ):
        with pytest.raises(
            RecipeRefused, match="header_invalid|decoder_invalid|width_invalid"
        ):
            state_v3.load(_rewritten(raw, trust=bad), _recipe(), permitted)
    with pytest.raises(RecipeRefused, match="header_invalid"):
        state_v3.load(
            _rewritten(raw, schema=state_v2.ENSEMBLE_SCHEMA), _recipe(), permitted
        )


def test_a_state_bound_to_another_recipe_is_refused():
    permitted = allowlist.load()
    raw = _freeze(permitted)
    other = _recipe().to_dict()
    other["source"]["submission_digest"] = _sha("f")
    with pytest.raises(RecipeRefused, match="header_invalid"):
        state_v3.load(raw, ConstructionRecipe.from_dict(other), permitted)


def test_a_json_alias_in_the_header_is_refused_because_the_header_bytes_are_compared():
    # door-code 09:10:09Z: {"member": false} == {"member": 0} and a width written 3.0 == 3 as parsed dicts; as bytes they differ.
    permitted = allowlist.load()
    raw = _freeze(permitted)
    header = _header(raw)
    with pytest.raises(RecipeRefused, match="header_invalid"):
        state_v3.load(
            _rewritten(raw, trust={"member": False, "width": K}), _recipe(), permitted
        )
    with pytest.raises(RecipeRefused, match="header_invalid"):
        state_v3.load(
            _rewritten(raw, decoder={**header["decoder"], "width": float(W)}),
            _recipe(),
            permitted,
        )
    with pytest.raises(RecipeRefused, match="header_invalid"):
        state_v3.load(
            _rewritten(raw, trust={"member": 0, "width": float(K)}),
            _recipe(),
            permitted,
        )
    # the unchanged header, re-serialised the same way, still loads
    assert state_v3.load(_rewritten(raw), _recipe(), permitted) is not None
