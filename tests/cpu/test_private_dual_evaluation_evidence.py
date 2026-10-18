"""Inert public-development originals test the trusted v4 binder, not physics."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from test_score_lab_private_evaluation_evidence import (
    _bind,
    _graph_case,
    _source_receipt,
)

from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    PUBLIC_ROLES,
    SCHEMA,
    parse_pack,
)
from carbon.scoring import benchmark_evidence, dual_score
from carbon.scoring import private_evaluation_evidence as private
from carbon.scoring.engine import ScoreEngine


def _seal(case, manifest):
    raw = private._canonical(manifest)
    snapshot = parse_pack(
        raw,
        expected_digest=private._sha(raw),
        challenge_id=case["entry"]["challenge"],
        challenge_version=case["entry"]["challenge_version"],
    )
    case["manifest"] = manifest
    case["snapshot"] = snapshot
    case["pack_pin"] = snapshot.manifest_digest


def _case(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    case = _graph_case(tmp_path)
    case["references"][0]["outputs"] = [
        0.5
    ]  # Inert fixture target; retained model predicts 0.25.
    registration = {
        key: value
        for key, value in case["registration"].items()
        if key != "registration_digest"
    }
    registration["scope"] = "PUBLIC_DEVELOPMENT"
    case["registration"] = benchmark_evidence.register(registration)
    basis = {
        "schema": "carbon.scoring.dual-measurement-contract.v1",
        "producer_digest": private._sha(b"inert-test-producer-not-a-physical-method"),
        "accuracy_definition_sha256": private._sha(
            b"inert-absolute-error-fixture-definition"
        ),
        "important_limit_definition_sha256": private._sha(b"inert-finite-output-gate"),
        "design_objective_sha256": private._sha(b"inert-one-action-index-selection"),
    }

    def component(metric):
        return {
            "components": [
                {
                    "metric": metric,
                    "unit": "1",
                    "transform": "unit_benefit",
                    "scale": None,
                    "weight": 1.0,
                }
            ],
            "minimum": None,
        }

    case["pack"] = dual_score.register_pack(
        {
            "schema": dual_score.PACK_SCHEMA,
            "scope": "PUBLIC_DEVELOPMENT",
            "challenge": case["entry"]["challenge"],
            "physics_contract_digest": benchmark_evidence.physics_contract_identity(
                case["job"]["physics_contract"]
            )["definition_digest"],
            "measurement_contract_digest": private._sha(private._canonical(basis)),
            "hard_gates": ["toy_gate"],
            "legs": {
                "A": component("fixture_fidelity"),
                "D": component("fixture_verified_pick"),
            },
            "value_weight": 0.5,
            "combination": "weighted_arithmetic_mean",
            "decision_policy": {
                "VERIFIED_FEASIBLE": {"eligible": True, "maximum_D": 1.0},
                "MISSED_OPPORTUNITY": {"eligible": False, "maximum_D": 0.0},
                "NONE_FEASIBLE": {"eligible": False, "maximum_D": 0.0},
            },
        }
    )
    case["basis"] = basis
    manifest = {
        "schema": SCHEMA,
        "challenge": {
            "id": case["entry"]["challenge"],
            "version": case["entry"]["challenge_version"],
        },
        "pack_version": "inert-v4-test",
        "public": {
            role: {"path": f"inert/{role}.json", "sha256": private._sha(role.encode())}
            for role in PUBLIC_ROLES
        },
        "private": {
            role: {"path": f"inert/{role}.json", "sha256": private._sha(role.encode())}
            for role in PRIVATE_ROLES
        },
    }
    for role in (
        "accuracy_definition",
        "important_limit_definition",
        "design_objective",
    ):
        manifest["public"][role]["sha256"] = basis[role + "_sha256"]
    _seal(case, manifest)
    return case


def _arguments(case, *, benchmark_changes=None):
    source_raw, _ = _source_receipt(case)
    source = json.loads(source_raw)
    source["schema"] = private.PACK_SOURCE_SCHEMA
    source["evaluation_pack_digest"] = case["pack_pin"]
    source_raw = private._canonical(source)
    # These fixture measurements follow the inert retained scalar originals:
    # raw fidelity error, and selection of the sole finite feasible toy action.
    prediction = case["measured"]["cases"][0]["outputs"][0]
    target = case["references"][0].get("outputs", [None])[0]
    state = {
        "RESOLVED": "RESOLVED",
        "UNRESOLVED": "REFERENCE_UNRESOLVED",
        "FAILED_INFRA": "REFERENCE_INFRA",
    }[case["references"][0]["status"]]
    measured = {
        "fixture_fidelity": {
            "status": state,
            "value": 1 / (1 + abs(prediction - target)) if target is not None else None,
            "unit": "1",
        },
        "fixture_verified_pick": {
            "status": state,
            "value": 1.0 if target is not None else None,
            "unit": "1",
        },
    }
    benchmark = {
        "schema": dual_score.INPUT_SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT",
        "challenge": case["entry"]["challenge"],
        "physics_contract_digest": case["pack"]["physics_contract_digest"],
        "measurement_contract_digest": case["pack"]["measurement_contract_digest"],
        "population_role": "P",
        "common_mask_digest": private._sha(private._canonical(source["cases"])),
        "models": [
            {
                "artifact_digest": case["entry"]["entry_id"],
                "gates": {
                    "toy_gate": (
                        (
                            "PASS"
                            if case["measured"]["cases"][0]["gates"]["toy_gate"]
                            else "FAIL"
                        )
                        if state == "RESOLVED"
                        else state
                    )
                },
                "measurements": measured,
                "decision_outcome": "VERIFIED_FEASIBLE",
            }
        ],
    }
    if benchmark_changes:
        benchmark.update(benchmark_changes)
    receipt = {
        "schema": private.DUAL_MEASUREMENT_SCHEMA,
        "source_receipt_sha256": private._sha(source_raw),
        "evaluation_pack_digest": case["pack_pin"],
        "score_pack_digest": case["pack"]["pack_digest"],
        "measurement_contract": case["basis"],
        "measurement_contract_digest": case["pack"]["measurement_contract_digest"],
        "producer_digest": case["basis"]["producer_digest"],
        "entry_id": case["entry"]["entry_id"],
        "state_digest": case["entry"]["state_digest"],
        "measured_model_sha256": private._sha(private._canonical(case["measured"])),
        "inference_receipt_sha256": private._sha(
            case["graph_originals"]["inference_receipt_raw"]
        ),
        "worker_evidence_sha256": private._sha(
            case["graph_originals"]["worker_evidence_raw"]
        ),
        "benchmark": benchmark,
    }
    raw = private._canonical(receipt)
    scoring = ScoreEngine.score_dual_benchmark_v4(benchmark, case["pack"])
    return {
        "entry": case["entry"],
        "custody_receipt_raw": case["custody_receipt_raw"],
        "trusted_job": case["job"],
        "registration": case["registration"],
        "references": case["references"],
        "measured_model": case["measured"],
        "score_pack": case["pack"],
        "graph_originals": case["graph_originals"],
        "expected_result_digest": private._sha(private._canonical(scoring)),
        "ordered_query_bytes": case["ordered_query_bytes"],
        "evaluation_source_receipt_raw": source_raw,
        "registered_source_receipt_sha256": private._sha(source_raw),
        "expected_evaluation_pack_digest": case["pack_pin"],
        "selected_evaluation_pack": case["snapshot"],
        "dual_measurement_receipt_raw": raw,
        "registered_dual_measurement_sha256": private._sha(raw),
    }, scoring


def test_bound_public_fixture_uses_exact_same_core_and_keeps_bank_ineligible(tmp_path):
    case = _case(tmp_path)
    args, expected = _arguments(case)
    original = deepcopy(case["entry"])
    bound = private.bind_private_evaluation_evidence(**args)
    assert bound["schema"] == private.DUAL_SIDECAR_SCHEMA
    assert bound["scoring"] == expected
    assert bound["model_p"]["physics_benefit"] == 0.8
    assert bound["model_p"]["design_benefit"] == 1.0
    assert bound["model_p"]["total_score"] == 0.9
    assert bound["model_p"]["score_status"] == "SCORED_DEVELOPMENT_CANDIDATE"
    assert bound["official_eligible"] is bound["official_score"] is False
    assert case["entry"] == original
    assert case["entry"]["score_state"] == "NOT_COMPUTED"
    assert "toy-case" not in private._canonical(bound).decode()


def test_mandatory_failure_cannot_be_compensated_by_high_legs(tmp_path):
    case = _case(tmp_path)
    case["measured"]["cases"][0]["gates"]["toy_gate"] = False
    args, _ = _arguments(case)
    row = private.bind_private_evaluation_evidence(**args)["model_p"]
    assert row["physics_benefit"] == 0.8 and row["design_benefit"] == 1.0
    assert row["score_status"] == "MANDATORY_GATE_FAILED"
    assert row["total_score"] is None


@pytest.mark.parametrize(
    "status,expected",
    [("UNRESOLVED", "INDETERMINATE_EVIDENCE"), ("FAILED_INFRA", "FAILED_INFRA")],
)
def test_reference_failure_is_typed_without_candidate_penalty(
    tmp_path, status, expected
):
    case = _case(tmp_path)
    case["references"] = [{"id": "toy-case", "status": status}]
    args, _ = _arguments(case)
    result = private.bind_private_evaluation_evidence(**args)
    assert result["model_p"]["score_status"] == expected
    assert result["model_p"]["total_score"] is None
    assert result["reference_coverage"][status] == 1


@pytest.mark.parametrize(
    "field", ["dual_measurement_receipt_raw", "registered_dual_measurement_sha256"]
)
def test_missing_trusted_record_stays_unavailable(tmp_path, field):
    args, _ = _arguments(_case(tmp_path))
    args[field] = None
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="dual_measurement_unavailable"
    ):
        private.bind_private_evaluation_evidence(**args)


def test_submitted_measurement_tamper_cannot_reuse_registered_operator_pin(tmp_path):
    args, _ = _arguments(_case(tmp_path))
    record = json.loads(args["dual_measurement_receipt_raw"])
    record["benchmark"]["models"][0]["measurements"]["fixture_fidelity"]["value"] = 1.0
    args["dual_measurement_receipt_raw"] = private._canonical(record)
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="dual_measurement_pin_mismatch"
    ):
        private.bind_private_evaluation_evidence(**args)


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("challenge", "wrong-challenge"),
        ("common_mask_digest", "sha256:" + "d" * 64),
        ("population_role", "Q"),
    ],
)
def test_wrong_challenge_or_mask_refuses_even_if_record_is_newly_pinned(
    tmp_path, field, replacement
):
    args, _ = _arguments(_case(tmp_path))
    record = json.loads(args["dual_measurement_receipt_raw"])
    record["benchmark"][field] = replacement
    args["dual_measurement_receipt_raw"] = private._canonical(record)
    args["registered_dual_measurement_sha256"] = private._sha(
        args["dual_measurement_receipt_raw"]
    )
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="dual_benchmark_binding"
    ):
        private.bind_private_evaluation_evidence(**args)


@pytest.mark.parametrize(
    "field",
    [
        "entry_id",
        "state_digest",
        "measured_model_sha256",
        "inference_receipt_sha256",
        "worker_evidence_sha256",
        "source_receipt_sha256",
        "score_pack_digest",
    ],
)
def test_stale_material_or_originals_refuse(tmp_path, field):
    args, _ = _arguments(_case(tmp_path))
    record = json.loads(args["dual_measurement_receipt_raw"])
    record[field] = "sha256:" + "c" * 64
    args["dual_measurement_receipt_raw"] = private._canonical(record)
    args["registered_dual_measurement_sha256"] = private._sha(
        args["dual_measurement_receipt_raw"]
    )
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused,
        match="dual_measurement_original_binding",
    ):
        private.bind_private_evaluation_evidence(**args)


def test_caller_producer_label_cannot_replace_pack_bound_contract(tmp_path):
    args, _ = _arguments(_case(tmp_path))
    record = json.loads(args["dual_measurement_receipt_raw"])
    record["producer_digest"] = "sha256:" + "b" * 64
    args["dual_measurement_receipt_raw"] = private._canonical(record)
    args["registered_dual_measurement_sha256"] = private._sha(
        args["dual_measurement_receipt_raw"]
    )
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="dual_measurement_contract"
    ):
        private.bind_private_evaluation_evidence(**args)


def test_definition_hashes_must_match_the_actual_selected_manifest(tmp_path):
    case = _case(tmp_path)
    changed = deepcopy(case["manifest"])
    changed["public"]["accuracy_definition"]["sha256"] = "sha256:" + "a" * 64
    _seal(case, changed)
    args, _ = _arguments(case)
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused,
        match="dual_selected_definition_binding",
    ):
        private.bind_private_evaluation_evidence(**args)


def test_unavailable_grading_role_does_not_become_a_passing_packet(tmp_path):
    case = _case(tmp_path)
    changed = deepcopy(case["manifest"])
    changed["private"]["score_pack"] = "HUMAN_INPUT"
    _seal(case, changed)
    args, _ = _arguments(case)
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="dual_selected_pack_unavailable"
    ):
        private.bind_private_evaluation_evidence(**args)


def test_opaque_manifest_digest_alone_cannot_replace_trusted_snapshot(tmp_path):
    args, _ = _arguments(_case(tmp_path))
    args["selected_evaluation_pack"] = None
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="dual_selected_pack_binding"
    ):
        private.bind_private_evaluation_evidence(**args)


def test_no_change_to_legacy_v3_or_unverifiable_bundle_acceptance(tmp_path):
    legacy = _graph_case(tmp_path)
    assert _bind(legacy)["schema"] == private.SIDECAR_SCHEMA
    args, _ = _arguments(_case(tmp_path / "dual"))
    args["graph_originals"] = None
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused,
        match="model_query_originals_unavailable",
    ):
        private.bind_private_evaluation_evidence(**args)
