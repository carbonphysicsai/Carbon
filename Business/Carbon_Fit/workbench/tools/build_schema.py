"""Generate the closed v0.2 workspace schema and engine-constant snapshot."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATLAS = json.loads((ROOT / "data/atlas.json").read_text())
IDS = [item["id"] for item in ATLAS["opportunities"]]
VERSION = "carbon_workbench_draft_v0.2"
WORKSPACE = "carbon_workbench_workspace_v0.2"
APP = "Carbon Opportunity Workbench v0.2"
CHECKS = ["job_access", "reference", "reconstruction", "exam", "deployment", "value"]
STATES = ["UNKNOWN", "SUPPORTED_FOR_STAGE", "BLOCKED_FOR_SCOPE"]
PLANNING = [
    "UNREVIEWED",
    "INVESTIGATE",
    "PILOT_PROPOSAL",
    "PARTNER_DEPENDENT",
    "PARKED",
    "DECLINE_CURRENT_SCOPE",
]
INPUTS = [
    "hardware",
    "daily_pool_hours",
    "supply_per_day",
    "repetitions",
    "train_ref_lo",
    "train_ref_hi",
    "rebuild_lo",
    "rebuild_hi",
    "eval_lo",
    "eval_hi",
    "overhead_lo",
    "overhead_hi",
    "promotion_lo",
    "promotion_hi",
    "ref_lo",
    "ref_hi",
    "cohort",
    "qualification_cost",
    "qualification_currency",
    "qualification_days",
    "qualification_risk",
    "baseline_latency_ms",
    "required_latency_ms",
]
BRIEF = [
    "job",
    "output",
    "context",
    "baseline",
    "reference_access",
    "accuracy",
    "latency",
    "volume",
    "budget",
    "timing",
    "privacy",
    "contact",
    "notes",
]
ROLES = [
    "verification",
    "training_data",
    "routine_exam",
    "independent_witness",
    "physical_anchor",
    "protected_audit",
]
CONTROL_IDS = [f"P{i}" for i in range(1, 9)]
BLOCKER_IDS = ["AT-09", "AT-16", "AT-19", "AT-22", "AT-30"]
REVIEW_FIELDS = [
    "source_reference",
    "reviewer_notes",
    "measurement_method",
    "unresolved_assumptions",
]
ECON_FIELDS = [
    "reference_work",
    "group_overhead",
    "group_size",
    "unit",
    "unit_scope",
    "reference_status",
    "overhead_status",
    "group_size_status",
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
GAP_IDS = [
    "compatibility_identity",
    "compatible_dispatch_demand",
    "same_identity_reference_cost",
    "variant_b_overhead",
    "field_evidence_adequacy",
    "service_envelope",
]
GAP_FIELDS = REVIEW_FIELDS + [
    "source_owner",
    "smallest_observation",
    "why_decision_changes",
]
QUANTITY_STATUS = [
    "unknown",
    "observed",
    "source_estimated",
    "user_assumed",
    "simulated",
]
ECON_UNITS = [
    "",
    "synthetic work units",
    "CPU seconds — same profile",
    "GPU seconds — same profile",
    "explicit currency rate/basis",
    "other named matched unit",
]


def string(maximum=8000):
    return {"type": "string", "maxLength": maximum}


def obj(properties):
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


review = lambda extra: obj({**extra, **{field: string() for field in REVIEW_FIELDS}})
legacy = obj(
    {
        "status": {"const": "LEGACY_HYPOTHETICAL_SHARING_SCENARIO"},
        "cohort": string(),
        "ref_lo": string(),
        "ref_hi": string(),
        "hardware": string(),
        "note": string(),
    }
)
receipt = obj(
    {
        "from": {"const": "carbon_workbench_draft_v0.1"},
        "to": {"const": VERSION},
        "original_sha256": string(64),
        "digest_status": {"enum": ["VERIFIED_WEB_CRYPTO", "UNAVAILABLE"]},
        "semantic_changes": {"type": "array", "maxItems": 12, "items": string(500)},
    }
)
draft = obj(
    {
        "schema_version": {"const": VERSION},
        "opportunity_id": {"enum": IDS},
        "source_sha256": {"const": ATLAS["source"]["sha256"]},
        "planning_state": {"enum": PLANNING},
        "fit_checks": obj(
            {
                c: obj({"state": {"enum": STATES}, "evidence_note": string()})
                for c in CHECKS
            }
        ),
        "inputs": obj({field: string(300) for field in INPUTS}),
        "brief": obj({field: string() for field in BRIEF}),
        "reference_roles": {
            "type": "array",
            "uniqueItems": True,
            "maxItems": 6,
            "items": {"enum": ROLES},
        },
        "reference_architecture": obj(
            {
                role: obj(
                    {
                        "family": string(),
                        "implementation_scope": string(),
                        "evidence_note": string(),
                    }
                )
                for role in ROLES
            }
        ),
        "next_test": string(),
        "study_refs": {"type": "array", "maxItems": 100, "items": string(200)},
        "review_note": string(),
        "protection": obj(
            {
                "controls": obj(
                    {
                        cid: review(
                            {
                                "state": {
                                    "enum": [
                                        "UNASSESSED",
                                        "EVIDENCE_ASSEMBLED",
                                        "BLOCKED",
                                    ]
                                }
                            }
                        )
                        for cid in CONTROL_IDS
                    }
                ),
                "blockers": obj(
                    {
                        bid: review(
                            {
                                "applicability": {
                                    "enum": [
                                        "UNKNOWN",
                                        "APPLICABLE",
                                        "NOT_APPLICABLE_ASSERTED",
                                    ]
                                }
                            }
                        )
                        for bid in BLOCKER_IDS
                    }
                ),
                "publication_review": obj(
                    {
                        "desired_future_feature": {"const": True},
                        "rights_notes": string(),
                        "retirement_notes": string(),
                        "status": {"const": "DEFERRED_NOT_IMPLEMENTED"},
                    }
                ),
            }
        ),
        "reference_economics": obj(
            {
                field: (
                    {"enum": QUANTITY_STATUS}
                    if field
                    in [
                        "reference_status",
                        "overhead_status",
                        "group_size_status",
                        "compatible_demand_status",
                    ]
                    else (
                        {"enum": ["UNKNOWN", "YES", "NO"]}
                        if field == "field_dependent"
                        else {"enum": ECON_UNITS} if field == "unit" else string(300)
                    )
                )
                for field in ECON_FIELDS
            }
        ),
        "dynamic_scenario": obj({"scenario": string(100), "overhead": string(30)}),
        "next_evidence": obj(
            {gap: obj({field: string() for field in GAP_FIELDS}) for gap in GAP_IDS}
        ),
        "legacy_sharing_scenario": {"anyOf": [{"type": "null"}, legacy]},
        "migration_receipt": {"anyOf": [{"type": "null"}, receipt]},
        "evidence_status": {"const": "USER_ENTERED_UNREVIEWED"},
        "qualification_status": {"const": "NOT_QUALIFIED_BY_THIS_TOOL"},
        "submission_status": {"const": "NOT_SENT"},
        "reuse_permission": {"const": "NOT_GRANTED"},
    }
)
claim = obj(
    {
        "schema_version": {"const": "carbon.workbench.cpes-study-import.v1"},
        "study_id": string(300),
        "evidence_version": string(300),
        "recommendation": string(300),
        "source_reference": string(300),
        "delivery_status": string(300),
        "qualified_carbon_evidence": {"type": "null"},
        "content_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    }
)
workspace_receipt = obj(
    {
        "from": {"const": "carbon_workbench_workspace_v0.1"},
        "to": {"const": WORKSPACE},
        "original_sha256": string(64),
        "digest_status": {"enum": ["VERIFIED_WEB_CRYPTO", "UNAVAILABLE"]},
        "semantic_changes": {"type": "array", "maxItems": 12, "items": string(500)},
    }
)
schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Carbon offline opportunity workbench workspace v0.2",
    "$comment": "Planning artifact only. Derived recommendations are recomputed by engine.js. This schema grants no runtime, evidence, qualification, submission, or reuse authority.",
    **obj(
        {
            "schema_version": {"const": WORKSPACE},
            "application_version": {"const": APP},
            "source_sha256": {"const": ATLAS["source"]["sha256"]},
            "evidence_catalog": {"type": "array", "maxItems": 16, "items": claim},
            "drafts": {"type": "array", "maxItems": 64, "items": draft},
            "shortlist": {
                "type": "array",
                "maxItems": 3,
                "uniqueItems": True,
                "items": {"enum": IDS},
            },
            "migration_receipts": {
                "type": "array",
                "maxItems": 65,
                "items": workspace_receipt,
            },
        }
    ),
}
constants = {
    "VERSION": VERSION,
    "WORKSPACE_VERSION": WORKSPACE,
    "APP_VERSION": APP,
    "CHECKS": CHECKS,
    "STATES": STATES,
    "PLANNING": PLANNING,
    "INPUTS": INPUTS,
    "BRIEF": BRIEF,
    "ROLES": ROLES,
    "CONTROL_IDS": CONTROL_IDS,
    "BLOCKER_IDS": BLOCKER_IDS,
    "ECON_UNITS": ECON_UNITS,
    "ECON_FIELDS": ECON_FIELDS,
    "GAP_IDS": GAP_IDS,
    "QUANTITY_STATUS": QUANTITY_STATUS,
}
(ROOT / "data/workspace.schema.json").write_text(json.dumps(schema, indent=2) + "\n")
(ROOT / "data/draft_constants.json").write_text(json.dumps(constants, indent=2) + "\n")
print("v0.2 schema and constants generated")
