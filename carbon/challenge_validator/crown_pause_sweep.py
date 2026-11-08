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
- the sweep stops at an undecided record, so a persistently failing OLDEST record holds every later paused decision of
  its Challenge until it resolves (each is decided against the incumbent of its moment). The alert says so: when
  decisions are queued behind it, its code is ``crown_pause_blocked_by_undecided`` and ``waiting`` counts them (as of
  the filing).
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

ROTATED = "exam_rotated_during_pause"
ALREADY_INCUMBENT = "already_incumbent"
#: Outcomes that are no decision about the contender: kept unresolved and retried.
UNDECIDED = frozenset({UNAVAILABLE, FAILED_INFRA})
#: One reward epoch in seconds (360 blocks of 12 s, the weights cadence).
EPOCH_SECONDS = 360 * 12
#: The retry spacing of a failed (undecided) decision or king-upkeep step: an engineering value, not a science one. It
#: was one epoch; a door's whole queue then waited up to 72 min behind one passing fault (Deploy 5 Nov). 15 min (Lead and
#: Validator-2, 5 Nov) still never burns GPU every tick.
RETRY_SECONDS = 15 * 60
#: The store-clock time this process first looked at each store (`spaced`): an attempt filed before it was made by an
#: EARLIER process (before a deploy or restart), whose code may have been the reason it failed.
_FIRST_SEEN = {}
#: The store-clock time the sitting king last CHANGED in this process (`king_changed`: regraded, rebuilt, his crown
#: mean filed): a decision that failed before it may succeed now, so it is due at once.
_KING_CHANGED = {}


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


#: Failed attempts after which a typed alert is filed.
ALERT_AFTER = 3


def sweep(store, reconsider, *, kind, current_exam):
    """Make every unresolved paused decision of ``kind`` again; returns ``[(submission_id, code)]`` resolved now.

    ``reconsider(record)`` is the path's decision (`consider_private` with its repeat grade); ``current_exam`` is the
    digest of the exam the path serves now. The sweep does nothing while crowns are paused again, and stops at a
    decision that could not be made (an exception or a refusal), leaving it unresolved for the next tick so no
    later contender is decided ahead of it."""
    if operator_pause.crowns_paused(store.path.parent):
        return []
    resolved = []
    pending = store.paused_crowns(kind)
    awaits = getattr(store, "awaits_incumbent_regrade", None)
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
            break  # a menu-D crown held for the operator's release: no GPU, no attempt; nothing later decided ahead
        else:
            attempts, last = store.crown_pause_attempts(submission_id, key)
            if spaced(store, attempts, last):
                break  # tried within RETRY_SECONDS already: no GPU is burned again before then
            try:
                outcome = reconsider(record)
            except Exception:  # noqa: BLE001 - left unresolved, retried next tick
                break
            koth_journal.contention(
                "sweep", submission_id, outcome, incumbent.get("model_id"), store=store
            )
            if type(outcome) is not dict or "outcome" not in outcome:
                break  # a refusal ({"error": ...}) is not a decision
            if outcome.get("reason") in (CROWNS_PAUSED, CROWN_QUEUED, CROWN_HELD):
                break  # paused again, or an earlier record is still undecided (cannot happen to the oldest)
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
                break  # not a decision: stays unresolved, retried after RETRY_SECONDS (or at once once the king changes)
        store.resolve_crown_pause(submission_id, key, code)
        resolved.append((submission_id, code))
        if type(outcome) is dict and outcome.get("spent"):
            # it ran GPU work (a repeat grade or averaging rebuilds): the next decision waits for the next tick, so a
            # live grade runs between two of them (Validator 5 Nov); cheap no-crown comparisons go on in one tick
            break
    return resolved
