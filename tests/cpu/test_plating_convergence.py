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


def test_a_finest_rung_the_host_killed_is_a_failed_rung_not_a_result():
    cases = [{"case_id": "x", "question": "D-0001", "reference_margin_v": 0.0}]
    ok = {"case": 0, "rtol": 1e-6, "period_s": None, "cycles": 1, "status": "OK"}
    records = [
        {**ok, "mesh": 40, "plating_margin_v": 4e-4},
        {**ok, "mesh": 80, "plating_margin_v": 2e-4},
        {**ok, "mesh": 160, "plating_margin_v": 1e-4},
        {**ok, "mesh": 320, "status": pc.KILLED},
    ]
    [row] = pc.summarise(cases, records)
    assert row["mesh_rungs_v"] == {"40": 4e-4, "80": 2e-4, "160": 1e-4}
    assert row["richardson_meshes"] == [40, 80, 160]


def test_the_committed_study_evidence_matches_its_summary():
    evidence = REPOSITORY / "docs/development/evidence/plating-convergence-01"
    records = [
        json.loads(x)
        for x in (evidence / "records.jsonl").read_text(encoding="utf-8").splitlines()
        if x
    ]
    summary = json.loads((evidence / "summary.json").read_text(encoding="utf-8"))
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    assert len(records) == 61 and all(r["status"] == "OK" for r in records)
    rebuilt = pc.summarise(cases, records)
    for mine, theirs in zip(rebuilt, summary["cases"], strict=True):
        # Same rungs exactly; derived values to floating-point agreement across hosts.
        assert {k: mine[k] for k in ("case_id", "mesh_rungs_v", "standard_rung_v")} == {
            k: theirs[k] for k in ("case_id", "mesh_rungs_v", "standard_rung_v")
        }
        assert mine["observed_order"] == pytest.approx(theirs["observed_order"])
        assert mine["extrapolated_margin_v"] == pytest.approx(
            theirs["extrapolated_margin_v"], rel=1e-9
        )


def test_the_d2_panel_is_forty_stratified_public_cases_on_the_short_ladder():
    path = REPOSITORY / "docs/development/evidence/plating-convergence-02/cases.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    cases = document["cases"]
    assert document["schema"] == pc.CASES_SCHEMA and document["ladder"] == pc.PANEL
    assert len(cases) == sum(n for *_x, n in pc.PANEL_STRATA) == 40
    assert len({c["question"] for c in cases}) == 40  # one per question
    jobs = pc.ladder(cases, pc.PANEL)
    assert len(jobs) == 4 * 40
    assert sorted({j["mesh"] for j in jobs}) == [20, 40, 80, 160]
    assert all(j["rtol"] == (1e-5 if j["mesh"] == 20 else 1e-6) for j in jobs)
    assert all(j["cycles"] == 1 and j["period_s"] is None for j in jobs)


def test_the_d2_final_panel_is_the_validators_spec():
    path = (
        REPOSITORY / "docs/development/evidence/plating-convergence-02/cases-final.json"
    )
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["ladder"] == pc.PANEL
    assert document["counts"] == {
        "feasible_2_4mV": 21,
        "feasible_4_8mV": 10,
        "negative_pair": 4,
    }
    tiers = {}
    for case in document["cases"]:
        tiers.setdefault(case["panel_tier"], []).append(case)
    assert all(
        c["reference_status"] == "FEASIBLE" and 2e-3 < c["reference_margin_v"] <= 4e-3
        for c in tiers["feasible_2_4mV"]
    )
    assert all(4e-3 < c["reference_margin_v"] <= 8e-3 for c in tiers["feasible_4_8mV"])
    assert {(c["question"], c["c1"], c["c2"]) for c in tiers["negative_pair"]} == {
        ("V-T9-S0.06", 1.25, 0.6),
        ("V-T9-S0.06", 1.5, 0.6),
        ("V-T9-S0.06", 1.0, 0.6),
        ("V-T9-S0.22", 1.0, 0.6),
    }
