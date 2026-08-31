"""Audience-safe B-03 generation projections.

The protected generator result is deliberately not a public identity surface.
This module exposes only the small allowlist ratified by the B-03 contract and
requires the existing B-02A projection authority for any case identity.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from carbon.authoring.cases import (
    CaseProjectionAuthority,
    PublicCaseIdentityProjection,
)
from carbon.authoring.loading import GraphOriginTag
from carbon.authoring.primitives import (
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_version_token,
)
from carbon.registry.model import ChallengeKey

from .errors import GeneratorDisclosureCode, GeneratorDisclosureError
from .model import GeneratorOutcomeKind


class GeneratorProvenanceMarker(str, Enum):
    """The only provenance class B-03 can disclose."""

    FIXTURE_ONLY = "FIXTURE_ONLY"


_PUBLIC_PROJECTION_TOKEN = object()


@dataclass(frozen=True, slots=True, init=False)
class PublicGenerationProjection:
    """Closed, non-reversible public projection of one fixture invocation."""

    challenge_key: ChallengeKey
    generator_id: str
    generator_version: str
    provenance_marker: GeneratorProvenanceMarker
    outcome_kind: GeneratorOutcomeKind
    case_projection: PublicCaseIdentityProjection | None

    def __init__(
        self,
        *,
        challenge_key: ChallengeKey,
        generator_id: str,
        generator_version: str,
        provenance_marker: GeneratorProvenanceMarker,
        outcome_kind: GeneratorOutcomeKind,
        case_projection: PublicCaseIdentityProjection | None,
        _token: object,
    ) -> None:
        if (
            type(self) is not PublicGenerationProjection
            or _token is not _PUBLIC_PROJECTION_TOKEN
        ):
            raise TypeError(
                "public generation projections require the validated factory"
            )
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(self, "generator_id", generator_id)
        object.__setattr__(self, "generator_version", generator_version)
        object.__setattr__(self, "provenance_marker", provenance_marker)
        object.__setattr__(self, "outcome_kind", outcome_kind)
        object.__setattr__(self, "case_projection", case_projection)
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self) is not PublicGenerationProjection:
            raise TypeError("public generation projection subclasses are rejected")
        challenge_key = reconstruct_challenge_key(self.challenge_key)
        object.__setattr__(
            self,
            "challenge_key",
            challenge_key,
        )
        validate_canonical_id(self.generator_id, "generator_id")
        validate_version_token(self.generator_version, "generator_version")
        if type(self.provenance_marker) is not GeneratorProvenanceMarker:
            raise TypeError("provenance marker has the wrong exact type")
        if self.provenance_marker is not GeneratorProvenanceMarker.FIXTURE_ONLY:
            raise ValueError("only structural fixture provenance is available")
        if type(self.outcome_kind) is not GeneratorOutcomeKind:
            raise TypeError("outcome kind has the wrong exact type")
        if (
            self.case_projection is not None
            and type(self.case_projection) is not PublicCaseIdentityProjection
        ):
            raise TypeError("case projection has the wrong exact type")
        if (
            self.case_projection is not None
            and self.case_projection.challenge_key != challenge_key
        ):
            raise ValueError("case projection belongs to another Challenge")


def _unavailable(
    code: GeneratorDisclosureCode = GeneratorDisclosureCode.PROJECTION_NOT_PERMITTED,
) -> GeneratorDisclosureError:
    return GeneratorDisclosureError(
        code,
        path="/projection",
    )


def create_public_generation_projection(
    result: object,
    *,
    case_projection: PublicCaseIdentityProjection | None = None,
    projection_authority: CaseProjectionAuthority | None = None,
) -> PublicGenerationProjection:
    """Construct the exact public allowlist from a protected fixture result.

    A validated structural artifact is mandatory.  Valid/censored results may
    carry an already-issued B-02A public case projection after the separately
    owned authority re-verifies the pairing.  An audit-only constructed case
    on a later infrastructure failure is never projected.
    """

    from .burgers import (
        GeneratedFixtureArtifact,
        build_generated_fixture_artifact,
    )
    from .model import GeneratorResult

    if type(result) is not GeneratorResult:
        raise _unavailable()
    try:
        artifact = result.artifact
        if type(artifact) is not GeneratedFixtureArtifact:
            raise TypeError
        checked_artifact = build_generated_fixture_artifact(
            case=artifact.case,
            case_ref=artifact.case_ref,
            loaded_case=artifact.loaded_case,
            loaded_dependencies=artifact.loaded_dependencies,
            graph_origin=artifact.graph_origin,
        )
        checked_record = replace(result.record)
        checked_result = replace(
            result,
            record=checked_record,
            artifact=checked_artifact,
        )
    except Exception:  # noqa: BLE001 - sanitize the complete protected boundary.
        checked_result = None
    if checked_result is None:
        raise _unavailable(GeneratorDisclosureCode.ARTIFACT_REQUIRED)
    artifact = checked_result.artifact
    graph_origin = artifact.graph_origin
    if (
        getattr(graph_origin, "graph_origin", None)
        is not GraphOriginTag.FIXTURE_DERIVED
    ):
        raise _unavailable(GeneratorDisclosureCode.ARTIFACT_REQUIRED)

    record = checked_result.record
    generator_ref = record.generator_ref
    case_binding = record.case_binding
    if getattr(case_binding, "is_bound", None) is True:
        if (
            type(case_projection) is not PublicCaseIdentityProjection
            or type(projection_authority) is not CaseProjectionAuthority
        ):
            raise _unavailable(GeneratorDisclosureCode.CASE_PAIRING_INVALID)
        if case_projection.challenge_key != record.challenge_key:
            raise _unavailable(GeneratorDisclosureCode.CASE_PAIRING_INVALID)
        pair = getattr(case_binding, "pair", None)
        case_ref = getattr(pair, "ref", None)
        if case_ref is None:
            raise _unavailable(GeneratorDisclosureCode.CASE_PAIRING_INVALID)
        try:
            projection_authority.require_pairing(case_projection, case_ref)
        except Exception:  # noqa: BLE001 - external projection-authority boundary.
            pairing_valid = False
        else:
            pairing_valid = True
        if not pairing_valid:
            raise _unavailable(GeneratorDisclosureCode.CASE_PAIRING_INVALID)
    elif case_projection is not None or projection_authority is not None:
        raise _unavailable(GeneratorDisclosureCode.CASE_PAIRING_INVALID)

    return PublicGenerationProjection(
        challenge_key=record.challenge_key,
        generator_id=generator_ref.object_id,
        generator_version=generator_ref.object_version,
        provenance_marker=GeneratorProvenanceMarker.FIXTURE_ONLY,
        outcome_kind=record.outcome_kind,
        case_projection=case_projection,
        _token=_PUBLIC_PROJECTION_TOKEN,
    )


__all__ = (
    "GeneratorProvenanceMarker",
    "PublicGenerationProjection",
    "create_public_generation_projection",
)
