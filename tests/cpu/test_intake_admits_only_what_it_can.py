"""Each process admits and advances only what it can (lane D's L1 finding).

The intake's process holds neither the ladder's compiler nor a registered
score: its import closure must never reach the variant module or the score's
value-analysis code. On r8.1 its worker still admitted a ladder variant (and
recorded `development_variant_not_served` against the miner as
INVALID_CONSTRUCTION) and advanced submissions it could not score, spending
their infrastructure attempts. Now it leaves such a submission RECEIVED and
advances nothing there; the daemon, whose entry point installs both, runs the
same pass over the same inbox (`operate run --inbox`).
"""

from __future__ import annotations

from types import SimpleNamespace

from carbon.battery import deployment
from carbon.battery import intake as ib
from carbon.battery.daemon import DevelopmentCompilerUnavailable


class _Inbox:
    def __init__(self, received, admitted=()):
        self._received, self._admitted, self.marks = list(received), list(admitted), []

    def received(self):
        return list(self._received)

    def admitted(self):
        return list(self._admitted)

    def mark(self, submission_id, state, failure=None):
        self.marks.append((submission_id, state))


class _Target:
    def __init__(self, *, rule=None, ladder=None, compiler=None, score=None):
        self.rule = rule or {}
        self.ladder = ladder
        self.development_compiler = compiler
        self.registered_score = score
        self.lock_path = None
        self.processed, self.ran = [], 0

    def admit(self, submission):
        if submission == "dev" and not callable(self.development_compiler):
            raise DevelopmentCompilerUnavailable("digest")
        return {"submission_id": submission, "state": "ADMITTED"}

    def outcome(self, submission_id):
        return {"state": "ADMITTED"}

    def process(self, submission_id):
        self.processed.append(submission_id)

    def run_pending(self):
        self.ran += 1
        return []


def _run(monkeypatch, target, inbox):
    import contextlib

    monkeypatch.setattr(deployment, "writer", lambda t: contextlib.nullcontext())
    return ib.work_once(inbox, target)


def test_the_intake_leaves_a_ladder_variant_for_the_daemon(monkeypatch):
    target = _Target(ladder={"hotkeys": frozenset(), "variants": {}})
    inbox = _Inbox([("s-dev", "dev"), ("s-l0", "l0")], admitted=["s-old"])
    moved = _run(monkeypatch, target, inbox)
    assert ("s-dev", "ADMITTED") not in inbox.marks  # left RECEIVED
    assert ("s-l0", "ADMITTED") in inbox.marks
    assert moved["left"] == 1
    # No compiler: nothing is advanced here.
    assert target.processed == [] and target.ran == 0


def test_the_daemon_with_the_compiler_admits_and_advances_it(monkeypatch):
    target = _Target(
        ladder={"hotkeys": frozenset(), "variants": {}}, compiler=lambda *a: None
    )
    inbox = _Inbox([("s-dev", "dev")], admitted=["s-dev"])
    moved = _run(monkeypatch, target, inbox)
    assert ("s-dev", "ADMITTED") in inbox.marks and moved["left"] == 0
    assert target.processed == ["s-dev"] and target.ran == 1


def test_without_the_registered_score_the_intake_advances_nothing(monkeypatch):
    rule = {"score": {"candidate": "G-FEAS/A-Q>@0.05"}}
    unscored = _Target(rule=rule)
    _run(monkeypatch, unscored, _Inbox([("s", "l0")], admitted=["s"]))
    assert unscored.processed == [] and unscored.ran == 0
    scored = _Target(rule=rule, score=object())
    _run(monkeypatch, scored, _Inbox([("s", "l0")], admitted=["s"]))
    assert scored.processed == ["s"] and scored.ran == 1


def test_processes_here():
    assert deployment.processes_here(SimpleNamespace(rule={}, ladder=None))
    assert not deployment.processes_here(
        SimpleNamespace(rule={}, ladder={}, development_compiler=None)
    )
    assert not deployment.processes_here(
        SimpleNamespace(rule={"score": {}}, ladder=None, registered_score=None)
    )
