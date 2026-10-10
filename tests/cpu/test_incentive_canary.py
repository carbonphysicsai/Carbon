"""INCENTIVE-CANARY-01 slice 1: the passive "best model is paid" check.

Synthetic weight rows only: no chain, network or signer. Each verdict of
`verify_epoch` is pinned, and `check` is driven through fake readers.
"""

from __future__ import annotations

from types import SimpleNamespace

from carbon.challenge_validator.canary import CANARY_HOTKEYS
from scripts.dev.canary import incentive as inc

BATTERY = inc.BATTERY
INCUMBENT, OTHER = "5Incumbent", "5Other"
CANARY = CANARY_HOTKEYS[0]
HOTKEYS = {0: "5Burn", 7: INCUMBENT, 8: OTHER, 13: CANARY}


def row(incumbent_fraction, extra=()):
    """A u16 row: the incumbent's fraction of the whole, the rest burned."""
    paid = round(inc.U16 * incumbent_fraction)
    return [[0, inc.U16 - paid - sum(v for _, v in extra)], [7, paid], *extra]


def verify(weights, incumbent=INCUMBENT):
    return inc.verify_epoch(
        weights, HOTKEYS, {BATTERY: incumbent}, 3, frozenset(CANARY_HOTKEYS)
    )


def codes(result):
    return [f["code"] for f in result["findings"]]


def test_the_incumbent_paid_its_share_or_a_halving_passes():
    for halvings in (0, 1, 2, 5):
        found = verify(row((1 / 3) * 2.0**-halvings))
        assert found["state"] == inc.PASS, found
        assert found["findings"][0]["halvings"] == halvings


def test_weight_to_anyone_but_the_incumbent_is_a_blocker():
    found = verify(row(1 / 3, extra=[[8, 1000]]))
    assert found["state"] == inc.BLOCKER
    assert "weight_to_non_incumbent" in codes(found)


def test_a_weighted_canary_is_a_blocker():
    found = verify(row(1 / 3, extra=[[13, 500]]))
    assert found["state"] == inc.BLOCKER
    assert "canary_weighted" in codes(found)


def test_a_share_that_is_no_decay_level_is_a_blocker():
    found = verify(row(0.6 / 3))
    assert found["state"] == inc.BLOCKER
    assert codes(found) == ["share_not_a_decay_level"]


def test_an_unpaid_incumbent_is_attention_not_a_blocker():
    found = verify([[0, inc.U16]])
    assert found["state"] == inc.ATTENTION
    assert codes(found) == ["incumbent_unpaid"]


def test_what_cannot_be_read_is_unverified_never_a_pass():
    assert verify([[0, 0]])["state"] == inc.UNVERIFIED
    found = verify([[0, inc.U16]], incumbent=None)
    assert found["state"] == inc.UNVERIFIED
    assert codes(found) == ["incumbent_not_released"]
    # Paying nobody while the incumbent is unregistered is correct: it burns.
    assert verify([[0, inc.U16]], incumbent="5Unregistered")["state"] == inc.PASS


def test_check_reads_the_public_surfaces_and_refuses_mainnet():
    config = {
        "schema": inc.SCHEMA,
        "validator_hotkey": "5Validator",
        "intake_url": "http://127.0.0.1:1",
        "feed_key": "00" * 32,
        "policy": "testnet-winner-v1",
    }

    async def weights(context, hotkey):
        assert hotkey == "5Validator"
        return row(1 / 3), HOTKEYS

    testnet = SimpleNamespace(network="testnet")
    found = inc.check(
        config,
        weights_reader=weights,
        incumbent_reader=lambda url, key: INCUMBENT,
        context=testnet,
    )
    assert found["state"] == inc.PASS
    finney = SimpleNamespace(network="finney")
    assert inc.check(config, context=finney)["findings"] == [{"code": "testnet_only"}]

    def unreadable(url, key):
        raise inc.Unverified("feed_unavailable")

    found = inc.check(
        config, weights_reader=weights, incumbent_reader=unreadable, context=testnet
    )
    assert found == {
        "state": inc.UNVERIFIED,
        "findings": [{"code": "feed_unavailable"}],
    }
