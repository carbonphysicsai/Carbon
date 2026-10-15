"""Full-grid B3 controls keep missing/failing evidence explicit."""

import copy

import pytest

from scripts.dev.reference_packages.elmer import f13_assemble as assemble
from scripts.dev.reference_packages.elmer import f13_deck as deck
from scripts.dev.reference_packages.elmer import f13_pod_checks as worker


def test_dense_group_is_opt_in_and_covers_the_registered_four_coaxials():
    assert "coax4dense" not in worker.DEFAULT_GROUPS
    jobs = [j for j in worker.plan() if j[0] == "coax4dense"]
    assert {j[1].split("/")[-1] for j in jobs} == set(assemble.COAXIAL)
    assert all(j[3] == {"h_mm": 4.0, "step_hz": 10.0} for j in jobs)


def test_dense_only_layout_preserves_unrun_family_checks(tmp_path):
    (tmp_path / "coax4dense").mkdir()
    result = assemble.assemble(tmp_path, tmp_path / "report.json")
    assert result["checks"]["B3_coaxial_mode_matching_4mm_dense"] == "NOT_RUN"
    assert result["checks"]["B3_coaxial_mode_matching"] == "NOT_RUN"
    assert result["all_pass"] is False


@pytest.fixture
def evidence(monkeypatch):
    rows = [
        {"frequency_hz": f, "tl_db": 6.0, "transmitted_w": 0.25}
        for f in deck.frequencies(10.0)
    ]
    observed = {name: (copy.deepcopy(rows), False) for name in assemble.COAXIAL}
    modes = {
        name: {"n20": copy.deepcopy(rows), "n40": copy.deepcopy(rows)}
        for name in assemble.COAXIAL
    }
    monkeypatch.setattr(assemble, "_rows", lambda path: observed.get(path.name))
    monkeypatch.setattr(assemble, "_cost", lambda path: {"fixture": True})
    return observed, modes


def test_complete_control_set_can_pass_without_changing_historical_checks(
    tmp_path, evidence
):
    _, modes = evidence
    result = assemble.dense_coaxial_report(tmp_path, modes)
    assert result["status"] == "PASS"
    assert result["complete_cases"] == result["expected_cases"] == 4
    assert result["expected_frequencies_per_case"] == 201


@pytest.mark.parametrize("target", ["observed", "n20", "n40"])
def test_missing_frequency_cannot_be_a_dense_pass(tmp_path, evidence, target):
    observed, modes = evidence
    if target == "observed":
        observed["small-coaxial"][0].pop()
    else:
        modes["small-coaxial"][target].pop()
    result = assemble.dense_coaxial_report(tmp_path, modes)
    assert result["status"] == "NOT_RUN" and result["complete_cases"] == 3


def test_observer_failure_and_unconverged_truth_stay_failures(tmp_path, evidence):
    observed, modes = evidence
    rows, _ = observed["small-coaxial"]
    observed["small-coaxial"] = (rows, True)
    assert assemble.dense_coaxial_report(tmp_path, modes)["status"] == "FAIL"
    observed["small-coaxial"] = (rows, False)
    modes["small-coaxial"]["n20"][0]["tl_db"] += 0.06
    result = assemble.dense_coaxial_report(tmp_path, modes)
    assert result["status"] == "FAIL"
    assert (
        result["cases"]["small-coaxial"]["mode_matching_n20_n40_max_resolved_db"] > 0.05
    )


def test_one_failing_curve_cannot_be_compensated_by_other_controls(tmp_path, evidence):
    observed, modes = evidence
    for row in observed["small-coaxial"][0]:
        row["tl_db"] += 0.3
    result = assemble.dense_coaxial_report(tmp_path, modes)
    assert result["status"] == "FAIL"
    assert result["cases"]["small-coaxial"]["pass"] is False
