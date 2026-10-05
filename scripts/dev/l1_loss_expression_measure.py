"""L1 loss-expression measurements (CPU only). Scratch evidence for the review packet.

Modes:
  python measure.py main OUT.json        determinism, numpy-vs-jax, non-finite rates, cost, probes
  python measure.py fingerprint          sha256 of jax f32 values+grads of the sampled set
  python measure.py fit                  sha256 of params after short jitted fits

The "wide" operation set below is a prototype of the proposed v1 surface. It lives
only in this script; nothing in the repository is changed.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import random
import statistics
import sys
import time

os.environ.setdefault("JAX_PLATFORMS", "cpu")

import numpy as np

from carbon.battery import level1_draft as l1
from carbon.reconstruction import loss_expressions as le

GROUPS = ("voltage", "temperature", "plating", "capacity")
GROUP_TERMS = tuple(f"sq_error_{g}" for g in GROUPS) + tuple(
    f"target_energy_{g}" for g in GROUPS
)
CASE_TERMS = tuple(l1.TERMS) + GROUP_TERMS
TIME_TERMS = ("err_sq_t", "time_t", "time_rev_t")
OVER = ("both", "voltage", "temperature")
SORT = {**{t: "case" for t in CASE_TERMS}, **{t: "time" for t in TIME_TERMS}}
VARIADIC = ("add", "max", "min")
BINARY = ("mul", "div")
UNARY = ("log1p", "sqrt")
PARAM = {
    "scale": "by",
    "pow": "exponent",
    "cap": "at",
    "excess": "over",
    "expm1": "cap",
}
REDUCE = ("mean_t", "max_t")
COMMUTATIVE = ("add", "mul", "max", "min")
RAW = ("sub", "neg", "exp")  # measured for the record; not proposed

PROPOSED = {
    "name": "battery-l1-loss-expressions-v1",
    "terms": list(CASE_TERMS + TIME_TERMS),
    "operations": list(VARIADIC + BINARY + UNARY + tuple(PARAM) + REDUCE),
    "max_depth": 24,
    "max_nodes": 256,
    "max_arity": 16,
    "ranges": {
        "by": [0.0, 100.0],
        "exponent": [0.25, 4.0],
        "at": [0.0, 1.0e4],
        "over": [0.0, 1.0e4],
        "cap": [0.0, 16.0],
    },
    "epsilon": 1e-6,
}


class Refused(ValueError):
    pass


def _num(v):
    return type(v) in (int, float) and math.isfinite(v)


def canonical(node, opset, depth=1, count=0):
    """(canonical node, sort, count); mirrors loss_expressions._canonical."""
    if depth > opset["max_depth"]:
        raise Refused("too_deep")
    count += 1
    if count > opset["max_nodes"]:
        raise Refused("too_many_nodes")
    if type(node) is not dict:
        raise Refused("node_is_an_object")
    if "term" in node:
        if set(node) != {"term"} or node["term"] not in opset["terms"]:
            raise Refused("term")
        return {"term": node["term"]}, SORT[node["term"]], count
    op = node.get("op")
    if op not in opset["operations"]:
        raise Refused("operation_not_in_the_set")
    if op in VARIADIC or op in BINARY or op in ("sub",):
        args = node["args"]
        n = len(args)
        if not (n == 2 if op not in VARIADIC else 2 <= n <= opset["max_arity"]):
            raise Refused("arity")
        out, sorts = [], set()
        for a in args:
            c, s, count = canonical(a, opset, depth + 1, count)
            out.append(c)
            sorts.add(s)
        if len(sorts) != 1:
            raise Refused("mixed_sorts")
        if op in COMMUTATIVE:
            out.sort(key=lambda c: json.dumps(c, sort_keys=True))
        return {"op": op, "args": out}, sorts.pop(), count
    if op in REDUCE:
        if set(node) != {"op", "over", "arg"} or node["over"] not in OVER:
            raise Refused("reduction_fields")
        c, s, count = canonical(node["arg"], opset, depth + 1, count)
        if s != "time":
            raise Refused("reduce_needs_time")
        return {"op": op, "over": node["over"], "arg": c}, "case", count
    if op in UNARY or op in ("neg", "exp"):
        c, s, count = canonical(node["arg"], opset, depth + 1, count)
        return {"op": op, "arg": c}, s, count
    field = PARAM[op]
    v = node[field]
    lo, hi = opset["ranges"][field]
    if not _num(v) or not lo <= v <= hi:
        raise Refused(field + "_outside_bounds")
    c, s, count = canonical(node["arg"], opset, depth + 1, count)
    return {"op": op, field: float(v) + 0.0, "arg": c}, s, count


def compile_wide(node, opset):
    c, s, _ = canonical(node, opset)
    if s != "case":
        raise Refused("loss_is_per_case")
    return c


def evaluate(expr, case_terms, errors, xp, eps):
    """Per-case loss. `errors` are the per-trajectory error arrays (cases x times)."""

    def ev(node, j=None):
        if "term" in node:
            name = node["term"]
            if SORT[name] == "case":
                return case_terms[name]
            e = errors[j]
            if name == "err_sq_t":
                return e**2
            n = e.shape[1]
            line = (0.0, 1.0) if name == "time_t" else (1.0, 0.0)
            return xp.asarray(np.linspace(*line, n), dtype=e.dtype)[None, :]
        op = node["op"]
        if op in REDUCE:
            total = None
            over = {"both": (0, 1), "voltage": (0,), "temperature": (1,)}[node["over"]]
            for k in over:
                v = xp.broadcast_to(ev(node["arg"], k), errors[k].shape)
                r = xp.mean(v, axis=1) if op == "mean_t" else xp.max(v, axis=1)
                total = r if total is None else total + r
            return total
        if op in VARIADIC:
            vals = [ev(a, j) for a in node["args"]]
            out = vals[0]
            for v in vals[1:]:
                if op == "add":
                    out = out + v
                elif op == "max":
                    out = xp.maximum(out, v)
                else:
                    out = xp.minimum(out, v)
            return out
        if op == "mul":
            return ev(node["args"][0], j) * ev(node["args"][1], j)
        if op == "div":
            return ev(node["args"][0], j) / (ev(node["args"][1], j) + eps)
        if op == "sub":
            return ev(node["args"][0], j) - ev(node["args"][1], j)
        if op == "neg":
            return -ev(node["arg"], j)
        if op == "exp":
            return xp.exp(ev(node["arg"], j))
        if op == "log1p":
            return xp.log1p(ev(node["arg"], j))
        if op == "sqrt":
            return xp.sqrt(ev(node["arg"], j) + eps)
        a = ev(node["arg"], j)
        if op == "scale":
            return node["by"] * a
        if op == "pow":
            return (a + eps) ** node["exponent"]
        if op == "cap":
            return xp.minimum(a, node["at"])
        if op == "excess":
            return xp.maximum(a - node["over"], 0.0)
        return xp.expm1(xp.minimum(a, node["cap"]))  # expm1

    return ev(expr)


# --- random expressions -------------------------------------------------------------
def _const(rng, lo, hi):
    r = rng.random()
    if r < 0.15:
        return float(lo)
    if r < 0.3:
        return float(hi)
    if lo > 0 and hi / max(lo, 1e-300) > 100:
        return float(math.exp(rng.uniform(math.log(lo), math.log(hi))))
    if lo == 0 and hi > 100:
        return float(10 ** rng.uniform(-3, math.log10(hi)))
    return float(rng.uniform(lo, hi))


def generate(rng, opset, sort="case", depth=1, budget=None, ops=None):
    """A random well-sorted expression; returns (node, nodes used)."""
    ops = ops or opset["operations"]
    budget = opset["max_nodes"] if budget is None else budget
    names = [t for t in opset["terms"] if SORT[t] == sort]
    terminal = depth >= opset["max_depth"] or budget <= 1 or rng.random() < 0.12
    if terminal:
        return {"term": rng.choice(names)}, 1
    choices = [o for o in ops if o != "sub" or budget >= 3]
    if sort == "time":
        choices = [o for o in choices if o not in REDUCE]
    if sort == "case" and "mean_t" in ops and depth > 1 and rng.random() < 0.25:
        choices = [o for o in choices if o in REDUCE] or choices
    op = rng.choice(choices)
    budget -= 1
    if op in VARIADIC or op in BINARY or op == "sub":
        n = 2 if op not in VARIADIC else rng.randint(2, min(opset["max_arity"], 4))
        n = max(2, min(n, budget))
        if budget < 2:
            return {"term": rng.choice(names)}, 1
        args, used = [], 1
        share = max(1, budget // n)
        for i in range(n):
            remaining = budget - (used - 1) - (n - i - 1)
            a, u = generate(rng, opset, sort, depth + 1, min(share, remaining), ops)
            args.append(a)
            used += u
        return {"op": op, "args": args}, used
    if op in REDUCE:
        a, u = generate(rng, opset, "time", depth + 1, budget, ops)
        return {"op": op, "over": rng.choice(OVER), "arg": a}, u + 1
    if op in UNARY or op in ("neg", "exp"):
        a, u = generate(rng, opset, sort, depth + 1, budget, ops)
        return {"op": op, "arg": a}, u + 1
    field = PARAM[op]
    lo, hi = opset["ranges"][field]
    a, u = generate(rng, opset, sort, depth + 1, budget, ops)
    return {"op": op, field: _const(rng, lo, hi), "arg": a}, u + 1


def chain(rng, opset, depth):
    """A spine of unary/param ops reaching exactly `depth` (worst-case nesting)."""
    node = {"term": rng.choice(CASE_TERMS)}
    for _ in range(depth - 1):
        op = rng.choice(["pow", "scale", "sqrt", "log1p", "expm1", "cap", "excess"])
        if op in PARAM:
            lo, hi = opset["ranges"][PARAM[op]]
            node = {"op": op, PARAM[op]: _const(rng, lo, hi), "arg": node}
        else:
            node = {"op": op, "arg": node}
    return node


def stats(node):
    if "term" in node:
        return 1, 1
    kids = node.get("args") or [node["arg"]]
    s = [stats(k) for k in kids]
    return 1 + max(d for d, _ in s), 1 + sum(n for _, n in s)


def sample(opset, count, seed, ops=None):
    rng = random.Random(seed)
    out = []
    while len(out) < count:
        if len(out) % 5 == 4:
            node = chain(rng, opset, opset["max_depth"])
        else:
            node, _ = generate(rng, opset, ops=ops)
        try:
            out.append(compile_wide(node, opset))
        except Refused:
            continue
    return out


# --- battery-shaped data --------------------------------------------------------------
NV, NT, K, CASES = 121, 120, 4, 400
DIMS = NV + NT + 1 + K


def group_weights():
    return np.concatenate(
        [np.full(NV, 1 / NV), np.full(NT, 1 / NT), [1.0], np.full(K, 1 / K)]
    )


def trajectory(z):
    return z[:, :NV], z[:, NV : NV + NT]


REGIMES = {
    "perfect": 0.0,
    "near": 0.01,
    "typical": 0.3,
    "init": 1.0,
    "large": 30.0,
}


def regime_arrays(name, seed=11):
    rng = np.random.RandomState(seed)
    zt = rng.normal(size=(CASES, DIMS))
    if name == "init":
        zhat = rng.normal(size=(CASES, DIMS))
    else:
        zhat = zt + REGIMES[name] * rng.normal(size=(CASES, DIMS))
    return zhat, zt, group_weights()


SLICES = {
    "voltage": slice(0, NV),
    "temperature": slice(NV, NV + NT),
    "plating": slice(NV + NT, NV + NT + 1),
    "capacity": slice(NV + NT + 1, DIMS),
}


def term_arrays(xp, zhat, zt, gw):
    case = dict(l1.terms(xp, zhat, zt, gw, trajectory))
    for g, s in SLICES.items():
        case[f"sq_error_{g}"] = xp.sum(
            (zhat[:, s] - zt[:, s]) ** 2 * gw[None, s], axis=1
        )
        case[f"target_energy_{g}"] = xp.sum(zt[:, s] ** 2 * gw[None, s], axis=1)
    errors = [a - b for a, b in zip(trajectory(zhat), trajectory(zt))]
    return case, errors


# --- jax helpers -----------------------------------------------------------------------
def jax_fns(expr, eps):
    import jax
    import jax.numpy as jnp

    def per_case(zhat, zt, gw):
        case, errors = term_arrays(jnp, zhat, zt, gw)
        return evaluate(expr, case, errors, jnp, eps)

    def mean_loss(zhat, zt, gw):
        return jnp.mean(per_case(zhat, zt, gw))

    return jax.jit(per_case), jax.jit(jax.value_and_grad(mean_loss)), per_case


def np_values(expr, eps, zhat, zt, gw, dtype):
    zhat, zt, gw = (np.asarray(a, dtype) for a in (zhat, zt, gw))
    case, errors = term_arrays(np, zhat, zt, gw)
    with np.errstate(all="ignore"):
        return np.asarray(evaluate(expr, case, errors, np, eps))


def compare(a, b):
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    fa, fb = np.isfinite(a), np.isfinite(b)
    same_finite = bool((fa == fb).all())
    both = fa & fb
    bit = bool(np.array_equal(a, b, equal_nan=True))
    rel = 0.0
    if both.any():
        d = np.abs(a[both] - b[both]) / np.maximum(np.abs(a[both]), 1e-30)
        rel = float(d.max())
    return bit, rel, same_finite


# --- modes ------------------------------------------------------------------------------
def sets():
    draft = {
        "name": "battery-level1-draft (GA-D6)",
        "terms": list(l1.TERMS),
        "operations": list(le.OPERATIONS),
        "max_depth": 4,
        "max_nodes": 16,
        "max_arity": 8,
        "ranges": {
            "by": [0.0, 10.0],
            "exponent": [0.5, 2.0],
            "at": [0, 0],
            "over": [0, 0],
            "cap": [0, 0],
        },
        "epsilon": 1e-6,
    }
    raw = dict(PROPOSED, name="proposed + raw sub/neg/exp (not proposed)")
    raw["operations"] = PROPOSED["operations"] + list(RAW)
    return draft, PROPOSED, raw


def nonfinite_and_numerics(opset, exprs):
    import jax

    out = {}
    eps = opset["epsilon"]
    agreement = {
        "np32_vs_jax32_bit": 0,
        "np64_vs_jax64_bit": 0,
        "jit_vs_jit_bit": 0,
        "eager_vs_jit_bit": 0,
        "finite_pattern_mismatch_32": 0,
        "finite_pattern_mismatch_64": 0,
        "n": 0,
    }
    rel32, rel64 = [], []
    rates = {
        r: {
            "loss_nonfinite_f32": 0,
            "grad_nonfinite_f32": 0,
            "loss_nonfinite_f64": 0,
            "grad_nonfinite_f64": 0,
            "negative_case_loss": 0,
            "max_abs_grad_f32": 0.0,
        }
        for r in REGIMES
    }
    data = {r: regime_arrays(r) for r in REGIMES}
    for expr in exprs:
        values, vg, eager = jax_fns(expr, eps)
        values64, vg64, _ = jax_fns(expr, eps)
        for r in REGIMES:
            zhat, zt, gw = data[r]
            f32 = [np.asarray(a, np.float32) for a in (zhat, zt, gw)]
            v32 = np.asarray(values(*f32))
            loss32, g32 = vg(*f32)
            g32 = np.asarray(g32)
            with jax.enable_x64(True):
                f64 = [np.asarray(a, np.float64) for a in (zhat, zt, gw)]
                v64 = np.asarray(values64(*f64))
                loss64, g64 = vg64(*f64)
                g64 = np.asarray(g64)
            rr = rates[r]
            rr["loss_nonfinite_f32"] += not np.isfinite(float(loss32))
            rr["grad_nonfinite_f32"] += not np.isfinite(g32).all()
            rr["loss_nonfinite_f64"] += not np.isfinite(float(loss64))
            rr["grad_nonfinite_f64"] += not np.isfinite(g64).all()
            rr["negative_case_loss"] += bool((v64 < 0).any())
            finite = g32[np.isfinite(g32)]
            if finite.size:
                rr["max_abs_grad_f32"] = max(
                    rr["max_abs_grad_f32"], float(np.abs(finite).max())
                )
            if r in ("typical", "init"):
                agreement["n"] += 1
                n32 = np_values(expr, eps, zhat, zt, gw, np.float32)
                n64 = np_values(expr, eps, zhat, zt, gw, np.float64)
                b, rel, same = compare(n32, v32)
                agreement["np32_vs_jax32_bit"] += b
                agreement["finite_pattern_mismatch_32"] += not same
                rel32.append(rel)
                b, rel, same = compare(n64, v64)
                agreement["np64_vs_jax64_bit"] += b
                agreement["finite_pattern_mismatch_64"] += not same
                rel64.append(rel)
                again = np.asarray(values(*f32))
                agreement["jit_vs_jit_bit"] += bool(
                    np.array_equal(again, v32, equal_nan=True)
                )
                e = np.asarray(eager(*[jax.numpy.asarray(a) for a in f32]))
                agreement["eager_vs_jit_bit"] += bool(
                    np.array_equal(e, v32, equal_nan=True)
                )
    out["rates_per_regime"] = rates
    out["agreement"] = agreement
    out["np32_vs_jax32_max_rel"] = max(rel32) if rel32 else None
    out["np32_vs_jax32_median_rel"] = statistics.median(rel32) if rel32 else None
    out["np64_vs_jax64_max_rel"] = max(rel64) if rel64 else None
    out["np64_vs_jax64_median_rel"] = statistics.median(rel64) if rel64 else None
    out["count"] = len(exprs)
    depths = [stats(e) for e in exprs]
    out["depth_max"] = max(d for d, _ in depths)
    out["nodes_max"] = max(n for _, n in depths)
    out["nodes_median"] = statistics.median(n for _, n in depths)
    return out


def mlp_loss_fn(expr, eps, width=256, depth=3):
    import jax
    import jax.numpy as jnp

    sizes = [4] + [width] * depth + [DIMS]

    def init(key):
        params = []
        for a, b in itertools.pairwise(sizes):
            key, k = jax.random.split(key)
            params.append(
                (
                    jax.random.normal(k, (a, b), jnp.float32) * np.sqrt(2.0 / a),
                    jnp.zeros((b,), jnp.float32),
                )
            )
        return params

    def apply(params, x):
        h = x
        for w, b in params[:-1]:
            h = jax.nn.gelu(h @ w + b)
        w, b = params[-1]
        return h @ w + b

    def loss(params, x, zt, gw):
        case, errors = term_arrays(jnp, apply(params, x), zt, gw)
        return jnp.mean(evaluate(expr, case, errors, jnp, eps))

    return init, loss


def cost(opset_base):
    import jax

    rng = np.random.RandomState(3)
    x = jax.numpy.asarray(rng.uniform(size=(CASES, 4)), jax.numpy.float32)
    zt = jax.numpy.asarray(rng.normal(size=(CASES, DIMS)), jax.numpy.float32)
    gw = jax.numpy.asarray(group_weights(), jax.numpy.float32)
    menu = l1.menu_expression(
        {
            "relative_loss": True,
            "time_weighting": "late",
            "h1_weight": 1.0,
            "h2_weight": 0.5,
            "spectral_weight": 1.0,
        }
    )
    rows = []
    cases = [("level0_menu", 0, 0, [compile_wide(menu, opset_base)])]
    for depth, nodes in ((4, 16), (8, 32), (16, 64), (16, 128), (24, 256), (32, 512)):
        o = dict(opset_base, max_depth=depth, max_nodes=nodes, max_arity=16)
        ex = [e for e in sample(o, 40, 100 + nodes) if stats(e)[1] >= nodes * 0.5][:3]
        if not ex:
            ex = sample(o, 3, 200 + nodes)
        cases.append((f"depth<={depth},nodes<={nodes}", depth, nodes, ex))
    for label, depth, nodes, exprs in cases:
        compile_s, step_ms, actual = [], [], []
        for expr in exprs:
            init, loss = mlp_loss_fn(expr, opset_base["epsilon"])
            params = init(jax.random.PRNGKey(0))
            g = jax.jit(jax.value_and_grad(loss))
            t0 = time.perf_counter()
            jax.block_until_ready(g(params, x, zt, gw))
            compile_s.append(time.perf_counter() - t0)
            times = []
            for _ in range(20):
                t0 = time.perf_counter()
                jax.block_until_ready(g(params, x, zt, gw))
                times.append(time.perf_counter() - t0)
            step_ms.append(1000 * statistics.median(times))
            actual.append(stats(expr))
        rows.append(
            {
                "case": label,
                "actual_depth_nodes": actual,
                "compile_s_max": max(compile_s),
                "step_ms_median": statistics.median(step_ms),
                "step_ms_max": max(step_ms),
            }
        )
    return rows


def probes():
    """Edge inputs to the shipped module (carbon/reconstruction/loss_expressions.py)."""
    ops = l1.OPERATIONS
    out = {}

    def attempt(label, fn):
        try:
            r = fn()
            out[label] = {"result": "accepted", "detail": r}
        except le.ExpressionRefused as e:
            out[label] = {"result": "ExpressionRefused", "code": e.code}
        except Exception as e:  # noqa: BLE001
            out[label] = {
                "result": "UNTYPED " + type(e).__name__,
                "detail": str(e)[:120],
            }

    pos = le.compile_expression(
        {"op": "scale", "by": 0.0, "arg": {"term": "sq_error"}}, ops
    )
    attempt(
        "scale_by_negative_zero",
        lambda: {
            "accepted_digest_differs_from_+0.0": le.compile_expression(
                {"op": "scale", "by": -0.0, "arg": {"term": "sq_error"}}, ops
            ).digest
            != pos.digest
        },
    )
    attempt(
        "integer_constant_10**400",
        lambda: (
            le.compile_expression(
                {"op": "scale", "by": 10**400, "arg": {"term": "sq_error"}}, ops
            ).digest
        ),
    )
    deep = '{"op":"sqrt","arg":' * 200000 + '{"term":"sq_error"}' + "}" * 200000
    body = json.dumps(
        {"schema": le.SCHEMA, "operation_set": ops.digest, "expression": None}
    )
    body = body.replace("null", deep).encode()
    attempt("from_bytes_200000_deep_json", lambda: le.from_bytes(body, ops).digest)
    nested = {"term": "sq_error"}
    for _ in range(5000):
        nested = {"op": "sqrt", "arg": nested}
    attempt(
        "compile_5000_deep_object", lambda: le.compile_expression(nested, ops).digest
    )
    c = le.compile_expression(
        {"op": "add", "args": [{"term": "traj_d1"}, {"term": "sq_error"}]}, ops
    )
    loose = json.dumps(c.document(), indent=2).encode()
    attempt(
        "from_bytes_non_canonical_bytes",
        lambda: {
            "accepted_same_digest": le.from_bytes(loose, ops).digest == c.digest,
            "bytes_equal_canonical": loose == c.canonical_bytes(),
        },
    )
    dup = (
        b'{"schema":"'
        + le.SCHEMA.encode()
        + b'","operation_set":"'
        + ops.digest.encode()
        + b'","expression":{"term":"traj_d1","term":"sq_error"}}'
    )
    attempt("from_bytes_duplicate_key", lambda: le.from_bytes(dup, ops).expression)
    nan = (
        b'{"schema":"'
        + le.SCHEMA.encode()
        + b'","operation_set":"'
        + ops.digest.encode()
        + b'","expression":{"op":"scale","by":NaN,"arg":{"term":"sq_error"}}}'
    )
    attempt("from_bytes_NaN_token", lambda: le.from_bytes(nan, ops).digest)
    attempt(
        "bool_constant",
        lambda: (
            le.compile_expression(
                {"op": "scale", "by": True, "arg": {"term": "sq_error"}}, ops
            ).digest
        ),
    )
    attempt(
        "subnormal_scale_5e-324",
        lambda: (
            le.compile_expression(
                {"op": "scale", "by": 5e-324, "arg": {"term": "sq_error"}}, ops
            ).digest
        ),
    )
    attempt(
        "semantic_duplicate_scale_1",
        lambda: {
            "digest_differs_from_bare_term": le.compile_expression(
                {"op": "scale", "by": 1.0, "arg": {"term": "sq_error"}}, ops
            ).digest
            != le.compile_expression({"term": "sq_error"}, ops).digest
        },
    )
    return out


def hard_example_interplay():
    """(current / mean(current)) ** hew, as training.weights computes it, on losses
    that may be negative (raw sub/neg) versus the proposed non-negative set."""
    _, prop, raw = sets()
    zhat, zt, gw = regime_arrays("typical")
    out = {}
    for label, opset, ops in (
        ("proposed", prop, None),
        ("with_raw_sub_neg", raw, ["sub", "neg", "add", "scale", "mul", "mean_t"]),
    ):
        exprs = sample(opset, 200, 77, ops=ops)
        bad = 0
        neg = 0
        for e in exprs:
            v = np_values(e, 1e-6, zhat, zt, gw, np.float64)
            neg += bool((v < 0).any())
            with np.errstate(all="ignore"):
                w = (v / (np.mean(v) + 1e-12)) ** 0.5
            bad += not np.isfinite(w).all()
        out[label] = {
            "n": len(exprs),
            "some_case_loss_negative": neg,
            "hard_example_weights_nonfinite": bad,
        }
    return out


def divergence_fit():
    """A loss unbounded below (neg) versus a non-negative loss, 300 gradient steps."""
    import jax

    rng = np.random.RandomState(5)
    x = jax.numpy.asarray(rng.uniform(size=(64, 4)), jax.numpy.float32)
    zt = jax.numpy.asarray(rng.normal(size=(64, DIMS)), jax.numpy.float32)
    gw = jax.numpy.asarray(group_weights(), jax.numpy.float32)
    out = {}
    for label, expr in (
        ("neg_sq_error", {"op": "neg", "arg": {"term": "sq_error"}}),
        ("sq_error", {"term": "sq_error"}),
        (
            "constant_mean_t_time",
            {"op": "mean_t", "over": "both", "arg": {"term": "time_t"}},
        ),
    ):
        init, loss = mlp_loss_fn(expr, 1e-6, width=64, depth=2)
        p = init(jax.random.PRNGKey(1))
        p0 = p
        g = jax.jit(jax.value_and_grad(loss))
        first_nonfinite = None
        value = None
        for i in range(300):
            value, grads = g(p, x, zt, gw)
            if not np.isfinite(float(value)) and first_nonfinite is None:
                first_nonfinite = i
            p = jax.tree_util.tree_map(lambda a, b: a - 1e-2 * b, p, grads)
        moved = any(
            not np.array_equal(np.asarray(a), np.asarray(b))
            for a, b in zip(jax.tree_util.tree_leaves(p), jax.tree_util.tree_leaves(p0))
        )
        out[label] = {
            "final_loss": float(value),
            "first_nonfinite_step": first_nonfinite,
            "params_moved": moved,
        }
    return out


def fingerprint():
    import jax

    prop = PROPOSED
    exprs = sample(prop, 120, 4242)
    h = hashlib.sha256()
    for r in ("typical", "init"):
        zhat, zt, gw = regime_arrays(r)
        f32 = [np.asarray(a, np.float32) for a in (zhat, zt, gw)]
        for e in exprs:
            values, vg, _ = jax_fns(e, prop["epsilon"])
            v = np.asarray(values(*f32))
            loss, g = vg(*f32)
            h.update(v.tobytes())
            h.update(np.asarray(loss).tobytes())
            h.update(np.asarray(g).tobytes())
    print(
        json.dumps(
            {"exprs": len(exprs), "sha256": h.hexdigest(), "jax": jax.__version__}
        )
    )


def _clip(g):
    import jax.numpy as jnp

    return jnp.clip(g, -1.0, 1.0)


def _step(a, b):
    return a - 1e-3 * b


def _scan_fit(loss, p, x, zt, gw):
    """100 clipped gradient steps in one jitted lax.scan."""
    import jax

    def body(p, _):
        v, g = jax.value_and_grad(loss)(p, x, zt, gw)
        g = jax.tree_util.tree_map(_clip, g)
        return jax.tree_util.tree_map(_step, p, g), v

    return jax.jit(lambda p: jax.lax.scan(body, p, None, length=100))(p)


def fit():
    """Short jitted fits (Adam-free plain GD in a lax.scan, as a trainer would trace it)
    for max-size proposed expressions; prints param hashes."""
    import jax
    import jax.numpy as jnp

    exprs = [e for e in sample(PROPOSED, 60, 9090) if stats(e)[1] >= 40][:8]
    exprs.append(
        compile_wide(
            l1.menu_expression(
                {
                    "relative_loss": True,
                    "time_weighting": "early",
                    "h1_weight": 0.5,
                    "h2_weight": 0.0,
                    "spectral_weight": 2.0,
                }
            ),
            PROPOSED,
        )
    )
    rng = np.random.RandomState(8)
    x = jnp.asarray(rng.uniform(size=(128, 4)), jnp.float32)
    zt = jnp.asarray(rng.normal(size=(128, DIMS)), jnp.float32)
    gw = jnp.asarray(group_weights(), jnp.float32)
    hashes = []
    for e in exprs:
        init, loss = mlp_loss_fn(e, PROPOSED["epsilon"], width=128, depth=2)
        p = init(jax.random.PRNGKey(3))
        start = b"".join(np.asarray(a).tobytes() for a in jax.tree_util.tree_leaves(p))

        p, values = _scan_fit(loss, p, x, zt, gw)
        blob = b"".join(np.asarray(a).tobytes() for a in jax.tree_util.tree_leaves(p))
        hashes.append(
            {
                "nodes": stats(e)[1],
                "depth": stats(e)[0],
                "final_loss_finite": bool(np.isfinite(np.asarray(values)[-1])),
                "params_moved": blob != start,
                "params_sha256": hashlib.sha256(blob).hexdigest()[:16],
            }
        )
    print(json.dumps(hashes))


def canonical_checks():
    """Commutative reordering and byte round-trip on the proposed set."""
    rng = random.Random(55)
    exprs = sample(PROPOSED, 200, 5151)
    reorder_same = 0
    roundtrip_same = 0

    def shuffle(node):
        if "term" in node:
            return dict(node)
        n = dict(node)
        if "args" in n:
            n["args"] = [shuffle(a) for a in n["args"]]
            if n["op"] in COMMUTATIVE:
                rng.shuffle(n["args"])
        else:
            n["arg"] = shuffle(n["arg"])
        return n

    for e in exprs:
        c = compile_wide(e, PROPOSED)
        reorder_same += compile_wide(shuffle(e), PROPOSED) == c
        body = json.dumps(c, sort_keys=True, separators=(",", ":"), allow_nan=False)
        roundtrip_same += compile_wide(json.loads(body), PROPOSED) == c
    zhat, zt, gw = regime_arrays("typical")
    case, errors = term_arrays(np, zhat, zt, gw)
    late = compile_wide(
        {
            "op": "mean_t",
            "over": "both",
            "arg": {
                "op": "scale",
                "by": 2.0,
                "arg": {
                    "op": "mul",
                    "args": [{"term": "time_t"}, {"term": "err_sq_t"}],
                },
            },
        },
        PROPOSED,
    )
    got = evaluate(late, case, errors, np, 1e-6)
    ramp_rel = float(
        np.max(np.abs(got - case["traj_ramp_late"]) / case["traj_ramp_late"])
    )
    parts = sum(case[f"sq_error_{g}"] for g in GROUPS)
    group_rel = float(np.max(np.abs(parts - case["sq_error"]) / case["sq_error"]))
    return {
        "n": len(exprs),
        "commutative_shuffle_same_canonical": reorder_same,
        "canonical_bytes_roundtrip_same": roundtrip_same,
        "time_sort_restates_traj_ramp_late_max_rel": ramp_rel,
        "component_terms_sum_to_sq_error_max_rel": group_rel,
    }


def main(path):
    import jax

    t0 = time.time()
    draft, prop, raw = sets()
    result = {
        "jax": jax.__version__,
        "numpy": np.__version__,
        "platform": jax.devices()[0].platform,
        "proposed": prop,
    }
    result["probes_on_shipped_module"] = probes()
    result["canonical_checks"] = canonical_checks()
    for label, opset, n in (
        ("draft_GA_D6", draft, 120),
        ("proposed_v1", prop, 200),
        ("proposed_plus_raw", raw, 120),
    ):
        exprs = sample(opset, n, 1234 if label != "draft_GA_D6" else 99)
        result[label] = nonfinite_and_numerics(opset, exprs)
        print(label, "done", round(time.time() - t0), file=sys.stderr)
    result["hard_example_weight_interplay"] = hard_example_interplay()
    result["divergence_fit"] = divergence_fit()
    result["cost"] = cost(prop)
    result["seconds"] = round(time.time() - t0)
    with open(path, "w") as f:
        json.dump(result, f, indent=1, sort_keys=True)
    print("written", path, result["seconds"], "s")


def culprits():
    """Which sampled proposed expressions go non-finite in float32, and on what."""

    exprs = sample(PROPOSED, 200, 1234)
    out = []
    for r in ("perfect", "typical", "init"):
        zhat, zt, gw = regime_arrays(r)
        f32 = [np.asarray(a, np.float32) for a in (zhat, zt, gw)]
        for i, e in enumerate(exprs):
            _, vg, _ = jax_fns(e, PROPOSED["epsilon"])
            loss, g = vg(*f32)
            if not (np.isfinite(float(loss)) and np.isfinite(np.asarray(g)).all()):
                out.append(
                    {
                        "regime": r,
                        "index": i,
                        "depth_nodes": stats(e),
                        "expression": json.dumps(e, sort_keys=True)[:600],
                    }
                )
    print(json.dumps(out, indent=1))


def term_ranges():
    """The smallest and largest value of every registered term, per regime."""
    out = {}
    for r in REGIMES:
        zhat, zt, gw = regime_arrays(r)
        case, errors = term_arrays(np, zhat, zt, gw)
        row = {k: [float(np.min(v)), float(np.max(v))] for k, v in case.items()}
        sq = np.concatenate([(e**2).ravel() for e in errors])
        row["err_sq_t"] = [float(sq.min()), float(sq.max())]
        out[r] = row
    print(json.dumps(out, indent=1, sort_keys=True))


def polish_check():
    """Carbon's L-BFGS polish (training.polish) over kinked expressions."""
    import jax
    import jax.numpy as jnp
    import optax

    from carbon.battery.training import polish

    expressions = {
        "max_of_components": {
            "op": "max",
            "args": [{"term": f"sq_error_{g}"} for g in GROUPS],
        },
        "cap_saturated": {"op": "cap", "at": 0.001, "arg": {"term": "sq_error"}},
        "excess_deadzone": {"op": "excess", "over": 0.5, "arg": {"term": "sq_error"}},
        "max_t_voltage": {
            "op": "max_t",
            "over": "voltage",
            "arg": {"term": "err_sq_t"},
        },
        "smooth_control": {"term": "sq_error"},
    }
    rng = np.random.RandomState(4)
    x = jnp.asarray(rng.uniform(size=(64, 4)), jnp.float32)
    zt = jnp.asarray(rng.normal(size=(64, DIMS)), jnp.float32)
    gw = jnp.asarray(group_weights(), jnp.float32)
    out = {}
    for name, e in expressions.items():
        expr = compile_wide(e, PROPOSED)
        init, loss = mlp_loss_fn(expr, 1e-6, width=64, depth=2)
        p0 = init(jax.random.PRNGKey(2))
        before = float(loss(p0, x, zt, gw))
        p = polish(jax, optax, p0, lambda q, loss=loss: loss(q, x, zt, gw), 25)
        leaves = [np.asarray(a) for a in jax.tree_util.tree_leaves(p)]
        out[name] = {
            "loss_before": before,
            "loss_after": float(loss(p, x, zt, gw)),
            "params_finite": all(np.isfinite(a).all() for a in leaves),
            "params_sha256": hashlib.sha256(
                b"".join(a.tobytes() for a in leaves)
            ).hexdigest()[:16],
        }
    print(json.dumps(out, sort_keys=True))


def override_limits():
    for key in ("max_depth", "max_nodes"):
        value = os.environ.get("L1_" + key.upper())
        if value:
            PROPOSED[key] = int(value)


if __name__ == "__main__":
    override_limits()
    mode = sys.argv[1]
    if mode == "culprits":
        culprits()
    if mode == "cost":
        print(json.dumps(cost(PROPOSED), indent=1))
    if mode == "terms":
        term_ranges()
    if mode == "polish":
        polish_check()
    if mode == "main":
        main(sys.argv[2])
    elif mode == "fingerprint":
        fingerprint()
    elif mode == "fit":
        fit()
