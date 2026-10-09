"""Registered canary hotkeys (CANARY-01): scored, never anything else.

A canary's submission is admitted and scored as any other (the liveness
check). It is never nominated (never an incumbent or a finalist), never a
leak-detection baseline, never weighted, and never in the score feed. A
hotkey that is not listed is unaffected.

The registry is empty until OWNER-CANARY-LIST-01 names a hotkey; these tests
list one for their own duration only. Synthetic roots, in-process backends:
no container, chain, network or spend.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))

from test_battery_validator_daemon import backend, refs  # noqa: F401 - fixtures
from test_graphite_hidden_score import TEMPO, deployment, knn
from test_reward_testnet_winner_publication import composed, promotion

from carbon.agent_campaign.graphite import hidden_score
from carbon.challenge_validator import canary
from carbon.challenge_validator.battery import BatteryAdapter
from carbon.rewards.core import Q12


def scored(tmp_path, refs, backend, run_id):  # noqa: F811
    target = deployment(tmp_path, refs, backend)
    pool = hidden_score.HiddenPool(target, run_id=run_id, clock=lambda: TEMPO + 5)
    return target, pool


def test_the_registry_names_exactly_the_owners_record():
    assert canary.CANARY_LIST_RECORD == "OWNER-CANARY-LIST-01"
    assert canary.CANARY_LIST_VERSION == 1
    assert canary.canary_hotkeys() == frozenset(
        {"5GBmHPBLwyKheugbtAVgxtWdX9YmWjfeCaBwmeFHr4rEWiB5"}
    )
    record = (
        REPOSITORY / ".agent/decisions/2026-10-08-OWNER-CANARY-LIST-01.md"
    ).read_text()
    assert all(hotkey in record for hotkey in canary.CANARY_HOTKEYS)


def test_a_canary_is_scored_and_never_nominated(
    tmp_path, refs, backend, monkeypatch  # noqa: F811
):
    target, pool = scored(tmp_path, refs, backend, "canary-run")
    hotkey = pool.identity("proposal")
    monkeypatch.setattr(canary, "CANARY_HOTKEYS", (hotkey,))
    view, operator = pool.submit("proposal", knn())
    assert view["state"] == "SCORED", view
    assert operator["nomination"]["nominated"] is False
    assert operator["nomination"]["excluded"] == "CANARY"
    assert target.store.incumbent() is None
    # Never a leak-detection baseline.
    profiles = BatteryAdapter(target).leak_profiles()
    assert all(p["hotkey"] != hotkey for p in profiles)


def test_a_hotkey_that_is_not_listed_is_unaffected(
    tmp_path, refs, backend, monkeypatch  # noqa: F811
):
    _target, pool = scored(tmp_path, refs, backend, "plain-run")
    monkeypatch.setattr(canary, "CANARY_HOTKEYS", ("5SomeoneElse",))
    view, operator = pool.submit("proposal", knn())
    assert view["state"] == "SCORED", view
    assert operator["nomination"].get("excluded") is None


def test_a_canary_is_never_weighted(tmp_path, monkeypatch):
    """A canary that is somehow a ledger winner is never paid: its share
    burns, and its hotkey is in no weights publication."""
    monkeypatch.setattr(canary, "CANARY_HOTKEYS", ("miner-hotkey",))
    issuer, backend_, publisher = composed(tmp_path, source=promotion)
    state, _ = asyncio.run(backend_.observe())
    ref = issuer.issue(state)
    intent = issuer.resolve(ref, state)["intent"]
    assert intent["targets"]["winners"] == []
    assert intent["targets"]["burn"] == Q12
    asyncio.run(publisher.publish(ref))
    assert backend_.executions == 1
    assert "miner-hotkey" not in str(backend_.row)
