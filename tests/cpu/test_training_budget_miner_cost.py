"""TRAINING-BUDGET-01 slice 4: the miner's cost calculator.

Every Challenge with a training budget adapter offers the validator's own
calculator under "train" in its research environment, and a miner can run it
on a strategy file before submitting.
"""

from __future__ import annotations

import json

import pytest

from carbon.challenge_kit import standard
from carbon.reconstruction import capability_registry
from carbon.training_budget import adapter, cost


def test_every_adapted_challenge_offers_the_calculator_under_train():
    for challenge in adapter.registered():
        provision = standard.ENVIRONMENTS[challenge]["train"]
        assert standard.COST_EVIDENCE in provision.evidence, challenge


def test_no_challenge_declares_a_compute_budget_yet():
    """Slice 7 builds the check; no live contract switches on here."""
    for challenge in adapter.registered():
        assert cost.budget(adapter.adapter_for(challenge)) is None


def test_the_miner_runs_the_validators_calculator(tmp_path, capsys):
    pytest.importorskip("jax")
    strategy = tmp_path / "strategy.json"
    strategy.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "challenge_id": capability_registry.BATTERY_CHALLENGE,
                "backbone": "mlp",
                "parameters": {"width": 32, "depth": 2, "steps": 64},
            }
        )
    )
    code = cost.main(
        [
            "--challenge",
            capability_registry.BATTERY_CHALLENGE,
            "--strategy",
            str(strategy),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and out["F0_steps"] == 64 and out["budget"] is None
    assert out["decides"] == "the validator's calculation on its pinned image"


def test_a_refused_recipe_reports_its_code(tmp_path, capsys, monkeypatch):
    def refuse(challenge, strategy, train_cases=None):
        raise cost.CostRefused("cost_unbounded_loop")

    monkeypatch.setattr(cost, "cost", refuse)
    strategy = tmp_path / "strategy.json"
    strategy.write_text("{}")
    code = cost.main(["--challenge", "anything", "--strategy", str(strategy)])
    assert (
        code == 2
        and json.loads(capsys.readouterr().out)["refused"] == "cost_unbounded_loop"
    )
