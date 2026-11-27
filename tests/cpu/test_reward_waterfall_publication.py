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
from carbon.chain.publication import U16, RuntimeCapabilities
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


def _pin_policy_copy(
    tmp_path: Path, base_version: str = "testnet-winner-v1", **doc_updates
) -> Path:
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
        {
            k: v
            for k, v in _valid_waterfall_dict().items()
            if k != "enforce_king_u16_floor"
        },
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
        _valid_waterfall_dict(
            treasury_sinks=[{"hotkey": "hk_sink_0", "coldkey": "ck_vault"}]
        ),
        _valid_waterfall_dict(
            treasury_sinks=[
                {
                    "hotkey": "hk_sink_0",
                    "coldkey": "ck_vault",
                    "registered_at": 10,
                    "extra": 1,
                }
            ]
        ),
        _valid_waterfall_dict(
            treasury_sinks=[
                {"hotkey": "hk_sink_0", "coldkey": "ck_vault", "registered_at": True}
            ]
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
    king_promoted_at_ms: int | None = None,
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
    if source is not None and king_promoted_at_ms is not None:
        coldkeys = {p.hotkey: p.coldkey for p in state.participants}
        winner_ledger.observe(
            policy, challenge, source(), coldkeys, king_promoted_at_ms
        )
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
    """4-rung epoch (block 1080 -> epoch 3, 3-challenge testnet policy under F2 Option A):
    - Challenge 0 has Active King `hk_king` 24h into decay (`166_666_666_666` Q12);
      its decayed `166_666_666_667` Q12 is the ONLY pool funding Rung 2 & Rung 3!
    - Challenges 1 & 2 have no King: their `2 * 333_333_333_333` + `Q12 % 3` (`1`) go
      directly to Rung 4 (`UID 0` burn).
    - Rung 2 (Loyal Past King `ck_loyal` Hold Bonus): `100_000_000_000` Q12
    - Rung 3 (2 Pinned Treasury Sinks `hk_sink_0`, `hk_sink_1` below cap):
      `66_666_666_667 // 2 = 33_333_333_333` Q12 each
    - Rung 4 (UID 0 Burn): `666_666_666_668` Q12 -> exact `Q12` conservation!"""
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

        _policy, issuer, backend, publisher = _compose_waterfall_publisher(
            tmp_path,
            state=state,
            hold_ledger=hold_ledger,
            observer=observer,
            king_promoted_at_ms=9 * DAY_MS,
            source=lambda: {
                "model_id": "m-king-1",
                "hotkey": "hk_king",
                "previous": None,
                "kind": we.FIRST,
            },
        )
        before_preview_winner_bytes = issuer.ledger.path.read_bytes()

        # 1) Non-mutating preview: computes exact 4-rung targets, writes NOTHING to SQLite or WinnerLedger!
        seen = twp.preview(issuer, state)
        assert seen["signed"] is False
        assert _ledger_snapshot() == before_preview_sql
        assert issuer.ledger.path.read_bytes() == before_preview_winner_bytes
        with issuer.receipts.transaction() as db:
            assert db.execute(
                "SELECT COUNT(*) FROM testnet_winner_intent_v1"
            ).fetchone() == (0,)

        expected_targets = {
            "challenges": seen["targets"]["challenges"],
            "winners": [
                [
                    {"hotkey": "hk_king", "coldkey": "ck_king", "registered_at": 3},
                    166_666_666_666,
                ]
            ],
            "hold_bonus": [
                [
                    {"hotkey": "hk_loyal", "coldkey": "ck_loyal", "registered_at": 4},
                    100_000_000_000,
                ]
            ],
            "treasury": [
                [
                    {"hotkey": "hk_sink_0", "coldkey": "ck_vault", "registered_at": 10},
                    33_333_333_333,
                ],
                [
                    {"hotkey": "hk_sink_1", "coldkey": "ck_vault", "registered_at": 11},
                    33_333_333_333,
                ],
            ],
            "burn": 666_666_666_668,
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
        assert hold_ledger.window_status("ck_loyal", 3, 600) == (
            30_000 * RAO,
            Fraction(0),
        )
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
            [0, 666_666_666_668],
            [2, 166_666_666_666],
            [3, 100_000_000_000],
            [4, 33_333_333_333],
            [5, 33_333_333_333],
        ]
        top = 666_666_666_668
        expected_integers = [
            [0, U16],
            [2, round(Fraction(166_666_666_666 * U16, top))],
            [3, round(Fraction(100_000_000_000 * U16, top))],
            [4, round(Fraction(33_333_333_333 * U16, top))],
            [5, round(Fraction(33_333_333_333 * U16, top))],
        ]
        assert plan_doc["integers"] == expected_integers

        # Publishing the same ref again returns the journaled ROW_VERIFIED result without re-signing
        assert asyncio.run(publisher.publish(ref)) == result
        assert backend.executions == backend.signed == 1
    finally:
        hold_ledger.close()


# ---------------------------------------------------------------------------
# 3. Fail-Closed Treasury Cap & Missing Observation -> Refusal / UID 0 Burn
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "observed_treasury_stake",
    [
        None,  # Missing treasury stake observation -> Treasury fails closed to 0
        100_000 * RAO,  # Exactly at cap -> gated off
        150_000 * RAO,  # Above cap -> gated off
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

        def observer(
            _snap: MetagraphSnapshot, _epoch: int
        ) -> WaterfallEpochObservation:
            return WaterfallEpochObservation(
                epoch_miner_emission_rao=100 * RAO,
                treasury_current_stake_rao=observed_treasury_stake,
                staked_by_coldkey={"ck_loyal": 30_000 * RAO},
                owner_coldkey="ck_owner",
                owner_hotkeys=("hk_burn_owner",),
            )

        _policy, issuer, _backend, publisher = _compose_waterfall_publisher(
            tmp_path,
            state=state,
            hold_ledger=hold_ledger,
            observer=observer,
            king_promoted_at_ms=9 * DAY_MS,
            source=lambda: {
                "model_id": "m-king-1",
                "hotkey": "hk_king",
                "previous": None,
                "kind": we.FIRST,
            },
        )

        seen = twp.preview(issuer, state)
        assert seen["targets"]["treasury"] == []
        # Burn = Q12 - 166_666_666_666 (King) - 100_000_000_000 (Bonus) = 733_333_333_334 -> UID 0!
        assert seen["targets"]["burn"] == 733_333_333_334

        ref = issuer.issue(state)
        result = asyncio.run(publisher.publish(ref))
        assert result["state"] == "ROW_VERIFIED"
        assert result["document"]["plan"]["q12"] == [
            [0, 733_333_333_334],
            [2, 166_666_666_666],
            [3, 100_000_000_000],
        ]
        top = 733_333_333_334
        assert result["document"]["plan"]["integers"] == [
            [0, U16],
            [2, round(Fraction(166_666_666_666 * U16, top))],
            [3, round(Fraction(100_000_000_000 * U16, top))],
        ]
    finally:
        hold_ledger.close()


def test_waterfall_stake_drift_between_issue_and_publish_refuses_before_signing(
    tmp_path,
):
    """If a loyal miner dumps their stake after `issue()` before `publish()` signs,
    `resolve()` detects the changed Hold Bonus targets and refuses without signing."""
    ctx = _testnet_ctx()
    state = _waterfall_snapshot(ctx, block=1080, timestamp_ms=10 * DAY_MS)
    hold_ledger = HoldBonusLedger(tmp_path / "hold.sqlite3")
    try:
        hold_ledger.record_crown_earnings(2, {"ck_loyal": (30_000 * RAO, "hk_loyal")})
        hold_ledger.sample_epoch_stakes(2, {"ck_loyal": 30_000 * RAO})

        live_stake = {"ck_loyal": 30_000 * RAO}

        def observer(
            _snap: MetagraphSnapshot, _epoch: int
        ) -> WaterfallEpochObservation:
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
            king_promoted_at_ms=9 * DAY_MS,
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


def test_waterfall_fail_closed_missing_observer_fields_and_empty_winners_100pct_burn(
    tmp_path,
):
    """F5 + F2:
    1) Missing `waterfall_observer`, `staked_by_coldkey`, `epoch_miner_emission_rao`, or
       (on `finney`) `owner_coldkey` refuses publication (`WinnerPublicationRefused`).
    2) With a valid observer and no active Challenge Kings (`source=None`), even when loyal
       past winners hold earned Alpha, `decayed_from_active_kings_q12 == 0` so 100% `Q12`
       burns directly to `UID 0` (`no_winner is True`)."""
    ctx = _testnet_ctx()
    state = _waterfall_snapshot(ctx, block=1080, timestamp_ms=10 * DAY_MS)

    # 1a) observer=None -> WATERFALL_OBSERVER_REQUIRED
    _p0, issuer_no_obs, _b0, _pub0 = _compose_waterfall_publisher(
        tmp_path / "no_obs",
        state=state,
        hold_ledger=None,
        observer=None,
        source=None,
    )
    with pytest.raises(
        twp.WinnerPublicationRefused, match="WATERFALL_OBSERVER_REQUIRED"
    ):
        issuer_no_obs.issue(state)

    # 1b) staked_by_coldkey=None -> STAKE_OBSERVATION_REQUIRED
    _p1, issuer_no_stake, _b1, _pub1 = _compose_waterfall_publisher(
        tmp_path / "no_stake",
        state=state,
        hold_ledger=None,
        observer=lambda _s, _e: WaterfallEpochObservation(
            epoch_miner_emission_rao=10 * RAO,
            staked_by_coldkey=None,
            owner_coldkey="ck_owner",
        ),
        source=None,
    )
    with pytest.raises(
        twp.WinnerPublicationRefused, match="STAKE_OBSERVATION_REQUIRED"
    ):
        issuer_no_stake.issue(state)

    # 1c) epoch_miner_emission_rao=None -> EMISSION_OBSERVATION_REQUIRED
    _p2, issuer_no_em, _b2, _pub2 = _compose_waterfall_publisher(
        tmp_path / "no_em",
        state=state,
        hold_ledger=None,
        observer=lambda _s, _e: WaterfallEpochObservation(
            epoch_miner_emission_rao=None,
            staked_by_coldkey={},
            owner_coldkey="ck_owner",
        ),
        source=None,
    )
    with pytest.raises(
        twp.WinnerPublicationRefused, match="EMISSION_OBSERVATION_REQUIRED"
    ):
        issuer_no_em.issue(state)

    # 2) Valid observer + no active winners -> 100% burn to UID 0 (even with loyal past holder!)
    hold_ledger = HoldBonusLedger(tmp_path / "empty_slots_hold.sqlite3")
    try:
        hold_ledger.record_crown_earnings(2, {"ck_loyal": (30_000 * RAO, "hk_loyal")})
        hold_ledger.sample_epoch_stakes(2, {"ck_loyal": 30_000 * RAO})
        _policy, issuer, _backend, publisher = _compose_waterfall_publisher(
            tmp_path / "valid_empty",
            state=state,
            hold_ledger=hold_ledger,
            observer=lambda _s, _e: WaterfallEpochObservation(
                epoch_miner_emission_rao=100 * RAO,
                treasury_current_stake_rao=0,
                staked_by_coldkey={"ck_loyal": 30_000 * RAO},
                owner_coldkey="ck_owner",
                owner_hotkeys=("hk_burn_owner",),
            ),
            source=None,
        )
        ref = issuer.issue(state)
        resolved = issuer.resolve(ref, state)
        assert resolved["intent"]["route"] == WATERFALL_ROUTE
        assert resolved["intent"]["no_winner"] is True
        assert resolved["intent"]["targets"]["hold_bonus"] == []
        assert resolved["intent"]["targets"]["treasury"] == []
        assert resolved["intent"]["targets"]["burn"] == Q12
        result = asyncio.run(publisher.publish(ref))
        assert result["state"] == "ROW_VERIFIED"
        assert result["document"]["plan"]["q12"] == [[0, Q12]]
        assert result["document"]["plan"]["integers"] == [[0, U16]]
    finally:
        hold_ledger.close()


def test_publisher_wires_bonus_credits_non_compounding_and_anti_dump_end_to_end(
    tmp_path,
):
    """End-to-end verification through `preview` -> `issue` -> `publish` that:
    1) Invalid `bonus_credits_by_coldkey` fails closed with `INVALID_BONUS_CREDIT_OBSERVATION`.
    2) Epoch 3: Miner with `C = 1,000 α` and pending `H = 500 α` holding `B = 1,500 α` receives
       exact non-compounding +50% window rate on `1,000 α` (preview matches issue without mutating SQLite).
    3) Epoch 4: Miner dumps the `500 α` bonus (`B = 1,000 α` while `C + H = 1,500 α`) ->
       `worst_sold == 1/3`, slashing both rate (to 1/3) and eligible principal (to 2/3 of 1,000 α).
    """
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
                    dict(current_bonus_credits)
                    if current_bonus_credits is not None
                    else None
                ),
                owner_coldkey="ck_owner",
                owner_hotkeys=("hk_burn_owner",),
            )

        _policy, issuer, backend, publisher = _compose_waterfall_publisher(
            tmp_path,
            state=state_e3,
            hold_ledger=hold_ledger,
            observer=observer,
            king_promoted_at_ms=9 * DAY_MS,
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
            [
                {"hotkey": "hk_loyal", "coldkey": "ck_loyal", "registered_at": 4},
                83_333_333_333,
            ]
        ]

        ref_e3 = issuer.issue(state_e3)
        assert hold_ledger.window_status("ck_loyal", 3, 600) == (
            1_000 * RAO,
            Fraction(0),
        )
        assert twp.preview(issuer, state_e3)["targets"] == preview_e3["targets"]
        res_e3 = asyncio.run(publisher.publish(ref_e3))
        assert res_e3["state"] == "ROW_VERIFIED"

        # Epoch 4 (block 1440): miner dumps all 500 α Hold Bonus (`B = 1,000 α` < `C + H = 1,500 α`)
        current_bonus_credits = None
        current_stake["ck_loyal"] = 1_000 * RAO
        state_e4 = _waterfall_snapshot(
            ctx, block=1440, timestamp_ms=10 * DAY_MS + 360 * 12_000
        )
        backend.state = state_e4
        backend.tx_hash = "0x" + "c" * 64

        preview_e4 = twp.preview(issuer, state_e4)
        # Rate slashed to 1/3 and eligible_held = 666_666_666_666 rao:
        # target_alpha_rao = 666_666_666_666 * (5000 / 6_000_000) * (1/3)
        expected_dumped_q12 = int(
            (
                Fraction(666_666_666_666)
                * Fraction(5000, 10_000 * 600)
                * Fraction(1, 3)
                * Q12
            )
            // (10 * RAO)
        )
        assert expected_dumped_q12 == 18_518_518_518  # 2/9 of 83_333_333_333!
        assert preview_e4["targets"]["hold_bonus"] == [
            [
                {"hotkey": "hk_loyal", "coldkey": "ck_loyal", "registered_at": 4},
                expected_dumped_q12,
            ]
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
    "sha256:6e0c72a46f4bc8f7d3dcee359ba053e4ad469345d4c7da30a442d19dc0892836"
)
CARBON_EXCLUDED_COLDKEY = "5D5RwyMPFaKLwChEcfb5yPA6VENHxJBagcHkP5aztfg8Ynj9"
VAULT_EXCLUDED_COLDKEY = "5HVHGgWc1RvFFCkS678oB4DBjR8ZumAiAFsVXDf3aJCNbY8T"
MOTOR_PACK = "sha256:ee2348b1738fb13984601473b5624bfefc2f65d8c7c7e91471c2d4c419a5742c"


def test_mainnet_winner_v5_policy_registration_and_field_inheritance():
    v4 = wd.load_policy("mainnet-winner-v4")
    v5 = wd.load_policy("mainnet-winner-v5")
    registry = json.loads((wd.POLICY_DIR / "registry.json").read_text())
    assert registry["current"] == "testnet-winner-v1"
    assert registry["versions"]["mainnet-winner-v5"] == MAINNET_V5_DIGEST == v5.digest

    raw_bytes = (wd.POLICY_DIR / "mainnet-winner-v5.json").read_bytes()
    doc = json.loads(raw_bytes)
    assert (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    ) == raw_bytes

    # Cutover runbook pins the exact registered digest and both excluded coldkeys
    cutover_doc = (wd.POLICY_DIR.parent / "MAINNET-V5-CUTOVER.md").read_text(
        encoding="utf-8"
    )
    assert MAINNET_V5_DIGEST in cutover_doc
    assert v4.digest in cutover_doc
    assert CARBON_EXCLUDED_COLDKEY in cutover_doc
    assert VAULT_EXCLUDED_COLDKEY in cutover_doc

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

    # Exact Stage 5B WaterfallConfig (F3 enforce_king_u16_floor=False, F5 both excluded coldkeys)
    assert v5.waterfall == WaterfallConfig(
        hold_window_epochs=600,
        hold_cap_q12=400_000_000_000,
        window_bonus_rate_bps=5000,
        zero_bonus_sold_bps=5000,
        treasury_sinks=(),
        treasury_stake_cap_rao=0,
        excluded_coldkeys=frozenset({CARBON_EXCLUDED_COLDKEY, VAULT_EXCLUDED_COLDKEY}),
        enforce_king_u16_floor=False,
    )


def test_mainnet_winner_v5_simulation_across_day1_decay_bonus_cap_exclusion_and_uid0_burn(
    tmp_path,
):
    """End-to-end simulation of registered `mainnet-winner-v5` on Finney SN116:
    - Day 1 (full 24h window): Active King receives 100% (`Q12`), 0 burn, `u16 == 65535`.
    - Day 2 (50% decay): Loyal past winner receives +50% / 600-epoch Hold Bonus; BOTH
      excluded coldkeys (`5D5Rwy...` and `5HVHGg...`) receive 0 Hold Bonus; post-bonus
      remainder routes 100% to `UID 0` burn while `treasury_sinks == ()`.
    - Day 2 high-demand cap: Rung 2 Hold Bonus clamps at `40%` (`400_000_000_000` Q12) and
      remaining `10%` burns to `UID 0`.
    - Deep decay (45 halvings under F3 `enforce_king_u16_floor = False`): Unbeaten Active King
      decays naturally to `0` (`winners == []`) matching `mainnet-winner-v4`, while `100%` of
      its decayed share continues funding Rung 2 Hold Bonus (`40%`) + `UID 0` burn (`60%`).
    - Missing `owner_coldkey` on `finney` refuses with `OWNER_COLDKEY_REQUIRED`."""
    from carbon.chain import networks

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
                Participant(5, "hk_vault_miner", VAULT_EXCLUDED_COLDKEY, 13),
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
        # Loyal past winner AND both excluded coldkeys hold 100% of past crowns
        hold_ledger.record_crown_earnings(
            2,
            {
                "ck_loyal_past": (1_000 * RAO, "hk_loyal_past"),
                CARBON_EXCLUDED_COLDKEY: (100_000 * RAO, "hk_carbon_miner"),
                VAULT_EXCLUDED_COLDKEY: (100_000 * RAO, "hk_vault_miner"),
            },
        )
        hold_ledger.sample_epoch_stakes(
            2,
            {
                "ck_loyal_past": 1_000 * RAO,
                CARBON_EXCLUDED_COLDKEY: 100_000 * RAO,
                VAULT_EXCLUDED_COLDKEY: 100_000 * RAO,
            },
        )

        emission_state = {"rao": 10 * RAO, "owner_ck": CARBON_EXCLUDED_COLDKEY}

        def observer(
            _snap: MetagraphSnapshot, _epoch: int
        ) -> WaterfallEpochObservation:
            return WaterfallEpochObservation(
                epoch_miner_emission_rao=emission_state["rao"],
                treasury_current_stake_rao=10_000 * RAO,
                staked_by_coldkey={
                    "ck_loyal_past": 1_000 * RAO,
                    CARBON_EXCLUDED_COLDKEY: 100_000 * RAO,
                    VAULT_EXCLUDED_COLDKEY: 100_000 * RAO,
                },
                owner_coldkey=emission_state["owner_ck"],
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

        # Fail-closed check on finney if owner_coldkey is None
        emission_state["owner_ck"] = None  # type: ignore[assignment]
        with pytest.raises(
            twp.WinnerPublicationRefused, match="OWNER_COLDKEY_REQUIRED"
        ):
            twp.preview(issuer, _sn116_snap(block=1080, now_ms=t0))
        emission_state["owner_ck"] = CARBON_EXCLUDED_COLDKEY

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

        # --- Phase 2: Day 2 (24h elapsed -> King 50%, Loyal Bonus 83_333_333_333, both excluded coldkeys get 0, rest UID 0 burn) ---
        snap_d2 = _sn116_snap(block=8280, now_ms=t0 + DAY_MS)
        backend.state = snap_d2
        backend.tx_hash = "0x" + "1" * 64

        preview_d2 = twp.preview(issuer, snap_d2)
        assert preview_d2["targets"]["winners"] == [
            [
                {
                    "hotkey": "hk_motor_king",
                    "coldkey": "ck_motor_king",
                    "registered_at": 10,
                },
                500_000_000_000,
            ]
        ]
        assert preview_d2["targets"]["hold_bonus"] == [
            [
                {
                    "hotkey": "hk_loyal_past",
                    "coldkey": "ck_loyal_past",
                    "registered_at": 11,
                },
                83_333_333_333,
            ]
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

        # --- Phase 4: Deep Decay (45 halvings -> F3 `enforce_king_u16_floor = False` -> King decays naturally to 0!) ---
        snap_deep = _sn116_snap(block=330_120, now_ms=t0 + 45 * DAY_MS)
        backend.state = snap_deep
        backend.tx_hash = "0x" + "3" * 64

        ref_deep = issuer.issue(snap_deep)
        res_deep = asyncio.run(publisher.publish(ref_deep))
        assert res_deep["state"] == "ROW_VERIFIED"
        assert res_deep["document"]["plan"]["q12"] == [
            [0, 600_000_000_000],
            [3, 400_000_000_000],
        ]
        int_map = dict(res_deep["document"]["plan"]["integers"])
        assert 2 not in int_map  # Unbeaten King decayed naturally to 0!
        assert int_map[0] == U16
        assert int_map[3] == round(Fraction(400_000_000_000 * U16, 600_000_000_000))
    finally:
        hold_ledger.close()


# ---------------------------------------------------------------------------
# 5. CLI `_issuer` + `weights preview` / `weights run` End-to-End Persistence
# ---------------------------------------------------------------------------


def _setup_sn116_cli_fixture(tmp_path: Path):
    """Create a real `0700` state dir, `0600` operator config, `0600` standing.json,
    and a real `PoolStore` with a qualified Motor 1.8 crown on `MOTOR_PACK`."""
    from carbon.battery.pool_store import PoolStore
    from carbon.chain import networks
    from carbon.validator_setup import weights as vs_weights

    finney_row = networks.NETWORKS["finney"]
    ctx = ChainContext(
        "finney",
        "wss://entrypoint-finney.opentensor.ai:443",
        finney_row.chain_id,
        finney_row.genesis_hash,
        116,
    )
    state_dir = tmp_path / "state"
    state_dir.mkdir(mode=0o700)

    wallet_dir = tmp_path / "wallet"
    wallet_dir.mkdir(mode=0o700)

    op_cfg_path = tmp_path / "operator-weights.json"
    op_cfg_path.write_text(
        json.dumps(
            {
                "schema": vs_weights.SCHEMA,
                "context": {
                    "network": "finney",
                    "endpoint": ctx.endpoint,
                    "chain_id": finney_row.chain_id,
                    "genesis_hash": finney_row.genesis_hash,
                    "netuid": 116,
                },
                "expected_runtime_spec": SPEC,
                "publisher": {
                    "hotkey": "hk_sn116_validator",
                    "coldkey": "ck_validator",
                },
                "wallet": {
                    "name": "sn116-val",
                    "hotkey_name": "default",
                    "path": str(wallet_dir),
                },
            }
        ),
        encoding="utf-8",
    )
    op_cfg_path.chmod(0o600)

    record_file = tmp_path / "OWNER-WEIGHTS-AUTHORITY-01.md"
    record_file.write_text("owner authority record fixture", encoding="utf-8")
    standing_path = tmp_path / "standing.json"
    standing_path.write_text(
        json.dumps(
            {
                "authority": wd.MAINNET_AUTHORITY,
                "authority_record": record_file.name,
                "policy_digest": MAINNET_V5_DIGEST,
                "publisher_hotkey": "hk_sn116_validator",
                "expected_runtime_spec": SPEC,
                "valid_from_block": 1_000,
                "valid_through_block": 500_000,
            }
        ),
        encoding="utf-8",
    )
    standing_path.chmod(0o600)

    pool_path = tmp_path / "motor_pool.sqlite3"
    store = PoolStore(pool_path, clock=lambda: 100.0)
    store.admit(
        "motor-18-m1",
        request_digest="sha256:" + "1" * 64,
        hotkey="hk_motor_king",
        challenge="electric-motor-magnetics",
        strategy={},
        binding={"challenge": {"id": "electric-motor-magnetics"}},
    )
    eval_key = "sha256:" + "2" * 64
    with store.db() as db:
        db.execute(
            "INSERT INTO operations (op_id, kind, state, body) VALUES (?, 'private_evaluation.v1', 'BOUND_DEVELOPMENT_ONLY', ?)",
            (
                "op-eval-1",
                json.dumps(
                    {
                        "submission_id": "motor-18-m1",
                        "evaluation_key": eval_key,
                        "evidence": {"evaluation_pack_digest": MOTOR_PACK},
                    }
                ),
            ),
        )
    store.set_incumbent("motor-18-m1", we.SEALED_TESTNET_REASON)

    return ctx, state_dir, op_cfg_path, standing_path, pool_path


def test_cli_issuer_and_weights_execute_persist_hold_bonus_ledger_jsonl_across_epochs(
    monkeypatch, tmp_path
):
    """End-to-end CLI test through `carbon.validator_setup.weights.execute` + `twp._issuer`
    under `mainnet-winner-v5`:
    - `weights preview` before first `run` does NOT create `hold_bonus_ledger.jsonl` on disk.
    - Epoch 3 (`weights run`): publishes Day-1 King (`100%` Q12) and atomically creates
      `hold_bonus_ledger.jsonl` (`0600`) with `epoch_emission.v1`.
    - Epoch 23 (`+24h`, King decayed to `50%`):
      - `weights preview` replays Epoch 3's `ROW_VERIFIED` receipt from `publication.sqlite3`,
        queries live stake, previews exact non-zero Rung 2 Hold Bonus (`8_333_333_333` Q12),
        and leaves `hold_bonus_ledger.jsonl` byte-identical!
      - `weights run` persists `crown_credit.v1` + `stake_sample.v1` + `epoch_emission.v1`
        to `hold_bonus_ledger.jsonl` and publishes non-zero Rung 2 Hold Bonus to `ROW_VERIFIED`!
    - Epoch 24 (next epoch): reloads `hold_bonus_ledger.jsonl` from disk, settles ONLY Epoch 23
      (zero double-crediting of Epoch 3!), computes non-compounding Hold Bonus on `105 α` Crown
      principal (`8_750_000_000` Q12), and publishes to `ROW_VERIFIED`!"""
    from carbon.chain import sdk as chain_sdk
    from carbon.chain import sdk_weights
    from carbon.validator_setup import weights as vs_weights

    ctx, state_dir, op_cfg_path, standing_path, pool_path = _setup_sn116_cli_fixture(
        tmp_path
    )
    journal_path = state_dir / "publication.sqlite3"
    ledger_path = state_dir / "winners.jsonl"
    hold_jsonl_path = state_dir / twp.HOLD_LEDGER_FILENAME

    t0 = 20 * DAY_MS

    def _make_snap(block: int, now_ms: int) -> MetagraphSnapshot:
        return MetagraphSnapshot(
            context=ctx,
            finalized_block=block,
            block_hash="0x" + f"{block:064x}",
            timestamp_ms=now_ms,
            participants=(
                Participant(0, "hk_burn_owner", CARBON_EXCLUDED_COLDKEY, 1),
                Participant(1, "hk_sn116_validator", "ck_validator", 2),
                Participant(2, "hk_motor_king", "ck_motor_king", 10),
            ),
        )

    def _make_caps(snap: MetagraphSnapshot) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            snapshot_id=snap.snapshot_id,
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

    live_env = {
        "snap": _make_snap(1080, t0),
        "emission_rao": 100 * RAO,
        "stakes": {"ck_motor_king": 0, CARBON_EXCLUDED_COLDKEY: 0},
        "tx_seq": 0,
    }

    class _FakeCliBackend(_WaterfallBackend):
        def __init__(self, context, publisher, wallet, **kwargs):
            super().__init__(live_env["snap"], publisher=publisher)
            live_env["tx_seq"] += 1
            self.tx_hash = "0x" + f"{live_env['tx_seq']:064x}"

        async def observe(self):
            return self.state, _make_caps(self.state)

        async def close(self):
            pass

    async def _fake_capture(self, context):
        assert context == ctx
        return live_env["snap"]

    async def _fake_waterfall_read(
        context, *, block=None, block_hash=None, coldkeys=(), cadence_blocks=360
    ):
        assert context == ctx
        assert cadence_blocks == 360
        return {
            "block": block,
            "block_hash": block_hash,
            "epoch_miner_emission_rao": live_env["emission_rao"],
            "staked_by_coldkey": {ck: live_env["stakes"].get(ck, 0) for ck in coldkeys},
            "owner_coldkey": CARBON_EXCLUDED_COLDKEY,
            "owner_hotkeys": ("hk_burn_owner",),
        }

    monkeypatch.setattr(chain_sdk.BittensorReader, "capture", _fake_capture)
    monkeypatch.setattr(sdk_weights, "read_waterfall_chain_state", _fake_waterfall_read)
    monkeypatch.setattr(sdk_weights, "open_operator_wallet", lambda *a, **k: object())
    monkeypatch.setattr(sdk_weights, "BittensorPublicationBackend", _FakeCliBackend)

    def _cli_args(action: str):
        return SimpleNamespace(
            action=action,
            config=str(op_cfg_path),
            standing=str(standing_path),
            journal=str(journal_path),
            ledger=str(ledger_path),
            battery_deployment=None,
            lean_pool=[f"electric-motor-magnetics={pool_path}"],
            lean_pool_previous=None,
            policy_version="mainnet-winner-v5",
            repository=str(tmp_path),
            reconcile_archive_endpoint=None,
            archive_fallback_endpoint=None,
        )

    # --- Epoch 3 (Day 1): Preview writes nothing; Run publishes 100% King & writes hold_bonus_ledger.jsonl ---
    p_e3 = asyncio.run(vs_weights.execute(_cli_args("preview")))
    assert p_e3["signed"] is False
    assert p_e3["targets"]["winners"] == [
        [
            {
                "hotkey": "hk_motor_king",
                "coldkey": "ck_motor_king",
                "registered_at": 10,
            },
            Q12,
        ]
    ]
    assert p_e3["targets"]["hold_bonus"] == []
    assert not hold_jsonl_path.exists()

    r_e3 = asyncio.run(vs_weights.execute(_cli_args("run")))
    assert r_e3["state"] == "ROW_VERIFIED"
    assert hold_jsonl_path.is_file()
    assert (hold_jsonl_path.stat().st_mode & 0o777) == 0o600
    e3_lines = [json.loads(line) for line in hold_jsonl_path.read_text().splitlines()]
    assert e3_lines == [
        {
            "epoch": 3,
            "epoch_miner_emission_rao": str(100 * RAO),
            "kind": "epoch_emission.v1",
        }
    ]

    # --- Epoch 23 (+24h -> King at 50%, holding all 100 α earned in Epoch 3, live emission = 10 α) ---
    live_env["snap"] = _make_snap(8280, t0 + DAY_MS)
    live_env["emission_rao"] = 10 * RAO
    live_env["stakes"] = {"ck_motor_king": 100 * RAO, CARBON_EXCLUDED_COLDKEY: 0}
    before_e23_bytes = hold_jsonl_path.read_bytes()

    p_e23 = asyncio.run(vs_weights.execute(_cli_args("preview")))
    assert (
        hold_jsonl_path.read_bytes() == before_e23_bytes
    )  # Preview never mutates JSONL!
    # 100 α held * (5000 / 6_000_000) / 10 α * Q12 == 8_333_333_333 Q12!
    assert p_e23["targets"]["winners"] == [
        [
            {
                "hotkey": "hk_motor_king",
                "coldkey": "ck_motor_king",
                "registered_at": 10,
            },
            500_000_000_000,
        ]
    ]
    assert p_e23["targets"]["hold_bonus"] == [
        [
            {
                "hotkey": "hk_motor_king",
                "coldkey": "ck_motor_king",
                "registered_at": 10,
            },
            8_333_333_333,
        ]
    ]
    assert p_e23["targets"]["treasury"] == []
    assert p_e23["targets"]["burn"] == 491_666_666_667

    r_e23 = asyncio.run(vs_weights.execute(_cli_args("run")))
    assert r_e23["state"] == "ROW_VERIFIED"
    # Combined on UID 2 (King + Hold Bonus) = 508_333_333_333, Burn on UID 0 = 491_666_666_667
    assert r_e23["document"]["plan"]["q12"] == [
        [0, 491_666_666_667],
        [2, 508_333_333_333],
    ]

    # --- Epoch 24 (next epoch): reloads JSONL, settles ONLY Epoch 23 (no double-credit of Epoch 3!) ---
    # Epoch 23 emitted 10 α: King got 5 α (`50%`), Hold Bonus got `83_333_333` rao (`8_333_333_333 / 10^12 * 10 α`).
    # Total Crown principal C = 100 α + 5 α = 105 α; Bonus H = 83_333_333 rao; miner holds 200 α >= C + H!
    live_env["snap"] = _make_snap(8640, t0 + DAY_MS + 360 * 12_000)
    live_env["stakes"] = {"ck_motor_king": 200 * RAO, CARBON_EXCLUDED_COLDKEY: 0}

    p_e24 = asyncio.run(vs_weights.execute(_cli_args("preview")))
    # Non-compounding Hold Bonus on 105 α Crown principal: ((105 * 5000 / 6_000_000) / 10) * Q12 = 8_750_000_000!
    assert p_e24["targets"]["hold_bonus"] == [
        [
            {
                "hotkey": "hk_motor_king",
                "coldkey": "ck_motor_king",
                "registered_at": 10,
            },
            8_750_000_000,
        ]
    ]

    r_e24 = asyncio.run(vs_weights.execute(_cli_args("run")))
    assert r_e24["state"] == "ROW_VERIFIED"
    reloaded = HoldBonusLedger(hold_jsonl_path)
    try:
        assert reloaded.tracked_coldkeys() == [
            ("ck_motor_king", 105 * RAO, "hk_motor_king")
        ]
        assert reloaded.window_status("ck_motor_king", 24, 600) == (
            105 * RAO,
            Fraction(0),
        )
        assert reloaded.settled_intent_epochs() == frozenset({3, 23})
    finally:
        reloaded.close()


def test_cli_waterfall_observer_fails_closed_when_chain_read_unavailable(
    monkeypatch, tmp_path
):
    """If the Subtensor waterfall chain read raises, `_issuer`'s CLI observer fails closed
    with `WATERFALL_CHAIN_OBSERVATION_UNAVAILABLE`, writing nothing to disk."""
    from carbon.chain import sdk_weights
    from carbon.validator_setup import weights as vs_weights

    ctx, state_dir, op_cfg_path, standing_path, pool_path = _setup_sn116_cli_fixture(
        tmp_path
    )
    journal_path = state_dir / "publication.sqlite3"
    ledger_path = state_dir / "winners.jsonl"
    hold_jsonl_path = state_dir / twp.HOLD_LEDGER_FILENAME

    async def _broken_read(*args, **kwargs):
        raise RuntimeError("rpc socket closed")

    monkeypatch.setattr(sdk_weights, "read_waterfall_chain_state", _broken_read)
    config = vs_weights.load_config(op_cfg_path)
    args = SimpleNamespace(
        config=str(op_cfg_path),
        standing=str(standing_path),
        journal=str(journal_path),
        ledger=str(ledger_path),
        battery_deployment=None,
        lean_pool=[f"electric-motor-magnetics={pool_path}"],
        lean_pool_previous=None,
        policy_version="mainnet-winner-v5",
        repository=str(tmp_path),
    )
    issuer = twp._issuer(args, config, journal_path)
    snap = MetagraphSnapshot(
        context=ctx,
        finalized_block=1080,
        block_hash="0x" + f"{1080:064x}",
        timestamp_ms=20 * DAY_MS,
        participants=(
            Participant(0, "hk_burn_owner", CARBON_EXCLUDED_COLDKEY, 1),
            Participant(1, "hk_sn116_validator", "ck_validator", 2),
            Participant(2, "hk_motor_king", "ck_motor_king", 10),
        ),
    )
    for fn in (lambda: twp.preview(issuer, snap), lambda: issuer.issue(snap)):
        with pytest.raises(
            twp.WinnerPublicationRefused,
            match="WATERFALL_CHAIN_OBSERVATION_UNAVAILABLE",
        ):
            fn()
    assert not hold_jsonl_path.exists()


def test_hold_bonus_ledger_jsonl_tamper_and_symlink_refusal(tmp_path):
    target = tmp_path / "real.jsonl"
    target.write_text("", encoding="utf-8")
    link = tmp_path / "symlink.jsonl"
    link.symlink_to(target)
    with pytest.raises(RewardFailure, match="HOLD_LEDGER_SYMLINK_REFUSED"):
        HoldBonusLedger(link)

    corrupted = tmp_path / "corrupted.jsonl"
    corrupted.write_text('{"kind":"unknown.v1","epoch":1}\n', encoding="utf-8")
    with pytest.raises(RewardFailure, match="HOLD_LEDGER_CORRUPTED"):
        HoldBonusLedger(corrupted)


def test_f1_v4_to_v5_king_decay_clock_carryover_and_18_to_19_handover(
    monkeypatch, tmp_path
):
    """F1: Prove that an existing persisted `WinnerLedger` (`winners.jsonl`) recorded under
    `mainnet-winner-v4` with a Motor 1.8 `qualified_sealed` crown on `MOTOR_PACK` preserves its
    exact `clock_ms` (`promoted_at_ms`) when switching to `mainnet-winner-v5` — BOTH on direct
    `TestnetWinnerIntentIssuer` reload AND across a `1.8 -> 1.9` `Handover` (`--lean-pool` =
    empty Motor 1.9 store, `--lean-pool-previous` = Motor 1.8 store) via `weights.execute`:
    - At `t0 + 36h` (first `v5` epoch): King receives exact `50%` (`500_000_000_000` Q12),
      NEVER resetting to `100%`, and `winners.jsonl` stays byte-identical (`policy == mainnet-winner-v4`).
    - At `t0 + 48h`: King receives exact `25%` (`250_000_000_000` Q12)."""
    from carbon.battery.pool_store import PoolStore
    from carbon.chain import sdk as chain_sdk
    from carbon.chain import sdk_weights
    from carbon.validator_setup import weights as vs_weights

    v4 = wd.load_policy("mainnet-winner-v4")
    v5 = wd.load_policy("mainnet-winner-v5")
    ctx, state_dir, op_cfg_path, standing_path, motor_18_pool_path = (
        _setup_sn116_cli_fixture(tmp_path)
    )
    # Create an empty Motor 1.9 PoolStore (no incumbent yet -> triggers 1.8 -> 1.9 Handover!)
    motor_19_pool_path = tmp_path / "motor_19_pool.sqlite3"
    PoolStore(motor_19_pool_path, clock=lambda: 200.0)

    journal_path = state_dir / "publication.sqlite3"
    ledger_path = state_dir / "winners.jsonl"
    record_file = tmp_path / "OWNER-WEIGHTS-AUTHORITY-01.md"

    def _write_standing(policy_digest: str) -> None:
        standing_path.write_text(
            json.dumps(
                {
                    "authority": wd.MAINNET_AUTHORITY,
                    "authority_record": record_file.name,
                    "policy_digest": policy_digest,
                    "publisher_hotkey": "hk_sn116_validator",
                    "expected_runtime_spec": SPEC,
                    "valid_from_block": 1_000,
                    "valid_through_block": 500_000,
                }
            ),
            encoding="utf-8",
        )
        standing_path.chmod(0o600)

    t0 = 20 * DAY_MS

    def _make_snap(block: int, now_ms: int) -> MetagraphSnapshot:
        return MetagraphSnapshot(
            context=ctx,
            finalized_block=block,
            block_hash="0x" + f"{block:064x}",
            timestamp_ms=now_ms,
            participants=(
                Participant(0, "hk_burn_owner", CARBON_EXCLUDED_COLDKEY, 1),
                Participant(1, "hk_sn116_validator", "ck_validator", 2),
                Participant(2, "hk_motor_king", "ck_motor_king", 10),
            ),
        )

    def _make_caps(snap: MetagraphSnapshot) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            snapshot_id=snap.snapshot_id,
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

    live_env = {
        "snap": _make_snap(1080, t0),
        "emission_rao": 100 * RAO,
        "stakes": {
            "ck_motor_king": 100 * RAO,
            CARBON_EXCLUDED_COLDKEY: 0,
            "ck_validator": 0,
        },
        "tx_seq": 0,
    }

    class _FakeCliBackend(_WaterfallBackend):
        def __init__(self, context, publisher, wallet, **kwargs):
            super().__init__(live_env["snap"], publisher=publisher)
            live_env["tx_seq"] += 1
            self.tx_hash = "0x" + f"{live_env['tx_seq']:064x}"

        async def observe(self):
            return self.state, _make_caps(self.state)

        async def close(self):
            pass

    async def _fake_capture(self, context):
        return live_env["snap"]

    async def _fake_waterfall_read(
        context,
        *,
        block=None,
        block_hash=None,
        coldkeys=(),
        treasury_coldkeys=(),
        cadence_blocks=360,
    ):
        return {
            "block": block,
            "block_hash": block_hash,
            "epoch_miner_emission_rao": live_env["emission_rao"],
            "treasury_current_stake_rao": 0,
            "staked_by_coldkey": {ck: live_env["stakes"].get(ck, 0) for ck in coldkeys},
            "owner_coldkey": CARBON_EXCLUDED_COLDKEY,
            "owner_hotkeys": ("hk_burn_owner",),
        }

    monkeypatch.setattr(chain_sdk.BittensorReader, "capture", _fake_capture)
    monkeypatch.setattr(sdk_weights, "read_waterfall_chain_state", _fake_waterfall_read)
    monkeypatch.setattr(sdk_weights, "open_operator_wallet", lambda *a, **k: object())
    monkeypatch.setattr(sdk_weights, "BittensorPublicationBackend", _FakeCliBackend)

    def _cli_args(action: str, policy_version: str, *, handover: bool = True):
        return SimpleNamespace(
            action=action,
            config=str(op_cfg_path),
            standing=str(standing_path),
            journal=str(journal_path),
            ledger=str(ledger_path),
            battery_deployment=None,
            lean_pool=[
                f"electric-motor-magnetics={motor_19_pool_path if handover else motor_18_pool_path}"
            ],
            lean_pool_previous=(
                [f"electric-motor-magnetics={motor_18_pool_path}"] if handover else None
            ),
            policy_version=policy_version,
            repository=str(tmp_path),
            reconcile_archive_endpoint=None,
            archive_fallback_endpoint=None,
        )

    # --- Step 1: Run under `mainnet-winner-v4` at `t0` -> persists v4 WinnerLedger (`clock_ms == t0`) ---
    _write_standing(v4.digest)
    r_v4 = asyncio.run(
        vs_weights.execute(_cli_args("run", "mainnet-winner-v4", handover=True))
    )
    assert r_v4["state"] == "ROW_VERIFIED"
    v4_ledger_bytes = ledger_path.read_bytes()
    v4_records = we.WinnerLedger(ledger_path).records("electric-motor-magnetics")
    assert len(v4_records) == 1
    assert v4_records[0]["policy"] == v4.digest
    assert v4_records[0]["clock_ms"] == t0

    # --- Step 2: Cut over to `mainnet-winner-v5` at `t0 + 36h` (first v5 epoch!) ---
    _write_standing(v5.digest)
    t_36h = t0 + 36 * 3_600_000
    live_env["snap"] = _make_snap(11_880, t_36h)
    live_env["emission_rao"] = 10 * RAO

    # 2a) Direct TestnetWinnerIntentIssuer reload against the persisted v4 WinnerLedger
    direct_config = vs_weights.load_config(op_cfg_path)
    direct_issuer = twp._issuer(
        _cli_args("preview", "mainnet-winner-v5", handover=False),
        direct_config,
        tmp_path / "scratch_direct.sqlite3",
    )
    direct_preview_36h = twp.preview(direct_issuer, live_env["snap"])
    assert direct_preview_36h["records"]["electric-motor-magnetics"]["clock_ms"] == t0
    assert direct_preview_36h["targets"]["winners"] == [
        [
            {
                "hotkey": "hk_motor_king",
                "coldkey": "ck_motor_king",
                "registered_at": 10,
            },
            500_000_000_000,
        ]
    ]

    # 2b) Full `1.8 -> 1.9` Handover (`--lean-pool` = 1.9 empty, `--lean-pool-previous` = 1.8) via `weights run`
    r_v5_36h = asyncio.run(
        vs_weights.execute(_cli_args("run", "mainnet-winner-v5", handover=True))
    )
    assert r_v5_36h["state"] == "ROW_VERIFIED"
    # WinnerLedger on disk was NOT rewritten or re-clocked!
    assert ledger_path.read_bytes() == v4_ledger_bytes
    # 50% King (`500_000_000_000`) + Hold Bonus on settled v4 10 α (`833_333_333`) = `500_833_333_333` on UID 2!
    assert r_v5_36h["document"]["plan"]["q12"] == [
        [0, 499_166_666_667],
        [2, 500_833_333_333],
    ]

    # --- Step 3: Advance to `t0 + 48h` (2nd halving -> exact 25% King = `250_000_000_000`) ---
    t_48h = t0 + 2 * DAY_MS
    live_env["snap"] = _make_snap(15_480, t_48h)
    live_env["stakes"]["ck_motor_king"] = 200 * RAO
    p_v5_48h = asyncio.run(
        vs_weights.execute(_cli_args("preview", "mainnet-winner-v5", handover=True))
    )
    assert p_v5_48h["records"]["electric-motor-magnetics"]["clock_ms"] == t0
    assert p_v5_48h["targets"]["winners"] == [
        [
            {
                "hotkey": "hk_motor_king",
                "coldkey": "ck_motor_king",
                "registered_at": 10,
            },
            250_000_000_000,
        ]
    ]
    assert ledger_path.read_bytes() == v4_ledger_bytes


def test_read_waterfall_chain_state_queries_block_pinned_subtensor_storage_and_runtime_api(
    monkeypatch,
):
    """F4 + F5 + Blocker 1: Verify `carbon.chain.sdk_weights.read_waterfall_chain_state`
    queries block-pinned Subtensor `metagraph` (`alpha_out_emission`), `SubnetOwner`,
    `SubnetOwnerHotkey`, `OwnedHotkeys`, `SubnetOwnerCut`, `LastEpochBlock`, and
    `StakeInfoRuntimeApi.get_stake_info_for_coldkeys` (without querying non-existent
    `OwnerCutEnabled`), and fails closed on genesis mismatch, block-hash drift, or
    missing `SubnetOwner`."""
    import sys

    from carbon.chain import networks, sdk_weights
    from carbon.chain.publication import PublicationFailure

    finney_row = networks.NETWORKS["finney"]
    ctx = ChainContext(
        "finney",
        "wss://entrypoint-finney.opentensor.ai:443",
        finney_row.chain_id,
        finney_row.genesis_hash,
        116,
    )
    pinned_block = 4_320_000
    pinned_hash = "0x" + "ab" * 32

    rpc_state = {
        "genesis_hash": finney_row.genesis_hash,
        "block_hashes": {0: finney_row.genesis_hash, pinned_block: pinned_hash},
        "post_block_hash": pinned_hash,
        "alpha_out_emission": 1_000_000_000,  # 1.0 α per block
        "owner_coldkey": CARBON_EXCLUDED_COLDKEY,
        "owner_hotkey": "hk_owner_primary",
        "owned_hotkeys": ["hk_owner_secondary"],
        "owner_cut": 11_796,  # ~18% owner cut (`11796 / 65535`)
        "last_epoch_block": 4_319_800,
        "closed": 0,
    }
    calls_seen: list[tuple] = []

    class _FakeSubstrate:
        def __init__(
            self, endpoint, *, fallback_endpoints, archive_endpoints, retry_forever
        ):
            assert endpoint == ctx.endpoint
            assert fallback_endpoints == []
            assert archive_endpoints == []
            assert retry_forever is False
            self._reads = 0

        async def connect(self):
            calls_seen.append(("connect",))

        async def block_hash(self, number):
            if number == 0:
                return rpc_state["genesis_hash"]
            assert number == pinned_block
            self._reads += 1
            return (
                rpc_state["block_hashes"][pinned_block]
                if self._reads == 1
                else rpc_state["post_block_hash"]
            )

        async def query(self, module, name, args=None, *, block_hash=None):
            assert module == "SubtensorModule"
            assert block_hash == pinned_hash
            calls_seen.append(("query", name, args))
            if name == "SubnetOwner":
                assert args == [116]
                return rpc_state["owner_coldkey"]
            if name == "SubnetOwnerHotkey":
                assert args == [116]
                return rpc_state["owner_hotkey"]
            if name == "SubnetOwnerCut":
                return rpc_state["owner_cut"]
            if name == "LastEpochBlock":
                assert args == [116]
                return rpc_state["last_epoch_block"]
            if name == "OwnedHotkeys":
                assert args == [rpc_state["owner_coldkey"]]
                return rpc_state["owned_hotkeys"]
            raise AssertionError(f"unexpected query {name}")

    stake_fn_sentinel = object()

    class _FakeView:
        async def read(self, what, *, netuid):
            assert what == "metagraph" and netuid == 116
            return {"alpha_out_emission": rpc_state["alpha_out_emission"]}

        async def runtime(self, fn, params):
            assert fn is stake_fn_sentinel
            (ck_list,) = params
            calls_seen.append(("runtime_stake", tuple(ck_list)))
            return {
                "ck_miner_a": [
                    {
                        "hotkey": "hk_a1",
                        "coldkey": "ck_miner_a",
                        "netuid": 116,
                        "stake": 700 * RAO,
                    },
                    {
                        "hotkey": "hk_a2",
                        "coldkey": "ck_miner_a",
                        "netuid": 116,
                        "stake": 300 * RAO,
                    },
                    {
                        "hotkey": "hk_other_sn",
                        "coldkey": "ck_miner_a",
                        "netuid": 1,
                        "stake": 9_999 * RAO,
                    },
                ],
                VAULT_EXCLUDED_COLDKEY: [
                    {
                        "hotkey": "hk_sink_0",
                        "coldkey": VAULT_EXCLUDED_COLDKEY,
                        "netuid": 116,
                        "stake": 2_500 * RAO,
                    },
                ],
            }

    class _FakeClient:
        def __init__(self, endpoint, *, substrate):
            assert endpoint == ctx.endpoint
            self.substrate = substrate

        async def at(self, number):
            assert number == pinned_block
            return _FakeView()

        async def close(self):
            rpc_state["closed"] += 1

    fake_bt = SimpleNamespace(
        RpcSubstrate=_FakeSubstrate,
        Client=_FakeClient,
        _generated=SimpleNamespace(
            runtime_apis=SimpleNamespace(
                StakeInfoRuntimeApi=SimpleNamespace(
                    get_stake_info_for_coldkeys=stake_fn_sentinel
                )
            )
        ),
    )
    monkeypatch.setattr(sdk_weights, "require_sdk", lambda: None)
    monkeypatch.setitem(sys.modules, "bittensor", fake_bt)

    res = asyncio.run(
        sdk_weights.read_waterfall_chain_state(
            ctx,
            block=pinned_block,
            block_hash=pinned_hash,
            coldkeys=("ck_miner_a", "ck_miner_zero"),
            treasury_coldkeys=(VAULT_EXCLUDED_COLDKEY,),
            cadence_blocks=360,
        )
    )
    assert all(c[1] != "OwnerCutEnabled" for c in calls_seen if c[0] == "query")
    expected_after_owner = 1_000_000_000 - (1_000_000_000 * 11_796) // 65535
    expected_epoch_emission = (expected_after_owner // 2) * 360
    assert res == {
        "block": pinned_block,
        "block_hash": pinned_hash,
        "last_epoch_block": 4_319_800,
        "epoch_miner_emission_rao": expected_epoch_emission,
        "treasury_current_stake_rao": 2_500 * RAO,
        "staked_by_coldkey": {
            VAULT_EXCLUDED_COLDKEY: 2_500 * RAO,
            "ck_miner_a": 1_000 * RAO,  # netuid 116 stakes summed, netuid 1 ignored!
            "ck_miner_zero": 0,
        },
        "owner_coldkey": CARBON_EXCLUDED_COLDKEY,
        "owner_hotkeys": ("hk_owner_primary", "hk_owner_secondary"),
    }
    assert rpc_state["closed"] == 1

    # Fail-closed 1: Genesis hash mismatch
    rpc_state["genesis_hash"] = "0x" + "ff" * 32
    with pytest.raises(PublicationFailure, match="ENDPOINT_GENESIS_MISMATCH"):
        asyncio.run(
            sdk_weights.read_waterfall_chain_state(
                ctx, block=pinned_block, block_hash=pinned_hash
            )
        )
    rpc_state["genesis_hash"] = finney_row.genesis_hash

    # Fail-closed 2: Reorg / conflicting block hash during read
    rpc_state["post_block_hash"] = "0x" + "cd" * 32
    with pytest.raises(PublicationFailure, match="CONFLICTING_PROVIDER_IDENTITY"):
        asyncio.run(
            sdk_weights.read_waterfall_chain_state(
                ctx, block=pinned_block, block_hash=pinned_hash
            )
        )
    rpc_state["post_block_hash"] = pinned_hash

    # Fail-closed 3: SubnetOwner returns None -> never coerced to `"None"`!
    rpc_state["owner_coldkey"] = None
    with pytest.raises(
        PublicationFailure, match="WATERFALL_CHAIN_OBSERVATION_UNAVAILABLE"
    ):
        asyncio.run(
            sdk_weights.read_waterfall_chain_state(
                ctx, block=pinned_block, block_hash=pinned_hash
            )
        )
    rpc_state["owner_coldkey"] = CARBON_EXCLUDED_COLDKEY

    # Fail-closed 4: LastEpochBlock missing or > target_block
    rpc_state["last_epoch_block"] = None
    with pytest.raises(
        PublicationFailure, match="WATERFALL_CHAIN_OBSERVATION_UNAVAILABLE"
    ):
        asyncio.run(
            sdk_weights.read_waterfall_chain_state(
                ctx, block=pinned_block, block_hash=pinned_hash
            )
        )
    rpc_state["last_epoch_block"] = pinned_block + 1
    with pytest.raises(
        PublicationFailure, match="WATERFALL_CHAIN_OBSERVATION_UNAVAILABLE"
    ):
        asyncio.run(
            sdk_weights.read_waterfall_chain_state(
                ctx, block=pinned_block, block_hash=pinned_hash
            )
        )


def test_read_waterfall_chain_state_sn116_bittensor_contract_and_attribute_shapes(
    monkeypatch,
):
    """Blocker 1 contract test: Verify real `bittensor` (`Balance`, `sp_core.ss58_encode`,
    `SubtensorModule` storage descriptors, `StakeInfoRuntimeApi.get_stake_info_for_coldkeys`)
    and `SN116`-shaped `MetagraphInfo` (`alpha_out_emission` as `Balance`) + attribute-style
    `StakeInfo` entries with raw 32-byte `bytes` and 32-int `tuple` `ck_raw` decode cleanly
    into exact `1x` 360-block miner Alpha emission (`147_600_824_040` rao)."""
    import sys

    import bittensor as bt
    from bittensor._generated import runtime_apis, storage

    from carbon.chain import networks, sdk_weights
    from carbon.chain.publication import PublicationFailure

    # Contract check against installed bittensor descriptors
    assert hasattr(storage.SubtensorModule, "SubnetOwnerCut")
    assert hasattr(storage.SubtensorModule, "LastEpochBlock")
    assert hasattr(storage.SubtensorModule, "SubnetOwner")
    assert hasattr(storage.SubtensorModule, "SubnetOwnerHotkey")
    assert hasattr(storage.SubtensorModule, "OwnedHotkeys")
    assert hasattr(runtime_apis.StakeInfoRuntimeApi, "get_stake_info_for_coldkeys")

    finney_row = networks.NETWORKS["finney"]
    ctx = ChainContext(
        "finney",
        "wss://entrypoint-finney.opentensor.ai:443",
        finney_row.chain_id,
        finney_row.genesis_hash,
        116,
    )
    pinned_block = 9_594_954
    pinned_hash = "0x" + "99" * 32
    miner_ck = "5GNT77U8rC81CAzJu6r2FzkwYHiBFEAtiBnVdSE6WAejoGCd"
    miner_raw_bytes = bytes(bt.sp_core.ss58_decode(miner_ck))
    vault_raw_tuple = tuple(bt.sp_core.ss58_decode(VAULT_EXCLUDED_COLDKEY))
    runtime_calls: list[tuple] = []

    class _RealLikeSubstrate:
        def __init__(self, *args, **kwargs):
            pass

        async def connect(self):
            pass

        async def block_hash(self, number):
            return finney_row.genesis_hash if number == 0 else pinned_hash

        async def query(self, module, name, args=None, *, block_hash=None):
            assert module == "SubtensorModule"
            assert block_hash == pinned_hash
            if name == "OwnerCutEnabled":
                raise AssertionError("OwnerCutEnabled must never be queried")
            if name == "SubnetOwner":
                return CARBON_EXCLUDED_COLDKEY
            if name == "SubnetOwnerHotkey":
                return "5DDLUnX2yicKLC1T5PN7bkwgU51buJt93XQFV1giqhDsGUTk"
            if name == "SubnetOwnerCut":
                return 11_796
            if name == "LastEpochBlock":
                return 9_594_636
            if name == "OwnedHotkeys":
                return []
            raise AssertionError(f"unexpected query {name}")

        async def runtime_call(self, api, method, params, *, block_hash=None):
            runtime_calls.append((api, method, params, block_hash))
            assert api == "StakeInfoRuntimeApi"
            assert method == "get_stake_info_for_coldkeys"
            assert block_hash == pinned_hash
            return [
                (
                    miner_raw_bytes,
                    [
                        SimpleNamespace(
                            hotkey="5HKf8RVX7tzCZGf4vmpSFpmetFNxaRcdd3R36rN6UjQ3CLjx",
                            coldkey=miner_ck,
                            netuid=116,
                            stake=bt.Balance.from_rao(147_617_612_099),
                        ),
                        SimpleNamespace(
                            hotkey="5HKf8RVX7tzCZGf4vmpSFpmetFNxaRcdd3R36rN6UjQ3CLjx",
                            coldkey=miner_ck,
                            netuid=1,
                            stake=bt.Balance.from_rao(999 * RAO),
                        ),
                    ],
                ),
                (
                    vault_raw_tuple,
                    [
                        SimpleNamespace(
                            hotkey="hk_sink_0",
                            coldkey=VAULT_EXCLUDED_COLDKEY,
                            netuid=116,
                            stake=bt.Balance.from_rao(5_000 * RAO),
                        )
                    ],
                ),
            ]

    class _MetagraphView:
        async def read(self, what, *, netuid):
            assert what == "metagraph" and netuid == 116
            return SimpleNamespace(
                netuid=116,
                alpha_out_emission=bt.Balance.from_rao(1_000_000_000),
            )

    class _Client:
        def __init__(self, endpoint, *, substrate):
            self.substrate = substrate

        async def at(self, block):
            assert block == pinned_block
            return _MetagraphView()

        async def close(self):
            pass

    patched_bt = SimpleNamespace(
        RpcSubstrate=_RealLikeSubstrate,
        Client=_Client,
        sp_core=bt.sp_core,
        _generated=bt._generated,
    )
    monkeypatch.setattr(sdk_weights, "require_sdk", lambda: None)
    monkeypatch.setitem(sys.modules, "bittensor", patched_bt)

    res = asyncio.run(
        sdk_weights.read_waterfall_chain_state(
            ctx,
            block=pinned_block,
            block_hash=pinned_hash,
            coldkeys=(miner_ck,),
            treasury_coldkeys=(VAULT_EXCLUDED_COLDKEY,),
            cadence_blocks=360,
        )
    )
    assert len(runtime_calls) == 1
    assert res["last_epoch_block"] == 9_594_636
    # 1.0 α/block minus 11796/65535 owner cut, / 2 miner split, * 360 blocks = 147.600824040 α (1x miner pool!)
    assert res["epoch_miner_emission_rao"] == 147_600_824_040
    assert res["staked_by_coldkey"] == {
        VAULT_EXCLUDED_COLDKEY: 5_000 * RAO,
        miner_ck: 147_617_612_099,
    }
    assert res["treasury_current_stake_rao"] == 5_000 * RAO

    # Fail-closed if alpha_out_emission is a list instead of a scalar Balance/int
    class _BadListMetagraphView:
        async def read(self, what, *, netuid):
            return SimpleNamespace(netuid=116, alpha_out_emission=[1_000_000_000])

    _Client.at = lambda self, block: asyncio.sleep(0, result=_BadListMetagraphView())
    with pytest.raises(
        PublicationFailure, match="WATERFALL_CHAIN_OBSERVATION_UNAVAILABLE"
    ):
        asyncio.run(
            sdk_weights.read_waterfall_chain_state(
                ctx, block=pinned_block, block_hash=pinned_hash
            )
        )


def test_hold_bonus_ledger_settled_intent_v1_persistence_batch_and_tamper_refusal(
    tmp_path,
):
    jsonl_path = tmp_path / "hold.jsonl"
    ledger = HoldBonusLedger(jsonl_path)
    try:
        with ledger.batch():
            ledger.record_crown_earnings(12, {"ck_a": (100 * RAO, "hk_a")})
            ledger.sample_epoch_stakes(12, {"ck_a": 100 * RAO})
            ledger.record_epoch_emission(12, 100 * RAO)
            ledger.record_settled_intents((10, 10))
        assert ledger.settled_intent_epochs() == frozenset({10})
    finally:
        ledger.close()

    reloaded = HoldBonusLedger(jsonl_path)
    try:
        assert reloaded.settled_intent_epochs() == frozenset({10})
        assert reloaded.tracked_coldkeys() == [("ck_a", 100 * RAO, "hk_a")]
        before = jsonl_path.read_bytes()
        reloaded.record_settled_intents((10,))
        assert jsonl_path.read_bytes() == before
        # Failed batch never flushes partial mutations to disk
        with (
            pytest.raises(RewardFailure, match="INVALID_EPOCH"),
            reloaded.batch(),
        ):
            reloaded.record_settled_intents((11,))
            reloaded.record_settled_intents((-1,))
        assert jsonl_path.read_bytes() == before
    finally:
        reloaded.close()

    bad = tmp_path / "bad_settled.jsonl"
    bad.write_text(
        '{"intent_epoch":true,"kind":"settled_intent.v1"}\n', encoding="utf-8"
    )
    with pytest.raises(RewardFailure, match="HOLD_LEDGER_CORRUPTED"):
        HoldBonusLedger(bad)


def test_commit_reveal_tempo_payout_lag_maturity_and_journal_integrity(
    monkeypatch, tmp_path
):
    """Blocker 2 E2E regression (`commit_reveal = True`):
    - Epoch 10 (`block = 3610`, `last_epoch_block = 3600`): new King `ck_motor_king` (`0 α`
      prior stake) is issued `e10`, committed timelocked (`REVEAL_PENDING`, `100 α` emission).
    - Epoch 11 (`block = 4000`, `last_epoch_block = 3990`, `+24h` so King decays to `50%`,
      `B(ck) = 0 α`): `settle_pending` reveals `e10` at `3990` (`tracking['reveal_block'] = 3990`)
      and marks `e10` `ROW_VERIFIED`, then issues `e11`. Because `last_epoch_block (3990) <=
      reveal_block (3990)`, `e10` is NOT payout-mature yet -> Epoch 11 writes `epoch_emission.v1`
      and does NOT falsely credit `e10` or record `100%` sold!
    - Epoch 12 (`block = 4360`, `last_epoch_block = 4351`, `B(ck) = 100 α`): Subtensor's tempo
      at `3990 + 361 = 4351` has minted `e10`'s `100 α` into `B(ck)` (and revealed `e11` at `4351`).
      `e10` IS payout-mature (`4351 > 3990`) even though Epoch 11 wrote `epoch_emission.v1`!
      `sold_ratio == 0` in BOTH Epoch 11 and Epoch 12, `external_stake_rao == 0`, and Hold Bonus
      pays the `+50%` full rate (`833_333_333` Q12)!
    - Epoch 13 (`block = 4720`, `last_epoch_block = 4712`, `B(ck) = 150 α`): reloads from disk,
      never double-credits `e10`, and settles `e11` (`+50 α`)."""
    import sqlite3

    from carbon.chain import sdk as chain_sdk
    from carbon.chain import sdk_weights
    from carbon.validator_setup import weights as vs_weights

    ctx, state_dir, op_cfg_path, standing_path, pool_path = _setup_sn116_cli_fixture(
        tmp_path
    )
    journal_path = state_dir / "publication.sqlite3"
    ledger_path = state_dir / "winners.jsonl"
    hold_jsonl_path = state_dir / twp.HOLD_LEDGER_FILENAME
    t0 = 20 * DAY_MS

    def _make_snap(block: int, now_ms: int) -> MetagraphSnapshot:
        return MetagraphSnapshot(
            context=ctx,
            finalized_block=block,
            block_hash="0x" + f"{block:064x}",
            timestamp_ms=now_ms,
            participants=(
                Participant(0, "hk_burn_owner", CARBON_EXCLUDED_COLDKEY, 1),
                Participant(1, "hk_sn116_validator", "ck_validator", 2),
                Participant(2, "hk_motor_king", "ck_motor_king", 10),
            ),
        )

    def _make_caps(snap: MetagraphSnapshot) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            snapshot_id=snap.snapshot_id,
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
            commit_reveal=True,
            validator_permit=True,
            sufficient_stake=True,
        )

    live_env = {
        "snap": _make_snap(3610, t0),
        "last_epoch_block": 3600,
        "emission_rao": 100 * RAO,
        "stakes": {"ck_motor_king": 0, CARBON_EXCLUDED_COLDKEY: 0},
        "revealed_blocks": set(),
        "stored_rows": {},
        "tx_seq": 0,
    }

    class _CommitRevealCliBackend:
        def __init__(self, context, publisher, wallet, **kwargs):
            self.context = context
            self.publisher = publisher
            self._tx_blocks: dict[str, int] = {}

        async def observe(self):
            return live_env["snap"], _make_caps(live_env["snap"])

        async def execute(
            self, plan, integer_guard, call_checked, before_sign, dispatch
        ):
            uids = [uid for uid, _ in plan.integers]
            values = [value for _, value in plan.integers]
            preflight = SimpleNamespace(
                uid=plan.publisher_uid,
                min_allowed_weights=1,
                max_weight_limit=U16,
                commit_reveal=True,
            )
            await integer_guard(uids, values, preflight)
            call = SimpleNamespace(data=b"cr-weights", spec_version=SPEC)
            await call_checked(call, {"reveal_round": 1})
            await before_sign(call, self.publisher)
            live_env["tx_seq"] += 1
            tx_hash = "0x" + f"{live_env['tx_seq']:064x}"
            await dispatch(tx_hash)
            commit_block = live_env["snap"].finalized_block + 1
            live_env["snap"] = dataclasses.replace(
                live_env["snap"],
                finalized_block=commit_block,
                block_hash="0x" + f"{commit_block:064x}",
            )
            self._tx_blocks[tx_hash] = commit_block
            live_env["stored_rows"][commit_block] = [
                list(item) for item in plan.integers
            ]

        async def transaction(self, tx_hash, block):
            # Look up block from journal/tx_seq: commit occurs at finalized_block+1
            if tx_hash in self._tx_blocks and block == self._tx_blocks[tx_hash]:
                return TransactionObservation(True, block, "0x" + f"{block:064x}")
            for seq, b in ((1, 3611), (2, 4001), (3, 4361), (4, 4721)):
                if tx_hash == "0x" + f"{seq:064x}" and block == b:
                    return TransactionObservation(True, block, "0x" + f"{block:064x}")
            return None

        async def revealed(self, publisher, block):
            return publisher == self.publisher and block in live_env["revealed_blocks"]

        async def weight_row(self, state, uid):
            # Return latest stored row updated at or before state.finalized_block
            eligible = [
                (b, r)
                for b, r in live_env["stored_rows"].items()
                if b <= state.finalized_block
            ]
            b, row = max(eligible, key=lambda item: item[0])
            return row, b

        async def close(self):
            pass

    async def _fake_capture(self, context):
        return live_env["snap"]

    async def _fake_waterfall_read(
        context,
        *,
        block=None,
        block_hash=None,
        coldkeys=(),
        treasury_coldkeys=(),
        cadence_blocks=360,
    ):
        return {
            "block": block,
            "block_hash": block_hash,
            "last_epoch_block": live_env["last_epoch_block"],
            "epoch_miner_emission_rao": live_env["emission_rao"],
            "treasury_current_stake_rao": 0,
            "staked_by_coldkey": {ck: live_env["stakes"].get(ck, 0) for ck in coldkeys},
            "owner_coldkey": CARBON_EXCLUDED_COLDKEY,
            "owner_hotkeys": ("hk_burn_owner",),
        }

    monkeypatch.setattr(chain_sdk.BittensorReader, "capture", _fake_capture)
    monkeypatch.setattr(sdk_weights, "read_waterfall_chain_state", _fake_waterfall_read)
    monkeypatch.setattr(sdk_weights, "open_operator_wallet", lambda *a, **k: object())
    monkeypatch.setattr(
        sdk_weights, "BittensorPublicationBackend", _CommitRevealCliBackend
    )

    def _cli_args(action: str):
        return SimpleNamespace(
            action=action,
            config=str(op_cfg_path),
            standing=str(standing_path),
            journal=str(journal_path),
            ledger=str(ledger_path),
            battery_deployment=None,
            lean_pool=[f"electric-motor-magnetics={pool_path}"],
            lean_pool_previous=None,
            policy_version="mainnet-winner-v5",
            repository=str(tmp_path),
            reconcile_archive_endpoint=None,
            archive_fallback_endpoint=None,
        )

    # --- Epoch 10 (`block = 3610`): commits `e10` -> REVEAL_PENDING ---
    r_e10 = asyncio.run(vs_weights.execute(_cli_args("run")))
    assert r_e10["state"] == "REVEAL_PENDING"
    assert r_e10["document"]["intent"]["identity"].endswith("-e10")

    # --- Epoch 11 (`block = 4000`, `last_epoch_block = 3990`, reveal at `3990`, `B(ck) = 0`) ---
    # King is at 50% (+24h), `e10` reveals at 3990 and becomes ROW_VERIFIED,
    # yet payout will not mint until block 4351 (`last_epoch_block = 3990 <= 3990`).
    live_env["snap"] = _make_snap(4000, t0 + DAY_MS)
    live_env["last_epoch_block"] = 3990
    live_env["revealed_blocks"].add(3990)

    p_e11 = asyncio.run(vs_weights.execute(_cli_args("preview")))
    assert p_e11["targets"]["winners"][0][1] == 500_000_000_000
    assert p_e11["targets"]["hold_bonus"] == []

    r_e11 = asyncio.run(vs_weights.execute(_cli_args("run")))
    assert r_e11["state"] == "REVEAL_PENDING"
    assert r_e11["document"]["intent"]["identity"].endswith("-e11")

    l11 = HoldBonusLedger(hold_jsonl_path)
    try:
        assert l11.settled_intent_epochs() == frozenset()
        assert l11.epoch_emission(11) == 100 * RAO
        assert l11.coldkey_stake_tracking("ck_motor_king") == (0, None)
        assert l11.window_status("ck_motor_king", 11, 600) is None
    finally:
        l11.close()

    # --- Epoch 12 (`block = 4360`, `last_epoch_block = 4351`, `B(ck) = 100 α`) ---
    # Coinbase at 4351 minted `e10`'s 100 α into `B(ck)` and revealed `e11` at 4351.
    live_env["snap"] = _make_snap(4360, t0 + DAY_MS + 360 * 12_000)
    live_env["last_epoch_block"] = 4351
    live_env["revealed_blocks"].add(4351)
    live_env["stakes"]["ck_motor_king"] = 100 * RAO

    before_e12_bytes = hold_jsonl_path.read_bytes()
    p_e12 = asyncio.run(vs_weights.execute(_cli_args("preview")))
    assert hold_jsonl_path.read_bytes() == before_e12_bytes
    # +50% over 600 epochs on 100 α held at 0% sold (`833_333_333` Q12)!
    assert p_e12["targets"]["hold_bonus"] == [
        [
            {
                "hotkey": "hk_motor_king",
                "coldkey": "ck_motor_king",
                "registered_at": 10,
            },
            833_333_333,
        ]
    ]

    r_e12 = asyncio.run(vs_weights.execute(_cli_args("run")))
    assert r_e12["state"] == "REVEAL_PENDING"
    assert r_e12["document"]["intent"]["identity"].endswith("-e12")

    l12 = HoldBonusLedger(hold_jsonl_path)
    try:
        assert l12.settled_intent_epochs() == frozenset({10})
        assert l12.coldkey_stake_tracking("ck_motor_king") == (0, 100 * RAO)
        assert l12.window_status("ck_motor_king", 11, 600) is None
        assert l12.window_status("ck_motor_king", 12, 600) == (
            100 * RAO,
            Fraction(0),
        )
    finally:
        l12.close()

    # --- Epoch 13 (`block = 4720`, `last_epoch_block = 4712`, `B(ck) = 150 α`) ---
    # Settles `e11` (+50 α) ONLY without double-crediting `e10`!
    live_env["snap"] = _make_snap(4720, t0 + DAY_MS + 2 * 360 * 12_000)
    live_env["last_epoch_block"] = 4712
    live_env["revealed_blocks"].add(4712)
    live_env["stakes"]["ck_motor_king"] = 150 * RAO

    r_e13 = asyncio.run(vs_weights.execute(_cli_args("run")))
    assert r_e13["state"] == "REVEAL_PENDING"
    l13 = HoldBonusLedger(hold_jsonl_path)
    try:
        assert l13.settled_intent_epochs() == frozenset({10, 11})
        assert l13.coldkey_stake_tracking("ck_motor_king") == (0, 150 * RAO)
        assert l13.window_status("ck_motor_king", 13, 600) == (
            150 * RAO,
            Fraction(0),
        )
    finally:
        l13.close()

    # Verify offline fallback maturity when `last_epoch_block=None`
    assert twp._settled_waterfall_intents(
        journal_path,
        dataclasses.asdict(ctx),
        12,
        snapshot_finalized_block=4360,
        cadence_blocks=360,
        last_epoch_block=None,
        already_settled_epochs=frozenset(),
        check_maturity=True,
    ) == [
        json.loads(
            sqlite3.connect(journal_path)
            .execute(
                "SELECT body FROM testnet_winner_intent_v1 WHERE identity LIKE '%-e10'"
            )
            .fetchone()[0]
        )
    ]

    # Verify tamper on `publication_v1.digest` or `tracking_digest` or invalid `reveal_block` fails closed
    journal_bytes = journal_path.read_bytes()
    with sqlite3.connect(journal_path) as db:
        db.execute("UPDATE publication_v1 SET digest = '0' WHERE state='ROW_VERIFIED'")
    with pytest.raises(
        twp.WinnerPublicationRefused, match="CONFLICTING_DISPATCH_JOURNAL"
    ):
        twp._settled_waterfall_intents(
            journal_path,
            dataclasses.asdict(ctx),
            14,
            snapshot_finalized_block=5000,
            cadence_blocks=360,
            last_epoch_block=4712,
            already_settled_epochs=frozenset(),
            check_maturity=True,
        )

    journal_path.write_bytes(journal_bytes)
    with sqlite3.connect(journal_path) as db:
        db.execute(
            "UPDATE publication_v1 SET tracking_digest = '0' WHERE state='ROW_VERIFIED'"
        )
    with pytest.raises(
        twp.WinnerPublicationRefused, match="CONFLICTING_DISPATCH_JOURNAL"
    ):
        twp._settled_waterfall_intents(
            journal_path,
            dataclasses.asdict(ctx),
            14,
            snapshot_finalized_block=5000,
            cadence_blocks=360,
            last_epoch_block=4712,
            already_settled_epochs=frozenset(),
            check_maturity=True,
        )
