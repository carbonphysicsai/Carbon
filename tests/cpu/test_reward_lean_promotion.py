"""Workstream I5: a sealed-exam crown is a weight source on testnet only.

The reason `bank_comparison_sealed_testnet` is carried only by a win on a
sealed evaluation pack. The reward layer pays it under a testnet policy and
refuses it under any other; the development reason stays unpayable. In
process, with a duck-typed pool store; no chain, spend or real exam material.
"""

from __future__ import annotations

import pytest

from carbon.challenge_validator import bank_promotion as bp
from carbon.rewards import winner_decay as wd
from carbon.rewards import winner_eligibility as we
from carbon.rewards.core import DAY_MS, RewardFailure

POLICY = wd.load_policy()
CHALLENGE = POLICY.challenges[0]
T0 = 20 * DAY_MS


class _Store:
    def __init__(self, incumbent, events=(), submissions=None):
        self._incumbent = incumbent
        self._events = list(events)
        self._submissions = submissions or {}
        self.set_calls = []

    def incumbent(self):
        return self._incumbent

    def events(self, kind=None):
        return [{"body": body} for body in self._events]

    def submission(self, model_id):
        return self._submissions[model_id]

    def set_incumbent(self, model_id, reason, *, expected=None):
        self.set_calls.append((model_id, reason, expected))


def _store(reason, previous=None):
    submissions = {"m2": {"hotkey": "hk-b", "binding": {"recipe_digest": "r"}}}
    if previous is not None:
        submissions[previous] = {"hotkey": "hk-a", "binding": {}}
    return _Store(
        {"model_id": "m2", "reason": reason},
        [{"model_id": "m2", "reason": reason, "previous": previous}],
        submissions,
    )


def test_the_development_reason_is_never_payable():
    with pytest.raises(RewardFailure, match="PROMOTION_DEVELOPMENT_ONLY"):
        we.lean_promotion(_store(bp.DEVELOPMENT_PROMOTION))
    with pytest.raises(RewardFailure, match="PROMOTION_REASON_UNKNOWN"):
        we.lean_promotion(_store("something_else"))
    assert we.lean_promotion(_Store(None)) is None


def test_a_sealed_crown_is_read_as_first_or_bank():
    first = we.lean_promotion(_store(bp.SEALED_TESTNET_PROMOTION))
    assert first["kind"] == we.FIRST and first["hotkey"] == "hk-b"
    beaten = we.lean_promotion(_store(bp.SEALED_TESTNET_PROMOTION, previous="m1"))
    assert beaten["kind"] == we.BANK
    assert (beaten["previous"], beaten["previous_hotkey"]) == ("m1", "hk-a")
    assert beaten["incumbent_reason"] == "bank_comparison_sealed_testnet"


class _Policy:
    """The testnet policy, or the same policy on another network."""

    def __init__(self, network):
        self.network = network
        self.digest = POLICY.digest

    def baseline(self, challenge):
        return POLICY.baseline(challenge)


def test_a_sealed_crown_pays_on_testnet_and_a_mainnet_policy_refuses_it(tmp_path):
    assert POLICY.network == "testnet"
    promotion = we.lean_promotion(_store(bp.SEALED_TESTNET_PROMOTION, previous="m1"))
    book = we.WinnerLedger(tmp_path / "testnet.jsonl")
    book.observe(
        POLICY,
        CHALLENGE,
        {"model_id": "m1", "hotkey": "hk-a", "previous": None, "kind": we.FIRST},
        {"hk-a": "ck-a"},
        T0,
    )
    paid = book.observe(POLICY, CHALLENGE, promotion, {"hk-b": "ck-b"}, T0 + DAY_MS)
    assert (paid["eligible"], paid["reason"]) == (True, "bank_improvement")
    refused = we.WinnerLedger(tmp_path / "mainnet.jsonl").observe(
        _Policy("mainnet"), CHALLENGE, promotion, {"hk-b": "ck-b"}, T0
    )
    assert (refused["eligible"], refused["reason"]) == (
        False,
        "sealed_crown_testnet_only",
    )
    assert we.payable(refused, {"hk-b"}) is None


@pytest.mark.parametrize(
    ("sealed", "reason"),
    [(False, bp.DEVELOPMENT_PROMOTION), (True, bp.SEALED_TESTNET_PROMOTION)],
)
def test_the_crown_carries_the_reason_of_the_pack_it_was_won_on(
    monkeypatch, sealed, reason
):
    store = _Store(None)
    promotion = bp.BankPromotion.__new__(bp.BankPromotion)
    promotion.store = store
    promotion.private_pair = lambda *args: {"expected_incumbent": None}
    monkeypatch.setattr(
        bp,
        "compare_private_pair",
        lambda pair, comparator: {"outcome": bp.FIRST_INCUMBENT},
    )
    promotion.consider_private("m1", "key", object(), sealed=sealed)
    assert store.set_calls == [("m1", reason, None)]
