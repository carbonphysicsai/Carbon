"""Digest-bound DEVELOPMENT battery v3 inputs for one confirmed recipe.

Run ``python -m scripts.dev.battery.v3_score_inputs --help``. This module
never calls a truth solver or the retained private-role scoring-set loader.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

from carbon.battery import exam
from carbon.battery.calibration import SHAPES, frozen_calibration
from carbon.battery.challenge import PublicMaterial
from carbon.battery.value import contract as ev
from carbon.battery.value import decision as d
from carbon.battery.value import quiz, ratios
from carbon.battery.value import score_tuning as tuning
from carbon.battery.value import scoring as sc
from carbon.design_search.score_value import kendall_tau_b, spearman_rho

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = "carbon.battery.v3-score-input-panel.v1"
SCOPE = "PUBLIC_SYNTHETIC_DEVELOPMENT"
SETTLEMENT = "carbon.battery.quiz.q3_settle.v8"
REGISTRY = "docs/development/evidence/battery-score-tuning/registry-v4.json"
QUIZ_REGISTRY = "docs/development/evidence/battery-quiz-designs/quiz-registry-v8.json"
CANDIDATE = "G-FEAS/A-Q@0.05"


class Refused(ValueError):
    """A typed refusal, never a candidate score."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _under(path, directory):
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        raise Refused("development_path_required") from None
    return path.resolve()


def _registered_panel(root, path):
    root = Path(root).resolve()
    base = root / "docs/development/evidence/v3-score-inputs"
    path = _under(Path(path), base)
    relative = path.relative_to(root)
    command = ["git", "-c", f"safe.directory={root}", "-C", str(root)]
    tracked = subprocess.run(
        command + ["ls-files", "--error-unmatch", "--", str(relative)],
        capture_output=True,
        check=False,
    )
    dirty = subprocess.run(
        command + ["status", "--porcelain", "--", str(relative)],
        capture_output=True,
        check=True,
    )
    if tracked.returncode or dirty.stdout.strip():
        raise Refused("panel_not_committed_clean")
    return path


def _file(base, entry):
    if set(entry) != {"path", "sha256"} or type(entry["path"]) is not str:
        raise Refused("file_identity_invalid")
    path = _under(base / entry["path"], base)
    body = path.read_bytes()
    if entry["sha256"] != "sha256:" + _sha(body):
        raise Refused("file_digest_mismatch")
    return path, body


def _records(body, path):
    if path.suffix == ".gz":
        body = gzip.decompress(body)
    result = {}
    for line in body.splitlines():
        if line.strip():
            record = json.loads(line)
            case_id = record.get("case_id")
            if not isinstance(case_id, str) or case_id in result:
                raise Refused("reference_case_ids_invalid")
            result[case_id] = record
    return result


def load_panel(root, panel_path):
    """Read a committed registration and only its digest-pinned dev files."""
    root = Path(root).resolve()
    path = _registered_panel(root, panel_path)
    body = path.read_bytes()
    panel = json.loads(body)
    if (
        panel.get("schema") != SCHEMA
        or panel.get("scope") != SCOPE
        or panel.get("settlement_rule") != SETTLEMENT
        or set(panel)
        != {
            "schema",
            "scope",
            "job",
            "contract",
            "settlement_rule",
            "screening",
            "q3",
            "rule_registry",
            "quiz_registry",
        }
        or panel["job"] != "battery-q3-v8"
    ):
        raise Refused("panel_registration_invalid")
    base = path.parent
    contract_path, contract_body = _file(base, panel["contract"])
    contract, _canonical_contract_digest = ev.load(contract_path)
    registry_path = root / REGISTRY
    if panel["rule_registry"] != "sha256:" + _sha(registry_path.read_bytes()):
        raise Refused("rule_registry_mismatch")
    if panel["quiz_registry"] != "sha256:" + _sha((root / QUIZ_REGISTRY).read_bytes()):
        raise Refused("quiz_registry_mismatch")
    candidates, _identity = tuning.load_registry(registry_path, repository=root)
    candidate = candidates[CANDIDATE]
    if candidate.weights != {"a": 0.5, "q": 0.5} or candidate.gate != {
        "measure": "feasibility",
        "cutoff": 0.05,
    }:
        raise Refused("rule_contract_mismatch")
    screening = panel["screening"]
    q3 = panel["q3"]
    if (
        set(screening) != {"case_ids", "batch_ids", "references"}
        or not isinstance(screening["case_ids"], list)
        or not screening["case_ids"]
        or len(set(screening["case_ids"])) != len(screening["case_ids"])
        or not isinstance(screening["batch_ids"], list)
        or not screening["batch_ids"]
        or len(set(screening["batch_ids"])) != len(screening["batch_ids"])
        or set(q3) != {"scenarios", "standard", "refined"}
        or not isinstance(q3["scenarios"], list)
        or not q3["scenarios"]
    ):
        raise Refused("panel_cases_invalid")
    screening_path, screening_body = _file(base, screening["references"])
    standard_path, standard_body = _file(base, q3["standard"])
    refined_path, refined_body = _file(base, q3["refined"])
    screening_refs = _records(screening_body, screening_path)
    standard = _records(standard_body, standard_path)
    refined = _records(refined_body, refined_path)
    scenarios = []
    seen = set()
    expected_refine = set()
    expected_standard = set()
    batch_counts = {b: 0 for b in screening["batch_ids"]}
    for row in q3["scenarios"]:
        if set(row) != {"id", "batch_id", "t_amb_c", "soc0"} or row["id"] in seen:
            raise Refused("q3_scenarios_invalid")
        try:
            in_envelope = all(
                math.isfinite(float(row[key]))
                and contract["operating_conditions"]["envelope"][key][0]
                <= float(row[key])
                <= contract["operating_conditions"]["envelope"][key][1]
                for key in ("t_amb_c", "soc0")
            )
        except (TypeError, ValueError, KeyError):
            in_envelope = False
        if not in_envelope:
            raise Refused("q3_scenario_outside_envelope")
        if row["batch_id"] not in batch_counts:
            raise Refused("q3_screening_batch_mismatch")
        batch_counts[row["batch_id"]] += 1
        seen.add(row["id"])
        scenario = quiz.q3_scenario(row["id"], (row["t_amb_c"], row["soc0"]))
        grid = quiz.q3_grid(contract, scenario)
        expected_standard.update(job["case_id"] for job in grid)
        if any(job["case_id"] not in standard for job in grid):
            raise Refused("q3_standard_incomplete")
        for job in grid:
            record = standard[job["case_id"]]
            if record.get("inputs") != {
                k: job[k] for k in ("c1", "c2", "t_amb_c", "soc0")
            }:
                raise Refused("q3_reference_inputs_mismatch")
        expected_refine.update(
            job["case_id"]
            for job in quiz.q3_refine_points(contract, scenario, standard)
        )
        scenarios.append(scenario)
    if any(n != quiz.Q3_K for n in batch_counts.values()):
        raise Refused("q3_batch_size_mismatch")
    if set(standard) != expected_standard:
        raise Refused("q3_standard_outside_registration")
    if set(screening["case_ids"]) & expected_standard:
        raise Refused("screening_q3_case_id_collision")
    if set(refined) != expected_refine:
        raise Refused("q3_refinement_incomplete")
    for case_id, record in refined.items():
        if (
            record.get("refined") is not True
            or record.get("status")
            not in (
                "OK",
                "FAILED_INFRA",
            )
            or record.get("inputs") != standard[case_id].get("inputs")
        ):
            raise Refused("q3_refinement_invalid")
    if any(case_id not in screening_refs for case_id in screening["case_ids"]):
        raise Refused("screening_references_incomplete")
    settled = quiz.q3_settle(standard, refined.values())
    identity = {
        "panel_sha256": "sha256:" + _sha(body),
        "contract_sha256": "sha256:" + _sha(contract_body),
        "registry_sha256": panel["rule_registry"],
        "quiz_registry_sha256": panel["quiz_registry"],
        "screening_batches": list(screening["batch_ids"]),
        "screening_sha256": screening["references"]["sha256"],
        "q3_standard_sha256": q3["standard"]["sha256"],
        "q3_refined_sha256": q3["refined"]["sha256"],
        "settlement_rule": SETTLEMENT,
        "scope": SCOPE,
        "job": panel["job"],
    }
    return (
        contract,
        candidate,
        screening["case_ids"],
        screening_refs,
        scenarios,
        settled,
        identity,
    )


def _q3_outcomes(contract, scenarios, settled, predictions):
    outcomes = []
    for scenario in scenarios:
        candidates = quiz.q3_candidates()
        grid = quiz.q3_grid(contract, scenario)
        refs = {j["case_id"]: settled[j["case_id"]] for j in grid}
        reference = d.assess_reference(
            contract,
            scenario,
            candidates,
            {
                (c["id"], 0): refs[j["case_id"]]
                for c, j in zip(candidates, grid, strict=True)
            },
        )
        best = d.best_in_set(candidates, reference)
        if best is None:
            raise Refused("q3_reference_no_feasible_design")
        best_time = reference[best]["objective"]
        if any(
            r["status"] == d.UNAVAILABLE
            or (r["status"] == d.UNRESOLVED and r["objective"] <= best_time)
            for r in reference.values()
        ):
            raise Refused("q3_reference_could_change_best")
        outcome = quiz.q3_judge(contract, scenario, predictions, refs)
        if outcome["decision_loss"] is None:
            raise Refused("q3_selected_reference_unresolved")
        outcomes.append(outcome)
    return outcomes


def evaluate_member(
    root,
    contract,
    candidate,
    case_ids,
    screening_refs,
    scenarios,
    settled,
    predictions,
    identity,
    recipe,
):
    """Pure scoring over already committed predictions and pinned references."""
    required = set(case_ids)
    for scenario in scenarios:
        required.update(job["case_id"] for job in quiz.q3_grid(contract, scenario))
    result = {
        "schema": "carbon.battery.v3-score-inputs.v1",
        "identity": identity,
        "recipe": recipe,
        "required_predictions": len(required),
        "status": None,
        "a": None,
        "q": None,
        "g_feas": None,
        "q3_regret": None,
        "raw_score": None,
        "eligible": None,
    }
    if any(
        screening_refs[c].get("status") != "OK"
        or not exam._finite_shape(screening_refs[c].get("outputs"), SHAPES)
        for c in case_ids
    ):
        return {
            **result,
            "status": "FAILED_INFRA",
            "cause": "screening_reference_unavailable",
        }
    if any(
        c not in settled
        or settled[c].get("status") != "OK"
        or not exam._finite_shape(settled[c].get("outputs"), SHAPES)
        for c in required - set(case_ids)
    ):
        return {**result, "status": "FAILED_INFRA", "cause": "q3_reference_unavailable"}
    if any(
        c not in predictions
        or not isinstance(predictions[c], dict)
        or not exam._finite_shape(predictions[c], SHAPES)
        for c in required
    ):
        return {
            **result,
            "status": "INELIGIBLE",
            "cause": "candidate_prediction_invalid",
            "eligible": False,
        }
    try:
        outcomes = _q3_outcomes(contract, scenarios, settled, predictions)
    except Refused as failure:
        return {**result, "status": "FAILED_INFRA", "cause": failure.code}
    except (TypeError, ValueError, KeyError, IndexError, ZeroDivisionError):
        return {
            **result,
            "status": "INELIGIBLE",
            "cause": "candidate_prediction_invalid",
            "eligible": False,
        }
    regret = quiz.q3_measures(outcomes, contract)["regret"]
    if regret is None:
        return {**result, "status": "FAILED_INFRA", "cause": "q3_regret_unmeasured"}
    material = PublicMaterial.load(root)
    ocv = {
        c: float(
            np.interp(
                screening_refs[c]["inputs"]["soc0"], material.ocv_soc, material.ocv_v
            )
        )
        for c in case_ids
    }
    tol, scales = frozen_calibration(root)
    store = exam.CaseStore(screening_refs, ocv, tol, scales, SHAPES, {})
    try:
        component = sc.components(predictions, case_ids, store, contract)
    except (TypeError, ValueError, KeyError, IndexError, ZeroDivisionError):
        return {
            **result,
            "status": "FAILED_INFRA",
            "cause": "screening_evaluation_unavailable",
        }
    a, _r, _g = ratios.legs(component)
    g_feas = tuning.false_feasible_rate(contract, predictions, case_ids, screening_refs)
    if g_feas is None:
        return {
            **result,
            "status": "FAILED_INFRA",
            "cause": "g_feas_denominator_empty",
            "a": a,
            "q": 1 / (1 + regret),
            "q3_regret": regret,
        }
    row = {
        "eligible": component["eligible"],
        "E": component["E"],
        "legs": {"a": a, "q": 1 / (1 + regret)},
        "gates": {"feasibility": g_feas},
    }
    raw = tuning.score_member(candidate, row)
    verdict = tuning.gate_verdict(candidate, row)
    eligible = bool(component["eligible"]) and verdict == "PASS" and raw is not None
    return {
        **result,
        "status": "SCORED" if eligible else "INELIGIBLE",
        "cause": None if eligible else "screening_or_g_feas_gate",
        "eligible": eligible,
        "a": a,
        "q": row["legs"]["q"],
        "g_feas": g_feas,
        "q3_regret": regret,
        "raw_score": raw,
        "gate_verdict": verdict,
        "q3_scenarios": len(outcomes),
    }


def load_confirmed_member(root, member_path):
    """Bind the confirmation receipt to a compiled strategy and seed."""
    from carbon.battery.compile import compile_recipe

    root = Path(root).resolve()
    member_path = _under(Path(member_path), root / "docs/development/evidence")
    member_body = member_path.read_bytes()
    member = json.loads(member_body)
    if (
        member.get("schema") != "carbon.battery.confirmed-recipe-input.v1"
        or member.get("status") != "CONFIRMED"
        or set(member)
        != {
            "schema",
            "status",
            "member",
            "strategy",
            "seed",
            "recipe_digest",
            "confirmation",
        }
        or not isinstance(member["seed"], int)
    ):
        raise Refused("confirmed_recipe_input_invalid")
    _, compiled = compile_recipe(member["strategy"])
    if compiled.recipe_digest != member["recipe_digest"]:
        raise Refused("recipe_digest_mismatch")
    confirmation_path, confirmation_body = _file(
        Path(member_path).parent, member["confirmation"]
    )
    if confirmation_path == Path(member_path):
        raise Refused("confirmation_self_reference")
    confirmation = json.loads(confirmation_body)
    if (
        confirmation.get("status") != "CONFIRMED"
        or confirmation.get("recipe_digest") != compiled.recipe_digest
        or confirmation.get("seed") != member["seed"]
    ):
        raise Refused("confirmation_identity_mismatch")
    recipe = {
        "member": member["member"],
        "recipe_digest": compiled.recipe_digest,
        "seed": member["seed"],
        "input_sha256": "sha256:" + _sha(member_body),
        "confirmation_sha256": "sha256:" + _sha(confirmation_body),
    }
    return member, recipe


def run(root, panel_path, member_path, out):
    """One CPU reconstruction, then score on the registered dev panel."""
    from carbon.battery.value.experiment import member_bundle
    from carbon.battery.worker import DirectBackend

    root = Path(root).resolve()
    contract, candidate, ids, refs, scenarios, settled, identity = load_panel(
        root, panel_path
    )
    member, recipe = load_confirmed_member(root, member_path)
    inputs = {c: dict(refs[c]["inputs"]) for c in ids}
    for scenario in scenarios:
        inputs.update(
            {
                j["case_id"]: {k: j[k] for k in ("c1", "c2", "t_amb_c", "soc0")}
                for j in quiz.q3_grid(contract, scenario)
            }
        )
    bundle, _state = member_bundle(
        DirectBackend(root),
        member["member"],
        member["strategy"],
        member["seed"],
        inputs,
    )
    recipe["prediction_sha256"] = "sha256:" + _sha(
        json.dumps(
            bundle["predictions"], sort_keys=True, separators=(",", ":")
        ).encode()
    )
    report = evaluate_member(
        root,
        contract,
        candidate,
        ids,
        refs,
        scenarios,
        settled,
        bundle["predictions"],
        identity,
        recipe,
    )
    report["cpu_seconds"] = bundle["seconds"]
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return report


def compare_run5(q1_path, reports):
    """Matched eight-member v2/v3 correlation; no partial-mask conclusion."""
    q1 = json.loads(Path(q1_path).read_bytes())
    members = {m: q1["members"][m] for m in q1["one_seed"]["members_ranked"]}
    v3 = {}
    for path in reports:
        row = json.loads(Path(path).read_bytes())
        if (
            row.get("schema") != "carbon.battery.v3-score-inputs.v1"
            or row.get("identity", {}).get("scope") != SCOPE
            or row["identity"].get("job") != "battery-q3-v8"
            or not row["identity"].get("panel_sha256", "").startswith("sha256:")
        ):
            raise Refused("v3_report_identity_invalid")
        member = row["recipe"]["member"]
        if member in v3:
            raise Refused("duplicate_member_report")
        v3[member] = row
    missing = sorted(
        m
        for m in members
        if m not in v3
        or v3[m]["status"] not in ("SCORED", "INELIGIBLE")
        or v3[m].get("raw_score") is None
        or v3[m].get("a") is None
        or v3[m].get("q") is None
        or v3[m].get("g_feas") is None
        or v3[m]["recipe"]["seed"] != members[m]["seed"]
    )
    if len(members) != 8 or missing:
        return {
            "status": "UNMEASURED",
            "expected_members": len(members),
            "matched_scored": len(members) - len(missing),
            "missing": missing,
            "v2": {
                "kendall_tau_b": q1["one_seed"]["kendall_tau_b"],
                "spearman_rho": q1["one_seed"]["spearman_rho"],
            },
            "v3": None,
        }
    identities = {json.dumps(v3[m]["identity"], sort_keys=True) for m in members}
    if len(identities) != 1:
        raise Refused("v3_panel_identity_mismatch")
    names = sorted(members)
    value = [-members[m]["development_decision_loss"] for m in names]
    old = [-members[m]["cpu_practice_score"] for m in names]
    candidate = tuning.load_registry(ROOT / REGISTRY)[0][CANDIDATE]
    legs = {
        m: {
            "eligible": v3[m]["eligible"],
            "E": None,
            "legs": {"a": v3[m]["a"], "q": v3[m]["q"]},
            "gates": {"feasibility": v3[m]["g_feas"]},
        }
        for m in names
    }
    ranked, _verdicts = tuning.candidate_scores(candidate, legs, lambda m: m)
    new = [ranked[m] for m in names]
    return {
        "status": "SCORED",
        "members": len(names),
        "v2": {
            "kendall_tau_b": kendall_tau_b(old, value),
            "spearman_rho": spearman_rho(old, value),
        },
        "v3": {
            "kendall_tau_b": kendall_tau_b(new, value),
            "spearman_rho": spearman_rho(new, value),
        },
        "v3_identity": v3[names[0]]["identity"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser(
        "run", help="reconstruct one confirmed recipe on a dev panel"
    )
    run_parser.add_argument("--panel", required=True, type=Path)
    run_parser.add_argument("--member", required=True, type=Path)
    run_parser.add_argument("--out", required=True, type=Path)
    compare_parser = sub.add_parser("compare-run5", help="matched v2/v3 correlations")
    compare_parser.add_argument(
        "--q1",
        type=Path,
        default=ROOT / "docs/development/evidence/graphite-run5-q1/q1-report.json",
    )
    compare_parser.add_argument("--report", action="append", default=[], type=Path)
    args = parser.parse_args(argv)
    if args.command == "run":
        result = run(ROOT, args.panel, args.member, args.out)
    else:
        result = compare_run5(args.q1, args.report)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
