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

from . import koth_journal, operator_pause
from .bank_promotion import (
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
#: One reward epoch in seconds (360 blocks of 12 s, the weights cadence): an engineering retry spacing, not a science value.
EPOCH_SECONDS = 360 * 12
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
        incumbent = store.incumbent() or {}
        if incumbent.get("model_id") == submission_id:
            code = ALREADY_INCUMBENT
        elif record["exam"] != current_exam:
            code = "UNAVAILABLE:" + ROTATED
        elif awaits is not None and awaits(record):
            continue  # no contention possible until the king's regrade on this key: no GPU, no attempt, no alert
        else:
            attempts, last = store.crown_pause_attempts(submission_id, key)
            if attempts and store.clock() - last < EPOCH_SECONDS:
                break  # tried this epoch already: no GPU is burned again before the next one
            try:
                outcome = reconsider(record)
            except Exception:  # noqa: BLE001 - left unresolved, retried next tick
                break
            koth_journal.contention(
                "sweep", submission_id, outcome, incumbent.get("model_id")
            )
            if type(outcome) is not dict or "outcome" not in outcome:
                break  # a refusal ({"error": ...}) is not a decision
            if outcome.get("reason") in (CROWNS_PAUSED, CROWN_QUEUED):
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
                break  # not a decision: stays unresolved, retried after the epoch
        store.resolve_crown_pause(submission_id, key, code)
        resolved.append((submission_id, code))
    return resolved
