"""OWNER-A6000-48GB-BUILD-CLASS-01 (owner G-LEAD-60, 23 Nov 2026) accepted the Lambda RTX A6000 48 GB VM as the JAX build
class of Motor 1.9 and RB 2.0. Its FINNEY entry waits the owner's LARGE_MODEL worker-profile line for this class (v2 5793:
G-LEAD-60 names no profile), so today the A6000 is entered only on the rehearsal localnet (G-LEAD-58).
"""

from __future__ import annotations

import pytest

from carbon.reconstruction import hardware_acceptance as acceptance

A6000 = "NVIDIA RTX A6000"


def test_the_a6000_is_accepted_for_jax_rehearsal_builds_on_localnet_only():
    entry = acceptance.require_accepted(A6000, acceptance.JAX_GPU, "localnet")
    assert entry["networks"] == ("localnet",)
    assert entry["by_network"]["localnet"]["record"] == "G-LEAD-58-LAUNCH-REHEARSALS"
    for network in ("finney", "testnet", "mainnet", "", None):
        with pytest.raises(acceptance.DeviceClassNotAccepted):
            acceptance.require_accepted(A6000, acceptance.JAX_GPU, network)


def test_the_finney_record_is_kept_for_the_owner_line():
    # re-entered with the owner's LARGE_MODEL line; its class evidence (infra's record) stays as written
    record = acceptance._OWNER_A6000_48GB_FINNEY
    assert record["record"] == "OWNER-A6000-48GB-BUILD-CLASS-01"
    assert record["networks"] == ("finney",)
    assert (
        "54446e4a6675e2e67466961af8ada2d26da2b904ebb0f615d77d80ee4f2e1535"
        in record["evidence"]
    )


def test_the_a6000_pytorch_profile_is_not_accepted():
    with pytest.raises(acceptance.DeviceClassNotAccepted):
        acceptance.require_accepted(A6000, acceptance.TORCH_GPU, "localnet")
