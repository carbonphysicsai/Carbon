"""Source-owned physical limits admission; no model or scientific qualification."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from carbon.challenge_kit import physical_public, synthetic_linear_field_2d
from carbon.development_session import research_carrier
from carbon.development_session.bundle_construction_worker import (
    verify_direct_resource_policy,
)
from carbon.development_session.construction_recipe import RecipeRefused
from carbon.development_session.profile import canonical, digest

FAMILIES = ("electric-motor-magnetics", "chip-cold-plate")


def _material(challenge_id):
    kit = physical_public.construction_kit(challenge_id, "1.0")
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
    return (
        kit,
        binding,
        physical_public.construction_limits_document(challenge_id, "1.0"),
    )


@pytest.mark.parametrize("challenge_id", FAMILIES)
def test_exact_source_owned_physical_kit_accepts_both_normal_binding_shapes(
    challenge_id,
):
    kit, binding, limits = _material(challenge_id)
    assert (
        verify_direct_resource_policy(binding, limits)
        == kit["construction_limits_digest"]
    )
    assert (
        verify_direct_resource_policy(kit, limits) == kit["construction_limits_digest"]
    )


@pytest.mark.parametrize("challenge_id", FAMILIES)
@pytest.mark.parametrize(
    "key", ["train_digest", "interface_digest", "construction_limits_digest"]
)
def test_physical_guard_refuses_changed_or_missing_kit_pin(challenge_id, key):
    _, binding, limits = _material(challenge_id)
    for changed in (
        {**binding, key: "sha256:" + "0" * 64},
        {k: v for k, v in binding.items() if k != key},
    ):
        with pytest.raises(
            RecipeRefused, match="construction_resource_policy_binding_invalid"
        ):
            verify_direct_resource_policy(changed, limits)


@pytest.mark.parametrize(
    "field",
    ["cpu_count_max", "memory_bytes_max", "total_reconstruction_wall_seconds_max"],
)
def test_reauthored_physical_limits_refuse_even_with_self_consistent_digest(field):
    _, binding, limits = _material(FAMILIES[0])
    limits["reconstruction_resource_policy"][field] += 1
    binding["construction_limits_digest"] = digest(canonical(limits))
    with pytest.raises(
        RecipeRefused, match="construction_resource_policy_binding_invalid"
    ):
        verify_direct_resource_policy(binding, limits)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "carbon.synthetic-linear-field-2d.construction-limits.v2"),
        ("scope", "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY"),
    ],
)
def test_physical_schema_scope_cannot_be_relabelled(field, value):
    _, binding, limits = _material(FAMILIES[1])
    limits[field] = value
    binding["construction_limits_digest"] = digest(canonical(limits))
    with pytest.raises(
        RecipeRefused, match="construction_resource_policy_binding_invalid"
    ):
        verify_direct_resource_policy(binding, limits)


@pytest.mark.parametrize(
    "challenge_id", ["f02", "f08", "f08-ribbed-bracket", "unknown-public-challenge"]
)
def test_unknown_physical_id_cannot_borrow_synthetic_limits(challenge_id):
    material = synthetic_linear_field_2d.bundle_material()
    kit = {**material["construction_kit"], "id": challenge_id}
    with pytest.raises(
        RecipeRefused, match="construction_resource_policy_binding_invalid"
    ):
        verify_direct_resource_policy(kit, material["construction_limits_document"])


@pytest.mark.parametrize(
    "extra",
    [
        {"id": "synthetic-linear-field-2d"},
        {"version": "1.1"},
        {"challenge_version": "99.0"},
    ],
)
def test_conflicting_alias_or_unknown_version_refuses(extra):
    _, binding, limits = _material(FAMILIES[0])
    with pytest.raises(
        RecipeRefused, match="construction_resource_policy_binding_invalid"
    ):
        verify_direct_resource_policy({**binding, **extra}, limits)


def test_physical_guard_checks_actual_worker_even_with_frozen_trusted_kit(monkeypatch):
    kit, binding, limits = _material(FAMILIES[0])
    material = physical_public.trusted_material(FAMILIES[0], "1.0")
    monkeypatch.setattr(
        physical_public, "trusted_material", lambda *args: deepcopy(material)
    )
    monkeypatch.setattr(
        physical_public, "construction_kit", lambda *args: deepcopy(kit)
    )
    profile = deepcopy(
        research_carrier._worker_profile(
            None, research_carrier.LIBRARY_BUILD_PROVENANCE
        ).body
    )
    profile["cpu"]["count"] += 1
    monkeypatch.setattr(
        research_carrier, "_worker_profile", lambda *args: SimpleNamespace(body=profile)
    )
    with pytest.raises(RecipeRefused, match="construction_resource_policy_unserved"):
        verify_direct_resource_policy(binding, limits)


@pytest.mark.parametrize(
    "bad_binding",
    [
        None,
        {},
        {"challenge_id": []},
        {"challenge_id": "electric-motor-magnetics", "challenge_version": None},
    ],
)
def test_invalid_identity_returns_typed_refusal(bad_binding):
    with pytest.raises(
        RecipeRefused, match="construction_resource_policy_binding_invalid"
    ):
        verify_direct_resource_policy(bad_binding, {})
