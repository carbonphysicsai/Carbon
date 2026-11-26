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
        Participant(uid=3, hotkey="hk_loyal_1", coldkey="ck_loyal_1", registered_at=110),
        Participant(uid=4, hotkey="hk_loyal_2", coldkey="ck_loyal_2", registered_at=120),
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
    base = dict(
        hold_window_epochs=600,  # 30 days at 20 epochs/day
        hold_cap_q12=300_000_000_000,  # 30% max hold bonus cap
        window_bonus_rate_bps=2000,  # 20% over 30-day window
        zero_bonus_sold_bps=5000,  # 0 bonus at >= 50% sold
        treasury_sinks=(
            PinnedTreasurySink("hk_sink_0", "ck_vault", 200),
            PinnedTreasurySink("hk_sink_1", "ck_vault", 205),
        ),
        treasury_stake_cap_rao=50_000 * RAO,
        excluded_coldkeys=frozenset({"ck_vault", "ck_owner"}),
        enforce_king_u16_floor=True,
    )
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
    """Dumping 60% in epoch 5 and rebuying 100% in epoch 6 keeps `worst_sold == 3/5` (zero bonus
    under 50% cutoff) until epoch 5 ages out of the window."""
    ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        ledger.record_crown_earnings(1, {"ck_loyal_1": (100 * RAO, "hk_loyal_1")})
        for ep in range(1, 5):
            ledger.sample_epoch_stakes(ep, {"ck_loyal_1": 100 * RAO})
        # Epoch 5: sells 60 alpha -> staked = 40 alpha -> sold_ratio = 60/100 = 3/5 >= 50%
        ledger.sample_epoch_stakes(5, {"ck_loyal_1": 40 * RAO})
        # Epoch 6..14: rebuys back to 150 alpha (even above earned!)
        for ep in range(6, 15):
            ledger.sample_epoch_stakes(ep, {"ck_loyal_1": 150 * RAO})

        # Window of 10 epochs at epoch 14 covers [5..14] -> still includes epoch 5 dump!
        held_14, worst_14 = ledger.window_status("ck_loyal_1", 14, 10)
        assert held_14 == 100 * RAO  # Capped at cumulative_earned_rao (external purchase ignored)
        assert worst_14 == Fraction(60, 100)
        assert epoch_bonus_rate(worst_14, 2000, 5000, 10) == Fraction(0)

        # Epoch 15: window of 10 covers [6..15] -> dump at epoch 5 aged out -> back to 0% sold!
        ledger.sample_epoch_stakes(15, {"ck_loyal_1": 150 * RAO})
        held_15, worst_15 = ledger.window_status("ck_loyal_1", 15, 10)
        assert held_15 == 100 * RAO
        assert worst_15 == Fraction(0)
        assert epoch_bonus_rate(worst_15, 2000, 5000, 10) == Fraction(2000, 10_000 * 10)
    finally:
        ledger.close()


def test_waterfall_precedence_bonus_first_then_treasury_then_burn(tmp_path):
    """Day 2 (king at 50%): Hold Bonus gets first claim on the 50% decayed weight,
    unused decayed weight flows to the 2 pinned Treasury sinks, and integer dust burns to UID 0."""
    policy = load_policy("mainnet-winner-v4")
    t0 = 1_700_000_000_000
    snap = _snapshot(t0 + DAY_MS)  # 24h after promotion -> king gets 50% (5e11 Q12)
    ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        # Miner ck_loyal_1 earned 30,000 alpha and held 100% -> 20% / 600 per epoch = 10 alpha target
        # With epoch_miner_emission_rao = 100 alpha, desired weight = 10 / 100 = 10% of Q12 (1e11)
        ledger.record_crown_earnings(27, {"ck_loyal_1": (30_000 * RAO, "hk_loyal_1")})
        # Vault and owner coldkeys also recorded to prove they are strictly excluded from Hold Bonus!
        ledger.record_crown_earnings(27, {"ck_vault": (90_000 * RAO, "hk_sink_0"), "ck_owner": (90_000 * RAO, "hk_burn_owner")})
        ledger.sample_epoch_stakes(
            27,
            {"ck_loyal_1": 30_000 * RAO, "ck_vault": 90_000 * RAO, "ck_owner": 90_000 * RAO},
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
            [{"hotkey": "hk_king", "coldkey": "ck_king", "registered_at": 100}, 500_000_000_000]
        ]
        # Rung 2: ck_loyal_1 gets exact 10% = 100_000_000_000 (vault & owner excluded!)
        assert targets["hold_bonus"] == [
            [{"hotkey": "hk_loyal_1", "coldkey": "ck_loyal_1", "registered_at": 110}, 100_000_000_000]
        ]
        # Rung 3: Remaining 40% (400_000_000_000) split evenly across 2 pinned Treasury sinks = 200_000_000_000 each
        assert targets["treasury"] == [
            [{"hotkey": "hk_sink_0", "coldkey": "ck_vault", "registered_at": 200}, 200_000_000_000],
            [{"hotkey": "hk_sink_1", "coldkey": "ck_vault", "registered_at": 205}, 200_000_000_000],
        ]
        assert targets["burn"] == 0

        # Compile through carbon.chain.publication.compile_targets to verify u16 compilation & invariants!
        resolved = {
            "intent": {"context": asdict(snap.context), "route": WATERFALL_ROUTE, "targets": targets},
            "projection": {"route": WATERFALL_ROUTE, "targets": targets},
        }
        plan = compile_targets(
            resolved, snap, _caps(snap), "hk_publisher", network="finney", spec_version=495
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


def test_when_no_miners_take_bonus_and_treasury_at_cap_all_decayed_burns_to_uid0(tmp_path):
    """1) Zero hold bonus uptake -> 100% of decayed goes to Treasury while below stake cap.
    2) Once Treasury reaches `treasury_stake_cap_rao` (or stake read is None), 100% falls through to UID 0 burn!"""
    policy = load_policy("mainnet-winner-v4")
    t0 = 1_700_000_000_000
    snap = _snapshot(t0 + 2 * DAY_MS)  # Day 3: king at 25% (2.5e11), decayed = 75% (7.5e11)

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
        "intent": {"context": asdict(snap.context), "route": WATERFALL_ROUTE, "targets": targets},
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
    earning exact +50% window rate on `1,000 α` under `window_bonus_rate_bps=5000`, `hold_cap_q12=400_000_000_000`."""
    policy = load_policy("mainnet-winner-v4")
    t0 = 1_700_000_000_000
    snap = _snapshot(t0 + DAY_MS)  # Day 2: king at 50% (5e11 Q12), decayed = 5e11 Q12
    launch_cfg = _wf_cfg(
        hold_window_epochs=600,
        hold_cap_q12=400_000_000_000,  # 40% epoch cap
        window_bonus_rate_bps=5000,    # +50% over 30d at 0% sold
        zero_bonus_sold_bps=5000,      # 50% sold cutoff
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
        assert eligible_held == 1_000 * RAO  # Exact C = 1,000 α, zero bonus-on-bonus compounding!

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
            [{"hotkey": "hk_loyal_1", "coldkey": "ck_loyal_1", "registered_at": 110}, 83_333_333_333]
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
            [{"hotkey": "hk_loyal_1", "coldkey": "ck_loyal_1", "registered_at": 110}, 400_000_000_000]
        ]
    finally:
        ledger.close()


def test_bonus_yield_dumping_is_penalized_across_window_and_zeroed_at_cutoff(tmp_path):
    """If a miner with `C = 1,000 α` and `H = 500 α` dumps the `500 α` bonus (`B = 1,000 α`),
    `worst_sold == 1/3` (rate slashed by 2/3 under 50% cutoff) and `eligible_held == 666_666_666_666` rao,
    staying penalized across the window even if they rebuy to `2,000 α` next epoch;
    and dumping `750 α` (`B = 750 α`, 50% of `C + H`) drops bonus to exact `0`."""
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

        # Epoch 3..11: miner rebuys to 2,000 α (above C + H = 1,500 α) -> still penalized for full 10-epoch window!
        for ep in range(3, 12):
            ledger.sample_epoch_stakes(ep, {"ck_loyal_1": 2_000 * RAO})
        held_11, worst_11 = ledger.window_status("ck_loyal_1", 11, 10)
        assert held_11 == 1_000 * RAO
        assert worst_11 == Fraction(1, 3)

        # Epoch 12: epoch 2 dump ages out of 10-epoch window [3..12], restoring 0% sold
        ledger.sample_epoch_stakes(12, {"ck_loyal_1": 2_000 * RAO})
        held_12, worst_12 = ledger.window_status("ck_loyal_1", 12, 10)
        assert held_12 == 1_000 * RAO
        assert worst_12 == Fraction(0)

        # Epoch 13: miner dumps 750 α (`B = 750 α` == 50% of `C + H = 1,500 α`) -> exact 0 bonus!
        ledger.sample_epoch_stakes(13, {"ck_loyal_1": 750 * RAO})
        held_13, worst_13 = ledger.window_status("ck_loyal_1", 13, 10)
        assert held_13 == 500 * RAO
        assert worst_13 == Fraction(1, 2)
        assert epoch_bonus_rate(worst_13, 5000, 5000, 600) == Fraction(0)
    finally:
        ledger.close()


def test_preview_overlay_with_bonus_credits_matches_committed_state_and_migrates_legacy_db(tmp_path):
    """1) Legacy SQLite DB without `cumulative_bonus_rao` migrates cleanly in place.
    2) Non-mutating `compute_waterfall_targets(..., bonus_credits_by_coldkey=...)` matches committed
       `record_bonus_earnings` + `sample_epoch_stakes` byte-for-byte."""
    import sqlite3

    db_path = tmp_path / "legacy_hold.sqlite3"
    raw_conn = sqlite3.connect(str(db_path))
    with raw_conn:
        raw_conn.execute(
            """CREATE TABLE hold_coldkey_totals_v1 (
                coldkey TEXT PRIMARY KEY,
                cumulative_earned_rao TEXT NOT NULL,
                preferred_hotkey TEXT NOT NULL,
                updated_epoch INTEGER NOT NULL
            )"""
        )
        raw_conn.execute(
            """CREATE TABLE hold_epoch_credits_v1 (
                epoch INTEGER NOT NULL,
                coldkey TEXT NOT NULL,
                earned_delta_rao TEXT NOT NULL,
                hotkey TEXT NOT NULL,
                PRIMARY KEY(epoch, coldkey)
            )"""
        )
        raw_conn.execute(
            """CREATE TABLE hold_epoch_samples_v1 (
                epoch INTEGER NOT NULL,
                coldkey TEXT NOT NULL,
                staked_rao TEXT NOT NULL,
                cumulative_earned_rao TEXT NOT NULL,
                sold_rao TEXT NOT NULL,
                PRIMARY KEY(epoch, coldkey)
            )"""
        )
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
