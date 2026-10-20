"""Battery's published scaffold, served as a ready direct recipe (BUG
GRAPHITE_PRACTICE_CALL_REFUSED_20261020, step 2; Validator option A).

public_material scaffold_recipe stages the scaffold graph where practice reads
a workspace graph and returns a recipe naming only the scaffold's published
steps. That recipe resolves its graph from the workspace, validates against
the kit and interface, and is not Carbon's leg-minimum baseline recipe.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_lp_prod_research_tools import ledger

from carbon.battery import challenge, direct_graph, public_scaffold
from carbon.battery.research import BatteryPublicMaterial, make_battery_research_service
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    graph_envelope_from_workspace,
)
from carbon.development_session.profile import digest
from carbon.development_session.research_tools import ResearchMinerTools
from carbon.development_session.research_workspace import ResearchWorkspace
from carbon.level4 import intake, staging

REPOSITORY = Path(__file__).resolve().parents[2]
#: The leg-minimum baseline recipes (OWNER-LEG-MINIMUM-BEST-AGENT-01): never served.
LEG_MINIMUM_RECIPES = {
    "sha256:2b9ccd38fa4f8018655f693041f3a206545d86b9a00582a305ed9d8314f325e3",
    "sha256:00853517f170e2f6eab3e754cc1dfad2a347c057fdf9f31f93d6fa7fb30213b0",
    "sha256:08a9c190f4401464715af72e5608521de3569babb2b536ffd7fd14cdc855e0ea",
}


@pytest.fixture
def served(tmp_path):
    meter = ledger(tmp_path / "ledger")
    workspace = ResearchWorkspace(meter, "alice")
    reply = BatteryPublicMaterial(REPOSITORY)("scaffold_recipe", workspace)
    return meter, workspace, reply


def test_the_scaffold_graph_is_the_pinned_published_lowering():
    manifest, files = public_scaffold.graph()
    assert digest(manifest) == public_scaffold.GRAPH_DIGEST
    assert set(files) == set(public_scaffold.DOCUMENTS.values())
    assert json.loads(manifest)["allowlist"]["version"] == "level4-allowlist-v1"


def test_the_material_stages_the_graph_and_returns_a_ready_recipe(served):
    _, workspace, reply = served
    assert workspace.get(staging.WORKSPACE_MANIFEST) == public_scaffold.graph()[0]
    for document in public_scaffold.DOCUMENTS.values():
        assert workspace.get(staging.WORKSPACE_PREFIX + document[7:] + ".json")
    recipe = ConstructionRecipe.from_dict(reply["document"])
    training = recipe.to_dict()["procedure"]["configuration"]["training"]
    assert training == {"steps": 2000}  # only the scaffold's published field
    assert recipe.digest not in LEG_MINIMUM_RECIPES
    assert "scaffold graph is staged" in reply["use"]
    # The anchors' dependency is served to the agent with the scaffold.
    assert "train_fraction 1.0" in reply["anchors"]
    assert "initial_voltage" in reply["anchors"]


def test_the_served_recipe_resolves_and_validates_as_practice_would(served):
    meter, _, reply = served
    recipe = ConstructionRecipe.from_dict(reply["document"])
    envelope = graph_envelope_from_workspace(meter, "alice", recipe)
    assert json.loads(envelope)["submission"] == public_scaffold.GRAPH_DIGEST
    settings = direct_graph.training_settings(recipe)
    assert settings["steps"] == 2000 and settings["batch_size"] == 400
    manifest, files = public_scaffold.graph()
    model = direct_graph.build_validated_graph(
        recipe,
        manifest,
        files,
        max_bytes=intake.BOUNDS["submission_bytes"],
        train_cases=challenge.TRAIN_V1_CASES,
    )
    assert model is not None


def test_the_recipe_passes_the_direct_practice_door(served, tmp_path):
    _, _, reply = served
    meter = ledger(tmp_path / "door-ledger")
    composition = make_battery_research_service(
        root=tmp_path / "tasks",
        ledger=meter,
        owner="alice",
        image=SimpleNamespace(),
        practice=SimpleNamespace(root=tmp_path, construction_mode="direct"),
        material=lambda *a: None,
    )
    try:
        sdk = ResearchMinerTools(
            connection=None,
            wrapper=None,
            composition=composition,
            ledger=meter,
            owner="alice",
        )
        args = json.loads(
            json.dumps(
                {
                    "kind": "practice",
                    "strategy_json": json.dumps(reply["document"]),
                    "action": None,
                    "arguments_json": None,
                    "hypothesis": "the published scaffold",
                    "expected_effect": "a practice score",
                }
            )
        )
        request = sdk._request("start_research_task", args, "lp-scaffold-recipe-0001")
        assert type(request.task_spec).__name__ == "DirectPracticeTaskSpecV1"
    finally:
        composition.tasks.close()


def test_the_anchored_scaffold_passes_every_gate_on_public_practice():
    """The published scaffold is anchored (T(0) = t_amb, V(0) = OCV(soc0) from
    the published table, voltage inside the protocol window), so a miner's
    first practice scores. Scored here as the practice door scores, with the
    exam's own gates and frozen tolerances, on public PRACTICE only."""
    import jax
    import numpy as np

    from carbon.battery import domain
    from carbon.battery.practice import PracticeSet, score_practice

    manifest, files = public_scaffold.graph()
    recipe = ConstructionRecipe.from_dict(public_scaffold.recipe())
    model = direct_graph.build_validated_graph(
        recipe,
        manifest,
        files,
        max_bytes=intake.BOUNDS["submission_bytes"],
        train_cases=challenge.TRAIN_V1_CASES,
    )
    material = challenge.PublicMaterial.load(REPOSITORY)
    practice = PracticeSet.load(REPOSITORY)
    with jax.enable_x64(False):
        model.fit(material.train, seed=7)
        x = np.array(
            [[r["inputs"][k] for k in domain.INPUTS] for r in practice.records],
            dtype=np.float32,
        )
        out = model.predict(x)
    predictions = {
        r["case_id"]: {
            "voltage_v": out["v"][i].tolist(),
            "temperature_c": out["t"][i].tolist(),
            "plating_margin_v": float(out["eta"][i]),
            "capacity_ah": out["q"][i].tolist(),
        }
        for i, r in enumerate(practice.records)
    }
    rows, summary = score_practice(predictions, practice, material, REPOSITORY)
    assert summary["n_gate_failed"] == 0 and summary["n_scored"] == 200
    for gate in (
        "initial_temperature",
        "initial_voltage",
        "voltage_ceiling",
        "voltage_floor",
    ):
        assert all(row["gates"][gate] == "PASS" for row in rows), gate
