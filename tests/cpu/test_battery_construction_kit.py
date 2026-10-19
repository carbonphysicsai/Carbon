"""The prospective Battery kit binds current public TRAIN and trusted limits."""

from types import SimpleNamespace

import pytest

from carbon.battery import campaign as battery_campaign
from carbon.battery import challenge, construction_kit, domain
from carbon.challenge_registry.campaigns import campaign_for


def test_battery_kit_uses_pinned_train_and_family_neutral_io():
    kit = construction_kit.construction_kit()
    campaign = campaign_for(
        {
            "id": challenge.CHALLENGE.challenge_id,
            "version": challenge.CHALLENGE.version,
        }
    )
    assert kit == campaign.construction_kit()
    assert callable(campaign.construction_reconstruct)
    assert kit["train_digest"] == "sha256:" + challenge.TRAIN_V1_SHA256
    assert (
        kit["construction_limits_digest"]
        == construction_kit.construction_limits_digest()
    )
    assert kit["interface_digest"] == construction_kit.interface_digest()
    document = construction_kit.interface_document()
    assert document["input"]["names"] == list(domain.INPUTS)
    assert document["output"]["voltage_v"] == [domain.GRID_POINTS]
    assert "family" not in str(document).lower()
    assert "level" not in str(document).lower()


def test_local_host_profile_cannot_substitute_for_challenge_limits():
    with pytest.raises(TypeError):
        construction_kit.construction_kit({"cpus": 2})
    limits = construction_kit.construction_limits_document()
    assert limits["scope"] == "PUBLIC_DEVELOPMENT_GRAPH_CPU"
    assert limits["worker"]["memory_bytes"] > 0
    assert "families" not in limits and "level" not in limits


def test_new_battery_manifest_records_direct_mode_without_a_legacy_level():
    product = SimpleNamespace(
        campaign_id="direct-test",
        agent="none",
        budget={},
        manifest_fields=lambda: {"agent": "none"},
    )
    arguments = {"owner": "owner", "implementation": {}, "images": []}
    historical = battery_campaign.manifest_document(product, **arguments)
    direct = battery_campaign.manifest_document(
        product,
        construction_mode="direct",
        **arguments,
    )
    assert "construction_mode" not in historical
    assert direct["construction_mode"] == "direct"
    assert "construction_level" not in direct
    with pytest.raises(ValueError, match="conflicts with a legacy level"):
        battery_campaign.manifest_document(
            product,
            construction_mode="direct",
            construction_level={"level": 2},
            **arguments,
        )
    with pytest.raises(ValueError, match="conflicts with a legacy level"):
        battery_campaign.manifest_document(
            product,
            construction_mode="catalogue",
            **arguments,
        )
