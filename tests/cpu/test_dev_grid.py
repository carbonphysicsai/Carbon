"""Dev-pack v2 (Validator 2026-10-23), new versions only: the graph-route-v2 versions'
development pack is the practice grid with public probes, graded by the sealed v2 grader
under ``<kind>-dual-development-grid-v2``. Existing versions are untouched."""

from __future__ import annotations

import json

import pytest

from carbon.challenge_kit import physical_material, physical_pack, version_registry
from carbon.scoring import dev_grid, practice_grid
from carbon.scoring import physical_dual_pack as physical

KEYS = sorted(dev_grid.GRID_KINDS)
#: The kits of the dev-grid versions before dev-pack v2 (rc6 a454e75e5). A recipe or
#: calibration artifact bound to them stays valid only while these do not move.
KITS = {
    ("f08-ribbed-bracket", "1.5"): {
        "construction_limits_digest": "sha256:0efc4dcda08c571215898b60478a6c4878f2fc1f2ce1afffbdb298ccf532f62f",
        "id": "f08-ribbed-bracket",
        "interface_digest": "sha256:42e64c6800368f2b364bbc6e70e34814401e3e38b6a9ff7dcfec70c7b1818eba",
        "train_digest": "sha256:4b28e7490eca34061da1431c6379f0f2e5766ff41aedba968eba41ba84fefe0a",
        "version": "1.5",
    },
    ("f02", "2.4"): {
        "construction_limits_digest": "sha256:556d0c14c4111ed7604dd9f44e17c999913fa1f2232b967f300a7c21ac37eaf9",
        "id": "f02",
        "interface_digest": "sha256:3a9c2f8bd2fdaeeca65e060d32f17a60cba06c16b837d6be185a95cdfa9e011e",
        "train_digest": "sha256:1201ec5461bfc08ad2ae4522eafc147282f4167e4bb222ed4e798284faa9a4c3",
        "version": "2.4",
    },
}  # fmt: skip


@pytest.mark.parametrize("key", KEYS)
def test_the_kit_does_not_move_so_a_bound_recipe_or_artifact_stays_valid(key):
    assert physical_material.construction_kit(*key) == KITS[key]


@pytest.mark.parametrize("key", KEYS)
def test_a_dev_grid_version_registers_its_own_development_evaluation(key):
    entry = version_registry.entry(*key)
    kind = dev_grid.kind(*key)
    assert entry.development_evaluation[0] == f"{kind}-dual-development-grid-v2"
    variant = dev_grid.adapter(*key)
    assert variant.EVALUATION_VERSION == entry.development_evaluation[0]
    assert variant.VERSION == key[1]
    # the sealed grader's own evaluation version is unchanged and different
    assert practice_grid.adapter(kind, key[1]).EVALUATION_VERSION != (
        variant.EVALUATION_VERSION
    )


@pytest.mark.parametrize("key", KEYS)
def test_the_development_bank_is_the_practice_grid_with_interleaved_probes(key):
    bank = physical_pack.development_bank(*key)
    grid = practice_grid.practice_bank(dev_grid.kind(*key), key[1])
    assert tuple(bank["case_ids"]) == tuple(grid["case_ids"])
    cohorts = list(bank["cohorts"])
    assert cohorts.count("probe_response") > 0
    assert cohorts.count("decision_sealed_grid") == 8
    last_cell = max(i for i, c in enumerate(cohorts) if c != "probe_response")
    assert "probe_response" in cohorts[:last_cell]  # interleaved, never a suffix
    # the construction material's practice query is this bank
    material = physical_material.bundle_material(*key)
    assert len(material["practice_inputs"]) == len(bank["case_ids"])


def test_existing_versions_keep_their_banks_and_adapters():
    for key in (("f08-ribbed-bracket", "1.4"), ("f02", "2.3")):
        assert dev_grid.kind(*key) is None
        assert dev_grid.adapter(*key) is None
        legacy = physical_pack.legacy_development_bank(*key)
        assert physical_pack.development_bank(*key) is not None
        assert tuple(physical_pack.development_bank(*key)["case_ids"]) == tuple(
            legacy["case_ids"]
        )


@pytest.mark.parametrize("key", KEYS)
def test_the_development_pack_writes_and_grades_with_the_sealed_rule(key, tmp_path):
    kind = dev_grid.kind(*key)
    variant = dev_grid.adapter(*key)
    manifest = variant.write_development_pack(
        tmp_path / "pack", inference_image_id="sha256:" + "a" * 64
    )
    assert manifest.is_file()
    draft = json.loads(manifest.read_bytes())
    path = tmp_path / "pack" / draft["public"]["accuracy_definition"]["path"]
    definition = json.loads(path.read_bytes())
    assert "critical" in definition and "physics" in definition
    # the same totals as the practice (= exam) grader on the same bank and outputs
    bank = physical_pack.development_bank(*key)
    names = practice_grid.input_names(kind, key[1])
    rows = physical.bank_rows(bank, names)
    public = physical_pack.public_roles(*key)
    import numpy as np

    model_inputs = np.asarray(bank["inputs"], float)
    outputs = [
        [float(v) for v in (r["reference"] if r["reference"] is not None else [0.0])]
        for r in rows
    ]
    mean = np.mean(
        [o for r, o in zip(rows, outputs, strict=True) if r["reference"]], axis=0
    )
    outputs = [
        list(map(float, mean)) if r["reference"] is None else o
        for r, o in zip(rows, outputs, strict=True)
    ]
    assert len(model_inputs) == len(outputs)
    sealed = practice_grid.adapter(kind, key[1])
    args = {
        "bank_rows": rows,
        "outputs": outputs,
        "repeats": [outputs, outputs],
        "limits": json.loads(public["important_limit_definition"]),
        "objective": json.loads(public["design_objective"]),
        "train_raw": public["train"],
        "names": names,
    }
    dev = variant.measure(
        definition=variant.definition(bank=bank, train_raw=public["train"]), **args
    )
    exam = sealed.measure(
        definition=sealed.definition(bank=bank, train_raw=public["train"]), **args
    )
    # one code path: the dev pack's grade is the sealed grader's on the same bank
    assert dev == exam
    assert dev["A_legs"] is not None and set(dev["A_legs"]) == {
        "A_acc",
        "A_robust",
        "A_law",
        "A_response",
    }
