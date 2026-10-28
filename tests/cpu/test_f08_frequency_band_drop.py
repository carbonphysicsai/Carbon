"""OWNER-F08-FREQUENCY-BAND-DROP-01: prospective F08 1.7, one scoring path.

All tables here are synthetic diagnostics or the exposed development bank.
They do not register pool constants or assert scientific qualification.
"""

from __future__ import annotations

import copy
import json

import pytest
from test_f08_sealed_grid_grading import _full, case  # noqa: F401

from carbon.challenge_kit import physical_material, physical_pack, version_registry
from carbon.challenge_registry import published_exam, registry
from carbon.scoring import dev_grid, pool_adapters, pool_version, practice_grid
from carbon.scoring import f08_dual_measurement as fdm
from carbon.scoring import f08_sealed_dual_pack as sealed
from carbon.scoring import physical_dual_pack as physical

CHALLENGE = "f08-ribbed-bracket"
KEY = (CHALLENGE, "1.7")


def _measure(case, outputs, *, version, repeats=None):
    chosen = practice_grid.adapter("f08", version)
    definition = chosen.definition(
        bank=case["bank"], train_raw=case["public"]["train"]
    )
    return chosen.measure(
        bank_rows=case["rows"],
        outputs=outputs,
        repeats=[outputs, outputs] if repeats is None else repeats,
        definition=definition,
        limits=case["limits"],
        objective=None,
        train_raw=case["public"]["train"],
        names=case["names"],
    )


@pytest.mark.parametrize("frequency", [79.2, 606.0, 607.9])
def test_overshoot_is_an_accuracy_error_only_on_the_new_version(case, frequency):
    case = copy.deepcopy(case)
    outputs = _full(case, case["truth"])
    index = next(i for i, r in enumerate(case["rows"]) if r["cohort"] == sealed.COHORT)
    # A ~1% prediction error at either edge previously blanked the whole exam.
    for j in (2, 4, 6):
        case["rows"][index]["reference"][j] = 80.0 if frequency < 80 else 600.0
        outputs[index][j] = frequency
    current = _measure(case, outputs, version="1.7")
    assert all(current["gates"].values())
    assert 0 < current["A"] < 1
    for old in ("1.2", "1.5", "1.6"):
        historical = _measure(case, outputs, version=old)
        assert historical["gates"]["finite_native_summary"] is False
        assert historical["A"] is None
    row = outputs[index]
    assert pool_adapters.physics_gates("f08", "1.7").failed({}, row) == ()
    assert "finite_native_summary" in pool_adapters.physics_gates("f08", "1.6").failed(
        {}, row
    )


@pytest.mark.parametrize(
    "bad",
    [
        [],
        [0.001] * 6,
        [0.001] * 8,
        None,
        [0.001, 0.1, float("nan"), 0.05, 606.0, 0.025, 606.0],
        [0.001, 0.1, float("inf"), 0.05, 606.0, 0.025, 606.0],
        [0.001, 0.1, 0.0, 0.05, 606.0, 0.025, 606.0],
        [0.001, 0.1, -1.0, 0.05, 606.0, 0.025, 606.0],
        [-0.001, 0.1, 606.0, 0.05, 606.0, 0.025, 606.0],
        [0.001, -0.1, 606.0, 0.05, 606.0, 0.025, 606.0],
        [0.001, 0.1, "invalid", 0.05, 606.0, 0.025, 606.0],
        [0.001, 0.05, 606.0, 0.1, 606.0, 0.025, 606.0],
    ],
)
def test_invalid_answers_still_fail_native_and_pool_gates(case, bad):
    outputs = _full(case, case["truth"])
    index = next(i for i, r in enumerate(case["rows"]) if r["cohort"] == sealed.COHORT)
    outputs[index] = bad
    result = _measure(case, outputs, version="1.7")
    assert not all(result["gates"].values())
    assert pool_adapters.physics_gates("f08", "1.7").failed({}, bad)


def test_repeats_are_checked_by_the_same_new_sanity_rule(case):
    outputs = _full(case, case["truth"])
    repeat = copy.deepcopy(outputs)
    index = next(i for i, r in enumerate(case["rows"]) if r["cohort"] == sealed.COHORT)
    repeat[index][2] = 0.0
    result = _measure(case, outputs, version="1.7", repeats=[repeat, outputs])
    assert result["gates"]["finite_native_summary"] is False
    assert result["gates"]["paired_repeat"] is False


def test_new_version_has_distinct_identities_and_reuses_the_same_scorer(case):
    entry = version_registry.entry(*KEY)
    old = version_registry.entry(CHALLENGE, "1.6")
    assert entry.development_evaluation != old.development_evaluation
    assert entry.sealed_evaluation != old.sealed_evaluation
    assert entry.train == old.train
    assert entry.catalog_entries_from == old.catalog_entries_from
    pool = sealed.adapter("1.7")
    practice = practice_grid.adapter("f08", "1.7")
    development = dev_grid.adapter(*KEY)
    assert pool._module is practice._module is development._module
    assert pool.POOL_GRADED and not getattr(practice, "POOL_GRADED", False)
    for chosen in (pool, practice, development):
        definition = chosen.definition(
            bank=case["bank"], train_raw=case["public"]["train"]
        )
        assert definition["native_summary_rule"] == fdm.SANITY_RULE
    historical = sealed.adapter("1.6").definition(
        bank=case["bank"], train_raw=case["public"]["train"]
    )
    assert "native_summary_rule" not in historical
    assert historical["frequency_band_hz"] == [80, 600]
    assert physical.producer_digest(pool) != physical.producer_digest(
        sealed.adapter("1.6")
    )
    # The owner did not change design feasibility or construction data.
    new_public = physical_pack.public_roles(*KEY)
    old_public = physical_pack.public_roles(CHALLENGE, "1.6")
    for role in ("train", "physics_contract"):
        assert new_public[role] == old_public[role]
    for role in ("important_limit_definition", "design_objective"):
        new = json.loads(new_public[role])
        old = json.loads(old_public[role])
        new.pop("challenge")
        old.pop("challenge")
        assert new == old


def test_reserved_version_refuses_grading_until_owner_picks(case):
    entry = next(e for e in registry.entries() if (e.challenge_id, e.version) == KEY)
    assert entry.status == registry.RESERVED
    with pytest.raises(registry.ChallengeNotImplemented):
        registry.resolve(*KEY, registry.CPU_RESEARCH)
    constants = json.loads(pool_version.CONSTANTS.read_bytes())["versions"][
        " ".join(KEY)
    ]

    def leaves(value):
        return (
            [v for child in value.values() for v in leaves(child)]
            if isinstance(value, dict)
            else [value]
        )

    assert set(leaves(constants)) == {pool_version.HUMAN_INPUT}
    chosen = sealed.adapter("1.7")
    with pytest.raises(
        pool_version.PoolConstantsNotRegistered, match="pool_constants_not_registered"
    ):
        chosen.measure(
            bank_rows=[],
            outputs=[],
            repeats=[[], []],
            definition={"pool": {"sets": []}},
            limits={},
            objective=None,
            train_raw=b"",
            names=[],
        )


def test_published_gate_changes_only_for_the_prospective_version():
    new = published_exam.for_version(*KEY)
    old = published_exam.for_version(CHALLENGE, "1.6")
    assert new["scoring_version"] == "f08-pool-sealed-v2"
    assert old["scoring_version"] == "f08-pool-sealed-v1"
    assert new["gates"][0] != old["gates"][0]
    assert new["gates"][1:] == old["gates"][1:]
    assert "strictly positive" in str(new["gates"][0])
    assert new["limits"] == old["limits"]


def test_new_development_pack_binds_and_writes_the_registered_rule(tmp_path):
    chosen = dev_grid.adapter(*KEY)
    manifest = chosen.write_development_pack(
        tmp_path, inference_image_id="sha256:" + "1" * 64
    )
    document = json.loads(manifest.read_bytes())
    accuracy = json.loads(
        (tmp_path / document["public"]["accuracy_definition"]["path"]).read_bytes()
    )
    assert accuracy["native_summary_rule"] == fdm.SANITY_RULE
    assert accuracy["challenge"] == {"id": CHALLENGE, "version": "1.7"}
    # Exercise the real public kit/pack path, not a standalone definition only.
    kit = physical_material.construction_kit(*KEY)
    assert kit["version"] == "1.7"
    assert (tmp_path / physical.MANIFEST_NAME).is_file()
