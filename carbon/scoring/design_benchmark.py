"""Pure DEVELOPMENT rich-Design projections through the existing dual core.

Inputs are already native-bound measurements, predictions and references. This
module constructs no model, reads no files and grants no reference acceptance.
It retains the original Physics leg, gates, outcome policy and combination. The
point projection is explicitly partial; only the registered projection requires
all coverage and accepted-interval evidence demanded by ``design_fidelity``.
Neither projection adopts a rule or creates official scoring authority.
An optional, separately identified finite-task projection uses a complete
source-accepted point roster. It claims no interval, boundary or OOD adequacy.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from copy import deepcopy

from carbon.scoring import design_fidelity, dual_score
from carbon.scoring.engine import ScoreEngine

PARTIAL_POINT_DIAGNOSTIC = "PARTIAL_POINT_DIAGNOSTIC"
REGISTERED_COMPONENTS_REQUIRED = "REGISTERED_COMPONENTS_REQUIRED"
FINITE_TASK_POINT_REFERENCE = "FINITE_TASK_POINT_REFERENCE"
_METRIC = "rich_design_benefit"
_FINITE_METRIC = "finite_task_point_design_benefit"


class DesignBenchmarkRefused(ValueError):
    """An inconsistent input binding, not a candidate's scientific failure."""


def _require(value, reason):
    if not value:
        raise DesignBenchmarkRefused(reason)


def _identity(value):
    # A typed input identity preserves nonfinite candidate/reference separation;
    # it is not the digest of the original prediction file's bytes.
    return design_fidelity.digest(design_fidelity.typed_identity(value))


def _measurement_basis(value):
    fields = {
        "schema",
        "producer_digest",
        "accuracy_definition_sha256",
        "important_limit_definition_sha256",
        "design_objective_sha256",
    }
    _require(type(value) is dict and set(value) == fields, "measurement_basis_shape")
    _require(
        value["schema"] == "carbon.scoring.dual-measurement-contract.v1",
        "measurement_basis_schema",
    )
    _require(
        all(
            type(value[key]) is str
            and value[key].startswith("sha256:")
            and len(value[key]) == 71
            and all(char in "0123456789abcdef" for char in value[key][7:])
            for key in fields - {"schema"}
        ),
        "measurement_basis_identity",
    )
    return deepcopy(value)


def _finite_registration(value, policy, reference):
    fields = {
        "schema",
        "scope",
        "mode",
        "policy_digest",
        "reference_digest",
        "source_acceptance_digest",
        "native_point_contract_digest",
        "action_ids",
        "case_ids",
        "mandatory_condition_ids",
        "action_condition_case_ids",
    }
    _require(type(value) is dict and set(value) == fields, "finite_registration_shape")
    _require(
        value["schema"] == "carbon.scoring.finite-task-point-registration.v1"
        and value["scope"] == "DEVELOPMENT"
        and value["mode"] == FINITE_TASK_POINT_REFERENCE,
        "finite_registration_scope_or_schema",
    )
    for key in ("source_acceptance_digest", "native_point_contract_digest"):
        token = value[key]
        _require(
            type(token) is str
            and token.startswith("sha256:")
            and len(token) == 71
            and all(c in "0123456789abcdef" for c in token[7:]),
            "finite_registration_source_identity",
        )
    _require(
        value["policy_digest"] == _identity(policy)
        and value["reference_digest"] == _identity(reference),
        "finite_registration_binding",
    )
    _require(
        value["action_ids"] == policy["action_ids"]
        and value["case_ids"] == policy["case_ids"],
        "finite_registration_roster",
    )
    conditions = value["mandatory_condition_ids"]
    mapping = value["action_condition_case_ids"]
    _require(
        type(conditions) is list
        and bool(conditions)
        and all(type(c) is str and bool(c) for c in conditions)
        and len(set(conditions)) == len(conditions)
        and type(mapping) is dict
        and set(mapping) == set(policy["action_ids"]),
        "finite_registration_conditions",
    )
    flattened = []
    for action in policy["action_ids"]:
        row = mapping[action]
        _require(
            type(row) is dict
            and set(row) == set(conditions)
            and all(type(c) is str for c in row.values()),
            "finite_registration_action_conditions",
        )
        flattened.extend(row.values())
    _require(
        len(flattened) == len(set(flattened))
        and set(flattened) == set(policy["case_ids"]),
        "finite_registration_whole_task_roster",
    )
    return deepcopy(value)


def _finite_evidence(policy, reference, models):
    """Require the whole source roster; never infer acceptance from model errors."""
    issues = []
    quantities = {
        c["quantity"]
        for c in policy["components"]
        if c["kind"] != "gap" and policy["quantities"][c["quantity"]]["learned"]
    }
    if set(reference["cases"]) != set(policy["case_ids"]):
        issues.append("REFERENCE_CASE_ROSTER_INCOMPLETE")
    if set(reference["actions"]) != set(policy["action_ids"]):
        issues.append("REFERENCE_ACTION_ROSTER_INCOMPLETE")
    point_reference = deepcopy(reference)
    for case in policy["case_ids"]:
        row = reference["cases"].get(case)
        if type(row) is not dict:
            issues.append("REFERENCE_CASE_MISSING_OR_INVALID:" + case)
            continue
        for quantity in quantities - set(row):
            issues.append("REFERENCE_QUANTITY_MISSING:" + case + ":" + quantity)
        for quantity, atom in row.items():
            spec = policy["quantities"].get(quantity)
            if spec is None:
                issues.append("REFERENCE_UNKNOWN_QUANTITY:" + case + ":" + quantity)
            elif design_fidelity.reference_atom(atom, spec["unit"])["point"] is None:
                issues.append("REFERENCE_ATOM_UNRESOLVED:" + case + ":" + quantity)
            else:
                # This distinct projection uses points, never manufactured intervals.
                point_reference["cases"][case][quantity]["interval"] = None
    for action in policy["action_ids"]:
        row = reference["actions"].get(action)
        if (
            type(row) is not dict
            or set(row) != {"feasibility", "objective"}
            or row.get("feasibility")
            not in (
                "FEASIBLE",
                "INFEASIBLE",
            )
        ):
            issues.append("REFERENCE_ACTION_UNRESOLVED:" + action)
            continue
        atom = row.get("objective")
        if atom is not None or row["feasibility"] == "FEASIBLE":
            if (
                design_fidelity.reference_atom(atom, policy["objective"]["unit"])[
                    "point"
                ]
                is None
            ):
                issues.append("REFERENCE_OBJECTIVE_UNRESOLVED:" + action)
            else:
                point_reference["actions"][action]["objective"]["interval"] = None
    candidate_issues = {}
    for model in models:
        _require(
            type(model) is dict
            and set(model) == {"artifact_digest", "selected_action", "cases", "actions"}
            and type(model["cases"]) is dict
            and type(model["actions"]) is dict
            and (
                model["selected_action"] is None
                or (
                    type(model["selected_action"]) is str
                    and model["selected_action"] in policy["action_ids"]
                )
            ),
            "finite_candidate_container",
        )
        bad = []
        if set(model["cases"]) != set(policy["case_ids"]):
            bad.append("CANDIDATE_COMMON_CASE_MASK_MISMATCH")
        if set(model["actions"]) != set(policy["action_ids"]):
            bad.append("CANDIDATE_ACTION_ROSTER_MISMATCH")
        for case in policy["case_ids"]:
            row = model["cases"].get(case)
            for quantity in quantities:
                atom = row.get(quantity) if type(row) is dict else None
                _, reason = design_fidelity.prediction_atom(
                    atom, policy["quantities"][quantity]["unit"]
                )
                if reason:
                    bad.append(reason + ":" + case + ":" + quantity)
        if policy["objective"]["learned"]:
            for action in policy["action_ids"]:
                row = model["actions"].get(action)
                atom = row.get("objective") if type(row) is dict else None
                _, reason = design_fidelity.prediction_atom(
                    atom, policy["objective"]["unit"]
                )
                if reason:
                    bad.append(reason + ":objective:" + action)
        candidate_issues[model["artifact_digest"]] = sorted(set(bad))
    return point_reference, sorted(set(issues)), candidate_issues


def _reduce_finite_source_gap(policy, reference, models, context):
    """Defer only when unresolved source actions explain a frozen-pair mismatch."""
    try:
        return design_fidelity.reduce_design(policy, reference, models)
    except design_fidelity.ReductionRefused as error:
        if str(error) != "gap_requires_every_settled_feasible_pair":
            raise
        feasible, unresolved = [], []
        for action in policy["action_ids"]:
            row = reference["actions"].get(action)
            if type(row) is dict and set(row) == {"feasibility", "objective"}:
                if row["feasibility"] == "INFEASIBLE":
                    continue
                if (
                    row["feasibility"] == "FEASIBLE"
                    and design_fidelity.reference_atom(
                        row["objective"], policy["objective"]["unit"]
                    )["point"]
                    is not None
                ):
                    feasible.append(action)
                    continue
            unresolved.append(action)
        if not unresolved or not context["reference_issues"]:
            raise
        known_pairs = set(itertools.combinations(sorted(feasible), 2))
        possible_pairs = set(itertools.combinations(sorted(feasible + unresolved), 2))
        for component in policy["components"]:
            if (
                component["kind"] != "gap"
                or not policy["quantities"][component["quantity"]]["learned"]
            ):
                continue
            pairs = [tuple(sorted(pair)) for pair in component["pairs"]]
            # Preserve rejection of independently malformed frozen pair panels.
            if (
                len(pairs) != len(set(pairs))
                or not known_pairs <= set(pairs) <= possible_pairs
            ):
                raise
        issues = sorted(
            set(context["reference_issues"] + ["REFERENCE_ACTION_GAP_PANEL_UNRESOLVED"])
        )
        rows = []
        for model in models:
            selected = reference["actions"].get(model["selected_action"])
            unsafe = (
                type(selected) is dict
                and set(selected) == {"feasibility", "objective"}
                and selected["feasibility"] == "INFEASIBLE"
            )
            bad = context["candidate_issues"][model["artifact_digest"]]
            rows.append(
                {
                    "artifact_digest": model["artifact_digest"],
                    "prediction_digest": _identity(model),
                    "candidate_issues": deepcopy(bad),
                    "candidate_status": (
                        "INVALID"
                        if bad
                        else (
                            "PROVEN_UNSAFE_SELECTION"
                            if unsafe
                            else (
                                "ABSTAIN"
                                if model["selected_action"] is None
                                else "VALID_PREDICTIONS"
                            )
                        )
                    ),
                    "reference_status": "PARTIAL_OR_UNRESOLVED",
                    "status": (
                        "CANDIDATE_INVALID"
                        if bad
                        else (
                            "CANDIDATE_UNSAFE_SELECTION"
                            if unsafe
                            else "REFERENCE_UNRESOLVED"
                        )
                    ),
                    "candidate_selection_outcome": (
                        "SELECTED_PROVEN_INFEASIBLE"
                        if unsafe
                        else "REFERENCE_UNRESOLVED"
                    ),
                    "point_estimate_D": None,
                    "registered_D": None,
                    "full_credit_eligible": False,
                    "earns_full_credit": False,
                    "D_bounds": None,
                    "V": design_fidelity.value_result(
                        policy, {}, [], unresolved, model["selected_action"]
                    ),
                    "C": None,
                    "C_bounds": None,
                    "reference_limitations": issues,
                    "critical_components": {},
                    "coverage_slot_errors": {},
                    "limiting_components": [],
                    "no_scientific_candidate_penalty_from_reference_gap": True,
                }
            )
        # Typed absence only: no replacement action, reference point, component,
        # objective or interval is fabricated to make the frozen panel reduce.
        return {
            "policy_digest": design_fidelity.digest(policy),
            "common_mask_digest": design_fidelity.digest(
                {"case_ids": policy["case_ids"], "action_ids": policy["action_ids"]}
            ),
            "reference_coverage_digest": _identity(reference),
            "reference_coverage_digest_basis": "CANONICAL_TYPED_REFERENCE_NOT_RAW_BYTES",
            "full_credit_panel_eligible": False,
            "reference_limitations": issues,
            "coverage": [],
            "settled_feasible_actions": sorted(feasible),
            "unresolved_potentially_competitive_actions": sorted(unresolved),
            "models": rows,
            "official_score": False,
            "score_adopted": False,
        }


def _project(
    policy,
    reduction,
    original_pack,
    original_benchmark,
    mode,
    measurement_basis,
    finite_context=None,
):
    description = {
        "algorithm": "rich-design-same-core-development-v1",
        "mode": mode,
        "policy": deepcopy(policy),
        "reference_coverage_digest": reduction["reference_coverage_digest"],
        "common_mask_digest": reduction["common_mask_digest"],
        "original_pack_digest": original_pack["pack_digest"],
        "reference_scope": "SUPPLIED_REFERENCE_NOT_QUALIFIED_BY_THIS_PROJECTION",
        "score_adopted": False,
    }
    finite_mode = mode == FINITE_TASK_POINT_REFERENCE
    metric = _FINITE_METRIC if finite_mode else _METRIC
    if finite_mode:
        description.update(
            finite_task_registration=finite_context["registration"],
            reference_scope="COMPLETE_FINITE_TASK_SOURCE_ACCEPTED_POINTS_ONLY",
            uncertainty="UNMEASURED",
        )
    normal_basis = measurement_basis is not None and mode != PARTIAL_POINT_DIAGNOSTIC
    measurement = deepcopy(measurement_basis) if normal_basis else description
    if normal_basis:
        # Match the normal consumer's canonical document bytes, including LF.
        raw = (
            json.dumps(
                measurement, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
            + "\n"
        ).encode("utf-8")
        contract_digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    else:
        contract_digest = design_fidelity.digest(measurement)
    body = deepcopy(original_pack)
    del body["pack_digest"]
    body["measurement_contract_digest"] = contract_digest
    body["legs"]["D"] = {
        "minimum": None,
        "components": [
            {
                "metric": metric,
                "unit": "1",
                "transform": "unit_benefit",
                "scale": None,
                "weight": 1.0,
            }
        ],
    }
    pack = dual_score.register_pack(body)
    benchmark = deepcopy(original_benchmark)
    benchmark["measurement_contract_digest"] = contract_digest
    previous = [c["metric"] for c in original_pack["legs"]["D"]["components"]]
    reduced = {row["artifact_digest"]: row for row in reduction["models"]}
    for model in benchmark["models"]:
        row = reduced[model["artifact_digest"]]
        for previous_metric in previous:
            del model["measurements"][previous_metric]
        if row["candidate_issues"] or (
            finite_mode and finite_context["candidate_issues"][model["artifact_digest"]]
        ):
            status, value = "CANDIDATE_INVALID", None
        elif row["candidate_selection_outcome"] == "SELECTED_PROVEN_INFEASIBLE":
            # The native gate/outcome remains the authority for inadmissibility.
            outcome = original_pack["decision_policy"].get(model["decision_outcome"])
            _require(
                "FAIL" in model["gates"].values()
                or (outcome is not None and not outcome["eligible"]),
                "unsafe_selection_missing_native_inadmissibility",
            )
            # Complete point evidence establishes this breach. Retain the
            # native hard failure instead of classifying it as missing truth;
            # the core cannot award a score when that gate/outcome fails.
            status, value = (
                ("RESOLVED", 0.0)
                if mode == PARTIAL_POINT_DIAGNOSTIC
                or (finite_mode and not finite_context["reference_issues"])
                else ("NOT_MEASURED", None)
            )
        else:
            value = row[
                (
                    "point_estimate_D"
                    if mode in (PARTIAL_POINT_DIAGNOSTIC, FINITE_TASK_POINT_REFERENCE)
                    else "registered_D"
                )
            ]
            if finite_mode and finite_context["reference_issues"]:
                value = None
                # The source gap is common and recorded in the finite audit.
                # NOT_MEASURED keeps every valid model unscored without the
                # core's global reference precedence hiding an invalid model.
                status = "NOT_MEASURED"
            else:
                status = "RESOLVED" if value is not None else "REFERENCE_UNRESOLVED"
        model["measurements"][metric] = {
            "status": status,
            "value": value,
            "unit": "1",
        }
    result = ScoreEngine.score_dual_benchmark_v4(benchmark, pack)
    if mode == REGISTERED_COMPONENTS_REQUIRED:
        for model in result["models"]:
            if reduced[model["artifact_digest"]]["registered_D"] is None:
                _require(
                    model["score"] is None,
                    "partial_coverage_cannot_produce_registered_score",
                )
    projection = {
        "label": mode,
        "diagnostic_only": mode == PARTIAL_POINT_DIAGNOSTIC,
        "measurement_contract": measurement,
        "score_pack": pack,
        "benchmark_input": benchmark,
        "score_result": result,
        "official_score": False,
        "score_adopted": False,
    }
    if normal_basis:
        # An exact contract shape/digest is not producer authentication. The
        # normal caller still needs its trusted receipt and role-hash bindings.
        projection["design_audit"] = {
            "projection_definition": description,
            "policy_digest": reduction["policy_digest"],
            "model_prediction_digests": {
                row["artifact_digest"]: row["prediction_digest"]
                for row in reduction["models"]
            },
        }
    if finite_mode:
        projection["finite_task_audit"] = {
            "projection_definition": description,
            "reference_issues": finite_context["reference_issues"],
            "candidate_issues": finite_context["candidate_issues"],
            "uncertainty": "UNMEASURED",
            "interval_boundary_or_ood_qualified": False,
            "source_acceptance_authenticated_by_this_library": False,
            "point_reference_reduction": deepcopy(reduction),
        }
    return projection


def score_design_benchmark(
    policy,
    reference,
    models,
    original_pack,
    original_benchmark,
    *,
    provenance,
    original_result=None,
    measurement_basis=None,
    finite_task_registration=None,
    finite_task_measurement_basis=None,
):
    """Reduce fixed Design evidence and produce both labelled core projections.

    ``provenance`` must bind ``original_pack_digest`` and
    ``original_benchmark_digest``. The latter is canonical typed JSON via
    ``design_fidelity.digest(design_fidelity.typed_identity(benchmark))``, not
    a file-byte hash. Additional source, artifact and full-workflow cost records
    are retained unchanged. If supplied, ``original_result`` must replay exactly.

    Models must match the native benchmark's exact artifact set (no implicit
    cohort intersection); callers may explicitly submit matching subsets of
    both lists. Fixed-reference projection pack identities do not depend on the
    compared model cohort. Input bindings are returned separately from those
    pack identities. The already registered 50/50 weight is required, with its
    original combination and native Physics/gate rules retained.

    An optional ``measurement_basis`` is the normal consumer's exact five-field
    ``carbon.scoring.dual-measurement-contract.v1`` document, with typed SHA-256
    identities. Only the registered projection uses it and hashes its canonical
    JSON plus LF. The point diagnostic retains its distinct descriptive contract.
    Rich policy/reference/model audit remains separate. This option authenticates
    no caller: the normal consumer still requires a trusted producer receipt and
    selected-definition role-hash bindings. It supplies no missing references.

    ``finite_task_registration`` optionally adds FINITE_TASK_POINT_REFERENCE.
    Its closed v1 document binds the exact policy/reference digests, ordered
    action/case rosters, every action's mandatory-condition-to-case mapping,
    source acceptance and native point-contract digests, and DEVELOPMENT scope.
    Those assertions must come from the source owner; hashes do not authenticate
    or grant scientific acceptance. All reference points/whole actions must be
    resolved and every required candidate prediction present. Missing reference
    evidence defers every model on the same roster. Missing sign-side/proximity
    or interval evidence does not block this narrower finite-task projection.
    Supplied intervals are ignored for its point reduction; uncertainty remains
    UNMEASURED. It retains the original two projections and native A/gates/cost.

    ``finite_task_measurement_basis`` may bind this projection to a normal
    producer. If the interval projection also supplies a basis, the producer and
    Design-definition roles must both differ. The finite projection additionally
    uses a distinct D-metric namespace, preventing pack-identity aliasing even
    when an external caller supplies identical contract bytes across calls.
    """
    if measurement_basis is not None:
        measurement_basis = _measurement_basis(measurement_basis)
    if finite_task_measurement_basis is not None:
        _require(finite_task_registration is not None, "finite_registration_required")
        finite_task_measurement_basis = _measurement_basis(
            finite_task_measurement_basis
        )
        if measurement_basis is not None:
            _require(
                all(
                    finite_task_measurement_basis[key] != measurement_basis[key]
                    for key in ("producer_digest", "design_objective_sha256")
                ),
                "finite_measurement_basis_roles_must_be_distinct",
            )
    _require(type(provenance) is dict, "provenance_required")
    _require(type(original_pack) is dict, "original_pack_required")
    _require(type(original_benchmark) is dict, "original_benchmark_required")
    _require(
        provenance.get("original_pack_digest") == original_pack.get("pack_digest")
        and original_pack.get("pack_digest") is not None,
        "original_pack_binding",
    )
    _require(
        provenance.get("original_benchmark_digest") == _identity(original_benchmark),
        "original_benchmark_binding",
    )
    _require(original_pack.get("value_weight") == 0.5, "original_50_50_required")
    replay = ScoreEngine.score_dual_benchmark_v4(original_benchmark, original_pack)
    if original_result is not None:
        _require(replay == original_result, "original_result_replay")
    _require(type(models) is list and bool(models), "paired_model_identity")
    identities = [m.get("artifact_digest") for m in models if type(m) is dict]
    native = {m["artifact_digest"] for m in original_benchmark["models"]}
    _require(
        len(identities) == len(models)
        and all(type(key) is str for key in identities)
        and len(set(identities)) == len(identities)
        and set(identities) == native,
        "paired_model_identity",
    )
    _require(
        _METRIC not in {c["metric"] for c in original_pack["legs"]["A"]["components"]},
        "design_metric_collides_with_physics",
    )
    finite_context = None
    if finite_task_registration is not None:
        design_fidelity.validate_policy(policy)
        design_fidelity.shape(reference, ("cases", "actions"), "reference_container")
        _require(
            type(reference["cases"]) is dict and type(reference["actions"]) is dict,
            "finite_reference_masks",
        )
        registration = _finite_registration(finite_task_registration, policy, reference)
        point_reference, issues, candidate_issues = _finite_evidence(
            policy, reference, models
        )
        finite_context = {
            "registration": registration,
            "reference_issues": issues,
            "candidate_issues": candidate_issues,
        }
        reduction = _reduce_finite_source_gap(policy, reference, models, finite_context)
    else:
        reduction = design_fidelity.reduce_design(policy, reference, models)
    projections = {
        mode: _project(
            policy,
            reduction,
            original_pack,
            original_benchmark,
            mode,
            measurement_basis,
        )
        for mode in (PARTIAL_POINT_DIAGNOSTIC, REGISTERED_COMPONENTS_REQUIRED)
    }
    if finite_task_registration is not None:
        _require(
            _FINITE_METRIC
            not in {c["metric"] for c in original_pack["legs"]["A"]["components"]},
            "finite_design_metric_collides_with_physics",
        )
        point_reduction = _reduce_finite_source_gap(
            policy, point_reference, models, finite_context
        )
        # Finite input atoms can still overflow a derived reference difference.
        # Such a common source gap cannot disappear behind another component.
        for row in point_reduction["models"]:
            for name, component in row["critical_components"].items():
                if any(r["reference_point"] is None for r in component["rows"]):
                    issues.append("REFERENCE_COMPONENT_UNRESOLVED:" + name)
        issues = sorted(set(issues))
        finite_projection = _project(
            policy,
            point_reduction,
            original_pack,
            original_benchmark,
            FINITE_TASK_POINT_REFERENCE,
            finite_task_measurement_basis,
            {**finite_context, "reference_issues": issues},
        )
        _require(
            all(
                finite_projection["score_pack"]["pack_digest"]
                != p["score_pack"]["pack_digest"]
                for p in projections.values()
            ),
            "finite_projection_must_have_distinct_pack_identity",
        )
        projections[FINITE_TASK_POINT_REFERENCE] = finite_projection
    return {
        "schema": "carbon.scoring.rich-design-benchmark.v1",
        "scope": original_pack["scope"],
        "reduction": reduction,
        "projections": projections,
        "original": {
            "score_pack": deepcopy(original_pack),
            "benchmark_input": deepcopy(original_benchmark),
            "score_result": replay,
        },
        "provenance": deepcopy(provenance),
        "input_bindings": {
            "policy_digest": reduction["policy_digest"],
            "reference_digest": reduction["reference_coverage_digest"],
            "models_digest": _identity(models),
            "original_pack_digest": original_pack["pack_digest"],
            "original_benchmark_digest": _identity(original_benchmark),
            "digest_basis": "CANONICAL_TYPED_INPUTS_NOT_RAW_FILES",
        },
        "official_score": False,
        "score_adopted": False,
    }
