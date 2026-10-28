"""Custody consumes real inert codec output, without training or qualification.

All parameters, decoders and fit declarations below are synthetic. The graph
and source envelope use the maintained public graph fixture; the actual
registered freeze functions produce every state header and member layout.
"""

from __future__ import annotations

import io
import json

import numpy as np
import pytest
from test_graph_route_v2 import F08, MOTOR, _case, _x64
from test_public_bundle_model_custody import _json, _sha

from carbon.challenge_kit import physical_material
from carbon.development_session import (
    bundle_graph_state,
    physical_graph_state,
    physical_graph_state_v2,
)
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, staging
from scripts.dev.score_lab import public_unbound_custody as custody


def producer_fixture(kind="ensemble", key=(F08, "1.6")):
    """Freeze synthetic values with the actual registered producer codec."""
    material = physical_material.bundle_material(*key)
    with _x64(key):
        recipe, manifest_raw, documents, _staging = _case(
            key, {"training": {"steps": 1}}
        )
    manifest = json.loads(manifest_raw)
    forward = graph.parse(documents[manifest["documents"]["forward"]])
    inputs = forward["graphs"][forward["entry"]]["inputs"]
    parameters = [
        np.zeros(entry["shape"], dtype=entry["dtype"])
        for entry in inputs
        if entry["name"].startswith("params/")
    ]
    permitted = allowlist_module.Allowlist(material["allowlist_bytes"])
    width = physical_graph_state._width(forward)
    dtype = parameters[0].dtype
    mu, sd = np.zeros(width, dtype), np.ones(width, dtype)
    if kind == "plain":
        state = bundle_graph_state.freeze(recipe, forward, parameters, permitted)
    elif kind == "decoded":
        state = physical_graph_state.freeze(
            recipe, forward, parameters, permitted, mu, sd
        )
    else:
        assert kind == "ensemble"
        state = physical_graph_state_v2.freeze(
            recipe,
            forward,
            [parameters, parameters],
            permitted,
            mu,
            sd,
            np.full((2, width), 0.5, dtype),
        )
    fit = {
        "adapter_id": "synthetic-codec-fixture",
        "trainer_sha256": _sha(b"synthetic-trainer-declaration"),
        "members": 2,
        "steps": [1, 1],
        "train_cases": 1,
        "train_loss": 0.0,
        "member_losses": [0.0, 0.0],
        "params_sha256": _sha(b"synthetic-parameter-declaration"),
        "recipe_digest": recipe.digest,
    }
    if kind != "ensemble":
        del fit["members"], fit["member_losses"]
        fit["steps"] = 1
    return {
        "material": material,
        "recipe": recipe,
        "source": staging.envelope(manifest_raw, documents),
        "state": state,
        "fit": fit,
    }


def _inspect(fixture, state=None, **kwargs):
    return custody._bundle_header(
        fixture["state"] if state is None else state,
        graph_source=True,
        recipe=fixture["recipe"].canonical_bytes,
        allowlist=fixture["material"]["allowlist_bytes"],
        **kwargs,
    )


def _rewrite(raw, change):
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in archive.files}
    change(arrays)
    out = io.BytesIO()
    np.savez(out, **arrays)
    return out.getvalue()


@pytest.fixture(scope="module")
def ensemble():
    return producer_fixture()


@pytest.mark.parametrize("kind", ["plain", "decoded", "ensemble"])
def test_actual_freeze_formats_retain_exact_originals(kind):
    fixture = producer_fixture(kind)
    before = fixture["state"]
    header, arrays = _inspect(fixture)
    expected = (
        physical_graph_state_v2.ENSEMBLE_SCHEMA
        if kind == "ensemble"
        else bundle_graph_state.GRAPH_SCHEMA
    )
    assert header["schema"] == expected
    assert header["recipe_digest"] == fixture["recipe"].digest
    assert header["submission_digest"] == fixture["source"]["submission"]
    assert fixture["state"] == before
    assert ("decoder_mu" in arrays) == (kind != "plain")
    assert ("combine" in arrays) == (kind == "ensemble")
    assert (
        custody.graph_state_schema(
            before,
            fixture["recipe"].canonical_bytes,
            fixture["material"]["allowlist_bytes"],
        )
        == expected
    )


def test_actual_float64_ensemble_and_native_allowlist_resolution():
    fixture = producer_fixture(key=(MOTOR, "1.5"))
    header, arrays = custody._bundle_header(
        fixture["state"],
        graph_source=True,
        recipe=fixture["recipe"].canonical_bytes,
    )
    assert header["decoder"]["width"] == 60
    assert arrays["decoder_sd"]["dtype"] == "float64"


@pytest.mark.parametrize(
    "mutation",
    [
        "zero_sd",
        "nonfinite_mu",
        "bad_combine_sum",
        "negative_combine",
        "nonfinite_parameter",
        "wrong_parameter_shape",
        "missing_member",
        "extra_member",
        "wrong_decoder_dtype",
        "wrong_header_identity",
        "wrong_decoder_width",
        "extra_header_field",
        "huge_empty_ensemble",
    ],
)
def test_malformed_actual_ensemble_output_refuses(ensemble, mutation):
    def change(arrays):
        parameter = "member000000_parameter0000"
        if mutation == "zero_sd":
            arrays["decoder_sd"][0] = 0
        elif mutation == "nonfinite_mu":
            arrays["decoder_mu"][0] = np.nan
        elif mutation == "bad_combine_sum":
            arrays["combine"][:, 0] = 0
        elif mutation == "negative_combine":
            arrays["combine"][:, 0] = [-0.5, 1.5]
        elif mutation == "nonfinite_parameter":
            arrays[parameter].flat[0] = np.inf
        elif mutation == "wrong_parameter_shape":
            arrays[parameter] = arrays[parameter].reshape(-1)
        elif mutation == "missing_member":
            del arrays[parameter]
        elif mutation == "extra_member":
            arrays["member000002_parameter0000"] = arrays[parameter]
        elif mutation == "wrong_decoder_dtype":
            arrays["decoder_sd"] = arrays["decoder_sd"].astype(np.float64)
        else:
            header = json.loads(arrays["__header__"].tobytes())
            if mutation == "wrong_header_identity":
                header["recipe_digest"] = _sha(b"different recipe")
            elif mutation == "wrong_decoder_width":
                header["decoder"]["width"] += 1
            elif mutation == "extra_header_field":
                header["accepted"] = True
            else:
                header["members"], header["parameter_count"] = 10**100, 0
            arrays["__header__"] = np.frombuffer(_json(header), dtype=np.uint8)

    with pytest.raises(custody.CustodyRefused):
        _inspect(ensemble, _rewrite(ensemble["state"], change))


def test_decoder_needs_bound_recipe_and_allowlist_and_old_bundle_cannot_read_it(
    ensemble,
):
    with pytest.raises(custody.CustodyRefused, match="graph_state_codec"):
        custody._bundle_header(ensemble["state"], graph_source=True)
    with pytest.raises(custody.CustodyRefused, match="bundle_state_header"):
        custody._bundle_header(ensemble["state"])


def test_zero_parameter_validation_has_no_member_list_allocation(ensemble, monkeypatch):
    recipe = ensemble["recipe"]
    permitted = allowlist_module.Allowlist(ensemble["material"]["allowlist_bytes"])
    forward = {
        "schema": graph.SCHEMA,
        "allowlist": permitted.version,
        "role": "forward",
        "entry": "main",
        "graphs": {
            "main": {
                "inputs": [
                    {
                        "value": 0,
                        "name": "inputs/x",
                        "dtype": "float32",
                        "shape": [1, 7],
                    }
                ],
                "constants": [],
                "nodes": [],
                "outputs": [0],
            }
        },
    }
    members = 5000  # synthetic resource regression, not a model policy
    combine = np.zeros((members, 7), np.float32)
    combine[0] = 1
    state = physical_graph_state_v2.freeze(
        recipe,
        forward,
        [[]] * members,
        permitted,
        np.zeros(7, np.float32),
        np.ones(7, np.float32),
        combine,
    )
    loaded = physical_graph_state_v2.load(state, recipe, permitted)
    assert len(loaded[1]) == members and all(value == [] for value in loaded[1])

    def unexpected_parameter_materialization(*_args):
        raise AssertionError("zero-parameter custody must not allocate per member")

    monkeypatch.setattr(
        physical_graph_state_v2,
        "_checked_parameters",
        unexpected_parameter_materialization,
    )
    header, arrays = _inspect(ensemble, state)
    assert header["members"] == members
    assert header["parameter_count"] == 0
    assert len(arrays) == 5
    _digest, manifest_raw, documents = staging.from_envelope(ensemble["source"])
    with pytest.raises(custody.CustodyRefused, match="graph_source_forward"):
        custody._graph_state_source_binding(header, manifest_raw, documents)

    def inconsistent_claim(arrays):
        header = json.loads(arrays["__header__"].tobytes())
        header["members"] = 10**100
        arrays["__header__"] = np.frombuffer(_json(header), dtype=np.uint8)

    with pytest.raises(custody.CustodyRefused, match="bundle_state_header"):
        _inspect(ensemble, _rewrite(state, inconsistent_claim))


@pytest.mark.parametrize("mutation", ["schema", "count", "member"])
def test_historical_plain_header_rules_remain_closed(mutation):
    fixture = producer_fixture("plain")

    def change(arrays):
        header = json.loads(arrays["__header__"].tobytes())
        if mutation == "schema":
            header["schema"] = physical_graph_state_v2.ENSEMBLE_SCHEMA
        elif mutation == "count":
            header["parameter_count"] = True
        else:
            arrays["decoder_sd"] = np.ones(7, np.float32)
        arrays["__header__"] = np.frombuffer(_json(header), dtype=np.uint8)

    with pytest.raises(custody.CustodyRefused, match="bundle_state_header"):
        _inspect(fixture, _rewrite(fixture["state"], change))


@pytest.mark.parametrize("kind", ["decoded", "ensemble"])
def test_native_custody_uses_the_same_registered_codecs(tmp_path, kind):
    from test_public_bundle_model_custody import _native_graph_fixture

    fixture = producer_fixture(kind)
    root, manifest_path, originals = _native_graph_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_bytes())
    roles = manifest["roles"]
    recipe_raw, state = fixture["recipe"].canonical_bytes, fixture["state"]
    build = json.loads(originals[roles["build_receipt"]["file"]])
    build.update(
        recipe_digest=fixture["recipe"].digest,
        submission_digest=fixture["source"]["submission"],
        train_digest=_sha(fixture["material"]["train"]),
        state_digest=_sha(state),
        allowlist_digest=_sha(fixture["material"]["allowlist_bytes"]),
        fit=fixture["fit"],
    )
    inferred = json.loads(originals[roles["inference_receipt"]["file"]])
    inferred.update(recipe_digest=fixture["recipe"].digest, state_digest=_sha(state))
    replacements = {
        "recipe": recipe_raw,
        "inference_recipe": recipe_raw,
        "state": state,
        "inference_state": state,
        "source": _json(fixture["source"]),
        "train": fixture["material"]["train"],
        "build_receipt": _json(build),
        "inference_receipt": _json(inferred),
    }
    for role, raw in replacements.items():
        path = roles[role]["file"]
        originals[path] = raw
        (root / path).write_bytes(raw)
    manifest["source_schema"] = custody.graph_state_schema(
        state, recipe_raw, fixture["material"]["allowlist_bytes"]
    )
    manifest["retained_files"] = {name: _sha(raw) for name, raw in originals.items()}
    manifest_path.write_bytes(_json(manifest))
    receipt = custody.prepare_custody_v5(root, manifest_path)
    assert receipt["source_schema"] == manifest["source_schema"]
    assert receipt["state_digest"] == _sha(state)
    assert receipt["measurement_state"] == "NOT_MEASURED"
    assert receipt["official_eligible"] is False
    # A declared old schema cannot reinterpret actual ensemble bytes.
    if kind == "ensemble":
        manifest["source_schema"] = custody.GRAPH_SOURCE_STATE_SCHEMA
        manifest_path.write_bytes(_json(manifest))
        with pytest.raises(custody.CustodyRefused, match="native_graph_source_schema"):
            custody.prepare_custody_v5(root, manifest_path)
