"""Testnet 567 winner-weight publication, once per epoch (VALIDATOR-14;
OWNER-TESTNET-WEIGHTS-01).

SECURITY-SENSITIVE (AGENTS.md §13): this publishes weights. It is not
SECURITY_QUALIFIED, and it needs the dedicated review that every chain path
gets. Testnet subnet 567 only; mainnet has no path here.

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
- netuid 567 and burn UID 0;
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
from .winner_decay import WinnerPolicy, epoch_targets, winner_fraction
from .winner_eligibility import WinnerLedger, payable

INTENT_SCHEMA = "carbon.rewards.testnet-winner-intent.v1"
AUTHORITY = "OWNER-TESTNET-WEIGHTS-01"
NETUID = 567
BURN_UID = 0


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
            or self.context.network != "testnet"
            or self.context.netuid != NETUID
            or type(self.publisher_hotkey) is not str
            or not self.publisher_hotkey
            or type(self.expected_runtime_spec) is not int
            or self.expected_runtime_spec <= 0
            or type(self.valid_from_block) is not int
            or type(self.valid_through_block) is not int
            or not 0 <= self.valid_from_block <= self.valid_through_block
            or self.authority != AUTHORITY
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
    """

    def __init__(self, receipts, authorization, policy, ledger, sources):
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
        if receipts.context != authorization.context:
            _refuse("PUBLICATION_CONTEXT_REQUIRED")
        if type(ledger) is not WinnerLedger:
            _refuse("WINNER_LEDGER_REQUIRED")
        if set(sources) - set(policy.challenges):
            _refuse("SOURCE_OUTSIDE_POLICY")
        self.receipts, self.authorization = receipts, authorization
        self.policy, self.ledger, self.sources = policy, ledger, dict(sources)
        self.profile = DevelopmentTestnetProfile(
            authorization.context, authorization.expected_runtime_spec
        )
        with receipts.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS testnet_winner_intent_v1 "
                "(identity TEXT PRIMARY KEY, digest TEXT NOT NULL, body TEXT NOT NULL)"
            )

    def epoch(self, snapshot):
        return snapshot.finalized_block // self.policy.cadence_blocks

    def _records(self, snapshot, *, observe):
        coldkeys = {p.hotkey: p.coldkey for p in snapshot.participants}
        found = {}
        for challenge in self.policy.challenges:
            if observe and challenge in self.sources:
                promotion = self.sources[challenge]()
                found[challenge] = self.ledger.observe(
                    self.policy, challenge, promotion, coldkeys, snapshot.timestamp_ms
                )
            else:
                mine = self.ledger.records(challenge)
                found[challenge] = mine[-1] if mine else None
        return found

    def _targets(self, snapshot, records):
        registered = {p.hotkey: p for p in snapshot.participants}
        winners = {}
        for challenge, record in records.items():
            winner = payable(record, set(registered))
            if winner is not None:
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
                "identity": f"testnet-winner-{self.policy.version}-e{self.epoch(snapshot)}",
                "stage": "PUBLIC_TESTNET_DEVELOPMENT",
                "maturity": "DEVELOPMENT_ONLY",
                "authority": AUTHORITY,
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
        identity = f"testnet-winner-{self.policy.version}-e{self.epoch(snapshot)}"
        with self.receipts.transaction() as db:
            row = db.execute(
                "SELECT digest FROM testnet_winner_intent_v1 WHERE identity=?",
                (identity,),
            ).fetchone()
        if row is not None:
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
        if self._targets(snapshot, records) != body["targets"]:
            _refuse("TARGETS_CHANGED_REISSUE_NEXT_EPOCH")
        projection = {
            "schema": "carbon.rewards.testnet-winner-projection.v1",
            "maturity": "DEVELOPMENT_ONLY",
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
            network="testnet",
            spec_version=authorization.expected_runtime_spec,
        )
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
        if snapshot.context.network != "testnet" or snapshot.context.netuid != NETUID:
            _refuse("TESTNET_567_ONLY")
        if plan.burn_uid != BURN_UID:
            _refuse("BURN_UID_NOT_0")
        intent = resolved["intent"]
        if (
            intent["maturity"] != "DEVELOPMENT_ONLY"
            or intent["authority"] != AUTHORITY
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


def load_standing(path, context):
    """The operator's standing authorization file: owner-only JSON naming the
    owner record (whose bytes it digests), the policy digest, the publisher
    hotkey, the runtime spec and the block window."""
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
    )


async def _run(args):
    from pathlib import Path

    from carbon.battery import deployment
    from carbon.chain.sdk_weights import BittensorPublicationBackend
    from carbon.development_testnet.operator import _wallet, load_config
    from carbon.transport.store import ReceiptJournal

    from .winner_decay import load_policy
    from .winner_eligibility import battery_promotion

    config = load_config(Path(args.config).absolute())
    if config.context is None or config.netuid != NETUID:
        _refuse("TESTNET_567_ONLY")
    policy = load_policy()
    auth = load_standing(args.standing, config.context)
    sources = {}
    if args.battery_deployment:
        target = deployment.validator(
            Path(args.battery_deployment), repository=args.repository, readonly=True
        )
        sources[target.identities()["challenge"]["id"]] = lambda: battery_promotion(
            target
        )
    issuer = TestnetWinnerIntentIssuer(
        ReceiptJournal(Path(args.journal), config.context),
        auth,
        policy,
        WinnerLedger(Path(args.ledger)),
        sources,
    )
    backend = BittensorPublicationBackend(
        config.context, config.publisher_hotkey, _wallet(config), network="testnet"
    )
    try:
        publisher = TestnetWinnerPublisher(issuer, backend)
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
    parser.add_argument("command", choices=("run",))
    for name in ("config", "standing", "journal", "ledger"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--battery-deployment")
    parser.add_argument("--repository", default=".")
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(_run(args))
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
    import sys

    sys.exit(main())
