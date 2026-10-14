"""Combined-score controls: absence is not a score and value stays downstream."""

import copy
import json
from pathlib import Path

import pytest

from scripts.dev.score_lab import campaign_combined as cc
from scripts.dev.score_lab import core, physics

ROOT = Path(__file__).resolve().parents[2]
PLAN = (
    ROOT / "Business/research/score-lab-campaign-01/combined-matrix/REGISTRATION.json"
)


@pytest.fixture
def plan():
    obj = json.loads(PLAN.read_text(encoding="utf-8"))
    obj["profiles"] = [obj["profiles"][0]]
    cfg = obj["profiles"][0]["config"]
    cfg["bootstrap"] = 2
    cfg["questions_per_side"] = 3
    obj["profiles"][0]["config_sha256"] = core.canonical_sha(cfg)
    return obj


def toy_score(predictions, references, metadata):
    assert all(q.startswith("S-") for q in references)
    assert not any(
        k in metadata
        for k in ("value_losses", "value_questions", "exact_oracle_losses")
    )
    assert all(
        q.startswith("N-S-") for nb in metadata["neighbours"] for q in nb["references"]
    )
    score = -sum(
        abs(predictions[q][a]["objective"] - ref["objective"])
        for q, actions in references.items()
        for a, ref in actions.items()
    )
    return {"score": score, "gate": "PASS"}


def test_catalogue_is_complete_and_prospective_literals(plan):
    rows = cc.catalogue(plan["components"])
    assert len(rows) == 32 and rows[0] is None
    assert len({frozenset(row or {}) for row in rows}) == 32
    for row in rows[1:]:
        assert all(value == plan["components"][key] for key, value in row.items())
    ablations = {row["id"]: row for row in plan["ablations"]}
    assert ablations["TOY-ABLATION/A+Q/NO-GATE"]["weights"] == {"a": 0.5, "q": 0.5}
    assert ablations["TOY-ABLATION/Q/G-FEAS"]["gates"] == [
        ["feasibility", 0.05, "exceeds"]
    ]
    cc.validate_plan(plan)


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda p: p.update(scope="PUBLIC_DEVELOPMENT"), "combined_plan_scope"),
        (
            lambda p: p["profiles"][0]["config"].update(bootstrap=10),
            "combined_config_digest",
        ),
        (
            lambda p: p["components"].pop("honest_abstention"),
            "combined_component_catalogue",
        ),
        (lambda p: p.update(physics_indices=[0]), "combined_physics_catalogue"),
        (lambda p: p["caps"].update(cell_cpu_seconds=True), "combined_caps"),
        (lambda p: p["caps"].update(total_cpu_seconds=1), "combined_unaffordable_cell"),
        (
            lambda p: p.update(candidate_ids=["same"] * 16),
            "combined_candidate_catalogue",
        ),
    ],
)
def test_bad_registration_refuses_before_run(plan, mutation, code):
    mutation(plan)
    with pytest.raises(core.LabRefused, match=code):
        cc.validate_plan(plan)


def test_freeze_uses_only_scoring_and_detects_mutation():
    predictions = {"S-0": {"x": 1}}
    scoring = {
        "score_questions": {"S-0": {"x": 2}},
        "members": [
            {"id": "a", "score_predictions": predictions},
            {"id": "b", "score_predictions": copy.deepcopy(predictions)},
        ],
    }
    calls = []

    def score(p, r, m):
        calls.append((p, r, m))
        return {"score": 7, "admissible": True, "tier": 0}

    score.rule_identity = {"toy": True}
    replay, by_member, count = cc.freeze_scores(scoring, score)
    assert count == len(calls) == 1
    assert by_member["a"] == by_member["b"]
    assert (
        replay(predictions, scoring["score_questions"], {"score_row": None})["score"]
        == 7
    )
    predictions["S-0"]["x"] = 999
    with pytest.raises(core.LabRefused, match="combined_score_input_changed"):
        replay(predictions, scoring["score_questions"], {"score_row": None})


def test_combined_no_components_matches_existing_direct_evaluation(plan):
    specs = {name: {"rule": toy_score} for name in plan["candidate_ids"]}
    result = cc.evaluate_cell(plan, 0, 0, specs, "fixture")
    cfg = plan["profiles"][0]["config"]
    panel = physics.build(cfg)
    from scripts.dev.score_lab import candidates

    rule = candidates.rule_from_spec(
        plan["candidate_ids"][0],
        specs[plan["candidate_ids"][0]],
        path_digest="fixture",
        panel={"scope": panel["scope"]},
    )
    view = physics.value_view(panel, "in_range")
    view["score_metadata"] = {
        "knobs": {
            "physics": cfg["physics_sweep"][0],
            "neighbourhood_weight": cfg["neighbourhood"]["score_weight"],
        }
    }
    direct = core.analyze(view, rule, bootstrap=cfg["bootstrap"])
    combined = result["rows"][0]["outcomes"]["in_range"]
    for key in direct:
        assert combined[key] == direct[key]
    assert len(result["rows"]) == 64
    assert result["solver_calls"] == result["model_inference_calls"] == 0
    assert result["scorer_evaluations"] == 16 * 4 * 8


def test_missing_comparator_physics_is_unscored_in_all_nonoff_modes(plan):
    specs = {name: {"rule": toy_score} for name in plan["candidate_ids"]}
    index = next(
        i
        for i, row in enumerate(cc.catalogue(plan["components"]))
        if row and set(row) == {"cheap_margin_weight"}
    )
    result = cc.evaluate_cell(plan, 0, index, specs, "fixture")
    for row in result["rows"]:
        for outcome in row["outcomes"].values():
            if row["physics_index"]:
                assert outcome == {
                    "status": "INSUFFICIENT_EVIDENCE",
                    "reason": "missing_cheap_physics_measurements",
                }
                assert all(score is None for score in row["scores"].values())
            else:
                assert outcome["status"] == "MEASURED_DEVELOPMENT"
    assert result["scorer_evaluations"] == 16 * 8


def test_complete_cell_must_be_affordable_before_dispatch(plan):
    caps = plan["caps"]
    assert cc.cell_affordable(
        caps, caps["total_cpu_seconds"] - caps["cell_cpu_seconds"], 0
    )
    assert not cc.cell_affordable(
        caps, caps["total_cpu_seconds"] - caps["cell_cpu_seconds"] + 0.001, 0
    )
    assert not cc.cell_affordable(
        caps, 0, caps["total_wall_seconds"] - caps["cell_wall_seconds"] + 0.001
    )


def test_sources_are_verified_before_candidate_import(plan, tmp_path):
    path = tmp_path / "source.json"
    path.write_bytes(b"{}\n")
    candidate = tmp_path / "candidate.py"
    candidate.write_bytes(b'raise AssertionError("must not import")\n')
    plan["sources"] = [{"path": "source.json", "sha256": cc.source_sha(path)}]
    plan["controls"] = {"audit_path": "source.json", "stress_path": "source.json"}
    plan["candidates_sha256"] = cc.file_sha(candidate)
    cc.verify_sources(plan, tmp_path, candidate)
    path.write_bytes(b'{"changed":true}\n')
    with pytest.raises(core.LabRefused, match="combined_source_digest"):
        cc.verify_sources(plan, tmp_path, candidate)
    plan["sources"][0]["path"] = "../outside.json"
    with pytest.raises(core.LabRefused, match="combined_source_path"):
        cc.verify_sources(plan, tmp_path, candidate)
    plan["candidates_sha256"] = "0" * 64
    with pytest.raises(core.LabRefused, match="combined_candidate_digest"):
        cc.load_specs(plan, candidate)


def test_pair_with_missing_score_or_different_mask_never_gets_zero_effect():
    def cell(index, outcome):
        return {
            "profile_index": 0,
            "component_index": index,
            "rows": [
                {
                    "candidate": "a",
                    "physics_index": 0,
                    "outcomes": {"in_range": outcome},
                }
            ],
        }

    base = {
        "status": "MEASURED_DEVELOPMENT",
        "top1_value": 1,
        "common_mask_sha256": "a",
    }
    missing = {"status": "INSUFFICIENT_EVIDENCE", "reason": "missing_input"}
    other = {**base, "top1_value": 2, "common_mask_sha256": "b"}
    report = cc.summarize([cell(0, base), cell(1, missing), cell(2, other)])
    assert report["status_counts"] == {"MEASURED_DEVELOPMENT": 2, "missing_input": 1}
    assert all(
        row["delta_selected_value"] is None
        for row in report["paired_component_effects"]
    )


@pytest.mark.parametrize(
    "raw,expected",
    [(None, None), ({"score": None}, None), ("bad", "candidate_result_malformed")],
)
def test_component_unavailable_is_distinct_from_malformed(plan, raw, expected):
    from scripts.dev.score_lab import candidates

    panel = physics.build(plan["profiles"][0]["config"])
    rule = candidates.rule_from_spec(
        "toy",
        {"rule": lambda *_: raw},
        path_digest="fixture",
        panel={"scope": panel["scope"]},
    )
    member = panel["members"][0]
    args = (
        member["score_predictions"],
        panel["score_questions"],
        member["score_metadata"],
    )
    if expected:
        with pytest.raises(core.LabRefused, match=expected):
            rule(*args)
    else:
        assert rule(*args) is None
