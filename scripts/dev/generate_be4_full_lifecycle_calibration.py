#!/usr/bin/env python3
"""Generate frozen, full-lifecycle, non-qualifying B-E4 calibration evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CPU_FIXTURE_ROOT = REPOSITORY_ROOT / "tests" / "cpu"
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

FREEZE_PATH = (
    REPOSITORY_ROOT
    / ".agent"
    / "preregistrations"
    / "B-E4_full_lifecycle_calibration_v1.json"
)
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / ".agent"
    / "evidence"
    / "wave_b"
    / "b-e4-full-lifecycle-calibration-v1.json"
)
SCHEMA_VERSION = "carbon.be4.full-lifecycle-calibration.v1"
EVIDENCE_ROLE = "NONQUALIFYING_FULL_LIFECYCLE_CALIBRATION_RAW"
AUTHORITY_CEILING = "DESIGN_ANALYSIS_REHEARSAL_EVIDENCE_ONLY_NOT_QUALIFYING_EVIDENCE"
PRIMARY_BLOCKS_PER_PROFILE = 5
RESERVE_BLOCKS_PER_PROFILE = 1
CAMPAIGN_ID = "be4-full-lifecycle-calibration-v1"
STOPPING_RULE = "ATTEMPT_EVERY_PROSPECTIVE_PRIMARY_ONCE"
FAILURE_HANDLING = "REPLACE_ONLY_INFRASTRUCTURE_OR_REFERENCE"
WALL_SECONDS = 30.0
COMPUTE_UNITS = 250.0
ATTEMPT_LIMIT = 8
FIXTURE_UNITS = 223
_MANIFEST_DOMAIN = b"carbon.be4.full-lifecycle-calibration-manifest.v1\x00"
_REPLAY_DOMAIN = b"carbon.be4.full-lifecycle-calibration-replay.v1\x00"
_FREEZE_DOMAIN = b"carbon.be4.full-lifecycle-calibration-freeze.v1\x00"


class FullLifecycleCalibrationError(ValueError):
    """Frozen calibration evidence is malformed or inconsistent."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise FullLifecycleCalibrationError("content is not canonical JSON") from exc


def _domain_digest(domain: bytes, value: object) -> str:
    return "sha256:" + hashlib.sha256(domain + _canonical_bytes(value)).hexdigest()


def freeze_content_digest(value: dict[str, Any]) -> str:
    projected = copy.deepcopy(value)
    projected.pop("content_digest", None)
    return _domain_digest(_FREEZE_DOMAIN, projected)


def manifest_content_digest(value: dict[str, Any]) -> str:
    projected = copy.deepcopy(value)
    projected.pop("content_digest", None)
    return _domain_digest(_MANIFEST_DOMAIN, projected)


def replay_stable_digest(value: dict[str, Any]) -> str:
    projected = copy.deepcopy(value)
    projected.pop("content_digest", None)
    projected.pop("replay_stable_digest", None)
    for row in projected["rows"]:
        row.pop("wall_seconds", None)
    for profile in projected["summary"]["profiles"]:
        profile.pop("wall_p99_seconds", None)
        profile.pop("observed_wall_seconds", None)
    projected["summary"].pop("observed_wall_seconds", None)
    return _domain_digest(_REPLAY_DOMAIN, projected)


def render_manifest(value: dict[str, Any]) -> str:
    validate_manifest(value)
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _source_digest() -> str:
    return "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def load_freeze(path: Path = FREEZE_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FullLifecycleCalibrationError("cannot load calibration freeze") from exc
    expected = {
        "schema_version": "carbon.be4.full-lifecycle-calibration-freeze.v1",
        "status": "FROZEN_NONQUALIFYING_CALIBRATION",
        "purpose": "CALIBRATION",
        "authority_ceiling": AUTHORITY_CEILING,
        "v3_design_digest": (
            "sha256:11a2b6b7e3817cea62631dfbdd0e5b59393d70f0cb9617776b8996ed535d1538"
        ),
        "campaign_id": CAMPAIGN_ID,
        "primary_blocks_per_profile": PRIMARY_BLOCKS_PER_PROFILE,
        "reserve_blocks_per_profile": RESERVE_BLOCKS_PER_PROFILE,
        "arms_per_block": 4,
        "attempt_limit": ATTEMPT_LIMIT,
        "wall_seconds_per_run": WALL_SECONDS,
        "compute_units_per_run": COMPUTE_UNITS,
        "fixture_units_per_run": FIXTURE_UNITS,
        "stopping_rule": STOPPING_RULE,
        "failure_handling": FAILURE_HANDLING,
        "qualifying_execution_ready": False,
        "attack_campaign_calls": 0,
        "shadow_case_calls": 0,
    }
    if type(value) is not dict or set(value) != {
        *expected,
        "implementation_digest",
        "generator_source_digest",
        "content_digest",
    }:
        raise FullLifecycleCalibrationError("freeze does not have its exact schema")
    if any(value[key] != item for key, item in expected.items()):
        raise FullLifecycleCalibrationError("freeze identity or boundary changed")
    if value["generator_source_digest"] != _source_digest():
        raise FullLifecycleCalibrationError("generator source is not frozen")
    from carbon.gauntlet import rehearsal_implementation_digest

    if value["implementation_digest"] != rehearsal_implementation_digest():
        raise FullLifecycleCalibrationError("rehearsal implementation is not frozen")
    if value["content_digest"] != freeze_content_digest(value):
        raise FullLifecycleCalibrationError("freeze digest is inconsistent")
    return value


def _load_fixture_builders() -> tuple[object, object]:
    fixture_path = str(CPU_FIXTURE_ROOT)
    if fixture_path not in sys.path:
        sys.path.insert(0, fixture_path)
    import test_be4_execution_integration as integration
    import test_be4_nonqualifying_lifecycle as lifecycle

    return integration, lifecycle


def _compute_counts(receipt: object) -> dict[str, int]:
    return {item.kind.value: item.count for item in receipt.counts}


def _sample_sd(values: list[float]) -> float:
    return 0.0 if len(values) < 2 else statistics.stdev(values)


def _nearest_rank(values: list[float], fraction: float) -> float:
    return sorted(values)[math.ceil(fraction * len(values)) - 1]


def _row(run: object, evidence: object, role: str, number: int) -> dict[str, Any]:
    counts = _compute_counts(run.normalized_compute)
    invalid = sum(not item.executable for item in run.prepared.candidates)
    first_attempt = min(item.proposal.attempt for item in run.prepared.candidates)
    return {
        "row_id": (
            f"{run.plan.identity.profile.value}:{role}:{number}:"
            f"{run.plan.identity.arm.value}"
        ),
        "profile": run.plan.identity.profile.value,
        "arm": run.plan.identity.arm.value,
        "block_id": run.plan.block_id,
        "slot_role": role,
        "slot_number": number,
        "replicate": run.plan.identity.replicate,
        "run_evidence_digest": evidence.content_digest,
        "lifecycle_digest": run.content_digest,
        "wall_seconds": run.wall_time.elapsed_seconds,
        "normalized_compute_units": run.normalized_compute.total_work_units,
        "policy_work_counts": counts,
        "service_request_count": len(run.prepared.service_request_digests)
        + 2 * len(run.practice),
        "service_reply_count": len(run.prepared.service_reply_digests)
        + 2 * len(run.practice),
        "proposal_count": len(run.prepared.proposal_batch.proposals),
        "invalid_preflight_count": invalid,
        "practice_attempt_count": len(run.practice),
        "practice_admissible": bool(run.practice),
        "selected_attempt": run.selection.selected_attempt,
        "selected_changed_from_first": run.selection.selected_attempt != first_attempt,
        "fixture_units": run.fixture_units,
        "reconstruction_succeeded": True,
        "heldout_mse": run.heldout_mse,
        "heldout_quality_q": run.heldout_quality_q,
        "transfer_mse": run.transfer_mse,
        "transfer_quality_q": run.transfer_quality_q,
        "canonical_family_ids": list(evidence.canonical_family_ids),
        "semantic_bucket_ids": list(evidence.semantic_bucket_ids),
        "lineage_root_ids": list(evidence.lineage_root_ids),
        "experiment_record_digests": list(evidence.experiment_record_digests),
        "transcript_cluster_digest": evidence.transcript_cluster_digest,
        "provenance_cluster_digest": evidence.provenance_cluster_digest,
    }


def _paired(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from carbon.gauntlet import AgentProfile, ExperimentalArm

    result: list[dict[str, Any]] = []
    for profile in AgentProfile:
        profile_rows = [row for row in rows if row["profile"] == profile.value]
        by_block = {}
        for row in profile_rows:
            by_block.setdefault(row["block_id"], {})[row["arm"]] = row
        for baseline in ExperimentalArm:
            if baseline is ExperimentalArm.V2_TEST_ONLY_PRIOR:
                continue
            primary: list[float] = []
            transfer: list[float] = []
            for arms in by_block.values():
                if set(arms) != {item.value for item in ExperimentalArm}:
                    continue
                v2 = arms[ExperimentalArm.V2_TEST_ONLY_PRIOR.value]
                base = arms[baseline.value]
                primary.append(v2["heldout_quality_q"] - base["heldout_quality_q"])
                transfer.append(v2["transfer_quality_q"] - base["transfer_quality_q"])
            result.append(
                {
                    "profile": profile.value,
                    "baseline": baseline.value,
                    "paired_block_count": len(primary),
                    "primary_mean_difference_q": statistics.fmean(primary),
                    "primary_sample_sd_q": _sample_sd(primary),
                    "transfer_mean_difference_q": statistics.fmean(transfer),
                    "transfer_sample_sd_q": _sample_sd(transfer),
                }
            )
    return result


def _summary(
    rows: list[dict[str, Any]],
    *,
    primary_failures: int,
    replacement_count: int,
) -> dict[str, Any]:
    from carbon.gauntlet import AgentProfile, ExperimentalArm

    profiles = []
    for profile in AgentProfile:
        selected = [row for row in rows if row["profile"] == profile.value]
        blocks = {row["block_id"] for row in selected}
        profiles.append(
            {
                "profile": profile.value,
                "completed_block_count": len(blocks),
                "run_count": len(selected),
                "wall_p99_seconds": _nearest_rank(
                    [row["wall_seconds"] for row in selected], 0.99
                ),
                "observed_wall_seconds": math.fsum(
                    row["wall_seconds"] for row in selected
                ),
                "compute_p99_units": int(
                    _nearest_rank(
                        [row["normalized_compute_units"] for row in selected], 0.99
                    )
                ),
                "fixture_p99_units": _nearest_rank(
                    [row["fixture_units"] for row in selected], 0.99
                ),
                "invalid_attempt_count": sum(
                    row["invalid_preflight_count"] for row in selected
                ),
                "selection_changed_count": sum(
                    row["selected_changed_from_first"] for row in selected
                ),
            }
        )
    quality = []
    for arm in ExperimentalArm:
        selected = [row for row in rows if row["arm"] == arm.value]
        quality.append(
            {
                "arm": arm.value,
                "run_count": len(selected),
                "heldout_quality_mean_q": statistics.fmean(
                    row["heldout_quality_q"] for row in selected
                ),
                "transfer_quality_mean_q": statistics.fmean(
                    row["transfer_quality_q"] for row in selected
                ),
            }
        )
    v2_rows = [row for row in rows if row["arm"] == "V2_TEST_ONLY_PRIOR"]
    return {
        "planned_primary_block_count": 25,
        "completed_primary_block_count": 25 - primary_failures,
        "primary_failure_count": primary_failures,
        "replacement_count": replacement_count,
        "observed_primary_failure_rate": primary_failures / 25,
        "zero_failure_one_sided_95_upper_bound": (
            1.0 - math.pow(0.05, 1.0 / 25.0) if primary_failures == 0 else None
        ),
        "run_count": len(rows),
        "practice_admissible_run_count": sum(
            row["practice_admissible"] for row in rows
        ),
        "reconstruction_success_count": sum(
            row["reconstruction_succeeded"] for row in rows
        ),
        "invalid_attempt_count": sum(row["invalid_preflight_count"] for row in rows),
        "observed_wall_seconds": math.fsum(row["wall_seconds"] for row in rows),
        "normalized_compute_units": sum(
            row["normalized_compute_units"] for row in rows
        ),
        "fixture_units": math.fsum(row["fixture_units"] for row in rows),
        "service_calls": sum(row["service_request_count"] for row in rows),
        "profiles": profiles,
        "arm_quality": quality,
        "paired_contrasts": _paired(rows),
        "v2_canonical_family_ids": sorted(
            {item for row in v2_rows for item in row["canonical_family_ids"]}
        ),
        "v2_lineage_root_count": len(
            {item for row in v2_rows for item in row["lineage_root_ids"]}
        ),
        "unique_transcript_cluster_count": len(
            {row["transcript_cluster_digest"] for row in rows}
        ),
        "unique_provenance_cluster_count": len(
            {row["provenance_cluster_digest"] for row in rows}
        ),
        "cross_profile_dependence_status": "UNVALIDATED_NO_SHADOW_CAMPAIGN",
    }


def generate_manifest() -> dict[str, Any]:
    freeze = load_freeze()
    integration, lifecycle_fixture = _load_fixture_builders()
    from carbon.gauntlet import (
        AgentSession,
        LifecycleFailureKind,
        MatchedBudget,
        NonQualifyingLifecycleError,
        OfficialLifecycleBridge,
        RehearsalPurpose,
        RehearsalSlotRole,
        ResearchLifecycleBridge,
        authorize_replacement,
        build_nonqualifying_lifecycle_four_arm_block,
        build_rehearsal_campaign_manifest,
        executable_driver_artifact,
        fixture_agent_drivers,
        fixture_strategy_domain,
        lifecycle_treatment_artifact,
        record_block_failure,
        record_rehearsal_campaign,
        record_rehearsal_run,
        rehearsal_budget_digest,
        run_nonqualifying_lifecycle,
    )
    from carbon.gauntlet.meter import PolicyWorkMeter

    with tempfile.TemporaryDirectory(prefix="carbon-be4-full-calibration-") as raw:
        working = Path(raw)
        domain = integration._extended_resource_fixture(working / "domain")
        store, prior_provider, lookup = integration._published_prior(
            working / "prior", domain
        )
        service, provider, scaffold_ref, practice_pack_ref = (
            lifecycle_fixture._lifecycle_research_graph(
                working / "research", domain, store, prior_provider, lookup
            )
        )
        bridge = ResearchLifecycleBridge(service, provider)
        drivers = fixture_agent_drivers()
        strategy_domain = fixture_strategy_domain(
            domain.compile_fixture.catalog.to_ref(
                candidate_assembly=domain.compile_fixture.assembly
            )
        )
        budgets = {
            driver.profile: MatchedBudget(
                driver.profile, WALL_SECONDS, COMPUTE_UNITS, ATTEMPT_LIMIT
            )
            for driver in drivers
        }
        sample_block, sample_projection = build_nonqualifying_lifecycle_four_arm_block(
            design_digest=freeze["v3_design_digest"],
            block_id="be4-full-lifecycle-calibration-v1-planner-primary-0000",
            profile=drivers[0].profile,
            replicate=0,
            driver_ref=drivers[0].ref,
            budget=budgets[drivers[0].profile],
            fixture_resource_ceiling=FIXTURE_UNITS,
            scaffold_ref=scaffold_ref,
            practice_pack_ref=practice_pack_ref,
            v2_prior_pack=store.read_pack(lookup.prior_pack_ref),
            v2_authorization_ref=lookup.authorization.receipt_ref,
        )
        treatment_digests = tuple(
            lifecycle_treatment_artifact(plan, sample_projection).content_digest
            for plan in sample_block.runs
        )
        manifest = build_rehearsal_campaign_manifest(
            purpose=RehearsalPurpose.CALIBRATION,
            design_digest=freeze["v3_design_digest"],
            implementation_digest=freeze["implementation_digest"],
            treatment_digests=treatment_digests,
            driver_digests=tuple(
                executable_driver_artifact(driver).content_digest for driver in drivers
            ),
            budget_digests=tuple(
                rehearsal_budget_digest(budgets[driver.profile]) for driver in drivers
            ),
            primary_blocks_per_profile=PRIMARY_BLOCKS_PER_PROFILE,
            reserve_blocks_per_profile=RESERVE_BLOCKS_PER_PROFILE,
            campaign_id=CAMPAIGN_ID,
            stopping_rule=STOPPING_RULE,
            failure_handling=FAILURE_HANDLING,
        )
        catalog_ref = domain.compile_fixture.catalog.to_ref(
            candidate_assembly=domain.compile_fixture.assembly
        )
        requester = integration._REQUESTER
        runs = []
        rows: list[dict[str, Any]] = []
        failures = []
        replacements = []
        primary_failures = 0
        by_profile_reserve = {
            profile: next(
                item
                for item in manifest.slots
                if item.profile is profile and item.role is RehearsalSlotRole.RESERVE
            )
            for profile in type(drivers[0].profile)
        }
        execution_slots = [
            item for item in manifest.slots if item.role is RehearsalSlotRole.PRIMARY
        ]
        index = 0
        while index < len(execution_slots):
            slot = execution_slots[index]
            index += 1
            driver = next(item for item in drivers if item.profile is slot.profile)
            block, projection = build_nonqualifying_lifecycle_four_arm_block(
                design_digest=freeze["v3_design_digest"],
                block_id=slot.block_id,
                profile=slot.profile,
                replicate=slot.number,
                driver_ref=driver.ref,
                budget=budgets[slot.profile],
                fixture_resource_ceiling=FIXTURE_UNITS,
                scaffold_ref=scaffold_ref,
                practice_pack_ref=practice_pack_ref,
                v2_prior_pack=store.read_pack(lookup.prior_pack_ref),
                v2_authorization_ref=lookup.authorization.receipt_ref,
            )
            failed = None
            for plan in block.runs:
                official, submission, adapter = integration._official_graph(
                    working / "official" / slot.block_id / plan.identity.arm.value,
                    domain,
                )
                meter = PolicyWorkMeter()
                session = AgentSession(service, official, requester, meter)
                try:
                    run = run_nonqualifying_lifecycle(
                        session=session,
                        plan=plan,
                        driver=driver,
                        projection=projection,
                        strategy_domain=strategy_domain,
                        parameter_catalog=domain.compile_fixture.catalog,
                        candidate_assembly=domain.compile_fixture.assembly,
                        meter=meter,
                        research_bridge=bridge,
                        official_bridge=OfficialLifecycleBridge(
                            official, submission, adapter, requester
                        ),
                    )
                except NonQualifyingLifecycleError as exc:
                    failed = record_block_failure(slot, exc)
                    failures.append(failed)
                    break
                evidence = record_rehearsal_run(
                    run,
                    catalog=domain.compile_fixture.catalog,
                    candidate_assembly=domain.compile_fixture.assembly,
                    catalog_ref=catalog_ref,
                )
                runs.append(evidence)
                rows.append(_row(run, evidence, slot.role.value, slot.number))
            if failed is not None and slot.role is RehearsalSlotRole.PRIMARY:
                primary_failures += 1
                if failed.failure_kind in (
                    LifecycleFailureKind.INFRASTRUCTURE,
                    LifecycleFailureKind.REFERENCE,
                ):
                    reserve = by_profile_reserve[slot.profile]
                    replacements.append(
                        authorize_replacement(failed=failed, replacement=reserve)
                    )
                    execution_slots.append(reserve)
        campaign = record_rehearsal_campaign(
            manifest=manifest,
            runs=tuple(runs),
            failures=tuple(failures),
            replacements=tuple(replacements),
        )
        value = {
            "schema_version": SCHEMA_VERSION,
            "evidence_role": EVIDENCE_ROLE,
            "authority_ceiling": AUTHORITY_CEILING,
            "purpose": "CALIBRATION",
            "freeze_digest": freeze["content_digest"],
            "rehearsal_manifest_digest": manifest.content_digest,
            "rehearsal_campaign_digest": campaign.content_digest,
            "qualifying_execution_ready": False,
            "execution_boundary": {
                "attack_campaign_calls": 0,
                "shadow_case_calls": 0,
                "qualifying_gauntlet_calls": 0,
            },
            "rows": rows,
            "failures": [
                {
                    "block_id": item.slot.block_id,
                    "profile": item.slot.profile.value,
                    "slot_role": item.slot.role.value,
                    "slot_number": item.slot.number,
                    "failure_kind": item.failure_kind.value,
                    "stage": item.stage,
                    "content_digest": item.content_digest,
                }
                for item in failures
            ],
            "replacements": [
                {
                    "failed_digest": item.failed.content_digest,
                    "replacement_block_id": item.replacement.block_id,
                    "content_digest": item.content_digest,
                }
                for item in replacements
            ],
            "summary": _summary(
                rows,
                primary_failures=primary_failures,
                replacement_count=len(replacements),
            ),
        }
        value["replay_stable_digest"] = replay_stable_digest(value)
        value["content_digest"] = manifest_content_digest(value)
        return validate_manifest(value)


def validate_manifest(value: dict[str, Any]) -> dict[str, Any]:
    freeze = load_freeze()
    if type(value) is not dict or set(value) != {
        "schema_version",
        "evidence_role",
        "authority_ceiling",
        "purpose",
        "freeze_digest",
        "rehearsal_manifest_digest",
        "rehearsal_campaign_digest",
        "qualifying_execution_ready",
        "execution_boundary",
        "rows",
        "failures",
        "replacements",
        "summary",
        "replay_stable_digest",
        "content_digest",
    }:
        raise FullLifecycleCalibrationError("manifest does not have its exact schema")
    if (
        value["schema_version"] != SCHEMA_VERSION
        or value["evidence_role"] != EVIDENCE_ROLE
        or value["authority_ceiling"] != AUTHORITY_CEILING
        or value["purpose"] != "CALIBRATION"
        or value["freeze_digest"] != freeze["content_digest"]
        or value["qualifying_execution_ready"] is not False
        or value["execution_boundary"]
        != {
            "attack_campaign_calls": 0,
            "shadow_case_calls": 0,
            "qualifying_gauntlet_calls": 0,
        }
    ):
        raise FullLifecycleCalibrationError("manifest boundary is not exact")
    if type(value["rows"]) is not list or type(value["failures"]) is not list:
        raise FullLifecycleCalibrationError("manifest observations are not lists")
    rows = value["rows"]
    if value["summary"] != _summary(
        rows,
        primary_failures=len(
            {
                item["block_id"]
                for item in value["failures"]
                if item["slot_role"] == "PRIMARY"
            }
        ),
        replacement_count=len(value["replacements"]),
    ):
        raise FullLifecycleCalibrationError("summary does not match raw rows")
    if any(
        row["normalized_compute_units"] > COMPUTE_UNITS
        or row["fixture_units"] > FIXTURE_UNITS
        or row["wall_seconds"] > WALL_SECONDS
        or row["practice_admissible"] is not True
        or row["reconstruction_succeeded"] is not True
        for row in rows
    ):
        raise FullLifecycleCalibrationError("row violates frozen calibration bounds")
    if value["replay_stable_digest"] != replay_stable_digest(value):
        raise FullLifecycleCalibrationError("replay-stable digest is inconsistent")
    if value["content_digest"] != manifest_content_digest(value):
        raise FullLifecycleCalibrationError("manifest content digest is inconsistent")
    return value


def load_manifest(path: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FullLifecycleCalibrationError("cannot load calibration evidence") from exc
    return validate_manifest(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.write == args.check:
        parser.error("choose exactly one of --write or --check")
    if args.write:
        DEFAULT_OUTPUT.write_text(
            render_manifest(generate_manifest()), encoding="utf-8"
        )
        print(DEFAULT_OUTPUT)
        return 0
    value = load_manifest()
    if DEFAULT_OUTPUT.read_text(encoding="utf-8") != render_manifest(value):
        raise FullLifecycleCalibrationError("committed evidence is not canonical")
    print(value["content_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
