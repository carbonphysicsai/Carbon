from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from carbon.evidence_archive import (
    ALPHA_PROFILE_ID,
    AWS_PROVIDER_PROFILE_ID,
    AlphaActivationEvidence,
    AlphaActivationPredicate,
    AlphaActivationStatus,
    AlphaArchiveProfile,
    AlphaDeploymentConfiguration,
    AlphaExternalInput,
    AlphaPredicateEvidence,
    AlphaRecoveryIssue,
    AlphaRecoveryObject,
    AlphaRecoveryObservation,
    AlphaRecoveryWatermark,
    ArchiveCode,
    ArchiveFailure,
    AwsArchiveConfiguration,
    AwsKmsDataKeyService,
    AwsRdsIamConfiguration,
    AwsRdsIamConnectionFactory,
    S3ImmutableObjectStore,
    assess_alpha_activation,
    assess_recovery_watermark,
    derive_object_key,
    parse_recovery_observation,
    parse_recovery_watermark,
)
from carbon.evidence_archive.alpha_package import validate_aws_package

PACKAGE_ROOT = Path("deploy/evidence_archive/aws_private_alpha")


class ProviderError(Exception):
    def __init__(self, code: str):
        self.response = {"Error": {"Code": code}}


class FakeS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.versions: dict[str, str] = {}
        self.tags: dict[str, object] = {}
        self.retention = datetime.fromtimestamp(1_000_000, UTC)
        self.legal_hold = "OFF"

    def put_object(self, **request):
        key = request["Key"]
        if key in self.objects:
            raise ProviderError("PreconditionFailed")
        self.objects[key] = request["Body"]
        self.versions[key] = "version+/=1"
        assert request["IfNoneMatch"] == "*"
        assert request["ServerSideEncryption"] == "aws:kms"
        assert request["ChecksumSHA256"]
        return {
            "VersionId": self.versions[key],
            "ChecksumSHA256": request["ChecksumSHA256"],
        }

    def get_object(self, **request):
        body = self.objects[request["Key"]]
        if "VersionId" in request:
            assert request["VersionId"] == self.versions[request["Key"]]
        return {"ContentLength": len(body), "Body": io.BytesIO(body)}

    def head_object(self, **request):
        body = self.objects[request["Key"]]
        return {
            "VersionId": self.versions[request["Key"]],
            "ChecksumSHA256": base64.b64encode(hashlib.sha256(body).digest()).decode(
                "ascii"
            ),
        }

    def list_objects_v2(self, **request):
        return {
            "Contents": [
                {"Key": key}
                for key in sorted(self.objects)
                if key.startswith(request["Prefix"])
            ],
            "IsTruncated": False,
        }

    def put_object_tagging(self, **request):
        self.tags[request["Key"]] = request["Tagging"]

    def get_object_retention(self, **request):
        assert request["VersionId"] == self.versions[request["Key"]]
        return {
            "Retention": {
                "Mode": "COMPLIANCE",
                "RetainUntilDate": self.retention,
            }
        }

    def put_object_retention(self, **request):
        self.retention = request["Retention"]["RetainUntilDate"]

    def get_object_legal_hold(self, **request):
        return {"LegalHold": {"Status": self.legal_hold}}

    def put_object_legal_hold(self, **request):
        self.legal_hold = request["LegalHold"]["Status"]


class FakeKms:
    def __init__(self, key_arn: str):
        self.key_arn = key_arn
        self.plaintext = b"k" * 32
        self.wrapped = b"wrapped-data-key"
        self.context = None

    def generate_data_key(self, **request):
        self.context = request["EncryptionContext"]
        return {
            "Plaintext": self.plaintext,
            "CiphertextBlob": self.wrapped,
            "KeyId": self.key_arn,
        }

    def decrypt(self, **request):
        assert request["EncryptionContext"] == self.context
        return {"Plaintext": self.plaintext, "KeyId": self.key_arn}


class FakeRds:
    def __init__(self):
        self.request = None

    def generate_db_auth_token(self, **request):
        self.request = request
        return "short-lived-non-secret-test-token"


def _configuration(*, max_object_bytes: int = 1024) -> AwsArchiveConfiguration:
    return AwsArchiveConfiguration(
        region="us-west-2",
        bucket="carbon-alpha-evidence-123456789012",
        expected_bucket_owner="123456789012",
        storage_kms_key_arn=(
            "arn:aws:kms:us-west-2:123456789012:"
            "key/12345678-1234-1234-1234-123456789012"
        ),
        envelope_kms_key_arn=(
            "arn:aws:kms:us-west-2:123456789012:"
            "key/87654321-4321-4321-4321-210987654321"
        ),
        tenant_id="carbon-alpha",
        max_object_bytes=max_object_bytes,
    )


def _object_key() -> str:
    return derive_object_key(
        "carbon-alpha",
        "sha256:" + "a" * 64,
        "source_binding",
        "sha256:" + "b" * 64,
    )


def test_s3_adapter_is_immutable_bounded_and_tenant_scoped() -> None:
    client = FakeS3()
    store = S3ImmutableObjectStore(client, _configuration())
    key = _object_key()
    created = store.put_immutable_with_receipt(key, b"ciphertext")
    assert created.created is True
    assert created.version_id == "version+/=1"
    assert (
        created.checksum_sha256 == "sha256:" + hashlib.sha256(b"ciphertext").hexdigest()
    )
    assert store.put_immutable(key, b"ciphertext") is False
    with pytest.raises(ArchiveFailure) as conflict:
        store.put_immutable(key, b"changed")
    assert conflict.value.code is ArchiveCode.CONFLICT
    assert store.get(key) == b"ciphertext"
    assert store.get_version(key, created.version_id) == b"ciphertext"
    retention = store.apply_version_retention(
        key,
        created.version_id,
        retain_until_epoch_seconds=2_000_000,
        obligation_hold=True,
    )
    assert retention.retain_until_epoch_seconds == 2_000_000
    assert retention.obligation_hold is True
    assert client.legal_hold == "ON"
    retained = store.apply_version_retention(
        key,
        created.version_id,
        retain_until_epoch_seconds=1_500_000,
        obligation_hold=False,
    )
    assert retained.retain_until_epoch_seconds == 2_000_000
    assert client.legal_hold == "OFF"
    assert store.list_keys("carbon-alpha") == (key,)
    quarantine_ref = store.quarantine(key)
    assert quarantine_ref.startswith("sha256:")
    assert client.tags
    with pytest.raises(ArchiveFailure) as denied:
        store.list_keys("other-tenant")
    assert denied.value.code is ArchiveCode.DENIED


def test_s3_adapter_caps_request_and_response_bytes() -> None:
    client = FakeS3()
    store = S3ImmutableObjectStore(client, _configuration(max_object_bytes=8))
    with pytest.raises(ArchiveFailure) as oversized:
        store.put_immutable(_object_key(), b"123456789")
    assert oversized.value.code is ArchiveCode.CAPACITY
    client.objects["carbon-alpha-v1/" + _object_key()] = b"123456789"
    with pytest.raises(ArchiveFailure) as response:
        store.get(_object_key())
    assert response.value.code is ArchiveCode.CAPACITY


def test_kms_data_key_is_context_bound_and_only_wrapped_bytes_are_recoverable() -> None:
    configuration = _configuration()
    client = FakeKms(configuration.envelope_kms_key_arn)
    service = AwsKmsDataKeyService(client, configuration)
    lease = service.generate(archive_entry_id="sha256:" + "a" * 64)
    assert lease.key.key_bytes == b"k" * 32
    assert lease.encrypted_key == b"wrapped-data-key"
    assert lease.wrapped_key_digest.startswith("sha256:")
    assert dict(lease.encryption_context)["carbon:profile"] == AWS_PROVIDER_PROFILE_ID
    assert (
        service.recover(
            archive_entry_id="sha256:" + "a" * 64,
            encrypted_key=lease.encrypted_key,
        )
        == lease.key
    )
    assert configuration.storage_kms_key_arn != configuration.envelope_kms_key_arn


def test_rds_connection_factory_uses_fresh_iam_token_and_verified_tls(
    monkeypatch,
) -> None:
    client = FakeRds()
    configuration = AwsRdsIamConfiguration(
        region="us-west-2",
        hostname="catalogue.example.us-west-2.rds.amazonaws.com",
        port=5432,
        database="carbon_archive",
        username="carbon_archive_supervisor",
    )
    observed = {}
    sentinel = object()

    def connect(**request):
        observed.update(request)
        return sentinel

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=connect))
    assert AwsRdsIamConnectionFactory(client, configuration)() is sentinel
    assert client.request == {
        "DBHostname": configuration.hostname,
        "Port": 5432,
        "DBUsername": configuration.username,
        "Region": "us-west-2",
    }
    assert observed == {
        "host": configuration.hostname,
        "port": 5432,
        "dbname": "carbon_archive",
        "user": "carbon_archive_supervisor",
        "password": "short-lived-non-secret-test-token",
        "sslmode": "verify-full",
        "connect_timeout": 5,
    }


def test_activation_predicates_remain_non_acknowledging() -> None:
    configuration = AlphaDeploymentConfiguration(
        **{value.value: f"input:{value.value}" for value in AlphaExternalInput}
    )
    predicates = tuple(
        AlphaPredicateEvidence(value, f"evidence:{value.value}", True)
        for value in AlphaActivationPredicate
    )
    evidence = AlphaActivationEvidence(
        AlphaArchiveProfile().digest,
        AWS_PROVIDER_PROFILE_ID,
        "sha256:" + "d" * 64,
        predicates,
    )
    readiness = assess_alpha_activation(configuration, evidence)
    assert (
        readiness.status
        is AlphaActivationStatus.ACKNOWLEDGEMENT_IMPLEMENTATION_REQUIRED
    )
    assert readiness.missing_predicates == ()
    assert readiness.eligible_for_real_acknowledgement is False
    assert readiness.eligible_for_c_ea2 is False
    assert readiness.public_document()["eligible_for_c_ea2"] is False
    assert AlphaArchiveProfile().profile_id == ALPHA_PROFILE_ID


def test_activation_distinguishes_rehearsal_and_external_acceptance() -> None:
    configuration = AlphaDeploymentConfiguration(
        **{value.value: f"input:{value.value}" for value in AlphaExternalInput}
    )
    without_rehearsal = tuple(
        AlphaPredicateEvidence(
            value,
            f"evidence:{value.value}",
            value is not AlphaActivationPredicate.RECOVERY_REHEARSAL,
        )
        for value in AlphaActivationPredicate
    )
    evidence = AlphaActivationEvidence(
        AlphaArchiveProfile().digest,
        AWS_PROVIDER_PROFILE_ID,
        "sha256:" + "e" * 64,
        without_rehearsal,
    )
    assert (
        assess_alpha_activation(configuration, evidence).status
        is AlphaActivationStatus.REHEARSAL_REQUIRED
    )


def test_recovery_watermark_rejects_an_older_or_incomplete_subset() -> None:
    def digest(character):
        return "sha256:" + character * 64

    recovered_object = AlphaRecoveryObject(
        digest("a"),
        "evidence_manifest",
        "carbon-alpha-v1/v1/tenant/object.bin",
        "version-1",
        digest("b"),
        digest("c"),
        digest("d"),
        "arn:aws:kms:us-west-2:123456789012:key/87654321-4321-4321-4321-210987654321",
        digest("e"),
    )
    watermark = AlphaRecoveryWatermark(
        AlphaArchiveProfile().digest,
        digest("f"),
        "arn:aws:backup:us-west-2:123456789012:recovery-point:test",
        12,
        11,
        10,
        (digest("1"),),
        (digest("2"),),
        (digest("3"),),
        (digest("4"),),
        (recovered_object,),
    )
    complete = AlphaRecoveryObservation(
        watermark.digest,
        watermark.catalogue_recovery_point_ref,
        12,
        11,
        10,
        watermark.outbox_event_refs,
        watermark.acknowledgement_refs,
        watermark.manifest_refs,
        watermark.signature_refs,
        watermark.objects,
        (recovered_object.wrapped_key_digest,),
        3600,
    )
    accepted = assess_recovery_watermark(watermark, complete)
    assert accepted.provisional_rehearsal_passed is True
    assert accepted.eligible_for_real_acknowledgement is False
    assert accepted.eligible_for_c_ea2 is False
    encoded_watermark = json.dumps(watermark.document()).encode()
    encoded_observation = json.dumps(complete.document()).encode()
    assert parse_recovery_watermark(encoded_watermark) == watermark
    assert parse_recovery_observation(encoded_observation) == complete
    with pytest.raises(ArchiveFailure):
        parse_recovery_watermark(
            encoded_watermark.replace(
                b'"schema_version":',
                b'"schema_version":"duplicate","schema_version":',
                1,
            )
        )

    older = AlphaRecoveryObservation(
        watermark.digest,
        watermark.catalogue_recovery_point_ref,
        11,
        10,
        9,
        (),
        (),
        (),
        (),
        (),
        (),
        1800,
    )
    rejected = assess_recovery_watermark(watermark, older)
    assert rejected.provisional_rehearsal_passed is False
    assert set(rejected.issues) == {
        AlphaRecoveryIssue.CATALOGUE_COMMIT_BEHIND,
        AlphaRecoveryIssue.JOURNAL_BEHIND,
        AlphaRecoveryIssue.CAPACITY_LEDGER_BEHIND,
        AlphaRecoveryIssue.OUTBOX_INCOMPLETE,
        AlphaRecoveryIssue.ACKNOWLEDGEMENTS_INCOMPLETE,
        AlphaRecoveryIssue.MANIFESTS_INCOMPLETE,
        AlphaRecoveryIssue.SIGNATURES_INCOMPLETE,
        AlphaRecoveryIssue.OBJECT_VERSION_SET_MISMATCH,
        AlphaRecoveryIssue.ENVELOPE_KEYS_INCOMPLETE,
    }


def test_deployment_package_is_bound_and_fail_closed() -> None:
    report = validate_aws_package(PACKAGE_ROOT)
    assert report.incremental_archive_monthly_estimate_usd == 140.628
    assert report.complete_monthly_estimate_usd == 155.022
    assert report.previous_monthly_proposal_usd == 55.0
    assert report.corrected_monthly_authorization_request_usd == 175.0
    assert report.calculated_rehearsal_estimate_usd == 1.15
    assert report.rehearsal_authorization_request_usd == 5.0
    assert report.retained_after_rollback_monthly_estimate_usd == 6.49
    assert report.deployment_authorized is False
    assert report.recovery_rehearsed is False
    assert report.eligible_for_real_acknowledgement is False
    assert report.eligible_for_c_ea2 is False

    template = json.loads((PACKAGE_ROOT / "template.json").read_text())
    bucket = template["Resources"]["EvidenceBucket"]
    catalogue = template["Resources"]["Catalogue"]
    envelope_key = template["Resources"]["ArchiveKey"]
    storage_key = template["Resources"]["StorageKey"]
    assert bucket["DeletionPolicy"] == "Retain"
    assert bucket["Properties"]["VersioningConfiguration"] == {"Status": "Enabled"}
    assert bucket["Properties"]["ObjectLockConfiguration"]["Rule"][
        "DefaultRetention"
    ] == {"Mode": "COMPLIANCE", "Days": 90}
    assert set(bucket["Properties"]["PublicAccessBlockConfiguration"].values()) == {
        True
    }
    assert catalogue["DeletionPolicy"] == "Snapshot"
    assert catalogue["Properties"]["MultiAZ"] is True
    assert catalogue["Properties"]["PubliclyAccessible"] is False
    assert catalogue["Properties"]["StorageEncrypted"] is True
    assert catalogue["Properties"]["EnableIAMDatabaseAuthentication"] is True
    assert catalogue["Properties"]["DBInstanceClass"] == {"Ref": "DBInstanceClass"}
    assert template["Parameters"]["DBInstanceClass"]["AllowedValues"] == [
        "db.t4g.medium"
    ]
    for retained_key in (envelope_key, storage_key):
        assert retained_key["DeletionPolicy"] == "Retain"
        assert retained_key["UpdateReplacePolicy"] == "Retain"
    assert catalogue["Properties"]["KmsKeyId"] == {"Fn::GetAtt": ["StorageKey", "Arn"]}
    assert bucket["Properties"]["BucketEncryption"][
        "ServerSideEncryptionConfiguration"
    ][0]["ServerSideEncryptionByDefault"]["KMSMasterKeyID"] == {
        "Fn::GetAtt": ["StorageKey", "Arn"]
    }
    encoded = json.dumps(template, sort_keys=True)
    assert "SupervisorRuntimeRole" in template["Resources"]
    assert "AuditRuntimeRole" in template["Resources"]
    assert "RecoveryRuntimeRole" in template["Resources"]
    assert "rds-db:connect" in encoded
    assert "s3:DeleteObject" not in encoded
    assert "kms:ScheduleKeyDeletion" in encoded
    assert "s3:GetObjectVersion" in encoded
    assert "s3:PutObjectLegalHold" in encoded
    assert "iam:PassedToService" in encoded
    assert "AWSBackupServiceRolePolicyForRestores" in encoded

    supervisor = template["Resources"]["SupervisorRuntimeRole"]["Properties"][
        "Policies"
    ][0]["PolicyDocument"]["Statement"]
    by_sid = {statement["Sid"]: statement for statement in supervisor}
    assert "Condition" not in by_sid["BucketMetadata"]
    assert by_sid["EnvelopeOperations"]["Resource"] == {
        "Fn::GetAtt": ["ArchiveKey", "Arn"]
    }
    assert (
        "kms:EncryptionContext:carbon:profile"
        in by_sid["EnvelopeOperations"]["Condition"]["StringEquals"]
    )
    assert "Condition" not in by_sid["DescribeKeys"]
    assert by_sid["S3StorageKey"]["Condition"]["StringEquals"]["kms:ViaService"] == {
        "Fn::Sub": "s3.${AWS::Region}.amazonaws.com"
    }

    audit = template["Resources"]["AuditRuntimeRole"]["Properties"]["Policies"][0][
        "PolicyDocument"
    ]["Statement"]
    audit_encoded = json.dumps(audit, sort_keys=True)
    assert "ArchiveKey" not in audit_encoded
    assert "kms:GenerateDataKey" not in audit_encoded

    storage_key_policy = storage_key["Properties"]["KeyPolicy"]["Statement"]
    storage_key_by_sid = {
        statement["Sid"]: statement for statement in storage_key_policy
    }
    assert (
        storage_key_by_sid["OperatorAwsResourceGrants"]["Action"] == "kms:CreateGrant"
    )
    assert storage_key_by_sid["OperatorAwsResourceGrants"]["Condition"] == {
        "Bool": {"kms:GrantIsForAWSResource": "true"}
    }
    envelope_key_encoded = json.dumps(envelope_key["Properties"]["KeyPolicy"])
    assert "OperatorAwsResourceGrants" not in envelope_key_encoded

    endpoint = template["Resources"]["KmsInterfaceEndpoint"]["Properties"][
        "PolicyDocument"
    ]["Statement"]
    endpoint_by_sid = {statement["Sid"]: statement for statement in endpoint}
    assert endpoint_by_sid["AuditStorageDecryptOnly"]["Resource"] == {
        "Fn::GetAtt": ["StorageKey", "Arn"]
    }
    assert (
        "kms:GenerateDataKey"
        not in endpoint_by_sid["AuditStorageDecryptOnly"]["Action"]
    )
    assert "kms:GenerateDataKey" not in endpoint_by_sid["RecoveryDecryptOnly"]["Action"]

    logs_endpoint = template["Resources"]["LogsInterfaceEndpoint"]["Properties"]
    assert logs_endpoint["ServiceName"] == {
        "Fn::Sub": "com.amazonaws.${AWS::Region}.logs"
    }
    assert "logs:PutLogEvents" in by_sid["SanitizedDiagnostics"]["Action"]
    assert "AuditRuntimeRole" not in json.dumps(logs_endpoint["PolicyDocument"])

    runbook = Path("docs/development/EVIDENCE_ARCHIVE_AWS_PRIVATE_ALPHA.md").read_text()
    assert "execute-change-set" in runbook
    assert "--disable-rollback" in runbook
    assert "Catalogue.DeletionProtection=true" in runbook


def test_deployment_package_rejects_changed_bound_component(tmp_path: Path) -> None:
    candidate = tmp_path / "package"
    shutil.copytree(PACKAGE_ROOT, candidate)
    cost_path = candidate / "cost_estimate.json"
    cost = json.loads(cost_path.read_text())
    cost["corrected_monthly_authorization_request"] = 164.0
    cost_path.write_text(json.dumps(cost))
    with pytest.raises(ArchiveFailure) as changed:
        validate_aws_package(candidate)
    assert changed.value.code is ArchiveCode.CONFLICT
