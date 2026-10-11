"""Public, historical battery planning audit. No Carbon imports or network.

Only three explicitly public pinned JSON blobs may be read. This is research
resampling, not a solver, rescore, v3 proof, or qualification implementation.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import platform
from statistics import NormalDist

import numpy as np

BASE = "d426cf8b3f86a20c27e4dd82593b5935d99ada1f"
INPUTS = {
    "ev4.json": ("docs/development/evidence/ev4-2026-10-01/results.json", "67ca13b966a2f6fb4b2e68b084e2909657e7ba7f"),
    "ev5.json": ("docs/development/evidence/ev5-2026-10-03/results.json", "7d6ccf75a47c2df56c66d0b223300e5fd9398512"),
    "gate.json": ("docs/development/evidence/ev5-2026-10-03/gate.json", "df128cb7c30bfa679d85f537cfe3651fc9873463"),
}
CONTROLS = ("control-boundary_optimist", "control-localized_sign_error")
METHODS = ("historical_CE", "historical_DAR", "EV5_candidate_near_gate")


def read_inputs(directory):
    data, provenance = {}, {}
    for name, (source, expected) in INPUTS.items():
        raw = (directory / name).read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if blob != expected:
            raise ValueError(f"Public input hash mismatch: {name}")
        data[name] = json.loads(raw)
        provenance[name] = {"path": source, "git_blob": blob, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "source_commit": BASE}
    return data, provenance


def recipe(member):
    return re.sub(r"-s[0-9]+$", "", member)


def tau(scores, losses, weights=None):
    """Exact tau-b; repeated cluster weights retain ties, including -inf floors."""
    i, j = np.triu_indices(len(scores), 1)
    dx = (scores[i] > scores[j]).astype(int) - (scores[i] < scores[j]).astype(int)
    # Value is minus loss: lower loss is better.
    dy = (losses[i] < losses[j]).astype(int) - (losses[i] > losses[j]).astype(int)
    w = np.ones(len(i)) if weights is None else weights[i] * weights[j]
    denominator = math.sqrt(float(w[dx != 0].sum() * w[dy != 0].sum()))
    return None if denominator == 0 else float((w * dx * dy).sum() / denominator)


def summarize(xs):
    finite = np.array([x for x in xs if x is not None], dtype=float)
    if len(finite) < 2:
        return {"defined": len(finite), "undefined": len(xs) - len(finite), "variance": None, "ci95": None}
    bounds = np.quantile(finite, [0.025, 0.975]).tolist()
    return {"defined": len(finite), "undefined": len(xs) - len(finite), "mean": float(finite.mean()), "variance": float(finite.var(ddof=1)), "ci95": bounds, "half_width95": (bounds[1] - bounds[0]) / 2}


def group_codes(keys):
    names = sorted(set(keys))
    return np.array([names.index(k) for k in keys]), len(names)


def bootstrap(scores, losses, recipe_keys, question_keys, *, replicates, seed, draw_recipes=None, draw_questions=None, modes=None):
    row_codes, m = group_codes(recipe_keys)
    col_codes, c = group_codes(question_keys)
    rng = np.random.default_rng(seed)
    out = {}
    for mode, rows, columns in modes or (("recipe_only", True, False), ("question_only", False, True), ("crossed", True, True)):
        samples = {name: [] for name in scores}
        paired = []
        for _ in range(replicates):
            wr = rng.multinomial(draw_recipes or m, np.full(m, 1 / m))[row_codes] if rows else np.ones(len(row_codes))
            wc = rng.multinomial(draw_questions or c, np.full(c, 1 / c))[col_codes] if columns else np.ones(len(col_codes))
            mean_loss = losses @ wc / wc.sum()
            ts = {name: tau(s, mean_loss, wr) for name, s in scores.items()}
            for name, t in ts.items():
                samples[name].append(t)
            paired.append(None if ts["historical_CE"] is None or ts["historical_DAR"] is None else ts["historical_DAR"] - ts["historical_CE"])
        out[mode] = {name: summarize(s) for name, s in samples.items()}
        out[mode]["DAR_minus_CE"] = summarize(paired)
    return {"recipes": m, "question_units": c, "replicates_per_mode": replicates, "modes": out}


def coefficients(b):
    out = {}
    for name in (*METHODS, "DAR_minus_CE"):
        modes = b["modes"]
        vr = modes["recipe_only"][name]["variance"]
        vq = modes["question_only"][name]["variance"]
        vj = modes["crossed"][name]["variance"]
        residual = vj - vr - vq
        out[name] = {"a_recipe": b["recipes"] * vr, "b_question": b["question_units"] * vq, "c_interaction": b["recipes"] * b["question_units"] * max(0.0, residual), "raw_residual": residual, "crossed_variance": vj}
    return out


def projected_half_width(coef, recipes, questions, z):
    return z * math.sqrt(coef["a_recipe"] / recipes + coef["b_question"] / questions + coef["c_interaction"] / (recipes * questions))


def required_recipes(coef, questions, z, h=0.15):
    allowance = (h / z) ** 2 - coef["b_question"] / questions
    return None if allowance <= 0 else max(2, math.ceil((coef["a_recipe"] + coef["c_interaction"] / questions) / allowance))


def required_questions(coef, recipes, z, h=0.15):
    allowance = (h / z) ** 2 - coef["a_recipe"] / recipes
    return None if allowance <= 0 else max(2, math.ceil((coef["b_question"] + coef["c_interaction"] / recipes) / allowance))


def binomial_tail(n, p, k):
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    return min(1.0, math.fsum(math.exp(math.lgamma(n + 1) - math.lgamma(x + 1) - math.lgamma(n - x + 1) + x * math.log(p) + (n - x) * math.log1p(-p)) for x in range(k, n + 1)))


def exact_bounds(k, n, alpha=0.05):
    if not n:
        return [None, None]
    def solve(fn, target):
        lo, hi = 0.0, 1.0
        for _ in range(55):
            mid = (lo + hi) / 2
            if fn(mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    lower = 0.0 if not k else solve(lambda p: binomial_tail(n, p, k), alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: binomial_tail(n, p, k + 1), 1 - alpha / 2)
    return [lower, upper]


def known_bad_power(p, alpha, target):
    """Weak screen only: H0 Pr(real recipe scores above bad control) <= 1/2."""
    if p <= 0.5:
        return None
    for n in range(2, 2501):
        critical = next((k for k in range(n // 2, n + 1) if binomial_tail(n, 0.5, k) <= alpha), n + 1)
        if binomial_tail(n, p, critical) >= target:
            return n
    return "MORE_THAN_2500"


def detection_count(p, target):
    if p <= 0:
        return None
    if p >= 1:
        return 1
    return math.ceil(math.log1p(-target) / math.log1p(-p))


def screens(ev5, gate, members, scores):
    groups = defaultdict(list)
    for m in members:
        groups[recipe(m)].append(m)
    output = {"control_placement": {}, "gate_recall": {}}
    real_score = {name: {r: float(np.mean(s[[members.index(m) for m in ms]])) for r, ms in groups.items()} for name, s in scores.items()}
    for control in CONTROLS:
        control_scores = {
            "historical_CE": ev5["rule_scores"][control]["control-exam-v1"],
            "historical_DAR": ev5["rule_scores"][control]["dar-p0-r100-a0"],
            "EV5_candidate_near_gate": (-math.inf if gate["verdicts"][control]["verdict"] == "FAIL" else gate["candidate_scores"][control]),
        }
        output["control_placement"][control] = {}
        for name, cs in control_scores.items():
            k = sum(s > cs for s in real_score[name].values())
            ties = sum(s == cs for s in real_score[name].values())
            p = k / len(groups)
            ci = exact_bounds(k, len(groups))
            output["control_placement"][control][name] = {"real_recipes": len(groups), "strictly_above_control": k, "ties_with_control": ties, "p_above": p, "p_ci95": ci, "count_for_80pct_weak_screen": {"low": known_bad_power(ci[1], .025, .8), "base": known_bad_power(p, .025, .8), "high": known_bad_power(ci[0], .025, .8)}, "count_for_90pct_weak_screen": known_bad_power(p, .025, .9), "count_for_80pct_across_five_levels_alpha005": known_bad_power(p, .005, .8)}
    # Unsafe is an actual SELECTED_INFEASIBLE decision, not an uncertainty or
    # abstention. A recipe is unsafe if ANY recorded seed is unsafe. Detection
    # of unsafe and gate recall remain conditional on these public questions.
    for split in ("development", "verification", "both"):
        bad, missed = set(), set()
        for r, ms in groups.items():
            unsafe_seeds = [m for m in ms if any(d["outcome"]["kind"] == "SELECTED_INFEASIBLE" and (split == "both" or d["split"] == split) for d in ev5["decisions"][m].values())]
            if unsafe_seeds:
                bad.add(r)
                if any(gate["verdicts"][m]["verdict"] != "FAIL" for m in unsafe_seeds):
                    missed.add(r)
        n, k = len(bad), len(bad - missed)
        miss_p = len(missed) / n if n else 0
        ci = exact_bounds(len(missed), n)
        prevalence_ci = exact_bounds(n, len(groups))
        output["gate_recall"][split] = {"real_recipes": len(groups), "unsafe_recipes": n, "caught_recipes": k, "missed_recipes": len(missed), "recall": k / n if n else None, "recall_ci95": exact_bounds(k, n), "unsafe_prevalence": n / len(groups), "unsafe_prevalence_ci95": prevalence_ci, "unsafe_recipes_for_80pct_miss_detection": {"low": detection_count(ci[1], .8), "base": detection_count(miss_p, .8), "high": detection_count(ci[0], .8)}, "unsafe_recipes_for_90pct_miss_detection": detection_count(miss_p, .9)}
    # A complementary design screen asks how many public questions reveal at
    # least one unsafe choice by each fixed member. This does NOT raise recall.
    bad_members = [m for m in members if any(d["outcome"]["kind"] == "SELECTED_INFEASIBLE" for d in ev5["decisions"][m].values())]
    counts = []
    for m in bad_members:
        all_q = list(ev5["decisions"][m].values())
        k = sum(d["outcome"]["kind"] == "SELECTED_INFEASIBLE" for d in all_q)
        counts.append(detection_count(k / len(all_q), .8))
    output["question_screen"] = {"members_with_any_infeasible_selection": len(bad_members), "question_denominator": len(ev5["references"]), "questions_for_80pct_detection_per_unsafe_member": {"low": min(counts), "base": int(np.median(counts)), "high": max(counts)}, "assumption": "IID question draws from empirical EV5 distribution; unresolved counted as no detected failure; no guarantee for new physics cases"}
    # Exactly the member top-half screen, retaining seed clusters and fixed
    # controls. Bounds avoid letting alphabetical tie breaking become science.
    anchor_names = sorted(m for m, v in ev5["summary"]["members"].items() if v["kind"] == "SYNTHETIC_CONTROL")
    anchor_scores = {
        "historical_CE": {m: ev5["rule_scores"][m]["control-exam-v1"] for m in anchor_names},
        "historical_DAR": {m: ev5["rule_scores"][m]["dar-p0-r100-a0"] for m in anchor_names},
        "EV5_candidate_near_gate": {m: (-math.inf if gate["verdicts"][m]["verdict"] == "FAIL" else gate["candidate_scores"][m]) for m in anchor_names},
    }
    rcodes, nr = group_codes([recipe(m) for m in members])
    rng = np.random.default_rng(2026101107)
    placement = {}
    for count in (6, 12, 25, 50, 79, 100, 150):
        weights = rng.multinomial(count, np.full(nr, 1 / nr), size=5000)[:, rcodes]
        top_half = (weights.sum(axis=1) + len(anchor_names)) // 2
        placement[str(count)] = {}
        for name, s in scores.items():
            placement[str(count)][name] = {}
            for control in CONTROLS:
                cs = anchor_scores[name][control]
                better = weights[:, s > cs].sum(axis=1) + sum(v > cs for v in anchor_scores[name].values())
                tied = weights[:, s == cs].sum(axis=1) + sum(m != control and v == cs for m, v in anchor_scores[name].items())
                guaranteed = better + tied + 1 <= top_half
                possible = better + 1 <= top_half
                placement[str(count)][name][control] = {"probability_top_half_lower": float(guaranteed.mean()), "probability_top_half_upper": float(possible.mean())}
    output["member_top_half_cluster_projection"] = {"replicates": 5000, "fixed_anchors": len(anchor_names), "by_real_recipe_count": placement, "meaning": "Conditional probability of detecting a top-half violation on the empirical recipe distribution; not power for an unknown prospective alternative"}
    return output


def self_check():
    assert tau(np.array([1., 2., 3.]), np.array([3., 2., 1.])) == 1
    assert tau(np.array([1., 2., 3.]), np.array([1., 2., 3.])) == -1
    assert tau(np.ones(3), np.arange(3)) is None
    # A repeated member is a double tie, rather than a new independent recipe.
    x, y, w = np.array([-np.inf, -np.inf, 2.]), np.array([3., 2., 1.]), np.array([2, 1, 3])
    assert abs(tau(x, y, w) - tau(np.repeat(x, w), np.repeat(y, w))) < 1e-12
    assert abs(binomial_tail(4, .5, 3) - .3125) < 1e-12
    assert abs(exact_bounds(0, 10)[1] - (1 - .025 ** .1)) < 1e-12
    assert known_bad_power(1., .025, .8) == 6
    assert known_bad_power(.5, .025, .8) is None
    assert detection_count(.1, .8) == 16


def run(directory, replicates=4000, seed=20261011):
    self_check()
    inputs, provenance = read_inputs(directory)
    ev4, ev5, gate = inputs["ev4.json"], inputs["ev5.json"], inputs["gate.json"]
    assert gate["results_sha256"] == "sha256:" + provenance["ev5.json"]["sha256"]
    members = sorted(m for m, v in ev4["summary"]["members"].items() if v["kind"] == "RECONSTRUCTED" and v["eligible"])
    assert members == sorted(m for m, v in ev5["summary"]["members"].items() if v["kind"] == "RECONSTRUCTED" and v["eligible"])
    assert all(ev4["rule_scores"][m]["control-exam-v1"] == ev5["rule_scores"][m]["control-exam-v1"] for m in members)
    assert not set(ev4["references"]) & set(ev5["references"])
    recipes = [recipe(m) for m in members]
    scores = {
        "historical_CE": np.array([ev5["rule_scores"][m]["control-exam-v1"] for m in members]),
        "historical_DAR": np.array([ev5["rule_scores"][m]["dar-p0-r100-a0"] for m in members]),
        "EV5_candidate_near_gate": np.array([-math.inf if gate["verdicts"][m]["verdict"] == "FAIL" else gate["candidate_scores"][m] for m in members]),
    }
    columns, counts = [], {}
    for label, data in (("EV4", ev4), ("EV5", ev5)):
        valid = [q for q in data["references"] if all(isinstance(data["decisions"][m][q]["outcome"].get("decision_loss"), (int, float)) for m in members)]
        counts[label] = {"offered_questions": len(data["references"]), "common_resolved": len(valid), "development": sum(q.startswith("D-") for q in valid), "verification": sum(q.startswith("V-") for q in valid)}
        for q in valid:
            columns.append((label, q, [data["decisions"][m][q]["outcome"]["decision_loss"] for m in members]))
    loss = np.array([c[2] for c in columns]).T
    # Pooled means the shared Level-0 member set across public campaigns/splits;
    # it does NOT mean evidence at levels absent from the public panel.
    qnames = [label + ":" + q for label, q, _ in columns]
    blocks = [label + ":" + q.split("-S")[0] for label, q, _ in columns]
    ordinary = bootstrap(scores, loss, recipes, qnames, replicates=replicates, seed=seed)
    temperature = bootstrap(scores, loss, recipes, blocks, replicates=replicates, seed=seed + 1)
    # Independent repeated public resampling runs quantify Monte Carlo spread
    # only, not sampling uncertainty in the empirical variance coefficients.
    batches = []
    for k in range(5):
        b = bootstrap(scores, loss, recipes, qnames, replicates=max(500, replicates // 4), seed=seed + 20 + k)
        batches.append(coefficients(b))
    coeff = coefficients(ordinary)
    block_coeff = coefficients(temperature)
    campaigns = {}
    for k, campaign in enumerate(("EV4", "EV5")):
        ix = [i for i, c in enumerate(columns) if c[0] == campaign]
        campaigns[campaign] = bootstrap(scores, loss[:, ix], recipes, [qnames[i] for i in ix], replicates=replicates, seed=seed + 30 + k)
    campaign_coeffs = {name: coefficients(b) for name, b in campaigns.items()}
    projections = {}
    for k, m in enumerate((60, 79, 94, 112, 125, 150, 160, 175, 200)):
        projections[str(m)] = bootstrap(scores, loss, recipes, qnames, replicates=replicates, seed=seed + 40 + k, draw_recipes=m, draw_questions=150, modes=(("crossed", True, True),))
    z = NormalDist().inv_cdf(.975)
    planning = {}
    for name in METHODS:
        # Low/high are STRUCTURAL sensitivity scenarios, not a confidence
        # interval: separate campaigns / pooled / temperature-block dependence.
        planning[name] = {"coefficients_iid_questions": coeff[name], "coefficients_temperature_blocks": block_coeff[name], "at_150_questions": {"recipes": required_recipes(coeff[name], 150, z), "half_width_at_79_recipes": projected_half_width(coeff[name], len(set(recipes)), 150, z)}, "temperature_block_at_150_questions": {"effective_blocks": 150 / (len(columns) / len(set(blocks))), "recipes": required_recipes(block_coeff[name], 150 / (len(columns) / len(set(blocks))), z), "half_width_at_79_recipes": projected_half_width(block_coeff[name], len(set(recipes)), 150 / (len(columns) / len(set(blocks))), z)}, "two_inferential_looks_at_150": {"confidence_each": .975, "recipes": required_recipes(coeff[name], 150, NormalDist().inv_cdf(.9875))}, "MC_recipe_count_range_at_150": [required_recipes(c[name], 150, z) for c in batches], "frontier": [{"questions": n, "required_recipes": required_recipes(coeff[name], n, z)} for n in (27, 50, 75, 150, 300)]}
        planning[name]["questions_at_79_recipes"] = required_questions(coeff[name], 79, z)
        planning[name]["questions_at_150_recipes"] = required_questions(coeff[name], 150, z)
        scenario_counts = {campaign: required_recipes(c[name], 150, z) for campaign, c in campaign_coeffs.items()}
        scenario_counts["pooled"] = planning[name]["at_150_questions"]["recipes"]
        scenario_counts["temperature_blocks"] = planning[name]["temperature_block_at_150_questions"]["recipes"]
        planning[name]["sensitivity_recipes_at_150"] = scenario_counts
        planning[name]["low_base_high_recipes_at_150"] = {"low": min(n for n in scenario_counts.values() if n is not None), "base": scenario_counts["pooled"], "high": max(n for n in scenario_counts.values() if n is not None)}
    # Concrete member/question dependence diagnostics; correlations are
    # descriptive similarities across this purposive public panel, not a
    # random-effects identification or an independent-miner guarantee.
    recipe_groups = defaultdict(list)
    for i, r in enumerate(recipes):
        recipe_groups[r].append(i)
    seed_correlations = []
    for ix in recipe_groups.values():
        for a in range(len(ix)):
            for b in range(a + 1, len(ix)):
                if np.std(loss[ix[a]]) and np.std(loss[ix[b]]):
                    seed_correlations.append(float(np.corrcoef(loss[ix[a]], loss[ix[b]])[0, 1]))
    question_correlations = {"same_temperature": [], "different_temperature": []}
    for a in range(loss.shape[1]):
        for b in range(a + 1, loss.shape[1]):
            if np.std(loss[:, a]) and np.std(loss[:, b]):
                key = "same_temperature" if blocks[a] == blocks[b] else "different_temperature"
                question_correlations[key].append(float(np.corrcoef(loss[:, a], loss[:, b])[0, 1]))
    def correlation_summary(xs):
        return {"pairs": len(xs), "min_median_max": [float(np.min(xs)), float(np.median(xs)), float(np.max(xs))] if xs else None}
    paired_correlations = {}
    for mode, summaries in ordinary["modes"].items():
        va = summaries["historical_CE"]["variance"]
        vb = summaries["historical_DAR"]["variance"]
        vd = summaries["DAR_minus_CE"]["variance"]
        covariance = (va + vb - vd) / 2
        paired_correlations[mode] = {"covariance": covariance, "correlation": covariance / math.sqrt(va * vb)}
    dependence = {"same_recipe_seed_loss_correlation": correlation_summary(seed_correlations), "question_loss_correlations_across_members": {k: correlation_summary(v) for k, v in question_correlations.items()}, "paired_CE_DAR_tau_resample_correlations": paired_correlations}
    split_points = {}
    for campaign in ("EV4", "EV5"):
        for split, prefix in (("development", "D-"), ("verification", "V-")):
            cols = [i for i, c in enumerate(columns) if c[0] == campaign and c[1].startswith(prefix)]
            split_points[campaign + ":" + split] = {"questions": len(cols), "tau": {name: tau(s, loss[:, cols].mean(axis=1)) for name, s in scores.items()}}
    family_points = {}
    families = ["knn" if m.startswith("knn") else "deeponet" if m.startswith("deeponet") else "mlp" for m in members]
    for f in sorted(set(families)):
        ix = [i for i, family in enumerate(families) if family != f]
        family_points["without_" + f] = {"members": len(ix), "recipes": len(set(recipes[i] for i in ix)), "tau": {name: tau(s[ix], loss[ix].mean(axis=1)) for name, s in scores.items()}}
    out = {
        "schema": "carbon.research.score-proof-public-planning-audit.v1",
        "status": "MEASURED_PUBLIC_DEVELOPMENT_WITH_CONDITIONAL_PROJECTIONS",
        "runtime": {"python": platform.python_version(), "numpy": np.__version__, "host": platform.system(), "validation_class": "Native research diagnostics; not canonical qualification"},
        "source_commit": BASE, "provenance": provenance,
        "scope": {"solver_runs": 0, "training_runs": 0, "spend": 0, "hidden_access": False, "ax42_access": False, "runtime_changes": False},
        "owner_choices": {"tau_half_width": .15, "interim_questions": 150},
        "planning_assumptions": {"confidence": .95, "power_screen_low": .8, "power_screen_high": .9, "control_test_alpha_each": .025, "bootstrap_replicates": replicates, "rng_seed_public_research_only": seed, "inference": "fixed scoring set; exchangeable public recipe clusters and question/block clusters; first-order variance scaling beyond observed support"},
        "inventory": {"construction_level": 0, "members": len(members), "recipes": len(set(recipes)), "seeds_per_recipe": dict(Counter(Counter(recipes).values())), "campaign_questions": counts, "pooled_common_resolved_questions": len(columns), "temperature_blocks": len(set(blocks)), "levels_1_to_4": "NOT_IDENTIFIABLE_NO_PUBLIC_MATCHED_PANELS"},
        "point_tau": {name: tau(s, loss.mean(axis=1)) for name, s in scores.items()},
        "split_points": split_points, "family_sensitivity": family_points, "dependence_diagnostics": dependence,
        "bootstrap_iid_questions": ordinary, "bootstrap_temperature_blocks": temperature,
        "bootstrap_by_campaign": campaigns,
        "empirical_support_projection_at_150_questions": projections,
        "planning": planning, "screens": screens(ev5, gate, members, scores),
        "gaps": ["No current in-force v3 Q3/G-FEAS joint panel", "No scoring-case uncertainty or score-side fold data", "No measured higher-level variance/power", "No new questions or recipes generated by bootstrap", "Gate and rank intervals not calibrated for prospective unseen-family coverage", "Recipe hyperparameter grid is not a random miner population", "Common resolved mask is model-dependent; target restricted to this frozen mask"],
        "human_input": {"production_thresholds": None, "confirmatory_alpha": None, "familywise_family": None, "levels_weights": None, "interim_efficacy_or_stopping": None},
        "maturity": "RESEARCH_MEASURED_NOT_QUALIFIED",
    }
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--replicates", type=int, default=4000)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("Numerical self-checks passed")
    else:
        if args.input_dir is None or args.output is None or args.replicates < 100:
            parser.error("Public input directory, output and at least 100 resamples required")
        result = run(args.input_dir, args.replicates)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"inventory": result["inventory"], "point_tau": result["point_tau"], "at_150": {k: v["at_150_questions"] for k, v in result["planning"].items()}}, indent=2))
