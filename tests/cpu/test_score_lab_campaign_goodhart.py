"""Goodhart search sees toy score questions; value is measured afterward."""

import copy
import json
import math
import statistics
from pathlib import Path

import pytest

from scripts.dev.score_lab import __main__ as cli
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
    assert result["score_best_parameters"]["score_path_only"] == 1.0
    assert result["value_best_parameters"]["score_path_only"] == 0.0
    assert result["sampled_goodhart_gap"] > 0


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
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["reason"] == "all_score_proposals_unscored"
    assert result["component_spec"] is None
    assert result["component_spec_sha256"] is None


@pytest.mark.parametrize("unscored", [False, True])
def test_goodhart_receipt_identity_changes_when_only_components_change(unscored):
    config, search = _inputs()

    def rule(predictions, references, metadata):
        result = _score_only(predictions, references, metadata)
        if unscored:
            result["gate"] = "FAIL"
        return result

    results = [
        campaign_goodhart.run(
            config,
            "toy",
            {"rule": rule},
            candidates_sha256="toy",
            search=search,
            component_spec=component,
        )
        for component in (
            None,
            {"cvar_tail_fraction": 0.5},
            {"cvar_tail_fraction": 1.0},
        )
    ]
    assert len({result["recipe_sha256"] for result in results}) == 3
    assert len({result["component_spec_sha256"] for result in results}) == 3
    assert len({result["config_sha256"] for result in results}) == 1
    assert len({result["search_sha256"] for result in results}) == 1
    assert results[0]["component_spec"] is None
    assert results[1]["component_spec"] == {"cvar_tail_fraction": 0.5}


def test_cvar_goodhart_requires_explicit_tail_fraction():
    config, search = _inputs()
    search["value_scope"] = "robust_cvar"
    with pytest.raises(LabRefused, match="goodhart_cvar_tail_fraction"):
        campaign_goodhart.validate(config, search)
    search["tail_fraction"] = 0.5  # illustrative toy fraction, never a score value
    campaign_goodhart.validate(config, search)
    result = campaign_goodhart.run(
        config, "toy", {"rule": _score_only}, candidates_sha256="toy", search=search
    )
    assert result["status"] == "MEASURED_SYNTHETIC_DEVELOPMENT"
    search["tail_fraction"] = 0
    with pytest.raises(LabRefused, match="goodhart_cvar_tail_fraction"):
        campaign_goodhart.validate(config, search)


def test_goodhart_cli_aggregate_and_unscored_receipts_bind_components(
    tmp_path, monkeypatch
):
    config, search = _inputs()
    paths = {}
    for name, data in (("config", config), ("search", search)):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(data), encoding="utf-8")

    def gated(_predictions, _references, _metadata):
        return {"score": 1.0, "gate": "FAIL"}

    monkeypatch.setattr(
        cli.candidates, "load", lambda _p: ({"toy": {"rule": gated}}, "toy-digest")
    )
    reports = []
    for component in (None, {"cvar_tail_fraction": 0.5}):
        out = tmp_path / "result.json"
        argv = [
            "campaign-goodhart",
            "--config",
            str(paths["config"]),
            "--search",
            str(paths["search"]),
            "--candidates",
            str(tmp_path / "unused.py"),
            "--out",
            str(out),
        ]
        if component is not None:
            path = tmp_path / "components.json"
            path.write_text(json.dumps(component), encoding="utf-8")
            argv.extend(["--components", str(path)])
        assert cli.main(argv) == 0
        reports.append(json.loads(out.read_text(encoding="utf-8")))
    for report, component in zip(
        reports, (None, {"cvar_tail_fraction": 0.5}), strict=True
    ):
        assert report["component_spec"] == component
        assert report["results"]["toy"]["component_spec"] == component
        assert report["results"]["toy"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert reports[0]["recipe_sha256"] != reports[1]["recipe_sha256"]
    assert (
        reports[0]["results"]["toy"]["recipe_sha256"]
        != reports[1]["results"]["toy"]["recipe_sha256"]
    )
