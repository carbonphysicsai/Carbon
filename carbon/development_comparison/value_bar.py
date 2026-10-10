"""Development-only, evidence-bound Challenge value-bar evaluator.

This reads measured reports and a separately registered owner rule. It never
solves a reference, runs a model, chooses a scoring threshold or reads hidden
material. Missing or incomparable evidence cannot become a PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
from pathlib import Path

EVIDENCE_SCHEMA = "carbon.challenge-value-evidence.v1"
RULE_SCHEMA = "carbon.challenge-value-rule.v1"
REPORT_SCHEMA = "carbon.challenge-value-report.v1"
BASELINE_SCHEMA = "carbon.development-portfolio-baseline-report.v1"
SCREEN_SCHEMA = "carbon.development-cheap-screen.v1"
CARBON_SCHEMA = "carbon.development-carbon-value-arm.v1"
FOLDS_SCHEMA = "carbon.challenge-value-heldout-folds.v1"
SPEED_SCHEMA = "carbon.challenge-value-query-costs.v1"
EQUAL_BUDGET_SCHEMA = "carbon.design-search.equal-budget-report.v1"
PASS, FAIL, INSUFFICIENT = "PASS", "FAIL", "INSUFFICIENT_EVIDENCE"


class ValueBarError(ValueError):
    pass


def _sha(value, name):
    if (
        not isinstance(value, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
    ):
        raise ValueBarError(f"{name} must be a SHA-256 digest")
    return value


def _digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def seal(body):
    if type(body) is not dict or "evidence_digest" in body:
        raise ValueBarError("unsealed evidence body required")
    return {**body, "evidence_digest": _digest(body)}


def _number(value, name, *, positive=False):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueBarError(f"finite {name} required")
    if positive and value <= 0:
        raise ValueBarError(f"positive {name} required")
    return float(value)


def _identity(evidence):
    if type(evidence) is not dict or set(evidence) != {
        "schema",
        "scope",
        "challenge",
        "export_digest",
        "selection",
        "baseline_report",
        "carbon_report",
        "folds",
        "speed",
        "equal_budget",
        "item_1",
        "item_4",
        "evidence_digest",
    }:
        raise ValueBarError("closed evidence-pack schema required")
    if evidence["schema"] != EVIDENCE_SCHEMA or evidence["scope"] != "DEVELOPMENT":
        raise ValueBarError("development evidence pack required")
    if evidence["evidence_digest"] != _digest(
        {k: v for k, v in evidence.items() if k != "evidence_digest"}
    ):
        raise ValueBarError("evidence digest mismatch")
    if not isinstance(evidence["challenge"], str) or not evidence["challenge"]:
        raise ValueBarError("Challenge identity required")
    _sha(evidence["export_digest"], "comparator export digest")
    selection = evidence["selection"]
    if (
        type(selection) is not dict
        or set(selection)
        != {
            "carbon_model_id",
            "baseline_id",
            "selection_role",
            "selection_receipt_digest",
        }
        or selection["selection_role"] not in ("TRAIN", "TUNING")
        or any(
            not isinstance(selection[key], str) or not selection[key]
            for key in ("carbon_model_id", "baseline_id", "selection_receipt_digest")
        )
    ):
        raise ValueBarError(
            "pre-heldout model and comparator selection receipt required"
        )
    _sha(selection["selection_receipt_digest"], "selection receipt digest")


def _owner_rule(rule):
    if rule is None:
        return None
    if (
        type(rule) is not dict
        or set(rule)
        != {"schema", "rule_id", "owner_record", "item_2", "item_3", "item_5"}
        or rule["schema"] != RULE_SCHEMA
    ):
        raise ValueBarError("closed owner rule required")
    if (
        not isinstance(rule["rule_id"], str)
        or not rule["rule_id"]
        or not isinstance(rule["owner_record"], str)
        or not rule["owner_record"]
    ):
        raise ValueBarError("owner rule identity required")
    for item in ("item_2", "item_3", "item_5"):
        if rule[item] is not None and type(rule[item]) is not dict:
            raise ValueBarError(f"{item} rule must be an object or null")
    return rule


def _item(status, reason, **metrics):
    return {"status": status, "reason": reason, **metrics}


def _external_receipt(value, name, evidence):
    if value is None:
        return _item(INSUFFICIENT, f"{name} owner evidence absent")
    if type(value) is not dict or set(value) != {
        "status",
        "source_digest",
        "rule_id",
        "challenge",
        "export_digest",
    }:
        raise ValueBarError(f"{name} receipt shape invalid")
    if (
        value["status"] not in (PASS, FAIL, INSUFFICIENT)
        or not value["rule_id"]
        or value["challenge"] != evidence["challenge"]
        or value["export_digest"] != evidence["export_digest"]
    ):
        raise ValueBarError(f"{name} receipt invalid")
    _sha(value["source_digest"], f"{name} source digest")
    return _item(
        value["status"],
        f"external owner receipt for {name}",
        source_digest=value["source_digest"],
        rule_id=value["rule_id"],
    )


def _quantile(values, probability):
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _paired_regret(evidence, settings, *, bootstrap_replicates, seed):
    if settings is None:
        return _item(INSUFFICIENT, "owner item 2 decision margin absent")
    if set(settings) != {"max_mean_regret_delta"}:
        raise ValueBarError("item 2 requires max_mean_regret_delta in buyer units")
    limit = _number(settings["max_mean_regret_delta"], "item 2 margin")
    baseline = evidence["baseline_report"]
    carbon = evidence["carbon_report"]
    folds = evidence["folds"]
    if baseline is None or carbon is None or folds is None:
        return _item(
            INSUFFICIENT, "matched comparator, Carbon and fold evidence required"
        )
    if (
        type(baseline) is not dict
        or baseline.get("schema") != BASELINE_SCHEMA
        or baseline.get("material") != "DEVELOPMENT"
        or baseline.get("export_digest") != evidence["export_digest"]
        or baseline.get("family") != evidence["challenge"]
        or baseline.get("family") != evidence["selection"]["baseline_id"]
    ):
        raise ValueBarError("#994 comparator report identity mismatch")
    screen = baseline.get("equal_budget_screening")
    if (
        type(screen) is not dict
        or screen.get("schema") != SCREEN_SCHEMA
        or screen.get("export_digest") != evidence["export_digest"]
    ):
        raise ValueBarError("#994 digest-bound screening export required")
    _sha(screen.get("materials_digest"), "#994 materials digest")
    if (
        type(carbon) is not dict
        or carbon.get("schema") != CARBON_SCHEMA
        or carbon.get("export_digest") != evidence["export_digest"]
        or carbon.get("challenge") != evidence["challenge"]
        or carbon.get("model_id") != evidence["selection"]["carbon_model_id"]
    ):
        raise ValueBarError("matched Carbon arm required")
    if (
        type(folds) is not dict
        or set(folds) != {"schema", "export_digest", "folds"}
        or folds["schema"] != FOLDS_SCHEMA
        or folds["export_digest"] != evidence["export_digest"]
    ):
        raise ValueBarError("registered held-out folds required")
    groups = folds["folds"]
    if type(groups) is not list or len(groups) != 2:
        return _item(INSUFFICIENT, "two independent held-out folds required")
    baseline_decisions = (
        baseline.get("held_out", {}).get("decision", {}).get("decisions")
    )
    carbon_decisions = carbon.get("decisions")
    rankings = screen.get("candidate_rankings")
    if not all(
        type(rows) is list for rows in (baseline_decisions, carbon_decisions, rankings)
    ):
        return _item(
            INSUFFICIENT, "complete per-question decisions and rankings required"
        )
    if not all(
        type(row) is dict
        for rows in (baseline_decisions, carbon_decisions, rankings)
        for row in rows
    ):
        raise ValueBarError("decision and ranking rows must be objects")
    if not all(
        isinstance(row.get(key), str) and bool(row[key])
        for rows, key in (
            (baseline_decisions, "question"),
            (carbon_decisions, "question"),
            (rankings, "case"),
        )
        for row in rows
    ):
        raise ValueBarError("nonempty question identities required")
    by_baseline = {row.get("question"): row for row in baseline_decisions}
    by_carbon = {row.get("question"): row for row in carbon_decisions}
    by_rank = {row.get("case"): row for row in rankings}
    if any(
        len(index) != len(rows)
        for index, rows in (
            (by_baseline, baseline_decisions),
            (by_carbon, carbon_decisions),
            (by_rank, rankings),
        )
    ):
        raise ValueBarError("duplicate question in matched reports")
    fold_ids, sources, questions, fold_deltas, fold_means = set(), set(), set(), [], []
    units = set()
    unpriced = 0
    for fold in groups:
        if (
            type(fold) is not dict
            or set(fold) != {"fold_id", "source_digest", "questions"}
            or not fold["fold_id"]
            or type(fold["questions"]) is not list
            or not fold["questions"]
        ):
            raise ValueBarError("held-out fold registration incomplete")
        _sha(fold["source_digest"], "held-out fold source digest")
        if fold["fold_id"] in fold_ids or fold["source_digest"] in sources:
            return _item(
                INSUFFICIENT, "fold identities or source digests are not independent"
            )
        fold_ids.add(fold["fold_id"])
        sources.add(fold["source_digest"])
        deltas = []
        for question in fold["questions"]:
            if question in questions:
                return _item(INSUFFICIENT, "held-out questions overlap folds")
            questions.add(question)
            if (
                question not in by_baseline
                or question not in by_carbon
                or question not in by_rank
            ):
                return _item(INSUFFICIENT, "common resolved question mask incomplete")
            base_row, model_row, ranking = (
                by_baseline[question],
                by_carbon[question],
                by_rank[question],
            )
            objective = ranking.get("objective")
            if (
                type(objective) is not dict
                or not isinstance(objective.get("unit"), str)
                or not objective["unit"]
            ):
                raise ValueBarError("#994 ranking objective unit absent")
            units.add(objective["unit"])
            if (
                base_row.get("reference_state") != model_row.get("reference_state")
                or not base_row.get("reference_resolved")
                or not model_row.get("reference_resolved")
            ):
                return _item(
                    INSUFFICIENT, "matched settled reference outcomes required"
                )
            if base_row["reference_state"] == "NONE_FEASIBLE":
                if (
                    base_row.get("kind") != "CORRECT_ABSTENTION"
                    or model_row.get("kind") != "CORRECT_ABSTENTION"
                ):
                    return _item(
                        INSUFFICIENT, "NONE_FEASIBLE response differs between arms"
                    )
                unpriced += 1
                continue
            if (
                base_row["reference_state"] != "FEASIBLE_EXISTS"
                or base_row.get("kind") != "SELECTED_FEASIBLE"
                or model_row.get("kind") != "SELECTED_FEASIBLE"
            ):
                return _item(INSUFFICIENT, "matched admissibility is absent")
            base_regret = _number(base_row.get("regret"), "baseline regret")
            model_regret = _number(model_row.get("regret"), "Carbon regret")
            if base_regret < 0 or model_regret < 0:
                raise ValueBarError("negative regret invalid")
            deltas.append(model_regret - base_regret)
        if not deltas:
            return _item(
                INSUFFICIENT, "each held-out fold needs priced paired decisions"
            )
        fold_deltas.append(deltas)
        fold_means.append(statistics.fmean(deltas))
    if (
        set(by_baseline) != questions
        or set(by_carbon) != questions
        or set(by_rank) != questions
    ):
        return _item(
            INSUFFICIENT, "unregistered question outside the two-fold common mask"
        )
    if len(units) != 1:
        return _item(INSUFFICIENT, "mixed buyer objective units")
    # The fold, not a correlated question from one bank, is the resampling unit.
    rng = random.Random(seed)
    draws = [
        statistics.fmean(rng.choice(fold_means) for _ in fold_means)
        for _ in range(bootstrap_replicates)
    ]
    low = _quantile(draws, 0.025)
    high = _quantile(draws, 0.975)
    observed = statistics.fmean(fold_means)
    status = PASS if high < limit else FAIL if low >= limit else INSUFFICIENT
    return _item(
        status,
        "paired 95% fold-cluster bootstrap in buyer objective units",
        unit=next(iter(units)),
        mean_regret_delta=observed,
        ci95=[low, high],
        fold_mean_deltas=fold_means,
        paired_questions=sum(map(len, fold_deltas)),
        none_feasible_questions=unpriced,
        margin=limit,
        independent_folds=2,
    )


def _speed(evidence, settings):
    if settings is None:
        return _item(INSUFFICIENT, "owner item 3 speed threshold absent")
    if set(settings) != {"min_median_wall_speedup"}:
        raise ValueBarError("item 3 requires min_median_wall_speedup")
    threshold = _number(
        settings["min_median_wall_speedup"], "speed-up threshold", positive=True
    )
    receipt = evidence["speed"]
    if receipt is None:
        return _item(INSUFFICIENT, "matched measured query-cost receipt absent")
    if (
        type(receipt) is not dict
        or set(receipt)
        != {"schema", "export_digest", "status", "query_unit", "route", "pairs"}
        or receipt["schema"] != SPEED_SCHEMA
        or receipt["export_digest"] != evidence["export_digest"]
        or receipt["query_unit"] != "full_registered_decision_query"
        or not receipt["route"]
    ):
        raise ValueBarError("matched full-decision query cost receipt required")
    if receipt["status"] != "MEASURED":
        return _item(
            INSUFFICIENT, "measured reference and Carbon decision-query time absent"
        )
    pairs = receipt["pairs"]
    if type(pairs) is not list or not pairs:
        return _item(INSUFFICIENT, "paired reference and Carbon query costs absent")
    ratios = []
    seen = set()
    for row in pairs:
        if (
            type(row) is not dict
            or set(row) != {"query", "reference_wall_s", "carbon_wall_s"}
            or not row["query"]
            or row["query"] in seen
        ):
            raise ValueBarError("unique paired query cost rows required")
        seen.add(row["query"])
        ratios.append(
            _number(row["reference_wall_s"], "reference wall", positive=True)
            / _number(row["carbon_wall_s"], "Carbon wall", positive=True)
        )
    folds = evidence["folds"]
    if folds is None or type(folds) is not dict or type(folds.get("folds")) is not list:
        return _item(INSUFFICIENT, "registered decision-query sample absent")
    if any(
        type(fold) is not dict or type(fold.get("questions")) is not list
        for fold in folds["folds"]
    ):
        return _item(INSUFFICIENT, "registered decision-query sample incomplete")
    registered = {question for fold in folds["folds"] for question in fold["questions"]}
    if seen != registered:
        return _item(INSUFFICIENT, "speed queries differ from held-out decisions")
    value = statistics.median(ratios)
    return _item(
        PASS if value >= threshold else FAIL,
        "measured paired complete-query wall-time speed-up",
        median_speedup=value,
        required_speedup=threshold,
        pairs=len(ratios),
        route=receipt["route"],
    )


def _equal_budget(evidence, settings):
    if settings is None:
        return _item(INSUFFICIENT, "owner item 5 equal-budget decision rule absent")
    if set(settings) != {
        "budget",
        "min_p_lower",
        "max_regret_excess",
        "min_feasible_pick_fraction",
    }:
        raise ValueBarError("item 5 requires budget and three explicit thresholds")
    budget = settings["budget"]
    if type(budget) is not dict or set(budget) != {"wall_s", "core_s"}:
        raise ValueBarError("registered equal budget required")
    for key in budget:
        _number(budget[key], f"budget {key}", positive=True)
    p_min = _number(settings["min_p_lower"], "minimum P lower")
    regret_max = _number(settings["max_regret_excess"], "regret excess")
    feasible_min = _number(
        settings["min_feasible_pick_fraction"], "feasible pick floor"
    )
    if not 0 <= p_min <= 1 or regret_max < 0 or not 0 <= feasible_min <= 1:
        raise ValueBarError("item 5 thresholds out of range")
    report = evidence["equal_budget"]
    if report is None:
        return _item(INSUFFICIENT, "#998 equal-budget report absent")
    if (
        type(report) is not dict
        or report.get("schema") != EQUAL_BUDGET_SCHEMA
        or report.get("challenge") != evidence["challenge"]
        or report.get("source_digest") != evidence["export_digest"]
    ):
        raise ValueBarError("matched #998 report identity required")
    if (
        report.get("status") != "OK"
        or report.get("independent_clusters", 0) < 2
        or report.get("cost_basis") != "MEASURED"
        or report.get("confidence") != 0.95
    ):
        return _item(INSUFFICIENT, "settled multi-bank equal-budget result required")
    baseline_report = evidence["baseline_report"]
    if type(baseline_report) is not dict:
        return _item(INSUFFICIENT, "#994 buyer objective unit absent")
    screening = baseline_report.get("equal_budget_screening")
    if type(screening) is not dict:
        return _item(INSUFFICIENT, "#994 buyer objective unit absent")
    rankings = screening.get("candidate_rankings")
    if (
        not isinstance(rankings, list)
        or not rankings
        or any(
            type(row) is not dict or type(row.get("objective")) is not dict
            for row in rankings
        )
    ):
        return _item(INSUFFICIENT, "#994 buyer objective unit absent")
    units = {row["objective"].get("unit") for row in rankings}
    report_objective = report.get("objective")
    if (
        len(units) != 1
        or type(report_objective) is not dict
        or report_objective.get("unit") not in units
    ):
        return _item(INSUFFICIENT, "equal-budget buyer objective unit mismatch")
    matches = [row for row in report.get("curves", []) if row.get("budget") == budget]
    if len(matches) != 1:
        return _item(INSUFFICIENT, "registered budget absent from #998 curve")
    row = matches[0]
    ci = row.get("bootstrap_ci")
    estimates = row.get("estimates")
    if (
        type(ci) is not dict
        or type(estimates) is not dict
        or type(ci.get("p_model_beats_solver")) is not list
        or len(ci["p_model_beats_solver"]) != 2
    ):
        return _item(INSUFFICIENT, "equal-budget bootstrap interval absent")
    lower = _number(ci["p_model_beats_solver"][0], "P lower")
    upper = _number(ci["p_model_beats_solver"][1], "P upper")
    if not 0 <= lower <= upper <= 1:
        raise ValueBarError("invalid equal-budget probability interval")
    model = estimates.get("model_then_solver", {})
    baseline = estimates.get("baseline_then_solver", {})
    model_regret = model.get("mean_regret_conditional")
    baseline_regret = baseline.get("mean_regret_conditional")
    if model_regret is None or baseline_regret is None:
        return _item(INSUFFICIENT, "both arms need verified feasible picks and regret")
    excess = _number(model_regret, "model regret") - _number(
        baseline_regret, "baseline regret"
    )
    feasible = _number(
        model.get("feasible_pick_fraction"), "model feasible pick fraction"
    )
    passes = lower >= p_min and excess <= regret_max and feasible >= feasible_min
    return _item(
        PASS if passes else FAIL,
        "solver-verified equal-budget curve at registered time and compute",
        p_model_beats_solver_ci_lower=lower,
        regret_excess=excess,
        model_feasible_pick_fraction=feasible,
        budget=budget,
        independent_clusters=report["independent_clusters"],
    )


def evaluate(evidence, rule, *, bootstrap_replicates, seed):
    """Pure report: no I/O, selection or threshold defaults."""
    _identity(evidence)
    rule = _owner_rule(rule)
    if (
        type(bootstrap_replicates) is not int
        or bootstrap_replicates < 100
        or type(seed) is not int
    ):
        raise ValueBarError(
            "explicit bootstrap replicates >=100 and integer seed required"
        )
    items = {
        "1": _external_receipt(evidence["item_1"], "item 1", evidence),
        "2": _paired_regret(
            evidence,
            None if rule is None else rule["item_2"],
            bootstrap_replicates=bootstrap_replicates,
            seed=seed,
        ),
        "3": _speed(evidence, None if rule is None else rule["item_3"]),
        "4": _external_receipt(evidence["item_4"], "item 4", evidence),
        "5": _equal_budget(evidence, None if rule is None else rule["item_5"]),
    }
    statuses = {row["status"] for row in items.values()}
    overall = FAIL if FAIL in statuses else PASS if statuses == {PASS} else INSUFFICIENT
    return {
        "schema": REPORT_SCHEMA,
        "status": overall,
        "challenge": evidence["challenge"],
        "evidence_digest": evidence["evidence_digest"],
        "export_digest": evidence["export_digest"],
        "rule_id": None if rule is None else rule["rule_id"],
        "bootstrap_replicates": bootstrap_replicates,
        "bootstrap_seed": seed,
        "items": items,
    }


def evidence_page(report):
    """One-page owner summary; no per-case values or hidden identifiers."""
    lines = [
        f"# Challenge value bar — {report['challenge']}",
        "",
        f"**Overall: {report['status']}**. Development evidence only; owner adoption remains separate.",
        "",
        f"Evidence `{report['evidence_digest']}`; comparator export `{report['export_digest']}`; rule `{report['rule_id'] or 'HUMAN_INPUT'}`.",
        "",
        "| Item | Status | Evidence basis / gap |",
        "| --- | --- | --- |",
    ]
    for item, outcome in report["items"].items():
        lines.append(f"| {item} | {outcome['status']} | {outcome['reason']} |")
    item2 = report["items"]["2"]
    if "ci95" in item2:
        lines += [
            "",
            f"Item 2 paired regret delta (Carbon minus cheap baseline): {item2['mean_regret_delta']:.6g} {item2['unit']}; fold-cluster 95% CI [{item2['ci95'][0]:.6g}, {item2['ci95'][1]:.6g}]. Two independent held-out folds, {item2['paired_questions']} priced questions; {item2['none_feasible_questions']} settled NONE_FEASIBLE questions were not assigned invented regret.",
        ]
    item3 = report["items"]["3"]
    if "median_speedup" in item3:
        lines += [
            "",
            f"Item 3: {item3['median_speedup']:.6g}× median paired complete-query wall speed-up across {item3['pairs']} measured queries on {item3['route']}.",
        ]
    item5 = report["items"]["5"]
    if "p_model_beats_solver_ci_lower" in item5:
        lines += [
            "",
            f"Item 5: equal-budget P(model+solver beats solver-alone) bootstrap lower bound {item5['p_model_beats_solver_ci_lower']:.6g}; model-minus-baseline verified regret {item5['regret_excess']:.6g} objective units; {item5['independent_clusters']} independent bank clusters.",
        ]
    lines += [
        "",
        "PASS requires the registered owner rule and all five evidence items. No absent, unresolved or unmatched record is treated as a pass.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--rule")
    parser.add_argument("--bootstrap-replicates", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-page", required=True)
    args = parser.parse_args(argv)
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    rule = (
        None
        if args.rule is None
        else json.loads(Path(args.rule).read_text(encoding="utf-8"))
    )
    report = evaluate(
        evidence, rule, bootstrap_replicates=args.bootstrap_replicates, seed=args.seed
    )
    json_path, page_path = Path(args.output_json), Path(args.output_page)
    if json_path.exists() or page_path.exists():
        raise FileExistsError("value-bar output exists")
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    page_path.write_text(evidence_page(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    main()
