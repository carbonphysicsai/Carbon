"""No mainnet profile while the larger worker profile is on
(OWNER-LARGE-MODEL-PROFILE-APPLIED-TESTNET-01; the Lead's scoping (a)).

`LARGE_MODEL_PROFILE_APPLIED` is a module constant with no network condition
in code: any image built from a tree where it is True serves the larger
resources. The release rule (LANDING_QUEUE, item 13): no mainnet image from a
tree where the flag is True; the mainnet image is built from a later commit
with the flag False (owner-held).

This test fails when a mainnet profile is built in a tree with the flag on:
- the registered validator host class is scoped MAINNET;
- a validator GPU device class is accepted for a network other than testnet.
Either is the mainnet profile a mainnet image would be built for. Mainnet
needs its own acceptance of the larger profile first, or the flag False.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from carbon.reconstruction import hardware_acceptance
from carbon.reconstruction.worker import model

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
HOST_CLASS = ROOT / "carbon" / "challenge_validator" / "validator-host-class.json"
#: The networks the owner accepted the larger profile on.
ACCEPTED_NETWORKS = frozenset({"testnet"})
WHY = (
    "a mainnet profile is built while LARGE_MODEL_PROFILE_APPLIED is True "
    "(OWNER-LARGE-MODEL-PROFILE-APPLIED-TESTNET-01: testnet only); accept the "
    "larger profile for mainnet first, or set the flag False"
)


def _mainnet_profiles(host, classes):
    found = []
    if host["scope"] != "DEVELOPMENT":
        found.append(("validator host class", host["scope"]))
    for device, profiles in classes.items():
        for profile, entry in profiles.items():
            for network in sorted(set(entry["networks"]) - ACCEPTED_NETWORKS):
                found.append((device, profile, network))
    return found


def test_no_mainnet_profile_while_the_larger_profile_is_on():
    if model.LARGE_MODEL_PROFILE_APPLIED:
        host = json.loads(HOST_CLASS.read_bytes())
        classes = hardware_acceptance.ACCEPTED_DEVICE_CLASSES
        assert _mainnet_profiles(host, classes) == [], WHY


def test_the_check_sees_a_mainnet_profile():
    """The same check finds each kind of mainnet profile when one exists."""
    testnet = {"record": "X", "networks": ("testnet",), "evidence": "X"}
    mainnet = {**testnet, "networks": ("testnet", "mainnet")}
    development = {"scope": "DEVELOPMENT"}
    assert _mainnet_profiles(development, {"GPU": {"p": testnet}}) == []
    assert _mainnet_profiles(development, {"GPU": {"p": mainnet}}) == [
        ("GPU", "p", "mainnet")
    ]
    assert _mainnet_profiles({"scope": "MAINNET"}, {}) == [
        ("validator host class", "MAINNET")
    ]
