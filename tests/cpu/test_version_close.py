"""Owner decision #9 (8 Nov): at a version flip the submissions still queued on the old version are CLOSED, NOT GRADED,
NOTHING CHARGED, with a typed, miner-visible ``version_closed`` (`carbon.challenge_validator.version_close`).

Claims: the closer marks exactly the tasks the grader never marked, writes no attempt / exam-cap / recipe-copy row, and
is idempotent; the old root's grader then grades none of them and v4 says NOT_GRADED; the new door answers the owner's
own closed id with ``version_closed`` (410) and everyone else, and any other id, with ``feedback_submission_unknown``;
a configured file that is not an earlier version's of this Challenge refuses the start. Synthetic ids only.
"""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import auto_grade, direct_intake, direct_receiver
from carbon.challenge_validator import version_close as vc
from carbon.challenge_validator.ledger import AttemptLedger

CHALLENGE, OLD, NEW = "electric-motor-magnetics", "1.5", "1.8"
T = ["rtsk_" + c * 64 for c in "abcde"]
HOT_A, HOT_B = "5" + "A" * 47, "5" + "B" * 47
CONTRACT = "sha256:" + "c" * 64


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "_contract", lambda cid, ver: CONTRACT)
    (tmp_path / "auto-grade" / "markers").mkdir(parents=True)
    ledger = AttemptLedger(tmp_path / "attempts.sqlite3")
    for n, (sid, hotkey) in enumerate(
        [(T[0], HOT_A), (T[1], HOT_B), (T[2], HOT_A), (T[3], HOT_B)]
    ):
        ledger.record(
            SimpleNamespace(
                hotkey=hotkey,
                receipt={"sequence": n + 1, "digest": "d", "block": 100 + n},
                contract_digest=CONTRACT,
            ),
            kind="OUTCOME",
            submission_id=sid,
        )
    # T[1] was graded and T[3] failed on Carbon's side before the flip: their outcomes stand
    for sid, state in ((T[1], "GRADED"), (T[3], "FAILED")):
        (tmp_path / "auto-grade" / "markers" / (sid + ".json")).write_text(
            json.dumps(
                {
                    "schema": auto_grade.SCHEMA,
                    "submission_id": sid,
                    "state": state,
                    "code": None,
                    "entry_id": None,
                }
            )
        )
    return tmp_path


def _rows(path):
    with sqlite3.connect(path) as db:
        tables = [
            r[0]
            for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ]
        return {
            t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables
        }


def test_the_closer_marks_only_the_never_graded_and_charges_nothing(root):
    before = _rows(root / "attempts.sqlite3")
    document = vc.close_queued(root, challenge_id=CHALLENGE, version=OLD)
    assert document["closed"] == [
        {"submission_id": T[0], "owner": HOT_A},
        {"submission_id": T[2], "owner": HOT_A},
    ]
    assert document["challenge"] == {"id": CHALLENGE, "version": OLD}
    assert document["code"] == "version_closed"
    for sid in (T[0], T[2]):
        marker = json.loads(
            (root / "auto-grade" / "markers" / (sid + ".json")).read_text()
        )
        assert (
            marker["state"] == "VERSION_CLOSED" and marker["code"] == "version_closed"
        )
    for sid, state in ((T[1], "GRADED"), (T[3], "FAILED")):
        marker = json.loads(
            (root / "auto-grade" / "markers" / (sid + ".json")).read_text()
        )
        assert marker["state"] == state
    # nothing charged: not one row in any table of the attempts ledger (attempts, exam cap, recipe copies)
    assert _rows(root / "attempts.sqlite3") == before
    assert json.loads((root / vc.FILE).read_bytes()) == document


def test_the_closer_is_idempotent_and_its_file_written_once(root):
    first = vc.close_queued(root, challenge_id=CHALLENGE, version=OLD)
    assert vc.close_queued(root, challenge_id=CHALLENGE, version=OLD) == first
    (root / vc.FILE).write_text("{}")
    with pytest.raises(vc.VersionCloseRefused, match="file_differs"):
        vc.close_queued(root, challenge_id=CHALLENGE, version=OLD)


def test_the_closer_refuses_a_root_that_is_not_a_grading_door(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "_contract", lambda cid, ver: CONTRACT)
    with pytest.raises(vc.VersionCloseRefused, match="not_a_grading_door_root"):
        vc.close_queued(tmp_path, challenge_id=CHALLENGE, version=OLD)


def test_the_old_roots_grader_grades_none_of_them(root):
    vc.close_queued(root, challenge_id=CHALLENGE, version=OLD)
    adapter = SimpleNamespace(
        ledger=AttemptLedger(root / "attempts.sqlite3"), contract_digest=CONTRACT
    )
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.intake = SimpleNamespace(adapter=adapter)
    grader.markers = root / "auto-grade" / "markers"
    assert grader.pending() == []


def _intake(owners, closed=None, markers=None):
    intake = SimpleNamespace(
        adapter=SimpleNamespace(owner=lambda sid: owners.get(sid)),
        grade_marker=lambda sid: (markers or {}).get(sid),
    )
    if closed is not None:
        intake.version_closed = closed
    return intake


def _ask(intake, hotkey, sid):
    return direct_intake.DirectRecipeIntake._feedback(
        intake, hotkey, submission_id=sid, v4=True
    )


def test_the_new_door_tells_the_owner_its_submission_was_closed(root):
    document = vc.close_queued(root, challenge_id=CHALLENGE, version=OLD)
    closed = {r["submission_id"]: r["owner"] for r in document["closed"]}
    intake = _intake({}, closed)
    told = _ask(intake, HOT_A, T[0])
    assert told.status == 410 and told.body == {"refused": "version_closed"}
    # another hotkey asking about A's closed id, and anyone asking about an id that was not closed: unknown
    for hotkey, sid in ((HOT_B, T[0]), (HOT_A, T[1]), (HOT_B, T[4])):
        other = _ask(intake, hotkey, sid)
        assert (
            other.status == 404
            and other.body["refused"] == "feedback_submission_unknown"
        )


def test_a_door_without_the_files_answers_as_before():
    told = _ask(_intake({}), HOT_A, T[0])
    assert told.status == 404 and told.body["refused"] == "feedback_submission_unknown"


def test_on_the_old_root_v4_says_not_graded():
    intake = _intake(
        {T[0]: HOT_A},
        markers={T[0]: {"state": "VERSION_CLOSED", "code": "version_closed"}},
    )
    intake._grade_state_v4 = lambda hotkey, sid: (
        direct_intake.DirectRecipeIntake._grade_state_v4(intake, hotkey, sid)
    )
    assert direct_intake.DirectRecipeIntake._grade_state_v4(intake, HOT_A, T[0]) == (
        "NOT_GRADED",
        None,
    )


# --- the new door's configuration ------------------------------------------------------------------------------------


def _file(tmp_path, root, **change):
    document = vc.close_queued(root, challenge_id=CHALLENGE, version=OLD)
    path = tmp_path / "closed.json"
    path.write_text(json.dumps({**document, **change}))
    return str(path)


def test_the_door_loads_an_earlier_versions_file(tmp_path, root):
    path = _file(tmp_path, root)
    cfg = {
        "challenge": {"id": CHALLENGE, "version": NEW},
        "version_closed_files": [path],
    }
    assert direct_receiver._version_closed(cfg) == {T[0]: HOT_A, T[2]: HOT_A}
    assert direct_receiver._version_closed({"challenge": cfg["challenge"]}) == {}


@pytest.mark.parametrize(
    "change",
    [
        {"challenge": {"id": CHALLENGE, "version": NEW}},  # the door's own version
        {"challenge": {"id": "chip-cold-plate", "version": OLD}},  # another Challenge
        {"schema": "x"},
        {"code": "other"},
        {"closed": [{"submission_id": T[0]}]},
    ],
)
def test_a_file_that_is_not_an_earlier_versions_refuses_the_start(
    tmp_path, root, change
):
    path = _file(tmp_path, root, **change)
    cfg = {
        "challenge": {"id": CHALLENGE, "version": NEW},
        "version_closed_files": [path],
    }
    with pytest.raises(ValueError):
        direct_receiver._version_closed(cfg)


@pytest.mark.parametrize(
    "selected", [[], ["relative/closed.json"], "not-a-list", ["/no/such/closed.json"]]
)
def test_a_bad_selection_refuses_the_start(selected):
    cfg = {
        "challenge": {"id": CHALLENGE, "version": NEW},
        "version_closed_files": selected,
    }
    with pytest.raises(ValueError):
        direct_receiver._version_closed(cfg)


def test_the_field_is_an_allowed_optional_receiver_field():
    assert "version_closed_files" in direct_receiver._OPTIONAL_FIELDS
