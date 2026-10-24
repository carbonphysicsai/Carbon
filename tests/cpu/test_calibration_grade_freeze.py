"""The calibration driver freezes its own campaign before any dispatch, and fake mode
goes through the ledger exactly as the real carrier does (only the container launch is
stubbed): an unfrozen calibration ledger refuses in fake mode too (the custody2 preflight
failed with "freeze before dispatch" where fake mode had passed)."""

from __future__ import annotations

import json

import pytest

from carbon.challenge_validator import calibration_grade_run as run
from carbon.development_session.research_ledger import CampaignLedger


def _files():
    return {
        "control.json": json.dumps(
            {
                "recipe_digest": "sha256:" + "1" * 64,
                "state_digest": "sha256:" + "2" * 64,
                "inputs_digest": "sha256:" + "3" * 64,
            }
        ).encode(),
        "inputs.npz": b"inputs",
    }


def _call(ledger):
    runner = run.stub_runner(lambda _inputs, _control: [[1.0]])
    return runner(
        ledger,
        owner=run.CALIBRATION_OWNER,
        identity="calibration-test",
        files=_files(),
    )


def test_an_unfrozen_calibration_ledger_refuses_in_fake_mode(tmp_path):
    ledger = CampaignLedger(tmp_path / "ledger")
    with pytest.raises(ValueError, match="freeze before dispatch"):
        _call(ledger)


def test_a_frozen_calibration_campaign_dispatches_once_through_the_ledger(tmp_path):
    ledger = CampaignLedger(tmp_path / "ledger")
    run.freeze_campaign(ledger)
    run.freeze_campaign(ledger)  # idempotent for the same manifest
    record = _call(ledger)
    assert set(record["files"]) == {"predictions.json", "receipt.json"}
    with ledger.db() as db:
        states = db.execute("SELECT owner,state FROM operations").fetchall()
    assert states == [(run.CALIBRATION_OWNER, "SUCCEEDED")]


def test_the_frozen_campaign_is_the_calibration_owners_and_uncapped(tmp_path):
    ledger = CampaignLedger(tmp_path / "ledger")
    run.freeze_campaign(ledger)
    with ledger.db() as db:
        manifest = json.loads(db.execute("SELECT manifest FROM campaign").fetchone()[0])
    assert manifest["owner"] == "calibration"
    assert "ceilings" not in manifest and "elapsed_seconds" not in manifest
