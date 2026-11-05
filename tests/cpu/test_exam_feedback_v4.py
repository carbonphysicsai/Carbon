"""Head B (Validator 4 Nov 03:17 (3) and 07:18): the v4 per-submission feedback reply.

Claims:
- v2 stays closed and v3 is untouched; v4 is advertised in its own facts entry and asked for with ``reply: v4``.
- A v4 grade state is never None: the states v3 leaves None (or QUEUED) become RECONSTRUCTION_FAILED, FAILED_INFRA or
  NOT_GRADED, from the task, its marker and its slot.
- A failed candidate run says WHY with an allow-list only: the failing child, the observation CLASS, the registered limit
  (its public name and value) and the public refusal code. A measured value planted anywhere upstream (seconds, memory,
  cases, exit codes, output text, digests) never reaches the reply, for the inference child above all (hidden inputs).
- The client asks for v4 only where it is advertised and accepts back only that allow-listed shape.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
from types import SimpleNamespace

import pytest
from test_exam_feedback_grade_state import (
    CONTRACT,
    MOTOR,
    A,
    B,
    C,
    _hold,
    _intake,
    _public,
)

from carbon.challenge_validator import direct_intake
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.development_session import direct_submission as client


@pytest.fixture
def ledger(tmp_path):
    root = tmp_path / "receiver"
    root.mkdir(mode=0o700)
    os.chmod(root, 0o700)
    return AttemptLedger(root / "attempts.sqlite3")


D, E = ("rtsk_" + format(n, "064x") for n in (4, 5))
POLICY = {
    "memory_bytes_max": 16 * 1024**3,
    "build_wall_seconds_max": 648,
    "inference_wall_seconds_max": 648,
    "total_reconstruction_wall_seconds_max": 947,
}
#: What a measured value upstream would look like; none of it may appear in a reply.
PLANTED = {
    "elapsed_seconds": 611.25,
    "peak_memory_bytes": 17_179_000_123,
    "cases_completed": 37,
    "exit_code": 137,
    "stderr_tail": "Killed at case 37",
    "inputs_digest": "sha256:" + "d" * 64,
}


def _v4_intake(tmp_path, ledger, owners, *, outcomes=None, children=None):
    intake, marks = _intake(tmp_path, ledger, owners)
    outcomes, children = outcomes or {}, children or {}
    intake.adapter.outcome = lambda sid: outcomes.get(sid, {"state": "RECONSTRUCTED"})
    intake.adapter.failed_child = lambda sid: children.get(sid, (None, None))
    intake.adapter.discovery._material = {
        "construction_limits_document": {"reconstruction_resource_policy": POLICY}
    }
    return intake, marks


def _v4(intake, hotkey, submission_id):
    answer = intake._feedback(hotkey, submission_id=submission_id, v4=True)
    assert answer.status == 200
    assert answer.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA_V4
    submission = answer.body["submission"]
    assert set(submission) == {"submission_id", "grade_state", "failure"}
    assert submission["grade_state"] in direct_intake.GRADE_STATES_V4
    failure = submission["failure"]
    if failure is not None:
        assert set(failure) == set(direct_intake.FAILURE_KEYS)
    return submission["grade_state"], failure


def _v3(intake, hotkey, submission_id):
    answer = intake._feedback(hotkey, submission_id=submission_id, v3=True)
    assert answer.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA_V3
    assert set(answer.body["submission"]) == {"submission_id", "grade_state"}
    return answer.body["submission"]["grade_state"]


def test_v4_states_are_never_none_and_v3_is_untouched(tmp_path, ledger):
    owners = {s: "5Miner" for s in (A, B, C, D, E)}
    intake, marks = _v4_intake(
        tmp_path,
        ledger,
        owners,
        outcomes={
            B: {
                "state": "FAILED_INFRA",
                "failure": {"code": "direct_task_failed_infra"},
            },
            C: {
                "state": "RECONSTRUCTION_FAILED",
                "failure": {"code": "candidate_program_failed"},
            },
        },
        children={C: ("build", "WORKER_MEMORY_LIMIT_REACHED")},
    )
    # no marker: the task decides (v3 says QUEUED for all three)
    assert _v4(intake, "5Miner", A) == ("QUEUED", None)
    assert _v4(intake, "5Miner", B) == ("FAILED_INFRA", None)
    assert _v4(intake, "5Miner", C) == (
        "RECONSTRUCTION_FAILED",
        {
            "child": "build",
            "observation": "WORKER_MEMORY_LIMIT_REACHED",
            "limit": {"name": "memory_bytes_max", "value": POLICY["memory_bytes_max"]},
            "code": "candidate_program_failed",
        },
    )
    assert [_v3(intake, "5Miner", s) for s in (A, B, C)] == ["QUEUED"] * 3
    # a FAILED marker is Carbon's failure (v3: None)
    marks._write(A, "FAILED", code="direct_provider_registration_unavailable")
    assert _v4(intake, "5Miner", A) == ("FAILED_INFRA", None)
    assert _v3(intake, "5Miner", A) is None
    # the graded wall: the inference child, its class and the public registered limit
    marks._write(D, "CANDIDATE_FAILED", code="WORKER_WALL_LIMIT_REACHED")
    assert _v4(intake, "5Miner", D) == (
        "CANDIDATE_FAILED",
        {
            "child": "inference",
            "observation": "WORKER_WALL_LIMIT_REACHED",
            "limit": {"name": "inference_wall_seconds_max", "value": 648},
            "code": None,
        },
    )
    assert _v3(intake, "5Miner", D) == "CANDIDATE_FAILED"
    # a grade with a reason v3 leaves None: NOT_GRADED while given back, GRADED once its slot is held
    marks._write(E, "GRADED", code="carbon_capability_gap")
    assert _v4(intake, "5Miner", E) == ("NOT_GRADED", None)
    assert _v3(intake, "5Miner", E) is None
    _hold(ledger, "5Miner", E, 7_200)
    assert _v4(intake, "5Miner", E) == ("GRADED", None)
    # v2 stays closed: none of the new states ever appears there
    v2 = intake._feedback("5Miner", submission_id=A)
    assert v2.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA_V2
    assert set(v2.body["submission"]) == {"submission_id", "grade_state"}
    assert v2.body["submission"]["grade_state"] is None


def test_a_failure_is_built_from_closed_values_only(tmp_path, ledger):
    intake, _ = _v4_intake(tmp_path, ledger, {})
    allowed = intake.failure_v4("inference", "WORKER_WALL_LIMIT_REACHED")
    assert allowed["limit"] == {"name": "inference_wall_seconds_max", "value": 648}
    assert intake.failure_v4("build", "WORKER_WALL_LIMIT_REACHED")["limit"] == {
        "name": "build_wall_seconds_max",
        "value": 648,
    }
    assert intake.failure_v4("inference", "OOM_KILLED")["limit"]["name"] == (
        "memory_bytes_max"
    )
    # no limit for a program's own error; unknown child/observation/code become None, never echoed
    assert intake.failure_v4("build", "NONZERO_EXIT", "candidate_program_failed") == {
        "child": "build",
        "observation": "NONZERO_EXIT",
        "limit": None,
        "code": "candidate_program_failed",
    }
    odd = intake.failure_v4("prep", "exit=137 after 611.25 s", "Killed at case 37")
    assert odd == {"child": None, "observation": None, "limit": None, "code": None}
    # an unregistered limit value is not shown
    intake.adapter.discovery._material = {
        "construction_limits_document": {"reconstruction_resource_policy": {}}
    }
    assert intake.failure_v4("inference", "WORKER_WALL_LIMIT_REACHED")["limit"] is None


def _adapter_with_child_rows(tmp_path, rows):
    """A real `LeanRecipeAdapter.failed_child` over an owner ledger holding ``rows`` (phase -> (state, result))."""
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
    from carbon.development_session.bundle_construction_worker import (
        direct_child_identity,
    )

    path = tmp_path / "owner-ledger.sqlite3"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE operations(id TEXT, owner TEXT, state TEXT, result BLOB)")
    for phase, (state, result) in rows.items():
        db.execute(
            "INSERT INTO operations VALUES(?,?,?,?)",
            (direct_child_identity(C, phase), "5Miner", state, json.dumps(result)),
        )
    db.commit()
    db.close()

    class OwnerLedger:
        @contextlib.contextmanager
        def db(self):
            connection = sqlite3.connect(path)
            try:
                yield connection
            finally:
                connection.close()

    adapter = object.__new__(LeanRecipeAdapter)
    adapter.owner = lambda sid: "5Miner" if sid == C else None
    adapter._provider = lambda owner: SimpleNamespace(ledger=OwnerLedger())
    return adapter


def test_a_planted_measured_field_never_reaches_the_reply(tmp_path, ledger):
    """The child's private FAILED_MINER record carries measurements; only its phase and closed class leave."""
    miner_failure = {
        "schema": "carbon.autoresearch.miner-program-failure.v1",
        "state": "FAILED_MINER",
        "failure_code": "DEADLINE",
        "observation": "WORKER_WALL_LIMIT_REACHED",
        "limit": {"kind": "wall", "seconds": 648},
        **PLANTED,
    }
    adapter = _adapter_with_child_rows(
        tmp_path,
        {
            "build": ("SUCCEEDED", {"ok": True}),
            "inference": ("FAILED_MINER", miner_failure),
        },
    )
    assert adapter.failed_child(C) == ("inference", "WORKER_WALL_LIMIT_REACHED")
    assert adapter.failed_child(A) == (None, None)  # not this door's task
    intake, _ = _v4_intake(
        tmp_path,
        ledger,
        {C: "5Miner"},
        outcomes={
            C: {
                "state": "RECONSTRUCTION_FAILED",
                "failure": {"code": "candidate_program_failed", **PLANTED},
            }
        },
    )
    intake.adapter.failed_child = adapter.failed_child
    answer = intake._feedback("5Miner", submission_id=C, v4=True)
    text = json.dumps(answer.body)
    for key, value in PLANTED.items():
        assert key not in text and json.dumps(value) not in text
    assert answer.body["submission"]["failure"] == {
        "child": "inference",
        "observation": "WORKER_WALL_LIMIT_REACHED",
        "limit": {"name": "inference_wall_seconds_max", "value": 648},
        "code": "candidate_program_failed",
    }


def test_no_failed_child_names_no_child(tmp_path):
    clean = _adapter_with_child_rows(
        tmp_path, {"build": ("FAILED_INFRA", {"x": 1}), "inference": ("SUCCEEDED", {})}
    )
    assert clean.failed_child(C) == (None, None)
    (tmp_path / "u").mkdir()
    unreadable = _adapter_with_child_rows(
        tmp_path / "u", {"build": ("FAILED_MINER", "not a result")}
    )
    assert unreadable.failed_child(C) == ("build", None)


def test_an_unreadable_task_is_a_typed_503_not_a_wrong_state(tmp_path, ledger):
    from carbon.challenge_validator.interface import Unavailable

    intake, _ = _v4_intake(tmp_path, ledger, {A: "5Miner"})

    def down(sid):
        raise Unavailable("direct_provider_registration_unavailable")

    intake.adapter.outcome = down
    answer = intake._feedback("5Miner", submission_id=A, v4=True)
    assert answer.status == 503 and "grade_state_unavailable" in json.dumps(answer.body)


@pytest.mark.parametrize(
    "fields, reply",
    [
        ({"submission_id": A}, "v2"),
        ({"reply": "v3", "submission_id": A}, "v3"),
        ({"reply": "v4", "submission_id": A}, "v4"),
        ({"reply": "v5", "submission_id": A}, None),
        ({"reply": "v4"}, None),
        ({"reply": "v4", "submission_id": 7}, None),
        ({"reply": "v4", "submission_id": A, "extra": 1}, None),
    ],
)
def test_the_request_fields_choose_the_reply(fields, reply):
    assert direct_intake.feedback_reply(fields) == reply


def test_the_facts_advertise_v4_beside_v3_and_the_client_pins_the_same_values(
    tmp_path, ledger
):
    with_grader, _ = _intake(tmp_path, ledger, {})
    without, _ = _intake(tmp_path, ledger, {}, grader=False)
    facts = _public(with_grader)
    assert facts["exam_feedback_v4"] == client.FEEDBACK_V4_FACTS
    assert facts["exam_feedback_v3"] == client.FEEDBACK_V3_FACTS  # untouched
    assert "exam_feedback_v4" not in _public(without)
    assert client.FEEDBACK_REPLY_SCHEMA_V4 == direct_intake.FEEDBACK_REPLY_SCHEMA_V4
    assert client.GRADE_STATES_V4 == direct_intake.GRADE_STATES_V4
    for name in (
        "FAILURE_CHILDREN",
        "FAILURE_OBSERVATIONS",
        "FAILURE_LIMITS",
        "FAILURE_KEYS",
    ):
        assert getattr(client, name) == getattr(direct_intake, name)


@pytest.fixture
def read(monkeypatch):
    """The client's read against a fixture receiver advertising ``versions``; returns (run, sent fields)."""
    from carbon.development_session import direct_submission

    sent = []
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
    every = {
        "v2": ("exam_feedback_v2", client.FEEDBACK_V2_FACTS),
        "v3": ("exam_feedback_v3", client.FEEDBACK_V3_FACTS),
        "v4": ("exam_feedback_v4", client.FEEDBACK_V4_FACTS),
    }

    def run(reply, *, versions=("v2", "v3", "v4")):
        facts = {"exam_feedback": client.FEEDBACK_FACTS}
        facts.update(dict(every[v] for v in versions))

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
            read=lambda url: facts,
            send=send,
            submission_id=A,
        )

    return run, sent


def test_the_client_asks_v4_where_advertised_and_takes_only_its_allow_listed_shape(
    tmp_path, ledger, read
):
    intake, marks = _v4_intake(tmp_path, ledger, {A: "5Miner"})
    marks._write(A, "CANDIDATE_FAILED", code="WORKER_WALL_LIMIT_REACHED")
    body = intake._feedback("5Miner", submission_id=A, v4=True).body
    run, sent = read
    got = run({k: body[k] for k in ("schema", "submission")})
    assert sent[-1] == {"reply": "v4", "submission_id": A}
    assert got["submission"]["failure"]["observation"] == "WORKER_WALL_LIMIT_REACHED"
    # a receiver without v4 still gets v3, unchanged
    v3 = intake._feedback("5Miner", submission_id=A, v3=True).body
    run({k: v3[k] for k in ("schema", "submission")}, versions=("v2", "v3"))
    assert sent[-1] == {"reply": "v3", "submission_id": A}
    good = body["submission"]["failure"]
    for bad in (
        {**good, "elapsed_seconds": 611.25},  # an extra (measured) field
        {**good, "observation": "exit=137"},  # an open value
        {**good, "child": "prep"},
        {**good, "limit": {"name": "inference_wall_seconds_max", "value": 611.25}},
        {**good, "limit": {"name": "cases_completed", "value": 37}},
        {**good, "code": "Killed at case 37"},
        "WORKER_WALL_LIMIT_REACHED",
    ):
        with pytest.raises(client.DirectIntakeRefusal):
            run(
                {
                    "schema": client.FEEDBACK_REPLY_SCHEMA_V4,
                    "submission": {**body["submission"], "failure": bad},
                }
            )
    for broken in (
        {"submission_id": A, "grade_state": "GRADED"},  # no failure key
        {"submission_id": A, "grade_state": None, "failure": None},  # v4 is never None
        {"submission_id": A, "grade_state": "ON_FIRE", "failure": None},
    ):
        with pytest.raises(client.DirectIntakeRefusal):
            run({"schema": client.FEEDBACK_REPLY_SCHEMA_V4, "submission": broken})


@pytest.mark.parametrize(
    "refusal", ["candidate_program_failed", "carbon_capability_gap", "Not_A_Code!"]
)
def test_the_v4_code_is_the_one_construction_status_shows(tmp_path, ledger, refusal):
    """Validator 16:38: the v4 'code' opens no new channel: it is the refusal code the task's own projection
    (`LeanRecipeAdapter._project`, what construction_status returns) already shows for the same task, or None when
    that code is not a plain token (never a different value)."""
    from carbon.challenge_validator.lean_recipe import LeanRecipeAdapter
    from carbon.research import DirectTaskStateV3

    real = object.__new__(LeanRecipeAdapter)
    real.challenge_id, real.challenge_version = MOTOR.challenge_id, MOTOR.version
    real._evidence_label = "DEVELOPMENT"
    task = SimpleNamespace(
        state=DirectTaskStateV3.REFUSED,
        task_id=SimpleNamespace(value=C),
        terminal_receipt=SimpleNamespace(refusal_code=refusal),
    )
    status = real._project(task, None)  # the construction_status projection
    assert status["state"] == "RECONSTRUCTION_FAILED"
    intake, _ = _v4_intake(
        tmp_path,
        ledger,
        {C: "5Miner"},
        children={C: ("build", "NONZERO_EXIT")},
    )
    intake.adapter.outcome = lambda sid: real._project(task, None)
    state, failure = _v4(intake, "5Miner", C)
    assert state == "RECONSTRUCTION_FAILED"
    shown = status["failure"]["code"]
    assert failure["code"] == (
        shown if shown.islower() and shown.isidentifier() else None
    )


def test_a_slot_returned_graded_resubmit_still_reads_graded(tmp_path, ledger):
    """Validator 17:24 (2): OWNER-RESUBMIT-SLOT-PROMISE-KEEP-01 returns a graded resubmit's slot (RELEASED /
    SLOT_RETURNED); its grade stands, so v4 keeps it GRADED, never NOT_GRADED via the slot fallback.
    """
    from carbon.challenge_validator.exam_cap import ExamCap

    intake, marks = _v4_intake(tmp_path, ledger, {E: "5Miner"})
    marks._write(E, "GRADED", code="carbon_capability_gap")  # a reason v3 leaves None
    _hold(ledger, "5Miner", E, 7_200)
    assert _v4(intake, "5Miner", E) == ("GRADED", None)
    ExamCap(ledger).return_promised_slot(E)
    assert _v4(intake, "5Miner", E) == ("GRADED", None)
