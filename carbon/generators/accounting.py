"""Exact B-03 attempt, successor, and intended-population accounting.

This module has no retry loop and accepts no caller-provided execution flags,
counts, denominators, or realized-outcome overrides.  Replacement execution is
proved only by an exact admitted successor request and invocation output.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from itertools import pairwise
from typing import Protocol, final

from carbon.authoring.cases import CanonicalChallengeCase
from carbon.authoring.errors import AuthoringError
from carbon.authoring.evidence import (
    ReplacementDecision,
    ReplacementDecisionKind,
    ReplacementPolicyBinding,
    ReplacementPolicyBindingKind,
    validate_replacement_decision,
)
from carbon.authoring.model import ApplicabilityBinding
from carbon.authoring.primitives import reconstruct_challenge_key, validate_uint64
from carbon.authoring.refs import (
    CanonicalChallengeCaseRef,
    ChallengeScope,
    InstanceDistributionContractRef,
    SamplingPlanRef,
    require_owner_ref,
)
from carbon.authoring.sampling import (
    ReplacementPolicy,
    ReplacementPolicyKind,
    ReplacementTrigger,
)
from carbon.registry.model import ChallengeKey

from .errors import GeneratorInputCode, GeneratorValidationError
from .model import (
    ApplicabilityReasonKind,
    GenerationRoleBinding,
    GenerationSourceEvent,
    GeneratorFailureOccurrence,
    GeneratorFailureReason,
    GeneratorOutcomeKind,
    GeneratorRequest,
    GeneratorRequestIdentity,
    GeneratorResult,
    GeneratorResultRecord,
    GeneratorTerminalStage,
    RecordRefBinding,
    RecordRefBindingTag,
    RecordRefPair,
    SourceMaterializationState,
)
from .refs import (
    AttemptAccountingDecisionRef,
    AttemptAccountingDirectiveRef,
    BurgersFixtureConfigurationRef,
    CensoringVerdictRef,
    GenerationAccountingSummaryRef,
    GenerationAttemptRecordRef,
    GeneratorEnvironmentRef,
    GeneratorReplayCommitmentRef,
    GeneratorRequestRef,
    GeneratorResultRef,
    IntendedUnitAccountingRef,
    PendingGenerationAttemptRef,
    SupportExclusionDecisionRef,
)

_MAX_UINT64 = (1 << 64) - 1


def _wrong(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.WRONG_TYPE, path=path)


def _invalid(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.INVALID_VALUE, path=path)


def _cross_challenge(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.CROSS_CHALLENGE, path=path)


def _stale(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.STALE_BINDING, path=path)


def _incomplete(path: str) -> GeneratorValidationError:
    return GeneratorValidationError(GeneratorInputCode.INCOMPLETE_BINDING, path=path)


def _exact(value: object, expected: type, path: str) -> object:
    if type(value) is not expected:
        raise _wrong(path)
    return value


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AuthoringError, TypeError, ValueError):
        pass
    raise _wrong(path)


def _uint64(value: object, path: str) -> int:
    try:
        return validate_uint64(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    raise _invalid(path)


def _owner(
    value: object,
    kind: str,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> object:
    try:
        result = require_owner_ref(value, kind)
    except (AuthoringError, TypeError, ValueError):
        result = None
    if result is None:
        raise _wrong(path)
    scope = result.scope_binding
    if type(scope) is not ChallengeScope or scope.challenge_key != challenge_key:
        raise _cross_challenge(path)
    return result


def _top_ref(
    value: object,
    expected: type,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> object:
    result = _exact(value, expected, path)
    if result.challenge_key != challenge_key:
        raise _cross_challenge(path)
    return result


def _generator_ref(
    value: object,
    expected: type,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> object:
    result = _exact(value, expected, path)
    if result.challenge_key != challenge_key:
        raise _cross_challenge(path)
    return result


def _record_binding(value: object, path: str) -> RecordRefBinding:
    return _exact(value, RecordRefBinding, path)  # type: ignore[return-value]


def _applicability(value: object, path: str) -> ApplicabilityBinding:
    return _exact(value, ApplicabilityBinding, path)  # type: ignore[return-value]


def _require_not_applicable(
    binding: ApplicabilityBinding,
    reason_ref: object,
    path: str,
) -> None:
    if binding.is_bound or binding.value != reason_ref:
        raise _stale(path)


def _binding_owner(
    value: object,
    kind: str,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> ApplicabilityBinding:
    binding = _applicability(value, path)
    if binding.is_bound:
        _owner(binding.value, kind, challenge_key=challenge_key, path=path)
    else:
        _owner(
            binding.value,
            "applicability_reason",
            challenge_key=challenge_key,
            path=path,
        )
    return binding


def _binding_generator_ref(
    value: object,
    expected: type,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> ApplicabilityBinding:
    binding = _applicability(value, path)
    if binding.is_bound:
        _generator_ref(
            binding.value,
            expected,
            challenge_key=challenge_key,
            path=path,
        )
    else:
        _owner(
            binding.value,
            "applicability_reason",
            challenge_key=challenge_key,
            path=path,
        )
    return binding


def _binding_authoring(
    value: object,
    expected: type,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> ApplicabilityBinding:
    binding = _applicability(value, path)
    if binding.is_bound:
        _exact(binding.value, expected, path)
    else:
        _owner(
            binding.value,
            "applicability_reason",
            challenge_key=challenge_key,
            path=path,
        )
    return binding


def _pair(value: object, path: str) -> RecordRefPair:
    return _exact(value, RecordRefPair, path)  # type: ignore[return-value]


def _revalidated_pair(value: object, path: str) -> RecordRefPair:
    pair = _pair(value, path)
    validation_failure: tuple[str, str] | None = None
    try:
        record = replace(pair.record)
        checked = RecordRefPair(record, pair.ref)
    except GeneratorValidationError as error:
        validation_failure = (error.code, error.path)
    except Exception:  # noqa: BLE001 - protected hostile record boundary.
        validation_failure = (GeneratorInputCode.INVALID_VALUE.value, path)
    if validation_failure is not None:
        raise GeneratorValidationError(
            validation_failure[0],
            path=validation_failure[1],
        )
    return checked


def _revalidated_record_binding(value: object, path: str) -> RecordRefBinding:
    binding = _record_binding(value, path)
    if binding.is_bound:
        pair = _revalidated_pair(binding.pair, f"{path}/pair")
        return RecordRefBinding.bound(pair.record, pair.ref)
    return RecordRefBinding.not_applicable(binding.reason_ref)


def _pair_record_name(pair: RecordRefPair) -> str:
    return type(pair.record).__name__


def _reason_ref(
    identity: GeneratorRequestIdentity,
    kind: ApplicabilityReasonKind,
) -> object:
    matches = tuple(
        item.reason_ref
        for item in (
            identity.attempt_accounting_applicability_reasons
            + identity.result_applicability_reasons
        )
        if item.kind is kind
    )
    if len(matches) != 1:
        raise _invalid("/attempt_accounting_applicability_reasons")
    return matches[0]


def _binding_reason(
    binding: RecordRefBinding,
    *,
    challenge_key: ChallengeKey,
    path: str,
) -> object | None:
    if binding.tag is RecordRefBindingTag.BOUND:
        return None
    return _owner(
        binding.reason_ref,
        "applicability_reason",
        challenge_key=challenge_key,
        path=path,
    )


_OUTCOME_STAGE_MATRIX = {
    GeneratorOutcomeKind.VALID_GENERATED: frozenset(
        {GeneratorTerminalStage.CENSORING_COMPLETION}
    ),
    GeneratorOutcomeKind.REGISTERED_EXCLUSION: frozenset(
        {GeneratorTerminalStage.SUPPORT_AUTHORITY}
    ),
    GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE: frozenset(
        {
            GeneratorTerminalStage.MATERIALIZATION,
            GeneratorTerminalStage.SUPPORT_AUTHORITY,
        }
    ),
    GeneratorOutcomeKind.INVALID_CONSTRUCTION: frozenset(
        {
            GeneratorTerminalStage.CONSTRUCTION_COMPATIBILITY,
            GeneratorTerminalStage.CASE_CONSTRUCTION,
            GeneratorTerminalStage.GRAPH_VALIDATION,
        }
    ),
    GeneratorOutcomeKind.CENSORED_CASE: frozenset(
        {GeneratorTerminalStage.CENSORING_COMPLETION}
    ),
    GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE: frozenset(
        {
            GeneratorTerminalStage.CONTEXT_ACQUISITION,
            GeneratorTerminalStage.DERIVATION,
            GeneratorTerminalStage.MATERIALIZATION,
            GeneratorTerminalStage.SUPPORT_AUTHORITY,
            GeneratorTerminalStage.CASE_CONSTRUCTION,
            GeneratorTerminalStage.CENSORING_AUTHORITY,
            GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
            GeneratorTerminalStage.GRAPH_VALIDATION,
        }
    ),
}


def _outcome_stage(
    outcome: object,
    stage: object,
    *,
    path: str,
) -> tuple[GeneratorOutcomeKind, GeneratorTerminalStage]:
    checked_outcome = _exact(
        outcome,
        GeneratorOutcomeKind,
        f"{path}/outcome",
    )
    checked_stage = _exact(stage, GeneratorTerminalStage, f"{path}/stage")
    if checked_stage not in _OUTCOME_STAGE_MATRIX[checked_outcome]:
        raise _invalid(path)
    return checked_outcome, checked_stage


class AttemptAccountingDirectiveKind(str, Enum):
    """Closed authority response before an invocation can be finalized."""

    FINAL = "FINAL"
    PENDING_SUCCESSOR = "PENDING_SUCCESSOR"
    OWNER_UNAVAILABLE = "OWNER_UNAVAILABLE"


class AttemptAccountingAuthority(Protocol):
    """Nominal external owner of replacement and denominator decisions."""

    def decide_attempt_accounting(self, request: object) -> object: ...


@dataclass(frozen=True, slots=True, repr=False)
class AttemptAccountingRequest:
    """Exact post-outcome request supplied to the accounting authority."""

    challenge_key: ChallengeKey
    request_identity: GeneratorRequestIdentity
    request_ref: GeneratorRequestRef
    source_event: GenerationSourceEvent
    source_event_ref: object
    provisional_outcome: GeneratorOutcomeKind
    provisional_stage: GeneratorTerminalStage
    support_decision_binding: RecordRefBinding
    constructed_case_binding: RecordRefBinding
    censoring_verdict_binding: RecordRefBinding
    failure_reason_binding: RecordRefBinding
    failure_occurrence_binding: RecordRefBinding
    replacement_policy: ReplacementPolicy
    replacement_trigger_binding: ApplicabilityBinding[ReplacementTrigger]
    outcome_replacement_inapplicable_reason_ref: object
    successor_authorization_inapplicable_reason_ref: object
    successor_execution_inapplicable_reason_ref: object
    denominator_effect_inapplicable_reason_ref: object
    denominator_owner_unavailable_reason_ref: object
    accounting_authority_failure_ref: object

    def __post_init__(self) -> None:
        if type(self) is not AttemptAccountingRequest:
            raise _wrong("/request")
        key = _challenge(self.challenge_key)
        identity = replace(
            _exact(
                self.request_identity,
                GeneratorRequestIdentity,
                "/request_identity",
            )
        )
        request_ref = _generator_ref(
            self.request_ref,
            GeneratorRequestRef,
            challenge_key=key,
            path="/request_ref",
        )
        if identity.challenge_key != key or identity.to_ref() != request_ref:
            raise _stale("/request_identity")
        event = replace(
            _exact(self.source_event, GenerationSourceEvent, "/source_event")
        )
        event_ref = _owner(
            self.source_event_ref,
            "generation_event",
            challenge_key=key,
            path="/source_event_ref",
        )
        if event.challenge_key != key or event.to_ref() != event_ref:
            raise _stale("/source_event")
        if (
            event.request_ref != request_ref
            or event.attempt_ref != identity.attempt_ref
            or event.replay_ref != identity.replay_ref
        ):
            raise _stale("/source_event")
        outcome, stage = _outcome_stage(
            self.provisional_outcome,
            self.provisional_stage,
            path="/provisional_terminal",
        )
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "request_ref", request_ref)
        object.__setattr__(self, "source_event_ref", event_ref)
        object.__setattr__(self, "provisional_outcome", outcome)
        object.__setattr__(self, "provisional_stage", stage)

        support = _revalidated_record_binding(
            self.support_decision_binding,
            "/support_decision_binding",
        )
        constructed = _revalidated_record_binding(
            self.constructed_case_binding,
            "/constructed_case_binding",
        )
        censoring = _revalidated_record_binding(
            self.censoring_verdict_binding,
            "/censoring_verdict_binding",
        )
        failure_reason = _revalidated_record_binding(
            self.failure_reason_binding,
            "/failure_reason_binding",
        )
        failure_occurrence = _revalidated_record_binding(
            self.failure_occurrence_binding,
            "/failure_occurrence_binding",
        )
        for name, binding in (
            ("support_decision_binding", support),
            ("constructed_case_binding", constructed),
            ("censoring_verdict_binding", censoring),
            ("failure_reason_binding", failure_reason),
            ("failure_occurrence_binding", failure_occurrence),
        ):
            _binding_reason(binding, challenge_key=key, path=f"/{name}")
        from .authorities import CensoringVerdict, SupportExclusionDecision

        if support.is_bound:
            _require_pair_type(
                support.pair,
                SupportExclusionDecision,
                SupportExclusionDecisionRef,
                "/support_decision_binding",
            )
        if constructed.is_bound:
            _require_pair_type(
                constructed.pair,
                CanonicalChallengeCase,
                CanonicalChallengeCaseRef,
                "/constructed_case_binding",
            )
        if censoring.is_bound:
            _require_pair_type(
                censoring.pair,
                CensoringVerdict,
                CensoringVerdictRef,
                "/censoring_verdict_binding",
            )
        if failure_reason.is_bound:
            from .refs import (
                GeneratorFailureOccurrenceRef,
                GeneratorFailureReasonRef,
            )

            _require_pair_type(
                failure_reason.pair,
                GeneratorFailureReason,
                GeneratorFailureReasonRef,
                "/failure_reason_binding",
            )
            _require_pair_type(
                failure_occurrence.pair,
                GeneratorFailureOccurrence,
                GeneratorFailureOccurrenceRef,
                "/failure_occurrence_binding",
            )

        case_required = outcome in {
            GeneratorOutcomeKind.VALID_GENERATED,
            GeneratorOutcomeKind.CENSORED_CASE,
        } or (
            outcome is GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE
            and stage is GeneratorTerminalStage.CENSORING_AUTHORITY
        )
        if constructed.is_bound != case_required:
            raise _invalid("/constructed_case_binding")
        if constructed.is_bound and _pair_record_name(constructed.pair) != (
            "CanonicalChallengeCase"
        ):
            raise _wrong("/constructed_case_binding")
        failure_required = outcome in {
            GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
            GeneratorOutcomeKind.INVALID_CONSTRUCTION,
            GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        }
        if (
            failure_reason.is_bound != failure_required
            or failure_occurrence.is_bound != failure_required
        ):
            raise _invalid("/failure_reason_binding")
        for binding, reason_kind, path in (
            (
                support,
                ApplicabilityReasonKind.SUPPORT_DECISION_INAPPLICABLE,
                "/support_decision_binding",
            ),
            (
                constructed,
                ApplicabilityReasonKind.CONSTRUCTED_CASE_INAPPLICABLE,
                "/constructed_case_binding",
            ),
            (
                censoring,
                ApplicabilityReasonKind.CENSORING_VERDICT_INAPPLICABLE,
                "/censoring_verdict_binding",
            ),
            (
                failure_reason,
                ApplicabilityReasonKind.FAILURE_BINDING_INAPPLICABLE,
                "/failure_reason_binding",
            ),
            (
                failure_occurrence,
                ApplicabilityReasonKind.FAILURE_BINDING_INAPPLICABLE,
                "/failure_occurrence_binding",
            ),
        ):
            if not binding.is_bound and binding.reason_ref != _reason_ref(
                identity,
                reason_kind,
            ):
                raise _stale(path)

        _exact(self.replacement_policy, ReplacementPolicy, "/replacement_policy")
        trigger = _binding_authoring(
            self.replacement_trigger_binding,
            ReplacementTrigger,
            challenge_key=key,
            path="/replacement_trigger_binding",
        )
        if trigger.is_bound and outcome not in {
            GeneratorOutcomeKind.REGISTERED_EXCLUSION,
            GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
            GeneratorOutcomeKind.CENSORED_CASE,
        }:
            raise _invalid("/replacement_trigger_binding")
        for name, kind in (
            (
                "outcome_replacement_inapplicable_reason_ref",
                "applicability_reason",
            ),
            (
                "successor_authorization_inapplicable_reason_ref",
                "applicability_reason",
            ),
            (
                "successor_execution_inapplicable_reason_ref",
                "applicability_reason",
            ),
            (
                "denominator_effect_inapplicable_reason_ref",
                "applicability_reason",
            ),
            (
                "denominator_owner_unavailable_reason_ref",
                "applicability_reason",
            ),
            ("accounting_authority_failure_ref", "infrastructure_failure"),
        ):
            object.__setattr__(
                self,
                name,
                _owner(
                    getattr(self, name),
                    kind,
                    challenge_key=key,
                    path=f"/{name}",
                ),
            )
        expected_reasons = {
            "outcome_replacement_inapplicable_reason_ref": (
                ApplicabilityReasonKind.OUTCOME_REPLACEMENT_INAPPLICABLE
            ),
            "successor_authorization_inapplicable_reason_ref": (
                ApplicabilityReasonKind.SUCCESSOR_AUTHORIZATION_INAPPLICABLE
            ),
            "successor_execution_inapplicable_reason_ref": (
                ApplicabilityReasonKind.SUCCESSOR_EXECUTION_INAPPLICABLE
            ),
            "denominator_effect_inapplicable_reason_ref": (
                ApplicabilityReasonKind.DENOMINATOR_EFFECT_INAPPLICABLE
            ),
        }
        for name, reason_kind in expected_reasons.items():
            if getattr(self, name) != _reason_ref(identity, reason_kind):
                raise _stale(f"/{name}")
        if (
            self.denominator_owner_unavailable_reason_ref
            != identity.attempt_accounting_fallback.denominator_unavailable_reason_ref
            or self.accounting_authority_failure_ref
            != identity.attempt_accounting_fallback.authority_failure_ref
        ):
            raise _stale("/accounting_authority_failure_ref")
        if not trigger.is_bound and trigger.value != _reason_ref(
            identity,
            ApplicabilityReasonKind.REPLACEMENT_TRIGGER_INAPPLICABLE,
        ):
            raise _stale("/replacement_trigger_binding")
        object.__setattr__(self, "request_identity", identity)
        object.__setattr__(self, "source_event", event)
        object.__setattr__(self, "support_decision_binding", support)
        object.__setattr__(self, "constructed_case_binding", constructed)
        object.__setattr__(self, "censoring_verdict_binding", censoring)
        object.__setattr__(self, "failure_reason_binding", failure_reason)
        object.__setattr__(self, "failure_occurrence_binding", failure_occurrence)

    def __repr__(self) -> str:
        return "AttemptAccountingRequest(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("attempt accounting requests cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("attempt accounting requests cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class SuccessorAuthorization:
    """External authorization for one exact successor invocation."""

    challenge_key: ChallengeKey
    predecessor_request_ref: GeneratorRequestRef
    predecessor_source_event_ref: object
    predecessor_attempt_ref: object
    predecessor_attempt_ordinal: int
    sampling_plan_ref: SamplingPlanRef
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    intended_slot_ref: object
    intended_evidence_unit_ref: object
    registered_policy_ref: object
    replacement_trigger: ReplacementTrigger
    policy_decision_kind: ReplacementDecisionKind
    replacement_accounting_evidence_ref: object
    successor_attempt_ref: object
    successor_attempt_ordinal: int
    replacement_lineage_ref: object

    def __post_init__(self) -> None:
        if type(self) is not SuccessorAuthorization:
            raise _wrong("/authorization")
        key = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", key)
        _generator_ref(
            self.predecessor_request_ref,
            GeneratorRequestRef,
            challenge_key=key,
            path="/predecessor_request_ref",
        )
        for name, kind in (
            ("predecessor_source_event_ref", "generation_event"),
            ("predecessor_attempt_ref", "protected_attempt_commitment"),
            ("intended_slot_ref", "protected_intended_slot"),
            (
                "intended_evidence_unit_ref",
                "protected_intended_evidence_unit",
            ),
            ("registered_policy_ref", "replacement_policy"),
            (
                "replacement_accounting_evidence_ref",
                "replacement_accounting",
            ),
            ("successor_attempt_ref", "protected_attempt_commitment"),
            ("replacement_lineage_ref", "protected_replacement_lineage"),
        ):
            object.__setattr__(
                self,
                name,
                _owner(
                    getattr(self, name),
                    kind,
                    challenge_key=key,
                    path=f"/{name}",
                ),
            )
        predecessor_ordinal = _uint64(
            self.predecessor_attempt_ordinal,
            "/predecessor_attempt_ordinal",
        )
        successor_ordinal = _uint64(
            self.successor_attempt_ordinal,
            "/successor_attempt_ordinal",
        )
        if successor_ordinal <= predecessor_ordinal:
            raise _invalid("/successor_attempt_ordinal")
        if self.successor_attempt_ref == self.predecessor_attempt_ref:
            raise _invalid("/successor_attempt_ref")
        object.__setattr__(
            self,
            "predecessor_attempt_ordinal",
            predecessor_ordinal,
        )
        object.__setattr__(self, "successor_attempt_ordinal", successor_ordinal)
        for name, expected in (
            ("sampling_plan_ref", SamplingPlanRef),
            ("primary_population_ref", InstanceDistributionContractRef),
            ("selection_population_ref", InstanceDistributionContractRef),
        ):
            _top_ref(
                getattr(self, name),
                expected,
                challenge_key=key,
                path=f"/{name}",
            )
        _exact(self.replacement_trigger, ReplacementTrigger, "/replacement_trigger")
        if type(self.policy_decision_kind) is not ReplacementDecisionKind or (
            self.policy_decision_kind
            not in {
                ReplacementDecisionKind.PERMITTED,
                ReplacementDecisionKind.REQUIRED_BY_POLICY,
            }
        ):
            raise _invalid("/policy_decision_kind")

    def __repr__(self) -> str:
        return "SuccessorAuthorization(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("successor authorizations cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("successor authorizations cannot be pickled")


def _expected_denominator_ref(request: AttemptAccountingRequest) -> object | None:
    policy = request.replacement_policy
    trigger = request.replacement_trigger_binding
    if policy.kind is ReplacementPolicyKind.ON_REGISTERED_TRIGGERS and trigger.is_bound:
        return policy.payload.denominator_effect_ref
    return None


def _validate_successor_authorization(
    request: AttemptAccountingRequest,
    authorization: SuccessorAuthorization,
) -> None:
    identity = request.request_identity
    expected = (
        (authorization.challenge_key, request.challenge_key),
        (authorization.predecessor_request_ref, request.request_ref),
        (authorization.predecessor_source_event_ref, request.source_event_ref),
        (authorization.predecessor_attempt_ref, identity.attempt_ref),
        (authorization.predecessor_attempt_ordinal, identity.attempt_ordinal),
        (authorization.sampling_plan_ref, identity.sampling_plan_ref),
        (authorization.primary_population_ref, identity.primary_population_ref),
        (
            authorization.selection_population_ref,
            identity.selection_population_ref,
        ),
        (authorization.intended_slot_ref, identity.intended_slot_ref),
        (
            authorization.intended_evidence_unit_ref,
            identity.intended_evidence_unit_ref,
        ),
        (
            authorization.replacement_trigger,
            request.replacement_trigger_binding.value,
        ),
    )
    if any(actual != wanted for actual, wanted in expected):
        raise _stale("/successor_authorization_binding")
    policy = request.replacement_policy
    if (
        policy.kind is not ReplacementPolicyKind.ON_REGISTERED_TRIGGERS
        or authorization.registered_policy_ref != policy.payload.policy_ref
    ):
        raise _stale("/successor_authorization_binding/registered_policy_ref")


@dataclass(frozen=True, slots=True, repr=False)
class AttemptAccountingDirective:
    """Closed FINAL/PENDING_SUCCESSOR/OWNER_UNAVAILABLE authority result."""

    challenge_key: ChallengeKey
    request: AttemptAccountingRequest
    directive_kind: AttemptAccountingDirectiveKind
    provisional_outcome: GeneratorOutcomeKind
    provisional_stage: GeneratorTerminalStage
    final_outcome: GeneratorOutcomeKind | None
    final_stage: GeneratorTerminalStage | None
    outcome_replacement_binding: ApplicabilityBinding[ReplacementDecision]
    successor_authorization_binding: ApplicabilityBinding[SuccessorAuthorization]
    denominator_effect_binding: ApplicabilityBinding[object]
    accounting_authority_failure_ref: object | None

    def __post_init__(self) -> None:
        if type(self) is not AttemptAccountingDirective:
            raise _wrong("/directive")
        key = _challenge(self.challenge_key)
        request = replace(_exact(self.request, AttemptAccountingRequest, "/request"))
        if request.challenge_key != key:
            raise _cross_challenge("/request")
        if type(self.directive_kind) is not AttemptAccountingDirectiveKind:
            raise _wrong("/directive_kind")
        provisional = _outcome_stage(
            self.provisional_outcome,
            self.provisional_stage,
            path="/provisional_terminal",
        )
        if provisional != (
            request.provisional_outcome,
            request.provisional_stage,
        ):
            raise _stale("/provisional_terminal")
        replacement = _binding_authoring(
            self.outcome_replacement_binding,
            ReplacementDecision,
            challenge_key=key,
            path="/outcome_replacement_binding",
        )
        successor = _applicability(
            self.successor_authorization_binding,
            "/successor_authorization_binding",
        )
        if successor.is_bound:
            _exact(
                successor.value,
                SuccessorAuthorization,
                "/successor_authorization_binding",
            )
        else:
            _owner(
                successor.value,
                "applicability_reason",
                challenge_key=key,
                path="/successor_authorization_binding",
            )
        denominator = _binding_owner(
            self.denominator_effect_binding,
            "denominator_effect",
            challenge_key=key,
            path="/denominator_effect_binding",
        )

        expected_denominator = _expected_denominator_ref(request)
        if self.directive_kind is AttemptAccountingDirectiveKind.FINAL:
            final = _outcome_stage(
                self.final_outcome,
                self.final_stage,
                path="/final_terminal",
            )
            if final != provisional:
                raise _stale("/final_terminal")
            if self.accounting_authority_failure_ref is not None:
                raise _invalid("/accounting_authority_failure_ref")
            _require_not_applicable(
                successor,
                request.successor_authorization_inapplicable_reason_ref,
                "/successor_authorization_binding",
            )
            b02a_mapped = request.provisional_outcome in {
                GeneratorOutcomeKind.VALID_GENERATED,
                GeneratorOutcomeKind.REGISTERED_EXCLUSION,
                GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
                GeneratorOutcomeKind.CENSORED_CASE,
            }
            if replacement.is_bound != b02a_mapped:
                raise _invalid("/outcome_replacement_binding")
            if replacement.is_bound:
                decision = replacement.value
                if decision.decision is ReplacementDecisionKind.REQUIRED_BY_POLICY:
                    raise _invalid("/outcome_replacement_binding")
                if (
                    request.provisional_outcome is GeneratorOutcomeKind.VALID_GENERATED
                    and decision.decision is not ReplacementDecisionKind.PROHIBITED
                ):
                    raise _invalid("/outcome_replacement_binding")
                try:
                    validate_replacement_decision(
                        decision,
                        plan_ref=request.request_identity.sampling_plan_ref,
                        policy=request.replacement_policy,
                        executed=False,
                    )
                except (AuthoringError, TypeError, ValueError):
                    replacement_invalid = True
                else:
                    replacement_invalid = False
                if replacement_invalid:
                    raise _invalid("/outcome_replacement_binding")
                request_trigger = request.replacement_trigger_binding
                if request_trigger.is_bound:
                    if (
                        not decision.trigger_binding.is_bound
                        or decision.trigger_binding.value != request_trigger.value
                        or decision.decision is not ReplacementDecisionKind.PERMITTED
                    ):
                        raise _stale("/outcome_replacement_binding")
                elif (
                    decision.trigger_binding.is_bound
                    or decision.trigger_binding.value
                    != _reason_ref(
                        request.request_identity,
                        ApplicabilityReasonKind.REPLACEMENT_TRIGGER_INAPPLICABLE,
                    )
                ):
                    raise _stale("/outcome_replacement_binding")
                if (
                    decision.lineage_binding.is_bound
                    or decision.lineage_binding.value
                    != _reason_ref(
                        request.request_identity,
                        ApplicabilityReasonKind.REPLACEMENT_LINEAGE_NOT_EXECUTED,
                    )
                ):
                    raise _stale("/outcome_replacement_binding")
            else:
                _require_not_applicable(
                    replacement,
                    request.outcome_replacement_inapplicable_reason_ref,
                    "/outcome_replacement_binding",
                )
            if expected_denominator is None:
                _require_not_applicable(
                    denominator,
                    request.denominator_effect_inapplicable_reason_ref,
                    "/denominator_effect_binding",
                )
            elif not denominator.is_bound or denominator.value != expected_denominator:
                raise _stale("/denominator_effect_binding")
        elif self.directive_kind is AttemptAccountingDirectiveKind.PENDING_SUCCESSOR:
            if self.final_outcome is not None or self.final_stage is not None:
                raise _invalid("/final_terminal")
            if self.accounting_authority_failure_ref is not None:
                raise _invalid("/accounting_authority_failure_ref")
            _require_not_applicable(
                replacement,
                request.outcome_replacement_inapplicable_reason_ref,
                "/outcome_replacement_binding",
            )
            if not successor.is_bound:
                raise _incomplete("/successor_authorization_binding")
            if (
                request.provisional_outcome
                not in {
                    GeneratorOutcomeKind.REGISTERED_EXCLUSION,
                    GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
                    GeneratorOutcomeKind.CENSORED_CASE,
                }
                or not request.replacement_trigger_binding.is_bound
            ):
                raise _invalid("/directive_kind")
            _validate_successor_authorization(request, successor.value)
            if expected_denominator is None:
                raise _invalid("/denominator_effect_binding")
            if not denominator.is_bound or denominator.value != expected_denominator:
                raise _stale("/denominator_effect_binding")
        else:
            final = _outcome_stage(
                self.final_outcome,
                self.final_stage,
                path="/final_terminal",
            )
            if final != (
                GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
                GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
            ):
                raise _invalid("/final_terminal")
            _require_not_applicable(
                replacement,
                request.outcome_replacement_inapplicable_reason_ref,
                "/outcome_replacement_binding",
            )
            _require_not_applicable(
                successor,
                request.successor_authorization_inapplicable_reason_ref,
                "/successor_authorization_binding",
            )
            _require_not_applicable(
                denominator,
                request.denominator_owner_unavailable_reason_ref,
                "/denominator_effect_binding",
            )
            failure = _owner(
                self.accounting_authority_failure_ref,
                "infrastructure_failure",
                challenge_key=key,
                path="/accounting_authority_failure_ref",
            )
            if failure != request.accounting_authority_failure_ref:
                raise _stale("/accounting_authority_failure_ref")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "request", request)

    def __repr__(self) -> str:
        return "AttemptAccountingDirective(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("attempt accounting directives cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("attempt accounting directives cannot be pickled")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> AttemptAccountingDirectiveRef:
        from .canonical import _record_ref

        return _record_ref(  # type: ignore[return-value]
            self,
            AttemptAccountingDirectiveRef,
        )


def _require_pair_type(
    pair: RecordRefPair,
    record_type: type,
    ref_type: type,
    path: str,
) -> None:
    if type(pair.record) is not record_type or type(pair.ref) is not ref_type:
        raise _wrong(path)


def _conformance_pair(
    value: object,
    *,
    challenge_key: ChallengeKey,
    request_identity: GeneratorRequestIdentity,
    request_ref: GeneratorRequestRef,
    source_event: GenerationSourceEvent,
    source_event_ref: object,
    generator_ref: object,
    environment_ref: GeneratorEnvironmentRef,
    fixture_configuration_ref: BurgersFixtureConfigurationRef,
    primary_population_ref: InstanceDistributionContractRef,
    selection_population_ref: InstanceDistributionContractRef,
    sampling_plan_ref: SamplingPlanRef,
    role_binding: GenerationRoleBinding,
    outcome_kind: GeneratorOutcomeKind,
    terminal_stage: GeneratorTerminalStage,
    path: str,
) -> RecordRefPair:
    """Revalidate and bind one complete conformance record to its attempt."""

    from .conformance import GeneratorConformanceFacts
    from .refs import GeneratorConformanceFactsRef

    pair = _pair(value, path)
    _require_pair_type(
        pair, GeneratorConformanceFacts, GeneratorConformanceFactsRef, path
    )
    validation_failure: tuple[str, str] | None = None
    try:
        facts = replace(pair.record)
        checked = RecordRefPair(facts, pair.ref)
    except GeneratorValidationError as error:
        validation_failure = (error.code, error.path)
    except (TypeError, ValueError):
        validation_failure = (GeneratorInputCode.INVALID_VALUE.value, path)
    if validation_failure is not None:
        raise GeneratorValidationError(
            validation_failure[0],
            path=validation_failure[1],
        )
    expected = (
        (facts.challenge_key, challenge_key),
        (facts.request_identity, request_identity),
        (facts.request_ref, request_ref),
        (facts.source_event, source_event),
        (facts.source_event_ref, source_event_ref),
        (facts.generator_ref, generator_ref),
        (facts.environment_ref, environment_ref),
        (facts.fixture_configuration_ref, fixture_configuration_ref),
        (facts.primary_population_ref, primary_population_ref),
        (facts.selection_population_ref, selection_population_ref),
        (facts.sampling_plan_ref, sampling_plan_ref),
        (facts.role_binding, role_binding),
        (facts.outcome_kind, outcome_kind),
        (facts.terminal_stage, terminal_stage),
    )
    if any(actual != wanted for actual, wanted in expected):
        raise _stale(path)
    return checked


@dataclass(frozen=True, slots=True, repr=False)
class PendingGenerationAttemptRecord:
    """Canonical nonterminal record for one terminated predecessor invocation."""

    challenge_key: ChallengeKey
    request_ref: GeneratorRequestRef
    source_event_pair: RecordRefPair
    provisional_outcome: GeneratorOutcomeKind
    provisional_stage: GeneratorTerminalStage
    support_decision_binding: RecordRefBinding
    constructed_case_binding: RecordRefBinding
    censoring_verdict_binding: RecordRefBinding
    failure_reason_binding: RecordRefBinding
    failure_occurrence_binding: RecordRefBinding
    conformance_facts_pair: RecordRefPair
    accounting_directive_pair: RecordRefPair

    def __post_init__(self) -> None:
        if type(self) is not PendingGenerationAttemptRecord:
            raise _wrong("/pending")
        key = _challenge(self.challenge_key)
        request_ref = _generator_ref(
            self.request_ref,
            GeneratorRequestRef,
            challenge_key=key,
            path="/request_ref",
        )
        source = _revalidated_pair(self.source_event_pair, "/source_event_pair")
        _require_pair_type(
            source,
            GenerationSourceEvent,
            type(source.ref),
            "/source_event_pair",
        )
        _owner(
            source.ref,
            "generation_event",
            challenge_key=key,
            path="/source_event_pair/ref",
        )
        if (
            source.record.challenge_key != key
            or source.record.request_ref != request_ref
        ):
            raise _stale("/source_event_pair")
        outcome, stage = _outcome_stage(
            self.provisional_outcome,
            self.provisional_stage,
            path="/provisional_terminal",
        )
        if outcome not in {
            GeneratorOutcomeKind.REGISTERED_EXCLUSION,
            GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
            GeneratorOutcomeKind.CENSORED_CASE,
        }:
            raise _invalid("/provisional_outcome")
        binding_names = (
            "support_decision_binding",
            "constructed_case_binding",
            "censoring_verdict_binding",
            "failure_reason_binding",
            "failure_occurrence_binding",
        )
        for index, name in enumerate(binding_names):
            checked = _revalidated_record_binding(
                getattr(self, name),
                f"/bindings/{index}",
            )
            _binding_reason(
                checked,
                challenge_key=key,
                path=f"/bindings/{index}",
            )
            object.__setattr__(self, name, checked)
        if self.constructed_case_binding.is_bound != (
            outcome is GeneratorOutcomeKind.CENSORED_CASE
        ):
            raise _invalid("/constructed_case_binding")
        if (
            self.constructed_case_binding.is_bound
            and _pair_record_name(self.constructed_case_binding.pair)
            != "CanonicalChallengeCase"
        ):
            raise _wrong("/constructed_case_binding")
        failure_required = outcome is GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE
        if (
            self.failure_reason_binding.is_bound != failure_required
            or self.failure_occurrence_binding.is_bound != failure_required
        ):
            raise _invalid("/failure_reason_binding")
        directive = _revalidated_pair(
            self.accounting_directive_pair,
            "/accounting_directive_pair",
        )
        _require_pair_type(
            directive,
            AttemptAccountingDirective,
            AttemptAccountingDirectiveRef,
            "/accounting_directive_pair",
        )
        if (
            directive.record.directive_kind
            is not AttemptAccountingDirectiveKind.PENDING_SUCCESSOR
            or directive.record.request.request_ref != request_ref
            or directive.record.provisional_outcome is not outcome
            or directive.record.provisional_stage is not stage
        ):
            raise _stale("/accounting_directive_pair")
        request = directive.record.request
        identity = request.request_identity
        conformance = _conformance_pair(
            self.conformance_facts_pair,
            challenge_key=key,
            request_identity=identity,
            request_ref=request_ref,
            source_event=source.record,
            source_event_ref=source.ref,
            generator_ref=identity.generator_ref,
            environment_ref=identity.environment_ref,
            fixture_configuration_ref=identity.fixture_configuration_ref,
            primary_population_ref=identity.primary_population_ref,
            selection_population_ref=identity.selection_population_ref,
            sampling_plan_ref=identity.sampling_plan_ref,
            role_binding=identity.role_binding,
            outcome_kind=outcome,
            terminal_stage=stage,
            path="/conformance_facts_pair",
        )
        if (
            source != RecordRefPair(request.source_event, request.source_event_ref)
            or self.support_decision_binding != request.support_decision_binding
            or self.constructed_case_binding != request.constructed_case_binding
            or self.censoring_verdict_binding != request.censoring_verdict_binding
            or self.failure_reason_binding != request.failure_reason_binding
            or self.failure_occurrence_binding != request.failure_occurrence_binding
        ):
            raise _stale("/accounting_directive_pair")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "request_ref", request_ref)
        object.__setattr__(self, "source_event_pair", source)
        object.__setattr__(self, "provisional_outcome", outcome)
        object.__setattr__(self, "provisional_stage", stage)
        object.__setattr__(self, "conformance_facts_pair", conformance)
        object.__setattr__(self, "accounting_directive_pair", directive)

    def __repr__(self) -> str:
        return "PendingGenerationAttemptRecord(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("pending generation attempt records cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("pending generation attempt records cannot be pickled")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> PendingGenerationAttemptRef:
        from .canonical import _record_ref

        return _record_ref(  # type: ignore[return-value]
            self,
            PendingGenerationAttemptRef,
        )


@final
@dataclass(frozen=True, slots=True, repr=False)
class PendingGenerationAttempt:
    """Nonserializable wrapper retaining an optional validated artifact."""

    record: PendingGenerationAttemptRecord
    ref: PendingGenerationAttemptRef
    artifact: object | None

    def __post_init__(self) -> None:
        from .burgers import (
            GeneratedFixtureArtifact,
            build_generated_fixture_artifact,
            build_validated_case_facts,
        )

        if type(self) is not PendingGenerationAttempt:
            raise _wrong("/pending")
        record = replace(
            _exact(
                self.record,
                PendingGenerationAttemptRecord,
                "/record",
            )
        )
        ref = _generator_ref(
            self.ref,
            PendingGenerationAttemptRef,
            challenge_key=record.challenge_key,
            path="/ref",
        )
        if record.to_ref() != ref:
            raise _stale("/ref")
        constructed = record.constructed_case_binding
        if constructed.is_bound:
            artifact = _exact(
                self.artifact,
                GeneratedFixtureArtifact,
                "/artifact",
            )
            checked_artifact = build_generated_fixture_artifact(
                case=artifact.case,
                case_ref=artifact.case_ref,
                loaded_case=artifact.loaded_case,
                loaded_dependencies=artifact.loaded_dependencies,
                graph_origin=artifact.graph_origin,
            )
            if (
                checked_artifact.case != constructed.pair.record
                or checked_artifact.case_ref != constructed.pair.ref
            ):
                raise _stale("/artifact")
            validated_binding = (
                record.conformance_facts_pair.record.validated_case_facts_binding
            )
            expected_facts = build_validated_case_facts(checked_artifact)
            if (
                not validated_binding.is_bound
                or validated_binding.value != expected_facts
            ):
                raise _stale("/artifact")
        else:
            if self.artifact is not None:
                raise _invalid("/artifact")
            checked_artifact = None
        object.__setattr__(self, "record", record)
        object.__setattr__(self, "ref", ref)
        object.__setattr__(self, "artifact", checked_artifact)

    def __repr__(self) -> str:
        return "PendingGenerationAttempt(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("pending generation attempts cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("pending generation attempts cannot be pickled")


def build_pending_generation_attempt(
    *,
    request: AttemptAccountingRequest,
    directive: AttemptAccountingDirective,
    directive_ref: AttemptAccountingDirectiveRef,
    conformance_facts: object,
    conformance_facts_ref: object,
    artifact: object | None,
) -> PendingGenerationAttempt:
    """Build the sole nonterminal wrapper from one exact pending directive."""

    checked_request = _exact(request, AttemptAccountingRequest, "/request")
    checked_directive = _exact(
        directive,
        AttemptAccountingDirective,
        "/directive",
    )
    directive_pair = RecordRefPair(checked_directive, directive_ref)
    if (
        checked_directive.request != checked_request
        or checked_directive.directive_kind
        is not AttemptAccountingDirectiveKind.PENDING_SUCCESSOR
    ):
        raise _stale("/directive")
    conformance_pair = RecordRefPair(conformance_facts, conformance_facts_ref)
    record = PendingGenerationAttemptRecord(
        challenge_key=checked_request.challenge_key,
        request_ref=checked_request.request_ref,
        source_event_pair=RecordRefPair(
            checked_request.source_event,
            checked_request.source_event_ref,
        ),
        provisional_outcome=checked_request.provisional_outcome,
        provisional_stage=checked_request.provisional_stage,
        support_decision_binding=checked_request.support_decision_binding,
        constructed_case_binding=checked_request.constructed_case_binding,
        censoring_verdict_binding=checked_request.censoring_verdict_binding,
        failure_reason_binding=checked_request.failure_reason_binding,
        failure_occurrence_binding=checked_request.failure_occurrence_binding,
        conformance_facts_pair=conformance_pair,
        accounting_directive_pair=directive_pair,
    )
    return PendingGenerationAttempt(record, record.to_ref(), artifact)


@dataclass(frozen=True, slots=True, repr=False)
class SuccessorExecutionEvidence:
    """Exact proof that one authorized successor invocation actually exists."""

    authorization: SuccessorAuthorization
    successor_request_pair: RecordRefPair
    successor_output_pair: RecordRefPair

    def __post_init__(self) -> None:
        if type(self) is not SuccessorExecutionEvidence:
            raise _wrong("/successor_execution_binding")
        authorization = _exact(
            self.authorization,
            SuccessorAuthorization,
            "/authorization",
        )
        request_pair = _pair(
            self.successor_request_pair,
            "/successor_request_pair",
        )
        _require_pair_type(
            request_pair,
            GeneratorRequestIdentity,
            GeneratorRequestRef,
            "/successor_request_pair",
        )
        identity = replace(request_pair.record)
        request_pair = RecordRefPair(identity, request_pair.ref)
        if (
            identity.challenge_key != authorization.challenge_key
            or identity.attempt_ref != authorization.successor_attempt_ref
            or identity.attempt_ordinal != authorization.successor_attempt_ordinal
            or identity.sampling_plan_ref != authorization.sampling_plan_ref
            or identity.primary_population_ref != authorization.primary_population_ref
            or identity.selection_population_ref
            != authorization.selection_population_ref
            or identity.intended_slot_ref != authorization.intended_slot_ref
            or identity.intended_evidence_unit_ref
            != authorization.intended_evidence_unit_ref
            or identity.current_attempt_predecessor_ref is None
            or identity.current_attempt_lineage_ref
            != authorization.replacement_lineage_ref
        ):
            raise _stale("/successor_request_pair")
        output_pair = _pair(
            self.successor_output_pair,
            "/successor_output_pair",
        )
        valid_output = (
            type(output_pair.record) is PendingGenerationAttemptRecord
            and type(output_pair.ref) is PendingGenerationAttemptRef
        ) or (
            type(output_pair.record) is GeneratorResultRecord
            and type(output_pair.ref) is GeneratorResultRef
        )
        if not valid_output:
            raise _stale("/successor_output_pair")
        output_record = replace(output_pair.record)
        if (
            output_record.to_ref() != output_pair.ref
            or output_record.request_ref != request_pair.ref
        ):
            raise _stale("/successor_output_pair")
        output_pair = RecordRefPair(output_record, output_pair.ref)
        object.__setattr__(self, "authorization", authorization)
        object.__setattr__(self, "successor_request_pair", request_pair)
        object.__setattr__(self, "successor_output_pair", output_pair)

    def __repr__(self) -> str:
        return "SuccessorExecutionEvidence(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("successor execution evidence cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("successor execution evidence cannot be pickled")


@dataclass(frozen=True, slots=True, repr=False)
class AttemptAccountingDecision:
    """Final exact accounting decision for one terminated invocation."""

    challenge_key: ChallengeKey
    request_ref: GeneratorRequestRef
    source_event_ref: object
    attempt_ref: object
    intended_slot_ref: object
    intended_evidence_unit_ref: object
    provisional_outcome: GeneratorOutcomeKind
    provisional_stage: GeneratorTerminalStage
    final_outcome: GeneratorOutcomeKind
    final_stage: GeneratorTerminalStage
    accounting_directive_pair: RecordRefPair
    outcome_replacement_binding: ApplicabilityBinding[ReplacementDecision]
    denominator_effect_binding: ApplicabilityBinding[object]
    successor_execution_binding: ApplicabilityBinding[SuccessorExecutionEvidence]

    def __post_init__(self) -> None:
        if type(self) is not AttemptAccountingDecision:
            raise _wrong("/accounting_decision")
        key = _challenge(self.challenge_key)
        request_ref = _generator_ref(
            self.request_ref,
            GeneratorRequestRef,
            challenge_key=key,
            path="/request_ref",
        )
        source_ref = _owner(
            self.source_event_ref,
            "generation_event",
            challenge_key=key,
            path="/source_event_ref",
        )
        attempt_ref = _owner(
            self.attempt_ref,
            "protected_attempt_commitment",
            challenge_key=key,
            path="/attempt_ref",
        )
        slot_ref = _owner(
            self.intended_slot_ref,
            "protected_intended_slot",
            challenge_key=key,
            path="/intended_slot_ref",
        )
        unit_ref = _owner(
            self.intended_evidence_unit_ref,
            "protected_intended_evidence_unit",
            challenge_key=key,
            path="/intended_evidence_unit_ref",
        )
        provisional = _outcome_stage(
            self.provisional_outcome,
            self.provisional_stage,
            path="/provisional_terminal",
        )
        final = _outcome_stage(
            self.final_outcome,
            self.final_stage,
            path="/final_terminal",
        )
        directive_pair = _pair(
            self.accounting_directive_pair,
            "/accounting_directive_pair",
        )
        _require_pair_type(
            directive_pair,
            AttemptAccountingDirective,
            AttemptAccountingDirectiveRef,
            "/accounting_directive_pair",
        )
        directive = directive_pair.record
        request = directive.request
        identity = request.request_identity
        if (
            request.challenge_key != key
            or request.request_ref != request_ref
            or request.source_event_ref != source_ref
            or identity.attempt_ref != attempt_ref
            or identity.intended_slot_ref != slot_ref
            or identity.intended_evidence_unit_ref != unit_ref
            or provisional != (request.provisional_outcome, request.provisional_stage)
        ):
            raise _stale("/accounting_directive_pair")
        replacement = _binding_authoring(
            self.outcome_replacement_binding,
            ReplacementDecision,
            challenge_key=key,
            path="/outcome_replacement_binding",
        )
        denominator = _binding_owner(
            self.denominator_effect_binding,
            "denominator_effect",
            challenge_key=key,
            path="/denominator_effect_binding",
        )
        successor = _applicability(
            self.successor_execution_binding,
            "/successor_execution_binding",
        )
        if successor.is_bound:
            _exact(
                successor.value,
                SuccessorExecutionEvidence,
                "/successor_execution_binding",
            )
        else:
            _owner(
                successor.value,
                "applicability_reason",
                challenge_key=key,
                path="/successor_execution_binding",
            )
        if directive.directive_kind is AttemptAccountingDirectiveKind.FINAL:
            if final != provisional:
                raise _stale("/final_terminal")
            if (
                replacement != directive.outcome_replacement_binding
                or denominator != directive.denominator_effect_binding
            ):
                raise _stale("/outcome_replacement_binding")
            _require_not_applicable(
                successor,
                request.successor_execution_inapplicable_reason_ref,
                "/successor_execution_binding",
            )
        elif (
            directive.directive_kind is AttemptAccountingDirectiveKind.OWNER_UNAVAILABLE
        ):
            if final != (
                GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
                GeneratorTerminalStage.ATTEMPT_ACCOUNTING_AUTHORITY,
            ):
                raise _invalid("/final_terminal")
            if (
                replacement != directive.outcome_replacement_binding
                or denominator != directive.denominator_effect_binding
            ):
                raise _stale("/outcome_replacement_binding")
            _require_not_applicable(
                successor,
                request.successor_execution_inapplicable_reason_ref,
                "/successor_execution_binding",
            )
        else:
            if final != provisional or not successor.is_bound:
                raise _invalid("/successor_execution_binding")
            authorization = directive.successor_authorization_binding.value
            evidence = successor.value
            successor_identity = evidence.successor_request_pair.record
            if evidence.authorization != authorization:
                raise _stale("/successor_execution_binding")
            continuity = (
                "challenge_key",
                "sampling_plan_ref",
                "primary_population_ref",
                "selection_population_ref",
                "intended_slot_ref",
                "intended_evidence_unit_ref",
                "generator_ref",
                "environment_ref",
                "fixture_configuration_ref",
                "role_binding",
            )
            if any(
                getattr(successor_identity, name) != getattr(identity, name)
                for name in continuity
            ):
                raise _stale("/successor_execution_binding")
            if not replacement.is_bound:
                raise _incomplete("/outcome_replacement_binding")
            decision = replacement.value
            if (
                decision.decision is not authorization.policy_decision_kind
                or decision.trigger_binding.value != authorization.replacement_trigger
                or decision.lineage_binding.value
                != authorization.replacement_lineage_ref
                or decision.accounting_evidence_ref
                != authorization.replacement_accounting_evidence_ref
            ):
                raise _stale("/outcome_replacement_binding")
            try:
                validate_replacement_decision(
                    decision,
                    plan_ref=identity.sampling_plan_ref,
                    policy=request.replacement_policy,
                    executed=True,
                )
            except (AuthoringError, TypeError, ValueError):
                replacement_invalid = True
            else:
                replacement_invalid = False
            if replacement_invalid:
                raise _invalid("/outcome_replacement_binding")
            if denominator != directive.denominator_effect_binding:
                raise _stale("/denominator_effect_binding")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "request_ref", request_ref)
        object.__setattr__(self, "source_event_ref", source_ref)
        object.__setattr__(self, "attempt_ref", attempt_ref)
        object.__setattr__(self, "intended_slot_ref", slot_ref)
        object.__setattr__(self, "intended_evidence_unit_ref", unit_ref)
        object.__setattr__(self, "provisional_outcome", provisional[0])
        object.__setattr__(self, "provisional_stage", provisional[1])
        object.__setattr__(self, "final_outcome", final[0])
        object.__setattr__(self, "final_stage", final[1])

    def __repr__(self) -> str:
        return "AttemptAccountingDecision(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("attempt accounting decisions cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("attempt accounting decisions cannot be pickled")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> AttemptAccountingDecisionRef:
        from .canonical import _record_ref

        return _record_ref(  # type: ignore[return-value]
            self,
            AttemptAccountingDecisionRef,
        )


def build_attempt_accounting_decision(
    *,
    request: AttemptAccountingRequest,
    directive: AttemptAccountingDirective,
    directive_ref: AttemptAccountingDirectiveRef,
) -> tuple[AttemptAccountingDecision, AttemptAccountingDecisionRef]:
    """Finalize a direct or owner-unavailable directive without execution."""

    checked_request = _exact(request, AttemptAccountingRequest, "/request")
    checked_directive = _exact(
        directive,
        AttemptAccountingDirective,
        "/directive",
    )
    if checked_directive.request != checked_request:
        raise _stale("/directive")
    if (
        checked_directive.directive_kind
        is AttemptAccountingDirectiveKind.PENDING_SUCCESSOR
    ):
        raise _incomplete("/directive")
    directive_pair = RecordRefPair(checked_directive, directive_ref)
    identity = checked_request.request_identity
    decision = AttemptAccountingDecision(
        challenge_key=checked_request.challenge_key,
        request_ref=checked_request.request_ref,
        source_event_ref=checked_request.source_event_ref,
        attempt_ref=identity.attempt_ref,
        intended_slot_ref=identity.intended_slot_ref,
        intended_evidence_unit_ref=identity.intended_evidence_unit_ref,
        provisional_outcome=checked_request.provisional_outcome,
        provisional_stage=checked_request.provisional_stage,
        final_outcome=checked_directive.final_outcome,
        final_stage=checked_directive.final_stage,
        accounting_directive_pair=directive_pair,
        outcome_replacement_binding=(checked_directive.outcome_replacement_binding),
        denominator_effect_binding=(checked_directive.denominator_effect_binding),
        successor_execution_binding=ApplicabilityBinding.not_applicable(
            checked_request.successor_execution_inapplicable_reason_ref
        ),
    )
    return decision, decision.to_ref()


@dataclass(frozen=True, slots=True, repr=False)
class GenerationAttemptRecord:
    """Final immutable record for exactly one admitted invocation."""

    challenge_key: ChallengeKey
    request_ref: GeneratorRequestRef
    source_event_ref: object
    generator_ref: object
    environment_ref: GeneratorEnvironmentRef
    fixture_configuration_ref: object
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    sampling_plan_ref: SamplingPlanRef
    role_binding: object
    replay_ref: GeneratorReplayCommitmentRef
    intended_slot_ref: object
    intended_evidence_unit_ref: object
    attempt_ref: object
    attempt_ordinal: int
    materialization_state: SourceMaterializationState
    outcome_kind: GeneratorOutcomeKind
    terminal_stage: GeneratorTerminalStage
    case_ref_binding: ApplicabilityBinding[CanonicalChallengeCaseRef]
    support_decision_binding: RecordRefBinding
    censoring_verdict_binding: RecordRefBinding
    censoring_decision_binding: RecordRefBinding
    conformance_facts_pair: RecordRefPair
    failure_reason_binding: RecordRefBinding
    failure_occurrence_binding: RecordRefBinding
    current_predecessor_binding: RecordRefBinding
    current_lineage_binding: ApplicabilityBinding[object]
    pending_attempt_binding: ApplicabilityBinding[PendingGenerationAttemptRef]
    accounting_decision_pair: RecordRefPair

    def __post_init__(self) -> None:
        from .model import GenerationRoleBinding
        from .refs import (
            BurgersFixtureConfigurationRef,
            GeneratorFailureOccurrenceRef,
            GeneratorFailureReasonRef,
        )

        if type(self) is not GenerationAttemptRecord:
            raise _wrong("/record")
        key = _challenge(self.challenge_key)
        request_ref = _generator_ref(
            self.request_ref,
            GeneratorRequestRef,
            challenge_key=key,
            path="/request_ref",
        )
        source_ref = _owner(
            self.source_event_ref,
            "generation_event",
            challenge_key=key,
            path="/source_event_ref",
        )
        generator_ref = _owner(
            self.generator_ref,
            "generator",
            challenge_key=key,
            path="/generator_ref",
        )
        environment_ref = _generator_ref(
            self.environment_ref,
            GeneratorEnvironmentRef,
            challenge_key=key,
            path="/environment_ref",
        )
        configuration_ref = _generator_ref(
            self.fixture_configuration_ref,
            BurgersFixtureConfigurationRef,
            challenge_key=key,
            path="/fixture_configuration_ref",
        )
        for name, expected in (
            ("primary_population_ref", InstanceDistributionContractRef),
            ("selection_population_ref", InstanceDistributionContractRef),
            ("sampling_plan_ref", SamplingPlanRef),
        ):
            _top_ref(
                getattr(self, name),
                expected,
                challenge_key=key,
                path=f"/{name}",
            )
        role = _exact(self.role_binding, GenerationRoleBinding, "/role_binding")
        if role.sampling_plan_ref != self.sampling_plan_ref:
            raise _stale("/role_binding")
        replay = _exact(self.replay_ref, GeneratorReplayCommitmentRef, "/replay_ref")
        if replay.challenge_key != key:
            raise _cross_challenge("/replay_ref")
        for name, kind in (
            ("intended_slot_ref", "protected_intended_slot"),
            (
                "intended_evidence_unit_ref",
                "protected_intended_evidence_unit",
            ),
            ("attempt_ref", "protected_attempt_commitment"),
        ):
            object.__setattr__(
                self,
                name,
                _owner(
                    getattr(self, name),
                    kind,
                    challenge_key=key,
                    path=f"/{name}",
                ),
            )
        ordinal = _uint64(self.attempt_ordinal, "/attempt_ordinal")
        materialization = _exact(
            self.materialization_state,
            SourceMaterializationState,
            "/materialization_state",
        )
        outcome, stage = _outcome_stage(
            self.outcome_kind,
            self.terminal_stage,
            path="/terminal",
        )
        case_binding = _applicability(self.case_ref_binding, "/case_ref_binding")
        if case_binding.is_bound:
            _top_ref(
                case_binding.value,
                CanonicalChallengeCaseRef,
                challenge_key=key,
                path="/case_ref_binding",
            )
        else:
            _owner(
                case_binding.value,
                "applicability_reason",
                challenge_key=key,
                path="/case_ref_binding",
            )
        case_required = outcome in {
            GeneratorOutcomeKind.VALID_GENERATED,
            GeneratorOutcomeKind.CENSORED_CASE,
        }
        if case_binding.is_bound != case_required:
            raise _invalid("/case_ref_binding")

        for name in (
            "support_decision_binding",
            "censoring_verdict_binding",
            "censoring_decision_binding",
            "failure_reason_binding",
            "failure_occurrence_binding",
            "current_predecessor_binding",
        ):
            binding = _record_binding(getattr(self, name), f"/{name}")
            _binding_reason(binding, challenge_key=key, path=f"/{name}")
        from .authorities import (
            CensoringDecision,
            CensoringVerdict,
            SupportExclusionDecision,
        )
        from .refs import CensoringDecisionRef

        if self.support_decision_binding.is_bound:
            _require_pair_type(
                self.support_decision_binding.pair,
                SupportExclusionDecision,
                SupportExclusionDecisionRef,
                "/support_decision_binding",
            )
        if self.censoring_verdict_binding.is_bound:
            _require_pair_type(
                self.censoring_verdict_binding.pair,
                CensoringVerdict,
                CensoringVerdictRef,
                "/censoring_verdict_binding",
            )
        if self.censoring_decision_binding.is_bound:
            _require_pair_type(
                self.censoring_decision_binding.pair,
                CensoringDecision,
                CensoringDecisionRef,
                "/censoring_decision_binding",
            )
        failure_required = outcome in {
            GeneratorOutcomeKind.GENERATOR_NONCONFORMANCE,
            GeneratorOutcomeKind.INVALID_CONSTRUCTION,
            GeneratorOutcomeKind.INFRASTRUCTURE_FAILURE,
        }
        if (
            self.failure_reason_binding.is_bound != failure_required
            or self.failure_occurrence_binding.is_bound != failure_required
        ):
            raise _invalid("/failure_reason_binding")
        if self.failure_reason_binding.is_bound and (
            type(self.failure_reason_binding.pair.ref) is not GeneratorFailureReasonRef
            or type(self.failure_occurrence_binding.pair.ref)
            is not GeneratorFailureOccurrenceRef
            or self.failure_reason_binding.pair.record.outcome_kind is not outcome
            or self.failure_reason_binding.pair.record.terminal_stage is not stage
            or self.failure_occurrence_binding.pair.record.outcome_kind is not outcome
            or self.failure_occurrence_binding.pair.record.terminal_stage is not stage
        ):
            raise _wrong("/failure_reason_binding")
        censoring_verdict_bound = self.censoring_verdict_binding.is_bound
        verdict_kind = (
            getattr(
                self.censoring_verdict_binding.pair.record,
                "verdict_kind",
                None,
            )
            if censoring_verdict_bound
            else None
        )
        censored_verdict = getattr(verdict_kind, "value", None) == "CENSORED"
        censoring_decision_required = censoring_verdict_bound and (
            not censored_verdict or outcome is GeneratorOutcomeKind.CENSORED_CASE
        )
        if self.censoring_decision_binding.is_bound != censoring_decision_required:
            raise _invalid("/censoring_decision_binding")
        predecessor = self.current_predecessor_binding
        lineage = _binding_owner(
            self.current_lineage_binding,
            "protected_replacement_lineage",
            challenge_key=key,
            path="/current_lineage_binding",
        )
        if predecessor.is_bound:
            _require_pair_type(
                predecessor.pair,
                PendingGenerationAttemptRecord,
                PendingGenerationAttemptRef,
                "/current_predecessor_binding",
            )
            if not lineage.is_bound:
                raise _incomplete("/current_lineage_binding")
        elif lineage.is_bound:
            raise _invalid("/current_lineage_binding")

        accounting = _pair(
            self.accounting_decision_pair,
            "/accounting_decision_pair",
        )
        _require_pair_type(
            accounting,
            AttemptAccountingDecision,
            AttemptAccountingDecisionRef,
            "/accounting_decision_pair",
        )
        decision = accounting.record
        identity = decision.accounting_directive_pair.record.request.request_identity
        accounting_request = decision.accounting_directive_pair.record.request
        conformance = _conformance_pair(
            self.conformance_facts_pair,
            challenge_key=key,
            request_identity=identity,
            request_ref=request_ref,
            source_event=accounting_request.source_event,
            source_event_ref=source_ref,
            generator_ref=generator_ref,
            environment_ref=environment_ref,
            fixture_configuration_ref=configuration_ref,
            primary_population_ref=self.primary_population_ref,
            selection_population_ref=self.selection_population_ref,
            sampling_plan_ref=self.sampling_plan_ref,
            role_binding=role,
            outcome_kind=outcome,
            terminal_stage=stage,
            path="/conformance_facts_pair",
        )
        if (
            decision.challenge_key != key
            or decision.request_ref != request_ref
            or decision.source_event_ref != source_ref
            or decision.attempt_ref != self.attempt_ref
            or decision.intended_slot_ref != self.intended_slot_ref
            or decision.intended_evidence_unit_ref != self.intended_evidence_unit_ref
            or decision.final_outcome is not outcome
            or decision.final_stage is not stage
        ):
            raise _stale("/accounting_decision_pair")
        if (
            self.support_decision_binding != accounting_request.support_decision_binding
            or self.censoring_verdict_binding
            != accounting_request.censoring_verdict_binding
        ):
            raise _stale("/accounting_decision_pair")
        if self.censoring_decision_binding.is_bound:
            censoring_decision = self.censoring_decision_binding.pair.record
            if (
                censoring_decision.verdict != self.censoring_verdict_binding.pair.record
                or censoring_decision.verdict_ref
                != self.censoring_verdict_binding.pair.ref
                or censoring_decision.accounting_decision != decision
                or censoring_decision.accounting_decision_ref != accounting.ref
            ):
                raise _stale("/censoring_decision_binding")
        if case_required and (
            not accounting_request.constructed_case_binding.is_bound
            or accounting_request.constructed_case_binding.pair.ref
            != case_binding.value
        ):
            raise _stale("/case_ref_binding")
        if (
            decision.accounting_directive_pair.record.directive_kind
            is not AttemptAccountingDirectiveKind.OWNER_UNAVAILABLE
            and (
                self.failure_reason_binding != accounting_request.failure_reason_binding
                or self.failure_occurrence_binding
                != accounting_request.failure_occurrence_binding
            )
        ):
            raise _stale("/failure_reason_binding")
        if identity.current_attempt_predecessor_ref is None:
            if (
                predecessor.is_bound
                or predecessor.reason_ref
                != _reason_ref(
                    identity,
                    ApplicabilityReasonKind.PENDING_ATTEMPT_INAPPLICABLE,
                )
                or lineage.is_bound
                or lineage.value
                != _reason_ref(
                    identity,
                    ApplicabilityReasonKind.REPLACEMENT_LINEAGE_NOT_EXECUTED,
                )
            ):
                raise _stale("/current_predecessor_binding")
        elif (
            not predecessor.is_bound
            or predecessor.pair.ref != identity.current_attempt_predecessor_ref
            or not lineage.is_bound
            or lineage.value != identity.current_attempt_lineage_ref
        ):
            raise _stale("/current_predecessor_binding")
        exact_unbound_reasons = (
            (
                case_binding,
                ApplicabilityReasonKind.RESULT_CASE_INAPPLICABLE,
                "/case_ref_binding",
            ),
            (
                self.support_decision_binding,
                ApplicabilityReasonKind.SUPPORT_DECISION_INAPPLICABLE,
                "/support_decision_binding",
            ),
            (
                self.censoring_verdict_binding,
                ApplicabilityReasonKind.CENSORING_VERDICT_INAPPLICABLE,
                "/censoring_verdict_binding",
            ),
            (
                self.censoring_decision_binding,
                ApplicabilityReasonKind.CENSORING_DECISION_INAPPLICABLE,
                "/censoring_decision_binding",
            ),
            (
                self.failure_reason_binding,
                ApplicabilityReasonKind.FAILURE_BINDING_INAPPLICABLE,
                "/failure_reason_binding",
            ),
            (
                self.failure_occurrence_binding,
                ApplicabilityReasonKind.FAILURE_BINDING_INAPPLICABLE,
                "/failure_occurrence_binding",
            ),
        )
        for binding, reason_kind, path in exact_unbound_reasons:
            if not binding.is_bound:
                observed_reason = (
                    binding.value
                    if type(binding) is ApplicabilityBinding
                    else binding.reason_ref
                )
                if observed_reason != _reason_ref(identity, reason_kind):
                    raise _stale(path)
        pending = _binding_generator_ref(
            self.pending_attempt_binding,
            PendingGenerationAttemptRef,
            challenge_key=key,
            path="/pending_attempt_binding",
        )
        if pending.is_bound:
            if not decision.successor_execution_binding.is_bound:
                raise _stale("/pending_attempt_binding")
        elif decision.successor_execution_binding.is_bound:
            raise _incomplete("/pending_attempt_binding")
        elif pending.value != _reason_ref(
            identity,
            ApplicabilityReasonKind.PENDING_ATTEMPT_INAPPLICABLE,
        ):
            raise _stale("/pending_attempt_binding")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "request_ref", request_ref)
        object.__setattr__(self, "source_event_ref", source_ref)
        object.__setattr__(self, "generator_ref", generator_ref)
        object.__setattr__(self, "environment_ref", environment_ref)
        object.__setattr__(self, "fixture_configuration_ref", configuration_ref)
        object.__setattr__(self, "attempt_ordinal", ordinal)
        object.__setattr__(self, "materialization_state", materialization)
        object.__setattr__(self, "outcome_kind", outcome)
        object.__setattr__(self, "terminal_stage", stage)
        object.__setattr__(self, "conformance_facts_pair", conformance)

    def __repr__(self) -> str:
        return "GenerationAttemptRecord(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("generation attempt records cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("generation attempt records cannot be pickled")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> GenerationAttemptRecordRef:
        from .canonical import _record_ref

        return _record_ref(  # type: ignore[return-value]
            self,
            GenerationAttemptRecordRef,
        )


def _attempt_record_from_parts(
    *,
    request: GeneratorRequest,
    request_identity: GeneratorRequestIdentity,
    source_event: GenerationSourceEvent,
    accounting_decision: AttemptAccountingDecision,
    accounting_decision_ref: AttemptAccountingDecisionRef,
    case_ref_binding: ApplicabilityBinding[CanonicalChallengeCaseRef],
    support_decision_binding: RecordRefBinding,
    censoring_verdict_binding: RecordRefBinding,
    censoring_decision_binding: RecordRefBinding,
    conformance_facts_pair: RecordRefPair,
    failure_reason_binding: RecordRefBinding,
    failure_occurrence_binding: RecordRefBinding,
    pending_attempt_binding: ApplicabilityBinding[PendingGenerationAttemptRef],
) -> GenerationAttemptRecord:
    if request_identity.current_attempt_predecessor_ref is None:
        current_predecessor_binding = RecordRefBinding.not_applicable(
            _reason_ref(
                request_identity,
                ApplicabilityReasonKind.PENDING_ATTEMPT_INAPPLICABLE,
            )
        )
        current_lineage_binding = ApplicabilityBinding.not_applicable(
            _reason_ref(
                request_identity,
                ApplicabilityReasonKind.REPLACEMENT_LINEAGE_NOT_EXECUTED,
            )
        )
    else:
        predecessor = request.current_attempt_predecessor_binding
        if (
            type(predecessor) is not RecordRefPair
            or predecessor.ref != request_identity.current_attempt_predecessor_ref
        ):
            raise _stale("/current_attempt_predecessor_binding")
        current_predecessor_binding = RecordRefBinding.bound(
            predecessor.record,
            predecessor.ref,
        )
        current_lineage_binding = ApplicabilityBinding.bound(
            request_identity.current_attempt_lineage_ref
        )
    return GenerationAttemptRecord(
        challenge_key=request_identity.challenge_key,
        request_ref=request_identity.to_ref(),
        source_event_ref=source_event.to_ref(),
        generator_ref=request_identity.generator_ref,
        environment_ref=request_identity.environment_ref,
        fixture_configuration_ref=request_identity.fixture_configuration_ref,
        primary_population_ref=request_identity.primary_population_ref,
        selection_population_ref=request_identity.selection_population_ref,
        sampling_plan_ref=request_identity.sampling_plan_ref,
        role_binding=request_identity.role_binding,
        replay_ref=request_identity.replay_ref,
        intended_slot_ref=request_identity.intended_slot_ref,
        intended_evidence_unit_ref=request_identity.intended_evidence_unit_ref,
        attempt_ref=request_identity.attempt_ref,
        attempt_ordinal=request_identity.attempt_ordinal,
        materialization_state=source_event.materialization_state,
        outcome_kind=accounting_decision.final_outcome,
        terminal_stage=accounting_decision.final_stage,
        case_ref_binding=case_ref_binding,
        support_decision_binding=support_decision_binding,
        censoring_verdict_binding=censoring_verdict_binding,
        censoring_decision_binding=censoring_decision_binding,
        conformance_facts_pair=conformance_facts_pair,
        failure_reason_binding=failure_reason_binding,
        failure_occurrence_binding=failure_occurrence_binding,
        current_predecessor_binding=current_predecessor_binding,
        current_lineage_binding=current_lineage_binding,
        pending_attempt_binding=pending_attempt_binding,
        accounting_decision_pair=RecordRefPair(
            accounting_decision,
            accounting_decision_ref,
        ),
    )


def build_generation_attempt_record(
    *,
    request: GeneratorRequest,
    source_event: GenerationSourceEvent,
    accounting_decision: AttemptAccountingDecision,
    accounting_decision_ref: AttemptAccountingDecisionRef,
    case_ref_binding: ApplicabilityBinding[CanonicalChallengeCaseRef],
    support_decision_binding: RecordRefBinding,
    censoring_verdict_binding: RecordRefBinding,
    censoring_decision_binding: RecordRefBinding,
    conformance_facts_pair: RecordRefPair,
    failure_reason_binding: RecordRefBinding,
    failure_occurrence_binding: RecordRefBinding,
    pending_attempt_binding: ApplicabilityBinding[PendingGenerationAttemptRef],
) -> tuple[GenerationAttemptRecord, GenerationAttemptRecordRef]:
    """Construct one exact final attempt row without executing or retrying."""

    checked_request = _exact(request, GeneratorRequest, "/request")
    identity = checked_request.identity()
    event = _exact(source_event, GenerationSourceEvent, "/source_event")
    decision = _exact(
        accounting_decision,
        AttemptAccountingDecision,
        "/accounting_decision",
    )
    if (
        event.request_ref != identity.to_ref()
        or decision.request_ref != identity.to_ref()
        or decision.source_event_ref != event.to_ref()
    ):
        raise _stale("/accounting_decision")
    record = _attempt_record_from_parts(
        request=checked_request,
        request_identity=identity,
        source_event=event,
        accounting_decision=decision,
        accounting_decision_ref=accounting_decision_ref,
        case_ref_binding=case_ref_binding,
        support_decision_binding=support_decision_binding,
        censoring_verdict_binding=censoring_verdict_binding,
        censoring_decision_binding=censoring_decision_binding,
        conformance_facts_pair=conformance_facts_pair,
        failure_reason_binding=failure_reason_binding,
        failure_occurrence_binding=failure_occurrence_binding,
        pending_attempt_binding=pending_attempt_binding,
    )
    return record, record.to_ref()


def finalize_pending_accounting(
    *,
    predecessor_request: GeneratorRequest,
    pending: PendingGenerationAttempt,
    successor_request: GeneratorRequest,
    successor_output: PendingGenerationAttempt | GeneratorResult,
) -> tuple[
    AttemptAccountingDecision,
    AttemptAccountingDecisionRef,
    object | None,
    object | None,
    GenerationAttemptRecord,
    GenerationAttemptRecordRef,
]:
    """Prove one successor execution and finalize predecessor accounting.

    This is a pure composition boundary.  It performs no provider call,
    derivation, retry, authority invocation, or service recursion.
    """

    predecessor = replace(
        _exact(
            predecessor_request,
            GeneratorRequest,
            "/predecessor_request",
        )
    )
    checked_pending = replace(_exact(pending, PendingGenerationAttempt, "/pending"))
    successor = replace(
        _exact(
            successor_request,
            GeneratorRequest,
            "/successor_request",
        )
    )
    if type(successor_output) not in {PendingGenerationAttempt, GeneratorResult}:
        raise _wrong("/successor_output")
    checked_output = replace(successor_output)
    pending_pair = RecordRefPair(checked_pending.record, checked_pending.ref)
    predecessor_identity = predecessor.identity()
    successor_identity = successor.identity()
    directive_pair = checked_pending.record.accounting_directive_pair
    directive = directive_pair.record
    accounting_request = directive.request
    if (
        accounting_request.request_identity != predecessor_identity
        or accounting_request.request_ref != predecessor_identity.to_ref()
        or checked_pending.record.request_ref != predecessor_identity.to_ref()
        or checked_pending.record.source_event_pair
        != RecordRefPair(
            accounting_request.source_event,
            accounting_request.source_event_ref,
        )
    ):
        raise _stale("/predecessor_request")
    if (
        directive.directive_kind is not AttemptAccountingDirectiveKind.PENDING_SUCCESSOR
        or not directive.successor_authorization_binding.is_bound
    ):
        raise _incomplete("/pending")
    authorization = directive.successor_authorization_binding.value
    if (
        successor.current_attempt_predecessor_binding != pending_pair
        or successor_identity.current_attempt_predecessor_ref != checked_pending.ref
        or successor_identity.current_attempt_lineage_ref
        != authorization.replacement_lineage_ref
    ):
        raise _stale("/successor_request/current_attempt_predecessor_binding")
    continuity = (
        "challenge_key",
        "sampling_plan_ref",
        "primary_population_ref",
        "selection_population_ref",
        "intended_slot_ref",
        "intended_evidence_unit_ref",
        "generator_ref",
        "environment_ref",
        "fixture_configuration_ref",
        "role_binding",
    )
    if any(
        getattr(predecessor_identity, name) != getattr(successor_identity, name)
        for name in continuity
    ):
        raise _stale("/successor_request")
    if type(checked_output) is PendingGenerationAttempt:
        output_pair = RecordRefPair(checked_output.record, checked_output.ref)
    else:
        output_pair = RecordRefPair(checked_output.record, checked_output.ref)
    evidence = SuccessorExecutionEvidence(
        authorization=authorization,
        successor_request_pair=RecordRefPair(
            successor_identity,
            successor_identity.to_ref(),
        ),
        successor_output_pair=output_pair,
    )
    replacement = ReplacementDecision(
        sampling_plan_ref=predecessor_identity.sampling_plan_ref,
        policy_binding=ReplacementPolicyBinding(
            ReplacementPolicyBindingKind.REGISTERED_POLICY,
            authorization.registered_policy_ref,
        ),
        decision=authorization.policy_decision_kind,
        trigger_binding=ApplicabilityBinding.bound(authorization.replacement_trigger),
        lineage_binding=ApplicabilityBinding.bound(
            authorization.replacement_lineage_ref
        ),
        accounting_evidence_ref=(authorization.replacement_accounting_evidence_ref),
    )
    decision = AttemptAccountingDecision(
        challenge_key=accounting_request.challenge_key,
        request_ref=accounting_request.request_ref,
        source_event_ref=accounting_request.source_event_ref,
        attempt_ref=predecessor_identity.attempt_ref,
        intended_slot_ref=predecessor_identity.intended_slot_ref,
        intended_evidence_unit_ref=predecessor_identity.intended_evidence_unit_ref,
        provisional_outcome=accounting_request.provisional_outcome,
        provisional_stage=accounting_request.provisional_stage,
        final_outcome=accounting_request.provisional_outcome,
        final_stage=accounting_request.provisional_stage,
        accounting_directive_pair=directive_pair,
        outcome_replacement_binding=ApplicabilityBinding.bound(replacement),
        denominator_effect_binding=directive.denominator_effect_binding,
        successor_execution_binding=ApplicabilityBinding.bound(evidence),
    )
    decision_ref = decision.to_ref()

    censoring_decision: object | None = None
    censoring_decision_ref: object | None = None
    if accounting_request.provisional_outcome is GeneratorOutcomeKind.CENSORED_CASE:
        verdict_binding = checked_pending.record.censoring_verdict_binding
        if not verdict_binding.is_bound:
            raise _incomplete("/pending/record/censoring_verdict_binding")
        from .authorities import finalize_censoring_decision

        verdict = verdict_binding.pair.record
        censoring_decision, censoring_decision_ref = finalize_censoring_decision(
            request=verdict.request,
            verdict=verdict,
            verdict_ref=verdict_binding.pair.ref,
            accounting_decision=decision,
            accounting_decision_ref=decision_ref,
        )
        censoring_binding = RecordRefBinding.bound(
            censoring_decision,
            censoring_decision_ref,
        )
        case_ref_binding = ApplicabilityBinding.bound(
            checked_pending.record.constructed_case_binding.pair.ref
        )
    else:
        censoring_binding = RecordRefBinding.not_applicable(
            _reason_ref(
                predecessor_identity,
                ApplicabilityReasonKind.CENSORING_DECISION_INAPPLICABLE,
            )
        )
        case_ref_binding = ApplicabilityBinding.not_applicable(
            _reason_ref(
                predecessor_identity,
                ApplicabilityReasonKind.RESULT_CASE_INAPPLICABLE,
            )
        )
    attempt, attempt_ref = build_generation_attempt_record(
        request=predecessor,
        source_event=checked_pending.record.source_event_pair.record,
        accounting_decision=decision,
        accounting_decision_ref=decision_ref,
        case_ref_binding=case_ref_binding,
        support_decision_binding=checked_pending.record.support_decision_binding,
        censoring_verdict_binding=checked_pending.record.censoring_verdict_binding,
        censoring_decision_binding=censoring_binding,
        conformance_facts_pair=checked_pending.record.conformance_facts_pair,
        failure_reason_binding=checked_pending.record.failure_reason_binding,
        failure_occurrence_binding=checked_pending.record.failure_occurrence_binding,
        pending_attempt_binding=ApplicabilityBinding.bound(checked_pending.ref),
    )
    return (
        decision,
        decision_ref,
        censoring_decision,
        censoring_decision_ref,
        attempt,
        attempt_ref,
    )


@dataclass(frozen=True, slots=True, repr=False)
class GeneratorOutcomeCount:
    """One exact UInt64 count in the closed six-outcome order."""

    outcome_kind: GeneratorOutcomeKind
    count: int

    def __post_init__(self) -> None:
        if type(self) is not GeneratorOutcomeCount:
            raise _wrong("/count")
        outcome = _exact(self.outcome_kind, GeneratorOutcomeKind, "/outcome_kind")
        count = _uint64(self.count, "/count")
        object.__setattr__(self, "outcome_kind", outcome)
        object.__setattr__(self, "count", count)

    def __repr__(self) -> str:
        return "GeneratorOutcomeCount(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("generator outcome counts cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("generator outcome counts cannot be pickled")


def _exact_pair_tuple(
    value: object,
    *,
    record_type: type,
    ref_type: type,
    path: str,
    nonempty: bool = False,
) -> tuple[RecordRefPair, ...]:
    if type(value) is not tuple or (nonempty and not value):
        raise _wrong(path)
    result: list[RecordRefPair] = []
    for index, item in enumerate(value):
        pair = _pair(item, f"{path}/{index}")
        _require_pair_type(pair, record_type, ref_type, f"{path}/{index}")
        result.append(pair)
    if len({item.ref for item in result}) != len(result):
        raise _invalid(path)
    return tuple(result)


def _revalidated_pair_tuple(
    value: object,
    *,
    record_type: type,
    ref_type: type,
    path: str,
    nonempty: bool = False,
) -> tuple[RecordRefPair, ...]:
    pairs = _exact_pair_tuple(
        value,
        record_type=record_type,
        ref_type=ref_type,
        path=path,
        nonempty=nonempty,
    )
    result: list[RecordRefPair] = []
    for index, pair in enumerate(pairs):
        validation_failure: tuple[str, str] | None = None
        try:
            record = replace(pair.record)
            result.append(RecordRefPair(record, pair.ref))
        except GeneratorValidationError as error:
            validation_failure = (error.code, error.path)
        except (TypeError, ValueError):
            validation_failure = (
                GeneratorInputCode.INVALID_VALUE.value,
                f"{path}/{index}",
            )
        if validation_failure is not None:
            raise GeneratorValidationError(
                validation_failure[0],
                path=validation_failure[1],
            )
    return tuple(result)


@dataclass(frozen=True, slots=True, repr=False)
class IntendedUnitAccounting:
    """Complete attempt history for one externally linked intended unit."""

    challenge_key: ChallengeKey
    sampling_plan_ref: SamplingPlanRef
    primary_population_ref: InstanceDistributionContractRef
    selection_population_ref: InstanceDistributionContractRef
    intended_slot_ref: object
    intended_evidence_unit_ref: object
    link_decision_pairs: tuple[RecordRefPair, ...]
    attempt_record_pairs: tuple[RecordRefPair, ...]
    pending_attempt_pairs: tuple[RecordRefPair, ...]
    replacement_lineage_refs: tuple[object, ...]
    denominator_effect_bindings: tuple[ApplicabilityBinding[object], ...]
    realized_outcome: GeneratorOutcomeKind
    realized_case_ref: CanonicalChallengeCaseRef | None

    def __post_init__(self) -> None:
        from .authorities import IntendedUnitLinkDecision
        from .refs import IntendedUnitLinkDecisionRef

        if type(self) is not IntendedUnitAccounting:
            raise _wrong("/intended_unit_pairs")
        key = _challenge(self.challenge_key)
        plan = _top_ref(
            self.sampling_plan_ref,
            SamplingPlanRef,
            challenge_key=key,
            path="/sampling_plan_ref",
        )
        primary = _top_ref(
            self.primary_population_ref,
            InstanceDistributionContractRef,
            challenge_key=key,
            path="/primary_population_ref",
        )
        selection = _top_ref(
            self.selection_population_ref,
            InstanceDistributionContractRef,
            challenge_key=key,
            path="/selection_population_ref",
        )
        slot = _owner(
            self.intended_slot_ref,
            "protected_intended_slot",
            challenge_key=key,
            path="/intended_slot_ref",
        )
        unit = _owner(
            self.intended_evidence_unit_ref,
            "protected_intended_evidence_unit",
            challenge_key=key,
            path="/intended_evidence_unit_ref",
        )
        links = _revalidated_pair_tuple(
            self.link_decision_pairs,
            record_type=IntendedUnitLinkDecision,
            ref_type=IntendedUnitLinkDecisionRef,
            path="/link_decision_pairs",
            nonempty=True,
        )
        reconstructed_links: list[RecordRefPair] = []
        for index, pair in enumerate(links):
            validation_failure: tuple[str, str] | None = None
            try:
                request = replace(pair.record.request)
                decision = replace(pair.record, request=request)
                reconstructed = RecordRefPair(decision, pair.ref)
            except GeneratorValidationError as error:
                validation_failure = (error.code, error.path)
                reconstructed = None
            except Exception:  # noqa: BLE001 - protected nested-link boundary.
                validation_failure = (
                    GeneratorInputCode.INVALID_VALUE.value,
                    f"/link_decision_pairs/{index}",
                )
                reconstructed = None
            if validation_failure is not None:
                raise GeneratorValidationError(
                    validation_failure[0],
                    path=validation_failure[1],
                )
            if reconstructed is None:
                raise _invalid(f"/link_decision_pairs/{index}")
            reconstructed_links.append(reconstructed)
        links = tuple(reconstructed_links)
        attempts = _revalidated_pair_tuple(
            self.attempt_record_pairs,
            record_type=GenerationAttemptRecord,
            ref_type=GenerationAttemptRecordRef,
            path="/attempt_record_pairs",
            nonempty=True,
        )
        pending = _revalidated_pair_tuple(
            self.pending_attempt_pairs,
            record_type=PendingGenerationAttemptRecord,
            ref_type=PendingGenerationAttemptRef,
            path="/pending_attempt_pairs",
        )
        if len(links) != len(attempts) or len(pending) + 1 != len(attempts):
            raise _invalid("/attempt_record_pairs")
        ordinals = tuple(item.record.attempt_ordinal for item in attempts)
        if any(right <= left for left, right in pairwise(ordinals)):
            raise _invalid("/attempt_record_pairs")
        attempt_refs = tuple(item.record.attempt_ref for item in attempts)
        if len(set(attempt_refs)) != len(attempt_refs):
            raise _invalid("/attempt_record_pairs")
        lineages = self.replacement_lineage_refs
        if type(lineages) is not tuple or len(lineages) != len(pending):
            raise _wrong("/replacement_lineage_refs")
        checked_lineages = tuple(
            _owner(
                item,
                "protected_replacement_lineage",
                challenge_key=key,
                path=f"/replacement_lineage_refs/{index}",
            )
            for index, item in enumerate(lineages)
        )
        denominators = self.denominator_effect_bindings
        if type(denominators) is not tuple or len(denominators) != len(attempts):
            raise _wrong("/denominator_effect_bindings")
        checked_denominators = tuple(
            _binding_owner(
                item,
                "denominator_effect",
                challenge_key=key,
                path=f"/denominator_effect_bindings/{index}",
            )
            for index, item in enumerate(denominators)
        )
        common = (key, plan, primary, selection, slot, unit)
        for index, (link_pair, attempt_pair) in enumerate(zip(links, attempts)):
            attempt = attempt_pair.record
            identity = (
                attempt.accounting_decision_pair.record.accounting_directive_pair.record.request.request_identity
            )
            link_request = link_pair.record.request
            observed = (
                attempt.challenge_key,
                attempt.sampling_plan_ref,
                attempt.primary_population_ref,
                attempt.selection_population_ref,
                attempt.intended_slot_ref,
                attempt.intended_evidence_unit_ref,
            )
            if observed != common:
                raise _stale(f"/attempt_record_pairs/{index}")
            if (
                link_pair.ref != identity.intended_unit_link_decision_ref
                or link_pair.record.challenge_key != identity.challenge_key
                or (
                    link_request.challenge_key,
                    link_request.sampling_plan_ref,
                    link_request.selection_population_ref,
                    link_request.role_binding,
                    link_request.replay_ref,
                    link_request.intended_slot_ref,
                    link_request.intended_evidence_unit_ref,
                    link_request.attempt_ref,
                )
                != (
                    identity.challenge_key,
                    identity.sampling_plan_ref,
                    identity.selection_population_ref,
                    identity.role_binding,
                    identity.replay_ref,
                    identity.intended_slot_ref,
                    identity.intended_evidence_unit_ref,
                    identity.attempt_ref,
                )
            ):
                raise _stale(f"/link_decision_pairs/{index}")
            decision = attempt.accounting_decision_pair.record
            if decision.denominator_effect_binding != checked_denominators[index]:
                raise _stale(f"/denominator_effect_bindings/{index}")

        first = attempts[0].record
        if first.current_predecessor_binding.is_bound:
            raise _invalid("/attempt_record_pairs/0/current_predecessor_binding")
        for index, lineage in enumerate(checked_lineages):
            current = attempts[index].record
            successor = attempts[index + 1].record
            pending_pair = pending[index]
            if (
                not current.pending_attempt_binding.is_bound
                or current.pending_attempt_binding.value != pending_pair.ref
                or pending_pair.record.request_ref != current.request_ref
                or pending_pair.record.accounting_directive_pair
                != current.accounting_decision_pair.record.accounting_directive_pair
            ):
                raise _stale(f"/pending_attempt_pairs/{index}")
            execution = (
                current.accounting_decision_pair.record.successor_execution_binding
            )
            if not execution.is_bound:
                raise _incomplete(f"/attempt_record_pairs/{index}")
            evidence = execution.value
            if (
                evidence.authorization.replacement_lineage_ref != lineage
                or evidence.successor_request_pair.ref != successor.request_ref
                or not successor.current_predecessor_binding.is_bound
                or successor.current_predecessor_binding.pair != pending_pair
                or not successor.current_lineage_binding.is_bound
                or successor.current_lineage_binding.value != lineage
            ):
                raise _stale(f"/attempt_record_pairs/{index + 1}")
            output = evidence.successor_output_pair
            if index + 1 < len(attempts) - 1:
                if output != pending[index + 1]:
                    raise _stale(f"/attempt_record_pairs/{index + 1}")
            elif (
                type(output.record) is not GeneratorResultRecord
                or type(output.ref) is not GeneratorResultRef
                or output.record.attempt_record_ref != attempts[index + 1].ref
                or output.record.attempt_record != attempts[index + 1].record
            ):
                raise _stale(f"/attempt_record_pairs/{index + 1}")
        final_attempt = attempts[-1].record
        if (
            final_attempt.pending_attempt_binding.is_bound
            or final_attempt.accounting_decision_pair.record.successor_execution_binding.is_bound
        ):
            raise _incomplete("/attempt_record_pairs")
        realized = _exact(
            self.realized_outcome,
            GeneratorOutcomeKind,
            "/realized_outcome",
        )
        if realized is not final_attempt.outcome_kind:
            raise _stale("/realized_outcome")
        if realized in {
            GeneratorOutcomeKind.VALID_GENERATED,
            GeneratorOutcomeKind.CENSORED_CASE,
        }:
            case_ref = _top_ref(
                self.realized_case_ref,
                CanonicalChallengeCaseRef,
                challenge_key=key,
                path="/realized_case_ref",
            )
            if (
                not final_attempt.case_ref_binding.is_bound
                or final_attempt.case_ref_binding.value != case_ref
            ):
                raise _stale("/realized_case_ref")
        else:
            if self.realized_case_ref is not None:
                raise _invalid("/realized_case_ref")
            case_ref = None
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "sampling_plan_ref", plan)
        object.__setattr__(self, "primary_population_ref", primary)
        object.__setattr__(self, "selection_population_ref", selection)
        object.__setattr__(self, "intended_slot_ref", slot)
        object.__setattr__(self, "intended_evidence_unit_ref", unit)
        object.__setattr__(self, "link_decision_pairs", links)
        object.__setattr__(self, "attempt_record_pairs", attempts)
        object.__setattr__(self, "pending_attempt_pairs", pending)
        object.__setattr__(self, "replacement_lineage_refs", checked_lineages)
        object.__setattr__(self, "denominator_effect_bindings", checked_denominators)
        object.__setattr__(self, "realized_outcome", realized)
        object.__setattr__(self, "realized_case_ref", case_ref)

    def __repr__(self) -> str:
        return "IntendedUnitAccounting(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("intended unit accounting cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("intended unit accounting cannot be pickled")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> IntendedUnitAccountingRef:
        from .canonical import _record_ref

        return _record_ref(self, IntendedUnitAccountingRef)  # type: ignore[return-value]


def build_intended_unit_accounting(
    *,
    link_decision_pairs: tuple[RecordRefPair, ...],
    attempt_record_pairs: tuple[RecordRefPair, ...],
    pending_attempt_pairs: tuple[RecordRefPair, ...],
    accounting_directive_pairs: tuple[RecordRefPair, ...],
    accounting_decision_pairs: tuple[RecordRefPair, ...],
) -> tuple[IntendedUnitAccounting, IntendedUnitAccountingRef]:
    """Derive one complete intended-unit partition from verified final rows."""

    attempts = _revalidated_pair_tuple(
        attempt_record_pairs,
        record_type=GenerationAttemptRecord,
        ref_type=GenerationAttemptRecordRef,
        path="/attempt_record_pairs",
        nonempty=True,
    )
    directives = _revalidated_pair_tuple(
        accounting_directive_pairs,
        record_type=AttemptAccountingDirective,
        ref_type=AttemptAccountingDirectiveRef,
        path="/accounting_directive_pairs",
        nonempty=True,
    )
    decisions = _revalidated_pair_tuple(
        accounting_decision_pairs,
        record_type=AttemptAccountingDecision,
        ref_type=AttemptAccountingDecisionRef,
        path="/accounting_decision_pairs",
        nonempty=True,
    )
    if not (len(attempts) == len(directives) == len(decisions)):
        raise _invalid("/accounting_decision_pairs")
    for index, attempt_pair in enumerate(attempts):
        decision_pair = attempt_pair.record.accounting_decision_pair
        if decision_pair != decisions[index]:
            raise _stale(f"/accounting_decision_pairs/{index}")
        if decision_pair.record.accounting_directive_pair != directives[index]:
            raise _stale(f"/accounting_directive_pairs/{index}")
    first = attempts[0].record
    final = attempts[-1].record
    pending = _revalidated_pair_tuple(
        pending_attempt_pairs,
        record_type=PendingGenerationAttemptRecord,
        ref_type=PendingGenerationAttemptRef,
        path="/pending_attempt_pairs",
    )
    lineage_values: list[object] = []
    for index, item in enumerate(attempts[:-1]):
        replacement = (
            item.record.accounting_decision_pair.record.outcome_replacement_binding
        )
        if (
            not replacement.is_bound
            or type(replacement.value) is not ReplacementDecision
            or not replacement.value.lineage_binding.is_bound
        ):
            raise _incomplete(f"/attempt_record_pairs/{index}")
        lineage_values.append(replacement.value.lineage_binding.value)
    lineages = tuple(lineage_values)
    realized_case_ref = (
        final.case_ref_binding.value if final.case_ref_binding.is_bound else None
    )
    accounting = IntendedUnitAccounting(
        challenge_key=first.challenge_key,
        sampling_plan_ref=first.sampling_plan_ref,
        primary_population_ref=first.primary_population_ref,
        selection_population_ref=first.selection_population_ref,
        intended_slot_ref=first.intended_slot_ref,
        intended_evidence_unit_ref=first.intended_evidence_unit_ref,
        link_decision_pairs=link_decision_pairs,
        attempt_record_pairs=attempts,
        pending_attempt_pairs=pending,
        replacement_lineage_refs=lineages,
        denominator_effect_bindings=tuple(
            item.record.accounting_decision_pair.record.denominator_effect_binding
            for item in attempts
        ),
        realized_outcome=final.outcome_kind,
        realized_case_ref=realized_case_ref,
    )
    return accounting, accounting.to_ref()


_OUTCOME_ORDER = tuple(GeneratorOutcomeKind)


def _derived_counts(
    outcomes: tuple[GeneratorOutcomeKind, ...],
) -> tuple[GeneratorOutcomeCount, ...]:
    return tuple(
        GeneratorOutcomeCount(kind, sum(item is kind for item in outcomes))
        for kind in _OUTCOME_ORDER
    )


@dataclass(frozen=True, slots=True, repr=False)
class GenerationAccountingSummary:
    """Exact attempt and realized-intended-unit partitions."""

    challenge_key: ChallengeKey
    intended_unit_pairs: tuple[RecordRefPair, ...]
    attempt_count: int
    attempt_outcome_counts: tuple[GeneratorOutcomeCount, ...]
    intended_unit_count: int
    realized_outcome_counts: tuple[GeneratorOutcomeCount, ...]
    realized_valid_case_refs: tuple[CanonicalChallengeCaseRef, ...]

    def __post_init__(self) -> None:
        if type(self) is not GenerationAccountingSummary:
            raise _wrong("/accounting_summary")
        key = _challenge(self.challenge_key)
        units = _revalidated_pair_tuple(
            self.intended_unit_pairs,
            record_type=IntendedUnitAccounting,
            ref_type=IntendedUnitAccountingRef,
            path="/intended_unit_pairs",
            nonempty=True,
        )
        if any(item.record.challenge_key != key for item in units):
            raise _cross_challenge("/intended_unit_pairs")
        intended_units = tuple(item.record.intended_evidence_unit_ref for item in units)
        if len(set(intended_units)) != len(intended_units):
            raise _invalid("/intended_unit_pairs")
        if tuple(sorted(units, key=lambda item: item.ref.content_digest)) != units:
            raise _invalid("/intended_unit_pairs")
        attempt_refs = tuple(
            attempt.ref
            for unit_pair in units
            for attempt in unit_pair.record.attempt_record_pairs
        )
        if len(set(attempt_refs)) != len(attempt_refs):
            raise _invalid("/intended_unit_pairs")
        protected_attempt_refs = tuple(
            attempt.record.attempt_ref
            for unit_pair in units
            for attempt in unit_pair.record.attempt_record_pairs
        )
        if len(set(protected_attempt_refs)) != len(protected_attempt_refs):
            raise _invalid("/intended_unit_pairs")
        attempt_count = _uint64(self.attempt_count, "/attempt_count")
        unit_count = _uint64(self.intended_unit_count, "/intended_unit_count")
        if attempt_count != len(attempt_refs) or unit_count != len(units):
            raise _stale("/attempt_count")
        for name, values, total in (
            ("attempt_outcome_counts", self.attempt_outcome_counts, attempt_count),
            ("realized_outcome_counts", self.realized_outcome_counts, unit_count),
        ):
            if (
                type(values) is not tuple
                or len(values) != len(_OUTCOME_ORDER)
                or any(type(item) is not GeneratorOutcomeCount for item in values)
                or tuple(item.outcome_kind for item in values) != _OUTCOME_ORDER
                or sum(item.count for item in values) != total
            ):
                raise _invalid(f"/{name}")
        attempt_outcomes = tuple(
            attempt.record.outcome_kind
            for unit_pair in units
            for attempt in unit_pair.record.attempt_record_pairs
        )
        realized_outcomes = tuple(item.record.realized_outcome for item in units)
        if self.attempt_outcome_counts != _derived_counts(attempt_outcomes):
            raise _stale("/attempt_outcome_counts")
        if self.realized_outcome_counts != _derived_counts(realized_outcomes):
            raise _stale("/realized_outcome_counts")
        valid_refs = self.realized_valid_case_refs
        if type(valid_refs) is not tuple:
            raise _wrong("/realized_valid_case_refs")
        checked_valid_refs = tuple(
            _top_ref(
                ref,
                CanonicalChallengeCaseRef,
                challenge_key=key,
                path=f"/realized_valid_case_refs/{index}",
            )
            for index, ref in enumerate(valid_refs)
        )
        expected_valid_refs = tuple(
            item.record.realized_case_ref
            for item in units
            if item.record.realized_outcome is GeneratorOutcomeKind.VALID_GENERATED
        )
        if checked_valid_refs != expected_valid_refs:
            raise _stale("/realized_valid_case_refs")
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "intended_unit_pairs", units)
        object.__setattr__(self, "attempt_count", attempt_count)
        object.__setattr__(self, "intended_unit_count", unit_count)
        object.__setattr__(self, "realized_valid_case_refs", checked_valid_refs)

    def __repr__(self) -> str:
        return "GenerationAccountingSummary(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("generation accounting summaries cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("generation accounting summaries cannot be pickled")

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> GenerationAccountingSummaryRef:
        from .canonical import _record_ref

        return _record_ref(self, GenerationAccountingSummaryRef)  # type: ignore[return-value]


def build_generation_accounting_summary(
    intended_unit_pairs: tuple[RecordRefPair, ...],
) -> tuple[GenerationAccountingSummary, GenerationAccountingSummaryRef]:
    """Derive both partitions and every count; no caller totals are accepted."""

    units = _revalidated_pair_tuple(
        intended_unit_pairs,
        record_type=IntendedUnitAccounting,
        ref_type=IntendedUnitAccountingRef,
        path="/intended_unit_pairs",
        nonempty=True,
    )
    units = tuple(sorted(units, key=lambda item: item.ref.content_digest))
    attempt_outcomes = tuple(
        attempt.record.outcome_kind
        for unit_pair in units
        for attempt in unit_pair.record.attempt_record_pairs
    )
    realized_outcomes = tuple(item.record.realized_outcome for item in units)
    valid_refs = tuple(
        item.record.realized_case_ref
        for item in units
        if item.record.realized_outcome is GeneratorOutcomeKind.VALID_GENERATED
    )
    summary = GenerationAccountingSummary(
        challenge_key=units[0].record.challenge_key,
        intended_unit_pairs=units,
        attempt_count=len(attempt_outcomes),
        attempt_outcome_counts=_derived_counts(attempt_outcomes),
        intended_unit_count=len(units),
        realized_outcome_counts=_derived_counts(realized_outcomes),
        realized_valid_case_refs=valid_refs,
    )
    return summary, summary.to_ref()


# Closed canonical ownership for every accounting record and nested decision.
from .canonical import (
    _CHALLENGE_KEY,
    _REPLAY_REF,
    _UINT64,
    _authoring,
    _enum,
    _nested,
    _optional,
    _record,
    _register_canonical_type,
    _register_nested_canonical_type,
    _tuple_of,
)
from .canonical import (
    _applicability as _applicability_codec,
)
from .canonical import (
    _generator_ref as _generator_ref_codec,
)
from .canonical import (
    _owner as _owner_codec,
)
from .canonical import (
    _top_ref as _top_ref_codec,
)

_register_nested_canonical_type(
    AttemptAccountingRequest,
    record_type="attempt_accounting_request",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("request_identity", _record(GeneratorRequestIdentity)),
        ("request_ref", _generator_ref_codec(GeneratorRequestRef)),
        ("source_event", _record(GenerationSourceEvent)),
        ("source_event_ref", _owner_codec("generation_event")),
        ("provisional_outcome", _enum(GeneratorOutcomeKind)),
        ("provisional_stage", _enum(GeneratorTerminalStage)),
        ("support_decision_binding", _nested(RecordRefBinding)),
        ("constructed_case_binding", _nested(RecordRefBinding)),
        ("censoring_verdict_binding", _nested(RecordRefBinding)),
        ("failure_reason_binding", _nested(RecordRefBinding)),
        ("failure_occurrence_binding", _nested(RecordRefBinding)),
        ("replacement_policy", _authoring(ReplacementPolicy)),
        (
            "replacement_trigger_binding",
            _applicability_codec(_authoring(ReplacementTrigger)),
        ),
        (
            "outcome_replacement_inapplicable_reason_ref",
            _owner_codec("applicability_reason"),
        ),
        (
            "successor_authorization_inapplicable_reason_ref",
            _owner_codec("applicability_reason"),
        ),
        (
            "successor_execution_inapplicable_reason_ref",
            _owner_codec("applicability_reason"),
        ),
        (
            "denominator_effect_inapplicable_reason_ref",
            _owner_codec("applicability_reason"),
        ),
        (
            "denominator_owner_unavailable_reason_ref",
            _owner_codec("applicability_reason"),
        ),
        (
            "accounting_authority_failure_ref",
            _owner_codec("infrastructure_failure"),
        ),
    ),
)
_register_nested_canonical_type(
    SuccessorAuthorization,
    record_type="successor_authorization",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        (
            "predecessor_request_ref",
            _generator_ref_codec(GeneratorRequestRef),
        ),
        ("predecessor_source_event_ref", _owner_codec("generation_event")),
        (
            "predecessor_attempt_ref",
            _owner_codec("protected_attempt_commitment"),
        ),
        ("predecessor_attempt_ordinal", _UINT64),
        ("sampling_plan_ref", _top_ref_codec(SamplingPlanRef)),
        (
            "primary_population_ref",
            _top_ref_codec(InstanceDistributionContractRef),
        ),
        (
            "selection_population_ref",
            _top_ref_codec(InstanceDistributionContractRef),
        ),
        ("intended_slot_ref", _owner_codec("protected_intended_slot")),
        (
            "intended_evidence_unit_ref",
            _owner_codec("protected_intended_evidence_unit"),
        ),
        ("registered_policy_ref", _owner_codec("replacement_policy")),
        ("replacement_trigger", _authoring(ReplacementTrigger)),
        ("policy_decision_kind", _enum(ReplacementDecisionKind)),
        (
            "replacement_accounting_evidence_ref",
            _owner_codec("replacement_accounting"),
        ),
        (
            "successor_attempt_ref",
            _owner_codec("protected_attempt_commitment"),
        ),
        ("successor_attempt_ordinal", _UINT64),
        (
            "replacement_lineage_ref",
            _owner_codec("protected_replacement_lineage"),
        ),
    ),
)
_register_canonical_type(
    AttemptAccountingDirective,
    object_kind="attempt_accounting_directive",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("request", _nested(AttemptAccountingRequest)),
        ("directive_kind", _enum(AttemptAccountingDirectiveKind)),
        ("provisional_outcome", _enum(GeneratorOutcomeKind)),
        ("provisional_stage", _enum(GeneratorTerminalStage)),
        ("final_outcome", _optional(_enum(GeneratorOutcomeKind))),
        ("final_stage", _optional(_enum(GeneratorTerminalStage))),
        (
            "outcome_replacement_binding",
            _applicability_codec(_authoring(ReplacementDecision)),
        ),
        (
            "successor_authorization_binding",
            _applicability_codec(_nested(SuccessorAuthorization)),
        ),
        (
            "denominator_effect_binding",
            _applicability_codec(_owner_codec("denominator_effect")),
        ),
        (
            "accounting_authority_failure_ref",
            _optional(_owner_codec("infrastructure_failure")),
        ),
    ),
)
_register_canonical_type(
    PendingGenerationAttemptRecord,
    object_kind="pending_generation_attempt",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("request_ref", _generator_ref_codec(GeneratorRequestRef)),
        ("source_event_pair", _nested(RecordRefPair)),
        ("provisional_outcome", _enum(GeneratorOutcomeKind)),
        ("provisional_stage", _enum(GeneratorTerminalStage)),
        ("support_decision_binding", _nested(RecordRefBinding)),
        ("constructed_case_binding", _nested(RecordRefBinding)),
        ("censoring_verdict_binding", _nested(RecordRefBinding)),
        ("failure_reason_binding", _nested(RecordRefBinding)),
        ("failure_occurrence_binding", _nested(RecordRefBinding)),
        ("conformance_facts_pair", _nested(RecordRefPair)),
        ("accounting_directive_pair", _nested(RecordRefPair)),
    ),
)
_register_nested_canonical_type(
    SuccessorExecutionEvidence,
    record_type="successor_execution_evidence",
    fields=(
        ("authorization", _nested(SuccessorAuthorization)),
        ("successor_request_pair", _nested(RecordRefPair)),
        ("successor_output_pair", _nested(RecordRefPair)),
    ),
)
_register_canonical_type(
    AttemptAccountingDecision,
    object_kind="attempt_accounting_decision",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("request_ref", _generator_ref_codec(GeneratorRequestRef)),
        ("source_event_ref", _owner_codec("generation_event")),
        ("attempt_ref", _owner_codec("protected_attempt_commitment")),
        ("intended_slot_ref", _owner_codec("protected_intended_slot")),
        (
            "intended_evidence_unit_ref",
            _owner_codec("protected_intended_evidence_unit"),
        ),
        ("provisional_outcome", _enum(GeneratorOutcomeKind)),
        ("provisional_stage", _enum(GeneratorTerminalStage)),
        ("final_outcome", _enum(GeneratorOutcomeKind)),
        ("final_stage", _enum(GeneratorTerminalStage)),
        ("accounting_directive_pair", _nested(RecordRefPair)),
        (
            "outcome_replacement_binding",
            _applicability_codec(_authoring(ReplacementDecision)),
        ),
        (
            "denominator_effect_binding",
            _applicability_codec(_owner_codec("denominator_effect")),
        ),
        (
            "successor_execution_binding",
            _applicability_codec(_nested(SuccessorExecutionEvidence)),
        ),
    ),
)
_register_canonical_type(
    GenerationAttemptRecord,
    object_kind="generation_attempt_record",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("request_ref", _generator_ref_codec(GeneratorRequestRef)),
        ("source_event_ref", _owner_codec("generation_event")),
        ("generator_ref", _owner_codec("generator")),
        ("environment_ref", _generator_ref_codec(GeneratorEnvironmentRef)),
        (
            "fixture_configuration_ref",
            _generator_ref_codec(BurgersFixtureConfigurationRef),
        ),
        (
            "primary_population_ref",
            _top_ref_codec(InstanceDistributionContractRef),
        ),
        (
            "selection_population_ref",
            _top_ref_codec(InstanceDistributionContractRef),
        ),
        ("sampling_plan_ref", _top_ref_codec(SamplingPlanRef)),
        ("role_binding", _nested(GenerationRoleBinding)),
        ("replay_ref", _REPLAY_REF),
        ("intended_slot_ref", _owner_codec("protected_intended_slot")),
        (
            "intended_evidence_unit_ref",
            _owner_codec("protected_intended_evidence_unit"),
        ),
        ("attempt_ref", _owner_codec("protected_attempt_commitment")),
        ("attempt_ordinal", _UINT64),
        ("materialization_state", _enum(SourceMaterializationState)),
        ("outcome_kind", _enum(GeneratorOutcomeKind)),
        ("terminal_stage", _enum(GeneratorTerminalStage)),
        (
            "case_ref_binding",
            _applicability_codec(_top_ref_codec(CanonicalChallengeCaseRef)),
        ),
        ("support_decision_binding", _nested(RecordRefBinding)),
        ("censoring_verdict_binding", _nested(RecordRefBinding)),
        ("censoring_decision_binding", _nested(RecordRefBinding)),
        ("conformance_facts_pair", _nested(RecordRefPair)),
        ("failure_reason_binding", _nested(RecordRefBinding)),
        ("failure_occurrence_binding", _nested(RecordRefBinding)),
        ("current_predecessor_binding", _nested(RecordRefBinding)),
        (
            "current_lineage_binding",
            _applicability_codec(_owner_codec("protected_replacement_lineage")),
        ),
        (
            "pending_attempt_binding",
            _applicability_codec(_generator_ref_codec(PendingGenerationAttemptRef)),
        ),
        ("accounting_decision_pair", _nested(RecordRefPair)),
    ),
)
_register_nested_canonical_type(
    GeneratorOutcomeCount,
    record_type="generator_outcome_count",
    fields=(
        ("outcome_kind", _enum(GeneratorOutcomeKind)),
        ("count", _UINT64),
    ),
)
_register_canonical_type(
    IntendedUnitAccounting,
    object_kind="intended_unit_accounting",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("sampling_plan_ref", _top_ref_codec(SamplingPlanRef)),
        (
            "primary_population_ref",
            _top_ref_codec(InstanceDistributionContractRef),
        ),
        (
            "selection_population_ref",
            _top_ref_codec(InstanceDistributionContractRef),
        ),
        ("intended_slot_ref", _owner_codec("protected_intended_slot")),
        (
            "intended_evidence_unit_ref",
            _owner_codec("protected_intended_evidence_unit"),
        ),
        ("link_decision_pairs", _tuple_of(_nested(RecordRefPair))),
        ("attempt_record_pairs", _tuple_of(_nested(RecordRefPair))),
        ("pending_attempt_pairs", _tuple_of(_nested(RecordRefPair))),
        (
            "replacement_lineage_refs",
            _tuple_of(_owner_codec("protected_replacement_lineage")),
        ),
        (
            "denominator_effect_bindings",
            _tuple_of(_applicability_codec(_owner_codec("denominator_effect"))),
        ),
        ("realized_outcome", _enum(GeneratorOutcomeKind)),
        (
            "realized_case_ref",
            _optional(_top_ref_codec(CanonicalChallengeCaseRef)),
        ),
    ),
)
_register_canonical_type(
    GenerationAccountingSummary,
    object_kind="generation_accounting_summary",
    fields=(
        ("challenge_key", _CHALLENGE_KEY),
        ("intended_unit_pairs", _tuple_of(_nested(RecordRefPair))),
        ("attempt_count", _UINT64),
        (
            "attempt_outcome_counts",
            _tuple_of(_nested(GeneratorOutcomeCount)),
        ),
        ("intended_unit_count", _UINT64),
        (
            "realized_outcome_counts",
            _tuple_of(_nested(GeneratorOutcomeCount)),
        ),
        (
            "realized_valid_case_refs",
            _tuple_of(_top_ref_codec(CanonicalChallengeCaseRef)),
        ),
    ),
)


__all__ = (
    "AttemptAccountingAuthority",
    "AttemptAccountingDecision",
    "AttemptAccountingDirective",
    "AttemptAccountingDirectiveKind",
    "AttemptAccountingRequest",
    "GenerationAccountingSummary",
    "GenerationAttemptRecord",
    "GeneratorOutcomeCount",
    "IntendedUnitAccounting",
    "PendingGenerationAttempt",
    "PendingGenerationAttemptRecord",
    "SuccessorAuthorization",
    "SuccessorExecutionEvidence",
    "build_attempt_accounting_decision",
    "build_generation_accounting_summary",
    "build_generation_attempt_record",
    "build_intended_unit_accounting",
    "build_pending_generation_attempt",
    "finalize_pending_accounting",
)
