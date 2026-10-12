"""VALIDATOR-33 A: the feed's king, handovers, target to beat and chain time.

The fields the dashboard needs (DASHBOARD_FIELD_MAP.md), added to the signed
feed without changing its schema: the dashboard drops unknown keys and
verifies v1's signing domain, so they are additive. The king comes from the
weights publisher's own winner ledger, its share from the payment code's own
decay clock, and the chain-time fields from a finalized read. They are added
after versioning, so a version still changes only when the standings do.
Canary hotkeys are never named.
"""

from __future__ import annotations

import pytest
from test_challenge_validator_battery_bank import adapter, run  # noqa: F401
from test_challenge_validator_score_feed import validator  # noqa: F401

from carbon.challenge_validator import canary
from carbon.challenge_validator import score_feed as sf
from carbon.rewards.winner_decay import DAY_MS

CROWNED = 1_800_000_000_000


def _record(hotkey, previous, model, *, kind="FINAL", eligible=True, clock=CROWNED):
    return {
        "challenge": "toy",
        "promotion": {
            "hotkey": hotkey,
            "previous_hotkey": previous,
            "kind": kind,
            "model_id": model,
        },
        "eligible": eligible,
        "reason": "final_improvement" if eligible else "nomination_on_overdue_pool",
        "clock_ms": clock,
    }


def _chain(store, now, *, block=None):
    blocks = [
        w["activate_block"]
        for w in (store.window(f) for f in store.batch_fingerprints())
        if w is not None
    ]
    return {
        "block": min(blocks) - 1 if block is None else block,
        "hash": "0x" + "ab" * 32,
        "timestamp_ms": now,
        "participants": {"5King": {"uid": 7, "coldkey": "5Cold"}},
    }


def test_without_a_ledger_or_chain_the_new_fields_are_null(
    validator, tmp_path  # noqa: F811
):
    key = sf.FeedKey.create(tmp_path / "feed.key")
    feed = sf.build(validator["target"], key=key, hotkey="5Val", network="testnet")
    assert feed["king"] is None and feed["handovers"] == []
    assert feed["as_of_block"] is None
    assert feed["target_to_beat"]["kind"].endswith("margin_then_final")
    assert sf.verify_feed(feed)


def test_the_king_its_share_and_handovers_come_from_the_ledger_and_the_chain(
    validator, tmp_path, monkeypatch  # noqa: F811
):
    store = validator["store"]
    monkeypatch.setattr(canary, "CANARY_HOTKEYS", ())
    monkeypatch.setattr(
        store,
        "finals_rows",
        lambda: [
            {
                "final_id": "f1",
                "challenger": "c1",
                "incumbent": "m2",
                "state": "DECIDED",
            },
            {
                "final_id": "f2",
                "challenger": "c2",
                "incumbent": "m2",
                "state": "DECIDED",
            },
            {"final_id": "f3", "challenger": "c3", "incumbent": "m2", "state": "OPEN"},
        ],
    )
    outcomes = {
        "f1": {"outcome": "NO_IMPROVEMENT", "promotable": False},
        "f2": {"outcome": "WITHDRAWN", "promotable": False},
    }
    monkeypatch.setattr(store, "final", lambda f: {"outcome": outcomes.get(f)})
    winners = [
        _record("5First", None, "m1", kind="FIRST", clock=CROWNED - 5 * DAY_MS),
        _record("5King", "5First", "m2"),
    ]
    key = sf.FeedKey.create(tmp_path / "feed.key")
    chain = _chain(store, CROWNED + DAY_MS // 2)

    def build(chain):
        return sf.build(
            validator["target"],
            key=key,
            hotkey="5Val",
            network="testnet",
            chain=chain,
            winners=winners,
        )

    feed = build(chain)
    king = feed["king"]
    assert king["hotkey"] == "5King" and king["submission_id"] == "m2"
    assert king["uid"] == 7 and king["coldkey"] == "5Cold"
    assert king["crowned_utc_ms"] == CROWNED
    # Full share for the first 24 h; the first halving at crowned + 24 h.
    assert king["share_now"] == 1.0
    assert king["next_halving_utc_ms"] == CROWNED + DAY_MS
    # A decided non-promoting final counts; a withdrawn or open one doesn't.
    assert king["challenges_survived"] == 1
    assert [h["to_hotkey"] for h in feed["handovers"]] == ["5First", "5King"]
    assert feed["handovers"][1]["from_hotkey"] == "5First"
    assert feed["as_of_block"]["number"] == chain["block"]
    assert feed["release"]["next_rotation_block"] == chain["block"] + 1
    assert sf.verify_feed(feed)
    # A day and a half in: halved once, the next halving at crowned + 48 h. The
    # chain time changes the live fields but never the version.
    later = build(_chain(store, CROWNED + 3 * DAY_MS // 2, block=10**9))
    assert later["king"]["share_now"] == 0.5
    assert later["king"]["next_halving_utc_ms"] == CROWNED + 2 * DAY_MS
    assert later["release"]["next_rotation_block"] is None
    assert later["version"] == feed["version"]
    assert sf.verify_feed(later)


def test_an_ineligible_record_pays_nothing_and_a_canary_is_never_named(
    validator, tmp_path, monkeypatch  # noqa: F811
):
    store = validator["store"]
    key = sf.FeedKey.create(tmp_path / "feed.key")
    monkeypatch.setattr(canary, "CANARY_HOTKEYS", ("5Canary",))
    ineligible = [_record("5King", None, "m2", eligible=False)]
    feed = sf.build(
        validator["target"],
        key=key,
        hotkey="5Val",
        network="testnet",
        chain=_chain(store, CROWNED + 1),
        winners=ineligible,
    )
    assert feed["king"]["share_now"] == 0.0
    assert feed["king"]["next_halving_utc_ms"] is None
    canary_king = [_record("5Canary", "5King", "m3")]
    feed = sf.build(
        validator["target"],
        key=key,
        hotkey="5Val",
        network="testnet",
        chain=_chain(store, CROWNED + 1),
        winners=ineligible + canary_king,
    )
    assert feed["king"] is None
    assert feed["handovers"][1]["to_hotkey"] is None
    assert "5Canary" not in str(feed)


@pytest.mark.parametrize("registered", [False, True])
def test_the_target_to_beat_is_rule_tagged_from_the_rule(registered):
    rule = {"equivalence_margin_rel": 0.057, "comparison": {"n_min": 30}}
    if registered:
        rule["score"] = {
            "registry": "r",
            "registry_sha256": "0" * 64,
            "candidate": "G-FEAS/A-Q>@0.05",
            "decision": "OWNER-BATTERY-SCORE-CANDIDATE-01",
        }
    found = sf.target_to_beat(rule)
    assert found["screening_margin_rel"] == found["final_margin_rel"] == 0.057
    assert found["final_comparison"] == {"n_min": 30}
    if registered:
        assert found["kind"] == "registered_score_margin_then_final"
        assert found["score"]["candidate"] == "G-FEAS/A-Q>@0.05"
        assert "registered_score_gate" in found["gates"]
    else:
        assert found["kind"] == "accuracy_margin_then_final"
        assert found["score"] is None
