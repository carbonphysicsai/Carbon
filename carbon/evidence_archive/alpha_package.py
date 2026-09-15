"""Offline validator for the unprovisioned C-EA1 AWS deployment package."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from .alpha_activation import ALPHA_DEPLOYMENT_MANIFEST_SCHEMA
from .alpha_profile import ALPHA_LOGICAL_QUOTA_BYTES, ALPHA_PROFILE_ID
from .aws_provider import AWS_PROVIDER_PROFILE_ID
from .model import ArchiveCode, ArchiveFailure, canonical_bytes, content_digest

AWS_COST_SCHEMA = "carbon.evidence-archive.aws-cost-estimate.v2"
AWS_SOURCE_USE_SCHEMA = "carbon.evidence-archive.aws-source-use.v1"
AWS_OPERATION_MATRIX_SCHEMA = "carbon.evidence-archive.aws-operation-role-matrix.v1"
AWS_DEPLOYMENT_INPUTS_SCHEMA = "carbon.evidence-archive.aws-deployment-inputs.v1"
AWS_JSON_SCHEMA = "carbon.evidence-archive.json-schema.v1"
AWS_PACKAGE_SCHEMA = "carbon.evidence-archive.aws-package-report.v2"
MAX_PACKAGE_FILE_BYTES = 512 * 1024


def _statements(resources: dict[str, Any], role: str) -> dict[str, dict[str, Any]]:
    try:
        values = resources[role]["Properties"]["Policies"][0]["PolicyDocument"][
            "Statement"
        ]
    except (KeyError, IndexError, TypeError):
        raise ArchiveFailure(ArchiveCode.CONFLICT) from None
    if (
        type(values) is not list
        or any(
            type(value) is not dict or type(value.get("Sid")) is not str
            for value in values
        )
        or len({value["Sid"] for value in values}) != len(values)
    ):
        raise ArchiveFailure(ArchiveCode.CONFLICT)
    return {value["Sid"]: value for value in values}


def _indexed_statements(values: object) -> dict[str, dict[str, Any]]:
    if (
        type(values) is not list
        or any(
            type(value) is not dict or type(value.get("Sid")) is not str
            for value in values
        )
        or len({value["Sid"] for value in values}) != len(values)
    ):
        raise ArchiveFailure(ArchiveCode.CONFLICT)
    return {value["Sid"]: value for value in values}


def _validate_template_contract(resources: dict[str, Any]) -> None:
    try:
        keys = (resources["StorageKey"], resources["ArchiveKey"])
        storage_key_policy = _indexed_statements(
            resources["StorageKey"]["Properties"]["KeyPolicy"]["Statement"]
        )
        envelope_key_policy = json.dumps(
            resources["ArchiveKey"]["Properties"]["KeyPolicy"], sort_keys=True
        )
        bucket_key = resources["EvidenceBucket"]["Properties"]["BucketEncryption"][
            "ServerSideEncryptionConfiguration"
        ][0]["ServerSideEncryptionByDefault"]["KMSMasterKeyID"]
        supervisor = _statements(resources, "SupervisorRuntimeRole")
        audit = _statements(resources, "AuditRuntimeRole")
        recovery_control = _statements(resources, "RecoveryControlRole")
        kms_endpoint = _indexed_statements(
            resources["KmsInterfaceEndpoint"]["Properties"]["PolicyDocument"][
                "Statement"
            ]
        )
    except (KeyError, IndexError, TypeError):
        raise ArchiveFailure(ArchiveCode.CONFLICT) from None
    if (
        any(
            value.get("DeletionPolicy") != "Retain"
            or value.get("UpdateReplacePolicy") != "Retain"
            for value in keys
        )
        or bucket_key != {"Fn::GetAtt": ["StorageKey", "Arn"]}
        or storage_key_policy.get("OperatorAwsResourceGrants", {}).get("Action")
        != "kms:CreateGrant"
        or storage_key_policy.get("OperatorAwsResourceGrants", {})
        .get("Condition", {})
        .get("Bool", {})
        .get("kms:GrantIsForAWSResource")
        != "true"
        or "OperatorAwsResourceGrants" in envelope_key_policy
        or "Condition" in supervisor.get("BucketMetadata", {})
        or "s3:GetObjectVersion"
        not in supervisor.get("TenantObjects", {}).get("Action", [])
        or supervisor.get("EnvelopeOperations", {}).get("Resource")
        != {"Fn::GetAtt": ["ArchiveKey", "Arn"]}
        or "Condition" in supervisor.get("DescribeKeys", {})
        or "logs:PutLogEvents"
        not in supervisor.get("SanitizedDiagnostics", {}).get("Action", [])
        or "ArchiveKey" in json.dumps(audit, sort_keys=True)
        or recovery_control.get("PassExactRestoreServiceRole", {})
        .get("Condition", {})
        .get("StringEquals", {})
        .get("iam:PassedToService")
        != "backup.amazonaws.com"
        or kms_endpoint.get("AuditStorageDecryptOnly", {}).get("Resource")
        != {"Fn::GetAtt": ["StorageKey", "Arn"]}
        or "kms:GenerateDataKey"
        in kms_endpoint.get("AuditStorageDecryptOnly", {}).get("Action", [])
        or "kms:GenerateDataKey"
        in kms_endpoint.get("RecoveryDecryptOnly", {}).get("Action", [])
    ):
        raise ArchiveFailure(ArchiveCode.CONFLICT)


def _validate_deployment_example(
    document: dict[str, Any], cost: dict[str, Any]
) -> None:
    account = document.get("account_id")
    principals = document.get("principals")
    network = document.get("network")
    spending = document.get("spending")
    evidence = document.get("external_evidence")
    if (
        set(document)
        != {
            "schema_version",
            "provider_profile_id",
            "fixture_only",
            "deployment_authorized",
            "account_id",
            "region",
            "stack_name",
            "tenant_id",
            "project_tags",
            "network",
            "execution",
            "principals",
            "custody",
            "spending",
            "external_evidence",
        }
        or type(account) is not str
        or len(account) != 12
        or not account.isdigit()
        or type(principals) is not dict
        or any(
            type(value) is not str or not value.startswith(f"arn:aws:iam::{account}:")
            for value in principals.values()
        )
        or type(network) is not dict
        or type(network.get("private_subnet_ids")) is not list
        or len(network["private_subnet_ids"]) != 2
        or len(set(network["private_subnet_ids"])) != 2
        or type(spending) is not dict
        or spending.get("monthly_usd")
        != cost.get("corrected_monthly_authorization_request")
        or spending.get("rehearsal_usd")
        != cost.get("rehearsal", {}).get("corrected_authorization_request")
        or type(evidence) is not dict
        or any(value is not None for value in evidence.values())
    ):
        raise ArchiveFailure(ArchiveCode.CONFLICT)


def _validate_operation_matrix(document: dict[str, Any]) -> None:
    operations = document.get("operations")
    limitations = document.get("limitations")
    required = {
        "operation",
        "caller",
        "resource",
        "permissions",
        "encryption_context",
        "network_path",
        "expected_denial",
    }
    if (
        set(document)
        != {"schema_version", "provider_profile_id", "operations", "limitations"}
        or type(operations) is not list
        or not operations
        or any(
            type(value) is not dict
            or set(value) != required
            or type(value["operation"]) is not str
            or type(value["permissions"]) is not list
            or not value["permissions"]
            or any(type(permission) is not str for permission in value["permissions"])
            or any(
                type(value[field]) is not str or not value[field]
                for field in required - {"permissions"}
            )
            for value in operations
        )
        or len({value["operation"] for value in operations}) != len(operations)
        or type(limitations) is not list
        or not limitations
        or any(type(value) is not str or not value for value in limitations)
    ):
        raise ArchiveFailure(ArchiveCode.CONFLICT)


def _load_closed_json(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    if not 1 <= len(payload) <= MAX_PACKAGE_FILE_BYTES:
        raise ArchiveFailure(ArchiveCode.INVALID)

    def closed(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ArchiveFailure(ArchiveCode.INVALID)
            result[key] = value
        return result

    try:
        document = json.loads(payload, object_pairs_hook=closed)
    except (UnicodeDecodeError, json.JSONDecodeError, ArchiveFailure):
        raise ArchiveFailure(ArchiveCode.INVALID) from None
    if type(document) is not dict:
        raise ArchiveFailure(ArchiveCode.INVALID)
    return document


@dataclass(frozen=True, slots=True)
class AlphaAwsPackageReport:
    schema_version: str
    deployment_manifest_digest: str
    cloudformation_template_digest: str
    database_roles_digest: str
    cost_estimate_digest: str
    source_use_manifest_digest: str
    incremental_archive_monthly_estimate_usd: float
    complete_monthly_estimate_usd: float
    previous_monthly_proposal_usd: float
    corrected_monthly_authorization_request_usd: float
    calculated_rehearsal_estimate_usd: float
    rehearsal_authorization_request_usd: float
    retained_after_rollback_monthly_estimate_usd: float
    deployment_authorized: bool = False
    recovery_rehearsed: bool = False
    eligible_for_real_acknowledgement: bool = False
    eligible_for_c_ea2: bool = False

    def public_document(self) -> dict[str, object]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


def validate_aws_package(root: Path) -> AlphaAwsPackageReport:
    root = Path(root)
    manifest_path = root / "deployment_manifest.json"
    template_path = root / "template.json"
    roles_path = root / "database_roles.sql"
    cost_path = root / "cost_estimate.json"
    source_use_path = root / "source_use_manifest.json"
    operation_matrix_path = root / "operation_role_matrix.json"
    deployment_schema_path = root / "deployment_inputs.schema.json"
    deployment_example_path = root / "deployment_inputs.example.json"
    manifest = _load_closed_json(manifest_path)
    template = _load_closed_json(template_path)
    cost = _load_closed_json(cost_path)
    source_use = _load_closed_json(source_use_path)
    operation_matrix = _load_closed_json(operation_matrix_path)
    deployment_schema = _load_closed_json(deployment_schema_path)
    deployment_example = _load_closed_json(deployment_example_path)
    roles = roles_path.read_bytes()
    if not 1 <= len(roles) <= MAX_PACKAGE_FILE_BYTES:
        raise ArchiveFailure(ArchiveCode.INVALID)
    limits = manifest.get("limits")
    resources = template.get("Resources")
    acknowledgement = manifest.get("acknowledgement")
    template_digest = content_digest(
        "carbon.evidence-archive.cloudformation.v1", canonical_bytes(template)
    )
    roles_digest = content_digest("carbon.evidence-archive.database-roles.v1", roles)
    cost_digest = content_digest(AWS_COST_SCHEMA, canonical_bytes(cost))
    source_use_digest = content_digest(
        AWS_SOURCE_USE_SCHEMA, canonical_bytes(source_use)
    )
    operation_matrix_digest = content_digest(
        AWS_OPERATION_MATRIX_SCHEMA, canonical_bytes(operation_matrix)
    )
    deployment_schema_digest = content_digest(
        AWS_JSON_SCHEMA, canonical_bytes(deployment_schema)
    )
    deployment_example_digest = content_digest(
        AWS_DEPLOYMENT_INPUTS_SCHEMA, canonical_bytes(deployment_example)
    )
    if (
        manifest.get("schema_version") != ALPHA_DEPLOYMENT_MANIFEST_SCHEMA
        or manifest.get("profile_id") != ALPHA_PROFILE_ID
        or manifest.get("provider_profile_id") != AWS_PROVIDER_PROFILE_ID
        or manifest.get("deployment_state") != "UNPROVISIONED_REVIEW_PACKAGE"
        or type(limits) is not dict
        or limits.get("logical_evidence_bytes") != ALPHA_LOGICAL_QUOTA_BYTES
        or acknowledgement
        != {
            "implemented": False,
            "eligible": False,
            "reason": "deployment, recovery rehearsal, security acceptance and authorized issuer remain absent",
        }
        or template.get("AWSTemplateFormatVersion") != "2010-09-09"
        or type(resources) is not dict
        or {
            "ArchiveKey",
            "StorageKey",
            "EvidenceBucket",
            "Catalogue",
            "S3GatewayEndpoint",
            "KmsInterfaceEndpoint",
            "StsInterfaceEndpoint",
            "SecretsManagerInterfaceEndpoint",
            "BackupInterfaceEndpoint",
            "LogsInterfaceEndpoint",
            "DiagnosticLogGroup",
            "BackupPlan",
            "BackupRestoreServiceRole",
            "RecoveryControlRole",
        }
        - set(resources)
        or cost.get("schema_version") != AWS_COST_SCHEMA
        or cost.get("region") != manifest.get("recommended_region")
        or source_use.get("schema_version") != AWS_SOURCE_USE_SCHEMA
        or operation_matrix.get("schema_version") != AWS_OPERATION_MATRIX_SCHEMA
        or operation_matrix.get("provider_profile_id") != AWS_PROVIDER_PROFILE_ID
        or deployment_schema.get("$id") != AWS_DEPLOYMENT_INPUTS_SCHEMA
        or deployment_schema.get("properties", {})
        .get("deployment_authorized", {})
        .get("type")
        != "boolean"
        or "operator_control_plane_connectivity_ref"
        not in deployment_schema.get("properties", {})
        .get("execution", {})
        .get("required", [])
        or deployment_example.get("schema_version") != AWS_DEPLOYMENT_INPUTS_SCHEMA
        or deployment_example.get("provider_profile_id") != AWS_PROVIDER_PROFILE_ID
        or deployment_example.get("fixture_only") is not True
        or deployment_example.get("deployment_authorized") is not False
        or manifest.get("components")
        != {
            "cloudformation_template_digest": template_digest,
            "database_roles_digest": roles_digest,
            "cost_estimate_digest": cost_digest,
            "source_use_manifest_digest": source_use_digest,
            "operation_role_matrix_digest": operation_matrix_digest,
            "deployment_inputs_schema_digest": deployment_schema_digest,
            "deployment_inputs_example_digest": deployment_example_digest,
        }
    ):
        raise ArchiveFailure(ArchiveCode.CONFLICT)
    _validate_template_contract(resources)
    _validate_deployment_example(deployment_example, cost)
    _validate_operation_matrix(operation_matrix)
    rates = cost.get("incremental_archive_rates")
    additions = cost.get("complete_additions")
    if (
        type(rates) is not list
        or not rates
        or any(type(item) is not dict for item in rates)
        or type(additions) is not list
        or not additions
        or any(type(item) is not dict for item in additions)
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    incremental = round(sum(float(item["subtotal"]) for item in rates), 3)
    complete = round(
        incremental + sum(float(item["subtotal"]) for item in additions), 3
    )
    if incremental != cost.get(
        "incremental_archive_monthly_estimate"
    ) or complete != cost.get("complete_monthly_estimate"):
        raise ArchiveFailure(ArchiveCode.CONFLICT)
    for key in (
        "incremental_archive_monthly_estimate",
        "complete_monthly_estimate",
        "previous_monthly_proposal",
        "corrected_monthly_authorization_request",
        "retained_after_rollback_monthly_estimate",
    ):
        if type(cost.get(key)) not in {int, float} or cost[key] < 0:
            raise ArchiveFailure(ArchiveCode.INVALID)
    rehearsal = cost.get("rehearsal")
    if (
        type(rehearsal) is not dict
        or type(rehearsal.get("calculated_provider_estimate")) not in {int, float}
        or type(rehearsal.get("corrected_authorization_request")) not in {int, float}
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    return AlphaAwsPackageReport(
        AWS_PACKAGE_SCHEMA,
        content_digest(ALPHA_DEPLOYMENT_MANIFEST_SCHEMA, canonical_bytes(manifest)),
        template_digest,
        roles_digest,
        cost_digest,
        source_use_digest,
        float(cost["incremental_archive_monthly_estimate"]),
        float(cost["complete_monthly_estimate"]),
        float(cost["previous_monthly_proposal"]),
        float(cost["corrected_monthly_authorization_request"]),
        float(rehearsal["calculated_provider_estimate"]),
        float(rehearsal["corrected_authorization_request"]),
        float(cost["retained_after_rollback_monthly_estimate"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the unprovisioned C-EA1 AWS package without credentials or network."
    )
    parser.add_argument("package", type=Path)
    arguments = parser.parse_args()
    report = validate_aws_package(arguments.package)
    print(json.dumps(report.public_document(), sort_keys=True, separators=(",", ":")))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
