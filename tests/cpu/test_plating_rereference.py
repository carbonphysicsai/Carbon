"""PLATING-REREFERENCE-01 (D3): the set, the ladder and the labels (no PyBaMM)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev.battery import plating_convergence as pc
from scripts.dev.battery import plating_rereference as rr

REPOSITORY = Path(__file__).resolve().parents[2]
CASES = REPOSITORY / "docs/development/evidence/plating-rereference-01/cases.json"


def test_the_set_is_every_public_case_in_the_window():
    document = json.loads(CASES.read_text(encoding="utf-8"))
    cases = document["cases"]
    assert document["counts"] == {"pdd": 611, "ev4": 58} and len(cases) == 669
    assert all(rr.LOW_V < c["reference_margin_v"] < rr.HIGH_V for c in cases)
    assert {c["source"] for c in cases} == {"pdd", "ev4"}  # no sealed source
    checked = [c for c in cases if c.get("convergence_check")]
    assert len(checked) == document["convergence_check_cases"] == 67


def test_the_re_reference_ladder_is_mesh_160_plus_the_subsample():
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    jobs = pc.ladder(cases, pc.RE_REFERENCE)
    assert sum(j["mesh"] == 160 for j in jobs) == 669
    assert sum(j["mesh"] in (40, 80) for j in jobs) == 2 * 67
    assert all(j["rtol"] == 1e-6 and j["cycles"] == 1 for j in jobs)


@pytest.mark.parametrize(
    ("m20", "m160", "old", "new"),
    [
        (3.0e-3, 0.9e-3, "FEASIBLE", "FEASIBLE"),
        (3.0e-3, 0.3e-3, "FEASIBLE", "UNRESOLVED"),
        (3.0e-3, -0.1e-3, "FEASIBLE", "INFEASIBLE"),
        (-1.0e-3, -1.9e-3, "UNRESOLVED", "INFEASIBLE"),
        (1.5e-3, 0.6e-3, "UNRESOLVED", "FEASIBLE"),
        (20e-3, 18e-3, "FEASIBLE", None),  # not claimed beyond 15 mV
    ],
)
def test_old_and_new_labels_follow_the_validators_parameters(m20, m160, old, new):
    assert rr.old_label(m20) == old
    assert rr.new_label(m20, m160) == new


def test_label_reports_transitions_versions_and_stop_reasons(tmp_path):
    cases = {
        "schema": pc.CASES_SCHEMA,
        "ladder": pc.RE_REFERENCE,
        "cases": [
            {"case_id": "a", "source": "pdd", "question": "D-1", "c1": 1, "c2": 1,
             "t_amb_c": 9.0, "soc0": 0.06, "reference_margin_v": 3.0e-3,
             "convergence_check": True},
            {"case_id": "b", "source": "pdd", "question": "D-2", "c1": 1, "c2": 1,
             "t_amb_c": 9.0, "soc0": 0.06, "reference_margin_v": -1.0e-3},
        ],
    }  # fmt: skip
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases))
    records = [
        {"case": 0, "mesh": 40, "status": "OK", "plating_margin_v": 1.8e-3},
        {"case": 0, "mesh": 80, "status": "OK", "plating_margin_v": 1.2e-3},
        {"case": 0, "mesh": 160, "status": "OK", "plating_margin_v": 0.7e-3},
        {"case": 1, "mesh": 160, "status": "OK", "plating_margin_v": -1.5e-3},
    ]
    recs = tmp_path / "records.jsonl"
    recs.write_text("".join(json.dumps(r) + "\n" for r in records))
    report = rr.label(path, recs)
    assert report["transitions"] == {
        "FEASIBLE->FEASIBLE": 1,
        "UNRESOLVED->INFEASIBLE": 1,
    }
    assert report["feasible_to_infeasible"] == 0
    assert all(r["plating_reference"]["version"] == rr.VERSION for r in report["rows"])
    # 0.7 mV is FEASIBLE but below the 0.73 mV floor, and m80 - m160 = 0.5 mV
    # exceeds the 0.359 mV residual: both are stop-before-sealing reasons.
    assert report["feasible_below_floor"] == ["a"]
    assert report["convergence_check"]["residual_exceeded"] == ["a"]
    assert len(report["stop_before_sealing"]) >= 2
