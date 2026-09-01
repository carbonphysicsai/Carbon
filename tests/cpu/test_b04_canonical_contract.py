"""Exact D11 canonical framing, ref registry, and reconstruction checks."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import subprocess
import sys
from dataclasses import replace
from types import MappingProxyType

import pytest

import carbon.evaluation.canonical as canonical_runtime
from carbon.authoring.canonical import (
    CanonicalNominalRef,
    CanonicalRecord,
    CanonicalText,
    CanonicalUnion,
    encode_value,
    tagged_sha256,
)
from carbon.evaluation.assets import ReferenceArtifact
from carbon.evaluation.canonical import (
    REFERENCE_TRUTH_CANONICAL_OBJECT_KINDS,
    canonical_bytes,
    canonical_record,
    decode_canonical_bytes,
    verify_canonical_ref,
)
from carbon.evaluation.errors import (
    ReferenceCanonicalDecodingError,
    ReferenceCanonicalEncodingError,
    ReferenceInputCode,
    ReferenceValidationError,
)
from carbon.evaluation.execution import ReferenceRunRecord
from carbon.evaluation.fixtures import build_b04_fixture_reference_graph
from carbon.evaluation.model import (
    PinnedReferenceIdentity,
    ReferenceAuthorityTargetBinding,
    ReferenceExecutionTarget,
    RunArtifactBinding,
)
from carbon.evaluation.policy import ReferencePolicy, ReferencePolicyEntry
from carbon.evaluation.refs import (
    REFERENCE_TRUTH_CANONICALIZATION_PROFILE,
    REFERENCE_TRUTH_DOCUMENT_HEADER,
    REFERENCE_TRUTH_REF_TYPES,
    REFERENCE_TRUTH_SCHEMA_VERSION,
    decode_reference_truth_ref,
    encode_reference_truth_ref,
    reconstruct_reference_truth_ref,
    reference_truth_ref_from_canonical,
    reference_truth_ref_to_canonical,
    require_reference_truth_ref,
)
from carbon.registry.model import ChallengeKey

_EXPECTED_RECORD_TYPES = (
    "precomputed_reference_source_manifest",
    "reference_policy",
    "reference_policy_entry",
    "reference_composition",
    "primary_reference_request",
    "witness_reference_request",
    "primary_run_grant",
    "witness_run_grant",
    "reference_resolution_record",
    "reference_run_record",
    "reference_comparison_record",
    "reference_artifact",
    "fixture_reference_asset",
    "truth_asset_admission_grant_issuance_record",
    "truth_asset_admission_grant",
    "truth_asset_admission_decision_record",
    "truth_asset",
)

_FIXTURE_CANONICAL_GOLDENS = {
    "precomputed_reference_source_manifest": (
        "992673508952c1e1ff6e378018b33b24b40cbd3eadd67f8cd48081bed722d178",
        "14ff217602455a06186f0dc04094e13a94e828741b050307bd683414f9150242",
        16395,
        451,
    ),
    "reference_policy": (
        "91445e1479d02b15d858017bfad6d939a72093ca7198ca9e0f16ed3365b36c39",
        "a95ebea22b626438fb6dadb2524c8d2ca53993411a7656bdf626ec4dc2d6cf1c",
        12112,
        388,
    ),
    "reference_policy_entry": (
        "5aac3cdaadcb4bc09a454ed5418fed81efcd88064ec7a2a6d33a34cdee3e071f",
        "de13dd4621fc2369bd54f47daa65a2c2b894eae5e696d59067654e21d9d13763",
        13259,
        406,
    ),
    "reference_composition": (
        "5d2d5e26d98dfb56da285f45663a28a05d6c81d195849fbf9be0ce7572b4fcd4",
        "895df60efbf2f8c41c6a0e51b05900d19b223e515f817e8ab31b710b641eb8e2",
        12215,
        403,
    ),
    "primary_reference_request": (
        "84e330dfc71dc87f43e95fe5ac094bfb33a5fcccec9e8f77bd13375550b41990",
        "d47487974afe9c189565d75734da1f98fb7f8b83374600c18817dcc5d7efaa7a",
        8924,
        415,
    ),
    "witness_reference_request": (
        "aaccea3d41748dac6a29089a154c63d5751083a4a6ecc89cd996bda7564e0981",
        "eca72f1e4e586568ad628957429d2244be84f8ef5db3204416ea140ec5e23441",
        8918,
        415,
    ),
    "primary_run_grant": (
        "5be1cb3f87820f5273325656b798f802fc61ba1d010ffb3513656d5900a9e4b8",
        "21bbaae10154ee89f465e6356fa296353b4d9913842fa88bc0f82900ef4c4ae2",
        13305,
        391,
    ),
    "witness_run_grant": (
        "f7408284c88e3429f31d120e6d71b3809c8adddb310ac720fc266414fe1afbf5",
        "3f37c530f4cc8843197712d6a43cb7e767c85686b23cd9944b94d4c7c81619a1",
        12907,
        391,
    ),
    "reference_resolution_record": (
        "7af39a0f32066627e71763275455ed09dc1ba57737912ba8b31fc3fdaba23423",
        "7032bfa6b4968548b1cce621b6e467872e24bc9f6b9c59a5185ed10d53f4fcbe",
        11528,
        421,
    ),
    "reference_run_record": (
        "d5e8779d49e220701f05214b2a6bce63d20a5e51c714195b0be1748332f485eb",
        "67ff1c7d240fe5a65e07a48d78aab18d88e51812e67e876571a24ac642ccdfa4",
        35221,
        400,
    ),
    "reference_comparison_record": (
        "de12bb23f0d28bb9ca7f16d4b6426d841b1747dd5f9c6c915e2fb02b27d92710",
        "21160c69598c47c8a22dc0f0a35814bf99de5cd8c478d84a148294cad4b23ad0",
        17500,
        421,
    ),
    "reference_artifact": (
        "6488de27c2b705af1ae9dda9251d016c4491eb2a3b13517e2507958938794bc4",
        "bc274c478b4b84f476b7f52a986839a59aee0a587c285dbbf0198ff5bf3c7698",
        26778,
        394,
    ),
    "fixture_reference_asset": (
        "3de1895f299e227a747c9b06360037b5b898b9ff6a6a8b6e7f350c56e98900a3",
        "d5e61f342196014c24ce35e6c666e034ea5d893b46b8602f6229c04047555a95",
        2696,
        409,
    ),
}


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode('ascii')).hexdigest()}"


def test_d11_profile_header_and_ref_registry_are_exact_and_ordered() -> None:
    assert REFERENCE_TRUTH_SCHEMA_VERSION == "1.0"
    assert (
        REFERENCE_TRUTH_CANONICALIZATION_PROFILE
        == "carbon_reference_truth_canonical_v1"
    )
    assert REFERENCE_TRUTH_DOCUMENT_HEADER == (
        b"carbon.reference-truth.canonical.v1\x00"
    )
    assert REFERENCE_TRUTH_CANONICAL_OBJECT_KINDS == _EXPECTED_RECORD_TYPES
    assert tuple(item.RECORD_TYPE for item in REFERENCE_TRUTH_REF_TYPES) == (
        _EXPECTED_RECORD_TYPES
    )
    assert len(REFERENCE_TRUTH_REF_TYPES) == len(set(REFERENCE_TRUTH_REF_TYPES)) == 17


def test_nominal_ref_lookup_registry_is_exact_and_immutable() -> None:
    from carbon.evaluation.refs import _REF_TYPES_BY_RECORD_TYPE

    assert type(_REF_TYPES_BY_RECORD_TYPE) is MappingProxyType
    assert tuple(_REF_TYPES_BY_RECORD_TYPE) == _EXPECTED_RECORD_TYPES
    assert tuple(_REF_TYPES_BY_RECORD_TYPE.values()) == REFERENCE_TRUTH_REF_TYPES
    with pytest.raises(TypeError):
        _REF_TYPES_BY_RECORD_TYPE["forbidden"] = object


@pytest.mark.parametrize("ref_type", REFERENCE_TRUTH_REF_TYPES)
def test_each_nominal_ref_round_trips_exactly_and_is_redacted(ref_type: type) -> None:
    challenge = ChallengeKey("b04_ref_roundtrip", "1.0")
    original = ref_type(challenge, _digest(ref_type.RECORD_TYPE))
    encoded = encode_reference_truth_ref(original)
    reconstructed = decode_reference_truth_ref(encoded, ref_type)

    assert type(reconstructed) is ref_type
    assert reconstructed == original
    assert reconstruct_reference_truth_ref(original) == original
    assert require_reference_truth_ref(original, ref_type, challenge_key=challenge) == (
        original
    )
    assert encode_reference_truth_ref(reconstructed) == encoded
    assert repr(original) == f"{ref_type.__name__}(<protected>)"
    with pytest.raises(TypeError):
        pickle.dumps(original)


def test_nominal_ref_family_and_challenge_substitution_reject() -> None:
    challenge = ChallengeKey("b04_ref_binding", "1.0")
    first_type, second_type = REFERENCE_TRUTH_REF_TYPES[:2]
    first = first_type(challenge, _digest("first"))

    with pytest.raises(ReferenceCanonicalDecodingError):
        decode_reference_truth_ref(encode_reference_truth_ref(first), second_type)
    with pytest.raises(ReferenceValidationError) as captured:
        require_reference_truth_ref(
            first,
            first_type,
            challenge_key=ChallengeKey("b04_other_challenge", "1.0"),
        )
    assert captured.value.code == ReferenceInputCode.CROSS_CHALLENGE.value


def test_incomplete_exact_nominal_ref_is_normalized_across_ref_entry_points() -> None:
    ref_type = REFERENCE_TRUTH_REF_TYPES[1]
    partial = object.__new__(ref_type)
    calls = (
        reconstruct_reference_truth_ref,
        lambda value: require_reference_truth_ref(value, ref_type),
        reference_truth_ref_to_canonical,
        encode_reference_truth_ref,
    )

    for call in calls:
        with pytest.raises(ReferenceValidationError) as captured:
            call(partial)
        assert captured.value.__cause__ is None
        assert captured.value.__context__ is None


def test_incomplete_exact_canonical_nominal_ref_decodes_fail_closed() -> None:
    with pytest.raises(ReferenceCanonicalDecodingError) as captured:
        reference_truth_ref_from_canonical(object.__new__(CanonicalNominalRef))
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


@pytest.mark.parametrize("payload", (b"", b"unknown", b"\x00" * 64))
def test_malformed_ref_bytes_fail_with_closed_non_echoing_error(payload: bytes) -> None:
    with pytest.raises(ReferenceCanonicalDecodingError) as captured:
        decode_reference_truth_ref(payload)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    if payload:
        assert payload.hex() not in f"{captured.value!r} {captured.value}"


def _fixture_record_families() -> tuple[object, ...]:
    graph = build_b04_fixture_reference_graph()
    return (
        graph.precomputed_manifest,
        graph.policy,
        graph.entries[0],
        graph.compositions[0],
        graph.primary_request,
        graph.witness_request,
        graph.primary_grant,
        graph.witness_grant,
        graph.primary_resolution,
        graph.primary_run,
        graph.comparison,
        graph.primary_artifact,
        graph.primary_fixture_asset,
    )


@pytest.mark.parametrize("record_type", (ReferencePolicyEntry, ReferenceRunRecord))
def test_incomplete_exact_top_level_records_encode_fail_closed(
    record_type: type,
) -> None:
    with pytest.raises(ReferenceCanonicalEncodingError) as captured:
        canonical_bytes(object.__new__(record_type))
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_incomplete_exact_nested_and_tagged_values_encode_fail_closed() -> None:
    with pytest.raises(ReferenceCanonicalEncodingError) as nested:
        canonical_runtime._nested_to_canonical(object.__new__(PinnedReferenceIdentity))
    assert nested.value.__cause__ is None
    assert nested.value.__context__ is None

    run = replace(build_b04_fixture_reference_graph().primary_run)
    object.__setattr__(run, "artifact_binding", object.__new__(RunArtifactBinding))
    with pytest.raises(ReferenceCanonicalEncodingError) as tagged:
        canonical_bytes(run)
    assert tagged.value.__cause__ is None
    assert tagged.value.__context__ is None


def test_incomplete_exact_canonical_carriers_decode_fail_closed() -> None:
    with pytest.raises(ReferenceCanonicalDecodingError) as record:
        canonical_runtime._nested_from_canonical(
            object.__new__(CanonicalRecord),
            PinnedReferenceIdentity,
        )
    assert record.value.__cause__ is None
    assert record.value.__context__ is None

    policy_schema = canonical_runtime._ensure_schemas().top_by_type[ReferencePolicy]
    optional_codec = dict(policy_schema.fields)["supersedes"]
    with pytest.raises(ReferenceCanonicalDecodingError) as union:
        canonical_runtime._decode_field(
            object.__new__(CanonicalUnion),
            optional_codec,
        )
    assert union.value.__cause__ is None
    assert union.value.__context__ is None


_HOSTILE_CANONICAL_SECRET = "b04_hostile_canonical_secret"


class _HostileCanonicalScalar:
    def __eq__(self, other: object) -> bool:
        del other
        raise RuntimeError(_HOSTILE_CANONICAL_SECRET)

    def __ne__(self, other: object) -> bool:
        del other
        raise RuntimeError(_HOSTILE_CANONICAL_SECRET)

    def __hash__(self) -> int:
        raise RuntimeError(_HOSTILE_CANONICAL_SECRET)


def _assert_canonical_error_is_closed(error: ReferenceValidationError) -> None:
    assert _HOSTILE_CANONICAL_SECRET not in repr(error)
    assert _HOSTILE_CANONICAL_SECRET not in str(error)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_hostile_exact_nested_ref_behavior_encodes_fail_closed() -> None:
    run = replace(build_b04_fixture_reference_graph().primary_run)
    original = run.case_ref
    forged = object.__new__(type(original))
    for name in (
        "challenge_key",
        "object_id",
        "object_version",
        "canonicalization_profile",
        "content_digest",
        "disclosure_class",
    ):
        object.__setattr__(forged, name, getattr(original, name))
    object.__setattr__(forged, "schema_version", _HostileCanonicalScalar())
    object.__setattr__(run, "case_ref", forged)

    with pytest.raises(ReferenceCanonicalEncodingError) as captured:
        canonical_bytes(run)

    _assert_canonical_error_is_closed(captured.value)


def test_hostile_exact_union_tag_decodes_fail_closed() -> None:
    policy_schema = canonical_runtime._ensure_schemas().top_by_type[ReferencePolicy]
    optional_codec = dict(policy_schema.fields)["supersedes"]
    union = object.__new__(CanonicalUnion)
    object.__setattr__(union, "tag", _HostileCanonicalScalar())
    object.__setattr__(union, "payload", CanonicalRecord("empty_payload", ()))

    with pytest.raises(ReferenceCanonicalDecodingError) as captured:
        canonical_runtime._decode_field(union, optional_codec)

    _assert_canonical_error_is_closed(captured.value)


def test_hostile_exact_nominal_ref_field_key_decodes_fail_closed() -> None:
    record = object.__new__(CanonicalRecord)
    object.__setattr__(record, "record_type", "reference_policy_ref")
    object.__setattr__(
        record,
        "fields",
        ((_HostileCanonicalScalar(), CanonicalText("forbidden")),),
    )
    nominal = object.__new__(CanonicalNominalRef)
    object.__setattr__(nominal, "ref_type", "reference_policy_ref")
    object.__setattr__(nominal, "record", record)

    with pytest.raises(ReferenceCanonicalDecodingError) as captured:
        reference_truth_ref_from_canonical(nominal)

    _assert_canonical_error_is_closed(captured.value)


def test_every_fixture_constructible_record_family_round_trips_exactly() -> None:
    records = _fixture_record_families()
    assert tuple(item.object_kind for item in records) == _EXPECTED_RECORD_TYPES[:13]
    for original in records:
        payload = canonical_bytes(original)
        reconstructed = decode_canonical_bytes(payload, type(original))
        assert type(reconstructed) is type(original)
        assert reconstructed == original
        assert canonical_bytes(reconstructed) == payload
        assert reconstructed.to_ref() == original.to_ref()
        verify_canonical_ref(reconstructed, original.to_ref())


def test_composite_values_reconstruct_children_and_isolate_low_level_mutation() -> None:
    graph = build_b04_fixture_reference_graph()
    run = decode_canonical_bytes(
        canonical_bytes(graph.primary_run),
        ReferenceRunRecord,
    )
    source_execution = run.execution_target
    execution = ReferenceExecutionTarget(
        source_execution.kind,
        source_execution.value,
    )
    target_binding = ReferenceAuthorityTargetBinding.bound(source_execution.value)
    source_content = run.artifact_binding.value
    artifact_binding = RunArtifactBinding.bound(source_content)
    source_provenance = run.provenance_binding
    provenance = replace(source_provenance)

    assert execution.value == source_execution.value
    assert execution.value is not source_execution.value
    assert execution.value.value is not source_execution.value.value
    assert target_binding.value == source_execution.value
    assert target_binding.value is not source_execution.value
    assert target_binding.value.value is not source_execution.value.value
    assert artifact_binding.value == source_content
    assert artifact_binding.value is not source_content
    assert artifact_binding.value.artifact_descriptor_ref is not (
        source_content.artifact_descriptor_ref
    )
    assert provenance.dependency_disclosures == (
        source_provenance.dependency_disclosures
    )
    assert provenance.dependency_disclosures[0] is not (
        source_provenance.dependency_disclosures[0]
    )
    assert provenance.dependency_disclosures[0].evidence_refs[0] is not (
        source_provenance.dependency_disclosures[0].evidence_refs[0]
    )

    target_digest = execution.value.value.content_digest
    artifact_digest = artifact_binding.value.artifact_descriptor_ref.content_digest
    provenance_id = provenance.dependency_disclosures[0].evidence_refs[0].object_id
    object.__setattr__(
        source_execution.value.value,
        "content_digest",
        tagged_sha256(b"mutated-composite-target"),
    )
    object.__setattr__(
        source_content.artifact_descriptor_ref,
        "content_digest",
        tagged_sha256(b"mutated-composite-artifact"),
    )
    object.__setattr__(
        source_provenance.dependency_disclosures[0].evidence_refs[0],
        "object_id",
        "b04_mutated_composite_provenance",
    )
    assert execution.value.value.content_digest == target_digest
    assert target_binding.value.value.content_digest == target_digest
    assert artifact_binding.value.artifact_descriptor_ref.content_digest == (
        artifact_digest
    )
    assert provenance.dependency_disclosures[0].evidence_refs[0].object_id == (
        provenance_id
    )


def test_complete_fixture_graph_matches_frozen_canonical_goldens() -> None:
    records = _fixture_record_families()
    assert tuple(_FIXTURE_CANONICAL_GOLDENS) == _EXPECTED_RECORD_TYPES[:13]
    for record in records:
        document = canonical_bytes(record)
        encoded_ref = encode_reference_truth_ref(record.to_ref())
        expected = _FIXTURE_CANONICAL_GOLDENS[record.object_kind]
        assert (
            hashlib.sha256(document).hexdigest(),
            hashlib.sha256(encoded_ref).hexdigest(),
            len(document),
            len(encoded_ref),
        ) == expected


def _encoded_record(
    record_type: str,
    fields: tuple[tuple[str, object], ...],
) -> bytes:
    chunks = [b"\x09", encode_value(CanonicalText(record_type))]
    chunks.append(len(fields).to_bytes(4, "big"))
    for name, value in fields:
        chunks.append(encode_value(CanonicalText(name)))
        chunks.append(encode_value(value))
    return b"".join(chunks)


@pytest.mark.parametrize("mutation", ("missing", "extra", "reordered", "duplicate"))
def test_record_decoder_rejects_nonexact_field_manifests(mutation: str) -> None:
    policy = build_b04_fixture_reference_graph().policy
    record = canonical_record(policy)
    fields = list(record.fields)
    if mutation == "missing":
        fields.pop()
    elif mutation == "extra":
        fields.append(("zz_unregistered_field", CanonicalText("forbidden")))
        fields.sort(key=lambda item: item[0].encode("utf-8"))
    elif mutation == "reordered":
        fields[0], fields[1] = fields[1], fields[0]
    else:
        fields.insert(1, fields[0])
    payload = REFERENCE_TRUTH_DOCUMENT_HEADER + _encoded_record(
        record.record_type,
        tuple(fields),
    )

    with pytest.raises(ReferenceCanonicalDecodingError) as captured:
        decode_canonical_bytes(payload, ReferencePolicy)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None


def test_record_decoder_rejects_trailing_bytes_and_expected_type_substitution() -> None:
    policy = build_b04_fixture_reference_graph().policy
    with pytest.raises(ReferenceCanonicalDecodingError) as trailing:
        decode_canonical_bytes(canonical_bytes(policy) + b"\x00", ReferencePolicy)
    assert trailing.value.code == ReferenceInputCode.TRAILING_BYTES.value
    with pytest.raises(ReferenceCanonicalDecodingError):
        decode_canonical_bytes(
            canonical_bytes(policy), type(_fixture_record_families()[0])
        )


@pytest.mark.parametrize("record_name", ("run", "artifact"))
@pytest.mark.parametrize(
    "identity_field",
    ("environment_ref", "implementation_ref", "method_ref"),
)
def test_canonical_decode_rejects_forged_provenance_top_level_binding(
    record_name: str,
    identity_field: str,
) -> None:
    graph = build_b04_fixture_reference_graph()
    record = graph.primary_run if record_name == "run" else graph.primary_artifact
    expected_type = ReferenceRunRecord if record_name == "run" else ReferenceArtifact
    top = canonical_record(record)
    manifest = canonical_record(graph.precomputed_manifest)
    manifest_provenance = dict(manifest.fields)["provenance_binding"]
    assert type(manifest_provenance) is CanonicalRecord
    replacement = dict(manifest_provenance.fields)[identity_field]

    top_fields = list(top.fields)
    provenance_index = next(
        index
        for index, (name, _) in enumerate(top_fields)
        if name == "provenance_binding"
    )
    provenance_name, provenance = top_fields[provenance_index]
    assert type(provenance) is CanonicalRecord
    provenance_fields = list(provenance.fields)
    field_index = next(
        index
        for index, (name, _) in enumerate(provenance_fields)
        if name == identity_field
    )
    assert provenance_fields[field_index][1] != replacement
    provenance_fields[field_index] = (identity_field, replacement)
    top_fields[provenance_index] = (
        provenance_name,
        CanonicalRecord(provenance.record_type, tuple(provenance_fields)),
    )
    payload = REFERENCE_TRUTH_DOCUMENT_HEADER + encode_value(
        CanonicalRecord(top.record_type, tuple(top_fields))
    )

    with pytest.raises(ReferenceCanonicalDecodingError):
        decode_canonical_bytes(payload, expected_type)


_CROSS_PROCESS_SCRIPT = r"""
import json

from carbon.evaluation.canonical import canonical_bytes
from carbon.evaluation.fixtures import build_b04_fixture_reference_graph
from carbon.evaluation.refs import encode_reference_truth_ref

graph = build_b04_fixture_reference_graph()
records = (
    graph.precomputed_manifest,
    graph.policy,
    graph.entries[0],
    graph.compositions[0],
    graph.primary_request,
    graph.witness_request,
    graph.primary_grant,
    graph.witness_grant,
    graph.primary_resolution,
    graph.primary_run,
    graph.comparison,
    graph.primary_artifact,
    graph.primary_fixture_asset,
)
documents = tuple(
    item
    for record in records
    for item in (canonical_bytes(record), encode_reference_truth_ref(record.to_ref()))
)
print(json.dumps([item.hex() for item in documents], separators=(",", ":")))
"""


def _cross_process_documents(hash_seed: str) -> list[str]:
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = hash_seed
    environment["PYTHONPATH"] = "."
    completed = subprocess.run(
        [sys.executable, "-c", _CROSS_PROCESS_SCRIPT],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return json.loads(completed.stdout)


def test_complete_fixture_graph_is_cross_process_hash_seed_deterministic() -> None:
    first = _cross_process_documents("1")
    second = _cross_process_documents("8675309")
    assert len(first) == 26
    assert first == second


_CONCURRENT_FIRST_USE_SCRIPT = r"""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import MappingProxyType

from carbon.evaluation.canonical import _ensure_schemas
from carbon.evaluation.refs import REFERENCE_TRUTH_REF_TYPES

barrier = Barrier(24)

def initialize(_index):
    barrier.wait()
    registry = _ensure_schemas()
    return (
        id(registry),
        tuple(registry.top_by_kind),
        len(registry.nested_by_type),
        tuple(type(mapping) is MappingProxyType for mapping in (
            registry.top_by_type,
            registry.top_by_kind,
            registry.nested_by_type,
            registry.nested_by_tag,
        )),
    )

with ThreadPoolExecutor(max_workers=24) as executor:
    results = tuple(executor.map(initialize, range(24)))

registry = _ensure_schemas()
mutation_rejections = 0
for mapping in (
    registry.top_by_type,
    registry.top_by_kind,
    registry.nested_by_type,
    registry.nested_by_tag,
):
    try:
        mapping[object()] = None
    except TypeError:
        mutation_rejections += 1

print(json.dumps({
    "one_registry": len({item[0] for item in results}) == 1,
    "record_types": list(results[0][1]),
    "nested_count": results[0][2],
    "all_immutable": all(all(item[3]) for item in results),
    "mutation_rejections": mutation_rejections,
    "ref_types": [item.RECORD_TYPE for item in REFERENCE_TRUTH_REF_TYPES],
    "exact_record_ref_pairing": all(
        schema.record_type == ref_type.RECORD_TYPE
        and ref_type.__name__ == f"{schema.exact_type.__name__}Ref"
        for schema, ref_type in zip(
            registry.top_by_kind.values(), REFERENCE_TRUTH_REF_TYPES
        )
    ),
    "pair_count": len(tuple(registry.top_by_kind.values())),
}, sort_keys=True))
"""


def test_schema_registry_concurrent_first_use_is_atomic_and_immutable() -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "."
    completed = subprocess.run(
        [sys.executable, "-c", _CONCURRENT_FIRST_USE_SCRIPT],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    result = json.loads(completed.stdout)

    assert result["one_registry"] is True
    assert result["all_immutable"] is True
    assert result["mutation_rejections"] == 4
    assert result["nested_count"] > 0
    assert tuple(result["record_types"]) == _EXPECTED_RECORD_TYPES
    assert tuple(result["ref_types"]) == _EXPECTED_RECORD_TYPES
    assert result["exact_record_ref_pairing"] is True
    assert result["pair_count"] == 17
