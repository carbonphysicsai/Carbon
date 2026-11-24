"""Signed DEVELOPMENT ConstructionRecipe receiver using the existing intake shell.

This prospective receiver shares the Battery intake's bounded HTTP listener,
peer limits, snapshot window and authenticated transport. It has its own
registered Challenge and task adapter; it never calls the Battery daemon or
claims a Score Pack, official verdict, qualification or reward.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
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
    refusal_status,
)

from . import funder_map as funder_maps
from . import koth_public, queue_public, submission_terms
from .dispatch import Adapters, Validator
from .interface import Submission, Unavailable
from .lean_recipe import LeanRecipeAdapter
from .request_buckets import claimed_hotkey

#: Guards creation of the per-owner workspace locks (`DirectIntake._owner_lock`).
_OWNER_LOCKS_GUARD = threading.Lock()

INFO_PATH = "/carbon/v1/construction/intake"
#: The signed launch board: `GET FEED_PATH + <challenge id>` (the battery door's feed path).
FEED_PATH = "/carbon/v1/feed/"
#: How long the published readiness is reused: reading it verifies the whole official receipt log.
OFFICIAL_GPU_CACHE_SECONDS = 10.0
#: The public GETs' shared answers (live 116, 19 Nov 2026: py-spy 18:22Z, 23 of 37 request threads rebuilt the info
#: document's receipt readiness at once on its cache expiry): each requester-independent public GET answer is rebuilt by
#: ONE caller at a time, off every request lock, every other caller served the last good answer. An answer is fresh for
#: `PUBLIC_GET_FRESH_S`; while it rebuilds, the last good one is served if at most `PUBLIC_GET_STALE_MAX_S` old (V2: N
#: stated, <= 60 s), else the reader waits for the rebuild.
PUBLIC_GET_FRESH_S = 10.0
PUBLIC_GET_STALE_MAX_S = 60.0
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
#: v6 (owner 14 Nov: "yes tell them") = v5 plus ``submission.gate_failures``: for the caller's own gate-failed grade the failing OUTPUTS, each
#: with one closed reason (``over_limit`` | ``invalid_answer``), else None (`gate_failure_feedback`). Never a p90, ratio, class, count or case.
#: Advertised as ``exam_feedback_v6``; a v2..v5 reply is unchanged.
FEEDBACK_REPLY_SCHEMA_V6 = "carbon.private-exam.ladder-feedback-reply.v6"
#: v7 (Validator-2 15 Nov, P-1..P-4) = v6 whose Ladder documents may carry the NOT_SCORED reasons TIMED_OUT / STOPPED_EARLY
#: (`grade_feedback`). Opt-in by the kit's request: a kit already in the field validates documents against ITS OWN reason
#: list and would refuse the whole reply, so every older reply (v1..v6) WITHHOLDS each document carrying one of those
#: reasons (served as null, never a substitute reason). Advertised as ``exam_feedback_v7``.
FEEDBACK_REPLY_SCHEMA_V7 = "carbon.private-exam.ladder-feedback-reply.v7"
#: v8 (Lead 15 Nov: "for every settled task ... which phase/pass ... plus a public line on the grade worker") = v7 plus, for the
#: caller's own submission, ``failure.pass`` (which pass of a counted grade a candidate wall stop ended: `FAILURE_PASSES`, else
#: None) and ``grade_worker`` (the public facts of the machine that grades: CPU model, the registered CPU count and memory, GPU
#: or not). Nothing measured. Opt-in (a kit in the field pins v4's closed ``failure`` keys); advertised as ``exam_feedback_v8``.
FEEDBACK_REPLY_SCHEMA_V8 = "carbon.private-exam.ladder-feedback-reply.v8"
#: v9 (owner GO 15 Nov 2026 via the Lead, "those 3 are fine.": a miner may withdraw its own queued submission) = v8 plus the grade
#: state WITHDRAWN_BY_MINER for a submission its owner withdrew while it was still queued. Opt-in (a kit in the field pins its own
#: closed state set): every older reply (v4..v8) says NOT_GRADED for it, which it already reads. Advertised as ``exam_feedback_v9``.
FEEDBACK_REPLY_SCHEMA_V9 = "carbon.private-exam.ladder-feedback-reply.v9"
#: v10 (owner P0 20 Nov 2026 "better failure labels and explanations"; V2 FAILURE_LABELS_RULING_20261120 section 4) = v9
#: plus ``submission.failure_class``: for the caller's own submission whose build ended FAILED_INFRA, the closed public row of
#: its failure class (`infra_diagnosis.public_row`: code, what happened, side, charged, next step, retried or owed), else
#: None. Never a host, path, id, traceback or log text. Opt-in (a kit pins v9's closed keys); advertised as
#: ``exam_feedback_v10``.
FEEDBACK_REPLY_SCHEMA_V10 = "carbon.private-exam.ladder-feedback-reply.v10"
#: v11 (G-LEAD-10 row 1, RECIPE CRASHED: spot used; V2 23:2xZ (3): a versioned change, not a v10 widening) = v10 plus, for
#: the caller's own submission whose build ended RECONSTRUCTION_FAILED on its own program with its daily spot used, the
#: recipe-side row in ``submission.failure_class`` (`infra_diagnosis.RECIPE_SPOT_ROW`: side yours, charged). v10 keeps None
#: there. Opt-in (a kit pins v10's closed rows); advertised as ``exam_feedback_v11``.
FEEDBACK_REPLY_SCHEMA_V11 = "carbon.private-exam.ladder-feedback-reply.v11"
#: v12 (miner-ux 6054, v2 6039 (3); live 24 Nov: three of Martin Guthrie's ids read QUEUED after Carbon re-ran them under new
#: ids) = v11 plus ``submission.rerun_task_id``: for the caller's OWN submission that the DOOR re-ran as a new task
#: (`AttemptLedger.requeued_as`: its requeue, never a miner's own resubmission), grade_state ``RERUN`` and the new id, so
#: the caller reads that id for the result; else None and the state as v11. Never another hotkey's id. Opt-in (a kit pins
#: v11's closed states); advertised as ``exam_feedback_v12``.
FEEDBACK_REPLY_SCHEMA_V12 = "carbon.private-exam.ladder-feedback-reply.v12"
#: v13 (owner G-LEAD-78, 24 Nov 2026) = v12 plus ``submission.refusal_detail``: for the caller's OWN submission whose graph
#: build was refused (RECONSTRUCTION_FAILED), the closed public detail code of that refusal (`build_refusal_v2.CODES`, for
#: example ``graph_route_nonfinite_state``), else None: a build refused before the code was kept, or one that named none.
#: Never a worker's text, a number or anything of another hotkey's. Opt-in; advertised as ``exam_feedback_v13``.
FEEDBACK_REPLY_SCHEMA_V13 = "carbon.private-exam.ladder-feedback-reply.v13"
#: The grade state only a v12 reply names: Carbon re-ran this submission, uncharged, as ``rerun_task_id``.
RERUN_STATE = "RERUN"
#: The grade state only a v9 reply names (`auto_grade.WITHDRAWN_STATE`).
WITHDRAWN_STATE = "WITHDRAWN_BY_MINER"
#: A miner withdraws its OWN queued, not-yet-building submission (owner GO 15 Nov 2026 via the Lead): signed by the same hotkey,
#: ``{submission_id}``; no try and no allowance is used, the waiting place is freed, the task's marker is WITHDRAWN_BY_MINER.
#: Advertised in its own facts entry (``construction_withdraw_v1``) by a door that grades its own submissions, never in `tools`
#: (deployed clients pin that list exactly).
WITHDRAW_TOOL = "construction_withdraw"
WITHDRAW_FACTS_NAME = "construction_withdraw_v1"
#: A wall stop in any other pass (e.g. the speed sample) is still counted and reads ``pass: None``.
FAILURE_PASSES = ("graded_pass", "inference_pair", "menu_rowcheck", "early_stop")
#: The reasons only a v7 reply carries.
V7_ONLY_REASONS = ("TIMED_OUT", "STOPPED_EARLY")
#: The closed public code of a proven non-finite answer (owner G-LEAD-75, `auto_retry.NONFINITE_OUTPUT`; a test holds
#: them equal), in the ``failure`` of a v4+ reply. A reply's shape does not change.
NONFINITE_OUTPUT = "nonfinite_output"
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


def _cpu_model(path="/proc/cpuinfo"):
    """This host's CPU model name as ``/proc/cpuinfo`` reports it (printable, at most 96 characters), or None."""
    try:
        with open(path, encoding="ascii", errors="replace") as info:
            for line in info:
                if line.startswith("model name"):
                    name = line.split(":", 1)[1].strip()
                    return name[:96] if name and name.isprintable() else None
    except OSError:
        return None
    return None


def withdraw_facts():
    """The ``construction_withdraw_v1`` public facts entry (the kit pins it exactly): the tool, its one field, and the one task
    state it can still withdraw."""
    return {
        "tool": WITHDRAW_TOOL,
        "fields": ["submission_id"],
        "states": ["QUEUED"],
        "path": SUBMIT_PATH,
        "owner": "authenticated_hotkey",
    }


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
        "v6",
        "v7",
        "v8",
        "v9",
        "v10",
        "v11",
        "v12",
        "v13",
    ):
        return fields["reply"]
    return None


def _log_submit_timing(began, received_at, charged_at, steps):
    """One ``submit_timing`` journal line per construction submit (`step_timing`): the request's wall milliseconds in
    the transport receive (signature, snapshot, receipt journal), the charge check and each instrumented admission
    step; names and milliseconds only. Never raises."""
    try:
        from carbon.battery.intake import log

        now = time.monotonic()
        log(
            "submit_timing",
            total_ms=round((now - began) * 1000),
            receive_ms=round((received_at - began) * 1000),
            charge_ms=round((charged_at - received_at) * 1000),
            **{
                name: int(ms)
                for name, ms in sorted(steps.items())
                if name.isidentifier()
            },
        )
    except Exception:  # noqa: BLE001, S110 - a diagnostic line never changes a submit
        pass


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
        #: This door's submission terms (`submission_terms.for_door`; owner G-LEAD-50), or None when its Challenge
        #: version requires none (then discovery and construction_submit are unchanged).
        self.submission_terms = None
        #: The append-only acceptance record (`submission_terms.AcceptanceStore`), set with `submission_terms`.
        self.terms_store = None
        #: The withdrawal's marker writer (`AutoGrader.withdrawn`), or None: then no withdrawal is advertised or taken.
        self.withdraw_marker = None
        #: No door-wide writer lock (LOCK + CACHE AUDIT #2, 19 Nov 2026): an admission holds its OWNER's lock, then the
        #: locks of the cross-owner scopes its rules read (`_admission_scope`: its allowance group and its coldkey), so
        #: the cap, idempotency, the once-per-epoch rule and one-waiting-per-coldkey stay exact under any number of
        #: concurrent clients (GPU_REBUILD_RULINGS section 12) while unrelated owners admit in parallel. A withdrawal
        #: and a source stage hold their owner's lock only. Reads (the public facts, status, the Ladder) take none.
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

    def _note_transport(self, failure):
        """A transport refusal, counted by its code for the hourly request-buckets line (no buckets: nothing).
        Counts only: live-ops 6258 found no refused answer logged by code (the live TRANSPORT_STORE rate unknown).
        """
        if self.request_buckets is not None:
            self.request_buckets.note(failure.code.value.lower())

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
                        "exam_feedback_v6": {
                            "tool": FEEDBACK_TOOL,
                            "fields": ["reply", "submission_id"],
                            "reply_schema": FEEDBACK_REPLY_SCHEMA_V6,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        },
                        "exam_feedback_v7": {
                            "tool": FEEDBACK_TOOL,
                            "fields": ["reply", "submission_id"],
                            "reply_schema": FEEDBACK_REPLY_SCHEMA_V7,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        },
                        "exam_feedback_v8": {
                            "tool": FEEDBACK_TOOL,
                            "fields": ["reply", "submission_id"],
                            "reply_schema": FEEDBACK_REPLY_SCHEMA_V8,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        },
                        "exam_feedback_v9": {
                            "tool": FEEDBACK_TOOL,
                            "fields": ["reply", "submission_id"],
                            "reply_schema": FEEDBACK_REPLY_SCHEMA_V9,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        },
                        "exam_feedback_v10": {
                            "tool": FEEDBACK_TOOL,
                            "fields": ["reply", "submission_id"],
                            "reply_schema": FEEDBACK_REPLY_SCHEMA_V10,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        },
                        "exam_feedback_v11": {
                            "tool": FEEDBACK_TOOL,
                            "fields": ["reply", "submission_id"],
                            "reply_schema": FEEDBACK_REPLY_SCHEMA_V11,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        },
                        "exam_feedback_v12": {
                            "tool": FEEDBACK_TOOL,
                            "fields": ["reply", "submission_id"],
                            "reply_schema": FEEDBACK_REPLY_SCHEMA_V12,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        },
                        "exam_feedback_v13": {
                            "tool": FEEDBACK_TOOL,
                            "fields": ["reply", "submission_id"],
                            "reply_schema": FEEDBACK_REPLY_SCHEMA_V13,
                            "path": SUBMIT_PATH,
                            "owner": "authenticated_hotkey",
                        },
                    }
                ),
                **(
                    {}
                    if getattr(self, "grade_marker", None) is None
                    or getattr(self, "withdraw_marker", None) is None
                    else {WITHDRAW_FACTS_NAME: withdraw_facts()}
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
                **(
                    {}
                    if getattr(self, "submission_terms", None) is None
                    else {"terms": self.submission_terms.facts()}
                ),
                "score_pack": None,
                "qualification": False,
                "reward": False,
            },
        )

    def route(self, method, path, headers, body):
        if method == "GET":
            # every public GET: requester-independent (no signature, no hotkey), so one shared answer per path
            # (called as this class's own functions: a test double of the intake routes through them too)
            key = DirectRecipeIntake._public_key(self, path)
            if key is not None:
                answer = DirectRecipeIntake._public_get(
                    self, key, lambda: DirectRecipeIntake._public_answer(self, key)
                )
                if key != INFO_PATH:
                    return answer
                return DirectRecipeIntake._current_snapshot(self, answer)
        if method == "GET" and path == INFO_PATH:
            return self.public()
        if method == "GET" and path.startswith(koth_public.PATH):
            return self._koth(path)
        if method == "GET" and path.startswith(queue_public.PATH):
            return self._queue(path)
        if method == "GET" and path == FEED_PATH + self.challenge.challenge_id:
            return self._board()
        if method == "GET" and DirectRecipeIntake._terms_path(self) == path:
            return DirectRecipeIntake._terms_text(self)
        if method != "POST" or path != SUBMIT_PATH:
            return _refused(404, "not_found")
        return asyncio.run(self._post(headers, body))

    def _current_snapshot(self, answer):
        """The info document's answer with the snapshot this door holds NOW, never the shared answer's own (up to
        `PUBLIC_GET_STALE_MAX_S` old): a client signs its request over this snapshot and has what is left of
        `SNAPSHOT_MAX_AGE_S` to be admitted, so an automatic resend must never read the one it was just refused on. Reading
        the window takes no request lock. No fresh snapshot: the same 503 `public` gives. ``answer`` is the caller's copy.
        """
        if answer.status != 200 or "snapshot" not in answer.body:
            return answer
        snapshot = self.window.latest()
        if snapshot is None:
            return _refused(503, "snapshot_unavailable")
        return Answer(
            answer.status,
            {
                **answer.body,
                "snapshot": {
                    "id": snapshot.snapshot_id,
                    "finalized_block": snapshot.finalized_block,
                    "timestamp_ms": snapshot.timestamp_ms,
                },
            },
        )

    def _public_key(self, path):
        """The canonical path of one of this door's public GET documents, or None (any other path is answered live, as
        before: a 404 is cheap and never cached, so no path can grow the cache)."""
        from urllib.parse import unquote

        try:
            asked = unquote(path)
        except Exception:  # noqa: BLE001 - not a public document path
            return None
        challenge = self.challenge.challenge_id
        known = {INFO_PATH, FEED_PATH + challenge}
        terms_path = DirectRecipeIntake._terms_path(self)
        if terms_path is not None:
            known.add(terms_path)
        known.update(
            koth_public.PATH + challenge + suffix
            for suffix in ("", koth_public.V2_SUFFIX, koth_public.V3_SUFFIX)
        )
        known.update(
            queue_public.PATH + challenge + suffix
            for suffix in (
                "",
                queue_public.V2_SUFFIX,
                queue_public.V3_SUFFIX,
                queue_public.V4_SUFFIX,
            )
        )
        return asked if asked in known else None

    def _public_answer(self, key):
        """The live answer of the public document ``key`` (the same handlers as before)."""
        if key == INFO_PATH:
            return self.public()
        if key.startswith(koth_public.PATH):
            return self._koth(key)
        if key.startswith(queue_public.PATH):
            return self._queue(key)
        if key == DirectRecipeIntake._terms_path(self):
            return DirectRecipeIntake._terms_text(self)
        return self._board()

    def _terms_path(self):
        """The path this door serves its terms text at, or None (no terms door)."""
        terms = getattr(self, "submission_terms", None)
        return None if terms is None else submission_terms.path_of(terms.version)

    def _terms_text(self):
        """The terms text a client shows and the miner accepts: the pinned published bytes, served as they are
        (text/markdown, never re-encoded: the client checks their sha256 against the facts); else 503.
        """
        terms = getattr(self, "submission_terms", None)
        if terms is None:
            return _refused(404, "not_found")
        if not terms.ready:
            return Answer(
                503, submission_terms.refusal(submission_terms.UNAVAILABLE, terms)
            )
        return Answer(200, terms.text)

    def _public_get(self, key, build):
        """One shared public answer for ``key``: fresh for `PUBLIC_GET_FRESH_S`; rebuilt by ONE caller at a time outside
        the guard (no request lock is held while it builds); meanwhile every other caller gets the last GOOD answer (a
        2xx/4xx one) if at most `PUBLIC_GET_STALE_MAX_S` old, else waits for the rebuild. A rebuild that fails (raises,
        or answers 5xx) keeps the last good answer for others; its own caller gets its own result, as before. The body
        is copied per caller (the answer an earlier caller holds is never shared mutably).
        """
        import copy

        state = self.__dict__.setdefault("_public_state", {})
        cond = self.__dict__.setdefault("_public_cond", threading.Condition())
        with cond:
            while True:
                entry = state.get(key)
                now = time.monotonic()
                if entry is not None and entry.get("answer") is not None:
                    age = now - entry["at"]
                    if age < PUBLIC_GET_FRESH_S:
                        return Answer(
                            entry["answer"].status, copy.deepcopy(entry["answer"].body)
                        )
                    if entry.get("building") and age <= PUBLIC_GET_STALE_MAX_S:
                        return Answer(
                            entry["answer"].status, copy.deepcopy(entry["answer"].body)
                        )
                if entry is None or not entry.get("building"):
                    entry = state.setdefault(key, {"answer": None, "at": 0.0})
                    entry["building"] = True
                    break
                cond.wait(PUBLIC_GET_STALE_MAX_S)
        answer = None
        try:
            answer = build()
            return answer
        finally:
            with cond:
                entry = state[key]
                entry["building"] = False
                if (
                    answer is not None
                    and type(answer) is Answer
                    and answer.status < 500
                ):
                    entry["answer"] = Answer(answer.status, copy.deepcopy(answer.body))
                    entry["at"] = time.monotonic()
                cond.notify_all()

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
        elif asked.endswith(koth_public.V3_SUFFIX):
            # the v3 document (owner 16 Nov: totals to 3 decimals, the crown rule's own bar) at its own path
            asked, serve = asked[: -len(koth_public.V3_SUFFIX)], koth_public.serve_v3
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
        path + ``/v2``, v3 (the per-submission rows) at ``/v3``, v4 (v3 with the counts of what actually runs) at
        ``/v4``; any other id is not found.
        """
        from urllib.parse import unquote

        asked, serve = unquote(path[len(queue_public.PATH) :]), queue_public.serve
        if asked.endswith(queue_public.V2_SUFFIX):
            asked, serve = asked[: -len(queue_public.V2_SUFFIX)], queue_public.serve_v2
        elif asked.endswith(queue_public.V3_SUFFIX):
            asked, serve = asked[: -len(queue_public.V3_SUFFIX)], queue_public.serve_v3
        elif asked.endswith(queue_public.V4_SUFFIX):
            asked, serve = asked[: -len(queue_public.V4_SUFFIX)], queue_public.serve_v4
        if asked != self.challenge.challenge_id:
            return _refused(404, "not_found")
        status, body = serve(self.queue_view, self.challenge)
        return Answer(status, body)

    async def _post(self, headers, body):
        began = time.monotonic()
        try:
            envelope = parse_message(body)
        except TransportFailure as failure:
            self._malformed_diagnostics.note(failure, headers)
            self._note_transport(failure)
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
            self._note_transport(failure)
            refused = _refused(refusal_status(failure.code), failure.code.value)
            if failure.code is TransportCode.STORE:
                # v2 FINAL 900: the door could not record the request (Carbon's side, 503): it takes no R89 bucket,
                # not even the shared guard, and (raised before `_verified_charge` and any admission) no try and no
                # exam-cap allowance.
                return refused
            return self._unverified(refused)
        except AuthFailure as failure:
            return self._unverified(_refused(401, failure.code.value))
        received_at = time.monotonic()
        if not self._verified_charge(received):
            return _refused(429, "rate")
        charged_at = time.monotonic()
        if received.call.tool == RESEARCH_NAMESPACE:
            # Live 116, 19 Nov 2026 (no construction-submit for an hour: 10 requests queued behind ONE source chunk's
            # storage scan and rewrite under the door-wide `_write`): a source stage writes only its OWN owner's
            # workspace and checks only that owner's storage cap, so it holds that owner's lock, never `_write`.
            return self._stage(received)
        fields = {field.name: field.value for field in received.call.fields}
        if received.call.tool == SUBMIT_TOOL:
            terms = getattr(self, "submission_terms", None)
            code, recipe_fields = submission_terms.check_fields(terms, fields)
            if code == "submission_fields":
                return _refused(400, code)
            if code is not None:
                return Answer(400, submission_terms.refusal(code, terms))
            receipt = received.receipt
            receipt_facts = {
                "sequence": receipt.ref.sequence,
                "digest": receipt.ref.digest,
                "block": receipt.finalized_block,
            }
            if terms is not None:
                # owner G-LEAD-50: the acceptance (this hotkey-signed request) is kept BEFORE admission; a door that
                # cannot keep it, or whose terms text is not the pinned published one, admits nothing (refuse-without)
                try:
                    if not terms.ready or getattr(self, "terms_store", None) is None:
                        raise submission_terms.TermsUnavailable()
                    self.terms_store.record(
                        receipt=receipt_facts,
                        hotkey=receipt.hotkey,
                        challenge=self.challenge,
                        terms=terms,
                        body=body,
                        headers=headers,
                    )
                except submission_terms.TermsUnavailable:
                    return Answer(
                        503,
                        submission_terms.refusal(submission_terms.UNAVAILABLE, terms),
                    )
            fields = recipe_fields
            submitted = Submission(
                hotkey=receipt.hotkey,
                receipt=receipt_facts,
                challenge_id=self.challenge.challenge_id,
                challenge_version=self.challenge.version,
                strategy_json=fields["strategy_json"],
                contract_digest=fields["contract_digest"],
            )
            from . import step_timing

            with step_timing.collecting() as steps:
                try:
                    result = self._admit(submitted)
                finally:
                    _log_submit_timing(began, received_at, charged_at, steps)
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
                v4=reply
                in ("v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13"),
                v5=reply in ("v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13"),
                v6=reply in ("v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13"),
                v7=reply in ("v7", "v8", "v9", "v10", "v11", "v12", "v13"),
                v8=reply in ("v8", "v9", "v10", "v11", "v12", "v13"),
                v9=reply in ("v9", "v10", "v11", "v12", "v13"),
                v10=reply in ("v10", "v11", "v12", "v13"),
                v11=reply in ("v11", "v12", "v13"),
                v12=reply in ("v12", "v13"),
                v13=reply == "v13",
            )
        if received.call.tool == WITHDRAW_TOOL:
            return self._withdraw(received.receipt.hotkey, fields)
        return _refused(400, "tool")

    def _withdraw(self, hotkey, fields):
        """The signed hotkey withdraws its OWN queued, not-yet-building submission (`LeanRecipeAdapter.withdraw`).

        Order: the provider's cancel first (the one step that decides, under the provider's lock against a start), then the
        withdrawal row, then the terminal marker (`AutoGrader.withdrawn`). A call that stops after the cancel answers 503;
        the same withdrawal again is idempotent and writes what is missing, and the grade round repairs a missing marker
        itself (`AutoGrader._settle_withdrawn`), so the task never stays pending and is never graded. Answers: 200
        ``{"withdrawn", "grade_state"}`` (also for the same withdrawal again); 409 ``withdraw_too_late`` (building, built or
        ended); 404 ``withdraw_submission_unknown`` (unknown, another hotkey's, or no provider for it here: one answer);
        400 ``withdraw_fields``.
        """
        from .lean_recipe import (
            ALREADY_WITHDRAWN,
            WITHDRAW_TOO_LATE,
            WITHDRAWN,
        )

        if (
            set(fields) != {"submission_id"}
            or type(fields["submission_id"]) is not str
            or not fields["submission_id"]
        ):
            return _refused(400, "withdraw_fields")
        mark = getattr(self, "withdraw_marker", None)
        if getattr(self, "grade_marker", None) is None or mark is None:
            return _refused(
                400, "tool"
            )  # not advertised here: this door does not grade its own submissions
        submission_id = fields["submission_id"]
        # its owner's lock only (never door-wide): a withdrawal changes that owner's own task, and its admissions and
        # stages hold the same lock
        with self._owner_lock(hotkey):
            try:
                result = self.adapter.withdraw(hotkey, submission_id)
            except Unavailable:
                return _refused(503, "withdraw_unavailable")
            if result == WITHDRAW_TOO_LATE:
                return _refused(409, "withdraw_too_late")
            if result not in (WITHDRAWN, ALREADY_WITHDRAWN):
                return _refused(404, "withdraw_submission_unknown")
            try:
                self.adapter.ledger.record_miner_withdrawal(
                    self.adapter.contract_digest, submission_id, hotkey
                )
                mark(submission_id)
            # any failure is said, then repaired: the same withdrawal again, or the grade round
            except Exception as failure:  # noqa: BLE001
                log("withdraw_record_failed", type=type(failure).__name__)
                return _refused(503, "withdraw_unavailable")
        log("miner_withdrew", again=result == ALREADY_WITHDRAWN)
        return Answer(200, {"withdrawn": submission_id, "grade_state": WITHDRAWN_STATE})

    def _admit(self, submitted):
        """The one admission path. It holds the submitter's own owner lock FIRST (a duplicate is admitted once; an
        admission never reads its owner's workspace while that owner's source stage writes it), then the locks of its
        allowance group and coldkey (`_admission_scope`), so every rule that reads ANOTHER owner's state (the daily
        allowance and epoch limit with the group's pending submissions; one waiting submission per coldkey) is decided
        one admission at a time within that scope, and owners of other groups and coldkeys never wait for it.
        """
        hotkey = getattr(submitted, "hotkey", None)
        owner = (
            self._owner_lock(hotkey)
            if type(hotkey) is str
            else contextlib.nullcontext()
        )
        from . import step_timing

        with contextlib.ExitStack() as held:
            step_timing.enter(held, "owner_lock_wait", owner)
            if type(hotkey) is str:
                with step_timing.step("open_owner"):
                    self._open_owner(hotkey)
            step_timing.enter(held, "scope_lock_wait", self._admission_scope(hotkey))
            with step_timing.step("evaluate"):
                result = self.door.evaluate(submitted)
            self._note_recipe_digest(result)
            return result

    def _admission_keys(self, hotkey):
        """The cross-owner scopes an admission of ``hotkey`` decides in, sorted: ``g:<allowance group>``
        (`exam_cap.group_of`) and ``c:<coldkey>`` (the door's latest snapshot). Every hotkey of one coldkey shares both.
        Memory only (the latest snapshot and the funder map, as the rules read them); a scope that cannot be read now
        adds no key (the owner lock still holds, and the admission meets the same refusal its rule gives).
        """
        from . import exam_cap

        keys = set()
        try:
            keys.add("g:" + exam_cap.group_of(hotkey))
        # a refusing grouping: no group key, and the admission refuses the same way
        except Exception:  # noqa: BLE001, S110
            pass
        window = getattr(self, "window", None)
        try:
            snapshot = None if window is None else window.latest()
            member = None if snapshot is None else snapshot.resolve(hotkey)
        # no snapshot: no coldkey scope (the guard fails open the same way)
        except Exception:  # noqa: BLE001
            member = None
        coldkey = getattr(member, "coldkey", None)
        if type(coldkey) is str:
            keys.add("c:" + coldkey)
        return sorted(keys)

    @contextlib.contextmanager
    def _admission_scope(self, hotkey):
        """Hold the locks of ``hotkey``'s admission scopes (`_admission_keys`), taken in sorted order after the owner
        lock (so no two admissions can wait on each other in a cycle). Each lock guards nothing but the order of
        admissions within its scope; the registry of locks is memory only."""
        keys = self._admission_keys(hotkey) if type(hotkey) is str else []
        with _OWNER_LOCKS_GUARD:
            registry = self.__dict__.setdefault("_admission_locks", {})
            locks = [registry.setdefault(key, threading.Lock()) for key in keys]
        with contextlib.ExitStack() as held:
            for lock in locks:
                held.enter_context(lock)
            yield

    def _open_owner(self, hotkey):
        """Open (a lazy owner: restore, 3-10 s live) the submitter's provider BEFORE its admission scopes (case-procs,
        LOCK PROGRAM 19 Nov 2026: a burst of new owners' first submits serialised their restores under the then
        door-wide `_write`), so the admission's own `_provider` finds it open. Best effort: any refusal here is left to
        the admission, which meets and answers it exactly as before."""
        adapter = getattr(self, "adapter", None)
        opener = getattr(adapter, "_provider", None)
        if not callable(opener):
            return
        try:
            opener(hotkey)
        except Exception:  # noqa: BLE001, S110 - the admission meets the same refusal
            pass

    def _stage(self, received):
        """One source stage under its owner's lock only (see the route): never the door-wide `_write`."""
        with self._owner_lock(received.receipt.hotkey):
            return self._stage_source(received)

    def _owner_lock(self, hotkey):
        """The lock of one owner's state changes (its source stages, admissions and withdrawals): one per hotkey,
        created on first use. Lock order: an owner lock, then its admission scopes (`_admission_scope`, sorted); a
        source stage and a withdrawal take their owner's only.
        """
        with _OWNER_LOCKS_GUARD:
            locks = self.__dict__.setdefault("_owner_locks", {})
            return locks.setdefault(hotkey, threading.Lock())

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
        except Exception as failure:  # noqa: BLE001 - never changes the admission
            # said, never silent (RB door rs33, 9 Nov: a failing note hid a grade-time lock for every new submission)
            log("recipe_digest_note_failed", type=type(failure).__name__)
            return

    def _feedback(
        self,
        hotkey,
        *,
        submission_id=None,
        v3=False,
        v4=False,
        v5=False,
        v6=False,
        v7=False,
        v8=False,
        v9=False,
        v10=False,
        v11=False,
        v12=False,
        v13=False,
    ):
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
                # Owner decision #9: the caller's OWN submission that was still queued on an earlier version when this
                # door left it (`version_close`) was closed, not graded, nothing charged: said typed. Any other id, and
                # anyone else's closed one, stays unknown.
                closed = getattr(self, "version_closed", None) or {}
                if closed.get(submission_id, None) == hotkey:
                    return _refused(410, "version_closed")
                return _refused(404, "feedback_submission_unknown")
            failure = None
            if v4:
                try:
                    grade_state, failure = self._grade_state_v4(hotkey, submission_id)
                except (Unavailable, LookupError, ValueError, OSError):
                    return _refused(503, "grade_state_unavailable")
                if grade_state == WITHDRAWN_STATE and not v9:
                    grade_state = "NOT_GRADED"  # v4..v8: withdrawn = not graded, nothing charged (a state they read)
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
        rerun_task_id = None
        if v12 and submission_id is not None:
            # the DOOR re-ran the caller's own submission as a new task (never a miner's own resubmission): say so and
            # name the new id, instead of the old id's QUEUED / FAILED_INFRA (v2 6039 (3))
            try:
                rerun_task_id = self.adapter.ledger.requeued_as(
                    self.adapter.contract_digest, submission_id, hotkey
                )
            except (LookupError, ValueError, OSError, AttributeError):
                return _refused(503, "grade_state_unavailable")
            if rerun_task_id is not None:
                grade_state, failure, held_position = RERUN_STATE, None, None
        refusal_detail = None
        if v13 and submission_id is not None and grade_state == "RECONSTRUCTION_FAILED":
            refusal_detail = self._refusal_detail(submission_id)
        failure_class = None
        if v10 and submission_id is not None and grade_state == "FAILED_INFRA":
            failure_class = self._failure_class_row(submission_id)
        elif (
            v11 and submission_id is not None and grade_state == "RECONSTRUCTION_FAILED"
        ):
            failure_class = self._recipe_spot_row(submission_id)
        if v8 and submission_id is not None and failure is not None:
            # which pass a counted wall stop ended (the grade marker's closed name), else None
            marker = self.grade_marker(submission_id) or {}
            ended = marker.get("pass") if grade_state == "CANDIDATE_FAILED" else None
            failure = {**failure, "pass": ended if ended in FAILURE_PASSES else None}
        snapshot = getattr(self.adapter.discovery, "evaluation_pack_snapshot", None)
        exam_key = getattr(snapshot, "manifest_digest", None)
        gate_failures = None
        if v6 and exam_key is not None:
            from . import gate_failure_feedback

            try:
                gate_failures = gate_failure_feedback.read(
                    self.adapter.ledger, submission_id, exam_key
                )
            except (OSError, ValueError):
                return _refused(503, "grade_state_unavailable")
        documents = {"best": None, "latest": None}
        if exam_key is not None:
            try:
                documents = LadderStore(self.adapter.ledger).served(
                    hotkey, self.challenge, exam_key
                )
            except LadderStoreRefused:
                return _refused(503, "feedback_unavailable")
        if not v7:
            # P-2: an older reply withholds every document a kit in the field cannot read (never a substitute reason)
            documents = {
                name: (
                    None
                    if type(document) is dict
                    and document.get("reason") in V7_ONLY_REASONS
                    else document
                )
                for name, document in documents.items()
            }
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
                        # the newest reply the caller asked for (each implies the older ones' flags)
                        "schema": next(
                            schema
                            for flag, schema in (
                                (v13, FEEDBACK_REPLY_SCHEMA_V13),
                                (v12, FEEDBACK_REPLY_SCHEMA_V12),
                                (v11, FEEDBACK_REPLY_SCHEMA_V11),
                                (v10, FEEDBACK_REPLY_SCHEMA_V10),
                                (v9, FEEDBACK_REPLY_SCHEMA_V9),
                                (v8, FEEDBACK_REPLY_SCHEMA_V8),
                                (v7, FEEDBACK_REPLY_SCHEMA_V7),
                                (v6, FEEDBACK_REPLY_SCHEMA_V6),
                                (v5, FEEDBACK_REPLY_SCHEMA_V5),
                                (v4, FEEDBACK_REPLY_SCHEMA_V4),
                                (v3, FEEDBACK_REPLY_SCHEMA_V3),
                                (True, FEEDBACK_REPLY_SCHEMA_V2),
                            )
                            if flag
                        ),
                        "submission": {
                            "submission_id": submission_id,
                            "grade_state": grade_state,
                            **({"failure": failure} if v4 else {}),
                            **({"held_position": held_position} if v5 else {}),
                            **({"gate_failures": gate_failures} if v6 else {}),
                            **({"grade_worker": self.grade_worker()} if v8 else {}),
                            **({"failure_class": failure_class} if v10 else {}),
                            **({"rerun_task_id": rerun_task_id} if v12 else {}),
                            **({"refusal_detail": refusal_detail} if v13 else {}),
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
        from .lean_recipe import WITHDRAWN_CODE

        marker = self.grade_marker(submission_id)
        if marker is None:
            projected = self.adapter.outcome(submission_id)
            state = projected.get("state")
            if (projected.get("failure") or {}).get("code") == WITHDRAWN_CODE:
                # withdrawn by its owner, its marker not written yet (the grade round repairs it): the same answer
                return WITHDRAWN_STATE, None
            if state == "RECONSTRUCTION_FAILED":
                child, observation = self.adapter.failed_child(submission_id)
                code = (projected.get("failure") or {}).get("code")
                return state, self.failure_v4(child, observation, code)
            return ("FAILED_INFRA" if state == "FAILED_INFRA" else "QUEUED"), None
        if marker.get("state") == "CANDIDATE_FAILED":
            if marker.get("code") == NONFINITE_OUTPUT:
                return "CANDIDATE_FAILED", self.failure_v4(
                    "inference", None, NONFINITE_OUTPUT
                )
            return "CANDIDATE_FAILED", self.failure_v4("inference", marker.get("code"))
        if marker.get("state") == "DUPLICATE":
            # A copy of a recipe already graded on this key (OWNER-PROBING-COUNTERS-01 (b)): its own slot is counted
            # (no free probe), so v4 says GRADED, never NOT_GRADED ('given back, nothing charged': Validator-2B 7 Nov).
            # Nothing of the first's is added to the copier's reply: not its id, its owner or its private feedback.
            return "GRADED", None
        if marker.get("state") == "FAILED" and marker.get("code") == NONFINITE_OUTPUT:
            # the first proven non-finite answer of a day (owner G-LEAD-75): the model's, given back, never Carbon's
            return "NOT_GRADED", self.failure_v4("inference", None, NONFINITE_OUTPUT)
        if marker.get("state") == "FAILED":
            return "FAILED_INFRA", None
        if marker.get("state") == "VERSION_CLOSED":
            # closed at a version flip (`version_close`, owner #9): not graded, nothing charged (a rollback's answer)
            return "NOT_GRADED", None
        if marker.get("state") == WITHDRAWN_STATE:
            # withdrawn by its owner while queued: never graded, nothing charged (`_feedback` says NOT_GRADED before v9)
            return WITHDRAWN_STATE, None
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

    def _failure_class_row(self, submission_id):
        """The closed public row (`infra_diagnosis.public_row`) of the caller's own FAILED_INFRA build's failure class, or
        None (a grade-side FAILED marker, no diagnosis, unreadable). Only the closed keys are ever served.
        """
        from carbon.development_session import infra_diagnosis

        if self.grade_marker(submission_id) is not None:
            return None  # a grade's own Carbon failure: its own table (case-procs), not a build's
        reader = getattr(self.adapter, "failure_class", None)
        try:
            failure_class = None if reader is None else reader(submission_id)
        # unreadable: no row, the state alone as before
        except Exception:  # noqa: BLE001
            return None
        row = infra_diagnosis.public_row(failure_class)
        if row is None or tuple(row) != infra_diagnosis.PUBLIC_ROW_KEYS:
            return None
        return row

    def _refusal_detail(self, submission_id):
        """The closed public detail code of the caller's own refused graph build (G-LEAD-78), or None (none kept,
        unreadable). Checked against the closed table again: nothing else is ever served.
        """
        from carbon.development_session.research_tasks import closed_refusal_detail

        reader = getattr(self.adapter, "refusal_detail", None)
        try:
            return closed_refusal_detail(
                None if reader is None else reader(submission_id)
            )
        except Exception:  # noqa: BLE001
            return None  # unreadable: no code, the state alone as before

    def _recipe_spot_row(self, submission_id):
        """G-LEAD-10 row 1: the closed recipe-side row (`infra_diagnosis.RECIPE_SPOT_ROW`: side yours, charged, spot
        used) for the caller's own REFUSED build whose daily spot was filed and not returned
        (`ExamCap.file_build_spent`), else None (a build that ended before the rule, a spot given back, unreadable).
        """
        from carbon.development_session import infra_diagnosis

        from .exam_cap import ExamCap

        try:
            spent = ExamCap(self.adapter.ledger).build_spent(submission_id)
        except Exception:  # noqa: BLE001
            return None  # unreadable: no row, the state alone as before
        if spent is None or spent["returned"]:
            return None
        return infra_diagnosis.recipe_spot_row()

    def grade_worker(self):
        """The PUBLIC facts of the machine that grades (exam_feedback v8): ``cpu_model`` (this host's own /proc/cpuinfo model
        name, or None), ``cpu_count`` and ``memory_bytes`` (the Challenge's registered resource policy, the limits every
        graded run gets), and ``gpu`` (whether this receiver grades with a GPU lane). Nothing measured, nothing of a run.
        """
        policy = {}
        try:
            policy = self.adapter.discovery._material["construction_limits_document"][
                "reconstruction_resource_policy"
            ]
        except (AttributeError, KeyError, TypeError):
            policy = {}

        def positive(name):
            value = policy.get(name) if type(policy) is dict else None
            return value if type(value) is int and value > 0 else None

        return {
            "cpu_model": _cpu_model(),
            "cpu_count": positive("cpu_count_max"),
            "memory_bytes": positive("memory_bytes_max"),
            "gpu": getattr(self, "grading_gpu", False) is True,
        }

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
    if state_dir is not None:
        # A20: while the operator's DRAINING flag is set, every request is answered 503 "updating" at once
        intake.updating_flag = Path(state_dir) / DRAIN_NAME
    httpd = hardened_listener(
        config,
        _header_bounded_handler(intake),
        service="construction-intake",
        local_hop=True,
    )
    # Join already-authenticated bounded handlers before taking the final
    # cancellation snapshot. Otherwise a submit may queue after cancellation.
    httpd.daemon_threads = False
    work = _WorkLock(
        grading_lock_dir,
        state_dir=state_dir,
        stop=stop,
        lanes=_door_lanes(intake, grading_lock_dir, state_dir),
        remote_only=_door_remote_only(intake, grading_lock_dir, state_dir),
    )
    threads = [
        threading.Thread(
            target=refresher,
            args=(intake.window, intake.context),
            kwargs={"stop": stop, "reader": reader},
            daemon=True,
        ),
    ]
    lanes_rounds = len(work._usable) if work._parallel else 1
    adapter = getattr(intake, "adapter", None)
    # A19 (Lead, 16 Nov 2026): one ADVANCE round per lane too (a build holds a lane like a grade), when the adapter
    # takes owners through the door's `OwnerClaims` (one owner's ledger lease is non-blocking); grades share them.
    advance_rounds = (
        lanes_rounds if getattr(adapter, "PARALLEL_ADVANCE", False) is True else 1
    )
    if advance_rounds > 1:
        # BUILD LANES (Lead 17 Nov 2026): builds take the LOCAL lanes only, one build round per local lane plus one per
        # remote GPU build slot (those wait on the remote box with their lane given back); the remote lanes grade
        advance_rounds = work.local_builds(_remote_build_slots(intake))
        if work.builds_laneless:
            work.box_up = lambda: _remote_box_up(intake)
        log(
            "direct_build_rounds",
            rounds=advance_rounds,
            local_only=work.builds_local,
            lanes=len(work._usable),
        )
    if advance_rounds > 1:
        from .grade_sequencer import OwnerClaims

        claims = OwnerClaims()
        adapter.owner_claims = claims
        if grader is not None:
            grader.owner_claims = claims
            # grade first per owner (`LeanRecipeAdapter._built_waits_to_grade`)
            adapter.grade_marked = lambda task: grader._marker(task).exists()
        # only now may a build round run beside a grade round: every round of this door takes its owner
        work.overlap_kinds = True
    for _ in range(advance_rounds):
        threads.append(
            threading.Thread(
                target=_advance_loop,
                args=(intake, stop, work, getattr(grader, "oldest_pending_ns", None)),
                # N parallel build rounds wait longer when idle; one keeps the loop's default (and its signature)
                kwargs=(
                    {
                        "idle_s": ADVANCE_IDLE_S,
                        # the start-up filing first, bounded (`STARTUP_PRELUDE_WAIT_SECONDS`)
                        "ready": (
                            None
                            if grader is None
                            else lambda: getattr(grader, "_stranded_filed", True)
                            is True
                        ),
                    }
                    if advance_rounds > 1
                    else {}
                ),
                daemon=True,
            )
        )
    if grader is not None:
        # A receiver that grades its own submissions (auto_grade): one grade at a
        # time, never while a reconstruction runs.
        if getattr(grader, "others_waiting", None) is None:
            # slow-tail F2: the king's upkeep waits while another door waits for the host lock
            grader.others_waiting = getattr(work, "_others_waiting", None)
        rounds = grade_rounds(lanes_rounds)
        if rounds > 1:
            # PARALLEL ROUNDS (owner's order 16 Nov, via the Lead): one grade thread per lane, committing in claim order
            from .grade_sequencer import Sequencer

            grader.sequencer = Sequencer()
        for _ in range(rounds):
            threads.append(
                threading.Thread(
                    target=_grade_loop, args=(grader, stop, work), daemon=True
                )
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
                for thread in threads[1 : 1 + advance_rounds]:
                    if thread in started:
                        thread.join()
                if threads[0] in started:
                    threads[0].join(5)
                if serving.ident is not None:
                    serving.join(5)


#: Seconds a background loop waits after its nth consecutive failure: a bounded
#: exponential backoff (an operational bound, not a scientific value). A loop
#: that keeps failing is never a once-a-second hot loop, and its own success resets
#: it. S7 I3 (audit row 126): capped at 15 s, not 300 s: one infra blip (docker,
#: ssh, db) no longer idles a lane's thread for minutes; a failed grade stays
#: pending or goes FAILED_INFRA by its own path, so the wait only spaces the
#: retries. (No reset on ANOTHER loop's success: on a busy door that would turn a
#: fault repeating in one loop into a retry every second; case-procs 22:00:07Z.)
FAILURE_BACKOFF_S = (1, 2, 4, 8, 15)


def _backoff_s(failures):
    return FAILURE_BACKOFF_S[min(failures, len(FAILURE_BACKOFF_S)) - 1]


def _closed_code(failure):
    """A typed refusal's code when it is a closed identifier (``[a-z0-9_.:-]``, at most 96 chars), else None: safe for
    the journal, never a message, path or value."""
    code = getattr(failure, "code", None)
    code = getattr(code, "value", code)
    if type(code) is str and re.fullmatch(r"[a-z0-9_.:-]{1,96}", code):
        return code
    return None


def _keep_failure(subject, loop, failure):
    """Keep a failure's full traceback in the receiver's PRIVATE evidence
    directory, one file per distinct failure site, and return the site's short
    id for the log line. The log carries the exception type and this id only:
    a traceback can hold private paths and content. Best effort: a subject
    without a ledger, or an unwritable directory, keeps nothing."""
    try:
        ledger = getattr(getattr(subject, "adapter", subject), "ledger", None)
        if ledger is None:
            # the grader holds its adapter through its intake (live 116, 19 Nov 2026: 190 grade-loop failures, no file)
            adapter = getattr(getattr(subject, "intake", None), "adapter", None)
            ledger = getattr(adapter, "ledger", None)
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
#: GRADES-ONLY PAUSE (owner LO-5, 20 Nov 2026: "Whatever stops this"; live-ops 14:43:05Z): while this flag is in the
#: state directory the door starts no NEW grade round (no claim, no regrade, no crown or king upkeep round) and every
#: grade round already started finishes; the front, uploads and build rounds go on (unlike DRAINING, nothing is
#: refused). The stop kit sets it (``door_drain.py pause``), waits for no live grade round (``wait-grades``, which
#: reads `GRADES_INFLIGHT_NAME`), stops, and clears it at UNDRAINED (``door_drain.py clear``).
GRADES_PAUSE_NAME = "grades-paused"
#: The OLDEST live grade round's in-flight record plus ``grades`` (how many grade rounds are live), parallel mode only;
#: absent when none is. A one-lane door's grade round is its `INFLIGHT_NAME` record (``kind`` ``grade``).
GRADES_INFLIGHT_NAME = "grades-inflight.json"
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
#: The host's list of doors that OUTRANK the testnet doors in the waiting list (in the lock's own directory): one file
#: per live waiting door, named like its waiting entry. A door bound to finney 116 is always in it while it waits; a
#: testnet door joins it once it has been held back for `MAINNET_FIRST_PATIENCE_S` (so testnet is never starved).
PRIORITY_DIR = "official-grading.priority"
#: The network whose doors go first for the host's grading lock (the mainnet subnet, `carbon.chain.models`).
MAINNET_FIRST_NETWORK = "finney"
#: How long a testnet round may be held back by waiting mainnet doors before it counts as one of them (an operational
#: bound on starvation, not a scientific value; the owner's rule is mainnet first, never testnet forever behind).
MAINNET_FIRST_PATIENCE_S = 7200.0


def _door_remote_only(intake, grading_lock_dir, state_dir):
    """Whether this door's own remote record asks for its remote lanes alone (`grade_lanes.door_remote_only`)."""
    if grading_lock_dir is None or state_dir is None:
        return False
    from carbon.reconstruction import grade_lanes, remote_lane

    if (Path(state_dir) / remote_lane.RECORD).exists():
        # the door's OWN record was installed on purpose: a broken one refuses the start (never silently local lanes)
        remote_lane.load_record(state_dir)
    return grade_lanes.door_remote_only(state_dir)


def _remote_box_up(intake):
    """Whether this door's remote GPU build pool has a box not down now (`remote_gpu_build.door_box_up`); an unreadable
    pool counts as up (a build round then starts laneless, as before)."""
    challenge = getattr(intake, "challenge", None)
    try:
        from carbon.reconstruction import remote_gpu_build

        return remote_gpu_build.door_box_up(
            getattr(challenge, "challenge_id", None),
            getattr(challenge, "version", None),
        )
    except Exception:  # noqa: BLE001 - a hint only
        return True


def _remote_build_slots(intake):
    """How many build rounds this door's REMOTE GPU build boxes may keep busy (`remote_gpu_build.door_build_slots`: a
    box pool's slots per box times its most boxes): 0 without a pool, for a local slot lane (its builds hold their
    lane), or when the pool cannot be read (logged; the start goes on).
    """
    challenge = getattr(intake, "challenge", None)
    try:
        from carbon.reconstruction import remote_gpu_build

        return remote_gpu_build.door_build_slots(
            getattr(challenge, "challenge_id", None),
            getattr(challenge, "version", None),
        )
    except Exception as failure:  # noqa: BLE001 - a build-round count, never a failure
        log("direct_build_rounds_lane_unreadable", type=type(failure).__name__)
        return 0


def _door_lanes(intake, grading_lock_dir, state_dir=None):
    """This door's grade lanes (`grade_lanes.door_lanes`): ``()`` = one lane, today's single host lock. Only a door
    that holds the host lock at all can have lanes. In two-lane mode, a REMOTE lane the values row asks for and the
    operator installed (`grade_lanes.door_remote_lanes`) follows the local lanes (a `remote_lane.RemoteSpec`).
    """
    if grading_lock_dir is None:
        return ()
    from carbon.reconstruction import grade_lanes

    challenge = getattr(intake, "challenge", None)
    key = (
        getattr(challenge, "challenge_id", None),
        getattr(challenge, "version", None),
    )
    local = grade_lanes.door_lanes(*key)
    if not local:
        return ()
    return (*local, *grade_lanes.door_remote_lanes(*key, state_root=state_dir))


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

    TWO GRADE LANES (owner 15 Nov, `carbon.reconstruction.grade_lanes`): with ``lanes`` (the lane cpusets
    `grade_lanes.door_lanes` allows this door; empty by default) a round holds ONE free lane, bound for the round so its
    containers run on that lane's cores; lane 0 is the host lock above. Without them (one-lane mode) a round holds EVERY
    lane, so it never runs next to anyone, as before. The waiting list below decides who may try either way, unchanged.

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
        self,
        grading_lock_dir=None,
        *,
        state_dir=None,
        stop=None,
        poll_s=None,
        network=None,
        lanes=(),
        remote_only=False,
    ):
        self._lock = threading.Lock()
        #: The lane cpusets of two-lane mode (empty: one lane), the lane the current round holds, and its lock files.
        self._lanes = tuple(lanes)
        #: The lanes this door's rounds may take: every one, or its remote lanes alone (``remote_only``: a door's own
        #: record asks for it); local lanes keep their places, so lock names and holder records never move.
        self._usable = tuple(
            index
            for index, spec in enumerate(self._lanes)
            if not (remote_only and type(spec) is str)
        )
        if remote_only and len(self._usable) < 2:
            # fewer than two remote lanes cannot be a remote-only lane door: every lane, as without the record
            self._usable = tuple(range(len(self._lanes)))
        self._lane = None
        self._fds = []
        #: PARALLEL ROUNDS (owner's order 16 Nov, via the Lead): in lane mode with two or more lanes, this door runs up to
        #: one round PER LANE at once (`_slots`); ``_lock`` is then held only while a round acquires its lane, and each
        #: round keeps its own lane and lock files (`_Taking`). Rounds of DIFFERENT kinds (``advance`` / ``grade``) run
        #: at once too (A19), never two of one owner (`grade_sequencer.OwnerClaims`). One lane: one slot, ``_lock`` held for
        #: the whole round, exactly today.
        self._parallel = len(self._usable) > 1
        #: A19: rounds of both kinds may run at once (set by the serving loop when every round takes its owner).
        self.overlap_kinds = False
        self._slots = threading.BoundedSemaphore(max(1, len(self._usable)))
        self._kinds = threading.Condition()
        #: The live rounds of this door: ``{round: (kind, in-flight record)}`` (parallel mode only).
        self._live = {}
        #: How many rounds of each kind wait for the other kind to finish: a waiting kind stops NEW rounds of the other
        #: kind from starting, so a build round is never starved by back-to-back grade rounds (or the reverse).
        self._kind_waiters = {}
        #: Option A (Lead 17 Nov 2026): how many of this door's build rounds wait to hold a lane AGAIN after their op on a
        #: remote GPU build box (`_Taking.retake`): they finish in-flight work, so no NEW round takes a slot before them.
        self._retakers = 0
        #: GRADE rounds waiting to hold a lane again after their commit-turn wait (`grade_lanes.given_back`): a NEW grade
        #: round stands back for them (`_acquire_slot`)
        self._grade_retakers = 0
        #: GRADE re-takes after a commit-turn wait that need a LOCAL lane (`_Taking.retake`). Each is the head of the
        #: door's commit order: every claimed grade waits on it. While one waits, BUILDS take no local lane (a NEW build
        #: round, or a build re-take), so the head never waits behind a build's whole run (live 116, 18 Nov 2026 stall
        #: #3: a copy grade at the head waited for a local lane 25+ min while builds re-took them). Never handed back
        #: (unlike the new-round priority, `RETAKE_PRIORITY_SECONDS`): it ends when the head holds a lane.
        self._turn_waiting_local = 0
        #: The live build rounds whose lane is out for an op on a remote GPU build box (`_Taking.release`): live (a drain
        #: sees them), but holding no lane, so the kind fairness never counts them (`_enter_parallel_both_kinds`).
        self._away = set()
        #: BUILD LANES (Lead 17 Nov 2026, `local_builds`): builds take the door's LOCAL lanes only, each build round
        #: holding one of `_build_slots` (one per local lane) beside its round slot; None: builds take any lane.
        self.builds_local = False
        self._build_slots = None
        #: Under `builds_laneless`: whether a remote GPU build box is up now (`_remote_box_up`); while none is, a NEW build
        #: round starts on a local lane with a build slot like any build (`_Taking.__enter__`), so at most one build per
        #: local lane is started (Lead, 18 Nov 2026: with the A100 down, 9 laneless rounds queued on one lane). None: up.
        self.box_up = None
        if network is None:
            from carbon.chain import models

            network = models.CARBON_NETWORK
        #: Mainnet first (owner, 13 Nov): a door bound to finney goes before any testnet door for the host lock.
        self._mainnet = network == MAINNET_FIRST_NETWORK
        #: When this round was first held back by an outranking waiter (monotonic), and whether it has waited
        #: `MAINNET_FIRST_PATIENCE_S` and so counts as outranking too (reset at every round start).
        self._held_since = None
        self._promoted = False
        self._dir = grading_lock_dir
        self._state = None if state_dir is None else Path(state_dir)
        self._stop = stop if stop is not None else threading.Event()
        self._poll = WORK_POLL_S if poll_s is None else poll_s
        self._fd = None
        self._legacy = threading.local()
        self._yield_until = 0.0
        self._was_draining = None
        self._was_grades_paused = None
        #: This door's place in the host's waiting list (`_mark_waiting`): the acceptance time of its oldest ungraded
        #: submission when the round knows it (``since``, slow-tail F1a), else the time its current GRADE round began to
        #: wait; None while not queued. A queued round takes the host lock only when no live other door is ahead of it.
        self._wait_since = None
        self._grade_round = False
        #: The place each kind of round last HELD the host lock with (``{kind: place}``). A round whose place has not
        #: moved since (its door's oldest unmarked submission is still the same one) counts as arriving now: a place
        #: frozen on an item that never gets a marker (a cancelled or orphaned task) must never keep the head of the
        #: host's waiting list, or every younger door starves (RB + Motor vs BT + Cooling, 10 Nov 06:15).
        self._served = {}
        if self._state is not None:
            for name in (INFLIGHT_NAME, WAIT_NAME, GRADES_INFLIGHT_NAME):
                left = self._state / name
                if left.exists():
                    # This process holds nothing yet: whatever is there is a previous process's, never trusted.
                    aside = left.with_name(f"{name}.stale-{time.time_ns()}")
                    os.replace(left, aside)
                    log("direct_work_record_stale", record=name, kept_as=aside.name)
            for name in (INFLIGHT_NAME, WAIT_NAME, GRADES_INFLIGHT_NAME):
                # A writer's temp files (a crash mid-write) are never records: removed. Set-aside records: newest kept.
                for staged in self._state.glob(f".{name}.*"):
                    staged.unlink(missing_ok=True)
                for old in sorted(self._state.glob(f"{name}.stale-*"))[:-STALE_KEPT]:
                    old.unlink(missing_ok=True)
        # Said once at start, and on every change: a door left DRAINING (or grades-paused) after a switch is never silent.
        self.draining()
        self.grades_paused()

    def draining(self):
        draining = self._state is not None and (self._state / DRAIN_NAME).exists()
        if draining != self._was_draining:
            self._was_draining = draining
            if self._state is not None:
                log("direct_work_draining", draining=draining)
        return draining

    def grades_paused(self):
        """Whether the GRADES-ONLY pause is set (`GRADES_PAUSE_NAME`); said once at start and on every change."""
        paused = self._state is not None and (self._state / GRADES_PAUSE_NAME).exists()
        if paused != self._was_grades_paused:
            self._was_grades_paused = paused
            if self._state is not None:
                log("direct_work_grades_paused", paused=paused)
        return paused

    def _declined(self):
        if self._stop.is_set():
            return "stopping"
        if self.draining():
            return "draining"
        return None

    def _waiting_dir(self):
        return Path(self._dir) / WAITING_DIR

    def _priority_dir(self):
        return Path(self._dir) / PRIORITY_DIR

    def _outranks(self):
        """Whether this door's round goes before every testnet round: a finney door, or a testnet round that has
        waited out `MAINNET_FIRST_PATIENCE_S`."""
        return self._mainnet or self._promoted

    def _waiters(self):
        """``[(since_ns, pid)]`` of every LIVE other process (another door) waiting for the host lock with a grade to
        run. An entry whose process is gone (pid reused or exited) is not a waiter; one without a readable time
        counts as waiting since 0 (oldest: never lets a door jump it)."""
        return [(since, pid) for _, since, pid in self._classed_waiters()]

    def _classed_waiters(self):
        """``[(class, since_ns, pid)]`` of the live other waiting doors: class 0 when the door is in the priority
        list (finney, or a testnet round past its patience), else 1 (a door that wrote no such file, an older build
        included, is class 1). Sorts first-come within a class, class 0 before class 1.
        """
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
            outranks = (self._priority_dir() / entry.name).exists()
            live.append((0 if outranks else 1, since, int(pid)))
        return live

    def _others_waiting(self):
        """Whether another live process (another door) waits for the host lock with a grade to run."""
        return bool(self._waiters())

    def _behind_an_earlier_waiter(self):
        """Whether a QUEUED round must let another door go first: a live other door is ahead of it in the host's one
        waiting list (Deploy 5 Nov: Motor's due king work lost the race to three doors for over an hour). A round's
        place is the acceptance time of its door's oldest ungraded submission when it carries one (``since``: slow-tail
        F1a, Lead / TE-B 8 Nov), for a GRADE and an ADVANCE (rebuild) round alike, so the oldest submission on the host
        always goes next whichever step it needs; a grade round without one counts as arriving now. Ties go to the
        lower pid. An advance round without a place (nothing ungraded on its door) never queues, as before.

        MAINNET FIRST (owner, 13 Nov): every waiting finney door goes before every testnet round, queued or not
        (an advance round without a place included: it still never queues among its own class). A testnet round held
        back this way for `MAINNET_FIRST_PATIENCE_S` counts as outranking too from then on (first come among them), so
        testnet is never starved forever. Within one class the order is the one above, unchanged; a lone door, or doors
        of one network, see no difference. A round already holding the host lock is never preempted.
        """
        waiters = self._classed_waiters()
        if not self._outranks():
            if any(rank == 0 for rank, _, _ in waiters):
                now = time.monotonic()
                if self._held_since is None:
                    self._held_since = now
                if now - self._held_since < MAINNET_FIRST_PATIENCE_S:
                    return True
                self._promoted = True
                log("direct_work_mainnet_first_patience_spent")
            else:
                self._held_since = None
        if not self._grade_round:
            return False
        mine = (
            0 if self._outranks() else 1,
            time.time_ns() if self._wait_since is None else self._wait_since,
            os.getpid(),
        )
        return any(other < mine for other in waiters)

    def _mark_waiting(self, waiting):
        """This door's entry in the host's waiting list (``<lock dir>/official-grading.waiting/<pid>-<start>``), holding
        the time it began to wait (its place in the round-robin)."""
        path = self._waiting_dir() / f"{os.getpid()}-{_process_start(os.getpid())}"
        rank = self._priority_dir() / path.name
        if waiting:
            if self._outranks() and not rank.exists():
                # BEFORE the waiting entry, so a reader never sees an outranking door as class 1
                self._priority_dir().mkdir(mode=0o700, exist_ok=True)
                rank.touch(mode=0o600)
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
            rank.unlink(missing_ok=True)
            self._wait_since = None

    def _try_host(self, kind=None):
        """Take the host's official-grading lock without blocking; True when held. A door that has just released it
        while another door waits stands back for 2 polls first, so a busy door's back-to-back rounds never shut
        a polling door out (fairness without a queue: the waiter's next poll falls inside the gap).

        One lane: the host lock AND every other lane lock, all or none (`_take`). Two lanes: the first free lane.
        With `builds_local` (Lead 17 Nov 2026): a BUILD round (``kind`` ``advance``) takes a LOCAL lane only, and any
        other round tries the REMOTE lanes first, so the remote grade lanes always grade and the local lanes stay free
        for builds while a remote lane is.
        """
        from carbon.backbone_catalog.receipt_job import GRADING_LOCK

        if time.monotonic() < self._yield_until:
            return False
        if self._behind_an_earlier_waiter():
            return False
        from carbon.reconstruction import grade_lanes

        if not self._lanes:
            # one lane: lane 0 (the host lock) and every other lane, all or none
            for index in range(grade_lanes.ALL_LANES):
                fd = self._take(
                    GRADING_LOCK if index == 0 else grade_lanes.lane_lock_name(index)
                )
                if fd is None:
                    self._release_fds()
                    return False
                self._fds.append(fd)
            self._hold(None, grade_lanes.ONE_LANE_MODE)
            return True
        # two lanes: the first free lane, in index order
        order = list(enumerate(self._lanes))
        if self.builds_local:
            local = [(index, spec) for index, spec in order if type(spec) is str]
            remote = [pair for pair in order if type(pair[1]) is not str]
            # live 116 (7aeaa273, 17 Nov 22:2xZ): a grade that fell back to a local lane held it for minutes, so the
            # A100's builds found no local lane to start or re-take and the A100 sat idle with 69 builds queued. With
            # remote grade lanes, grades take ONLY those (`_grades_remote_only`); the local lanes are the builds'.
            order = local if kind == "advance" else remote + self._grade_local(local)
        for index, spec in order:
            if index not in self._usable:
                continue
            fd = self._take(grade_lanes.lane_lock_name(index))
            if fd is None:
                continue
            self._fds.append(fd)
            if index > 0 and type(spec) is str and not self._lane_zero_shares():
                # lane 0's share rule guards THIS host's cores only: a remote lane (another machine) never waits on it
                self._release_fds()
                return False
            self._hold(
                (
                    grade_lanes.Lane(index, spec, str(self._dir))
                    if type(spec) is str
                    # a remote lane (`remote_lane.RemoteSpec`): its daemon, its cores, its mirror root
                    else grade_lanes.Lane(
                        index,
                        spec.cpuset,
                        str(self._dir),
                        spec.docker_host,
                        spec.stage_root,
                    )
                ),
                grade_lanes.TWO_LANE_MODE,
            )
            return True
        return False

    def _take(self, name):
        """One lane lock, taken without blocking: its open descriptor, or None while another holds it."""
        import fcntl

        fd = os.open(Path(self._dir) / name, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return None
        except BaseException:
            os.close(fd)
            raise
        return fd

    def _lane_zero_shares(self):
        """Whether a round may run on a lane other than 0: lane 0 is free, or held by a door in two-lane mode. Never
        beside a door that does not know about lanes (an older build holds lane 0 only, writes no holder record) or a
        door in one-lane mode."""
        from carbon.reconstruction import grade_lanes

        if grade_lanes.held_in_two_lane_mode(self._dir, 0):
            return True
        probe = self._take(grade_lanes.lane_lock_name(0))
        if probe is None:
            return False
        self._unlock(probe)
        return True

    def _hold(self, lane, mode):
        """Record the lanes this round now holds (`grade_lanes.write_holder`); ``lane`` None = all of them."""
        from carbon.reconstruction import grade_lanes

        self._fd = self._fds[0]
        self._lane = lane
        for index in range(grade_lanes.ALL_LANES) if lane is None else (lane.index,):
            grade_lanes.write_holder(self._dir, index, mode)

    @staticmethod
    def _unlock(fd):
        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _release_fds(self):
        fds, self._fds = self._fds, []
        for fd in reversed(fds):
            self._unlock(fd)

    def _release_host(self):
        fd, fds, lane = self._fd, self._fds, self._lane
        self._fd, self._fds, self._lane = None, [], None
        self._release_round(fd, fds, lane)

    def _release_round(self, fd, fds, lane):
        """Give back one round's host lanes: its holder records, then its lock files."""
        held = fd is not None
        if held:
            from carbon.reconstruction import grade_lanes

            # the holder records go BEFORE the locks: a reader never sees a free lock with a stale holder of ours
            for index in (
                range(grade_lanes.ALL_LANES) if lane is None else (lane.index,)
            ):
                grade_lanes.clear_holder(self._dir, index)
        for one in reversed(fds):
            self._unlock(one)
        if held and self._others_waiting():
            self._yield_until = time.monotonic() + 2 * self._poll

    # -- parallel rounds (lane mode, two or more lanes) ------------------------------------------------------------------

    def _enter_parallel(self, kind):
        if not getattr(self, "overlap_kinds", False):
            return self._enter_parallel_one_kind(kind)
        return self._enter_parallel_both_kinds(kind)

    def _enter_parallel_one_kind(self, kind):
        """Take one of this door's round slots, then wait until no live round of another kind runs (a door whose rounds
        take no owners, `grade_sequencer.OwnerClaims`: an owner's ledger lease is non-blocking). Polls, and gives up
        the round (`WorkDeclined`) as soon as the door stops or drains."""
        while not self._acquire_slot(kind):
            reason = self._declined()
            if reason is not None:
                raise WorkDeclined(reason)
        try:
            with self._kinds:
                waiting = False
                try:
                    while any(other != kind for other, _ in self._live.values()) or any(
                        count and other != kind
                        for other, count in self._kind_waiters.items()
                    ):
                        if not waiting and any(
                            other != kind for other, _ in self._live.values()
                        ):
                            waiting = True
                            self._kind_waiters[kind] = (
                                self._kind_waiters.get(kind, 0) + 1
                            )
                        self._kinds.wait(self._poll)
                        reason = self._declined()
                        if reason is not None:
                            raise WorkDeclined(reason)
                finally:
                    if waiting:
                        self._kind_waiters[kind] -= 1
                        self._kinds.notify_all()
                self._live[threading.get_ident()] = (kind, None)
        except BaseException:
            self._release_slot(kind)
            raise

    def _enter_parallel_both_kinds(self, kind):
        """Take one of this door's round slots (A19, Lead 16 Nov 2026: rounds of BOTH kinds run at once, each on its own
        lane; owners never overlap, `grade_sequencer.OwnerClaims`). Fairness: while another kind waits for a slot and
        has no live round, a kind that already has one live round starts no NEW one, so neither builds nor grades are
        starved. Polls, and gives up the round (`WorkDeclined`) as soon as the door stops or drains.
        """
        with self._kinds:
            self._kind_waiters[kind] = self._kind_waiters.get(kind, 0) + 1
        try:
            while True:
                with self._kinds:
                    # a round whose lane is out (on the remote GPU build box) holds no lane: not live for fairness, so
                    # a build waiting to START (it needs a local lane) is never starved by back-to-back grade rounds
                    live = [
                        other
                        for ident, (other, _) in self._live.items()
                        if ident not in self._away
                    ]
                    yield_to_other = live.count(kind) >= 1 and any(
                        count and other != kind and other not in live
                        for other, count in self._kind_waiters.items()
                    )
                if yield_to_other and kind != "advance" and self.builds_local:
                    # builds take LOCAL lanes only: a grade stands back for a waiting build only when it would take a
                    # local lane itself, never while a remote lane it could grade on is free
                    yield_to_other = not self._remote_lane_free()
                if yield_to_other and kind == "advance" and self._grades_remote_only():
                    # S7 I3 (audit row 124): grades take REMOTE lanes only and builds LOCAL lanes only, so the lanes
                    # are disjoint: a build standing back for a waiting grade frees nothing that grade could use
                    yield_to_other = False
                if not yield_to_other and self._acquire_slot(kind):
                    break
                if yield_to_other:
                    with self._kinds:
                        self._kinds.wait(self._poll)
                reason = self._declined()
                if reason is not None:
                    raise WorkDeclined(reason)
            try:
                with self._kinds:
                    self._live[threading.get_ident()] = (kind, None)
            except BaseException:
                self._release_slot(kind)
                raise
        finally:
            with self._kinds:
                self._kind_waiters[kind] -= 1
                self._kinds.notify_all()

    def _box_is_up(self):
        probe = getattr(self, "box_up", None)
        if probe is None:
            return True
        try:
            return probe() is not False
        except Exception:  # noqa: BLE001 - unknown: laneless, as before
            return True

    def _remote_lane_free(self):
        return self._lane_free(local=False)

    def _lane_free(self, *, local, skip=()):
        """Whether one of this door's LOCAL (or REMOTE) lanes, but those in ``skip``, is free now (a probe of its lock,
        let go at once: a hint, never a hold)."""
        from carbon.reconstruction import grade_lanes

        for index in self._usable:
            if (type(self._lanes[index]) is str) is not local or index in skip:
                continue
            fd = self._take(grade_lanes.lane_lock_name(index))
            if fd is not None:
                self._unlock(fd)
                return True
        return False

    def _acquire_slot(self, kind=None):
        """One round slot for a NEW round of ``kind``, within one poll: never while a build round of this door waits to
        re-take a lane (`_Taking.retake`). Under `builds_local` only a NEW BUILD round stands back for it (a re-take
        needs a build slot, which grade rounds never hold): grade rounds keep starting on the remote lanes meanwhile.
        """
        with self._kinds:
            retaking = (
                (
                    self._retakers > 0
                    and (kind == "advance" or self._build_slots is None)
                )
                or (self._grade_retakers > 0 and kind != "advance")
                # the head of the commit order waits for a local lane: no NEW build round takes one first
                or (self._turn_waiting_local > 0 and kind == "advance")
            )
        if retaking:
            time.sleep(self._poll)
            return False
        return self._take_slots(kind)

    def _grades_remote_only(self):
        """Whether this door's grade rounds are kept off (some of) its local lanes: `builds_local` with at least one
        usable remote lane (live 116, 17 Nov: grades on the local lanes starved the A100's builds of the lane each needs
        to start and re-take). A door with no remote grade lane grades on its local lanes, as before.
        """
        return self.builds_local and any(
            type(self._lanes[index]) is not str for index in self._usable
        )

    def _grade_local(self, local):
        """The ``(index, spec)`` local lanes a grade round may take: every one on a door with no remote grade lane; on a
        door whose builds start laneless (`builds_laneless`), every one not reserved for builds (all are, since 19 Nov
        2026); else none.
        """
        if not self._grades_remote_only():
            return local
        reserved = getattr(self, "_reserved_local", ())
        if getattr(self, "builds_laneless", False):
            return [pair for pair in local if pair[0] not in reserved]
        return []

    def _take_slots(self, kind):
        """A round slot, plus a build slot first for a build round under `builds_local` (so at most one build round per
        local lane holds a round slot), within one poll each. A grade round of a door whose grades take remote lanes only
        (`_grades_remote_only`) never sits on a round slot while no remote lane is free, as a build never does while no
        local lane is.
        """
        if (
            kind != "advance"
            and self._grades_remote_only()
            and not (
                self._lane_free(local=False)
                or (
                    getattr(self, "builds_laneless", False)
                    and self._lane_free(local=True, skip=self._reserved_local)
                )
            )
        ):
            time.sleep(self._poll)
            return False
        if self._build_slots is not None and kind == "advance":
            if not self._lane_free(local=True):
                # a build only ever takes a LOCAL lane: it never sits on a round slot a grade could use on a free
                # remote lane while it waits for one
                time.sleep(self._poll)
                return False
            if not self._build_slots.acquire(timeout=self._poll):
                return False
            if not self._slots.acquire(timeout=self._poll):
                self._build_slots.release()
                return False
            return True
        return self._slots.acquire(timeout=self._poll)

    def _release_slot(self, kind):
        self._slots.release()
        if self._build_slots is not None and kind == "advance":
            self._build_slots.release()

    def local_builds(self, extra_rounds):
        """BUILD LANES (Lead 17 Nov 2026): this door's build rounds take its LOCAL lanes only (the remote grade lanes
        always grade), at most one build round per local lane holding a round slot; returns how many build rounds the
        door runs: one per local lane plus ``extra_rounds`` (its remote GPU build slots: those rounds wait on the remote
        box with their lane given back, `grade_lanes.released`). A door with fewer than two local lanes it may use (one
        lane, or a remote-only door): unchanged, one build round per usable lane."""
        local = [index for index in self._usable if type(self._lanes[index]) is str]
        if not self._parallel or len(local) < 2:
            return len(self._usable) if self._parallel else 1
        self.builds_local = True
        self._build_slots = threading.BoundedSemaphore(len(local))
        # Owner, 17 Nov 2026 ("make them independent of each other"): with remote GPU build slots, a build round STARTS
        # with no lane (`_Taking._enter_laneless`: it needs only its remote slot), and its local part runs on a local
        # lane re-taken when it needs one. EVERY local lane is RESERVED for builds (`_reserved_local`; Lead 19 Nov 2026:
        # with one reserved lane the A100 slots' local parts queued up to 605 s, live 116 13:31-13:37Z, while grades held
        # the other; the local EPYC lanes grade ~2x slower than the remote Ryzen lanes anyway, 597 s vs 313 s): grades
        # run on the remote lanes only, so a build's local part never waits behind a grade.
        # (a door with no remote grade lane grades on its local lanes: its builds start on one, as before)
        self.builds_laneless = extra_rounds > 0 and self._grades_remote_only()
        self._reserved_local = tuple(local) if self.builds_laneless else ()
        return len(local) + max(0, extra_rounds)

    def _take_local_lane(self, *, like=None):
        """The first free LOCAL lane this door may use, as a round's own ``(fd, fds, lane)``, or None. ``like`` (a grade
        round's lane given back for its commit turn): that same lane first, else another lane of the SAME machine only
        (this host's local lanes, or the same box's), never another class (V2 17 Nov 2026: a crown repeat after the
        commit turn runs where the grade ran). Called by a round re-taking a lane
        (`_Taking.retake`), WITHOUT ``_lock`` (a new round holds that while it waits among doors;
        this touches none of the fields it guards, and the lane locks themselves decide): it continues in-flight work,
        so it neither queues in the host's waiting list nor stands back; a lane other than 0 still needs lane 0 to share
        (`_lane_zero_shares`). A failure after a lock is taken lets that lock go."""
        from carbon.reconstruction import grade_lanes

        def machine(spec):
            return None if type(spec) is str else spec.docker_host

        order = list(enumerate(self._lanes))
        wanted = None if like is None else like.docker_host
        if like is not None:
            # the lane given back first, then the rest of its machine, in index order
            order = sorted(order, key=lambda pair: pair[0] != like.index)
        for index, spec in order:
            if index not in self._usable or machine(spec) != wanted:
                continue
            fd = self._take(grade_lanes.lane_lock_name(index))
            if fd is None:
                continue
            try:
                # this host's lanes only (live 116, 18 Nov 02:40Z: a grade re-taking its REMOTE lane after its commit
                # turn waited on the host's lane 0, and every new grade round stood back behind it)
                if index > 0 and type(spec) is str and not self._lane_zero_shares():
                    self._unlock(fd)
                    return None
                grade_lanes.write_holder(self._dir, index, grade_lanes.TWO_LANE_MODE)
            except BaseException:
                self._unlock(fd)
                raise
            if type(spec) is str:
                return fd, [fd], grade_lanes.Lane(index, spec, str(self._dir))
            # a remote lane (`remote_lane.RemoteSpec`): its daemon, its cores, its mirror root
            return (
                fd,
                [fd],
                grade_lanes.Lane(
                    index,
                    spec.cpuset,
                    str(self._dir),
                    spec.docker_host,
                    spec.stage_root,
                ),
            )
        return None

    def _record_live(self, record):
        """This round's in-flight record; the door's file names the OLDEST live round (a drain sees busy until all end)."""
        with self._kinds:
            kind, _ = self._live[threading.get_ident()]
            self._live[threading.get_ident()] = (kind, record)
            self._write_oldest()

    def _leave_parallel(self):
        self._release_slot(self._leave_live())

    def _leave_live(self):
        """Remove this round from the live rounds; returns its kind (None: it was not live)."""
        with self._kinds:
            self._away.discard(threading.get_ident())
            kind, _ = self._live.pop(threading.get_ident(), (None, None))
            self._write_oldest()
            self._kinds.notify_all()
        return kind

    def _write_oldest(self):
        if self._state is None:
            return
        records = [record for _, record in self._live.values() if record is not None]
        if records:
            _write_record(
                self._state / INFLIGHT_NAME,
                min(records, key=lambda record: record["since_ns"]),
            )
        else:
            (self._state / INFLIGHT_NAME).unlink(missing_ok=True)
        # the grade rounds alone: a grades-only pause waits for these, never for the builds
        grades = [
            record
            for kind, record in self._live.values()
            if kind == "grade" and record is not None
        ]
        if grades:
            _write_record(
                self._state / GRADES_INFLIGHT_NAME,
                {
                    **min(grades, key=lambda record: record["since_ns"]),
                    "grades": len(grades),
                },
            )
        else:
            (self._state / GRADES_INFLIGHT_NAME).unlink(missing_ok=True)

    def taking(self, kind, *, has_work=None, since=None):
        """A context for one round of ``kind`` work (``advance`` or ``grade``). ``has_work`` (called under the
        door's own lock) lets a round with nothing to do skip the host lock entirely (`WorkDeclined("idle")`).
        ``since`` (called likewise) gives the round's place in the host's waiting list: the acceptance time (ns) of
        its door's oldest ungraded submission, or None (`AutoGrader.oldest_pending_ns`).
        """
        return _Taking(self, kind, has_work, since)

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

    def __init__(self, work, kind, has_work, since=None):
        self.work, self.kind, self.has_work, self.since = work, kind, has_work, since
        #: The place this round queued by (None: none, or a frozen one that already had its turn).
        self.place = None
        #: A two-lane round's lane binding (`grade_lanes.bind`), reset at exit.
        self._lane_token = None
        #: PARALLEL rounds only: this round's own host lanes (moved off the shared lock object once held).
        self._parallel = False
        self._held = (None, [], None)
        #: Option A: the `grade_lanes.offer_releaser` token offering this round to its ops, and whether its lane is out (`release`).
        self._releasing = None
        self._released = False
        #: The lane this round gave back (`release`): a GRADE round re-takes it, or one of its machine (`retake`).
        self._gave_back = None
        #: (a): a GRADE round re-takes the lane it gave back for its commit-turn wait, or another of the same machine
        #: (`grade_lanes.given_back`, V2 17 Nov 2026); a build round re-takes a LOCAL lane only (Option A).
        self.any_lane = kind == "grade"

    def _place(self):
        """The round's place from ``since`` (a non-negative int of ns), or None: a failing or odd reader never
        blocks a round, it only loses its place (the earlier behaviour)."""
        if self.since is None:
            return None
        try:
            place = self.since()
        # a place is an optimisation, never a reason to stop work
        except Exception as failure:  # noqa: BLE001
            log("direct_work_place_unavailable", type=type(failure).__name__)
            return None
        return place if type(place) is int and place >= 0 else None

    @staticmethod
    def _poll_without_lock(work):
        """One poll of a BUILD round waiting for a local lane (`builds_local`), with ``_lock`` let go meanwhile, so the
        door's other rounds keep taking lanes; this round's queue fields are put back once it holds ``_lock`` again.
        Gives up the round (`WorkDeclined`) as soon as the door stops or drains."""
        saved = (work._grade_round, work._wait_since, work._held_since, work._promoted)
        work._lock.release()
        try:
            work._stop.wait(work._poll)
        finally:
            work._lock.acquire()
            work._grade_round, work._wait_since = saved[0], saved[1]
            work._held_since, work._promoted = saved[2], saved[3]
        reason = work._declined()
        if reason is not None:
            raise WorkDeclined(reason)

    def _refused(self):
        """Why this NEW round may not start: the door's stop or DRAINING (`_WorkLock._declined`), or, for a GRADE round,
        the grades-only pause (`GRADES_PAUSE_NAME`). Read at every check of the round's start, the last one after its
        in-flight record is down, so a kit that sets the pause and then reads no live grade record never sees a grade
        start after it. A started round (its re-takes included) never reads the pause: it finishes.
        """
        reason = self.work._declined()
        if reason is None and self.kind == "grade" and self.work.grades_paused():
            reason = "grades_paused"
        return reason

    def _inflight(self):
        lane = self.work._lane if not self._parallel else self._held[2]
        return {
            "schema": INFLIGHT_SCHEMA,
            "kind": self.kind,
            "pid": os.getpid(),
            "pid_start": _process_start(os.getpid()),
            "since_ns": time.time_ns(),
            # two-lane mode only: the lane and its cores (a one-lane record is unchanged)
            **({} if lane is None else {"lane": lane.index, "cpuset": lane.cpuset}),
        }

    def __enter__(self):
        work = self.work
        self._parallel = work._parallel
        reason = self._refused()
        if reason is not None:
            raise WorkDeclined(reason)
        if (
            self._parallel
            and self.kind == "advance"
            and getattr(work, "builds_laneless", False)
            and getattr(work, "overlap_kinds", False)
            and (getattr(work, "_box_is_up", None) is None or work._box_is_up())
        ):
            return self._enter_laneless()
        if self._parallel:
            work._enter_parallel(self.kind)
        try:
            while not work._lock.acquire(timeout=work._poll):
                reason = self._refused()
                if reason is not None:
                    raise WorkDeclined(reason)
        except BaseException:
            if self._parallel:
                work._leave_parallel()
            raise
        recorded = False
        # Only a GRADE with work waits visibly (the starvation-alert input and the host's waiting list): an advance
        # round cannot tell whether it has work, and must never look like a starving door.
        visible = self.kind == "grade" and self.has_work is not None
        work._grade_round = visible
        work._wait_since = None
        work._held_since, work._promoted = None, False
        waiting = False
        try:
            reason = self._refused()
            if reason is not None:
                raise WorkDeclined(reason)
            if self.has_work is not None and not self.has_work():
                raise WorkDeclined("idle")
            # slow-tail F1a: a round that knows its door's oldest ungraded submission queues by it (advance included)
            place = self._place() if work._dir is not None else None
            if place is not None and work._served.get(self.kind) == place:
                # this door already held the host with this same place and it did not move: no head of the queue
                # again until it does (it queues as a round without a place: round-robin, as before F1a)
                place = None
            self.place = place
            if place is not None:
                work._grade_round = True
                work._wait_since = place
            queued = work._grade_round
            # BUILD LANES: a build round waits for one of the LOCAL lanes only, which grade rounds may hold for a whole
            # grade; it never sleeps holding ``_lock``, so the door's grade rounds keep starting on the remote lanes
            lets_go = self._parallel and work.builds_local and self.kind == "advance"
            # a GRADE of a door whose grades keep off the builds' local lanes never waits here holding ``_lock`` and a
            # round slot (its slot check is a hint: another round may take the lane first): it gives the round up and
            # the grade loop tries again, so a build never waits behind it (Runner, 17 Nov 2026)
            gives_up = (
                self._parallel and self.kind != "advance" and work._grades_remote_only()
            )
            while work._dir is not None and not work._try_host(self.kind):
                if gives_up:
                    raise WorkDeclined("no_grade_lane")
                if lets_go:
                    self._poll_without_lock(work)
                    continue
                if queued and not waiting:
                    if visible and work._state is not None:
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
                reason = self._refused()
                if reason is not None:
                    raise WorkDeclined(reason)
            if waiting:
                work._mark_waiting(False)
                if work._state is not None:
                    (work._state / WAIT_NAME).unlink(missing_ok=True)
                waiting = False
            if self._parallel:
                # this round's host lanes are its own from here (another round of this door may take the next lane)
                self._held = (work._fd, work._fds, work._lane)
                work._fd, work._fds, work._lane = None, [], None
            # The in-flight record goes down BEFORE the last check, so a drain that reads "no record" can never be
            # followed by a round starting: either the round sees DRAINING here, or the drain sees its record.
            if work._state is not None:
                if self._parallel:
                    work._record_live(self._inflight())
                else:
                    _write_record(work._state / INFLIGHT_NAME, self._inflight())
                recorded = True
            reason = self._refused()
            if reason is not None:
                raise WorkDeclined(reason)
            lane = self._held[2] if self._parallel else work._lane
            if lane is not None:
                # this round's containers run on its lane's cores (`host_execution.resolve_cpuset`)
                from carbon.reconstruction import grade_lanes

                self._lane_token = grade_lanes.bind(lane)
                if (
                    self._parallel
                    and self.kind == "advance"
                    and getattr(work, "overlap_kinds", False)
                    and lane.docker_host is None
                ):
                    # Option A (Lead 17 Nov 2026): a build op on a REMOTE GPU build box gives this LOCAL lane back for
                    # its run and holds one again after (`grade_lanes.released`)
                    self._releasing = grade_lanes.offer_releaser(self)
                elif self._parallel and self.kind == "grade":
                    # (a) (Lead 17 Nov 2026): a grade gives its lane back while it waits for its commit turn and holds
                    # one again after (`grade_lanes.given_back`)
                    self._releasing = grade_lanes.offer_releaser(self)
        except BaseException:
            try:
                if waiting:
                    work._mark_waiting(False)
                if work._state is not None:
                    (work._state / WAIT_NAME).unlink(missing_ok=True)
                    if recorded and not self._parallel:
                        (work._state / INFLIGHT_NAME).unlink(missing_ok=True)
                if self._parallel:
                    held, self._held = self._held, (None, [], None)
                    work._release_round(*held)
                work._release_host()
            finally:
                work._lock.release()
                if self._parallel:
                    work._leave_parallel()
            raise
        if self._parallel:
            # the shared lock only guards acquiring a lane: the next round of this door may now take another one
            work._lock.release()
        return work

    def _enter_laneless(self):
        """A BUILD round of a door whose builds start laneless (`_WorkLock.builds_laneless`; owner, 17 Nov 2026): it holds
        no lane and no round slot, only its place among the door's live rounds (a drain still sees it busy) and its
        releaser, in the state of a round whose lane is out (`release`). Its remote GPU op needs nothing more; an op that
        runs on this host first holds a LOCAL lane (`grade_lanes.laned`, `grade_lanes.released`: `retake`, the builds'
        reserved lane first), so no container ever runs unpinned. Grades never wait for it, nor it for them.
        """
        from carbon.reconstruction import grade_lanes

        work = self.work
        reason = work._declined()
        if reason is not None:
            raise WorkDeclined(reason)
        if self.has_work is not None and not self.has_work():
            raise WorkDeclined("idle")
        ident = threading.get_ident()
        with work._kinds:
            work._live[ident] = (self.kind, None)
            work._away.add(ident)
            work._kinds.notify_all()
        self._released, self._held = True, (None, [], None)
        try:
            if work._state is not None:
                work._record_live(self._inflight())
            reason = work._declined()
            if reason is not None:
                raise WorkDeclined(reason)
        except BaseException:
            self._released = False
            work._leave_live()
            raise
        self._lane_token = grade_lanes.bind(None)
        self._releasing = grade_lanes.offer_releaser(self)
        return work

    def __exit__(self, *exc):
        work = self.work
        if self.place is not None:
            work._served[self.kind] = self.place  # this round held the host with it
        releasing, self._releasing = self._releasing, None
        if releasing is not None:
            from carbon.reconstruction import grade_lanes

            grade_lanes.withdraw_releaser(releasing)
        token, self._lane_token = self._lane_token, None
        if token is not None:
            from carbon.reconstruction import grade_lanes

            grade_lanes.unbind(token)
        if self._parallel and self._released:
            # a round whose lane is out holds no slot either: both went back together (`release`)
            self._released = False
            work._leave_live()
            return False
        if self._parallel:
            held, self._held = self._held, (None, [], None)
            try:
                work._release_round(*held)
            finally:
                work._leave_parallel()
            return False
        try:
            if work._state is not None:
                (work._state / INFLIGHT_NAME).unlink(missing_ok=True)
        finally:
            try:
                work._release_host()
            finally:
                work._lock.release()
        return False

    # -- Option A (Lead 17 Nov 2026): a build round's lane while its op runs on a remote GPU build box ------------------

    def release(self):
        """Give this round's LOCAL lane and its round slot back (`grade_lanes.released`), so the door's other rounds
        may use them. The round stays live (its in-flight record, without a lane), so a drain still sees it busy.
        """
        work = self.work
        if self._released or not self._parallel:
            return
        held, self._held = self._held, (None, [], None)
        self._gave_back = held[2]
        try:
            work._release_round(*held)
        finally:
            self._released = True
            with work._kinds:
                work._away.add(threading.get_ident())
                work._kinds.notify_all()
            work._release_slot(self.kind)
            try:
                with work._kinds:
                    kind, record = work._live[threading.get_ident()]
                    if record is not None:
                        record = {
                            key: value
                            for key, value in record.items()
                            if key not in ("lane", "cpuset")
                        }
                    work._live[threading.get_ident()] = (kind, record)
                    work._write_oldest()
                    work._kinds.notify_all()
            except Exception as failure:  # noqa: BLE001
                # the record keeps naming this round (busy) with its old lane until it re-takes one: never a stop
                log("direct_work_lane_record_failed", type=type(failure).__name__)
        log(
            "direct_work_lane_released",
            kind=self.kind,
            lane=None if held[2] is None else held[2].index,
        )

    def retake(self):
        """Hold a round slot and a LOCAL lane again, before any NEW round of this door takes one; returns the lane.
        In-flight work is finished whatever happens meanwhile: it never declines on drain or stop, nor queues among
        doors; it waits only for a lane to be free. It never returns without a lane held (V2 B1: its caller must never go
        on bound to the lane it gave back): a failure taking one is logged (``direct_work_lane_retake_retry``) and tried
        again, so a broken host shows as a round that stays busy, never as a container on another round's cores.
        """
        work = self.work
        if not self._released:
            return self._held[2]
        began = time.monotonic()
        counter = "_grade_retakers" if self.any_lane else "_retakers"
        # a grade re-taking a LOCAL lane (its given-back lane is local, or unknown) is the commit order's head: builds
        # stand back for it until it holds one (`_turn_waiting_local`)
        head_local = self.any_lane and (
            self._gave_back is None or self._gave_back.docker_host is None
        )
        with work._kinds:
            setattr(work, counter, getattr(work, counter) + 1)
            if head_local:
                work._turn_waiting_local += 1
        # A re-take that keeps waiting is logged each minute, and after RETAKE_PRIORITY_SECONDS it stops making new
        # rounds stand back (it still waits for a lane: never on without one, V2 B1), so one stuck re-take never
        # stops the door's grading (live 116, 18 Nov 02:40Z).
        standing = [True]
        logged = [began]

        def waiting():
            now = time.monotonic()
            if now - logged[0] >= 60:
                logged[0] = now
                log(
                    "direct_work_lane_retake_waiting",
                    kind=self.kind,
                    seconds=round(now - began),
                    lane=getattr(self._gave_back, "index", None),
                )
            if standing[0] and now - began >= RETAKE_PRIORITY_SECONDS:
                standing[0] = False
                with work._kinds:
                    setattr(work, counter, getattr(work, counter) - 1)
                    work._kinds.notify_all()

        try:
            while not work._take_slots(self.kind):
                waiting()
            try:
                while True:
                    if not self.any_lane and work._turn_waiting_local > 0:
                        # a build re-take stands back while the commit order's head waits for a local lane
                        waiting()
                        time.sleep(work._poll)
                        continue
                    try:
                        held = (
                            work._take_local_lane(like=self._gave_back)
                            if self.any_lane and self._gave_back is not None
                            else work._take_local_lane()
                        )
                    except Exception as failure:  # noqa: BLE001
                        # never on without a lane (the caller cannot fail the op here): logged, tried again
                        log(
                            "direct_work_lane_retake_retry", type=type(failure).__name__
                        )
                        held = None
                    if held is not None:
                        break
                    waiting()
                    time.sleep(work._poll)
            except BaseException:
                work._release_slot(self.kind)
                raise
        finally:
            with work._kinds:
                if standing[0]:
                    setattr(work, counter, getattr(work, counter) - 1)
                if head_local:
                    work._turn_waiting_local -= 1
                work._kinds.notify_all()
        self._held, self._released = held, False
        with work._kinds:
            work._away.discard(threading.get_ident())
        lane = held[2]
        try:
            with work._kinds:
                kind, record = work._live[threading.get_ident()]
                if record is not None:
                    record = {**record, "lane": lane.index, "cpuset": lane.cpuset}
                work._live[threading.get_ident()] = (kind, record)
                work._write_oldest()
        except Exception as failure:  # noqa: BLE001
            # the lane is held: the record keeps naming this round (busy), without its lane, until the round ends
            log("direct_work_lane_record_failed", type=type(failure).__name__)
        log(
            "direct_work_lane_retaken",
            kind=self.kind,
            lane=lane.index,
            waited_s=round(time.monotonic() - began, 1),
        )
        return lane


def _round(work, kind, has_work=None, since=None):
    """One work round: `_WorkLock.taking` when ``work`` is one, else ``work`` itself (any lock, as before)."""
    taking = getattr(work, "taking", None)
    if taking is None:
        return work
    if since is None:
        return taking(kind, has_work=has_work)
    return taking(kind, has_work=has_work, since=since)


#: OPERATIONAL, not science: how long an advance loop with nothing to start waits before its next round (it takes
#: a lane for each round).
ADVANCE_IDLE_S = 5
#: How long a round re-taking a lane (`_Taking.retake`) keeps priority over NEW rounds before it waits like them.
RETAKE_PRIORITY_SECONDS = 300


#: Restart speed (case-procs + V2, 18 Nov 2026): the build rounds wait at most this long at start for the grader's
#: start-up filing of stranded challengers (`AutoGrader._stranded_filed`), so no build takes the owners it needs first
#: (live 17:19Z restart: builds took them and the filing landed only at +336 s, holding every grade).
STARTUP_PRELUDE_WAIT_SECONDS = 60


def _advance_loop(intake, stop, work=None, since=None, idle_s=1, ready=None):
    from carbon.development_session.research_carrier import Detached

    work = work or _WorkLock(stop=stop)
    failures = 0
    if ready is not None:
        deadline = time.monotonic() + STARTUP_PRELUDE_WAIT_SECONDS
        while not stop.is_set() and time.monotonic() < deadline:
            try:
                if ready():
                    break
            except Exception:  # noqa: BLE001 - doubt: the builds go on
                break
            stop.wait(1)
    while not stop.is_set():
        wait = 1
        try:
            with _round(work, "advance", since=since):
                moved = intake.advance()
            failures = 0
            if not moved:
                wait = idle_s  # nothing queued: N parallel build rounds take no lane every second
        except WorkDeclined:
            pass  # stopping, draining, or the host lock is another door's: never a failure
        except Detached:
            # the receiver is stopping and this round's remote build runs on, for the next start: never a failure
            break
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


def grade_rounds(lanes):
    """How many grade threads a door with ``lanes`` lanes runs. A parallel door (more than one lane) runs TWO per lane:
    a grade waiting its commit turn gives its lane and round slot back (`grade_lanes.given_back`) but its thread waits
    there, so with one thread per lane a slow grade at the head of the commit order left every lane free and nothing
    started (live 116, 18 Nov 2026 00:12-00:26Z: 10 grades reserved, 2 running, 8 waiting behind a ~12-min head pair;
    Lead). The extra threads start a grade only on a free round slot (still one per lane), so at most one grade RUNS
    per lane, and only the commits stay in claim order. A single-lane door keeps its one.
    """
    return 2 * lanes if lanes > 1 else 1


#: S7 I3 (audit row 125): a grade round of a door whose grades take remote lanes only gives its round up when no remote
#: lane is free (`no_grade_lane`, so a build never waits behind it); the loop looks again after this long, not after
#: the 5 s idle wait (an operational bound, not a scientific value).
NO_GRADE_LANE_RECHECK_S = 1


def _grade_loop(grader, stop, work):
    failures = 0
    while not stop.is_set():
        graded = None
        wait = 5
        try:
            # Only a door with something to grade takes the host lock (MAINNET_UPDATE_ARCHITECTURE s2.4 Step A).
            with _round(
                work,
                "grade",
                getattr(grader, "has_work", None),
                getattr(grader, "oldest_pending_ns", None),
            ):
                graded = grader.run_once()
            failures = 0
        except WorkDeclined as declined:
            # stopping, draining, nothing to grade, or waiting on the host: never a failure
            if declined.reason == "no_grade_lane":
                wait = NO_GRADE_LANE_RECHECK_S
        except Exception as failure:  # noqa: BLE001 - no private content in log
            failures += 1
            wait = max(5, _backoff_s(failures))
            log(
                "direct_grade_failure",
                type=type(failure).__name__,
                # a typed refusal's closed code (e.g. an Unavailable's), never free text: names the cause in the journal
                code=_closed_code(failure),
                consecutive=failures,
                retry_s=wait,
                site=_keep_failure(grader, "grade", failure),
            )
        if graded is not None:
            log("direct_grade", state=graded[1])
            wait = 2
        stop.wait(wait)
