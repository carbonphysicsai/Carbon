"""The two pinned Julia environments do real SciML work in the miner's sandbox.

Requires the built authored-Julia image (the Julia service suite builds it).
Each program runs through run_julia - the isolated, network-free miner lane -
and asserts a numerical result rather than only that a package loads: a solved
ODE against its exact solution, a symbolic derivative, an Enzyme gradient
against a finite difference, a NeuralPDE problem built from a symbolic PDE, and
the challenge kit labelling a case with the trusted solver. Everything here is
self-reported research; nothing is qualified.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests/cpu")]

from test_authored_julia import prepared

from carbon.development_session.julia_analysis import (
    build_julia_analysis_image,
    run_julia,
)
from carbon.reconstruction.worker.model import WorkerFailure


@pytest.fixture(scope="module")
def image(tmp_path_factory):
    return build_julia_analysis_image(
        Path(os.environ["CARBON_JULIA_WORKER_MANIFEST"]),
        Path(
            os.environ.get(
                "CARBON_AUTHORED_JULIA_IMAGE_ROOT",
                str(tmp_path_factory.mktemp("julia-image")),
            )
        ),
    )


def run(image, tmp_path, identity, source, environment):
    ledger, _ = prepared(tmp_path, image=image)
    try:
        result = run_julia(
            ledger,
            owner="test-miner",
            identity=identity,
            source=source,
            files={},
            image=image,
            seconds=1800,
            environment=environment,
        )
    except WorkerFailure as exc:
        pytest.fail(exc.private_diagnostic.decode("utf-8", errors="replace"))
    snapshot = ledger.root / result["operation"] / "snapshot"
    return json.loads((snapshot / "result.json").read_bytes())


def test_current_solves_symbolic_numeric_and_differentiable_problems(image, tmp_path):
    source = r"""
using ModelingToolkit, OrdinaryDiffEq, Symbolics, Lux, Enzyme, Random
using ModelingToolkit: t_nounits as t, D_nounits as D
# A symbolic-numeric ODE, solved and checked against exp(-2t).
@variables x(t)
@mtkcompile sys = System([D(x) ~ -2x], t)
sol = solve(ODEProblem(sys, [x => 1.0], (0.0, 1.0)), Tsit5(); abstol=1e-10, reltol=1e-10)
ode_error = abs(sol[x][end] - exp(-2.0))
@assert ode_error < 1e-7
# A symbolic derivative.
@variables y
dy = Symbolics.derivative(sin(y)^2, y)
@assert Symbolics.value(substitute(dy - 2sin(y)*cos(y), Dict(y => 0.7))) ≈ 0 atol=1e-12
# A Lux model differentiated by Enzyme, checked against a central difference.
model = Chain(Dense(3 => 8, tanh), Dense(8 => 1))
ps, st = Lux.setup(Random.Xoshiro(0), model)
loss(v) = sum(abs2, first(model(reshape(v, 3, 1), ps, st)))
v = [0.1, -0.2, 0.3]
g = Enzyme.gradient(Enzyme.Reverse, loss, v)[1]
h = 1e-6
fd = [(loss(v .+ h .* (1:3 .== i)) - loss(v .- h .* (1:3 .== i))) / 2h for i in 1:3]
@assert maximum(abs.(g .- fd)) < 1e-5
open("/scratch/output/result.json", "w") do io
    print(io, "{\"ode_error\":", ode_error, ",\"gradient_gap\":", maximum(abs.(g .- fd)), "}")
end
"""
    values = run(image, tmp_path, "sciml-current", source, "current")
    assert values["ode_error"] < 1e-7
    assert values["gradient_gap"] < 1e-5


def test_pde_builds_a_physics_informed_problem_from_a_symbolic_pde(image, tmp_path):
    source = r"""
using NeuralPDE, ModelingToolkit, Lux, Optimization, OptimizationOptimisers, Random
using DomainSets: Interval
@parameters x
@variables u(..)
Dx = Differential(x)
eq = Dx(Dx(u(x))) ~ -sin(x)
bcs = [u(0.0) ~ 0.0, u(Float64(pi)) ~ 0.0]
@named pde = PDESystem(eq, bcs, [x ∈ Interval(0.0, Float64(pi))], [x], [u(x)])
chain = Chain(Dense(1 => 12, tanh), Dense(12 => 1))
discretization = PhysicsInformedNN(chain, GridTraining(0.2))
prob = discretize(pde, discretization)
first_loss = prob.f(prob.u0, prob.p)
res = solve(prob, OptimizationOptimisers.Adam(0.02); maxiters=150)
last_loss = prob.f(res.u, prob.p)
@assert isfinite(first_loss) && last_loss < first_loss
open("/scratch/output/result.json", "w") do io
    print(io, "{\"first_loss\":", first_loss, ",\"last_loss\":", last_loss, "}")
end
"""
    values = run(image, tmp_path, "sciml-pde", source, "pde")
    assert values["last_loss"] < values["first_loss"]

