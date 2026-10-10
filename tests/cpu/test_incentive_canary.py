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


# --- slice 2: the incentive roles --------------------------------------------------


def test_the_roles_are_registered_paid_and_off_the_canary_grid():
    from scripts.dev.canary import roles, variants

    assert {e["role"] for e in roles.ROLES.values()} == {
        "strong",
        "degraded",
        "challenger",
    }
    assert not set(roles.ROLES) & set(CANARY_HOTKEYS)
    canary_fractions = set(variants.TRAIN_FRACTIONS)
    bounds = {"neighbours": (1, 64), "train_fraction": (0.1, 1.0)}
    for entry in roles.ROLES.values():
        for neighbours, fraction in entry["recipes"]:
            assert fraction not in canary_fractions  # never a canary digest
            assert bounds["neighbours"][0] <= neighbours <= bounds["neighbours"][1]
            assert (
                bounds["train_fraction"][0] <= fraction <= bounds["train_fraction"][1]
            )


def test_a_role_hotkey_passes_the_runner_config_and_others_still_do_not():
    import pytest

    from scripts.dev.canary import config, roles

    strong = roles.hotkey_of("strong")
    assert roles.role_of(strong) == "strong"
    assert roles.role_of("5NotARole") is None
    # parse refuses a hotkey that is neither a canary nor a role first.
    with pytest.raises(config.ConfigRefused):
        config.parse({"schema": config.SCHEMA})


def test_role_order_is_attention_never_a_payment_blocker():
    from scripts.dev.canary import roles

    strong, degraded = roles.hotkey_of("strong"), roles.hotkey_of("degraded")
    held = {
        "incumbent": {"hotkey": strong},
        "standing": [{"hotkey": strong, "rank": 1}, {"hotkey": degraded, "rank": 2}],
    }
    assert [f["code"] for f in inc.verify_roles(held, roles.ROLES)] == [
        "role_order_held"
    ]
    inverted = {
        "incumbent": {"hotkey": degraded},
        "standing": [{"hotkey": strong, "rank": 1}, {"hotkey": degraded, "rank": 2}],
    }
    found = inc.verify_roles(inverted, roles.ROLES)
    assert found == [{"level": inc.ATTENTION, "code": "role_order_inverted"}]
    assert inc.verify_roles({}, roles.ROLES)[0]["code"] == "roles_not_both_released"


def test_a_role_list_is_a_valid_runner_variant_list(tmp_path):
    import pytest

    from scripts.dev.canary import roles, variants

    for role in ("strong", "degraded"):
        path = tmp_path / f"{role}.json"
        assert roles.main(["generate", "--role", role, "--out", str(path)]) == 0
        loaded, _ = variants.load(path)
        recipes = roles.ROLES[roles.hotkey_of(role)]["recipes"]
        assert [v["strategy"] for v in loaded["variants"]] == [
            variants.strategy(n, f) for n, f in recipes
        ]
    with pytest.raises(variants.VariantRefused):
        roles.generate("challenger")  # slice 3 calibrates its recipes


# --- slice 3a: the sybil scenario --------------------------------------------------


def test_the_sybil_scenarios_copy_strong_exactly_or_near_off_the_canary_grid():
    from scripts.dev.canary import roles, variants

    strong = roles.ROLES[roles.hotkey_of("strong")]["recipes"]
    copy, near = roles.SCENARIOS["sybil-copy"], roles.SCENARIOS["sybil-near"]
    assert copy["recipes"][0] in strong  # D6 must refuse it as contested
    for scenario in (copy, near):
        assert roles.role_of(scenario["hotkey"]) == "challenger"
        assert roles.role_of(scenario["of"]) == "strong"
    for neighbours, fraction in near["recipes"]:
        assert (neighbours, fraction) not in strong
        assert fraction not in set(variants.TRAIN_FRACTIONS)
        assert 1 <= neighbours <= 64 and 0.1 <= fraction <= 1.0


def test_a_sybil_list_is_a_valid_runner_variant_list(tmp_path):
    from scripts.dev.canary import roles, variants

    for name in roles.SCENARIOS:
        path = tmp_path / f"{name}.json"
        assert roles.main(["generate", "--scenario", name, "--out", str(path)]) == 0
        document, _ = variants.load(path)
        assert document["grid"]["scenario"] == name


def test_a_sybil_split_is_a_blocker_and_one_holder_is_not():
    honest, sybil = "5Honest", "5Sybil"
    hotkeys = {0: "5Burn", 14: honest, 16: sybil}
    found, shares = inc.verify_sybil(
        [[0, 1000], [14, 500], [16, 500]], hotkeys, honest, sybil
    )
    assert found == [{"level": inc.BLOCKER, "code": "sybil_split"}]
    found, shares = inc.verify_sybil([[0, 1500], [14, 500]], hotkeys, honest, sybil)
    assert found[0]["code"] == "sybil_not_split" and shares["sybil"] == 0


def test_summarize_fills_the_974_sybil_row_observed_half():
    share = 1 / 8
    lines = [
        {"shares": {"honest": share, "sybil": 0.0}},
        {"shares": {"honest": share, "sybil": 0.0}},
        {"shares": {"honest": 0.0, "sybil": share}},
        {"state": "UNVERIFIED", "findings": []},
    ]
    row = inc.summarize(lines, share)
    assert row["strategy"] == "sybil" and row["sybil_hotkeys"] == 2
    observed = row["observed"]
    assert observed["epochs"] == 3 and observed["sybil_takeovers"] == 1
    assert abs(observed["attacker_weight_fraction"] - 1 / 3) < 1e-9
    assert observed["split_epochs"] == 0
    assert inc.summarize([], share)["observed"] is None


def test_an_empty_weight_row_with_roles_is_unverified_not_a_crash():
    config = {
        "schema": inc.SCHEMA,
        "validator_hotkey": "5Publisher",
        "intake_url": "http://127.0.0.1:1",
        "feed_key": "00" * 32,
        "policy": "testnet-winner-v1",
        "roles": True,
    }

    async def weights(context, hotkey):
        return [], {0: "5Burn"}

    class Testnet:
        network = "testnet"

    result = inc.check(
        config,
        weights_reader=weights,
        leaderboard_reader=lambda url, key: {},
        context=Testnet(),
    )
    assert result["state"] == inc.UNVERIFIED
    assert result["findings"][0] == {"level": inc.UNVERIFIED, "code": "no_weights_set"}


def test_weight_before_the_feed_releases_the_incumbent_is_unverified():
    hotkeys = {0: "5Burn", 14: "5Strong", 99: CANARY_HOTKEYS[0]}
    row = [[0, 40000], [14, 25535]]
    result = inc.verify_epoch(
        row, hotkeys, {"battery": None}, 3, frozenset(CANARY_HOTKEYS)
    )
    assert result["state"] == inc.UNVERIFIED
    assert {
        "level": inc.UNVERIFIED,
        "code": "weight_to_unreleased_incumbent",
        "uid": 14,
    } in (result["findings"])
    # A canary is a blocker whether or not anything is released.
    result = inc.verify_epoch(
        [[0, 40000], [99, 25535]],
        hotkeys,
        {"battery": None},
        3,
        frozenset(CANARY_HOTKEYS),
    )
    assert result["state"] == inc.BLOCKER


# --- the incentive readback: weight became payment ---------------------------------


def test_a_weighted_miner_with_incentive_is_paid_and_without_is_attention():
    row = [[0, 65535], [5, 32767]]
    paid = inc.verify_incentive(row, [43690, 0, 0, 0, 0, 21844, 0])
    assert paid == [
        {
            "level": inc.PASS,
            "code": "weighted_uid_paid",
            "uid": 5,
            "incentive": 0.333318,
        }
    ]
    lagging = inc.verify_incentive(row, [65535, 0, 0, 0, 0, 0, 0])
    assert lagging == [
        {"level": inc.ATTENTION, "code": "weighted_uid_no_incentive", "uid": 5}
    ]


def test_a_miner_paid_by_another_validator_is_attention():
    found = inc.verify_incentive([[0, 65535]], [40000, 0, 0, 25535])
    assert found == [
        {"level": inc.ATTENTION, "code": "incentive_not_from_this_validator", "uid": 3}
    ]


def test_check_folds_the_incentive_readback_into_its_state():
    config = {
        "schema": inc.SCHEMA,
        "validator_hotkey": "5Validator",
        "intake_url": "http://127.0.0.1:1",
        "feed_key": "00" * 32,
        "policy": "testnet-winner-v1",
    }

    async def weights(context, hotkey):
        return (
            [[0, 65535], [5, 32767]],
            {0: "5Burn", 5: "5MinerA"},
            [43690] + [0] * 4 + [21844],
        )

    class Testnet:
        network = "testnet"

    result = inc.check(
        config,
        weights_reader=weights,
        incumbent_reader=lambda url, key: None,
        context=Testnet(),
    )
    codes = [f["code"] for f in result["findings"]]
    assert "weight_to_unreleased_incumbent" in codes and "weighted_uid_paid" in codes
    assert result["state"] == inc.UNVERIFIED
