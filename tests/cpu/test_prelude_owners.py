"""V2's ruling B (17 Nov 2026): the incumbent's steps take only the owners whose ledgers they touch, never every owner.

Live 116 (17:25Z): 6 build rounds, 76 waiting builds over 76 hotkeys, yet building_now 1 and grading_now 0. The
incumbent's steps (king upkeep, crown sweep, paused crowns, due retries) took EVERY owner (`OwnerClaims.exclusive`):
every new build and grade was refused and a grade round sat on its lane until every in-flight build, the A100's
included, had ended. That exclusivity protects only the per-owner ledger lease (non-blocking: two rounds of one owner
fail the second); the integrity guard is `Sequencer.exclusive` (no grade in flight while the steps run), which stays.

Now (`AutoGrader._prelude_owners_held`): the king's owner, the crown average's host owner, each paused crown's and each
due retry's owner are taken without waiting; every other miner keeps building. A touched owner busy elsewhere: skipped,
asked again next round; after `UPKEEP_DEFER_MAX_SECONDS` every owner, as before. Unreadable owners: every owner.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import auto_grade, auto_retry, grade_sequencer
from carbon.challenge_validator.crown_average import HOST_OWNER

KING, KING_OWNER = "rtsk_" + "k" * 64, "5King"
PAUSED, PAUSED_OWNER = "rtsk_" + "p" * 64, "5Paused"
OWNERS = {KING: KING_OWNER, PAUSED: PAUSED_OWNER}


class _Pool:
    def incumbent(self):
        return {"model_id": KING}

    def paused_crowns(self, kind=None):
        return [{"submission_id": PAUSED, "kind": "pack"}]


def _grader(claims, seen, owners=OWNERS):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.sequencer = grade_sequencer.Sequencer()
    grader.owner_claims = claims
    grader.root = "/nonexistent-grader-root"
    grader.chain_degraded = lambda: False
    grader.pending = list
    grader._pool = lambda: _Pool()
    grader.intake = SimpleNamespace(
        adapter=SimpleNamespace(
            owner=owners.get,
            contract_digest="sha256:" + "c" * 64,
            ledger=SimpleNamespace(
                owned_outcome=lambda contract, task: None,
                admitted_owner=lambda task: None,
            ),
        )
    )
    grader._prelude_due = lambda pending: True
    grader.pool_store = "/nonexistent-pool-store"
    grader._stranded_filed = True  # the start-up filing is made (its own test below)

    def king():
        # what the steps can do meanwhile: other miners claim, the touched owners cannot
        seen.append(
            {
                "other_miner": claims.try_claim("5OtherMiner"),
                "king_owner": claims.try_claim(KING_OWNER),
                "host": claims.try_claim(HOST_OWNER),
                "paused_owner": claims.try_claim(PAUSED_OWNER),
            }
        )
        claims.release("5OtherMiner")

    grader._settle_queue_places = lambda: None
    grader._upkeep_deferred = lambda: False
    grader._king_upkeep = king
    grader._resume_paused_crowns = lambda: None
    grader._apply_due_retries = lambda idle: None
    return grader


@pytest.fixture(autouse=True)
def _no_due_retries(monkeypatch):
    monkeypatch.setattr(auto_retry, "due", lambda root, **kwargs: [])


def test_the_steps_take_only_the_owners_they_touch(monkeypatch):
    claims = grade_sequencer.OwnerClaims()
    assert claims.try_claim(
        "5BuildingOnTheA100"
    )  # another miner's build in flight: never waited for
    seen = []
    grader = _grader(claims, seen)
    assert grader._run_once() is None
    assert seen == [
        {"other_miner": True, "king_owner": False, "host": False, "paused_owner": False}
    ]
    assert claims.held() == {"5BuildingOnTheA100"}  # the steps' owners are back
    assert not claims._exclusive  # no new claim was ever refused for other miners


def test_a_due_retrys_owner_is_taken_too(monkeypatch):
    retry, retry_owner = "rtsk_" + "r" * 64, "5Retry"
    monkeypatch.setattr(auto_retry, "due", lambda root, **kwargs: [retry])
    claims = grade_sequencer.OwnerClaims()
    seen = []
    grader = _grader(claims, seen, {**OWNERS, retry: retry_owner})
    taken = []
    grader._king_upkeep = lambda: taken.append(claims.try_claim(retry_owner))
    grader._run_once()
    assert taken == [False]


def test_a_touched_owner_in_flight_skips_the_steps_until_it_is_free(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(auto_grade.time, "monotonic", lambda: now[0])
    claims = grade_sequencer.OwnerClaims()
    assert claims.try_claim(KING_OWNER)  # the king's own miner is building
    seen = []
    grader = _grader(claims, seen)
    assert grader._run_once() is None and seen == []  # skipped, nothing waited for
    assert claims.held() == {KING_OWNER}  # no owner taken by the skip is kept
    claims.release(KING_OWNER)
    grader._run_once()
    assert len(seen) == 1  # asked again next round: it runs


def test_the_steps_are_never_starved_past_their_deferral(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(auto_grade.time, "monotonic", lambda: now[0])
    claims = grade_sequencer.OwnerClaims()
    assert claims.try_claim(KING_OWNER)
    seen = []
    grader = _grader(claims, seen)
    grader._run_once()
    now[0] += auto_grade.UPKEEP_DEFER_MAX_SECONDS
    done = threading.Event()
    threading.Thread(
        target=lambda: (grader._run_once(), done.set()), daemon=True
    ).start()
    # overdue: the steps now wait (bounded) for the owners they need, the king's miner's among them
    assert not done.wait(0.3) and seen == []
    assert not claims._exclusive  # only the needed owners, never every owner
    claims.release(KING_OWNER)
    assert done.wait(5) and len(seen) == 1


def test_owners_that_cannot_be_read_take_every_owner_as_before():
    claims = grade_sequencer.OwnerClaims()
    seen = []
    grader = _grader(
        claims, seen, {KING: KING_OWNER}
    )  # the paused crown's owner unresolved
    states = []
    grader._king_upkeep = lambda: states.append(claims._exclusive)
    grader._run_once()
    assert states == [True]


def test_no_grade_is_in_flight_while_the_steps_run():
    """The integrity guard stays: the steps wait for an in-flight grade to end and no grade starts meanwhile."""
    claims = grade_sequencer.OwnerClaims()
    seen = []
    grader = _grader(claims, seen)
    sequencer = grader.sequencer
    grading, finish = threading.Event(), threading.Event()

    def grade():
        with sequencer.task() as task:
            task.bind("rtsk_" + "g" * 64)
            grading.set()
            assert finish.wait(5)

    thread = threading.Thread(target=grade, daemon=True)
    thread.start()
    assert grading.wait(5)
    done = threading.Event()
    threading.Thread(
        target=lambda: (grader._run_once(), done.set()), daemon=True
    ).start()
    assert not done.wait(0.3) and seen == []  # waits for the grade in flight
    finish.set()
    thread.join(5)
    assert done.wait(5) and len(seen) == 1


def test_a_missed_owner_only_collides_on_its_lease_as_carbons_never_a_crown(tmp_path):
    """V2: an owner the read missed can only meet another round on its ledger's numerical lease, which refuses at once
    (Carbon's, never the candidate's); the king's step turns that into its typed FAILED attempt, never a crown change.
    """
    from carbon.challenge_validator import king_upkeep
    from carbon.development_session import research_carrier

    pytest.importorskip("fcntl")
    ledger = SimpleNamespace(root=tmp_path)
    with (
        research_carrier._numerical_lease(ledger),
        pytest.raises(ValueError, match="numerical supervisor active"),
        research_carrier._numerical_lease(ledger),
    ):
        pass
    noted = []

    class _UpkeepPool:
        def incumbent(self):
            return {"model_id": KING}

        def note_king_upkeep_attempt(self, king, exam, step, code):
            noted.append((king, step, code))
            return 1

    def collide(*args, **kwargs):
        raise ValueError("numerical supervisor active; do not reconcile live work")

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            king_upkeep,
            "_plan",
            lambda pool, intake, active: (king_upkeep.REGRADE, KING, "exam", [], None),
        )
        patch.setattr(king_upkeep, "king_origin_entry", lambda pool, root, king: {})
        from carbon.challenge_validator import lean_recipe_retention

        patch.setattr(lean_recipe_retention, "king_parent_moved", collide)
        out = king_upkeep.step(
            _UpkeepPool(),
            SimpleNamespace(adapter=None),
            root=tmp_path,
            artifacts=None,
            entries=None,
        )
    assert out["state"] == "FAILED" and out["step"] == king_upkeep.REGRADE
    assert noted == [(KING, king_upkeep.REGRADE, out["code"])]


def test_the_start_up_filing_takes_only_the_steps_owners_and_no_grade_runs_before_it():
    """Live 116 (18 Nov 2026): the start-up filing took EVERY owner, so it waited for every running build to end and
    refused every grade and new build meanwhile. It writes the pool store only: it takes the steps' own owners, other
    miners keep building, and ruling C holds by the round itself: until the filing is made, no grade is claimed.
    """
    claims = grade_sequencer.OwnerClaims()
    # another miner's build in flight: never waited for
    assert claims.try_claim("5BuildingOnTheA100")
    seen = []
    grader = _grader(claims, seen)
    grader._stranded_filed = False
    states = []

    def king():
        states.append(claims._exclusive)
        grader._stranded_filed = True  # the filing is made in this step

    grader._king_upkeep = king
    grader.pending = lambda: ["rtsk_" + "g" * 64]
    claimed = []
    grader._claim_and_grade = lambda *args: claimed.append(1)
    grader._run_once()
    assert states == [False]  # narrowed: never every owner
    assert claimed == [1]  # made: this round grades


def test_while_the_start_up_filing_is_not_made_no_grade_is_claimed(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(auto_grade.time, "monotonic", lambda: now[0])
    claims = grade_sequencer.OwnerClaims()
    # the steps' owner is busy: the steps are skipped this round
    assert claims.try_claim(KING_OWNER)
    seen = []
    grader = _grader(claims, seen)
    grader._stranded_filed = False
    grader.pending = lambda: ["rtsk_" + "g" * 64]
    claimed = []
    grader._claim_and_grade = lambda *args: claimed.append(1)
    assert grader._run_once() is None
    assert seen == [] and claimed == []  # no grade ahead of the filing


def test_a_skip_asks_again_soon_never_every_round_and_a_gap_resets_the_wait(
    monkeypatch,
):
    now = [1000.0]
    monkeypatch.setattr(auto_grade.time, "monotonic", lambda: now[0])
    claims = grade_sequencer.OwnerClaims()
    assert claims.try_claim(KING_OWNER)
    seen = []
    grader = _grader(claims, seen)
    grader._run_once()
    assert grader._prelude_after == now[0] + grader.PRELUDE_REASK_SECONDS
    assert grader._prelude_waiting_since == 1000.0
    grader._prelude_due = lambda pending: False  # nothing due for a while
    grader._run_once()
    assert grader._prelude_waiting_since == 1000.0  # only throttled: the clock runs on
    now[0] += grader.PRELUDE_REASK_SECONDS
    grader._run_once()
    assert (
        grader._prelude_waiting_since is None
    )  # really not due: a later wait starts afresh


def test_the_starvation_bound_holds_through_the_throttled_rounds(monkeypatch):
    """Review: a throttled round (the steps asked again shortly) is not 'nothing due': the deferral clock keeps running
    through rounds every 5 s, most inside the 10 s re-ask window, so the 30-min bound is reached (then every owner).
    """
    now = [1000.0]
    monkeypatch.setattr(auto_grade.time, "monotonic", lambda: now[0])
    claims = grade_sequencer.OwnerClaims()
    assert claims.try_claim(KING_OWNER)
    seen = []
    grader = _grader(claims, seen)
    # the real throttle, with the steps always due behind it
    grader._prelude_due = lambda pending: now[0] >= getattr(
        grader, "_prelude_after", 0.0
    )
    grader._run_once()  # skipped: the clock starts
    while now[0] + 5 < 1000.0 + auto_grade.UPKEEP_DEFER_MAX_SECONDS:
        now[0] += 5
        grader._run_once()
        assert (
            grader._prelude_waiting_since == 1000.0
        )  # never reset by a throttled round
    assert (
        seen == []
    )  # the king's owner stayed busy: skipped every time, until the bound


def test_a_king_admitted_under_an_earlier_pack_resolves_through_the_ledger():
    claims = grade_sequencer.OwnerClaims()
    seen = []
    grader = _grader(
        claims, seen, {PAUSED: PAUSED_OWNER}
    )  # the adapter no longer resolves the king
    grader.intake.adapter.ledger.admitted_owner = lambda task: (
        ("sha256:" + "0" * 64, KING_OWNER) if task == KING else None
    )
    states = []

    def king():
        states.append((claims._exclusive, claims.try_claim(KING_OWNER)))

    grader._king_upkeep = king
    grader._run_once()
    assert states == [
        (False, False)
    ]  # narrowed, and the king's owner is held by the steps


def test_a_grade_in_flight_holding_a_steps_owner_never_hangs_the_steps_they_run_after_it():
    """V2's ruling (18 Nov 2026): the steps take the sequencer's exclusive FIRST, then their owners without waiting. A
    grade in flight that holds one of their owners: the steps wait for it to end (the crown CAS), never while holding
    owner claims, and then run."""
    claims = grade_sequencer.OwnerClaims()
    seen = []
    grader = _grader(claims, seen)
    sequencer = grader.sequencer
    grading, finish = threading.Event(), threading.Event()

    def grade():
        with sequencer.task() as task:
            task.bind("rtsk_" + "g" * 64)
            assert claims.try_claim(KING_OWNER)  # the king's own miner's grade
            grading.set()
            assert finish.wait(5)
            claims.release(KING_OWNER)

    thread = threading.Thread(target=grade, daemon=True)
    thread.start()
    assert grading.wait(5)
    done = threading.Event()
    threading.Thread(
        target=lambda: (grader._run_once(), done.set()), daemon=True
    ).start()
    assert not done.wait(0.3) and seen == []
    # waiting for the grade in flight, the steps hold no owner claim
    assert claims.held() == {KING_OWNER}
    finish.set()
    thread.join(5)
    assert done.wait(5) and len(seen) == 1


def _hold_bound():
    return min(
        auto_grade.STRANDED_GRADE_HOLD_SECONDS, auto_grade.UPKEEP_DEFER_MAX_SECONDS
    )


def _logged(monkeypatch):
    from carbon.battery import intake

    lines = []
    monkeypatch.setattr(
        intake, "log", lambda event, **fields: lines.append((event, fields))
    )
    return lines


def test_a_start_up_filing_that_never_runs_holds_grades_only_up_to_its_bound(
    monkeypatch,
):
    """V2's condition (18 Nov 2026): the filing's hold on grades is bounded. Its owners stay busy, so it is skipped
    every round; past the bound grading goes on, with ONE ``stranded_filing_overdue`` alert.
    """
    now = [1000.0]
    monkeypatch.setattr(auto_grade.time, "monotonic", lambda: now[0])
    lines = _logged(monkeypatch)
    claims = grade_sequencer.OwnerClaims()
    assert claims.try_claim(KING_OWNER)
    seen = []
    grader = _grader(claims, seen)
    grader._stranded_filed = False
    grader.pending = lambda: ["rtsk_" + "g" * 64]
    claimed = []
    grader._claim_and_grade = lambda *args: claimed.append(now[0])
    bound = _hold_bound()
    grader._run_once()
    now[0] += bound - 1
    grader._run_once()
    assert claimed == []  # still inside the bound: no grade ahead of the filing
    now[0] += 2
    grader._run_once()
    grader._run_once()
    assert claimed == [now[0], now[0]]  # past it: grading goes on
    overdue = [fields for event, fields in lines if event == "stranded_filing_overdue"]
    assert overdue == [{"code": "not_run", "seconds": round(bound + 1)}]


def test_a_filing_stuck_on_retry_does_not_block_grading_past_the_bound(monkeypatch):
    from carbon.challenge_validator import king_upkeep

    now = [1000.0]
    monkeypatch.setattr(auto_grade.time, "monotonic", lambda: now[0])
    lines = _logged(monkeypatch)
    claims = grade_sequencer.OwnerClaims()
    seen = []
    grader = _grader(claims, seen)
    grader._stranded_filed = False
    grader._upkeep_deferred = lambda: True  # the round's step is the filing alone
    grader._pool = lambda: _Pool()
    grader.root = "/r"
    grader.intake.adapter.discovery = SimpleNamespace(evaluation_pack_digest="e")
    tries = []

    def refused(root, pool_store, discovery):
        tries.append(now[0])
        return king_upkeep.STRANDED_RETRY, 0

    monkeypatch.setattr(king_upkeep, "file_stranded", refused)
    grader.pending = lambda: ["rtsk_" + "g" * 64]
    claimed = []
    grader._claim_and_grade = lambda *args: claimed.append(now[0])
    bound = _hold_bound()
    end = now[0] + bound + 2 * king_upkeep.STRANDED_RETRY_SECONDS
    while now[0] < end:
        grader._run_once()
        now[0] += king_upkeep.STRANDED_RETRY_SECONDS
    assert len(tries) > 2  # tried again every time it was due
    assert claimed and claimed[-1] > 1000.0 + bound  # grading goes on past the bound
    assert [f["code"] for e, f in lines if e == "stranded_filing_overdue"] == ["retry"]


def test_the_overdue_wait_for_a_busy_owner_is_bounded_and_defers_again(monkeypatch):
    """V2's ruling (18 Nov 2026): inside the sequencer's exclusive the steps never wait unboundedly for an owner a
    running build holds: past `PRELUDE_OWNER_WAIT_SECONDS` they let go, log ``prelude_owners_busy`` and defer.
    """
    now = [1000.0]
    monkeypatch.setattr(auto_grade.time, "monotonic", lambda: now[0])
    lines = _logged(monkeypatch)
    claims = grade_sequencer.OwnerClaims()
    assert claims.try_claim(
        KING_OWNER
    )  # an A100 build of the king's miner, for its whole build
    seen = []
    grader = _grader(claims, seen)
    grader._run_once()  # skipped: the deferral clock starts
    now[0] += auto_grade.UPKEEP_DEFER_MAX_SECONDS
    real = grade_sequencer.OwnerClaims.within

    def short(self, owners, seconds, poll=1.0):
        import time as real_time

        monkeypatch.setattr(auto_grade.time, "monotonic", real_time.perf_counter)
        return real(self, owners, 0.2, poll=0.05)

    monkeypatch.setattr(grade_sequencer.OwnerClaims, "within", short)
    done = threading.Event()
    threading.Thread(
        target=lambda: (grader._run_once(), done.set()), daemon=True
    ).start()
    assert done.wait(5) and seen == []  # returned within the bound, the steps not run
    assert claims.held() == {KING_OWNER}  # nothing kept
    assert [event for event, _ in lines if event == "prelude_owners_busy"] == [
        "prelude_owners_busy"
    ]


def test_a_grader_built_without_a_pool_store_holds_no_grade():
    """Runner g8934 (18 Nov 2026): a grader built without a pool store (a one-shot tool, a test double) files nothing,
    so the start-up filing holds no grade there, and never raises (it killed the grade thread).
    """
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader._stranded_filed = False
    assert not hasattr(grader, "pool_store")
    assert grader._stranded_holds_grades() is False
