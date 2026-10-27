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


@pytest.mark.parametrize("challenge", CHALLENGES)
def test_no_version_is_the_newest_open_version_not_the_first_registered(challenge):
    from carbon.challenge_registry.registry import entries

    versions = [
        e.version for e in entries() if e.challenge_id == challenge and e.version
    ]
    served = latest_ref(challenge)["version"]
    assert served == max(versions, key=lambda v: tuple(map(int, v.split("."))))
    document = toolbox.for_request(None, {"challenge": challenge}, lanes={})
    assert document["challenge"]["version"] == served
    assert served != versions[0] or len(versions) == 1


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
