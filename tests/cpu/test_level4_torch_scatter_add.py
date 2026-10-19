"""Versioned static-index scatter lowering; v5 remains frozen and refused."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret
from carbon.level4.tooling import lower_torch

V5 = Path(allowlist_module.__file__).with_name("allowlist_v5.json")
V6 = Path(allowlist_module.__file__).with_name("allowlist_v6.json")


def _prospective():
    return allowlist_module.load(V6)


def test_v6_only_adds_static_torch_emitter_and_keeps_graph_scatter_refused():
    import hashlib
    import json

    from carbon.development_session.bundle_construction_worker import _trusted_allowlist
    from carbon.development_session.construction_recipe import RecipeRefused

    old, new = json.loads(V5.read_bytes()), json.loads(V6.read_bytes())
    assert hashlib.sha256(V5.read_bytes()).hexdigest() == (
        "f26ea734d3078564b72fa30c66ab46cf4419a004ed249130481b517985af3122"
    )
    assert new.pop("version") == "level4-allowlist-v6"
    assert old.pop("version") == "level4-allowlist-v5"
    admitted = new["aten_core"].pop("aten.scatter_add.default")
    assert admitted["default"] == "allow" and admitted["lowering"] == "emitted"
    assert new == old
    assert new["carbon_ops"]["scatter_add"]["v0_interpreter"] is False
    with pytest.raises(graph.GraphRefused) as refused:
        _prospective().admit("scatter_add", "forward")
    assert refused.value.code == "op_not_supported_v0"
    with pytest.raises(RecipeRefused, match="bundle_allowlist_unregistered"):
        _trusted_allowlist(V6.read_bytes())


def _static_program():
    torch = pytest.importorskip("torch")

    class Scatter(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(
                torch.tensor([[0.5, -0.25, 1.0], [0.75, 0.125, -0.5]])
            )
            self.register_buffer(
                "index", torch.tensor([[2, 2, 0], [1, 1, 3]], dtype=torch.int64)
            )

        def forward(self, x):
            return x.scatter_add(1, self.index, self.weight)

    module = Scatter()
    x = torch.arange(8, dtype=torch.float32).reshape(2, 4) / 8
    program = torch.export.export(module, (x,)).run_decompositions()
    assert "aten.scatter_add.default" in lower_torch.inventory(program)
    return torch, module, x, program


def test_ordered_repeats_forward_gradient_and_source_free_state_parity():
    jax = pytest.importorskip("jax")
    import numpy as np

    _torch, module, x, program = _static_program()
    allowed = _prospective()
    doc, _ = lower_torch.lower(program, allowlist=allowed)
    assert any(entry["name"] == "params/0" for entry in doc["graphs"]["main"]["inputs"])
    assert any(
        entry["dtype"] == "int32" for entry in doc["graphs"]["main"]["constants"]
    )
    assert all(node["op"] != "scatter_add" for node in doc["graphs"]["main"]["nodes"])
    assert (
        graph.measure(doc)["nodes_executed"] <= allowlist_module.CAPS["nodes_executed"]
    )
    parsed = graph.parse(
        graph.dumps(doc), max_bytes=allowlist_module.CAPS["document_bytes"]
    )
    rebuilt = interpret.rebuild(parsed, allowed)

    def run(weight, base):
        values = {
            "params/0": weight,
            next(
                entry["name"]
                for entry in doc["graphs"]["main"]["inputs"]
                if entry["name"].startswith("inputs/")
            ): base,
        }
        return rebuilt(
            *(values[entry["name"]] for entry in doc["graphs"]["main"]["inputs"])
        )[0]

    weight = jax.numpy.asarray(module.weight.detach().numpy())
    base = jax.numpy.asarray(x.numpy())
    np.testing.assert_allclose(
        np.asarray(run(weight, base)),
        module(x).detach().numpy(),
        rtol=1e-6,
        atol=1e-6,
    )
    wanted_base = x.detach().clone().requires_grad_(True)
    (module(wanted_base) ** 2).sum().backward()
    got_weight, got_base = jax.grad(
        lambda w, b: jax.numpy.sum(run(w, b) ** 2), argnums=(0, 1)
    )(weight, base)
    np.testing.assert_allclose(
        np.asarray(got_weight), module.weight.grad.numpy(), rtol=1e-5, atol=1e-5
    )
    np.testing.assert_allclose(
        np.asarray(got_base), wanted_base.grad.numpy(), rtol=1e-5, atol=1e-5
    )


def _field_program():
    torch = pytest.importorskip("torch")

    class StaticField(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.full((1, 2, 8, 1), 7.0))
            self.register_buffer("index", torch.ones((1, 2, 8, 1), dtype=torch.int64))

        def forward(self, x):
            return x.scatter_add(1, self.index, self.weight)

    source = StaticField()
    example = torch.zeros((1, 8, 8, 1), dtype=torch.float32)
    return source, torch.export.export(source, (example,)).run_decompositions()


def test_static_field_lowers_with_registered_caps_and_no_captured_weights():
    _source, program = _field_program()
    forward, _ = lower_torch.lower(program, allowlist=_prospective())
    assert [i["name"] for i in forward["graphs"]["main"]["inputs"]] == [
        "params/0",
        "inputs/x",
    ]
    assert all(n["op"] != "scatter_add" for n in forward["graphs"]["main"]["nodes"])
    assert all(
        c["shape"] != [1, 2, 8, 1] for c in forward["graphs"]["main"]["constants"]
    )
    assert all(
        v == "pass"
        for v in allowlist_module.check_caps(graph.measure(forward)).values()
    )


def test_static_scatter_fits_fixed_public_train_then_loads_inert_numeric_state():
    jax = pytest.importorskip("jax")
    import io
    import json
    import zipfile

    import numpy as np

    from carbon.challenge_kit import synthetic_linear_field_2d as fixture
    from carbon.development_session import bundle_graph_state
    from carbon.development_session.construction_recipe import ConstructionRecipe
    from carbon.development_session.synthetic_graph_adapter import (
        build_validated_graph,
        checked_train,
        graph_interface,
    )
    from carbon.level4 import initializers, submission

    source, program = _field_program()
    allowed = _prospective()
    forward, _ = lower_torch.lower(program, allowlist=allowed)
    # The authoring layer binds Torch's local argument name to this Challenge's
    # published input name before the immutable submission is built.
    inputs = forward["graphs"]["main"]["inputs"]
    assert [i["name"] for i in inputs] == ["params/0", "inputs/x"]
    inputs[1]["name"] = "inputs/forcing"
    assert all(n["op"] != "scatter_add" for n in forward["graphs"]["main"]["nodes"])
    assert all(
        c["shape"] != [1, 2, 8, 1] for c in forward["graphs"]["main"]["constants"]
    )  # captured module weights are not a submission artifact

    init_spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(forward),
        "parameters": [
            {
                "input": "params/0",
                "initializer": "zeros",
                "fan_in_axes": [],
                "fan_out_axes": [],
            }
        ],
    }
    manifest, files = submission.build(
        challenge=fixture.CHALLENGE.challenge_id,
        interface=graph_interface().digest(),
        allowlist=allowed,
        forward=forward,
        init_spec=init_spec,
    )
    recipe_body = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "cr06_public"
            / "cr06_recipe.json"
        ).read_bytes()
    )
    recipe_body["challenge"]["version"] = "prospective-v6-test"
    recipe_body["source"]["submission_digest"] = submission.digest(manifest)
    recipe_body["procedure"]["configuration"]["training"]["optimizer"] = "sgd"
    recipe = ConstructionRecipe.from_dict(recipe_body)
    train_x, train_y = checked_train(
        fixture.train_bytes(), recipe.to_dict()["challenge"]["train_digest"]
    )
    model = build_validated_graph(
        recipe,
        submission.canonical(manifest),
        files,
        allowlist_bytes=V6.read_bytes(),
        train_cases=len(train_x),
    )
    fit = model.fit(train_x, train_y, seed=3)
    assert fit["train_cases"] == fixture.TRAIN_CASES
    assert fit["steps"] == 1
    assert any(np.any(p != 0) for p in model.params)
    assert all(
        not np.array_equal(p, source.weight.detach().numpy()) for p in model.params
    )

    state = model.frozen_state()
    with zipfile.ZipFile(io.BytesIO(state)) as archive:
        assert set(archive.namelist()) == {
            "__header__.npy",
            "graph.npy",
            "parameter0000.npy",
        }
    frozen_graph, frozen_params = bundle_graph_state.load(state, recipe, allowed)
    inference = interpret.rebuild(frozen_graph, allowed)
    query = fixture.practice_inputs()[:1]
    inert_prediction = inference(
        jax.numpy.asarray(frozen_params[0]), jax.numpy.asarray(query)
    )[0]
    np.testing.assert_allclose(np.asarray(inert_prediction), model.predict(query))
    with pytest.raises(bundle_graph_state.RecipeRefused):
        bundle_graph_state.load(state, recipe, allowlist_module.load(V5))


def test_pinned_v5_still_refuses_scatter_add():
    _, _, _, program = _static_program()
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=allowlist_module.load(V5))
    assert refused.value.code == "aten_op_not_allowlisted"


def test_input_derived_indices_refuse_until_runtime_bounds_have_a_trusted_path():
    torch = pytest.importorskip("torch")

    class Dynamic(torch.nn.Module):
        def forward(self, base, index, source):
            return base.scatter_add(1, index, source)

    base = torch.zeros((2, 4))
    index = torch.tensor([[2, 2, 0], [1, 1, 3]], dtype=torch.int64)
    source = torch.ones((2, 3))
    program = torch.export.export(Dynamic(), (base, index, source)).run_decompositions()
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=_prospective())
    assert refused.value.code == "aten_scatter_index_not_static"


def test_static_out_of_bounds_and_registered_cost_refuse():
    _, _, _, program = _static_program()
    program.state_dict["index"][0, 0] = 4
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=_prospective())
    assert refused.value.code == "aten_scatter_index_out_of_bounds"

    _, _, _, program = _static_program()
    original = allowlist_module.CAPS["nodes_executed"]
    allowlist_module.CAPS["nodes_executed"] = 1
    try:
        with pytest.raises(graph.GraphRefused) as refused:
            lower_torch.lower(program, allowlist=_prospective())
    finally:
        allowlist_module.CAPS["nodes_executed"] = original
    assert refused.value.code == "aten_scatter_registered_resource_bound"

    original = allowlist_module.CAPS["largest_intermediate_bytes"]
    allowlist_module.CAPS["largest_intermediate_bytes"] = 31
    try:
        with pytest.raises(graph.GraphRefused) as refused:
            lower_torch.lower(program, allowlist=_prospective())
    finally:
        allowlist_module.CAPS["largest_intermediate_bytes"] = original
    assert refused.value.code == "aten_scatter_registered_resource_bound"


def test_large_ordered_graph_uses_registered_single_intermediate_bound():
    torch = pytest.importorskip("torch")

    class Wide(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.register_buffer("index", torch.arange(256, dtype=torch.int64) // 2)

        def forward(self, base, source):
            return base.scatter_add(0, self.index, source)

    program = torch.export.export(
        Wide(), (torch.zeros(65536), torch.ones(256))
    ).run_decompositions()
    doc, _ = lower_torch.lower(program, allowlist=_prospective())
    measured = graph.measure(doc)
    assert measured["nodes_executed"] == 2 + 7 * 256
    assert measured["largest_intermediate_bytes"] == 65536 * 4
    assert all(
        verdict == "pass" for verdict in allowlist_module.check_caps(measured).values()
    )


@pytest.mark.parametrize("case", ["dimension", "index_dtype", "source_shape"])
def test_static_scatter_refuses_invalid_dimension_dtype_or_shape(case):
    torch, _, _, program = _static_program()
    node = next(
        item
        for item in program.graph.nodes
        if str(item.target) == "aten.scatter_add.default"
    )
    if case == "dimension":
        node.args = (node.args[0], 3, node.args[2], node.args[3])
    elif case == "index_dtype":
        program.state_dict["index"] = program.state_dict["index"].to(torch.int32)
        node.args[2].meta["val"] = torch.empty((2, 3), dtype=torch.int32)
    else:
        node.args[3].meta["val"] = torch.empty((2, 2), dtype=torch.float32)
    with pytest.raises(graph.GraphRefused) as refused:
        lower_torch.lower(program, allowlist=_prospective())
    assert refused.value.code == "aten_scatter_shape_or_dtype_not_supported"
