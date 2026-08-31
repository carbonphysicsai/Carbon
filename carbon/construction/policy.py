"""Exact resolved training-only sampling policy for B-02B.

The policy is inert identity data.  It contains registered abstract purposes,
but no entropy domain, seed, draw, case, population, weighting, or realized
sample.  Actual randomness remains an A4/consumer responsibility.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass
from typing import ClassVar

from carbon.authoring.canonical import CanonicalText, CanonicalTuple
from carbon.authoring.errors import AuthoringError, AuthoringValidationError
from carbon.authoring.primitives import (
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
)
from carbon.authoring.refs import (
    TrainingSupportContractRef,
    reconstruct_top_level_ref,
)
from carbon.construction import model as m
from carbon.construction.canonical import (
    canonical_record,
    construction_document,
    decode_document,
    encode_model,
    from_canonical_value,
    to_canonical_value,
)
from carbon.construction.catalog import (
    _validate_authority_identifier_allowing_exact_identifiers,
    _validate_authority_identifier_allowing_exact_tokens,
    _validate_authority_identifiers,
)
from carbon.construction.errors import (
    ConstructionCanonicalDecodingError,
    ConstructionReferenceMismatchError,
    ConstructionValidationError,
)
from carbon.construction.refs import (
    CONSTRUCTION_CANONICALIZATION_PROFILE,
    CONSTRUCTION_SCHEMA_VERSION,
    ParameterCatalogRef,
    TrainingSamplingPolicyRef,
    make_resolved_ref,
    reconstruct_authored_ref,
    verify_construction_ref,
)
from carbon.registry import ChallengeKey

_POLICY_FIELDS = (
    "object_kind",
    "schema_version",
    "canonicalization_profile",
    "challenge_key",
    "training_support_ref",
    "catalog_ref",
    "policy_state",
    "bindings",
    "randomness_purposes",
)


def _invalid(code: str, message: str, path: str) -> ConstructionValidationError:
    return ConstructionValidationError(code, message, path=path)


def _challenge_key(value: object) -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.challenge_key_invalid",
            "challenge_key must be an exact valid A3 ChallengeKey",
            "/challenge_key",
        ) from exc


def _copy_model(value: object, expected_type: type, field: str) -> object:
    if type(value) is not expected_type:
        raise _invalid(
            "construction.nominal_type_invalid",
            f"{field} must have exact nominal type {expected_type.__name__}",
            f"/{field}",
        )
    return from_canonical_value(to_canonical_value(value), expected_type)


def _copy_training_ref(value: object) -> TrainingSupportContractRef:
    if type(value) is not TrainingSupportContractRef:
        raise _invalid(
            "construction.authoring_ref_type_invalid",
            "training_support_ref must use its exact B-02A nominal type",
            "/training_support_ref",
        )
    try:
        copied = reconstruct_top_level_ref(value)
    except AuthoringValidationError as exc:
        raise _invalid(
            "construction.authoring_ref_invalid",
            "training_support_ref is not a valid exact B-02A reference",
            "/training_support_ref",
        ) from exc
    assert type(copied) is TrainingSupportContractRef
    return copied


def _copy_catalog_ref(value: object) -> ParameterCatalogRef:
    if type(value) is not ParameterCatalogRef:
        raise _invalid(
            "construction.reference_type_invalid",
            "catalog_ref must use its exact nominal type",
            "/catalog_ref",
        )
    copied = reconstruct_authored_ref(value)
    assert type(copied) is ParameterCatalogRef
    return copied


def _exact_tuple(value: object, field: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise _invalid(
            "construction.tuple_type_invalid",
            f"{field} must be an exact built-in tuple",
            f"/{field}",
        )
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _invalid(
            "construction.tuple_size_invalid",
            f"{field} exceeds the canonical item bound",
            f"/{field}",
        )
    return value


def _ordered_bindings(value: object) -> tuple[m.ResolvedTrainingBinding, ...]:
    copied = tuple(
        _copy_model(item, m.ResolvedTrainingBinding, "bindings")
        for item in _exact_tuple(value, "bindings")
    )
    surface_ids = tuple(item.surface_id for item in copied)
    if len(set(surface_ids)) != len(surface_ids):
        raise _invalid(
            "construction.training_binding_duplicate",
            "training bindings must name unique catalog surfaces",
            "/bindings",
        )
    return tuple(sorted(copied, key=lambda item: item.surface_id.encode("ascii")))


def _canonical_purposes(
    value: object,
) -> tuple[m.TrainingRandomnessPurpose, ...]:
    copied = tuple(
        _copy_model(item, m.TrainingRandomnessPurpose, "randomness_purposes")
        for item in _exact_tuple(value, "randomness_purposes")
    )
    if len(set(copied)) != len(copied):
        raise _invalid(
            "construction.randomness_purpose_duplicate",
            "randomness purposes must be a duplicate-free canonical union",
            "/randomness_purposes",
        )
    return tuple(sorted(copied, key=encode_model))


def _validate_binding_scopes(
    bindings: tuple[m.ResolvedTrainingBinding, ...], challenge_key: ChallengeKey
) -> None:
    for binding in bindings:
        m.validate_owner_ref_scope(
            binding.executable_semantics_ref,
            expected_challenge_key=challenge_key,
        )


def _validate_policy_authority_carriers(
    *,
    catalog_ref: ParameterCatalogRef,
    bindings: tuple[m.ResolvedTrainingBinding, ...],
    purposes: tuple[m.TrainingRandomnessPurpose, ...],
) -> None:
    identities: list[tuple[str, str]] = [
        (catalog_ref.object_id, "/catalog_ref/object_id"),
    ]
    for binding in bindings:
        identities.append((binding.surface_id, "/bindings/surface_id"))
        if type(binding.resolved_value.value) is str:
            identities.append(
                (binding.resolved_value.value, "/bindings/resolved_value/value")
            )
        _validate_authority_identifier_allowing_exact_tokens(
            binding.executable_semantics_ref.object_id,
            allowed_tokens=frozenset({"executable"}),
            path="/bindings/executable_semantics_ref/object_id",
        )
    for purpose in purposes:
        _validate_authority_identifier_allowing_exact_identifiers(
            purpose.purpose_id,
            allowed_identifiers=frozenset({"training_draw"}),
            path="/randomness_purposes/purpose_id",
        )
        identities.append(
            (purpose.role_key_label, "/randomness_purposes/role_key_label")
        )
    _validate_authority_identifiers(tuple(identities))


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ResolvedTrainingSamplingPolicy:
    """One exact resolved ``R_strategy`` value, without realized randomness."""

    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    training_support_ref: TrainingSupportContractRef
    catalog_ref: ParameterCatalogRef
    policy_state: m.PolicyState
    bindings: tuple[m.ResolvedTrainingBinding, ...]
    randomness_purposes: tuple[m.TrainingRandomnessPurpose, ...]

    OBJECT_KIND: ClassVar[str] = "resolved_training_sampling_policy"

    def __post_init__(self) -> None:
        if type(self) is not ResolvedTrainingSamplingPolicy:
            raise _invalid(
                "construction.subclass_rejected",
                "ResolvedTrainingSamplingPolicy subclasses are rejected",
                "/type",
            )
        if type(self.object_kind) is not str or self.object_kind != self.OBJECT_KIND:
            raise _invalid(
                "construction.object_kind_invalid",
                "training policy has a wrong exact object kind",
                "/object_kind",
            )
        if (
            type(self.schema_version) is not str
            or self.schema_version != CONSTRUCTION_SCHEMA_VERSION
        ):
            raise _invalid(
                "construction.schema_version_unsupported",
                "training policy supports only construction schema 1.0",
                "/schema_version",
            )
        if (
            type(self.canonicalization_profile) is not str
            or self.canonicalization_profile != CONSTRUCTION_CANONICALIZATION_PROFILE
        ):
            raise _invalid(
                "construction.canonicalization_profile_invalid",
                "training policy uses an unknown canonicalization profile",
                "/canonicalization_profile",
            )
        key = _challenge_key(self.challenge_key)
        training_ref = _copy_training_ref(self.training_support_ref)
        catalog_ref = _copy_catalog_ref(self.catalog_ref)
        if training_ref.challenge_key != key or catalog_ref.challenge_key != key:
            raise _invalid(
                "construction.reference_challenge_mismatch",
                "training policy refs must match its exact ChallengeKey",
                "/challenge_key",
            )
        if type(self.policy_state) is not m.PolicyState:
            raise _invalid(
                "construction.policy_state_type_invalid",
                "policy_state must use its exact closed enum type",
                "/policy_state",
            )
        bindings = _ordered_bindings(self.bindings)
        purposes = _canonical_purposes(self.randomness_purposes)
        if self.policy_state is m.PolicyState.BASE_NO_OVERRIDE:
            if bindings or purposes:
                raise _invalid(
                    "construction.policy_state_mismatch",
                    "BASE_NO_OVERRIDE requires empty bindings and purposes",
                    "/policy_state",
                )
        elif not bindings:
            raise _invalid(
                "construction.policy_state_mismatch",
                "RESOLVED_OVERRIDES requires at least one training binding",
                "/policy_state",
            )
        _validate_binding_scopes(bindings, key)
        _validate_policy_authority_carriers(
            catalog_ref=catalog_ref,
            bindings=bindings,
            purposes=purposes,
        )

        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(self, "training_support_ref", training_ref)
        object.__setattr__(self, "catalog_ref", catalog_ref)
        object.__setattr__(self, "bindings", bindings)
        object.__setattr__(self, "randomness_purposes", purposes)

    def canonical_bytes(self) -> bytes:
        return training_sampling_policy_canonical_bytes(self)

    def to_ref(self) -> TrainingSamplingPolicyRef:
        return training_sampling_policy_to_ref(self)


_VERIFIED_POLICIES: weakref.WeakSet = weakref.WeakSet()


def _mark_training_sampling_policy_verified(
    policy: ResolvedTrainingSamplingPolicy,
) -> ResolvedTrainingSamplingPolicy:
    if type(policy) is not ResolvedTrainingSamplingPolicy:
        raise _invalid(
            "construction.policy_derivation_unverified",
            "only an exact resolved training policy can be verified",
            "/policy",
        )
    _VERIFIED_POLICIES.add(policy)
    return policy


def _require_training_sampling_policy_verified(
    policy: ResolvedTrainingSamplingPolicy,
) -> None:
    if policy not in _VERIFIED_POLICIES:
        raise _invalid(
            "construction.policy_derivation_unverified",
            "policy identity is available only after compiler or decoder verification",
            "/policy",
        )


def _canonical_tuple(values: tuple[object, ...], *, set_like: bool) -> CanonicalTuple:
    return CanonicalTuple(
        tuple(to_canonical_value(value) for value in values),
        set_like=set_like,
    )


def training_sampling_policy_canonical_bytes(
    policy: ResolvedTrainingSamplingPolicy,
) -> bytes:
    """Return the complete domain-separated identity bytes for one policy."""

    if type(policy) is not ResolvedTrainingSamplingPolicy:
        raise _invalid(
            "construction.nominal_type_invalid",
            "policy must use the exact ResolvedTrainingSamplingPolicy type",
            "/policy",
        )
    _require_training_sampling_policy_verified(policy)
    record = canonical_record(
        policy.OBJECT_KIND,
        (
            ("object_kind", policy.object_kind),
            ("schema_version", policy.schema_version),
            ("canonicalization_profile", policy.canonicalization_profile),
            ("challenge_key", policy.challenge_key),
            ("training_support_ref", policy.training_support_ref),
            ("catalog_ref", policy.catalog_ref),
            ("policy_state", policy.policy_state),
            ("bindings", _canonical_tuple(policy.bindings, set_like=False)),
            (
                "randomness_purposes",
                _canonical_tuple(policy.randomness_purposes, set_like=True),
            ),
        ),
    )
    return construction_document(policy.object_kind, policy.schema_version, record)


def training_sampling_policy_to_ref(
    policy: ResolvedTrainingSamplingPolicy,
) -> TrainingSamplingPolicyRef:
    """Derive the exact digest-only identity reference for *policy*."""

    result = make_resolved_ref(
        TrainingSamplingPolicyRef,
        canonical_bytes=training_sampling_policy_canonical_bytes(policy),
        challenge_key=policy.challenge_key,
    )
    assert type(result) is TrainingSamplingPolicyRef
    return result


def _text_field(fields: object, name: str) -> str:
    value = fields.get(name)
    if type(value) is not CanonicalText:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_text_invalid",
            f"{name} must be exact canonical TEXT",
            path=f"/{name}",
        )
    return value.value


def _tuple_field(
    fields: object,
    name: str,
    expected_type: type,
    *,
    set_like: bool,
) -> tuple[object, ...]:
    value = fields.get(name)
    if type(value) is not CanonicalTuple:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_tuple_invalid",
            f"{name} must be an exact canonical tuple",
            path=f"/{name}",
        )
    return tuple(from_canonical_value(item, expected_type) for item in value.items)


def decode_training_sampling_policy(
    payload: object,
    *,
    expected_ref: object,
) -> ResolvedTrainingSamplingPolicy:
    """Decode and digest-verify one exact training policy before returning it."""

    if type(expected_ref) is not TrainingSamplingPolicyRef:
        raise ConstructionReferenceMismatchError(
            "construction.reference_type_mismatch",
            "expected_ref must be an exact TrainingSamplingPolicyRef",
        )
    decoded = decode_document(
        payload,
        expected_object_kind=ResolvedTrainingSamplingPolicy.OBJECT_KIND,
        expected_schema_version=CONSTRUCTION_SCHEMA_VERSION,
        allowed_record_fields=_POLICY_FIELDS,
    )
    fields = decoded.record.field_map()
    policy = ResolvedTrainingSamplingPolicy(
        object_kind=_text_field(fields, "object_kind"),
        schema_version=_text_field(fields, "schema_version"),
        canonicalization_profile=_text_field(fields, "canonicalization_profile"),
        challenge_key=from_canonical_value(fields["challenge_key"], ChallengeKey),
        training_support_ref=_decode_top_ref(
            fields["training_support_ref"], TrainingSupportContractRef
        ),
        catalog_ref=from_canonical_value(fields["catalog_ref"], ParameterCatalogRef),
        policy_state=_enum_field(fields, "policy_state", m.PolicyState),
        bindings=_tuple_field(
            fields,
            "bindings",
            m.ResolvedTrainingBinding,
            set_like=False,
        ),
        randomness_purposes=_tuple_field(
            fields,
            "randomness_purposes",
            m.TrainingRandomnessPurpose,
            set_like=True,
        ),
    )
    _mark_training_sampling_policy_verified(policy)
    if type(payload) is not bytes or policy.canonical_bytes() != payload:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_document_noncanonical",
            "training policy fields are not in their unique canonical order",
        )
    verify_construction_ref(
        expected_ref,
        canonical_bytes=payload,
        challenge_key=policy.challenge_key,
    )
    return policy


def _decode_top_ref(value: object, expected_type: type) -> object:
    from carbon.authoring.canonical import top_level_ref_from_canonical

    try:
        result = top_level_ref_from_canonical(value)
    except AuthoringError as exc:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_authoring_ref_invalid",
            "top-level authoring ref is malformed",
        ) from exc
    if type(result) is not expected_type:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_authoring_ref_type_invalid",
            "top-level authoring ref has the wrong exact nominal type",
        )
    return result


def _enum_field(fields: object, name: str, enum_type: type) -> object:
    value = fields.get(name)
    if type(value) is not CanonicalText:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_enum_invalid",
            f"{name} must be exact canonical TEXT",
            path=f"/{name}",
        )
    try:
        return enum_type(value.value)
    except ValueError as exc:
        raise ConstructionCanonicalDecodingError(
            "construction.canonical_enum_invalid",
            f"{name} contains an unknown closed literal",
            path=f"/{name}",
        ) from exc


def _copy_entry_tuple(value: object) -> tuple[m.ParameterCatalogEntry, ...]:
    return tuple(
        _copy_model(item, m.ParameterCatalogEntry, "entries")
        for item in _exact_tuple(value, "entries")
    )


def _copy_surface_tuple(value: object) -> tuple[m.ResolvedSurface, ...]:
    allowed = (m.SelectedSurface, m.DefaultedSurface, m.NotApplicableSurface)
    copied: list[m.ResolvedSurface] = []
    for item in _exact_tuple(value, "resolved_surfaces"):
        if type(item) not in allowed:
            raise _invalid(
                "construction.union_type_invalid",
                "resolved_surfaces contains an unknown closed variant",
                "/resolved_surfaces",
            )
        copied.append(_copy_model(item, type(item), "resolved_surfaces"))
    return tuple(copied)


def _build_training_sampling_policy(
    *,
    challenge_key: object,
    training_support_ref: object,
    catalog_ref: object,
    entries: object,
    resolved_surfaces: object,
) -> tuple[ResolvedTrainingSamplingPolicy, TrainingSamplingPolicyRef]:
    """Derive exact ``R_strategy`` identity from catalog-owned training levers."""

    key = _challenge_key(challenge_key)
    copied_entries = _copy_entry_tuple(entries)
    copied_surfaces = _copy_surface_tuple(resolved_surfaces)
    entries_by_id = {entry.surface_id: entry for entry in copied_entries}
    surfaces_by_id = {surface.surface_id: surface for surface in copied_surfaces}
    if (
        len(entries_by_id) != len(copied_entries)
        or len(surfaces_by_id) != len(copied_surfaces)
        or set(entries_by_id) != set(surfaces_by_id)
    ):
        raise _invalid(
            "construction.training_resolution_incomplete",
            "training-policy derivation requires one resolution per catalog entry",
            "/resolved_surfaces",
        )

    bindings: list[m.ResolvedTrainingBinding] = []
    purposes: list[m.TrainingRandomnessPurpose] = []
    for surface_id in sorted(entries_by_id):
        entry = entries_by_id[surface_id]
        surface = surfaces_by_id[surface_id]
        if surface.consumer_target != entry.consumer_target:
            raise _invalid(
                "construction.training_resolution_target_mismatch",
                "resolved training surface has a different consumer target",
                f"/resolved_surfaces/{surface_id}",
            )
        lever = entry.training_lever_binding
        if type(lever) is not m.BoundTrainingLever:
            continue
        if type(entry.semantic_owner_binding) is not m.TrainingSupportSemanticOwner:
            raise _invalid(
                "construction.training_owner_mismatch",
                "a bound training lever must be owned by training support",
                f"/entries/{surface_id}",
            )
        if type(surface) is m.NotApplicableSurface:
            continue
        if surface.value.value_type is not entry.value_type:
            raise _invalid(
                "construction.training_resolution_type_mismatch",
                "resolved training value has a different exact surface type",
                f"/resolved_surfaces/{surface_id}",
            )
        bindings.append(
            m.ResolvedTrainingBinding(
                surface_id=surface_id,
                kind=lever.kind,
                resolved_value=surface.value,
                executable_semantics_ref=lever.executable_semantics_ref,
            )
        )
        purposes.extend(lever.randomness_purposes)

    policy = ResolvedTrainingSamplingPolicy(
        object_kind=ResolvedTrainingSamplingPolicy.OBJECT_KIND,
        schema_version=CONSTRUCTION_SCHEMA_VERSION,
        canonicalization_profile=CONSTRUCTION_CANONICALIZATION_PROFILE,
        challenge_key=key,
        training_support_ref=training_support_ref,
        catalog_ref=catalog_ref,
        policy_state=(
            m.PolicyState.RESOLVED_OVERRIDES
            if bindings
            else m.PolicyState.BASE_NO_OVERRIDE
        ),
        bindings=tuple(bindings),
        randomness_purposes=tuple(set(purposes)),
    )
    _mark_training_sampling_policy_verified(policy)
    return policy, policy.to_ref()


decode_resolved_training_sampling_policy = decode_training_sampling_policy


__all__ = [
    "ResolvedTrainingSamplingPolicy",
    "decode_resolved_training_sampling_policy",
    "decode_training_sampling_policy",
    "training_sampling_policy_canonical_bytes",
    "training_sampling_policy_to_ref",
]
