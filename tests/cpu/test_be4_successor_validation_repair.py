"""Regressions for the bounded B-E4 successor validation repair."""

from __future__ import annotations

from dataclasses import replace
from enum import Enum

import pytest

from carbon.evaluation.errors import ReferenceInputCode
from carbon.gauntlet import (
    AgentProfile,
    ExperimentalArm,
    GauntletPreflightError,
    GauntletPreregistration,
    GauntletRecord,
    IntegrityCase,
    IntegrityDisposition,
    IntegrityObservation,
    MatchedBudget,
    OwnerRatification,
    RatifyingOwner,
    RunIdentity,
    validate_experiment_matrix,
    validate_integrity_matrix,
)
from carbon.qualification.errors import DossierInputCode
from carbon.registry import ChallengeKey
from carbon.reproducibility.errors import ReproducibilityErrorCode
from carbon.research import (
    PriorChannel,
    PriorPackRef,
    ResearchServiceErrorCode,
)
from carbon.research import (
    TestOnlyPriorAuthorizationReceiptRef as AuthorizationReceiptRef,
)
from carbon.resource_policy.errors import ResourcePolicyInputCode

_DIGEST = "sha256:" + "a" * 64


class _UnrelatedOutcome(str, Enum):
    VALUE = "VALUE"


def _declared_preregistration() -> GauntletPreregistration:
    draft = GauntletPreregistration(
        None,
        "profiles",
        "budgets",
        "estimand",
        "effect-floor",
        "decision-rule",
        "diversity-metric",
        "diversity-floor",
        "leakage-limit",
        (),
    )
    digest = draft.computed_design_digest
    assert digest is not None
    return replace(
        draft,
        design_digest=digest,
        ratifications=tuple(
            OwnerRatification(owner, digest, f"fixture-{owner.value.lower()}")
            for owner in RatifyingOwner
        ),
    )


def _pins(
    *, channel: PriorChannel = PriorChannel.TEST_ONLY_FIXTURE
) -> tuple[PriorPackRef, AuthorizationReceiptRef]:
    key = ChallengeKey("be4_fixture", "1.0")
    return (
        PriorPackRef(key, channel, 1, _DIGEST),
        AuthorizationReceiptRef(key, "fixture_authorization", _DIGEST),
    )


def _runs() -> tuple[RunIdentity, ...]:
    pack, receipt = _pins()
    return tuple(
        RunIdentity(
            profile,
            arm,
            replicate,
            pack if arm is ExperimentalArm.V2_TEST_ONLY_PRIOR else None,
            receipt if arm is ExperimentalArm.V2_TEST_ONLY_PRIOR else None,
        )
        for profile in AgentProfile
        for arm in ExperimentalArm
        for replicate in range(2)
    )


def _budgets() -> tuple[MatchedBudget, ...]:
    return tuple(MatchedBudget(profile, 1.0, 1.0, 1) for profile in AgentProfile)


def test_design_digest_is_bound_to_preregistered_content() -> None:
    preregistration = _declared_preregistration()
    assert preregistration.is_complete
    assert preregistration.is_syntactically_complete
    assert preregistration.has_declared_ratifications
    assert not preregistration.is_verified_owner_ratified
    changed = replace(preregistration, utility_estimand="changed-estimand")
    assert not changed.is_complete
    assert "design_digest:content_mismatch" in changed.missing_inputs


def test_duplicate_or_relabelled_ratifications_are_not_declared_complete() -> None:
    preregistration = _declared_preregistration()
    duplicate = replace(
        preregistration,
        ratifications=(
            *preregistration.ratifications,
            preregistration.ratifications[0],
        ),
    )
    assert not duplicate.has_declared_ratifications
    assert "ratification:duplicate_owner" in duplicate.missing_ratifications

    relabelled = replace(
        preregistration,
        ratifications=(
            replace(preregistration.ratifications[0], design_digest=_DIGEST),
            *preregistration.ratifications[1:],
        ),
    )
    assert not relabelled.has_declared_ratifications
    assert "ratification:exact_design_digest" in relabelled.missing_ratifications


def test_direct_qualifying_record_is_unavailable_without_verified_integration() -> None:
    with pytest.raises(ValueError, match="qualifying execution recording unavailable"):
        GauntletRecord(
            _declared_preregistration(),
            (),
            (),
            (),
            (),
            qualifying_execution=True,
        )


def test_v2_run_rejects_public_channel_and_cross_challenge_receipt() -> None:
    public_pack, receipt = _pins(channel=PriorChannel.PUBLIC)
    with pytest.raises(ValueError, match="TEST_ONLY_FIXTURE"):
        RunIdentity(
            AgentProfile.PLANNER,
            ExperimentalArm.V2_TEST_ONLY_PRIOR,
            0,
            public_pack,
            receipt,
        )

    pack, _ = _pins()
    other_receipt = replace(receipt, challenge_key=ChallengeKey("other_fixture", "1.0"))
    with pytest.raises(ValueError, match="one Challenge"):
        RunIdentity(
            AgentProfile.PLANNER,
            ExperimentalArm.V2_TEST_ONLY_PRIOR,
            0,
            pack,
            other_receipt,
        )


def test_non_v2_run_requires_both_pins_to_be_exactly_none() -> None:
    with pytest.raises(ValueError, match="exactly None"):
        RunIdentity(
            AgentProfile.PLANNER,
            ExperimentalArm.NO_PRIOR,
            0,
            object(),  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
        )


def test_v2_run_revalidates_hostile_nested_pin_values_before_hashing() -> None:
    forged = object.__new__(PriorPackRef)
    object.__setattr__(forged, "challenge_key", ChallengeKey("be4_fixture", "1.0"))
    object.__setattr__(forged, "channel", "TEST_ONLY_FIXTURE")
    object.__setattr__(forged, "publication_sequence", 1)
    object.__setattr__(forged, "content_hash", _DIGEST)
    _, receipt = _pins()
    with pytest.raises(ValueError, match="structurally invalid"):
        RunIdentity(
            AgentProfile.PLANNER,
            ExperimentalArm.V2_TEST_ONLY_PRIOR,
            0,
            forged,
            receipt,
        )


def test_matrix_reconstructs_mutated_nested_pins_before_hashing() -> None:
    runs = list(_runs())
    forged = object.__new__(PriorPackRef)
    object.__setattr__(forged, "challenge_key", ChallengeKey("be4_fixture", "1.0"))
    object.__setattr__(forged, "channel", [PriorChannel.TEST_ONLY_FIXTURE])
    object.__setattr__(forged, "publication_sequence", 1)
    object.__setattr__(forged, "content_hash", _DIGEST)
    target = next(run for run in runs if run.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR)
    object.__setattr__(target, "prior_pack_ref", forged)
    with pytest.raises(GauntletPreflightError, match="nested reconstruction"):
        validate_experiment_matrix(
            preregistration=_declared_preregistration(),
            budgets=_budgets(),
            runs=tuple(runs),
        )


def test_matrix_rejects_changed_receipt_pin_across_replicates() -> None:
    runs = list(_runs())
    receipt = runs[-1].test_only_authorization_ref
    assert receipt is not None
    runs[-1] = replace(
        runs[-1],
        test_only_authorization_ref=replace(
            receipt, authorization_id="other_fixture_authorization"
        ),
    )
    with pytest.raises(GauntletPreflightError, match="freeze one exact"):
        validate_experiment_matrix(
            preregistration=_declared_preregistration(),
            budgets=_budgets(),
            runs=tuple(runs),
        )


@pytest.mark.parametrize("outcome", (AgentProfile.PLANNER, _UnrelatedOutcome.VALUE))
def test_integrity_observation_rejects_unrelated_enum(outcome: Enum) -> None:
    with pytest.raises(TypeError, match="registered protocol outcome"):
        IntegrityObservation(
            IntegrityCase.PROTECTED_CASE_INFERENCE,
            IntegrityDisposition.TYPED_REJECTION,
            outcome,
        )


def test_integrity_case_rejects_wrong_domain_outcome() -> None:
    with pytest.raises(ValueError, match="not applicable"):
        IntegrityObservation(
            IntegrityCase.DUPLICATE_LINEAGE,
            IntegrityDisposition.TYPED_REJECTION,
            ResearchServiceErrorCode.DISCLOSURE_REJECTED,
        )


def test_integrity_matrix_accepts_case_specific_existing_outcomes() -> None:
    outcomes = {
        IntegrityCase.DUPLICATE_LINEAGE: ReproducibilityErrorCode.DUPLICATE_IDENTITY,
        IntegrityCase.TIMING_RESOURCE_SURFACE: ResourcePolicyInputCode.LIMIT_NOT_BOUND,
        IntegrityCase.PRIOR_POISONING: ResearchServiceErrorCode.TEST_ONLY_AUTHORITY_INVALID,
        IntegrityCase.DUPLICATE_EVIDENCE: ReproducibilityErrorCode.DUPLICATE_IDENTITY,
        IntegrityCase.RAW_STRING: ResearchServiceErrorCode.REQUEST_TYPE_INVALID,
        IntegrityCase.STRUCTURAL_LABEL_MISREPRESENTATION: DossierInputCode.ROLE_CONFUSION,
        IntegrityCase.EVIDENCE_ROLE_SUBSTITUTION: DossierInputCode.ROLE_CONFUSION,
        IntegrityCase.REFERENCE_CANDIDATE_FAILURE_COLLAPSE: ReferenceInputCode.OUTCOME_REASON_MISMATCH,
        IntegrityCase.PARTIAL_PROXY_SUPERIOR: DossierInputCode.PLACEHOLDER_EVIDENCE,
        IntegrityCase.LEARNED_COMPONENT_WRONG_ROLE: DossierInputCode.ROLE_CONFUSION,
        IntegrityCase.LEARNED_COMPONENT_INCOMPATIBLE_IO: DossierInputCode.SLOT_MISMATCH,
        IntegrityCase.LEARNED_COMPONENT_STALE_PIN: DossierInputCode.VERSION_MISMATCH,
        IntegrityCase.LEARNED_COMPONENT_SIDE_EFFECT: ReproducibilityErrorCode.PROCEDURE_INVALID,
    }
    observations = tuple(
        IntegrityObservation(
            case,
            IntegrityDisposition.TYPED_REJECTION,
            outcomes.get(case, ResearchServiceErrorCode.DISCLOSURE_REJECTED),
        )
        for case in IntegrityCase
    )
    validate_integrity_matrix(observations)

    with pytest.raises(GauntletPreflightError, match="incomplete"):
        validate_integrity_matrix(observations[:-1] + (observations[0],))
