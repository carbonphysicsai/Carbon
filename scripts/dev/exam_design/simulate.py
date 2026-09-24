"""Cheap statistical simulations that supplement the physical campaign.

These are **simulations**, reported separately from measured model results.
Their inputs are measured per-case errors; their assumptions are stated here
and repeated in the report:

A. ``ranking_reliability`` - for two models, how often does a screening pool of
   ``n`` cases order them the same way as the full fresh set, and how often does
   it separate two *equal-quality* models (two seeds of one recipe) by more than
   the equivalence margin? Assumes cases are exchangeable draws from the
   challenge population; resampling above the available case count is marked
   as extrapolation.

B. ``seed_mixing_attack`` - an adaptive submitter holding two equal-quality
   prediction sets (two seeds) submits mixtures: each submission switches a
   random half of the active pool's cases to the other seed and keeps the switch
   if the reported pool score improved. Only the aggregate pool score is fed
   back, as in the exam. Nothing about the fresh cases is learned, so any pool
   gain is pure optimism. Rotation after ``k`` admitted submissions replaces the
   oldest batch, discarding what was learned about it.

   This is a scripted attacker, not an autonomous agent; it bounds what a simple
   feedback-driven strategy extracts and says nothing about what an adaptive
   agent would find.
"""

from __future__ import annotations

import numpy as np


def ranking_reliability(err_a: np.ndarray, err_b: np.ndarray, sizes, margin: float, reps=4000, seed=0) -> dict:
    """``err_a``, ``err_b``: paired per-case errors on the same cases (a pool larger than any n)."""
    rng = np.random.default_rng(seed)
    full = float(np.mean(err_b - err_a))
    out = {"full_mean_delta": full, "n_available": int(err_a.size), "sizes": {}}
    for n in sizes:
        idx = rng.integers(0, err_a.size, size=(reps, n))
        d = (err_b[idx] - err_a[idx]).mean(1)
        out["sizes"][int(n)] = {
            "same_order_as_full": float(np.mean(np.sign(d) == np.sign(full))),
            "separated_beyond_margin": float(np.mean(np.abs(d) > margin)),
            "sd_of_delta": float(d.std()),
            "extrapolated": bool(n > err_a.size),
        }
    return out


def seed_mixing_attack(err_s1: np.ndarray, err_s2: np.ndarray, batch_size: int, rotate_after: int,
                       submissions: int, reps=400, seed=0) -> dict:
    """Pool-score optimism an aggregate-feedback attacker extracts, under rotation.

    ``err_s1``/``err_s2``: per-case errors of two equal-quality prediction sets over
    a large case supply; batches are drawn from it without replacement per rep.
    Returns the mean final pool-score gain (the attacker's advantage on screening)
    and the same quantity as a fraction of the pool's mean error.
    """
    rng = np.random.default_rng(seed)
    n_batches_needed = 3 + submissions // max(rotate_after, 1) + 1
    need = n_batches_needed * batch_size
    gains, rel = [], []
    for _ in range(reps):
        idx = rng.choice(err_s1.size, size=need, replace=need > err_s1.size)
        e1, e2 = err_s1[idx], err_s2[idx]
        choice = np.zeros(need, bool)  # False -> seed 1
        active = list(range(3))
        nxt = 3
        since = 0

        def pool_ids():
            return np.concatenate([np.arange(b * batch_size, (b + 1) * batch_size) for b in active])

        def score(ch, ids):
            return np.where(ch[ids], e2[ids], e1[ids]).mean()

        start = None
        for _s in range(submissions):
            ids = pool_ids()
            if start is None:
                start = score(np.zeros(need, bool), ids)
            cur = score(choice, ids)
            trial = choice.copy()
            flip = ids[rng.random(ids.size) < 0.5]
            trial[flip] = ~trial[flip]
            if score(trial, ids) < cur:
                choice = trial
            since += 1
            if since >= rotate_after and (nxt + 1) * batch_size <= need:
                active = active[1:] + [nxt]
                nxt += 1
                since = 0
        ids = pool_ids()
        honest = score(np.zeros(need, bool), ids)
        final = score(choice, ids)
        gains.append(honest - final)
        rel.append((honest - final) / honest)
    return {"batch_size": batch_size, "rotate_after": rotate_after, "submissions": submissions,
            "mean_gain": float(np.mean(gains)), "p90_gain": float(np.quantile(gains, 0.9)),
            "mean_relative_gain": float(np.mean(rel)), "reps": reps,
            "assumption": "aggregate score feedback only; attacker mixes two equal-quality seed predictions"}
