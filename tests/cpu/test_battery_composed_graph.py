"""S2 CPU/public-fixture graph composition: parity, effects and objective refusal."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from carbon.agent_campaign.attack.adapters import battery_level1 as expressions
from carbon.battery import (
    composed_graph,
    composed_worker,
    development_rebuild,
    level4_model,
    level4_worker,
    pools,
    recipes,
)
from carbon.battery import level4 as battery
from carbon.battery.compile import compile_recipe
from carbon.level4 import allowlist, graph, intake, staging, submission
from carbon.reconstruction import development_composition as dc

ROOT = Path(__file__).resolve().parents[2]
BASE = {
    "width": 8,
    "depth": 1,
    "steps": 24,
    "batch_size": 32,
    "polish_steps": 4,
    "optimizer_family": "muon",
}
SEED = 7
(POOL,) = pools.registered()
PARTS = {
    "loss_expressions": expressions.VALID["valid_robust_l2"],
    "muon_spectral": True,
    "pool_selection": {
        "pool_version": POOL,
        "strata": {"train": 1.0},
        "box": {"t_amb_c": [10.0, 35.0]},
        "cases": 120,
    },
    "quasi_newton_family": "bfgs",
    "line_search": "backtracking",
}


def strategy(**values):
    return {
        "schema_version": "1.0",
        "challenge_id": battery.challenge_id(),
        "backbone": "mlp",
        "parameters": {**BASE, **values},
    }


@pytest.fixture(scope="module")
def graph_input():
    # A deliberately different architecture: graph width 12, outer recipe width 8.
    # Removing the graph must therefore change the trained parameter tree.
    loaded = allowlist.load()
    manifest, files = battery.lower_recipe(
        strategy(width=12), loaded, max_bytes=intake.BOUNDS["document_bytes"]
    )
    return submission.digest(manifest), staging.workspace(
        submission.canonical(manifest), files
    )


@pytest.fixture(scope="module")
def material():
    m = battery.material()
    return m.train, battery.structure(m)


def compiled(graph_input, **parts):
    digest, _ = graph_input
    return dc.compile(strategy(composition_graphs=digest, **parts), check_budget=False)


def fit(found, workspace, material):
    model = development_rebuild.build_in_process(
        found.construction, found.record, workspace
    )
    train, structure = material
    train = development_rebuild.training_data(found.record, train)
    return model, model.fit(train, structure, SEED)


def test_graph_only_composed_factory_keeps_existing_l4_parameters(
    graph_input, material
):
    found = compiled(graph_input)
    workspace = graph_input[1]
    native = level4_worker.build_in_process(found.construction, found.record, workspace)
    candidate = composed_graph.build(
        found.construction, found.record, workspace, composed=False
    )
    train, structure = material
    assert (
        candidate.fit(train, structure, SEED)["params_sha256"]
        == native.fit(train, structure, SEED)["params_sha256"]
    )


@pytest.mark.parametrize(
    "parts",
    [
        {"muon_spectral": True},
        {"pool_selection": PARTS["pool_selection"]},
        {"quasi_newton_family": "bfgs", "line_search": "backtracking"},
        {"loss_expressions": PARTS["loss_expressions"]},
        PARTS,
    ],
)
def test_graph_parts_rebuild_deterministically_and_never_take_classic_path(
    graph_input, material, parts
):
    found = compiled(graph_input, **parts)
    assert found.record["schema"] == composed_worker.GRAPH_SCHEMA
    first, one = fit(found, graph_input[1], material)
    second, two = fit(found, graph_input[1], material)
    assert isinstance(first, composed_graph.ComposedGraph)
    assert not first.classic and not second.classic
    assert one["params_sha256"] == two["params_sha256"]


@pytest.fixture(scope="module")
def effects(graph_input, material):
    full = compiled(graph_input, **PARTS)
    _, expected = fit(full, graph_input[1], material)
    removed = {}
    for field in PARTS:
        remaining = {k: v for k, v in PARTS.items() if k != field}
        _, result = fit(compiled(graph_input, **remaining), graph_input[1], material)
        removed[field] = result["params_sha256"]
    plain = dc.compile(strategy(**PARTS), check_budget=False)
    _, result = fit(plain, None, material)
    removed["composition_graphs"] = result["params_sha256"]
    return expected["params_sha256"], removed


@pytest.mark.parametrize("field", [*PARTS, "composition_graphs"])
def test_each_graph_combination_field_changes_the_actual_rebuild(effects, field):
    full, removed = effects
    assert full != removed[field], field


def test_declaration_only_graph_uses_the_single_l1_objective(graph_input, material):
    one = compiled(graph_input, loss_expressions=PARTS["loss_expressions"])
    two = compiled(
        graph_input, loss_expressions=expressions.VALID["valid_menu_restated"]
    )
    assert one.record["graph"]["loss_override"] == "graph"
    _, first = fit(one, graph_input[1], material)
    _, second = fit(two, graph_input[1], material)
    assert first["params_sha256"] != second["params_sha256"]


@pytest.fixture(scope="module")
def loss_graph_input(graph_input):
    import jax.numpy as jnp

    from carbon.level4.tooling import through_bprime

    raw, files = staging.from_workspace(graph_input[1], graph_input[0])
    manifest = json.loads(raw)
    documents = {
        role: json.loads(files[name]) for role, name in manifest["documents"].items()
    }
    _, recipe = compile_recipe(strategy())
    native = recipes.build(recipe.family, recipe.settings)
    m = battery.material()
    native.layout = recipes.Layout(
        m.train.v.shape[1],
        m.train.q.shape[1],
        bounded_v=native.bounded_v,
        predict_v0=native.predict_v0,
        fade=native.fade,
    )
    n_in, n_out = level4_model.dims(native)

    def case(pred, target, features):
        del features
        return jnp.sum((pred - target) ** 2, axis=1)

    loaded = allowlist.load()
    _, loss, _ = through_bprime(
        case,
        (jnp.ones((1, n_out)), jnp.ones((1, n_out)), jnp.ones((1, n_in))),
        role="loss",
        allowlist=loaded,
        input_names=["loss/pred/0", "loss/target/0", "loss/x/features"],
        max_bytes=intake.BOUNDS["document_bytes"],
    )
    manifest, files = submission.build(
        challenge=manifest["challenge"],
        interface=manifest["interface"],
        allowlist=loaded,
        forward=documents["forward"],
        init=documents["init"],
        loss=loss,
    )
    return submission.digest(manifest), staging.workspace(
        submission.canonical(manifest), files
    )


def test_actual_loss_graph_plus_expression_refuses_before_training(loss_graph_input):
    found = compiled(loss_graph_input, loss_expressions=PARTS["loss_expressions"])
    with pytest.raises(graph.GraphRefused) as refused:
        development_rebuild.build_in_process(
            found.construction, found.record, loss_graph_input[1]
        )
    assert refused.value.code == composed_graph.CONFLICT
    assert all(field in str(refused.value) for field in composed_graph.CONFLICT_FIELDS)


def test_graph_composition_preserves_self_contained_inference(graph_input, material):
    model, _ = fit(compiled(graph_input, **PARTS), graph_input[1], material)
    restored = level4_model.model_from_bytes(level4_model.state_bytes(model))
    x = material[0].x[:7]
    before, after = model.predict(x), restored.predict(x)
    for name in before:
        np.testing.assert_array_equal(before[name], after[name])


def test_composed_graph_missing_or_tampered_documents_is_infrastructure(graph_input):
    found = compiled(graph_input, muon_spectral=True)
    with pytest.raises(ImportError, match=level4_worker.BLOCKED):
        development_rebuild.build_in_process(found.construction, found.record)
    corrupted = {**graph_input[1], staging.WORKSPACE_MANIFEST: b"{}"}
    with pytest.raises(ImportError, match="level4_staging_corrupt"):
        development_rebuild.build_in_process(
            found.construction, found.record, corrupted
        )


def test_graph_parameter_tree_keeps_the_registered_l3_memory_bound(
    graph_input, material
):
    from copy import deepcopy

    from carbon.battery import level3_worker

    found = compiled(
        graph_input, quasi_newton_family="bfgs", line_search="backtracking"
    )
    record = deepcopy(found.record)
    original = found.reconstruction[level3_worker.QUASI_NEWTON]
    assert record["numerics"]["memory_bound_bytes"] == original["memory_bound_bytes"]
    # A fixture bound sufficient for the outer width-8 recipe, but insufficient
    # for the actual graph's width-12 parameter tree. No large Hessian is built.
    record["numerics"]["memory_bound_bytes"] = original["inverse_hessian_bytes"]
    model = development_rebuild.build_in_process(
        found.construction, record, graph_input[1]
    )
    with pytest.raises(graph.GraphRefused) as refused:
        model.fit(*material, SEED)
    assert refused.value.code == "development.inverse_hessian_too_large"
    assert model.prepared is None


def test_graph_owned_single_objective_composes_without_a_precedence_choice(
    loss_graph_input, material
):
    found = compiled(
        loss_graph_input, muon_spectral=True, pool_selection=PARTS["pool_selection"]
    )
    _, first = fit(found, loss_graph_input[1], material)
    _, second = fit(found, loss_graph_input[1], material)
    assert first["params_sha256"] == second["params_sha256"]


@pytest.mark.parametrize(
    "parts",
    [
        PARTS,
        {"pool_selection": PARTS["pool_selection"]},
        {"loss_expressions": PARTS["loss_expressions"]},
        {"quasi_newton_family": "bfgs", "line_search": "backtracking"},
    ],
)
def test_graph_staged_program_state_and_documents_match_in_process(
    tmp_path, graph_input, material, parts
):
    import subprocess
    import sys

    from carbon.battery.worker import RECONSTRUCT_PROGRAM, reconstruct_files, state_kind

    found = compiled(graph_input, **parts)
    model, expected = fit(found, graph_input[1], material)
    program, files, trainer = development_rebuild.stage(
        found.record,
        RECONSTRUCT_PROGRAM,
        reconstruct_files(ROOT, found.construction, SEED),
        level1_program=lambda: 1 / 0,
    )
    assert trainer == development_rebuild.COMPOSED and development_rebuild.uses_graph(
        found.record
    )
    assert "state = level4_model.state_bytes(model)" in program
    files.update(graph_input[1])
    work, output = tmp_path / "work", tmp_path / "output"
    work.mkdir()
    output.mkdir()
    for name, body in files.items():
        (work / name).write_bytes(body)
    (work / "program.py").write_text(program, encoding="utf-8", newline="\n")
    subprocess.run(
        [sys.executable, "program.py"],
        cwd=work,
        env={"PYTHONPATH": str(ROOT), "JAX_PLATFORMS": "cpu", "PATH": "/usr/bin:/bin"},
        check=True,
        timeout=900,
    )
    actual = json.loads((output / "fit.json").read_text(encoding="utf-8"))
    assert actual["params_sha256"] == expected["params_sha256"]
    state = (output / "state.npz").read_bytes()
    assert state_kind(state) == "level4_graph"
    restored = level4_model.model_from_bytes(state)
    before, after = model.predict(material[0].x[:5]), restored.predict(
        material[0].x[:5]
    )
    for name in before:
        np.testing.assert_array_equal(before[name], after[name])


def test_isolated_worker_stages_composed_graph_documents(monkeypatch, graph_input):
    from carbon.battery.worker import CarrierBackend

    found = compiled(graph_input, muon_spectral=True)
    carrier = object.__new__(CarrierBackend)
    carrier.root = ROOT
    calls = []

    def capture(identity, program, files, names, backend):
        calls.append(files)
        return {"state.npz": b"fixture-state", "fit.json": b"{}"}

    monkeypatch.setattr(carrier, "_call", capture)
    carrier.reconstruct(None, found.construction, SEED, found.record, graph_input[1])
    assert len(calls) == 1
    for name, body in graph_input[1].items():
        assert calls[0][name] == body


def test_graph_admission_strips_every_widening_and_keeps_pool_batch(graph_input):
    from carbon.battery import level4_admission

    requested = strategy(composition_graphs=graph_input[0], **PARTS)
    assert level4_admission._base(requested) == strategy()
    _, batch = level4_admission.interface_and_batch(requested)
    assert batch == BASE["batch_size"]
    small = {**requested, "parameters": {**requested["parameters"], "batch_size": 256}}
    _, batch = level4_admission.interface_and_batch(small)
    assert batch == PARTS["pool_selection"]["cases"]


def test_graph_envelope_checks_single_objective_and_refuses_actual_conflict(
    graph_input, loss_graph_input
):
    from carbon.battery import level4_admission

    def envelope(value):
        raw, files = staging.from_workspace(value[1], value[0])
        return json.dumps(staging.envelope(raw, files)).encode("utf-8")

    requested = strategy(
        composition_graphs=graph_input[0], loss_expressions=PARTS["loss_expressions"]
    )
    assert level4_admission.admit_envelope(
        requested, envelope(graph_input), loss_override="graph"
    )
    requested = strategy(
        composition_graphs=loss_graph_input[0],
        loss_expressions=PARTS["loss_expressions"],
    )
    with pytest.raises(graph.GraphRefused) as refused:
        level4_admission.admit_envelope(
            requested, envelope(loss_graph_input), loss_override="graph"
        )
    assert refused.value.code == "construction_rebuild_unavailable"
    assert all(field in str(refused.value) for field in composed_graph.CONFLICT_FIELDS)


def test_unset_graph_cap_still_blocks_a_combination(monkeypatch, graph_input, material):
    found = compiled(graph_input, muon_spectral=True)
    monkeypatch.setattr(
        allowlist, "CAPS", {**allowlist.CAPS, "nodes_executed": allowlist.HUMAN_INPUT}
    )
    model = development_rebuild.build_in_process(
        found.construction, found.record, graph_input[1]
    )
    with pytest.raises(ImportError, match=level4_model.CAPS_UNSET):
        model.fit(*material, SEED)
    assert model.prepared is None


def test_composition_graph_directory_uses_graph_widening_and_all_base_fields(
    tmp_path, monkeypatch, graph_input
):
    from carbon.reconstruction import development_level_cli as door

    composition = dc.load(battery.challenge_id())
    # S2 exercises the directory checker with a verified composition object;
    # S3 owns selecting/serving this composition through the launch request.
    monkeypatch.setattr(door, "_variant", lambda request: composition)
    requested = strategy(composition_graphs=graph_input[0], **PARTS)
    raw, files = staging.from_workspace(graph_input[1], graph_input[0])
    directory = tmp_path / "composed-directory"
    staging.write_directory(directory, raw, files)
    request = {"strategy": requested, "directory": str(directory)}
    checked = door.level4(request)
    assert checked["variant_digest"] == composition.digest
    assert staging.from_envelope(checked["envelope"]) == (graph_input[0], raw, files)
    # Changing the effective batch must fail the checker rather than passing
    # merely because a composition includes a graph-capable variant.
    request["strategy"] = {
        **requested,
        "parameters": {**requested["parameters"], "batch_size": 256},
    }
    with pytest.raises(door.Refused) as refused:
        door.level4(request)
    assert refused.value.code == door.BATCH_MISMATCH
