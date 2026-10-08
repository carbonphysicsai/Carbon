"""The study analysis: rules R1-R11 applied as written (TRAINING-BUDGET-01 slice 5).

The rules are frozen (`DECISION_RULES.md`, `DECISION_RULES_R9_R11.md`); each
function here applies one, and its test binds it to the rule's text by
example. It holds R2-R10 and the F3/F4 fits; R1 is the harness's gate
(`study.r1`) and R11 is `capacity`. Where the frozen text leaves a reading
open, the Test Lead's rulings of 2026-10-07 apply, each cited where it is used.

Every function takes records as the harness writes them
(`carbon.training-budget.study-record.v1`) and returns a document naming its
rule. Only completed records count.
"""

from __future__ import annotations

import math
import statistics

#: R5's thresholds, as written.
R5_WITHIN = 0.25
R5_SHARE = 0.95
R5_WORST = 1.5
#: R6's threshold, as written.
R6_SLOW = 1.5
#: R7's multiple, as written.
R7_MULTIPLE = 3
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400


class AnalysisRefused(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code


def _completed(records, phases):
    return [r for r in records if r["state"] == "COMPLETED" and r["phase"] in phases]


def _measured(record):
    value = record["time"]["wall_s"]
    if not (type(value) in (int, float) and value > 0):
        raise AnalysisRefused("analysis_time_missing", record["run_id"])
    return float(value)


def r5(records, predict, formulas):
    """R5: adopt a compute-cost limit if a formula predicts rebuild time within
    25% for at least 95% of Phase C and F rebuilds, and no rebuild takes more
    than 1.5 times its prediction; use the simpler formula when both pass
    (`formulas` lists them simplest first). Otherwise keep per-setting caps.

    `predict(record, formula)` is the formula's predicted seconds for the
    record, from the fit on Phases A and B only."""
    held_out = _completed(records, ("C", "F"))
    if not held_out:
        raise AnalysisRefused("analysis_r5_needs_phase_c_and_f")
    results = {}
    for formula in formulas:
        within, worst = 0, 0.0
        for record in held_out:
            predicted, measured = float(predict(record, formula)), _measured(record)
            if predicted <= 0:
                raise AnalysisRefused("analysis_prediction_not_positive", formula)
            within += abs(measured - predicted) <= R5_WITHIN * predicted
            worst = max(worst, measured / predicted)
        share = within / len(held_out)
        results[formula] = {
            "share_within_25_percent": share,
            "worst_ratio": worst,
            "passes": share >= R5_SHARE and worst <= R5_WORST,
        }
    adopted = next((f for f in formulas if results[f]["passes"]), None)
    return {
        "rule": "R5",
        "rebuilds": len(held_out),
        "formulas": results,
        "adopted": adopted,
        "outcome": "COMPUTE_COST_LIMIT" if adopted else "PER_SETTING_CAPS",
    }


def r6(records, predict, formula):
    """R6: a Phase F recipe taking more than 1.5 times its prediction gets a
    factor for its setting and is re-run; this names those settings. Whether
    a factor fixes one is the re-run's R6, and a setting no factor fixes keeps
    its own cap (the report's decision, not this function's)."""
    slow = {}
    for record in _completed(records, ("F",)):
        ratio = _measured(record) / float(predict(record, formula))
        if ratio > R6_SLOW:
            setting = record["run"]["note"]
            slow[setting] = max(slow.get(setting, 0.0), ratio)
    return {
        "rule": "R6",
        "formula": formula,
        "settings_needing_a_factor": dict(sorted(slow.items())),
    }


def r7(costliest_predicted_seconds):
    """R7: the rebuild time limit is three times the predicted time of the
    costliest allowed recipe."""
    if not (
        type(costliest_predicted_seconds) in (int, float)
        and costliest_predicted_seconds > 0
    ):
        raise AnalysisRefused("analysis_r7_prediction_malformed")
    return {
        "rule": "R7",
        "costliest_predicted_s": costliest_predicted_seconds,
        "time_limit_s": R7_MULTIPLE * costliest_predicted_seconds,
    }


def r8(records, time_target_seconds):
    """R8: rebuilds per GPU-hour at L, alone and with 2 and 4 sharing one GPU
    (Phase E), and the time target's worst case per GPU-day. A shared group
    finishes when its slowest member does."""
    phase_e = _completed(records, ("E",))
    alone = [_measured(r) for r in phase_e if r["run"]["concurrency"] == 1]
    groups = {}
    for record in phase_e:
        if record["run"]["concurrency"] > 1:
            groups.setdefault(record["run"]["group"], []).append(record)
    if not alone:
        raise AnalysisRefused("analysis_r8_needs_lone_rebuilds")
    rates = {"alone": SECONDS_PER_HOUR / statistics.mean(alone)}
    for name, members in sorted(groups.items()):
        share = members[0]["run"]["concurrency"]
        if len(members) != share:
            raise AnalysisRefused("analysis_r8_group_incomplete", name)
        rates[f"shared_{share}"] = (
            share * SECONDS_PER_HOUR / max(_measured(r) for r in members)
        )
    if not (type(time_target_seconds) in (int, float) and time_target_seconds > 0):
        raise AnalysisRefused("analysis_r8_time_target_malformed")
    return {
        "rule": "R8",
        "rebuilds_per_gpu_hour": rates,
        "worst_case_rebuilds_per_gpu_day": SECONDS_PER_DAY / time_target_seconds,
    }


# -- Fits (F3 and F4 in seconds) ----------------------------------------------
#
# The Test Lead's ruling 5 (2026-10-07): one ordinary least-squares fit per
# model family of wall time against calculated cost, its intercept the
# family's setup time, fitted on Phases A and B only. Each family's residual
# spread and its share of points outside 1.5 times are reported beside R5.


def _cost(record, unit):
    value = (record.get("calculated_cost") or {}).get(unit)
    if not (type(value) in (int, float) and value >= 0):
        raise AnalysisRefused("analysis_cost_missing", f"{record['run_id']}: {unit}")
    return float(value)


def fit(records, unit, family):
    """Per-family `{setup_s, per_unit_s, points, residual_sd,
    share_outside_1_5}`. `family(record)` names a record's model family."""
    groups = {}
    for record in _completed(records, ("A", "B")):
        groups.setdefault(family(record), []).append(
            (_cost(record, unit), _measured(record))
        )
    out = {}
    for name, points in sorted(groups.items()):
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        if len(points) < 2 or len(set(xs)) < 2:
            raise AnalysisRefused("analysis_fit_underdetermined", name)
        mx, my = statistics.mean(xs), statistics.mean(ys)
        rate = sum((x - mx) * (y - my) for x, y in points) / sum(
            (x - mx) ** 2 for x in xs
        )
        setup = my - rate * mx
        residuals = [y - (setup + rate * x) for x, y in points]
        outside = sum(
            1
            for x, y in points
            if setup + rate * x <= 0 or y / (setup + rate * x) > R5_WORST
        )
        out[name] = {
            "setup_s": setup,
            "per_unit_s": rate,
            "points": len(points),
            "residual_sd": statistics.pstdev(residuals),
            "share_outside_1_5": outside / len(points),
        }
    return {"unit": unit, "families": out}


def predictor(fits, family):
    """`predict(record, unit)` from `fit` results keyed by unit."""

    def predict(record, unit):
        row = fits[unit]["families"].get(family(record))
        if row is None:
            raise AnalysisRefused("analysis_family_not_fitted", str(family(record)))
        return row["setup_s"] + row["per_unit_s"] * _cost(record, unit)

    return predict


# -- Plateaus: R2, R3 and R9 --------------------------------------------------
#
# The Test Lead's rulings 1-3 (2026-10-07): a curve is one recipe's ladder in
# one setting (for R9, its TRAIN sizes), scored by the median over seeds. A
# recipe's plateau is the largest of its curves' plateaus; a curve still
# improving at its top has none and is reported. Plateaus are computed in
# every candidate unit; L is stated in the unit R5 adopts. The best recipes
# rank by median score at their plateau under the exam rule in force, ties
# to the lower cost.
#
# Reading "doubling the budget": between consecutive points of a curve the
# improvement is taken per doubling (the score change divided by log2 of the
# budget ratio). On a ladder whose budget doubles exactly this is the rule's
# own comparison.


def _improvement(a, b, higher_is_better):
    (budget_a, score_a), (budget_b, score_b) = a, b
    gain = (score_b - score_a) if higher_is_better else (score_a - score_b)
    return gain / math.log2(budget_b / budget_a)


def plateau(points, margin, higher_is_better):
    """The smallest budget beyond which every doubling improves the median
    score by less than half the margin, or None while the curve still
    improves at its top. `points` are (budget, median score)."""
    points = sorted(points)
    if len(points) < 2 or any(b <= 0 for b, _ in points):
        raise AnalysisRefused("analysis_curve_too_short")
    gains = [
        _improvement(points[i], points[i + 1], higher_is_better)
        for i in range(len(points) - 1)
    ]
    for i in range(len(points) - 1):
        if all(g < margin / 2 for g in gains[i:]):
            return points[i][0]
    return None


def curves(records, unit, score, *, phases=("B",), by=None):
    """{(recipe, setting): [(budget, median score)]} from completed records.
    `score(record)` is the exam score under the rule in force; `unit` is a
    calculated-cost unit, or `train_size` for R9."""
    by = by or (lambda r: r["run"]["note"])
    cells = {}
    for record in _completed(records, phases):
        key = (record["run"]["recipe"], by(record))
        if unit == "train_size":
            budget = record["run"]["train_size"]
        else:
            budget = _cost(record, unit)
        cells.setdefault(key, {}).setdefault(budget, []).append(score(record))
    return {
        key: sorted((b, statistics.median(s)) for b, s in values.items())
        for key, values in sorted(cells.items())
    }


def r2(records, unit, score, margin, higher_is_better):
    """R2 per recipe: each curve's plateau, the recipe's plateau (the
    largest), its median score there, and the curves with none."""
    per_recipe = {}
    for (recipe, setting), points in curves(records, unit, score).items():
        row = per_recipe.setdefault(recipe, {"curves": {}, "no_plateau": []})
        found = plateau(points, margin, higher_is_better)
        row["curves"][setting] = {"plateau": found, "points": points}
        if found is None:
            row["no_plateau"].append(setting)
    for row in per_recipe.values():
        found = [
            c["plateau"] for c in row["curves"].values() if c["plateau"] is not None
        ]
        row["plateau"] = max(found) if found else None
        row["score_at_plateau"] = None
        if row["plateau"] is not None:
            setting = next(
                s for s, c in row["curves"].items() if c["plateau"] == row["plateau"]
            )
            row["score_at_plateau"] = dict(row["curves"][setting]["points"])[
                row["plateau"]
            ]
    return {"rule": "R2", "unit": unit, "recipes": per_recipe}


def best(r2_result, higher_is_better, count=3):
    """The best recipes: median score at their plateau, ties to lower cost."""
    ranked = [
        (name, row)
        for name, row in r2_result["recipes"].items()
        if row["plateau"] is not None
    ]
    sign = -1 if higher_is_better else 1
    ranked.sort(
        key=lambda item: (sign * item[1]["score_at_plateau"], item[1]["plateau"])
    )
    return [name for name, _ in ranked[:count]]


def r3(
    r2_result,
    best_recipes,
    *,
    costliest_seconds=None,
    costliest_memory=None,
    sheet=None,
):
    """R3: L is twice the largest plateau among the three best recipes,
    rounded up. A best recipe with a curve that never plateaus blocks L for
    that setting (the Test Lead's ruling 1). The costliest recipe allowed at
    L must meet the sheet's time target and memory ceiling; if it does not,
    the owner chooses."""
    recipes = r2_result["recipes"]
    blocking = sorted(
        f"{name}:{setting}"
        for name in best_recipes
        for setting in recipes[name]["no_plateau"]
    )
    plateaus = [recipes[name]["plateau"] for name in best_recipes]
    if blocking or None in plateaus:
        return {
            "rule": "R3",
            "unit": r2_result["unit"],
            "limit": None,
            "blocked_by_curves_without_plateau": blocking,
        }
    checks = {}
    if sheet is not None and costliest_seconds is not None:
        checks["meets_time_target"] = costliest_seconds <= sheet.get(
            "rebuild_time_target"
        )
    if sheet is not None and costliest_memory is not None:
        checks["meets_memory_ceiling"] = costliest_memory <= sheet.get("memory_ceiling")
    return {
        "rule": "R3",
        "unit": r2_result["unit"],
        "limit": math.ceil(2 * max(plateaus)),
        "best": list(best_recipes),
        **checks,
        "owner_chooses": (not all(checks.values())) if checks else None,
    }


def r9(
    records, score, margin, higher_is_better, best_recipes, sizes, ceiling, passes=None
):
    """R9: each best recipe's data plateau over nested TRAIN sizes; D is the
    largest, rounded up to the next tested size. Data binds when D is the
    largest size the ceiling allows and the last doubling still improved by
    at least half the margin. `passes(size)` reports passes per TRAIN case
    (reported, never a threshold)."""
    sizes = sorted(s for s in sizes if s <= ceiling)
    per_recipe, plateaus, binds = {}, [], False
    found_curves = curves(
        records, "train_size", score, phases=("G",), by=lambda r: "train_size"
    )
    for name in best_recipes:
        points = found_curves.get((name, "train_size"))
        if not points or len(points) < 2:
            raise AnalysisRefused("analysis_r9_recipe_missing", name)
        found = plateau(points, margin, higher_is_better)
        last = _improvement(points[-2], points[-1], higher_is_better)
        per_recipe[name] = {"plateau": found, "points": points}
        plateaus.append(found if found is not None else points[-1][0])
        if points[-1][0] == sizes[-1] and last >= margin / 2:
            binds = True
    top = max(plateaus)
    d = next(s for s in sizes if s >= top)
    return {
        "rule": "R9",
        "recipes": per_recipe,
        "D": d,
        "data_binds": binds and d == sizes[-1],
        "passes_per_case": None if passes is None else passes(d),
    }


# -- Finalists: R4 and R10 ----------------------------------------------------
#
# The Test Lead's ruling 4 (2026-10-07): per-case predictions stay with the
# study sets on the producer host. The analysis receives the Challenge's own
# finalist-rule verdicts, never per-case values. Ruling 3: once the owner
# adopts a tuned score variant, R4 and R10 are rerun under it as a reported
# recheck (the caller passes the variant's rankings and verdicts).

IMPROVEMENT = "IMPROVEMENT"


def r4(verdict):
    """R4 from the producer's verdict: `{"best_at_L", "best_at_4L",
    "classification"}`, the classification being the Challenge's finalist
    rule comparing 4L's best with L's best on the confirmation set."""
    if not (
        type(verdict) is dict
        and {"best_at_L", "best_at_4L", "classification"} <= set(verdict)
    ):
        raise AnalysisRefused("analysis_r4_verdict_malformed")
    improvement = verdict["classification"] == IMPROVEMENT
    changed = verdict["best_at_L"] != verdict["best_at_4L"]
    return {
        "rule": "R4",
        **verdict,
        "l_binds_on_quality": improvement,
        "action": (
            "double L and repeat once, then escalate to the owner"
            if improvement
            else "none"
        ),
        "warning": (
            "the winning recipe changes between L and 4L without a significant "
            "difference"
            if changed and not improvement
            else None
        ),
    }


def r10(rankings, finalists, fractions):
    """R10: a screen at fraction f with k survivors is safe when, on every
    seed, every finalist at L is among the k best at f. `rankings[seed][f]`
    is the panel ordered best first; `finalists[seed]` is the finalist rule's
    verdict at L. s is the smallest safe f, with the smallest k that makes it
    safe; a k that keeps the whole panel screens nothing. With no safe f,
    there is no screen."""
    seeds = sorted(finalists)
    if not seeds or set(rankings) != set(seeds):
        raise AnalysisRefused("analysis_r10_seeds_mismatch")
    for f in sorted(fractions):
        if f >= 1:
            continue
        k = 0
        for seed in seeds:
            order = rankings[seed][f]
            missing = [name for name in finalists[seed] if name not in order]
            if missing:
                raise AnalysisRefused(
                    "analysis_r10_finalist_unranked", ",".join(missing)
                )
            k = max([k] + [order.index(name) + 1 for name in finalists[seed]])
        panel = min(len(rankings[s][f]) for s in seeds)
        if k < panel:
            return {"rule": "R10", "screen": {"fraction": f, "survivors": k}}
    return {
        "rule": "R10",
        "screen": None,
        "note": "no safe screen: every submission is rebuilt at L",
    }
