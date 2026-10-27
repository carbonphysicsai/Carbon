"""A pool-graded version is offered only once its owner constants are registered (Validator 06:55Z): until then it is
RESERVED, the page (which offers by status only) lists it as reserved, and selecting it is refused. It flips to
IMPLEMENTED in the same change that registers its constants, which this test ties across the grading constants
(`scoring/pool_constants.json`) and the published ones (`published_exam._REGISTERED_POOL`).
"""

from __future__ import annotations

import pytest

from carbon import challenge_registry as challenges
from carbon.challenge_registry import published_exam, registry
from carbon.scoring import pool_version

POOL = [
    ("electric-motor-magnetics", "1.5"),
    ("chip-cold-plate", "1.5"),
    ("f08-ribbed-bracket", "1.6"),
    ("f02", "2.5"),
]
NOTHING = challenges.HostFacts(frozenset())


def _status(key):
    return {(e.challenge_id, e.version): e.status for e in registry.entries()}[key]


def _constants_registered(key):
    try:
        pool_version.registered_policies(*key)
        pool_version.registered_a_multiplier(*key)
    except pool_version.PoolConstantsNotRegistered:
        return False
    return True


@pytest.mark.parametrize("key", POOL)
def test_the_registry_status_follows_the_registered_constants(key):
    registered = _constants_registered(key)
    assert _status(key) == (registry.IMPLEMENTED if registered else registry.RESERVED)


@pytest.mark.parametrize("key", POOL)
def test_the_grading_constants_and_the_published_ones_are_registered_together(key):
    """No version is offered to miners on one without the other: grading constants registered iff published."""
    assert (published_exam.registered_pool(*key) is not None) == _constants_registered(
        key
    )


def test_motor_1_5_is_offered_and_the_others_are_reserved_until_they_register():
    assert _status(("electric-motor-magnetics", "1.5")) == registry.IMPLEMENTED
    for key in POOL[1:]:
        assert _status(key) == registry.RESERVED, key


@pytest.mark.parametrize("key", POOL[1:])
def test_a_reserved_pool_version_is_listed_as_reserved_and_refuses_selection(key):
    listed = {
        (c["challenge_id"], c["version"]): c
        for c in challenges.catalog(NOTHING)["challenges"]
    }
    assert listed[key]["status"] == "RESERVED"
    assert all(
        not p["implemented"] and not p["usable_here"] for p in listed[key]["profiles"]
    )
    with pytest.raises(challenges.ChallengeNotImplemented):
        challenges.resolve(key[0], key[1], "cpu_research")


@pytest.mark.parametrize("key", POOL[1:])
def test_registering_the_published_constants_flips_the_version_to_offered(
    key, monkeypatch
):
    monkeypatch.setitem(
        published_exam._REGISTERED_POOL,
        key,
        dict(published_exam._REGISTERED_POOL[("electric-motor-magnetics", "1.5")]),
    )
    assert _status(key) == registry.IMPLEMENTED


def test_the_other_versions_of_the_same_challenges_stay_offered():
    for key in (
        ("chip-cold-plate", "1.4"),
        ("f08-ribbed-bracket", "1.5"),
        ("f02", "2.4"),
        ("electric-motor-magnetics", "1.4"),
    ):
        assert _status(key) == registry.IMPLEMENTED, key
