"""SHORTCUT PANEL TRAINER: a Challenge-neutral panel of cheap, generic models fit on a version's PUBLIC TRAIN set only.

This is check (1) (b) and (c) of the strong-checks spec: the generic fits (Gaussian process, polynomial ridge, RBF ridge,
gradient-boosted trees, k-nearest-neighbour) and the physics-feature sparse regression. It only FITS and PREDICTS. Scoring the
predictions through the version's own grader belongs to the caller. The query inputs never influence a fit: every choice
(standardization statistics, folds, hyperparameters, selected terms) is made from the TRAIN rows alone.

    python shortcut_panel.py fit --train TRAIN.npz --query QUERY.npy --members gp,poly_ridge,... --seed 0 --out OUTDIR

writes OUTDIR/<member>.npy (raw query predictions, float64, query row order) and OUTDIR/panel-record.json.

TRAIN layout. The repo's public TRAIN artifacts (carbon/challenge_kit/data/*.npz) hold arrays ``inputs`` (n, d) and ``targets``
(n, m). A plain npz with arrays ``X`` and ``Y`` is accepted too. Those are the only keys read (``inputs``/``targets`` first).

Method common to all members: X and Y are standardized with TRAIN mean/std (a constant column gets std 1). Folds: one seeded
permutation of the training rows split into k = 5 folds (fewer for tiny sets). The CV score is the mean, over folds and output
columns, of the held-out RMSE on standardized Y. A grid point wins on the lowest mean CV score; ties go to the earlier grid point.

Members, grids (``d`` = number of inputs; lengthscales are in standardized X units and scale with sqrt(d)):
- gp: universal kriging. Mean = OLS linear trend, residual = zero-mean GP with a squared-exponential kernel (unit signal
  variance) plus a noise term. Shared lengthscale multiplier in {0.1, 0.2, 0.4, 0.8, 1.6, 3.2} x sqrt(d) and noise in
  {1e-8, 1e-6, 1e-4, 1e-2, 1e-1} chosen by k-fold CV (not marginal likelihood), then ONE coordinate sweep per input that tries
  half and double that input's lengthscale (ARD, kept only when CV improves; skipped above 2000 rows or 12 inputs). One kernel
  is shared by all output columns.
- poly_ridge: polynomial features (all monomials) of degree 1, 2, 3 on standardized X; ridge alpha in {1e-6, 1e-4, 1e-2, 1, 100}
  on standardized features; degree and alpha by CV. A degree whose feature count exceeds 3000 is skipped.
- rbf_ridge: kernel ridge, RBF kernel, one shared lengthscale multiplier in the gp grid, alpha in {1e-6, 1e-4, 1e-2, 1e-1, 1, 10},
  centred targets (no trend). Same predictor family as the gp mean but a different grid and no trend or ARD.
- gbm: gradient-boosted regression trees, squared loss, exact-split multi-output trees (one tree per round for all columns),
  min leaf 2. depth in {2, 4}, learning rate in {0.1, 0.3}, rounds in {30, 60, 100, 150}; rounds come from one 150-round fit.
- knn: k nearest training rows in standardized X, weights 1/(distance + 1e-9), k in {1, 2, 3, 5, 8, 12, 20}.
- sparse_physics: sequentially thresholded least squares (SINDy style), fit per output column. Primitives are the inputs and,
  for inputs strictly positive on TRAIN, their logs. Two spaces per column, chosen by CV: "lin" (y against 1, x_i, log x_i,
  x_i x_j, 1/x_i, x_i/x_j) and "log" (log y against 1, log x_i, x_i and log x_i log x_j; needs y > 0 on TRAIN, and
  predictions are exp of the fit, a power-law search). Threshold on the standardized coefficient in
  {0.3, 0.1, 0.03, 0.01, 0.003, 0}; the sparsest grid point within 1 percent (+1e-9) of the best CV score is taken. The selected terms and
  coefficients (raw units) are in the record. Queries with a non-positive value for a positive input use log(max(x, 1e-12)).

Cost limits. GP and RBF ridge are O(n^3) (an eigendecomposition per fold and lengthscale): above MAX_KERNEL_ROWS (3000) training
rows both fit a deterministic seeded subsample of 3000 rows, recorded as ``n_rows_used``. The other members use every row. Worst
case wall clock is minutes at n of a few thousand with m near 40 (gbm and sparse_physics dominate); the grids are small on purpose.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path

import numpy as np
from scipy.linalg import LinAlgError, cho_factor, cho_solve
from scipy.spatial.distance import cdist

SCHEMA = "carbon.exam-reads.shortcut-panel.v1"
MEMBER_NAMES = ("gp", "poly_ridge", "rbf_ridge", "gbm", "knn", "sparse_physics")
MAX_KERNEL_ROWS = 3000
MIN_ROWS = 6
MAX_FOLDS = 5
LS_MULT = (0.1, 0.2, 0.4, 0.8, 1.6, 3.2)
GP_NOISE = (1e-8, 1e-6, 1e-4, 1e-2, 1e-1)
KRR_ALPHA = (1e-6, 1e-4, 1e-2, 1e-1, 1.0, 10.0)
POLY_DEGREES = (1, 2, 3)
POLY_ALPHA = (1e-6, 1e-4, 1e-2, 1.0, 100.0)
POLY_MAX_FEATURES = 3000
GBM_DEPTH = (2, 4)
GBM_LR = (0.1, 0.3)
GBM_ROUNDS = (30, 60, 100, 150)
KNN_K = (1, 2, 3, 5, 8, 12, 20)
SPARSE_THRESHOLDS = (0.3, 0.1, 0.03, 0.01, 0.003, 0.0)
SPARSE_SPACES = ("log", "lin")
SPARSE_TOLERANCE = 0.01
ARD_MAX_ROWS = 2000
ARD_MAX_INPUTS = 12


class Refused(ValueError):
    """Bad inputs: the panel refuses rather than fitting something unintended."""


# ---------------------------------------------------------------- inputs, scaling, folds


class _Ctx:
    """TRAIN statistics only."""

    def __init__(self, X, Y):
        self.xmean = X.mean(axis=0)
        self.xstd = np.where(X.std(axis=0) > 1e-12, X.std(axis=0), 1.0)
        self.ymean = Y.mean(axis=0)
        self.ystd = np.where(Y.std(axis=0) > 1e-12, Y.std(axis=0), 1.0)
        self.positive = (X > 0).all(axis=0)

    def xs(self, X):
        return (X - self.xmean) / self.xstd

    def x_raw(self, Xs):
        return Xs * self.xstd + self.xmean

    def y_raw(self, Ys):
        return Ys * self.ystd + self.ymean


def _as_matrix(name, a, *, columns_to_vector=False):
    a = np.asarray(a)
    if a.ndim == 1 and columns_to_vector:
        a = a[:, None]
    if a.ndim != 2 or a.shape[0] < 1 or a.shape[1] < 1 or a.dtype.kind not in "fiu":
        raise Refused(f"{name}_must_be_a_2d_real_array")
    a = a.astype(np.float64)
    if not np.isfinite(a).all():
        raise Refused(f"{name}_not_finite")
    return a


def _make_folds(n, seed):
    k = min(MAX_FOLDS, n // 2)
    perm = np.random.default_rng(seed).permutation(n)
    return [np.sort(part) for part in np.array_split(perm, k)]


def _col_rmse(pred, truth):
    with np.errstate(invalid="ignore", over="ignore"):
        r = np.sqrt(((pred - truth) ** 2).mean(axis=0))
    return np.where(np.isfinite(r), r, np.inf)


def _split(n, va):
    mask = np.ones(n, dtype=bool)
    mask[va] = False
    return mask


def _cv_fn(fn, Xs, Ys, folds):
    """Mean CV RMSE of ``fn(Xtr, Ytr, Xva) -> pred``."""
    total = 0.0
    for va in folds:
        tr = _split(len(Xs), va)
        total += _col_rmse(fn(Xs[tr], Ys[tr], Xs[va]), Ys[va]).mean()
    return total / len(folds)


def _grid_cv(keys, predict, Xs, Ys, folds):
    """Per-column mean CV RMSE for each grid key. ``predict(Xtr, Ytr, Xva, keys) -> {key: (pred, info)}``."""
    cv = {k: np.zeros(Ys.shape[1]) for k in keys}
    for va in folds:
        tr = _split(len(Xs), va)
        out = predict(Xs[tr], Ys[tr], Xs[va], keys)
        for k in keys:
            cv[k] += _col_rmse(out[k][0], Ys[va]) / len(folds)
    return cv


def _first_within(keys, scores, tol):
    best = min(scores[k] for k in keys)
    for k in keys:
        if scores[k] <= best * (1.0 + tol) + (1e-9 if tol else 0.0):
            return k
    return keys[0]


def _finish(keys, predict, Xs, Ys, Xq, folds, per_column=False, tol=0.0):
    """Pick from the CV table, refit on all rows, predict the query. Returns (chosen, cv, Yq_std, info)."""
    cv = _grid_cv(keys, predict, Xs, Ys, folds)
    m = Ys.shape[1]
    if per_column:
        chosen = [
            _first_within(keys, {k: cv[k][j] for k in keys}, tol) for j in range(m)
        ]
    else:
        chosen = [_first_within(keys, {k: cv[k].mean() for k in keys}, tol)] * m
    out = predict(Xs, Ys, Xq, sorted(set(chosen), key=keys.index))
    pred = np.stack([out[chosen[j]][0][:, j] for j in range(m)], axis=1)
    info = [out[chosen[j]][1] for j in range(m)]
    score = float(np.mean([cv[chosen[j]][j] for j in range(m)]))
    if not np.isfinite(score):
        raise Refused("no_grid_point_gave_a_finite_cv_score")
    return chosen, score, pred, info


# ---------------------------------------------------------------- kernels: gp, rbf_ridge


def _rbf(A, B, ls):
    return np.exp(-0.5 * cdist(A / ls, B / ls, "sqeuclidean"))


def _linear_trend(Xtr, Ytr, Xte):
    A = np.hstack([np.ones((len(Xtr), 1)), Xtr])
    B = np.linalg.lstsq(A, Ytr, rcond=None)[0]
    return Ytr - A @ B, np.hstack([np.ones((len(Xte), 1)), Xte]) @ B


def _krr_predict(trend):
    def predict(Xtr, Ytr, Xte, keys):
        if trend:
            R, base = _linear_trend(Xtr, Ytr, Xte)
        else:
            R, base = Ytr - Ytr.mean(axis=0), np.tile(Ytr.mean(axis=0), (len(Xte), 1))
        out = {}
        sd = np.sqrt(Xtr.shape[1])
        for mult in sorted({k[0] for k in keys}):
            w, U = np.linalg.eigh(_rbf(Xtr, Xtr, mult * sd))
            w = np.maximum(w, 0.0)
            Kte, UtR = _rbf(Xte, Xtr, mult * sd), U.T @ R
            for k in (k for k in keys if k[0] == mult):
                out[k] = (base + Kte @ (U @ (UtR / (w + k[1])[:, None])), None)
        return out

    return predict


def _gp_predict_ard(Xtr, Ytr, Xte, ls, alpha):
    R, base = _linear_trend(Xtr, Ytr, Xte)
    K = _rbf(Xtr, Xtr, ls)
    K[np.diag_indices_from(K)] += alpha
    try:
        coef = cho_solve(cho_factor(K), R)
    except LinAlgError:
        w, U = np.linalg.eigh(K)
        coef = U @ ((U.T @ R) / np.maximum(w, alpha)[:, None])
    return base + _rbf(Xte, Xtr, ls) @ coef


def _run_gp(ctx, Xs, Ys, Xq, folds):
    d = Xs.shape[1]
    keys = [(m, a) for m in LS_MULT for a in GP_NOISE]
    predict = _krr_predict(True)
    table = _grid_cv(keys, predict, Xs, Ys, folds)
    mult, alpha = _first_within(keys, {k: table[k].mean() for k in keys}, 0.0)
    best = float(table[(mult, alpha)].mean())
    pred = predict(Xs, Ys, Xq, [(mult, alpha)])[(mult, alpha)][0]
    ls, ard = np.full(d, mult * np.sqrt(d)), False
    if len(Xs) <= ARD_MAX_ROWS and 1 < d <= ARD_MAX_INPUTS:
        for j in range(d):
            current = ls.copy()
            for factor in (0.5, 2.0):
                trial = current.copy()
                trial[j] *= factor
                score = _cv_fn(
                    lambda a, b, c, ls_=trial: _gp_predict_ard(a, b, c, ls_, alpha),
                    Xs,
                    Ys,
                    folds,
                )
                if score < best - 1e-12:
                    best, ls, ard = score, trial, True
        if ard:
            pred = _gp_predict_ard(Xs, Ys, Xq, ls, alpha)
    hp = {
        "kernel": "rbf_squared_exponential",
        "mean": "ols_linear_trend",
        "selection": "k_fold_cv",
        "lengthscales_std_x": [float(v) for v in ls],
        "shared_multiplier_x_sqrt_d": float(mult),
        "noise": float(alpha),
        "ard_refined": ard,
    }
    return hp, best, pred


def _run_rbf_ridge(ctx, Xs, Ys, Xq, folds):
    keys = [(m, a) for m in LS_MULT for a in KRR_ALPHA]
    chosen, score, pred, _ = _finish(keys, _krr_predict(False), Xs, Ys, Xq, folds)
    hp = {
        "kernel": "rbf",
        "lengthscale_multiplier_x_sqrt_d": chosen[0][0],
        "alpha": chosen[0][1],
    }
    return hp, score, pred


# ---------------------------------------------------------------- poly_ridge


def _poly_count(d, degree):
    from math import comb

    return comb(d + degree, degree) - 1


def _poly_features(X, degree):
    cols = []
    for deg in range(1, degree + 1):
        for combo in itertools.combinations_with_replacement(range(X.shape[1]), deg):
            cols.append(np.prod(X[:, combo], axis=1))
    return np.stack(cols, axis=1)


def _poly_predict(Xtr, Ytr, Xte, keys):
    out = {}
    for degree in sorted({k[0] for k in keys}):
        ks = [k for k in keys if k[0] == degree]
        if _poly_count(Xtr.shape[1], degree) > POLY_MAX_FEATURES:
            for k in ks:
                out[k] = (np.full((len(Xte), Ytr.shape[1]), np.nan), None)
            continue
        Ftr, Fte = _poly_features(Xtr, degree), _poly_features(Xte, degree)
        fm = Ftr.mean(axis=0)
        fs = np.where(Ftr.std(axis=0) > 1e-12, Ftr.std(axis=0), 1.0)
        ym = Ytr.mean(axis=0)
        U, s, Vt = np.linalg.svd((Ftr - fm) / fs, full_matrices=False)
        UtY, Zte = U.T @ (Ytr - ym), (Fte - fm) / fs
        for k in ks:
            out[k] = (Zte @ (Vt.T @ ((s / (s**2 + k[1]))[:, None] * UtY)) + ym, None)
    return out


def _run_poly_ridge(ctx, Xs, Ys, Xq, folds):
    keys = [(deg, a) for deg in POLY_DEGREES for a in POLY_ALPHA]
    chosen, score, pred, _ = _finish(keys, _poly_predict, Xs, Ys, Xq, folds)
    return {"degree": chosen[0][0], "alpha": chosen[0][1]}, score, pred


# ---------------------------------------------------------------- gbm


def _grow(X, R, depth, min_leaf=2):
    n = len(X)
    if depth == 0 or n < 2 * min_leaf:
        return R.mean(axis=0)
    total = R.sum(axis=0)
    base = (total**2).sum() / n
    best = None
    for j in range(X.shape[1]):
        order = np.argsort(X[:, j], kind="stable")
        xs, cs = X[order, j], np.cumsum(R[order], axis=0)
        i = np.arange(min_leaf - 1, n - min_leaf)
        i = i[xs[i] < xs[i + 1]]
        if i.size == 0:
            continue
        nl = i + 1.0
        gain = (
            (cs[i] ** 2).sum(axis=1) / nl
            + ((total - cs[i]) ** 2).sum(axis=1) / (n - nl)
            - base
        )
        t = int(np.argmax(gain))
        if best is None or gain[t] > best[0]:
            best = (gain[t], j, 0.5 * (xs[i[t]] + xs[i[t] + 1]))
    if best is None or best[0] <= 1e-12:
        return R.mean(axis=0)
    _, j, thr = best
    left = X[:, j] <= thr
    return (
        j,
        thr,
        _grow(X[left], R[left], depth - 1, min_leaf),
        _grow(X[~left], R[~left], depth - 1, min_leaf),
    )


def _tree_predict(node, X, m):
    if isinstance(node, np.ndarray):
        return np.broadcast_to(node, (len(X), m))
    j, thr, left, right = node
    mask = X[:, j] <= thr
    out = np.empty((len(X), m))
    out[mask] = _tree_predict(left, X[mask], m)
    out[~mask] = _tree_predict(right, X[~mask], m)
    return out


def _gbm_predict(Xtr, Ytr, Xte, keys):
    out, m = {}, Ytr.shape[1]
    for depth, lr in sorted({(k[0], k[1]) for k in keys}):
        marks = {k[2]: k for k in keys if (k[0], k[1]) == (depth, lr)}
        F, G = np.tile(Ytr.mean(axis=0), (len(Xtr), 1)), np.tile(
            Ytr.mean(axis=0), (len(Xte), 1)
        )
        for r in range(1, max(marks) + 1):
            tree = _grow(Xtr, Ytr - F, depth)
            F = F + lr * _tree_predict(tree, Xtr, m)
            G = G + lr * _tree_predict(tree, Xte, m)
            if r in marks:
                out[marks[r]] = (G.copy(), None)
    return out


def _run_gbm(ctx, Xs, Ys, Xq, folds):
    keys = [(dp, lr, r) for dp in GBM_DEPTH for lr in GBM_LR for r in GBM_ROUNDS]
    chosen, score, pred, _ = _finish(keys, _gbm_predict, Xs, Ys, Xq, folds)
    c = chosen[0]
    return (
        {"depth": c[0], "learning_rate": c[1], "rounds": c[2], "min_leaf": 2},
        score,
        pred,
    )


# ---------------------------------------------------------------- knn


def _knn_predict(Xtr, Ytr, Xte, keys):
    out = {k: np.empty((len(Xte), Ytr.shape[1])) for k in keys}
    for lo in range(0, len(Xte), 1000):
        D = cdist(Xte[lo : lo + 1000], Xtr)
        order = np.argsort(D, axis=1, kind="stable")
        for k in keys:
            idx = order[:, : min(k[0], len(Xtr))]
            w = 1.0 / (np.take_along_axis(D, idx, axis=1) + 1e-9)
            w /= w.sum(axis=1, keepdims=True)
            out[k][lo : lo + 1000] = np.einsum("qk,qkm->qm", w, Ytr[idx])
    return {k: (v, None) for k, v in out.items()}


def _run_knn(ctx, Xs, Ys, Xq, folds):
    keys = [(k,) for k in KNN_K]
    chosen, score, pred, _ = _finish(keys, _knn_predict, Xs, Ys, Xq, folds)
    return {"k": chosen[0][0], "weights": "inverse_distance"}, score, pred


# ---------------------------------------------------------------- sparse_physics


def _library(X, positive, space, names):
    """(F, term names) for one space. ``names`` are the input names."""
    d = X.shape[1]
    pos = [i for i in range(d) if positive[i]]
    cols, labels = [], []

    def add(col, label):
        cols.append(col)
        labels.append(label)

    L = {i: np.log(np.maximum(X[:, i], 1e-12)) for i in pos}
    if space == "lin":
        for i in range(d):
            add(X[:, i], names[i])
        for i in pos:
            add(L[i], f"log({names[i]})")
        for i, j in itertools.combinations_with_replacement(range(d), 2):
            add(X[:, i] * X[:, j], f"{names[i]}*{names[j]}")
        for i in pos:
            add(1.0 / np.maximum(X[:, i], 1e-12), f"1/{names[i]}")
        for i, j in itertools.permutations(pos, 2):
            add(X[:, i] / np.maximum(X[:, j], 1e-12), f"{names[i]}/{names[j]}")
    else:
        for i in pos:
            add(L[i], f"log({names[i]})")
        for i in range(d):
            add(X[:, i], names[i])
        for i, j in itertools.combinations_with_replacement(pos, 2):
            add(L[i] * L[j], f"log({names[i]})*log({names[j]})")
    if not cols:
        return np.zeros((len(X), 0)), []
    return np.stack(cols, axis=1), labels


def _stlsq(Z, t, threshold):
    active = np.arange(Z.shape[1])
    while True:
        b = np.zeros(Z.shape[1])
        if active.size:
            b[active] = np.linalg.lstsq(Z[:, active], t, rcond=None)[0]
        drop = active[np.abs(b[active]) < threshold]
        if drop.size == 0:
            return b
        active = np.setdiff1d(active, drop)


def _sparse_fit_column(F, t, threshold):
    """Returns (coef in raw feature units, intercept)."""
    if F.shape[1] == 0:
        return np.zeros(0), float(t.mean())
    fm = F.mean(axis=0)
    fs = np.where(F.std(axis=0) > 1e-12, F.std(axis=0), 1.0)
    tm, ts = t.mean(), t.std() if t.std() > 1e-12 else 1.0
    beta = _stlsq((F - fm) / fs, (t - tm) / ts, threshold)
    coef = beta * ts / fs
    return coef, float(tm - coef @ fm)


def _sparse_predict(ctx, names):
    def predict(Xtr, Ytr, Xte, keys):
        Xr, Xe, Yr = ctx.x_raw(Xtr), ctx.x_raw(Xte), ctx.y_raw(Ytr)
        libs = {
            s: (
                _library(Xr, ctx.positive, s, names),
                _library(Xe, ctx.positive, s, names)[0],
            )
            for s in SPARSE_SPACES
        }
        out = {}
        for space, thr in keys:
            (F, labels), Fe = libs[space]
            pred = np.full((len(Xe), Yr.shape[1]), np.nan)
            info = [None] * Yr.shape[1]
            for j in range(Yr.shape[1]):
                y = Yr[:, j]
                if space == "log" and not (y > 0).all():
                    continue
                coef, icpt = _sparse_fit_column(
                    F, np.log(y) if space == "log" else y, thr
                )
                raw = Fe @ coef + icpt
                raw = np.exp(np.clip(raw, -50.0, 50.0)) if space == "log" else raw
                pred[:, j] = (raw - ctx.ymean[j]) / ctx.ystd[j]
                terms = [{"term": "1", "coef": icpt}]
                terms += [
                    {"term": labels[i], "coef": float(coef[i])}
                    for i in np.flatnonzero(coef)
                ]
                info[j] = {
                    "space": space,
                    "threshold": thr,
                    "target": "log(y)" if space == "log" else "y",
                    "terms": terms,
                }
            out[(space, thr)] = (pred, info)
        return out

    return predict


def _run_sparse(ctx, Xs, Ys, Xq, folds, names):
    keys = [(s, t) for t in SPARSE_THRESHOLDS for s in SPARSE_SPACES]
    predict = _sparse_predict(ctx, names)
    cv = _grid_cv(keys, predict, Xs, Ys, folds)
    m = Ys.shape[1]
    chosen = [
        _first_within(keys, {k: cv[k][j] for k in keys}, SPARSE_TOLERANCE)
        for j in range(m)
    ]
    out = predict(Xs, Ys, Xq, sorted(set(chosen), key=keys.index))
    pred = np.stack([out[chosen[j]][0][:, j] for j in range(m)], axis=1)
    score = float(np.mean([cv[chosen[j]][j] for j in range(m)]))
    if not np.isfinite(score):
        raise Refused("no_grid_point_gave_a_finite_cv_score")
    selected = [out[chosen[j]][1][j] for j in range(m)]
    hp = {"method": "stlsq", "tolerance": SPARSE_TOLERANCE, "selected_terms": selected}
    return hp, score, pred


# ---------------------------------------------------------------- public API


def fit_predict(member, X_train, Y_train, X_query, *, seed, input_names=None):
    """Fit ``member`` on TRAIN only and predict ``X_query``. Returns ``(Y_query (nq, m) float64 raw, record)``."""
    if member not in MEMBER_NAMES:
        raise Refused("unknown_member:" + str(member))
    X = _as_matrix("X_train", X_train)
    Y = _as_matrix("Y_train", Y_train, columns_to_vector=True)
    Xq = _as_matrix("X_query", X_query)
    if len(X) != len(Y):
        raise Refused("train_row_count_mismatch")
    if Xq.shape[1] != X.shape[1]:
        raise Refused("query_input_count_differs_from_train")
    if len(X) < MIN_ROWS:
        raise Refused("too_few_train_rows")
    names = (
        list(input_names)
        if input_names is not None
        else [f"x{i}" for i in range(X.shape[1])]
    )
    if len(names) != X.shape[1]:
        raise Refused("input_names_count")
    seed = int(seed)
    ctx = _Ctx(X, Y)
    Xs, Ys, Qs = ctx.xs(X), (Y - ctx.ymean) / ctx.ystd, ctx.xs(Xq)
    used = np.arange(len(X))
    if member in ("gp", "rbf_ridge") and len(X) > MAX_KERNEL_ROWS:
        used = np.sort(
            np.random.default_rng([seed, 1]).choice(
                len(X), MAX_KERNEL_ROWS, replace=False
            )
        )
    Xs, Ys = Xs[used], Ys[used]
    folds = _make_folds(len(used), seed)
    if member == "sparse_physics":
        hp, score, pred = _run_sparse(ctx, Xs, Ys, Qs, folds, names)
    else:
        runner = {
            "gp": _run_gp,
            "poly_ridge": _run_poly_ridge,
            "rbf_ridge": _run_rbf_ridge,
            "gbm": _run_gbm,
            "knn": _run_knn,
        }[member]
        hp, score, pred = runner(ctx, Xs, Ys, Qs, folds)
    Yq = ctx.y_raw(pred).astype(np.float64)
    if not np.isfinite(Yq).all():
        raise Refused("member_prediction_not_finite:" + member)
    record = {
        "member": member,
        "hyperparameters": _plain(hp),
        "cv_score": float(score),
        "cv_folds": len(folds),
        "seed": seed,
        "n_train": len(X),
        "n_rows_used": len(used),
    }
    return Yq, record


def _plain(obj):
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


# ---------------------------------------------------------------- CLI


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_train(path):
    """(X, Y) from a TRAIN npz: arrays ``inputs``/``targets`` (repo layout) or ``X``/``Y``."""
    with np.load(path, allow_pickle=False) as z:
        for a, b in (("inputs", "targets"), ("X", "Y")):
            if a in z.files and b in z.files:
                return z[a], z[b]
    raise Refused("train_npz_needs_inputs_targets_or_X_Y")


def load_query(path):
    loaded = np.load(path, allow_pickle=False)
    if isinstance(loaded, np.lib.npyio.NpzFile):
        with loaded as z:
            for key in ("inputs", "X"):
                if key in z.files:
                    return z[key]
        raise Refused("query_npz_needs_inputs_or_X")
    return loaded


def run_panel(train, query, members, seed, out_dir):
    X, Y = load_train(train)
    Xq = load_query(query)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    record = {
        "schema": SCHEMA,
        "train_sha256": _sha256(train),
        "query_sha256": _sha256(query),
        "seed": int(seed),
        "members": {},
    }
    for member in members:
        Yq, rec = fit_predict(member, X, Y, Xq, seed=seed)
        path = out / f"{member}.npy"
        np.save(path, Yq)
        record["members"][member] = {**rec, "rows_sha256": _sha256(path)}
    (out / "panel-record.json").write_text(
        json.dumps(record, indent=1, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return record


EXTRA_KINDS = ("engineer_shortcut", "previous_king")
MEMBER_KIND = {name: "generic_fit" for name in MEMBER_NAMES}
MEMBER_KIND["sparse_physics"] = "physics_regression"


def _rows_count(path, what):
    try:
        rows = np.load(path, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise Refused(f"{what}_unreadable") from exc
    if not isinstance(rows, np.ndarray) or rows.ndim < 1:
        raise Refused(f"{what}_not_an_npy_array")
    return int(rows.shape[0])


def build_strong_config(panel_dir, query, extras, default, draws, seed, out_path):
    """Write the strong-checks input JSON (`q3_q8_whatif.load_strong`) from a finished ``fit`` output. ``extras`` is a list of
    ``(name, kind, rows_npy)`` (kind engineer_shortcut or previous_king), ``default`` is ``(name, rows_npy)``. Nothing is
    written when any check fails."""
    out = Path(out_path)
    if out.exists():
        raise Refused("out_path_exists")
    if type(draws) is not int or draws < 1 or type(seed) is not int:
        raise Refused("ceiling_draws_and_seed")
    panel = Path(panel_dir)
    try:
        record = json.loads((panel / "panel-record.json").read_bytes())
    except (OSError, ValueError) as exc:
        raise Refused("panel_record_unreadable") from exc
    if (
        type(record) is not dict
        or record.get("schema") != SCHEMA
        or type(record.get("members")) is not dict
        or not record["members"]
    ):
        raise Refused("panel_record_shape")
    if _sha256(query) != record.get("query_sha256"):
        raise Refused("query_sha256_differs_from_panel_record")
    n_query = _rows_count(query, "query")
    names, entries = set(), []

    def take(name, kind, path, expected_sha, what):
        if not name or name in names:
            raise Refused("name_repeats:" + str(name))
        names.add(name)
        if not Path(path).is_file():
            raise Refused(f"{what}_rows_missing:{name}")
        digest = _sha256(path)
        if expected_sha is not None and digest != expected_sha:
            raise Refused(f"rows_sha256_differs_from_panel_record:{name}")
        if _rows_count(path, what) != n_query:
            raise Refused(f"row_count_differs_from_query:{name}")
        entry = {"name": name, "rows_npy": str(Path(path).resolve()), "sha256": digest}
        if kind is not None:
            entry["kind"] = kind
        return entry

    for name, rec in sorted(record["members"].items()):
        if name not in MEMBER_KIND:
            raise Refused("unknown_panel_member:" + str(name))
        sha = rec.get("rows_sha256") if type(rec) is dict else None
        if not sha:
            raise Refused("panel_record_member_sha:" + name)
        entries.append(
            take(name, MEMBER_KIND[name], panel / f"{name}.npy", sha, "panel")
        )
    for name, kind, path in extras:
        if kind not in EXTRA_KINDS:
            raise Refused("extra_kind:" + str(kind))
        entries.append(take(name, kind, path, None, "extra"))
    default_entry = take(default[0], None, default[1], None, "default")
    document = {
        "panel": entries,
        "default_model": default_entry,
        "ceiling": {"draws": draws, "seed": seed},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=1, sort_keys=True, allow_nan=False) + "\n"
    with open(out, "x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return document


def _split_spec(text, parts, flag):
    pieces = text.split(":", parts - 1)
    if len(pieces) != parts or not all(pieces):
        raise Refused(f"{flag}_spec_needs_{parts}_colon_separated_parts")
    return pieces


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    fit = sub.add_parser("fit")
    fit.add_argument("--train", required=True)
    fit.add_argument("--query", required=True)
    fit.add_argument("--members", default=",".join(MEMBER_NAMES))
    fit.add_argument("--seed", type=int, default=0)
    fit.add_argument("--out", required=True)
    cfg = sub.add_parser("strong-config")
    cfg.add_argument("--panel-dir", required=True)
    cfg.add_argument("--query", required=True)
    cfg.add_argument("--extra", action="append", default=[])
    cfg.add_argument("--default", required=True)
    cfg.add_argument("--draws", type=int, required=True)
    cfg.add_argument("--seed", type=int, required=True)
    cfg.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "strong-config":
        try:
            extras = [_split_spec(e, 3, "extra") for e in args.extra]
            default = _split_spec(args.default, 2, "default")
            document = build_strong_config(
                args.panel_dir,
                args.query,
                extras,
                default,
                args.draws,
                args.seed,
                args.out,
            )
        except Refused as exc:
            print("REFUSED: " + str(exc), file=sys.stderr)
            return 2
        print(f"wrote {args.out}: {len(document['panel'])} panel entries")
        return 0
    members = [m.strip() for m in args.members.split(",") if m.strip()]
    try:
        record = run_panel(args.train, args.query, members, args.seed, args.out)
    except Refused as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        return 2
    for name, rec in record["members"].items():
        print(
            f"{name}: cv_score={rec['cv_score']:.6g} rows_sha256={rec['rows_sha256']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
