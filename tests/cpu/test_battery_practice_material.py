"""Battery public practice material: pinned, disjoint, label-free for the worker."""

import gzip
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.battery.challenge import INPUTS, MaterialMismatch, PublicMaterial
from carbon.battery.practice import (
    PRACTICE_CASES,
    STAGED_MODULES,
    PracticeSet,
    staged_files,
)
from carbon.battery.research import BatteryPublicMaterial

REPOSITORY = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def practice():
    return PracticeSet.load(REPOSITORY)


def test_practice_is_pinned_and_disjoint_from_train(practice):
    train = PublicMaterial.load(REPOSITORY).train
    assert len(practice.records) == PRACTICE_CASES
    assert not set(practice.case_ids) & set(train.case_ids)
    train_inputs = {tuple(row) for row in train.x.round(4).tolist()}
    practice_inputs = {
        tuple(round(r["inputs"][k], 4) for k in INPUTS) for r in practice.records
    }
    assert not train_inputs & practice_inputs


def test_a_changed_source_is_refused(tmp_path, practice):
    from carbon.battery.practice import PRACTICE_SOURCE_PATH

    target = tmp_path / PRACTICE_SOURCE_PATH
    target.parent.mkdir(parents=True)
    target.write_bytes(b"{}\n")
    with pytest.raises(MaterialMismatch):
        PracticeSet.load(tmp_path)


def test_the_worker_gets_inputs_and_exact_code_never_labels(practice):
    from carbon.battery.compile import compile_recipe

    _, recipe = compile_recipe(
        {
            "schema_version": "1.0",
            "challenge_id": "battery-fastcharge-ageing-development-v1",
            "backbone": "knn",
            "parameters": {"neighbours": 4},
        }
    )
    files = staged_files(REPOSITORY, practice, recipe, 7)
    import carbon.battery

    here = Path(carbon.battery.__file__).parent
    for staged, module in STAGED_MODULES.items():
        assert files[staged] == (here / module).read_bytes()
    document = json.loads(files["practice-inputs.json"])
    assert {k for case in document["cases"] for k in case} == {"case_id", "inputs"}
    assert json.loads(files["recipe.json"])["seed"] == 7
    assert set(files) == {
        *STAGED_MODULES,
        "train-v1.jsonl.gz",
        "ocv-table.json",
        "practice-inputs.json",
        "recipe.json",
    }


def test_public_material_is_an_allow_list(practice):
    stored = {}
    workspace = SimpleNamespace(put=lambda name, body: stored.__setitem__(name, body))
    material = BatteryPublicMaterial(REPOSITORY)
    result = material("practice_data", workspace)
    body = stored["battery-practice-v1.jsonl.gz"]
    assert body == practice.public_bytes()  # deterministic
    rows = [json.loads(line) for line in gzip.decompress(body).splitlines()]
    assert len(rows) == result["cases"] == PRACTICE_CASES
    for name in ("final_data", "../secrets", "private_pool", "reference_solve"):
        with pytest.raises(ValueError):
            material(name, workspace)
