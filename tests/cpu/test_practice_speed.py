"""The practice speed result (PRACTICE_FEEDBACK_NEW_EXAM_20261025 row 5; Validator
ruling: publish the 500x rule and the ceilings, label practice timing "on your
machine; the exam measures on the validator class"): seconds per design against
the registered ceiling, from the cold query the practice already knows how to
time."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from carbon.challenge_registry import speed_gate
from carbon.scoring import practice_dual, practice_speed
from scripts.dev.miner_launchpad import campaign_view

RECEIPT = {
    "measurement": {
        "timing_s": {
            "preprocess": 2.0,
            "inference": 16.0,
            "postprocess": 1.0,
            "export": 100.0,
        }
    }
}


def test_seconds_per_design_against_the_registered_ceiling():
    # F02: the solver needs 190 s per design, so the ceiling is 190 / 500 = 0.38 s.
    block = practice_speed.speed_block("f02", seconds=19.0, designs=100)
    assert block["seconds_per_design"] == pytest.approx(0.19)
    assert block["ceiling_seconds_per_design"] == speed_gate.ceiling_seconds("f02")
    assert block["ceiling_seconds_per_design"] == 0.38
    assert block["within_ceiling"] is True
    assert block["times_faster_than_solver"] == pytest.approx(1000.0)
    assert block["ratio_required"] == 500
    assert block["label"] == "on your machine; the exam measures on the validator class"


def test_over_the_ceiling_says_so():
    block = practice_speed.speed_block("f02", seconds=100.0, designs=100)
    assert block["within_ceiling"] is False
    assert block["times_faster_than_solver"] < speed_gate.RATIO


@pytest.mark.parametrize(
    "kind,gate",
    [
        ("f02", "f02"),
        ("f08", "f08-ribbed-bracket"),
        ("cooling", "chip-cold-plate"),
        ("motor", "electric-motor-magnetics"),
    ],
)
def test_every_challenge_reads_its_own_registered_numbers(kind, gate):
    block = practice_speed.speed_block(kind, seconds=1.0, designs=1)
    assert block["ceiling_seconds_per_design"] == speed_gate.ceiling_seconds(gate)
    assert (
        block["solver_seconds_per_design"] == speed_gate.SOLVER_SECONDS_PER_DESIGN[gate]
    )


@pytest.mark.parametrize(
    "kind,seconds,designs",
    [
        ("f02", 0, 10),
        ("f02", -1.0, 10),
        ("f02", float("nan"), 10),
        ("f02", float("inf"), 10),
        ("f02", 5.0, 0),
        ("f02", 5.0, -3),
        ("f02", 5.0, 2.5),
        ("f02", True, 10),
        ("battery", 5.0, 10),
        ("unknown", 5.0, 10),
    ],
)
def test_no_result_for_a_measurement_that_means_nothing(kind, seconds, designs):
    assert practice_speed.speed_block(kind, seconds=seconds, designs=designs) is None


def test_the_receipt_counts_the_models_time_and_not_the_export():
    block = practice_speed.from_receipt("f02", RECEIPT, designs=19)
    assert block["seconds_per_design"] == pytest.approx(1.0)  # (2 + 16 + 1) / 19


@pytest.mark.parametrize(
    "receipt",
    [
        None,
        {},
        {"measurement": None},
        {"measurement": {"timing_s": {"preprocess": 1.0}}},
        {
            "measurement": {
                "timing_s": {"preprocess": "1", "inference": 1, "postprocess": 1}
            }
        },
    ],
)
def test_a_receipt_without_a_measurement_gives_none(receipt):
    assert practice_speed.from_receipt("f02", receipt, designs=10) is None


def test_only_a_real_worker_run_is_timed_and_an_untimed_result_has_no_speed():
    assert practice_speed.measure(None) is True
    assert practice_speed.measure(object()) is False
    assert (
        practice_speed.from_result("f02", SimpleNamespace(timed=None), designs=5)
        is None
    )
    timed = SimpleNamespace(timed=SimpleNamespace(receipt=RECEIPT))
    assert practice_speed.from_result("f02", timed, designs=19)["designs"] == 19


def test_the_dual_block_carries_the_speed_result(monkeypatch):
    monkeypatch.setattr(
        practice_dual, "feedback_v2", lambda kind, version, predict: {"available": True}
    )
    speed = practice_speed.speed_block("f08", seconds=10.0, designs=10)
    assert (
        practice_dual.from_rows_v2("f08", "1.5", [[1.0]], speed=speed)["speed"] == speed
    )
    assert "speed" not in practice_dual.from_rows_v2("f08", "1.5", [[1.0]])
    monkeypatch.setattr(
        practice_dual,
        "feedback_v2",
        lambda kind, version, predict: {"available": False, "reason": "x"},
    )
    assert "speed" not in practice_dual.from_rows_v2("f08", "1.5", [[1.0]], speed=speed)


def _doc(speed):
    return {
        "outcome": {
            "practice_dual": {
                "schema": campaign_view.DUAL_FEEDBACK_SCHEMA_V2,
                "available": True,
                "gates": {},
                "eligible": True,
                "total": 0.5,
                "accuracy": 0.5,
                "design_value": 0.5,
                "n_cases": 4,
                "speed": speed,
            }
        }
    }


def test_the_page_reader_allow_lists_the_speed_result():
    block = practice_speed.speed_block("f02", seconds=19.0, designs=100)
    shown = campaign_view.dual_feedback(_doc(block))["speed"]
    assert shown["seconds_per_design"] == pytest.approx(0.19)
    assert shown["ceiling_seconds_per_design"] == 0.38
    assert shown["within_ceiling"] is True
    assert shown["label"] == practice_speed.LABEL
    assert shown["scope"] == "practice (this machine)"
    # Carbon's own words, never the document's.
    hostile = {**block, "label": "this is the exam grade", "extra": "x"}
    shown = campaign_view.dual_feedback(_doc(hostile))["speed"]
    assert shown["label"] == practice_speed.LABEL
    assert "extra" not in shown
    # No schema, or unusable numbers: nothing is shown.
    assert campaign_view.dual_feedback(_doc({**block, "schema": "x"}))["speed"] is None
    assert (
        campaign_view.dual_feedback(_doc({**block, "seconds_per_design": "fast"}))[
            "speed"
        ]
        is None
    )
    assert campaign_view.dual_feedback(_doc(None))["speed"] is None


def test_a_timing_run_that_did_not_finish_is_named_not_measured():
    timed_out = SimpleNamespace(timed=None)
    block = practice_speed.from_result("f02", timed_out, designs=5, requested=True)
    assert block["schema"] == practice_speed.SCHEMA
    assert block["measured"] is False
    assert "not measured" in block["note"]
    assert block["label"] == practice_speed.LABEL
    # Not asked for (a test runner stands in for the worker): no speed at all.
    assert practice_speed.from_result("f02", timed_out, designs=5) is None
    # A timing receipt with no usable measurement is the same named state.
    empty = SimpleNamespace(timed=SimpleNamespace(receipt={}))
    assert (
        practice_speed.from_result("f02", empty, designs=5, requested=True)["measured"]
        is False
    )


def test_the_page_shows_a_speed_that_was_not_measured_in_words():
    block = practice_speed.not_measured("f02")
    shown = campaign_view.dual_feedback(_doc(block))["speed"]
    assert shown["measured"] is False
    assert "not measured" in shown["note"]
    assert shown["label"] == practice_speed.LABEL
    assert "seconds_per_design" not in shown


def test_optional_timed_swallows_only_a_failed_timing_run():
    from carbon.development_session.bundle_construction_worker import optional_timed
    from carbon.reconstruction.worker.model import WorkerCode, WorkerFailure

    def raising(error):
        def run():
            raise error

        return run

    assert optional_timed(lambda: "timed") == "timed"
    for code in (WorkerCode.RUNTIME, WorkerCode.DEADLINE, WorkerCode.UNAVAILABLE):
        assert optional_timed(raising(WorkerFailure(code))) is None
    assert optional_timed(raising(TimeoutError())) is None
    for code in (WorkerCode.CLEANUP, WorkerCode.QUARANTINED, WorkerCode.CANCELLED):
        with pytest.raises(WorkerFailure):
            optional_timed(raising(WorkerFailure(code)))
