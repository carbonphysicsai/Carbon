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

AWS_COST_SCHEMA = "carbon.evidence-archive.aws-cost-estimate.v1"
AWS_SOURCE_USE_SCHEMA = "carbon.evidence-archive.aws-source-use.v1"
AWS_PACKAGE_SCHEMA = "carbon.evidence-archive.aws-package-report.v1"
MAX_PACKAGE_FILE_BYTES = 512 * 1024


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
    monthly_estimate_usd: float
    monthly_budget_recommendation_usd: float
    one_off_rehearsal_estimate_usd: float
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
    manifest = _load_closed_json(manifest_path)
    template = _load_closed_json(template_path)
    cost = _load_closed_json(cost_path)
    source_use = _load_closed_json(source_use_path)
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
            "EvidenceBucket",
            "Catalogue",
            "S3GatewayEndpoint",
            "KmsInterfaceEndpoint",
            "BackupPlan",
        }
        - set(resources)
        or cost.get("schema_version") != AWS_COST_SCHEMA
        or cost.get("region") != manifest.get("recommended_region")
        or source_use.get("schema_version") != AWS_SOURCE_USE_SCHEMA
        or manifest.get("components")
        != {
            "cloudformation_template_digest": template_digest,
            "database_roles_digest": roles_digest,
            "cost_estimate_digest": cost_digest,
            "source_use_manifest_digest": source_use_digest,
        }
    ):
        raise ArchiveFailure(ArchiveCode.CONFLICT)
    rates = cost.get("rates")
    if (
        type(rates) is not list
        or not rates
        or any(type(item) is not dict for item in rates)
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    calculated = round(sum(float(item["subtotal"]) for item in rates), 3)
    if calculated != cost.get("monthly_estimate"):
        raise ArchiveFailure(ArchiveCode.CONFLICT)
    for key in (
        "monthly_estimate",
        "monthly_budget_recommendation",
        "one_off_rehearsal_estimate",
    ):
        if type(cost.get(key)) not in {int, float} or cost[key] < 0:
            raise ArchiveFailure(ArchiveCode.INVALID)
    return AlphaAwsPackageReport(
        AWS_PACKAGE_SCHEMA,
        content_digest(ALPHA_DEPLOYMENT_MANIFEST_SCHEMA, canonical_bytes(manifest)),
        template_digest,
        roles_digest,
        cost_digest,
        source_use_digest,
        float(cost["monthly_estimate"]),
        float(cost["monthly_budget_recommendation"]),
        float(cost["one_off_rehearsal_estimate"]),
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
