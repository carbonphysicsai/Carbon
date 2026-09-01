"""Policy-owned primary/witness comparison records for B-04.

Comparison never runs a solver, selects a tolerance, averages references, or
promotes a witness.  The trusted factory derives one closed terminal pair from
observed facts under the ratified precedence and preserves correlation facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from carbon.authoring.canonical import encode_value, owner_ref_to_canonical
from carbon.authoring.errors import AuthoringError
from carbon.authoring.primitives import MAX_CANONICAL_TUPLE_ITEMS
from carbon.authoring.refs import (
    CanonicalChallengeCaseRef,
    ChallengeScope,
    require_owner_ref,
)
from carbon.registry.model import ChallengeKey

from .enums import (
    COMPARISON_OUTCOME_REASON_COMPATIBILITY,
    DependencyCategory,
    DependencyRelation,
    ReferenceAuthorityFunction,
    ReferenceComparisonOutcome,
    ReferenceComparisonReason,
    ReferenceIdentityKind,
    ReferenceRunOutcome,
    UncertaintyStatus,
)
from .errors import ReferenceInputCode
from .execution import (
    ReferenceRunRecord,
    _b04_ref,
    _challenge,
    _identifier,
    _identity,
    _model,
    _model_tuple,
    _ref_tuple,
    _reject,
    _scope,
    _top_ref,
    _version,
)
from .model import (
    DependencyDisclosure,
    PinnedReferenceIdentity,
    ReferenceAuthorityTarget,
    ReferenceScopeBinding,
    ReferenceTruthRecord,
    ReferenceWitnessTarget,
)
from .refs import (
    ReferencePolicyEntryRef,
    ReferencePolicyRef,
    ReferenceRunRecordRef,
)

_COMPARISON_OUTCOMES = MappingProxyType(
    {
        reason: outcome
        for outcome, reasons in COMPARISON_OUTCOME_REASON_COMPATIBILITY.items()
        for reason in reasons
    }
)
if set(_COMPARISON_OUTCOMES) != set(ReferenceComparisonReason):
    raise RuntimeError("comparison compatibility matrix is incomplete")

COMPARISON_REASON_PRECEDENCE = (
    ReferenceComparisonReason.COMPARISON_INPUT_IDENTITY_MISMATCH,
    ReferenceComparisonReason.COMPARISON_PROVENANCE_INVALID,
    ReferenceComparisonReason.PRIMARY_OR_WITNESS_NOT_SUPPORTED,
    ReferenceComparisonReason.COMPARISON_APPLICABILITY_MISMATCH,
    ReferenceComparisonReason.COMPARISON_METHOD_UNAVAILABLE,
    ReferenceComparisonReason.COMPARISON_UNCERTAINTY_UNRESOLVED,
    ReferenceComparisonReason.COMPARISON_DEPENDENCE_UNRESOLVED,
    ReferenceComparisonReason.REGISTERED_DISAGREEMENT_EXCEEDED,
    ReferenceComparisonReason.COMPARISON_REQUIREMENTS_SATISFIED,
)


def select_comparison_terminal(
    observed_reasons: tuple[ReferenceComparisonReason, ...],
) -> tuple[ReferenceComparisonOutcome, ReferenceComparisonReason]:
    if type(observed_reasons) is not tuple:
        raise _reject("/reason", ReferenceInputCode.WRONG_TYPE)
    if len(observed_reasons) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _reject("/reason", ReferenceInputCode.INVALID_VALUE)
    if any(type(item) is not ReferenceComparisonReason for item in observed_reasons):
        raise _reject("/reason", ReferenceInputCode.WRONG_TYPE)
    if len(set(observed_reasons)) != len(observed_reasons):
        raise _reject("/reason", ReferenceInputCode.DUPLICATE_IDENTITY)
    observed = set(observed_reasons)
    if not observed:
        observed.add(ReferenceComparisonReason.COMPARISON_REQUIREMENTS_SATISFIED)
    reason = next(item for item in COMPARISON_REASON_PRECEDENCE if item in observed)
    return _COMPARISON_OUTCOMES[reason], reason


def _owner_set(
    value: object,
    kind: str,
    challenge: ChallengeKey,
    path: str,
    *,
    nonempty: bool = False,
) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise _reject(path, ReferenceInputCode.WRONG_TYPE)
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _reject(path, ReferenceInputCode.INVALID_VALUE)
    if nonempty and not value:
        raise _reject(path, ReferenceInputCode.INCOMPLETE_BINDING)
    copied: list[object] = []
    for item in value:
        try:
            ref = require_owner_ref(item, kind)
        except (AttributeError, AuthoringError, TypeError, ValueError):
            raise _reject(path, ReferenceInputCode.WRONG_TYPE) from None
        if (
            type(ref.scope_binding) is not ChallengeScope
            or ref.scope_binding.challenge_key != challenge
        ):
            raise _reject(path, ReferenceInputCode.CROSS_CHALLENGE)
        copied.append(ref)
    if len(set(copied)) != len(copied):
        raise _reject(path, ReferenceInputCode.DUPLICATE_IDENTITY)
    return tuple(
        sorted(copied, key=lambda item: encode_value(owner_ref_to_canonical(item)))
    )


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceComparisonRecord(ReferenceTruthRecord):
    answer_key_authority_target: ReferenceAuthorityTarget
    applicability_evidence_refs: tuple[object, ...]
    case_ref: CanonicalChallengeCaseRef
    challenge_key: ChallengeKey
    comparison_id: str
    comparison_method_ref: PinnedReferenceIdentity
    comparison_policy_ref: object
    comparison_version: str
    dependency_disclosures: tuple[DependencyDisclosure, ...]
    evidence_refs: tuple[object, ...]
    outcome: ReferenceComparisonOutcome
    policy_ref: ReferencePolicyRef
    primary_entry_refs: tuple[ReferencePolicyEntryRef, ...]
    primary_run_ref: ReferenceRunRecordRef
    reason: ReferenceComparisonReason
    representation_ref: PinnedReferenceIdentity
    scope_binding: ReferenceScopeBinding
    uncertainty_treatment_ref: PinnedReferenceIdentity
    witness_entry_refs: tuple[ReferencePolicyEntryRef, ...]
    witness_run_ref: ReferenceRunRecordRef
    witness_target: ReferenceWitnessTarget

    OBJECT_KIND: ClassVar[str] = "reference_comparison_record"

    def __post_init__(self) -> None:
        if type(self) is not ReferenceComparisonRecord:
            raise _reject("/record", ReferenceInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        outcome = _model_enum(self.outcome, ReferenceComparisonOutcome, "/outcome")
        reason = _model_enum(self.reason, ReferenceComparisonReason, "/reason")
        if _COMPARISON_OUTCOMES[reason] is not outcome:
            raise _reject("/outcome", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self,
            "answer_key_authority_target",
            _model(
                self.answer_key_authority_target,
                ReferenceAuthorityTarget,
                challenge,
                "/answer_key_authority_target",
            ),
        )
        object.__setattr__(
            self,
            "applicability_evidence_refs",
            _owner_set(
                self.applicability_evidence_refs,
                "applicability_evidence",
                challenge,
                "/applicability_evidence_refs",
            ),
        )
        object.__setattr__(
            self,
            "case_ref",
            _top_ref(self.case_ref, CanonicalChallengeCaseRef, challenge, "/case_ref"),
        )
        object.__setattr__(
            self, "comparison_id", _identifier(self.comparison_id, "/comparison_id")
        )
        object.__setattr__(
            self,
            "comparison_method_ref",
            _identity(
                self.comparison_method_ref,
                ReferenceIdentityKind.COMPARISON_METHOD,
                challenge,
                "/comparison_method_ref",
            ),
        )
        object.__setattr__(
            self,
            "comparison_policy_ref",
            _owner_ref(
                self.comparison_policy_ref,
                "semantic_equivalence",
                challenge,
                "/comparison_policy_ref",
            ),
        )
        object.__setattr__(
            self,
            "comparison_version",
            _version(self.comparison_version, "/comparison_version"),
        )
        disclosures = _model_tuple(
            self.dependency_disclosures,
            DependencyDisclosure,
            challenge,
            "/dependency_disclosures",
            nonempty=True,
        )
        if tuple(item.category for item in disclosures) != tuple(DependencyCategory):
            raise _reject(
                "/dependency_disclosures", ReferenceInputCode.INCOMPLETE_BINDING
            )
        for disclosure in disclosures:
            for evidence_ref in disclosure.evidence_refs:
                _owner_ref(
                    evidence_ref,
                    "provenance",
                    challenge,
                    "/dependency_disclosures/evidence_refs",
                )
        object.__setattr__(self, "dependency_disclosures", disclosures)
        object.__setattr__(
            self,
            "evidence_refs",
            _owner_set(
                self.evidence_refs, "audit_evidence", challenge, "/evidence_refs"
            ),
        )
        object.__setattr__(
            self,
            "policy_ref",
            _b04_ref(self.policy_ref, ReferencePolicyRef, challenge, "/policy_ref"),
        )
        primary = _ref_tuple(
            self.primary_entry_refs,
            ReferencePolicyEntryRef,
            challenge,
            "/primary_entry_refs",
            nonempty=True,
        )
        witness = _ref_tuple(
            self.witness_entry_refs,
            ReferencePolicyEntryRef,
            challenge,
            "/witness_entry_refs",
            nonempty=True,
        )
        if set(primary) & set(witness):
            raise _reject("/witness_entry_refs", ReferenceInputCode.ROLE_MISMATCH)
        object.__setattr__(self, "primary_entry_refs", primary)
        object.__setattr__(self, "witness_entry_refs", witness)
        object.__setattr__(
            self,
            "primary_run_ref",
            _b04_ref(
                self.primary_run_ref,
                ReferenceRunRecordRef,
                challenge,
                "/primary_run_ref",
            ),
        )
        object.__setattr__(
            self,
            "representation_ref",
            _identity(
                self.representation_ref,
                ReferenceIdentityKind.REPRESENTATION,
                challenge,
                "/representation_ref",
            ),
        )
        object.__setattr__(self, "scope_binding", _scope(self.scope_binding, challenge))
        object.__setattr__(
            self,
            "uncertainty_treatment_ref",
            _identity(
                self.uncertainty_treatment_ref,
                ReferenceIdentityKind.UNCERTAINTY_METHOD,
                challenge,
                "/uncertainty_treatment_ref",
            ),
        )
        object.__setattr__(
            self,
            "witness_run_ref",
            _b04_ref(
                self.witness_run_ref,
                ReferenceRunRecordRef,
                challenge,
                "/witness_run_ref",
            ),
        )
        if self.primary_run_ref == self.witness_run_ref:
            raise _reject("/witness_run_ref", ReferenceInputCode.ROLE_MISMATCH)
        witness_target = _model(
            self.witness_target, ReferenceWitnessTarget, challenge, "/witness_target"
        )
        object.__setattr__(self, "witness_target", witness_target)
        direct_primary = self.answer_key_authority_target.expanded_entry_refs
        direct_witness = witness_target.expanded_entry_refs
        if direct_primary and primary != direct_primary:
            raise _reject("/primary_entry_refs", ReferenceInputCode.STALE_BINDING)
        if direct_witness and witness != direct_witness:
            raise _reject("/witness_entry_refs", ReferenceInputCode.STALE_BINDING)
        unresolved_dependence = any(
            item.relation is DependencyRelation.UNDISCLOSED
            or item.relation in (DependencyRelation.SHARED, DependencyRelation.DISTINCT)
            and not item.evidence_refs
            for item in disclosures
        )
        if (
            outcome is not ReferenceComparisonOutcome.COMPARISON_INDETERMINATE
            and unresolved_dependence
        ):
            raise _reject(
                "/dependency_disclosures", ReferenceInputCode.OUTCOME_REASON_MISMATCH
            )


def _model_enum(value: object, expected: type, path: str):
    if type(value) is not expected:
        raise _reject(path, ReferenceInputCode.WRONG_TYPE)
    return value


def _owner_ref(value: object, kind: str, challenge: ChallengeKey, path: str) -> object:
    try:
        copied = require_owner_ref(value, kind)
    except (AttributeError, AuthoringError, TypeError, ValueError):
        raise _reject(path, ReferenceInputCode.WRONG_TYPE) from None
    if (
        type(copied.scope_binding) is not ChallengeScope
        or copied.scope_binding.challenge_key != challenge
    ):
        raise _reject(path, ReferenceInputCode.CROSS_CHALLENGE)
    return copied


def _component_refs(run: ReferenceRunRecord) -> tuple[ReferencePolicyEntryRef, ...]:
    return tuple(item.entry_ref for item in run.component_bindings)


def create_reference_comparison_record(
    *,
    primary_run: ReferenceRunRecord,
    witness_run: ReferenceRunRecord,
    observed_reasons: tuple[ReferenceComparisonReason, ...],
    applicability_evidence_refs: tuple[object, ...],
    comparison_id: str,
    comparison_method_ref: PinnedReferenceIdentity,
    comparison_policy_ref: object,
    comparison_version: str,
    dependency_disclosures: tuple[DependencyDisclosure, ...],
    evidence_refs: tuple[object, ...],
    uncertainty_treatment_ref: PinnedReferenceIdentity,
    witness_target: ReferenceWitnessTarget,
) -> ReferenceComparisonRecord:
    if (
        type(primary_run) is not ReferenceRunRecord
        or type(witness_run) is not ReferenceRunRecord
    ):
        raise _reject("/primary_run_ref", ReferenceInputCode.WRONG_TYPE)
    if primary_run.challenge_key != witness_run.challenge_key:
        raise _reject("/witness_run_ref", ReferenceInputCode.CROSS_CHALLENGE)
    if type(observed_reasons) is not tuple:
        raise _reject("/reason", ReferenceInputCode.WRONG_TYPE)
    if len(observed_reasons) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _reject("/reason", ReferenceInputCode.INVALID_VALUE)
    if any(type(item) is not ReferenceComparisonReason for item in observed_reasons):
        raise _reject("/reason", ReferenceInputCode.WRONG_TYPE)
    if len(set(observed_reasons)) != len(observed_reasons):
        raise _reject("/reason", ReferenceInputCode.DUPLICATE_IDENTITY)
    if type(dependency_disclosures) is not tuple:
        raise _reject("/dependency_disclosures", ReferenceInputCode.WRONG_TYPE)
    if len(dependency_disclosures) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _reject("/dependency_disclosures", ReferenceInputCode.INVALID_VALUE)
    if any(type(item) is not DependencyDisclosure for item in dependency_disclosures):
        raise _reject("/dependency_disclosures", ReferenceInputCode.WRONG_TYPE)
    checked_witness_target = _model(
        witness_target,
        ReferenceWitnessTarget,
        primary_run.challenge_key,
        "/witness_target",
    )
    if (
        primary_run.authority_function is not ReferenceAuthorityFunction.PRIMARY
        or witness_run.authority_function
        is not ReferenceAuthorityFunction.CORROBORATING_WITNESS
    ):
        raise _reject("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
    facts = set(observed_reasons)
    identity_mismatch = (
        primary_run.case_ref != witness_run.case_ref
        or primary_run.policy_ref != witness_run.policy_ref
        or primary_run.answer_key_authority_target
        != witness_run.answer_key_authority_target
        or primary_run.representation_ref != witness_run.representation_ref
        or primary_run.scope_binding != witness_run.scope_binding
        or witness_run.execution_target.value != checked_witness_target
    )
    if identity_mismatch:
        facts.add(ReferenceComparisonReason.COMPARISON_INPUT_IDENTITY_MISMATCH)
    if (
        primary_run.outcome is not ReferenceRunOutcome.SUPPORTED
        or witness_run.outcome is not ReferenceRunOutcome.SUPPORTED
    ):
        facts.add(ReferenceComparisonReason.PRIMARY_OR_WITNESS_NOT_SUPPORTED)
    if (
        primary_run.applicability_assessment.status
        is not witness_run.applicability_assessment.status
        or primary_run.applicability_assessment.support_boundary_ref
        != witness_run.applicability_assessment.support_boundary_ref
    ):
        facts.add(ReferenceComparisonReason.COMPARISON_APPLICABILITY_MISMATCH)
    if (
        primary_run.uncertainty_binding.status is not UncertaintyStatus.RESOLVED
        or witness_run.uncertainty_binding.status is not UncertaintyStatus.RESOLVED
    ):
        facts.add(ReferenceComparisonReason.COMPARISON_UNCERTAINTY_UNRESOLVED)
    if any(
        item.relation is DependencyRelation.UNDISCLOSED
        or item.relation in (DependencyRelation.SHARED, DependencyRelation.DISTINCT)
        and not item.evidence_refs
        for item in dependency_disclosures
    ):
        facts.add(ReferenceComparisonReason.COMPARISON_DEPENDENCE_UNRESOLVED)
    outcome, reason = select_comparison_terminal(tuple(facts))
    primary_entries = _component_refs(primary_run)
    witness_entries = _component_refs(witness_run)
    if (
        not primary_entries
        or not witness_entries
        or set(primary_entries) & set(witness_entries)
    ):
        raise _reject("/witness_entry_refs", ReferenceInputCode.ROLE_MISMATCH)
    return ReferenceComparisonRecord(
        answer_key_authority_target=primary_run.answer_key_authority_target,
        applicability_evidence_refs=applicability_evidence_refs,
        case_ref=primary_run.case_ref,
        challenge_key=primary_run.challenge_key,
        comparison_id=comparison_id,
        comparison_method_ref=comparison_method_ref,
        comparison_policy_ref=comparison_policy_ref,
        comparison_version=comparison_version,
        dependency_disclosures=dependency_disclosures,
        evidence_refs=evidence_refs,
        outcome=outcome,
        policy_ref=primary_run.policy_ref,
        primary_entry_refs=primary_entries,
        primary_run_ref=primary_run.to_ref(),
        reason=reason,
        representation_ref=primary_run.representation_ref,
        scope_binding=primary_run.scope_binding,
        uncertainty_treatment_ref=uncertainty_treatment_ref,
        witness_entry_refs=witness_entries,
        witness_run_ref=witness_run.to_ref(),
        witness_target=checked_witness_target,
    )


__all__ = [
    "COMPARISON_REASON_PRECEDENCE",
    "ReferenceComparisonRecord",
    "create_reference_comparison_record",
    "select_comparison_terminal",
]
