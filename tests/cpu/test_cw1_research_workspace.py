"""Requester files and capability requests cannot acquire host authority."""

import pytest

from carbon.development_session.research_ledger import DIMENSIONS, CampaignLedger
from carbon.development_session.research_workspace import (
    CAPABILITY_FIELDS,
    ResearchWorkspace,
    request_capability,
)


def test_requester_isolation_restart_and_compare_swap(tmp_path):
    ledger = CampaignLedger(tmp_path)
    alice = ResearchWorkspace(ledger, "alice")
    pin = alice.put("hypothesis.py", b"print(1)")
    assert (
        ResearchWorkspace(CampaignLedger(tmp_path), "alice").get("hypothesis.py")
        == b"print(1)"
    )
    bob = ResearchWorkspace(ledger, "bob")
    assert bob.inventory() == []
    with pytest.raises(ValueError):
        bob.get("hypothesis.py")
    with pytest.raises(ValueError):
        alice.put("hypothesis.py", b"print(2)")
    alice.put("hypothesis.py", b"print(2)", expected_digest=pin)
    assert alice.snapshot(["hypothesis.py"]) == {"hypothesis.py": b"print(2)"}


@pytest.mark.parametrize(
    "name", ["../secret", "/etc/passwd", "a/b", "a\\b", "..", "", "a" * 97]
)
def test_no_host_path_surface(tmp_path, name):
    with pytest.raises(ValueError):
        ResearchWorkspace(CampaignLedger(tmp_path), "alice").put(name, b"x")


def test_request_cannot_choose_its_disposition_or_grant(tmp_path):
    ledger = CampaignLedger(tmp_path)
    request = dict.fromkeys(CAPABILITY_FIELDS, "public hypothesis")
    request["reason"] = "missing_adapter"
    result = request_capability(ledger, owner="alice", request=request)
    assert result["authority_granted"] is False
    # Every dimension at zero. Enumerated from DIMENSIONS rather than from the
    # budget, because the claim is that nothing was consumed - which holds
    # whether or not the miner set a budget at all.
    assert ledger.status(owner="alice")["used"] == dict.fromkeys(DIMENSIONS, 0)
    with pytest.raises(ValueError):
        request_capability(
            ledger, owner="alice", request={**request, "disposition": "approved"}
        )


def _uncapped_workspace(tmp_path):
    from carbon.development_session.research_ledger import CampaignLedger
    from carbon.development_session.research_workspace import ResearchWorkspace

    tmp_path.chmod(0o700)
    return ResearchWorkspace(CampaignLedger(tmp_path / "campaign"), "miner")


def test_a_checkpoint_of_any_size_persists_on_disk_not_in_the_ledger(tmp_path):
    """No Carbon cap: 40 MiB is five times the old 8 MiB per-file limit."""
    workspace = _uncapped_workspace(tmp_path)
    body = bytes(range(256)) * (40 * 4096)
    fingerprint = workspace.put("checkpoint.bin", body)
    assert workspace.get("checkpoint.bin") == body
    assert workspace.inventory() == [
        {"name": "checkpoint.bin", "bytes": len(body), "digest": fingerprint}
    ]
    stored = workspace.objects / fingerprint.removeprefix("sha256:")
    assert stored.stat().st_size == len(body) and stored.stat().st_mode & 0o777 == 0o600
    with workspace.ledger.db() as db:
        assert db.execute("SELECT LENGTH(body) FROM workspace").fetchone()[0] == 0


def test_a_blob_written_by_the_earlier_layout_still_reads(tmp_path):
    from carbon.development_session.profile import digest

    workspace = _uncapped_workspace(tmp_path)
    with workspace.ledger.db() as db:
        db.execute(
            "INSERT INTO workspace VALUES(?,?,?,?)",
            ("miner", "legacy.json", b"{}", digest(b"{}")),
        )
    assert workspace.get("legacy.json") == b"{}"
    assert workspace.inventory()[0]["bytes"] == 2


def test_a_tampered_object_is_refused_not_returned(tmp_path):
    workspace = _uncapped_workspace(tmp_path)
    fingerprint = workspace.put("weights.bin", b"real weights")
    (workspace.objects / fingerprint.removeprefix("sha256:")).write_bytes(b"swapped")
    with pytest.raises(ValueError, match="unavailable"):
        workspace.get("weights.bin")
