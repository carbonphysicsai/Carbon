"""Exact public schema, nominal-ref, and canonical foundation checks."""

from __future__ import annotations

from dataclasses import fields

import pytest
from test_b02b_catalog import _fixture

from carbon import construction
from carbon.authoring.refs import PhysicalSystemSpecRef
from carbon.construction.canonical import (
    CONSTRUCTION_DOCUMENT_HEADER,
    decode_construction_ref,
    decode_model,
    encode_construction_ref,
    encode_model,
)
from carbon.construction.catalog import CandidateAssemblyContract, ParameterCatalog
from carbon.construction.errors import (
    ConstructionCanonicalDecodingError,
    ConstructionValidationError,
)
from carbon.construction.model import (
    CompilerIdentity,
    SurfaceValue,
    SurfaceValueType,
)
from carbon.construction.plan import ResolvedConstructionPlan
from carbon.construction.policy import ResolvedTrainingSamplingPolicy
from carbon.construction.refs import (
    CandidateAssemblyContractRef,
    ParameterCatalogRef,
    ResolvedConstructionPlanRef,
    TrainingSamplingPolicyRef,
)


def _field_names(value_type: type) -> tuple[str, ...]:
    return tuple(field.name for field in fields(value_type))


def test_public_root_is_explicit_sorted_unique_and_identity_preserving() -> None:
    assert construction.__all__[:4] == [
        "COMPILE_ISSUE_CODES",
        "CONSTRUCTION_CANONICALIZATION_PROFILE",
        "CONSTRUCTION_SCHEMA_VERSION",
        "SUPPORTED_COMPILER_IDENTITY",
    ]
    assert len(construction.__all__) == len(set(construction.__all__))
    assert all(hasattr(construction, name) for name in construction.__all__)
    assert construction.CompilerIdentity is CompilerIdentity
    assert construction.CandidateAssemblyContractRef is CandidateAssemblyContractRef
    assert construction.compile_strategy.__module__ == "carbon.construction.compiler"


def test_contract_field_order_is_exact_and_distinct_from_canonical_sorting() -> None:
    assert _field_names(CompilerIdentity) == (
        "compiler_id",
        "compiler_version",
        "implementation_digest",
        "construction_schema_version",
        "canonicalization_profile",
    )
    assert _field_names(CandidateAssemblyContractRef) == (
        "challenge_key",
        "object_id",
        "object_version",
        "schema_version",
        "canonicalization_profile",
        "content_digest",
    )
    assert _field_names(ParameterCatalogRef) == _field_names(
        CandidateAssemblyContractRef
    )
    assert _field_names(TrainingSamplingPolicyRef) == (
        "challenge_key",
        "schema_version",
        "canonicalization_profile",
        "content_digest",
    )
    assert _field_names(ResolvedConstructionPlanRef) == _field_names(
        TrainingSamplingPolicyRef
    )
    assert _field_names(CandidateAssemblyContract)[:7] == (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "object_id",
        "object_version",
        "physical_system_ref",
    )
    assert _field_names(ParameterCatalog)[:7] == (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "object_id",
        "object_version",
        "candidate_assembly_ref",
    )
    assert _field_names(ResolvedTrainingSamplingPolicy) == (
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
    assert _field_names(ResolvedConstructionPlan)[0:7] == (
        "object_kind",
        "schema_version",
        "canonicalization_profile",
        "challenge_key",
        "strategy_schema_version",
        "strategy_hash",
        "authoring_origin_binding",
    )


def test_nested_models_and_refs_round_trip_with_nominal_and_trailing_rejection() -> (
    None
):
    fixture = _fixture()
    compiler = fixture["compiler"]
    payload = encode_model(compiler)
    assert decode_model(payload, CompilerIdentity) == compiler
    with pytest.raises(ConstructionCanonicalDecodingError):
        decode_model(payload + b"\x00", CompilerIdentity)

    assembly_ref = fixture["assembly"].to_ref()
    ref_payload = encode_construction_ref(assembly_ref)
    assert (
        decode_construction_ref(
            ref_payload,
            expected_type=CandidateAssemblyContractRef,
        )
        == assembly_ref
    )
    with pytest.raises(ConstructionCanonicalDecodingError):
        decode_construction_ref(
            ref_payload,
            expected_type=ParameterCatalogRef,
        )
    assert type(assembly_ref) is not type(fixture["assembly"].physical_system_ref)
    assert type(assembly_ref) is not PhysicalSystemSpecRef


def test_one_exact_document_header_subclass_and_negative_zero_laws() -> None:
    fixture = _fixture()
    payload = fixture["assembly"].canonical_bytes()
    assert payload.startswith(CONSTRUCTION_DOCUMENT_HEADER)
    assert CONSTRUCTION_DOCUMENT_HEADER == b"carbon.construction.canonical.v1\x00"

    class CompilerSubclass(CompilerIdentity):
        pass

    with pytest.raises(ConstructionValidationError):
        CompilerSubclass(
            "fixture_compiler",
            "1.0",
            "sha256:" + "0" * 64,
            "1.0",
            "carbon_construction_canonical_v1",
        )
    with pytest.raises(ConstructionValidationError) as error:
        SurfaceValue(SurfaceValueType.FLOAT64, -0.0)
    assert error.value.code == "construction.negative_zero"
