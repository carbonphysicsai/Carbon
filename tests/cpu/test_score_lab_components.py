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
from scripts.dev.score_lab.core import LabRefused, analyze


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


def test_cvar_preserves_full_panel_floor_even_when_tail_is_clean():
    predictions, references, metadata = _fixture()

    def floored(predictions, references, metadata):
        return {
            **_rule(predictions, references, metadata),
            "tier": 2 if len(references) > 1 else int("q2" in references),
        }

    result = with_cvar(floored, tail_fraction=0.5)(predictions, references, metadata)
    assert result["score"] == 1.0  # q1 alone is the clean worst-score tail
    assert result["tier"] == 2  # full-panel FLOOR still governs admission


def test_floor_cvar_candidate_cannot_win_primary_by_a_higher_score():
    panel = synthetic.build(next(synthetic.profiles()), questions_per_side=3)
    panel["members"] = [m for m in panel["members"] if m["kind"] == "MODEL"][:2]
    breached, clean = panel["members"]
    breached["score_metadata"] = {"physics": {"breach": True}}
    clean["score_metadata"] = {"physics": {"breach": False}}

    def floored(_predictions, _references, metadata):
        breach = metadata["physics"]["breach"]
        return {"score": 100.0 if breach else 1.0, "gate": "PASS", "tier": int(breach)}

    raw = candidates.rule_from_spec(
        "toy", {"rule": floored}, path_digest="fixture", panel=panel
    )
    wrapped = candidates.rule_from_spec(
        "toy",
        {"rule": floored},
        path_digest="fixture",
        panel=panel,
        component_spec={"cvar_tail_fraction": 0.5},
    )
    for rule in (raw, wrapped):
        result = analyze(panel, rule, bootstrap=3)
        assert result["physics_tiers"][breached["id"]] == 1
        assert (
            result["ranked_scores"][breached["id"]]
            < result["ranked_scores"][clean["id"]]
        )
        assert result["top1_member"] == clean["id"]


@pytest.mark.parametrize("tier", [None, True, -1, 0.5])
def test_cvar_refuses_malformed_floor_tier(tier):
    predictions, references, metadata = _fixture()

    def malformed(predictions, references, metadata):
        return {**_rule(predictions, references, metadata), "tier": tier}

    with pytest.raises(LabRefused, match="component_tier_malformed"):
        with_cvar(malformed, tail_fraction=0.5)(predictions, references, metadata)


@pytest.mark.parametrize("unscored_count", [1, 2])
def test_cvar_refuses_unscored_full_panel_or_question(unscored_count):
    predictions, references, metadata = _fixture()

    def undecomposable(predictions, references, metadata):
        if len(references) == unscored_count:
            return None
        return _rule(predictions, references, metadata)

    assert (
        with_cvar(undecomposable, tail_fraction=0.5)(predictions, references, metadata)
        is None
    )


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
