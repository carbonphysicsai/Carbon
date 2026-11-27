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

from .core import Q12, RewardFailure
from .ledger import encode
from .waterfall import (
    WATERFALL_ROUTE,
    HoldBonusLedger,
    WaterfallEpochObservation,
    compute_waterfall_targets,
)
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
    SEALED_TESTNET_REASON,
    WinnerCutoverFailure,
    WinnerIdentityFailure,
    WinnerLedger,
    payable,
)

INTENT_SCHEMA = "carbon.rewards.testnet-winner-intent.v1"
AUTHORITY = "OWNER-TESTNET-WEIGHTS-01"
NETUID = 567
BURN_UID = 0
HOLD_LEDGER_FILENAME = "hold_bonus_ledger.jsonl"
WATERFALL_CHAIN_READ_TIMEOUT_S = 30.0
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


@dataclass(frozen=True)
class Handover:
    """One Challenge's king hand-over between two exam versions' pool stores (OWNER G-LEAD-69: the Motor slot pays the
    last payable 1.8 king from the 1.9 launch until the first PAYABLE 1.9 king).

    A new exam resets the king (`koth_carry`), so the new version's store starts without one. ``source`` and ``replay``
    read the PREVIOUS version's store; ``models`` returns the model ids the NEW store's own journal ever crowned, which
    is how a ledger record is told to be the new version's. The issuer's ordinary source is the new store.
    """

    source: object
    replay: object
    models: object


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
    Crowns are recorded only on a cycle that proceeds (a new epoch's first
    issue): a refused or settling cycle leaves the ledger byte-identical, and
    the next proceeding cycle replays every crown it missed, each clocked when
    it won at the door.

    `handovers` (optional) maps a Challenge to its `Handover`.
    """

    def __init__(
        self,
        receipts,
        authorization,
        policy,
        ledger,
        sources,
        replays=None,
        handovers=None,
        hold_ledger=None,
        waterfall_observer=None,
    ):
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
        if hold_ledger is not None and type(hold_ledger) is not HoldBonusLedger:
            _refuse("HOLD_LEDGER_INVALID")
        if waterfall_observer is not None and not callable(waterfall_observer):
            _refuse("WATERFALL_OBSERVER_INVALID")
        self.receipts, self.authorization = receipts, authorization
        self.policy, self.ledger, self.sources = policy, ledger, dict(sources)
        self.replays = dict(replays or {})
        if set(self.replays) - set(self.sources):
            _refuse("SOURCE_OUTSIDE_POLICY")
        self.handovers = dict(handovers or {})
        if set(self.handovers) - set(self.replays):
            _refuse("HANDOVER_SOURCE_REQUIRED")
        self.hold_ledger = hold_ledger
        self.waterfall_observer = waterfall_observer
        #: The journal whose stored intents say which epochs the loop published (`_published`): this issuer's own
        #: receipts, or, for a preview on a scratch journal, the loop's real journal read only.
        self.intent_journal = None
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

    def _published(self, epoch):
        """Whether the loop stored an intent for ``epoch`` (it issued, so its observation recorded every crown before
        it). Read only; an unreadable real journal refuses rather than guessing."""
        identity = f"{self.prefix}-{self.policy.version}-e{epoch}"
        query = "SELECT 1 FROM testnet_winner_intent_v1 WHERE identity=?"
        if self.intent_journal is None:
            with self.receipts.transaction() as db:
                return db.execute(query, (identity,)).fetchone() is not None
        import sqlite3

        try:
            db = sqlite3.connect(f"file:{self.intent_journal}?mode=ro", uri=True)
            try:
                return db.execute(query, (identity,)).fetchone() is not None
            finally:
                db.close()
        except sqlite3.Error:
            _refuse("INTENT_JOURNAL_UNREADABLE")

    def _promotion(self, challenge, source=None):
        source = self.sources.get(challenge) if source is None else source
        if source is None:
            return None
        try:
            promotion = source()
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

    def _crowns(self, replay, mine, promotion, snapshot, whole=False):
        """``(promotion, journal, crowned_ms)`` to observe, in order: every crown since the last record
        (``replays``), else the current one alone. ``crowned_ms`` is the door event time of a crown the loop MISSED,
        else None (clocked at observation, as on a cycle that ran normally). Missed (owner: a king's window starts
        'when it actually won'; Validator-2 6 Nov): two or more crowns since the last record, or a single one while the
        previous epoch has no stored intent (the loop skipped or refused it; had it issued, its observation would have
        recorded any earlier crown). ``whole``: with no record yet, every crown of the store's journal (a hand-over's
        new store)."""
        if replay is None or not (mine or whole):
            return [(promotion, None, None)]
        try:
            crowns = replay(mine[-1]["promotion"]["model_id"] if mine else None)
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
        if len(crowns) == 1 and self._published(self.epoch(snapshot) - 1):
            # the usual cycle: one new crown since the last epoch's issue, clocked when first observed
            return [(crowns[0]["promotion"], crowns[0]["journal"], None)]
        # crowns the loop missed: each clocked when it won at the door; one without a time refuses them all, before
        # anything is written
        if any(
            type(c["journal"].get("at_ms")) is not int or c["journal"]["at_ms"] < 0
            for c in crowns
        ):
            _refuse("CROWN_EVENT_TIME_MISSING")
        return [(c["promotion"], c["journal"], c["journal"]["at_ms"]) for c in crowns]

    def _records(self, snapshot, *, observe, preview=False):
        mode = {"observe": observe, "preview": preview}
        return {
            challenge: (
                self._handed_over(challenge, snapshot, **mode)
                if challenge in self.handovers
                else self._record(
                    challenge,
                    self._promotion(challenge),
                    self.replays.get(challenge),
                    snapshot,
                    **mode,
                )
            )
            for challenge in self.policy.challenges
        }

    def _handed_over(self, challenge, snapshot, *, observe, preview):
        """The one record a Challenge in a king hand-over pays, never two: the new version's king once one is payable,
        else the previous version's. A king of one store is never another store's predecessor: the new version's FIRST
        recorded king starts a fresh clock, the previous king's own miner included (owner G-LEAD-81, 24 Nov 2026). One
        thing carries over: an INELIGIBLE previous king's miner gains no eligibility from the new deployment (`decide`'s
        same-miner rule, unchanged).

        Until it is over, a new crown that cannot be paid takes nothing from the previous king and stops no cycle: one
        graded on a pack the policy does not qualify, or whose hotkey is not registered, is not recorded (a record is
        permanent) and is replayed later; one inside the replayed journal is passed over (`_steps`). Under a registered
        baseline the new store's first incumbent is recorded ineligible, as on a fresh ledger. It is over once a new
        king was payable when the loop observed him (a king replayed behind a later one never was); from then on only
        the new store is read, by the ordinary rules."""
        from carbon.challenge_validator.canary import is_canary

        handover = self.handovers[challenge]
        try:
            crowned = frozenset(handover.models())
        except Exception:  # noqa: BLE001 - closed source failure, no stale fallback
            raise WinnerPublicationRefused("WINNER_SOURCE_UNAVAILABLE") from None

        def new(record):
            return record["promotion"]["model_id"] in crowned

        def old(record):
            return not new(record)

        mode = {"observe": observe, "preview": preview}
        registered = {p.hotkey for p in snapshot.participants}
        mine = self.ledger.records(challenge)
        before = [r for r in mine if old(r)]
        # the last king recorded in each observation: the one that held the crown when the loop looked
        seen = {r["observed_ms"]: r for r in mine if new(r)}
        over = any(
            r["eligible"]
            and r.get("winner_coldkey") is not None
            and not is_canary(r["promotion"]["hotkey"])
            for r in seen.values()
        )
        promotion = self._promotion(challenge)
        fallback = before[-1] if before and not before[-1]["eligible"] else None
        if over:
            return self._record(
                challenge,
                promotion,
                self.replays[challenge],
                snapshot,
                belongs=new,
                fallback=fallback,
                **mode,
            )
        if (
            promotion is not None
            and promotion["hotkey"] in registered
            and self._qualified(challenge, promotion)
        ):
            current = self._record(
                challenge,
                promotion,
                self.replays[challenge],
                snapshot,
                belongs=new,
                fallback=(
                    fallback if self.policy.baseline(challenge) is None else None
                ),
                whole=True,
                **mode,
            )
            if payable(current, registered) is not None and not is_canary(
                current["promotion"]["hotkey"]
            ):
                return current
        return self._record(
            challenge,
            self._promotion(challenge, handover.source),
            handover.replay,
            snapshot,
            belongs=old,
            **mode,
        )

    @staticmethod
    def _steps(crowns, mine, coldkeys, whole):
        """Each replayed crown as ``(crown, decided_as, journal, crowned_ms)``. In a hand-over (``whole``) a crown whose
        hotkey is not registered is passed over, and the next one is decided against the last king that IS recorded: as
        a first incumbent while its store has none. Otherwise every crown, decided as itself.
        """
        last = mine[-1]["promotion"] if mine else None
        for crown, journal, crowned_ms in crowns:
            decided = None
            if whole:
                if crown["hotkey"] not in coldkeys:
                    continue
                if crown["kind"] != FIRST and last is None:
                    decided = {**crown, "kind": FIRST}
                elif crown["kind"] != FIRST and crown["previous"] != last["model_id"]:
                    decided = {
                        **crown,
                        "previous": last["model_id"],
                        "previous_hotkey": last["hotkey"],
                    }
            yield crown, decided, journal, crowned_ms
            last = crown

    def _qualified(self, challenge, promotion):
        """Whether a sealed crown's packs are ones this policy names (`decide`'s own test, before it records)."""
        if (
            promotion.get("incumbent_reason") != SEALED_TESTNET_REASON
            or self.policy.network == "testnet"
        ):
            return True
        packs = self.policy.qualified_packs(challenge)
        graded = promotion.get("evaluation_pack_digests")
        # unreadable evidence stays `decide`'s own refusal
        return not graded or (packs is not None and set(graded) <= packs)

    def _record(
        self,
        challenge,
        promotion,
        replay,
        snapshot,
        *,
        observe,
        preview,
        belongs=None,
        fallback=None,
        whole=False,
    ):
        from .winner_eligibility import decide, same_crown

        if promotion is None:
            return None
        coldkeys = {p.hotkey: p.coldkey for p in snapshot.participants}
        mine = self.ledger.records(challenge)
        if belongs is not None:
            mine = [r for r in mine if belongs(r)]
        known = [r for r in mine if r["promotion"]["model_id"] == promotion["model_id"]]
        if known:
            if not same_crown(known[0]["promotion"], promotion):
                _refuse("TARGETS_CHANGED_REISSUE_NEXT_EPOCH")
            return known[0]
        found = None
        try:
            if observe:
                # each crown since the last record, in the door's order, each with its own predecessor
                for crown, decided, journal, crowned_ms in self._steps(
                    self._crowns(replay, mine, promotion, snapshot, whole),
                    mine,
                    coldkeys,
                    whole,
                ):
                    found = self.ledger.observe(
                        self.policy,
                        challenge,
                        crown,
                        coldkeys,
                        snapshot.timestamp_ms,
                        journal,
                        crowned_ms,
                        belongs=belongs,
                        fallback=fallback,
                        decided_as=decided,
                    )
            elif preview:
                # the same replay in memory: nothing is written
                seen = list(mine)
                for crown, decided, journal, crowned_ms in self._steps(
                    self._crowns(replay, mine, promotion, snapshot, whole),
                    mine,
                    coldkeys,
                    whole,
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
                            crown if decided is None else decided,
                            seen[-1] if seen else fallback,
                            coldkeys,
                            snapshot.timestamp_ms,
                            crowned_ms,
                        )
                    )
                    if not again:
                        record = {**record, "promotion": crown}
                        if journal is not None:
                            record = {**record, "journal": journal}
                        seen.append(record)
                    found = record
            else:
                _refuse("TARGETS_CHANGED_REISSUE_NEXT_EPOCH")
        except (WinnerIdentityFailure, WinnerCutoverFailure) as failure:
            _refuse(str(failure))
        return found

    def _targets(self, snapshot, records, *, observe_waterfall=False):
        from carbon.challenge_validator.canary import is_canary

        registered = {p.hotkey: p for p in snapshot.participants}
        winners = {}
        for challenge, record in records.items():
            winner = payable(record, set(registered))
            # A registered canary is never weighted (CANARY-01): its share
            # burns, as a Challenge with no payable winner does.
            if winner is not None and not is_canary(winner.hotkey):
                winners[challenge] = winner
        if self.policy.waterfall is not None:
            if self.waterfall_observer is None:
                _refuse("WATERFALL_OBSERVER_REQUIRED")
            epoch = self.epoch(snapshot)
            try:
                obs = self.waterfall_observer(snapshot, epoch)
            except (WinnerPublicationRefused, PublicationFailure):
                raise
            except RewardFailure as failure:
                _refuse(str(failure))
            except Exception:  # noqa: BLE001 - closed observer failure
                _refuse("WATERFALL_OBSERVER_UNAVAILABLE")
            if type(obs) is not WaterfallEpochObservation:
                _refuse("WATERFALL_OBSERVATION_INVALID")
            if obs.staked_by_coldkey is None:
                _refuse("STAKE_OBSERVATION_REQUIRED")
            if obs.epoch_miner_emission_rao is None:
                _refuse("EMISSION_OBSERVATION_REQUIRED")
            if self.policy.network == "finney" and obs.owner_coldkey is None:
                _refuse("OWNER_COLDKEY_REQUIRED")
            canary_hotkeys = frozenset(
                p.hotkey for p in snapshot.participants if is_canary(p.hotkey)
            )
            try:
                targets = compute_waterfall_targets(
                    self.policy,
                    self.policy.waterfall,
                    snapshot,
                    winners,
                    epoch=epoch,
                    hold_ledger=self.hold_ledger,
                    epoch_miner_emission_rao=obs.epoch_miner_emission_rao,
                    treasury_current_stake_rao=obs.treasury_current_stake_rao,
                    staked_by_coldkey=obs.staked_by_coldkey,
                    crown_credits_by_coldkey=obs.crown_credits_by_coldkey,
                    bonus_credits_by_coldkey=obs.bonus_credits_by_coldkey,
                    owner_coldkey=obs.owner_coldkey,
                    owner_hotkeys=obs.owner_hotkeys,
                    publisher_hotkey=self.authorization.publisher_hotkey,
                    canary_hotkeys=canary_hotkeys,
                )
                if observe_waterfall and self.hold_ledger is not None:
                    if obs.crown_credits_by_coldkey:
                        self.hold_ledger.record_crown_earnings(
                            epoch, obs.crown_credits_by_coldkey
                        )
                    if obs.bonus_credits_by_coldkey:
                        self.hold_ledger.record_bonus_earnings(
                            epoch, obs.bonus_credits_by_coldkey
                        )
                    self.hold_ledger.sample_epoch_stakes(epoch, obs.staked_by_coldkey)
                    self.hold_ledger.record_epoch_emission(
                        epoch, obs.epoch_miner_emission_rao
                    )
            except RewardFailure as failure:
                _refuse(str(failure))
            return targets
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
        waterfall_mode = self.policy.waterfall is not None
        route = WATERFALL_ROUTE if waterfall_mode else "DIRECT_WINNER_PLUS_BURN"
        no_winner = (
            not targets["winners"]
            and not targets.get("hold_bonus")
            and not targets.get("treasury")
            if waterfall_mode
            else not targets["winners"]
        )
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
                "route": route,
                "no_winner": no_winner,
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
            return TestnetWinnerWeightRef(identity, row[0])
        records = self._records(snapshot, observe=True)
        body = self._body(
            snapshot, records, self._targets(snapshot, records, observe_waterfall=True)
        )
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
        expected_route = (
            WATERFALL_ROUTE
            if self.policy.waterfall is not None
            else "DIRECT_WINNER_PLUS_BURN"
        )
        if (
            body["context"] != asdict(snapshot.context)
            or body["policy_digest"] != self.authorization.policy_digest
            or body["epoch"] != self.epoch(snapshot)
            or body.get("route", "DIRECT_WINNER_PLUS_BURN") != expected_route
        ):
            _refuse("INTENT_NOT_FOR_THIS_EPOCH")
        records = self._records(snapshot, observe=False)
        if self._targets(snapshot, records, observe_waterfall=False) != body[
            "targets"
        ] or any(
            (None if r is None else digest(encode(r).encode())) != body["ledger"][c]
            for c, r in records.items()
        ):
            _refuse("TARGETS_CHANGED_REISSUE_NEXT_EPOCH")
        projection = {
            "schema": "carbon.rewards.testnet-winner-projection.v1",
            "maturity": body["maturity"],
            "route": body["route"],
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
        "targets": issuer._targets(snapshot, records, observe_waterfall=False),
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


def crowned_models(store):
    """Every model id a lean pool store's own incumbent journal ever crowned."""
    return {
        e["body"]["model_id"]
        for e in store.events("incumbent")
        if e["body"].get("model_id") is not None
    }


def _settled_waterfall_intents(journal_path, context_dict, start_epoch, end_epoch):
    """Read-only scan of `ROW_VERIFIED` intents in `journal_path` for `context_dict`
    with `start_epoch <= epoch < end_epoch`, ordered by `epoch ASC`."""
    import sqlite3
    from pathlib import Path

    path = Path(journal_path)
    if path.is_symlink():
        _refuse("INTENT_JOURNAL_UNREADABLE")
    if not path.is_file() or start_epoch >= end_epoch:
        return []
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            tables = {
                r[0]
                for r in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if not {"testnet_winner_intent_v1", "publication_v1"} <= tables:
                return []
            epoch_pins = {}
            if "testnet_winner_epoch_v1" in tables:
                epoch_pins = dict(
                    db.execute(
                        "SELECT epoch, intent_digest FROM testnet_winner_epoch_v1"
                    ).fetchall()
                )
            rows = db.execute("""SELECT i.digest, i.body
                   FROM testnet_winner_intent_v1 AS i
                   JOIN publication_v1 AS p ON p.identity = i.digest
                   WHERE p.state = 'ROW_VERIFIED'""").fetchall()
        finally:
            db.close()
    except sqlite3.Error:
        _refuse("INTENT_JOURNAL_UNREADABLE")

    by_epoch = {}
    for intent_digest, body_text in rows:
        if digest(body_text.encode()) != intent_digest:
            _refuse("UNKNOWN_OR_ALTERED_WINNER_INTENT")
        body = json.loads(body_text)
        if body.get("context") != context_dict:
            continue
        ep = body.get("epoch")
        if type(ep) is not int or not (start_epoch <= ep < end_epoch):
            continue
        if ep in epoch_pins and epoch_pins[ep] != intent_digest:
            continue
        if ep not in by_epoch:
            by_epoch[ep] = body
    return [by_epoch[ep] for ep in sorted(by_epoch)]


def _invoke_waterfall_chain_reader(
    context,
    *,
    block,
    block_hash,
    coldkeys,
    treasury_coldkeys=(),
    cadence_blocks,
    chain_reader=None,
):
    """Execute the read-only Subtensor waterfall state read in a bounded worker thread
    so callers already inside an `asyncio` event loop (`_preview`, `_run`, `weights.execute`)
    never collide with the running loop."""
    import asyncio
    import concurrent.futures
    import inspect

    if chain_reader is None:
        from carbon.chain.sdk_weights import (
            read_waterfall_chain_state as chain_reader,
        )

    async def _coro():
        kwargs = {
            "block": block,
            "block_hash": block_hash,
            "coldkeys": coldkeys,
            "cadence_blocks": cadence_blocks,
        }
        sig = inspect.signature(chain_reader)
        if "treasury_coldkeys" in sig.parameters or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        ):
            kwargs["treasury_coldkeys"] = treasury_coldkeys
        res = chain_reader(context, **kwargs)
        if inspect.isawaitable(res):
            return await res
        return res

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                asyncio.run,
                asyncio.wait_for(_coro(), WATERFALL_CHAIN_READ_TIMEOUT_S),
            ).result()
    except Exception:  # noqa: BLE001 - fail closed without leaking provider text
        _refuse("WATERFALL_CHAIN_OBSERVATION_UNAVAILABLE")


def _build_cli_waterfall_observer(
    context,
    policy,
    hold_ledger,
    journal_path,
    *,
    chain_reader=None,
):
    """Build the fail-closed CLI `waterfall_observer(snapshot, epoch)` for a one-shot
    `weights preview` or `weights run` invocation."""
    wf = policy.waterfall
    sink_coldkeys = tuple(sorted({s.coldkey for s in wf.treasury_sinks}))
    cache: dict[int, WaterfallEpochObservation] = {}

    def _observe(snapshot, epoch):
        if epoch in cache:
            return cache[epoch]
        prev = hold_ledger.latest_recorded_epoch_before(epoch)
        start_epoch = 0 if prev is None else prev
        settled = _settled_waterfall_intents(
            journal_path, asdict(snapshot.context), start_epoch, epoch
        )
        candidate_crown_cks = {
            holder["coldkey"]
            for body in settled
            for holder, weight_q12 in body.get("targets", {}).get("winners", ())
            if weight_q12 > 0
        }
        participant_cks = {p.coldkey for p in snapshot.participants}
        tracked_cks = {ck for ck, _, _ in hold_ledger.tracked_coldkeys()}
        query_coldkeys = tuple(
            sorted(
                tracked_cks | candidate_crown_cks | participant_cks | set(sink_coldkeys)
            )
        )
        state = _invoke_waterfall_chain_reader(
            context,
            block=snapshot.finalized_block,
            block_hash=snapshot.block_hash,
            coldkeys=query_coldkeys,
            treasury_coldkeys=sink_coldkeys,
            cadence_blocks=policy.cadence_blocks,
            chain_reader=chain_reader,
        )
        if type(state) is not dict:
            _refuse("WATERFALL_CHAIN_OBSERVATION_UNAVAILABLE")
        live_emission_rao = state.get("epoch_miner_emission_rao")
        staked_by_coldkey = state.get("staked_by_coldkey")
        owner_coldkey = state.get("owner_coldkey")
        owner_hotkeys = state.get("owner_hotkeys", ())
        if (
            type(live_emission_rao) is not int
            or live_emission_rao < 0
            or type(staked_by_coldkey) is not dict
            or any(ck not in staked_by_coldkey for ck in query_coldkeys)
            or type(owner_coldkey) is not str
            or not owner_coldkey
        ):
            _refuse("WATERFALL_CHAIN_OBSERVATION_UNAVAILABLE")

        crown_credits: dict[str, tuple[int, str]] = {}
        bonus_credits: dict[str, tuple[int, str]] = {}
        for body in settled:
            ep = body["epoch"]
            ep_emission = hold_ledger.epoch_emission(ep)
            if ep_emission is None:
                ep_emission = live_emission_rao
            targets = body.get("targets", {})
            for holder, weight_q12 in targets.get("winners", ()):
                delta_rao = (ep_emission * int(weight_q12)) // Q12
                if delta_rao > 0:
                    ck = holder["coldkey"]
                    prev_delta = crown_credits[ck][0] if ck in crown_credits else 0
                    crown_credits[ck] = (prev_delta + delta_rao, holder["hotkey"])
            for holder, weight_q12 in targets.get("hold_bonus", ()):
                delta_rao = (ep_emission * int(weight_q12)) // Q12
                if delta_rao > 0:
                    ck = holder["coldkey"]
                    prev_delta = bonus_credits[ck][0] if ck in bonus_credits else 0
                    bonus_credits[ck] = (prev_delta + delta_rao, holder["hotkey"])

        raw_treasury_stake = state.get("treasury_current_stake_rao")
        if type(raw_treasury_stake) is int and raw_treasury_stake >= 0:
            treasury_stake_rao = raw_treasury_stake
        else:
            treasury_stake_rao = (
                sum(int(staked_by_coldkey[ck]) for ck in sink_coldkeys)
                if sink_coldkeys
                else 0
            )
        try:
            obs = WaterfallEpochObservation(
                epoch_miner_emission_rao=live_emission_rao,
                treasury_current_stake_rao=treasury_stake_rao,
                staked_by_coldkey=dict(staked_by_coldkey),
                crown_credits_by_coldkey=crown_credits or None,
                bonus_credits_by_coldkey=bonus_credits or None,
                owner_coldkey=owner_coldkey,
                owner_hotkeys=tuple(owner_hotkeys),
            )
        except Exception:  # noqa: BLE001 - closed observation validation error
            _refuse("WATERFALL_OBSERVATION_INVALID")
        cache[epoch] = obs
        return obs

    return _observe


def _issuer(args, config, journal, *, runtime_spec=None, chain_reader=None):
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
    sources, replays, stores = {}, {}, {}
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
        store = stores[challenge_id] = _open_lean_pool(Path(path))
        sources[challenge_id] = lambda store=store: lean_promotion(store)
        replays[challenge_id] = lambda recorded, store=store: lean_crowns_since(
            store, recorded
        )
    handovers = {}
    for entry in getattr(args, "lean_pool_previous", None) or ():
        # CHALLENGE_ID=POOL_STORE_PATH: the PREVIOUS exam version's store of a Challenge whose --lean-pool is the new
        # version's (a king hand-over). Opened read only, and never the same store as the new one.
        challenge_id, _, path = entry.partition("=")
        if (
            not challenge_id
            or not path
            or challenge_id not in stores
            or challenge_id in handovers
            or Path(path).resolve() == stores[challenge_id].path.resolve()
        ):
            _refuse("LEAN_POOL_ARGUMENT_INVALID")
        old = _open_lean_pool(Path(path))
        handovers[challenge_id] = Handover(
            source=lambda old=old: lean_promotion(old),
            replay=lambda recorded, old=old: lean_crowns_since(old, recorded),
            models=lambda new=stores[challenge_id]: crowned_models(new),
        )
    hold_ledger = None
    waterfall_observer = None
    if policy.waterfall is not None:
        raw_hold_path = getattr(args, "hold_ledger", None)
        hold_path = (
            Path(raw_hold_path)
            if raw_hold_path is not None
            else Path(args.ledger).with_name(HOLD_LEDGER_FILENAME)
        )
        try:
            hold_ledger = HoldBonusLedger(hold_path)
        except RewardFailure as failure:
            _refuse(str(failure))
        waterfall_observer = _build_cli_waterfall_observer(
            config.context,
            policy,
            hold_ledger,
            Path(args.journal).absolute(),
            chain_reader=(
                chain_reader
                if chain_reader is not None
                else getattr(args, "waterfall_chain_reader", None)
            ),
        )
    issuer = TestnetWinnerIntentIssuer(
        ReceiptJournal(Path(journal), config.context),
        auth,
        policy,
        WinnerLedger(Path(args.ledger)),
        sources,
        replays,
        handovers,
        hold_ledger=hold_ledger,
        waterfall_observer=waterfall_observer,
    )
    if Path(journal).absolute() != Path(args.journal).absolute():
        # a preview on a scratch journal reads which epochs were published from the loop's real one, read only
        issuer.intent_journal = Path(args.journal).absolute()
    return issuer


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
        "--lean-pool-previous",
        action="append",
        metavar="CHALLENGE_ID=PATH",
        help="the previous exam version's pool store: its king is paid until the new version's first payable king",
    )
    parser.add_argument(
        "--policy-version",
        help="a registered policy version (the current one if omitted)",
    )
    parser.add_argument(
        "--hold-ledger",
        default=None,
        help=f"hold-bonus ledger JSONL path (defaults to {HOLD_LEDGER_FILENAME} alongside --ledger)",
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
