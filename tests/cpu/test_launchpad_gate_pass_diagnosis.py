"""Toy public-practice summaries for the Launchpad gate diagnosis."""

import json

import pytest

from carbon.battery.scaffold import SCAFFOLD
from scripts.dev.battery.gate_pass_diagnosis import (
    diagnose,
    main,
    shareable_counts,
)


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


def test_shareable_projection_names_only_public_gate_counts_and_coverage():
    trial = _trial("secret-fno-recipe", 0.04, False, {"voltage_floor": 3})
    trial["recipe"] = {"secret": "do-not-share"}
    trial["summary"]["gate_failures"]["secret-gate-name"] = 1
    shared = shareable_counts(diagnose({"experiments": [trial]}))
    assert shared["exported_trials"] == shared["checked_trials"] == 1
    assert shared["gate_failures"]["voltage_floor"] == {"trials": 1, "cases": 3}
    assert shared["gate_failures"]["paired_repeat"] == {"trials": 0, "cases": 0}
    assert shared["unrecognized_gate_names"] == 1
    assert "secret" not in str(shared)
    assert "0.04" not in str(shared)


def test_shareable_coverage_excludes_contradictory_summaries():
    contradictory = _trial("mlp", 0.2, True, {"voltage_floor": 1})
    shared = shareable_counts(diagnose({"experiments": [contradictory]}))
    assert shared["exported_trials"] == 1
    assert shared["checked_trials"] == 0
    assert shared["unverified_trial_summaries"] == 1


def test_counts_only_cli_never_prints_local_recipe_or_error(tmp_path, capsys):
    trial = _trial("fno", 0.04, False, {"capacity_bound": 2})
    trial["recipe"] = {"secret": "private-recipe"}
    export = tmp_path / "miner-private.json"
    export.write_text(json.dumps({"experiments": [trial]}), encoding="utf-8")
    assert main([str(export), "--counts-only"]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["gate_failures"]["capacity_bound"]["cases"] == 2
    assert "private-recipe" not in output
    assert '"fno"' not in output
    assert "0.04" not in output


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
