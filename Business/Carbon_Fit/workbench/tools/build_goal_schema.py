#!/usr/bin/env python3
"""Generate the closed additive v0.3 goal-workbench schema and constants."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = "carbon.goal-workbench.design.v0.3"
WORKSPACE = "carbon.goal-workbench.workspace.v0.3"
APP = "Carbon Goal-to-Challenge Workbench v0.3"
BASE = "3fb98bfbfb9ca8dd3f6dd0d8e5a588a89b1c9932"
BLOCKERS = ["AT-09", "AT-16", "AT-19", "AT-22", "AT-30"]
CONTROLS = [f"P{i}" for i in range(1, 9)]
ROLES = ["MANDATORY", "SOFT", "DIAGNOSTIC", "DEPLOYMENT"]
CASE_ROLES = ["TRAIN", "EVAL", "STRESS", "QUALIFICATION", "REFERENCE_AUDIT"]


def string(maximum: int = 8_000) -> dict[str, object]:
    return {"type": "string", "maxLength": maximum}


def obj(properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def array(items: dict[str, object], maximum: int) -> dict[str, object]:
    return {"type": "array", "maxItems": maximum, "items": items}


def nullable(schema: dict[str, object]) -> dict[str, object]:
    return {"anyOf": [{"type": "null"}, schema]}


text_map = {
    "source_reference": string(),
    "reviewer_notes": string(),
    "measurement_method": string(),
    "unresolved_assumptions": string(),
}
review = obj(
    {"state": {"enum": ["UNASSESSED", "ASSEMBLED_FOR_REVIEW", "BLOCKED"]}, **text_map}
)
blocker = obj(
    {
        "applicability": {
            "enum": ["UNKNOWN", "APPLICABLE", "NOT_APPLICABLE_USER_ASSERTION"]
        },
        **text_map,
    }
)
economics_fields = [
    "reference_work",
    "reference_status",
    "group_overhead",
    "overhead_status",
    "group_size",
    "group_size_status",
    "unit",
    "unit_scope",
    "compatible_demand_status",
    "compatible_demand_source",
    "field_dependent",
    "completed_comparisons",
    "offered_requests",
    "unresolved_or_censored",
    "upfront_cost",
    "upfront_duration",
    "upfront_risk",
]
economics = obj({field: string(300) for field in economics_fields})
requirement = obj(
    {
        "requirement_id": string(128),
        "original_words": string(),
        "source_reference": string(),
        "decision_consequence": string(),
        "kind": {"enum": ["MATERIAL", "PREFERENCE", "CONSTRAINT", "EXCLUSION"]},
        "agreement_status": {
            "enum": [
                "CLIENT_ASSERTION",
                "ANALYST_PROPOSAL",
                "CLIENT_CONFIRMED",
                "SCOPED_EXCLUSION",
            ]
        },
    }
)
trace_fields = [
    "observable",
    "requested_output",
    "measurement_definition",
    "numerical_method",
    "normalization",
    "floor",
    "aggregation",
    "uncertainty",
    "population_ref",
    "stratum_ref",
    "finite_case_coverage",
    "reference_requirement",
    "authoring_binding",
    "gap",
]
trace = obj(
    {
        "trace_id": string(128),
        "requirement_id": string(128),
        **{field: string() for field in trace_fields[:4]},
        "role": {"enum": ROLES},
        **{field: string() for field in trace_fields[4:]},
    }
)
case_family = obj(
    {
        "case_family_id": string(128),
        "role": {"enum": CASE_ROLES},
        "requirement_ids": array(string(128), 64),
        "target_population": string(),
        "target_mass": string(),
        "sampling_frequency": string(),
        "analysis_weight": string(),
        "independent_physical_cases": string(),
        "reconstruction_replicas": string(),
        "generator_ref": string(),
        "rationale": string(),
        "support_status": {
            "enum": ["UNASSESSED", "PROPOSED", "SOURCE_SUPPORTED", "GAP"]
        },
    }
)
handoff = obj(
    {
        "schema_version": {"const": "carbon.goal-workbench.handoff.v1"},
        "request_id": string(128),
        "base_revision": {"type": "integer", "minimum": 1},
        "job_id": string(128),
        "design_id": string(128),
        "design_revision": {"type": "integer", "minimum": 1},
        "native_task_id": string(300),
        "sender": string(300),
        "recipient": string(300),
        "lead": string(300),
        "question": string(),
        "required_output": string(),
        "permitted_data": string(),
        "rights": string(),
        "required_authority": string(),
        "allowance": string(),
        "stop_condition": string(),
        "input_artifact_refs": array(string(500), 32),
        "dependency_owner": string(300),
        "restart_event": string(1_000),
        "route": {"enum": ["MANUAL", "VERIFIED_CONNECTOR", "UNAVAILABLE"]},
        "status": {
            "enum": ["PREPARED", "EXPORTED", "ACKNOWLEDGED", "RETURNED", "BLOCKED"]
        },
        "authority": {"const": "REQUEST_ONLY_NO_EXECUTION_OR_APPROVAL"},
    }
)
response = obj(
    {
        "schema_version": {"const": "carbon.goal-workbench.response.v1"},
        "response_id": string(128),
        "request_id": string(128),
        "base_revision": {"type": "integer", "minimum": 1},
        "job_id": string(128),
        "design_id": string(128),
        "design_revision": {"type": "integer", "minimum": 1},
        "kind": {
            "enum": [
                "ACKNOWLEDGMENT",
                "RESULT",
                "BLOCKER",
                "OWNER_DECISION",
                "LAUNCH_STATUS",
            ]
        },
        "route": {
            "enum": ["MANUAL", "VERIFIED_CONNECTOR", "UNAVAILABLE", "TEST_FIXTURE"]
        },
        "source_owner": string(300),
        "status": string(),
        "output_reference": string(),
        "input_digest": string(300),
        "authority_class": {
            "enum": [
                "UNVERIFIED_ASSERTION",
                "VERIFIED_OWNER_DECISION",
                "SYNTHETIC_TEST_EVIDENCE",
            ]
        },
        "verification_reference": string(),
        "limitations": string(),
        "note": string(),
        "content_sha256": string(128),
    }
)
semantic_receipt = obj(
    {
        "schema_version": {"const": "carbon.goal-workbench.semantic-receipt.v1"},
        "request_id": string(128),
        "job_id": string(128),
        "design_id": string(128),
        "design_revision": {"type": "integer", "minimum": 1},
        "input_digest": string(200),
        "proposal_digest": string(200),
        "expected": {"type": "object"},
        "emitted": {"type": "object"},
        "mismatches": array(string(1_000), 32),
        "status": {"enum": ["INTENT_PRESERVED", "INTENT_MISMATCH"]},
        "qualification": {"const": "NOT_QUALIFIED"},
        "launch": {"const": "NOT_LAUNCHED"},
    }
)
extension_request = obj(
    {
        "schema_version": {"const": "carbon.goal-workbench.authoring-extension.v1"},
        "request_id": string(128),
        "job_id": string(128),
        "design_id": string(128),
        "design_revision": {"type": "integer", "minimum": 1},
        "missing_capability": string(),
        "client_rationale": string(),
        "compatible_existing_components": string(),
        "proposed_tests": string(),
        "unresolved_scientific_choices": string(),
        "owner_interface": string(),
    }
)
scope_fields = [
    "physics_family",
    "requested_goal",
    "intended_use",
    "inputs",
    "outputs",
    "units",
    "geometry",
    "conditions",
    "regime",
    "exclusions",
    "query_workload",
    "turnaround",
    "failure_consequences",
    "data_access",
    "rights_scope",
]
score_fields = [
    "official_score_status",
    "mandatory_gate_summary",
    "soft_estimand",
    "training_objective",
    "reward_accounting",
    "deployment_acceptance",
    "unresolved_tradeoffs",
]
reference_fields = [
    "equation",
    "role",
    "method",
    "configuration",
    "convergence_evidence",
    "uncertainty_evidence",
    "applicable_envelope",
    "failures",
    "cost_scope",
    "independence_limitations",
]
decision_fields = [
    "client_interpretation",
    "design_completeness",
    "authoring_status",
    "evidence_status",
    "scientific_qualification",
    "security_rights",
    "launch_authorization",
    "native_launch_status",
    "owner_decision",
    "next_action",
    "permitted_claims",
]
design = obj(
    {
        "schema_version": {"const": DESIGN},
        "job_id": string(128),
        "design_id": string(128),
        "revision": {"type": "integer", "minimum": 1},
        "parent_design_id": nullable(string(128)),
        "status": {"enum": ["DRAFT", "SEALED", "SUPERSEDED"]},
        "alternative_label": string(300),
        "scope": obj({field: string() for field in scope_fields}),
        "requirements": array(requirement, 128),
        "traces": array(trace, 256),
        "cases": array(case_family, 128),
        "score_plan": obj({field: string() for field in score_fields}),
        "reference_plan": obj({field: string() for field in reference_fields}),
        "cpes": obj(
            {
                "study_ref": {"const": "CPES-REFERENCE-REUSE-GAUNTLET-V2"},
                "baseline": {"const": "RETAIN_A_DEVELOPMENT"},
                "design_binding_revision": {"type": "integer", "minimum": 1},
                "protection": obj(
                    {
                        "controls": obj({control: review for control in CONTROLS}),
                        "blockers": obj({attack: blocker for attack in BLOCKERS}),
                        "publication_review": obj(
                            {"rights_notes": string(), "retirement_notes": string()}
                        ),
                    }
                ),
                "economics": economics,
                "invalidated_by": array(string(300), 64),
            }
        ),
        "authoring": obj(
            {
                "template_id": string(300),
                "requested_goal": string(300),
                "compatibility": {
                    "enum": [
                        "UNASSESSED",
                        "EXACT_SUPPORTED",
                        "INTENT_MISMATCH",
                        "EXTENSION_REQUIRED",
                    ]
                },
                "request_id": string(300),
                "result_ref": string(300),
                "semantic_receipt": nullable(semantic_receipt),
                "extension_request": nullable(extension_request),
            }
        ),
        "handoffs": array(handoff, 128),
        "responses": array(response, 256),
        "decision": obj({field: string() for field in decision_fields}),
        "change_log": array(
            obj(
                {
                    "field": string(500),
                    "kind": string(500),
                    "impact": string(500),
                    "note": string(500),
                }
            ),
            128,
        ),
    }
)
job = obj(
    {
        "job_id": string(128),
        "title": string(300),
        "source_opportunity_id": nullable(string(128)),
        "native_task_id": string(300),
        "lead": string(300),
        "assignment": obj(
            {
                field: string()
                for field in [
                    "client_words",
                    "client_source",
                    "intended_decision",
                    "credible_baseline",
                    "context",
                    "allowances",
                    "rights_summary",
                    "next_owner_decision",
                ]
            }
        ),
        "designs": array(design, 64),
        "created_from": {"enum": ["DIRECT_INTAKE", "ASSISTED_INTAKE", "MIGRATED"]},
    }
)
component = json.loads(
    (ROOT / "data/workspace.schema.json").read_text(encoding="utf-8")
)
schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Carbon goal-to-Challenge workbench workspace v0.3",
    "$comment": (
        "Closed browser-local planning schema. Derived results are recomputed. "
        "It grants no scientific, security, rights, reuse, submission, execution, or launch authority."
    ),
    "$defs": {"opportunity_workspace_v02": component},
    **obj(
        {
            "schema_version": {"const": WORKSPACE},
            "application_version": {"const": APP},
            "decision_id": {"const": "GOAL-WORKBENCH-02"},
            "base_application_merge": {"const": BASE},
            "opportunity_workspace": {"$ref": "#/$defs/opportunity_workspace_v02"},
            "jobs": array(job, 64),
            "selected_job_id": nullable(string(128)),
            "selected_design_id": nullable(string(128)),
            "migration_receipts": array(
                obj(
                    {
                        "from": string(200),
                        "to": {"const": WORKSPACE},
                        "original_digest_status": {
                            "enum": ["VERIFIED_WEB_CRYPTO", "UNAVAILABLE"]
                        },
                        "semantic_changes": array(string(500), 16),
                    }
                ),
                128,
            ),
            "authority": obj(
                {
                    "qualification": {"const": "NOT_QUALIFIED_BY_THIS_TOOL"},
                    "launch": {"const": "NOT_LAUNCHED"},
                    "sharing": {"const": "RETAIN_A_DEVELOPMENT_ONLY"},
                    "submission": {"const": "NOT_SENT_BY_THIS_TOOL"},
                }
            ),
        }
    ),
}
constants = {
    "DESIGN_VERSION": DESIGN,
    "WORKSPACE_VERSION": WORKSPACE,
    "APP_VERSION": APP,
    "BASE_APPLICATION_MERGE": BASE,
    "BLOCKERS": BLOCKERS,
    "CONTROLS": CONTROLS,
    "ROLES": ROLES,
    "CASE_ROLES": CASE_ROLES,
}
(ROOT / "data/goal_workspace.schema.json").write_text(
    json.dumps(schema, indent=2) + "\n", encoding="utf-8"
)
(ROOT / "data/goal_constants.json").write_text(
    json.dumps(constants, indent=2) + "\n", encoding="utf-8"
)
print("v0.3 goal-workbench schema and constants generated")
