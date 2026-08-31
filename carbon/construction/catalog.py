"""Challenge-bound candidate assembly and parameter catalog contracts.

The values in this module are inert identity documents.  Validation is
deliberately table-driven and structural: it performs no import, lookup,
construction, execution, I/O, scoring, or resource-policy operation.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import ClassVar

from carbon.authoring.errors import AuthoringValidationError
from carbon.authoring.primitives import (
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_version_token,
)
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    PhysicalSystemSpecRef,
    TrainingSupportContractRef,
    reconstruct_top_level_ref,
)
from carbon.construction import model as m
from carbon.construction.errors import (
    ConstructionCanonicalDecodingError,
    ConstructionValidationError,
)
from carbon.construction.refs import (
    CONSTRUCTION_CANONICALIZATION_PROFILE,
    CONSTRUCTION_SCHEMA_VERSION,
    CandidateAssemblyContractRef,
    ParameterCatalogRef,
    make_authored_ref,
    reconstruct_authored_ref,
    verify_construction_ref,
)
from carbon.registry import ChallengeKey

_FORBIDDEN_RANDOMNESS_TOKENS = frozenset(
    {
        "draw",
        "draws",
        "entropy",
        "nonce",
        "nonces",
        "prng",
        "rng",
        "seed",
        "seeds",
        "ordering",
    }
)
_FORBIDDEN_RESOURCE_POLICY_TOKENS = frozenset(
    {
        "admission",
        "admit",
        "admitted",
        "budget",
        "budgets",
        "calibration",
        "calibrations",
        "ceiling",
        "ceilings",
        "deny",
        "denied",
        "enforcement",
        "forecast",
        "forecasts",
        "kill",
        "price",
        "prices",
        "quota",
        "quotas",
        "queue",
        "queues",
        "rail",
        "rails",
        "receipt",
        "receipts",
        "runtime",
        "runtimes",
        "schedule",
        "scheduled",
        "scheduling",
        "verdict",
        "verdicts",
    }
)
_FORBIDDEN_GRAPH_TOKENS = frozenset(
    {
        "edge",
        "edges",
        "graph",
        "graphs",
        "node",
        "nodes",
        "topology",
    }
)
_FORBIDDEN_CAPABILITY_TOKENS = frozenset(
    {
        "artifact",
        "artifacts",
        "blob",
        "blobs",
        "callback",
        "callbacks",
        "callable",
        "callables",
        "checkpoint",
        "checkpoints",
        "code",
        "command",
        "commands",
        "dataset",
        "datasets",
        "dependency",
        "dependencies",
        "deserialization",
        "deserialize",
        "endpoint",
        "endpoints",
        "entrypoint",
        "entrypoints",
        "environment",
        "environments",
        "executable",
        "executables",
        "fallback",
        "file",
        "files",
        "import",
        "imports",
        "implementation",
        "implementations",
        "loader",
        "loaders",
        "module",
        "modules",
        "network",
        "package",
        "packages",
        "path",
        "paths",
        "pickle",
        "repository",
        "repositories",
        "requirements",
        "reflection",
        "raw",
        "script",
        "scripts",
        "serialized",
        "source",
        "subprocess",
        "unregistered",
        "uri",
        "uris",
        "url",
        "urls",
    }
)
_FORBIDDEN_SCIENTIFIC_AUTHORITY_TOKENS = frozenset(
    {
        "authority",
        "disclosure",
        "eval",
        "evaluation",
        "evidence",
        "gate",
        "gates",
        "live",
        "measurement",
        "measurements",
        "metric",
        "metrics",
        "official",
        "p",
        "protected",
        "proposal",
        "predictions",
        "publication",
        "q",
        "qualification",
        "qualifications",
        "qualified",
        "qualify",
        "reference",
        "references",
        "score",
        "scorer",
        "scorers",
        "scores",
        "stress",
        "threshold",
        "thresholds",
        "w",
        "weight",
        "weights",
    }
)
_FORBIDDEN_RANDOMNESS_FOLDS = (
    "actualdraw",
    "blockhash",
    "drawid",
    "drawidentity",
    "entropydomain",
    "evalseed",
    "evaluationseed",
    "examid",
    "examids",
    "officialdraw",
    "officialexamoverride",
    "officialseed",
    "minerseed",
    "participantnonce",
    "participantseed",
    "prngstate",
    "randomnesspurpose",
    "randomnumbergeneratorstate",
    "randomstate",
    "realizeddraw",
    "realizedsample",
    "rngstate",
    "rngseed",
    "runnonce",
    "seedmaterial",
    "stressseed",
)
_FORBIDDEN_RESOURCE_POLICY_FOLDS = (
    "admissionpolicy",
    "admissionverdict",
    "admitresult",
    "denyresult",
    "fitresult",
    "forecastcalibration",
    "killrule",
    "policyreceipt",
    "queuechoice",
    "resourceceiling",
    "resourcepolicy",
    "retryrail",
    "runtimemeasurement",
    "schedulingchoice",
    "successprobability",
)
_FORBIDDEN_GRAPH_FOLDS = (
    "arbitrarygraph",
    "graphdefinition",
    "graphspecification",
    "participantgraph",
)
_FORBIDDEN_CAPABILITY_FOLDS = (
    "arbitrarydependency",
    "arbitrarydependencies",
    "artifactpath",
    "customdataset",
    "customcode",
    "datapath",
    "datauri",
    "dataurl",
    "executablepath",
    "executableblob",
    "filepath",
    "filereference",
    "importpath",
    "modelartifact",
    "modelweights",
    "modelpath",
    "modulepath",
    "networkendpoint",
    "packagepath",
    "participantcode",
    "rawdataset",
    "repositorypath",
    "repositoryreference",
    "serializedblob",
    "shellcommand",
    "sourcecode",
    "sourcepath",
    "statedict",
    "trainingdataset",
    "unregisteredcomposition",
)
_FORBIDDEN_SCIENTIFIC_AUTHORITY_FOLDS = (
    "consumermode",
    "evalcontrol",
    "evaldataset",
    "evalgate",
    "evaluationcontrol",
    "evaluationdataset",
    "evaluationgate",
    "gatecontrol",
    "gateoverride",
    "gatethreshold",
    "golive",
    "measurementgate",
    "hiddencase",
    "officialcase",
    "officialevaluation",
    "officialmeasurement",
    "officialmode",
    "officialselector",
    "populationp",
    "precomputedmetrics",
    "practicemode",
    "proposalq",
    "protectedcase",
    "qualificationstatus",
    "referencepolicy",
    "samplingplan",
    "scoreoverride",
    "scorepack",
    "scoringweights",
    "scorecontrol",
    "scorercontrol",
    "scientificresult",
    "targetpopulation",
    "thresholdcontrol",
    "disablegates",
    "weightw",
)


def _invalid(code: str, message: str, path: str) -> ConstructionValidationError:
    return ConstructionValidationError(code, message, path=path)


def _forbidden_authority_code(identifier: str) -> str | None:
    """Classify canonical identifiers after folding ``-`` and ``_`` aliases."""

    tokens = tuple(identifier.replace("-", "_").split("_"))
    compact = "".join(tokens)
    token_set = frozenset(tokens)

    def contains_authority(
        forbidden_tokens: frozenset[str], forbidden_folds: tuple[str, ...]
    ) -> bool:
        return bool(token_set & forbidden_tokens) or compact in forbidden_folds

    if contains_authority(_FORBIDDEN_RANDOMNESS_TOKENS, _FORBIDDEN_RANDOMNESS_FOLDS):
        return "construction.training_randomness_authority_forbidden"
    if contains_authority(
        _FORBIDDEN_RESOURCE_POLICY_TOKENS, _FORBIDDEN_RESOURCE_POLICY_FOLDS
    ):
        return "construction.resource_policy_authority_forbidden"
    if contains_authority(_FORBIDDEN_GRAPH_TOKENS, _FORBIDDEN_GRAPH_FOLDS):
        return "construction.component_graph_authority_forbidden"
    if contains_authority(_FORBIDDEN_CAPABILITY_TOKENS, _FORBIDDEN_CAPABILITY_FOLDS):
        return "construction.capability_authority_forbidden"
    if contains_authority(
        _FORBIDDEN_SCIENTIFIC_AUTHORITY_TOKENS,
        _FORBIDDEN_SCIENTIFIC_AUTHORITY_FOLDS,
    ):
        return "construction.scientific_authority_forbidden"
    return None


def _validate_authority_identifiers(
    identities: tuple[tuple[str, str], ...],
) -> None:
    for identifier, path in identities:
        code = _forbidden_authority_code(identifier)
        if code is not None:
            raise _invalid(
                code,
                "construction identity attempts to carry authority outside B-02B",
                path,
            )


def _validate_authority_identifier_allowing_exact_tokens(
    identifier: str,
    *,
    allowed_tokens: frozenset[str],
    path: str,
) -> None:
    remaining = "_".join(
        token
        for token in identifier.replace("-", "_").split("_")
        if token not in allowed_tokens
    )
    _validate_authority_identifiers(((remaining, path),))


def _validate_authority_identifier_allowing_exact_identifiers(
    identifier: str,
    *,
    allowed_identifiers: frozenset[str],
    path: str,
) -> None:
    if identifier in allowed_identifiers:
        return
    _validate_authority_identifiers(((identifier, path),))


def _validate_authority_identifiers_with_pin_context(
    identities: tuple[tuple[str, str], ...],
) -> None:
    expected_pin_tokens = frozenset(
        {
            "dependency",
            "environment",
            "executable",
            "implementation",
            "interface",
            "module",
            "package",
            "runtime",
        }
    )
    ordinary: list[tuple[str, str]] = []
    for identifier, path in identities:
        if "pin/" in path or "pins/" in path:
            _validate_authority_identifier_allowing_exact_tokens(
                identifier,
                allowed_tokens=expected_pin_tokens,
                path=path,
            )
        else:
            ordinary.append((identifier, path))
    _validate_authority_identifiers(tuple(ordinary))


def _validate_entry_authority_identifiers(entry: m.ParameterCatalogEntry) -> None:
    identities = [
        (entry.surface_id, "surface_id"),
        (entry.consumer_target.consumer_id, "consumer_target/consumer_id"),
        (entry.consumer_target.field_id, "consumer_target/field_id"),
        *(
            (tag, "public_outcome_family_tags")
            for tag in entry.public_outcome_family_tags
        ),
    ]
    if type(entry.semantic_owner_binding) is m.AssemblySemanticOwner:
        identities.append(
            (
                entry.semantic_owner_binding.local_target_id,
                "semantic_owner_binding/local_target_id",
            )
        )
    if (
        entry.value_type is m.SurfaceValueType.CANONICAL_CHOICE
        and type(entry.domain) is m.ChoiceDomain
    ):
        identities.extend(
            (choice, "domain/allowed_ids") for choice in entry.domain.allowed_ids
        )
    if type(entry.training_lever_binding) is m.BoundTrainingLever:
        _validate_authority_identifier_allowing_exact_tokens(
            entry.training_lever_binding.executable_semantics_ref.object_id,
            allowed_tokens=frozenset({"executable"}),
            path=(
                f"/entries/{entry.surface_id}/training_lever_binding/"
                "executable_semantics_ref/object_id"
            ),
        )
        for purpose in entry.training_lever_binding.randomness_purposes:
            _validate_authority_identifier_allowing_exact_identifiers(
                purpose.purpose_id,
                allowed_identifiers=frozenset({"training_draw"}),
                path=(
                    f"/entries/{entry.surface_id}/training_lever_binding/"
                    "randomness_purposes/purpose_id"
                ),
            )
            identities.append(
                (
                    purpose.role_key_label,
                    "training_lever_binding/randomness_purposes/role_key_label",
                )
            )
    if type(entry.component_slot_binding) is m.BoundComponentSelection:
        identities.append(
            (
                entry.component_slot_binding.slot_id,
                "component_slot_binding/slot_id",
            )
        )

    _validate_authority_identifiers(
        tuple(
            (identifier, f"/entries/{entry.surface_id}/{field}")
            for identifier, field in identities
        )
    )

    _validate_resource_output_identifiers(
        entry.resource_impact_tags,
        path=f"/entries/{entry.surface_id}/resource_impact_tags",
    )


def _validate_resource_output_identifiers(
    identifiers: tuple[str, ...], *, path: str
) -> None:
    for identifier in identifiers:
        if _forbidden_authority_code(identifier) is not None:
            raise _invalid(
                "construction.resource_policy_authority_forbidden",
                "static resource output cannot carry policy or external authority",
                path,
            )


def _challenge_key(value: object) -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.challenge_key_invalid",
            "challenge_key must be an exact valid A3 ChallengeKey",
            "/challenge_key",
        ) from exc


def _canonical_id(value: object, field: str) -> str:
    try:
        return validate_canonical_id(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.identifier_invalid",
            f"{field} must be an exact canonical identifier",
            f"/{field}",
        ) from exc


def _version(value: object, field: str) -> str:
    try:
        return validate_version_token(value, field)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.version_invalid",
            f"{field} must be an exact bounded version token",
            f"/{field}",
        ) from exc


def _common_document_fields(
    *,
    object_kind: object,
    expected_kind: str,
    schema_version: object,
    canonicalization_profile: object,
    challenge_key: object,
    object_id: object,
    object_version: object,
) -> tuple[str, str, ChallengeKey, str, str]:
    if type(object_kind) is not str or object_kind != expected_kind:
        raise _invalid(
            "construction.object_kind_invalid",
            "construction document has a wrong exact object kind",
            "/object_kind",
        )
    schema = _version(schema_version, "schema_version")
    if schema != CONSTRUCTION_SCHEMA_VERSION:
        raise _invalid(
            "construction.schema_version_unsupported",
            "construction v1 supports only schema version 1.0",
            "/schema_version",
        )
    if (
        type(canonicalization_profile) is not str
        or canonicalization_profile != CONSTRUCTION_CANONICALIZATION_PROFILE
    ):
        raise _invalid(
            "construction.canonicalization_profile_invalid",
            "construction document uses an unknown canonicalization profile",
            "/canonicalization_profile",
        )
    return (
        schema,
        canonicalization_profile,
        _challenge_key(challenge_key),
        _canonical_id(object_id, "object_id"),
        _version(object_version, "object_version"),
    )


def _copy_model(value: object, expected_type: type, field: str) -> object:
    if type(value) is not expected_type:
        raise _invalid(
            "construction.nominal_type_invalid",
            f"{field} must have exact nominal type {expected_type.__name__}",
            f"/{field}",
        )
    from carbon.construction.canonical import from_canonical_value, to_canonical_value

    return from_canonical_value(to_canonical_value(value), expected_type)


def _copy_union(value: object, allowed_types: tuple[type, ...], field: str) -> object:
    if type(value) not in allowed_types:
        raise _invalid(
            "construction.union_type_invalid",
            f"{field} must use one exact closed union variant",
            f"/{field}",
        )
    return _copy_model(value, type(value), field)


def _copy_top_ref(value: object, expected_type: type, field: str) -> object:
    if type(value) is not expected_type:
        raise _invalid(
            "construction.authoring_ref_type_invalid",
            f"{field} must have exact nominal type {expected_type.__name__}",
            f"/{field}",
        )
    try:
        return reconstruct_top_level_ref(value)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.authoring_ref_invalid",
            f"{field} is not a valid exact B-02A reference",
            f"/{field}",
        ) from exc


def _copy_assembly_ref(value: object) -> CandidateAssemblyContractRef:
    if type(value) is not CandidateAssemblyContractRef:
        raise _invalid(
            "construction.reference_type_invalid",
            "candidate_assembly_ref must use its exact nominal type",
            "/candidate_assembly_ref",
        )
    copied = reconstruct_authored_ref(value)
    assert type(copied) is CandidateAssemblyContractRef
    return copied


def _canonical_tuple(
    value: object,
    expected_type: type,
    field: str,
    *,
    nonempty: bool = False,
) -> tuple:
    if type(value) is not tuple:
        raise _invalid(
            "construction.tuple_type_invalid",
            f"{field} must be an exact built-in tuple",
            f"/{field}",
        )
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS or (nonempty and not value):
        raise _invalid(
            "construction.tuple_size_invalid",
            f"{field} has invalid size",
            f"/{field}",
        )
    copied = tuple(_copy_model(item, expected_type, field) for item in value)
    if len(set(copied)) != len(copied):
        raise _invalid(
            "construction.tuple_duplicate",
            f"{field} contains duplicate semantic members",
            f"/{field}",
        )
    from carbon.construction.canonical import encode_model

    return tuple(sorted(copied, key=encode_model))


def _canonical_union_tuple(
    value: object,
    allowed_types: tuple[type, ...],
    field: str,
    *,
    nonempty: bool = False,
) -> tuple:
    if type(value) is not tuple:
        raise _invalid(
            "construction.tuple_type_invalid",
            f"{field} must be an exact built-in tuple",
            f"/{field}",
        )
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS or (nonempty and not value):
        raise _invalid(
            "construction.tuple_size_invalid",
            f"{field} has invalid size",
            f"/{field}",
        )
    copied = tuple(_copy_union(item, allowed_types, field) for item in value)
    if len(set(copied)) != len(copied):
        raise _invalid(
            "construction.tuple_duplicate",
            f"{field} contains duplicate semantic members",
            f"/{field}",
        )
    from carbon.construction.canonical import encode_model

    return tuple(sorted(copied, key=encode_model))


def _scope(
    value: object, challenge_key: ChallengeKey, *, portable: bool = False
) -> None:
    m.validate_owner_ref_scope(
        value,
        expected_challenge_key=challenge_key,
        portable=portable,
    )


def _scopes(
    values: tuple[object, ...],
    challenge_key: ChallengeKey,
    *,
    portable: bool = False,
) -> None:
    for value in values:
        _scope(value, challenge_key, portable=portable)


def _validate_provenance_scope(
    provenance: m.ConstructionProvenance, challenge_key: ChallengeKey
) -> None:
    if type(provenance) is m.FixtureProvenance:
        _scope(provenance.fixture_registration_ref, challenge_key)
    else:
        assert type(provenance) is m.RegisteredProvenance
        _scope(provenance.authoring_registration_ref, challenge_key)
    _scopes(provenance.source_provenance_refs, challenge_key, portable=True)
    _scopes(provenance.origin_evidence_refs, challenge_key, portable=True)


def _validate_contribution_scope(
    contribution: m.StaticResourceContribution, challenge_key: ChallengeKey
) -> None:
    _scope(contribution.unit_ref, challenge_key, portable=True)


def _validate_entry_owner_scopes(
    entry: m.ParameterCatalogEntry, challenge_key: ChallengeKey
) -> None:
    if type(entry.unit_binding) is m.UnitNotApplicable:
        _scope(entry.unit_binding.reason_ref, challenge_key)
    else:
        assert type(entry.unit_binding) is m.BoundUnit
        _scope(entry.unit_binding.unit_ref, challenge_key, portable=True)
    if type(entry.applicability) is m.AlwaysApplicable:
        _scope(entry.applicability.applicability_ref, challenge_key)
    else:
        assert type(entry.applicability) is m.WhenSurfaceIn
        _scope(entry.applicability.applicability_ref, challenge_key)
        _scope(entry.applicability.not_applicable_reason_ref, challenge_key)
    if type(entry.semantic_owner_binding) is m.AssemblySemanticOwner:
        _scope(entry.semantic_owner_binding.authority_ref, challenge_key)
    else:
        assert type(entry.semantic_owner_binding) is m.TrainingSupportSemanticOwner
        _scope(entry.semantic_owner_binding.semantic_clause_ref, challenge_key)
        _scope(entry.semantic_owner_binding.authority_ref, challenge_key)
    if type(entry.lifecycle) is m.RetiredLifecycle:
        _scope(entry.lifecycle.reason_ref, challenge_key)
        _scope(entry.lifecycle.supersession_ref, challenge_key)
    if type(entry.training_lever_binding) is m.TrainingLeverNotApplicable:
        _scope(entry.training_lever_binding.reason_ref, challenge_key)
    else:
        assert type(entry.training_lever_binding) is m.BoundTrainingLever
        _scope(entry.training_lever_binding.executable_semantics_ref, challenge_key)
    if type(entry.component_slot_binding) is m.ComponentSelectionNotApplicable:
        _scope(entry.component_slot_binding.reason_ref, challenge_key)
    for contribution in entry.static_resource_contributions:
        _validate_contribution_scope(contribution, challenge_key)


def _validate_assembly_owner_scopes(
    assembly: CandidateAssemblyContract,
) -> None:
    key = assembly.challenge_key
    _validate_provenance_scope(assembly.provenance, key)
    for dimension in assembly.resource_dimensions:
        _scope(dimension.unit_ref, key, portable=True)
    for option in assembly.backbone_surface.options:
        _scope(option.applicability_ref, key)
        _scopes(option.assumption_refs, key)
        _scopes(option.limitation_refs, key)
        for contribution in option.static_resource_contributions:
            _validate_contribution_scope(contribution, key)
    for slot in assembly.component_slots:
        _scope(slot.applicability_ref, key)
        for option in slot.options:
            _scope(option.applicability_ref, key)
            _scopes(option.assumption_refs, key)
            _scopes(option.limitation_refs, key)
            _scopes(option.public_falsification_refs, key)
            for contribution in option.static_resource_contributions:
                _validate_contribution_scope(contribution, key)


@dataclass(frozen=True, slots=True)
class CandidateAssemblyContract:
    """One exact trusted outer candidate workflow and its closed selectors."""

    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_ref: CandidateOutputContractRef
    training_support_ref: TrainingSupportContractRef
    backbone_surface: m.BackboneSurfaceContract
    component_slots: tuple[m.ComponentSlotContract, ...]
    resource_dimensions: tuple[m.StaticResourceDimension, ...]
    dependency_pins: tuple[m.DependencyPin, ...]
    environment_pins: tuple[m.EnvironmentPin, ...]
    provenance: m.ConstructionProvenance
    unknown_or_invalid_policy: m.UnknownOrInvalidPolicy

    OBJECT_KIND: ClassVar[str] = "candidate_assembly_contract"

    def __post_init__(self) -> None:
        if type(self) is not CandidateAssemblyContract:
            raise _invalid(
                "construction.subclass_rejected",
                "CandidateAssemblyContract subclasses are rejected",
                "/type",
            )
        schema, profile, key, object_id, object_version = _common_document_fields(
            object_kind=self.object_kind,
            expected_kind=self.OBJECT_KIND,
            schema_version=self.schema_version,
            canonicalization_profile=self.canonicalization_profile,
            challenge_key=self.challenge_key,
            object_id=self.object_id,
            object_version=self.object_version,
        )
        physical_ref = _copy_top_ref(
            self.physical_system_ref,
            PhysicalSystemSpecRef,
            "physical_system_ref",
        )
        candidate_ref = _copy_top_ref(
            self.candidate_output_ref,
            CandidateOutputContractRef,
            "candidate_output_ref",
        )
        training_ref = _copy_top_ref(
            self.training_support_ref,
            TrainingSupportContractRef,
            "training_support_ref",
        )
        if any(
            ref.challenge_key != key
            for ref in (physical_ref, candidate_ref, training_ref)
        ):
            raise _invalid(
                "construction.authoring_ref_challenge_mismatch",
                "assembly B-02A refs must match its exact ChallengeKey",
                "/challenge_key",
            )
        backbone = _copy_model(
            self.backbone_surface, m.BackboneSurfaceContract, "backbone_surface"
        )
        slots = _canonical_tuple(
            self.component_slots, m.ComponentSlotContract, "component_slots"
        )
        dimensions = _canonical_tuple(
            self.resource_dimensions,
            m.StaticResourceDimension,
            "resource_dimensions",
        )
        dependency_pins = _canonical_tuple(
            self.dependency_pins, m.DependencyPin, "dependency_pins"
        )
        environment_pins = _canonical_tuple(
            self.environment_pins, m.EnvironmentPin, "environment_pins"
        )
        provenance = _copy_union(
            self.provenance,
            (m.FixtureProvenance, m.RegisteredProvenance),
            "provenance",
        )
        if type(self.unknown_or_invalid_policy) is not m.UnknownOrInvalidPolicy:
            raise _invalid(
                "construction.policy_type_invalid",
                "unknown_or_invalid_policy must use its exact closed enum type",
                "/unknown_or_invalid_policy",
            )
        if self.unknown_or_invalid_policy is not m.UnknownOrInvalidPolicy.REJECT:
            raise _invalid(
                "construction.policy_invalid",
                "unknown_or_invalid_policy must be REJECT",
                "/unknown_or_invalid_policy",
            )

        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(self, "canonicalization_profile", profile)
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "object_id", object_id)
        object.__setattr__(self, "object_version", object_version)
        object.__setattr__(self, "physical_system_ref", physical_ref)
        object.__setattr__(self, "candidate_output_ref", candidate_ref)
        object.__setattr__(self, "training_support_ref", training_ref)
        object.__setattr__(self, "backbone_surface", backbone)
        object.__setattr__(self, "component_slots", slots)
        object.__setattr__(self, "resource_dimensions", dimensions)
        object.__setattr__(self, "dependency_pins", dependency_pins)
        object.__setattr__(self, "environment_pins", environment_pins)
        object.__setattr__(self, "provenance", provenance)
        validate_candidate_assembly(self)

    def canonical_bytes(self) -> bytes:
        return candidate_assembly_canonical_bytes(self)

    def to_canonical_record(self):
        return candidate_assembly_to_canonical_record(self)

    def to_ref(self) -> CandidateAssemblyContractRef:
        return candidate_assembly_to_ref(self)


@dataclass(frozen=True, slots=True)
class ParameterCatalog:
    """One exact Strategy projection bound to an assembly and compiler."""

    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    candidate_assembly_ref: CandidateAssemblyContractRef
    training_support_ref: TrainingSupportContractRef
    compiler_identity: m.CompilerIdentity
    entries: tuple[m.ParameterCatalogEntry, ...]
    compatibility_rules: tuple[m.CompatibilityRule, ...]
    provenance: m.ConstructionProvenance
    unknown_or_invalid_policy: m.UnknownOrInvalidPolicy

    OBJECT_KIND: ClassVar[str] = "parameter_catalog"

    def __post_init__(self) -> None:
        if type(self) is not ParameterCatalog:
            raise _invalid(
                "construction.subclass_rejected",
                "ParameterCatalog subclasses are rejected",
                "/type",
            )
        schema, profile, key, object_id, object_version = _common_document_fields(
            object_kind=self.object_kind,
            expected_kind=self.OBJECT_KIND,
            schema_version=self.schema_version,
            canonicalization_profile=self.canonicalization_profile,
            challenge_key=self.challenge_key,
            object_id=self.object_id,
            object_version=self.object_version,
        )
        assembly_ref = _copy_assembly_ref(self.candidate_assembly_ref)
        training_ref = _copy_top_ref(
            self.training_support_ref,
            TrainingSupportContractRef,
            "training_support_ref",
        )
        if assembly_ref.challenge_key != key or training_ref.challenge_key != key:
            raise _invalid(
                "construction.reference_challenge_mismatch",
                "catalog refs must match its exact ChallengeKey",
                "/challenge_key",
            )
        compiler = _copy_model(
            self.compiler_identity, m.CompilerIdentity, "compiler_identity"
        )
        if (
            compiler.construction_schema_version != schema
            or compiler.canonicalization_profile != profile
        ):
            raise _invalid(
                "construction.compiler_profile_mismatch",
                "catalog compiler identity does not match its construction profile",
                "/compiler_identity",
            )
        entries = _canonical_tuple(
            self.entries, m.ParameterCatalogEntry, "entries", nonempty=True
        )
        rules = _canonical_tuple(
            self.compatibility_rules, m.CompatibilityRule, "compatibility_rules"
        )
        provenance = _copy_union(
            self.provenance,
            (m.FixtureProvenance, m.RegisteredProvenance),
            "provenance",
        )
        if type(self.unknown_or_invalid_policy) is not m.UnknownOrInvalidPolicy:
            raise _invalid(
                "construction.policy_type_invalid",
                "unknown_or_invalid_policy must use its exact closed enum type",
                "/unknown_or_invalid_policy",
            )
        if self.unknown_or_invalid_policy is not m.UnknownOrInvalidPolicy.REJECT:
            raise _invalid(
                "construction.policy_invalid",
                "unknown_or_invalid_policy must be REJECT",
                "/unknown_or_invalid_policy",
            )

        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(self, "canonicalization_profile", profile)
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "object_id", object_id)
        object.__setattr__(self, "object_version", object_version)
        object.__setattr__(self, "candidate_assembly_ref", assembly_ref)
        object.__setattr__(self, "training_support_ref", training_ref)
        object.__setattr__(self, "compiler_identity", compiler)
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "compatibility_rules", rules)
        object.__setattr__(self, "provenance", provenance)
        _validate_catalog_intrinsic(self)

    def canonical_bytes(
        self, *, candidate_assembly: CandidateAssemblyContract
    ) -> bytes:
        return parameter_catalog_canonical_bytes(
            self, candidate_assembly=candidate_assembly
        )

    def to_canonical_record(self, *, candidate_assembly: CandidateAssemblyContract):
        validate_parameter_catalog(self, candidate_assembly=candidate_assembly)
        return parameter_catalog_to_canonical_record(self)

    def to_ref(
        self, *, candidate_assembly: CandidateAssemblyContract
    ) -> ParameterCatalogRef:
        return parameter_catalog_to_ref(self, candidate_assembly=candidate_assembly)


def _require_unique_attribute(
    values: tuple,
    attribute: str,
    field: str,
    *,
    code: str = "construction.identity_collision",
) -> None:
    projected = tuple(getattr(value, attribute) for value in values)
    if len(set(projected)) != len(projected):
        raise _invalid(
            code,
            f"{field} contains duplicate {attribute} identities",
            f"/{field}",
        )


def _validate_pin_ids(
    dependencies: tuple[m.DependencyPin, ...],
    environments: tuple[m.EnvironmentPin, ...],
) -> None:
    _require_unique_attribute(dependencies, "dependency_id", "dependency_pins")
    _require_unique_attribute(environments, "environment_id", "environment_pins")


def _validate_option_pins(
    *,
    environment_pin: m.EnvironmentPin,
    dependency_pins: tuple[m.DependencyPin, ...],
    declared_environments: frozenset[m.EnvironmentPin],
    declared_dependencies: frozenset[m.DependencyPin],
    path: str,
) -> None:
    _require_unique_attribute(dependency_pins, "dependency_id", path)
    if environment_pin not in declared_environments:
        raise _invalid(
            "construction.environment_pin_undeclared",
            "option environment pin is absent from the assembly pin set",
            path,
        )
    if not frozenset(dependency_pins).issubset(declared_dependencies):
        raise _invalid(
            "construction.dependency_pin_undeclared",
            "option dependency pin is absent from the assembly pin set",
            path,
        )


def _resource_dimensions_by_id(
    assembly: CandidateAssemblyContract,
) -> dict[str, m.StaticResourceDimension]:
    return {
        dimension.dimension_id: dimension for dimension in assembly.resource_dimensions
    }


def _validate_contribution_dimension(
    contribution: m.StaticResourceContribution,
    dimensions: dict[str, m.StaticResourceDimension],
    *,
    path: str,
) -> None:
    _validate_resource_output_identifiers(contribution.impact_tags, path=path)
    dimension = dimensions.get(contribution.dimension_id)
    if dimension is None:
        raise _invalid(
            "construction.resource_dimension_unknown",
            "static resource contribution names an unknown assembly dimension",
            path,
        )
    if contribution.unit_ref != dimension.unit_ref:
        raise _invalid(
            "construction.resource_unit_mismatch",
            "static resource contribution unit differs from its assembly dimension",
            path,
        )


def _validate_assembly_authority_identifiers(
    assembly: CandidateAssemblyContract,
) -> None:
    backbone = assembly.backbone_surface
    identities: list[tuple[str, str]] = [
        (assembly.object_id, "/object_id"),
        (backbone.surface_id, "/backbone_surface/surface_id"),
        (
            backbone.consumer_target.consumer_id,
            "/backbone_surface/consumer_target/consumer_id",
        ),
        (
            backbone.consumer_target.field_id,
            "/backbone_surface/consumer_target/field_id",
        ),
    ]
    identities.extend(
        (pin.dependency_id, "/dependency_pins/dependency_id")
        for pin in assembly.dependency_pins
    )
    identities.extend(
        (pin.environment_id, "/environment_pins/environment_id")
        for pin in assembly.environment_pins
    )

    for option in backbone.options:
        base = "/backbone_surface/options"
        identities.extend(
            (
                (option.selector_token, f"{base}/selector_token"),
                (option.backbone_id, f"{base}/backbone_id"),
                (
                    option.implementation_pin.implementation_id,
                    f"{base}/implementation_pin/implementation_id",
                ),
                (
                    option.environment_pin.environment_id,
                    f"{base}/environment_pin/environment_id",
                ),
                (
                    option.input_interface_pin.interface_id,
                    f"{base}/input_interface_pin/interface_id",
                ),
                (
                    option.output_interface_pin.interface_id,
                    f"{base}/output_interface_pin/interface_id",
                ),
            )
        )
        identities.extend(
            (pin.dependency_id, f"{base}/dependency_pins/dependency_id")
            for pin in option.dependency_pins
        )

    for slot in assembly.component_slots:
        base = f"/component_slots/{slot.slot_id}"
        identities.extend(
            (
                (slot.slot_id, f"{base}/slot_id"),
                (slot.selector_surface_id, f"{base}/selector_surface_id"),
                (
                    slot.consumer_target.consumer_id,
                    f"{base}/consumer_target/consumer_id",
                ),
                (slot.consumer_target.field_id, f"{base}/consumer_target/field_id"),
                (
                    slot.input_interface_pin.interface_id,
                    f"{base}/input_interface_pin/interface_id",
                ),
                (
                    slot.output_interface_pin.interface_id,
                    f"{base}/output_interface_pin/interface_id",
                ),
            )
        )
        for option in slot.options:
            option_base = f"{base}/options"
            identities.extend(
                (
                    (option.selector_token, f"{option_base}/selector_token"),
                    (option.component_id, f"{option_base}/component_id"),
                    (
                        option.consumer_target.consumer_id,
                        f"{option_base}/consumer_target/consumer_id",
                    ),
                    (
                        option.consumer_target.field_id,
                        f"{option_base}/consumer_target/field_id",
                    ),
                    (
                        option.implementation_pin.implementation_id,
                        f"{option_base}/implementation_pin/implementation_id",
                    ),
                    (
                        option.environment_pin.environment_id,
                        f"{option_base}/environment_pin/environment_id",
                    ),
                    (
                        option.input_interface_pin.interface_id,
                        f"{option_base}/input_interface_pin/interface_id",
                    ),
                    (
                        option.output_interface_pin.interface_id,
                        f"{option_base}/output_interface_pin/interface_id",
                    ),
                )
            )
            identities.extend(
                (pin.dependency_id, f"{option_base}/dependency_pins/dependency_id")
                for pin in option.dependency_pins
            )

    _validate_authority_identifiers_with_pin_context(tuple(identities))


def validate_candidate_assembly(
    assembly: object,
) -> CandidateAssemblyContract:
    """Validate every closed, cross-nested invariant of one assembly object."""

    if type(assembly) is not CandidateAssemblyContract:
        raise _invalid(
            "construction.assembly_type_invalid",
            "assembly must have exact CandidateAssemblyContract type",
            "/candidate_assembly",
        )
    if any(
        ref.challenge_key != assembly.challenge_key
        for ref in (
            assembly.physical_system_ref,
            assembly.candidate_output_ref,
            assembly.training_support_ref,
        )
    ):
        raise _invalid(
            "construction.authoring_ref_challenge_mismatch",
            "assembly B-02A refs must match its exact ChallengeKey",
            "/challenge_key",
        )

    _validate_assembly_authority_identifiers(assembly)
    _validate_assembly_owner_scopes(assembly)
    _validate_pin_ids(assembly.dependency_pins, assembly.environment_pins)
    _require_unique_attribute(assembly.component_slots, "slot_id", "component_slots")
    _require_unique_attribute(
        assembly.component_slots, "selector_surface_id", "component_slots"
    )
    _require_unique_attribute(
        assembly.resource_dimensions, "dimension_id", "resource_dimensions"
    )
    for dimension in assembly.resource_dimensions:
        _validate_resource_output_identifiers(
            (dimension.dimension_id,), path="/resource_dimensions"
        )
    if assembly.backbone_surface.surface_id in {
        slot.selector_surface_id for slot in assembly.component_slots
    }:
        raise _invalid(
            "construction.selector_surface_collision",
            "assembly selector surface ids must be pairwise distinct",
            "/component_slots",
        )
    structural_consumers = (
        assembly.backbone_surface.consumer_target,
        *(slot.consumer_target for slot in assembly.component_slots),
    )
    if len(set(structural_consumers)) != len(structural_consumers):
        raise _invalid(
            "construction.consumer_target_collision",
            "assembly selector surfaces must have distinct consumer targets",
            "/component_slots",
        )

    all_tokens: list[str] = []
    backbone_targets: set[tuple[str, str, str]] = set()
    dimensions = _resource_dimensions_by_id(assembly)
    declared_environments = frozenset(assembly.environment_pins)
    declared_dependencies = frozenset(assembly.dependency_pins)
    for option in assembly.backbone_surface.options:
        all_tokens.append(option.selector_token)
        _validate_resource_output_identifiers(
            option.resource_impact_tags,
            path="/backbone_surface/options/resource_impact_tags",
        )
        target = (option.backbone_id, option.backbone_version, option.content_digest)
        if target in backbone_targets:
            raise _invalid(
                "construction.selector_alias",
                "backbone selector tokens must not alias one pinned option",
                "/backbone_surface/options",
            )
        backbone_targets.add(target)
        _validate_option_pins(
            environment_pin=option.environment_pin,
            dependency_pins=option.dependency_pins,
            declared_environments=declared_environments,
            declared_dependencies=declared_dependencies,
            path="/backbone_surface/options",
        )
        for contribution in option.static_resource_contributions:
            _validate_contribution_dimension(
                contribution, dimensions, path="/backbone_surface/options"
            )

    for slot in assembly.component_slots:
        option_targets: set[tuple[str, str, str]] = set()
        for option in slot.options:
            all_tokens.append(option.selector_token)
            _validate_resource_output_identifiers(
                option.resource_impact_tags,
                path="/component_slots/options/resource_impact_tags",
            )
            target = (
                option.component_id,
                option.component_version,
                option.content_digest,
            )
            if target in option_targets:
                raise _invalid(
                    "construction.selector_alias",
                    "component selector tokens must not alias one pinned option",
                    "/component_slots/options",
                )
            option_targets.add(target)
            _validate_option_pins(
                environment_pin=option.environment_pin,
                dependency_pins=option.dependency_pins,
                declared_environments=declared_environments,
                declared_dependencies=declared_dependencies,
                path="/component_slots/options",
            )
            for contribution in option.static_resource_contributions:
                _validate_contribution_dimension(
                    contribution, dimensions, path="/component_slots/options"
                )
    if len(all_tokens) != len(set(all_tokens)):
        raise _invalid(
            "construction.selector_token_collision",
            "selector tokens must be unique across all assembly selector surfaces",
            "/component_slots",
        )
    return assembly


def surface_value_in_domain(
    value: object,
    *,
    value_type: m.SurfaceValueType,
    domain: m.SurfaceDomain,
) -> bool:
    """Return exact tagged type/domain membership without coercion."""

    if type(value) is not m.SurfaceValue or value.value_type is not value_type:
        return False
    raw = value.value
    if type(domain) is m.BooleanDomain:
        return value_type is m.SurfaceValueType.BOOL and raw in domain.allowed_values
    if type(domain) is m.Int64RangeDomain:
        return (
            value_type is m.SurfaceValueType.INT64
            and type(raw) is int
            and domain.minimum <= raw <= domain.maximum
        )
    if type(domain) is m.UInt64RangeDomain:
        return (
            value_type is m.SurfaceValueType.UINT64
            and type(raw) is int
            and domain.minimum <= raw <= domain.maximum
        )
    if type(domain) is m.Float64RangeDomain:
        if value_type is not m.SurfaceValueType.FLOAT64 or type(raw) is not float:
            return False
        lower_ok = raw > domain.minimum or (
            domain.lower_inclusive and raw == domain.minimum
        )
        upper_ok = raw < domain.maximum or (
            domain.upper_inclusive and raw == domain.maximum
        )
        return lower_ok and upper_ok
    if type(domain) is m.ChoiceDomain:
        return (
            value_type
            in (
                m.SurfaceValueType.CANONICAL_CHOICE,
                m.SurfaceValueType.BACKBONE_SELECTOR,
                m.SurfaceValueType.COMPONENT_SELECTOR,
            )
            and raw in domain.allowed_ids
        )
    return False


def validate_surface_value(
    value: object, entry: object, *, path: str = "/value"
) -> m.SurfaceValue:
    """Require one exact value to inhabit one exact catalog entry domain."""

    if type(entry) is not m.ParameterCatalogEntry:
        raise _invalid(
            "construction.catalog_entry_type_invalid",
            "entry must have exact ParameterCatalogEntry type",
            "/entry",
        )
    if not surface_value_in_domain(
        value, value_type=entry.value_type, domain=entry.domain
    ):
        raise _invalid(
            "construction.surface_value_out_of_domain",
            "surface value has a wrong exact type or lies outside its closed domain",
            path,
        )
    assert type(value) is m.SurfaceValue
    return value


def _validate_entry_domain(entry: m.ParameterCatalogEntry) -> None:
    domain_type_by_value_type = {
        m.SurfaceValueType.BOOL: m.BooleanDomain,
        m.SurfaceValueType.INT64: m.Int64RangeDomain,
        m.SurfaceValueType.UINT64: m.UInt64RangeDomain,
        m.SurfaceValueType.FLOAT64: m.Float64RangeDomain,
        m.SurfaceValueType.CANONICAL_CHOICE: m.ChoiceDomain,
        m.SurfaceValueType.BACKBONE_SELECTOR: m.ChoiceDomain,
        m.SurfaceValueType.COMPONENT_SELECTOR: m.ChoiceDomain,
    }
    expected_domain = domain_type_by_value_type[entry.value_type]
    if type(entry.domain) is not expected_domain:
        raise _invalid(
            "construction.surface_domain_type_mismatch",
            "entry value type and domain variant do not exactly agree",
            f"/entries/{entry.surface_id}/domain",
        )
    if type(entry.requirement) is m.ExplicitDefaultSurface:
        validate_surface_value(
            entry.requirement.default_value,
            entry,
            path=f"/entries/{entry.surface_id}/requirement/default_value",
        )


def _catalog_graph(
    entries_by_id: dict[str, m.ParameterCatalogEntry],
) -> dict[str, frozenset[str]]:
    graph: dict[str, frozenset[str]] = {}
    known = frozenset(entries_by_id)
    for surface_id, entry in entries_by_id.items():
        dependencies = set(entry.dependency_surface_ids)
        unknown = dependencies - known
        if unknown:
            raise _invalid(
                "construction.catalog_dependency_unknown",
                "catalog dependency names an unknown surface",
                f"/entries/{surface_id}/dependency_surface_ids",
            )
        if type(entry.applicability) is m.WhenSurfaceIn:
            selector = entry.applicability.selector_surface_id
            if selector not in dependencies:
                raise _invalid(
                    "construction.applicability_dependency_missing",
                    "applicability controller must be an explicit dependency",
                    f"/entries/{surface_id}/applicability",
                )
        graph[surface_id] = frozenset(dependencies)
    return graph


def _topological_surface_ids(
    entries_by_id: dict[str, m.ParameterCatalogEntry],
) -> tuple[str, ...]:
    graph = _catalog_graph(entries_by_id)
    remaining = {
        surface_id: set(dependencies) for surface_id, dependencies in graph.items()
    }
    ordered: list[str] = []
    while remaining:
        ready = sorted(
            surface_id
            for surface_id, dependencies in remaining.items()
            if not dependencies
        )
        if not ready:
            raise _invalid(
                "construction.catalog_dependency_cycle",
                "catalog dependency and applicability graph must be acyclic",
                "/entries",
            )
        for surface_id in ready:
            ordered.append(surface_id)
            del remaining[surface_id]
        ready_set = set(ready)
        for dependencies in remaining.values():
            dependencies.difference_update(ready_set)
    return tuple(ordered)


def catalog_topological_entries(
    catalog: object,
) -> tuple[m.ParameterCatalogEntry, ...]:
    """Return the deterministic dependency order with surface-id tie breaking."""

    if type(catalog) is not ParameterCatalog:
        raise _invalid(
            "construction.catalog_type_invalid",
            "catalog must have exact ParameterCatalog type",
            "/parameter_catalog",
        )
    entries_by_id = {entry.surface_id: entry for entry in catalog.entries}
    return tuple(
        entries_by_id[surface_id]
        for surface_id in _topological_surface_ids(entries_by_id)
    )


def catalog_entries_by_surface(
    catalog: object,
) -> dict[str, m.ParameterCatalogEntry]:
    """Return a fresh closed lookup after exact catalog validation."""

    if type(catalog) is not ParameterCatalog:
        raise _invalid(
            "construction.catalog_type_invalid",
            "catalog must have exact ParameterCatalog type",
            "/parameter_catalog",
        )
    return {entry.surface_id: entry for entry in catalog.entries}


def _validate_catalog_intrinsic(catalog: ParameterCatalog) -> None:
    _validate_provenance_scope(catalog.provenance, catalog.challenge_key)
    _validate_authority_identifiers(
        (
            (catalog.object_id, "/object_id"),
            (catalog.compiler_identity.compiler_id, "/compiler_identity/compiler_id"),
            *(
                (rule.rule_id, f"/compatibility_rules/{rule.rule_id}/rule_id")
                for rule in catalog.compatibility_rules
            ),
        )
    )
    _require_unique_attribute(
        catalog.entries,
        "surface_id",
        "entries",
        code="construction.catalog_surface_duplicate",
    )
    _require_unique_attribute(
        catalog.entries,
        "consumer_target",
        "entries",
        code="construction.consumer_target_collision",
    )
    _require_unique_attribute(
        catalog.compatibility_rules,
        "rule_id",
        "compatibility_rules",
        code="construction.compatibility_rule_duplicate",
    )
    entries_by_id = {entry.surface_id: entry for entry in catalog.entries}
    rules_by_id = {rule.rule_id: rule for rule in catalog.compatibility_rules}

    top_level_entries = tuple(
        entry
        for entry in catalog.entries
        if entry.input_source is m.InputSource.TOP_LEVEL_BACKBONE
    )
    if len(top_level_entries) != 1:
        raise _invalid(
            "construction.backbone_projection_cardinality",
            "catalog must contain exactly one top-level backbone entry",
            "/entries",
        )

    for entry in catalog.entries:
        _validate_entry_authority_identifiers(entry)
        _validate_entry_owner_scopes(entry, catalog.challenge_key)
        _validate_entry_domain(entry)
        if entry.input_source is m.InputSource.TOP_LEVEL_BACKBONE and (
            entry.surface_id != "strategy_backbone"
            or entry.value_type is not m.SurfaceValueType.BACKBONE_SELECTOR
        ):
            raise _invalid(
                "construction.backbone_projection_invalid",
                "top-level backbone entry has a forbidden surface or value type",
                f"/entries/{entry.surface_id}",
            )
        if (
            entry.input_source is m.InputSource.PARAMETER_KEY
            and entry.surface_id == "strategy_backbone"
        ):
            raise _invalid(
                "construction.backbone_projection_invalid",
                "parameter-key entries cannot use strategy_backbone",
                f"/entries/{entry.surface_id}",
            )
        if (
            entry.value_type is m.SurfaceValueType.BACKBONE_SELECTOR
            and entry.input_source is not m.InputSource.TOP_LEVEL_BACKBONE
        ):
            raise _invalid(
                "construction.selector_source_invalid",
                "BACKBONE_SELECTOR is reserved for the top-level backbone entry",
                f"/entries/{entry.surface_id}",
            )
        if (
            entry.value_type is m.SurfaceValueType.COMPONENT_SELECTOR
            and entry.input_source is not m.InputSource.PARAMETER_KEY
        ):
            raise _invalid(
                "construction.selector_source_invalid",
                "COMPONENT_SELECTOR must use PARAMETER_KEY input",
                f"/entries/{entry.surface_id}",
            )
        training_owned = (
            type(entry.semantic_owner_binding) is m.TrainingSupportSemanticOwner
        )
        training_bound = type(entry.training_lever_binding) is m.BoundTrainingLever
        if training_owned != training_bound:
            raise _invalid(
                "construction.training_owner_mismatch",
                "TrainingSupport ownership and bound training levers must coincide",
                f"/entries/{entry.surface_id}/training_lever_binding",
            )
        if training_bound and (
            type(entry.component_slot_binding) is not m.ComponentSelectionNotApplicable
        ):
            raise _invalid(
                "construction.entry_role_conflict",
                "one surface cannot be both a training lever and component binding",
                f"/entries/{entry.surface_id}",
            )
        if type(entry.component_slot_binding) is m.BoundComponentSelection:
            if type(entry.semantic_owner_binding) is not m.AssemblySemanticOwner:
                raise _invalid(
                    "construction.component_owner_mismatch",
                    "component-bound surfaces require assembly semantic ownership",
                    f"/entries/{entry.surface_id}/semantic_owner_binding",
                )
            if type(entry.training_lever_binding) is not m.TrainingLeverNotApplicable:
                raise _invalid(
                    "construction.entry_role_conflict",
                    "component-bound surfaces cannot also be training levers",
                    f"/entries/{entry.surface_id}",
                )
        unknown_rules = set(entry.compatibility_rule_ids) - set(rules_by_id)
        if unknown_rules:
            raise _invalid(
                "construction.compatibility_rule_unknown",
                "catalog entry names an unknown compatibility rule",
                f"/entries/{entry.surface_id}/compatibility_rule_ids",
            )

    _topological_surface_ids(entries_by_id)
    for entry in catalog.entries:
        if type(entry.applicability) is m.WhenSurfaceIn:
            controller = entries_by_id[entry.applicability.selector_surface_id]
            for allowed in entry.applicability.allowed_values:
                validate_surface_value(
                    allowed,
                    controller,
                    path=f"/entries/{entry.surface_id}/applicability/allowed_values",
                )

    rule_memberships: dict[str, set[str]] = {
        surface_id: set() for surface_id in entries_by_id
    }
    for rule in catalog.compatibility_rules:
        _scope(rule.semantic_clause_ref, catalog.challenge_key)
        for surface_id in rule.surface_ids:
            if surface_id not in entries_by_id:
                raise _invalid(
                    "construction.compatibility_surface_unknown",
                    "compatibility rule names an unknown surface",
                    f"/compatibility_rules/{rule.rule_id}/surface_ids",
                )
            rule_memberships[surface_id].add(rule.rule_id)
        for row in rule.allowed_rows:
            for surface_id, cell in zip(rule.surface_ids, row):
                if type(cell) is m.ValueCompatibilityCell:
                    validate_surface_value(
                        cell.value,
                        entries_by_id[surface_id],
                        path=f"/compatibility_rules/{rule.rule_id}/allowed_rows",
                    )
    for entry in catalog.entries:
        if frozenset(entry.compatibility_rule_ids) != frozenset(
            rule_memberships[entry.surface_id]
        ):
            raise _invalid(
                "construction.compatibility_membership_mismatch",
                "entry compatibility ids must exactly match rules that name it",
                f"/entries/{entry.surface_id}/compatibility_rule_ids",
            )


def _validate_resource_lookup(
    contribution: m.StaticResourceContribution,
    *,
    dimensions: dict[str, m.StaticResourceDimension],
    entries_by_id: dict[str, m.ParameterCatalogEntry],
    path: str,
) -> None:
    _validate_contribution_dimension(contribution, dimensions, path=path)
    if type(contribution) is m.DiscreteLookupResourceContribution:
        selector = entries_by_id.get(contribution.selector_surface_id)
        if selector is None:
            raise _invalid(
                "construction.resource_selector_unknown",
                "resource lookup names an unknown catalog surface",
                path,
            )
        for case in contribution.cases:
            validate_surface_value(case.selector_value, selector, path=path)


def _validate_backbone_projection(
    entry: m.ParameterCatalogEntry, assembly: CandidateAssemblyContract
) -> None:
    backbone = assembly.backbone_surface
    expected_tokens = frozenset(option.selector_token for option in backbone.options)
    if (
        entry.surface_id != backbone.surface_id
        or entry.input_source is not m.InputSource.TOP_LEVEL_BACKBONE
        or entry.consumer_target != backbone.consumer_target
        or entry.value_type is not m.SurfaceValueType.BACKBONE_SELECTOR
        or type(entry.unit_binding) is not m.UnitNotApplicable
        or type(entry.domain) is not m.ChoiceDomain
        or frozenset(entry.domain.allowed_ids) != expected_tokens
        or len(entry.domain.allowed_ids) != len(expected_tokens)
        or entry.dependency_surface_ids
        or type(entry.applicability) is not m.AlwaysApplicable
        or type(entry.requirement) is not m.RequiredSurface
        or type(entry.semantic_owner_binding) is not m.AssemblySemanticOwner
        or entry.semantic_owner_binding.local_target_id != backbone.surface_id
        or type(entry.training_lever_binding) is not m.TrainingLeverNotApplicable
        or type(entry.component_slot_binding) is not m.ComponentSelectionNotApplicable
    ):
        raise _invalid(
            "construction.backbone_projection_mismatch",
            "catalog backbone entry is not the exact assembly-owned projection",
            f"/entries/{entry.surface_id}",
        )


def _validate_component_projection(
    entry: m.ParameterCatalogEntry, slot: m.ComponentSlotContract
) -> None:
    expected_tokens = frozenset(option.selector_token for option in slot.options)
    if (
        entry.input_source is not m.InputSource.PARAMETER_KEY
        or entry.surface_id != slot.selector_surface_id
        or entry.consumer_target != slot.consumer_target
        or entry.value_type is not m.SurfaceValueType.COMPONENT_SELECTOR
        or type(entry.unit_binding) is not m.UnitNotApplicable
        or type(entry.domain) is not m.ChoiceDomain
        or frozenset(entry.domain.allowed_ids) != expected_tokens
        or len(entry.domain.allowed_ids) != len(expected_tokens)
        or type(entry.semantic_owner_binding) is not m.AssemblySemanticOwner
        or entry.semantic_owner_binding.local_target_id != slot.slot_id
        or type(entry.component_slot_binding) is not m.BoundComponentSelection
        or entry.component_slot_binding.slot_id != slot.slot_id
        or entry.component_slot_binding.role is not slot.role
        or type(entry.training_lever_binding) is not m.TrainingLeverNotApplicable
    ):
        raise _invalid(
            "construction.component_projection_mismatch",
            "component selector entry is not the exact assembly-owned projection",
            f"/entries/{entry.surface_id}",
        )


def validate_parameter_catalog(
    catalog: object,
    *,
    candidate_assembly: object,
    expected_compiler_identity: object | None = None,
    reject_retired: bool = False,
) -> ParameterCatalog:
    """Validate an exact catalog against its digest-verified assembly binding.

    ``reject_retired`` is the explicit new-compilation gate; historical catalog
    identity remains representable and verifiable when this flag is false.
    """

    if type(catalog) is not ParameterCatalog:
        raise _invalid(
            "construction.catalog_type_invalid",
            "catalog must have exact ParameterCatalog type",
            "/parameter_catalog",
        )
    if type(candidate_assembly) is not CandidateAssemblyContract:
        raise _invalid(
            "construction.assembly_type_invalid",
            "candidate_assembly must have exact CandidateAssemblyContract type",
            "/candidate_assembly",
        )
    if type(reject_retired) is not bool:
        raise TypeError("reject_retired must be an exact Boolean")
    validate_candidate_assembly(candidate_assembly)
    _validate_catalog_intrinsic(catalog)
    if catalog.challenge_key != candidate_assembly.challenge_key:
        raise _invalid(
            "construction.catalog_challenge_mismatch",
            "catalog and assembly ChallengeKey differ",
            "/challenge_key",
        )
    if catalog.candidate_assembly_ref != candidate_assembly.to_ref():
        raise _invalid(
            "construction.assembly_reference_mismatch",
            "catalog does not bind the exact candidate assembly bytes",
            "/candidate_assembly_ref",
        )
    if catalog.training_support_ref != candidate_assembly.training_support_ref:
        raise _invalid(
            "construction.training_support_reference_mismatch",
            "catalog and assembly bind different TrainingSupport contracts",
            "/training_support_ref",
        )
    if expected_compiler_identity is not None and (
        type(expected_compiler_identity) is not m.CompilerIdentity
        or catalog.compiler_identity != expected_compiler_identity
    ):
        raise _invalid(
            "construction.compiler_identity_mismatch",
            "catalog compiler identity differs from the trusted compiler",
            "/compiler_identity",
        )

    entries_by_id = catalog_entries_by_surface(catalog)
    backbone_entries = tuple(
        entry
        for entry in catalog.entries
        if entry.input_source is m.InputSource.TOP_LEVEL_BACKBONE
    )
    assert len(backbone_entries) == 1
    _validate_backbone_projection(backbone_entries[0], candidate_assembly)

    slots_by_id = {slot.slot_id: slot for slot in candidate_assembly.component_slots}
    slot_by_surface = {
        slot.selector_surface_id: slot for slot in candidate_assembly.component_slots
    }
    for surface_id, slot in slot_by_surface.items():
        entry = entries_by_id.get(surface_id)
        if entry is None:
            raise _invalid(
                "construction.component_projection_missing",
                "catalog omits an assembly component selector surface",
                f"/entries/{surface_id}",
            )
        _validate_component_projection(entry, slot)

    for entry in catalog.entries:
        if reject_retired and type(entry.lifecycle) is m.RetiredLifecycle:
            raise _invalid(
                "construction.catalog_entry_retired",
                "retired catalog entries cannot enter new compilation",
                f"/entries/{entry.surface_id}/lifecycle",
            )
        if (
            entry.value_type is m.SurfaceValueType.COMPONENT_SELECTOR
            and entry.surface_id not in slot_by_surface
        ):
            raise _invalid(
                "construction.component_projection_extra",
                "catalog contains an extra component selector surface",
                f"/entries/{entry.surface_id}",
            )
        binding = entry.component_slot_binding
        if type(binding) is m.BoundComponentSelection:
            slot = slots_by_id.get(binding.slot_id)
            if (
                slot is None
                or binding.role is not slot.role
                or entry.consumer_target.consumer_id != slot.consumer_target.consumer_id
                or type(entry.semantic_owner_binding) is not m.AssemblySemanticOwner
                or entry.semantic_owner_binding.local_target_id != slot.slot_id
            ):
                raise _invalid(
                    "construction.component_binding_mismatch",
                    "component-bound entry differs from its exact assembly slot",
                    f"/entries/{entry.surface_id}/component_slot_binding",
                )
            if (
                entry.value_type is m.SurfaceValueType.COMPONENT_SELECTOR
                and entry.surface_id != slot.selector_surface_id
            ):
                raise _invalid(
                    "construction.component_projection_alias",
                    "component selector binding aliases another assembly surface",
                    f"/entries/{entry.surface_id}",
                )

    dimensions = _resource_dimensions_by_id(candidate_assembly)
    for entry in catalog.entries:
        for contribution in entry.static_resource_contributions:
            _validate_resource_lookup(
                contribution,
                dimensions=dimensions,
                entries_by_id=entries_by_id,
                path=f"/entries/{entry.surface_id}/static_resource_contributions",
            )
    for option in candidate_assembly.backbone_surface.options:
        for contribution in option.static_resource_contributions:
            _validate_resource_lookup(
                contribution,
                dimensions=dimensions,
                entries_by_id=entries_by_id,
                path="/backbone_surface/options/static_resource_contributions",
            )
    for slot in candidate_assembly.component_slots:
        for option in slot.options:
            for contribution in option.static_resource_contributions:
                _validate_resource_lookup(
                    contribution,
                    dimensions=dimensions,
                    entries_by_id=entries_by_id,
                    path="/component_slots/options/static_resource_contributions",
                )
    return catalog


def validate_catalog_against_assembly(
    catalog: object,
    assembly: object,
    assembly_ref: object,
    compiler_identity: object,
) -> ParameterCatalog:
    """Compiler-oriented exact-ref, exact-compiler, and retirement gate."""

    if type(assembly_ref) is not CandidateAssemblyContractRef:
        raise _invalid(
            "construction.reference_type_invalid",
            "assembly_ref must have exact CandidateAssemblyContractRef type",
            "/candidate_assembly_ref",
        )
    if type(assembly) is not CandidateAssemblyContract:
        raise _invalid(
            "construction.assembly_type_invalid",
            "assembly must have exact CandidateAssemblyContract type",
            "/candidate_assembly",
        )
    if assembly.to_ref() != assembly_ref:
        raise _invalid(
            "construction.assembly_reference_mismatch",
            "passed assembly bytes do not match the passed exact reference",
            "/candidate_assembly_ref",
        )
    if (
        type(catalog) is not ParameterCatalog
        or catalog.candidate_assembly_ref != assembly_ref
    ):
        raise _invalid(
            "construction.assembly_reference_mismatch",
            "catalog does not bind the passed exact assembly reference",
            "/candidate_assembly_ref",
        )
    return validate_parameter_catalog(
        catalog,
        candidate_assembly=assembly,
        expected_compiler_identity=compiler_identity,
        reject_retired=True,
    )


_ASSEMBLY_FIELDS = (
    "object_kind",
    "schema_version",
    "canonicalization_profile",
    "challenge_key",
    "object_id",
    "object_version",
    "physical_system_ref",
    "candidate_output_ref",
    "training_support_ref",
    "backbone_surface",
    "component_slots",
    "resource_dimensions",
    "dependency_pins",
    "environment_pins",
    "provenance",
    "unknown_or_invalid_policy",
)

_CATALOG_FIELDS = (
    "object_kind",
    "schema_version",
    "canonicalization_profile",
    "challenge_key",
    "object_id",
    "object_version",
    "candidate_assembly_ref",
    "training_support_ref",
    "compiler_identity",
    "entries",
    "compatibility_rules",
    "provenance",
    "unknown_or_invalid_policy",
)


def _canonical_set(values: tuple[object, ...]):
    from carbon.authoring.canonical import CanonicalTuple
    from carbon.construction.canonical import to_canonical_value

    return CanonicalTuple(
        tuple(to_canonical_value(value) for value in values), set_like=True
    )


def candidate_assembly_to_canonical_record(assembly: object):
    """Adapt one validated assembly to its exact closed top-level record."""

    validate_candidate_assembly(assembly)
    assert type(assembly) is CandidateAssemblyContract
    from carbon.authoring.canonical import CanonicalRecord, CanonicalText
    from carbon.construction.canonical import to_canonical_value

    return CanonicalRecord(
        CandidateAssemblyContract.OBJECT_KIND,
        (
            ("object_kind", CanonicalText(assembly.object_kind)),
            ("schema_version", CanonicalText(assembly.schema_version)),
            (
                "canonicalization_profile",
                CanonicalText(assembly.canonicalization_profile),
            ),
            ("challenge_key", to_canonical_value(assembly.challenge_key)),
            ("object_id", CanonicalText(assembly.object_id)),
            ("object_version", CanonicalText(assembly.object_version)),
            ("physical_system_ref", to_canonical_value(assembly.physical_system_ref)),
            ("candidate_output_ref", to_canonical_value(assembly.candidate_output_ref)),
            ("training_support_ref", to_canonical_value(assembly.training_support_ref)),
            ("backbone_surface", to_canonical_value(assembly.backbone_surface)),
            ("component_slots", _canonical_set(assembly.component_slots)),
            ("resource_dimensions", _canonical_set(assembly.resource_dimensions)),
            ("dependency_pins", _canonical_set(assembly.dependency_pins)),
            ("environment_pins", _canonical_set(assembly.environment_pins)),
            ("provenance", to_canonical_value(assembly.provenance)),
            (
                "unknown_or_invalid_policy",
                to_canonical_value(assembly.unknown_or_invalid_policy),
            ),
        ),
    )


def candidate_assembly_canonical_bytes(assembly: object) -> bytes:
    """Return the complete domain-separated assembly identity bytes."""

    record = candidate_assembly_to_canonical_record(assembly)
    assert type(assembly) is CandidateAssemblyContract
    from carbon.construction.canonical import construction_document

    return construction_document(assembly.object_kind, assembly.schema_version, record)


def candidate_assembly_to_ref(
    assembly: object,
) -> CandidateAssemblyContractRef:
    """Build the exact nominal authored ref from complete assembly bytes."""

    validate_candidate_assembly(assembly)
    assert type(assembly) is CandidateAssemblyContract
    result = make_authored_ref(
        CandidateAssemblyContractRef,
        canonical_bytes=candidate_assembly_canonical_bytes(assembly),
        challenge_key=assembly.challenge_key,
        object_id=assembly.object_id,
        object_version=assembly.object_version,
        schema_version=assembly.schema_version,
        canonicalization_profile=assembly.canonicalization_profile,
    )
    assert type(result) is CandidateAssemblyContractRef
    return result


def parameter_catalog_to_canonical_record(catalog: object):
    """Adapt an already cross-validated catalog to its exact top-level record."""

    if type(catalog) is not ParameterCatalog:
        raise _invalid(
            "construction.catalog_type_invalid",
            "catalog must have exact ParameterCatalog type",
            "/parameter_catalog",
        )
    from carbon.authoring.canonical import CanonicalRecord, CanonicalText
    from carbon.construction.canonical import to_canonical_value

    return CanonicalRecord(
        ParameterCatalog.OBJECT_KIND,
        (
            ("object_kind", CanonicalText(catalog.object_kind)),
            ("schema_version", CanonicalText(catalog.schema_version)),
            (
                "canonicalization_profile",
                CanonicalText(catalog.canonicalization_profile),
            ),
            ("challenge_key", to_canonical_value(catalog.challenge_key)),
            ("object_id", CanonicalText(catalog.object_id)),
            ("object_version", CanonicalText(catalog.object_version)),
            (
                "candidate_assembly_ref",
                to_canonical_value(catalog.candidate_assembly_ref),
            ),
            ("training_support_ref", to_canonical_value(catalog.training_support_ref)),
            ("compiler_identity", to_canonical_value(catalog.compiler_identity)),
            ("entries", _canonical_set(catalog.entries)),
            ("compatibility_rules", _canonical_set(catalog.compatibility_rules)),
            ("provenance", to_canonical_value(catalog.provenance)),
            (
                "unknown_or_invalid_policy",
                to_canonical_value(catalog.unknown_or_invalid_policy),
            ),
        ),
    )


def parameter_catalog_canonical_bytes(
    catalog: object, *, candidate_assembly: object
) -> bytes:
    """Return catalog identity bytes only after exact assembly validation."""

    validate_parameter_catalog(catalog, candidate_assembly=candidate_assembly)
    assert type(catalog) is ParameterCatalog
    from carbon.construction.canonical import construction_document

    return construction_document(
        catalog.object_kind,
        catalog.schema_version,
        parameter_catalog_to_canonical_record(catalog),
    )


def parameter_catalog_to_ref(
    catalog: object, *, candidate_assembly: object
) -> ParameterCatalogRef:
    """Build the exact catalog ref after complete cross-object validation."""

    validate_parameter_catalog(catalog, candidate_assembly=candidate_assembly)
    assert type(catalog) is ParameterCatalog
    result = make_authored_ref(
        ParameterCatalogRef,
        canonical_bytes=parameter_catalog_canonical_bytes(
            catalog, candidate_assembly=candidate_assembly
        ),
        challenge_key=catalog.challenge_key,
        object_id=catalog.object_id,
        object_version=catalog.object_version,
        schema_version=catalog.schema_version,
        canonicalization_profile=catalog.canonicalization_profile,
    )
    assert type(result) is ParameterCatalogRef
    return result


def _decoding_error(message: str) -> ConstructionCanonicalDecodingError:
    return ConstructionCanonicalDecodingError(
        "construction.canonical_document_value_invalid", message
    )


def _decoded_text(fields: dict, name: str) -> str:
    from carbon.authoring.canonical import CanonicalText

    value = fields[name]
    if type(value) is not CanonicalText:
        raise _decoding_error(f"{name} must be exact canonical TEXT")
    return value.value


def _decoded_set(fields: dict, name: str, expected_type: type) -> tuple:
    from carbon.authoring.canonical import CanonicalTuple
    from carbon.construction.canonical import from_canonical_value

    value = fields[name]
    if type(value) is not CanonicalTuple:
        raise _decoding_error(f"{name} must be an exact canonical tuple")
    return tuple(from_canonical_value(item, expected_type) for item in value.items)


def _decoded_provenance(value: object) -> m.ConstructionProvenance:
    from carbon.authoring.canonical import CanonicalUnion
    from carbon.construction.canonical import from_canonical_value

    if type(value) is not CanonicalUnion:
        raise _decoding_error("provenance must use one exact closed union tag")
    expected = {
        "FIXTURE": m.FixtureProvenance,
        "REGISTERED": m.RegisteredProvenance,
    }.get(value.tag)
    if expected is None:
        raise _decoding_error("provenance has an unknown union tag")
    result = from_canonical_value(value, expected)
    assert type(result) in (m.FixtureProvenance, m.RegisteredProvenance)
    return result


def decode_candidate_assembly(
    payload: object,
    *,
    expected_ref: object,
) -> CandidateAssemblyContract:
    """Decode, reconstruct, scope-check, and byte-verify one exact assembly."""

    from carbon.authoring.canonical import top_level_ref_from_canonical
    from carbon.construction.canonical import decode_document, from_canonical_value

    decoded = decode_document(
        payload,
        expected_object_kind=CandidateAssemblyContract.OBJECT_KIND,
        expected_schema_version=CONSTRUCTION_SCHEMA_VERSION,
        allowed_record_fields=_ASSEMBLY_FIELDS,
    )
    fields = dict(decoded.record.field_map())
    try:
        result = CandidateAssemblyContract(
            object_kind=_decoded_text(fields, "object_kind"),
            schema_version=_decoded_text(fields, "schema_version"),
            canonicalization_profile=_decoded_text(fields, "canonicalization_profile"),
            challenge_key=from_canonical_value(fields["challenge_key"], ChallengeKey),
            object_id=_decoded_text(fields, "object_id"),
            object_version=_decoded_text(fields, "object_version"),
            physical_system_ref=top_level_ref_from_canonical(
                fields["physical_system_ref"]
            ),
            candidate_output_ref=top_level_ref_from_canonical(
                fields["candidate_output_ref"]
            ),
            training_support_ref=top_level_ref_from_canonical(
                fields["training_support_ref"]
            ),
            backbone_surface=from_canonical_value(
                fields["backbone_surface"], m.BackboneSurfaceContract
            ),
            component_slots=_decoded_set(
                fields, "component_slots", m.ComponentSlotContract
            ),
            resource_dimensions=_decoded_set(
                fields, "resource_dimensions", m.StaticResourceDimension
            ),
            dependency_pins=_decoded_set(fields, "dependency_pins", m.DependencyPin),
            environment_pins=_decoded_set(fields, "environment_pins", m.EnvironmentPin),
            provenance=_decoded_provenance(fields["provenance"]),
            unknown_or_invalid_policy=m.UnknownOrInvalidPolicy(
                _decoded_text(fields, "unknown_or_invalid_policy")
            ),
        )
    except ConstructionCanonicalDecodingError:
        raise
    except (TypeError, ValueError) as exc:
        raise _decoding_error(
            "assembly record contains an invalid exact value"
        ) from exc
    if type(payload) is not bytes or not hmac.compare_digest(
        result.canonical_bytes(), payload
    ):
        raise _decoding_error("assembly document is not in its unique canonical form")
    if type(expected_ref) is not CandidateAssemblyContractRef:
        raise _decoding_error(
            "expected_ref must be an exact CandidateAssemblyContractRef"
        )
    verify_construction_ref(
        expected_ref,
        canonical_bytes=payload,
        challenge_key=result.challenge_key,
        object_id=result.object_id,
        object_version=result.object_version,
    )
    return result


def decode_parameter_catalog(
    payload: object,
    *,
    candidate_assembly: object,
    expected_ref: object,
) -> ParameterCatalog:
    """Decode and cross-validate one exact catalog against its assembly."""

    from carbon.authoring.canonical import top_level_ref_from_canonical
    from carbon.construction.canonical import decode_document, from_canonical_value

    decoded = decode_document(
        payload,
        expected_object_kind=ParameterCatalog.OBJECT_KIND,
        expected_schema_version=CONSTRUCTION_SCHEMA_VERSION,
        allowed_record_fields=_CATALOG_FIELDS,
    )
    fields = dict(decoded.record.field_map())
    try:
        result = ParameterCatalog(
            object_kind=_decoded_text(fields, "object_kind"),
            schema_version=_decoded_text(fields, "schema_version"),
            canonicalization_profile=_decoded_text(fields, "canonicalization_profile"),
            challenge_key=from_canonical_value(fields["challenge_key"], ChallengeKey),
            object_id=_decoded_text(fields, "object_id"),
            object_version=_decoded_text(fields, "object_version"),
            candidate_assembly_ref=from_canonical_value(
                fields["candidate_assembly_ref"], CandidateAssemblyContractRef
            ),
            training_support_ref=top_level_ref_from_canonical(
                fields["training_support_ref"]
            ),
            compiler_identity=from_canonical_value(
                fields["compiler_identity"], m.CompilerIdentity
            ),
            entries=_decoded_set(fields, "entries", m.ParameterCatalogEntry),
            compatibility_rules=_decoded_set(
                fields, "compatibility_rules", m.CompatibilityRule
            ),
            provenance=_decoded_provenance(fields["provenance"]),
            unknown_or_invalid_policy=m.UnknownOrInvalidPolicy(
                _decoded_text(fields, "unknown_or_invalid_policy")
            ),
        )
        validate_parameter_catalog(result, candidate_assembly=candidate_assembly)
    except ConstructionCanonicalDecodingError:
        raise
    except (TypeError, ValueError) as exc:
        raise _decoding_error("catalog record contains an invalid exact value") from exc
    if type(payload) is not bytes or not hmac.compare_digest(
        result.canonical_bytes(candidate_assembly=candidate_assembly), payload
    ):
        raise _decoding_error("catalog document is not in its unique canonical form")
    if type(expected_ref) is not ParameterCatalogRef:
        raise _decoding_error("expected_ref must be an exact ParameterCatalogRef")
    verify_construction_ref(
        expected_ref,
        canonical_bytes=payload,
        challenge_key=result.challenge_key,
        object_id=result.object_id,
        object_version=result.object_version,
    )
    return result


__all__ = [
    "CandidateAssemblyContract",
    "ParameterCatalog",
    "candidate_assembly_canonical_bytes",
    "candidate_assembly_to_canonical_record",
    "candidate_assembly_to_ref",
    "catalog_entries_by_surface",
    "catalog_topological_entries",
    "decode_candidate_assembly",
    "decode_parameter_catalog",
    "parameter_catalog_canonical_bytes",
    "parameter_catalog_to_canonical_record",
    "parameter_catalog_to_ref",
    "surface_value_in_domain",
    "validate_candidate_assembly",
    "validate_catalog_against_assembly",
    "validate_parameter_catalog",
    "validate_surface_value",
]
