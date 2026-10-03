"""EV4's pre-registered hypotheses, computed from an engineering-value result.

The contract fixes everything here before any solve
(`acceptance.paired_comparison` and `acceptance.hypotheses`):

- **H1 (primary, paired).** Δτ = τ(proposed) − τ(deciding). Each τ is Kendall
  tau-b between a rule's scores of the eligible reconstructed members and
  their negated mean decision loss on the verification conditions. The
  interval is a percentile bootstrap that resamples members and conditions
  jointly, with the contract's replicate count and RNG seed. An interval that
  excludes 0 decides H1 in its sign's direction; otherwise H1 is UNRESOLVED,
  never "no difference".
- **H2** is EV2's boundary-optimist check, already in the result's summary;
  it is reported here for the two rules of H1.
- **H3 (the real-model blind spot).** Eligible reconstructed members that
  select a protocol the reference verifies INFEASIBLE on any verification
  condition, each with its rank under both rules.

`group_difference_bootstrap` is EV5's H2 interval (OWNER-EV5-Q4-01).

Nothing here chooses a number. Members or replicates where a quantity is
undefined are counted and reported, never imputed.
"""

from __future__ import annotations

import math

import numpy as np

from . import contract as ev
from .decision import kendall_tau_b

PROPOSED_BETTER = "PROPOSED_RANKS_BETTER"
DECIDING_BETTER = "DECIDING_RANKS_BETTER"
UNRESOLVED = "UNRESOLVED"


def tau_b(xs, ys):
    """Kendall tau-b, vectorized; equal to `decision.kendall_tau_b`."""
    x = np.asarray(xs, float)
    y = np.asarray(ys, float)
    n = len(x)
    if n < 2:
        return None
    upper = np.triu_indices(n, 1)
    dx = np.sign(x[:, None] - x[None, :])[upper]
    dy = np.sign(y[:, None] - y[None, :])[upper]
    product = dx * dy
    concordant = int(np.count_nonzero(product > 0))
    discordant = int(np.count_nonzero(product < 0))
    ties_x = int(np.count_nonzero((dx == 0) & (dy != 0)))
    ties_y = int(np.count_nonzero((dx != 0) & (dy == 0)))
    denominator = math.sqrt(
        (concordant + discordant + ties_x) * (concordant + discordant + ties_y)
    )
    if denominator == 0:
        return None
    return (concordant - discordant) / denominator


def _numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def eligible_real(results):
    members = results["summary"]["members"]
    return sorted(
        m
        for m, row in members.items()
        if row["kind"] == "RECONSTRUCTED" and row["eligible"] is True
    )


def verification_scenarios(contract):
    return [s["id"] for s in ev.scenarios(contract, "verification")]


def loss_matrix(results, members, scenarios):
    """Decision loss per member and verification condition; NaN where the
    loss is undefined (unresolved or unavailable at the reference)."""
    out = np.full((len(members), len(scenarios)), np.nan)
    for i, member in enumerate(members):
        for j, scenario in enumerate(scenarios):
            loss = results["decisions"][member][scenario]["outcome"]["decision_loss"]
            if loss is not None:
                out[i, j] = float(loss)
    return out


def paired_bootstrap(proposed, deciding, losses, *, replicates, seed, level):
    """The paired Δτ and its percentile interval.

    `proposed`, `deciding`: scores per member (higher is better); `losses`:
    member × condition matrix (NaN = undefined). Each replicate draws members
    and conditions with replacement, independently; a member's loss is its
    mean over the drawn conditions where defined. A member with no defined
    loss in a replicate is left out of that replicate for both rules; a
    replicate where either τ is undefined is skipped and counted.
    """
    a = np.asarray(proposed, float)
    b = np.asarray(deciding, float)
    losses = np.asarray(losses, float)
    n, k = losses.shape

    def mean_loss(matrix):
        defined = ~np.isnan(matrix)
        counts = defined.sum(axis=1)
        sums = np.where(defined, matrix, 0.0).sum(axis=1)
        keep = counts > 0
        return keep, np.divide(sums, np.maximum(counts, 1))

    keep, loss = mean_loss(losses)
    point_a = kendall_tau_b(a[keep].tolist(), (-loss[keep]).tolist())
    point_b = kendall_tau_b(b[keep].tolist(), (-loss[keep]).tolist())
    point = None if point_a is None or point_b is None else point_a - point_b
    rng = np.random.default_rng(seed)
    deltas = []
    skipped = 0
    for _ in range(replicates):
        rows = rng.integers(0, n, n)
        cols = rng.integers(0, k, k)
        keep_r, loss_r = mean_loss(losses[np.ix_(rows, cols)])
        y = -loss_r[keep_r]
        ta = tau_b(a[rows][keep_r], y)
        tb = tau_b(b[rows][keep_r], y)
        if ta is None or tb is None:
            skipped += 1
            continue
        deltas.append(ta - tb)
    if not deltas:
        low = high = None
    else:
        tail = (1.0 - level) / 2.0
        low, high = (float(v) for v in np.quantile(deltas, [tail, 1.0 - tail]))
    if low is None:
        decision = UNRESOLVED
    elif low > 0:
        decision = PROPOSED_BETTER
    elif high < 0:
        decision = DECIDING_BETTER
    else:
        decision = UNRESOLVED
    return {
        "tau_proposed": point_a,
        "tau_deciding": point_b,
        "delta_tau": point,
        "interval": [low, high],
        "level": level,
        "replicates": replicates,
        "replicates_skipped": skipped,
        "rng_seed": seed,
        "members": int(keep.sum()),
        "conditions": k,
        "decision": decision,
    }


def group_difference_bootstrap(losses, failed, *, replicates, seed, level):
    """EV5 H2: mean verification decision loss of the members the gate FAILs
    minus that of the members it PASSes, with a percentile interval.

    `losses`: member × condition matrix (NaN = undefined); `failed`: one
    Boolean per member. Each replicate resamples the FAIL members and the PASS
    members separately, each group to its own size (stratified, so every
    replicate has both groups), and the conditions jointly for all members. A
    member's loss is its mean over the drawn conditions where defined; a
    member with none is left out of that replicate, and a replicate where
    either group is then empty is skipped and counted. Either group empty
    leaves the difference and its interval undefined.
    """
    losses = np.asarray(losses, float)
    failed = np.asarray(failed, bool)
    n, k = losses.shape
    if failed.shape != (n,):
        raise ValueError("one verdict per member")

    def group_means(matrix, mask):
        defined = ~np.isnan(matrix)
        counts = defined.sum(axis=1)
        means = np.where(defined, matrix, 0.0).sum(axis=1) / np.maximum(counts, 1)
        keep = counts > 0
        a, b = means[keep & mask], means[keep & ~mask]
        if not len(a) or not len(b):
            return None
        return float(a.mean() - b.mean())

    fail_rows = np.flatnonzero(failed)
    pass_rows = np.flatnonzero(~failed)
    point = group_means(losses, failed)
    out = {
        "difference": point,
        "members_failed": len(fail_rows),
        "members_passed": len(pass_rows),
        "level": level,
        "replicates": replicates,
        "rng_seed": seed,
    }
    if not len(fail_rows) or not len(pass_rows):
        return {
            **out,
            "interval": [None, None],
            "replicates_skipped": replicates,
            "excludes_zero": False,
        }
    rng = np.random.default_rng(seed)
    labels = np.r_[np.ones(len(fail_rows), bool), np.zeros(len(pass_rows), bool)]
    values, skipped = [], 0
    for _ in range(replicates):
        rows = np.r_[
            rng.choice(fail_rows, len(fail_rows)), rng.choice(pass_rows, len(pass_rows))
        ]
        cols = rng.integers(0, k, k)
        value = group_means(losses[np.ix_(rows, cols)], labels)
        if value is None:
            skipped += 1
            continue
        values.append(value)
    if values:
        tail = (1.0 - level) / 2.0
        low, high = (float(v) for v in np.quantile(values, [tail, 1.0 - tail]))
    else:
        low = high = None
    return {
        **out,
        "interval": [low, high],
        "replicates_skipped": skipped,
        "excludes_zero": low is not None and (low > 0 or high < 0),
    }


def ranks(results, members, rule):
    """Competition rank (1 = best) among `members` under `rule`; None when
    the member's score is not numeric."""
    scores = {m: results["rule_scores"][m].get(rule) for m in members}
    numeric = [s for s in scores.values() if _numeric(s)]
    return {
        m: (1 + sum(1 for v in numeric if v > s)) if _numeric(s) else None
        for m, s in scores.items()
    }


def evaluate(contract, results):
    """H1, H2 and H3 for a result produced under `contract`."""
    paired = contract["acceptance"]["paired_comparison"]
    proposed, deciding = paired["proposed_rule"], paired["deciding_rule"]
    scenarios = verification_scenarios(contract)
    pool = eligible_real(results)
    excluded = sorted(
        m
        for m in pool
        if not (
            _numeric(results["rule_scores"][m].get(proposed))
            and _numeric(results["rule_scores"][m].get(deciding))
        )
    )
    members = [m for m in pool if m not in excluded]
    h1 = paired_bootstrap(
        [results["rule_scores"][m][proposed] for m in members],
        [results["rule_scores"][m][deciding] for m in members],
        loss_matrix(results, members, scenarios),
        replicates=paired["replicates"],
        seed=paired["rng_seed"],
        level=paired["level"],
    )
    h1.update(
        {
            "proposed_rule": proposed,
            "deciding_rule": deciding,
            "excluded_not_numeric": excluded,
        }
    )
    check = results["summary"].get("boundary_optimist_check") or {}
    h2 = {rule: check.get(rule) for rule in (proposed, deciding)}
    rank = {rule: ranks(results, pool, rule) for rule in (proposed, deciding)}
    offenders = []
    for member in pool:
        conditions = [
            s
            for s in scenarios
            if results["decisions"][member][s]["outcome"]["kind"]
            == "SELECTED_INFEASIBLE"
        ]
        if conditions:
            offenders.append(
                {
                    "member": member,
                    "false_acceptance_conditions": conditions,
                    "rank": {rule: rank[rule][member] for rule in rank},
                }
            )
    h3 = {
        "eligible_members": len(pool),
        "members_with_false_acceptance": len(offenders),
        "members": offenders,
        "rank_basis": "competition rank among eligible reconstructed members, 1 = best",
    }
    return {
        "H1": h1,
        "H2": h2,
        "H3": h3,
        "continuity": {
            "chosen_rule_on_development": results["summary"][
                "chosen_rule_on_development"
            ],
            "chosen_rule_tau_verification": results["summary"][
                "chosen_rule_tau_verification"
            ],
        },
    }
