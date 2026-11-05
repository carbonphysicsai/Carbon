"""A receiver that grades its own submissions (E2E gap 1): once per task, typed
failures, never concurrent with a reconstruction, configured explicitly."""

from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import auto_grade, direct_intake, direct_receiver
from carbon.challenge_validator.lean_recipe_retention import RetentionUnavailable

A, B, C = ("rtsk_" + c * 64 for c in "abc")


class FakeIntake:
    def __init__(self, tasks, behaviour):
        self.adapter = SimpleNamespace(
            contract_digest="sha256:" + "0" * 64,
            ledger=SimpleNamespace(submitted_outcomes=lambda contract: tuple(tasks)),
            owner=lambda submission_id: None,
        )
        self.behaviour = behaviour
        self.calls = []

    def retain_result(self, submission_id, **kwargs):
        self.calls.append((submission_id, sorted(kwargs)))
        outcome = self.behaviour[submission_id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome if isinstance(outcome, dict) else {"entry_id": outcome}


def _grader(tmp_path, tasks, behaviour):
    intake = FakeIntake(tasks, behaviour)
    return auto_grade.AutoGrader(intake, tmp_path), intake


def _marker(tmp_path, task):
    return json.loads(
        (tmp_path / "auto-grade" / "markers" / (task + ".json")).read_text()
    )


def test_each_ready_task_is_graded_once_and_marked(tmp_path):
    grader, intake = _grader(
        tmp_path, [A, B], {A: "sha256:" + "1" * 64, B: "sha256:" + "2" * 64}
    )
    assert grader.run_once() == (A, "GRADED")
    assert grader.run_once() == (B, "GRADED")
    assert grader.run_once() is None
    assert [c[0] for c in intake.calls] == [A, B]  # never retained twice
    marker = _marker(tmp_path, A)
    assert marker["state"] == "GRADED" and marker["entry_id"] == "sha256:" + "1" * 64
    # The operator directories are the receiver's own, owner-only.
    assert intake.calls[0][1] == ["artifact_directory", "entry_directory", "pool_store"]
    assert (tmp_path / "auto-grade" / "entries").is_dir()


def test_a_task_still_building_is_left_alone_until_it_succeeds(tmp_path):
    behaviour = {A: RetentionUnavailable("task_not_succeeded")}
    grader, _intake = _grader(tmp_path, [A], behaviour)
    assert grader.run_once() is None
    assert not list((tmp_path / "auto-grade" / "markers").glob("*.json"))
    behaviour[A] = "sha256:" + "3" * 64
    assert grader.run_once() == (A, "GRADED")


def test_a_failed_retention_is_a_typed_marker_and_is_never_retried(tmp_path):
    behaviour = {
        A: RetentionUnavailable("inference_pair_identity_already_used"),
        B: "x",
    }
    grader, intake = _grader(tmp_path, [A, B], behaviour)
    assert grader.run_once() == (A, "FAILED")
    marker = _marker(tmp_path, A)
    assert marker["state"] == "FAILED"
    assert marker["code"] == "inference_pair_identity_already_used"
    assert marker["entry_id"] is None
    assert grader.run_once() == (B, "GRADED")
    assert grader.run_once() is None
    assert [c[0] for c in intake.calls].count(A) == 1


def test_an_unexpected_error_is_recorded_by_type_only(tmp_path):
    behaviour = {A: RuntimeError("secret detail /private/path")}
    grader, _ = _grader(tmp_path, [A], behaviour)
    assert grader.run_once() == (A, "FAILED")
    text = (tmp_path / "auto-grade" / "markers" / (A + ".json")).read_text()
    assert "RuntimeError" in text and "secret" not in text and "/private" not in text


def test_a_marker_is_create_only_and_an_operator_deleting_it_retries(tmp_path):
    behaviour = {A: RetentionUnavailable("verified_attempt_gone")}
    grader, _intake = _grader(tmp_path, [A], behaviour)
    grader.run_once()
    behaviour[A] = "sha256:" + "4" * 64
    assert grader.run_once() is None
    (tmp_path / "auto-grade" / "markers" / (A + ".json")).unlink()
    assert grader.run_once() == (A, "GRADED")


def test_a_malformed_task_id_is_never_passed_on(tmp_path):
    grader, intake = _grader(tmp_path, ["../../etc/passwd", "rtsk_short"], {})
    assert grader.run_once() is None and intake.calls == []


def test_grading_and_advancing_never_run_at_the_same_time():
    work = threading.Lock()
    inside, overlap = [], []
    stop = threading.Event()

    class Advancer:
        def advance(self):
            if inside:
                overlap.append("advance during grade")
            inside.append("advance")
            threading.Event().wait(0.02)
            inside.pop()

    class Grader:
        calls = 0

        def run_once(self):
            if inside:
                overlap.append("grade during advance")
            inside.append("grade")
            threading.Event().wait(0.02)
            inside.pop()
            Grader.calls += 1
            if Grader.calls >= 5:
                stop.set()
            return (A, "GRADED")

    threads = [
        threading.Thread(
            target=direct_intake._advance_loop, args=(Advancer(), stop, work)
        ),
        threading.Thread(target=direct_intake._grade_loop, args=(Grader(), stop, work)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert Grader.calls >= 5 and overlap == []


@pytest.mark.parametrize(
    "value,ok",
    [
        ({}, True),
        ({"pool_store": "/abs/pool.sqlite3"}, True),
        ({"pool_store": "relative.sqlite3"}, False),
        ({"pool_store": 3}, False),
        ({"extra": 1}, False),
        (True, False),
    ],
)
def test_the_receiver_configuration_validates_auto_grade(
    tmp_path, monkeypatch, value, ok
):
    from test_direct_receiver import _config

    cfg = {**_config(tmp_path), "auto_grade": value}
    monkeypatch.setattr(direct_receiver, "private_json", lambda _: cfg)
    if ok:
        assert direct_receiver.load_config(tmp_path / "config.json") == cfg
    else:
        with pytest.raises(ValueError):
            direct_receiver.load_config(tmp_path / "config.json")


def test_a_receiver_without_auto_grade_is_unchanged(tmp_path, monkeypatch):
    from test_direct_receiver import _config

    cfg = _config(tmp_path)
    monkeypatch.setattr(direct_receiver, "private_json", lambda _: cfg)
    assert "auto_grade" not in direct_receiver.load_config(tmp_path / "config.json")


def test_a_failed_grade_is_given_back_on_infrastructure_so_a_resubmit_runs_fresh(
    tmp_path,
):
    """Invariant 7: the task stays SUCCEEDED, but its exam row is RELEASED/FAILED_INFRA,
    which is what the receiver's door counts as 'ended on infra'; the miner's next
    submit then gets a fresh generation."""
    from carbon.challenge_validator.exam_cap import ExamCap
    from carbon.challenge_validator.ledger import AttemptLedger

    ledger = AttemptLedger(tmp_path / "attempts.sqlite3")
    cap = ExamCap(ledger)
    ident = {
        "hotkey": "5" + "1" * 47,
        "challenge_id": "electric-motor-magnetics",
        "challenge_version": "1.3",
        "exam_key": "sha256:" + "e" * 64,
        "submission_id": A,
    }

    class Ledger:
        _db = staticmethod(ledger._db)

        @staticmethod
        def submitted_outcomes(contract):
            return (A,)

    adapter = SimpleNamespace(
        challenge_id=ident["challenge_id"],
        challenge_version=ident["challenge_version"],
        contract_digest="sha256:" + "0" * 64,
        ledger=Ledger,
        owner=lambda submission_id: ident["hotkey"],
        _provider=lambda owner: SimpleNamespace(
            evaluation_pack_digest=ident["exam_key"]
        ),
        # the give-back reads the adapter's bound pack digest, never the provider (REG-UNAVAILABLE)
        discovery=SimpleNamespace(evaluation_pack_digest=ident["exam_key"]),
    )
    intake = FakeIntake([A], {A: RetentionUnavailable("evaluation_unavailable")})
    intake.adapter = adapter
    grader = auto_grade.AutoGrader(intake, tmp_path)
    # Before: nothing recorded, so the door would hand back the same ungraded task.
    assert not cap.released_on_infra(**ident)
    assert grader.run_once() == (A, "FAILED")
    assert cap.released_on_infra(**ident)
    assert not cap.holds_slot(**ident)
    assert grader.run_once() is None  # and no automatic retry of the same task
    assert auto_grade.failure_summary(tmp_path) == {
        "auto_grade_failed": 1,
        "auto_grade_last_failure": "evaluation_unavailable",
    }


def test_a_graded_row_is_never_given_back(tmp_path):
    from carbon.challenge_validator.exam_cap import ExamCap
    from carbon.challenge_validator.ledger import AttemptLedger

    ledger = AttemptLedger(tmp_path / "attempts.sqlite3")
    cap = ExamCap(ledger)
    ident = {
        "hotkey": "5" + "1" * 47,
        "challenge_id": "electric-motor-magnetics",
        "challenge_version": "1.3",
        "exam_key": "sha256:" + "e" * 64,
        "submission_id": A,
    }
    with ledger._db() as db:
        db.execute(
            "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, "
            "exam_key, kind, epoch, submission_id, state, status, reserved_ns) "
            "VALUES(?,?,?,?,'GRADED',7,?,'COUNTED','SCORED',1)",
            tuple(ident.values()),
        )
    assert cap.give_back_on_infra(**ident) == "COUNTED"
    assert cap.holds_slot(**ident) and not cap.released_on_infra(**ident)


def test_no_failures_means_an_empty_summary(tmp_path):
    assert auto_grade.failure_summary(tmp_path) == {}


def test_auto_grade_with_a_pack_set_is_refused_with_a_typed_code(tmp_path, monkeypatch):
    from test_direct_receiver import _config

    cfg = {
        **_config(tmp_path),
        "auto_grade": {},
        "evaluation_pack_set": {"store": "/x", "set_key": "sha256:" + "a" * 64},
    }
    monkeypatch.setattr(direct_receiver, "private_json", lambda _: cfg)
    with pytest.raises(direct_receiver.ReceiverUnavailable) as refused:
        direct_receiver.load_config(tmp_path / "config.json")
    assert refused.value.code == "auto_grade_pack_set_unsupported"


def test_an_incomplete_inference_pair_reaches_only_the_operator_never_a_miner(tmp_path):
    """Disclosure allowlist: an auto-graded inference_pair_incomplete leaves no
    "inference_pair" text in anything a miner can read (the Ladder document or the
    feedback reply); it reaches the operator's marker and status, and the grading
    is given back as FAILED_INFRA."""
    from carbon.challenge_validator.direct_intake import FEEDBACK_REPLY_SCHEMA
    from carbon.challenge_validator.exam_cap import ExamCap
    from carbon.challenge_validator.ladder_store import LadderStore
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
    from carbon.challenge_validator.ledger import AttemptLedger

    ledger = AttemptLedger(tmp_path / "attempts.sqlite3")
    hotkey = "5" + "1" * 47
    challenge = "electric-motor-magnetics"
    exam_key = "sha256:" + "e" * 64

    class Ledger:
        _db = staticmethod(ledger._db)

        @staticmethod
        def submitted_outcomes(contract):
            return (A,)

    adapter = SimpleNamespace(
        challenge_id=challenge,
        challenge_version="1.3",
        contract_digest="sha256:" + "0" * 64,
        ledger=Ledger,
        owner=lambda submission_id: hotkey,
        _provider=lambda owner: SimpleNamespace(evaluation_pack_digest=exam_key),
        # the give-back reads the adapter's bound pack digest, never the provider (REG-UNAVAILABLE)
        discovery=SimpleNamespace(evaluation_pack_digest=exam_key),
    )
    intake = FakeIntake([A], {A: RetentionUnavailable("inference_pair_incomplete")})
    intake.adapter = adapter
    grader = auto_grade.AutoGrader(intake, tmp_path)
    assert grader.run_once() == (A, "FAILED")
    # Operator-side: the marker and the status summary carry the code.
    assert auto_grade.failure_summary(tmp_path)["auto_grade_last_failure"] == (
        "inference_pair_incomplete"
    )
    assert ExamCap(ledger).released_on_infra(
        hotkey=hotkey,
        challenge_id=challenge,
        challenge_version="1.3",
        exam_key=exam_key,
        submission_id=A,
    )
    # Miner-side: no Ladder document was written, and the reply built from the store
    # names nothing; the adapter's disclosure allowlist has no such field.
    key = SimpleNamespace(challenge_id=challenge, version="1.3")
    served = LadderStore(ledger).served(hotkey, key, exam_key)
    reply = {
        "schema": FEEDBACK_REPLY_SCHEMA,
        "challenge": {"id": challenge, "version": "1.3"},
        "best": served["best"],
        "latest": served["latest"],
    }
    assert served == {"best": None, "latest": None}
    assert "inference_pair" not in json.dumps(reply)
    assert not any("inference_pair" in f for f in LeanRecipeAdapter.disclosure_fields)
    # Every file a receiver could serve to a miner is outside auto-grade/markers.
    for path in tmp_path.rglob("*"):
        if path.is_file() and "markers" not in path.parts and path.suffix == ".json":
            assert "inference_pair" not in path.read_text()


def test_a_grade_that_could_not_be_computed_keeps_its_own_reason_in_the_marker(
    tmp_path,
):
    """valV3 2026-10-28: an operator's idempotent re-retention reported a different, secondary reason than the
    first attempt's; the marker now carries the first attempt's typed reason."""
    unavailable = {
        "entry_id": "sha256:" + "1" * 64,
        "private_evaluation_state": "UNAVAILABLE",
        "private_evaluation_reason": "single_call_row_not_in_the_delivered_query",
    }
    grader, _ = _grader(tmp_path, [A, B], {A: unavailable, B: "sha256:" + "2" * 64})
    assert grader.run_once() == (A, "GRADED")
    assert grader.run_once() == (B, "GRADED")
    assert _marker(tmp_path, A)["code"] == "single_call_row_not_in_the_delivered_query"
    assert _marker(tmp_path, B)["code"] is None


# ---------------------------------------------------------------- the bank wall stop is the candidate's (interim)


def _wall_setup(
    tmp_path,
    failure,
    *,
    row=("RELEASED", "UNAVAILABLE"),
    host_lock=True,
    containers=lambda: 0,
    reserved_ns=2**62,  # reserved by THIS attempt (after it started)
):
    """A grader whose retention raises ``failure`` after the bank grade settled the slot ``row``."""
    from carbon.challenge_validator.exam_cap import ExamCap
    from carbon.challenge_validator.ledger import AttemptLedger

    ledger = AttemptLedger(tmp_path / "attempts.sqlite3")
    cap = ExamCap(ledger)
    ident = {
        "hotkey": "5" + "1" * 47,
        "challenge_id": "electric-motor-magnetics",
        "challenge_version": "1.3",
        "exam_key": "sha256:" + "e" * 64,
        "submission_id": A,
    }
    if row is not None:
        with ledger._db() as db:
            db.execute(
                "INSERT INTO exam_graded(hotkey, challenge_id, challenge_version, exam_key, kind, "
                "epoch, submission_id, state, status, reserved_ns) VALUES(?,?,?,?,'GRADED',7,?,?,?,?)",
                (*ident.values(), *row, reserved_ns),
            )

    class Ledger:
        _db = staticmethod(ledger._db)

        @staticmethod
        def submitted_outcomes(contract):
            return (A,)

    adapter = SimpleNamespace(
        challenge_id=ident["challenge_id"],
        challenge_version=ident["challenge_version"],
        contract_digest="sha256:" + "0" * 64,
        ledger=Ledger,
        owner=lambda submission_id: ident["hotkey"],
        discovery=SimpleNamespace(evaluation_pack_digest=ident["exam_key"]),
    )
    intake = FakeIntake([A], {A: failure})
    intake.adapter = adapter
    grader = auto_grade.AutoGrader(
        intake, tmp_path, host_lock=host_lock, containers=containers
    )
    return grader, cap, ident, ledger


def _miner_failure(code, observation):
    from carbon.development_session import research_carrier as carrier

    return carrier.MinerProgramFailure(
        {
            "schema": carrier.MINER_FAILURE_SCHEMA,
            "failure_code": code,
            "observation": observation,
        }
    )


def _row(ledger):
    with ledger._db() as db:
        return db.execute(
            "SELECT state, status FROM exam_graded WHERE submission_id=?", (A,)
        ).fetchall()


def test_a_bank_wall_stop_is_the_candidates_outcome_counted_never_a_free_rerun(
    tmp_path,
):
    """Validator 16:52: the graph's own wall stop on hidden inputs is COUNTED as CANDIDATE_FAILED, never given back
    as FAILED_INFRA, so neither a resubmit nor a changed recipe probes the hidden inputs uncharged.
    """
    from carbon.reconstruction.worker.model import WorkerCode

    wall = _miner_failure(WorkerCode.DEADLINE.value, "WORKER_WALL_LIMIT_REACHED")
    grader, cap, ident, ledger = _wall_setup(tmp_path, wall)
    assert grader.run_once() == (A, "CANDIDATE_FAILED")
    assert _row(ledger) == [("COUNTED", "WORKER_WALL_LIMIT_REACHED")]
    assert _marker(tmp_path, A)["state"] == "CANDIDATE_FAILED"
    assert _marker(tmp_path, A)["code"] == "WORKER_WALL_LIMIT_REACHED"
    assert cap.holds_slot(**ident)  # the door refuses the same recipe: graded
    assert not cap.released_on_infra(**ident)  # and no free infrastructure rerun


@pytest.mark.parametrize(
    "code, observation",
    [("RUNTIME", "WORKER_MEMORY_LIMIT_REACHED"), ("DEADLINE", "OWN_ALLOWANCE_ELAPSED")],
)
def test_any_other_program_failure_is_given_back_as_before(tmp_path, code, observation):
    from carbon.reconstruction.worker.model import WorkerCode

    failure = _miner_failure(getattr(WorkerCode, code).value, observation)
    grader, cap, ident, ledger = _wall_setup(tmp_path, failure)
    assert grader.run_once() == (A, "FAILED")
    assert _row(ledger) == [("RELEASED", "FAILED_INFRA")]
    assert cap.released_on_infra(**ident)


def test_a_wall_stop_with_no_settled_slot_is_given_back_as_before(tmp_path):
    from carbon.reconstruction.worker.model import WorkerCode

    wall = _miner_failure(WorkerCode.DEADLINE.value, "WORKER_WALL_LIMIT_REACHED")
    grader, _cap, _ident, ledger = _wall_setup(tmp_path, wall, row=None)
    assert grader.run_once() == (A, "FAILED")  # stopped before any reservation
    assert _row(ledger) == [("RELEASED", "FAILED_INFRA")]


def test_a_true_infrastructure_failure_still_reruns_free(tmp_path):
    grader, cap, ident, _ledger = _wall_setup(
        tmp_path, RetentionUnavailable("direct_provider_registration_unavailable")
    )
    assert grader.run_once() == (A, "FAILED")
    assert cap.released_on_infra(**ident)


def test_only_an_unavailable_released_row_is_recounted(tmp_path):
    for n, row in enumerate(
        (
            ("RELEASED", "FAILED_INFRA"),
            ("COUNTED", "SCORED_DEVELOPMENT_CANDIDATE"),
            ("RESERVED", None),
        )
    ):
        (tmp_path / str(n)).mkdir(mode=0o700)
        (tmp_path / str(n)).chmod(0o700)
        _grader, cap, ident, ledger = _wall_setup(tmp_path / str(n), None, row=row)
        assert cap.count_candidate_wall(**ident, since_ns=0) is None
        assert _row(ledger) == [row]


@pytest.mark.parametrize(
    "host_lock, containers, why",
    [
        (True, lambda: 2, "another worker container ran"),
        (
            True,
            lambda: 1,
            "a container still ran at the stop (ours was already removed)",
        ),
        (True, lambda: None, "the daemon could not say"),
        (False, lambda: 1, "the grade did not hold the host lock"),
    ],
)
def test_a_wall_stop_under_possible_contention_is_given_back_and_logged(
    tmp_path, host_lock, containers, why
):
    """Validator 17:16 guard (invariant 7): a wall stop is counted only when this grade held the host lock and no
    other Carbon worker container ran during it; otherwise our host may have slowed it, so it is given back.
    """
    from carbon.reconstruction.worker.model import WorkerCode

    wall = _miner_failure(WorkerCode.DEADLINE.value, "WORKER_WALL_LIMIT_REACHED")
    grader, cap, ident, ledger = _wall_setup(
        tmp_path, wall, host_lock=host_lock, containers=containers
    )
    assert grader.run_once() == (A, "FAILED"), why
    assert _row(ledger) == [("RELEASED", "FAILED_INFRA")]
    assert cap.released_on_infra(**ident)
    (logged,) = [
        json.loads(line)
        for line in (tmp_path / "auto-grade" / "wall-stops.jsonl")
        .read_text()
        .splitlines()
    ]
    assert logged["task"] == A and logged["counted"] is False
    assert logged["host_lock"] is host_lock


def test_an_uncontended_wall_stop_is_logged_as_counted(tmp_path):
    from carbon.reconstruction.worker.model import WorkerCode

    wall = _miner_failure(WorkerCode.DEADLINE.value, "WORKER_WALL_LIMIT_REACHED")
    grader, _cap, _ident, _ledger = _wall_setup(tmp_path, wall)
    assert grader.run_once() == (A, "CANDIDATE_FAILED")
    logged = json.loads((tmp_path / "auto-grade" / "wall-stops.jsonl").read_text())
    assert logged["counted"] is True and logged["stop_worker_containers"] == 0


def test_the_sampler_reads_the_host_while_a_grade_runs():
    import time as clock

    seen = []
    sampler = auto_grade._Sampler(lambda: seen.append(1) or 1, 0.01)
    with sampler:
        clock.sleep(0.1)
    assert len(sampler.samples) >= 2 and set(sampler.samples) == {1}
    quick = auto_grade._Sampler(lambda: 1, 60)
    with quick:
        pass  # a not-ready task returns at once: no docker call
    assert quick.samples == []


def test_a_failure_while_counting_gives_back_and_never_crashes_the_grade(tmp_path):
    """Review finding 2: an exception in the count (a provider or ledger fault) gives the slot back as before; a crash
    would leave no marker and re-run the task on hidden inputs."""
    from carbon.reconstruction.worker.model import WorkerCode

    wall = _miner_failure(WorkerCode.DEADLINE.value, "WORKER_WALL_LIMIT_REACHED")
    grader, _cap, _ident, _ledger = _wall_setup(tmp_path, wall)

    def broken(submission_id):
        raise RuntimeError("provider unavailable")

    grader.intake.adapter.owner = broken
    assert grader.run_once() == (A, "FAILED")
    logged = json.loads((tmp_path / "auto-grade" / "wall-stops.jsonl").read_text())
    assert logged["uncontended"] is True and logged["counted"] is False


def test_a_slot_from_an_earlier_attempt_is_never_counted(tmp_path):
    """Review finding 6: only the row THIS attempt reserved is re-settled; a stale RELEASED/UNAVAILABLE row from
    before the attempt started is given back as before."""
    from carbon.reconstruction.worker.model import WorkerCode

    wall = _miner_failure(WorkerCode.DEADLINE.value, "WORKER_WALL_LIMIT_REACHED")
    grader, _cap, _ident, ledger = _wall_setup(tmp_path, wall, reserved_ns=1)
    assert grader.run_once() == (A, "FAILED")
    assert _row(ledger) == [("RELEASED", "FAILED_INFRA")]
