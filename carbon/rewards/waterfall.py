"""Unified 4-Rung Post-Crown Settlement Waterfall (Track 3).

Routes each 360-block epoch's Q12 (10^12) miner weight across four ordered rungs:
  1. Active Challenge King(s) — full share for 24h, halving every 24h thereafter,
     with an optional u16 >= 1 floor (`MIN_POSITIVE_U16_Q12`) when enabled in policy.
     Excluded coldkeys (`excluded_coldkeys`, `treasury_sinks`, and `owner_coldkey` off
     testnet) and excluded hotkeys (`owner_hotkeys`, `publisher_hotkey`, `canary_hotkeys`,
     `treasury_sinks`) receive 0 King pay and burn their Challenge slot directly to UID 0.
  2. Miner Hold Bonus — first claim ONLY on the decayed portion of Challenge slots that
     have a payable King (`decayed_from_active_kings_q12`), capped at
     `min(hold_cap_q12, decayed_from_active_kings_q12)`. Empty / un-won / excluded
     Challenge slots burn directly to UID 0 and never fund Hold Bonus or Treasury.
     Tracks cumulative Challenge Crown Alpha `C(c,t)`, cumulative Hold Bonus Alpha `H(c,t)`
     (`I(c,t) = C(c,t) + H(c,t)`), and `external_stake_rao` / `last_observed_stake_rao` so
     pre-existing, bought, or transferred-in Alpha never masks selling mined rewards
     (`retained_mined_rao = max(0, B(c,t) - external_stake_rao)`). Evaluates point-in-time
     sold ratio `S_c` and non-compounding principal `(C * min(retained_mined_rao, I)) // I`.
  3. Community Treasury Sink(s) — receives unused active-King decay across identity-pinned
     `(hotkey, coldkey, registered_at)` vault sink UIDs ONLY while observed treasury
     stake is strictly below `treasury_stake_cap_rao` (fail-closed if None or >= cap).
  4. UID 0 Burn — receives 100% of empty/excluded Challenge slots, `Q12 % N`, above-cap
     treasury overflow, unclaimed active-King decay, and integer dust.

Pure policy & journal arithmetic: imports no SDK, scoring, seeding, or signing modules.
Every economic parameter requires explicit configuration (no hardcoded live values).
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from carbon.chain.models import MetagraphSnapshot, Participant, identifier, uint

from .core import Q12, RewardFailure, units

U16_MAX = 65535
#: Smallest Q12 weight guaranteed to round to >= 1 in `round(Fraction(q12 * 65535, top))`
#: for every `top <= Q12` (`7_629_511 * 65535 = 500_000_003_385 > Q12 / 2`).
MIN_POSITIVE_U16_Q12 = (Q12 // (2 * U16_MAX)) + 1
WATERFALL_ROUTE = "WATERFALL_KING_BONUS_TREASURY_BURN"


@dataclass(frozen=True)
class PinnedTreasurySink:
    """Identity-pinned Treasury Vault sink UID (`hotkey`, `coldkey`, `registered_at`).
    If a sink UID deregisters and another miner registers on that UID or hotkey,
    the tuple fails to match `MetagraphSnapshot` and receives zero weight."""

    hotkey: str
    coldkey: str
    registered_at: int

    def __post_init__(self) -> None:
        identifier(self.hotkey)
        identifier(self.coldkey)
        uint(self.registered_at)


@dataclass(frozen=True)
class WaterfallConfig:
    """Explicit owner-configured parameters for the 4-rung waterfall.
    Setting `hold_cap_q12 = 0` or `window_bonus_rate_bps = 0` disables Rung 2;
    setting `treasury_stake_cap_rao = 0` or `treasury_sinks = ()` disables Rung 3."""

    hold_window_epochs: int
    hold_cap_q12: int
    window_bonus_rate_bps: int
    zero_bonus_sold_bps: int
    treasury_sinks: tuple[PinnedTreasurySink, ...]
    treasury_stake_cap_rao: int
    excluded_coldkeys: frozenset[str] = frozenset()
    enforce_king_u16_floor: bool = True

    def __post_init__(self) -> None:
        if (
            type(self.hold_window_epochs) is not int
            or not 1 <= self.hold_window_epochs <= 100_000
        ):
            raise RewardFailure("INVALID_HOLD_WINDOW_EPOCHS")
        units(self.hold_cap_q12)
        if (
            type(self.window_bonus_rate_bps) is not int
            or not 0 <= self.window_bonus_rate_bps <= 100_000
        ):
            raise RewardFailure("INVALID_BONUS_RATE_BPS")
        if (
            type(self.zero_bonus_sold_bps) is not int
            or not 1 <= self.zero_bonus_sold_bps <= 10_000
        ):
            raise RewardFailure("INVALID_ZERO_BONUS_SOLD_BPS")
        if type(self.treasury_sinks) is not tuple or len(self.treasury_sinks) > 16:
            raise RewardFailure("INVALID_TREASURY_SINKS")
        seen_hk = set()
        for s in self.treasury_sinks:
            if type(s) is not PinnedTreasurySink or s.hotkey in seen_hk:
                raise RewardFailure("INVALID_TREASURY_SINKS")
            seen_hk.add(s.hotkey)
        if (
            type(self.treasury_stake_cap_rao) is not int
            or self.treasury_stake_cap_rao < 0
        ):
            raise RewardFailure("INVALID_TREASURY_STAKE_CAP")
        if type(self.excluded_coldkeys) is not frozenset:
            raise RewardFailure("INVALID_EXCLUDED_COLDKEYS")
        for ck in self.excluded_coldkeys:
            identifier(ck)
        if type(self.enforce_king_u16_floor) is not bool:
            raise RewardFailure("INVALID_KING_FLOOR_FLAG")


@dataclass(frozen=True)
class WaterfallEpochObservation:
    """Per-epoch chain and emission observations for the 4-rung waterfall."""

    epoch_miner_emission_rao: int | None = None
    treasury_current_stake_rao: int | None = None
    staked_by_coldkey: dict[str, int] | None = None
    crown_credits_by_coldkey: dict[str, tuple[int, str]] | None = None
    bonus_credits_by_coldkey: dict[str, tuple[int, str]] | None = None
    owner_coldkey: str | None = None
    owner_hotkeys: tuple[str, ...] = ()
    last_epoch_block: int | None = None
    settled_intent_epochs: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.epoch_miner_emission_rao is not None and (
            type(self.epoch_miner_emission_rao) is not int
            or self.epoch_miner_emission_rao < 0
        ):
            raise RewardFailure("INVALID_EMISSION_RAO")
        if self.treasury_current_stake_rao is not None and (
            type(self.treasury_current_stake_rao) is not int
            or self.treasury_current_stake_rao < 0
        ):
            raise RewardFailure("INVALID_TREASURY_STAKE_RAO")
        if (
            self.staked_by_coldkey is not None
            and type(self.staked_by_coldkey) is not dict
        ):
            raise RewardFailure("INVALID_STAKE_OBSERVATION")
        if (
            self.crown_credits_by_coldkey is not None
            and type(self.crown_credits_by_coldkey) is not dict
        ):
            raise RewardFailure("INVALID_CREDIT_OBSERVATION")
        if (
            self.bonus_credits_by_coldkey is not None
            and type(self.bonus_credits_by_coldkey) is not dict
        ):
            raise RewardFailure("INVALID_BONUS_CREDIT_OBSERVATION")
        if self.owner_coldkey is not None:
            identifier(self.owner_coldkey)
        if type(self.owner_hotkeys) is not tuple:
            raise RewardFailure("INVALID_OWNER_HOTKEYS")
        for hk in self.owner_hotkeys:
            identifier(hk)
        if self.last_epoch_block is not None and (
            type(self.last_epoch_block) is not int or self.last_epoch_block < 0
        ):
            raise RewardFailure("INVALID_LAST_EPOCH_BLOCK")
        if type(self.settled_intent_epochs) is not tuple or any(
            type(ep) is not int or ep < 0 for ep in self.settled_intent_epochs
        ):
            raise RewardFailure("INVALID_SETTLED_INTENT_EPOCHS")


from .winner_decay import Winner, WinnerPolicy, winner_fraction


def epoch_bonus_rate(
    worst_sold_ratio: Fraction,
    window_bonus_rate_bps: int,
    zero_bonus_sold_bps: int,
    hold_window_epochs: int,
) -> Fraction:
    """Exact per-epoch bonus rate `r_epoch(S_c)`:
    - At `S_c == 0`: `window_bonus_rate_bps / (10_000 * hold_window_epochs)`
    - Linearly decays to `0` at `S_c >= zero_bonus_sold_bps / 10_000`."""
    if window_bonus_rate_bps == 0 or worst_sold_ratio < 0:
        return Fraction(0)
    cutoff = Fraction(zero_bonus_sold_bps, 10_000)
    if worst_sold_ratio >= cutoff:
        return Fraction(0)
    full_per_epoch = Fraction(window_bonus_rate_bps, 10_000 * hold_window_epochs)
    retention_factor = Fraction(1) - (worst_sold_ratio / cutoff)
    return full_per_epoch * retention_factor


def _parse_rao_str(value: object) -> int:
    if type(value) is not str or not value or not value.isdigit():
        raise RewardFailure("HOLD_LEDGER_CORRUPTED")
    return int(value)


class HoldBonusLedger:
    """Per-epoch ledger of cumulative Challenge crown earnings `C(c, e)`,
    cumulative Hold Bonus earnings `H(c, e)`, and live Subnet-116 staked balances `B(c, e)`
    for point-in-time sold ratio and non-compounding principal evaluation.

    Anti-masking & 360-block snapshot cadence (intentional design choice):
    - Stake is sampled once per `360`-block epoch at the finalized snapshot block, tracking
      `external_stake_rao` and `last_observed_stake_rao` so pre-existing, bought, or
      transferred-in Alpha never masks selling mined rewards (`retained_mined_rao =
      max(0, B(c, e) - external_stake_rao)`).
    - Intra-epoch sell-and-rebuy within a single 360-block epoch intentionally requires
      buying back into the SN116 AMM pool before the epoch snapshot block — paying round-trip
      SN116 AMM swap fees and slippage while restoring full Alpha liquidity to the pool.

    Supports both direct SQLite files (`*.sqlite3`) and atomic JSONL files (`*.jsonl`,
    loaded into an in-memory SQLite engine and persisted atomically only on writes so
    `preview` and refused cycles never create or touch disk files)."""

    def __init__(self, path: Path | str):
        raw_path = str(path)
        self.path = Path(raw_path)
        self._jsonl_mode = raw_path != ":memory:" and raw_path.endswith(".jsonl")
        self._suppress_flush = False
        self._batch_mutated = False
        if self._jsonl_mode and self.path.is_symlink():
            raise RewardFailure("HOLD_LEDGER_SYMLINK_REFUSED")
        self._conn = sqlite3.connect(":memory:" if self._jsonl_mode else str(self.path))
        if not self._jsonl_mode:
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        with self._conn:
            self._conn.execute("""CREATE TABLE IF NOT EXISTS hold_coldkey_totals_v1 (
                    coldkey TEXT PRIMARY KEY,
                    cumulative_earned_rao TEXT NOT NULL,
                    cumulative_bonus_rao TEXT NOT NULL DEFAULT '0',
                    external_stake_rao TEXT NOT NULL DEFAULT '0',
                    last_observed_stake_rao TEXT DEFAULT NULL,
                    preferred_hotkey TEXT NOT NULL,
                    updated_epoch INTEGER NOT NULL
                )""")
            totals_cols = {
                r[1]
                for r in self._conn.execute(
                    "PRAGMA table_info(hold_coldkey_totals_v1)"
                ).fetchall()
            }
            if "cumulative_bonus_rao" not in totals_cols:
                self._conn.execute(
                    "ALTER TABLE hold_coldkey_totals_v1 ADD COLUMN cumulative_bonus_rao TEXT NOT NULL DEFAULT '0'"
                )
            if "external_stake_rao" not in totals_cols:
                self._conn.execute(
                    "ALTER TABLE hold_coldkey_totals_v1 ADD COLUMN external_stake_rao TEXT NOT NULL DEFAULT '0'"
                )
            if "last_observed_stake_rao" not in totals_cols:
                self._conn.execute(
                    "ALTER TABLE hold_coldkey_totals_v1 ADD COLUMN last_observed_stake_rao TEXT DEFAULT NULL"
                )
            self._conn.execute("""CREATE TABLE IF NOT EXISTS hold_epoch_credits_v1 (
                    epoch INTEGER NOT NULL,
                    coldkey TEXT NOT NULL,
                    earned_delta_rao TEXT NOT NULL,
                    hotkey TEXT NOT NULL,
                    PRIMARY KEY(epoch, coldkey)
                )""")
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS hold_epoch_bonus_credits_v1 (
                    epoch INTEGER NOT NULL,
                    coldkey TEXT NOT NULL,
                    bonus_delta_rao TEXT NOT NULL,
                    hotkey TEXT NOT NULL,
                    PRIMARY KEY(epoch, coldkey)
                )"""
            )
            self._conn.execute("""CREATE TABLE IF NOT EXISTS hold_epoch_samples_v1 (
                    epoch INTEGER NOT NULL,
                    coldkey TEXT NOT NULL,
                    staked_rao TEXT NOT NULL,
                    external_stake_rao TEXT NOT NULL DEFAULT '0',
                    cumulative_earned_rao TEXT NOT NULL,
                    cumulative_bonus_rao TEXT NOT NULL DEFAULT '0',
                    sold_rao TEXT NOT NULL,
                    PRIMARY KEY(epoch, coldkey)
                )""")
            samples_cols = {
                r[1]
                for r in self._conn.execute(
                    "PRAGMA table_info(hold_epoch_samples_v1)"
                ).fetchall()
            }
            if "cumulative_bonus_rao" not in samples_cols:
                self._conn.execute(
                    "ALTER TABLE hold_epoch_samples_v1 ADD COLUMN cumulative_bonus_rao TEXT NOT NULL DEFAULT '0'"
                )
            if "external_stake_rao" not in samples_cols:
                self._conn.execute(
                    "ALTER TABLE hold_epoch_samples_v1 ADD COLUMN external_stake_rao TEXT NOT NULL DEFAULT '0'"
                )
            for (ck,) in self._conn.execute(
                "SELECT coldkey FROM hold_coldkey_totals_v1 WHERE last_observed_stake_rao IS NULL"
            ).fetchall():
                latest_sample = self._conn.execute(
                    """SELECT staked_rao, external_stake_rao
                       FROM hold_epoch_samples_v1
                       WHERE coldkey=?
                       ORDER BY epoch DESC LIMIT 1""",
                    (ck,),
                ).fetchone()
                if latest_sample is not None:
                    self._conn.execute(
                        """UPDATE hold_coldkey_totals_v1
                           SET last_observed_stake_rao=?, external_stake_rao=?
                           WHERE coldkey=?""",
                        (latest_sample[0], latest_sample[1], ck),
                    )
            self._conn.execute("""CREATE TABLE IF NOT EXISTS hold_epoch_emissions_v1 (
                    epoch INTEGER PRIMARY KEY,
                    emission_rao TEXT NOT NULL
                )""")
            self._conn.execute("""CREATE TABLE IF NOT EXISTS hold_settled_intents_v1 (
                    intent_epoch INTEGER PRIMARY KEY
                )""")
        if self._jsonl_mode and self.path.exists():
            self._load_jsonl()

    def _compute_external_stake_at(
        self,
        coldkey: str,
        epoch: int,
        staked_rao: int,
        cur_issued_rao: int,
    ) -> int:
        """Compute `external_stake_rao` for `coldkey` at `epoch` given current on-chain
        stake `staked_rao` and cumulative protocol-issued rewards `cur_issued_rao`."""
        if cur_issued_rao <= 0:
            return staked_rao
        prev_row = self._conn.execute(
            """SELECT staked_rao, external_stake_rao, cumulative_earned_rao, cumulative_bonus_rao
               FROM hold_epoch_samples_v1
               WHERE coldkey=? AND epoch < ?
               ORDER BY epoch DESC LIMIT 1""",
            (coldkey, epoch),
        ).fetchone()
        if prev_row is None:
            return max(0, staked_rao - cur_issued_rao)
        prev_staked = int(prev_row[0])
        prev_external = int(prev_row[1])
        prev_issued = int(prev_row[2]) + int(prev_row[3])
        delta_issued_rao = max(0, cur_issued_rao - prev_issued)
        if staked_rao > prev_staked + delta_issued_rao:
            return prev_external + (staked_rao - (prev_staked + delta_issued_rao))
        return prev_external

    def coldkey_stake_tracking(self, coldkey: str) -> tuple[int, int | None]:
        """Return `(external_stake_rao, last_observed_stake_rao)` for `coldkey`."""
        row = self._conn.execute(
            "SELECT external_stake_rao, last_observed_stake_rao FROM hold_coldkey_totals_v1 WHERE coldkey=?",
            (coldkey,),
        ).fetchone()
        if row is None:
            return 0, None
        return int(row[0]), (None if row[1] is None else int(row[1]))

    def _load_jsonl(self) -> None:
        if self.path.is_symlink() or not self.path.is_file():
            raise RewardFailure("HOLD_LEDGER_CORRUPTED")
        self._suppress_flush = True
        try:
            text = self.path.read_text(encoding="utf-8")
            req_sample_keys = {
                "kind",
                "epoch",
                "coldkey",
                "staked_rao",
                "cumulative_earned_rao",
                "cumulative_bonus_rao",
                "sold_rao",
            }
            opt_sample_keys = {"external_stake_rao", "last_observed_stake_rao"}
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if type(entry) is not dict:
                    raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                kind = entry.get("kind")
                if kind == "crown_credit.v1":
                    if set(entry) != {
                        "kind",
                        "epoch",
                        "coldkey",
                        "earned_delta_rao",
                        "hotkey",
                    }:
                        raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    self.record_crown_earnings(
                        entry["epoch"],
                        {
                            entry["coldkey"]: (
                                _parse_rao_str(entry["earned_delta_rao"]),
                                entry["hotkey"],
                            )
                        },
                    )
                elif kind == "bonus_credit.v1":
                    if set(entry) != {
                        "kind",
                        "epoch",
                        "coldkey",
                        "bonus_delta_rao",
                        "hotkey",
                    }:
                        raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    self.record_bonus_earnings(
                        entry["epoch"],
                        {
                            entry["coldkey"]: (
                                _parse_rao_str(entry["bonus_delta_rao"]),
                                entry["hotkey"],
                            )
                        },
                    )
                elif kind == "stake_sample.v1":
                    entry_keys = set(entry)
                    if not (
                        req_sample_keys
                        <= entry_keys
                        <= (req_sample_keys | opt_sample_keys)
                    ):
                        raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    ep = entry["epoch"]
                    ck = entry["coldkey"]
                    if type(ep) is not int or ep < 0:
                        raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    identifier(ck)
                    staked = _parse_rao_str(entry["staked_rao"])
                    earned = _parse_rao_str(entry["cumulative_earned_rao"])
                    bonus = _parse_rao_str(entry["cumulative_bonus_rao"])
                    sold = _parse_rao_str(entry["sold_rao"])
                    if "last_observed_stake_rao" in entry and (
                        _parse_rao_str(entry["last_observed_stake_rao"]) != staked
                    ):
                        raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    total_issued = earned + bonus
                    if earned == 0 and bonus > 0:
                        raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    cur = self._conn.execute(
                        "SELECT cumulative_earned_rao, cumulative_bonus_rao FROM hold_coldkey_totals_v1 WHERE coldkey=?",
                        (ck,),
                    ).fetchone()
                    cur_earned = int(cur[0]) if cur is not None else 0
                    cur_bonus = int(cur[1]) if cur is not None else 0
                    if cur_earned != earned or cur_bonus != bonus:
                        raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    expected_ext = self._compute_external_stake_at(
                        ck, ep, staked, total_issued
                    )
                    if "external_stake_rao" in entry:
                        external = _parse_rao_str(entry["external_stake_rao"])
                        if external != expected_ext:
                            raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    else:
                        # Backward-compatible load for legacy JSONL rows without external_stake_rao
                        expected_retained = max(0, staked - expected_ext)
                        if sold == total_issued - min(expected_retained, total_issued):
                            external = expected_ext
                        elif sold == total_issued - min(staked, total_issued):
                            external = 0
                        else:
                            raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    retained = max(0, staked - external)
                    if sold != total_issued - min(retained, total_issued):
                        raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    with self._conn:
                        self._conn.execute(
                            """INSERT INTO hold_epoch_samples_v1
                               (epoch, coldkey, staked_rao, external_stake_rao,
                                cumulative_earned_rao, cumulative_bonus_rao, sold_rao)
                               VALUES (?,?,?,?,?,?,?)""",
                            (
                                ep,
                                ck,
                                str(staked),
                                str(external),
                                str(earned),
                                str(bonus),
                                str(sold),
                            ),
                        )
                        self._conn.execute(
                            """INSERT INTO hold_coldkey_totals_v1
                               (coldkey, cumulative_earned_rao, cumulative_bonus_rao,
                                external_stake_rao, last_observed_stake_rao, preferred_hotkey, updated_epoch)
                               VALUES (?, ?, ?, ?, ?, '', ?)
                               ON CONFLICT(coldkey) DO UPDATE SET
                                 external_stake_rao=excluded.external_stake_rao,
                                 last_observed_stake_rao=excluded.last_observed_stake_rao,
                                 updated_epoch=MAX(hold_coldkey_totals_v1.updated_epoch, excluded.updated_epoch)""",
                            (
                                ck,
                                str(earned),
                                str(bonus),
                                str(external),
                                str(staked),
                                ep,
                            ),
                        )
                elif kind == "epoch_emission.v1":
                    if set(entry) != {"kind", "epoch", "epoch_miner_emission_rao"}:
                        raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    self.record_epoch_emission(
                        entry["epoch"],
                        _parse_rao_str(entry["epoch_miner_emission_rao"]),
                    )
                elif kind == "settled_intent.v1":
                    if set(entry) != {"kind", "intent_epoch"}:
                        raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    si_epoch = entry["intent_epoch"]
                    if type(si_epoch) is not int or si_epoch < 0:
                        raise RewardFailure("HOLD_LEDGER_CORRUPTED")
                    self.record_settled_intents((si_epoch,))
                else:
                    raise RewardFailure("HOLD_LEDGER_CORRUPTED")
        except RewardFailure:
            self._conn.close()
            raise
        except Exception:  # noqa: BLE001 - closed JSONL validation error
            self._conn.close()
            raise RewardFailure("HOLD_LEDGER_CORRUPTED") from None
        finally:
            self._suppress_flush = False
            self._batch_mutated = False

    def _flush_jsonl(self) -> None:
        if not self._jsonl_mode:
            return
        if self._suppress_flush:
            self._batch_mutated = True
            return
        if self.path.is_symlink():
            raise RewardFailure("HOLD_LEDGER_SYMLINK_REFUSED")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        epoch_rows = self._conn.execute("""SELECT epoch FROM hold_epoch_credits_v1
               UNION SELECT epoch FROM hold_epoch_bonus_credits_v1
               UNION SELECT epoch FROM hold_epoch_samples_v1
               UNION SELECT epoch FROM hold_epoch_emissions_v1
               UNION SELECT intent_epoch AS epoch FROM hold_settled_intents_v1
               ORDER BY epoch ASC""").fetchall()
        lines: list[str] = []
        for (ep,) in epoch_rows:
            for ck, delta_s, hk in self._conn.execute(
                "SELECT coldkey, earned_delta_rao, hotkey FROM hold_epoch_credits_v1 WHERE epoch=? ORDER BY coldkey",
                (ep,),
            ).fetchall():
                lines.append(
                    json.dumps(
                        {
                            "kind": "crown_credit.v1",
                            "epoch": ep,
                            "coldkey": ck,
                            "earned_delta_rao": delta_s,
                            "hotkey": hk,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
            for ck, delta_s, hk in self._conn.execute(
                "SELECT coldkey, bonus_delta_rao, hotkey FROM hold_epoch_bonus_credits_v1 WHERE epoch=? ORDER BY coldkey",
                (ep,),
            ).fetchall():
                lines.append(
                    json.dumps(
                        {
                            "kind": "bonus_credit.v1",
                            "epoch": ep,
                            "coldkey": ck,
                            "bonus_delta_rao": delta_s,
                            "hotkey": hk,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
            for (
                ck,
                staked_s,
                external_s,
                earned_s,
                bonus_s,
                sold_s,
            ) in self._conn.execute(
                """SELECT coldkey, staked_rao, external_stake_rao,
                          cumulative_earned_rao, cumulative_bonus_rao, sold_rao
                   FROM hold_epoch_samples_v1 WHERE epoch=? ORDER BY coldkey""",
                (ep,),
            ).fetchall():
                lines.append(
                    json.dumps(
                        {
                            "kind": "stake_sample.v1",
                            "epoch": ep,
                            "coldkey": ck,
                            "staked_rao": staked_s,
                            "external_stake_rao": external_s,
                            "last_observed_stake_rao": staked_s,
                            "cumulative_earned_rao": earned_s,
                            "cumulative_bonus_rao": bonus_s,
                            "sold_rao": sold_s,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
            em_row = self._conn.execute(
                "SELECT emission_rao FROM hold_epoch_emissions_v1 WHERE epoch=?",
                (ep,),
            ).fetchone()
            if em_row is not None:
                lines.append(
                    json.dumps(
                        {
                            "kind": "epoch_emission.v1",
                            "epoch": ep,
                            "epoch_miner_emission_rao": em_row[0],
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
            si_row = self._conn.execute(
                "SELECT intent_epoch FROM hold_settled_intents_v1 WHERE intent_epoch=?",
                (ep,),
            ).fetchone()
            if si_row is not None:
                lines.append(
                    json.dumps(
                        {
                            "kind": "settled_intent.v1",
                            "intent_epoch": int(si_row[0]),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
        payload = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
        fd, tmp_name = tempfile.mkstemp(
            prefix=".hold_bonus_ledger.", dir=str(self.path.parent)
        )
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, payload)
            os.fsync(fd)
            os.close(fd)
            fd = -1
            os.replace(tmp_name, self.path)
        except BaseException:
            if fd != -1:
                os.close(fd)
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def batch(self):
        """Coalesce multiple ledger mutations into a single atomic JSONL flush."""
        prev_suppress = self._suppress_flush
        prev_mutated = self._batch_mutated
        self._suppress_flush = True
        self._batch_mutated = False
        succeeded = False
        try:
            yield
            succeeded = True
        finally:
            mutated = self._batch_mutated
            self._suppress_flush = prev_suppress
            if succeeded:
                if not prev_suppress and mutated:
                    self._flush_jsonl()
                    self._batch_mutated = False
                else:
                    self._batch_mutated = prev_mutated or mutated
            else:
                self._batch_mutated = prev_mutated

    def settled_intent_epochs(self) -> frozenset[int]:
        """Return all `intent_epoch` values already credited into this ledger."""
        rows = self._conn.execute(
            "SELECT intent_epoch FROM hold_settled_intents_v1 ORDER BY intent_epoch ASC"
        ).fetchall()
        return frozenset(int(r[0]) for r in rows)

    def record_settled_intents(self, intent_epochs: Iterable[int]) -> None:
        """Idempotently record `intent_epoch`s whose settled payouts were credited."""
        cleaned: list[int] = []
        for ep in intent_epochs:
            if type(ep) is not int or ep < 0:
                raise RewardFailure("INVALID_EPOCH")
            cleaned.append(ep)
        if not cleaned:
            return
        mutated = False
        with self._conn:
            for ep in sorted(set(cleaned)):
                existing = self._conn.execute(
                    "SELECT 1 FROM hold_settled_intents_v1 WHERE intent_epoch=?",
                    (ep,),
                ).fetchone()
                if existing is not None:
                    continue
                self._conn.execute(
                    "INSERT INTO hold_settled_intents_v1(intent_epoch) VALUES (?)",
                    (ep,),
                )
                mutated = True
        if mutated:
            self._flush_jsonl()

    def record_epoch_emission(self, epoch: int, emission_rao: int) -> None:
        """Idempotently record observed `epoch_miner_emission_rao` for `epoch`."""
        if type(epoch) is not int or epoch < 0:
            raise RewardFailure("INVALID_EPOCH")
        if type(emission_rao) is not int or emission_rao < 0:
            raise RewardFailure("INVALID_EMISSION_RAO")
        mutated = False
        with self._conn:
            prev = self._conn.execute(
                "SELECT emission_rao FROM hold_epoch_emissions_v1 WHERE epoch=?",
                (epoch,),
            ).fetchone()
            if prev is not None:
                if int(prev[0]) != emission_rao:
                    raise RewardFailure("CONFLICTING_EPOCH_EMISSION")
                return
            self._conn.execute(
                "INSERT INTO hold_epoch_emissions_v1(epoch, emission_rao) VALUES (?,?)",
                (epoch, str(emission_rao)),
            )
            mutated = True
        if mutated:
            self._flush_jsonl()

    def epoch_emission(self, epoch: int) -> int | None:
        row = self._conn.execute(
            "SELECT emission_rao FROM hold_epoch_emissions_v1 WHERE epoch=?",
            (epoch,),
        ).fetchone()
        return None if row is None else int(row[0])

    def latest_recorded_epoch_before(self, epoch: int) -> int | None:
        """Return the highest epoch `< epoch` recorded in this ledger, or None."""
        row = self._conn.execute(
            """SELECT MAX(ep) FROM (
                   SELECT MAX(epoch) AS ep FROM hold_epoch_emissions_v1 WHERE epoch < ?
                   UNION ALL
                   SELECT MAX(epoch) AS ep FROM hold_epoch_credits_v1 WHERE epoch < ?
                   UNION ALL
                   SELECT MAX(epoch) AS ep FROM hold_epoch_bonus_credits_v1 WHERE epoch < ?
                   UNION ALL
                   SELECT MAX(epoch) AS ep FROM hold_epoch_samples_v1 WHERE epoch < ?
               )""",
            (epoch, epoch, epoch, epoch),
        ).fetchone()
        return None if row is None or row[0] is None else int(row[0])

    def record_crown_earnings(
        self,
        epoch: int,
        credits: dict[str, tuple[int, str]],
    ) -> None:
        """Idempotently record Challenge crown Alpha earned in `epoch`.
        `credits` maps `coldkey -> (earned_delta_rao, king_hotkey)`."""
        if type(epoch) is not int or epoch < 0:
            raise RewardFailure("INVALID_EPOCH")
        mutated = False
        with self._conn:
            for coldkey, (delta_rao, hotkey) in sorted(credits.items()):
                identifier(coldkey)
                identifier(hotkey)
                if type(delta_rao) is not int or delta_rao < 0:
                    raise RewardFailure("INVALID_EARNED_RAO")
                if delta_rao == 0:
                    continue
                existing = self._conn.execute(
                    "SELECT earned_delta_rao, hotkey FROM hold_epoch_credits_v1 WHERE epoch=? AND coldkey=?",
                    (epoch, coldkey),
                ).fetchone()
                if existing is not None:
                    if int(existing[0]) != delta_rao or existing[1] != hotkey:
                        raise RewardFailure("CONFLICTING_EPOCH_CREDIT")
                    continue
                cur = self._conn.execute(
                    "SELECT cumulative_earned_rao FROM hold_coldkey_totals_v1 WHERE coldkey=?",
                    (coldkey,),
                ).fetchone()
                prev_total = int(cur[0]) if cur is not None else 0
                new_total = prev_total + delta_rao
                self._conn.execute(
                    "INSERT INTO hold_epoch_credits_v1(epoch, coldkey, earned_delta_rao, hotkey) VALUES (?,?,?,?)",
                    (epoch, coldkey, str(delta_rao), hotkey),
                )
                self._conn.execute(
                    """INSERT INTO hold_coldkey_totals_v1(coldkey, cumulative_earned_rao, preferred_hotkey, updated_epoch)
                       VALUES (?,?,?,?)
                       ON CONFLICT(coldkey) DO UPDATE SET
                         cumulative_earned_rao=excluded.cumulative_earned_rao,
                         preferred_hotkey=excluded.preferred_hotkey,
                         updated_epoch=MAX(hold_coldkey_totals_v1.updated_epoch, excluded.updated_epoch)""",
                    (coldkey, str(new_total), hotkey, epoch),
                )
                mutated = True
        if mutated:
            self._flush_jsonl()

    def record_bonus_earnings(
        self,
        epoch: int,
        credits: dict[str, tuple[int, str]],
    ) -> None:
        """Idempotently record Miner Hold Bonus Alpha earned in `epoch`.
        `credits` maps `coldkey -> (bonus_delta_rao, recipient_hotkey)`."""
        if type(epoch) is not int or epoch < 0:
            raise RewardFailure("INVALID_EPOCH")
        mutated = False
        with self._conn:
            for coldkey, (delta_rao, hotkey) in sorted(credits.items()):
                identifier(coldkey)
                identifier(hotkey)
                if type(delta_rao) is not int or delta_rao < 0:
                    raise RewardFailure("INVALID_EARNED_RAO")
                if delta_rao == 0:
                    continue
                existing = self._conn.execute(
                    "SELECT bonus_delta_rao, hotkey FROM hold_epoch_bonus_credits_v1 WHERE epoch=? AND coldkey=?",
                    (epoch, coldkey),
                ).fetchone()
                if existing is not None:
                    if int(existing[0]) != delta_rao or existing[1] != hotkey:
                        raise RewardFailure("CONFLICTING_EPOCH_BONUS_CREDIT")
                    continue
                cur = self._conn.execute(
                    "SELECT cumulative_bonus_rao FROM hold_coldkey_totals_v1 WHERE coldkey=?",
                    (coldkey,),
                ).fetchone()
                prev_bonus = int(cur[0]) if cur is not None else 0
                new_bonus = prev_bonus + delta_rao
                self._conn.execute(
                    "INSERT INTO hold_epoch_bonus_credits_v1(epoch, coldkey, bonus_delta_rao, hotkey) VALUES (?,?,?,?)",
                    (epoch, coldkey, str(delta_rao), hotkey),
                )
                self._conn.execute(
                    """INSERT INTO hold_coldkey_totals_v1
                       (coldkey, cumulative_earned_rao, cumulative_bonus_rao, preferred_hotkey, updated_epoch)
                       VALUES (?, '0', ?, ?, ?)
                       ON CONFLICT(coldkey) DO UPDATE SET
                         cumulative_bonus_rao=excluded.cumulative_bonus_rao,
                         preferred_hotkey=excluded.preferred_hotkey,
                         updated_epoch=MAX(hold_coldkey_totals_v1.updated_epoch, excluded.updated_epoch)""",
                    (coldkey, str(new_bonus), hotkey, epoch),
                )
                mutated = True
        if mutated:
            self._flush_jsonl()

    def sample_epoch_stakes(
        self,
        epoch: int,
        staked_by_coldkey: dict[str, int],
    ) -> None:
        """Sample live Subnet-116 stake `B(c, epoch)` once per 360-block epoch.
        Tracks `external_stake_rao` and `last_observed_stake_rao` per coldkey so pre-existing,
        bought, or transferred-in Alpha never masks selling mined rewards (`retained_mined_rao =
        max(0, B - external_stake_rao)`)."""
        if type(epoch) is not int or epoch < 0:
            raise RewardFailure("INVALID_EPOCH")
        if type(staked_by_coldkey) is not dict:
            raise RewardFailure("INVALID_STAKE_OBSERVATION")
        for ck, staked_val in staked_by_coldkey.items():
            identifier(ck)
            if type(staked_val) is not int or staked_val < 0:
                raise RewardFailure("INVALID_STAKE_RAO")
        mutated = False
        with self._conn:
            totals_map = {
                ck: (int(earned_s), int(bonus_s), last_obs_s)
                for ck, earned_s, bonus_s, last_obs_s in self._conn.execute(
                    """SELECT coldkey, cumulative_earned_rao, cumulative_bonus_rao, last_observed_stake_rao
                       FROM hold_coldkey_totals_v1"""
                ).fetchall()
            }
            for ck, (earned_rao, _bonus_rao, _last_obs_s) in sorted(totals_map.items()):
                if earned_rao > 0 and ck not in staked_by_coldkey:
                    raise RewardFailure("MISSING_COLDKEY_STAKE_OBSERVATION")

            candidate_cks = sorted(
                {
                    ck
                    for ck, (earned_rao, _b, last_obs_s) in totals_map.items()
                    if earned_rao > 0
                    or (last_obs_s is not None and ck in staked_by_coldkey)
                }
                | {ck for ck, val in staked_by_coldkey.items() if val > 0}
            )
            for coldkey in candidate_cks:
                staked_rao = staked_by_coldkey[coldkey]
                earned_rao, bonus_rao, _last_obs_s = totals_map.get(
                    coldkey, (0, 0, None)
                )
                total_issued_rao = earned_rao + bonus_rao
                prev = self._conn.execute(
                    """SELECT staked_rao, external_stake_rao, cumulative_earned_rao, cumulative_bonus_rao
                       FROM hold_epoch_samples_v1 WHERE epoch=? AND coldkey=?""",
                    (epoch, coldkey),
                ).fetchone()
                external_rao = self._compute_external_stake_at(
                    coldkey, epoch, staked_rao, total_issued_rao
                )
                if prev is not None:
                    if (
                        int(prev[0]) != staked_rao
                        or int(prev[1]) != external_rao
                        or int(prev[2]) != earned_rao
                        or int(prev[3]) != bonus_rao
                    ):
                        raise RewardFailure("CONFLICTING_EPOCH_STAKE_SAMPLE")
                    continue
                retained_mined_rao = max(0, staked_rao - external_rao)
                held_total = min(retained_mined_rao, total_issued_rao)
                sold_rao = total_issued_rao - held_total
                self._conn.execute(
                    """INSERT INTO hold_epoch_samples_v1
                       (epoch, coldkey, staked_rao, external_stake_rao,
                        cumulative_earned_rao, cumulative_bonus_rao, sold_rao)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        epoch,
                        coldkey,
                        str(staked_rao),
                        str(external_rao),
                        str(earned_rao),
                        str(bonus_rao),
                        str(sold_rao),
                    ),
                )
                self._conn.execute(
                    """INSERT INTO hold_coldkey_totals_v1
                       (coldkey, cumulative_earned_rao, cumulative_bonus_rao,
                        external_stake_rao, last_observed_stake_rao, preferred_hotkey, updated_epoch)
                       VALUES (?, ?, ?, ?, ?, '', ?)
                       ON CONFLICT(coldkey) DO UPDATE SET
                         external_stake_rao=excluded.external_stake_rao,
                         last_observed_stake_rao=excluded.last_observed_stake_rao,
                         updated_epoch=MAX(hold_coldkey_totals_v1.updated_epoch, excluded.updated_epoch)""",
                    (
                        coldkey,
                        str(earned_rao),
                        str(bonus_rao),
                        str(external_rao),
                        str(staked_rao),
                        epoch,
                    ),
                )
                mutated = True
        if mutated:
            self._flush_jsonl()

    def tracked_coldkeys(self) -> list[tuple[str, int, str]]:
        """Return `(coldkey, cumulative_earned_rao, preferred_hotkey)` for all tracked winners."""
        rows = self._conn.execute(
            "SELECT coldkey, cumulative_earned_rao, preferred_hotkey FROM hold_coldkey_totals_v1 ORDER BY coldkey"
        ).fetchall()
        return [(r[0], int(r[1]), r[2]) for r in rows if int(r[1]) > 0]

    def tracked_coldkeys_preview(
        self,
        current_epoch: int,
        crown_credits_by_coldkey: dict[str, tuple[int, str]] | None = None,
        bonus_credits_by_coldkey: dict[str, tuple[int, str]] | None = None,
    ) -> list[tuple[str, int, str]]:
        """Read-only preview of `(coldkey, cumulative_earned_rao, preferred_hotkey)` at `current_epoch`,
        overlaying `crown_credits_by_coldkey` and `bonus_credits_by_coldkey` without mutating SQLite tables.
        """
        if type(current_epoch) is not int or current_epoch < 0:
            raise RewardFailure("INVALID_EPOCH")
        totals: dict[str, tuple[int, str]] = {}
        rows = self._conn.execute(
            "SELECT coldkey, cumulative_earned_rao, preferred_hotkey, updated_epoch FROM hold_coldkey_totals_v1"
        ).fetchall()
        for coldkey, earned_s, pref_hk, updated_epoch in rows:
            earned = int(earned_s)
            if int(updated_epoch) > current_epoch:
                later = self._conn.execute(
                    "SELECT earned_delta_rao FROM hold_epoch_credits_v1 WHERE coldkey=? AND epoch>?",
                    (coldkey, current_epoch),
                ).fetchall()
                earned -= sum(int(r[0]) for r in later)
            totals[coldkey] = (earned, pref_hk)
        if crown_credits_by_coldkey:
            for coldkey, (delta_rao, hotkey) in sorted(
                crown_credits_by_coldkey.items()
            ):
                identifier(coldkey)
                identifier(hotkey)
                if type(delta_rao) is not int or delta_rao < 0:
                    raise RewardFailure("INVALID_EARNED_RAO")
                if delta_rao == 0:
                    continue
                existing = self._conn.execute(
                    "SELECT earned_delta_rao, hotkey FROM hold_epoch_credits_v1 WHERE epoch=? AND coldkey=?",
                    (current_epoch, coldkey),
                ).fetchone()
                if existing is not None:
                    if int(existing[0]) != delta_rao or existing[1] != hotkey:
                        raise RewardFailure("CONFLICTING_EPOCH_CREDIT")
                    continue
                prev_earned = totals[coldkey][0] if coldkey in totals else 0
                totals[coldkey] = (prev_earned + delta_rao, hotkey)
        if bonus_credits_by_coldkey:
            for coldkey, (delta_rao, hotkey) in sorted(
                bonus_credits_by_coldkey.items()
            ):
                identifier(coldkey)
                identifier(hotkey)
                if type(delta_rao) is not int or delta_rao < 0:
                    raise RewardFailure("INVALID_EARNED_RAO")
                if delta_rao == 0:
                    continue
                existing_bonus = self._conn.execute(
                    "SELECT bonus_delta_rao, hotkey FROM hold_epoch_bonus_credits_v1 WHERE epoch=? AND coldkey=?",
                    (current_epoch, coldkey),
                ).fetchone()
                if existing_bonus is not None:
                    if (
                        int(existing_bonus[0]) != delta_rao
                        or existing_bonus[1] != hotkey
                    ):
                        raise RewardFailure("CONFLICTING_EPOCH_BONUS_CREDIT")
                    continue
                prev_earned = totals[coldkey][0] if coldkey in totals else 0
                totals[coldkey] = (prev_earned, hotkey)
        return [
            (ck, earned, hk)
            for ck, (earned, hk) in sorted(totals.items())
            if earned > 0
        ]

    def window_status(
        self,
        coldkey: str,
        current_epoch: int,
        window_epochs: int,
    ) -> tuple[int, Fraction] | None:
        """Return `(eligible_held_now_rao, worst_sold_ratio)` over `[current_epoch - window_epochs + 1, current_epoch]`.
        Requires a current-epoch sample (`epoch == current_epoch`) with `cumulative_earned_rao > 0`.
        """
        start_epoch = max(0, current_epoch - window_epochs + 1)
        rows = self._conn.execute(
            """SELECT epoch, staked_rao, external_stake_rao,
                      cumulative_earned_rao, cumulative_bonus_rao, sold_rao
               FROM hold_epoch_samples_v1
               WHERE coldkey=? AND epoch BETWEEN ? AND ?
               ORDER BY epoch ASC""",
            (coldkey, start_epoch, current_epoch),
        ).fetchall()
        if not rows or rows[-1][0] != current_epoch:
            return None
        cur_crown = int(rows[-1][3])
        if cur_crown <= 0:
            return None
        worst = Fraction(0)
        for _ep, _staked_s, _ext_s, earned_s, bonus_s, sold_s in rows:
            total_issued = int(earned_s) + int(bonus_s)
            sold = int(sold_s)
            if total_issued > 0:
                ratio = Fraction(sold, total_issued)
                worst = max(worst, ratio)
        cur_staked = int(rows[-1][1])
        cur_external = int(rows[-1][2])
        cur_bonus = int(rows[-1][4])
        cur_total_issued = cur_crown + cur_bonus
        retained_mined_now = max(0, cur_staked - cur_external)
        eligible_held_now = (
            (cur_crown * min(retained_mined_now, cur_total_issued)) // cur_total_issued
            if cur_total_issued > 0
            else 0
        )
        return eligible_held_now, worst

    def window_status_preview(
        self,
        coldkey: str,
        current_epoch: int,
        window_epochs: int,
        *,
        pending_credit_rao: int = 0,
        pending_credit_hotkey: str | None = None,
        pending_bonus_rao: int = 0,
        pending_bonus_hotkey: str | None = None,
        pending_stake_rao: int | None = None,
    ) -> tuple[int, Fraction] | None:
        """Read-only preview of `(eligible_held_now_rao, worst_sold_ratio)` at `current_epoch`,
        overlaying any pending current-epoch crown/bonus credits and stake sample in memory without mutating SQLite.
        """
        if type(current_epoch) is not int or current_epoch < 0:
            raise RewardFailure("INVALID_EPOCH")
        if type(pending_credit_rao) is not int or pending_credit_rao < 0:
            raise RewardFailure("INVALID_EARNED_RAO")
        if pending_credit_hotkey is not None:
            identifier(pending_credit_hotkey)
        if type(pending_bonus_rao) is not int or pending_bonus_rao < 0:
            raise RewardFailure("INVALID_EARNED_RAO")
        if pending_bonus_hotkey is not None:
            identifier(pending_bonus_hotkey)
        cur_row = self._conn.execute(
            "SELECT cumulative_earned_rao, cumulative_bonus_rao, updated_epoch FROM hold_coldkey_totals_v1 WHERE coldkey=?",
            (coldkey,),
        ).fetchone()
        cur_earned_total = int(cur_row[0]) if cur_row is not None else 0
        cur_bonus_total = int(cur_row[1]) if cur_row is not None else 0
        if cur_row is not None and int(cur_row[2]) > current_epoch:
            later = self._conn.execute(
                "SELECT earned_delta_rao FROM hold_epoch_credits_v1 WHERE coldkey=? AND epoch>?",
                (coldkey, current_epoch),
            ).fetchall()
            cur_earned_total -= sum(int(r[0]) for r in later)
            later_bonus = self._conn.execute(
                "SELECT bonus_delta_rao FROM hold_epoch_bonus_credits_v1 WHERE coldkey=? AND epoch>?",
                (coldkey, current_epoch),
            ).fetchall()
            cur_bonus_total -= sum(int(r[0]) for r in later_bonus)
        if pending_credit_rao > 0:
            existing = self._conn.execute(
                "SELECT earned_delta_rao, hotkey FROM hold_epoch_credits_v1 WHERE epoch=? AND coldkey=?",
                (current_epoch, coldkey),
            ).fetchone()
            if existing is not None:
                if int(existing[0]) != pending_credit_rao or (
                    pending_credit_hotkey is not None
                    and existing[1] != pending_credit_hotkey
                ):
                    raise RewardFailure("CONFLICTING_EPOCH_CREDIT")
            else:
                cur_earned_total += pending_credit_rao
        if pending_bonus_rao > 0:
            existing_bonus = self._conn.execute(
                "SELECT bonus_delta_rao, hotkey FROM hold_epoch_bonus_credits_v1 WHERE epoch=? AND coldkey=?",
                (current_epoch, coldkey),
            ).fetchone()
            if existing_bonus is not None:
                if int(existing_bonus[0]) != pending_bonus_rao or (
                    pending_bonus_hotkey is not None
                    and existing_bonus[1] != pending_bonus_hotkey
                ):
                    raise RewardFailure("CONFLICTING_EPOCH_BONUS_CREDIT")
            else:
                cur_bonus_total += pending_bonus_rao
        start_epoch = max(0, current_epoch - window_epochs + 1)
        rows = self._conn.execute(
            """SELECT epoch, staked_rao, external_stake_rao,
                      cumulative_earned_rao, cumulative_bonus_rao, sold_rao
               FROM hold_epoch_samples_v1
               WHERE coldkey=? AND epoch BETWEEN ? AND ?
               ORDER BY epoch ASC""",
            (coldkey, start_epoch, current_epoch),
        ).fetchall()
        effective_stake_rao = pending_stake_rao
        if (
            effective_stake_rao is None
            and (pending_credit_rao > 0 or pending_bonus_rao > 0)
            and rows
            and rows[-1][0] == current_epoch
        ):
            effective_stake_rao = int(rows[-1][1])
        if effective_stake_rao is not None:
            if type(effective_stake_rao) is not int or effective_stake_rao < 0:
                raise RewardFailure("INVALID_STAKE_RAO")
            if cur_earned_total <= 0:
                return None
            cur_total_issued = cur_earned_total + cur_bonus_total
            ext_now = self._compute_external_stake_at(
                coldkey, current_epoch, effective_stake_rao, cur_total_issued
            )
            retained_now = max(0, effective_stake_rao - ext_now)
            held_now = min(retained_now, cur_total_issued)
            sold_now = cur_total_issued - held_now
            cur_sample = (
                current_epoch,
                str(effective_stake_rao),
                str(ext_now),
                str(cur_earned_total),
                str(cur_bonus_total),
                str(sold_now),
            )
            effective_rows = [r for r in rows if r[0] < current_epoch] + [cur_sample]
        else:
            effective_rows = rows
        if not effective_rows or effective_rows[-1][0] != current_epoch:
            return None
        cur_crown = int(effective_rows[-1][3])
        if cur_crown <= 0:
            return None
        worst = Fraction(0)
        for _ep, _staked_s, _ext_s, earned_s, bonus_s, sold_s in effective_rows:
            total_issued = int(earned_s) + int(bonus_s)
            sold = int(sold_s)
            if total_issued > 0:
                ratio = Fraction(sold, total_issued)
                worst = max(worst, ratio)
        cur_staked = int(effective_rows[-1][1])
        cur_external = int(effective_rows[-1][2])
        cur_bonus = int(effective_rows[-1][4])
        cur_total_issued = cur_crown + cur_bonus
        retained_mined_now = max(0, cur_staked - cur_external)
        eligible_held_now = (
            (cur_crown * min(retained_mined_now, cur_total_issued)) // cur_total_issued
            if cur_total_issued > 0
            else 0
        )
        return eligible_held_now, worst


def _context_id(challenge_name: str) -> str:
    import hashlib

    return hashlib.sha256(
        f"carbon.testnet.winner.v1:{challenge_name}".encode()
    ).hexdigest()


def _holder_dict(p: Participant) -> dict:
    return {
        "hotkey": p.hotkey,
        "coldkey": p.coldkey,
        "registered_at": p.registered_at,
    }


def _resolve_coldkey_recipient(
    coldkey: str,
    preferred_hotkey: str,
    snapshot: MetagraphSnapshot,
    forbidden_hotkeys: set[str],
) -> Participant | None:
    """Resolve an active registered UID for `coldkey` on `snapshot`, preferring `preferred_hotkey`."""
    pref = snapshot.resolve(preferred_hotkey)
    if (
        pref is not None
        and pref.coldkey == coldkey
        and pref.hotkey not in forbidden_hotkeys
    ):
        return pref
    candidates = [
        p
        for p in snapshot.participants
        if p.coldkey == coldkey and p.hotkey not in forbidden_hotkeys
    ]
    if not candidates:
        return None
    # Deterministic lowest-UID tie-break if preferred_hotkey deregistered
    return min(candidates, key=lambda p: p.uid)


def compute_waterfall_targets(
    policy: WinnerPolicy,
    waterfall: WaterfallConfig,
    snapshot: MetagraphSnapshot,
    winners: dict[str, Winner],
    *,
    epoch: int,
    hold_ledger: HoldBonusLedger | None = None,
    epoch_miner_emission_rao: int | None = None,
    treasury_current_stake_rao: int | None = None,
    staked_by_coldkey: dict[str, int] | None = None,
    crown_credits_by_coldkey: dict[str, tuple[int, str]] | None = None,
    bonus_credits_by_coldkey: dict[str, tuple[int, str]] | None = None,
    owner_coldkey: str | None = None,
    owner_hotkeys: tuple[str, ...] = (),
    publisher_hotkey: str | None = None,
    canary_hotkeys: frozenset[str] = frozenset(),
) -> dict:
    """Compute one 360-block epoch's complete 4-rung waterfall in exact Q12 units:
      Rung 1: Active Challenge King(s) (`winners`)
      Rung 2: Miner Hold Bonus (`hold_bonus`, capped at `min(hold_cap_q12, decayed_from_active_kings_q12)`)
      Rung 3: Community Treasury Sink(s) (`treasury`, funded ONLY from unused active-King decay)
      Rung 4: UID 0 Burn (`burn`, receives all empty/excluded Challenge slots, `Q12 % N`, and unused decay)
    Total `sum(winners) + sum(hold_bonus) + sum(treasury) + burn == Q12` always."""
    if type(policy) is not WinnerPolicy:
        raise TypeError("a WinnerPolicy is required")
    if type(waterfall) is not WaterfallConfig:
        raise TypeError("a WaterfallConfig is required")
    if type(snapshot) is not MetagraphSnapshot:
        raise TypeError("a MetagraphSnapshot is required")
    unknown = set(winners) - set(policy.challenges)
    if unknown:
        raise RewardFailure("CHALLENGE_NOT_IN_POLICY")
    if policy.network == "finney" and owner_coldkey is None:
        raise RewardFailure("OWNER_COLDKEY_REQUIRED")
    if (
        hold_ledger is not None
        and waterfall.hold_cap_q12 > 0
        and waterfall.window_bonus_rate_bps > 0
        and epoch_miner_emission_rao is None
    ):
        raise RewardFailure("EMISSION_OBSERVATION_REQUIRED")

    registered = {p.hotkey: p for p in snapshot.participants}
    sink_hotkeys = {s.hotkey for s in waterfall.treasury_sinks}
    sink_coldkeys = {s.coldkey for s in waterfall.treasury_sinks}
    forbidden_hotkeys = set(owner_hotkeys) | set(canary_hotkeys) | sink_hotkeys
    if publisher_hotkey is not None:
        forbidden_hotkeys.add(publisher_hotkey)

    king_excluded_coldkeys = set(waterfall.excluded_coldkeys) | sink_coldkeys
    if owner_coldkey is not None and policy.network != "testnet":
        king_excluded_coldkeys.add(owner_coldkey)

    excluded_coldkeys = set(king_excluded_coldkeys)
    if owner_coldkey is not None:
        excluded_coldkeys.add(owner_coldkey)

    use_overlay = (
        crown_credits_by_coldkey is not None
        or bonus_credits_by_coldkey is not None
        or staked_by_coldkey is not None
    )
    tracked_overlay: list[tuple[str, int, str]] | None = None
    if hold_ledger is not None and use_overlay:
        tracked_overlay = hold_ledger.tracked_coldkeys_preview(
            epoch, crown_credits_by_coldkey, bonus_credits_by_coldkey
        )
        if staked_by_coldkey is not None:
            for coldkey, cum_earned, _pref_hk in tracked_overlay:
                if cum_earned <= 0:
                    continue
                if coldkey not in staked_by_coldkey:
                    raise RewardFailure("MISSING_COLDKEY_STAKE_OBSERVATION")
                staked_rao = staked_by_coldkey[coldkey]
                if type(staked_rao) is not int or staked_rao < 0:
                    raise RewardFailure("INVALID_STAKE_RAO")

    # ---------------- Rung 1: Active Challenge Kings ----------------
    raw_rows = []
    for challenge in policy.challenges:
        w = winners.get(challenge)
        member = registered.get(w.hotkey) if w is not None else None
        if (
            w is None
            or member is None
            or w.hotkey in forbidden_hotkeys
            or member.coldkey in king_excluded_coldkeys
        ):
            # Empty / un-won / excluded Challenge slot: burns directly to UID 0 (never funds Rung 2/3)
            raw_rows.append((challenge, 0, None, False))
            continue
        amt = policy.share * winner_fraction(w.clock_ms, snapshot.timestamp_ms) // Q12
        if amt > 0 and waterfall.enforce_king_u16_floor and amt < MIN_POSITIVE_U16_Q12:
            amt = min(policy.share, MIN_POSITIVE_U16_Q12)
        raw_rows.append((challenge, amt, member if amt > 0 else None, True))

    challenge_rows = []
    king_aggregate: dict[tuple[str, str, int], int] = {}
    king_total_q12 = 0
    decayed_from_active_kings_q12 = 0
    for challenge, earned, member, has_payable_king in raw_rows:
        holder = _holder_dict(member) if member is not None else None
        challenge_rows.append(
            {
                "context_id": _context_id(challenge),
                "allocated": policy.share,
                "earned": earned,
                "unearned": policy.share - earned,
                "holder": holder,
            }
        )
        if has_payable_king:
            decayed_from_active_kings_q12 += policy.share - earned
        if earned and member is not None:
            key = (member.hotkey, member.coldkey, member.registered_at)
            king_aggregate[key] = king_aggregate.get(key, 0) + earned
            king_total_q12 += earned

    if king_total_q12 + decayed_from_active_kings_q12 > Q12:
        raise RewardFailure("OVER_ALLOCATED")

    # ---------------- Rung 2: Miner Hold Bonus (Precedence over Treasury) ----------------
    bonus_aggregate: dict[tuple[str, str, int], int] = {}
    bonus_cap_q12 = min(waterfall.hold_cap_q12, decayed_from_active_kings_q12)
    if (
        bonus_cap_q12 > 0
        and waterfall.window_bonus_rate_bps > 0
        and hold_ledger is not None
        and epoch_miner_emission_rao is not None
        and epoch_miner_emission_rao > 0
    ):
        desired_by_key: dict[tuple[str, str, int], int] = {}
        tracked = (
            tracked_overlay
            if tracked_overlay is not None
            else hold_ledger.tracked_coldkeys()
        )
        for coldkey, _cum_earned, pref_hk in tracked:
            if coldkey in excluded_coldkeys:
                continue
            if use_overlay:
                credit_entry = (crown_credits_by_coldkey or {}).get(coldkey)
                bonus_entry = (bonus_credits_by_coldkey or {}).get(coldkey)
                status = hold_ledger.window_status_preview(
                    coldkey,
                    epoch,
                    waterfall.hold_window_epochs,
                    pending_credit_rao=(
                        credit_entry[0] if credit_entry is not None else 0
                    ),
                    pending_credit_hotkey=(
                        credit_entry[1] if credit_entry is not None else None
                    ),
                    pending_bonus_rao=bonus_entry[0] if bonus_entry is not None else 0,
                    pending_bonus_hotkey=(
                        bonus_entry[1] if bonus_entry is not None else None
                    ),
                    pending_stake_rao=(
                        staked_by_coldkey[coldkey]
                        if staked_by_coldkey is not None
                        else None
                    ),
                )
            else:
                status = hold_ledger.window_status(
                    coldkey, epoch, waterfall.hold_window_epochs
                )
            if status is None:
                continue
            eligible_held_rao, worst_sold = status
            if eligible_held_rao <= 0:
                continue
            rate = epoch_bonus_rate(
                worst_sold,
                waterfall.window_bonus_rate_bps,
                waterfall.zero_bonus_sold_bps,
                waterfall.hold_window_epochs,
            )
            if rate <= 0:
                continue
            recipient = _resolve_coldkey_recipient(
                coldkey, pref_hk, snapshot, forbidden_hotkeys
            )
            if recipient is None:
                continue
            target_alpha_rao = Fraction(eligible_held_rao) * rate
            desired_q12 = int((target_alpha_rao * Q12) // epoch_miner_emission_rao)
            if desired_q12 > 0:
                rkey = (recipient.hotkey, recipient.coldkey, recipient.registered_at)
                desired_by_key[rkey] = desired_by_key.get(rkey, 0) + desired_q12

        total_desired = sum(desired_by_key.values())
        if 0 < total_desired <= bonus_cap_q12:
            bonus_aggregate = dict(desired_by_key)
        elif total_desired > bonus_cap_q12:
            for rkey, w_q12 in sorted(desired_by_key.items()):
                scaled = (w_q12 * bonus_cap_q12) // total_desired
                if scaled > 0:
                    bonus_aggregate[rkey] = scaled

    bonus_total_q12 = sum(bonus_aggregate.values())
    residual_after_bonus_q12 = decayed_from_active_kings_q12 - bonus_total_q12

    # ---------------- Rung 3: Community Treasury Sink(s) ----------------
    treasury_aggregate: dict[tuple[str, str, int], int] = {}
    if (
        residual_after_bonus_q12 > 0
        and waterfall.treasury_sinks
        and waterfall.treasury_stake_cap_rao > 0
        and treasury_current_stake_rao is not None
        and 0 <= treasury_current_stake_rao < waterfall.treasury_stake_cap_rao
    ):
        active_sinks: list[Participant] = []
        for pin in waterfall.treasury_sinks:
            p = registered.get(pin.hotkey)
            if (
                p is not None
                and (p.coldkey, p.registered_at) == (pin.coldkey, pin.registered_at)
                and p.hotkey != publisher_hotkey
                and p.hotkey not in owner_hotkeys
            ):
                active_sinks.append(p)
        if active_sinks:
            per_sink = residual_after_bonus_q12 // len(active_sinks)
            if per_sink > 0:
                for p in active_sinks:
                    skey = (p.hotkey, p.coldkey, p.registered_at)
                    treasury_aggregate[skey] = (
                        treasury_aggregate.get(skey, 0) + per_sink
                    )

    treasury_total_q12 = sum(treasury_aggregate.values())

    # ---------------- Rung 4: UID 0 Burn (Fallback + Integer Dust) ----------------
    burn_q12 = Q12 - king_total_q12 - bonus_total_q12 - treasury_total_q12
    if burn_q12 < 0:
        raise RewardFailure("OVER_ALLOCATED")

    def _fmt(agg: dict[tuple[str, str, int], int]) -> list:
        return [
            [dict(zip(("hotkey", "coldkey", "registered_at"), k)), v]
            for k, v in sorted(agg.items())
        ]

    return {
        "challenges": challenge_rows,
        "winners": _fmt(king_aggregate),
        "hold_bonus": _fmt(bonus_aggregate),
        "treasury": _fmt(treasury_aggregate),
        "burn": burn_q12,
    }
