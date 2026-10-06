"""The owner's testnet winner-decay rule (VALIDATOR-14; OWNER-TESTNET-WEIGHTS-01).

Pure arithmetic in Q12 units of one epoch: 1/N per Challenge; the winner gets
all of it for 24 hours, then half each further day; everything unpaid burns.
"""

import json
import shutil

import pytest

from carbon.rewards import winner_decay as wd
from carbon.rewards.core import DAY_MS, Q12, RewardFailure

POLICY = wd.load_policy()
BATTERY, COOLING, MOTOR = POLICY.challenges
T0 = 10 * DAY_MS


def test_the_registered_policy_is_the_owners_rule():
    assert POLICY.version == "testnet-winner-v1"
    assert (POLICY.network, POLICY.netuid, POLICY.burn_uid) == ("testnet", 567, 0)
    assert len(POLICY.challenges) == 3
    assert POLICY.share == Q12 // 3
    assert POLICY.self_improvement_factor is None


@pytest.mark.parametrize(
    ("elapsed", "fraction"),
    [
        (0, Q12),
        (DAY_MS - 1, Q12),
        (DAY_MS, Q12 // 2),
        (2 * DAY_MS - 1, Q12 // 2),
        (2 * DAY_MS, Q12 // 4),
        (3 * DAY_MS + 5, Q12 // 8),
        (70 * DAY_MS, 0),
    ],
)
def test_all_for_24_hours_then_half_every_24_hours(elapsed, fraction):
    assert wd.winner_fraction(T0, T0 + elapsed) == fraction


def test_a_clock_in_the_future_is_refused():
    with pytest.raises(RewardFailure):
        wd.winner_fraction(T0, T0 - 1)


def test_no_winner_burns_everything():
    assert wd.epoch_targets(POLICY, {}, T0) == {"winners": {}, "burn": Q12}


def test_one_winner_gets_its_challenges_share_and_the_rest_burns():
    found = wd.epoch_targets(POLICY, {BATTERY: wd.Winner("hk-a", T0)}, T0 + 5)
    assert found == {"winners": {"hk-a": Q12 // 3}, "burn": Q12 - Q12 // 3}
    later = wd.epoch_targets(POLICY, {BATTERY: wd.Winner("hk-a", T0)}, T0 + DAY_MS)
    assert later["winners"] == {"hk-a": Q12 // 3 // 2}
    assert sum(later["winners"].values()) + later["burn"] == Q12


def test_being_beaten_restarts_the_clock_for_the_new_winner():
    old = wd.epoch_targets(POLICY, {COOLING: wd.Winner("hk-a", T0)}, T0 + 3 * DAY_MS)
    new = wd.epoch_targets(
        POLICY, {COOLING: wd.Winner("hk-b", T0 + 3 * DAY_MS)}, T0 + 3 * DAY_MS
    )
    assert old["winners"] == {"hk-a": (Q12 // 3) // 8}
    assert new["winners"] == {"hk-b": Q12 // 3}


def test_one_miner_winning_two_challenges_is_paid_for_both():
    found = wd.epoch_targets(
        POLICY,
        {BATTERY: wd.Winner("hk-a", T0), MOTOR: wd.Winner("hk-a", T0 - DAY_MS)},
        T0,
    )
    assert found["winners"] == {"hk-a": Q12 // 3 + (Q12 // 3) // 2}
    assert sum(found["winners"].values()) + found["burn"] == Q12


def test_every_epoch_sums_exactly_to_one_and_nothing_carries_over():
    winners = {
        BATTERY: wd.Winner("hk-a", T0),
        COOLING: wd.Winner("hk-b", T0 - 2 * DAY_MS),
        MOTOR: wd.Winner("hk-c", T0 - 9 * DAY_MS),
    }
    for hour in range(24 * 5):
        found = wd.epoch_targets(POLICY, winners, T0 + hour * 3_600_000)
        assert sum(found["winners"].values()) + found["burn"] == Q12
        assert found["burn"] >= Q12 - 3 * (Q12 // 3)


def test_a_challenge_outside_the_policy_is_refused():
    with pytest.raises(RewardFailure) as refused:
        wd.epoch_targets(POLICY, {"photonic-coupler": wd.Winner("hk", T0)}, T0)
    assert str(refused.value) == "CHALLENGE_NOT_IN_POLICY"


def test_an_altered_policy_is_refused(tmp_path):
    copy = tmp_path / "weight_policies"
    shutil.copytree(wd.POLICY_DIR, copy)
    path = copy / "testnet-winner-v1.json"
    document = json.loads(path.read_text())
    document["challenges"] = document["challenges"][:1]
    path.write_text(json.dumps(document))
    with pytest.raises(RewardFailure) as refused:
        wd.load_policy(directory=copy)
    assert str(refused.value) == "WEIGHT_POLICY_ALTERED"


def test_a_mainnet_policy_is_malformed_even_when_pinned(tmp_path):
    import hashlib

    copy = tmp_path / "weight_policies"
    shutil.copytree(wd.POLICY_DIR, copy)
    path = copy / "testnet-winner-v1.json"
    document = json.loads(path.read_text())
    document["network"], document["netuid"] = "finney", 1
    path.write_text(json.dumps(document))
    registry = json.loads((copy / "registry.json").read_text())
    registry["versions"]["testnet-winner-v1"] = (
        "sha256:" + hashlib.sha256(wd._canonical(document)).hexdigest()
    )
    (copy / "registry.json").write_text(json.dumps(registry))
    with pytest.raises(RewardFailure) as refused:
        wd.load_policy(directory=copy)
    assert str(refused.value) == "WEIGHT_POLICY_MALFORMED"
