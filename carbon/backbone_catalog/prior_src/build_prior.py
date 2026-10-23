"""Physics prior + learned residual, JAX build (backbone-catalog lane, 2026-10-23).

One Challenge-neutral pattern: a Challenge's public analytic model (`prior.py`, pure JAX ops, same input order and output
encoding as the interface) is the baseline; a learned model fits the residual `targets - prior(inputs)` and the product is
`prior(x) + residual(x)`. The prior is never the exam reference. Everything below is a miner setting.

configuration (all optional):
  backbone        "krr" (default, closed form) or a packet-registry JAX backbone (fit by the catalog trainer v2 on the residual)
  learning_rate   as the catalog trainer v2 (non-KRR backbones only)
  prior           "analytic" (default) | "none" (then the residual is the target itself: a plain model)
  krr             kernel ridge on the residual, a closed-form deterministic fit (Cholesky, float64):
                    kernel        rbf | matern32 | matern52           (default rbf)
                    length_scales one number or one per input         (unit-cube inputs; default DEFAULT_LENGTH)
                    ridge         added to the kernel diagonal, > 0   (default DEFAULT_RIDGE)
                    log_space     fit log(output / prior output) on the outputs the prior declares positive
                    groups        [{"outputs": [start, stop], kernel, length_scales, ridge, log_space}, ...]: separate
                                  models (e.g. a separate pressure model) over contiguous output ranges that cover every
                                  output once; a missing key takes the top-level value
train_use: for "krr" none; for another backbone as the catalog trainer v2.
The solve uses NumPy's LAPACK in float64; the build is deterministic on one host and the Validator's rebuild class decides
cross-host identity.
"""

from __future__ import annotations

import math

KERNELS = ("rbf", "matern32", "matern52")
DEFAULT_LENGTH = 1.0
DEFAULT_RIDGE = 1e-6
GROUP_KEYS = {"outputs", "kernel", "length_scales", "ridge", "log_space"}
KRR_KEYS = GROUP_KEYS - {"outputs"} | {"groups"}
CONFIG_KEYS = {"backbone", "learning_rate", "prior", "krr"}


def _only(spec, allowed, where):
    if type(spec) is not dict:
        raise ValueError(f"{where} must be an object")
    extra = set(spec) - set(allowed)
    if extra:
        raise ValueError(f"{where}: unknown key {sorted(extra)[0]}")


def _number(value, where, low=None, low_open=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{where} must be a finite number")
    if low is not None and (value <= low if low_open else value < low):
        raise ValueError(f"{where} must be {'>' if low_open else '>='} {low}")
    return float(value)


def _group_spec(top, group, n_in, n_out, positive):
    """One group's resolved settings: the group's keys over the top-level ones over the defaults."""
    spec = {
        "kernel": "rbf",
        "length_scales": DEFAULT_LENGTH,
        "ridge": DEFAULT_RIDGE,
        "log_space": False,
    }
    for source in (top, group):
        for key in ("kernel", "length_scales", "ridge", "log_space"):
            if key in source:
                spec[key] = source[key]
    if spec["kernel"] not in KERNELS:
        raise ValueError(f"krr.kernel must be one of {', '.join(KERNELS)}")
    scales = spec["length_scales"]
    scales = list(scales) if type(scales) is list else [scales] * n_in
    if len(scales) != n_in:
        raise ValueError(f"krr.length_scales must be one number or {n_in} numbers")
    spec["length_scales"] = [_number(v, "krr.length_scales", 0, True) for v in scales]
    spec["ridge"] = _number(spec["ridge"], "krr.ridge", 0, True)
    if type(spec["log_space"]) is not bool:
        raise ValueError("krr.log_space must be true or false")
    return spec


def _groups(krr, n_in, n_out, positive):
    _only(krr, KRR_KEYS, "krr")
    raw = krr.get("groups")
    if raw is None:
        raw = [{"outputs": [0, n_out]}]
    if type(raw) is not list or not raw:
        raise ValueError("krr.groups must be a non-empty list")
    groups, at = [], 0
    for index, group in enumerate(sorted(raw, key=lambda g: g.get("outputs", [0])[0] if type(g) is dict else 0)):
        _only(group, GROUP_KEYS, f"krr.groups[{index}]")
        span = group.get("outputs")
        if (
            type(span) is not list
            or len(span) != 2
            or any(type(v) is not int for v in span)
            or not 0 <= span[0] < span[1] <= n_out
        ):
            raise ValueError(f"krr.groups[{index}].outputs must be [start, stop] inside 0..{n_out}")
        if span[0] != at:
            raise ValueError(f"krr.groups must cover every output once: output {at} is {'uncovered' if span[0] > at else 'covered twice'}")
        at = span[1]
        spec = _group_spec(krr, group, n_in, n_out, positive)
        if spec["log_space"] and not all(o in positive for o in range(*span)):
            raise ValueError("krr.log_space is only offered for outputs the prior declares positive")
        groups.append((span[0], span[1], spec))
    if at != n_out:
        raise ValueError(f"krr.groups must cover every output once: output {at} is uncovered")
    return groups


def _solve_spd(matrix, rhs):
    """Solve matrix @ X = rhs for a symmetric positive definite matrix by Cholesky, in NumPy loops of elementwise products
    and pairwise sums only (no BLAS/LAPACK call), so the bytes do not depend on the thread count."""
    import numpy as np

    n = len(matrix)
    lower = np.zeros((n, n))
    for j in range(n):
        row = lower[j, :j]
        diagonal = matrix[j, j] - (row * row).sum()
        if not diagonal > 0:
            raise ValueError("krr: the kernel matrix is not positive definite; raise krr.ridge")
        lower[j, j] = math.sqrt(diagonal)
        if j + 1 < n:
            lower[j + 1 :, j] = (matrix[j + 1 :, j] - (lower[j + 1 :, :j] * row).sum(axis=1)) / lower[j, j]
    forward = np.zeros_like(rhs, dtype=np.float64)
    for i in range(n):
        forward[i] = (rhs[i] - (lower[i, :i, None] * forward[:i]).sum(axis=0)) / lower[i, i]
    solution = np.zeros_like(forward)
    for i in range(n - 1, -1, -1):
        solution[i] = (forward[i] - (lower[i + 1 :, i, None] * solution[i + 1 :]).sum(axis=0)) / lower[i, i]
    return solution


def build(train_inputs, train_targets, *, seed, configuration, train_use):
    import jax
    import jax.numpy as jnp
    import numpy as np

    from . import prior as P

    x64 = bool(jax.config.jax_enable_x64)
    if not x64 and np.asarray(train_inputs).dtype == np.float64:
        raise RuntimeError("JAX x64 must be enabled for a float64 TRAIN")
    FLOAT = jnp.float64 if x64 else jnp.float32
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be a uint32 integer")
    _only(configuration, CONFIG_KEYS, "configuration")
    x = np.asarray(train_inputs, dtype=np.float64)
    y = np.asarray(train_targets, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 2 or len(x) != len(y) or len(x) < 2 or y.shape[1] != P.N_OUT or x.shape[1] != len(P.INPUTS):
        raise ValueError("expected paired TRAIN inputs and targets of the prior's shapes")
    n_in, n_out = x.shape[1], y.shape[1]
    backbone = configuration.get("backbone", "krr")
    use_prior = configuration.get("prior", "analytic")
    if use_prior not in ("analytic", "none"):
        raise ValueError("prior must be analytic or none")

    def prior_of(inputs):
        if use_prior == "none":
            return jnp.zeros((inputs.shape[0], n_out), dtype=FLOAT)
        return P.prior(jnp.asarray(inputs, dtype=FLOAT)).astype(FLOAT)

    base = np.asarray(prior_of(jnp.asarray(x, dtype=FLOAT)), dtype=np.float64)
    residual = y - base

    if backbone != "krr":
        from . import trainer as T

        if "krr" in configuration:
            raise ValueError("krr settings need backbone krr")
        inner = T.build(
            x, residual, seed=seed,
            configuration={k: v for k, v in configuration.items() if k in ("backbone", "learning_rate")},
            train_use=train_use,
        )
        inner_apply = inner["apply"]

        def apply(params, inputs):
            inputs = jnp.asarray(inputs, dtype=FLOAT)
            return prior_of(inputs) + inner_apply(params, inputs).astype(FLOAT)

        direct = np.asarray(apply(inner["parameters"], x))
        if direct.shape != y.shape or not np.isfinite(direct).all():
            raise RuntimeError("trained prediction invalid")
        return {"framework": "jax", "apply": apply, "parameters": inner["parameters"]}

    if train_use:
        raise ValueError("train_use takes no settings with backbone krr")
    krr = dict(configuration.get("krr") or {})
    positive = tuple(getattr(P, "POSITIVE_OUTPUTS", ()))
    groups = _groups(krr, n_in, n_out, positive)
    lo = np.asarray([b[0] for b in P.INPUT_BOUNDS], dtype=np.float64)
    hi = np.asarray([b[1] for b in P.INPUT_BOUNDS], dtype=np.float64)
    unit = (x - lo) / (hi - lo)

    def kernel_np(d2, name):
        if name == "rbf":
            return np.exp(-0.5 * d2)
        r = np.sqrt(d2 + 1e-30)
        if name == "matern32":
            return (1 + math.sqrt(3) * r) * np.exp(-math.sqrt(3) * r)
        return (1 + math.sqrt(5) * r + 5.0 / 3.0 * d2) * np.exp(-math.sqrt(5) * r)

    def kernel_jx(d2, name):
        if name == "rbf":
            return jnp.exp(-0.5 * d2)
        r = jnp.sqrt(d2 + 1e-30)
        if name == "matern32":
            return (1 + math.sqrt(3) * r) * jnp.exp(-math.sqrt(3) * r)
        return (1 + math.sqrt(5) * r + 5.0 / 3.0 * d2) * jnp.exp(-math.sqrt(5) * r)

    def softplus_np(v):
        return np.log1p(np.exp(-np.abs(v))) + np.maximum(v, 0.0)

    def softplus_jx(v):
        return jnp.log1p(jnp.exp(-jnp.abs(v))) + jnp.maximum(v, 0.0)

    params, plan = [jnp.asarray(unit, dtype=FLOAT)], []
    for start, stop, spec in groups:
        inv_ls = 1.0 / np.asarray(spec["length_scales"], dtype=np.float64)
        diff = (unit[:, None, :] - unit[None, :, :]) * inv_ls
        gram = kernel_np((diff * diff).sum(-1), spec["kernel"])
        target = residual[:, start:stop].copy()
        if spec["log_space"]:
            true_pos, prior_pos = softplus_np(y[:, start:stop]), softplus_np(base[:, start:stop])
            if not (np.all(true_pos > 0) and np.all(prior_pos > 0)):
                raise ValueError("log_space needs positive values")
            target = np.log(true_pos) - np.log(prior_pos)
        mean = target.mean(axis=0)
        alpha = _solve_spd(gram + spec["ridge"] * np.eye(len(x)), target - mean)
        params += [jnp.asarray(alpha, dtype=FLOAT), jnp.asarray(mean, dtype=FLOAT), jnp.asarray(inv_ls, dtype=FLOAT)]
        plan.append((start, stop, spec["kernel"], spec["log_space"]))

    lo_j, span_j = jnp.asarray(lo, dtype=FLOAT), jnp.asarray(hi - lo, dtype=FLOAT)

    def apply(p, inputs):
        if len(p) != 1 + 3 * len(plan):
            raise ValueError("parameter count differs")
        inputs = jnp.asarray(inputs, dtype=FLOAT)
        z = (inputs - lo_j) / span_j
        pri = prior_of(inputs)
        parts = []
        for k, (start, stop, name, logged) in enumerate(plan):
            alpha, mean, inv_ls = p[1 + 3 * k : 4 + 3 * k]
            diff = (z[:, None, :] - p[0][None, :, :]) * inv_ls
            part = kernel_jx((diff * diff).sum(axis=-1), name) @ alpha + mean
            if logged:
                part = P.encode_positive(softplus_jx(pri[:, start:stop]) * jnp.exp(part))
            else:
                part = pri[:, start:stop] + part
            parts.append(part)
        return jnp.concatenate(parts, axis=1) if len(parts) > 1 else parts[0]

    direct = np.asarray(apply(params, x))
    if direct.shape != y.shape or direct.dtype != np.dtype(FLOAT) or not np.isfinite(direct).all():
        raise RuntimeError("trained prediction invalid")
    return {"framework": "jax", "apply": apply, "parameters": params}
