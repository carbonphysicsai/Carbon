"""The feedback gamer gets only a rounded synthetic score, never buyer value."""

import json
from pathlib import Path

import pytest

from scripts.dev.score_lab import __main__ as cli
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


def test_feedback_receipt_binds_component_settings():
    config, search, disclosure = _inputs()
    results = [
        campaign_feedback.run(
            config,
            "toy",
            {"rule": _score_only},
            candidates_sha256="toy",
            search=search,
            disclosure=disclosure,
            component_spec=component,
        )
        for component in (None, {"cvar_tail_fraction": 0.5})
    ]
    assert results[0]["component_spec"] is None
    assert results[0]["component_spec_sha256"] is None
    assert results[1]["component_spec"] == {"cvar_tail_fraction": 0.5}
    assert results[0]["recipe_sha256"] != results[1]["recipe_sha256"]
    assert results[0]["config_sha256"] == results[1]["config_sha256"]
    assert results[0]["search_sha256"] == results[1]["search_sha256"]
    assert results[0]["disclosure_sha256"] == results[1]["disclosure_sha256"]


def test_feedback_cli_unscored_and_aggregate_receipts_bind_components(
    tmp_path, monkeypatch
):
    config, search, disclosure = _inputs()
    paths = {}
    for name, data in (
        ("config", config),
        ("search", search),
        ("disclosure", disclosure),
    ):
        paths[name] = tmp_path / f"{name}.json"
        paths[name].write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(
        cli.candidates, "load", lambda _path: ({"toy": {}}, "toy-digest")
    )

    def unscored(*_args, **_kwargs):
        raise LabRefused("feedback_probe_unscored")

    monkeypatch.setattr(cli.campaign_feedback, "run", unscored)
    reports = []
    for component in (None, {"cvar_tail_fraction": 0.5}):
        out = tmp_path / "result.json"
        argv = [
            "campaign-feedback",
            "--config",
            str(paths["config"]),
            "--search",
            str(paths["search"]),
            "--disclosure",
            str(paths["disclosure"]),
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
