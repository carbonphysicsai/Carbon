"""Actual fixed inference programs over real codec output and public inputs.

Parameters/decoders are synthetic, not trained models. Only carrier accounting
is a fixture: both child programs really load, interpret and predict, without
mocking the state loader or numerical predictions. This is CPU program-contract
evidence, not Docker containment, GPU, science or official qualification.
"""

from __future__ import annotations

import base64
import copy
import json
import os

import numpy as np
import pytest
from test_bundle_graph_state import _recipe as _bundle_recipe
from test_f08_f02_graph_adapters import _case as _decoded_case
from test_graph_route_v2 import _case as _ensemble_case
from test_graph_route_v2 import _image, _local_runner
from test_paired_inference import FixtureLedger

from carbon.challenge_kit import physical_material
from carbon.development_session import (
    bundle_construction_worker,
    bundle_graph_state,
    direct_graph_construction_worker,
    paired_inference,
    physical_graph_state,
    physical_graph_state_v2,
    single_call_timing,
)
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret

pytestmark = pytest.mark.skipif(os.name != "posix", reason="fixed program subprocesses")
FORMATS = {
    "bundle": ("f08-ribbed-bracket", "1.6"),
    "decoded": ("f08-ribbed-bracket", "1.4"),
    "ensemble32": ("f08-ribbed-bracket", "1.6"),
    "ensemble64": ("electric-motor-magnetics", "1.5"),
}


def _precision(dtype):
    import jax

    return jax.enable_x64(np.dtype(dtype) == np.dtype("float64"))


@pytest.fixture(scope="module", params=sorted(FORMATS))
def artifact(request):
    kind, key = request.param, FORMATS[request.param]
    material = physical_material.bundle_material(*key)
    permitted = allowlist_module.Allowlist(material["allowlist_bytes"])
    with _precision(material["practice_inputs"].dtype):
        if kind == "decoded":
            recipe, raw_manifest, documents, _staging = _decoded_case(key)
        else:
            recipe, raw_manifest, documents, _staging = _ensemble_case(key, {})
    manifest = json.loads(raw_manifest)
    doc = graph.parse(
        documents[manifest["documents"]["forward"]],
        max_bytes=bundle_graph_state._limits(permitted)[1],
    )
    entries = doc["graphs"][doc["entry"]]["inputs"]
    parameters = [
        np.zeros(entry["shape"], entry["dtype"])
        for entry in entries
        if entry["name"].startswith("params/")
    ]
    width = physical_graph_state._width(doc)
    dtype = parameters[0].dtype
    parameters[-1][...] = np.arange(width, dtype=dtype) / 4
    mu, sd = np.arange(width, dtype=dtype) / 2, np.full(width, 2, dtype)
    if kind == "bundle":
        value = recipe.to_dict()
        value["source"] = _bundle_recipe().to_dict()["source"]
        value["procedure"]["entrypoint"] = {"module": "synthetic", "name": "build"}
        recipe = ConstructionRecipe.from_dict(value)
        for entry in entries:
            if entry["name"].startswith("inputs/"):
                entry["name"] = "inputs/x"
        state = bundle_graph_state.freeze(recipe, doc, parameters, permitted)
        loader = bundle_graph_state.load
    elif kind == "decoded":
        state = physical_graph_state.freeze(recipe, doc, parameters, permitted, mu, sd)
        loader = physical_graph_state.load
    else:
        second = [value.copy() for value in parameters]
        second[-1] += 1
        combine = np.vstack((np.full(width, 0.25, dtype), np.full(width, 0.75, dtype)))
        state = physical_graph_state_v2.freeze(
            recipe, doc, [parameters, second], permitted, mu, sd, combine
        )
        loader = physical_graph_state_v2.load
    kit = material["construction_kit"]
    binding = {
        "challenge_id": key[0],
        "challenge_version": key[1],
        **{
            field: kit[field]
            for field in (
                "train_digest",
                "interface_digest",
                "construction_limits_digest",
            )
        },
    }
    inputs = np.ascontiguousarray(material["practice_inputs"][:8], dtype=dtype)
    return {
        "kind": kind,
        "key": key,
        "recipe": recipe,
        "state": state,
        "material": material,
        "allowlist": permitted,
        "binding": binding,
        "inputs": inputs,
        "dtype": str(dtype),
        "width": width,
        "policy": material["construction_limits_document"][
            "reconstruction_resource_policy"
        ],
        "loaded": loader(state, recipe, permitted),
    }


def _expected(artifact, *, per_case):
    loaded = artifact["loaded"]
    doc = loaded[0]
    width = artifact["width"]
    if artifact["kind"].startswith("ensemble"):
        members, mu, sd, combine = loaded[1:]
    elif artifact["kind"] == "decoded":
        parameters, mu, sd = loaded[1:]
        members, combine = [parameters], np.ones((1, width), artifact["dtype"])
    else:
        members = [loaded[1]]
        mu = np.zeros(width, artifact["dtype"])
        sd = np.ones(width, artifact["dtype"])
        combine = np.ones((1, width), artifact["dtype"])
    with _precision(artifact["dtype"]):
        import jax.numpy as jnp

        fn = interpret.rebuild(doc, artifact["allowlist"])

        def predict(inputs):
            return (
                sum(
                    np.asarray(
                        fn(*[jnp.asarray(p) for p in params], jnp.asarray(inputs))[0]
                    )
                    * combine[index]
                    for index, params in enumerate(members)
                )
                * sd
                + mu
            )

        if not per_case:
            return predict(artifact["inputs"])
        results = []
        for row in artifact["inputs"]:
            padded = np.zeros_like(artifact["inputs"])
            padded[0] = row
            results.append(predict(padded)[0])
        return np.asarray(results)


def _runner(ledger, seen):
    local = _local_runner()

    def run(current_ledger, **kwargs):
        assert current_ledger is ledger
        assert not {"train.npz", "train.gz", "source.tar.gz"} & kwargs["files"].keys()
        seen.append(kwargs)
        result = local(current_ledger, **kwargs)
        # Explicit synthetic accounting; program outputs/receipts are real.
        ledger.record(
            kwargs["identity"], "SUCCEEDED", {"numerical_milliseconds": 1}, result
        )
        return result

    return run


@pytest.mark.parametrize("procedure", ["per_case", "batched_measured"])
def test_pair_executes_the_registered_codec_and_program(artifact, procedure, tmp_path):
    ledger, seen = FixtureLedger(tmp_path), []
    try:
        result = paired_inference.infer_frozen_pair(
            ledger,
            owner="fixture-owner",
            identity="real-program-pair",
            inference_image=_image(),
            recipe=artifact["recipe"],
            challenge_binding=artifact["binding"],
            limits_document=artifact["material"]["construction_limits_document"],
            state_bytes=artifact["state"],
            expected_state_digest=paired_inference._digest(artifact["state"]),
            inputs=artifact["inputs"],
            expected_output_shape=(8, artifact["width"]),
            expected_output_dtype=artifact["dtype"],
            allowlist_bytes=artifact["material"]["allowlist_bytes"],
            seconds=artifact["policy"]["inference_wall_seconds_max"],
            total_seconds=artifact["policy"]["total_reconstruction_wall_seconds_max"],
            procedure=procedure,
            runner=_runner(ledger, seen),
        ).evidence
        expected = _expected(artifact, per_case=procedure == "per_case")
        assert len(seen) == 2
        for phase in ("primary", "repeat"):
            raw = base64.b64decode(
                result[phase]["originals"]["predictions.json"]["raw_base64"]
            )
            np.testing.assert_array_equal(np.asarray(json.loads(raw)), expected)
        assert result["execution_boundary"] == "TEST_ONLY_LOCAL_RUNNER"
        assert result["official_eligible"] is False
        assert (
            result["primary"]["worker_operation"]
            != result["repeat"]["worker_operation"]
        )
        assert seen[0]["files"]["state.npz"] == artifact["state"]
    finally:
        ledger.connection.close()


def test_derived_single_call_executes_the_same_registered_graph(artifact, tmp_path):
    ledger, seen = FixtureLedger(tmp_path), []
    try:
        limits = artifact["material"]["construction_limits_document"]
        bundle_construction_worker.verify_direct_resource_policy(
            artifact["binding"], limits
        )
        query = {}
        if artifact["kind"] != "bundle":
            _loader, query, dtype = (
                direct_graph_construction_worker.registered_inference_contract(
                    artifact["binding"],
                    artifact["material"]["construction_limits_document"],
                    recipe=artifact["recipe"],
                )
            )
            assert dtype == artifact["dtype"]
        program = single_call_timing.program(
            query.pop("program", bundle_construction_worker.INFER_PROGRAM)
        )
        bank = np.tile(artifact["inputs"], (4, 1))
        indices = list(range(single_call_timing.SAMPLE))
        result = bundle_construction_worker._infer_state(
            ledger,
            owner="fixture-owner",
            identity="real-single-call",
            inference_image=_image(),
            recipe=artifact["recipe"],
            binding=artifact["binding"],
            state=artifact["state"],
            state_digest=paired_inference._digest(artifact["state"]),
            inputs=bank,
            expected_output_shape=(single_call_timing.SAMPLE, artifact["width"]),
            expected_output_dtype=artifact["dtype"],
            allowlist_bytes=artifact["material"]["allowlist_bytes"],
            single_call={"indices": indices, "warmup": artifact["inputs"][:1]},
            program=program,
            runner=_runner(ledger, seen),
            seconds=artifact["policy"]["inference_wall_seconds_max"],
            **bundle_construction_worker.rebuild_wall_kwargs(limits),
            **query,
        )
        expected = np.tile(_expected(artifact, per_case=True), (4, 1))[indices]
        np.testing.assert_array_equal(np.asarray(result.predictions), expected)
        assert len(seen) == 1
    finally:
        ledger.connection.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "unregistered-fixture-adapter"),
        ("state_schema", "unregistered-fixture-state"),
        ("program", "unregistered-fixture-code"),
    ],
)
def test_unknown_adapter_declaration_refuses_before_state_or_execution(field, value):
    from carbon.development_session import graph_adapters

    key = ("f08-ribbed-bracket", "1.6")
    material = physical_material.bundle_material(*key)
    recipe = ConstructionRecipe.from_dict(
        graph_adapters.graph_recipe(*key, "sha256:" + "1" * 64)
    )
    binding = {"challenge_id": key[0], "challenge_version": key[1]}
    limits = copy.deepcopy(material["construction_limits_document"])
    limits["graph_training_adapter"][field] = value
    with pytest.raises(RecipeRefused, match="direct_graph_adapter_identity_invalid"):
        direct_graph_construction_worker.registered_inference_contract(
            binding, limits, recipe=recipe
        )


def test_corrupt_state_refuses_before_dispatch_for_every_codec(artifact, tmp_path):
    state = artifact["state"][:-1]
    ledger = FixtureLedger(tmp_path)

    def unexpected_runner(*_args, **_kwargs):
        raise AssertionError("invalid inert state reached execution")

    try:
        with pytest.raises(RecipeRefused):
            paired_inference.infer_frozen_pair(
                ledger,
                owner="fixture-owner",
                identity="bad-state-pair",
                inference_image=_image(),
                recipe=artifact["recipe"],
                challenge_binding=artifact["binding"],
                limits_document=artifact["material"]["construction_limits_document"],
                state_bytes=state,
                expected_state_digest=paired_inference._digest(state),
                inputs=artifact["inputs"],
                expected_output_shape=(8, artifact["width"]),
                expected_output_dtype=artifact["dtype"],
                allowlist_bytes=artifact["material"]["allowlist_bytes"],
                seconds=artifact["policy"]["inference_wall_seconds_max"],
                total_seconds=artifact["policy"][
                    "total_reconstruction_wall_seconds_max"
                ],
                runner=unexpected_runner,
            )
        assert (
            ledger.connection.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
            == 0
        )
    finally:
        ledger.connection.close()
