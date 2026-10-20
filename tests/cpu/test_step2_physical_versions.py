"""Motor 1.1 and Cooling 1.1, the step-2 versions (Validator,
STEP2_BATCH_VERSIONS_20261020): served v6 and no fixed training-step cap
(OWNER-REBUILD-TIME-LIMIT-01). The 1.0 versions keep their bytes.

The exam banks are Data Collection's (physical_pack.development_bank); here a
stand-in bank checks only this lane's wiring.
"""

from __future__ import annotations

import pytest

from carbon.challenge_kit import physical_material, physical_public
from carbon.challenge_kit import served_versions as sv
from carbon.challenge_kit.synthetic_linear_field_2d import allowlist_v5_bytes
from carbon.level4 import allowlist as allowlist_module

NEW = [(sv.MOTOR, "1.1"), (sv.COOLING, "1.1")]
OLD = [(sv.MOTOR, "1.0"), (sv.COOLING, "1.0")]


@pytest.mark.parametrize("key", NEW + OLD)
def test_each_version_is_registered_and_builds_its_kit(key):
    challenge_id, version = key
    assert physical_material.is_registered(challenge_id, version)
    kit = physical_public.construction_kit(challenge_id, version)
    assert (kit["id"], kit["version"]) == key


@pytest.mark.parametrize("key", NEW)
def test_a_step2_version_names_the_rebuild_time_as_its_only_training_limit(key):
    limits = physical_public.construction_limits_document(*key)
    assert limits["training_step_cap"] is None
    assert limits["training_limit"] == "build_wall_seconds_max"
    policy = limits["reconstruction_resource_policy"]
    assert policy["build_wall_seconds_max"] > 0


@pytest.mark.parametrize("key", OLD)
def test_an_existing_version_keeps_its_limits_bytes(key):
    limits = physical_public.construction_limits_document(*key)
    assert "training_step_cap" not in limits and "training_limit" not in limits
    # Apart from the version, the new limits add exactly the two fields.
    new = physical_public.construction_limits_document(key[0], "1.1")
    for name in ("training_step_cap", "training_limit"):
        new.pop(name)
    new["challenge"]["version"] = key[1]
    assert new == limits


@pytest.mark.parametrize("version", ["1.2", "2.0", ""])
def test_an_unregistered_version_is_refused(version):
    with pytest.raises(ValueError, match="unknown public physical Challenge version"):
        physical_public.construction_kit(sv.MOTOR, version)
    assert not physical_material.is_registered(sv.MOTOR, version)


def test_the_step2_material_serves_v6_and_the_old_one_v5(monkeypatch):
    from carbon.challenge_kit import physical_pack

    real = physical_pack.development_bank

    def bank(challenge_id, version):
        # Stand-in for Data Collection's 1.1 bank: 1.0's rows, re-versioned.
        return real(challenge_id, "1.0")

    monkeypatch.setattr(physical_pack, "development_bank", bank)
    for challenge_id, version in NEW:
        material = physical_material.bundle_material(challenge_id, version)
        assert material["allowlist_bytes"] == allowlist_module.served_bytes()
        assert material["construction_kit"]["version"] == version
    for challenge_id, version in OLD:
        material = physical_material.bundle_material(challenge_id, version)
        assert material["allowlist_bytes"] == allowlist_v5_bytes()
