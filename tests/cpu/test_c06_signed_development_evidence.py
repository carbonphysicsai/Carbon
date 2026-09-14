"""C-06 signed DEVELOPMENT receipt and append-only ledger tests."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace

import pytest

from carbon import audit


def _digest(label: str) -> str:
    return audit.digest_bytes(label.encode("ascii"))


def _binding(**changes: object) -> audit.DevelopmentEvidenceBinding:
    values: dict[str, object] = {
        "submission_id": "submission-c06-public-1",
        "strategy_digest": _digest("strategy"),
        "challenge_id": "burgers-dynamics-v1",
        "challenge_version": "1.0",
        "generator_digest": _digest("generator"),
        "target_population_digest": _digest("population"),
        "sampling_plan_digest": _digest("sampling"),
        "training_data_commitment": _digest("private-train-commitment"),
        "reconstruction_plan_digest": _digest("reconstruction-plan"),
        "repeat_plan_digest": _digest("three-replicas"),
        "resource_policy_digest": _digest("c03-resource-policy"),
        "reconstruction_outcome_digest": _digest("reconstruction-outcome"),
        "reconstruction_attempt_digests": tuple(
            _digest(f"attempt-{index}") for index in range(3)
        ),
        "inference_request_digest": _digest("inference-request"),
        "prediction_digest": _digest("prediction"),
        "reference_policy_digest": _digest("reference-policy"),
        "reference_implementation_digest": _digest("cole-hopf"),
        "reference_environment_digest": _digest("reference-environment"),
        "reference_artifact_digest": _digest("reference-artifact"),
        "measurement_contract_digest": _digest("measurement-contract"),
        "measurement_implementation_digest": _digest("measurement-code"),
        "measurement_environment_digest": _digest("measurement-environment"),
        "measurement_result_digest": _digest("measurement-result"),
        "scoring_policy_digest": _digest("unqualified-scoring-policy"),
        "dossier_digest": _digest("dossier"),
        "qualification_manifest_digest": _digest("qualification-manifest"),
        "source_tree_digest": _digest("source-tree"),
        "worker_image_digest": _digest("worker-image"),
        "execution_policy_digest": _digest("execution-policy"),
    }
    values.update(changes)
    return audit.DevelopmentEvidenceBinding(**values)


def _signer() -> audit.DevelopmentReceiptSigner:
    return audit.DevelopmentReceiptSigner(
        key_id="c06-development-key-v1",
        private_key=bytes(range(32)),
        valid_from_micros=1_000,
        valid_until_micros=9_000,
    )


def _receipt(
    signer: audit.DevelopmentReceiptSigner,
    *,
    receipt_id: str = "c06-receipt-1",
    binding: audit.DevelopmentEvidenceBinding | None = None,
    supersedes: str | None = None,
    status: audit.DevelopmentRunStatus = audit.DevelopmentRunStatus.COMPLETE_UNRESOLVED,
) -> audit.SignedDevelopmentEvaluationReceipt:
    key = signer.verification_key
    receipt = audit.DevelopmentEvaluationReceipt(
        receipt_id=receipt_id,
        binding=_binding() if binding is None else binding,
        run_status=status,
        started_at_micros=2_000,
        finished_at_micros=3_000,
        signing_key_id=key.key_id,
        signing_public_key_digest=key.public_key_digest,
        supersedes_receipt_id=supersedes,
    )
    return signer.sign(receipt)


def _evidence(binding: audit.DevelopmentEvidenceBinding) -> audit.FrozenEvidenceIndex:
    return audit.FrozenEvidenceIndex(frozenset(binding.required_evidence_digests()))


def _ledger(tmp_path, signer: audit.DevelopmentReceiptSigner):
    return audit.DevelopmentEvidenceLedger(
        tmp_path / "c06.sqlite3", (signer.verification_key,)
    )


def test_signature_append_replay_and_round_trip_are_exact(tmp_path) -> None:
    signer = _signer()
    signed = _receipt(signer)
    ledger = _ledger(tmp_path, signer)

    disposition, reference = ledger.append(
        signed, _evidence(signed.receipt.binding), verified_at_micros=3_100
    )
    replay, same_reference = ledger.append(
        signed, _evidence(signed.receipt.binding), verified_at_micros=3_100
    )
    resolved, state = ledger.resolve(reference, verified_at_micros=3_100)

    assert disposition is audit.ReceiptWriteDisposition.APPENDED
    assert replay is audit.ReceiptWriteDisposition.ALREADY_PRESENT
    assert same_reference == reference
    assert resolved == signed
    assert state is audit.ReceiptLifecycleState.ACTIVE
    assert ledger.checkpoint().receipt_count == 1
    audit.verify_signed_receipt(
        resolved, signer.verification_key, verified_at_micros=3_100
    )


def test_public_and_reviewer_projections_are_distinct_positive_allow_lists(
    tmp_path,
) -> None:
    signer = _signer()
    signed = _receipt(signer)
    ledger = _ledger(tmp_path, signer)
    _, reference = ledger.append(
        signed, _evidence(signed.receipt.binding), verified_at_micros=3_100
    )
    resolved, state = ledger.resolve(reference, verified_at_micros=3_100)

    public = audit.public_projection(resolved, reference, state)
    reviewer = audit.reviewer_projection(resolved, reference, state)
    assert set(public) == {
        "schema",
        "receipt_id",
        "receipt_digest",
        "challenge",
        "submission_id",
        "run_status",
        "lifecycle_state",
        "authority_marker",
        "signing_key_id",
        "ledger",
        "eligibility",
    }
    assert set(reviewer) == {
        "schema",
        "public",
        "binding",
        "started_at_micros",
        "finished_at_micros",
        "supersedes_receipt_id",
        "signature",
    }
    assert reviewer["binding"] == signed.receipt.binding.document()
    public_text = json.dumps(public).lower()
    for forbidden in (
        "private-train-commitment",
        "seed",
        "draw_id",
        "reference_solution",
        "threshold",
        "metric_value",
        "private_key",
    ):
        assert forbidden not in public_text
    assert set(public["eligibility"].values()) == {False}


def test_missing_evidence_signature_tamper_and_stale_key_fail_before_append(
    tmp_path,
) -> None:
    signer = _signer()
    signed = _receipt(signer)
    ledger = _ledger(tmp_path, signer)
    complete = set(signed.receipt.binding.required_evidence_digests())
    complete.remove(signed.receipt.binding.measurement_result_digest)

    with pytest.raises(audit.AuditFailure) as missing:
        ledger.append(
            signed,
            audit.FrozenEvidenceIndex(frozenset(complete)),
            verified_at_micros=3_100,
        )
    assert missing.value.code is audit.AuditCode.MISSING_EVIDENCE
    assert ledger.checkpoint().receipt_count == 0

    tampered = audit.SignedDevelopmentEvaluationReceipt(
        signed.receipt, signed.signature[:-1] + bytes([signed.signature[-1] ^ 1])
    )
    with pytest.raises(audit.AuditFailure) as invalid:
        ledger.append(
            tampered, _evidence(signed.receipt.binding), verified_at_micros=3_100
        )
    assert invalid.value.code is audit.AuditCode.SIGNATURE

    stale_receipt = replace(
        signed.receipt,
        started_at_micros=8_999,
        finished_at_micros=9_001,
    )
    stale_signed = audit.SignedDevelopmentEvaluationReceipt(stale_receipt, bytes(64))
    with pytest.raises(audit.AuditFailure) as stale:
        ledger.append(
            stale_signed,
            _evidence(stale_receipt.binding),
            verified_at_micros=9_001,
        )
    assert stale.value.code is audit.AuditCode.STALE_KEY
    assert ledger.checkpoint().receipt_count == 0


def test_same_id_changed_bytes_conflict_and_exact_types_reject(tmp_path) -> None:
    signer = _signer()
    first = _receipt(signer)
    ledger = _ledger(tmp_path, signer)
    ledger.append(first, _evidence(first.receipt.binding), verified_at_micros=3_100)
    changed = _receipt(
        signer,
        binding=_binding(measurement_result_digest=_digest("different-result")),
    )
    with pytest.raises(audit.AuditFailure) as conflict:
        ledger.append(
            changed, _evidence(changed.receipt.binding), verified_at_micros=3_100
        )
    assert conflict.value.code is audit.AuditCode.CONFLICT
    with pytest.raises(audit.AuditFailure) as lookalike:
        ledger.append(
            object(),  # type: ignore[arg-type]
            _evidence(first.receipt.binding),
            verified_at_micros=3_100,
        )
    assert lookalike.value.code is audit.AuditCode.INVALID


def test_supersession_and_revocation_are_append_only_states(tmp_path) -> None:
    signer = _signer()
    first = _receipt(signer)
    ledger = _ledger(tmp_path, signer)
    _, first_ref = ledger.append(
        first, _evidence(first.receipt.binding), verified_at_micros=3_100
    )
    second = _receipt(
        signer,
        receipt_id="c06-receipt-2",
        binding=_binding(measurement_result_digest=_digest("corrected-result")),
        supersedes=first.receipt.receipt_id,
    )
    _, second_ref = ledger.append(
        second, _evidence(second.receipt.binding), verified_at_micros=3_100
    )
    assert ledger.resolve(first_ref, verified_at_micros=3_100)[1] is (
        audit.ReceiptLifecycleState.SUPERSEDED
    )
    assert ledger.resolve(second_ref, verified_at_micros=3_100)[1] is (
        audit.ReceiptLifecycleState.ACTIVE
    )
    checkpoint = ledger.revoke(second.receipt.receipt_id, _digest("reason"))
    assert checkpoint.receipt_count == 2
    assert ledger.resolve(second_ref, verified_at_micros=3_100)[1] is (
        audit.ReceiptLifecycleState.REVOKED
    )
    with pytest.raises(audit.AuditFailure) as duplicate:
        ledger.revoke(second.receipt.receipt_id, _digest("again"))
    assert duplicate.value.code is audit.AuditCode.STATE


def test_atomic_append_rolls_back_when_event_append_fails(
    tmp_path, monkeypatch
) -> None:
    signer = _signer()
    signed = _receipt(signer)
    ledger = _ledger(tmp_path, signer)

    def fail_event(*_args, **_kwargs):
        raise audit.AuditFailure(audit.AuditCode.STORE)

    monkeypatch.setattr(ledger, "_append_event", fail_event)
    with pytest.raises(audit.AuditFailure):
        ledger.append(
            signed, _evidence(signed.receipt.binding), verified_at_micros=3_100
        )
    assert ledger.checkpoint().receipt_count == 0


@pytest.mark.parametrize(
    "field",
    (
        "protected_execution_eligible",
        "score_eligible",
        "archive_acknowledged",
        "network_eligible",
        "reward_eligible",
    ),
)
def test_authority_upgrade_fields_are_structurally_denied(field: str) -> None:
    signer = _signer()
    key = signer.verification_key
    values = {
        "receipt_id": "c06-receipt-denied",
        "binding": _binding(),
        "run_status": audit.DevelopmentRunStatus.COMPLETE_UNRESOLVED,
        "started_at_micros": 2_000,
        "finished_at_micros": 3_000,
        "signing_key_id": key.key_id,
        "signing_public_key_digest": key.public_key_digest,
        field: True,
    }
    with pytest.raises(audit.AuditFailure) as denied:
        audit.DevelopmentEvaluationReceipt(**values)
    assert denied.value.code is audit.AuditCode.DENIED


def test_tampered_and_partial_persisted_state_refuses_reopen(tmp_path) -> None:
    signer = _signer()
    signed = _receipt(signer)
    ledger = _ledger(tmp_path, signer)
    ledger.append(signed, _evidence(signed.receipt.binding), verified_at_micros=3_100)
    with sqlite3.connect(ledger.path) as database:
        database.execute(
            "UPDATE development_receipt_event_v1 SET entry_digest=? WHERE sequence=1",
            (_digest("tampered"),),
        )
    with pytest.raises(audit.AuditFailure) as corrupt:
        _ledger(tmp_path, signer)
    assert corrupt.value.code is audit.AuditCode.STORE

    partial_path = tmp_path / "partial.sqlite3"
    partial = audit.DevelopmentEvidenceLedger(partial_path, (signer.verification_key,))
    with sqlite3.connect(partial.path) as database:
        database.execute(
            "INSERT INTO development_receipt_v1 "
            "(receipt_id,receipt_digest,body,signature,signing_key_id,public_key_digest) "
            "VALUES (?,?,?,?,?,?)",
            (
                signed.receipt.receipt_id,
                signed.receipt.receipt_digest,
                signed.receipt.canonical_bytes.decode(),
                signed.signature,
                signed.receipt.signing_key_id,
                signed.receipt.signing_public_key_digest,
            ),
        )
    with pytest.raises(audit.AuditFailure) as partial_failure:
        audit.DevelopmentEvidenceLedger(partial_path, (signer.verification_key,))
    assert partial_failure.value.code is audit.AuditCode.STORE


def test_invalid_persisted_lifecycle_transition_refuses_reopen(tmp_path) -> None:
    signer = _signer()
    signed = _receipt(signer)
    ledger = _ledger(tmp_path, signer)
    ledger.append(signed, _evidence(signed.receipt.binding), verified_at_micros=3_100)
    ledger.revoke(signed.receipt.receipt_id, _digest("first-reason"))
    with sqlite3.connect(ledger.path) as database:
        head = database.execute(
            "SELECT entry_digest FROM development_receipt_event_v1 "
            "ORDER BY sequence DESC LIMIT 1"
        ).fetchone()[0]
        payload = audit.canonical_json(
            {
                "kind": audit.LedgerEventKind.RECEIPT_REVOKED.value,
                "reason_digest": _digest("second-reason"),
                "receipt_id": signed.receipt.receipt_id,
                "related_receipt_id": None,
            }
        )
        payload_digest = audit.digest_bytes(payload)
        entry_digest = audit.digest_bytes(
            audit.canonical_json(
                {
                    "payload_digest": payload_digest,
                    "previous_entry_digest": head,
                }
            )
        )
        database.execute(
            "INSERT INTO development_receipt_event_v1 "
            "(kind,receipt_id,related_receipt_id,reason_digest,"
            "previous_entry_digest,payload,payload_digest,entry_digest) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                audit.LedgerEventKind.RECEIPT_REVOKED.value,
                signed.receipt.receipt_id,
                None,
                _digest("second-reason"),
                head,
                payload.decode("ascii"),
                payload_digest,
                entry_digest,
            ),
        )
    with pytest.raises(audit.AuditFailure) as invalid_transition:
        _ledger(tmp_path, signer)
    assert invalid_transition.value.code is audit.AuditCode.STORE


def test_key_revocation_and_failure_status_never_create_score_authority(
    tmp_path,
) -> None:
    signer = _signer()
    revoked_key = replace(signer.verification_key, revoked_at_micros=2_500)
    signed = _receipt(signer, status=audit.DevelopmentRunStatus.FAILED_INFRASTRUCTURE)
    ledger = audit.DevelopmentEvidenceLedger(
        tmp_path / "revoked.sqlite3", (revoked_key,)
    )
    with pytest.raises(audit.AuditFailure) as revoked:
        ledger.append(
            signed, _evidence(signed.receipt.binding), verified_at_micros=3_100
        )
    assert revoked.value.code is audit.AuditCode.STALE_KEY
    assert signed.receipt.score_eligible is False
    assert not hasattr(signed.receipt, "score")
    assert not hasattr(signed.receipt, "validator_hotkey")
