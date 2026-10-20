"""The per-miner graded-submission cap and the epoch limit (OWNER-EXAM-CAP-ROTATION-01)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from carbon.challenge_validator import exam_cap
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.scoring import dual_score

MOTOR = ("electric-motor-magnetics", "1.0")
HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
OTHER = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
EXAM = "sha256:" + "1" * 64
NEXT_EXAM = "sha256:" + "2" * 64


class Clock:
    def __init__(self):
        self.now = 1_000_000_000_000

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def cap(tmp_path, clock):
    directory = tmp_path / "ledger"
    directory.mkdir(mode=0o700)
    return exam_cap.ExamCap(AttemptLedger(directory / "attempts.sqlite3"), clock=clock)


def _reserve(cap, n, *, hotkey=HOTKEY, exam=EXAM, block=None, challenge=MOTOR, **kw):
    # Distinct epochs by default, so the epoch limit does not interfere.
    block = 360 * n if block is None else block
    return cap.reserve(
        hotkey=hotkey,
        challenge_id=challenge[0],
        challenge_version=challenge[1],
        exam_key=exam,
        submission_id=f"rtsk_{n}",
        block=block,
        **kw,
    )


def _grade(cap, n, status="SCORED_DEVELOPMENT_CANDIDATE", **kw):
    slot = _reserve(cap, n, **kw)
    cap.settle(slot, status)
    return slot


def _count(cap, hotkey=HOTKEY, exam=EXAM):
    return cap.count(
        hotkey=hotkey,
        challenge_id=MOTOR[0],
        challenge_version=MOTOR[1],
        exam_key=exam,
    )


def test_the_21st_graded_submission_is_refused(cap):
    for n in range(20):
        _grade(cap, n)
    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        _reserve(cap, 20)
    assert refused.value.code == "exam_cap_reached"


@pytest.mark.parametrize(
    "status",
    [
        "SCORED_DEVELOPMENT_CANDIDATE",
        "MANDATORY_GATE_FAILED",
        "CANDIDATE_INVALID",
        "REQUIRED_LEG_MINIMUM_FAILED",
        "DECISION_OUTCOME_INELIGIBLE",
    ],
)
def test_anything_that_ran_the_sealed_evaluation_counts(cap, status):
    _grade(cap, 0, status)
    assert _count(cap) == 1


@pytest.mark.parametrize(
    "status",
    [
        "CARBON_CAPABILITY_GAP",
        "CANDIDATE_BUILD_REFUSED",
        "FAILED_INFRA",
        "INDETERMINATE_EVIDENCE",
        "DIAGNOSTIC_Q",
    ],
)
def test_gap_refusal_infrastructure_and_unmeasured_results_do_not_count(cap, status):
    for n in range(25):
        _grade(cap, n, status)
    assert _count(cap) == 0
    _grade(cap, 99)  # the cap is untouched


def test_a_second_graded_submission_in_one_epoch_is_refused(cap):
    _grade(cap, 0, block=360 * 5 + 1)
    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        _reserve(cap, 1, block=360 * 5 + 359)
    assert refused.value.code == "epoch_limit_reached"
    _grade(cap, 2, block=360 * 6)  # the next epoch is open


def test_a_released_result_does_not_use_the_epoch(cap):
    _grade(cap, 0, "FAILED_INFRA", block=360)
    _grade(cap, 1, block=361)


def test_an_unsettled_attempt_holds_its_slot(cap):
    for n in range(20):
        _reserve(cap, n)  # reserved, not yet graded
    with pytest.raises(exam_cap.ExamCapRefused, match="exam_cap_reached"):
        _reserve(cap, 20)


def test_a_new_sealed_exam_resets_the_count(cap):
    for n in range(20):
        _grade(cap, n)
    with pytest.raises(exam_cap.ExamCapRefused):
        _reserve(cap, 20)
    _grade(cap, 20, exam=NEXT_EXAM)


def test_counts_are_per_hotkey_and_per_challenge(cap):
    for n in range(20):
        _grade(cap, n)
    _grade(cap, 21, hotkey=OTHER)
    _grade(cap, 22, challenge=("chip-cold-plate", "1.0"))


def test_every_registered_challenge_has_the_cap_and_others_are_refused(cap):
    caps = exam_cap.registered_caps()
    assert set(caps.values()) == {20}
    assert {MOTOR[0], "chip-cold-plate", "f08-ribbed-bracket", "f02"} <= set(caps)
    assert exam_cap.BATTERY_FALLBACK_CAP == 10  # recorded, never applied
    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        _reserve(cap, 0, challenge=("not-registered", "1.0"))
    assert refused.value.code == "exam_cap_unregistered"


def test_a_refusal_writes_no_attempt_row_only_an_audit_line(cap):
    for n in range(20):
        _grade(cap, n)
    with pytest.raises(exam_cap.ExamCapRefused):
        _reserve(cap, 20)
    with cap.ledger._db() as db:
        rows = db.execute("SELECT COUNT(*) FROM exam_graded").fetchone()[0]
        refusals = db.execute(
            "SELECT code FROM operator_refusals WHERE action LIKE 'grading:%'"
        ).fetchall()
    assert rows == 20
    assert refusals == [("exam_cap_reached",)]


def test_a_repeat_for_the_same_submission_reuses_its_slot(cap):
    first = _reserve(cap, 0, block=360)
    assert _reserve(cap, 0, block=360) == first
    cap.settle(first, "SCORED_DEVELOPMENT_CANDIDATE")
    assert _reserve(cap, 0, block=360) == first  # a retry is not a second submission
    assert _count(cap) == 1


def test_a_released_submission_can_be_graded_again(cap):
    first = _grade(cap, 0, "FAILED_INFRA", block=360)
    assert _reserve(cap, 0, block=720) == first


def test_settle_is_a_closed_vocabulary_and_not_repeatable_differently(cap):
    slot = _reserve(cap, 0)
    with pytest.raises(ValueError, match="not classified"):
        cap.settle(slot, "SOMETHING_NEW")
    cap.settle(slot, "CANDIDATE_INVALID")
    cap.settle(slot, "CANDIDATE_INVALID")  # the same settlement is idempotent
    with pytest.raises(ValueError, match="not open"):
        cap.settle(slot, "FAILED_INFRA")


def test_no_block_means_no_grading(cap):
    with pytest.raises(exam_cap.ExamCapRefused, match="exam_cap_block_unavailable"):
        _reserve(cap, 0, block=-1)


def test_a_crashed_reservation_is_released_as_infrastructure_on_recovery(cap, clock):
    for n in range(20):
        _reserve(cap, n)  # all 20 slots held by attempts that never settled
    with pytest.raises(exam_cap.ExamCapRefused):
        _reserve(cap, 20)
    clock.now += 599 * 1_000_000_000
    assert cap.recover(600) == 0  # still within the grading deadline
    clock.now += 2 * 1_000_000_000
    assert cap.recover(600) == 20  # past it: our crash is not charged to the miner
    assert _count(cap) == 0
    with cap.ledger._db() as db:
        statuses = db.execute("SELECT DISTINCT status FROM exam_graded").fetchall()
    assert statuses == [("FAILED_INFRA",)]
    _grade(cap, 20)


def test_recovery_runs_when_a_deadline_is_given_at_construction(tmp_path, clock):
    directory = tmp_path / "ledger"
    directory.mkdir(mode=0o700)
    ledger = AttemptLedger(directory / "attempts.sqlite3")
    first = exam_cap.ExamCap(ledger, clock=clock)
    _reserve(first, 0)
    clock.now += 700 * 1_000_000_000
    restarted = exam_cap.ExamCap(ledger, clock=clock, grading_deadline_seconds=600)
    assert _count(restarted) == 0


def test_a_regrade_bypasses_both_limits_and_is_never_counted(cap):
    for n in range(20):
        _grade(cap, n)  # the king's cap is spent
    _grade(cap, 5, exam=NEXT_EXAM, regrade=True, block=360 * 5)
    _grade(cap, 0, exam=NEXT_EXAM, regrade=True, block=360 * 5)  # same epoch, no limit
    assert _count(cap, exam=NEXT_EXAM) == 0
    assert _count(cap) == 20  # the old exam's count is unchanged
    # and a regrade leaves the king's own graded budget on the new exam untouched
    for n in range(100, 120):
        _grade(cap, n, exam=NEXT_EXAM)


def _record(cap, contract, submission_id, block):
    submission = SimpleNamespace(
        hotkey=HOTKEY,
        receipt={"sequence": 1, "digest": "d", "block": block},
        contract_digest=contract,
    )
    cap.ledger.record(submission, kind="OUTCOME", submission_id=submission_id)


def test_the_block_comes_from_the_signed_receipt_the_submission_arrived_under(cap):
    contract = "sha256:" + "c" * 64
    _record(cap, contract, "rtsk_0", 4321)
    assert exam_cap.submission_block(cap.ledger, contract, "rtsk_0") == 4321
    assert exam_cap.submission_block(cap.ledger, "sha256:" + "d" * 64, "rtsk_0") is None


def _adapter(cap, contract, caps=None):
    snapshot = SimpleNamespace(
        manifest_digest=EXAM,
        read_json_role=lambda *a, **k: {"schema": dual_score.PACK_SCHEMA},
        read_source_registration=lambda root: {"evaluation_version": "exam-v2"},
    )
    return SimpleNamespace(
        discovery=SimpleNamespace(
            evaluation_pack_snapshot=snapshot,
            evaluation_pack_private_root=None,
            evaluation_pack_public_root=None,
        ),
        ledger=cap.ledger,
        owner=lambda sid: HOTKEY,
        challenge_id=MOTOR[0],
        challenge_version=MOTOR[1],
        contract_digest=contract,
        **({} if caps is None else {"exam_cap_caps": caps}),
    )


def _retain(adapter, submission_id):
    result = {"evaluation_pack_digest": "sha256:" + "p" * 64}
    evidence = {"inference_operation": "op", "inference_image_id": "sha256:" + "i" * 64}
    return retention._retain_selected_pack_evaluation(
        adapter, submission_id, result, {"inputs.npz": b""}, evidence
    )


def test_retention_refuses_before_grading_when_the_cap_is_reached(cap):
    """The hook sits before any evaluation: a full cap returns the typed reason."""
    contract = "sha256:" + "c" * 64
    for n in range(20):
        _grade(cap, n)  # under the same sealed exam as the pack's manifest digest
    _record(cap, contract, "rtsk_new", 360 * 30)
    refused = _retain(_adapter(cap, contract), "rtsk_new")
    assert refused["private_evaluation_state"] == "UNAVAILABLE"
    assert refused["private_evaluation_reason"] == "exam_cap_reached"


def test_retention_refuses_an_unregistered_challenge_fail_closed(cap):
    contract = "sha256:" + "c" * 64
    _record(cap, contract, "rtsk_new", 360)
    adapter = _adapter(cap, contract)
    adapter.challenge_id = "not-registered"
    refused = _retain(adapter, "rtsk_new")
    assert refused["private_evaluation_reason"] == "exam_cap_unregistered"


def test_retention_with_no_signed_block_does_not_grade(cap):
    contract = "sha256:" + "c" * 64  # no OUTCOME attempt row: no receipt block
    refused = _retain(_adapter(cap, contract), "rtsk_new")
    assert refused["private_evaluation_reason"] == "exam_cap_block_unavailable"


def test_the_grading_deadline_is_the_challenges_registered_wall_limit():
    material = {
        "construction_limits_document": {
            "reconstruction_resource_policy": {
                "total_reconstruction_wall_seconds_max": 1800
            }
        }
    }
    assert exam_cap.grading_deadline_seconds(material) == 1800
    for missing in ({}, None, {"construction_limits_document": {}}):
        assert exam_cap.grading_deadline_seconds(missing) is None


def test_retention_never_recovers_reservations_only_start_up_does(cap, clock):
    """Recovery is a start-up act: a retention call leaves another attempt's slot alone."""
    contract = "sha256:" + "c" * 64
    _reserve(cap, 7)  # another attempt, left open
    clock.now += 100_000 * 1_000_000_000  # long past any deadline
    _record(cap, contract, "rtsk_new", 360 * 30)
    _retain(_adapter(cap, contract), "rtsk_new")  # reaches the cap hook, then stops
    with cap.ledger._db() as db:
        row = db.execute(
            "SELECT state FROM exam_graded WHERE submission_id='rtsk_7'"
        ).fetchone()
    assert row == ("RESERVED",)
    restarted = exam_cap.ExamCap(cap.ledger, clock=clock, grading_deadline_seconds=1800)
    assert (
        restarted.count(
            hotkey=HOTKEY,
            challenge_id=MOTOR[0],
            challenge_version=MOTOR[1],
            exam_key=EXAM,
        )
        == 0
    )
