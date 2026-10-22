"""Signed DEVELOPMENT ConstructionRecipe receiver using the existing intake shell.

This prospective receiver shares the Battery intake's bounded HTTP listener,
peer limits, snapshot window and authenticated transport. It has its own
registered Challenge and task adapter; it never calls the Battery daemon or
claims a Score Pack, official verdict, qualification or reward.
"""

from __future__ import annotations

import asyncio
import base64
import socket
import threading
import time

from carbon.battery.intake import (
    SNAPSHOT_MAX_AGE_S,
    SOCKET_TIMEOUT_S,
    Answer,
    BatteryIntake,
    IntakeUnavailable,
    SnapshotWindow,
    _handler,
    _Pinned,
    _refused,
    hardened_listener,
    is_loopback,
    log,
    refresher,
)
from carbon.chain.auth import AuthFailure
from carbon.miner_mcp.research import decode_research_call
from carbon.research import (
    RESEARCH_NAMESPACE,
    DirectPublicResearchContext,
    LocalResearchService,
    canonical_bytes,
)
from carbon.transport.gateway import AuthenticatedGateway
from carbon.transport.models import (
    MAX_BODY,
    PATH,
    TransportCode,
    TransportFailure,
    parse_message,
)

from .dispatch import Adapters, Validator
from .interface import Submission, Unavailable
from .lean_recipe import LeanRecipeAdapter

INFO_PATH = "/carbon/v1/construction/intake"
SUBMIT_PATH = PATH
SUBMIT_TOOL = "construction_submit"
STATUS_TOOL = "construction_status"
#: The signed read of the caller's own private-exam Ladder documents, its best
#: and its latest (OWNER-GRADE-FEEDBACK-LADDER-01). Advertised in its own facts entry, not
#: in `tools`, which deployed clients pin exactly.
FEEDBACK_TOOL = "exam_feedback"
FEEDBACK_REPLY_SCHEMA = "carbon.private-exam.ladder-feedback-reply.v1"
PUBLIC_SCHEMA = "carbon.construction.intake-public.v1"
SOURCE_REPLY_SCHEMA = "carbon.construction.source-stage-reply.v1"


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
        measure_query: bool = False,
        copy_hotkey: str | None = None,
        clock_ns=time.time_ns,
    ):
        adapter = LeanRecipeAdapter(
            discovery,
            provider_for,
            attempt_ledger,
            measure_query=measure_query,
            copy_hotkey=copy_hotkey,
        )
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
                "discovery_path": INFO_PATH,
                "path": SUBMIT_PATH,
                "tools": [SUBMIT_TOOL, STATUS_TOOL, RESEARCH_NAMESPACE],
                "source_staging": {
                    "tool": RESEARCH_NAMESPACE,
                    "operation": "stage_research_source",
                    "request_schema": "direct_stage_source_request_v1",
                    "reply_schema": SOURCE_REPLY_SCHEMA,
                    "path": SUBMIT_PATH,
                    "owner": "authenticated_hotkey",
                },
                **(
                    {
                        "material_staging": {
                            "tool": RESEARCH_NAMESPACE,
                            "operation": "stage_research_material",
                            "request_schema": "direct_stage_material_request_v1",
                            "reply_schema": SOURCE_REPLY_SCHEMA,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        }
                    }
                    if "stage_research_material"
                    in self.adapter.discovery.manifest.supported_operations
                    else {}
                ),
                "exam_feedback": {
                    "tool": FEEDBACK_TOOL,
                    "fields": [],
                    "reply_schema": FEEDBACK_REPLY_SCHEMA,
                    "path": SUBMIT_PATH,
                    "owner": "authenticated_hotkey",
                },
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
        if method != "POST" or path != SUBMIT_PATH:
            return _refused(404, "not_found")
        return asyncio.run(self._post(headers, body))

    async def _post(self, headers, body):
        try:
            envelope = parse_message(body)
        except TransportFailure as failure:
            self._malformed_diagnostics.note(failure, headers)
            return _refused(400, failure.code.value)
        snapshot = self.window.get(envelope["snapshot"])
        if snapshot is None:
            return _refused(409, "snapshot_unknown")
        gateway = AuthenticatedGateway(
            self.context,
            self.challenge,
            self.receiver,
            _Pinned(snapshot),
            self.verifier,
            self.journal,
            clock_ns=self.clock_ns,
        )
        try:
            received = await gateway.receive(
                body, headers, method="POST", path=SUBMIT_PATH
            )
        except TransportFailure as failure:
            self._malformed_diagnostics.note(failure, headers)
            return _refused(
                401 if failure.code is TransportCode.IDENTITY else 400,
                failure.code.value,
            )
        except AuthFailure as failure:
            return _refused(401, failure.code.value)
        if received.call.tool == RESEARCH_NAMESPACE:
            return self._stage_source(received)
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
        if received.call.tool == FEEDBACK_TOOL:
            if fields:
                return _refused(400, "feedback_fields")
            return self._feedback(received.receipt.hotkey)
        return _refused(400, "tool")

    def _feedback(self, hotkey):
        """The caller's own best and latest Ladder documents for the active exam
        (each None until there is one): nothing else, and never another hotkey's
        (the signed hotkey is the key)."""
        from .ladder_store import LadderStore, LadderStoreRefused

        snapshot = getattr(self.adapter.discovery, "evaluation_pack_snapshot", None)
        exam_key = getattr(snapshot, "manifest_digest", None)
        documents = {"best": None, "latest": None}
        if exam_key is not None:
            try:
                documents = LadderStore(self.adapter.ledger).served(
                    hotkey, self.challenge, exam_key
                )
            except LadderStoreRefused:
                return _refused(503, "feedback_unavailable")
        return Answer(
            200,
            {
                "schema": FEEDBACK_REPLY_SCHEMA,
                "challenge": {
                    "id": self.challenge.challenge_id,
                    "version": self.challenge.version,
                },
                "best": documents["best"],
                "latest": documents["latest"],
            },
        )

    def _stage_source(self, received):
        """Stage graph bytes in the exact receiver-owned construction workspace.

        The existing research codec and service own bounds, digest checks,
        compare-and-swap and typed failures. No caller can choose an owner,
        ledger, host path, image or task operation through this route.
        """
        try:
            call = decode_research_call(received.call)
        except (ValueError, TypeError):
            return _refused(400, "source_staging_fields")
        if (
            call.operation not in {"stage_research_source", "stage_research_material"}
            or call.request.challenge_key != self.challenge
        ):
            return _refused(400, "source_staging_context")
        try:
            provider = self.adapter._provider(received.receipt.hotkey)
        except Unavailable as unavailable:
            return _refused(503, unavailable.code)
        service = LocalResearchService(
            DirectPublicResearchContext(
                self.adapter.discovery, self.adapter.discovery, provider
            )
        )
        reply = service.call(call)
        return Answer(
            200,
            {
                "schema": SOURCE_REPLY_SCHEMA,
                "protocol_reply_base64": base64.b64encode(
                    canonical_bytes(reply)
                ).decode("ascii"),
            },
        )

    def advance(self):
        """Operator-only single-task progress; the HTTP route never invokes it."""
        return self.adapter.advance()

    def regrade_result(
        self,
        entry_id,
        *,
        artifact_directory,
        entry_directory,
        promotion=None,
        exam_se=False,
    ):
        """Operator-only regrade of a retained model on the selected pack; never a route."""
        from .lean_recipe_retention import regrade_retained_entry

        return regrade_retained_entry(
            self.adapter,
            entry_id,
            artifact_directory=artifact_directory,
            entry_directory=entry_directory,
            promotion=promotion,
            exam_se=exam_se,
        )

    def retain_result(
        self,
        submission_id,
        *,
        artifact_directory,
        entry_directory,
        pool_store=None,
    ):
        """Operator-only post-outcome bank custody; never an HTTP route."""
        from .lean_recipe_retention import retain_served_bundle_result

        return retain_served_bundle_result(
            self.adapter,
            submission_id,
            artifact_directory=artifact_directory,
            entry_directory=entry_directory,
            pool_store=pool_store,
        )


def _header_bounded_handler(intake):
    """The maintained handler with an absolute deadline through header parsing."""

    class Handler(_handler(intake)):
        def setup(self):
            super().setup()
            self._header_expired = threading.Event()
            self._header_timer = threading.Timer(SOCKET_TIMEOUT_S, self._expire_header)
            self._header_timer.daemon = True
            self._header_timer.start()

        def _expire_header(self):
            self._header_expired.set()
            try:
                self.connection.shutdown(socket.SHUT_RD)
            except OSError:
                pass

        def parse_request(self):
            try:
                parsed = super().parse_request()
            finally:
                self._header_timer.cancel()
            return parsed and not self._header_expired.is_set()

        def finish(self):
            self._header_timer.cancel()
            super().finish()

    return Handler


def serve_loopback(
    intake: DirectRecipeIntake, config, *, stop, reader=None, ready=None, closing=None
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
    httpd = hardened_listener(
        config, _header_bounded_handler(intake), service="construction-intake"
    )
    # Join already-authenticated bounded handlers before taking the final
    # cancellation snapshot. Otherwise a submit may queue after cancellation.
    httpd.daemon_threads = False
    threads = [
        threading.Thread(
            target=refresher,
            args=(intake.window, intake.context),
            kwargs={"stop": stop, "reader": reader},
            daemon=True,
        ),
        threading.Thread(target=_advance_loop, args=(intake, stop), daemon=True),
    ]
    host, port = httpd.server_address[:2]
    serving = threading.Thread(target=httpd.serve_forever, daemon=True)
    started = []
    try:
        serving.start()
        for thread in threads:
            thread.start()
            started.append(thread)
        if ready is not None:
            ready((host, port))
        stop.wait()
    finally:
        stop.set()
        try:
            if serving.is_alive():
                httpd.shutdown()
            httpd.server_close()
        finally:
            try:
                if closing is not None:
                    closing()
            finally:
                # Cancel through the durable task API, then retain provider
                # ownership until the finite carrier observes stop.
                if threads[1] in started:
                    threads[1].join()
                if threads[0] in started:
                    threads[0].join(5)
                if serving.ident is not None:
                    serving.join(5)


def _advance_loop(intake, stop):
    while not stop.is_set():
        try:
            intake.advance()
        except Exception as failure:  # noqa: BLE001 - no private content in log
            log("direct_worker_failure", type=type(failure).__name__)
        stop.wait(1)
