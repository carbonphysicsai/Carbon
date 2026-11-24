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
(OWNER-LARGE-MODEL-PROFILE-APPLIED-GPUYARD-MAINNET-01, 2026-11-13) and on the
Lambda A100 40GB build box (OWNER-LARGE-MODEL-PROFILE-APPLIED-A100-MAINNET-01,
2026-11-16) and on the Lium RTX 6000 Ada build boxes
(OWNER-LARGE-MODEL-PROFILE-APPLIED-ADA-MAINNET-01, 2026-11-21). Each acceptance is scoped here to exactly its two device-class
entries `hardware_acceptance` opens for finney, and to no other entry or network.
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
#: The second: finney 116 on the Lambda A100 40GB build box (OWNER-LARGE-MODEL-PROFILE-APPLIED-A100-MAINNET-01), for
#: exactly its two (device class, profile) entries.
A100_RECORD = "OWNER-LARGE-MODEL-PROFILE-APPLIED-A100-MAINNET-01"
A100_RECORD_FILE = ROOT / ".agent" / "decisions" / ("2026-11-16-" + A100_RECORD + ".md")
A100_ENTRIES = frozenset(
    {
        ("NVIDIA A100-SXM4-40GB", hardware_acceptance.JAX_GPU),
        ("NVIDIA A100-SXM4-40GB", hardware_acceptance.TORCH_GPU),
    }
)
#: The third: finney 116 on the Lium RTX 6000 Ada build boxes (OWNER-LARGE-MODEL-PROFILE-APPLIED-ADA-MAINNET-01), for
#: exactly its two (device class, profile) entries.
ADA_RECORD = "OWNER-LARGE-MODEL-PROFILE-APPLIED-ADA-MAINNET-01"
ADA_RECORD_FILE = ROOT / ".agent" / "decisions" / ("2026-11-21-" + ADA_RECORD + ".md")
ADA_ENTRIES = frozenset(
    {
        ("NVIDIA RTX 6000 Ada Generation", hardware_acceptance.JAX_GPU),
        ("NVIDIA RTX 6000 Ada Generation", hardware_acceptance.TORCH_GPU),
    }
)
#: The fourth: finney 116 on the Lambda RTX A6000 48 GB build boxes (OWNER-LARGE-MODEL-PROFILE-APPLIED-A6000-MAINNET-01,
#: typed in the exam-motor seat ~2026-11-24T01:25Z, OWNER_LINES.md L675), for exactly the ONE entry its build class has
#: (OWNER-A6000-48GB-BUILD-CLASS-01 measured JAX only; v2 5817). The public-repo stop keeps the record off .agent/decisions:
#: the owner's words live in OWNER_LINES.md and in this constant.
A6000_RECORD = "OWNER-LARGE-MODEL-PROFILE-APPLIED-A6000-MAINNET-01"
A6000_WORDS = (
    "I accept the LARGE_MODEL worker profile (the same 2/4/16 GiB container limits and containment settings as "
    "testnet) on the Lambda RTX A6000 48 GB build boxes for mainnet 116 "
    "(OWNER-LARGE-MODEL-PROFILE-APPLIED-A6000-MAINNET-01)."
)
A6000_ENTRIES = frozenset({("NVIDIA RTX A6000", hardware_acceptance.JAX_GPU)})
MAINNET_ENTRIES = (
    frozenset(
        {
            ("NVIDIA GeForce RTX 4090", hardware_acceptance.JAX_GPU),
            ("NVIDIA GeForce RTX 4090", hardware_acceptance.TORCH_GPU),
        }
    )
    | A100_ENTRIES
    | ADA_ENTRIES
    | A6000_ENTRIES
)
#: The launch rehearsals (owner G-LEAD-58, "rehearsals build on the launch build class"; the record
#: G-LEAD-58-LAUNCH-REHEARSALS in `hardware_acceptance`): the disposable LOCALNET chain, never mainnet, for exactly the
#: launch build classes' entries. No mainnet image is built for localnet; any other localnet entry still fails.
REHEARSAL_NETWORK = "localnet"
REHEARSAL_RECORD = "G-LEAD-58-LAUNCH-REHEARSALS"
REHEARSAL_ENTRIES = A100_ENTRIES | frozenset(
    {("NVIDIA RTX A6000", hardware_acceptance.JAX_GPU)}
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
                if (
                    network == REHEARSAL_NETWORK
                    and (device, profile) in REHEARSAL_ENTRIES
                    and entry.get("by_network", {}).get(network, {}).get("record")
                    == REHEARSAL_RECORD
                ):
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


def test_the_localnet_rehearsal_entries_are_exactly_the_recorded_ones():
    """G-LEAD-58: localnet is opened for exactly the launch classes' rehearsal entries, each under its own record."""
    opened = {
        (device, profile)
        for device, profiles in hardware_acceptance.ACCEPTED_DEVICE_CLASSES.items()
        for profile, entry in profiles.items()
        if REHEARSAL_NETWORK in entry["networks"]
    }
    assert opened == REHEARSAL_ENTRIES
    for device, profile in opened:
        entry = hardware_acceptance.ACCEPTED_DEVICE_CLASSES[device][profile]
        assert entry["by_network"][REHEARSAL_NETWORK]["record"] == REHEARSAL_RECORD
    # a localnet entry without the rehearsal record is still a mainnet profile
    host = {"scope": "DEVELOPMENT"}
    device, profile = min(REHEARSAL_ENTRIES)
    plain = {"record": "X", "networks": ("localnet",), "evidence": "X"}
    assert _mainnet_profiles(host, {device: {profile: plain}}) == [
        (device, profile, REHEARSAL_NETWORK)
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


def test_the_a100_record_carries_the_owners_words_and_no_host():
    text = A100_RECORD_FILE.read_text(encoding="utf-8")
    assert text.startswith("# " + A100_RECORD + ":")
    assert (
        "I accept the LARGE_MODEL worker profile (the same 2/4/16 GiB container limits and "
        "containment settings\nas testnet) on the Lambda A100 40GB build box for mainnet 116."
    ) in text
    assert "13:41 CST" in text and "TE3 session" in text
    assert not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", text), "a host address"


def test_the_a100_acceptance_widens_nothing_else():
    """Another A100 variant, another profile or another network is still a mainnet profile."""
    host = {"scope": "DEVELOPMENT"}
    jax = hardware_acceptance.JAX_GPU
    a100 = "NVIDIA A100-SXM4-40GB"

    def entry(*networks):
        return {"record": "X", "networks": networks, "evidence": "X"}

    assert _mainnet_profiles(host, {a100: {jax: entry("finney")}}) == []
    for classes, expected in (
        (
            {"NVIDIA A100-SXM4-80GB": {jax: entry("finney")}},
            ("NVIDIA A100-SXM4-80GB", jax),
        ),
        ({a100: {"other_profile": entry("finney")}}, (a100, "other_profile")),
    ):
        assert _mainnet_profiles(host, classes) == [(*expected, "finney")]
    assert _mainnet_profiles(host, {a100: {jax: entry("finney", "mainnet")}}) == [
        (a100, jax, "mainnet")
    ]


def test_the_ada_record_carries_the_owners_words_and_no_host():
    text = ADA_RECORD_FILE.read_text(encoding="utf-8")
    assert text.startswith("# " + ADA_RECORD + ":")
    assert (
        "I accept the LARGE_MODEL worker profile (the same 2/4/16 GiB container limits and "
        "containment settings\nas testnet) on the Lium RTX 6000 Ada build boxes for mainnet 116"
    ) in text
    assert "22:4" in text and "door-code seat" in text
    assert not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", text), "a host address"


def test_the_ada_acceptance_widens_nothing_else():
    """Another RTX 6000 name, another profile or another network is still a mainnet profile."""
    host = {"scope": "DEVELOPMENT"}
    jax = hardware_acceptance.JAX_GPU
    ada = "NVIDIA RTX 6000 Ada Generation"

    def entry(*networks):
        return {"record": "X", "networks": networks, "evidence": "X"}

    assert _mainnet_profiles(host, {ada: {jax: entry("finney")}}) == []
    for classes, expected in (
        # the A6000's own line (A6000_RECORD) opens its JAX entry only; its PyTorch profile is still a mainnet profile
        (
            {"NVIDIA RTX A6000": {hardware_acceptance.TORCH_GPU: entry("finney")}},
            ("NVIDIA RTX A6000", hardware_acceptance.TORCH_GPU),
        ),
        ({ada: {"other_profile": entry("finney")}}, (ada, "other_profile")),
    ):
        assert _mainnet_profiles(host, classes) == [(*expected, "finney")]
    assert _mainnet_profiles(host, {ada: {jax: entry("finney", "mainnet")}}) == [
        (ada, jax, "mainnet")
    ]


def test_the_a6000_line_is_the_owners_words_for_exactly_its_one_entry():
    """OWNER-LARGE-MODEL-PROFILE-APPLIED-A6000-MAINNET-01: the owner's words, and finney opened for the A6000 JAX entry
    only (its build class measured JAX only); another A6000 profile or network is still a mainnet profile.
    """
    assert A6000_WORDS.startswith("I accept the LARGE_MODEL worker profile")
    assert "Lambda RTX A6000 48 GB build boxes for mainnet 116" in A6000_WORDS
    assert A6000_RECORD in A6000_WORDS
    assert not re.search(r"\d{1,3}(\.\d{1,3}){3}", A6000_WORDS), "a host address"
    host = {"scope": "DEVELOPMENT"}
    a6000 = "NVIDIA RTX A6000"
    jax, torch = hardware_acceptance.JAX_GPU, hardware_acceptance.TORCH_GPU

    def entry(*networks):
        return {"record": "X", "networks": networks, "evidence": "X"}

    assert _mainnet_profiles(host, {a6000: {jax: entry("finney")}}) == []
    assert _mainnet_profiles(host, {a6000: {torch: entry("finney")}}) == [
        (a6000, torch, "finney")
    ]
    assert _mainnet_profiles(host, {a6000: {jax: entry("mainnet")}}) == [
        (a6000, jax, "mainnet")
    ]
