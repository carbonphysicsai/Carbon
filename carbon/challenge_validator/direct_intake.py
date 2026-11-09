"""Signed DEVELOPMENT ConstructionRecipe receiver using the existing intake shell.

This prospective receiver shares the Battery intake's bounded HTTP listener,
peer limits, snapshot window and authenticated transport. It has its own
registered Challenge and task adapter; it never calls the Battery daemon or
claims a Score Pack, official verdict, qualification or reward.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
import socket
import threading
import time
import traceback
from pathlib import Path

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

from . import funder_map as funder_maps
from . import koth_public, queue_public
from .dispatch import Adapters, Validator
from .interface import Submission, Unavailable
from .lean_recipe import LeanRecipeAdapter
from .request_buckets import claimed_hotkey

INFO_PATH = "/carbon/v1/construction/intake"
#: The signed launch board: `GET FEED_PATH + <challenge id>` (the battery door's feed path).
FEED_PATH = "/carbon/v1/feed/"
#: How long the published readiness is reused: reading it verifies the whole official receipt log.
OFFICIAL_GPU_CACHE_SECONDS = 10.0
SUBMIT_PATH = PATH
SUBMIT_TOOL = "construction_submit"
STATUS_TOOL = "construction_status"
#: The signed read of the caller's own private-exam Ladder documents, its best
#: and its latest (OWNER-GRADE-FEEDBACK-LADDER-01). Advertised in its own facts entry, not
#: in `tools`, which deployed clients pin exactly.
FEEDBACK_TOOL = "exam_feedback"
FEEDBACK_REPLY_SCHEMA = "carbon.private-exam.ladder-feedback-reply.v1"
#: The same read for one of the caller's own submissions: v1's fields plus that submission's grade
#: state. Advertised in its own facts entry (``exam_feedback_v2``) only by a receiver that grades its
#: own submissions, so the v1 entry deployed clients pin is unchanged.
FEEDBACK_REPLY_SCHEMA_V2 = "carbon.private-exam.ladder-feedback-reply.v2"
#: The closed grade states of a v2 reply (`DirectRecipeIntake._grade_state`); None is none of these.
GRADE_STATES = (
    "GRADED",
    "QUEUED",
    "SUPERSEDED_BY_OWN_LATER_SUBMIT",
    "ROUND_LIMIT_REACHED",
)
#: v3 = v2 plus CANDIDATE_FAILED (the official wall rule, Validator 22:40): a v2 reply keeps it None, so a
#: deployed v2 client, which pins `GRADE_STATES`, still parses every reply. Advertised as ``exam_feedback_v3``.
FEEDBACK_REPLY_SCHEMA_V3 = "carbon.private-exam.ladder-feedback-reply.v3"
GRADE_STATES_V3 = (*GRADE_STATES, "CANDIDATE_FAILED")
#: v4 = v3 plus the states a v3 reply leaves None (or QUEUED), and WHY a candidate run failed (Validator 4 Nov 03:17 (3)
#: and 07:18: v2 stays closed, v3 untouched). RECONSTRUCTION_FAILED: the task's own build or inference child failed, nothing
#: graded. FAILED_INFRA: Carbon's side failed, nothing charged. NOT_GRADED: the grade could not be computed, the slot given
#: back. Advertised as ``exam_feedback_v4``.
FEEDBACK_REPLY_SCHEMA_V4 = "carbon.private-exam.ladder-feedback-reply.v4"
#: v5 (Miner X-B / TE-B 7 Nov) = v4 plus CROWN_HELD_FOR_REVIEW for the caller's own submission while its crown change is
#: held for review on a menu-D version (`crown_hold`), and ``held_position`` {place (1-based, filing order), of}, else
#: None. No id and nothing of another miner. Advertised as ``exam_feedback_v5``.
FEEDBACK_REPLY_SCHEMA_V5 = "carbon.private-exam.ladder-feedback-reply.v5"
HELD_STATE = "CROWN_HELD_FOR_REVIEW"
GRADE_STATES_V4 = (
    *GRADE_STATES_V3,
    "RECONSTRUCTION_FAILED",
    "FAILED_INFRA",
    "NOT_GRADED",
)
#: The v4 ``failure`` is built from these closed values ONLY (an allow-list, never a filtered private record): the failing
#: child, the observation CLASS, the registered limit that applied (its name in the public resource policy and that public
#: value), and for a reconstruction the public refusal code `construction_status` already shows. Nothing measured: no
#: seconds, memory, cases, exit codes, output text or digests (the inference child runs on hidden inputs: a side channel).
FAILURE_CHILDREN = ("build", "inference")
FAILURE_OBSERVATIONS = (
    "WORKER_MEMORY_LIMIT_REACHED",
    "WORKER_WALL_LIMIT_REACHED",
    "OOM_KILLED",
    "NONZERO_EXIT",
    "OWN_ALLOWANCE_ELAPSED",
)
FAILURE_LIMITS = (
    "memory_bytes_max",
    "build_wall_seconds_max",
    "inference_wall_seconds_max",
)
FAILURE_KEYS = ("child", "observation", "limit", "code")
PUBLIC_SCHEMA = "carbon.construction.intake-public.v1"
SOURCE_REPLY_SCHEMA = "carbon.construction.source-stage-reply.v1"


def feedback_reply(fields):
    """Which per-submission feedback reply a signed request's fields ask for: ``"v2"`` (``submission_id`` alone),
    ``"v3"`` or ``"v4"`` (``reply`` + ``submission_id``), or None for anything else (refused ``feedback_fields``).
    """
    if type(fields.get("submission_id")) is not str:
        return None
    if set(fields) == {"submission_id"}:
        return "v2"
    if set(fields) == {"reply", "submission_id"} and fields["reply"] in (
        "v3",
        "v4",
        "v5",
    ):
        return fields["reply"]
    return None


class DirectRecipeIntake(BatteryIntake):
    """One trusted, registered synthetic DEVELOPMENT contract per listener."""

    #: Reached through a local hop (an ssh forward, the operator's tools): the listener shares one
    #: loopback address across its clients and answers past capacity with a typed 503; reads
    #: are not charged to a peer bucket (`battery.intake`, GPU_REBUILD_RULINGS section 12).
    local_hop = True

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
        speed_sample_key: bytes | None = None,
        request_buckets=None,
        funder_map=None,
        clock_ns=time.time_ns,
    ):
        adapter = LeanRecipeAdapter(
            discovery,
            provider_for,
            attempt_ledger,
            measure_query=measure_query,
            copy_hotkey=copy_hotkey,
            speed_sample_key=speed_sample_key,
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
        #: The receiver's public king view (`koth_public`); None until it publishes one.
        self.koth_view = None
        #: The public queue view (`queue_public`, `queue_view.QueueView`); None when this door does not grade.
        self.queue_view = None
        #: The signed launch board's reader (`launch_board_file.read_board` bound to the
        #: configured file), or None when this receiver serves no board.
        self.board_feed = None
        #: The auto-grade marker reader (`AutoGrader.marker`), or None when this receiver does not
        #: grade its own submissions (then no grade state is served).
        self.grade_marker = None
        #: One writer at a time for the calls that change state (an admission or a source
        #: stage): the cap, idempotency and the once-per-epoch rule hold exactly under any
        #: number of concurrent clients (GPU_REBUILD_RULINGS section 12). Reads (the public
        #: facts, status, the Ladder) never take it.
        self._write = threading.Lock()
        #: R89: the per-group request buckets (`request_buckets.RequestBuckets`), or None (the peer bucket, as before).
        self.request_buckets = request_buckets
        #: The allowance-group map; swapped whole on a reload, so a reload never empties a bucket.
        self.funder_map = (
            funder_maps.FunderMap.empty() if funder_map is None else funder_map
        )

    def _current_map(self):
        """The funder map to use now: re-read when the configured file changed (`funder_map.Watched`, set by the
        receiver as ``funder_map_watch``), swapped whole, so R89 and the exam cap's grouping read ONE copy.
        """
        watch = getattr(self, "funder_map_watch", None)
        if watch is not None:
            self.funder_map = watch.current()
        return self.funder_map

    def _claimed_group(self, headers):
        """The group of the hotkey a POST CLAIMS, if it is registered in the latest snapshot; else None. Unverified:
        used only to peek, never to charge."""
        hotkey = claimed_hotkey(headers)
        snapshot = self.window.latest() if hotkey is not None else None
        member = None if snapshot is None else snapshot.resolve(hotkey)
        return None if member is None else self._current_map().group(member.coldkey)

    def admit_before_body(self, method, peer, headers):
        """R89 before the body: an unattributable POST takes a guard token; a POST naming a registered hotkey is
        only peeked (refused at once when its group has no token left). Without request buckets, or for a GET,
        the peer bucket as before."""
        buckets = self.request_buckets
        if buckets is None or method != "POST":
            return super().admit_before_body(method, peer, headers)
        group = self._claimed_group(headers)
        return (
            buckets.charge_guard("unattributed")
            if group is None
            else buckets.peek_group(group)
        )

    def note_capacity(self):
        """The listener's 503 capacity answer, counted for the hourly request-buckets line (no buckets: nothing)."""
        if self.request_buckets is not None:
            self.request_buckets.note("capacity_503")

    def _unverified(self, answer):
        """A POST that failed before or at verification: charged to the guard (never to a group), then refused."""
        if self.request_buckets is not None:
            self.request_buckets.charge_guard("verify_failed")
        return answer

    def _verified_charge(self, received):
        """R89 after verification over a fresh nonce: charge the verified group's chunk bucket (a continuation
        chunk) or its request bucket. True when admitted, or when this door has no request buckets.
        """
        if self.request_buckets is None:
            return True
        chunk = False
        if received.call.tool == RESEARCH_NAMESPACE:
            try:
                call = decode_research_call(received.call)
            except (ValueError, TypeError):
                call = None
            chunk = (
                call is not None
                and call.operation == "stage_research_source"
                and self._continues_upload(received.receipt.hotkey, call.request)
            )
        group = self._current_map().group(received.receipt.coldkey)
        return self.request_buckets.charge_group(group, chunk=chunk)

    def _continues_upload(self, hotkey, request):
        """Whether a verified source chunk continues this hotkey's own staged upload at its current length (Validator-2B
        7 Nov R89 condition): a read of its workspace, never a stage. Any failure to read says no (a request).
        """
        from carbon.development_session.direct_source_staging import continuation_at

        try:
            provider = self.adapter._provider(hotkey)
            return continuation_at(provider.ledger, provider.owner, request)
        except Exception:  # noqa: BLE001 - unreadable = not a continuation
            return False

    def _official_gpu(self):
        """Readiness for the public info document (`served.official_readiness`), cached for a few seconds: it
        verifies the receipt log. Never an error: a failure is a typed status with an empty list.
        """
        now = time.monotonic()
        cached = getattr(self, "_official_gpu_cache", None)
        if cached is not None and now - cached[0] < OFFICIAL_GPU_CACHE_SECONDS:
            return dict(cached[1])
        try:
            from carbon.backbone_catalog import served

            runtimes = getattr(self.adapter, "_gpu_runtimes", None)
            value = served.official_readiness(
                self.challenge.challenge_id,
                self.challenge.version,
                tuple(runtimes()) if callable(runtimes) else (),
            )
        except Exception:  # noqa: BLE001 - never an error page
            value = {"status": "UNAVAILABLE", "ready": [], "log_head": None}
        self._official_gpu_cache = (now, value)
        return dict(value)

    def _catalog_digest(self):
        """The digest of the catalog this version serves (public: every catalog recipe names it); None if it has none."""
        try:
            from carbon.backbone_catalog import served

            return served.digest(self.challenge.challenge_id, self.challenge.version)
        except Exception:  # noqa: BLE001 - never an error page
            return None

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
                "exam_feedback": {
                    "tool": FEEDBACK_TOOL,
                    "fields": [],
                    "reply_schema": FEEDBACK_REPLY_SCHEMA,
                    "path": SUBMIT_PATH,
                    "owner": "authenticated_hotkey",
                },
                **(
                    {}
                    if getattr(self, "grade_marker", None) is None
                    else {
                        "exam_feedback_v2": {
                            "tool": FEEDBACK_TOOL,
                            "fields": ["submission_id"],
                            "reply_schema": FEEDBACK_REPLY_SCHEMA_V2,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        },
                        "exam_feedback_v3": {
                            "tool": FEEDBACK_TOOL,
                            "fields": ["reply", "submission_id"],
                            "reply_schema": FEEDBACK_REPLY_SCHEMA_V3,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        },
                        "exam_feedback_v4": {
                            "tool": FEEDBACK_TOOL,
                            "fields": ["reply", "submission_id"],
                            "reply_schema": FEEDBACK_REPLY_SCHEMA_V4,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        },
                        "exam_feedback_v5": {
                            "tool": FEEDBACK_TOOL,
                            "fields": ["reply", "submission_id"],
                            "reply_schema": FEEDBACK_REPLY_SCHEMA_V5,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        },
                    }
                ),
                "served_contracts": self.door.served_contracts(),
                # Which catalog entries are officially gradable now: ids and the receipt log's head digest only.
                "official_gpu": self._official_gpu(),
                "catalog_digest": self._catalog_digest(),
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
        if method == "GET" and path.startswith(koth_public.PATH):
            return self._koth(path)
        if method == "GET" and path.startswith(queue_public.PATH):
            return self._queue(path)
        if method == "GET" and path == FEED_PATH + self.challenge.challenge_id:
            return self._board()
        if method != "POST" or path != SUBMIT_PATH:
            return _refused(404, "not_found")
        return asyncio.run(self._post(headers, body))

    def _board(self):
        """The operator-signed launch board of this receiver's one Challenge
        (`launch_board_file`): served only when its signature, shape and Challenge
        verify; this door holds no key."""
        if self.board_feed is None:
            return _refused(404, "feed_not_served")
        found = self.board_feed()
        if found is None:
            return _refused(503, "feed_unavailable")
        return Answer(200, found)

    def _koth(self, path):
        """The public king document of this receiver's one Challenge; any other
        Challenge id is not found."""
        from urllib.parse import unquote

        asked = unquote(path[len(koth_public.PATH) :])
        serve = koth_public.serve
        if asked.endswith(koth_public.V2_SUFFIX):
            # the v2 document at its own path; v1 is served unchanged at the existing one
            asked, serve = asked[: -len(koth_public.V2_SUFFIX)], koth_public.serve_v2
        if asked != self.challenge.challenge_id:
            return _refused(404, "not_found")
        status, body = serve(self.koth_view, self.challenge)
        return Answer(status, body)

    def _held(self):
        """The held contenders' ids in filing order on a crown-hold door (`queue_view.QueueView.held`), else None."""
        view = getattr(self, "queue_view", None)
        return None if view is None else view.held()

    def _queue(self, path):
        """The public queue document of this receiver's one Challenge (`queue_public`): v1 at its path, v2 at the same
        path + ``/v2``; any other id is not found."""
        from urllib.parse import unquote

        asked, serve = unquote(path[len(queue_public.PATH) :]), queue_public.serve
        if asked.endswith(queue_public.V2_SUFFIX):
            asked, serve = asked[: -len(queue_public.V2_SUFFIX)], queue_public.serve_v2
        if asked != self.challenge.challenge_id:
            return _refused(404, "not_found")
        status, body = serve(self.queue_view, self.challenge)
        return Answer(status, body)

    async def _post(self, headers, body):
        try:
            envelope = parse_message(body)
        except TransportFailure as failure:
            self._malformed_diagnostics.note(failure, headers)
            return self._unverified(_refused(400, failure.code.value))
        snapshot = self.window.get(envelope["snapshot"])
        if snapshot is None:
            return self._unverified(_refused(409, "snapshot_unknown"))
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
            return self._unverified(
                _refused(
                    401 if failure.code is TransportCode.IDENTITY else 400,
                    failure.code.value,
                )
            )
        except AuthFailure as failure:
            return self._unverified(_refused(401, failure.code.value))
        if not self._verified_charge(received):
            return _refused(429, "rate")
        if received.call.tool == RESEARCH_NAMESPACE:
            with self._write:
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
            result = self._admit(submitted)
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
            if not fields:
                return self._feedback(received.receipt.hotkey)
            reply = feedback_reply(fields)
            if reply is None:
                return _refused(400, "feedback_fields")
            return self._feedback(
                received.receipt.hotkey,
                submission_id=fields["submission_id"],
                v3=reply == "v3",
                v4=reply in ("v4", "v5"),
                v5=reply == "v5",
            )
        return _refused(400, "tool")

    def _admit(self, submitted):
        """The one admission path: a single writer, so a duplicate is admitted once."""
        with self._write:
            result = self.door.evaluate(submitted)
            self._note_recipe_digest(result)
            return result

    def _note_recipe_digest(self, result):
        """OWNER-PROBING-COUNTERS-01 (b): store an admitted task's recipe digest at admission (`recipe_copies.
        note_admitted`), so a restart cannot make a later copy read as fresh. Best effort: never changes the answer.
        """
        outcome = result.get("outcome") if type(result) is dict else None
        task_id = outcome.get("task_id") if type(outcome) is dict else None
        if type(task_id) is not str or not hasattr(
            getattr(self.adapter, "ledger", None), "_db"
        ):
            return
        from . import recipe_copies

        try:
            recipe_copies.note_admitted(self.adapter, task_id)
        except Exception:  # noqa: BLE001 - never changes the admission
            return

    def _feedback(self, hotkey, *, submission_id=None, v3=False, v4=False, v5=False):
        """The caller's own best and latest Ladder documents for the active exam
        (each None until there is one): nothing else, and never another hotkey's
        (the signed hotkey is the key). With ``submission_id`` (v2), also that
        submission's grade state; an id the caller does not own and an unknown id
        are refused with the same code, so the read says nothing of other keys."""
        from .ladder_store import LadderStore, LadderStoreRefused

        if submission_id is not None:
            if getattr(self, "grade_marker", None) is None:
                return _refused(503, "grade_state_unavailable")
            if self.adapter.owner(submission_id) != hotkey:
                return _refused(404, "feedback_submission_unknown")
            failure = None
            if v4:
                try:
                    grade_state, failure = self._grade_state_v4(hotkey, submission_id)
                except (Unavailable, LookupError, ValueError, OSError):
                    return _refused(503, "grade_state_unavailable")
            else:
                grade_state = self._grade_state(hotkey, submission_id)
            held_position = None
            if v5:
                try:
                    held = self._held()
                except (LookupError, ValueError, OSError):
                    return _refused(503, "grade_state_unavailable")
                if held and submission_id in held:
                    grade_state = HELD_STATE
                    held_position = {
                        "place": held.index(submission_id) + 1,
                        "of": len(held),
                    }
            if not (v3 or v4) and grade_state not in GRADE_STATES:
                grade_state = (
                    None  # CANDIDATE_FAILED is v3's; a v2 reply keeps its closed set
                )
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
                **(
                    {}
                    if submission_id is None
                    else {
                        "schema": (
                            FEEDBACK_REPLY_SCHEMA_V5
                            if v5
                            else (
                                FEEDBACK_REPLY_SCHEMA_V4
                                if v4
                                else (
                                    FEEDBACK_REPLY_SCHEMA_V3
                                    if v3
                                    else FEEDBACK_REPLY_SCHEMA_V2
                                )
                            )
                        ),
                        "submission": {
                            "submission_id": submission_id,
                            "grade_state": grade_state,
                            **({"failure": failure} if v4 else {}),
                            **({"held_position": held_position} if v5 else {}),
                        },
                    }
                ),
            },
        )

    def _grade_state(self, hotkey, submission_id):
        """One of `GRADE_STATES` for the caller's own submission, from its auto-grade marker
        (`AutoGrader.marker`) and the exam slot rows of its round, or None for none of them (a
        failed grade, or a grade refused for any reason but the two limits).

        No marker yet: QUEUED. A computed grade: GRADED. Refused at a limit: SUPERSEDED_BY_OWN_LATER_SUBMIT
        when the slot of the submission's round is held by the caller's own LATER submission (a later
        submit built first and took it), else ROUND_LIMIT_REACHED. No time, count or other key is read
        out."""
        from .exam_cap import later_own_holds_the_round

        marker = self.grade_marker(submission_id)
        if marker is None:
            return "QUEUED"
        if marker.get("state") == "CANDIDATE_FAILED":
            return "CANDIDATE_FAILED"
        if marker.get("state") != "GRADED":
            return None
        if marker.get("code") is None:
            return "GRADED"
        if marker.get("code") not in (
            "epoch_limit_reached",
            "exam_daily_allowance_reached",
        ):
            return None
        return (
            "SUPERSEDED_BY_OWN_LATER_SUBMIT"
            if later_own_holds_the_round(
                self.adapter.ledger,
                self.adapter.contract_digest,
                hotkey=hotkey,
                challenge_id=self.challenge.challenge_id,
                submission_id=submission_id,
            )
            else "ROUND_LIMIT_REACHED"
        )

    def _grade_state_v4(self, hotkey, submission_id):
        """``(grade_state, failure)`` of the caller's own submission for a v4 reply: one of `GRADE_STATES_V4` (never
        None), and the allow-listed `failure` of a failed candidate run (`failure_v4`) or None.

        No marker: the task itself says RECONSTRUCTION_FAILED (its build or its own inference child failed) or
        FAILED_INFRA, else QUEUED (v3 says QUEUED for both). A FAILED marker is Carbon's failure (FAILED_INFRA); a
        CANDIDATE_FAILED one is the inference child at the graded wall. A grade whose reason v3 leaves None is GRADED
        while its slot is held (a counted outcome), else NOT_GRADED (given back, nothing charged).
        """
        marker = self.grade_marker(submission_id)
        if marker is None:
            projected = self.adapter.outcome(submission_id)
            state = projected.get("state")
            if state == "RECONSTRUCTION_FAILED":
                child, observation = self.adapter.failed_child(submission_id)
                code = (projected.get("failure") or {}).get("code")
                return state, self.failure_v4(child, observation, code)
            return ("FAILED_INFRA" if state == "FAILED_INFRA" else "QUEUED"), None
        if marker.get("state") == "CANDIDATE_FAILED":
            return "CANDIDATE_FAILED", self.failure_v4("inference", marker.get("code"))
        if marker.get("state") == "DUPLICATE":
            # A copy of a recipe already graded on this key (OWNER-PROBING-COUNTERS-01 (b)): its own slot is counted
            # (no free probe), so v4 says GRADED, never NOT_GRADED ('given back, nothing charged': Validator-2B 7 Nov).
            # Nothing of the first's is added to the copier's reply: not its id, its owner or its private feedback.
            return "GRADED", None
        if marker.get("state") == "FAILED":
            return "FAILED_INFRA", None
        state = self._grade_state(hotkey, submission_id)
        if state is not None:
            return state, None
        from .exam_cap import ExamCap

        held = ExamCap(self.adapter.ledger).holds_slot(
            hotkey=hotkey,
            challenge_id=self.challenge.challenge_id,
            challenge_version=self.challenge.version,
            exam_key=self.adapter.discovery.evaluation_pack_snapshot.manifest_digest,
            submission_id=submission_id,
        )
        return ("GRADED" if held else "NOT_GRADED"), None

    def failure_v4(self, child, observation, code=None):
        """The v4 ``failure``: exactly `FAILURE_KEYS`, each from a closed value set (anything else becomes None). The
        limit is named only for a memory or wall observation, with the value the PUBLIC resource policy registers.
        """
        child = child if child in FAILURE_CHILDREN else None
        observation = observation if observation in FAILURE_OBSERVATIONS else None
        name = None
        if observation in ("WORKER_MEMORY_LIMIT_REACHED", "OOM_KILLED"):
            name = "memory_bytes_max"
        elif observation == "WORKER_WALL_LIMIT_REACHED" and child is not None:
            name = child + "_wall_seconds_max"
        limit = None
        if name in FAILURE_LIMITS:
            try:
                value = self.adapter.discovery._material[
                    "construction_limits_document"
                ]["reconstruction_resource_policy"][name]
            except (AttributeError, KeyError, TypeError):
                value = None
            if type(value) is int and value > 0:
                limit = {"name": name, "value": value}
        public_code = (
            code
            if type(code) is str and re.fullmatch(r"[a-z0-9_]{1,64}", code)
            else None
        )
        return {
            "child": child,
            "observation": observation,
            "limit": limit,
            "code": public_code,
        }

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
        # OWNER-DOOR-A-NARROW-01: the door stages graph source only. Any other operation
        # (stage_research_material included) is refused before any provider or service call.
        if (
            call.operation != "stage_research_source"
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
    intake: DirectRecipeIntake,
    config,
    *,
    stop,
    reader=None,
    ready=None,
    closing=None,
    grader=None,
    grading_lock_dir=None,
    state_dir=None,
):
    """Serve the prospective receiver on a trusted loopback test host.

    ``state_dir`` (the receiver's state): where the per-door DRAINING flag is read and the in-flight record kept
    (`_WorkLock`)."""
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
        config,
        _header_bounded_handler(intake),
        service="construction-intake",
        local_hop=True,
    )
    # Join already-authenticated bounded handlers before taking the final
    # cancellation snapshot. Otherwise a submit may queue after cancellation.
    httpd.daemon_threads = False
    work = _WorkLock(grading_lock_dir, state_dir=state_dir, stop=stop)
    threads = [
        threading.Thread(
            target=refresher,
            args=(intake.window, intake.context),
            kwargs={"stop": stop, "reader": reader},
            daemon=True,
        ),
        threading.Thread(target=_advance_loop, args=(intake, stop, work), daemon=True),
    ]
    if grader is not None:
        # A receiver that grades its own submissions (auto_grade): one grade at a
        # time, never while a reconstruction runs.
        if getattr(grader, "others_waiting", None) is None:
            # slow-tail F2: the king's upkeep waits while another door waits for the host lock
            grader.others_waiting = getattr(work, "_others_waiting", None)
        threads.append(
            threading.Thread(target=_grade_loop, args=(grader, stop, work), daemon=True)
        )
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


#: Seconds a background loop waits after its nth consecutive failure: a bounded
#: exponential backoff (an operational bound, not a scientific value). A loop
#: that keeps failing is never a once-a-second hot loop, and a success resets it.
FAILURE_BACKOFF_S = (1, 2, 4, 8, 15, 30, 60, 120, 300)


def _backoff_s(failures):
    return FAILURE_BACKOFF_S[min(failures, len(FAILURE_BACKOFF_S)) - 1]


def _keep_failure(subject, loop, failure):
    """Keep a failure's full traceback in the receiver's PRIVATE evidence
    directory, one file per distinct failure site, and return the site's short
    id for the log line. The log carries the exception type and this id only:
    a traceback can hold private paths and content. Best effort: a subject
    without a ledger, or an unwritable directory, keeps nothing."""
    try:
        ledger = getattr(getattr(subject, "adapter", subject), "ledger", None)
        path = getattr(ledger, "path", None)
        frames = traceback.extract_tb(failure.__traceback__)
        site = hashlib.sha256(
            "|".join(
                [type(failure).__name__]
                + [f"{Path(f.filename).name}:{f.name}:{f.lineno}" for f in frames]
            ).encode()
        ).hexdigest()[:16]
        if path is None:
            return site
        directory = Path(path).parent / "worker-failures"
        directory.mkdir(mode=0o700, exist_ok=True)
        record = directory / f"{loop}-{site}.txt"
        if not record.exists():
            text = "".join(traceback.format_exception(failure))
            fd = os.open(record, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                out.write(time.strftime("%Y-%m-%dT%H:%M:%SZ\n", time.gmtime()))
                out.write(text)
        return site
    except Exception:  # noqa: BLE001 - evidence is best effort
        return None


#: Per-door drain and in-flight records in the receiver's state directory (MAINNET_UPDATE_ARCHITECTURE s2.4 Step A).
DRAIN_NAME = "draining"
INFLIGHT_NAME = "work-inflight.json"
WAIT_NAME = "work-wait.json"
#: The host's list of doors waiting for the grading lock with a grade to run (in the lock's own directory).
WAITING_DIR = "official-grading.waiting"
#: Set-aside (stale) records kept per kind; older ones are removed at start.
STALE_KEPT = 5
INFLIGHT_SCHEMA = "carbon.challenge-validator.work-inflight.v1"
#: How often a door retries the host's official-grading lock, and re-reads stop and DRAINING, while it waits
#: (an operational poll period, not a scientific value).
WORK_POLL_S = 1.0
#: A waiting door refreshes its entry every poll; an entry not refreshed for this long is not a waiter (a frozen
#: process never holds the round-robin): an operational value, not a scientific one.
WAITER_STALE_S = 30.0


class WorkDeclined(Exception):
    """This round takes no work: ``stopping``, ``draining`` or ``idle`` (nothing to do). Never a failure."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _process_start(pid):
    """The kernel's start time of ``pid`` (clock ticks since boot), or None: with the pid it names one process."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as handle:
            return int(handle.read().rsplit(b")", 1)[1].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _write_record(path, body):
    """Atomic: a temp file beside ``path``, fsynced, put in place by rename. A reader sees the whole record or none."""
    import json

    staged = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}")
    with open(staged, "w", encoding="utf-8") as handle:
        json.dump(body, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(staged, 0o600)
    os.replace(staged, path)


class _WorkLock:
    """The one lock the reconstruction pass and the grade share (one at a time), plus, when ``grading_lock_dir`` is
    set, the host's official-grading file lock (the same file `receipt_job.official_grading` holds): held for each
    whole official rebuild and grade, so one grade runs per host at a time and the standing receipt worker starts no
    lane meanwhile. Released on every exit path.

    A door never BLOCKS waiting for either lock (MAINNET_UPDATE_ARCHITECTURE s2.4 Step A): it polls every
    `WORK_POLL_S` and gives up the round (`WorkDeclined`) as soon as the receiver is stopping or the operator set
    DRAINING (``<state>/draining``), so a stopped receiver never starts work after SIGTERM and a draining door holds
    no item while it waits. With ``state_dir`` it also keeps:

    - ``work-inflight.json`` while it holds the lock (kind, pid + process start, since): written and removed
      atomically. A deploy's idle check reads THIS door's record, never the host lock (another door grading is not
      this door being busy). A record left by a crash is set aside at start (renamed, logged), never trusted;
    - ``work-wait.json`` while a door with work waits for the host lock (since when): the input for a starvation
      alert, whose threshold is the host's measured longest grade wall (not set here).
    """

    def __init__(
        self, grading_lock_dir=None, *, state_dir=None, stop=None, poll_s=None
    ):
        self._lock = threading.Lock()
        self._dir = grading_lock_dir
        self._state = None if state_dir is None else Path(state_dir)
        self._stop = stop if stop is not None else threading.Event()
        self._poll = WORK_POLL_S if poll_s is None else poll_s
        self._fd = None
        self._legacy = threading.local()
        self._yield_until = 0.0
        self._was_draining = None
        #: This door's place in the host's waiting list (`_mark_waiting`): the time its current GRADE round began to
        #: wait, or None. A grade round takes the host lock only when no live other door has waited longer.
        self._wait_since = None
        self._grade_round = False
        if self._state is not None:
            for name in (INFLIGHT_NAME, WAIT_NAME):
                left = self._state / name
                if left.exists():
                    # This process holds nothing yet: whatever is there is a previous process's, never trusted.
                    aside = left.with_name(f"{name}.stale-{time.time_ns()}")
                    os.replace(left, aside)
                    log("direct_work_record_stale", record=name, kept_as=aside.name)
            for name in (INFLIGHT_NAME, WAIT_NAME):
                # A writer's temp files (a crash mid-write) are never records: removed. Set-aside records: newest kept.
                for staged in self._state.glob(f".{name}.*"):
                    staged.unlink(missing_ok=True)
                for old in sorted(self._state.glob(f"{name}.stale-*"))[:-STALE_KEPT]:
                    old.unlink(missing_ok=True)
        # Said once at start, and on every change: a door left DRAINING after a switch is never silent.
        self.draining()

    def draining(self):
        draining = self._state is not None and (self._state / DRAIN_NAME).exists()
        if draining != self._was_draining:
            self._was_draining = draining
            if self._state is not None:
                log("direct_work_draining", draining=draining)
        return draining

    def _declined(self):
        if self._stop.is_set():
            return "stopping"
        if self.draining():
            return "draining"
        return None

    def _waiting_dir(self):
        return Path(self._dir) / WAITING_DIR

    def _waiters(self):
        """``[(since_ns, pid)]`` of every LIVE other process (another door) waiting for the host lock with a grade to
        run. An entry whose process is gone (pid reused or exited) is not a waiter; one without a readable time
        counts as waiting since 0 (oldest: never lets a door jump it)."""
        mine = os.getpid()
        try:
            entries = list(self._waiting_dir().iterdir())
        except OSError:
            return []
        live = []
        for entry in entries:
            pid, _, started = entry.name.partition("-")
            if not (pid.isdigit() and started.isdigit()) or int(pid) == mine:
                continue
            if _process_start(int(pid)) != int(started):
                continue
            try:
                if time.time() - entry.stat().st_mtime > WAITER_STALE_S:
                    continue
                since = int(entry.read_text().strip() or 0)
            except (OSError, ValueError):
                since = 0
            live.append((since, int(pid)))
        return live

    def _others_waiting(self):
        """Whether another live process (another door) waits for the host lock with a grade to run."""
        return bool(self._waiters())

    def _behind_an_earlier_waiter(self):
        """Whether a GRADE round must let another door go first: a live other door has waited longer (round-robin
        across doors, Deploy 5 Nov: Motor's due king work lost the race to three doors for over an hour). A round that
        is not yet waiting counts as arriving now, so it queues behind every current waiter; ties go to the lower
        pid. Advance rounds never queue (they cannot tell whether they have work), as before.
        """
        if not self._grade_round:
            return False
        mine = (
            time.time_ns() if self._wait_since is None else self._wait_since,
            os.getpid(),
        )
        return any(other < mine for other in self._waiters())

    def _mark_waiting(self, waiting):
        """This door's entry in the host's waiting list (``<lock dir>/official-grading.waiting/<pid>-<start>``), holding
        the time it began to wait (its place in the round-robin)."""
        path = self._waiting_dir() / f"{os.getpid()}-{_process_start(os.getpid())}"
        if waiting:
            if self._wait_since is not None and path.exists():
                os.utime(path)  # still waiting: refreshed every poll (`WAITER_STALE_S`)
                return
            self._waiting_dir().mkdir(mode=0o700, exist_ok=True)
            if self._wait_since is None:
                self._wait_since = time.time_ns()
            staged = path.with_name(f".{path.name}.{threading.get_ident()}")
            staged.write_text(str(self._wait_since))
            os.chmod(staged, 0o600)
            os.replace(staged, path)
        else:
            path.unlink(missing_ok=True)
            self._wait_since = None

    def _try_host(self):
        """Take the host's official-grading lock without blocking; True when held. A door that has just released it
        while another door waits stands back for 2 polls first, so a busy door's back-to-back rounds never shut
        a polling door out (fairness without a queue: the waiter's next poll falls inside the gap).
        """
        import fcntl

        from carbon.backbone_catalog.receipt_job import GRADING_LOCK

        if time.monotonic() < self._yield_until:
            return False
        if self._behind_an_earlier_waiter():
            return False
        fd = os.open(Path(self._dir) / GRADING_LOCK, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return False
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        return True

    def _release_host(self):
        import fcntl

        fd, self._fd = self._fd, None
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
            if self._others_waiting():
                self._yield_until = time.monotonic() + 2 * self._poll

    def taking(self, kind, *, has_work=None):
        """A context for one round of ``kind`` work (``advance`` or ``grade``). ``has_work`` (called under the
        door's own lock) lets a round with nothing to do skip the host lock entirely (`WorkDeclined("idle")`).
        """
        return _Taking(self, kind, has_work)

    # The earlier ``with work:`` form (one advance round), kept for callers outside this module; per thread.
    def __enter__(self):
        taking = self.taking("advance")
        self._legacy.taking = taking
        return taking.__enter__()

    def __exit__(self, *exc):
        taking, self._legacy.taking = self._legacy.taking, None
        return taking.__exit__(*exc)


class _Taking:
    """One round of work under `_WorkLock`; see there."""

    def __init__(self, work, kind, has_work):
        self.work, self.kind, self.has_work = work, kind, has_work

    def _inflight(self):
        return {
            "schema": INFLIGHT_SCHEMA,
            "kind": self.kind,
            "pid": os.getpid(),
            "pid_start": _process_start(os.getpid()),
            "since_ns": time.time_ns(),
        }

    def __enter__(self):
        work = self.work
        while not work._lock.acquire(timeout=work._poll):
            reason = work._declined()
            if reason is not None:
                raise WorkDeclined(reason)
        recorded = False
        # Only a GRADE with work waits visibly (the starvation-alert input and the host's waiting list): an advance
        # round cannot tell whether it has work, and must never look like a starving door.
        visible = self.kind == "grade" and self.has_work is not None
        work._grade_round = visible
        work._wait_since = None
        waiting = False
        try:
            reason = work._declined()
            if reason is not None:
                raise WorkDeclined(reason)
            if self.has_work is not None and not self.has_work():
                raise WorkDeclined("idle")
            while work._dir is not None and not work._try_host():
                if visible and not waiting:
                    if work._state is not None:
                        _write_record(
                            work._state / WAIT_NAME,
                            {**self._inflight(), "pid_start": None},
                        )
                    work._mark_waiting(True)
                    waiting = True
                elif waiting:
                    work._mark_waiting(
                        True
                    )  # refresh this door's place: it is still waiting
                work._stop.wait(work._poll)
                reason = work._declined()
                if reason is not None:
                    raise WorkDeclined(reason)
            if waiting:
                work._mark_waiting(False)
                if work._state is not None:
                    (work._state / WAIT_NAME).unlink(missing_ok=True)
                waiting = False
            # The in-flight record goes down BEFORE the last check, so a drain that reads "no record" can never be
            # followed by a round starting: either the round sees DRAINING here, or the drain sees its record.
            if work._state is not None:
                _write_record(work._state / INFLIGHT_NAME, self._inflight())
                recorded = True
            reason = work._declined()
            if reason is not None:
                raise WorkDeclined(reason)
        except BaseException:
            try:
                if waiting:
                    work._mark_waiting(False)
                if work._state is not None:
                    (work._state / WAIT_NAME).unlink(missing_ok=True)
                    if recorded:
                        (work._state / INFLIGHT_NAME).unlink(missing_ok=True)
                work._release_host()
            finally:
                work._lock.release()
            raise
        return work

    def __exit__(self, *exc):
        work = self.work
        try:
            if work._state is not None:
                (work._state / INFLIGHT_NAME).unlink(missing_ok=True)
        finally:
            try:
                work._release_host()
            finally:
                work._lock.release()
        return False


def _round(work, kind, has_work=None):
    """One work round: `_WorkLock.taking` when ``work`` is one, else ``work`` itself (any lock, as before)."""
    taking = getattr(work, "taking", None)
    return work if taking is None else taking(kind, has_work=has_work)


def _advance_loop(intake, stop, work=None):
    work = work or _WorkLock(stop=stop)
    failures = 0
    while not stop.is_set():
        wait = 1
        try:
            with _round(work, "advance"):
                intake.advance()
            failures = 0
        except WorkDeclined:
            pass  # stopping, draining, or the host lock is another door's: never a failure
        except Exception as failure:  # noqa: BLE001 - no private content in log
            failures += 1
            wait = _backoff_s(failures)
            log(
                "direct_worker_failure",
                type=type(failure).__name__,
                consecutive=failures,
                retry_s=wait,
                site=_keep_failure(intake, "advance", failure),
            )
        stop.wait(wait)


def _grade_loop(grader, stop, work):
    failures = 0
    while not stop.is_set():
        graded = None
        wait = 5
        try:
            # Only a door with something to grade takes the host lock (MAINNET_UPDATE_ARCHITECTURE s2.4 Step A).
            with _round(work, "grade", getattr(grader, "has_work", None)):
                graded = grader.run_once()
            failures = 0
        except WorkDeclined:
            pass  # stopping, draining, nothing to grade, or waiting on the host: never a failure
        except Exception as failure:  # noqa: BLE001 - no private content in log
            failures += 1
            wait = max(5, _backoff_s(failures))
            log(
                "direct_grade_failure",
                type=type(failure).__name__,
                consecutive=failures,
                retry_s=wait,
                site=_keep_failure(grader, "grade", failure),
            )
        if graded is not None:
            log("direct_grade", state=graded[1])
            wait = 2
        stop.wait(wait)
