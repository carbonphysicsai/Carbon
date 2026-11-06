"""Winner-weight publication, once per epoch (VALIDATOR-14;
OWNER-TESTNET-WEIGHTS-01; OWNER-WEIGHTS-AUTHORITY-01).

SECURITY-SENSITIVE (AGENTS.md §13): this publishes weights. It is not
SECURITY_QUALIFIED, and it needs the dedicated review that every chain path
gets.

**Networks.** It runs on any network a registered weight policy names
(`winner_decay.NETWORK_AUTHORITIES`): testnet 567, and mainnet `finney` once
its policy (netuid, launch Challenges) is registered and its operator
configured. The rule is the same on both; nothing here is an authority
block (OWNER-WEIGHTS-AUTHORITY-01, its hold lifted by
OWNER-WEIGHTS-HOLD-LIFT-01). What differs by network:
- the intent's stage and maturity labels (`STAGES`);
- a winner whose coldkey is the subnet owner's is paid on testnet, so that
  Carbon's own miners exercise winning, and refused on mainnet. A winner
  whose hotkey is an owner hotkey is refused on both: that weight burns.

What it publishes, each epoch:
- **The targets.** `winner_decay.epoch_targets` over the registered policy:
  1/N per Challenge, all of the share to the winner for 24 hours, then half
  every 24 hours, and everything unpaid burned to UID 0.
- **The winners.** Each Challenge's winner comes from its validator's own
  promotion, recorded once in the `WinnerLedger` (`winner_eligibility`). A
  winner whose hotkey is not in the snapshot is paid nothing.

**The authority** is one standing approval, the owner's record together with
the policy digest (`StandingAuthorization`), in place of OD-4a's per-request
approval. That standing approval was decided by the owner in
OWNER-TESTNET-WEIGHTS-01 §1.

The checks are inherited unchanged from the shared publisher
(`chain.publisher.VerifiedWeightPublisher`):
- a fresh snapshot and recompilation before signing;
- recipients and runtime may not drift;
- the integer-row guard;
- journalled dispatch;
- no-resend reconciliation;
- the owner-associated-winner and self-winner refusals.

This module adds:
- the authorization's block window;
- the authorized network and netuid, and burn UID 0;
- the policy digest;
- **at most one publication per epoch** (360 blocks).

An intent is issued from the ledger at one snapshot. It is resolved again at
publish time against the fresh snapshot, and refused if its targets changed
(for example across a halving boundary); the next epoch reissues.

Signing is external: the operator's wallet is opened by path, and starting the
signer is a human step. No miner key is involved.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from carbon.chain import ChainContext
from carbon.chain.publication import PublicationFailure
from carbon.chain.publisher import VerifiedWeightPublisher
from carbon.development_testnet.model import DevelopmentTestnetProfile
from carbon.transport.models import digest

from .core import Q12
from .ledger import encode
from .winner_decay import (
    WinnerPolicy,
    epoch_targets,
    network_authorized,
    winner_fraction,
)
from .winner_eligibility import (
    BANK,
    FINAL,
    FIRST,
    WinnerCutoverFailure,
    WinnerIdentityFailure,
    WinnerLedger,
    payable,
)

INTENT_SCHEMA = "carbon.rewards.testnet-winner-intent.v1"
AUTHORITY = "OWNER-TESTNET-WEIGHTS-01"
NETUID = 567
BURN_UID = 0
#: Each network's intent identity prefix, stage and maturity label. The
#: maturity names where the authority comes from; it claims no
#: qualification.
STAGES = {
    "testnet": ("testnet-winner", "PUBLIC_TESTNET_DEVELOPMENT", "DEVELOPMENT_ONLY"),
    "finney": ("mainnet-winner", "PUBLIC_MAINNET", "MAINNET_OWNER_AUTHORIZED"),
}


class WinnerPublicationRefused(PublicationFailure):
    """A typed refusal; its code carries no provider, wallet or input text."""


def _refuse(code):
    raise WinnerPublicationRefused(code)


def _hex64(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


@dataclass(frozen=True)
class StandingAuthorization:
    """The owner's standing approval for this publisher, as the operator
    configures it. It is never inferred from a wallet file."""

    authority_record_digest: str  # sha256 hex of the owner's decision file
    policy_digest: str
    context: ChainContext
    publisher_hotkey: str
    expected_runtime_spec: int
    valid_from_block: int
    valid_through_block: int
    authority: str = AUTHORITY

    def __post_init__(self):
        if (
            not _hex64(self.authority_record_digest)
            or type(self.policy_digest) is not str
            or not self.policy_digest.startswith("sha256:")
            or type(self.context) is not ChainContext
            or not network_authorized(
                self.context.network, self.context.netuid, self.authority
            )
            or type(self.publisher_hotkey) is not str
            or not self.publisher_hotkey
            or type(self.expected_runtime_spec) is not int
            or self.expected_runtime_spec <= 0
            or type(self.valid_from_block) is not int
            or type(self.valid_through_block) is not int
            or not 0 <= self.valid_from_block <= self.valid_through_block
        ):
            _refuse("INVALID_STANDING_AUTHORIZATION")


@dataclass(frozen=True)
class TestnetWinnerWeightRef:
    identity: str
    digest: str

    def __post_init__(self):
        if type(self.identity) is not str or not _hex64(self.digest):
            _refuse("INVALID_WINNER_INTENT_REFERENCE")


def _context_id(challenge):
    return hashlib.sha256(challenge.encode()).hexdigest()


class TestnetWinnerIntentIssuer:
    """Issues one epoch's intent from the winner ledger.

    `sources` maps each policy Challenge to a callable returning its current
    promotion (`winner_eligibility.battery_promotion(target)`), or None while
    the Challenge has no serving validator. A Challenge without a source burns
    its share.

    `replays` (optional) maps a Challenge to a callable that, given the model id
    of the Challenge's last ledger record, returns every crown since it, oldest
    first, ending with the current promotion, each with its door journal event
    (`winner_eligibility.lean_crowns_since`). With it, a crown that came and
    went between two observations is still recorded, in the door's order, before
    the current one; without it only the current promotion is observed.
    `record` observes on cycles that publish nothing new (RECONCILE_PENDING, a
    re-issue inside the epoch), so no crown waits for the next intent.
    """

    def __init__(self, receipts, authorization, policy, ledger, sources, replays=None):
        from carbon.transport.store import ReceiptJournal

        if type(receipts) is not ReceiptJournal:
            _refuse("RECEIPT_JOURNAL_REQUIRED")
        if type(authorization) is not StandingAuthorization:
            _refuse("STANDING_AUTHORIZATION_REQUIRED")
        if (
            type(policy) is not WinnerPolicy
            or policy.digest != authorization.policy_digest
        ):
            _refuse("POLICY_NOT_AUTHORIZED")
        context = authorization.context
        if (policy.network, policy.netuid, policy.authority) != (
            context.network,
            context.netuid,
            authorization.authority,
        ):
            _refuse("POLICY_NOT_FOR_THIS_NETWORK")
        if receipts.context != authorization.context:
            _refuse("PUBLICATION_CONTEXT_REQUIRED")
        if type(ledger) is not WinnerLedger:
            _refuse("WINNER_LEDGER_REQUIRED")
        if set(sources) - set(policy.challenges):
            _refuse("SOURCE_OUTSIDE_POLICY")
        self.receipts, self.authorization = receipts, authorization
        self.policy, self.ledger, self.sources = policy, ledger, dict(sources)
        self.replays = dict(replays or {})
        if set(self.replays) - set(self.sources):
            _refuse("SOURCE_OUTSIDE_POLICY")
        self.prefix, self.stage, self.maturity = STAGES[context.network]
        #: The bounded development profile is testnet's only.
        self.profile = (
            DevelopmentTestnetProfile(
                authorization.context, authorization.expected_runtime_spec
            )
            if context.network == "testnet"
            else None
        )
        with receipts.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS testnet_winner_intent_v1 "
                "(identity TEXT PRIMARY KEY, digest TEXT NOT NULL, body TEXT NOT NULL)"
            )

    def epoch(self, snapshot):
        return snapshot.finalized_block // self.policy.cadence_blocks

    def _identity(self, snapshot):
        return f"{self.prefix}-{self.policy.version}-e{self.epoch(snapshot)}"

    def _promotion(self, challenge):
        if challenge not in self.sources:
            return None
        try:
            promotion = self.sources[challenge]()
            if promotion is not None and (
                type(promotion) is not dict
                or any(
                    type(promotion.get(key)) is not str or not promotion[key]
                    for key in ("model_id", "hotkey")
                )
                # A lean pool's second and later crowns are bank promotions (`lean_promotion`); `decide` handles
                # every kind listed here, and any other kind is refused.
                or promotion.get("kind") not in (FIRST, FINAL, BANK)
            ):
                _refuse("WINNER_SOURCE_UNAVAILABLE")
            return promotion
        except Exception:  # noqa: BLE001 - closed source failure, no stale fallback
            raise WinnerPublicationRefused("WINNER_SOURCE_UNAVAILABLE") from None

    #: Replay refusals passed through by name (the operator needs to know which); anything else is a closed
    #: WINNER_SOURCE_UNAVAILABLE, as for the current promotion.
    REPLAY_CODES = frozenset(
        {
            "PREDECESSOR_NOT_IN_DOOR_JOURNAL",
            "DOOR_JOURNAL_DISAGREES_WITH_INCUMBENT",
            "PROMOTION_DEVELOPMENT_ONLY",
            "PROMOTION_REASON_UNKNOWN",
            "CROWN_EVENT_TIME_MISSING",
        }
    )

    def _crowns(self, challenge, mine, promotion):
        """``(promotion, journal, crowned_ms)`` to observe, in order: every crown since the last record
        (``replays``), else the current one alone. ``crowned_ms`` is the door event time of a crown the loop missed
        (two or more since the last record), else None (clocked at observation)."""
        if not mine or challenge not in self.replays:
            return [(promotion, None, None)]
        try:
            crowns = self.replays[challenge](mine[-1]["promotion"]["model_id"])
        except Exception as failure:  # noqa: BLE001 - closed source failure
            code = getattr(failure, "code", None) or str(failure)
            _refuse(code if code in self.REPLAY_CODES else "WINNER_SOURCE_UNAVAILABLE")
        if (
            type(crowns) is not list
            or not crowns
            or any(
                type(c) is not dict
                or set(c) != {"promotion", "journal"}
                or type(c["promotion"]) is not dict
                or type(c["journal"]) is not dict
                for c in crowns
            )
            or crowns[-1]["promotion"] != promotion
            or any(
                any(
                    type(c["promotion"].get(k)) is not str or not c["promotion"][k]
                    for k in ("model_id", "hotkey")
                )
                or c["promotion"].get("kind") not in (FIRST, FINAL, BANK)
                for c in crowns
            )
        ):
            _refuse("WINNER_SOURCE_UNAVAILABLE")
        if len(crowns) == 1:
            # the usual cycle: one new crown, clocked when first observed
            return [(crowns[0]["promotion"], crowns[0]["journal"], None)]
        # crowns the loop missed: each clocked when it won at the door; one without a time refuses them all, before
        # anything is written
        if any(
            type(c["journal"].get("at_ms")) is not int or c["journal"]["at_ms"] < 0
            for c in crowns
        ):
            _refuse("CROWN_EVENT_TIME_MISSING")
        return [(c["promotion"], c["journal"], c["journal"]["at_ms"]) for c in crowns]

    def record(self, snapshot):
        """Record every crown since each Challenge's last ledger record, building no intent: the cycles that publish
        nothing new (RECONCILE_PENDING, a re-issue inside the epoch) still observe, so a crown that comes and goes
        between two intents is recorded in the door's order (record integrity only; pay stays the crown holder at each update). A gap
        refuses here, as in `issue`."""
        return self._records(snapshot, observe=True)

    def _records(self, snapshot, *, observe, preview=False):
        from .winner_eligibility import decide, same_crown

        coldkeys = {p.hotkey: p.coldkey for p in snapshot.participants}
        found = {}
        for challenge in self.policy.challenges:
            promotion = self._promotion(challenge)
            if promotion is None:
                found[challenge] = None
            else:
                mine = self.ledger.records(challenge)
                known = [
                    r
                    for r in mine
                    if r["promotion"]["model_id"] == promotion["model_id"]
                ]
                if known:
                    if not same_crown(known[0]["promotion"], promotion):
                        _refuse("TARGETS_CHANGED_REISSUE_NEXT_EPOCH")
                    found[challenge] = known[0]
                else:
                    try:
                        if observe:
                            # each crown since the last record, in the door's order, each with its own predecessor
                            for crown, journal, crowned_ms in self._crowns(
                                challenge, mine, promotion
                            ):
                                found[challenge] = self.ledger.observe(
                                    self.policy,
                                    challenge,
                                    crown,
                                    coldkeys,
                                    snapshot.timestamp_ms,
                                    journal,
                                    crowned_ms,
                                )
                        elif preview:
                            # the same replay in memory: nothing is written
                            seen = list(mine)
                            for crown, journal, crowned_ms in self._crowns(
                                challenge, mine, promotion
                            ):
                                again = [
                                    r
                                    for r in seen
                                    if r["promotion"]["model_id"] == crown["model_id"]
                                ]
                                record = (
                                    again[0]
                                    if again
                                    else decide(
                                        self.policy,
                                        challenge,
                                        crown,
                                        seen[-1] if seen else None,
                                        coldkeys,
                                        snapshot.timestamp_ms,
                                        crowned_ms,
                                    )
                                )
                                if not again:
                                    if journal is not None:
                                        record = {**record, "journal": journal}
                                    seen.append(record)
                                found[challenge] = record
                        else:
                            _refuse("TARGETS_CHANGED_REISSUE_NEXT_EPOCH")
                    except (WinnerIdentityFailure, WinnerCutoverFailure) as failure:
                        _refuse(str(failure))
        return found

    def _targets(self, snapshot, records):
        from carbon.challenge_validator.canary import is_canary

        registered = {p.hotkey: p for p in snapshot.participants}
        winners = {}
        for challenge, record in records.items():
            winner = payable(record, set(registered))
            # A registered canary is never weighted (CANARY-01): its share
            # burns, as a Challenge with no payable winner does.
            if winner is not None and not is_canary(winner.hotkey):
                winners[challenge] = winner
        paid = epoch_targets(self.policy, winners, snapshot.timestamp_ms)
        rows = []
        for challenge in self.policy.challenges:
            winner = winners.get(challenge)
            amount = (
                0
                if winner is None
                else self.policy.share
                * winner_fraction(winner.clock_ms, snapshot.timestamp_ms)
                // Q12
            )
            holder = None
            if amount:
                member = registered[winner.hotkey]
                holder = {
                    "hotkey": member.hotkey,
                    "coldkey": member.coldkey,
                    "registered_at": member.registered_at,
                }
            rows.append(
                {
                    "context_id": _context_id(challenge),
                    "allocated": self.policy.share,
                    "earned": amount,
                    "unearned": self.policy.share - amount,
                    "holder": holder,
                }
            )
        aggregate = {}
        for row in rows:
            if row["earned"]:
                h = row["holder"]
                key = (h["hotkey"], h["coldkey"], h["registered_at"])
                aggregate[key] = aggregate.get(key, 0) + row["earned"]
        winners_list = [
            [dict(zip(("hotkey", "coldkey", "registered_at"), key)), value]
            for key, value in sorted(aggregate.items())
        ]
        if sum(aggregate.values()) + paid["burn"] != Q12:
            _refuse("TARGETS_INCONSISTENT")
        return {"challenges": rows, "winners": winners_list, "burn": paid["burn"]}

    def _body(self, snapshot, records, targets):
        return encode(
            {
                "schema": INTENT_SCHEMA,
                "identity": self._identity(snapshot),
                "stage": self.stage,
                "maturity": self.maturity,
                "authority": self.authorization.authority,
                "authority_record_digest": self.authorization.authority_record_digest,
                "context": asdict(self.authorization.context),
                "runtime_spec": self.authorization.expected_runtime_spec,
                "mechanism_id": 0,
                "policy_digest": self.policy.digest,
                "epoch": self.epoch(snapshot),
                "ledger": {
                    c: None if r is None else digest(encode(r).encode())
                    for c, r in sorted(records.items())
                },
                "route": "DIRECT_WINNER_PLUS_BURN",
                "no_winner": not targets["winners"],
                "targets": targets,
            }
        )

    def issue(self, snapshot):
        """Observe promotions and issue this epoch's intent (idempotent per
        epoch: a second issue returns the stored reference)."""
        identity = self._identity(snapshot)
        with self.receipts.transaction() as db:
            row = db.execute(
                "SELECT digest FROM testnet_winner_intent_v1 WHERE identity=?",
                (identity,),
            ).fetchone()
        if row is not None:
            # the epoch's intent stands; a crown since it is still recorded now, not at the next epoch
            self.record(snapshot)
            return TestnetWinnerWeightRef(identity, row[0])
        records = self._records(snapshot, observe=True)
        body = self._body(snapshot, records, self._targets(snapshot, records))
        key = digest(body.encode())
        with self.receipts.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO testnet_winner_intent_v1 VALUES (?,?,?)",
                (identity, key, body),
            )
            stored = db.execute(
                "SELECT digest FROM testnet_winner_intent_v1 WHERE identity=?",
                (identity,),
            ).fetchone()
        return TestnetWinnerWeightRef(identity, stored[0])

    def resolve(self, ref, snapshot):
        if type(ref) is not TestnetWinnerWeightRef:
            _refuse("WINNER_INTENT_REQUIRED")
        with self.receipts.transaction() as db:
            row = db.execute(
                "SELECT digest,body FROM testnet_winner_intent_v1 WHERE identity=?",
                (ref.identity,),
            ).fetchone()
        if row is None or row[0] != ref.digest or digest(row[1].encode()) != ref.digest:
            _refuse("UNKNOWN_OR_ALTERED_WINNER_INTENT")
        body = json.loads(row[1])
        if (
            body["context"] != asdict(snapshot.context)
            or body["policy_digest"] != self.authorization.policy_digest
            or body["epoch"] != self.epoch(snapshot)
        ):
            _refuse("INTENT_NOT_FOR_THIS_EPOCH")
        records = self._records(snapshot, observe=False)
        if self._targets(snapshot, records) != body["targets"] or any(
            (None if r is None else digest(encode(r).encode())) != body["ledger"][c]
            for c, r in records.items()
        ):
            _refuse("TARGETS_CHANGED_REISSUE_NEXT_EPOCH")
        projection = {
            "schema": "carbon.rewards.testnet-winner-projection.v1",
            "maturity": body["maturity"],
            "route": "DIRECT_WINNER_PLUS_BURN",
            "context": body["context"],
            "targets": body["targets"],
        }
        return {"intent": body, "projection": projection}


class TestnetWinnerPublisher(VerifiedWeightPublisher):
    """The shared checked publisher, bound to the standing authorization."""

    def __init__(self, issuer, backend):
        if type(issuer) is not TestnetWinnerIntentIssuer:
            _refuse("WINNER_ISSUER_REQUIRED")
        authorization = issuer.authorization
        if backend.publisher != authorization.publisher_hotkey:
            _refuse("PUBLISHER_NOT_AUTHORIZED")
        self.authorization = authorization
        super().__init__(
            issuer,
            backend,
            issuer_type=TestnetWinnerIntentIssuer,
            intent_type=TestnetWinnerWeightRef,
            network=authorization.context.network,
            spec_version=authorization.expected_runtime_spec,
        )
        #: Testnet pays a winner whose coldkey is the subnet owner's (the
        #: owner: "remove that owner coldkey rule for testing"); mainnet keeps
        #: the refusal (OWNER-WEIGHTS-AUTHORITY-01).
        self.ALLOW_OWNER_COLDKEY_WINNER = authorization.context.network == "testnet"
        with issuer.receipts.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS testnet_winner_epoch_v1 "
                "(epoch INTEGER PRIMARY KEY, intent_digest TEXT NOT NULL)"
            )

    def validate_stage(self, ref, snapshot, capabilities, resolved, plan):
        auth = self.authorization
        if (
            not auth.valid_from_block
            <= snapshot.finalized_block
            <= auth.valid_through_block
        ):
            _refuse("STANDING_AUTHORIZATION_OUTSIDE_WINDOW")
        if snapshot.context != auth.context:
            _refuse("NETWORK_NOT_AUTHORIZED")
        if plan.burn_uid != BURN_UID:
            _refuse("BURN_UID_NOT_0")
        intent = resolved["intent"]
        if (
            intent["maturity"] != self.issuer.maturity
            or intent["stage"] != self.issuer.stage
            or intent["authority"] != auth.authority
            or intent["policy_digest"] != auth.policy_digest
            or intent["authority_record_digest"] != auth.authority_record_digest
        ):
            _refuse("INTENT_NOT_AUTHORIZED")
        with self.issuer.receipts.transaction() as db:
            row = db.execute(
                "SELECT intent_digest FROM testnet_winner_epoch_v1 WHERE epoch=?",
                (intent["epoch"],),
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO testnet_winner_epoch_v1 VALUES (?,?)",
                    (intent["epoch"], ref.digest),
                )
            elif row[0] != ref.digest:
                _refuse("EPOCH_ALREADY_PUBLISHED")


# -- operator entry point ------------------------------------------------------------------


def preview(issuer, snapshot):
    """This epoch's targets exactly as `issue` would compute them, without
    recording a promotion in the ledger or storing an intent; it opens no
    wallet and signs nothing. For the operator's look before the first
    publication, and for each epoch's journal line."""
    records = issuer._records(snapshot, observe=False, preview=True)
    return {
        "schema": "carbon.rewards.testnet-winner-preview.v1",
        "identity": issuer._identity(snapshot),
        "epoch": issuer.epoch(snapshot),
        "finalized_block": snapshot.finalized_block,
        "policy": issuer.policy.version,
        "records": {
            challenge: (
                None
                if record is None
                else {
                    "hotkey": record["promotion"]["hotkey"],
                    "kind": record["promotion"]["kind"],
                    "eligible": record["eligible"],
                    "reason": record["reason"],
                    "clock_ms": record["clock_ms"],
                }
            )
            for challenge, record in sorted(records.items())
        },
        "targets": issuer._targets(snapshot, records),
        "signed": False,
    }


def load_standing(path, context):
    """The operator's standing authorization file: owner-only JSON naming the
    owner record (whose bytes it digests), the policy digest, the publisher
    hotkey, the runtime spec and the block window; and, off testnet 567, the
    `authority` record id (OWNER-WEIGHTS-AUTHORITY-01)."""
    import os
    import stat
    from pathlib import Path

    path = Path(path)
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or info.st_mode & 0o077:
        _refuse("STANDING_AUTHORIZATION_NOT_OWNER_ONLY")
    raw = json.loads(path.read_bytes())
    record = (path.parent / raw["authority_record"]).resolve()
    return StandingAuthorization(
        authority_record_digest=hashlib.sha256(record.read_bytes()).hexdigest(),
        policy_digest=raw["policy_digest"],
        context=context,
        publisher_hotkey=raw["publisher_hotkey"],
        expected_runtime_spec=raw["expected_runtime_spec"],
        valid_from_block=raw["valid_from_block"],
        valid_through_block=raw["valid_through_block"],
        authority=raw.get("authority", AUTHORITY),
    )


def check_weight_source(target):
    """A deployment whose promotions may set weights: never a Graphite
    development deployment (`development_only`, VALIDATOR-13)."""
    if getattr(target, "development_only", False):
        _refuse("DEVELOPMENT_DEPLOYMENT_NEVER_SETS_WEIGHTS")
    return target


def _open_lean_pool(path):
    """The existing pool store of a direct-receiver Challenge; never created."""
    from carbon.battery.pool_store import PoolStore

    if path.is_symlink() or not path.is_file():
        _refuse("LEAN_POOL_UNAVAILABLE")
    return PoolStore(path)


def _issuer(args, config, journal, *, runtime_spec=None):
    """The issuer `run` and `preview` share: the same policy, standing
    authorization, ledger and weight sources. ``runtime_spec`` (from
    `runtime_accept.resolve`) replaces the authorization's pinned spec IN MEMORY
    when the live runtime was accepted by its used-surface digest (H8); the
    owner's file is never rewritten."""
    from pathlib import Path

    from carbon.battery import deployment
    from carbon.transport.store import ReceiptJournal

    from .winner_decay import load_policy
    from .winner_eligibility import (
        battery_promotion,
        lean_crowns_since,
        lean_promotion,
    )

    policy = load_policy(args.policy_version)
    if config.context is None or (config.context.network, config.netuid) != (
        policy.network,
        policy.netuid,
    ):
        _refuse("POLICY_NOT_FOR_THIS_NETWORK")
    auth = load_standing(args.standing, config.context)
    if runtime_spec is not None and runtime_spec != auth.expected_runtime_spec:
        from dataclasses import replace

        auth = replace(auth, expected_runtime_spec=runtime_spec)
    sources, replays = {}, {}
    if args.battery_deployment:
        try:
            deployment.require_live(
                deployment.load_config(Path(args.battery_deployment))
            )
        except deployment.EvaluationUnavailable:
            _refuse("WEIGHT_SOURCE_ARCHIVED")
        target = deployment.validator(
            Path(args.battery_deployment), repository=args.repository, readonly=True
        )
        check_weight_source(target)
        sources[target.identities()["challenge"]["id"]] = lambda: battery_promotion(
            target
        )
    for entry in args.lean_pool or ():
        # CHALLENGE_ID=POOL_STORE_PATH: a direct-receiver Challenge's pool
        # store, opened read only through the same loader the receiver uses.
        challenge_id, _, path = entry.partition("=")
        if not challenge_id or not path or challenge_id in sources:
            _refuse("LEAN_POOL_ARGUMENT_INVALID")
        store = _open_lean_pool(Path(path))
        sources[challenge_id] = lambda store=store: lean_promotion(store)
        replays[challenge_id] = lambda recorded, store=store: lean_crowns_since(
            store, recorded
        )
    return TestnetWinnerIntentIssuer(
        ReceiptJournal(Path(journal), config.context),
        auth,
        policy,
        WinnerLedger(Path(args.ledger)),
        sources,
        replays,
    )


async def _preview(args):
    """`preview`: the issuer over a throwaway journal, at a fresh finalized
    snapshot read without any wallet."""
    import tempfile
    from pathlib import Path

    from carbon.chain.sdk import BittensorReader
    from carbon.development_testnet.operator import load_config

    config = load_config(Path(args.config).absolute())
    with tempfile.TemporaryDirectory() as scratch:
        issuer = _issuer(args, config, Path(scratch) / "preview.sqlite3")
        snapshot = await BittensorReader().capture(config.context)
        return preview(issuer, snapshot)


#: The most reconcile calls one run makes for an earlier dispatch (each scans
#: at most 256 finalized blocks): enough to find a reveal several epochs back.
RECONCILE_CALLS = 40
#: Dispatch states reconcile may still move on: a timelocked commit not yet
#: revealed, or a transaction not yet found in the finalized backfill.
RECONCILABLE = ("REVEAL_PENDING", "AMBIGUOUS")


async def settle_pending(publisher, calls=RECONCILE_CALLS):
    """Reconcile an earlier, unfinished dispatch before a new publication.

    A timelocked commit stays `REVEAL_PENDING` until its reveal is read, and
    the shared publisher refuses a new publication while one is open
    (`RECONCILE_PENDING_DISPATCH_FIRST`). Without this, the first commit-reveal
    publication blocked every later one. Bounded: None once nothing is
    pending, else the open dispatch's latest row. Reads the chain only; signs
    nothing."""
    row = None
    for _ in range(calls):
        pending = publisher.journal.pending()
        if pending is None:
            return None
        row = await publisher.reconcile(pending)
    return row if publisher.journal.pending() is not None else None


async def _run(args):
    from pathlib import Path

    from carbon.chain import runtime_accept
    from carbon.chain.sdk_weights import BittensorPublicationBackend
    from carbon.development_testnet.operator import _wallet, load_config

    config = load_config(Path(args.config).absolute())
    issuer = _issuer(args, config, args.journal)
    # H8: the live runtime, after the issuer's own offline refusals and before any wallet. A new spec with the
    # accepted used-surface digest is published under at once; anything else refuses here, before signing.
    try:
        spec = None
        if runtime_accept.has_baseline(args.journal):
            spec = await runtime_accept.resolve(
                config.endpoint, config.genesis_hash, args.journal
            )
    except runtime_accept.RuntimeRefused as refused:
        _refuse(refused.code)
    if spec is not None and spec != config.expected_runtime_spec:
        issuer = _issuer(args, config, args.journal, runtime_spec=spec)
    backend = BittensorPublicationBackend(
        config.context,
        config.publisher_hotkey,
        _wallet(config),
        network=config.context.network,
    )
    try:
        publisher = TestnetWinnerPublisher(issuer, backend)
        # An earlier timelocked commit is settled first; while it cannot be,
        # nothing new is published (fail closed), and the result says why.
        open_row = await settle_pending(publisher)
        if open_row is not None:
            # nothing new is published, but every crown since the last record is (fail closed on a gap)
            issuer.record((await backend.observe())[0])
            return {
                "status": "RECONCILE_PENDING",
                "dispatch": open_row.get("identity"),
                "state": open_row["state"],
                "reason": open_row.get("reason"),
            }
        snapshot, _ = await backend.observe()
        return await publisher.publish(issuer.issue(snapshot))
    finally:
        await backend.close()


def main(argv=None):
    import argparse
    import asyncio
    import sys

    parser = argparse.ArgumentParser(
        prog="python -m carbon.rewards.testnet_winner_publication"
    )
    parser.add_argument("command", choices=("run", "preview"))
    for name in ("config", "standing", "journal", "ledger"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--battery-deployment")
    parser.add_argument(
        "--lean-pool",
        action="append",
        metavar="CHALLENGE_ID=PATH",
        help="a direct-receiver Challenge's pool store (repeatable)",
    )
    parser.add_argument(
        "--policy-version",
        help="a registered policy version (the current one if omitted)",
    )
    parser.add_argument("--repository", default=".")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run((_preview if args.command == "preview" else _run)(args))
    except WinnerPublicationRefused as refused:
        print(json.dumps({"status": "REFUSED", "reason": str(refused)}))
        return 2
    except Exception:  # noqa: BLE001 - no provider, wallet or input text echoed
        print(json.dumps({"status": "FAILED_CLOSED"}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2, default=str))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    # The package module's own main: under `python -m` this file is
    # `__main__`, a second copy whose classes the package's are not.
    import sys

    from carbon.rewards.testnet_winner_publication import main as _main

    sys.exit(_main())
