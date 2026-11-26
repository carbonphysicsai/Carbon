"""End-to-end tests for prospective waterfall policy loading, preview, issuance, and publication."""

from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import json
import shutil
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.chain import ChainContext, MetagraphSnapshot, Participant
from carbon.chain.publication import RuntimeCapabilities, U16
from carbon.chain.publisher import TransactionObservation
from carbon.development_testnet.operator import DEFAULT_ENDPOINT, TESTNET_GENESIS
from carbon.rewards import testnet_winner_publication as twp
from carbon.rewards import winner_decay as wd
from carbon.rewards import winner_eligibility as we
from carbon.rewards.core import DAY_MS, Q12, RewardFailure
from carbon.rewards.waterfall import (
    WATERFALL_ROUTE,
    HoldBonusLedger,
    PinnedTreasurySink,
    WaterfallConfig,
    WaterfallEpochObservation,
)
from carbon.transport.store import ReceiptJournal

RAO = 10**9
SPEC = 471
RECORD = "e" * 64


def _valid_waterfall_dict(**overrides) -> dict:
    base = {
        "hold_window_epochs": 600,
        "hold_cap_q12": 300_000_000_000,
        "window_bonus_rate_bps": 2000,
        "zero_bonus_sold_bps": 5000,
        "treasury_stake_cap_rao": 100_000 * RAO,
        "treasury_sinks": [
            {"hotkey": "hk_sink_0", "coldkey": "ck_vault", "registered_at": 10},
            {"hotkey": "hk_sink_1", "coldkey": "ck_vault", "registered_at": 11},
        ],
        "excluded_coldkeys": ["ck_vault", "ck_owner"],
        "enforce_king_u16_floor": True,
    }
    base.update(overrides)
    return base


def _pin_policy_copy(tmp_path: Path, base_version: str = "testnet-winner-v1", **doc_updates) -> Path:
    copy = tmp_path / "weight_policies"
    if copy.exists():
        shutil.rmtree(copy)
    shutil.copytree(wd.POLICY_DIR, copy)
    path = copy / f"{base_version}.json"
    document = json.loads(path.read_text())
    document.update(doc_updates)
    path.write_text(json.dumps(document))
    registry = json.loads((copy / "registry.json").read_text())
    registry["versions"][base_version] = (
        "sha256:" + hashlib.sha256(wd._canonical(document)).hexdigest()
    )
    (copy / "registry.json").write_text(json.dumps(registry))
    return copy


def _testnet_ctx(netuid: int = 567) -> ChainContext:
    return ChainContext(
        "testnet", DEFAULT_ENDPOINT, "bittensor-official-test", TESTNET_GENESIS, netuid
    )


def _waterfall_snapshot(
    ctx: ChainContext,
    *,
    block: int = 1080,
    timestamp_ms: int = 10 * DAY_MS,
) -> MetagraphSnapshot:
    participants = (
        Participant(0, "hk_burn_owner", "ck_owner", 1),
        Participant(1, "hk_publisher", "ck_validator", 2),
        Participant(2, "hk_king", "ck_king", 3),
        Participant(3, "hk_loyal", "ck_loyal", 4),
        Participant(4, "hk_sink_0", "ck_vault", 10),
        Participant(5, "hk_sink_1", "ck_vault", 11),
    )
    return MetagraphSnapshot(
        context=ctx,
        finalized_block=block,
        block_hash="0x" + f"{block:064x}",
        timestamp_ms=timestamp_ms,
        participants=participants,
    )


def _caps(state: MetagraphSnapshot) -> RuntimeCapabilities:
    return RuntimeCapabilities(
        snapshot_id=state.snapshot_id,
        spec_version=SPEC,
        mechanism_count=1,
        maximum_mechanisms=8,
        burn_mode="Burn",
        owner_coldkey="ck_owner",
        owner_hotkey="hk_burn_owner",
        owner_hotkeys=("hk_burn_owner",),
        min_weights=1,
        max_weight=U16,
        version_key=1,
        rate_limit=0,
        last_update=0,
        commit_reveal=False,
        validator_permit=True,
        sufficient_stake=True,
    )


class _WaterfallBackend:
    """In-memory publication backend preserving multi-participant snapshots across dispatch."""

    def __init__(self, state: MetagraphSnapshot, publisher: str = "hk_publisher"):
        self.context = state.context
        self.publisher = publisher
        self.state = state
        self.executions = 0
        self.signed = 0
        self.tx_hash = "0x" + "b" * 64
        self.tx_block: int | None = None
        self.row: list[list[int]] = []

    async def observe(self):
        return self.state, _caps(self.state)

    async def execute(self, plan, integer_guard, call_checked, before_sign, dispatch):
        self.executions += 1
        uids = [uid for uid, _ in plan.integers]
        values = [value for _, value in plan.integers]
        preflight = SimpleNamespace(
            uid=plan.publisher_uid,
            min_allowed_weights=1,
            max_weight_limit=U16,
            commit_reveal=False,
        )
        await integer_guard(uids, values, preflight)
        call = SimpleNamespace(data=b"checked-waterfall-weights", spec_version=SPEC)
        await call_checked(call, {})
        await before_sign(call, self.publisher)
        self.signed += 1
        await dispatch(self.tx_hash)
        next_block = self.state.finalized_block + 1
        self.state = dataclasses.replace(
            self.state,
            finalized_block=next_block,
            block_hash="0x" + f"{next_block:064x}",
        )
        self.tx_block = next_block
        self.row = [list(item) for item in plan.integers]

    async def transaction(self, tx_hash, block):
        if tx_hash == self.tx_hash and block == self.tx_block:
            return TransactionObservation(True, block, self.state.block_hash)
        return None

    async def revealed(self, publisher, block):
        return False

    async def weight_row(self, state, uid):
        return self.row, self.tx_block


# ---------------------------------------------------------------------------
# 1. Policy Loading & Immutable Registered Policies
# ---------------------------------------------------------------------------


def test_all_existing_registered_policies_load_with_waterfall_none():
    registry = json.loads((wd.POLICY_DIR / "registry.json").read_text())
    assert registry["current"] == "testnet-winner-v1"
    legacy_without_waterfall = {
        "testnet-winner-v1",
        "testnet-winner-v2-four-challenge-dev",
        "testnet-winner-v3-five-challenge-dev",
        "testnet-winner-v4-launch",
        "testnet-winner-v5-launch",
        "mainnet-winner-v1",
        "mainnet-winner-v2",
        "mainnet-winner-v3",
        "mainnet-winner-v4",
    }
    assert legacy_without_waterfall <= set(registry["versions"])
    for version, pinned_digest in registry["versions"].items():
        policy = wd.load_policy(version)
        assert policy.digest == pinned_digest
        if version in legacy_without_waterfall:
            assert policy.waterfall is None
        else:
            assert isinstance(policy.waterfall, WaterfallConfig)


def test_prospective_waterfall_policy_loads_frozen_waterfall_config(tmp_path):
    wf_dict = _valid_waterfall_dict()
    copy = _pin_policy_copy(tmp_path, **{wd.WATERFALL_POLICY_KEY: wf_dict})
    policy = wd.load_policy("testnet-winner-v1", directory=copy)
    assert isinstance(policy.waterfall, WaterfallConfig)
    assert policy.waterfall == WaterfallConfig(
        hold_window_epochs=600,
        hold_cap_q12=300_000_000_000,
        window_bonus_rate_bps=2000,
        zero_bonus_sold_bps=5000,
        treasury_sinks=(
            PinnedTreasurySink("hk_sink_0", "ck_vault", 10),
            PinnedTreasurySink("hk_sink_1", "ck_vault", 11),
        ),
        treasury_stake_cap_rao=100_000 * RAO,
        excluded_coldkeys=frozenset({"ck_vault", "ck_owner"}),
        enforce_king_u16_floor=True,
    )

    # Also verify coexistence with `qualified_sealed` on mainnet-winner-v4
    copy_v4 = _pin_policy_copy(
        tmp_path / "v4",
        base_version="mainnet-winner-v4",
        **{wd.WATERFALL_POLICY_KEY: wf_dict},
    )
    policy_v4 = wd.load_policy("mainnet-winner-v4", directory=copy_v4)
    assert policy_v4.qualified_sealed != ()
    assert isinstance(policy_v4.waterfall, WaterfallConfig)


@pytest.mark.parametrize(
    "bad_waterfall",
    [
        None,
        [],
        "waterfall",
        # Missing required key
        {k: v for k, v in _valid_waterfall_dict().items() if k != "enforce_king_u16_floor"},
        # Extra unexpected key
        {**_valid_waterfall_dict(), "extra_param": 1},
        # Bool instead of int
        _valid_waterfall_dict(hold_window_epochs=True),
        _valid_waterfall_dict(hold_cap_q12=False),
        _valid_waterfall_dict(treasury_stake_cap_rao=True),
        # Int instead of bool
        _valid_waterfall_dict(enforce_king_u16_floor=1),
        # Out-of-range values
        _valid_waterfall_dict(hold_window_epochs=0),
        _valid_waterfall_dict(hold_cap_q12=Q12 + 1),
        _valid_waterfall_dict(hold_cap_q12=-1),
        _valid_waterfall_dict(window_bonus_rate_bps=-1),
        _valid_waterfall_dict(zero_bonus_sold_bps=0),
        _valid_waterfall_dict(zero_bonus_sold_bps=10_001),
        _valid_waterfall_dict(treasury_stake_cap_rao=-1),
        # Malformed treasury_sinks
        _valid_waterfall_dict(treasury_sinks="not-a-list"),
        _valid_waterfall_dict(treasury_sinks=[{"hotkey": "hk_sink_0", "coldkey": "ck_vault"}]),
        _valid_waterfall_dict(
            treasury_sinks=[
                {"hotkey": "hk_sink_0", "coldkey": "ck_vault", "registered_at": 10, "extra": 1}
            ]
        ),
        _valid_waterfall_dict(
            treasury_sinks=[{"hotkey": "hk_sink_0", "coldkey": "ck_vault", "registered_at": True}]
        ),
        _valid_waterfall_dict(
            treasury_sinks=[{"hotkey": "", "coldkey": "ck_vault", "registered_at": 10}]
        ),
        # Duplicate sink hotkeys
        _valid_waterfall_dict(
            treasury_sinks=[
                {"hotkey": "hk_dup", "coldkey": "ck_vault", "registered_at": 10},
                {"hotkey": "hk_dup", "coldkey": "ck_vault", "registered_at": 11},
            ]
        ),
        # Malformed excluded_coldkeys
        _valid_waterfall_dict(excluded_coldkeys="ck_vault"),
        _valid_waterfall_dict(excluded_coldkeys=[123]),
        _valid_waterfall_dict(excluded_coldkeys=[""]),
        _valid_waterfall_dict(excluded_coldkeys=["ck_vault", "ck_vault"]),
    ],
)
def test_malformed_waterfall_policy_blocks_raise_weight_policy_malformed(
    tmp_path, bad_waterfall
):
    copy = _pin_policy_copy(tmp_path, **{wd.WATERFALL_POLICY_KEY: bad_waterfall})
    with pytest.raises(RewardFailure) as exc_info:
        wd.load_policy("testnet-winner-v1", directory=copy)
    assert str(exc_info.value) == "WEIGHT_POLICY_MALFORMED"


# ---------------------------------------------------------------------------
# 2. End-to-End 4-Rung Preview -> Issue -> Publish + Idempotence
# ---------------------------------------------------------------------------


def _compose_waterfall_publisher(
    tmp_path: Path,
    *,
    state: MetagraphSnapshot,
    hold_ledger: HoldBonusLedger | None,
    observer,
    source=None,
    wf_overrides: dict | None = None,
):
    copy = _pin_policy_copy(
        tmp_path / "policies",
        **{wd.WATERFALL_POLICY_KEY: _valid_waterfall_dict(**(wf_overrides or {}))},
    )
    policy = wd.load_policy("testnet-winner-v1", directory=copy)
    auth = twp.StandingAuthorization(
        authority_record_digest=RECORD,
        policy_digest=policy.digest,
        context=state.context,
        publisher_hotkey="hk_publisher",
        expected_runtime_spec=SPEC,
        valid_from_block=900,
        valid_through_block=2000,
    )
    receipts = ReceiptJournal(tmp_path / "publication.sqlite3", auth.context)
    winner_ledger = we.WinnerLedger(tmp_path / "winners.jsonl")
    challenge = policy.challenges[0]
    sources = {} if source is None else {challenge: source}
    issuer = twp.TestnetWinnerIntentIssuer(
        receipts,
        auth,
        policy,
        winner_ledger,
        sources,
        hold_ledger=hold_ledger,
        waterfall_observer=observer,
    )
    backend = _WaterfallBackend(state)
    publisher = twp.TestnetWinnerPublisher(issuer, backend)
    return policy, issuer, backend, publisher


def test_end_to_end_four_rung_preview_issue_publish_and_idempotence(tmp_path):
    """4-rung epoch (block 1080 -> epoch 3, 3-challenge testnet policy):
    - Rung 1 (Active King `hk_king` on Challenge 0, Day 1): `333_333_333_333` Q12
    - Rung 2 (Loyal Past King `ck_loyal` Hold Bonus): `100_000_000_000` Q12
      (earned 25,000 Alpha in epoch 2 + 5,000 Alpha pending in epoch 3 = 30,000 Alpha held 100%,
       bonus rate = 20% / 600 -> 10 Alpha target out of 100 Alpha epoch miner emission = 10% Q12)
    - Rung 3 (2 Pinned Treasury Sinks `hk_sink_0`, `hk_sink_1` below cap):
      `566_666_666_667 // 2 = 283_333_333_333` Q12 each
    - Rung 4 (UID 0 Burn): `1` Q12 residual dust -> exact `Q12` conservation!"""
    ctx = _testnet_ctx()
    state = _waterfall_snapshot(ctx, block=1080, timestamp_ms=10 * DAY_MS)
    hold_ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        # Prior epoch 2 history for Loyal Past King (`ck_loyal`)
        hold_ledger.record_crown_earnings(2, {"ck_loyal": (25_000 * RAO, "hk_loyal")})
        hold_ledger.sample_epoch_stakes(2, {"ck_loyal": 25_000 * RAO})

        def _ledger_snapshot():
            return (
                hold_ledger._conn.execute(
                    "SELECT * FROM hold_coldkey_totals_v1 ORDER BY coldkey"
                ).fetchall(),
                hold_ledger._conn.execute(
                    "SELECT * FROM hold_epoch_credits_v1 ORDER BY epoch, coldkey"
                ).fetchall(),
                hold_ledger._conn.execute(
                    "SELECT * FROM hold_epoch_samples_v1 ORDER BY epoch, coldkey"
                ).fetchall(),
            )

        before_preview_sql = _ledger_snapshot()

        def observer(_snap: MetagraphSnapshot, epoch: int) -> WaterfallEpochObservation:
            assert epoch == 3
            return WaterfallEpochObservation(
                epoch_miner_emission_rao=100 * RAO,
                treasury_current_stake_rao=10_000 * RAO,
                staked_by_coldkey={
                    "ck_loyal": 30_000 * RAO,
                    "ck_king": 5_000 * RAO,
                    "ck_vault": 10_000 * RAO,
                    "ck_owner": 50_000 * RAO,
                },
                crown_credits_by_coldkey={
                    "ck_loyal": (5_000 * RAO, "hk_loyal"),
                    "ck_vault": (10_000 * RAO, "hk_sink_0"),
                    "ck_owner": (10_000 * RAO, "hk_burn_owner"),
                },
                owner_coldkey="ck_owner",
                owner_hotkeys=("hk_burn_owner",),
            )

        policy, issuer, backend, publisher = _compose_waterfall_publisher(
            tmp_path,
            state=state,
            hold_ledger=hold_ledger,
            observer=observer,
            source=lambda: {
                "model_id": "m-king-1",
                "hotkey": "hk_king",
                "previous": None,
                "kind": we.FIRST,
            },
        )

        # 1) Non-mutating preview: computes exact 4-rung targets, writes NOTHING to SQLite or WinnerLedger!
        seen = twp.preview(issuer, state)
        assert seen["signed"] is False
        assert _ledger_snapshot() == before_preview_sql
        assert issuer.ledger.records() == []
        with issuer.receipts.transaction() as db:
            assert db.execute(
                "SELECT COUNT(*) FROM testnet_winner_intent_v1"
            ).fetchone() == (0,)

        expected_targets = {
            "challenges": seen["targets"]["challenges"],
            "winners": [
                [{"hotkey": "hk_king", "coldkey": "ck_king", "registered_at": 3}, 333_333_333_333]
            ],
            "hold_bonus": [
                [{"hotkey": "hk_loyal", "coldkey": "ck_loyal", "registered_at": 4}, 100_000_000_000]
            ],
            "treasury": [
                [{"hotkey": "hk_sink_0", "coldkey": "ck_vault", "registered_at": 10}, 283_333_333_333],
                [{"hotkey": "hk_sink_1", "coldkey": "ck_vault", "registered_at": 11}, 283_333_333_333],
            ],
            "burn": 1,
        }
        assert seen["targets"] == expected_targets
        assert (
            sum(v for _, v in expected_targets["winners"])
            + sum(v for _, v in expected_targets["hold_bonus"])
            + sum(v for _, v in expected_targets["treasury"])
            + expected_targets["burn"]
            == Q12
        )

        # 2) Issue: records epoch 3 credits & stakes into HoldBonusLedger and stores waterfall intent
        ref = issuer.issue(state)
        assert hold_ledger.window_status("ck_loyal", 3, 600) == (30_000 * RAO, Fraction(0))
        after_first_issue_sql = _ledger_snapshot()

        # Idempotence on second issue(state) in same epoch
        later_same_epoch = dataclasses.replace(
            state, finalized_block=1085, block_hash="0x" + f"{1085:064x}"
        )
        assert issuer.issue(later_same_epoch) == ref
        assert _ledger_snapshot() == after_first_issue_sql

        # Preview after issue also matches without double-counting credits
        assert twp.preview(issuer, state)["targets"] == expected_targets

        resolved = issuer.resolve(ref, state)
        assert resolved["intent"]["route"] == WATERFALL_ROUTE
        assert resolved["intent"]["no_winner"] is False
        assert resolved["projection"]["route"] == WATERFALL_ROUTE
        assert resolved["intent"]["targets"] == expected_targets

        # 3) Publish through TestnetWinnerPublisher -> VerifiedWeightPublisher -> compile_targets
        result = asyncio.run(publisher.publish(ref))
        assert result["state"] == "ROW_VERIFIED"
        assert backend.executions == backend.signed == 1

        plan_doc = result["document"]["plan"]
        assert plan_doc["q12"] == [
            [0, 1],
            [2, 333_333_333_333],
            [3, 100_000_000_000],
            [4, 283_333_333_333],
            [5, 283_333_333_333],
        ]
        top = 333_333_333_333
        expected_integers = [
            [2, round(Fraction(333_333_333_333 * U16, top))],
            [3, round(Fraction(100_000_000_000 * U16, top))],
            [4, round(Fraction(283_333_333_333 * U16, top))],
            [5, round(Fraction(283_333_333_333 * U16, top))],
        ]
        assert expected_integers == [[2, 65535], [3, 19661], [4, 55705], [5, 55705]]
        assert plan_doc["integers"] == expected_integers

        # Publishing the same ref again returns the journaled ROW_VERIFIED result without re-signing
        assert asyncio.run(publisher.publish(ref)) == result
        assert backend.executions == backend.signed == 1
    finally:
        hold_ledger.close()


# ---------------------------------------------------------------------------
# 3. Fail-Closed Treasury Cap & Missing Observation -> Residual Burns to UID 0
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "observed_treasury_stake",
    [
        None,               # Missing observation -> fail-closed
        100_000 * RAO,      # Exactly at cap -> gated off
        150_000 * RAO,      # Above cap -> gated off
    ],
)
def test_treasury_missing_or_at_cap_fails_closed_and_burns_residual_to_uid0(
    tmp_path, observed_treasury_stake
):
    ctx = _testnet_ctx()
    state = _waterfall_snapshot(ctx, block=1080, timestamp_ms=10 * DAY_MS)
    hold_ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        hold_ledger.record_crown_earnings(2, {"ck_loyal": (30_000 * RAO, "hk_loyal")})
        hold_ledger.sample_epoch_stakes(2, {"ck_loyal": 30_000 * RAO})

        def observer(_snap: MetagraphSnapshot, _epoch: int) -> WaterfallEpochObservation:
            return WaterfallEpochObservation(
                epoch_miner_emission_rao=100 * RAO,
                treasury_current_stake_rao=observed_treasury_stake,
                staked_by_coldkey={"ck_loyal": 30_000 * RAO},
                owner_coldkey="ck_owner",
                owner_hotkeys=("hk_burn_owner",),
            )

        _policy, issuer, backend, publisher = _compose_waterfall_publisher(
            tmp_path,
            state=state,
            hold_ledger=hold_ledger,
            observer=observer,
            source=lambda: {
                "model_id": "m-king-1",
                "hotkey": "hk_king",
                "previous": None,
                "kind": we.FIRST,
            },
        )

        seen = twp.preview(issuer, state)
        assert seen["targets"]["treasury"] == []
        # Residual = Q12 - 333_333_333_333 (King) - 100_000_000_000 (Bonus) = 566_666_666_667 -> UID 0 Burn!
        assert seen["targets"]["burn"] == 566_666_666_667

        ref = issuer.issue(state)
        result = asyncio.run(publisher.publish(ref))
        assert result["state"] == "ROW_VERIFIED"
        assert result["document"]["plan"]["q12"] == [
            [0, 566_666_666_667],
            [2, 333_333_333_333],
            [3, 100_000_000_000],
        ]
        top = 566_666_666_667
        assert result["document"]["plan"]["integers"] == [
            [0, U16],
            [2, round(Fraction(333_333_333_333 * U16, top))],
            [3, round(Fraction(100_000_000_000 * U16, top))],
        ]
    finally:
        hold_ledger.close()


def test_waterfall_stake_drift_between_issue_and_publish_refuses_before_signing(tmp_path):
    """If a loyal miner dumps their stake after `issue()` before `publish()` signs,
    `resolve()` detects the changed Hold Bonus targets and refuses without signing."""
    ctx = _testnet_ctx()
    state = _waterfall_snapshot(ctx, block=1080, timestamp_ms=10 * DAY_MS)
    hold_ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        hold_ledger.record_crown_earnings(2, {"ck_loyal": (30_000 * RAO, "hk_loyal")})
        hold_ledger.sample_epoch_stakes(2, {"ck_loyal": 30_000 * RAO})

        live_stake = {"ck_loyal": 30_000 * RAO}

        def observer(_snap: MetagraphSnapshot, _epoch: int) -> WaterfallEpochObservation:
            return WaterfallEpochObservation(
                epoch_miner_emission_rao=100 * RAO,
                treasury_current_stake_rao=10_000 * RAO,
                staked_by_coldkey=dict(live_stake),
                owner_coldkey="ck_owner",
                owner_hotkeys=("hk_burn_owner",),
            )

        _policy, issuer, backend, publisher = _compose_waterfall_publisher(
            tmp_path,
            state=state,
            hold_ledger=hold_ledger,
            observer=observer,
            source=lambda: {
                "model_id": "m-king-1",
                "hotkey": "hk_king",
                "previous": None,
                "kind": we.FIRST,
            },
        )

        ref = issuer.issue(state)
        # Miner sells 100% of stake before publish() observes fresh state
        live_stake["ck_loyal"] = 0
        with pytest.raises(
            twp.WinnerPublicationRefused, match="TARGETS_CHANGED_REISSUE_NEXT_EPOCH"
        ):
            asyncio.run(publisher.publish(ref))
        assert backend.signed == backend.executions == 0
    finally:
        hold_ledger.close()


def test_waterfall_without_observer_or_active_winners_burns_100_percent_to_uid0(tmp_path):
    """With `waterfall_observer=None` and no winners, Treasury & Hold Bonus fail closed to 0
    and `no_winner` is True with 100% Q12 burned to UID 0."""
    ctx = _testnet_ctx()
    state = _waterfall_snapshot(ctx, block=1080, timestamp_ms=10 * DAY_MS)
    _policy, issuer, backend, publisher = _compose_waterfall_publisher(
        tmp_path,
        state=state,
        hold_ledger=None,
        observer=None,
        source=None,
    )
    ref = issuer.issue(state)
    resolved = issuer.resolve(ref, state)
    assert resolved["intent"]["route"] == WATERFALL_ROUTE
    assert resolved["intent"]["no_winner"] is True
    assert resolved["intent"]["targets"]["burn"] == Q12
    result = asyncio.run(publisher.publish(ref))
    assert result["state"] == "ROW_VERIFIED"
    assert result["document"]["plan"]["q12"] == [[0, Q12]]
    assert result["document"]["plan"]["integers"] == [[0, U16]]


def test_publisher_wires_bonus_credits_non_compounding_and_anti_dump_end_to_end(tmp_path):
    """End-to-end verification through `preview` -> `issue` -> `publish` that:
    1) Invalid `bonus_credits_by_coldkey` fails closed with `INVALID_BONUS_CREDIT_OBSERVATION`.
    2) Epoch 3: Miner with `C = 1,000 α` and pending `H = 500 α` holding `B = 1,500 α` receives
       exact non-compounding +50% window rate on `1,000 α` (preview matches issue without mutating SQLite).
    3) Epoch 4: Miner dumps the `500 α` bonus (`B = 1,000 α` while `C + H = 1,500 α`) ->
       `worst_sold == 1/3`, slashing both rate (to 1/3) and eligible principal (to 2/3 of 1,000 α)."""
    with pytest.raises(RewardFailure, match="INVALID_BONUS_CREDIT_OBSERVATION"):
        WaterfallEpochObservation(bonus_credits_by_coldkey=["not-a-dict"])  # type: ignore[arg-type]

    ctx = _testnet_ctx()
    state_e3 = _waterfall_snapshot(ctx, block=1080, timestamp_ms=10 * DAY_MS)
    hold_ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        hold_ledger.record_crown_earnings(2, {"ck_loyal": (1_000 * RAO, "hk_loyal")})
        hold_ledger.sample_epoch_stakes(2, {"ck_loyal": 1_000 * RAO})

        current_stake = {"ck_loyal": 1_500 * RAO}
        current_bonus_credits: dict[str, tuple[int, str]] | None = {
            "ck_loyal": (500 * RAO, "hk_loyal")
        }

        def observer(_snap: MetagraphSnapshot, epoch: int) -> WaterfallEpochObservation:
            return WaterfallEpochObservation(
                epoch_miner_emission_rao=10 * RAO,
                treasury_current_stake_rao=10_000 * RAO,
                staked_by_coldkey=dict(current_stake),
                bonus_credits_by_coldkey=(
                    dict(current_bonus_credits) if current_bonus_credits is not None else None
                ),
                owner_coldkey="ck_owner",
                owner_hotkeys=("hk_burn_owner",),
            )

        _policy, issuer, backend, publisher = _compose_waterfall_publisher(
            tmp_path,
            state=state_e3,
            hold_ledger=hold_ledger,
            observer=observer,
            source=lambda: {
                "model_id": "m-king-1",
                "hotkey": "hk_king",
                "previous": None,
                "kind": we.FIRST,
            },
            wf_overrides={
                "hold_window_epochs": 600,
                "hold_cap_q12": 400_000_000_000,
                "window_bonus_rate_bps": 5000,
                "zero_bonus_sold_bps": 5000,
            },
        )

        # Epoch 3 preview: writes nothing to `hold_epoch_bonus_credits_v1` or `hold_epoch_samples_v1`
        preview_e3 = twp.preview(issuer, state_e3)
        assert hold_ledger._conn.execute(
            "SELECT COUNT(*) FROM hold_epoch_bonus_credits_v1"
        ).fetchone() == (0,)
        # Exact non-compounding +50% rate on C = 1,000 α: ((1000 * 5000 / 6_000_000) / 10) * Q12 = 83_333_333_333
        assert preview_e3["targets"]["hold_bonus"] == [
            [{"hotkey": "hk_loyal", "coldkey": "ck_loyal", "registered_at": 4}, 83_333_333_333]
        ]

        ref_e3 = issuer.issue(state_e3)
        assert hold_ledger.window_status("ck_loyal", 3, 600) == (1_000 * RAO, Fraction(0))
        assert twp.preview(issuer, state_e3)["targets"] == preview_e3["targets"]
        res_e3 = asyncio.run(publisher.publish(ref_e3))
        assert res_e3["state"] == "ROW_VERIFIED"

        # Epoch 4 (block 1440): miner dumps all 500 α Hold Bonus (`B = 1,000 α` < `C + H = 1,500 α`)
        current_bonus_credits = None
        current_stake["ck_loyal"] = 1_000 * RAO
        state_e4 = _waterfall_snapshot(ctx, block=1440, timestamp_ms=10 * DAY_MS + 360 * 12_000)
        backend.state = state_e4
        backend.tx_hash = "0x" + "c" * 64

        preview_e4 = twp.preview(issuer, state_e4)
        # Rate slashed to 1/3 and eligible_held = 666_666_666_666 rao:
        # target_alpha_rao = 666_666_666_666 * (5000 / 6_000_000) * (1/3)
        expected_dumped_q12 = int(
            (Fraction(666_666_666_666) * Fraction(5000, 10_000 * 600) * Fraction(1, 3) * Q12)
            // (10 * RAO)
        )
        assert expected_dumped_q12 == 18_518_518_518  # 2/9 of 83_333_333_333!
        assert preview_e4["targets"]["hold_bonus"] == [
            [{"hotkey": "hk_loyal", "coldkey": "ck_loyal", "registered_at": 4}, expected_dumped_q12]
        ]

        ref_e4 = issuer.issue(state_e4)
        assert hold_ledger.window_status("ck_loyal", 4, 600) == (
            666_666_666_666,
            Fraction(1, 3),
        )
        res_e4 = asyncio.run(publisher.publish(ref_e4))
        assert res_e4["state"] == "ROW_VERIFIED"
    finally:
        hold_ledger.close()


# ---------------------------------------------------------------------------
# 4. Registered Mainnet Policy `mainnet-winner-v5` (Stage 5B Hold Bonus Launch)
# ---------------------------------------------------------------------------

MAINNET_V5_DIGEST = (
    "sha256:691b882f5afa22cb30fc9cf439555e481793c95d4310084284f29de5701a9724"
)
CARBON_EXCLUDED_COLDKEY = "5D5RwyMPFaKLwChEcfb5yPA6VENHxJBagcHkP5aztfg8Ynj9"
MOTOR_PACK = "sha256:ee2348b1738fb13984601473b5624bfefc2f65d8c7c7e91471c2d4c419a5742c"


def test_mainnet_winner_v5_policy_registration_and_field_inheritance():
    v4 = wd.load_policy("mainnet-winner-v4")
    v5 = wd.load_policy("mainnet-winner-v5")
    registry = json.loads((wd.POLICY_DIR / "registry.json").read_text())
    assert registry["current"] == "testnet-winner-v1"
    assert registry["versions"]["mainnet-winner-v5"] == MAINNET_V5_DIGEST == v5.digest

    raw_bytes = (wd.POLICY_DIR / "mainnet-winner-v5.json").read_bytes()
    doc = json.loads(raw_bytes)
    assert (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8") == raw_bytes

    # Cutover runbook pins the exact registered digest
    cutover_doc = (wd.POLICY_DIR.parent / "MAINNET-V5-CUTOVER.md").read_text(encoding="utf-8")
    assert MAINNET_V5_DIGEST in cutover_doc
    assert v4.digest in cutover_doc

    # Inherits every v4 field unchanged
    assert (
        v5.authority,
        v5.network,
        v5.netuid,
        v5.burn_uid,
        v5.cadence_blocks,
        v5.challenges,
        v5.baselines,
        v5.qualified_sealed,
        v5.self_improvement_factor,
        v5.share,
    ) == (
        v4.authority,
        v4.network,
        v4.netuid,
        v4.burn_uid,
        v4.cadence_blocks,
        v4.challenges,
        v4.baselines,
        v4.qualified_sealed,
        v4.self_improvement_factor,
        Q12,
    )

    # Exact Stage 5B WaterfallConfig
    assert v5.waterfall == WaterfallConfig(
        hold_window_epochs=600,
        hold_cap_q12=400_000_000_000,
        window_bonus_rate_bps=5000,
        zero_bonus_sold_bps=5000,
        treasury_sinks=(),
        treasury_stake_cap_rao=0,
        excluded_coldkeys=frozenset({CARBON_EXCLUDED_COLDKEY}),
        enforce_king_u16_floor=True,
    )


def test_mainnet_winner_v5_simulation_across_day1_decay_bonus_cap_exclusion_and_uid0_burn(
    tmp_path,
):
    """End-to-end simulation of registered `mainnet-winner-v5` on Finney SN116:
    - Day 1 (full 24h window): Active King receives 100% (`Q12`), 0 burn, `u16 == 65535`.
    - Day 2 (50% decay): Loyal past winner receives +50% / 600-epoch Hold Bonus; Carbon's
      excluded coldkey `5D5RwyMPFaKLwChEcfb5yPA6VENHxJBagcHkP5aztfg8Ynj9` receives 0 Hold Bonus;
      post-bonus remainder routes 100% to `UID 0` burn while `treasury_sinks == ()`.
    - Day 2 high-demand cap: Rung 2 Hold Bonus clamps at `40%` (`400_000_000_000` Q12) and
      remaining `10%` burns to `UID 0`.
    - Deep decay (25 halvings): Active King gets `MIN_POSITIVE_U16_Q12` (`7,629,511`) and compiles
      to `u16 >= 1` alongside `40%` Hold Bonus and `~60%` `UID 0` burn."""
    from carbon.chain import networks
    from carbon.rewards.waterfall import MIN_POSITIVE_U16_Q12

    v5 = wd.load_policy("mainnet-winner-v5")
    finney_row = networks.NETWORKS["finney"]
    ctx = ChainContext(
        "finney",
        "wss://entrypoint-finney.opentensor.ai:443",
        finney_row.chain_id,
        finney_row.genesis_hash,
        116,
    )
    t0 = 20 * DAY_MS

    def _sn116_snap(block: int, now_ms: int) -> MetagraphSnapshot:
        return MetagraphSnapshot(
            context=ctx,
            finalized_block=block,
            block_hash="0x" + f"{block:064x}",
            timestamp_ms=now_ms,
            participants=(
                Participant(0, "hk_burn_owner", CARBON_EXCLUDED_COLDKEY, 1),
                Participant(1, "hk_sn116_validator", "ck_validator", 2),
                Participant(2, "hk_motor_king", "ck_motor_king", 10),
                Participant(3, "hk_loyal_past", "ck_loyal_past", 11),
                Participant(4, "hk_carbon_miner", CARBON_EXCLUDED_COLDKEY, 12),
            ),
        )

    def _sn116_caps(state: MetagraphSnapshot) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            snapshot_id=state.snapshot_id,
            spec_version=SPEC,
            mechanism_count=1,
            maximum_mechanisms=8,
            burn_mode="Burn",
            owner_coldkey=CARBON_EXCLUDED_COLDKEY,
            owner_hotkey="hk_burn_owner",
            owner_hotkeys=("hk_burn_owner",),
            min_weights=1,
            max_weight=U16,
            version_key=1,
            rate_limit=0,
            last_update=0,
            commit_reveal=False,
            validator_permit=True,
            sufficient_stake=True,
        )

    class _MainnetBackend(_WaterfallBackend):
        async def observe(self):
            return self.state, _sn116_caps(self.state)

    auth = twp.StandingAuthorization(
        authority_record_digest=RECORD,
        policy_digest=v5.digest,
        context=ctx,
        publisher_hotkey="hk_sn116_validator",
        expected_runtime_spec=SPEC,
        valid_from_block=1_000,
        valid_through_block=500_000,
        authority=wd.MAINNET_AUTHORITY,
    )
    receipts = ReceiptJournal(tmp_path / "sn116_pub.sqlite3", ctx)
    winner_ledger = we.WinnerLedger(tmp_path / "sn116_winners.jsonl")
    hold_ledger = HoldBonusLedger(tmp_path / "sn116_hold.sqlite3")

    try:
        # Both loyal past winner (1,000 α) and Carbon excluded coldkey (100,000 α) hold 100% of past crowns
        hold_ledger.record_crown_earnings(
            2,
            {
                "ck_loyal_past": (1_000 * RAO, "hk_loyal_past"),
                CARBON_EXCLUDED_COLDKEY: (100_000 * RAO, "hk_carbon_miner"),
            },
        )
        hold_ledger.sample_epoch_stakes(
            2,
            {"ck_loyal_past": 1_000 * RAO, CARBON_EXCLUDED_COLDKEY: 100_000 * RAO},
        )

        emission_state = {"rao": 10 * RAO}

        def observer(_snap: MetagraphSnapshot, _epoch: int) -> WaterfallEpochObservation:
            return WaterfallEpochObservation(
                epoch_miner_emission_rao=emission_state["rao"],
                treasury_current_stake_rao=10_000 * RAO,
                staked_by_coldkey={
                    "ck_loyal_past": 1_000 * RAO,
                    CARBON_EXCLUDED_COLDKEY: 100_000 * RAO,
                },
                owner_coldkey=CARBON_EXCLUDED_COLDKEY,
                owner_hotkeys=("hk_burn_owner",),
            )

        def motor_source():
            return {
                "model_id": "motor-18-crown-1",
                "hotkey": "hk_motor_king",
                "previous": None,
                "previous_hotkey": None,
                "incumbent_reason": we.SEALED_TESTNET_REASON,
                "evaluation_pack_digests": [MOTOR_PACK],
                "kind": we.FIRST,
            }

        issuer = twp.TestnetWinnerIntentIssuer(
            receipts,
            auth,
            v5,
            winner_ledger,
            {"electric-motor-magnetics": motor_source},
            hold_ledger=hold_ledger,
            waterfall_observer=observer,
        )

        # --- Phase 1: Day 1 (within 24h) -> King gets 100% Q12 ---
        snap_d1 = _sn116_snap(block=1080, now_ms=t0)
        backend = _MainnetBackend(snap_d1, publisher="hk_sn116_validator")
        publisher = twp.TestnetWinnerPublisher(issuer, backend)
        assert publisher.ALLOW_OWNER_COLDKEY_WINNER is False

        ref_d1 = issuer.issue(snap_d1)
        res_d1 = asyncio.run(publisher.publish(ref_d1))
        assert res_d1["state"] == "ROW_VERIFIED"
        assert res_d1["document"]["plan"]["q12"] == [[2, Q12]]
        assert res_d1["document"]["plan"]["integers"] == [[2, U16]]

        # --- Phase 2: Day 2 (24h elapsed -> King 50%, Loyal Bonus 83_333_333_333, Carbon excluded, rest UID 0 burn) ---
        snap_d2 = _sn116_snap(block=8280, now_ms=t0 + DAY_MS)
        backend.state = snap_d2
        backend.tx_hash = "0x" + "1" * 64

        preview_d2 = twp.preview(issuer, snap_d2)
        assert preview_d2["targets"]["winners"] == [
            [{"hotkey": "hk_motor_king", "coldkey": "ck_motor_king", "registered_at": 10}, 500_000_000_000]
        ]
        assert preview_d2["targets"]["hold_bonus"] == [
            [{"hotkey": "hk_loyal_past", "coldkey": "ck_loyal_past", "registered_at": 11}, 83_333_333_333]
        ]
        assert preview_d2["targets"]["treasury"] == []
        assert preview_d2["targets"]["burn"] == 416_666_666_667

        ref_d2 = issuer.issue(snap_d2)
        res_d2 = asyncio.run(publisher.publish(ref_d2))
        assert res_d2["state"] == "ROW_VERIFIED"
        assert res_d2["document"]["plan"]["q12"] == [
            [0, 416_666_666_667],
            [2, 500_000_000_000],
            [3, 83_333_333_333],
        ]

        # --- Phase 3: Day 2 High-Demand Cap (`hold_cap_q12 == 400_000_000_000` == 40%) ---
        emission_state["rao"] = 1 * RAO  # Desired bonus ~833_333_333_333 > 40% cap
        snap_d2_cap = _sn116_snap(block=8640, now_ms=t0 + DAY_MS + 360 * 12_000)
        backend.state = snap_d2_cap
        backend.tx_hash = "0x" + "2" * 64

        ref_cap = issuer.issue(snap_d2_cap)
        res_cap = asyncio.run(publisher.publish(ref_cap))
        assert res_cap["state"] == "ROW_VERIFIED"
        assert res_cap["document"]["plan"]["q12"] == [
            [0, 100_000_000_000],
            [2, 500_000_000_000],
            [3, 400_000_000_000],
        ]

        # --- Phase 4: Deep Decay (25 halvings -> King floored at MIN_POSITIVE_U16_Q12 -> u16 >= 1) ---
        snap_deep = _sn116_snap(block=200_160, now_ms=t0 + 25 * DAY_MS)
        backend.state = snap_deep
        backend.tx_hash = "0x" + "3" * 64

        ref_deep = issuer.issue(snap_deep)
        res_deep = asyncio.run(publisher.publish(ref_deep))
        assert res_deep["state"] == "ROW_VERIFIED"
        expected_deep_burn = Q12 - MIN_POSITIVE_U16_Q12 - 400_000_000_000
        assert res_deep["document"]["plan"]["q12"] == [
            [0, expected_deep_burn],
            [2, MIN_POSITIVE_U16_Q12],
            [3, 400_000_000_000],
        ]
        int_map = dict(res_deep["document"]["plan"]["integers"])
        assert int_map[2] >= 1  # Active King stays >= 1 in u16 weights!
        assert int_map[0] == U16
    finally:
        hold_ledger.close()
