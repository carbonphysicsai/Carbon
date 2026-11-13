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

The owner accepted the larger profile for mainnet 116 on the GPUYard validator
(OWNER-LARGE-MODEL-PROFILE-APPLIED-GPUYARD-MAINNET-01, 2026-11-13). That
acceptance is scoped here to exactly the two device-class entries
`hardware_acceptance` opens for finney, and to no other entry or network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from carbon.reconstruction import hardware_acceptance
from carbon.reconstruction.worker import model

pytestmark = pytest.mark.invariant

ROOT = Path(__file__).resolve().parents[2]
HOST_CLASS = ROOT / "carbon" / "challenge_validator" / "validator-host-class.json"
#: The networks the owner accepted the larger profile on.
ACCEPTED_NETWORKS = frozenset({"testnet"})
#: The one mainnet acceptance of the larger profile: finney 116 on the GPUYard validator
#: (OWNER-LARGE-MODEL-PROFILE-APPLIED-GPUYARD-MAINNET-01), for exactly these (device class,
#: profile) entries and no others. The registry names a device kind, not a host.
MAINNET_RECORD = "OWNER-LARGE-MODEL-PROFILE-APPLIED-GPUYARD-MAINNET-01"
MAINNET_RECORD_FILE = (
    ROOT / ".agent" / "decisions" / ("2026-11-13-" + MAINNET_RECORD + ".md")
)
MAINNET_NETWORK = "finney"
MAINNET_ENTRIES = frozenset(
    {
        ("NVIDIA GeForce RTX 4090", hardware_acceptance.JAX_GPU),
        ("NVIDIA GeForce RTX 4090", hardware_acceptance.TORCH_GPU),
    }
)
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
                if network == MAINNET_NETWORK and (device, profile) in MAINNET_ENTRIES:
                    continue
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


def test_the_finney_acceptance_is_exactly_the_recorded_entries():
    """The registry opens finney for the recorded (device class, profile) entries, and only those."""
    opened = {
        (device, profile)
        for device, profiles in hardware_acceptance.ACCEPTED_DEVICE_CLASSES.items()
        for profile, entry in profiles.items()
        if MAINNET_NETWORK in entry["networks"]
    }
    assert opened == MAINNET_ENTRIES


def test_the_mainnet_record_carries_the_owners_words_and_no_host():
    text = MAINNET_RECORD_FILE.read_text(encoding="utf-8")
    assert text.startswith("# " + MAINNET_RECORD + ":")
    assert (
        "I accept the LARGE_MODEL worker profile (the same 2/4/16 GiB container "
        "limits and containment settings as testnet) on the GPUYard validator for "
        "mainnet 116, extending OWNER-LARGE-MODEL-PROFILE-APPLIED-TESTNET-01 and "
        "OWNER-CONTAINMENT-ACCEPT-GPUYARD-MAINNET-01."
    ) in text
    assert "12:57 CST" in text and "Deploy-C" in text
    assert not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", text), "a host address"


def test_any_other_non_testnet_entry_still_fails():
    """The acceptance widens nothing: another device, profile or network is still a mainnet profile."""
    host = {"scope": "DEVELOPMENT"}
    jax, torch = hardware_acceptance.JAX_GPU, hardware_acceptance.TORCH_GPU
    four = "NVIDIA GeForce RTX 4090"

    def entry(*networks):
        return {"record": "X", "networks": networks, "evidence": "X"}

    assert _mainnet_profiles(host, {four: {jax: entry("testnet", "finney")}}) == []
    assert _mainnet_profiles(host, {four: {torch: entry("testnet", "finney")}}) == []
    for classes, expected in (
        ({"NVIDIA A40": {jax: entry("testnet", "finney")}}, ("NVIDIA A40", jax)),
        ({"NVIDIA H100": {torch: entry("finney")}}, ("NVIDIA H100", torch)),
        ({four: {"other_profile": entry("finney")}}, (four, "other_profile")),
    ):
        assert _mainnet_profiles(host, classes) == [(*expected, "finney")]
    for network in ("mainnet", "localnet", "finney2", ""):
        assert _mainnet_profiles(host, {four: {jax: entry("testnet", network)}}) == [
            (four, jax, network)
        ]
    # finney opened for the recorded entry never hides a second network beside it
    assert _mainnet_profiles(host, {four: {jax: entry("finney", "mainnet")}}) == [
        (four, jax, "mainnet")
    ]
    assert _mainnet_profiles({"scope": "MAINNET"}, {}) == [
        ("validator host class", "MAINNET")
    ]
