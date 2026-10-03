"""Bounded loss expressions and battery's Level-1 draft (GRAPHITE-ADMISSION-01 slice B).

Claims tested:
- an expression is validated against a closed operation set, put in canonical
  form and pinned by digest; anything outside the set is refused by code;
- Carbon rebuilds an expression from its pinned bytes alone, in a clean
  process, to the same trained parameters;
- the expression that restates battery's registered objective menu computes
  the menu's loss;
- nothing is opened: battery's contract, its expansion records and every miner
  path are unchanged, and the draft surface is refused by name.
"""

from __future__ import annotations

import importlib.util
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from carbon.battery import level1_draft as l1
from carbon.challenge_pipeline import proposals
from carbon.reconstruction import capability_registry as cr
from carbon.reconstruction import expansion_record
from carbon.reconstruction import loss_expressions as le
from carbon.reconstruction.challenge_contracts import validate_for_challenge

REPOSITORY = Path(__file__).resolve().parents[2]
BATTERY = cr.BATTERY_CHALLENGE
T = 12

EXPRESSION = {
    "op": "add",
    "args": [
        {"op": "div", "args": [{"term": "sq_error"}, {"term": "target_energy"}]},
        {"op": "scale", "by": 0.5, "arg": {"term": "traj_d1"}},
        {
            "op": "log1p",
            "arg": {"op": "pow", "exponent": 1.5, "arg": {"term": "traj_spectral"}},
        },
    ],
}


def arrays(seed=0, cases=5):
    rng = np.random.default_rng(seed)
    width = 2 * T + 3
    return (
        rng.normal(size=(cases, width)),
        rng.normal(size=(cases, width)),
        rng.uniform(0.5, 1.5, size=width),
    )


def trajectory(z):
    return z[:, :T], z[:, T : 2 * T]


def test_an_expression_compiles_to_a_canonical_pinned_form():
    first = le.compile_expression(EXPRESSION, l1.OPERATIONS)
    reordered = {**EXPRESSION, "args": list(reversed(EXPRESSION["args"]))}
    assert le.compile_expression(reordered, l1.OPERATIONS).digest == first.digest
    scaled = le.compile_expression(
        {"op": "scale", "by": 2, "arg": {"term": "sq_error"}}, l1.OPERATIONS
    )
    assert scaled.expression["by"] == 2.0 and type(scaled.expression["by"]) is float
    assert (
        le.compile_expression(
            {"op": "scale", "by": 2.0, "arg": {"term": "sq_error"}}, l1.OPERATIONS
        ).digest
        == scaled.digest
    )
    assert scaled.digest != first.digest
    assert first.document()["operation_set"] == l1.OPERATIONS.digest
    rebuilt = le.from_bytes(first.canonical_bytes(), l1.OPERATIONS)
    assert rebuilt == first


@pytest.mark.parametrize(
    "expression, code",
    [
        ({"term": "score"}, "term_not_registered"),
        ({"op": "exp", "arg": {"term": "sq_error"}}, "operation_not_in_the_set"),
        ("lambda z: z", "node_is_an_object"),
        ({"term": "sq_error", "op": "add"}, "node_fields"),
        ({"op": "scale", "by": True, "arg": {"term": "sq_error"}}, "by_outside_bounds"),
        (
            {"op": "scale", "by": math.nan, "arg": {"term": "sq_error"}},
            "by_outside_bounds",
        ),
        ({"op": "scale", "by": 10.5, "arg": {"term": "sq_error"}}, "by_outside_bounds"),
        ({"op": "scale", "by": -1, "arg": {"term": "sq_error"}}, "by_outside_bounds"),
        (
            {"op": "pow", "exponent": 3, "arg": {"term": "sq_error"}},
            "exponent_outside_bounds",
        ),
        ({"op": "add", "args": [{"term": "sq_error"}]}, "arity"),
        (
            {"op": "mul", "args": [{"term": "sq_error"}] * 3},
            "arity",
        ),
        (
            {
                "op": "log1p",
                "arg": {
                    "op": "log1p",
                    "arg": {
                        "op": "log1p",
                        "arg": {"op": "sqrt", "arg": {"term": "sq_error"}},
                    },
                },
            },
            "too_deep",
        ),
        (
            {
                "op": "add",
                "args": [
                    {"op": "add", "args": [{"term": "sq_error"}] * 8},
                    {"op": "add", "args": [{"term": "traj_d1"}] * 8},
                ],
            },
            "too_many_nodes",
        ),
    ],
)
def test_an_expression_outside_the_set_is_refused_by_code(expression, code):
    with pytest.raises(le.ExpressionRefused) as refused:
        le.compile_expression(expression, l1.OPERATIONS)
    assert refused.value.code == code


def test_pinned_bytes_bind_their_operation_set():
    compiled = le.compile_expression(EXPRESSION, l1.OPERATIONS)
    other = le.OperationSet(
        name="other",
        terms=l1.OPERATIONS.terms,
        max_depth=5,
        max_nodes=16,
        max_arity=8,
        scale=(0.0, 10.0),
        exponent=(0.5, 2.0),
        epsilon=1e-6,
    )
    with pytest.raises(le.ExpressionRefused, match="operation_set_mismatch"):
        le.from_bytes(compiled.canonical_bytes(), other)
    with pytest.raises(le.ExpressionRefused, match="not_json"):
        le.from_bytes(b"{", l1.OPERATIONS)


def _registered_case_loss(settings, zhat, zt, gw):
    """`carbon/battery/training.py` train.case_loss, restated in numpy."""
    base = np.sum((zhat - zt) ** 2 * gw[None, :], axis=1)
    if settings["relative_loss"]:
        base = base / (np.sum(zt**2 * gw[None, :], axis=1) + 1e-6)
    extra = 0.0
    for a, b in zip(trajectory(zhat), trajectory(zt)):
        e = a - b
        if settings["time_weighting"] != "uniform":
            ramp = (
                np.linspace(2.0, 0.0, e.shape[1])
                if settings["time_weighting"] == "early"
                else np.linspace(0.0, 2.0, e.shape[1])
            )
            extra = extra + np.mean(ramp * e**2, axis=1)
        if settings["h1_weight"]:
            extra = extra + settings["h1_weight"] * np.mean(
                np.diff(e, axis=1) ** 2, axis=1
            )
        if settings["h2_weight"]:
            extra = extra + settings["h2_weight"] * np.mean(
                np.diff(e, n=2, axis=1) ** 2, axis=1
            )
        if settings["spectral_weight"]:
            spectrum = np.abs(np.fft.rfft(e, axis=1)) ** 2
            k = np.linspace(0.0, 1.0, spectrum.shape[1])
            extra = (
                extra
                + settings["spectral_weight"]
                * np.mean(k * spectrum, axis=1)
                / e.shape[1]
            )
    return base + extra


MENUS = [
    {
        "relative_loss": False,
        "time_weighting": "uniform",
        "h1_weight": 0.0,
        "h2_weight": 0.0,
        "spectral_weight": 0.0,
    },
    {
        "relative_loss": True,
        "time_weighting": "early",
        "h1_weight": 0.5,
        "h2_weight": 0.0,
        "spectral_weight": 2.0,
    },
    {
        "relative_loss": False,
        "time_weighting": "late",
        "h1_weight": 1.0,
        "h2_weight": 3.0,
        "spectral_weight": 0.25,
    },
]


@pytest.mark.parametrize("settings", MENUS)
def test_the_menu_expression_computes_the_registered_objective(settings):
    zhat, zt, gw = arrays()
    compiled = le.compile_expression(l1.menu_expression(settings), l1.OPERATIONS)
    got = le.evaluate(compiled, l1.terms(np, zhat, zt, gw, trajectory), np)
    expected = _registered_case_loss(settings, zhat, zt, gw)
    np.testing.assert_allclose(got, expected, rtol=1e-12, atol=0)


def test_every_operation_keeps_the_loss_finite_and_differentiable():
    jax = pytest.importorskip("jax")
    import jax.numpy as jnp

    zhat, zt, gw = (jnp.asarray(a, jnp.float32) for a in arrays(1))
    exact = jnp.asarray(np.asarray(zt))  # a perfect prediction: every error is 0
    for op in ("sqrt", "log1p"):
        compiled = le.compile_expression(
            {"op": op, "arg": {"term": "sq_error"}}, l1.OPERATIONS
        )

        def loss(z, compiled=compiled):
            return jnp.mean(
                le.evaluate(compiled, l1.terms(jnp, z, zt, gw, trajectory), jnp)
            )

        for z in (zhat, exact):
            value, grad = jax.value_and_grad(loss)(z)
            assert np.isfinite(float(value)) and np.isfinite(np.asarray(grad)).all()
    compiled = le.compile_expression(EXPRESSION, l1.OPERATIONS)
    value = le.evaluate(compiled, l1.terms(jnp, zhat, zt, gw, trajectory), jnp)
    assert (np.asarray(value) >= 0).all()


#: A tiny deterministic fit with a compiled loss, run in this process and in a
#: clean one from the pinned bytes alone.
FIT = """
def fit(compiled, steps=30):
    import hashlib
    import jax
    import jax.numpy as jnp
    import numpy as np
    from carbon.battery.level1_draft import terms
    from carbon.reconstruction.loss_expressions import evaluate
    T = 8
    rng = np.random.RandomState(7)
    x = jnp.asarray(rng.normal(size=(6, 3)), jnp.float32)
    zt = jnp.asarray(rng.normal(size=(6, 2 * T + 1)), jnp.float32)
    gw = jnp.asarray(rng.uniform(0.5, 1.5, size=2 * T + 1), jnp.float32)
    w = jnp.asarray(rng.normal(size=(3, 2 * T + 1)) * 0.1, jnp.float32)
    def traj(z):
        return z[:, :T], z[:, T:2 * T]
    def loss(w):
        return jnp.mean(evaluate(compiled, terms(jnp, x @ w, zt, gw, traj), jnp))
    grad = jax.jit(jax.grad(loss))
    for _ in range(steps):
        w = w - 0.05 * grad(w)
    return hashlib.sha256(np.asarray(w).tobytes()).hexdigest()


if __name__ == "__main__":
    import sys
    from carbon.battery.level1_draft import OPERATIONS
    from carbon.reconstruction.loss_expressions import from_bytes
    with open(sys.argv[1], "rb") as pinned:
        print(fit(from_bytes(pinned.read(), OPERATIONS)))
"""


def test_carbon_rebuilds_an_expression_in_a_clean_process(tmp_path):
    pytest.importorskip("jax")
    compiled = le.compile_expression(EXPRESSION, l1.OPERATIONS)
    source = tmp_path / "rebuild_fit.py"
    source.write_text(FIT)
    spec = importlib.util.spec_from_file_location("rebuild_fit", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    here = module.fit(compiled)
    pinned = tmp_path / "expression.json"
    pinned.write_bytes(compiled.canonical_bytes())
    # A clean process that has only the pinned bytes.
    clean = subprocess.run(
        [sys.executable, str(source), str(pinned)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(REPOSITORY)},
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    assert clean.stdout.strip() == here
    # A different expression trains to different parameters.
    other = le.compile_expression({"term": "sq_error"}, l1.OPERATIONS)
    assert module.fit(other) != here


def test_the_draft_is_shaped_like_a_level_proposal():
    assert l1.DRAFT["status"] == "ENGINEERING_DRAFT" and l1.DRAFT["level"] == 1
    # It is the implementing agent's draft, never presented as Graphite's.
    assert "proposed_by" not in l1.DRAFT and "not a Graphite" in l1.DRAFT["drafted_by"]
    for capability in l1.DRAFT["capabilities"]:
        assert set(capability) == proposals.CAPABILITY_KEYS
        assert proposals.CAPABILITY_ID.match(capability["id"])
        assert capability["sources"] and all(capability["sources"])
    assert l1.DRAFT["left_out"]
    assert l1.DRAFT["capabilities"][0]["id"] == l1.PERMISSION


def test_nothing_is_opened_to_miners():
    battery = cr.contract(BATTERY)
    assert cr.capability(l1.PERMISSION, BATTERY).status is cr.Status.EXCLUDED
    assert "loss_expressions" not in cr.catalog_surfaces(BATTERY)
    public = {c["id"]: c["status"] for c in cr.public_registry(BATTERY)["capabilities"]}
    assert public[l1.PERMISSION] == "excluded"
    # The miner path refuses the draft surface by name.
    strategy = {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": "mlp",
        "parameters": {"loss_expressions": "sq_error"},
    }
    result = validate_for_challenge(strategy)
    assert not result.ok
    assert ("parameter.not_rebuildable", "/parameters/loss_expressions") in {
        (i.code, i.path) for i in result.errors
    }
    # No expansion was recorded and the contract is its newest record.
    assert expansion_record.unrecorded() == {}
    newest = expansion_record.records(BATTERY)[-1]
    assert newest["contract_digest"] == battery.digest
    # The development profile is not a contract and is never served.
    profile = l1.development_profile()
    assert profile["scope"] == "DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS"
    assert profile["base_contract_digest"] == battery.digest
    assert profile["digest"] not in {c.digest for c in cr.CONTRACTS.values()}
    # No miner-facing module reads the draft.
    for relative in (
        "carbon/reconstruction/capability_registry.py",
        "carbon/reconstruction/challenge_contracts.py",
        "carbon/battery/compile.py",
        "carbon/battery/training.py",
        "carbon/battery/intake.py",
        "carbon/battery/daemon.py",
        *(
            str(p.relative_to(REPOSITORY))
            for p in (REPOSITORY / "carbon/miner_mcp").rglob("*.py")
        ),
    ):
        text = (REPOSITORY / relative).read_text()
        assert "level1_draft" not in text and "loss_expressions import" not in text
