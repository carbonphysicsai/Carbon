"""Configurable analytic physics and task-neighbourhood Score Lab experiment.

All quantities here are toy assumptions. No Challenge law, tolerance, or buyer
population is inferred from these surfaces.
"""

from __future__ import annotations

import copy
import hashlib
import math
import statistics

from . import candidates, synthetic
from .core import LabRefused, analyze, canonical_sha, validate_panel

SCHEMA = "carbon.dev.score-lab-physics-config.v1"
TRAITS = ("law_violations", "rollout_drift", "robustness", "extrapolation")
DIRECTIONS = ("objective", "constraint", "operating", "boundary")
MODES = ("OFF", "GATE", "FLOOR", "BLEND")
ERROR_REGIONS = ("uniform", "boundary", "optimum")


def _finite(value, *, low=0.0, high=None):
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and value >= low
        and (high is None or value <= high)
    )


def validate_config(config):
    if config.get("schema") != SCHEMA:
        raise LabRefused("physics_config_schema")
    problem = config.get("problem", {})
    if (
        problem.get("space") not in ("small-grid", "continuous")
        or problem.get("optima") not in ("single", "multi")
        or problem.get("constraint") not in ("loose", "tight")
        or problem.get("shift") not in ("nominal", "shifted")
        or not _finite(problem.get("verification_cost_ASSUMPTION"), low=0)
    ):
        raise LabRefused("physics_problem_assumptions")
    if (
        type(config.get("questions_per_side")) is not int
        or config["questions_per_side"] < 3
    ):
        raise LabRefused("physics_question_count")
    decision = config.get("decision", {})
    if config.get("value_definition", "v2_shortlist") not in (
        "v2_shortlist",
        "legacy_one_pick",
    ):
        raise LabRefused("physics_value_definition")
    if (
        type(decision.get("k")) is not int
        or decision["k"] < 1
        or not _finite(decision.get("unit"), low=1e-12)
        or not _finite(decision.get("abstention_loss"))
        or not _finite(decision.get("unsafe_loss"))
    ):
        raise LabRefused("physics_decision_assumptions")
    hood = config.get("neighbourhood", {})
    if (
        not _finite(hood.get("size"))
        or not _finite(hood.get("score_weight"), high=1)
        or not _finite(hood.get("value_weight"), high=1)
        or not _finite(hood.get("extrapolation_distance"))
        or not isinstance(hood.get("directions"), list)
        or not hood["directions"]
        or len(hood["directions"]) != len(set(hood["directions"]))
        or any(x not in DIRECTIONS for x in hood["directions"])
    ):
        raise LabRefused("physics_neighbourhood_assumptions")
    if (
        not _finite(config.get("coverage"), high=1)
        or not _finite(config.get("good_fraction"), low=1e-12, high=1)
        or type(config.get("bootstrap")) is not int
        or config["bootstrap"] < 1
    ):
        raise LabRefused("physics_coverage_or_bootstrap")
    population = config.get("population")
    if not isinstance(population, list) or len(population) < 3:
        raise LabRefused("physics_population")
    ids = [m.get("id") for m in population if isinstance(m, dict)]
    if len(ids) != len(population) or len(set(ids)) != len(ids):
        raise LabRefused("physics_member_id")
    for member in population:
        if (
            not isinstance(member.get("id"), str)
            or member.get("kind") not in ("MODEL", "PROBE")
            or not _finite(member.get("noise"))
            or not _finite(member.get("transfer"), high=1)
            or type(member.get("score_path_only", False)) is not bool
            or not _finite(member.get("law_rate"), high=1)
            or not all(
                _finite(member.get(key))
                for key in ("law_size", "rollout_drift", "robustness", "extrapolation")
            )
            or not _finite(member.get("heteroscedasticity", 0), high=5)
            or member.get("error_region", "uniform") not in ERROR_REGIONS
            or not _finite(member.get("cross_design_correlation", 0), high=1)
            or not _finite(member.get("tail_rate", 0), high=1)
            or not _finite(member.get("tail_size", 0))
            or not _finite(member.get("sigma_scale", 1), low=1e-12)
        ):
            raise LabRefused("physics_member_traits")
    if sum(m["kind"] == "MODEL" for m in population) < 3:
        raise LabRefused("physics_primary_population")
    sweep = config.get("physics_sweep")
    if not isinstance(sweep, list) or not sweep:
        raise LabRefused("physics_sweep_missing")
    for item in sweep:
        if item.get("mode") not in MODES:
            raise LabRefused("physics_mode")
        if not isinstance(item.get("limit"), dict) or not isinstance(
            item.get("weight"), dict
        ):
            raise LabRefused("physics_limits")
        if any(
            key not in (*TRAITS, "b15", "b9", "b16") or not _finite(value)
            for field in ("limit", "weight")
            for key, value in item[field].items()
        ):
            raise LabRefused("physics_limits")
        if item["mode"] in ("GATE", "FLOOR") and not item["limit"]:
            raise LabRefused("physics_limit_missing")
        if item["mode"] == "BLEND" and (
            not item["weight"]
            or any(item["limit"].get(key, 0) <= 0 for key in item["weight"])
        ):
            raise LabRefused("physics_blend_denominator")
    if sweep[0]["mode"] != "OFF" or sum(x["mode"] == "OFF" for x in sweep) != 1:
        raise LabRefused("physics_off_baseline_required")
    return config


def _hash_fraction(*parts):
    raw = ":".join(str(x) for x in parts).encode()
    return int(hashlib.sha256(raw).hexdigest()[:15], 16) / float(16**15)


def _toy_truth(x, context, problem, direction=None, size=0.0):
    shifted_x = min(1.0, max(0.0, x + (size if direction == "boundary" else 0)))
    shifted_context = context + (size if direction == "operating" else 0)
    row = synthetic.truth(shifted_x, shifted_context, problem)
    objective = row["objective"] * (
        1.0 + size * (x - 0.5) if direction == "objective" else 1.0
    )
    margins = list(row["margins"])
    if direction == "constraint":
        margins[0] -= size
    return {
        "objective": objective,
        "margins": tuple(margins),
        "status": "FEASIBLE" if min(margins) >= 0 else "INFEASIBLE",
        "solves": 1,
    }


def _question(qid, context, problem, *, direction=None, size=0.0):
    base = synthetic._question(qid, context, problem)
    base["actions"] = {
        aid: _toy_truth(float(aid[2:]), context, problem, direction, size)
        for aid in base["actions"]
    }
    feasible = [
        row["objective"]
        for row in base["actions"].values()
        if row["status"] == "FEASIBLE"
    ]
    safe_ids = [
        aid for aid, row in base["actions"].items() if row["status"] == "FEASIBLE"
    ]
    if safe_ids:
        base["fallback"] = min(
            safe_ids, key=lambda aid: (abs(float(aid[2:]) - 0.2), aid)
        )
    base["exact_best_objective"] = min(feasible) if feasible else None
    return base


def _predict(member, qid, aid, question, *, base_question, horizon, perturbation):
    reference = question["actions"][aid]
    old = base_question["actions"][aid]
    rng = synthetic._rng(member["id"], qid, aid)
    path_only = member.get("score_path_only", False) and qid.startswith("S-")
    noise = 0.0 if path_only else member["noise"]
    transfer_gap = 0.0 if path_only else 1.0 - member["transfer"]
    rollout = 0.0 if path_only else member["rollout_drift"]
    robustness = 0.0 if path_only else member["robustness"]
    extrapolation = 0.0 if path_only else member["extrapolation"]
    region = member.get("error_region", "uniform")
    if region == "boundary":
        locality = max(0.0, 1.0 - min(abs(v) for v in reference["margins"]) / 0.15)
    elif region == "optimum":
        best = question["exact_best_objective"]
        locality = (
            max(0.0, 1.0 - (reference["objective"] - best) / 0.15)
            if best is not None
            else 0.0
        )
    else:
        locality = 1.0
    local_noise = noise * (1 + member.get("heteroscedasticity", 0) * locality)
    correlation = member.get("cross_design_correlation", 0)
    shared_rng = synthetic._rng(member["id"], qid, "shared-error")

    def error():
        independent = rng.gauss(0, local_noise)
        common = shared_rng.gauss(0, local_noise)
        return (
            independent * math.sqrt(1 - correlation * correlation)
            + common * correlation
        )

    objective = (
        reference["objective"]
        + transfer_gap * (old["objective"] - reference["objective"])
        + error()
        + rollout * horizon
        + robustness * perturbation
    )
    margins = [
        reference["margins"][j]
        + transfer_gap * (old["margins"][j] - reference["margins"][j])
        + error()
        + robustness * perturbation
        for j in (0, 1)
    ]
    if not path_only and _hash_fraction(member["id"], qid, aid, "tail") < member.get(
        "tail_rate", 0
    ):
        sign = 1 if _hash_fraction(member["id"], qid, aid, "tail-sign") < 0.5 else -1
        size = member.get("tail_size", 0)
        objective -= sign * size
        margins = [value + sign * size for value in margins]
    if qid.startswith("X-"):
        objective += extrapolation * perturbation
        margins = [v + extrapolation * perturbation for v in margins]
    if (
        not path_only
        and _hash_fraction(member["id"], qid, aid, "law") < member["law_rate"]
    ):
        objective -= member["law_size"]
        margins = [v + member["law_size"] for v in margins]
    return {
        "objective": objective,
        "margins": tuple(margins),
        "feasible": min(margins) >= 0,
        "sigma": max(local_noise * member.get("sigma_scale", 1), 1e-9),
    }


def _prediction_set(member, questions, bases, problem, coverage, size):
    out = {}
    for i, (qid, question) in enumerate(questions.items()):
        horizon = (i + 1) / len(questions)
        perturbation = size if qid.startswith(("N-", "X-")) else 0.0
        covered = _hash_fraction(member["id"], qid, "coverage") < coverage
        out[qid] = {}
        for aid in question["actions"]:
            pred = _predict(
                member,
                qid,
                aid,
                question,
                base_question=bases[qid],
                horizon=horizon,
                perturbation=perturbation,
            )
            if not covered:
                pred = {**pred, "feasible": False, "margins": (-1.0, -1.0)}
            out[qid][aid] = pred
    return out


def _loss(question, predictions, decision, cost):
    fallback = question["actions"][question["fallback"]]
    if fallback["status"] != "FEASIBLE":
        return None
    shortlist = sorted(
        (
            (pred["objective"], aid)
            for aid, pred in predictions.items()
            if pred["feasible"] and pred["objective"] < fallback["objective"]
        ),
        key=lambda row: (row[0], row[1]),
    )[: decision["k"]]
    if not shortlist:
        return decision["abstention_loss"]
    safe = [
        question["actions"][aid]["objective"]
        for _, aid in shortlist
        if question["actions"][aid]["status"] == "FEASIBLE"
        and question["actions"][aid]["objective"] < fallback["objective"]
    ]
    gain = (
        max(0.0, fallback["objective"] - min(safe)) / decision["unit"] if safe else 0.0
    )
    unsafe = sum(
        question["actions"][aid]["status"] != "FEASIBLE" for _, aid in shortlist
    )
    return cost * len(shortlist) - gain + decision["unsafe_loss"] * unsafe


def _oracle_loss(question, decision, cost):
    fallback = question["actions"][question["fallback"]]
    best = question["exact_best_objective"]
    if fallback["status"] != "FEASIBLE" or best is None:
        return None
    return min(
        decision["abstention_loss"],
        cost - max(0.0, fallback["objective"] - best) / decision["unit"],
    )


def build(config):
    """Construct disjoint score/value tasks and member-specific neighbour scores."""
    validate_config(config)
    problem = config["problem"]
    hood = config["neighbourhood"]
    n = config["questions_per_side"]
    value_context_shift = 0.19 if problem["shift"] == "shifted" else 0.0
    score = {f"S-{i}": _question(f"S-{i}", 0.06 + i * 0.075, problem) for i in range(n)}
    target = {
        f"V-{i}": _question(f"V-{i}", 0.085 + i * 0.075 + value_context_shift, problem)
        for i in range(n)
    }
    neighbour_score = {}
    neighbour_value = {}
    for direction in hood["directions"]:
        neighbour_score[direction] = {
            f"N-S-{direction}-{i}": _question(
                f"N-S-{direction}-{i}",
                0.06 + i * 0.075,
                problem,
                direction=direction,
                size=hood["size"],
            )
            for i in range(n)
        }
        neighbour_value.update(
            {
                f"N-V-{direction}-{i}": _question(
                    f"N-V-{direction}-{i}",
                    0.085 + i * 0.075 + value_context_shift,
                    problem,
                    direction=direction,
                    size=hood["size"],
                )
                for i in range(n)
            }
        )
    extrapolated = {
        f"X-{i}": _question(
            f"X-{i}",
            0.085 + i * 0.075 + value_context_shift + hood["extrapolation_distance"],
            problem,
        )
        for i in range(n)
    }
    value = target | neighbour_value | extrapolated
    strata = {
        **{qid: "in_range" for qid in target},
        **{qid: "shifted" for qid in neighbour_value},
        **{qid: "extrapolated" for qid in extrapolated},
    }
    score_bases = {qid: score[f"S-{i}"] for i, qid in enumerate(score)}
    value_bases = {
        **{qid: target[qid] for qid in target},
        **{qid: target[f"V-{int(qid.rsplit('-', 1)[1])}"] for qid in neighbour_value},
        **{qid: target[f"V-{i}"] for i, qid in enumerate(extrapolated)},
    }
    members = []
    for spec in config["population"]:
        sp = _prediction_set(
            spec, score, score_bases, problem, config["coverage"], hood["size"]
        )
        vp = _prediction_set(
            spec,
            value,
            value_bases,
            problem,
            config["coverage"],
            max(hood["size"], hood["extrapolation_distance"]),
        )
        neighbours = []
        for direction, questions in neighbour_score.items():
            bases = {qid: score[f"S-{int(qid.rsplit('-', 1)[1])}"] for qid in questions}
            neighbours.append(
                {
                    "id": direction,
                    "references": questions,
                    "predictions": _prediction_set(
                        spec,
                        questions,
                        bases,
                        problem,
                        config["coverage"],
                        hood["size"],
                    ),
                }
            )
        physics = {
            "law_violations": spec["law_rate"] * spec["law_size"],
            "rollout_drift": spec["rollout_drift"],
            "robustness": spec["robustness"],
            "extrapolation": spec["extrapolation"],
            "b15": spec["law_rate"] * spec["law_size"],
            "b9": spec["robustness"],
            "b16": spec["rollout_drift"],
        }
        members.append(
            {
                "id": spec["id"],
                "recipe": spec["id"],
                "kind": spec["kind"],
                "score_predictions": sp,
                "score_row": synthetic._row(score, sp, problem),
                "score_metadata": {"physics": physics, "neighbours": neighbours},
                "value_losses": {
                    qid: (
                        _loss(
                            q,
                            vp[qid],
                            config["decision"],
                            problem["verification_cost_ASSUMPTION"],
                        )
                        if config.get("value_definition", "v2_shortlist")
                        == "v2_shortlist"
                        else synthetic._decision_loss(
                            q,
                            vp[qid],
                            problem["verification_cost_ASSUMPTION"],
                        )
                    )
                    for qid, q in value.items()
                },
            }
        )
    panel = {
        "schema": synthetic.SCHEMA,
        "scope": "SYNTHETIC_DEVELOPMENT",
        "assumption": {
            "physics_config_sha256": canonical_sha(config),
            "job": "OPT-15b-analytic-toy",
        },
        "score_questions": score,
        "value_questions": value,
        "value_strata": strata,
        "oracle_kind": "EXACT_ENUMERATED_OFFERED_ACTIONS",
        "exact_oracle_losses": {
            qid: (
                _oracle_loss(
                    q, config["decision"], problem["verification_cost_ASSUMPTION"]
                )
                if config.get("value_definition", "v2_shortlist") == "v2_shortlist"
                else _oracle_loss(
                    q,
                    {**config["decision"], "abstention_loss": 0.0, "unit": 1.0},
                    problem["verification_cost_ASSUMPTION"],
                )
            )
            for qid, q in value.items()
        },
        "members": members,
    }
    validate_panel(panel)
    return panel


def value_view(panel, stratum, neighbour_weight=0.0):
    """Leave the scoring half untouched; select only a true-value estimand."""
    view = copy.copy(panel)
    if stratum == "robust_worst_case":
        target = [
            qid for qid, kind in panel["value_strata"].items() if kind == "in_range"
        ]
        view["value_questions"] = {qid: panel["value_questions"][qid] for qid in target}
        view["members"] = []
        for member in panel["members"]:
            losses = {}
            for qid in target:
                suffix = qid.split("-")[-1]
                related = [
                    member["value_losses"][name]
                    for name in panel["value_questions"]
                    if name == qid or name.endswith("-" + suffix)
                ]
                losses[qid] = (
                    max(related)
                    if related and all(loss is not None for loss in related)
                    else None
                )
            view["members"].append({**member, "value_losses": losses})
        # Per-task minima cannot be combined into the min-max oracle for one
        # robust decision. Keep that reference explicitly unresolved.
        view["exact_oracle_losses"] = {qid: None for qid in target}
    elif stratum == "neighbourhood_blend":
        if not _finite(neighbour_weight, high=1):
            raise LabRefused("physics_neighbourhood_weight")
        target = [
            qid for qid, kind in panel["value_strata"].items() if kind == "in_range"
        ]
        shifted = [
            qid for qid, kind in panel["value_strata"].items() if kind == "shifted"
        ]
        view["value_questions"] = {qid: panel["value_questions"][qid] for qid in target}
        view["members"] = []
        for member in panel["members"]:
            losses = {}
            for qid in target:
                suffix = qid.split("-")[-1]
                neighbours = [
                    member["value_losses"][nq]
                    for nq in shifted
                    if nq.endswith("-" + suffix)
                ]
                own = member["value_losses"][qid]
                losses[qid] = (
                    (1 - neighbour_weight) * own
                    + neighbour_weight * statistics.fmean(neighbours)
                    if own is not None
                    and neighbours
                    and all(x is not None for x in neighbours)
                    else None
                )
            view["members"].append({**member, "value_losses": losses})
        view["exact_oracle_losses"] = {
            qid: (
                (1 - neighbour_weight) * panel["exact_oracle_losses"][qid]
                + neighbour_weight
                * statistics.fmean(
                    panel["exact_oracle_losses"][nq]
                    for nq in shifted
                    if nq.endswith("-" + qid.split("-")[-1])
                )
                if panel["exact_oracle_losses"][qid] is not None
                and all(
                    panel["exact_oracle_losses"][nq] is not None
                    for nq in shifted
                    if nq.endswith("-" + qid.split("-")[-1])
                )
                else None
            )
            for qid in target
        }
    else:
        selected = [
            qid for qid, kind in panel["value_strata"].items() if kind == stratum
        ]
        if not selected:
            raise LabRefused("physics_value_stratum")
        view["value_questions"] = {
            qid: panel["value_questions"][qid] for qid in selected
        }
        view["members"] = [
            {**m, "value_losses": {qid: m["value_losses"][qid] for qid in selected}}
            for m in panel["members"]
        ]
        view["exact_oracle_losses"] = {
            qid: panel["exact_oracle_losses"][qid] for qid in selected
        }
    view["assumption"] = {**panel["assumption"], "value_stratum": stratum}
    return view


def evaluate(config, specs, digest, *, component_spec=None):
    """Run every candidate under every physics switch on the same toy panel."""
    panel = build(config)
    views = {
        stratum: value_view(panel, stratum, config["neighbourhood"]["value_weight"])
        for stratum in ("in_range", "shifted", "extrapolated", "neighbourhood_blend")
    }
    results = []
    for candidate_id, spec in specs.items():
        rule = candidates.rule_from_spec(
            candidate_id,
            spec,
            path_digest=digest,
            panel=panel,
            component_spec=component_spec,
        )
        baseline_admissibility = None
        for switch_index, switch in enumerate(config["physics_sweep"]):
            for view in views.values():
                view.setdefault("score_metadata", {})["knobs"] = {
                    "physics": switch,
                    "neighbourhood_weight": config["neighbourhood"]["score_weight"],
                }
            outcomes = {
                stratum: analyze(view, rule, bootstrap=config["bootstrap"])
                for stratum, view in views.items()
            }
            base = outcomes["in_range"]
            blend = outcomes["neighbourhood_blend"]
            good = _good_members(views["neighbourhood_blend"], config["good_fraction"])
            tiers = base.get("physics_tiers", {})
            admissible = base.get("admissibility", {})
            if switch["mode"] == "OFF":
                baseline_admissibility = admissible
            eligible = {m["id"] for m in panel["members"] if m["kind"] == "MODEL"}
            excluded = [
                m
                for m in good
                if baseline_admissibility.get(m, False)
                and (tiers.get(m, 0) > 0 or not admissible.get(m, False))
            ]
            results.append(
                {
                    "candidate": candidate_id,
                    "switch_index": switch_index,
                    "switch": switch,
                    "status": blend["status"],
                    "tau": {k: v.get("tau") for k, v in outcomes.items()},
                    "tau_ci95": {k: v.get("tau_ci95") for k, v in outcomes.items()},
                    "top1_regret": {
                        k: v.get("top1_regret") for k, v in outcomes.items()
                    },
                    "gamer_top_half": {
                        k: bool(v.get("adversarial_in_top_half"))
                        for k, v in outcomes.items()
                    },
                    "good_wrongly_excluded": len(excluded),
                    "good_members": len(good),
                    "eligible_primary": sum(
                        admissible.get(m, False) and tiers.get(m, 0) == 0
                        for m in eligible
                    ),
                    "reasons": {
                        k: v.get("reason")
                        for k, v in outcomes.items()
                        if v.get("reason")
                    },
                }
            )
    measured = sum(row["status"] == "MEASURED_DEVELOPMENT" for row in results)
    return {
        "status": "DEVELOPMENT_DIAGNOSTIC" if measured else "INSUFFICIENT_EVIDENCE",
        "assumption_sha256": canonical_sha(config),
        "candidates_sha256": digest,
        "members": len(panel["members"]),
        "measured_rows": measured,
        "rows": results,
        "physics_verdict": _verdict(results),
    }


def _good_members(view, fraction):
    models = [m for m in view["members"] if m["kind"] == "MODEL"]
    quality = []
    for member in models:
        losses = list(member["value_losses"].values())
        if all(x is not None for x in losses):
            quality.append((statistics.fmean(losses), member["id"]))
    quality.sort()
    return {name for _, name in quality[: max(1, math.ceil(len(quality) * fraction))]}


def _verdict(rows):
    """Descriptive switch effects; never a recommendation of owner values."""
    by_rule = {}
    for row in rows:
        by_rule.setdefault(row["candidate"], []).append(row)
    effects = []
    for name, outcomes in by_rule.items():
        off = next((r for r in outcomes if r["switch"]["mode"] == "OFF"), None)
        if off is None:
            continue
        for row in outcomes:
            mode = row["switch"]["mode"]
            if mode == "OFF":
                continue
            a, b = off["tau"]["neighbourhood_blend"], row["tau"]["neighbourhood_blend"]
            interpretation = (
                "unresolved_point_alignment"
                if a is None or b is None
                else (
                    "helps_point_alignment"
                    if b > a
                    else (
                        "hurts_point_alignment"
                        if b < a
                        else "unchanged_point_alignment"
                    )
                )
            )
            effects.append(
                {
                    "candidate": name,
                    "mode": mode,
                    "switch": row["switch"],
                    "delta_tau_point": (
                        b - a if a is not None and b is not None else None
                    ),
                    "false_exclusions": row["good_wrongly_excluded"],
                    "gamer_resisted": off["gamer_top_half"]["extrapolated"]
                    and not row["gamer_top_half"]["extrapolated"],
                    "interpretation": interpretation,
                }
            )
    return {"status": "DESCRIPTIVE_ONLY", "effects": effects}


def sensitivity(config, specs, digest):
    """One-factor-at-a-time ranking changes over caller-registered settings."""
    base = evaluate(config, specs, digest)
    variants = config.get("sensitivity", {})
    if not isinstance(variants, dict):
        raise LabRefused("physics_sensitivity_malformed")
    base_rank = _rule_ranks(base["rows"])
    table = []
    for path, values in variants.items():
        if not isinstance(values, list) or not values:
            raise LabRefused("physics_sensitivity_values")
        for value in values:
            variant = copy.deepcopy(config)
            node = variant
            keys = path.split(".")
            for key in keys[:-1]:
                if key not in node or not isinstance(node[key], dict):
                    raise LabRefused("physics_sensitivity_path")
                node = node[key]
            if keys[-1] not in node:
                raise LabRefused("physics_sensitivity_path")
            node[keys[-1]] = value
            row = evaluate(variant, specs, digest)
            rank = _rule_ranks(row["rows"])
            table.append(
                {
                    "lever": path,
                    "setting": value,
                    "ranked_rules": rank,
                    "changed_positions": {
                        index: {
                            name: [before.index(name) + 1, rank[index].index(name) + 1]
                            for name in before
                            if name in rank[index]
                            and before.index(name) != rank[index].index(name)
                        }
                        for index, before in base_rank.items()
                        if index in rank
                    },
                }
            )
    base["sensitivity"] = {"baseline_ranked_rules": base_rank, "table": table}
    return base


def _rule_ranks(rows):
    grouped = {}
    for row in rows:
        tau = row["tau"]["neighbourhood_blend"]
        grouped.setdefault(str(row["switch_index"]), {})
        if tau is not None:
            grouped[str(row["switch_index"])][row["candidate"]] = tau
    return {
        index: sorted(values, key=lambda name: (-values[name], name))
        for index, values in grouped.items()
    }
