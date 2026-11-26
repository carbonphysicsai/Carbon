"""OWNER-RTX6000ADA-BUILD-CLASS-01 (21 Nov 2026, under INFRA-17): the Lium RTX 6000 Ada is a GPU build class for JAX
and PyTorch on finney (later Motor versions), and on nothing else; the A100's acceptance is unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from carbon.reconstruction import hardware_acceptance as acceptance

ADA = "NVIDIA RTX 6000 Ada Generation"
RECORD = "OWNER-RTX6000ADA-BUILD-CLASS-01"


@pytest.mark.parametrize("profile", [acceptance.JAX_GPU, acceptance.TORCH_GPU])
def test_the_rtx_6000_ada_is_accepted_on_finney_for_both_profiles(profile):
    entry = acceptance.require_accepted(ADA, profile, "finney")
    assert entry["record"] == RECORD
    assert entry["by_network"]["finney"]["record"] == RECORD
    assert entry["networks"] == ("finney",)


@pytest.mark.parametrize("network", ["testnet", "local", "mainnet", None])
def test_the_rtx_6000_ada_is_accepted_on_no_other_network(network):
    with pytest.raises(acceptance.DeviceClassNotAccepted):
        acceptance.require_accepted(ADA, acceptance.JAX_GPU, network)


# "NVIDIA RTX A6000" is its own class since OWNER-A6000-48GB-BUILD-CLASS-01 (test_hardware_acceptance_a6000.py)
@pytest.mark.parametrize(
    "kind", ["NVIDIA RTX 6000 Ada", "NVIDIA RTX PRO 6000 Blackwell"]
)
def test_other_rtx_6000_names_are_not_entered(kind):
    with pytest.raises(acceptance.DeviceClassNotAccepted):
        acceptance.require_accepted(kind, acceptance.JAX_GPU, "finney")


def test_the_a100_acceptance_is_unchanged():
    entry = acceptance.require_accepted(
        "NVIDIA A100-SXM4-40GB", acceptance.TORCH_GPU, "finney"
    )
    assert entry["record"] == "OWNER-A100-40GB-BUILD-CLASS-01"


def test_the_entry_carries_the_owners_words_and_the_record_id_resolves():
    """The record left public main (owner G-LEAD-128); its id resolves by the public decision index (the private copy
    keeps its sha); the owner's words stay in the acceptance entry read here."""
    import json

    root = Path(__file__).resolve().parents[2]
    index = json.loads((root / "tests/invariants/decision_index.json").read_bytes())
    assert RECORD in index["ids"]
    evidence = acceptance._OWNER_RTX6000ADA_FINNEY["evidence"]
    assert "slots 4 at the first admission" in evidence and "finney" in evidence
