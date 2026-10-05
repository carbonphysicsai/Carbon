"""Score-to-value alignment for any Challenge (TRACK-B-HARNESS-01, Q1).

Does a Challenge's score rank models by the quality of the decisions they
lead to? This generalises ``carbon.battery.value.divergence`` (which keeps
its own meaning for battery and is not imported here):

- Kendall τ-b and Spearman ρ between each eligible member's score (higher is
  better) and its decision value (lower is better), over members whose value
  is defined;
- the τ noise band: τ's spread over every one-seed-per-recipe panel;
- the value noise band: the largest spread of a recipe's numeric value across
  its seeds;
- conditions, in the battery record shape: GATE_ANOMALY for every ineligible
  member, and SCORE_VALUE_DIVERGENCE for X when some eligible Y decides
  clearly better yet X scores at or above Y.

"Clearly better" uses the value noise band: Y's value class is lower, or the
classes match and value(Y) + band < value(X). A value is a ``(class,
number)`` pair, as ``track_b.decision_value`` returns, or a plain number
(class 0). With no seed replicates the band is 0, so any gap fires: when in
doubt, fire.

Internal DEVELOPMENT evidence: no qualification gate, threshold or rank cut
is chosen here.
"""

from __future__ import annotations

import itertools
import math

SCHEMA = "carbon.admission-condition.v1"
RESULT_SCHEMA = "carbon.design-search.score-value-alignment.v1"


def _key(value):
    if value is None:
        return None
    if isinstance(value, tuple):
        return (int(value[0]), float(value[1]))
    return (0, float(value))


def kendall_tau_b(xs, ys):
    """Kendall's τ-b of two equal-length sequences; None if undefined."""

    if len(xs) != len(ys):
        raise ValueError("tau_lengths_differ")
    concordant = discordant = ties_x = ties_y = 0
    n = len(xs)
    for i in range(n):
        for j in range(i + 1, n):
            dx = (xs[i] > xs[j]) - (xs[i] < xs[j])
            dy = (ys[i] > ys[j]) - (ys[i] < ys[j])
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                ties_x += 1
            elif dy == 0:
                ties_y += 1
            elif dx == dy:
                concordant += 1
            else:
                discordant += 1
    denominator = math.sqrt(
        (concordant + discordant + ties_x) * (concordant + discordant + ties_y)
    )
    if denominator == 0:
        return None
    return (concordant - discordant) / denominator


def _ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def spearman_rho(xs, ys):
    """Spearman's ρ (Pearson correlation of average ranks); None if undefined."""

    if len(xs) != len(ys):
        raise ValueError("rho_lengths_differ")
    if len(xs) < 2:
        return None
    rx, ry = _ranks(list(xs)), _ranks(list(ys))
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def _negated(key):
    """A value key turned higher-is-better, for correlation with a score."""

    return (-key[0], -key[1])


def value_noise_band(members):
    """The largest spread of a recipe's numeric value across its seeds,
    within one value class; None when no recipe has two class-0 seeds."""

    by_recipe = {}
    for row in members.values():
        key = _key(row.get("value"))
        if row.get("eligible") is True and key is not None and key[0] == 0:
            by_recipe.setdefault(row["recipe"], []).append(key[1])
    spreads = [max(v) - min(v) for v in by_recipe.values() if len(v) >= 2]
    return max(spreads) if spreads else None


def _clearly_better(y, x, band):
    if y[0] != x[0]:
        return y[0] < x[0]
    return y[1] + band < x[1]


def alignment(members, *, top_k=1):
    """The alignment verdict inputs for one panel.

    ``members``: ``{member: {"score", "value", "eligible", "recipe", "kind"}}``,
    where ``score`` is the Challenge score (higher is better) and ``value`` the
    decision value (lower is better; None when unresolved).
    """

    eligible = sorted(
        m
        for m, row in members.items()
        if row.get("eligible") is True
        and isinstance(row.get("score"), (int, float))
        and _key(row.get("value")) is not None
    )
    scores = [float(members[m]["score"]) for m in eligible]
    values = [_key(members[m]["value"]) for m in eligible]
    good = [_negated(v) for v in values]
    tau = kendall_tau_b(scores, good) if len(eligible) >= 2 else None
    rho = spearman_rho(scores, good)
    band = value_noise_band(members)
    margin = 0.0 if band is None else band

    recipes = {}
    for m in eligible:
        recipes.setdefault(members[m]["recipe"], []).append(m)
    taus = []
    for panel in itertools.product(*recipes.values()):
        if len(panel) < 2:
            continue
        t = kendall_tau_b(
            [float(members[m]["score"]) for m in panel],
            [_negated(_key(members[m]["value"])) for m in panel],
        )
        if t is not None:
            taus.append(t)

    k = min(top_k, len(eligible))
    by_score = sorted(eligible, key=lambda m: (-float(members[m]["score"]), m))[:k]
    by_value = sorted(eligible, key=lambda m: (_key(members[m]["value"]), m))[:k]

    conditions = []
    for m in sorted(members):
        if members[m].get("eligible") is not True:
            conditions.append(
                {
                    "schema": SCHEMA,
                    "condition": "GATE_ANOMALY",
                    "member": m,
                    "kind": members[m].get("kind"),
                    "basis": "member is not eligible",
                }
            )
    for x in eligible:
        kx, sx = _key(members[x]["value"]), float(members[x]["score"])
        outranked = [
            y
            for y in eligible
            if y != x
            and _clearly_better(_key(members[y]["value"]), kx, margin)
            and sx >= float(members[y]["score"])
        ]
        if outranked:
            conditions.append(
                {
                    "schema": SCHEMA,
                    "condition": "SCORE_VALUE_DIVERGENCE",
                    "member": x,
                    "kind": members[x].get("kind"),
                    "scored_at_or_above": outranked,
                    "value": list(kx),
                    "value_noise_band": band,
                    "basis": (
                        "Challenge score against Track B decision value at an "
                        "equal search budget; band from seed replicates"
                    ),
                }
            )
    return {
        "schema": RESULT_SCHEMA,
        "members_ranked": eligible,
        "excluded_unresolved_or_ineligible": sorted(set(members) - set(eligible)),
        "kendall_tau_b": tau,
        "spearman_rho": rho,
        "tau_noise_band": {
            "band": (max(taus) - min(taus)) if taus else None,
            "tau_min": min(taus) if taus else None,
            "tau_max": max(taus) if taus else None,
            "panels": len(taus),
        },
        "value_noise_band": band,
        "top_k": {
            "k": k,
            "by_score": by_score,
            "by_value": by_value,
            "overlap": len(set(by_score) & set(by_value)),
        },
        "conditions": conditions,
    }
