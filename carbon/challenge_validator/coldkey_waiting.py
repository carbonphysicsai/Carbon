"""One waiting submission per coldkey (owner 14 Nov 2026, via the Lead: "1.0 and yes" to TE-B's estimate of 23:30 CST).

At SUBMIT, before anything is built or any intent is written, a door refuses a NEW official submission when a hotkey of
the SAME coldkey already has a submission WAITING on this door: queued, building, or built and not yet graded. The
per-round grading rule (`exam_cap`) is unchanged; this only stops a coldkey from stacking the build queue, where a
refusal at grading time would still have spent a whole build.

- The LIMIT is a value, per ``"<challenge> <version>"``, in `REGISTRY` (outside ``carbon/``, a values-only path):
  ``{"limit": <int >= 1>}``. No registry, no row or a malformed row = OFF (the door takes submissions as before).
- The COLDKEY of a hotkey is the door's OWN latest chain snapshot's (``snapshot.resolve(hotkey).coldkey``), never anything
  a miner sends. A SUBMITTER whose coldkey the snapshot cannot give is refused with the existing retry code
  ``allowance_group_unresolved`` (never counted as a new coldkey); a waiting task whose owner cannot be resolved counts
  for no coldkey.
- WAITING is read from the task views of the providers already open on this door (no provider is opened, no ledger lock
  taken): a task QUEUED, RUNNING or CANCEL_REQUESTED, or SUCCEEDED and still in the grader's pending list (built, no
  grade marker yet), unless the grade round found it NOT gradable now (`AutoGrader.stalled`: an owned task or verified
  attempt it cannot read), which would otherwise hold the coldkey for good. ANY terminal state frees the place: the round
  writes a marker for every grade it settles (graded, refused, wall or early stop, failed incl. an infra give-back).
- ATOMIC: on the live door every submit is already decided under the intake's one writer lock
  (`DirectRecipeIntake._write`); the guard's own lock, held from this check to the task's start (a just-started task is
  QUEUED in its view at once), keeps that true for any other caller.
- The submission's OWN task (a resend of the same recipe; the same task id) is never counted against it.
- Submissions already waiting when the rule is switched on are KEPT: nothing is cancelled or judged again.
- A read that cannot be made (the views changing too fast, no snapshot) never refuses: the door takes the submission as
  before (fail open), except the submitter-unresolved case above.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "coldkey_waiting_limit.json"
)
SCHEMA = "carbon.exam.coldkey-waiting-limit.v1"
CODE = "coldkey_submission_waiting"
UNRESOLVED = "allowance_group_unresolved"
#: Waiting states of a task view: queued or building.
_BUILDING = frozenset({"QUEUED", "RUNNING", "CANCEL_REQUESTED"})
#: Built, waiting for its grade while it has no grade marker (`AutoGrader.pending`).
_BUILT = "SUCCEEDED"

MESSAGE = (
    "One waiting submission per coldkey on this Challenge: a submission from a hotkey of this coldkey is already "
    "queued, building or waiting for its grade on this validator. Nothing was built or graded for this submission and "
    "it used none of your allowance. Submit again once that submission has its result."
)
UNRESOLVED_MESSAGE = (
    "The validator cannot yet match this hotkey to its coldkey in its latest chain snapshot, so it cannot take this "
    "submission yet. Nothing was built or graded for this submission and it used none of your allowance. Try again "
    "later."
)


def limit_for(challenge_id, version, *, path=None):
    """The registered limit of ``"<challenge_id> <version>"`` (an int >= 1), or None = OFF. Never raises."""
    try:
        document = json.loads(Path(REGISTRY if path is None else path).read_bytes())
        if type(document) is not dict or document.get("schema") != SCHEMA:
            return None
        row = (document.get("rows") or {}).get(f"{challenge_id} {version}")
        if type(row) is not dict or set(row) != {"limit"}:
            return None
        limit = row["limit"]
        if type(limit) is not int or limit < 1:
            return None
        return limit
    except Exception:  # noqa: BLE001 - OFF, never a failure of a submission
        return None


class Guard:
    """The door's guard: ``opened()`` -> the providers already open (``{hotkey: provider}``), ``pending()`` -> the grader's
    ungraded task ids, ``snapshot()`` -> the latest chain snapshot (or None), ``stalled()`` -> the task ids the grade round
    found not gradable now. Installed on the adapter by the receiver."""

    def __init__(self, *, opened, pending, snapshot, stalled=frozenset):
        self._opened, self._pending, self._snapshot = opened, pending, snapshot
        self._stalled = stalled
        #: held from the check to the task's start (`LeanRecipeAdapter.evaluate`): one submission decided at a time
        self.lock = threading.Lock()
        self._said_unreadable = False

    def _unreadable(self):
        """Fail open, said once (counts only): a wiring fault must never turn the rule off silently."""
        if not self._said_unreadable:
            self._said_unreadable = True
            try:
                from carbon.battery.intake import log

                log("coldkey_waiting_unreadable")
            except Exception:  # noqa: BLE001, S110 - the log is best effort
                pass

    def refusal(self, *, hotkey, task_id, limit):
        """``(code, message)`` when ``hotkey``'s NEW submission ``task_id`` must be refused now, else None."""
        snapshot = self._snapshot()
        if snapshot is None:
            return None  # no snapshot at all: the door's own signed-request checks decide, as before
        member = snapshot.resolve(hotkey)
        if member is None:
            return UNRESOLVED, UNRESOLVED_MESSAGE
        opened = self._opened()
        if not isinstance(opened, dict):
            self._unreadable()
            return None
        for _attempt in range(2):
            try:
                providers = tuple(opened.items())
                break
            except RuntimeError:  # opened or closed mid-read
                continue
        else:
            return None
        held, built = 0, []
        for owner, provider in providers:
            found = snapshot.resolve(owner)
            if found is None or found.coldkey != member.coldkey:
                continue  # another coldkey, or an owner that cannot be resolved (counts for no coldkey)
            try:
                views = tuple(getattr(provider, "_views", {}).items())
            except RuntimeError:
                return None
            for task, view in views:
                if task == task_id:
                    continue  # its own task (a resend): never counted against it
                state = getattr(getattr(view, "state", None), "value", None)
                if state in _BUILDING:
                    held += 1
                elif state == _BUILT:
                    built.append(task)
        if held < limit and built:
            # only now the grader's list: a built task holds the place while it waits for its grade
            try:
                pending, stalled = set(self._pending()), set(self._stalled())
            except Exception:  # noqa: BLE001 - fail open
                return None
            held += sum(1 for task in built if task in pending and task not in stalled)
        return (CODE, MESSAGE) if held >= limit else None


__all__ = ["CODE", "MESSAGE", "REGISTRY", "SCHEMA", "Guard", "limit_for"]
