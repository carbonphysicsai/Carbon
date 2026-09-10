"""Localnet publisher orchestration, durable ambiguity and explicit stale exposure."""

import asyncio
import uuid
from dataclasses import dataclass

from carbon.rewards.core import RewardFailure
from carbon.rewards.intents import LocalnetIntentIssuer, StructuralLocalnetWeightIntent
from carbon.transport.models import digest

from .dispatch import TERMINAL, DispatchJournal
from .models import ChainFailure
from .publication import (
    CompiledTargets,
    PublicationFailure,
    RuntimeCapabilities,
    compile_targets,
    validate_integers,
)


@dataclass(frozen=True)
class TransactionObservation:
    success: bool
    block: int
    block_hash: str


def load_plan(value):
    raw = dict(value)
    raw["q12"] = tuple(tuple(p) for p in raw["q12"])
    raw["integers"] = tuple(tuple(p) for p in raw["integers"])
    return CompiledTargets(**raw)


def load_caps(value):
    raw = dict(value)
    raw["owner_hotkeys"] = tuple(raw["owner_hotkeys"])
    return RuntimeCapabilities(**raw)


class LocalnetPublisher:
    def __init__(self, issuer, backend):
        if (
            type(issuer) is not LocalnetIntentIssuer
            or backend.context != issuer.receipts.context
        ):
            raise PublicationFailure("LOCALNET_ISSUER_CONTEXT_REQUIRED")
        self.issuer, self.backend = issuer, backend
        self.journal = DispatchJournal(issuer.receipts)
        self._lock = asyncio.Lock()
        self.last_status = "NOT_STARTED_STORED_EXPOSURE_UNKNOWN"

    async def publish(self, ref):
        if type(ref) is not StructuralLocalnetWeightIntent:
            raise PublicationFailure("LOCALNET_INTENT_REQUIRED")
        async with self._lock:
            old = self.journal.get(ref.digest)
            if old:
                if old["document"]["intent"]["identity"] != ref.identity:
                    raise PublicationFailure("CONFLICTING_INTENT_REFERENCE")
                return old
            if self.journal.pending():
                raise PublicationFailure("RECONCILE_PENDING_DISPATCH_FIRST")
            snapshot, caps = await self.backend.observe()
            resolved = self.issuer.resolve(ref, snapshot)
            plan = compile_targets(resolved, snapshot, caps, self.backend.publisher)
            self.journal.prepare(ref, plan, snapshot, caps)

            async def current():
                fresh, fresh_caps = await self.backend.observe()
                latest = compile_targets(
                    self.issuer.resolve(ref, fresh),
                    fresh,
                    fresh_caps,
                    self.backend.publisher,
                )
                if (
                    latest.q12 != plan.q12
                    or latest.publisher_uid != plan.publisher_uid
                    or latest.burn_uid != plan.burn_uid
                ):
                    raise PublicationFailure("EXECUTION_RECIPIENTS_CHANGED")
                for key in (
                    "spec_version",
                    "mechanism_count",
                    "maximum_mechanisms",
                    "burn_mode",
                    "owner_coldkey",
                    "owner_hotkey",
                    "owner_hotkeys",
                    "min_weights",
                    "max_weight",
                    "version_key",
                    "commit_reveal",
                ):
                    if getattr(fresh_caps, key) != getattr(caps, key):
                        raise PublicationFailure("EXECUTION_RUNTIME_CHANGED")
                return fresh, fresh_caps

            async def integers(uids, values, preflight):
                _, fresh_caps = await current()
                if (
                    preflight.uid,
                    preflight.min_allowed_weights,
                    preflight.max_weight_limit,
                    preflight.commit_reveal,
                ) != (
                    plan.publisher_uid,
                    fresh_caps.min_weights,
                    fresh_caps.max_weight,
                    fresh_caps.commit_reveal,
                ):
                    raise PublicationFailure("SDK_REBUILT_DIFFERENT_CAPABILITIES")
                validate_integers(plan, uids, values, fresh_caps)
                self.journal.update(
                    ref.digest,
                    "VALIDATED",
                    integers=[list(p) for p in zip(uids, values)],
                )

            async def call_checked(call, extras):
                if (
                    call.spec_version != caps.spec_version
                    or type(call.data) is not bytes
                ):
                    raise PublicationFailure("SDK_CALL_RUNTIME_MISMATCH")
                self.journal.update(
                    ref.digest,
                    "VALIDATED",
                    call_hash=digest(call.data),
                    reveal_round=extras.get("reveal_round"),
                )

            async def before_sign(call, signer):
                await current()
                row = self.journal.get(ref.digest)
                if (
                    signer != plan.publisher
                    or row["tracking"]["call_hash"] != digest(call.data)
                    or row["tracking"]["integers"] is None
                ):
                    raise PublicationFailure("UNCHECKED_CALL_OR_SIGNER")
                self.journal.update(ref.digest, "SIGNING")

            async def before_dispatch(tx_hash):
                if self.journal.get(ref.digest)["state"] != "SIGNING":
                    raise PublicationFailure("UNJOURNALED_SIGNING")
                self.journal.update(ref.digest, "DISPATCHED", tx_hash=tx_hash)

            reason = None
            try:
                await self.backend.execute(
                    plan, integers, call_checked, before_sign, before_dispatch
                )
            except (PublicationFailure, RewardFailure) as error:
                reason = str(error)
            except ChainFailure as error:
                reason = error.code.value
            except Exception:  # noqa: BLE001 - redact SDK/provider payloads
                reason = "PROVIDER_OR_SDK_OUTCOME_AMBIGUOUS"
            if reason:
                row = self.journal.get(ref.digest)
                state = (
                    "FAILED_BEFORE_SIGNING"
                    if row["state"] in ("PREPARED", "VALIDATED")
                    else "AMBIGUOUS"
                )
                return self.journal.update(ref.digest, state, reason=reason)
            return await self.reconcile(ref.digest)

    async def reconcile(self, identity):
        """Scan at most 256 finalized blocks per call. Never resubmit a transaction."""
        row = self.journal.get(identity)
        if row is None:
            raise PublicationFailure("UNKNOWN_DISPATCH")
        if row["state"] in TERMINAL:
            return row
        tracking, document = row["tracking"], row["document"]
        if tracking["tx_hash"] is None:
            return self.journal.update(
                identity,
                "AMBIGUOUS",
                reason="INTERRUPTED_BEFORE_TRANSACTION_HASH_REQUIRES_OPERATOR_RECONCILIATION",
            )
        snapshot, observed_caps = await self.backend.observe()
        plan, caps = load_plan(document["plan"]), load_caps(document["capabilities"])
        if (
            snapshot.context != self.backend.context
            or snapshot.finalized_block < document["snapshot"]["finalized_block"]
        ):
            raise PublicationFailure("RECONCILIATION_CHAIN_MISMATCH")
        start = tracking["scan_block"]
        end = min(snapshot.finalized_block, start + 255)
        for block in range(start, end + 1):
            if tracking["included_block"] is None:
                result = await self.backend.transaction(tracking["tx_hash"], block)
                if result is not None:
                    if (
                        type(result) is not TransactionObservation
                        or result.block != block
                    ):
                        raise PublicationFailure("MALFORMED_TRANSACTION_OBSERVATION")
                    self.journal.update(
                        identity,
                        "INCLUDED",
                        included_block=block,
                        included_hash=result.block_hash,
                    )
                    self.journal.update(identity, "FINALIZED", finalized_block=block)
                    if not result.success:
                        return self.journal.update(
                            identity,
                            "CHAIN_REJECTED",
                            reason="FINALIZED_CHAIN_REJECTION",
                        )
                    tracking = self.journal.get(identity)["tracking"]
            if (
                tracking["included_block"] is not None
                and plan.commit_reveal
                and not tracking["revealed"]
                and block > tracking["included_block"]
                and await self.backend.revealed(plan.publisher, block)
            ):
                tracking = self.journal.update(
                    identity, "FINALIZED", revealed=True, reveal_block=block
                )["tracking"]
        if end >= start:
            self.journal.update(
                identity, self.journal.get(identity)["state"], scan_block=end + 1
            )
        row = self.journal.get(identity)
        tracking = row["tracking"]
        if tracking["included_block"] is None:
            return self.journal.update(
                identity,
                "AMBIGUOUS",
                reason="TRANSACTION_NOT_YET_FOUND_IN_FINALIZED_BACKFILL",
            )
        if plan.commit_reveal and not tracking["revealed"]:
            return self.journal.update(
                identity, "REVEAL_PENDING", reason="FINALIZED_COMMIT_IS_NOT_REVEAL"
            )
        for key in (
            "spec_version",
            "burn_mode",
            "owner_coldkey",
            "owner_hotkey",
            "owner_hotkeys",
        ):
            if getattr(observed_caps, key) != getattr(caps, key):
                return self.journal.update(
                    identity,
                    "EXPOSURE_CHANGED",
                    reason="RUNTIME_BURN_EXPOSURE_CHANGED_AFTER_FINALIZATION",
                )
        for uid, _ in plan.q12:
            old_recipient = document["snapshot"]["participants"][uid]
            recipient = snapshot.resolve(old_recipient["hotkey"])
            if recipient is None or (
                recipient.uid,
                recipient.coldkey,
                recipient.registered_at,
            ) != (uid, old_recipient["coldkey"], old_recipient["registered_at"]):
                return self.journal.update(
                    identity,
                    "EXPOSURE_CHANGED",
                    reason="RECIPIENT_IDENTITY_CHANGED_AFTER_FINALIZATION_REFRESH_TARGETS",
                )
        old_member = next(
            p
            for p in document["snapshot"]["participants"]
            if p["hotkey"] == plan.publisher
        )
        member = snapshot.resolve(plan.publisher)
        if member is None or (member.uid, member.coldkey, member.registered_at) != (
            old_member["uid"],
            old_member["coldkey"],
            old_member["registered_at"],
        ):
            return self.journal.update(
                identity,
                "EXPOSURE_CHANGED",
                reason="PUBLISHER_IDENTITY_CHANGED_STORED_ROW_UNKNOWN",
            )
        stored, last_update = await self.backend.weight_row(
            snapshot, plan.publisher_uid
        )
        if last_update < tracking["included_block"]:
            return self.journal.update(
                identity, "FINALIZED", reason="STORED_ROW_NOT_UPDATED"
            )
        try:
            validate_integers(
                plan, [p[0] for p in stored], [p[1] for p in stored], caps
            )
        except PublicationFailure:
            return self.journal.update(
                identity,
                "FINALIZED",
                stored_row=stored,
                row_block=snapshot.finalized_block,
                reason="STORED_ROW_DIFFERS_FROM_TARGET",
            )
        return self.journal.update(
            identity,
            "ROW_VERIFIED",
            stored_row=stored,
            row_block=snapshot.finalized_block,
            reason=None,
        )

    async def heartbeat(self, request_id):
        """One operator-scheduled tick; pending effects reconcile before new issuance."""
        pending = self.journal.pending()
        if pending:
            return await self.reconcile(pending)
        return await self.publish(await self.issuer.issue(request_id))

    def exposure(self):
        pending = self.journal.pending()
        return {
            "publisher_status": self.last_status,
            "pending_dispatch": pending,
            "stored_weights_may_remain_effective": True,
            "settlement": "OBSERVE_CHAIN_SEPARATELY",
            "operator_action": (
                "RECONCILE_PENDING"
                if pending
                else "KEEP_HEARTBEAT_AND_READBACK_RUNNING"
            ),
        }

    async def run(self, stop, *, interval_seconds=5, max_ticks=None):
        """Explicit operator-owned DEVELOPMENT loop; shutdown does not clear weights."""
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 30:
            raise PublicationFailure("INVALID_DEVELOPMENT_HEARTBEAT_INTERVAL")
        if max_ticks is not None and (type(max_ticks) is not int or max_ticks < 1):
            raise PublicationFailure("INVALID_HEARTBEAT_LIMIT")
        ticks = 0
        while not stop.is_set():
            try:
                result = await self.heartbeat("heartbeat-" + uuid.uuid4().hex)
                self.last_status = result["state"]
            except (PublicationFailure, RewardFailure) as error:
                self.last_status = str(error)
            except ChainFailure as error:
                self.last_status = error.code.value
            except Exception:  # noqa: BLE001 - redact provider diagnostics
                self.last_status = "PUBLISHER_UNAVAILABLE_STORED_EXPOSURE_UNKNOWN"
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass
        return self.exposure()
