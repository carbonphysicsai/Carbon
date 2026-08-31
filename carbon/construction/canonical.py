"""Closed B-02B construction canonical adapters and document framing."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from types import MappingProxyType
from typing import NamedTuple

from carbon.authoring.canonical import (
    CanonicalFloat64,
    CanonicalInt64,
    CanonicalNominalRef,
    CanonicalRecord,
    CanonicalText,
    CanonicalTuple,
    CanonicalUInt64,
    CanonicalUnion,
    CanonicalValue,
    challenge_key_from_canonical,
    challenge_key_to_canonical,
    decode_value,
    encode_value,
    owner_ref_from_canonical,
    owner_ref_to_canonical,
    top_level_ref_from_canonical,
    top_level_ref_to_canonical,
)
from carbon.authoring.canonical import (
    tagged_sha256 as authoring_tagged_sha256,
)
from carbon.authoring.errors import AuthoringError
from carbon.authoring.primitives import (
    MAX_CANONICAL_DOCUMENT_BYTES,
    validate_version_token,
)
from carbon.authoring.refs import is_owner_ref, is_top_level_ref
from carbon.construction import model as m
from carbon.construction.errors import (
    ConstructionCanonicalDecodingError,
    ConstructionCanonicalEncodingError,
    ConstructionReferenceMismatchError,
    ConstructionValidationError,
)
from carbon.construction.refs import (
    AUTHORED_CONSTRUCTION_REF_TYPES,
    CONSTRUCTION_CANONICALIZATION_PROFILE,
    CONSTRUCTION_REF_TYPES,
    CONSTRUCTION_SCHEMA_VERSION,
    ConstructionRef,
    is_construction_ref,
    reconstruct_construction_ref,
)
from carbon.registry import ChallengeKey

CONSTRUCTION_DOCUMENT_HEADER = b"carbon.construction.canonical.v1\x00"
CONSTRUCTION_OBJECT_KINDS = (
    "candidate_assembly_contract",
    "parameter_catalog",
    "resolved_training_sampling_policy",
    "resolved_construction_plan",
)


@dataclass(frozen=True, slots=True)
class DecodedConstructionDocument:
    """One validated construction frame and its exact canonical record."""

    object_kind: str
    schema_version: str
    record: CanonicalRecord

    def __post_init__(self) -> None:
        if type(self) is not DecodedConstructionDocument:
            raise _decoding_error(
                "construction.decoded_document_subclass_rejected",
                "decoded document must use its exact nominal type",
            )


def _encoding_error(code: str, message: str) -> ConstructionCanonicalEncodingError:
    return ConstructionCanonicalEncodingError(code, message)


def _decoding_error(code: str, message: str) -> ConstructionCanonicalDecodingError:
    return ConstructionCanonicalDecodingError(code, message)


def _required_document_text(record: CanonicalRecord, field: str) -> str:
    value = record.field_map().get(field)
    if type(value) is not CanonicalText:
        raise _encoding_error(
            "construction.canonical_document_field_invalid",
            "construction identity fields must be exact canonical text",
        )
    return value.value


def construction_document(
    object_kind: object,
    schema_version: object,
    record: CanonicalRecord,
) -> bytes:
    """Frame one exact closed construction record with B-02B domain separation."""

    if type(object_kind) is not str or object_kind not in CONSTRUCTION_OBJECT_KINDS:
        raise _encoding_error(
            "construction.object_kind_unknown",
            "object kind is outside the closed B-02B document registry",
        )
    try:
        schema = validate_version_token(schema_version, "schema_version")
    except ValueError as exc:
        raise _encoding_error(
            "construction.schema_version_invalid",
            "schema version is not canonical",
        ) from exc
    if schema != CONSTRUCTION_SCHEMA_VERSION:
        raise _encoding_error(
            "construction.schema_version_unsupported",
            "construction v1 supports only schema version 1.0",
        )
    if type(record) is not CanonicalRecord or record.record_type != object_kind:
        raise _encoding_error(
            "construction.canonical_record_kind_mismatch",
            "top-level record type must equal its framed object kind",
        )
    if _required_document_text(record, "object_kind") != object_kind:
        raise _encoding_error(
            "construction.canonical_record_kind_mismatch",
            "record object kind differs from its frame",
        )
    if _required_document_text(record, "schema_version") != schema:
        raise _encoding_error(
            "construction.canonical_schema_version_mismatch",
            "record schema version differs from its frame",
        )
    if (
        _required_document_text(record, "canonicalization_profile")
        != CONSTRUCTION_CANONICALIZATION_PROFILE
    ):
        raise _encoding_error(
            "construction.canonicalization_profile_invalid",
            "record canonicalization profile is not construction v1",
        )
    try:
        document = CONSTRUCTION_DOCUMENT_HEADER + encode_value(record)
    except AuthoringError as exc:
        raise _encoding_error(
            "construction.canonical_encoding_failed",
            "construction document cannot be encoded",
        ) from exc
    if len(document) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise _encoding_error(
            "construction.canonical_document_too_large",
            "construction document exceeds the v1 byte bound",
        )
    return document


def decode_document(
    payload: object,
    *,
    expected_object_kind: object | None = None,
    expected_schema_version: object | None = None,
    allowed_record_fields: tuple[str, ...] | None = None,
) -> DecodedConstructionDocument:
    """Decode an exact construction frame and reject every schema ambiguity."""

    if type(payload) is not bytes:
        raise _decoding_error(
            "construction.canonical_payload_type_invalid",
            "canonical document must be exact immutable bytes",
        )
    if len(payload) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise _decoding_error(
            "construction.canonical_document_too_large",
            "construction document exceeds the v1 byte bound",
        )
    if not payload.startswith(CONSTRUCTION_DOCUMENT_HEADER):
        raise _decoding_error(
            "construction.canonical_header_invalid",
            "construction document has the wrong domain-separation header",
        )
    try:
        value = decode_value(payload[len(CONSTRUCTION_DOCUMENT_HEADER) :])
    except AuthoringError as exc:
        raise _decoding_error(
            "construction.canonical_decoding_failed",
            "construction payload is malformed, noncanonical, or has trailing bytes",
        ) from exc
    if type(value) is not CanonicalRecord:
        raise _decoding_error(
            "construction.canonical_record_invalid",
            "construction document must contain one exact canonical record",
        )
    fields = value.field_map()
    kind_value = fields.get("object_kind")
    schema_value = fields.get("schema_version")
    profile_value = fields.get("canonicalization_profile")
    if (
        type(kind_value) is not CanonicalText
        or kind_value.value not in CONSTRUCTION_OBJECT_KINDS
        or value.record_type != kind_value.value
    ):
        raise _decoding_error(
            "construction.canonical_record_kind_mismatch",
            "record object kind is missing, unknown, or inconsistent",
        )
    if (
        type(schema_value) is not CanonicalText
        or schema_value.value != CONSTRUCTION_SCHEMA_VERSION
    ):
        raise _decoding_error(
            "construction.canonical_schema_version_mismatch",
            "record schema version is missing or unsupported",
        )
    if (
        type(profile_value) is not CanonicalText
        or profile_value.value != CONSTRUCTION_CANONICALIZATION_PROFILE
    ):
        raise _decoding_error(
            "construction.canonicalization_profile_invalid",
            "record canonicalization profile is missing or unsupported",
        )
    if expected_object_kind is not None and (
        type(expected_object_kind) is not str
        or kind_value.value != expected_object_kind
    ):
        raise _decoding_error(
            "construction.expected_object_kind_mismatch",
            "construction document has a different object kind than expected",
        )
    if expected_schema_version is not None and (
        type(expected_schema_version) is not str
        or schema_value.value != expected_schema_version
    ):
        raise _decoding_error(
            "construction.expected_schema_version_mismatch",
            "construction document has a different schema version than expected",
        )
    if allowed_record_fields is not None:
        if type(allowed_record_fields) is not tuple or any(
            type(name) is not str for name in allowed_record_fields
        ):
            raise TypeError("allowed_record_fields must be an exact tuple of strings")
        if set(fields) != set(allowed_record_fields):
            raise _decoding_error(
                "construction.canonical_record_fields_invalid",
                "construction record has missing, unknown, or extra fields",
            )
    return DecodedConstructionDocument(
        kind_value.value,
        schema_value.value,
        value,
    )


class _Schema(NamedTuple):
    record_type: str
    fields: tuple[tuple[str, object], ...]
    union_tag: str | None = None


_TEXT = "TEXT"
_BOOL = "BOOL"
_INT64 = "INT64"
_UINT64 = "UINT64"
_FLOAT64 = "FLOAT64"
_TOP_REF = "TOP_REF"
_CONSTRUCTION_REF = "CONSTRUCTION_REF"
_CHALLENGE_KEY = "CHALLENGE_KEY"
_SURFACE_SCALAR = "SURFACE_SCALAR"


def _enum(enum_type: type) -> tuple[str, type]:
    return ("ENUM", enum_type)


def _model(model_type: type) -> tuple[str, type]:
    return ("MODEL", model_type)


def _union(*model_types: type) -> tuple[str, tuple[type, ...]]:
    return ("UNION", model_types)


def _tuple_of(
    descriptor: object, *, set_like: bool = False
) -> tuple[str, object, bool]:
    return ("TUPLE", descriptor, set_like)


def _owner(kind: str) -> tuple[str, str]:
    return ("OWNER", kind)


def _schema(
    record_type: str,
    *fields: tuple[str, object],
    tag: str | None = None,
) -> _Schema:
    return _Schema(record_type, fields, tag)


_SCHEMAS = MappingProxyType(
    {
        m.CompilerIdentity: _schema(
            "compiler_identity",
            ("compiler_id", _TEXT),
            ("compiler_version", _TEXT),
            ("implementation_digest", _TEXT),
            ("construction_schema_version", _TEXT),
            ("canonicalization_profile", _TEXT),
        ),
        m.ImplementationPin: _schema(
            "implementation_pin",
            ("implementation_id", _TEXT),
            ("implementation_version", _TEXT),
            ("content_digest", _TEXT),
        ),
        m.EnvironmentPin: _schema(
            "environment_pin",
            ("environment_id", _TEXT),
            ("environment_version", _TEXT),
            ("content_digest", _TEXT),
        ),
        m.DependencyPin: _schema(
            "dependency_pin",
            ("dependency_id", _TEXT),
            ("dependency_version", _TEXT),
            ("content_digest", _TEXT),
        ),
        m.InterfacePin: _schema(
            "interface_pin",
            ("interface_id", _TEXT),
            ("interface_version", _TEXT),
            ("content_digest", _TEXT),
            ("direction", _enum(m.InterfaceDirection)),
        ),
        m.ConsumerTarget: _schema(
            "consumer_target",
            ("consumer_id", _TEXT),
            ("field_id", _TEXT),
        ),
        m.SurfaceValue: _schema(
            "surface_value",
            ("value_type", _enum(m.SurfaceValueType)),
            ("value", _SURFACE_SCALAR),
        ),
        m.UnitNotApplicable: _schema(
            "unit_binding_not_applicable",
            ("reason_ref", _owner("applicability_reason")),
            tag="NOT_APPLICABLE",
        ),
        m.BoundUnit: _schema(
            "unit_binding_bound",
            ("unit_ref", _owner("unit")),
            tag="BOUND",
        ),
        m.BooleanDomain: _schema(
            "surface_domain_boolean",
            ("allowed_values", _tuple_of(_BOOL, set_like=True)),
            tag="BOOLEAN",
        ),
        m.Int64RangeDomain: _schema(
            "surface_domain_int64_range",
            ("minimum", _INT64),
            ("maximum", _INT64),
            tag="INT64_RANGE",
        ),
        m.UInt64RangeDomain: _schema(
            "surface_domain_uint64_range",
            ("minimum", _UINT64),
            ("maximum", _UINT64),
            tag="UINT64_RANGE",
        ),
        m.Float64RangeDomain: _schema(
            "surface_domain_float64_range",
            ("minimum", _FLOAT64),
            ("maximum", _FLOAT64),
            ("lower_inclusive", _BOOL),
            ("upper_inclusive", _BOOL),
            tag="FLOAT64_RANGE",
        ),
        m.ChoiceDomain: _schema(
            "surface_domain_choice",
            ("allowed_ids", _tuple_of(_TEXT, set_like=True)),
            tag="CHOICE",
        ),
        m.RequiredSurface: _schema(
            "surface_requirement_required",
            tag="REQUIRED",
        ),
        m.ExplicitDefaultSurface: _schema(
            "surface_requirement_explicit_default",
            ("default_value", _model(m.SurfaceValue)),
            tag="EXPLICIT_DEFAULT",
        ),
        m.AssemblySemanticOwner: _schema(
            "semantic_owner_assembly",
            ("local_target_id", _TEXT),
            ("authority_ref", _owner("scientific_authority")),
            tag="ASSEMBLY",
        ),
        m.TrainingSupportSemanticOwner: _schema(
            "semantic_owner_training_support",
            ("semantic_clause_ref", _owner("semantic_clause")),
            ("authority_ref", _owner("policy_authority")),
            tag="TRAINING_SUPPORT",
        ),
        m.ActiveLifecycle: _schema(
            "catalog_entry_lifecycle_active",
            tag="ACTIVE",
        ),
        m.RetiredLifecycle: _schema(
            "catalog_entry_lifecycle_retired",
            ("reason_ref", _owner("applicability_reason")),
            ("supersession_ref", _owner("semantic_equivalence")),
            tag="RETIRED_FOR_NEW_COMPILATION",
        ),
        m.AlwaysApplicable: _schema(
            "applicability_always",
            ("applicability_ref", _owner("applicability")),
            tag="ALWAYS",
        ),
        m.WhenSurfaceIn: _schema(
            "applicability_when_surface_in",
            ("applicability_ref", _owner("applicability")),
            ("selector_surface_id", _TEXT),
            (
                "allowed_values",
                _tuple_of(_model(m.SurfaceValue), set_like=True),
            ),
            (
                "not_applicable_reason_ref",
                _owner("applicability_reason"),
            ),
            tag="WHEN_SURFACE_IN",
        ),
        m.ValueCompatibilityCell: _schema(
            "compatibility_cell_value",
            ("value", _model(m.SurfaceValue)),
            tag="VALUE",
        ),
        m.NotApplicableCompatibilityCell: _schema(
            "compatibility_cell_not_applicable",
            tag="NOT_APPLICABLE",
        ),
        m.CompatibilityRule: _schema(
            "compatibility_rule",
            ("rule_id", _TEXT),
            ("surface_ids", _tuple_of(_TEXT)),
            (
                "allowed_rows",
                _tuple_of(
                    _tuple_of(
                        _union(
                            m.ValueCompatibilityCell,
                            m.NotApplicableCompatibilityCell,
                        )
                    ),
                    set_like=True,
                ),
            ),
            ("semantic_clause_ref", _owner("semantic_clause")),
        ),
        m.TrainingRandomnessPurpose: _schema(
            "training_randomness_purpose",
            ("purpose_id", _TEXT),
            ("role_key_label", _TEXT),
        ),
        m.TrainingLeverNotApplicable: _schema(
            "training_lever_not_applicable",
            ("reason_ref", _owner("applicability_reason")),
            tag="NOT_APPLICABLE",
        ),
        m.BoundTrainingLever: _schema(
            "training_lever_bound",
            ("kind", _enum(m.TrainingLeverKind)),
            ("executable_semantics_ref", _owner("semantic_clause")),
            (
                "randomness_purposes",
                _tuple_of(_model(m.TrainingRandomnessPurpose), set_like=True),
            ),
            tag="BOUND",
        ),
        m.ComponentSelectionNotApplicable: _schema(
            "component_selection_not_applicable",
            ("reason_ref", _owner("applicability_reason")),
            tag="NOT_APPLICABLE",
        ),
        m.BoundComponentSelection: _schema(
            "component_selection_bound",
            ("slot_id", _TEXT),
            ("role", _enum(m.ComponentRole)),
            tag="BOUND",
        ),
        m.StaticResourceDimension: _schema(
            "static_resource_dimension",
            ("dimension_id", _TEXT),
            ("unit_ref", _owner("unit")),
        ),
        m.ResourceLookupCase: _schema(
            "resource_lookup_case",
            ("selector_value", _model(m.SurfaceValue)),
            ("quantity", _UINT64),
        ),
        m.FixedResourceContribution: _schema(
            "static_resource_contribution_fixed",
            ("dimension_id", _TEXT),
            ("unit_ref", _owner("unit")),
            ("quantity", _UINT64),
            ("impact_tags", _tuple_of(_TEXT, set_like=True)),
            tag="FIXED",
        ),
        m.DiscreteLookupResourceContribution: _schema(
            "static_resource_contribution_discrete_lookup",
            ("dimension_id", _TEXT),
            ("unit_ref", _owner("unit")),
            ("selector_surface_id", _TEXT),
            (
                "cases",
                _tuple_of(_model(m.ResourceLookupCase), set_like=True),
            ),
            ("impact_tags", _tuple_of(_TEXT, set_like=True)),
            tag="DISCRETE_LOOKUP",
        ),
        m.StaticResourceRequirement: _schema(
            "static_resource_requirement",
            ("dimension_id", _TEXT),
            ("unit_ref", _owner("unit")),
            ("quantity", _UINT64),
            ("contributing_source_ids", _tuple_of(_TEXT, set_like=True)),
            ("impact_tags", _tuple_of(_TEXT, set_like=True)),
        ),
        m.FixtureProvenance: _schema(
            "construction_provenance_fixture",
            ("fixture_registration_ref", _owner("fixture_registration")),
            (
                "source_provenance_refs",
                _tuple_of(_owner("provenance"), set_like=True),
            ),
            (
                "origin_evidence_refs",
                _tuple_of(_owner("authoring_origin_evidence"), set_like=True),
            ),
            tag="FIXTURE",
        ),
        m.RegisteredProvenance: _schema(
            "construction_provenance_registered",
            ("authoring_registration_ref", _owner("authoring_registration")),
            (
                "source_provenance_refs",
                _tuple_of(_owner("provenance"), set_like=True),
            ),
            (
                "origin_evidence_refs",
                _tuple_of(_owner("authoring_origin_evidence"), set_like=True),
            ),
            tag="REGISTERED",
        ),
        m.AuthoringOriginBinding: _schema(
            "authoring_origin_binding",
            ("graph_origin", _enum(m.GraphOrigin)),
            ("graph_fingerprint", _TEXT),
            ("root_ref", _TOP_REF),
            ("dependency_refs", _tuple_of(_TOP_REF, set_like=True)),
            (
                "origin_evidence_refs",
                _tuple_of(_owner("authoring_origin_evidence"), set_like=True),
            ),
            ("composition_audit_ref", _owner("origin_composition_audit")),
        ),
    }
)

_SCHEMAS = MappingProxyType(
    {
        **dict(_SCHEMAS),
        m.BackboneOption: _schema(
            "backbone_option",
            ("selector_token", _TEXT),
            ("backbone_id", _TEXT),
            ("backbone_version", _TEXT),
            ("content_digest", _TEXT),
            ("implementation_pin", _model(m.ImplementationPin)),
            ("environment_pin", _model(m.EnvironmentPin)),
            (
                "dependency_pins",
                _tuple_of(_model(m.DependencyPin), set_like=True),
            ),
            ("input_interface_pin", _model(m.InterfacePin)),
            ("output_interface_pin", _model(m.InterfacePin)),
            ("applicability_ref", _owner("applicability")),
            (
                "assumption_refs",
                _tuple_of(_owner("semantic_clause"), set_like=True),
            ),
            (
                "limitation_refs",
                _tuple_of(_owner("restriction"), set_like=True),
            ),
            (
                "static_resource_contributions",
                _tuple_of(
                    _union(
                        m.FixedResourceContribution,
                        m.DiscreteLookupResourceContribution,
                    ),
                    set_like=True,
                ),
            ),
            ("resource_impact_tags", _tuple_of(_TEXT, set_like=True)),
        ),
        m.BackboneSurfaceContract: _schema(
            "backbone_surface_contract",
            ("surface_id", _TEXT),
            ("consumer_target", _model(m.ConsumerTarget)),
            ("options", _tuple_of(_model(m.BackboneOption), set_like=True)),
        ),
        m.RegisteredComponentOption: _schema(
            "registered_component_option",
            ("selector_token", _TEXT),
            ("component_id", _TEXT),
            ("component_version", _TEXT),
            ("content_digest", _TEXT),
            ("role", _enum(m.ComponentRole)),
            ("consumer_target", _model(m.ConsumerTarget)),
            ("input_interface_pin", _model(m.InterfacePin)),
            ("output_interface_pin", _model(m.InterfacePin)),
            ("state_policy", _enum(m.ComponentStatePolicy)),
            ("side_effect_policy", _enum(m.SideEffectPolicy)),
            ("trainability_boundary", _enum(m.TrainabilityBoundary)),
            ("implementation_pin", _model(m.ImplementationPin)),
            ("environment_pin", _model(m.EnvironmentPin)),
            (
                "dependency_pins",
                _tuple_of(_model(m.DependencyPin), set_like=True),
            ),
            ("applicability_ref", _owner("applicability")),
            (
                "assumption_refs",
                _tuple_of(_owner("semantic_clause"), set_like=True),
            ),
            (
                "limitation_refs",
                _tuple_of(_owner("restriction"), set_like=True),
            ),
            (
                "static_resource_contributions",
                _tuple_of(
                    _union(
                        m.FixedResourceContribution,
                        m.DiscreteLookupResourceContribution,
                    ),
                    set_like=True,
                ),
            ),
            ("resource_impact_tags", _tuple_of(_TEXT, set_like=True)),
            (
                "public_falsification_refs",
                _tuple_of(_owner("audit_evidence"), set_like=True),
            ),
        ),
        m.ComponentSlotContract: _schema(
            "component_slot_contract",
            ("slot_id", _TEXT),
            ("selector_surface_id", _TEXT),
            ("role", _enum(m.ComponentRole)),
            ("consumer_target", _model(m.ConsumerTarget)),
            ("input_interface_pin", _model(m.InterfacePin)),
            ("output_interface_pin", _model(m.InterfacePin)),
            ("state_policy", _enum(m.ComponentStatePolicy)),
            ("side_effect_policy", _enum(m.SideEffectPolicy)),
            ("trainability_boundary", _enum(m.TrainabilityBoundary)),
            ("applicability_ref", _owner("applicability")),
            (
                "options",
                _tuple_of(_model(m.RegisteredComponentOption), set_like=True),
            ),
            ("fallback_policy", _enum(m.FallbackPolicy)),
        ),
        m.ParameterCatalogEntry: _schema(
            "parameter_catalog_entry",
            ("surface_id", _TEXT),
            ("input_source", _enum(m.InputSource)),
            ("consumer_target", _model(m.ConsumerTarget)),
            ("value_type", _enum(m.SurfaceValueType)),
            ("unit_binding", _union(m.UnitNotApplicable, m.BoundUnit)),
            (
                "domain",
                _union(
                    m.BooleanDomain,
                    m.Int64RangeDomain,
                    m.UInt64RangeDomain,
                    m.Float64RangeDomain,
                    m.ChoiceDomain,
                ),
            ),
            ("dependency_surface_ids", _tuple_of(_TEXT, set_like=True)),
            (
                "applicability",
                _union(m.AlwaysApplicable, m.WhenSurfaceIn),
            ),
            (
                "requirement",
                _union(m.RequiredSurface, m.ExplicitDefaultSurface),
            ),
            ("compatibility_rule_ids", _tuple_of(_TEXT, set_like=True)),
            (
                "static_resource_contributions",
                _tuple_of(
                    _union(
                        m.FixedResourceContribution,
                        m.DiscreteLookupResourceContribution,
                    ),
                    set_like=True,
                ),
            ),
            ("resource_impact_tags", _tuple_of(_TEXT, set_like=True)),
            ("public_outcome_family_tags", _tuple_of(_TEXT, set_like=True)),
            (
                "semantic_owner_binding",
                _union(
                    m.AssemblySemanticOwner,
                    m.TrainingSupportSemanticOwner,
                ),
            ),
            ("lifecycle", _union(m.ActiveLifecycle, m.RetiredLifecycle)),
            (
                "training_lever_binding",
                _union(m.TrainingLeverNotApplicable, m.BoundTrainingLever),
            ),
            (
                "component_slot_binding",
                _union(
                    m.ComponentSelectionNotApplicable,
                    m.BoundComponentSelection,
                ),
            ),
        ),
        m.SelectedSurface: _schema(
            "resolved_surface_selected",
            ("surface_id", _TEXT),
            ("consumer_target", _model(m.ConsumerTarget)),
            ("value", _model(m.SurfaceValue)),
            tag="SELECTED",
        ),
        m.DefaultedSurface: _schema(
            "resolved_surface_defaulted",
            ("surface_id", _TEXT),
            ("consumer_target", _model(m.ConsumerTarget)),
            ("value", _model(m.SurfaceValue)),
            tag="DEFAULTED",
        ),
        m.NotApplicableSurface: _schema(
            "resolved_surface_not_applicable",
            ("surface_id", _TEXT),
            ("consumer_target", _model(m.ConsumerTarget)),
            ("reason_ref", _owner("applicability_reason")),
            tag="NOT_APPLICABLE",
        ),
        m.ResolvedBackboneBinding: _schema(
            "resolved_backbone_binding",
            ("surface_id", _TEXT),
            ("selector_token", _TEXT),
            ("backbone_id", _TEXT),
            ("backbone_version", _TEXT),
            ("content_digest", _TEXT),
            ("implementation_pin", _model(m.ImplementationPin)),
            ("environment_pin", _model(m.EnvironmentPin)),
            (
                "dependency_pins",
                _tuple_of(_model(m.DependencyPin), set_like=True),
            ),
            ("input_interface_pin", _model(m.InterfacePin)),
            ("output_interface_pin", _model(m.InterfacePin)),
            ("applicability_ref", _owner("applicability")),
            (
                "assumption_refs",
                _tuple_of(_owner("semantic_clause"), set_like=True),
            ),
            (
                "limitation_refs",
                _tuple_of(_owner("restriction"), set_like=True),
            ),
        ),
        m.ResolvedComponentBinding: _schema(
            "resolved_component_binding",
            ("slot_id", _TEXT),
            ("selector_surface_id", _TEXT),
            ("selector_token", _TEXT),
            ("component_id", _TEXT),
            ("component_version", _TEXT),
            ("content_digest", _TEXT),
            ("role", _enum(m.ComponentRole)),
            ("consumer_target", _model(m.ConsumerTarget)),
            ("input_interface_pin", _model(m.InterfacePin)),
            ("output_interface_pin", _model(m.InterfacePin)),
            ("state_policy", _enum(m.ComponentStatePolicy)),
            ("side_effect_policy", _enum(m.SideEffectPolicy)),
            ("trainability_boundary", _enum(m.TrainabilityBoundary)),
            ("implementation_pin", _model(m.ImplementationPin)),
            ("environment_pin", _model(m.EnvironmentPin)),
            (
                "dependency_pins",
                _tuple_of(_model(m.DependencyPin), set_like=True),
            ),
            ("applicability_ref", _owner("applicability")),
            (
                "assumption_refs",
                _tuple_of(_owner("semantic_clause"), set_like=True),
            ),
            (
                "limitation_refs",
                _tuple_of(_owner("restriction"), set_like=True),
            ),
            (
                "public_falsification_refs",
                _tuple_of(_owner("audit_evidence"), set_like=True),
            ),
        ),
        m.ResolvedTrainingBinding: _schema(
            "resolved_training_binding",
            ("surface_id", _TEXT),
            ("kind", _enum(m.TrainingLeverKind)),
            ("resolved_value", _model(m.SurfaceValue)),
            ("executable_semantics_ref", _owner("semantic_clause")),
        ),
    }
)

MODEL_CANONICAL_FIELD_REGISTRY_V1 = MappingProxyType(
    {
        schema.record_type: tuple(name for name, _ in schema.fields)
        for schema in _SCHEMAS.values()
    }
)

_ENUM_TYPES = (
    m.SurfaceValueType,
    m.InterfaceDirection,
    m.InputSource,
    m.ComponentRole,
    m.ComponentStatePolicy,
    m.SideEffectPolicy,
    m.TrainabilityBoundary,
    m.FallbackPolicy,
    m.TrainingLeverKind,
    m.PolicyState,
    m.GraphOrigin,
    m.UnknownOrInvalidPolicy,
    m.AuthorityMarker,
)

_CANONICAL_VALUE_TYPES = (
    bool,
    CanonicalInt64,
    CanonicalUInt64,
    CanonicalFloat64,
    CanonicalText,
    CanonicalTuple,
    CanonicalRecord,
    CanonicalUnion,
    CanonicalNominalRef,
)


def _canonical_text(value: object) -> CanonicalText:
    if type(value) is not str:
        raise _encoding_error(
            "construction.canonical_text_invalid",
            "canonical TEXT source must be an exact built-in string",
        )
    try:
        return CanonicalText(value)
    except AuthoringError as exc:
        raise _encoding_error(
            "construction.canonical_text_invalid",
            "canonical TEXT source is invalid",
        ) from exc


def _encode_surface_scalar(owner: object, value: object) -> CanonicalValue:
    if type(owner) is not m.SurfaceValue:
        raise _encoding_error(
            "construction.surface_value_context_invalid",
            "surface scalar requires its exact SurfaceValue context",
        )
    value_type = object.__getattribute__(owner, "value_type")
    if value_type is m.SurfaceValueType.BOOL and type(value) is bool:
        return value
    if value_type is m.SurfaceValueType.INT64 and type(value) is int:
        return CanonicalInt64(value)
    if value_type is m.SurfaceValueType.UINT64 and type(value) is int:
        return CanonicalUInt64(value)
    if value_type is m.SurfaceValueType.FLOAT64 and type(value) is float:
        return CanonicalFloat64(value)
    if (
        value_type
        in {
            m.SurfaceValueType.CANONICAL_CHOICE,
            m.SurfaceValueType.BACKBONE_SELECTOR,
            m.SurfaceValueType.COMPONENT_SELECTOR,
        }
        and type(value) is str
    ):
        return CanonicalText(value)
    raise _encoding_error(
        "construction.surface_value_type_mismatch",
        "surface scalar does not match its exact type tag",
    )


def _encode_field(descriptor: object, value: object, owner: object) -> CanonicalValue:
    if descriptor == _TEXT:
        return _canonical_text(value)
    if descriptor == _BOOL:
        if type(value) is not bool:
            raise _encoding_error(
                "construction.canonical_bool_invalid",
                "canonical Boolean source must be exact bool",
            )
        return value
    if descriptor == _INT64:
        if type(value) is not int:
            raise _encoding_error(
                "construction.canonical_int64_invalid",
                "canonical Int64 source must be exact int",
            )
        return CanonicalInt64(value)
    if descriptor == _UINT64:
        if type(value) is not int:
            raise _encoding_error(
                "construction.canonical_uint64_invalid",
                "canonical UInt64 source must be exact int",
            )
        return CanonicalUInt64(value)
    if descriptor == _FLOAT64:
        if type(value) is not float:
            raise _encoding_error(
                "construction.canonical_float64_invalid",
                "canonical Float64 source must be exact float",
            )
        return CanonicalFloat64(value)
    if descriptor == _TOP_REF:
        try:
            return top_level_ref_to_canonical(value)
        except AuthoringError as exc:
            raise _encoding_error(
                "construction.canonical_authoring_ref_invalid",
                "top-level authoring ref cannot be canonicalized",
            ) from exc
    if descriptor == _CONSTRUCTION_REF:
        return construction_ref_to_canonical(value)
    if descriptor == _CHALLENGE_KEY:
        try:
            return challenge_key_to_canonical(value)
        except AuthoringError as exc:
            raise _encoding_error(
                "construction.canonical_challenge_key_invalid",
                "ChallengeKey cannot be canonicalized",
            ) from exc
    if descriptor == _SURFACE_SCALAR:
        return _encode_surface_scalar(owner, value)
    if type(descriptor) is not tuple or not descriptor:
        raise _encoding_error(
            "construction.canonical_descriptor_unknown",
            "field uses an unknown closed canonical descriptor",
        )
    kind = descriptor[0]
    if kind == "ENUM":
        enum_type = descriptor[1]
        if type(value) is not enum_type:
            raise _encoding_error(
                "construction.canonical_enum_invalid",
                "enum field has a wrong exact nominal type",
            )
        return CanonicalText(value.value)
    if kind in {"MODEL", "UNION"}:
        if kind == "MODEL" and type(value) is not descriptor[1]:
            raise _encoding_error(
                "construction.canonical_model_type_invalid",
                "model field has a wrong exact nominal type",
            )
        if kind == "UNION" and type(value) not in descriptor[1]:
            raise _encoding_error(
                "construction.canonical_union_type_invalid",
                "union field has a wrong exact variant type",
            )
        return to_canonical_value(value)
    if kind == "OWNER":
        try:
            canonical = owner_ref_to_canonical(value)
        except AuthoringError as exc:
            raise _encoding_error(
                "construction.canonical_owner_ref_invalid",
                "owner ref cannot be canonicalized",
            ) from exc
        if canonical.ref_type != descriptor[1]:
            raise _encoding_error(
                "construction.canonical_owner_ref_kind_mismatch",
                "owner ref has the wrong exact nominal kind",
            )
        return canonical
    if kind == "TUPLE":
        if type(value) is not tuple:
            raise _encoding_error(
                "construction.canonical_tuple_invalid",
                "canonical tuple source must be exact tuple",
            )
        item_descriptor, set_like = descriptor[1], descriptor[2]
        return CanonicalTuple(
            tuple(_encode_field(item_descriptor, item, owner) for item in value),
            set_like=set_like,
        )
    raise _encoding_error(
        "construction.canonical_descriptor_unknown",
        "field uses an unknown closed canonical descriptor",
    )


def _model_to_canonical(value: object) -> CanonicalRecord | CanonicalUnion:
    schema = _SCHEMAS.get(type(value))
    if schema is None:
        raise _encoding_error(
            "construction.canonical_model_unknown",
            "value is not in the closed construction model registry",
        )
    fields = tuple(
        (
            name,
            _encode_field(descriptor, object.__getattribute__(value, name), value),
        )
        for name, descriptor in schema.fields
    )
    record = CanonicalRecord(schema.record_type, fields)
    if schema.union_tag is not None:
        return CanonicalUnion(schema.union_tag, record)
    return record


def to_canonical_value(value: object) -> CanonicalValue:
    """Adapt one exact closed construction value for composable B-02A encoding."""

    if type(value) in _CANONICAL_VALUE_TYPES:
        return value
    if type(value) is str:
        return _canonical_text(value)
    if type(value) is tuple:
        return CanonicalTuple(
            tuple(to_canonical_value(item) for item in value),
            set_like=False,
        )
    if type(value) in _ENUM_TYPES:
        return CanonicalText(value.value)
    if type(value) is ChallengeKey:
        return challenge_key_to_canonical(value)
    if is_owner_ref(value):
        return owner_ref_to_canonical(value)
    if is_top_level_ref(value):
        return top_level_ref_to_canonical(value)
    if is_construction_ref(value):
        return construction_ref_to_canonical(value)
    if type(value) in _SCHEMAS:
        try:
            return _model_to_canonical(value)
        except (AuthoringError, ConstructionValidationError) as exc:
            raise _encoding_error(
                "construction.canonical_model_invalid",
                "construction model cannot be canonicalized",
            ) from exc
    raise _encoding_error(
        "construction.canonical_value_unknown",
        "value is outside the closed construction canonical vocabulary",
    )


def _require_text(value: object) -> str:
    if type(value) is not CanonicalText:
        raise _decoding_error(
            "construction.canonical_text_invalid",
            "field must be exact canonical TEXT",
        )
    return value.value


def _decode_surface_scalar(value: object, value_type: m.SurfaceValueType) -> object:
    if value_type is m.SurfaceValueType.BOOL and type(value) is bool:
        return value
    if value_type is m.SurfaceValueType.INT64 and type(value) is CanonicalInt64:
        return value.value
    if value_type is m.SurfaceValueType.UINT64 and type(value) is CanonicalUInt64:
        return value.value
    if value_type is m.SurfaceValueType.FLOAT64 and type(value) is CanonicalFloat64:
        return value.value
    if (
        value_type
        in {
            m.SurfaceValueType.CANONICAL_CHOICE,
            m.SurfaceValueType.BACKBONE_SELECTOR,
            m.SurfaceValueType.COMPONENT_SELECTOR,
        }
        and type(value) is CanonicalText
    ):
        return value.value
    raise _decoding_error(
        "construction.surface_value_type_mismatch",
        "surface scalar does not match its exact type tag",
    )


def _decode_field(descriptor: object, value: object) -> object:
    if descriptor == _TEXT:
        return _require_text(value)
    if descriptor == _BOOL:
        if type(value) is not bool:
            raise _decoding_error(
                "construction.canonical_bool_invalid", "field must be exact Boolean"
            )
        return value
    if descriptor == _INT64:
        if type(value) is not CanonicalInt64:
            raise _decoding_error(
                "construction.canonical_int64_invalid", "field must be exact Int64"
            )
        return value.value
    if descriptor == _UINT64:
        if type(value) is not CanonicalUInt64:
            raise _decoding_error(
                "construction.canonical_uint64_invalid", "field must be exact UInt64"
            )
        return value.value
    if descriptor == _FLOAT64:
        if type(value) is not CanonicalFloat64:
            raise _decoding_error(
                "construction.canonical_float64_invalid", "field must be exact Float64"
            )
        return value.value
    if descriptor == _TOP_REF:
        try:
            return top_level_ref_from_canonical(value)
        except AuthoringError as exc:
            raise _decoding_error(
                "construction.canonical_authoring_ref_invalid",
                "top-level authoring ref is malformed",
            ) from exc
    if descriptor == _CONSTRUCTION_REF:
        return construction_ref_from_canonical(value)
    if descriptor == _CHALLENGE_KEY:
        try:
            return challenge_key_from_canonical(value)
        except AuthoringError as exc:
            raise _decoding_error(
                "construction.canonical_challenge_key_invalid",
                "ChallengeKey is malformed",
            ) from exc
    if type(descriptor) is not tuple or not descriptor:
        raise _decoding_error(
            "construction.canonical_descriptor_unknown",
            "field uses an unknown closed canonical descriptor",
        )
    kind = descriptor[0]
    if kind == "ENUM":
        text = _require_text(value)
        enum_type = descriptor[1]
        try:
            return enum_type(text)
        except ValueError as exc:
            raise _decoding_error(
                "construction.canonical_enum_invalid",
                "enum field contains an unknown closed literal",
            ) from exc
    if kind == "MODEL":
        return _from_canonical_model(value, descriptor[1])
    if kind == "UNION":
        return _from_canonical_union(value, descriptor[1])
    if kind == "OWNER":
        try:
            return owner_ref_from_canonical(value, expected_kind=descriptor[1])
        except AuthoringError as exc:
            raise _decoding_error(
                "construction.canonical_owner_ref_invalid",
                "owner ref is malformed or has a wrong nominal kind",
            ) from exc
    if kind == "TUPLE":
        if type(value) is not CanonicalTuple:
            raise _decoding_error(
                "construction.canonical_tuple_invalid", "field must be exact tuple"
            )
        return tuple(_decode_field(descriptor[1], item) for item in value.items)
    raise _decoding_error(
        "construction.canonical_descriptor_unknown",
        "field uses an unknown closed canonical descriptor",
    )


def _record_for_schema(value: object, schema: _Schema) -> CanonicalRecord:
    if schema.union_tag is None:
        if type(value) is not CanonicalRecord:
            raise _decoding_error(
                "construction.canonical_record_invalid",
                "model requires its exact canonical record",
            )
        record = value
    else:
        if type(value) is not CanonicalUnion or value.tag != schema.union_tag:
            raise _decoding_error(
                "construction.canonical_union_tag_invalid",
                "model requires its exact closed union tag",
            )
        if type(value.payload) is not CanonicalRecord:
            raise _decoding_error(
                "construction.canonical_union_payload_invalid",
                "union payload must be its exact canonical record",
            )
        record = value.payload
    if record.record_type != schema.record_type:
        raise _decoding_error(
            "construction.canonical_record_type_invalid",
            "canonical record has a wrong exact schema type",
        )
    expected_fields = {name for name, _ in schema.fields}
    if set(record.field_map()) != expected_fields:
        raise _decoding_error(
            "construction.canonical_record_fields_invalid",
            "canonical record has missing, unknown, or extra fields",
        )
    return record


def _from_canonical_model(value: object, expected_type: type) -> object:
    schema = _SCHEMAS.get(expected_type)
    if schema is None:
        raise _decoding_error(
            "construction.canonical_model_unknown",
            "expected type is outside the closed model registry",
        )
    record = _record_for_schema(value, schema)
    fields = record.field_map()
    if expected_type is m.SurfaceValue:
        value_type = _decode_field(_enum(m.SurfaceValueType), fields["value_type"])
        kwargs = {
            "value_type": value_type,
            "value": _decode_surface_scalar(fields["value"], value_type),
        }
    else:
        kwargs = {
            name: _decode_field(descriptor, fields[name])
            for name, descriptor in schema.fields
        }
    try:
        if expected_type is m.AuthoringOriginBinding:
            return m.AuthoringOriginBinding._from_canonical(**kwargs)
        return expected_type(**kwargs)
    except (TypeError, ValueError) as exc:
        raise _decoding_error(
            "construction.canonical_model_value_invalid",
            "canonical record contains an invalid construction value",
        ) from exc


def _from_canonical_union(value: object, allowed_types: tuple[type, ...]) -> object:
    if type(value) is not CanonicalUnion:
        raise _decoding_error(
            "construction.canonical_union_invalid",
            "closed union field must be an exact canonical union",
        )
    matches = tuple(
        model_type
        for model_type in allowed_types
        if _SCHEMAS[model_type].union_tag == value.tag
    )
    if len(matches) != 1:
        raise _decoding_error(
            "construction.canonical_union_tag_invalid",
            "union tag is unknown or ambiguous for the expected field",
        )
    return _from_canonical_model(value, matches[0])


def from_canonical_value(value: object, expected_type: type) -> object:
    """Reconstruct one exact registered type and reject noncanonical variants."""

    if type(expected_type) is not type:
        raise TypeError("expected_type must be an exact class")
    if expected_type in CONSTRUCTION_REF_TYPES:
        result = construction_ref_from_canonical(value, expected_type=expected_type)
    elif expected_type is ChallengeKey:
        try:
            result = challenge_key_from_canonical(value)
        except AuthoringError as exc:
            raise _decoding_error(
                "construction.canonical_challenge_key_invalid",
                "ChallengeKey is malformed",
            ) from exc
    elif expected_type in _ENUM_TYPES:
        text = _require_text(value)
        try:
            result = expected_type(text)
        except ValueError as exc:
            raise _decoding_error(
                "construction.canonical_enum_invalid",
                "enum contains an unknown closed literal",
            ) from exc
    else:
        result = _from_canonical_model(value, expected_type)
    try:
        if not hmac.compare_digest(
            encode_value(to_canonical_value(result)), encode_value(value)
        ):
            raise _decoding_error(
                "construction.canonical_noncanonical_value",
                "decoded value was not in its unique canonical form",
            )
    except AuthoringError as exc:
        raise _decoding_error(
            "construction.canonical_noncanonical_value",
            "decoded value cannot be re-encoded canonically",
        ) from exc
    return result


def encode_model(value: object) -> bytes:
    """Encode one nested construction model or reference as a standalone value."""

    try:
        return encode_value(to_canonical_value(value))
    except AuthoringError as exc:
        raise _encoding_error(
            "construction.canonical_encoding_failed",
            "construction value cannot be encoded",
        ) from exc


def decode_model(payload: object, expected_type: type) -> object:
    """Decode one nested model with exact-type and trailing-byte rejection."""

    if type(payload) is not bytes:
        raise _decoding_error(
            "construction.canonical_payload_type_invalid",
            "canonical payload must be exact immutable bytes",
        )
    try:
        canonical = decode_value(payload)
    except AuthoringError as exc:
        raise _decoding_error(
            "construction.canonical_decoding_failed",
            "canonical payload is malformed, noncanonical, or has trailing bytes",
        ) from exc
    return from_canonical_value(canonical, expected_type)


__all__ = [
    "CONSTRUCTION_DOCUMENT_HEADER",
    "CONSTRUCTION_OBJECT_KINDS",
    "DecodedConstructionDocument",
    "construction_document",
    "decode_document",
    "decode_model",
    "encode_construction_ref",
    "encode_model",
    "from_canonical_value",
    "to_canonical_value",
]


def construction_ref_to_canonical(value: object) -> CanonicalNominalRef:
    """Encode one exact nominal construction ref as a canonical value."""

    if not is_construction_ref(value):
        raise _encoding_error(
            "construction.reference_type_invalid",
            "value is not an exact closed construction ref",
        )
    fields: list[tuple[str, object]] = [
        (
            "canonicalization_profile",
            CanonicalText(value.canonicalization_profile),
        ),
        ("challenge_key", challenge_key_to_canonical(value.challenge_key)),
        ("content_digest", CanonicalText(value.content_digest)),
    ]
    if type(value) in AUTHORED_CONSTRUCTION_REF_TYPES:
        fields.extend(
            (
                ("object_id", CanonicalText(value.object_id)),
                ("object_version", CanonicalText(value.object_version)),
            )
        )
    fields.append(("schema_version", CanonicalText(value.schema_version)))
    return CanonicalNominalRef(
        value.ref_type,
        CanonicalRecord(value.ref_type, tuple(fields)),
    )


def construction_ref_from_canonical(
    value: object, *, expected_type: type | None = None
) -> ConstructionRef:
    """Reconstruct one exact construction ref and reject nominal confusion."""

    if type(value) is not CanonicalNominalRef:
        raise _decoding_error(
            "construction.reference_value_invalid",
            "construction ref must be an exact canonical nominal ref",
        )
    candidates = tuple(
        ref_type
        for ref_type in CONSTRUCTION_REF_TYPES
        if f"{ref_type.OBJECT_KIND}_ref" == value.ref_type
    )
    if expected_type is not None:
        if (
            type(expected_type) is not type
            or expected_type not in CONSTRUCTION_REF_TYPES
        ):
            raise TypeError("expected_type must be an exact construction ref class")
        candidates = tuple(item for item in candidates if item is expected_type)
    if len(candidates) != 1 or value.record.record_type != value.ref_type:
        raise _decoding_error(
            "construction.reference_kind_unknown",
            "construction ref has an unknown or wrong nominal kind",
        )
    ref_type = candidates[0]
    expected_fields = {
        "canonicalization_profile",
        "challenge_key",
        "content_digest",
        "schema_version",
    }
    if ref_type in AUTHORED_CONSTRUCTION_REF_TYPES:
        expected_fields.update({"object_id", "object_version"})
    fields = value.record.field_map()
    if set(fields) != expected_fields:
        raise _decoding_error(
            "construction.reference_fields_invalid",
            "construction ref has missing, unknown, or extra fields",
        )
    text_fields = expected_fields - {"challenge_key"}
    if any(type(fields[name]) is not CanonicalText for name in text_fields):
        raise _decoding_error(
            "construction.reference_value_invalid",
            "construction ref scalar fields must be canonical TEXT",
        )
    try:
        if ref_type in AUTHORED_CONSTRUCTION_REF_TYPES:
            result: ConstructionRef = ref_type(
                challenge_key_from_canonical(fields["challenge_key"]),
                fields["object_id"].value,
                fields["object_version"].value,
                fields["schema_version"].value,
                fields["canonicalization_profile"].value,
                fields["content_digest"].value,
            )
        else:
            result = ref_type(
                challenge_key_from_canonical(fields["challenge_key"]),
                fields["schema_version"].value,
                fields["canonicalization_profile"].value,
                fields["content_digest"].value,
            )
    except (AuthoringError, ConstructionValidationError) as exc:
        raise _decoding_error(
            "construction.reference_value_invalid",
            "construction ref contains malformed identity fields",
        ) from exc
    return reconstruct_construction_ref(result)


def encode_construction_ref(value: object) -> bytes:
    """Encode one exact construction ref as a standalone canonical value."""

    try:
        return encode_value(construction_ref_to_canonical(value))
    except AuthoringError as exc:
        raise _encoding_error(
            "construction.reference_encoding_failed",
            "construction ref cannot be encoded",
        ) from exc


def decode_construction_ref(
    payload: object, *, expected_type: type | None = None
) -> ConstructionRef:
    """Decode one exact construction ref with trailing-byte rejection."""

    if type(payload) is not bytes:
        raise _decoding_error(
            "construction.reference_payload_type_invalid",
            "construction ref payload must be exact immutable bytes",
        )
    try:
        canonical = decode_value(payload)
    except AuthoringError as exc:
        raise _decoding_error(
            "construction.reference_decoding_failed",
            "construction ref payload is malformed or has trailing bytes",
        ) from exc
    result = construction_ref_from_canonical(canonical, expected_type=expected_type)
    if not hmac.compare_digest(encode_construction_ref(result), payload):
        raise _decoding_error(
            "construction.reference_noncanonical",
            "construction ref payload is not in unique canonical form",
        )
    return result


def canonical_record(record_type: object, fields: object) -> CanonicalRecord:
    """Build a closed composable record from exact name/construction-value pairs."""

    if type(fields) is not tuple:
        raise _encoding_error(
            "construction.canonical_fields_type_invalid",
            "record fields must be an exact tuple",
        )
    adapted: list[tuple[str, CanonicalValue]] = []
    for field in fields:
        if type(field) is not tuple or len(field) != 2 or type(field[0]) is not str:
            raise _encoding_error(
                "construction.canonical_field_invalid",
                "each field must be an exact name/value pair",
            )
        adapted.append((field[0], to_canonical_value(field[1])))
    try:
        return CanonicalRecord(record_type, tuple(adapted))
    except AuthoringError as exc:
        raise _encoding_error(
            "construction.canonical_record_invalid",
            "record type or fields are not canonical",
        ) from exc


# Descriptive compatibility spellings share the one exact framing law above.
encode_construction_document = construction_document
decode_construction_document = decode_document


def construction_content_digest(payload: object) -> str:
    """Delegate exact construction-byte hashing to B-02A tagged SHA-256."""

    try:
        return authoring_tagged_sha256(payload)
    except AuthoringError as exc:
        raise _encoding_error(
            "construction.digest_payload_type_invalid",
            "digest input must be exact immutable bytes",
        ) from exc


content_digest = construction_content_digest


def verify_document_digest(payload: object, expected_digest: object) -> bytes:
    """Decode a document and verify its exact tagged digest before returning bytes."""

    decoded = decode_document(payload)
    del decoded
    if type(expected_digest) is not str or not hmac.compare_digest(
        construction_content_digest(payload), expected_digest
    ):
        raise ConstructionReferenceMismatchError(
            "construction.reference_digest_mismatch",
            "construction document does not match the expected digest",
        )
    return bytes(payload)


__all__ = [
    "CONSTRUCTION_DOCUMENT_HEADER",
    "CONSTRUCTION_OBJECT_KINDS",
    "MODEL_CANONICAL_FIELD_REGISTRY_V1",
    "DecodedConstructionDocument",
    "canonical_record",
    "construction_content_digest",
    "construction_document",
    "construction_ref_from_canonical",
    "construction_ref_to_canonical",
    "content_digest",
    "decode_construction_document",
    "decode_construction_ref",
    "decode_document",
    "decode_model",
    "encode_construction_document",
    "encode_construction_ref",
    "encode_model",
    "from_canonical_value",
    "to_canonical_value",
    "verify_document_digest",
]
