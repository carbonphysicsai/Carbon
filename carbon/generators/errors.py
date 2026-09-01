"""Stable, non-echoing failures for the B-03 generator-runtime domain."""

# ruff: noqa: SIM905

from __future__ import annotations

import re
from enum import Enum

_PATH_SEGMENT = re.compile(r"(?:[a-z][a-z0-9_]*|[0-9]{1,5})\Z", re.ASCII)

# Error paths are themselves a disclosure surface.  Shape validation alone is
# insufficient because a protected caller value may also happen to look like a
# canonical identifier.  Keep a closed vocabulary of schema-owned segments and
# preserve decimal tuple indexes; an unknown suffix is reduced to the longest
# useful trusted prefix rather than echoed.
_TRUSTED_PATH_SEGMENTS = frozenset("""
    accounting_authority accounting_authority_failure_ref accounting_binding
    accounting_decision accounting_decision_pair accounting_decision_pairs
    accounting_directive accounting_directive_pair accounting_directive_pairs
    accounting_summary accounting_summary_ref actor_authority_ref
    all_initial_values_identical all_initial_values_zero applicability_bindings
    applicability_evidence_binding applicability_reason applicability_reasons
    applicability_stage artifact assessment_role assessments
    attempt_accounting_applicability_reasons attempt_accounting_fallback
    attempt_count attempt_ordinal attempt_outcome_counts attempt_record_pairs
    attempt_ref audit_evidence_ref audit_evidence_refs authoring_bundle
    authoring_capability authority_failure_ref authorization availability
    baseline_case_ref baseline_physical_payload_fingerprint_ref baseline_request
    baseline_request_identity baseline_request_ref baseline_result
    baseline_result_ref baseline_source_event_ref basis binding bindings
    candidate_output_ref canonical_bytes canonical_case_duplicate_binding canonical_profile case
    case_binding case_construction case_provenance_refs case_ref case_ref_binding
    case_representation_ref censoring_authority censoring_decision
    censoring_decision_binding censoring_reason censoring_record
    censoring_verdict censoring_verdict_binding challenge_key commitment_digest
    composition_audit_ref conformance_facts conformance_facts_pair
    conformance_facts_ref conformance_fallback conformance_fallbacks
    constructed_case_binding constructed_case_facts_binding content_digest
    context corpus_case_refs corpus_decision corpus_decision_ref
    corpus_issuance_ref corpus_owner_unavailable_reason_ref
    corpus_physical_payload_fingerprint_refs corpus_physical_payload_fingerprints
    corpus_results count current_attempt_lineage_ref
    current_attempt_predecessor_binding current_attempt_predecessor_ref
    current_lineage_binding current_predecessor_binding decision_kind decisions
    degeneracy_facts denominator_effect_binding denominator_effect_bindings
    denominator_unavailable_reason_ref dependency_lock_digest dependency_refs
    derived_seed deterministic_replay_comparison directive directive_kind
    disclosure_class disclosure_contract disposition disposition_construction
    distinct_initial_value_count downstream_use_restrictions draw_index
    duplicate_comparison_request_binding duplicate_rule_ref
    effective_assessment_role environment environment_class environment_id
    environment_ref environment_version evidence_campaign_binding evidence_scope
    exclusion_assessment_ref_binding exclusion_contract_binding
    exclusion_contract_ref_binding expected_ref fact_kind fact_ref
    failure_catalog_entry failure_occurrence failure_occurrence_binding
    failure_reason failure_reason_binding failure_reason_catalog fallback_id
    fallback_ref final_terminal fixture_authority fixture_configuration
    fixture_configuration_ref fixture_loading fixture_payload_facts
    fixture_registration_ref fixture_replay_probe fixture_unqualified_reason_ref
    generated_fixture_artifact generator generator_id generator_ref
    generator_version grant graph_origin grid_points implementation_digest
    implementation_id implementation_manifest implementation_version
    inclusion_probability_accounting_ref_binding infrastructure_failure_binding
    infrastructure_failure_ref initial_value_count initial_values
    intended_evidence_unit_ref intended_slot_ref intended_unit_count
    intended_unit_link_decision intended_unit_link_decision_ref
    intended_unit_pairs invocation_output kind latent_codec_id
    link_decision_pairs link_evidence_ref loaded_case loaded_dependencies
    loaded_dependency materialization_state materialized membership_evidence_binding
    missingness_adjustment_binding near_duplicate_decision
    near_duplicate_decision_binding near_duplicate_policy_unavailable_reason_ref
    object_id object_version observed_physical_payload_fingerprint
    observed_physical_payload_fingerprint_ref occurrence_evidence_category
    occurrence_evidence_fallback origin origin_evidence_ref origin_evidence_refs
    origin_tag outcome outcome_kind outcome_replacement_binding
    owner_unavailable_reason_ref package pair payload payload_facts
    payload_facts_binding payload_ref payload_ref_binding pending
    pending_attempt_binding pending_attempt_pairs period
    physical_instance_collision_binding physical_payload_fingerprint physical_system_ref
    physical_payload_fingerprint_ref physical_payload_ref pin platform_tag
    policy_authority_ref policy_decision_kind policy_unavailable_reason_ref
    population_ref post_result_request predecessor_attempt_ordinal
    predecessor_request predecessor_request_ref primary primary_population_ref
    probe probe_ref production_inputs projection
    prospective_censoring_policy_binding prospective_censoring_policy_ref
    prospective_exclusion_contract_ref_binding protected_payload
    protected_payload_digest protected_payload_ref provider provisional_outcome
    provisional_terminal python_implementation python_version
    qualification_evidence query_observation_provenance realized_case_ref
    realized_outcome realized_outcome_counts realized_valid_case_refs reason
    reason_code reason_id reason_ref reason_version recomputed_ref
    reconstructed_case_ref reconstructed_protected_payload_ref
    reconstructed_source_event_ref record record_type ref ref_type
    registered_policy_ref related_population_bindings replacement_lineage_refs
    replacement_policy replacement_trigger replacement_trigger_binding
    replay_capability replay_identity_facts replay_ref replay_scheme_id
    replay_scheme_version representation_ref request request_identity request_ref
    requested_fact_kind reservation_issuer_ref resolution_evidence_ref
    resolution_policy_ref resolved_dependencies result
    result_applicability_reasons result_pairs result_record role_binding role_key
    root_ref runtime_contract_version sampling_plan sampling_plan_binding
    sampling_plan_ref sampling_role schema_version screening_design_ref_binding
    seed_domain selection_population_ref semantic_equivalence_ref source_event
    source_event_pair source_event_ref source_payload_inapplicable_reason_ref
    source_provenance_refs spatial_point_count stage statistics_objective_ref
    subject_case_ref subject_physical_payload_fingerprint
    subject_physical_payload_fingerprint_ref subject_result subject_result_ref
    successor_attempt_ordinal successor_attempt_ref
    successor_authorization_binding successor_execution_binding successor_output
    successor_output_pair successor_request successor_request_pair supersedes
    support_authority support_contract support_decision support_decision_binding
    support_decision_ref tag terminal terminal_reason terminal_resolution
    terminal_stage time_point_count trigger_failure_binding
    unavailable_reason_ref validated_case_facts validated_case_facts_binding
    verdict verdict_kind viscosity aggregation_policy_ref internal_field_ids
    intended_estimand_or_reporting_ref measurement_applicability_binding
    observation_population_binding protected_field_ids public_field_ids
    query_population_binding release_policy_ref value
    """.split())


def _trusted_path(value: object) -> str:
    """Retain only schema-shaped paths, never caller-controlled values."""

    if type(value) is not str:
        raise TypeError("generator error path must be a string")
    if value == "":
        return ""
    if len(value) > 256 or not value.startswith("/") or value.endswith("/"):
        return ""
    segments = value[1:].split("/")
    if not segments:
        return ""
    trusted: list[str] = []
    for segment in segments:
        if _PATH_SEGMENT.fullmatch(segment) is None:
            break
        if segment.isdecimal() or segment in _TRUSTED_PATH_SEGMENTS:
            trusted.append(segment)
        else:
            break
    return f"/{'/'.join(trusted)}" if trusted else ""


class GeneratorInputCode(str, Enum):
    """Closed input and canonical-identity rejection codes."""

    WRONG_TYPE = "WRONG_TYPE"
    INVALID_VALUE = "INVALID_VALUE"
    INVALID_CANONICAL_BYTES = "INVALID_CANONICAL_BYTES"
    TRAILING_BYTES = "TRAILING_BYTES"
    REF_DIGEST_MISMATCH = "REF_DIGEST_MISMATCH"
    CROSS_CHALLENGE = "CROSS_CHALLENGE"
    STALE_BINDING = "STALE_BINDING"
    INCOMPLETE_BINDING = "INCOMPLETE_BINDING"
    REPLAY_RESERVATION_INVALID = "REPLAY_RESERVATION_INVALID"
    AUTHORITY_INTERFACE_INVALID = "AUTHORITY_INTERFACE_INVALID"


class GeneratorServiceCode(str, Enum):
    """Closed sanitized failures for protected post-admission operations."""

    AUTHORITY_UNAVAILABLE = "AUTHORITY_UNAVAILABLE"
    REPLAY_UNAVAILABLE = "REPLAY_UNAVAILABLE"
    FINALIZATION_INVALID = "FINALIZATION_INVALID"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class GeneratorDisclosureCode(str, Enum):
    """Closed sanitized failures at the public projection boundary."""

    ARTIFACT_REQUIRED = "ARTIFACT_REQUIRED"
    CASE_PAIRING_INVALID = "CASE_PAIRING_INVALID"
    PROJECTION_NOT_PERMITTED = "PROJECTION_NOT_PERMITTED"


INPUT_REJECTION_MESSAGES = {
    GeneratorInputCode.WRONG_TYPE: "input has the wrong exact type",
    GeneratorInputCode.INVALID_VALUE: "input value is outside the closed contract",
    GeneratorInputCode.INVALID_CANONICAL_BYTES: "canonical bytes are invalid",
    GeneratorInputCode.TRAILING_BYTES: "canonical bytes contain trailing data",
    GeneratorInputCode.REF_DIGEST_MISMATCH: "object and ref digest do not match",
    GeneratorInputCode.CROSS_CHALLENGE: "bound values do not share one Challenge",
    GeneratorInputCode.STALE_BINDING: "a bound object and identity do not match",
    GeneratorInputCode.INCOMPLETE_BINDING: "a required exact binding is incomplete",
    GeneratorInputCode.REPLAY_RESERVATION_INVALID: (
        "replay reservation is unavailable for this request"
    ),
    GeneratorInputCode.AUTHORITY_INTERFACE_INVALID: (
        "required nominal authority interface is unavailable"
    ),
}

SERVICE_FAILURE_MESSAGES = {
    GeneratorServiceCode.AUTHORITY_UNAVAILABLE: "required generator authority is unavailable",
    GeneratorServiceCode.REPLAY_UNAVAILABLE: "replay evidence is unavailable",
    GeneratorServiceCode.FINALIZATION_INVALID: "generation finalization inputs are inconsistent",
    GeneratorServiceCode.INTERNAL_FAILURE: "generator operation could not be completed",
}

DISCLOSURE_FAILURE_MESSAGES = {
    GeneratorDisclosureCode.ARTIFACT_REQUIRED: "a constructed fixture artifact is required",
    GeneratorDisclosureCode.CASE_PAIRING_INVALID: "public case identity pairing is invalid",
    GeneratorDisclosureCode.PROJECTION_NOT_PERMITTED: "generation result is not publicly projectable",
}


class GeneratorError(Exception):
    """Base class for exact generator-runtime failures."""

    def __init__(self, code: str, message: str, *, path: str = "") -> None:
        if type(code) is not str or not code:
            raise TypeError("generator error code must be a nonempty string")
        if type(message) is not str or not message:
            raise TypeError("generator error message must be a nonempty string")
        self.code = code
        self.path = _trusted_path(path)
        self.__cause__ = None
        self.__suppress_context__ = True
        super().__init__(message)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, path={self.path!r})"


class GeneratorValidationError(GeneratorError, ValueError):
    """A malformed or inconsistent value was rejected before admission."""

    def __init__(
        self,
        code: GeneratorInputCode | str,
        *,
        path: str = "",
    ) -> None:
        try:
            normalized = (
                code if type(code) is GeneratorInputCode else GeneratorInputCode(code)
            )
        except (TypeError, ValueError):
            normalized = None
        if normalized is None:
            raise TypeError("code must be one exact GeneratorInputCode")
        super().__init__(
            normalized.value,
            INPUT_REJECTION_MESSAGES[normalized],
            path=path,
        )


class GeneratorCanonicalEncodingError(GeneratorValidationError):
    """A value cannot be represented by the closed B-03 profile."""

    def __init__(self, *, path: str = "") -> None:
        super().__init__(GeneratorInputCode.INVALID_VALUE, path=path)


class GeneratorCanonicalDecodingError(GeneratorValidationError):
    """Canonical bytes are malformed, ambiguous, unknown, or trailing."""

    def __init__(self, *, trailing: bool = False, path: str = "") -> None:
        super().__init__(
            (
                GeneratorInputCode.TRAILING_BYTES
                if trailing
                else GeneratorInputCode.INVALID_CANONICAL_BYTES
            ),
            path=path,
        )


class GeneratorReferenceMismatchError(GeneratorValidationError):
    """Canonical bytes or scope differ from an exact nominal ref."""

    def __init__(self, *, path: str = "") -> None:
        super().__init__(GeneratorInputCode.REF_DIGEST_MISMATCH, path=path)


class GeneratorServiceError(GeneratorError, RuntimeError):
    """A protected operation failed without exposing its inputs or cause."""

    def __init__(
        self,
        code: GeneratorServiceCode | str,
        *,
        path: str = "",
    ) -> None:
        try:
            normalized = (
                code
                if type(code) is GeneratorServiceCode
                else GeneratorServiceCode(code)
            )
        except (TypeError, ValueError):
            normalized = None
        if normalized is None:
            raise TypeError("code must be one exact GeneratorServiceCode")
        super().__init__(
            normalized.value,
            SERVICE_FAILURE_MESSAGES[normalized],
            path=path,
        )


class GeneratorDisclosureError(GeneratorError, ValueError):
    """A public projection request crossed the closed disclosure boundary."""

    def __init__(
        self,
        code: GeneratorDisclosureCode | str,
        *,
        path: str = "",
    ) -> None:
        try:
            normalized = (
                code
                if type(code) is GeneratorDisclosureCode
                else GeneratorDisclosureCode(code)
            )
        except (TypeError, ValueError):
            normalized = None
        if normalized is None:
            raise TypeError("code must be one exact GeneratorDisclosureCode")
        super().__init__(
            normalized.value,
            DISCLOSURE_FAILURE_MESSAGES[normalized],
            path=path,
        )


CanonicalEncodingError = GeneratorCanonicalEncodingError
CanonicalDecodingError = GeneratorCanonicalDecodingError
ReferenceMismatchError = GeneratorReferenceMismatchError


def reject(code: GeneratorInputCode, path: str = "") -> GeneratorValidationError:
    """Construct a fixed hard-rejection failure without echoing input."""

    return GeneratorValidationError(code, path=path)


__all__ = [
    "DISCLOSURE_FAILURE_MESSAGES",
    "INPUT_REJECTION_MESSAGES",
    "SERVICE_FAILURE_MESSAGES",
    "CanonicalDecodingError",
    "CanonicalEncodingError",
    "GeneratorCanonicalDecodingError",
    "GeneratorCanonicalEncodingError",
    "GeneratorDisclosureCode",
    "GeneratorDisclosureError",
    "GeneratorError",
    "GeneratorInputCode",
    "GeneratorReferenceMismatchError",
    "GeneratorServiceCode",
    "GeneratorServiceError",
    "GeneratorValidationError",
    "ReferenceMismatchError",
]
