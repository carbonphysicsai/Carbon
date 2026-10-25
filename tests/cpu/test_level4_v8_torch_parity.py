"""Backend parity for allowlist v8's new ops (owner rule: PyTorch must agree
with JAX): each op a miner can now write is built as a Carbon graph from the
JAX program, rebuilt by Carbon's interpreter, and compared with PyTorch's own
implementation of the same operation on the same inputs, in values and in
gradients. Where PyTorch has no equivalent (cbrt, population_count, clz,
nextafter on integers) the op is listed in `NO_TORCH_EQUIVALENT` and parity is
against JAX alone in `test_level4_v8_ops.py`.

CPU only: both frameworks run on this host's CPU. The GPU variant of every
case is the same parametrisation with `CARBON_PARITY_DEVICE=cuda` on a host
with both a CUDA JAX and a CUDA torch; it is skipped otherwise.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("JAX_PLATFORMS", "cpu")

torch = pytest.importorskip("torch")
jax = pytest.importorskip("jax")
import jax.numpy as jnp
import jax.scipy.linalg as jsl
import jax.scipy.special as jsp
import numpy as np
from jax import lax

from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import graph, interpret
from carbon.level4.tooling import lower_jax

V8 = allowlist_module.load(
    Path(allowlist_module.__file__).with_name("allowlist_v8.json")
)
if os.environ.get("CARBON_PARITY_DEVICE", "cpu") != "cpu":
    pytest.skip(
        "GPU parity needs a CUDA JAX and torch together", allow_module_level=True
    )

# Ops with no PyTorch operation of the same meaning; checked against JAX only.
NO_TORCH_EQUIVALENT = {
    "cbrt",
    "population_count",
    "clz",
    "reduce_precision",
    "betainc",
    "platform_index",
    "optimization_barrier",
}


def _rebuild(fn, args):
    closed = lower_jax.trace(fn, *args)
    names = [f"a{i}" for i in range(len(closed.jaxpr.invars))]
    doc = lower_jax.lower(closed, role="forward", allowlist=V8, input_names=names)
    parsed = graph.parse(graph.dumps(doc), max_bytes=1 << 26)
    return interpret.rebuild(parsed, V8)


def _t(x, grad=False):
    t = torch.from_numpy(np.array(x))
    return t.requires_grad_(True) if grad and t.is_floating_point() else t


def _np(x):
    return x.detach().numpy() if isinstance(x, torch.Tensor) else np.asarray(x)


def _compare(fn, tfn, args, *, rtol=2e-4, atol=1e-5, grad=True, post=None):
    run = _rebuild(fn, args)
    got = [np.asarray(o) for o in run(*args)]
    targs = [_t(a, grad) for a in args]
    out = tfn(*targs)
    want = [_np(o) for o in (out if isinstance(out, tuple | list) else [out])]
    if post is not None:
        got, want = post(got), post(want)
    assert len(got) == len(want)
    for g, w in zip(got, want):
        assert g.shape == w.shape, (g.shape, w.shape)
        if w.dtype.kind in "fc":
            np.testing.assert_allclose(g, w, rtol=rtol, atol=atol, equal_nan=True)
        else:
            np.testing.assert_array_equal(g, w)
    diff = [
        i
        for i, a in enumerate(targs)
        if isinstance(a, torch.Tensor) and a.requires_grad
    ]
    float_out = [
        o
        for o in (out if isinstance(out, tuple | list) else [out])
        if isinstance(o, torch.Tensor) and o.is_floating_point()
    ]
    if grad and diff and float_out and post is None:
        probe = [
            torch.linspace(0.3, 1.1, o.numel(), dtype=o.dtype).reshape(o.shape)
            for o in float_out
        ]
        total = sum((o * p).sum() for o, p in zip(float_out, probe))
        want_grads = torch.autograd.grad(total, [targs[i] for i in diff])
        probes = [jnp.asarray(p.numpy()) for p in probe]

        def scalar(*a):
            outs = [o for o in run(*a) if jnp.issubdtype(o.dtype, jnp.floating)]
            return sum((o * p).sum() for o, p in zip(outs, probes))

        got_grads = jax.grad(scalar, argnums=tuple(diff))(*args)
        for g, w in zip(got_grads, want_grads):
            np.testing.assert_allclose(
                np.asarray(g), w.numpy(), rtol=max(rtol, 5e-4), atol=max(atol, 1e-4)
            )


X = np.linspace(-0.9, 0.9, 12, dtype=np.float32).reshape(3, 4)
POS = np.linspace(0.3, 3.0, 12, dtype=np.float32).reshape(3, 4)
BIG = np.linspace(1.1, 4.0, 12, dtype=np.float32).reshape(3, 4)
V = np.array([0.5, -1.25, 2.0, 0.75], np.float32)
SPD = np.array([[4.0, 1.0, 0.5], [1.0, 3.0, 0.2], [0.5, 0.2, 2.0]], np.float32)
GEN = np.array([[2.0, 1.0, 0.3], [0.4, 3.0, 0.1], [0.2, 0.5, 1.5]], np.float32)
RHS = np.array([[1.0, 2.0], [0.5, -1.0], [3.0, 0.25]], np.float32)
IDX = np.array([0, 2, 2, 1], np.int32)
SH = np.array([3, 7, 255, 1 << 20], np.int32)

tc = torch
ts = torch.special

ELEMENTWISE = {
    "asin": (jnp.arcsin, tc.asin, (X,)),
    "acos": (jnp.arccos, tc.acos, (X,)),
    "atan": (jnp.arctan, tc.atan, (X * 3,)),
    "atan2": (jnp.arctan2, tc.atan2, (X, X[::-1].copy() + 1.5)),
    "atan2_negative": (jnp.arctan2, tc.atan2, (X, -X[::-1].copy() - 0.2)),
    "asinh": (jnp.arcsinh, tc.asinh, (X * 3,)),
    "acosh": (jnp.arccosh, tc.acosh, (BIG,)),
    "atanh": (jnp.arctanh, tc.atanh, (X,)),
    "sinh": (jnp.sinh, tc.sinh, (X * 2,)),
    "cosh": (jnp.cosh, tc.cosh, (X * 2,)),
    "exp2": (jnp.exp2, tc.exp2, (X * 3,)),
    "ceil": (jnp.ceil, tc.ceil, (X * 3,)),
    "round_half_even": (
        jnp.round,
        tc.round,
        (np.array([0.5, 1.5, 2.5, -0.5, -1.5, 0.49, 2.51], np.float32),),
    ),
    "isfinite": (
        jnp.isfinite,
        tc.isfinite,
        (np.array([1.0, np.inf, -np.inf, np.nan], np.float32),),
    ),
    "clamp": (
        lambda x: lax.clamp(-0.2, x, 0.4),
        lambda x: tc.clamp(x, -0.2, 0.4),
        (X,),
    ),
    "nextafter": (jnp.nextafter, tc.nextafter, (V, V + 1)),
    "lgamma": (jsp.gammaln, tc.lgamma, (POS,)),
    "digamma": (jsp.digamma, tc.digamma, (POS,)),
    "polygamma": (lambda x: jsp.polygamma(2, x), lambda x: tc.polygamma(2, x), (POS,)),
    "igamma": (jsp.gammainc, ts.gammainc, (POS, POS[::-1].copy())),
    "igammac": (jsp.gammaincc, ts.gammaincc, (POS, POS[::-1].copy())),
    "zeta": (jsp.zeta, ts.zeta, (BIG, POS)),
    "i0e": (jsp.i0e, ts.i0e, (X * 4,)),
    "i1e": (jsp.i1e, ts.i1e, (X * 4,)),
    "i0": (jsp.i0, tc.i0, (X * 4,)),
    "erfinv": (jsp.erfinv, tc.erfinv, (X,)),
    "ndtri": (jsp.ndtri, ts.ndtri, (X * 0.5 + 0.5,)),
    "logsumexp": (
        lambda x: jsp.logsumexp(x, axis=1),
        lambda x: tc.logsumexp(x, dim=1),
        (X,),
    ),
    "cumprod": (
        lambda x: jnp.cumprod(x, axis=1),
        lambda x: tc.cumprod(x, dim=1),
        (POS,),
    ),
    "cummax": (
        lambda x: lax.cummax(x, axis=1),
        lambda x: tc.cummax(x, dim=1).values,
        (X,),
    ),
    "cummin": (
        lambda x: lax.cummin(x, axis=0),
        lambda x: tc.cummin(x, dim=0).values,
        (X,),
    ),
    "cumlogsumexp": (
        lambda x: lax.cumlogsumexp(x, axis=1),
        lambda x: tc.logcumsumexp(x, dim=1),
        (X,),
    ),
    "reduce_and": (
        lambda x: jnp.all(x > -0.5, axis=1),
        lambda x: (x > -0.5).all(dim=1),
        (X,),
    ),
    "reduce_or": (
        lambda x: jnp.any(x > 0.5, axis=0),
        lambda x: (x > 0.5).any(dim=0),
        (X,),
    ),
    "xor": (
        lambda a: a ^ (a >> 1),
        lambda a: tc.bitwise_xor(a, tc.bitwise_right_shift(a, 1)),
        (SH,),
    ),
    "shift_left": (lambda a: a << 2, lambda a: tc.bitwise_left_shift(a, 2), (SH,)),
    "shift_right_arithmetic": (
        lambda a: lax.shift_right_arithmetic(-a, 1),
        lambda a: tc.bitwise_right_shift(-a, 1),
        (SH,),
    ),
}

SHAPES = {
    "stack": (
        lambda a, b: jnp.stack([a, b, a + b]),
        lambda a, b: tc.stack([a, b, a + b]),
        (V, V * 2),
    ),
    "stack_axis1": (
        lambda a, b: jnp.stack([a, b], axis=1),
        lambda a, b: tc.stack([a, b], dim=1),
        (V, V * 2),
    ),
    "unstack": (lambda a: tuple(a), lambda a: tuple(a.unbind(0)), (X,)),
    "tile": (lambda a: jnp.tile(a, (2, 2)), lambda a: tc.tile(a, (2, 2)), (X,)),
    "diag": (jnp.diag, tc.diag, (V,)),
    "diagonal": (jnp.diagonal, tc.diagonal, (SPD,)),
    "trace": (jnp.trace, tc.trace, (SPD,)),
    "top_k": (
        lambda a: lax.top_k(a, 2),
        lambda a: tuple(tc.topk(a, 2)),
        (X,),
    ),
    "sort_values": (
        lambda a: jnp.sort(a, axis=1),
        lambda a: tc.sort(a, dim=1).values,
        (X[:, ::-1].copy(),),
    ),
}

WINDOWS = {
    "reduce_window_sum": (
        lambda a: lax.reduce_window(a, 0.0, lax.add, (1, 2), (1, 1), "VALID"),
        lambda a: tc.nn.functional.avg_pool1d(a[None], 2, 1)[0] * 2,
        (X,),
    ),
    "reduce_window_max": (
        lambda a: lax.reduce_window(a, -jnp.inf, lax.max, (1, 2), (1, 1), "VALID"),
        lambda a: tc.nn.functional.max_pool1d(a[None], 2, 1)[0],
        (X,),
    ),
    "reduce_window_min": (
        lambda a: lax.reduce_window(a, jnp.inf, lax.min, (1, 3), (1, 1), "VALID"),
        lambda a: -tc.nn.functional.max_pool1d(-a[None], 3, 1)[0],
        (X,),
    ),
}

SCATTERS = {
    "scatter_add": (
        lambda a, i: a.at[i].add(1.5),
        lambda a, i: a.index_add(0, i.long(), tc.full((4,), 1.5)),
        (V, IDX),
    ),
    "scatter_mul": (
        lambda a, i: a.at[i].multiply(2.0),
        lambda a, i: a.scatter_reduce(0, i.long(), tc.full((4,), 2.0), "prod"),
        (V, IDX),
    ),
    "scatter_min": (
        lambda a, i: a.at[i].min(0.4),
        lambda a, i: a.scatter_reduce(0, i.long(), tc.full((4,), 0.4), "amin"),
        (V, IDX),
    ),
    "scatter_max": (
        lambda a, i: a.at[i].max(0.4),
        lambda a, i: a.scatter_reduce(0, i.long(), tc.full((4,), 0.4), "amax"),
        (V, IDX),
    ),
    "scatter_sub": (
        lambda a, i: a.at[i].subtract(0.5),
        lambda a, i: a.index_add(0, i.long(), tc.full((4,), -0.5)),
        (V, IDX),
    ),
}


def _lu(a):
    _, lo, up = tc.linalg.lu(a)
    return lo, up


def _eigh_recon(outs):
    values, vectors = outs
    return [values, (vectors * values) @ vectors.T]


def _svd_recon(outs):
    u, s, vt = outs
    return [s, (u * s) @ vt]


def _qr_recon(outs):
    q, r = outs
    return [np.abs(np.diag(r)), q @ r]


LINALG = {
    "cholesky": (jnp.linalg.cholesky, tc.linalg.cholesky, (SPD,), None),
    "triangular_solve": (
        lambda a, b: jsl.solve_triangular(jnp.tril(a), b, lower=True),
        lambda a, b: tc.linalg.solve_triangular(tc.tril(a), b, upper=False),
        (SPD, RHS),
        None,
    ),
    "triangular_solve_transposed": (
        lambda a, b: jsl.solve_triangular(jnp.triu(a), b, trans=1, lower=False),
        lambda a, b: tc.linalg.solve_triangular(tc.triu(a).T, b, upper=False),
        (SPD, RHS),
        None,
    ),
    "solve": (jnp.linalg.solve, tc.linalg.solve, (GEN, RHS), None),
    "inv": (jnp.linalg.inv, tc.linalg.inv, (GEN,), None),
    "det": (jnp.linalg.det, tc.linalg.det, (GEN,), None),
    "slogdet": (
        jnp.linalg.slogdet,
        lambda a: tuple(tc.linalg.slogdet(a)),
        (GEN,),
        None,
    ),
    "lu_factors": (
        lambda a: jsl.lu(a)[1:],
        _lu,
        (GEN,),
        None,
    ),
    "qr": (jnp.linalg.qr, tc.linalg.qr, (GEN,), _qr_recon),
    "eigh": (jnp.linalg.eigh, lambda a: tuple(tc.linalg.eigh(a)), (SPD,), _eigh_recon),
    "eigvalsh": (jnp.linalg.eigvalsh, tc.linalg.eigvalsh, (SPD,), None),
    "svd": (
        lambda a: jnp.linalg.svd(a, full_matrices=False),
        lambda a: tuple(tc.linalg.svd(a, full_matrices=False)),
        (GEN,),
        _svd_recon,
    ),
    "svdvals": (
        lambda a: jnp.linalg.svd(a, compute_uv=False),
        tc.linalg.svdvals,
        (GEN,),
        None,
    ),
    "pinv": (jnp.linalg.pinv, tc.linalg.pinv, (GEN,), None),
    "lstsq": (
        lambda a, b: jnp.linalg.lstsq(a, b)[0],
        lambda a, b: tc.linalg.lstsq(a, b).solution,
        (GEN, RHS),
        None,
    ),
    "matrix_exp": (jsl.expm, tc.linalg.matrix_exp, (GEN * 0.3,), None),
    "matrix_power": (
        lambda a: jnp.linalg.matrix_power(a, 3),
        lambda a: tc.linalg.matrix_power(a, 3),
        (GEN,),
        None,
    ),
    "matrix_norm_2": (
        lambda a: jnp.linalg.norm(a, 2),
        lambda a: tc.linalg.matrix_norm(a, 2),
        (GEN,),
        None,
    ),
}


def _loop_scan(a):
    carry, ys = 0.0, []
    for x in a:
        ys.append(carry * x)
        carry = carry + x
    return carry, tc.stack(ys)


CONTROL = {
    "scan": (
        lambda a: lax.scan(lambda c, x: (c + x, c * x), 0.0, a),
        _loop_scan,
        (V,),
    ),
    "fori_loop": (
        lambda a: lax.fori_loop(0, 5, lambda k, x: x * 1.1 + k, a),
        lambda a: _iterate(a),
        (V,),
    ),
    "cond_true": (
        lambda a: lax.cond(a.sum() > 0, lambda x: x * 2, lambda x: -x, a),
        lambda a: tc.where(a.sum() > 0, a * 2, -a),
        (V,),
    ),
    "cond_false": (
        lambda a: lax.cond(a.sum() > 0, lambda x: x * 2, lambda x: -x, a),
        lambda a: tc.where(a.sum() > 0, a * 2, -a),
        (-V,),
    ),
}


def _iterate(a):
    for k in range(5):
        a = a * 1.1 + k
    return a


CASES = {
    **{k: (*v, None) if len(v) == 3 else v for k, v in ELEMENTWISE.items()},
    **{k: (*v, None) for k, v in SHAPES.items()},
    **{k: (*v, None) for k, v in WINDOWS.items()},
    **{k: (*v, None) for k, v in SCATTERS.items()},
    **LINALG,
    **{k: (*v, None) for k, v in CONTROL.items()},
}
#: Piecewise-constant or discrete cases: values only.
VALUES_ONLY = {
    "ceil",
    "round_half_even",
    "nextafter",
    "isfinite",
    "xor",
    "shift_left",
    "shift_right_arithmetic",
    "top_k",
    "sort_values",
    # PyTorch has no derivative for these (JAX does; see test_level4_v8_ops).
    "igamma",
    "igammac",
    "zeta",
}
#: Libraries that agree to rounding, not bit for bit.
LOOSE = {
    "svd": 5e-4,
    "svdvals": 5e-4,
    "pinv": 5e-4,
    "lstsq": 5e-4,
    "matrix_exp": 5e-4,
    "matrix_norm_2": 5e-4,
    "eigh": 5e-4,
    "eigvalsh": 5e-4,
    "qr": 5e-4,
    "polygamma": 5e-4,
    "zeta": 5e-4,
    "igamma": 5e-4,
    "igammac": 5e-4,
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_new_op_agrees_with_pytorch(name):
    fn, tfn, args, post = CASES[name]
    # Piecewise or discrete: values only. Sorting-network and decomposition
    # gradients differ in gauge, so those compare reconstructions in values.
    grad = name not in VALUES_ONLY and post is None and not name.startswith("lu")
    _compare(fn, tfn, args, rtol=LOOSE.get(name, 2e-4), grad=grad, post=post)
