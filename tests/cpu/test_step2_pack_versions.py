"""Step-2 batch (STEP2_BATCH_VERSIONS_20261020): each new Challenge version's
exam pack carries the same content as its predecessor apart from the
version binding, and every version is named explicitly (no default)."""

from __future__ import annotations

import numpy as np
import pytest

from carbon.challenge_kit import f02_public, f02_train, f08_public, f08_train
from carbon.challenge_kit import physical_pack as pp

F08, F02 = f08_train.CHALLENGE_ID, f02_train.CHALLENGE_ID
NEW = {
    ("electric-motor-magnetics", "1.1"): "motor-normal-construction-development-2",
    ("chip-cold-plate", "1.1"): "cooling-normal-construction-development-2",
    (F08, "1.2"): "f08-normal-construction-development-3",
    (F02, "2.1"): "f02-normal-construction-development-3",
    (
        "battery-fastcharge-ageing-development-v1",
        "2.0",
    ): "battery-normal-construction-development-3",
}


def _same_bank(a, b):
    """Same keys, and every value equal (arrays elementwise, NaN == NaN)."""
    if set(a) != set(b):
        return False
    for key in a:
        x, y = a[key], b[key]
        if isinstance(x, np.ndarray) or isinstance(y, np.ndarray):
            if not np.array_equal(x, y, equal_nan=True):
                return False
        elif x != y:
            return False
    return True


def test_every_new_version_has_its_own_explicit_pack_version():
    for key, pack_version in NEW.items():
        assert pp.PACK_VERSIONS[key] == pack_version
    # Distinct from every existing version's pack.
    assert len(set(pp.PACK_VERSIONS.values())) == len(pp.PACK_VERSIONS)


def test_f08_1_2_is_1_1_apart_from_the_binding():
    assert _same_bank(pp.development_bank(F08, "1.1"), pp.development_bank(F08, "1.2"))
    v11, v12 = (f08_train.load_public_train(v) for v in ("1.1", "1.2"))
    assert v11["train"] == v12["train"]
    k11, k12 = (f08_public.construction_kit(F08, v) for v in ("1.1", "1.2"))
    assert k11["train_digest"] == k12["train_digest"]
    assert (
        k12["version"] == "1.2" and k11["interface_digest"] != k12["interface_digest"]
    )


def test_f02_2_1_is_2_0_apart_from_the_binding():
    assert _same_bank(pp.development_bank(F02, "2.0"), pp.development_bank(F02, "2.1"))
    t20, t21 = (f02_train.load_public_train(v) for v in ("2.0", "2.1"))
    assert t20["train"] == t21["train"]
    assert t20["train_peak_std_c"] == t21["train_peak_std_c"]
    k21 = f02_public.construction_kit(F02, "2.1")
    assert (
        k21["train_digest"] == f02_public.construction_kit(F02, "2.0")["train_digest"]
    )
    assert k21["version"] == "2.1"


def test_there_is_no_default_version():
    with pytest.raises(TypeError):
        f02_train.load_public_train()
    with pytest.raises(TypeError):
        f08_train.load_public_train()
    with pytest.raises(ValueError):
        f02_train.load_public_train("9.9")  # 2.2 is registered (v7)
    with pytest.raises(SystemExit):
        pp.main(["out", "--challenge", F02])  # --version is required
    with pytest.raises(SystemExit):
        pp.main(["out", "--challenge", F02, "--version", "9.9"])


def test_an_unregistered_version_writes_no_pack(tmp_path):
    with pytest.raises(ValueError):
        pp.write_public_pack(tmp_path / "x", F02, "9.9")  # 2.2 is registered (v7)


def test_step2_kits_carry_no_step_cap_and_existing_kits_keep_their_bytes():
    for public, cid, new, old in (
        (f08_public, F08, "1.2", "1.1"),
        (f02_public, F02, "2.1", "2.0"),
    ):
        limits = public.construction_limits_document(cid, new)
        assert limits["training_step_cap"] is None
        assert limits["training_limit"] == "build_wall_seconds_max"
        assert "training_step_cap" not in public.construction_limits_document(cid, old)
    # The existing kits' digests at base 10368fa86, unchanged.
    assert f08_public.construction_kit(F08, "1.1")["construction_limits_digest"] == (
        "sha256:28a77a5beaf259a73acfa5b807fb5fd683353ee2c7de20ddb5ee155c94c7fb78"
    )
    assert f02_public.construction_kit(F02, "2.0")["construction_limits_digest"] == (
        "sha256:df88cb39b0213803cf7c6ad0a7cdc60f9ee55a3418f054d17776e433391dae99"
    )


def test_battery_2_0_roles_come_from_its_served_material():
    import json

    from carbon.battery.construction_bundle_material import versioned_material
    from carbon.challenge_kit import battery_pack

    roles = battery_pack.public_roles("2.0")
    material = versioned_material("2.0")
    assert json.loads(roles["construction_kit"]) == material["construction_kit"]
    assert json.loads(roles["construction_kit"])["version"] == "2.0"
    assert roles["train"] == material["train"]
    assert json.loads(roles["physics_contract"]) == material["physics_contract"]
    limits = json.loads(roles["important_limit_definition"])
    assert limits["b15_probe_plan"]["sha256"] == battery_pack._B15_PLAN[1]
    assert (
        limits["ev4_decision_references"]["sha256"] == battery_pack._EV4_REFERENCES[1]
    )
    # 1.0's limit role names neither (its bytes are unchanged).
    old = json.loads(battery_pack.public_roles("1.0")["important_limit_definition"])
    assert "b15_probe_plan" not in old and "ev4_decision_references" not in old


@pytest.mark.parametrize("cid", ["electric-motor-magnetics", "chip-cold-plate"])
def test_motor_and_cooling_1_1_differ_from_1_0_only_in_the_kit(cid):
    assert _same_bank(pp.development_bank(cid, "1.0"), pp.development_bank(cid, "1.1"))
    old, new = pp.public_roles(cid, "1.0"), pp.public_roles(cid, "1.1")
    assert set(old) == set(new)
    assert {role for role in old if old[role] != new[role]} == {"construction_kit"}


def test_motor_1_2_is_1_1_with_its_own_kit_and_pack_id():
    """Motor 1.2 (backbone catalog) changes only what a miner may build: the
    pack reuses 1.1's bank, physics and public roles except the kit."""
    import numpy as np

    from carbon.challenge_kit import physical_pack as pp

    m = "electric-motor-magnetics"
    assert pp.PACK_VERSIONS[(m, "1.2")] == "motor-normal-construction-development-3"
    assert len({pp.PACK_VERSIONS[(m, v)] for v in ("1.0", "1.1", "1.2")}) == 3
    a, b = pp.public_roles(m, "1.1"), pp.public_roles(m, "1.2")
    assert set(a) == set(b)
    assert [k for k in a if a[k] != b[k]] == ["construction_kit"]
    x, y = pp.development_bank(m, "1.1"), pp.development_bank(m, "1.2")
    assert x["case_ids"] == y["case_ids"] and x["cohorts"] == y["cohorts"]
    assert np.array_equal(x["inputs"], y["inputs"])
    assert np.array_equal(x["references"], y["references"])
    assert x["reference_records"] == y["reference_records"]
    assert pp.physics_contract(m, "1.1") == pp.physics_contract(m, "1.2")


V7 = {
    # version: (predecessor, own pack version)
    ("electric-motor-magnetics", "1.3"): (
        "1.2",
        "motor-normal-construction-development-4",
    ),
    ("chip-cold-plate", "1.2"): ("1.1", "cooling-normal-construction-development-3"),
    (F08, "1.3"): ("1.2", "f08-normal-construction-development-4"),
    (F02, "2.2"): ("2.1", "f02-normal-construction-development-4"),
    (F08, "1.4"): ("1.3", "f08-normal-construction-development-5"),
    (F02, "2.3"): ("2.2", "f02-normal-construction-development-5"),
    (
        "battery-fastcharge-ageing-development-v1",
        "2.1",
    ): ("2.0", "battery-normal-construction-development-4"),
}


def _without_version(raw, version, predecessor):
    """A role's bytes with this version's identity written as the
    predecessor's, so only real content differences remain."""
    import json

    text = json.dumps(json.loads(raw), sort_keys=True)
    return text.replace(f'"version": "{version}"', f'"version": "{predecessor}"')


@pytest.mark.parametrize("key", sorted(V7))
def test_v7_versions_are_their_predecessors_exam_under_their_own_pack(key):
    """The v7 catalog versions change what a miner may build: the exam (bank,
    references, physics, limits, objective, interface) is the predecessor's,
    and only the construction kit differs; each has its own pack version."""
    cid, version = key
    predecessor, pack_version = V7[key]
    assert pp.PACK_VERSIONS[key] == pack_version
    assert _same_bank(
        pp.development_bank(cid, predecessor), pp.development_bank(cid, version)
    )
    assert pp.physics_contract(cid, predecessor) == pp.physics_contract(cid, version)
    old, new = pp.public_roles(cid, predecessor), pp.public_roles(cid, version)
    assert set(old) == set(new)
    # F08 1.4's limit statement cites the registered U (3.9e-5) where 1.3's
    # carries the pre-record 3.4e-5; the test below pins exactly that change.
    differs = {(F08, "1.4"): ("important_limit_definition",)}.get(key, ())
    for role in old:
        if role in ("construction_kit", "train", *differs):
            continue
        assert _without_version(old[role], version, predecessor) == _without_version(
            new[role], version, predecessor
        ), role
    assert old["train"] == new["train"]


def test_f08_limit_cites_the_registered_u_from_1_4_and_served_versions_keep_bytes():
    """Validator, 2026-10-21: the registered U (3.9e-5 mm/N, worst dynamic)
    governs; the fix is prospective, so 1.1-1.3 keep their served statement."""
    import json

    record_path = (
        "docs/development/evidence/f08-near-limit-public-20261020/"
        "reference-uncertainty/f08-reference-uncertainty.json"
    )
    for version in ("1.1", "1.2", "1.3"):
        limits = json.loads(pp.public_roles(F08, version)["important_limit_definition"])
        assert limits["exam_straddle"]["largest_reference_error_mm_per_n"] == 3.4e-5
        assert "reference_uncertainty_mm_per_n" not in limits["exam_straddle"]
    old = json.loads(pp.public_roles(F08, "1.3")["important_limit_definition"])
    new = json.loads(pp.public_roles(F08, "1.4")["important_limit_definition"])
    straddle = new["exam_straddle"]
    assert straddle["reference_uncertainty_mm_per_n"] == 3.9e-5
    assert straddle["reference_uncertainty_record"]["path"] == record_path
    assert "largest_reference_error_mm_per_n" not in straddle
    assert straddle["smallest_margin_mm_per_n"] / 3.9e-5 > 70
    # Only the reference term differs from 1.3's statement.
    old["exam_straddle"].pop("largest_reference_error_mm_per_n")
    for k in ("reference_uncertainty_mm_per_n", "reference_uncertainty_record"):
        new["exam_straddle"].pop(k)
    assert _without_version(json.dumps(old), "1.4", "1.3") == _without_version(
        json.dumps(new), "1.4", "1.3"
    )
