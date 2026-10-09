"""TRAINING-BUDGET-02: the cost calculator prices battery's development levels
as the development rebuild trains them.

Claims tested:
- Level 0 is unchanged: `level=0` is the calculator as before;
- honest recipes at Levels 1, 2 and 3 price (F4 is a number), none refused as
  an unknown parameter;
- Level 2 SpecMuon's per-step SVD and extra forward pass are inside the
  compiled step: its step costs more than base Muon's;
- a Level 2 pool selection prices at its drawn size: N cases train, N bound
  the update;
- a Level 3 polish prices at its line search's recorded worst case, plus a
  dense routine's inverse-Hessian update;
- Level 4 is refused typed until its graph FLOPs are wired (slice 5);
- a development compile checks the declared compute budget at its own level,
  and a recipe over it is refused `budget.over_compute_budget`.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("jax")

from carbon.agent_campaign.attack.adapters import battery_level1 as atk
from carbon.battery import development_rebuild, level3_numerics, level4_worker, pools
from carbon.reconstruction import challenge_contracts
from carbon.reconstruction import development_variants as dv
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE
from carbon.training_budget.cost import CostRefused, cost

SMALL = {"width": 16, "depth": 1, "steps": 32}
(POOL,) = pools.registered()


def strategy(**parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY_CHALLENGE,
        "backbone": "mlp",
        "parameters": {**SMALL, **parameters},
    }


def priced(value, level):
    report = cost(BATTERY_CHALLENGE, value, level=level)
    assert type(report["F4_flops"]) is float, report["F4_flops"]
    return report


def test_level_0_is_unchanged():
    assert priced(strategy(), 0) == cost(BATTERY_CHALLENGE, strategy())


@pytest.mark.parametrize(
    ("value", "level"),
    [
        (atk.strategy(next(iter(atk.VALID.values())), steps=32), 1),
        (strategy(optimizer_family="muon", muon_spectral=True), 2),
        (
            strategy(
                pool_selection={
                    "pool_version": POOL,
                    "strata": {"train": 1.0},
                    "cases": 120,
                }
            ),
            2,
        ),
        (strategy(polish_steps=4, quasi_newton_family="bfgs"), 3),
        (strategy(polish_steps=4, line_search="backtracking"), 3),
    ],
)
def test_honest_development_recipes_price(value, level):
    priced(value, level)


def test_a_development_field_at_level_0_is_still_refused():
    with pytest.raises(Exception) as refused:
        cost(BATTERY_CHALLENGE, strategy(optimizer_family="muon", muon_spectral=True))
    assert "parameter" in str(refused.value) or "unknown" in str(refused.value)


def test_specmuon_costs_more_per_step_than_base_muon():
    base = priced(strategy(optimizer_family="muon"), 2)["programs"][0]
    spectral = priced(strategy(optimizer_family="muon", muon_spectral=True), 2)
    step = spectral["programs"][0]
    assert step["parameters"] == base["parameters"]
    assert step["step_flops"] > base["step_flops"]


def test_a_pool_selection_prices_at_its_drawn_size():
    selection = {"pool_version": POOL, "strata": {"train": 1.0}, "cases": 120}
    report = priced(strategy(pool_selection=selection, batch_size=400), 2)
    assert report["programs"][0]["cases_per_update"] == 120
    full = priced(strategy(batch_size=400), 0)["programs"][0]
    assert full["cases_per_update"] == 400
    assert report["programs"][0]["step_flops"] < full["step_flops"]


@pytest.mark.parametrize(
    ("routine", "search", "dense"),
    [
        ("bfgs", "strong_wolfe", 4),
        ("lbfgs", "none", 0),
        ("ssbroyden", "backtracking", 4),
    ],
)
def test_a_level_3_polish_prices_at_its_worst_case(routine, search, dense):
    polish = 4
    report = priced(
        strategy(polish_steps=polish, quasi_newton_family=routine, line_search=search),
        3,
    )
    (program,) = report["programs"]
    p, step = program["parameters"], program["step_flops"]
    factor = level3_numerics.evaluations_per_step(search)  # full batch = update
    expected = step * (program["main_steps"] + factor * polish) + polish * dense * p * p
    assert report["F4_flops"] == pytest.approx(expected, rel=1e-9)


def test_level_4_is_refused_typed_until_its_graph_flops_are_wired(monkeypatch):
    graph = {"schema": level4_worker.SCHEMA}
    monkeypatch.setattr(
        dv,
        "compile_development",
        lambda *a, **k: SimpleNamespace(construction=None, reconstruction={}),
    )
    monkeypatch.setattr(development_rebuild, "record", lambda reconstruction: graph)
    with pytest.raises(CostRefused) as refused:
        cost(BATTERY_CHALLENGE, strategy(), level=4)
    assert refused.value.code == "cost_level4_graph_pending"


class _Budgeted:
    def __init__(self, value):
        self.value = value

    def document(self):
        return {
            "envelope": {"compute_budget": {"unit": "F4_flops", "value": self.value}}
        }


def test_a_development_recipe_over_the_budget_is_refused():
    value = strategy(optimizer_family="muon", muon_spectral=True)
    f4 = priced(value, 2)["F4_flops"]
    challenge_contracts.check_compute_budget(_Budgeted(f4 * 2), value, level=2)
    with pytest.raises(challenge_contracts.SubmissionRefused) as refused:
        challenge_contracts.check_compute_budget(_Budgeted(f4 / 2), value, level=2)
    assert "budget.over_compute_budget" in str(refused.value.issues)


def test_a_development_compile_checks_the_budget_at_its_own_level(monkeypatch):
    calls = []
    monkeypatch.setattr(
        challenge_contracts,
        "check_compute_budget",
        lambda item, strategy, level=0: calls.append(level),
    )
    dv.compile_development(
        strategy(optimizer_family="muon", muon_spectral=True),
        dv.variant(BATTERY_CHALLENGE, 2),
    )
    assert 2 in calls
    calls.clear()
    dv.compile_development(
        strategy(optimizer_family="muon", muon_spectral=True),
        dv.variant(BATTERY_CHALLENGE, 2),
        check_budget=False,
    )
    assert 2 not in calls
