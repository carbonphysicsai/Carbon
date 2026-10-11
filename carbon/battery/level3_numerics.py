"""Battery's Level-3 training-time numerics: the polish stage's quasi-Newton
routine and line search (development only).

BATTERY-CLIMB-1-REVIEW (the Test Lead's F1 review, 2026-10-07). Level 3 is a
declarative menu (OWNER-GRAPHITE-DEV-LEVELS-01 F2): a recipe names one routine
and one line search; Carbon runs them here. Nothing a recipe supplies is
executed.

- **Routines.** `lbfgs` is today's polish (`training.polish`, optax's L-BFGS).
  `bfgs`, `ssbfgs` and `ssbroyden` hold a dense inverse Hessian H and update
  it with the inverse Broyden-class formula

      H+ = τH − τHy(τHy)ᵀ / (yᵀτHy) + ssᵀ/(sᵀy) + φ (yᵀτHy) v vᵀ,
      v  = s/(sᵀy) − τHy/(yᵀτHy),

  with φ = 1 the BFGS member and φ = ½ the midpoint of the restricted class;
  τ = 1 for `bfgs` and the Oren-Luenberger self-scaling τ = sᵀy / yᵀHy for
  `ssbfgs` and `ssbroyden`. An update whose curvature sᵀy is not positive is
  skipped, so H stays positive definite.
- **Line searches.** `strong_wolfe` is optax's zoom search (today's), and
  `backtracking` optax's Armijo backtracking, each with a fixed cap on its
  steps (`LINE_SEARCH_STEPS`). `none` takes the unit quasi-Newton step: the
  miner's own risk, bounded by the step budget.
- **Default.** `lbfgs` with `strong_wolfe` calls `training.polish` itself, so
  the default is today's polish exactly.

Relative imports only: this file is staged into the isolated worker's
`carbon_battery_lab` package beside `training.py`.
"""

from __future__ import annotations

ROUTINES = ("lbfgs", "bfgs", "ssbfgs", "ssbroyden")
SEARCHES = ("strong_wolfe", "backtracking", "none")
DEFAULT = {"routine": "lbfgs", "line_search": "strong_wolfe"}
#: The fixed cap on each line search's steps per polish step (one loss and
#: gradient evaluation each), recorded so the cost calculator's worst case
#: counts it: optax's zoom default (20) and its backtracking default (15).
LINE_SEARCH_STEPS = {"strong_wolfe": 20, "backtracking": 15, "none": 0}
#: The Broyden-class parameter φ and whether τ self-scales, per dense routine.
BROYDEN = {"bfgs": (1.0, False), "ssbfgs": (1.0, True), "ssbroyden": (0.5, True)}
#: The routines that hold a dense p × p inverse Hessian.
DENSE = frozenset(BROYDEN)


def evaluations_per_step(line_search):
    """The worst-case loss-and-gradient evaluations of one polish step."""
    return 1 + LINE_SEARCH_STEPS[line_search]


def hessian_bytes(parameters, itemsize):
    """A dense routine's inverse Hessian: p² values."""
    return parameters * parameters * itemsize


def scale_by_broyden(jax, optax, phi, self_scaled):
    """The search direction −Hg of a dense inverse-Hessian routine."""
    jnp = jax.numpy
    from jax.flatten_util import ravel_pytree

    def init(params):
        flat, _ = ravel_pytree(params)
        return {
            "inverse_hessian": jnp.eye(flat.size, dtype=flat.dtype),
            "previous_params": flat,
            "previous_grad": jnp.zeros_like(flat),
            "count": jnp.zeros([], jnp.int32),
        }

    def update(updates, state, params=None):
        g, unravel = ravel_pytree(updates)
        x, _ = ravel_pytree(params)
        h = state["inverse_hessian"]
        s, y = x - state["previous_params"], g - state["previous_grad"]
        sy = s @ y
        hy = h @ y
        yhy = y @ hy
        scale = jnp.where(yhy > 0, sy / jnp.where(yhy > 0, yhy, 1.0), 1.0)
        tau = scale if self_scaled else jnp.ones_like(sy)
        scaled, thy, ythy = tau * h, tau * hy, tau * yhy
        safe_sy = jnp.where(sy > 0, sy, 1.0)
        safe_ythy = jnp.where(ythy > 0, ythy, 1.0)
        v = s / safe_sy - thy / safe_ythy
        updated = (
            scaled
            - jnp.outer(thy, thy) / safe_ythy
            + jnp.outer(s, s) / safe_sy
            + phi * ythy * jnp.outer(v, v)
        )
        ok = (
            (state["count"] > 0)
            & (sy > 0)
            & (ythy > 0)
            & jnp.all(jnp.isfinite(updated))
        )
        h = jnp.where(ok, updated, h)
        direction = -(h @ g)
        return unravel(direction), {
            "inverse_hessian": h,
            "previous_params": x,
            "previous_grad": g,
            "count": state["count"] + 1,
        }

    return optax.GradientTransformation(init, update)


def line_search(optax, name):
    if name == "strong_wolfe":
        return optax.scale_by_zoom_linesearch(
            max_linesearch_steps=LINE_SEARCH_STEPS[name], initial_guess_strategy="one"
        )
    if name == "backtracking":
        return optax.scale_by_backtracking_linesearch(
            max_backtracking_steps=LINE_SEARCH_STEPS[name], store_grad=True
        )
    if name == "none":
        return None
    raise ValueError("unknown line search " + str(name))


def transform(jax, optax, routine, search):
    """The optax transformation for one routine and line search."""
    found = line_search(optax, search)
    if routine == "lbfgs":
        return optax.lbfgs(linesearch=found)
    if routine not in BROYDEN:
        raise ValueError("unknown quasi-Newton routine " + str(routine))
    phi, self_scaled = BROYDEN[routine]
    parts = [scale_by_broyden(jax, optax, phi, self_scaled)]
    return optax.chain(*parts, *([found] if found is not None else []))


def polish(jax, optax, params, objective, count, numerics):
    """`count` full-batch polish steps with the recipe's routine and line
    search; the default is `training.polish` itself."""
    routine, search = numerics["routine"], numerics["line_search"]
    if {"routine": routine, "line_search": search} == DEFAULT:
        from .training import polish as level0

        return level0(jax, optax, params, objective, count)
    tx = transform(jax, optax, routine, search)
    if search == "none":

        def value_and_grad(p, state):
            return jax.value_and_grad(objective)(p)

    else:
        value_and_grad = optax.value_and_grad_from_state(objective)

    @jax.jit
    def run(p):
        def body(carry, _):
            p, state = carry
            value, g = value_and_grad(p, state=state)
            updates, state = tx.update(
                g, state, p, value=value, grad=g, value_fn=objective
            )
            return (optax.apply_updates(p, updates), state), None

        (p, _), _ = jax.lax.scan(body, (p, tx.init(p)), None, length=count)
        return p

    return run(params)
