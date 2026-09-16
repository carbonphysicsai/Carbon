#!/usr/bin/env python3
"""Generate the closed additive v0.8 goal-workbench and intake schemas."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = "carbon.goal-workbench.design.v0.8"
WORKSPACE = "carbon.goal-workbench.workspace.v0.8"
APP = "Carbon Goal-to-Challenge Workbench v0.8"
BASE = "94762b6a8932ac6834c731a416c3a45c4cbf6170"
BLOCKERS = ["AT-09", "AT-16", "AT-19", "AT-22", "AT-30"]
CONTROLS = [f"P{i}" for i in range(1, 9)]
ROLES = ["MANDATORY", "SOFT", "DIAGNOSTIC", "DEPLOYMENT"]
CASE_ROLES = ["TRAIN", "EVAL", "STRESS", "QUALIFICATION", "REFERENCE_AUDIT"]
ROUTES = [
    "UNASSESSED",
    "USE_EXISTING_CAPABILITY",
    "ADAPT_SUPPORTED_CHALLENGE",
    "DEVELOP_NEW_CAPABILITY",
]
PROVENANCE = [
    "WORKBENCH_DERIVED",
    "LOCAL_MANUAL_ASSERTION",
    "NATIVE_IMPORTED_RESULT",
    "EXTERNAL_LINKED_RECORD",
]
CUSTOMER_OUTCOMES = [
    "OPEN",
    "FEASIBILITY_FINDING",
    "SCOPE_REVISION_NEEDED",
    "BASELINE_RETAINED",
    "CANDIDATE_READY_FOR_FURTHER_TEST",
    "DELIVERY_QUALIFICATION_REQUIRED",
    "PARKED",
    "CLOSED",
]
DEPENDENCY_DOMAINS = [
    "COMMERCIAL_CONTEXT",
    "INTENDED_USE",
    "PHYSICS_SCOPE",
    "INPUT_CONTRACT",
    "OUTPUT_CONTRACT",
    "UNITS_SCALING",
    "POPULATION_CASES",
    "GENERATOR",
    "MEASUREMENT_SCORE",
    "REFERENCE",
    "RECONSTRUCTION",
    "CPES_DISCLOSURE",
    "RIGHTS",
    "DEPLOYMENT",
    "AUTHORING",
    "UNRESOLVED_IMPACT",
]
SCOPE_RELATIONSHIPS = ["UNASSESSED", "UNCHANGED", "CHANGED", "UNKNOWN"]
ORIGIN_VERIFICATION = [
    "UNVERIFIED_CLAIM",
    "EXTERNAL_LOCATOR_ONLY",
    "PINNED_C05_FIXTURE_VERIFIED",
    "WORKBENCH_DERIVED_LINEAGE",
]


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
route_plan = obj(
    {
        "route": {"enum": ROUTES},
        "rationale": string(),
        "source_or_capability_ref": string(),
        "route_basis": string(),
        "unresolved_conditions": array(string(1_000), 64),
        "next_decision": string(),
        "bounded_question": string(),
        "stop_condition": string(),
        "restart_event": string(),
        "selected_by_assertion": string(),
        "status_provenance": {"enum": PROVENANCE},
    }
)
external_record = obj(
    {
        "record_id": string(192),
        "source_ref": string(1_000),
        "status": {
            "enum": [
                "PREPARED",
                "EXPORTED_OWNER_REQUEST",
                "SENT",
                "ACKNOWLEDGED",
                "EXECUTION_REPORTED_ACTIVE",
                "EXECUTED",
                "RETURNED",
                "FAILED",
                "OWNER_DECISION",
                "BLOCKED",
            ]
        },
        "provenance": {"const": "EXTERNAL_LINKED_RECORD"},
        "note": string(2_000),
    }
)
coordination = obj(
    {
        "customer_outcome": {"enum": CUSTOMER_OUTCOMES},
        "customer_outcome_provenance": {"enum": PROVENANCE},
        "decision_needed": string(),
        "blocker": string(),
        "blocker_owner": string(),
        "restart_event": string(),
        "current_action_ref": string(192),
        "external_records": array(external_record, 64),
        "last_relevant_design_revision": {"type": "integer", "minimum": 1},
    }
)
evidence_binding = obj(
    {
        "evidence_binding_id": string(192),
        "evidence_kind": {
            "enum": [
                "MEASUREMENT_IMPLEMENTATION",
                "TEMPLATE",
                "PRIOR_DECISION",
                "FIXED_CASE_RESULT",
                "RESEARCH_REFERENCE",
                "DEPLOYMENT_EVIDENCE",
                "MANUAL_RESEARCH_NOTE",
            ]
        },
        "source_ref": string(1_000),
        "source_digest_or_identity": string(300),
        "design_id": string(128),
        "design_revision": {"type": "integer", "minimum": 1},
        "originating_design_id": string(128),
        "originating_design_revision": {"type": "integer", "minimum": 1},
        "originating_binding_id": string(192),
        "trace_ids": array(string(128), 256),
        "case_family_ids": array(string(128), 128),
        "dependency_domains": array({"enum": DEPENDENCY_DOMAINS}, 32),
        "scope_relationship": {"enum": SCOPE_RELATIONSHIPS},
        "scientific_applicability": {
            "enum": [
                "UNASSESSED",
                "REVIEW_REQUIRED",
                "NOT_APPLICABLE",
            ]
        },
        "use_or_rights_status": {
            "enum": [
                "UNRESOLVED",
                "REVIEW_REQUIRED",
                "PROHIBITED",
            ]
        },
        "assessment_basis": string(2_000),
        "rationale": string(2_000),
        "invalidated_by": array(string(1_000), 64),
        "scientific_review_reasons": array(
            obj(
                {
                    "reason_id": string(192),
                    "domain": {"enum": DEPENDENCY_DOMAINS},
                    "field": string(500),
                    "originating_design_id": string(128),
                    "originating_revision": {"type": "integer", "minimum": 1},
                    "basis": string(1_000),
                }
            ),
            128,
        ),
        "rights_review_reasons": array(
            obj(
                {
                    "reason_id": string(192),
                    "domain": {"enum": DEPENDENCY_DOMAINS},
                    "field": string(500),
                    "originating_design_id": string(128),
                    "originating_revision": {"type": "integer", "minimum": 1},
                    "basis": string(1_000),
                }
            ),
            128,
        ),
        "source_claimed_provenance": {"enum": PROVENANCE},
        "origin_verification": {"enum": ORIGIN_VERIFICATION},
        "status_provenance": {"enum": PROVENANCE},
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
    "commercial_context",
    "disclosure_scope",
    "deployment_environment",
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
digest = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
candidate_identity = obj(
    {
        field: (string(160) if field == "replica_id" else digest)
        for field in [
            "artifact_digest",
            "binding_digest",
            "source_digest",
            "environment_digest",
            "plan_digest",
            "replica_id",
        ]
    }
)
reference_identity = obj(
    {
        "artifact_digest": digest,
        "request_digest": digest,
        "policy_digest": digest,
        "environment_digest": digest,
        "role": string(100),
        "scientifically_qualified": {"const": False},
    }
)
measurement_identity = obj(
    {
        "policy_id": string(200),
        "policy_version": string(50),
        "contract_digest": digest,
        "environment_digest": digest,
        "implementation_digest": digest,
        "precision": string(30),
        "operator_ids": array(string(100), 4),
        "physics_ids": array(string(100), 6),
        "scientific_limits": {"type": "null"},
        "uncertainty_policy": {"type": "null"},
        "scientifically_qualified": {"const": False},
    }
)
measurement_observation = obj(
    {
        "measurement_id": string(100),
        "candidate_value": {"type": "number"},
        "reference_value": {"type": "number"},
        "raw_absolute_error": {"type": "number", "minimum": 0},
        "normalization_scale": {"type": "number", "exclusiveMinimum": 0},
        "normalized_error": {"type": "number", "minimum": 0},
        "uncertainty": {"type": "null"},
        "scientific_limit": {"type": "null"},
        "decision": {"const": "UNRESOLVED_NO_QUALIFIED_LIMIT"},
    }
)
physics_observation = obj(
    {
        "physics_id": string(100),
        "raw_defect": {"type": "number", "minimum": 0},
        "normalization_scale": {"type": "number", "exclusiveMinimum": 0},
        "normalized_defect": {"type": "number", "minimum": 0},
        "uncertainty": {"type": "null"},
        "scientific_limit": {"type": "null"},
        "decision": {"const": "UNRESOLVED_NO_QUALIFIED_LIMIT"},
    }
)
diagnostic_item = {
    "type": "array",
    "minItems": 2,
    "maxItems": 2,
    "prefixItems": [string(200), {"anyOf": [{"type": "number"}, string(1000)]}],
    "items": False,
}
behavior_item = obj(
    {"example": string(100), "classification": string(100), "reason": string(1200)}
)
evidence_record = obj(
    {
        "schema_version": {
            "const": "carbon.goal-workbench.c05-evidence-association.v1"
        },
        "association_id": string(300),
        "workbench_request_id": string(128),
        "job_id": string(128),
        "design_id": string(128),
        "design_revision": {"type": "integer", "minimum": 1},
        "requirement_trace_ids": array(string(128), 256),
        "case_family_ids": array(string(128), 128),
        "challenge": obj({"id": string(128), "version": string(50)}),
        "template_id": string(300),
        "evidence_scope": {"const": "PUBLIC_DEVELOPMENT_ONLY"},
        "evidence_state": {
            "enum": [
                "SOURCE_MEASUREMENT_EVIDENCE_BOUND",
                "SOURCE_MEASUREMENT_EVIDENCE_NOT_EXECUTED",
            ]
        },
        "binding_status": {"enum": ["CURRENT_DESIGN_REVISION", "STALE_DESIGN_CHANGED"]},
        "source_disposition": string(100),
        "source": obj(
            {
                "fixture_id": string(160),
                "repository": {"const": "carbonphysicsai/Carbon"},
                "source_revision": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
                "implementation": string(300),
                "request_schema": {"const": "carbon.c05.burgers-measurement.v1"},
                "result_schema": {"const": "carbon.c05.burgers-measurement-result.v1"},
                "request_digest": digest,
                "result_digest": digest,
                "case_digest": digest,
                "candidate": candidate_identity,
                "reference": reference_identity,
                "measurement": measurement_identity,
            }
        ),
        "measurements": array(measurement_observation, 4),
        "physics": array(physics_observation, 6),
        "diagnostics": array(diagnostic_item, 64),
        "behavior_classification": array(behavior_item, 8),
        "limitations": array(string(1200), 32),
        "trace_state": string(150),
        "imported_artifact_digest": digest,
        "scientifically_qualified": {"const": False},
        "score_eligible": {"const": False},
        "approved": {"const": False},
        "launch_authorized": {"const": False},
    }
)
assessment_association = obj(
    {
        "job_id": string(256),
        "design_id": string(256),
        "design_revision": {"type": "integer", "minimum": 1},
    }
)
assessment_ceiling = obj(
    {
        "scientific_qualification": {"const": False},
        "rights_authorization": {"const": False},
        "fresh_execution": {"const": False},
        "score_eligibility": {"const": False},
        "protected_reuse": {"const": False},
        "launch_authorization": {"const": False},
    }
)
assessment_question = obj(
    {
        "question_id": string(256),
        "domain": {
            "enum": [
                "AUTHORING_EXPRESSIBILITY",
                "SOURCE_ARTIFACT_IDENTITY",
                "FIXED_EVIDENCE_RELATIONSHIP",
            ]
        },
        "text": string(),
        "reason_ids": array(string(256), 128),
    }
)
assessment_subject = obj(
    {
        "schema_version": {"const": "carbon.goal-workbench.assessment-subject.v1"},
        "job_id": string(128),
        "design_id": string(128),
        "design_revision": {"type": "integer", "minimum": 1},
        "route": {"enum": ROUTES},
        "scope": obj({field: string() for field in scope_fields}),
        "requirements": array(requirement, 128),
        "traces": array(trace, 256),
        "cases": array(case_family, 128),
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
        "reference_plan": obj({field: string() for field in reference_fields}),
        "evidence_bindings": array(
            obj(
                {
                    "evidence_binding_id": string(128),
                    "source_digest_or_identity": string(),
                    "originating_design_id": string(128),
                    "originating_design_revision": {"type": "integer", "minimum": 1},
                    "trace_ids": array(string(128), 256),
                    "case_family_ids": array(string(128), 128),
                }
            ),
            128,
        ),
    }
)
assessment_request = obj(
    {
        "schema_version": {
            "const": "carbon.goal-workbench.source-assessment-request.v2"
        },
        "profile_id": {"const": "burgers-dynamics-public.repository-snapshot.v1"},
        "request_id": string(256),
        "association": assessment_association,
        "subject": assessment_subject,
        "subject_digest": digest,
        "source": obj(
            {
                "implementation_id": string(),
                "authoring_result_ref": string(),
                "evidence_identity_refs": array(string(), 128),
            }
        ),
        "questions": array(assessment_question, 16),
        "permitted_information_scope": {"const": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY"},
        "requested_recipient": {"const": "github:jbequ5"},
        "expected_result_or_restart": string(),
        "authority_ceiling": assessment_ceiling,
    }
)
assessment_answer = obj(
    {
        "question_id": string(256),
        "domain": {
            "enum": [
                "AUTHORING_EXPRESSIBILITY",
                "SOURCE_ARTIFACT_IDENTITY",
                "FIXED_EVIDENCE_RELATIONSHIP",
            ]
        },
        "status": {"enum": ["ANSWERED", "PARTIAL", "UNSUPPORTED", "BLOCKED"]},
        "statement": string(),
        "addressed_reason_ids": array(string(256), 128),
        "supporting_refs": array(string(), 128),
    }
)
assessment_response = obj(
    {
        "schema_version": {
            "const": "carbon.goal-workbench.source-assessment-response.v2"
        },
        "profile_id": {"const": "burgers-dynamics-public.repository-snapshot.v1"},
        "response_id": string(256),
        "request_id": string(256),
        "request_digest": digest,
        "association": assessment_association,
        "subject_digest": digest,
        "prepared_by": string(),
        "claimed_issuer": obj(
            {
                "principal": string(256),
                "role": string(),
                "claim_basis": {
                    "enum": [
                        "PRODUCER_CLAIM_UNVERIFIED",
                        "REPOSITORY_ADOPTION_REFERENCE",
                    ]
                },
            }
        ),
        "result_kind": {
            "enum": [
                "SCOPED_ASSESSMENT",
                "PARTIAL_RESPONSE",
                "UNSUPPORTED_SCOPE",
                "NAMED_BLOCKER",
                "CORRECTION",
            ]
        },
        "answered": array(assessment_answer, 16),
        "unanswered_question_ids": array(string(256), 16),
        "source_basis": array(string(), 32),
        "limitations": array(string(), 32),
        "supersedes_response_ids": array(string(256), 16),
        "next_action": string(),
        "authority_ceiling": assessment_ceiling,
    }
)
assessment_receipt = obj(
    {
        "schema_version": {
            "const": "carbon.goal-workbench.source-assessment-receipt.v1"
        },
        "receipt_id": string(256),
        "request_id": string(256),
        "response_id": string(256),
        "profile_id": string(256),
        "snapshot_id": string(256),
        "snapshot_as_of": string(100),
        "status": {
            "enum": [
                "MATCHED_APPROVED_SOURCE_SNAPSHOT",
                "HISTORICAL_WITHDRAWN",
                "HISTORICAL_SUPERSEDED",
            ]
        },
        "answered_question_ids": array(string(256), 16),
        "remaining_question_ids": array(string(256), 16),
        "resolved_reason_ids": array(string(256), 128),
        "remaining_reason_ids": array(string(256), 128),
        "origin_verification": {"const": "CONSUMER_DERIVED_REPOSITORY_SNAPSHOT_MATCH"},
        "authority_effect": {"const": "NONE"},
    }
)
assessment_state = obj(
    {
        "schema_version": {"const": "carbon.goal-workbench.source-assessment-state.v1"},
        "current_request_id": nullable(string(256)),
        "requests": array(assessment_request, 32),
        "responses": array(
            obj(
                {
                    "response": assessment_response,
                    "raw": string(300_000),
                    "raw_sha256": digest,
                    "canonical_digest": digest,
                    "received_for_request_id": string(256),
                }
            ),
            64,
        ),
        "receipts": array(assessment_receipt, 64),
        "dispositions": array(
            obj(
                {
                    "disposition_id": string(256),
                    "receipt_id": string(256),
                    "reason_id": string(256),
                    "effect": {
                        "enum": ["TECHNICAL_REASON_RESOLVED", "RETAINED_UNRESOLVED"]
                    },
                    "basis": string(),
                }
            ),
            128,
        ),
    }
)
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
        "route_plan": route_plan,
        "measurement_evidence": array(evidence_record, 64),
        "evidence_bindings": array(evidence_binding, 128),
        "source_assessments": assessment_state,
        "handoffs": array(handoff, 128),
        "responses": array(response, 256),
        "coordination": coordination,
        "decision": obj({field: string() for field in decision_fields}),
        "change_log": array(
            obj(
                {
                    "field": string(500),
                    "kind": string(500),
                    "impact": string(1_000),
                    "domains": array({"enum": DEPENDENCY_DOMAINS}, 32),
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
        "accountable_owner": string(300),
        "lead": string(300),
        "working_design_id": nullable(string(128)),
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
        "intake_records": array({"$ref": "#/$defs/intake_record"}, 64),
        "designs": array(design, 64),
        "created_from": {"enum": ["DIRECT_INTAKE", "ASSISTED_INTAKE", "MIGRATED"]},
    }
)
component = json.loads(
    (ROOT / "data/workspace.schema.json").read_text(encoding="utf-8")
)
text_answer = obj(
    {
        "state": {"enum": ["UNKNOWN", "VALUE"]},
        "value": string(),
        "origin": {"const": "USER_ENTERED_LOCAL"},
    }
)
quantity_answer = obj(
    {
        "state": {"enum": ["UNKNOWN", "POINT", "RANGE"]},
        "value": nullable({"type": "number"}),
        "minimum": nullable({"type": "number"}),
        "maximum": nullable({"type": "number"}),
        "unit": string(120),
        "note": string(1_000),
        "origin": {"const": "USER_ENTERED_LOCAL"},
    }
)
text_fields = [
    "intended_decision",
    "requested_result",
    "current_baseline",
    "baseline_limitation",
    "changing_conditions",
    "exclusions",
    "consequential_error",
    "comparison_evidence",
    "access_limitations",
]
quantity_fields = [
    "preparation_time",
    "prediction_latency",
    "reference_query_time",
    "workload_frequency",
    "desired_accuracy",
]
intake_draft = obj(
    {
        "schema_version": {"const": "carbon.client-intake.draft.v1"},
        "draft_id": string(128),
        "revision_id": string(128),
        "predecessor": nullable(
            obj(
                {
                    "draft_id": string(128),
                    "revision_id": string(128),
                    "canonical_digest": {
                        "type": "string",
                        "pattern": "^sha256:[0-9a-f]{64}$",
                    },
                }
            )
        ),
        "answers": obj({field: text_answer for field in text_fields}),
        "quantities": obj({field: quantity_answer for field in quantity_fields}),
        "summary": obj(
            {
                "mapping_version": {"const": "carbon.client-intake.mapping.v1"},
                "text": string(24_000),
                "unknown_fields": array({"enum": text_fields + quantity_fields}, 32),
                "next_clarification": string(1_000),
            }
        ),
        "source": obj(
            {
                "application": {"const": "Carbon Client Intake Preview"},
                "mapping_version": {"const": "carbon.client-intake.mapping.v1"},
                "local_scope": {"const": "LOCAL_SYNTHETIC_DEVELOPMENT_NOT_TRANSMITTED"},
            }
        ),
    }
)
intake_record = obj(
    {
        "draft_id": string(128),
        "revision_id": string(128),
        "predecessor_canonical_digest": nullable(
            {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
        ),
        "raw_sha256": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
        "canonical_digest": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
        "raw_json": string(120_000),
        "validated_draft": {"$ref": "#/$defs/intake_draft"},
        "mapped_requirement_ids": array(string(128), 16),
        "import_status": {"const": "IMPORTED_LOCAL_ASSERTION"},
    }
)
schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Carbon goal-to-Challenge workbench workspace v0.8",
    "$comment": (
        "Closed browser-local planning schema. Derived results are recomputed. "
        "It grants no scientific, security, rights, reuse, submission, execution, or launch authority."
    ),
    "$defs": {
        "opportunity_workspace_v02": component,
        "intake_draft": intake_draft,
        "intake_record": intake_record,
    },
    **obj(
        {
            "schema_version": {"const": WORKSPACE},
            "application_version": {"const": APP},
            "decision_id": {"const": "GOAL-WORKBENCH-08"},
            "base_application_merge": {"const": BASE},
            "opportunity_workspace": {"$ref": "#/$defs/opportunity_workspace_v02"},
            "jobs": array(job, 64),
            "selected_job_id": nullable(string(128)),
            "selected_design_id": nullable(string(128)),
            "migration_receipts": array(
                obj(
                    {
                        "from": string(200),
                        "to": {
                            "enum": [
                                "carbon.goal-workbench.workspace.v0.3",
                                "carbon.goal-workbench.workspace.v0.4",
                                "carbon.goal-workbench.workspace.v0.5",
                                "carbon.goal-workbench.workspace.v0.6",
                                "carbon.goal-workbench.workspace.v0.7",
                                WORKSPACE,
                            ]
                        },
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
    "ROUTES": ROUTES,
    "PROVENANCE": PROVENANCE,
    "CUSTOMER_OUTCOMES": CUSTOMER_OUTCOMES,
    "DEPENDENCY_DOMAINS": DEPENDENCY_DOMAINS,
    "SCOPE_RELATIONSHIPS": SCOPE_RELATIONSHIPS,
    "ORIGIN_VERIFICATION": ORIGIN_VERIFICATION,
}
(ROOT / "data/goal_workspace.schema.json").write_text(
    json.dumps(schema, indent=2) + "\n", encoding="utf-8"
)
(ROOT / "data/goal_constants.json").write_text(
    json.dumps(constants, indent=2) + "\n", encoding="utf-8"
)
(ROOT / "data/intake_draft.schema.json").write_text(
    json.dumps(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Carbon local client intake draft v1",
            "$comment": "Local, untrusted, non-authoritative transport. Nothing is submitted or approved.",
            **intake_draft,
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print("v0.8 goal-workbench and intake schemas generated")
