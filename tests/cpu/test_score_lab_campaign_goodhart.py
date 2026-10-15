"""Goodhart search sees toy score questions; value is measured afterward."""

import copy
import json
import math
import statistics
from pathlib import Path

import pytest

from scripts.dev.score_lab import __main__ as cli
from scripts.dev.score_lab import campaign_goodhart, synthetic
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


def test_cheap_component_has_independent_legacy_score_control():
    config, search = _inputs()
    calls = []

    def observed(predictions, references, metadata):
        calls.append(copy.deepcopy((predictions, references, metadata)))
        return _score_only(predictions, references, metadata)

    evaluator = campaign_goodhart.ToyTraitEvaluator(
        config,
        "toy",
        {"rule": observed},
        candidates_sha256="toy",
        search=search,
        component_spec={"cheap_margin_weight": 0.25},
    )
    parameters = {"noise": 0.05, "transfer": 0.0, "score_path_only": 0.0}
    assert evaluator.score(parameters) is not None
    candidate, cheap = calls
    assert candidate[0] != cheap[0]
    assert cheap[2]["physics"] is None  # no invented baseline physics measurement
    assert all(qid.startswith("S-") for qid in cheap[1])
    for qid, question in evaluator.panel_for(parameters)["score_questions"].items():
        for aid in question["actions"]:
            expected = synthetic._predict(
                "control-bilinear",
                qid,
                float(aid[2:]),
                question["context"],
                config["problem"],
                score_side=True,
            )
            assert cheap[0][qid][aid]["objective"] == expected["objective"]
    assert cheap[2]["neighbours"] != candidate[2]["neighbours"]
    calls.clear()
    assert evaluator.score({**parameters, "noise": 0.09, "transfer": 0.9}) is not None
    assert calls[1] == cheap  # candidate changes cannot alter its comparator metadata

    calls.clear()
    assert evaluator.score(parameters, grain="prefix:2") is not None
    for _predictions, references, metadata in calls:
        assert len(references) == 2
        assert all(len(row["references"]) == 2 for row in metadata["neighbours"])


@pytest.mark.parametrize(
    "extension",
    [
        {"dimension": 2},
        {"objective_kind": "weighted"},
        {"objective_kind": "robust"},
        {"roughness": 0.1},
        {"optimum_location": "boundary"},
        {"optima_count": 1},
        {"constraint_count": 3},
        {"constraint_offset": 0.1},
        {"constraint_coupling": 0.1},
    ],
)
def test_legacy_cheap_control_refuses_nonlegacy_physics_shape(extension):
    config, search = _inputs()
    config["problem"].update(extension)
    evaluator = campaign_goodhart.ToyTraitEvaluator(
        config,
        "toy",
        {"rule": _score_only},
        candidates_sha256="toy",
        search=search,
        component_spec={"cheap_margin_weight": 0.25},
    )
    assert (
        evaluator.score({"noise": 0.05, "transfer": 0.0, "score_path_only": 0.0})
        is None
    )


def test_cheap_cvar_preserves_independent_baseline_and_subset_scope():
    config, search = _inputs()
    calls = []

    def observed(predictions, references, metadata):
        calls.append(copy.deepcopy((predictions, references, metadata)))
        return _score_only(predictions, references, metadata)

    evaluator = campaign_goodhart.ToyTraitEvaluator(
        config,
        "toy",
        {"rule": observed},
        candidates_sha256="toy",
        search=search,
        component_spec={"cheap_margin_weight": 0.25, "cvar_tail_fraction": 0.25},
    )
    parameters = {"noise": 0.05, "transfer": 0.0, "score_path_only": 0.0}
    assert evaluator.score(parameters, grain="prefix:2") is not None
    assert len(calls) == 6  # aggregate + two questions, for candidate and comparator
    baseline = calls[3:]
    for predictions, references, metadata in baseline:
        assert set(predictions) == set(references) == set(metadata["cheap_predictions"])
        assert metadata["physics"] is None
        assert all(len(row["references"]) == 2 for row in metadata["neighbours"])
    calls.clear()
    assert evaluator.score({**parameters, "noise": 0.09}, grain="prefix:2") is not None
    assert calls[3:] == baseline


def test_legacy_cheap_control_never_consumes_value_questions():
    config, _search = _inputs()
    panel = campaign_goodhart.physics.build(config)
    with pytest.raises(LabRefused, match="goodhart_cheap_score_scope"):
        campaign_goodhart._legacy_cheap_score_control(
            config, {"score_questions": panel["value_questions"]}, {}
        )


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
    assert result["calls"] == {"score": search["random_draws"], "value": 0}
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
