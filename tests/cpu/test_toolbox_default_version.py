"""A toolbox request that names no version is served the NEWEST open version of the
Challenge, as the Launchpad page offers it (owner decision U-f), not the first one
registered (Test Runner 05:10Z: a Cooling agent got the Level-0 1.0 example)."""

from __future__ import annotations

import pytest

from carbon.challenge_registry.campaigns import latest_ref
from scripts.dev.miner_launchpad import toolbox
from scripts.dev.miner_launchpad.controller import Rejected

CHALLENGES = (
    "electric-motor-magnetics",
    "chip-cold-plate",
    "f08-ribbed-bracket",
    "f02",
)


def _gradeable(challenge, version):
    from carbon.challenge_registry import published_exam

    return (challenge, version) not in published_exam._POOL_VERSIONS or (
        published_exam.registered_pool(challenge, version) is not None
    )


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_no_version_is_the_newest_open_gradeable_version_not_the_first_registered(
    challenge,
):
    from carbon.challenge_registry.registry import entries

    versions = [
        e.version for e in entries() if e.challenge_id == challenge and e.version
    ]
    served = latest_ref(challenge)["version"]
    gradeable = [v for v in versions if _gradeable(challenge, v)]
    assert served == max(gradeable, key=lambda v: tuple(map(int, v.split("."))))
    document = toolbox.for_request(None, {"challenge": challenge}, lanes={})
    assert document["challenge"]["version"] == served
    assert served != versions[0] or len(versions) == 1


def test_the_default_never_lands_on_a_pool_version_whose_constants_are_unregistered():
    from carbon.challenge_registry import published_exam

    for challenge in CHALLENGES:
        served = latest_ref(challenge)["version"]
        if (challenge, served) in published_exam._POOL_VERSIONS:
            assert published_exam.registered_pool(challenge, served) is not None
    # Cooling 1.5, F08 1.6 and F02 2.5 are pool versions with HUMAN_INPUT constants today.
    registered = set(published_exam._REGISTERED_POOL)
    for key in published_exam._POOL_VERSIONS - registered:
        assert latest_ref(key[0])["version"] != key[1], key


@pytest.mark.parametrize("challenge", ("electric-motor-magnetics", "chip-cold-plate"))
def test_motor_and_cooling_are_no_longer_served_the_level_0_example(challenge):
    document = toolbox.for_request(None, {"challenge": challenge}, lanes={})
    assert document["challenge"]["version"] != "1.0"


def test_a_named_version_is_still_taken_as_named():
    document = toolbox.for_request(
        None, {"challenge": "chip-cold-plate", "challenge_version": "1.4"}, lanes={}
    )
    assert document["challenge"]["version"] == "1.4"
    with pytest.raises(Rejected) as refused:
        toolbox.for_request(
            None, {"challenge": "chip-cold-plate", "challenge_version": "9.9"}, lanes={}
        )
    assert refused.value.code == "challenge_unknown"


def test_a_reserved_or_unknown_challenge_has_no_toolbox():
    assert latest_ref("photonic-coupler")["version"] is None
    assert latest_ref("not-a-challenge")["version"] is None
    with pytest.raises(Rejected) as refused:
        toolbox.for_request(None, {"challenge": "photonic-coupler"}, lanes={})
    assert refused.value.code == "challenge_unknown"
