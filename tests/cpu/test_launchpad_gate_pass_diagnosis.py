"""Toy public-practice summaries for the Launchpad gate diagnosis."""

import pytest

from carbon.battery.scaffold import SCAFFOLD
from scripts.dev.miner_launchpad.gate_pass_diagnosis import diagnose


def _trial(backbone, score, eligible, failures, *, recipe=None):
    return {
        "id": "must-never-appear-in-report",
        "backbone": backbone,
        "recipe": recipe,
        "summary": {
            "score": score,
            "eligible": eligible,
            "gate_failures": failures,
            "n_scored": 199 if failures else 200,
        },
    }


def test_lower_error_does_not_erase_mandatory_gate_failure():
    export = {
        "experiments": [
            _trial("mlp", 0.2, True, {}, recipe=SCAFFOLD),
            _trial("fno", 0.1, False, {"voltage_ceiling": 2, "capacity_bound": 1}),
            _trial("fno", 0.15, False, {"voltage_ceiling": 1}),
        ]
    }
    report = diagnose(export)
    assert report["exported_trials"] == 3
    assert report["counts"]["eligible_trials"] == 1
    assert report["gate_failures"] == {
        "capacity_bound": {"trials": 1, "cases": 1},
        "voltage_ceiling": {"trials": 2, "cases": 3},
    }
    assert report["published_default_mlp"]["eligible_trials"] == 1
    assert report["lowest_descriptive_error_by_backbone"]["fno"] == 0.1
    assert "fno" not in report["lowest_eligible_error_by_backbone"]
    assert "must-never-appear" not in str(report)


def test_absent_and_conflicting_evidence_does_not_become_a_pass():
    export = {
        "experiments": [
            {"summary": {"eligible": True}},
            _trial("mlp", 0.2, True, {"voltage_floor": 1}, recipe=SCAFFOLD),
            _trial("mlp", 0.3, False, {}, recipe={**SCAFFOLD, "parameters": {}}),
        ]
    }
    report = diagnose(export)
    assert report["counts"]["incomplete_summaries"] == 1
    assert report["counts"]["contradictory_summaries"] == 1
    assert report["counts"]["eligible_trials"] == 0
    assert report["counts"]["ineligible_without_reported_gate_failure"] == 1
    assert report["published_default_mlp"]["checked_trials"] == 1
    assert report["published_default_mlp"]["eligible_trials"] == 0


def test_modified_mlp_is_not_the_published_default():
    modified = {**SCAFFOLD, "backend": "pytorch"}
    report = diagnose({"experiments": [_trial("mlp", 0.2, True, {}, recipe=modified)]})
    assert report["counts"]["eligible_trials"] == 1
    assert report["published_default_mlp"]["checked_trials"] == 0


def test_zero_scored_cases_cannot_be_reported_as_gate_passage():
    trial = _trial("mlp", None, True, {}, recipe=SCAFFOLD)
    trial["summary"]["n_scored"] = 0
    report = diagnose({"experiments": [trial]})
    assert report["counts"]["contradictory_summaries"] == 1
    assert report["counts"]["eligible_trials"] == 0
    assert report["published_default_mlp"]["eligible_trials"] == 0


@pytest.mark.parametrize(
    "export",
    [None, {}, {"experiments": None}, {"experiments": {}}],
)
def test_requires_full_experiment_export(export):
    with pytest.raises(ValueError, match="experiments list"):
        diagnose(export)
