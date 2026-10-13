"""The feedback gamer gets only a rounded synthetic score, never buyer value."""

import json
from pathlib import Path

import pytest

from scripts.dev.score_lab import campaign_feedback
from scripts.dev.score_lab.core import LabRefused

EXAMPLE = Path(__file__).parents[2] / "scripts/dev/score_lab/physics-example.json"


def _inputs():
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    config["questions_per_side"] = 3
    search = {
        "seed": 7,
        "random_draws": 2,
        "hill_epochs": 1,
        "base_member_id": "physics-understanding-0",
        "value_scope": "in_range",
        "parameters": {
            "noise": [0.05, 0.1, 0.01],
            "score_path_only": [0, 1, 1],
        },
    }
    disclosure = {
        "initial": {"noise": 0.05, "score_path_only": 0},
        "grains": ["aggregate", "prefix:2"],
        "roundings": [3],
        "probe_allowances": [4],
        "epochs": 1,
    }
    return config, search, disclosure


def _score_only(predictions, references, metadata):
    assert set(predictions) == set(references)
    assert all(qid.startswith("S-") for qid in references)
    assert "value_questions" not in metadata and "value_losses" not in metadata
    error = sum(
        abs(predictions[qid][aid]["objective"] - ref["objective"])
        for qid, actions in references.items()
        for aid, ref in actions.items()
    ) / sum(len(actions) for actions in references.values())
    return {"score": -error, "gate": "PASS"}


def test_feedback_search_runs_on_disjoint_analytic_toy_and_is_replayable():
    config, search, disclosure = _inputs()
    seen = []

    def inspected(predictions, references, metadata):
        seen.append(len(references))
        return _score_only(predictions, references, metadata)

    kwargs = {
        "candidates_sha256": "toy-candidate-digest",
        "search": search,
        "disclosure": disclosure,
    }
    result = campaign_feedback.run(config, "toy", {"rule": inspected}, **kwargs)
    assert result == campaign_feedback.run(config, "toy", {"rule": inspected}, **kwargs)
    assert {2, 3} <= set(seen)
    assert result["status"] == "MEASURED_SYNTHETIC_DEVELOPMENT"
    assert len(result["rows"]) == 2
    assert all(row["calls"] == 5 for row in result["rows"])
    assert all(
        row["final_parameters"]["score_path_only"] == 1 for row in result["rows"]
    )
    assert all(row["score_gain"] > 0 for row in result["rows"])
    # The score-path exploit improves disclosed fit while buyer value stays put.
    assert all(row["value_gain"] == 0 for row in result["rows"])
    assert result["calls"] == {"score": 10, "value": 4}


def test_missing_grain_bad_initial_and_gated_probe_refuse():
    config, search, disclosure = _inputs()
    kwargs = {
        "candidates_sha256": "toy",
        "search": search,
        "disclosure": disclosure,
    }
    bad = {**disclosure, "grains": ["secret-value"]}
    with pytest.raises(LabRefused, match="feedback_disclosure_grain"):
        campaign_feedback.run(
            config, "toy", {"rule": _score_only}, **{**kwargs, "disclosure": bad}
        )
    bad = {**disclosure, "initial": {"noise": 0.05}}
    with pytest.raises(LabRefused, match="feedback_initial_traits"):
        campaign_feedback.run(
            config, "toy", {"rule": _score_only}, **{**kwargs, "disclosure": bad}
        )
    bad = {**disclosure, "grains": ["prefix:4"]}
    with pytest.raises(LabRefused, match="feedback_grain"):
        campaign_feedback.run(
            config, "toy", {"rule": _score_only}, **{**kwargs, "disclosure": bad}
        )
    with pytest.raises(LabRefused, match="feedback_probe_unscored"):
        campaign_feedback.run(
            config,
            "toy",
            {"rule": lambda _p, _r, _m: {"score": 1.0, "gate": "FAIL"}},
            **kwargs,
        )
