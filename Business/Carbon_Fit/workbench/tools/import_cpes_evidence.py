"""Validate pinned CPES public-safe evidence and emit the browser study record."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "cpes_reference_reuse_v2"
OUTPUT = ROOT / "data" / "cpes_study_v1.json"
INDEX_SHA256 = "4565995a98fe8f238ca88b44e418e6c7da2954de9dca577b80968854bad34ba7"
PROFILER_SHA256 = "d19b24da7f032bf13d3434c4aefdaaf77d8b35a81eead47e6674bf9d499bb116"
STUDY_ID = "EXAM-PROTECT-01-REUSE-GAUNTLET-V2"
BLOCKED = ["AT-09", "AT-16", "AT-19", "AT-22", "AT-30"]
COUNTS = {
    "REJECTED_BY_REPRODUCED_ORIGINAL_MODEL": 17,
    "REJECTED_BY_PERSISTENT_RESEARCH_PROTOTYPE": 8,
    "BLOCKED": 5,
}

CONTROLS = [
    ("P1", "Commit rules before case knowability", "Exam owner / independent audit"),
    (
        "P2",
        "Lock producer behavior and seal execution",
        "Construction / execution owners",
    ),
    ("P3", "Fix and verify private case randomness", "A4 / security owners"),
    ("P4", "Restrict case and answer custody", "Security / operations"),
    (
        "P5",
        "Bind pre-exposure membership; separate summary release from retired-answer publication",
        "Lifecycle / disclosure owners",
    ),
    ("P6", "Verify execution and scientific evidence", "Science / independent audit"),
    ("P7", "Bound admission and selection risk", "Science / operations"),
    ("P8", "Qualify attacks and response", "Security / independent reviewers"),
]

ENTRY_CONDITIONS = [
    (
        "compatibility_identity",
        "Complete compatibility identity and intended reference role",
        "Challenge / reference owner",
    ),
    (
        "compatible_dispatch_demand",
        "Arrival and admission observations showing compatible jobs coexist at dispatch",
        "Admission / operations owner",
    ),
    (
        "same_identity_reference_cost",
        "Same-identity reference cost with required evidence work and applicability limits",
        "Reference / measurement owner",
    ),
    (
        "variant_b_overhead",
        "B membership, cache, recovery, audit and closure overhead with scope",
        "Engineering / operations owner",
    ),
    (
        "field_evidence_adequacy",
        "Common-case comparison, field-size adequacy, repetitions and promotion meaning",
        "Scientific owner",
    ),
    (
        "service_envelope",
        "Acceptable feedback and unresolved-member behavior",
        "Product / service owner",
    ),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def validate() -> dict:
    index_bytes = (EVIDENCE / "evidence_index_v1.json").read_bytes()
    if sha256_bytes(index_bytes) != INDEX_SHA256:
        raise ValueError("pinned evidence index byte identity mismatch")
    index = json.loads(index_bytes)
    if index.get("schema_version") != "carbon.cpes-reuse.evidence-index.v1":
        raise ValueError("unsupported evidence index schema")
    if index.get("study_id") != STUDY_ID or len(index.get("files", {})) != 8:
        raise ValueError("evidence index study/member mismatch")
    for name, expected in index["files"].items():
        path = EVIDENCE / name
        raw = path.read_bytes()
        if len(raw) != expected["bytes"] or sha256_bytes(raw) != expected["sha256"]:
            raise ValueError(f"evidence member mismatch: {name}")
    if index["files"]["profiler_summary_v1.json"]["sha256"] != PROFILER_SHA256:
        raise ValueError("profiler summary pin mismatch")

    attacks = load("attack_dispositions_v2.json")
    if not isinstance(attacks, list) or len(attacks) != 30:
        raise ValueError("attack register must contain 30 rows")
    ids = [row.get("attack_id") for row in attacks]
    if len(set(ids)) != 30 or ids != [f"AT-{n:02d}" for n in range(1, 31)]:
        raise ValueError("attack IDs are missing, duplicated, or reordered")
    counts = Counter(row.get("current_disposition") for row in attacks)
    if dict(counts) != COUNTS:
        raise ValueError("attack disposition counts disagree with the pinned study")
    blocked = [
        row["attack_id"] for row in attacks if row["current_disposition"] == "BLOCKED"
    ]
    if blocked != BLOCKED:
        raise ValueError("blocked-attack identity mismatch")

    study = load("study_summary_v1.json")
    profiler = load("profiler_summary_v1.json")
    source = load("source_manifest_v1.json")
    cost = load("cost_delay_analysis_v1.json")
    adaptive = load("adaptive_bank_control_v1.json")
    persistent = load("persistent_probes_v1.json")
    expected_schemas = {
        "study": "carbon.cpes-reuse.study-summary.v1",
        "profiler": "carbon.challenge-profiler.cpes-reuse-study.v1",
        "source": "carbon.cpes-reuse.source-manifest.v1",
        "cost": "carbon.cpes-reuse.cost-delay-study.v1",
        "adaptive": "carbon.cpes-reuse.adaptive-bank-control.v1",
        "persistent": "carbon.cpes-reuse.persistent-probes.v1",
    }
    for label, payload in (
        ("study", study),
        ("profiler", profiler),
        ("source", source),
        ("cost", cost),
        ("adaptive", adaptive),
        ("persistent", persistent),
    ):
        if payload.get("schema_version") != expected_schemas[label]:
            raise ValueError(f"unsupported {label} evidence schema")
    trace_lines = (
        (EVIDENCE / "attack_traces_v2.jsonl").read_text(encoding="utf-8").splitlines()
    )
    try:
        traces = [json.loads(line) for line in trace_lines]
    except json.JSONDecodeError as error:
        raise ValueError("invalid attack trace JSONL") from error
    if len(traces) != 12 or any(
        "probe" not in row or "evidence_layer" not in row for row in traces
    ):
        raise ValueError("attack trace structure mismatch")
    if (
        source.get("source_revision") != index["source_revision"]
        or source.get("study_id") != STUDY_ID
    ):
        raise ValueError("source-manifest revision/study mismatch")
    if not persistent.get("research_only") or persistent.get("production_authority"):
        raise ValueError("persistent probes must remain research-only")
    if (
        study["recommendation"] != profiler["recommendation"]
        or study["recommendation"] != "RETAIN_A"
    ):
        raise ValueError("recommendation mismatch")
    if study["attack_counts"] != {
        "BLOCKED": 5,
        "REJECTED_BY_PERSISTENT_RESEARCH_PROTOTYPE": 8,
        "REJECTED_BY_REPRODUCED_ORIGINAL_MODEL": 17,
    }:
        raise ValueError("summary counts mismatch")
    if (
        study["blocked_attack_ids"] != BLOCKED
        or profiler["protection_blockers"] != BLOCKED
    ):
        raise ValueError("summary blocker mismatch")
    if profiler["categories"].get("qualified_carbon_evidence") is not None:
        raise ValueError("qualified_carbon_evidence must remain null")
    if any(
        (
            study["production_authority"],
            study["runtime_sharing_implemented"],
            profiler["runtime_sharing_authorized"],
        )
    ):
        raise ValueError("research evidence must not carry runtime authority")
    if (
        cost.get("schema_version") != "carbon.cpes-reuse.cost-delay-study.v1"
        or len(cost.get("rows", [])) != 45
    ):
        raise ValueError("cost/delay row schema mismatch")
    if not cost.get("membership_recomputed_per_overhead"):
        raise ValueError("dynamic rows must recompute membership per overhead")
    for row in cost["rows"]:
        if row.get("evidence_class") != "COUNTERFACTUAL_MODEL":
            raise ValueError("unexpected cost-row evidence class")
        if row.get("variant") not in {"A", "B", "C"}:
            raise ValueError("unexpected cost-row variant")
        if not row.get("one_validator_serial_resource"):
            raise ValueError("cost rows must retain the one-validator resource scope")
        if row.get("uses_future_information"):
            raise ValueError("cost rows must not use future information")
        if row.get("schema_version") != "carbon.cpes-reuse.operating-replay.v1":
            raise ValueError("unexpected operating-replay row schema")
        work = row.get("work", {})
        if set(work) != {
            "candidate",
            "reference",
            "group_control",
            "evidence_closure",
            "failed_cancelled_unresolved",
        }:
            raise ValueError("cost-row work scopes are incomplete")
        if sum(work.values()) != row.get("total_recurring_work"):
            raise ValueError("cost-row recurring-work total mismatch")
    if adaptive != {
        **adaptive,
        "whole_cases": 32,
        "queries": 33,
        "recovered_bank_exactly": True,
        "reused_bank_accuracy": 1.0,
        "independent_holdout_accuracy": 0.46875,
    }:
        raise ValueError("adaptive negative-control quantities mismatch")

    return {
        "schema_version": "carbon.workbench.cpes-study.v1",
        "study_id": STUDY_ID,
        "evidence_version": "ca904dfee93d3574df4e56b99981a6ed3b138e80",
        "recommendation": "RETAIN_A",
        "recommendation_date": "2026-09-13",
        "current_baseline": {
            "variant": "A",
            "environment": "DEVELOPMENT",
            "description": "Fresh pack for each separately admitted job, private evidence, and pack-closure summaries.",
            "official_exam_qualified": False,
            "editable": False,
        },
        "variant_b": {
            "status": "CONDITIONAL_FUTURE_RESEARCH_OPTION",
            "description": "Compatible already-committed queued jobs; no intentional fill wait, early summary, answer publication, or new reward route in the minimal proposed design.",
            "runtime_implemented": False,
            "activation_authorized": False,
        },
        "variant_c": "RESEARCH_SENSITIVITY_ONLY_NOT_RECOMMENDED",
        "negative_control_policy_status": "VULNERABLE_NEGATIVE_CONTROL_ONLY_NOT_AN_OPERATING_OPTION",
        "categories": profiler["categories"],
        "provenance": {
            "research_baseline_revision": index["source_revision"],
            "study_implementation_revision": None,
            "study_implementation_limitation": "The evidence names source/file hashes but no distinct executed-study implementation commit; no SHA is fabricated.",
            "packaging_revision": "ca904dfee93d3574df4e56b99981a6ed3b138e80",
            "integration_revision": "ab1331e2d7e8ed390bd136e888f05f33d02f275f",
            "evidence_index_sha256": INDEX_SHA256,
            "profiler_summary_sha256": PROFILER_SHA256,
            "raw_source_reference": "docs/development/cpes_reference_reuse_gauntlet_evidence_v2/evidence_index_v1.json",
            "delivery": {
                "checked_at": "2026-09-14",
                "pr": 152,
                "state": "MERGED_ACCEPTED",
                "pinned_reviewed_head": "ca904dfee93d3574df4e56b99981a6ed3b138e80",
                "accepted_head": "0a5690270dc449ea19c941280203987d37db5283",
                "merge_commit": "2ac835d1dd55deb9c99e493f3615143efa2e51e0",
                "acceptance_run": 34786945000,
                "historical_failed_run": 34778525936,
                "canonical_environment": "PASSED",
                "clean_image": "PASSED",
                "merge_gate": "PASSED",
            },
            "historical_results": {
                "original_extracted_harness_tests": 26,
                "new_focused_tests": 14,
                "combined_continuation_c_ep_regressions": 52,
                "invariants": 208,
                "sets_overlap_do_not_sum": True,
            },
            "source_manifest": source,
            "member_hashes": index["files"],
        },
        "attack_counts": study["attack_counts"],
        "blocked_attack_ids": BLOCKED,
        "attacks": attacks,
        "controls": [
            {"id": cid, "label": label, "owner": owner}
            for cid, label, owner in CONTROLS
        ],
        "entry_conditions": [
            {"id": cid, "question": label, "default_owner": owner}
            for cid, label, owner in ENTRY_CONDITIONS
        ],
        "adaptive_negative_control": adaptive,
        "observations": {
            "c03_linux_worker_total": {
                "value": profiler["observed_components"]["c03_foundax_worker_total_ms"],
                "unit": "ms wall latency",
                "scope": "C-03 Linux worker observation",
                "status": "observed",
                "environment": "Linux worker; exact report pin in source manifest",
            },
            "c_ep3_public_reference_warm": {
                "value": profiler["observed_components"][
                    "c_ep3_public_reference_warm_ms"
                ],
                "unit": "ms wall latency",
                "scope": "one C-EP3 public physical case",
                "status": "observed",
                "environment": "Apple M3; exact source pin in source manifest",
            },
            "cross_hardware_composition_permitted": False,
        },
        "quantity_unknowns": {
            "scientifically_adequate_reference_cost": None,
            "compatible_demand": None,
            "variant_b_overhead": None,
            "field_dependent_evidence": None,
            "acceptable_service_delay": None,
        },
        "fixed_membership_vectors": cost["fixed_membership_sanity"],
        "dynamic": {
            "units": {
                "work": "synthetic matched-work units",
                "time": "synthetic time units",
            },
            "rows": cost["rows"],
            "counterexample": {
                "arrivals": {"a": 0, "b": 13, "c": 14, "d": 15},
                "h0": {
                    "groups": [["a"], ["b"], ["c", "d"]],
                    "work": 38,
                    "c_d_release": 39,
                },
                "h4": {
                    "groups": [["a"], ["b", "c", "d"]],
                    "work": 36,
                    "c_d_release": 36,
                },
                "status": "PINNED_TEST_VECTOR_NOT_A_PRODUCTION_RECOMMENDATION",
            },
        },
        "source_precedence": [
            {"order": 1, "source": "Current repository contracts", "role": "Authority"},
            {
                "order": 2,
                "source": "PR #152 pinned research head",
                "role": "Displayed research findings",
            },
            {
                "order": 3,
                "source": "EXAM-PROTECT-WORKBENCH-01 assignment",
                "role": "Bounded UI integration",
            },
            {
                "order": 4,
                "source": "User inputs/imports",
                "role": "Unreviewed scenario assumptions",
            },
        ],
        "authority_disclaimer": "Planning evidence only. This record cannot qualify an exam, approve protected use, authorize reference sharing or publication, activate runtime behavior, or grant rights.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(validate(), indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit("generated CPES study record is stale")
        print("CPES evidence verified; generated record is current")
        return
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
