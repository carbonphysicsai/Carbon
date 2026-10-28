"""Dev-pack v2 (Validator 2026-10-23), new versions only: the graph-route-v2 versions'
development pack is the practice grid with public probes, graded by the sealed v2 grader
under ``<kind>-dual-development-grid-v2``. Existing versions are untouched."""

from __future__ import annotations

import json

import pytest
import rc43_surfaces

from carbon.challenge_kit import physical_material, physical_pack, version_registry
from carbon.scoring import dev_grid, practice_grid
from carbon.scoring import physical_dual_pack as physical

KEYS = sorted(dev_grid.GRID_KINDS)
MOTOR = "electric-motor-magnetics"
#: The kits of the dev-grid versions on rc9 (rc8 + the 1800 s rebuild wall, OWNER-SANDBOX-REBUILD-WALL-01; new
#: versions, pre-publish, dev-pack v2: the wall moves only the two wall fields,
#: tests/cpu/test_v2_rebuild_wall.py), before and after dev-pack v2 alike. A recipe or
#: calibration artifact bound to them stays valid only while these do not move.
KITS = {
    ("f08-ribbed-bracket", "1.5"): {
        "construction_limits_digest": "sha256:c50a11fd96f410b633ddf9440b760667a8da5dc2ad38808986dadf14d2e22afc",
        "id": "f08-ribbed-bracket",
        "interface_digest": "sha256:42e64c6800368f2b364bbc6e70e34814401e3e38b6a9ff7dcfec70c7b1818eba",
        "train_digest": "sha256:4b28e7490eca34061da1431c6379f0f2e5766ff41aedba968eba41ba84fefe0a",
        "version": "1.5",
    },
    ("f02", "2.4"): {
        "construction_limits_digest": "sha256:eec25b85d0cd31b5b35db0eb6441cb8428b2c2f874de7c9c6512c16807071dfa",
        "id": "f02",
        "interface_digest": "sha256:3a9c2f8bd2fdaeeca65e060d32f17a60cba06c16b837d6be185a95cdfa9e011e",
        "train_digest": "sha256:1201ec5461bfc08ad2ae4522eafc147282f4167e4bb222ed4e798284faa9a4c3",
        "version": "2.4",
    },
    ("electric-motor-magnetics", "1.4"): {
        "construction_limits_digest": "sha256:a6c1c9f13bed863ae427caaf6898c311dbda59f4f654184fea87c2ce8f37a40d",
        "id": "electric-motor-magnetics",
        "interface_digest": "sha256:e257628ce8fc935e42f495cf185facc19bbf93947f00a8766d232f155d896399",
        "train_digest": "sha256:5d27220b8b0c0ccddd013299183118cdce61f205057fe99bceb95c1f52173361",
        "version": "1.4",
    },
    ("chip-cold-plate", "1.4"): {
        "construction_limits_digest": "sha256:afd16c41239081cef4a4447b6fc725d3506c72fb489ad79b13ffe0c7a7c930a0",
        "id": "chip-cold-plate",
        "interface_digest": "sha256:cb1d7820bf1708920b0bd5e313f52d685047469d2e8e60f3ad2f2ed0f1d1298e",
        "train_digest": "sha256:2df26b41a2fdba6a6a64921a9d8c357370374d43d313840ea6e8a371920641d0",
        "version": "1.4",
    },
    # the pool-graded versions (M2/M3; new, pre-publish): the predecessor's kit by its own train and interface
    ("f08-ribbed-bracket", "1.6"): {
        "construction_limits_digest": "sha256:44a9dbf57444cdf6b484fe9b76aa690c3acb7bf24667060dc2971f6b3220d4d8",
        "id": "f08-ribbed-bracket",
        "interface_digest": "sha256:203e2e79b46f26bcc98b2c5807039159038f356c95eaa783be6e8c3c376e1cdb",
        "train_digest": "sha256:4b28e7490eca34061da1431c6379f0f2e5766ff41aedba968eba41ba84fefe0a",
        "version": "1.6",
    },
    ("f02", "2.5"): {
        "construction_limits_digest": "sha256:567f31adcab3cb3ab0b7385eb2c1a89f63016a61fa130489c6ea3b5eb87e04e1",
        "id": "f02",
        "interface_digest": "sha256:928e4eedd9ed6b31ef75268726c5130e916c74a1b0c7afc989e7d1ff6f22da5d",
        "train_digest": "sha256:1201ec5461bfc08ad2ae4522eafc147282f4167e4bb222ed4e798284faa9a4c3",
        "version": "2.5",
    },
    ("electric-motor-magnetics", "1.5"): {
        "construction_limits_digest": "sha256:391dbddcf047326654b172f3e8b34cd6fa10070cbdec071981867e8b4e0f186f",
        "id": "electric-motor-magnetics",
        "interface_digest": "sha256:e257628ce8fc935e42f495cf185facc19bbf93947f00a8766d232f155d896399",
        "train_digest": "sha256:5d27220b8b0c0ccddd013299183118cdce61f205057fe99bceb95c1f52173361",
        "version": "1.5",
    },
    ("chip-cold-plate", "1.5"): {
        "construction_limits_digest": "sha256:7bfb4366cba785d11546aa6882ae13c3a457cba6e88df02b662becf61d68ee72",
        "id": "chip-cold-plate",
        "interface_digest": "sha256:cb1d7820bf1708920b0bd5e313f52d685047469d2e8e60f3ad2f2ed0f1d1298e",
        "train_digest": "sha256:2df26b41a2fdba6a6a64921a9d8c357370374d43d313840ea6e8a371920641d0",
        "version": "1.5",
    },
    ("chip-cold-plate", "1.6"): {
        "construction_limits_digest": "sha256:39a7b6fe1c19274382097a0d41bc0b20ca18a4b0b2be9ba411b0986d29017215",
        "id": "chip-cold-plate",
        "interface_digest": "sha256:cb1d7820bf1708920b0bd5e313f52d685047469d2e8e60f3ad2f2ed0f1d1298e",
        "train_digest": "sha256:2df26b41a2fdba6a6a64921a9d8c357370374d43d313840ea6e8a371920641d0",
        "version": "1.6",
    },
}  # fmt: skip


@pytest.mark.parametrize("key", KEYS)
def test_the_kit_does_not_move_so_a_bound_recipe_or_artifact_stays_valid(key):
    assert physical_material.construction_kit(*key) == KITS[key]


@pytest.mark.parametrize("key", KEYS)
def test_a_dev_grid_version_registers_its_own_development_evaluation(key):
    entry = version_registry.entry(*key)
    kind = dev_grid.kind(*key)
    expected = (
        "cooling-dual-development-grid-v3"
        if key == ("chip-cold-plate", "1.6")
        else f"{kind}-dual-development-grid-v2"
    )
    assert entry.development_evaluation[0] == expected
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
    if key[0] == MOTOR:
        # M2: the PRACTICE cohort first, then the practice grid (tested below)
        assert tuple(bank["case_ids"])[30:] == tuple(grid["case_ids"])
    else:
        assert tuple(bank["case_ids"]) == tuple(grid["case_ids"])
    cohorts = list(bank["cohorts"])
    assert cohorts.count("probe_response") > 0
    assert cohorts.count("decision_sealed_grid") == (
        8 if key[0] in ("f08-ribbed-bracket", "f02") else 48
    )
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
    if key[0] == MOTOR:
        pytest.skip("Motor's dev bank carries the PRACTICE cohort; see the Motor tests")
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


# --- Motor 1.4 (M2): the PRACTICE cohort plus the practice grid --------------------


def test_motor_dev_bank_is_the_practice_cohort_then_the_practice_grid():
    import numpy as np

    key = (MOTOR, "1.4")
    bank = physical_pack.development_bank(*key)
    legacy = physical_pack.legacy_development_bank(*key)
    grid = practice_grid.practice_bank("motor", "1.4")
    practice_ids = [
        c
        for c, k in zip(legacy["case_ids"], legacy["cohorts"], strict=True)
        if k == "practice"
    ]
    assert len(practice_ids) == 30  # the existing public PRACTICE cohort, unchanged
    assert tuple(bank["case_ids"]) == tuple(practice_ids) + tuple(grid["case_ids"])
    assert set(bank["cohorts"][:30]) == {"practice"}
    assert tuple(bank["cohorts"][30:]) == tuple(grid["cohorts"])
    assert np.array_equal(bank["inputs"][30:], grid["inputs"], equal_nan=True)
    assert np.array_equal(bank["references"][30:], grid["references"], equal_nan=True)
    # the PRACTICE rows are exactly the legacy rows
    keep = [i for i, k in enumerate(legacy["cohorts"]) if k == "practice"]
    assert np.array_equal(bank["inputs"][:30], np.asarray(legacy["inputs"])[keep])
    assert np.array_equal(
        bank["references"][:30], np.asarray(legacy["references"])[keep]
    )
    material = physical_material.bundle_material(*key)
    assert len(material["practice_inputs"]) == len(bank["case_ids"]) == 30 + 124
    assert list(material["practice_case_ids"][:30]) == practice_ids


def test_the_rows_reaching_the_sealed_measurement_are_the_practice_grid_byte_for_byte(
    monkeypatch,
):
    """Selection is by cohort name: wherever the PRACTICE rows sit in the dev bank, the
    sealed measurement sees exactly the practice-grid rows and their outputs."""
    from carbon.scoring import motor_sealed_dual_pack as sealed

    key = (MOTOR, "1.4")
    bank = physical_pack.development_bank(*key)
    grid = practice_grid.practice_bank("motor", "1.4")
    names = practice_grid.input_names("motor", "1.4")
    rows = physical.bank_rows(bank, names)
    grid_rows = physical.bank_rows(grid, names)
    outputs = [[float(i)] * 60 for i in range(len(rows))]
    seen = {}

    def spy(**kwargs):
        seen.update(kwargs)
        return {"spied": True}

    monkeypatch.setattr(sealed, "measure", spy)
    adapter = dev_grid.adapter(*key)
    rest = {"definition": {}, "limits": {}, "objective": {}, "train_raw": b""}
    result = adapter.measure(
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        names=names,
        **rest,
    )
    assert result == {"spied": True}
    assert seen["bank_rows"] == grid_rows
    assert seen["outputs"] == outputs[30:]
    assert seen["repeats"] == [outputs[30:], outputs[30:]]
    # a PRACTICE block in the middle: selection never goes by position
    moved_rows = rows[30:60] + rows[:30] + rows[60:]
    moved_out = outputs[30:60] + outputs[:30] + outputs[60:]
    adapter.measure(
        bank_rows=moved_rows,
        outputs=moved_out,
        repeats=[moved_out, moved_out],
        names=names,
        **rest,
    )
    assert "practice" not in {r["cohort"] for r in seen["bank_rows"]}
    assert [r["case_id"] for r in seen["bank_rows"]] == [
        r["case_id"] for r in moved_rows if r["cohort"] != "practice"
    ]
    # a bank with no PRACTICE rows is not this dev bank
    with pytest.raises(sealed.Refused):
        adapter.measure(
            bank_rows=grid_rows,
            outputs=outputs[30:],
            repeats=[outputs[30:]] * 2,
            names=names,
            **rest,
        )


def test_the_sealed_population_takes_no_practice_row():
    """Shape bound to population: PRACTICE rows exist only in the development bank."""
    from carbon.scoring import motor_sealed_dual_pack as sealed

    bank = physical_pack.development_bank(MOTOR, "1.4")
    public = physical_pack.public_roles(MOTOR, "1.4")
    assert not sealed.is_sealed_bank(bank)
    # the sealed grader's own shape check: every row is a cell or a probe
    grid = practice_grid.practice_bank("motor", "1.4")
    names = practice_grid.input_names("motor", "1.4")
    rows = physical.bank_rows(bank, names)
    outputs = [[1.0] * 60 for _ in rows]
    with pytest.raises(sealed.Refused):
        sealed.measure(
            bank_rows=rows,
            outputs=outputs,
            repeats=[outputs, outputs],
            definition=sealed.definition(bank=grid, train_raw=public["train"]),
            limits=json.loads(public["important_limit_definition"]),
            objective=json.loads(public["design_objective"]),
            train_raw=public["train"],
            names=names,
        )


def test_motor_dev_pack_writes_with_the_sealed_rule_and_its_own_identity(tmp_path):
    key = (MOTOR, "1.4")
    adapter = dev_grid.adapter(*key)
    assert adapter.EVALUATION_VERSION == "motor-dual-development-grid-v2"
    assert "motor_dev_grid.py" in adapter.FILES  # inside its producer identity
    manifest = adapter.write_development_pack(
        tmp_path / "pack", inference_image_id="sha256:" + "a" * 64
    )
    draft = json.loads(manifest.read_bytes())
    path = tmp_path / "pack" / draft["public"]["accuracy_definition"]["path"]
    definition = json.loads(path.read_bytes())
    assert definition["population"] == "PRACTICE_PUBLIC_BANK"
    assert definition["grid"] == {"designs": 8, "conditions": 6}
    assert "critical" in definition and "physics" in definition


def test_the_practice_30_total_is_unchanged_by_the_re_layout(tmp_path, monkeypatch):
    """Same predictions, same summary on the 30 PRACTICE cases: the catalog practice with the
    receiver's worker stubbed, 1.3 (old layout) against 1.4 (dev-grid layout)."""
    from types import SimpleNamespace

    import numpy as np
    from test_lp_prod_research_tools import ledger

    from carbon.challenge_registry.motor import catalog_recipe
    from carbon.development_session import bundle_construction_worker as worker
    from carbon.motor import catalog_practice

    def run(version):
        calls = []

        def fake(ledger_, **kwargs):
            calls.append(kwargs)
            rows = np.full((len(kwargs["inputs"]), 60), 1.0).tolist()
            state = "sha256:" + "5" * 64
            return SimpleNamespace(
                build=SimpleNamespace(state_digest=state),
                inference=SimpleNamespace(state_digest=state, predictions=rows),
            )

        monkeypatch.setattr(worker, "reconstruct_and_infer_public", fake)
        parent = SimpleNamespace(image_id="sha256:" + "7" * 64)
        item = catalog_practice.MotorCatalogPractice(
            ledger=ledger(tmp_path / f"ledger-{version}"),
            owner="alice",
            parent=parent,
            cache_root=tmp_path / f"cache-{version}",
            root=".",
            version=version,
            resolver=lambda ref: SimpleNamespace(bundle_ref=ref),
            parents=SimpleNamespace(for_bundle=lambda _ref: parent),
        )
        recipe = catalog_recipe("neuralop.FNO", version=version)
        return item(f"motor-catalog-{version}", recipe), calls[0]

    old, old_call = run("1.3")
    new, new_call = run("1.4")
    assert len(new_call["inputs"]) == 30 + 124  # one query: PRACTICE, then the grid
    assert len(old_call["inputs"]) == 90 + 48 + 76
    assert new["summary"] == old["summary"]
    assert new["safety"] == old["safety"]
    assert new["practice_dual"]["schema"] == "carbon.practice.dual-feedback.v2"
    assert new["practice_dual"]["bank"] == "practice (public bank)"


def test_motor_dev_grade_is_the_sealed_grade_on_the_practice_grid(tmp_path):
    """One code path: the dev adapter's grade of the full dev bank equals the sealed
    grader's grade of the practice-grid rows alone, for the same predictions."""
    import numpy as np

    from carbon.motor import domain
    from carbon.scoring import motor_physics
    from carbon.scoring import motor_sealed_dual_pack as sealed

    key = (MOTOR, "1.4")
    adapter = dev_grid.adapter(*key)
    bank = physical_pack.development_bank(*key)
    grid = practice_grid.practice_bank("motor", "1.4")
    names = practice_grid.input_names("motor", "1.4")
    public = physical_pack.public_roles(*key)
    model = motor_physics.registered_model(public["train"])
    rows = physical.bank_rows(bank, names)

    def predict(row):
        if row["cohort"] == "probe_response":
            return [float(model(list(row["inputs"].values())))] * domain.ANGLE_STEPS
        return [float(v) for v in row["reference"]]

    outputs = [predict(r) for r in rows]
    args = {
        "limits": json.loads(public["important_limit_definition"]),
        "objective": json.loads(public["design_objective"]),
        "train_raw": public["train"],
        "names": names,
    }
    dev = adapter.measure(
        bank_rows=rows,
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=adapter.definition(bank=bank, train_raw=public["train"]),
        **args,
    )
    grid_rows = physical.bank_rows(grid, names)
    exam = sealed.measure(
        bank_rows=grid_rows,
        outputs=outputs[30:],
        repeats=[outputs[30:], outputs[30:]],
        definition=sealed.definition(bank=grid, train_raw=public["train"]),
        **args,
    )
    assert dev == exam
    assert set(dev["A_legs"]) == {"A_acc", "A_robust", "A_law", "A_response"}
    assert np.isfinite(dev["A"])


# --- Cooling 1.4: the practice grid, graded as 1.3 is (the encoded adapter) -------------

COOLING = "chip-cold-plate"


def test_cooling_has_its_practice_and_sealed_adapter_and_the_dev_adapter_shares_its_module():
    from carbon.scoring import cooling_encoded_dual_pack as encoded

    practice = practice_grid.adapter("cooling", "1.4")
    assert practice is not None and practice.VERSION == "1.4"
    dev = dev_grid.adapter(COOLING, "1.4")
    assert dev.EVALUATION_VERSION == "cooling-dual-development-grid-v2"
    # one code path: the dev adapter is the same encoded module the sealed one runs
    assert getattr(dev, "_module", dev) is getattr(practice, "_module", practice)
    assert getattr(dev, "_module", dev) is encoded._SELF
    assert "cooling_encoded_dual_pack.py" in dev.FILES


def test_cooling_dev_shape_is_bound_to_its_population(tmp_path):
    """The dev (practice-grid) definition is the 48-cell PRACTICE_PUBLIC_BANK; a sealed
    definition is exactly the 16-cell batch; neither validates as the other."""
    adapter = dev_grid.adapter(COOLING, "1.4")
    public = physical_pack.public_roles(COOLING, "1.4")
    bank = physical_pack.development_bank(COOLING, "1.4")
    definition = adapter.definition(bank=bank, train_raw=public["train"])
    assert definition["population"] == "PRACTICE_PUBLIC_BANK"
    assert definition["cohort_counts"] == {"decision_sealed_grid": 48}
    adapter.validate_definition(definition)
    sealed_named = {k: v for k, v in definition.items() if k != "population"}
    with pytest.raises(adapter.Refused):
        adapter.validate_definition(sealed_named)
    shrunk = {**definition, "cohort_counts": {"decision_sealed_grid": 16}}
    with pytest.raises(adapter.Refused):
        adapter.validate_definition(shrunk)


def test_cooling_dev_pack_writes_and_practice_still_reads_its_own_cases(tmp_path):
    """Cooling's practice set (100 public practice cases) is separate from the dev bank
    and is queried by the practice flow itself, so its totals cannot move; the dev pack
    writes on the grid with the sealed rule."""
    adapter = dev_grid.adapter(COOLING, "1.4")
    manifest = adapter.write_development_pack(
        tmp_path / "pack", inference_image_id="sha256:" + "a" * 64
    )
    draft = json.loads(manifest.read_bytes())
    path = tmp_path / "pack" / draft["public"]["accuracy_definition"]["path"]
    definition = json.loads(path.read_bytes())
    assert "critical" in definition and "physics" in definition
    material = physical_material.bundle_material(COOLING, "1.4")
    assert len(material["practice_inputs"]) == len(
        physical_pack.development_bank(COOLING, "1.4")["case_ids"]
    )


# --- the catalog freeze moves a kit by its served backbone-catalog digest and nothing else ---

#: Each dev-grid version's kit and the served backbone-catalog digest its limits document carried on
#: rc10 (385bc1279), before the frozen catalog (0530c1d41). New versions, pre-publish (the pool versions
#: did not exist on rc10 and are not in this table).
KITS_ON_RC10 = {
    ("chip-cold-plate", "1.4"): (
        "sha256:6db34335c03c3b1bd8bbd55de89a38e3cd44026f47bd227a9be4c522266b3334",
        "sha256:f6a9b9c5ca937cd491d9df97c43e309832f87f2897cce2828e8810e3f2cc5924",
    ),
    ("electric-motor-magnetics", "1.4"): (
        "sha256:43f3c2c3d9c7f3b6672cd59be012038526c4a937aa6fa1cc82ad3444eb365fa0",
        "sha256:384beb065f566300f701ea0443e593f1990fc4fc0993f383ad4ec133b4c8eaaa",
    ),
    ("f02", "2.4"): (
        "sha256:5e1bf1057bbbaad62b223e748b54dd92ec94c384020c63778228789967feaf1f",
        "sha256:a33b56d54e804f3bd2c82580cd518b54c1296e82a3a020b4cfe1d67830bdc63d",
    ),
    ("f08-ribbed-bracket", "1.5"): (
        "sha256:9ada93ee419c2adbe91e7e8aae8176f35e2d60b11484ad9e9814b772ae4cf63b",
        "sha256:8c47d928947ed3039eaa5a8dda2a92f36270d9a72944c48efb8a0a9f74f9e1ac",
    ),
}


@pytest.mark.parametrize("key", sorted(KITS_ON_RC10))
def test_a_kit_moved_with_the_served_catalog_digest_and_nothing_else(key, monkeypatch):
    """With the one field `backbone_catalog.digest` set back to what it was on rc10, each
    dev-grid version's limits document hashes to the kit it had on rc10: the catalog freeze
    moved the kit through that field alone (and not at all where the catalog did not change).
    """
    import copy

    from carbon.challenge_kit import served_versions

    # The kit before the large-profile publication (a separate move, pinned by
    # test_published_policy_is_enforced): rc10's kits predate it.
    monkeypatch.setattr(served_versions, "worker_resources", lambda *_: None)
    rc43_surfaces.learning_rate_as_in_rc43(monkeypatch)
    kit_before, catalog_before = KITS_ON_RC10[key]
    public = physical_material._public(key[0])
    limits = copy.deepcopy(public.construction_limits_document(*key))
    limits["backbone_catalog"]["digest"] = catalog_before
    # rc10 predates the 648/947 wall (OWNER-REBUILD-WALL-11MIN-01): it published 1800 s.
    policy = limits["reconstruction_resource_policy"]
    policy.update(
        build_wall_seconds_max=1800,
        inference_wall_seconds_max=1800,
        total_reconstruction_wall_seconds_max=1800,
    )
    assert public._digest(limits) == kit_before
