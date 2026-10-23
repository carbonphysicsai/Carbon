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

#: Each new version's limits digest as served at 600 s (rc7 ba04fb6b7), the
#: document its 600-second form must reproduce.
AT_600 = {
    ("chip-cold-plate", "1.4"): (
        "7578be6dac4c19d1c49377728f018aa575c364cfa40088aadf111011e93c9546"
    ),
    ("electric-motor-magnetics", "1.4"): (
        "a2855d5a4a8e7cc8bb20082e9a0ffe8c5f9631ee3ffd22b31c8dd9f36db8d345"
    ),
    ("f02", "2.4"): "556d0c14c4111ed7604dd9f44e17c999913fa1f2232b967f300a7c21ac37eaf9",
    ("f08-ribbed-bracket", "1.5"): (
        "0efc4dcda08c571215898b60478a6c4878f2fc1f2ce1afffbdb298ccf532f62f"
    ),
}
#: The new versions' kits, re-pinned once: new version, pre-publish,
#: OWNER-SANDBOX-REBUILD-WALL-01.
NEW_KITS = {
    ("chip-cold-plate", "1.4"): (
        "b6d5b6181886fc08b2e738c525df68a8ea4dd501df5f103cfd43c6787f61945b"
    ),
    ("electric-motor-magnetics", "1.4"): (
        "efdbde97bbfea10587912f5b04707fe6a40dc94aa8527e6efb595636da27ac00"
    ),
    ("f02", "2.4"): "8188f29dbb9f11d2c41c8a552b18981f163814c15e3f1e2d3f65857900b4c9d3",
    ("f08-ribbed-bracket", "1.5"): (
        "9da5628287dbbb4d68cde35c55b86758a0fb490f91060c81194b55d652a7ecb2"
    ),
}
#: The shared C-03 profiles (CPU build, G5 compile) at rc7 ba04fb6b7.
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
