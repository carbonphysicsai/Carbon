# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""Dispatch adapter for one approved battery OD-4a all-burn publication.

SECURITY-SENSITIVE (AGENTS.md §13). Owner-reviewed 2026-09-28, NOT
SECURITY_QUALIFIED: no dispatch may use this until the owner says so. It
authorizes nothing; a publication needs a fresh request, the owner's written
approval of that exact request digest, and the operator-config authorization
bound to it.
Scope: docs/development/BATTERY_OD4A_DISPATCH_ADAPTER.md.

The only thing this adapter can publish is the source intent the owner
approved, and that is enforced by construction:

- `ApprovedPublication` has no public constructor. `ApprovedPublication.verify`
  is the only way to make one, and it refuses unless the request, the owner
  approval record, the service-signed intent, a fresh runtime probe and the
  operator's transaction authorization all bind to each other (see `verify`).
- `BatteryAllBurnIntentIssuer` takes only an `ApprovedPublication` and stores
  exactly its verified intent envelope; it has no input for any other intent.
- `BatteryAllBurnPublisher` takes only that issuer and an authorization whose
  `source_intent_digest` is the approved one, and rechecks the digest, UID 0,
  netuid 567 and the expiry at every stage, including just before signing.

All-burn only: `signing.sign()` and `winner_intent()` are untouched and this
module never widens them. OD-4b (winner weights) is unauthorized and has no
path here. Signing is external: the publisher hotkey is opened through the
existing operator wallet path, and only the public coldkey address is read.
Testnet subnet 567 only.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from carbon.chain.publication import PublicationFailure
from carbon.development_testnet.model import (
    DevelopmentTestnetFailure,
    DevelopmentTestnetProfile,
    DevelopmentTransactionAuthorization,
)
from carbon.development_testnet.publication import DevelopmentTestnetPublisher
from carbon.rewards.core import Q12
from carbon.rewards.ledger import encode
from carbon.transport.models import digest

from . import od4a, signing

#: The battery validator service key whose weight intents may be published.
#: Pinned by full public key, so a self-consistent envelope signed by any
#: other key is refused (`signing.verify` alone only proves the embedded key
#: signed it). Rotating the key is a reviewed code change, by design.
TRUSTED_SERVICE_PUBLIC_KEY = (
    "28ff1850326a9ff6bf7ef4bb7efb330cff5df58a60a1cb827f5459944a71217a"
)
TRUSTED_SERVICE_KEY_ID = "battery-validator-1392ad958a84e6bc"
APPROVAL_SCHEMA = "carbon.battery.od4a-owner-approval.v1"
INTENT_SCHEMA = "carbon.battery.od4a-dispatch-intent.v1"
BURN_UID = 0
U16_MAX = 65535
_REQUEST_DERIVED = ("request_digest", "operator_config_fragment")
_VERIFIED = object()


class DispatchRefused(DevelopmentTestnetFailure, PublicationFailure):
    """A closed refusal; its message is a fixed code, never input text, so
    the shared lifecycle may record it as the dispatch's reason."""


def _refuse(code):
    raise DispatchRefused(code)


def _utc_now():
    return datetime.now(UTC)


def _expiry(value):
    if type(value) is not str or not od4a._UTC.match(value):
        _refuse("REQUEST_EXPIRY_MALFORMED")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _trusted_intent(intent):
    """The approved key signed exactly a Phase A all-burn weight intent."""
    return (
        type(intent) is dict
        and signing.verify(intent)
        and intent.get("kind") == "weight_intent"
        and intent.get("public_key") == TRUSTED_SERVICE_PUBLIC_KEY
        and intent.get("key_id") == TRUSTED_SERVICE_KEY_ID
        and signing._is_all_burn(intent.get("payload"))
        and intent["payload"]["netuid"] == signing.NETUID
    )


class ApprovedPublication:
    """One approved OD-4a publication; constructed only by `verify`."""

    __slots__ = (
        "approval_digest",
        "authorization",
        "authorization_id",
        "context",
        "expected_runtime_spec",
        "expires",
        "intent",
        "intent_digest",
        "request_digest",
    )

    def __init__(self, *, _token=None, **values):
        if _token is not _VERIFIED:
            raise TypeError("an ApprovedPublication comes only from verify()")
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def __setattr__(self, name, value):
        raise AttributeError("an ApprovedPublication is immutable")

    def __reduce__(self):
        raise TypeError("an ApprovedPublication cannot be serialized")

    @classmethod
    def verify(cls, *, request, approval_bytes, intent, probe, authorization, now):
        """Refuse unless every approved binding holds, then return the value.

        - the request's digest recomputes, and it is exactly Phase A on 567;
        - the approval record names that request digest, and its file digest
          is the authorization's `authority_record_digest`;
        - the intent is signed by the pinned service key, is all-burn, and its
          digest is the request's `source_intent.digest`;
        - the fresh probe still reports the approved runtime surface;
        - the authorization carries the request's id, window, spec, publisher
          and source-intent digest;
        - the request has not expired.

        `now=None` and `probe=None` are for reconciling a dispatch already
        made (`resume`): it reads the chain and never signs. A publisher still
        refuses to dispatch after the expiry, at every stage.
        """
        if type(request) is not dict or type(approval_bytes) is not bytes:
            _refuse("REQUEST_AND_APPROVAL_REQUIRED")
        body = {k: v for k, v in request.items() if k not in _REQUEST_DERIVED}
        if request.get("schema") != od4a.SCHEMA or od4a._digest(body) != request.get(
            "request_digest"
        ):
            _refuse("REQUEST_DIGEST_MISMATCH")
        from carbon.development_testnet.operator import TESTNET_GENESIS

        context = request["context"]
        if (
            context.get("network") != "testnet"
            or context.get("netuid") != signing.NETUID
            or str(context.get("genesis_hash")).lower() != TESTNET_GENESIS
        ):
            _refuse("TESTNET_567_ONLY")
        if (
            request.get("authority") != "OWNER-BATTERY-TESTNET-01 OD-4a"
            or request.get("weights") != {"mode": "ALL_BURN", "rows": od4a.ALL_BURN_ROW}
            or request.get("publisher", {}).get("uid") != BURN_UID
            or request.get("mechanism_id") != 0
            or request.get("max_dispatches") != 1
            or request.get("max_fee_tao") != 0
            or request.get("max_spend_tao") != 0
        ):
            _refuse("REQUEST_NOT_PHASE_A_ALL_BURN")
        expires = _expiry(request.get("expires_utc"))
        if now is not None and now >= expires:
            _refuse("REQUEST_EXPIRED")

        try:
            approval = json.loads(approval_bytes)
        except (UnicodeError, json.JSONDecodeError):
            _refuse("APPROVAL_RECORD_MALFORMED")
        approval_digest = "sha256:" + hashlib.sha256(approval_bytes).hexdigest()
        if (
            type(approval) is not dict
            or approval.get("schema") != APPROVAL_SCHEMA
            or approval.get("request_digest") != request["request_digest"]
            or approval.get("authorization_id") != request["authorization_id"]
            or approval.get("valid_from_block") != request["valid_from_block"]
            or approval.get("valid_through_block") != request["valid_through_block"]
        ):
            _refuse("APPROVAL_DOES_NOT_NAME_THIS_REQUEST")

        source = request.get("source_intent", {})
        intent_digest = od4a._digest(intent) if type(intent) is dict else None
        if not _trusted_intent(intent):
            _refuse("INTENT_NOT_TRUSTED_ALL_BURN")
        if (
            intent_digest != source.get("digest")
            or intent["key_id"] != source.get("key_id")
            or intent["payload"]["pool_version"] != source.get("pool_version")
        ):
            _refuse("INTENT_NOT_APPROVED")

        pinned = request["runtime_probe"]
        if (now is None) != (probe is None):
            _refuse("DISPATCH_NEEDS_TIME_AND_PROBE")
        if probe is not None and (
            type(probe) is not dict
            or probe.get("status") != "COMPATIBLE_USED_SURFACE"
            or probe.get("surface_digest") != pinned["surface_digest"]
            or probe.get("spec_version") != request["expected_runtime_spec"]
            or str(probe.get("context", {}).get("genesis_hash")).lower()
            != TESTNET_GENESIS
            or type(probe["context"].get("finalized_block")) is not int
            or probe["context"]["finalized_block"] < pinned["finalized_block"]
        ):
            _refuse("RUNTIME_PROBE_CHANGED")

        if type(authorization) is not DevelopmentTransactionAuthorization:
            _refuse("TRANSACTION_AUTHORIZATION_REQUIRED")
        chain = authorization.context
        if (
            authorization.authorization_id != request["authorization_id"]
            or authorization.authority_record_digest != approval_digest
            or authorization.source_intent_digest != intent_digest
            or authorization.publisher_hotkey != request["publisher"]["hotkey"]
            or authorization.expected_runtime_spec != request["expected_runtime_spec"]
            or authorization.valid_from_block != request["valid_from_block"]
            or authorization.valid_through_block != request["valid_through_block"]
            or (chain.network, chain.endpoint, chain.provider, chain.netuid)
            != (
                "testnet",
                context["endpoint"],
                context["chain_id"],
                signing.NETUID,
            )
            or chain.genesis_hash.lower() != TESTNET_GENESIS
        ):
            _refuse("AUTHORIZATION_NOT_BOUND_TO_APPROVAL")
        return cls(
            _token=_VERIFIED,
            authorization=authorization,
            authorization_id=request["authorization_id"],
            approval_digest=approval_digest,
            request_digest=request["request_digest"],
            intent=json.loads(json.dumps(intent)),
            intent_digest=intent_digest,
            context=chain,
            expected_runtime_spec=request["expected_runtime_spec"],
            expires=expires,
        )


@dataclass(frozen=True, slots=True)
class BatteryAllBurnWeightIntent:
    identity: str
    digest: str

    def __post_init__(self):
        if (
            type(self.identity) is not str
            or type(self.digest) is not str
            or len(self.digest) != 64
            or any(c not in "0123456789abcdef" for c in self.digest)
        ):
            _refuse("INVALID_BATTERY_INTENT_REFERENCE")


class BatteryAllBurnIntentIssuer:
    """Stores the approved envelope and nothing else; one identity per approval."""

    def __init__(self, receipts, approved):
        from carbon.transport.store import ReceiptJournal

        if type(approved) is not ApprovedPublication:
            _refuse("APPROVED_PUBLICATION_REQUIRED")
        if type(receipts) is not ReceiptJournal or receipts.context != approved.context:
            _refuse("BATTERY_PUBLICATION_CONTEXT_REQUIRED")
        self.receipts = receipts
        self.approved = approved
        self.profile = DevelopmentTestnetProfile(
            approved.context, approved.expected_runtime_spec
        )
        with receipts.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS battery_od4a_intent_v1 "
                "(identity TEXT PRIMARY KEY, digest TEXT NOT NULL, body TEXT NOT NULL)"
            )

    def _body(self):
        approved = self.approved
        return encode(
            {
                "schema": INTENT_SCHEMA,
                "identity": approved.authorization_id,
                "stage": "PUBLIC_TESTNET_DEVELOPMENT",
                "maturity": "DEVELOPMENT_ONLY",
                "authority": "OWNER-BATTERY-TESTNET-01 OD-4a",
                "context": asdict(approved.context),
                "runtime_spec": approved.expected_runtime_spec,
                "mechanism_id": 0,
                "request_digest": approved.request_digest,
                "approval_digest": approved.approval_digest,
                "source_intent_digest": approved.intent_digest,
                "source_intent": approved.intent,
                "route": "ALL_BURN",
                "no_winner": True,
            }
        )

    def issue(self):
        body = self._body()
        key = digest(body.encode())
        identity = self.approved.authorization_id
        with self.receipts.transaction() as db:
            row = db.execute(
                "SELECT digest,body FROM battery_od4a_intent_v1 WHERE identity=?",
                (identity,),
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO battery_od4a_intent_v1 VALUES (?,?,?)",
                    (identity, key, body),
                )
            elif row != (key, body):
                _refuse("CONFLICTING_BATTERY_INTENT")
        return BatteryAllBurnWeightIntent(identity, key)

    def resolve(self, ref, snapshot):
        if type(ref) is not BatteryAllBurnWeightIntent:
            _refuse("BATTERY_INTENT_REQUIRED")
        with self.receipts.transaction() as db:
            row = db.execute(
                "SELECT digest,body FROM battery_od4a_intent_v1 WHERE identity=?",
                (ref.identity,),
            ).fetchone()
        # The stored body must be byte-identical to the one the approval
        # produces, so an edited journal row cannot carry another intent.
        if (
            row is None
            or row != (ref.digest, self._body())
            or digest(row[1].encode()) != ref.digest
        ):
            _refuse("UNKNOWN_OR_ALTERED_BATTERY_INTENT")
        body = json.loads(row[1])
        if (
            body["source_intent_digest"] != self.approved.intent_digest
            or od4a._digest(body["source_intent"]) != self.approved.intent_digest
            or not _trusted_intent(body["source_intent"])
            or body["context"] != asdict(snapshot.context)
            or snapshot.context != self.approved.context
        ):
            _refuse("INTENT_NOT_APPROVED")
        projection = {
            "schema": "carbon.battery.od4a-all-burn-projection.v1",
            "maturity": "DEVELOPMENT_ONLY",
            "route": "ALL_BURN",
            "context": body["context"],
            "targets": {"challenges": [], "winners": [], "burn": Q12},
        }
        return {"intent": body, "projection": projection}


class BatteryAllBurnPublisher(DevelopmentTestnetPublisher):
    """The shared checked publisher, bound to one approved battery intent.

    Inherits the block window, the one-dispatch consumption record, fee and
    spend 0, the runtime and genesis checks and no-resend reconciliation.
    Adds, at every stage and again just before signing: the approved intent
    digest, netuid 567, the all-burn row at UID 0, and the request expiry.
    """

    ISSUER_TYPE = BatteryAllBurnIntentIssuer
    INTENT_TYPE = BatteryAllBurnWeightIntent
    BINDS_SOURCE_INTENT = True

    def __init__(self, issuer, backend, authorization, *, clock=_utc_now):
        if type(issuer) is not BatteryAllBurnIntentIssuer:
            _refuse("APPROVED_BATTERY_ISSUER_REQUIRED")
        if authorization != issuer.approved.authorization:
            _refuse("AUTHORIZATION_NOT_BOUND_TO_APPROVAL")
        self.clock = clock
        super().__init__(issuer, backend, authorization)

    def validate_stage(self, ref, snapshot, capabilities, resolved, plan):
        approved = self.issuer.approved
        if self.clock() >= approved.expires:
            _refuse("REQUEST_EXPIRED")
        if (
            ref.identity != approved.authorization_id
            or resolved["intent"]["source_intent_digest"] != approved.intent_digest
            or self.authorization.source_intent_digest != approved.intent_digest
        ):
            _refuse("INTENT_NOT_APPROVED")
        if (
            snapshot.context.network != "testnet"
            or snapshot.context.netuid != signing.NETUID
        ):
            _refuse("TESTNET_567_ONLY")
        if (
            plan.burn_uid != BURN_UID
            or plan.publisher_uid != BURN_UID
            or plan.q12 != ((BURN_UID, Q12),)
            or plan.integers != ((BURN_UID, U16_MAX),)
        ):
            _refuse("ROW_NOT_APPROVED_ALL_BURN")
        super().validate_stage(ref, snapshot, capabilities, resolved, plan)


def _read_json(path):
    return json.loads(Path(path).read_bytes())


class _JournalLock:
    """An exclusive, non-blocking lock on one dispatch journal, held for the
    whole of a `run` or `resume`, so two processes can never both sign. The
    lock file sits beside the journal; the OS releases it if the process dies.
    Only `_JournalLock.hold` makes one, and composition requires a held one."""

    __slots__ = ("_handle",)

    def __init__(self, handle, *, _token=None):
        if _token is not _VERIFIED:
            raise TypeError("a journal lock comes only from _JournalLock.hold")
        self._handle = handle

    @classmethod
    def hold(cls, journal):
        import fcntl
        import os

        path = Path(str(journal) + ".lock")
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(descriptor)
            _refuse("DISPATCH_JOURNAL_LOCKED")
        return cls(descriptor, _token=_VERIFIED)

    def held(self):
        return self._handle is not None

    def release(self):
        import os

        if self._handle is not None:
            os.close(self._handle)
            object.__setattr__(self, "_handle", None)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()


async def _live_probe(config):
    """The runtime surface read from the chain now, never from a file."""
    from carbon.chain.runtime_probe import probe

    return await probe(config.endpoint, config.genesis_hash)


def _approved(args, config, now, probe=None):
    return ApprovedPublication.verify(
        request=_read_json(args.request),
        approval_bytes=Path(args.approval).read_bytes(),
        intent=_read_json(args.intent),
        probe=probe,
        authorization=config.transaction_authorization,
        now=now,
    )


def _composition(args, config, backend, lock, now, probe=None):
    from carbon.transport.store import ReceiptJournal

    if type(lock) is not _JournalLock or not lock.held():
        _refuse("DISPATCH_JOURNAL_LOCK_REQUIRED")
    approved = _approved(args, config, now, probe)
    issuer = BatteryAllBurnIntentIssuer(
        ReceiptJournal(Path(args.journal), config.context), approved
    )
    return issuer, BatteryAllBurnPublisher(issuer, backend, approved.authorization)


async def _run(args, config):
    from carbon.chain.sdk_weights import BittensorPublicationBackend
    from carbon.development_testnet.operator import _wallet, doctor

    with _JournalLock.hold(args.journal) as lock:
        # Every binding, including the runtime surface read live from the
        # chain, is verified before the wallet is touched.
        _approved(args, config, _utc_now(), await _live_probe(config))
        report = await doctor(config, online=True)
        if report["chain_transaction_ready"] is not True:
            _refuse("CHAIN_TRANSACTION_NOT_READY")
        backend = BittensorPublicationBackend(
            config.context, config.publisher_hotkey, _wallet(config), network="testnet"
        )
        try:
            issuer, publisher = _composition(
                args, config, backend, lock, _utc_now(), await _live_probe(config)
            )
            return await publisher.publish(issuer.issue())
        finally:
            await backend.close()


async def _resume(args, config):
    from carbon.chain.sdk_weights import BittensorPublicationBackend

    with _JournalLock.hold(args.journal) as lock:
        backend = BittensorPublicationBackend(
            config.context, config.publisher_hotkey, None, network="testnet"
        )
        try:
            issuer, publisher = _composition(args, config, backend, lock, None)
            return await publisher.reconcile(issuer.issue().digest)
        finally:
            await backend.close()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m carbon.battery.od4a_dispatch")
    parser.add_argument("command", choices=("verify", "run", "resume"))
    for name in ("config", "request", "approval", "intent", "journal"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument(
        "--probe",
        type=Path,
        help="verify only: an offline probe report; run always probes live",
    )
    args = parser.parse_args(argv)
    from carbon.development_testnet.operator import load_config

    try:
        config = load_config(args.config.absolute())
        if config.context is None or config.netuid != signing.NETUID:
            _refuse("TESTNET_567_ONLY")
        if config.transaction_authorization is None:
            _refuse("TRANSACTION_AUTHORIZATION_REQUIRED")
        if (args.command == "verify") != (args.probe is not None):
            # verify is offline and checks a supplied report; run reads the
            # runtime live and refuses a file, so a stale report cannot stand in.
            _refuse("PROBE_FILE_ONLY_FOR_VERIFY")
        if args.command == "verify":
            approved = _approved(args, config, _utc_now(), _read_json(args.probe))
            result = {
                "verified": True,
                "authorization_id": approved.authorization_id,
                "request_digest": approved.request_digest,
                "source_intent_digest": approved.intent_digest,
                "wallet_read": False,
                "chain_read": False,
            }
        elif args.command == "run":
            result = asyncio.run(_run(args, config))
        else:
            result = asyncio.run(_resume(args, config))
    except DispatchRefused as refused:
        print(json.dumps({"status": "REFUSED", "reason": str(refused)}))
        return 2
    except Exception:  # noqa: BLE001 - no provider, wallet or input text echoed
        print(json.dumps({"status": "FAILED_CLOSED"}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
