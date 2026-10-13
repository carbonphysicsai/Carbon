"""Actual fixed-program cost profiles; fixtures are not host isolation acceptance."""

from __future__ import annotations

import os
import subprocess
import sys
from copy import deepcopy
from types import SimpleNamespace

import pytest

pytest.importorskip("jax")
os.environ.setdefault("JAX_PLATFORMS", "cpu")

from test_battery_composed_graph import BASE, PARTS, ROOT, compiled, graph_input

from carbon.battery import composed_graph_cost as profile_cost
from carbon.level4 import compile as g5
from carbon.training_budget import cost

# Pytest registers this shared fixture by its exported module name.
__all__ = ["graph_input"]

IMAGE = "sha256:" + "1" * 64  # non-production fixture identity


@pytest.fixture(scope="module")
def profiles(tmp_path_factory, graph_input):
    directory = tmp_path_factory.mktemp("composed-cost")
    ledger = SimpleNamespace(root=directory)
    dispatches = []

    def runner(ledger, **kwargs):
        dispatches.append(kwargs)
        assert kwargs["seconds"] == g5.DEADLINE_SECONDS
        assert kwargs["provenance"] == g5.PROVENANCE and kwargs["extra_resources"] == {}
        operation = "fixture-" + str(len(dispatches))
        work = ledger.root / operation / "work"
        output = work.parent / "output"
        snapshot = work.parent / "snapshot"
        work.mkdir(parents=True)
        output.mkdir()
        snapshot.mkdir()
        for name, body in kwargs["files"].items():
            (work / name).write_bytes(body)
        (work / "program.py").write_text(
            kwargs["source"], encoding="utf-8", newline="\n"
        )
        subprocess.run(
            [sys.executable, "program.py"],
            cwd=work,
            env={
                "PYTHONPATH": str(ROOT),
                "JAX_PLATFORMS": "cpu",
                "PATH": "/usr/bin:/bin",
            },
            check=True,
            timeout=180,
        )
        assert (
            not (output / "state.npz").exists() and not (output / "fit.json").exists()
        )
        assert (output / "cost-profile.json").exists(), (
            (output / "failure.json").read_text()
            if (output / "failure.json").exists()
            else "no profile"
        )
        (snapshot / "cost-profile.json").write_bytes(
            (output / "cost-profile.json").read_bytes()
        )
        return {"operation": operation}

    _, _, _, input_hash = profile_cost._verified(
        graph_input[1],
        compiled(graph_input, pool_selection=PARTS["pool_selection"]).record,
    )
    base_g5 = {
        "train_step_flops": 1.0,
        "train_step_loss": "sum_of_squares",
        "input_digest": input_hash,
        "image": IMAGE,
        "scope": "development",
    }
    combinations = {
        "pool": {"pool_selection": PARTS["pool_selection"]},
        "l1_pool": {
            "pool_selection": PARTS["pool_selection"],
            "loss_expressions": PARTS["loss_expressions"],
        },
        "l3_pool": {
            "pool_selection": PARTS["pool_selection"],
            "quasi_newton_family": "bfgs",
            "line_search": "backtracking",
        },
        "l3_full_data": {"quasi_newton_family": "bfgs", "line_search": "backtracking"},
        "spectral_pool": {
            "pool_selection": PARTS["pool_selection"],
            "muon_spectral": True,
        },
    }
    made = {}
    for name, parts in combinations.items():
        found = compiled(graph_input, **parts)
        measured = profile_cost.compile_in_isolation(
            found,
            graph_input[1],
            base_g5,
            ledger=ledger,
            owner="fixture-owner",
            image=IMAGE,
            scope="development",
            runner=runner,
            root=ROOT,
        )
        made[name] = (found, measured)
    return made, dispatches, ledger


def test_actual_profile_counts_l1_optimizer_and_l3_without_double_count(profiles):
    made, _, _ = profiles
    pool = made["pool"][1]["composed_profile"]
    expression = made["l1_pool"][1]["composed_profile"]
    l3 = made["l3_pool"][1]["composed_profile"]
    full = made["l3_full_data"][1]["composed_profile"]
    assert all(row["status"] == "MEASURED" for row in (pool, expression, l3, full))
    assert pool["main_step_flops"] != expression["main_step_flops"]
    assert l3["polish_step_flops"] > 0
    assert (
        full["polish_step_flops"] > l3["polish_step_flops"]
    )  # actual full-batch work, not optimizer work scaled up
    found, result = made["l3_pool"]
    program = profile_cost.program(
        found.construction, found.record, result, PARTS["pool_selection"]["cases"]
    )
    expected = (
        program.main_steps * l3["main_step_flops"]
        + program.polish_steps * l3["polish_step_flops"]
    )
    assert (
        program.measured_step_flops
        * (program.main_steps + program.polish_steps * program.polish_factor)
        + program.polish_steps
        * program.polish_dense_flops_per_p2
        * program.measured_parameters**2
    ) == pytest.approx(expected)
    assert (
        program.measured_step_flops == l3["main_step_flops"]
    )  # G5 is not added a second time


def test_host_cost_consumer_never_profiles_or_prepares_graph(profiles, monkeypatch):
    from carbon.battery import level4_model

    made, _, _ = profiles
    found, measured = made["l3_pool"]

    def forbidden(*args, **kwargs):
        raise AssertionError("graph execution on evaluator host")

    monkeypatch.setattr(cost, "measure_jax", forbidden)
    monkeypatch.setitem(cost.MEASURE, "jax", forbidden)
    monkeypatch.setattr(cost, "_compiled", forbidden)
    monkeypatch.setattr(level4_model.GraphModel, "_prepare", forbidden)
    recipe = {
        "schema_version": "1.0",
        "challenge_id": found.challenge,
        "backbone": "mlp",
        "parameters": {
            **BASE,
            "composition_graphs": found.record["graph"]["submission"],
            "pool_selection": PARTS["pool_selection"],
            "quasi_newton_family": "bfgs",
            "line_search": "backtracking",
        },
    }
    report = cost.cost(
        found.challenge, recipe, level="composed", graph_compile=measured
    )
    assert report["F4_flops"] > 0
    for mutation in (
        "binding",
        "source_digest",
        "input_digest",
        "objective",
        "image",
        "g5_digest",
    ):
        wrong = deepcopy(measured)
        wrong["composed_profile"][mutation] = "wrong"
        with pytest.raises(cost.CostRefused):
            cost.cost(found.challenge, recipe, level="composed", graph_compile=wrong)


def test_opaque_svd_is_named_not_counted_as_zero(profiles):
    made, _, _ = profiles
    found, measured = made["spectral_pool"]
    row = measured["composed_profile"]
    assert row["status"] == "REFUSED" and row["field"] == "muon_spectral"
    assert "svd" in row["reason"]
    with pytest.raises(cost.CostRefused, match="muon_spectral"):
        profile_cost.program(
            found.construction, found.record, measured, PARTS["pool_selection"]["cases"]
        )


@pytest.mark.parametrize(
    "mutation", ["batch", "precision", "workspace", "g5_result", "missing_profile"]
)
def test_mixed_or_stale_profile_refuses_before_pricing(profiles, mutation):
    made, _, _ = profiles
    found, measured = made["l3_pool"]
    wrong = deepcopy(measured)
    if mutation == "batch":
        wrong["composed_profile"]["batch_size"] += 1
    elif mutation == "precision":
        wrong["composed_profile"]["precision"] = "float64"
    elif mutation == "workspace":
        wrong["composed_workspace"]["manifest"] = "e30="
    elif mutation == "g5_result":
        wrong["train_step_flops"] += 2
    else:
        del wrong["composed_profile"]
    with pytest.raises(cost.CostRefused):
        profile_cost.program(
            found.construction, found.record, wrong, PARTS["pool_selection"]["cases"]
        )


@pytest.mark.parametrize("value", [True, -1, float("inf"), float("nan"), "1"])
def test_invalid_measured_counts_refuse(profiles, value):
    made, _, _ = profiles
    found, measured = made["l3_pool"]
    wrong = deepcopy(measured)
    wrong["composed_profile"]["main_step_flops"] = value
    with pytest.raises(cost.CostRefused):
        profile_cost.program(
            found.construction, found.record, wrong, PARTS["pool_selection"]["cases"]
        )


def test_profile_driver_rejects_g5_mix_and_mainnet_without_dispatch(
    profiles, graph_input
):
    made, dispatches, ledger = profiles
    found, measured = made["l3_pool"]
    before = len(dispatches)
    with pytest.raises(g5.CompileBlocked):
        profile_cost.compile_in_isolation(
            found,
            graph_input[1],
            measured,
            ledger=ledger,
            owner="fixture",
            image=IMAGE,
            scope="mainnet",
            runner=lambda *a, **k: pytest.fail("dispatch"),
        )
    wrong = {**measured, "input_digest": "wrong"}
    with pytest.raises(cost.CostRefused):
        profile_cost.compile_in_isolation(
            found,
            graph_input[1],
            wrong,
            ledger=ledger,
            owner="fixture",
            image=IMAGE,
            scope="development",
            runner=lambda *a, **k: pytest.fail("dispatch"),
        )
    assert len(dispatches) == before


@pytest.mark.parametrize(
    "g5_value", [None, {}, {"train_step_flops": 0}, {"train_step_flops": float("inf")}]
)
def test_existing_g5_requirement_cannot_be_bypassed(profiles, g5_value):
    made, _, _ = profiles
    found, _ = made["l3_pool"]
    with pytest.raises(cost.CostRefused, match="composition_graphs"):
        profile_cost.program(
            found.construction, found.record, g5_value, PARTS["pool_selection"]["cases"]
        )


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("polish_step_flops", float("inf")),
        ("polish_step_flops", -1),
        ("polish_step_flops", True),
        ("parameter_count", True),
        ("parameter_count", -1),
        ("parameter_count", 1),
        ("polish_gradient_flops", True),
        ("polish_gradient_flops", float("inf")),
        ("polish_gradient_flops", -1),
        ("polish_gradient_flops", 0),
    ],
)
def test_all_profile_counts_are_typed_finite_and_nonnegative(profiles, key, value):
    made, _, _ = profiles
    found, measured = made["l3_pool"]
    changed = deepcopy(measured)
    changed["composed_profile"][key] = value
    with pytest.raises(cost.CostRefused):
        profile_cost.program(
            found.construction, found.record, changed, PARTS["pool_selection"]["cases"]
        )


def test_nested_data_dependent_work_is_detected_before_counting():
    import jax
    import jax.numpy as jnp

    @jax.jit
    def nested(x):
        return jax.lax.while_loop(lambda y: y < 8, lambda y: y + 1, x)

    closed = jax.make_jaxpr(lambda x: nested(x))(jnp.array(0.0))
    assert "while" in profile_cost._names(closed, cost) & profile_cost.OPAQUE


def test_supplied_polish_factor_preserves_dense_graph_work(profiles):
    made, _, _ = profiles
    found, measured = made["l3_pool"]
    profile = measured["composed_profile"]
    recipe = {
        "schema_version": "1.0",
        "challenge_id": found.challenge,
        "backbone": "mlp",
        "parameters": {
            **BASE,
            "composition_graphs": found.record["graph"]["submission"],
            "pool_selection": PARTS["pool_selection"],
            "quasi_newton_family": "bfgs",
            "line_search": "backtracking",
        },
    }
    main, polish = BASE["steps"] - BASE["polish_steps"], BASE["polish_steps"]
    dense = 4 * profile["parameter_count"] ** 2 * polish
    for factor in (0, 2.5):
        report = cost.cost(
            found.challenge,
            recipe,
            level="composed",
            graph_compile=measured,
            factors={"k_polish": factor},
        )
        assert report["F4_flops"] == pytest.approx(
            profile["main_step_flops"] * (main + factor * polish) + dense
        )
    default = cost.cost(
        found.challenge, recipe, level="composed", graph_compile=measured
    )
    assert default["F4_flops"] == pytest.approx(
        main * profile["main_step_flops"] + polish * profile["polish_step_flops"]
    )
    assert default["F1"] > 0


def test_nonfinite_g5_metadata_has_a_typed_refusal(profiles):
    made, _, _ = profiles
    found, measured = made["l3_pool"]
    changed = deepcopy(measured)
    changed["compile_seconds"] = float("nan")
    with pytest.raises(cost.CostRefused, match="cost_profile_g5_invalid"):
        profile_cost.program(
            found.construction, found.record, changed, PARTS["pool_selection"]["cases"]
        )
