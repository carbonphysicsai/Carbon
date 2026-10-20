"""Submission cadence and the exam key's age limit (OWNER-CADENCE-AND-ROTATION-02)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import exam_cap
from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.challenge_validator.ledger import AttemptLedger
from carbon.scoring import dual_score

MOTOR = ("electric-motor-magnetics", "1.0")
COOLING = ("chip-cold-plate", "1.0")
HOTKEY = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
OTHER = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
EXAM = "sha256:" + "1" * 64
NEXT_EXAM = "sha256:" + "2" * 64
PLACEHOLDERS = {
    "electric-motor-magnetics": 1.0,
    "chip-cold-plate": 1.0,
    "f08-ribbed-bracket": 0.5,
    "f02": 0.2,
    "battery-fastcharge-ageing-development-v1": 2.0,
}  # sum 4.7 CPU-h, the approved proposal's table


def cadence(capacity=270.0, placeholders=None):
    return {
        "capacity_cpu_hours_per_day": capacity,
        "rebuild_cpu_hours_placeholder": dict(placeholders or PLACEHOLDERS),
    }


class Clock:
    def __init__(self):
        self.now = 1_000_000_000_000

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


def make_cap(tmp_path, clock, **options):
    directory = tmp_path / "ledger"
    directory.mkdir(mode=0o700, exist_ok=True)
    return exam_cap.ExamCap(
        AttemptLedger(directory / "attempts.sqlite3"), clock=clock, **options
    )


@pytest.fixture
def cap(tmp_path, clock):
    """The committed registry: 67.2 CPU-h a day (the registered 4-vCPU host class)."""
    return make_cap(tmp_path, clock)


@pytest.fixture
def tight(tmp_path, clock):
    """9.4 CPU-h a day: one miner may grade 2 a day, two active miners 1 each."""
    return make_cap(tmp_path, clock, cadence=cadence(9.4))


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


def _grade(cap, n, status="SCORED_DEVELOPMENT_CANDIDATE", cpu_seconds=None, **kw):
    slot = _reserve(cap, n, **kw)
    cap.settle(slot, status, cpu_seconds=cpu_seconds)
    return slot


def _count(cap, hotkey=HOTKEY, exam=EXAM):
    return cap.count(
        hotkey=hotkey,
        challenge_id=MOTOR[0],
        challenge_version=MOTOR[1],
        exam_key=exam,
    )


# --- the registry -----------------------------------------------------------------


def test_the_committed_registry_is_the_approved_proposals_table():
    registered = exam_cap.registered_cadence()
    # R = nproc x 24 h x 0.7 for the registered validator host class (4 vCPU).
    assert registered["capacity_cpu_hours_per_day"] == pytest.approx(4 * 24 * 0.7)
    assert registered["rebuild_cpu_hours_placeholder"] == PLACEHOLDERS
    assert set(PLACEHOLDERS) == set(exam_cap.registered_challenges())
    document = json.loads(exam_cap.REGISTRY.read_bytes())
    assert document["source"].startswith(
        "OWNER-CADENCE-AND-ROTATION-02, proposal rev 2"
    )
    assert "OWNER-VALIDATOR-HOST-CLASS-01" in document["source"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(capacity_cpu_hours_per_day=0),
        lambda d: d.update(capacity_cpu_hours_per_day="270"),
        lambda d: d.update(capacity_cpu_hours_per_day=float("nan")),
        lambda d: d.update(schema="other"),
        lambda d: d.update(source=""),
        lambda d: d.update(extra=1),
        lambda d: d["rebuild_cpu_hours_placeholder"].update(f02=0),
        lambda d: d.pop("rebuild_cpu_hours_placeholder"),
    ],
)
def test_a_malformed_registry_refuses_fail_closed(tmp_path, mutate):
    document = json.loads(exam_cap.REGISTRY.read_bytes())
    mutate(document)
    path = tmp_path / "exam_cadence.json"
    path.write_text(json.dumps(document))
    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        exam_cap.registered_cadence(path)
    assert refused.value.code == "exam_cadence_unregistered"
    with pytest.raises(exam_cap.ExamCapRefused):
        exam_cap.registered_cadence(tmp_path / "absent.json")


def test_without_a_registry_grading_refuses_not_defaults(tmp_path, clock, monkeypatch):
    monkeypatch.setattr(exam_cap, "REGISTRY", tmp_path / "absent.json")
    unregistered = make_cap(tmp_path, clock)
    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        _reserve(unregistered, 0)
    assert refused.value.code == "exam_cadence_unregistered"


# --- the cadence ------------------------------------------------------------------


# floor(67.2 / (miners x 4.7)), at least 1, for the registered 4-vCPU host class.
@pytest.mark.parametrize("miners, expected", [(2, 7), (5, 2), (25, 1), (100, 1)])
def test_the_allowance_follows_the_approved_tables_miner_counts(cap, miners, expected):
    for n in range(miners - 1):  # the others are active in the rolling day
        _grade(cap, n, hotkey=f"hotkey-{n}", block=360 * 30 + n)
    view = cap.allowance(hotkey=HOTKEY, block=360 * 30)
    assert view["active_miners"] == miners
    assert view["allowance"] == expected
    assert view["sum_rebuild_cpu_hours"] == pytest.approx(4.7)


def test_a_daily_allowance_refuses_the_next_graded_submission(tight):
    _grade(tight, 0)
    _grade(tight, 1)
    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        _reserve(tight, 2)
    assert refused.value.code == "exam_daily_allowance_reached"
    # The rolling day moves on: 20 epochs later the first has left the window.
    _grade(tight, 3, block=360 * 20)


def test_more_active_miners_shrink_everyones_allowance_together(tight):
    _grade(tight, 0)
    _grade(tight, 1, hotkey=OTHER, block=360 * 5)
    # With two active miners a = floor(9.4 / (2 * 4.7)) = 1: the first has used it.
    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        _reserve(tight, 2, block=360 * 6)
    assert refused.value.code == "exam_daily_allowance_reached"


def test_the_allowance_is_per_challenge(tight):
    _grade(tight, 0)
    _grade(tight, 1)
    _grade(tight, 2, challenge=COOLING)  # another Challenge has its own allowance


def test_the_floor_is_one_a_day_however_many_miners(tight):
    for n in range(40):
        _grade(tight, n, hotkey=f"hotkey-{n}", block=360 * 30 + n)
    assert tight.allowance(hotkey=HOTKEY, block=360 * 30)["allowance"] == 1
    _grade(tight, 99, block=360 * 30)  # the floor still lets the first one in


def test_measured_rebuild_time_replaces_the_placeholder_for_that_challenge(tight):
    # Motor's measured mean rebuild is 2 CPU-h (not the placeholder 1.0), so sum t = 5.7
    # and a = floor(9.4 / 5.7) = 1.
    _grade(tight, 0, cpu_seconds=2 * 3600.0)
    view = tight.allowance(hotkey=HOTKEY, block=360 * 1)
    assert view["sum_rebuild_cpu_hours"] == pytest.approx(5.7)
    assert view["allowance"] == 1
    with pytest.raises(exam_cap.ExamCapRefused, match="exam_daily_allowance_reached"):
        _reserve(tight, 1)


def test_released_attempts_neither_count_nor_make_a_miner_active(tight):
    _grade(tight, 0, "FAILED_INFRA", hotkey=OTHER, block=360 * 5, cpu_seconds=99999.0)
    view = tight.allowance(hotkey=HOTKEY, block=360 * 6)
    assert view["active_miners"] == 1
    assert view["sum_rebuild_cpu_hours"] == pytest.approx(4.7)  # its time is ignored


def test_rebuild_cpu_seconds_must_be_a_finite_non_negative_number(tight):
    slot = _reserve(tight, 0)
    for bad in (-1.0, float("nan"), float("inf"), "3"):
        with pytest.raises(ValueError, match="cpu seconds"):
            tight.settle(slot, "SCORED_DEVELOPMENT_CANDIDATE", cpu_seconds=bad)


def test_there_is_no_per_version_cap_any_more(cap):
    for n in range(40):
        # One a day, far more than the old C = 20 under one exam key.
        _grade(cap, n, block=360 * 20 * n)
    _grade(cap, 40, block=360 * 20 * 40)


# --- counting, as before ------------------------------------------------------------


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
def test_gap_refusal_infrastructure_and_unmeasured_results_do_not_count(tight, status):
    for n in range(25):
        _grade(tight, n, status)
    assert _count(tight) == 0
    _grade(tight, 99)  # the allowance is untouched


def test_a_second_graded_submission_in_one_epoch_is_refused(cap):
    _grade(cap, 0, block=360 * 5 + 1)
    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        _reserve(cap, 1, block=360 * 5 + 359)
    assert refused.value.code == "epoch_limit_reached"
    _grade(cap, 2, block=360 * 6)  # the next epoch is open


def test_a_released_result_does_not_use_the_epoch(cap):
    _grade(cap, 0, "FAILED_INFRA", block=360)
    _grade(cap, 1, block=361)


def test_an_unsettled_attempt_holds_its_slot(tight):
    _reserve(tight, 0)  # reserved, not yet graded
    _reserve(tight, 1)
    with pytest.raises(exam_cap.ExamCapRefused, match="exam_daily_allowance_reached"):
        _reserve(tight, 2)


def test_counts_are_per_hotkey_and_per_challenge(cap):
    for n in range(3):
        _grade(cap, n)
    assert _count(cap) == 3
    assert _count(cap, hotkey=OTHER) == 0
    assert (
        cap.count(hotkey=HOTKEY, challenge_id=COOLING[0], exam_key=EXAM) == 0
    )  # version and key are optional filters


def test_an_unregistered_challenge_is_refused_fail_closed(cap):
    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        _reserve(cap, 0, challenge=("not-registered", "1.0"))
    assert refused.value.code == "exam_cap_unregistered"


def test_a_refusal_writes_no_attempt_row_only_an_audit_line(tight):
    _grade(tight, 0)
    _grade(tight, 1)
    with pytest.raises(exam_cap.ExamCapRefused):
        _reserve(tight, 2)
    with tight.ledger._db() as db:
        rows = db.execute("SELECT COUNT(*) FROM exam_graded").fetchone()[0]
        refusals = db.execute(
            "SELECT code FROM operator_refusals WHERE action LIKE 'grading:%'"
        ).fetchall()
    assert rows == 2
    assert refusals == [("exam_daily_allowance_reached",)]


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


def test_a_crashed_reservation_is_released_as_infrastructure_on_recovery(tight, clock):
    _reserve(tight, 0)
    _reserve(tight, 1)  # both slots held by attempts that never settled
    with pytest.raises(exam_cap.ExamCapRefused):
        _reserve(tight, 2)
    clock.now += 599 * 1_000_000_000
    assert tight.recover(600) == 0  # still within the grading deadline
    clock.now += 2 * 1_000_000_000
    assert tight.recover(600) == 2  # past it: our crash is not charged to the miner
    assert _count(tight) == 0
    with tight.ledger._db() as db:
        statuses = db.execute("SELECT DISTINCT status FROM exam_graded").fetchall()
    assert statuses == [("FAILED_INFRA",)]
    _grade(tight, 20)


def test_recovery_runs_when_a_deadline_is_given_at_construction(tmp_path, clock):
    first = make_cap(tmp_path, clock)
    _reserve(first, 0)
    clock.now += 700 * 1_000_000_000
    restarted = exam_cap.ExamCap(
        first.ledger, clock=clock, grading_deadline_seconds=600
    )
    assert _count(restarted) == 0


def test_a_ledger_from_before_the_cadence_gains_the_cpu_column(tmp_path, clock):
    directory = tmp_path / "ledger"
    directory.mkdir(mode=0o700)
    ledger = AttemptLedger(directory / "attempts.sqlite3")
    with ledger._db() as db:
        db.execute(
            "CREATE TABLE exam_graded(id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "hotkey TEXT NOT NULL, challenge_id TEXT NOT NULL, challenge_version TEXT "
            "NOT NULL, exam_key TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'GRADED', "
            "epoch INTEGER NOT NULL, submission_id TEXT NOT NULL, state TEXT NOT NULL, "
            "status TEXT, reserved_ns INTEGER NOT NULL, settled_ns INTEGER, "
            "UNIQUE(challenge_id, challenge_version, exam_key, submission_id))"
        )
    upgraded = exam_cap.ExamCap(ledger, clock=clock)
    _grade(upgraded, 0, cpu_seconds=10.0)


# --- regrade ------------------------------------------------------------------------


def test_a_regrade_bypasses_every_limit_and_is_never_counted(tight):
    _grade(tight, 0)
    _grade(tight, 1)  # the king's allowance is spent
    _grade(tight, 5, exam=NEXT_EXAM, regrade=True, block=360 * 1)
    _grade(tight, 0, exam=NEXT_EXAM, regrade=True, block=360 * 1)  # same epoch too
    tight.reserve(  # no signed block either
        hotkey=HOTKEY,
        challenge_id=MOTOR[0],
        challenge_version=MOTOR[1],
        exam_key=NEXT_EXAM,
        submission_id="rtsk_none",
        block=None,
        regrade=True,
    )
    assert _count(tight, exam=NEXT_EXAM) == 0
    assert _count(tight) == 2  # the old exam's count is unchanged
    # a regrade's compute never moves the cadence
    assert tight.allowance(hotkey=HOTKEY, block=360 * 2)["active_miners"] == 1


# --- the exam key's age -------------------------------------------------------------


def test_an_exam_key_is_refused_at_ninety_days_from_its_first_block(cap, capsys):
    first = 360
    _grade(cap, 0, block=first)
    limit = first + exam_cap.MAX_EXAM_AGE_BLOCKS
    assert exam_cap.MAX_EXAM_AGE_BLOCKS == 648_000
    _grade(cap, 1, block=limit - 1)  # one block short of 90 days: still open
    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        _reserve(cap, 2, block=limit)
    assert refused.value.code == "exam_key_expired"
    logged = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert logged["event"] == "exam_key_expired" and logged["challenge"] == MOTOR[0]
    # A rotated key starts its own clock; a regrade never ages or is refused.
    _grade(cap, 3, exam=NEXT_EXAM, block=limit + 360)
    _grade(cap, 4, regrade=True, block=limit)


def test_the_age_is_per_exam_key(cap):
    _grade(cap, 0, block=360)
    _grade(cap, 1, exam=NEXT_EXAM, block=360 + exam_cap.MAX_EXAM_AGE_BLOCKS)
    with pytest.raises(exam_cap.ExamCapRefused, match="exam_key_expired"):
        _reserve(cap, 2, block=360 + exam_cap.MAX_EXAM_AGE_BLOCKS)


# --- the block, the retention hook, start-up ------------------------------------------


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


def _adapter(cap, contract, exam_cadence=None):
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
        **({} if exam_cadence is None else {"exam_cadence": exam_cadence}),
    )


def _retain(adapter, submission_id):
    result = {"evaluation_pack_digest": "sha256:" + "p" * 64}
    evidence = {"inference_operation": "op", "inference_image_id": "sha256:" + "i" * 64}
    return retention._retain_selected_pack_evaluation(
        adapter, submission_id, result, {"inputs.npz": b""}, evidence
    )


def test_retention_refuses_before_grading_when_the_allowance_is_reached(tight):
    """The hook sits before any evaluation: a spent allowance returns the typed reason."""
    contract = "sha256:" + "c" * 64
    _grade(tight, 0)
    _grade(tight, 1)  # under the same sealed exam as the pack's manifest digest
    _record(tight, contract, "rtsk_new", 360 * 5)
    refused = _retain(_adapter(tight, contract, cadence(9.4)), "rtsk_new")
    assert refused["private_evaluation_state"] == "UNAVAILABLE"
    assert refused["private_evaluation_reason"] == "exam_daily_allowance_reached"


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


def test_rebuild_cpu_seconds_come_from_the_ledgers_operation_receipts(tmp_path):
    import sqlite3

    database = tmp_path / "operations.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE operations(id TEXT PRIMARY KEY, actual BLOB)")
        for operation, milliseconds in (
            ("operation-build", 600_000),
            ("operation-infer", 30_000),
            ("operation-timed", 10_000),
        ):
            db.execute(
                "INSERT INTO operations VALUES(?,?)",
                (operation, json.dumps({"numerical_milliseconds": milliseconds})),
            )

    class Ledger:
        def db(self):
            return sqlite3.connect(database)

    provider = SimpleNamespace(ledger=Ledger())
    adapter = SimpleNamespace(
        discovery=SimpleNamespace(
            _material={
                "construction_limits_document": {
                    "reconstruction_resource_policy": {"cpu_count_max": 2}
                }
            }
        ),
        owner=lambda sid: HOTKEY,
        _provider=lambda owner: provider,
    )
    evidence = {
        "build_operation": "operation-build",
        "inference_operation": "operation-infer",
        "timed_operation": "operation-timed",
    }
    # (600 + 30 + 10) s of compute on 2 CPUs; the pair operations carry no receipt here.
    assert retention._rebuild_cpu_seconds(
        adapter, "rtsk_x", evidence, EXAM
    ) == pytest.approx(1280.0)
    # No receipt at all leaves the placeholder in force.
    assert retention._rebuild_cpu_seconds(adapter, "rtsk_x", {}, EXAM) is None


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


def test_retention_never_recovers_reservations_only_start_up_does(tight, clock):
    """Recovery is a start-up act: a retention call leaves another attempt's slot alone."""
    contract = "sha256:" + "c" * 64
    _reserve(tight, 7)  # another attempt, left open
    clock.now += 100_000 * 1_000_000_000  # long past any deadline
    _record(tight, contract, "rtsk_new", 360 * 30)
    _retain(_adapter(tight, contract, cadence(9.4)), "rtsk_new")
    with tight.ledger._db() as db:
        row = db.execute(
            "SELECT state FROM exam_graded WHERE submission_id='rtsk_7'"
        ).fetchone()
    assert row == ("RESERVED",)
    restarted = exam_cap.ExamCap(
        tight.ledger, clock=clock, grading_deadline_seconds=1800
    )
    assert _count(restarted) == 0


def test_a_registered_challenge_without_the_wall_policy_refuses_to_start():
    material = {"construction_limits_document": {"reconstruction_resource_policy": {}}}
    for challenge_id in (MOTOR[0], "chip-cold-plate", "f08-ribbed-bracket", "f02"):
        with pytest.raises(exam_cap.ExamCapRefused) as refused:
            exam_cap.require_grading_deadline(material, challenge_id)
        assert refused.value.code == "exam_cap_deadline_unregistered"
    assert exam_cap.require_grading_deadline(material, "not-registered") is None
    present = {
        "construction_limits_document": {
            "reconstruction_resource_policy": {
                "total_reconstruction_wall_seconds_max": 900
            }
        }
    }
    assert exam_cap.require_grading_deadline(present, MOTOR[0]) == 900


def test_receiver_start_up_refuses_before_restoring_when_the_policy_is_missing(
    tmp_path,
):
    from carbon.challenge_validator import direct_receiver

    ledger = AttemptLedger(tmp_path / "attempts.sqlite3")
    restored = []

    def discovery(challenge_id, material):
        return SimpleNamespace(
            _material=material,
            info=SimpleNamespace(
                challenge_key=SimpleNamespace(challenge_id=challenge_id)
            ),
        )

    with pytest.raises(exam_cap.ExamCapRefused) as refused:
        direct_receiver._exam_cap_startup(
            ledger, discovery(MOTOR[0], {}), lambda: restored.append(1)
        )
    assert refused.value.code == "exam_cap_deadline_unregistered" and not restored
    uncapped = discovery("some-fixture", {})
    direct_receiver._exam_cap_startup(ledger, uncapped, lambda: restored.append(1))
    assert restored == [1]
