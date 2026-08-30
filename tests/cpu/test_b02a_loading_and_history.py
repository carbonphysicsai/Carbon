"""B-02A digest-first loading, structural origin, and immutable history tests."""

from __future__ import annotations

import hashlib
import os
import shutil
import threading
from dataclasses import replace

import pytest

import carbon.authoring.history as history_module
from carbon.authoring.canonical import tagged_sha256
from carbon.authoring.errors import (
    AuthoringValidationError,
    CanonicalDecodingError,
    ReferenceMismatchError,
)
from carbon.authoring.graph import scientific_authoring_graph_fingerprint
from carbon.authoring.history import AuthoringHistoryError, AuthoringHistoryStore
from carbon.authoring.loading import (
    AuthoringLoadError,
    AuthoringOriginIssuer,
    FixtureAuthoringCapability,
    FixtureOrigin,
    GraphOriginTag,
    LoadedAuthoringArtifact,
    compose_authoring_graph_origin,
    load_authoring_bytes,
)
from carbon.authoring.model import (
    ApplicabilityBinding,
    PrecisionLiteral,
    TimeMode,
)
from carbon.authoring.physical import (
    BoundaryConditionContract,
    InitialConditionContract,
    PhysicalSystemSpec,
    Presence,
    PresenceKind,
    TimeContract,
    ValueFieldContract,
)
from carbon.authoring.primitives import (
    AUTHORING_SCHEMA_VERSION,
    CANONICALIZATION_PROFILE,
    MAX_CANONICAL_DOCUMENT_BYTES,
    MAX_CANONICAL_PAYLOAD_BYTES,
)
from carbon.authoring.refs import GlobalScope, PhysicalSystemSpecRef, owner_ref
from carbon.registry import ChallengeKey


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _owner(kind: str, label: str) -> object:
    return owner_ref(
        kind,
        scope_binding=GlobalScope(),
        object_id=label,
        object_version="1.0",
        content_digest=_digest(f"{kind}:{label}"),
    )


def _not_applicable(label: str) -> ApplicabilityBinding[object]:
    return ApplicabilityBinding.not_applicable(_owner("applicability_reason", label))


def _physical(
    *,
    object_version: str = "1.0",
    supersedes: PhysicalSystemSpecRef | None = None,
) -> PhysicalSystemSpec:
    geometry = _owner("geometry_domain", "fixture_geometry")
    value_field = ValueFieldContract(
        field_id="state",
        semantic_role_ref=_owner("semantic_clause", "fixture_state_semantics"),
        representation_ref=_owner("representation", "fixture_representation"),
        unit_ref=_owner("unit", "fixture_unit"),
        shape_contract=(),
        precision_contract=(PrecisionLiteral.FLOAT64,),
        geometry_binding=ApplicabilityBinding.bound(geometry),
        presence=Presence(PresenceKind.REQUIRED),
        admissibility_refs=(),
        nonfinite_policy="REJECT",
    )
    return PhysicalSystemSpec(
        object_kind="physical_system_spec",
        schema_version=AUTHORING_SCHEMA_VERSION,
        canonicalization_profile=CANONICALIZATION_PROFILE,
        challenge_key=ChallengeKey("fixture_physics", "1.0"),
        object_id="fixture_physical_system",
        object_version=object_version,
        supersedes=(
            ApplicabilityBinding.bound(supersedes)
            if supersedes is not None
            else _not_applicable("first_version")
        ),
        governing_job_ref=_owner("semantic_clause", "fixture_job"),
        governing_law_refs=(_owner("semantic_clause", "fixture_law"),),
        assumptions=(),
        causal_inputs=(value_field,),
        required_physical_quantities=(replace(value_field, field_id="required_state"),),
        geometry_domain_ref=geometry,
        boundary_conditions=BoundaryConditionContract(()),
        initial_conditions=InitialConditionContract(()),
        time_contract=TimeContract(
            mode=TimeMode.STEADY,
            time_coordinate_binding=_not_applicable("steady_coordinate"),
            horizon_binding=_not_applicable("steady_horizon"),
            endpoint_inclusion_semantic_ref=_owner(
                "semantic_clause", "fixture_endpoint"
            ),
            time_unit_ref=_owner("unit", "fixture_time_unit"),
        ),
        operating_envelope_ref=_owner("operating_envelope", "fixture_envelope"),
        claim_scope_ref=_owner("claim_scope", "fixture_claim"),
        missing_input_policy="REJECT",
    )


def _fixture_loaded(
    physical: PhysicalSystemSpec,
    *,
    evidence_label: str = "fixture_origin_evidence",
) -> LoadedAuthoringArtifact:
    provenance = _owner("provenance", "fixture_provenance")
    origin = FixtureAuthoringCapability().issue_origin(
        fixture_registration_ref=_owner("fixture_registration", "fixture_registration"),
        source_provenance_refs=(provenance,),
    )
    return load_authoring_bytes(
        physical.to_ref(),
        physical.canonical_bytes(),
        origin=origin,
        origin_evidence_ref=_owner("authoring_origin_evidence", evidence_label),
        source_provenance_refs=(provenance,),
        audit_evidence_refs=(_owner("audit_evidence", "fixture_audit"),),
        qualification_evidence=_not_applicable("fixture_not_qualified"),
    )


class _AllowOriginAuthority:
    def verify_authoring_origin(self, **_: object) -> bool:
        return True


class _AllowGraphAuthority:
    def verify_registered_graph(self, **_: object) -> bool:
        return True


def _registered_loaded(
    physical: PhysicalSystemSpec,
    *,
    evidence_label: str,
) -> LoadedAuthoringArtifact:
    provenance = _owner("provenance", "registered_provenance")
    origin = AuthoringOriginIssuer(_AllowOriginAuthority()).issue_registered(
        registration_ref=_owner("authoring_registration", "registration"),
        authority_evidence_refs=(_owner("authority_evidence", "authority"),),
        source_provenance_refs=(provenance,),
    )
    return load_authoring_bytes(
        physical.to_ref(),
        physical.canonical_bytes(),
        origin=origin,
        origin_evidence_ref=_owner("authoring_origin_evidence", evidence_label),
        source_provenance_refs=(provenance,),
        audit_evidence_refs=(_owner("audit_evidence", "registered_audit"),),
        qualification_evidence=ApplicabilityBinding.bound(
            _owner("qualification_evidence_bundle", "qualification")
        ),
    )


def test_loader_verifies_digest_before_closed_round_trip() -> None:
    physical = _physical()
    loaded = _fixture_loaded(physical)

    assert loaded.expected_ref == physical.to_ref()
    assert type(loaded.authored_object) is PhysicalSystemSpec
    assert loaded.authored_object == physical
    assert loaded.authored_object is not physical
    assert _fixture_loaded(physical).authored_object is not loaded.authored_object

    wrong_ref = replace(physical.to_ref(), content_digest=_digest("wrong"))
    with pytest.raises(ValueError, match="expected digest"):
        load_authoring_bytes(
            wrong_ref,
            physical.canonical_bytes(),
            origin=loaded.origin,
            origin_evidence_ref=loaded.origin_evidence_ref,
            source_provenance_refs=loaded.source_provenance_refs,
            audit_evidence_refs=loaded.audit_evidence_refs,
            qualification_evidence=loaded.qualification_evidence,
        )


@pytest.mark.parametrize(
    "size",
    (
        MAX_CANONICAL_PAYLOAD_BYTES,
        MAX_CANONICAL_PAYLOAD_BYTES + 1,
        MAX_CANONICAL_DOCUMENT_BYTES,
    ),
)
def test_loader_uses_complete_document_bound_not_element_bound(size: int) -> None:
    source = _fixture_loaded(_physical())
    payload = b"x" * size
    expected = replace(source.expected_ref, content_digest=tagged_sha256(payload))

    with pytest.raises(CanonicalDecodingError):
        load_authoring_bytes(
            expected,
            payload,
            origin=source.origin,
            origin_evidence_ref=source.origin_evidence_ref,
            source_provenance_refs=source.source_provenance_refs,
            audit_evidence_refs=source.audit_evidence_refs,
            qualification_evidence=source.qualification_evidence,
        )


def test_loader_rejects_bytes_over_complete_document_bound() -> None:
    source = _fixture_loaded(_physical())
    payload = b"x" * (MAX_CANONICAL_DOCUMENT_BYTES + 1)

    with pytest.raises(AuthoringValidationError) as captured:
        load_authoring_bytes(
            source.expected_ref,
            payload,
            origin=source.origin,
            origin_evidence_ref=source.origin_evidence_ref,
            source_provenance_refs=source.source_provenance_refs,
            audit_evidence_refs=source.audit_evidence_refs,
            qualification_evidence=source.qualification_evidence,
        )
    assert captured.value.code == "authoring.document_bytes_too_large"


def test_origin_and_loaded_result_have_no_caller_authority_constructor() -> None:
    provenance = (_owner("provenance", "fixture_provenance"),)
    with pytest.raises((TypeError, AuthoringLoadError)):
        FixtureOrigin(
            _owner("fixture_registration", "fixture_registration"),
            provenance,
        )
    with pytest.raises((TypeError, AuthoringLoadError)):
        LoadedAuthoringArtifact(
            expected_ref=_physical().to_ref(),
            recomputed_ref=_physical().to_ref(),
            verified_bytes=b"not-authoring-bytes",
            authored_object=_physical(),
            origin=_fixture_loaded(_physical()).origin,
            origin_evidence_ref=_owner(
                "authoring_origin_evidence", "fixture_origin_evidence"
            ),
            source_provenance_refs=provenance,
            audit_evidence_refs=(_owner("audit_evidence", "audit"),),
            qualification_evidence=_not_applicable("not_qualified"),
        )


@pytest.mark.skipif(os.name == "nt", reason="canonical secure history I/O is POSIX")
def test_history_is_exact_create_only_and_preserves_supersession(tmp_path) -> None:
    store = AuthoringHistoryStore(tmp_path / "history")
    first = _physical()
    first_loaded = _fixture_loaded(first)
    first_ref = store.put(first_loaded)

    assert store.contains(first_ref)
    assert store.get(first_ref).authored_object == first
    assert not hasattr(store, "latest")

    second = _physical(object_version="2.0", supersedes=first_ref)
    second_ref = store.put(_fixture_loaded(second, evidence_label="second_origin"))
    assert second_ref != first_ref
    assert store.get(first_ref).authored_object.object_version == "1.0"
    assert store.get(second_ref).authored_object.object_version == "2.0"

    conflicting = _registered_loaded(first, evidence_label="registered_origin")
    with pytest.raises(AuthoringHistoryError, match="different immutable bytes"):
        store.put(conflicting)

    revocation = _owner("authoring_revocation", "prospective_revocation")
    store.register_revocation(first_ref, revocation)
    assert store.is_revoked(first_ref)
    assert store.get(first_ref).authored_object == first


@pytest.mark.skipif(os.name == "nt", reason="canonical secure history I/O is POSIX")
def test_history_rejects_missing_predecessor(tmp_path) -> None:
    store = AuthoringHistoryStore(tmp_path / "history")
    absent = _physical().to_ref()
    successor = _physical(object_version="2.0", supersedes=absent)

    with pytest.raises(AuthoringHistoryError, match="predecessor is absent"):
        store.put(_fixture_loaded(successor, evidence_label="successor_origin"))


@pytest.mark.skipif(os.name == "nt", reason="canonical secure history I/O is POSIX")
def test_corrupt_predecessor_payload_cannot_authorize_successor(tmp_path) -> None:
    store = AuthoringHistoryStore(tmp_path / "history")
    first = _physical()
    first_ref = store.put(_fixture_loaded(first))
    target = store.root.joinpath(*store._parts_for(first_ref))
    tampered = bytearray(target.read_bytes())
    tampered[
        -1
    ] ^= 1  # Payload is the envelope's final bounded blob; header stays exact.
    target.write_bytes(tampered)

    with pytest.raises(ReferenceMismatchError):
        store.contains(first_ref)

    successor = _physical(object_version="2.0", supersedes=first_ref)
    with pytest.raises(ReferenceMismatchError):
        store.put(_fixture_loaded(successor, evidence_label="successor_origin"))


@pytest.mark.skipif(os.name == "nt", reason="canonical secure history I/O is POSIX")
def test_history_does_not_publish_a_partial_final_record(
    tmp_path,
    monkeypatch,
) -> None:
    store = AuthoringHistoryStore(tmp_path / "history")
    loaded = _fixture_loaded(_physical())
    expected_ref = loaded.expected_ref
    write_started = threading.Event()
    release_write = threading.Event()
    original_write = history_module.os.write
    errors: list[BaseException] = []

    def pausing_write(descriptor: int, data: object) -> int:
        view = memoryview(data)  # type: ignore[arg-type]
        if not write_started.is_set():
            written = original_write(descriptor, view[: min(32, len(view))])
            write_started.set()
            if not release_write.wait(timeout=10):
                raise RuntimeError("history publication test was not released")
            return written
        return original_write(descriptor, view)

    def write_record() -> None:
        try:
            store.put(loaded)
        except BaseException as exc:  # noqa: BLE001 - captured across test thread.
            errors.append(exc)

    monkeypatch.setattr(history_module.os, "write", pausing_write)
    worker = threading.Thread(target=write_record)
    worker.start()
    assert write_started.wait(timeout=10)
    assert not store.contains(expected_ref)
    release_write.set()
    worker.join(timeout=10)

    assert not worker.is_alive()
    assert errors == []
    assert store.get(expected_ref).expected_ref == expected_ref


@pytest.mark.skipif(os.name == "nt", reason="canonical secure history I/O is POSIX")
def test_history_concurrent_identical_put_is_idempotent(tmp_path) -> None:
    store = AuthoringHistoryStore(tmp_path / "history")
    loaded = _fixture_loaded(_physical())
    barrier = threading.Barrier(8)
    results: list[PhysicalSystemSpecRef] = []
    errors: list[BaseException] = []

    def write_record() -> None:
        try:
            barrier.wait(timeout=10)
            ref = store.put(loaded)
            assert type(ref) is PhysicalSystemSpecRef
            results.append(ref)
        except BaseException as exc:  # noqa: BLE001 - captured across test thread.
            errors.append(exc)

    workers = [threading.Thread(target=write_record) for _ in range(8)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)

    assert all(not worker.is_alive() for worker in workers)
    assert errors == []
    assert results == [loaded.expected_ref] * 8


@pytest.mark.skipif(os.name == "nt", reason="canonical secure history I/O is POSIX")
def test_history_rejects_record_growth_during_read(tmp_path, monkeypatch) -> None:
    store = AuthoringHistoryStore(tmp_path / "history")
    ref = store.put(_fixture_loaded(_physical()))
    target = store.root.joinpath(*store._parts_for(ref))
    original_fstat = history_module.os.fstat
    regular_fstat_calls = 0

    def growing_fstat(descriptor: int):
        nonlocal regular_fstat_calls
        metadata = original_fstat(descriptor)
        if history_module.stat.S_ISREG(metadata.st_mode):
            regular_fstat_calls += 1
            if regular_fstat_calls == 1:
                with target.open("ab") as stream:
                    stream.write(b"concurrent-growth")
                    stream.flush()
                    os.fsync(stream.fileno())
        return metadata

    monkeypatch.setattr(history_module.os, "fstat", growing_fstat)
    with pytest.raises(AuthoringHistoryError) as captured:
        store.get(ref)
    assert captured.value.code == "authoring.history_snapshot_changed"


@pytest.mark.skipif(os.name == "nt", reason="canonical secure history I/O is POSIX")
@pytest.mark.parametrize("special_kind", ("symlink", "fifo"))
def test_history_rejects_special_file_at_exact_record_path(
    tmp_path,
    special_kind: str,
) -> None:
    store = AuthoringHistoryStore(tmp_path / "history")
    loaded = _fixture_loaded(_physical())
    target = store.root.joinpath(*store._parts_for(loaded.expected_ref))
    target.parent.mkdir(parents=True)
    if special_kind == "symlink":
        source = tmp_path / "untrusted-history-source"
        source.write_bytes(b"not a history envelope")
        target.symlink_to(source)
    else:
        os.mkfifo(target)

    with pytest.raises(AuthoringHistoryError) as captured:
        store.put(loaded)
    assert captured.value.code in {
        "authoring.history_not_regular",
        "authoring.history_path_escape",
    }


@pytest.mark.skipif(os.name == "nt", reason="canonical secure history I/O is POSIX")
@pytest.mark.parametrize("tamper", ("empty", "symlink", "fifo"))
def test_history_rejects_malformed_or_special_revocation_entry(
    tmp_path,
    tamper: str,
) -> None:
    store = AuthoringHistoryStore(tmp_path / "history")
    ref = store.put(_fixture_loaded(_physical()))
    event = _owner("authoring_revocation", "prospective_revocation")
    event_parts = store._revocation_parts(ref, event)
    target = store.root.joinpath(*event_parts)
    target.parent.mkdir(parents=True)
    if tamper == "empty":
        target.write_bytes(b"")
    elif tamper == "symlink":
        source = tmp_path / "untrusted-revocation-source"
        source.write_bytes(b"not a revocation envelope")
        target.symlink_to(source)
    else:
        os.mkfifo(target)

    with pytest.raises(AuthoringHistoryError):
        store.is_revoked(ref)


@pytest.mark.skipif(os.name == "nt", reason="canonical secure history I/O is POSIX")
def test_history_revocation_binds_exact_target_and_event_filename(tmp_path) -> None:
    store = AuthoringHistoryStore(tmp_path / "history")
    first = _physical()
    first_ref = store.put(_fixture_loaded(first))
    second = _physical(object_version="2.0", supersedes=first_ref)
    second_ref = store.put(_fixture_loaded(second, evidence_label="second_origin"))
    event = _owner("authoring_revocation", "prospective_revocation")
    store.register_revocation(second_ref, event)

    second_path = store.root.joinpath(*store._revocation_parts(second_ref, event))
    wrong_target = store.root.joinpath(*store._revocation_parts(first_ref, event))
    wrong_target.parent.mkdir(parents=True)
    shutil.copy2(second_path, wrong_target)
    with pytest.raises(AuthoringHistoryError) as captured:
        store.is_revoked(first_ref)
    assert captured.value.code == "authoring.history_revocation_target_mismatch"

    wrong_target.unlink()
    store.register_revocation(first_ref, event)
    correct_path = store.root.joinpath(*store._revocation_parts(first_ref, event))
    wrong_name = correct_path.with_name(f"{'0' * 64}.rev")
    correct_path.rename(wrong_name)
    with pytest.raises(AuthoringHistoryError) as captured:
        store.is_revoked(first_ref)
    assert captured.value.code == "authoring.history_revocation_name_mismatch"


def test_fixture_origin_taints_registered_successor_graph() -> None:
    first = _physical()
    first_loaded = _fixture_loaded(first)
    second = _physical(object_version="2.0", supersedes=first.to_ref())
    second_loaded = _registered_loaded(second, evidence_label="second_registered")

    graph = compose_authoring_graph_origin(
        root=second_loaded,
        dependencies=(first_loaded,),
        expected_dependency_refs=(first_loaded.expected_ref,),
        composition_audit_ref=_owner("origin_composition_audit", "composition_audit"),
        registered_authority=_AllowGraphAuthority(),
    )

    assert graph.graph_origin is GraphOriginTag.FIXTURE_DERIVED


def test_graph_fingerprint_pins_exact_resolved_origin_manifest() -> None:
    loaded = _fixture_loaded(_physical())
    graph = compose_authoring_graph_origin(
        root=loaded,
        dependencies=(),
        expected_dependency_refs=(),
        composition_audit_ref=_owner("origin_composition_audit", "composition_audit"),
        registered_authority=None,
    )
    same = compose_authoring_graph_origin(
        root=loaded,
        dependencies=(),
        expected_dependency_refs=(),
        composition_audit_ref=_owner("origin_composition_audit", "composition_audit"),
        registered_authority=None,
    )
    different_origin = _fixture_loaded(
        _physical(),
        evidence_label="different_fixture_origin_evidence",
    )
    changed = compose_authoring_graph_origin(
        root=different_origin,
        dependencies=(),
        expected_dependency_refs=(),
        composition_audit_ref=_owner("origin_composition_audit", "composition_audit"),
        registered_authority=None,
    )

    fingerprint = scientific_authoring_graph_fingerprint(graph)
    assert fingerprint == scientific_authoring_graph_fingerprint(same)
    assert fingerprint != scientific_authoring_graph_fingerprint(changed)
    assert fingerprint.startswith("sha256:") and len(fingerprint) == 71
    with pytest.raises(TypeError):
        scientific_authoring_graph_fingerprint(object())
