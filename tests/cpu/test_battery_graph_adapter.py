"""Battery's graph training adapter (the Validator's ruling (a), 2026-10-22):
Battery 2.2 takes graph recipes through the receiver's one graph path, on 2.1's
graph route. The ruling's conditions, each tested here:

- 2.2's graph TRAIN is 2.1's float64 TRAIN, by digest;
- the v7 allowlist with 2.1's graph limits;
- parity: a graph recipe practised through the old 2.1 local path
  (`battery.direct_graph_worker` + `direct_graph_inference`) and through the
  new adapter gives byte-identical predictions and dev grades;
- sealed: a graph-built model is graded by the 2.2 sealed adapter as a catalog
  one is (from its output rows);
- F08/F02's trainer and producer digests and the pinned Battery modules are
  unchanged.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from test_battery_direct_graph_v21 import _envelope, _graph, _recipe, _run

from carbon import research
from carbon.battery import (
    catalog_version,
    construction_kit,
    direct_graph,
    direct_graph_inference,
    direct_graph_worker,
)
from carbon.battery import construction_bundle_material as cbm
from carbon.development_session import battery_graph_adapter as adapter
from carbon.development_session import (
    build_refusal,
    direct_graph_construction_worker,
    graph_adapters,
    physical_graph_adapter,
)
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.level4 import allowlist as allowlist_module

ROOT = Path(__file__).resolve().parents[2]
BATTERY = "battery-fastcharge-ageing-development-v1"
KEY = (BATTERY, "2.2")
TRAIN_SHA256 = "3a7c763cca272df729268759e3062abd79e104a5c527c17314aef663944cf0e3"
#: F08/F02's pinned trainer, unchanged by Battery's adapter.
F08_F02_TRAINER = "3e97569bafd4b2f25312c8e1c01aa3fe5e581af94d2802a85ce17b29b62db7e5"
posix = pytest.mark.skipif(os.name == "nt", reason="G3 parser needs POSIX rlimits")


def _material():
    return cbm.versioned_material("2.2")


def _binding(material):
    kit = material["construction_kit"]
    return {
        "challenge_id": kit["id"],
        "challenge_version": kit["version"],
        "train_digest": kit["train_digest"],
        "interface_digest": kit["interface_digest"],
        "construction_limits_digest": kit["construction_limits_digest"],
    }


def _rekey(recipe, kit):
    doc = recipe.to_dict()
    return ConstructionRecipe.from_dict(
        {
            **doc,
            "challenge": kit,
            "output": {**doc["output"], "interface_digest": kit["interface_digest"]},
        }
    )


# --- registration and the ruling's identity conditions ----------------------------

#: Battery 2.2 is not served (OWNER-BATTERY-OUT-OF-LAUNCH-01: Battery is out of
#: launch, and 2.2 was never completed): these tests describe its graph
#: adapter as served, and come back if 2.2 is registered again.
NOT_SERVED = pytest.mark.skip(
    reason="Battery 2.2 is not served (OWNER-BATTERY-OUT-OF-LAUNCH-01)"
)


@NOT_SERVED
def test_2_2_registers_the_battery_adapter_on_2_1s_graph_route():
    material = _material()
    block = material["construction_limits_document"]["graph_training_adapter"]
    assert block == adapter.adapter_block(*KEY)
    assert block["base_version"] == "2.1"
    assert block["base_kit"] == construction_kit.construction_kit_for("2.1")
    # TRAIN: 2.1's float64 gzip-JSON-lines TRAIN, by digest.
    assert block["train_sha256"] == "sha256:" + TRAIN_SHA256
    assert material["construction_kit"]["train_digest"] == "sha256:" + TRAIN_SHA256
    assert construction_kit.construction_kit_for("2.1")["train_digest"] == (
        "sha256:" + TRAIN_SHA256
    )
    assert block["interface"]["output_dtype"] == "float64"
    # The v7 allowlist and 2.1's graph limits.
    assert adapter.served_allowlist_bytes(*KEY) == allowlist_module.v7_bytes()
    assert direct_graph.graph_allowlist("2.1").digest == (
        allowlist_module.Allowlist(allowlist_module.v7_bytes()).digest
    )
    limits = construction_kit.construction_limits_document_for("2.1")
    for name in ("train_surfaces", "graph_caps", "graph_intake", "training_limit"):
        assert block["graph_limits"][name] == limits[name]
    # Battery's training code is named by its exact bytes.
    for module, sha in block["trainer"]["modules"].items():
        raw = (ROOT / "carbon" / "battery" / module).read_bytes()
        assert sha == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert set(block["trainer"]["modules"]) == set(
        direct_graph_worker.BATTERY_MODULES.values()
    )
    assert adapter.BUILD_MODULES == (
        *direct_graph_worker.STAGED_MODULES,
        "carbon.development_session.build_refusal",
    )


def test_the_registry_serves_battery_2_2_and_leaves_f08_f02_alone():
    assert graph_adapters.for_version(*KEY) is adapter
    assert graph_adapters.for_version(BATTERY, "2.1") is None
    assert graph_adapters.for_version("f08-ribbed-bracket", "1.4") is (
        physical_graph_adapter
    )
    assert graph_adapters.registered_train_use(*KEY) == direct_graph.TRAIN_USE
    assert direct_graph_construction_worker.graph_adapter_ids() == {
        direct_graph_construction_worker.SYNTHETIC_ADAPTER_ID,
        *physical_graph_adapter.ADAPTER_IDS,
        *adapter.ADAPTER_IDS,
    }
    assert physical_graph_adapter.TRAINER_SHA256 == F08_F02_TRAINER
    assert BATTERY not in physical_graph_adapter.PREFIXES


def _discovery(key, limits):
    return SimpleNamespace(
        info=SimpleNamespace(challenge_key=key),
        _checked=lambda selected: None,
        _material={"construction_limits_document": limits},
    )


@NOT_SERVED
def test_the_receiver_selects_the_adapter_only_on_its_served_block():
    from carbon.development_session.research_service import DirectFixtureDiscovery

    select = DirectFixtureDiscovery.graph_adapter_for
    key = research.ChallengeKey(*KEY)
    limits = _material()["construction_limits_document"]
    assert select(_discovery(key, limits), key) == adapter.SPECS[KEY].adapter_id
    altered = json.loads(json.dumps(limits))
    altered["graph_training_adapter"]["trainer"]["modules"]["training.py"] = (
        "sha256:" + "1" * 64
    )
    assert select(_discovery(key, altered), key) is None
    other = research.ChallengeKey(BATTERY, "2.1")
    assert select(_discovery(other, limits), other) is None


@NOT_SERVED
def test_the_build_stage_refuses_off_its_served_identity():
    material = _material()
    binding = _binding(material)
    limits = material["construction_limits_document"]
    recipe = _rekey(_recipe("2.1"), material["construction_kit"])
    spec, files = adapter.build_stage(
        binding, limits, allowlist_module.v7_bytes(), recipe
    )
    assert spec is adapter.SPECS[KEY]
    assert files["base-recipe.json"] == _recipe("2.1").canonical_bytes
    assert "train-v1.jsonl.gz" not in files and "train.npz" not in files
    control = json.loads(files["battery-control.json"])
    assert control["refusal"] is None and control["base_kit"]["version"] == "2.1"
    with pytest.raises(RecipeRefused, match="direct_graph_allowlist_unregistered"):
        adapter.build_stage(binding, limits, allowlist_module.served_bytes(), recipe)
    altered = json.loads(json.dumps(limits))
    altered["graph_training_adapter"]["id"] = "another"
    with pytest.raises(RecipeRefused, match="direct_graph_adapter_identity_invalid"):
        adapter.build_stage(binding, altered, allowlist_module.v7_bytes(), recipe)


@NOT_SERVED
def test_a_2_2_recipe_is_2_1s_recipe_re_keyed():
    material = _material()
    old = _recipe("2.1")
    new = _rekey(old, material["construction_kit"])
    assert adapter.base_recipe(new).digest == old.digest
    assert adapter.training_settings(new) == direct_graph.training_settings(old)
    with pytest.raises(RecipeRefused, match="challenge_version_unregistered"):
        adapter.spec_for(BATTERY, "2.1")


def test_every_battery_graph_refusal_has_its_class():
    for code in (
        "battery_graph_training_value_invalid",
        "battery_graph_training_field_invalid",
        "battery_graph_procedure_invalid",
        "battery_graph_output_unsupported",
        "battery_graph_nonfinite_state",
    ):
        assert build_refusal.outcome(code) == build_refusal.REFUSED
    for code in (
        "battery_graph_backend_unsupported",
        "battery_graph_ensemble_unsupported",
    ):
        assert build_refusal.outcome(code) == build_refusal.GAP


# --- the build and inference children (JAX; local runner) --------------------------


def _local_runner():
    count = itertools.count()

    def runner(ledger, *, source, files, output_validator, **_kwargs):
        name = f"operation-{next(count):064x}"
        home = ledger.root / name
        work = home / "workspace"
        work.mkdir(parents=True)
        (home / "output").mkdir()
        for filename, body in files.items():
            (work / filename).write_bytes(body)
        done = subprocess.run(
            [sys.executable, "-c", source],
            cwd=work,
            env={**os.environ, "JAX_PLATFORMS": "cpu"},
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
        assert done.returncode == 0, done.stderr[-4000:]
        snapshot = home / "snapshot"
        (home / "output").rename(snapshot)
        output_validator(snapshot)
        return {
            "operation": name,
            "files": {
                path.name: "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                for path in snapshot.iterdir()
            },
        }

    return runner


def _image():
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    return WorkerImageIdentity(*(("sha256:" + "a" * 64,) * 8))


def _receiver(tmp_path, recipe, envelope, inputs, *, material=None):
    material = material or _material()
    return direct_graph_construction_worker.reconstruct_and_infer_graph_public(
        SimpleNamespace(root=tmp_path),
        owner="test",
        identity="test",
        image=_image(),
        recipe=recipe,
        challenge_binding=_binding(material),
        limits_document=material["construction_limits_document"],
        source_envelope=envelope,
        train=material["train"],
        inputs=np.ascontiguousarray(inputs),
        expected_output_shape=(len(inputs), 247),
        allowlist_bytes=material["allowlist_bytes"],
        seed=0,
        runner=_local_runner(),
        adapter_id=adapter.SPECS[KEY].adapter_id,
    )


def _old_path(tmp_path, recipe, envelope, case_ids, inputs):
    """The old 2.1 local path: Battery's own build and inference programs."""
    from carbon.battery import challenge

    test_inputs = {
        "cases": [
            {"case_id": case, "inputs": dict(zip(challenge.INPUTS, map(float, row)))}
            for case, row in zip(case_ids, inputs, strict=True)
        ]
    }
    staged = direct_graph_worker.staged_files(
        ROOT, recipe, envelope, seed=0, test_inputs=test_inputs
    )
    built = _run(direct_graph_worker.PROGRAM, staged, tmp_path / "old-build")
    state = (built / "state.npz").read_bytes()
    files = direct_graph_inference.staged_files(recipe, state, test_inputs)
    inferred = _run(direct_graph_inference.PROGRAM, files, tmp_path / "old-infer")
    predictions = json.loads((inferred / "predictions.json").read_text())
    return np.asarray(
        [
            [
                *predictions[case]["voltage_v"],
                *predictions[case]["temperature_c"],
                predictions[case]["plating_margin_v"],
                *predictions[case]["capacity_ah"],
            ]
            for case in case_ids
        ],
        dtype=np.float64,
    )


@NOT_SERVED
@posix
def test_parity_the_old_2_1_path_and_the_adapter_grade_identically(tmp_path):
    material = _material()
    raw, files, submission_digest = _graph("2.1")
    old = _recipe("2.1", submission_digest)
    new = _rekey(old, material["construction_kit"])
    envelope = _envelope(tmp_path, old, raw, files)
    inputs = material["practice_inputs"]
    result = _receiver(tmp_path / "new", new, envelope, inputs)
    assert result.execution_boundary == "TEST_ONLY_LOCAL_RUNNER"
    assert result.build.receipt["train_digest"] == "sha256:" + TRAIN_SHA256
    rows = np.asarray(result.inference.predictions, dtype=np.float64)
    reference = _old_path(
        tmp_path, old, envelope, material["practice_case_ids"], inputs
    )
    # Byte-identical predictions, so byte-identical dev grades.
    assert rows.tobytes() == reference.tobytes()
    assert catalog_version.practice_summary("2.2", rows.tolist(), material) == (
        catalog_version.practice_summary("2.2", reference.tolist(), material)
    )
    adapter.check_state(result.build.state_path.read_bytes(), new)


@NOT_SERVED
@posix
def test_a_settings_refusal_is_settled_in_the_build_child_by_its_class(tmp_path):
    material = _material()
    raw, files, submission_digest = _graph("2.1")
    envelope = _envelope(tmp_path, _recipe("2.1", submission_digest), raw, files)
    for index, (training, state, detail) in enumerate(
        (
            ({"steps": 1}, "REFUSED", "battery_graph_training_value_invalid"),
            ({"backend": "pytorch"}, "UNRESOLVED", "battery_graph_backend_unsupported"),
        )
    ):
        doc = _rekey(
            _recipe("2.1", submission_digest), material["construction_kit"]
        ).to_dict()
        doc["procedure"]["configuration"]["training"].update(training)
        recipe = ConstructionRecipe.from_dict(doc)
        with pytest.raises(
            direct_graph_construction_worker.GraphConstructionDecision
        ) as caught:
            direct_graph_construction_worker.reconstruct_public_graph(
                SimpleNamespace(root=tmp_path / str(index)),
                owner="test",
                identity="test",
                image=_image(),
                recipe=recipe,
                challenge_binding=_binding(material),
                limits_document=material["construction_limits_document"],
                source_envelope=envelope,
                train=material["train"],
                allowlist_bytes=material["allowlist_bytes"],
                seed=0,
                seconds=600,
                runner=_local_runner(),
                adapter_id=adapter.SPECS[KEY].adapter_id,
            )
        assert (caught.value.state, caught.value.detail_code) == (state, detail)


@NOT_SERVED
@posix
def test_sealed_a_graph_built_model_is_graded_by_the_2_2_sealed_adapter(tmp_path):
    from test_battery_sealed_grading import _bank, _definition, _rows

    from carbon.scoring import battery_sealed_dual_pack as sealed

    assert sealed.adapter("2.2") is not None
    material = _material()
    raw, files, submission_digest = _graph("2.1")
    old = _recipe("2.1", submission_digest)
    new = _rekey(old, material["construction_kit"])
    envelope = _envelope(tmp_path, old, raw, files)
    inputs = np.asarray(_bank()["inputs"], dtype=np.float64)
    result = _receiver(tmp_path / "sealed", new, envelope, inputs)
    outputs = [list(map(float, row)) for row in result.inference.predictions]
    measured = sealed.measure(
        bank_rows=_rows(),
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=_definition(),
        limits={},
        objective={},
        train_raw=b"",
        names=sealed.input_names(),
    )
    # Graded as any model's rows are, a catalog one's included: the same
    # legs, gates and decision value as a model equal to the references.
    from test_battery_sealed_grading import _measure, _truth

    exact = _measure(_truth())
    assert set(measured) == set(exact)
    assert set(measured["gates"]) == set(exact["gates"])
    for leg in ("A", "D"):
        assert measured[leg] is None or 0.0 <= measured[leg] <= 1.0
