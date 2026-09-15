"""Build the closed GOAL-WORKBENCH-07 repository-snapshot schemas."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "source_assessment/repository_snapshot/v1/schemas"
PROFILE = "burgers-dynamics-public.repository-snapshot.v1"


def closed(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required or list(properties),
        "properties": properties,
    }


def string(maximum: int = 8000, *, empty: bool = True) -> dict:
    result = {"type": "string", "maxLength": maximum}
    if not empty:
        result["minLength"] = 1
    return result


ID = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$"}
DIGEST = {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$"}
REVISION = {"type": "integer", "minimum": 1}


def array(items: dict, maximum: int = 128, minimum: int = 0) -> dict:
    return {
        "type": "array",
        "items": items,
        "minItems": minimum,
        "maxItems": maximum,
    }


CEILING = closed(
    {
        "scientific_qualification": {"const": False},
        "rights_authorization": {"const": False},
        "fresh_execution": {"const": False},
        "score_eligibility": {"const": False},
        "protected_reuse": {"const": False},
        "launch_authorization": {"const": False},
    }
)
ASSOCIATION = closed({"job_id": ID, "design_id": ID, "design_revision": REVISION})
REASON = closed(
    {
        "reason_id": ID,
        "domain": string(256, empty=False),
        "field": string(500),
        "originating_design_id": ID,
        "originating_revision": REVISION,
        "basis": string(2000),
    }
)
SCOPE_KEYS = [
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
SCOPE = closed({key: string() for key in SCOPE_KEYS})
REQUIREMENT = closed(
    {
        "requirement_id": ID,
        "original_words": string(),
        "source_reference": string(),
        "decision_consequence": string(),
        "kind": string(256),
        "agreement_status": string(256),
    }
)
TRACE_KEYS = [
    "observable",
    "requested_output",
    "measurement_definition",
    "numerical_method",
    "role",
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
TRACE = closed(
    {"trace_id": ID, "requirement_id": ID, **{key: string() for key in TRACE_KEYS}}
)
CASE = closed(
    {
        "case_family_id": ID,
        "role": string(256),
        "requirement_ids": array(ID, 64),
        "target_population": string(),
        "target_mass": string(),
        "sampling_frequency": string(),
        "analysis_weight": string(),
        "independent_physical_cases": string(),
        "reconstruction_replicas": string(),
        "generator_ref": string(),
        "rationale": string(),
        "support_status": string(256),
    }
)
SEMANTIC_RECEIPT = closed(
    {
        "schema_version": {"const": "carbon.goal-workbench.semantic-receipt.v1"},
        "request_id": ID,
        "job_id": ID,
        "design_id": ID,
        "design_revision": REVISION,
        "input_digest": string(1000, empty=False),
        "proposal_digest": string(1000, empty=False),
        "status": {"enum": ["INTENT_PRESERVED", "INTENT_MISMATCH"]},
        "qualification": {"const": "NOT_QUALIFIED"},
        "launch": {"const": "NOT_LAUNCHED"},
    }
)
EXTENSION = closed(
    {
        "schema_version": {"const": "carbon.goal-workbench.authoring-extension.v1"},
        "request_id": ID,
        "job_id": ID,
        "design_id": ID,
        "design_revision": REVISION,
        "missing_capability": string(),
        "client_rationale": string(),
        "compatible_existing_components": string(),
        "proposed_tests": string(),
        "unresolved_scientific_choices": string(),
        "owner_interface": string(),
    }
)
AUTHORING = closed(
    {
        "template_id": string(1000),
        "requested_goal": string(1000),
        "compatibility": string(1000),
        "request_id": string(1000),
        "result_ref": string(1000),
        "semantic_receipt": {"oneOf": [{"type": "null"}, SEMANTIC_RECEIPT]},
        "extension_request": {"oneOf": [{"type": "null"}, EXTENSION]},
    }
)
REFERENCE_KEYS = [
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
REFERENCE = closed({key: string() for key in REFERENCE_KEYS})
BINDING = closed(
    {
        "evidence_binding_id": ID,
        "source_digest_or_identity": string(1000),
        "originating_design_id": ID,
        "originating_design_revision": REVISION,
        "trace_ids": array(string(1000, empty=False)),
        "case_family_ids": array(string(1000, empty=False)),
        "dependency_domains": array(string(1000, empty=False)),
        "scientific_applicability": string(1000, empty=False),
        "scientific_review_reasons": array(REASON),
        "use_or_rights_status": string(1000, empty=False),
        "rights_review_reasons": array(REASON),
    }
)
SUBJECT = closed(
    {
        "schema_version": {"const": "carbon.goal-workbench.assessment-subject.v1"},
        "job_id": ID,
        "design_id": ID,
        "design_revision": REVISION,
        "route": string(1000, empty=False),
        "scope": SCOPE,
        "requirements": array(REQUIREMENT),
        "traces": array(TRACE, 256),
        "cases": array(CASE),
        "authoring": AUTHORING,
        "reference_plan": REFERENCE,
        "evidence_bindings": array(BINDING),
    }
)
QUESTION = closed(
    {
        "question_id": ID,
        "domain": {
            "enum": [
                "AUTHORING_EXPRESSIBILITY",
                "SOURCE_ARTIFACT_IDENTITY",
                "FIXED_EVIDENCE_RELATIONSHIP",
            ]
        },
        "text": string(empty=False),
        "reason_ids": array(ID),
    }
)
REQUEST = closed(
    {
        "schema_version": {
            "const": "carbon.goal-workbench.source-assessment-request.v2"
        },
        "profile_id": {"const": PROFILE},
        "request_id": ID,
        "association": ASSOCIATION,
        "subject": SUBJECT,
        "subject_digest": DIGEST,
        "source": closed(
            {
                "implementation_id": string(1000, empty=False),
                "authoring_result_ref": string(1000, empty=False),
                "evidence_identity_refs": array(string(1000, empty=False)),
            }
        ),
        "questions": array(QUESTION, 16, 1),
        "permitted_information_scope": {"const": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY"},
        "requested_recipient": {"const": "github:jbequ5"},
        "expected_result_or_restart": string(empty=False),
        "authority_ceiling": CEILING,
    }
)
ANSWER = closed(
    {
        "question_id": ID,
        "domain": QUESTION["properties"]["domain"],
        "status": {"enum": ["ANSWERED", "PARTIAL", "UNSUPPORTED", "BLOCKED"]},
        "statement": string(empty=False),
        "addressed_reason_ids": array(ID),
        "supporting_refs": array(string(8000, empty=False)),
    }
)
RESPONSE = closed(
    {
        "schema_version": {
            "const": "carbon.goal-workbench.source-assessment-response.v2"
        },
        "profile_id": {"const": PROFILE},
        "response_id": ID,
        "request_id": ID,
        "request_digest": DIGEST,
        "association": ASSOCIATION,
        "subject_digest": DIGEST,
        "prepared_by": string(empty=False),
        "claimed_issuer": closed(
            {
                "principal": ID,
                "role": string(1000, empty=False),
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
        "answered": array(ANSWER, 16),
        "unanswered_question_ids": array(ID, 16),
        "source_basis": array(string(8000, empty=False), 32),
        "limitations": array(string(8000, empty=False), 32),
        "supersedes_response_ids": array(ID, 16),
        "next_action": string(empty=False),
        "authority_ceiling": CEILING,
    }
)
PROFILE_SCHEMA = closed(
    {
        "schema_version": {
            "const": "carbon.goal-workbench.repository-snapshot-profile.v1"
        },
        "profile_id": {"const": PROFILE},
        "policy_decision_id": {"const": "OWNER-GW07-RYAN-SNAPSHOT-01"},
        "verifier_implementation_id": ID,
        "issuer_policy": closed(
            {
                "principal": {"const": "github:jbequ5"},
                "role": {"const": "FINAL_INTERFACE_OWNER"},
                "allowed_domains": array(QUESTION["properties"]["domain"]),
                "adoption_required": {"const": True},
            }
        ),
        "supported_scope": closed(
            {
                "physics_family": {"const": "periodic_viscous_burgers_1d_v1"},
                "goal": {"const": "Dynamics"},
                "information_scope": {"const": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY"},
            }
        ),
        "trust_assumptions": array(string(8000, empty=False), 16),
        "snapshot_id": ID,
        "snapshot_as_of": string(1000, empty=False),
        "test_only": {"type": "boolean"},
    }
)
ENTRY = closed(
    {
        "assessment_id": ID,
        "request_id": ID,
        "request_digest": DIGEST,
        "subject_digest": DIGEST,
        "response_raw_sha256": DIGEST,
        "response_canonical_digest": DIGEST,
        "issuer_principal": ID,
        "allowed_domains": array(QUESTION["properties"]["domain"]),
        "owner_adoption_ref": ID,
        "owner_adoption_content_digest": DIGEST,
        "state": {"enum": ["CURRENT", "WITHDRAWN", "SUPERSEDED", "CONFLICTING"]},
        "withdrawn_reason": string(2000),
        "supersedes_assessment_ids": array(ID, 16),
        "conflicts_with_assessment_ids": array(ID, 16),
    }
)
INDEX = closed(
    {
        "schema_version": {
            "const": "carbon.goal-workbench.approved-assessment-snapshot.v1"
        },
        "snapshot_id": ID,
        "test_only": {"type": "boolean"},
        "entries": array(ENTRY),
    }
)
RECEIPT = closed(
    {
        "schema_version": {
            "const": "carbon.goal-workbench.source-assessment-receipt.v1"
        },
        "receipt_id": ID,
        "request_id": ID,
        "response_id": ID,
        "profile_id": ID,
        "snapshot_id": ID,
        "snapshot_as_of": string(1000, empty=False),
        "status": {
            "enum": [
                "MATCHED_APPROVED_SOURCE_SNAPSHOT",
                "HISTORICAL_WITHDRAWN",
                "HISTORICAL_SUPERSEDED",
            ]
        },
        "answered_question_ids": array(ID),
        "remaining_question_ids": array(ID),
        "resolved_reason_ids": array(ID),
        "remaining_reason_ids": array(ID),
        "origin_verification": {"const": "CONSUMER_DERIVED_REPOSITORY_SNAPSHOT_MATCH"},
        "authority_effect": {"const": "NONE"},
    }
)


def document(schema_id: str, body: dict) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_id,
        **body,
    }


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    schemas = {
        "request.schema.json": document(
            REQUEST["properties"]["schema_version"]["const"], REQUEST
        ),
        "response.schema.json": document(
            RESPONSE["properties"]["schema_version"]["const"], RESPONSE
        ),
        "profile.schema.json": document(
            PROFILE_SCHEMA["properties"]["schema_version"]["const"], PROFILE_SCHEMA
        ),
        "approved_index.schema.json": document(
            INDEX["properties"]["schema_version"]["const"], INDEX
        ),
        "receipt.schema.json": document(
            RECEIPT["properties"]["schema_version"]["const"], RECEIPT
        ),
    }
    for name, schema in schemas.items():
        (OUT / name).write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
