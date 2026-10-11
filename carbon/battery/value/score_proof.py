"""The battery score proof (SCORE-PROOF-01): does a registered scoring rule rank
members by the value of their engineering decisions, at every construction
level, and does it resist gaming? Built on `score_tuning`. It retrains
nothing, adopts nothing and changes no rule, gate or reward.

For each registered candidate rule (the rule in force first), at each level
and pooled:
- **tau**: Kendall tau-b between score rank and decision-value rank, with a
  bootstrap 95 % interval. Members are resampled by recipe, so a recipe's
  seeds move together. The paired bootstrap interval of tau minus the rule in
  force's tau uses the same resamples.
- **known-bad in the top half**: the known-bad controls and the adversarial
  members that rank in the top half by score.
- **top-1 regret**: the decision loss of the top-scoring member minus the best
  in the pool.
- **gate recall**: the share of the known-unsafe members the candidate's gate
  fails. The target is every one. It is None for a candidate without a gate;
  the unsafe members' ranks are reported either way. A pre-registered check:
  a gate that misses any unsafe member is FAIL, and the report names the
  cutoff range that would catch every one (`catching_cutoff`), without
  picking a cutoff.
- **fold stability**: tau on each of K folds of the decision scenarios (the
  value side) and, when the caller supplies per-fold legs, on each of K
  folds of the scoring cases (the score side), with their range and
  standard deviation.
- **adversarial divergence**: each adversarial member that scores at or
  above a member whose decision value is better by more than the value
  noise band, that is, a score raised without value. The target is none.

**A rule with missing legs.** If any member of a pool has no raw score under
a rule (for example a leg the panel did not supply), that rule's ranking
metrics on that pool are withheld (`INCOMPLETE_LEGS`; an eligible member
without a raw score), never computed over
the members that happen to have one. A gate still floors only failures, so a
partial panel would otherwise rank the failures alone. Gate recall is still
reported.

Aggregates only: member names appear only where they are the registered
controls, adversarial or unsafe members, never case or reference data. The
cutoffs and the choice of rule stay the owner's (HUMAN_INPUT).
"""

from __future__ import annotations

import random
import statistics

from carbon.design_search import score_value

from . import admissibility
from . import score_candidates_b1 as b1
from . import score_tuning as st

SCHEMA = "carbon.battery.score-proof.v1"
POOLED = "pooled"
BOOTSTRAP = 2000
FOLDS = 5
SEED = 20261010


def _tau(scores, values, members):
    return b1._tau(scores, values, members)


def _interval(xs):
    return b1._interval(xs)


def _ranked(scores, members):
    return sorted(
        (m for m in members if scores.get(m) is not None), key=lambda m: (-scores[m], m)
    )


def tau_b(x, y):
    """Kendall tau-b of two numpy arrays, exactly `score_value.kendall_tau_b`
    (joint ties excluded), vectorized for the bootstrap."""
    import numpy as np

    i, j = np.triu_indices(len(x), 1)
    dx, dy = np.sign(x[i] - x[j]), np.sign(y[i] - y[j])
    both = (dx != 0) & (dy != 0)
    cd = int(both.sum())
    tx = int(((dx == 0) & (dy != 0)).sum())
    ty = int(((dy == 0) & (dx != 0)).sum())
    denominator = ((cd + tx) * (cd + ty)) ** 0.5
    if denominator == 0:
        return None
    return float((dx * dy)[both].sum() / denominator)


def tie_counts(scores, values, members):
    """The point tau's pair accounting on the usable members."""
    import numpy as np

    usable = [
        m for m in members if scores.get(m) is not None and values.get(m) is not None
    ]
    x = np.asarray([scores[m] for m in usable], float)
    y = -np.asarray([values[m] for m in usable], float)
    i, j = np.triu_indices(len(usable), 1)
    dx, dy = np.sign(x[i] - x[j]), np.sign(y[i] - y[j])
    return {
        "usable_members": len(usable),
        "pairs": len(i),
        "score_ties": int(((dx == 0) & (dy != 0)).sum()),
        "value_ties": int(((dy == 0) & (dx != 0)).sum()),
        "double_ties": int(((dx == 0) & (dy == 0)).sum()),
    }


def bootstrap(
    scores, base_scores, losses, recipe_of, members, *, n=BOOTSTRAP, seed=SEED
):
    """Crossed recipe x decision-question resampling (SCORE-PROOF-DESIGN-01).

    `losses` maps each member to its decision losses on the pool's common
    resolved mask, one per question. Each replicate draws recipe clusters (a
    recipe's seeds move together; a recipe drawn twice appears twice) and,
    independently, questions with replacement, and recomputes every member's
    value from the drawn questions. The scoring cases are fixed: the
    intervals are conditional on the scoring set. Returns the joint 95 %
    interval of tau and of the paired delta against the rule in force, the
    recipe-only and question-only sensitivity intervals, and the fraction of
    replicates where tau was undefined (never counted as 0)."""
    import numpy as np

    usable = [m for m in members if scores.get(m) is not None and m in losses]
    groups = {}
    for k, m in enumerate(usable):
        groups.setdefault(recipe_of[m], []).append(k)
    keys = sorted(groups)
    if len(keys) < 2:
        return None
    s = np.asarray([scores[m] for m in usable], float)
    loss = np.asarray([losses[m] for m in usable], float)
    q = loss.shape[1]
    paired = all(base_scores.get(m) is not None for m in usable)
    b = np.asarray([base_scores[m] for m in usable], float) if paired else None
    rng = random.Random(seed)
    every_member = np.arange(len(usable))
    every_question = np.arange(q)

    def draw(recipes, questions):
        rows = (
            np.asarray(
                [k for key in (rng.choice(keys) for _ in keys) for k in groups[key]]
            )
            if recipes
            else every_member
        )
        cols = (
            np.asarray([rng.randrange(q) for _ in range(q)])
            if questions
            else every_question
        )
        return rows, -loss[np.ix_(rows, cols)].mean(axis=1)

    out = {"replicates": n, "questions": q, "scoring_cases": "fixed (conditional)"}
    for mode, recipes, questions, count in (
        ("joint", True, True, n),
        ("recipe_only", True, False, max(1, n // 4)),
        ("question_only", False, True, max(1, n // 4)),
    ):
        taus, deltas = [], []
        for _ in range(count):
            rows, value = draw(recipes, questions)
            tau = tau_b(s[rows], value)
            taus.append(tau)
            if paired and mode == "joint":
                tb = tau_b(b[rows], value)
                deltas.append(None if tau is None or tb is None else tau - tb)
        out[mode] = _interval(taus)
        if mode == "joint":
            out["undefined_fraction"] = sum(x is None for x in taus) / count
            out["delta_joint"] = _interval(deltas) if paired else None
    return out


def _spread(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {
        "values": xs,
        "min": min(xs),
        "max": max(xs),
        "sd": statistics.pstdev(xs) if len(xs) > 1 else 0.0,
    }


def scenario_folds(results, members, k=FOLDS, split="development"):
    """Decision values on each of `k` folds of the resolved scenarios."""
    _values, mask, _ = st.decision_values(results, members, split)
    folds = [mask[i::k] for i in range(k)]
    decisions = results["decisions"]
    return [
        {
            m: statistics.fmean(
                decisions[m][s]["outcome"]["decision_loss"] for s in fold
            )
            for m in members
        }
        for fold in folds
        if fold
    ]


def catching_cutoff(gate, measures):
    """The cutoffs on `gate`'s measure that fail every unsafe member, from the
    members' measured values: FAIL is `measured >= cutoff` ("at_or_above") or
    `measured > cutoff` ("exceeds"), and an unmeasured member always fails.
    Reported, never picked."""
    measured = [m for m in measures if m is not None]
    if not measured:
        return {"any_cutoff": True}
    lowest = min(measured)
    if gate.get("comparison", st.COMPARISONS[0]) == "exceeds":
        return {"measure": gate["measure"], "cutoff_below": lowest}
    return {"measure": gate["measure"], "cutoff_at_or_below": lowest}


def gate_check(candidate, legs, unsafe):
    """The pre-registered gate-recall check for one candidate over the
    unsafe members: PASS, FAIL (with the catching cutoff) or NO_GATE."""
    if candidate.gate is None:
        return {"status": "NO_GATE"}
    if not unsafe:
        return {"status": "NO_UNSAFE_MEMBER"}
    verdicts = {u: st.gate_verdict(candidate, legs[u]) for u in unsafe}
    missed = sorted(u for u, v in verdicts.items() if v != admissibility.FAIL)
    if not missed:
        return {"status": "PASS"}
    return {
        "status": "FAIL",
        "missed": missed,
        "cutoff_in_force": candidate.gate["cutoff"],
        "catching_cutoff": catching_cutoff(
            candidate.gate,
            [legs[u]["gates"][candidate.gate["measure"]] for u in unsafe],
        ),
    }


def adversarial_divergence(scores, values, members, adversarial, band):
    """Adversarial members that score at or above a member of better value
    (beyond `band`), with how many such members each one outranks."""
    margin = 0.0 if band is None else band
    usable = [
        m for m in members if scores.get(m) is not None and values.get(m) is not None
    ]
    out = {}
    for x in adversarial:
        if x not in usable:
            continue
        beaten = [
            y
            for y in usable
            if y != x and values[y] + margin < values[x] and scores[x] >= scores[y]
        ]
        if beaten:
            out[x] = len(beaten)
    return out


def level_report(
    scores,
    base_scores,
    verdicts,
    values,
    recipe_of,
    members,
    *,
    known_bad=(),
    adversarial=(),
    unsafe=(),
    value_folds=(),
    case_fold_scores=(),
    n_bootstrap=BOOTSTRAP,
    unscored=(),
    purposive=(),
    losses=None,
):
    """One candidate's proof metrics on one pool of members. `unscored` are
    the members with no raw score under the candidate. `purposive` members
    (the controls and the registered roles' constructions) are placed in the
    full ranking but kept out of the primary pool that tau, its intervals,
    the folds and top-1 regret are computed on (SCORE-PROOF-DESIGN-01: they
    are falsification probes, not random recipes). `losses` are per-question
    decision losses for the crossed bootstrap."""
    members = [m for m in members if values.get(m) is not None]
    missing = sorted(set(unscored) & set(members))
    if missing:
        unsafe = [u for u in unsafe if u in members]
        return {
            "members": len(members),
            "status": "INCOMPLETE_LEGS",
            "unscored": len(missing),
            "gate_recall_unsafe": (
                None
                if not verdicts or not unsafe
                else sum(verdicts.get(u) == admissibility.FAIL for u in unsafe)
                / len(unsafe)
            ),
        }
    ranked = _ranked(scores, members)
    n = len(ranked)
    top_half = set(ranked[: n // 2]) if n else set()
    purposive = set(purposive)
    primary = [m for m in members if m not in purposive]
    gated = bool(verdicts)
    # Deployment: the top-scoring admissible real recipe. With every primary
    # member failing the gate there is none to deploy (never the floor's
    # arbitrary top member).
    deployable = [
        m
        for m in _ranked(scores, primary)
        if not gated or verdicts.get(m) != admissibility.FAIL
    ]
    top1 = deployable[0] if deployable else None
    best = min((values[m] for m in primary), default=None)
    band = score_value.value_noise_band(
        {
            m: {"value": values[m], "eligible": True, "recipe": recipe_of[m]}
            for m in members
        }
    )
    if losses is None:
        losses = {m: [values[m]] for m in primary}
    intervals = bootstrap(
        scores,
        base_scores,
        {m: losses[m] for m in primary if m in losses},
        recipe_of,
        primary,
        n=n_bootstrap,
    )
    unsafe = [u for u in unsafe if u in members]
    sensitivity = (
        None
        if intervals is None
        else {k: intervals[k] for k in ("recipe_only", "question_only")}
    )
    resampling = (
        None
        if intervals is None
        else {
            k: intervals[k]
            for k in ("replicates", "questions", "scoring_cases", "undefined_fraction")
        }
    )
    return {
        "members": len(members),
        "primary_members": len(primary),
        "status": "COMPLETE",
        "deployment": "NONE_ELIGIBLE" if top1 is None and primary else "TOP1",
        "tau": _tau(scores, values, primary),
        "tau_ci95": None if intervals is None else intervals["joint"],
        "tau_sensitivity": sensitivity,
        "bootstrap": resampling,
        "ties": tie_counts(scores, values, primary),
        "delta_tau_vs_rule_in_force_ci95": (
            None if intervals is None else intervals["delta_joint"]
        ),
        "known_bad_in_top_half": sorted(m for m in known_bad if m in top_half),
        "adversarial_in_top_half": sorted(m for m in adversarial if m in top_half),
        "top1_regret": (None if top1 is None or best is None else values[top1] - best),
        "gate_recall_unsafe": (
            None
            if not gated or not unsafe
            else sum(verdicts.get(u) == admissibility.FAIL for u in unsafe)
            / len(unsafe)
        ),
        "unsafe_ranks": {
            u: (ranked.index(u) + 1 if u in ranked else None, n) for u in unsafe
        },
        "fold_stability": {
            "scenario_folds": _spread([_tau(scores, v, primary) for v in value_folds]),
            "case_folds": _spread([_tau(s, values, primary) for s in case_fold_scores]),
        },
        "adversarial_divergence": adversarial_divergence(
            scores, values, members, [a for a in adversarial if a in members], band
        ),
        "value_noise_band": band,
    }


def prove(
    registry,
    legs,
    values,
    recipe_of,
    levels,
    *,
    results=None,
    known_bad=(),
    adversarial=(),
    unsafe=(),
    fold_legs=(),
    ids=None,
    baseline="CE",
    folds=FOLDS,
    n_bootstrap=BOOTSTRAP,
):
    """Every requested registered candidate, at each level and pooled.

    `levels` maps a member to its construction level (an int), or None for a
    level-agnostic member (a control), which joins every level's pool.
    `fold_legs` are per-case-fold legs ({member: legs} per fold).
    `results` (the development decision results) gives the scenario folds."""
    candidates, identity = registry
    ids = list(candidates) if ids is None else list(ids)
    missing = sorted(set(ids) - set(candidates))
    if missing:
        raise st.TuningError("candidate_not_registered", ",".join(missing))
    if baseline not in candidates:
        raise st.TuningError("baseline_not_registered", baseline)
    ids = list(dict.fromkeys([baseline, *ids]))
    members = sorted(m for m in legs if values.get(m) is not None)
    anchors = [m for m in members if levels.get(m) is None]
    level_ids = sorted({levels[m] for m in members if levels.get(m) is not None})
    pools = {
        f"L{lv}": sorted({*anchors, *(m for m in members if levels.get(m) == lv)})
        for lv in level_ids
    }
    pools[POOLED] = members
    value_folds = (
        {name: scenario_folds(results, pool, folds) for name, pool in pools.items()}
        if results is not None
        else {}
    )
    scored = {cid: st.candidate_scores(candidates[cid], legs, recipe_of) for cid in ids}
    unscored = {
        # Eligible yet unscored: a leg the panel did not supply. An ineligible
        # member's missing score is the rule's own verdict, not a gap.
        cid: [
            m
            for m in members
            if legs[m]["eligible"] and st.score_member(candidates[cid], legs[m]) is None
        ]
        for cid in ids
    }
    fold_scores = {
        cid: [
            st.candidate_scores(candidates[cid], fl, recipe_of)[0] for fl in fold_legs
        ]
        for cid in ids
    }
    purposive = set(anchors) | set(known_bad) | set(adversarial)
    pool_losses = {}
    for name, pool in pools.items():
        if results is None:
            pool_losses[name] = None
            continue
        _v, mask, _o = st.decision_values(results, pool)
        decisions = results["decisions"]
        pool_losses[name] = {
            m: [decisions[m][s]["outcome"]["decision_loss"] for s in mask] for m in pool
        }
    report, gate_checks = {}, {}
    for cid in ids:
        scores, verdicts = scored[cid]
        gate_checks[cid] = gate_check(
            candidates[cid], legs, [u for u in unsafe if u in members]
        )
        report[cid] = {
            name: level_report(
                scores,
                scored[baseline][0],
                verdicts,
                values,
                recipe_of,
                pool,
                known_bad=known_bad,
                adversarial=adversarial,
                unsafe=unsafe,
                value_folds=value_folds.get(name, ()),
                case_fold_scores=fold_scores[cid],
                n_bootstrap=n_bootstrap,
                unscored=unscored[cid],
                purposive=purposive,
                losses=pool_losses[name],
            )
            for name, pool in pools.items()
        }
    return {
        "schema": SCHEMA,
        "registry": identity,
        "rule_in_force": baseline,
        "levels": {name: len(pool) for name, pool in pools.items()},
        "candidates": report,
        "gate_recall_check": gate_checks,
        "targets": {
            "known_bad_in_top_half": 0,
            "gate_recall_unsafe": 1.0,
            "adversarial_divergence": 0,
        },
        "threshold": "HUMAN_INPUT: the owner adopts a rule and picks its cutoffs",
        "claims": "DEVELOPMENT evidence; nothing adopted; no rule, gate or reward changed",
    }


# --- selection kept apart from proof ---------------------------------------------------
SPLIT_SCHEMA = "carbon.battery.score-proof-split.v1"
SELECTION, CONFIRMATION = "selection", "confirmation"
PROVEN, UNPROVEN = "PROVEN", "UNPROVEN"


def side(salt, kind, key):
    """`selection` or `confirmation` for one case or recipe, by the
    registered hash rule (`proof-split-v1.json`)."""
    import hashlib

    h = hashlib.sha256(f"{salt}:{kind}:{key}".encode()).hexdigest()
    return SELECTION if int(h[:8], 16) % 2 == 0 else CONFIRMATION


def split_cases(split, case_ids, phase):
    return [c for c in case_ids if side(split["salt"], "case", c) == phase]


def split_members(split, members, recipe_of, levels, anchors, phase):
    """The phase's members: anchors always; within a level holding at least
    the registered minimum of recipes, one side of the recipe split; a
    smaller level keeps every member. Returns (members, split levels)."""
    anchors = set(anchors)
    by_level = {}
    for m in members:
        if m not in anchors and levels.get(m) is not None:
            by_level.setdefault(levels[m], set()).add(recipe_of[m])
    split_levels = sorted(
        lv
        for lv, recipes in by_level.items()
        if len(recipes) >= split["minimum_recipes"]
    )
    kept = [
        m
        for m in members
        if m in anchors
        or levels.get(m) is None
        or levels[m] not in split_levels
        or side(split["salt"], "recipe", recipe_of[m]) == phase
    ]
    return kept, split_levels


def verdict(report, rule, minimum_level_members=10):
    """PROVEN only when the chosen rule meets every registered confirmation
    criterion, pooled and at each level with enough members; else UNPROVEN
    with each failed criterion named."""
    failed = []
    check = report["gate_recall_check"].get(rule, {})
    for level, r in report["candidates"][rule].items():
        if level != POOLED and r["members"] < minimum_level_members:
            continue

        def fail(what, level=level):
            failed.append(f"{level}: {what}")

        if r.get("status") != "COMPLETE":
            fail("incomplete legs")
            continue
        ci = r["tau_ci95"]
        if ci is None or ci[0] <= 0:
            fail("tau interval does not exclude 0")
        if r["known_bad_in_top_half"]:
            fail("known-bad member in the top half")
        if r["adversarial_in_top_half"]:
            fail("adversarial member in the top half")
        status = check.get("status")
        if status == "FAIL":
            fail("gate misses an unsafe member")
        elif status == "NO_GATE" and any(
            rank is None or 2 * rank <= n for rank, n in r["unsafe_ranks"].values()
        ):
            fail("no gate, and an unsafe member is not in the bottom half")
        if r["adversarial_divergence"]:
            fail("adversarial divergence")
        for kind in ("scenario_folds", "case_folds"):
            spread = r["fold_stability"][kind]
            if spread is not None and spread["min"] <= 0:
                fail(f"a {kind.replace('_', ' ')} tau is not above 0")
    return {"rule": rule, "verdict": UNPROVEN if failed else PROVEN, "failed": failed}
