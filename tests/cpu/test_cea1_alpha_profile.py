import json

import pytest

from carbon.evidence_archive import (
    ALPHA_DEPLOYMENT_CONFIG_SCHEMA,
    ALPHA_LOGICAL_QUOTA_BYTES,
    ALPHA_MAX_ACTIVE_EVALUATIONS,
    ALPHA_MINIMUM_RETENTION_DAYS,
    ALPHA_PROFILE_ID,
    ALPHA_RESTORE_TARGET_SECONDS,
    AlphaArchiveProfile,
    AlphaCapacityDisposition,
    AlphaDeploymentConfiguration,
    AlphaExternalInput,
    AlphaNamedUse,
    AlphaPreflightReport,
    AlphaPreparationStatus,
    ArchiveCode,
    ArchiveFailure,
    ArtifactRequirement,
    ExecutionDisposition,
    assess_alpha_deployment,
    parse_alpha_deployment_configuration,
)


def _configuration_document(value=None):
    return {item.value: value for item in AlphaExternalInput}


def test_alpha_profile_freezes_owner_selected_policy_without_acknowledgement() -> None:
    profile = AlphaArchiveProfile()
    assert profile.profile_id == ALPHA_PROFILE_ID
    assert profile.named_uses == (
        AlphaNamedUse.INTERNAL_AUDIT,
        AlphaNamedUse.NON_PAYING_TESTNET_EVIDENCE,
    )
    assert profile.capacity.max_active_evaluations == ALPHA_MAX_ACTIVE_EVALUATIONS
    assert profile.capacity.logical_quota_bytes == ALPHA_LOGICAL_QUOTA_BYTES
    assert profile.retention.minimum_retention_days == ALPHA_MINIMUM_RETENTION_DAYS
    assert profile.restore_target_seconds == ALPHA_RESTORE_TARGET_SECONDS
    assert profile.acknowledgement_implemented is False
    assert profile.digest == (
        "sha256:e7f9b86943d482ad5c0e92c386a6edf3cdc493049f912c88f7e5a25d5eb6f49c"
    )
    rules = {rule.name: rule for rule in profile.artifact_rules}
    assert set(rules) == {
        "attempt_journal",
        "bounded_diagnostics",
        "checkpoint_index",
        "construction_plan",
        "derived_summary",
        "evidence_manifest",
        "outcome_account",
        "reconstruction_artifact",
        "reference_measurement",
        "runtime_manifest",
        "signed_receipt",
        "source_binding",
    }
    assert rules["attempt_journal"].is_required(ExecutionDisposition.CANCELLED)
    assert rules["signed_receipt"].is_required(ExecutionDisposition.COMPLETED)
    assert not rules["signed_receipt"].is_required(ExecutionDisposition.CANCELLED)
    assert (
        rules["bounded_diagnostics"].requirement is ArtifactRequirement.OPTIONAL_DEBUG
    )
    with pytest.raises(ArchiveFailure) as captured:
        AlphaArchiveProfile(acknowledgement_implemented=True)
    assert captured.value.code is ArchiveCode.DENIED


def test_alpha_capacity_exact_boundary_and_backpressure_are_pure_policy() -> None:
    capacity = AlphaArchiveProfile().capacity
    exact = capacity.assess(
        active_evaluations=0,
        reserved_bytes=0,
        declared_bytes=ALPHA_LOGICAL_QUOTA_BYTES,
    )
    assert exact.disposition is AlphaCapacityDisposition.RESERVED
    assert exact.active_evaluations_after == 1
    assert exact.reserved_bytes_after == ALPHA_LOGICAL_QUOTA_BYTES
    assert (
        capacity.assess(
            active_evaluations=1,
            reserved_bytes=1,
            declared_bytes=1,
        ).disposition
        is AlphaCapacityDisposition.BACKPRESSURE
    )
    assert (
        capacity.assess(
            active_evaluations=0,
            reserved_bytes=1,
            declared_bytes=ALPHA_LOGICAL_QUOTA_BYTES,
        ).disposition
        is AlphaCapacityDisposition.BACKPRESSURE
    )
    with pytest.raises(ArchiveFailure):
        capacity.assess(
            active_evaluations=False,
            reserved_bytes=0,
            declared_bytes=1,
        )


def test_alpha_retention_never_authorizes_deletion_with_open_obligations() -> None:
    retention = AlphaArchiveProfile().retention
    last_use = 1_000_000
    assert (
        retention.earliest_deletion_epoch_seconds(
            last_eligible_use_epoch_seconds=last_use,
            receipt_obligation_open=False,
            review_obligation_open=False,
            dispute_obligation_open=False,
        )
        == last_use + 90 * 86400
    )
    for position in range(3):
        flags = [False, False, False]
        flags[position] = True
        assert (
            retention.earliest_deletion_epoch_seconds(
                last_eligible_use_epoch_seconds=last_use,
                receipt_obligation_open=flags[0],
                review_obligation_open=flags[1],
                dispute_obligation_open=flags[2],
            )
            is None
        )
    assert (
        retention.earliest_deletion_epoch_seconds(
            last_eligible_use_epoch_seconds=None,
            receipt_obligation_open=False,
            review_obligation_open=False,
            dispute_obligation_open=False,
        )
        is None
    )


def test_alpha_configuration_is_closed_and_reports_every_external_input() -> None:
    encoded = json.dumps(_configuration_document()).encode("ascii")
    configuration = parse_alpha_deployment_configuration(encoded)
    assert configuration == AlphaDeploymentConfiguration()
    assert configuration.missing_inputs == tuple(AlphaExternalInput)
    report = assess_alpha_deployment(configuration, isolated_preflight_passed=True)
    assert report.schema_version == ALPHA_DEPLOYMENT_CONFIG_SCHEMA
    assert report.status is AlphaPreparationStatus.MISSING_EXTERNAL_INPUTS
    assert report.isolated_preflight_passed is True
    assert report.eligible_for_real_acknowledgement is False
    assert report.eligible_for_c_ea2 is False
    assert set(report.public_document()) == {
        "eligible_for_c_ea2",
        "eligible_for_real_acknowledgement",
        "isolated_preflight_passed",
        "missing_external_inputs",
        "profile_digest",
        "profile_id",
        "schema_version",
        "status",
    }


def test_complete_external_references_still_require_activation_implementation() -> None:
    document = {value.value: f"input:{value.value}" for value in AlphaExternalInput}
    configuration = parse_alpha_deployment_configuration(
        json.dumps(document).encode("ascii")
    )
    report = assess_alpha_deployment(configuration, isolated_preflight_passed=True)
    assert configuration.missing_inputs == ()
    assert report.status is AlphaPreparationStatus.ACTIVATION_IMPLEMENTATION_REQUIRED
    assert report.eligible_for_real_acknowledgement is False
    assert report.eligible_for_c_ea2 is False


@pytest.mark.parametrize(
    "payload",
    (
        b"{}",
        b'{"tenant_id":null,"tenant_id":null}',
        json.dumps({**_configuration_document(), "extra": None}).encode("ascii"),
        json.dumps({**_configuration_document(), "tenant_id": 7}).encode("ascii"),
    ),
)
def test_alpha_configuration_rejects_missing_duplicate_extra_and_typed_values(
    payload,
) -> None:
    with pytest.raises(ArchiveFailure) as captured:
        parse_alpha_deployment_configuration(payload)
    assert captured.value.code is ArchiveCode.INVALID


def test_preflight_report_cannot_be_relabelled_as_real_acknowledgement() -> None:
    with pytest.raises(ArchiveFailure):
        AlphaPreflightReport(
            "carbon.evidence-archive.alpha-preflight.v1",
            "sha256:" + "a" * 64,
            "carbon.evidence-archive.postgresql.v1",
            "carbon.evidence-archive.journal.v1",
            "sha256:" + "b" * 64,
            True,
            True,
            True,
            True,
            eligible_for_real_acknowledgement=True,
        )
