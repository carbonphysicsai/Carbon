"""The prospective bundle source retains Battery's registered public bytes."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from carbon.battery import challenge, practice
from carbon.battery.construction_bundle_material import (
    PHYSICS_PATH,
    bundle_material,
)
from carbon.development_session.research_service import DirectFixtureDiscovery


def test_registered_bundle_material_uses_original_battery_train_and_practice():
    material = bundle_material()
    assert material["challenge_key"] == challenge.CHALLENGE
    assert hashlib.sha256(material["train"]).hexdigest() == challenge.TRAIN_V1_SHA256
    assert material["construction_kit"]["train_digest"] == (
        "sha256:" + challenge.TRAIN_V1_SHA256
    )
    assert material["practice_inputs"].shape == (practice.PRACTICE_CASES, 4)
    assert material["practice_reference"].shape == (practice.PRACTICE_CASES, 247)
    assert material["practice_inputs"].dtype == np.float64
    assert material["practice_reference"].dtype == np.float64
    assert material["construction_limits_document"]["accuracy_gate"] is None
    assert material["disclosure"]["live_eligible"] is False


def test_registered_battery_discovery_rechecks_exact_public_source():
    material = bundle_material()
    discovery = DirectFixtureDiscovery(material, task_admission=True)
    assert discovery.info.challenge_key == challenge.CHALLENGE
    assert (
        discovery.info.public_train_digest
        == material["construction_kit"]["train_digest"]
    )
    assert "stage_research_source" in discovery.manifest.supported_operations
    material["train"] = b"changed"
    with pytest.raises(ValueError, match="direct Challenge kit or fixed public TRAIN"):
        discovery.get_challenge_info(challenge.CHALLENGE)


@pytest.mark.parametrize(
    "changed", [challenge.TRAIN_V1_PATH, practice.PRACTICE_SOURCE_PATH, PHYSICS_PATH]
)
def test_registered_bundle_material_refuses_changed_public_source(tmp_path, changed):
    repository = Path(__file__).resolve().parents[2]
    for name in (challenge.TRAIN_V1_PATH, practice.PRACTICE_SOURCE_PATH, PHYSICS_PATH):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repository / name).read_bytes())
    target = tmp_path / changed
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises((challenge.MaterialMismatch, ValueError)):
        bundle_material(tmp_path)


def test_battery_bundle_policy_matches_enforced_c03_and_refuses_reauthored_limit():
    from carbon.development_session.bundle_construction_worker import (
        verify_direct_resource_policy,
    )
    from carbon.development_session.construction_recipe import RecipeRefused
    from carbon.development_session.profile import canonical, digest

    material = bundle_material()
    kit = material["construction_kit"]
    binding = {
        "challenge_id": kit["id"],
        "challenge_version": kit["version"],
        **{
            key: kit[key]
            for key in (
                "train_digest",
                "interface_digest",
                "construction_limits_digest",
            )
        },
    }
    limits = material["construction_limits_document"]
    assert (
        verify_direct_resource_policy(binding, limits)
        == kit["construction_limits_digest"]
    )
    limits["reconstruction_resource_policy"]["memory_bytes_max"] += 1
    altered = {**binding, "construction_limits_digest": digest(canonical(limits))}
    with pytest.raises(
        RecipeRefused, match="construction_resource_policy_binding_invalid"
    ):
        verify_direct_resource_policy(altered, limits)
