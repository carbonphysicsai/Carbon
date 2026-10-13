"""Toy LHS plan controls; no Challenge labels or held-out generator."""

import copy
import json
from pathlib import Path

import pytest

from scripts.dev.score_lab import campaign_sweep
from scripts.dev.score_lab.__main__ import main
from scripts.dev.score_lab.core import LabRefused

EXAMPLE = Path(__file__).parents[2] / "scripts/dev/score_lab/physics-example.json"
AXES = Path(__file__).parents[2] / "scripts/dev/score_lab/campaign-axes-example.json"


def _plan():
    return {
        "schema": campaign_sweep.SCHEMA,
        "seed": 17,
        "count": 8,
        "base_config": json.loads(EXAMPLE.read_text(encoding="utf-8")),
        "axes": [
            {
                "path": "problem.space",
                "kind": "choices",
                "values": ["small-grid", "continuous"],
            },
            {"path": "neighbourhood.size", "kind": "linear", "low": 0.02, "high": 0.18},
            {
                "path": "problem.verification_cost_ASSUMPTION",
                "kind": "log",
                "low": 0.01,
                "high": 0.3,
            },
            {
                "path": "population.0.noise",
                "kind": "linear",
                "low": 0.005,
                "high": 0.08,
            },
        ],
    }


def test_lhs_is_deterministic_stratified_and_shard_complete():
    plan = _plan()
    all_rows = list(campaign_sweep.sample(plan))
    assert all_rows == list(campaign_sweep.sample(plan))
    shards = [
        *campaign_sweep.sample(plan, shard=0, shards=2),
        *campaign_sweep.sample(plan, shard=1, shards=2),
    ]
    assert sorted(shards, key=lambda row: row["index"]) == all_rows
    assert {row["config"]["problem"]["space"] for row in all_rows} == {
        "small-grid",
        "continuous",
    }
    low, high = 0.02, 0.18
    cells = {
        int((row["config"]["neighbourhood"]["size"] - low) / (high - low) * 8)
        for row in all_rows
    }
    assert cells == set(range(8))
    assert len({row["config_sha256"] for row in all_rows}) == 8


def test_bad_axes_and_shards_refuse_without_guessing():
    plan = _plan()
    for edit, code in (
        (
            {"path": "not_registered", "kind": "choices", "values": [1]},
            "sweep_axis_path",
        ),
        (
            {"path": "problem.space", "kind": "choices", "values": []},
            "sweep_axis_values",
        ),
        (
            {"path": "neighbourhood.size", "kind": "log", "low": 0, "high": 1},
            "sweep_axis_range",
        ),
    ):
        broken = copy.deepcopy(plan)
        broken["axes"][0] = edit
        with pytest.raises(LabRefused, match=code):
            list(campaign_sweep.sample(broken))
    with pytest.raises(LabRefused, match="sweep_shard"):
        list(campaign_sweep.sample(plan, shard=2, shards=2))


def test_cli_writes_only_the_requested_synthetic_shard(tmp_path):
    output = tmp_path / "plan.json"
    assert (
        main(
            [
                "campaign-plan",
                "--base-config",
                str(EXAMPLE),
                "--axes",
                str(AXES),
                "--count",
                "8",
                "--seed",
                "17",
                "--shard",
                "1",
                "--shards",
                "2",
                "--out",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["scope"] == "SYNTHETIC_DEVELOPMENT"
    assert [row["index"] for row in report["rows"]] == [1, 3, 5, 7]
    assert all(row["config_sha256"] for row in report["rows"])


def test_scored_toy_shards_are_deterministic_and_keep_axis_identity():
    plan = _plan()
    plan["count"] = 2
    plan["base_config"]["questions_per_side"] = 3
    plan["base_config"]["bootstrap"] = 2

    def score_only(predictions, references, metadata):
        assert all(qid.startswith("S-") for qid in predictions)
        assert "value_questions" not in metadata
        return {"score": 1.0, "gate": "PASS"}

    specs = {"toy-score": {"rule": score_only}}
    first = campaign_sweep.evaluate(plan, specs, "toy", shard=0, shards=2)
    second = campaign_sweep.evaluate(plan, specs, "toy", shard=1, shards=2)
    assert first == campaign_sweep.evaluate(plan, specs, "toy", shard=0, shards=2)
    assert [row["index"] for row in first["rows"] + second["rows"]] == [0, 1]
    assert first["scope"] == second["scope"] == "SYNTHETIC_DEVELOPMENT"
    assert first["plan_sha256"] == second["plan_sha256"]
    assert all(row["rows"] for row in first["rows"] + second["rows"])
    assert all(row["axes"] for row in first["rows"] + second["rows"])

    prepared = campaign_sweep.summary(plan, shard=0, shards=2)
    corrupted = copy.deepcopy(prepared)
    corrupted["rows"][0]["config"]["population"][0]["noise"] = 0.8
    with pytest.raises(LabRefused, match="sweep_prepared_replay"):
        campaign_sweep.evaluate_summary(corrupted, specs, "toy")
