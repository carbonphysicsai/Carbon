"""Graphite phase 4: the pre-live gate. Every real code path, no spend.

    python -m carbon.agent_campaign.graphite.phase4 prelive --root DIR \
        --challenge TOKEN [--grant PATH]

Phase-3 session 3 failed on a defect no dry run could see: a scripted backend
stood where the real code runs, so the real code's threading never ran. This
gate runs the real code of a live phase-4 run up to the network boundary,
under the threading the live run uses, and puts a fake only *at* that
boundary, where it answers the way the real service does. Nothing behind the
boundary is synthetic:

- **grant and code (L1)**: `phase4.live_checks`, the live run's own checks,
  for the Challenge `--challenge` names: the grant file is the phase-4 grant
  registered for that Challenge (`phase4.PHASE4_GRANTS`), equal to its
  committed blob on main at a pushed HEAD with the grants directory clean,
  and HEAD is pushed with its shipped code clean; a copy with its ceiling
  raised is refused, and so is a copy naming each other Challenge's grant;
- **the session**: `phase4.live_provider` and `phase4.run_live`, exactly as
  `phase4 run` builds and drives them: the real `AttackerProvider` and
  campaign controller, the real research ledger and loop (`asyncio.run` on
  the main thread, each model call in `asyncio.to_thread`), the real model
  client (`model.LiveModel` -> `model_provider.SelectionTransport` on the
  `engy-chat` adapter, its key read from a file and its request posted from
  its own worker thread) with a fake HTTP opener that answers in Engy's Chat
  Completions shape (charging nothing), and the real miner-path translation
  (`miner_path.MinerPathTools`) over a fake miner door;
- **Carbon's side**: the real analysis, verify, report, B2 and the
  attack-knowledge store (its hash-chained journal), the session's pin and
  the replay guard, and the controller's findings; a resume reuses the pin
  and a view under another digest is refused;
- **the pod and compute store path**: `pods.RunPodPods` over the real
  `operator_compute` layer (its sqlite `ComputeStore`) with a fake RunPod
  transport and fake pod HTTP, built on the main thread and driven the way
  phase 3 drives it (`Phase3Tools.call` -> `asyncio.to_thread`), and once on
  the creating thread as a control. A phase-4 live run launches no pod
  (`NoVerifyPods`, the declared seam `POD_REBUILD_SEAM`), but the step
  (`POD_STEP`) still blocks the gate: it goes green only when the pod store
  is thread-safe. When the pod layer provides its own real-path check
  (`pods.real_path_check`, claude/fix-pod-store-threads) the gate calls it
  instead of its own minimal one.

Two guards run for the whole gate: a network guard (any socket connect or
name lookup is refused and recorded) and a sqlite thread guard (every sqlite
connection records the thread that made it and any use from another thread,
even one a caller catches; `check_same_thread` cannot be switched off). A
check fails loudly on either, and on any exception, with its type.

It writes only under `DIR/attacker-prelive`, sends nothing, spends nothing,
and prints one JSON report. Every failed path is listed under
`blocking_findings` (with whether a phase-4 live run itself uses it) and
fails the gate: exit 0 only when every path passed with no network use, 4
otherwise. `phase4_live_path` reports the phase-4 paths alone. The report's
`attacker_model` block is the session's model selection as its record froze
it: input window, admission ceiling, timeout and reservation per call against
the run's token allowance (GRAPHITE-D35). The report is a live run's release
evidence (OWNER-GRAPHITE-TEST-WAVE-05 §3), so it also names the Challenge the
gate ran for and, under `grant`, the grant it accepted: its id, file and
canonical digest and the Challenge it is bound to (null when the grant was
refused). Not security acceptance.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import io
import json
import os
import shutil
import socket
import sqlite3
import threading
import time
import traceback
import urllib.parse
from decimal import Decimal
from pathlib import Path

from carbon.development_session.research_tools import PREFIX

#: v2 adds `challenge` and `grant` (the accepted grant's id, file, digest and
#: bound Challenge), since the report is release evidence
#: (OWNER-GRAPHITE-TEST-WAVE-05 §3), and `attacker_model` (GRAPHITE-D35, #605),
#: which v1 reports carried unversioned. One version covers both additions.
SCHEMA = "carbon.graphite.phase4-prelive.v2"
#: The pod and compute-store step under phase 3's threading: a blocking gate
#: failure until the pod store is thread-safe (claude/fix-pod-store-threads).
POD_STEP = "pods_compute_store_phase3_threading"
STORE_DIRNAME = "attacker-prelive"
#: What the fake model key file holds: never a credential.
FAKE_KEY = "prelive-fake-key-not-a-credential"


# -- guards -------------------------------------------------------------------------------------
class NetworkUseRefused(RuntimeError):
    """A socket connect or name lookup inside a network guard."""


@contextlib.contextmanager
def network_guard():
    """Refuse and record every IPv4/IPv6 socket connect, `create_connection`
    and name lookup while inside; yields the list of attempts. A caller that
    swallows the error is still recorded."""
    attempts = []
    real = {
        "connect": socket.socket.connect,
        "connect_ex": socket.socket.connect_ex,
        "create_connection": socket.create_connection,
        "getaddrinfo": socket.getaddrinfo,
    }

    def refuse(what, detail):
        attempts.append({"call": what, "target": str(detail)[:120]})
        raise NetworkUseRefused("network use refused: " + what)

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            refuse("connect", address)
        return real["connect"](self, address)

    def connect_ex(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            refuse("connect_ex", address)
        return real["connect_ex"](self, address)

    def create_connection(address, *args, **kwargs):
        refuse("create_connection", address)

    def getaddrinfo(host, *args, **kwargs):
        refuse("getaddrinfo", host)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.create_connection = create_connection
    socket.getaddrinfo = getaddrinfo
    try:
        yield attempts
    finally:
        socket.socket.connect = real["connect"]
        socket.socket.connect_ex = real["connect_ex"]
        socket.create_connection = real["create_connection"]
        socket.getaddrinfo = real["getaddrinfo"]


class _Uses:
    """What a sqlite thread guard saw: cross-thread uses and thread errors."""

    def __init__(self):
        self.lock = threading.Lock()
        self.cross_thread = []
        self.thread_errors = []

    def mark(self):
        with self.lock:
            return len(self.cross_thread), len(self.thread_errors)

    def since(self, mark):
        with self.lock:
            return self.cross_thread[mark[0] :], self.thread_errors[mark[1] :]


def _guarded_connection(uses):
    class GuardedConnection(sqlite3.Connection):
        """A connection that records the thread that made it, and any use
        from another one before sqlite refuses it."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._owner = threading.get_ident()
            self._owner_name = threading.current_thread().name
            self._database = str(args[0] if args else kwargs.get("database"))

        def _check(self, operation):
            if threading.get_ident() != self._owner:
                with uses.lock:
                    uses.cross_thread.append(
                        {
                            "operation": operation,
                            "database": Path(self._database).name,
                            "opened_on": self._owner_name,
                            "used_on": threading.current_thread().name,
                        }
                    )

        def cursor(self, *args, **kwargs):
            self._check("cursor")
            return super().cursor(*args, **kwargs)

        def execute(self, *args, **kwargs):
            self._check("execute")
            return super().execute(*args, **kwargs)

        def executemany(self, *args, **kwargs):
            self._check("executemany")
            return super().executemany(*args, **kwargs)

        def executescript(self, *args, **kwargs):
            self._check("executescript")
            return super().executescript(*args, **kwargs)

        def commit(self):
            self._check("commit")
            return super().commit()

        def rollback(self):
            self._check("rollback")
            return super().rollback()

    return GuardedConnection


@contextlib.contextmanager
def sqlite_thread_guard():
    """Every `sqlite3.connect` inside makes a connection that records a use
    from a thread other than the one that opened it, and keeps sqlite's own
    same-thread check on (`check_same_thread=True`, whatever the caller
    passed). Uncaught exceptions in other threads are recorded too. Yields
    the record (`_Uses`)."""
    uses = _Uses()
    real_connect, real_hook = sqlite3.connect, threading.excepthook
    factory = _guarded_connection(uses)

    def connect(*args, **kwargs):
        if len(args) > 4:
            args = (*args[:4], True, *args[5:])
        else:
            kwargs["check_same_thread"] = True
        kwargs["factory"] = factory
        return real_connect(*args, **kwargs)

    def hook(info):
        with uses.lock:
            uses.thread_errors.append(
                {
                    "thread": getattr(info.thread, "name", None),
                    "error": info.exc_type.__name__,
                    "message": str(info.exc_value)[:300],
                }
            )
        real_hook(info)

    sqlite3.connect, threading.excepthook = connect, hook
    try:
        yield uses
    finally:
        sqlite3.connect, threading.excepthook = real_connect, real_hook


# -- the fake model service (Engy's Chat Completions shape) -------------------------------------
class _Response:
    def __init__(self, status, body):
        self.status, self._body = status, body

    def read(self, limit=-1):
        return self._body if limit < 0 else self._body[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeEngy:
    """An opener for `model_provider.SelectionTransport`: it answers each
    POST in Engy's Chat Completions shape (`choices[0].message`, `usage`,
    `x_engy.charged_micro`), charging nothing. `script` is one reply per
    request: a list of `(tool, arguments)` calls, or a final text. It checks
    what the real service would see: a POST to the selection's endpoint, a
    bearer key header and a well-formed body offering every tool it calls."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.threads = set()
        self.problems = []

    def open(self, request, timeout=None):
        self.threads.add(threading.current_thread().name)
        index = len(self.requests)
        try:
            body = json.loads(request.data)
        except (TypeError, ValueError):
            body = None
        auth = request.get_header("Authorization") or ""
        self.requests.append(
            {
                "method": request.get_method(),
                "url": request.full_url,
                "bearer_key_sent": auth.startswith("Bearer ") and len(auth) > 7,
                "body_bytes": len(request.data or b""),
            }
        )
        if request.get_method() != "POST" or type(body) is not dict:
            self.problems.append(f"request {index} is not a JSON POST")
            return _Response(400, b'{"error":{"code":"invalid_request"}}')
        if index >= len(self.script):
            self.problems.append(f"request {index} is past the script")
            return _Response(400, b'{"error":{"code":"script_exhausted"}}')
        offered = {
            tool.get("function", {}).get("name")
            for tool in body.get("tools") or ()
            if type(tool) is dict
        }
        step = self.script[index]
        message = {"role": "assistant", "content": None}
        finish = "stop"
        if type(step) is str:
            message["content"] = step
        else:
            calls = []
            for number, (name, arguments) in enumerate(step):
                if name not in offered:
                    self.problems.append(f"request {index} does not offer {name}")
                calls.append(
                    {
                        "id": f"call_prelive_{index:03d}_{number}",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(arguments, sort_keys=True),
                        },
                    }
                )
            message["tool_calls"] = calls
            finish = "tool_calls"
        reply = {
            "id": f"chatcmpl-prelive-{index:03d}",
            "object": "chat.completion",
            "model": body.get("model"),
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {
                "prompt_tokens": max(1, len(request.data) // 4),
                "completion_tokens": 24,
                "prompt_tokens_details": {"cached_tokens": 0},
                "completion_tokens_details": {"reasoning_tokens": 0},
            },
            "x_engy": {
                "charged_micro": 0,
                "request_id": f"prelive-{index:03d}",
                "miner": None,
                "worker": None,
            },
        }
        return _Response(200, json.dumps(reply).encode())


# -- the fake miner door ------------------------------------------------------------------------
class FakeMinerDoor:
    """Stands where `carbon.miner_mcp.standard.ResearchToolAdapter` stands
    (the miner's own door, which needs the operator's miner profile, signer
    and campaign lock): it answers each request in the path's envelope.
    `MinerPathTools`, which translates the loop's calls into its requests,
    is real."""

    def __init__(self):
        self.requests = []

    async def call(self, request):
        from carbon.miner_mcp.standard import ResearchToolResult

        self.requests.append((request.operation, request.operation_id))
        result = {"accepted": True}
        if request.operation == "dry_validate":
            result = {"valid": False, "issues": [["backbone.not_admitted", "backbone"]]}
        elif request.operation == "start_research_task":
            result = {"task_id": "prelive-task-1", "state": "QUEUED"}
        payload = {
            "protocol": "carbon_research_v2",
            "operation": request.operation,
            "reply": {"status": "OK", "result": result},
            "terminal_task": None,
            "public_result": None,
            "requires_reconciliation": False,
        }
        return ResearchToolResult(
            request.operation, request.operation_id, payload, False
        )


def fake_attach(door):
    from .miner_path import MinerPathTools

    @contextlib.asynccontextmanager
    async def attach(*, session):
        yield MinerPathTools(door, session=session)

    return attach


def session_script(adapter):
    """The fake model's replies for one Attacker session: read the
    Challenge, validate a recipe the contract refuses, ask for a code run
    with no wall allowance (refused before dispatch) and one within it
    (dispatched), two calls in one turn (the parallel-call rule), then
    stop."""
    from . import phase4

    outside = phase4.surface_value(adapter, "recipe_outside_contract")
    seconds = phase4.adapter_code_run_seconds(adapter)

    def code_run(inner):
        return {
            "kind": "workspace",
            "strategy_json": None,
            "action": "run_python",
            "arguments_json": json.dumps(inner),
            "hypothesis": "the code-run rule",
            "expected_effect": "refused without an allowance; dispatched within it",
        }

    return [
        [(PREFIX + "get_challenge_info", {})],
        [(PREFIX + "dry_validate", {"strategy_json": json.dumps(outside)})],
        [
            (
                PREFIX + "start_research_task",
                code_run({"source": "print(1)", "files": []}),
            )
        ],
        [
            (
                PREFIX + "start_research_task",
                code_run({"source": "print(1)", "files": [], "seconds": seconds}),
            )
        ],
        [
            (PREFIX + "get_interaction_manifest", {}),
            (PREFIX + "get_research_result", {"task_id": "prelive-task-1"}),
        ],
        "PRELIVE: the scripted Attacker stops here.",
    ]


# -- the fake RunPod service --------------------------------------------------------------------
class FakeRunPod:
    """A `RunPodTransport` answering the REST v1 and GraphQL shapes the
    operator layer sends (`operator_compute.runpod`): a balance, an A40
    Secure price under the ceiling, a pod create, its status until it is
    deleted, and a zero charge. Nothing is created and nothing is spent."""

    def __init__(self):
        self.calls = []
        self.pods = {}
        self.threads = set()

    def __call__(self, method, url, *, body, headers, timeout):
        self.threads.add(threading.current_thread().name)
        self.calls.append((method, url.split("?")[0]))
        payload = json.loads(body) if body else None
        if url.endswith("/graphql"):
            query = payload["query"]
            if "clientBalance" in query:
                return (
                    200,
                    json.dumps({"data": {"myself": {"clientBalance": 100.0}}}).encode(),
                )
            return (
                200,
                json.dumps(
                    {
                        "data": {
                            "gpuTypes": [
                                {
                                    "lowestPrice": {
                                        "uninterruptablePrice": 0.44,
                                        "stockStatus": "High",
                                    }
                                }
                            ]
                        }
                    }
                ).encode(),
            )
        if method == "POST" and url.endswith("/v1/pods"):
            pod_id = "prelive" + hashlib.sha256(body).hexdigest()[:10]
            self.pods[pod_id] = {"id": pod_id, "name": payload["name"]}
            return 200, json.dumps({**self.pods[pod_id], "costPerHr": 0.44}).encode()
        if "/billing/pods" in url:
            pod_id = url.split("podId=")[1].split("&")[0]
            return 200, json.dumps([{"podId": pod_id, "amount": 0.0}]).encode()
        if method == "GET" and url.endswith("/v1/pods"):
            return 200, json.dumps(list(self.pods.values())).encode()
        pod_id = url.rsplit("/", 1)[1]
        if method == "DELETE":
            self.pods.pop(pod_id, None)
            return 200, b"{}"
        if pod_id not in self.pods:
            return 404, b""
        return (
            200,
            json.dumps(
                {
                    **self.pods[pod_id],
                    "desiredStatus": "RUNNING",
                    "runtime": {"uptimeInSeconds": 1},
                    "costPerHr": 0.44,
                }
            ).encode(),
        )


def fake_pod_http():
    """The pod's own HTTP (`pods._https_get`): status `done` and one
    exported file, served by token."""
    done = b'{"exit": 0, "prelive": true}'
    listing = [
        {
            "path": "DONE.json",
            "size": len(done),
            "sha256": hashlib.sha256(done).hexdigest(),
        }
    ]

    def get(url, token, timeout):
        if not token:
            return 403, b""
        if url.endswith("/status"):
            return 200, b'{"stage": "done"}'
        if url.endswith("/files"):
            return 200, json.dumps(listing).encode()
        if url.endswith("/file/DONE.json"):
            return 200, done
        return 404, b""

    return get


def pod_job():
    from .pods import PodJob

    return PodJob(
        intent_id="prelive-pod-intent-0001",
        strategy={"prelive": True},
        contract_digest="sha256:" + "0" * 64,
        seed=0,
        expected={},
        minutes=30,
        seconds=600,
    )


def pod_lifecycle(pods, private):
    """One pod's whole lifecycle on the backend (launch, wait, fetch,
    terminate, charge), as the phase-3 experiment drives it for one
    proposal."""
    handle = pods.launch(pod_job(), private)
    state = pods.wait(handle, deadline=time.time() + 120, cancelled=lambda: False)
    files = pods.fetch(handle)
    terminated = pods.terminate(handle)
    charge = pods.charge(handle)
    return {
        "state": state,
        "files": sorted(files),
        "terminated": terminated,
        "charge_usd": None if charge is None else str(charge),
    }


# -- the gate -----------------------------------------------------------------------------------
class _Gate:
    def __init__(self, uses):
        self.uses = uses
        self.paths = []

    def check(self, name, exercised, call, *, phase4=True):
        """Run one path; record PASS with its detail, or FAIL with the
        exception's type, a typed refusal's code, and any cross-thread
        sqlite use or thread error seen while it ran."""
        mark = self.uses.mark()
        out = io.StringIO()
        status, detail = "PASS", None
        try:
            with contextlib.redirect_stdout(out):
                detail = call()
        except KeyboardInterrupt:
            raise
        except BaseException as error:  # noqa: BLE001 - every failure is reported
            status = "FAIL"
            detail = {
                "error": type(error).__name__,
                "message": str(error)[:500],
                "refusal": _refusal_code(out.getvalue()),
                "where": _where(error),
            }
        cross, thread_errors = self.uses.since(mark)
        if cross or thread_errors:
            status = "FAIL"
            detail = {
                **(detail if isinstance(detail, dict) else {"detail": detail}),
                "sqlite_cross_thread_uses": cross[:10],
                "thread_errors": thread_errors[:10],
            }
        self.paths.append(
            {
                "path": name,
                "status": status,
                "phase4_live_path": phase4,
                "exercised": list(exercised),
                "detail": detail,
                "stdout_lines": len(out.getvalue().splitlines()),
            }
        )
        return status == "PASS", detail


def _refusal_code(printed):
    for line in reversed(printed.strip().splitlines()):
        with contextlib.suppress(ValueError, TypeError, AttributeError):
            record = json.loads(line)
            if record.get("status") == "REFUSED":
                return record.get("reason_code")
    return None


def _where(error):
    frames = traceback.extract_tb(error.__traceback__)
    return [f"{Path(f.filename).name}:{f.lineno}:{f.name}" for f in frames[-4:]]


def _path_of(url):
    """A provider call as its path and query, without naming the host."""
    parts = urllib.parse.urlsplit(url)
    return parts.path + ("?" + parts.query if parts.query else "")


def _fresh(root):
    Path(root).mkdir(parents=True, exist_ok=True, mode=0o700)
    store = Path(root) / STORE_DIRNAME
    if store.exists():
        shutil.rmtree(store)
    store.mkdir(mode=0o700)
    return store


def _key_file(store, name):
    path = store / name
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(FAKE_KEY)
    return path


def prelive(
    root,
    adapter,
    atk,
    *,
    grant_path,
    challenge,
    repository=None,
    emit=print,
    scoring=None,
):
    """Run the gate (module docstring) under `root`; returns the exit code.
    `challenge` is the Challenge `--challenge` names, whose registered grant
    the grant check binds to. `scoring` is the Challenge's registered
    ChallengeScoring, as `phase4 run` resolves it; None resolves it from the
    adapter's Challenge."""
    from . import phase4

    repository = phase4.REPOSITORY if repository is None else Path(repository)
    store = _fresh(root)
    with network_guard() as network, sqlite_thread_guard() as uses:
        gate = _Gate(uses)
        report = _run(
            gate, store, adapter, atk, grant_path, repository, scoring, challenge
        )
    blocking = [
        {
            "path": row["path"],
            "detail": row["detail"],
            "blocks_phase4_live_run": row["phase4_live_path"],
            "blocks": (
                "the first live phase-4 run"
                if row["phase4_live_path"]
                else "any run that launches pods through RunPodPods (phase 3; the "
                "phase-4 verify-pod rebuild seam once wired)"
            ),
        }
        for row in gate.paths
        if row["status"] != "PASS"
    ]
    phase4_ok = all(
        row["status"] == "PASS" for row in gate.paths if row["phase4_live_path"]
    )
    # Every failed path is a blocking gate failure, the pod step included:
    # the gate goes green only when every path passes. `phase4_live_path`
    # says separately whether the paths a phase-4 live run itself uses passed.
    out = {
        "schema": SCHEMA,
        "root": str(store),
        "challenge": challenge,
        "grant": report.get("grant"),
        "verdict": "PASS" if not blocking and not network else "FAIL",
        "phase4_live_path": "PASS" if phase4_ok else "FAIL",
        "paths": gate.paths,
        "blocking_findings": blocking,
        "network_attempts": list(network),
        "spent_usd": report.get("spent_usd"),
        # The Attacker's input window, admission ceiling, timeout and
        # reservation per call, from the session record (GRAPHITE-D35).
        "attacker_model": report.get("attacker_model"),
        "claims": {"security_acceptance": False, "live_run": False, "spend": False},
    }
    emit(json.dumps(out, indent=1, sort_keys=True, default=str))
    return 0 if out["verdict"] == "PASS" else 4


def _refused_copy(phase4, store, name, document, repository, challenge):
    """The refusal code `check_committed_grant` gives a copy of the grant
    with `document`'s fields, or None when it accepts it."""
    copy = store / name
    copy.write_text(json.dumps(document))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            phase4.check_committed_grant(copy, repository, challenge=challenge)
        except SystemExit:
            return _refusal_code(out.getvalue())
    return None


def _run(gate, store, adapter, atk, grant_path, repository, scoring, challenge):
    from . import phase4
    from .pods import RunPodPods, private_dir

    state = {}

    def grant_and_code():
        grant, head = phase4.live_checks(grant_path, repository, challenge=challenge)
        state["grant"], state["head"] = grant, head
        entry = phase4.phase4_grant(challenge)
        document = json.loads(Path(grant_path).read_bytes())
        tampered = _refused_copy(
            phase4,
            store,
            "grant-ceiling-raised.json",
            {**document, "monetary_ceiling": "100.00"},
            repository,
            challenge,
        )
        if tampered != "grant_differs_from_the_committed_phase4_grant":
            raise AssertionError("a copy with its ceiling raised was not refused")
        # A copy naming each other Challenge's grant is refused for this one.
        others = {}
        for other in phase4.PHASE4_GRANTS.values():
            if other.challenge == challenge:
                continue
            others[other.grant_id] = _refused_copy(
                phase4,
                store,
                "grant-named-" + other.grant_id + ".json",
                {**document, "grant_id": other.grant_id},
                repository,
                challenge,
            )
            if others[other.grant_id] != "grant_is_for_another_challenge":
                raise AssertionError(
                    "a copy naming " + other.grant_id + " was not refused"
                )
        state["evidence"] = {
            "challenge": entry.challenge,
            "grant_id": entry.grant_id,
            "grant_file": entry.grant_file,
            "grant_digest": phase4.grant_digest(document),
        }
        return {
            **state["evidence"],
            "head": head,
            "tampered_copy": tampered,
            "other_challenges_grants": others,
        }

    gate.check(
        "grant_and_code_checks",
        (
            (
                "phase4.live_checks: load_grant and the provider, for the "
                "Challenge --challenge names"
            ),
            (
                "phase4.check_committed_grant: the grant registered for the "
                "Challenge, git show HEAD blob, HEAD on a remote branch, the "
                "blob on main, grants directory clean (L1)"
            ),
            "phase3.check_code_ref: HEAD pushed, shipped code clean",
            "negative: a copy with its ceiling raised is refused",
            "negative: a copy naming another Challenge's grant is refused",
        ),
        grant_and_code,
    )
    if "grant" not in state or "evidence" not in state:
        return {"spent_usd": "0", "grant": None}

    engy = FakeEngy(session_script(adapter))
    door = FakeMinerDoor()

    def session():
        key = _key_file(store, "fake-engy-key")
        model = phase4.live_model(state["grant"], str(key), opener=engy)
        provider = phase4.live_provider(
            store,
            grant=state["grant"],
            model=model,
            adapter=adapter,
            miner_attach=fake_attach(door),
            scoring=scoring,
        )
        state["provider"] = provider
        if type(provider.pods) is not phase4.NoVerifyPods:
            raise AssertionError("the live provider's pod backend is not NoVerifyPods")
        entry, coverage = phase4.run_live(
            store,
            state["grant"],
            provider,
            adapter,
            atk,
            session=1,
            head=state["head"],
            signals=False,
        )
        state["entry"], state["coverage"] = entry, coverage
        if entry["provider_state"] != "succeeded":
            raise AssertionError(
                "the session ended "
                + str(entry["provider_state"])
                + ": "
                + json.dumps(entry["failure"], default=str)
            )
        if engy.problems:
            raise AssertionError("; ".join(engy.problems))
        run_id = entry["run_id"]
        usage = provider.usage(run_id)
        calls = provider._calls(run_id)
        if usage.settled != 0 or usage.pending != 0:
            raise AssertionError("the session settled or reserved money")
        if any(call["settlement"] is None for call in calls):
            raise AssertionError("a model call kept its reservation")
        if not all(row["bearer_key_sent"] for row in engy.requests):
            raise AssertionError("a model request carried no key header")
        if threading.main_thread().name in engy.threads:
            raise AssertionError("a model request ran on the main thread")
        # The selection the session record froze (GRAPHITE-D35).
        state["attacker_model"] = phase4.attacker_model(provider, run_id)
        return {
            "provider_state": entry["provider_state"],
            "model_requests": len(engy.requests),
            "model_endpoint": sorted({row["url"] for row in engy.requests}),
            "model_request_threads": sorted(engy.threads),
            "model_calls_settled": len(calls),
            "settled_usd": str(usage.settled),
            "pending_usd": str(usage.pending),
            "code_runs_dispatched": entry["code_runs"],
            "miner_door_requests": [op for op, _ in door.requests],
            "pod_backend": provider.pods.describe(),
        }

    gate.check(
        "session_model_ledger_controller",
        (
            "phase4.live_provider + run_live (as `phase4 run` drives them)",
            "AttackerProvider and the campaign controller (CampaignController)",
            "research_loop.run_epoch in asyncio.run on the main thread",
            (
                "model calls in asyncio.to_thread, posted from model_provider's "
                "own worker thread"
            ),
            (
                "model.LiveModel -> model_provider.SelectionTransport (engy-chat): "
                "chat_request, read_credential, _post, chat_response, "
                "provider_report"
            ),
            "the research ledger's reservation and settlement (CampaignLedger)",
            "AttackerTools' code-run rule (the adapter's own)",
            "miner_path.MinerPathTools over a fake miner door",
            "fake at the boundary: Engy Chat Completions over a fake opener",
        ),
        session,
    )

    def carbon_side():
        if "entry" not in state:
            raise AssertionError("no session to read")
        coverage, entry = state["coverage"], state["entry"]
        kstore = phase4.open_store(store, atk)
        kstore._entries()  # reads and checks the hash-chained journal
        view = phase4.pin_session(store, 1, kstore, resume=True)
        if view.digest != entry["store_pinned"]:
            raise AssertionError("a resume did not reuse the session's pin")
        phase4.replay_guard(store, 1, view, atk)
        other = kstore.pin(kstore.snapshot())
        out = io.StringIO()
        refused = None
        if other.digest != view.digest:
            with contextlib.redirect_stdout(out):
                try:
                    phase4.replay_guard(store, 1, other, atk)
                except SystemExit:
                    refused = _refusal_code(out.getvalue())
            if refused != "attack_knowledge_replay_under_another_digest":
                raise AssertionError("a view under another digest was not refused")
        control = phase4.controller_for(store, state["provider"], state["grant"])
        try:
            recorded = [f["id"] for f in control.admission_ledgers()["findings"]]
        finally:
            control.close()
        if sorted(recorded) != sorted(entry["findings"]):
            raise AssertionError("the controller's findings are not the session's")
        return {
            "attempts": coverage["attempts"],
            "verdicts": sorted({v["outcome"] for v in coverage["verdicts"]}),
            "findings": len(entry["findings"]),
            "findings_by_source": {
                k: len(v) for k, v in coverage["findings_by_source"].items()
            },
            "store_pinned": entry["store_pinned"],
            "store_after": entry["store_after"],
            "journal_entries": len(kstore._entries()),
            "replay_under_another_digest": refused or "no_other_digest_yet",
            "checks_named": len(coverage["checks"]["checks"]),
        }

    gate.check(
        "carbon_side_store_pin_replay",
        (
            "attack.analysis.attempts and map_to_families on the session journal",
            "attack.verify on every attempt with the adapter's rebuild and oracle",
            "attack.report and benchmark B2 against the adapter's deterministic runs",
            "attack.knowledge.AttackStore: hash-chained journal read, snapshot, pin",
            (
                "phase4.pin_session resume (reuses the pin), replay_guard, and a "
                "view under another digest refused"
            ),
            "controller.record_finding for every finding",
        ),
        carbon_side,
    )

    def pods_on(threaded):
        name = "threaded" if threaded else "same-thread"
        root = store / ("pods-" + name)
        key = _key_file(store, "fake-runpod-key-" + name)
        transport = FakeRunPod()
        pods = RunPodPods(
            root=root,
            key_file=str(key),
            code_ref=state["head"],
            repository=repository,
            transport=transport,
            http=fake_pod_http(),
            sleep=lambda seconds: None,
            balance_floor=lambda: Decimal(0),
            scoring=scoring,
        )
        private = private_dir(root / "job")
        try:
            if threaded:

                async def drive():
                    # Phase3Tools.call: `await asyncio.to_thread(...)`.
                    return await asyncio.to_thread(pod_lifecycle, pods, private)

                result = asyncio.run(drive())
            else:
                result = pod_lifecycle(pods, private)
        finally:
            pods.store.close()
        if not result["terminated"] or result["state"] != "done":
            raise AssertionError("the pod lifecycle did not finish: " + str(result))
        return {
            **result,
            "runpod_calls": [f"{m} {_path_of(u)}" for m, u in transport.calls],
            "runpod_threads": sorted(transport.threads),
        }

    exercised = (
        "pods.RunPodPods (launch, wait, fetch, terminate, charge)",
        "operator_compute.ComputeService, RunPodAdapter and the sqlite ComputeStore",
        "fake at the boundary: RunPod REST v1 / GraphQL and the pod's HTTP",
    )
    gate.check(
        "pods_compute_store_creating_thread",
        (*exercised, "control: driven on the thread that built the store"),
        lambda: pods_on(False),
        phase4=False,
    )
    from . import pods as pods_module

    shared = getattr(pods_module, "real_path_check", None)
    if callable(shared):
        # The pod layer's own real-path check (claude/fix-pod-store-threads):
        # RunPodPods.launch through asyncio.to_thread with a fake RunPod
        # transport. Called with its private root only; its report is ours.
        def threaded():
            return shared(root=store / "pods-shared-check", scoring=scoring)

        how = "pods.real_path_check (the pod layer's shared real-path check)"
    else:
        # Until that check exists: this gate's own minimal one.
        def threaded():
            return pods_on(True)

        how = "this gate's own minimal check (pods.real_path_check not present)"
    gate.check(
        POD_STEP,
        (
            *exercised,
            (
                "built on the main thread, driven through asyncio.to_thread as "
                "Phase3Tools.call drives experiment.propose_tool"
            ),
            how,
        ),
        threaded,
        phase4=False,
    )
    entry = state.get("entry") or {}
    return {
        "spent_usd": entry.get("settled_usd"),
        "attacker_model": state.get("attacker_model"),
        "grant": state["evidence"],
    }
