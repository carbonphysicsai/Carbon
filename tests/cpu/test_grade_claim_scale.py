"""Owner G22 (19 Nov 2026, via the Lead): no update may stall grading at live scale. After a start the first grade must
be claimed within 60 s of LISTENING, and no pass before it may touch O(all owners).

Live 116, 19 Nov 2026 07:46-08:3xZ (8632ef69): the incumbent's steps settled stop-cancelled queue places by opening the
owner of EVERY marked task (a lazy owner's full restore, a few seconds each), ~350 owners one after another, before any
grade was claimed. This harness runs the REAL code of a parallel door's first grade round at live scale over synthetic
state, and fails on that behaviour:

- the real `AttemptLedger` (sqlite, on disk), the real grade markers, the real automatic-retry log (owed re-run chains,
  one with its D16 cap spent), the real `AutoGrader` round (`_run_once_parallel`: the incumbent's steps, the claim
  scan, `grade_sequencer.Sequencer` + `OwnerClaims`) and the real `LeanRecipeAdapter.settle_stop_cancelled_places`;
- >= 400 owners, most LAZY after the start (as `OwnerProviders.restore` leaves them: only an owner with a waiting build
  or a built, unmarked task is open), each idle one carrying an old ``cancelled_by_carbon_stop`` marker as live did;
- >= 100 built, queued tasks; the first 20 belong to owners whose daily allowance (25) is spent, and an owner graded
  this round waits for the next (1 per round): both are "not yet" in the claim loop;
- a restart mid-run (the grade in flight cut by the stop, every idle owner lazy again), then the first round again.

Stand-ins, and only these: the owner pool (`provider_for`) counts every owner it is asked for and charges each LAZY
open `LAZY_OPEN_SECONDS` of virtual time (the low end of live's measured restore cost); the grade step after the pick
(`_grade_one`) opens the task's owner as the real retain step does, applies the two allowance rules and ends the round
at the first task it would reserve: that is the first claim. Synthetic ids and values only: nothing from live state.
"""

from __future__ import annotations

import json
import os
import threading
import time
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import auto_grade, auto_retry, grade_sequencer
from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.research import DirectTaskStateV3

CONTRACT = "sha256:" + "c" * 64
PACK = "sha256:" + "e" * 64
#: Owner G22: the bound on the first claim after LISTENING.
FIRST_CLAIM_SECONDS = 60.0
#: Virtual seconds per lazy owner open: live 116 measured 1,556 s for 163 lazy opens (18 Nov) and 20-50 min for ~350
#: (19 Nov), 3.4-9.5 s each; the harness charges the low end.
LAZY_OPEN_SECONDS = 3.4
#: The daily allowance in force on live 116 (owner, 19 Nov 2026); a fixture of the stand-in grade step.
DAILY_ALLOWANCE = 25

BUILT, BUSY_OWNERS, CAPPED_OWNERS = 100, 60, 10
MARKED_BUSY = 50  # open owners that also carry an old stop-cancelled marker
OWED, RESUBMITTED = 12, 2
OLD = 5 * 86400  # the 14 Nov one-shot markers were days old by the 19 Nov starts

SUCCEEDED, CANCELLED = DirectTaskStateV3.SUCCEEDED, DirectTaskStateV3.CANCELLED


def _owner(kind, i):
    return f"5{kind}{i:05d}".ljust(48, "x")


def _task(kind, i):
    return "rtsk_" + f"{kind:02x}{i:062x}"


class _Provider:
    def __init__(self, owner, views):
        self.owner = owner
        self._views = {t: SimpleNamespace(state=s) for t, s in views.items()}
        self._requests = {}
        self._lock = threading.Lock()


class _Owners:
    """The receiver's owner pool as a start leaves it (`OwnerProviders.restore`): owners with work open, the rest LAZY
    (opened, by a full restore, at their first touch). Counts every owner asked for and every lazy open.
    """

    def __init__(self, open_views, lazy_views):
        self._providers = {o: _Provider(o, v) for o, v in open_views.items()}
        self._lazy = {o: dict(v) for o, v in lazy_views.items()}
        self.touched, self.opened = set(), []

    def __call__(self, owner):
        self.touched.add(owner)
        provider = self._providers.get(owner)
        if provider is None:
            self.opened.append(owner)
            views = self._lazy.pop(owner, {})
            provider = self._providers[owner] = _Provider(owner, views)
        return provider

    def hotkey_of(self, task):
        """As `OwnerProviders.hotkey_of`: the open views, then the lazy index; never opens an owner."""
        for owner, provider in self._providers.items():
            if task in provider._views:
                return owner
        for owner, views in self._lazy.items():
            if task in views:
                return owner
        return None

    def set_aside(self):
        return frozenset()

    def cost(self):
        return len(self.opened) * LAZY_OPEN_SECONDS


def _scheduled(task, code, at_ns):
    return {"task": task, "kind": "scheduled", "code": code, "at_ns": at_ns}


def _refused(task, at_ns):
    return {"task": task, "kind": "refused", "refusal": "x", "at_ns": at_ns}


class _Scenario:
    """Synthetic live-scale door state on disk: ``idle`` lazy owners beyond the fixed working set."""

    def __init__(self, root, idle):
        self.root = root
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        seq = iter(range(1_000, 10**9, 10))
        self.ledger = AttemptLedger(root / "attempts.sqlite3", clock=lambda: next(seq))
        self.markers = root / "auto-grade" / "markers"
        self.markers.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.views = {}  # owner -> {task: build state}
        # owner -> grades counted today (the stand-in's allowance table)
        self.spent = {}

        # 1. idle owners: each was hit by an old receiver stop (its task's marker is days old); nothing waits
        for i in range(idle):
            owner, task = _owner("Idle", i), _task(1, i)
            self._submit(owner, task, CANCELLED)
            self._mark(task, "FAILED", LeanRecipeAdapter.STOP_CANCELLED_CODE, age=OLD)
        # 2. owed re-run chains on lazy owners: a FAILED Carbon-side grade, two earlier retries of other causes refused,
        #    the last one pending (due now: V2-OWED-NOW (b)); the last chain's cap for its cause is spent (D16: owed list)
        log = root / "auto-grade" / "requeued"
        log.mkdir(mode=0o700, parents=True, exist_ok=True)
        lines, now_ns = [], time.time_ns()
        for i in range(OWED):
            owner, task = _owner("Owed", i), _task(2, i)
            self._submit(owner, task, SUCCEEDED)
            self._mark(task, "FAILED", "WorkerFailure")
            earlier = ("inference_pair_incomplete", "Unavailable:unrecorded")
            for k, code in enumerate(earlier):
                lines.append(_scheduled(task, code, now_ns - (9 - k) * 10**12))
                lines.append(_refused(task, now_ns - (8 - k) * 10**12))
            if i == OWED - 1:
                for _k in range(auto_retry.PER_CAUSE_RETRIES):
                    lines.append(_scheduled(task, "WorkerFailure", now_ns - 10**12))
                    lines.append(_refused(task, now_ns - 10**12))
            else:
                lines.append(_scheduled(task, "WorkerFailure", now_ns - 10**9))
        text = "".join(json.dumps(r) + "\n" for r in lines)
        (log / auto_retry.LOG_NAME).write_text(text)
        # 3. busy owners: the built, queued tasks (open after a start: a built, unmarked task is work); the first
        #    CAPPED_OWNERS have spent today's allowance, and their tasks come first in the queue
        for i in range(BUILT):
            owner = _owner("Busy", i % BUSY_OWNERS)
            self._submit(owner, _task(3, i), SUCCEEDED)
        for i in range(CAPPED_OWNERS):
            self.spent[_owner("Busy", i)] = DAILY_ALLOWANCE
        for i in range(MARKED_BUSY):
            owner, task = _owner("Busy", i), _task(4, i)
            self._submit(owner, task, CANCELLED)
            self._mark(task, "FAILED", LeanRecipeAdapter.STOP_CANCELLED_CODE, age=OLD)
        # 4. real resubmissions waiting for their place: lazy owners with a stop-cancelled task and an intent-only task
        for i in range(RESUBMITTED):
            owner, task = _owner("Resub", i), _task(5, i)
            self._submit(owner, task, CANCELLED)
            self._mark(task, "FAILED", LeanRecipeAdapter.STOP_CANCELLED_CODE, age=OLD)
            self.ledger.record_recipe_task_intent(CONTRACT, _task(6, i), owner, "r")

    def _submit(self, owner, task, state):
        self.ledger.record(
            SimpleNamespace(
                hotkey=owner,
                receipt={"sequence": 1, "digest": "d", "block": 1},
                contract_digest=CONTRACT,
            ),
            kind="OUTCOME",
            submission_id=task,
        )
        self.views.setdefault(owner, {})[task] = state

    def _mark(self, task, state, code, age=0.0):
        path = self.markers / f"{task}.json"
        path.write_text(json.dumps({"state": state, "code": code}))
        if age:
            then = time.time() - age
            os.utime(path, (then, then))

    def start(self):
        """A receiver start: the owner pool as `restore` leaves it, a fresh grader (a new process's state)."""
        marked = {p.stem for p in self.markers.glob("rtsk_*.json")}
        has_work = {
            owner
            for owner, views in self.views.items()
            if any(s is SUCCEEDED and t not in marked for t, s in views.items())
        }
        owners = _Owners(
            {o: v for o, v in self.views.items() if o in has_work},
            {o: v for o, v in self.views.items() if o not in has_work},
        )
        door = object.__new__(LeanRecipeAdapter)
        door.ledger, door.contract_digest = self.ledger, CONTRACT
        door.provider_for = owners
        door.discovery = SimpleNamespace(
            evaluation_pack_digest=PACK, evaluation_pack_snapshot=None
        )
        intake = SimpleNamespace(
            adapter=door,
            window=None,
            draining=lambda: False,
            challenge=SimpleNamespace(challenge_id="synthetic", version="0"),
        )
        grader = auto_grade.AutoGrader(
            intake, self.root, containers=lambda: 0, gpu=lambda: 0
        )
        grader.sequencer = grade_sequencer.Sequencer()
        grader.owner_claims = grade_sequencer.OwnerClaims()
        grader.claimed = []
        graded_round = set()

        def grade_one(submission_id, turn=lambda: None):
            # the real retain step opens the task's owner (a lazy owner's restore) before anything is reserved
            owner = grader._owner_of(submission_id)
            if owner is None:
                return auto_grade._NEXT
            view = owners(owner)._views.get(submission_id)
            if view is None or view.state is not SUCCEEDED:
                return auto_grade._NEXT  # task_not_succeeded
            if self.spent.get(owner, 0) >= DAILY_ALLOWANCE or owner in graded_round:
                # the allowance's "not yet": 25 a day, 1 a round
                return auto_grade._NEXT
            graded_round.add(owner)
            grader.claimed.append(submission_id)
            return submission_id, "GRADED"

        grader._grade_one = grade_one
        return grader, owners


@pytest.fixture(autouse=True)
def _fresh_process(monkeypatch):
    # each start is a new process: the hourly carbon-cut sweep's memory starts empty
    monkeypatch.setattr(auto_retry, "_SWEPT", {})


def _first_round(scenario, monkeypatch):
    monkeypatch.setattr(auto_retry, "_SWEPT", {})
    grader, owners = scenario.start()
    started = time.monotonic()
    outcome = grader.run_once()
    seconds = time.monotonic() - started + owners.cost()
    return grader, owners, outcome, seconds


def _report(owners, seconds):
    bound = FIRST_CLAIM_SECONDS
    return (
        f"first claim {seconds:.0f} s after LISTENING (bound {bound:.0f} s): "
        f"{len(owners.opened)} lazy owners opened, "
        f"{len(owners.touched)} owners touched"
    )


def test_the_first_claim_after_a_start_is_within_60_s_at_live_scale(
    tmp_path, monkeypatch
):
    scenario = _Scenario(tmp_path / "receiver", idle=340)
    assert len(scenario.views) >= 400 and BUILT >= 100
    grader, owners, outcome, seconds = _first_round(scenario, monkeypatch)
    assert outcome is not None and outcome[1] == "GRADED", outcome
    # the capped owners' tasks came first: each is "not yet", the first claim is the first task past them
    assert grader.claimed == [_task(3, CAPPED_OWNERS)]
    assert seconds <= FIRST_CLAIM_SECONDS, _report(owners, seconds)


def test_a_restart_mid_run_claims_again_within_60_s(tmp_path, monkeypatch):
    scenario = _Scenario(tmp_path / "receiver", idle=340)
    grader, _owners_before, outcome, _seconds = _first_round(scenario, monkeypatch)
    cut, _state = outcome
    # the stop cuts the grade in flight (Carbon's: a FAILED marker), then the receiver starts again
    scenario._mark(cut, "FAILED", "Unavailable:unrecorded")
    grader, owners, outcome, seconds = _first_round(scenario, monkeypatch)
    assert outcome is not None and outcome[1] == "GRADED", outcome
    assert grader.claimed and grader.claimed[0] != cut
    assert seconds <= FIRST_CLAIM_SECONDS, _report(owners, seconds)


def test_no_pass_before_the_first_claim_scales_with_all_owners(tmp_path, monkeypatch):
    """Doubling the idle (lazy) owners changes nothing the first round touches: no pass is O(all owners)."""
    small = _first_round(_Scenario(tmp_path / "small", idle=340), monkeypatch)
    large = _first_round(_Scenario(tmp_path / "large", idle=740), monkeypatch)
    (_g1, owners_small, _o1, s_small), (_g2, owners_large, _o2, s_large) = small, large
    assert len(owners_large.opened) == len(owners_small.opened), (
        _report(owners_small, s_small),
        _report(owners_large, s_large),
    )
    assert len(owners_large.touched) == len(owners_small.touched), (
        _report(owners_small, s_small),
        _report(owners_large, s_large),
    )
