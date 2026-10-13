"""Independent toy controls for optional prospective score components."""

import math

import pytest

from scripts.dev.score_lab import candidates, synthetic
from scripts.dev.score_lab.components import (
    gaussian_crps,
    with_cheap_margin,
    with_crps,
    with_cvar,
    with_gradient_sign,
)
from scripts.dev.score_lab.core import LabRefused


def _rule(predictions, _references, _metadata):
    return {
        "score": sum(row["a"]["objective"] for row in predictions.values()),
        "gate": "PASS",
    }


def _fixture():
    predictions = {
        "q1": {"a": {"objective": 1.0, "sigma": 0.1}, "b": {"objective": 2.0}},
        "q2": {"a": {"objective": 3.0, "sigma": 0.2}, "b": {"objective": 2.0}},
    }
    references = {
        "q1": {"a": {"status": "FEASIBLE", "objective": 1.0}},
        "q2": {"a": {"status": "FEASIBLE", "objective": 3.0}},
    }
    metadata = {
        "questions": {"q1": {}, "q2": {}},
        "probes": [("q1", "a", "b", 1), ("q2", "a", "b", -1)],
        "cheap_predictions": {
            "q1": {"a": {"objective": 0.0}},
            "q2": {"a": {"objective": 1.0}},
        },
    }
    return predictions, references, metadata


def test_cheap_relative_margin_and_missing_arm():
    predictions, references, metadata = _fixture()
    result = with_cheap_margin(_rule, weight=0.5)(predictions, references, metadata)
    assert result["score"] == 3.5
    worse = {qid: {"a": {"objective": 0.0}} for qid in predictions}
    assert (
        with_cheap_margin(_rule, weight=1)(worse, references, metadata)["score"] == 0.0
    )
    assert (
        with_cheap_margin(_rule, weight=0.5)(
            predictions, references, {**metadata, "cheap_predictions": {}}
        )
        is None
    )
    with pytest.raises(LabRefused, match="component_cheap_margin_weight"):
        with_cheap_margin(_rule, weight=1.1)


def test_crps_is_proper_and_missing_uncertainty_refuses():
    predictions, references, metadata = _fixture()
    assert gaussian_crps(1.0, 0.0, 1.0) == 0.0
    assert gaussian_crps(2.0, 0.0, 1.0) == 1.0
    result = with_crps(_rule, weight=1)(predictions, references, metadata)
    assert 0 < result["score"] < 4
    predictions["q1"]["a"].pop("sigma")
    assert with_crps(_rule, weight=1)(predictions, references, metadata) is None
    with pytest.raises(LabRefused, match="component_crps_input"):
        gaussian_crps(1.0, -0.1, 1.0)


def test_gradient_sign_penalises_only_wrong_probes():
    predictions, references, metadata = _fixture()
    score = with_gradient_sign(_rule, weight=2)(predictions, references, metadata)
    assert score["score"] == 4.0
    predictions["q2"]["b"]["objective"] = 4.0
    score = with_gradient_sign(_rule, weight=2)(predictions, references, metadata)
    assert score["score"] == 3.0


def test_cvar_uses_worst_question_and_preserves_fail_gate():
    predictions, references, metadata = _fixture()
    result = with_cvar(_rule, tail_fraction=0.5)(predictions, references, metadata)
    assert result["score"] == 1.0
    assert result["detail"] == {"tail_questions": 1, "total_questions": 2}

    def gated(predictions, references, metadata):
        outcome = _rule(predictions, references, metadata)
        outcome["gate"] = "FAIL" if "q2" in references else "PASS"
        return outcome

    assert (
        with_cvar(gated, tail_fraction=1)(predictions, references, metadata)["gate"]
        == "FAIL"
    )
    with pytest.raises(LabRefused, match="component_cvar_fraction"):
        with_cvar(_rule, tail_fraction=math.nan)


def test_components_compose_over_score_side_only():
    problem = next(synthetic.profiles())
    panel = synthetic.build(problem, questions_per_side=3)

    def toy_candidate(predictions, references, metadata):
        del references, metadata
        return {
            "score": sum(row["x=0.20"]["objective"] for row in predictions.values()),
            "gate": "PASS",
        }

    spec = {"rule": toy_candidate}
    raw = candidates.rule_from_spec("toy", spec, path_digest="toy", panel=panel)
    wrapped = candidates.rule_from_spec(
        "toy",
        spec,
        path_digest="toy",
        panel=panel,
        component_spec={
            "crps_weight": 0.2,
            "gradient_weight": 0.1,
            "cvar_tail_fraction": 0.5,
            "cheap_margin_weight": 0.3,
        },
    )
    member = panel["members"][0]
    metadata = panel.get("score_metadata", {})
    base = raw(member["score_predictions"], panel["score_questions"], metadata)
    scored = wrapped(member["score_predictions"], panel["score_questions"], metadata)
    assert scored is not None and scored["admissible"]
    assert scored["score"] != base["score"]
    assert wrapped.rule_identity["components"]["cvar_tail_fraction"] == 0.5
    with pytest.raises(LabRefused, match="component_requires_synthetic_panel"):
        candidates.rule_from_spec(
            "toy",
            spec,
            path_digest="toy",
            panel={"scope": "PUBLIC_DEVELOPMENT"},
            component_spec={"crps_weight": 0.2},
        )
    with pytest.raises(LabRefused, match="component_spec"):
        candidates.rule_from_spec(
            "toy",
            spec,
            path_digest="toy",
            panel=panel,
            component_spec={"unregistered": 0.1},
        )
