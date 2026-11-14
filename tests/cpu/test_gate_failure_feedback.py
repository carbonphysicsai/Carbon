"""Gate-failure feedback (owner 14 Nov, "yes tell them"): a gate-failed grade names the failing OUTPUT and one closed REASON
(``over_limit`` | ``invalid_answer``), for every miner, prospectively; never a p90, ratio, class, count or case.

- `gate_failure_feedback.derive`: the allow-list from the custody accuracy record (a SYNTHETIC record here);
- the per-submission store beside the Ladder; the grade-time recording; the signed v6 read and its client; the miner's projection.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import direct_intake
from carbon.challenge_validator import gate_failure_feedback as gff
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.development_session import direct_submission as client
from scripts.dev.miner_launchpad import projection

HOTKEY = "5" + "M" * 47
SID = "rtsk_" + "1" * 64
OTHER_SID = "rtsk_" + "2" * 64
EXAM = "sha256:" + "e" * 64
LEAK = ("p90", "median", "n_invalid", "n_exact", "class", "ratio", "threshold")


def _row(cls, output, verdict, *, n_invalid=0, n_exact=0, p90=0.5, rng="in_range"):
    return {
        "class": cls,
        "range": rng,
        "family": "f",
        "output": output,
        "scored": True,
        "n": 7,
        "median": 0.2,
        "p90": p90,
        "max": 2.0,
        "n_exact": n_exact,
        "max_abs_exact": None,
        "n_invalid": n_invalid,
        "verdict": verdict,
    }


def _record(*rows, statistic="p90"):
    return {
        "schema": "x",
        "rows": list(rows),
        "gate": {"statistic": statistic, "passed": False},
    }


# --- derive: the allow-list ------------------------------------------------------------------------------------------


def test_an_output_over_limit_and_a_class_with_an_invalid_answer_are_named_by_reason_once_per_output():
    record = _record(
        _row("c1", "torque_mean", "FAIL", p90=3.2),
        _row("c1", "efficiency", "PASS"),
        # one invalid answer fails the whole class: BOTH of its outputs fail, as invalid answers
        _row("c2", "torque_mean", "FAIL", n_invalid=1, p90=0.4),
        _row("c2", "core_loss", "FAIL", n_invalid=1, p90=0.1),
        _row("c3", "efficiency", "PASS"),
    )
    # torque_mean fails over the limit in c1 and as an invalid answer in c2: ONE entry, invalid_answer first
    assert gff.derive(record) == [
        {"output": "core_loss", "reason": "invalid_answer"},
        {"output": "torque_mean", "reason": "invalid_answer"},
    ]


def test_two_classes_failing_one_output_for_different_reasons_give_the_single_class_entry_byte_for_byte():
    """V2C 14 Nov: two entries for one output would say there are at least two hidden classes. The list must not depend on how many
    classes fail the output, nor on their order."""
    one_class = _record(_row("c1", "torque_mean", "FAIL", n_invalid=1))
    over_then_invalid = _record(
        _row("c1", "torque_mean", "FAIL", p90=3.2),
        _row("c2", "torque_mean", "FAIL", n_invalid=2),
    )
    invalid_then_over = _record(
        _row("c1", "torque_mean", "FAIL", n_invalid=2),
        _row("c2", "torque_mean", "FAIL", p90=3.2),
    )
    three_classes = _record(
        _row("c1", "torque_mean", "FAIL", p90=3.2),
        _row("c2", "torque_mean", "FAIL", n_invalid=1),
        _row("c3", "torque_mean", "FAIL", n_invalid=5),
        _row("c4", "torque_mean", "FAIL", p90=9.0),
    )
    expected = json.dumps(gff.derive(one_class), sort_keys=True)
    for record in (over_then_invalid, invalid_then_over, three_classes):
        assert json.dumps(gff.derive(record), sort_keys=True) == expected
    assert gff.derive(one_class) == [
        {"output": "torque_mean", "reason": "invalid_answer"}
    ]
    # and over the limit everywhere stays one over_limit entry, however many classes fail it
    over_only = _record(
        _row("c1", "a", "FAIL", p90=2.0), _row("c2", "a", "FAIL", p90=7.0)
    )
    assert gff.derive(over_only) == [{"output": "a", "reason": "over_limit"}]


def test_only_the_failing_in_range_rows_count_and_the_list_is_sorted_and_distinct():
    record = _record(
        _row("c1", "b_out", "FAIL"),
        _row(
            "c2", "b_out", "FAIL"
        ),  # the same output over the limit in two classes: once
        _row("c3", "a_out", "FAIL"),
        _row("c4", "z_out", None, rng="out_of_range"),  # no verdict: never a failure
        _row("c5", "y_out", "PASS"),
    )
    assert gff.derive(record) == [
        {"output": "a_out", "reason": "over_limit"},
        {"output": "b_out", "reason": "over_limit"},
    ]


def test_what_the_record_cannot_explain_is_left_out_never_guessed():
    record = _record(
        _row(
            "c1", "no_value", "FAIL", p90=None
        ),  # a failing row with no value and no invalid answer
        _row("c2", "exact_out", "FAIL", n_exact=2),  # an exact-row case: neither reason
    )
    assert gff.derive(record) is None
    assert gff.derive(_record(_row("c1", "ok", "PASS"))) is None
    for bad in (
        None,
        {},
        [],
        {"rows": []},
        {"rows": 3, "gate": {}},
        _record(statistic=3),
    ):
        assert gff.derive(bad) is None


def test_the_derived_list_carries_the_output_and_the_reason_only():
    record = _record(
        _row("hidden_class_name", "torque_mean", "FAIL", p90=3.2, n_invalid=0),
        _row("hidden_class_other", "core_loss", "FAIL", n_invalid=4),
    )
    failures = gff.derive(record)
    text = json.dumps(failures)
    assert all(set(item) == {"output", "reason"} for item in failures)
    assert "hidden_class" not in text and "3.2" not in text and "4" not in text
    for name in LEAK:
        assert name not in text.replace("over_limit", "").replace("invalid_answer", "")


def test_an_unregistered_looking_output_name_is_never_shown():
    for name in ("Torque", "1x", "a b", "x" * 65, "", "torque/mean", 5, None):
        record = _record(_row("c1", name, "FAIL"))
        assert gff.derive(record) is None


# --- the closed shape -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {"output": "a", "reason": "over_limit"},
        [{"output": "a", "reason": "slow"}],
        [{"output": "a", "reason": "over_limit", "n": 3}],
        [{"output": "a"}],
        [{"output": "B", "reason": "over_limit"}],
        [
            {"output": "b", "reason": "over_limit"},
            {"output": "a", "reason": "over_limit"},
        ],
        [
            {"output": "a", "reason": "over_limit"},
            {"output": "a", "reason": "over_limit"},
        ],
        [
            {"output": "a", "reason": "invalid_answer"},
            {"output": "a", "reason": "over_limit"},
        ],  # two entries for one output
        [{"output": 1, "reason": "over_limit"}],
        "a",
    ],
)
def test_valid_refuses_anything_but_the_closed_list(bad):
    assert gff.valid(bad) is False


def test_valid_accepts_exactly_what_derive_emits():
    record = _record(_row("c1", "b", "FAIL"), _row("c2", "a", "FAIL", n_invalid=2))
    assert gff.valid(gff.derive(record)) is True


# --- the store --------------------------------------------------------------------------------------------------------


@pytest.fixture
def ledger(tmp_path):
    directory = tmp_path / "state"
    directory.mkdir(mode=0o700)
    return AttemptLedger(directory / "attempts.sqlite3")


def test_the_store_keeps_one_list_per_submission_and_exam_and_never_rewrites_it(ledger):
    failures = [{"output": "a", "reason": "over_limit"}]
    assert gff.read(ledger, SID, EXAM) is None  # no table yet: nothing, not an error
    gff.record(ledger, SID, EXAM, failures)
    gff.record(ledger, SID, EXAM, failures)  # idempotent
    assert gff.read(ledger, SID, EXAM) == failures
    assert gff.read(ledger, OTHER_SID, EXAM) is None
    assert gff.read(ledger, SID, "sha256:" + "f" * 64) is None
    with pytest.raises(ValueError, match="gate_failures_changed"):
        gff.record(ledger, SID, EXAM, [{"output": "b", "reason": "invalid_answer"}])
    for bad in ("x", None):
        with pytest.raises(ValueError):
            gff.record(ledger, SID, EXAM, bad)
    with pytest.raises(ValueError):
        gff.record(ledger, "task-1", EXAM, failures)


def test_a_stored_list_that_is_not_the_closed_shape_is_not_served(ledger):
    gff.ensure(ledger)
    with ledger._db() as db:
        db.execute(
            "INSERT INTO gate_failures_v1(submission_id, exam_key, failures) VALUES(?,?,?)",
            (SID, EXAM, json.dumps([{"output": "a", "reason": "slow", "n": 1}])),
        )
    assert gff.read(ledger, SID, EXAM) is None


# --- the grade-time recording ----------------------------------------------------------------------------------------


def test_a_gate_failed_grade_records_its_failures_and_nothing_else_does(ledger):
    adapter = SimpleNamespace(ledger=ledger)
    record = _record(_row("c1", "torque_mean", "FAIL"))
    failed = {"status": "GATE_FAILED"}
    assert retention._record_gate_failures(adapter, SID, EXAM, failed, record) == ""
    assert gff.read(ledger, SID, EXAM) == [
        {"output": "torque_mean", "reason": "over_limit"}
    ]
    for status in ("IMPROVED", "NO_IMPROVEMENT", "NOT_SCORED"):
        assert (
            retention._record_gate_failures(
                adapter, OTHER_SID, EXAM, {"status": status}, record
            )
            == ""
        )
    assert gff.read(ledger, OTHER_SID, EXAM) is None
    # a version with no accuracy record (or nothing identifiable): nothing is claimed
    assert retention._record_gate_failures(adapter, OTHER_SID, EXAM, failed, None) == ""
    assert gff.read(ledger, OTHER_SID, EXAM) is None


def test_a_failure_to_record_never_touches_the_grade_it_says_so(ledger):
    adapter = SimpleNamespace(ledger=SimpleNamespace(path="/nonexistent/x.sqlite3"))
    state = retention._record_gate_failures(
        adapter, SID, EXAM, {"status": "GATE_FAILED"}, _record(_row("c", "a", "FAIL"))
    )
    assert state.startswith(" (gate_failures unavailable: ")


# --- the signed v6 read -------------------------------------------------------------------------------------------------


def _intake(ledger, owners):
    intake = SimpleNamespace(
        challenge=SimpleNamespace(
            challenge_id="electric-motor-magnetics", version="1.8"
        ),
        grade_marker=lambda sid: {"state": "GRADED"},
        adapter=SimpleNamespace(
            owner=lambda sid: owners.get(sid),
            ledger=ledger,
            discovery=SimpleNamespace(
                evaluation_pack_snapshot=SimpleNamespace(manifest_digest=EXAM)
            ),
        ),
        queue_view=SimpleNamespace(held=lambda: None),
    )
    intake._grade_state_v4 = lambda hotkey, sid: ("GRADED", None)
    intake._grade_state = lambda hotkey, sid: "GRADED"
    intake._held = lambda: None
    return intake


def _read(intake, **kw):
    return direct_intake.DirectRecipeIntake._feedback(
        intake, HOTKEY, submission_id=SID, **kw
    )


def test_v6_names_the_failing_outputs_of_the_callers_own_gate_failed_grade(ledger):
    failures = [
        {"output": "core_loss", "reason": "invalid_answer"},
        {"output": "torque_mean", "reason": "over_limit"},
    ]
    gff.record(ledger, SID, EXAM, failures)
    reply = _read(_intake(ledger, {SID: HOTKEY}), v4=True, v5=True, v6=True)
    assert reply.status == 200
    assert reply.body["schema"] == direct_intake.FEEDBACK_REPLY_SCHEMA_V6
    assert reply.body["submission"] == {
        "submission_id": SID,
        "grade_state": "GRADED",
        "failure": None,
        "held_position": None,
        "gate_failures": failures,
    }


def test_v6_says_none_for_a_grade_that_is_not_gate_failed(ledger):
    reply = _read(_intake(ledger, {SID: HOTKEY}), v4=True, v5=True, v6=True)
    assert reply.body["submission"]["gate_failures"] is None


def test_v2_to_v5_replies_never_carry_the_field(ledger):
    gff.record(ledger, SID, EXAM, [{"output": "a", "reason": "over_limit"}])
    intake = _intake(ledger, {SID: HOTKEY})
    for kw in ({"v4": True}, {"v4": True, "v5": True}, {"v3": True}, {}):
        reply = _read(intake, **kw)
        assert "gate_failures" not in reply.body["submission"], kw
        assert reply.body["schema"] != direct_intake.FEEDBACK_REPLY_SCHEMA_V6


def test_v6_never_answers_for_another_hotkeys_submission(ledger):
    gff.record(ledger, SID, EXAM, [{"output": "a", "reason": "over_limit"}])
    reply = _read(_intake(ledger, {SID: "5" + "N" * 47}), v4=True, v5=True, v6=True)
    assert reply.status == 404 and "gate_failures" not in repr(reply.body)


def test_v6_is_a_recognised_reply_and_advertised():
    assert direct_intake.feedback_reply({"reply": "v6", "submission_id": SID}) == "v6"
    assert direct_intake.feedback_reply({"reply": "v7", "submission_id": SID}) is None
    from pathlib import Path

    text = Path(direct_intake.__file__).read_text(encoding="utf-8")
    assert '"exam_feedback_v6"' in text and "FEEDBACK_REPLY_SCHEMA_V6" in text


# --- the client -------------------------------------------------------------------------------------------------------------


@pytest.fixture
def read(monkeypatch):
    sent = []
    recipe = object.__new__(client.ConstructionRecipe)
    monkeypatch.setattr(
        client.ConstructionRecipe,
        "to_dict",
        lambda self: {
            "challenge": {"id": "electric-motor-magnetics", "version": "1.8"}
        },
    )
    monkeypatch.setattr(client, "_body", lambda facts, **kw: {"fields": kw["fields"]})
    monkeypatch.setattr(
        client,
        "BittensorMessageSigner",
        lambda signer: SimpleNamespace(sign=lambda body, **kw: {}),
    )
    every = {
        "v2": ("exam_feedback_v2", client.FEEDBACK_V2_FACTS),
        "v3": ("exam_feedback_v3", client.FEEDBACK_V3_FACTS),
        "v4": ("exam_feedback_v4", client.FEEDBACK_V4_FACTS),
        "v5": ("exam_feedback_v5", client.FEEDBACK_V5_FACTS),
        "v6": ("exam_feedback_v6", client.FEEDBACK_V6_FACTS),
    }

    def run(reply, *, versions=("v2", "v3", "v4", "v5", "v6")):
        facts = {"exam_feedback": client.FEEDBACK_FACTS}
        facts.update(dict(every[v] for v in versions))

        def send(url, body, headers):
            sent.append(body["fields"])
            return 200, {
                "challenge": {"id": "electric-motor-magnetics", "version": "1.8"},
                "best": None,
                "latest": None,
                **reply,
            }

        return client.read_exam_feedback(
            "http://127.0.0.1:1",
            "external-signer",
            recipe=recipe,
            contract_digest="sha256:" + "c" * 64,
            receiver="validator",
            context=None,
            read=lambda url: facts,
            send=send,
            submission_id=SID,
        )

    return run, sent


def _v6(failures, grade_state="GRADED"):
    return {
        "schema": client.FEEDBACK_REPLY_SCHEMA_V6,
        "submission": {
            "submission_id": SID,
            "grade_state": grade_state,
            "failure": None,
            "held_position": None,
            "gate_failures": failures,
        },
    }


def test_the_client_asks_v6_where_advertised_and_reads_the_failures(read):
    run, sent = read
    failures = [{"output": "torque_mean", "reason": "over_limit"}]
    got = run(_v6(failures))
    assert sent[-1] == {"reply": "v6", "submission_id": SID}
    assert got["submission"]["gate_failures"] == failures
    assert run(_v6(None))["submission"]["gate_failures"] is None


def test_a_receiver_without_v6_still_gets_v5_unchanged(read):
    run, sent = read
    run(
        {
            "schema": client.FEEDBACK_REPLY_SCHEMA_V5,
            "submission": {
                "submission_id": SID,
                "grade_state": "GRADED",
                "failure": None,
                "held_position": None,
            },
        },
        versions=("v2", "v3", "v4", "v5"),
    )
    assert sent[-1] == {"reply": "v5", "submission_id": SID}


@pytest.mark.parametrize(
    "bad",
    [
        [],
        [{"output": "a", "reason": "slow"}],
        [{"output": "a", "reason": "over_limit", "p90": 3.1}],
        [{"output": "a", "reason": "over_limit", "class": "c1"}],
        {"output": "a", "reason": "over_limit"},
    ],
)
def test_the_client_refuses_a_failure_list_that_is_not_the_closed_shape(read, bad):
    run, _sent = read
    with pytest.raises(client.DirectIntakeRefusal) as refused:
        run(_v6(bad))
    assert "exam_feedback_reply_invalid" in str(refused.value)


def test_the_client_refuses_a_v6_reply_without_the_field(read):
    run, _sent = read
    reply = _v6(None)
    del reply["submission"]["gate_failures"]
    with pytest.raises(client.DirectIntakeRefusal):
        run(reply)


# --- the miner's projection ----------------------------------------------------------------------------------------------


def _ladder(failures, *, status="GATE_FAILED", digest="sha256:" + "d" * 64):
    return {
        "best": None,
        "latest": {
            "schema": "carbon.private-exam.ladder-feedback.v3",
            "exam_version": "v",
            "status": status,
            "total": None,
            "gate_names": ["in_range_accuracy"] if status == "GATE_FAILED" else [],
            "recipe_digest": digest,
            "epoch": 4,
        },
        "submission": {
            "submission_id": SID,
            "grade_state": "GRADED",
            "failure": None,
            "held_position": None,
            "gate_failures": failures,
        },
    }


def test_the_projection_names_the_failing_outputs_in_words_and_as_data():
    failures = [
        {"output": "core_loss", "reason": "invalid_answer"},
        {"output": "torque_mean", "reason": "over_limit"},
    ]
    digest = "sha256:" + "d" * 64
    shown = projection._grade(_ladder(failures), submission=digest)
    assert shown["latest"]["gate_failures"] == failures
    words = shown["latest"]["words"]
    assert "in range accuracy" in words
    assert (
        "core_loss: an invalid answer" in words
        and "torque_mean: over the limit" in words
    )
    for name in LEAK:
        assert name not in words.replace("in range accuracy", "")


def test_the_projection_shows_nothing_extra_for_another_status_or_a_bad_list():
    digest = "sha256:" + "d" * 64
    ok = [{"output": "a", "reason": "over_limit"}]
    other = projection._grade(_ladder(ok, status="NO_IMPROVEMENT"), submission=digest)
    assert "gate_failures" not in other["latest"]
    bad = projection._grade(
        _ladder([{"output": "a", "reason": "slow"}]), submission=digest
    )
    assert (
        "gate_failures" not in bad["latest"]
        and "failing output" not in bad["latest"]["words"]
    )
    none = projection._grade(_ladder(None), submission=digest)
    assert "gate_failures" not in none["latest"]
    # a grade that is not this submission's is never given this submission's failures
    foreign = projection._grade(_ladder(ok), submission="sha256:" + "0" * 64)
    assert foreign["latest"] is None
