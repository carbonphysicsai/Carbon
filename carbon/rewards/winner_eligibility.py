"""Who a Challenge's testnet weight goes to (VALIDATOR-14;
OWNER-TESTNET-WEIGHTS-01).

The winner is the Challenge validator's own incumbent, never a ranking of
scores (invariant 7.7). This module turns the validator's promotions into the
`Winner` that `winner_decay` pays. Each promotion is recorded once, in an
append-only ledger, at the finalized-chain time it is first observed; that
time starts the winner's 24 hours.

A promotion is **eligible** only when:
- its kind is allowed:
  - a decided `IMPROVEMENT` final on a fresh, consumed set;
  - or the first-incumbent rule, while the policy has no public baseline for
    the Challenge (testnet now, §2b). Once a baseline is registered, a first
    incumbent is not eligible until the validator compares it against that
    baseline (fail closed);
- the final's nomination score was not taken on an overdue pool version. The
  Test Lead's ruling: overdue scores never enter a promotion claim;
- for the **same miner** (the hotkey or coldkey of the incumbent it beat),
  the promotion never resets the clock until checking the adopted
  self-improvement factor is built. The miner keeps its previous clock, so a
  tweak of its own winner earns nothing new.

An ineligible promotion of another miner pays nobody: the Challenge's share
burns while it holds. At payment time a winner whose hotkey is not in the
metagraph snapshot is paid nothing either; its share burns.

Graphite development identities are never registered hotkeys, so they never
reach payment.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from .core import RewardFailure
from .winner_decay import Winner

LEDGER_SCHEMA = "carbon.rewards.testnet-winner-ledger.v1"
FINAL = "FINAL_IMPROVEMENT"
FIRST = "FIRST_INCUMBENT"


def battery_promotion(target):
    """The current incumbent's promotion in a battery validator, or None.

    Read only. The promotion's kind, the miner and the incumbent it beat come
    from the validator's own state: its incumbent event and, for a final, the
    decided promotable final with that challenger and that incumbent.
    """
    store = target.store
    incumbent = store.incumbent()
    if incumbent is None:
        return None
    model_id = incumbent["model_id"]
    events = [
        e["body"]
        for e in store.events("incumbent")
        if e["body"].get("model_id") == model_id
    ]
    if not events:
        raise RewardFailure("PROMOTION_UNRECORDED")
    previous = events[-1].get("previous")
    row = store.submission(model_id)
    promotion = {
        "model_id": model_id,
        "hotkey": row["hotkey"],
        "previous": previous,
        "previous_hotkey": (
            None if previous is None else store.submission(previous)["hotkey"]
        ),
        "recipe_digest": row["binding"].get("recipe_digest"),
        "contract_digest": row["binding"].get("contract_digest"),
        "rule_digest": target.identities()["rule_digest"],
    }
    if previous is None:
        return {**promotion, "kind": FIRST}
    for (final_id,) in target._finals_for(model_id):
        final = store.final(final_id)
        outcome = final["outcome"] or {}
        if (
            final["state"] == "DECIDED"
            and outcome.get("promotable")
            and final["incumbent"] == previous
        ):
            version = final["frozen"]["screening"]["pool_version"]
            overdue = any(
                e["body"].get("version") == version
                for e in store.events("rotation_overdue")
            )
            return {
                **promotion,
                "kind": FINAL,
                "final_id": final_id,
                "fresh_set": final["finalist"],
                "nomination_pool_version": version,
                "nomination_overdue": overdue,
            }
    raise RewardFailure("PROMOTION_FINAL_NOT_FOUND")


def decide(policy, challenge, promotion, previous_record, coldkeys, now_ms):
    """The ledger record for a newly observed `promotion`: its eligibility,
    the reason, and the clock it pays from. `coldkeys` maps hotkeys to
    coldkeys (from the snapshot); `previous_record` is the Challenge's last
    ledger record, or None."""
    base = {
        "schema": LEDGER_SCHEMA,
        "challenge": challenge,
        "policy": policy.digest,
        "promotion": promotion,
        "observed_ms": now_ms,
    }

    def record(eligible, reason, clock_ms=now_ms):
        return {**base, "eligible": eligible, "reason": reason, "clock_ms": clock_ms}

    if promotion["kind"] == FIRST:
        if policy.baseline(challenge) is not None:
            return record(False, "baseline_registered_first_incumbent_unchecked")
        return record(True, "first_incumbent_no_baseline")
    if promotion["kind"] != FINAL:
        return record(False, "promotion_kind_unknown")
    if promotion["nomination_overdue"]:
        return record(False, "nomination_on_overdue_pool")
    previous_hotkey = promotion["previous_hotkey"]
    same = promotion["hotkey"] == previous_hotkey or (
        previous_hotkey is not None
        and coldkeys.get(promotion["hotkey"]) is not None
        and coldkeys.get(promotion["hotkey"]) == coldkeys.get(previous_hotkey)
    )
    if same:
        # No reset: the same miner keeps its old clock, or, when its earlier
        # win paid nothing, still earns nothing new. Checking the adopted
        # factor against a measured gain is not built yet, so even a set
        # factor resets nothing (fail closed).
        keep = previous_record is not None and previous_record["eligible"]
        return record(
            keep,
            "same_miner_no_reset",
            previous_record["clock_ms"] if keep else now_ms,
        )
    return record(True, "final_improvement")


class WinnerLedger:
    """Append-only, owner-only JSONL of observed promotions per Challenge. A
    promotion is recorded once; later observations reuse its record."""

    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists():
            info = os.lstat(self.path)
            if stat.S_ISLNK(info.st_mode) or info.st_mode & 0o077:
                raise RewardFailure("WINNER_LEDGER_NOT_OWNER_ONLY")

    def records(self, challenge=None):
        if not self.path.exists():
            return []
        found = [json.loads(line) for line in self.path.read_bytes().splitlines()]
        return [r for r in found if challenge is None or r["challenge"] == challenge]

    def _append(self, record):
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "ab") as stream:
            stream.write(json.dumps(record, sort_keys=True).encode() + b"\n")
            stream.flush()
            os.fsync(stream.fileno())

    def observe(self, policy, challenge, promotion, coldkeys, now_ms):
        """The Challenge's current record, recording `promotion` first if it
        is new. None when the Challenge has no incumbent."""
        if promotion is None:
            return None
        mine = self.records(challenge)
        for found in mine:
            if found["promotion"]["model_id"] == promotion["model_id"]:
                return found
        previous = mine[-1] if mine else None
        record = decide(policy, challenge, promotion, previous, coldkeys, now_ms)
        self._append(record)
        return record


def payable(record, registered_hotkeys):
    """The `Winner` a ledger record pays this epoch, or None: ineligible, or
    its hotkey is not in the snapshot."""
    if record is None or not record["eligible"]:
        return None
    hotkey = record["promotion"]["hotkey"]
    if hotkey not in registered_hotkeys:
        return None
    return Winner(hotkey, record["clock_ms"])
