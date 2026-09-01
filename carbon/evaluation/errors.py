"""Stable, non-echoing failures for the B-04 reference/truth boundary."""

from __future__ import annotations

import re
from enum import Enum
from types import MappingProxyType

_PATH_SEGMENT = re.compile(r"(?:[a-z][a-z0-9_]*|[0-9]{1,5})\Z", re.ASCII)

# Error paths are disclosure surfaces.  Only schema-owned field names and
# bounded tuple indexes survive normalization; caller values are never echoed.
_TRUSTED_PATH_SEGMENTS = frozenset(
    [
        "admission_authority_ref",
        "admission_decision_ref",
        "admission_grant_ref",
        "admission_issuance_record_ref",
        "answer_key_authority_target",
        "applicability_assessment",
        "applicability_evidence_refs",
        "applicability_policy_ref",
        "artifact_binding",
        "artifact_content_digest",
        "artifact_descriptor_ref",
        "artifact_id",
        "artifact_origin",
        "artifact_ref",
        "artifact_schema_ref",
        "artifact_version",
        "attempt_binding",
        "authority_function",
        "authoritative_case_ref",
        "canonical_bytes",
        "canonicalization_profile",
        "capability_ref",
        "case_ref",
        "challenge_key",
        "claim_scope_ref",
        "combination_environment_ref",
        "combination_implementation_ref",
        "combination_method_ref",
        "comparison_id",
        "comparison_method_ref",
        "comparison_policy_ref",
        "comparison_refs",
        "comparison_version",
        "component_bindings",
        "component_entry_refs",
        "component_kinds",
        "composition_id",
        "composition_kind",
        "composition_refs",
        "composition_version",
        "conditioning_assessment",
        "conditioning_policy_ref",
        "configuration_ref",
        "consumed_grant_receipt_ref",
        "content_digest",
        "correlation_policy_ref",
        "coverage_ref",
        "decision_id",
        "decision_profile_ref",
        "decision_version",
        "dependency_constraints_ref",
        "dependency_disclosures",
        "dependence_policy_ref",
        "diagnostics_ref",
        "disclosure_policy_ref",
        "entry_id",
        "entry_ref",
        "entry_refs",
        "entry_version",
        "environment_constraints_ref",
        "environment_ref",
        "evidence_campaign_ref",
        "evidence_population_refs",
        "evidence_refs",
        "evidence_role_binding",
        "execution_target",
        "expected_representation_ref",
        "fallback_policy_ref",
        "fixture_asset_id",
        "fixture_asset_version",
        "fixture_provenance_ref",
        "generated_or_copied_code_refs",
        "grant_binding",
        "grant_id",
        "grant_ref",
        "grant_version",
        "hardware_ref",
        "history_binding_ref",
        "hybrid_role_ref",
        "idempotency_ref",
        "identity_id",
        "identity_kind",
        "identity_version",
        "implementation_constraints_ref",
        "implementation_ref",
        "issuance_id",
        "issuance_record_ref",
        "issuance_token",
        "issuance_version",
        "issuer_ref",
        "known_limitations",
        "limitations",
        "live_eligible",
        "manifest_id",
        "manifest_version",
        "member_entry_refs",
        "method_constraints_ref",
        "method_ref",
        "object_kind",
        "outcome",
        "payload_bytes",
        "physical_system_ref",
        "policy_id",
        "policy_ref",
        "policy_version",
        "precision_ref",
        "precomputed_source_manifest_ref",
        "primary_entry_refs",
        "primary_execution_target",
        "primary_run_ref",
        "proposal_population_ref",
        "provenance_binding",
        "provenance_policy_ref",
        "provenance_refs",
        "qualification_binding",
        "qualification_evidence_ref",
        "qualification_policy_ref",
        "reason",
        "record",
        "record_type",
        "ref",
        "ref_type",
        "registered_witness_targets",
        "relation",
        "representation_ref",
        "request_binding",
        "request_id",
        "request_ref",
        "request_version",
        "requested_resource_policy_ref",
        "resolution_id",
        "resolution_ref",
        "resolution_version",
        "resolver_ref",
        "resource_authorization_ref",
        "resource_policy_ref",
        "resource_receipt_ref",
        "revocation_binding",
        "rights_profile_ref",
        "role",
        "run_id",
        "run_ref",
        "run_version",
        "sampling_plan_ref",
        "schema_version",
        "scientific_qualification_eligible",
        "scope_binding",
        "source_class",
        "source_corpus_digest",
        "source_ref",
        "status",
        "supersedes",
        "support_boundary_ref",
        "target_population_ref",
        "truth_asset_id",
        "truth_asset_version",
        "truth_target_ref",
        "uncertainty_binding",
        "uncertainty_policy_ref",
        "uncertainty_treatment_ref",
        "units_ref",
        "use_restrictions",
        "value",
        "witness_entry_refs",
        "witness_run_ref",
        "witness_target",
        "witness_targets",
    ]
)


def _trusted_path(value: object) -> str:
    if type(value) is not str:
        raise TypeError("reference error path must be a string")
    if value == "":
        return ""
    if len(value) > 256 or not value.startswith("/") or value.endswith("/"):
        return ""
    trusted: list[str] = []
    for segment in value[1:].split("/"):
        if _PATH_SEGMENT.fullmatch(segment) is None:
            break
        if segment.isdecimal() or segment in _TRUSTED_PATH_SEGMENTS:
            trusted.append(segment)
        else:
            break
    return f"/{'/'.join(trusted)}" if trusted else ""


class ReferenceInputCode(str, Enum):
    """Closed rejection codes for hostile B-04 inputs and identity graphs."""

    WRONG_TYPE = "WRONG_TYPE"
    INVALID_VALUE = "INVALID_VALUE"
    INVALID_CANONICAL_BYTES = "INVALID_CANONICAL_BYTES"
    TRAILING_BYTES = "TRAILING_BYTES"
    REF_DIGEST_MISMATCH = "REF_DIGEST_MISMATCH"
    CROSS_CHALLENGE = "CROSS_CHALLENGE"
    STALE_BINDING = "STALE_BINDING"
    INCOMPLETE_BINDING = "INCOMPLETE_BINDING"
    DUPLICATE_IDENTITY = "DUPLICATE_IDENTITY"
    ROLE_MISMATCH = "ROLE_MISMATCH"
    OUTCOME_REASON_MISMATCH = "OUTCOME_REASON_MISMATCH"
    AUTHORITY_INTERFACE_INVALID = "AUTHORITY_INTERFACE_INVALID"


class ReferenceServiceCode(str, Enum):
    """Sanitized failures of trusted B-04 capabilities."""

    RESOLVER_UNAVAILABLE = "RESOLVER_UNAVAILABLE"
    RUNNER_UNAVAILABLE = "RUNNER_UNAVAILABLE"
    ADMISSION_ISSUER_UNAVAILABLE = "ADMISSION_ISSUER_UNAVAILABLE"
    ADMISSION_AUTHORITY_UNAVAILABLE = "ADMISSION_AUTHORITY_UNAVAILABLE"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class ReferenceDisclosureCode(str, Enum):
    """Closed public-projection rejection codes."""

    DISCLOSURE_POLICY_REQUIRED = "DISCLOSURE_POLICY_REQUIRED"
    PROJECTION_NOT_PERMITTED = "PROJECTION_NOT_PERMITTED"
    SOURCE_RECORD_REQUIRED = "SOURCE_RECORD_REQUIRED"


def _closed_code_member(value: object, enum_type: type[Enum]) -> Enum | None:
    """Normalize only a registered member or its exact built-in string value."""

    if type(value) is enum_type:
        return next((member for member in enum_type if value is member), None)
    if type(value) is not str:
        return None
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        return None


INPUT_REJECTION_MESSAGES = MappingProxyType(
    {
        ReferenceInputCode.WRONG_TYPE: "input has the wrong exact type",
        ReferenceInputCode.INVALID_VALUE: "input value is outside the closed contract",
        ReferenceInputCode.INVALID_CANONICAL_BYTES: "canonical bytes are invalid",
        ReferenceInputCode.TRAILING_BYTES: "canonical bytes contain trailing data",
        ReferenceInputCode.REF_DIGEST_MISMATCH: "object and ref digest do not match",
        ReferenceInputCode.CROSS_CHALLENGE: "bound values do not share one Challenge",
        ReferenceInputCode.STALE_BINDING: "a bound object and identity do not match",
        ReferenceInputCode.INCOMPLETE_BINDING: "a required exact binding is incomplete",
        ReferenceInputCode.DUPLICATE_IDENTITY: "a closed inventory contains a duplicate",
        ReferenceInputCode.ROLE_MISMATCH: "evidence and authority roles are incompatible",
        ReferenceInputCode.OUTCOME_REASON_MISMATCH: (
            "outcome and reason are incompatible under the closed matrix"
        ),
        ReferenceInputCode.AUTHORITY_INTERFACE_INVALID: (
            "required nominal authority interface is unavailable"
        ),
    }
)

SERVICE_FAILURE_MESSAGES = MappingProxyType(
    {
        ReferenceServiceCode.RESOLVER_UNAVAILABLE: (
            "the configured reference resolver is unavailable"
        ),
        ReferenceServiceCode.RUNNER_UNAVAILABLE: (
            "the configured reference runner is unavailable"
        ),
        ReferenceServiceCode.ADMISSION_ISSUER_UNAVAILABLE: (
            "the configured admission grant issuer is unavailable"
        ),
        ReferenceServiceCode.ADMISSION_AUTHORITY_UNAVAILABLE: (
            "the configured admission authority is unavailable"
        ),
        ReferenceServiceCode.INTERNAL_FAILURE: (
            "the protected reference operation could not be completed"
        ),
    }
)

DISCLOSURE_FAILURE_MESSAGES = MappingProxyType(
    {
        ReferenceDisclosureCode.DISCLOSURE_POLICY_REQUIRED: (
            "a positive disclosure-policy binding is required"
        ),
        ReferenceDisclosureCode.PROJECTION_NOT_PERMITTED: (
            "the source record is not publicly projectable"
        ),
        ReferenceDisclosureCode.SOURCE_RECORD_REQUIRED: (
            "an exact protected source record is required"
        ),
    }
)


class ReferenceTruthError(Exception):
    """Base class for fixed B-04 failures without protected caller data."""

    def __init__(self, code: str, message: str, *, path: str = "") -> None:
        if type(code) is not str or not code:
            raise TypeError("reference error code must be a nonempty string")
        if type(message) is not str or not message:
            raise TypeError("reference error message must be a nonempty string")
        self.code = code
        self.path = _trusted_path(path)
        self.__cause__ = None
        self.__suppress_context__ = True
        super().__init__(message)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, path={self.path!r})"

    @property
    def __context__(self) -> None:
        """Never retain a lower-layer exception as a disclosure side channel."""

        return None

    @__context__.setter
    def __context__(self, value: object) -> None:
        del value

    def __reduce__(self):
        raise TypeError("protected reference errors cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected reference errors cannot be pickled")


class ReferenceValidationError(ReferenceTruthError, ValueError):
    """A malformed or cross-bound B-04 input was rejected."""

    def __init__(self, code: ReferenceInputCode | str, *, path: str = "") -> None:
        normalized = _closed_code_member(code, ReferenceInputCode)
        if normalized is None:
            raise TypeError("code must be one exact ReferenceInputCode")
        super().__init__(
            normalized.value,
            INPUT_REJECTION_MESSAGES[normalized],
            path=path,
        )


class ReferenceCanonicalEncodingError(ReferenceValidationError):
    def __init__(self, *, path: str = "") -> None:
        super().__init__(ReferenceInputCode.INVALID_VALUE, path=path)


class ReferenceCanonicalDecodingError(ReferenceValidationError):
    def __init__(self, *, trailing: bool = False, path: str = "") -> None:
        if type(trailing) is not bool:
            raise TypeError("trailing must be an exact bool")
        super().__init__(
            (
                ReferenceInputCode.TRAILING_BYTES
                if trailing
                else ReferenceInputCode.INVALID_CANONICAL_BYTES
            ),
            path=path,
        )


class ReferenceMismatchError(ReferenceValidationError):
    def __init__(self, *, path: str = "") -> None:
        super().__init__(ReferenceInputCode.REF_DIGEST_MISMATCH, path=path)


class ReferenceServiceError(ReferenceTruthError, RuntimeError):
    def __init__(self, code: ReferenceServiceCode | str, *, path: str = "") -> None:
        normalized = _closed_code_member(code, ReferenceServiceCode)
        if normalized is None:
            raise TypeError("code must be one exact ReferenceServiceCode")
        super().__init__(
            normalized.value,
            SERVICE_FAILURE_MESSAGES[normalized],
            path=path,
        )


class ReferenceDisclosureError(ReferenceTruthError, ValueError):
    def __init__(self, code: ReferenceDisclosureCode | str, *, path: str = "") -> None:
        normalized = _closed_code_member(code, ReferenceDisclosureCode)
        if normalized is None:
            raise TypeError("code must be one exact ReferenceDisclosureCode")
        super().__init__(
            normalized.value,
            DISCLOSURE_FAILURE_MESSAGES[normalized],
            path=path,
        )


CanonicalEncodingError = ReferenceCanonicalEncodingError
CanonicalDecodingError = ReferenceCanonicalDecodingError


def reject(code: ReferenceInputCode, path: str = "") -> ReferenceValidationError:
    """Construct a fixed hard rejection without echoing the caller input."""

    return ReferenceValidationError(code, path=path)


__all__ = [
    "DISCLOSURE_FAILURE_MESSAGES",
    "INPUT_REJECTION_MESSAGES",
    "SERVICE_FAILURE_MESSAGES",
    "CanonicalDecodingError",
    "CanonicalEncodingError",
    "ReferenceCanonicalDecodingError",
    "ReferenceCanonicalEncodingError",
    "ReferenceDisclosureCode",
    "ReferenceDisclosureError",
    "ReferenceInputCode",
    "ReferenceMismatchError",
    "ReferenceServiceCode",
    "ReferenceServiceError",
    "ReferenceTruthError",
    "ReferenceValidationError",
    "reject",
]
