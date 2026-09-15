"""Fail-closed recovery-watermark verification for the C-EA1 AWS package.

The types bind a test-owned provider rehearsal to the complete acknowledged
dependency set.  They do not restore AWS resources, issue an acknowledgement,
or qualify the selected recovery target.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .alpha_profile import AlphaArchiveProfile
from .aws_provider import AWS_PROVIDER_PROFILE_ID
from .model import (
    ArchiveCode,
    ArchiveFailure,
    canonical_bytes,
    content_digest,
    validate_artifact_name,
    validate_digest,
    validate_token,
)

ALPHA_RECOVERY_WATERMARK_SCHEMA = "carbon.evidence-archive.recovery-watermark.v1"
ALPHA_RECOVERY_OBSERVATION_SCHEMA = "carbon.evidence-archive.recovery-observation.v1"
ALPHA_RECOVERY_ASSESSMENT_SCHEMA = "carbon.evidence-archive.recovery-assessment.v1"
ALPHA_MAX_RECOVERY_OBJECTS = 8192
ALPHA_MAX_RECOVERY_REFS = 8192
ALPHA_MAX_RECOVERY_DOCUMENT_BYTES = 8 * 1024 * 1024


def _provider_id(value: object, *, maximum_bytes: int = 1024) -> str:
    if (
        type(value) is not str
        or not value
        or any(
            character.isspace() or not character.isprintable() for character in value
        )
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise ArchiveFailure(ArchiveCode.INVALID) from None
    if len(encoded) > maximum_bytes:
        raise ArchiveFailure(ArchiveCode.INVALID)
    return value


class AlphaRecoveryIssue(StrEnum):
    WATERMARK_MISMATCH = "WATERMARK_MISMATCH"
    CATALOGUE_RECOVERY_POINT_MISMATCH = "CATALOGUE_RECOVERY_POINT_MISMATCH"
    CATALOGUE_COMMIT_BEHIND = "CATALOGUE_COMMIT_BEHIND"
    JOURNAL_BEHIND = "JOURNAL_BEHIND"
    OUTBOX_INCOMPLETE = "OUTBOX_INCOMPLETE"
    CAPACITY_LEDGER_BEHIND = "CAPACITY_LEDGER_BEHIND"
    ACKNOWLEDGEMENTS_INCOMPLETE = "ACKNOWLEDGEMENTS_INCOMPLETE"
    MANIFESTS_INCOMPLETE = "MANIFESTS_INCOMPLETE"
    SIGNATURES_INCOMPLETE = "SIGNATURES_INCOMPLETE"
    OBJECT_VERSION_SET_MISMATCH = "OBJECT_VERSION_SET_MISMATCH"
    ENVELOPE_KEYS_INCOMPLETE = "ENVELOPE_KEYS_INCOMPLETE"


@dataclass(frozen=True, slots=True)
class AlphaRecoveryObject:
    archive_entry_id: str
    artifact_name: str
    object_key: str
    version_id: str
    ciphertext_digest: str
    plaintext_digest: str
    wrapped_key_digest: str
    envelope_key_arn: str
    encryption_context_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "archive_entry_id", validate_digest(self.archive_entry_id)
        )
        object.__setattr__(
            self, "artifact_name", validate_artifact_name(self.artifact_name)
        )
        if (
            type(self.object_key) is not str
            or not 1 <= len(self.object_key) <= 512
            or not self.object_key.isascii()
            or any(
                character.isspace() or ord(character) < 33
                for character in self.object_key
            )
            or self.object_key.startswith("/")
            or ".." in self.object_key.split("/")
            or any(not part for part in self.object_key.split("/"))
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)
        object.__setattr__(self, "version_id", _provider_id(self.version_id))
        for name in (
            "ciphertext_digest",
            "plaintext_digest",
            "wrapped_key_digest",
            "encryption_context_digest",
        ):
            object.__setattr__(self, name, validate_digest(getattr(self, name)))
        if (
            type(self.envelope_key_arn) is not str
            or not 1 <= len(self.envelope_key_arn) <= 256
            or not self.envelope_key_arn.isascii()
            or any(
                character.isspace() or ord(character) < 33
                for character in self.envelope_key_arn
            )
            or not self.envelope_key_arn.startswith("arn:aws:kms:")
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.archive_entry_id, self.artifact_name, self.version_id)

    def document(self) -> dict[str, object]:
        return {
            "archive_entry_id": self.archive_entry_id,
            "artifact_name": self.artifact_name,
            "object_key": self.object_key,
            "version_id": self.version_id,
            "ciphertext_digest": self.ciphertext_digest,
            "plaintext_digest": self.plaintext_digest,
            "wrapped_key_digest": self.wrapped_key_digest,
            "envelope_key_arn": self.envelope_key_arn,
            "encryption_context_digest": self.encryption_context_digest,
        }


def _refs(
    values: tuple[str, ...], *, maximum: int = ALPHA_MAX_RECOVERY_REFS
) -> tuple[str, ...]:
    if type(values) is not tuple or len(values) > maximum:
        raise ArchiveFailure(ArchiveCode.INVALID)
    validated = tuple(validate_digest(value) for value in values)
    if tuple(sorted(set(validated))) != validated:
        raise ArchiveFailure(ArchiveCode.INVALID)
    return validated


@dataclass(frozen=True, slots=True)
class AlphaRecoveryWatermark:
    profile_digest: str
    deployment_manifest_digest: str
    catalogue_recovery_point_ref: str
    catalogue_commit_sequence: int
    journal_event_sequence: int
    capacity_event_sequence: int
    outbox_event_refs: tuple[str, ...]
    acknowledgement_refs: tuple[str, ...]
    manifest_refs: tuple[str, ...]
    signature_refs: tuple[str, ...]
    objects: tuple[AlphaRecoveryObject, ...]
    schema_version: str = ALPHA_RECOVERY_WATERMARK_SCHEMA
    provider_profile_id: str = AWS_PROVIDER_PROFILE_ID

    def __post_init__(self) -> None:
        if (
            self.schema_version != ALPHA_RECOVERY_WATERMARK_SCHEMA
            or self.provider_profile_id != AWS_PROVIDER_PROFILE_ID
            or self.profile_digest != AlphaArchiveProfile().digest
        ):
            raise ArchiveFailure(ArchiveCode.DENIED)
        object.__setattr__(
            self,
            "deployment_manifest_digest",
            validate_digest(self.deployment_manifest_digest),
        )
        object.__setattr__(
            self,
            "catalogue_recovery_point_ref",
            validate_token(self.catalogue_recovery_point_ref, maximum=512),
        )
        for name in (
            "catalogue_commit_sequence",
            "journal_event_sequence",
            "capacity_event_sequence",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ArchiveFailure(ArchiveCode.INVALID)
        for name in (
            "outbox_event_refs",
            "acknowledgement_refs",
            "manifest_refs",
            "signature_refs",
        ):
            object.__setattr__(self, name, _refs(getattr(self, name)))
        if (
            type(self.objects) is not tuple
            or not 1 <= len(self.objects) <= ALPHA_MAX_RECOVERY_OBJECTS
            or any(type(value) is not AlphaRecoveryObject for value in self.objects)
            or tuple(sorted(value.identity for value in self.objects))
            != tuple(value.identity for value in self.objects)
            or len({value.identity for value in self.objects}) != len(self.objects)
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)

    def document(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "provider_profile_id": self.provider_profile_id,
            "profile_digest": self.profile_digest,
            "deployment_manifest_digest": self.deployment_manifest_digest,
            "catalogue_recovery_point_ref": self.catalogue_recovery_point_ref,
            "catalogue_commit_sequence": self.catalogue_commit_sequence,
            "journal_event_sequence": self.journal_event_sequence,
            "capacity_event_sequence": self.capacity_event_sequence,
            "outbox_event_refs": list(self.outbox_event_refs),
            "acknowledgement_refs": list(self.acknowledgement_refs),
            "manifest_refs": list(self.manifest_refs),
            "signature_refs": list(self.signature_refs),
            "objects": [value.document() for value in self.objects],
        }

    @property
    def digest(self) -> str:
        return content_digest(
            ALPHA_RECOVERY_WATERMARK_SCHEMA, canonical_bytes(self.document())
        )


@dataclass(frozen=True, slots=True)
class AlphaRecoveryObservation:
    watermark_digest: str
    catalogue_recovery_point_ref: str
    catalogue_commit_sequence: int
    journal_event_sequence: int
    capacity_event_sequence: int
    outbox_event_refs: tuple[str, ...]
    acknowledgement_refs: tuple[str, ...]
    manifest_refs: tuple[str, ...]
    signature_refs: tuple[str, ...]
    objects: tuple[AlphaRecoveryObject, ...]
    recovered_envelope_key_refs: tuple[str, ...]
    elapsed_seconds: int
    schema_version: str = ALPHA_RECOVERY_OBSERVATION_SCHEMA
    test_owned_resources_only: bool = True

    def __post_init__(self) -> None:
        if (
            self.schema_version != ALPHA_RECOVERY_OBSERVATION_SCHEMA
            or self.test_owned_resources_only is not True
        ):
            raise ArchiveFailure(ArchiveCode.DENIED)
        object.__setattr__(
            self, "watermark_digest", validate_digest(self.watermark_digest)
        )
        object.__setattr__(
            self,
            "catalogue_recovery_point_ref",
            validate_token(self.catalogue_recovery_point_ref, maximum=512),
        )
        for name in (
            "catalogue_commit_sequence",
            "journal_event_sequence",
            "capacity_event_sequence",
            "elapsed_seconds",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ArchiveFailure(ArchiveCode.INVALID)
        for name in (
            "outbox_event_refs",
            "acknowledgement_refs",
            "manifest_refs",
            "signature_refs",
            "recovered_envelope_key_refs",
        ):
            object.__setattr__(self, name, _refs(getattr(self, name)))
        if (
            type(self.objects) is not tuple
            or len(self.objects) > ALPHA_MAX_RECOVERY_OBJECTS
            or any(type(value) is not AlphaRecoveryObject for value in self.objects)
            or tuple(sorted(value.identity for value in self.objects))
            != tuple(value.identity for value in self.objects)
            or len({value.identity for value in self.objects}) != len(self.objects)
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)

    def document(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "watermark_digest": self.watermark_digest,
            "catalogue_recovery_point_ref": self.catalogue_recovery_point_ref,
            "catalogue_commit_sequence": self.catalogue_commit_sequence,
            "journal_event_sequence": self.journal_event_sequence,
            "capacity_event_sequence": self.capacity_event_sequence,
            "outbox_event_refs": list(self.outbox_event_refs),
            "acknowledgement_refs": list(self.acknowledgement_refs),
            "manifest_refs": list(self.manifest_refs),
            "signature_refs": list(self.signature_refs),
            "objects": [value.document() for value in self.objects],
            "recovered_envelope_key_refs": list(self.recovered_envelope_key_refs),
            "elapsed_seconds": self.elapsed_seconds,
            "test_owned_resources_only": self.test_owned_resources_only,
        }


@dataclass(frozen=True, slots=True)
class AlphaRecoveryAssessment:
    watermark_digest: str
    issues: tuple[AlphaRecoveryIssue, ...]
    elapsed_seconds: int
    schema_version: str = ALPHA_RECOVERY_ASSESSMENT_SCHEMA
    provisional_rehearsal_passed: bool = False
    eligible_for_real_acknowledgement: bool = False
    eligible_for_c_ea2: bool = False

    def __post_init__(self) -> None:
        if (
            self.schema_version != ALPHA_RECOVERY_ASSESSMENT_SCHEMA
            or self.provisional_rehearsal_passed is not (not self.issues)
            or self.eligible_for_real_acknowledgement is not False
            or self.eligible_for_c_ea2 is not False
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)

    def public_document(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "watermark_digest": self.watermark_digest,
            "issues": [value.value for value in self.issues],
            "elapsed_seconds": self.elapsed_seconds,
            "provisional_rehearsal_passed": self.provisional_rehearsal_passed,
            "eligible_for_real_acknowledgement": False,
            "eligible_for_c_ea2": False,
        }


def assess_recovery_watermark(
    watermark: AlphaRecoveryWatermark,
    observation: AlphaRecoveryObservation,
) -> AlphaRecoveryAssessment:
    if (
        type(watermark) is not AlphaRecoveryWatermark
        or type(observation) is not AlphaRecoveryObservation
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    issues: list[AlphaRecoveryIssue] = []
    if observation.watermark_digest != watermark.digest:
        issues.append(AlphaRecoveryIssue.WATERMARK_MISMATCH)
    if (
        observation.catalogue_recovery_point_ref
        != watermark.catalogue_recovery_point_ref
    ):
        issues.append(AlphaRecoveryIssue.CATALOGUE_RECOVERY_POINT_MISMATCH)
    comparisons = (
        (
            observation.catalogue_commit_sequence,
            watermark.catalogue_commit_sequence,
            AlphaRecoveryIssue.CATALOGUE_COMMIT_BEHIND,
        ),
        (
            observation.journal_event_sequence,
            watermark.journal_event_sequence,
            AlphaRecoveryIssue.JOURNAL_BEHIND,
        ),
        (
            observation.capacity_event_sequence,
            watermark.capacity_event_sequence,
            AlphaRecoveryIssue.CAPACITY_LEDGER_BEHIND,
        ),
    )
    issues.extend(
        issue for observed, required, issue in comparisons if observed < required
    )
    sets = (
        (
            observation.outbox_event_refs,
            watermark.outbox_event_refs,
            AlphaRecoveryIssue.OUTBOX_INCOMPLETE,
        ),
        (
            observation.acknowledgement_refs,
            watermark.acknowledgement_refs,
            AlphaRecoveryIssue.ACKNOWLEDGEMENTS_INCOMPLETE,
        ),
        (
            observation.manifest_refs,
            watermark.manifest_refs,
            AlphaRecoveryIssue.MANIFESTS_INCOMPLETE,
        ),
        (
            observation.signature_refs,
            watermark.signature_refs,
            AlphaRecoveryIssue.SIGNATURES_INCOMPLETE,
        ),
    )
    issues.extend(
        issue
        for observed, required, issue in sets
        if not set(required).issubset(observed)
    )
    if (
        tuple(sorted(observation.objects, key=lambda value: value.identity))
        != watermark.objects
    ):
        issues.append(AlphaRecoveryIssue.OBJECT_VERSION_SET_MISMATCH)
    required_keys = {value.wrapped_key_digest for value in watermark.objects}
    if not required_keys.issubset(observation.recovered_envelope_key_refs):
        issues.append(AlphaRecoveryIssue.ENVELOPE_KEYS_INCOMPLETE)
    unique = tuple(dict.fromkeys(issues))
    return AlphaRecoveryAssessment(
        watermark.digest,
        unique,
        observation.elapsed_seconds,
        provisional_rehearsal_passed=not unique,
    )


def _closed_json(payload: bytes) -> dict[str, Any]:
    if (
        type(payload) is not bytes
        or not 1 <= len(payload) <= ALPHA_MAX_RECOVERY_DOCUMENT_BYTES
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)

    def closed(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        document: dict[str, Any] = {}
        for key, value in pairs:
            if key in document:
                raise ArchiveFailure(ArchiveCode.INVALID)
            document[key] = value
        return document

    try:
        document = json.loads(payload, object_pairs_hook=closed)
    except (UnicodeDecodeError, json.JSONDecodeError, ArchiveFailure):
        raise ArchiveFailure(ArchiveCode.INVALID) from None
    if type(document) is not dict:
        raise ArchiveFailure(ArchiveCode.INVALID)
    return document


def _object(document: object) -> AlphaRecoveryObject:
    expected = {
        "archive_entry_id",
        "artifact_name",
        "object_key",
        "version_id",
        "ciphertext_digest",
        "plaintext_digest",
        "wrapped_key_digest",
        "envelope_key_arn",
        "encryption_context_digest",
    }
    if type(document) is not dict or set(document) != expected:
        raise ArchiveFailure(ArchiveCode.INVALID)
    return AlphaRecoveryObject(**document)


def _tuple(document: dict[str, Any], name: str) -> tuple[str, ...]:
    value = document[name]
    if type(value) is not list:
        raise ArchiveFailure(ArchiveCode.INVALID)
    return tuple(value)


def parse_recovery_watermark(payload: bytes) -> AlphaRecoveryWatermark:
    document = _closed_json(payload)
    expected = {
        "schema_version",
        "provider_profile_id",
        "profile_digest",
        "deployment_manifest_digest",
        "catalogue_recovery_point_ref",
        "catalogue_commit_sequence",
        "journal_event_sequence",
        "capacity_event_sequence",
        "outbox_event_refs",
        "acknowledgement_refs",
        "manifest_refs",
        "signature_refs",
        "objects",
    }
    if (
        set(document) != expected
        or type(document["objects"]) is not list
        or not 1 <= len(document["objects"]) <= ALPHA_MAX_RECOVERY_OBJECTS
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    return AlphaRecoveryWatermark(
        profile_digest=document["profile_digest"],
        deployment_manifest_digest=document["deployment_manifest_digest"],
        catalogue_recovery_point_ref=document["catalogue_recovery_point_ref"],
        catalogue_commit_sequence=document["catalogue_commit_sequence"],
        journal_event_sequence=document["journal_event_sequence"],
        capacity_event_sequence=document["capacity_event_sequence"],
        outbox_event_refs=_tuple(document, "outbox_event_refs"),
        acknowledgement_refs=_tuple(document, "acknowledgement_refs"),
        manifest_refs=_tuple(document, "manifest_refs"),
        signature_refs=_tuple(document, "signature_refs"),
        objects=tuple(_object(value) for value in document["objects"]),
        schema_version=document["schema_version"],
        provider_profile_id=document["provider_profile_id"],
    )


def parse_recovery_observation(payload: bytes) -> AlphaRecoveryObservation:
    document = _closed_json(payload)
    expected = {
        "schema_version",
        "watermark_digest",
        "catalogue_recovery_point_ref",
        "catalogue_commit_sequence",
        "journal_event_sequence",
        "capacity_event_sequence",
        "outbox_event_refs",
        "acknowledgement_refs",
        "manifest_refs",
        "signature_refs",
        "objects",
        "recovered_envelope_key_refs",
        "elapsed_seconds",
        "test_owned_resources_only",
    }
    if (
        set(document) != expected
        or type(document["objects"]) is not list
        or len(document["objects"]) > ALPHA_MAX_RECOVERY_OBJECTS
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    return AlphaRecoveryObservation(
        watermark_digest=document["watermark_digest"],
        catalogue_recovery_point_ref=document["catalogue_recovery_point_ref"],
        catalogue_commit_sequence=document["catalogue_commit_sequence"],
        journal_event_sequence=document["journal_event_sequence"],
        capacity_event_sequence=document["capacity_event_sequence"],
        outbox_event_refs=_tuple(document, "outbox_event_refs"),
        acknowledgement_refs=_tuple(document, "acknowledgement_refs"),
        manifest_refs=_tuple(document, "manifest_refs"),
        signature_refs=_tuple(document, "signature_refs"),
        objects=tuple(_object(value) for value in document["objects"]),
        recovered_envelope_key_refs=_tuple(document, "recovered_envelope_key_refs"),
        elapsed_seconds=document["elapsed_seconds"],
        schema_version=document["schema_version"],
        test_owned_resources_only=document["test_owned_resources_only"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare a test-owned AWS recovery observation with its frozen C-EA1 watermark."
    )
    parser.add_argument("watermark", type=Path)
    parser.add_argument("observation", type=Path)
    arguments = parser.parse_args()
    assessment = assess_recovery_watermark(
        parse_recovery_watermark(arguments.watermark.read_bytes()),
        parse_recovery_observation(arguments.observation.read_bytes()),
    )
    print(
        json.dumps(assessment.public_document(), sort_keys=True, separators=(",", ":"))
    )
    return 0 if assessment.provisional_rehearsal_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
