"""Battery Level 2 v2: `training_data.pool_selection` (BATTERY-L2-POOL-SELECTION-01).

Claims tested:
- v2 is the current Level 2 variant, recorded, built from the code, a
  superset of v1, which stays registered and byte for byte unchanged;
- pool v1 is TRAIN v1 only, its committed manifest is the builder's, and
  PRACTICE is refused by name;
- every malformed selection is refused, typed, before anything trains;
- the draw is Carbon's, from the recipe alone: deterministic, inside the box,
  sized exactly, with no case named by the recipe;
- a recipe without a selection is Level 0 byte for byte; a selection alone
  keeps Level 0's trainer and stages only the restriction; with SpecMuon both
  apply;
- the staged program and the in-process rebuild train on the drawn subset,
  and a rebuild repeats.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("jax")

from carbon.battery import challenge, development_rebuild, level2, level2_worker, pools
from carbon.battery.worker import DirectBackend
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import development_variants as dv
from carbon.reconstruction.challenge_contracts import (
    SubmissionRefused,
    compile_submission,
)

REPOSITORY = Path(__file__).resolve().parents[2]
BATTERY = cr.BATTERY_CHALLENGE
MLP = {"width": 16, "depth": 1, "steps": 32}
(POOL_V1,) = pools.registered()


def selection(**changes):
    return {
        "pool_version": POOL_V1,
        "strata": {"train": 1.0},
        "box": {"t_amb_c": [10.0, 35.0]},
        "cases": 120,
        **changes,
    }


def strategy(backbone="mlp", **parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": backbone,
        "parameters": {**MLP, **parameters},
    }


def compiled(**parameters):
    return dv.compile_development(strategy(**parameters), dv.variant(BATTERY, 2))


def issues(**parameters):
    with pytest.raises(dv.VariantRefused) as refused:
        compiled(**parameters)
    return [code for code, _path in refused.value.issues]


@pytest.fixture(scope="module")
def train():
    return challenge.PublicMaterial.load().train


# -- the variant -----------------------------------------------------------------------
def test_v2_is_current_recorded_and_a_superset_of_v1():
    found = dv.variant(BATTERY, 2)
    assert found.version == level2.VERSION == "battery-l2-v2"
    base = {
        "digest": found.base_contract_digest,
        "record_sequence": found.base_record_sequence,
    }
    assert found.document() == level2.variant_document(base=base)
    assert dv.newest_record(found, None, None) is not None
    assert found.permissions() == (level2.SPECTRAL, level2.POOL)
    v1 = level2.variant_document(level2.VERSION_V1, base=base)
    pinned = json.loads((Path(dv.SHIPPED_DIR) / "registry.json").read_text())
    assert dv.digest_of(v1) == pinned["versions"][level2.VERSION_V1]
    assert v1["widened"] == found.document()["widened"][:1]


def test_miner_surfaces_never_resolve_a_pool_selection():
    with pytest.raises(SubmissionRefused):
        compile_submission(strategy(pool_selection=selection()))


# -- the pool --------------------------------------------------------------------------
def test_pool_v1_is_train_v1_only_and_its_manifest_is_the_builders(train):
    (manifest,) = pools.registered().values()
    assert manifest == pools.manifest_v1(train)
    assert [p["part"] for p in manifest["parts"]] == ["train"]
    assert manifest["parts"][0]["cases"] == len(train.case_ids) == 400
    path = pools.POOLS_DIR / "public-pool-v1.json"
    assert path.read_text() == json.dumps(manifest, indent=1, sort_keys=True) + "\n"


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"strata": {"practice": 1.0}}, "pool.practice_refused"),
        ({"strata": {"train": 1.0, "practice": 0.5}}, "pool.practice_refused"),
        ({"strata": {"bank": 1.0}}, "pool.part_not_in_version"),
        ({"strata": {"train": 2.5}}, "pool.weight_out_of_bounds"),
        ({"strata": {"train": -0.1}}, "pool.weight_out_of_bounds"),
        ({"strata": {"train": True}}, "pool.weight_out_of_bounds"),
        ({"strata": {"train": 0.0}}, "pool.weights_all_zero"),
        ({"strata": {}}, "pool.strata_malformed"),
        ({"box": {"seed": [0, 1]}}, "pool.box_unknown_input"),
        ({"box": {"c1": [2.0, 1.0]}}, "pool.box_malformed"),
        ({"box": {"c1": [0.0, float("inf")]}}, "pool.box_malformed"),
        ({"cases": 0}, "pool.cases_out_of_bounds"),
        ({"cases": 401}, "pool.cases_out_of_bounds"),
        ({"cases": 12.0}, "pool.cases_out_of_bounds"),
        ({"pool_version": "sha256:" + "0" * 64}, "pool.version_unregistered"),
        ({"case_ids": ["train-0001"]}, "pool.selection_malformed"),
        ({"cases": 399, "box": {"t_amb_c": [10.0, 11.0]}}, "pool.box_too_narrow"),
    ],
)
def test_a_malformed_selection_is_refused_typed(change, code):
    assert code in issues(pool_selection=selection(**change))


def test_a_selection_missing_a_field_is_refused():
    for name in ("pool_version", "strata", "cases"):
        value = {k: v for k, v in selection().items() if k != name}
        assert "pool.selection_missing" in issues(pool_selection=value)


# -- the draw --------------------------------------------------------------------------
def test_the_draw_is_deterministic_sized_and_inside_the_box(train):
    a = pools.draw(selection(), {"train": train})
    b = pools.draw(selection(), {"train": train})
    assert a == b and len(a) == 120 == len(set(a))
    picked = pools.subset(train, a)
    assert ((picked.x[:, 2] >= 10.0) & (picked.x[:, 2] <= 35.0)).all()
    other = pools.draw(selection(cases=121), {"train": train})
    assert other != a  # the recipe is the seed


def test_the_allocation_sums_to_cases():
    counts = pools._allocation({"train": 1.0, "bank": 2.0}, 100)
    assert counts == {"bank": 67, "train": 33}
    assert sum(pools._allocation({"a": 0.3, "b": 0.3, "c": 0.4}, 7).values()) == 7


# -- rebuild ---------------------------------------------------------------------------
def test_no_selection_is_level_0_byte_for_byte():
    from carbon.challenge_validator import scoring as challenge_scoring

    scoring = challenge_scoring.scoring_for(BATTERY)
    found = compiled()
    assert level2_worker.level2_record(found.reconstruction) is None
    level0, _f0, program0 = scoring.built_from(
        compile_submission(strategy()), 7, REPOSITORY
    )
    built, _f, program = scoring.built_from(found, 7, REPOSITORY)
    assert program == program0 and built["staged"] == level0["staged"]


def test_a_selection_alone_keeps_level_0s_trainer_and_stages_the_restriction():
    found = compiled(pool_selection=selection())
    record = development_rebuild.record(found.reconstruction)
    assert development_rebuild.kind(record) == development_rebuild.LEVEL2
    assert record["schema"] == level2_worker.SCHEMA_V2 and record["spectral"] is None
    assert record["pool"]["cases"] == 120 == len(record["pool"]["case_ids"])
    from carbon.battery.worker import RECONSTRUCT_PROGRAM

    program, files, trainer = development_rebuild.stage(
        record, RECONSTRUCT_PROGRAM, {}, level1_program=lambda: 1 / 0
    )
    assert trainer == development_rebuild.LEVEL2
    assert 'model = recipes.build(recipe["family"], recipe["settings"])' in program
    assert "battery-pool-selection.json" in program
    assert set(files) == {level2_worker.POOL_FILE}


def test_with_specmuon_both_apply():
    found = compiled(
        optimizer_family="muon", muon_spectral=True, pool_selection=selection()
    )
    record = development_rebuild.record(found.reconstruction)
    assert record["spectral"]["interpretation"] == "specmuon-carbon-v1"
    from carbon.battery.worker import RECONSTRUCT_PROGRAM

    program, files, _ = development_rebuild.stage(
        record, RECONSTRUCT_PROGRAM, {}, level1_program=lambda: 1 / 0
    )
    assert (
        "level2_training.build" in program and "battery-pool-selection.json" in program
    )
    assert set(level2_worker.STAGED_MODULES) | {level2_worker.POOL_FILE} == set(files)


@pytest.mark.parametrize("backbone", ["knn", "deeponet"])
def test_every_family_may_select(backbone):
    parameters = {} if backbone == "knn" else {"deeponet_depth": 1}
    found = dv.compile_development(
        {
            "schema_version": "1.0",
            "challenge_id": BATTERY,
            "backbone": backbone,
            "parameters": {**parameters, "pool_selection": selection()},
        },
        dv.variant(BATTERY, 2),
    )
    assert development_rebuild.record(found.reconstruction) is not None


def test_the_in_process_rebuild_trains_on_the_subset_and_repeats():
    backend = DirectBackend(REPOSITORY)
    found = compiled(pool_selection=selection())
    record = development_rebuild.record(found.reconstruction)
    first = backend.reconstruct(None, found.construction, 7, record)
    second = backend.reconstruct(None, found.construction, 7, record)
    level0 = backend.reconstruct(None, compiled().construction, 7, None)
    assert first[0] == second[0] and first[0] != level0[0]
    assert first[1]["trainer"] == "level2"


def test_the_staged_program_trains_on_exactly_the_subset(tmp_path):
    from carbon.battery.worker import RECONSTRUCT_PROGRAM, reconstruct_files

    found = compiled(pool_selection=selection())
    record = development_rebuild.record(found.reconstruction)
    program, files, _ = development_rebuild.stage(
        record,
        RECONSTRUCT_PROGRAM,
        reconstruct_files(REPOSITORY, found.construction, 7),
        level1_program=lambda: 1 / 0,
    )
    work, out = tmp_path / "work", tmp_path / "output"
    work.mkdir()
    out.mkdir()
    for name, body in files.items():
        (work / name).write_bytes(body)
    (work / "program.py").write_text(
        program.replace(
            '    stats = model.fit(train, structure, recipe["seed"])\n',
            "    (out / 'n.txt').write_text(str(len(train.case_ids)))\n"
            '    stats = model.fit(train, structure, recipe["seed"])\n',
        )
    )
    subprocess.run(
        [sys.executable, "program.py"],
        cwd=work,
        env={
            "PYTHONPATH": str(REPOSITORY),
            "JAX_PLATFORMS": "cpu",
            "PATH": "/usr/bin:/bin",
        },
        check=True,
        timeout=900,
    )
    assert (out / "n.txt").read_text() == "120"
    assert (out / "fit.json").exists()
