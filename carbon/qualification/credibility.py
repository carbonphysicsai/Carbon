"""B-E3 credibility crosswalk over exact B-06 evidence identities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from carbon.authoring.primitives import (
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_tagged_sha256,
    validate_version_token,
)
from carbon.authoring.refs import ChallengeScope, owner_ref, require_owner_ref
from carbon.registry.model import ChallengeKey

from .enums import (
    DOSSIER_SLOT_ORDER,
    EVIDENCE_CLASS_ALLOWED_CLAIMS,
    ArtifactCurrentness,
    DossierClaimRole,
    DossierSlot,
    StructuralOrigin,
    effective_structural_origin,
)
from .evidence import DossierEvidenceManifest
from .evidence_canonical import evidence_manifest_ref
from .refs import (
    DossierEvidenceManifestRef,
    DossierEvidenceRef,
    ValidationDossierRef,
)

CREDIBILITY_SCHEMA_VERSION = "1.0"
CREDIBILITY_CANONICALIZATION_PROFILE = "carbon_credibility_crosswalk_canonical_v1"
CREDIBILITY_DOCUMENT_HEADER = (
    b"carbon.qualification.credibility-crosswalk.canonical.v1\x00"
)


class EvidenceCategory(str, Enum):
    EXTERNAL_SCIENTIFIC_RESULT = "EXTERNAL_SCIENTIFIC_RESULT"
    CARBON_DESIGN_OR_HYPOTHESIS = "CARBON_DESIGN_OR_HYPOTHESIS"
    PROPOSED_CARBON_EXPERIMENT = "PROPOSED_CARBON_EXPERIMENT"
    CARBON_IMPLEMENTATION = "CARBON_IMPLEMENTATION"
    CARBON_TEST_EVIDENCE = "CARBON_TEST_EVIDENCE"
    QUALIFIED_CARBON_EVIDENCE = "QUALIFIED_CARBON_EVIDENCE"
    INDEPENDENT_REPLICATION = "INDEPENDENT_REPLICATION"
    COMMERCIAL_VALIDATION = "COMMERCIAL_VALIDATION"
    PRODUCTION_QUALIFICATION = "PRODUCTION_QUALIFICATION"


class EvidenceMaturity(str, Enum):
    UNAVAILABLE = "UNAVAILABLE"
    SPECIFIED = "SPECIFIED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    EXTERNALLY_REPORTED = "EXTERNALLY_REPORTED"
    QUALIFIED = "QUALIFIED"
    REPLICATED = "REPLICATED"
    COMMERCIALLY_VALIDATED = "COMMERCIALLY_VALIDATED"
    PRODUCTION_QUALIFIED = "PRODUCTION_QUALIFIED"


CATEGORY_AVAILABLE_MATURITY = MappingProxyType(
    {
        EvidenceCategory.EXTERNAL_SCIENTIFIC_RESULT: EvidenceMaturity.EXTERNALLY_REPORTED,
        EvidenceCategory.CARBON_DESIGN_OR_HYPOTHESIS: EvidenceMaturity.SPECIFIED,
        EvidenceCategory.PROPOSED_CARBON_EXPERIMENT: EvidenceMaturity.SPECIFIED,
        EvidenceCategory.CARBON_IMPLEMENTATION: EvidenceMaturity.IMPLEMENTED,
        EvidenceCategory.CARBON_TEST_EVIDENCE: EvidenceMaturity.TESTED,
        EvidenceCategory.QUALIFIED_CARBON_EVIDENCE: EvidenceMaturity.QUALIFIED,
        EvidenceCategory.INDEPENDENT_REPLICATION: EvidenceMaturity.REPLICATED,
        EvidenceCategory.COMMERCIAL_VALIDATION: (
            EvidenceMaturity.COMMERCIALLY_VALIDATED
        ),
        EvidenceCategory.PRODUCTION_QUALIFICATION: (
            EvidenceMaturity.PRODUCTION_QUALIFIED
        ),
    }
)


class EvidenceAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    PENDING = "PENDING"
    ABSENT = "ABSENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceSourceKind(str, Enum):
    ANALYTIC_SEMI_ANALYTIC_REFERENCE = "ANALYTIC_SEMI_ANALYTIC_REFERENCE"
    MMS_CODE_VERIFICATION = "MMS_CODE_VERIFICATION"
    CONVERGED_NUMERICAL_PRIMARY = "CONVERGED_NUMERICAL_PRIMARY"
    INDEPENDENT_WITNESS = "INDEPENDENT_WITNESS"
    EXPERIMENTAL_VALIDATION = "EXPERIMENTAL_VALIDATION"
    INDUSTRIAL_GOLDEN = "INDUSTRIAL_GOLDEN"
    QUALIFIED_ACCELERATOR_SURROGATE = "QUALIFIED_ACCELERATOR_SURROGATE"
    POPULATION_EVIDENCE = "POPULATION_EVIDENCE"
    GENERATOR_CONFORMANCE = "GENERATOR_CONFORMANCE"
    RECONSTRUCTION_EVIDENCE = "RECONSTRUCTION_EVIDENCE"
    REPRESENTATION_EVIDENCE = "REPRESENTATION_EVIDENCE"
    MEASUREMENT_EVIDENCE = "MEASUREMENT_EVIDENCE"
    REFERENCE_INDEPENDENCE = "REFERENCE_INDEPENDENCE"
    UNCERTAINTY_EVIDENCE = "UNCERTAINTY_EVIDENCE"
    SECURITY_ROLE_SEPARATION = "SECURITY_ROLE_SEPARATION"
    DECISION_RESOLUTION = "DECISION_RESOLUTION"
    LIMITATION_DISCLOSURE = "LIMITATION_DISCLOSURE"


REQUIRED_SOURCE_KINDS = tuple(EvidenceSourceKind)
_SLOT_INDEX = {slot: index for index, slot in enumerate(DOSSIER_SLOT_ORDER)}


class EvidenceOwnerRole(str, Enum):
    PHYSICS_SCIML = "PHYSICS_SCIML"
    STATISTICS = "STATISTICS"
    PROTOCOL = "PROTOCOL"
    SECURITY = "SECURITY"
    INDEPENDENT_REVIEW = "INDEPENDENT_REVIEW"
    OPERATIONS = "OPERATIONS"
    BUSINESS_RIGHTS = "BUSINESS_RIGHTS"
    PRODUCT_QUALIFICATION = "PRODUCT_QUALIFICATION"


class EvidenceIndependence(str, Enum):
    SELF_REPORTED = "SELF_REPORTED"
    CORRELATED = "CORRELATED"
    CARBON_INDEPENDENT = "CARBON_INDEPENDENT"
    EXTERNAL_INDEPENDENT = "EXTERNAL_INDEPENDENT"
    UNRESOLVED = "UNRESOLVED"


class EvidenceDisclosure(str, Enum):
    PUBLIC = "PUBLIC"
    INDEPENDENT_REVIEW = "INDEPENDENT_REVIEW"
    CARBON_PRIVATE = "CARBON_PRIVATE"


class CredibilityRefKind(str, Enum):
    CONTRACT = "CONTRACT"
    FRAMEWORK_REFERENCE = "FRAMEWORK_REFERENCE"
    PHYSICAL_REGIME = "PHYSICAL_REGIME"
    EQUATIONS_MODEL_CLASS = "EQUATIONS_MODEL_CLASS"
    ASSUMPTIONS = "ASSUMPTIONS"
    GEOMETRY_BOUNDARY_INITIAL_CONDITIONS = "GEOMETRY_BOUNDARY_INITIAL_CONDITIONS"
    METHOD = "METHOD"
    APPLICABILITY = "APPLICABILITY"
    UNCERTAINTY = "UNCERTAINTY"
    INDEPENDENCE_CORRELATION = "INDEPENDENCE_CORRELATION"
    VALIDATION_EVIDENCE = "VALIDATION_EVIDENCE"
    FAILURE_POLICY = "FAILURE_POLICY"
    LIMITATION = "LIMITATION"
    UNRESOLVED_INPUT = "UNRESOLVED_INPUT"


REQUIRED_AVAILABLE_REF_KINDS = frozenset(CredibilityRefKind) - {
    CredibilityRefKind.UNRESOLVED_INPUT
}


class HumanInputDisposition(str, Enum):
    PENDING_REQUIRED = "PENDING_REQUIRED"
    PENDING_NON_BLOCKING = "PENDING_NON_BLOCKING"
    NOT_APPLICABLE_WITH_RATIONALE = "NOT_APPLICABLE_WITH_RATIONALE"


class CredibilityIssueCode(str, Enum):
    MALFORMED_DOCUMENT = "credibility.malformed_document"
    SIZE_LIMIT = "credibility.size_limit"
    MISSING_REQUIRED_EVIDENCE = "credibility.missing_required_evidence"
    STALE_REFERENCE = "credibility.stale_reference"
    IDENTITY_MISMATCH = "credibility.identity_mismatch"
    CIRCULAR_SELF_CERTIFICATION = "credibility.circular_self_certification"
    ROLE_CLAIM_MISMATCH = "credibility.role_claim_mismatch"
    UNSUPPORTED_SUBSTITUTION = "credibility.unsupported_substitution"
    MATURITY_OVERSTATEMENT = "credibility.maturity_overstatement"
    UNRESOLVED_REQUIRED_HUMAN_INPUT = "credibility.unresolved_required_human_input"
    DUPLICATE_IDENTITY = "credibility.duplicate_identity"


class CredibilityError(Exception):
    def __init__(self, code: CredibilityIssueCode, *, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code.value} at {path}")


class CredibilityValidationError(CredibilityError, ValueError):
    """A crosswalk is malformed or cannot support its represented claims."""


class CredibilityCanonicalError(CredibilityError, ValueError):
    """Canonical crosswalk bytes are malformed, non-canonical, or oversized."""


class _ProtectedRecord:
    def __repr__(self) -> str:
        return f"{type(self).__name__}(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected credibility records cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected credibility records cannot be pickled")


def _invalid(path: str, code: CredibilityIssueCode) -> CredibilityValidationError:
    return CredibilityValidationError(code, path=path)


def _exact(value: object, expected: type, path: str):
    if type(value) is not expected:
        raise _invalid(path, CredibilityIssueCode.IDENTITY_MISMATCH)
    return value


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, CredibilityIssueCode.IDENTITY_MISMATCH) from None


def _identifier(value: object, path: str) -> str:
    try:
        return validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path, CredibilityIssueCode.IDENTITY_MISMATCH) from None


def _version(value: object, path: str) -> str:
    try:
        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path, CredibilityIssueCode.IDENTITY_MISMATCH) from None


def _digest(value: object, path: str = "/content_digest") -> str:
    try:
        return validate_tagged_sha256(value, path.rsplit("/", 1)[-1])
    except (TypeError, ValueError):
        raise _invalid(path, CredibilityIssueCode.IDENTITY_MISMATCH) from None


def _same_challenge(value: ChallengeKey, expected: ChallengeKey, path: str) -> None:
    if value != expected:
        raise _invalid(path, CredibilityIssueCode.IDENTITY_MISMATCH)


def _copy_evidence(value: object, challenge: ChallengeKey, path: str):
    item = _exact(value, DossierEvidenceRef, path)
    try:
        result = DossierEvidenceRef(
            item.challenge_key,
            item.evidence_class,
            item.evidence_id,
            item.evidence_version,
            item.content_digest,
            item.origin,
        )
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, CredibilityIssueCode.IDENTITY_MISMATCH) from None
    _same_challenge(result.challenge_key, challenge, path)
    return result


def _copy_manifest_ref(value: object, challenge: ChallengeKey, path: str):
    item = _exact(value, DossierEvidenceManifestRef, path)
    try:
        result = DossierEvidenceManifestRef(
            item.challenge_key,
            item.slot,
            item.manifest_id,
            item.manifest_version,
            item.content_digest,
            item.origin,
            item.schema_version,
            item.canonicalization_profile,
        )
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, CredibilityIssueCode.IDENTITY_MISMATCH) from None
    _same_challenge(result.challenge_key, challenge, path)
    return result


def _copy_dossier_ref(value: object, challenge: ChallengeKey, path: str):
    item = _exact(value, ValidationDossierRef, path)
    try:
        result = ValidationDossierRef(
            item.challenge_key,
            item.dossier_id,
            item.dossier_version,
            item.content_digest,
            item.origin,
            item.schema_version,
            item.canonicalization_profile,
        )
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, CredibilityIssueCode.IDENTITY_MISMATCH) from None
    _same_challenge(result.challenge_key, challenge, path)
    return result


def _copy_claim_scope(value: object, challenge: ChallengeKey, path: str):
    try:
        item = require_owner_ref(value, "claim_scope")
    except (AttributeError, TypeError, ValueError):
        raise _invalid(path, CredibilityIssueCode.IDENTITY_MISMATCH) from None
    if type(item.scope_binding) is not ChallengeScope:
        raise _invalid(path, CredibilityIssueCode.IDENTITY_MISMATCH)
    _same_challenge(item.scope_binding.challenge_key, challenge, path)
    return owner_ref(
        "claim_scope",
        scope_binding=ChallengeScope(challenge),
        object_id=item.object_id,
        object_version=item.object_version,
        content_digest=item.content_digest,
    )


@dataclass(frozen=True, slots=True, repr=False)
class CredibilityRef(_ProtectedRecord):
    challenge_key: ChallengeKey
    ref_kind: CredibilityRefKind
    object_id: str
    object_version: str
    content_digest: str
    currentness: ArtifactCurrentness = ArtifactCurrentness.CURRENT

    def __post_init__(self) -> None:
        if type(self) is not CredibilityRef:
            raise _invalid("/ref_type", CredibilityIssueCode.IDENTITY_MISMATCH)
        challenge = _challenge(self.challenge_key)
        _exact(self.ref_kind, CredibilityRefKind, "/ref_kind")
        _exact(self.currentness, ArtifactCurrentness, "/currentness")
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "object_id", _identifier(self.object_id, "/object_id"))
        object.__setattr__(
            self, "object_version", _version(self.object_version, "/object_version")
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))


@dataclass(frozen=True, slots=True, repr=False)
class HumanInputBinding(_ProtectedRecord):
    input_ref: CredibilityRef
    disposition: HumanInputDisposition

    def __post_init__(self) -> None:
        if type(self) is not HumanInputBinding:
            raise _invalid("/input_type", CredibilityIssueCode.IDENTITY_MISMATCH)
        item = _exact(self.input_ref, CredibilityRef, "/input_ref")
        if item.ref_kind is not CredibilityRefKind.UNRESOLVED_INPUT:
            raise _invalid("/input_ref", CredibilityIssueCode.ROLE_CLAIM_MISMATCH)
        _exact(self.disposition, HumanInputDisposition, "/disposition")


@dataclass(frozen=True, slots=True, repr=False)
class CredibilityEvidenceSource(_ProtectedRecord):
    challenge_key: ChallengeKey
    source_id: str
    source_version: str
    source_kind: EvidenceSourceKind
    category: EvidenceCategory
    maturity: EvidenceMaturity
    availability: EvidenceAvailability
    owner: EvidenceOwnerRole
    independence: EvidenceIndependence
    disclosure: EvidenceDisclosure
    evidence_ref: DossierEvidenceRef | None
    evidence_currentness: ArtifactCurrentness
    permitted_claim_roles: tuple[DossierClaimRole, ...]
    use_refs: tuple[CredibilityRef, ...]
    human_inputs: tuple[HumanInputBinding, ...] = ()

    def __post_init__(self) -> None:
        if type(self) is not CredibilityEvidenceSource:
            raise _invalid("/source_type", CredibilityIssueCode.IDENTITY_MISMATCH)
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "source_id", _identifier(self.source_id, "/source_id"))
        object.__setattr__(
            self, "source_version", _version(self.source_version, "/source_version")
        )
        for name, expected in (
            ("source_kind", EvidenceSourceKind),
            ("category", EvidenceCategory),
            ("maturity", EvidenceMaturity),
            ("availability", EvidenceAvailability),
            ("owner", EvidenceOwnerRole),
            ("independence", EvidenceIndependence),
            ("disclosure", EvidenceDisclosure),
            ("evidence_currentness", ArtifactCurrentness),
        ):
            _exact(getattr(self, name), expected, f"/{name}")
        if type(self.permitted_claim_roles) is not tuple:
            raise _invalid(
                "/permitted_claim_roles", CredibilityIssueCode.IDENTITY_MISMATCH
            )
        roles = tuple(
            _exact(item, DossierClaimRole, "/permitted_claim_roles")
            for item in self.permitted_claim_roles
        )
        if len(set(roles)) != len(roles):
            raise _invalid(
                "/permitted_claim_roles", CredibilityIssueCode.DUPLICATE_IDENTITY
            )
        if type(self.use_refs) is not tuple or type(self.human_inputs) is not tuple:
            raise _invalid("/use_refs", CredibilityIssueCode.IDENTITY_MISMATCH)
        refs: list[CredibilityRef] = []
        for index, value in enumerate(self.use_refs):
            item = _exact(value, CredibilityRef, f"/use_refs/{index}")
            _same_challenge(item.challenge_key, challenge, f"/use_refs/{index}")
            refs.append(
                CredibilityRef(
                    item.challenge_key,
                    item.ref_kind,
                    item.object_id,
                    item.object_version,
                    item.content_digest,
                    item.currentness,
                )
            )
        ref_keys = tuple(
            (item.ref_kind, item.object_id, item.object_version) for item in refs
        )
        if len(set(ref_keys)) != len(ref_keys):
            raise _invalid("/use_refs", CredibilityIssueCode.DUPLICATE_IDENTITY)
        inputs: list[HumanInputBinding] = []
        for index, value in enumerate(self.human_inputs):
            item = _exact(value, HumanInputBinding, f"/human_inputs/{index}")
            _same_challenge(
                item.input_ref.challenge_key, challenge, f"/human_inputs/{index}"
            )
            inputs.append(HumanInputBinding(item.input_ref, item.disposition))
        input_keys = tuple(
            (item.input_ref.object_id, item.input_ref.object_version) for item in inputs
        )
        if len(set(input_keys)) != len(input_keys):
            raise _invalid("/human_inputs", CredibilityIssueCode.DUPLICATE_IDENTITY)
        evidence = self.evidence_ref
        if self.availability is EvidenceAvailability.AVAILABLE:
            if evidence is None:
                raise _invalid(
                    "/evidence_ref", CredibilityIssueCode.MISSING_REQUIRED_EVIDENCE
                )
            evidence = _copy_evidence(evidence, challenge, "/evidence_ref")
            present_kinds = {item.ref_kind for item in refs}
            if not REQUIRED_AVAILABLE_REF_KINDS.issubset(present_kinds):
                raise _invalid(
                    "/use_refs", CredibilityIssueCode.MISSING_REQUIRED_EVIDENCE
                )
            if not roles:
                raise _invalid(
                    "/permitted_claim_roles",
                    CredibilityIssueCode.MISSING_REQUIRED_EVIDENCE,
                )
        else:
            if (
                evidence is not None
                or self.maturity is not EvidenceMaturity.UNAVAILABLE
            ):
                raise _invalid(
                    "/availability", CredibilityIssueCode.MATURITY_OVERSTATEMENT
                )
            if roles:
                raise _invalid(
                    "/permitted_claim_roles",
                    CredibilityIssueCode.UNSUPPORTED_SUBSTITUTION,
                )
            if not inputs:
                raise _invalid(
                    "/human_inputs",
                    CredibilityIssueCode.UNRESOLVED_REQUIRED_HUMAN_INPUT,
                )
        refs.sort(
            key=lambda item: (item.ref_kind.value, item.object_id, item.object_version)
        )
        roles = tuple(sorted(roles, key=lambda item: item.value))
        inputs.sort(
            key=lambda item: (item.input_ref.object_id, item.input_ref.object_version)
        )
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "evidence_ref", evidence)
        object.__setattr__(self, "permitted_claim_roles", roles)
        object.__setattr__(self, "use_refs", tuple(refs))
        object.__setattr__(self, "human_inputs", tuple(inputs))

    @property
    def effective_origin(self) -> StructuralOrigin:
        if self.evidence_ref is None:
            return StructuralOrigin.DRAFT_OR_UNRESOLVED
        return self.evidence_ref.origin


@dataclass(frozen=True, slots=True, repr=False)
class ClaimEvidenceLink(_ProtectedRecord):
    challenge_key: ChallengeKey
    slot: DossierSlot
    evidence_manifest_ref: DossierEvidenceManifestRef
    claim_scope_ref: object
    claim_role: DossierClaimRole
    claim_owner: EvidenceOwnerRole
    source_id: str
    source_version: str
    evidence_ref: DossierEvidenceRef

    def __post_init__(self) -> None:
        if type(self) is not ClaimEvidenceLink:
            raise _invalid("/link_type", CredibilityIssueCode.IDENTITY_MISMATCH)
        challenge = _challenge(self.challenge_key)
        _exact(self.slot, DossierSlot, "/slot")
        _exact(self.claim_role, DossierClaimRole, "/claim_role")
        _exact(self.claim_owner, EvidenceOwnerRole, "/claim_owner")
        manifest_ref = _copy_manifest_ref(
            self.evidence_manifest_ref, challenge, "/evidence_manifest_ref"
        )
        if manifest_ref.slot is not self.slot:
            raise _invalid(
                "/evidence_manifest_ref", CredibilityIssueCode.IDENTITY_MISMATCH
            )
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "evidence_manifest_ref", manifest_ref)
        object.__setattr__(
            self,
            "claim_scope_ref",
            _copy_claim_scope(self.claim_scope_ref, challenge, "/claim_scope_ref"),
        )
        object.__setattr__(self, "source_id", _identifier(self.source_id, "/source_id"))
        object.__setattr__(
            self, "source_version", _version(self.source_version, "/source_version")
        )
        object.__setattr__(
            self,
            "evidence_ref",
            _copy_evidence(self.evidence_ref, challenge, "/evidence_ref"),
        )


@dataclass(frozen=True, slots=True, repr=False)
class CredibilityCrosswalkRef(_ProtectedRecord):
    challenge_key: ChallengeKey
    crosswalk_id: str
    crosswalk_version: str
    content_digest: str
    origin: StructuralOrigin
    schema_version: str = CREDIBILITY_SCHEMA_VERSION
    canonicalization_profile: str = CREDIBILITY_CANONICALIZATION_PROFILE

    def __post_init__(self) -> None:
        if type(self) is not CredibilityCrosswalkRef:
            raise _invalid("/ref_type", CredibilityIssueCode.IDENTITY_MISMATCH)
        _exact(self.origin, StructuralOrigin, "/origin")
        if (
            type(self.schema_version) is not str
            or self.schema_version != CREDIBILITY_SCHEMA_VERSION
            or type(self.canonicalization_profile) is not str
            or self.canonicalization_profile != CREDIBILITY_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version", CredibilityIssueCode.IDENTITY_MISMATCH)
        object.__setattr__(self, "challenge_key", _challenge(self.challenge_key))
        object.__setattr__(
            self, "crosswalk_id", _identifier(self.crosswalk_id, "/crosswalk_id")
        )
        object.__setattr__(
            self,
            "crosswalk_version",
            _version(self.crosswalk_version, "/crosswalk_version"),
        )
        object.__setattr__(self, "content_digest", _digest(self.content_digest))


@dataclass(frozen=True, slots=True, repr=False)
class CredibilityCrosswalk(_ProtectedRecord):
    challenge_key: ChallengeKey
    crosswalk_id: str
    crosswalk_version: str
    dossier_ref: ValidationDossierRef
    evidence_manifest_refs: tuple[DossierEvidenceManifestRef, ...]
    sources: tuple[CredibilityEvidenceSource, ...]
    links: tuple[ClaimEvidenceLink, ...]
    origin: StructuralOrigin
    supersedes: CredibilityCrosswalkRef | None = None
    schema_version: str = CREDIBILITY_SCHEMA_VERSION
    canonicalization_profile: str = CREDIBILITY_CANONICALIZATION_PROFILE

    def __post_init__(self) -> None:
        if type(self) is not CredibilityCrosswalk:
            raise _invalid("/crosswalk_type", CredibilityIssueCode.IDENTITY_MISMATCH)
        challenge = _challenge(self.challenge_key)
        crosswalk_id = _identifier(self.crosswalk_id, "/crosswalk_id")
        crosswalk_version = _version(self.crosswalk_version, "/crosswalk_version")
        _exact(self.origin, StructuralOrigin, "/origin")
        if (
            type(self.schema_version) is not str
            or self.schema_version != CREDIBILITY_SCHEMA_VERSION
            or type(self.canonicalization_profile) is not str
            or self.canonicalization_profile != CREDIBILITY_CANONICALIZATION_PROFILE
        ):
            raise _invalid("/schema_version", CredibilityIssueCode.IDENTITY_MISMATCH)
        dossier = _copy_dossier_ref(self.dossier_ref, challenge, "/dossier_ref")
        if type(self.evidence_manifest_refs) is not tuple:
            raise _invalid(
                "/evidence_manifest_refs", CredibilityIssueCode.IDENTITY_MISMATCH
            )
        manifest_refs = tuple(
            _copy_manifest_ref(item, challenge, f"/evidence_manifest_refs/{index}")
            for index, item in enumerate(self.evidence_manifest_refs)
        )
        slots = tuple(item.slot for item in manifest_refs)
        if len(set(slots)) != len(slots):
            raise _invalid(
                "/evidence_manifest_refs", CredibilityIssueCode.DUPLICATE_IDENTITY
            )
        if set(slots) != set(DOSSIER_SLOT_ORDER):
            raise _invalid(
                "/evidence_manifest_refs",
                CredibilityIssueCode.MISSING_REQUIRED_EVIDENCE,
            )
        manifest_refs = tuple(
            sorted(manifest_refs, key=lambda item: _SLOT_INDEX[item.slot])
        )
        if type(self.sources) is not tuple or type(self.links) is not tuple:
            raise _invalid("/sources", CredibilityIssueCode.IDENTITY_MISMATCH)
        sources: list[CredibilityEvidenceSource] = []
        for index, value in enumerate(self.sources):
            item = _exact(value, CredibilityEvidenceSource, f"/sources/{index}")
            _same_challenge(item.challenge_key, challenge, f"/sources/{index}")
            sources.append(item)
        source_keys = tuple((item.source_id, item.source_version) for item in sources)
        if len(set(source_keys)) != len(source_keys):
            raise _invalid("/sources", CredibilityIssueCode.DUPLICATE_IDENTITY)
        evidence_keys = tuple(
            (
                item.evidence_ref.evidence_class,
                item.evidence_ref.evidence_id,
                item.evidence_ref.evidence_version,
            )
            for item in sources
            if item.evidence_ref is not None
        )
        if len(set(evidence_keys)) != len(evidence_keys):
            raise _invalid("/sources", CredibilityIssueCode.DUPLICATE_IDENTITY)
        if not set(REQUIRED_SOURCE_KINDS).issubset(
            {item.source_kind for item in sources}
        ):
            raise _invalid("/sources", CredibilityIssueCode.MISSING_REQUIRED_EVIDENCE)
        links: list[ClaimEvidenceLink] = []
        valid_sources = set(source_keys)
        valid_manifests = set(manifest_refs)
        for index, value in enumerate(self.links):
            item = _exact(value, ClaimEvidenceLink, f"/links/{index}")
            _same_challenge(item.challenge_key, challenge, f"/links/{index}")
            if (item.source_id, item.source_version) not in valid_sources:
                raise _invalid(
                    f"/links/{index}/source_id", CredibilityIssueCode.IDENTITY_MISMATCH
                )
            if item.evidence_manifest_ref not in valid_manifests:
                raise _invalid(
                    f"/links/{index}/evidence_manifest_ref",
                    CredibilityIssueCode.IDENTITY_MISMATCH,
                )
            links.append(item)
        link_keys = tuple(
            (
                item.slot,
                item.claim_role,
                item.claim_scope_ref.object_id,
                item.claim_scope_ref.object_version,
                item.evidence_ref.evidence_class,
                item.evidence_ref.evidence_id,
                item.evidence_ref.evidence_version,
                item.source_id,
                item.source_version,
            )
            for item in links
        )
        if len(set(link_keys)) != len(link_keys):
            raise _invalid("/links", CredibilityIssueCode.DUPLICATE_IDENTITY)
        predecessor = self.supersedes
        if predecessor is not None:
            predecessor = _exact(predecessor, CredibilityCrosswalkRef, "/supersedes")
            _same_challenge(predecessor.challenge_key, challenge, "/supersedes")
            if (
                predecessor.crosswalk_id != crosswalk_id
                or predecessor.crosswalk_version == crosswalk_version
            ):
                raise _invalid("/supersedes", CredibilityIssueCode.IDENTITY_MISMATCH)
        sources.sort(
            key=lambda item: (
                item.source_kind.value,
                item.source_id,
                item.source_version,
            )
        )
        links.sort(
            key=lambda item: (
                _SLOT_INDEX[item.slot],
                item.claim_role.value,
                item.evidence_ref.evidence_id,
                item.evidence_ref.evidence_version,
                item.source_id,
            )
        )
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(self, "crosswalk_id", crosswalk_id)
        object.__setattr__(self, "crosswalk_version", crosswalk_version)
        object.__setattr__(self, "dossier_ref", dossier)
        object.__setattr__(self, "evidence_manifest_refs", manifest_refs)
        object.__setattr__(self, "sources", tuple(sources))
        object.__setattr__(self, "links", tuple(links))
        object.__setattr__(self, "supersedes", predecessor)

    @property
    def effective_origin(self) -> StructuralOrigin:
        return effective_structural_origin(
            self.origin,
            self.dossier_ref.origin,
            *(item.origin for item in self.evidence_manifest_refs),
            *(item.effective_origin for item in self.sources),
            *(() if self.supersedes is None else (self.supersedes.origin,)),
        )


@dataclass(frozen=True, slots=True)
class CredibilityIssue:
    code: CredibilityIssueCode
    path: str

    def __post_init__(self) -> None:
        if type(self) is not CredibilityIssue:
            raise TypeError("issue must have its exact nominal type")
        if type(self.code) is not CredibilityIssueCode or type(self.path) is not str:
            raise TypeError("issue code/path must have exact closed types")


@dataclass(frozen=True, slots=True)
class CredibilityAssessment:
    issues: tuple[CredibilityIssue, ...]
    all_required_claims_supported: bool
    certifies_scientific_adequacy: bool = False

    def __post_init__(self) -> None:
        if type(self) is not CredibilityAssessment:
            raise TypeError("assessment must have its exact nominal type")
        if type(self.issues) is not tuple or any(
            type(item) is not CredibilityIssue for item in self.issues
        ):
            raise TypeError("issues must be exact CredibilityIssue values")
        if type(self.all_required_claims_supported) is not bool:
            raise TypeError("support state must be an exact bool")
        if self.certifies_scientific_adequacy is not False:
            raise ValueError(
                "credibility assessment cannot certify scientific adequacy"
            )


SOURCE_KIND_ALLOWED_CLAIMS = MappingProxyType(
    {
        EvidenceSourceKind.ANALYTIC_SEMI_ANALYTIC_REFERENCE: frozenset(
            {
                DossierClaimRole.PHYSICAL_SYSTEM_ADEQUACY,
                DossierClaimRole.CLAIM_ENVELOPE_ADEQUACY,
                DossierClaimRole.IMPLEMENTATION_VERIFICATION,
                DossierClaimRole.DISCRETIZATION_CONVERGENCE,
                DossierClaimRole.REFERENCE_AGREEMENT,
                DossierClaimRole.LIMITING_CASE_BEHAVIOR,
            }
        ),
        EvidenceSourceKind.MMS_CODE_VERIFICATION: frozenset(
            {
                DossierClaimRole.IMPLEMENTATION_VERIFICATION,
                DossierClaimRole.DISCRETIZATION_CONVERGENCE,
                DossierClaimRole.REFERENCE_AGREEMENT,
                DossierClaimRole.LIMITING_CASE_BEHAVIOR,
            }
        ),
        EvidenceSourceKind.CONVERGED_NUMERICAL_PRIMARY: frozenset(
            {
                DossierClaimRole.REFERENCE_ADEQUACY,
                DossierClaimRole.DISCRETIZATION_CONVERGENCE,
                DossierClaimRole.REFERENCE_AGREEMENT,
            }
        ),
        EvidenceSourceKind.INDEPENDENT_WITNESS: frozenset(
            {DossierClaimRole.REFERENCE_ADEQUACY, DossierClaimRole.REFERENCE_AGREEMENT}
        ),
        EvidenceSourceKind.EXPERIMENTAL_VALIDATION: frozenset(
            {
                DossierClaimRole.PHYSICAL_SYSTEM_ADEQUACY,
                DossierClaimRole.CLAIM_ENVELOPE_ADEQUACY,
                DossierClaimRole.TARGET_POPULATION_ADEQUACY,
                DossierClaimRole.REFERENCE_ADEQUACY,
                DossierClaimRole.MEASUREMENT_ADEQUACY,
            }
        ),
        EvidenceSourceKind.INDUSTRIAL_GOLDEN: frozenset(
            {
                DossierClaimRole.CUSTOMER_CONTEXT_OF_USE,
                DossierClaimRole.PRODUCT_QUALIFICATION,
            }
        ),
        EvidenceSourceKind.QUALIFIED_ACCELERATOR_SURROGATE: frozenset(
            {DossierClaimRole.REFERENCE_ADEQUACY, DossierClaimRole.REFERENCE_AGREEMENT}
        ),
        EvidenceSourceKind.POPULATION_EVIDENCE: frozenset(
            {
                DossierClaimRole.TARGET_POPULATION_ADEQUACY,
                DossierClaimRole.SAMPLING_PLAN_ADEQUACY,
            }
        ),
        EvidenceSourceKind.GENERATOR_CONFORMANCE: frozenset(
            {
                DossierClaimRole.GENERATOR_IMPLEMENTATION_INTEGRITY,
                DossierClaimRole.GENERATOR_DISTRIBUTION_CONFORMANCE,
                DossierClaimRole.GENERATOR_CONFORMANCE_DIAGNOSTIC,
            }
        ),
        EvidenceSourceKind.RECONSTRUCTION_EVIDENCE: frozenset(
            {
                DossierClaimRole.IMPLEMENTATION_VERIFICATION,
                DossierClaimRole.STATISTICAL_SUFFICIENCY,
                DossierClaimRole.DECISION_RESOLUTION_DIAGNOSTIC,
            }
        ),
        EvidenceSourceKind.REPRESENTATION_EVIDENCE: frozenset(
            {DossierClaimRole.REPRESENTATION_FIDELITY}
        ),
        EvidenceSourceKind.MEASUREMENT_EVIDENCE: frozenset(
            {
                DossierClaimRole.MEASUREMENT_ADEQUACY,
                DossierClaimRole.MEASUREMENT_FLOOR_DIAGNOSTIC,
            }
        ),
        EvidenceSourceKind.REFERENCE_INDEPENDENCE: frozenset(
            {DossierClaimRole.REFERENCE_ADEQUACY, DossierClaimRole.REFERENCE_AGREEMENT}
        ),
        EvidenceSourceKind.UNCERTAINTY_EVIDENCE: frozenset(
            {
                DossierClaimRole.STATISTICAL_SUFFICIENCY,
                DossierClaimRole.DECISION_RESOLUTION_DIAGNOSTIC,
                DossierClaimRole.CENSORING_LIMITATIONS,
            }
        ),
        EvidenceSourceKind.SECURITY_ROLE_SEPARATION: frozenset(
            {DossierClaimRole.SECRECY_ROLE_SEPARATION}
        ),
        EvidenceSourceKind.DECISION_RESOLUTION: frozenset(
            {
                DossierClaimRole.STATISTICAL_SUFFICIENCY,
                DossierClaimRole.DECISION_RESOLUTION_DIAGNOSTIC,
            }
        ),
        EvidenceSourceKind.LIMITATION_DISCLOSURE: frozenset(
            {
                DossierClaimRole.CENSORING_LIMITATIONS,
                DossierClaimRole.RESIDUAL_LIMITATION_DISCLOSURE,
            }
        ),
    }
)


_INDEPENDENT_CATEGORIES = frozenset(
    {
        EvidenceCategory.QUALIFIED_CARBON_EVIDENCE,
        EvidenceCategory.INDEPENDENT_REPLICATION,
        EvidenceCategory.COMMERCIAL_VALIDATION,
        EvidenceCategory.PRODUCTION_QUALIFICATION,
    }
)
_INDEPENDENT_KINDS = frozenset(
    {EvidenceSourceKind.INDEPENDENT_WITNESS, EvidenceSourceKind.REFERENCE_INDEPENDENCE}
)


def _evidence_key(value: DossierEvidenceRef) -> tuple[object, ...]:
    return (
        value.evidence_class,
        value.evidence_id,
        value.evidence_version,
        value.content_digest,
        value.origin,
    )


def _claim_scope_key(value: object) -> tuple[object, ...]:
    return (value.object_id, value.object_version, value.content_digest)


def _expected_claim_key(slot: DossierSlot, binding: object) -> tuple[object, ...]:
    return (
        slot,
        binding.claim_role,
        _claim_scope_key(binding.claim_scope_ref),
        _evidence_key(binding.evidence_ref),
    )


def _link_claim_key(value: ClaimEvidenceLink) -> tuple[object, ...]:
    return (
        value.slot,
        value.claim_role,
        _claim_scope_key(value.claim_scope_ref),
        _evidence_key(value.evidence_ref),
    )


def assess_credibility_crosswalk(
    crosswalk: CredibilityCrosswalk,
    evidence_manifests: tuple[DossierEvidenceManifest, ...],
) -> CredibilityAssessment:
    """Assess exact claim support without making any adequacy judgment."""
    value = _exact(crosswalk, CredibilityCrosswalk, "/crosswalk")
    if type(evidence_manifests) is not tuple:
        raise _invalid("/evidence_manifests", CredibilityIssueCode.IDENTITY_MISMATCH)
    issues: list[CredibilityIssue] = []

    def add(code: CredibilityIssueCode, path: str) -> None:
        issues.append(CredibilityIssue(code, path))

    supplied: dict[DossierSlot, DossierEvidenceManifest] = {}
    for index, manifest in enumerate(evidence_manifests):
        if type(manifest) is not DossierEvidenceManifest:
            add(CredibilityIssueCode.IDENTITY_MISMATCH, f"/evidence_manifests/{index}")
            continue
        if manifest.challenge_key != value.challenge_key:
            add(
                CredibilityIssueCode.IDENTITY_MISMATCH,
                f"/evidence_manifests/{index}/challenge_key",
            )
            continue
        if manifest.slot in supplied:
            add(
                CredibilityIssueCode.DUPLICATE_IDENTITY,
                f"/evidence_manifests/{index}/slot",
            )
            continue
        supplied[manifest.slot] = manifest
    if set(supplied) != set(DOSSIER_SLOT_ORDER):
        add(CredibilityIssueCode.MISSING_REQUIRED_EVIDENCE, "/evidence_manifests")

    ref_by_slot = {item.slot: item for item in value.evidence_manifest_refs}
    expected_claims: set[tuple[object, ...]] = set()
    for slot in DOSSIER_SLOT_ORDER:
        manifest = supplied.get(slot)
        if manifest is None:
            continue
        try:
            exact_ref = evidence_manifest_ref(manifest)
        except (TypeError, ValueError):
            add(
                CredibilityIssueCode.IDENTITY_MISMATCH,
                f"/evidence_manifests/{slot.value}",
            )
            continue
        if ref_by_slot.get(slot) != exact_ref:
            add(
                CredibilityIssueCode.IDENTITY_MISMATCH,
                f"/evidence_manifest_refs/{slot.value}",
            )
        for binding in manifest.claim_bindings:
            expected_claims.add(_expected_claim_key(slot, binding))

    source_by_key = {
        (item.source_id, item.source_version): item for item in value.sources
    }
    linked_claims: set[tuple[object, ...]] = set()
    for index, link in enumerate(value.links):
        path = f"/links/{index}"
        claim_key = _link_claim_key(link)
        if claim_key not in expected_claims:
            add(CredibilityIssueCode.IDENTITY_MISMATCH, f"{path}/claim")
            continue
        source = source_by_key[(link.source_id, link.source_version)]
        if source.evidence_ref is None or _evidence_key(
            source.evidence_ref
        ) != _evidence_key(link.evidence_ref):
            add(CredibilityIssueCode.IDENTITY_MISMATCH, f"{path}/evidence_ref")
            continue
        if source.availability is not EvidenceAvailability.AVAILABLE:
            add(CredibilityIssueCode.MISSING_REQUIRED_EVIDENCE, f"{path}/source")
        if source.evidence_currentness is not ArtifactCurrentness.CURRENT or any(
            item.currentness is not ArtifactCurrentness.CURRENT
            for item in source.use_refs
        ):
            add(CredibilityIssueCode.STALE_REFERENCE, f"{path}/source")
        expected_maturity = CATEGORY_AVAILABLE_MATURITY[source.category]
        if source.maturity is not expected_maturity:
            add(CredibilityIssueCode.MATURITY_OVERSTATEMENT, f"{path}/maturity")
        if (
            link.claim_role
            not in EVIDENCE_CLASS_ALLOWED_CLAIMS[link.evidence_ref.evidence_class]
        ):
            add(CredibilityIssueCode.ROLE_CLAIM_MISMATCH, f"{path}/claim_role")
        if link.claim_role not in source.permitted_claim_roles:
            add(
                CredibilityIssueCode.ROLE_CLAIM_MISMATCH,
                f"{path}/permitted_claim_roles",
            )
        if link.claim_role not in SOURCE_KIND_ALLOWED_CLAIMS[source.source_kind]:
            add(CredibilityIssueCode.UNSUPPORTED_SUBSTITUTION, f"{path}/source_kind")
        if any(
            item.disposition is HumanInputDisposition.PENDING_REQUIRED
            for item in source.human_inputs
        ):
            add(
                CredibilityIssueCode.UNRESOLVED_REQUIRED_HUMAN_INPUT,
                f"{path}/human_inputs",
            )
        needs_independence = (
            source.category in _INDEPENDENT_CATEGORIES
            or source.source_kind in _INDEPENDENT_KINDS
            or source.independence
            in {
                EvidenceIndependence.CARBON_INDEPENDENT,
                EvidenceIndependence.EXTERNAL_INDEPENDENT,
            }
        )
        if needs_independence and (
            source.owner is link.claim_owner
            or source.independence
            not in {
                EvidenceIndependence.CARBON_INDEPENDENT,
                EvidenceIndependence.EXTERNAL_INDEPENDENT,
            }
        ):
            add(CredibilityIssueCode.CIRCULAR_SELF_CERTIFICATION, f"{path}/owner")
        linked_claims.add(claim_key)

    if expected_claims - linked_claims:
        add(CredibilityIssueCode.MISSING_REQUIRED_EVIDENCE, "/links")
    issues.sort(key=lambda item: (item.path, item.code.value))
    return CredibilityAssessment(tuple(issues), not issues, False)


def validate_credibility_crosswalk(
    crosswalk: CredibilityCrosswalk,
    evidence_manifests: tuple[DossierEvidenceManifest, ...],
) -> CredibilityAssessment:
    assessment = assess_credibility_crosswalk(crosswalk, evidence_manifests)
    if assessment.issues:
        first = assessment.issues[0]
        raise CredibilityValidationError(first.code, path=first.path)
    return assessment


__all__ = (
    "CATEGORY_AVAILABLE_MATURITY",
    "CREDIBILITY_CANONICALIZATION_PROFILE",
    "CREDIBILITY_DOCUMENT_HEADER",
    "CREDIBILITY_SCHEMA_VERSION",
    "REQUIRED_AVAILABLE_REF_KINDS",
    "REQUIRED_SOURCE_KINDS",
    "SOURCE_KIND_ALLOWED_CLAIMS",
    "ClaimEvidenceLink",
    "CredibilityAssessment",
    "CredibilityCanonicalError",
    "CredibilityCrosswalk",
    "CredibilityCrosswalkRef",
    "CredibilityError",
    "CredibilityEvidenceSource",
    "CredibilityIssue",
    "CredibilityIssueCode",
    "CredibilityRef",
    "CredibilityRefKind",
    "CredibilityValidationError",
    "EvidenceAvailability",
    "EvidenceCategory",
    "EvidenceDisclosure",
    "EvidenceIndependence",
    "EvidenceMaturity",
    "EvidenceOwnerRole",
    "EvidenceSourceKind",
    "HumanInputBinding",
    "HumanInputDisposition",
    "assess_credibility_crosswalk",
    "validate_credibility_crosswalk",
)
