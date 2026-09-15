"""Permanent authority boundaries for C-W1-D1's non-official testnet profile."""

import inspect
from pathlib import Path

import pytest

from carbon.development_testnet import (
    DevelopmentTestnetFailure,
    DevelopmentTestnetPublisher,
    LocalRetentionEvidence,
)

ROOT = Path(__file__).parents[2]
pytestmark = pytest.mark.invariant


@pytest.mark.invariant
def test_official_cw1_and_archive_gate_remain_open_and_distinct():
    ticket = (ROOT / ".agent/tickets/C-W1_testnet_eligibility.md").read_text()
    graph = (ROOT / ".agent/plans/C1_DEPENDENCY_GRAPH.md").read_text()
    assert "official slice `future_reserved`" in ticket
    assert "official path unchanged; development all-burn only" in graph
    assert "C-09+C-EA2+real C1" in graph


@pytest.mark.invariant
def test_runtime_has_no_archive_provider_or_official_result_dependency():
    source = "\n".join(
        path.read_text()
        for path in sorted((ROOT / "carbon/development_testnet").glob("*.py"))
    ).lower()
    assert "carbon.evidence_archive" not in source
    assert "carbon.scoring" not in source
    assert "hippius" not in source
    assert "boto" not in source
    assert "testnetwinnerweightintent" not in source


@pytest.mark.invariant
def test_local_retention_cannot_claim_archive_or_host_loss_recovery():
    evidence = LocalRetentionEvidence(
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
        1,
    )
    assert evidence.host_loss_recoverable is False
    assert evidence.archive_acknowledgement is None
    with pytest.raises(DevelopmentTestnetFailure):
        LocalRetentionEvidence(
            "sha256:" + "1" * 64,
            "sha256:" + "2" * 64,
            1,
            host_loss_recoverable=True,
        )


@pytest.mark.invariant
def test_public_publisher_cannot_be_constructed_without_authorization():
    signature = inspect.signature(DevelopmentTestnetPublisher)
    assert list(signature.parameters) == ["issuer", "backend", "authorization"]
