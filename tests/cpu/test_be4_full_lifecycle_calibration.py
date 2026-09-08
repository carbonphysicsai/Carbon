"""Frozen B-E4 full-lifecycle calibration and v4 proposal boundaries."""

from __future__ import annotations

import ast
import copy
import json
import math
from pathlib import Path

import pytest

from carbon.gauntlet.proposal import (
    FIXTURE_PRACTICAL_EFFECT_FLOOR,
    FIXTURE_TRANSFER_NONINFERIORITY_MARGIN,
    ReadinessProposalError,
    derive_v3_resource_estimate,
    parse_execution_readiness_proposal,
)
from scripts.dev.generate_be4_full_lifecycle_calibration import (
    AUTHORITY_CEILING,
    FullLifecycleCalibrationError,
    _summary,
    load_freeze,
    load_manifest,
    manifest_content_digest,
    replay_stable_digest,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = (
    ROOT / ".agent" / "evidence" / "wave_b" / "b-e4-full-lifecycle-calibration-v1.json"
)
V4 = ROOT / ".agent" / "preregistrations" / "B-E4_recommended_design_v4.json"


def test_committed_calibration_is_complete_bounded_and_nonqualifying() -> None:
    freeze = load_freeze()
    manifest = load_manifest(EVIDENCE)
    summary = manifest["summary"]

    assert manifest["freeze_digest"] == freeze["content_digest"]
    assert manifest["authority_ceiling"] == AUTHORITY_CEILING
    assert manifest["purpose"] == "CALIBRATION"
    assert manifest["qualifying_execution_ready"] is False
    assert manifest["execution_boundary"] == {
        "attack_campaign_calls": 0,
        "qualifying_gauntlet_calls": 0,
        "shadow_case_calls": 0,
    }
    assert len(manifest["rows"]) == 100
    assert manifest["failures"] == []
    assert manifest["replacements"] == []
    assert summary["planned_primary_block_count"] == 25
    assert summary["completed_primary_block_count"] == 25
    assert summary["practice_admissible_run_count"] == 100
    assert summary["reconstruction_success_count"] == 100
    assert summary["invalid_attempt_count"] == 0
    assert summary["unique_transcript_cluster_count"] == 100
    assert summary["unique_provenance_cluster_count"] == 5
    assert summary["v2_lineage_root_count"] == 3
    assert math.isclose(
        summary["zero_failure_one_sided_95_upper_bound"],
        0.11292814500684323,
        rel_tol=0.0,
        abs_tol=1e-15,
    )


def test_manifest_binds_rows_but_replay_digest_excludes_host_wall_time() -> None:
    original = load_manifest(EVIDENCE)
    changed = copy.deepcopy(original)
    changed["rows"][0]["wall_seconds"] += 0.001
    changed["summary"] = _summary(
        changed["rows"], primary_failures=0, replacement_count=0
    )
    changed["replay_stable_digest"] = replay_stable_digest(changed)
    changed["content_digest"] = manifest_content_digest(changed)

    validate_manifest(changed)
    assert changed["content_digest"] != original["content_digest"]
    assert changed["replay_stable_digest"] == original["replay_stable_digest"]

    tampered = copy.deepcopy(original)
    tampered["rows"][0]["normalized_compute_units"] += 1
    tampered["content_digest"] = manifest_content_digest(tampered)
    with pytest.raises(FullLifecycleCalibrationError, match="summary"):
        validate_manifest(tampered)


def test_calibration_cannot_be_relabelled_as_qualifying() -> None:
    manifest = copy.deepcopy(load_manifest(EVIDENCE))
    manifest["qualifying_execution_ready"] = True
    manifest["content_digest"] = manifest_content_digest(manifest)
    with pytest.raises(FullLifecycleCalibrationError, match="boundary"):
        validate_manifest(manifest)

    source = ast.parse(
        (
            ROOT / "scripts" / "dev" / "generate_be4_full_lifecycle_calibration.py"
        ).read_text(encoding="utf-8")
    )
    invoked = {
        node.func.id
        for node in ast.walk(source)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not invoked.intersection(
        {"run_attack_campaign", "run_shadow_campaign", "run_qualifying_gauntlet"}
    )


def test_v4_proposal_uses_calibrated_caps_and_separate_transfer_geometry() -> None:
    proposal = parse_execution_readiness_proposal(V4.read_text(encoding="utf-8"))
    payload = json.loads(proposal.canonical_payload)
    inputs = payload["design_inputs"]
    budget = inputs["matched_time_compute_budgets"]["recommended_value"]
    rule = inputs["uncertainty_aware_decision_rule"]["recommended_value"]

    assert proposal.status == "STILL_BLOCKED"
    assert not proposal.qualifying_execution_ready
    assert proposal.design_digest == (
        "sha256:038eecfa8c17ae5bb309e9417f9397777168ddeaf281c9601ca35402b5caf836"
    )
    assert [
        (item["normalized_compute_units"], item["wall_time_seconds"])
        for item in budget["profile_caps"]
    ] == [(49, 2), (49, 2), (53, 2), (53, 2), (27, 1)]
    assert rule["transfer_noninferiority_margin_q"] == pytest.approx(
        FIXTURE_TRANSFER_NONINFERIORITY_MARGIN
    )
    assert rule["transfer_noninferiority_margin_q"] < FIXTURE_PRACTICAL_EFFECT_FLOOR

    # Both margins allow the same multiplicative change in (loss + 1), despite
    # independent 0/90 and 0/650 endpoint anchors.
    primary_factor = math.exp(FIXTURE_PRACTICAL_EFFECT_FLOOR * math.log1p(90.0))
    transfer_factor = math.exp(
        rule["transfer_noninferiority_margin_q"] * math.log1p(650.0)
    )
    assert transfer_factor == pytest.approx(primary_factor)

    resources = derive_v3_resource_estimate(proposal)
    assert resources.agent_arm_runs_planned == 12_720
    assert resources.policy_work_units_planned == 587_664
    assert resources.wall_seconds_planned == 22_896


def test_v4_rejects_uncalibrated_cap_or_v3_transfer_alias() -> None:
    payload = json.loads(V4.read_text(encoding="utf-8"))
    payload["design_inputs"]["matched_time_compute_budgets"]["recommended_value"][
        "profile_caps"
    ][0]["normalized_compute_units"] = 48
    with pytest.raises(ReadinessProposalError, match="v4 profile caps"):
        parse_execution_readiness_proposal(json.dumps(payload, sort_keys=True))

    payload = json.loads(V4.read_text(encoding="utf-8"))
    payload["design_inputs"]["uncertainty_aware_decision_rule"]["recommended_value"][
        "transfer_noninferiority_margin_q"
    ] = FIXTURE_PRACTICAL_EFFECT_FLOOR
    with pytest.raises(ReadinessProposalError, match="endpoint geometry"):
        parse_execution_readiness_proposal(json.dumps(payload, sort_keys=True))
