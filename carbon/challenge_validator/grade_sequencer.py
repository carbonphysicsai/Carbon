"""One door, N grades at once, committed in order (owner's order 16 Nov 2026, via the Lead).

A door in lane mode runs one grade round per lane (`direct_intake._WorkLock`). Each grade's heavy work (the graded
pass, the subset repeat, the menu re-check) runs in parallel on its lane, but everything that depends on the ORDER of
grades is committed by one writer, in claim order (= the door's pending order = submission order):

- **Claim** (`Sequencer.task`): one grade at a time PICKS the next pending task (its owner, its group) and binds it;
  the claim lock then goes at once (`_Task.release_claim`, design A, 19 Nov 2026: live 116 lost 20-30 min of grading
  after every start while one claim held the lock through a lazy owner's open and the retain step). The retain step
  and the owner's open run outside the lock, in parallel with other rounds' picks.
- **Reservation turn** (`reserve_turn`): just before its exam-cap reservation a grade waits until every EARLIER claimed
  grade has reserved or ended; `claimed` marks it reserved. So reservations, and every allowance count they read, are
  made in claim order exactly as when the claim lock was held through them.
- **Commit turn** (`turn`): before its own order-dependent writes (the exam-cap settle, which feeds every later
  allowance of ITS group; the Ladder, one row per hotkey; the marker), a grade waits until every EARLIER claimed grade
  of the SAME exam-cap allowance group has finished (a grade whose group is unknown waits for, and holds, every
  earlier one). Fix 1b (V2's verdict of 18 Nov 2026, GRADE_SPEED_20261118.md; Lead 19 Nov): across groups these writes
  are order-free (M counts RESERVED + COUNTED rows, reserved at claim), so a light grade's marker, settle, keep, lane
  and slot land at once, never behind an earlier heavy grade of another miner (live 116, 19 Nov 11:31-11:44Z: light
  grades done in 100-200 s landed 593-653 s after their claim). Before waiting it gives up its grade-session container
  (`research_carrier.yield_grade_session`).
- **Crown queue** (`crown_decision`): the crown IS order-dependent (V2: with the crown margin, K = 1.00, earlier A = 1.05,
  later B = 1.06 crowns A in claim order but B out of order: a different miner holds the weights). Each grade's crown
  decision is appended under its ticket and applied strictly in claim order by one applier (`_drain`: whichever thread
  can take the short applier lock, under `CROWN_LOCK`). A decision waits only for EARLIER grades' decisions, never in
  its grade's thread: a grade whose earlier ones are still running hands its decision over and ends (its lane and its
  round are freed); the earlier grade's thread applies it after its own. A grade that ends with no decision (FAILED,
  RELEASED, refused, an exception) closes its ticket so the queue never waits on it; a hung grade ended by `abandon`
  drops any decision it had queued (its slot was given back: never a free grade that crowns). The queue is in memory;
  a caller's ``journal`` makes each decision durable (V2 C5, 19 Nov 2026: a decision queued at a stop is never lost):
  ``queued`` before it is handed over, ``applied`` or ``dropped`` after (`lean_recipe_retention.CrownJournal`, re-filed
  at the next start by `lean_recipe_retention.refile_queued_crowns`).
- **Exclusive** (`exclusive`): the king's upkeep, the crown sweep and due retries move the incumbent; they run only
  with no grade claimed and none in flight.

Outside a sequenced task every hook is a no-op, so a door with one lane, a tool, or a test behaves exactly as before.
This module decides no order of its own and sets no value: the order is the door's pending order.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar

_CURRENT: ContextVar = ContextVar("carbon_grade_sequencer_task", default=None)


#: V2 (19 Nov 2026, design A addition 1): how long an early claim may retain before its reservation while later claims
#: wait on it. Past it the early claim no longer holds the order: later claims reserve and commit, and the early one ends
#: "not yet" at its own reservation turn (`ReserveTurnExpired`: its task goes back to pending, nothing reserved,
#: uncharged). OPERATIONAL (door-code picks, minutes, not GRADE_HUNG_SECONDS): a slow lazy open is ~12 s, a retain step
#: a few seconds; 300 s only ends a claim that is truly stuck before its reservation.
RETAIN_BEFORE_RESERVE_SECONDS = 300


class ReserveTurnExpired(RuntimeError):
    """This claim retained past `RETAIN_BEFORE_RESERVE_SECONDS` and later claims went ahead: it ends "not yet"."""

    code = "reserve_turn_expired"


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
        #: ticket -> when its grade was claimed (`time.monotonic`), for `overdue`
        self._started = {}
        #: tickets ended as hung (`abandon`): their thread may never commit
        self._abandoned = set()
        #: tickets inside their commit-turn wait (`_Task.turn`): a legitimate wait on EARLIER grades, never hung (V2)
        self._waiting = set()
        #: tickets past their exam-cap reservation (`claimed`): a later grade's `reserve_turn` no longer waits for them
        self._reserved = set()
        #: ticket -> when it was claimed (never reset), for `RETAIN_BEFORE_RESERVE_SECONDS`
        self._claimed_at = {}
        #: tickets that retained past the bound: they no longer hold the order and end "not yet" at their own turn
        self._expired = set()
        #: the crown queue (`crown_decision`): ticket -> its decisions not yet applied, in the order they came, each
        #: ``(apply, drop)``: ``drop`` is called when an abandoned grade's decision is dropped
        self._crown = {}
        #: tickets whose grade ended (or was abandoned): no further decision of theirs will come
        self._crown_closed = set()
        #: the lowest ticket whose decisions are not all applied: the queue's head (tickets are dense from 0)
        self._crown_next = 0
        #: held by the one thread applying decisions now (`_drain`), never waited for
        self._applier = threading.Lock()

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
            self._started[ticket] = time.monotonic()
            self._claimed_at[ticket] = self._started[ticket]
        state = _Task(self, ticket)
        token = _CURRENT.set(state)
        try:
            yield state
        finally:
            _CURRENT.reset(token)
            state.release_claim()
            # its decisions are all in: the queue goes past it, applying whatever later grades handed over meanwhile,
            # before its ticket leaves the open set (`exclusive` never sees a door with a decision still queued)
            self._close_crown(ticket)
            with self._order:
                self._open.pop(ticket, None)
                self._groups.pop(ticket, None)
                self._started.pop(ticket, None)
                self._abandoned.discard(ticket)
                self._waiting.discard(ticket)
                self._reserved.discard(ticket)
                self._claimed_at.pop(ticket, None)
                self._expired.discard(ticket)
                self._order.notify_all()

    def _holds_order(self, other, now):
        """Whether open ticket ``other`` (earlier than a caller) still holds the reservation / commit order: not past
        its bound. An unreserved ticket that is not itself waiting and retained past `RETAIN_BEFORE_RESERVE_SECONDS` is
        marked expired (caller holds ``_order``)."""
        if other in self._expired:
            return False
        age = now - self._claimed_at.get(other, now)
        if (
            other not in self._reserved
            and other not in self._waiting
            and age > RETAIN_BEFORE_RESERVE_SECONDS
        ):
            self._expired.add(other)
            self._order.notify_all()
            return False
        return True

    def overdue(self, seconds, now=None):
        """``[(ticket, submission id)]`` of the grades claimed more than ``seconds`` ago and still open (a grade stuck in
        Carbon's own code: a model cannot run past its worker wall)."""
        now = time.monotonic() if now is None else now
        with self._order:
            return [
                (ticket, sid)
                for ticket, sid in self._open.items()
                if sid is not None
                and ticket not in self._abandoned
                and ticket not in self._waiting
                and now - self._started.get(ticket, now) > seconds
            ]

    def age(self, ticket, now=None):
        """Seconds since ``ticket``'s grade was claimed (None when unknown)."""
        now = time.monotonic() if now is None else now
        with self._order:
            started = self._started.get(ticket)
        return None if started is None else now - started

    def abandon(self, ticket):
        """End a hung grade's place in the order (`overdue`): later grades no longer wait for it, and its own thread,
        should it ever wake, raises `GradeAbandoned` at its next commit turn instead of writing anything.
        """
        with self._order:
            self._open.pop(ticket, None)
            self._groups.pop(ticket, None)
            self._abandoned.add(ticket)
            # fix 1b: its queued crown decision is dropped (its slot is given back as Carbon's: never a free grade
            # that crowns) and the queue goes on past it
            dropped = self._crown.pop(ticket, None) or []
            self._order.notify_all()
        for _apply, drop in dropped:
            try:
                drop()
            # a dropped decision's record never stops the door
            except Exception as error:  # noqa: BLE001
                from carbon.battery.intake import log

                log("crown_decision_drop_failed", type=type(error).__name__)
        self._close_crown(ticket)

    def _close_crown(self, ticket):
        """No further crown decision of ``ticket`` will come: the queue may go past it (`_drain`)."""
        with self._order:
            if ticket >= self._crown_next:
                self._crown_closed.add(ticket)
        self._drain()

    def _submit_crown(self, ticket, apply, drop=lambda: None):
        """Append ``apply`` to ``ticket``'s crown decisions, then apply every decision that is next in claim order."""
        with self._order:
            if ticket in self._abandoned:
                raise GradeAbandoned(ticket)
            self._crown.setdefault(ticket, []).append((apply, drop))
        self._drain()

    def _next_crown(self):
        """The next decision to apply in claim order, or None (under ``_order``): the head ticket's next queued
        decision; a closed head with none left is passed."""
        while True:
            head = self._crown_next
            queued = self._crown.get(head)
            if queued:
                apply, _drop = queued.pop(0)
                return apply
            # an expired claim (design A: stuck before its reservation) can bring no decision: passed as closed
            if head in self._crown_closed or head in self._expired:
                self._crown_closed.discard(head)
                self._crown.pop(head, None)
                self._crown_next = head + 1
                continue
            return None

    def _drain(self):
        """Apply the crown decisions that are next in claim order, in one thread at a time: a thread that finds the
        applier busy leaves them to it (it looks again before it lets go, so none is left behind).
        """
        while True:
            if not self._applier.acquire(blocking=False):
                return
            try:
                while True:
                    with self._order:
                        apply = self._next_crown()
                    if apply is None:
                        break
                    try:
                        apply()
                    # one decision never stops the queue
                    except Exception as error:  # noqa: BLE001
                        from carbon.battery.intake import log

                        log("crown_decision_failed", type=type(error).__name__)
            finally:
                self._applier.release()
            with self._order:
                head = self._crown_next
                ready = (
                    bool(self._crown.get(head))
                    or head in self._crown_closed
                    or head in self._expired
                )
            if not ready:
                return

    @contextmanager
    def exclusive(self):
        """No grade claims, and none is in flight, while this runs (the incumbent's own steps)."""
        with self._claim:
            with self._order:
                while self._open:
                    self._order.wait(1.0)
            yield

    @contextmanager
    def exclusive_within(self, seconds):
        """`exclusive`, waited for at most ``seconds`` (the claim lock, then every grade in flight to end); yields
        whether it is held. Not in time: the claim lock is let go at once, and the caller asks again later (live 116, 18
        Nov 2026: an unbounded drain behind one stuck grade held the claim lock, and the door graded nothing for 30 min).
        """
        deadline = time.monotonic() + seconds
        if not self._claim.acquire(timeout=max(0.0, seconds)):
            yield False
            return
        try:
            with self._order:
                while self._open and time.monotonic() < deadline:
                    self._order.wait(max(0.0, min(1.0, deadline - time.monotonic())))
                drained = not self._open
        except BaseException:
            self._claim.release()
            raise
        if not drained:
            self._claim.release()
            yield False
            return
        try:
            yield True
        finally:
            self._claim.release()


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

    def reserve_turn(self):
        """Wait until every EARLIER claimed grade has made its exam-cap reservation or ended (design A): reservations
        stay in claim order now that the claim lock is let go after the pick. A legitimate wait on earlier grades, as
        the commit turn is: `overdue` skips this ticket meanwhile and its clock starts afresh after.
        """
        if self.ticket in self.sequencer._abandoned:
            raise GradeAbandoned(self.ticket)
        order = self.sequencer._order
        seq = self.sequencer
        with order:
            if self.ticket in seq._expired:
                raise ReserveTurnExpired(self.ticket)

        def earlier():
            now = time.monotonic()
            return any(
                other < self.ticket
                and other not in seq._reserved
                and seq._holds_order(other, now)
                for other in tuple(seq._open)
            )

        with order:
            if not earlier():
                return
            seq._waiting.add(self.ticket)
        try:
            with order:
                while earlier():
                    order.wait(1.0)
        finally:
            with order:
                seq._waiting.discard(self.ticket)
                if self.ticket in seq._started:
                    seq._started[self.ticket] = time.monotonic()
        if self.ticket in seq._abandoned:
            raise GradeAbandoned(self.ticket)
        with order:
            if self.ticket in seq._expired:
                raise ReserveTurnExpired(self.ticket)

    def _earlier_holding(self):
        """Whether an EARLIER open ticket still holds this grade's commit order (caller holds ``_order``): one of the
        same exam-cap allowance group, or of an unknown group (None, or not bound yet), and not expired (design A); a
        grade whose own group is unknown is ordered behind every earlier one (fix 1b: across groups a grade's own
        writes are order-free; only the crown decision is claim-ordered, `crown_decision`)."""
        seq = self.sequencer
        mine = seq._groups.get(self.ticket)
        now = time.monotonic()
        for other in tuple(seq._open):
            if other >= self.ticket:
                continue
            theirs = seq._groups.get(other)
            related = mine is None or theirs is None or theirs == mine
            if related and seq._holds_order(other, now):
                return True
        return False

    def reserved(self):
        """This grade's reservation is made (or refused): later grades may reserve, and the claim lock, if still held,
        goes."""
        with self.sequencer._order:
            self.sequencer._reserved.add(self.ticket)
            self.sequencer._order.notify_all()
        self.release_claim()

    def turn(self):
        """Wait until every earlier grade of this grade's allowance group has finished (idempotent; fix 1b). Gives up
        the claim lock and, before any wait, this grade's session container."""
        if self.ticket in self.sequencer._abandoned:
            raise GradeAbandoned(self.ticket)
        if self._turned:
            return
        self.release_claim()
        order = self.sequencer._order
        with order:
            earlier = self._earlier_holding()
        if not earlier:
            self._turned = True
            return
        from carbon.development_session.research_carrier import yield_grade_session

        # best effort itself: a removal that cannot be confirmed means no later op joins it, and the grade session's
        # own exit removes (and reports) it again
        yield_grade_session()
        # Lead (18 Nov 2026, live 116 deadlock, STACKS #4): the grade KEEPS its lane through this wait. A lane given
        # back here had to be re-taken behind every queued build and grade round, while the rounds behind it waited
        # for this ticket: the head of the commit order never got a lane back, and nothing graded.
        # V2 (18 Nov 2026): the commit-turn wait, and the lane re-take after it, are waits on EARLIER grades: `overdue`
        # skips this ticket meanwhile, and its clock starts afresh after, so a healthy grade behind a slow head is never
        # ended as hung (only the head, or a ticket stuck outside this wait, can be)
        with order:
            self.sequencer._waiting.add(self.ticket)
        try:
            with order:
                while self._earlier_holding():
                    order.wait(1.0)
        finally:
            with order:
                self.sequencer._waiting.discard(self.ticket)
                if self.ticket in self.sequencer._started:
                    self.sequencer._started[self.ticket] = time.monotonic()
        if self.ticket in self.sequencer._abandoned:
            raise GradeAbandoned(self.ticket)
        self._turned = True

    def crown(self, decide, journal=None):
        """Hand this grade's crown decision to the crown queue (`crown_decision`): ``decide()`` runs under `CROWN_LOCK`
        once every earlier grade's decisions are applied or it ended. Returns ``decide()``'s result when it was applied
        now (no earlier decision outstanding), else `CROWN_QUEUED`: this grade goes on and ends; the decision is applied
        by the thread of the earlier grade, after its own. ``journal`` (optional): ``queued()`` is written BEFORE the
        hand-over (so a stop can never lose a decision the grade's marker already says is graded), ``applied()`` after
        the decision, ``dropped()`` when `abandon` drops it."""
        result = {}

        def apply():
            try:
                with CROWN_LOCK:
                    result["value"] = decide()
            finally:
                _journal(journal, "applied")

        if self.ticket in self.sequencer._abandoned:
            raise GradeAbandoned(self.ticket)
        _journal(journal, "queued")
        self.sequencer._submit_crown(
            self.ticket, apply, lambda: _journal(journal, "dropped")
        )
        return result.get("value", CROWN_QUEUED)


class GradeAbandoned(RuntimeError):
    """This grade was ended as hung (`Sequencer.abandon`): it never commits."""


#: The crown's in-process lock (V2, 18 Nov 2026, replacing the door-wide `Sequencer.exclusive`): held around each
#: grade's crown commit (`lean_recipe_retention._contend`'s consideration) and the incumbent's own crown steps
#: (`auto_grade._crown_steps`), so no two of them read and write the king at once. The store's own compare-and-set
#: (`PoolStore._set_incumbent`: the expected king checked inside one BEGIN IMMEDIATE transaction) still refuses a
#: king that moved. Re-entrant: an incumbent step that files a stranded challenger reaches `_contend` holding it.
CROWN_LOCK = threading.RLock()


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
    def within(self, owners, seconds, poll=1.0):
        """Hold ``owners`` (None: every owner, `exclusive`), waiting at most ``seconds`` for the rounds holding them;
        yields whether they are held. Not held in time: nothing is kept and no later claim is refused (V2, 18 Nov 2026:
        the incumbent's steps wait inside the sequencer's exclusive, never unboundedly behind a running build).
        """
        import time

        deadline = time.monotonic() + seconds
        if owners is None:
            with self._cond:
                while self._exclusive:
                    left = deadline - time.monotonic()
                    if not self._cond.wait(max(0.0, min(poll, left))) and left <= poll:
                        break
                if self._exclusive:
                    got = False
                else:
                    self._exclusive = True
                    while self._held and time.monotonic() < deadline:
                        self._cond.wait(
                            max(0.0, min(poll, deadline - time.monotonic()))
                        )
                    got = not self._held
                    if not got:
                        self._exclusive = False
                        self._cond.notify_all()
            try:
                yield got
            finally:
                if got:
                    with self._cond:
                        self._exclusive = False
                        self._cond.notify_all()
            return
        wanted, taken = sorted(owners), []
        try:
            with self._cond:
                while True:
                    for owner in wanted:
                        if (
                            owner not in taken
                            and not self._exclusive
                            and owner not in self._held
                        ):
                            self._held.add(owner)
                            taken.append(owner)
                    if len(taken) == len(wanted) or time.monotonic() >= deadline:
                        break
                    self._cond.wait(max(0.0, min(poll, deadline - time.monotonic())))
            got = len(taken) == len(wanted)
            if not got:
                for owner in taken:
                    self.release(owner)
                taken = []
            yield got
        finally:
            for owner in taken:
                self.release(owner)

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


#: What `crown_decision` returns for a decision queued behind an earlier grade's (fix 1b): the grade goes on and ends;
#: the decision is applied in claim order later (its outcome reaches the KOTH journal then).
CROWN_QUEUED = {
    "outcome": "QUEUED_IN_CLAIM_ORDER",
    "reason": "earlier_grade_in_flight",
}


def _journal(journal, event):
    """Write one event of a crown decision's durable record; a record that cannot be written is logged, never a
    reason to lose or stop the decision itself."""
    if journal is None:
        return
    try:
        getattr(journal, event)()
    except Exception as error:  # noqa: BLE001
        from carbon.battery.intake import log

        log("crown_queue_journal_failed", event=event, type=type(error).__name__)


def crown_decision(decide, journal=None):
    """Apply a grade's crown decision ``decide()`` (the king read and the crown written) in claim order (fix 1b, see the
    module docstring). Unsequenced (one lane, a tool, a test, an incumbent step): run now under `CROWN_LOCK`, as
    before, with no record. Returns ``decide()``'s result, or a copy of `CROWN_QUEUED`. ``journal``: see `_Task.crown`.
    """
    task = _CURRENT.get()
    if task is None:
        with CROWN_LOCK:
            return decide()
    value = task.crown(decide, journal)
    return dict(CROWN_QUEUED) if value is CROWN_QUEUED else value


def claimed():
    """The calling grade has made (or been refused) its order-dependent reservation: later grades may reserve, and the
    claim lock goes if still held. No-op unsequenced."""
    task = _CURRENT.get()
    if task is not None:
        task.reserved()


def reserve_turn():
    """Wait for the calling grade's reservation turn (see the module docstring). No-op unsequenced."""
    task = _CURRENT.get()
    if task is not None:
        task.reserve_turn()


def turn():
    """Wait for the calling grade's commit turn (see the module docstring). No-op unsequenced."""
    task = _CURRENT.get()
    if task is not None:
        task.turn()


__all__ = [
    "CROWN_QUEUED",
    "GradeAbandoned",
    "OwnerClaims",
    "Sequencer",
    "claimed",
    "crown_decision",
    "current",
    "owner_exclusive",
    "turn",
]
