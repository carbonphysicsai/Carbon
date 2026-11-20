"""A miner withdraws its own queued, not-yet-building official submission (owner GO 15 Nov 2026 via the Lead: "those 3 are
fine."; pick (2)).

Claims: the signed ``construction_withdraw {submission_id}`` of the SAME hotkey cancels its own QUEUED task under a durable
cancellation id (``miner-withdraw-<id>``), records a ledger row and a terminal WITHDRAWN_BY_MINER grade marker, uses no try
and no allowance, and frees the waiting place at once; again is idempotent; building, built or ended is too late and
changes nothing; another hotkey's id and an unknown id are one 404. The withdrawn task projects ``withdrawn_by_miner`` (the
kit never resubmits it); the same recipe submitted again is the next generation and no later copy WAITs on it; a start
that loses the race to a withdrawal is skipped quietly; the grade round repairs a missing marker; exam feedback v9 says
WITHDRAWN_BY_MINER and every older reply NOT_GRADED; the kit's ``withdraw`` signs the request from the epoch's own admission
record, says each refusal in words and sets the record aside.

Through the REAL `LeanRecipeAdapter` (a real durable task provider and attempt ledger) on the synthetic fixture Challenge.
Synthetic hotkeys, ids and fixture material only.
"""

from __future__ import annotations

import functools
import json
import sqlite3
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from carbon.challenge_validator import auto_grade, direct_intake, recipe_copies
from carbon.challenge_validator import coldkey_waiting as cw
from carbon.challenge_validator import lean_recipe as lr
from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable
from carbon.development_session import direct_submission as client

UNKNOWN = "rtsk_" + "0" * 64
EXAM = "sha256:" + "e" * 64


# --- the real door ------------------------------------------------------------------------------------------------


def _door(tmp_path, monkeypatch, *, per="hotkey"):
    """`test_coldkey_waiting._door` (a real provider for the hotkey "miner", a real attempt ledger, the waiting guard per
    hotkey), plus the door's grader (its markers beside the ledger, as on a receiver root) and the intake's state.
    """
    from test_coldkey_waiting import _door as coldkey_door

    request, adapter, ledger, door, provider = coldkey_door(
        tmp_path, monkeypatch, per=per
    )
    intake = SimpleNamespace(adapter=adapter, window=None)
    # the intake's REAL per-owner lock (`DirectRecipeIntake._owner_lock`), which a withdrawal holds (LEAD #1: no
    # door-wide `_write` any more), bound to this stand-in intake
    intake._owner_lock = functools.partial(
        direct_intake.DirectRecipeIntake._owner_lock, intake
    )
    grader = auto_grade.AutoGrader(intake, ledger.path.parent)
    intake.grade_marker = grader.marker
    intake.withdraw_marker = grader.withdrawn
    return SimpleNamespace(
        request=request,
        adapter=adapter,
        ledger=ledger,
        door=door,
        provider=provider,
        intake=intake,
        grader=grader,
    )


def _submit(d, recipe, sequence):
    from test_coldkey_waiting import _submit as submit

    return submit(d.door, d.adapter, recipe, sequence)


def _queued(d, sequence=1):
    result = _submit(d, d.request.recipe, sequence)
    assert result["kind"] == "OUTCOME", result
    sid = result["outcome"]["submission_id"]
    assert d.provider._views[sid].state.value == "QUEUED"
    return sid


def _withdraw(d, sid, hotkey="miner"):
    return direct_intake.DirectRecipeIntake._withdraw(
        d.intake, hotkey, {"submission_id": sid}
    )


def _exam_rows(ledger, sid):
    """Rows naming ``sid`` in any exam slot table of the ledger (none exist until a grade reserves one)."""
    found = 0
    with sqlite3.connect(ledger.path) as db:
        tables = [
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'exam%'"
            )
        ]
        for table in tables:
            columns = [row[1] for row in db.execute(f"PRAGMA table_info({table})")]
            if "submission_id" in columns:
                found += db.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE submission_id=?", (sid,)
                ).fetchone()[0]
    return found


def _same_or_nothing(d, sid):
    """Nothing about ``sid`` was recorded as a withdrawal."""
    assert d.ledger.miner_withdrawal(d.adapter.contract_digest, sid) is None
    assert d.grader.marker(sid) is None
    assert d.provider._cancellations.get(sid) != lr.WITHDRAW_PREFIX + sid


def test_a_queued_submission_is_withdrawn_recorded_and_marked_and_uses_no_try(
    tmp_path, monkeypatch
):
    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    assert d.grader.pending() == [sid]
    answer = _withdraw(d, sid)
    assert (answer.status, answer.body) == (
        200,
        {"withdrawn": sid, "grade_state": "WITHDRAWN_BY_MINER"},
    )
    assert d.provider._views[sid].state.value == "CANCELLED"
    assert d.provider._cancellations[sid] == "miner-withdraw-" + sid
    hotkey, at_ns = d.ledger.miner_withdrawal(d.adapter.contract_digest, sid)
    assert hotkey == "miner" and type(at_ns) is int
    marker = d.grader.marker(sid)
    assert (marker["state"], marker["code"]) == (
        auto_grade.WITHDRAWN_STATE,
        auto_grade.WITHDRAWN_CODE,
    )
    assert d.grader.pending() == []
    assert _exam_rows(d.ledger, sid) == 0  # no slot, no try, no allowance
    # the intent and OUTCOME rows are kept: the owner still resolves (status and feedback reads keep working)
    assert d.ledger.owned_outcome(d.adapter.contract_digest, sid) == "miner"
    assert d.adapter.owner(sid) == "miner"
    # the durable cancellation id survives a restart of the provider's store
    with d.provider._db() as db:
        stored = db.execute(
            "SELECT cancellation FROM direct_tasks WHERE id=?", (sid,)
        ).fetchone()[0]
    assert stored == "miner-withdraw-" + sid


def test_the_same_withdrawal_again_is_idempotent(tmp_path, monkeypatch):
    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    first = _withdraw(d, sid)
    row = d.ledger.miner_withdrawal(d.adapter.contract_digest, sid)
    marker = (d.grader.markers / (sid + ".json")).read_bytes()
    again = _withdraw(d, sid)
    assert (again.status, again.body) == (first.status, first.body)
    assert d.ledger.miner_withdrawal(d.adapter.contract_digest, sid) == row
    assert (d.grader.markers / (sid + ".json")).read_bytes() == marker
    assert d.adapter.withdraw("miner", sid) == lr.ALREADY_WITHDRAWN


def test_a_building_submission_is_too_late_and_nothing_changes(tmp_path, monkeypatch):
    from carbon.development_session import bundle_construction_worker

    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    seen = []

    def building(*args, **kwargs):
        # the build is running now (the start took the provider's lock, then let go of it before the build)
        seen.append((d.provider._views[sid].state.value, _withdraw(d, sid)))
        return {"claimed": "success"}

    monkeypatch.setattr(
        bundle_construction_worker, "reconstruct_and_infer_public", building
    )
    assert d.adapter.advance() == 1
    [(state, answer)] = seen
    assert state == "RUNNING"
    assert (answer.status, answer.body) == (409, {"refused": "withdraw_too_late"})
    ended = d.provider._views[sid].state.value
    assert ended not in ("QUEUED", "RUNNING", "CANCELLED")  # it ran to its own end
    again = _withdraw(d, sid)  # ended: still too late, still nothing changed
    assert (again.status, again.body) == (409, {"refused": "withdraw_too_late"})
    _same_or_nothing(d, sid)
    assert d.provider._views[sid].state.value == ended


@pytest.mark.parametrize("state", ["SUCCEEDED", "CANCEL_REQUESTED", "REFUSED"])
def test_built_cancel_requested_or_ended_is_too_late(tmp_path, monkeypatch, state):
    from carbon.research import DirectTaskStateV3

    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    # the provider's view as it reads in that state (only the state is looked at; a terminal view's receipt is not)
    d.provider._views[sid] = SimpleNamespace(
        state=DirectTaskStateV3[state], task_id=d.provider._views[sid].task_id
    )
    answer = _withdraw(d, sid)
    assert (answer.status, answer.body) == (409, {"refused": "withdraw_too_late"})
    assert d.provider._views[sid].state is DirectTaskStateV3[state]
    _same_or_nothing(d, sid)


def test_a_task_a_receiver_stop_cancelled_is_too_late_and_keeps_its_own_code(
    tmp_path, monkeypatch
):
    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    d.provider.cancel_observed_task(
        d.provider._views[sid].task_id, d.adapter.discovery.info.challenge_key
    )
    answer = _withdraw(d, sid)
    assert (answer.status, answer.body) == (409, {"refused": "withdraw_too_late"})
    assert d.adapter.outcome(sid)["failure"]["code"] == "direct_task_cancelled"
    _same_or_nothing(d, sid)


def test_another_hotkeys_task_an_unknown_id_and_a_door_without_its_provider_are_one_404(
    tmp_path, monkeypatch
):
    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    unknown = (404, {"refused": "withdraw_submission_unknown"})
    for hotkey, task in (("other-miner", sid), ("miner", UNKNOWN)):
        answer = _withdraw(d, task, hotkey=hotkey)
        assert (answer.status, answer.body) == unknown
    assert d.provider._views[sid].state.value == "QUEUED"
    d.adapter.provider_for = (
        lambda owner: None
    )  # this door holds no provider for that hotkey
    answer = _withdraw(d, sid)
    assert (answer.status, answer.body) == unknown
    assert d.provider._views[sid].state.value == "QUEUED"
    _same_or_nothing(d, sid)


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"submission_id": 7},
        {"submission_id": ""},
        {"submission_id": UNKNOWN, "x": 1},
    ],
)
def test_malformed_fields_are_refused(tmp_path, monkeypatch, fields):
    d = _door(tmp_path, monkeypatch)
    answer = direct_intake.DirectRecipeIntake._withdraw(d.intake, "miner", fields)
    assert (answer.status, answer.body) == (400, {"refused": "withdraw_fields"})


def test_a_door_that_does_not_grade_its_own_submissions_neither_advertises_nor_takes_it(
    tmp_path, monkeypatch
):
    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    d.intake.withdraw_marker = None
    answer = _withdraw(d, sid)
    assert (answer.status, answer.body) == (400, {"refused": "tool"})
    assert d.provider._views[sid].state.value == "QUEUED"


def test_the_door_advertises_the_withdraw_facts_entry_the_kit_pins():
    assert direct_intake.withdraw_facts() == client.WITHDRAW_FACTS
    assert direct_intake.WITHDRAW_FACTS_NAME == client.WITHDRAW_FACTS_NAME
    assert (
        direct_intake.WITHDRAW_TOOL == client.WITHDRAW_TOOL == "construction_withdraw"
    )
    text = Path(direct_intake.__file__).read_text(encoding="utf-8")
    # in its own facts entry, only beside a grade marker reader; never in the pinned `tools` list
    assert "{WITHDRAW_FACTS_NAME: withdraw_facts()}" in text
    assert '"tools": [SUBMIT_TOOL, STATUS_TOOL, RESEARCH_NAMESPACE]' in text
    assert "if received.call.tool == WITHDRAW_TOOL:" in text
    import inspect

    from carbon.challenge_validator import direct_receiver

    assert "intake.withdraw_marker = grader.withdrawn" in inspect.getsource(
        direct_receiver.serve
    )


# --- the waiting place, the next generation, copies, the projection ------------------------------------------------


def test_the_waiting_place_is_freed_at_once(tmp_path, monkeypatch):
    from test_coldkey_waiting import _other

    d = _door(tmp_path, monkeypatch, per="hotkey")
    sid = _queued(d)
    refused = _submit(d, _other(d.request.recipe), 2)
    assert (refused["kind"], refused["code"]) == ("UNAVAILABLE", cw.HOTKEY_CODE)
    assert "withdraw it while it is still queued" in cw.HOTKEY_MESSAGE
    assert _withdraw(d, sid).status == 200
    admitted = _submit(d, _other(d.request.recipe), 3)
    assert admitted["kind"] == "OUTCOME", admitted
    assert admitted["outcome"]["submission_id"] != sid


def test_the_same_recipe_again_is_the_next_generation_and_no_copy_waits_on_the_withdrawn(
    tmp_path, monkeypatch
):
    from carbon.development_session.construction_recipe import ConstructionRecipe

    d = _door(tmp_path, monkeypatch)
    recipe_copies.activate(d.ledger, d.adapter.contract_digest)
    sid = _queued(d)
    recipe_copies.note_admitted(d.adapter, sid)
    assert _withdraw(d, sid).status == 200
    again = _submit(d, d.request.recipe, 2)
    assert again["kind"] == "OUTCOME", again
    new = again["outcome"]["submission_id"]
    recipe = ConstructionRecipe.from_dict(d.provider._requests[sid].recipe)
    generation = [
        d.provider._task_id(
            d.adapter._request(
                "miner",
                recipe,
                evaluation_pack_digest=d.provider.evaluation_pack_digest,
                rerun=rerun,
            )
        ).value
        for rerun in (0, 1)
    ]
    assert generation == [
        sid,
        new,
    ]  # each withdraw uses one of MAX_INFRA_RERUNS generations
    assert d.provider._views[new].state.value == "QUEUED"
    recipe_copies.note_admitted(d.adapter, new)

    def decide(marker):
        return recipe_copies.decide(
            adapter=d.adapter,
            ledger=d.ledger,
            marker=marker,
            submission_id=new,
            challenge_id=d.adapter.challenge_id,
            challenge_version=d.adapter.challenge_version,
            exam_key=EXAM,
        )

    # the withdrawn first has a marker, so it is settled: the new one is graded, never held behind it
    assert decide(d.grader.marker) == (recipe_copies.GRADE, None)
    # without that marker the withdrawn first still never holds it: it ended without a build (Order 3, 17 Nov)
    assert decide(lambda task: None) == (recipe_copies.GRADE, None)
    # (the control: an earlier task whose state cannot be read, and that has no marker, holds it WAITING, as before)
    monkeypatch.setattr(
        d.adapter, "outcome", lambda task: (_ for _ in ()).throw(LookupError(task))
    )
    assert decide(lambda task: None) == (recipe_copies.WAIT, sid)


def test_the_withdrawn_task_projects_its_own_code_never_a_stops_cancellation(
    tmp_path, monkeypatch
):
    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    _withdraw(d, sid)
    outcome = d.adapter.outcome(sid)
    assert outcome["state"] == "FAILED_INFRA"
    assert outcome["failure"] == {"code": "withdrawn_by_miner"}
    assert not client._cancelled_by_stop(outcome)


# --- the race with a start ----------------------------------------------------------------------------------------


def test_advance_skips_a_task_withdrawn_between_its_read_and_its_start(
    tmp_path, monkeypatch
):
    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    real = d.provider.run_queued_task

    def withdrawn_first(task_id):
        assert _withdraw(d, sid).status == 200  # lands after advance read QUEUED
        return real(task_id)

    monkeypatch.setattr(d.provider, "run_queued_task", withdrawn_first)
    assert (
        d.adapter.advance() == 0
    )  # nothing started, and nothing raised (no direct_worker_failure)
    assert d.provider._views[sid].state.value == "CANCELLED"


def test_advance_still_raises_an_invalid_start_that_is_not_a_withdrawal(
    tmp_path, monkeypatch
):
    from carbon.research.errors import ResearchServiceErrorCode
    from carbon.research.lifecycle import ResearchTaskProviderError

    d = _door(tmp_path, monkeypatch)
    _queued(d)

    def refused(task_id):
        raise ResearchTaskProviderError(
            ResearchServiceErrorCode.INVALID_TASK_TRANSITION
        )

    monkeypatch.setattr(d.provider, "run_queued_task", refused)
    with pytest.raises(ResearchTaskProviderError):
        d.adapter.advance()


def test_a_withdrawal_and_a_start_on_two_threads_one_wins_cleanly(
    tmp_path, monkeypatch
):
    from carbon.development_session import bundle_construction_worker
    from carbon.research.errors import ResearchServiceErrorCode
    from carbon.research.lifecycle import ResearchTaskProviderError

    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    built = []
    monkeypatch.setattr(
        bundle_construction_worker,
        "reconstruct_and_infer_public",
        lambda *args, **kwargs: built.append(1) or {"claimed": "success"},
    )
    barrier = threading.Barrier(2)
    results = {}

    def withdraw():
        barrier.wait()
        results["withdraw"] = _withdraw(d, sid)

    def start():
        barrier.wait()
        try:
            d.provider.run_queued_task(d.provider._views[sid].task_id)
            results["start"] = "started"
        except ResearchTaskProviderError as refused:
            results["start"] = refused.code

    threads = [threading.Thread(target=withdraw), threading.Thread(target=start)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    state = d.provider._views[sid].state.value
    if results["withdraw"].status == 200:
        assert results["start"] is ResearchServiceErrorCode.INVALID_TASK_TRANSITION
        assert state == "CANCELLED" and built == []
        assert d.grader.marker(sid)["state"] == auto_grade.WITHDRAWN_STATE
    else:
        assert results["withdraw"].body == {"refused": "withdraw_too_late"}
        assert results["start"] == "started" and built == [1]
        assert state != "CANCELLED"
        _same_or_nothing(d, sid)


# --- the repair of a missing marker -------------------------------------------------------------------------------


def test_the_grade_round_repairs_a_withdrawal_whose_record_and_marker_were_not_written(
    tmp_path, monkeypatch
):
    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    # the door call stopped right after the provider's cancel (no ledger row, no marker)
    assert d.adapter.withdraw("miner", sid) == lr.WITHDRAWN
    assert d.grader.pending() == [sid]
    d.intake.retain_result = lambda *args, **kwargs: (_ for _ in ()).throw(
        RetentionUnavailable("task_not_succeeded")
    )
    assert d.grader.run_once() is None
    assert d.grader.marker(sid)["state"] == auto_grade.WITHDRAWN_STATE
    assert d.ledger.miner_withdrawal(d.adapter.contract_digest, sid)[0] == "miner"
    assert d.grader.pending() == []
    assert _exam_rows(d.ledger, sid) == 0
    # and the miner's retry still answers 200 (idempotent), changing nothing
    assert _withdraw(d, sid).status == 200


def test_the_repair_runs_before_the_copy_rule_so_a_waiting_copy_never_holds_it(
    tmp_path, monkeypatch
):
    """An unsettled earlier identical recipe would make the copy rule WAIT on this task every round: the withdrawal's repair
    comes first, so the withdrawn task is settled anyway (and never graded or charged as a copy).
    """
    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    assert d.adapter.withdraw("miner", sid) == lr.WITHDRAWN  # the cancel only
    asked = []
    d.grader._copy_decision = lambda task: asked.append(task) or ("wait", UNKNOWN)
    d.intake.retain_result = lambda *a, **k: pytest.fail(
        "a withdrawn task is never retained"
    )
    assert d.grader.run_once() is None
    assert d.grader.marker(sid)["state"] == auto_grade.WITHDRAWN_STATE
    assert asked == [] and d.grader.pending() == []


def test_a_failing_marker_write_answers_503_and_the_retry_completes_it(
    tmp_path, monkeypatch
):
    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    real = d.intake.withdraw_marker

    def broken(task):
        raise OSError("disk full")

    d.intake.withdraw_marker = broken
    answer = _withdraw(d, sid)
    assert (answer.status, answer.body) == (503, {"refused": "withdraw_unavailable"})
    assert d.provider._views[sid].state.value == "CANCELLED"  # the cancel itself stands
    assert d.grader.marker(sid) is None and d.grader.pending() == [sid]
    d.intake.withdraw_marker = real
    assert _withdraw(d, sid).status == 200
    assert d.grader.marker(sid)["state"] == auto_grade.WITHDRAWN_STATE


def test_a_pending_task_that_was_not_withdrawn_is_never_marked_by_the_repair(
    tmp_path, monkeypatch
):
    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    assert d.grader._settle_withdrawn(sid) is False
    assert d.grader.marker(sid) is None and d.grader.pending() == [sid]


def test_a_withdrawn_marker_never_replaces_another_state(tmp_path):
    grader = auto_grade.AutoGrader(SimpleNamespace(adapter=None), tmp_path)
    task = "rtsk_" + "a" * 64
    grader._write(task, "GRADED")
    with pytest.raises(FileExistsError):
        grader.withdrawn(task)
    assert grader.marker(task)["state"] == "GRADED"


def test_every_marker_reader_treats_a_withdrawal_as_settled_and_never_graded(
    tmp_path,
):
    from carbon.challenge_validator import infra_requeue, queue_view

    grader = auto_grade.AutoGrader(SimpleNamespace(adapter=None), tmp_path)
    task = "rtsk_" + "a" * 64
    grader.withdrawn(task)
    grader.withdrawn(task)  # idempotent
    # (the instance's `failures` is its failures DIRECTORY: the status method is read from the class)
    assert auto_grade.AutoGrader.failures(grader) == (0, None)
    assert auto_grade.failure_summary(tmp_path)["auto_grade_failed"] == 0
    marker = grader.markers / (task + ".json")
    # the requeue's scan, release and reclass act on FAILED markers only: this one is its own state
    assert infra_requeue._marker(marker) == "WITHDRAWN_BY_MINER"
    assert queue_view._withdrawn(marker)
    view = SimpleNamespace(grader=grader)
    import time

    now = time.time()
    # a withdrawn task's marker is never a wait sample; a graded one's is
    assert queue_view.QueueView._waits(view, now, {task: ("CANCELLED", now - 60)}) == []
    other = "rtsk_" + "b" * 64
    grader._write(other, "GRADED")
    waits = queue_view.QueueView._waits(
        view, now + 1, {task: ("CANCELLED", now - 60), other: ("SUCCEEDED", now - 60)}
    )
    assert len(waits) == 1


# --- exam feedback v9 ---------------------------------------------------------------------------------------------


def _feedback_intake():
    from test_gate_failure_feedback import HOTKEY, SID

    intake = SimpleNamespace(
        challenge=SimpleNamespace(
            challenge_id="electric-motor-magnetics", version="1.8"
        ),
        grade_marker=lambda sid: {
            "schema": auto_grade.SCHEMA,
            "state": auto_grade.WITHDRAWN_STATE,
            "code": auto_grade.WITHDRAWN_CODE,
        },
        adapter=SimpleNamespace(
            owner=lambda sid: HOTKEY if sid == SID else None,
            discovery=SimpleNamespace(evaluation_pack_snapshot=None),
        ),
        queue_view=SimpleNamespace(held=lambda: None),
    )
    intake._grade_state_v4 = (
        lambda hotkey, sid: direct_intake.DirectRecipeIntake._grade_state_v4(
            intake, hotkey, sid
        )
    )
    intake._grade_state = (
        lambda hotkey, sid: direct_intake.DirectRecipeIntake._grade_state(
            intake, hotkey, sid
        )
    )
    intake._held = lambda: None
    intake.grade_worker = lambda: {
        "cpu_model": None,
        "cpu_count": None,
        "memory_bytes": None,
        "gpu": False,
    }
    return intake, HOTKEY, SID


V8 = {"v4": True, "v5": True, "v6": True, "v7": True, "v8": True}


def _reply(**flags):
    intake, hotkey, sid = _feedback_intake()
    return direct_intake.DirectRecipeIntake._feedback(
        intake, hotkey, submission_id=sid, **flags
    )


def test_feedback_v9_says_withdrawn_and_every_older_reply_not_graded():
    v9 = _reply(**V8, v9=True)
    assert v9.status == 200
    assert v9.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA_V9
    assert v9.body["submission"]["grade_state"] == "WITHDRAWN_BY_MINER"
    assert v9.body["submission"]["failure"] is None
    for flags in (
        V8,
        {"v4": True, "v5": True, "v6": True, "v7": True},
        {"v4": True},
    ):
        older = _reply(**flags)
        assert older.body["submission"]["grade_state"] == "NOT_GRADED", flags
        assert older.body["schema"] != direct_intake.FEEDBACK_REPLY_SCHEMA_V9
    assert _reply().body["submission"]["grade_state"] is None  # v2's closed set
    assert _reply(v3=True).body["submission"]["grade_state"] is None


def test_feedback_v9_is_opt_in_recognised_and_advertised():
    sid = "rtsk_" + "1" * 64
    assert direct_intake.feedback_reply({"reply": "v9", "submission_id": sid}) == "v9"
    # v10 (failure classes, 20 Nov 2026) asks for v9's states too; an unknown reply is still refused
    assert direct_intake.feedback_reply({"reply": "v10", "submission_id": sid}) == "v10"
    # v11 (G-LEAD-10 row 1's recipe-side row) asks for them too
    assert direct_intake.feedback_reply({"reply": "v11", "submission_id": sid}) == "v11"
    assert direct_intake.feedback_reply({"reply": "v12", "submission_id": sid}) is None
    text = Path(direct_intake.__file__).read_text(encoding="utf-8")
    assert '"exam_feedback_v9"' in text and 'v9=reply in ("v9", "v10", "v11")' in text
    assert client.FEEDBACK_V9_FACTS["reply_schema"] == (
        direct_intake.FEEDBACK_REPLY_SCHEMA_V9
    )
    assert client.GRADE_STATES_V9 == (*client.GRADE_STATES_V5, "WITHDRAWN_BY_MINER")
    assert direct_intake.WITHDRAWN_STATE == auto_grade.WITHDRAWN_STATE


def test_feedback_v9_through_the_real_adapter_before_and_after_its_marker(
    tmp_path, monkeypatch
):
    d = _door(tmp_path, monkeypatch)
    sid = _queued(d)
    assert (
        d.adapter.withdraw("miner", sid) == lr.WITHDRAWN
    )  # the cancel only: no marker yet
    state = direct_intake.DirectRecipeIntake._grade_state_v4(d.intake, "miner", sid)
    assert state == ("WITHDRAWN_BY_MINER", None)
    assert _withdraw(d, sid).status == 200
    state = direct_intake.DirectRecipeIntake._grade_state_v4(d.intake, "miner", sid)
    assert state == ("WITHDRAWN_BY_MINER", None)


def test_a_v9_kit_asks_for_v9_where_advertised_and_reads_withdrawn(monkeypatch):
    from test_feedback_reply_v7 import _kit as kit7

    body = _reply(**V8, v9=True).body
    original = client.read_exam_feedback

    def with_v9(*args, read, **kw):
        facts = {
            **read(None),
            "exam_feedback_v8": client.FEEDBACK_V8_FACTS,
            "exam_feedback_v9": client.FEEDBACK_V9_FACTS,
        }
        return original(*args, read=lambda url: facts, **kw)

    monkeypatch.setattr(client, "read_exam_feedback", with_v9)
    got, sent = kit7(monkeypatch, body, ("v2", "v3", "v4", "v5", "v6", "v7"))
    assert sent["reply"] == "v9"
    assert got["submission"]["grade_state"] == "WITHDRAWN_BY_MINER"
    # a v8 reply naming the v9 state is refused whole, never trimmed
    v8_body = {**body, "schema": client.FEEDBACK_REPLY_SCHEMA_V8}

    def with_v8(*args, read, **kw):
        facts = {**read(None), "exam_feedback_v8": client.FEEDBACK_V8_FACTS}
        return original(*args, read=lambda url: facts, **kw)

    monkeypatch.setattr(client, "read_exam_feedback", with_v8)
    with pytest.raises(client.DirectIntakeRefusal):
        kit7(monkeypatch, v8_body, ("v2", "v3", "v4", "v5", "v6", "v7"))


# --- the kit ------------------------------------------------------------------------------------------------------


def _admitted_epoch(tmp_path, monkeypatch, task="task-1"):
    """An epoch the kit submitted: its admission record (written by the real `submit_and_wait`) and frozen selection."""
    from test_direct_submission import _answer, _client, _recipe

    def send(url, body, headers):
        return 202, _answer("ADMITTED", task_id=task)

    with pytest.raises(client.DirectConstructionPending):
        _client(tmp_path, monkeypatch, send, wait_s=0)()
    folder = tmp_path / "epoch-1"
    folder.mkdir()
    (folder / "selected-recipe.json").write_text(
        json.dumps({"strategy": _recipe().to_dict()})
    )
    return tmp_path / "construction-intake-epoch-1.json"


def _facts(withdraw=True):
    from test_direct_submission import _facts as facts

    found = facts()
    if withdraw:
        found[client.WITHDRAW_FACTS_NAME] = dict(client.WITHDRAW_FACTS)
    return found


def test_the_kit_signs_the_withdraw_from_the_epochs_record_and_sets_the_record_aside(
    tmp_path, monkeypatch
):
    record = _admitted_epoch(tmp_path, monkeypatch)
    sent = []

    def send(url, body, headers):
        sent.append((url, json.loads(body), headers))
        return 200, {"withdrawn": "task-1", "grade_state": "WITHDRAWN_BY_MINER"}

    answer = client.withdraw_submission(
        tmp_path, 1, "external-signer", read=lambda url: _facts(), send=send
    )
    assert answer == {"withdrawn": "task-1", "grade_state": "WITHDRAWN_BY_MINER"}
    [(url, request, headers)] = sent
    assert url == "http://127.0.0.1:9080"
    assert request["tool"] == "construction_withdraw"
    assert request["fields"] == {"submission_id": "task-1"}
    assert headers == {"signed": "fixture"}
    assert not record.exists()  # set aside, never deleted
    aside = json.loads(
        (tmp_path / "construction-intake-epoch-1.withdrawn-1.json").read_bytes()
    )
    assert aside["submission_id"] == "task-1"
    # the next submit is a NEW request (a bumped request id), so the frozen recipe goes again as a fresh task
    assert (tmp_path / "construction-intake-epoch-1.attempt").read_text() == "1"


def test_the_kit_refuses_before_signing_where_the_door_does_not_take_withdrawals(
    tmp_path, monkeypatch
):
    record = _admitted_epoch(tmp_path, monkeypatch)
    sent = []
    with pytest.raises(client.DirectWithdrawRefused) as refused:
        client.withdraw_submission(
            tmp_path,
            1,
            "external-signer",
            read=lambda url: _facts(withdraw=False),
            send=lambda *a: sent.append(a),
        )
    assert refused.value.code == "withdraw_not_offered"
    assert "does not take withdrawals yet" in refused.value.words
    assert sent == [] and record.exists()


@pytest.mark.parametrize(
    ("status", "code", "words"),
    [
        (409, "withdraw_too_late", "already building or built"),
        (409, "withdraw_too_late", "can no longer be withdrawn"),
        (404, "withdraw_submission_unknown", "nothing to withdraw"),
        (400, "withdraw_fields", "Update your kit"),
        (503, "withdraw_unavailable", "may have happened"),
        (503, "withdraw_unavailable", "Run withdraw again"),
    ],
)
def test_each_door_refusal_reads_in_plain_words_and_keeps_the_record(
    tmp_path, monkeypatch, status, code, words
):
    record = _admitted_epoch(tmp_path, monkeypatch)
    with pytest.raises(client.DirectWithdrawRefused) as refused:
        client.withdraw_submission(
            tmp_path,
            1,
            "external-signer",
            read=lambda url: _facts(),
            send=lambda url, body, headers: (status, {"refused": code}),
        )
    assert refused.value.code == code and words in refused.value.words
    assert record.exists()
    assert set(client.WITHDRAW_WORDS) >= {
        "withdraw_unavailable",
        "withdraw_too_late",
        "withdraw_submission_unknown",
        "withdraw_fields",
    }


def test_a_reply_of_any_other_shape_is_refused_and_the_record_kept(
    tmp_path, monkeypatch
):
    record = _admitted_epoch(tmp_path, monkeypatch)
    for reply in (
        {"withdrawn": "task-2", "grade_state": "WITHDRAWN_BY_MINER"},
        {"withdrawn": "task-1", "grade_state": "WITHDRAWN_BY_MINER", "x": 1},
    ):
        with pytest.raises(client.DirectWithdrawRefused):
            client.withdraw_submission(
                tmp_path,
                1,
                "external-signer",
                read=lambda url: _facts(),
                send=lambda url, body, headers, reply=reply: (200, reply),
            )
    assert record.exists()


def test_without_an_admission_record_there_is_nothing_to_withdraw(tmp_path):
    with pytest.raises(client.DirectWithdrawRefused) as refused:
        client.withdraw_submission(tmp_path, 1, "external-signer")
    assert refused.value.code == "no_queued_submission"


def _poll_send(states, submits):
    """A door whose status answers come from ``states`` (task -> outcome state, or "withdrawn"), counting SUBMITs."""
    from test_direct_submission import _answer

    def send(url, body, headers):
        request = json.loads(body)
        if request["tool"] == client.SUBMIT_TOOL:
            submits.append(request["request"])
            return 202, _answer("ADMITTED", task_id=f"task-{len(submits)}")
        task = request["fields"]["submission_id"]
        if states.get(task) == "withdrawn":
            return 200, _answer(
                "FAILED_INFRA", task_id=task, failure={"code": "withdrawn_by_miner"}
            )
        return 200, _answer(states.get(task, "RECONSTRUCTED"), task_id=task)

    return send


@pytest.mark.parametrize("observe_only", [False, True])
def test_a_withdrawn_task_is_never_a_result_its_record_is_set_aside_and_nothing_resubmitted(
    tmp_path, monkeypatch, observe_only
):
    """The record was not set aside by the kit (the door answered 503 after its cancel, a crash after the 200, or a
    withdrawal from another client): the next submit or result read sets it aside and refuses ``withdrawn_by_miner``,
    an observation too, so no caller ever stores it as the round's verdict."""
    from test_direct_submission import _client

    record = _admitted_epoch(tmp_path, monkeypatch)
    submits = []
    send = _poll_send({"task-1": "withdrawn"}, submits)
    run = _client(tmp_path, monkeypatch, send, wait_s=10)
    if observe_only:
        from test_direct_submission import _CONTEXT, _CONTRACT, _RECEIVER, _URL, _recipe
        from test_direct_submission import _facts as plain_facts

        def run():
            return client.submit_and_wait(
                _URL,
                "external-signer",
                root=tmp_path,
                epoch=1,
                recipe=_recipe(),
                contract_digest=_CONTRACT,
                receiver=_RECEIVER,
                context=_CONTEXT,
                read=lambda url: plain_facts(),
                send=send,
                clock=lambda: 0.0,
                sleep=lambda seconds: None,
                wait_s=10,
                observe_only=True,
            )

    with pytest.raises(client.DirectIntakeRefusal) as refused:
        run()
    assert refused.value.code == "withdrawn_by_miner"
    assert "submit again when ready" in refused.value.words
    assert client.WITHDRAW_RETRY_WORDS in refused.value.words
    assert submits == []  # the admission was earlier: nothing was resubmitted by itself
    assert not record.exists()
    aside = tmp_path / "construction-intake-epoch-1.withdrawn-1.json"
    assert json.loads(aside.read_bytes())["submission_id"] == "task-1"
    # the next submit is a fresh request for a fresh task
    again = _client(tmp_path, monkeypatch, _poll_send({}, submits), wait_s=10)()
    assert again["task_id"] == "task-1" and len(submits) == 1
    assert submits[0].endswith("-r1")


def test_a_record_naming_a_newer_task_is_never_set_aside_for_an_older_withdrawal(
    tmp_path, monkeypatch
):
    record = _admitted_epoch(tmp_path, monkeypatch, task="task-2")
    before = record.read_bytes()
    assert (
        client._set_cancelled_record_aside(
            tmp_path, 1, record, label="withdrawn", task_id="task-1"
        )
        is False
    )
    assert record.read_bytes() == before
    assert not (tmp_path / "construction-intake-epoch-1.attempt").exists()


def test_a_set_aside_never_writes_over_an_existing_aside_copy(tmp_path, monkeypatch):
    record = _admitted_epoch(tmp_path, monkeypatch)
    taken = tmp_path / "construction-intake-epoch-1.withdrawn-1.json"
    taken.write_text("kept")
    assert client._set_cancelled_record_aside(
        tmp_path, 1, record, label="withdrawn", task_id="task-1"
    )
    assert taken.read_text() == "kept"
    moved = tmp_path / "construction-intake-epoch-1.withdrawn-2.json"
    assert json.loads(moved.read_bytes())["submission_id"] == "task-1"
    assert not record.exists()


def test_the_kit_re_reads_the_record_before_setting_it_aside(tmp_path, monkeypatch):
    """A newer submit recorded between the withdrawal's send and its set-aside is never moved."""
    record = _admitted_epoch(tmp_path, monkeypatch)
    newer = json.loads(record.read_bytes())
    newer["submission_id"] = "task-2"

    def send(url, body, headers):
        record.write_text(json.dumps(newer))
        return 200, {"withdrawn": "task-1", "grade_state": "WITHDRAWN_BY_MINER"}

    client.withdraw_submission(
        tmp_path, 1, "external-signer", read=lambda url: _facts(), send=send
    )
    assert json.loads(record.read_bytes())["submission_id"] == "task-2"
    assert not list(tmp_path.glob("construction-intake-epoch-1.withdrawn-*.json"))


# --- the campaign: withdraw during the submit's poll, then submit again in the SAME round ---------------------------


def _f08_answer(state, task, contract, challenge, **outcome):
    answer = {
        "schema": client.RESULT_SCHEMA,
        "kind": "OUTCOME",
        "code": None,
        "pinned": {
            "contract_digest": contract.digest,
            "rule_digest": "sha256:" + "b" * 64,
            "implementation_digest": "sha256:" + "c" * 64,
            "identities_digest": "sha256:" + "d" * 64,
        },
        "outcome": {
            "schema": client.OUTCOME_SCHEMA,
            "submission_id": task,
            "challenge": dict(challenge),
            "state": state,
            "evidence": contract.evidence_label,
            "qualification": False,
            "reward": False,
            "task_id": task,
            **outcome,
        },
        "evidence": "DEVELOPMENT",
        "qualification": False,
        "reward": False,
    }
    if state == "RECONSTRUCTED":
        answer["outcome"]["state_digest"] = "sha256:" + "e" * 64
        answer["outcome"]["predictions_digest"] = "sha256:" + "f" * 64
    return answer


@pytest.mark.parametrize("withdrawn_by", ["this_kit", "another_client"])
def test_a_withdraw_during_the_submit_poll_leaves_the_round_open_and_the_same_round_resubmits(
    tmp_path, monkeypatch, withdrawn_by
):
    """Freeze, submit, withdraw while the submit still polls the validator, then submit again in the SAME round: the
    withdrawn task is never stored as the round's verdict (no permitted feedback), the frozen candidate is kept, and the
    resubmission's result is the round's verdict."""
    import asyncio
    import dataclasses
    import functools

    from test_direct_submission import _CONTEXT
    from test_miner_freeze_submit import prepared as freeze_prepared

    from carbon.challenge_registry.campaigns import campaign_for
    from carbon.challenge_registry.direct import graph_recipe
    from carbon.development_session import (
        construction_recipe,
        direct_source_submission,
        research_report,
    )
    from carbon.development_session import research_campaign as rc
    from carbon.development_session.profile import canonical
    from carbon.direct_campaign.spec import F08
    from carbon.reconstruction.served_recipe_contract import registered

    version, receiver = "1.4", "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
    url = "http://127.0.0.1:8769"
    challenge = {"id": F08.challenge_id, "version": version}
    contract = registered(F08.challenge_id, version)
    recipe = graph_recipe(F08, "sha256:" + "a" * 64, version=version)
    value, _final = freeze_prepared(tmp_path / "c", monkeypatch, practiced=(recipe,))
    manifest = {**value.manifest, "construction_mode": "direct"}
    (value.ledger.root / "campaign-manifest.json").write_bytes(canonical(manifest))
    value = dataclasses.replace(
        value,
        manifest=manifest,
        campaign=campaign_for(challenge),
        args=SimpleNamespace(
            intakes={F08.challenge_id: url}, receivers={F08.challenge_id: receiver}
        ),
        sdk=SimpleNamespace(
            connection=SimpleNamespace(miner_key="miner-key", chain_context=_CONTEXT)
        ),
    )
    root = value.ledger.root
    monkeypatch.setattr(
        direct_source_submission, "stage_graph_source", lambda *a, **k: None
    )
    monkeypatch.setattr(research_report, "report", lambda *a, **k: None)
    # the frozen graph's source envelope from the miner's workspace (staged to the door by `stage_graph_source`, a stand-in)
    monkeypatch.setattr(
        construction_recipe, "graph_envelope_from_workspace", lambda *a: b"{}"
    )
    monkeypatch.setattr(
        client, "read_exam_feedback", lambda *a, **k: {"best": None, "latest": None}
    )
    monkeypatch.setattr(
        client,
        "BittensorMessageSigner",
        lambda signer: SimpleNamespace(sign=lambda body, **kw: {"signed": "fixture"}),
    )
    facts = {
        "schema": client.PUBLIC_SCHEMA,
        "network": _CONTEXT.network,
        "genesis": _CONTEXT.genesis_hash,
        "netuid": _CONTEXT.netuid,
        "challenge": challenge,
        "receiver": receiver,
        "snapshot": {"id": "snapshot-1"},
        "discovery_path": client.INFO_PATH,
        "path": client.SUBMIT_PATH,
        "tools": [client.SUBMIT_TOOL, client.STATUS_TOOL],
        "served_contracts": [{"level": 0, "digest": contract.digest}],
        "score_pack": None,
        "qualification": False,
        "reward": False,
        client.WITHDRAW_FACTS_NAME: dict(client.WITHDRAW_FACTS),
    }

    def answer(state, task, **outcome):
        return _f08_answer(state, task, contract, challenge, **outcome)

    submits, withdrawn, aside = [], set(), []

    def send(url, body, headers):
        request = json.loads(body)
        tool, fields = request["tool"], request["fields"]
        if tool == client.SUBMIT_TOOL:
            submits.append(request["request"])
            return 202, answer("ADMITTED", f"task-{len(submits)}")
        if tool == client.WITHDRAW_TOOL:
            withdrawn.add(fields["submission_id"])
            return 200, {
                "withdrawn": fields["submission_id"],
                "grade_state": "WITHDRAWN_BY_MINER",
            }
        task = fields["submission_id"]
        if task == "task-1" and task not in withdrawn:
            # the miner withdraws while this submit still polls the validator
            if withdrawn_by == "this_kit":
                client.withdraw_submission(
                    root, 1, "miner-key", read=lambda url: facts, send=send
                )
                aside.append(not (root / "construction-intake-epoch-1.json").exists())
            else:
                withdrawn.add(task)
            return 200, answer("ADMITTED", task)
        if task in withdrawn:
            return 200, answer(
                "FAILED_INFRA", task, failure={"code": "withdrawn_by_miner"}
            )
        return 200, answer("RECONSTRUCTED", task)

    clock = [0.0]
    monkeypatch.setattr(
        client,
        "submit_and_wait",
        functools.partial(
            client.submit_and_wait,
            read=lambda url: facts,
            send=send,
            clock=lambda: clock[0],
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        ),
    )
    asyncio.run(rc.freeze_candidate(value, strategy=recipe, reason="practised"))
    with pytest.raises(rc.OperationRefused, match="withdrawn_by_miner"):
        asyncio.run(rc.submit_frozen(value))
    folder = root / "epoch-1"
    assert not (folder / "permitted-final-feedback.json").exists()  # no verdict
    assert rc._open_epoch(value) == 1 and (folder / "selected-recipe.json").exists()
    assert not (root / "construction-intake-epoch-1.json").exists()
    kept = json.loads(
        (root / "construction-intake-epoch-1.withdrawn-1.json").read_bytes()
    )
    assert kept["submission_id"] == "task-1"
    assert aside == ([True] if withdrawn_by == "this_kit" else [])
    # the same round again: a fresh request, a fresh task, and ITS result is the round's verdict
    done = asyncio.run(rc.submit_frozen(value))
    assert done["epoch"] == 1 and done["feedback"]["result"]["task_id"] == "task-2"
    assert len(submits) == 2 and submits[1].endswith("-r1")
    stored = json.loads((folder / "permitted-final-feedback.json").read_bytes())
    assert stored["result"]["task_id"] == "task-2"
    assert rc._open_epoch(value) == 2


def test_no_background_verdict_read_stores_a_direct_campaigns_withdrawn_task():
    """The launchpad's background verdict read (`verdict_read.read_queued_verdict`) stores only through a Challenge's
    ``queued_verdict``, which no direct (recipe) campaign has: a withdrawn recipe task reaches the round's record only
    through `submit_and_wait`, which refuses it (above, an observation too)."""
    from carbon.battery import campaign as battery_campaign
    from carbon.challenge_registry.campaigns import implemented_campaigns

    reading = [
        campaign.queued_verdict
        for _entry, campaign in implemented_campaigns()
        if campaign.queued_verdict is not None
    ]
    # only the Battery's own (remote submission) campaign reads queued verdicts; no recipe campaign does
    assert reading and all(read is battery_campaign.queued_verdict for read in reading)


# --- the launchpad operation --------------------------------------------------------------------------------------


def test_the_withdraw_operation_is_a_gated_signed_non_read_operation():
    from scripts.dev.miner_launchpad import operations, practice_only

    op = operations.OPERATIONS["withdraw"]
    assert op.required == frozenset({"campaign"}) and op.admits_work is False
    assert op.gates == ("request", "profile", "campaign")
    assert "withdraw" not in operations.READ_ONLY_OPERATIONS
    assert "withdraw" in practice_only.REGISTERED_ONLY
    # the retries a withdrawal costs the same model are said plainly, digit-free (the bound is not public)
    said = "counts toward the validator's limit of retries for that model on this exam"
    assert said in op.summary and said in client.WITHDRAWN_WORDS
    assert not any(ch.isdigit() for ch in client.WITHDRAW_RETRY_WORDS)
    from scripts.dev.miner_launchpad.supervisor import NEXT_ACTIONS

    assert (
        NEXT_ACTIONS["withdrawn_by_miner"]
        == client.WITHDRAW_WORDS["withdrawn_by_miner"]
    )
    from carbon.miner_mcp.mcp_operations import operation_tool_names

    assert "carbon_withdraw" in operation_tool_names()
    app = Path(operations.__file__).with_name("app.js").read_text(encoding="utf-8")
    assert '"/api/v1/operations/withdraw"' in app


def _runner_host(tmp_path, monkeypatch, behaviour):
    from carbon.development_session import direct_submission

    calls = []

    def withdraw_submission(root, epoch, signer):
        calls.append((Path(root), epoch, signer))
        return behaviour()

    monkeypatch.setattr(direct_submission, "withdraw_submission", withdraw_submission)
    host = SimpleNamespace(
        verdict_signer=lambda cfg: "miner-signer",
        configured=dict,
        read=lambda identity: {"id": identity, "state": "READY"},
    )
    admitted = SimpleNamespace(campaign={"id": "c1", "root": str(tmp_path)})
    return host, admitted, calls


def test_the_runner_withdraws_the_latest_submitted_epoch(tmp_path, monkeypatch):
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    for name in (
        "construction-intake-epoch-1.json",
        "construction-intake-epoch-3.json",
        "construction-intake-epoch-4.cancelled-1.json",
    ):
        (tmp_path / name).write_text("{}")
    host, admitted, calls = _runner_host(
        tmp_path,
        monkeypatch,
        lambda: {"withdrawn": "t", "grade_state": "WITHDRAWN_BY_MINER"},
    )
    assert RunnerAdapter.withdraw_admitted(host, admitted, {}) == {
        "id": "c1",
        "state": "READY",
    }
    assert calls == [(tmp_path, 3, "miner-signer")]


def test_the_runner_says_each_refusal_in_words(tmp_path, monkeypatch):
    from scripts.dev.miner_launchpad.controller import Rejected
    from scripts.dev.miner_launchpad.runner import RunnerAdapter

    host, admitted, _calls = _runner_host(tmp_path, monkeypatch, dict)
    with pytest.raises(Rejected) as refused:
        RunnerAdapter.withdraw_admitted(host, admitted, {})
    assert refused.value.code == "no_queued_submission"
    assert refused.value.next_step == client.WITHDRAW_WORDS["no_queued_submission"]
    (tmp_path / "construction-intake-epoch-2.json").write_text("{}")

    def too_late():
        raise client.DirectWithdrawRefused("withdraw_too_late")

    host, admitted, _calls = _runner_host(tmp_path, monkeypatch, too_late)
    with pytest.raises(Rejected) as refused:
        RunnerAdapter.withdraw_admitted(host, admitted, {})
    assert (refused.value.code, refused.value.status) == ("withdraw_too_late", 409)
    assert "can no longer be withdrawn" in refused.value.next_step
