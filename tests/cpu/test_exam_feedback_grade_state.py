"""The exam feedback read for one of the caller's own submissions: its grade state (miner feedback fix 1).

Claims: a receiver that grades its own submissions advertises the v2 read in its own facts entry (the v1 entry deployed
clients pin is unchanged, and a receiver without auto-grade advertises no v2); the v2 read is refused unless the signed
caller owns the submission, with the SAME code for another key's id and an unknown id; the grade state is one of four,
read from the submission's auto-grade marker and its round's slot rows (QUEUED with no marker, GRADED for a computed
grade, SUPERSEDED_BY_OWN_LATER_SUBMIT when the caller's own later submission holds the round's slot, else
ROUND_LIMIT_REACHED), and None for anything else; no time, count or other key is in the reply; the client asks for the
v2 read only where it is advertised and accepts back only its allow-listed shape."""

from __future__ import annotations

import json
import os
import time
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_intake
from carbon.challenge_validator.auto_grade import AutoGrader
from carbon.challenge_validator.exam_cap import EPOCH_BLOCKS, ExamCap
from carbon.challenge_validator.ladder_store import LadderStore
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.development_session import direct_submission as client
from carbon.registry.model import ChallengeKey

MOTOR = ChallengeKey("electric-motor-magnetics", "1.0")
EXAM = "sha256:" + "e" * 64
CONTRACT = "sha256:" + "c" * 64
CADENCE = {
    "capacity_gpu_lane_hours_per_day": 100.0,
    "rebuild_gpu_lane_hours": {MOTOR.challenge_id: 1.0},
}


def _task(n):
    return "rtsk_" + format(n, "064x")


A, B, C, OTHER = _task(1), _task(2), _task(3), _task(9)


@pytest.fixture
def ledger(tmp_path):
    root = tmp_path / "receiver"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    return AttemptLedger(root / "attempts.sqlite3")


def _arrive(ledger, submission_id, block):
    """An OUTCOME attempt row under a signed receipt at ``block``, in arrival order."""
    with ledger._db() as db:
        db.execute(
            "INSERT INTO attempts(at_ns, kind, contract_digest, submission_id, receipt, submission_sha256) "
            "VALUES(0, 'OUTCOME', ?, ?, ?, '')",
            (CONTRACT, submission_id, json.dumps({"block": block})),
        )


def _intake(tmp_path, ledger, owners, *, grader=True):
    adapter = SimpleNamespace(
        ledger=ledger,
        contract_digest=CONTRACT,
        owner=owners.get,
        discovery=SimpleNamespace(
            evaluation_pack_snapshot=SimpleNamespace(manifest_digest=EXAM)
        ),
    )
    intake = object.__new__(direct_intake.DirectRecipeIntake)
    intake.adapter, intake.challenge = adapter, MOTOR
    marks = None
    if grader:
        marks = AutoGrader(intake, tmp_path / "grade-root")
        intake.grade_marker = marks.marker
    return intake, marks


def _state(intake, hotkey, submission_id):
    answer = intake._feedback(hotkey, submission_id=submission_id)
    assert answer.status == 200
    assert set(answer.body) == {"schema", "challenge", "best", "latest", "submission"}
    assert answer.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA_V2
    assert set(answer.body["submission"]) == {"submission_id", "grade_state"}
    assert answer.body["submission"]["submission_id"] == submission_id
    return answer.body["submission"]["grade_state"]


def _hold(ledger, hotkey, submission_id, block):
    cap = ExamCap(ledger, cadence=CADENCE)
    reservation = cap.reserve(
        hotkey=hotkey,
        challenge_id=MOTOR.challenge_id,
        challenge_version=MOTOR.version,
        exam_key=EXAM,
        submission_id=submission_id,
        block=block,
    )
    cap.settle(reservation, "SCORED_DEVELOPMENT_CANDIDATE")


def test_another_keys_id_and_an_unknown_id_are_refused_alike(tmp_path, ledger):
    intake, marks = _intake(tmp_path, ledger, {A: "5Miner", OTHER: "5Other"})
    marks._write(OTHER, "GRADED")
    refused = [
        intake._feedback("5Miner", submission_id=s) for s in (OTHER, _task(77), "x")
    ]
    assert {(r.status, json.dumps(r.body, sort_keys=True)) for r in refused} == {
        (refused[0].status, json.dumps(refused[0].body, sort_keys=True))
    }
    assert refused[0].status == 404
    assert "feedback_submission_unknown" in json.dumps(refused[0].body)
    assert _state(intake, "5Other", OTHER) == "GRADED"


def test_the_plain_read_is_unchanged_and_no_grader_serves_no_grade_state(
    tmp_path, ledger
):
    intake, _marks = _intake(tmp_path, ledger, {A: "5Miner"}, grader=False)
    plain = intake._feedback("5Miner")
    assert plain.status == 200
    assert set(plain.body) == {"schema", "challenge", "best", "latest"}
    assert plain.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA
    refused = intake._feedback("5Miner", submission_id=A)
    assert refused.status == 503
    assert "grade_state_unavailable" in json.dumps(refused.body)


def test_queued_graded_and_none_come_from_the_marker(tmp_path, ledger):
    owners = {A: "5Miner", B: "5Miner", C: "5Miner"}
    intake, marks = _intake(tmp_path, ledger, owners)
    assert _state(intake, "5Miner", A) == "QUEUED"
    marks._write(A, "GRADED", entry_id="sha256:" + "1" * 64)
    assert _state(intake, "5Miner", A) == "GRADED"
    marks._write(B, "FAILED", code="WorkerFailure")
    assert _state(intake, "5Miner", B) is None
    marks._write(C, "GRADED", code="carbon_capability_gap")
    assert _state(intake, "5Miner", C) is None


@pytest.mark.parametrize(
    "code", ["epoch_limit_reached", "exam_daily_allowance_reached"]
)
def test_a_limit_refusal_is_superseded_only_by_the_callers_own_later_submit(
    tmp_path, ledger, code
):
    block = 10 * EPOCH_BLOCKS + 5
    owners = {A: "5Miner", B: "5Miner", C: "5Miner", OTHER: "5Other"}
    intake, marks = _intake(tmp_path, ledger, owners)
    for submission in (A, B, C, OTHER):
        _arrive(ledger, submission, block)
    # B arrived after A and holds the round's slot: A was superseded by the miner's own later submit
    _hold(ledger, "5Miner", B, block)
    marks._write(A, "GRADED", code=code)
    assert _state(intake, "5Miner", A) == "SUPERSEDED_BY_OWN_LATER_SUBMIT"
    # C arrived after B, the holder: the round's limit was reached
    marks._write(C, "GRADED", code=code)
    assert _state(intake, "5Miner", C) == "ROUND_LIMIT_REACHED"
    # another key's slot never supersedes; nothing of it is read out
    _hold(ledger, "5Other", OTHER, block)
    marks2 = AutoGrader(intake, tmp_path / "grade-root-2")
    intake.grade_marker = marks2.marker
    marks2._write(C, "GRADED", code=code)
    assert _state(intake, "5Miner", C) == "ROUND_LIMIT_REACHED"


def test_a_limit_refusal_with_no_signed_block_is_the_round_limit(tmp_path, ledger):
    intake, marks = _intake(tmp_path, ledger, {A: "5Miner"})
    marks._write(A, "GRADED", code="epoch_limit_reached")
    assert _state(intake, "5Miner", A) == "ROUND_LIMIT_REACHED"


def _public(intake):
    intake.window = SimpleNamespace(
        latest=lambda: SimpleNamespace(
            snapshot_id="s", finalized_block=1, timestamp_ms=0
        )
    )
    intake.context = SimpleNamespace(network="testnet", genesis_hash="0x0", netuid=567)
    intake.receiver = "validator"
    intake.door = SimpleNamespace(served_contracts=list)
    intake._official_gpu_cache = (time.monotonic(), {})
    return intake.public().body


def test_the_facts_advertise_v2_only_with_a_grader_and_keep_v1_pinned(tmp_path, ledger):
    with_grader, _ = _intake(tmp_path, ledger, {})
    without, _ = _intake(tmp_path, ledger, {}, grader=False)
    facts = _public(with_grader)
    assert facts["exam_feedback"] == client.FEEDBACK_FACTS
    assert facts["exam_feedback_v2"] == client.FEEDBACK_V2_FACTS
    plain = _public(without)
    assert plain["exam_feedback"] == client.FEEDBACK_FACTS
    assert "exam_feedback_v2" not in plain
    assert client.GRADE_STATES == direct_intake.GRADE_STATES
    assert client.FEEDBACK_REPLY_SCHEMA_V2 == direct_intake.FEEDBACK_REPLY_SCHEMA_V2
    assert facts["exam_feedback_v3"] == client.FEEDBACK_V3_FACTS
    assert "exam_feedback_v3" not in plain
    assert client.GRADE_STATES_V3 == direct_intake.GRADE_STATES_V3
    assert client.FEEDBACK_REPLY_SCHEMA_V3 == direct_intake.FEEDBACK_REPLY_SCHEMA_V3


@pytest.fixture
def read_v2(monkeypatch):
    """The client's read against a fixture receiver; returns (result, sent fields)."""
    from carbon.development_session import direct_submission

    sent = []
    facts = {
        "exam_feedback": client.FEEDBACK_FACTS,
        "exam_feedback_v2": client.FEEDBACK_V2_FACTS,
    }
    recipe = object.__new__(client.ConstructionRecipe)
    monkeypatch.setattr(
        client.ConstructionRecipe,
        "to_dict",
        lambda self: {
            "challenge": {"id": MOTOR.challenge_id, "version": MOTOR.version}
        },
    )
    monkeypatch.setattr(
        direct_submission, "_body", lambda facts, **kw: {"fields": kw["fields"]}
    )
    monkeypatch.setattr(
        direct_submission,
        "BittensorMessageSigner",
        lambda signer: SimpleNamespace(sign=lambda body, **kw: {}),
    )

    def run(reply, *, advertised=True, submission_id=A, v3=False):
        def send(url, body, headers):
            sent.append(body["fields"])
            return 200, {
                "challenge": {"id": MOTOR.challenge_id, "version": MOTOR.version},
                "best": None,
                "latest": None,
                **reply,
            }

        return client.read_exam_feedback(
            "http://127.0.0.1:1",
            "external-signer",
            recipe=recipe,
            contract_digest=CONTRACT,
            receiver="validator",
            context=None,
            read=lambda url: (
                (
                    {**facts, "exam_feedback_v3": client.FEEDBACK_V3_FACTS}
                    if v3
                    else facts
                )
                if advertised
                else {"exam_feedback": client.FEEDBACK_FACTS}
            ),
            send=send,
            submission_id=submission_id,
        )

    return run, sent


def test_the_client_asks_for_v2_only_where_advertised_and_checks_its_shape(read_v2):
    run, sent = read_v2
    v2 = {"schema": client.FEEDBACK_REPLY_SCHEMA_V2}
    for state in (*client.GRADE_STATES, None):
        result = run({**v2, "submission": {"submission_id": A, "grade_state": state}})
        assert result == {
            "submission": {"submission_id": A, "grade_state": state},
            "best": None,
            "latest": None,
        }
    assert sent[-1] == {"submission_id": A}
    # a receiver without the v2 read answers v1, asked with no fields
    assert run({"schema": client.FEEDBACK_REPLY_SCHEMA}, advertised=False) == {
        "best": None,
        "latest": None,
    }
    assert sent[-1] == {}
    for bad in (
        {**v2, "submission": {"submission_id": B, "grade_state": "GRADED"}},
        {**v2, "submission": {"submission_id": A, "grade_state": "DONE"}},
        {**v2, "submission": {"submission_id": A, "grade_state": "GRADED", "at": 1}},
        {"schema": client.FEEDBACK_REPLY_SCHEMA},
        {**v2},
    ):
        with pytest.raises(client.DirectIntakeRefusal) as refused:
            run(bad)
        assert refused.value.code == "exam_feedback_reply_invalid"


def test_the_ladder_rows_are_still_only_the_callers(tmp_path, ledger):
    intake, marks = _intake(tmp_path, ledger, {A: "5Miner"})
    marks._write(A, "GRADED")
    body = intake._feedback("5Miner", submission_id=A).body
    assert (body["best"], body["latest"]) == (None, None)
    assert LadderStore(ledger).served("5Miner", MOTOR, EXAM) == {
        "best": None,
        "latest": None,
    }


def test_candidate_failed_is_v3_only_and_a_v2_reply_keeps_its_closed_set(
    tmp_path, ledger, read_v2
):
    """Validator 22:40: CANDIDATE_FAILED appears only in the v3 reply; a v2 reply keeps None, so a deployed v2 client parses it."""
    intake, marks = _intake(tmp_path, ledger, {A: "5Miner"})
    marks._write(A, "CANDIDATE_FAILED", code="WORKER_WALL_LIMIT_REACHED")
    assert "CANDIDATE_FAILED" not in direct_intake.GRADE_STATES
    v2 = intake._feedback("5Miner", submission_id=A)
    assert v2.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA_V2
    assert v2.body["submission"]["grade_state"] is None
    v3 = intake._feedback("5Miner", submission_id=A, v3=True)
    assert v3.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA_V3
    assert v3.body["submission"]["grade_state"] == "CANDIDATE_FAILED"
    run, sent = read_v2
    # a v2-only client (no v3 advertised) parses the v2 reply the receiver gives it
    assert (
        run({**{k: v2.body[k] for k in ("schema", "submission")}})["submission"][
            "grade_state"
        ]
        is None
    )
    assert sent[-1] == {"submission_id": A}
    # ...and would refuse CANDIDATE_FAILED in a v2 reply: why it is v3's
    with pytest.raises(client.DirectIntakeRefusal):
        run(
            {
                "schema": client.FEEDBACK_REPLY_SCHEMA_V2,
                "submission": {"submission_id": A, "grade_state": "CANDIDATE_FAILED"},
            }
        )
    # a client that sees v3 advertised asks for v3 and accepts it
    got = run({k: v3.body[k] for k in ("schema", "submission")}, v3=True)
    assert got["submission"]["grade_state"] == "CANDIDATE_FAILED"
    assert sent[-1] == {"reply": "v3", "submission_id": A}
