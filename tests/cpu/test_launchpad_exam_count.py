"""The final exams a campaign shows are the ones it can actually use.

Found in the live battery journey (Launchpad H, 2026-09-29): a campaign the
miner capped at one epoch showed "Final exams remaining: 2". The campaign runs
FINAL_EPOCHS[:cap]; the count shown now uses the same rule.
"""

import pytest
from test_miner_operation_idempotency import settle

from scripts.dev.miner_launchpad.journey_fixture import (
    journey_host,
    register_fixture_challenge,
)
from scripts.dev.miner_launchpad.operations import perform


@pytest.mark.parametrize(("budget", "remaining"), [(None, 2), (1, 1)])
def test_final_exams_remaining_follow_the_epoch_cap(
    tmp_path, monkeypatch, budget, remaining
):
    named = register_fixture_challenge(monkeypatch.setattr)
    tmp_path.chmod(0o700)
    host = journey_host(tmp_path, patch=monkeypatch.setattr)
    request = {**named, "agent": "none", "idempotency_key": "launch-key-0000001"}
    if budget is not None:
        request["budget"] = {"ceilings": {"epochs": budget}}
    launched = perform(host, "launch", request)
    view = settle(host, launched["id"])
    assert view["state"] == "READY"
    assert view["journey"]["final_exams_remaining"] == remaining
