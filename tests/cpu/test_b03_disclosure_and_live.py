"""Safe-disclosure and fail-closed LIVE proofs for the B-03 fixture."""

from __future__ import annotations

import hashlib
import pickle
from dataclasses import fields
from types import SimpleNamespace

import pytest
from b03_fixtures import make_b03_fixture

from carbon.authoring.cases import (
    CaseProjectionAuthority,
    CaseProjectionVerificationEcho,
    PublicCaseIdentityProjection,
    _issue_case_projection_authority,
)
from carbon.authoring.loading import GraphOriginTag
from carbon.authoring.refs import (
    CanonicalChallengeCaseRef,
    ChallengeScope,
    owner_ref,
)
from carbon.generators.burgers import (
    GeneratedFixtureArtifact,
    ProtectedBurgersFixturePayload,
    _materialize_burgers_fixture_payload,
    burgers_fixture_configuration_ref,
)
from carbon.generators.disclosure import (
    GeneratorProvenanceMarker,
    PublicGenerationProjection,
    create_public_generation_projection,
)
from carbon.generators.errors import (
    GeneratorDisclosureCode,
    GeneratorDisclosureError,
    GeneratorInputCode,
    GeneratorValidationError,
)
from carbon.generators.model import (
    GeneratorOutcomeKind,
    GeneratorResult,
    GeneratorResultRecord,
    RecordRefBinding,
)
from carbon.generators.service import generate_fixture_case
from carbon.registry import (
    ChallengeKey,
    ChallengeRecord,
    ChallengeRegistry,
    LiveActivationError,
    QualificationManifest,
    ScientificAuthoringEligibility,
    ScientificAuthoringGraphOrigin,
    ScientificAuthoringReason,
)
from carbon.seeding.model import DerivedSeed

_GRAPH_FINGERPRINT = (
    "sha256:8c2df7376355d0d4e5339f83d9bf780e26e8ec75f76203d922921c9121b4ce01"
)
_PUBLIC_GENERATION_FIELDS = (
    "challenge_key",
    "generator_id",
    "generator_version",
    "provenance_marker",
    "outcome_kind",
    "case_projection",
)
_SECRET_TOKENS = (
    "seed_value_do_not_disclose",
    "draw_value_do_not_disclose",
    "slot_value_do_not_disclose",
    "payload_value_do_not_disclose",
)


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode('ascii')).hexdigest()}"


def _owner(kind: str, label: str, key: ChallengeKey) -> object:
    return owner_ref(
        kind,
        scope_binding=ChallengeScope(key),
        object_id=label,
        object_version="1.0",
        content_digest=_digest(f"{kind}:{label}"),
    )


def _public_case_projection(
    key: ChallengeKey,
    *,
    issuance_ref: object,
) -> PublicCaseIdentityProjection:
    """Build an exact validated value while leaving issuance to the test authority."""

    projection = object.__new__(PublicCaseIdentityProjection)
    object.__setattr__(projection, "schema_version", "1.0")
    object.__setattr__(projection, "challenge_key", key)
    object.__setattr__(
        projection,
        "opaque_public_handle",
        _owner("opaque_public_case_handle", "opaque_fixture_case", key),
    )
    object.__setattr__(
        projection,
        "disclosure_policy_ref",
        _owner("release_policy", "fixture_public_release", key),
    )
    object.__setattr__(projection, "issuance_ref", issuance_ref)
    object.__setattr__(projection, "public_fact_bindings", ())
    projection.__post_init__()
    return projection


class _CaseEcho:
    def __init__(self, case_ref: CanonicalChallengeCaseRef) -> None:
        self._case_ref = case_ref

    def to_ref(self) -> CanonicalChallengeCaseRef:
        return self._case_ref


def _forged_partial_result(
    key: ChallengeKey,
    case_ref: CanonicalChallengeCaseRef,
) -> GeneratorResult:
    """Bypass every constructor to prove the public boundary revalidates."""

    binding = RecordRefBinding.bound(_CaseEcho(case_ref), case_ref)
    record = object.__new__(GeneratorResultRecord)
    object.__setattr__(record, "challenge_key", key)
    object.__setattr__(
        record,
        "generator_ref",
        _owner("generator", "b03_burgers_fixture", key),
    )
    object.__setattr__(record, "case_binding", binding)
    object.__setattr__(record, "outcome_kind", GeneratorOutcomeKind.VALID_GENERATED)

    artifact = object.__new__(GeneratedFixtureArtifact)
    object.__setattr__(
        artifact,
        "graph_origin",
        SimpleNamespace(graph_origin=GraphOriginTag.FIXTURE_DERIVED),
    )

    result = object.__new__(GeneratorResult)
    object.__setattr__(result, "record", record)
    object.__setattr__(result, "ref", None)
    object.__setattr__(result, "artifact", artifact)
    return result


class _ProjectionRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple[object, object, object]] = []

    def verify_case_projection(
        self,
        *,
        authority_ref: object,
        case_ref: CanonicalChallengeCaseRef,
        projection: object,
    ) -> CaseProjectionVerificationEcho:
        self.calls.append((authority_ref, case_ref, projection))
        return CaseProjectionVerificationEcho(
            authority_ref=authority_ref,
            case_ref=case_ref,
            projection=projection,
        )


class _HostileProjectionFailure(RuntimeError):
    pass


class _RejectingProjectionRegistry:
    def verify_case_projection(self, **kwargs: object) -> object:
        del kwargs
        raise _HostileProjectionFailure("participant_secret_must_not_escape")


def test_public_factory_uses_bound_pair_ref_and_requires_the_same_challenge() -> None:
    fixture = make_b03_fixture()
    invocation = generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )
    result = invocation.payload
    key = result.record.challenge_key
    other_key = ChallengeKey("b03_other_fixture", "1.0")
    case_ref = result.record.case_binding.pair.ref
    issuance_ref = _owner("projection_issuance", "fixture_projection", key)
    case_projection = _public_case_projection(key, issuance_ref=issuance_ref)
    registry = _ProjectionRegistry()
    authority = _issue_case_projection_authority(
        authority_ref=issuance_ref,
        authority=registry,
    )
    assert type(authority) is CaseProjectionAuthority

    observed = create_public_generation_projection(
        result,
        case_projection=case_projection,
        projection_authority=authority,
    )

    assert observed.challenge_key == key
    assert observed.generator_id == "b03_burgers_fixture_generator"
    assert observed.generator_version == "1.0"
    assert observed.provenance_marker is GeneratorProvenanceMarker.FIXTURE_ONLY
    assert observed.outcome_kind is GeneratorOutcomeKind.VALID_GENERATED
    assert observed.case_projection is case_projection
    assert registry.calls == [(issuance_ref, case_ref, case_projection)]

    rejecting_authority = _issue_case_projection_authority(
        authority_ref=issuance_ref,
        authority=_RejectingProjectionRegistry(),
    )
    with pytest.raises(GeneratorDisclosureError) as rejected:
        create_public_generation_projection(
            result,
            case_projection=case_projection,
            projection_authority=rejecting_authority,
        )
    assert rejected.value.code == GeneratorDisclosureCode.CASE_PAIRING_INVALID.value
    assert rejected.value.__cause__ is None
    assert rejected.value.__context__ is None
    assert "participant_secret_must_not_escape" not in repr(rejected.value)
    assert case_ref.content_digest not in repr(observed)

    with pytest.raises(GeneratorDisclosureError) as forged:
        create_public_generation_projection(
            _forged_partial_result(key, case_ref),
            case_projection=case_projection,
            projection_authority=authority,
        )
    assert forged.value.code == GeneratorDisclosureCode.ARTIFACT_REQUIRED.value
    assert forged.value.__cause__ is None
    assert forged.value.__context__ is None

    wrong_projection = _public_case_projection(
        other_key,
        issuance_ref=issuance_ref,
    )
    with pytest.raises(GeneratorDisclosureError) as caught:
        create_public_generation_projection(
            result,
            case_projection=wrong_projection,
            projection_authority=authority,
        )
    assert caught.value.code == GeneratorDisclosureCode.CASE_PAIRING_INVALID.value
    assert caught.value.__cause__ is None
    assert registry.calls == [(issuance_ref, case_ref, case_projection)]

    with pytest.raises(TypeError):
        PublicGenerationProjection(
            challenge_key=key,
            generator_id="b03_burgers_fixture_generator",
            generator_version="1.0",
            provenance_marker=GeneratorProvenanceMarker.FIXTURE_ONLY,
            outcome_kind=GeneratorOutcomeKind.VALID_GENERATED,
            case_projection=case_projection,
        )

    class ProjectionSubclass(PublicGenerationProjection):
        pass

    with pytest.raises(TypeError):
        ProjectionSubclass(
            challenge_key=key,
            generator_id="b03_burgers_fixture_generator",
            generator_version="1.0",
            provenance_marker=GeneratorProvenanceMarker.FIXTURE_ONLY,
            outcome_kind=GeneratorOutcomeKind.VALID_GENERATED,
            case_projection=case_projection,
        )


class _SecretSentinel:
    def __repr__(self) -> str:
        return " ".join(_SECRET_TOKENS)

    __str__ = __repr__


def test_seed_draw_slot_and_payload_do_not_leak_through_safe_surfaces() -> None:
    key = ChallengeKey("b03_no_leakage_fixture", "1.0")
    material = b"seed-draw-slot-payload-bytes!!!!"
    assert len(material) == 32
    seed = DerivedSeed(material)
    payload = _materialize_burgers_fixture_payload(
        seed,
        fixture_configuration_ref=burgers_fixture_configuration_ref(key),
    )

    assert type(payload) is ProtectedBurgersFixturePayload
    protected_surface = repr((repr(seed), str(seed), repr(payload), str(payload)))
    assert material.hex() not in protected_surface
    assert material.decode("ascii") not in protected_surface
    with pytest.raises(TypeError) as pickle_error:
        pickle.dumps(payload)
    assert material.hex() not in repr(pickle_error.value)

    fixture = make_b03_fixture()
    invocation = generate_fixture_case(
        fixture.request,
        fixture_authority=fixture.fixture_authority,
        support_authority=fixture.support_authority,
        censoring_authority=fixture.censoring_authority,
        accounting_authority=fixture.accounting_authority,
    )
    result = invocation.payload
    result_key = result.record.challenge_key
    issuance_ref = _owner(
        "projection_issuance",
        "fixture_no_leakage_projection",
        result_key,
    )
    case_projection = _public_case_projection(
        result_key,
        issuance_ref=issuance_ref,
    )
    projection_authority = _issue_case_projection_authority(
        authority_ref=issuance_ref,
        authority=_ProjectionRegistry(),
    )
    public = create_public_generation_projection(
        result,
        case_projection=case_projection,
        projection_authority=projection_authority,
    )
    assert tuple(field.name for field in fields(public)) == _PUBLIC_GENERATION_FIELDS
    assert all(
        protected_name not in _PUBLIC_GENERATION_FIELDS
        for protected_name in (
            "derived_seed",
            "draw_index",
            "intended_slot_ref",
            "payload",
            "payload_ref",
            "case_ref",
            "replay_ref",
        )
    )

    with pytest.raises(GeneratorDisclosureError) as caught:
        create_public_generation_projection(_SecretSentinel())
    error_surface = repr(
        (
            str(caught.value),
            repr(caught.value),
            caught.value.args,
            caught.value.__dict__,
            repr(public),
        )
    )
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    assert all(token not in error_surface for token in _SECRET_TOKENS)

    with pytest.raises(GeneratorValidationError) as rejected_seed:
        _materialize_burgers_fixture_payload(  # type: ignore[arg-type]
            _SecretSentinel(),
            fixture_configuration_ref=burgers_fixture_configuration_ref(key),
        )
    validation = rejected_seed.value
    validation_surface = repr((str(validation), repr(validation), validation.__dict__))
    assert all(token not in validation_surface for token in _SECRET_TOKENS)

    hostile_path_error = GeneratorValidationError(
        GeneratorInputCode.INVALID_VALUE,
        path=f"/payload/{_SECRET_TOKENS[-1]}",
    )
    assert hostile_path_error.path == "/payload"
    hostile_path_surface = repr(
        (
            str(hostile_path_error),
            repr(hostile_path_error),
            hostile_path_error.__dict__,
        )
    )
    assert all(token not in hostile_path_surface for token in _SECRET_TOKENS)

    stable_schema_path = "/request/conformance_fallbacks/3/fallback_ref"
    stable_path_error = GeneratorValidationError(
        GeneratorInputCode.STALE_BINDING,
        path=stable_schema_path,
    )
    assert stable_path_error.path == stable_schema_path


class _FixtureDerivedVerifier:
    def __init__(self) -> None:
        self.calls: list[tuple[ChallengeKey, str]] = []

    def verify_scientific_authoring(
        self,
        challenge_key: ChallengeKey,
        expected_graph_fingerprint: str,
        /,
    ) -> ScientificAuthoringEligibility:
        self.calls.append((challenge_key, expected_graph_fingerprint))
        return ScientificAuthoringEligibility(
            challenge_key=challenge_key,
            graph_fingerprint=expected_graph_fingerprint,
            graph_origin=ScientificAuthoringGraphOrigin.FIXTURE_DERIVED,
            complete=True,
            revoked=False,
            reasons=(ScientificAuthoringReason.GRAPH_FIXTURE_DERIVED,),
        )


def test_fixture_derived_authoring_graph_fails_closed_at_a3_live_gate(
    tmp_path: object,
) -> None:
    # pytest supplies pathlib.Path, but keeping it structural avoids broad path APIs.
    artifact_root = tmp_path / "artifacts"  # type: ignore[operator]
    artifact_root.mkdir()
    verifier = _FixtureDerivedVerifier()
    registry = ChallengeRegistry(
        tmp_path / "registry",  # type: ignore[operator]
        artifact_root,
        scientific_authoring_verifier=verifier,
    )
    record = ChallengeRecord(
        challenge_id="b03_fixture_live_gate",
        version="1.0",
        fixture_origin=False,
        allowed_backbones=("fno",),
        qualification=QualificationManifest(
            challenge_id="b03_fixture_live_gate",
            challenge_version="1.0",
            mode="production",
            scientific_authoring_graph_fingerprint=_GRAPH_FINGERPRINT,
            slots={},
        ),
        scientific_authoring_graph_fingerprint=_GRAPH_FINGERPRINT,
    )
    registry.save(record)

    assessment = registry.assess_live_eligibility(record.challenge_id, record.version)
    reason_codes = tuple(reason.code for reason in assessment.reasons)
    assert not assessment.eligible
    assert reason_codes.count("scientific_authoring.fixture_derived") == 1

    with pytest.raises(LiveActivationError) as caught:
        registry.activate_live(record.challenge_id, record.version)
    activation_codes = tuple(reason.code for reason in caught.value.eligibility.reasons)
    assert activation_codes.count("scientific_authoring.fixture_derived") == 1
    assert registry.load(record.challenge_id, record.version).status == "draft"
    assert verifier.calls == [
        (record.key, _GRAPH_FINGERPRINT),
        (record.key, _GRAPH_FINGERPRINT),
    ]
