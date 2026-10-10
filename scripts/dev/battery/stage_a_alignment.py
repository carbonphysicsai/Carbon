"""Read-only Stage A score/value analysis of digest-bound DEVELOPMENT summaries.

The input is a deliberately narrow summary, not a Graphite operator record.
This module never reads predictions, case references, or hidden-pool files.
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

from carbon.battery.value import score_tuning as tuning
from carbon.design_search.score_value import kendall_tau_b, spearman_rho

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / "docs/development/evidence/battery-score-tuning/registry-v4.json"
CANDIDATE = "G-FEAS/A-Q@0.05"
SCHEMA = "carbon.battery.stage-a-alignment-input.v1"
REPORT_SCHEMA = "carbon.battery.stage-a-alignment-report.v1"
V3_SCHEMA = "carbon.battery.v3-score-inputs.v1"
SCOPE = "DEVELOPMENT_SUMMARY_ONLY"
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
STATES = {"SCORED", "CANDIDATE_FAILED", "FAILED_INFRA", "VOID"}
V3_FIELDS = {
    "schema",
    "identity",
    "recipe",
    "required_predictions",
    "status",
    "a",
    "q",
    "g_feas",
    "q3_regret",
    "raw_score",
    "eligible",
    "cause",
    "gate_verdict",
    "q3_scenarios",
    "cpu_seconds",
}
V3_IDENTITY_FIELDS = {
    "panel_sha256",
    "contract_sha256",
    "registry_sha256",
    "quiz_registry_sha256",
    "screening_batches",
    "screening_sha256",
    "q3_standard_sha256",
    "q3_refined_sha256",
    "settlement_rule",
    "scope",
    "job",
}
V3_RECIPE_FIELDS = {
    "member",
    "recipe_digest",
    "seed",
    "input_sha256",
    "confirmation_sha256",
    "prediction_sha256",
}


class Refused(ValueError):
    """Malformed or scientifically incomparable summary input."""


def _closed(value, fields, where):
    if type(value) is not dict or set(value) != set(fields):
        raise Refused(f"{where}_shape")


def _sha(value, where):
    if type(value) is not str or SHA.fullmatch(value) is None:
        raise Refused(f"{where}_digest")


def _number(value, where, *, nullable=False):
    if value is None and nullable:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise Refused(f"{where}_finite")
    return float(value)


def _text(value, where):
    if type(value) is not str or not value or len(value) > 200:
        raise Refused(f"{where}_text")


def _file(base, entry):
    _closed(entry, {"path", "sha256"}, "v3_file")
    _sha(entry["sha256"], "v3_file")
    if type(entry["path"]) is not str or not entry["path"]:
        raise Refused("v3_file_path")
    path = (base / entry["path"]).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError:
        raise Refused("v3_file_outside_input") from None
    body = path.read_bytes()
    if "sha256:" + hashlib.sha256(body).hexdigest() != entry["sha256"]:
        raise Refused("v3_file_digest_mismatch")
    return json.loads(body)


def _validate_member(row, context, base, candidate):
    _closed(
        row,
        {
            "member",
            "recipe",
            "recipe_digest",
            "seed",
            "confirmation_sha256",
            "practice",
            "exam",
            "decision",
            "v3_report",
        },
        "member",
    )
    for field in ("member", "recipe"):
        _text(row[field], field)
    if type(row["seed"]) is not int or row["seed"] < 0:
        raise Refused("seed_invalid")
    _sha(row["recipe_digest"], "recipe")
    _sha(row["confirmation_sha256"], "confirmation")
    practice = row["practice"]
    exam = row["exam"]
    decision = row["decision"]
    _closed(practice, {"state", "score", "panel_sha256", "source_sha256"}, "practice")
    _closed(
        exam,
        {
            "state",
            "score",
            "eligible",
            "rule",
            "rule_sha256",
            "pool_version",
            "device_class",
            "source_sha256",
        },
        "exam",
    )
    _closed(decision, {"state", "loss", "source_sha256"}, "decision")
    if practice["state"] not in STATES or exam["state"] not in STATES:
        raise Refused("score_state_invalid")
    _sha(practice["panel_sha256"], "practice_panel")
    _sha(practice["source_sha256"], "practice_source")
    _sha(exam["rule_sha256"], "exam_rule")
    _sha(exam["source_sha256"], "exam_source")
    _sha(decision["source_sha256"], "decision_source")
    if exam["rule"] != "v2":
        raise Refused("exam_not_v2")
    if type(exam["pool_version"]) is not int or exam["pool_version"] < 0:
        raise Refused("pool_version_invalid")
    _text(exam["device_class"], "device_class")
    if type(exam["eligible"]) is not bool and exam["eligible"] is not None:
        raise Refused("exam_eligible_invalid")
    if exam["state"] == "SCORED" and exam["eligible"] is None:
        raise Refused("exam_eligible_missing")
    for name, part in (("practice", practice), ("exam", exam)):
        score = _number(part["score"], name + "_score", nullable=True)
        if (
            part["state"] == "SCORED"
            and score is None
            and (name == "practice" or exam["eligible"])
        ):
            raise Refused(name + "_scored_without_score")
        if part["state"] != "SCORED" and score is not None:
            raise Refused(name + "_unscored_with_score")
    if decision["state"] not in ("RESOLVED", "UNRESOLVED", "FAILED_INFRA"):
        raise Refused("decision_state_invalid")
    loss = _number(decision["loss"], "decision_loss", nullable=True)
    if (decision["state"] == "RESOLVED") != (loss is not None):
        raise Refused("decision_loss_state_mismatch")
    if loss is not None and loss < 0:
        raise Refused("decision_loss_negative")
    report = None
    if row["v3_report"] is not None:
        report = _file(base, row["v3_report"])
        if type(report) is not dict or not set(report) <= V3_FIELDS:
            raise Refused("v3_report_fields")
        if report.get("schema") != V3_SCHEMA:
            raise Refused("v3_report_schema")
        identity = report.get("identity", {})
        recipe = report.get("recipe", {})
        if (
            type(identity) is not dict
            or not set(identity) <= V3_IDENTITY_FIELDS
            or type(recipe) is not dict
            or not set(recipe) <= V3_RECIPE_FIELDS
        ):
            raise Refused("v3_report_fields")
        if (
            identity.get("scope") != "PUBLIC_SYNTHETIC_DEVELOPMENT"
            or identity.get("job") != "battery-q3-v8"
            or identity.get("panel_sha256") != context["v3_panel_sha256"]
            or identity.get("registry_sha256") != context["v3_registry_sha256"]
            or recipe.get("member") != row["member"]
            or recipe.get("seed") != row["seed"]
            or recipe.get("recipe_digest") != row["recipe_digest"]
            or recipe.get("confirmation_sha256") != row["confirmation_sha256"]
        ):
            raise Refused("v3_report_identity_mismatch")
        if (
            report.get("status") in ("SCORED", "INELIGIBLE")
            and report.get("raw_score") is not None
        ):
            if type(report.get("eligible")) is not bool:
                raise Refused("v3_eligible_invalid")
            for key in ("a", "q", "g_feas", "raw_score", "q3_regret"):
                _number(report.get(key), "v3_" + key)
            if not (0 < report["a"] <= 1 and 0 < report["q"] <= 1):
                raise Refused("v3_leg_range")
            if not (0 <= report["g_feas"] <= 1 and report["q3_regret"] >= 0):
                raise Refused("v3_measure_range")
            if not math.isclose(
                report["q"], 1 / (1 + report["q3_regret"]), abs_tol=1e-12
            ):
                raise Refused("v3_q_regret_mismatch")
            screening_eligible = report["raw_score"] > 0
            leg_row = {
                "eligible": screening_eligible,
                "legs": {"a": report["a"], "q": report["q"]},
                "gates": {"feasibility": report["g_feas"]},
            }
            raw = tuning.score_member(candidate, leg_row)
            if raw is None or not math.isclose(raw, report["raw_score"], abs_tol=1e-12):
                raise Refused("v3_raw_score_mismatch")
            verdict = tuning.gate_verdict(candidate, leg_row)
            if report.get("gate_verdict") != verdict:
                raise Refused("v3_gate_verdict_mismatch")
            if report["eligible"] != (screening_eligible and verdict == "PASS"):
                raise Refused("v3_eligible_mismatch")
            if (report["status"] == "SCORED") != report["eligible"]:
                raise Refused("v3_status_mismatch")
        elif report.get("status") == "SCORED":
            raise Refused("v3_scored_without_legs")
    return report


def _cohort_key(row, context):
    exam = row["exam"]
    return (
        context["challenge"],
        context["level"],
        exam["rule_sha256"],
        exam["pool_version"],
        exam["device_class"],
        context["decision_measure"],
        context["decision_panel_sha256"],
        context["v3_panel_sha256"],
    )


def _metrics(scores, losses):
    if len(scores) < 2:
        return {"tau_b": None, "rho": None}
    values = [-loss for loss in losses]
    return {"tau_b": kendall_tau_b(scores, values), "rho": spearman_rho(scores, values)}


def _ordinal(keys):
    """Numeric ranks preserving lexicographic eligibility and score ordering."""
    order = {key: index for index, key in enumerate(sorted(set(keys)))}
    return [order[key] for key in keys]


def _quantile(values, p):
    ordered = sorted(values)
    point = (len(ordered) - 1) * p
    low = math.floor(point)
    high = math.ceil(point)
    return ordered[low] + (ordered[high] - ordered[low]) * (point - low)


def _bootstrap(rows, score_key, draws, seed):
    groups = {}
    for row in rows:
        groups.setdefault(row["recipe"], []).append(row)
    keys = sorted(groups)
    rng = random.Random(seed)
    samples = {"tau_b": [], "rho": []}
    for _ in range(draws):
        sampled = [r for _ in keys for r in groups[rng.choice(keys)]]
        metric = _metrics([r[score_key] for r in sampled], [r["loss"] for r in sampled])
        for name, values in samples.items():
            if metric[name] is not None:
                values.append(metric[name])
    return {
        name: (
            {
                "low": _quantile(values, 0.025),
                "high": _quantile(values, 0.975),
                "defined_draws": len(values),
            }
            if values
            else {"low": None, "high": None, "defined_draws": 0}
        )
        for name, values in samples.items()
    }


def _divergences(rows, score_key, *, with_terms):
    results = []
    for x in rows:
        better = []
        for y in rows:
            if y is x or not (y["loss"] < x["loss"] and x[score_key] >= y[score_key]):
                continue
            pair = {"better_decider": y["member"], "loss_gap": x["loss"] - y["loss"]}
            if with_terms:
                pair["accuracy_log_delta"] = 0.5 * math.log(x["a"] / y["a"])
                pair["q3_log_delta"] = 0.5 * math.log(x["q"] / y["q"])
                pair["g_feas_gate"] = {"member": x["gate"], "better_decider": y["gate"]}
                pair["screening_eligible"] = {
                    "member": x["eligible"],
                    "better_decider": y["eligible"],
                }
            better.append(pair)
        if better:
            results.append({"member": x["member"], "inversions": better})
    return results


def _practice_exam(rows):
    by_recipe = {}
    for row in rows:
        by_recipe.setdefault(row["recipe"], []).append(row)
    table = []
    for recipe, members in sorted(by_recipe.items()):
        table.append(
            {
                "recipe": recipe,
                "members": [
                    {
                        "member": r["member"],
                        "seed": r["seed"],
                        "practice_score_lower_better": r["practice"],
                        "v2_exam_score_lower_better": r["exam"],
                        "v2_exam_eligible": r["exam_eligible"],
                    }
                    for r in sorted(members, key=lambda m: m["seed"])
                ],
                "mean_practice_score": statistics.fmean(r["practice"] for r in members),
                "mean_exam_score": (
                    statistics.fmean(r["exam"] for r in members)
                    if all(r["exam_eligible"] for r in members)
                    else None
                ),
            }
        )
    panels = {r["practice_panel"] for r in rows}
    same_exam_eligibility = all(r["exam_eligible"] for r in rows)
    association = (
        _metrics(
            [-r["mean_practice_score"] for r in table],
            [r["mean_exam_score"] for r in table],
        )
        if len(panels) == 1 and same_exam_eligibility
        else {"tau_b": None, "rho": None}
    )
    return {
        "per_recipe": table,
        "practice_panels": len(panels),
        "rank_association": association,
        "rank_association_status": (
            "DIFFERENT_PRACTICE_PANELS"
            if len(panels) != 1
            else "EXAM_INELIGIBILITY" if not same_exam_eligibility else "COMPARABLE"
        ),
    }


def analyze(path, *, draws=500, seed=20261009):
    """Analyze one planned Stage A summary; incomplete cohorts stay unmeasured."""
    if type(draws) is not int or draws < 1 or type(seed) is not int:
        raise Refused("bootstrap_parameters_invalid")
    body = Path(path).read_bytes()
    source = json.loads(body)
    _closed(source, {"schema", "scope", "context", "members"}, "input")
    if source["schema"] != SCHEMA or source["scope"] != SCOPE:
        raise Refused("development_summary_required")
    context = source["context"]
    _closed(
        context,
        {
            "challenge",
            "level",
            "decision_measure",
            "decision_panel_sha256",
            "v3_panel_sha256",
            "v3_registry_sha256",
        },
        "context",
    )
    if context["challenge"] != "battery-fastcharge-ageing-development-v1":
        raise Refused("battery_challenge_required")
    if type(context["level"]) is not int or context["level"] < 0:
        raise Refused("level_invalid")
    _text(context["decision_measure"], "decision_measure")
    for name in ("decision_panel_sha256", "v3_panel_sha256", "v3_registry_sha256"):
        _sha(context[name], name)
    registry_body = REGISTRY.read_bytes()
    if (
        context["v3_registry_sha256"]
        != "sha256:" + hashlib.sha256(registry_body).hexdigest()
    ):
        raise Refused("v3_registry_mismatch")
    candidate = tuning.load_registry(REGISTRY, repository=ROOT)[0][CANDIDATE]
    if (
        candidate.kind != "geometric"
        or candidate.stable
        or candidate.weights != {"a": 0.5, "q": 0.5}
        or candidate.gate != {"measure": "feasibility", "cutoff": 0.05}
    ):
        raise Refused("v3_rule_mismatch")
    if type(source["members"]) is not list or not source["members"]:
        raise Refused("members_empty")
    cohorts = {}
    seen = set()
    for member in source["members"]:
        report = _validate_member(member, context, Path(path).parent, candidate)
        if member["member"] in seen:
            raise Refused("duplicate_member")
        seen.add(member["member"])
        cohorts.setdefault(_cohort_key(member, context), []).append((member, report))
    out = []
    for key, entries in sorted(cohorts.items()):
        missing = []
        rows = []
        base_missing = False
        v3_missing = False
        for member, report in entries:
            base_causes = []
            for name in ("practice", "exam"):
                if member[name]["state"] != "SCORED":
                    base_causes.append(name + ":" + member[name]["state"])
            if member["decision"]["state"] != "RESOLVED":
                base_causes.append("decision:" + member["decision"]["state"])
            v3_causes = []
            if report is None:
                v3_causes.append("v3:REPORT_MISSING")
            elif report.get("status") not in ("SCORED", "INELIGIBLE"):
                v3_causes.append("v3:" + str(report.get("status")))
            elif report.get("raw_score") is None:
                v3_causes.append("v3:INELIGIBLE_NO_LEGS")
            causes = base_causes + v3_causes
            if causes:
                missing.append({"member": member["member"], "causes": causes})
            base_missing |= bool(base_causes)
            v3_missing |= bool(v3_causes)
            if base_causes:
                continue
            row = {
                "member": member["member"],
                "recipe": member["recipe"],
                "seed": member["seed"],
                "practice": member["practice"]["score"],
                "practice_panel": member["practice"]["panel_sha256"],
                "exam": member["exam"]["score"],
                "exam_eligible": member["exam"]["eligible"],
                "v2": None,
                "loss": member["decision"]["loss"],
            }
            if not v3_causes:
                row.update(
                    {
                        "a": report["a"],
                        "q": report["q"],
                        "g_feas": report["g_feas"],
                        "gate": report["gate_verdict"],
                        "eligible": report["raw_score"] > 0,
                        "overall_eligible": report["eligible"],
                        "raw_score": report["raw_score"],
                    }
                )
            rows.append(row)
        identity = {
            "challenge": key[0],
            "level": key[1],
            "v2_rule_sha256": key[2],
            "pool_version": key[3],
            "device_class": key[4],
            "decision_measure": key[5],
            "decision_panel_sha256": key[6],
            "v3_panel_sha256": key[7],
        }
        result = {
            "cohort": identity,
            "planned_members": len(entries),
            "v2_members": len(rows),
            "matched_members": sum("a" in row for row in rows),
            "unmeasured_members": missing,
            "status": (
                "UNMEASURED"
                if base_missing or len(rows) < 2
                else "V2_ONLY" if v3_missing else "MEASURED"
            ),
            "v2": None,
            "v3": None,
            "practice_vs_exam": None,
        }
        if result["status"] == "UNMEASURED":
            out.append(result)
            continue
        rows.sort(key=lambda r: r["member"])
        v2_ordinals = _ordinal(
            [
                (r["exam_eligible"], -r["exam"] if r["exam_eligible"] else 0)
                for r in rows
            ]
        )
        for row, ordinal in zip(rows, v2_ordinals, strict=True):
            row["v2"] = ordinal
        losses = [r["loss"] for r in rows]
        result["v2"] = {
            "score_rule": "v2_hidden_exam_as_recorded_lower_better",
            "alignment": _metrics([r["v2"] for r in rows], losses),
            "bootstrap_95_descriptive": _bootstrap(rows, "v2", draws, seed),
            "divergent_members": _divergences(rows, "v2", with_terms=False),
        }
        result["practice_vs_exam"] = _practice_exam(rows)
        if result["status"] == "V2_ONLY":
            out.append(result)
            continue
        legs = {
            r["member"]: {
                "eligible": r["eligible"],
                "E": None,
                "legs": {"a": r["a"], "q": r["q"]},
                "gates": {"feasibility": r["g_feas"]},
            }
            for r in rows
        }
        recipe_by_member = {r["member"]: r["recipe"] for r in rows}
        ranked, _ = tuning.candidate_scores(
            candidate, legs, recipe_by_member.__getitem__
        )
        if any(ranked[r["member"]] is None for r in rows):
            raise Refused("v3_rank_unavailable")
        for r in rows:
            r["v3"] = ranked[r["member"]]
        result["v3"] = {
            "score_rule": CANDIDATE,
            "alignment": _metrics([r["v3"] for r in rows], losses),
            "bootstrap_95_descriptive": _bootstrap(rows, "v3", draws, seed),
            "term_alignment": {
                "accuracy_a": _metrics([r["a"] for r in rows], losses),
                "q3_q": _metrics([r["q"] for r in rows], losses),
                "g_feas_lower_better": _metrics([-r["g_feas"] for r in rows], losses),
            },
            "per_member_contributions": [
                {
                    "member": r["member"],
                    "accuracy_half_log": 0.5 * math.log(r["a"]),
                    "q3_half_log": 0.5 * math.log(r["q"]),
                    "g_feas": r["g_feas"],
                    "gate_verdict": r["gate"],
                    "screening_eligible": r["eligible"],
                    "overall_eligible": r["overall_eligible"],
                    "rank_score": r["v3"],
                }
                for r in rows
            ],
            "divergent_members": _divergences(rows, "v3", with_terms=True),
        }
        out.append(result)
    return {
        "schema": REPORT_SCHEMA,
        "scope": SCOPE,
        "input_sha256": "sha256:" + hashlib.sha256(body).hexdigest(),
        "bootstrap": {
            "unit": "recipe_cluster_with_all_seeds",
            "draws": draws,
            "seed": seed,
            "interval": "descriptive_percentile_95",
        },
        "cohorts": out,
        "interpretation": "development analysis only; no score-rule adoption or qualification",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--draws", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20261009)
    args = parser.parse_args(argv)
    print(json.dumps(analyze(args.input, draws=args.draws, seed=args.seed), indent=2))


if __name__ == "__main__":
    main()
