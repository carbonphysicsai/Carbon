"""The compute cost of a recipe: F0-F4 (`CHALLENGE_TRAINING_BUDGET_STUDY.md`).

One function for every Challenge and backend: `cost(challenge, strategy)`.
The Challenge's adapter turns the recipe into its training programs; this
module measures each one and combines them.

- **JAX.** The adapter's fit runs with `jax.jit` captured: the first jitted
  call whose program holds a top-level loop is the training program, and it
  is compiled, never run. XLA's cost analysis counts a loop body once
  whatever its trip count, so each `scan` body is compiled on its own and
  counted `length` times (nested scans the same way). A `while` loop has no
  static trip count and is refused (`cost_unbounded_loop`).
- **PyTorch.** PyTorch's FLOP counter over two short fits of the same member
  (16 and 32 main steps); the difference per step is the step's cost. The two
  backends count by their own conventions, so a study fits each backend's
  conversion to seconds separately.

F0 and F1 are exact from the recipe and the compiled parameter count. F2
needs the study's measured optimizer and polish factors, F4 needs the polish
factor when the recipe polishes, and F3 and F4 in seconds need the study's
fitted conversion. Each is `HUMAN_INPUT` until it is supplied. No factor,
rate or budget is chosen here.

Deterministic: the same recipe on the same image gives the same numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

from .adapter import Program, adapter_for

SCHEMA = "carbon.training-budget.cost.v1"
HUMAN_INPUT = "HUMAN_INPUT"
#: The two short PyTorch fits whose difference is one step's cost.
TORCH_STEPS = (16, 32)


class CostRefused(ValueError):
    """A recipe whose cost cannot be measured, by a closed code."""

    def __init__(self, code, detail=""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code


@dataclass(frozen=True)
class Measured:
    """One training program's measurement, per member."""

    parameters: int
    step_flops: float
    outside_flops: float
    peak_memory_bytes: int | None


# -- JAX ----------------------------------------------------------------------


class _Captured(Exception):
    pass


def _subjaxprs(eqn):
    """The closed sub-programs of an equation, by parameter."""
    from jax.extend import core

    found = []
    for value in eqn.params.values():
        for item in value if isinstance(value, (list, tuple)) else (value,):
            if isinstance(item, core.ClosedJaxpr):
                found.append(item)
            elif isinstance(item, core.Jaxpr):
                if item.constvars:
                    raise CostRefused("cost_program_unsupported", "open sub-program")
                found.append(core.ClosedJaxpr(item, []))
    return found


def _has_loop(jaxpr):
    for eqn in jaxpr.eqns:
        if eqn.primitive.name in ("scan", "while"):
            return True
        if any(_has_loop(sub.jaxpr) for sub in _subjaxprs(eqn)):
            return True
    return False


def _compiled(closed):
    import jax
    from jax.extend import core

    inputs = [
        jax.ShapeDtypeStruct(v.aval.shape, v.aval.dtype) for v in closed.jaxpr.invars
    ]
    return jax.jit(core.jaxpr_as_fun(closed)).lower(*inputs).compile()


def _xla_flops(closed):
    analysis = _compiled(closed).cost_analysis()
    analysis = analysis[0] if isinstance(analysis, list) else analysis
    return float(analysis.get("flops", 0.0))


def _extra(closed):
    """What XLA's single count of each loop body leaves out."""
    extra = 0.0
    for eqn in closed.jaxpr.eqns:
        name = eqn.primitive.name
        if name == "while":
            raise CostRefused(
                "cost_unbounded_loop", "a while loop has no static trip count"
            )
        subs = _subjaxprs(eqn)
        if name == "scan":
            (body,) = subs
            n = int(eqn.params["length"])
            extra += (n - 1) * _xla_flops(body) + n * _extra(body)
        elif name == "cond":
            if any(_has_loop(sub.jaxpr) for sub in subs):
                raise CostRefused("cost_program_unsupported", "a loop inside a branch")
        else:
            for sub in subs:
                extra += _extra(sub)
    return extra


def _loops(closed):
    """The top-level loops of a program, looking through calls but not into
    loop bodies."""
    found = []
    for eqn in closed.jaxpr.eqns:
        if eqn.primitive.name == "scan":
            found.append(eqn)
        else:
            for sub in _subjaxprs(eqn):
                found.extend(_loops(sub))
    return found


class _Jitted:
    """A jitted function under capture. Calling or lowering it with a loop in
    its program records the program and stops the fit; anything else runs the
    real jitted function."""

    def __init__(self, compiled, fun, options, seen):
        self._compiled, self._fun, self._options, self._seen = (
            compiled,
            fun,
            options,
            seen,
        )

    def _check(self, args, kwargs):
        import jax

        static = self._options.get("static_argnums", ())
        closed = jax.make_jaxpr(self._fun, static_argnums=static)(*args, **kwargs)
        if _has_loop(closed.jaxpr):
            self._seen.append((closed, args))
            raise _Captured

    def __call__(self, *args, **kwargs):
        self._check(args, kwargs)
        return self._compiled(*args, **kwargs)

    def lower(self, *args, **kwargs):
        self._check(args, kwargs)
        return self._compiled.lower(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._compiled, name)


def _capture(fit, steps):
    """The first jitted program `fit(steps)` runs that holds a loop."""
    import jax

    real = jax.jit
    seen = []

    def jit(fun=None, **options):
        if fun is None:
            return lambda f: jit(f, **options)
        return _Jitted(real(fun, **options), fun, options, seen)

    jax.jit = jit
    try:
        fit(steps)
    except _Captured:
        pass
    finally:
        jax.jit = real
    if not seen:
        raise CostRefused("cost_program_not_captured", "no jitted training loop")
    return seen[0]


def measure_jax(program: Program) -> Measured:
    closed, args = _capture(program.fit, program.main_steps)
    total = _xla_flops(closed) + _extra(closed)
    loops = _loops(closed)
    if len(loops) != 1:
        raise CostRefused(
            "cost_program_unsupported", f"{len(loops)} top-level training loops"
        )
    (loop,) = loops
    body = loop.params["jaxpr"]
    n = int(loop.params["length"])
    if n != program.main_steps:
        raise CostRefused(
            "cost_program_unsupported",
            f"the training loop runs {n} steps, not the recipe's {program.main_steps}",
        )
    step = _xla_flops(body) + _extra(body)
    memory = _compiled(closed).memory_analysis()
    peak = None
    if memory is not None:
        peak = int(
            memory.argument_size_in_bytes
            + memory.output_size_in_bytes
            + memory.temp_size_in_bytes
            - memory.alias_size_in_bytes
        )
    # Compiled alone, a loop body fuses slightly differently than inside its
    # loop, so the remainder can come out a few FLOPs below zero.
    return Measured(program.parameters(args), step, max(0.0, total - n * step), peak)


# -- PyTorch ------------------------------------------------------------------


def measure_torch(program: Program) -> Measured:
    from torch.utils.flop_counter import FlopCounterMode

    counts, stats = [], None
    for steps in TORCH_STEPS:
        with FlopCounterMode(display=False) as counter:
            stats = program.fit(steps)
        counts.append(counter.get_total_flops())
    low, high = TORCH_STEPS
    difference = counts[1] - counts[0]
    if difference % (high - low):
        raise CostRefused("cost_not_linear", "a step's cost varies between steps")
    step = difference // (high - low)
    return Measured(
        int(stats["n_params"]), float(step), float(counts[0] - low * step), None
    )


MEASURE = {"jax": measure_jax, "pytorch": measure_torch}


# -- The report ---------------------------------------------------------------


def _versions(backend):
    from importlib.metadata import version

    package = {"jax": "jaxlib", "pytorch": "torch"}[backend]
    return {package: version(package)}


def cost(challenge_id, strategy, *, train_cases=None, factors=None, level=0):
    """F0-F4 for one recipe on this host's image.

    The backend is the recipe's own. `train_cases` costs the recipe at a study
    TRAIN size instead of the contract's. `factors` may carry the study's
    measured `k_opt` and `k_polish` and its fitted conversions to seconds
    (`F3_seconds`, `F4_seconds`, each `{"setup_s", "per_unit_s"}`); each is
    HUMAN_INPUT until supplied. A recipe that trains nothing (no training
    program, as a nearest-neighbour recipe) costs 0.

    `level` above 0 costs the recipe under that construction level's current
    development variant (TRAINING-BUDGET-02): the program the development
    rebuild trains, never a Level 0 reading of it.
    """
    adapter = adapter_for(challenge_id)
    if level:
        programs = adapter.training_programs(
            strategy, train_cases=train_cases, level=level
        )
    else:
        programs = adapter.training_programs(strategy, train_cases=train_cases)
    backends = {program.backend for program in programs}
    if not backends <= set(adapter.backends()):
        raise CostRefused("cost_backend_unsupported", ", ".join(sorted(backends)))
    factors = dict(factors or {})
    k_opt, k_polish = factors.get("k_opt"), factors.get("k_polish")
    rows, f0, f1, f2, f4 = [], 0, 0, 0.0, 0.0
    for program in programs:
        if program.backend not in MEASURE:
            raise CostRefused("cost_backend_unsupported", program.backend)
        m = MEASURE[program.backend](program)
        members, main, polish = (
            program.members,
            program.main_steps,
            program.polish_steps,
        )
        p_b = m.parameters * program.cases_per_update
        f0 += members * (main + polish)
        f1 += members * p_b * (main + polish)
        if f2 is not None:
            f2 = (
                None
                if k_opt is None or (polish and k_polish is None)
                else f2
                + members * (k_opt * p_b * main + (k_polish or 0) * p_b * polish)
            )
        # A development recipe's recorded worst case stands in for an unset
        # k_polish (TRAINING-BUDGET-02); a measured k_polish still decides.
        k_poly = k_polish if k_polish is not None else program.polish_factor
        if f4 is not None:
            f4 = (
                None
                if polish and k_poly is None
                else f4
                + members * m.step_flops * (main + (k_poly or 0) * polish)
                + members
                * polish
                * program.polish_dense_flops_per_p2
                * m.parameters
                * m.parameters
            )
        rows.append(
            {
                "backend": program.backend,
                "members": members,
                "main_steps": main,
                "polish_steps": polish,
                "cases_per_update": program.cases_per_update,
                "parameters": m.parameters,
                "step_flops": m.step_flops,
                "outside_flops": m.outside_flops,
                "peak_memory_bytes": m.peak_memory_bytes,
            }
        )

    def seconds(value, name):
        conversion = factors.get(name)
        if value is None or conversion is None:
            return HUMAN_INPUT
        return conversion["setup_s"] + conversion["per_unit_s"] * value

    peaks = [r["peak_memory_bytes"] for r in rows if r["peak_memory_bytes"] is not None]
    return {
        "schema": SCHEMA,
        "challenge_id": challenge_id,
        "backends": sorted(backends),
        "versions": {k: v for b in sorted(backends) for k, v in _versions(b).items()},
        "programs": rows,
        "F0_steps": f0,
        "F1": f1,
        "F2": HUMAN_INPUT if f2 is None else f2,
        "F3_seconds": seconds(f2, "F3_seconds"),
        "F4_flops": HUMAN_INPUT if f4 is None else f4,
        "F4_seconds": seconds(f4, "F4_seconds"),
        "peak_memory_bytes": max(peaks) if peaks else None,
    }


def budget(adapter):
    """The contract's declared compute budget, or None while it declares none
    (then its per-setting caps are the limit)."""
    envelope = adapter.contract().document().get("envelope", {})
    return envelope.get("compute_budget")


def main(argv=None):
    """`python -m carbon.training_budget.cost --challenge ID --strategy FILE`:
    the miner's calculator, the same function the validator runs. The
    validator's figure on its pinned image is the one that decides."""
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(prog="python -m carbon.training_budget.cost")
    parser.add_argument("--challenge", required=True)
    parser.add_argument("--strategy", required=True, help="a strategy JSON file")
    parser.add_argument("--train-cases", type=int)
    parser.add_argument(
        "--level",
        type=int,
        default=0,
        help="cost under this construction level's development variant",
    )
    args = parser.parse_args(argv)
    strategy = json.loads(Path(args.strategy).read_text(encoding="utf-8"))
    try:
        # Level 0 calls the calculator exactly as before the ladder.
        ladder = {"level": args.level} if args.level else {}
        report = cost(args.challenge, strategy, train_cases=args.train_cases, **ladder)
    except CostRefused as refused:
        print(json.dumps({"refused": refused.code, "detail": str(refused)}))
        return 2
    declared = budget(adapter_for(args.challenge))
    print(
        json.dumps(
            {
                **report,
                "budget": declared,
                "budget_note": (
                    "no compute budget is declared yet: the contract's "
                    "per-setting caps are the limit"
                    if declared is None
                    else "the contract's compute budget"
                ),
                "decides": "the validator's calculation on its pinned image",
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
