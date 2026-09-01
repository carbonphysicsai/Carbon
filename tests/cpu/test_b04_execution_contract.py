"""Focused closed execution/comparison boundary tests for B-04."""

from __future__ import annotations

import inspect
import pickle
from dataclasses import FrozenInstanceError, fields
from types import MappingProxyType

import pytest

import carbon.evaluation.comparison as comparison_runtime
import carbon.evaluation.execution as execution_runtime
from carbon.authoring.primitives import MAX_CANONICAL_TUPLE_ITEMS
from carbon.evaluation.comparison import (
    COMPARISON_REASON_PRECEDENCE,
    ReferenceComparisonRecord,
    select_comparison_terminal,
)
from carbon.evaluation.enums import (
    COMPARISON_OUTCOME_REASON_COMPATIBILITY,
    RESOLUTION_OUTCOME_REASON_COMPATIBILITY,
    RUN_OUTCOME_REASON_COMPATIBILITY,
    ReferenceComparisonOutcome,
    ReferenceComparisonReason,
    ReferenceFailureReason,
    ReferenceRunOutcome,
    ResolutionOutcome,
    ResolutionReason,
)
from carbon.evaluation.errors import ReferenceInputCode, ReferenceValidationError
from carbon.evaluation.execution import (
    RESOLUTION_REASON_PRECEDENCE,
    RUN_REASON_PRECEDENCE,
    PrimaryReferenceRequest,
    PrimaryRunGrant,
    ReferenceResolutionRecord,
    ReferenceRunRecord,
    WitnessReferenceRequest,
    WitnessRunGrant,
    select_resolution_terminal,
    select_run_terminal,
)
from carbon.evaluation.model import OptionalBinding
from carbon.evaluation.refs import PrimaryReferenceRequestRef
from carbon.evaluation.runners import (
    PrimaryReferenceRunner,
    WitnessReferenceRunner,
    require_primary_runner,
    require_witness_runner,
)
from carbon.registry.model import ChallengeKey


def _uninitialized(exact_type: type):
    """Make an exact nominal shell only for pure selector/interface tests."""

    return object.__new__(exact_type)


def test_selector_outcome_maps_are_immutable_exact_enum_derivations() -> None:
    expected_resolution: dict[ResolutionReason, ResolutionOutcome | None] = {}
    for outcome, reasons in RESOLUTION_OUTCOME_REASON_COMPATIBILITY.items():
        for reason in reasons:
            prior = expected_resolution.get(reason)
            expected_resolution[reason] = (
                outcome if prior is None or prior is outcome else None
            )
    expected_run = {
        reason: outcome
        for outcome, reasons in RUN_OUTCOME_REASON_COMPATIBILITY.items()
        for reason in reasons
    }
    expected_comparison = {
        reason: outcome
        for outcome, reasons in COMPARISON_OUTCOME_REASON_COMPATIBILITY.items()
        for reason in reasons
    }
    mappings = (
        (execution_runtime._RESOLUTION_OUTCOMES, expected_resolution),
        (execution_runtime._RUN_OUTCOMES, expected_run),
        (comparison_runtime._COMPARISON_OUTCOMES, expected_comparison),
    )
    for actual, expected in mappings:
        assert type(actual) is MappingProxyType
        assert actual == expected
        key = next(iter(actual))
        with pytest.raises(TypeError):
            actual[key] = actual[key]


@pytest.mark.parametrize(
    ("request_type", "outcome"),
    (
        (PrimaryReferenceRequest, ResolutionOutcome.PRIMARY_GRANT_ISSUED),
        (WitnessReferenceRequest, ResolutionOutcome.WITNESS_GRANT_ISSUED),
    ),
)
def test_resolution_success_is_fixed_by_nominal_request_family(
    request_type: type,
    outcome: ResolutionOutcome,
) -> None:
    assert select_resolution_terminal(_uninitialized(request_type), ()) == (
        outcome,
        ResolutionReason.RESOLUTION_REQUIREMENTS_SATISFIED,
    )


@pytest.mark.parametrize(
    ("reason", "outcome"),
    (
        (ResolutionReason.POLICY_PRIMARY_MISSING, ResolutionOutcome.POLICY_INCOMPLETE),
        (ResolutionReason.POLICY_ENTRY_INCOMPLETE, ResolutionOutcome.POLICY_INCOMPLETE),
        (ResolutionReason.ROLE_NOT_REGISTERED, ResolutionOutcome.ROLE_UNAVAILABLE),
        (ResolutionReason.CASE_NOT_APPLICABLE, ResolutionOutcome.NOT_APPLICABLE),
        (ResolutionReason.CASE_UNSUPPORTED, ResolutionOutcome.UNSUPPORTED),
        (
            ResolutionReason.APPLICABILITY_ASSESSMENT_UNAVAILABLE,
            ResolutionOutcome.APPLICABILITY_UNRESOLVED,
        ),
        (
            ResolutionReason.QUALIFICATION_BINDING_UNAVAILABLE,
            ResolutionOutcome.QUALIFICATION_UNAVAILABLE,
        ),
        (
            ResolutionReason.RESOURCE_POLICY_UNAVAILABLE,
            ResolutionOutcome.RESOURCE_AUTHORIZATION_UNAVAILABLE,
        ),
        (
            ResolutionReason.RESOURCE_CAPACITY_UNAVAILABLE,
            ResolutionOutcome.RESOURCE_AUTHORIZATION_UNAVAILABLE,
        ),
        (
            ResolutionReason.RESOLUTION_IDENTITY_MISMATCH,
            ResolutionOutcome.IDENTITY_OR_PROVENANCE_FAILURE,
        ),
        (
            ResolutionReason.RESOLUTION_PROVENANCE_INVALID,
            ResolutionOutcome.IDENTITY_OR_PROVENANCE_FAILURE,
        ),
    ),
)
def test_resolution_matrix_is_closed(
    reason: ResolutionReason,
    outcome: ResolutionOutcome,
) -> None:
    assert select_resolution_terminal(
        _uninitialized(PrimaryReferenceRequest), (reason,)
    ) == (outcome, reason)


def test_resolution_precedence_cannot_be_overridden_by_success() -> None:
    observed = tuple(reversed(RESOLUTION_REASON_PRECEDENCE))
    assert select_resolution_terminal(
        _uninitialized(PrimaryReferenceRequest), observed
    ) == (
        ResolutionOutcome.IDENTITY_OR_PROVENANCE_FAILURE,
        ResolutionReason.RESOLUTION_IDENTITY_MISMATCH,
    )


@pytest.mark.parametrize(
    ("reason", "outcome"),
    (
        (
            ReferenceFailureReason.UNCERTAINTY_EVIDENCE_UNRESOLVED,
            ReferenceRunOutcome.UNCERTAINTY_UNRESOLVED,
        ),
        (
            ReferenceFailureReason.CONDITIONING_EVIDENCE_UNRESOLVED,
            ReferenceRunOutcome.CONDITIONING_UNRESOLVED,
        ),
        (
            ReferenceFailureReason.APPLICABILITY_ASSESSMENT_UNAVAILABLE,
            ReferenceRunOutcome.APPLICABILITY_UNRESOLVED,
        ),
        (
            ReferenceFailureReason.POLICY_ENTRY_NOT_APPLICABLE,
            ReferenceRunOutcome.NOT_APPLICABLE,
        ),
        (
            ReferenceFailureReason.POLICY_ENTRY_UNSUPPORTED,
            ReferenceRunOutcome.UNSUPPORTED,
        ),
        (
            ReferenceFailureReason.NUMERICAL_NONCONVERGENCE,
            ReferenceRunOutcome.NUMERICAL_FAILURE,
        ),
        (
            ReferenceFailureReason.NUMERICAL_INVALID_RESULT,
            ReferenceRunOutcome.NUMERICAL_FAILURE,
        ),
        (
            ReferenceFailureReason.REQUEST_OR_GRANT_INVALID,
            ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
        ),
        (
            ReferenceFailureReason.PROVIDER_RESULT_MALFORMED,
            ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
        ),
        (
            ReferenceFailureReason.PROVENANCE_INVALID,
            ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
        ),
        (
            ReferenceFailureReason.VERSION_OR_IDENTITY_MISMATCH,
            ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
        ),
        (
            ReferenceFailureReason.DEPENDENCY_UNAVAILABLE,
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
        ),
        (
            ReferenceFailureReason.TRANSPORT_FAILURE,
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
        ),
        (
            ReferenceFailureReason.PROCESS_FAILURE,
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
        ),
        (
            ReferenceFailureReason.CAPACITY_UNAVAILABLE,
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
        ),
        (
            ReferenceFailureReason.RESOURCE_LIMIT,
            ReferenceRunOutcome.INFRASTRUCTURE_FAILURE,
        ),
        (ReferenceFailureReason.TIMEOUT, ReferenceRunOutcome.INFRASTRUCTURE_FAILURE),
        (
            ReferenceFailureReason.TRUSTED_CANCELLATION,
            ReferenceRunOutcome.CANCELLED,
        ),
    ),
)
def test_run_matrix_keeps_reference_failures_typed_and_separate(
    reason: ReferenceFailureReason,
    outcome: ReferenceRunOutcome,
) -> None:
    assert select_run_terminal((reason,)) == (
        outcome,
        OptionalBinding.present(reason),
    )


def test_run_success_has_no_failure_reason_and_precedence_is_total() -> None:
    assert select_run_terminal(()) == (
        ReferenceRunOutcome.SUPPORTED,
        OptionalBinding.absent(),
    )
    observed = tuple(reversed(RUN_REASON_PRECEDENCE))
    assert select_run_terminal(observed) == (
        ReferenceRunOutcome.MALFORMED_OR_PROVENANCE_FAILURE,
        OptionalBinding.present(ReferenceFailureReason.REQUEST_OR_GRANT_INVALID),
    )


@pytest.mark.parametrize(
    ("reason", "outcome"),
    tuple(
        (
            reason,
            (
                ReferenceComparisonOutcome.AGREEMENT_WITHIN_REGISTERED_POLICY
                if reason is ReferenceComparisonReason.COMPARISON_REQUIREMENTS_SATISFIED
                else (
                    ReferenceComparisonOutcome.CONTESTED_DISAGREEMENT
                    if reason
                    is ReferenceComparisonReason.REGISTERED_DISAGREEMENT_EXCEEDED
                    else ReferenceComparisonOutcome.COMPARISON_INDETERMINATE
                )
            ),
        )
        for reason in ReferenceComparisonReason
    ),
)
def test_comparison_matrix_is_closed(
    reason: ReferenceComparisonReason,
    outcome: ReferenceComparisonOutcome,
) -> None:
    assert select_comparison_terminal((reason,)) == (outcome, reason)


def test_comparison_precedence_does_not_average_or_promote_disagreement() -> None:
    assert select_comparison_terminal(
        tuple(reversed(COMPARISON_REASON_PRECEDENCE))
    ) == (
        ReferenceComparisonOutcome.COMPARISON_INDETERMINATE,
        ReferenceComparisonReason.COMPARISON_INPUT_IDENTITY_MISMATCH,
    )
    assert select_comparison_terminal(
        (ReferenceComparisonReason.REGISTERED_DISAGREEMENT_EXCEEDED,)
    ) == (
        ReferenceComparisonOutcome.CONTESTED_DISAGREEMENT,
        ReferenceComparisonReason.REGISTERED_DISAGREEMENT_EXCEEDED,
    )


@pytest.mark.parametrize(
    "selector,args",
    (
        (select_run_terminal, ([ReferenceFailureReason.TIMEOUT],)),
        (
            select_comparison_terminal,
            ([ReferenceComparisonReason.COMPARISON_METHOD_UNAVAILABLE],),
        ),
    ),
)
def test_selectors_reject_open_or_coerced_reason_collections(selector, args) -> None:
    with pytest.raises(ReferenceValidationError) as captured:
        selector(*args)
    assert captured.value.code == ReferenceInputCode.WRONG_TYPE.value


def test_execution_helpers_reject_over_limit_tuples_before_traversal() -> None:
    over_limit = (object(),) * (MAX_CANONICAL_TUPLE_ITEMS + 1)
    challenge = ChallengeKey("b04_over_limit", "1.0")
    calls = (
        lambda: execution_runtime._ref_tuple(
            over_limit,
            PrimaryReferenceRequestRef,
            challenge,
            "/refs",
        ),
        lambda: execution_runtime._model_tuple(
            over_limit,
            OptionalBinding,
            challenge,
            "/models",
        ),
        lambda: comparison_runtime._owner_set(
            over_limit,
            "provenance",
            challenge,
            "/owners",
        ),
    )
    for call in calls:
        with pytest.raises(ReferenceValidationError) as captured:
            call()
        assert captured.value.code == ReferenceInputCode.INVALID_VALUE.value


class _PrimaryOnly:
    def run_primary(self, grant, request):
        del grant, request
        raise AssertionError("interface conformance must not invoke a provider")


class _WitnessOnly:
    def run_witness(self, grant, request):
        del grant, request
        raise AssertionError("interface conformance must not invoke a provider")


def test_primary_and_witness_runner_interfaces_are_not_interchangeable() -> None:
    primary = _PrimaryOnly()
    witness = _WitnessOnly()
    assert isinstance(primary, PrimaryReferenceRunner)
    assert not isinstance(primary, WitnessReferenceRunner)
    assert isinstance(witness, WitnessReferenceRunner)
    assert not isinstance(witness, PrimaryReferenceRunner)
    assert require_primary_runner(primary) is primary
    assert require_witness_runner(witness) is witness
    with pytest.raises(ReferenceValidationError):
        require_witness_runner(primary)
    with pytest.raises(ReferenceValidationError):
        require_primary_runner(witness)


@pytest.mark.parametrize(
    ("require_runner", "method_name"),
    (
        (require_primary_runner, "run_primary"),
        (require_witness_runner, "run_witness"),
    ),
)
def test_runner_interface_inspection_never_invokes_dynamic_attributes(
    require_runner,
    method_name: str,
) -> None:
    class DynamicRunner:
        reads = 0

        def __getattr__(self, name):
            self.reads += 1
            if name == method_name:
                return lambda grant, request: (grant, request)
            raise RuntimeError("protected dynamic attribute detail")

    runner = DynamicRunner()
    with pytest.raises(ReferenceValidationError) as captured:
        require_runner(runner)
    assert captured.value.code == ReferenceInputCode.AUTHORITY_INTERFACE_INVALID.value
    assert captured.value.path == ""
    assert runner.reads == 0


def test_runner_static_inspection_rejects_unsafe_and_dual_roles() -> None:
    class HostileDescriptor:
        reads = 0

        def __get__(self, instance, owner):
            del instance, owner
            self.reads += 1
            raise RuntimeError("protected runner descriptor detail")

    descriptor = HostileDescriptor()

    class DescriptorPrimary:
        run_primary = descriptor

    class NoncallablePrimary:
        run_primary = object()

    class DualRunner:
        def run_primary(self, grant, request):
            del grant, request

        def run_witness(self, grant, request):
            del grant, request

    for value, requirement in (
        (DescriptorPrimary(), require_primary_runner),
        (NoncallablePrimary(), require_primary_runner),
        (DualRunner(), require_primary_runner),
        (DualRunner(), require_witness_runner),
    ):
        with pytest.raises(ReferenceValidationError) as captured:
            requirement(value)
        assert (
            captured.value.code == ReferenceInputCode.AUTHORITY_INTERFACE_INVALID.value
        )
        assert captured.value.path == ""
    assert descriptor.reads == 0


def test_execution_record_declaration_order_matches_d11() -> None:
    expected = {
        PrimaryReferenceRequest: (
            "answer_key_authority_target",
            "case_ref",
            "challenge_key",
            "disclosure_policy_ref",
            "execution_target",
            "idempotency_ref",
            "policy_ref",
            "representation_ref",
            "request_id",
            "request_version",
            "requested_resource_policy_ref",
            "scope_binding",
        ),
        WitnessReferenceRequest: (
            "answer_key_authority_target",
            "case_ref",
            "challenge_key",
            "disclosure_policy_ref",
            "execution_target",
            "idempotency_ref",
            "policy_ref",
            "representation_ref",
            "request_id",
            "request_version",
            "requested_resource_policy_ref",
            "scope_binding",
        ),
        PrimaryRunGrant: (
            "answer_key_authority_target",
            "authority_function",
            "capability_ref",
            "case_ref",
            "challenge_key",
            "component_entry_refs",
            "configuration_ref",
            "disclosure_policy_ref",
            "environment_ref",
            "evidence_role_binding",
            "execution_target",
            "grant_id",
            "grant_version",
            "hardware_ref",
            "implementation_ref",
            "issuance_token",
            "issuer_ref",
            "method_ref",
            "policy_ref",
            "precision_ref",
            "representation_ref",
            "request_ref",
            "resource_authorization_ref",
            "scope_binding",
            "source_class",
        ),
        WitnessRunGrant: (
            "answer_key_authority_target",
            "authority_function",
            "capability_ref",
            "case_ref",
            "challenge_key",
            "component_entry_refs",
            "configuration_ref",
            "disclosure_policy_ref",
            "environment_ref",
            "evidence_role_binding",
            "execution_target",
            "grant_id",
            "grant_version",
            "hardware_ref",
            "implementation_ref",
            "issuance_token",
            "issuer_ref",
            "method_ref",
            "policy_ref",
            "precision_ref",
            "representation_ref",
            "request_ref",
            "resource_authorization_ref",
            "scope_binding",
            "source_class",
        ),
        ReferenceResolutionRecord: (
            "answer_key_authority_target",
            "applicability_assessment",
            "authority_function",
            "case_ref",
            "challenge_key",
            "evidence_role_binding",
            "execution_target",
            "grant_binding",
            "outcome",
            "policy_ref",
            "qualification_binding",
            "reason",
            "request_binding",
            "resolution_id",
            "resolution_version",
            "resolver_ref",
            "resource_policy_ref",
            "scope_binding",
            "source_class",
        ),
        ReferenceRunRecord: (
            "answer_key_authority_target",
            "applicability_assessment",
            "artifact_binding",
            "authority_function",
            "case_ref",
            "challenge_key",
            "component_bindings",
            "conditioning_assessment",
            "configuration_ref",
            "diagnostics_ref",
            "environment_ref",
            "evidence_role_binding",
            "execution_target",
            "grant_binding",
            "hardware_ref",
            "implementation_ref",
            "method_ref",
            "outcome",
            "policy_ref",
            "precision_ref",
            "provenance_binding",
            "reason",
            "representation_ref",
            "request_binding",
            "resolution_ref",
            "resource_receipt_ref",
            "run_id",
            "run_version",
            "scope_binding",
            "source_class",
            "uncertainty_binding",
        ),
        ReferenceComparisonRecord: (
            "answer_key_authority_target",
            "applicability_evidence_refs",
            "case_ref",
            "challenge_key",
            "comparison_id",
            "comparison_method_ref",
            "comparison_policy_ref",
            "comparison_version",
            "dependency_disclosures",
            "evidence_refs",
            "outcome",
            "policy_ref",
            "primary_entry_refs",
            "primary_run_ref",
            "reason",
            "representation_ref",
            "scope_binding",
            "uncertainty_treatment_ref",
            "witness_entry_refs",
            "witness_run_ref",
            "witness_target",
        ),
    }
    assert {
        record_type: tuple(field.name for field in fields(record_type))
        for record_type in expected
    } == expected


@pytest.mark.parametrize(
    "record_type",
    (
        PrimaryReferenceRequest,
        WitnessReferenceRequest,
        PrimaryRunGrant,
        WitnessRunGrant,
        ReferenceResolutionRecord,
        ReferenceRunRecord,
        ReferenceComparisonRecord,
    ),
)
def test_protected_execution_records_do_not_repr_or_pickle(record_type: type) -> None:
    value = _uninitialized(record_type)
    assert repr(value) == f"{record_type.__name__}(<protected>)"
    with pytest.raises(TypeError):
        pickle.dumps(value)
    with pytest.raises(FrozenInstanceError):
        value.challenge_key = "protected"


def test_runner_surface_has_no_generic_mode_fallback_or_io_parameter() -> None:
    source = "\n".join(
        (
            inspect.getsource(PrimaryReferenceRunner),
            inspect.getsource(WitnessReferenceRunner),
        )
    )
    assert "run_primary" in source and "run_witness" in source
    for forbidden in (
        "truth_mode",
        "fallback",
        "filesystem",
        "path:",
        "uri:",
        "code:",
        "solver:",
    ):
        assert forbidden not in source.lower()
