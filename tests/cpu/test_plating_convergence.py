"""PLATING-CONVERGENCE-01: the ladder, the extrapolation and the summary
(no PyBaMM: the solves themselves run in the pinned image)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev.battery import plating_convergence as pc

REPOSITORY = Path(__file__).resolve().parents[2]
CASES = REPOSITORY / "docs/development/evidence/plating-convergence-01/cases.json"


def test_the_registered_case_list_is_ten_public_near_onset_cases():
    document = json.loads(CASES.read_text(encoding="utf-8"))
    assert document["schema"] == pc.CASES_SCHEMA
    cases = document["cases"]
    assert len(cases) == 10
    assert len({c["question"] for c in cases}) == 10  # one per question
    assert all(
        abs(c["reference_margin_v"]) < document["threshold_v"] + 1e-4 for c in cases
    )


def test_the_ladder_is_fixed_and_the_finest_rung_is_limited():
    jobs = pc.ladder([{}] * 10)
    assert len(jobs) == 10 * 6 + 1 + pc.FINE_CASES
    meshes = sorted({j["mesh"] for j in jobs})
    assert tuple(meshes) == pc.MESHES
    assert sum(j["mesh"] == 320 for j in jobs) == pc.FINE_CASES
    standard = [j for j in jobs if j["mesh"] == 20 and j["cycles"] == 1]
    assert all(j["rtol"] == 1e-5 for j in standard)  # the reference's own rung
    assert [j for j in jobs if j["cycles"] == 30] == [
        {"case": 0, "mesh": 20, "rtol": 1e-5, "period_s": None, "cycles": 30}
    ]


def test_richardson_recovers_a_second_order_limit():
    limit = 1.0e-3
    margins = [limit + 4e-4 * h**2 for h in (1.0, 0.5, 0.25)]
    p, extrapolated = pc.richardson(*margins)
    assert p == pytest.approx(2.0)
    assert extrapolated == pytest.approx(limit)


@pytest.mark.parametrize("margins", [(1.0, 1.0, 0.9), (1.0, 0.9, 1.0), (1.0, 0.9, 0.7)])
def test_richardson_refuses_differences_that_do_not_shrink(margins):
    assert pc.richardson(*margins) == (None, None)


def test_the_summary_reads_each_rung_and_check():
    cases = [{"case_id": "x", "question": "D-0001", "reference_margin_v": 0.0}]
    limit = 5e-4

    def rec(mesh, rtol=1e-6, period=None, cycles=1, value=None):
        h = 40 / mesh
        return {
            "case": 0,
            "mesh": mesh,
            "rtol": rtol,
            "period_s": period,
            "cycles": cycles,
            "status": "OK",
            "plating_margin_v": value if value is not None else limit + 1e-3 * h**2,
        }

    records = [
        rec(20, rtol=1e-5, value=2e-3),
        rec(40),
        rec(80),
        rec(160),
        rec(80, rtol=1e-8, value=limit + 1e-3 * 0.25 + 1e-9),
        rec(80, period=5, value=limit + 1e-3 * 0.25),
        rec(20, rtol=1e-5, cycles=30, value=2e-3),
    ]
    [row] = pc.summarise(cases, records)
    assert row["standard_rung_v"] == 2e-3
    assert row["observed_order"] == pytest.approx(2.0)
    assert row["extrapolated_margin_v"] == pytest.approx(limit)
    assert row["error_v"]["standard_20"] == pytest.approx(2e-3 - limit)
    assert row["rtol_check_v"] == pytest.approx(1e-9)
    assert row["period_check_v"] == pytest.approx(0.0)
    assert row["thirty_cycle_check_v"] == 0.0


def test_run_refuses_anything_but_a_registered_case_list(tmp_path):
    other = tmp_path / "cases.json"
    other.write_text(json.dumps({"schema": "other", "cases": []}))
    with pytest.raises(SystemExit, match="refused"):
        pc.run(other, tmp_path / "out", 1)
