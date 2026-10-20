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
        f02_train.load_public_train("2.2")
    with pytest.raises(SystemExit):
        pp.main(["out", "--challenge", F02])  # --version is required
    with pytest.raises(SystemExit):
        pp.main(["out", "--challenge", F02, "--version", "9.9"])


def test_an_unregistered_version_writes_no_pack(tmp_path):
    with pytest.raises(ValueError):
        pp.write_public_pack(tmp_path / "x", F02, "2.2")


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
