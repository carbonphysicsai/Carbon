"""One door, N grades at once, committed in order (owner's order 16 Nov 2026, via the Lead).

A door in lane mode runs one grade round per lane (`direct_intake._WorkLock`). Each grade's heavy work (the graded
pass, the subset repeat, the menu re-check) runs in parallel on its lane, but everything that depends on the ORDER of
grades is committed by one writer, in claim order (= the door's pending order = submission order):

- **Claim** (`Sequencer.task`): one grade at a time picks the next pending task and does the cheap preparation up to and
  including its exam-cap reservation (allowance counts read in order); `claimed` then lets the next grade claim.
- **Commit turn** (`turn`): before the order-dependent writes (the exam-cap settle, which feeds every later allowance;
  the crown compare-and-set; the Ladder; the marker), a grade waits until every EARLIER claimed grade has finished.
  Before waiting it gives up its grade-session container (`research_carrier.yield_grade_session`), so the idle
  container never sits on its lane's cores meanwhile.
- **Exclusive** (`exclusive`): the king's upkeep, the crown sweep and due retries move the incumbent; they run only
  with no grade claimed and none in flight.

Outside a sequenced task every hook is a no-op, so a door with one lane, a tool, or a test behaves exactly as before.
This module decides no order of its own and sets no value: the order is the door's pending order.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar

_CURRENT: ContextVar = ContextVar("carbon_grade_sequencer_task", default=None)


class Sequencer:
    """A door's claim lock, its tickets, and the commit order. Shared by the door's grade threads."""

    def __init__(self):
        self._claim = threading.Lock()
        self._order = threading.Condition()
        self._next = 0
        #: ticket -> submission id, for every grade claimed and not yet finished
        self._open = {}
        #: ticket -> its task's exam-cap allowance group (`exam_cap.group_of`), None when unknown
        self._groups = {}

    def in_flight(self):
        """The submission ids claimed and not yet finished (a claim skips them)."""
        with self._order:
            return {sid for sid in self._open.values() if sid is not None}

    def groups_in_flight(self):
        """The exam-cap allowance groups of the grades in flight (a claim holds a later task of the same group back,
        so its allowance is read after the earlier one settles, as one at a time does). An unknown group is "any".
        """
        with self._order:
            return set(self._groups.values())

    @contextmanager
    def task(self):
        """One grade: holds the claim lock until `claimed` or `turn` (or the end), and a ticket until the end."""
        self._claim.acquire()
        with self._order:
            ticket = self._next
            self._next += 1
            self._open[ticket] = None
        state = _Task(self, ticket)
        token = _CURRENT.set(state)
        try:
            yield state
        finally:
            _CURRENT.reset(token)
            state.release_claim()
            with self._order:
                self._open.pop(ticket, None)
                self._groups.pop(ticket, None)
                self._order.notify_all()

    @contextmanager
    def exclusive(self):
        """No grade claims, and none is in flight, while this runs (the incumbent's own steps)."""
        with self._claim:
            with self._order:
                while self._open:
                    self._order.wait(1.0)
            yield


class _Task:
    def __init__(self, sequencer, ticket):
        self.sequencer = sequencer
        self.ticket = ticket
        self._claim_held = True
        self._turned = False

    def bind(self, submission_id, group=None):
        """Name the task this ticket grades, and its exam-cap allowance group (None: unknown)."""
        with self.sequencer._order:
            self.sequencer._open[self.ticket] = submission_id
            self.sequencer._groups[self.ticket] = group

    def release_claim(self):
        if self._claim_held:
            self._claim_held = False
            self.sequencer._claim.release()

    def turn(self):
        """Wait until every earlier grade has finished (idempotent). Gives up the claim lock and this grade's session
        container first."""
        if self._turned:
            return
        self.release_claim()
        order = self.sequencer._order
        with order:
            earlier = any(other < self.ticket for other in self.sequencer._open)
        if earlier:
            from carbon.development_session.research_carrier import (
                yield_grade_session,
            )

            # best effort itself: a removal that cannot be confirmed means no later op joins it, and the grade
            # session's own exit removes (and reports) it again
            yield_grade_session()
        with order:
            while any(other < self.ticket for other in self.sequencer._open):
                order.wait(1.0)
        self._turned = True


class OwnerClaims:
    """The owners (miner hotkeys) with a round in flight on this door, across BOTH kinds of round (A19, Lead 16 Nov
    2026: N advance rounds beside N grade rounds). Each owner's work runs in that owner's own ledger, whose numerical
    lease is NON-blocking (`research_carrier._numerical_lease`): two rounds of one owner at once would fail the second.
    So a round takes an owner only when no other round holds it (`try_claim`), and the incumbent's own steps (the
    king's upkeep, the crown sweep, due retries), which run in the king's owner's ledger, take every owner at once
    (`exclusive`). Decides nothing about order: the grade commit order stays the sequencer's.
    """

    def __init__(self):
        self._cond = threading.Condition()
        self._held = set()
        self._exclusive = False

    def try_claim(self, owner):
        """Take ``owner`` for one round, or False (another round holds it, or the incumbent's steps run)."""
        with self._cond:
            if self._exclusive or owner in self._held:
                return False
            self._held.add(owner)
            return True

    def release(self, owner):
        with self._cond:
            self._held.discard(owner)
            self._cond.notify_all()

    def held(self):
        with self._cond:
            return set(self._held)

    @contextmanager
    def exclusive(self):
        """No owner is claimed while this runs: new claims are refused, and it waits for the held ones to end."""
        with self._cond:
            while self._exclusive:
                self._cond.wait(1.0)
            self._exclusive = True
            try:
                while self._held:
                    self._cond.wait(1.0)
            except BaseException:
                self._exclusive = False
                self._cond.notify_all()
                raise
        try:
            yield
        finally:
            with self._cond:
                self._exclusive = False
                self._cond.notify_all()


@contextmanager
def owner_exclusive(claims):
    """`OwnerClaims.exclusive` of ``claims``, or nothing when there are none (one-lane doors, tools, tests)."""
    if claims is None:
        yield
    else:
        with claims.exclusive():
            yield


def current():
    """The sequenced grade of the calling context, or None."""
    return _CURRENT.get()


def claimed():
    """The calling grade has made its order-dependent reservation: the next grade may claim. No-op unsequenced."""
    task = _CURRENT.get()
    if task is not None:
        task.release_claim()


def turn():
    """Wait for the calling grade's commit turn (see the module docstring). No-op unsequenced."""
    task = _CURRENT.get()
    if task is not None:
        task.turn()


__all__ = [
    "OwnerClaims",
    "Sequencer",
    "claimed",
    "current",
    "owner_exclusive",
    "turn",
]
