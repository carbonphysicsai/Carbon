"""Grades that read the repeat pair under the SAME ceiling read together (owner LO-3, 19 Nov 2026; case-procs).

`carbon.scoring.pair_read_bound` raises the source-free pair reader's ceiling (`inference_pair_evidence._MAX_BYTES`, a
process-global module constant) for a Motor 1.8 grade, under ONE process-wide re-entrant lock (`_LOCK`): `raised` for
1.8's sized blocks and `held` for every other produce. That lock ran every 1.8 grade's measure, evidence binding and
pool filing / crown decision one grade at a time on a door that grades on 8 lanes, though each of them reads under the
same 1.8 ceiling.

`pair_read_bound.py` is a Motor 1.8 PRODUCER file (`motor18_dual_pack._BOUND_FILE`): its bytes are in 1.8's producer
digest, which `scripts/validator_host_classes/producer_successor.json` pins and every 1.8 grade's producer binding checks.
So its bytes do not move (v2 20 Nov 16:12:44Z). This door-side module replaces the lock at RUNTIME instead, the way
`pair_read_bound.size_produce` itself wraps `physical_dual_pack.produce`: `install` points the module's `held`,
`raised` and `_LOCK` at one gate (`_Gate`). Every caller reaches them through the module at call time (the sized
`produce` wrapper, `subset_repeat_produce`, `lean_recipe_retention`), so all of them hold the gate:

- blocks that read under the SAME ceiling value run together;
- a block that needs another value waits until every holder of the current one has left, in arrival order;
- an old-path block (a caller that resolved the original `raised` / `held` before `install` and enters `_LOCK` after it)
  holds the gate ALONE, exactly as the old lock held it.

So no read in the process ever happens under a ceiling other than the one its own block asked for (the value it read
under when the lock ran one block at a time), and the constant is restored however a block ends. What a pair read does
inside its block, and every byte it reads and checks, is unchanged. Not installed (any other process), the module's own
lock runs as before. This file is not a producer file and not a worker build input.
"""

from __future__ import annotations

import collections
import contextlib
import threading
import time


class NestedCeilingConflict(RuntimeError):
    """Two holders of one ceiling each asked, inside their block, for another value: neither can wait for the other."""


def _reader():
    from carbon.scoring import inference_pair_evidence as reader

    return reader


class _Gate:
    """Holders of the pair reader's ceiling: any number at ONE value at once, never two values.

    ``hold(want_of)`` blocks until no holder reads under another value and every earlier waiter has gone first (arrival
    order), then holds ``want``: the first holder of a value sets the reader's constant to it, the last one out restores
    the value it found. A thread that already holds re-enters: at the same value it just nests; at another value it
    waits until it is the only holder (nobody new is let in meanwhile), sets that value and puts back the one it read
    under on the way out, exactly as one re-entrant lock did. Two such nested waits at once would wait for each other:
    the second raises `NestedCeilingConflict` instead (never a silent read under a value it did not ask for).

    ``acquire`` / ``release`` hold the gate ALONE (the old lock's own semantics, re-entrant): `install` puts them in
    `pair_read_bound._LOCK`, so a block of the original ``raised`` / ``held`` code sets and restores the constant itself
    with nobody else holding.
    """

    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._value = None  # the ceiling the holders read under; None: no holder
        self._found = None  # the reader's own value when the first holder came in
        self._depth = {}  # thread ident -> nesting depth
        self._queue = collections.deque()  # waiting tickets, arrival order
        # the one holder that is (or is waiting to be) alone, and how many alone-holds it has open
        self._upgrading = None
        self._lifts = 0

    # -- shared holds (the installed `held` / `raised`) -----------------------------------------------------------------

    @contextlib.contextmanager
    def hold(self, want_of):
        """Hold the ceiling ``want_of(value it would raise from)`` returns; yields the value read under inside."""
        reader = _reader()
        me = threading.get_ident()
        with self._cond:
            if self._depth.get(me):
                lifted, put_back = self._enter_nested(reader, me, want_of)
            else:
                lifted, put_back = False, None
                self._enter(reader, me, want_of, deadline=None)
            value = reader._MAX_BYTES
        try:
            yield value
        finally:
            with self._cond:
                if lifted:
                    reader._MAX_BYTES = self._value = put_back
                    self._drop_lift()
                self._leave(reader, me)

    def _enter(self, reader, me, want_of, *, deadline, alone=False):
        """Wait for this thread's turn; False on a passed ``deadline``. ``alone``: only into an empty gate, then nobody
        else comes in until it leaves (the old lock)."""
        ticket = object()
        self._queue.append(ticket)
        try:
            while True:
                base = reader._MAX_BYTES if self._value is None else self._found
                want = base if alone else want_of(base)
                if (
                    self._queue[0] is ticket
                    and self._upgrading is None
                    and (self._value is None or (not alone and self._value == want))
                ):
                    break
                if not self._wait(deadline):
                    return False
        finally:
            self._queue.remove(ticket)
            self._cond.notify_all()
        if self._value is None:
            self._found = reader._MAX_BYTES
            self._value = reader._MAX_BYTES = want
        self._depth[me] = 1
        if alone:
            self._upgrading, self._lifts = me, 1
        return True

    def _enter_nested(self, reader, me, want_of):
        # the constant itself, not `_value`: inside an alone-hold the original `raised` code may have set it directly
        current = reader._MAX_BYTES
        want = want_of(current)
        if want == current:
            self._depth[me] += 1
            return False, None
        self._be_alone(me, deadline=None)
        self._lifts += 1
        self._value = reader._MAX_BYTES = want
        self._depth[me] += 1
        return True, current

    def _be_alone(self, me, *, deadline):
        """Wait until this holder is the only one; nobody new comes in from here until its last alone-hold is put back
        (`_lifts` back at 0). False on a passed ``deadline``."""
        if self._upgrading not in (None, me):
            raise NestedCeilingConflict("pair_read_bound_nested_conflict")
        if self._upgrading is None:
            self._upgrading = me
            try:
                while set(self._depth) != {me}:
                    if not self._wait(deadline):
                        self._upgrading = None
                        self._cond.notify_all()
                        return False
            except BaseException:
                self._upgrading = None
                self._cond.notify_all()
                raise
        return True

    def _drop_lift(self):
        self._lifts -= 1
        if not self._lifts:
            self._upgrading = None

    def _leave(self, reader, me):
        self._depth[me] -= 1
        if not self._depth[me]:
            del self._depth[me]
        if not self._depth:
            reader._MAX_BYTES = self._found
            self._value = self._found = None
        self._cond.notify_all()

    def _wait(self, deadline):
        if deadline is None:
            self._cond.wait()
            return True
        left = deadline - time.monotonic()
        return left > 0 and (self._cond.wait(left) or time.monotonic() < deadline)

    # -- alone holds (the installed `_LOCK`: the original code's own lock) ----------------------------------------------

    def acquire(self, blocking=True, timeout=-1):
        """The old lock's ``acquire``: hold the gate alone (re-entrant); False if it could not by ``timeout``."""
        if not blocking:
            timeout = 0
        deadline = (
            None if timeout is None or timeout < 0 else time.monotonic() + timeout
        )
        reader = _reader()
        me = threading.get_ident()
        with self._cond:
            if self._depth.get(me):
                if not self._be_alone(me, deadline=deadline):
                    return False
                self._lifts += 1
                self._depth[me] += 1
                return True
            return self._enter(reader, me, None, deadline=deadline, alone=True)

    def release(self):
        reader = _reader()
        me = threading.get_ident()
        with self._cond:
            if not self._depth.get(me) or self._upgrading != me:
                raise RuntimeError("cannot release un-acquired lock")
            self._drop_lift()
            self._leave(reader, me)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()
        return False


_GATE = _Gate()


@contextlib.contextmanager
def held():
    """Read under the reader's own ceiling: nothing in this process reads the pair under a raised ceiling meanwhile
    (other blocks at the reader's own ceiling run alongside)."""
    with _GATE.hold(lambda value: value):
        yield


@contextlib.contextmanager
def raised(limit):
    """Read pairs under ``max(the reader's ceiling, limit)`` inside the block; the ceiling is restored after it. Blocks
    that read under the same value run alongside; another value waits (`_Gate`)."""
    if type(limit) is not int or limit < 1:
        raise ValueError("pair_read_bound_limit")
    with _GATE.hold(lambda value: max(value, limit)) as ceiling:
        yield ceiling


def install():
    """Point `pair_read_bound`'s ``held``, ``raised`` and ``_LOCK`` at the gate (idempotent; True once installed).

    Takes the module's own lock first, so a block already inside it leaves before anything changes. Called from a
    thread that is itself inside that lock, it installs nothing (False): a later call installs.
    """
    from carbon.scoring import pair_read_bound as bound

    old = bound._LOCK
    if old is _GATE:
        return True
    owned = getattr(old, "_is_owned", None)
    if owned is not None and owned():
        return False
    with old:
        if bound._LOCK is old:
            bound._LOCK = _GATE
            bound.held = held
            bound.raised = raised
    return bound._LOCK is _GATE
