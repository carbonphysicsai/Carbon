"""TRAINING-BUDGET-01 slice 1: the cost calculator (F0-F4).

Hand-counted small programs pin each backend's counting; the battery adapter
runs the real recipes on pinned TRAIN v1 without training them.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from carbon.reconstruction import capability_registry
from carbon.training_budget import cost
from carbon.training_budget.adapter import Program

BATTERY = capability_registry.BATTERY_CHALLENGE
B, N, M = 32, 64, 48


def battery(**parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": parameters,
    }


@dataclass
class Synthetic:
    """A test Challenge's adapter over one given program."""

    program: Program
    challenge_id: str = "synthetic"
    records = {}

    def contract(self):
        return None

    def backends(self):
        return ("jax", "pytorch")

    def train_cases(self):
        return B

    def training_programs(self, strategy, *, train_cases=None):
        return [self.program]


@pytest.fixture
def synthetic(monkeypatch):
    def install(program):
        monkeypatch.setattr(cost, "adapter_for", lambda challenge: Synthetic(program))
        return cost.cost("synthetic", {})

    return install


# -- JAX ----------------------------------------------------------------------


def jax_program(steps, body="dot", members=1, polish=0):
    jax = pytest.importorskip("jax")
    jnp = jax.numpy

    def fit(main_steps):
        @jax.jit
        def train(w, x):
            def step(c, _):
                if body == "dot":
                    return c, x @ w
                if body == "while":
                    return (
                        jax.lax.while_loop(lambda v: v.sum() < 0, lambda v: v, c),
                        None,
                    )
                return c, None

            return jax.lax.scan(step, w, None, length=main_steps)

        return train(jnp.ones((N, M), jnp.float32), jnp.ones((B, N), jnp.float32))

    return Program(
        backend="jax",
        members=members,
        main_steps=steps,
        polish_steps=polish,
        cases_per_update=B,
        fit=fit,
        parameters=lambda args: int(args[0].size),
    )


def test_a_jax_step_is_counted_once_per_step_not_once_per_loop(synthetic):
    """XLA counts a loop body once; the calculator counts it per step."""
    short = synthetic(jax_program(10))
    long = synthetic(jax_program(100))
    step = 2 * B * N * M  # one (B x N) @ (N x M) product, hand-counted
    assert short["programs"][0]["step_flops"] == step
    assert short["F4_flops"] == 10 * step and long["F4_flops"] == 100 * step
    assert short["F0_steps"] == 10 and short["F1"] == N * M * B * 10
    assert short["peak_memory_bytes"] > 0


def test_jax_members_and_polish(synthetic):
    step = 2 * B * N * M
    two = synthetic(jax_program(10, members=2))
    assert two["F4_flops"] == 2 * 10 * step and two["F0_steps"] == 20
    polished = synthetic(jax_program(10, polish=4))
    assert (
        polished["F4_flops"] == cost.HUMAN_INPUT and polished["F2"] == cost.HUMAN_INPUT
    )
    assert polished["F0_steps"] == 14


def test_supplied_factors_complete_f2_f3_and_f4(monkeypatch):
    program = jax_program(10, polish=4)
    monkeypatch.setattr(cost, "adapter_for", lambda challenge: Synthetic(program))
    factors = {
        "k_opt": 1.5,
        "k_polish": 3.0,
        "F3_seconds": {"setup_s": 2.0, "per_unit_s": 1e-9},
        "F4_seconds": {"setup_s": 2.0, "per_unit_s": 1e-12},
    }
    report = cost.cost("synthetic", {}, factors=factors)
    p_b, step = N * M * B, 2 * B * N * M
    assert report["F2"] == 1.5 * p_b * 10 + 3.0 * p_b * 4
    assert report["F4_flops"] == step * (10 + 3.0 * 4)
    assert report["F3_seconds"] == 2.0 + 1e-9 * report["F2"]
    assert report["F4_seconds"] == 2.0 + 1e-12 * report["F4_flops"]


def test_an_unbounded_loop_is_refused(synthetic):
    with pytest.raises(cost.CostRefused) as refused:
        synthetic(jax_program(10, body="while"))
    assert refused.value.code == "cost_unbounded_loop"


def test_capture_restores_jit_even_when_refused(synthetic):
    jax = pytest.importorskip("jax")
    real = jax.jit
    with pytest.raises(cost.CostRefused):
        synthetic(jax_program(10, body="while"))
    assert jax.jit is real


def test_a_fit_without_a_jitted_loop_is_refused(synthetic):
    program = Program("jax", 1, 10, 0, B, lambda steps: {}, lambda args: 0)
    with pytest.raises(cost.CostRefused) as refused:
        synthetic(program)
    assert refused.value.code == "cost_program_not_captured"


# -- PyTorch ------------------------------------------------------------------


def torch_program(steps):
    torch = pytest.importorskip("torch")

    def fit(main_steps):
        w = torch.ones(N, M, requires_grad=True)
        x = torch.ones(B, N)
        for _ in range(main_steps):
            (x @ w).sum().backward()
        return {"n_params": w.numel()}

    return Program("pytorch", 1, steps, 0, B, fit, lambda args: 0)


def test_a_pytorch_step_is_its_forward_and_backward_products(synthetic):
    report = synthetic(torch_program(10))
    # Forward (B x N)(N x M) and the weight gradient's (N x B)(B x M).
    step = 2 * (2 * B * N * M)
    assert report["programs"][0]["step_flops"] == step
    assert report["programs"][0]["outside_flops"] == 0
    assert report["F4_flops"] == 10 * step and report["F1"] == N * M * B * 10


# -- Battery, through its adapter ---------------------------------------------


def test_battery_jax_recipes_cost_without_training():
    pytest.importorskip("jax")
    small = cost.cost(BATTERY, battery(width=32, depth=2, steps=64))
    double = cost.cost(BATTERY, battery(width=32, depth=2, steps=128))
    (row,) = small["programs"]
    assert row["backend"] == "jax" and row["cases_per_update"] == 400
    assert small["F1"] == row["parameters"] * 400 * 64
    assert double["F4_flops"] == 2 * small["F4_flops"]
    members = cost.cost(
        BATTERY, battery(width=32, depth=2, steps=64, ensemble_members=2)
    )
    (member,) = members["programs"]
    assert member["members"] == 2 and member["main_steps"] == 32
    assert members["F0_steps"] == 64


def test_a_battery_knn_trains_nothing():
    report = cost.cost(BATTERY, {**battery(), "backbone": "knn"})
    assert (
        report["programs"] == [] and report["F0_steps"] == 0 and report["F4_flops"] == 0
    )


def test_battery_pytorch_recipe_costs_through_the_same_function():
    pytest.importorskip("torch")
    report = cost.cost(BATTERY, battery(width=32, depth=2, steps=64, backend="pytorch"))
    (row,) = report["programs"]
    assert row["backend"] == "pytorch" and row["step_flops"] > 0
    assert report["F1"] == row["parameters"] * 400 * 64


def test_a_study_train_size_changes_cases_per_update():
    pytest.importorskip("jax")
    report = cost.cost(BATTERY, battery(width=32, depth=2, steps=64), train_cases=100)
    assert report["programs"][0]["cases_per_update"] == 100
