from __future__ import annotations

import dataclasses
import json
import threading
from pathlib import Path

import pytest

from carbon.evidence_archive import (
    SYNTHETIC_FIXTURE_PREFIX,
    AcknowledgementReason,
    AcknowledgementState,
    ArchiveCode,
    ArchiveFailure,
    ArtifactInput,
    ArtifactState,
    AttemptRelation,
    AttemptRelationKind,
    CapacityLimits,
    EvidenceArchive,
    EvidenceCompleteness,
    EvidenceUseAssessment,
    ExecutionDisposition,
    KeyMaterial,
    NamedUse,
    PersistenceStage,
    QualificationOrigin,
    ScientificResultState,
    SourceBinding,
    SourceFailureClass,
    StageJournal,
    UseEligibility,
    canonical_bytes,
    content_digest,
    derive_object_key,
    encrypt_artifact,
    synthetic_capture_profile,
    validate_object_key,
)
from carbon.execution import DurableExecutionBinding, ExecutionScope
from carbon.fees import (
    AdmissionKind,
    ExecutionAttemptHandle,
    ExecutionEnvironmentPin,
    RequesterIdentity,
    StrategyHash,
    SubmissionId,
)
from carbon.registry import ChallengeKey
from carbon.seeding import EvaluationBinding, SeedPin


def _sha(value: str) -> str:
    return "sha256:" + value * 64


def _execution_binding(
    *,
    attempt: int = 1,
    admission_kind: AdmissionKind = AdmissionKind.FIXTURE,
) -> DurableExecutionBinding:
    return DurableExecutionBinding(
        handle=ExecutionAttemptHandle(
            SubmissionId("00000000-0000-4000-8000-000000000001"),
            attempt,
            admission_kind,
            SeedPin(
                ChallengeKey("burgers", "1.0"),
                "generator-v1",
                _sha("1"),
                "score-v1",
                _sha("2"),
                EvaluationBinding(b"e" * 32),
            ),
            ExecutionEnvironmentPin("synthetic-cpu-v1", _sha("3")),
        ),
        requester_identity=RequesterIdentity("synthetic-owner"),
        strategy_hash=StrategyHash(_sha("4")),
        scope=(
            ExecutionScope.FIXTURE_DEVELOPMENT
            if admission_kind is AdmissionKind.FIXTURE
            else ExecutionScope.REAL_PATH_NON_LIVE
        ),
        resolved_plan_digest=_sha("5"),
        reconstruction_policy_digest=_sha("6"),
        resource_policy_digest=_sha("7"),
        protected_evaluation_policy_digest=_sha("8"),
    )


def _source(*, attempt: int = 1) -> SourceBinding:
    return SourceBinding.from_execution_binding(
        _execution_binding(attempt=attempt),
        execution_id=f"synthetic-execution-{attempt}",
        physical_attempt_id=f"synthetic-attempt-{attempt}",
    )


def _artifact_inputs(source: SourceBinding, disposition=ExecutionDisposition.COMPLETED):
    profile = synthetic_capture_profile()
    terminal = {
        "source_binding": canonical_bytes(source.payload()),
        "manifest_input": canonical_bytes(profile.payload()),
        "representative_output": SYNTHETIC_FIXTURE_PREFIX + b"output",
        "execution_log": SYNTHETIC_FIXTURE_PREFIX + b"public-safe-log",
        "checkpoint": SYNTHETIC_FIXTURE_PREFIX + b"checkpoint",
    }
    values = []
    for rule in profile.artifact_rules:
        if rule.name in terminal and (
            rule.is_required(disposition)
            or rule.name in {"source_binding", "manifest_input"}
        ):
            values.append(
                ArtifactInput(rule.name, ArtifactState.WRITTEN, terminal[rule.name])
            )
        else:
            values.append(ArtifactInput(rule.name, ArtifactState.INTENTIONALLY_ABSENT))
    return tuple(values)


class MemoryObjects:
    def __init__(self):
        self.values: dict[str, bytes] = {}
        self.quarantined: dict[str, bytes] = {}

    def put_immutable(self, key, body):
        if key in self.values:
            if self.values[key] != body:
                raise ArchiveFailure(ArchiveCode.CONFLICT)
            return False
        self.values[key] = body
        return True

    def get(self, key):
        try:
            return self.values[key]
        except KeyError:
            raise ArchiveFailure(ArchiveCode.STORE) from None

    def list_keys(self, tenant_id):
        return tuple(
            sorted(key for key in self.values if key.split("/")[1] == tenant_id)
        )

    def quarantine(self, key):
        body = self.values.pop(key)
        ref = "quarantine-" + content_digest("q", key.encode())[7:]
        self.quarantined[ref] = body
        return ref


class MemoryCatalogue:
    def __init__(self, limits=None):
        self.limits = limits or CapacityLimits()
        self.admissions = {}
        self.entries = {}
        self.acks = {}
        self.effects = set()
        self.orphans = {}
        self.availability = {}
        self.lock = threading.Lock()

    def reserve(self, entry_id, tenant_id, binding, objects, byte_count):
        digest = content_digest("carbon.evidence-archive.admission.v1", binding)
        candidate = [tenant_id, binding, digest, objects, byte_count, True]
        with self.lock:
            old = self.admissions.get(entry_id)
            if old:
                if old[:5] != candidate[:5]:
                    raise ArchiveFailure(ArchiveCode.CONFLICT)
                return False
            active = [value for value in self.admissions.values() if value[5]]
            if (
                len(active) + 1 > self.limits.max_active_entries
                or sum(value[3] for value in active) + objects > self.limits.max_objects
                or sum(value[4] for value in active) + byte_count
                > self.limits.max_bytes
            ):
                raise ArchiveFailure(ArchiveCode.CAPACITY)
            self.admissions[entry_id] = candidate
            return True

    def release_reservation(self, entry_id):
        self.admissions[entry_id][5] = False

    def relation_source(self, entry_id):
        value = self.admissions.get(entry_id)
        if value is None:
            return None
        source = json.loads(value[1])["entry"]["source"]
        return source["tenant_id"], source["submission_id"], source["attempt_number"]

    def finalize(
        self,
        entry_id,
        profile_digest,
        entry_payload,
        manifest_identity,
        artifacts,
        manifest_payload,
    ):
        candidate = (
            profile_digest,
            entry_payload,
            manifest_identity,
            artifacts,
            manifest_payload,
        )
        old = self.entries.get(entry_id)
        if old is not None:
            if old != candidate:
                raise ArchiveFailure(ArchiveCode.CONFLICT)
            return False
        self.entries[entry_id] = candidate
        return True

    def record_acknowledgement(self, entry_id, payload, ref, *, release):
        old = self.acks.get(ref)
        if old is not None:
            if old != (entry_id, payload):
                raise ArchiveFailure(ArchiveCode.CONFLICT)
            return False
        self.acks[ref] = entry_id, payload
        if release:
            self.admissions[entry_id][5] = False
        return True

    def outbox(self):
        return tuple(
            (
                content_digest("carbon.evidence-archive.outbox.v1", value[4]),
                "ARCHIVE_CATALOGUED",
                value[4].decode(),
            )
            for value in self.entries.values()
        )

    def consume(self, consumer_id, event_id, payload):
        value = consumer_id, event_id
        if value in self.effects:
            return False
        self.effects.add(value)
        return True

    def object_keys(self, tenant_id):
        return tuple(
            record.object_key
            for entry in self.entries.values()
            for record in entry[3]
            if record.object_key is not None
        )

    def verify_commit(self, entry_id, entry_payload, manifest_identity, artifacts):
        value = self.entries.get(entry_id)
        return value is not None and value[:4] == (
            value[0],
            entry_payload,
            manifest_identity,
            artifacts,
        )

    def record_orphan(self, object_key, quarantine_ref, body):
        self.orphans.setdefault(object_key, (quarantine_ref, body))

    def health_counts(self):
        return (
            sum(value[5] for value in self.admissions.values()),
            len(self.entries),
            len(self.outbox()),
            len(self.orphans),
        )

    def append_availability(self, entry_id, artifact_name, state, reason_ref):
        self.availability.setdefault(entry_id, []).append(
            (artifact_name, state, reason_ref)
        )

    def latest_availability(self, entry_id):
        return {
            name: state for name, state, _reason in self.availability.get(entry_id, [])
        }


def _archive(tmp_path, *, limits=None, fault_hook=None):
    limits = limits or CapacityLimits()
    catalogue = MemoryCatalogue(limits)
    journal = StageJournal(tmp_path / "spool.sqlite3", limits)
    objects = MemoryObjects()
    return (
        EvidenceArchive(catalogue, journal, objects, fault_hook=fault_hook),
        catalogue,
        journal,
        objects,
    )


def _admit(
    archive, source=None, relation=None, disposition=ExecutionDisposition.COMPLETED
):
    source = source or _source()
    profile = synthetic_capture_profile()
    return archive.admit(
        source,
        relation or AttemptRelation(AttemptRelationKind.INITIAL),
        profile,
        execution_disposition=disposition,
        scientific_result_state=ScientificResultState.SOURCE_RESULT_REF,
        scientific_result_ref="synthetic-result-1",
        declared_objects=7,
        declared_bytes=64 * 1024,
    )


def test_runtime_axes_and_use_policy_are_independent_and_closed() -> None:
    entry_id = _sha("a")
    assessments = {
        use: EvidenceUseAssessment.for_synthetic_profile(entry_id, use)
        for use in NamedUse
    }
    assert assessments[NamedUse.INTERNAL_AUDIT].eligibility is UseEligibility.ELIGIBLE
    assert all(
        assessment.eligibility is UseEligibility.INELIGIBLE
        for use, assessment in assessments.items()
        if use is not NamedUse.INTERNAL_AUDIT
    )
    assert QualificationOrigin.FIXTURE.value == "FIXTURE"
    assert set(ExecutionDisposition) == {
        ExecutionDisposition.NOT_DISPATCHED,
        ExecutionDisposition.RUNNING,
        ExecutionDisposition.INTERRUPTED,
        ExecutionDisposition.CANCELLED,
        ExecutionDisposition.EARLY_STOPPED,
        ExecutionDisposition.COMPLETED,
    }
    contract = json.loads(
        Path("Design_Specs/evidence_capture_contract_v1.json").read_text(
            encoding="utf-8"
        )
    )
    axes = contract["status_axes"]
    assert set(axes["execution_disposition"]) == {
        value.value for value in ExecutionDisposition
    }
    assert set(axes["scientific_result"]) == {
        value.value for value in ScientificResultState
    }
    assert set(axes["evidence_completeness"]) == {
        value.value for value in EvidenceCompleteness
    }
    assert set(axes["qualification_origin"]) == {
        value.value for value in QualificationOrigin
    }
    assert set(axes["named_use_eligibility"]) == {
        value.value for value in UseEligibility
    }
    assert set(contract["source_failure_classes"]) == {
        value.value for value in SourceFailureClass
    }
    for case in contract["contract_cases"]:
        ExecutionDisposition(case["execution_disposition"])
        ScientificResultState(case["scientific_result"])
        EvidenceCompleteness(case["evidence_completeness"])
        QualificationOrigin(case["qualification_origin"])
        UseEligibility(case["named_use_eligibility"])
        SourceFailureClass(case["source_failure_class"])


def test_only_fixture_c01_binding_can_enter_synthetic_profile() -> None:
    with pytest.raises(ArchiveFailure) as captured:
        SourceBinding.from_execution_binding(
            _execution_binding(admission_kind=AdmissionKind.PRODUCTION),
            execution_id="real-execution",
            physical_attempt_id="real-attempt",
        )
    assert captured.value.code is ArchiveCode.DENIED


def test_positive_ack_requires_verified_manifest_catalogue_and_current_objects(
    tmp_path,
) -> None:
    archive, catalogue, journal, objects = _archive(tmp_path)
    admission = _admit(archive)
    result = archive.archive(
        admission,
        synthetic_capture_profile(),
        _artifact_inputs(admission.entry.source),
        KeyMaterial("ephemeral-test-key-v1", b"k" * 32),
    )
    assert result.completeness is EvidenceCompleteness.COMPLETE
    assert result.acknowledgement.state is AcknowledgementState.VERIFIED_DURABLE
    assert result.acknowledgement.reason is AcknowledgementReason.VERIFIED
    assert result.acknowledgement.synthetic_only is True
    assert result.acknowledgement.eligible_for_real_finalization is False
    assert result.acknowledgement.eligible_for_network_use is False
    assert len(catalogue.entries) == len(catalogue.acks) == 1
    assert all(SYNTHETIC_FIXTURE_PREFIX not in body for body in objects.values.values())
    assert journal.envelope(admission.entry.archive_entry_id, "checkpoint") is not None
    health = archive.health()
    assert health.catalogue_available is health.object_store_available is True
    assert health.active_catalogue_reservations == 0
    assert health.active_journal_reservations == 0
    assert health.archived_entries == health.outbox_events == 1
    unavailable, completeness = archive.verify_current(
        result.entry, synthetic_capture_profile(), result.manifest, None
    )
    assert unavailable.reason is AcknowledgementReason.KEY_UNAVAILABLE
    assert completeness is EvidenceCompleteness.UNAVAILABLE


@pytest.mark.parametrize(
    "stage",
    tuple(PersistenceStage),
)
def test_crash_at_every_stage_resumes_without_false_ack_or_duplicate_effect(
    tmp_path, stage
) -> None:
    fired = False

    def crash(current):
        nonlocal fired
        if not fired and current is stage:
            fired = True
            raise RuntimeError("synthetic crash")

    archive, catalogue, journal, objects = _archive(tmp_path, fault_hook=crash)
    source = _source()
    try:
        admission = _admit(archive, source=source)
        archive.archive(
            admission,
            synthetic_capture_profile(),
            _artifact_inputs(source),
            KeyMaterial("ephemeral-test-key-v1", b"k" * 32),
        )
        archive.consume_outbox("audit-consumer")
    except RuntimeError:
        pass
    restarted = EvidenceArchive(
        catalogue, StageJournal(tmp_path / "spool.sqlite3", journal.limits), objects
    )
    admission = _admit(restarted, source=source)
    result = restarted.archive(
        admission,
        synthetic_capture_profile(),
        _artifact_inputs(source),
        KeyMaterial("ephemeral-test-key-v1", b"k" * 32),
    )
    assert result.acknowledgement.state is AcknowledgementState.VERIFIED_DURABLE
    restarted.consume_outbox("audit-consumer")
    assert len(catalogue.entries) == len(catalogue.acks) == len(catalogue.effects) == 1


def test_required_missing_blocks_but_optional_missing_does_not_become_required(
    tmp_path,
) -> None:
    archive, _, _, _ = _archive(tmp_path)
    admission = _admit(archive)
    values = list(_artifact_inputs(admission.entry.source))
    checkpoint = next(
        index for index, value in enumerate(values) if value.name == "checkpoint"
    )
    values[checkpoint] = ArtifactInput("checkpoint", ArtifactState.MISSING)
    result = archive.archive(
        admission,
        synthetic_capture_profile(),
        tuple(values),
        KeyMaterial("ephemeral-test-key-v1", b"k" * 32),
    )
    assert result.acknowledgement.state is AcknowledgementState.REJECTED
    assert (
        result.acknowledgement.reason
        is AcknowledgementReason.REQUIRED_ARTIFACT_UNAVAILABLE
    )

    second, _, _, _ = _archive(tmp_path / "second")
    second_admission = _admit(second)
    optional_missing = tuple(
        (
            ArtifactInput(value.name, ArtifactState.MISSING)
            if value.name == "debug_trace"
            else value
        )
        for value in _artifact_inputs(second_admission.entry.source)
    )
    accepted = second.archive(
        second_admission,
        synthetic_capture_profile(),
        optional_missing,
        KeyMaterial("ephemeral-test-key-v1", b"k" * 32),
    )
    assert accepted.acknowledgement.state is AcknowledgementState.VERIFIED_DURABLE


def test_later_withdrawal_appends_state_and_does_not_rewrite_historical_ack(
    tmp_path,
) -> None:
    archive, catalogue, _, _ = _archive(tmp_path)
    admission = _admit(archive)
    key = KeyMaterial("ephemeral-test-key-v1", b"k" * 32)
    result = archive.archive(
        admission,
        synthetic_capture_profile(),
        _artifact_inputs(admission.entry.source),
        key,
    )
    historical_ref = result.acknowledgement.acknowledgement_ref
    archive.record_unavailability(
        result.entry,
        "checkpoint",
        ArtifactState.WITHDRAWN,
        "synthetic-policy-withdrawal-v1",
    )
    current, completeness = archive.verify_current(
        result.entry, synthetic_capture_profile(), result.manifest, key
    )
    assert current.state is AcknowledgementState.REJECTED
    assert current.reason is AcknowledgementReason.REQUIRED_ARTIFACT_UNAVAILABLE
    assert completeness is EvidenceCompleteness.UNAVAILABLE
    assert historical_ref in catalogue.acks


def test_duplicate_converges_conflict_tamper_and_wrong_key_fail_closed(
    tmp_path,
) -> None:
    archive, _, _, objects = _archive(tmp_path)
    admission = _admit(archive)
    key = KeyMaterial("ephemeral-test-key-v1", b"k" * 32)
    inputs = _artifact_inputs(admission.entry.source)
    first = archive.archive(admission, synthetic_capture_profile(), inputs, key)
    duplicate = archive.archive(admission, synthetic_capture_profile(), inputs, key)
    assert duplicate.manifest.content_identity == first.manifest.content_identity

    tampered_record = dataclasses.replace(
        first.manifest.artifacts[0],
        plaintext_size=first.manifest.artifacts[0].plaintext_size + 1,
    )
    tampered_manifest = dataclasses.replace(
        first.manifest,
        artifacts=(tampered_record, *first.manifest.artifacts[1:]),
    )
    rejected_manifest, _ = archive.verify_current(
        first.entry, synthetic_capture_profile(), tampered_manifest, key
    )
    assert rejected_manifest.reason is AcknowledgementReason.MANIFEST_NOT_VERIFIED

    with pytest.raises(ArchiveFailure) as captured:
        archive.archive(
            admission,
            synthetic_capture_profile(),
            tuple(
                (
                    ArtifactInput(
                        value.name, value.state, SYNTHETIC_FIXTURE_PREFIX + b"changed"
                    )
                    if value.name == "checkpoint"
                    else value
                )
                for value in inputs
            ),
            key,
        )
    assert captured.value.code is ArchiveCode.CONFLICT

    ack, _ = archive.verify_current(
        first.entry,
        synthetic_capture_profile(),
        first.manifest,
        KeyMaterial("ephemeral-test-key-v1", b"w" * 32),
    )
    assert ack.state is AcknowledgementState.REJECTED
    assert ack.reason is AcknowledgementReason.OBJECT_UNAVAILABLE
    object_key = next(
        record.object_key for record in first.manifest.artifacts if record.object_key
    )
    objects.values[object_key] = objects.values[object_key][:-1] + b"x"
    tampered, _ = archive.verify_current(
        first.entry, synthetic_capture_profile(), first.manifest, key
    )
    assert tampered.reason is AcknowledgementReason.OBJECT_UNAVAILABLE


def test_linked_retry_and_reexecution_never_overwrite_attempt_history(tmp_path) -> None:
    archive, catalogue, _, _ = _archive(tmp_path)
    first = _admit(archive)
    for kind, attempt in (
        (AttemptRelationKind.RETRY_OF, 2),
        (AttemptRelationKind.REEXECUTION_OF, 3),
    ):
        source = _source(attempt=attempt)
        linked = _admit(
            archive,
            source=source,
            relation=AttemptRelation(kind, first.entry.archive_entry_id),
        )
        first = linked
    assert len(catalogue.admissions) == 3
    assert len(set(catalogue.admissions)) == 3


def test_capacity_exact_boundary_concurrency_and_release(tmp_path) -> None:
    limits = CapacityLimits(
        max_active_entries=1, max_objects=7, max_bytes=65536, max_spool_bytes=65536
    )
    archive, catalogue, _, _ = _archive(tmp_path, limits=limits)
    first = _admit(archive)
    errors = []

    def attempt_second():
        try:
            _admit(
                archive,
                source=dataclasses.replace(
                    _source(),
                    submission_id="00000000-0000-4000-8000-000000000002",
                    execution_id="synthetic-execution-other",
                    physical_attempt_id="synthetic-attempt-other",
                ),
            )
        except ArchiveFailure as failure:
            errors.append(failure.code)

    threads = [threading.Thread(target=attempt_second) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == [ArchiveCode.CAPACITY, ArchiveCode.CAPACITY]
    archive.archive(
        first,
        synthetic_capture_profile(),
        _artifact_inputs(first.entry.source),
        KeyMaterial("ephemeral-test-key-v1", b"k" * 32),
    )
    second_source = dataclasses.replace(
        _source(),
        submission_id="00000000-0000-4000-8000-000000000003",
        execution_id="synthetic-execution-released",
        physical_attempt_id="synthetic-attempt-released",
    )
    assert (
        _admit(archive, source=second_source).entry.archive_entry_id
        in catalogue.admissions
    )


@pytest.mark.parametrize(
    "value",
    (
        "../escape",
        "v1/carbon-synthetic-ci/" + "a" * 64 + "/../" + "b" * 64 + ".bin",
        "v1/other-tenant/" + "a" * 64 + "/checkpoint/" + "b" * 64 + ".bin",
    ),
)
def test_invalid_paths_and_cross_tenant_access_fail_before_storage(value) -> None:
    with pytest.raises(ArchiveFailure):
        validate_object_key(value, "carbon-synthetic-ci")


def test_unsubmitted_or_unmarked_bytes_are_rejected_before_storage(tmp_path) -> None:
    archive, _, _, objects = _archive(tmp_path)
    admission = _admit(archive)
    inputs = tuple(
        (
            ArtifactInput(value.name, value.state, b"customer-looking-bytes")
            if value.name == "checkpoint"
            else value
        )
        for value in _artifact_inputs(admission.entry.source)
    )
    with pytest.raises(ArchiveFailure) as captured:
        archive.archive(
            admission,
            synthetic_capture_profile(),
            inputs,
            KeyMaterial("ephemeral-test-key-v1", b"k" * 32),
        )
    assert captured.value.code is ArchiveCode.DENIED
    assert objects.values == {}


def test_ephemeral_key_bytes_never_enter_catalogue_or_journal_events(tmp_path) -> None:
    archive, catalogue, _journal, _ = _archive(tmp_path)
    admission = _admit(archive)
    secret = b"z" * 32
    archive.archive(
        admission,
        synthetic_capture_profile(),
        _artifact_inputs(admission.entry.source),
        KeyMaterial("ephemeral-test-key-v1", secret),
    )
    serialized = repr(catalogue.__dict__).encode()
    assert secret not in serialized
    raw = (tmp_path / "spool.sqlite3").read_bytes()
    assert secret not in raw
    assert SYNTHETIC_FIXTURE_PREFIX not in raw


def test_orphans_quarantine_without_guessing_source_ownership(tmp_path) -> None:
    archive, catalogue, _, objects = _archive(tmp_path)
    orphan_key = derive_object_key(
        "carbon-synthetic-ci", _sha("a"), "checkpoint", _sha("b")
    )
    objects.values[orphan_key] = b"ciphertext-without-authority"
    quarantined = archive.quarantine_orphans()
    assert len(quarantined) == 1
    assert orphan_key not in objects.values
    assert orphan_key in catalogue.orphans


def test_health_is_bounded_to_counts_and_closed_availability(tmp_path) -> None:
    archive, _, _, _ = _archive(tmp_path)
    health = archive.health()
    assert health.schema_version == "carbon.evidence-archive.health.v1"
    assert health.catalogue_available is True
    assert health.object_store_available is True
    assert health.active_catalogue_reservations == 0
    assert "key" not in repr(health).lower()
    assert "payload" not in repr(health).lower()


def test_aead_wrong_digest_and_metadata_tampering_fail() -> None:
    key = KeyMaterial("ephemeral-test-key-v1", b"k" * 32)
    payload = SYNTHETIC_FIXTURE_PREFIX + b"payload"
    digest = content_digest("carbon.evidence-artifact.v1", payload)
    envelope = encrypt_artifact(
        payload,
        entry_id=_sha("a"),
        artifact_name="checkpoint",
        plaintext_digest=digest,
        key=key,
        nonce=b"n" * 12,
    )
    from carbon.evidence_archive import decrypt_artifact

    for changed in (
        dataclasses.replace(envelope, ciphertext=envelope.ciphertext[:-1] + b"x"),
        dataclasses.replace(envelope, nonce_hex=(b"m" * 12).hex()),
    ):
        with pytest.raises(ArchiveFailure):
            decrypt_artifact(
                changed,
                entry_id=_sha("a"),
                artifact_name="checkpoint",
                plaintext_digest=digest,
                key=key,
            )


def test_stage_journal_schema_corruption_fails_closed(tmp_path) -> None:
    path = tmp_path / "spool.sqlite3"
    StageJournal(path, CapacityLimits())
    import sqlite3

    with sqlite3.connect(path) as db:
        db.execute("UPDATE cea1_journal_meta SET schema_version='corrupt'")
    with pytest.raises(ArchiveFailure) as captured:
        StageJournal(path, CapacityLimits())
    assert captured.value.code is ArchiveCode.STORE
