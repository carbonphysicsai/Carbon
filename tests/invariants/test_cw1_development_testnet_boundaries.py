"""Permanent authority boundaries for C-W1-D1's non-official testnet profile."""

from pathlib import Path

import pytest

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
    source = (ROOT / "carbon/development_testnet/model.py").read_text()
    assert "host_loss_recoverable: bool = False" in source
    assert "archive_acknowledgement: None = None" in source
    assert "self.host_loss_recoverable is not False" in source
    assert "self.archive_acknowledgement is not None" in source


@pytest.mark.invariant
def test_public_publisher_cannot_be_constructed_without_authorization():
    source = (ROOT / "carbon/development_testnet/publication.py").read_text()
    assert "def __init__(self, issuer, backend, authorization):" in source
    assert "type(authorization) is not DevelopmentTransactionAuthorization" in source
    assert "TRANSACTION_AUTHORIZATION_REQUIRED" in source
