"""G-LEAD-10 row 1 (owner 20 Nov 2026; V2 part (1) spec 13:11Z): a build that ended on the candidate's OWN failure uses the
daily spot, with a typed reason and no rebuild.

Claims:
(a) only the structured recipe-side end files a spot: REFUSED + ``candidate_program_failed`` + a FAILED_MINER build or
    build-pipeline inference child; every look-alike files none (a GPU-lane FAILED_MINER under FAILED_INFRA, a campaign
    limit, a refused graph, the door's CPU worker wall, no FAILED_MINER child);
(b) ONE spot per task in its own table (idempotent), counted against the DAILY allowance only (not the round: V2 23:2xZ),
    never an exam_graded row (no score, no copy rule, no board / ladder / crown input);
(c) a later Carbon-side ruling gives it back (``return-build-spot``), once, logged;
(d) the miner's v11 row says side yours, charged, spot used (v10 keeps None); a returned or never-filed spot shows no
    row;
(e) prospective: nothing reads past REFUSED builds, the door files only right after a build run ends.
SYNTHETIC ledgers, tasks and providers; no build runs.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import exam_cap, infra_requeue, lean_recipe
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.development_session import infra_diagnosis
from carbon.development_session.bundle_construction_worker import (
    direct_child_identity,
)
from carbon.reconstruction.worker.model import WorkerCode
from carbon.research import DirectTaskStateV3

HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
MOTOR = ("electric-motor-magnetics", "1.0")
TASK = "rtsk_" + "a" * 64
OTHER = "rtsk_" + "b" * 64
THIRD = "rtsk_" + "c" * 64


def _cadence(capacity):
    return {
        "capacity_gpu_lane_hours_per_day": capacity,
        "rebuild_gpu_lane_hours": {"electric-motor-magnetics": 4.7},
        "lanes": 1,
        "measurement_digest": "sha256:" + "a" * 64,
        "class_record_digest": "sha256:" + "b" * 64,
    }


def _cap(tmp_path, capacity=9.4, root=None):
    """9.4 lane-hours at 4.7 a rebuild: one active miner may use 2 spots a day (fixture values)."""
    directory = root or (tmp_path / "ledger")
    directory.mkdir(mode=0o700, exist_ok=True)
    return exam_cap.ExamCap(
        AttemptLedger(directory / "attempts.sqlite3"),
        cadence=_cadence(capacity),
        clock=lambda: 1_000_000_000_000,
    )


def _spend(cap, task, block):
    return cap.file_build_spent(
        hotkey=HOTKEY,
        challenge_id=MOTOR[0],
        challenge_version=MOTOR[1],
        submission_id=task,
        block=block,
        code=lean_recipe.RECIPE_SPOT_CODE,
    )


def _reserve(cap, task, block):
    return cap.reserve(
        hotkey=HOTKEY,
        challenge_id=MOTOR[0],
        challenge_version=MOTOR[1],
        exam_key="sha256:" + "1" * 64,
        submission_id=task,
        block=block,
    )


# --- (b) the spot counts like a grade, in its own table ------------------------------------------------------------


def test_a_recipe_spot_uses_the_day_not_the_round_and_is_filed_once(tmp_path):
    cap = _cap(tmp_path)
    assert _spend(cap, TASK, 360 * 5 + 1) is True
    assert _spend(cap, TASK, 360 * 5 + 1) is False  # idempotent: one spot per task
    # the round stays open (a build sees only public inputs: a retry in the round probes no exam)
    cap.settle(_reserve(cap, OTHER, 360 * 5 + 300), "SCORED_DEVELOPMENT_CANDIDATE")
    # the day: 2 a day here; the spot + one grade use both
    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        _reserve(cap, THIRD, 360 * 7)
    assert refused.value.code == "exam_daily_allowance_reached"
    # the rolling day moves on
    cap.settle(_reserve(cap, THIRD, 360 * 26), "SCORED_DEVELOPMENT_CANDIDATE")


def test_a_spot_only_group_is_not_an_active_miner(tmp_path):
    """V2 (2): the allowance's M sizes GRADE lane capacity; a group whose only use is a crashed build is not in it."""
    cap = _cap(tmp_path, capacity=9.4)
    other = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
    cap.file_build_spent(
        hotkey=other,
        challenge_id=MOTOR[0],
        challenge_version=MOTOR[1],
        submission_id=OTHER,
        block=360,
        code=lean_recipe.RECIPE_SPOT_CODE,
    )
    assert cap.allowance(hotkey=HOTKEY, block=360)["active_miners"] == 1


def test_the_spot_is_never_an_exam_row_or_a_grade(tmp_path):
    cap = _cap(tmp_path)
    _spend(cap, TASK, 360)
    assert (
        cap.count(hotkey=HOTKEY, challenge_id=MOTOR[0]) == 0
    )  # no exam_graded row: no copy rule, board, ladder or crown input
    with cap.ledger._db() as db:
        assert (
            db.execute(
                "SELECT COUNT(*) FROM exam_graded WHERE submission_id=?", (TASK,)
            ).fetchone()[0]
            == 0
        )
    assert cap.build_spent(TASK) == {
        "code": lean_recipe.RECIPE_SPOT_CODE,
        "epoch": 1,
        "returned": False,
    }
    assert cap.build_spent(OTHER) is None


def test_a_returned_spot_no_longer_counts(tmp_path):
    cap = _cap(tmp_path)
    _spend(cap, TASK, 360 * 5 + 1)
    cap.settle(_reserve(cap, OTHER, 360 * 6), "SCORED_DEVELOPMENT_CANDIDATE")
    assert cap.return_build_spot(TASK)["code"] == lean_recipe.RECIPE_SPOT_CODE
    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        cap.return_build_spot(TASK)
    assert refused.value.code == "build_spot_return_no_row"
    _reserve(cap, THIRD, 360 * 7)  # the day has room again (2 a day: the grade only)
    assert cap.build_spent(TASK)["returned"] is True


# --- (c) the operator path ---------------------------------------------------------------------------------------------


def test_return_build_spot_needs_a_ruling_and_runs_once(tmp_path):
    root = tmp_path / "door"
    cap = _cap(tmp_path, root=root)
    _spend(cap, TASK, 360)
    assert infra_requeue.return_build_spot(root, [TASK], ruling="nope!")["refused"] == {
        "*": "ruling_id_required"
    }
    ruling = "V2-RECLASS-20261121"
    dry = infra_requeue.return_build_spot(root, [TASK, OTHER, "x"], ruling=ruling)
    assert dry["returned"] == [TASK]
    assert dry["refused"] == {OTHER: "no_build_spot", "x": "not_a_task_id"}
    assert cap.build_spent(TASK)["returned"] is False  # a dry run changes nothing
    done = infra_requeue.return_build_spot(root, [TASK], ruling=ruling, apply=True)
    assert done["returned"] == [TASK] and done["refused"] == {}
    again = infra_requeue.return_build_spot(root, [TASK], ruling=ruling, apply=True)
    assert again["refused"] == {TASK: "already_returned"}
    lines = (
        root / "auto-grade/requeued" / infra_requeue.BUILD_SPOT_RETURNS
    ).read_text()
    assert [json.loads(line)["task"] for line in lines.splitlines()] == [TASK]


# --- (a) the detector: the structured end and its look-alikes ---------------------------------------------------------


def _provider(children):
    """A provider whose ledger holds ``children``: ``{phase: (state, result dict)}`` for TASK."""
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE operations(id TEXT, owner TEXT, state TEXT, result TEXT)")
    for phase, (state, result) in children.items():
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?)",
            (direct_child_identity(TASK, phase), HOTKEY, state, json.dumps(result)),
        )

    @contextlib.contextmanager
    def connection():
        yield db

    return SimpleNamespace(ledger=SimpleNamespace(db=connection))


def _task(state, code):
    return SimpleNamespace(
        state=state, terminal_receipt=SimpleNamespace(refusal_code=code)
    )


REFUSED = DirectTaskStateV3.REFUSED
PROGRAM = {"failure_code": "reconstruction.worker.program.failed", "observation": "x"}
WALL = {"failure_code": WorkerCode.DEADLINE.value, "observation": "x"}


@pytest.mark.parametrize(
    "task, children",
    [
        (
            _task(REFUSED, "candidate_program_failed"),
            {"build": ("FAILED_MINER", PROGRAM)},
        ),
        # the build-pipeline inference child's own failure (not the CPU worker wall)
        (
            _task(REFUSED, "candidate_program_failed"),
            {"build": ("SUCCEEDED", {}), "inference": ("FAILED_MINER", PROGRAM)},
        ),
        # the build wall on a QUIET box settles FAILED_MINER (a busy box's never does)
        (_task(REFUSED, "candidate_program_failed"), {"build": ("FAILED_MINER", WALL)}),
    ],
)
def test_the_structured_recipe_side_end_uses_the_spot(task, children):
    code = lean_recipe.recipe_spot_code(_provider(children), HOTKEY, TASK, task)
    assert code == lean_recipe.RECIPE_SPOT_CODE


@pytest.mark.parametrize(
    "task, children",
    [
        # a GPU-lane build's FAILED_MINER under a FAILED_INFRA task (`_gpu_build_failure_is_carbons`)
        (
            _task(DirectTaskStateV3.FAILED_INFRA, None),
            {"build": ("FAILED_MINER", PROGRAM)},
        ),
        # REFUSED by a campaign limit: no FAILED_MINER child, another code
        (_task(REFUSED, "time_limit_reached"), {}),
        (_task(REFUSED, "miner_ceiling_reached"), {}),
        # a refused graph or a Carbon capability gap
        (
            _task(REFUSED, "candidate_build_refused"),
            {"build": ("FAILED_MINER", PROGRAM)},
        ),
        (_task(REFUSED, "carbon_capability_gap"), {}),
        # the door's CPU worker wall: Carbon's class carbon_cpu_worker_wall
        (
            _task(REFUSED, "candidate_program_failed"),
            {"build": ("SUCCEEDED", {}), "inference": ("FAILED_MINER", WALL)},
        ),
        # the right code with no FAILED_MINER child: unproven, never the candidate's
        (_task(REFUSED, "candidate_program_failed"), {"build": ("FAILED_INFRA", {})}),
        (_task(DirectTaskStateV3.SUCCEEDED, None), {}),
        (_task(REFUSED, "candidate_program_failed"), {}),
    ],
)
def test_every_look_alike_uses_no_spot(task, children):
    assert lean_recipe.recipe_spot_code(_provider(children), HOTKEY, TASK, task) is None


def test_an_unreadable_task_or_ledger_uses_no_spot():
    broken = SimpleNamespace(ledger=SimpleNamespace(db=None))
    task = _task(REFUSED, "candidate_program_failed")
    assert lean_recipe.recipe_spot_code(broken, HOTKEY, TASK, task) is None
    assert lean_recipe.recipe_spot_code(_provider({}), HOTKEY, TASK, None) is None


# --- (e) the door files right after a build run ends ------------------------------------------------------------------


def test_the_door_files_once_after_a_recipe_crash_and_never_raises(
    tmp_path, monkeypatch
):
    import carbon.research

    cap = _cap(tmp_path)
    provider = _provider({"build": ("FAILED_MINER", PROGRAM)})
    provider.get_research_result = lambda request: SimpleNamespace(
        task=_task(REFUSED, "candidate_program_failed")
    )
    monkeypatch.setattr(
        carbon.research, "DirectGetTaskRequestV3", lambda key, task_id: task_id
    )
    monkeypatch.setattr(exam_cap, "submission_block", lambda *a: 360 * 3)
    door = SimpleNamespace(
        discovery=SimpleNamespace(info=SimpleNamespace(challenge_key="key")),
        ledger=cap.ledger,
        contract_digest="sha256:" + "c" * 64,
        challenge_id=MOTOR[0],
        challenge_version=MOTOR[1],
    )
    task_id = SimpleNamespace(value=TASK)
    file = lean_recipe.LeanRecipeAdapter._file_recipe_spot
    assert file(door, HOTKEY, task_id, provider) == lean_recipe.RECIPE_SPOT_CODE
    assert file(door, HOTKEY, task_id, provider) == lean_recipe.RECIPE_SPOT_CODE
    assert cap.build_spent(TASK) == {
        "code": lean_recipe.RECIPE_SPOT_CODE,
        "epoch": 3,
        "returned": False,
    }
    # no block on record: nothing filed (the spot stays the miner's)
    monkeypatch.setattr(exam_cap, "submission_block", lambda *a: None)
    door.contract_digest = "other"
    task_id = SimpleNamespace(value=OTHER)
    assert file(door, HOTKEY, task_id, provider) is None
    assert cap.build_spent(OTHER) is None
    # anything raising inside: None, never an exception into the build round
    provider.get_research_result = None
    assert file(door, HOTKEY, task_id, provider) is None


# --- (d) what the miner sees -------------------------------------------------------------------------------------------


def test_the_miner_row_says_yours_charged_and_spot_used(tmp_path):
    from carbon.challenge_validator.direct_intake import DirectRecipeIntake

    cap = _cap(tmp_path)
    intake = SimpleNamespace(adapter=SimpleNamespace(ledger=cap.ledger))
    assert DirectRecipeIntake._recipe_spot_row(intake, TASK) is None  # never filed
    _spend(cap, TASK, 360)
    row = DirectRecipeIntake._recipe_spot_row(intake, TASK)
    assert tuple(row) == infra_diagnosis.PUBLIC_ROW_KEYS
    assert row["code"] == lean_recipe.RECIPE_SPOT_CODE
    assert (row["side"], row["charged"], row["retried_or_owed"]) == (
        "yours",
        True,
        "not rebuilt",
    )
    assert "spot was used" in row["next_step"]
    # not a Carbon class: never in the FAILED_INFRA table or the miner error table's Carbon rows
    assert row["code"] not in infra_diagnosis.CLASSES
    assert infra_diagnosis.public_row(row["code"]) is None
    cap.return_build_spot(TASK)
    assert (
        DirectRecipeIntake._recipe_spot_row(intake, TASK) is None
    )  # given back: no row


def test_only_a_v11_reply_carries_the_recipe_row():
    """V2 (3): a versioned change (AGENTS s12): v11 is opt-in and advertised; v10 keeps its closed rows."""
    from pathlib import Path

    from carbon.challenge_validator import direct_intake

    assert direct_intake.feedback_reply({"reply": "v11", "submission_id": "t"}) == "v11"
    assert direct_intake.FEEDBACK_REPLY_SCHEMA_V11.endswith(".v11")
    text = Path(direct_intake.__file__).read_text(encoding="utf-8")
    assert '"exam_feedback_v11"' in text
    assert (
        'v11 and submission_id is not None and grade_state == "RECONSTRUCTION_FAILED"'
        in text
    )
    assert 'v10=reply in ("v10", "v11")' in text
