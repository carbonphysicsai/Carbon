"""Resume the crown decisions an operator pause withheld (`operator_pause`).

While crowns are paused, `BankPromotion.consider_private` files each crown-changing contender as paused
(`PoolStore.record_crown_paused`) and the incumbent stays. Once the flag is gone this sweep makes those decisions
again, from the filed evaluations, with no regrade, no exam-cap slot and no Ladder document: the contender's repeat
grade is the only extra grade, uncounted, as for any crown change.

Rules (Validator, 2026-10-29):

- oldest first, each against the incumbent as it is at that moment, so the outcome is what it would have been without
  the pause;
- a resolution is write-once, so a crash mid-sweep resumes where it stopped and no contender is decided twice (a
  contender that is already the incumbent resolves without a decision);
- a record whose exam is no longer the active one (a rotation during the pause) resolves to UNAVAILABLE
  ``exam_rotated_during_pause``, never a crown;
- a decision that could not be MADE is never resolved (Validator, 2026-10-31): an UNAVAILABLE outcome (the host could
  not rebuild or repeat; a margin or a king's mean not measured) or a FAILED_INFRA one (a host-fault mismatch) says nothing
  about the contender, so the record stays UNRESOLVED and is retried, at most once per epoch (a persistent fault never
  burns GPU every tick), with a typed alert after `ALERT_AFTER` failed attempts. Only decided outcomes resolve
  (FIRST_INCUMBENT, CHALLENGER, INCUMBENT_KEEPS, NO_WINNER, including ``unstable_across_seeds``).
- ADMISSION ORDER IS ENFORCED AT THE DOOR TOO: `BankPromotion.consider_private` files a crown-changing contender as
  queued (``queued_behind_undecided_crown``, no decision) whenever an earlier record of the Challenge is unresolved, so a
  later candidate cannot be crowned in the gap while an earlier one waits (the sweep alone did not stop that);
- AT MOST ONE decision that ran GPU work (a repeat grade or averaging rebuilds, `SpendWatch`) per tick: the sweep
  stops after it, so a live grade runs between two of them (Validator 5 Nov: 381 queued challengers must not hold live
  grades for hours); cheap no-crown comparisons go on in the same tick;
- A STUCK RECORD KEEPS ITS PLACE AND IS SKIPPED (over-broad rules audit #14, owner 20 Nov 2026: only exam integrity,
  hidden values or funds justify a gate). A record that could not be decided (an UNAVAILABLE / FAILED_INFRA outcome, a
  raising `reconsider`, a refusal, a menu-D hold, a missing margin row) or is inside its retry spacing stays UNRESOLVED
  and first in the order, and the sweep goes on to the later records in the same tick. It still holds back every later
  decision that would CHANGE the crown: `BankPromotion.consider_private` queues such a contender
  (``queued_behind_undecided_crown``, no repeat or rebuild spent) while any earlier record is unresolved, so the crown
  still moves strictly in admission order, each change against the incumbent of its moment. What goes on is only a
  later decision that changes no crown (the incumbent keeps it, or no winner): its outcome cannot depend on the stuck
  record, because a contender that does not beat the king by the margin cannot beat a king who did. Once the stuck
  record resolves, the contenders queued behind it are decided in order against the king of that moment. A queued
  contender is not reconsidered every tick for nothing: while the records ahead of it and the king are unchanged its
  answer is the same, so it waits (`queued_spaced`) up to `RETRY_SECONDS`. The alert still names, when it is filed,
  the later decisions the stuck one may hold (code ``crown_pause_blocked_by_undecided``, ``waiting`` counts them).
- A CONTENDER THAT NEVER MET THE KING is contended once he is regraded (Lead 5 Nov): a record whose king has no
  evaluation on its key (`PoolStore.awaits_incumbent_regrade`; filed PENDING_CONTENTION by the live path on
  ``incumbent_regrade_required``) is skipped, not tried, not counted and never resolved, every tick until the regrade,
  so the first tick after it contends it, in filing order, against the king of that moment. It holds nobody back: a later
  record that can be decided is (its key is one the king was regraded on, which this record's is not).
"""

from __future__ import annotations

from . import crown_hold, koth_journal, operator_pause
from .bank_promotion import (
    CROWN_HELD,
    CROWN_QUEUED,
    CROWNS_PAUSED,
    FAILED_INFRA,
    INCUMBENT_REGRADE_REQUIRED,
    UNAVAILABLE,
)
from .crown_common import REBUILD_IN_PROGRESS
from .crown_official import (
    CROWN_CONFIRMATION_UNAVAILABLE,
    CROWN_CONFIRMATION_UNSET,
    CROWN_MARGIN_UNSET,
)

#: The reasons a crown change waits in its place for a registered value or a filed record, nothing spent (`sweep`).
WAITING_REASONS = (
    CROWN_QUEUED,
    CROWN_MARGIN_UNSET,
    CROWN_CONFIRMATION_UNSET,
    CROWN_CONFIRMATION_UNAVAILABLE,
)

ROTATED = "exam_rotated_during_pause"
ALREADY_INCUMBENT = "already_incumbent"
#: Outcomes that are no decision about the contender: kept unresolved and retried.
UNDECIDED = frozenset({UNAVAILABLE, FAILED_INFRA})
#: One reward epoch in seconds (360 blocks of 12 s, the weights cadence).
EPOCH_SECONDS = 360 * 12
#: The retry spacing of a failed (undecided) decision or king-upkeep step: an engineering value, not a science one. It
#: was one epoch; a door's whole queue then waited up to 72 min behind one passing fault (Deploy 5 Nov); then 15 min
#: (Lead and Validator-2, 5 Nov). 5 min (over-broad rules audit #6/#14: the spacing V2 ruled for automatic retries)
#: still never burns GPU every tick, and a stuck record no longer holds the decisions that change no crown (`sweep`).
RETRY_SECONDS = 5 * 60
#: The store-clock time this process first looked at each store (`spaced`): an attempt filed before it was made by an
#: EARLIER process (before a deploy or restart), whose code may have been the reason it failed.
_FIRST_SEEN = {}
#: The store-clock time the sitting king last CHANGED in this process (`king_changed`: regraded, rebuilt, his crown
#: mean filed): a decision that failed before it may succeed now, so it is due at once.
_KING_CHANGED = {}
#: A contender queued behind a stuck record or waiting for its margin row (`CROWN_QUEUED` / `CROWN_MARGIN_UNSET` from the
#: sweep's own `reconsider`), per store: its record
#: -> (store-clock time, the unresolved records ahead of it then). In-process only: after a restart it is tried at once.
_QUEUED = {}


def _store_key(store):
    return str(getattr(store, "path", id(store)))


def king_changed(store):
    """Note that the sitting king can be met differently now (his regrade or rebuild on this exam landed, or his crown
    mean was filed): every waiting decision that failed before this is retried at once, not after its spacing (Lead 5
    Nov: Motor's queue sat behind the spacing after the mean filed). In-process: the king's upkeep runs in the same
    receiver, just before the sweep; after a restart `spaced` already retries at once.
    """
    _KING_CHANGED[_store_key(store)] = store.clock()


def spaced(store, attempts, last):
    """Whether a failed decision is still inside its retry spacing (`RETRY_SECONDS`). An attempt filed before THIS
    process first looked at the store never holds it back: the first round after a switch tries again at once (Lead 5
    Nov: no wait after a code change); nor does one filed before the king last changed (`king_changed`). Attempts this
    process makes after both are spaced."""
    now = store.clock()
    key = _store_key(store)
    # recorded on the FIRST check, attempt or not, so every failure this process makes comes after it
    first = _FIRST_SEEN.setdefault(key, now)
    changed = _KING_CHANGED.get(key)
    if (
        not attempts
        or last is None
        or last < first
        or (changed is not None and last < changed)
    ):
        return False
    return now - last < RETRY_SECONDS


def _ahead(pending, place, awaits):
    """The unresolved records filed before ``pending[place]`` that can hold it back (as `consider_private` counts them:
    a record that waits for the king's regrade on its own key holds nobody)."""
    return frozenset(
        (r["submission_id"], r["evaluation_key"])
        for r in pending[:place]
        if awaits is None or not awaits(r)
    )


def _queued_key(store, record):
    return (_store_key(store), record["submission_id"], record["evaluation_key"])


def queued_spaced(store, record, ahead):
    """Whether ``record`` was queued (`CROWN_QUEUED`, `CROWN_MARGIN_UNSET`) by this process with the same unresolved
    records ``ahead`` of it, the king unchanged since (`king_changed`) and less than `RETRY_SECONDS` ago: then its answer
    is the same and it is not reconsidered."""
    seen = _QUEUED.get(_queued_key(store, record))
    if seen is None:
        return False
    when, before = seen
    changed = _KING_CHANGED.get(_store_key(store))
    return (
        before == ahead
        and (changed is None or when >= changed)
        and store.clock() - when < RETRY_SECONDS
    )


def due(store, *, current_exam):
    """Whether `sweep` would make or retry a decision now (an idle door runs a round only then): an unresolved record
    that is the incumbent's own or of a rotated exam (resolved at once), or one that is not held, not waiting for the
    king's regrade, not inside its retry spacing and not queued with nothing changed (`queued_spaced`).
    """
    if operator_pause.crowns_paused(store.path.parent):
        return False
    incumbent = store.incumbent() or {}
    awaits = getattr(store, "awaits_incumbent_regrade", None)
    pending = store.paused_crowns("pack")
    for place, record in enumerate(pending):
        if (
            incumbent.get("model_id") == record["submission_id"]
            or record["exam"] != current_exam
        ):
            return True  # resolved at once, without a grade
        if awaits is not None and awaits(record):
            continue
        if crown_hold.held(store.path.parent, record["submission_id"]):
            continue
        attempts, last = store.crown_pause_attempts(
            record["submission_id"], record["evaluation_key"]
        )
        if spaced(store, attempts, last):
            continue
        if queued_spaced(store, record, _ahead(pending, place, awaits)):
            continue
        return True
    return False


#: Failed attempts after which a typed alert is filed.
ALERT_AFTER = 3


def _failed_loudly(store, record, error, *, waiting, queued):
    """A `reconsider` that RAISED (a StateError such as ``evaluation_source_changed``, an unreadable role, a missing retained
    entry...) used to end the tick with NO journal line, NO attempt and NO alert, every tick, and the sweep stops at the oldest
    record, so every later one waited with it (14 Nov: three records sat silently on a king evaluation under another source pin).
    Now it says so: one journal line (record id, exception type, closed code: never the message), a failed attempt counted so the
    retry is spaced (`spaced`) and the typed alert follows after `ALERT_AFTER` attempts exactly as for an undecided outcome. The
    record is not resolved and keeps its place; the sweep goes on to the later records (`sweep`).
    """
    submission_id, key = record["submission_id"], record["evaluation_key"]
    code = getattr(error, "code", None)
    code = (
        code
        if type(code) is str and 0 < len(code) <= 128 and code.isprintable()
        else ""
    )
    name = type(error).__name__
    attempt = f"EXCEPTION:{name}:{code}" if code else f"EXCEPTION:{name}"
    koth_journal.note(
        "crown_sweep_reconsider_failed",
        submission_id=submission_id,
        error=name,
        code=code,
    )
    try:
        failed = store.note_crown_pause_attempt(submission_id, key, attempt)
        if failed >= ALERT_AFTER:
            store.record_crown_pause_alert(
                submission_id,
                key,
                failed,
                attempt,
                waiting=waiting,
                queued=[r["submission_id"] for r in queued],
            )
    except Exception:  # noqa: BLE001 - the journal line is the record
        return


def sweep(store, reconsider, *, kind, current_exam):
    """Make every unresolved paused decision of ``kind`` again; returns ``[(submission_id, code)]`` resolved now.

    ``reconsider(record)`` is the path's decision (`consider_private` with its repeat grade); ``current_exam`` is the
    digest of the exam the path serves now. The sweep does nothing while crowns are paused again. A decision that could
    not be made (an exception, a refusal, an undecided outcome) or is spaced or held stays unresolved in its place and
    the sweep goes on: a later decision that would change the crown is queued behind it by `consider_private` itself, so
    the crown still moves in admission order (module docstring). The tick ends after a decision that ran GPU work.
    """
    if operator_pause.crowns_paused(store.path.parent):
        return []
    resolved = []
    pending = store.paused_crowns(kind)
    awaits = getattr(store, "awaits_incumbent_regrade", None)
    # records resolved earlier in this tick: they hold nobody back any more
    gone = set()
    for place, record in enumerate(pending):
        submission_id, key = record["submission_id"], record["evaluation_key"]
        outcome = None
        incumbent = store.incumbent() or {}
        if incumbent.get("model_id") == submission_id:
            code = ALREADY_INCUMBENT
        elif record["exam"] != current_exam:
            code = "UNAVAILABLE:" + ROTATED
        elif awaits is not None and awaits(record):
            continue  # no contention possible until the king's regrade on this key: no GPU, no attempt, no alert
        elif crown_hold.held(store.path.parent, submission_id):
            continue  # a menu-D crown held for the operator's release: no GPU, no attempt; it keeps its place
        else:
            attempts, last = store.crown_pause_attempts(submission_id, key)
            if spaced(store, attempts, last):
                continue  # tried within RETRY_SECONDS already: no GPU burned again before then; it keeps its place
            ahead = _ahead(pending, place, awaits) - gone
            if queued_spaced(store, record, ahead):
                continue  # queued behind the same stuck records and the same king: the same answer, not asked again
            try:
                outcome = reconsider(record)
            except Exception as error:  # noqa: BLE001 - spaced retry
                _failed_loudly(
                    store,
                    record,
                    error,
                    waiting=len(pending) - place - 1,
                    queued=pending[place + 1 :],
                )
                continue  # unresolved, in its place; a later crown change is queued behind it (`consider_private`)
            koth_journal.contention(
                "sweep", submission_id, outcome, incumbent.get("model_id"), store=store
            )
            if type(outcome) is not dict or "outcome" not in outcome:
                continue  # a refusal ({"error": ...}) is not a decision: unresolved, in its place
            if outcome.get("reason") == CROWNS_PAUSED:
                break  # paused again: nothing more this tick
            if outcome.get("reason") in WAITING_REASONS:
                # a crown change behind an unresolved earlier record, or with no margin row or confirmation value or record
                # yet: it waits in its place,
                # nothing spent, and is not asked again until the records ahead of it or the king change, or for
                # `RETRY_SECONDS` (`queued_spaced`)
                _QUEUED[_queued_key(store, record)] = (store.clock(), ahead)
                continue
            _QUEUED.pop(_queued_key(store, record), None)
            if outcome.get("reason") == CROWN_HELD:
                continue  # held for the operator's release: unresolved, in its place
            if outcome.get("reason") == REBUILD_IN_PROGRESS:
                # a stepwise decision ran ONE new rebuild (kept) and stopped: not a failure, so no attempt is counted, no spacing
                # applies and nothing is alerted; the record stays unresolved and the next tick resumes it. The tick ends here
                # (it ran GPU work), so a live grade runs before the next rebuild.
                break
            if outcome.get("reason") == INCUMBENT_REGRADE_REQUIRED:
                continue  # the king lost his evaluation on this key between the two reads: still pending
            code = f"{outcome['outcome']}:{outcome.get('reason')}"
            if outcome["outcome"] in UNDECIDED:
                failed = store.note_crown_pause_attempt(submission_id, key, code)
                if failed >= ALERT_AFTER:
                    store.record_crown_pause_alert(
                        submission_id,
                        key,
                        failed,
                        code,
                        waiting=len(pending) - place - 1,
                        queued=[r["submission_id"] for r in pending[place + 1 :]],
                    )
                if outcome.get("spent"):
                    break  # it ran GPU work: the next decision waits for the next tick
                continue  # not a decision: unresolved in its place, retried after RETRY_SECONDS (or once the king changes)
        store.resolve_crown_pause(submission_id, key, code)
        gone.add((submission_id, key))
        resolved.append((submission_id, code))
        if type(outcome) is dict and outcome.get("spent"):
            # it ran GPU work (a repeat grade or averaging rebuilds): the next decision waits for the next tick, so a
            # live grade runs between two of them (Validator 5 Nov); cheap no-crown comparisons go on in one tick
            break
    return resolved
