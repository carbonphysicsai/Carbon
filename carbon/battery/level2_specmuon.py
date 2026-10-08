"""`specmuon-carbon-v1`: Carbon's interpretation of SpecMuon for battery's
Level 2 (development only).

BATTERY-CLIMB-1-REVIEW and the Test Lead's rulings of 2026-10-07. This is a
named, versioned Carbon interpretation of SpecMuon (arXiv 2602.16167v1),
**never claimed to be the paper's exact algorithm**.

**The interpretation.**
- **Base.** The step is battery's base Muon (`optax.contrib.muon` as
  `training.optimizer` builds it), unchanged, with its momentum where it is
  (μ = the recipe's beta1).
- **Correction.** For each matrix (2-D) weight W, Ĝ = G / (‖G‖_F + ε) is
  decomposed by SVD. Along its top k_r = min(8, rank) singular directions
  u_i v_iᵀ, Muon's own component c_i = u_iᵀ O v_i of the step O is rescaled by
  the mode's RSAV factor r̃_i / E:

      O_spec = O + Σ_i (r̃_i / E − 1) c_i u_i v_iᵀ.

  The remaining modes are Muon's own.
- **RSAV.** E = √(f(Θ) + κ), h_i = η_sav / σ_i, g_i = σ_i / E, and
  r̃_i = r_i / (1 + (h_i / 2) g_i²). After the step, with E⁺ = √(f(Θ⁺) + κ) from
  one extra forward pass on the same minibatch:
  - D_i = h_i⁻¹ ‖ΔW_i‖², the SAV-standard dissipation, ΔW_i being the step
    along mode i;
  - ξ_i = max{0, (−b − √(b² − 4ac)) / 2a}, with
    a = (r̃_i − E⁺)², b = 2E⁺(r̃_i − E⁺) and c = f(Θ⁺) + κ − r̃_i² − ψ D_i;
  - r_i ← ξ_i r̃_i + (1 − ξ_i) E⁺.

  The first step sets r_i = E.
- **Fixed Carbon constants:** κ = 1e-8, k_r = min(8, rank), η_sav = 0.2,
  ψ = 0.95.
- **Non-matrix parameters** keep base Muon's handling.

**Departures from Algorithm 1**, recorded:
- **Momentum (the main one).** Momentum stays where base Muon has it, before
  orthogonalization, rather than on the RSAV output (B ← μB + O). That keeps
  the RSAV-off step base Muon's byte for byte.
- **Basis.** The rescaled directions are those of the normalized gradient,
  applied to Muon's Newton–Schulz output rather than to an exact-SVD
  orthogonalization.
- **D** is the SAV-standard term, our reading of the paper's undefined D.

**RSAV off** (`rsav=False`) returns base Muon's update and state unchanged.

Relative imports only: this file is staged into the isolated worker's
`carbon_battery_lab` package beside `training.py`.
"""

from __future__ import annotations

INTERPRETATION = "specmuon-carbon-v1"
KAPPA = 1e-8
TOP_MODES = 8
ETA_SAV = 0.2
PSI = 0.95
EPS = 1e-12


def spectral(jax, optax, base, *, rsav=True):
    """Wrap `base` (battery's Muon) with the mode-wise RSAV correction.
    `update(g, state, params, value=, value_fn=)` needs the loss at `params`
    and `value_fn` for the extra forward pass on the same minibatch."""
    jnp = jax.numpy

    def is_matrix(leaf):
        return getattr(leaf, "ndim", 0) == 2

    def init(params):
        def modes(leaf):
            if not is_matrix(leaf):
                return jnp.zeros((0,), leaf.dtype)
            return jnp.full((min(TOP_MODES, *leaf.shape),), jnp.nan, leaf.dtype)

        return {"base": base.init(params), "r": jax.tree_util.tree_map(modes, params)}

    def update(updates, state, params=None, *, value=None, value_fn=None, **extra):
        step, base_state = base.update(updates, state["base"], params)
        if not rsav:
            return step, {"base": base_state, "r": state["r"]}
        energy = jnp.sqrt(value + KAPPA)

        def correct(g, o, r):
            if not is_matrix(g):
                return o, None
            k = r.shape[0]
            normalized = g / (jnp.linalg.norm(g) + EPS)
            u, s, vt = jnp.linalg.svd(normalized, full_matrices=False)
            u, s, vt = u[:, :k], s[:k], vt[:k]
            r = jnp.where(jnp.isnan(r), energy, r)
            h = ETA_SAV / jnp.maximum(s, EPS)
            predicted = r / (1.0 + 0.5 * h * (s / energy) ** 2)
            along = jnp.einsum("ik,ij,kj->k", u, o, vt)
            factor = predicted / energy
            corrected = o + jnp.einsum("k,ik,kj->ij", (factor - 1.0) * along, u, vt)
            return corrected, (predicted, h, factor * along)

        flat_g, tree = jax.tree_util.tree_flatten(updates)
        flat_o = tree.flatten_up_to(step)
        flat_r = tree.flatten_up_to(state["r"])
        results = [correct(g, o, r) for g, o, r in zip(flat_g, flat_o, flat_r)]
        new_step = tree.unflatten([o for o, _ in results])
        after = value_fn(optax.apply_updates(params, new_step))
        energy_after = jnp.sqrt(after + KAPPA)
        new_r = []
        for (_, modes), r in zip(results, flat_r):
            if modes is None:
                new_r.append(r)
                continue
            predicted, h, delta = modes
            dissipation = delta**2 / h
            a = (predicted - energy_after) ** 2
            b = 2.0 * energy_after * (predicted - energy_after)
            c = after + KAPPA - predicted**2 - PSI * dissipation
            disc = b**2 - 4.0 * a * c
            root = (-b - jnp.sqrt(jnp.maximum(disc, 0.0))) / jnp.where(
                a > 0, 2.0 * a, 1.0
            )
            xi = jnp.where((a > 0) & (disc >= 0), jnp.clip(root, 0.0, 1.0), 0.0)
            new_r.append(xi * predicted + (1.0 - xi) * energy_after)
        return new_step, {"base": base_state, "r": tree.unflatten(new_r)}

    return optax.GradientTransformationExtraArgs(init, update)
