"""Prospective G-FEAS threshold curves from explicit DEVELOPMENT summaries.

No prediction bundles, references, hidden cases, solver calls or rule writes.
The strict `exceeds` comparison follows the owner record and registry v5;
historical v4 scores remain historical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from collections import Counter
from pathlib import Path

from carbon.battery.value import score_tuning
from carbon.design_search.score_value import kendall_tau_b

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "docs/development/evidence/battery-score-tuning/registry-v5.json"
SCHEMA = "carbon.battery.g-feas-retune-input.v1"
REPORT_SCHEMA = "carbon.battery.g-feas-retune-curves.v1"
SCOPE = {"PUBLIC_DEVELOPMENT", "DEVELOPMENT_SUMMARY_ONLY", "SYNTHETIC_FIXTURE"}
FIELDS = {
    "schema",
    "scope",
    "source_digest",
    "screening_digest",
    "q3_digest",
    "decision_digest",
    "registry_sha256",
    "good_receipt_digest",
    "good_recipes",
    "thresholds",
    "members",
}
MEMBER_FIELDS = {
    "member",
    "recipe",
    "v3_report_digest",
    "value_receipt_digest",
    "state",
    "a",
    "q3_regret",
    "g_feas",
    "decision_loss",
}


class RetuneError(ValueError):
    pass


def _sha(value, label):
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(c not in "0123456789abcdef" for c in value[7:])
    ):
        raise RetuneError(f"{label}: SHA-256 digest required")


def _number(value, label, *, low=None, high=None):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise RetuneError(f"{label}: finite number required")
    value = float(value)
    if (low is not None and value < low) or (high is not None and value > high):
        raise RetuneError(f"{label}: out of range")
    return value


def _quantile(values, probability):
    values = sorted(values)
    position = probability * (len(values) - 1)
    low, high = math.floor(position), math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def _validate(panel, registry_sha):
    if (
        type(panel) is not dict
        or set(panel) != FIELDS
        or panel["schema"] != SCHEMA
        or panel["scope"] not in SCOPE
    ):
        raise RetuneError("closed public/development summary required")
    for key in (
        "source_digest",
        "screening_digest",
        "q3_digest",
        "decision_digest",
        "registry_sha256",
        "good_receipt_digest",
    ):
        _sha(panel[key], key)
    if panel["registry_sha256"] != registry_sha:
        raise RetuneError("registered scoring rule digest mismatch")
    thresholds = panel["thresholds"]
    if type(thresholds) is not list or not thresholds or len(thresholds) > 100:
        raise RetuneError("explicit threshold grid required")
    grid = [_number(value, "threshold", low=0, high=1.01) for value in thresholds]
    if grid != sorted(set(grid)):
        raise RetuneError("threshold grid must be strictly increasing")
    members = panel["members"]
    if type(members) is not list or not members:
        raise RetuneError("member summaries required")
    ids = set()
    recipes = set()
    states = Counter()
    for row in members:
        if type(row) is not dict or set(row) != MEMBER_FIELDS:
            raise RetuneError("closed member summary required")
        for key in ("member", "recipe"):
            if not isinstance(row[key], str) or not row[key] or len(row[key]) > 200:
                raise RetuneError(f"{key}: identifier required")
        for key in ("v3_report_digest", "value_receipt_digest"):
            _sha(row[key], key)
        if row["member"] in ids:
            raise RetuneError("duplicate member")
        ids.add(row["member"])
        recipes.add(row["recipe"])
        if row["state"] not in ("SCORED", "CANDIDATE_FAILED", "FAILED_INFRA", "VOID"):
            raise RetuneError("unknown member state")
        states[row["state"]] += 1
        if row["state"] == "SCORED":
            _number(row["a"], "a", low=0, high=1)
            if row["a"] == 0:
                raise RetuneError("accuracy leg must be positive")
            _number(row["q3_regret"], "q3_regret", low=0)
            _number(row["g_feas"], "g_feas", low=0, high=1)
            _number(row["decision_loss"], "decision_loss", low=0)
        elif any(
            row[key] is not None
            for key in ("a", "q3_regret", "g_feas", "decision_loss")
        ):
            raise RetuneError("unscored row must not carry substitute score/value")
    good = panel["good_recipes"]
    if (
        type(good) is not list
        or not good
        or len(set(good)) != len(good)
        or not set(good) <= recipes
    ):
        raise RetuneError("predeclared good recipes must appear in panel")
    return grid, states


def _candidate(base, threshold):
    return score_tuning.Candidate(
        f"G-FEAS/A-Q>@{threshold:g}",
        base.kind,
        dict(base.weights),
        {"measure": "feasibility", "cutoff": threshold, "comparison": "exceeds"},
        base.stable,
        "prospective diagnostic threshold, not adopted",
    )


def _curve_point(rows, good_recipes, candidate):
    legs = {
        row["member"]: {
            "eligible": True,
            "E": 1 / row["a"] - 1,
            "legs": {"a": row["a"], "q": 1 / (1 + row["q3_regret"])},
            "gates": {"feasibility": row["g_feas"]},
        }
        for row in rows
    }
    recipe_of = {row["member"]: row["recipe"] for row in rows}
    scores, verdicts = score_tuning.candidate_scores(candidate, legs, recipe_of)
    passing = [row for row in rows if verdicts[row["member"]] == "PASS"]
    failed_good = {
        row["recipe"]
        for row in rows
        if row["recipe"] in good_recipes and verdicts[row["member"]] == "FAIL"
    }
    values = [-row["decision_loss"] for row in rows]
    tau = kendall_tau_b([scores[row["member"]] for row in rows], values)
    pass_tau = (
        kendall_tau_b(
            [scores[row["member"]] for row in passing],
            [-row["decision_loss"] for row in passing],
        )
        if len(passing) >= 2
        else None
    )
    return {
        "threshold": candidate.gate["cutoff"],
        "accepted_mean_false_feasible_rate": (
            statistics.fmean(row["g_feas"] for row in passing) if passing else None
        ),
        "accepted_with_any_false_feasible_fraction": (
            sum(row["g_feas"] > 0 for row in passing) / len(passing)
            if passing
            else None
        ),
        "good_recipe_fail_rate_any_seed": len(failed_good) / len(good_recipes),
        "score_value_tau_b_all": tau,
        "score_value_tau_b_passing_only": pass_tau,
        "passing_members": len(passing),
        "scored_members": len(rows),
        "good_recipes": len(good_recipes),
    }


def evaluate(panel, *, bootstrap_replicates, seed):
    """Aggregate prospective curves; resample recipes as clusters."""
    if (
        type(bootstrap_replicates) is not int
        or bootstrap_replicates < 100
        or type(seed) is not int
    ):
        raise RetuneError("explicit bootstrap replicates >=100 and seed required")
    registry, identity = score_tuning.load_registry(REGISTRY)
    grid, states = _validate(panel, "sha256:" + identity["sha256"])
    summary = {
        "schema": REPORT_SCHEMA,
        "scope": panel["scope"],
        "source_digest": panel["source_digest"],
        "registry_sha256": panel["registry_sha256"],
        "rule_at_0_05": "G-FEAS/A-Q>@0.05 (strict exceeds; registry v5)",
        "states": dict(sorted(states.items())),
        "bootstrap_replicates": bootstrap_replicates,
        "bootstrap_seed": seed,
    }
    if states["SCORED"] != len(panel["members"]):
        return {
            **summary,
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "unscored member summaries; no common complete value mask",
            "curves": [],
        }
    rows = panel["members"]
    recipes = sorted({row["recipe"] for row in rows})
    if len(recipes) < 2:
        return {
            **summary,
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "at least two recipe clusters required",
            "curves": [],
        }
    by_recipe = {
        recipe: [row for row in rows if row["recipe"] == recipe] for recipe in recipes
    }
    rng = random.Random(seed)
    cluster_draws = [
        [rng.choice(recipes) for _ in recipes] for _ in range(bootstrap_replicates)
    ]
    curves = []
    for threshold in grid:
        candidate = _candidate(registry["A-Q"], threshold)
        point = _curve_point(rows, set(panel["good_recipes"]), candidate)
        bands = []
        for draw in cluster_draws:
            sampled = []
            sampled_good = set()
            for cluster_index, recipe in enumerate(draw):
                if recipe in panel["good_recipes"]:
                    sampled_good.add(f"cluster-{cluster_index}")
                for member_index, row in enumerate(by_recipe[recipe]):
                    sampled.append(
                        {
                            **row,
                            "member": f"draw-{cluster_index}-{member_index}",
                            "recipe": f"cluster-{cluster_index}",
                        }
                    )
            # A resample with no predeclared good recipe has no good-fail rate.
            if not sampled_good:
                continue
            bands.append(_curve_point(sampled, sampled_good, candidate))
        point["bootstrap_ci95"] = {
            metric: (
                None
                if len(values := [b[metric] for b in bands if b[metric] is not None])
                < bootstrap_replicates // 2
                else [_quantile(values, 0.025), _quantile(values, 0.975)]
            )
            for metric in (
                "accepted_mean_false_feasible_rate",
                "good_recipe_fail_rate_any_seed",
                "score_value_tau_b_all",
            )
        }
        point["bootstrap_defined_draws"] = len(bands)
        curves.append(point)
    return {
        **summary,
        "status": "DESCRIPTIVE_ONLY",
        "reason": "thresholds are prospective probes; owner selects any change",
        "curves": curves,
    }


def synthetic_fixture():
    """Public synthetic #961 controls, not development recipe measurements."""
    from scripts.dev.battery import v3_rule_robustness

    cases = v3_rule_robustness.report()["cases"]
    registry_sha = "sha256:" + score_tuning.load_registry(REGISTRY)[1]["sha256"]
    # Extra known-good toy recipes make the good-recipe rejection trade-off
    # visible. Their values are ASSUMPTION, never observations from #961.
    extra = [
        {
            "member": "toy-good-0.02",
            "recipe": "toy-good-0.02",
            "a": 0.8,
            "q3_regret": 0.15,
            "g_feas": 0.02,
            "decision_loss": 0.15,
        },
        {
            "member": "toy-good-0.08",
            "recipe": "toy-good-0.08",
            "a": 0.8,
            "q3_regret": 0.15,
            "g_feas": 0.08,
            "decision_loss": 0.15,
        },
    ]
    digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                {"cases": cases, "assumption_toys": extra},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )
    members = []
    good = []
    for name, pair in sorted(cases.items()):
        for side in ("baseline", "attack"):
            row = pair[side]
            recipe = f"{name}-{side}"
            if side == "baseline":
                good.append(recipe)
            members.append(
                {
                    "member": recipe,
                    "recipe": recipe,
                    "v3_report_digest": digest,
                    "value_receipt_digest": digest,
                    "state": "SCORED",
                    "a": row["accuracy_leg"],
                    "q3_regret": row["mean_q3_regret"],
                    "g_feas": row["false_feasible_rate"],
                    "decision_loss": row["synthetic_decision_loss"],
                }
            )
    for row in extra:
        good.append(row["recipe"])
        members.append(
            {
                **row,
                "v3_report_digest": digest,
                "value_receipt_digest": digest,
                "state": "SCORED",
            }
        )
    return {
        "schema": SCHEMA,
        "scope": "SYNTHETIC_FIXTURE",
        "source_digest": digest,
        "screening_digest": digest,
        "q3_digest": digest,
        "decision_digest": digest,
        "registry_sha256": registry_sha,
        "good_receipt_digest": digest,
        "good_recipes": good,
        "thresholds": [0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.01],
        "members": members,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input")
    source.add_argument("--public-synthetic-demo", action="store_true")
    parser.add_argument("--bootstrap-replicates", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    panel = (
        synthetic_fixture()
        if args.public_synthetic_demo
        else json.loads(Path(args.input).read_text(encoding="utf-8"))
    )
    report = evaluate(
        panel, bootstrap_replicates=args.bootstrap_replicates, seed=args.seed
    )
    target = Path(args.output)
    if target.exists():
        raise FileExistsError("refusing to overwrite retune report")
    target.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    main()
