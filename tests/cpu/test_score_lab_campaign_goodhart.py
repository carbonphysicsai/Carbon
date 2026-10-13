"""Goodhart search sees toy score questions; value is measured afterward."""

import copy
import json
import math
import statistics
from pathlib import Path

import pytest

from scripts.dev.score_lab import campaign_goodhart
from scripts.dev.score_lab.core import LabRefused

EXAMPLE = Path(__file__).parents[2] / "scripts/dev/score_lab/physics-example.json"


def _inputs():
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    config["questions_per_side"] = 3
    search = {
        "seed": 42,
        "random_draws": 6,
        "hill_epochs": 1,
        "base_member_id": "physics-understanding-0",
        "value_scope": "in_range",
        "parameters": {
            "noise": [0.001, 0.1, 0.02],
            "transfer": [0.0, 1.0, 0.25],
            "score_path_only": [0, 1, 1],
        },
    }
    return config, search


def _score_only(predictions, references, metadata):
    assert set(predictions) == set(references)
    assert all(qid.startswith("S-") for qid in references)
    assert "value_questions" not in metadata and "value_losses" not in metadata
    error = statistics.fmean(
        abs(predictions[qid][aid]["objective"] - ref["objective"])
        for qid, actions in references.items()
        for aid, ref in actions.items()
    )
    return {"score": -error, "gate": "PASS"}


def test_score_search_and_value_oracle_are_deterministic_and_separate():
    config, search = _inputs()
    args = (config, "toy-accuracy", {"rule": _score_only})
    result = campaign_goodhart.run(*args, candidates_sha256="toy", search=search)
    assert result == campaign_goodhart.run(
        *args, candidates_sha256="toy", search=search
    )
    assert result["status"] == "MEASURED_SYNTHETIC_DEVELOPMENT"
    assert result["oracle_kind"] == "RANDOM_PLUS_COORDINATE_HILLCLIMB_ON_ANALYTIC_TOY"
    assert math.isfinite(result["sampled_goodhart_gap"])
    assert result["calls"]["score"] > 0 and result["calls"]["value"] > 0
    assert result["score_best_parameters"]["score_path_only"] in (0.0, 1.0)


def test_bad_search_grammar_and_all_gated_scores_refuse():
    config, search = _inputs()
    bad = copy.deepcopy(search)
    bad["parameters"]["score_path_only"] = [0, 1, 0.5]
    with pytest.raises(LabRefused, match="goodhart_trait_bounds"):
        campaign_goodhart.run(
            config, "toy", {"rule": _score_only}, candidates_sha256="toy", search=bad
        )
    bad = copy.deepcopy(search)
    bad["parameters"]["transfer"] = [0, 1.1, 0.25]
    with pytest.raises(LabRefused, match="goodhart_trait_bounds"):
        campaign_goodhart.run(
            config, "toy", {"rule": _score_only}, candidates_sha256="toy", search=bad
        )

    def never_eligible(predictions, references, metadata):
        return {"score": 1.0, "gate": "FAIL"}

    result = campaign_goodhart.run(
        config,
        "gated",
        {"rule": never_eligible},
        candidates_sha256="toy",
        search=search,
    )
    assert result == {
        "status": "INSUFFICIENT_EVIDENCE",
        "reason": "all_score_proposals_unscored",
    }
