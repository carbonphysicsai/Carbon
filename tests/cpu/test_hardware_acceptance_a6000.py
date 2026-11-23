"""OWNER-A6000-48GB-BUILD-CLASS-01 (owner G-LEAD-60, 23 Nov 2026): the Lambda RTX A6000 48 GB VM is a GPU build class
for Motor 1.9 and RB 2.0 on finney only, JAX only (its class record, a6000-class-check.json 54446e4a, measured JAX).
"""

from __future__ import annotations

import pytest

from carbon.reconstruction import hardware_acceptance as acceptance

A6000 = "NVIDIA RTX A6000"


def test_the_a6000_is_accepted_for_jax_builds_on_finney_only():
    entry = acceptance.require_accepted(A6000, acceptance.JAX_GPU, "finney")
    assert entry["record"] == "OWNER-A6000-48GB-BUILD-CLASS-01"
    assert entry["networks"] == ("finney",)
    assert (
        "54446e4a6675e2e67466961af8ada2d26da2b904ebb0f615d77d80ee4f2e1535"
        in entry["evidence"]
    )
    for network in ("testnet", "localnet", "mainnet", "", None):
        with pytest.raises(acceptance.DeviceClassNotAccepted):
            acceptance.require_accepted(A6000, acceptance.JAX_GPU, network)


def test_the_a6000_pytorch_profile_is_not_accepted():
    with pytest.raises(acceptance.DeviceClassNotAccepted):
        acceptance.require_accepted(A6000, acceptance.TORCH_GPU, "finney")
