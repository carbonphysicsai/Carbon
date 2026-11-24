"""miner_lookup's 5th source (V2 6111 (3); door-code 6089 (b); Torres rtsk_24f42560): a build that ended in the door's task
store with no ledger row after its admission (a REFUSED graph) reads as the door's own reply says (RECONSTRUCTION_FAILED),
never QUEUED; and a submission the door re-ran under a new id reads RERUN with that id (the v12 rule, from the ledger).

The views are REAL canonical bytes (`carbon.research.canonical_bytes` of a `DirectTaskViewV3`), decoded by the lookup's own
stdlib reader, which keeps only the task state and the public refusal code. Synthetic ids only.
"""

from __future__ import annotations

import sqlite3

from test_miner_lookup import CANARY, HOTKEY, OTHER, T0, _ask, _marker, _seed

from carbon import research
from carbon.research.refs import RESEARCH_DOCUMENT_HEADER
from scripts.dev import miner_lookup as ml

TASK = "rtsk_" + "5a" * 32
NEW = "rtsk_" + "6b" * 32
KEY = research.ChallengeKey("electric-motor-magnetics", "1.8")
BINDINGS = research.DirectTaskBindingsV3(
    KEY, *("sha256:" + c * 64 for c in "123456789")
)


def _view(task, state, refusal=None):
    state = research.DirectTaskStateV3(state)
    receipt = None
    if state in (
        research.DirectTaskStateV3.REFUSED,
        research.DirectTaskStateV3.FAILED_INFRA,
    ):
        infra = (
            research.InfrastructureFailureClass.INTERNAL
            if state is research.DirectTaskStateV3.FAILED_INFRA
            else None
        )
        receipt = research.DirectTaskReceiptV3(
            research.ResearchTaskId(task),
            state,
            BINDINGS,
            None,
            None,
            infra,
            refusal,
            2_000,
            ("PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",),
        )
    view = research.DirectTaskViewV3(
        research.ResearchTaskId(task), KEY, state, 1, 1_000, 2_000, BINDINGS, receipt
    )
    return research.canonical_bytes(view)


def _tasks(path, rows):
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE direct_tasks (id TEXT PRIMARY KEY, request BLOB NOT NULL, view BLOB NOT NULL, cancellation TEXT)"
    )
    for task, view in rows:
        db.execute(
            "INSERT INTO direct_tasks VALUES(?,?,?,NULL)", (task, CANARY.encode(), view)
        )
    db.commit()
    db.close()
    return path


def test_the_lookup_pins_the_doors_header_and_states():
    assert ml.VIEW_HEADER == RESEARCH_DOCUMENT_HEADER
    assert ml.TASK_STORE_STATES == tuple(s.value for s in research.DirectTaskStateV3)
    assert "rerun_task_id" in ml.ALLOWED_FIELDS["task"]
    assert ml._words("RERUN") and ml._words(ml.CANDIDATE_BUILD_REFUSED)


def test_view_tokens_keep_only_the_state_and_the_public_refusal_code():
    raw = _view(TASK, "REFUSED", "graph_submission_invalid")
    assert ml.view_tokens(raw, TASK) == ("REFUSED", "graph_submission_invalid")
    assert ml.view_tokens(_view(TASK, "QUEUED"), TASK) == ("QUEUED", None)
    # a code outside the public token shape is never kept; another task's view, a cut or foreign blob says nothing
    assert ml.view_tokens(_view(TASK, "REFUSED", "graph-submission"), TASK) == (
        "REFUSED",
        None,
    )
    assert ml.view_tokens(raw, NEW) == (None, None)
    assert ml.view_tokens(raw[:-3], TASK) == (None, None)
    assert ml.view_tokens(raw + b"\x00", TASK) == (None, None)
    assert ml.view_tokens(b"not a view", TASK) == (None, None)
    assert ml.view_tokens(None, TASK) == (None, None)


def test_a_refused_build_reads_reconstruction_failed_not_queued(tmp_path):
    _seed(
        tmp_path / "attempts.sqlite3",
        [
            (T0, "RECEIVED", None, HOTKEY, TASK, None),
            (T0 + 5, "OUTCOME", None, HOTKEY, TASK, "ADMITTED"),
        ],
    )
    # without the 5th source (no config): unchanged, as before
    assert _ask(tmp_path, "task", TASK)[0]["task"]["state"] == "QUEUED"
    tasks = _tasks(
        tmp_path / "direct-tasks.sqlite3",
        [(TASK, _view(TASK, "REFUSED", "graph_submission_invalid"))],
    )
    document, text = _ask(tmp_path, "task", TASK, tasks=tasks)
    shown = document["task"]
    assert shown["state"] == "RECONSTRUCTION_FAILED"
    assert shown["outcome_code"] == ml.CANDIDATE_BUILD_REFUSED
    assert shown["reason"] == ml._words(ml.CANDIDATE_BUILD_REFUSED)
    assert set(shown) <= ml.ALLOWED_FIELDS["task"] and CANARY not in text
    # a Carbon-side end with no marker reads FAILED_INFRA; a store still QUEUED stays QUEUED
    _tasks(tmp_path / "t2.sqlite3", [(TASK, _view(TASK, "FAILED_INFRA"))])
    assert (
        _ask(tmp_path, "task", TASK, tasks=tmp_path / "t2.sqlite3")[0]["task"]["state"]
        == "FAILED_INFRA"
    )
    _tasks(tmp_path / "t3.sqlite3", [(TASK, _view(TASK, "QUEUED"))])
    assert (
        _ask(tmp_path, "task", TASK, tasks=tmp_path / "t3.sqlite3")[0]["task"]["state"]
        == "QUEUED"
    )
    # an absent store file says nothing (QUEUED as before), never a refusal of the whole answer
    assert (
        _ask(tmp_path, "task", TASK, tasks=tmp_path / "missing.sqlite3")[0]["task"][
            "state"
        ]
        == "QUEUED"
    )


def _grant(path, new, old, hotkey):
    db = sqlite3.connect(path)
    db.execute(
        "INSERT INTO queue_place_grants(contract_digest,new_task,from_task,hotkey,place_seq,granted_ns) VALUES(?,?,?,?,?,?)",
        ("d" * 8, new, old, hotkey, 1, 1),
    )
    db.commit()
    db.close()


def test_a_door_rerun_reads_rerun_with_the_new_id(tmp_path):
    _seed(
        tmp_path / "attempts.sqlite3",
        [
            (T0, "OUTCOME", None, HOTKEY, TASK, "ADMITTED"),
            (T0 + 9, "OUTCOME", ml.BUILD_REQUEUED, HOTKEY, NEW, "ADMITTED"),
        ],
    )
    _grant(tmp_path / "attempts.sqlite3", NEW, TASK, HOTKEY)
    shown = _ask(tmp_path, "task", TASK)[0]["task"]
    assert shown["state"] == "RERUN" and shown["rerun_task_id"] == NEW
    assert shown["charged"] == "no" and shown["reason"] == ml._words("RERUN")


def test_a_miners_own_resubmission_or_another_hotkeys_task_is_not_a_rerun(tmp_path):
    _seed(
        tmp_path / "attempts.sqlite3",
        [
            (T0, "OUTCOME", None, HOTKEY, TASK, "ADMITTED"),
            (
                T0 + 9,
                "OUTCOME",
                None,
                HOTKEY,
                NEW,
                "ADMITTED",
            ),  # a grant without the door's requeue code
        ],
    )
    _grant(tmp_path / "attempts.sqlite3", NEW, TASK, HOTKEY)
    shown = _ask(tmp_path, "task", TASK)[0]["task"]
    assert shown["state"] == "QUEUED" and "rerun_task_id" not in shown
    other = tmp_path / "other"
    other.mkdir()
    _seed(
        other / "attempts.sqlite3",
        [
            (T0, "OUTCOME", None, HOTKEY, TASK, "ADMITTED"),
            (T0 + 9, "OUTCOME", ml.BUILD_REQUEUED, OTHER, NEW, "ADMITTED"),
        ],
    )
    _grant(other / "attempts.sqlite3", NEW, TASK, OTHER)
    assert "rerun_task_id" not in _ask(other, "task", TASK)[0]["task"]


def test_a_door_reruns_own_graded_task_reads_uncharged(tmp_path):
    """v2 6168 / live-ops 6183 (rtsk_3b596e44): the re-run's slot is COUNTED (it stands on the board) but it took no try;
    the lookup says charged no and the re-run sentence, never 'counted as your try'."""
    _seed(
        tmp_path / "attempts.sqlite3",
        [(T0, "OUTCOME", ml.BUILD_REQUEUED, HOTKEY, NEW, "ADMITTED")],
        slots=[(NEW, HOTKEY, "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")],
    )
    _marker(tmp_path, NEW, state="GRADED", code=None)
    shown = _ask(tmp_path, "task", NEW)[0]["task"]
    assert shown["state"] == "GRADED" and shown["charged"] == "no"
    assert shown["reason"] == ml.REQUEUED_REASON
    # the exam cap's own requeue row alone says the same (a re-run whose first ledger code is not the requeue's)
    other = tmp_path / "second"
    other.mkdir()
    _seed(
        other / "attempts.sqlite3",
        [(T0, "OUTCOME", None, HOTKEY, NEW, "ADMITTED")],
        slots=[(NEW, HOTKEY, "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")],
    )
    db = sqlite3.connect(other / "attempts.sqlite3")
    db.execute("INSERT INTO exam_requeues(submission_id,attempt,queued_ns,reserved_ns) VALUES(?,?,?,?)", (NEW, 2, 1, 2))
    db.commit()
    db.close()
    _marker(other, NEW, state="GRADED", code=None)
    assert _ask(other, "task", NEW)[0]["task"]["charged"] == "no"
    # an ordinary graded task is still charged
    plain = tmp_path / "third"
    plain.mkdir()
    _seed(
        plain / "attempts.sqlite3",
        [(T0, "OUTCOME", None, HOTKEY, TASK, "ADMITTED")],
        slots=[(TASK, HOTKEY, "COUNTED", "SCORED_DEVELOPMENT_CANDIDATE")],
    )
    _marker(plain, TASK, state="GRADED", code=None)
    seen = _ask(plain, "task", TASK)[0]["task"]
    assert seen["charged"] == "yes" and seen["reason"] != ml.REQUEUED_REASON
