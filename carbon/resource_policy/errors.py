"""Stable, non-echoing failures for the B-02C resource-policy domain."""

from __future__ import annotations

from enum import Enum

_TRUSTED_PATH_SEGMENTS = frozenset(
    {
        "assessment_ref",
        "authority_marker",
        "authority_context",
        "build_attempt_digest",
        "build_attempt_id",
        "canonical_bytes",
        "canonicalization_profile",
        "challenge_key",
        "class_bindings",
        "complete_build_digest",
        "construction_plan_ref",
        "candidate_assembly_ref",
        "compiler_identity",
        "content_digest",
        "context_id",
        "dimension_id",
        "enforcement",
        "enforcement_mode",
        "enforcement_point",
        "expected_active_policy_ref",
        "expected_active_resource_class_ref",
        "fixture_decision_ref",
        "fixture_registration_ref",
        "internal_service_scope_ref",
        "limit_id",
        "maximum_quantity",
        "metric_id",
        "object_id",
        "object_kind",
        "object_version",
        "observation",
        "observation_role",
        "parameter_catalog_ref",
        "policy_ref",
        "provenance",
        "quantity",
        "ref",
        "ref_type",
        "replicate_attempt_digest",
        "replicate_attempt_id",
        "replicate_digest",
        "replicate_id",
        "resource_class",
        "resource_class_ref",
        "resource_impact_tags",
        "required_plan_environment_pins",
        "schema_version",
        "scope_binding",
        "source_provenance_refs",
        "static_resource_requirements",
        "type",
        "unit_ref",
    }
)


def _trusted_path(value: object) -> str:
    """Retain only closed schema paths; never retain caller-controlled text."""

    if type(value) is not str:
        raise TypeError("resource-policy error path must be a string")
    if value == "":
        return ""
    if len(value) > 256 or not value.startswith("/") or value.endswith("/"):
        return ""
    segments = value[1:].split("/")
    if not segments or any(
        segment not in _TRUSTED_PATH_SEGMENTS
        and not (segment.isascii() and segment.isdecimal() and len(segment) <= 5)
        for segment in segments
    ):
        return ""
    return value


class ResourcePolicyInputCode(str, Enum):
    """Closed hard-rejection codes fixed by the B-02C contract."""

    WRONG_TYPE = "WRONG_TYPE"
    INVALID_VALUE = "INVALID_VALUE"
    INVALID_CANONICAL_BYTES = "INVALID_CANONICAL_BYTES"
    TRAILING_BYTES = "TRAILING_BYTES"
    REF_DIGEST_MISMATCH = "REF_DIGEST_MISMATCH"
    POLICY_BUNDLE_INCOMPLETE = "POLICY_BUNDLE_INCOMPLETE"
    LIMIT_NOT_BOUND = "LIMIT_NOT_BOUND"


INPUT_REJECTION_MESSAGES = {
    ResourcePolicyInputCode.WRONG_TYPE: "input has the wrong exact type",
    ResourcePolicyInputCode.INVALID_VALUE: "input value is outside the closed contract",
    ResourcePolicyInputCode.INVALID_CANONICAL_BYTES: "canonical bytes are invalid",
    ResourcePolicyInputCode.TRAILING_BYTES: "canonical bytes contain trailing data",
    ResourcePolicyInputCode.REF_DIGEST_MISMATCH: ("object and ref digest do not match"),
    ResourcePolicyInputCode.POLICY_BUNDLE_INCOMPLETE: (
        "policy class bundle is incomplete or injected"
    ),
    ResourcePolicyInputCode.LIMIT_NOT_BOUND: "runtime limit is not bound by policy",
}


class ResourcePolicyError(Exception):
    """Base class for exact resource-policy failures."""

    def __init__(self, code: str, message: str, *, path: str = "") -> None:
        if type(code) is not str or not code:
            raise TypeError("resource-policy error code must be a nonempty string")
        if type(message) is not str or not message:
            raise TypeError("resource-policy error message must be a nonempty string")
        self.code = code
        self.path = _trusted_path(path)
        super().__init__(message)


class ResourcePolicyInputRejected(ResourcePolicyError, ValueError):
    """A hostile or malformed input was rejected before result issuance."""

    def __init__(
        self,
        code: ResourcePolicyInputCode | str,
        *,
        path: str = "",
    ) -> None:
        try:
            normalized = (
                code
                if type(code) is ResourcePolicyInputCode
                else ResourcePolicyInputCode(code)
            )
        except (TypeError, ValueError) as exc:
            raise TypeError("code must be one exact ResourcePolicyInputCode") from exc
        super().__init__(
            normalized.value,
            INPUT_REJECTION_MESSAGES[normalized],
            path=path,
        )


class ResourcePolicyCanonicalEncodingError(ResourcePolicyInputRejected):
    """A value cannot be represented by the closed resource-policy profile."""

    def __init__(self, *, path: str = "") -> None:
        super().__init__(ResourcePolicyInputCode.INVALID_VALUE, path=path)


class ResourcePolicyCanonicalDecodingError(ResourcePolicyInputRejected):
    """Canonical bytes are malformed, noncanonical, unknown, or trailing."""

    def __init__(self, *, trailing: bool = False, path: str = "") -> None:
        super().__init__(
            (
                ResourcePolicyInputCode.TRAILING_BYTES
                if trailing
                else ResourcePolicyInputCode.INVALID_CANONICAL_BYTES
            ),
            path=path,
        )


class ResourcePolicyReferenceMismatchError(ResourcePolicyInputRejected):
    """Canonical bytes or identity metadata differ from an exact nominal ref."""

    def __init__(self, *, path: str = "") -> None:
        super().__init__(ResourcePolicyInputCode.REF_DIGEST_MISMATCH, path=path)


CanonicalEncodingError = ResourcePolicyCanonicalEncodingError
CanonicalDecodingError = ResourcePolicyCanonicalDecodingError
ReferenceMismatchError = ResourcePolicyReferenceMismatchError


def reject(code: ResourcePolicyInputCode, path: str) -> ResourcePolicyInputRejected:
    """Construct one fixed hard-rejection failure without echoing input."""

    return ResourcePolicyInputRejected(code, path=path)


__all__ = [
    "INPUT_REJECTION_MESSAGES",
    "CanonicalDecodingError",
    "CanonicalEncodingError",
    "ReferenceMismatchError",
    "ResourcePolicyCanonicalDecodingError",
    "ResourcePolicyCanonicalEncodingError",
    "ResourcePolicyError",
    "ResourcePolicyInputCode",
    "ResourcePolicyInputRejected",
    "ResourcePolicyReferenceMismatchError",
]
