"""Battery 2.1 graphs build through the direct-graph worker under allowlist v7
(Validator, 2026-10-21): the worker binds the recipe's own version's kit,
stages v7 and reads v7's intake bounds and state envelope. Battery 1.0 stages
exactly what it did before.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.battery import (
    challenge,
    construction_kit,
    direct_graph,
    direct_graph_inference,
    direct_graph_worker,
)
from carbon.battery.public_model_retention import MAX_STATE_BYTES
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import intake
from carbon.reconstruction.worker import model as worker_model

ROOT = Path(__file__).resolve().parents[2]
#: 1.0's staged file names, before versioning (plus the graph's own documents).
STAGED_1_0 = {
    *(name + ".py" for name in direct_graph_worker.STAGED_MODULES),
    *direct_graph_worker.BATTERY_MODULES,
    "allowlist_v1.json",
    "allowlist_v6.json",
    "recipe.json",
    "settings.json",
    "train-v1.jsonl.gz",
    "test-inputs.json",
    "control.json",
}


def _recipe(version, submission_digest="sha256:" + "a" * 64):
    kit = construction_kit.construction_kit_for(version)
    return ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": kit,
            "source": {"kind": "graph", "submission_digest": submission_digest},
            "procedure": {
                "entrypoint": None,
                "configuration": {"training": {"steps": 16, "batch_size": 8}},
                "train_use": {
                    "dataset": direct_graph.TRAIN_USE,
                    "train_fraction": 0.1,
                    "curriculum": "none",
                },
                "initial_state": None,
            },
            "output": {
                "format": direct_graph.OUTPUT_FORMAT,
                "interface_digest": kit["interface_digest"],
            },
        }
    )


def test_the_worker_binds_each_versions_own_kit_and_bounds():
    assert direct_graph_worker.VERSIONS == ("1.0", "2.1")
    assert direct_graph_worker.kit_for(_recipe("1.0")) == (
        construction_kit.construction_kit()
    )
    assert direct_graph_worker.kit_for(_recipe("2.1")) == (
        construction_kit.construction_kit_for("2.1")
    )
    # 2.0 is not served by this worker: bound against 1.0's kit and refused.
    assert direct_graph_worker.kit_for(_recipe("2.0")) == (
        construction_kit.construction_kit()
    )
    assert direct_graph_worker.state_bytes_for("1.0") == MAX_STATE_BYTES
    assert direct_graph_worker.state_bytes_for("2.1") == worker_model.OUTPUT_BYTES
    old = direct_graph_worker.staged_allowlists("1.0")
    assert old == {
        "allowlist_v1.json": (ROOT / "carbon/level4/allowlist_v1.json").read_bytes(),
        "allowlist_v6.json": allowlist_module.served_bytes(),
    }
    new = direct_graph_worker.staged_allowlists("2.1")
    assert new == {**old, "allowlist_v7.json": allowlist_module.v7_bytes()}
    assert direct_graph.submission_bytes("2.1") == (
        intake.CONTAINMENT_BOUNDS["submission_bytes"]
    )


def test_both_programs_stage_v7_only_when_the_host_staged_it():
    for program in (direct_graph_worker.PROGRAM, direct_graph_inference.PROGRAM):
        assert 'if (work / "allowlist_v7.json").exists():' in program


posix = pytest.mark.skipif(
    os.name == "nt", reason="G3 isolated graph parse needs POSIX rlimits"
)


def _graph(version, chain=0):
    """An affine Battery graph under the version's allowlist, with `chain`
    extra negation pairs to make its document large."""
    pytest.importorskip("jax")
    os.environ.setdefault("JAX_PLATFORMS", "cpu")
    import jax.numpy as jnp

    from carbon.level4 import graph, initializers, submission
    from carbon.level4.tooling import through_bprime

    allowed = direct_graph.graph_allowlist(version)
    settings = direct_graph.training_settings(_recipe(version))
    interface = direct_graph.graph_interface(settings)

    def forward(w, b, x):
        y = x @ w + b
        for _ in range(chain):
            y = -y
            y = -y
        return y

    _, document, _ = through_bprime(
        forward,
        (
            jnp.ones((4, 247), jnp.float32),
            jnp.zeros((247,), jnp.float32),
            jnp.ones((8, 4), jnp.float32),
        ),
        role="forward",
        allowlist=allowed,
        input_names=["params/0", "params/1", "inputs/features"],
        max_bytes=intake.bounds_for(allowed)["document_bytes"],
    )
    init_spec = {
        "schema": initializers.SCHEMA,
        "graph": graph.digest(document),
        "parameters": [
            {
                "input": "params/0",
                "initializer": "he_normal",
                "fan_in_axes": [0],
                "fan_out_axes": [1],
            },
            {
                "input": "params/1",
                "initializer": "zeros",
                "fan_in_axes": [],
                "fan_out_axes": [],
            },
        ],
    }
    manifest, files = submission.build(
        challenge=challenge.CHALLENGE.challenge_id,
        interface=interface.digest(),
        allowlist=allowed,
        forward=document,
        init_spec=init_spec,
    )
    return submission.canonical(manifest), files, submission.digest(manifest)


def _envelope(tmp_path, recipe, raw, files):
    from carbon.development_session.construction_recipe import (
        graph_envelope_from_workspace,
    )
    from carbon.development_session.research_ledger import VERSION, CampaignLedger
    from carbon.development_session.research_workspace import ResearchWorkspace
    from carbon.level4 import staging

    ledger = CampaignLedger(tmp_path / "campaign")
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": {},
            "elapsed_seconds": None,
            "campaign_id": "battery-2-1-graph-test",
            "implementation": "fixture",
            "objective": "public TRAIN graph reconstruction test",
            "sampling": "fixture",
            "control": "none",
            "selection": "none",
            "replica_policy": "fixture",
            "provider": "none",
            "owner": "fixture",
        }
    )
    workspace = ResearchWorkspace(ledger, "fixture")
    workspace.put(staging.WORKSPACE_MANIFEST, raw)
    for name, body in files.items():
        workspace.put(staging.WORKSPACE_PREFIX + name[7:] + ".json", body)
    return graph_envelope_from_workspace(ledger, "fixture", recipe)


def _inputs():
    material = challenge.PublicMaterial.load(ROOT)
    return {
        "cases": [
            {
                "case_id": case_id,
                "inputs": dict(zip(challenge.INPUTS, map(float, values))),
            }
            for case_id, values in zip(
                material.train.case_ids[:2], material.train.x[:2]
            )
        ]
    }


def _run(program, files, base):
    work = base / "work"
    work.mkdir(parents=True)
    (base / "output").mkdir()
    for name, body in files.items():
        (work / name).write_bytes(body)
    (work / "program.py").write_text(program)
    result = subprocess.run(
        [sys.executable, "-I", str(work / "program.py")],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    return base / "output"


@posix
def test_a_2_1_graph_builds_and_infers_through_the_worker_under_v7(tmp_path):
    raw, files, submission_digest = _graph("2.1")
    assert json.loads(raw)["allowlist"]["version"] == "level4-allowlist-v7"
    recipe = _recipe("2.1", submission_digest)
    envelope = _envelope(tmp_path, recipe, raw, files)
    inputs = _inputs()
    staged = direct_graph_worker.staged_files(
        ROOT, recipe, envelope, seed=7, test_inputs=inputs
    )
    assert staged["allowlist_v7.json"] == allowlist_module.v7_bytes()
    control = json.loads(staged["control.json"])
    assert control["kit"] == construction_kit.construction_kit_for("2.1")
    assert control["max_state_bytes"] == worker_model.OUTPUT_BYTES
    output = _run(direct_graph_worker.PROGRAM, staged, tmp_path / "build")
    fit = json.loads((output / "fit.json").read_text())
    assert fit["recipe_digest"] == recipe.digest
    assert fit["train_digest"] == control["kit"]["train_digest"]
    state = (output / "state.npz").read_bytes()
    inference_files = direct_graph_inference.staged_files(recipe, state, inputs)
    assert inference_files["allowlist_v7.json"] == allowlist_module.v7_bytes()
    assert "train-v1.jsonl.gz" not in inference_files
    inferred = _run(direct_graph_inference.PROGRAM, inference_files, tmp_path / "infer")
    predictions = json.loads((inferred / "predictions.json").read_text())
    assert set(predictions) == {case["case_id"] for case in inputs["cases"]}

    import hashlib
    import shutil

    snapshot = tmp_path / "operation-test" / "snapshot"
    shutil.copytree(output, snapshot)

    def runner(_ledger, **kwargs):
        kwargs["output_validator"](snapshot)
        return {
            "operation": "operation-test",
            "files": {
                path.name: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                for path in snapshot.iterdir()
            },
        }

    result = direct_graph_worker.reconstruct_public(
        SimpleNamespace(root=tmp_path),
        owner="test",
        identity="test",
        image=object(),
        root=ROOT,
        recipe=recipe,
        source_envelope=envelope,
        seed=7,
        test_inputs=inputs,
        runner=runner,
    )
    assert result.recipe_digest == recipe.digest
    assert result.train_digest == control["kit"]["train_digest"]


@posix
def test_1_0_stages_exactly_what_it_did(tmp_path):
    raw, files, submission_digest = _graph("1.0")
    recipe = _recipe("1.0", submission_digest)
    envelope = _envelope(tmp_path, recipe, raw, files)
    staged = direct_graph_worker.staged_files(
        ROOT, recipe, envelope, seed=7, test_inputs=_inputs()
    )
    documents = {name for name in staged if name.startswith("level4-")}
    assert set(staged) - documents == STAGED_1_0
    control = json.loads(staged["control.json"])
    assert control == {
        "recipe_digest": recipe.digest,
        "settings_digest": control["settings_digest"],
        "kit": construction_kit.construction_kit(),
        "seed": 7,
        "train_cases": challenge.TRAIN_V1_CASES,
        "max_state_bytes": MAX_STATE_BYTES,
    }


@posix
def test_a_2_1_graph_over_4_mib_is_staged_and_1_0_bounds_refuse_it(tmp_path):
    raw, files, submission_digest = _graph("2.1", chain=25_000)
    size = len(raw) + sum(len(name) + len(body) for name, body in files.items())
    assert intake.BOUNDS["submission_bytes"] < size
    recipe = _recipe("2.1", submission_digest)
    envelope = _envelope(tmp_path / "a", recipe, raw, files)
    staged = direct_graph_worker.staged_files(
        ROOT, recipe, envelope, seed=7, test_inputs=_inputs()
    )
    assert "allowlist_v7.json" in staged
    from carbon.development_session.construction_recipe import graph_workspace

    with pytest.raises(RecipeRefused, match="construction_recipe_graph_bytes_invalid"):
        graph_workspace(
            recipe, raw, files, max_bytes=direct_graph.submission_bytes("1.0")
        )
