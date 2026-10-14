"""Pick-and-freeze toy sensitivity uses complete matched A/B/AB profiles."""

import copy
import json
import math
from pathlib import Path

import pytest

from scripts.dev.score_lab import campaign_sobol
from scripts.dev.score_lab.core import LabRefused

EXAMPLE = Path(__file__).parents[2] / "scripts/dev/score_lab/physics-example.json"


def _plan(count=128):
    config = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    config["questions_per_side"] = 3
    return {
        "schema": campaign_sobol.PLAN_SCHEMA,
        "seed": 19,
        "count": count,
        "base_config": config,
        "axes": [
            {"path": "population.0.noise", "kind": "linear", "low": 0.01, "high": 0.11},
            {
                "path": "population.0.transfer",
                "kind": "linear",
                "low": 0.0,
                "high": 1.0,
            },
        ],
        "switch_index": 0,
        "scope": "neighbourhood_blend",
    }


def _toy_result(prepared):
    def response(config):
        member = config["population"][0]
        return member["noise"] + member["transfer"]

    return {
        "schema": campaign_sobol.RESULT_SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "plan_sha256": prepared["plan_sha256"],
        "plan": prepared["plan"],
        "candidate": "toy-response",
        "candidates_sha256": "toy-digest",
        "shard": prepared["shard"],
        "shards": prepared["shards"],
        "rows": [
            {
                "index": item["index"],
                "A": response(item["A"]),
                "B": response(item["B"]),
                "AB": {name: response(config) for name, config in item["AB"].items()},
            }
            for item in prepared["rows"]
        ],
    }


def test_matched_shards_replay_and_raw_indices_identify_dominant_axis():
    plan = _plan()
    left = campaign_sobol.prepare(plan, shard=0, shards=2)
    right = campaign_sobol.prepare(plan, shard=1, shards=2)
    assert left == campaign_sobol.prepare(plan, shard=0, shards=2)
    assert {row["index"] for row in left["rows"]}.isdisjoint(
        {row["index"] for row in right["rows"]}
    )
    report = campaign_sobol.aggregate([_toy_result(left), _toy_result(right)])
    assert report["matched_pairs"] == 128
    assert report["estimator"] == "SALTELLI_FIRST_ORDER_JANSEN_TOTAL_ORDER_RAW"
    assert report["indices"]["population.0.transfer"]["total_order_raw"] > 0.7
    assert report["indices"]["population.0.noise"]["total_order_raw"] < 0.1
    assert math.isfinite(report["indices"]["population.0.transfer"]["first_order_raw"])


def test_missing_duplicate_unresolved_and_tampered_inputs_fail_closed():
    plan = _plan(count=4)
    left = _toy_result(campaign_sobol.prepare(plan, shard=0, shards=2))
    right = _toy_result(campaign_sobol.prepare(plan, shard=1, shards=2))
    with pytest.raises(LabRefused, match="sobol_incomplete"):
        campaign_sobol.aggregate([left])
    with pytest.raises(LabRefused, match="sobol_shard_identity"):
        campaign_sobol.aggregate([left, left])
    bad = copy.deepcopy(right)
    bad["rows"][0]["AB"].pop("population.0.noise")
    with pytest.raises(LabRefused, match="sobol_hybrids_missing"):
        campaign_sobol.aggregate([left, bad])
    bad = copy.deepcopy(right)
    bad["rows"][0]["A"] = None
    assert (
        campaign_sobol.aggregate([left, bad])["reason"]
        == "unresolved_candidate_profile"
    )
    bad = copy.deepcopy(plan)
    bad["scope"] = "holdout"
    with pytest.raises(LabRefused, match="sobol_plan"):
        campaign_sobol.prepare(bad)
    bad = copy.deepcopy(left)
    bad["plan"]["seed"] += 1
    with pytest.raises(LabRefused, match="sobol_identity"):
        campaign_sobol.aggregate([bad, right])


def test_tampered_prepared_profiles_refuse_before_any_candidate_evaluation():
    prepared = campaign_sobol.prepare(_plan(count=2))
    bad = copy.deepcopy(prepared)
    bad["rows"][0]["A"]["population"][0]["noise"] = 0.999
    with pytest.raises(LabRefused, match="sobol_prepared_replay"):
        campaign_sobol.evaluate(
            bad,
            "toy",
            {"rule": lambda _p, _r, _m: {"score": 1, "gate": "PASS"}},
            candidates_sha256="toy",
        )


def test_candidate_evaluation_consumes_replayed_toy_configs():
    plan = _plan(count=2)
    plan["axes"] = plan["axes"][:1]

    def score(predictions, references, _metadata):
        errors = [
            abs(predictions[qid][aid]["objective"] - ref["objective"])
            for qid, actions in references.items()
            for aid, ref in actions.items()
        ]
        return {"score": -sum(errors) / len(errors), "gate": "PASS"}

    result = campaign_sobol.evaluate(
        campaign_sobol.prepare(plan),
        "toy-score",
        {"rule": score},
        candidates_sha256="toy-digest",
    )
    assert [row["index"] for row in result["rows"]] == [0, 1]
    assert all(set(row["AB"]) == {"population.0.noise"} for row in result["rows"])
    assert result["candidate"] == "toy-score"
    assert result["candidates_sha256"] == "toy-digest"
    assert all(row["A"] is not None and row["B"] is not None for row in result["rows"])
