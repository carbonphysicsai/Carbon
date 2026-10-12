"""Development-only three-arm winnability pilot over precomputed evidence.

No model, reference solver, or training code is invoked here. A prospective
pilot reuses equal_budget's verified replay and charges preparation at an
explicit served-decision amortisation. The EV4 retrospective is a separate,
unmatched historical diagnostic; it never becomes a VALUE-BAR verdict.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path

from . import budget_registration as br
from . import equal_budget as eb

SCHEMA = "carbon.design-search.winnability-pilot-input.v1"
REPORT_SCHEMA = "carbon.design-search.winnability-pilot-report.v1"
RETRO_SCHEMA = "carbon.design-search.winnability-battery-ev4-retro.v1"
RES07_SCHEMA = "carbon.research.value-metric-audit.v1"
FAMILIES = ("nominal", "shifted", "robust_soc", "robust_temperature")
CAPS = ("1", "3", "5")


class WinnabilityError(ValueError):
    """Malformed evidence or an unsupported retrospective source."""


def _digest(body):
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _finite(value, *, nonnegative=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise WinnabilityError("finite numeric measurement required")
    if nonnegative and value < 0:
        raise WinnabilityError("nonnegative measurement required")
    return float(value)


def _cost(value):
    if type(value) is not dict or set(value) != {"wall_s", "core_s"}:
        raise WinnabilityError("wall_s and core_s cost required")
    return {key: _finite(value[key], nonnegative=True) for key in value}


def _learning(rows, panel):
    jobs = {job["job_id"]: job for job in panel["jobs"]}
    if type(rows) is not list or len(rows) != len(jobs):
        raise WinnabilityError("one learning outcome per independent question required")
    seen = set()
    groups = defaultdict(list)
    for row in rows:
        required = {
            "job_id",
            "cluster_id",
            "stratum",
            "reference_status",
            "pointwise_error",
            "decision_agreement",
            "false_feasible",
            "missed_feasible",
            "abstained",
        }
        if type(row) is not dict or set(row) != required:
            raise WinnabilityError("closed learning-outcome schema required")
        job_id = row["job_id"]
        if job_id not in jobs or job_id in seen:
            raise WinnabilityError("unknown or repeated learning question")
        seen.add(job_id)
        if row["cluster_id"] != jobs[job_id]["cluster_id"]:
            raise WinnabilityError("learning cluster differs from reference panel")
        if not isinstance(row["stratum"], str) or not row["stratum"]:
            raise WinnabilityError("registered stratum required")
        statuses = {c["reference"]["status"] for c in jobs[job_id]["candidates"]}
        expected = (
            "FEASIBLE_EXISTS"
            if "FEASIBLE" in statuses
            else "UNRESOLVED" if "UNRESOLVED" in statuses else "NONE_FEASIBLE"
        )
        if row["reference_status"] != expected:
            raise WinnabilityError("learning reference status differs from panel")
        if row["pointwise_error"] is not None:
            _finite(row["pointwise_error"], nonnegative=True)
        for key in (
            "decision_agreement",
            "false_feasible",
            "missed_feasible",
            "abstained",
        ):
            if row[key] is not None and type(row[key]) is not bool:
                raise WinnabilityError(
                    "learning outcomes must be boolean or unresolved"
                )
        if expected == "UNRESOLVED" and any(
            row[key] is not None
            for key in required
            - {"job_id", "cluster_id", "stratum", "reference_status"}
        ):
            raise WinnabilityError("unresolved references cannot become model outcomes")
        groups[row["stratum"]].append(row)
    return {
        name: {
            "questions": len(items),
            "resolved": sum(item["reference_status"] != "UNRESOLVED" for item in items),
            "mean_pointwise_error": _mean(
                [
                    item["pointwise_error"]
                    for item in items
                    if item["pointwise_error"] is not None
                ]
            ),
            "decision_agreement_fraction": _mean(
                [
                    float(item["decision_agreement"])
                    for item in items
                    if item["decision_agreement"] is not None
                ]
            ),
            "false_feasible_count": sum(
                item["false_feasible"] is True for item in items
            ),
            "missed_feasible_count": sum(
                item["missed_feasible"] is True for item in items
            ),
            "false_feasible_fraction_resolved": _mean(
                [
                    float(item["false_feasible"])
                    for item in items
                    if item["false_feasible"] is not None
                ]
            ),
            "missed_feasible_fraction_resolved": _mean(
                [
                    float(item["missed_feasible"])
                    for item in items
                    if item["missed_feasible"] is not None
                ]
            ),
            "abstention_count": sum(item["abstained"] is True for item in items),
            "none_feasible_count": sum(
                item["reference_status"] == "NONE_FEASIBLE" for item in items
            ),
            "unresolved_count": sum(
                item["reference_status"] == "UNRESOLVED" for item in items
            ),
        }
        for name, items in sorted(groups.items())
    }


def _mean(values):
    return sum(values) / len(values) if values else None


def _paired(rows, direction):
    sign = 1 if direction == "max" else -1
    deltas = []
    wins = []
    for result in rows:
        model = result["model_then_solver"]["value"]
        cheap = result["baseline_then_solver"]["value"]
        if model is not None and cheap is not None:
            deltas.append(sign * (model - cheap))
        wins.append(
            float(model is not None and (cheap is None or sign * (model - cheap) > 0))
        )
    return {
        "paired_model_minus_cheap_improvement": (
            _mean(deltas) if len(deltas) == len(rows) else None
        ),
        "paired_complete_questions": len(deltas),
        "p_model_strictly_beats_cheap": _mean(wins),
    }


def _paired_curve(panel, registration, *, replicates, confidence, seed):
    direction = panel["objective"]["direction"]
    clusters = defaultdict(list)
    for job in panel["jobs"]:
        clusters[job["cluster_id"]].append(job)
    cluster_ids = sorted(clusters)
    curves = []
    registered = eb.CHALLENGE_ROUTES[panel["challenge"]]["validator"](registration)
    for position, budget in enumerate(panel["budgets"]):
        limit = eb._cost(budget, "budget")
        cap = registered.cap(panel["challenge"], br.TIERS[position])
        by_cluster = {
            cluster: [eb._one(job, limit, direction, cap=cap) for job in jobs]
            for cluster, jobs in clusters.items()
        }
        observed = _paired(
            [r for cluster in cluster_ids for r in by_cluster[cluster]], direction
        )
        interval = None
        if (
            len(cluster_ids) >= 2
            and observed["paired_model_minus_cheap_improvement"] is not None
        ):
            rng = random.Random(seed)
            draws = []
            for _ in range(replicates):
                selected = [rng.choice(cluster_ids) for _ in cluster_ids]
                statistic = _paired(
                    [r for c in selected for r in by_cluster[c]], direction
                )
                draws.append(statistic["paired_model_minus_cheap_improvement"])
            tail = (1 - confidence) / 2
            interval = [eb._quantile(draws, tail), eb._quantile(draws, 1 - tail)]
        curves.append(
            {"budget": budget, "paired": observed, "paired_bootstrap_ci": interval}
        )
    return curves


def evaluate(source, *, bootstrap_replicates, confidence, seed):
    """Replay a registered development panel, without setting pass thresholds."""
    required = {
        "schema",
        "evidence_class",
        "panel",
        "registration",
        "methods",
        "question_law",
        "preparation_cost",
        "served_decisions",
        "learning",
        "learning_unit",
        "cost_record_digest",
    }
    if (
        type(source) is not dict
        or set(source) != required
        or source["schema"] != SCHEMA
    ):
        raise WinnabilityError("closed pilot input schema required")
    if source["evidence_class"] != "DEVELOPMENT_PUBLIC":
        raise WinnabilityError("public development evidence only")
    methods = source["methods"]
    if (
        type(methods) is not dict
        or set(methods) != {"model", "cheap", "solver"}
        or methods
        != {
            "model": "PLAIN_L0_MLP",
            "cheap": "STRONGEST_APPLICABLE_CHEAP",
            "solver": "REGISTERED_ADAPTIVE_SOLVER",
        }
    ):
        raise WinnabilityError(
            "plain L0, strongest cheap, and adaptive solver arms required"
        )
    law = source["question_law"]
    if (
        type(law) is not dict
        or set(law) != {"P", "Q", "w", "panel_use"}
        or law["panel_use"] != "PUBLIC_HELDOUT"
        or any(not isinstance(law[k], str) or not law[k] for k in ("P", "Q", "w"))
    ):
        raise WinnabilityError("separate P/Q/w and public held-out role required")
    if not isinstance(source["learning_unit"], str) or not source["learning_unit"]:
        raise WinnabilityError("unit for pointwise error required")
    if not isinstance(source["cost_record_digest"], str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", source["cost_record_digest"]
    ):
        raise WinnabilityError("digest-bound complete workflow cost record required")
    costs = source["preparation_cost"]
    if type(costs) is not dict or set(costs) != {"model", "baseline"}:
        raise WinnabilityError("model fit and cheap-map acquisition costs required")
    preparation = {key: _cost(value) for key, value in costs.items()}
    served = source["served_decisions"]
    if (
        type(served) is not list
        or not served
        or any(type(n) is not int or n < 1 for n in served)
        or len(set(served)) != len(served)
    ):
        raise WinnabilityError("explicit served-decision amortisation required")
    panel = source["panel"]
    eb._validate(panel)
    if panel["evidence_class"] != "DEVELOPMENT":
        raise WinnabilityError("development panel required")
    registration = source["registration"]
    registered = eb.CHALLENGE_ROUTES[panel["challenge"]]["validator"](registration)
    if panel["registrations"]["cost_plan"] != registered.registration_id:
        raise WinnabilityError("cost plan differs from registration")
    learning = _learning(source["learning"], panel)
    reports = []
    for n in served:
        charged = copy.deepcopy(panel)
        charged.pop("panel_digest")
        for job in charged["jobs"]:
            for name in ("model", "baseline"):
                for unit in ("wall_s", "core_s"):
                    job["screen_cost"][name][unit] += preparation[name][unit] / n
        charged = eb.seal(charged)
        replay = eb.compare(
            charged,
            bootstrap_replicates=bootstrap_replicates,
            confidence=confidence,
            seed=seed,
            registration=registration,
        )
        paired = (
            []
            if replay["status"] != "OK"
            else _paired_curve(
                charged,
                registration,
                replicates=bootstrap_replicates,
                confidence=confidence,
                seed=seed,
            )
        )
        headroom = [
            {
                "budget": curve["budget"],
                "finite_bank_mean_mlp_regret_conditional": curve["estimates"][
                    "model_then_solver"
                ]["mean_regret_conditional"],
                "mlp_feasible_pick_fraction": curve["estimates"]["model_then_solver"][
                    "feasible_pick_fraction"
                ],
                "unit": panel["objective"]["unit"],
            }
            for curve in replay["curves"]
        ]
        reports.append(
            {
                "served_decisions_assumption": n,
                "equal_budget": replay,
                "model_vs_cheap": paired,
                "finite_bank_headroom": headroom,
            }
        )
    return {
        "schema": REPORT_SCHEMA,
        "maturity": "PROPOSED_DEVELOPMENT_ONLY",
        "challenge": panel["challenge"],
        "input_digest": _digest(source),
        "source_panel_digest": panel["panel_digest"],
        "budget_registration_digest": registered.registration_digest,
        "cost_record_digest": source["cost_record_digest"],
        "question_law": law,
        "learning_unit": source["learning_unit"],
        "learnable": learning,
        "advantage_and_headroom": reports,
        "thresholds": "HUMAN_INPUT",
        "qualification": "UNDECIDED",
    }


def battery_ev4_retrospective(res07, public_input_root):
    """Summarise RES-07's stored public EV4 replay, preserving its cost gaps."""
    if type(res07) is not dict or res07.get("schema") != RES07_SCHEMA:
        raise WinnabilityError("committed RES-07 aggregate required")
    source = Path(public_input_root)
    reference = source / "ev4-decision-references.jsonl"
    digest = hashlib.sha256(reference.read_bytes()).hexdigest()
    if digest != res07["inventory"]["public_reference_sha256"]:
        raise WinnabilityError("public EV4 reference digest differs from RES-07")
    manifests = {
        entry["file"]: entry for entry in res07["inventory"]["bundle_manifest"]
    }
    for name in ("mlp-s0.json.gz", "mlp-s1.json.gz", "mlp-s2.json.gz"):
        item = manifests[name]
        path = source / item["folder"] / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise WinnabilityError("public plain-MLP bundle digest differs from RES-07")
    families = {}
    for family in FAMILIES:
        replay = res07["verified_workflow_sensitivity"][family]
        baseline = res07["additional_cached_baselines_and_checks"]["by_family"].get(
            family
        )
        mlp = res07["fresh_member_summary"]["mlp-s0"][family]
        summary = {
            "offered_questions": mlp["offered"],
            "known_opportunity_questions": len(
                replay.get("known_opportunity_questions", [])
            ),
            "mlp_s0_observed_unsafe_picks": mlp["observed_unsafe"],
            "mlp_s0_outcome_counts": mlp["kinds"],
            "caps": {},
        }
        for cap in CAPS:
            if replay.get("status") == "NO_PRICED_OPPORTUNITIES":
                break
            comparison = replay["by_budget"][cap]
            cheap = (
                None
                if baseline is None
                else baseline["by_budget"][cap]["cached_D_maps"]["bilinear_D_clamped"]
            )
            summary["caps"][cap] = {
                "plain_mlp_s0_gain_u": comparison["per_member"]["mlp-s0"]["gain"],
                "cheap_bilinear_gain_u": None if cheap is None else cheap["gain"],
                "illustrative_fixed_order_solver_gain_u": comparison[
                    "fixed_solver_alone"
                ]["gain"],
                "finite_bank_cache_ceiling_gain_u": comparison[
                    "cheap_public_exact_cache_gain"
                ],
                "mlp_s0_attempts_mean": comparison["per_member"]["mlp-s0"]["attempts"],
            }
        families[family] = summary
    return {
        "schema": RETRO_SCHEMA,
        "maturity": "PROPOSED_RETROSPECTIVE_DIAGNOSTIC",
        "job": "historical battery EV4 CV-onset decision; not battery v3",
        "value_unit": "historical 120-second CV-onset gain unit",
        "panel_previously_used_for_development": True,
        "source_res07_content_digest": _digest(res07),
        "source_reference_sha256": "sha256:" + digest,
        "public_mlp_bundle_sha256": {
            name: "sha256:" + manifests[name]["sha256"]
            for name in ("mlp-s0.json.gz", "mlp-s1.json.gz", "mlp-s2.json.gz")
        },
        "source_res07_schema": RES07_SCHEMA,
        "families": families,
        "learnable": "PARTIAL_PUBLIC_DECISION_EVIDENCE; pointwise buyer-useful accuracy not established",
        "advantage": "INDETERMINATE_UNMATCHED_COMPLETE_COST",
        "headroom": "FINITE_BANK_DIAGNOSTIC_ONLY",
        "cheap_method_status": "D-only bilinear response map; strongest industry method unproved",
        "solver_method_status": "illustrative fixed order; adaptive competitor unmeasured",
        "missing_for_matched_pilot": [
            "independent public held-out buyer-question clusters",
            "registered strong adaptive solver-alone proposal and complete costs",
            "full model fitting, cheap-map acquisition, query, refinement, and verification wall/core costs",
            "buyer thresholds and uncertainty resolution",
        ],
        "thresholds": "HUMAN_INPUT",
        "qualification": "UNDECIDED",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pilot = commands.add_parser("evaluate")
    pilot.add_argument("input")
    pilot.add_argument("--bootstrap-replicates", type=int, required=True)
    pilot.add_argument("--confidence", type=float, required=True)
    pilot.add_argument("--seed", type=int, required=True)
    retro = commands.add_parser("battery-ev4-retro")
    retro.add_argument("--res07", required=True)
    retro.add_argument("--public-input-root", required=True)
    args = parser.parse_args(argv)
    if args.command == "evaluate":
        report = evaluate(
            json.loads(Path(args.input).read_text()),
            bootstrap_replicates=args.bootstrap_replicates,
            confidence=args.confidence,
            seed=args.seed,
        )
    else:
        report = battery_ev4_retrospective(
            json.loads(Path(args.res07).read_text()), args.public_input_root
        )
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
