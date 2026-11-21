"""OWNER-A100-40GB-BUILD-CLASS-01 (16 Nov 2026): the Lambda A100 40GB SXM4 is a GPU build class for JAX and PyTorch on
finney, and on nothing else; every other class's acceptance is unchanged."""

from __future__ import annotations

from pathlib import Path

import pytest

from carbon.reconstruction import hardware_acceptance as acceptance

A100 = "NVIDIA A100-SXM4-40GB"


@pytest.mark.parametrize("profile", [acceptance.JAX_GPU, acceptance.TORCH_GPU])
def test_the_a100_40gb_is_accepted_on_finney_for_both_profiles(profile):
    entry = acceptance.require_accepted(A100, profile, "finney")
    assert entry["record"] == "OWNER-A100-40GB-BUILD-CLASS-01"
    assert entry["by_network"]["finney"]["record"] == "OWNER-A100-40GB-BUILD-CLASS-01"
    assert entry["networks"] == ("finney",)


@pytest.mark.parametrize("network", ["testnet", "local", None])
def test_the_a100_40gb_is_accepted_on_no_other_network(network):
    with pytest.raises(acceptance.DeviceClassNotAccepted):
        acceptance.require_accepted(A100, acceptance.JAX_GPU, network)


@pytest.mark.parametrize(
    "kind", ["NVIDIA A100-SXM4-80GB", "NVIDIA A100 80GB PCIe", "NVIDIA A100-PCIE-40GB"]
)
def test_other_a100_variants_are_not_entered(kind):
    with pytest.raises(acceptance.DeviceClassNotAccepted):
        acceptance.require_accepted(kind, acceptance.JAX_GPU, "finney")


def test_the_other_classes_are_unchanged():
    assert set(acceptance.ACCEPTED_DEVICE_CLASSES) == {
        "NVIDIA A40",
        "NVIDIA GeForce RTX 4090",
        A100,
        # OWNER-RTX6000ADA-BUILD-CLASS-01 (21 Nov 2026): Motor 1.9's build class, finney only
        "NVIDIA RTX 6000 Ada Generation",
    }
    assert acceptance.ACCEPTED_DEVICE_CLASSES["NVIDIA A40"][acceptance.JAX_GPU][
        "networks"
    ] == ("testnet",)
    assert acceptance.ACCEPTED_DEVICE_CLASSES["NVIDIA GeForce RTX 4090"][
        acceptance.TORCH_GPU
    ]["networks"] == ("testnet", "finney")


def test_the_record_names_the_owners_words():
    root = Path(__file__).resolve().parents[2]
    record = (
        root / ".agent/decisions/2026-11-16-OWNER-A100-40GB-BUILD-CLASS-01.md"
    ).read_text()
    assert "I accept the Lambda 1× A100 40GB SXM4 as a Carbon GPU build class" in record
    assert "finney" in record
