"""Signed DEVELOPMENT ConstructionRecipe receiver using the existing intake shell.

This prospective receiver shares the Battery intake's bounded HTTP listener,
peer limits, snapshot window and authenticated transport. It has its own
registered Challenge and task adapter; it never calls the Battery daemon or
claims a Score Pack, official verdict, qualification or reward.
"""

from __future__ import annotations

import asyncio
import threading
import time

from carbon.battery.intake import (
    Answer,
    BatteryIntake,
    IntakeUnavailable,
    SNAPSHOT_MAX_AGE_S,
    SnapshotWindow,
    _handler,
    _refused,
    hardened_listener,
    is_loopback,
    log,
    refresher,
)
from carbon.chain.auth import AuthFailure
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import MAX_BODY, TransportCode, TransportFailure

from .dispatch import Adapters, Validator
from .interface import Submission
from .lean_recipe import LeanRecipeAdapter

INFO_PATH = "/carbon/v1/construction/intake"
SUBMIT_TOOL = "construction_submit"
STATUS_TOOL = "construction_status"
PUBLIC_SCHEMA = "carbon.construction.intake-public.v1"


class _CurrentSnapshot:
    """The trusted window's current snapshot for the existing gateway."""

    def __init__(self, window):
        self.window = window

    async def observe(self, *, minimum_finalized_block):
        snapshot = self.window.latest()
        if snapshot is None or snapshot.finalized_block < minimum_finalized_block:
            raise TransportFailure(TransportCode.STALE)
        return snapshot


class DirectRecipeIntake(BatteryIntake):
    """One trusted, registered synthetic DEVELOPMENT contract per listener."""

    def __init__(
        self,
        *,
        context,
        receiver,
        journal,
        verifier,
        window: SnapshotWindow,
        discovery,
        provider_for,
        attempt_ledger,
        clock_ns=time.time_ns,
    ):
        adapter = LeanRecipeAdapter(discovery, provider_for, attempt_ledger)
        door = Validator(Adapters([adapter]), attempt_ledger)
        super().__init__(
            context=context,
            receiver=receiver,
            journal=journal,
            verifier=verifier,
            inbox=None,
            window=window,
            status_reader=None,
            door=door,
            clock_ns=clock_ns,
            commitment="not_checked: public DEVELOPMENT construction only",
        )
        self.challenge = discovery.info.challenge_key
        self.adapter = adapter
        self.gateway = AuthenticatedGateway(
            context,
            self.challenge,
            receiver,
            _CurrentSnapshot(window),
            verifier,
            journal,
            clock_ns=clock_ns,
        )

    def public(self):
        snapshot = self.window.latest()
        if snapshot is None:
            return _refused(503, "snapshot_unavailable")
        return Answer(
            200,
            {
                "schema": PUBLIC_SCHEMA,
                "network": self.context.network,
                "genesis": self.context.genesis_hash,
                "netuid": self.context.netuid,
                "challenge": {
                    "id": self.challenge.challenge_id,
                    "version": self.challenge.version,
                },
                "receiver": self.receiver,
                "snapshot": {
                    "id": snapshot.snapshot_id,
                    "finalized_block": snapshot.finalized_block,
                    "timestamp_ms": snapshot.timestamp_ms,
                },
                "path": INFO_PATH,
                "tools": [SUBMIT_TOOL, STATUS_TOOL],
                "served_contracts": self.door.served_contracts(),
                "limits": {
                    "max_body": MAX_BODY,
                    "snapshot_max_age_s": SNAPSHOT_MAX_AGE_S,
                    "signature_max_age_s": 10.0,
                },
                "score_pack": None,
                "qualification": False,
                "reward": False,
            },
        )

    def route(self, method, path, headers, body):
        if method == "GET" and path == INFO_PATH:
            return self.public()
        if method != "POST" or path != INFO_PATH:
            return _refused(404, "not_found")
        return asyncio.run(self._post(headers, body))

    async def _post(self, headers, body):
        try:
            received = await self.gateway.receive(body, headers)
        except TransportFailure as failure:
            self._malformed_diagnostics.note(failure, headers)
            return _refused(
                401 if failure.code is TransportCode.IDENTITY else 400,
                failure.code.value,
            )
        except AuthFailure as failure:
            return _refused(401, failure.code.value)
        fields = {field.name: field.value for field in received.call.fields}
        if received.call.tool == SUBMIT_TOOL:
            if set(fields) != {"strategy_json", "contract_digest"}:
                return _refused(400, "submission_fields")
            receipt = received.receipt
            submitted = Submission(
                hotkey=receipt.hotkey,
                receipt={
                    "sequence": receipt.ref.sequence,
                    "digest": receipt.ref.digest,
                    "block": receipt.finalized_block,
                },
                challenge_id=self.challenge.challenge_id,
                challenge_version=self.challenge.version,
                strategy_json=fields["strategy_json"],
                contract_digest=fields["contract_digest"],
            )
            result = self.door.evaluate(submitted)
            if result["kind"] == "OUTCOME":
                return Answer(202, result)
            return Answer(
                503 if result["kind"] in ("UNAVAILABLE", "FAILED_INFRA") else 400,
                result,
            )
        if received.call.tool == STATUS_TOOL:
            if (
                set(fields) != {"submission_id"}
                or type(fields["submission_id"]) is not str
            ):
                return _refused(400, "status_fields")
            return Answer(
                200,
                self.door.outcome(
                    self.adapter.contract_digest,
                    fields["submission_id"],
                    received.receipt.hotkey,
                ),
            )
        return _refused(400, "tool")

    def advance(self):
        """Operator-only single-task progress; the HTTP route never invokes it."""
        return self.adapter.advance()


def serve_loopback(
    intake: DirectRecipeIntake, config, *, stop, reader=None, ready=None
):
    """Serve the prospective receiver on a trusted loopback test host."""
    host = config.get("host")
    if (
        type(intake) is not DirectRecipeIntake
        or type(host) is not str
        or not is_loopback(host)
    ):
        raise IntakeUnavailable("direct_intake_loopback_required")
    if config.get("exposure") is not None:
        raise IntakeUnavailable("direct_intake_exposure_unserved")
    httpd = hardened_listener(config, _handler(intake), service="construction-intake")
    threads = [
        threading.Thread(
            target=refresher,
            args=(intake.window, intake.context),
            kwargs={"stop": stop, "reader": reader},
            daemon=True,
        ),
        threading.Thread(target=_advance_loop, args=(intake, stop), daemon=True),
    ]
    for thread in threads:
        thread.start()
    host, port = httpd.server_address[:2]
    try:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        if ready is not None:
            ready((host, port))
        stop.wait()
    finally:
        httpd.shutdown()
        httpd.server_close()
        for thread in threads:
            thread.join(5)


def _advance_loop(intake, stop):
    while not stop.is_set():
        try:
            intake.advance()
        except Exception as failure:  # noqa: BLE001 - no private content in log
            log("direct_worker_failure", type=type(failure).__name__)
        stop.wait(1)
