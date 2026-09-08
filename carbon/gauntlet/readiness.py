"""Fail-closed B-E4 shadow, attack, execution, and ratification readiness.

Everything in this module is fixture engineering or design-analysis evidence.
It cannot verify a human approval, authorize a qualifying execution, or create
scientific, security, privacy, production, or LIVE authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from enum import Enum

from carbon.qualification.errors import DossierInputCode
from carbon.registry import ChallengeKey
from carbon.research.errors import ResearchServiceErrorCode
from carbon.resource_policy.errors import ResourcePolicyInputCode

from .design import PROTECTED_TARGETS, DesignAnalysisClassification
from .model import (
    AgentProfile,
    EngineeringObservation,
    ExperimentalArm,
    GauntletPreregistration,
    IntegrityCase,
    IntegrityDisposition,
    IntegrityObservation,
    RatifyingOwner,
    RunIdentity,
)

READINESS_AUTHORITY_CEILING = "FIXTURE_ONLY_DESIGN_ANALYSIS_NOT_QUALIFYING_EVIDENCE"
SHADOW_ESTIMATOR_ID = "cross_fitted_shadow_plus_transcript_log_loss/v1"
SHADOW_FOLD_POLICY = "profile_stratified_whole_transcript_digest/v1"
SHADOW_FEATURE_POLICY = "frozen_public_physics_plus_canonical_transcript/v1"
SHADOW_CLIPPING_POLICY = "epsilon_1_over_2_n_train_plus_1_renormalized/v1"

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SHADOW_DOMAIN = b"carbon.be4.shadow-campaign.v1\x00"
_SHADOW_ESTIMATE_DOMAIN = b"carbon.be4.shadow-estimate.v1\x00"
_ATTACK_CAMPAIGN_DOMAIN = b"carbon.be4.attack-campaign.v1\x00"
_ATTACK_RECEIPT_DOMAIN = b"carbon.be4.attack-attempt.v1\x00"
_EXECUTION_DRAFT_DOMAIN = b"carbon.be4.execution-evidence-draft.v1\x00"
_RECEIPT_TOKEN = object()
_SIGNED_LAMBDA_TOKEN = object()
_SHADOW_TARGET_TOKEN = object()
_SHADOW_ESTIMATE_TOKEN = object()
_MAX_SHADOW_OBSERVATIONS = 10_000_000


class ReadinessError(ValueError):
    """A B-E4 readiness object is malformed or crosses an authority seam."""


class RatificationUnavailableError(ReadinessError):
    """Trusted owner ratification is not available in current Carbon."""


def _text(value: object, name: str, *, maximum: int = 4096) -> str:
    if type(value) is not str or not value:
        raise ReadinessError(f"{name} must be bounded non-empty text")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ReadinessError(f"{name} must be valid UTF-8 text") from exc
    if len(encoded) > maximum:
        raise ReadinessError(f"{name} must be bounded non-empty text")
    return value


def _digest(value: object, name: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ReadinessError(f"{name} must be a tagged SHA-256 digest")
    return value


def _challenge(value: object) -> ChallengeKey:
    if type(value) is not ChallengeKey:
        raise ReadinessError("challenge_key must be an exact ChallengeKey")
    try:
        return ChallengeKey(value.challenge_id, value.version)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ReadinessError("challenge_key is structurally invalid") from exc


def _canonical_digest(domain: bytes, payload: object) -> str:
    try:
        encoded = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ReadinessError("readiness evidence is not canonically encodable") from exc
    return "sha256:" + hashlib.sha256(domain + encoded).hexdigest()


def _challenge_payload(value: ChallengeKey) -> dict[str, str]:
    return {"challenge_id": value.challenge_id, "version": value.version}


def _float(value: float) -> str:
    return value.hex()


def _optional_float(value: float | None) -> str | None:
    return None if value is None else _float(value)


@dataclass(frozen=True, slots=True)
class ShadowTargetDefinition:
    """One evaluator-held target definition, not a realized target value."""

    target: str
    definition_id: str
    class_labels: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            type(self) is not ShadowTargetDefinition
            or self.target not in PROTECTED_TARGETS
        ):
            raise ReadinessError("shadow target is not registered")
        _text(self.definition_id, "definition_id")
        if (
            type(self.class_labels) is not tuple
            or len(self.class_labels) < 2
            or len(self.class_labels) > 64
            or any(type(item) is not str or not item for item in self.class_labels)
            or len(set(self.class_labels)) != len(self.class_labels)
        ):
            raise ReadinessError("shadow target labels must be unique bounded text")
        for item in self.class_labels:
            _text(item, "class_label", maximum=256)


@dataclass(frozen=True, slots=True)
class ShadowCampaignRef:
    challenge_key: ChallengeKey
    design_digest: str
    campaign_id: str
    campaign_version: str
    content_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        _digest(self.design_digest, "design_digest")
        _text(self.campaign_id, "campaign_id")
        _text(self.campaign_version, "campaign_version")
        _digest(self.content_digest, "content_digest")


@dataclass(frozen=True, slots=True, repr=False)
class ShadowCampaignRegistration:
    """Exact fixture-only shadow contract; realized cases remain elsewhere."""

    challenge_key: ChallengeKey
    design_digest: str
    campaign_id: str
    campaign_version: str
    distribution_digest: str
    shadow_sampler_digest: str
    shadow_physics_feature_digest: str
    transcript_feature_digest: str
    target_definitions: tuple[ShadowTargetDefinition, ...]
    fold_count: int = 5
    estimator_id: str = SHADOW_ESTIMATOR_ID
    fold_policy: str = SHADOW_FOLD_POLICY
    feature_policy: str = SHADOW_FEATURE_POLICY
    clipping_policy: str = SHADOW_CLIPPING_POLICY
    fixture_only: bool = True

    def __post_init__(self) -> None:
        if type(self) is not ShadowCampaignRegistration:
            raise ReadinessError("shadow campaign subclasses are rejected")
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        for value, name in (
            (self.design_digest, "design_digest"),
            (self.distribution_digest, "distribution_digest"),
            (self.shadow_sampler_digest, "shadow_sampler_digest"),
            (self.shadow_physics_feature_digest, "shadow_physics_feature_digest"),
            (self.transcript_feature_digest, "transcript_feature_digest"),
        ):
            _digest(value, name)
        for value, name in (
            (self.campaign_id, "campaign_id"),
            (self.campaign_version, "campaign_version"),
            (self.estimator_id, "estimator_id"),
            (self.fold_policy, "fold_policy"),
            (self.feature_policy, "feature_policy"),
            (self.clipping_policy, "clipping_policy"),
        ):
            _text(value, name)
        if (
            self.estimator_id != SHADOW_ESTIMATOR_ID
            or self.fold_policy != SHADOW_FOLD_POLICY
            or self.feature_policy != SHADOW_FEATURE_POLICY
            or self.clipping_policy != SHADOW_CLIPPING_POLICY
        ):
            raise ReadinessError(
                "shadow analysis policy must use the frozen v1 contract"
            )
        if type(self.fold_count) is not int or self.fold_count != 5:
            raise ReadinessError(
                "shadow fold_count must use the frozen five-fold design"
            )
        if self.fixture_only is not True:
            raise ReadinessError("shadow campaigns are fixture-only")
        if type(self.target_definitions) is not tuple or any(
            type(item) is not ShadowTargetDefinition for item in self.target_definitions
        ):
            raise ReadinessError("shadow target definitions must use the exact order")
        try:
            targets = tuple(
                ShadowTargetDefinition(
                    item.target,
                    item.definition_id,
                    tuple(item.class_labels),
                )
                for item in self.target_definitions
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ReadinessError("shadow target definition is invalid") from exc
        if tuple(item.target for item in targets) != PROTECTED_TARGETS:
            raise ReadinessError("shadow target definitions must use the exact order")
        object.__setattr__(self, "target_definitions", targets)

    def __repr__(self) -> str:
        return "ShadowCampaignRegistration(<evaluator-held>)"

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("shadow campaign registrations cannot be serialized")

    @property
    def authority_ceiling(self) -> str:
        return READINESS_AUTHORITY_CEILING

    @property
    def content_digest(self) -> str:
        checked = _canonical_shadow_campaign(self)
        return _canonical_digest(_SHADOW_DOMAIN, _shadow_campaign_payload(checked))

    def to_ref(self) -> ShadowCampaignRef:
        return ShadowCampaignRef(
            self.challenge_key,
            self.design_digest,
            self.campaign_id,
            self.campaign_version,
            self.content_digest,
        )


def _canonical_shadow_campaign(value: object) -> ShadowCampaignRegistration:
    if type(value) is not ShadowCampaignRegistration:
        raise TypeError("exact shadow campaign registration is required")
    try:
        return ShadowCampaignRegistration(
            value.challenge_key,
            value.design_digest,
            value.campaign_id,
            value.campaign_version,
            value.distribution_digest,
            value.shadow_sampler_digest,
            value.shadow_physics_feature_digest,
            value.transcript_feature_digest,
            value.target_definitions,
            value.fold_count,
            value.estimator_id,
            value.fold_policy,
            value.feature_policy,
            value.clipping_policy,
            value.fixture_only,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ReadinessError("shadow campaign is structurally invalid") from exc


def _shadow_campaign_payload(value: ShadowCampaignRegistration) -> dict[str, object]:
    return {
        "authority_ceiling": READINESS_AUTHORITY_CEILING,
        "campaign_id": value.campaign_id,
        "campaign_version": value.campaign_version,
        "challenge_key": _challenge_payload(value.challenge_key),
        "clipping_policy": value.clipping_policy,
        "design_digest": value.design_digest,
        "distribution_digest": value.distribution_digest,
        "estimator_id": value.estimator_id,
        "feature_policy": value.feature_policy,
        "fixture_only": value.fixture_only,
        "fold_count": value.fold_count,
        "fold_policy": value.fold_policy,
        "shadow_physics_feature_digest": value.shadow_physics_feature_digest,
        "shadow_sampler_digest": value.shadow_sampler_digest,
        "target_definitions": [
            {
                "class_labels": list(item.class_labels),
                "definition_id": item.definition_id,
                "target": item.target,
            }
            for item in value.target_definitions
        ],
        "transcript_feature_digest": value.transcript_feature_digest,
    }


def shadow_fold_index(
    registration: ShadowCampaignRegistration,
    *,
    profile: AgentProfile,
    transcript_cluster_digest: str,
) -> int:
    """Assign a whole transcript cluster deterministically to one fold."""

    if type(registration) is not ShadowCampaignRegistration:
        raise TypeError("exact shadow campaign registration is required")
    registration = _canonical_shadow_campaign(registration)
    if type(profile) is not AgentProfile:
        raise TypeError("exact agent profile is required")
    _digest(transcript_cluster_digest, "transcript_cluster_digest")
    payload = (
        b"carbon.be4.shadow-fold.v1\x00"
        + registration.design_digest.encode("ascii")
        + b"\x00"
        + profile.value.encode("ascii")
        + b"\x00"
        + transcript_cluster_digest.encode("ascii")
    )
    return (
        int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
        % registration.fold_count
    )


def clip_and_renormalize_probabilities(
    probabilities: tuple[float, ...], *, training_count: int
) -> tuple[float, ...]:
    """Apply the frozen per-training-fold clipping rule."""

    if (
        type(probabilities) is not tuple
        or len(probabilities) < 2
        or len(probabilities) > 64
        or any(
            type(value) is not float
            or not math.isfinite(value)
            or not 0.0 <= value <= 1.0
            for value in probabilities
        )
        or not math.isclose(sum(probabilities), 1.0, rel_tol=0.0, abs_tol=1e-12)
    ):
        raise ReadinessError("probabilities must be an exact finite simplex")
    if (
        type(training_count) is not int
        or training_count < 1
        or training_count > _MAX_SHADOW_OBSERVATIONS
    ):
        raise ReadinessError("training_count must be a bounded positive integer")
    epsilon = 1.0 / (2.0 * (training_count + 1.0))
    clipped = tuple(min(1.0 - epsilon, max(epsilon, value)) for value in probabilities)
    total = sum(clipped)
    return tuple(value / total for value in clipped)


class SignedLambdaState(str, Enum):
    ESTIMATED = "DESIGN_ANALYSIS_ONLY_ESTIMATED"
    INDETERMINATE_DENOMINATOR = "DESIGN_ANALYSIS_ONLY_INDETERMINATE_DENOMINATOR"


@dataclass(frozen=True, slots=True, init=False)
class SignedLambdaEstimate:
    state: SignedLambdaState
    shadow_only_cross_entropy: float
    shadow_plus_transcript_cross_entropy: float
    signed_lambda: float | None

    def __init__(
        self,
        shadow_only_cross_entropy: float,
        shadow_plus_transcript_cross_entropy: float,
        *,
        force_indeterminate: bool = False,
        _factory_token: object,
    ) -> None:
        if (
            type(self) is not SignedLambdaEstimate
            or _factory_token is not _SIGNED_LAMBDA_TOKEN
        ):
            raise TypeError("signed Lambda estimates require the mechanical estimator")
        if type(shadow_only_cross_entropy) is not float:
            raise TypeError("shadow-only cross entropy must be exact float")
        if (
            type(shadow_plus_transcript_cross_entropy) is not float
            or not math.isfinite(shadow_plus_transcript_cross_entropy)
            or shadow_plus_transcript_cross_entropy < 0.0
        ):
            raise ReadinessError("transcript cross entropy must be non-negative")
        if type(force_indeterminate) is not bool:
            raise TypeError("force_indeterminate must be exact bool")
        denominator_valid = (
            math.isfinite(shadow_only_cross_entropy) and shadow_only_cross_entropy > 0.0
        )
        state = (
            SignedLambdaState.ESTIMATED
            if denominator_valid and not force_indeterminate
            else SignedLambdaState.INDETERMINATE_DENOMINATOR
        )
        statistic = (
            (shadow_only_cross_entropy - shadow_plus_transcript_cross_entropy)
            / shadow_only_cross_entropy
            if state is SignedLambdaState.ESTIMATED
            else None
        )
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "shadow_only_cross_entropy", shadow_only_cross_entropy)
        object.__setattr__(
            self,
            "shadow_plus_transcript_cross_entropy",
            shadow_plus_transcript_cross_entropy,
        )
        object.__setattr__(self, "signed_lambda", statistic)

    @property
    def authority_ceiling(self) -> str:
        return READINESS_AUTHORITY_CEILING


def estimate_signed_lambda(
    *, shadow_only_cross_entropy: float, shadow_plus_transcript_cross_entropy: float
) -> SignedLambdaEstimate:
    """Compute proposed signed Lambda, failing invalid denominators closed."""

    if type(shadow_only_cross_entropy) is not float:
        raise TypeError("shadow-only cross entropy must be exact float")
    if (
        type(shadow_plus_transcript_cross_entropy) is not float
        or not math.isfinite(shadow_plus_transcript_cross_entropy)
        or shadow_plus_transcript_cross_entropy < 0.0
    ):
        raise ReadinessError("transcript cross entropy must be non-negative")
    if not math.isfinite(shadow_only_cross_entropy) or shadow_only_cross_entropy <= 0.0:
        return SignedLambdaEstimate(
            shadow_only_cross_entropy,
            shadow_plus_transcript_cross_entropy,
            _factory_token=_SIGNED_LAMBDA_TOKEN,
        )
    return SignedLambdaEstimate(
        shadow_only_cross_entropy,
        shadow_plus_transcript_cross_entropy,
        _factory_token=_SIGNED_LAMBDA_TOKEN,
    )


@dataclass(frozen=True, slots=True, repr=False)
class ShadowFoldObservation:
    """Evaluator-only cross-fit prediction record; no realized case is exposed."""

    target: str
    profile: AgentProfile
    transcript_cluster_digest: str
    fold_index: int
    training_count: int
    observed_label_index: int
    shadow_only_probabilities: tuple[float, ...]
    shadow_plus_transcript_probabilities: tuple[float, ...]

    def __post_init__(self) -> None:
        if (
            self.target not in PROTECTED_TARGETS
            or type(self.profile) is not AgentProfile
        ):
            raise ReadinessError("shadow fold observation identity is invalid")
        _digest(self.transcript_cluster_digest, "transcript_cluster_digest")
        if type(self.fold_index) is not int or self.fold_index < 0:
            raise ReadinessError("fold_index must be a non-negative integer")
        if (
            type(self.training_count) is not int
            or self.training_count < 1
            or self.training_count > _MAX_SHADOW_OBSERVATIONS
        ):
            raise ReadinessError("training_count must be bounded and positive")
        if type(self.observed_label_index) is not int or self.observed_label_index < 0:
            raise ReadinessError("observed_label_index must be non-negative")
        for values in (
            self.shadow_only_probabilities,
            self.shadow_plus_transcript_probabilities,
        ):
            normalized = clip_and_renormalize_probabilities(
                values, training_count=self.training_count
            )
            if self.observed_label_index >= len(normalized):
                raise ReadinessError("observed label is outside the registered classes")

    def __repr__(self) -> str:
        return "ShadowFoldObservation(<evaluator-held>)"

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("shadow fold observations cannot be serialized")


@dataclass(frozen=True, slots=True, init=False)
class ShadowTargetEstimate:
    target: str
    fold_estimates: tuple[SignedLambdaEstimate, ...]
    fold_observation_counts: tuple[int, ...]
    aggregate: SignedLambdaEstimate

    def __init__(
        self,
        target: str,
        fold_estimates: tuple[SignedLambdaEstimate, ...],
        fold_observation_counts: tuple[int, ...],
        *,
        _factory_token: object,
    ) -> None:
        if (
            type(self) is not ShadowTargetEstimate
            or _factory_token is not _SHADOW_TARGET_TOKEN
        ):
            raise TypeError("shadow target estimates require the campaign estimator")
        if target not in PROTECTED_TARGETS:
            raise ReadinessError("shadow target estimate is unregistered")
        if (
            type(fold_estimates) is not tuple
            or not fold_estimates
            or any(type(item) is not SignedLambdaEstimate for item in fold_estimates)
        ):
            raise TypeError("fold estimates require exact signed Lambda records")
        if (
            type(fold_observation_counts) is not tuple
            or len(fold_observation_counts) != len(fold_estimates)
            or any(
                type(item) is not int or item < 1 for item in fold_observation_counts
            )
        ):
            raise ReadinessError("fold observation counts must bind every fold")
        total = sum(fold_observation_counts)
        base = (
            sum(
                item.shadow_only_cross_entropy * count
                for item, count in zip(fold_estimates, fold_observation_counts)
            )
            / total
        )
        full = (
            sum(
                item.shadow_plus_transcript_cross_entropy * count
                for item, count in zip(fold_estimates, fold_observation_counts)
            )
            / total
        )
        aggregate = SignedLambdaEstimate(
            base,
            full,
            force_indeterminate=any(
                item.state is SignedLambdaState.INDETERMINATE_DENOMINATOR
                for item in fold_estimates
            ),
            _factory_token=_SIGNED_LAMBDA_TOKEN,
        )
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "fold_estimates", fold_estimates)
        object.__setattr__(self, "fold_observation_counts", fold_observation_counts)
        object.__setattr__(self, "aggregate", aggregate)


@dataclass(frozen=True, slots=True, init=False)
class ShadowCampaignEstimate:
    campaign_ref: ShadowCampaignRef
    targets: tuple[ShadowTargetEstimate, ...]

    def __init__(
        self,
        campaign_ref: ShadowCampaignRef,
        targets: tuple[ShadowTargetEstimate, ...],
        *,
        _factory_token: object,
    ) -> None:
        if (
            type(self) is not ShadowCampaignEstimate
            or _factory_token is not _SHADOW_ESTIMATE_TOKEN
        ):
            raise TypeError("shadow campaign estimates require the campaign estimator")
        if type(campaign_ref) is not ShadowCampaignRef:
            raise TypeError("exact shadow campaign ref is required")
        if (
            type(targets) is not tuple
            or any(type(item) is not ShadowTargetEstimate for item in targets)
            or tuple(item.target for item in targets) != PROTECTED_TARGETS
        ):
            raise ReadinessError("shadow estimate must contain the exact four targets")
        object.__setattr__(self, "campaign_ref", campaign_ref)
        object.__setattr__(self, "targets", targets)

    @property
    def authority_ceiling(self) -> str:
        return READINESS_AUTHORITY_CEILING

    @property
    def content_digest(self) -> str:
        payload = {
            "authority_ceiling": self.authority_ceiling,
            "campaign_digest": self.campaign_ref.content_digest,
            "targets": [
                {
                    "aggregate": _lambda_payload(item.aggregate),
                    "fold_observation_counts": list(item.fold_observation_counts),
                    "folds": [_lambda_payload(fold) for fold in item.fold_estimates],
                    "target": item.target,
                }
                for item in self.targets
            ],
        }
        return _canonical_digest(_SHADOW_ESTIMATE_DOMAIN, payload)

    def to_ref(self) -> ShadowCampaignEstimateRef:
        return ShadowCampaignEstimateRef(self.campaign_ref, self.content_digest)


@dataclass(frozen=True, slots=True)
class ShadowCampaignEstimateRef:
    campaign_ref: ShadowCampaignRef
    content_digest: str

    def __post_init__(self) -> None:
        if type(self.campaign_ref) is not ShadowCampaignRef:
            raise TypeError("exact shadow campaign ref is required")
        _digest(self.content_digest, "content_digest")


def _lambda_payload(value: SignedLambdaEstimate) -> dict[str, object]:
    return {
        "shadow_only_cross_entropy": _float(value.shadow_only_cross_entropy),
        "shadow_plus_transcript_cross_entropy": _float(
            value.shadow_plus_transcript_cross_entropy
        ),
        "signed_lambda": (
            None if value.signed_lambda is None else _float(value.signed_lambda)
        ),
        "state": value.state.value,
    }


def estimate_shadow_campaign(
    registration: ShadowCampaignRegistration,
    observations: tuple[ShadowFoldObservation, ...],
) -> ShadowCampaignEstimate:
    """Evaluate exact cross-fit records without producing a leakage verdict."""

    if type(registration) is not ShadowCampaignRegistration:
        raise TypeError("exact shadow campaign registration is required")
    registration = _canonical_shadow_campaign(registration)
    if type(observations) is not tuple or any(
        type(item) is not ShadowFoldObservation for item in observations
    ):
        raise TypeError("shadow observations require exact evaluator-held records")
    results: list[ShadowTargetEstimate] = []
    definitions = {item.target: item for item in registration.target_definitions}
    for target in PROTECTED_TARGETS:
        selected = tuple(item for item in observations if item.target == target)
        if not selected or len(selected) > _MAX_SHADOW_OBSERVATIONS:
            raise ReadinessError("every registered shadow target requires observations")
        if len({item.transcript_cluster_digest for item in selected}) != len(selected):
            raise ReadinessError("shadow transcript clusters must be unique per target")
        expected_classes = len(definitions[target].class_labels)
        fold_losses: dict[int, list[tuple[float, float]]] = {
            index: [] for index in range(registration.fold_count)
        }
        fold_observation_counts = {
            index: sum(item.fold_index == index for item in selected)
            for index in range(registration.fold_count)
        }
        for item in selected:
            if (
                len(item.shadow_only_probabilities) != expected_classes
                or len(item.shadow_plus_transcript_probabilities) != expected_classes
                or item.fold_index >= registration.fold_count
                or item.fold_index
                != shadow_fold_index(
                    registration,
                    profile=item.profile,
                    transcript_cluster_digest=item.transcript_cluster_digest,
                )
            ):
                raise ReadinessError(
                    "shadow observation contradicts the frozen campaign"
                )
            expected_training_count = (
                len(selected) - fold_observation_counts[item.fold_index]
            )
            if item.training_count != expected_training_count:
                raise ReadinessError(
                    "training_count must be derived from the held-out fold"
                )
            base = clip_and_renormalize_probabilities(
                item.shadow_only_probabilities, training_count=item.training_count
            )
            full = clip_and_renormalize_probabilities(
                item.shadow_plus_transcript_probabilities,
                training_count=item.training_count,
            )
            fold_losses[item.fold_index].append(
                (
                    -math.log(base[item.observed_label_index]),
                    -math.log(full[item.observed_label_index]),
                )
            )
        if any(not fold_losses[index] for index in range(registration.fold_count)):
            raise ReadinessError("every frozen shadow fold requires an observation")
        folds = tuple(
            estimate_signed_lambda(
                shadow_only_cross_entropy=sum(value[0] for value in fold_losses[index])
                / len(fold_losses[index]),
                shadow_plus_transcript_cross_entropy=sum(
                    value[1] for value in fold_losses[index]
                )
                / len(fold_losses[index]),
            )
            for index in range(registration.fold_count)
        )
        results.append(
            ShadowTargetEstimate(
                target,
                folds,
                tuple(
                    len(fold_losses[index]) for index in range(registration.fold_count)
                ),
                _factory_token=_SHADOW_TARGET_TOKEN,
            )
        )
    return ShadowCampaignEstimate(
        registration.to_ref(), tuple(results), _factory_token=_SHADOW_ESTIMATE_TOKEN
    )


@dataclass(frozen=True, slots=True)
class AttackProcedureRef:
    case: IntegrityCase
    procedure_id: str
    procedure_version: str
    content_digest: str

    def __post_init__(self) -> None:
        if type(self) is not AttackProcedureRef or type(self.case) is not IntegrityCase:
            raise TypeError("attack procedure case must use its exact enum")
        _text(self.procedure_id, "procedure_id")
        _text(self.procedure_version, "procedure_version")
        _digest(self.content_digest, "content_digest")


@dataclass(frozen=True, slots=True)
class AttackCampaignRef:
    challenge_key: ChallengeKey
    design_digest: str
    campaign_id: str
    campaign_version: str
    content_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        _digest(self.design_digest, "design_digest")
        _text(self.campaign_id, "campaign_id")
        _text(self.campaign_version, "campaign_version")
        _digest(self.content_digest, "content_digest")


@dataclass(frozen=True, slots=True)
class AttackCampaignRegistration:
    challenge_key: ChallengeKey
    design_digest: str
    campaign_id: str
    campaign_version: str
    procedures: tuple[AttackProcedureRef, ...]
    fixture_only: bool = True

    def __post_init__(self) -> None:
        if type(self) is not AttackCampaignRegistration:
            raise ReadinessError("attack campaign subclasses are rejected")
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        _digest(self.design_digest, "design_digest")
        _text(self.campaign_id, "campaign_id")
        _text(self.campaign_version, "campaign_version")
        if type(self.procedures) is not tuple or any(
            type(item) is not AttackProcedureRef for item in self.procedures
        ):
            raise ReadinessError(
                "attack campaign must register every case in exact order"
            )
        try:
            procedures = tuple(
                AttackProcedureRef(
                    item.case,
                    item.procedure_id,
                    item.procedure_version,
                    item.content_digest,
                )
                for item in self.procedures
            )
        except (AttributeError, TypeError, ValueError) as exc:
            raise ReadinessError("attack procedure identity is invalid") from exc
        if tuple(item.case for item in procedures) != tuple(IntegrityCase):
            raise ReadinessError(
                "attack campaign must register every case in exact order"
            )
        object.__setattr__(self, "procedures", procedures)
        if self.fixture_only is not True:
            raise ReadinessError("B-E4 attack readiness is fixture-only")

    @property
    def authority_ceiling(self) -> str:
        return READINESS_AUTHORITY_CEILING

    @property
    def content_digest(self) -> str:
        return _canonical_digest(
            _ATTACK_CAMPAIGN_DOMAIN,
            {
                "authority_ceiling": self.authority_ceiling,
                "campaign_id": self.campaign_id,
                "campaign_version": self.campaign_version,
                "challenge_key": _challenge_payload(self.challenge_key),
                "design_digest": self.design_digest,
                "fixture_only": self.fixture_only,
                "procedures": [_procedure_payload(item) for item in self.procedures],
            },
        )

    def to_ref(self) -> AttackCampaignRef:
        return AttackCampaignRef(
            self.challenge_key,
            self.design_digest,
            self.campaign_id,
            self.campaign_version,
            self.content_digest,
        )


def _procedure_payload(value: AttackProcedureRef) -> dict[str, str]:
    return {
        "case": value.case.value,
        "content_digest": value.content_digest,
        "procedure_id": value.procedure_id,
        "procedure_version": value.procedure_version,
    }


@dataclass(frozen=True, slots=True)
class AttackExecutionBinding:
    challenge_key: ChallengeKey
    design_digest: str
    run_identity: RunIdentity | None
    block_id: str | None
    dedicated_campaign_id: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        _digest(self.design_digest, "design_digest")
        run_path = self.run_identity is not None or self.block_id is not None
        dedicated_path = self.dedicated_campaign_id is not None
        if run_path == dedicated_path:
            raise ReadinessError("attack execution needs one exact execution identity")
        if run_path:
            if type(self.run_identity) is not RunIdentity or self.block_id is None:
                raise ReadinessError(
                    "run-bound attacks require run and block identities"
                )
            object.__setattr__(self, "run_identity", _copy_run(self.run_identity))
            _text(self.block_id, "block_id")
        else:
            _text(self.dedicated_campaign_id, "dedicated_campaign_id")


class AttackEvidenceKind(str, Enum):
    TASK = "TASK"
    EXPERIMENT_RECORD = "EXPERIMENT_RECORD"
    RESOURCE = "RESOURCE"
    FIXTURE = "FIXTURE"
    SHADOW = "SHADOW"
    TRANSFER = "TRANSFER"
    EVALUATOR_DECISION_INPUT = "EVALUATOR_DECISION_INPUT"
    PROVENANCE = "PROVENANCE"


@dataclass(frozen=True, slots=True)
class AttackEvidenceRef:
    kind: AttackEvidenceKind
    content_digest: str

    def __post_init__(self) -> None:
        if type(self.kind) is not AttackEvidenceKind:
            raise TypeError("attack evidence kind must use its exact enum")
        _digest(self.content_digest, "content_digest")


class AttackTerminalState(str, Enum):
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


class AttackReceiptStatus(str, Enum):
    DESIGN_ANALYSIS_TYPED_REJECTION_CARRIER = (
        "DESIGN_ANALYSIS_ONLY_UNTRUSTED_TYPED_REJECTION_CARRIER"
    )
    DESIGN_ANALYSIS_NON_REJECTION_CARRIER = (
        "DESIGN_ANALYSIS_ONLY_UNTRUSTED_NON_REJECTION_CARRIER"
    )


ProtocolOutcome = ResearchServiceErrorCode | ResourcePolicyInputCode | DossierInputCode
_PROTOCOL_TYPES = (ResearchServiceErrorCode, ResourcePolicyInputCode, DossierInputCode)


@dataclass(frozen=True, slots=True)
class AttackAttemptReceiptRef:
    campaign_ref: AttackCampaignRef
    attempt_id: str
    case: IntegrityCase
    content_digest: str

    def __post_init__(self) -> None:
        if type(self.campaign_ref) is not AttackCampaignRef:
            raise TypeError("exact attack campaign ref is required")
        _text(self.attempt_id, "attempt_id")
        if type(self.case) is not IntegrityCase:
            raise TypeError("attack receipt case must use its exact enum")
        _digest(self.content_digest, "content_digest")


@dataclass(frozen=True, slots=True, init=False, repr=False)
class AttackAttemptReceipt:
    """Untrusted design-analysis carrier; never proof an attack was executed."""

    campaign_ref: AttackCampaignRef
    attempt_id: str
    case: IntegrityCase
    procedure_ref: AttackProcedureRef
    execution_binding: AttackExecutionBinding
    protocol_outcomes: tuple[ProtocolOutcome, ...]
    transcript_digest: str
    evidence_refs: tuple[AttackEvidenceRef, ...]
    evaluator_inputs_digest: str
    provenance_digest: str
    terminal_state: AttackTerminalState
    status: AttackReceiptStatus

    def __init__(
        self,
        campaign_ref: AttackCampaignRef,
        attempt_id: str,
        case: IntegrityCase,
        procedure_ref: AttackProcedureRef,
        execution_binding: AttackExecutionBinding,
        protocol_outcomes: tuple[ProtocolOutcome, ...],
        transcript_digest: str,
        evidence_refs: tuple[AttackEvidenceRef, ...],
        evaluator_inputs_digest: str,
        provenance_digest: str,
        terminal_state: AttackTerminalState,
        status: AttackReceiptStatus,
        *,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _RECEIPT_TOKEN:
            raise TypeError("attack receipts are created only by the evidence store")
        for name, value in locals().copy().items():
            if name not in {"self", "_factory_token"}:
                object.__setattr__(self, name, value)

    def __repr__(self) -> str:
        return "AttackAttemptReceipt(<untrusted-design-analysis>)"

    def __reduce_ex__(self, protocol: int) -> object:
        del protocol
        raise TypeError("private attack receipts cannot be serialized")

    @property
    def authority_ceiling(self) -> str:
        return READINESS_AUTHORITY_CEILING

    @property
    def disposition(self) -> IntegrityDisposition | None:
        """No integrity disposition is earned from caller-supplied evidence refs."""

        return None

    @property
    def is_trusted_execution_evidence(self) -> bool:
        return False

    @property
    def is_qualifying(self) -> bool:
        return False

    @property
    def content_digest(self) -> str:
        return _canonical_digest(_ATTACK_RECEIPT_DOMAIN, _attack_receipt_payload(self))

    def to_ref(self) -> AttackAttemptReceiptRef:
        return AttackAttemptReceiptRef(
            self.campaign_ref, self.attempt_id, self.case, self.content_digest
        )


def _copy_run(value: RunIdentity) -> RunIdentity:
    try:
        return RunIdentity(
            value.profile,
            value.arm,
            value.replicate,
            value.prior_pack_ref,
            value.test_only_authorization_ref,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ReadinessError("run identity is structurally invalid") from exc


def _run_payload(value: RunIdentity) -> dict[str, object]:
    result: dict[str, object] = {
        "arm": value.arm.value,
        "profile": value.profile.value,
        "replicate": value.replicate,
        "prior_pack": None,
        "test_only_authorization": None,
    }
    if value.prior_pack_ref is not None:
        pack = value.prior_pack_ref
        result["prior_pack"] = {
            "challenge_key": _challenge_payload(pack.challenge_key),
            "channel": pack.channel.value,
            "content_hash": pack.content_hash,
            "publication_sequence": pack.publication_sequence,
        }
    if value.test_only_authorization_ref is not None:
        receipt = value.test_only_authorization_ref
        result["test_only_authorization"] = {
            "authorization_id": receipt.authorization_id,
            "challenge_key": _challenge_payload(receipt.challenge_key),
            "content_digest": receipt.content_digest,
        }
    return result


def _execution_binding_payload(value: AttackExecutionBinding) -> dict[str, object]:
    return {
        "block_id": value.block_id,
        "challenge_key": _challenge_payload(value.challenge_key),
        "dedicated_campaign_id": value.dedicated_campaign_id,
        "design_digest": value.design_digest,
        "run_identity": (
            None if value.run_identity is None else _run_payload(value.run_identity)
        ),
    }


def _attack_receipt_payload(value: AttackAttemptReceipt) -> dict[str, object]:
    return {
        "authority_ceiling": value.authority_ceiling,
        "attempt_id": value.attempt_id,
        "campaign_digest": value.campaign_ref.content_digest,
        "case": value.case.value,
        "evaluator_inputs_digest": value.evaluator_inputs_digest,
        "evidence_refs": [
            {"content_digest": item.content_digest, "kind": item.kind.value}
            for item in value.evidence_refs
        ],
        "execution_binding": _execution_binding_payload(value.execution_binding),
        "procedure": _procedure_payload(value.procedure_ref),
        "protocol_outcomes": [
            {"owner_type": type(item).__name__, "value": item.value}
            for item in value.protocol_outcomes
        ],
        "provenance_digest": value.provenance_digest,
        "status": value.status.value,
        "terminal_state": value.terminal_state.value,
        "transcript_digest": value.transcript_digest,
    }


class AttackEvidenceStore:
    """Insert-only store for explicitly untrusted design-analysis carriers."""

    __slots__ = (
        "_campaign_identities",
        "_campaigns",
        "_identities",
        "_receipts",
    )

    def __init__(self) -> None:
        self._campaigns: dict[AttackCampaignRef, AttackCampaignRegistration] = {}
        self._campaign_identities: dict[
            tuple[ChallengeKey, str, str, str], AttackCampaignRef
        ] = {}
        self._identities: dict[
            tuple[AttackCampaignRef, str], AttackAttemptReceiptRef
        ] = {}
        self._receipts: dict[AttackAttemptReceiptRef, AttackAttemptReceipt] = {}

    def register_campaign(
        self, registration: AttackCampaignRegistration
    ) -> AttackCampaignRef:
        if type(registration) is not AttackCampaignRegistration:
            raise TypeError("exact attack campaign registration is required")
        ref = registration.to_ref()
        identity = (
            ref.challenge_key,
            ref.design_digest,
            ref.campaign_id,
            ref.campaign_version,
        )
        previous = self._campaign_identities.get(identity)
        if previous is not None and previous != ref:
            raise ReadinessError(
                "attack campaign identity already binds different content"
            )
        self._campaign_identities[identity] = ref
        self._campaigns.setdefault(ref, registration)
        return ref

    def record_attempt(
        self,
        *,
        campaign_ref: AttackCampaignRef,
        attempt_id: str,
        case: IntegrityCase,
        execution_binding: AttackExecutionBinding,
        protocol_outcomes: tuple[ProtocolOutcome, ...],
        transcript_digest: str,
        evidence_refs: tuple[AttackEvidenceRef, ...],
        evaluator_inputs_digest: str,
        provenance_digest: str,
        terminal_state: AttackTerminalState,
    ) -> AttackAttemptReceiptRef:
        if type(campaign_ref) is not AttackCampaignRef:
            raise TypeError("exact attack campaign ref is required")
        campaign = self._campaigns.get(campaign_ref)
        if campaign is None or campaign.to_ref() != campaign_ref:
            raise ReadinessError("attack campaign is not registered")
        _text(attempt_id, "attempt_id")
        if type(case) is not IntegrityCase:
            raise TypeError("attack case must use its exact enum")
        if type(execution_binding) is not AttackExecutionBinding:
            raise TypeError("exact attack execution binding is required")
        execution_binding = AttackExecutionBinding(
            execution_binding.challenge_key,
            execution_binding.design_digest,
            execution_binding.run_identity,
            execution_binding.block_id,
            execution_binding.dedicated_campaign_id,
        )
        if (
            execution_binding.challenge_key != campaign_ref.challenge_key
            or execution_binding.design_digest != campaign_ref.design_digest
        ):
            raise ReadinessError(
                "attack execution binding must match campaign Challenge and design"
            )
        if (
            execution_binding.run_identity is not None
            and execution_binding.run_identity.prior_pack_ref is not None
            and execution_binding.run_identity.prior_pack_ref.challenge_key
            != campaign_ref.challenge_key
        ):
            raise ReadinessError("attack run binding is cross-Challenge")
        if (
            type(protocol_outcomes) is not tuple
            or len(protocol_outcomes) > 1
            or any(type(item) not in _PROTOCOL_TYPES for item in protocol_outcomes)
        ):
            raise ReadinessError("attack outcomes require zero or one exact owner code")
        if type(terminal_state) is not AttackTerminalState:
            raise TypeError("terminal state must use its exact enum")
        if protocol_outcomes:
            IntegrityObservation(
                case,
                IntegrityDisposition.TYPED_REJECTION,
                protocol_outcomes[0],
            )
            if terminal_state is not AttackTerminalState.COMPLETED:
                raise ReadinessError(
                    "a typed rejection carrier requires a completed attempt"
                )
            status = AttackReceiptStatus.DESIGN_ANALYSIS_TYPED_REJECTION_CARRIER
        else:
            status = AttackReceiptStatus.DESIGN_ANALYSIS_NON_REJECTION_CARRIER
        if (
            type(evidence_refs) is not tuple
            or not evidence_refs
            or len(evidence_refs) > 64
            or any(type(item) is not AttackEvidenceRef for item in evidence_refs)
            or len(set(evidence_refs)) != len(evidence_refs)
        ):
            raise ReadinessError("attack evidence refs must be non-empty and unique")
        evidence_kinds = {item.kind for item in evidence_refs}
        if AttackEvidenceKind.PROVENANCE not in evidence_kinds:
            raise ReadinessError("every attack carrier requires provenance evidence")
        if not protocol_outcomes:
            if AttackEvidenceKind.EVALUATOR_DECISION_INPUT not in evidence_kinds:
                raise ReadinessError(
                    "a non-rejection carrier requires evaluator decision inputs"
                )
            if (
                terminal_state is AttackTerminalState.COMPLETED
                and not evidence_kinds
                & {
                    AttackEvidenceKind.SHADOW,
                    AttackEvidenceKind.TRANSFER,
                }
            ):
                raise ReadinessError(
                    "a completed non-rejection carrier requires shadow or transfer evidence"
                )
        for value, name in (
            (transcript_digest, "transcript_digest"),
            (evaluator_inputs_digest, "evaluator_inputs_digest"),
            (provenance_digest, "provenance_digest"),
        ):
            _digest(value, name)
        if (
            AttackEvidenceRef(AttackEvidenceKind.PROVENANCE, provenance_digest)
            not in evidence_refs
        ):
            raise ReadinessError(
                "provenance evidence ref must bind the provenance digest"
            )
        if (
            not protocol_outcomes
            and AttackEvidenceRef(
                AttackEvidenceKind.EVALUATOR_DECISION_INPUT,
                evaluator_inputs_digest,
            )
            not in evidence_refs
        ):
            raise ReadinessError(
                "evaluator evidence ref must bind the evaluator-input digest"
            )
        procedure = campaign.procedures[tuple(IntegrityCase).index(case)]
        receipt = AttackAttemptReceipt(
            campaign_ref,
            attempt_id,
            case,
            procedure,
            execution_binding,
            protocol_outcomes,
            transcript_digest,
            evidence_refs,
            evaluator_inputs_digest,
            provenance_digest,
            terminal_state,
            status,
            _factory_token=_RECEIPT_TOKEN,
        )
        ref = receipt.to_ref()
        identity = (campaign_ref, attempt_id)
        previous = self._identities.get(identity)
        if previous is not None and previous != ref:
            raise ReadinessError(
                "attack attempt identity already binds different evidence"
            )
        self._identities[identity] = ref
        self._receipts.setdefault(ref, receipt)
        return ref

    def get(self, ref: AttackAttemptReceiptRef) -> AttackAttemptReceipt:
        if type(ref) is not AttackAttemptReceiptRef:
            raise TypeError("exact attack attempt ref is required")
        receipt = self._receipts.get(ref)
        if receipt is None or receipt.to_ref() != ref:
            raise ReadinessError("attack receipt is unavailable or corrupt")
        return receipt

    def __len__(self) -> int:
        return len(self._receipts)

    @property
    def is_trusted_execution_evidence(self) -> bool:
        return False


class ExecutionArtifactKind(str, Enum):
    DRIVER = "DRIVER"
    RUNTIME = "RUNTIME"
    ARM = "ARM"
    METER = "METER"
    ANALYSIS = "ANALYSIS"


@dataclass(frozen=True, slots=True)
class ExecutionArtifactPin:
    kind: ExecutionArtifactKind
    artifact_id: str
    artifact_version: str
    content_digest: str

    def __post_init__(self) -> None:
        if type(self.kind) is not ExecutionArtifactKind:
            raise TypeError("execution artifact kind must use its exact enum")
        _text(self.artifact_id, "artifact_id")
        _text(self.artifact_version, "artifact_version")
        _digest(self.content_digest, "content_digest")


@dataclass(frozen=True, slots=True)
class BlockReplacement:
    profile: AgentProfile
    original_replicate: int
    replacement_replicate: int
    reason_digest: str

    def __post_init__(self) -> None:
        if type(self.profile) is not AgentProfile:
            raise TypeError("replacement profile must use its exact enum")
        if (
            type(self.original_replicate) is not int
            or type(self.replacement_replicate) is not int
            or self.original_replicate < 0
            or self.replacement_replicate < 0
            or self.original_replicate == self.replacement_replicate
        ):
            raise ReadinessError("block replacement identities are invalid")
        _digest(self.reason_digest, "reason_digest")


def _observation_payload(value: EngineeringObservation) -> dict[str, object]:
    return {
        "attempts_to_first_practice_admissible": value.attempts_to_first_practice_admissible,
        "best_independent_heldout_toy_result": _optional_float(
            value.best_independent_heldout_toy_result
        ),
        "compute_to_executable_strategy": _optional_float(
            value.compute_to_executable_strategy
        ),
        "intervention_labels": list(value.intervention_labels),
        "invalid_run_count": value.invalid_run_count,
        "reconstruction_success": value.reconstruction_success,
        "run": _run_payload(value.run),
        "time_to_executable_strategy_seconds": _optional_float(
            value.time_to_executable_strategy_seconds
        ),
        "time_to_first_practice_admissible_seconds": _optional_float(
            value.time_to_first_practice_admissible_seconds
        ),
        "total_run_count": value.total_run_count,
        "transfer_result": _optional_float(value.transfer_result),
        "transcript_digest": value.transcript_digest,
    }


@dataclass(frozen=True, slots=True, repr=False)
class ExecutionEvidenceDraft:
    """Content-bound untrusted design-analysis carrier for wiring/dry runs.

    The current draft deliberately models only an unreplaced complete matrix.
    A future trusted execution owner must define profile-specific reserve
    selection, retained-block membership, and complete driver/arm manifests
    before replacement evidence can be represented without ambiguity.
    """

    challenge_key: ChallengeKey
    design_digest: str
    run_identities: tuple[RunIdentity, ...]
    artifact_pins: tuple[ExecutionArtifactPin, ...]
    observations: tuple[EngineeringObservation, ...]
    block_replacements: tuple[BlockReplacement, ...]
    attack_campaign_ref: AttackCampaignRef
    attack_receipt_refs: tuple[AttackAttemptReceiptRef, ...]
    shadow_campaign_ref: ShadowCampaignRef
    shadow_estimate_ref: ShadowCampaignEstimateRef
    analysis_version: str
    deterministic_analysis_seed: int
    utility_component: DesignAnalysisClassification
    diversity_component: DesignAnalysisClassification
    leakage_component: DesignAnalysisClassification
    authority_ceiling: str = field(default=READINESS_AUTHORITY_CEILING, init=False)

    def __post_init__(self) -> None:
        if type(self) is not ExecutionEvidenceDraft:
            raise ReadinessError("execution evidence draft subclasses are rejected")
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        _digest(self.design_digest, "design_digest")
        if type(self.run_identities) is not tuple or not self.run_identities:
            raise ReadinessError("execution draft requires exact run identities")
        runs = tuple(_copy_run(item) for item in self.run_identities)
        if len(set(runs)) != len(runs):
            raise ReadinessError("execution draft run identities must be unique")
        for run in runs:
            if (
                run.prior_pack_ref is not None
                and run.prior_pack_ref.challenge_key != challenge
            ):
                raise ReadinessError("execution draft contains a cross-Challenge run")
        replicates = {item.replicate for item in runs}
        expected_runs = {
            (profile, arm, replicate)
            for profile in AgentProfile
            for arm in ExperimentalArm
            for replicate in replicates
        }
        actual_runs = {(item.profile, item.arm, item.replicate) for item in runs}
        if (
            not replicates
            or actual_runs != expected_runs
            or len(runs) != len(expected_runs)
        ):
            raise ReadinessError(
                "execution draft requires a complete profile-by-arm matrix"
            )
        v2_pins = {
            (item.prior_pack_ref, item.test_only_authorization_ref)
            for item in runs
            if item.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR
        }
        if len(v2_pins) != 1:
            raise ReadinessError("execution draft must freeze one exact v2 pin pair")
        object.__setattr__(self, "run_identities", runs)
        if (
            type(self.artifact_pins) is not tuple
            or len(self.artifact_pins) != len(ExecutionArtifactKind)
            or any(
                type(item) is not ExecutionArtifactPin for item in self.artifact_pins
            )
            or len(set(self.artifact_pins)) != len(self.artifact_pins)
            or {item.kind for item in self.artifact_pins} != set(ExecutionArtifactKind)
            or tuple(item.kind for item in self.artifact_pins)
            != tuple(ExecutionArtifactKind)
        ):
            raise ReadinessError(
                "execution draft requires all exact artifact pin kinds"
            )
        if (
            type(self.observations) is not tuple
            or not self.observations
            or any(
                type(item) is not EngineeringObservation for item in self.observations
            )
        ):
            raise ReadinessError("execution draft requires engineering observations")
        copied_observations = tuple(
            EngineeringObservation(
                _copy_run(item.run),
                item.time_to_executable_strategy_seconds,
                item.compute_to_executable_strategy,
                item.time_to_first_practice_admissible_seconds,
                item.attempts_to_first_practice_admissible,
                item.best_independent_heldout_toy_result,
                item.transfer_result,
                item.reconstruction_success,
                item.invalid_run_count,
                item.total_run_count,
                item.intervention_labels,
                item.transcript_digest,
            )
            for item in self.observations
        )
        observation_runs = tuple(item.run for item in copied_observations)
        if len(set(observation_runs)) != len(observation_runs) or set(
            observation_runs
        ) != set(runs):
            raise ReadinessError(
                "execution observations must cover every matrix run exactly once"
            )
        object.__setattr__(self, "observations", copied_observations)
        if type(self.block_replacements) is not tuple or any(
            type(item) is not BlockReplacement for item in self.block_replacements
        ):
            raise TypeError("block replacements require exact records")
        replacements = tuple(
            BlockReplacement(
                item.profile,
                item.original_replicate,
                item.replacement_replicate,
                item.reason_digest,
            )
            for item in self.block_replacements
        )
        object.__setattr__(self, "block_replacements", replacements)
        if replacements:
            raise ReadinessError("retained replacement-matrix binding is unavailable")
        if len(
            {(item.profile, item.original_replicate) for item in replacements}
        ) != len(replacements):
            raise ReadinessError("a block can be replaced at most once")
        if len(
            {(item.profile, item.replacement_replicate) for item in replacements}
        ) != len(replacements):
            raise ReadinessError("a reserve block can be consumed at most once")
        original_blocks = {
            (item.profile, item.original_replicate) for item in replacements
        }
        replacement_blocks = {
            (item.profile, item.replacement_replicate) for item in replacements
        }
        if original_blocks & replacement_blocks:
            raise ReadinessError("block replacement chains are forbidden")
        for replacement in replacements:
            for arm in ExperimentalArm:
                if (
                    replacement.profile,
                    arm,
                    replacement.original_replicate,
                ) not in actual_runs or (
                    replacement.profile,
                    arm,
                    replacement.replacement_replicate,
                ) not in actual_runs:
                    raise ReadinessError(
                        "block replacements must identify complete matrix blocks"
                    )
        if (
            type(self.attack_campaign_ref) is not AttackCampaignRef
            or self.attack_campaign_ref.challenge_key != challenge
            or self.attack_campaign_ref.design_digest != self.design_digest
        ):
            raise ReadinessError("attack campaign does not bind the draft design")
        if (
            type(self.attack_receipt_refs) is not tuple
            or len(self.attack_receipt_refs) != len(IntegrityCase)
            or any(
                type(item) is not AttackAttemptReceiptRef
                or item.campaign_ref != self.attack_campaign_ref
                for item in self.attack_receipt_refs
            )
            or len(set(self.attack_receipt_refs)) != len(self.attack_receipt_refs)
            or tuple(item.case for item in self.attack_receipt_refs)
            != tuple(IntegrityCase)
        ):
            raise ReadinessError(
                "attack receipts must cover every case for the exact campaign"
            )
        if (
            type(self.shadow_campaign_ref) is not ShadowCampaignRef
            or self.shadow_campaign_ref.challenge_key != challenge
            or self.shadow_campaign_ref.design_digest != self.design_digest
        ):
            raise ReadinessError("shadow campaign does not bind the draft design")
        if (
            type(self.shadow_estimate_ref) is not ShadowCampaignEstimateRef
            or self.shadow_estimate_ref.campaign_ref != self.shadow_campaign_ref
        ):
            raise ReadinessError("shadow estimate must bind the exact shadow campaign")
        _text(self.analysis_version, "analysis_version")
        if (
            type(self.deterministic_analysis_seed) is not int
            or not 0 <= self.deterministic_analysis_seed < 1 << 64
        ):
            raise ReadinessError("analysis seed must be uint64")
        for value in (
            self.utility_component,
            self.diversity_component,
            self.leakage_component,
        ):
            if type(value) is not DesignAnalysisClassification:
                raise TypeError(
                    "draft components require design-analysis-only outcomes"
                )

    def __repr__(self) -> str:
        return "ExecutionEvidenceDraft(<untrusted-design-analysis>)"

    @property
    def is_qualifying(self) -> bool:
        return False

    @property
    def is_trusted_execution_evidence(self) -> bool:
        return False

    @property
    def verified_ratification_ref(self) -> None:
        return None

    @property
    def content_digest(self) -> str:
        payload = {
            "analysis_seed": self.deterministic_analysis_seed,
            "analysis_version": self.analysis_version,
            "artifact_pins": [
                {
                    "artifact_id": item.artifact_id,
                    "artifact_version": item.artifact_version,
                    "content_digest": item.content_digest,
                    "kind": item.kind.value,
                }
                for item in self.artifact_pins
            ],
            "attack_campaign_digest": self.attack_campaign_ref.content_digest,
            "attack_receipts": [
                {
                    "attempt_id": item.attempt_id,
                    "case": item.case.value,
                    "content_digest": item.content_digest,
                }
                for item in self.attack_receipt_refs
            ],
            "authority_ceiling": self.authority_ceiling,
            "block_replacements": [
                {
                    "original_replicate": item.original_replicate,
                    "profile": item.profile.value,
                    "reason_digest": item.reason_digest,
                    "replacement_replicate": item.replacement_replicate,
                }
                for item in self.block_replacements
            ],
            "challenge_key": _challenge_payload(self.challenge_key),
            "components": {
                "diversity": self.diversity_component.value,
                "leakage": self.leakage_component.value,
                "utility": self.utility_component.value,
            },
            "design_digest": self.design_digest,
            "observations": [_observation_payload(item) for item in self.observations],
            "runs": [_run_payload(item) for item in self.run_identities],
            "shadow_campaign_digest": self.shadow_campaign_ref.content_digest,
            "shadow_estimate_digest": self.shadow_estimate_ref.content_digest,
            "verified_ratification_ref": None,
        }
        return _canonical_digest(_EXECUTION_DRAFT_DOMAIN, payload)


RATIFICATION_TRUST_SEAMS = (
    "AUTHENTICATED_FIVE_ROLE_PRINCIPAL_ASSIGNMENTS",
    "MULTI_ROLE_AND_ROLE_CURRENTNESS_POLICY",
    "IMMUTABLE_APPROVAL_ACT_VERIFIER_AND_TRUST_ROOT",
    "APPROVAL_REVOCATION_AND_EDIT_POLICY",
    "ONE_USE_EXECUTION_AUTHORIZATION",
)


@dataclass(frozen=True, slots=True)
class RatificationReadinessAudit:
    design_digest: str | None
    syntactically_complete: bool
    declared_owners: tuple[RatifyingOwner, ...]
    missing_declared_owners: tuple[RatifyingOwner, ...]
    invalid_declaration_reasons: tuple[str, ...] = ()
    missing_trust_seams: tuple[str, ...] = RATIFICATION_TRUST_SEAMS
    authority_ceiling: str = READINESS_AUTHORITY_CEILING

    def __post_init__(self) -> None:
        if self.design_digest is not None:
            _digest(self.design_digest, "design_digest")
        if (
            type(self.syntactically_complete) is not bool
            or type(self.declared_owners) is not tuple
            or type(self.missing_declared_owners) is not tuple
            or any(type(item) is not RatifyingOwner for item in self.declared_owners)
            or any(
                type(item) is not RatifyingOwner
                for item in self.missing_declared_owners
            )
            or len(set(self.declared_owners)) != len(self.declared_owners)
            or len(set(self.missing_declared_owners))
            != len(self.missing_declared_owners)
            or set(self.declared_owners) & set(self.missing_declared_owners)
            or set(self.declared_owners) | set(self.missing_declared_owners)
            != set(RatifyingOwner)
        ):
            raise ReadinessError("ratification audit owner partition is invalid")
        if (
            type(self.invalid_declaration_reasons) is not tuple
            or any(
                type(item) is not str or not item
                for item in self.invalid_declaration_reasons
            )
            or len(set(self.invalid_declaration_reasons))
            != len(self.invalid_declaration_reasons)
        ):
            raise ReadinessError("ratification audit reasons are invalid")
        for item in self.invalid_declaration_reasons:
            _text(item, "invalid_declaration_reason", maximum=256)
        if self.missing_trust_seams != RATIFICATION_TRUST_SEAMS:
            raise ReadinessError("ratification trust seams cannot be caller-defined")
        if self.authority_ceiling != READINESS_AUTHORITY_CEILING:
            raise ReadinessError("ratification audit authority ceiling is fixed")

    @property
    def is_verified_owner_ratified(self) -> bool:
        return False

    @property
    def qualifying_execution_ready(self) -> bool:
        return False


def audit_ratification_readiness(
    preregistration: GauntletPreregistration,
) -> RatificationReadinessAudit:
    """Report structural declarations while keeping verification unavailable."""

    if type(preregistration) is not GauntletPreregistration:
        raise TypeError("exact GauntletPreregistration is required")
    by_owner = {
        owner: tuple(
            item for item in preregistration.ratifications if item.owner is owner
        )
        for owner in RatifyingOwner
    }
    valid_design = preregistration.is_syntactically_complete
    declared = tuple(
        owner
        for owner in RatifyingOwner
        if valid_design
        and len(by_owner[owner]) == 1
        and by_owner[owner][0].design_digest == preregistration.design_digest
    )
    missing = tuple(owner for owner in RatifyingOwner if owner not in declared)
    reasons: list[str] = []
    if not valid_design and preregistration.ratifications:
        reasons.append("PREREGISTRATION_DESIGN_NOT_CONTENT_BOUND")
    for owner in RatifyingOwner:
        declarations = by_owner[owner]
        if len(declarations) > 1:
            reasons.append(f"DUPLICATE_OWNER:{owner.value}")
        if declarations and any(
            item.design_digest != preregistration.design_digest for item in declarations
        ):
            reasons.append(f"DESIGN_DIGEST_MISMATCH:{owner.value}")
    return RatificationReadinessAudit(
        preregistration.design_digest,
        valid_design,
        declared,
        missing,
        tuple(reasons),
    )


def require_verified_ratification(audit: RatificationReadinessAudit) -> None:
    """Fail closed until an authenticated role/approval verifier is ratified."""

    if type(audit) is not RatificationReadinessAudit:
        raise TypeError("exact ratification readiness audit is required")
    raise RatificationUnavailableError(
        "verified B-E4 owner ratification is unavailable: "
        + ",".join(audit.missing_trust_seams)
    )


def build_qualifying_execution_evidence(
    draft: ExecutionEvidenceDraft,
    audit: RatificationReadinessAudit,
) -> None:
    """There is deliberately no positive qualifying constructor yet."""

    if type(draft) is not ExecutionEvidenceDraft:
        raise TypeError("exact non-qualifying execution draft is required")
    require_verified_ratification(audit)


__all__ = (
    "RATIFICATION_TRUST_SEAMS",
    "READINESS_AUTHORITY_CEILING",
    "SHADOW_CLIPPING_POLICY",
    "SHADOW_ESTIMATOR_ID",
    "SHADOW_FEATURE_POLICY",
    "SHADOW_FOLD_POLICY",
    "AttackAttemptReceipt",
    "AttackAttemptReceiptRef",
    "AttackCampaignRef",
    "AttackCampaignRegistration",
    "AttackEvidenceKind",
    "AttackEvidenceRef",
    "AttackEvidenceStore",
    "AttackExecutionBinding",
    "AttackProcedureRef",
    "AttackReceiptStatus",
    "AttackTerminalState",
    "BlockReplacement",
    "ExecutionArtifactKind",
    "ExecutionArtifactPin",
    "ExecutionEvidenceDraft",
    "RatificationReadinessAudit",
    "RatificationUnavailableError",
    "ReadinessError",
    "ShadowCampaignEstimate",
    "ShadowCampaignEstimateRef",
    "ShadowCampaignRef",
    "ShadowCampaignRegistration",
    "ShadowFoldObservation",
    "ShadowTargetDefinition",
    "ShadowTargetEstimate",
    "SignedLambdaEstimate",
    "SignedLambdaState",
    "audit_ratification_readiness",
    "build_qualifying_execution_evidence",
    "clip_and_renormalize_probabilities",
    "estimate_shadow_campaign",
    "estimate_signed_lambda",
    "require_verified_ratification",
    "shadow_fold_index",
)
