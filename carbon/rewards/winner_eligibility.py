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
from .winner_decay import FULL_RESET, Winner

LEDGER_SCHEMA = "carbon.rewards.testnet-winner-ledger.v2"
LEGACY_LEDGER_SCHEMA = "carbon.rewards.testnet-winner-ledger.v1"
FINAL = "FINAL_IMPROVEMENT"
FIRST = "FIRST_INCUMBENT"
#: A contender that beat the incumbent on one shared bank key beyond the
#: Challenge's measured rebuild noise (KOTH-TAKEOVER-RULE-01).
BANK = "BANK_IMPROVEMENT"


#: The incumbent reasons a lean (direct-receiver) pool store may carry, as
#: `bank_promotion` names them. Only the sealed-exam crown is payable, and only
#: on a testnet policy.
DEVELOPMENT_REASON = "bank_comparison_development"
SEALED_TESTNET_REASON = "bank_comparison_sealed_testnet"


class WinnerIdentityFailure(RewardFailure):
    """The snapshot and ledger cannot establish a promotion's miner identity."""


class WinnerCutoverFailure(RewardFailure):
    """An existing winner meets an unchecked first incumbent under a baseline."""


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
    if incumbent.get("reason") == "bank_comparison_development":
        raise RewardFailure("PROMOTION_DEVELOPMENT_ONLY")
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


def lean_promotion(store):
    """The current incumbent's promotion in a lean (direct-receiver) pool
    store, or None. Read only; the miner and the incumbent it beat come from
    the store's own incumbent events.

    The development reason is never payable (`PROMOTION_DEVELOPMENT_ONLY`).
    A sealed-exam crown carries its reason into the promotion, and `decide`
    pays it only under a testnet policy.
    """
    incumbent = store.incumbent()
    if incumbent is None:
        return None
    _lean_reason(incumbent.get("reason"))
    model_id = incumbent["model_id"]
    events = [
        e["body"]
        for e in store.events("incumbent")
        if e["body"].get("model_id") == model_id
    ]
    if not events:
        raise RewardFailure("PROMOTION_UNRECORDED")
    return _lean_crown(
        store, model_id, incumbent.get("reason"), events[-1].get("previous")
    )


def _lean_reason(reason):
    if reason == DEVELOPMENT_REASON:
        raise RewardFailure("PROMOTION_DEVELOPMENT_ONLY")
    if reason != SEALED_TESTNET_REASON:
        raise RewardFailure("PROMOTION_REASON_UNKNOWN")


def lean_crowns_since(store, recorded_model_id):
    """Every crown the lean pool store's own incumbent journal holds after ``recorded_model_id`` (the Challenge's last
    ledger record), oldest first, ending with the current incumbent exactly as `lean_promotion` reads it. Each item is
    ``{"promotion": ..., "journal": {"sequence": n, "event_digest": "sha256:...", "at_ms": t}}``: the door's own
    event that crowned it and when (``at_ms`` None when the store does not say). The replay is record integrity; pay
    stays the crown holder at each update, and a crown the loop missed is clocked when it actually won (the issuer).

    Crowns can land between two observations (6 Nov: Ribbed Bracket crowned twice and the ledger never saw the middle
    king). The publisher replays each one in the store's sequence order, each with its own previous king and reason,
    so `decide` still checks every predecessor link. A gap is bridged only from this journal: if the recorded king is
    not in it, or its last crown is not the current incumbent, nothing is replayed
    (``PREDECESSOR_NOT_IN_DOOR_JOURNAL`` / ``DOOR_JOURNAL_DISAGREES_WITH_INCUMBENT``). Read only.
    """
    import hashlib

    current = lean_promotion(store)
    if current is None:
        return []
    events = list(store.events("incumbent"))
    bodies = [e["body"] for e in events]
    times = _event_times(store, events)

    def journal(i):
        body = json.dumps(bodies[i], sort_keys=True, separators=(",", ":")).encode()
        return {
            "sequence": events[i].get("sequence"),
            "event_digest": "sha256:" + hashlib.sha256(body).hexdigest(),
            "at_ms": times[i],
        }

    recorded = [
        i for i, b in enumerate(bodies) if b.get("model_id") == recorded_model_id
    ]
    if not recorded:
        raise RewardFailure("PREDECESSOR_NOT_IN_DOOR_JOURNAL")
    # a withdrawn crown (model_id None) is not a king; the next crown names previous None (a first incumbent)
    crowns = [
        i
        for i in range(recorded[-1] + 1, len(bodies))
        if bodies[i].get("model_id") is not None
    ]
    if current["model_id"] == recorded_model_id and not crowns:
        return [{"promotion": current, "journal": journal(recorded[-1])}]
    if not crowns or bodies[crowns[-1]].get("model_id") != current["model_id"]:
        raise RewardFailure("DOOR_JOURNAL_DISAGREES_WITH_INCUMBENT")
    out = []
    for i in crowns[:-1]:
        body = bodies[i]
        _lean_reason(body.get("reason"))
        promotion = _lean_crown(
            store, body["model_id"], body["reason"], body.get("previous")
        )
        out.append({"promotion": promotion, "journal": journal(i)})
    return [*out, {"promotion": current, "journal": journal(crowns[-1])}]


def _event_times(store, events):
    """Each incumbent event's door time in ms (``events.at``, the store's clock in seconds), or None. Read only: the
    event's own ``at`` when it carries one, else the store's events table by sequence (the pool store's ``events()``
    returns no time, and its file is a grading path, so it is read here rather than changed).
    """

    def ms(value):
        if type(value) in (int, float) and value >= 0:
            return round(value * 1000)
        return None

    if all("at" in e for e in events):
        return [ms(e["at"]) for e in events]
    by_sequence = {}
    db = getattr(store, "db", None)
    if db is not None:
        try:
            with db() as connection:
                by_sequence = dict(
                    connection.execute(
                        "SELECT sequence, at FROM events WHERE kind='incumbent'"
                    ).fetchall()
                )
        except Exception:  # noqa: BLE001 - no time = the replay refuses by name
            by_sequence = {}
    return [ms(by_sequence.get(e.get("sequence"))) for e in events]


#: Promotion fields that are evidence for `decide`, not the crown's identity: a recorded king whose evidence is read
#: differently later (an averaged crown read as verified once that reader existed) is still the same crown.
EVIDENCE_FIELDS = frozenset({"repeat_verified", "evaluation_pack_digests"})


def same_crown(recorded, promotion):
    """Whether a recorded promotion and a fresh read of it are the same crown (evidence fields aside)."""

    def identity(p):
        return {k: v for k, v in p.items() if k not in EVIDENCE_FIELDS}

    return identity(recorded) == identity(promotion)


def _averaged_crown(store, model_id):
    """Whether ``model_id``'s crown was decided by the averaged decision: a CHALLENGER decision (a crown_decision row,
    or a paused contender's crown_pause_resolved code ``CHALLENGER:<reason>``) AND an averaged record that scored N of
    N, filed for it on the SAME evaluation key. Read only, from the pool store's operations (its file
    is a grading path, so it is read here rather than changed); a store that cannot say reads False.
    """
    db = getattr(store, "db", None)
    if db is None:
        return False
    try:
        with db() as connection:
            rows = connection.execute(
                "SELECT kind, body FROM operations WHERE kind IN "
                "('crown_decision.v1', 'crown_pause_resolved.v1', 'crown_average.v1')"
            ).fetchall()
    except Exception:  # noqa: BLE001 - unreadable = unverified
        return False
    decided, averaged = set(), set()
    for kind, raw in rows:
        try:
            body = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if type(body) is not dict or body.get("submission_id") != model_id:
            continue
        key = body.get("evaluation_key")
        if type(key) is not str:
            continue
        # bank_promotion.CHALLENGER: the outcome only a verified crown change returns
        if kind == "crown_decision.v1" and body.get("outcome") == "CHALLENGER":
            decided.add(key)
        elif kind == "crown_pause_resolved.v1" and str(body.get("code")).startswith(
            "CHALLENGER:"
        ):
            # a paused contender decided by the sweep files its outcome here, never as a crown_decision row
            # (crown_pause_sweep: f"{outcome}:{reason}"; the doors' d3e6bab9 writes no crown_decision.v1 at all)
            decided.add(key)
        elif kind == "crown_average.v1" and _all_admissible(body.get("private")):
            averaged.add(key)
    return bool(decided & averaged)


def _all_admissible(private):
    """An averaged record that scored N of N (counts only; no value read): its registered ``n``, n seeds and n totals,
    and no per-seed statuses (`crown_average.run_average` files those only when a rebuild was not admissible). The
    host-fault second build is not a field: `run_average` returns CHALLENGER only after it agreed, so the CHALLENGER
    decision on the same key carries it (Carbon Validator, 6 Nov 09:31)."""
    if type(private) is not dict or "statuses" in private:
        return False
    n = private.get("n")
    return (
        type(n) is int
        and n > 0
        and type(private.get("seeds")) is list
        and type(private.get("totals")) is list
        and len(private["seeds"]) == n
        and len(private["totals"]) == n
    )


def _crown_pack_digests(store, model_id):
    """The evaluation pack digest(s) ``model_id``'s private evaluation was graded on (a single binding's
    ``evaluation_pack_digest``, or a set binding's per-batch ones), sorted. Read only from the pool store's
    operations; a store that cannot say reads [] (an unreadable crown is never qualified).
    """
    db = getattr(store, "db", None)
    if db is None:
        return []
    try:
        with db() as connection:
            rows = connection.execute(
                "SELECT body FROM operations WHERE kind = 'private_evaluation.v1'"
            ).fetchall()
    except Exception:  # noqa: BLE001 - unreadable = unqualified
        return []
    found = set()
    for (raw,) in rows:
        try:
            body = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if type(body) is not dict or body.get("submission_id") != model_id:
            continue
        evidence = body.get("evidence")
        if type(evidence) is not dict:
            continue
        digests = [evidence.get("evaluation_pack_digest")] + [
            b.get("evaluation_pack_digest")
            for b in (evidence.get("batches") or [])
            if type(b) is dict
        ]
        found.update(d for d in digests if type(d) is str and d)
    return sorted(found)


def _lean_crown(store, model_id, reason, previous):
    """One crown of a lean pool store as a promotion: the king, its miner and the king it beat."""
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
        "incumbent_reason": reason,
    }
    # Evidence for a non-testnet policy's sealed-crown qualification (`decide`); kept out of the crown identity.
    packs = (
        _crown_pack_digests(store, model_id) if reason == SEALED_TESTNET_REASON else []
    )
    if packs:
        promotion["evaluation_pack_digests"] = packs
    if previous is None:
        return {**promotion, "kind": FIRST}
    # A crown change applies only after the contender's grade was verified (`bank_promotion.consider_private`):
    # by the repeat, which files a mark beside the grade, or (OWNER-CROWN-GRADE-REPEAT-01, crowns since averaging) by
    # the N=10 averaged decision, which files its record and the CHALLENGER outcome. Either is the evidence a
    # self-improvement reset (`decide`) trusts, with no threshold of its own.
    marks = getattr(store, "repeat_marks", None)
    if marks is not None:
        promotion["repeat_verified"] = len(marks(model_id)) > 0 or _averaged_crown(
            store, model_id
        )
    return {**promotion, "kind": BANK}


def decide(
    policy, challenge, promotion, previous_record, coldkeys, now_ms, crowned_ms=None
):
    """The ledger record for a newly observed `promotion`: its eligibility,
    the reason, and the clock it pays from. `coldkeys` maps hotkeys to
    coldkeys (from the snapshot); `previous_record` is the Challenge's last
    ledger record, or None. V2 freezes the observed winner coldkey so later
    comparisons do not depend on the predecessor remaining registered."""
    winner_coldkey = coldkeys.get(promotion["hotkey"])
    if winner_coldkey is not None and (
        type(winner_coldkey) is not str or not winner_coldkey
    ):
        raise WinnerIdentityFailure("WINNER_IDENTITY_UNAVAILABLE")
    base = {
        "schema": LEDGER_SCHEMA,
        "challenge": challenge,
        "policy": policy.digest,
        "promotion": promotion,
        "observed_ms": now_ms,
        "winner_coldkey": winner_coldkey,
    }

    # A crown the loop missed (a replay) starts its clock when it won at the door, never after the snapshot; every
    # other crown when it is first observed (``now_ms``).
    crown_ms = now_ms if crowned_ms is None else min(crowned_ms, now_ms)

    def record(eligible, reason, clock_ms=crown_ms):
        return {**base, "eligible": eligible, "reason": reason, "clock_ms": clock_ms}

    if promotion.get("incumbent_reason") == SEALED_TESTNET_REASON and (
        policy.network != "testnet"
    ):
        # A sealed-exam crown is paid on testnet only until qualification
        # (invariant 5): any other network's policy refuses it, UNLESS the
        # policy names the Challenge in its owner qualification
        # (`winner_decay.QUALIFIED_SEALED`) AND every pack the crown was graded
        # on is one that qualification names (a re-seal is never paid silently).
        qualified = getattr(policy, "qualified_packs", None)
        packs = None if qualified is None else qualified(challenge)
        if packs is None:
            return record(False, "sealed_crown_testnet_only")
        graded = promotion.get("evaluation_pack_digests")
        if type(graded) is not list or not graded or not set(graded) <= packs:
            return record(False, "sealed_crown_pack_not_qualified")

    def same_miner(previous_hotkey):
        if promotion["hotkey"] == previous_hotkey:
            return True
        if winner_coldkey is None:
            raise WinnerIdentityFailure("WINNER_IDENTITY_UNAVAILABLE")
        if (
            previous_record is not None
            and previous_record.get("schema") == LEDGER_SCHEMA
        ):
            previous_coldkey = previous_record.get("winner_coldkey")
        elif (
            previous_record is None
            or previous_record.get("schema") == LEGACY_LEDGER_SCHEMA
        ):
            # v1 did not freeze this association; only a still-present old
            # hotkey can supply it. Historical records are not rewritten.
            previous_coldkey = coldkeys.get(previous_hotkey)
        else:
            raise WinnerIdentityFailure("PREDECESSOR_IDENTITY_UNAVAILABLE")
        if type(previous_coldkey) is not str or not previous_coldkey:
            raise WinnerIdentityFailure("PREDECESSOR_IDENTITY_UNAVAILABLE")
        return winner_coldkey == previous_coldkey

    def no_reset():
        # A same miner keeps its old clock; an ineligible predecessor cannot
        # gain eligibility from a new deployment or a self-improvement.
        keep = previous_record is not None and previous_record["eligible"]
        return record(
            keep,
            "same_miner_no_reset",
            previous_record["clock_ms"] if keep else now_ms,
        )

    def self_improvement():
        # OWNER-KING-SELF-IMPROVEMENT-RESET-01: a repeat-confirmed crown by the same miner
        # beating its own king restarts the clock. What qualifies is the KOTH rule alone
        # (the grade beat the king's by more than the registered rebuild noise AND was
        # repeat-verified); this adds no threshold. A bank promotion without its repeat
        # mark is refused, leaving the ledger unchanged (fail closed). An ineligible
        # predecessor cannot gain eligibility this way.
        if promotion["kind"] != BANK:
            return no_reset()
        if promotion.get("repeat_verified") is not True:
            raise RewardFailure("SELF_IMPROVEMENT_UNVERIFIED")
        if previous_record is None or not previous_record["eligible"]:
            return no_reset()
        return record(True, "self_improvement_reset")

    if promotion["kind"] == FIRST:
        if policy.baseline(challenge) is not None:
            if previous_record is not None:
                # The candidate has not beaten the registered baseline, and
                # authority does not define what happens to the old winner
                # across this deployment cutover. Leave the ledger unchanged.
                raise WinnerCutoverFailure("BASELINE_CUTOVER_UNRESOLVED")
            return record(False, "baseline_registered_first_incumbent_unchecked")
        if previous_record is not None and same_miner(
            previous_record["promotion"]["hotkey"]
        ):
            return no_reset()
        return record(True, "first_incumbent_no_baseline")
    if promotion["kind"] not in (FINAL, BANK):
        return record(False, "promotion_kind_unknown")
    if promotion["kind"] == FINAL and promotion["nomination_overdue"]:
        return record(False, "nomination_on_overdue_pool")
    previous_hotkey = promotion["previous_hotkey"]
    if previous_record is not None and (
        previous_record["promotion"]["model_id"] != promotion["previous"]
        or previous_record["promotion"]["hotkey"] != previous_hotkey
    ):
        raise WinnerIdentityFailure("PREDECESSOR_RECORD_MISMATCH")
    if same_miner(previous_hotkey):
        factor = policy.self_improvement_factor
        if factor is None:
            # A king beating himself: the better model is the incumbent, the
            # clock does not reset (KOTH-TAKEOVER-RULE-01 §2).
            return no_reset()
        if factor != FULL_RESET:
            raise RewardFailure("SELF_IMPROVEMENT_FACTOR_UNKNOWN")
        return self_improvement()
    return record(
        True, "final_improvement" if promotion["kind"] == FINAL else "bank_improvement"
    )


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

    def observe(
        self,
        policy,
        challenge,
        promotion,
        coldkeys,
        now_ms,
        journal=None,
        crowned_ms=None,
    ):
        """The Challenge's current record, recording `promotion` first if it
        is new. None when the Challenge has no incumbent. ``journal`` (the door
        event that crowned it, from a replay) is stored beside the decision; it
        never enters the decision."""
        if promotion is None:
            return None
        mine = self.records(challenge)
        for found in mine:
            if found["promotion"]["model_id"] == promotion["model_id"]:
                return found
        previous = mine[-1] if mine else None
        record = decide(
            policy, challenge, promotion, previous, coldkeys, now_ms, crowned_ms
        )
        if journal is not None:
            record = {**record, "journal": journal}
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
