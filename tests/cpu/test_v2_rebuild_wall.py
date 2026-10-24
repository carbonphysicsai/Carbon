"""The graph route v2 versions' 30-minute rebuild wall
(OWNER-SANDBOX-REBUILD-WALL-01, testnet; the Validator's design and
conditions, 2026-10-23).

Motor 1.4, Cooling 1.4, F08 1.5 and F02 2.4 build and infer under an 1800 s
wall, in their limits document and in the launch; every older version stays
byte for byte at 600 s. Claims tested:

- each new version's limits document moves only by its two wall fields:
  set back to 600 they reproduce the document served before this change;
- the older versions' kits are unchanged (`test_graph_route_v2.BASE_KITS`)
  and the shared C-03 profiles keep their digests;
- the sandbox enforces the wall: a new version's launch runs under 1800 s
  (its profile states it), an older one is refused beyond 600 s, and the
  longer wall is never available to the miner lane, the G5 lane or
  dependency preparation.
"""

from __future__ import annotations

import pytest
from test_graph_route_v2 import BASE_KITS

from carbon.challenge_kit import physical_material, version_registry
from carbon.challenge_kit.version_registry import REBUILD_LIMIT_SECONDS
from carbon.development_session import bundle_construction_worker as worker
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_carrier import (
    G5_PROVENANCE,
    LIBRARY_BUILD_PROVENANCE,
    LIBRARY_PREP_PROVENANCE,
    _run_locked,
    _worker_profile,
)

NEW = sorted(version_registry.keys(graph_adapter="v2"))
WALLS = ("build_wall_seconds_max", "inference_wall_seconds_max")

#: Each new version's limits digest as served at 600 s (rc8 1ea4c49ad), the
#: document its 600-second form must reproduce.
AT_600 = {
    ("chip-cold-plate", "1.4"): (
        "203847f2cdd826190a1a2b607f5d9fd750e7e76882d9b103942ac7545906ac29"
    ),
    ("electric-motor-magnetics", "1.4"): (
        "07d08ec38eda6f78b34880846e3dc9cbbf840b2f732cd5517b77373a6fe71d45"
    ),
    ("f02", "2.4"): "639c1bfb05965cde5bab24e1e95271dbc6df8de4d48a57068cbb9ff18c5dc3eb",
    ("f08-ribbed-bracket", "1.5"): (
        "ae6be62f31881aa2ce41e5dd631349672d101fdb4b351e9a3260f4bf0e8e3650"
    ),
}
#: The two new versions whose served catalog the catalog freeze moved (frozen
#: catalog 0530c1d41, "catalog v2 entries"): the catalog digest served at rc10
#: 385bc1279 and the 600-second limits digest then. Their documents differ now
#: in `backbone_catalog.digest` only (asserted below). Motor 1.4 and Ribbed
#: Bracket 1.5 did not move.
FREEZE_MOVED = {
    ("chip-cold-plate", "1.4"): (
        "sha256:f6a9b9c5ca937cd491d9df97c43e309832f87f2897cce2828e8810e3f2cc5924",
        "35f7a59244dc715b62915758b9896c6069d1169c5ac244595db4e8b9d5ec9e60",
    ),
    ("f02", "2.4"): (
        "sha256:a33b56d54e804f3bd2c82580cd518b54c1296e82a3a020b4cfe1d67830bdc63d",
        "a6195b4ea335306f10ad647caf9d9f51748b9ca0339916ac69ddb5c0ebd2c50c",
    ),
}
#: The new versions' kits, re-pinned once: new version, pre-publish,
#: OWNER-SANDBOX-REBUILD-WALL-01.
NEW_KITS = {
    ("chip-cold-plate", "1.4"): (
        "bf94ffc1d6008c5abb81203c3bd54c232f3b3a923e3ef93a19e9a8d57a0c547d"
    ),
    ("electric-motor-magnetics", "1.4"): (
        "3c3a854f4e035b70b542d91222b83d4bb3fcb674c60526f00bf51c3e3d3c4b78"
    ),
    ("f02", "2.4"): "10836cbdd3a266cd73152c27e980e8f2e7db191bd3077b8b0bcd06321c34c281",
    ("f08-ribbed-bracket", "1.5"): (
        "2c54ee8493a87bb2f04bf6deabf85d18f865a917165f8df92943c90d24f698cf"
    ),
}
#: The shared C-03 profiles (CPU build, G5 compile) at rc8 1ea4c49ad.
C03_PROFILES = {
    LIBRARY_BUILD_PROVENANCE: (
        "sha256:0d1168fb5bbffde24617c54df2cedfcb092d73b97f88fa8aae400f430869347f"
    ),
    G5_PROVENANCE: (
        "sha256:8893b027e89a6635964f45704afad73fcfc2a2dcefaec899a1a45457ab17dd7e"
    ),
}


def _limits(cid, version):
    return physical_material._public(cid).construction_limits_document(cid, version)


def _binding(cid, version):
    kit = physical_material.construction_kit(cid, version)
    return {
        "challenge_id": cid,
        "challenge_version": version,
        "train_digest": kit["train_digest"],
        "interface_digest": kit["interface_digest"],
        "construction_limits_digest": kit["construction_limits_digest"],
    }


def test_exactly_the_graph_route_v2_versions_declare_the_wall():
    assert REBUILD_LIMIT_SECONDS == 1800
    assert NEW == sorted(NEW_KITS) == sorted(AT_600)
    for key, entry in version_registry.VERSIONS.items():
        expected = REBUILD_LIMIT_SECONDS if key in NEW_KITS else None
        assert entry.rebuild_wall_seconds == expected, key


@pytest.mark.parametrize("key", NEW)
def test_a_new_version_moves_only_by_its_two_wall_fields(key):
    document = _limits(*key)
    policy = document["reconstruction_resource_policy"]
    assert [policy[name] for name in WALLS] == [REBUILD_LIMIT_SECONDS] * 2
    assert physical_material.construction_kit(*key)["construction_limits_digest"] == (
        "sha256:" + NEW_KITS[key]
    )
    at_600 = {
        **document,
        "reconstruction_resource_policy": {**policy, **dict.fromkeys(WALLS, 600)},
    }
    assert digest(canonical(at_600)) == "sha256:" + AT_600[key]
    if key in FREEZE_MOVED:
        old_catalog, old_at_600 = FREEZE_MOVED[key]
        assert document["backbone_catalog"]["digest"] != old_catalog
        restored = {
            **at_600,
            "backbone_catalog": {**at_600["backbone_catalog"], "digest": old_catalog},
        }
        assert digest(canonical(restored)) == "sha256:" + old_at_600


@pytest.mark.parametrize("key", sorted(BASE_KITS))
def test_an_older_version_keeps_600_seconds(key):
    policy = _limits(*key)["reconstruction_resource_policy"]
    assert [policy[name] for name in WALLS] == [600, 600]
    assert worker.rebuild_wall_kwargs(_limits(*key)) == {}


def test_the_shared_c03_profiles_keep_their_digests():
    for provenance, pinned in C03_PROFILES.items():
        assert _worker_profile(None, provenance).digest == pinned


def test_the_rebuild_profile_differs_only_in_its_wall_and_resource_class():
    base = _worker_profile(None, LIBRARY_BUILD_PROVENANCE).body
    wall = _worker_profile(
        None, LIBRARY_BUILD_PROVENANCE, rebuild_wall_seconds=REBUILD_LIMIT_SECONDS
    ).body
    assert wall["deadline_seconds"] == 1800 and base["deadline_seconds"] == 600
    assert wall["b02c"]["resource_class_digest"] == digest(
        b"2cpu-4gib-noswap-1800seconds"
    )
    assert base["b02c"]["resource_class_digest"] == digest(
        b"2cpu-4gib-noswap-600seconds"
    )
    rest = {k: v for k, v in wall.items() if k not in ("deadline_seconds", "b02c")}
    assert rest == {
        k: v for k, v in base.items() if k not in ("deadline_seconds", "b02c")
    }
    for refused in (600, 1799, 3600):
        with pytest.raises(ValueError, match="unsupported rebuild wall"):
            _worker_profile(
                None, LIBRARY_BUILD_PROVENANCE, rebuild_wall_seconds=refused
            )
    with pytest.raises(ValueError, match="unsupported rebuild wall"):
        _worker_profile(None, G5_PROVENANCE, rebuild_wall_seconds=1800)


@pytest.mark.parametrize("key", NEW + sorted(BASE_KITS))
def test_each_version_s_launch_takes_its_own_wall(key):
    """The worker reads the wall from the version's trusted document, which
    the resource-policy check accepts against the profile that enforces it."""
    document = _limits(*key)
    assert worker.verify_direct_resource_policy(_binding(*key), document) == (
        physical_material.construction_kit(*key)["construction_limits_digest"]
    )
    expected = (
        {"rebuild_wall_seconds": REBUILD_LIMIT_SECONDS} if key in NEW_KITS else {}
    )
    assert worker.rebuild_wall_kwargs(document) == expected
    assert worker.rebuild_wall_kwargs(None) == {}


def _launch(seconds, provenance=LIBRARY_BUILD_PROVENANCE, **kwargs):
    """The carrier's wall check, stopped at the next check (no stage given)."""
    return _run_locked(
        None,
        owner="o",
        identity="i",
        source="",
        files=None,
        image=None,
        seconds=seconds,
        provenance=provenance,
        extra_resources={},
        **kwargs,
    )


def test_the_sandbox_enforces_1800_for_a_new_version_and_600_otherwise():
    wall = {"rebuild_wall_seconds": REBUILD_LIMIT_SECONDS}
    # Within its wall a new version's launch passes the wall check (and stops
    # at the next one); beyond it, refused.
    for seconds in (40, 600, 601, 1800):
        with pytest.raises(ValueError, match="closed stage required"):
            _launch(seconds, **wall)
    with pytest.raises(ValueError, match="bounded worker wall allowance"):
        _launch(1801, **wall)
    # An older version's launch is refused beyond 600 s.
    with pytest.raises(ValueError, match="closed stage required"):
        _launch(600)
    for seconds in (601, 1800):
        with pytest.raises(ValueError, match="bounded worker wall allowance"):
            _launch(seconds)


@pytest.mark.parametrize(
    "provenance", ["MINER_SELF_REPORTED", G5_PROVENANCE, LIBRARY_PREP_PROVENANCE]
)
def test_the_longer_wall_is_never_another_lane_s(provenance):
    with pytest.raises(ValueError, match="unsupported rebuild wall"):
        _launch(600, provenance, rebuild_wall_seconds=REBUILD_LIMIT_SECONDS)
    with pytest.raises(ValueError, match="unsupported rebuild wall"):
        _launch(600, rebuild_wall_seconds=1200)
