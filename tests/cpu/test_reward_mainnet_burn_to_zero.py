"""mainnet-winner-v4 (owner BURN-TO-ZERO, OWNER_LINES L678, typed in the live-ops seat ~2026-11-24T01:4xZ: "Turn burn to
0"): v3's rule with the Challenge list cut to the Challenges with a LIVE pool on 116 (today Motor alone), so no share burns
for an unlaunched slot. The no-eligible-winner burn, the decay remainder and the qualification stay exactly v3's.
"""

from __future__ import annotations

import json

from carbon.rewards import winner_decay as wd
from carbon.rewards.core import DAY_MS, Q12

MOTOR = "electric-motor-magnetics"
NOW = 1_800_000_000_000


def test_v4_is_v3_with_only_the_live_challenge():
    v3, v4 = wd.load_policy("mainnet-winner-v3"), wd.load_policy("mainnet-winner-v4")
    assert v4.challenges == (MOTOR,) and v4.share == Q12
    assert v3.share * 4 == Q12  # v3: four Challenges x 1/4 (three unlaunched = 75 % burned)
    for field in (
        "network",
        "netuid",
        "authority",
        "burn_uid",
        "cadence_blocks",
        "self_improvement_factor",
    ):
        assert getattr(v4, field) == getattr(v3, field), field
    assert v4.qualified_packs(MOTOR) == v3.qualified_packs(MOTOR)
    raw = (wd.POLICY_DIR / "mainnet-winner-v4.json").read_text(encoding="utf-8")
    assert "Turn burn to 0" in json.loads(raw)["membership_note"]
    # never the registry's current policy: live-ops re-points the standing authorization under the owner line
    assert wd.load_policy().version == "testnet-winner-v1"


def test_a_fresh_motor_king_takes_the_whole_epoch_and_nothing_burns():
    v4 = wd.load_policy("mainnet-winner-v4")
    king = wd.Winner("5King", NOW - DAY_MS // 2)
    assert wd.epoch_targets(v4, {MOTOR: king}, NOW) == {
        "winners": {"5King": Q12},
        "burn": 0,
    }
    # under v3 the same king got a quarter and three quarters burned
    v3 = wd.load_policy("mainnet-winner-v3")
    assert wd.epoch_targets(v3, {MOTOR: king}, NOW)["burn"] == Q12 - Q12 // 4


def test_what_still_burns_is_unchanged_from_v3():
    v4 = wd.load_policy("mainnet-winner-v4")
    # no eligible winner: the whole epoch burns (the ineligible-incumbent guard upstream stays)
    assert wd.epoch_targets(v4, {}, NOW) == {"winners": {}, "burn": Q12}
    # the 24 h halving decay is the registered rule: a king on its second day is paid half
    second_day = wd.Winner("5King", NOW - DAY_MS - 1)
    assert wd.epoch_targets(v4, {MOTOR: second_day}, NOW) == {
        "winners": {"5King": Q12 // 2},
        "burn": Q12 // 2,
    }
