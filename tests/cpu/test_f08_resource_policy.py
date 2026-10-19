"""F08 source-owned guard admission; no model, EVAL or qualification evidence."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from carbon.challenge_kit import f08_public, f08_train, physical_public
from carbon.development_session import research_carrier
from carbon.development_session.bundle_construction_worker import (
    verify_direct_resource_policy,
)
from carbon.development_session.construction_recipe import RecipeRefused
from carbon.development_session.profile import canonical, digest


def _material():
    kit = f08_public.construction_kit(
        f08_train.CHALLENGE_ID, f08_train.CHALLENGE_VERSION
    )
    binding = {
        "challenge_id": kit["id"],
        "challenge_version": kit["version"],
        **{key: value for key, value in kit.items() if key not in ("id", "version")},
    }
    limits = f08_public.construction_limits_document(kit["id"], kit["version"])
    return kit, binding, limits


def test_f08_exact_kit_accepts_both_normal_binding_shapes():
    kit, binding, limits = _material()
    assert (
        verify_direct_resource_policy(kit, limits) == kit["construction_limits_digest"]
    )
    assert (
        verify_direct_resource_policy(binding, limits)
        == kit["construction_limits_digest"]
    )


@pytest.mark.parametrize(
    "key", ["train_digest", "interface_digest", "construction_limits_digest"]
)
def test_f08_missing_or_changed_artifact_pin_refuses(key):
    _, binding, limits = _material()
    for changed in (
        {k: v for k, v in binding.items() if k != key},
        {**binding, key: "sha256:" + "0" * 64},
    ):
        with pytest.raises(
            RecipeRefused, match="construction_resource_policy_binding_invalid"
        ):
            verify_direct_resource_policy(changed, limits)


@pytest.mark.parametrize(
    "extra",
    [
        {"challenge_version": "1.1"},
        {"challenge_version": "99.0"},
        {"challenge_id": "f08"},
        {"challenge_id": "f02"},
        {"challenge_id": "unknown-public-challenge"},
        {"id": "electric-motor-magnetics"},
        {"version": "1.1"},
    ],
)
def test_f08_unknown_identity_or_conflicting_alias_refuses(extra):
    _, binding, limits = _material()
    with pytest.raises(
        RecipeRefused, match="construction_resource_policy_binding_invalid"
    ):
        verify_direct_resource_policy({**binding, **extra}, limits)


@pytest.mark.parametrize(
    "field", ["schema", "scope", "cpu_count_max", "resource_schema"]
)
def test_f08_reauthored_limits_refuse_even_with_self_consistent_digest(field):
    _, binding, limits = _material()
    if field == "cpu_count_max":
        limits["reconstruction_resource_policy"][field] += 1
    elif field == "resource_schema":
        limits["reconstruction_resource_policy"]["schema"] = "carbon.unregistered.v1"
    else:
        limits[field] = "carbon.unregistered.v1"
    binding["construction_limits_digest"] = digest(canonical(limits))
    with pytest.raises(
        RecipeRefused, match="construction_resource_policy_binding_invalid"
    ):
        verify_direct_resource_policy(binding, limits)


def test_f08_cannot_borrow_another_physical_kit_limits():
    _, binding, _ = _material()
    limits = physical_public.construction_limits_document(
        "electric-motor-magnetics", "1.0"
    )
    binding["construction_limits_digest"] = digest(canonical(limits))
    with pytest.raises(
        RecipeRefused, match="construction_resource_policy_binding_invalid"
    ):
        verify_direct_resource_policy(binding, limits)


def test_f08_checks_actual_worker_against_frozen_source_material(monkeypatch):
    kit, binding, limits = _material()
    material = f08_public.trusted_material(kit["id"], kit["version"])
    monkeypatch.setattr(
        f08_public, "trusted_material", lambda *args: deepcopy(material)
    )
    monkeypatch.setattr(f08_public, "construction_kit", lambda *args: deepcopy(kit))
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


def test_f08_source_material_failure_is_typed_refusal(monkeypatch):
    _, binding, limits = _material()

    def unavailable(*args):
        raise OSError("fixture artifact unavailable")

    monkeypatch.setattr(f08_public, "trusted_material", unavailable)
    with pytest.raises(
        RecipeRefused, match="construction_resource_policy_binding_invalid"
    ):
        verify_direct_resource_policy(binding, limits)
