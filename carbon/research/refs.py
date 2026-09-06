"""Exact nominal references shared by the v2 research protocol."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, TypeAlias

from carbon.authoring.primitives import (
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_tagged_sha256,
    validate_uint64,
    validate_version_token,
)
from carbon.registry import ChallengeKey

RESEARCH_SCHEMA_VERSION = "2.0"
RESEARCH_CANONICALIZATION_PROFILE = "carbon_research_service_canonical_v2"
RESEARCH_DOCUMENT_HEADER = b"carbon.research-service.canonical.v2\x00"


def _challenge(value: object) -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AttributeError, TypeError, ValueError):
        raise TypeError("challenge_key must be an exact ChallengeKey") from None


def _digest(value: object, field: str = "content_digest") -> str:
    try:
        return validate_tagged_sha256(value, field)
    except (AttributeError, TypeError, ValueError):
        raise ValueError(f"{field} must be canonical tagged SHA-256") from None


def _id(value: object, field: str) -> str:
    try:
        return validate_canonical_id(value, field)
    except (AttributeError, TypeError, ValueError):
        raise ValueError(f"{field} must be a canonical identifier") from None


def _version(value: object, field: str) -> str:
    try:
        return validate_version_token(value, field)
    except (AttributeError, TypeError, ValueError):
        raise ValueError(f"{field} must be a canonical version") from None


def _schema_profile(schema: object, profile: object) -> tuple[str, str]:
    checked = _version(schema, "schema_version")
    if checked != RESEARCH_SCHEMA_VERSION:
        raise ValueError("only research schema version 2.0 is supported")
    if type(profile) is not str or profile != RESEARCH_CANONICALIZATION_PROFILE:
        raise ValueError("unknown research canonicalization profile")
    return checked, profile


@dataclass(frozen=True, slots=True)
class _ChallengeDigestRef:
    challenge_key: ChallengeKey
    schema_version: str = RESEARCH_SCHEMA_VERSION
    canonicalization_profile: str = RESEARCH_CANONICALIZATION_PROFILE
    content_digest: str = ""

    REF_TYPE: ClassVar[str] = ""

    def __post_init__(self) -> None:
        expected = _CHALLENGE_DIGEST_TYPES.get(self.REF_TYPE)
        if expected is None or type(self) is not expected:
            raise TypeError("v2 ref must use its exact nominal type")
        schema, profile = _schema_profile(
            self.schema_version, self.canonicalization_profile
        )
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(self, "canonicalization_profile", profile)
        object.__setattr__(self, "content_digest", _digest(self.content_digest))

    @property
    def ref_type(self) -> str:
        return self.REF_TYPE


class ChallengeInfoRef(_ChallengeDigestRef):
    REF_TYPE = "challenge_info_ref"


class InteractionManifestRef(_ChallengeDigestRef):
    REF_TYPE = "interaction_manifest_ref"


class PublicScorePolicyRef(_ChallengeDigestRef):
    REF_TYPE = "public_score_policy_ref"


class StrategySchemaRef(_ChallengeDigestRef):
    REF_TYPE = "strategy_schema_ref"


class PriorPolicyBundleRef(_ChallengeDigestRef):
    REF_TYPE = "prior_policy_bundle_ref"


class DisclosurePolicyRef(_ChallengeDigestRef):
    REF_TYPE = "disclosure_policy_ref"


class PublicEstimandRef(_ChallengeDigestRef):
    REF_TYPE = "public_estimand_ref"


class PublicSearchScopeRef(_ChallengeDigestRef):
    REF_TYPE = "public_search_scope_ref"


class PracticeScopeStatementRef(_ChallengeDigestRef):
    REF_TYPE = "practice_scope_statement_ref"


class PublicMethodResourceCodebookRef(_ChallengeDigestRef):
    REF_TYPE = "public_method_resource_codebook_ref"


class PracticePackRef(_ChallengeDigestRef):
    REF_TYPE = "practice_pack_ref"


class PublicScaffoldCatalogRef(_ChallengeDigestRef):
    REF_TYPE = "public_scaffold_catalog_ref"


class PublicPracticeTestRef(_ChallengeDigestRef):
    REF_TYPE = "public_practice_test_ref"


class PublicMethodArtifactRef(_ChallengeDigestRef):
    REF_TYPE = "public_method_artifact_ref"


class PublicAggregatePublicationRef(_ChallengeDigestRef):
    REF_TYPE = "public_aggregate_publication_ref"


class CompilerEnvironmentRef(_ChallengeDigestRef):
    REF_TYPE = "compiler_environment_ref"


class MockScaffoldRef(_ChallengeDigestRef):
    REF_TYPE = "mock_scaffold_ref"


class ValidationResultRef(_ChallengeDigestRef):
    REF_TYPE = "validation_result_ref"


class StrategyCompilationRef(_ChallengeDigestRef):
    REF_TYPE = "strategy_compilation_ref"


class PriorAlignmentRef(_ChallengeDigestRef):
    REF_TYPE = "prior_alignment_ref"


class ResourceForecastRef(_ChallengeDigestRef):
    REF_TYPE = "resource_forecast_ref"


_CHALLENGE_DIGEST_TYPES = {
    ref_type.REF_TYPE: ref_type
    for ref_type in (
        ChallengeInfoRef,
        InteractionManifestRef,
        PublicScorePolicyRef,
        StrategySchemaRef,
        PriorPolicyBundleRef,
        DisclosurePolicyRef,
        PublicEstimandRef,
        PublicSearchScopeRef,
        PracticeScopeStatementRef,
        PublicMethodResourceCodebookRef,
        PracticePackRef,
        PublicScaffoldCatalogRef,
        PublicPracticeTestRef,
        PublicMethodArtifactRef,
        PublicAggregatePublicationRef,
        CompilerEnvironmentRef,
        MockScaffoldRef,
        ValidationResultRef,
        StrategyCompilationRef,
        PriorAlignmentRef,
        ResourceForecastRef,
    )
}
CHALLENGE_DIGEST_REF_TYPES = tuple(_CHALLENGE_DIGEST_TYPES.values())


class PriorChannel(str, Enum):
    PUBLIC = "PUBLIC"
    TEST_ONLY_FIXTURE = "TEST_ONLY_FIXTURE"


def _channel(value: object) -> PriorChannel:
    if type(value) is not PriorChannel:
        raise ValueError("prior channel is outside the closed vocabulary")
    return value


@dataclass(frozen=True, slots=True)
class PriorChannelRef:
    challenge_key: ChallengeKey
    channel: PriorChannel
    schema_version: str = RESEARCH_SCHEMA_VERSION
    canonicalization_profile: str = RESEARCH_CANONICALIZATION_PROFILE
    content_digest: str = ""

    def __post_init__(self) -> None:
        if type(self) is not PriorChannelRef:
            raise TypeError("prior channel ref subclasses are rejected")
        schema, profile = _schema_profile(
            self.schema_version, self.canonicalization_profile
        )
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(self, "channel", _channel(self.channel))
        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(self, "canonicalization_profile", profile)
        object.__setattr__(self, "content_digest", _digest(self.content_digest))

    @property
    def ref_type(self) -> str:
        return "prior_channel_ref"


@dataclass(frozen=True, slots=True)
class PriorPackRef:
    challenge_key: ChallengeKey
    channel: PriorChannel
    publication_sequence: int
    content_hash: str

    def __post_init__(self) -> None:
        if type(self) is not PriorPackRef:
            raise TypeError("prior pack ref subclasses are rejected")
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(self, "channel", _channel(self.channel))
        validate_uint64(self.publication_sequence, "publication_sequence")
        object.__setattr__(
            self, "content_hash", _digest(self.content_hash, "content_hash")
        )

    @property
    def ref_type(self) -> str:
        return "prior_pack_ref"


@dataclass(frozen=True, slots=True)
class PriorIndexSnapshotRef:
    challenge_key: ChallengeKey
    channel: PriorChannel
    index_sequence: int
    schema_version: str = RESEARCH_SCHEMA_VERSION
    content_digest: str = ""

    def __post_init__(self) -> None:
        if type(self) is not PriorIndexSnapshotRef:
            raise TypeError("prior index ref subclasses are rejected")
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(self, "channel", _channel(self.channel))
        validate_uint64(self.index_sequence, "index_sequence")
        if _version(self.schema_version, "schema_version") != RESEARCH_SCHEMA_VERSION:
            raise ValueError("prior index ref requires schema 2.0")
        object.__setattr__(self, "content_digest", _digest(self.content_digest))

    @property
    def ref_type(self) -> str:
        return "prior_index_snapshot_ref"


@dataclass(frozen=True, slots=True)
class PriorPublicationReceiptRef:
    challenge_key: ChallengeKey
    channel: PriorChannel
    publication_sequence: int
    schema_version: str = RESEARCH_SCHEMA_VERSION
    content_digest: str = ""

    def __post_init__(self) -> None:
        if type(self) is not PriorPublicationReceiptRef:
            raise TypeError("publication receipt ref subclasses are rejected")
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(self, "channel", _channel(self.channel))
        validate_uint64(self.publication_sequence, "publication_sequence")
        if _version(self.schema_version, "schema_version") != RESEARCH_SCHEMA_VERSION:
            raise ValueError("publication receipt ref requires schema 2.0")
        object.__setattr__(self, "content_digest", _digest(self.content_digest))

    @property
    def ref_type(self) -> str:
        return "prior_publication_receipt_ref"


@dataclass(frozen=True, slots=True)
class ResearchTaskId:
    value: str

    def __post_init__(self) -> None:
        if type(self) is not ResearchTaskId:
            raise TypeError("research task id subclasses are rejected")
        if type(self.value) is not str or not self.value.startswith("rtsk_"):
            raise ValueError("research task id is malformed")
        suffix = self.value[5:]
        if len(suffix) != 64 or any(c not in "0123456789abcdef" for c in suffix):
            raise ValueError("research task id is malformed")


@dataclass(frozen=True, slots=True)
class ResearchReceiptRef:
    task_id: ResearchTaskId
    receipt_digest: str

    def __post_init__(self) -> None:
        if type(self) is not ResearchReceiptRef:
            raise TypeError("research receipt ref subclasses are rejected")
        if type(self.task_id) is not ResearchTaskId:
            raise TypeError("task_id must use its exact nominal type")
        object.__setattr__(self, "task_id", ResearchTaskId(self.task_id.value))
        object.__setattr__(
            self, "receipt_digest", _digest(self.receipt_digest, "receipt_digest")
        )

    @property
    def ref_type(self) -> str:
        return "research_receipt_ref"


@dataclass(frozen=True, slots=True)
class TestOnlyPriorAuthorizationReceiptRef:
    challenge_key: ChallengeKey
    authorization_id: str
    content_digest: str

    def __post_init__(self) -> None:
        if type(self) is not TestOnlyPriorAuthorizationReceiptRef:
            raise TypeError("test authorization ref subclasses are rejected")
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(
            self, "authorization_id", _id(self.authorization_id, "authorization_id")
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))

    @property
    def ref_type(self) -> str:
        return "test_only_prior_authorization_receipt_ref"


RESEARCH_REF_TYPES = (
    *CHALLENGE_DIGEST_REF_TYPES,
    PriorChannelRef,
    PriorPackRef,
    PriorIndexSnapshotRef,
    PriorPublicationReceiptRef,
    ResearchReceiptRef,
    TestOnlyPriorAuthorizationReceiptRef,
)
ResearchRef: TypeAlias = (
    _ChallengeDigestRef
    | PriorChannelRef
    | PriorPackRef
    | PriorIndexSnapshotRef
    | PriorPublicationReceiptRef
    | ResearchReceiptRef
    | TestOnlyPriorAuthorizationReceiptRef
)


def is_research_ref(value: object) -> bool:
    return type(value) in RESEARCH_REF_TYPES


__all__ = tuple(
    name
    for name in globals()
    if name.endswith("Ref")
    or name
    in {
        "CHALLENGE_DIGEST_REF_TYPES",
        "RESEARCH_CANONICALIZATION_PROFILE",
        "RESEARCH_DOCUMENT_HEADER",
        "RESEARCH_REF_TYPES",
        "RESEARCH_SCHEMA_VERSION",
        "PriorChannel",
        "ResearchTaskId",
        "is_research_ref",
    }
)
