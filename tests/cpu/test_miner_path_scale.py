"""LOCK PROGRAM (2) (owner via the Lead, 19 Nov 2026; TEAM_RULES #12): the miner paths at live volume.

Live 116, 19 Nov 2026 14:50Z: no construction-submit completed for over an hour while status, feedback and uploads still
arrived; a miner found it before we did. This harness runs the REAL signed door (`DirectRecipeIntake.handle`: the
per-peer limits and in-flight cap, the authenticated gateway with the real receipt journal, the door's write lock, the
real `LeanRecipeAdapter.evaluate` and source staging, the real `AttemptLedger`) with REAL per-owner construction
providers (`DirectDevelopmentTasksV3`, each on its own durable root), at live volume:

- >= 400 owners in the metagraph, most LAZY after a start: an owner's provider is built at its first touch, and that
  first touch pays the live restore cost (`LAZY_OPEN_SECONDS`, scaled: live 3.4-9.5 s at 1/100);
- 100 concurrent clients mixing construction submits, source upload chunks, status and feedback;
- grading at the same time: grade rounds holding what grades hold on live (the attempt ledger's write transactions,
  the crown lock, owner claims), for scaled live hold times.

Asserted: every request gets an answer; every submit completes under `SUBMIT_BOUND_SECONDS`; no slow step (a lazy
restore, a slow task start) ever runs while the door-wide write lock is held; no request opens an owner it does not
concern (nothing O(all owners) per request). A self-proof case injects a slow task start and shows the harness fails.

Stand-ins, and only these: the signature verifier (`_Verifier`: CPU per request, not a lock), the restore cost (a sleep),
and the grade rounds (their lock holds, not their compute). Synthetic ids and values only; nothing from live state.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import replace

from test_c08_authenticated_miner_mcp import (
    CONTEXT,
    NOW,
    _headers,
    _snapshot,
    _Verifier,
)
from test_direct_v3_durable_tasks import _fixture

from carbon import research
from carbon.battery.intake import PeerLimits, SnapshotWindow
from carbon.chain.models import Participant
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator import AttemptLedger, grade_sequencer
from carbon.challenge_validator.direct_intake import (
    FEEDBACK_TOOL,
    STATUS_TOOL,
    SUBMIT_PATH,
    SUBMIT_TOOL,
    DirectRecipeIntake,
)
from carbon.development_session.research_ledger import CampaignLedger
from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
from carbon.level4 import staging, submission
from carbon.transport.models import message
from carbon.transport.store import ReceiptJournal

OWNERS = 400
CLIENTS = 100
REQUESTS_PER_CLIENT = 6
GRADE_ROUNDS = 8
#: Live: a lazy owner's restore 3.4-9.5 s (19 Nov 2026); scaled 1/100.
LAZY_OPEN_SECONDS = 0.04
#: Live: the miner client's submit timeout is 30 s (`direct_submission.post`). The harness bound is burst-wide, at
#: 1/100 of the live costs plus the real per-request work: a door that restores lazy owners outside its write lock
#: answers the burst's slowest submit well under it; one that serialises ~300 restores (12 s here) does not.
SUBMIT_BOUND_SECONDS = 3.0
#: Scaled live hold times of what a grade holds: an exam-cap settle transaction, a crown decision.
LEDGER_HOLD_SECONDS = 0.02
CROWN_HOLD_SECONDS = 0.05
#: The self-proof's slow task start (a door-wide lock held across it serialises every submit).
SLOW_START_SECONDS = 0.05
#: How soon a client asks again after a typed ``503 capacity`` (the miner client retries it, f099c4fb).
CAPACITY_RETRY_SECONDS = 0.02


class _TimedLock:
    """The door's write lock, with its holder known (to flag a slow step under it) and its longest hold kept."""

    def __init__(self, lock):
        self._lock = lock
        self._holder = None
        self._since = 0.0
        self.longest = 0.0

    def acquire(self, *args, **kwargs):
        got = self._lock.acquire(*args, **kwargs)
        if got:
            self._holder, self._since = threading.get_ident(), time.monotonic()
        return got

    def release(self):
        self.longest = max(self.longest, time.monotonic() - self._since)
        self._holder = None
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()

    def held_by_me(self):
        return self._holder == threading.get_ident()


class _Door:
    """A live-scale door: the real signed intake over real per-owner providers, most of them lazy."""

    def __init__(self, tmp_path, monkeypatch, *, slow_start=False):
        request, factory, discovery = _fixture(
            tmp_path / "direct", monkeypatch, material=bundle_material_v5()
        )
        fixed = factory()
        self.image, self.inference_image = fixed.image, fixed.inference_image
        fixed.close()
        self.request, self.discovery, self.base = request, discovery, tmp_path
        self.owners = [f"5Owner{i:04d}".ljust(48, "x") for i in range(OWNERS)]
        state = _snapshot()
        miners = tuple(
            Participant(i + 1, owner, f"cold{i // 4}", i + 2)
            for i, owner in enumerate(self.owners)
        )
        state = replace(state, participants=(state.participants[0], *miners))
        self.state = state
        window = SnapshotWindow(clock=lambda: NOW / 1_000_000_000)
        window.add(state)
        attempts = tmp_path / "attempts"
        attempts.mkdir(mode=0o700)
        attempts.chmod(0o700)
        self.ledger = AttemptLedger(attempts / "ledger.sqlite3")
        self._providers, self._gates, self._gate = {}, {}, threading.Lock()
        self.opened, self.touched, self.violations = [], set(), []
        self.intake = DirectRecipeIntake(
            context=CONTEXT,
            receiver="validator",
            journal=ReceiptJournal(tmp_path / "transport.sqlite3", CONTEXT),
            verifier=_Verifier(),
            window=window,
            discovery=discovery,
            provider_for=self.provider,
            attempt_ledger=self.ledger,
            clock_ns=lambda: NOW,
        )
        # live: every client arrives through the front with its own peer address; one shared test peer must not be
        # rate-limited as if it were one miner (the in-flight cap stays the real one)
        self.intake.limits = PeerLimits(burst=1_000_000, rate=1_000_000.0)
        self.write = _TimedLock(self.intake._write)
        self.intake._write = self.write
        self._nonce, self._nonce_lock = {}, threading.Lock()
        if slow_start:
            real = DirectDevelopmentTasksV3.start_research_task

            def start(provider, *args, **kwargs):
                self._slow("start_research_task", SLOW_START_SECONDS)
                return real(provider, *args, **kwargs)

            monkeypatch.setattr(DirectDevelopmentTasksV3, "start_research_task", start)

    def _slow(self, step, seconds):
        """A step that takes live time: flagged when the door-wide write lock is held across it."""
        if self.write.held_by_me():
            self.violations.append(step)
        time.sleep(seconds)

    def provider(self, owner):
        """`OwnerProviders` as a start leaves it: an owner's provider is built at its first touch (a lazy owner's
        restore, under that owner's own gate only, paying `LAZY_OPEN_SECONDS`)."""
        if owner not in self.owners:
            return None
        self.touched.add(owner)
        with self._gate:
            gate = self._gates.setdefault(owner, threading.Lock())
        with gate:
            provider = self._providers.get(owner)
            if provider is None:
                self.opened.append(owner)
                self._slow("lazy_restore", LAZY_OPEN_SECONDS)
                root = self.base / "owners" / owner[:12]
                provider = DirectDevelopmentTasksV3(
                    root=root / "tasks",
                    requester=owner,
                    ledger=CampaignLedger(root / "ledger"),
                    owner=owner,
                    discovery=self.discovery,
                    image=self.image,
                    inference_image=self.inference_image,
                )
                self._providers[owner] = provider
            return provider

    def close(self):
        for provider in self._providers.values():
            provider.close()

    def _signed(self, owner, tool, fields):
        with self._nonce_lock:
            nonce = self._nonce[owner] = self._nonce.get(owner, NOW) + 1
        body = message(
            CONTEXT,
            self.state.snapshot_id,
            self.request.challenge_key,
            session="miner-path-scale",
            request=f"{tool}-{owner[:12]}-{nonce}",
            tool=tool,
            fields=fields,
        )
        return body, _headers(body, nonce, hotkey=owner)

    def send(self, owner, tool, fields):
        """One request, asked again after a typed ``503 capacity`` as the miner client does (signed afresh each
        time); the caller times the whole exchange."""
        while True:
            body, headers = self._signed(owner, tool, fields)
            answer = self.intake.handle("POST", SUBMIT_PATH, headers, body, "127.0.0.1")
            refused = answer.body.get("refused") if type(answer.body) is dict else None
            if answer.status != 503 or refused != "capacity":
                return answer
            time.sleep(CAPACITY_RETRY_SECONDS)

    def submit(self, owner):
        return self.send(
            owner,
            SUBMIT_TOOL,
            {
                "strategy_json": json.dumps(self.request.recipe, sort_keys=True),
                "contract_digest": self.intake.adapter.contract_digest,
            },
        )

    def upload(self, owner, index):
        document = json.dumps({"inert": owner[:12], "chunk": index}).encode()
        name = staging.WORKSPACE_PREFIX + submission.name(document)[7:] + ".json"
        source = research.DirectStageSourceRequestV1(
            self.request.challenge_key,
            name,
            0,
            len(document),
            submission.name(document),
            None,
            document,
        )
        call = research.ServiceCall(
            research.RESEARCH_NAMESPACE, "stage_research_source", source
        )
        encoded = base64.b64encode(research.canonical_bytes(call)).decode("ascii")
        return self.send(owner, research.RESEARCH_NAMESPACE, {"call_base64": encoded})

    def status(self, owner):
        return self.send(owner, STATUS_TOOL, {"submission_id": "rtsk_" + "0" * 64})

    def feedback(self, owner):
        return self.send(owner, FEEDBACK_TOOL, {})


def _grade_rounds(door, stop):
    """Grade rounds running beside the miners, holding what live grades hold: a write transaction on the door's attempt
    ledger (an exam-cap settle), the crown lock (a crown decision) and an owner claim.
    """
    import sqlite3

    claims = grade_sequencer.OwnerClaims()

    def round_(index):
        owner = door.owners[-1 - index]
        db = sqlite3.connect(door.ledger.path, timeout=30, isolation_level=None)
        try:
            while not stop.is_set():
                if claims.try_claim(owner):
                    try:
                        db.execute("BEGIN IMMEDIATE")
                        time.sleep(LEDGER_HOLD_SECONDS)
                        db.execute("COMMIT")
                        with grade_sequencer.CROWN_LOCK:
                            time.sleep(CROWN_HOLD_SECONDS)
                    finally:
                        claims.release(owner)
                stop.wait(0.01)
        finally:
            db.close()

    threads = [
        threading.Thread(target=round_, args=(i,), daemon=True)
        for i in range(GRADE_ROUNDS)
    ]
    for thread in threads:
        thread.start()
    return threads


def _burst(door):
    """100 clients at once, each a mix of submits, upload chunks, status and feedback for its own owners; returns
    ``{kind: [(status, seconds)]}``."""
    out = {"submit": [], "upload": [], "status": [], "feedback": []}
    lock = threading.Lock()
    barrier = threading.Barrier(CLIENTS)

    def client(index):
        barrier.wait()
        for step in range(REQUESTS_PER_CLIENT):
            owner = door.owners[(index * REQUESTS_PER_CLIENT + step) % OWNERS]
            kind = ("submit", "upload", "status", "feedback", "submit", "status")[step]
            started = time.monotonic()
            if kind == "submit":
                answer = door.submit(owner)
            elif kind == "upload":
                answer = door.upload(owner, step)
            else:
                answer = getattr(door, kind)(owner)
            with lock:
                out[kind].append((answer.status, time.monotonic() - started))

    clients = [threading.Thread(target=client, args=(i,)) for i in range(CLIENTS)]
    for thread in clients:
        thread.start()
    for thread in clients:
        thread.join(120)
    alive = [thread for thread in clients if thread.is_alive()]
    assert alive == [], "a client never got an answer"
    return out


def _run(tmp_path, monkeypatch, **options):
    door = _Door(tmp_path, monkeypatch, **options)
    stop = threading.Event()
    rounds = _grade_rounds(door, stop)
    try:
        out = _burst(door)
    finally:
        stop.set()
        for thread in rounds:
            thread.join(10)
        door.close()
    return door, out


def _summary(door, out):
    submits = sorted(seconds for _status, seconds in out["submit"])
    return (
        f"submits {len(submits)}, slowest {submits[-1]:.2f} s, p50 {submits[len(submits) // 2]:.2f} s; "
        f"longest write-lock hold {door.write.longest:.2f} s; lazy opens {len(door.opened)}; "
        f"slow steps under the write lock {sorted(set(door.violations))} x{len(door.violations)}; "
        f"statuses {sorted({s for kind in out.values() for s, _ in kind})}"
    )


def test_every_request_is_answered_and_nothing_scales_with_all_owners(
    tmp_path, monkeypatch
):
    door, out = _run(tmp_path, monkeypatch)
    answered = sum(len(results) for results in out.values())
    assert answered == CLIENTS * REQUESTS_PER_CLIENT
    # submits, uploads, status: a typed answer each, never a server error (feedback may be typed-unavailable here)
    for kind in ("submit", "upload", "status"):
        assert all(status < 500 for status, _ in out[kind]), _summary(door, out)
    assert {status for status, _ in out["submit"]} == {202}, _summary(door, out)
    # nothing O(all owners): only owners a request concerned were ever opened
    asked = {door.owners[i % OWNERS] for i in range(CLIENTS * REQUESTS_PER_CLIENT)}
    assert door.touched <= asked and len(door.opened) <= len(asked)


def test_every_submit_completes_under_the_bound_while_uploads_and_grades_run(
    tmp_path, monkeypatch
):
    door, out = _run(tmp_path, monkeypatch)
    slowest = max(seconds for _status, seconds in out["submit"])
    assert slowest <= SUBMIT_BOUND_SECONDS, _summary(door, out)


def test_no_slow_step_runs_under_the_doors_write_lock(tmp_path, monkeypatch):
    door, out = _run(tmp_path, monkeypatch)
    assert door.violations == [], _summary(door, out)


def test_the_harness_catches_a_slow_call_held_under_the_write_lock(
    tmp_path, monkeypatch
):
    """Self-proof: with a slow task start (the door's write lock held across it) the harness names it, and the burst's
    submits pile up behind the lock past the bound.
    """
    door, out = _run(tmp_path, monkeypatch, slow_start=True)
    assert "start_research_task" in door.violations, _summary(door, out)
    assert door.write.longest >= SLOW_START_SECONDS
    slowest = max(seconds for _status, seconds in out["submit"])
    # 200 submits serialised behind 0.05 s each (10 s): far past what the bound allows a healthy door
    assert slowest > SUBMIT_BOUND_SECONDS, _summary(door, out)
