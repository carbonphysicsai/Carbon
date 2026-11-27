"""Tests for Track 3: 4-Rung Post-Crown Settlement Waterfall & Miner Hold Bonus."""

from __future__ import annotations

from dataclasses import asdict
from fractions import Fraction

import pytest

from carbon.chain.models import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.publication import RuntimeCapabilities, compile_targets
from carbon.rewards.core import DAY_MS, Q12, RewardFailure
from carbon.rewards.waterfall import (
    MIN_POSITIVE_U16_Q12,
    WATERFALL_ROUTE,
    HoldBonusLedger,
    PinnedTreasurySink,
    WaterfallConfig,
    compute_waterfall_targets,
    epoch_bonus_rate,
)
from carbon.rewards.winner_decay import Winner, load_policy

RAO = 10**9
GENESIS = "0x" + "22" * 32
BLOCK_HASH = "0x" + "33" * 32


def _ctx(network: str = "finney", netuid: int = 116) -> ChainContext:
    return ChainContext(
        network=network,
        endpoint="wss://entrypoint-finney.opentensor.ai:443",
        provider="test",
        genesis_hash=GENESIS,
        netuid=netuid,
    )


def _snapshot(now_ms: int, block: int = 10_000) -> MetagraphSnapshot:
    participants = (
        Participant(uid=0, hotkey="hk_burn_owner", coldkey="ck_owner", registered_at=1),
        Participant(uid=1, hotkey="hk_publisher", coldkey="ck_owner", registered_at=1),
        Participant(uid=2, hotkey="hk_king", coldkey="ck_king", registered_at=100),
        Participant(
            uid=3, hotkey="hk_loyal_1", coldkey="ck_loyal_1", registered_at=110
        ),
        Participant(
            uid=4, hotkey="hk_loyal_2", coldkey="ck_loyal_2", registered_at=120
        ),
        Participant(uid=5, hotkey="hk_sink_0", coldkey="ck_vault", registered_at=200),
        Participant(uid=6, hotkey="hk_sink_1", coldkey="ck_vault", registered_at=205),
    )
    return MetagraphSnapshot(
        context=_ctx(),
        finalized_block=block,
        block_hash=BLOCK_HASH,
        timestamp_ms=now_ms,
        participants=participants,
    )


def _caps(snap: MetagraphSnapshot) -> RuntimeCapabilities:
    return RuntimeCapabilities(
        snapshot_id=snap.snapshot_id,
        spec_version=495,
        mechanism_count=1,
        maximum_mechanisms=8,
        burn_mode="Burn",
        owner_coldkey="ck_owner",
        owner_hotkey="hk_burn_owner",
        owner_hotkeys=("hk_burn_owner",),
        min_weights=1,
        max_weight=65535,
        version_key=1,
        rate_limit=100,
        last_update=1,
        commit_reveal=True,
        validator_permit=True,
        sufficient_stake=True,
        pending_commits=0,
    )


def _wf_cfg(**overrides) -> WaterfallConfig:
    base = {
        "hold_window_epochs": 600,  # 30 days at 20 epochs/day
        "hold_cap_q12": 300_000_000_000,  # 30% max hold bonus cap
        "window_bonus_rate_bps": 2000,  # 20% over 30-day window
        "zero_bonus_sold_bps": 5000,  # 0 bonus at >= 50% sold
        "treasury_sinks": (
            PinnedTreasurySink("hk_sink_0", "ck_vault", 200),
            PinnedTreasurySink("hk_sink_1", "ck_vault", 205),
        ),
        "treasury_stake_cap_rao": 50_000 * RAO,
        "excluded_coldkeys": frozenset({"ck_vault", "ck_owner"}),
        "enforce_king_u16_floor": True,
    }
    base.update(overrides)
    return WaterfallConfig(**base)


def test_point_in_time_sold_ratio_does_not_penalize_new_crown_earnings(tmp_path):
    """Critical Hold Bonus math fix: winning +900 alpha on epoch 10 after holding 100 alpha
    for epochs 1..9 yields 0% sold (`worst_sold == 0`), NOT 90% sold!"""
    ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        ledger.record_crown_earnings(1, {"ck_loyal_1": (100 * RAO, "hk_loyal_1")})
        for ep in range(1, 10):
            ledger.sample_epoch_stakes(ep, {"ck_loyal_1": 100 * RAO})

        # Epoch 10: miner wins a huge new crown (+900 alpha -> 1,000 cumulative) and holds all 1,000!
        ledger.record_crown_earnings(10, {"ck_loyal_1": (900 * RAO, "hk_loyal_1")})
        ledger.sample_epoch_stakes(10, {"ck_loyal_1": 1_000 * RAO})

        eligible_held, worst_sold = ledger.window_status("ck_loyal_1", 10, 600)
        assert eligible_held == 1_000 * RAO
        assert worst_sold == Fraction(0)
    finally:
        ledger.close()


def test_dump_and_rebuy_stays_penalized_across_window_until_expiry(tmp_path):
    """1) Dumping 60% in epoch 5 (`B = 40 α` out of `100 α`) and buying `110 α` on the market
       in epoch 6 (`B = 150 α`, `ΔI = 0`) records `external_stake_rao == 110 α`, so market
       rebuy NEVER restores `retained_mined_rao` (`40 α`, `60%` sold -> `0` bonus even at epoch 15).
    2) Only earning and holding NEW mined Alpha (`+200 α` in epoch 16 -> `B = 350 α`,
       `retained_mined_rao = 240 α` out of `300 α` -> `20%` current sold) dilutes the sale,
       and `worst_sold` still stays at `60%` (`0` bonus) until epoch 15 ages out of the 10-epoch
       window at epoch 25!"""
    ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        ledger.record_crown_earnings(1, {"ck_loyal_1": (100 * RAO, "hk_loyal_1")})
        for ep in range(1, 5):
            ledger.sample_epoch_stakes(ep, {"ck_loyal_1": 100 * RAO})
        # Epoch 5: sells 60 alpha -> staked = 40 alpha -> sold_ratio = 60/100 = 3/5 >= 50%
        ledger.sample_epoch_stakes(5, {"ck_loyal_1": 40 * RAO})
        # Epoch 6..15: buys 110 alpha on market (`B = 150 α`, `ΔI = 0`) -> external_stake_rao = 110 α!
        for ep in range(6, 16):
            ledger.sample_epoch_stakes(ep, {"ck_loyal_1": 150 * RAO})

        assert ledger.coldkey_stake_tracking("ck_loyal_1") == (110 * RAO, 150 * RAO)
        held_15, worst_15 = ledger.window_status("ck_loyal_1", 15, 10)
        assert (
            held_15 == 40 * RAO
        )  # Market-bought Alpha never restores sold mined principal!
        assert worst_15 == Fraction(60, 100)
        assert epoch_bonus_rate(worst_15, 2000, 5000, 10) == Fraction(0)

        # Epoch 16: legitimately mines +200 α new Crown rewards and holds them (`B = 350 α`, `I = 300 α`)
        ledger.record_crown_earnings(16, {"ck_loyal_1": (200 * RAO, "hk_loyal_1")})
        for ep in range(16, 25):
            ledger.sample_epoch_stakes(ep, {"ck_loyal_1": 350 * RAO})
        # At epoch 24, window [15..24] still includes epoch 15 (`60%` sold) -> still 0 bonus!
        held_24, worst_24 = ledger.window_status("ck_loyal_1", 24, 10)
        assert held_24 == 240 * RAO
        assert worst_24 == Fraction(60, 100)
        assert epoch_bonus_rate(worst_24, 2000, 5000, 10) == Fraction(0)

        # At epoch 25, window [16..25] has aged out epoch 15 -> worst_sold drops to 60/300 = 1/5 (20%)!
        ledger.sample_epoch_stakes(25, {"ck_loyal_1": 350 * RAO})
        held_25, worst_25 = ledger.window_status("ck_loyal_1", 25, 10)
        assert held_25 == 240 * RAO
        assert worst_25 == Fraction(1, 5)
        assert epoch_bonus_rate(worst_25, 2000, 5000, 10) == (
            Fraction(2000, 10_000 * 10) * Fraction(3, 5)
        )
    finally:
        ledger.close()


def test_waterfall_precedence_bonus_first_then_treasury_then_burn(tmp_path):
    """Day 2 (king at 50%): Hold Bonus gets first claim on the 50% decayed weight,
    unused decayed weight flows to the 2 pinned Treasury sinks, and integer dust burns to UID 0.
    """
    policy = load_policy("mainnet-winner-v4")
    t0 = 1_700_000_000_000
    snap = _snapshot(t0 + DAY_MS)  # 24h after promotion -> king gets 50% (5e11 Q12)
    ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        # Miner ck_loyal_1 earned 30,000 alpha and held 100% -> 20% / 600 per epoch = 10 alpha target
        # With epoch_miner_emission_rao = 100 alpha, desired weight = 10 / 100 = 10% of Q12 (1e11)
        ledger.record_crown_earnings(27, {"ck_loyal_1": (30_000 * RAO, "hk_loyal_1")})
        # Vault and owner coldkeys also recorded to prove they are strictly excluded from Hold Bonus!
        ledger.record_crown_earnings(
            27,
            {
                "ck_vault": (90_000 * RAO, "hk_sink_0"),
                "ck_owner": (90_000 * RAO, "hk_burn_owner"),
            },
        )
        ledger.sample_epoch_stakes(
            27,
            {
                "ck_loyal_1": 30_000 * RAO,
                "ck_vault": 90_000 * RAO,
                "ck_owner": 90_000 * RAO,
            },
        )

        targets = compute_waterfall_targets(
            policy,
            _wf_cfg(),
            snap,
            {"electric-motor-magnetics": Winner("hk_king", t0)},
            epoch=27,
            hold_ledger=ledger,
            epoch_miner_emission_rao=100 * RAO,
            treasury_current_stake_rao=10_000 * RAO,
            owner_coldkey="ck_owner",
            owner_hotkeys=("hk_burn_owner",),
            publisher_hotkey="hk_publisher",
        )

        # Rung 1: King gets 50% = 500_000_000_000
        assert targets["winners"] == [
            [
                {"hotkey": "hk_king", "coldkey": "ck_king", "registered_at": 100},
                500_000_000_000,
            ]
        ]
        # Rung 2: ck_loyal_1 gets exact 10% = 100_000_000_000 (vault & owner excluded!)
        assert targets["hold_bonus"] == [
            [
                {"hotkey": "hk_loyal_1", "coldkey": "ck_loyal_1", "registered_at": 110},
                100_000_000_000,
            ]
        ]
        # Rung 3: Remaining 40% (400_000_000_000) split evenly across 2 pinned Treasury sinks = 200_000_000_000 each
        assert targets["treasury"] == [
            [
                {"hotkey": "hk_sink_0", "coldkey": "ck_vault", "registered_at": 200},
                200_000_000_000,
            ],
            [
                {"hotkey": "hk_sink_1", "coldkey": "ck_vault", "registered_at": 205},
                200_000_000_000,
            ],
        ]
        assert targets["burn"] == 0

        # Compile through carbon.chain.publication.compile_targets to verify u16 compilation & invariants!
        resolved = {
            "intent": {
                "context": asdict(snap.context),
                "route": WATERFALL_ROUTE,
                "targets": targets,
            },
            "projection": {"route": WATERFALL_ROUTE, "targets": targets},
        }
        plan = compile_targets(
            resolved,
            snap,
            _caps(snap),
            "hk_publisher",
            network="finney",
            spec_version=495,
        )
        assert dict(plan.q12) == {
            2: 500_000_000_000,
            3: 100_000_000_000,
            5: 200_000_000_000,
            6: 200_000_000_000,
        }
        assert sum(dict(plan.q12).values()) == Q12
    finally:
        ledger.close()


def test_when_no_miners_take_bonus_and_treasury_at_cap_all_decayed_burns_to_uid0(
    tmp_path,
):
    """1) Zero hold bonus uptake -> 100% of decayed goes to Treasury while below stake cap.
    2) Once Treasury reaches `treasury_stake_cap_rao` (or stake read is None), 100% falls through to UID 0 burn!
    """
    policy = load_policy("mainnet-winner-v4")
    t0 = 1_700_000_000_000
    snap = _snapshot(
        t0 + 2 * DAY_MS
    )  # Day 3: king at 25% (2.5e11), decayed = 75% (7.5e11)

    # Case A: Below stake cap, no hold bonus -> all 75% goes to Treasury sinks
    below_cap = compute_waterfall_targets(
        policy,
        _wf_cfg(),
        snap,
        {"electric-motor-magnetics": Winner("hk_king", t0)},
        epoch=27,
        hold_ledger=None,
        epoch_miner_emission_rao=100 * RAO,
        treasury_current_stake_rao=49_999 * RAO,
        owner_coldkey="ck_owner",
        owner_hotkeys=("hk_burn_owner",),
        publisher_hotkey="hk_publisher",
    )
    assert below_cap["hold_bonus"] == []
    assert sum(v for _, v in below_cap["treasury"]) == 750_000_000_000
    assert below_cap["burn"] == 0

    # Case B: At stake cap (`50_000 * RAO`) -> 0 to Treasury, all 75% burns to UID 0!
    at_cap = compute_waterfall_targets(
        policy,
        _wf_cfg(),
        snap,
        {"electric-motor-magnetics": Winner("hk_king", t0)},
        epoch=27,
        hold_ledger=None,
        epoch_miner_emission_rao=100 * RAO,
        treasury_current_stake_rao=50_000 * RAO,
        owner_coldkey="ck_owner",
        owner_hotkeys=("hk_burn_owner",),
        publisher_hotkey="hk_publisher",
    )
    assert at_cap["treasury"] == []
    assert at_cap["burn"] == 750_000_000_000

    # Case C: Missing stake observation (`None`) -> fail-closed -> 0 to Treasury, all 75% burns to UID 0!
    missing_obs = compute_waterfall_targets(
        policy,
        _wf_cfg(),
        snap,
        {"electric-motor-magnetics": Winner("hk_king", t0)},
        epoch=27,
        hold_ledger=None,
        epoch_miner_emission_rao=100 * RAO,
        treasury_current_stake_rao=None,
        owner_coldkey="ck_owner",
        owner_hotkeys=("hk_burn_owner",),
        publisher_hotkey="hk_publisher",
    )
    assert missing_obs["treasury"] == []
    assert missing_obs["burn"] == 750_000_000_000


def test_king_u16_integer_floor_prevents_zero_quantization_at_deep_decay():
    """After 25 days of halving (`Q12 >> 25 = 29,802`), without the u16 floor the king would
    quantize to `u16 = 0` against a 99.999% Treasury/Burn share. With `enforce_king_u16_floor`,
    the king receives `MIN_POSITIVE_U16_Q12` and compiles to `u16 >= 1`!"""
    policy = load_policy("mainnet-winner-v4")
    t0 = 1_700_000_000_000
    snap = _snapshot(t0 + 25 * DAY_MS)

    targets = compute_waterfall_targets(
        policy,
        _wf_cfg(),
        snap,
        {"electric-motor-magnetics": Winner("hk_king", t0)},
        epoch=500,
        treasury_current_stake_rao=1_000 * RAO,
        owner_coldkey="ck_owner",
        owner_hotkeys=("hk_burn_owner",),
        publisher_hotkey="hk_publisher",
    )
    assert targets["winners"][0][1] == MIN_POSITIVE_U16_Q12

    resolved = {
        "intent": {
            "context": asdict(snap.context),
            "route": WATERFALL_ROUTE,
            "targets": targets,
        },
        "projection": {"route": WATERFALL_ROUTE, "targets": targets},
    }
    plan = compile_targets(
        resolved, snap, _caps(snap), "hk_publisher", network="finney", spec_version=495
    )
    int_map = dict(plan.integers)
    assert int_map[2] >= 1  # King UID 2 stays strictly > 0 in u16 weights!


def test_recycled_sink_uid_fails_identity_pin_and_falls_through_to_burn():
    """If sink_0 deregisters and an attacker re-registers on that UID/hotkey at block 999 != 200,
    its identity pin fails and only valid sinks (or UID 0 burn) receive weight."""
    policy = load_policy("mainnet-winner-v4")
    t0 = 1_700_000_000_000
    snap = _snapshot(t0 + DAY_MS)
    # Pin expects registered_at=999 for sink_0 and sink_1 -> neither matches snapshot (200, 205)!
    hijacked_cfg = _wf_cfg(
        treasury_sinks=(
            PinnedTreasurySink("hk_sink_0", "ck_vault", 999),
            PinnedTreasurySink("hk_sink_1", "ck_attacker", 205),
        )
    )
    targets = compute_waterfall_targets(
        policy,
        hijacked_cfg,
        snap,
        {"electric-motor-magnetics": Winner("hk_king", t0)},
        epoch=27,
        treasury_current_stake_rao=0,
        owner_coldkey="ck_owner",
        owner_hotkeys=("hk_burn_owner",),
        publisher_hotkey="hk_publisher",
    )
    assert targets["treasury"] == []
    assert targets["burn"] == 500_000_000_000


def test_non_compounding_bonus_principal_at_50pct_rate_and_40pct_cap(tmp_path):
    """Miner with Crown `C = 1,000 α` and Hold Bonus `H = 500 α` holding `B = 1,500 α`
    gets `worst_sold == 0` and non-compounding `eligible_held == 1,000 α` (NOT `1,500 α`),
    earning exact +50% window rate on `1,000 α` under `window_bonus_rate_bps=5000`, `hold_cap_q12=400_000_000_000`.
    """
    policy = load_policy("mainnet-winner-v4")
    t0 = 1_700_000_000_000
    snap = _snapshot(t0 + DAY_MS)  # Day 2: king at 50% (5e11 Q12), decayed = 5e11 Q12
    launch_cfg = _wf_cfg(
        hold_window_epochs=600,
        hold_cap_q12=400_000_000_000,  # 40% epoch cap
        window_bonus_rate_bps=5000,  # +50% over 30d at 0% sold
        zero_bonus_sold_bps=5000,  # 50% sold cutoff
    )
    ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        ledger.record_crown_earnings(1, {"ck_loyal_1": (1_000 * RAO, "hk_loyal_1")})
        ledger.record_bonus_earnings(1, {"ck_loyal_1": (500 * RAO, "hk_loyal_1")})
        # Idempotent re-recording succeeds; conflicting re-recording fails closed
        ledger.record_bonus_earnings(1, {"ck_loyal_1": (500 * RAO, "hk_loyal_1")})
        with pytest.raises(RewardFailure, match="CONFLICTING_EPOCH_BONUS_CREDIT"):
            ledger.record_bonus_earnings(1, {"ck_loyal_1": (499 * RAO, "hk_loyal_1")})

        ledger.sample_epoch_stakes(1, {"ck_loyal_1": 1_500 * RAO})
        eligible_held, worst_sold = ledger.window_status("ck_loyal_1", 1, 600)
        assert worst_sold == Fraction(0)
        assert (
            eligible_held == 1_000 * RAO
        )  # Exact C = 1,000 α, zero bonus-on-bonus compounding!

        # With epoch_miner_emission_rao = 10 α:
        # target_alpha = 1,000 α * (5000 / (10_000 * 600)) = (5/6) α
        # desired_q12 = ((5/6) α * 10^12) // 10 α = 83_333_333_333 Q12 (NOT 125_000_000_000!)
        targets = compute_waterfall_targets(
            policy,
            launch_cfg,
            snap,
            {"electric-motor-magnetics": Winner("hk_king", t0)},
            epoch=1,
            hold_ledger=ledger,
            epoch_miner_emission_rao=10 * RAO,
            treasury_current_stake_rao=1_000 * RAO,
            owner_coldkey="ck_owner",
            owner_hotkeys=("hk_burn_owner",),
            publisher_hotkey="hk_publisher",
        )
        assert targets["hold_bonus"] == [
            [
                {"hotkey": "hk_loyal_1", "coldkey": "ck_loyal_1", "registered_at": 110},
                83_333_333_333,
            ]
        ]

        # Also verify the 40% epoch cap (`hold_cap_q12 = 400_000_000_000`) clamps when emission is small (1 α)
        capped = compute_waterfall_targets(
            policy,
            launch_cfg,
            snap,
            {"electric-motor-magnetics": Winner("hk_king", t0)},
            epoch=1,
            hold_ledger=ledger,
            epoch_miner_emission_rao=1 * RAO,
            treasury_current_stake_rao=1_000 * RAO,
            owner_coldkey="ck_owner",
            owner_hotkeys=("hk_burn_owner",),
            publisher_hotkey="hk_publisher",
        )
        assert capped["hold_bonus"] == [
            [
                {"hotkey": "hk_loyal_1", "coldkey": "ck_loyal_1", "registered_at": 110},
                400_000_000_000,
            ]
        ]
    finally:
        ledger.close()


def test_bonus_yield_dumping_is_penalized_across_window_and_zeroed_at_cutoff(tmp_path):
    """If a miner with `C = 1,000 α` and `H = 500 α` dumps the `500 α` bonus (`B = 1,000 α`),
    `worst_sold == 1/3` (rate slashed by 2/3 under 50% cutoff) and `eligible_held == 666_666_666_666` rao;
    buying `1,000 α` on the market (`B = 2,000 α`, `ΔI = 0`) adds `external_stake_rao = 1,000 α`
    and never restores sold bonus yield (`retained_mined_rao` stays `1,000 α` even at epoch 12);
    and selling another `250 α` (`B = 1,750 α`, `retained_mined_rao = 750 α` == 50% of `C + H`)
    drops bonus to exact `0`."""
    ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        ledger.record_crown_earnings(1, {"ck_loyal_1": (1_000 * RAO, "hk_loyal_1")})
        ledger.record_bonus_earnings(1, {"ck_loyal_1": (500 * RAO, "hk_loyal_1")})
        ledger.sample_epoch_stakes(1, {"ck_loyal_1": 1_500 * RAO})

        # Epoch 2: dumps all 500 α Hold Bonus (`B = 1,000 α` out of `I = 1,500 α`)
        ledger.sample_epoch_stakes(2, {"ck_loyal_1": 1_000 * RAO})
        held_2, worst_2 = ledger.window_status("ck_loyal_1", 2, 10)
        assert worst_2 == Fraction(1, 3)
        assert held_2 == 666_666_666_666
        full_rate = epoch_bonus_rate(Fraction(0), 5000, 5000, 600)
        slashed_rate = epoch_bonus_rate(worst_2, 5000, 5000, 600)
        assert slashed_rate == full_rate * Fraction(1, 3)  # Slashed by 2/3!

        # Epoch 3..12: miner buys 1,000 α on market (`B = 2,000 α`, `ΔI = 0`) -> external = 1,000 α!
        for ep in range(3, 13):
            ledger.sample_epoch_stakes(ep, {"ck_loyal_1": 2_000 * RAO})
        assert ledger.coldkey_stake_tracking("ck_loyal_1") == (1_000 * RAO, 2_000 * RAO)
        held_12, worst_12 = ledger.window_status("ck_loyal_1", 12, 10)
        assert held_12 == 666_666_666_666
        assert worst_12 == Fraction(1, 3)

        # Epoch 13: miner sells another 250 α (`B = 1,750 α`, `retained_mined_rao = 750 α` == 50% of `I`) -> exact 0 bonus!
        ledger.sample_epoch_stakes(13, {"ck_loyal_1": 1_750 * RAO})
        held_13, worst_13 = ledger.window_status("ck_loyal_1", 13, 10)
        assert held_13 == 500 * RAO
        assert worst_13 == Fraction(1, 2)
        assert epoch_bonus_rate(worst_13, 5000, 5000, 600) == Fraction(0)
    finally:
        ledger.close()


def test_preview_overlay_with_bonus_credits_matches_committed_state_and_migrates_legacy_db(
    tmp_path,
):
    """1) Legacy SQLite DB without `cumulative_bonus_rao` migrates cleanly in place.
    2) Non-mutating `compute_waterfall_targets(..., bonus_credits_by_coldkey=...)` matches committed
       `record_bonus_earnings` + `sample_epoch_stakes` byte-for-byte."""
    import sqlite3

    db_path = tmp_path / "legacy_hold.sqlite3"
    raw_conn = sqlite3.connect(str(db_path))
    with raw_conn:
        raw_conn.execute("""CREATE TABLE hold_coldkey_totals_v1 (
                coldkey TEXT PRIMARY KEY,
                cumulative_earned_rao TEXT NOT NULL,
                preferred_hotkey TEXT NOT NULL,
                updated_epoch INTEGER NOT NULL
            )""")
        raw_conn.execute("""CREATE TABLE hold_epoch_credits_v1 (
                epoch INTEGER NOT NULL,
                coldkey TEXT NOT NULL,
                earned_delta_rao TEXT NOT NULL,
                hotkey TEXT NOT NULL,
                PRIMARY KEY(epoch, coldkey)
            )""")
        raw_conn.execute("""CREATE TABLE hold_epoch_samples_v1 (
                epoch INTEGER NOT NULL,
                coldkey TEXT NOT NULL,
                staked_rao TEXT NOT NULL,
                cumulative_earned_rao TEXT NOT NULL,
                sold_rao TEXT NOT NULL,
                PRIMARY KEY(epoch, coldkey)
            )""")
        raw_conn.execute(
            "INSERT INTO hold_coldkey_totals_v1 VALUES ('ck_loyal_1', ?, 'hk_loyal_1', 1)",
            (str(1_000 * RAO),),
        )
        raw_conn.execute(
            "INSERT INTO hold_epoch_credits_v1 VALUES (1, 'ck_loyal_1', ?, 'hk_loyal_1')",
            (str(1_000 * RAO),),
        )
        raw_conn.execute(
            "INSERT INTO hold_epoch_samples_v1 VALUES (1, 'ck_loyal_1', ?, ?, '0')",
            (str(1_000 * RAO), str(1_000 * RAO)),
        )
    raw_conn.close()

    policy = load_policy("mainnet-winner-v4")
    t0 = 1_700_000_000_000
    snap = _snapshot(t0 + DAY_MS)
    cfg = _wf_cfg(
        hold_window_epochs=600,
        hold_cap_q12=400_000_000_000,
        window_bonus_rate_bps=5000,
        zero_bonus_sold_bps=5000,
    )

    ledger = HoldBonusLedger(db_path)
    try:
        # Epoch 2 preview: miner earned +500 α bonus, but only holds B = 1,000 α (dumped the 500 α bonus!)
        preview_targets = compute_waterfall_targets(
            policy,
            cfg,
            snap,
            {"electric-motor-magnetics": Winner("hk_king", t0)},
            epoch=2,
            hold_ledger=ledger,
            epoch_miner_emission_rao=10 * RAO,
            treasury_current_stake_rao=1_000 * RAO,
            staked_by_coldkey={"ck_loyal_1": 1_000 * RAO},
            bonus_credits_by_coldkey={"ck_loyal_1": (500 * RAO, "hk_loyal_1")},
            owner_coldkey="ck_owner",
            owner_hotkeys=("hk_burn_owner",),
            publisher_hotkey="hk_publisher",
        )
        # Verify nothing was written to SQLite during preview
        assert ledger._conn.execute(
            "SELECT COUNT(*) FROM hold_epoch_bonus_credits_v1"
        ).fetchone() == (0,)
        assert ledger._conn.execute(
            "SELECT COUNT(*) FROM hold_epoch_samples_v1 WHERE epoch=2"
        ).fetchone() == (0,)

        # Now commit via record_bonus_earnings + sample_epoch_stakes and verify byte-for-byte parity
        ledger.record_bonus_earnings(2, {"ck_loyal_1": (500 * RAO, "hk_loyal_1")})
        ledger.sample_epoch_stakes(2, {"ck_loyal_1": 1_000 * RAO})
        committed_targets = compute_waterfall_targets(
            policy,
            cfg,
            snap,
            {"electric-motor-magnetics": Winner("hk_king", t0)},
            epoch=2,
            hold_ledger=ledger,
            epoch_miner_emission_rao=10 * RAO,
            treasury_current_stake_rao=1_000 * RAO,
            owner_coldkey="ck_owner",
            owner_hotkeys=("hk_burn_owner",),
            publisher_hotkey="hk_publisher",
        )
        assert preview_targets == committed_targets

        # Historical roll-back preview for epoch 1 (while updated_epoch == 2) subtracts epoch 2 bonus cleanly
        assert ledger.window_status_preview(
            "ck_loyal_1", 1, 600, pending_stake_rao=1_000 * RAO
        ) == (1_000 * RAO, Fraction(0))
    finally:
        ledger.close()


def test_f2_empty_challenge_slots_burn_directly_to_uid0_never_funding_bonus_or_treasury(
    tmp_path,
):
    """F2 (Owner Option A): On a 3-challenge policy (`share = 333_333_333_333`, `Q12 % 3 = 1`),
    when Challenge 0 has a decaying King at 50% (`166_666_666_666`) and Challenges 1 & 2 have
    NO payable King:
    - Challenges 1 & 2 (`2 * 333_333_333_333 = 666_666_666_666`) + `Q12 % 3` (`1`) go directly
      to Rung 4 (`UID 0` burn) and NEVER enter the Rung 2 Hold Bonus or Rung 3 Treasury pool!
    - ONLY Challenge 0's decayed `166_666_666_667` funds Rung 2 Hold Bonus and Rung 3 Treasury.
    """
    policy = load_policy("testnet-winner-v1")  # 3 challenges -> share = 333_333_333_333
    t0 = 1_700_000_000_000
    snap = MetagraphSnapshot(
        context=_ctx(network="testnet", netuid=567),
        finalized_block=10_000,
        block_hash=BLOCK_HASH,
        timestamp_ms=t0 + DAY_MS,  # 24h elapsed -> Challenge 0 King at 50%
        participants=(
            Participant(
                uid=0, hotkey="hk_burn_owner", coldkey="ck_owner", registered_at=1
            ),
            Participant(
                uid=1, hotkey="hk_publisher", coldkey="ck_owner", registered_at=1
            ),
            Participant(uid=2, hotkey="hk_king", coldkey="ck_king", registered_at=100),
            Participant(
                uid=3, hotkey="hk_loyal_1", coldkey="ck_loyal_1", registered_at=110
            ),
            Participant(
                uid=4, hotkey="hk_loyal_2", coldkey="ck_loyal_2", registered_at=120
            ),
            Participant(
                uid=5, hotkey="hk_sink_0", coldkey="ck_vault", registered_at=200
            ),
            Participant(
                uid=6, hotkey="hk_sink_1", coldkey="ck_vault", registered_at=205
            ),
        ),
    )
    ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        # ck_loyal_1 desires 100_000_000_000 Q12 (10% of Q12)
        ledger.record_crown_earnings(1, {"ck_loyal_1": (30_000 * RAO, "hk_loyal_1")})
        ledger.sample_epoch_stakes(1, {"ck_loyal_1": 30_000 * RAO})

        targets = compute_waterfall_targets(
            policy,
            _wf_cfg(hold_cap_q12=400_000_000_000),
            snap,
            {policy.challenges[0]: Winner("hk_king", t0)},
            epoch=1,
            hold_ledger=ledger,
            epoch_miner_emission_rao=100 * RAO,
            treasury_current_stake_rao=10_000 * RAO,
            owner_coldkey="ck_owner",
            owner_hotkeys=("hk_burn_owner",),
            publisher_hotkey="hk_publisher",
        )
        # Active King gets 50% of 1/3 = 166_666_666_666
        assert targets["winners"] == [
            [
                {"hotkey": "hk_king", "coldkey": "ck_king", "registered_at": 100},
                166_666_666_666,
            ]
        ]
        # Hold Bonus gets 100_000_000_000 out of the 166_666_666_667 active-King decay
        assert targets["hold_bonus"] == [
            [
                {"hotkey": "hk_loyal_1", "coldkey": "ck_loyal_1", "registered_at": 110},
                100_000_000_000,
            ]
        ]
        # Treasury gets ONLY remaining active-King decay: 66_666_666_667 // 2 = 33_333_333_333 per sink
        assert targets["treasury"] == [
            [
                {"hotkey": "hk_sink_0", "coldkey": "ck_vault", "registered_at": 200},
                33_333_333_333,
            ],
            [
                {"hotkey": "hk_sink_1", "coldkey": "ck_vault", "registered_at": 205},
                33_333_333_333,
            ],
        ]
        # Burn gets both empty slots (2 * 333_333_333_333) + Q12 % 3 (1) + Treasury dust (1) = 666_666_666_668
        assert targets["burn"] == 666_666_666_668
        assert (
            sum(v for _, v in targets["winners"])
            + sum(v for _, v in targets["hold_bonus"])
            + sum(v for _, v in targets["treasury"])
            + targets["burn"]
            == Q12
        )

        # Also verify when desired Hold Bonus exceeds active-King decay (e.g. emission=1 α -> desired=10e12),
        # Hold Bonus is strictly capped at `decayed_from_active_kings_q12` (166_666_666_667), NOT hold_cap_q12 (4e11)!
        capped = compute_waterfall_targets(
            policy,
            _wf_cfg(hold_cap_q12=400_000_000_000),
            snap,
            {policy.challenges[0]: Winner("hk_king", t0)},
            epoch=1,
            hold_ledger=ledger,
            epoch_miner_emission_rao=1 * RAO,
            treasury_current_stake_rao=10_000 * RAO,
            owner_coldkey="ck_owner",
            owner_hotkeys=("hk_burn_owner",),
            publisher_hotkey="hk_publisher",
        )
        assert capped["hold_bonus"] == [
            [
                {"hotkey": "hk_loyal_1", "coldkey": "ck_loyal_1", "registered_at": 110},
                166_666_666_667,
            ]
        ]
        assert capped["treasury"] == []
        assert capped["burn"] == 666_666_666_667
    finally:
        ledger.close()


def test_f4_anti_masking_preexisting_transferred_and_loyal_alpha_cases(tmp_path):
    """F4 anti-masking verification across all three required scenarios + JSONL reload:
    (a) Miner holding 5,000 α pre-existing who wins 1,000 α and sells 1,000 α (`B_C = 5,000 α`)
        gets 100% sold (`0%` bonus) — both when pre-existing stake was observed before winning
        and when observed alongside winning then sold next epoch.
    (b) Miner who wins 1,000 α, transfers in 1,000 α from a second key (`B_C = 2,000 α`),
        then sells 1,000 α (`B_C = 1,000 α`) gets 100% sold (`0%` bonus).
    (c) Miner holding 5,000 α pre-existing who wins 1,000 α + 100 α bonus (`B_C = 6,100 α`)
        and sells nothing gets 0% sold and +50% full bonus on 1,000 α Crown principal.
    """
    policy = load_policy("mainnet-winner-v4")
    t0 = 1_700_000_000_000
    snap = _snapshot(t0 + DAY_MS)
    cfg = _wf_cfg(
        hold_window_epochs=600,
        hold_cap_q12=400_000_000_000,
        window_bonus_rate_bps=5000,
        zero_bonus_sold_bps=5000,
    )

    # --- Case (a1): Pre-existing 5,000 α observed at epoch 0, wins 1,000 α & sells 1,000 α by epoch 1 ---
    ledger_a1 = HoldBonusLedger(tmp_path / "case_a1.jsonl")
    try:
        ledger_a1.sample_epoch_stakes(0, {"ck_loyal_1": 5_000 * RAO})
        assert ledger_a1.coldkey_stake_tracking("ck_loyal_1") == (
            5_000 * RAO,
            5_000 * RAO,
        )
        ledger_a1.record_crown_earnings(1, {"ck_loyal_1": (1_000 * RAO, "hk_loyal_1")})
        ledger_a1.sample_epoch_stakes(1, {"ck_loyal_1": 5_000 * RAO})
        assert ledger_a1.window_status("ck_loyal_1", 1, 600) == (0, Fraction(1))
    finally:
        ledger_a1.close()

    # --- Case (a2): First observed at epoch 1 holding 5,000 α + 1,000 α won = 6,000 α, sells 1,000 α at epoch 2 ---
    ledger_a2 = HoldBonusLedger(tmp_path / "case_a2.jsonl")
    try:
        ledger_a2.record_crown_earnings(1, {"ck_loyal_1": (1_000 * RAO, "hk_loyal_1")})
        ledger_a2.sample_epoch_stakes(1, {"ck_loyal_1": 6_000 * RAO})
        assert ledger_a2.coldkey_stake_tracking("ck_loyal_1") == (
            5_000 * RAO,
            6_000 * RAO,
        )
        assert ledger_a2.window_status("ck_loyal_1", 1, 600) == (
            1_000 * RAO,
            Fraction(0),
        )

        ledger_a2.sample_epoch_stakes(2, {"ck_loyal_1": 5_000 * RAO})
        assert ledger_a2.window_status("ck_loyal_1", 2, 600) == (0, Fraction(1))
        targets_a2 = compute_waterfall_targets(
            policy,
            cfg,
            snap,
            {"electric-motor-magnetics": Winner("hk_king", t0)},
            epoch=2,
            hold_ledger=ledger_a2,
            epoch_miner_emission_rao=10 * RAO,
            treasury_current_stake_rao=1_000 * RAO,
            owner_coldkey="ck_owner",
            owner_hotkeys=("hk_burn_owner",),
            publisher_hotkey="hk_publisher",
        )
        assert targets_a2["hold_bonus"] == []
    finally:
        ledger_a2.close()

    # --- Case (b): Wins 1,000 α, transfers in 1,000 α (`B = 2,000 α`), sells 1,000 α (`B = 1,000 α`) -> 100% sold ---
    jsonl_b = tmp_path / "case_b.jsonl"
    ledger_b = HoldBonusLedger(jsonl_b)
    try:
        ledger_b.record_crown_earnings(1, {"ck_loyal_1": (1_000 * RAO, "hk_loyal_1")})
        ledger_b.sample_epoch_stakes(1, {"ck_loyal_1": 1_000 * RAO})
        ledger_b.sample_epoch_stakes(2, {"ck_loyal_1": 2_000 * RAO})
        assert ledger_b.coldkey_stake_tracking("ck_loyal_1") == (
            1_000 * RAO,
            2_000 * RAO,
        )
        # Verify preview overlay at epoch 3 matches committed sample_epoch_stakes(3, 1_000 α)
        assert ledger_b.window_status_preview(
            "ck_loyal_1", 3, 600, pending_stake_rao=1_000 * RAO
        ) == (0, Fraction(1))
        ledger_b.sample_epoch_stakes(3, {"ck_loyal_1": 1_000 * RAO})
        assert ledger_b.window_status("ck_loyal_1", 3, 600) == (0, Fraction(1))
    finally:
        ledger_b.close()

    # Reload JSONL from disk and verify external_stake_rao & 100% sold survive restart
    reloaded_b = HoldBonusLedger(jsonl_b)
    try:
        assert reloaded_b.coldkey_stake_tracking("ck_loyal_1") == (
            1_000 * RAO,
            1_000 * RAO,
        )
        assert reloaded_b.window_status("ck_loyal_1", 3, 600) == (0, Fraction(1))
    finally:
        reloaded_b.close()

    # --- Case (c): 5,000 α pre-existing + 1,000 α Crown + 100 α Bonus (`B = 6,100 α`) -> 0% sold, +50% on 1,000 α ---
    ledger_c = HoldBonusLedger(tmp_path / "case_c.jsonl")
    try:
        ledger_c.sample_epoch_stakes(0, {"ck_loyal_1": 5_000 * RAO})
        ledger_c.record_crown_earnings(1, {"ck_loyal_1": (1_000 * RAO, "hk_loyal_1")})
        ledger_c.record_bonus_earnings(1, {"ck_loyal_1": (100 * RAO, "hk_loyal_1")})
        ledger_c.sample_epoch_stakes(1, {"ck_loyal_1": 6_100 * RAO})
        assert ledger_c.coldkey_stake_tracking("ck_loyal_1") == (
            5_000 * RAO,
            6_100 * RAO,
        )
        assert ledger_c.window_status("ck_loyal_1", 1, 600) == (
            1_000 * RAO,
            Fraction(0),
        )

        targets_c = compute_waterfall_targets(
            policy,
            cfg,
            snap,
            {"electric-motor-magnetics": Winner("hk_king", t0)},
            epoch=1,
            hold_ledger=ledger_c,
            epoch_miner_emission_rao=10 * RAO,
            treasury_current_stake_rao=1_000 * RAO,
            owner_coldkey="ck_owner",
            owner_hotkeys=("hk_burn_owner",),
            publisher_hotkey="hk_publisher",
        )
        # +50% over 600 epochs on 1,000 α Crown principal at 10 α epoch emission = 83_333_333_333 Q12
        assert targets_c["hold_bonus"] == [
            [
                {"hotkey": "hk_loyal_1", "coldkey": "ck_loyal_1", "registered_at": 110},
                83_333_333_333,
            ]
        ]
    finally:
        ledger_c.close()


def test_f5_excluded_coldkeys_enforced_on_king_pay_and_fail_closed_inputs(tmp_path):
    """F5: Excluded coldkeys (`excluded_coldkeys`, `treasury_sinks`, and `owner_coldkey` on finney)
    receive 0 on Rung 1 King pay AND burn their Challenge slot directly to `UID 0` (never funding
    Rung 2 Hold Bonus or Rung 3 Treasury); missing `owner_coldkey` on finney or missing
    `epoch_miner_emission_rao` with active `hold_ledger` fails closed."""
    policy = load_policy("mainnet-winner-v4")
    t0 = 1_700_000_000_000
    vault_ck = "5HVHGgWc1RvFFCkS678oB4DBjR8ZumAiAFsVXDf3aJCNbY8T"
    snap = MetagraphSnapshot(
        context=_ctx(),
        finalized_block=10_000,
        block_hash=BLOCK_HASH,
        timestamp_ms=t0 + DAY_MS,
        participants=(
            Participant(
                uid=0, hotkey="hk_burn_owner", coldkey="ck_owner", registered_at=1
            ),
            Participant(
                uid=1, hotkey="hk_publisher", coldkey="ck_validator", registered_at=1
            ),
            Participant(
                uid=2, hotkey="hk_vault_miner", coldkey=vault_ck, registered_at=100
            ),
            Participant(
                uid=3, hotkey="hk_loyal_1", coldkey="ck_loyal_1", registered_at=110
            ),
            Participant(
                uid=4, hotkey="hk_loyal_2", coldkey="ck_loyal_2", registered_at=120
            ),
            Participant(
                uid=5, hotkey="hk_sink_0", coldkey="ck_vault", registered_at=200
            ),
            Participant(
                uid=6, hotkey="hk_sink_1", coldkey="ck_vault", registered_at=205
            ),
        ),
    )
    cfg = _wf_cfg(excluded_coldkeys=frozenset({"ck_vault", "ck_owner", vault_ck}))
    ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        ledger.record_crown_earnings(1, {"ck_loyal_1": (30_000 * RAO, "hk_loyal_1")})
        ledger.sample_epoch_stakes(1, {"ck_loyal_1": 30_000 * RAO})

        # Excluded King (`hk_vault_miner` under `vault_ck`) gets 0 King pay AND burns 100% Q12 to UID 0!
        targets = compute_waterfall_targets(
            policy,
            cfg,
            snap,
            {"electric-motor-magnetics": Winner("hk_vault_miner", t0)},
            epoch=1,
            hold_ledger=ledger,
            epoch_miner_emission_rao=100 * RAO,
            treasury_current_stake_rao=1_000 * RAO,
            owner_coldkey="ck_owner",
            owner_hotkeys=("hk_burn_owner",),
            publisher_hotkey="hk_publisher",
        )
        assert targets["winners"] == []
        assert targets["hold_bonus"] == []
        assert targets["treasury"] == []
        assert targets["burn"] == Q12

        # Missing owner_coldkey on finney fails closed with OWNER_COLDKEY_REQUIRED
        with pytest.raises(RewardFailure, match="OWNER_COLDKEY_REQUIRED"):
            compute_waterfall_targets(
                policy,
                cfg,
                snap,
                {},
                epoch=1,
                owner_coldkey=None,
            )

        # Missing epoch_miner_emission_rao when hold_ledger is active fails closed
        with pytest.raises(RewardFailure, match="EMISSION_OBSERVATION_REQUIRED"):
            compute_waterfall_targets(
                policy,
                cfg,
                snap,
                {},
                epoch=1,
                hold_ledger=ledger,
                epoch_miner_emission_rao=None,
                owner_coldkey="ck_owner",
            )
    finally:
        ledger.close()
