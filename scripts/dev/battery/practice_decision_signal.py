"""Public-only battery practice decision diagnostic; no solver or exam reads.

    python -m scripts.dev.battery.practice_decision_signal collect --out DIR
    python -m scripts.dev.battery.practice_decision_signal report --out DIR

`collect` reconstructs the committed run-5 first-seed recipes on public TRAIN
and predicts only the pinned 210 public practice-decision inputs. Its local
receipts are resumable. `report` compares aggregate practice regret and
accuracy with the already published EV4 DEVELOPMENT decision values. Neither
command changes miner feedback, Launchpad, the exam, or a scoring rule.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from carbon.battery import practice_safety as safety
from carbon.battery.value import decision, panel, quiz
from carbon.design_search.score_value import kendall_tau_b, spearman_rho

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs/development/evidence/graphite-run5-q1"
Q1 = EVIDENCE / "q1-report.json"
PRACTICE_SUMMARIES = EVIDENCE / "practice-summaries.json"
PANEL = "graphite-run5"
SCHEMA = "carbon.battery.practice-decision-signal.v1"
REPORT_SCHEMA = "carbon.battery.practice-decision-signal-report.v1"
RUN5_IMPLEMENTATION = "1.0"

# The already registered EV4 DEVELOPMENT preferences, copied for this public
# practice diagnostic. A test binds these fields to the committed contract.
# The runtime reads no EV scenario, scoring-set, tuning or hidden case file.
RULES = {
    **safety.DECISION_RULES,
    "minimum_useful_improvement_s": 120.0,
    "mistake_costs": {
        "false_acceptance": 10.0,
        "missed_opportunity": 1.0,
        "regret_per_minimum_useful_improvement": 1.0,
    },
}
BASELINE_ID = "c1=0.75,c2=0.6"
RULE_DIGEST = (
    "sha256:"
    + hashlib.sha256(
        json.dumps(
            {"rules": RULES, "candidates": safety.CANDIDATES, "baseline": BASELINE_ID},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
)


def _sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _public_pin():
    return "sha256:" + safety.DECISION_SET_SUMS_SHA256


def _conditions(decision_set):
    """Reference assessment on public practice records alone."""
    for condition, cases in zip(
        decision_set.conditions, decision_set.grid, strict=True
    ):
        scenario = {"conditions": [condition]}
        references = {
            (candidate_id, 0): decision_set.references[case_id]
            for candidate_id, case_id in cases.items()
        }
        assessed = decision.assess_reference(
            RULES, scenario, safety.CANDIDATES, references
        )
        yield scenario, cases, assessed


def evaluate(predictions, decision_set):
    """Aggregate Q3-style outcomes, without any case ID or pick in the result.

    No subset of an incomplete prediction panel is scored. A reference fault
    makes its entire condition unscored; it never becomes model regret.
    """
    if decision_set.refused is not None:
        return {"status": "REFUSED_PUBLIC_SET", "reason": decision_set.refused}
    required = set(decision_set.case_ids)
    if type(predictions) is not dict or set(predictions) != required:
        return {
            "status": "UNMEASURED_PREDICTIONS",
            "missing": (
                len(required - set(predictions))
                if type(predictions) is dict
                else len(required)
            ),
            "extra": (
                len(set(predictions) - required) if type(predictions) is dict else 0
            ),
        }
    invalid = sum(not safety.measurable(predictions[c]) for c in required)
    if invalid:
        return {"status": "UNMEASURED_PREDICTIONS", "invalid": invalid}

    excluded = reference_unresolved = abstained = chosen = 0
    outcomes = []
    for scenario, cases, reference in _conditions(decision_set):
        statuses = {row["status"] for row in reference.values()}
        if decision.UNAVAILABLE in statuses:
            reference_unresolved += 1
            continue
        if statuses == {decision.INFEASIBLE}:
            excluded += 1
            continue
        if decision.best_in_set(safety.CANDIDATES, reference) is None:
            reference_unresolved += 1
            continue
        quantities = {
            (candidate_id, 0): decision.measure(RULES, predictions[case_id])
            for candidate_id, case_id in cases.items()
        }
        predicted = decision.assess_predicted(
            RULES, scenario, safety.CANDIDATES, quantities
        )
        pick = decision.select(safety.CANDIDATES, predicted)
        result = decision.outcome(
            RULES, safety.CANDIDATES, pick, reference, BASELINE_ID
        )
        abstained += pick is None
        chosen += pick is not None
        outcomes.append(
            {"kind": result["kind"], "decision_loss": result["decision_loss"]}
        )
    if not outcomes:
        return {
            "status": "UNMEASURED_REFERENCES",
            "conditions": len(decision_set.conditions),
            "excluded_all_infeasible": excluded,
            "reference_unresolved": reference_unresolved,
        }
    return {
        "status": "MEASURED_PUBLIC_PRACTICE",
        "conditions": len(decision_set.conditions),
        "scored_conditions": len(outcomes),
        "excluded_all_infeasible": excluded,
        "reference_unresolved": reference_unresolved,
        "chosen": chosen,
        "abstained": abstained,
        "outcome_counts": dict(sorted(Counter(o["kind"] for o in outcomes).items())),
        "measures": quiz.q3_measures(outcomes, RULES),
        "feedback_only": True,
        "official": False,
    }


def _first_seed_panel():
    """The published Q1 matched panel already excludes the known alias."""
    q1 = json.loads(Q1.read_text(encoding="utf-8"))
    selected = {name: row for name, row in q1["members"].items() if row["first_seed"]}
    source = {
        name: (recipe, strategy, seed)
        for name, recipe, strategy, seed in panel.members(PANEL)
    }
    if len(selected) != 8 or set(selected) - set(source):
        raise ValueError("run-5 first-seed public panel changed")
    if len({row["recipe"] for row in selected.values()}) != len(selected):
        raise ValueError("run-5 alias was not removed")
    return q1, [(name, *source[name]) for name in sorted(selected)]


def _receipt_context(member, recipe, seed, digest):
    return {
        "schema": SCHEMA,
        "member": member,
        "recipe": recipe,
        "recipe_digest": digest,
        "battery_implementation": RUN5_IMPLEMENTATION,
        "seed": seed,
        "public_set_sha256s_sha256": _public_pin(),
        "rule_digest": RULE_DIGEST,
    }


def _verify_historical_jax_rebuild():
    """Run-5's JAX model code is unchanged, even though Torch advanced."""
    from carbon.battery import implementation_versions as versions

    historical = versions.module_bytes(RUN5_IMPLEMENTATION)
    current = versions.module_bytes()
    for name in ("domain.py", "recipes.py", "training.py"):
        if historical[name] != current[name]:
            raise ValueError("historical JAX rebuild requires its pinned runtime")


def collect(out, *, only=()):
    """CPU reconstruction and inference on public material; no truth solver."""
    from carbon.battery.compile import compile_recipe
    from carbon.battery.worker import DirectBackend

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    decision_set = safety.load_decision_set(ROOT)
    cases = {row["case_id"]: row["inputs"] for row in decision_set.cases()}
    q1, members = _first_seed_panel()
    summaries = json.loads(PRACTICE_SUMMARIES.read_text(encoding="utf-8"))
    selected_recipes = {recipe for _, recipe, _, _ in members}
    if set(only) - selected_recipes:
        raise ValueError("unknown run-5 recipe")
    _verify_historical_jax_rebuild()
    backend = None
    for member, recipe_name, strategy, seed in members:
        if only and recipe_name not in only:
            continue
        if q1["members"][member]["recipe"] != recipe_name:
            raise ValueError("run-5 recipe identity mismatch")
        _, compiled = compile_recipe(strategy, implementation=RUN5_IMPLEMENTATION)
        if compiled.settings["backend"] != "jax":
            raise ValueError("run-5 public prototype requires JAX recipe")
        digest = compiled.recipe_digest
        if summaries[member]["recipe_digest"] != digest:
            raise ValueError("run-5 compiled recipe digest mismatch")
        identity = _receipt_context(member, recipe_name, seed, digest)
        target = out / (recipe_name + ".json")
        if target.exists():
            saved = json.loads(target.read_text(encoding="utf-8"))
            if (
                all(saved.get(key) == value for key, value in identity.items())
                and saved.get("result", {}).get("status") == "MEASURED_PUBLIC_PRACTICE"
            ):
                continue
            raise ValueError("stale or incomplete local receipt: " + recipe_name)
        if backend is None:
            backend = DirectBackend(ROOT)
        started = time.monotonic()
        state, _stats = backend.reconstruct(member, compiled, seed)
        predictions = backend.infer(member, state, cases)
        result = evaluate(predictions, decision_set)
        if result["status"] != "MEASURED_PUBLIC_PRACTICE":
            raise ValueError("public decision signal unmeasured: " + result["status"])
        target.write_text(
            json.dumps({**identity, "result": result}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "recipe": recipe_name,
                    "status": result["status"],
                    "seconds": round(time.monotonic() - started, 1),
                }
            ),
            flush=True,
        )


def _ranks(rows, key):
    values = [-row[key] for row in rows]
    target = [-row["development_value"] for row in rows]
    return {
        "kendall_tau_b": kendall_tau_b(values, target),
        "spearman_rho": spearman_rho(values, target),
    }


def report(out):
    """Matched public-aggregate comparison; fail closed on any missing member."""
    out = Path(out)
    q1, members = _first_seed_panel()
    summaries = json.loads(PRACTICE_SUMMARIES.read_text(encoding="utf-8"))
    rows = []
    for member, recipe_name, strategy, seed in members:
        from carbon.battery.compile import compile_recipe

        _, compiled = compile_recipe(strategy, implementation=RUN5_IMPLEMENTATION)
        identity = _receipt_context(member, recipe_name, seed, compiled.recipe_digest)
        path = out / (recipe_name + ".json")
        if not path.exists():
            raise ValueError("missing public-practice receipt: " + recipe_name)
        saved = json.loads(path.read_text(encoding="utf-8"))
        if any(saved.get(key) != value for key, value in identity.items()):
            raise ValueError(
                "public-practice receipt identity mismatch: " + recipe_name
            )
        measured = saved.get("result", {})
        if measured.get("status") != "MEASURED_PUBLIC_PRACTICE":
            raise ValueError("unmeasured public-practice receipt: " + recipe_name)
        source = q1["members"][member]
        if (
            source["development_decision_loss"] is None
            or source["cpu_practice_score"] is None
            or summaries[member]["summary"]["score"] != source["cpu_practice_score"]
            or summaries[member]["recipe_digest"] != compiled.recipe_digest
        ):
            raise ValueError("run-5 published aggregate mismatch: " + recipe_name)
        rows.append(
            {
                "recipe": recipe_name,
                "practice_accuracy_loss": source["cpu_practice_score"],
                "public_practice_decision_regret": measured["measures"]["regret"],
                "public_practice_false_feasible": measured["measures"][
                    "false_feasible"
                ],
                "public_practice_unresolved": measured["measures"]["unresolved"],
                "public_practice_over_caution": measured["measures"]["over_caution"],
                "public_practice_chosen": measured["chosen"],
                "public_practice_abstained": measured["abstained"],
                "public_practice_outcome_counts": measured["outcome_counts"],
                "development_value": source["development_decision_loss"],
                "practice_conditions_scored": measured["scored_conditions"],
                "practice_conditions_total": measured["conditions"],
                "practice_reference_unresolved": measured["reference_unresolved"],
                "practice_excluded_all_infeasible": measured["excluded_all_infeasible"],
            }
        )
    coverage = {row["practice_conditions_scored"] for row in rows}
    if len(coverage) != 1:
        raise ValueError("members have different public-practice condition masks")
    accuracy = _ranks(rows, "practice_accuracy_loss")
    decision_metric = _ranks(rows, "public_practice_decision_regret")
    result = {
        "schema": REPORT_SCHEMA,
        "status": "DEVELOPMENT_DIAGNOSTIC_ONLY",
        "public_set_sha256s_sha256": _public_pin(),
        "rule_digest": RULE_DIGEST,
        "run5_q1_report_sha256": _sha(Q1),
        "practice_summaries_sha256": _sha(PRACTICE_SUMMARIES),
        "recipes": len(rows),
        "practice_conditions_per_recipe": next(iter(coverage)),
        "development_value_common_resolved_scenarios": q1["mask"]["common_resolved"],
        "accuracy_vs_development_value": accuracy,
        "public_decision_regret_vs_development_value": decision_metric,
        "difference_decision_minus_accuracy": {
            key: (
                decision_metric[key] - accuracy[key]
                if decision_metric[key] is not None and accuracy[key] is not None
                else None
            )
            for key in accuracy
        },
        "per_recipe": rows,
        "limits": "Eight distinct recipes, one seed each; public six-condition practice set versus six previously used EV4 development scenarios. Retrospective association only; no exam prediction, gate, qualification, or miner-display decision.",
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("collect", "report"):
        command = sub.add_parser(name)
        command.add_argument("--out", type=Path, required=True)
        if name == "collect":
            command.add_argument("--recipe", action="append", default=[])
    args = parser.parse_args(argv)
    if args.command == "collect":
        collect(args.out, only=args.recipe)
    else:
        print(json.dumps(report(args.out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
