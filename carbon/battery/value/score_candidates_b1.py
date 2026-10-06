"""SR-B1: battery score candidates, computed exactly as registered.

The definitions are in `.agent/tickets/SR-B1_battery_score_candidates.md`,
committed and pushed (7c355f2f) before this module computed anything. This is
DEVELOPMENT evidence only:
- the frozen rules and EV5 are untouched;
- frozen modules (`admissibility`, `margins`, `ratios`, `near`, `scoring`) are
  imported, never edited;
- nothing is adopted.
"""

from __future__ import annotations

import itertools
import math
import random
import statistics

from carbon.design_search import score_value

from . import admissibility, margins, ratios
from . import scoring as sc

DECIDING = "control-exam-v1"
SR2_WEIGHTS = (0.0, 0.3, 0.6, 0.1)  # (a, r, g, m)
P1_WEIGHTS = (0.0, 0.3, 0.6, 0.0, 0.1)  # (a, r, g, m, p)
P2_WEIGHTS = (0.0, 0.3, 0.4, 0.0, 0.3)
G_CUTOFF = 1.0
ENVELOPE = {
    "c1": (0.5, 2.0),
    "c2": (0.2, 1.0),
    "t_amb_c": (5.0, 34.0),
    "soc0": (0.12, 0.48),
}
CANDIDATES = (
    "CE",
    "SR2",
    "P1",
    "P2",
    "S-CE",
    "S-SR2",
    "S-P1",
    "P1+G1",
    "S-P1+G1",
    "S-P1+G2",
    "S-SR2+G1",
    "CE+G1",
)
MAX_PANELS = 20000
SAMPLED_PANELS = 2000


def proximity_leg(contract, predictions, case_ids, refs):
    """p = 1 / (1 + P). P is the proximity-weighted mean optimism in bands,
    with weight 1 / (1 + |true margin|); None when any case is missing."""

    weighted = total = 0.0
    for case_id in case_ids:
        outputs, reference = predictions.get(case_id), refs[case_id].get("outputs")
        if outputs is None or reference is None:
            return None
        said = margins._margins(contract, outputs)
        truth = margins._margins(contract, reference)
        for constraint in margins.CONSTRAINTS:
            weight = 1.0 / (1.0 + abs(truth[constraint]))
            weighted += weight * max(0.0, said[constraint] - truth[constraint])
            total += weight
    return None if total == 0 else 1.0 / (1.0 + weighted / total)


def _geometric(legs, weights):
    terms = []
    for weight, leg in zip(weights, legs, strict=True):
        if weight == 0:
            continue
        if leg is None:
            return None
        if leg <= 0:
            return 0.0
        terms.append(weight * math.log(leg))
    return math.exp(sum(terms))


def envelope_ids(store, scoring_ids):
    def inside(inputs):
        return all(
            low <= inputs.get(name, math.nan) <= high
            for name, (low, high) in ENVELOPE.items()
        )

    return [c for c in scoring_ids if inside(store.refs[c].get("inputs") or {})]


def member_scores(contract, results, predictions, members, repository):
    """Each member's base legs, gate verdicts and base rule scores."""

    store, scoring_ids, _ = sc.scoring_set(repository)
    inside = envelope_ids(store, scoring_ids)
    out = {}
    for m in members:
        component = results["components"][m]
        preds = predictions[m]
        margin = margins.margin_component(contract, preds, scoring_ids, store.refs)
        p = proximity_leg(contract, preds, scoring_ids, store.refs)
        a, r, g = ratios.legs(component)
        eligible = bool(component.get("eligible"))
        legs5 = (a, r, g, None if margin is None else margin["score"], p)
        g1 = admissibility.near_optimism(contract, preds, scoring_ids, store.refs)
        g2 = admissibility.near_optimism(contract, preds, inside, store.refs)
        out[m] = {
            "CE": results["rule_scores"][m].get(DECIDING),
            "SR2": 0.0 if not eligible else _geometric(legs5[:4], SR2_WEIGHTS),
            "P1": 0.0 if not eligible else _geometric(legs5, P1_WEIGHTS),
            "P2": 0.0 if not eligible else _geometric(legs5, P2_WEIGHTS),
            "p_leg": p,
            "G1": {
                "optimism": g1,
                "verdict": admissibility.verdict(g1, threshold=G_CUTOFF),
            },
            "G2": {
                "optimism": g2,
                "verdict": admissibility.verdict(g2, threshold=G_CUTOFF),
            },
        }
    return out, {"envelope_scoring_cases": len(inside)}


def candidate_scores(base, recipe_of):
    """Every registered candidate's score per member."""

    def stable(rule):
        by_recipe = {}
        for m, row in base.items():
            by_recipe.setdefault(recipe_of[m], []).append(row[rule])
        means = {
            r: (None if any(v is None for v in vs) else statistics.fmean(vs))
            for r, vs in by_recipe.items()
        }
        return {m: means[recipe_of[m]] for m in base}

    def gated(scores, gate):
        # A gate FAIL ranks below every member that passes (inadmissible).
        # `admissibility.gated` returns 0.0, which is last only for rules on
        # (0, 1]; the deciding rule scores -E < 0, where 0.0 would rank a
        # FAIL first. So failures get one less than the panel's lowest score.
        finite = [s for s in scores.values() if s is not None]
        floor = (min(finite) if finite else 0.0) - 1.0
        return {
            m: (
                None
                if s is None
                else (floor if base[m][gate]["verdict"] == "FAIL" else s)
            )
            for m, s in scores.items()
        }

    plain = {
        rule: {m: base[m][rule] for m in base} for rule in ("CE", "SR2", "P1", "P2")
    }
    s_ce, s_sr2, s_p1 = stable("CE"), stable("SR2"), stable("P1")
    table = {
        "CE": plain["CE"],
        "SR2": plain["SR2"],
        "P1": plain["P1"],
        "P2": plain["P2"],
        "S-CE": s_ce,
        "S-SR2": s_sr2,
        "S-P1": s_p1,
        "P1+G1": gated(plain["P1"], "G1"),
        "S-P1+G1": gated(s_p1, "G1"),
        "S-P1+G2": gated(s_p1, "G2"),
        "S-SR2+G1": gated(s_sr2, "G1"),
        "CE+G1": gated(plain["CE"], "G1"),
    }
    assert tuple(table) == CANDIDATES
    return table


def _tau(scores, values, names):
    usable = [
        n for n in names if scores.get(n) is not None and values.get(n) is not None
    ]
    if len(usable) < 2:
        return None
    return score_value.kendall_tau_b(
        [scores[n] for n in usable], [-values[n] for n in usable]
    )


def _interval(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    return [xs[int(0.025 * (len(xs) - 1))], xs[math.ceil(0.975 * (len(xs) - 1))]]


def seed_panels(recipe_of, members):
    by_recipe = {}
    for m in members:
        by_recipe.setdefault(recipe_of[m], []).append(m)
    groups = [sorted(v) for _, v in sorted(by_recipe.items())]
    count = math.prod(len(g) for g in groups)
    if count <= MAX_PANELS:
        return [list(p) for p in itertools.product(*groups)], count, "ALL"
    rng = random.Random(0)
    return (
        [[rng.choice(g) for g in groups] for _ in range(SAMPLED_PANELS)],
        count,
        "SAMPLED_2000_SEED_0",
    )


def analyse(table, values, recipe_of, members, one_seed):
    panels, count, mode = seed_panels(recipe_of, members)
    taus = {c: [_tau(table[c], values, p) for p in panels] for c in CANDIDATES}
    out = {}
    # The value band for divergence: the largest seed-to-seed spread of a
    # recipe's decision value (score_value's band). score_value.alignment is
    # not called: its tau band enumerates every one-seed-per-recipe panel,
    # which is intractable on EV4's 80 recipes; the registered seed band above
    # replaces it.
    band = score_value.value_noise_band(
        {
            m: {"value": values[m], "eligible": True, "recipe": recipe_of[m]}
            for m in members
            if values[m] is not None
        }
    )
    margin = 0.0 if band is None else band
    for c in CANDIDATES:
        usable = [
            m for m in members if table[c][m] is not None and values[m] is not None
        ]
        rho = score_value.spearman_rho(
            [table[c][m] for m in usable], [-values[m] for m in usable]
        )
        divergent = sum(
            1
            for x in usable
            if any(
                y != x and values[y] + margin < values[x] and table[c][x] >= table[c][y]
                for y in usable
            )
        )

        def delta(base, c=c):
            return _interval(
                [
                    None if a is None or b is None else a - b
                    for a, b in zip(taus[c], taus[base])
                ]
            )

        d_ce, d_sr2 = delta("CE"), delta("SR2")
        out[c] = {
            "tau_one_seed": _tau(table[c], values, one_seed),
            "tau_all": _tau(table[c], values, members),
            "rho_all": rho,
            "tau_seed_band": _interval(taus[c]),
            "delta_tau_vs_CE": d_ce,
            "delta_tau_vs_SR2": d_sr2,
            "progress_vs_CE": c != "CE" and d_ce is not None and d_ce[0] > 0,
            "progress_vs_SR2": c != "SR2" and d_sr2 is not None and d_sr2[0] > 0,
            "divergence_count": divergent,
        }
    return out, {
        "seed_panels": len(panels),
        "panel_product": count,
        "mode": mode,
        "value_noise_band": band,
    }
