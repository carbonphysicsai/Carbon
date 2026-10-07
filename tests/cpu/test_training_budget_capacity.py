"""TRAINING-BUDGET-01 slice 3: R11's cadence capacity, as written."""

from __future__ import annotations

import pytest
from test_training_budget_study import sheet_for

from carbon.training_budget import capacity as cap
from carbon.training_budget import sheet as sheets

TIMES = cap.Times(rebuild_at_screen=30.0, rebuild_at_limit=300.0, grading=6.0)


def test_g_is_r11_by_hand():
    g = cap.gpus(256, TIMES, 16, utilization=0.5)
    assert g == pytest.approx((256 * (30 + 6) + 16 * (300 + 6)) / (72 * 60 * 0.5))


def test_no_safe_screen_rebuilds_everyone_at_l():
    g = cap.gpus(256, TIMES, None, utilization=0.5)
    assert g == pytest.approx((256 * 6 + 256 * (300 + 6)) / (72 * 60 * 0.5))


def test_survivors_never_exceed_submissions():
    assert cap.gpus(4, TIMES, 16, utilization=1) == cap.gpus(4, TIMES, 4, utilization=1)


def test_the_report_states_both_cases_against_the_ceiling():
    sheet = sheet_for("synthetic-one", expected_participation=32, gpu_ceiling=4)
    report = cap.report(sheet, TIMES, None)
    assert report["worst_case"]["submissions_per_tempo"] == 256
    assert report["expected"]["submissions_per_tempo"] == 32
    worst = report["worst_case"]
    assert worst["gpus"] >= worst["G"] and worst["exceeds_gpu_ceiling"]
    assert report["owner_chooses"] and report["assumes_no_duplicates"]


def test_the_report_waits_for_the_sheets_r11_values():
    sheet = sheet_for("synthetic-one", gpu_ceiling=None)
    with pytest.raises(sheets.SheetIncomplete):
        cap.report(sheet, TIMES, None)


@pytest.mark.parametrize(
    ("args", "code"),
    [
        ((-1, TIMES, None), "capacity_submissions_malformed"),
        ((8, cap.Times(None, 0.0, 6.0), None), "capacity_time_malformed"),
        ((8, cap.Times(None, 300.0, 6.0), 4), "capacity_time_malformed"),
        ((8, TIMES, -1), "capacity_survivors_malformed"),
    ],
)
def test_malformed_inputs_are_refused(args, code):
    with pytest.raises(cap.CapacityRefused) as refused:
        cap.gpus(*args, utilization=0.5)
    assert refused.value.code == code


def test_utilization_is_a_fraction():
    with pytest.raises(cap.CapacityRefused):
        cap.gpus(8, TIMES, None, utilization=1.5)
