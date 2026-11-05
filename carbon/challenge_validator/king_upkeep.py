"""The receiver keeps its own king comparable on its current exam, with no operator step (owner via Lead, 5 Nov).

When the door's pack (or judge) changes, the sitting king's grades are on the previous exam, so every challenger on the
new one meets ``incumbent_regrade_required`` and waits as PENDING_CONTENTION (`lean_recipe_retention._file_if_paused`).
At the start of every auto-grade tick (`AutoGrader.run_once`, before the crown sweep and before any new grade) `step`:

1. REGRADE: if any pending challenger on the current pack is waiting because the king has no evaluation on its key,
   the king's retained origin entry is regraded on the current pack through the receiver's own path
   (`DirectIntake.regrade_result` -> `regrade_retained_entry`: uncounted, exam-cap kind REGRADE, filed under the
   challengers' key). The sweep that follows in the same tick contends every waiting challenger, in filing order.
2. RE-MEASURE (crown averaging on): if the king has an evaluation on the current exam but no mean (and no unstable
   flag) filed on that key, ONE crown rebuild runs per tick (`remeasure_incumbent_pack(stepwise=True)`, each kept in the
   pool store), so live grades run between them; the tick that finds them all done files the mean on that key.
   Meanwhile crown-changing challengers wait as KING_UNMEASURED (queued, retried, never dropped).

A step that fails (infrastructure, an entry that cannot be found, a regrade that lands on another key) is retried at
most once per epoch (`crown_pause_sweep.EPOCH_SECONDS`: a persistent fault never burns GPU every tick) with a journal
line and an operator alert after `ALERT_AFTER` failures. It never raises into the grading loop, never counts a slot,
and decides no crown itself. DEVELOPMENT / TESTNET only.
"""

from __future__ import annotations

from . import koth_journal
from .crown_pause_sweep import ALERT_AFTER, EPOCH_SECONDS

REGRADE = "regrade"
REMEASURE = "remeasure"


def _waiting(pool, exam):
    """The pending records on the current exam that wait for the king's regrade, oldest first."""
    awaits = getattr(pool, "awaits_incumbent_regrade", None)
    if awaits is None:
        return []
    return [r for r in pool.paused_crowns("pack") if r["exam"] == exam and awaits(r)]


def _king_key_on(pool, king, exam):
    """The evaluation key of the king's latest evaluation on ``exam``, or None."""
    key = None
    for body in pool.private_evaluation_bodies():
        evidence = body.get("evidence") or {}
        if (
            body.get("submission_id") == king
            and evidence.get("evaluation_pack_digest") == exam
        ):
            key = body.get("evaluation_key")
    return key


def king_origin_entry(pool, root, king):
    """The king's retained origin entry (the one his regrade and his rebuilds run from), or None."""
    from .recontend import _origin_entry, _provenance

    provenance = _provenance(root)
    for body in reversed(pool.private_evaluation_bodies()):
        if body.get("submission_id") != king:
            continue
        entry = _origin_entry(
            root, king, (body.get("evidence") or {}).get("entry_id"), provenance
        )
        if entry is not None:
            return entry
    return None


#: `file_stranded` outcomes: the check was made (or can never apply: no king), so it is not tried again this start; or it
#: could not be made now and is tried again (`STRANDED_RETRY_SECONDS` later, so a failing check never holds the host lock
#: every poll).
STRANDED_DONE = "DONE"
STRANDED_RETRY = "RETRY"
STRANDED_RETRY_SECONDS = 60.0


def file_stranded(root, pool_store, discovery):
    """Queue, in grading order, every challenger on the current exam that was graded while the king could not be met
    and was never filed (`recontend.file`). Returns ``(STRANDED_DONE | STRANDED_RETRY, filed count)``. Never raises.

    Every attempt writes ONE journal line, ``recontend_checked``, whatever it found (Deploy 5 Nov 09:3x: Motor and RB
    filed nothing and said nothing): its state, the counts filed and skipped, or the refusal code, or ``no_exam`` when
    the door's discovery names no evaluation pack."""
    from . import recontend

    exam = getattr(discovery, "evaluation_pack_digest", None)
    if exam is None:
        koth_journal.note("recontend_checked", state=STRANDED_RETRY, code="no_exam")
        return STRANDED_RETRY, 0
    try:
        out = recontend.file(root, pool_store, exam, apply=True)
    except recontend.RecontendRefused as refused:
        # no king yet: nothing can be stranded behind one, so the check is done; anything else is tried again
        state = STRANDED_DONE if refused.code == "no_incumbent" else STRANDED_RETRY
        koth_journal.note("recontend_checked", state=state, code=refused.code)
        return state, 0
    except Exception as error:  # noqa: BLE001
        koth_journal.note(
            "recontend_checked",
            state=STRANDED_RETRY,
            code=str(getattr(error, "code", None) or type(error).__name__),
        )
        return STRANDED_RETRY, 0
    koth_journal.note(
        "recontend_checked",
        state=STRANDED_DONE,
        incumbent=out["king"],
        filed=len(out["filed"]),
        skipped=len(out["skipped"]),
    )
    return STRANDED_DONE, len(out["filed"])


def _due(pool, king, exam, step):
    attempts, last = pool.king_upkeep_attempts(king, exam, step)
    return not attempts or pool.clock() - last >= EPOCH_SECONDS


def _failed(pool, king, exam, step, code):
    failed = pool.note_king_upkeep_attempt(king, exam, step, code)
    koth_journal.note(
        "king_upkeep_failed", step=step, incumbent=king, code=code, attempts=failed
    )
    if failed >= ALERT_AFTER:
        koth_journal.note(
            "operator_alert",
            code="king_upkeep_" + step + "_failing",
            action="check_validator_host",
            incumbent=king,
            attempts=failed,
            last_code=code,
        )
    return {"step": step, "state": "FAILED", "code": code}


def step(pool, intake, *, root, artifacts, entries, active=None):
    """One upkeep step for this tick (see the module text); returns what it did, or None when nothing was due."""
    try:
        return _step(pool, intake, root, artifacts, entries, active)
    except Exception as error:  # noqa: BLE001 - upkeep never breaks the grading loop
        koth_journal.note("king_upkeep_error", type=type(error).__name__)
        return {"step": None, "state": "ERROR", "code": type(error).__name__}


def due(pool, intake, *, active=None):
    """Whether `step` would do something this tick: its own gates (`_plan`), read-only, no work. Head H4a asks this
    (`AutoGrader.has_work`): an idle door's grade round never takes the host's grading lock, so a round must run
    whenever the king's upkeep is due, even with no task pending. On doubt, True: the round then runs `step`.
    """
    try:
        return _plan(pool, intake, active) is not None
    except Exception:  # noqa: BLE001
        # doubt runs the round; the upkeep is never skipped
        return True


def _plan(pool, intake, active):
    """``(step, king, exam, waiting, key)`` for the step due now, or None. Read-only: `due` and `_step` share it."""
    if pool is None or not hasattr(pool, "king_upkeep_attempts"):
        return None
    king = (pool.incumbent() or {}).get("model_id")
    exam = getattr(intake.adapter.discovery, "evaluation_pack_digest", None)
    if king is None or exam is None:
        return None
    waiting = _waiting(pool, exam)
    if waiting:
        if not _due(pool, king, exam, REGRADE):
            return None
        return REGRADE, king, exam, waiting, None
    if active is None:
        return None
    rule = getattr(active, "rule", None)
    challenge = getattr(intake.adapter, "challenge_id", None)
    if (
        rule is not None
        and challenge is not None
        and rule.margin_for(challenge) is None
    ):
        # averaging only where margin_N is registered at the configured N (Validator 06:49); the comparisons there say
        # crown_average_margin_unregistered in their journal line
        return None
    key = _king_key_on(pool, king, exam)
    if (
        key is None
        or pool.crown_mean(king, key) is not None
        or pool.crown_average_unstable(king, key)
        or not _due(pool, king, exam, REMEASURE)
    ):
        return None
    return REMEASURE, king, exam, waiting, key


def _step(pool, intake, root, artifacts, entries, active):
    plan = _plan(pool, intake, active)
    if plan is None:
        return None
    which, king, exam, waiting, key = plan
    if which == REGRADE:
        entry = king_origin_entry(pool, root, king)
        if entry is None:
            return _failed(pool, king, exam, REGRADE, "king_entry_unresolved")
        koth_journal.note(
            "king_regrade_started", incumbent=king, waiting=len(waiting), exam=exam
        )
        try:
            regraded = intake.regrade_result(
                entry,
                artifact_directory=artifacts,
                entry_directory=entries,
                promotion=pool,
            )
        except Exception as error:  # noqa: BLE001
            return _failed(
                pool,
                king,
                exam,
                REGRADE,
                str(getattr(error, "code", None) or error or type(error).__name__),
            )
        state = (
            regraded.get("private_evaluation_state") if type(regraded) is dict else None
        )
        if state != "BOUND_DEVELOPMENT_ONLY":
            # The grade itself stopped (it returns its typed reason instead of raising, e.g. the pack's
            # leg_minimum_platform_mismatch): that reason, never the key post-check (Deploy 5 Nov 10:5x).
            reason = (
                regraded.get("private_evaluation_reason")
                if type(regraded) is dict
                else None
            )
            return _failed(
                pool,
                king,
                exam,
                REGRADE,
                f"regrade_unbound:{reason or state or type(regraded).__name__}",
            )
        if pool.awaits_incumbent_regrade(waiting[0]):
            # the king's new grade is not on the challengers' key: a real difference for people to look at
            return _failed(pool, king, exam, REGRADE, "king_regrade_key_differs")
        koth_journal.note("king_regraded", incumbent=king, waiting=len(waiting))
        return {"step": REGRADE, "state": "DONE"}
    entry = king_origin_entry(pool, root, king)
    if entry is None:
        return _failed(pool, king, exam, REMEASURE, "king_entry_unresolved")
    from . import lean_recipe_retention as retention

    before = _kept_rebuilds(pool, king, key)
    try:
        outcome = retention.remeasure_incumbent_pack(
            intake.adapter,
            pool,
            submission_id=king,
            evaluation_key=key,
            entry_id=entry,
            artifact_directory=artifacts,
            entry_directory=entries,
            stepwise=True,
        )
    except Exception as error:  # noqa: BLE001
        return _failed(
            pool,
            king,
            exam,
            REMEASURE,
            str(getattr(error, "code", None) or error or type(error).__name__),
        )
    state = (outcome or {}).get("outcome")
    if state == retention.REMEASURE_IN_PROGRESS:
        if _kept_rebuilds(pool, king, key) == before:
            return _failed(pool, king, exam, REMEASURE, "crown_rebuild_not_measured")
        koth_journal.note(
            "king_remeasure_step", incumbent=king, kept=before + 1, evaluation_key=key
        )
        return {"step": REMEASURE, "state": "IN_PROGRESS"}
    if pool.crown_mean(king, key) is not None or pool.crown_average_unstable(king, key):
        koth_journal.note(
            "king_remeasured", incumbent=king, outcome=state, evaluation_key=key
        )
        return {"step": REMEASURE, "state": "DONE", "outcome": state}
    return _failed(
        pool,
        king,
        exam,
        REMEASURE,
        f"{state}:{(outcome or {}).get('reason')}",
    )


def _kept_rebuilds(pool, king, key):
    """How many of the king's crown rebuilds on ``key`` are kept (progress of a stepwise re-measure)."""
    with pool.db() as db:
        rows = db.execute(
            "SELECT body FROM operations WHERE kind='crown_rebuild.v1'"
        ).fetchall()
    import json

    count = 0
    for (raw,) in rows:
        body = json.loads(raw)
        if body.get("submission_id") == king and body.get("evaluation_key") == key:
            count += 1
    return count
