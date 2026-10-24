"""A deterministic, dependency-free CMA-ES for the pool grader.

Pure Python on purpose: the same private seed must give the same proposals on every grading host, and
a BLAS-backed eigendecomposition changes with the thread count. Problem sizes are small (2 to 8
design variables), so a cyclic Jacobi eigensolver is plenty.

The algorithm is the standard (mu/mu_w, lambda)-CMA-ES as Hansen describes it in "The CMA Evolution
Strategy: A Tutorial" (2016): log-weighted recombination, cumulative step-size adaptation and the
rank-one plus rank-mu covariance update. The strategy parameters are the tutorial's formulas of the
dimension; nothing here is tuned. The starting mean, the initial step size and the seed are inputs
(Carbon's custody holds them); this module has no default for any of them.

`ask` returns the unrepaired samples; `tell` takes one comparable key per sample (lower is better), so
the caller owns what "fitness" means (the pool grader ranks feasible-first, then by objective).
"""

from __future__ import annotations

import math
import random


def _jacobi_eigh(matrix, sweeps=60):
    """Eigenvalues and eigenvectors (as columns) of a small symmetric matrix, by cyclic Jacobi rotations."""
    n = len(matrix)
    a = [row[:] for row in matrix]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(sweeps):
        off = sum(a[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off < 1e-30:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-300:
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q])
                t = math.copysign(1.0, theta) / (
                    abs(theta) + math.sqrt(theta * theta + 1.0)
                )
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p], a[k][q] = c * akp - s * akq, s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k], a[q][k] = c * apk - s * aqk, s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p], v[k][q] = c * vkp - s * vkq, s * vkp + c * vkq
    values = [a[i][i] for i in range(n)]
    order = sorted(range(n), key=lambda i: (values[i], i))
    return [values[i] for i in order], [[v[r][i] for i in order] for r in range(n)]


class CmaEs:
    def __init__(self, start, sigma0, seed, population=None):
        n = len(start)
        if n < 1 or not all(math.isfinite(x) for x in start):
            raise ValueError("start must be a finite, non-empty vector")
        if not (
            isinstance(sigma0, (int, float)) and math.isfinite(sigma0) and sigma0 > 0
        ):
            raise ValueError("sigma0 must be a positive finite number")
        self.n = n
        self.rng = random.Random(seed)
        self.mean = [float(x) for x in start]
        self.sigma = float(sigma0)
        self.lam = population if population is not None else 4 + int(3 * math.log(n))
        if self.lam < 2:
            raise ValueError("population must be at least 2")
        self.mu = self.lam // 2
        raw = [math.log(self.mu + 0.5) - math.log(i) for i in range(1, self.mu + 1)]
        total = sum(raw)
        self.weights = [w / total for w in raw]
        self.mu_eff = 1.0 / sum(w * w for w in self.weights)
        mu_eff = self.mu_eff
        self.c_sigma = (mu_eff + 2.0) / (n + mu_eff + 5.0)
        self.d_sigma = (
            1.0
            + 2.0 * max(0.0, math.sqrt((mu_eff - 1.0) / (n + 1.0)) - 1.0)
            + self.c_sigma
        )
        self.c_c = (4.0 + mu_eff / n) / (n + 4.0 + 2.0 * mu_eff / n)
        self.c_1 = 2.0 / ((n + 1.3) ** 2 + mu_eff)
        self.c_mu = min(
            1.0 - self.c_1,
            2.0 * (mu_eff - 2.0 + 1.0 / mu_eff) / ((n + 2.0) ** 2 + mu_eff),
        )
        self.chi_n = math.sqrt(n) * (1.0 - 1.0 / (4.0 * n) + 1.0 / (21.0 * n * n))
        self.p_sigma = [0.0] * n
        self.p_c = [0.0] * n
        self.cov = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        self.generation = 0
        self._decompose()
        self._ys = []

    def _decompose(self):
        values, vectors = _jacobi_eigh(self.cov)
        self.eigenvalues = [max(value, 1e-20) for value in values]
        self.basis = vectors

    def _normal(self):
        # Box-Muller from the Mersenne Twister's uniform stream: reproducible across hosts.
        u1 = 1.0 - self.rng.random()
        u2 = self.rng.random()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)

    def ask(self):
        """The generation's samples x_k = m + sigma * B D z_k (unrepaired)."""
        n = self.n
        self._ys = []
        samples = []
        for _ in range(self.lam):
            z = [self._normal() for _ in range(n)]
            dz = [math.sqrt(self.eigenvalues[i]) * z[i] for i in range(n)]
            y = [sum(self.basis[r][i] * dz[i] for i in range(n)) for r in range(n)]
            self._ys.append(y)
            samples.append([self.mean[r] + self.sigma * y[r] for r in range(n)])
        return samples

    def tell(self, keys):
        """Rank the last `ask` by `keys` (one comparable per sample, lower is better) and adapt."""
        if len(keys) != self.lam or len(self._ys) != self.lam:
            raise ValueError("tell needs one key per sample of the last ask")
        n = self.n
        order = sorted(range(self.lam), key=lambda i: (keys[i], i))
        best = [self._ys[i] for i in order[: self.mu]]
        y_w = [
            sum(self.weights[k] * best[k][r] for k in range(self.mu)) for r in range(n)
        ]
        self.mean = [self.mean[r] + self.sigma * y_w[r] for r in range(n)]
        # C^{-1/2} y_w = B D^{-1} B^T y_w
        bt_y = [sum(self.basis[r][i] * y_w[r] for r in range(n)) for i in range(n)]
        scaled = [bt_y[i] / math.sqrt(self.eigenvalues[i]) for i in range(n)]
        inv_sqrt_y = [
            sum(self.basis[r][i] * scaled[i] for i in range(n)) for r in range(n)
        ]
        scale_s = math.sqrt(self.c_sigma * (2.0 - self.c_sigma) * self.mu_eff)
        self.p_sigma = [
            (1.0 - self.c_sigma) * self.p_sigma[r] + scale_s * inv_sqrt_y[r]
            for r in range(n)
        ]
        norm_ps = math.sqrt(sum(x * x for x in self.p_sigma))
        self.generation += 1
        h_sigma = (
            1.0
            if norm_ps / math.sqrt(1.0 - (1.0 - self.c_sigma) ** (2 * self.generation))
            < (1.4 + 2.0 / (n + 1.0)) * self.chi_n
            else 0.0
        )
        scale_c = math.sqrt(self.c_c * (2.0 - self.c_c) * self.mu_eff)
        self.p_c = [
            (1.0 - self.c_c) * self.p_c[r] + h_sigma * scale_c * y_w[r]
            for r in range(n)
        ]
        delta_h = (1.0 - h_sigma) * self.c_c * (2.0 - self.c_c)
        decay = 1.0 - self.c_1 - self.c_mu
        for r in range(n):
            for c in range(n):
                rank_mu = sum(
                    self.weights[k] * best[k][r] * best[k][c] for k in range(self.mu)
                )
                self.cov[r][c] = (
                    decay * self.cov[r][c]
                    + self.c_1 * (self.p_c[r] * self.p_c[c] + delta_h * self.cov[r][c])
                    + self.c_mu * rank_mu
                )
        for r in range(n):
            for c in range(r):
                mean_rc = 0.5 * (self.cov[r][c] + self.cov[c][r])
                self.cov[r][c] = self.cov[c][r] = mean_rc
        self.sigma *= math.exp(
            (self.c_sigma / self.d_sigma) * (norm_ps / self.chi_n - 1.0)
        )
        self._decompose()
