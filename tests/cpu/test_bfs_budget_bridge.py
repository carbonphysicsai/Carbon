"""Synthetic replay verifies existing BFS proposal through #1047 hard caps."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from carbon.design_search import bfs_budget
from carbon.design_search import budget_registration as br
from carbon.design_search import equal_budget as eb

ROOT = Path(__file__).resolve().parents[2]


def proposal():
    return json.loads(
        (
            ROOT
            / "docs/development/challenge_pipeline/benchmark-readiness/bfs/equal-budget-proposal.json"
        ).read_text()
    )


def test_bfs_extends_not_mutates_registration():
    raw = proposal()
    assert (
        bfs_budget.validate(raw).cap(bfs_budget.FAMILY, "base").solver_evaluations == 8
    )
    with pytest.raises(br.BudgetRegistrationError):
        br.validate(raw)
    bad = copy.deepcopy(raw)
    bad["challenge_budgets"][bfs_budget.FAMILY]["tiers"]["half"][
        "solver_evaluations"
    ] = 5
    bad = br.seal({k: v for k, v in bad.items() if k != "registration_digest"})
    with pytest.raises(br.BudgetRegistrationError):
        bfs_budget.validate(bad)


def test_complete_public_panel_replays_shared_caps():
    spec = importlib.util.spec_from_file_location(
        "budget_toy", ROOT / "tests/cpu/test_design_search_equal_budget.py"
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    panel = fixture.panel(challenge=bfs_budget.FAMILY)
    panel.pop("panel_digest")
    raw = proposal()
    caps = bfs_budget.validate(raw)
    panel["budgets"] = [
        caps.cap(bfs_budget.FAMILY, tier).time_compute for tier in br.TIERS
    ]
    panel["registrations"]["cost_plan"] = bfs_budget.ID
    report = eb.compare(
        eb.seal(panel),
        bootstrap_replicates=100,
        confidence=0.9,
        seed=1,
        registration=raw,
    )
    assert report["budget_registration_id"] == bfs_budget.ID
    assert report["budget_registration_digest"] == raw["registration_digest"]
    assert report["status"] == "OK"
