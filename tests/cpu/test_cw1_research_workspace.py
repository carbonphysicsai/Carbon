"""Requester files and capability requests cannot acquire host authority."""

import pytest

from carbon.development_session.research_ledger import CampaignLedger
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
    "name", ["../secret", "/home/carbon", "a/b", "a\\b", "..", "", "a" * 97]
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
    assert ledger.status(owner="alice")["used"] == dict.fromkeys(
        ledger.status(owner="alice")["ceilings"], 0
    )
    with pytest.raises(ValueError):
        request_capability(
            ledger, owner="alice", request={**request, "disposition": "approved"}
        )
