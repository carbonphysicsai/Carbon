"""Trusted loading and structural-origin composition for B-02A artifacts.

Authored bytes do not carry provenance, fixture status, qualification, or LIVE
authority.  This module keeps those facts in capability-issued exact values
that are attached only after digest-first, closed-schema loading.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, final

from .errors import AuthoringError, ReferenceMismatchError
from .model import ApplicabilityBinding, ApplicabilityTag
from .primitives import (
    validate_exact_document_bytes,
)
from .refs import (
    CanonicalChallengeCaseRef,
    ChallengeScope,
    GlobalScope,
    InstanceDistributionContractRef,
    TopLevelObjectRef,
    is_top_level_ref,
    reconstruct_top_level_ref,
    require_owner_ref,
)


class AuthoringLoadError(AuthoringError):
    """A bounded artifact could not be loaded or structurally verified."""


class OriginTag(str, Enum):
    """Closed per-artifact structural origin."""

    FIXTURE = "FIXTURE"
    DRAFT = "DRAFT"
    REGISTERED = "REGISTERED"


class GraphOriginTag(str, Enum):
    """Closed least-authoritative join over one complete authoring graph."""

    FIXTURE_DERIVED = "FIXTURE_DERIVED"
    DRAFT_OR_UNRESOLVED = "DRAFT_OR_UNRESOLVED"
    REGISTERED_GRAPH = "REGISTERED_GRAPH"


_ORIGIN_TOKEN = object()
_LOADED_TOKEN = object()
_GRAPH_TOKEN = object()


def _owner_ref_key(value: object) -> tuple[object, ...]:
    """Return an explicit stable key without repr or Python class identity."""
    ref_kind = object.__getattribute__(value, "ref_kind")
    scope = object.__getattribute__(value, "scope_binding")
    if type(scope) is ChallengeScope:
        scope_key: tuple[object, ...] = (
            "CHALLENGE",
            scope.challenge_key.challenge_id,
            scope.challenge_key.version,
        )
    elif type(scope) is GlobalScope:
        scope_key = ("GLOBAL",)
    else:  # defensive; require_owner_ref normally rejects this first
        raise AuthoringLoadError(
            "authoring.origin_ref_scope_invalid",
            "Origin evidence has an invalid owner-ref scope.",
            path="/scope_binding",
        )
    return (
        ref_kind,
        *scope_key,
        object.__getattribute__(value, "object_id"),
        object.__getattribute__(value, "object_version"),
        object.__getattribute__(value, "content_digest"),
    )


def _owner_ref_tuple(
    value: object,
    *,
    kind: str,
    field: str,
    nonempty: bool = True,
) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise AuthoringLoadError(
            "authoring.origin_tuple_type_invalid",
            f"{field} must be an exact built-in tuple.",
            path=f"/{field}",
        )
    if nonempty and not value:
        raise AuthoringLoadError(
            "authoring.origin_tuple_empty",
            f"{field} must not be empty.",
            path=f"/{field}",
        )
    copied = tuple(require_owner_ref(item, kind) for item in value)
    ordered = tuple(sorted(copied, key=_owner_ref_key))
    if len(set(ordered)) != len(ordered):
        raise AuthoringLoadError(
            "authoring.origin_tuple_duplicate",
            f"{field} contains a duplicate exact ref.",
            path=f"/{field}",
        )
    return ordered


@final
@dataclass(frozen=True, slots=True, init=False)
class FixtureOrigin:
    """Fixture origin issued only by a conspicuous fixture capability."""

    fixture_registration_ref: object
    source_provenance_refs: tuple[object, ...]

    def __init__(
        self,
        fixture_registration_ref: object,
        source_provenance_refs: tuple[object, ...],
        *,
        _token: object,
    ) -> None:
        if _token is not _ORIGIN_TOKEN:
            raise AuthoringLoadError(
                "authoring.origin_capability_required",
                "Fixture origin requires the controlled fixture capability.",
            )
        object.__setattr__(
            self,
            "fixture_registration_ref",
            require_owner_ref(fixture_registration_ref, "fixture_registration"),
        )
        object.__setattr__(
            self,
            "source_provenance_refs",
            _owner_ref_tuple(
                source_provenance_refs,
                kind="provenance",
                field="source_provenance_refs",
            ),
        )

    @property
    def tag(self) -> OriginTag:
        return OriginTag.FIXTURE


@final
@dataclass(frozen=True, slots=True, init=False)
class DraftOrigin:
    """Draft origin issued only after an injected authority verifies it."""

    draft_authority_ref: object
    source_provenance_refs: tuple[object, ...]

    def __init__(
        self,
        draft_authority_ref: object,
        source_provenance_refs: tuple[object, ...],
        *,
        _token: object,
    ) -> None:
        if _token is not _ORIGIN_TOKEN:
            raise AuthoringLoadError(
                "authoring.origin_capability_required",
                "Draft origin requires a verified authority capability.",
            )
        object.__setattr__(
            self,
            "draft_authority_ref",
            require_owner_ref(draft_authority_ref, "draft_authority"),
        )
        object.__setattr__(
            self,
            "source_provenance_refs",
            _owner_ref_tuple(
                source_provenance_refs,
                kind="provenance",
                field="source_provenance_refs",
            ),
        )

    @property
    def tag(self) -> OriginTag:
        return OriginTag.DRAFT


@final
@dataclass(frozen=True, slots=True, init=False)
class RegisteredOrigin:
    """Registered origin issued only after complete external verification."""

    registration_ref: object
    authority_evidence_refs: tuple[object, ...]
    source_provenance_refs: tuple[object, ...]

    def __init__(
        self,
        registration_ref: object,
        authority_evidence_refs: tuple[object, ...],
        source_provenance_refs: tuple[object, ...],
        *,
        _token: object,
    ) -> None:
        if _token is not _ORIGIN_TOKEN:
            raise AuthoringLoadError(
                "authoring.origin_capability_required",
                "Registered origin requires a verified authority capability.",
            )
        object.__setattr__(
            self,
            "registration_ref",
            require_owner_ref(registration_ref, "authoring_registration"),
        )
        object.__setattr__(
            self,
            "authority_evidence_refs",
            _owner_ref_tuple(
                authority_evidence_refs,
                kind="authority_evidence",
                field="authority_evidence_refs",
            ),
        )
        object.__setattr__(
            self,
            "source_provenance_refs",
            _owner_ref_tuple(
                source_provenance_refs,
                kind="provenance",
                field="source_provenance_refs",
            ),
        )

    @property
    def tag(self) -> OriginTag:
        return OriginTag.REGISTERED


AuthoringOrigin = FixtureOrigin | DraftOrigin | RegisteredOrigin


class OriginEvidenceAuthority(Protocol):
    """Trusted composition-root provider; B-02A does not implement authority."""

    def verify_authoring_origin(
        self,
        *,
        origin_tag: OriginTag,
        principal_ref: object,
        authority_evidence_refs: tuple[object, ...],
        source_provenance_refs: tuple[object, ...],
    ) -> bool:
        """Return exact True only when the external evidence currently verifies."""


@final
class FixtureAuthoringCapability:
    """Conspicuous capability that can issue fixture origin and nothing else."""

    __slots__ = ()

    def issue_origin(
        self,
        *,
        fixture_registration_ref: object,
        source_provenance_refs: tuple[object, ...],
    ) -> FixtureOrigin:
        return FixtureOrigin(
            fixture_registration_ref,
            source_provenance_refs,
            _token=_ORIGIN_TOKEN,
        )


@final
class AuthoringOriginIssuer:
    """Adapter around a separately owned origin-evidence authority."""

    __slots__ = ("_authority",)

    def __init__(self, authority: OriginEvidenceAuthority) -> None:
        verifier = getattr(authority, "verify_authoring_origin", None)
        if not callable(verifier):
            raise TypeError("authority must provide verify_authoring_origin")
        self._authority = authority

    def issue_draft(
        self,
        *,
        draft_authority_ref: object,
        source_provenance_refs: tuple[object, ...],
    ) -> DraftOrigin:
        principal = require_owner_ref(draft_authority_ref, "draft_authority")
        provenance = _owner_ref_tuple(
            source_provenance_refs,
            kind="provenance",
            field="source_provenance_refs",
        )
        verified = self._authority.verify_authoring_origin(
            origin_tag=OriginTag.DRAFT,
            principal_ref=principal,
            authority_evidence_refs=(),
            source_provenance_refs=provenance,
        )
        if type(verified) is not bool or not verified:
            raise AuthoringLoadError(
                "authoring.draft_origin_unverified",
                "Draft origin authority evidence did not verify.",
            )
        return DraftOrigin(principal, provenance, _token=_ORIGIN_TOKEN)

    def issue_registered(
        self,
        *,
        registration_ref: object,
        authority_evidence_refs: tuple[object, ...],
        source_provenance_refs: tuple[object, ...],
    ) -> RegisteredOrigin:
        principal = require_owner_ref(registration_ref, "authoring_registration")
        authority_refs = _owner_ref_tuple(
            authority_evidence_refs,
            kind="authority_evidence",
            field="authority_evidence_refs",
        )
        provenance = _owner_ref_tuple(
            source_provenance_refs,
            kind="provenance",
            field="source_provenance_refs",
        )
        verified = self._authority.verify_authoring_origin(
            origin_tag=OriginTag.REGISTERED,
            principal_ref=principal,
            authority_evidence_refs=authority_refs,
            source_provenance_refs=provenance,
        )
        if type(verified) is not bool or not verified:
            raise AuthoringLoadError(
                "authoring.registered_origin_unverified",
                "Registered origin authority evidence did not verify.",
            )
        return RegisteredOrigin(
            principal,
            authority_refs,
            provenance,
            _token=_ORIGIN_TOKEN,
        )


def reconstruct_authoring_origin(value: object) -> AuthoringOrigin:
    """Defensively copy one capability-issued exact origin variant."""
    if type(value) is FixtureOrigin:
        return FixtureOrigin(
            value.fixture_registration_ref,
            value.source_provenance_refs,
            _token=_ORIGIN_TOKEN,
        )
    if type(value) is DraftOrigin:
        return DraftOrigin(
            value.draft_authority_ref,
            value.source_provenance_refs,
            _token=_ORIGIN_TOKEN,
        )
    if type(value) is RegisteredOrigin:
        return RegisteredOrigin(
            value.registration_ref,
            value.authority_evidence_refs,
            value.source_provenance_refs,
            _token=_ORIGIN_TOKEN,
        )
    raise AuthoringLoadError(
        "authoring.origin_type_invalid",
        "Origin must be an exact capability-issued variant.",
        path="/origin",
    )


def _ref_key(value: TopLevelObjectRef) -> tuple[object, ...]:
    key: tuple[object, ...] = (
        value.object_kind,
        value.challenge_key.challenge_id,
        value.challenge_key.version,
        value.object_id,
        value.object_version,
        value.schema_version,
        value.canonicalization_profile,
        value.content_digest,
    )
    if type(value) is InstanceDistributionContractRef:
        return (*key, value.expected_population_role)
    if type(value) is CanonicalChallengeCaseRef:
        return (*key, value.disclosure_class)
    return key


def _ref_tuple(
    value: object, *, field: str, nonempty: bool = False
) -> tuple[TopLevelObjectRef, ...]:
    if type(value) is not tuple:
        raise AuthoringLoadError(
            "authoring.graph_ref_tuple_type_invalid",
            f"{field} must be an exact built-in tuple.",
            path=f"/{field}",
        )
    if nonempty and not value:
        raise AuthoringLoadError(
            "authoring.graph_ref_tuple_empty",
            f"{field} must not be empty.",
            path=f"/{field}",
        )
    copied = tuple(reconstruct_top_level_ref(item) for item in value)
    ordered = tuple(sorted(copied, key=_ref_key))
    if len(set(ordered)) != len(ordered):
        raise AuthoringLoadError(
            "authoring.graph_ref_duplicate",
            f"{field} contains a duplicate exact ref.",
            path=f"/{field}",
        )
    return ordered


@final
@dataclass(frozen=True, slots=True, init=False)
class LoadedAuthoringArtifact:
    """Digest-verified object plus separately verified structural authority."""

    expected_ref: TopLevelObjectRef
    recomputed_ref: TopLevelObjectRef
    verified_bytes: bytes
    authored_object: object
    origin: AuthoringOrigin
    origin_evidence_ref: object
    source_provenance_refs: tuple[object, ...]
    audit_evidence_refs: tuple[object, ...]
    qualification_evidence: ApplicabilityBinding[object]

    def __init__(
        self,
        *,
        expected_ref: TopLevelObjectRef,
        recomputed_ref: TopLevelObjectRef,
        verified_bytes: bytes,
        authored_object: object,
        origin: AuthoringOrigin,
        origin_evidence_ref: object,
        source_provenance_refs: tuple[object, ...],
        audit_evidence_refs: tuple[object, ...],
        qualification_evidence: ApplicabilityBinding[object],
        _token: object,
    ) -> None:
        if _token is not _LOADED_TOKEN:
            raise AuthoringLoadError(
                "authoring.loaded_capability_required",
                "Loaded artifacts are created only by the verified loader.",
            )
        expected = reconstruct_top_level_ref(expected_ref)
        recomputed = reconstruct_top_level_ref(recomputed_ref)
        if type(expected) is not type(recomputed) or expected != recomputed:
            raise ReferenceMismatchError(
                "authoring.ref_mismatch",
                "Recomputed authored identity does not match the expected ref.",
                path="/expected_ref",
            )
        payload = validate_exact_document_bytes(verified_bytes, "verified_bytes")
        origin_copy = reconstruct_authoring_origin(origin)
        origin_ref = require_owner_ref(origin_evidence_ref, "authoring_origin_evidence")
        provenance = _owner_ref_tuple(
            source_provenance_refs,
            kind="provenance",
            field="source_provenance_refs",
        )
        audit = _owner_ref_tuple(
            audit_evidence_refs,
            kind="audit_evidence",
            field="audit_evidence_refs",
        )
        if type(qualification_evidence) is not ApplicabilityBinding:
            raise AuthoringLoadError(
                "authoring.qualification_binding_invalid",
                "Qualification evidence must use the exact applicability union.",
                path="/qualification_evidence",
            )
        if qualification_evidence.tag is ApplicabilityTag.BOUND:
            qualification = ApplicabilityBinding.bound(
                require_owner_ref(
                    qualification_evidence.value,
                    "qualification_evidence_bundle",
                )
            )
        else:
            qualification = ApplicabilityBinding.not_applicable(
                require_owner_ref(
                    qualification_evidence.value,
                    "applicability_reason",
                )
            )
        object.__setattr__(self, "expected_ref", expected)
        object.__setattr__(self, "recomputed_ref", recomputed)
        object.__setattr__(self, "verified_bytes", bytes(payload))
        object.__setattr__(self, "authored_object", authored_object)
        object.__setattr__(self, "origin", origin_copy)
        object.__setattr__(self, "origin_evidence_ref", origin_ref)
        object.__setattr__(self, "source_provenance_refs", provenance)
        object.__setattr__(self, "audit_evidence_refs", audit)
        object.__setattr__(self, "qualification_evidence", qualification)


class GraphCompositionAuthority(Protocol):
    """External authority required only for a REGISTERED_GRAPH result."""

    def verify_registered_graph(
        self,
        *,
        root_ref: TopLevelObjectRef,
        dependency_refs: tuple[TopLevelObjectRef, ...],
        origin_evidence_refs: tuple[object, ...],
        composition_audit_ref: object,
    ) -> bool:
        """Return exact True only for a complete verified registered graph."""


@final
@dataclass(frozen=True, slots=True, init=False)
class AuthoringGraphOrigin:
    """Exact capability-issued result of the closed least-authority join."""

    root_ref: TopLevelObjectRef
    dependency_refs: tuple[TopLevelObjectRef, ...]
    origin_evidence_refs: tuple[object, ...]
    graph_origin: GraphOriginTag
    composition_audit_ref: object

    def __init__(
        self,
        *,
        root_ref: TopLevelObjectRef,
        dependency_refs: tuple[TopLevelObjectRef, ...],
        origin_evidence_refs: tuple[object, ...],
        graph_origin: GraphOriginTag,
        composition_audit_ref: object,
        _token: object,
    ) -> None:
        if _token is not _GRAPH_TOKEN:
            raise AuthoringLoadError(
                "authoring.graph_capability_required",
                "Graph origin is created only by controlled composition.",
            )
        root = reconstruct_top_level_ref(root_ref)
        dependencies = _ref_tuple(dependency_refs, field="dependency_refs")
        if any(ref.challenge_key != root.challenge_key for ref in dependencies):
            raise AuthoringLoadError(
                "authoring.graph_challenge_mismatch",
                "Every graph dependency must bind the root Challenge key.",
                path="/dependency_refs",
            )
        evidence = _owner_ref_tuple(
            origin_evidence_refs,
            kind="authoring_origin_evidence",
            field="origin_evidence_refs",
        )
        if type(graph_origin) is not GraphOriginTag:
            raise AuthoringLoadError(
                "authoring.graph_origin_invalid",
                "Graph origin must be an exact closed tag.",
                path="/graph_origin",
            )
        audit = require_owner_ref(composition_audit_ref, "origin_composition_audit")
        object.__setattr__(self, "root_ref", root)
        object.__setattr__(self, "dependency_refs", dependencies)
        object.__setattr__(self, "origin_evidence_refs", evidence)
        object.__setattr__(self, "graph_origin", graph_origin)
        object.__setattr__(self, "composition_audit_ref", audit)


def compose_authoring_graph_origin(
    *,
    root: LoadedAuthoringArtifact,
    dependencies: tuple[LoadedAuthoringArtifact, ...],
    expected_dependency_refs: tuple[TopLevelObjectRef, ...],
    composition_audit_ref: object,
    registered_authority: GraphCompositionAuthority | None,
    revoked_refs: tuple[TopLevelObjectRef, ...] = (),
) -> AuthoringGraphOrigin:
    """Join exact loaded origins; only an external verifier can issue REGISTERED."""
    if type(root) is not LoadedAuthoringArtifact:
        raise AuthoringLoadError(
            "authoring.graph_root_invalid",
            "Graph root must be an exact verified loader result.",
            path="/root",
        )
    if type(dependencies) is not tuple or any(
        type(item) is not LoadedAuthoringArtifact for item in dependencies
    ):
        raise AuthoringLoadError(
            "authoring.graph_dependencies_invalid",
            "Graph dependencies must be an exact tuple of verified loader results.",
            path="/dependencies",
        )
    expected = _ref_tuple(expected_dependency_refs, field="expected_dependency_refs")
    actual = _ref_tuple(
        tuple(item.expected_ref for item in dependencies),
        field="dependency_refs",
    )
    revoked = _ref_tuple(revoked_refs, field="revoked_refs")
    complete = actual == expected and not any(
        ref in revoked for ref in (root.expected_ref, *actual)
    )
    evidence = _owner_ref_tuple(
        (
            root.origin_evidence_ref,
            *(item.origin_evidence_ref for item in dependencies),
        ),
        kind="authoring_origin_evidence",
        field="origin_evidence_refs",
    )
    origins = (root.origin, *(item.origin for item in dependencies))
    if any(type(origin) is FixtureOrigin for origin in origins):
        result_tag = GraphOriginTag.FIXTURE_DERIVED
    elif not complete or any(
        type(origin) is not RegisteredOrigin for origin in origins
    ):
        result_tag = GraphOriginTag.DRAFT_OR_UNRESOLVED
    else:
        audit = require_owner_ref(composition_audit_ref, "origin_composition_audit")
        if registered_authority is None:
            result_tag = GraphOriginTag.DRAFT_OR_UNRESOLVED
        else:
            verifier = getattr(registered_authority, "verify_registered_graph", None)
            if not callable(verifier):
                raise TypeError(
                    "registered_authority must provide verify_registered_graph"
                )
            verified = verifier(
                root_ref=root.expected_ref,
                dependency_refs=actual,
                origin_evidence_refs=evidence,
                composition_audit_ref=audit,
            )
            result_tag = (
                GraphOriginTag.REGISTERED_GRAPH
                if type(verified) is bool and verified
                else GraphOriginTag.DRAFT_OR_UNRESOLVED
            )
    return AuthoringGraphOrigin(
        root_ref=root.expected_ref,
        dependency_refs=actual,
        origin_evidence_refs=evidence,
        graph_origin=result_tag,
        composition_audit_ref=composition_audit_ref,
        _token=_GRAPH_TOKEN,
    )


def load_authoring_bytes(
    expected_ref: TopLevelObjectRef,
    payload: bytes,
    *,
    origin: AuthoringOrigin,
    origin_evidence_ref: object,
    source_provenance_refs: tuple[object, ...],
    audit_evidence_refs: tuple[object, ...],
    qualification_evidence: ApplicabilityBinding[object],
) -> LoadedAuthoringArtifact:
    """Digest-check, parse, reconstruct, and exact-ref-check one authored object."""
    expected = reconstruct_top_level_ref(expected_ref)
    verified = validate_exact_document_bytes(payload, "payload")

    # Import lazily to keep the value/model layer independent of I/O.
    from .canonical import decode_document, tagged_sha256
    from .model import authored_object_from_record

    actual_digest = tagged_sha256(verified)
    if actual_digest != expected.content_digest:
        raise ReferenceMismatchError(
            "authoring.digest_mismatch",
            "Authored bytes do not match the externally expected digest.",
            path="/content_digest",
        )
    decoded = decode_document(
        verified,
        expected_object_kind=expected.object_kind,
        expected_schema_version=expected.schema_version,
    )
    authored_object = authored_object_from_record(
        object_kind=decoded.object_kind,
        record=decoded.record,
    )
    to_ref = getattr(authored_object, "to_ref", None)
    if not callable(to_ref):
        raise AuthoringLoadError(
            "authoring.object_type_unknown",
            "Decoded value is not a closed B-02A authored object.",
        )
    recomputed = to_ref()
    if not is_top_level_ref(recomputed):
        raise AuthoringLoadError(
            "authoring.object_ref_invalid",
            "Decoded authored object produced an invalid exact ref.",
        )
    return LoadedAuthoringArtifact(
        expected_ref=expected,
        recomputed_ref=recomputed,
        verified_bytes=verified,
        authored_object=authored_object,
        origin=origin,
        origin_evidence_ref=origin_evidence_ref,
        source_provenance_refs=source_provenance_refs,
        audit_evidence_refs=audit_evidence_refs,
        qualification_evidence=qualification_evidence,
        _token=_LOADED_TOKEN,
    )


__all__ = [
    "AuthoringGraphOrigin",
    "AuthoringLoadError",
    "AuthoringOrigin",
    "AuthoringOriginIssuer",
    "DraftOrigin",
    "FixtureAuthoringCapability",
    "FixtureOrigin",
    "GraphCompositionAuthority",
    "GraphOriginTag",
    "LoadedAuthoringArtifact",
    "OriginEvidenceAuthority",
    "OriginTag",
    "RegisteredOrigin",
    "compose_authoring_graph_origin",
    "load_authoring_bytes",
]
