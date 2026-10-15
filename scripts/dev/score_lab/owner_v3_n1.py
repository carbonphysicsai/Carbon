"""Approved DEVELOPMENT diagnostic binding, separate from legacy score rules.

No fitting, solver, dispatch, holdout, official admission or rule adoption.
The pinned native function supplies the authoritative score. Original buyer
questions remain the paired units; grouped errors expose its full reduction.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

from carbon.design_search import tasks

from . import candidates, owner_dev_v1, owner_v3, owner_v3_panel_export

DIRECTORY = (
    Path(__file__).resolve().parents[3]
    / "Business/research/score-lab-campaign-01/n1-diagnostic-v1"
)
REGISTRATION_SHA256 = "40f2bb984dc1a9921c05a2c7b0d75fdaab587b0ddec7f5fbd4c4a4c731c836a1"
N1 = "N1-DECISION-RELEVANCE-ERROR"
CONTROL = "SCALAR-ACCURACY-CONTROL-v1"
SCHEMA = "carbon.scorelab.battery-v3.n1-diagnostic.v1"


def _finite(value):
    try:
        return type(value) in (float, int) and math.isfinite(value)
    except OverflowError:
        return False


def registration(*, expected_sha256):
    """Read only the committed binding and exact approved provenance bytes."""
    raw = (DIRECTORY / "registration.json").read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != REGISTRATION_SHA256 or expected_sha256 != actual:
        raise tasks.TaskError("N1 diagnostic registration digest differs")
    registered = json.loads(raw)
    for name, key in (
        ("APPROVED_PROPOSAL.md", "proposal_sha256"),
        ("OWNER_APPROVAL.json", "approval_sha256"),
        ("TRAIN_SCALE_RECEIPT.json", "train_scale_receipt_sha256"),
    ):
        if hashlib.sha256((DIRECTORY / name).read_bytes()).hexdigest() != registered[key]:
            raise tasks.TaskError("N1 approved provenance bytes differ")
    return registered


def _source(registered):
    rules, source_digest = candidates.load()
    if source_digest != registered["native_source_sha256"]:
        raise tasks.TaskError("N1 native source digest differs")
    native = rules[N1]["rule"]
    # Reuse helpers from the SAME checked module, not a second implementation
    # of its error definition, optimum or relevance weights.
    return native, native.__globals__


def _rows(rows, bindings, *, role, population, scope):
    """Authenticate producer data before deriving the model-independent mask."""
    if scope not in ("PUBLIC_DEVELOPMENT", "SYNTHETIC_FIXTURE"):
        raise tasks.TaskError("N1 is public-development/fixture diagnostic only")
    if population not in ("P", "Q") or (scope == "PUBLIC_DEVELOPMENT" and population != "P"):
        raise tasks.TaskError("public Q support is not registered for this binding")
    if type(rows) is not list or not rows or type(bindings) is not dict:
        raise tasks.TaskError("complete offered questions and independent bindings required")
    ids, prepared = set(), []
    # Check roles before touching ANY reference values, including VALUE rows.
    for row in rows:
        if type(row) is not dict or set(row) != {"draw", "evidence"}:
            raise tasks.TaskError("exact draw and producer evidence fields required")
        draw = row["draw"]
        if (
            draw.get("role") != role
            or draw.get("population") != population
            or draw.get("outer_weight") != 1
        ):
            raise tasks.TaskError("one population and one role with unit outer weights required")
        registered = draw["task"]
        owner_v3._validate(registered)
        qid = registered["task_digest"]
        if qid in ids or draw.get("bank_cluster") != registered["indices"][0]["task"]["identity"]["reference_bank"]:
            raise tasks.TaskError("duplicate question or different bank identity")
        ids.add(qid)
    if set(bindings) != ids:
        raise tasks.TaskError("independent bindings must cover every offered question")
    for row in sorted(rows, key=lambda r: r["draw"]["task"]["task_digest"]):
        draw, evidence = row["draw"], row["evidence"]
        registered = draw["task"]
        qid = registered["task_digest"]
        if type(evidence) is not owner_v3_panel_export.ValidatedEvidence:
            raise tasks.TaskError("constructed producer evidence required")
        refs, intervals = evidence.references, evidence.enclosures
        receipt = owner_v3_panel_export.validate_for(evidence, registered, refs, intervals, scope=scope)
        binding = bindings[qid]
        if (
            type(binding) is not dict
            or set(binding) != {"plan_digest", "source_pins_digest", "manifest_digest"}
            or any(binding[k] != receipt[k] for k in binding)
        ):
            raise tasks.TaskError("Root prebound producer identity differs")
        for index in registered["indices"]:
            sub = index["task"]
            if len(sub["candidates"]) != 12 or len(sub["conditions"]) != 1:
                raise tasks.TaskError("all twelve actions and one condition per band required")
            units = {limit["quantity"]: limit["unit"] for limit in sub["limits"]}
            units[sub["objective"]["quantity"]] = sub["objective"]["unit"]
            if units != {"minutes": "min", "charging_t_max_c": "C", "plating_min_v": "V", "v_max_v": "V", "q30_over_q1": "1"}:
                raise tasks.TaskError("exact five observable units required")
        prepared.append({
            "draw": draw, "references": refs, "intervals": intervals,
            "evidence": evidence, "binding": binding,
            "producer_receipt_digest": receipt["receipt_digest"],
            "mask": owner_v3.reference_mask(registered, refs, intervals),
        })
    return prepared


def _prediction_issue(prepared, predictions, quantities):
    if type(predictions) is not dict or set(predictions) != {p["draw"]["task"]["task_digest"] for p in prepared}:
        return "PREDICTION_QUESTION_COVERAGE"
    for row in prepared:
        task = row["draw"]["task"]
        panels = predictions[task["task_digest"]]
        if type(panels) is not list or len(panels) != 5:
            return "PREDICTION_INDEX_COVERAGE"
        for index, panel in zip(task["indices"], panels):
            if type(panel) is not dict or set(panel) != {"index_value", "values"} or panel["index_value"] != index["index_value"]:
                return "PREDICTION_INDEX_COVERAGE"
            sub = index["task"]
            expected = {(a, c["id"]) for a in sub["candidates"] for c in sub["conditions"]}
            values = panel["values"]
            if type(values) is not dict or set(values) != expected:
                return "PREDICTION_ACTION_COVERAGE"
            if any(type(v) is not dict or set(v) != quantities or not all(_finite(x) for x in v.values()) for v in values.values()):
                return "INVALID_OR_NONFINITE_PREDICTION"
    return None


def _point(values, subtask):
    return {
        "objective": values["minutes"],
        "margins": {
            limit["quantity"]: (
                limit["value"] - values[limit["quantity"]]
                if limit["op"] == "<=" else values[limit["quantity"]] - limit["value"]
            )
            for limit in subtask["limits"]
        },
    }


def _native_inputs(prepared, predictions, registered):
    refs, preds, questions, parent = {}, {}, {}, {}
    for row in prepared:
        task = row["draw"]["task"]
        qid = task["task_digest"]
        if not row["mask"]["included"]:
            continue
        for index, panel, prediction, settled in zip(task["indices"], row["references"], predictions[qid], row["mask"]["per_index"]):
            sub = index["task"]
            bid = f"{qid}:T{index['index_value']}"
            parent[bid] = qid
            refs[bid], preds[bid] = {}, {}
            verdicts = {v["candidate"]: v["feasible"] for v in settled["verdicts"]}
            for aid in sub["candidates"]:
                key = (aid, sub["conditions"][0]["id"])
                refs[bid][aid] = {**_point(panel["values"][key], sub), "status": "FEASIBLE" if verdicts[aid] else "INFEASIBLE"}
                preds[bid][aid] = _point(prediction["values"][key], sub)
            questions[bid] = {"actions": list(sub["candidates"])}
    scales = {q: max(v["population_sd"] + v["epsilon"], v["floor"]) for q, v in registered["scales"].items()}
    scales["objective"] = scales.pop("minutes")
    metadata = {
        "sense": "min", "questions": questions, "scale": scales,
        "near_band": registered["near_band"], "physics": {}, "neighbours": [],
        "knobs": {"optimum_band": registered["optimum_band"], "physics": {"mode": "OFF"}, "neighbourhood_weight": 0},
    }
    return preds, refs, metadata, parent


def _reduce(predictions, references, metadata, parent, native, namespace):
    """Expose full-source weights using its helpers, retaining native authority."""
    grouped = {qid: [] for qid in parent.values()}
    errors = {qid: [] for qid in grouped}
    weights, flat_errors = [], []
    for bid, aid, prediction, ref in namespace["_cases"](predictions, references):
        if not all(_finite(v) for p in (prediction, ref) for v in (p["objective"], *p["margins"].values())):
            raise ArithmeticError("NONFINITE_DERIVED_MARGIN")
        error = namespace["_case_error"](prediction, ref, metadata["scale"])
        boundary = max(math.exp(-abs(m) / metadata["scale"][q] / metadata["near_band"]) for q, m in ref["margins"].items())
        best = namespace["_best_feasible"](references, bid, metadata)
        optimum = 0.0
        if best is not None and ref["status"] == "FEASIBLE":
            gap = abs(ref["objective"] - best[1]) / metadata["scale"]["objective"]
            if not _finite(gap):
                raise ArithmeticError("NONFINITE_OPTIMUM_GAP")
            optimum = math.exp(-gap / metadata["knobs"]["optimum_band"])
        weight = max(boundary, optimum)
        if not all(_finite(v) and v >= 0 for v in (error, weight, weight * error)):
            raise ArithmeticError("NONFINITE_DERIVED_ERROR_OR_WEIGHT")
        weights.append(weight)
        flat_errors.append(error)
        grouped[parent[bid]].append(weight * error)
        errors[parent[bid]].append(error)
    total_weight = sum(weights)
    if not grouped or not _finite(total_weight) or total_weight <= 0:
        raise ArithmeticError("EMPTY_OR_ZERO_NONFINITE_WEIGHT")
    count = len(grouped)
    contributions = {q: count / total_weight * sum(v) for q, v in grouped.items()}
    control = {q: sum(v) / len(v) for q, v in errors.items()}
    out = native(predictions, references, metadata)
    native_error = out["detail"]["weighted_error"]
    grouped_error = sum(contributions.values()) / count
    control_error = sum(flat_errors) / len(weights)
    scores = {N1: out["score"], CONTROL: 1 / (1 + control_error)}
    if not all(_finite(v) for v in (native_error, grouped_error, control_error, *contributions.values(), *control.values(), *scores.values())):
        raise ArithmeticError("NONFINITE_REDUCTION")
    # An operation-count roundoff check, NOT a scientific error tolerance.
    arithmetic_bound = 64 * len(weights) * math.ulp(max(1.0, abs(native_error), abs(grouped_error)))
    residual = abs(native_error - grouped_error)
    if residual > arithmetic_bound:
        raise ArithmeticError("GROUPED_NATIVE_ARITHMETIC_MISMATCH")
    return {
        "scores": scores, "case_contributions": {N1: contributions, CONTROL: control},
        "native_weighted_error": native_error, "reference_weight_sum": total_weight,
        "relevance_weight_range": [min(weights), max(weights)],
        "all_relevance_weights_one": all(w == 1 for w in weights),
        "arithmetic": {"absolute_error_residual": residual, "operation_count_bound": arithmetic_bound, "physical_tolerance": False, "authoritative_score": "full pinned native call"},
    }


def score_leg(rows, predictions, *, producer_bindings, expected_registration_digest, population="P", scope="PUBLIC_DEVELOPMENT"):
    """One member on LEG ONLY; predictions use producer.reference panel shape.

    Independent Root bindings are keyed by task_digest. Rows contain exactly
    {draw, evidence}; evidence must come from the existing producer build().
    Missing predictions withhold the WHOLE member, even on excluded questions.
    """
    registered = registration(expected_sha256=expected_registration_digest)
    native, namespace = _source(registered)
    prepared = _rows(rows, producer_bindings, role="LEG", population=population, scope=scope)
    base = {
        "schema": SCHEMA, "scope": scope, "population": population, "role": "LEG",
        "registration_sha256": expected_registration_digest,
        "native_source_sha256": registered["native_source_sha256"],
        "offered_questions": len(prepared),
        "included_questions": sum(r["mask"]["included"] for r in prepared),
        "excluded_questions": sum(not r["mask"]["included"] for r in prepared),
        "banks": sorted({r["draw"]["bank_cluster"] for r in prepared}),
        "reference_masks": {r["draw"]["task"]["task_digest"]: r["mask"] for r in prepared},
        "producer_receipts": {r["draw"]["task"]["task_digest"]: r["producer_receipt_digest"] for r in prepared},
        "scores": {N1: None, CONTROL: None}, "old_inforce_gates": "UNMEASURED",
        "official_eligible": False, "stage_c_or_d_adoption": False, "qualification": False,
    }
    issue = _prediction_issue(prepared, predictions, set(registered["scales"]))
    if issue:
        return {**base, "status": "CANDIDATE_UNAVAILABLE", "reason": issue}
    if not any(r["mask"]["included"] for r in prepared):
        return {**base, "status": "REFERENCE_UNRESOLVED", "candidate_penalty": False}
    inputs = _native_inputs(prepared, predictions, registered)
    try:
        result = _reduce(*inputs, native, namespace)
    except (ArithmeticError, ValueError) as exc:
        return {**base, "status": "NUMERICAL_UNAVAILABLE", "reason": str(exc)}
    return {**base, **result, "status": "MEASURED_DEVELOPMENT_DIAGNOSTIC"}


def judge_values(rows, commitments, *, producer_bindings, expected_registration_digest, population="P", scope="PUBLIC_DEVELOPMENT"):
    """Reuse the owner-D2 judge for all offered VALUE questions, no scoring."""
    registration(expected_sha256=expected_registration_digest)
    prepared = _rows(rows, producer_bindings, role="VALUE", population=population, scope=scope)
    if set(commitments) != {r["draw"]["task"]["task_digest"] for r in prepared}:
        raise tasks.TaskError("all offered VALUE commitments required")
    outcomes = [owner_v3.judge(
        r["draw"]["task"], commitments[r["draw"]["task"]["task_digest"]],
        r["references"], r["intervals"], scope=scope,
        producer_evidence=r["evidence"], producer_binding=r["binding"],
    ) for r in prepared]
    masks = {r["task_digest"]: r["reference_mask"] for r in outcomes}
    return {
        "scope": scope, "population": population, "role": "VALUE",
        "registration_sha256": expected_registration_digest,
        "banks": sorted({r["draw"]["bank_cluster"] for r in prepared}),
        "summary": owner_v3.model_summary(outcomes, expected_masks=masks),
        "outcomes": outcomes, "reference_masks_digest": tasks.digest(masks),
        "qualification": False,
    }


def alignment(legs, values, *, recipe_of, gamers, bootstrap, seed):
    """Conditional diagnostic tau and LEG-first top-3; never Stage C/D.

    VALUE cannot prefilter LEG selection. Unsafe/missed VALUE withholds the
    selected comparison; tau explicitly names its complete-safe member subset.
    Root supplies the fixed recipe/artifact identities and bootstrap inputs.
    """
    from carbon.battery.value import score_proof
    from carbon.design_search import score_value

    members = sorted(legs)
    if not members or set(values) != set(members) or set(recipe_of) != set(members) or type(bootstrap) is not int or bootstrap < 1:
        raise tasks.TaskError("complete fixed members, recipe identities and bootstrap count required")
    identities = {(r["scope"], r["population"], r["registration_sha256"]) for r in (*legs.values(), *values.values())}
    if (
        any(r.get("role") != "LEG" for r in legs.values())
        or any(r.get("role") != "VALUE" for r in values.values())
        or any(r["registration_sha256"] != REGISTRATION_SHA256 for r in (*legs.values(), *values.values()))
        or len(identities) != 1
        or len({tasks.digest(r["reference_masks"]) for r in legs.values()}) != 1
        or len({r["reference_masks_digest"] for r in values.values()}) != 1
        or len({tuple(r["banks"]) for r in (*legs.values(), *values.values())}) != 1
    ):
        raise tasks.TaskError("one scope/population/registration and common masks required")
    scores = {rule: {m: legs[m]["scores"][rule] for m in members} for rule in (N1, CONTROL)}
    selections = {rule: owner_dev_v1.select_top_three(s, admitted=members, gamers=gamers) for rule, s in scores.items()}
    usable = [m for m in members if all(_finite(scores[r][m]) for r in scores) and values[m]["summary"]["regret_ranking_eligible"]]
    losses = {m: [o["regret_min"] for o in values[m]["outcomes"] if o["reference_mask"]["reference_state"] == "FEASIBLE_EXISTS"] for m in usable}
    means = {m: values[m]["summary"]["mean_regret_min"] for m in usable}
    rules = {}
    for rule in scores:
        selection = selections[rule]
        picked = selection["selected"]
        complete = len(picked) == 3 and all(values[m]["summary"]["regret_ranking_eligible"] for m in picked)
        rules[rule] = {
            "selection": selection,
            "selected_value_outcomes": {m: values[m]["outcomes"] for m in picked},
            "top3_mean_regret_min": statistics.fmean(values[m]["summary"]["mean_regret_min"] for m in picked) if complete else None,
            "top3_status": "MEASURED_CONDITIONAL_DIAGNOSTIC" if complete else "INSUFFICIENT_EVIDENCE",
            "tau": score_proof._tau(scores[rule], means, usable),
            "rho": score_value.spearman_rho([scores[rule][m] for m in usable], [-means[m] for m in usable]) if len(usable) >= 2 else None,
            "bootstrap": score_proof.bootstrap(scores[rule], scores[CONTROL], losses, recipe_of, usable, n=bootstrap, seed=seed) if losses else None,
        }
    return {
        "first_line": "value conditional on reference-adequate frozen bank and FEASIBLE_EXISTS; diagnostic only",
        "scope": next(iter(identities))[0], "population": next(iter(identities))[1],
        "offered_members": members, "recipe_clusters": len(set(recipe_of.values())),
        "conditional_tau_members": usable, "conditional_tau_excluded": [m for m in members if m not in usable],
        "all_member_outcome_summaries": {m: values[m]["summary"] for m in members},
        "rules": rules, "bank_resampling": "bank fixed; recipe x VALUE-question bootstrap, LEG fixed",
        "roundoff_caution": "Native ranks are descriptive; an ulp-scale difference is not a measured physical benefit or adoption evidence",
        "old_inforce_gates": "UNMEASURED", "official_eligible": False,
        "stage_c_or_d_adoption": False, "qualification": False,
    }
