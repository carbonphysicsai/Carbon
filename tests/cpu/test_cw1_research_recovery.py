import json
from types import SimpleNamespace

import pytest

from carbon.development_session import research_carrier as carrier
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_ledger import (
    CEILINGS,
    ELAPSED_SECONDS,
    VERSION,
    CampaignLedger,
)


def setup(tmp_path):
    ledger = CampaignLedger(tmp_path)
    ledger.freeze(
        {
            "schema": VERSION,
            "ceilings": CEILINGS,
            "elapsed_seconds": ELAPSED_SECONDS,
            "campaign_id": "fixture",
            "implementation": "fixture",
            "objective": "fixture",
            "sampling": "fixture",
            "control": "fixture",
            "selection": "fixture",
            "replica_policy": "fixture",
            "provider": "none",
            "owner": "one",
        }
    )
    request = {"source": "retained-test-source"}
    ledger.reserve(
        "worker",
        owner="one",
        phase="research",
        request=request,
        resources={"numerical_milliseconds": 60000, "research_trials": 1},
    )
    launch = digest(
        canonical({"owner": "one", "identity": "worker", "request": request})
    )
    directory = tmp_path / ("operation-" + launch[7:])
    directory.mkdir()
    (directory / "intent.json").write_bytes(
        canonical(
            {
                "owner": "one",
                "identity": "worker",
                "request": request,
                "launch": launch,
                "container": "carbon-d4-" + launch[7:31],
            }
        )
    )
    return ledger, directory


def test_recovery_preserves_failed_budget_without_retry(tmp_path, monkeypatch):
    ledger, _directory = setup(tmp_path)
    calls = []
    monkeypatch.setattr(
        carrier, "remove_exact_container", lambda **kwargs: calls.append(kwargs)
    )
    monkeypatch.setattr(
        carrier,
        "DockerCLI",
        lambda: SimpleNamespace(run=lambda *a, **k: SimpleNamespace(stdout="")),
    )
    result = carrier.reconcile_worker(ledger, owner="one", identity="worker")
    assert result["cleanup_observed"] and not result["retry_dispatched"]
    assert ledger.status(owner="one")["used"]["numerical_milliseconds"] == 60000
    assert ledger.status(owner="one")["used"]["research_trials"] == 1
    assert carrier.reconcile_worker(ledger, owner="one", identity="worker") == result
    assert len(calls) == 1


def test_recovery_refuses_active_wrong_owner_and_altered_intent(tmp_path):
    ledger, directory = setup(tmp_path)
    with carrier._numerical_lease(ledger), pytest.raises(ValueError, match="active"):
        carrier.reconcile_worker(ledger, owner="one", identity="worker")
    with pytest.raises(ValueError, match="owned"):
        carrier.reconcile_worker(ledger, owner="two", identity="worker")
    path = directory / "intent.json"
    value = json.loads(path.read_bytes())
    value["container"] = "unrelated"
    path.write_bytes(canonical(value))
    with pytest.raises(ValueError, match="identity conflict"):
        carrier.reconcile_worker(ledger, owner="one", identity="worker")
    assert ledger.status(owner="one")["operations"][0]["state"] == "RESERVED"
